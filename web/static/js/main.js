/* ==========================================================================
   AI Course Studio - 主JavaScript文件
   ========================================================================== */

class AICourseStudioApp {
    constructor() {
        this.state = {
            files: [],  // [{file, filePath, fileName, taskId, status, percentage, stage, message, videoPath, error}]
            isUploading: false,
            isConverting: false,
            activeBatchId: null,
            logoPath: null,
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
        this.voicePreviewAudio = null;
        this.activeVoicePreviewButton = null;

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
                selectAllFiles: document.getElementById('select-all-files'),
                applyStrategyBtn: document.getElementById('apply-strategy-btn'),

                ttsEngine: document.getElementById('tts-engine'),
                voiceSelect: document.getElementById('voice-select'),
                voicePreviewList: document.getElementById('voice-preview-list'),
                customVoice: document.getElementById('custom-voice'),
                renderEngine: document.getElementById('render-engine'),

                llmEnabled: document.getElementById('llm-enabled'),
                llmEngine: document.getElementById('llm-engine'),
                llmModeGroup: document.getElementById('llm-mode-group'),
                llmMode: document.getElementById('llm-mode'),
                refinementLevel: document.getElementById('refinement-level'),
                illustrationsEnabled: document.getElementById('illustrations-enabled'),
                maxIllustrations: document.getElementById('max-illustrations'),
                pptFooterText: document.getElementById('ppt-footer-text'),
                schoolLogoInput: document.getElementById('school-logo-input'),
                schoolLogoButton: document.getElementById('school-logo-button'),
                schoolLogoPreview: document.getElementById('school-logo-preview'),
                schoolLogoImage: document.getElementById('school-logo-image'),
                schoolLogoRemove: document.getElementById('school-logo-remove'),
                schoolLogoHint: document.getElementById('school-logo-hint'),

                convertBtn: document.getElementById('convert-btn'),
                renderBtn: document.getElementById('render-btn'),
                convertStatus: document.getElementById('convert-status'),
                statusIcon: document.getElementById('status-icon'),
                statusText: document.getElementById('status-text'),

                batchSummary: document.getElementById('batch-summary'),
                batchCount: document.getElementById('batch-count'),
                batchProgressFill: document.getElementById('batch-progress-fill'),

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
                cancelCourseBtn: document.getElementById('cancel-course-btn'),
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
        this.taskRefreshTimer = setInterval(() => this.reconcileTasks(), 5000);
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

        this.elements.schoolLogoButton.addEventListener(
            'click', () => this.elements.schoolLogoInput.click()
        );
        this.elements.schoolLogoInput.addEventListener('change', (event) => {
            const logo = event.target.files[0];
            if (logo) this.uploadSchoolLogo(logo);
            event.target.value = '';
        });
        this.elements.schoolLogoRemove.addEventListener('click', () => {
            this.state.logoPath = null;
            this.elements.schoolLogoPreview.hidden = true;
            this.elements.schoolLogoImage.removeAttribute('src');
            this.elements.schoolLogoHint.textContent =
                '支持 PNG/JPG/WebP，生成时按每页版式自动调整位置与大小';
        });

        convertBtn.addEventListener('click', () => this.handleConvert());
        renderBtn.addEventListener('click', () => this.handleRender());
        ttsEngine.addEventListener('change', () => this.loadVoices());

        const { llmEnabled } = this.elements;
        llmEnabled.addEventListener('change', () => this.toggleLLMMode());

        const { slidesToggle } = this.elements;
        slidesToggle.addEventListener('click', () => this.toggleSlides());
        this.elements.cancelCourseBtn.addEventListener('click', () => this.cancelCourse());
        this.elements.saveScriptsBtn.addEventListener('click', () => this.savePreviewScripts());
        this.elements.continueCourseBtn.addEventListener('click', () => this.continueCourse());
        this.elements.selectAllFiles.addEventListener('change', (event) => {
            this.state.files.forEach(item => {
                if (item.status === 'pending') item.selected = event.target.checked;
            });
            this.renderFileList();
        });
        this.elements.applyStrategyBtn.addEventListener(
            'click', () => this.applyStrategyToSelected()
        );

    }

    async uploadSchoolLogo(file) {
        const allowedExtensions = ['.png', '.jpg', '.jpeg', '.webp'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!allowedExtensions.includes(ext)) {
            alert('Logo 仅支持 PNG、JPG 或 WebP 图片');
            return;
        }
        const formData = new FormData();
        formData.append('logo', file);
        this.elements.schoolLogoButton.disabled = true;
        this.elements.schoolLogoHint.textContent = 'Logo 上传中...';
        try {
            const response = await fetch('/api/logo-upload', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Logo 上传失败');
            this.state.logoPath = result.logo_path;
            this.elements.schoolLogoImage.src = URL.createObjectURL(file);
            this.elements.schoolLogoPreview.hidden = false;
            this.elements.schoolLogoHint.textContent =
                '已上传，Logo 将根据封面、正文和小结版式自动适配';
        } catch (error) {
            this.state.logoPath = null;
            this.elements.schoolLogoHint.textContent = error.message;
            alert(error.message);
        } finally {
            this.elements.schoolLogoButton.disabled = false;
        }
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
        const { ttsEngine, voiceSelect, voicePreviewList } = this.elements;
        this.stopVoicePreview();
        voiceSelect.disabled = true;
        voiceSelect.innerHTML = '<option value="">正在加载对应厂商音色...</option>';
        voicePreviewList.innerHTML = '<div class="voice-list-message">正在加载音色...</div>';
        try {
            const engine = ttsEngine.value;
            const response = await fetch(`/api/voices?engine=${encodeURIComponent(engine)}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '加载音色失败');
            const voiceList = data.voices || [];
            voiceSelect.innerHTML = '';
            voiceList.forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.id;
                option.textContent = `${voice.name} · ${voice.id}`;
                voiceSelect.appendChild(option);
            });
            this.renderVoicePreviewList(engine, voiceList);
            if (!voiceList.length) {
                voiceSelect.innerHTML = '<option value="">无公共音色，请输入专属音色 ID</option>';
            }
        } catch (error) {
            console.error('加载语音列表失败:', error);
            voiceSelect.innerHTML = '<option value="">加载失败，请输入专属音色 ID</option>';
            voicePreviewList.innerHTML = '<div class="voice-list-message">音色加载失败，请使用专属音色 ID</div>';
        } finally {
            voiceSelect.disabled = false;
        }
    }

    renderVoicePreviewList(engine, voices) {
        const { voicePreviewList, voiceSelect } = this.elements;
        voicePreviewList.innerHTML = '';
        if (!voices.length) {
            voicePreviewList.innerHTML = '<div class="voice-list-message">暂无公共音色</div>';
            return;
        }
        voices.forEach((voice, index) => {
            const item = document.createElement('div');
            item.className = `voice-preview-item${index === 0 ? ' selected' : ''}`;
            item.setAttribute('role', 'option');
            item.setAttribute('aria-selected', index === 0 ? 'true' : 'false');
            item.innerHTML = `
                <button type="button" class="voice-play-btn"
                        aria-label="试听 ${this._esc(voice.name)}" title="试听音色">▶</button>
                <span>
                    <span class="voice-preview-name">${this._esc(voice.name)}</span>
                    <span class="voice-preview-id">${this._esc(voice.id)}</span>
                </span>
            `;
            item.addEventListener('click', (event) => {
                this.selectVoiceItem(item, voice.id);
                if (event.target.closest('.voice-play-btn')) {
                    this.playVoicePreview(
                        engine, voice.id, item.querySelector('.voice-play-btn')
                    );
                }
            });
            voicePreviewList.appendChild(item);
        });
        voiceSelect.value = voices[0].id;
    }

    selectVoiceItem(item, voiceId) {
        this.elements.voiceSelect.value = voiceId;
        this.elements.customVoice.value = '';
        this.elements.voicePreviewList.querySelectorAll('.voice-preview-item').forEach(row => {
            const selected = row === item;
            row.classList.toggle('selected', selected);
            row.setAttribute('aria-selected', selected ? 'true' : 'false');
        });
    }

    stopVoicePreview() {
        if (this.voicePreviewAudio) {
            this.voicePreviewAudio.pause();
            this.voicePreviewAudio.src = '';
            this.voicePreviewAudio = null;
        }
        if (this.activeVoicePreviewButton) {
            this.activeVoicePreviewButton.textContent = '▶';
            this.activeVoicePreviewButton.classList.remove('loading');
            this.activeVoicePreviewButton.disabled = false;
            this.activeVoicePreviewButton = null;
        }
    }

    async playVoicePreview(engine, voice, button) {
        if (this.activeVoicePreviewButton === button && this.voicePreviewAudio) {
            this.stopVoicePreview();
            return;
        }
        this.stopVoicePreview();
        this.activeVoicePreviewButton = button;
        button.textContent = '…';
        button.classList.add('loading');
        button.disabled = true;
        try {
            const response = await fetch('/api/voice-preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ engine, voice })
            });
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || '试听音频生成失败');
            }
            const audioUrl = URL.createObjectURL(await response.blob());
            const audio = new Audio(audioUrl);
            this.voicePreviewAudio = audio;
            button.disabled = false;
            button.classList.remove('loading');
            button.textContent = '■';
            audio.addEventListener('ended', () => {
                URL.revokeObjectURL(audioUrl);
                this.stopVoicePreview();
            }, { once: true });
            audio.addEventListener('error', () => {
                URL.revokeObjectURL(audioUrl);
                this.stopVoicePreview();
                this.showStatus('error', '试听音频播放失败');
            }, { once: true });
            await audio.play();
        } catch (error) {
            this.stopVoicePreview();
            this.showStatus('error', error.message);
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
            error: null,
            selected: true,
            strategy: null,
            strategySource: 'batch',
            queuePosition: null
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
                ${item.status === 'pending' ? `
                    <label class="file-list-select" title="选择批量应用策略">
                        <input type="checkbox" class="file-select-checkbox"
                               ${item.selected !== false ? 'checked' : ''}>
                    </label>` : ''}
                <svg class="file-list-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
                <span class="file-list-name" title="${this._esc(item.fileName)}">${this._esc(item.fileName)}</span>
                <span class="file-list-status status-${item.status}">${statusText}</span>
                ${item.status === 'pending' ? `
                    <span class="file-strategy-badge">
                        ${item.strategySource === 'single' ? '单独策略' : '批量策略'}
                    </span>
                    <button type="button" class="file-strategy-button"
                            title="把当前生成策略只应用到此文件">仅配置此项</button>` : ''}
                ${showMiniProgress ? `<div class="mini-progress-bar"><div class="mini-progress-fill" style="width:${item.percentage}%"></div></div>` : ''}
                <button class="file-list-remove" data-index="${index}" title="移除">&times;</button>
            `;

            row.querySelector('.file-list-remove').addEventListener('click', () => this.removeFile(index));
            const checkbox = row.querySelector('.file-select-checkbox');
            if (checkbox) {
                checkbox.addEventListener('change', (event) => {
                    item.selected = event.target.checked;
                    this._syncSelectAll();
                });
            }
            const strategyButton = row.querySelector('.file-strategy-button');
            if (strategyButton) {
                strategyButton.addEventListener('click', () => {
                    item.strategy = this.collectCurrentStrategy();
                    item.strategySource = 'single';
                    item.selected = false;
                    this.renderFileList();
                    this.showStatus('success', `已为“${item.fileName}”保存单独策略`);
                });
            }
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
        this._syncSelectAll();
    }

    _syncSelectAll() {
        const pending = this.state.files.filter(item => item.status === 'pending');
        this.elements.selectAllFiles.checked =
            pending.length > 0 && pending.every(item => item.selected !== false);
        this.elements.selectAllFiles.indeterminate =
            pending.some(item => item.selected !== false)
            && !this.elements.selectAllFiles.checked;
    }

    collectCurrentStrategy() {
        return {
            tts_engine: this.elements.ttsEngine.value,
            voice: this.elements.customVoice.value.trim() || this.elements.voiceSelect.value,
            render_engine: this.elements.renderEngine.value,
            llm_enabled: this.elements.llmEnabled.checked,
            llm_engine: this.elements.llmEngine.value,
            llm_mode: this.elements.llmMode.value,
            refinement_level: this.elements.refinementLevel.value,
            illustrations_enabled: this.elements.illustrationsEnabled.checked,
            max_illustrations: Number(this.elements.maxIllustrations.value),
            ppt_footer_text: this.elements.pptFooterText.value.trim(),
            school_logo_path: this.state.logoPath
        };
    }

    applyStrategyToSelected() {
        const strategy = this.collectCurrentStrategy();
        let count = 0;
        this.state.files.forEach(item => {
            if (item.status === 'pending' && item.selected !== false) {
                item.strategy = { ...strategy };
                item.strategySource = 'batch';
                count += 1;
            }
        });
        this.renderFileList();
        this.showStatus(
            count ? 'success' : 'error',
            count ? `当前策略已应用到 ${count} 个文件` : '请先勾选待处理文件'
        );
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
            case 'queued':
                return item.queuePosition
                    ? `排队中 · 第 ${item.queuePosition} 位`
                    : '排队中';
            case 'interrupted': return '服务重启后待重新提交';
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
    async removeFile(index) {
        const item = this.state.files[index];
        if (
            item?.taskId
            && ['completed', 'error', 'interrupted', 'awaiting_confirmation'].includes(item.status)
        ) {
            await this.deleteTask(index);
            return;
        }
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
        const batchId = (
            globalThis.crypto?.randomUUID?.()
            || `batch-${Date.now()}-${Math.random().toString(16).slice(2)}`
        );
        this.state.activeBatchId = batchId;
        const defaultStrategy = this.collectCurrentStrategy();

        await Promise.all(pending.map(async (item) => {
            const index = this.state.files.indexOf(item);
            this.updateItem(index, { status: 'queued', message: '排队中' });
            this.renderFileList();
            this.updateBatchSummary();

            try {
                const strategy = item.strategy || defaultStrategy;
                const response = await fetch('/api/convert', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        file_path: item.filePath,
                        original_name: item.fileName,
                        batch_id: batchId,
                        strategy_source: item.strategySource || 'batch',
                        ...strategy
                    })
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || '转换失败');
                }

                const result = await response.json();
                this.updateItem(index, {
                    taskId: result.task_id,
                    status: 'queued',
                    message: result.message || '已进入生产队列'
                });
                this.renderFileList();
                this.renderResultsGrid();
                this.updateBatchSummary();
                this.startProgressStream(result.task_id);
            } catch (error) {
                const idx = this.state.files.indexOf(item);
                if (idx >= 0) {
                    this.updateItem(idx, { status: 'error', error: error.message, message: error.message });
                    this.renderFileList();
                    this.renderResultsGrid();
                    this.updateBatchSummary();
                }
            }
        }));

        this.state.isConverting = false;
        this._refreshButtons();
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
                        {
                            const percentage = Number(data.percentage ?? item.percentage ?? 0);
                            const message = data.message || `${this.stageNames[data.stage] || data.stage}...`;
                            const completedStages = [...(item.completedStages || [])];
                            if (
                                item.stage
                                && item.stage !== data.stage
                                && !completedStages.includes(item.stage)
                            ) {
                                completedStages.push(item.stage);
                            }
                            this.updateItem(index, {
                                status: 'processing',
                                stage: data.stage,
                                percentage,
                                message,
                                completedStages
                            });
                        }
                        this.renderFileList();
                        this.renderResultsGrid();
                        this.updateBatchSummary();
                        break;

                    case 'progress': {
                        const percentage = data.percentage || 0;
                        const message = data.message || (data.stage ? `${this.stageNames[data.stage] || data.stage} (${data.current}/${data.total})` : '');
                        this.updateItem(index, { percentage, stage: data.stage || item.stage, message });
                        this.renderFileList();
                        this.renderResultsGrid();
                        this.updateBatchSummary();
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

                    case 'rollback':
                        eventSource.close();
                        this.state.activeEventSources.delete(taskId);
                        this.updateItem(index, {
                            status: 'awaiting_confirmation',
                            percentage: 50,
                            stage: 'preview',
                            error: data.message,
                            message: `${data.failed_stage || '生成'}失败，已退回上一步`,
                            courseJsonPath: data.course_json_path || item.courseJsonPath,
                            presentationPath: data.presentation_path || item.presentationPath
                        });
                        this.renderFileList();
                        this.renderResultsGrid();
                        this.updateBatchSummary();
                        this.state.isConverting = false;
                        this._refreshButtons();
                        this.showStatus(
                            'error',
                            `${data.failed_stage || '生成'}失败：${data.message}。已保留成果，可调整后重试。`
                        );
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

        const current = this.getItemByTaskId(taskId);
        if (current) {
            this.updateItem(current.index, { message: '进度连接中断，正在重新连接...' });
            this.renderResultsGrid();
        }

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
    _renderCardProgress(item) {
        const stages = ['init', 'extract', 'render', 'llm', 'tts', 'video'];
        const completed = new Set(item.completedStages || []);
        const activeIndex = stages.indexOf(item.stage);
        const percentage = Math.max(0, Math.min(100, Number(item.percentage) || 0));
        const message = item.message
            || (item.status === 'queued' ? '排队中...' : `${this.stageNames[item.stage] || '准备'}中...`);
        const steps = stages.map((stage, index) => {
            const isCompleted = completed.has(stage) || (activeIndex > index);
            const stateClass = item.stage === stage
                ? 'active'
                : isCompleted ? 'completed' : '';
            return `
                <div class="card-progress-step ${stateClass}">
                    <span class="card-progress-dot"></span>
                    <span>${this._esc(this.stageNames[stage])}</span>
                </div>
            `;
        }).join('');

        return `
            <div class="card-progress">
                <div class="card-progress-heading">
                    <span>${this._esc(message)}</span>
                    <strong>${Math.round(percentage)}%</strong>
                </div>
                <div class="card-progress-track">
                    <div class="card-progress-fill" style="width:${percentage}%"></div>
                </div>
                <div class="card-progress-steps">${steps}</div>
            </div>
        `;
    }

    renderResultsGrid() {
        const container = this.elements.resultsGrid;
        container.innerHTML = '';

        let hasVisible = false;

        this.state.files.forEach((item, index) => {
            if (!['awaiting_confirmation', 'completed', 'processing', 'queued', 'error', 'interrupted'].includes(item.status)) return;
            hasVisible = true;

            const card = document.createElement('div');
            card.className = 'result-card';
            if (item.status === 'error') card.classList.add('error-card');

            if (item.status === 'awaiting_confirmation') {
                card.innerHTML = `
                    <div class="result-video-wrap">
                        ${this._deleteTaskButton(item)}
                        <div class="result-placeholder"><p>等待确认逐页讲稿</p></div>
                    </div>
                    <div class="result-card-footer">
                        <span class="result-card-name" title="${this._esc(item.fileName)}">${this._esc(item.fileName)}</span>
                    </div>
                    <button class="result-card-download preview-open-btn" data-index="${index}">编辑讲稿</button>
                `;
                card.querySelector('.preview-open-btn').addEventListener('click', () => this.loadCoursePreview(item.taskId));
                card.querySelector('.result-card-delete').addEventListener('click', () => this.deleteTask(index));
            } else if (item.status === 'completed' && item.videoPath) {
                const artifacts = this._artifactLinks(item);
                card.innerHTML = `
                    <div class="result-video-wrap">
                        ${this._deleteTaskButton(item)}
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
                card.querySelector('.result-card-delete').addEventListener('click', () => this.deleteTask(index));
            } else if (item.status === 'completed') {
                card.innerHTML = `
                    <div class="result-video-wrap">
                        ${this._deleteTaskButton(item)}
                        <div class="result-placeholder"><p>课程文件已生成</p></div>
                    </div>
                    <div class="result-card-footer">
                        <span class="result-card-name">${this._esc(item.fileName)}</span>
                    </div>
                    ${this._artifactLinks(item)}
                `;
                card.querySelector('.result-card-delete').addEventListener('click', () => this.deleteTask(index));
            } else {
                const placeholderText = item.status === 'error'
                    ? this._esc(item.error || '转换失败')
                    : item.status === 'queued'
                        ? '排队中...'
                        : '转换中...';

                card.innerHTML = `
                    <div class="result-video-wrap">
                        ${['error', 'interrupted'].includes(item.status) ? this._deleteTaskButton(item) : ''}
                        <div class="result-placeholder">
                            ${item.status !== 'error' ? '<div class="spinner"></div>' : ''}
                            <p>${placeholderText}</p>
                            ${item.status !== 'error' ? this._renderCardProgress(item) : ''}
                        </div>
                    </div>
                    <div class="result-card-footer">
                        <span class="result-card-name" title="${this._esc(item.fileName)}">${this._esc(item.fileName)}</span>
                        ${['processing', 'queued'].includes(item.status) && item.taskId
                            ? `<button class="result-card-stop" data-task-id="${item.taskId}">停止</button>`
                            : ''}
                    </div>
                `;
                const stopButton = card.querySelector('.result-card-stop');
                if (stopButton) {
                    stopButton.addEventListener('click', () => this.stopTask(item.taskId));
                }
                const deleteButton = card.querySelector('.result-card-delete');
                if (deleteButton) {
                    deleteButton.addEventListener('click', () => this.deleteTask(index));
                }
            }

            container.appendChild(card);
        });

        this.elements.resultsModule.hidden = !hasVisible;
    }

    _deleteTaskButton(item) {
        if (
            !item.taskId
            || !['completed', 'error', 'interrupted', 'awaiting_confirmation'].includes(item.status)
        ) return '';
        return `
            <button class="result-card-delete" type="button"
                    data-task-id="${this._esc(item.taskId)}" title="物理删除课程产物"
                    aria-label="删除 ${this._esc(item.fileName)}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6l-1 14H6L5 6"></path>
                    <path d="M10 11v6M14 11v6"></path>
                    <path d="M9 6V4h6v2"></path>
                </svg>
            </button>
        `;
    }

    async deleteTask(index) {
        const item = this.state.files[index];
        if (
            !item?.taskId
            || !['completed', 'error', 'interrupted', 'awaiting_confirmation'].includes(item.status)
        ) return;
        const confirmed = window.confirm(
            `确定物理删除“${item.fileName}”吗？\n\n该任务生成的 PPT、视频、字幕、音频和中间文件都将永久删除，且无法恢复。`
        );
        if (!confirmed) return;

        const button = this.elements.resultsGrid.querySelector(
            `.result-card-delete[data-task-id="${CSS.escape(item.taskId)}"]`
        );
        if (button) button.disabled = true;
        try {
            const response = await fetch(`/api/tasks/${item.taskId}`, {
                method: 'DELETE'
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '删除失败');
            this.state.files.splice(index, 1);
            this.renderFileList();
            this.renderResultsGrid();
            this.updateBatchSummary();
            this.showStatus('success', data.message || '课程产物已删除');
        } catch (error) {
            if (button) button.disabled = false;
            this.showStatus('error', error.message);
        }
    }

    async stopTask(taskId) {
        if (!taskId || !window.confirm('停止后将退回讲稿确认，并保留已生成成果。确认停止？')) {
            return;
        }
        const found = this.getItemByTaskId(taskId);
        if (found) {
            this.updateItem(found.index, { message: '正在停止生成，请稍候…' });
            this.renderFileList();
            this.renderResultsGrid();
        }
        const cardButton = document.querySelector(
            `.result-card-stop[data-task-id="${CSS.escape(taskId)}"]`
        );
        if (cardButton) cardButton.disabled = true;
        try {
            const response = await fetch(`/api/stop/${taskId}`, { method: 'POST' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '停止失败');
            this.showStatus('success', data.message);
        } catch (error) {
            if (cardButton) cardButton.disabled = false;
            this.showStatus('error', error.message);
        }
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
                    filePath: t.file_path || null,
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
                    error: t.error || null,
                    queuePosition: t.queue_position || null,
                    selected: false,
                    strategy: t.strategy || null,
                    strategySource: t.strategy_source || 'batch'
                }));

                this.renderFileList();
                this.renderResultsGrid();
                this.updateBatchSummary();

                // Reconnect SSE for processing tasks
                for (const item of this.state.files) {
                    if (['processing', 'queued'].includes(item.status) && item.taskId) {
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

    async reconcileTasks() {
        try {
            const response = await fetch('/api/tasks');
            if (!response.ok) return;
            const data = await response.json();
            for (const task of data.tasks || []) {
                const found = this.getItemByTaskId(task.task_id);
                if (!found) continue;
                this.updateItem(found.index, {
                    status: task.status,
                    stage: task.stage,
                    percentage: task.percentage || 0,
                    message: task.message || '',
                    videoPath: task.video_path,
                    error: task.error,
                    queuePosition: task.queue_position || null,
                    strategy: task.strategy || found.item.strategy,
                    strategySource: task.strategy_source || found.item.strategySource
                });
            }
            this.renderFileList();
            this.renderResultsGrid();
            this.updateBatchSummary();
        } catch (error) {
            console.debug('任务状态轮询暂时不可用:', error);
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
                body: JSON.stringify({
                    pages: this.collectPreviewScripts(),
                    tts_engine: this.elements.ttsEngine.value,
                    voice: (
                        this.elements.customVoice.value.trim()
                        || this.elements.voiceSelect.value
                    )
                })
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

    async cancelCourse() {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        const found = this.getItemByTaskId(taskId);
        if (!taskId || !found) return;

        const button = this.elements.cancelCourseBtn;
        button.disabled = true;
        try {
            const response = await fetch(`/api/course-cancel/${taskId}`, {
                method: 'POST'
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '取消失败');

            this.updateItem(found.index, {
                taskId: null,
                status: 'pending',
                percentage: 0,
                stage: null,
                message: '请调整生成策略后重新生成',
                courseJsonPath: null,
                presentationPath: null,
                subtitlesPath: null,
                previewPath: null,
                videoPath: null,
                error: null
            });
            this.elements.coursePreviewModule.hidden = true;
            delete this.elements.coursePreviewModule.dataset.taskId;
            this.renderFileList();
            this.renderResultsGrid();
            this.updateBatchSummary();
            this.showStatus('success', '已取消本次生成，请调整生成策略后重新提交');
            document.getElementById('options-module').scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        } catch (error) {
            this.showStatus('error', error.message);
        } finally {
            button.disabled = false;
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
