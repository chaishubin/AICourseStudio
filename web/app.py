"""
AI Course Studio - Web 服务

提供教案/PPT 上传、课程知识模型编辑与三路渲染器调度的 Web 界面。
"""

import os
import re
import uuid
import json
import hashlib
import asyncio
import threading
import sys
import time
import shutil
import secrets
import subprocess
from io import BytesIO
from functools import lru_cache
from pathlib import Path
from queue import Queue, Empty
from urllib.parse import quote
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
SUPER_ADMIN_ROLE = 'super_admin'
USER_ROLE = 'user'


def _load_account_config() -> dict[str, dict]:
    """读取账号配置；默认保留原单管理员登录方式。"""
    accounts = {
        AUTH_USERNAME: {
            'password': AUTH_PASSWORD,
            'role': SUPER_ADMIN_ROLE,
            'display_name': AUTH_USERNAME,
        }
    }
    raw = os.environ.get('VIDPPT_USERS', '').strip()
    if not raw:
        return accounts
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(f'VIDPPT_USERS 解析失败，回退单管理员账号: {exc}')
        return accounts

    configured: dict[str, dict] = {}
    if isinstance(parsed, dict):
        iterable = parsed.items()
    elif isinstance(parsed, list):
        iterable = ((item.get('username'), item) for item in parsed if isinstance(item, dict))
    else:
        logger.warning('VIDPPT_USERS 必须是对象或数组，回退单管理员账号')
        return accounts

    for username, item in iterable:
        if isinstance(item, str):
            item = {'password': item}
        if not username or not isinstance(item, dict):
            continue
        password = str(item.get('password') or '').strip()
        if not password:
            continue
        role = str(item.get('role') or USER_ROLE).strip()
        if role not in {USER_ROLE, SUPER_ADMIN_ROLE}:
            role = USER_ROLE
        configured[str(username).strip()] = {
            'password': password,
            'role': role,
            'display_name': str(item.get('display_name') or username).strip(),
        }
    return configured or accounts


ACCOUNTS = _load_account_config()

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
SUBTITLE_FONT_FALLBACKS = [
    'Noto Sans CJK SC',
    'Noto Serif CJK SC',
    'Source Han Sans SC',
    'Source Han Serif SC',
    'Source Han Sans CN',
    'Source Han Serif CN',
    'WenQuanYi Zen Hei',
    'WenQuanYi Micro Hei',
    'Droid Sans Fallback',
    'AR PL UMing CN',
    'AR PL UKai CN',
    'AR PL SungtiL GB',
    'AR PL KaitiM GB',
    'LXGW WenKai',
    'LXGW WenKai Screen',
]
PROPRIETARY_SUBTITLE_FONTS = {
    'PingFang SC',
    'PingFang TC',
    'Heiti SC',
    'Heiti TC',
    'STHeiti',
    'STSong',
    'Songti SC',
    'Microsoft YaHei',
    'Microsoft JhengHei',
    'SimHei',
    'SimSun',
    'NSimSun',
    'KaiTi',
    'FangSong',
}
_state_lock = threading.Lock()
_continue_lock = threading.Lock()
_preview_audio_locks: dict[str, threading.Lock] = {}
MAX_STATE_ENTRIES = 50
RESOURCE_CPU_LIMIT = float(os.environ.get('VIDPPT_CPU_LIMIT', '85'))
RESOURCE_MEMORY_LIMIT = float(os.environ.get('VIDPPT_MEMORY_LIMIT', '80'))
RESOURCE_MIN_DISK_GB = float(os.environ.get('VIDPPT_MIN_DISK_GB', '2'))
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


def current_user_context() -> dict:
    """返回当前请求用户；测试关闭登录时视为超级管理员。"""
    if app.config.get('LOGIN_DISABLED'):
        return {
            'username': AUTH_USERNAME,
            'role': SUPER_ADMIN_ROLE,
            'display_name': AUTH_USERNAME,
        }
    username = session.get('username') or AUTH_USERNAME
    return {
        'username': username,
        'role': session.get('role') or ACCOUNTS.get(username, {}).get('role', USER_ROLE),
        'display_name': session.get('display_name') or ACCOUNTS.get(username, {}).get('display_name', username),
    }


def is_super_admin() -> bool:
    return current_user_context().get('role') == SUPER_ADMIN_ROLE


def _task_owner(task: dict | None) -> str:
    """旧任务没有 owner 时默认归属原单管理员账号。"""
    if not task:
        return AUTH_USERNAME
    return str(
        task.get('owner_username')
        or task.get('created_by')
        or AUTH_USERNAME
    )


def can_access_task(task: dict | None) -> bool:
    if not task:
        return False
    user = current_user_context()
    return user['role'] == SUPER_ADMIN_ROLE or _task_owner(task) == user['username']


def require_task_access(task_id: str):
    task = tasks.get(task_id)
    if not task:
        return None, (jsonify({'error': '任务不存在'}), 404)
    if not can_access_task(task):
        return None, (jsonify({'error': '无权访问该任务'}), 403)
    return task, None


def _path_belongs_to_task(path: Path, task: dict) -> bool:
    candidates = {
        task.get('file_path'),
        task.get('video_path'),
        task.get('course_json_path'),
        task.get('presentation_path'),
        task.get('subtitles_path'),
        task.get('preview_path'),
    }
    for segment in task.get('video_segments') or []:
        if isinstance(segment, dict):
            candidates.add(segment.get('video_path'))
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for candidate in candidates:
        if not candidate:
            continue
        try:
            if Path(candidate).resolve() == resolved:
                return True
        except OSError:
            continue
    output_dir = task.get('output_dir')
    if output_dir:
        try:
            resolved.relative_to(Path(output_dir).resolve())
            return True
        except (OSError, ValueError):
            return False
    return False


def task_for_path(file_path: str) -> tuple[str | None, dict | None]:
    if not file_path:
        return None, None
    path = Path(file_path)
    for task_id, task in tasks.items():
        if _path_belongs_to_task(path, task):
            return task_id, task
    return None, None


def log_operation(
    action: str,
    *,
    task_id: str | None = None,
    target_name: str | None = None,
    success: bool = True,
    message: str | None = None,
):
    user = current_user_context()
    try:
        task_store.add_operation_log({
            'actor': user['username'],
            'role': user['role'],
            'action': action,
            'task_id': task_id,
            'target_name': target_name,
            'success': success,
            'message': message,
            'ip_address': request.headers.get('X-Forwarded-For', request.remote_addr),
            'user_agent': request.headers.get('User-Agent', '')[:300],
            'created_at': time.time(),
        })
    except Exception as exc:
        logger.warning(f'写入操作日志失败 action={action}, task={task_id}: {exc}')


def task_summary(task_id: str, task: dict, queue_positions: dict[str, int]) -> dict:
    return {
        'task_id': task_id,
        'status': task.get('status', 'unknown'),
        'original_name': task.get('original_name', ''),
        'file_path': task.get('file_path', ''),
        'stage': task.get('stage'),
        'percentage': task.get('percentage', 0),
        'stage_percentage': task.get('stage_percentage', 0),
        'message': task.get('message', ''),
        'video_path': task.get('video_path'),
        'course_json_path': task.get('course_json_path'),
        'presentation_path': task.get('presentation_path'),
        'subtitles_path': task.get('subtitles_path'),
        'preview_path': task.get('preview_path'),
        'video_segments': task.get('video_segments', []),
        'error': task.get('error'),
        'batch_id': task.get('batch_id'),
        'strategy_source': task.get('strategy_source', 'batch'),
        'strategy': task.get('strategy', {}),
        'queue_position': queue_positions.get(task_id),
        'owner_username': _task_owner(task),
        'created_by': task.get('created_by') or _task_owner(task),
        'created_at': task.get('created_at'),
        'started_at': task.get('started_at'),
        'stage_started_at': task.get('stage_started_at'),
        'stage_timings': task.get('stage_timings', {}),
        'updated_at': task.get('updated_at'),
        'completed_at': task.get('completed_at'),
    }


