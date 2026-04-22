"""
Web界面后端API
提供文件上传和PPT转视频的接口
"""

import os
import uuid
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, make_response
from werkzeug.utils import secure_filename

app = Flask(__name__, 
            template_folder=Path(__file__).parent / 'templates', 
            static_folder=Path(__file__).parent / 'static')

# 配置
UPLOAD_FOLDER = Path(__file__).parent / 'uploads'
OUTPUT_FOLDER = Path(__file__).parent / 'outputs'
ALLOWED_EXTENSIONS = {'ppt', 'pptx'}

# 确保目录存在
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['OUTPUT_FOLDER'] = str(OUTPUT_FOLDER)


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """渲染主页面"""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_ppt():
    """
    上传PPT文件接口
    直接返回文件路径，暂不实现实际的文件保存逻辑
    """
    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    
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


@app.route('/api/convert', methods=['POST'])
def convert_ppt():
    """
    PPT转视频接口
    这里留出接口，实际转换逻辑可以后续实现
    
    转换逻辑：
    1. 接收PPT文件路径
    2. 调用vidppt进行转换
    3. 返回视频文件路径和第一帧图片
    """
    data = request.get_json()
    file_path = data.get('file_path')
    
    if not file_path:
        return jsonify({'error': '未提供文件路径'}), 400
    
    # 检查文件是否存在
    if not Path(file_path).exists():
        return jsonify({'error': '文件不存在'}), 404
    
    # 这里可以调用实际的vidppt转换逻辑
    # 当前返回模拟的转换结果
    # 实际实现时，这里应该调用vidppt的Pipeline
    
    # 生成输出视频路径
    input_name = Path(file_path).stem
    video_filename = f"{input_name}.mp4"
    video_path = OUTPUT_FOLDER / video_filename
    
    # 生成第一帧图片路径（转换完成后用于预览）
    frame_filename = f"{input_name}_frame.png"
    frame_path = OUTPUT_FOLDER / frame_filename
    
    # TODO: 实现实际的PPT转视频逻辑
    # 这里先创建一个占位响应，返回文件路径
    # 实际转换需要调用 vidppt.pipeline.Pipeline
    
    # 返回转换结果
    return jsonify({
        'success': True,
        'video_path': str(video_path),
        'frame_path': str(frame_path),
        'message': '转换接口已预留，实际转换逻辑待实现'
    })


@app.route('/api/video/<path:video_path>', methods=['GET'])
def get_video(video_path):
    """获取视频文件用于预览"""
    try:
        return send_file(video_path, mimetype='video/mp4')
    except FileNotFoundError:
        return jsonify({'error': '视频文件不存在'}), 404


@app.route('/api/frame/<path:frame_path>', methods=['GET'])
def get_frame(frame_path):
    """获取视频第一帧图片用于预览"""
    try:
        return send_file(frame_path, mimetype='image/png')
    except FileNotFoundError:
        return jsonify({'error': '图片文件不存在'}), 404


@app.route('/api/download/<path:file_path>', methods=['GET'])
def download_file(file_path):
    """下载文件"""
    try:
        filename = Path(file_path).name
        response = make_response(send_file(file_path))
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response
    except FileNotFoundError:
        return jsonify({'error': '文件不存在'}), 404


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)