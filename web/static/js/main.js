/* ==========================================================================
   VidPPT Web界面 - 主JavaScript文件
   ========================================================================== */

class VidPPTApp {
    constructor() {
        this.state = {
            file: null,
            filePath: null,
            taskId: null,
            videoPath: null,
            isUploading: false,
            isConverting: false
        };

        this.stageNames = {
            'init': '初始化',
            'extract': '提取内容',
            'tts': '文字转语音',
            'video': '合成视频',
            'complete': '完成'
        };

        this.elements = {
            uploadArea: document.getElementById('upload-area'),
            fileInput: document.getElementById('file-input'),
            uploadPlaceholder: document.getElementById('upload-placeholder'),
            uploadProgress: document.getElementById('upload-progress'),
            progressFill: document.getElementById('progress-fill'),
            uploadProgressText: document.getElementById('upload-progress-text'),
            fileInfo: document.getElementById('file-info'),
            fileName: document.getElementById('file-name'),
            filePath: document.getElementById('file-path'),

            ttsEngine: document.getElementById('tts-engine'),
            voiceSelect: document.getElementById('voice-select'),

            convertBtn: document.getElementById('convert-btn'),
            convertStatus: document.getElementById('convert-status'),
            statusIcon: document.getElementById('status-icon'),
            statusText: document.getElementById('status-text'),

            conversionProgress: document.getElementById('conversion-progress'),
            progressStage: document.getElementById('progress-stage'),
            progressPercentage: document.getElementById('progress-percentage'),
            conversionProgressFill: document.getElementById('conversion-progress-fill'),

            previewContainer: document.getElementById('preview-container'),
            previewPlaceholder: document.getElementById('preview-placeholder'),
            videoPlayer: document.getElementById('video-player'),
            downloadBtn: document.getElementById('download-btn')
        };

        this.init();
    }

    init() {
        this.bindEvents();
        this.loadVoices();
    }

