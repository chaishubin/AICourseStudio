"""
AI Course Studio - Web 服务

提供教案/PPT 上传、课程知识模型编辑与三路渲染器调度的 Web 界面。
"""

import os
import uuid
import json
import threading
import sys
import time
from pathlib import Path
from queue import Queue, Empty
from flask import Flask, render_template, request, jsonify, send_file, make_response, Response
from werkzeug.utils import secure_filename
from loguru import logger

# 导入 vidppt
sys.path.insert(0, str(Path(__file__).parent.parent))
from vidppt import Pipeline, ProcessConfig
from vidppt.core.course import Course, CourseSection, KnowledgePoint
from vidppt.utils.progress import ProcessStage

# 导入处理器以触发注册
import vidppt.processors  # noqa: F401

app = Flask(__name__,
            template_folder=Path(__file__).parent / 'templates',
            static_folder=Path(__file__).parent / 'static')

DASHBOARD_ENABLED = os.environ.get('VIDPPT_DASHBOARD', 'true').lower() == 'true'
if DASHBOARD_ENABLED:
    sys.path.insert(0, str(Path(__file__).parent))
    from api.system_stats import system_stats_bp
    app.register_blueprint(system_stats_bp)

# 配置
UPLOAD_FOLDER = Path(__file__).parent / 'uploads'
OUTPUT_FOLDER = Path(__file__).parent / 'outputs'
ALLOWED_EXTENSIONS = {'docx', 'pdf', 'ppt', 'pptx'}
STATE_FILE = OUTPUT_FOLDER / 'state.json'
_state_lock = threading.Lock()
_continue_lock = threading.Lock()
MAX_STATE_ENTRIES = 50

# 确保目录存在
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['OUTPUT_FOLDER'] = str(OUTPUT_FOLDER)

# 存储任务状态和进度队列
tasks = {}  # task_id -> {status, file_path, output_dir, stage, percentage, message, video_path, error}
progress_queues = {}  # task_id -> Queue


class ConversionQueue:
    """串行转换队列，保证同一时刻只运行一个转换任务"""

    def __init__(self):
        self._queue = Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def enqueue(self, func, *args, **kwargs):
        self._queue.put((func, args, kwargs))

    def _run(self):
        while True:
            func, args, kwargs = self._queue.get()
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"ConversionQueue worker error: {e}")


conversion_queue = ConversionQueue()


def save_state(task_id: str):
    """将指定任务的状态持久化到 state.json（JSON 数组格式）"""
    task = tasks.get(task_id)
    if not task:
        return
    with _state_lock:
        data = _read_state_file()
        # 构建当前任务条目
        entry = {'task_id': task_id}
        entry.update(task)
        file_path = task.get('file_path', '')
        if file_path and 'original_name' not in entry:
            name = Path(file_path).name
            parts = name.split('_', 1)
            entry['original_name'] = parts[1] if len(parts) > 1 else name
        # 按 task_id 查找并更新/追加
        found = False
        for i, item in enumerate(data):
            if item.get('task_id') == task_id:
                data[i] = entry
                found = True
                break
        if not found:
            data.append(entry)
        # 限制最近 50 条
        data = data[-MAX_STATE_ENTRIES:]
        try:
            STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass


def _read_state_file() -> list:
    """读取 state.json，兼容旧版单对象格式"""
    if not STATE_FILE.exists():
        return []
    try:
        raw = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        if isinstance(raw, list):
            return raw
        # 旧版单对象格式
        return [raw]
    except Exception:
        return []


def load_state():
    """服务启动时从 state.json 恢复所有已完成/出错的任务状态"""
    data = _read_state_file()
    for entry in data:
        task_id = entry.get('task_id')
        if not task_id:
            continue
        status = entry.get('status', '')
        if status in ('awaiting_confirmation', 'completed', 'error'):
            tasks[task_id] = entry


# 启动时恢复状态
load_state()


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """渲染主页面"""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_ppt():
    """上传PPT文件接口"""
    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    # 检查文件是否为空（0字节）
    file.seek(0, 2)  # 移动到文件末尾
    file_size = file.tell()
    file.seek(0)  # 重置到文件开头
    if file_size == 0:
        return jsonify({'error': '文件为空，请选择有效的PPT文件'}), 400

    # 直接从原始文件名取扩展名，不依赖 secure_filename 保留中文
    original_filename = file.filename
    if '.' in original_filename:
        ext = original_filename.rsplit('.', 1)[1].lower()
    else:
        ext = ''
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': '不支持的文件类型'}), 400

    # 磁盘文件名只使用服务端生成的 UUID，原始名称仅作为展示元数据。
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = UPLOAD_FOLDER / unique_filename

    # 保存文件
    file.save(file_path)

    return jsonify({
        'success': True,
        'file_path': str(file_path),
        'original_name': original_filename
    })


