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
        this.voiceFavoritesStorageKey = 'vidppt.voiceFavorites.v1';
        this.strategyDraftStorageKey = 'vidppt.currentStrategy.v1';
        this.voiceFavorites = this.loadVoiceFavorites();
        this.pendingVoiceSelection = null;
        this.previewAutoSaveTimer = null;
        this.previewSaveSequence = 0;
        this.currentPreviewPage = 1;
        this.smartCutSegments = [];
        this.smartCutApplied = false;
        this.coursePreviewAudio = null;
        this.coursePreviewPlaying = false;
        this.coursePreviewSubtitlePage = null;

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
                routeSummary: document.getElementById('route-summary'),
                routeSummaryIcon: document.getElementById('route-summary-icon'),
                routeSummaryTitle: document.getElementById('route-summary-title'),
                routeSummaryDescription: document.getElementById('route-summary-description'),

                ttsEngine: document.getElementById('tts-engine'),
                voiceSelect: document.getElementById('voice-select'),
                voicePreviewList: document.getElementById('voice-preview-list'),
                customVoice: document.getElementById('custom-voice'),
                volcengineExpressionGroup: document.getElementById('volcengine-expression-group'),
                ttsEmotion: document.getElementById('tts-emotion'),
                ttsRate: document.getElementById('tts-rate'),
                ttsEmotionScale: document.getElementById('tts-emotion-scale'),
                ttsSentencePause: document.getElementById('tts-sentence-pause'),
                burnSubtitles: document.getElementById('burn-subtitles'),
                subtitleStyleTemplate: document.getElementById('subtitle-style-template'),
                subtitlePreset: document.getElementById('subtitle-preset'),
                subtitleX: document.getElementById('subtitle-x'),
                subtitleY: document.getElementById('subtitle-y'),
                subtitleWidth: document.getElementById('subtitle-width'),
                subtitleHeight: document.getElementById('subtitle-height'),
                subtitleFontSize: document.getElementById('subtitle-font-size'),
                subtitleFontName: document.getElementById('subtitle-font-name'),
                subtitleFontPreview: document.getElementById('subtitle-font-preview'),
                subtitleColor: document.getElementById('subtitle-color'),
                subtitleBackgroundColor: document.getElementById('subtitle-background-color'),
                subtitleBackgroundOpacity: document.getElementById('subtitle-background-opacity'),
                subtitleOutlineWidth: document.getElementById('subtitle-outline-width'),
                subtitleOutlineColor: document.getElementById('subtitle-outline-color'),
                renderEngine: document.getElementById('render-engine'),

                llmEnabled: document.getElementById('llm-enabled'),
                llmEngine: document.getElementById('llm-engine'),
                llmModeGroup: document.getElementById('llm-mode-group'),
                llmMode: document.getElementById('llm-mode'),
                refinementLevel: document.getElementById('refinement-level'),
                visualTheme: document.getElementById('visual-theme'),
                illustrationsEnabled: document.getElementById('illustrations-enabled'),
                maxIllustrations: document.getElementById('max-illustrations'),
                pptFooterText: document.getElementById('ppt-footer-text'),
                schoolLogoInput: document.getElementById('school-logo-input'),
                schoolLogoButton: document.getElementById('school-logo-button'),
                schoolLogoPreview: document.getElementById('school-logo-preview'),
                schoolLogoImage: document.getElementById('school-logo-image'),
                schoolLogoRemove: document.getElementById('school-logo-remove'),
                schoolLogoHint: document.getElementById('school-logo-hint'),
                advancedToggle: document.getElementById('advanced-toggle'),
                workflowBadge: document.getElementById('workflow-badge'),
                workflowDescription: document.getElementById('workflow-description'),
                strategyTemplateSelect: document.getElementById('strategy-template-select'),
                saveTemplateBtn: document.getElementById('save-template-btn'),
                deleteTemplateBtn: document.getElementById('delete-template-btn'),

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
                coursePreviewPosition: document.getElementById('course-preview-position'),
                previewPreviousBtn: document.getElementById('preview-previous-btn'),
                previewNextBtn: document.getElementById('preview-next-btn'),
                previewPageSelect: document.getElementById('preview-page-select'),
                unreviewedOnly: document.getElementById('unreviewed-only'),
                cutDurationMinutes: document.getElementById('cut-duration-minutes'),
                smartCutRecommendBtn: document.getElementById('smart-cut-recommend-btn'),
                smartCutApplyBtn: document.getElementById('smart-cut-apply-btn'),
                smartCutList: document.getElementById('smart-cut-list'),
                smartCutSummary: document.getElementById('smart-cut-summary'),
                courseDurationEstimate: document.getElementById('course-duration-estimate'),
                courseDurationTotal: document.getElementById('course-duration-total'),
                courseDurationSegments: document.getElementById('course-duration-segments'),
                downloadEditablePptBtn: document.getElementById('download-editable-ppt-btn'),
                uploadEditedPptBtn: document.getElementById('upload-edited-ppt-btn'),
                editedPptInput: document.getElementById('edited-ppt-input'),
                cancelCourseBtn: document.getElementById('cancel-course-btn'),
                saveScriptsBtn: document.getElementById('save-scripts-btn'),
                continueCourseBtn: document.getElementById('continue-course-btn'),
                metricTotal: document.getElementById('metric-total'),
                metricProcessing: document.getElementById('metric-processing'),
                metricReview: document.getElementById('metric-review'),
                metricCompleted: document.getElementById('metric-completed'),
                assetTableBody: document.getElementById('asset-table-body'),
                operationLogBody: document.getElementById('operation-log-body')
            };
        } catch(e) {
            console.error('AICourseStudio element init failed:', e);
        }

        this.init();
    }

    init() {
        this.bindEvents();
        this.bindSubtitleControls();
        this.loadSubtitleFonts();
        this.restoreCurrentStrategy();
        this.loadStrategyTemplates();
        this.loadVoices({ preferredVoice: this.pendingVoiceSelection });
        this.restoreTasks().then(() => this.openRequestedPreviewTask());
        this.loadOperationLogs();
        this.taskRefreshTimer = setInterval(() => this.reconcileTasks(), 5000);
    }

    // ── State helpers ──────────────────────────────────
    getItemByTaskId(taskId) {
        const idx = this.state.files.findIndex(f => f.taskId === taskId);
        return idx >= 0 ? { index: idx, item: this.state.files[idx] } : null;
    }

    updateItem(index, patch) {
        const item = this.state.files[index];
        const changed = Object.entries(patch).some(([key, value]) =>
            !this._stateValueEquals(item[key], value)
        );
        if (changed) Object.assign(item, patch);
        return changed;
    }

    _stateValueEquals(left, right) {
        if (left === right) return true;
        if (
            left
            && right
            && typeof left === 'object'
            && typeof right === 'object'
        ) {
            try {
                return JSON.stringify(left) === JSON.stringify(right);
            } catch {
                return false;
            }
        }
        return false;
    }

    _taskStatus(status) {
        return ['pending', 'processing'].includes(status) ? 'processing' : status;
    }

    requestedPreviewTaskId() {
        try {
            return new URLSearchParams(window.location.search).get('preview_task') || '';
        } catch {
            return '';
        }
    }

    async openRequestedPreviewTask() {
        const taskId = this.requestedPreviewTaskId();
        if (!taskId) return;
        await this.loadCoursePreview(taskId);
    }

    // ── Strategy draft persistence ─────────────────────
    bindStrategyPersistence() {
        const controls = [
            this.elements.voiceSelect,
            this.elements.customVoice,
            this.elements.ttsEmotion,
            this.elements.ttsRate,
            this.elements.ttsEmotionScale,
            this.elements.ttsSentencePause,
            this.elements.burnSubtitles,
            this.elements.subtitleX,
            this.elements.subtitleY,
            this.elements.subtitleWidth,
            this.elements.subtitleHeight,
            this.elements.subtitleFontSize,
            this.elements.subtitleFontName,
            this.elements.subtitleColor,
            this.elements.subtitleBackgroundColor,
            this.elements.subtitleBackgroundOpacity,
            this.elements.subtitleOutlineWidth,
            this.elements.subtitleOutlineColor,
            this.elements.renderEngine,
            this.elements.llmEnabled,
            this.elements.llmEngine,
            this.elements.llmMode,
            this.elements.refinementLevel,
            this.elements.visualTheme,
            this.elements.illustrationsEnabled,
            this.elements.maxIllustrations,
            this.elements.pptFooterText
        ];
        controls.forEach(control => {
            if (!control) return;
            const eventName = control.tagName === 'INPUT' && control.type === 'text'
                ? 'input'
                : 'change';
            control.addEventListener(eventName, () => {
                if (control === this.elements.customVoice && control.value.trim()) {
                    this.elements.voicePreviewList
                        .querySelectorAll('.voice-preview-item')
                        .forEach(row => {
                            row.classList.remove('selected');
                            row.setAttribute('aria-selected', 'false');
                        });
                }
                if (control === this.elements.llmEnabled) this.toggleLLMMode();
                this.saveCurrentStrategy();
            });
        });
    }

    bindSubtitleControls() {
        this.subtitlePresets = {
            course: { x: 96, y: 900, width: 1728, height: 110, fontSize: 46 },
            compact: { x: 160, y: 955, width: 1600, height: 70, fontSize: 42 },
            safe: { x: 160, y: 805, width: 1600, height: 110, fontSize: 44 },
            top: { x: 160, y: 80, width: 1600, height: 110, fontSize: 44 },
            lowerMiddle: { x: 160, y: 720, width: 1600, height: 110, fontSize: 44 }
        };
        this.subtitleStyleTemplates = {
            standard: {
                label: '标准网课 · 黑底白字',
                fontName: 'Noto Sans CJK SC',
                fontSize: 46,
                color: '#ffffff',
                backgroundColor: '#111111',
                backgroundOpacity: 0.55,
                outlineWidth: 0,
                outlineColor: '#000000'
            },
            lightSlide: {
                label: '浅色课件 · 深字浅底',
                fontName: 'Noto Sans CJK SC',
                fontSize: 46,
                color: '#172033',
                backgroundColor: '#ffffff',
                backgroundOpacity: 0.82,
                outlineWidth: 0,
                outlineColor: '#ffffff'
            },
            darkSlide: {
                label: '深色课件 · 高对比描边',
                fontName: 'Noto Sans CJK SC',
                fontSize: 46,
                color: '#ffffff',
                backgroundColor: '#000000',
                backgroundOpacity: 0.38,
                outlineWidth: 2,
                outlineColor: '#000000'
            },
            lectureSerif: {
                label: '理论讲授 · 宋体稳重',
                fontName: 'Noto Serif CJK SC',
                fontSize: 48,
                color: '#ffffff',
                backgroundColor: '#182033',
                backgroundOpacity: 0.62,
                outlineWidth: 1,
                outlineColor: '#000000'
            },
            codeDemo: {
                label: '实操录屏 · 小框清晰',
                fontName: 'WenQuanYi Micro Hei',
                fontSize: 42,
                color: '#fff7cc',
                backgroundColor: '#050505',
                backgroundOpacity: 0.72,
                outlineWidth: 1,
                outlineColor: '#000000'
            },
            emphasis: {
                label: '重点提示 · 金色强调',
                fontName: 'Noto Sans CJK SC',
                fontSize: 50,
                color: '#ffe08a',
                backgroundColor: '#111111',
                backgroundOpacity: 0.50,
                outlineWidth: 2,
                outlineColor: '#000000'
            },
            minimal: {
                label: '极简无底 · 白字描边',
                fontName: 'Noto Sans CJK SC',
                fontSize: 46,
                color: '#ffffff',
                backgroundColor: '#000000',
                backgroundOpacity: 0,
                outlineWidth: 3,
                outlineColor: '#000000'
            }
        };
        this.renderSubtitleStyleTemplates();
        this.elements.subtitleStyleTemplate?.addEventListener('change', () => {
            this.applySubtitleStyleTemplate(this.elements.subtitleStyleTemplate.value);
            this.saveCurrentStrategy();
        });
        this.elements.subtitlePreset?.addEventListener('change', () => {
            this.applySubtitlePreset(this.elements.subtitlePreset.value);
            this.saveCurrentStrategy();
        });
        const controls = [
            this.elements.subtitleX,
            this.elements.subtitleY,
            this.elements.subtitleWidth,
            this.elements.subtitleHeight,
            this.elements.subtitleFontSize,
            this.elements.subtitleColor,
            this.elements.subtitleBackgroundColor,
            this.elements.subtitleBackgroundOpacity,
            this.elements.subtitleOutlineWidth,
            this.elements.subtitleOutlineColor
        ];
        controls.forEach(control => {
            if (!control) return;
            control.addEventListener('input', () => {
                this.clampSubtitleInputs();
                this.syncSubtitlePresetSelection();
                this.syncSubtitleStyleTemplateSelection();
                this.syncSubtitleFontPreview();
                this.syncSubtitlePreviewFromInputs();
                this.saveCurrentStrategy();
            });
        });
        this.elements.subtitleFontName?.addEventListener('change', () => {
            this.syncSubtitleStyleTemplateSelection();
            this.syncSubtitleFontPreview();
            this.syncSubtitlePreviewFromInputs();
            this.saveCurrentStrategy();
        });
        this.syncSubtitleFontPreview();
        this.syncSubtitlePreviewFromInputs();
        this.syncSubtitlePresetSelection();
        this.syncSubtitleStyleTemplateSelection();
    }

    async loadSubtitleFonts() {
        const select = this.elements.subtitleFontName;
        if (!select) return;
        const selected = select.value || 'Noto Sans CJK SC';
        try {
            const response = await fetch('/api/subtitle-fonts');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const payload = await response.json();
            this.renderSubtitleFontOptions(payload.fonts || [], selected);
        } catch (error) {
            console.warn('读取字幕字体目录失败，使用内置字体列表:', error);
            this.renderSubtitleFontOptions([], selected);
        }
    }

    renderSubtitleFontOptions(fonts, selected) {
        const select = this.elements.subtitleFontName;
        if (!select) return;
        const currentOptions = Array.from(select.options).map(option => ({
            value: option.value,
            label: option.textContent.trim() || option.value
        }));
        const byValue = new Map();
        currentOptions.forEach(option => {
            if (option.value) byValue.set(option.value, option.label);
        });
        fonts.forEach(font => {
            const value = String(font || '').trim();
            if (value && !byValue.has(value)) byValue.set(value, value);
        });
        if (selected && !byValue.has(selected)) byValue.set(selected, selected);

        select.innerHTML = '';
        Array.from(byValue.entries()).forEach(([value, label]) => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = label;
            select.appendChild(option);
        });
        select.value = byValue.has(selected) ? selected : 'Noto Sans CJK SC';
        this.syncSubtitleFontPreview();
        this.syncSubtitlePreviewFromInputs();
    }

    setSubtitleFontValue(fontName) {
        const select = this.elements.subtitleFontName;
        if (!select || !fontName) return;
        const value = String(fontName).trim();
        if (!value) return;
        if (!Array.from(select.options).some(option => option.value === value)) {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = value;
            select.appendChild(option);
        }
        select.value = value;
        this.syncSubtitleFontPreview();
    }

    renderSubtitleStyleTemplates() {
        const select = this.elements.subtitleStyleTemplate;
        if (!select || !this.subtitleStyleTemplates) return;
        select.innerHTML = '<option value="">选择字幕样式模板</option>';
        Object.entries(this.subtitleStyleTemplates).forEach(([key, template]) => {
            const option = document.createElement('option');
            option.value = key;
            option.textContent = template.label;
            select.appendChild(option);
        });
        const custom = document.createElement('option');
        custom.value = 'custom';
        custom.textContent = '自定义';
        select.appendChild(custom);
    }

    applySubtitleStyleTemplate(name) {
        const template = this.subtitleStyleTemplates?.[name];
        if (!template) return;
        this.setSubtitleFontValue(template.fontName);
        this.elements.subtitleFontSize.value = template.fontSize;
        this.elements.subtitleColor.value = template.color;
        this.elements.subtitleBackgroundColor.value = template.backgroundColor;
        this.elements.subtitleBackgroundOpacity.value = template.backgroundOpacity;
        this.elements.subtitleOutlineWidth.value = template.outlineWidth;
        this.elements.subtitleOutlineColor.value = template.outlineColor;
        this.syncSubtitlePresetSelection();
        this.syncSubtitleFontPreview();
        this.syncSubtitlePreviewFromInputs();
        this.syncSubtitleStyleTemplateSelection();
    }

    collectSubtitleStyleValues() {
        return {
            fontName: this.elements.subtitleFontName.value || 'Noto Sans CJK SC',
            fontSize: Number(this.elements.subtitleFontSize.value) || 46,
            color: this.elements.subtitleColor.value || '#ffffff',
            backgroundColor: this.elements.subtitleBackgroundColor.value || '#111111',
            backgroundOpacity: Number(this.elements.subtitleBackgroundOpacity.value),
            outlineWidth: Number(this.elements.subtitleOutlineWidth.value) || 0,
            outlineColor: this.elements.subtitleOutlineColor.value || '#000000'
        };
    }

    syncSubtitleStyleTemplateSelection() {
        const select = this.elements.subtitleStyleTemplate;
        if (!select || !this.subtitleStyleTemplates) return;
        const current = this.collectSubtitleStyleValues();
        const match = Object.entries(this.subtitleStyleTemplates).find(([, template]) => (
            template.fontName === current.fontName
            && template.fontSize === current.fontSize
            && template.color.toLowerCase() === current.color.toLowerCase()
            && template.backgroundColor.toLowerCase() === current.backgroundColor.toLowerCase()
            && Number(template.backgroundOpacity) === current.backgroundOpacity
            && Number(template.outlineWidth) === current.outlineWidth
            && template.outlineColor.toLowerCase() === current.outlineColor.toLowerCase()
        ));
        select.value = match ? match[0] : 'custom';
    }

    syncSubtitleFontPreview() {
        const preview = this.elements.subtitleFontPreview;
        const select = this.elements.subtitleFontName;
        if (!preview || !select) return;
        const opacity = Number(this.elements.subtitleBackgroundOpacity.value);
        preview.style.background = this._hexToRgba(
            this.elements.subtitleBackgroundColor.value || '#111111',
            Number.isFinite(opacity) ? opacity : 0.55
        );
        const params = new URLSearchParams({
            text: '这是字幕预览 AaBb 123',
            font: select.value || 'Noto Sans CJK SC',
            font_size: String(Number(this.elements.subtitleFontSize.value) || 46),
            color: this.elements.subtitleColor.value || '#ffffff',
            outline_width: String(Number(this.elements.subtitleOutlineWidth.value) || 0),
            outline_color: this.elements.subtitleOutlineColor.value || '#000000',
            width: '720',
            height: '96'
        });
        preview.src = `/api/subtitle-preview-image?${params.toString()}`;
    }

    applySubtitlePreset(name) {
        const preset = this.subtitlePresets?.[name];
        if (!preset) return;
        this.elements.subtitleX.value = preset.x;
        this.elements.subtitleY.value = preset.y;
        this.elements.subtitleWidth.value = preset.width;
        this.elements.subtitleHeight.value = preset.height;
        this.elements.subtitleFontSize.value = preset.fontSize;
        this.syncSubtitlePreviewFromInputs();
    }

    syncSubtitlePresetSelection() {
        if (!this.elements.subtitlePreset || !this.subtitlePresets) return;
        const current = {
            x: Number(this.elements.subtitleX.value),
            y: Number(this.elements.subtitleY.value),
            width: Number(this.elements.subtitleWidth.value),
            height: Number(this.elements.subtitleHeight.value),
            fontSize: Number(this.elements.subtitleFontSize.value)
        };
        const match = Object.entries(this.subtitlePresets).find(([, preset]) => (
            preset.x === current.x &&
            preset.y === current.y &&
            preset.width === current.width &&
            preset.height === current.height &&
            preset.fontSize === current.fontSize
        ));
        this.elements.subtitlePreset.value = match ? match[0] : 'custom';
    }

    clampSubtitleInputs() {
        const width = Math.max(1, Math.min(1920, Number(this.elements.subtitleWidth.value) || 1920));
        const height = Math.max(1, Math.min(360, Number(this.elements.subtitleHeight.value) || 110));
        const x = Math.max(0, Math.min(1920 - width, Number(this.elements.subtitleX.value) || 0));
        const y = Math.max(0, Math.min(1080 - height, Number(this.elements.subtitleY.value) || 900));
        this.elements.subtitleWidth.value = width;
        this.elements.subtitleHeight.value = height;
        this.elements.subtitleX.value = x;
        this.elements.subtitleY.value = y;
    }

    syncSubtitlePreviewFromInputs() {
        this.clampSubtitleInputs();
        this.syncCourseSubtitleOverlays();
    }

    syncAllSubtitlePreviewImages() {
        document.querySelectorAll('.course-preview-page')
            .forEach(card => this.updatePageSubtitleSample(card));
    }

    syncCourseSubtitleOverlays() {
        const overlays = document.querySelectorAll('.course-preview-subtitle-overlay');
        if (!overlays.length) return;
        this.clampSubtitleInputs();
        const x = Number(this.elements.subtitleX.value) || 0;
        const y = Number(this.elements.subtitleY.value) || 0;
        const width = Number(this.elements.subtitleWidth.value) || 1920;
        const height = Number(this.elements.subtitleHeight.value) || 110;
        const fontSize = Number(this.elements.subtitleFontSize.value) || 46;
        const background = this.elements.subtitleBackgroundColor.value || '#111111';
        const opacity = Number(this.elements.subtitleBackgroundOpacity.value);
        overlays.forEach(overlay => {
            overlay.style.left = `${x / 1920 * 100}%`;
            overlay.style.top = `${y / 1080 * 100}%`;
            overlay.style.width = `${width / 1920 * 100}%`;
            overlay.style.height = `${height / 1080 * 100}%`;
            overlay.style.background = this._hexToRgba(
                background,
                Number.isFinite(opacity) ? opacity : 0.55
            );
            this.fitCourseSubtitleOverlay(
                overlay,
                Math.max(10, Math.min(28, fontSize / 2.5))
            );
        });
        this.syncAllSubtitlePreviewImages();
        this.refreshSubtitleRiskChecks();
    }

    fitCourseSubtitleOverlay(overlay, targetFontSize) {
        const sample = overlay.querySelector('.course-preview-subtitle-sample');
        const rect = overlay.getBoundingClientRect();
        const availableHeight = rect.height > 0
            ? Math.max(8, rect.height - 4)
            : Math.max(8, Number(this.elements.subtitleHeight.value || 110) / 1080 * 220);
        const lineHeight = 1.12;
        const lines = availableHeight < 24 ? 1 : 2;
        const fittedFontSize = Math.max(
            8,
            Math.min(targetFontSize, Math.floor(availableHeight / (lines * lineHeight)))
        );
        overlay.style.fontSize = `${fittedFontSize}px`;
        overlay.style.lineHeight = String(lineHeight);
        if (sample) {
            if (sample.tagName === 'IMG') {
                sample.style.webkitLineClamp = '';
                sample.style.maxHeight = '';
                return;
            }
            sample.style.webkitLineClamp = String(lines);
            sample.style.maxHeight = `${Math.floor(fittedFontSize * lineHeight * lines)}px`;
        }
    }

    _hexToRgba(hex, opacity) {
        const value = String(hex || '#333333').replace('#', '');
        const red = parseInt(value.slice(0, 2), 16);
        const green = parseInt(value.slice(2, 4), 16);
        const blue = parseInt(value.slice(4, 6), 16);
        return `rgba(${red}, ${green}, ${blue}, ${Math.max(0, Math.min(1, opacity))})`;
    }

    saveCurrentStrategy() {
        try {
            localStorage.setItem(
                this.strategyDraftStorageKey,
                JSON.stringify(this.collectCurrentStrategy())
            );
        } catch (error) {
            console.warn('保存当前生成策略失败:', error);
        }
    }

    restoreCurrentStrategy() {
        try {
            const rawStrategy = localStorage.getItem(this.strategyDraftStorageKey);
            if (!rawStrategy) return;
            const strategy = JSON.parse(rawStrategy);
            if (!strategy || typeof strategy !== 'object') return;
            this.applyStrategyToControls(strategy);
        } catch (error) {
            console.warn('恢复当前生成策略失败:', error);
        }
    }

    applyStrategyToControls(strategy) {
        if (strategy.tts_engine) this.elements.ttsEngine.value = strategy.tts_engine;

        const values = {
            renderEngine: 'render_engine',
            llmEngine: 'llm_engine',
            llmMode: 'llm_mode',
            refinementLevel: 'refinement_level',
            visualTheme: 'visual_theme',
            maxIllustrations: 'max_illustrations',
            pptFooterText: 'ppt_footer_text',
            ttsEmotion: 'tts_emotion',
            ttsRate: 'tts_rate',
            ttsEmotionScale: 'tts_emotion_scale',
            ttsSentencePause: 'tts_sentence_pause',
            subtitleX: 'subtitle_x',
            subtitleY: 'subtitle_y',
            subtitleWidth: 'subtitle_width',
            subtitleHeight: 'subtitle_height',
            subtitleFontSize: 'subtitle_font_size',
            subtitleColor: 'subtitle_color',
            subtitleBackgroundColor: 'subtitle_background_color',
            subtitleBackgroundOpacity: 'subtitle_background_opacity',
            subtitleOutlineWidth: 'subtitle_outline_width',
            subtitleOutlineColor: 'subtitle_outline_color'
        };
        Object.entries(values).forEach(([elementName, key]) => {
            if (strategy[key] !== undefined && this.elements[elementName]) {
                this.elements[elementName].value = strategy[key];
            }
        });
        this.setSubtitleFontValue(strategy.subtitle_font_name);

        if (strategy.llm_enabled !== undefined) {
            this.elements.llmEnabled.checked = Boolean(strategy.llm_enabled);
        }
        if (strategy.illustrations_enabled !== undefined) {
            this.elements.illustrationsEnabled.checked = Boolean(strategy.illustrations_enabled);
        }
        if (strategy.burn_subtitles !== undefined) {
            this.elements.burnSubtitles.checked = Boolean(strategy.burn_subtitles);
        }

        const customVoice = strategy.custom_voice || '';
        this.elements.customVoice.value = customVoice;
        this.pendingVoiceSelection = strategy.selected_voice || strategy.voice || null;
        this.state.logoPath = strategy.school_logo_path || null;
        this.syncSubtitleStyleTemplateSelection();
        this.syncSubtitleFontPreview();
        this.syncSubtitlePreviewFromInputs();
        this.toggleLLMMode();
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
            this.saveCurrentStrategy();
        });

        convertBtn.addEventListener('click', () => this.handleConvert());
        renderBtn.addEventListener('click', () => this.handleRender());
        ttsEngine.addEventListener('change', async () => {
            await this.loadVoices();
            this.saveCurrentStrategy();
        });

        const { llmEnabled } = this.elements;
        llmEnabled.addEventListener('change', () => this.toggleLLMMode());

        const { slidesToggle } = this.elements;
        slidesToggle.addEventListener('click', () => this.toggleSlides());
        this.elements.cancelCourseBtn.addEventListener('click', () => this.cancelCourse());
        this.elements.saveScriptsBtn.addEventListener('click', () => this.savePreviewScripts());
        this.elements.continueCourseBtn.addEventListener('click', () => this.continueCourse());
        this.elements.previewPreviousBtn.addEventListener(
            'click', () => this.goToPreviewPage(this.currentPreviewPage - 1)
        );
        this.elements.previewNextBtn.addEventListener(
            'click', () => this.goToPreviewPage(this.currentPreviewPage + 1)
        );
        this.elements.previewPageSelect.addEventListener(
            'change', event => this.goToPreviewPage(Number(event.target.value))
        );
        this.elements.unreviewedOnly.addEventListener(
            'change', () => this.filterPreviewPages()
        );
        this.elements.smartCutRecommendBtn.addEventListener(
            'click', () => this.recommendSmartCuts()
        );
        this.elements.smartCutApplyBtn.addEventListener(
            'click', () => this.applySmartCuts()
        );
        this.elements.uploadEditedPptBtn.addEventListener(
            'click', () => this.elements.editedPptInput.click()
        );
        this.elements.editedPptInput.addEventListener('change', event => {
            const file = event.target.files[0];
            if (file) this.uploadEditedPresentation(file);
            event.target.value = '';
        });
        this.elements.strategyTemplateSelect.addEventListener(
            'change', event => this.applyStrategyTemplate(event.target.value)
        );
        this.elements.saveTemplateBtn.addEventListener(
            'click', () => this.saveStrategyTemplate()
        );
        this.elements.deleteTemplateBtn.addEventListener(
            'click', () => this.deleteStrategyTemplate()
        );
        this.elements.selectAllFiles.addEventListener('change', (event) => {
            this.state.files.forEach(item => {
                if (item.status === 'pending') item.selected = event.target.checked;
            });
            this.renderFileList();
        });
        this.elements.applyStrategyBtn.addEventListener(
            'click', () => this.applyStrategyToSelected()
        );
        this.bindStrategyPersistence();
        this.elements.advancedToggle.addEventListener('click', () => {
            const expanded = this.elements.advancedToggle.getAttribute('aria-expanded') === 'true';
            this.elements.advancedToggle.setAttribute('aria-expanded', String(!expanded));
            this.elements.advancedToggle.textContent = expanded ? '展开高级设置' : '收起高级设置';
            document.querySelectorAll('.advanced-option').forEach(element => {
                element.hidden = expanded;
            });
            if (!expanded) this.toggleLLMMode();
        });

    }

    async uploadSchoolLogo(file) {
        const allowedExtensions = ['.png', '.jpg', '.jpeg', '.webp'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!allowedExtensions.includes(ext)) {
            window.VidPPTUI.alert('Logo 仅支持 PNG、JPG 或 WebP 图片', { type: 'warning' });
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
            this.saveCurrentStrategy();
        } catch (error) {
            this.state.logoPath = null;
            this.elements.schoolLogoHint.textContent = error.message;
            await window.VidPPTUI.alert(error.message, { type: 'error' });
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

    async loadVoices({ preferredVoice = null } = {}) {
        const { ttsEngine, voiceSelect, voicePreviewList } = this.elements;
        preferredVoice = preferredVoice || this.pendingVoiceSelection || voiceSelect.value;
        this.pendingVoiceSelection = null;
        this.elements.volcengineExpressionGroup.hidden =
            ttsEngine.value !== 'volcengine';
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
            const matchedPreferredVoice = voiceList.some(voice => voice.id === preferredVoice);
            this.renderVoicePreviewList(
                engine,
                voiceList,
                matchedPreferredVoice ? preferredVoice : null
            );
            if (preferredVoice && !matchedPreferredVoice && !this.elements.customVoice.value.trim()) {
                this.elements.customVoice.value = preferredVoice;
            }
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

    renderVoicePreviewList(engine, voices, selectedVoiceId = null) {
        const { voicePreviewList, voiceSelect } = this.elements;
        voicePreviewList.innerHTML = '';
        if (!voices.length) {
            voicePreviewList.innerHTML = '<div class="voice-list-message">暂无公共音色</div>';
            return;
        }
        const sortedVoices = [...voices].sort((left, right) => {
            const leftFavorite = this.isVoiceFavorite(engine, left.id);
            const rightFavorite = this.isVoiceFavorite(engine, right.id);
            if (leftFavorite !== rightFavorite) return leftFavorite ? -1 : 1;
            return 0;
        });
        const selectedVoice = selectedVoiceId || sortedVoices[0]?.id || '';
        sortedVoices.forEach((voice, index) => {
            const isFavorite = this.isVoiceFavorite(engine, voice.id);
            const isSelected = voice.id === selectedVoice;
            const voiceNameAttr = this._escAttr(voice.name);
            const item = document.createElement('div');
            item.className = `voice-preview-item${isSelected ? ' selected' : ''}`;
            item.setAttribute('role', 'option');
            item.setAttribute('aria-selected', isSelected ? 'true' : 'false');
            item.innerHTML = `
                <button type="button" class="voice-play-btn"
                        aria-label="试听 ${voiceNameAttr}" title="试听音色">▶</button>
                <span class="voice-preview-copy">
                    <span class="voice-preview-name">${this._esc(voice.name)}</span>
                    <span class="voice-preview-id">${this._esc(voice.id)}</span>
                </span>
                <button type="button"
                        class="voice-favorite-btn${isFavorite ? ' active' : ''}"
                        aria-label="${isFavorite ? '取消收藏' : '收藏'} ${voiceNameAttr}"
                        aria-pressed="${isFavorite ? 'true' : 'false'}"
                        title="${isFavorite ? '取消收藏' : '收藏音色'}">${isFavorite ? '★' : '☆'}</button>
            `;
            item.addEventListener('click', (event) => {
                const favoriteButton = event.target.closest('.voice-favorite-btn');
                if (favoriteButton) {
                    event.stopPropagation();
                    this.toggleVoiceFavorite(engine, voice, favoriteButton);
                    return;
                }
                this.selectVoiceItem(item, voice.id);
                if (event.target.closest('.voice-play-btn')) {
                    this.playVoicePreview(
                        engine, voice.id, item.querySelector('.voice-play-btn')
                    );
                }
            });
            voicePreviewList.appendChild(item);
        });
        voiceSelect.value = selectedVoice;
    }

    loadVoiceFavorites() {
        try {
            const rawFavorites = localStorage.getItem(this.voiceFavoritesStorageKey);
            const parsed = rawFavorites ? JSON.parse(rawFavorites) : {};
            return parsed && typeof parsed === 'object' ? parsed : {};
        } catch (error) {
            console.warn('读取收藏音色失败:', error);
            return {};
        }
    }

    saveVoiceFavorites() {
        try {
            localStorage.setItem(
                this.voiceFavoritesStorageKey,
                JSON.stringify(this.voiceFavorites)
            );
        } catch (error) {
            console.warn('保存收藏音色失败:', error);
        }
    }

    getVoiceFavoriteSet(engine) {
        return new Set(Array.isArray(this.voiceFavorites[engine])
            ? this.voiceFavorites[engine]
            : []);
    }

    isVoiceFavorite(engine, voiceId) {
        return this.getVoiceFavoriteSet(engine).has(voiceId);
    }

    toggleVoiceFavorite(engine, voice, button) {
        const favoriteSet = this.getVoiceFavoriteSet(engine);
        const nextFavoriteState = !favoriteSet.has(voice.id);
        if (nextFavoriteState) {
            favoriteSet.add(voice.id);
        } else {
            favoriteSet.delete(voice.id);
        }
        this.voiceFavorites[engine] = [...favoriteSet];
        this.saveVoiceFavorites();
        button.classList.toggle('active', nextFavoriteState);
        button.textContent = nextFavoriteState ? '★' : '☆';
        button.setAttribute('aria-pressed', nextFavoriteState ? 'true' : 'false');
        button.setAttribute(
            'aria-label',
            `${nextFavoriteState ? '取消收藏' : '收藏'} ${voice.name}`
        );
        button.title = nextFavoriteState ? '取消收藏' : '收藏音色';
    }

    selectVoiceItem(item, voiceId) {
        this.elements.voiceSelect.value = voiceId;
        this.elements.customVoice.value = '';
        this.elements.voicePreviewList.querySelectorAll('.voice-preview-item').forEach(row => {
            const selected = row === item;
            row.classList.toggle('selected', selected);
            row.setAttribute('aria-selected', selected ? 'true' : 'false');
        });
        this.saveCurrentStrategy();
    }

    stopVoicePreview() {
        if (this.voicePreviewAudio) {
            this.voicePreviewAudio.pause();
            this.voicePreviewAudio.src = '';
            this.voicePreviewAudio = null;
        }
        if (this.activeVoicePreviewButton) {
            this.activeVoicePreviewButton.textContent =
                '▶';
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
            window.VidPPTUI.alert('不支持的文件类型，请上传 Word、PDF 或 PowerPoint 文件', { type: 'warning' });
            return;
        }

        if (file.size === 0) {
            window.VidPPTUI.alert('文件为空，请选择有效的课程文件', { type: 'warning' });
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
                <span class="file-route-badge ${item.sourceType === 'lesson-plan' ? 'lesson-plan' : 'presentation'}">
                    ${item.sourceType === 'lesson-plan' ? 'AI 设计' : '保留原稿'}
                </span>
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
        this.renderAssetTable();
        this.updateRouteSummary();
        this._syncSelectAll();
    }

    updateRouteSummary() {
        const active = this.state.files.filter(item =>
            !['error', 'completed'].includes(item.status)
        );
        const lessonPlans = active.filter(item => item.sourceType === 'lesson-plan').length;
        const presentations = active.filter(item => item.sourceType === 'presentation').length;
        const { routeSummary } = this.elements;

        if (!active.length) {
            routeSummary.hidden = true;
            this.elements.workflowBadge.textContent = '智能识别';
            this.elements.workflowDescription.textContent =
                '上传素材后将自动匹配教案设计或原稿保真路线。';
            return;
        }

        routeSummary.hidden = false;
        if (lessonPlans && !presentations) {
            this.elements.routeSummaryIcon.textContent = 'AI';
            this.elements.routeSummaryTitle.textContent = '教案设计路线';
            this.elements.routeSummaryDescription.textContent =
                `${lessonPlans} 份 Word/PDF 将经过内容提炼、PPT 设计、讲稿审核后合成视频。`;
            this.elements.workflowBadge.textContent = '教案设计';
            this.elements.workflowDescription.textContent =
                'AI 将生成可编辑 PPT；插图、页脚和 Logo 等高级设置会应用到新课件。';
        } else if (presentations && !lessonPlans) {
            this.elements.routeSummaryIcon.textContent = 'PPT';
            this.elements.routeSummaryTitle.textContent = '原稿保真路线';
            this.elements.routeSummaryDescription.textContent =
                `${presentations} 份 PPT 将保留原有版式，提取页面内容与备注生成讲稿和视频。`;
            this.elements.workflowBadge.textContent = '原稿保真';
            this.elements.workflowDescription.textContent =
                '保留现有 PPT 样式；课程设计类视觉选项不会改写原稿版式。';
        } else {
            this.elements.routeSummaryIcon.textContent = '2×';
            this.elements.routeSummaryTitle.textContent = '混合生产任务';
            this.elements.routeSummaryDescription.textContent =
                `${lessonPlans} 份教案走 AI 设计路线，${presentations} 份 PPT 走原稿保真路线。`;
            this.elements.workflowBadge.textContent = '两条路线';
            this.elements.workflowDescription.textContent =
                '系统将按文件类型分别处理，共用当前声音和基础生成策略。';
        }
    }

    confirmProduction(pending) {
        const lessonPlans = pending.filter(item => item.sourceType === 'lesson-plan').length;
        const presentations = pending.length - lessonPlans;
        const engineNames = {
            'edge-tts': 'Edge TTS',
            'volcengine': '火山引擎 TTS',
            'minimax': 'MiniMax TTS'
        };
        const routeLines = [];
        if (lessonPlans) routeLines.push(`教案设计路线：${lessonPlans} 个`);
        if (presentations) routeLines.push(`原稿保真路线：${presentations} 个`);
        const voiceName = this.elements.customVoice.value.trim()
            || this.elements.voiceSelect.selectedOptions[0]?.textContent
            || '默认音色';
        return window.VidPPTUI.confirm([
            `即将提交 ${pending.length} 个课程任务`,
            '',
            ...routeLines,
            `语音：${engineNames[this.elements.ttsEngine.value] || this.elements.ttsEngine.value} · ${voiceName}`,
            `字幕：${this.elements.burnSubtitles.checked ? '烧录到视频' : '仅生成 SRT 文件'}`,
            lessonPlans ? `AI 提炼：${this.elements.refinementLevel.selectedOptions[0]?.textContent}` : '',
            lessonPlans ? `视觉方案：${this.elements.visualTheme.selectedOptions[0]?.textContent}` : '',
            '',
            '确认开始生成课程草稿？'
        ].filter(Boolean).join('\n'), {
            title: '开始生成课程草稿',
            confirmText: '开始生成'
        });
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
        const customVoice = this.elements.customVoice.value.trim();
        return {
            tts_engine: this.elements.ttsEngine.value,
            voice: customVoice || this.elements.voiceSelect.value,
            selected_voice: this.elements.voiceSelect.value,
            custom_voice: customVoice,
            tts_rate: this.elements.ttsRate.value,
            tts_emotion: this.elements.ttsEmotion.value,
            tts_emotion_scale: Number(this.elements.ttsEmotionScale.value),
            tts_sentence_pause: Number(this.elements.ttsSentencePause.value),
            burn_subtitles: this.elements.burnSubtitles.checked,
            subtitle_x: Number(this.elements.subtitleX.value),
            subtitle_y: Number(this.elements.subtitleY.value),
            subtitle_width: Number(this.elements.subtitleWidth.value),
            subtitle_height: Number(this.elements.subtitleHeight.value),
            subtitle_font_size: Number(this.elements.subtitleFontSize.value),
            subtitle_font_name: this.elements.subtitleFontName.value,
            subtitle_color: this.elements.subtitleColor.value,
            subtitle_background_color: this.elements.subtitleBackgroundColor.value,
            subtitle_background_opacity: Number(this.elements.subtitleBackgroundOpacity.value),
            subtitle_outline_width: Number(this.elements.subtitleOutlineWidth.value),
            subtitle_outline_color: this.elements.subtitleOutlineColor.value,
            render_engine: this.elements.renderEngine.value,
            llm_enabled: this.elements.llmEnabled.checked,
            llm_engine: this.elements.llmEngine.value,
            llm_mode: this.elements.llmMode.value,
            refinement_level: this.elements.refinementLevel.value,
            visual_theme: this.elements.visualTheme.value,
            illustrations_enabled: this.elements.illustrationsEnabled.checked,
            max_illustrations: Number(this.elements.maxIllustrations.value),
            ppt_footer_text: this.elements.pptFooterText.value.trim(),
            school_logo_path: this.state.logoPath
        };
    }

    collectSubtitleOptions() {
        return {
            subtitle_x: Number(this.elements.subtitleX.value),
            subtitle_y: Number(this.elements.subtitleY.value),
            subtitle_width: Number(this.elements.subtitleWidth.value),
            subtitle_height: Number(this.elements.subtitleHeight.value),
            subtitle_font_size: Number(this.elements.subtitleFontSize.value),
            subtitle_font_name: this.elements.subtitleFontName.value,
            subtitle_color: this.elements.subtitleColor.value,
            subtitle_background_color: this.elements.subtitleBackgroundColor.value,
            subtitle_background_opacity: Number(this.elements.subtitleBackgroundOpacity.value),
            subtitle_outline_width: Number(this.elements.subtitleOutlineWidth.value),
            subtitle_outline_color: this.elements.subtitleOutlineColor.value
        };
    }

    loadStrategyTemplates() {
        const builtIns = {
            '高校理论课': {
                tts_engine: 'volcengine',
                llm_enabled: true,
                llm_engine: 'qwen',
                llm_mode: 'per-page',
                refinement_level: 'standard',
                illustrations_enabled: true,
                max_illustrations: 3
            },
            '企业制度宣讲': {
                tts_engine: 'volcengine',
                llm_enabled: true,
                llm_engine: 'qwen',
                llm_mode: 'per-page',
                refinement_level: 'light',
                illustrations_enabled: false,
                max_illustrations: 1
            },
            '高度提炼微课': {
                tts_engine: 'edge-tts',
                llm_enabled: true,
                llm_engine: 'qwen',
                llm_mode: 'per-page',
                refinement_level: 'strong',
                illustrations_enabled: true,
                max_illustrations: 2
            }
        };
        let personal = {};
        try {
            personal = JSON.parse(localStorage.getItem('courseStrategyTemplates') || '{}');
        } catch {
            personal = {};
        }
        this.strategyTemplates = { ...builtIns, ...personal };
        const select = this.elements.strategyTemplateSelect;
        select.innerHTML = '<option value="">选择生产模板</option>';
        Object.keys(this.strategyTemplates).forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = personal[name] ? `${name} · 我的` : name;
            select.appendChild(option);
        });
        this.personalStrategyTemplates = personal;
        this.elements.deleteTemplateBtn.disabled = true;
    }

    async applyStrategyTemplate(name) {
        const strategy = this.strategyTemplates?.[name];
        if (!strategy) {
            this.elements.deleteTemplateBtn.disabled = true;
            return;
        }
        this.applyStrategyToControls(strategy);
        await this.loadVoices({ preferredVoice: this.pendingVoiceSelection });
        this.elements.deleteTemplateBtn.disabled = !this.personalStrategyTemplates[name];
        this.saveCurrentStrategy();
        this.showStatus('success', `已应用“${name}”生产模板`);
    }

    async saveStrategyTemplate() {
        const name = await window.VidPPTUI.prompt('请输入模板名称', {
            title: '保存生产模板',
            placeholder: '例如：高校理论课标准配置'
        });
        if (!name?.trim()) return;
        const trimmedName = name.trim().slice(0, 30);
        this.personalStrategyTemplates[trimmedName] = this.collectCurrentStrategy();
        localStorage.setItem(
            'courseStrategyTemplates',
            JSON.stringify(this.personalStrategyTemplates)
        );
        this.loadStrategyTemplates();
        this.elements.strategyTemplateSelect.value = trimmedName;
        this.elements.deleteTemplateBtn.disabled = false;
        this.showStatus('success', `已保存模板“${trimmedName}”`);
    }

    async deleteStrategyTemplate() {
        const name = this.elements.strategyTemplateSelect.value;
        if (!this.personalStrategyTemplates[name]) return;
        const confirmed = await window.VidPPTUI.confirm(`删除个人模板“${name}”？`, {
            title: '删除生产模板',
            confirmText: '删除',
            danger: true
        });
        if (!confirmed) return;
        delete this.personalStrategyTemplates[name];
        localStorage.setItem(
            'courseStrategyTemplates',
            JSON.stringify(this.personalStrategyTemplates)
        );
        this.loadStrategyTemplates();
        this.showStatus('success', '模板已删除');
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

    renderAssetTable() {
        const body = this.elements.assetTableBody;
        if (!body) return;
        if (!this.state.files.length) {
            body.innerHTML = '<tr><td colspan="6" class="table-empty">暂无课程数据</td></tr>';
            return;
        }
        body.innerHTML = this.state.files.map(item => {
            const actions = [];
            if (item.status === 'awaiting_confirmation') {
                actions.push(`<button type="button" class="table-action" data-action="preview" data-task-id="${this._escAttr(item.taskId)}">预览审核</button>`);
            }
            if (item.status === 'completed' && item.videoPath) {
                actions.push(`<button type="button" class="table-action" data-action="download" data-task-id="${this._escAttr(item.taskId)}">下载</button>`);
            }
            if (['completed', 'error', 'interrupted', 'awaiting_confirmation'].includes(item.status)) {
                actions.push(`<button type="button" class="table-action danger" data-action="delete" data-task-id="${this._escAttr(item.taskId)}">删除</button>`);
            }
            return `
                <tr>
                    <td><strong>${this._esc(item.fileName || '未知文件')}</strong><small>${this._esc(item.taskId || '')}</small></td>
                    <td>${this._esc(item.ownerUsername || '-')}</td>
                    <td><span class="status-pill status-${this._escAttr(item.status || 'unknown')}">${this._esc(this._fileStatusText(item))}</span></td>
                    <td>${Math.round(item.percentage || 0)}%</td>
                    <td>${this._formatTime(item.updatedAt || item.completedAt || item.startedAt || item.createdAt)}</td>
                    <td class="table-actions">${actions.join('') || '-'}</td>
                </tr>
            `;
        }).join('');
        body.querySelectorAll('.table-action').forEach(button => {
            button.addEventListener('click', () => {
                const taskId = button.dataset.taskId;
                const action = button.dataset.action;
                if (action === 'preview') this.loadCoursePreview(taskId);
                if (action === 'download') this.handleDownloadByTaskId(taskId);
                if (action === 'delete') this.deleteTask(taskId);
            });
        });
    }

    async loadOperationLogs() {
        const body = this.elements.operationLogBody;
        if (!body) return;
        try {
            const response = await fetch('/api/operation-logs?limit=80');
            if (!response.ok) return;
            const data = await response.json();
            const logs = data.logs || [];
            if (!logs.length) {
                body.innerHTML = '<tr><td colspan="5" class="table-empty">暂无操作日志</td></tr>';
                return;
            }
            body.innerHTML = logs.map(log => `
                <tr>
                    <td>${this._formatTime(log.created_at)}</td>
                    <td>${this._esc(log.actor || '-')}</td>
                    <td>${this._esc(this._operationText(log.action))}</td>
                    <td><strong>${this._esc(log.target_name || log.task_id || '-')}</strong><small>${this._esc(log.message || '')}</small></td>
                    <td>${log.success ? '成功' : '失败'}</td>
                </tr>
            `).join('');
        } catch (error) {
            console.debug('操作日志暂时不可用:', error);
        }
    }

    _formatTime(value) {
        if (!value) return '-';
        const date = new Date(Number(value) * 1000);
        if (Number.isNaN(date.getTime())) return '-';
        return date.toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    _operationText(action) {
        const labels = {
            login: '登录',
            login_failed: '登录失败',
            logout: '退出登录',
            upload: '上传文件',
            create_task: '创建任务',
            preview_task: '预览任务',
            save_preview: '保存讲稿',
            continue_task: '继续生成',
            retry_task: '重试任务',
            stop_task: '停止任务',
            delete_task: '删除任务',
            cancel_task: '取消任务',
            download: '下载文件',
            apply_segments: '应用切课',
            upload_reviewed_ppt: '上传审核 PPT'
        };
        return labels[action] || action || '-';
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

    _escAttr(s) {
        return this._esc(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
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
        if (!await this.confirmProduction(pending)) return;

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
                                stagePercentage: Number(data.stage_percentage ?? 0),
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
                        const stagePercentage = Number(data.stage_percentage ?? 0);
                        const message = data.message || (data.stage ? `${this.stageNames[data.stage] || data.stage} (${data.current}/${data.total})` : '');
                        this.updateItem(index, {
                            percentage,
                            stagePercentage,
                            stage: data.stage || item.stage,
                            message
                        });
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
                            previewPath: data.preview_path || item.previewPath,
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
                            subtitlesPath: data.subtitles_path || null,
                            videoSegments: data.video_segments || []
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
        const stagePercentage = Math.max(
            0, Math.min(100, Number(item.stagePercentage) || 0)
        );
        const displayedPercentage = item.stage === 'video'
            ? stagePercentage
            : percentage;
        const message = item.message
            || (item.status === 'queued' ? '排队中...' : `${this.stageNames[item.stage] || '准备'}中...`);
        const now = Date.now() / 1000;
        const elapsed = item.startedAt ? Math.max(0, now - item.startedAt) : null;
        const stageElapsed = item.stageStartedAt
            ? Math.max(0, now - item.stageStartedAt)
            : null;
        const progressForEta = item.stage === 'video'
            ? stagePercentage
            : percentage;
        const elapsedForEta = item.stage === 'video'
            ? stageElapsed
            : elapsed;
        const remaining = elapsedForEta && progressForEta >= 3
            ? Math.max(
                0,
                elapsedForEta * (100 - progressForEta) / progressForEta
            )
            : null;
        const timing = [
            elapsed !== null ? `已耗时 ${this.formatDuration(elapsed)}` : null,
            remaining !== null ? `预计剩余 ${this.formatDuration(remaining)}` : null,
            item.queuePosition ? `队列第 ${item.queuePosition} 位` : null,
            item.updatedAt ? `更新于 ${new Date(item.updatedAt * 1000).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}` : null
        ].filter(Boolean).join(' · ');
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
                    <strong>${Math.round(displayedPercentage)}%</strong>
                </div>
                <div class="card-progress-track">
                    <div class="card-progress-fill" style="width:${displayedPercentage}%"></div>
                </div>
                ${timing ? `<div class="card-progress-timing">${this._esc(timing)}</div>` : ''}
                <div class="card-progress-steps">${steps}</div>
            </div>
        `;
    }

    formatDuration(seconds) {
        const value = Math.max(0, Math.round(seconds));
        const hours = Math.floor(value / 3600);
        const minutes = Math.floor((value % 3600) / 60);
        if (hours) return `${hours}小时${minutes}分`;
        if (minutes) return `${minutes}分${value % 60}秒`;
        return `${value}秒`;
    }

    renderResultsGrid() {
        const container = this.elements.resultsGrid;
        const preservedVideoCards = new Map();
        container.querySelectorAll('.result-card[data-preserve-video="true"]').forEach(card => {
            preservedVideoCards.set(this._resultVideoPreserveKey(
                card.dataset.taskId,
                card.dataset.videoPath,
                card.dataset.artifactKey
            ), card);
            card.remove();
        });
        container.innerHTML = '';

        let hasVisible = false;

        this.state.files.forEach((item, index) => {
            if (!['awaiting_confirmation', 'completed', 'processing', 'queued', 'error', 'interrupted'].includes(item.status)) return;
            hasVisible = true;

            let card = document.createElement('div');
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
                card.querySelector('.result-card-delete').addEventListener('click', () => this.deleteTask(item.taskId));
            } else if (item.status === 'completed' && item.videoPath) {
                const artifacts = this._artifactLinks(item);
                const artifactKey = this._resultArtifactKey(item);
                const preserveKey = this._resultVideoPreserveKey(
                    item.taskId,
                    item.videoPath,
                    artifactKey
                );
                const preservedCard = preservedVideoCards.get(preserveKey);
                if (preservedCard) {
                    card = preservedCard;
                } else {
                    card.innerHTML = `
                        <div class="result-video-wrap">
                            ${this._deleteTaskButton(item)}
                            <video src="/api/video?path=${encodeURIComponent(item.videoPath)}" controls preload="metadata"></video>
                        </div>
                        <div class="result-card-footer">
                            <span class="result-card-name" title="${this._esc(item.fileName)}">${this._esc(item.fileName)}</span>
                            <button class="result-card-download" data-task-id="${this._esc(item.taskId)}">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                    <polyline points="7 10 12 15 17 10"/>
                                    <line x1="12" y1="15" x2="12" y2="3"/>
                                </svg>
                                下载
                            </button>
                        </div>
                        ${artifacts}
                        ${this._retryStageActions(item)}
                    `;
                    card.querySelector('.result-card-download').addEventListener('click', () => this.handleDownloadByTaskId(item.taskId));
                    card.querySelector('.result-card-delete').addEventListener('click', () => this.deleteTask(item.taskId));
                    card.querySelectorAll('.result-stage-retry').forEach(button => {
                        button.addEventListener('click', () => this.retryTaskStage(
                            item.taskId,
                            button.dataset.stage,
                            null,
                            button
                        ));
                    });
                }
                card.dataset.preserveVideo = 'true';
                card.dataset.taskId = item.taskId || '';
                card.dataset.videoPath = item.videoPath || '';
                card.dataset.artifactKey = artifactKey;
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
                    ${this._retryStageActions(item)}
                `;
                card.querySelector('.result-card-delete').addEventListener('click', () => this.deleteTask(item.taskId));
                card.querySelectorAll('.result-stage-retry').forEach(button => {
                    button.addEventListener('click', () => this.retryTaskStage(
                        item.taskId,
                        button.dataset.stage,
                        null,
                        button
                    ));
                });
            } else {
                const isInterrupted = item.status === 'interrupted';
                const placeholderText = item.status === 'error'
                    ? this._esc(item.error || '转换失败')
                    : isInterrupted
                        ? this._esc(item.message || '服务曾重启，本次生成已中断')
                    : item.status === 'queued'
                        ? '排队中...'
                        : '转换中...';

                card.innerHTML = `
                    <div class="result-video-wrap">
                        ${['error', 'interrupted'].includes(item.status) ? this._deleteTaskButton(item) : ''}
                        <div class="result-placeholder">
                            ${!['error', 'interrupted'].includes(item.status) ? '<div class="spinner"></div>' : ''}
                            <p>${placeholderText}</p>
                            ${!['error', 'interrupted'].includes(item.status) ? this._renderCardProgress(item) : ''}
                            ${isInterrupted ? `
                                <button class="result-card-retry" type="button"
                                        data-task-id="${this._esc(item.taskId)}">重新提交</button>
                            ` : ''}
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
                    deleteButton.addEventListener('click', () => this.deleteTask(item.taskId));
                }
                const retryButton = card.querySelector('.result-card-retry');
                if (retryButton) {
                    retryButton.addEventListener('click', () => this.retryTask(item.taskId));
                }
            }

            container.appendChild(card);
        });

        this.elements.resultsModule.hidden = !hasVisible;
    }

    _resultArtifactKey(item) {
        return [
            item.fileName,
            item.courseJsonPath,
            item.presentationPath,
            item.subtitlesPath,
            item.previewPath,
            JSON.stringify(item.videoSegments || [])
        ].map(value => value || '').join('|');
    }

    _resultVideoPreserveKey(taskId, videoPath, artifactKey) {
        return `${taskId || ''}|${videoPath || ''}|${artifactKey || ''}`;
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

    _retryStageActions(item) {
        if (item.status !== 'completed' || !item.previewPath) return '';
        return `
            <div class="result-stage-actions">
                <button type="button" class="result-stage-retry" data-stage="video">重新合成视频</button>
                <button type="button" class="result-stage-retry" data-stage="tts">重新生成全部配音</button>
            </div>
        `;
    }

    async deleteTask(taskIdOrIndex) {
        const taskId = typeof taskIdOrIndex === 'number'
            ? this.state.files[taskIdOrIndex]?.taskId
            : taskIdOrIndex;
        const found = this.getItemByTaskId(taskId);
        const item = found?.item;
        if (
            !item?.taskId
            || !['completed', 'error', 'interrupted', 'awaiting_confirmation'].includes(item.status)
        ) return;
        const confirmed = await window.VidPPTUI.confirm(
            `确定物理删除“${item.fileName}”吗？\n\n该任务生成的 PPT、视频、字幕、音频和中间文件都将永久删除，且无法恢复。`,
            {
                title: '删除课程产物',
                confirmText: '永久删除',
                danger: true
            }
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
            const current = this.getItemByTaskId(item.taskId);
            if (current) this.state.files.splice(current.index, 1);
            this.renderFileList();
            this.renderResultsGrid();
            this.updateBatchSummary();
            this.loadOperationLogs();
            this.showStatus('success', data.message || '课程产物已删除');
        } catch (error) {
            if (button) button.disabled = false;
            this.showStatus('error', error.message);
        }
    }

    async retryTask(taskId) {
        const found = this.getItemByTaskId(taskId);
        if (!found || found.item.status !== 'interrupted') return;

        const { item } = found;
        const button = this.elements.resultsGrid.querySelector(
            `.result-card-retry[data-task-id="${CSS.escape(taskId)}"]`
        );
        if (button) {
            button.disabled = true;
            button.textContent = '提交中...';
        }

        try {
            const response = await fetch('/api/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_path: item.filePath,
                    original_name: item.fileName,
                    batch_id: globalThis.crypto?.randomUUID?.() || `retry-${Date.now()}`,
                    strategy_source: item.strategySource || 'batch',
                    ...(item.strategy || {})
                })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '重新提交失败');

            // 新任务成功入队后再清理已中断的旧任务，避免提交失败时丢失恢复入口。
            await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
            const current = this.getItemByTaskId(taskId);
            if (!current) return;
            this.updateItem(current.index, {
                taskId: data.task_id,
                status: 'queued',
                stage: 'queue',
                percentage: 0,
                message: data.message || '已重新进入生产队列',
                error: null,
                queuePosition: data.queue_size || null
            });
            this.renderFileList();
            this.renderResultsGrid();
            this.updateBatchSummary();
            this.loadOperationLogs();
            this.showStatus('success', '任务已重新提交');
            this.startProgressStream(data.task_id);
        } catch (error) {
            if (button) {
                button.disabled = false;
                button.textContent = '重新提交';
            }
            this.showStatus('error', error.message);
        }
    }

    async retryTaskStage(taskId, stage, pageNumber = null, button = null) {
        const labels = {
            page_tts: `第 ${pageNumber} 页配音`,
            tts: '全部配音',
            video: '视频',
            media: '媒体'
        };
        if (!await window.VidPPTUI.confirm(`确认重新生成${labels[stage] || '当前阶段'}？已有可复用成果会保留。`, {
            title: '重新生成',
            confirmText: '重新生成'
        })) {
            return;
        }
        if (button) button.disabled = true;
        try {
            const response = await fetch(`/api/tasks/${taskId}/retry`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stage, page_number: pageNumber })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '阶段重试失败');
            const found = this.getItemByTaskId(taskId);
            if (found) {
                this.updateItem(found.index, {
                    status: 'queued',
                    stage: 'queue',
                    percentage: 50,
                    message: data.message,
                    error: null
                });
            }
            this.elements.coursePreviewModule.hidden = true;
            this.renderFileList();
            this.renderResultsGrid();
            this.updateBatchSummary();
            this.loadOperationLogs();
            this.showStatus('success', data.message);
            this.startProgressStream(taskId);
        } catch (error) {
            if (button) button.disabled = false;
            this.showStatus('error', error.message);
        }
    }

    async stopTask(taskId) {
        if (!taskId) return;
        if (!await window.VidPPTUI.confirm('停止后将退回讲稿确认，并保留已生成成果。确认停止？', {
            title: '停止生成',
            confirmText: '停止生成',
            danger: true
        })) {
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
            window.VidPPTUI.alert('没有可下载的视频', { type: 'warning' });
            return;
        }

        try {
            const downloadUrl = '/api/download?task_id='
                + encodeURIComponent(item.taskId)
                + '&path=' + encodeURIComponent(item.videoPath);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = item.fileName.replace(/\.(ppt|pptx)$/i, '.mp4');
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        } catch (error) {
            console.error('下载错误:', error);
            window.VidPPTUI.alert('下载失败: ' + error.message, { type: 'error' });
        }
    }

    handleDownloadByTaskId(taskId) {
        const found = this.getItemByTaskId(taskId);
        if (!found) {
            window.VidPPTUI.alert('没有可下载的视频', { type: 'warning' });
            return;
        }
        this.handleDownload(found.index);
    }

    _artifactLinks(item) {
        const artifacts = [
            ['课程 JSON', item.courseJsonPath],
            ['可编辑 PPT', item.presentationPath],
            ['字幕 SRT', item.subtitlesPath],
            ['课程视频', item.videoPath]
        ].filter(([, path]) => path);
        const segmentLinks = (item.videoSegments || [])
            .filter(segment => segment.video_path)
            .map(segment => [
                `第 ${segment.id} 段`,
                segment.video_path,
                `${segment.start_page}-${segment.end_page}`
            ]);
        if (!artifacts.length && !segmentLinks.length) return '';
        return `<div class="artifact-links">${artifacts.map(([label, path]) =>
            `<a class="artifact-link" href="/api/download?task_id=${encodeURIComponent(item.taskId)}&path=${encodeURIComponent(path)}">${label}</a>`
        ).join('')}${segmentLinks.map(([label, path, range]) =>
            `<a class="artifact-link segment-artifact-link" href="/api/download?task_id=${encodeURIComponent(item.taskId)}&path=${encodeURIComponent(path)}">${label} · ${range} 页</a>`
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
        window.VidPPTUI?.toast(message, { type: type === 'success' ? 'success' : 'error' });
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
                    status: this._taskStatus(t.status),
                    percentage: t.percentage || 0,
                    stagePercentage: t.stage_percentage || 0,
                    stage: t.stage,
                    message: t.message || '',
                    videoPath: t.video_path || null,
                    courseJsonPath: t.course_json_path || null,
                    presentationPath: t.presentation_path || null,
                    subtitlesPath: t.subtitles_path || null,
                    videoSegments: t.video_segments || [],
                    previewPath: t.preview_path || null,
                    error: t.error || null,
                    queuePosition: t.queue_position || null,
                    selected: false,
                    strategy: t.strategy || null,
                    strategySource: t.strategy_source || 'batch',
                    ownerUsername: t.owner_username || t.created_by || '-',
                    createdAt: t.created_at || null,
                    startedAt: t.started_at || null,
                    stageStartedAt: t.stage_started_at || null,
                    updatedAt: t.updated_at || null,
                    completedAt: t.completed_at || null
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
                const requestedTaskId = this.requestedPreviewTaskId();
                const awaiting = this.state.files.find(item => item.status === 'awaiting_confirmation');
                if (!requestedTaskId && awaiting) this.loadCoursePreview(awaiting.taskId);
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
            let changed = false;
            for (const task of data.tasks || []) {
                const found = this.getItemByTaskId(task.task_id);
                if (!found) continue;
                changed = this.updateItem(found.index, {
                    status: this._taskStatus(task.status),
                    stage: task.stage || null,
                    percentage: task.percentage || 0,
                    stagePercentage: task.stage_percentage || 0,
                    message: task.message || '',
                    videoPath: task.video_path || null,
                    error: task.error || null,
                    queuePosition: task.queue_position || null,
                    strategy: task.strategy || found.item.strategy,
                    strategySource: task.strategy_source || found.item.strategySource,
                    ownerUsername: task.owner_username || task.created_by || found.item.ownerUsername,
                    createdAt: task.created_at || found.item.createdAt,
                    startedAt: task.started_at || found.item.startedAt,
                    stageStartedAt: task.stage_started_at || found.item.stageStartedAt,
                    updatedAt: task.updated_at || found.item.updatedAt,
                    completedAt: task.completed_at || found.item.completedAt
                }) || changed;
            }
            if (changed) {
                this.renderFileList();
                this.renderResultsGrid();
                this.updateBatchSummary();
            }
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
            this.renderCoursePreview(
                taskId,
                data.pages || [],
                data.lesson_segments || [],
                data.duration_estimate || null
            );
        } catch (error) {
            this.showStatus('error', error.message);
        }
    }

    renderCoursePreview(taskId, pages, lessonSegments = [], durationEstimate = null) {
        const { coursePreviewModule, coursePreviewPages, coursePreviewSaveState } = this.elements;
        clearTimeout(this.previewAutoSaveTimer);
        this.stopCoursePreviewPlayback(
            '从当前页开始，按页图、讲稿、字幕和配音预览课程效果'
        );
        this.smartCutSegments = lessonSegments;
        this.smartCutApplied = this.smartCutSegments.length > 0;
        this.elements.continueCourseBtn.disabled = false;
        coursePreviewModule.dataset.taskId = taskId;
        this.elements.downloadEditablePptBtn.href = `/api/course-presentation/${taskId}`;
        coursePreviewPages.innerHTML = '';
        this.elements.previewPageSelect.innerHTML = '';
        pages.forEach(page => {
            const card = document.createElement('article');
            card.className = 'course-preview-page';
            card.dataset.pageNumber = page.page_number;
            const segment = page.lesson_segment;
            const segmentLabel = segment
                ? `<span class="course-preview-segment">第 ${segment.id} 段 · ${this._esc(segment.title || '')}</span>`
                : '';
            card.innerHTML = `
                <div class="course-preview-slide-canvas">
                    <img class="course-preview-image" src="${page.image_url}" alt="第 ${page.page_number} 页">
                    <div class="subtitle-safe-area" aria-hidden="true"></div>
                    <div class="course-preview-subtitle-overlay">
                        <img class="course-preview-subtitle-sample" alt="字幕预览">
                    </div>
                    <div class="subtitle-risk-badge ok">
                        <span class="subtitle-risk-message">字幕区待检测</span>
                        <button type="button" class="subtitle-risk-apply" hidden>应用推荐</button>
                    </div>
                </div>
                <div class="course-preview-page-player">
                    <button type="button" class="btn-preview course-preview-page-play">播放本页预览</button>
                    <button type="button" class="btn-secondary course-preview-page-stop" disabled>停止</button>
                    <span class="course-preview-page-player-status">使用本页讲稿预览 PPT、字幕和配音</span>
                </div>
                <div class="course-preview-editor">
                    <div class="course-preview-page-title">第 ${page.page_number} 页 · ${this._esc(page.title || '')}${segmentLabel}</div>
                    <textarea class="course-preview-script" aria-label="第 ${page.page_number} 页讲稿">${this._esc(page.script || '')}</textarea>
                    <div class="course-preview-page-meta">
                        <span class="course-preview-length"></span>
                        <div class="course-preview-page-actions">
                            <label class="page-reviewed-control">
                                <input type="checkbox" class="page-reviewed" ${page.reviewed ? 'checked' : ''}>
                                已审核
                            </label>
                            <button type="button" class="page-retry-tts-button">重配本页</button>
                        </div>
                    </div>
                </div>
            `;
            const textarea = card.querySelector('textarea');
            card.dataset.estimatedSeconds = String(
                Number(page.estimated_seconds)
                || this.estimatePreviewScriptSeconds(textarea.value)
            );
            const updateLength = () => {
                const length = textarea.value.trim().length;
                const seconds = this.estimatePreviewScriptSeconds(textarea.value);
                card.dataset.estimatedSeconds = String(seconds);
                card.querySelector('.course-preview-length').textContent =
                    `${length} 字 · 预计 ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
                this.updatePageSubtitleSample(card);
                this.updateCourseDurationEstimate();
            };
            updateLength();
            card.querySelector('.course-preview-image').addEventListener(
                'load',
                () => this.evaluateSubtitleRisk(card)
            );
            card.querySelector('.subtitle-risk-apply')?.addEventListener('click', event => {
                const recommendation = event.currentTarget.dataset.recommendation;
                this.applySubtitleRecommendation(recommendation);
            });
            textarea.addEventListener('input', () => {
                this.stopCoursePreviewPlayback();
                updateLength();
                this.evaluateSubtitleRisk(card);
                coursePreviewSaveState.textContent = '等待自动保存…';
                coursePreviewSaveState.classList.remove('saved');
                clearTimeout(this.previewAutoSaveTimer);
                this.previewAutoSaveTimer = setTimeout(
                    () => this.savePreviewScripts({ automatic: true }),
                    1200
                );
            });
            card.querySelector('.course-preview-page-play').addEventListener(
                'click', () => this.startCoursePreviewPlayback(page.page_number)
            );
            card.querySelector('.course-preview-page-stop').addEventListener(
                'click', () => this.stopCoursePreviewPlayback()
            );
            card.querySelector('.page-reviewed').addEventListener('change', () => {
                coursePreviewSaveState.textContent = '等待自动保存…';
                coursePreviewSaveState.classList.remove('saved');
                this.filterPreviewPages();
                clearTimeout(this.previewAutoSaveTimer);
                this.previewAutoSaveTimer = setTimeout(
                    () => this.savePreviewScripts({ automatic: true }),
                    400
                );
            });
            card.querySelector('.page-retry-tts-button').addEventListener(
                'click',
                event => this.retryTaskStage(taskId, 'page_tts', page.page_number, event.currentTarget)
            );
            this.bindCourseSubtitleOverlayDrag(card.querySelector('.course-preview-subtitle-overlay'));
            coursePreviewPages.appendChild(card);

            const option = document.createElement('option');
            option.value = page.page_number;
            option.textContent = `第 ${page.page_number} 页 · ${page.title || '未命名'}`;
            this.elements.previewPageSelect.appendChild(option);
        });
        this.renderSmartCutSegments();
        this.updateCourseDurationEstimate(durationEstimate);
        this.currentPreviewPage = Number(pages[0]?.page_number || 1);
        this.updatePreviewNavigation();
        coursePreviewSaveState.textContent = '修改将自动保存';
        coursePreviewModule.hidden = false;
        this.syncSubtitlePreviewFromInputs();
        this.refreshSubtitleRiskChecks();
        coursePreviewModule.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    updatePageSubtitleSample(card) {
        const text = card.querySelector('.course-preview-script')?.value || '';
        const sample = this.makeSubtitleSample(text);
        this.renderSubtitlePreviewImage(card, sample || '本页暂无字幕文本');
    }

    renderSubtitlePreviewImage(card, text) {
        const sampleNode = card?.querySelector('.course-preview-subtitle-sample');
        if (!sampleNode) return;
        const styleKey = [
            this.elements.subtitleFontName.value || 'Noto Sans CJK SC',
            Number(this.elements.subtitleFontSize.value) || 46,
            this.elements.subtitleColor.value || '#ffffff',
            Number(this.elements.subtitleOutlineWidth.value) || 0,
            this.elements.subtitleOutlineColor.value || '#000000',
            Number(this.elements.subtitleWidth.value) || 1728,
            Number(this.elements.subtitleHeight.value) || 110
        ].join('|');
        if (sampleNode.dataset.previewText === text && sampleNode.dataset.previewStyle === styleKey) {
            return;
        }
        sampleNode.dataset.previewText = text;
        sampleNode.dataset.previewStyle = styleKey;
        const params = new URLSearchParams({
            text: text || '本页暂无字幕文本',
            font: this.elements.subtitleFontName.value || 'Noto Sans CJK SC',
            font_size: String(Number(this.elements.subtitleFontSize.value) || 46),
            color: this.elements.subtitleColor.value || '#ffffff',
            outline_width: String(Number(this.elements.subtitleOutlineWidth.value) || 0),
            outline_color: this.elements.subtitleOutlineColor.value || '#000000',
            width: String(Number(this.elements.subtitleWidth.value) || 1728),
            height: String(Number(this.elements.subtitleHeight.value) || 110)
        });
        sampleNode.src = `/api/subtitle-preview-image?${params.toString()}`;
        sampleNode.alt = text || '字幕预览';
    }

    makeSubtitleSample(text) {
        const clean = String(text || '')
            .replace(/\s+/g, '')
            .replace(/[“”"']/g, '')
            .trim();
        if (!clean) return '';
        const parts = [];
        let buffer = '';
        for (const char of clean) {
            buffer += char;
            if ('。！？!?；;，,'.includes(char)) {
                parts.push(buffer);
                buffer = '';
            }
        }
        if (buffer) parts.push(buffer);
        const first = (parts.find(part => part.length >= 8) || parts[0] || clean).trim();
        return first.slice(0, 48);
    }

    refreshSubtitleRiskChecks() {
        this.elements.coursePreviewPages
            ?.querySelectorAll('.course-preview-page')
            .forEach(card => this.evaluateSubtitleRisk(card));
    }

    evaluateSubtitleRisk(card) {
        const canvas = card.querySelector('.course-preview-slide-canvas');
        const img = card.querySelector('.course-preview-image');
        const badge = card.querySelector('.subtitle-risk-badge');
        const messageNode = card.querySelector('.subtitle-risk-message');
        const applyButton = card.querySelector('.subtitle-risk-apply');
        if (!canvas || !img || !badge || !messageNode || !img.complete || !img.naturalWidth) return;

        const x = Number(this.elements.subtitleX.value) || 0;
        const y = Number(this.elements.subtitleY.value) || 0;
        const width = Number(this.elements.subtitleWidth.value) || 1920;
        const height = Number(this.elements.subtitleHeight.value) || 110;
        const fontSize = Number(this.elements.subtitleFontSize.value) || 46;
        const text = card.querySelector('.course-preview-script')?.value || '';
        const textLength = this.makeSubtitleSample(text).length;
        const areaDensity = this.measureImageRegionDensity(img, x, y, width, height);
        if (areaDensity === null) {
            messageNode.textContent = '字幕区检测不可用';
            badge.className = 'subtitle-risk-badge warn';
            if (applyButton) applyButton.hidden = true;
            canvas.classList.add('subtitle-risk-medium');
            canvas.classList.remove('subtitle-risk-high');
            return;
        }

        const lineCapacity = Math.max(8, Math.floor(width / Math.max(1, fontSize)));
        const estimatedLines = Math.max(1, Math.ceil(textLength / lineCapacity));
        const lineHeight = fontSize * 1.25;
        const needsHeight = estimatedLines * lineHeight + 24;
        let level = 'ok';
        let message = '字幕区清晰';
        if (areaDensity > 0.28) {
            level = 'danger';
            message = '底部内容密集，建议上移';
        } else if (areaDensity > 0.16) {
            level = 'warn';
            message = '字幕区有内容，注意遮挡';
        }
        if (needsHeight > height) {
            level = level === 'danger' ? 'danger' : 'warn';
            message = '字幕框偏矮，可能挤压文字';
        }
        if (fontSize < 42) {
            level = level === 'danger' ? 'danger' : 'warn';
            message = '字号偏小，小窗观看不稳';
        }
        const recommendation = this.pickSubtitleRecommendation(img);
        if (level !== 'ok' && recommendation) {
            message = `${message} · 推荐${recommendation.label}`;
        }
        messageNode.textContent = message;
        badge.className = `subtitle-risk-badge ${level === 'danger' ? 'danger' : level === 'warn' ? 'warn' : 'ok'}`;
        if (applyButton) {
            applyButton.hidden = level === 'ok' || !recommendation;
            applyButton.dataset.recommendation = recommendation?.key || '';
        }
        canvas.classList.toggle('subtitle-risk-medium', level === 'warn');
        canvas.classList.toggle('subtitle-risk-high', level === 'danger');
    }

    pickSubtitleRecommendation(img) {
        if (!img?.complete || !img.naturalWidth) return null;
        const candidates = [
            { key: 'course', label: '标准底部双行', ...this.subtitlePresets.course },
            { key: 'safe', label: '中下避让', ...this.subtitlePresets.safe },
            { key: 'top', label: '顶部字幕', ...this.subtitlePresets.top },
            { key: 'lowerMiddle', label: '中部偏下', ...this.subtitlePresets.lowerMiddle },
            { key: 'compact', label: '紧凑单行', ...this.subtitlePresets.compact }
        ];
        const current = {
            x: Number(this.elements.subtitleX.value),
            y: Number(this.elements.subtitleY.value),
            width: Number(this.elements.subtitleWidth.value),
            height: Number(this.elements.subtitleHeight.value),
            fontSize: Number(this.elements.subtitleFontSize.value)
        };
        const scored = candidates
            .filter(candidate => !(
                candidate.x === current.x &&
                candidate.y === current.y &&
                candidate.width === current.width &&
                candidate.height === current.height &&
                candidate.fontSize === current.fontSize
            ))
            .map(candidate => ({
                ...candidate,
                density: this.measureImageRegionDensity(
                    img,
                    candidate.x,
                    candidate.y,
                    candidate.width,
                    candidate.height
                )
            }))
            .filter(candidate => Number.isFinite(candidate.density));
        if (!scored.length) return null;
        scored.sort((left, right) => left.density - right.density);
        return scored[0];
    }

    applySubtitleRecommendation(key) {
        if (!key || !this.subtitlePresets?.[key]) return;
        this.applySubtitlePreset(key);
        this.syncSubtitlePresetSelection();
        this.saveCurrentStrategy();
    }

    measureImageRegionDensity(img, x, y, width, height) {
        try {
            const probe = document.createElement('canvas');
            const probeWidth = 96;
            const probeHeight = Math.max(12, Math.round(probeWidth * height / Math.max(1, width)));
            probe.width = probeWidth;
            probe.height = probeHeight;
            const ctx = probe.getContext('2d', { willReadFrequently: true });
            if (!ctx) return null;
            ctx.drawImage(
                img,
                x / 1920 * img.naturalWidth,
                y / 1080 * img.naturalHeight,
                width / 1920 * img.naturalWidth,
                height / 1080 * img.naturalHeight,
                0,
                0,
                probeWidth,
                probeHeight
            );
            const { data } = ctx.getImageData(0, 0, probeWidth, probeHeight);
            let active = 0;
            const total = data.length / 4;
            for (let i = 0; i < data.length; i += 4) {
                const red = data[i];
                const green = data[i + 1];
                const blue = data[i + 2];
                const max = Math.max(red, green, blue);
                const min = Math.min(red, green, blue);
                const contrast = max - min;
                const luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue;
                if (contrast > 24 || (luminance > 35 && luminance < 235)) active += 1;
            }
            return active / Math.max(1, total);
        } catch (error) {
            console.debug('字幕区域检测失败:', error);
            return null;
        }
    }

    bindCourseSubtitleOverlayDrag(overlay) {
        if (!overlay) return;
        const canvas = overlay.closest('.course-preview-slide-canvas');
        if (!canvas) return;
        let dragOffset = { x: 0, y: 0 };
        overlay.addEventListener('pointerdown', event => {
            event.preventDefault();
            const overlayRect = overlay.getBoundingClientRect();
            dragOffset = {
                x: event.clientX - overlayRect.left,
                y: event.clientY - overlayRect.top
            };
            overlay.setPointerCapture(event.pointerId);
        });
        overlay.addEventListener('pointermove', event => {
            if (!overlay.hasPointerCapture(event.pointerId)) return;
            const canvasRect = canvas.getBoundingClientRect();
            const width = Number(this.elements.subtitleWidth.value) || 1;
            const height = Number(this.elements.subtitleHeight.value) || 1;
            const x = Math.round(
                (event.clientX - canvasRect.left - dragOffset.x) / canvasRect.width * 1920
            );
            const y = Math.round(
                (event.clientY - canvasRect.top - dragOffset.y) / canvasRect.height * 1080
            );
            this.elements.subtitleX.value = Math.max(0, Math.min(1920 - width, x));
            this.elements.subtitleY.value = Math.max(0, Math.min(1080 - height, y));
            this.syncSubtitlePreviewFromInputs();
            this.saveCurrentStrategy();
        });
        overlay.addEventListener('pointerup', event => {
            if (overlay.hasPointerCapture(event.pointerId)) {
                overlay.releasePointerCapture(event.pointerId);
            }
        });
        overlay.addEventListener('pointercancel', event => {
            if (overlay.hasPointerCapture(event.pointerId)) {
                overlay.releasePointerCapture(event.pointerId);
            }
        });
    }

    async startCoursePreviewPlayback(startPage = this.currentPreviewPage) {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        if (!taskId) return;
        if (!await this.savePreviewScripts({ automatic: true })) return;
        this.stopVoicePreview();
        this.coursePreviewPlaying = true;
        this.currentPreviewPage = Number(startPage) || this.currentPreviewPage;
        this.updateCoursePreviewPagePlayerState(this.currentPreviewPage, '准备预览…');
        await this.playCoursePreviewPage(this.currentPreviewPage);
    }

    stopCoursePreviewPlayback(message = '预览已停止') {
        this.coursePreviewPlaying = false;
        if (this.coursePreviewAudio) {
            this.coursePreviewAudio.pause();
            this.coursePreviewAudio.removeAttribute('src');
            this.coursePreviewAudio.load();
            this.coursePreviewAudio = null;
        }
        this.clearCoursePreviewSubtitlePlayback();
        this.updateCoursePreviewPagePlayerState(null, message);
    }

    async playCoursePreviewPage(pageNumber) {
        if (!this.coursePreviewPlaying) return;
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        const card = this.previewCardByPage(pageNumber);
        if (!taskId || !card) {
            this.stopCoursePreviewPlayback('预览已结束');
            return;
        }
        this.goToPreviewPage(pageNumber, { focusEditor: false });
        const script = card.querySelector('.course-preview-script')?.value || '';
        const title = card.querySelector('.course-preview-page-title')?.textContent?.trim()
            || `第 ${pageNumber} 页`;
        this.updateCoursePreviewPagePlayerState(pageNumber, '准备配音…');
        try {
            const response = await fetch(`/api/course-preview/${taskId}/page-audio`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    page_number: pageNumber,
                    script
                })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '预览音频生成失败');
            if (!this.coursePreviewPlaying) return;
            await this.playCoursePreviewAudio(data.audio_url, pageNumber, title);
        } catch (error) {
            this.stopCoursePreviewPlayback('预览失败');
            this.showStatus('error', error.message);
        }
    }

    async playCoursePreviewAudio(audioUrl, pageNumber, title) {
        if (this.coursePreviewAudio) {
            this.coursePreviewAudio.pause();
        }
        const audio = new Audio(audioUrl);
        this.coursePreviewAudio = audio;
        const card = this.previewCardByPage(pageNumber);
        const cues = this.makeSubtitleCues(
            card?.querySelector('.course-preview-script')?.value || ''
        );
        this.activateCoursePreviewSubtitles(card, cues);
        this.updateCoursePreviewPagePlayerState(pageNumber, '正在播放本页');
        audio.addEventListener('timeupdate', () => {
            this.syncPlayingSubtitleCue(audio, card, cues);
        });
        audio.addEventListener('loadedmetadata', () => {
            this.syncPlayingSubtitleCue(audio, card, cues);
        }, { once: true });
        audio.addEventListener('ended', () => {
            this.clearCoursePreviewSubtitlePlayback(card);
            const nextPage = this.nextPreviewPageNumber(pageNumber);
            if (nextPage) {
                this.playCoursePreviewPage(nextPage);
            } else {
                this.stopCoursePreviewPlayback('课程预览播放完成');
            }
        }, { once: true });
        audio.addEventListener('error', () => {
            this.stopCoursePreviewPlayback('预览音频播放失败');
            this.showStatus('error', '预览音频播放失败');
        }, { once: true });
        await audio.play();
    }

    updateCoursePreviewPagePlayerState(activePageNumber = null, status = '') {
        this.elements.coursePreviewPages
            ?.querySelectorAll('.course-preview-page')
            .forEach(card => {
                const isActive = this.coursePreviewPlaying
                    && Number(card.dataset.pageNumber) === Number(activePageNumber);
                const playButton = card.querySelector('.course-preview-page-play');
                const stopButton = card.querySelector('.course-preview-page-stop');
                const statusNode = card.querySelector('.course-preview-page-player-status');
                card.classList.toggle('preview-audio-active', isActive);
                if (playButton) {
                    playButton.disabled = isActive;
                    playButton.textContent = isActive ? '正在预览' : '播放本页预览';
                }
                if (stopButton) stopButton.disabled = !isActive;
                if (statusNode) {
                    statusNode.textContent = isActive
                        ? status
                        : '使用本页讲稿预览 PPT、字幕和配音';
                }
            });
    }

    activateCoursePreviewSubtitles(card, cues) {
        this.clearCoursePreviewSubtitlePlayback();
        if (!card) return;
        this.coursePreviewSubtitlePage = card;
        card.classList.add('playing-preview');
        this.renderSubtitlePreviewImage(card, cues[0] || '本页暂无字幕文本');
    }

    clearCoursePreviewSubtitlePlayback(card = null) {
        const target = card || this.coursePreviewSubtitlePage;
        if (target) {
            target.classList.remove('playing-preview');
            this.updatePageSubtitleSample(target);
        }
        if (!card) {
            this.coursePreviewSubtitlePage = null;
        }
    }

    syncPlayingSubtitleCue(audio, card, cues) {
        if (!card || !cues.length) return;
        const duration = Number.isFinite(audio.duration) && audio.duration > 0
            ? audio.duration
            : Math.max(1, cues.length);
        const index = Math.min(
            cues.length - 1,
            Math.max(0, Math.floor(audio.currentTime / duration * cues.length))
        );
        this.renderSubtitlePreviewImage(card, cues[index] || cues[0] || '');
    }

    makeSubtitleCues(text) {
        const clean = String(text || '').replace(/\s+/g, '').trim();
        if (!clean) return [];
        const maxCueChars = 28;
        const minCueChars = 6;
        const phrases = this.splitSubtitlePhrases(clean);
        let buffer = '';
        const chunks = [];
        phrases.forEach(phrase => {
            if ((buffer + phrase).length <= maxCueChars) {
                buffer += phrase;
                return;
            }
            if (buffer) {
                chunks.push(buffer);
                buffer = '';
            }
            const pieces = this.splitLongSubtitlePhrase(phrase, maxCueChars, minCueChars);
            chunks.push(...pieces.slice(0, -1));
            buffer = pieces[pieces.length - 1] || '';
        });
        if (buffer) chunks.push(buffer);
        return chunks.reduce((result, chunk) => {
            const last = result[result.length - 1];
            if (last && chunk.length < minCueChars && (last + chunk).length <= maxCueChars) {
                result[result.length - 1] = last + chunk;
            } else {
                result.push(chunk);
            }
            return result;
        }, []);
    }

    splitSubtitlePhrases(text) {
        const phrasePattern = /[^。！？!?；;：:，,、]+[。！？!?；;：:，,、]?/g;
        const phrases = text.match(phrasePattern) || [text];
        return phrases.flatMap(phrase => (
            phrase.length <= 28
                ? [phrase]
                : this.splitAfterSubtitleConnectors(phrase)
        ));
    }

    splitAfterSubtitleConnectors(text) {
        const connectors = [
            '并且', '同时', '因此', '所以', '但是', '而且', '以及', '然后',
            '例如', '比如', '其中', '对于', '通过', '围绕', '基于'
        ];
        const parts = [];
        let start = 0;
        let index = 0;
        while (index < text.length) {
            const matched = connectors.find(connector => text.startsWith(connector, index));
            if (matched) {
                const end = index + matched.length;
                parts.push(text.slice(start, end));
                start = end;
                index = end;
            } else {
                index += 1;
            }
        }
        if (start < text.length) parts.push(text.slice(start));
        return parts.filter(Boolean);
    }

    splitLongSubtitlePhrase(text, limit, minCueChars) {
        let phrase = text;
        const chunks = [];
        while (phrase.length > limit) {
            const splitAt = this.bestSubtitleSplitIndex(phrase, limit, minCueChars);
            chunks.push(phrase.slice(0, splitAt));
            phrase = phrase.slice(splitAt);
        }
        if (phrase) chunks.push(phrase);
        return chunks;
    }

    bestSubtitleSplitIndex(text, limit, minCueChars) {
        const window = text.slice(0, limit);
        for (const marks of ['，,、：:', '的地得在和与及或并而']) {
            let splitAt = -1;
            for (const mark of marks) {
                splitAt = Math.max(splitAt, window.lastIndexOf(mark) + 1);
            }
            if (splitAt >= minCueChars) {
                return splitAt;
            }
        }
        return limit;
    }

    previewCardByPage(pageNumber) {
        return Array.from(
            this.elements.coursePreviewPages.querySelectorAll('.course-preview-page')
        ).find(card => Number(card.dataset.pageNumber) === Number(pageNumber));
    }

    nextPreviewPageNumber(pageNumber) {
        const pages = Array.from(this.elements.previewPageSelect.options)
            .map(option => Number(option.value))
            .filter(value => Number.isFinite(value));
        const index = pages.indexOf(Number(pageNumber));
        return index >= 0 ? pages[index + 1] : null;
    }

    goToPreviewPage(pageNumber, options = {}) {
        const cards = Array.from(
            this.elements.coursePreviewPages.querySelectorAll('.course-preview-page')
        );
        const target = cards.find(card => Number(card.dataset.pageNumber) === pageNumber);
        if (!target) return;
        this.currentPreviewPage = pageNumber;
        this.updatePreviewNavigation();
        target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        if (options.focusEditor !== false) {
            target.querySelector('textarea')?.focus({ preventScroll: true });
        }
    }

    updatePreviewNavigation() {
        const total = this.elements.previewPageSelect.options.length;
        this.elements.previewPageSelect.value = String(this.currentPreviewPage);
        this.elements.coursePreviewPosition.textContent =
            total ? `第 ${this.currentPreviewPage} / ${total} 页` : '';
        this.elements.previewPreviousBtn.disabled = this.currentPreviewPage <= 1;
        this.elements.previewNextBtn.disabled = this.currentPreviewPage >= total;
    }

    collectPreviewScripts() {
        return Array.from(this.elements.coursePreviewPages.querySelectorAll('.course-preview-page')).map(card => ({
            page_number: Number(card.dataset.pageNumber),
            script: card.querySelector('.course-preview-script').value,
            reviewed: card.querySelector('.page-reviewed').checked
        }));
    }

    filterPreviewPages() {
        const onlyUnreviewed = this.elements.unreviewedOnly.checked;
        this.elements.coursePreviewPages.querySelectorAll('.course-preview-page').forEach(card => {
            card.hidden = onlyUnreviewed && card.querySelector('.page-reviewed').checked;
        });
    }

    estimatePreviewScriptSeconds(text) {
        const length = String(text || '').trim().length;
        return Math.max(15, Math.round(length / 4));
    }

    formatCourseDuration(seconds) {
        const value = Math.max(0, Math.round(Number(seconds) || 0));
        const hours = Math.floor(value / 3600);
        const minutes = Math.floor((value % 3600) / 60);
        const rest = value % 60;
        if (hours > 0) {
            return `约 ${hours} 小时 ${minutes} 分 ${rest} 秒`;
        }
        if (minutes > 0) {
            return `约 ${minutes} 分 ${rest} 秒`;
        }
        return `约 ${rest} 秒`;
    }

    collectPreviewPageDurations() {
        return Array.from(this.elements.coursePreviewPages.querySelectorAll('.course-preview-page'))
            .map(card => ({
                pageNumber: Number(card.dataset.pageNumber),
                seconds: Number(card.dataset.estimatedSeconds)
                    || this.estimatePreviewScriptSeconds(
                        card.querySelector('.course-preview-script')?.value || ''
                    )
            }))
            .filter(page => Number.isFinite(page.pageNumber));
    }

    updateCourseDurationEstimate(serverEstimate = null) {
        const { courseDurationTotal, courseDurationSegments } = this.elements;
        if (!courseDurationTotal || !courseDurationSegments) return;

        const pageDurations = this.collectPreviewPageDurations();
        const totalSeconds = pageDurations.length
            ? pageDurations.reduce((sum, page) => sum + page.seconds, 0)
            : Number(serverEstimate?.total_seconds || 0);
        courseDurationTotal.textContent = this.formatCourseDuration(totalSeconds);

        const segments = this.smartCutSegments.length
            ? this.collectSmartCutSegments()
            : [];
        courseDurationSegments.innerHTML = '';
        courseDurationSegments.hidden = !segments.length;
        segments.forEach((segment, index) => {
            const segmentSeconds = pageDurations
                .filter(page => (
                    page.pageNumber >= Number(segment.start_page)
                    && page.pageNumber <= Number(segment.end_page)
                ))
                .reduce((sum, page) => sum + page.seconds, 0);
            const row = document.createElement('div');
            row.className = 'course-duration-segment';
            row.innerHTML = `
                <span>第 ${index + 1} 段 · ${this._esc(segment.title || `第 ${index + 1} 课`)}（${segment.start_page}-${segment.end_page} 页）</span>
                <strong>${this.formatCourseDuration(segmentSeconds)}</strong>
            `;
            courseDurationSegments.appendChild(row);
        });
    }

    getSmartCutPriority() {
        return document.querySelector('input[name="cut-priority"]:checked')?.value || 'section';
    }

    renderSmartCutSegments() {
        const { smartCutList, smartCutSummary, smartCutApplyBtn } = this.elements;
        if (!smartCutList || !smartCutSummary || !smartCutApplyBtn) return;
        smartCutList.innerHTML = '';
        if (!this.smartCutSegments.length) {
            smartCutSummary.textContent = '尚未生成切课建议，可跳过切课直接继续生成完整视频';
            smartCutApplyBtn.disabled = true;
            this.updateContinueCourseLabel();
            this.updateCourseDurationEstimate();
            return;
        }
        smartCutSummary.textContent = this.smartCutApplied
            ? `已应用 ${this.smartCutSegments.length} 段，继续生成将输出完整 MP4 和分段 MP4`
            : `已生成 ${this.smartCutSegments.length} 段建议，应用后将额外输出分段 MP4`;
        this.smartCutSegments.forEach((segment, index) => {
            const row = document.createElement('div');
            row.className = 'smart-cut-row';
            row.innerHTML = `
                <span class="smart-cut-index">${index + 1}</span>
                <input type="text" class="smart-cut-title"
                       value="${this._escAttr(segment.title || `第 ${index + 1} 课`)}"
                       aria-label="第 ${index + 1} 段标题">
                <input type="number" class="smart-cut-start" min="1"
                       value="${Number(segment.start_page) || 1}"
                       aria-label="第 ${index + 1} 段起始页">
                <span class="smart-cut-dash">-</span>
                <input type="number" class="smart-cut-end" min="1"
                       value="${Number(segment.end_page) || 1}"
                       aria-label="第 ${index + 1} 段结束页">
                <span class="smart-cut-estimate">约 ${segment.estimated_minutes || '?'} 分钟</span>
            `;
            row.querySelectorAll('input').forEach(input => {
                input.addEventListener('input', () => {
                    this.smartCutApplied = false;
                    smartCutApplyBtn.disabled = false;
                    this.updateContinueCourseLabel();
                    this.updateCourseDurationEstimate();
                });
            });
            smartCutList.appendChild(row);
        });
        smartCutApplyBtn.disabled = this.smartCutApplied;
        this.updateContinueCourseLabel();
        this.updateCourseDurationEstimate();
    }

    updateContinueCourseLabel() {
        const text = this.elements.continueCourseBtn?.querySelector('.btn-text');
        if (!text) return;
        text.textContent = this.smartCutApplied ? '继续生成视频（含分段）' : '跳过切课并继续生成视频';
    }

    collectSmartCutSegments() {
        return Array.from(this.elements.smartCutList.querySelectorAll('.smart-cut-row')).map((row, index) => ({
            id: index + 1,
            title: row.querySelector('.smart-cut-title').value.trim() || `第 ${index + 1} 课`,
            start_page: Number(row.querySelector('.smart-cut-start').value),
            end_page: Number(row.querySelector('.smart-cut-end').value)
        }));
    }

    async recommendSmartCuts() {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        if (!taskId) return;
        clearTimeout(this.previewAutoSaveTimer);
        await this.savePreviewScripts({ automatic: true });
        const button = this.elements.smartCutRecommendBtn;
        button.disabled = true;
        button.textContent = '分析中...';
        try {
            const response = await fetch(`/api/course-segments/${taskId}/recommend`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_minutes: Number(this.elements.cutDurationMinutes.value) || 5,
                    priority: this.getSmartCutPriority()
                })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '智能切课失败');
            this.smartCutSegments = data.segments || [];
            this.smartCutApplied = false;
            this.renderSmartCutSegments();
            this.showStatus('success', `已生成 ${this.smartCutSegments.length} 段切课建议`);
        } catch (error) {
            this.showStatus('error', error.message);
        } finally {
            button.disabled = false;
            button.textContent = '确定';
        }
    }

    async applySmartCuts() {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        if (!taskId) return;
        const segments = this.collectSmartCutSegments();
        if (!segments.length) return;
        clearTimeout(this.previewAutoSaveTimer);
        const button = this.elements.smartCutApplyBtn;
        button.disabled = true;
        button.textContent = '应用中...';
        try {
            const response = await fetch(`/api/course-segments/${taskId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ segments })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '应用切课失败');
            this.smartCutSegments = data.segments || [];
            this.smartCutApplied = this.smartCutSegments.length > 0;
            await this.loadCoursePreview(taskId);
            this.showStatus('success', data.message || '已应用智能切课');
        } catch (error) {
            this.showStatus('error', error.message);
        } finally {
            button.disabled = this.smartCutApplied;
            button.textContent = '应用';
        }
    }

    async savePreviewScripts({ automatic = false } = {}) {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        if (!taskId) return false;
        const sequence = ++this.previewSaveSequence;
        this.elements.coursePreviewSaveState.textContent = '保存中…';
        try {
            const response = await fetch(`/api/course-preview/${taskId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pages: this.collectPreviewScripts() })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '保存讲稿失败');
            if (sequence !== this.previewSaveSequence) return true;
            if (Array.isArray(data.lesson_segments)) {
                this.smartCutSegments = data.lesson_segments;
                this.renderSmartCutSegments();
            } else {
                this.updateCourseDurationEstimate(data.duration_estimate || null);
            }
            this.elements.coursePreviewSaveState.textContent = automatic ? '已自动保存' : '已保存';
            this.elements.coursePreviewSaveState.classList.add('saved');
            return true;
        } catch (error) {
            if (sequence !== this.previewSaveSequence) return false;
            this.elements.coursePreviewSaveState.textContent = '自动保存失败，请手动保存';
            this.elements.coursePreviewSaveState.classList.remove('saved');
            if (!automatic) this.showStatus('error', error.message);
            return false;
        }
    }

    async uploadEditedPresentation(file) {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        if (!taskId) return;
        if (!file.name.toLowerCase().endsWith('.pptx')) {
            this.showStatus('error', '请上传修改后的 PPTX 文件');
            return;
        }
        const button = this.elements.uploadEditedPptBtn;
        const originalText = button.textContent;
        const formData = new FormData();
        formData.append('presentation', file);
        button.disabled = true;
        button.textContent = '上传并重新渲染…';
        this.elements.continueCourseBtn.disabled = true;
        try {
            const response = await fetch(`/api/course-presentation/${taskId}`, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'PPT 更新失败');
            this.renderCoursePreview(taskId, data.pages || [], []);
            this.elements.coursePreviewSaveState.textContent = 'PPT 已更新';
            this.elements.coursePreviewSaveState.classList.add('saved');
        } catch (error) {
            this.elements.continueCourseBtn.disabled = false;
            this.showStatus('error', error.message);
        } finally {
            button.disabled = false;
            button.textContent = originalText;
        }
    }

    async continueCourse() {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        const found = this.getItemByTaskId(taskId);
        if (!taskId || !found) return;
        clearTimeout(this.previewAutoSaveTimer);
        this.stopCoursePreviewPlayback();
        const button = this.elements.continueCourseBtn;
        button.disabled = true;
        if (!this.smartCutApplied) {
            const hasDraftCuts = this.smartCutSegments.length > 0;
            const confirmed = await window.VidPPTUI.confirm(
                hasDraftCuts
                    ? '切课建议尚未应用，继续后只生成完整视频，不输出分段视频。是否继续？'
                    : '尚未应用智能切课，继续后只生成完整视频。是否继续？',
                {
                    title: '继续生成完整视频',
                    confirmText: '继续生成'
                }
            );
            if (!confirmed) {
                button.disabled = false;
                return;
            }
        }
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
                    ),
                    tts_rate: this.elements.ttsRate.value,
                    tts_emotion: this.elements.ttsEmotion.value,
                    tts_emotion_scale: Number(this.elements.ttsEmotionScale.value),
                    tts_sentence_pause: Number(this.elements.ttsSentencePause.value),
                    burn_subtitles: this.elements.burnSubtitles.checked,
                    ...this.collectSubtitleOptions()
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
        clearTimeout(this.previewAutoSaveTimer);
        this.stopCoursePreviewPlayback();

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
