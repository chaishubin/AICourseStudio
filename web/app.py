"""
Web界面后端API
提供文件上传和PPT转视频的接口
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
ALLOWED_EXTENSIONS = {'ppt', 'pptx'}
STATE_FILE = OUTPUT_FOLDER / 'state.json'
_state_lock = threading.Lock()
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
        if status in ('completed', 'error'):
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

    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
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

    def complete(self, video_path: str = None):
        """标记完成"""
        self._complete_current_stage()
        self._update_task(
            status='completed',
            stage='complete',
            percentage=100,
            message='转换完成',
            video_path=video_path,
            completed_at=time.time(),
        )

        self.queue.put({
            'type': 'complete',
            'video_path': video_path,
            'message': '转换完成'
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
                   llm_enabled: bool = False, llm_mode: str = 'per-page'):
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
        config = ProcessConfig(
            input_path=Path(file_path),
            output_dir=output_dir,
            save_intermediate=True,
            skip_existing=True,
            tts_engine=tts_engine,
            tts_voice=voice,
            render_engine=render_engine,
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

            # 检查 API key
            api_key = os.getenv("MINIMAX_API")
            if not api_key:
                raise RuntimeError("LLM 摘要需要 MiniMax API。请设置环境变量 MINIMAX_API。")

            from vidppt.engines.llm.minimax_llm_engine import MiniMaxLLMEngine
            llm_engine = MiniMaxLLMEngine(api_key=api_key)

            # 保存原文
            for page in content.pages:
                page.metadata["original_text"] = page.text

            total_pages = content.total_pages

            if llm_mode == "per-page":
                for i, page in enumerate(content.pages, 1):
                    if not page.text or not page.text.strip():
                        progress.update('llm', i, total_pages, f'第 {i} 页无文本，跳过')
                        continue
                    page.text = llm_engine.summarize(page.text)
                    progress.update('llm', i, total_pages, f'摘要第 {i}/{total_pages} 页')
            elif llm_mode == "whole-document":
                pages_text = [page.text for page in content.pages]
                summary = llm_engine.summarize_document(pages_text)
                content.pages[0].text = summary
                for page in content.pages[1:]:
                    page.text = ""
                progress.update('llm', total_pages, total_pages, '整文档摘要完成')

            progress.update('llm', total_pages, total_pages, '文本摘要完成')

        # 5. TTS 转换
        progress.set_stage('tts', '文字转语音...')

        if config.enable_tts:
            # 手动执行 TTS（简化版本，实际应该使用 pipeline 的方法）
            import asyncio
            from vidppt.core.interfaces import TTSEngine

            tts_engine = pipeline.tts_engine

            page_texts = []
            for page in content.pages:
                if page.text and page.text.strip():
                    audio_path = output_dir / str(page.page_number) / "audio.mp3"
                    audio_path.parent.mkdir(parents=True, exist_ok=True)
                    page.audio = audio_path
                    page_texts.append((page.page_number, page.text, audio_path))

            total_tts = len(page_texts)

            # 执行 TTS
            if page_texts:
                def tts_callback(current: int, total: int, info: str):
                    progress.update('tts', current, total, info)

                # 运行异步 TTS
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    errors = loop.run_until_complete(
                        tts_engine.batch_convert(
                            page_texts,
                            voice=config.tts_voice,
                            rate=config.tts_rate,
                            progress_callback=tts_callback,
                        )
                    )

                    # 处理失败的页面
                    for page_num, _ in errors:
                        for page in content.pages:
                            if page.page_number == page_num:
                                page.audio = None
                finally:
                    loop.close()

            progress.update('tts', total_tts, total_tts, '语音转换完成')

        # 6. 视频合成
        progress.set_stage('video', '合成视频...')

        if config.enable_video:
            from vidppt.utils.video_composer import VideoComposer

            video_path = output_dir / f"{Path(file_path).stem}.mp4"
            VideoComposer.compose(content, config, video_path)

            progress.update('video', 1, 1, f'视频生成完成')

            # 完成
            progress.complete(str(video_path))
        else:
            progress.complete(None)

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
    tts_engine = data.get('tts_engine', 'edge-tts')
    voice = data.get('voice', 'zh-CN-XiaoxiaoNeural')
    render_engine = data.get('render_engine', 'spire')
    llm_enabled = data.get('llm_enabled', False)
    llm_mode = data.get('llm_mode', 'per-page')

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
    # 从上传文件路径中提取原始文件名（格式: <uuid>_<original_name>）
    uploaded_name = Path(file_path).name
    name_parts = uploaded_name.split('_', 1)
    original_name = name_parts[1] if len(name_parts) > 1 else uploaded_name
    tasks[task_id] = {
        'status': 'pending',
        'file_path': file_path,
        'output_dir': str(output_dir),
        'original_name': original_name,
    }

    # 入队串行执行
    conversion_queue.enqueue(run_conversion, task_id, file_path, output_dir, tts_engine, voice, render_engine, llm_enabled, llm_mode)

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': '转换已启动'
    })


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

                if data.get('type') in ('complete', 'error'):
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
        ]
    }
    return jsonify(voices)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='VidPPT Web Server')
    parser.add_argument('port', nargs='?', type=int, default=5000, help='端口号 (默认: 5000)')
    args = parser.parse_args()
    app.run(debug=True, host='0.0.0.0', port=args.port)