class WebProgressTracker:
    """Web端进度跟踪器，将进度推送到队列"""

    STAGE_ORDER = ['init', 'extract', 'render', 'llm', 'tts', 'video']
    STAGE_WEIGHT = 100 / len(STAGE_ORDER)  # 每个阶段占 20%

    def __init__(self, task_id: str, queue: Queue, total_pages: int = 0):
        self.task_id = task_id
        self.queue = queue
        self.total_pages = total_pages
        self.current_stage = None
        self.current_progress = 0
        self.stage_progress = {}  # stage_name -> {current, total, percentage}
        self._stage_started_at = None
        self._update_task(started_at=time.time(), stage_timings={})

    def _overall_percentage(self, stage: str, stage_pct: float) -> int:
        """将阶段局部百分比转换为整体百分比"""
        idx = self.STAGE_ORDER.index(stage) if stage in self.STAGE_ORDER else 0
        return int(idx * self.STAGE_WEIGHT + (stage_pct / 100) * self.STAGE_WEIGHT)

    def _update_task(self, **kwargs):
        """更新 tasks 字典中的最新状态，合并 stage_timings"""
        task = tasks.get(self.task_id, {})
        if 'stage_timings' in kwargs:
            existing = task.get('stage_timings', {})
            existing.update(kwargs.pop('stage_timings'))
            task['stage_timings'] = existing
        task.update(kwargs)
        tasks[self.task_id] = task
        # 持久化到 state.json（已完成/出错时写入，处理中也可写入以保留进度）
        save_state(self.task_id)

    def _complete_current_stage(self):
        """记录当前阶段的耗时"""
        if self.current_stage and self._stage_started_at:
            duration = time.time() - self._stage_started_at
            self._update_task(stage_timings={
                self.current_stage: {'duration': round(duration, 2)}
            })

    def update(self, stage: str, current: int, total: int, message: str = ""):
        """更新进度"""
        self.current_stage = stage
        self.current_progress = int((current / total * 100) if total > 0 else 0)

        # 计算整体进度
        overall = self._overall_percentage(stage, self.current_progress)

        self.stage_progress[stage] = {
            'current': current,
            'total': total,
            'percentage': self.current_progress
        }

        self._update_task(
            status='processing',
            stage=stage,
            percentage=overall,
            message=message,
        )

        # 推送到队列
        self.queue.put({
            'type': 'progress',
            'stage': stage,
            'current': current,
            'total': total,
            'percentage': overall,
            'message': message
        })

    def set_stage(self, stage: str, message: str = ""):
        """设置当前阶段"""
        self._complete_current_stage()
        self.current_stage = stage
        self._stage_started_at = time.time()

        self._update_task(
            status='processing',
            stage=stage,
            message=message,
            stage_started_at=self._stage_started_at,
        )

        self.queue.put({
            'type': 'stage',
            'stage': stage,
            'message': message
        })

    def complete(self, video_path: str = None, **artifacts):
        """标记完成"""
        self._complete_current_stage()
        self._update_task(
            status='completed',
            stage='complete',
            percentage=100,
            message='转换完成',
            video_path=video_path,
            completed_at=time.time(),
            **artifacts,
        )

        event = {
            'type': 'complete',
            'video_path': video_path,
            'message': '转换完成',
        }
        event.update(artifacts)
        self.queue.put(event)

    def preview_ready(self, preview_path: str, **artifacts):
        """暂停任务并通知前端进入逐页讲稿确认阶段。"""
        self._complete_current_stage()
        self._update_task(
            status='awaiting_confirmation',
            stage='preview',
            percentage=50,
            message='预览已生成，请确认逐页讲稿',
            preview_path=preview_path,
            **artifacts,
        )
        self.queue.put({
            'type': 'preview_ready',
            'preview_path': preview_path,
            'message': '预览已生成，请确认逐页讲稿',
            **artifacts,
        })

    def error(self, error_msg: str):
        """标记错误"""
        self._complete_current_stage()
        self._update_task(
            status='error',
            error=error_msg,
            completed_at=time.time(),
        )

        self.queue.put({
            'type': 'error',
            'message': error_msg
        })


