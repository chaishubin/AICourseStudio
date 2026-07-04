/* ==========================================================================
   AI Course Studio - 主JavaScript文件
   ========================================================================== */

class AICourseStudioApp {
    constructor() {
        this.state = {
            files: [],  // [{file, filePath, fileName, taskId, status, percentage, stage, message, videoPath, error}]
            isUploading: false,
            isConverting: false,
            activeEventSources: new Map()  // taskId → EventSource
        };

        this.stageNames = {
            'init': '初始化',
            'extract': '提取内容',
            'render': '渲染幻灯片',
            'llm': 'AI 课程设计',
            'preview': '确认讲稿',
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
                fileList: document.getElementById('file-list'),

                ttsEngine: document.getElementById('tts-engine'),
                voiceSelect: document.getElementById('voice-select'),
                renderEngine: document.getElementById('render-engine'),

                llmEnabled: document.getElementById('llm-enabled'),
                llmEngine: document.getElementById('llm-engine'),
                llmModeGroup: document.getElementById('llm-mode-group'),
                llmMode: document.getElementById('llm-mode'),

                convertBtn: document.getElementById('convert-btn'),
                renderBtn: document.getElementById('render-btn'),
                convertStatus: document.getElementById('convert-status'),
                statusIcon: document.getElementById('status-icon'),
                statusText: document.getElementById('status-text'),

                batchSummary: document.getElementById('batch-summary'),
                batchCount: document.getElementById('batch-count'),
                batchProgressFill: document.getElementById('batch-progress-fill'),

                conversionProgress: document.getElementById('conversion-progress'),
                progressStage: document.getElementById('progress-stage'),
                progressPercentage: document.getElementById('progress-percentage'),
                conversionProgressFill: document.getElementById('conversion-progress-fill'),

                resultsModule: document.getElementById('results-module'),
                resultsGrid: document.getElementById('results-grid'),

                slidesModule: document.getElementById('slides-module'),
                slidesToggle: document.getElementById('slides-toggle'),
                slidesToggleIcon: document.getElementById('slides-toggle-icon'),
                slidesBody: document.getElementById('slides-body'),
                slidesGrid: document.getElementById('slides-grid'),

                coursePreviewModule: document.getElementById('course-preview-module'),
                coursePreviewPages: document.getElementById('course-preview-pages'),
                coursePreviewSaveState: document.getElementById('course-preview-save-state'),
                saveScriptsBtn: document.getElementById('save-scripts-btn'),
                continueCourseBtn: document.getElementById('continue-course-btn'),
                metricTotal: document.getElementById('metric-total'),
                metricProcessing: document.getElementById('metric-processing'),
                metricReview: document.getElementById('metric-review'),
                metricCompleted: document.getElementById('metric-completed')
            };
        } catch(e) {
            console.error('AICourseStudio element init failed:', e);
        }

