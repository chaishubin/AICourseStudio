"""
AI Course Studio - Web 服务

提供教案/PPT 上传、课程知识模型编辑与三路渲染器调度的 Web 界面。
"""

import os
import uuid
import json
import hashlib
import asyncio
import threading
import sys
import time
import shutil
import secrets
from pathlib import Path
from queue import Queue, Empty
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    make_response,
    Response,
    redirect,
    url_for,
    session,
)
from werkzeug.utils import secure_filename
from loguru import logger
try:
    from task_store import TaskStore
except ImportError:
    from web.task_store import TaskStore

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
app.secret_key = os.environ.get('VIDPPT_SECRET_KEY') or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('VIDPPT_COOKIE_SECURE', 'false').lower() == 'true',
)

AUTH_USERNAME = os.environ.get('VIDPPT_AUTH_USERNAME', 'admin')
AUTH_PASSWORD = os.environ.get('VIDPPT_AUTH_PASSWORD', 'vidppt123')

DASHBOARD_ENABLED = os.environ.get('VIDPPT_DASHBOARD', 'true').lower() == 'true'
if DASHBOARD_ENABLED:
    sys.path.insert(0, str(Path(__file__).parent))
    from api.system_stats import system_stats_bp
    app.register_blueprint(system_stats_bp)

# 配置
UPLOAD_FOLDER = Path(__file__).parent / 'uploads'
OUTPUT_FOLDER = Path(__file__).parent / 'outputs'
ALLOWED_EXTENSIONS = {'docx', 'pdf', 'ppt', 'pptx'}
ALLOWED_LOGO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
DEFAULT_STATE_FILE = OUTPUT_FOLDER / 'state.json'
STATE_FILE = DEFAULT_STATE_FILE
TASK_DB_FILE = Path(os.environ.get(
    'VIDPPT_TASK_DB',
    str(OUTPUT_FOLDER / 'tasks.db'),
))
VOICE_PREVIEW_FOLDER = OUTPUT_FOLDER / 'voice_previews'
VOICE_PREVIEW_TEXT = "你好，欢迎使用 AI 课程工作室，这是当前音色的试听效果。"
_state_lock = threading.Lock()
_continue_lock = threading.Lock()
MAX_STATE_ENTRIES = 50
RESOURCE_CPU_LIMIT = float(os.environ.get('VIDPPT_CPU_LIMIT', '85'))
RESOURCE_MEMORY_LIMIT = float(os.environ.get('VIDPPT_MEMORY_LIMIT', '80'))
RESOURCE_MIN_DISK_GB = float(os.environ.get('VIDPPT_MIN_DISK_GB', '5'))
RESOURCE_CHECK_INTERVAL = float(os.environ.get('VIDPPT_RESOURCE_CHECK_INTERVAL', '5'))

# 确保目录存在
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
VOICE_PREVIEW_FOLDER.mkdir(parents=True, exist_ok=True)

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['OUTPUT_FOLDER'] = str(OUTPUT_FOLDER)

# 存储任务状态和进度队列
tasks = {}  # task_id -> {status, file_path, output_dir, stage, percentage, message, video_path, error}
progress_queues = {}  # task_id -> Queue
cancellation_events = {}  # task_id -> threading.Event
task_store = TaskStore(TASK_DB_FILE)


class ConversionQueue:
    """串行转换队列，保证同一时刻只运行一个转换任务"""

    def __init__(self):
        self._queue = Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def enqueue(self, func, *args, **kwargs):
        self._queue.put((func, args, kwargs))

    def _wait_for_capacity(self, task_id):
        while True:
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=0.3)
                memory = psutil.virtual_memory().percent
                disk_free_gb = psutil.disk_usage(OUTPUT_FOLDER).free / (1024 ** 3)
            except ImportError:
                return
            if (
                cpu < RESOURCE_CPU_LIMIT
                and memory < RESOURCE_MEMORY_LIMIT
                and disk_free_gb >= RESOURCE_MIN_DISK_GB
            ):
                return
            task = tasks.get(task_id)
            if task:
                task.update(
                    status='queued',
                    stage='queue',
                    message=(
                        f'机器资源繁忙，等待执行（CPU {cpu:.0f}% / '
                        f'内存 {memory:.0f}% / 磁盘剩余 {disk_free_gb:.1f}GB）'
                    ),
                )
                save_state(task_id)
            time.sleep(RESOURCE_CHECK_INTERVAL)

    def _run(self):
        while True:
            func, args, kwargs = self._queue.get()
            try:
                task_id = args[0] if args else None
                if task_id:
                    self._wait_for_capacity(task_id)
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"ConversionQueue worker error: {e}")
            finally:
                self._queue.task_done()

    def size(self):
        return self._queue.qsize()


conversion_queue = ConversionQueue()