def run_conversion(task_id: str, file_path: str, output_dir: Path,
                   tts_engine: str = 'edge-tts', voice: str = 'zh-CN-XiaoxiaoNeural',
                   render_engine: str = 'spire',
                   llm_enabled: bool = False, llm_mode: str = 'per-page',
                   llm_engine: str = 'qwen'):
    """在后台线程中运行转换"""
    queue = progress_queues.get(task_id)
    if not queue:
        return

    progress = WebProgressTracker(task_id, queue)

    try:
        # 1. 初始化
        progress.set_stage('init', '初始化转换...')

        # 2. 创建配置（LLM 由内联逻辑处理，不通过 Pipeline）
        logger.info(f"render_engine = {render_engine}")
        tts_options = {}
        tts_voice = voice
        if tts_engine == 'volcengine':
            tts_options['voice_type'] = voice
            tts_voice = None
        elif tts_engine == 'minimax':
            tts_options['voice_id'] = voice
            tts_voice = None

        config = ProcessConfig(
            input_path=Path(file_path),
            output_dir=output_dir,
            save_intermediate=True,
            skip_existing=True,
            tts_engine=tts_engine,
            tts_voice=tts_voice,
            tts_options=tts_options,
            render_engine=render_engine,
            llm_enabled=llm_enabled,
            llm_engine=llm_engine,
        )

        # 3. 创建 Pipeline（仅用于 TTS 引擎）
        pipeline = Pipeline(config)

        progress.update('init', 1, 1, '初始化完成')

        # 4. 分步执行，实时推送进度

        # 获取处理器
        from vidppt.core.registry import ProcessorRegistry
        processor_class = ProcessorRegistry.get_processor(Path(file_path))
        if not processor_class:
            raise ValueError(f"不支持的文件类型: {Path(file_path).suffix}")

        processor = processor_class()

        # 4a. 提取内容
        progress.set_stage('extract', '提取PPT内容...')
        content = processor.extract_content(config)
        total_pages = content.total_pages
        progress.total_pages = total_pages
        progress.update('extract', total_pages, total_pages, f'提取完成，共 {total_pages} 页')

        # 4b. 渲染幻灯片
        progress.set_stage('render', '渲染幻灯片截图...')
        slide_images = processor.render_pages(config)
        for page, image in zip(content.pages, slide_images):
            page.slide_image = image
        progress.update('render', len(slide_images), len(slide_images), f'渲染完成，共 {len(slide_images)} 页')

        # 4c. LLM 文本摘要
        if llm_enabled:
            progress.set_stage('llm', 'LLM 文本摘要...')

            llm_provider = pipeline.llm_engine

            # 保存原文
            for page in content.pages:
                page.metadata["original_text"] = page.text

            total_pages = content.total_pages

            if llm_mode == "per-page":
                for i, page in enumerate(content.pages, 1):
                    if not page.text or not page.text.strip():
                        progress.update('llm', i, total_pages, f'第 {i} 页无文本，跳过')
                        continue
                    page.text = llm_provider.summarize(page.text)
                    progress.update('llm', i, total_pages, f'摘要第 {i}/{total_pages} 页')
            elif llm_mode == "whole-document":
                pages_text = [page.text for page in content.pages]
                summary = llm_provider.summarize_document(pages_text)
                content.pages[0].text = summary
                for page in content.pages[1:]:
                    page.text = ""
                progress.update('llm', total_pages, total_pages, '整文档摘要完成')

            progress.update('llm', total_pages, total_pages, '文本摘要完成')

        preview_path = _write_preview(
            task_id,
            source_type='presentation',
            pages=[
                {
                    'page_number': page.page_number,
                    'title': _page_title(page.text, page.page_number),
                    'image_path': str(page.slide_image),
                    'script': page.text,
                    'original_script': page.text,
                }
                for page in content.pages
            ],
        )
        progress.preview_ready(str(preview_path))

    except Exception as e:
        import traceback
        traceback.print_exc()
        progress.error(str(e))


