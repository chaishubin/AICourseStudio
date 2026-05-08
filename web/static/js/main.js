/* ==========================================================================
   VidPPT Web界面 - 主JavaScript文件
   ========================================================================== */

class VidPPTApp {
    constructor() {
        this.state = {
            file: null,
            filePath: null,
            fileName: null,
            taskId: null,
            videoPath: null,
            isUploading: false,
            isConverting: false
        };

        this.stageNames = {
            'init': '初始化',
            'extract': '提取内容',
            'render': '渲染幻灯片',
            'tts': '文字转语音',
            'video': '合成视频',
            'complete': '完成'
        };

        this.slideUrls = [];

        try {
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
                renderEngine: document.getElementById('render-engine'),

                convertBtn: document.getElementById('convert-btn'),
                renderBtn: document.getElementById('render-btn'),
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
                downloadBtn: document.getElementById('download-btn'),

                slidesModule: document.getElementById('slides-module'),
                slidesToggle: document.getElementById('slides-toggle'),
                slidesToggleIcon: document.getElementById('slides-toggle-icon'),
                slidesBody: document.getElementById('slides-body'),
                slidesGrid: document.getElementById('slides-grid')
            };
        } catch(e) {
            console.error('VidPPT element init failed:', e);
        }

        this.init();
    }

    init() {
        this.bindEvents();
        this.loadVoices();
        this.restoreActiveTask();
    }

    bindEvents() {
        const { uploadArea, fileInput, convertBtn, renderBtn, downloadBtn, ttsEngine } = this.elements;

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
        renderBtn.addEventListener('click', () => this.handleRender());
        downloadBtn.addEventListener('click', () => this.handleDownload());
        ttsEngine.addEventListener('change', () => this.loadVoices());

        const { slidesToggle } = this.elements;
        slidesToggle.addEventListener('click', () => this.toggleSlides());
    }

    toggleSlides() {
        const { slidesBody, slidesToggleIcon } = this.elements;
        const isExpanded = !slidesBody.hidden;
        slidesBody.hidden = isExpanded;
        slidesToggleIcon.classList.toggle('expanded', !isExpanded);
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

    async restoreActiveTask() {
        try {
            const resp = await fetch('/api/active-task');
            const data = await resp.json();
            if (data.task_id) {
                this.state.taskId = data.task_id;

                if (data.status === 'processing' || data.status === 'pending') {
                    this._resumeProgressUI(data);
                    this.startProgressStream(data.task_id);
                } else if (data.status === 'completed') {
                    this._resumeCompletedUI(data);
                } else if (data.status === 'error') {
                    this._resumeErrorUI(data);
                } else if (data.status === 'rendered') {
                    this._resumeRenderedUI(data);
                }
                return;
            }

            const lastResp = await fetch('/api/last-result');
            const lastData = await lastResp.json();
            if (lastData.found && lastData.status === 'completed') {
                this._resumeCompletedUI(lastData);
            } else if (lastData.found && lastData.status === 'error') {
                this._resumeErrorUI(lastData);
            }
        } catch {
            // 无活跃任务，忽略
        }
    }

    _resumeProgressUI(data) {
        const { convertBtn, renderBtn, conversionProgress } = this.elements;
        const { progressStage, progressPercentage, conversionProgressFill } = this.elements;

        convertBtn.disabled = true;
        convertBtn.classList.add('loading');
        renderBtn.disabled = true;
        renderBtn.classList.add('loading');
        this.state.isConverting = true;

        conversionProgress.hidden = false;

        const pct = data.percentage || 0;
        progressPercentage.textContent = `${Math.round(pct)}%`;
        conversionProgressFill.style.width = `${pct}%`;

        const stageLabel = data.stage ? (this.stageNames[data.stage] || data.stage) : '';
        const msg = data.message || (stageLabel ? stageLabel + '...' : '处理中...');
        progressStage.textContent = '转换中：' + msg;
        this.showConvertingStatus(msg);

        this._restoreStepIndicators(data.stage, pct);
    }

    _resumeCompletedUI(data) {
        const { progressStage, progressPercentage, conversionProgressFill,
                convertBtn, renderBtn,
                conversionProgress,
                videoPlayer, previewPlaceholder, downloadBtn,
                fileName, filePath, fileInfo, uploadPlaceholder } = this.elements;

        conversionProgressFill.style.width = '100%';
        progressPercentage.textContent = '100%';
        progressStage.textContent = '完成';

        this._restoreStepIndicators('complete', 100);

        convertBtn.classList.remove('loading');
        convertBtn.disabled = false;
        renderBtn.classList.remove('loading');
        renderBtn.disabled = false;
        this.state.isConverting = false;

        if (data.original_name) {
            this.state.fileName = data.original_name;
            fileName.textContent = data.original_name;
            if (data.file_path) {
                filePath.textContent = data.file_path;
            }
            fileInfo.hidden = false;
            uploadPlaceholder.hidden = true;
        }

        if (data.video_path) {
            this.state.videoPath = data.video_path;
            previewPlaceholder.hidden = true;
            videoPlayer.src = '/api/video?path=' + encodeURIComponent(data.video_path);
            videoPlayer.hidden = false;
            downloadBtn.disabled = false;
        }

        conversionProgress.hidden = false;
        this.showStatus('success', '转换完成');

        // 加载幻灯片预览
        if (data.task_id) this.loadSlides(data.task_id);
    }

    _resumeRenderedUI(data) {
        const { convertBtn, renderBtn } = this.elements;
        convertBtn.classList.remove('loading');
        convertBtn.disabled = false;
        renderBtn.classList.remove('loading');
        renderBtn.disabled = false;
        this.state.isConverting = false;

        if (data.original_name) {
            this.state.fileName = data.original_name;
            this.elements.fileName.textContent = data.original_name;
            this.elements.fileInfo.hidden = false;
            this.elements.uploadPlaceholder.hidden = true;
        }

        this.showStatus('success', '幻灯片渲染完成');
        if (data.task_id) this.loadSlides(data.task_id);
    }

    _resumeErrorUI(data) {
        const { convertBtn, renderBtn } = this.elements;
        convertBtn.classList.remove('loading');
        convertBtn.disabled = false;
        renderBtn.classList.remove('loading');
        renderBtn.disabled = false;
        this.state.isConverting = false;
        this.showStatus('error', data.error || data.message || '转换失败');
    }

    _restoreStepIndicators(currentStage, percentage) {
        const stageOrder = ['init', 'extract', 'render', 'tts', 'video'];
        const currentIdx = stageOrder.indexOf(currentStage);

        stageOrder.forEach((stage, idx) => {
            const step = document.getElementById(`step-${stage}`);
            if (!step) return;
            step.classList.remove('active', 'completed');
            if (idx < currentIdx) {
                step.classList.add('completed');
            } else if (idx === currentIdx && percentage < 100) {
                step.classList.add('active');
            } else if (currentStage === 'complete' || (idx === currentIdx && percentage >= 100)) {
                step.classList.add('completed');
            }
        });

        document.querySelectorAll('.step-line').forEach((line, idx) => {
            line.classList.remove('completed');
            if (idx < currentIdx || currentStage === 'complete') {
                line.classList.add('completed');
            }
        });
    }

    async handleFileSelect(file) {
        const allowedExtensions = ['.ppt', '.pptx'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!allowedExtensions.includes(ext)) {
            alert('不支持的文件类型，请上传 .ppt 或 .pptx 文件');
            return;
        }

        if (file.size === 0) {
            alert('文件为空，请选择有效的PPT文件');
            return;
        }

        this.state.file = file;
        this.state.filePath = null;

        this.elements.fileName.textContent = file.name;
        this.elements.fileInfo.hidden = false;
        this.elements.uploadPlaceholder.hidden = true;

        await this.uploadFile(file);
    }

    async uploadFile(file) {
        const { uploadProgress, progressFill, uploadProgressText, convertBtn, renderBtn } = this.elements;

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
            renderBtn.disabled = false;
            this.elements.convertStatus.hidden = true;
        } catch (error) {
            console.error('上传错误:', error);
            alert('上传失败: ' + error.message);
            this.resetUpload();
        } finally {
            this.state.isUploading = false;
        }
    }

    resetUpload() {
        const { uploadProgress, uploadPlaceholder, fileInfo, convertBtn, renderBtn } = this.elements;
        uploadProgress.hidden = true;
        fileInfo.hidden = true;
        uploadPlaceholder.hidden = false;
        convertBtn.disabled = true;
        renderBtn.disabled = true;
        this.state.file = null;
        this.state.filePath = null;
    }

    resetConversion() {
        const { conversionProgress, convertStatus, videoPlayer, previewPlaceholder, downloadBtn,
                progressStage, progressPercentage, conversionProgressFill, convertBtn, renderBtn,
                slidesModule, slidesBody, slidesToggleIcon, slidesGrid } = this.elements;
        conversionProgress.hidden = true;
        convertStatus.hidden = true;
        convertStatus.className = 'convert-status';
        videoPlayer.hidden = true;
        previewPlaceholder.hidden = false;
        downloadBtn.disabled = true;
        slidesModule.hidden = true;
        slidesBody.hidden = true;
        slidesToggleIcon.classList.remove('expanded');
        slidesGrid.innerHTML = '';

        progressStage.textContent = '准备中...';
        progressPercentage.textContent = '0%';
        conversionProgressFill.style.width = '0%';

        convertBtn.classList.remove('loading');
        renderBtn.classList.remove('loading');

        this.slideUrls = [];

        ['step-init', 'step-extract', 'step-render', 'step-tts', 'step-video'].forEach(id => {
            const step = document.getElementById(id);
            if (step) {
                step.classList.remove('active', 'completed');
            }
        });
        document.querySelectorAll('.step-line').forEach(line => {
            line.classList.remove('completed');
        });

        this.state.videoPath = null;
        this.state.fileName = null;
    }

    setStepStatus(stepId, status) {
        const step = document.getElementById(stepId);
        if (!step) return;

        step.classList.remove('active', 'completed');

        if (status === 'active') {
            step.classList.add('active');
        } else if (status === 'completed') {
            step.classList.add('completed');
            const prevLine = step.previousElementSibling;
            if (prevLine && prevLine.classList.contains('step-line')) {
                prevLine.classList.add('completed');
            }
        }
    }

    setButtonsDisabled(disabled) {
        const { convertBtn, renderBtn } = this.elements;
        if (disabled) {
            convertBtn.disabled = true;
            convertBtn.classList.add('loading');
            renderBtn.disabled = true;
            renderBtn.classList.add('loading');
        } else {
            convertBtn.disabled = false;
            convertBtn.classList.remove('loading');
            renderBtn.disabled = false;
            renderBtn.classList.remove('loading');
        }
    }

    showConvertingStatus(message) {
        const { convertStatus, statusIcon, statusText } = this.elements;
        convertStatus.hidden = false;
        convertStatus.className = 'convert-status converting';
        statusIcon.textContent = '';
        statusIcon.innerHTML = '<span class="spinner" style="width:16px;height:16px;border-width:2px"></span>';
        statusText.textContent = message || '转换中...';
    }

    showStatus(type, message) {
        const { convertStatus, statusIcon, statusText } = this.elements;
        convertStatus.hidden = false;
        convertStatus.className = 'convert-status';
        convertStatus.classList.add(type);
        statusIcon.innerHTML = '';
        statusIcon.textContent = type === 'success' ? '\u2713' : '\u2715';
        statusText.textContent = message;
    }

    async handleConvert() {
        if (!this.state.filePath) {
            alert('请先上传PPT文件');
            return;
        }

        this.resetConversion();
        this.setButtonsDisabled(true);
        this.state.isConverting = true;

        const ttsEngine = this.elements.ttsEngine.value;
        const voice = this.elements.voiceSelect.value;
        const renderEngine = this.elements.renderEngine.value;

        try {
            const response = await fetch('/api/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_path: this.state.filePath,
                    tts_engine: ttsEngine,
                    voice: voice,
                    render_engine: renderEngine
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || '转换失败');
            }

            const result = await response.json();
            this.state.taskId = result.task_id;

            this.elements.conversionProgress.hidden = false;
            this.showConvertingStatus('正在初始化...');
            this.startProgressStream(result.task_id);
        } catch (error) {
            console.error('转换错误:', error);
            this.showStatus('error', '转换失败: ' + error.message);
            this.setButtonsDisabled(false);
            this.state.isConverting = false;
        }
    }

    async handleRender() {
        if (!this.state.filePath) {
            alert('请先上传PPT文件');
            return;
        }

        this.resetConversion();
        this.setButtonsDisabled(true);
        this.state.isConverting = true;

        const renderEngine = this.elements.renderEngine.value;

        try {
            const response = await fetch('/api/render-slides', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_path: this.state.filePath,
                    render_engine: renderEngine
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || '渲染失败');
            }

            const result = await response.json();
            this.state.taskId = result.task_id;

            this.elements.conversionProgress.hidden = false;
            this.showConvertingStatus('正在渲染...');
            this.startProgressStream(result.task_id, 0, true);
        } catch (error) {
            console.error('渲染错误:', error);
            this.showStatus('error', '渲染失败: ' + error.message);
            this.setButtonsDisabled(false);
            this.state.isConverting = false;
        }
    }

    startProgressStream(taskId, retryCount = 0, renderOnly = false) {
        const MAX_RETRIES = 3;
        const RETRY_DELAY = 3000;

        const eventSource = new EventSource(`/api/progress/${taskId}`);
        const { progressStage, progressPercentage, conversionProgressFill,
                convertStatus, statusIcon, statusText,
                videoPlayer, previewPlaceholder, downloadBtn } = this.elements;

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                switch (data.type) {
                    case 'stage':
                        const stageName = this.stageNames[data.stage] || data.stage;
                        progressStage.textContent = '转换中：' + stageName + '...';
                        this.setStepStatus(`step-${data.stage}`, 'active');
                        this.showConvertingStatus(stageName + '...');
                        break;

                    case 'progress':
                        const percentage = data.percentage || 0;
                        const current = data.current || 0;
                        const total = data.total || 0;

                        progressPercentage.textContent = `${Math.round(percentage)}%`;
                        conversionProgressFill.style.width = `${percentage}%`;

                        if (data.message) {
                            progressStage.textContent = '转换中：' + data.message;
                            this.showConvertingStatus(data.message);
                        } else if (data.stage) {
                            const stageName = this.stageNames[data.stage] || data.stage;
                            progressStage.textContent = `转换中：${stageName} (${current}/${total})`;
                            this.showConvertingStatus(`${stageName} (${current}/${total})`);
                        }

                        if (percentage >= 100 && data.stage) {
                            this.setStepStatus(`step-${data.stage}`, 'completed');
                        }
                        break;

                    case 'rendered':
                        eventSource.close();
                        this.setButtonsDisabled(false);
                        this.state.isConverting = false;
                        this.showStatus('success', '幻灯片渲染完成');
                        this.setStepStatus('step-render', 'completed');
                        progressPercentage.textContent = '100%';
                        conversionProgressFill.style.width = '100%';
                        progressStage.textContent = '渲染完成';
                        this.loadSlides(taskId);
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

                        this.showStatus('success', '转换完成');
                        this.setStepStatus('step-video', 'completed');
                        progressPercentage.textContent = '100%';
                        conversionProgressFill.style.width = '100%';
                        progressStage.textContent = '完成';

                        this.setButtonsDisabled(false);
                        this.state.isConverting = false;
                        this.loadSlides(taskId);
                        break;

                    case 'error':
                        eventSource.close();
                        this.showStatus('error', data.message || '转换失败');
                        this.setButtonsDisabled(false);
                        this.state.isConverting = false;
                        break;

                    case 'timeout':
                        eventSource.close();
                        if (this.state.isConverting) {
                            this._reconnectOrRestore(taskId, retryCount, renderOnly);
                        }
                        break;
                }
            } catch (e) {
                console.error('解析进度数据失败:', e);
            }
        };

        eventSource.onerror = () => {
            eventSource.close();
            if (this.state.isConverting) {
                this._reconnectOrRestore(taskId, retryCount, renderOnly);
            }
        };
    }

    _reconnectOrRestore(taskId, retryCount, renderOnly = false) {
        const MAX_RETRIES = 3;
        const RETRY_DELAY = 3000;
        const { progressStage } = this.elements;

        if (retryCount >= MAX_RETRIES) {
            this._showReconnectFailed();
            return;
        }

        progressStage.textContent = '重新连接...';

        setTimeout(() => {
            if (!this.state.isConverting) return;

            fetch('/api/active-task')
                .then(r => r.json())
                .then(d => {
                    if (d.status === 'completed') {
                        this._resumeCompletedUI(d);
                    } else if (d.status === 'rendered') {
                        this._resumeRenderedUI(d);
                    } else if (d.status === 'error') {
                        this._resumeErrorUI(d);
                    } else if (d.task_id && d.status === 'processing') {
                        this.startProgressStream(taskId, retryCount + 1, renderOnly);
                    } else {
                        fetch('/api/last-result')
                            .then(r => r.json())
                            .then(ld => {
                                if (ld.found && ld.status === 'completed') {
                                    this._resumeCompletedUI(ld);
                                } else if (ld.found && ld.status === 'error') {
                                    this._resumeErrorUI(ld);
                                } else {
                                    this.startProgressStream(taskId, retryCount + 1, renderOnly);
                                }
                            })
                            .catch(() => this.startProgressStream(taskId, retryCount + 1, renderOnly));
                    }
                })
                .catch(() => {
                    this.startProgressStream(taskId, retryCount + 1, renderOnly);
                });
        }, RETRY_DELAY);
    }

    _showReconnectFailed() {
        this.showStatus('error', '连接丢失，请刷新页面');
        this.setButtonsDisabled(false);
        this.state.isConverting = false;
    }

    async loadSlides(taskId) {
        try {
            const resp = await fetch(`/api/slides/${taskId}`);
            const data = await resp.json();
            if (data.slides && data.slides.length > 0) {
                this.renderSlides(data.slides);
            }
        } catch (e) {
            console.error('加载幻灯片失败:', e);
        }
    }

    renderSlides(slides) {
        const { slidesModule, slidesBody, slidesToggleIcon, slidesGrid } = this.elements;
        slidesGrid.innerHTML = '';
        this.slideUrls = slides;

        slides.forEach(slide => {
            const thumb = document.createElement('div');
            thumb.className = 'slide-thumb';
            thumb.innerHTML = `
                <img src="${slide.url}" alt="第${slide.page}页" loading="lazy">
                <span class="slide-num">${slide.page}</span>
            `;
            thumb.addEventListener('click', () => this.openLightbox(slide.url, slide.page, slides));
            slidesGrid.appendChild(thumb);
        });

        slidesModule.hidden = false;
        slidesBody.hidden = true;
        slidesToggleIcon.classList.remove('expanded');
    }

    openLightbox(url, page, slides) {
        const overlay = document.createElement('div');
        overlay.className = 'slide-lightbox';

        const currentIndex = slides.findIndex(s => s.url === url);

        overlay.innerHTML = `
            <span class="lightbox-close">&times;</span>
            <span class="lightbox-nav lightbox-prev">&lsaquo;</span>
            <img src="${url}" alt="第${page}页">
            <span class="lightbox-nav lightbox-next">&rsaquo;</span>
        `;

        const close = () => overlay.remove();
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay || e.target.classList.contains('lightbox-close')) close();
        });

        const img = overlay.querySelector('img');
        const prev = overlay.querySelector('.lightbox-prev');
        const next = overlay.querySelector('.lightbox-next');

        const navigate = (delta) => {
            const newIdx = currentIndex + delta;
            if (newIdx >= 0 && newIdx < slides.length) {
                img.src = slides[newIdx].url;
                img.alt = `第${slides[newIdx].page}页`;
            }
        };

        prev.addEventListener('click', (e) => { e.stopPropagation(); navigate(-1); });
        next.addEventListener('click', (e) => { e.stopPropagation(); navigate(1); });

        document.addEventListener('keydown', function handler(e) {
            if (e.key === 'Escape') { close(); document.removeEventListener('keydown', handler); }
            if (e.key === 'ArrowLeft') navigate(-1);
            if (e.key === 'ArrowRight') navigate(1);
        });

        document.body.appendChild(overlay);
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
            a.download = (this.state.file ? this.state.file.name : this.state.fileName || 'video').replace(/\.(ppt|pptx)$/i, '.mp4');
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