def _synthesize_voice_preview(engine_name: str, voice: str, output_path: Path):
    """使用现有 TTS 引擎生成短试听音频。"""
    if engine_name == 'edge-tts':
        from vidppt.engines.tts.edge_tts_engine import EdgeTTSEngine
        engine = EdgeTTSEngine()
    elif engine_name == 'volcengine':
        from vidppt.engines.tts.volcengine_tts_engine import VolcengineTTSEngine
        engine = VolcengineTTSEngine()
    elif engine_name == 'minimax':
        from vidppt.engines.tts.api_tts_engine import MiniMaxTTSEngine
        engine = MiniMaxTTSEngine()
    else:
        raise ValueError(f'不支持的语音引擎: {engine_name}')
    asyncio.run(engine.convert_async(
        VOICE_PREVIEW_TEXT,
        output_path,
        voice,
        '+0%',
    ))


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
        if STATE_FILE == DEFAULT_STATE_FILE:
            try:
                queue_order = task_store.upsert(task_id, entry)
                task['queue_order'] = queue_order
            except Exception as exc:
                logger.warning(f'Unable to persist task {task_id} to SQLite: {exc}')


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
    data = []
    if STATE_FILE == DEFAULT_STATE_FILE:
        try:
            data = task_store.load_recent(MAX_STATE_ENTRIES)
        except Exception:
            data = []
    if not data:
        data = _read_state_file()
    for entry in data:
        task_id = entry.get('task_id')
        if not task_id:
            continue
        status = entry.get('status', '')
        preview_path = entry.get('preview_path')
        if (
            status == 'error'
            and entry.get('stage') in {'tts', 'video'}
            and preview_path
            and Path(preview_path).exists()
        ):
            entry.update(
                status='awaiting_confirmation',
                stage='preview',
                percentage=50,
                message='上次媒体生成失败，已恢复到讲稿确认，可调整后重试',
                failed_stage=entry.get('stage'),
                retryable=True,
            )
            status = 'awaiting_confirmation'
        if status in ('pending', 'processing'):
            entry.update(
                status='interrupted',
                stage='queue',
                message='服务曾重启，请重新提交该任务',
                error='任务执行被服务重启中断',
            )
            status = 'interrupted'
        if status in ('queued', 'awaiting_confirmation', 'completed', 'error', 'interrupted'):
            tasks[task_id] = entry