def run_course_generation(
    task_id: str,
    file_path: str,
    output_dir: Path,
    tts_engine: str,
    voice: str,
    render_engine: str,
    llm_enabled: bool,
    llm_engine: str,
):
    """Word/PDF 教案生成 Course、PPTX、字幕和视频。"""
    queue = progress_queues.get(task_id)
    if not queue:
        return
    progress = WebProgressTracker(task_id, queue)

    try:
        progress.set_stage('extract', '读取教案结构...')
        tts_options = {}
        tts_voice = voice
        if tts_engine == 'volcengine':
            tts_options['voice_type'] = voice
            tts_voice = None
        elif tts_engine == 'minimax':
            tts_options['voice_id'] = voice
            tts_voice = None

        llm_provider = None
        if llm_enabled:
            progress.set_stage('llm', 'AI 正在设计课程结构与逐页讲稿...')
            if llm_engine == 'qwen':
                from vidppt.engines.llm.qwen_llm_engine import QwenLLMEngine
                llm_provider = QwenLLMEngine()
            elif llm_engine == 'minimax':
                from vidppt.engines.llm.minimax_llm_engine import MiniMaxLLMEngine
                llm_provider = MiniMaxLLMEngine()
            else:
                raise ValueError(f"不支持的文本模型: {llm_engine}")

        config = ProcessConfig(
            input_path=Path(file_path),
            output_dir=output_dir,
            tts_engine=tts_engine,
            tts_voice=tts_voice,
            tts_options=tts_options,
            render_engine=render_engine,
            enable_tts=False,
            enable_video=False,
        )

        progress.set_stage('render', '生成可编辑 PPT 与课程资源...')
        from vidppt.course_pipeline import CoursePipeline
        result = CoursePipeline(llm_provider).run(
            Path(file_path), output_dir
        )

        from vidppt.processors.ppt_processor import PPTProcessor
        preview_content = PPTProcessor().process(ProcessConfig(
            **{
                **config.__dict__,
                'input_path': result.presentation,
                'save_intermediate': True,
                'skip_existing': False,
            }
        ))
        if len(preview_content.pages) != len(result.course.sections):
            raise RuntimeError("生成 PPT 页数与课程讲稿数量不一致")

        preview_path = _write_preview(
            task_id,
            source_type='lesson_plan',
            pages=[
                {
                    'page_number': page.page_number,
                    'title': section.title,
                    'image_path': str(page.slide_image),
                    'script': section.script or section.title,
                    'original_script': section.script or section.title,
                }
                for page, section in zip(preview_content.pages, result.course.sections)
            ],
            course_json_path=str(result.course_json),
            presentation_path=str(result.presentation),
        )
        progress.preview_ready(
            str(preview_path),
            course_json_path=str(result.course_json),
            presentation_path=str(result.presentation),
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        progress.error(str(e))


def _page_title(text: str, page_number: int) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), '')
    if first_line in {'[幻灯片正文]', '[演讲者备注]'}:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        first_line = lines[1] if len(lines) > 1 else ''
    return first_line[:80] or f'第 {page_number} 页'


def _preview_file(task_id: str) -> Path:
    task = tasks.get(task_id)
    if not task:
        raise KeyError("任务不存在")
    return Path(task['output_dir']) / 'preview.json'


def _write_preview(task_id: str, source_type: str, pages: list[dict], **artifacts) -> Path:
    preview_path = _preview_file(task_id)
    payload = {
        'task_id': task_id,
        'source_type': source_type,
        'pages': pages,
        **artifacts,
    }
    preview_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return preview_path


def _read_preview(task_id: str) -> dict:
    preview_path = _preview_file(task_id)
    if not preview_path.exists():
        raise FileNotFoundError("预览数据不存在")
    return json.loads(preview_path.read_text(encoding='utf-8'))