        this.init();
    }

    init() {
        this.bindEvents();
        this.loadVoices();
        this.restoreTasks();
    }

    // ── State helpers ──────────────────────────────────
    getItemByTaskId(taskId) {
        const idx = this.state.files.findIndex(f => f.taskId === taskId);
        return idx >= 0 ? { index: idx, item: this.state.files[idx] } : null;
    }

    updateItem(index, patch) {
        Object.assign(this.state.files[index], patch);
    }

    // ── Events ─────────────────────────────────────────
    bindEvents() {
        const { uploadArea, fileInput, convertBtn, renderBtn, ttsEngine } = this.elements;

        uploadArea.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', (e) => {
            for (const file of e.target.files) {
                this.handleFileSelect(file);
            }
            fileInput.value = '';
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
            for (const file of e.dataTransfer.files) {
                this.handleFileSelect(file);
            }
        });

        convertBtn.addEventListener('click', () => this.handleConvert());
        renderBtn.addEventListener('click', () => this.handleRender());
        ttsEngine.addEventListener('change', () => this.loadVoices());

        const { llmEnabled } = this.elements;
        llmEnabled.addEventListener('change', () => this.toggleLLMMode());

        const { slidesToggle } = this.elements;
        slidesToggle.addEventListener('click', () => this.toggleSlides());
        this.elements.saveScriptsBtn.addEventListener('click', () => this.savePreviewScripts());
        this.elements.continueCourseBtn.addEventListener('click', () => this.continueCourse());
    }

    toggleSlides() {
        const { slidesBody, slidesToggleIcon } = this.elements;
        const isExpanded = !slidesBody.hidden;
        slidesBody.hidden = isExpanded;
        slidesToggleIcon.classList.toggle('expanded', !isExpanded);
    }

    toggleLLMMode() {
        const { llmEnabled, llmModeGroup } = this.elements;
        llmModeGroup.classList.toggle('visible', llmEnabled.checked);
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

    // ── Multi-file upload ──────────────────────────────
    async handleFileSelect(file) {
        const allowedExtensions = ['.docx', '.pdf', '.ppt', '.pptx'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!allowedExtensions.includes(ext)) {
            alert('不支持的文件类型，请上传 Word、PDF 或 PowerPoint 文件');
            return;
        }

        if (file.size === 0) {
            alert('文件为空，请选择有效的课程文件');
            return;
        }

        const index = this.state.files.length;
        this.state.files.push({
            file,
            filePath: null,
            fileName: file.name,
            sourceType: ['.docx', '.pdf'].includes(ext) ? 'lesson-plan' : 'presentation',
            taskId: null,
            status: 'uploading',
            percentage: 0,
            stage: null,
            message: '上传中...',
            videoPath: null,
            courseJsonPath: null,
            presentationPath: null,
            subtitlesPath: null,
            error: null
        });

        this.renderFileList();
        await this.uploadFile(file, index);
    }

    async uploadFile(file, index) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += 10;
                this.updateItem(index, { percentage: Math.min(progress, 90), message: `上传中 ${Math.min(progress, 90)}%` });
                this.renderFileList();
            }, 200);

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            clearInterval(progressInterval);

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || '上传失败');
            }

            const result = await response.json();
            this.updateItem(index, {
                filePath: result.file_path,
                status: 'pending',
                percentage: 0,
                message: '待转换'
            });
            this.renderFileList();
        } catch (error) {
            console.error('上传错误:', error);
            this.updateItem(index, { status: 'error', message: '上传失败', error: error.message });
            this.renderFileList();
        }
    }

    // ── File list rendering ─────────────────────────────
    renderFileList() {
        const container = this.elements.fileList;
        container.innerHTML = '';

        this.state.files.forEach((item, index) => {
            const row = document.createElement('div');
            row.className = `file-list-item status-${item.status}`;

            const statusText = this._fileStatusText(item);
            const showMiniProgress = ['uploading', 'processing'].includes(item.status);

            row.innerHTML = `
                <svg class="file-list-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
                <span class="file-list-name" title="${this._esc(item.fileName)}">${this._esc(item.fileName)}</span>
                <span class="file-list-status status-${item.status}">${statusText}</span>
                ${showMiniProgress ? `<div class="mini-progress-bar"><div class="mini-progress-fill" style="width:${item.percentage}%"></div></div>` : ''}
                <button class="file-list-remove" data-index="${index}" title="移除">&times;</button>
            `;

            row.querySelector('.file-list-remove').addEventListener('click', () => this.removeFile(index));
            container.appendChild(row);
        });

        // Update convert/render buttons
        const pendingCount = this.state.files.filter(f => f.status === 'pending' && f.filePath).length;
        const previewableCount = this.state.files.filter(
            f => f.status === 'pending' && f.filePath && f.sourceType !== 'lesson-plan'
        ).length;
        this.elements.convertBtn.disabled = pendingCount === 0 || this.state.isConverting;
        this.elements.renderBtn.disabled = previewableCount === 0 || this.state.isConverting;
        this.updateWorkspaceMetrics();
    }

    updateWorkspaceMetrics() {
        const files = this.state.files;
        const processing = files.filter(item =>
            ['uploading', 'queued', 'processing'].includes(item.status)
        ).length;
        const review = files.filter(item => item.status === 'awaiting_confirmation').length;
        const completed = files.filter(item => item.status === 'completed').length;
        if (this.elements.metricTotal) this.elements.metricTotal.textContent = files.length;
        if (this.elements.metricProcessing) this.elements.metricProcessing.textContent = processing;
        if (this.elements.metricReview) this.elements.metricReview.textContent = review;
        if (this.elements.metricCompleted) this.elements.metricCompleted.textContent = completed;
    }

    _fileStatusText(item) {
        switch (item.status) {
            case 'uploading': return item.message || '上传中...';
            case 'pending': return '待转换';
            case 'queued': return '排队中';
            case 'awaiting_confirmation': return '等待确认讲稿';
            case 'processing': {
                const stageName = this.stageNames[item.stage] || item.stage || '';
                return `${stageName} ${Math.round(item.percentage)}%`;
            }
            case 'completed': return '已完成';
            case 'error': return '失败';
            default: return item.message || '';
        }
    }

    _esc(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    // ── Remove file ────────────────────────────────────
    removeFile(index) {
        const item = this.state.files[index];
        if (item.taskId && this.state.activeEventSources.has(item.taskId)) {
            this.state.activeEventSources.get(item.taskId).close();
            this.state.activeEventSources.delete(item.taskId);
        }
        this.state.files.splice(index, 1);
        this.renderFileList();
        this.renderResultsGrid();
        this.updateBatchSummary();
    }

    // ── Batch convert ───────────────────────────────────
    async handleConvert() {
        const pending = this.state.files.filter(f => f.status === 'pending' && f.filePath);
        if (pending.length === 0) return;

        this.state.isConverting = true;
        this.elements.convertBtn.disabled = true;
        this.elements.renderBtn.disabled = true;

        const ttsEngine = this.elements.ttsEngine.value;
        const voice = this.elements.voiceSelect.value;
        const renderEngine = this.elements.renderEngine.value;
        const llmEnabled = this.elements.llmEnabled.checked;
        const llmEngine = this.elements.llmEngine.value;
        const llmMode = this.elements.llmMode.value;

        this.elements.conversionProgress.hidden = false;

        for (const item of pending) {
            const index = this.state.files.indexOf(item);
            this.updateItem(index, { status: 'queued', message: '排队中' });
            this.renderFileList();

            try {
                const response = await fetch('/api/convert', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        file_path: item.filePath,
                        original_name: item.fileName,
                        tts_engine: ttsEngine,
                        voice: voice,
                        render_engine: renderEngine,
                        llm_enabled: llmEnabled,
                        llm_engine: llmEngine,
                        llm_mode: llmMode
                    })
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || '转换失败');
                }

                const result = await response.json();
                this.updateItem(index, {
                    taskId: result.task_id,
                    status: 'processing',
                    message: '正在初始化...'
                });
                this.renderFileList();
                this.renderResultsGrid();
                this.startProgressStream(result.task_id);

                // Wait for this task to complete before starting next
                await this._waitForTask(result.task_id);
            } catch (error) {
                const idx = this.state.files.indexOf(item);
                if (idx >= 0) {
                    this.updateItem(idx, { status: 'error', error: error.message, message: error.message });
                    this.renderFileList();
                    this.renderResultsGrid();
                    this.updateBatchSummary();
                }
            }
        }

        this.state.isConverting = false;
        this.elements.conversionProgress.hidden = true;
        this._refreshButtons();
    }

    _waitForTask(taskId) {
        return new Promise((resolve) => {
            const check = () => {
                const found = this.getItemByTaskId(taskId);
                if (!found || ['awaiting_confirmation', 'completed', 'error'].includes(found.item.status)) {
                    resolve();
                } else {
                    setTimeout(check, 500);
                }
            };
            check();
        });
    }

    // ── Render only (single file for now) ──────────────
    async handleRender() {
        // Find first pending file
        const item = this.state.files.find(
            f => f.status === 'pending' && f.filePath && f.sourceType !== 'lesson-plan'
        );
        if (!item) return;

        const index = this.state.files.indexOf(item);
        this.state.isConverting = true;
        this.elements.convertBtn.disabled = true;
        this.elements.renderBtn.disabled = true;

        this.updateItem(index, { status: 'queued', message: '排队中' });
        this.renderFileList();

        const renderEngine = this.elements.renderEngine.value;

        try {
            const response = await fetch('/api/render-slides', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_path: item.filePath,
                    render_engine: renderEngine
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || '渲染失败');
            }

            const result = await response.json();
            this.updateItem(index, {
                taskId: result.task_id,
                status: 'processing',
                message: '正在渲染...'
            });
            this.renderFileList();
            this.startProgressStream(result.task_id, true);
        } catch (error) {
            this.updateItem(index, { status: 'error', error: error.message, message: error.message });
            this.renderFileList();
            this.state.isConverting = false;
            this._refreshButtons();
        }
    }

    // ── Progress stream ─────────────────────────────────
    startProgressStream(taskId, renderOnly = false, retryCount = 0) {
        const MAX_RETRIES = 3;
        const RETRY_DELAY = 3000;

        const eventSource = new EventSource(`/api/progress/${taskId}`);
        this.state.activeEventSources.set(taskId, eventSource);

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                const found = this.getItemByTaskId(taskId);
                if (!found) return;
                const { index, item } = found;

                switch (data.type) {
                    case 'stage':
                        this.updateItem(index, { stage: data.stage, message: (this.stageNames[data.stage] || data.stage) + '...' });
                        this.renderFileList();
                        break;

                    case 'progress': {
                        const percentage = data.percentage || 0;
                        const message = data.message || (data.stage ? `${this.stageNames[data.stage] || data.stage} (${data.current}/${data.total})` : '');
                        this.updateItem(index, { percentage, stage: data.stage || item.stage, message });
                        this.renderFileList();

                        // Update main progress bar to show current task
                        this.elements.progressPercentage.textContent = `${Math.round(percentage)}%`;
                        this.elements.conversionProgressFill.style.width = `${percentage}%`;
                        if (message) {
                            this.elements.progressStage.textContent = message;
                        }
                        break;
                    }

                    case 'rendered':
                        eventSource.close();
                        this.state.activeEventSources.delete(taskId);
                        this.updateItem(index, { status: 'completed', percentage: 100, message: '渲染完成' });
                        this.renderFileList();
                        this.renderResultsGrid();
                        this.updateBatchSummary();
                        this.showStatus('success', '幻灯片渲染完成');
                        this.loadSlides(taskId);
                        break;

                    case 'preview_ready':
                        eventSource.close();
                        this.state.activeEventSources.delete(taskId);
                        this.updateItem(index, {
                            status: 'awaiting_confirmation',
                            percentage: 50,
                            stage: 'preview',
                            message: '请确认逐页讲稿',
                            courseJsonPath: data.course_json_path || null,
                            presentationPath: data.presentation_path || null
                        });
                        this.renderFileList();
                        this.renderResultsGrid();
                        this.updateBatchSummary();
                        this.showStatus('success', '预览已生成，请确认讲稿');
                        this.loadCoursePreview(taskId);
                        break;

                    case 'complete':
                        eventSource.close();
                        this.state.activeEventSources.delete(taskId);
                        this.updateItem(index, {
                            status: 'completed',
                            percentage: 100,
                            message: '转换完成',
                            videoPath: data.video_path,
                            courseJsonPath: data.course_json_path || null,
                            presentationPath: data.presentation_path || null,
                            subtitlesPath: data.subtitles_path || null
                        });
                        this.renderFileList();
                        this.renderResultsGrid();
                        this.updateBatchSummary();
                        this.showStatus('success', '转换完成');
                        this.loadSlides(taskId);
                        break;

                    case 'error':
                        eventSource.close();
                        this.state.activeEventSources.delete(taskId);
                        this.updateItem(index, { status: 'error', error: data.message, message: data.message });
                        this.renderFileList();
                        this.renderResultsGrid();
                        this.updateBatchSummary();
                        break;

                    case 'timeout':
                        eventSource.close();
                        this.state.activeEventSources.delete(taskId);
                        if (item.status === 'processing') {
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
            this.state.activeEventSources.delete(taskId);
            const found = this.getItemByTaskId(taskId);
            if (found && found.item.status === 'processing') {
                this._reconnectOrRestore(taskId, retryCount, renderOnly);
            }
        };
    }

    _reconnectOrRestore(taskId, retryCount, renderOnly = false) {
        const MAX_RETRIES = 3;
        const RETRY_DELAY = 3000;

        if (retryCount >= MAX_RETRIES) {
            this.showStatus('error', '连接丢失，请刷新页面');
            return;
        }

        this.elements.progressStage.textContent = '重新连接...';

        setTimeout(() => {
            const found = this.getItemByTaskId(taskId);
            if (!found || found.item.status !== 'processing') return;

            fetch(`/api/status/${taskId}`)
                .then(r => r.json())
                .then(d => {
                    if (d.status === 'awaiting_confirmation') {
                        this.updateItem(found.index, {
                            status: 'awaiting_confirmation',
                            percentage: 50,
                            message: '请确认逐页讲稿'
                        });
                        this.renderFileList();
                        this.renderResultsGrid();
                        this.loadCoursePreview(taskId);
                    } else if (d.status === 'completed') {
                        const idx = found.index;
                        this.updateItem(idx, { status: 'completed', percentage: 100, message: '转换完成', videoPath: d.video_path });
                        this.renderFileList();
                        this.renderResultsGrid();
                        this.updateBatchSummary();
                    } else if (d.status === 'error') {
                        this.updateItem(found.index, { status: 'error', error: d.error, message: d.error });
                        this.renderFileList();
                        this.renderResultsGrid();
                        this.updateBatchSummary();
                    } else {
                        this.startProgressStream(taskId, renderOnly, retryCount + 1);
                    }
                })
                .catch(() => {
                    this.startProgressStream(taskId, renderOnly, retryCount + 1);
                });
        }, RETRY_DELAY);
    }

    // ── Results grid rendering ──────────────────────────
    renderResultsGrid() {
        const container = this.elements.resultsGrid;
        container.innerHTML = '';

        let hasVisible = false;

        this.state.files.forEach((item, index) => {
            if (!['awaiting_confirmation', 'completed', 'processing', 'queued', 'error'].includes(item.status)) return;
            hasVisible = true;

            const card = document.createElement('div');
            card.className = 'result-card';
            if (item.status === 'error') card.classList.add('error-card');

            if (item.status === 'awaiting_confirmation') {
                card.innerHTML = `
                    <div class="result-video-wrap">
                        <div class="result-placeholder"><p>等待确认逐页讲稿</p></div>
                    </div>
                    <div class="result-card-footer">
                        <span class="result-card-name" title="${this._esc(item.fileName)}">${this._esc(item.fileName)}</span>
                    </div>
                    <button class="result-card-download preview-open-btn" data-index="${index}">编辑讲稿</button>
                `;
                card.querySelector('.preview-open-btn').addEventListener('click', () => this.loadCoursePreview(item.taskId));
            } else if (item.status === 'completed' && item.videoPath) {
                const artifacts = this._artifactLinks(item);
                card.innerHTML = `
                    <div class="result-video-wrap">
                        <video src="/api/video?path=${encodeURIComponent(item.videoPath)}" controls preload="metadata"></video>
                    </div>
                    <div class="result-card-footer">
                        <span class="result-card-name" title="${this._esc(item.fileName)}">${this._esc(item.fileName)}</span>
                        <button class="result-card-download" data-index="${index}">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                <polyline points="7 10 12 15 17 10"/>
                                <line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                            下载
                        </button>
                    </div>
                    ${artifacts}
                `;
                card.querySelector('.result-card-download').addEventListener('click', () => this.handleDownload(index));
            } else if (item.status === 'completed') {
                card.innerHTML = `
                    <div class="result-video-wrap">
                        <div class="result-placeholder"><p>课程文件已生成</p></div>
                    </div>
                    <div class="result-card-footer">
                        <span class="result-card-name">${this._esc(item.fileName)}</span>
                    </div>
                    ${this._artifactLinks(item)}
                `;
            } else {
                const placeholderText = item.status === 'error'
                    ? this._esc(item.error || '转换失败')
                    : item.status === 'queued'
                        ? '排队中...'
                        : '转换中...';

                card.innerHTML = `
                    <div class="result-video-wrap">
                        <div class="result-placeholder">
                            ${item.status !== 'error' ? '<div class="spinner"></div>' : ''}
                            <p>${placeholderText}</p>
                        </div>
                    </div>
                    <div class="result-card-footer">
                        <span class="result-card-name" title="${this._esc(item.fileName)}">${this._esc(item.fileName)}</span>
                    </div>
                `;
            }

            container.appendChild(card);
        });

        this.elements.resultsModule.hidden = !hasVisible;
    }

    // ── Single item download ────────────────────────────
    handleDownload(index) {
        const item = this.state.files[index];
        if (!item || !item.videoPath) {
            alert('没有可下载的视频');
            return;
        }

        try {
            const downloadUrl = '/api/download?path=' + encodeURIComponent(item.videoPath);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = item.fileName.replace(/\.(ppt|pptx)$/i, '.mp4');
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        } catch (error) {
            console.error('下载错误:', error);
            alert('下载失败: ' + error.message);
        }
    }

    _artifactLinks(item) {
        const artifacts = [
            ['课程 JSON', item.courseJsonPath],
            ['可编辑 PPT', item.presentationPath],
            ['字幕 SRT', item.subtitlesPath],
            ['课程视频', item.videoPath]
        ].filter(([, path]) => path);
        if (!artifacts.length) return '';
        return `<div class="artifact-links">${artifacts.map(([label, path]) =>
            `<a class="artifact-link" href="/api/download?path=${encodeURIComponent(path)}">${label}</a>`
        ).join('')}</div>`;
    }

    // ── Batch summary ──────────────────────────────────
    updateBatchSummary() {
        const total = this.state.files.filter(f => ['awaiting_confirmation', 'completed', 'processing', 'queued', 'error'].includes(f.status)).length;
        const completed = this.state.files.filter(f => f.status === 'completed').length;
        const failed = this.state.files.filter(f => f.status === 'error').length;

        if (total === 0) {
            this.elements.batchSummary.hidden = true;
            return;
        }

        this.elements.batchSummary.hidden = false;
        this.elements.batchCount.textContent = `${completed + failed}/${total}`;
        this.elements.batchProgressFill.style.width = `${(completed + failed) / total * 100}%`;

        // Check if all done
        if (completed + failed === total) {
            this.state.isConverting = false;
            this._refreshButtons();
        }
    }

    _refreshButtons() {
        const pendingCount = this.state.files.filter(f => f.status === 'pending' && f.filePath).length;
        const previewableCount = this.state.files.filter(
            f => f.status === 'pending' && f.filePath && f.sourceType !== 'lesson-plan'
        ).length;
        this.elements.convertBtn.disabled = pendingCount === 0 || this.state.isConverting;
        this.elements.renderBtn.disabled = previewableCount === 0 || this.state.isConverting;
        if (this.state.isConverting) {
            this.elements.convertBtn.classList.add('loading');
            this.elements.renderBtn.classList.add('loading');
        } else {
            this.elements.convertBtn.classList.remove('loading');
            this.elements.renderBtn.classList.remove('loading');
        }
    }

    // ── Status helpers ──────────────────────────────────
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

    // ── State restoration ───────────────────────────────
    async restoreTasks() {
        try {
            const resp = await fetch('/api/tasks');
            const data = await resp.json();
            if (data.tasks && data.tasks.length > 0) {
                this.state.files = data.tasks.map(t => ({
                    file: null,
                    filePath: null,
                    fileName: t.original_name || '未知文件',
                    sourceType: /\.(docx|pdf)$/i.test(t.original_name || '') ? 'lesson-plan' : 'presentation',
                    taskId: t.task_id,
                    status: t.status === 'processing' || t.status === 'pending' ? 'processing' : t.status,
                    percentage: t.percentage || 0,
                    stage: t.stage,
                    message: t.message || '',
                    videoPath: t.video_path || null,
                    courseJsonPath: t.course_json_path || null,
                    presentationPath: t.presentation_path || null,
                    subtitlesPath: t.subtitles_path || null,
                    previewPath: t.preview_path || null,
                    error: t.error || null
                }));

                this.renderFileList();
                this.renderResultsGrid();
                this.updateBatchSummary();

                // Reconnect SSE for processing tasks
                for (const item of this.state.files) {
                    if (item.status === 'processing' && item.taskId) {
                        this.startProgressStream(item.taskId);
                    }
                }
                const awaiting = this.state.files.find(item => item.status === 'awaiting_confirmation');
                if (awaiting) this.loadCoursePreview(awaiting.taskId);
            }
        } catch {
            // No tasks to restore
        }
    }

    // ── Editable course preview ─────────────────────────
    async loadCoursePreview(taskId) {
        try {
            const response = await fetch(`/api/course-preview/${taskId}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '加载预览失败');
            this.renderCoursePreview(taskId, data.pages || []);
        } catch (error) {
            this.showStatus('error', error.message);
        }
    }

    renderCoursePreview(taskId, pages) {
        const { coursePreviewModule, coursePreviewPages, coursePreviewSaveState } = this.elements;
        this.elements.continueCourseBtn.disabled = false;
        coursePreviewModule.dataset.taskId = taskId;
        coursePreviewPages.innerHTML = '';
        pages.forEach(page => {
            const card = document.createElement('article');
            card.className = 'course-preview-page';
            card.dataset.pageNumber = page.page_number;
            card.innerHTML = `
                <img class="course-preview-image" src="${page.image_url}" alt="第 ${page.page_number} 页">
                <div class="course-preview-editor">
                    <div class="course-preview-page-title">第 ${page.page_number} 页 · ${this._esc(page.title || '')}</div>
                    <textarea class="course-preview-script" aria-label="第 ${page.page_number} 页讲稿">${this._esc(page.script || '')}</textarea>
                </div>
            `;
            card.querySelector('textarea').addEventListener('input', () => {
                coursePreviewSaveState.textContent = '有未保存修改';
                coursePreviewSaveState.classList.remove('saved');
            });
            coursePreviewPages.appendChild(card);
        });
        coursePreviewSaveState.textContent = '';
        coursePreviewModule.hidden = false;
        coursePreviewModule.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    collectPreviewScripts() {
        return Array.from(this.elements.coursePreviewPages.querySelectorAll('.course-preview-page')).map(card => ({
            page_number: Number(card.dataset.pageNumber),
            script: card.querySelector('.course-preview-script').value
        }));
    }

    async savePreviewScripts() {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        if (!taskId) return false;
        const response = await fetch(`/api/course-preview/${taskId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pages: this.collectPreviewScripts() })
        });
        const data = await response.json();
        if (!response.ok) {
            this.showStatus('error', data.error || '保存讲稿失败');
            return false;
        }
        this.elements.coursePreviewSaveState.textContent = '已保存';
        this.elements.coursePreviewSaveState.classList.add('saved');
        return true;
    }

    async continueCourse() {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        const found = this.getItemByTaskId(taskId);
        if (!taskId || !found) return;
        const button = this.elements.continueCourseBtn;
        button.disabled = true;
        try {
            const response = await fetch(`/api/course-continue/${taskId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pages: this.collectPreviewScripts() })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '继续生成失败');
            this.updateItem(found.index, {
                status: 'processing',
                stage: 'tts',
                percentage: 50,
                message: '正在生成配音'
            });
            this.elements.coursePreviewModule.hidden = true;
            this.renderFileList();
            this.renderResultsGrid();
            this.startProgressStream(taskId);
        } catch (error) {
            button.disabled = false;
            this.showStatus('error', error.message);
        }
    }

    // ── Slides ─────────────────────────────────────────
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
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new AICourseStudioApp();
});