# 启动时恢复状态
load_state()


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.before_request
def require_login():
    """保护工作台与业务 API，仅放行登录页和静态资源。"""
    if app.config.get('LOGIN_DISABLED'):
        return None
    if request.endpoint in {'login', 'static'} or session.get('authenticated'):
        return None
    if request.path.startswith('/api/'):
        return jsonify({'error': '请先登录', 'code': 'authentication_required'}), 401
    return redirect(url_for('login', next=request.full_path if request.query_string else request.path))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面与凭据校验。"""
    if session.get('authenticated'):
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        username_ok = secrets.compare_digest(username, AUTH_USERNAME)
        password_ok = secrets.compare_digest(password, AUTH_PASSWORD)
        if username_ok and password_ok:
            session.clear()
            session['authenticated'] = True
            session['username'] = username
            next_url = request.form.get('next', '')
            if next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect(url_for('index'))
        error = '用户名或密码错误，请重新输入'

    return render_template('login.html', error=error, next_url=request.args.get('next', ''))


@app.route('/logout', methods=['POST'])
def logout():
    """退出当前登录会话。"""
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
def index():
    """渲染主页面"""
    return render_template('index.html', current_user=session.get('username', AUTH_USERNAME))


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


@app.route('/api/logo-upload', methods=['POST'])
def upload_logo():
    """上传并校验学校 Logo，返回仅供后续课程生成使用的服务端路径。"""
    from PIL import Image, UnidentifiedImageError

    file = request.files.get('logo')
    if not file or not file.filename:
        return jsonify({'error': '未选择 Logo 文件'}), 400
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        return jsonify({'error': 'Logo 仅支持 PNG、JPG 或 WebP'}), 400
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size == 0:
        return jsonify({'error': 'Logo 文件为空'}), 400
    if size > 5 * 1024 * 1024:
        return jsonify({'error': 'Logo 文件不能超过 5MB'}), 400

    logo_path = UPLOAD_FOLDER / f"logo_{uuid.uuid4().hex}.{ext}"
    file.save(logo_path)
    try:
        with Image.open(logo_path) as image:
            image.verify()
    except (UnidentifiedImageError, OSError):
        logo_path.unlink(missing_ok=True)
        return jsonify({'error': 'Logo 图片无法识别或已损坏'}), 400
    return jsonify({'success': True, 'logo_path': str(logo_path)})


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
        task = tasks.get(self.task_id, {})
        stage_base = self._overall_percentage(stage, 0)
        overall = max(int(task.get('percentage', 0) or 0), stage_base)

        self._update_task(
            status='processing',
            stage=stage,
            percentage=overall,
            message=message,
            stage_started_at=self._stage_started_at,
        )

        self.queue.put({
            'type': 'stage',
            'stage': stage,
            'percentage': overall,
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

    def rollback(self, error_msg: str, failed_stage: str):
        """媒体阶段失败时回到讲稿确认，不丢弃已完成的中间产物。"""
        self._complete_current_stage()
        task = tasks.get(self.task_id, {})
        self._update_task(
            status='awaiting_confirmation',
            stage='preview',
            percentage=50,
            message=f'{failed_stage}失败，已退回讲稿确认，可直接重试',
            error=error_msg,
            failed_stage=failed_stage,
            retryable=True,
        )
        self.queue.put({
            'type': 'rollback',
            'message': error_msg,
            'failed_stage': failed_stage,
            'preview_path': task.get('preview_path'),
            'course_json_path': task.get('course_json_path'),
            'presentation_path': task.get('presentation_path'),
        })


def run_conversion(task_id: str, file_path: str, output_dir: Path,
                   tts_engine: str = 'edge-tts', voice: str = 'zh-CN-XiaoxiaoNeural',
                   render_engine: str = 'spire',
                   llm_enabled: bool = False, llm_mode: str = 'per-page',
                   llm_engine: str = 'qwen',
                   refinement_level: str = 'standard'):
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
                refinement_prompts = {
                    'light': '尽量保留当前页原文和篇幅，只修正重复、病句与生硬表达。',
                    'standard': '保留关键知识，合并重复内容，生成详略适中的自然讲稿。',
                    'strong': '只保留核心结论、关键依据与必要过渡，讲稿简洁有力。',
                }
                refinement_prompt = refinement_prompts.get(
                    refinement_level, refinement_prompts['standard']
                )
                original_texts = [page.text for page in content.pages]
                previous_script = ""
                for i, page in enumerate(content.pages, 1):
                    if not page.text or not page.text.strip():
                        progress.update('llm', i, total_pages, f'第 {i} 页无文本，跳过')
                        continue
                    previous_text = original_texts[i - 2] if i > 1 else "（无，当前为第一页）"
                    next_text = (
                        original_texts[i] if i < total_pages
                        else "（无，当前为最后一页）"
                    )
                    page.text = llm_provider.summarize(
                        (
                            f"上一页原文：\n{previous_text}\n\n"
                            f"上一页已生成讲稿：\n{previous_script or '（无）'}\n\n"
                            f"当前页原文：\n{original_texts[i - 1]}\n\n"
                            f"下一页原文：\n{next_text}"
                        ),
                        system_prompt=(
                            "你是课程讲稿编辑。结合前后页理解当前页在整套课程中的位置，"
                            "让开头承接上一页、结尾自然引向下一页；避免重复上一页已经讲过的内容，"
                            "也不要提前展开下一页。只输出当前页可直接配音的讲稿，不要标题、说明或标记。"
                            + refinement_prompt
                        ),
                    )
                    previous_script = page.text
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
    refinement_level: str,
    illustrations_enabled: bool,
    max_illustrations: int,
    ppt_footer_text: str,
    school_logo_path: str | None,
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
        illustration_generator = None
        if illustrations_enabled:
            from vidppt.generation import DashScopeIllustrationGenerator
            illustration_generator = DashScopeIllustrationGenerator()

        result = CoursePipeline(
            llm_provider,
            refinement_level,
            illustration_generator=illustration_generator,
            max_illustrations=max_illustrations,
            footer_text=ppt_footer_text,
            logo_path=Path(school_logo_path) if school_logo_path else None,
        ).run(
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
    changed_pages = set()
    by_page = {
        int(item['page_number']): str(item.get('script', '')).strip()
        for item in updates
        if 'page_number' in item
    }
    for page in preview.get('pages', []):
        page_number = int(page['page_number'])
        if page_number in by_page:
            if page.get('script', '').strip() != by_page[page_number]:
                changed_pages.add(page_number)
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
    output_dir = Path(tasks[task_id]['output_dir'])
    for page_number in changed_pages:
        (output_dir / str(page_number) / 'audio.mp3').unlink(missing_ok=True)
    return preview


def run_media_generation(task_id: str):
    """读取用户确认后的逐页讲稿，生成配音、字幕和最终视频。"""
    queue = progress_queues.get(task_id)
    if not queue:
        return
    progress = WebProgressTracker(task_id, queue)
    cancel_event = cancellation_events.setdefault(task_id, threading.Event())
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
            skip_existing=True,
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
        if cancel_event.is_set():
            raise InterruptedError("用户停止了生成")
        Pipeline(config)._generate_audio(
            content, ProgressTracker(total_pages=len(content.pages))
        )
        if cancel_event.is_set():
            raise InterruptedError("用户停止了生成")
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
        last_reported = -1

        def report_video(stage_percentage: int, message: str):
            nonlocal last_reported
            stage_percentage = max(0, min(100, stage_percentage))
            if stage_percentage > last_reported:
                last_reported = stage_percentage
                progress.update('video', stage_percentage, 100, message)

        VideoComposer.compose(
            content,
            config,
            base_video,
            progress_callback=lambda fraction: report_video(
                round(fraction * 78),
                f'正在编码视频 {round(fraction * 100)}%',
            ),
            cancel_check=cancel_event.is_set,
        )
        if not base_video.exists():
            raise RuntimeError("视频合成未产生输出文件")
        video_path = config.output_dir / f'{stem}.mp4'
        CoursePipeline._burn_subtitles(
            base_video,
            subtitles,
            video_path,
            config,
            progress_callback=lambda fraction: report_video(
                78 + round(fraction * 20),
                f'正在烧录字幕 {round(fraction * 100)}%',
            ),
            cancel_check=cancel_event.is_set,
        )
        base_video.unlink(missing_ok=True)
        progress.update('video', 100, 100, '视频生成完成')
        progress.complete(
            str(video_path),
            course_json_path=preview.get('course_json_path'),
            presentation_path=preview.get('presentation_path'),
            subtitles_path=str(subtitles),
        )
    except InterruptedError as e:
        import traceback
        traceback.print_exc()
        progress.rollback(str(e), '生成已停止')
    except Exception as e:
        import traceback
        traceback.print_exc()
        failed_stage = (
            '视频合成' if progress.current_stage == 'video' else '配音生成'
        )
        progress.rollback(str(e), failed_stage)
    finally:
        cancellation_events.pop(task_id, None)


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
    refinement_level = data.get('refinement_level', 'standard')
    illustrations_enabled = bool(data.get('illustrations_enabled', False))
    max_illustrations = int(data.get('max_illustrations', 3))
    ppt_footer_text = str(
        data.get('ppt_footer_text', 'AI COURSE STUDIO')
    ).strip()[:40]
    school_logo_path = data.get('school_logo_path')
    batch_id = str(data.get('batch_id') or uuid.uuid4().hex)
    strategy_source = data.get('strategy_source', 'batch')
    if refinement_level not in {'light', 'standard', 'strong'}:
        return jsonify({'error': '不支持的精炼程度'}), 400
    if max_illustrations not in {1, 2, 3, 4}:
        return jsonify({'error': '插图数量必须为 1 到 4'}), 400
    if school_logo_path:
        logo_path = Path(school_logo_path)
        if (
            not logo_path.is_file()
            or logo_path.parent.resolve() != UPLOAD_FOLDER.resolve()
            or logo_path.suffix.lower().lstrip('.') not in ALLOWED_LOGO_EXTENSIONS
        ):
            return jsonify({'error': '学校 Logo 路径无效，请重新上传'}), 400

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
    strategy = {
        'tts_engine': tts_engine,
        'voice': voice,
        'render_engine': render_engine,
        'llm_enabled': llm_enabled,
        'llm_engine': llm_engine,
        'llm_mode': llm_mode,
        'refinement_level': refinement_level,
        'illustrations_enabled': illustrations_enabled,
        'max_illustrations': max_illustrations,
        'ppt_footer_text': ppt_footer_text,
        'school_logo_path': school_logo_path,
    }
    tasks[task_id] = {
        'status': 'queued',
        'stage': 'queue',
        'percentage': 0,
        'message': '已进入生产队列',
        'file_path': file_path,
        'output_dir': str(output_dir),
        'original_name': original_name,
        'batch_id': batch_id,
        'strategy_source': strategy_source,
        'strategy': strategy,
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
    save_state(task_id)

    suffix = Path(file_path).suffix.lower()
    if suffix in {'.docx', '.pdf'}:
        conversion_queue.enqueue(
            run_course_generation, task_id, file_path, output_dir,
            tts_engine, voice, render_engine, llm_enabled, llm_engine,
            refinement_level, illustrations_enabled, max_illustrations,
            ppt_footer_text, school_logo_path
        )
    else:
        conversion_queue.enqueue(
            run_conversion, task_id, file_path, output_dir, tts_engine, voice,
            render_engine, llm_enabled, llm_mode, llm_engine, refinement_level
        )

    return jsonify({
        'success': True,
        'task_id': task_id,
        'batch_id': batch_id,
        'queue_size': conversion_queue.size(),
        'message': '任务已进入生产队列'
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
    tts_engine = data.get('tts_engine')
    voice = data.get('voice')

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

        if tts_engine and voice:
            task['media_options'] = {
                **task.get('media_options', {}),
                'tts_engine': tts_engine,
                'tts_voice': None if tts_engine in {'volcengine', 'minimax'} else voice,
                'tts_options': (
                    {'voice_type': voice} if tts_engine == 'volcengine'
                    else {'voice_id': voice} if tts_engine == 'minimax'
                    else {}
                ),
            }

        progress_queues[task_id] = Queue()
        cancellation_events[task_id] = threading.Event()
        task.update(
            status='pending',
            stage='tts',
            percentage=50,
            message='已确认讲稿，等待生成配音',
        )
        save_state(task_id)
        conversion_queue.enqueue(run_media_generation, task_id)

    return jsonify({'success': True, 'message': '已继续生成视频'})


@app.route('/api/stop/<task_id>', methods=['POST'])
def stop_task(task_id):
    """请求停止当前媒体生成；工作线程会清理并回退到讲稿确认。"""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    if task.get('status') not in {'pending', 'processing'}:
        return jsonify({'error': '当前任务不在运行中'}), 409
    cancel_event = cancellation_events.setdefault(task_id, threading.Event())
    cancel_event.set()
    task.update(message='正在停止生成，请稍候…', stop_requested=True)
    save_state(task_id)
    queue = progress_queues.get(task_id)
    if queue:
        queue.put({
            'type': 'progress',
            'stage': task.get('stage', 'video'),
            'current': task.get('percentage', 0),
            'total': 100,
            'percentage': task.get('percentage', 0),
            'message': '正在停止生成，请稍候…',
        })
    return jsonify({'success': True, 'message': '已请求停止，正在回退上一步'})


@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """物理删除未运行任务的输出目录及持久化状态。"""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    deletable_statuses = {
        'completed',
        'error',
        'interrupted',
        'awaiting_confirmation',
    }
    if task.get('status') not in deletable_statuses:
        return jsonify({'error': '任务仍在运行或排队，请先停止任务再删除'}), 409

    output_root = OUTPUT_FOLDER.resolve()
    output_dir = Path(task.get('output_dir') or (OUTPUT_FOLDER / task_id))
    try:
        resolved_output = output_dir.resolve()
    except OSError:
        return jsonify({'error': '任务输出路径无效'}), 400
    if (
        resolved_output.parent != output_root
        or resolved_output.name != task_id
    ):
        logger.warning(
            f'Refused to delete task {task_id}: unsafe output path {resolved_output}'
        )
        return jsonify({'error': '任务输出路径不安全，已拒绝删除'}), 400
    try:
        if resolved_output.exists():
            shutil.rmtree(resolved_output)
        with _state_lock:
            data = [
                entry for entry in _read_state_file()
                if entry.get('task_id') != task_id
            ]
            STATE_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
    except OSError as exc:
        logger.exception(f'Failed to delete task {task_id}: {exc}')
        return jsonify({'error': f'物理删除失败：{exc}'}), 500

    try:
        task_store.delete(task_id)
    except Exception as exc:
        logger.exception(f'Unable to delete task {task_id} from SQLite: {exc}')
        return jsonify({
            'error': '课程文件已删除，但数据库记录清理失败，请重试删除',
        }), 500
    tasks.pop(task_id, None)
    progress_queues.pop(task_id, None)
    cancellation_events.pop(task_id, None)
    return jsonify({'success': True, 'message': '课程产物已物理删除'})


@app.route('/api/course-cancel/<task_id>', methods=['POST'])
def cancel_course(task_id):
    """放弃待确认任务，让前端使用原上传文件重新选择生成策略。"""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    if task.get('status') != 'awaiting_confirmation':
        return jsonify({'error': '当前任务不能取消'}), 409

    with _state_lock:
        data = [
            entry for entry in _read_state_file()
            if entry.get('task_id') != task_id
        ]
        try:
            STATE_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
        except Exception:
            pass

    tasks.pop(task_id, None)
    progress_queues.pop(task_id, None)
    cancellation_events.pop(task_id, None)
    try:
        task_store.delete(task_id)
    except Exception as exc:
        logger.warning(f'Unable to delete cancelled task {task_id} from SQLite: {exc}')
    return jsonify({'success': True, 'message': '已取消本次生成'})


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
        'stage': task.get('stage'),
        'percentage': task.get('percentage', 0),
        'message': task.get('message', ''),
        'batch_id': task.get('batch_id'),
        'strategy_source': task.get('strategy_source', 'batch'),
        'queue_position': (
            sum(
                1
                for other in tasks.values()
                if other.get('status') == 'queued'
                and other.get('queue_order', float('inf'))
                <= task.get('queue_order', float('inf'))
            )
            if task.get('status') == 'queued'
            else None
        ),
        'error': task.get('error')
    })


@app.route('/api/tasks')
def get_tasks():
    """返回所有任务的列表（最近 50 条）"""
    all_tasks = []
    queued_ids = [
        task_id
        for task_id, task in sorted(
            tasks.items(),
            key=lambda item: item[1].get('queue_order', float('inf')),
        )
        if task.get('status') == 'queued'
    ]
    queue_positions = {
        task_id: index + 1 for index, task_id in enumerate(queued_ids)
    }
    for task_id, task in tasks.items():
        all_tasks.append({
            'task_id': task_id,
            'status': task.get('status', 'unknown'),
            'original_name': task.get('original_name', ''),
            'file_path': task.get('file_path', ''),
            'stage': task.get('stage'),
            'percentage': task.get('percentage', 0),
            'message': task.get('message', ''),
            'video_path': task.get('video_path'),
            'course_json_path': task.get('course_json_path'),
            'presentation_path': task.get('presentation_path'),
            'subtitles_path': task.get('subtitles_path'),
            'preview_path': task.get('preview_path'),
            'error': task.get('error'),
            'batch_id': task.get('batch_id'),
            'strategy_source': task.get('strategy_source', 'batch'),
            'strategy': task.get('strategy', {}),
            'queue_position': queue_positions.get(task_id),
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
    """列出各 TTS 引擎可用音色；Edge 优先从 SDK 动态读取完整目录。"""
    engine = request.args.get('engine')
    edge_voices = [
        {'id': 'zh-CN-XiaoxiaoNeural', 'name': '晓晓（女声）', 'gender': 'female'},
        {'id': 'zh-CN-YunxiNeural', 'name': '云希（男声）', 'gender': 'male'},
        {'id': 'zh-CN-YunyangNeural', 'name': '云扬（男声）', 'gender': 'male'},
        {'id': 'zh-CN-XiaoyiNeural', 'name': '晓伊（女声）', 'gender': 'female'},
        {'id': 'zh-CN-YunjianNeural', 'name': '云健（男声）', 'gender': 'male'},
    ]
    if engine in {None, 'edge-tts'}:
        try:
            import asyncio
            import edge_tts
            available = asyncio.run(edge_tts.list_voices())
            edge_voices = [
                {
                    'id': voice['ShortName'],
                    'name': (
                        f"{voice.get('FriendlyName', voice['ShortName'])} · "
                        f"{voice.get('Locale', '')}"
                    ),
                    'gender': str(voice.get('Gender', '')).lower(),
                }
                for voice in available
            ]
            preferred = {
                'zh-CN-XiaoxiaoNeural': 0,
                'zh-CN-YunxiNeural': 1,
                'zh-CN-YunyangNeural': 2,
            }
            edge_voices.sort(
                key=lambda voice: (
                    0 if voice['id'] in preferred else
                    1 if voice['id'].startswith('zh-CN-') else
                    2 if voice['id'].startswith('zh-') else 3,
                    preferred.get(voice['id'], 99),
                    voice['id'],
                )
            )
        except Exception as exc:
            logger.warning(f"动态读取 Edge 音色失败，使用内置目录: {exc}")

    minimax_zh = [
        ('male-qn-qingse', '青涩青年'), ('male-qn-jingying', '精英青年'),
        ('male-qn-badao', '霸道青年'), ('male-qn-daxuesheng', '青年大学生'),
        ('female-shaonv', '少女'), ('female-yujie', '御姐'),
        ('female-chengshu', '成熟女性'), ('female-tianmei', '甜美女性'),
        ('male-qn-qingse-jingpin', '青涩青年 beta'),
        ('male-qn-jingying-jingpin', '精英青年 beta'),
        ('male-qn-badao-jingpin', '霸道青年 beta'),
        ('male-qn-daxuesheng-jingpin', '青年大学生 beta'),
        ('female-shaonv-jingpin', '少女 beta'),
        ('female-yujie-jingpin', '御姐 beta'),
        ('female-chengshu-jingpin', '成熟女性 beta'),
        ('female-tianmei-jingpin', '甜美女性 beta'),
        ('clever_boy', '聪明男童'), ('cute_boy', '可爱男童'),
        ('lovely_girl', '萌萌女童'), ('cartoon_pig', '卡通猪小琪'),
        ('bingjiao_didi', '病娇弟弟'), ('junlang_nanyou', '俊朗男友'),
        ('chunzhen_xuedi', '纯真学弟'), ('lengdan_xiongzhang', '冷淡学长'),
        ('badao_shaoye', '霸道少爷'), ('tianxin_xiaoling', '甜心小玲'),
        ('qiaopi_mengmei', '俏皮萌妹'), ('wumei_yujie', '妩媚御姐'),
        ('diadia_xuemei', '嗲嗲学妹'), ('danya_xuejie', '淡雅学姐'),
        ('Chinese (Mandarin)_Reliable_Executive', '沉稳高管'),
        ('Chinese (Mandarin)_News_Anchor', '新闻女声'),
        ('Chinese (Mandarin)_Mature_Woman', '傲娇御姐'),
        ('Chinese (Mandarin)_Unrestrained_Young_Man', '不羁青年'),
        ('Chinese (Mandarin)_Gentleman', '温润男声'),
        ('Chinese (Mandarin)_Warm_Bestie', '温暖闺蜜'),
        ('Chinese (Mandarin)_Male_Announcer', '播报男声'),
        ('Chinese (Mandarin)_Sweet_Lady', '甜美女声'),
        ('Chinese (Mandarin)_Wise_Women', '阅历姐姐'),
        ('Chinese (Mandarin)_Gentle_Youth', '温润青年'),
        ('Chinese (Mandarin)_Warm_Girl', '温暖少女'),
        ('Chinese (Mandarin)_Radio_Host', '电台男主播'),
        ('Chinese (Mandarin)_Lyrical_Voice', '抒情男声'),
        ('Chinese (Mandarin)_Sincere_Adult', '真诚青年'),
        ('Chinese (Mandarin)_Gentle_Senior', '温柔学姐'),
        ('Chinese (Mandarin)_Crisp_Girl', '清脆少女'),
        ('Chinese (Mandarin)_Soft_Girl', '柔和少女'),
        ('Cantonese_ProfessionalHost（F)', '粤语专业女主持'),
        ('Cantonese_GentleLady', '粤语温柔女声'),
        ('Cantonese_ProfessionalHost（M)', '粤语专业男主持'),
        ('Cantonese_PlayfulMan', '粤语活泼男声'),
        ('Cantonese_CuteGirl', '粤语可爱女孩'),
        ('Cantonese_KindWoman', '粤语善良女声'),
    ]
    voices = {
        'edge-tts': edge_voices,
        'minimax': [
            {'id': voice_id, 'name': name, 'gender': ''}
            for voice_id, name in minimax_zh
        ],
        'volcengine': [
            {'id': 'zh_female_cancan_mars_bigtts', 'name': '灿灿', 'gender': 'female'},
            {'id': 'zh_female_vv_mars_bigtts', 'name': 'Vivi', 'gender': 'female'},
            {'id': 'zh_female_vv_uranus_bigtts', 'name': 'Vivi 2.0', 'gender': 'female'},
            {'id': 'zh_female_wanwanxiaohe_moon_bigtts', 'name': '湾湾小何', 'gender': 'female'},
            {'id': 'zh_male_shaonianzixin_moon_bigtts', 'name': '少年梓辛', 'gender': 'male'},
            {'id': 'zh_male_M392_conversation_wvae_bigtts', 'name': '通用男声', 'gender': 'male'},
            {'id': 'zh_female_yingyujiaoyu_mars_bigtts', 'name': 'Tina老师', 'gender': 'female'},
            {'id': 'zh_female_tianmeitaozi_mars_bigtts', 'name': '甜美桃子', 'gender': 'female'},
            {'id': 'zh_female_kefunvsheng_mars_bigtts', 'name': '暖阳女声', 'gender': 'female'},
            {'id': 'zh_female_qinqienvsheng_moon_bigtts', 'name': '亲切女声', 'gender': 'female'},
            {'id': 'zh_female_yueyunv_mars_bigtts', 'name': '粤语小溏', 'gender': 'female'},
            {'id': 'zh_male_dayi_saturn_bigtts', 'name': '大壹', 'gender': 'male'},
            {'id': 'zh_female_mizai_saturn_bigtts', 'name': '黑猫侦探社咪仔', 'gender': 'female'},
            {'id': 'zh_female_jitangnv_saturn_bigtts', 'name': '鸡汤女', 'gender': 'female'},
            {'id': 'zh_female_meilinvyou_saturn_bigtts', 'name': '魅力女友', 'gender': 'female'},
            {'id': 'zh_female_santongyongns_saturn_bigtts', 'name': '流畅女声', 'gender': 'female'},
            {'id': 'zh_male_ruyayichen_saturn_bigtts', 'name': '儒雅逸辰', 'gender': 'male'},
            {'id': 'zh_female_xueayi_saturn_bigtts', 'name': '儿童绘本', 'gender': 'female'},
            {'id': 'ICL_zh_female_keainvsheng_tob', 'name': '可爱女生', 'gender': 'female'},
            {'id': 'ICL_zh_female_tiaopigongzhu_tob', 'name': '调皮公主', 'gender': 'female'},
            {'id': 'ICL_zh_male_shuanglangshaonian_tob', 'name': '爽朗少年', 'gender': 'male'},
            {'id': 'ICL_zh_male_tiancaitongzhuo_tob', 'name': '天才同桌', 'gender': 'male'},
            {'id': 'zh_male_beijingxiaoye_emo_v2_mars_bigtts', 'name': '北京小爷（多情感）', 'gender': 'male'},
            {'id': 'zh_female_roumeinvyou_emo_v2_mars_bigtts', 'name': '柔美女友（多情感）', 'gender': 'female'},
            {'id': 'zh_male_yangguangqingnian_emo_v2_mars_bigtts', 'name': '阳光青年（多情感）', 'gender': 'male'},
            {'id': 'zh_female_meilinvyou_emo_v2_mars_bigtts', 'name': '魅力女友（多情感）', 'gender': 'female'},
            {'id': 'zh_female_shuangkuaisisi_emo_v2_mars_bigtts', 'name': '爽快思思（多情感）', 'gender': 'female'},
            {'id': 'zh_female_tianxinxiaomei_emo_v2_mars_bigtts', 'name': '甜心小美（多情感）', 'gender': 'female'},
            {'id': 'zh_male_lengkugege_emo_v2_mars_bigtts', 'name': '冷酷哥哥（多情感）', 'gender': 'male'},
        ],
    }
    if engine:
        if engine not in voices:
            return jsonify({'error': f'不支持的语音引擎: {engine}'}), 400
        return jsonify({
            'engine': engine,
            'voices': voices[engine],
            'count': len(voices[engine]),
            'supports_custom_voice': engine in {'volcengine', 'minimax'},
        })
    return jsonify(voices)


@app.route('/api/voice-preview', methods=['POST'])
def preview_voice():
    """生成并返回指定引擎、音色的短试听音频。"""
    data = request.get_json(silent=True) or {}
    engine = str(data.get('engine', '')).strip()
    voice = str(data.get('voice', '')).strip()
    if engine not in {'edge-tts', 'volcengine', 'minimax'}:
        return jsonify({'error': '不支持的语音引擎'}), 400
    if not voice or len(voice) > 200:
        return jsonify({'error': '无效的音色 ID'}), 400

    cache_key = hashlib.sha256(f'{engine}:{voice}'.encode()).hexdigest()
    preview_path = VOICE_PREVIEW_FOLDER / f'{cache_key}.mp3'
    try:
        if not preview_path.exists() or preview_path.stat().st_size == 0:
            _synthesize_voice_preview(engine, voice, preview_path)
        return send_file(preview_path, mimetype='audio/mpeg')
    except Exception as exc:
        logger.exception(f'生成音色试听失败: engine={engine}, voice={voice}')
        preview_path.unlink(missing_ok=True)
        return jsonify({'error': f'试听生成失败: {exc}'}), 502


def resume_queued_tasks():
    """Rebuild executable queue entries that were persisted before a restart."""
    resumed = 0
    for task_id, task in list(tasks.items()):
        if task.get('status') != 'queued':
            continue
        file_path = task.get('file_path')
        output_dir = Path(task.get('output_dir') or (OUTPUT_FOLDER / task_id))
        if not file_path or not Path(file_path).exists():
            task.update(status='error', error='源文件不存在，无法恢复排队任务')
            save_state(task_id)
            continue
        strategy = task.get('strategy') or {}
        progress_queues[task_id] = Queue()
        suffix = Path(file_path).suffix.lower()
        if suffix in {'.docx', '.pdf'}:
            conversion_queue.enqueue(
                run_course_generation,
                task_id,
                file_path,
                output_dir,
                strategy.get('tts_engine', 'edge-tts'),
                strategy.get('voice', 'zh-CN-XiaoxiaoNeural'),
                strategy.get('render_engine', 'spire'),
                strategy.get('llm_enabled', False),
                strategy.get('llm_engine', 'qwen'),
                strategy.get('refinement_level', 'standard'),
                strategy.get('illustrations_enabled', False),
                int(strategy.get('max_illustrations', 3)),
                strategy.get('ppt_footer_text', 'AI COURSE STUDIO'),
                strategy.get('school_logo_path'),
            )
        else:
            conversion_queue.enqueue(
                run_conversion,
                task_id,
                file_path,
                output_dir,
                strategy.get('tts_engine', 'edge-tts'),
                strategy.get('voice', 'zh-CN-XiaoxiaoNeural'),
                strategy.get('render_engine', 'spire'),
                strategy.get('llm_enabled', False),
                strategy.get('llm_mode', 'per-page'),
                strategy.get('llm_engine', 'qwen'),
                strategy.get('refinement_level', 'standard'),
            )
        resumed += 1
    if resumed:
        logger.info(f'Restored {resumed} queued production task(s)')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='AI Course Studio - Web Server')
    parser.description = 'AI Course Studio - Web Server'
    parser.add_argument('port', nargs='?', type=int, default=5000, help='端口号 (默认: 5000)')
    args = parser.parse_args()
    resume_queued_tasks()
    debug_enabled = os.environ.get('VIDPPT_DEBUG', 'false').lower() == 'true'
    app.run(
        debug=debug_enabled,
        use_reloader=False,
        threaded=True,
        host='0.0.0.0',
        port=args.port,
    )
