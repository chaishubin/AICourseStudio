"""
Web界面后端API
提供文件上传和PPT转视频的接口
"""

import os
import uuid
import json
import threading
import sys
from pathlib import Path
from queue import Queue
from flask import Flask, render_template, request, jsonify, send_file, make_response, Response
from werkzeug.utils import secure_filename

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

# 确保目录存在
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['OUTPUT_FOLDER'] = str(OUTPUT_FOLDER)

# 存储任务状态和进度队列
tasks = {}  # task_id -> {status, file_path, output_dir, stage, percentage, message, video_path, error}
progress_queues = {}  # task_id -> Queue


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

    if file and allowed_file(file.filename):
        # 生成唯一文件名
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = UPLOAD_FOLDER / unique_filename

        # 保存文件
        file.save(file_path)

        return jsonify({
            'success': True,
            'file_path': str(file_path),
            'original_name': filename
        })

    return jsonify({'error': '不支持的文件类型'}), 400


class WebProgressTracker:
    """Web端进度跟踪器，将进度推送到队列"""

    STAGE_ORDER = ['init', 'extract', 'tts', 'video']
    STAGE_WEIGHT = 100 / len(STAGE_ORDER)  # 每个阶段占 25%

    def __init__(self, task_id: str, queue: Queue, total_pages: int = 0):
        self.task_id = task_id
        self.queue = queue
        self.total_pages = total_pages
        self.current_stage = None
        self.current_progress = 0
        self.stage_progress = {}  # stage_name -> {current, total, percentage}

    def _overall_percentage(self, stage: str, stage_pct: float) -> int:
        """将阶段局部百分比转换为整体百分比"""
        idx = self.STAGE_ORDER.index(stage) if stage in self.STAGE_ORDER else 0
        return int(idx * self.STAGE_WEIGHT + (stage_pct / 100) * self.STAGE_WEIGHT)

    def _update_task(self, **kwargs):
        """更新 tasks 字典中的最新状态"""
        task = tasks.get(self.task_id, {})
        task.update(kwargs)
        tasks[self.task_id] = task

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
        self.current_stage = stage

        self._update_task(
            status='processing',
            stage=stage,
            message=message,
        )

        self.queue.put({
            'type': 'stage',
            'stage': stage,
            'message': message
        })

    def complete(self, video_path: str = None):
        """标记完成"""
        self._update_task(
            status='completed',
            stage='complete',
            percentage=100,
            message='转换完成',
            video_path=video_path,
        )

        self.queue.put({
            'type': 'complete',
            'video_path': video_path,
            'message': '转换完成'
        })

    def error(self, error_msg: str):
        """标记错误"""
        self._update_task(
            status='error',
            error=error_msg,
        )

        self.queue.put({
            'type': 'error',
            'message': error_msg
        })


def run_conversion(task_id: str, file_path: str, output_dir: Path,
                   tts_engine: str = 'edge-tts', voice: str = 'zh-CN-XiaoxiaoNeural'):
    """在后台线程中运行转换"""
    queue = progress_queues.get(task_id)
    if not queue:
        return

    progress = WebProgressTracker(task_id, queue)

    try:
        # 1. 初始化
        progress.set_stage('init', '初始化转换...')

        # 2. 创建配置
        config = ProcessConfig(
            input_path=Path(file_path),
            output_dir=output_dir,
            save_intermediate=False,
            tts_engine=tts_engine,
            tts_voice=voice,
        )

        # 3. 创建 Pipeline
        pipeline = Pipeline(config)

        progress.update('init', 1, 1, '初始化完成')

        # 4. 运行转换（需要修改 pipeline 以支持进度回调）
        # 这里我们用一种简化的方式：监控输出文件变化来估计进度

        progress.set_stage('extract', '提取PPT内容...')

        # 获取处理器
        from vidppt.core.registry import ProcessorRegistry
        processor_class = ProcessorRegistry.get_processor(Path(file_path))
        if not processor_class:
            raise ValueError(f"不支持的文件类型: {Path(file_path).suffix}")

        processor = processor_class()

        # 提取内容
        content = processor.process(config)
        total_pages = content.total_pages
        progress.total_pages = total_pages

        progress.update('extract', total_pages, total_pages, f'提取完成，共 {total_pages} 页')

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
                    audio_path = output_dir / f"temp_audio_{page.page_number}.mp3"
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
        'output_dir': str(output_dir)
    }

    # 在后台线程中运行转换
    thread = threading.Thread(
        target=run_conversion,
        args=(task_id, file_path, output_dir, tts_engine, voice)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': '转换已启动'
    })


@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    """
    SSE 接口，推送转换进度
    """
    queue = progress_queues.get(task_id)
    if not queue:
        return jsonify({'error': '任务不存在'}), 404

    def generate():
        while True:
            try:
                # 阻塞获取进度更新
                data = queue.get(timeout=300)  # 5分钟超时

                # 发送 SSE 事件
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

                # 如果任务完成或出错，结束流
                if data.get('type') in ('complete', 'error'):
                    # 仅清理队列，保留 tasks 中的状态以便刷新恢复
                    if task_id in progress_queues:
                        del progress_queues[task_id]
                    break

            except Exception:
                # 超时或其他错误
                yield f"data: {json.dumps({'type': 'timeout', 'message': '连接超时'})}\n\n"
                break

    return Response(
        generate(),
        mimetype='text/event-stream',
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
                'error': task.get('error'),
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
            'error': t.get('error'),
        })
    return jsonify({'active': False})


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