def _update_preview_scripts(task_id: str, updates: list[dict]) -> dict:
    preview = _read_preview(task_id)
    by_page = {
        int(item['page_number']): str(item.get('script', '')).strip()
        for item in updates
        if 'page_number' in item
    }
    for page in preview.get('pages', []):
        page_number = int(page['page_number'])
        if page_number in by_page:
            page['script'] = by_page[page_number]
    if not any(page.get('script', '').strip() for page in preview.get('pages', [])):
        raise ValueError("至少需要保留一页非空讲稿")
    _preview_file(task_id).write_text(
        json.dumps(preview, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    course_json_path = preview.get('course_json_path')
    if course_json_path:
        course_path = Path(course_json_path)
        course = Course.from_dict(json.loads(course_path.read_text(encoding='utf-8')))
        scripts = {
            int(page['page_number']): page.get('script', '')
            for page in preview.get('pages', [])
        }
        for page_number, section in enumerate(course.sections, 1):
            if page_number in scripts:
                section.script = scripts[page_number]
        course_path.write_text(
            json.dumps(course.to_dict(), ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
    return preview


def run_media_generation(task_id: str):
    """读取用户确认后的逐页讲稿，生成配音、字幕和最终视频。"""
    queue = progress_queues.get(task_id)
    if not queue:
        return
    progress = WebProgressTracker(task_id, queue)
    try:
        from moviepy import AudioFileClip
        from vidppt.core.models import DocumentContent, PageContent
        from vidppt.renderers.subtitles import SubtitleRenderer
        from vidppt.utils.progress import ProgressTracker
        from vidppt.utils.video_composer import VideoComposer
        from vidppt.course_pipeline import CoursePipeline

        task = tasks[task_id]
        preview = _read_preview(task_id)
        options = task.get('media_options', {})
        config = ProcessConfig(
            input_path=Path(task['file_path']),
            output_dir=Path(task['output_dir']),
            save_intermediate=True,
            skip_existing=False,
            tts_engine=options.get('tts_engine', 'edge-tts'),
            tts_voice=options.get('tts_voice'),
            tts_options=options.get('tts_options', {}),
            render_engine=options.get('render_engine', 'spire'),
            enable_tts=True,
            enable_video=True,
        )
        content = DocumentContent(pages=[
            PageContent(
                page_number=int(page['page_number']),
                text=page.get('script', ''),
                slide_image=Path(page['image_path']),
            )
            for page in preview.get('pages', [])
        ])

        progress.set_stage('tts', '根据确认后的讲稿生成配音...')
        Pipeline(config)._generate_audio(
            content, ProgressTracker(total_pages=len(content.pages))
        )
        progress.update('tts', len(content.pages), len(content.pages), '语音转换完成')

        timed_pages = []
        for page in content.pages:
            if page.text.strip() and (not page.audio or not page.audio.exists()):
                raise RuntimeError(f"第 {page.page_number} 页配音生成失败")
            duration = 3.0
            if page.audio and page.audio.exists():
                audio = AudioFileClip(str(page.audio))
                duration = audio.duration
                audio.close()
            timed_pages.append((
                CourseSection(
                    id=f"slide-{page.page_number}",
                    title=_page_title(page.text, page.page_number),
                    script=page.text,
                ),
                duration,
            ))

        stem = Path(task['file_path']).stem
        subtitles = SubtitleRenderer().render_course(
            timed_pages, config.output_dir / f'{stem}.srt'
        )
        progress.set_stage('video', '合成视频并烧录字幕...')
        base_video = config.output_dir / f'{stem}.base.mp4'
        VideoComposer.compose(content, config, base_video)
        if not base_video.exists():
            raise RuntimeError("视频合成未产生输出文件")
        video_path = config.output_dir / f'{stem}.mp4'
        CoursePipeline._burn_subtitles(base_video, subtitles, video_path)
        base_video.unlink(missing_ok=True)
        progress.update('video', 1, 1, '视频生成完成')
        progress.complete(
            str(video_path),
            course_json_path=preview.get('course_json_path'),
            presentation_path=preview.get('presentation_path'),
            subtitles_path=str(subtitles),
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        progress.error(str(e))


def run_render_only(task_id: str, file_path: str, output_dir: Path,
                    render_engine: str = 'spire'):
    """仅渲染幻灯片截图，不做 TTS 和视频合成"""
    queue = progress_queues.get(task_id)
    if not queue:
        return

    progress = WebProgressTracker(task_id, queue)

    try:
        progress.set_stage('render', '渲染幻灯片截图...')

        from vidppt.core.registry import ProcessorRegistry
        processor_class = ProcessorRegistry.get_processor(Path(file_path))
        if not processor_class:
            raise ValueError(f"不支持的文件类型: {Path(file_path).suffix}")

        processor = processor_class()

        config = ProcessConfig(
            input_path=Path(file_path),
            output_dir=output_dir,
            render_engine=render_engine,
            save_intermediate=True,
            skip_existing=False,
            enable_tts=False,
            enable_video=False,
        )

        slide_images = processor.render_pages(config)
        total = len(slide_images)

        tasks[task_id]['status'] = 'rendered'
        tasks[task_id]['slide_count'] = total
        save_state(task_id)

        progress.update('render', total, total, f'渲染完成，共 {total} 页')

        queue.put({
            'type': 'rendered',
            'slide_count': total,
            'message': f'渲染完成，共 {total} 页'
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['error'] = str(e)
        save_state(task_id)

        queue.put({
            'type': 'error',
            'message': str(e)
        })


@app.route('/api/convert', methods=['POST'])
def convert_ppt():
    """
    PPT转视频接口
    启动异步转换并返回 task_id
    """
    data = request.get_json()
    file_path = data.get('file_path')
    original_name = data.get('original_name') or Path(file_path or '').name
    tts_engine = data.get('tts_engine', 'edge-tts')
    voice = data.get('voice', 'zh-CN-XiaoxiaoNeural')
    render_engine = data.get('render_engine', 'spire')
    llm_enabled = data.get('llm_enabled', False)
    llm_mode = data.get('llm_mode', 'per-page')
    llm_engine = data.get('llm_engine', 'qwen')

    if not file_path:
        return jsonify({'error': '未提供文件路径'}), 400

    # 检查文件是否存在
    if not Path(file_path).exists():
        return jsonify({'error': '文件不存在'}), 404

    # 生成任务 ID
    task_id = uuid.uuid4().hex

    # 创建输出目录
    output_dir = OUTPUT_FOLDER / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # 创建进度队列
    progress_queues[task_id] = Queue()
    tasks[task_id] = {
        'status': 'pending',
        'file_path': file_path,
        'output_dir': str(output_dir),
        'original_name': original_name,
        'media_options': {
            'tts_engine': tts_engine,
            'tts_voice': None if tts_engine in {'volcengine', 'minimax'} else voice,
            'tts_options': (
                {'voice_type': voice} if tts_engine == 'volcengine'
                else {'voice_id': voice} if tts_engine == 'minimax'
                else {}
            ),
            'render_engine': render_engine,
        },
    }

    suffix = Path(file_path).suffix.lower()
    if suffix in {'.docx', '.pdf'}:
        conversion_queue.enqueue(
            run_course_generation, task_id, file_path, output_dir,
            tts_engine, voice, render_engine, llm_enabled, llm_engine
        )
    else:
        conversion_queue.enqueue(
            run_conversion, task_id, file_path, output_dir, tts_engine, voice,
            render_engine, llm_enabled, llm_mode, llm_engine
        )

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': '转换已启动'
    })


@app.route('/api/course-preview/<task_id>')
def get_course_preview(task_id):
    """返回逐页 PPT 图片和可编辑讲稿。"""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    if task.get('status') != 'awaiting_confirmation':
        return jsonify({'error': '任务尚未进入讲稿确认阶段'}), 409
    try:
        preview = _read_preview(task_id)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return jsonify({'error': str(exc)}), 404
    preview['pages'] = [
        {
            **page,
            'image_url': f"/api/slide-image?path={page['image_path']}",
        }
        for page in preview.get('pages', [])
    ]
    return jsonify(preview)


@app.route('/api/course-preview/<task_id>', methods=['PATCH'])
def save_course_preview(task_id):
    """持久化用户修改的逐页讲稿，但不启动媒体生成。"""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    if task.get('status') != 'awaiting_confirmation':
        return jsonify({'error': '当前任务不能修改讲稿'}), 409
    data = request.get_json(silent=True) or {}
    pages = data.get('pages')
    if not isinstance(pages, list):
        return jsonify({'error': 'pages 必须是数组'}), 400
    try:
        _update_preview_scripts(task_id, pages)
    except (ValueError, KeyError, FileNotFoundError, json.JSONDecodeError) as exc:
        return jsonify({'error': str(exc)}), 400
    tasks[task_id]['message'] = '讲稿已保存，等待继续'
    save_state(task_id)
    return jsonify({'success': True, 'message': '讲稿已保存'})


@app.route('/api/course-continue/<task_id>', methods=['POST'])
def continue_course(task_id):
    """确认最终讲稿，并将 TTS/字幕/视频阶段重新加入转换队列。"""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    data = request.get_json(silent=True) or {}
    pages = data.get('pages')

    with _continue_lock:
        if task.get('status') != 'awaiting_confirmation':
            return jsonify({'error': '任务已继续或当前状态不可继续'}), 409
        try:
            if pages is not None:
                if not isinstance(pages, list):
                    raise ValueError("pages 必须是数组")
                _update_preview_scripts(task_id, pages)
            else:
                _read_preview(task_id)
        except (ValueError, KeyError, FileNotFoundError, json.JSONDecodeError) as exc:
            return jsonify({'error': str(exc)}), 400

        progress_queues[task_id] = Queue()
        task.update(
            status='pending',
            stage='tts',
            percentage=50,
            message='已确认讲稿，等待生成配音',
        )
        save_state(task_id)
        conversion_queue.enqueue(run_media_generation, task_id)

    return jsonify({'success': True, 'message': '已继续生成视频'})


@app.route('/api/render-slides', methods=['POST'])
def render_slides():
    """仅渲染幻灯片截图接口"""
    data = request.get_json()
    file_path = data.get('file_path')
    render_engine = data.get('render_engine', 'spire')

    if not file_path:
        return jsonify({'error': '未提供文件路径'}), 400

    if not Path(file_path).exists():
        return jsonify({'error': '文件不存在'}), 404

    task_id = uuid.uuid4().hex
    output_dir = OUTPUT_FOLDER / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    progress_queues[task_id] = Queue()
    uploaded_name = Path(file_path).name
    name_parts = uploaded_name.split('_', 1)
    original_name = name_parts[1] if len(name_parts) > 1 else uploaded_name
    tasks[task_id] = {
        'status': 'pending',
        'file_path': file_path,
        'output_dir': str(output_dir),
        'original_name': original_name,
    }

    conversion_queue.enqueue(run_render_only, task_id, file_path, output_dir, render_engine)

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': '渲染已启动'
    })


@app.route('/api/slides/<task_id>')
def get_slides(task_id):
    """获取任务的所有幻灯片图片路径"""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    output_dir = Path(task.get('output_dir', ''))
    if not output_dir.exists():
        return jsonify({'slides': []})

    slides = []
    page_num = 1
    while True:
        slide_path = output_dir / str(page_num) / "slide.png"
        if not slide_path.exists():
            break
        slides.append({
            'page': page_num,
            'url': f'/api/slide-image?path={str(slide_path)}'
        })
        page_num += 1

    return jsonify({'slides': slides})


@app.route('/api/slide-image')
def get_slide_image():
    """获取单张幻灯片图片"""
    slide_path = request.args.get('path', '')
    try:
        return send_file(slide_path, mimetype='image/png')
    except FileNotFoundError:
        return jsonify({'error': '图片不存在'}), 404


@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    """
    SSE 接口，推送转换进度
    """
    queue = progress_queues.get(task_id)
    if not queue:
        return jsonify({'error': '任务不存在'}), 404

    def generate():
        idle_seconds = 0
        HEARTBEAT_INTERVAL = 25   # 每 25 秒发一次心跳
        MAX_IDLE = 600          # 10 分钟无真实消息才判定超时
        while True:
            try:
                data = queue.get(timeout=HEARTBEAT_INTERVAL)
                idle_seconds = 0  # 收到真实消息，重置空闲计时

                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

                if data.get('type') in ('preview_ready', 'complete', 'error'):
                    if task_id in progress_queues:
                        del progress_queues[task_id]
                    break

            except Empty:
                idle_seconds += HEARTBEAT_INTERVAL
                if idle_seconds >= MAX_IDLE:
                    yield f"data: {json.dumps({'type': 'timeout', 'message': '连接超时'}, ensure_ascii=False)}\n\n"
                    break
                # 发送 SSE 注释行作为心跳，浏览器会自动忽略
                yield ": keepalive\n\n"

            except Exception:
                yield f"data: {json.dumps({'type': 'error', 'message': '服务内部错误'}, ensure_ascii=False)}\n\n"
                break

    return Response(
        generate(),
        mimetype='text/event-stream; charset=utf-8',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/status/<task_id>')
def get_status(task_id):
    """获取任务状态"""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    return jsonify({
        'task_id': task_id,
        'status': task.get('status', 'unknown'),
        'video_path': task.get('video_path'),
        'course_json_path': task.get('course_json_path'),
        'presentation_path': task.get('presentation_path'),
        'subtitles_path': task.get('subtitles_path'),
        'preview_path': task.get('preview_path'),
        'error': task.get('error')
    })


@app.route('/api/tasks')
def get_tasks():
    """返回所有任务的列表（最近 50 条）"""
    all_tasks = []
    for task_id, task in tasks.items():
        all_tasks.append({
            'task_id': task_id,
            'status': task.get('status', 'unknown'),
            'original_name': task.get('original_name', ''),
            'stage': task.get('stage'),
            'percentage': task.get('percentage', 0),
            'message': task.get('message', ''),
            'video_path': task.get('video_path'),
            'course_json_path': task.get('course_json_path'),
            'presentation_path': task.get('presentation_path'),
            'subtitles_path': task.get('subtitles_path'),
            'preview_path': task.get('preview_path'),
            'error': task.get('error'),
        })
    # 按最近排序，限制 50 条
    all_tasks = all_tasks[-MAX_STATE_ENTRIES:]
    return jsonify({'tasks': all_tasks})


@app.route('/api/active-task')
def get_active_task():
    """获取当前正在运行或刚完成的任务，供前端刷新后恢复状态"""
    for task_id, task in tasks.items():
        status = task.get('status', '')
        if status in ('pending', 'processing') or \
           (status in ('completed', 'error') and task_id in progress_queues):
            return jsonify({
                'task_id': task_id,
                'status': status,
                'stage': task.get('stage'),
                'percentage': task.get('percentage', 0),
                'message': task.get('message', ''),
                'video_path': task.get('video_path'),
                'original_name': task.get('original_name', ''),
                'file_path': task.get('file_path', ''),
                'error': task.get('error'),
                'started_at': task.get('started_at'),
                'completed_at': task.get('completed_at'),
            })
    # 也返回最近完成的任务（1个）
    completed = [(tid, t) for tid, t in tasks.items() if t.get('status') in ('completed', 'error')]
    if completed:
        tid, t = completed[-1]
        return jsonify({
            'task_id': tid,
            'status': t.get('status'),
            'stage': t.get('stage'),
            'percentage': t.get('percentage', 0),
            'message': t.get('message', ''),
            'video_path': t.get('video_path'),
            'original_name': t.get('original_name', ''),
            'file_path': t.get('file_path', ''),
            'error': t.get('error'),
            'started_at': t.get('started_at'),
            'completed_at': t.get('completed_at'),
        })
    return jsonify({'active': False})


@app.route('/api/last-result')
def get_last_result():
    """返回 state.json 中最近完成的任务结果（含 original_name）"""
    data = _read_state_file()
    if not data:
        return jsonify({'found': False})
    # 查找最后一个已完成且有视频的任务
    for entry in reversed(data):
        status = entry.get('status')
        if status in ('completed', 'error'):
            video_path = entry.get('video_path')
            if video_path and not Path(video_path).exists():
                continue
            return jsonify({
                'found': True,
                'task_id': entry.get('task_id'),
                'status': status,
                'stage': entry.get('stage'),
                'percentage': entry.get('percentage', 0),
                'message': entry.get('message', ''),
                'video_path': video_path,
                'original_name': entry.get('original_name', ''),
                'error': entry.get('error'),
                'started_at': entry.get('started_at'),
                'completed_at': entry.get('completed_at'),
            })
    return jsonify({'found': False})


@app.route('/api/task-timing')
def get_task_timing():
    """获取任务计时信息"""
    # 优先查找正在运行的任务
    for task_id, task in tasks.items():
        status = task.get('status', '')
        if status in ('pending', 'processing'):
            return jsonify({
                'active': True,
                'status': status,
                'current_stage': task.get('stage'),
                'started_at': task.get('started_at'),
                'stage_started_at': task.get('stage_started_at'),
                'stage_timings': task.get('stage_timings', {}),
            })
    # 再查找最近完成的任务
    completed = [(tid, t) for tid, t in tasks.items() if t.get('status') in ('completed', 'error')]
    if completed:
        tid, t = completed[-1]
        return jsonify({
            'active': False,
            'status': t.get('status'),
            'current_stage': None,
            'started_at': t.get('started_at'),
            'completed_at': t.get('completed_at'),
            'stage_timings': t.get('stage_timings', {}),
            'error': t.get('error'),
        })
    return jsonify({'active': False, 'no_task': True})


@app.route('/api/video')
def get_video():
    """获取视频文件用于预览"""
    video_path = request.args.get('path', '')
    try:
        return send_file(video_path, mimetype='video/mp4')
    except FileNotFoundError:
        return jsonify({'error': '视频文件不存在'}), 404


@app.route('/api/frame')
def get_frame():
    """获取视频第一帧图片用于预览"""
    frame_path = request.args.get('path', '')
    try:
        return send_file(frame_path, mimetype='image/png')
    except FileNotFoundError:
        return jsonify({'error': '图片文件不存在'}), 404


@app.route('/api/download')
def download_file():
    """下载文件"""
    file_path = request.args.get('path', '')
    try:
        filename = Path(file_path).name
        response = make_response(send_file(file_path))
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response
    except FileNotFoundError:
        return jsonify({'error': '文件不存在'}), 404


@app.route('/api/voices')
def list_voices():
    """列出可用的语音"""
    voices = {
        'edge-tts': [
            {'id': 'zh-CN-XiaoxiaoNeural', 'name': '晓晓（女声）', 'gender': 'female'},
            {'id': 'zh-CN-YunxiNeural', 'name': '云希（男声）', 'gender': 'male'},
            {'id': 'zh-CN-YunyangNeural', 'name': '云扬（男声，新闻风格）', 'gender': 'male'},
            {'id': 'zh-CN-XiaoyiNeural', 'name': '晓伊（女声）', 'gender': 'female'},
            {'id': 'zh-CN-YunjianNeural', 'name': '云健（男声）', 'gender': 'male'},
        ],
        'minimax': [
            {'id': 'male-qn-qingse', 'name': '青涩男声', 'gender': 'male'},
            {'id': 'female-qn-nana', 'name': '娜娜女声', 'gender': 'female'},
            {'id': 'male-qn-jingying', 'name': '精英男声', 'gender': 'male'},
            {'id': 'female-shaonv', 'name': '少女女声', 'gender': 'female'},
        ],
        'volcengine': [
            {
                'id': 'zh_female_cancan_mars_bigtts',
                'name': '灿灿（女声）',
                'gender': 'female'
            },
            {
                'id': 'zh_male_M392_conversation_wvae_bigtts',
                'name': '通用男声',
                'gender': 'male'
            },
        ],
    }
    return jsonify(voices)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='AI Course Studio - Web Server')
    parser.description = 'AI Course Studio - Web Server'
    parser.add_argument('port', nargs='?', type=int, default=5000, help='端口号 (默认: 5000)')
    args = parser.parse_args()
    app.run(debug=True, host='0.0.0.0', port=args.port)
