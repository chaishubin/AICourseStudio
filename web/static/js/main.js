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
            taskId: null,
            videoPath: null,
            isUploading: false,
            isConverting: false
        };

        // 阶段名称映射
        this.stageNames = {
            'init': '初始化',
            'extract': '提取内容',
            'tts': '文字转语音',
            'video': '合成视频',
            'complete': '完成'
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

            // 选项模块
            ttsEngine: document.getElementById('tts-engine'),
            voiceSelect: document.getElementById('voice-select'),

            // 转换模块
            convertBtn: document.getElementById('convert-btn'),
            convertStatus: document.getElementById('convert-status'),
            statusText: document.getElementById('status-text'),

            // 进度条
            conversionProgress: document.getElementById('conversion-progress'),
            progressStage: document.getElementById('progress-stage'),
            progressPercentage: document.getElementById('progress-percentage'),
            conversionProgressFill: document.getElementById('conversion-progress-fill'),
            progressDetails: document.getElementById('progress-details'),

            // 预览模块
            previewContainer: document.getElementById('preview-container'),
            previewPlaceholder: document.getElementById('preview-placeholder'),
            videoPlayer: document.getElementById('video-player'),
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
        this.loadVoices();
    }

    /**
     * 绑定事件监听
     */
    bindEvents() {
        const { uploadArea, fileInput, convertBtn, downloadBtn, ttsEngine } = this.elements;

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

        // 下载按钮点击事件
        downloadBtn.addEventListener('click', () => {
            this.handleDownload();
        });

        // TTS 引擎切换时更新语音列表
        ttsEngine.addEventListener('change', () => {
            this.loadVoices();
        });
    }

    /**
     * 加载语音列表
     */
    async loadVoices() {
        const { ttsEngine, voiceSelect } = this.elements;

        try {
            const response = await fetch('/api/voices');
            const voices = await response.json();

            const engine = ttsEngine.value;
            const voiceList = voices[engine] || [];

            // 清空并重新填充选项
            voiceSelect.innerHTML = '';
            voiceList.forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.id;
                option.textContent = voice.name;
                voiceSelect.appendChild(option);
            });
        } catch (error) {
            console.error('加载语音列表失败:', error);
        }
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

        // 重置状态
        this.resetConversion();

        // 更新状态
        this.state.file = file;
        this.state.filePath = null;
        this.state.videoPath = null;

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
     * 重置转换状态
     */
    resetConversion() {
        const { conversionProgress, convertStatus, videoPlayer, previewPlaceholder, downloadBtn } = this.elements;

        conversionProgress.hidden = true;
        convertStatus.hidden = true;
        videoPlayer.hidden = true;
        previewPlaceholder.hidden = false;
        downloadBtn.disabled = true;

        // 重置步骤状态
        ['step-init', 'step-extract', 'step-tts', 'step-video'].forEach(id => {
            const step = document.getElementById(id);
            if (step) {
                step.classList.remove('active', 'completed');
                step.querySelector('.step-icon').textContent = '○';
            }
        });

        this.state.videoPath = null;
    }

    /**
     * 设置步骤状态
     */
    setStepStatus(stepId, status) {
        const step = document.getElementById(stepId);
        if (!step) return;

        const icon = step.querySelector('.step-icon');

        step.classList.remove('active', 'completed');

        if (status === 'active') {
            step.classList.add('active');
            icon.textContent = '◉';
        } else if (status === 'completed') {
            step.classList.add('completed');
            icon.textContent = '●';
        } else {
            icon.textContent = '○';
        }
    }

    /**
     * 处理PPT转视频
     */
    async handleConvert() {
        if (!this.state.filePath) {
            alert('请先上传PPT文件');
            return;
        }

        const { convertBtn, convertStatus, statusText, conversionProgress,
                progressStage, progressPercentage, conversionProgressFill } = this.elements;

        // 重置状态
        this.resetConversion();

        // 显示进度条
        conversionProgress.hidden = false;
        convertStatus.hidden = true;

        // 禁用按钮
        convertBtn.disabled = true;
        this.state.isConverting = true;

        // 获取选项
        const ttsEngine = this.elements.ttsEngine.value;
        const voice = this.elements.voiceSelect.value;

        try {
            // 发送转换请求
            const response = await fetch('/api/convert', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    file_path: this.state.filePath,
                    tts_engine: ttsEngine,
                    voice: voice
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || '转换失败');
            }

            const result = await response.json();
            const taskId = result.task_id;
            this.state.taskId = taskId;

            console.log('转换已启动, task_id:', taskId);

            // 开始监听进度
            this.startProgressStream(taskId);

        } catch (error) {
            console.error('转换错误:', error);
            this.showStatus('error', '转换失败: ' + error.message);
            convertBtn.disabled = false;
            this.state.isConverting = false;
        }
    }

    /**
     * 启动进度流监听
     */
    startProgressStream(taskId) {
        const eventSource = new EventSource(`/api/progress/${taskId}`);
        const { progressStage, progressPercentage, conversionProgressFill,
                progressDetails, convertBtn, convertStatus, statusText,
                videoPlayer, previewPlaceholder, downloadBtn } = this.elements;

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('进度更新:', data);

                switch (data.type) {
                    case 'stage':
                        // 新阶段开始
                        const stageName = this.stageNames[data.stage] || data.stage;
                        progressStage.textContent = stageName + '...';

                        // 更新步骤状态
                        this.setStepStatus(`step-${data.stage}`, 'active');
                        break;

                    case 'progress':
                        // 进度更新
                        const percentage = data.percentage || 0;
                        const current = data.current || 0;
                        const total = data.total || 0;

                        progressPercentage.textContent = `${percentage}%`;
                        conversionProgressFill.style.width = `${percentage}%`;

                        if (data.message) {
                            progressStage.textContent = data.message;
                        } else if (data.stage) {
                            const stageName = this.stageNames[data.stage] || data.stage;
                            progressStage.textContent = `${stageName} (${current}/${total})`;
                        }

                        // 完成当前步骤
                        if (percentage >= 100 && data.stage) {
                            this.setStepStatus(`step-${data.stage}`, 'completed');
                        }
                        break;

                    case 'complete':
                        // 转换完成
                        eventSource.close();

                        if (data.video_path) {
                            this.state.videoPath = data.video_path;

                            // 显示视频
                            previewPlaceholder.hidden = true;
                            videoPlayer.src = '/api/video/' + encodeURIComponent(data.video_path);
                            videoPlayer.hidden = false;
                            downloadBtn.disabled = false;
                        }

                        this.showStatus('success', data.message || '转换完成');
                        this.setStepStatus('step-video', 'completed');
                        progressPercentage.textContent = '100%';
                        conversionProgressFill.style.width = '100%';
                        progressStage.textContent = '完成';

                        convertBtn.disabled = false;
                        this.state.isConverting = false;
                        break;

                    case 'error':
                        // 转换错误
                        eventSource.close();
                        this.showStatus('error', data.message || '转换失败');

                        convertBtn.disabled = false;
                        this.state.isConverting = false;
                        break;

                    case 'timeout':
                        // 连接超时
                        eventSource.close();
                        this.showStatus('error', '连接超时，请重试');

                        convertBtn.disabled = false;
                        this.state.isConverting = false;
                        break;
                }
            } catch (e) {
                console.error('解析进度数据失败:', e);
            }
        };

        eventSource.onerror = (error) => {
            console.error('SSE 连接错误:', error);
            eventSource.close();

            if (this.state.isConverting) {
                this.showStatus('error', '连接丢失，请重试');
                convertBtn.disabled = false;
                this.state.isConverting = false;
            }
        };
    }

    /**
     * 显示状态信息
     */
    showStatus(type, message) {
        const { convertStatus, statusText } = this.elements;

        convertStatus.hidden = false;
        convertStatus.classList.remove('success', 'error');
        convertStatus.classList.add(type);
        statusText.textContent = message;
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