class ConversionQueue:
    """串行转换队列，保证同一时刻只运行一个转换任务"""

    def __init__(self):
        self._queue = Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def enqueue(self, func, *args, **kwargs):
        task_id = args[0] if args else None
        queue_run_id = None
        if task_id and task_id in tasks:
            queue_run_id = uuid.uuid4().hex
            tasks[task_id]['queue_run_id'] = queue_run_id
        self._queue.put((func, args, kwargs, queue_run_id))

    def _should_skip(self, task_id, queue_run_id=None):
        task = tasks.get(task_id)
        if not task:
            return True
        if queue_run_id and task.get('queue_run_id') != queue_run_id:
            return True
        if task.get('stop_requested'):
            return True
        cancel_event = cancellation_events.get(task_id)
        if cancel_event and cancel_event.is_set():
            return True
        return task.get('status') not in {'queued', 'pending', 'processing'}

    def _wait_for_capacity(self, task_id, queue_run_id=None):
        while True:
            if self._should_skip(task_id, queue_run_id):
                return False
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=0.3)
                memory = psutil.virtual_memory().percent
                disk_free_gb = psutil.disk_usage(OUTPUT_FOLDER).free / (1024 ** 3)
            except ImportError:
                return True
            if (
                cpu < RESOURCE_CPU_LIMIT
                and memory < RESOURCE_MEMORY_LIMIT
                and disk_free_gb >= RESOURCE_MIN_DISK_GB
            ):
                return True
            task = tasks.get(task_id)
            if task:
                task.update(
                    status='queued',
                    stage='queue',
                    message=(
                        f'资源未满足，等待执行（CPU {cpu:.0f}% / '
                        f'内存 {memory:.0f}% / 磁盘剩余 {disk_free_gb:.1f}GB，'
                        f'最低需要 {RESOURCE_MIN_DISK_GB:.1f}GB）'
                    ),
                )
                save_state(task_id)
            time.sleep(RESOURCE_CHECK_INTERVAL)

    def _run(self):
        while True:
            func, args, kwargs, queue_run_id = self._queue.get()
            try:
                task_id = args[0] if args else None
                if task_id:
                    if self._should_skip(task_id, queue_run_id):
                        continue
                    if not self._wait_for_capacity(task_id, queue_run_id):
                        continue
                    if self._should_skip(task_id, queue_run_id):
                        continue
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


def _synthesize_script_preview(
    engine_name: str,
    voice: str,
    text: str,
    output_path: Path,
    rate: str = '+0%',
    tts_options: dict | None = None,
):
    """使用当前 TTS 配置生成真实讲稿片段试听。"""
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
        text, output_path, voice, rate, **(tts_options or {})
    ))


def _volcengine_tts_options(data: dict, voice: str) -> tuple[str, dict]:
    """校验并生成火山 TTS 的表现力参数。"""
    rate = str(data.get('tts_rate', '-8%')).strip()
    if rate not in {'-15%', '-8%', '+0%', '+10%'}:
        raise ValueError('不支持的火山 TTS 语速')
    emotion = str(data.get('tts_emotion', '')).strip().lower()
    if emotion not in {'', 'happy', 'sad', 'angry', 'surprised'}:
        raise ValueError('不支持的火山 TTS 情感')
    emotion_scale = float(data.get('tts_emotion_scale', 3))
    sentence_pause = int(data.get('tts_sentence_pause', 260))
    if not 1 <= emotion_scale <= 5:
        raise ValueError('火山 TTS 情感强度必须在 1 到 5 之间')
    if not 0 <= sentence_pause <= 3000:
        raise ValueError('火山 TTS 句间停顿必须在 0 到 3000 毫秒之间')
    options = {
        'voice_type': voice,
        'emotion_scale': emotion_scale,
        'silence_duration': sentence_pause,
        'volume_ratio': 1.0,
        'pitch_ratio': 1.0,
    }
    if emotion:
        options['emotion'] = emotion
    return rate, options


def _subtitle_options(data: dict) -> dict:
    """校验字幕坐标与样式设置，坐标基于 1920x1080 输出画布。"""
    def number(name, default, min_value, max_value, cast=int):
        raw = data.get(name, default)
        value = cast(raw)
        if value < min_value or value > max_value:
            raise ValueError(f'{name} 必须在 {min_value} 到 {max_value} 之间')
        return value

    x = number('subtitle_x', 96, 0, 1919)
    y = number('subtitle_y', 900, 0, 1079)
    width = number('subtitle_width', 1728, 1, 1920)
    height = number('subtitle_height', 110, 1, 360)
    if x + width > 1920:
        raise ValueError('字幕区域宽度超出视频画布')
    if y + height > 1080:
        raise ValueError('字幕区域高度超出视频画布')
    font_size = number('subtitle_font_size', 46, 12, 120)
    opacity = number(
        'subtitle_background_opacity', 0.55, 0.0, 1.0, float
    )
    outline_width = number('subtitle_outline_width', 0.0, 0.0, 12.0, float)

    def color(name, default):
        value = str(data.get(name, default)).strip()
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise ValueError(f'{name} 必须是 #RRGGBB 颜色值')
        return value

    font_name = str(data.get('subtitle_font_name', 'Noto Sans CJK SC')).strip()
    return {
        'subtitle_x': x,
        'subtitle_y': y,
        'subtitle_width': width,
        'subtitle_height': height,
        'subtitle_font_size': font_size,
        'subtitle_font_name': font_name[:60] or 'Noto Sans CJK SC',
        'subtitle_color': color('subtitle_color', '#FFFFFF'),
        'subtitle_background_color': color(
            'subtitle_background_color', '#111111'
        ),
        'subtitle_background_opacity': opacity,
        'subtitle_outline_width': outline_width,
        'subtitle_outline_color': color('subtitle_outline_color', '#000000'),
    }