    bindEvents() {
        const { uploadArea, fileInput, convertBtn, downloadBtn, ttsEngine } = this.elements;

        uploadArea.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) this.handleFileSelect(file);
        });

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
            if (file) this.handleFileSelect(file);
        });

        convertBtn.addEventListener('click', () => this.handleConvert());
        downloadBtn.addEventListener('click', () => this.handleDownload());
        ttsEngine.addEventListener('change', () => this.loadVoices());
    }

    async loadVoices() {
        const { ttsEngine, voiceSelect } = this.elements;
        try {
            const response = await fetch('/api/voices');
            const voices = await response.json();
            const engine = ttsEngine.value;
            const voiceList = voices[engine] || [];
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

    async handleFileSelect(file) {
        const allowedExtensions = ['.ppt', '.pptx'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!allowedExtensions.includes(ext)) {
            alert('不支持的文件类型，请上传 .ppt 或 .pptx 文件');
            return;
        }

        this.resetConversion();
        this.state.file = file;
        this.state.filePath = null;
        this.state.videoPath = null;

        this.elements.fileName.textContent = file.name;
        this.elements.fileInfo.hidden = false;
        this.elements.uploadPlaceholder.hidden = true;

        await this.uploadFile(file);
    }

    async uploadFile(file) {
        const { uploadProgress, progressFill, uploadProgressText, convertBtn } = this.elements;

        uploadProgress.hidden = false;
        progressFill.style.width = '0%';
        uploadProgressText.textContent = '上传中...';
        this.state.isUploading = true;

        const formData = new FormData();
        formData.append('file', file);

        try {
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += 10;
                progressFill.style.width = Math.min(progress, 90) + '%';
                uploadProgressText.textContent = `上传中... ${progress}%`;
            }, 200);

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            clearInterval(progressInterval);
            progressFill.style.width = '100%';
            uploadProgressText.textContent = '上传完成';

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || '上传失败');
            }

            const result = await response.json();
            this.state.filePath = result.file_path;
            convertBtn.disabled = false;
        } catch (error) {
            console.error('上传错误:', error);
            alert('上传失败: ' + error.message);
            this.resetUpload();
        } finally {
            this.state.isUploading = false;
        }
    }

    resetUpload() {
        const { uploadProgress, uploadPlaceholder, fileInfo, convertBtn } = this.elements;
        uploadProgress.hidden = true;
        fileInfo.hidden = true;
        uploadPlaceholder.hidden = false;
        convertBtn.disabled = true;
        this.state.file = null;
        this.state.filePath = null;
    }

    resetConversion() {
        const { conversionProgress, convertStatus, videoPlayer, previewPlaceholder, downloadBtn } = this.elements;
        conversionProgress.hidden = true;
        convertStatus.hidden = true;
        videoPlayer.hidden = true;
        previewPlaceholder.hidden = false;
        downloadBtn.disabled = true;

        ['step-init', 'step-extract', 'step-tts', 'step-video'].forEach(id => {
            const step = document.getElementById(id);
            if (step) {
                step.classList.remove('active', 'completed');
            }
        });
        document.querySelectorAll('.step-line').forEach(line => {
            line.classList.remove('completed');
        });

        this.state.videoPath = null;
    }

    setStepStatus(stepId, status) {
        const step = document.getElementById(stepId);
        if (!step) return;

        step.classList.remove('active', 'completed');

        if (status === 'active') {
            step.classList.add('active');
        } else if (status === 'completed') {
            step.classList.add('completed');
            // Mark the line before this step as completed
            const prevLine = step.previousElementSibling;
            if (prevLine && prevLine.classList.contains('step-line')) {
                prevLine.classList.add('completed');
            }
        }
    }

    async handleConvert() {
        if (!this.state.filePath) {
            alert('请先上传PPT文件');
            return;
        }

        const { convertBtn, convertStatus, conversionProgress } = this.elements;

        this.resetConversion();
        conversionProgress.hidden = false;
        convertStatus.hidden = true;
        convertBtn.disabled = true;
        this.state.isConverting = true;

        const ttsEngine = this.elements.ttsEngine.value;
        const voice = this.elements.voiceSelect.value;

        try {
            const response = await fetch('/api/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
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
            this.state.taskId = result.task_id;
            this.startProgressStream(result.task_id);
        } catch (error) {
            console.error('转换错误:', error);
            this.showStatus('error', '转换失败: ' + error.message);
            convertBtn.disabled = false;
            this.state.isConverting = false;
        }
    }

    startProgressStream(taskId) {
        const eventSource = new EventSource(`/api/progress/${taskId}`);
        const { progressStage, progressPercentage, conversionProgressFill,
                convertBtn, convertStatus, statusIcon, statusText,
                videoPlayer, previewPlaceholder, downloadBtn } = this.elements;

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                switch (data.type) {
                    case 'stage':
                        const stageName = this.stageNames[data.stage] || data.stage;
                        progressStage.textContent = stageName + '...';
                        this.setStepStatus(`step-${data.stage}`, 'active');
                        break;

                    case 'progress':
                        const percentage = data.percentage || 0;
                        const current = data.current || 0;
                        const total = data.total || 0;

                        progressPercentage.textContent = `${Math.round(percentage)}%`;
                        conversionProgressFill.style.width = `${percentage}%`;

                        if (data.message) {
                            progressStage.textContent = data.message;
                        } else if (data.stage) {
                            const stageName = this.stageNames[data.stage] || data.stage;
                            progressStage.textContent = `${stageName} (${current}/${total})`;
                        }

                        if (percentage >= 100 && data.stage) {
                            this.setStepStatus(`step-${data.stage}`, 'completed');
                        }
                        break;

                    case 'complete':
                        eventSource.close();

                        if (data.video_path) {
                            this.state.videoPath = data.video_path;
                            previewPlaceholder.hidden = true;
                            videoPlayer.src = '/api/video?path=' + encodeURIComponent(data.video_path);
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
                        eventSource.close();
                        this.showStatus('error', data.message || '转换失败');
                        convertBtn.disabled = false;
                        this.state.isConverting = false;
                        break;

                    case 'timeout':
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

        eventSource.onerror = () => {
            eventSource.close();
            if (this.state.isConverting) {
                this.showStatus('error', '连接丢失，请重试');
                convertBtn.disabled = false;
                this.state.isConverting = false;
            }
        };
    }

    showStatus(type, message) {
        const { convertStatus, statusIcon, statusText } = this.elements;
        convertStatus.hidden = false;
        convertStatus.classList.remove('success', 'error');
        convertStatus.classList.add(type);
        statusIcon.textContent = type === 'success' ? '✓' : '✕';
        statusText.textContent = message;
    }

    async handleDownload() {
        if (!this.state.videoPath) {
            alert('没有可下载的视频');
            return;
        }

        try {
            const downloadUrl = '/api/download?path=' + encodeURIComponent(this.state.videoPath);
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

document.addEventListener('DOMContentLoaded', () => {
    window.app = new VidPPTApp();
});
