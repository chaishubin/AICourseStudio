/* ==========================================================================
   VidPPT Web界面 - 主JavaScript文件
   ========================================================================== */

/**
 * VidPPT Web界面主模块
 * 处理文件上传、转换和视频预览功能
 */

class VidPPTApp {
    constructor() {
        // 状态管理
        this.state = {
            file: null,
            filePath: null,
            videoPath: null,
            framePath: null,
            isUploading: false,
            isConverting: false
        };
        
        // DOM元素
        this.elements = {
            // 上传模块
            uploadArea: document.getElementById('upload-area'),
            fileInput: document.getElementById('file-input'),
            uploadProgress: document.getElementById('upload-progress'),
            progressFill: document.getElementById('progress-fill'),
            uploadProgressText: document.getElementById('upload-progress-text'),
            fileInfo: document.getElementById('file-info'),
            fileName: document.getElementById('file-name'),
            filePath: document.getElementById('file-path'),
            
            // 转换模块
            convertBtn: document.getElementById('convert-btn'),
            convertStatus: document.getElementById('convert-status'),
            statusText: document.getElementById('status-text'),
            
            // 预览模块
            previewContainer: document.getElementById('preview-container'),
            previewPlaceholder: document.querySelector('.preview-placeholder'),
            videoPlayer: document.getElementById('video-player'),
            videoThumbnail: document.getElementById('video-thumbnail'),
            downloadBtn: document.getElementById('download-btn')
        };
        
        // 初始化
        this.init();
    }
    
    /**
     * 初始化应用
     */
    init() {
        this.bindEvents();
    }
    
    /**
     * 绑定事件监听
     */
    bindEvents() {
        const { uploadArea, fileInput, convertBtn, downloadBtn, videoThumbnail, previewPlaceholder } = this.elements;
        
        // 上传区域点击事件
        uploadArea.addEventListener('click', () => {
            fileInput.click();
        });
        
        // 文件选择事件
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                this.handleFileSelect(file);
            }
        });
        
        // 拖拽事件
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file) {
                this.handleFileSelect(file);
            }
        });
        
        // 转换按钮点击事件
        convertBtn.addEventListener('click', () => {
            this.handleConvert();
        });
        
        // 视频缩略图点击事件（下载视频）
        videoThumbnail.addEventListener('click', () => {
            this.handleDownload();
        });
        
        // 下载按钮点击事件
        downloadBtn.addEventListener('click', () => {
            this.handleDownload();
        });
    }
    
    /**
     * 处理文件选择
     * @param {File} file - 选择的上传文件
     */
    async handleFileSelect(file) {
        // 验证文件类型
        const allowedExtensions = ['.ppt', '.pptx'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!allowedExtensions.includes(ext)) {
            alert('不支持的文件类型，请上传 .ppt 或 .pptx 文件');
            return;
        }
        
        // 更新状态
        this.state.file = file;
        this.state.filePath = null;
        this.state.videoPath = null;
        this.state.framePath = null;
        
        // 显示文件名
        this.elements.fileName.textContent = file.name;
        this.elements.fileInfo.hidden = false;
        
        // 开始上传
        await this.uploadFile(file);
    }
    
    /**
     * 上传文件到服务器
     * @param {File} file - 要上传的文件
     */
    async uploadFile(file) {
        const { uploadProgress, progressFill, uploadProgressText, convertBtn } = this.elements;
        
        // 显示上传进度
        uploadProgress.hidden = false;
        progressFill.style.width = '0%';
        uploadProgressText.textContent = '上传中...';
        this.state.isUploading = true;
        
        // 创建FormData
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            // 模拟上传进度
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += 10;
                progressFill.style.width = Math.min(progress, 90) + '%';
                uploadProgressText.textContent = `上传中... ${progress}%`;
            }, 200);
            
            // 发送上传请求
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            
            // 清除进度定时器
            clearInterval(progressInterval);
            progressFill.style.width = '100%';
            uploadProgressText.textContent = '上传完成';
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || '上传失败');
            }
            
            const result = await response.json();
            
            // 更新状态
            this.state.filePath = result.file_path;
            
            // 启用转换按钮
            convertBtn.disabled = false;
            
            console.log('文件上传成功:', result);
            
        } catch (error) {
            console.error('上传错误:', error);
            alert('上传失败: ' + error.message);
            this.resetUpload();
        } finally {
            this.state.isUploading = false;
        }
    }
    
    /**
     * 重置上传状态
     */
    resetUpload() {
        const { uploadProgress, fileInfo, convertBtn } = this.elements;
        
        uploadProgress.hidden = true;
        fileInfo.hidden = true;
        convertBtn.disabled = true;
        
        this.state.file = null;
        this.state.filePath = null;
    }
    
    /**
     * 处理PPT转视频
     */
    async handleConvert() {
        if (!this.state.filePath) {
            alert('请先上传PPT文件');
            return;
        }
        
        const { convertBtn, convertStatus, statusText, videoPlayer, videoThumbnail, downloadBtn, previewPlaceholder } = this.elements;
        
        // 显示转换状态
        convertStatus.hidden = false;
        convertStatus.classList.remove('success', 'error');
        statusText.textContent = '转换中...';
        convertBtn.disabled = true;
        this.state.isConverting = true;
        
        try {
            // 发送转换请求
            const response = await fetch('/api/convert', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    file_path: this.state.filePath
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || '转换失败');
            }
            
            const result = await response.json();
            
            // 更新状态
            this.state.videoPath = result.video_path;
            this.state.framePath = result.frame_path;
            
            // 显示转换成功状态
            convertStatus.classList.add('success');
            statusText.textContent = result.message || '转换完成';
            
            // 显示视频或第一帧预览
            if (this.state.videoPath) {
                // 尝试显示视频
                previewPlaceholder.hidden = true;
                videoPlayer.src = '/api/video/' + encodeURIComponent(this.state.videoPath);
                videoPlayer.hidden = false;
                videoThumbnail.hidden = true;
                downloadBtn.disabled = false;
            } else if (this.state.framePath) {
                // 显示第一帧图片
                previewPlaceholder.hidden = true;
                videoThumbnail.src = '/api/frame/' + encodeURIComponent(this.state.frame_path);
                videoThumbnail.hidden = false;
                videoPlayer.hidden = true;
                downloadBtn.disabled = false;
            } else {
                // 转换未完成，保持显示占位符
                previewPlaceholder.hidden = false;
                videoPlayer.hidden = true;
                videoThumbnail.hidden = true;
                downloadBtn.disabled = true;
            }
            
            console.log('转换成功:', result);
            
        } catch (error) {
            console.error('转换错误:', error);
            convertStatus.classList.add('error');
            statusText.textContent = '转换失败: ' + error.message;
        } finally {
            this.state.isConverting = false;
        }
    }
    
    /**
     * 处理视频下载
     */
    async handleDownload() {
        if (!this.state.videoPath) {
            alert('没有可下载的视频');
            return;
        }
        
        try {
            // 创建下载链接
            const downloadUrl = '/api/download/' + encodeURIComponent(this.state.videoPath);
            
            // 创建临时a标签触发下载
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = this.state.file ? this.state.file.name.replace(/\.(ppt|pptx)$/i, '.mp4') : 'video.mp4';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            
        } catch (error) {
            console.error('下载错误:', error);
            alert('下载失败: ' + error.message);
        }
    }
}

/**
 * 页面加载完成后初始化应用
 */
document.addEventListener('DOMContentLoaded', () => {
    window.app = new VidPPTApp();
});