def _subtitle_font_catalog() -> list[str]:
    """读取当前运行环境可用于字幕烧录的字体族，失败时返回内置兜底。"""
    fonts = set(SUBTITLE_FONT_FALLBACKS)
    fc_list = shutil.which('fc-list')
    if not fc_list:
        return SUBTITLE_FONT_FALLBACKS.copy()
    try:
        result = subprocess.run(
            [fc_list, ':lang=zh', 'family'],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception as exc:
        logger.warning(f"读取字幕字体目录失败，使用内置目录: {exc}")
        return SUBTITLE_FONT_FALLBACKS.copy()

    for line in result.stdout.splitlines():
        for family in line.split(','):
            name = family.strip()
            if name and name not in PROPRIETARY_SUBTITLE_FONTS:
                fonts.add(name[:80])

    priority = {name: index for index, name in enumerate(SUBTITLE_FONT_FALLBACKS)}
    return sorted(
        fonts,
        key=lambda name: (
            priority.get(name, len(priority)),
            0 if any(token in name for token in ('CJK', 'Han', 'WenQuanYi')) else 1,
            name.lower(),
        ),
    )


@lru_cache(maxsize=128)
def _subtitle_font_file(font_name: str) -> str | None:
    """通过 fontconfig 字体目录匹配字体族对应的字体文件。"""
    name = (font_name or SUBTITLE_FONT_FALLBACKS[0]).strip()[:80]
    aliases = {
        'Source Han Sans SC': 'Noto Sans CJK SC',
        'Source Han Sans CN': 'Noto Sans CJK SC',
        'Source Han Serif SC': 'Noto Serif CJK SC',
        'Source Han Serif CN': 'Noto Serif CJK SC',
    }
    lookup_name = aliases.get(name, name)
    fc_list = shutil.which('fc-list')
    if fc_list:
        try:
            result = subprocess.run(
                [fc_list, ':lang=zh', 'file', 'family'],
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            )
            exact: dict[str, str] = {}
            regular: dict[str, str] = {}
            for line in result.stdout.splitlines():
                if ': ' not in line:
                    continue
                path, families = line.split(': ', 1)
                if not Path(path).is_file():
                    continue
                for family in families.split(','):
                    family_name = family.strip()
                    if not family_name:
                        continue
                    exact.setdefault(family_name, path)
                    if 'Bold' not in Path(path).name:
                        regular[family_name] = path
            path = regular.get(lookup_name) or exact.get(lookup_name)
            if path:
                return path
        except Exception as exc:
            logger.warning(f"读取字幕字体文件目录失败，回退 fc-match: {exc}")

    fc_match = shutil.which('fc-match')
    if not fc_match:
        return None
    try:
        result = subprocess.run(
            [fc_match, '--format=%{file}', lookup_name],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception as exc:
        logger.warning(f"匹配字幕字体失败 {lookup_name}: {exc}")
        return None
    path = result.stdout.strip()
    return path if path and Path(path).is_file() else None


def _parse_hex_color(value: str, default: str) -> tuple[int, int, int, int]:
    color = (value or default).strip()
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        color = default
    return (
        int(color[1:3], 16),
        int(color[3:5], 16),
        int(color[5:7], 16),
        255,
    )


def _subtitle_preview_lines(draw, text: str, font, max_width: int) -> list[str]:
    chars = list((text or '').strip()[:80])
    if not chars:
        return ['本页暂无字幕文本']
    lines: list[str] = []
    current = ''
    for char in chars:
        candidate = current + char
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if current and bbox[2] - bbox[0] > max_width:
            lines.append(current)
            current = char
            if len(lines) == 2:
                break
        else:
            current = candidate
    if current and len(lines) < 2:
        lines.append(current)
    if len(lines) == 2 and len(''.join(lines)) < len(chars):
        lines[-1] = lines[-1].rstrip('，。；、,. ') + '…'
    return lines


def _render_subtitle_preview_image(params) -> BytesIO:
    """使用真实字幕字体渲染透明文字层，供 PPT 预览叠加。"""
    from PIL import Image, ImageDraw, ImageFont

    width = max(120, min(1920, int(params.get('width', 1728) or 1728)))
    height = max(32, min(360, int(params.get('height', 110) or 110)))
    font_size = max(12, min(120, int(params.get('font_size', 46) or 46)))
    outline_width = max(0, min(12, float(params.get('outline_width', 0) or 0)))
    font_name = str(params.get('font', SUBTITLE_FONT_FALLBACKS[0])).strip()[:80]
    text = str(params.get('text', '')).strip()[:120] or '本页暂无字幕文本'
    text_color = _parse_hex_color(str(params.get('color', '#ffffff')), '#ffffff')
    outline_color = _parse_hex_color(
        str(params.get('outline_color', '#000000')),
        '#000000',
    )

    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    font_path = _subtitle_font_file(font_name)
    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except Exception as exc:
        logger.warning(f"加载字幕预览字体失败 {font_name}: {exc}")
        font = ImageFont.load_default()

    max_text_width = max(24, width - 32)
    lines = _subtitle_preview_lines(draw, text, font, max_text_width)
    line_gap = max(2, int(font_size * 0.14))
    stroke = int(round(outline_width))
    bboxes = [
        draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
        for line in lines
    ]
    line_heights = [bbox[3] - bbox[1] for bbox in bboxes]
    block_height = sum(line_heights) + line_gap * (len(lines) - 1)
    y = max(0, (height - block_height) // 2)
    for line, bbox, line_height in zip(lines, bboxes, line_heights):
        line_width = bbox[2] - bbox[0]
        x = max(0, (width - line_width) // 2 - bbox[0])
        draw.text(
            (x, y - bbox[1]),
            line,
            font=font,
            fill=text_color,
            stroke_width=stroke,
            stroke_fill=outline_color,
        )
        y += line_height + line_gap

    buffer = BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


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
            if preview_path and Path(preview_path).exists():
                entry.update(
                    status='awaiting_confirmation',
                    stage='preview',
                    percentage=50,
                    message='服务重启，已从讲稿检查点恢复，可继续生成',
                    error=None,
                    failed_stage=entry.get('stage'),
                    retryable=True,
                )
                status = 'awaiting_confirmation'
            else:
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
        account = ACCOUNTS.get(username)
        password_ok = bool(account) and secrets.compare_digest(
            password,
            account['password'],
        )
        if password_ok:
            session.clear()
            session['authenticated'] = True
            session['username'] = username
            session['role'] = account['role']
            session['display_name'] = account.get('display_name') or username
            log_operation('login', target_name=username)
            next_url = request.form.get('next', '')
            if next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect(url_for('index'))
        log_operation('login_failed', target_name=username, success=False)
        error = '用户名或密码错误，请重新输入'

    return render_template('login.html', error=error, next_url=request.args.get('next', ''))


@app.route('/logout', methods=['POST'])
def logout():
    """退出当前登录会话。"""
    log_operation('logout')
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
def index():
    """渲染主页面"""
    user = current_user_context()
    return render_template(
        'index.html',
        current_user=user['display_name'],
        current_username=user['username'],
        current_role=user['role'],
        is_super_admin=user['role'] == SUPER_ADMIN_ROLE,
    )


@app.route('/data-management')
def data_management_page():
    """渲染课程数据管理页面。"""
    user = current_user_context()
    return render_template(
        'data_management.html',
        current_user=user['display_name'],
        current_username=user['username'],
        current_role=user['role'],
        is_super_admin=user['role'] == SUPER_ADMIN_ROLE,
    )


@app.route('/operation-logs-page')
def operation_logs_page():
    """渲染操作日志页面。"""
    user = current_user_context()
    return render_template(
        'operation_logs.html',
        current_user=user['display_name'],
        current_username=user['username'],
        current_role=user['role'],
        is_super_admin=user['role'] == SUPER_ADMIN_ROLE,
    )


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
    log_operation('upload', target_name=original_filename)

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
        kwargs.setdefault('updated_at', time.time())
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
            stage_percentage=self.current_progress,
            stage_current=current,
            stage_total=total,
            message=message,
        )

        # 推送到队列
        self.queue.put({
            'type': 'progress',
            'stage': stage,
            'current': current,
            'total': total,
            'percentage': overall,
            'stage_percentage': self.current_progress,
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
            stage_percentage=0,
            message=message,
            stage_started_at=self._stage_started_at,
        )

        self.queue.put({
            'type': 'stage',
            'stage': stage,
            'percentage': overall,
            'stage_percentage': 0,
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
        media_options = tasks.get(task_id, {}).get('media_options', {})
        tts_voice = voice
        if tts_engine == 'volcengine':
            tts_options.update(
                media_options.get('tts_options') or {'voice_type': voice}
            )
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
            tts_rate=media_options.get('tts_rate', '+0%'),
            tts_options=tts_options,
            render_engine=render_engine,
            burn_subtitles=media_options.get('burn_subtitles', True),
            **{
                key: value for key, value in media_options.items()
                if key.startswith('subtitle_')
            },
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
    visual_theme: str,
):
    """Word/PDF 教案生成 Course、PPTX、字幕和视频。"""
    queue = progress_queues.get(task_id)
    if not queue:
        return
    progress = WebProgressTracker(task_id, queue)

    try:
        progress.set_stage('extract', '读取教案结构...')
        tts_options = {}
        media_options = tasks.get(task_id, {}).get('media_options', {})
        tts_voice = voice
        if tts_engine == 'volcengine':
            tts_options.update(
                media_options.get('tts_options') or {'voice_type': voice}
            )
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
            tts_rate=media_options.get('tts_rate', '+0%'),
            tts_options=tts_options,
            render_engine=render_engine,
            burn_subtitles=media_options.get('burn_subtitles', True),
            **{
                key: value for key, value in media_options.items()
                if key.startswith('subtitle_')
            },
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
            visual_theme=visual_theme,
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


def _persist_preview(task_id: str, preview: dict) -> None:
    _preview_file(task_id).write_text(
        json.dumps(preview, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def _slide_image_url(image_path: str) -> str:
    """返回带文件版本的预览图片 URL，避免重渲染后浏览器复用旧图。"""
    path = Path(image_path)
    version = path.stat().st_mtime_ns if path.exists() else int(time.time_ns())
    return f"/api/slide-image?path={quote(str(path), safe='')}&v={version}"


def _page_audio_url(task_id: str, page_number: int, audio_path: Path) -> str:
    """返回带文件版本的逐页音频 URL，避免重配音后浏览器复用旧音频。"""
    version = (
        audio_path.stat().st_mtime_ns
        if audio_path.exists() else int(time.time_ns())
    )
    return f"/api/course-preview/{task_id}/audio/{page_number}?v={version}"


def _preview_page(preview: dict, page_number: int) -> dict | None:
    return next(
        (
            page for page in preview.get('pages', [])
            if int(page.get('page_number', 0)) == page_number
        ),
        None,
    )


def _ensure_course_preview_audio(task_id: str, page_number: int) -> Path:
    """为课程准视频预览生成或复用单页完整配音。"""
    task = tasks.get(task_id)
    if not task:
        raise FileNotFoundError("任务不存在")
    output_dir = Path(task['output_dir'])
    audio_path = output_dir / str(page_number) / 'audio.mp3'
    if audio_path.exists() and audio_path.stat().st_size > 0:
        return audio_path

    lock = _preview_audio_locks.setdefault(task_id, threading.Lock())
    with lock:
        if audio_path.exists() and audio_path.stat().st_size > 0:
            return audio_path

        from vidppt.core.models import DocumentContent, PageContent
        from vidppt.utils.progress import ProgressTracker

        preview = _read_preview(task_id)
        page = _preview_page(preview, page_number)
        if not page:
            raise FileNotFoundError("页面不存在")
        script = str(page.get('script', '')).strip()
        if not script:
            raise ValueError("当前页讲稿为空")

        options = task.get('media_options', {})
        config = ProcessConfig(
            input_path=Path(task['file_path']),
            output_dir=output_dir,
            save_intermediate=True,
            skip_existing=True,
            tts_engine=options.get('tts_engine', 'edge-tts'),
            tts_voice=options.get('tts_voice'),
            tts_rate=options.get('tts_rate', '+0%'),
            tts_options=options.get('tts_options', {}),
            render_engine=options.get('render_engine', 'spire'),
            enable_tts=True,
            enable_video=False,
        )
        content = DocumentContent(pages=[
            PageContent(
                page_number=page_number,
                text=script,
                slide_image=Path(page['image_path']),
            )
        ])
        Pipeline(config)._generate_audio(content, ProgressTracker(total_pages=1))
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise RuntimeError(f"第 {page_number} 页配音生成失败")
        return audio_path


def _estimate_page_duration(page: dict) -> float:
    """用已知 duration 或讲稿字数估算页时长，单位秒。"""
    try:
        duration = float(page.get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration > 0:
        return duration
    text = str(page.get('script') or page.get('original_script') or '')
    return max(15.0, len(text.strip()) / 4.0)


def _duration_estimate_payload(preview: dict) -> dict:
    """汇总预览阶段的完整视频和已应用切课时长估算。"""
    pages = sorted(
        preview.get('pages', []),
        key=lambda page: int(page.get('page_number', 0)),
    )
    total_seconds = sum(_estimate_page_duration(page) for page in pages)
    segments = []
    for index, segment in enumerate(preview.get('lesson_segments') or [], 1):
        try:
            start_page = int(segment.get('start_page'))
            end_page = int(segment.get('end_page'))
        except (TypeError, ValueError):
            continue
        segment_pages = [
            page for page in pages
            if start_page <= int(page.get('page_number', 0)) <= end_page
        ]
        if not segment_pages:
            continue
        segments.append(_segment_payload(
            int(segment.get('id') or index),
            str(segment.get('title') or f'第 {index} 课').strip(),
            segment_pages,
        ))
    return {
        'total_seconds': round(total_seconds, 1),
        'total_minutes': round(total_seconds / 60, 1),
        'segments': segments,
    }


def _page_section_key(page: dict) -> str:
    section = str(page.get('section_title') or '').strip()
    if section:
        return section
    title = str(page.get('title') or '').strip()
    return title or f"第 {page.get('page_number', '')} 页"


def _segment_payload(
    segment_id: int,
    title: str,
    pages: list[dict],
) -> dict:
    duration = sum(_estimate_page_duration(page) for page in pages)
    return {
        'id': segment_id,
        'title': title or f'第 {segment_id} 课',
        'start_page': int(pages[0]['page_number']),
        'end_page': int(pages[-1]['page_number']),
        'page_count': len(pages),
        'estimated_seconds': round(duration, 1),
        'estimated_minutes': round(duration / 60, 1),
    }


def _recommend_lesson_segments(
    pages: list[dict],
    target_minutes: int,
    priority: str,
) -> list[dict]:
    if not pages:
        return []
    target_seconds = max(60, int(target_minutes) * 60)
    ordered_pages = sorted(pages, key=lambda page: int(page['page_number']))
    segments = []

    if priority == 'section':
        current_key = _page_section_key(ordered_pages[0])
        current_pages = []
        for page in ordered_pages:
            page_key = _page_section_key(page)
            current_duration = sum(_estimate_page_duration(item) for item in current_pages)
            should_split = (
                current_pages
                and page_key != current_key
                and current_duration >= target_seconds * 0.55
            )
            if should_split:
                segments.append(_segment_payload(len(segments) + 1, current_key, current_pages))
                current_pages = []
                current_key = page_key
            current_pages.append(page)
        if current_pages:
            segments.append(_segment_payload(len(segments) + 1, current_key, current_pages))
        return segments

    current_pages = []
    for page in ordered_pages:
        current_pages.append(page)
        current_duration = sum(_estimate_page_duration(item) for item in current_pages)
        if current_duration >= target_seconds:
            title = _page_section_key(current_pages[0])
            segments.append(_segment_payload(len(segments) + 1, title, current_pages))
            current_pages = []
    if current_pages:
        title = _page_section_key(current_pages[0])
        segments.append(_segment_payload(len(segments) + 1, title, current_pages))
    return segments


def _normalize_lesson_segments(raw_segments: list[dict], pages: list[dict]) -> list[dict]:
    page_numbers = [int(page['page_number']) for page in pages]
    if not page_numbers:
        raise ValueError("没有可切分页面")
    min_page, max_page = min(page_numbers), max(page_numbers)
    covered = set()
    normalized = []
    for index, item in enumerate(raw_segments, 1):
        try:
            start_page = int(item.get('start_page'))
            end_page = int(item.get('end_page'))
        except (TypeError, ValueError):
            raise ValueError("推荐范围页码必须是整数") from None
        if start_page > end_page:
            raise ValueError("推荐范围起始页不能大于结束页")
        if start_page < min_page or end_page > max_page:
            raise ValueError("推荐范围超出当前页面")
        pages_in_segment = {
            page_number for page_number in page_numbers
            if start_page <= page_number <= end_page
        }
        if not pages_in_segment:
            raise ValueError("推荐范围没有包含有效页面")
        if covered & pages_in_segment:
            raise ValueError("推荐范围不能重叠")
        covered.update(pages_in_segment)
        normalized.append(_segment_payload(
            index,
            str(item.get('title') or f'第 {index} 课').strip()[:80],
            sorted(
                (
                    page for page in pages
                    if start_page <= int(page['page_number']) <= end_page
                ),
                key=lambda page: int(page['page_number']),
            ),
        ))
    if covered != set(page_numbers):
        raise ValueError("推荐范围必须覆盖全部页面且不能遗漏")
    return normalized


def _apply_lesson_segments_to_course(preview: dict, segments: list[dict]) -> None:
    course_json_path = preview.get('course_json_path')
    if not course_json_path:
        return
    course_path = Path(course_json_path)
    if not course_path.exists():
        return
    course = Course.from_dict(json.loads(course_path.read_text(encoding='utf-8')))
    for section_index, section in enumerate(course.sections, 1):
        page_number = section_index
        segment = next(
            (
                item for item in segments
                if item['start_page'] <= page_number <= item['end_page']
            ),
            None,
        )
        if segment:
            section.metadata['lesson_segment'] = segment
    course.metadata['lesson_segments'] = segments
    course_path.write_text(
        json.dumps(course.to_dict(), ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def _update_preview_scripts(task_id: str, updates: list[dict]) -> dict:
    preview = _read_preview(task_id)
    changed_pages = set()
    by_page = {
        int(item['page_number']): str(item.get('script', '')).strip()
        for item in updates
        if 'page_number' in item
    }
    reviewed_by_page = {
        int(item['page_number']): bool(item.get('reviewed'))
        for item in updates
        if 'page_number' in item and 'reviewed' in item
    }
    for page in preview.get('pages', []):
        page_number = int(page['page_number'])
        if page_number in by_page:
            if page.get('script', '').strip() != by_page[page_number]:
                changed_pages.add(page_number)
            page['script'] = by_page[page_number]
        if page_number in reviewed_by_page:
            page['reviewed'] = reviewed_by_page[page_number]
    if not any(page.get('script', '').strip() for page in preview.get('pages', [])):
        raise ValueError("至少需要保留一页非空讲稿")
    _persist_preview(task_id, preview)

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


def _remove_media_artifacts(task: dict, retry_stage: str, page_number: int | None):
    """按重试阶段清理最小必要产物，其余检查点继续复用。"""
    output_dir = Path(task['output_dir'])
    if retry_stage == 'page_tts':
        if not page_number or page_number < 1:
            raise ValueError("page_number 必须为正整数")
        (output_dir / str(page_number) / 'audio.mp3').unlink(missing_ok=True)
    elif retry_stage == 'tts':
        for audio_path in output_dir.glob('*/audio.mp3'):
            audio_path.unlink(missing_ok=True)
    elif retry_stage not in {'media', 'video'}:
        raise ValueError("不支持的重试阶段")

    for artifact in output_dir.glob('*.mp4'):
        artifact.unlink(missing_ok=True)
    for artifact in output_dir.glob('*.srt'):
        artifact.unlink(missing_ok=True)


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
            tts_rate=options.get('tts_rate', '+0%'),
            tts_options=options.get('tts_options', {}),
            render_engine=options.get('render_engine', 'spire'),
            burn_subtitles=options.get('burn_subtitles', True),
            **{
                key: value for key, value in options.items()
                if key.startswith('subtitle_')
            },
            enable_tts=True,
            enable_video=True,
        )
        content = DocumentContent(pages=[
            PageContent(
                page_number=int(page['page_number']),
                text=page.get('script', ''),
                slide_image=Path(page['image_path']),
                metadata={
                    'lesson_segment': page.get('lesson_segment'),
                } if page.get('lesson_segment') else {},
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
        progress.set_stage(
            'video',
            '合成视频并烧录字幕...'
            if config.burn_subtitles else '合成无内嵌字幕视频...'
        )
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
        if config.burn_subtitles:
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
        else:
            base_video.replace(video_path)
        progress.update('video', 100, 100, '视频生成完成')
        lesson_segments = [
            segment for segment in preview.get('lesson_segments', [])
            if isinstance(segment, dict)
        ]
        segment_artifacts = []
        if lesson_segments:
            progress.set_stage('video', '按智能切课范围生成分段视频...')
            pages_by_number = {page.page_number: page for page in content.pages}
            timed_by_number = {
                int(page.page_number): (course_page, duration)
                for page, (course_page, duration) in zip(content.pages, timed_pages)
            }
            segment_dir = config.output_dir / 'segments'
            segment_dir.mkdir(exist_ok=True)
            for index, segment in enumerate(lesson_segments, 1):
                if cancel_event.is_set():
                    raise InterruptedError("用户停止了生成")
                start_page = int(segment['start_page'])
                end_page = int(segment['end_page'])
                segment_pages = [
                    pages_by_number[number]
                    for number in sorted(pages_by_number)
                    if start_page <= number <= end_page
                ]
                segment_timed_pages = [
                    timed_by_number[number]
                    for number in sorted(timed_by_number)
                    if start_page <= number <= end_page
                ]
                if not segment_pages or not segment_timed_pages:
                    continue
                segment_content = DocumentContent(
                    pages=segment_pages,
                    metadata={
                        **content.metadata,
                        'lesson_segment': segment,
                    },
                )
                segment_stem = f"{index:02d}_pages_{start_page}_{end_page}"
                segment_subtitles = SubtitleRenderer().render_course(
                    segment_timed_pages, segment_dir / f'{segment_stem}.srt'
                )
                segment_base = segment_dir / f'{segment_stem}.base.mp4'
                segment_video = segment_dir / f'{segment_stem}.mp4'
                segment_last_reported = -1

                def report_segment(fraction: float):
                    nonlocal segment_last_reported
                    stage_percentage = round(
                        ((index - 1) + max(0.0, min(1.0, fraction))) / len(lesson_segments) * 100
                    )
                    if stage_percentage > segment_last_reported:
                        segment_last_reported = stage_percentage
                        progress.update(
                            'video',
                            stage_percentage,
                            100,
                            f'正在生成第 {index}/{len(lesson_segments)} 段视频',
                        )

                VideoComposer.compose(
                    segment_content,
                    config,
                    segment_base,
                    progress_callback=report_segment,
                    cancel_check=cancel_event.is_set,
                )
                if config.burn_subtitles:
                    CoursePipeline._burn_subtitles(
                        segment_base,
                        segment_subtitles,
                        segment_video,
                        config,
                        progress_callback=report_segment,
                        cancel_check=cancel_event.is_set,
                    )
                    segment_base.unlink(missing_ok=True)
                else:
                    segment_base.replace(segment_video)
                segment_artifacts.append({
                    **segment,
                    'video_path': str(segment_video),
                    'subtitles_path': str(segment_subtitles),
                })
            progress.update('video', 100, 100, '分段视频生成完成')
        progress.complete(
            str(video_path),
            course_json_path=preview.get('course_json_path'),
            presentation_path=preview.get('presentation_path'),
            subtitles_path=str(subtitles),
            video_segments=segment_artifacts,
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
    tts_rate = '+0%'
    vendor_tts_options = None
    if tts_engine == 'volcengine':
        try:
            tts_rate, vendor_tts_options = _volcengine_tts_options(data, voice)
        except (TypeError, ValueError) as exc:
            return jsonify({'error': str(exc)}), 400
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
    visual_theme = str(data.get('visual_theme', 'auto')).strip().lower()
    burn_subtitles = bool(data.get('burn_subtitles', True))
    try:
        subtitle_options = _subtitle_options(data)
    except (TypeError, ValueError) as exc:
        return jsonify({'error': str(exc)}), 400
    batch_id = str(data.get('batch_id') or uuid.uuid4().hex)
    strategy_source = data.get('strategy_source', 'batch')
    if refinement_level not in {'light', 'standard', 'strong'}:
        return jsonify({'error': '不支持的精炼程度'}), 400
    if max_illustrations not in {1, 2, 3, 4}:
        return jsonify({'error': '插图数量必须为 1 到 4'}), 400
    allowed_visual_themes = {
        'auto', 'industry', 'technology', 'culture', 'nature',
        'education', 'business', 'health', 'public', 'finance',
    }
    if visual_theme not in allowed_visual_themes:
        return jsonify({'error': '不支持的 PPT 视觉方案'}), 400
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
        'tts_rate': tts_rate,
        'tts_options': vendor_tts_options or {},
        'render_engine': render_engine,
        'llm_enabled': llm_enabled,
        'llm_engine': llm_engine,
        'llm_mode': llm_mode,
        'refinement_level': refinement_level,
        'illustrations_enabled': illustrations_enabled,
        'max_illustrations': max_illustrations,
        'ppt_footer_text': ppt_footer_text,
        'school_logo_path': school_logo_path,
        'visual_theme': visual_theme,
        'burn_subtitles': burn_subtitles,
        **subtitle_options,
    }
    user = current_user_context()
    now = time.time()
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
        'owner_username': user['username'],
        'created_by': user['username'],
        'created_at': now,
        'updated_at': now,
        'strategy': strategy,
        'media_options': {
            'tts_engine': tts_engine,
            'tts_voice': None if tts_engine in {'volcengine', 'minimax'} else voice,
            'tts_options': (
                vendor_tts_options if tts_engine == 'volcengine'
                else {'voice_id': voice} if tts_engine == 'minimax'
                else {}
            ),
            'tts_rate': tts_rate,
            'render_engine': render_engine,
            'burn_subtitles': burn_subtitles,
            **subtitle_options,
        },
    }
    save_state(task_id)
    log_operation('create_task', task_id=task_id, target_name=original_name)

    suffix = Path(file_path).suffix.lower()
    if suffix in {'.docx', '.pdf'}:
        conversion_queue.enqueue(
            run_course_generation, task_id, file_path, output_dir,
            tts_engine, voice, render_engine, llm_enabled, llm_engine,
            refinement_level, illustrations_enabled, max_illustrations,
            ppt_footer_text, school_logo_path, visual_theme
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
    task, error = require_task_access(task_id)
    if error:
        return error
    if task.get('status') != 'awaiting_confirmation':
        return jsonify({'error': '任务尚未进入讲稿确认阶段'}), 409
    try:
        preview = _read_preview(task_id)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return jsonify({'error': str(exc)}), 404
    preview['pages'] = [
        {
            **page,
            'image_url': _slide_image_url(page['image_path']),
            'estimated_seconds': round(_estimate_page_duration(page), 1),
        }
        for page in preview.get('pages', [])
    ]
    duration_estimate = _duration_estimate_payload(preview)
    preview['duration_estimate'] = duration_estimate
    preview['lesson_segments'] = duration_estimate['segments']
    log_operation('preview_task', task_id=task_id, target_name=task.get('original_name'))
    return jsonify(preview)


@app.route('/api/course-preview/<task_id>/page-audio', methods=['POST'])
def ensure_course_preview_audio(task_id):
    """按需生成或复用单页完整配音，供浏览器端准视频预览播放。"""
    task, error = require_task_access(task_id)
    if error:
        return error
    if task.get('status') not in {
        'awaiting_confirmation',
        'processing',
        'completed',
    }:
        return jsonify({'error': '当前任务阶段暂不支持预览音频'}), 409
    data = request.get_json(silent=True) or {}
    try:
        page_number = int(data.get('page_number', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'page_number 必须为正整数'}), 400
    if page_number < 1:
        return jsonify({'error': 'page_number 必须为正整数'}), 400

    script = str(data.get('script', '')).strip()
    try:
        if script and task.get('status') == 'awaiting_confirmation':
            _update_preview_scripts(task_id, [{
                'page_number': page_number,
                'script': script,
            }])
        audio_path = Path(task['output_dir']) / str(page_number) / 'audio.mp3'
        if task.get('status') == 'processing':
            if not audio_path.exists() or audio_path.stat().st_size == 0:
                return jsonify({'error': '当前页配音尚未生成，请稍后再预览'}), 409
        else:
            audio_path = _ensure_course_preview_audio(task_id, page_number)
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        logger.exception(f'生成课程预览音频失败: task={task_id}, page={page_number}')
        return jsonify({'error': f'预览音频生成失败: {exc}'}), 502

    return jsonify({
        'success': True,
        'page_number': page_number,
        'audio_url': _page_audio_url(task_id, page_number, audio_path),
    })


@app.route('/api/course-preview/<task_id>/audio/<int:page_number>')
def get_course_preview_audio(task_id, page_number):
    """播放课程准视频预览用的单页音频。"""
    task, error = require_task_access(task_id)
    if error:
        return error
    audio_path = Path(task['output_dir']) / str(page_number) / 'audio.mp3'
    if not audio_path.exists() or audio_path.stat().st_size == 0:
        return jsonify({'error': '音频不存在'}), 404
    return send_file(audio_path, mimetype='audio/mpeg')


@app.route('/api/course-segments/<task_id>/recommend', methods=['POST'])
def recommend_course_segments(task_id):
    """根据目标时长和优先级给出智能切课范围。"""
    task, error = require_task_access(task_id)
    if error:
        return error
    if task.get('status') != 'awaiting_confirmation':
        return jsonify({'error': '任务尚未进入讲稿确认阶段'}), 409
    data = request.get_json(silent=True) or {}
    try:
        target_minutes = int(data.get('target_minutes', 5))
    except (TypeError, ValueError):
        return jsonify({'error': '分割时长必须是整数分钟'}), 400
    priority = data.get('priority', 'section')
    if target_minutes < 1 or target_minutes > 120:
        return jsonify({'error': '分割时长必须在 1 到 120 分钟之间'}), 400
    if priority not in {'section', 'duration'}:
        return jsonify({'error': '不支持的切课优先级'}), 400
    try:
        preview = _read_preview(task_id)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return jsonify({'error': str(exc)}), 404
    segments = _recommend_lesson_segments(
        preview.get('pages', []),
        target_minutes,
        priority,
    )
    return jsonify({
        'success': True,
        'target_minutes': target_minutes,
        'priority': priority,
        'segments': segments,
        'total_estimated_minutes': round(
            sum(segment['estimated_seconds'] for segment in segments) / 60,
            1,
        ),
    })


@app.route('/api/course-segments/<task_id>', methods=['POST'])
def apply_course_segments(task_id):
    """把用户确认的切课范围写入预览数据和 course.json。"""
    task, error = require_task_access(task_id)
    if error:
        return error
    if task.get('status') != 'awaiting_confirmation':
        return jsonify({'error': '当前任务不能应用切课'}), 409
    data = request.get_json(silent=True) or {}
    raw_segments = data.get('segments')
    if not isinstance(raw_segments, list) or not raw_segments:
        return jsonify({'error': 'segments 必须是非空数组'}), 400
    try:
        preview = _read_preview(task_id)
        segments = _normalize_lesson_segments(
            raw_segments,
            preview.get('pages', []),
        )
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        return jsonify({'error': str(exc)}), 400

    segment_by_page = {}
    for segment in segments:
        for page_number in range(segment['start_page'], segment['end_page'] + 1):
            segment_by_page[page_number] = segment
    for page in preview.get('pages', []):
        page_number = int(page['page_number'])
        if page_number in segment_by_page:
            page['lesson_segment'] = segment_by_page[page_number]
    preview['lesson_segments'] = segments
    _persist_preview(task_id, preview)
    _apply_lesson_segments_to_course(preview, segments)

    task['lesson_segments'] = segments
    task['message'] = f'已应用智能切课，共 {len(segments)} 段'
    save_state(task_id)
    log_operation('apply_segments', task_id=task_id, target_name=task.get('original_name'))
    return jsonify({
        'success': True,
        'message': f'已应用智能切课，共 {len(segments)} 段',
        'segments': segments,
    })


@app.route('/api/course-presentation/<task_id>', methods=['GET', 'POST'])
def course_presentation(task_id):
    """下载可编辑 PPTX，或接收用户修改后的版本并刷新审核预览。"""
    task, error = require_task_access(task_id)
    if error:
        return error
    if task.get('status') != 'awaiting_confirmation':
        return jsonify({'error': '任务尚未进入 PPT 审核阶段'}), 409
    try:
        preview = _read_preview(task_id)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return jsonify({'error': str(exc)}), 404

    presentation_path = preview.get('presentation_path') or task.get('file_path')
    if request.method == 'GET':
        if not presentation_path:
            return jsonify({'error': '当前任务没有可编辑 PPT'}), 404
        presentation = Path(presentation_path)
        if not presentation.is_file() or presentation.suffix.lower() not in {'.ppt', '.pptx'}:
            return jsonify({'error': '可编辑 PPT 文件不存在'}), 404
        return send_file(
            presentation,
            as_attachment=True,
            download_name=_artifact_download_name(task, str(presentation)),
        )

    upload = request.files.get('presentation')
    if not upload or not upload.filename:
        return jsonify({'error': '请选择修改后的 PPTX 文件'}), 400
    if Path(upload.filename).suffix.lower() != '.pptx':
        return jsonify({'error': '仅支持上传 PPTX 文件'}), 400

    output_dir = Path(task['output_dir'])
    reviewed_path = output_dir / 'reviewed.pptx'
    temporary_path = output_dir / f'.reviewed-{uuid.uuid4().hex}.pptx'
    try:
        upload.save(temporary_path)
        temporary_path.replace(reviewed_path)

        from vidppt.processors.ppt_processor import PPTProcessor
        content = PPTProcessor().process(ProcessConfig(
            input_path=reviewed_path,
            output_dir=output_dir,
            save_intermediate=True,
            skip_existing=False,
            render_engine=task.get('media_options', {}).get('render_engine', 'spire'),
        ))
        old_pages = {
            int(page['page_number']): page
            for page in preview.get('pages', [])
        }
        refreshed_pages = []
        for page in content.pages:
            previous = old_pages.get(page.page_number, {})
            script = previous.get('script', page.text)
            refreshed_pages.append({
                'page_number': page.page_number,
                'title': _page_title(page.text, page.page_number),
                'image_path': str(page.slide_image),
                'script': script,
                'original_script': previous.get('original_script', page.text),
                'reviewed': False,
            })
        if not refreshed_pages:
            raise ValueError('上传的 PPTX 不包含可渲染页面')

        preview['presentation_path'] = str(reviewed_path)
        preview['pages'] = refreshed_pages
        _preview_file(task_id).write_text(
            json.dumps(preview, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        task['presentation_path'] = str(reviewed_path)
        task['message'] = 'PPT 已更新，请确认预览和讲稿'
        save_state(task_id)
        log_operation('upload_reviewed_ppt', task_id=task_id, target_name=task.get('original_name'))
        return jsonify({
            'success': True,
            'message': 'PPT 已更新并重新渲染',
            'pages': [
                {
                    **page,
                    'image_url': _slide_image_url(page['image_path']),
                }
                for page in refreshed_pages
            ],
        })
    except Exception as exc:
        logger.exception("更新审核 PPT 失败")
        return jsonify({'error': f'PPT 更新失败: {exc}'}), 400
    finally:
        temporary_path.unlink(missing_ok=True)


@app.route('/api/course-preview/<task_id>', methods=['PATCH'])
def save_course_preview(task_id):
    """持久化用户修改的逐页讲稿，但不启动媒体生成。"""
    task, error = require_task_access(task_id)
    if error:
        return error
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
    log_operation('save_preview', task_id=task_id, target_name=task.get('original_name'))
    preview = _read_preview(task_id)
    duration_estimate = _duration_estimate_payload(preview)
    return jsonify({
        'success': True,
        'message': '讲稿已保存',
        'duration_estimate': duration_estimate,
        'lesson_segments': duration_estimate['segments'],
    })


@app.route('/api/course-continue/<task_id>', methods=['POST'])
def continue_course(task_id):
    """确认最终讲稿，并将 TTS/字幕/视频阶段重新加入转换队列。"""
    task, error = require_task_access(task_id)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    pages = data.get('pages')
    tts_engine = data.get('tts_engine')
    voice = data.get('voice')
    burn_subtitles = bool(data.get('burn_subtitles', True))
    try:
        subtitle_options = _subtitle_options(data)
    except (TypeError, ValueError) as exc:
        return jsonify({'error': str(exc)}), 400

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
            tts_rate = '+0%'
            volcengine_options = None
            if tts_engine == 'volcengine':
                try:
                    tts_rate, volcengine_options = _volcengine_tts_options(
                        data, voice
                    )
                except (TypeError, ValueError) as exc:
                    return jsonify({'error': str(exc)}), 400
            task['media_options'] = {
                **task.get('media_options', {}),
                'tts_engine': tts_engine,
                'tts_voice': None if tts_engine in {'volcengine', 'minimax'} else voice,
                'tts_options': (
                    volcengine_options if tts_engine == 'volcengine'
                    else {'voice_id': voice} if tts_engine == 'minimax'
                    else {}
                ),
                'tts_rate': tts_rate,
                'burn_subtitles': burn_subtitles,
                **subtitle_options,
            }

        progress_queues[task_id] = Queue()
        cancellation_events[task_id] = threading.Event()
        task.update(
            status='pending',
            stage='tts',
            percentage=50,
            message='已确认讲稿，等待生成配音',
            stop_requested=False,
            error=None,
        )
        save_state(task_id)
        conversion_queue.enqueue(run_media_generation, task_id)
    log_operation('continue_task', task_id=task_id, target_name=task.get('original_name'))

    return jsonify({'success': True, 'message': '已继续生成视频'})


@app.route('/api/stop/<task_id>', methods=['POST'])
def stop_task(task_id):
    """请求停止当前媒体生成；工作线程会清理并回退到讲稿确认。"""
    task, error = require_task_access(task_id)
    if error:
        return error
    status = task.get('status')
    if status not in {'queued', 'pending', 'processing'}:
        return jsonify({'error': '当前任务不在运行中'}), 409
    cancel_event = cancellation_events.setdefault(task_id, threading.Event())
    cancel_event.set()
    task.update(message='正在停止生成，请稍候…', stop_requested=True)
    if status in {'queued', 'pending'}:
        preview_path = task.get('preview_path')
        if preview_path and Path(preview_path).exists():
            task.update(
                status='awaiting_confirmation',
                stage='preview',
                percentage=50,
                stage_percentage=0,
                message='生成已停止，已退回讲稿确认，可直接重试',
                error='用户停止了生成',
                failed_stage=task.get('stage', 'queue'),
                retryable=True,
                stop_requested=False,
            )
            event_type = 'rollback'
        else:
            task.update(
                status='interrupted',
                stage='queue',
                percentage=0,
                stage_percentage=0,
                message='任务已从队列移除，可重新提交',
                error='用户停止了排队任务',
                retryable=True,
                stop_requested=False,
            )
            event_type = 'error'
    save_state(task_id)
    queue = progress_queues.get(task_id)
    if queue:
        if status in {'queued', 'pending'}:
            if event_type == 'rollback':
                queue.put({
                    'type': 'rollback',
                    'message': '用户停止了生成',
                    'failed_stage': '生成已停止',
                    'preview_path': task.get('preview_path'),
                    'course_json_path': task.get('course_json_path'),
                    'presentation_path': task.get('presentation_path'),
                })
            else:
                queue.put({
                    'type': 'error',
                    'message': '任务已从队列移除，可重新提交',
                })
        else:
            queue.put({
                'type': 'progress',
                'stage': task.get('stage', 'video'),
                'current': task.get('percentage', 0),
                'total': 100,
                'percentage': task.get('percentage', 0),
                'stage_percentage': task.get('stage_percentage', 0),
                'message': '正在停止生成，请稍候…',
            })
    log_operation('stop_task', task_id=task_id, target_name=task.get('original_name'))
    return jsonify({'success': True, 'message': '已请求停止，正在回退上一步'})


@app.route('/api/tasks/<task_id>/retry', methods=['POST'])
def retry_task_stage(task_id):
    """从讲稿检查点重新执行指定媒体阶段，并尽量复用已有成果。"""
    task, error = require_task_access(task_id)
    if error:
        return error
    if task.get('status') not in {
        'awaiting_confirmation', 'completed', 'error', 'interrupted'
    }:
        return jsonify({'error': '任务仍在运行或排队，不能重复提交'}), 409
    try:
        _read_preview(task_id)
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
        return jsonify({'error': f'缺少讲稿检查点，无法分阶段重试: {exc}'}), 409

    data = request.get_json(silent=True) or {}
    retry_stage = str(data.get('stage', 'media')).strip()
    page_number = data.get('page_number')
    try:
        page_number = int(page_number) if page_number is not None else None
        _remove_media_artifacts(task, retry_stage, page_number)
    except (TypeError, ValueError) as exc:
        return jsonify({'error': str(exc)}), 400

    progress_queues[task_id] = Queue()
    cancellation_events.pop(task_id, None)
    label = {
        'page_tts': f'第 {page_number} 页配音',
        'tts': '全部配音',
        'video': '视频合成',
        'media': '媒体生成',
    }[retry_stage]
    task.update(
        status='queued',
        stage='queue',
        percentage=50,
        message=f'{label}已重新进入队列',
        error=None,
        failed_stage=None,
        retryable=False,
        stop_requested=False,
        retry_stage=retry_stage,
        retry_page=page_number,
    )
    save_state(task_id)
    conversion_queue.enqueue(run_media_generation, task_id)
    log_operation('retry_task', task_id=task_id, target_name=task.get('original_name'))
    return jsonify({
        'success': True,
        'task_id': task_id,
        'stage': retry_stage,
        'message': task['message'],
        'queue_size': conversion_queue.size(),
    })


@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """物理删除未运行任务的输出目录及持久化状态。"""
    task, error = require_task_access(task_id)
    if error:
        return error
    deletable_statuses = {
        'completed',
        'error',
        'interrupted',
        'awaiting_confirmation',
    }
    if task.get('status') not in deletable_statuses:
        return jsonify({'error': '任务仍在运行或排队，请先停止任务再删除'}), 409

    output_root = OUTPUT_FOLDER.resolve()
    output_dir = OUTPUT_FOLDER / task_id
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
    recorded_output = task.get('output_dir')
    if recorded_output:
        try:
            recorded_path = Path(recorded_output).resolve()
        except OSError:
            recorded_path = None
        if recorded_path != resolved_output:
            logger.warning(
                f'Ignoring stale output path for task {task_id}: {recorded_output}'
            )
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
    log_operation('delete_task', task_id=task_id, target_name=task.get('original_name'))
    return jsonify({'success': True, 'message': '课程产物已物理删除'})


@app.route('/api/course-cancel/<task_id>', methods=['POST'])
def cancel_course(task_id):
    """放弃待确认任务，让前端使用原上传文件重新选择生成策略。"""
    task, error = require_task_access(task_id)
    if error:
        return error
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
    log_operation('cancel_task', task_id=task_id, target_name=task.get('original_name'))
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
    user = current_user_context()
    now = time.time()
    tasks[task_id] = {
        'status': 'pending',
        'file_path': file_path,
        'output_dir': str(output_dir),
        'original_name': original_name,
        'owner_username': user['username'],
        'created_by': user['username'],
        'created_at': now,
        'updated_at': now,
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
    task, error = require_task_access(task_id)
    if error:
        return error

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
    _, task = task_for_path(slide_path)
    if not task:
        return jsonify({'error': '图片不存在'}), 404
    if not can_access_task(task):
        return jsonify({'error': '无权访问该图片'}), 403
    try:
        response = make_response(send_file(slide_path, mimetype='image/png'))
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except FileNotFoundError:
        return jsonify({'error': '图片不存在'}), 404


@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    """
    SSE 接口，推送转换进度
    """
    task, error = require_task_access(task_id)
    if error:
        return error
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
    task, error = require_task_access(task_id)
    if error:
        return error

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
        'stage_percentage': task.get('stage_percentage', 0),
        'message': task.get('message', ''),
        'batch_id': task.get('batch_id'),
        'strategy_source': task.get('strategy_source', 'batch'),
        'owner_username': _task_owner(task),
        'queue_position': (
            sum(
                1
                for other in tasks.values()
                if other.get('status') == 'queued'
                and can_access_task(other)
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
    visible_tasks = {
        task_id: task for task_id, task in tasks.items()
        if can_access_task(task)
    }
    queued_ids = [
        task_id
        for task_id, task in sorted(
            visible_tasks.items(),
            key=lambda item: item[1].get('queue_order', float('inf')),
        )
        if task.get('status') == 'queued'
    ]
    queue_positions = {
        task_id: index + 1 for index, task_id in enumerate(queued_ids)
    }
    all_tasks = [
        task_summary(task_id, task, queue_positions)
        for task_id, task in visible_tasks.items()
    ]
    # 按创建时间倒序排列，限制最近 50 条
    all_tasks = sorted(
        all_tasks,
        key=lambda task: task.get('created_at') or 0,
        reverse=True,
    )[:MAX_STATE_ENTRIES]
    return jsonify({
        'tasks': all_tasks,
        'current_user': current_user_context(),
        'is_super_admin': is_super_admin(),
    })


@app.route('/api/operation-logs')
def get_operation_logs():
    """返回当前用户可见的操作日志。"""
    try:
        limit = int(request.args.get('limit', 100))
    except (TypeError, ValueError):
        limit = 100
    actor = None if is_super_admin() else current_user_context()['username']
    try:
        logs = task_store.list_operation_logs(actor=actor, limit=limit)
    except Exception as exc:
        logger.exception(f'读取操作日志失败: {exc}')
        return jsonify({'error': '读取操作日志失败'}), 500
    return jsonify({
        'logs': logs,
        'current_user': current_user_context(),
        'is_super_admin': is_super_admin(),
    })


@app.route('/api/active-task')
def get_active_task():
    """获取当前正在运行或刚完成的任务，供前端刷新后恢复状态"""
    for task_id, task in tasks.items():
        if not can_access_task(task):
            continue
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
    completed = [
        (tid, t) for tid, t in tasks.items()
        if t.get('status') in ('completed', 'error') and can_access_task(t)
    ]
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
    data = [
        entry for entry in _read_state_file()
        if can_access_task(entry)
    ]
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
        if not can_access_task(task):
            continue
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
    completed = [
        (tid, t) for tid, t in tasks.items()
        if t.get('status') in ('completed', 'error') and can_access_task(t)
    ]
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
    _, task = task_for_path(video_path)
    if not task:
        return jsonify({'error': '视频文件不存在'}), 404
    if not can_access_task(task):
        return jsonify({'error': '无权访问该视频'}), 403
    try:
        return send_file(video_path, mimetype='video/mp4')
    except FileNotFoundError:
        return jsonify({'error': '视频文件不存在'}), 404


@app.route('/api/frame')
def get_frame():
    """获取视频第一帧图片用于预览"""
    frame_path = request.args.get('path', '')
    _, task = task_for_path(frame_path)
    if not task:
        return jsonify({'error': '图片文件不存在'}), 404
    if not can_access_task(task):
        return jsonify({'error': '无权访问该图片'}), 403
    try:
        return send_file(frame_path, mimetype='image/png')
    except FileNotFoundError:
        return jsonify({'error': '图片文件不存在'}), 404


def _artifact_download_name(task: dict | None, file_path: str) -> str:
    """使用上传时的原始主文件名，并保留产物自身扩展名。"""
    artifact = Path(file_path)
    original_name = (task or {}).get('original_name', '')
    original_basename = str(original_name).replace('\\', '/').rsplit('/', 1)[-1]
    stem = Path(original_basename).stem.strip() if original_basename else ''
    return f"{stem or artifact.stem or 'course'}{artifact.suffix}"


@app.route('/api/download')
def download_file():
    """下载文件"""
    file_path = request.args.get('path', '')
    task_id = request.args.get('task_id', '')
    task = tasks.get(task_id)
    if not task:
        task_id, task = task_for_path(file_path)
    if not task:
        return jsonify({'error': '文件不存在'}), 404
    if not can_access_task(task):
        return jsonify({'error': '无权下载该文件'}), 403
    try:
        log_operation('download', task_id=task_id or None, target_name=task.get('original_name'))
        return send_file(
            file_path,
            as_attachment=True,
            download_name=_artifact_download_name(task, file_path),
        )
    except FileNotFoundError:
        return jsonify({'error': '文件不存在'}), 404


@app.route('/api/subtitle-fonts')
def list_subtitle_fonts():
    """列出字幕烧录可用字体；优先返回当前容器 fontconfig 可见的中文字体。"""
    fonts = _subtitle_font_catalog()
    return jsonify({
        'fonts': fonts,
        'count': len(fonts),
        'default': SUBTITLE_FONT_FALLBACKS[0],
    })


@app.route('/api/subtitle-preview-image')
def subtitle_preview_image():
    """生成透明字幕文字层，用于 PPT 预览中展示真实字体和描边效果。"""
    response = make_response(send_file(
        _render_subtitle_preview_image(request.args),
        mimetype='image/png',
        max_age=0,
    ))
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


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
            {'id': 'zh_male_yangguangqingnian_emo_v2_mars_bigtts', 'name': '阳光青年（多情感·推荐）', 'gender': 'male'},
            {'id': 'zh_female_roumeinvyou_emo_v2_mars_bigtts', 'name': '柔美女友（多情感·推荐）', 'gender': 'female'},
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


@app.route('/api/script-preview', methods=['POST'])
def preview_script():
    """使用所选音色生成当前页讲稿前 300 字的试听音频。"""
    data = request.get_json(silent=True) or {}
    engine = str(data.get('engine', '')).strip()
    voice = str(data.get('voice', '')).strip()
    text = str(data.get('text', '')).strip()
    if engine not in {'edge-tts', 'volcengine', 'minimax'}:
        return jsonify({'error': '不支持的语音引擎'}), 400
    if not voice or len(voice) > 200:
        return jsonify({'error': '无效的音色 ID'}), 400
    if not text:
        return jsonify({'error': '当前页讲稿为空'}), 400

    sample = text[:300]
    rate = '+0%'
    tts_options = {}
    if engine == 'volcengine':
        try:
            rate, tts_options = _volcengine_tts_options(data, voice)
        except (TypeError, ValueError) as exc:
            return jsonify({'error': str(exc)}), 400
    cache_key = hashlib.sha256(
        (
            f'script:{engine}:{voice}:{sample}:{rate}:'
            f'{json.dumps(tts_options, sort_keys=True)}'
        ).encode()
    ).hexdigest()
    preview_path = VOICE_PREVIEW_FOLDER / f'{cache_key}.mp3'
    try:
        if not preview_path.exists() or preview_path.stat().st_size == 0:
            if engine == 'volcengine':
                _synthesize_script_preview(
                    engine, voice, sample, preview_path, rate, tts_options
                )
            else:
                _synthesize_script_preview(engine, voice, sample, preview_path)
        return send_file(preview_path, mimetype='audio/mpeg')
    except Exception as exc:
        logger.exception(f'生成讲稿试听失败: engine={engine}, voice={voice}')
        preview_path.unlink(missing_ok=True)
        return jsonify({'error': f'讲稿试听生成失败: {exc}'}), 502


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
                strategy.get('visual_theme', 'auto'),
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
