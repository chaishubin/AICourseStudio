/* ==========================================================================
   AI Course Studio - 主JavaScript文件
   ========================================================================== */

class AICourseStudioApp {
    constructor() {
        this.state = {
            files: [],  // [{file, filePath, fileName, courseName, taskId, status, percentage, stage, message, videoPath, error}]
            isUploading: false,
            isConverting: false,
            activeBatchId: null,
            logoPath: null,
            packagingBackgroundPath: null,
            packagingMusicPath: null,
            packagingIntroVideoPath: null,
            packagingOutroVideoPath: null,
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

        window.addEventListener('beforeunload', event => {
            if (!this.previewDirty) return;
            event.preventDefault();
            event.returnValue = '';
        });
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
        this.currentAIReview = null;
        this.packagingLayout = this.defaultPackagingLayout();

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
                voiceGenderFilter: document.getElementById('voice-gender-filter'),
                voicePreviewList: document.getElementById('voice-preview-list'),
                customVoice: document.getElementById('custom-voice'),
                volcengineExpressionGroup: document.getElementById('volcengine-expression-group'),
                ttsEmotion: document.getElementById('tts-emotion'),
                ttsRate: document.getElementById('tts-rate'),
                ttsEmotionScale: document.getElementById('tts-emotion-scale'),
                ttsSentencePause: document.getElementById('tts-sentence-pause'),
                burnSubtitles: document.getElementById('burn-subtitles'),
                focusHighlight: document.getElementById('focus-highlight'),
                focusHighlightStyle: document.getElementById('focus-highlight-style'),
                focusHighlightColor: document.getElementById('focus-highlight-color'),
                focusHighlightWidth: document.getElementById('focus-highlight-width'),
                focusSmoothingSeconds: document.getElementById('focus-smoothing-seconds'),
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
                videoDefaultsReset: document.getElementById('video-defaults-reset'),
                videoAdvancedToggle: document.getElementById('video-advanced-toggle'),
                videoAdvancedOptions: document.getElementById('video-advanced-options'),
                videoResolution: document.getElementById('video-resolution'),
                videoFps: document.getElementById('video-fps'),
                videoPreset: document.getElementById('video-preset'),
                videoCrf: document.getElementById('video-crf'),
                videoCodec: document.getElementById('video-codec'),
                videoPixelFormat: document.getElementById('video-pixel-format'),
                videoProfile: document.getElementById('video-profile'),
                videoGopSeconds: document.getElementById('video-gop-seconds'),
                audioBitrate: document.getElementById('audio-bitrate'),
                audioSampleRate: document.getElementById('audio-sample-rate'),
                audioChannels: document.getElementById('audio-channels'),
                audioLoudnessLufs: document.getElementById('audio-loudness-lufs'),

                llmEnabled: document.getElementById('llm-enabled'),
                llmEngine: document.getElementById('llm-engine'),
                llmModeGroup: document.getElementById('llm-mode-group'),
                llmMode: document.getElementById('llm-mode'),
                refinementLevel: document.getElementById('refinement-level'),
                narrationStyle: document.getElementById('narration-style'),
                targetDurationMinutes: document.getElementById('target-duration-minutes'),
                teachingScenario: document.getElementById('teaching-scenario'),
                teachingAudience: document.getElementById('teaching-audience'),
                teachingPriorKnowledge: document.getElementById('teaching-prior-knowledge'),
                teachingTeachingGoal: document.getElementById('teaching-teaching-goal'),
                teachingExpressionStyle: document.getElementById('teaching-expression-style'),
                teachingDeliveryMode: document.getElementById('teaching-delivery-mode'),
                qualityMode: document.getElementById('quality-mode'),
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
                packagingTemplate: document.getElementById('packaging-template'),
                packagingOrganization: document.getElementById('packaging-organization'),
                packagingDepartment: document.getElementById('packaging-department'),
                packagingInstructor: document.getElementById('packaging-instructor'),
                packagingInstructorTitle: document.getElementById('packaging-instructor-title'),
                packagingDuration: document.getElementById('packaging-duration'),
                packagingTransitionSeconds: document.getElementById('packaging-transition-seconds'),
                packagingOutroText: document.getElementById('packaging-outro-text'),
                enableIntro: document.getElementById('enable-intro'),
                enableOutro: document.getElementById('enable-outro'),
                packagingApplySegments: document.getElementById('packaging-apply-segments'),
                packagingUseSlideBackground: document.getElementById('packaging-use-slide-background'),
                packagingEnableMotion: document.getElementById('packaging-enable-motion'),
                packagingEnableMusic: document.getElementById('packaging-enable-music'),
                packagingManageBtn: document.getElementById('packaging-manage-btn'),
                packagingManagerOverlay: document.getElementById('packaging-manager-overlay'),
                packagingManagerClose: document.getElementById('packaging-manager-close'),
                packagingPreviewRefresh: document.getElementById('packaging-preview-refresh'),
                packagingLayoutReset: document.getElementById('packaging-layout-reset'),
                packagingPreviewStatus: document.getElementById('packaging-preview-status'),
                packagingIntroPreview: document.getElementById('packaging-intro-preview'),
                packagingOutroPreview: document.getElementById('packaging-outro-preview'),
                packagingIntroLabel: document.getElementById('packaging-intro-label'),
                packagingIntroTitle: document.getElementById('packaging-intro-title'),
                packagingIntroSubtitle: document.getElementById('packaging-intro-subtitle'),
                packagingIntroDuration: document.getElementById('packaging-intro-duration'),
                packagingOutroTitle: document.getElementById('packaging-outro-title'),
                packagingOutroSubtitle: document.getElementById('packaging-outro-subtitle'),
                packagingOutroDuration: document.getElementById('packaging-outro-duration'),
                packagingAccentColor: document.getElementById('packaging-accent-color'),
                packagingBackgroundStyle: document.getElementById('packaging-background-style'),
                packagingLogoPosition: document.getElementById('packaging-logo-position'),
                packagingMotionStyle: document.getElementById('packaging-motion-style'),
                packagingMusicStyle: document.getElementById('packaging-music-style'),
                packagingBackgroundInput: document.getElementById('packaging-background-input'),
                packagingBackgroundButton: document.getElementById('packaging-background-button'),
                packagingBackgroundRemove: document.getElementById('packaging-background-remove'),
                packagingBackgroundStatus: document.getElementById('packaging-background-status'),
                packagingMusicInput: document.getElementById('packaging-music-input'),
                packagingMusicButton: document.getElementById('packaging-music-button'),
                packagingMusicRemove: document.getElementById('packaging-music-remove'),
                packagingMusicStatus: document.getElementById('packaging-music-status'),
                packagingMusicLibrary: document.getElementById('packaging-music-library'),
                packagingMusicPreview: document.getElementById('packaging-music-preview'),
                packagingIntroVideoInput: document.getElementById('packaging-intro-video-input'),
                packagingIntroVideoButton: document.getElementById('packaging-intro-video-button'),
                packagingIntroVideoRemove: document.getElementById('packaging-intro-video-remove'),
                packagingIntroVideoStatus: document.getElementById('packaging-intro-video-status'),
                packagingOutroVideoInput: document.getElementById('packaging-outro-video-input'),
                packagingOutroVideoButton: document.getElementById('packaging-outro-video-button'),
                packagingOutroVideoRemove: document.getElementById('packaging-outro-video-remove'),
                packagingOutroVideoStatus: document.getElementById('packaging-outro-video-status'),
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
                previewAutoplay: document.getElementById('preview-autoplay'),
                previewPlaybackDock: document.getElementById('preview-playback-dock'),
                previewPlaybackStatus: document.getElementById('preview-playback-status'),
                previewStopBtn: document.getElementById('preview-stop-btn'),
                previewLocateBtn: document.getElementById('preview-locate-btn'),
                previewPreviousBtn: document.getElementById('preview-previous-btn'),
                previewNextBtn: document.getElementById('preview-next-btn'),
                previewPageSelect: document.getElementById('preview-page-select'),
                unreviewedOnly: document.getElementById('unreviewed-only'),
                aiReviewPanel: document.getElementById('ai-review-panel'),
                aiReviewSummary: document.getElementById('ai-review-summary'),
                aiReviewMeta: document.getElementById('ai-review-meta'),
                aiReviewFindings: document.getElementById('ai-review-findings'),
                aiReviewSampleBtn: document.getElementById('ai-review-sample-btn'),
                aiReviewFullBtn: document.getElementById('ai-review-full-btn'),
                aiReviewFixAllBtn: document.getElementById('ai-review-fix-all-btn'),
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
        this.loadPackagingTemplates();
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

    defaultCourseName(fileName) {
        return String(fileName || '')
            .replace(/[\\/]+/g, '/')
            .split('/')
            .pop()
            .replace(/\.[^.]+$/, '')
            .trim() || 'course';
    }

    courseDisplayName(item) {
        return (item?.courseName || this.defaultCourseName(item?.fileName || '')).trim();
    }

    shouldShowInUploadList(item) {
        return item?.status !== 'completed';
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
        if (status === 'rendered') return 'completed';
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
            this.elements.videoResolution,
            this.elements.videoFps,
            this.elements.videoPreset,
            this.elements.videoCrf,
            this.elements.videoCodec,
            this.elements.videoPixelFormat,
            this.elements.videoProfile,
            this.elements.videoGopSeconds,
            this.elements.audioBitrate,
            this.elements.audioSampleRate,
            this.elements.audioChannels,
            this.elements.audioLoudnessLufs,
            this.elements.llmEnabled,
            this.elements.llmEngine,
            this.elements.llmMode,
            this.elements.refinementLevel,
            this.elements.teachingScenario,
            this.elements.teachingAudience,
            this.elements.teachingPriorKnowledge,
            this.elements.teachingTeachingGoal,
            this.elements.teachingExpressionStyle,
            this.elements.teachingDeliveryMode,
            this.elements.qualityMode,
            this.elements.visualTheme,
            this.elements.illustrationsEnabled,
            this.elements.maxIllustrations,
            this.elements.pptFooterText,
            this.elements.packagingTemplate,
            this.elements.packagingOrganization,
            this.elements.packagingInstructor,
            this.elements.packagingDuration,
            this.elements.packagingOutroText,
            this.elements.enableIntro,
            this.elements.enableOutro,
            this.elements.packagingApplySegments,
            this.elements.packagingUseSlideBackground,
            this.elements.packagingEnableMotion,
            this.elements.packagingEnableMusic,
            this.elements.packagingIntroLabel,
            this.elements.packagingIntroTitle,
            this.elements.packagingIntroSubtitle,
            this.elements.packagingIntroDuration,
            this.elements.packagingOutroTitle,
            this.elements.packagingOutroSubtitle,
            this.elements.packagingOutroDuration,
            this.elements.packagingAccentColor,
            this.elements.packagingBackgroundStyle,
            this.elements.packagingLogoPosition,
            this.elements.packagingMotionStyle,
            this.elements.packagingMusicStyle
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

    resetVideoDefaults() {
        document.querySelectorAll('.video-tuning-group select, .video-tuning-group input').forEach(control => {
            if (control.tagName === 'SELECT') {
                const defaultOption = Array.from(control.options).find(option => option.defaultSelected);
                control.value = (defaultOption || control.options[0]).value;
            } else {
                control.value = control.defaultValue;
            }
        });
        this.saveCurrentStrategy();
        window.VidPPTUI?.toast('视频合成参数已恢复默认', { type: 'success' });
    }

    bindSubtitleControls() {
        this.subtitlePresets = {
            course: { x: 128, y: 930, width: 1664, height: 72, fontSize: 38 },
            compact: { x: 160, y: 950, width: 1600, height: 64, fontSize: 34 },
            safe: { x: 160, y: 825, width: 1600, height: 72, fontSize: 36 },
            top: { x: 160, y: 88, width: 1600, height: 68, fontSize: 34 },
            lowerMiddle: { x: 160, y: 740, width: 1600, height: 72, fontSize: 36 }
        };
        this.subtitleStyleTemplates = {
            standard: {
                label: '标准网课 · 黑底白字',
                fontName: 'Noto Sans CJK SC',
                fontSize: 38,
                color: '#ffffff',
                backgroundColor: '#111111',
                backgroundOpacity: 0.48,
                outlineWidth: 0,
                outlineColor: '#000000'
            },
            lightSlide: {
                label: '浅色课件 · 深字浅底',
                fontName: 'Noto Sans CJK SC',
                fontSize: 38,
                color: '#172033',
                backgroundColor: '#ffffff',
                backgroundOpacity: 0.78,
                outlineWidth: 0,
                outlineColor: '#ffffff'
            },
            darkSlide: {
                label: '深色课件 · 高对比描边',
                fontName: 'Noto Sans CJK SC',
                fontSize: 38,
                color: '#ffffff',
                backgroundColor: '#000000',
                backgroundOpacity: 0.42,
                outlineWidth: 0.8,
                outlineColor: '#000000'
            },
            lectureSerif: {
                label: '理论讲授 · 宋体稳重',
                fontName: 'Noto Serif CJK SC',
                fontSize: 38,
                color: '#ffffff',
                backgroundColor: '#182033',
                backgroundOpacity: 0.54,
                outlineWidth: 0,
                outlineColor: '#000000'
            },
            codeDemo: {
                label: '实操录屏 · 小框清晰',
                fontName: 'WenQuanYi Micro Hei',
                fontSize: 34,
                color: '#fff7cc',
                backgroundColor: '#050505',
                backgroundOpacity: 0.64,
                outlineWidth: 0,
                outlineColor: '#000000'
            },
            emphasis: {
                label: '重点提示 · 金色强调',
                fontName: 'Noto Sans CJK SC',
                fontSize: 40,
                color: '#ffe08a',
                backgroundColor: '#111111',
                backgroundOpacity: 0.50,
                outlineWidth: 0.8,
                outlineColor: '#000000'
            },
            minimal: {
                label: '极简轻描边',
                fontName: 'Noto Sans CJK SC',
                fontSize: 36,
                color: '#ffffff',
                backgroundColor: '#000000',
                backgroundOpacity: 0,
                outlineWidth: 1.2,
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
        this.updatePreviewSpeechSummary();
        try {
            localStorage.setItem(
                this.strategyDraftStorageKey,
                JSON.stringify(this.collectCurrentStrategy())
            );
        } catch (error) {
            console.warn('保存当前生成策略失败:', error);
        }
        if (this.elements.coursePreviewModule?.dataset.taskId
            && !this.elements.coursePreviewModule.hidden) {
            this.elements.coursePreviewSaveState.textContent = '生成设置已修改，等待自动保存…';
            this.elements.coursePreviewSaveState.classList.remove('saved');
            clearTimeout(this.previewAutoSaveTimer);
            this.previewAutoSaveTimer = setTimeout(() => this.savePreviewScripts({ automatic: true }), 1200);
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
        const teaching = strategy.teaching_context || {};
        if (this.elements.teachingScenario) this.elements.teachingScenario.value = teaching.scenario ?? 'university';
        if (this.elements.teachingAudience) this.elements.teachingAudience.value = teaching.audience ?? '';
        if (this.elements.teachingPriorKnowledge) this.elements.teachingPriorKnowledge.value = teaching.prior_knowledge ?? 'auto';
        if (this.elements.teachingTeachingGoal) this.elements.teachingTeachingGoal.value = teaching.teaching_goal ?? 'auto';
        if (this.elements.teachingExpressionStyle) this.elements.teachingExpressionStyle.value = teaching.expression_style ?? 'auto';
        if (this.elements.teachingDeliveryMode) this.elements.teachingDeliveryMode.value = teaching.delivery_mode ?? 'recorded';

        if (strategy.tts_engine) this.elements.ttsEngine.value = strategy.tts_engine;

        const values = {
            renderEngine: 'render_engine',
            llmEngine: 'llm_engine',
            llmMode: 'llm_mode',
            refinementLevel: 'refinement_level',
            narrationStyle: 'narration_style',
            targetDurationMinutes: 'target_duration_minutes',
            qualityMode: 'quality_mode',
            visualTheme: 'visual_theme',
            maxIllustrations: 'max_illustrations',
            pptFooterText: 'ppt_footer_text',
            packagingTemplate: 'packaging_template',
            packagingOrganization: 'packaging_organization',
            packagingDepartment: 'packaging_department',
            packagingInstructor: 'packaging_instructor',
            packagingInstructorTitle: 'packaging_instructor_title',
            packagingDuration: 'packaging_duration_seconds',
            packagingTransitionSeconds: 'packaging_transition_seconds',
            packagingOutroText: 'packaging_outro_text',
            packagingIntroLabel: 'packaging_intro_label',
            packagingIntroTitle: 'packaging_intro_title',
            packagingIntroSubtitle: 'packaging_intro_subtitle',
            packagingIntroDuration: 'packaging_intro_duration_seconds',
            packagingOutroTitle: 'packaging_outro_title',
            packagingOutroSubtitle: 'packaging_outro_subtitle',
            packagingOutroDuration: 'packaging_outro_duration_seconds',
            packagingAccentColor: 'packaging_accent_color',
            packagingBackgroundStyle: 'packaging_background_style',
            packagingLogoPosition: 'packaging_logo_position',
            packagingMotionStyle: 'packaging_motion_style',
            packagingMusicStyle: 'packaging_music_style',
            ttsEmotion: 'tts_emotion',
            ttsRate: 'tts_rate',
            ttsEmotionScale: 'tts_emotion_scale',
            ttsSentencePause: 'tts_sentence_pause',
            focusHighlightStyle: 'focus_highlight_style',
            focusHighlightColor: 'focus_highlight_color',
            focusHighlightWidth: 'focus_highlight_width',
            focusSmoothingSeconds: 'focus_smoothing_seconds',
            subtitleX: 'subtitle_x',
            subtitleY: 'subtitle_y',
            subtitleWidth: 'subtitle_width',
            subtitleHeight: 'subtitle_height',
            subtitleFontSize: 'subtitle_font_size',
            subtitleColor: 'subtitle_color',
            subtitleBackgroundColor: 'subtitle_background_color',
            subtitleBackgroundOpacity: 'subtitle_background_opacity',
            subtitleOutlineWidth: 'subtitle_outline_width',
            subtitleOutlineColor: 'subtitle_outline_color',
            videoFps: 'video_fps',
            videoPreset: 'video_preset',
            videoCrf: 'video_crf',
            videoCodec: 'video_codec',
            videoPixelFormat: 'video_pixel_format',
            videoProfile: 'video_profile',
            videoGopSeconds: 'video_gop_seconds',
            audioBitrate: 'audio_bitrate',
            audioSampleRate: 'audio_sample_rate',
            audioChannels: 'audio_channels',
            audioLoudnessLufs: 'audio_loudness_lufs'
        };
        Object.entries(values).forEach(([elementName, key]) => {
            if (strategy[key] !== undefined && this.elements[elementName]) {
                this.elements[elementName].value = strategy[key];
            }
        });
        if (strategy.video_width && strategy.video_height && this.elements.videoResolution) {
            this.elements.videoResolution.value = `${strategy.video_width}x${strategy.video_height}`;
        }
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
        if (strategy.focus_highlight !== undefined && this.elements.focusHighlight) {
            this.elements.focusHighlight.checked = Boolean(strategy.focus_highlight);
        }
        if (strategy.enable_intro !== undefined && this.elements.enableIntro) {
            this.elements.enableIntro.checked = Boolean(strategy.enable_intro);
        }
        if (strategy.enable_outro !== undefined && this.elements.enableOutro) {
            this.elements.enableOutro.checked = Boolean(strategy.enable_outro);
        }
        if (strategy.packaging_apply_to_segments !== undefined && this.elements.packagingApplySegments) {
            this.elements.packagingApplySegments.checked = Boolean(strategy.packaging_apply_to_segments);
        }
        if (strategy.packaging_use_slide_background !== undefined && this.elements.packagingUseSlideBackground) {
            this.elements.packagingUseSlideBackground.checked = Boolean(strategy.packaging_use_slide_background);
        }
        if (strategy.packaging_enable_motion !== undefined && this.elements.packagingEnableMotion) {
            this.elements.packagingEnableMotion.checked = Boolean(strategy.packaging_enable_motion);
        }
        if (strategy.packaging_enable_music !== undefined && this.elements.packagingEnableMusic) {
            this.elements.packagingEnableMusic.checked = Boolean(strategy.packaging_enable_music);
        }
        ['intro', 'outro'].forEach(kind => {
            const x = Number(strategy[`packaging_${kind}_content_x`]);
            const y = Number(strategy[`packaging_${kind}_content_y`]);
            const width = Number(strategy[`packaging_${kind}_content_width`]);
            if (Number.isFinite(x)) this.packagingLayout[kind].x = x;
            if (Number.isFinite(y)) this.packagingLayout[kind].y = y;
            if (Number.isFinite(width)) this.packagingLayout[kind].width = width;
        });

        const customVoice = strategy.custom_voice || '';
        this.elements.customVoice.value = customVoice;
        this.pendingVoiceSelection = strategy.selected_voice || strategy.voice || null;
        this.state.logoPath = strategy.school_logo_path || null;
        this.state.packagingBackgroundPath = strategy.packaging_background_path || null;
        this.state.packagingMusicPath = strategy.packaging_music_path || null;
        this.state.packagingIntroVideoPath = strategy.packaging_intro_video_path || null;
        this.state.packagingOutroVideoPath = strategy.packaging_outro_video_path || null;
        this.syncPackagingAssetState();
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
        this.elements.voiceGenderFilter?.addEventListener('change', () => {
            this.renderVoicePreviewList(this.elements.ttsEngine.value, this.loadedVoices || [], this.elements.voiceSelect.value);
        });
        ttsEngine.addEventListener('change', async () => {
            this.elements.customVoice.value = '';
            this.elements.voiceSelect.value = '';
            this.pendingVoiceSelection = null;
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
        this.elements.previewStopBtn?.addEventListener('click', () => this.stopCoursePreviewPlayback());
        this.elements.previewLocateBtn?.addEventListener('click', () => {
            this.goToPreviewPage(this.coursePreviewActivePage, { focusEditor: false });
            this.openCoursePreviewStage(this.previewCardByPage(this.coursePreviewActivePage));
        });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                if (this.coursePreviewSession || this.coursePreviewPlaying) this.stopCoursePreviewPlayback();
                this.closeCoursePreviewStage();
            }
        });
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
        [this.elements.focusHighlightStyle, this.elements.focusHighlightColor, this.elements.focusHighlightWidth]
            .forEach(control => control?.addEventListener('input', () => {
                this.elements.coursePreviewPages?.querySelectorAll('.course-focus-overlays').forEach(root => {
                    root.dataset.focusStyle = this.elements.focusHighlightStyle?.value || 'underline';
                    root.style.setProperty('--focus-color', this.elements.focusHighlightColor?.value || '#FFAE1F');
                    root.style.setProperty('--focus-line-width', this.elements.focusHighlightWidth?.value || 2);
                });
                this.saveCurrentStrategy();
            }));
        this.elements.aiReviewSampleBtn.addEventListener(
            'click', () => this.runCourseReview('sample')
        );
        this.elements.aiReviewFullBtn.addEventListener(
            'click', () => this.runCourseReview('full')
        );
        this.elements.aiReviewFixAllBtn.addEventListener(
            'click', () => this.applyCourseReviewFixes()
        );
        this.elements.smartCutRecommendBtn.addEventListener(
            'click', () => this.recommendSmartCuts()
        );
        this.elements.smartCutApplyBtn.addEventListener(
            'click', () => this.applySmartCuts()
        );
        this.elements.packagingManageBtn?.addEventListener(
            'click', () => this.openPackagingManager()
        );
        this.elements.packagingManagerClose?.addEventListener(
            'click', () => this.closePackagingManager()
        );
        this.elements.packagingManagerOverlay?.addEventListener('click', event => {
            if (event.target === this.elements.packagingManagerOverlay) {
                this.closePackagingManager();
            }
        });
        this.elements.packagingPreviewRefresh?.addEventListener(
            'click', () => this.refreshPackagingPreview()
        );
        this.elements.packagingLayoutReset?.addEventListener('click', () => {
            this.packagingLayout = this.defaultPackagingLayout();
            this.syncPackagingLayoutBoxes();
            this.refreshPackagingPreview();
            this.saveCurrentStrategy();
        });
        this.bindPackagingLayoutEditor();
        this.bindPackagingAssetUploads();
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
        this.elements.videoDefaultsReset?.addEventListener('click', () => this.resetVideoDefaults());
        this.elements.videoAdvancedToggle?.addEventListener('click', () => {
            const expanded = this.elements.videoAdvancedToggle.getAttribute('aria-expanded') === 'true';
            this.elements.videoAdvancedToggle.setAttribute('aria-expanded', String(!expanded));
            this.elements.videoAdvancedToggle.textContent = expanded ? '展开完整参数' : '收起完整参数';
            if (this.elements.videoAdvancedOptions) {
                this.elements.videoAdvancedOptions.hidden = expanded;
            }
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
        const request = this.voiceListRequest = {};
        const { ttsEngine, voiceSelect, voicePreviewList } = this.elements;
        preferredVoice = preferredVoice || this.pendingVoiceSelection || voiceSelect.value;
        this.pendingVoiceSelection = null;
        this.elements.volcengineExpressionGroup.hidden =
            ttsEngine.value !== 'volcengine';
        this.stopVoicePreview();
        this.loadedVoices = [];
        voiceSelect.disabled = true;
        voiceSelect.innerHTML = '<option value="">正在加载对应厂商音色...</option>';
        voicePreviewList.innerHTML = '<div class="voice-list-message">正在加载音色...</div>';
        try {
            const engine = ttsEngine.value;
            const response = await fetch(`/api/voices?engine=${encodeURIComponent(engine)}`);
            const data = await response.json();
            if (this.voiceListRequest !== request) return;
            if (!response.ok) throw new Error(data.error || '加载音色失败');
            const voiceList = data.voices || [];
            this.loadedVoices = voiceList;
            voiceSelect.innerHTML = '';
            this.groupVoicesByGender(voiceList).forEach(group => {
                const options = document.createElement('optgroup');
                options.label = group.label;
                group.voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.id;
                    option.textContent = `${voice.name} · ${voice.id}`;
                    options.appendChild(option);
                });
                voiceSelect.appendChild(options);
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
            if (this.voiceListRequest !== request) return;
            console.error('加载语音列表失败:', error);
            voiceSelect.innerHTML = '<option value="">加载失败，请输入专属音色 ID</option>';
            voicePreviewList.innerHTML = '<div class="voice-list-message">音色加载失败，请使用专属音色 ID</div>';
        } finally {
            if (this.voiceListRequest === request) {
                voiceSelect.disabled = false;
                this.updatePreviewSpeechSummary();
            }
        }
    }

    voiceGender(voice) {
        const gender = String(voice.gender || '').trim().toLowerCase();
        if (['female', '女', '女声'].includes(gender)) return 'female';
        if (['male', '男', '男声'].includes(gender)) return 'male';
        const id = String(voice.id || '').toLowerCase();
        if (/(^|[_\s(-])(female|woman|women|girl|lady)(?=$|[_\s)-])/.test(id)) return 'female';
        if (/(^|[_\s(-])(male|man|boy|gentleman)(?=$|[_\s)-])/.test(id)) return 'male';
        if (/女声|女性|女童|女孩|少女|御姐|学姐|学妹|闺蜜|姐姐|萌妹/.test(voice.name || '')) return 'female';
        if (/男声|男性|男童|男孩|男友|男主播|男主持|弟弟|学弟|学长|少爷/.test(voice.name || '')) return 'male';
        return 'unknown';
    }

    groupVoicesByGender(voices) {
        return [
            { gender: 'male', label: '男老师 · 男声' },
            { gender: 'female', label: '女老师 · 女声' },
            { gender: 'unknown', label: '性别未标注' }
        ].map(group => ({ ...group, voices: voices.filter(voice => this.voiceGender(voice) === group.gender) }))
            .filter(group => group.voices.length);
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
        const filter = this.elements.voiceGenderFilter?.value || 'all';
        let visibleCount = 0;
        this.groupVoicesByGender(sortedVoices).forEach(group => {
            if (filter !== 'all' && filter !== group.gender) return;
            const section = document.createElement('div');
            section.setAttribute('role', 'group');
            section.setAttribute('aria-label', group.label);
            const heading = document.createElement('div');
            heading.className = 'voice-gender-heading';
            heading.textContent = `${group.label}（${group.voices.length}）`;
            section.appendChild(heading);
            voicePreviewList.appendChild(section);
            group.voices.forEach(voice => {
            visibleCount += 1;
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
            section.appendChild(item);
            });
        });
        if (!visibleCount) {
            voicePreviewList.innerHTML = '<div class="voice-list-message">当前厂商暂无此类音色，可切换分类或厂商</div>';
        }
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
        this.voicePreviewRequest = null;
        if (this.voicePreviewAudio) {
            this.voicePreviewAudio.pause();
            this.voicePreviewAudio.src = '';
            this.voicePreviewAudio = null;
        }
        if (this.voicePreviewAudioUrl) {
            URL.revokeObjectURL(this.voicePreviewAudioUrl);
            this.voicePreviewAudioUrl = null;
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
        const request = this.voicePreviewRequest = {};
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
            const blob = await response.blob();
            if (this.voicePreviewRequest !== request) return;
            const audioUrl = URL.createObjectURL(blob);
            this.voicePreviewAudioUrl = audioUrl;
            const audio = new Audio(audioUrl);
            this.voicePreviewAudio = audio;
            button.disabled = false;
            button.classList.remove('loading');
            button.textContent = '■';
            audio.addEventListener('ended', () => {
                if (this.voicePreviewRequest !== request) return;
                this.stopVoicePreview();
            }, { once: true });
            audio.addEventListener('error', () => {
                if (this.voicePreviewRequest !== request) return;
                this.stopVoicePreview();
                this.showStatus('error', '试听音频播放失败');
            }, { once: true });
            await audio.play();
        } catch (error) {
            if (this.voicePreviewRequest !== request) return;
            this.stopVoicePreview();
            this.showStatus('error', error.message);
        }
    }

    // ── Multi-file upload ──────────────────────────────
    async handleFileSelect(file) {
        const allowedExtensions = ['.docx', '.pdf', '.epub', '.ppt', '.pptx'];
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
            courseName: this.defaultCourseName(file.name),
            sourceType: ['.docx', '.pdf', '.epub'].includes(ext) ? 'lesson-plan' : 'presentation',
            taskId: null,
            status: 'uploading',
            percentage: 0,
            stage: null,
            message: '上传中...',
            videoPath: null,
            courseJsonPath: null,
            presentationPath: null,
            subtitlesPath: null,
            cueTimelinePath: null,
            sourceFileExists: false,
            error: null,
            selected: true,
            strategy: null,
            strategySource: 'batch',
            queuePosition: null
        });

        this.renderFileList();
        await this.uploadFile(file, index);
    }

    async uploadFile(file, index, originalSlides = null) {
        const formData = new FormData();
        formData.append('file', file);
        if (originalSlides) formData.append('original_slides', originalSlides);

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
                originalSlides: Boolean(result.original_slides),
                sourceFileExists: true,
                status: 'pending',
                percentage: 0,
                message: result.original_slides ? '原生页面已校验，待转换' : '待转换'
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
            if (!this.shouldShowInUploadList(item)) return;

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
                <label class="file-course-name">
                    <span>课程名称</span>
                    <input type="text" class="course-name-input"
                           value="${this._escAttr(this.courseDisplayName(item))}"
                           ${item.status === 'pending' ? '' : 'disabled'}
                           maxlength="120">
                </label>
                <span class="file-route-badge ${item.sourceType === 'lesson-plan' ? 'lesson-plan' : 'presentation'}">
                    ${item.sourceType === 'lesson-plan' ? 'AI 设计' : item.originalSlides ? '原生页面' : '兼容渲染'}
                </span>
                ${item.status === 'pending' && item.file && /\.pptx$/i.test(item.fileName) ? `
                    <button type="button" class="original-slides-button btn-secondary"
                            title="在 PowerPoint 中导出所有幻灯片为 PNG，将图片压缩成 ZIP 后上传；按文件名末尾页码匹配，必须包含全部页面">
                        ${item.originalSlides ? '更换原生页面 ZIP' : '上传原生页面 ZIP'}
                    </button>` : ''}
                <span class="file-list-status status-${item.status}">${statusText}</span>
                ${item.status === 'pending' ? `
                    <span class="file-strategy-badge">
                        ${item.strategySource === 'single' ? '单独策略' : '批量策略'}
                    </span>
                    <button type="button" class="file-strategy-button"
                            title="把当前生成策略只应用到此文件">仅配置此项</button>` : ''}
                ${showMiniProgress ? `<div class="mini-progress-bar"><div class="mini-progress-fill" style="width:${this._displayProgressValue(item)}%"></div></div>` : ''}
                <button class="file-list-remove" data-index="${index}"
                        title="${['pending', 'queued', 'processing'].includes(item.status) && item.taskId ? '停止生成并返回编辑' : item.taskId ? '删除课程产物' : '移除'}">&times;</button>
            `;

            row.querySelector('.file-list-remove').addEventListener('click', () => this.removeFile(index));
            row.querySelector('.original-slides-button')?.addEventListener('click', () => {
                const input = document.createElement('input');
                input.type = 'file';
                input.accept = '.zip';
                input.addEventListener('change', async () => {
                    if (!input.files[0]) return;
                    this.updateItem(index, { status: 'uploading', message: '校验原生页面中…' });
                    this.renderFileList();
                    await this.uploadFile(item.file, index, input.files[0]);
                });
                input.click();
            });
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
            const courseNameInput = row.querySelector('.course-name-input');
            if (courseNameInput) {
                courseNameInput.addEventListener('input', (event) => {
                    item.courseName = event.target.value;
                });
                courseNameInput.addEventListener('blur', (event) => {
                    const name = event.target.value.trim() || this.defaultCourseName(item.fileName);
                    item.courseName = name;
                    event.target.value = name;
                    this.renderResultsGrid();
                    this.renderAssetTable();
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
            `字幕：${this.elements.burnSubtitles.checked ? '内嵌到视频' : '仅生成 SRT 文件'}`,
            lessonPlans ? `AI 提炼：${this.elements.refinementLevel.selectedOptions[0]?.textContent}` : '',
            lessonPlans ? `质量模式：${this.elements.qualityMode.selectedOptions[0]?.textContent}` : '',
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
        const videoOptions = this.collectVideoOptions();
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
            focus_highlight: this.elements.focusHighlight?.checked !== false,
            focus_highlight_style: this.elements.focusHighlightStyle?.value || 'underline',
            focus_highlight_color: this.elements.focusHighlightColor?.value || '#FFAE1F',
            focus_highlight_width: Number(this.elements.focusHighlightWidth?.value || 2),
            focus_smoothing_seconds: Number(this.elements.focusSmoothingSeconds?.value || 0),
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
            narration_style: this.elements.narrationStyle.value,
            target_duration_minutes: Number(this.elements.targetDurationMinutes.value),
            teaching_context: {
                scenario: this.elements.teachingScenario.value,
                audience: this.elements.teachingAudience.value,
                prior_knowledge: this.elements.teachingPriorKnowledge.value,
                teaching_goal: this.elements.teachingTeachingGoal.value,
                expression_style: this.elements.teachingExpressionStyle.value,
                delivery_mode: this.elements.teachingDeliveryMode.value,
            },
            quality_mode: this.elements.qualityMode.value,
            visual_theme: this.elements.visualTheme.value,
            illustrations_enabled: this.elements.illustrationsEnabled.checked,
            max_illustrations: Number(this.elements.maxIllustrations.value),
            ppt_footer_text: this.elements.pptFooterText.value.trim(),
            school_logo_path: this.state.logoPath,
            ...this.collectCoursePackagingOptions(),
            ...videoOptions
        };
    }

    collectCoursePackagingOptions() {
        let saved = {};
        try {
            saved = JSON.parse(localStorage.getItem(this.strategyDraftStorageKey) || '{}') || {};
        } catch (error) {
            console.warn('读取课程包装默认配置失败:', error);
        }
        const managedSideOptions = {};
        ['intro', 'mid', 'outro'].forEach(side => {
            [
                'background_path', 'music_path', 'video_path', 'accent_color',
                'background_style', 'logo_position', 'motion_style', 'music_style',
                'use_slide_background', 'enable_motion', 'enable_music',
                'content_x', 'content_y', 'content_width'
            ].forEach(name => {
                const key = `packaging_${side}_${name}`;
                if (saved[key] !== undefined) managedSideOptions[key] = saved[key];
            });
        });
        return {
            ...managedSideOptions,
            enable_intro: this.elements.enableIntro?.checked ?? true,
            enable_mid: saved.enable_mid ?? true,
            enable_outro: this.elements.enableOutro?.checked ?? true,
            packaging_template: this.elements.packagingTemplate?.value || 'academic',
            packaging_organization: this.elements.packagingOrganization?.value.trim() || '',
            packaging_department: this.elements.packagingDepartment?.value.trim() ?? saved.packaging_department ?? '',
            packaging_instructor: this.elements.packagingInstructor?.value.trim() || '',
            packaging_instructor_title: this.elements.packagingInstructorTitle?.value.trim() ?? saved.packaging_instructor_title ?? '',
            packaging_copyright: saved.packaging_copyright || '',
            packaging_duration_seconds: Number(this.elements.packagingDuration?.value) || 4,
            packaging_transition_seconds: Number(this.elements.packagingTransitionSeconds?.value ?? saved.packaging_transition_seconds ?? 0.35),
            packaging_outro_text: this.elements.packagingOutroText?.value.trim() || '感谢观看',
            packaging_apply_to_segments: this.elements.packagingApplySegments?.checked ?? false,
            packaging_use_slide_background: this.elements.packagingUseSlideBackground?.checked ?? true,
            packaging_enable_motion: this.elements.packagingEnableMotion?.checked ?? true,
            packaging_enable_music: this.elements.packagingEnableMusic?.checked ?? true,
            packaging_intro_label: this.elements.packagingIntroLabel?.value.trim() ?? saved.packaging_intro_label ?? '在线开放课程',
            packaging_intro_title: this.elements.packagingIntroTitle?.value.trim() ?? saved.packaging_intro_title ?? '',
            packaging_intro_subtitle: this.elements.packagingIntroSubtitle?.value.trim() ?? saved.packaging_intro_subtitle ?? '',
            packaging_intro_duration_seconds: Number(this.elements.packagingIntroDuration?.value) || Number(saved.packaging_intro_duration_seconds) || Number(this.elements.packagingDuration?.value) || 4,
            packaging_mid_title: saved.packaging_mid_title || '章节过渡',
            packaging_mid_subtitle: saved.packaging_mid_subtitle || '',
            packaging_mid_label: saved.packaging_mid_label || '课程继续',
            packaging_mid_duration_seconds: Number(saved.packaging_mid_duration_seconds) || 2.5,
            packaging_outro_title: this.elements.packagingOutroTitle?.value.trim() ?? saved.packaging_outro_title ?? '',
            packaging_outro_subtitle: this.elements.packagingOutroSubtitle?.value.trim() ?? saved.packaging_outro_subtitle ?? '',
            packaging_outro_duration_seconds: Number(this.elements.packagingOutroDuration?.value) || Number(saved.packaging_outro_duration_seconds) || Number(this.elements.packagingDuration?.value) || 4,
            packaging_accent_color: this.elements.packagingAccentColor?.value || saved.packaging_accent_color || '#D6A239',
            packaging_background_style: this.elements.packagingBackgroundStyle?.value || saved.packaging_background_style || 'ppt',
            packaging_logo_position: this.elements.packagingLogoPosition?.value || saved.packaging_logo_position || 'top-right',
            packaging_motion_style: this.elements.packagingMotionStyle?.value || saved.packaging_motion_style || 'zoom',
            packaging_music_style: this.elements.packagingMusicStyle?.value || saved.packaging_music_style || 'warm',
            packaging_background_path: this.state.packagingBackgroundPath,
            packaging_music_path: this.state.packagingMusicPath,
            packaging_intro_video_path: saved.packaging_intro_video_path || this.state.packagingIntroVideoPath,
            packaging_mid_video_path: saved.packaging_mid_video_path || null,
            packaging_outro_video_path: saved.packaging_outro_video_path || this.state.packagingOutroVideoPath,
            packaging_intro_content_x: this.packagingLayout.intro.x,
            packaging_intro_content_y: this.packagingLayout.intro.y,
            packaging_intro_content_width: this.packagingLayout.intro.width,
            packaging_outro_content_x: this.packagingLayout.outro.x,
            packaging_outro_content_y: this.packagingLayout.outro.y,
            packaging_outro_content_width: this.packagingLayout.outro.width
        };
    }

    async loadPackagingTemplates() {
        const select = this.elements.packagingTemplate;
        if (!select) return;
        try {
            const response = await fetch('/api/course-packaging-templates');
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || '包装模板加载失败');
            const stored = JSON.parse(localStorage.getItem(this.strategyDraftStorageKey) || '{}').packaging_template;
            select.replaceChildren();
            const system = document.createElement('optgroup');
            system.label = '系统模板';
            const custom = document.createElement('optgroup');
            custom.label = '自定义模板';
            result.templates.forEach(template => {
                const option = new Option(`${template.name}${template.is_default ? ' · 默认' : ''}`, template.id);
                option.dataset.config = JSON.stringify(template.config || {});
                (template.builtin ? system : custom).append(option);
            });
            if (system.children.length) select.append(system);
            if (custom.children.length) select.append(custom);
            select.value = result.templates.some(item => item.id === stored) ? stored : result.default_template_id;
            select.addEventListener('change', () => {
                const selectedId = select.value;
                const config = JSON.parse(select.selectedOptions[0]?.dataset.config || '{}');
                if (Object.keys(config).length) this.applyStrategyToControls(config);
                select.value = selectedId;
                this.persistCurrentStrategy();
            });
        } catch (error) {
            console.warn('加载包装模板失败:', error);
        }
    }

    defaultPackagingLayout() {
        return {
            intro: { x: 9.5, y: 30, width: 70 },
            outro: { x: 9.5, y: 34, width: 70 }
        };
    }

    bindPackagingAssetUploads() {
        const bindings = [
            ['background', this.elements.packagingBackgroundButton, this.elements.packagingBackgroundInput],
            ['music', this.elements.packagingMusicButton, this.elements.packagingMusicInput],
            ['intro_video', this.elements.packagingIntroVideoButton, this.elements.packagingIntroVideoInput],
            ['outro_video', this.elements.packagingOutroVideoButton, this.elements.packagingOutroVideoInput]
        ];
        bindings.forEach(([kind, button, input]) => {
            button?.addEventListener('click', () => input.click());
            input?.addEventListener('change', async event => {
                const file = event.target.files[0];
                event.target.value = '';
                if (file) await this.uploadPackagingAsset(kind, file);
            });
        });
        this.elements.packagingBackgroundRemove?.addEventListener('click', () => {
            this.state.packagingBackgroundPath = null;
            this.syncPackagingAssetState();
            this.refreshPackagingPreview();
            this.saveCurrentStrategy();
        });
        this.elements.packagingMusicRemove?.addEventListener('click', () => {
            this.state.packagingMusicPath = null;
            this.syncPackagingAssetState();
            this.saveCurrentStrategy();
        });
        ['intro', 'outro'].forEach(side => {
            const remove = this.elements[`packaging${side[0].toUpperCase()}${side.slice(1)}VideoRemove`];
            remove?.addEventListener('click', () => {
                this.state[`packaging${side[0].toUpperCase()}${side.slice(1)}VideoPath`] = null;
                this.syncPackagingAssetState();
                this.saveCurrentStrategy();
            });
        });
        this.elements.packagingMusicLibrary?.addEventListener('change', event => {
            const selected = event.target.selectedOptions[0];
            this.state.packagingMusicPath = event.target.value || null;
            if (this.elements.packagingMusicPreview) {
                this.elements.packagingMusicPreview.src = selected?.dataset.url || '';
            }
            this.syncPackagingAssetState();
            this.saveCurrentStrategy();
        });
        this.loadPackagingMusicLibrary();
    }

    async uploadPackagingAsset(kind, file) {
        const formData = new FormData();
        formData.append('kind', kind);
        formData.append('asset', file);
        const status = kind === 'background' ? this.elements.packagingBackgroundStatus
            : kind === 'music' ? this.elements.packagingMusicStatus
            : kind === 'intro_video' ? this.elements.packagingIntroVideoStatus
            : this.elements.packagingOutroVideoStatus;
        status.textContent = '上传中...';
        try {
            const response = await fetch('/api/course-packaging-asset-upload', { method: 'POST', body: formData });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || '素材上传失败');
            if (kind === 'background') this.state.packagingBackgroundPath = result.asset_path;
            else if (kind === 'music') this.state.packagingMusicPath = result.asset_path;
            else if (kind === 'intro_video') this.state.packagingIntroVideoPath = result.asset_path;
            else this.state.packagingOutroVideoPath = result.asset_path;
            if (kind === 'background' && this.elements.packagingBackgroundStyle) {
                this.elements.packagingBackgroundStyle.value = 'ppt';
            }
            this.syncPackagingAssetState();
            if (kind === 'music') await this.loadPackagingMusicLibrary();
            if (kind === 'background') this.refreshPackagingPreview();
            this.saveCurrentStrategy();
        } catch (error) {
            status.textContent = error.message;
            await window.VidPPTUI.alert(error.message, { type: 'error' });
        }
    }

    syncPackagingAssetState() {
        const hasBackground = Boolean(this.state.packagingBackgroundPath);
        const hasMusic = Boolean(this.state.packagingMusicPath);
        const hasIntroVideo = Boolean(this.state.packagingIntroVideoPath);
        const hasOutroVideo = Boolean(this.state.packagingOutroVideoPath);
        if (this.elements.packagingBackgroundRemove) this.elements.packagingBackgroundRemove.hidden = !hasBackground;
        if (this.elements.packagingMusicRemove) this.elements.packagingMusicRemove.hidden = !hasMusic;
        if (this.elements.packagingIntroVideoRemove) this.elements.packagingIntroVideoRemove.hidden = !hasIntroVideo;
        if (this.elements.packagingOutroVideoRemove) this.elements.packagingOutroVideoRemove.hidden = !hasOutroVideo;
        if (this.elements.packagingBackgroundStatus) {
            this.elements.packagingBackgroundStatus.textContent = hasBackground ? '已使用自定义背景图' : '片头片尾共用，可恢复为 PPT 背景';
        }
        if (this.elements.packagingMusicStatus) {
            this.elements.packagingMusicStatus.textContent = hasMusic ? '已使用自定义背景音乐' : '自动裁剪到片头片尾时长';
        }
        if (this.elements.packagingIntroVideoStatus) this.elements.packagingIntroVideoStatus.textContent = hasIntroVideo ? '已使用本地片头视频' : '支持 MP4/MOV，自动循环并裁剪';
        if (this.elements.packagingOutroVideoStatus) this.elements.packagingOutroVideoStatus.textContent = hasOutroVideo ? '已使用本地片尾视频' : '可与片头使用不同素材';
        if (this.elements.packagingMusicLibrary) this.elements.packagingMusicLibrary.value = this.state.packagingMusicPath || '';
    }

    async loadPackagingMusicLibrary() {
        const select = this.elements.packagingMusicLibrary;
        if (!select) return;
        try {
            const response = await fetch('/api/course-packaging-assets?kind=music');
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || '音乐素材库加载失败');
            select.replaceChildren(new Option('使用内置风格音乐', ''));
            result.assets.forEach(asset => {
                const option = new Option(asset.name, asset.path);
                option.dataset.url = asset.url;
                select.add(option);
            });
            select.value = this.state.packagingMusicPath || '';
            const selected = select.selectedOptions[0];
            if (this.elements.packagingMusicPreview) this.elements.packagingMusicPreview.src = selected?.dataset.url || '';
        } catch (error) {
            console.warn('加载音乐素材库失败:', error);
        }
    }

    bindPackagingLayoutEditor() {
        document.querySelectorAll('[data-packaging-layout]').forEach(box => {
            box.addEventListener('pointerdown', event => {
                const kind = box.dataset.packagingLayout;
                const canvas = box.parentElement;
                const resizing = event.target.tagName === 'I';
                const start = { x: event.clientX, y: event.clientY };
                const original = { ...this.packagingLayout[kind] };
                const rect = canvas.getBoundingClientRect();
                box.setPointerCapture(event.pointerId);
                const move = moveEvent => {
                    const dx = (moveEvent.clientX - start.x) / rect.width * 100;
                    const dy = (moveEvent.clientY - start.y) / rect.height * 100;
                    if (resizing) {
                        this.packagingLayout[kind].width = Math.max(
                            18, Math.min(95 - original.x, original.width + dx)
                        );
                    } else {
                        this.packagingLayout[kind].x = Math.max(
                            0, Math.min(100 - original.width, original.x + dx)
                        );
                        this.packagingLayout[kind].y = Math.max(
                            0, Math.min(78, original.y + dy)
                        );
                    }
                    this.syncPackagingLayoutBoxes();
                };
                const up = () => {
                    box.removeEventListener('pointermove', move);
                    box.removeEventListener('pointerup', up);
                    box.removeEventListener('pointercancel', up);
                    this.refreshPackagingPreview();
                    this.saveCurrentStrategy();
                };
                box.addEventListener('pointermove', move);
                box.addEventListener('pointerup', up);
                box.addEventListener('pointercancel', up);
                event.preventDefault();
            });
        });
    }

    syncPackagingLayoutBoxes() {
        document.querySelectorAll('[data-packaging-layout]').forEach(box => {
            const layout = this.packagingLayout[box.dataset.packagingLayout];
            if (!layout) return;
            box.style.left = `${layout.x}%`;
            box.style.top = `${layout.y}%`;
            box.style.width = `${layout.width}%`;
            box.style.height = '34%';
        });
    }

    openPackagingManager() {
        const overlay = this.elements.packagingManagerOverlay;
        if (!overlay) return;
        overlay.hidden = false;
        requestAnimationFrame(() => overlay.classList.add('visible'));
        this.syncPackagingLayoutBoxes();
        this.refreshPackagingPreview();
    }

    closePackagingManager() {
        const overlay = this.elements.packagingManagerOverlay;
        if (!overlay) return;
        overlay.classList.remove('visible');
        window.setTimeout(() => {
            if (!overlay.classList.contains('visible')) overlay.hidden = true;
        }, 180);
    }

    refreshPackagingPreview() {
        const intro = this.elements.packagingIntroPreview;
        const outro = this.elements.packagingOutroPreview;
        if (!intro || !outro) return;
        if (this.elements.packagingPreviewStatus) {
            this.elements.packagingPreviewStatus.textContent = '正在生成预览...';
        }
        intro.src = this.packagingPreviewUrl('intro');
        outro.src = this.packagingPreviewUrl('outro');
        let loaded = 0;
        const done = () => {
            loaded += 1;
            if (loaded >= 2 && this.elements.packagingPreviewStatus) {
                this.elements.packagingPreviewStatus.textContent = '预览已更新';
            }
        };
        const failed = () => {
            if (this.elements.packagingPreviewStatus) {
                this.elements.packagingPreviewStatus.textContent = '预览生成失败';
            }
        };
        intro.onload = done;
        outro.onload = done;
        intro.onerror = failed;
        outro.onerror = failed;
    }

    packagingPreviewUrl(kind) {
        const params = new URLSearchParams({
            kind,
            packaging_template: this.elements.packagingTemplate?.value || 'academic',
            packaging_organization: this.elements.packagingOrganization?.value.trim() || '',
            packaging_department: this.elements.packagingDepartment?.value.trim() || '',
            packaging_instructor: this.elements.packagingInstructor?.value.trim() || '',
            packaging_instructor_title: this.elements.packagingInstructorTitle?.value.trim() || '',
            packaging_outro_text: this.elements.packagingOutroText?.value.trim() || '感谢观看',
            packaging_intro_label: this.elements.packagingIntroLabel?.value.trim() || '在线开放课程',
            packaging_intro_title: this.elements.packagingIntroTitle?.value.trim() || '',
            packaging_intro_subtitle: this.elements.packagingIntroSubtitle?.value.trim() || '',
            packaging_outro_title: this.elements.packagingOutroTitle?.value.trim() || '',
            packaging_outro_subtitle: this.elements.packagingOutroSubtitle?.value.trim() || '',
            packaging_accent_color: this.elements.packagingAccentColor?.value || '#D6A239',
            packaging_background_style: this.elements.packagingBackgroundStyle?.value || 'solid',
            packaging_logo_position: this.elements.packagingLogoPosition?.value || 'top-right',
            packaging_background_path: this.state.packagingBackgroundPath || '',
            packaging_intro_content_x: String(this.packagingLayout.intro.x),
            packaging_intro_content_y: String(this.packagingLayout.intro.y),
            packaging_intro_content_width: String(this.packagingLayout.intro.width),
            packaging_outro_content_x: String(this.packagingLayout.outro.x),
            packaging_outro_content_y: String(this.packagingLayout.outro.y),
            packaging_outro_content_width: String(this.packagingLayout.outro.width),
            course_title: '人工智能课程示例',
            segment_title: kind === 'intro' ? '第一讲 课程导入' : '',
            t: String(Date.now())
        });
        return `/api/course-packaging-preview-image?${params.toString()}`;
    }

    collectVideoOptions() {
        const [width, height] = String(this.elements.videoResolution?.value || '1920x1080')
            .split('x')
            .map(value => Number(value));
        return {
            video_width: width || 1920,
            video_height: height || 1080,
            video_fps: Number(this.elements.videoFps?.value) || 24,
            video_codec: this.elements.videoCodec?.value || 'libx264',
            video_preset: this.elements.videoPreset?.value || 'veryfast',
            video_crf: Number(this.elements.videoCrf?.value) || 21,
            video_pixel_format: this.elements.videoPixelFormat?.value || 'yuv420p',
            video_gop_seconds: Number(this.elements.videoGopSeconds?.value) || 2,
            video_profile: this.elements.videoProfile?.value || 'high',
            audio_bitrate: this.elements.audioBitrate?.value || '128k',
            audio_sample_rate: Number(this.elements.audioSampleRate?.value) || 48000,
            audio_channels: Number(this.elements.audioChannels?.value) || 1,
            audio_loudness_lufs: Number(this.elements.audioLoudnessLufs?.value) || -16
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
                narration_style: 'lecture',
                target_duration_minutes: 0,
                quality_mode: 'balanced',
                illustrations_enabled: true,
                max_illustrations: 3
            },
            '企业制度宣讲': {
                tts_engine: 'volcengine',
                llm_enabled: true,
                llm_engine: 'qwen',
                llm_mode: 'per-page',
                refinement_level: 'light',
                narration_style: 'faithful',
                target_duration_minutes: 0,
                quality_mode: 'economy',
                illustrations_enabled: false,
                max_illustrations: 1
            },
            '高度提炼微课': {
                tts_engine: 'edge-tts',
                llm_enabled: true,
                llm_engine: 'qwen',
                llm_mode: 'per-page',
                refinement_level: 'strong',
                narration_style: 'micro',
                target_duration_minutes: 10,
                quality_mode: 'premium',
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
            if (item.taskId && item.sourceFileExists) {
                actions.push(`
                    <span class="table-action-group" aria-label="上传文件操作">
                        <span class="table-action-label">源文件</span>
                        <button type="button" class="table-action" data-action="source-preview" data-task-id="${this._escAttr(item.taskId)}" title="预览上传文件">预览</button>
                        <button type="button" class="table-action" data-action="source-download" data-task-id="${this._escAttr(item.taskId)}" title="下载上传文件">下载</button>
                    </span>
                `);
            }
            if (item.status === 'completed' && item.videoPath) {
                actions.push(`
                    <span class="table-action-group" aria-label="生成视频操作">
                        <span class="table-action-label">视频</span>
                        <button type="button" class="table-action" data-action="video-preview" data-task-id="${this._escAttr(item.taskId)}" title="预览生成视频">预览</button>
                        <button type="button" class="table-action" data-action="video-download" data-task-id="${this._escAttr(item.taskId)}" title="下载生成视频">下载</button>
                    </span>
                `);
            } else {
                actions.push(`
                    <span class="table-action-group table-action-group-disabled" aria-label="生成视频操作">
                        <span class="table-action-label">视频</span>
                        <button type="button" class="table-action" disabled title="视频生成完成后可预览">预览</button>
                        <button type="button" class="table-action" disabled title="视频生成完成后可下载">下载</button>
                    </span>
                `);
            }
            if (['completed', 'error', 'interrupted', 'awaiting_confirmation'].includes(item.status)) {
                actions.push(`<button type="button" class="table-action danger" data-action="delete" data-task-id="${this._escAttr(item.taskId)}">删除</button>`);
            }
            return `
                <tr>
                    <td><strong>${this._esc(this.courseDisplayName(item) || '未知课程')}</strong><small>${this._esc(item.fileName || item.taskId || '')}</small></td>
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
                if (action === 'source-preview') this.previewSourceFile(taskId);
                if (action === 'source-download') this.downloadSourceFile(taskId);
                if (action === 'video-preview') this.previewVideoByTaskId(taskId);
                if (action === 'video-download') this.handleDownloadByTaskId(taskId);
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
                return `${stageName} ${Math.round(this._displayProgressValue(item))}%`;
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
        if (item?.taskId && ['pending', 'queued', 'processing'].includes(item.status)) {
            await this.stopTask(item.taskId);
            return;
        }
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
                        course_name: this.courseDisplayName(item),
                        batch_id: batchId,
                        strategy_source: item.strategySource || 'batch',
                        ...strategy,
                        render_engine: item.originalSlides ? 'original' : strategy.render_engine
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

        const renderEngine = item.originalSlides ? 'original' : this.elements.renderEngine.value;

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
                                stageCurrent: data.current ?? null,
                                stageTotal: data.total ?? null,
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
                            stageCurrent: data.current ?? item.stageCurrent ?? null,
                            stageTotal: data.total ?? item.stageTotal ?? null,
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
                            cueTimelinePath: data.cue_timeline_path || null,
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
                        this.updateItem(found.index, {
                            stage: d.stage || found.item.stage,
                            percentage: d.percentage ?? found.item.percentage,
                            stagePercentage: d.stage_percentage ?? found.item.stagePercentage,
                            stageCurrent: d.stage_current ?? found.item.stageCurrent ?? null,
                            stageTotal: d.stage_total ?? found.item.stageTotal ?? null,
                            message: d.message || found.item.message,
                            stageStartedAt: d.stage_started_at || found.item.stageStartedAt,
                            updatedAt: d.updated_at || found.item.updatedAt
                        });
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
        const displayedPercentage = this._displayProgressValue(item);
        const message = item.message
            || (item.status === 'queued' ? '排队中...' : `${this.stageNames[item.stage] || '准备'}中...`);
        const now = Date.now() / 1000;
        const elapsed = item.startedAt ? Math.max(0, now - item.startedAt) : null;
        const stageElapsed = item.stageStartedAt
            ? Math.max(0, now - item.stageStartedAt)
            : null;
        const remaining = this._estimateRemainingSeconds(item, {
            percentage,
            stagePercentage,
            elapsed,
            stageElapsed
        });
        const timingRemaining = remaining === null
            ? null
            : Number.isFinite(remaining)
                ? `预计剩余 ${this.formatDuration(remaining)}`
                : '预计剩余 估算中';
        const timing = [
            elapsed !== null ? `已耗时 ${this.formatDuration(elapsed)}` : null,
            timingRemaining,
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

    _displayProgressValue(item) {
        const percentage = Math.max(0, Math.min(100, Number(item?.percentage) || 0));
        const stagePercentage = Math.max(
            0, Math.min(100, Number(item?.stagePercentage) || 0)
        );
        return item?.stage === 'video' ? stagePercentage : percentage;
    }

    _estimateRemainingSeconds(item, { percentage, stagePercentage, elapsed, stageElapsed }) {
        if (!['processing', 'queued'].includes(item?.status)) return null;
        if (item.status === 'queued') return null;

        if (item.stage === 'video') {
            if (!stageElapsed || stagePercentage < 3) return Number.POSITIVE_INFINITY;
            return Math.max(0, stageElapsed * (100 - stagePercentage) / stagePercentage);
        }

        if (item.stage === 'render') {
            const stageCurrent = Number(item.stageCurrent);
            const stageTotal = Number(item.stageTotal);
            const hasMeasuredStageProgress = (
                Number.isFinite(stageCurrent)
                && Number.isFinite(stageTotal)
                && stageTotal > 0
                && stageCurrent > 0
                && stageCurrent < stageTotal
            );
            if (!hasMeasuredStageProgress) return Number.POSITIVE_INFINITY;
            if (!stageElapsed) return Number.POSITIVE_INFINITY;
            return Math.max(0, stageElapsed * (stageTotal - stageCurrent) / stageCurrent);
        }

        if (!elapsed || percentage < 3) return Number.POSITIVE_INFINITY;
        return Math.max(0, elapsed * (100 - percentage) / percentage);
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
                        <span class="result-card-name" title="${this._esc(item.fileName)}">${this._esc(this.courseDisplayName(item))}</span>
                    </div>
                    <button class="result-card-download preview-open-btn" data-index="${index}">编辑讲稿</button>
                    ${item.videoPath ? `<small>上一版产物（新版生成成功前保留）</small>${this._artifactLinks(item)}` : ''}
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
                            <span class="result-card-name" title="${this._esc(item.fileName)}">${this._esc(this.courseDisplayName(item))}</span>
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
                        <span class="result-card-name" title="${this._esc(item.fileName)}">${this._esc(this.courseDisplayName(item))}</span>
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
                        <span class="result-card-name" title="${this._esc(item.fileName)}">${this._esc(this.courseDisplayName(item))}</span>
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
            item.courseName,
            item.courseJsonPath,
            item.presentationPath,
            item.subtitlesPath,
            item.cueTimelinePath,
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
                <button type="button" class="result-stage-retry" data-stage="edit">编辑并生成新版</button>
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
                    course_name: this.courseDisplayName(item),
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
        if (stage === 'edit') return this.reopenCourse(taskId);
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
            a.download = `${this.courseDisplayName(item)}.mp4`;
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

    sourceFileUrl(taskId, mode = 'download') {
        return `/api/tasks/${encodeURIComponent(taskId)}/source-file?mode=${encodeURIComponent(mode)}`;
    }

    downloadSourceFile(taskId) {
        const found = this.getItemByTaskId(taskId);
        const item = found?.item;
        if (!item?.taskId || !item.sourceFileExists) {
            window.VidPPTUI.alert('上传文件不存在', { type: 'warning' });
            return;
        }
        const a = document.createElement('a');
        a.href = this.sourceFileUrl(item.taskId, 'download');
        a.download = item.fileName || '';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    previewSourceFile(taskId) {
        const found = this.getItemByTaskId(taskId);
        const item = found?.item;
        if (!item?.taskId || !item.sourceFileExists) {
            window.VidPPTUI.alert('上传文件不存在', { type: 'warning' });
            return;
        }
        if (/\.pdf$/i.test(item.fileName || '')) {
            window.open(this.sourceFileUrl(item.taskId, 'preview'), '_blank', 'noopener');
            return;
        }
        if (item.previewPath) {
            this.loadCoursePreview(item.taskId);
            return;
        }
        window.VidPPTUI.alert('该格式暂不支持在线预览，请下载源文件查看', { type: 'warning' });
    }

    previewVideoByTaskId(taskId) {
        const found = this.getItemByTaskId(taskId);
        const item = found?.item;
        if (!item?.taskId || !item.videoPath) {
            window.VidPPTUI.alert('没有可预览的视频', { type: 'warning' });
            return;
        }
        const url = '/api/video?path=' + encodeURIComponent(item.videoPath);
        window.open(url, '_blank', 'noopener');
    }

    _artifactLinks(item) {
        const artifacts = [
            ['课程 JSON', item.courseJsonPath],
            ['可编辑 PPT', item.presentationPath],
            ['字幕 SRT', item.subtitlesPath],
            ['音画时间轴 JSON', item.cueTimelinePath],
            ['课程视频', item.videoPath]
        ].filter(([, path]) => path);
        const segmentLinks = (item.videoSegments || []).flatMap(segment => {
            const range = `${segment.start_page}-${segment.end_page}`;
            return [
                segment.video_path
                    ? [`第 ${segment.id} 段`, segment.video_path, range]
                    : null,
                segment.cue_timeline_path
                    ? [`第 ${segment.id} 段时间轴`, segment.cue_timeline_path, range]
                    : null
            ].filter(Boolean);
        });
        if (!artifacts.length && !segmentLinks.length) return '';
        const link = (label, path) => `<a class="artifact-link" href="/api/download?task_id=${encodeURIComponent(item.taskId)}&path=${encodeURIComponent(path)}">${this._esc(label)}</a>`;
        const main = artifacts.filter(([label]) => !label.includes('JSON')).map(([label, path]) => link(label, path)).join('');
        const advanced = artifacts.filter(([label]) => label.includes('JSON')).map(([label, path]) => link(label, path)).join('')
            + segmentLinks.filter(([label]) => label.includes('时间轴')).map(([label, path, range]) => link(`${label} · ${range} 页`, path)).join('');
        const segments = segmentLinks.filter(([label]) => !label.includes('时间轴')).map(([label, path, range]) => link(`${label} · ${range} 页`, path)).join('');
        return `<div class="artifact-links">${main}</div>${segments ? `<details class="artifact-group"><summary>分段视频目录</summary><div class="artifact-links">${segments}</div></details>` : ''}${advanced ? `<details class="artifact-group"><summary>高级产物</summary><div class="artifact-links">${advanced}</div></details>` : ''}`;

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
                    originalSlides: t.media_options?.render_engine === 'original',
                    fileName: t.original_name || '未知文件',
                    sourceFileExists: Boolean(t.source_file_exists),
                    courseName: t.course_name || this.defaultCourseName(t.original_name || ''),
                    sourceType: /\.(docx|pdf|epub)$/i.test(t.original_name || '') ? 'lesson-plan' : 'presentation',
                    taskId: t.task_id,
                    status: this._taskStatus(t.status),
                    percentage: t.percentage || 0,
                    stagePercentage: t.stage_percentage || 0,
                    stageCurrent: t.stage_current ?? null,
                    stageTotal: t.stage_total ?? null,
                    stage: t.stage,
                    message: t.message || '',
                    videoPath: t.video_path || null,
                    courseJsonPath: t.course_json_path || null,
                    presentationPath: t.presentation_path || null,
                    subtitlesPath: t.subtitles_path || null,
                    cueTimelinePath: t.cue_timeline_path || null,
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
                    stageCurrent: task.stage_current ?? found.item.stageCurrent ?? null,
                    stageTotal: task.stage_total ?? found.item.stageTotal ?? null,
                    message: task.message || '',
                    videoPath: task.video_path || null,
                    courseName: task.course_name || found.item.courseName,
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
        if (this.previewLoading) return;
        this.previewLoading = true;
        try {
            const request = this.previewLoadRequest = {};
            const currentTask = this.elements.coursePreviewModule.dataset.taskId;
            if (currentTask && currentTask !== taskId && !this.elements.coursePreviewModule.hidden) {
                clearTimeout(this.previewAutoSaveTimer);
                if (!await this.savePreviewScripts({ automatic: true })) return;
            }
            if (this.previewLoadRequest !== request) return;
            this.stopCoursePreviewPlayback();
            const response = await fetch(`/api/course-preview/${taskId}`);
            const data = await response.json();
            if (this.previewLoadRequest !== request) return;
            if (!response.ok) throw new Error(data.error || '加载预览失败');
            if (data.speech_settings && this.elements.coursePreviewModule.dataset.taskId !== taskId) {
                if (data.strategy) {
                    localStorage.setItem(this.strategyDraftStorageKey, JSON.stringify(data.strategy));
                    this.applyStrategyToControls(data.strategy);
                }
                const speech = data.speech_settings;
                this.elements.ttsEngine.value = speech.tts_engine;
                this.elements.customVoice.value = '';
                ['ttsRate', 'ttsEmotion', 'ttsEmotionScale', 'ttsSentencePause'].forEach((key, index) => {
                    const field = ['tts_rate', 'tts_emotion', 'tts_emotion_scale', 'tts_sentence_pause'][index];
                    if (this.elements[key]) this.elements[key].value = speech[field];
                });
                await this.loadVoices({ preferredVoice: speech.voice });
            }
            if (this.previewLoadRequest !== request) return;
            try {
                const draft = JSON.parse(localStorage.getItem(this.previewDraftKey(taskId)) || 'null');
                if (draft?.pages && await window.VidPPTUI.confirm('发现上次未同步的本地讲稿，是否恢复？', { title: '恢复本地草稿', confirmText: '恢复' })) {
                    if (draft.strategy) {
                        this.applyStrategyToControls(draft.strategy);
                        await this.loadVoices({ preferredVoice: draft.strategy.voice });
                    }
                    const local = new Map(draft.pages.map(page => [page.page_number, page]));
                    data.pages = data.pages.map(page => local.has(page.page_number) ? { ...page, ...local.get(page.page_number) } : page);
                    this.previewDirty = true;
                }
            } catch (error) { console.warn('读取本地草稿失败', error); }
            this.smartCutRecommendationOptions = data.segmentation_settings || null;
            this.renderCoursePreview(
                taskId,
                data.pages || [],
                data.lesson_segments || [],
                data.duration_estimate || null,
                data.ai_review || null,
                data.quality_mode || 'balanced'
            );
        } catch (error) {
            this.showStatus('error', error.message);
        } finally {
            this.previewLoading = false;
        }
    }

    renderCoursePreview(
        taskId,
        pages,
        lessonSegments = [],
        durationEstimate = null,
        aiReview = null,
        qualityMode = 'balanced'
    ) {
        const { coursePreviewModule, coursePreviewPages, coursePreviewSaveState } = this.elements;
        clearTimeout(this.previewAutoSaveTimer);
        this.closeCoursePreviewStage();
        this.stopCoursePreviewPlayback(
            '从当前页开始，按页图、讲稿、字幕和配音预览课程效果'
        );
        this.smartCutSegments = lessonSegments;
        this.smartCutApplied = this.smartCutSegments.length > 0;
        this.elements.continueCourseBtn.disabled = false;
        coursePreviewModule.dataset.taskId = taskId;
        coursePreviewModule.dataset.qualityMode = qualityMode || 'balanced';
        this.updatePreviewSpeechSummary();
        this.elements.downloadEditablePptBtn.href = `/api/course-presentation/${taskId}`;
        this.renderCourseReview(aiReview, qualityMode);
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
                <div class="course-preview-stage">
                <div class="course-preview-stage-heading">
                    <span>第 ${page.page_number} 页 · 画面与配音预览</span>
                    <button type="button" class="btn-preview course-preview-expand" aria-expanded="false">放大预览</button>
                </div>
                <div class="course-preview-slide-canvas">
                    <img class="course-preview-image" src="${page.image_url}" alt="第 ${page.page_number} 页">
                    <div class="course-focus-overlays" aria-label="讲解焦点预览"></div>
                    <div class="subtitle-safe-area" aria-hidden="true"></div>
                    <div class="course-preview-subtitle-overlay">
                        <img class="course-preview-subtitle-sample" alt="字幕预览">
                    </div>
                </div>
                <div class="course-preview-page-player">
                    <button type="button" class="btn-preview course-preview-page-play">播放本页预览</button>
                    <button type="button" class="btn-secondary course-preview-page-stop" disabled>停止</button>
                    <span class="course-preview-page-player-status">使用本页讲稿预览 PPT、字幕和配音</span>
                    <span class="course-focus-now" aria-live="polite">当前讲解位置将在播放时显示</span>
                </div>
                </div>
                <div class="course-preview-editor">
                    <div class="course-preview-page-title">第 ${page.page_number} 页 · ${this._esc(page.title || '')}${segmentLabel}</div>
                    <textarea class="course-preview-script" aria-label="第 ${page.page_number} 页讲稿">${this._esc(page.script || '')}</textarea>
                    <details class="page-revision-panel">
                        <summary>AI 修改本页</summary>
                        <p class="course-preview-hint">指出理解有误的地方或提出改进要求，AI 将结合本页原文和前后页重新生成讲稿。</p>
                        <label for="page-feedback-${page.page_number}">本页改进意见</label>
                        <textarea id="page-feedback-${page.page_number}" class="page-revision-feedback" maxlength="2000" rows="3" placeholder="例如：这里的 PLC 指可编程逻辑控制器，请纠正概念，并用初学者能理解的例子解释。"></textarea>
                        <button type="button" class="btn-secondary page-revision-generate">根据意见重新生成讲稿</button>
                        <p class="page-revision-status" role="status" aria-live="polite"></p>
                        <div class="page-revision-result" hidden>
                            <label for="page-replacement-${page.page_number}">新讲稿预览</label>
                            <textarea id="page-replacement-${page.page_number}" class="page-revision-candidate" rows="6" readonly></textarea>
                            <button type="button" class="btn-primary page-revision-apply">应用并保存本页讲稿</button>
                        </div>
                    </details>
                    <div class="course-focus-editor"></div>
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
            card._focusMode = page.focus_mode || 'auto';
            card._focusEventsManualClear = Boolean(page.focus_events_manual_clear);
            card._focusTargets = Array.isArray(page.focus_targets) ? page.focus_targets : [];
            card._focusCues = Array.isArray(page.focus_cues) ? page.focus_cues : [];
            card._focusEvents = Array.isArray(page.focus_events) ? page.focus_events : null;
            this.renderCourseFocusEditor(card);
            const textarea = card.querySelector('textarea');
            card.querySelector('.page-revision-generate').addEventListener(
                'click', () => this.generatePageRevision(card)
            );
            card.querySelector('.page-revision-apply').addEventListener(
                'click', () => this.applyPageRevision(card)
            );
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
            textarea.addEventListener('input', () => {
                this.stopCoursePreviewPlayback();
                const manualEvents = (card._focusEvents || [])
                    .filter(event => event.manual || event.reviewed)
                    .map(event => ({ ...event, needs_review: true }));
                card._focusEvents = manualEvents.length ? manualEvents : null;
                this.renderCourseFocusEditor(card);
                this.markCourseReviewStale(page.page_number);
                this.storePreviewDraft();
                updateLength();
                coursePreviewSaveState.textContent = '等待自动保存…';
                coursePreviewSaveState.classList.remove('saved');
                clearTimeout(this.previewAutoSaveTimer);
                this.previewAutoSaveTimer = setTimeout(
                    () => this.savePreviewScripts({ automatic: true }),
                    1200
                );
            });
            card.querySelector('.course-preview-expand').addEventListener('click', () => {
                if (this.expandedPreviewStage === card.querySelector('.course-preview-stage')) {
                    this.closeCoursePreviewStage();
                } else {
                    this.openCoursePreviewStage(card);
                }
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
                async event => {
                    const button = event.currentTarget;
                    if (await this.savePreviewScripts({ automatic: true })) {
                        this.retryTaskStage(taskId, 'page_tts', page.page_number, button);
                    }
                }
            );
            this.bindCourseSubtitleOverlayDrag(card.querySelector('.course-preview-subtitle-overlay'));
            coursePreviewPages.appendChild(card);

            const option = document.createElement('option');
            option.value = page.page_number;
            option.textContent = `第 ${page.page_number} 页 · ${(page.title || '未命名').slice(0, 28)}`;
            this.elements.previewPageSelect.appendChild(option);
        });
        this.renderSmartCutSegments();
        this.updateCourseDurationEstimate(durationEstimate);
        this.currentPreviewPage = Number(pages[0]?.page_number || 1);
        this.updatePreviewNavigation();
        coursePreviewSaveState.textContent = '修改将自动保存';
        coursePreviewModule.hidden = false;
        this.syncSubtitlePreviewFromInputs();
        coursePreviewModule.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    async generatePageRevision(card) {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        const feedback = card.querySelector('.page-revision-feedback').value.trim();
        const status = card.querySelector('.page-revision-status');
        if (!feedback) {
            status.textContent = '请先输入本页的改进意见。';
            card.querySelector('.page-revision-feedback').focus();
            return;
        }
        if (!taskId || card._revisionBusy) return;
        card._revisionBusy = true;
        const button = card.querySelector('.page-revision-generate');
        button.disabled = true;
        card.querySelector('.page-revision-result').hidden = true;
        card._revision = null;
        status.textContent = '正在保存当前讲稿…';
        const isCurrent = () => taskId === this.elements.coursePreviewModule.dataset.taskId
            && this.previewCardByPage(card.dataset.pageNumber) === card;
        try {
            clearTimeout(this.previewAutoSaveTimer);
            if (!await this.savePreviewScripts({ automatic: true })) {
                throw new Error('当前讲稿保存失败，请保存成功后再重新生成。');
            }
            if (!isCurrent()) return;
            const script = card.querySelector('.course-preview-script').value;
            status.textContent = 'AI 正在根据意见重新理解本页并生成讲稿…';
            const response = await fetch(`/api/course-preview/${taskId}/revise-page`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ page_number: Number(card.dataset.pageNumber), feedback, script })
            });
            const data = await response.json();
            if (!isCurrent()) return;
            if (!response.ok) throw new Error(data.error || '重新生成失败，请重试。');
            if (card.querySelector('.course-preview-script').value !== script) {
                throw new Error('生成期间你修改了本页讲稿，请根据最新讲稿重新生成。');
            }
            card._revision = { script: data.script, baseScript: script };
            card.querySelector('.page-revision-candidate').value = data.script;
            card.querySelector('.page-revision-result').hidden = false;
            status.textContent = '新讲稿已生成，确认后点击“应用并保存本页讲稿”。';
        } catch (error) {
            if (isCurrent()) status.textContent = error.message;
        } finally {
            card._revisionBusy = false;
            button.disabled = false;
        }
    }

    async applyPageRevision(card) {
        const revision = card._revision;
        const textarea = card.querySelector('.course-preview-script');
        const status = card.querySelector('.page-revision-status');
        if (!revision || card._revisionBusy) return;
        if (textarea.value !== revision.baseScript) {
            status.textContent = '本页讲稿已修改，请根据最新讲稿重新生成。';
            return;
        }
        card._revisionBusy = true;
        const button = card.querySelector('.page-revision-apply');
        const generate = card.querySelector('.page-revision-generate');
        button.disabled = generate.disabled = true;
        try {
            this.stopCoursePreviewPlayback();
            card.querySelector('.page-reviewed').checked = false;
            textarea.value = revision.script;
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            clearTimeout(this.previewAutoSaveTimer);
            card.querySelector('.page-revision-result').hidden = true;
            card._revision = null;
            status.textContent = '正在保存新讲稿…';
            const saved = await this.savePreviewScripts({ automatic: true });
            status.textContent = saved
                ? '新讲稿已保存，请播放本页预览，确认配音与字幕后重新审核。'
                : '新讲稿已填入编辑框，保存失败；请点击“保存草稿与生成设置”重试。';
        } finally {
            card._revisionBusy = false;
            button.disabled = generate.disabled = false;
        }
    }

    async pollBackgroundReview(taskId, token) {
        const current = () => this.reviewPollToken === token
            && this.elements.coursePreviewModule.dataset.taskId === taskId
            && !this.elements.coursePreviewModule.hidden;
        if (!current()) return;
        try {
            const response = await fetch(`/api/course-review/${taskId}`);
            if (!current() || !response.ok) return;
            const data = await response.json();
            if (!current()) return;
            this.renderCourseReview(data.ai_review, data.quality_mode || 'balanced');
        } catch (_) {
            if (current()) this.reviewPollTimer = setTimeout(() => this.pollBackgroundReview(taskId, token), 5000);
        }
    }

    renderCourseReview(review, qualityMode = 'balanced') {
        clearTimeout(this.reviewPollTimer);
        const token = this.reviewPollToken = {};
        if (review?.running) {
            const taskId = this.elements.coursePreviewModule.dataset.taskId;
            this.reviewPollTimer = setTimeout(() => this.pollBackgroundReview(taskId, token), 2500);
        }
        this.currentAIReview = review || null;
        const modeLabels = {
            economy: '经济模式',
            balanced: '均衡模式',
            premium: '精品模式',
            sample: '抽检',
            full: '全课二审'
        };
        const statusLabels = {
            passed: '通过',
            warning: '需关注',
            failed: '未通过',
            pending: '待审查'
        };
        const completed = review?.review_completed === true && review?.status !== 'pending';
        const status = review && !completed && review.status !== 'pending'
            ? 'failed'
            : (review?.status || (qualityMode === 'economy' ? 'passed' : 'pending'));
        this.elements.aiReviewPanel.dataset.status = status;
        this.elements.aiReviewFixAllBtn.hidden = true;
        if (!review) {
            this.elements.aiReviewSummary.textContent = qualityMode === 'economy'
                ? '经济模式不自动调用 AI 质检，可手动抽检或二审'
                : '等待 AI 质检结果，也可手动重新发起质检';
            this.elements.aiReviewMeta.textContent =
                `${modeLabels[qualityMode] || '均衡模式'} · ${statusLabels[status]}`;
            this.elements.aiReviewFindings.innerHTML = '';
            return;
        }
        const reviewMode = modeLabels[review.mode] || review.mode || '审查';
        const pages = completed && review.reviewed_pages?.length
            ? `已审查 ${review.reviewed_pages.join('、')} 页`
            : '';
        const cost = Number(review.estimated_cost_cny || 0);
        const providerLabel = review.provider === 'deepseek'
            ? 'DeepSeek'
            : (review.provider === 'openai' ? 'OpenAI' : '');
        this.elements.aiReviewSummary.textContent =
            review.summary || statusLabels[status] || '审查完成';
        this.elements.aiReviewMeta.textContent = [
            reviewMode,
            !completed && status === 'failed' ? '质检未完成' : (statusLabels[status] || status),
            providerLabel,
            review.model ? `模型 ${review.model}` : '',
            review.estimated_cost_cny == null ? '费用未核算' : `约 ${cost.toFixed(4)} 元`,
            pages
        ].filter(Boolean).join(' · ');
        const findings = (completed || review.stale) && Array.isArray(review.findings) ? review.findings : [];
        const fixableFindings = findings.filter(item =>
            !item.applied && Number(item.page_number) > 0 && String(item.replacement_script || '').trim()
        );
        this.elements.aiReviewFixAllBtn.hidden = fixableFindings.length === 0;
        this.elements.aiReviewFixAllBtn.disabled = Boolean(this.courseReviewFixing);
        if (!findings.length) {
            const emptyMessage = !completed
                ? (review.running ? '质检正在后台进行，结果会自动更新' : (status === 'pending' ? '请重新运行 AI 质检' : '质检未完成，无法判断课程质量，请重新运行 AI 质检'))
                : (status === 'passed' ? '未发现具体问题' : '未返回具体问题，请重新运行 AI 质检');
            this.elements.aiReviewFindings.innerHTML =
                `<div class="ai-review-empty">${emptyMessage}</div>`;
            return;
        }
        const appliedPages = review.applied_pages || [];
        const renderFinding = (item, index) => `
            <details class="ai-review-finding ${item.applied ? 'applied' : this._escAttr(item.level || 'info')}"
                     data-page-number="${Number(item.page_number) || 0}">
                <summary class="ai-review-finding-summary">
                    <span>第 ${Number(item.page_number) || '-'} 页 · ${this._esc(item.category || '内容质量')}</span>
                    <span class="ai-review-finding-preview">${this._esc(item.message || '')}</span>
                    <span class="ai-review-finding-state">${item.applied ? '已应用并保存' : '待处理'}</span>
                </summary>
                <div class="ai-review-finding-body">
                    <button type="button" class="ai-review-finding-detail" title="定位到本页讲稿">
                        <strong>${this._esc(item.message || '')}</strong>
                        ${item.suggestion ? `<small>${this._esc(item.suggestion)}</small>` : ''}
                        <span>查看本页讲稿 →</span>
                    </button>
                    ${item.replacement_script ? `
                        <button type="button" class="ai-review-apply-fix" data-finding-index="${index}" ${item.applied || this.courseReviewFixing ? 'disabled' : ''}>
                            ${item.applied ? '已应用并保存' : '应用讲稿修复'}
                        </button>
                    ` : '<span class="ai-review-manual-fix">需手动处理</span>'}
                </div>
            </details>
        `;
        const pendingItems = [];
        const appliedItems = [];
        findings.forEach((item, index) => {
            (item.applied ? appliedItems : pendingItems).push(renderFinding(item, index));
        });
        const appliedCount = new Set(findings.filter(item => item.applied).map(item => Number(item.page_number))).size;
        this.elements.aiReviewFindings.innerHTML = pendingItems.join('') + (appliedItems.length ? `
            <details class="ai-review-applied-group">
                <summary>已应用并保存 ${appliedCount} 页讲稿 · 展开查看修复记录</summary>
                <div class="ai-review-applied-content">
                    <div class="ai-review-applied-notice">
                        已应用并保存：第 ${appliedPages.map(Number).join('、')} 页讲稿。
                        智能切课时长和自动推荐范围已同步，手动范围保留；继续生成时将使用新讲稿生成配音、字幕，并按当前课程包装设置合成视频。
                        请重新质检确认修复效果。
                    </div>
                    ${appliedItems.join('')}
                </div>
            </details>` : '');
        this.elements.aiReviewFindings
            .querySelectorAll('.ai-review-finding-detail')
            .forEach(button => {
                button.addEventListener('click', () => {
                    const pageNumber = Number(button.closest('.ai-review-finding')?.dataset.pageNumber);
                    if (pageNumber) this.goToPreviewPage(pageNumber, { focusEditor: true });
                });
            });
        this.elements.aiReviewFindings
            .querySelectorAll('.ai-review-apply-fix')
            .forEach(button => {
                button.addEventListener('click', () => {
                    const item = findings[Number(button.dataset.findingIndex)];
                    this.applyCourseReviewFixes(item ? [item] : []);
                });
            });
    }

    async applyCourseReviewFixes(findings = null) {
        if (this.courseReviewFixing) return;
        const source = Array.isArray(findings)
            ? findings
            : (Array.isArray(this.currentAIReview?.findings) ? this.currentAIReview.findings : []);
        const fixesByPage = new Map();
        source.forEach(item => {
            if (item.applied) return;
            const pageNumber = Number(item.page_number);
            const replacement = String(item.replacement_script || '').trim();
            if (pageNumber > 0 && replacement) fixesByPage.set(pageNumber, replacement);
        });
        if (!fixesByPage.size) {
            this.showStatus('error', '当前质检结果没有可直接应用的修复讲稿');
            return;
        }
        this.courseReviewFixing = true;
        this.elements.aiReviewFixAllBtn.disabled = true;
        this.elements.aiReviewFixAllBtn.textContent = '正在应用并保存…';
        this.elements.aiReviewFindings.querySelectorAll('.ai-review-apply-fix').forEach(button => {
            button.disabled = true;
        });
        try {
            let applied = 0;
            fixesByPage.forEach((replacement, pageNumber) => {
                const card = this.previewCardByPage(pageNumber);
                const textarea = card?.querySelector('.course-preview-script');
                if (!textarea) return;
                if (textarea.value.trim() !== replacement) {
                    textarea.value = replacement;
                    textarea.dispatchEvent(new Event('input', { bubbles: true }));
                }
                applied += 1;
            });
            if (!applied) {
                this.showStatus('error', '未找到建议对应的讲稿页，请刷新后重试');
                return;
            }
            clearTimeout(this.previewAutoSaveTimer);
            const saved = await this.savePreviewScripts({ automatic: true });
            if (saved) {
                const confirmed = (this.currentAIReview?.applied_pages || [])
                    .filter(number => fixesByPage.has(Number(number))).length;
                this.showStatus(confirmed ? 'success' : 'info', confirmed
                    ? `已应用并保存 ${confirmed} 页讲稿，后续生成将使用新内容；请重新质检确认效果`
                    : '已保存最新讲稿；修复内容已被后续编辑改变，请重新质检确认');
            } else {
                this.showStatus('error', '修复尚未确认保存成功，请重试或手动保存');
            }
        } finally {
            this.courseReviewFixing = false;
            this.elements.aiReviewFixAllBtn.textContent = '一键修复全部';
            this.renderCourseReview(this.currentAIReview, this.elements.coursePreviewModule.dataset.qualityMode || 'balanced');
        }
    }

    async runCourseReview(mode) {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        if (!taskId) return;
        if (!await this.savePreviewScripts({ automatic: true })) return;
        clearTimeout(this.reviewPollTimer);
        this.reviewPollToken = {};
        const button = mode === 'full'
            ? this.elements.aiReviewFullBtn
            : this.elements.aiReviewSampleBtn;
        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = mode === 'full' ? '二审中…' : '抽检中…';
        this.elements.aiReviewSummary.textContent =
            mode === 'full' ? 'AI 正在进行全课二审…' : 'AI 正在抽检课程讲稿…';
        let failedReview = null;
        try {
            const response = await fetch(`/api/course-review/${taskId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode })
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                failedReview = data.ai_review || null;
                throw new Error(data.error || 'AI 审查失败');
            }
            if (this.elements.coursePreviewModule.dataset.taskId !== taskId) return;
            this.renderCourseReview(
                data.ai_review,
                this.elements.coursePreviewModule.dataset.qualityMode || 'balanced'
            );
            this.showStatus('success', mode === 'full' ? '全课二审完成' : '抽检完成');
        } catch (error) {
            this.showStatus('error', error.message);
            this.renderCourseReview(
                failedReview || {
                    review_completed: false,
                    status: 'failed',
                    mode,
                    summary: error.message,
                    findings: [],
                    estimated_cost_cny: 0
                },
                this.elements.coursePreviewModule.dataset.qualityMode || 'balanced'
            );
        } finally {
            button.disabled = false;
            button.textContent = originalText;
        }
    }

    markCourseReviewStale(pageNumber) {
        if (!this.currentAIReview) return;
        this.currentAIReview = {
            ...this.currentAIReview,
            status: 'pending',
            summary: '讲稿已修改，建议重新运行 AI 审查',
            stale: true,
            findings: (this.currentAIReview.findings || []).map(item =>
                Number(item.page_number) === Number(pageNumber) ? { ...item, applied: false } : item
            ),
            applied_pages: (this.currentAIReview.applied_pages || []).filter(number => Number(number) !== Number(pageNumber))
        };
        this.renderCourseReview(
            this.currentAIReview,
            this.elements.coursePreviewModule.dataset.qualityMode || 'balanced'
        );
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
            .replace(/[^\p{L}\p{N}\s《》]+/gu, ' ')
            .replace(/\s+/g, ' ')
            .trim();
        if (!clean) return '';
        return clean.slice(0, 48);
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

    openCoursePreviewStage(card) {
        const stage = card?.querySelector('.course-preview-stage');
        if (!stage || this.expandedPreviewStage === stage) return;
        this.closeCoursePreviewStage();
        this.expandedPreviewStage = stage;
        const button = stage.querySelector('.course-preview-expand');
        button.textContent = '收起预览';
        button.setAttribute('aria-expanded', 'true');
        if (stage.showPopover) {
            stage.setAttribute('popover', 'manual');
            stage.showPopover();
        } else {
            stage.classList.add('preview-stage-expanded');
        }
        button.focus({ preventScroll: true });
    }

    closeCoursePreviewStage() {
        const stage = this.expandedPreviewStage;
        if (!stage) return;
        if (stage.hasAttribute('popover')) {
            stage.hidePopover();
            stage.removeAttribute('popover');
        }
        stage.classList.remove('preview-stage-expanded');
        const button = stage.querySelector('.course-preview-expand');
        button.textContent = '放大预览';
        button.setAttribute('aria-expanded', 'false');
        this.expandedPreviewStage = null;
        button.focus({ preventScroll: true });
    }

    async startCoursePreviewPlayback(startPage = this.currentPreviewPage) {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        if (!taskId) return;
        this.stopCoursePreviewPlayback();
        const session = this.coursePreviewSession = {};
        this.coursePreviewPlaying = true;
        this.coursePreviewActivePage = Number(startPage) || this.currentPreviewPage;
        this.updateCoursePreviewPagePlayerState(this.coursePreviewActivePage, '正在保存讲稿…');
        if (!await this.savePreviewScripts({ automatic: true })) {
            if (this.coursePreviewSession === session) this.stopCoursePreviewPlayback('保存失败，请重试');
            return;
        }
        if (this.coursePreviewSession !== session) return;
        this.stopVoicePreview();
        this.coursePreviewPlaying = true;
        this.currentPreviewPage = Number(startPage) || this.currentPreviewPage;
        this.updateCoursePreviewPagePlayerState(this.currentPreviewPage, '准备预览…');
        await this.playCoursePreviewPage(this.currentPreviewPage);
    }

    stopCoursePreviewPlayback(message = '预览已停止') {
        this.coursePreviewSession = null;
        this.coursePreviewRequest = null;
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
        const expanded = Boolean(this.expandedPreviewStage);
        this.coursePreviewActivePage = Number(pageNumber);
        const request = this.coursePreviewRequest = {};
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        const card = this.previewCardByPage(pageNumber);
        if (!taskId || !card) {
            this.stopCoursePreviewPlayback('预览已结束');
            return;
        }
        this.goToPreviewPage(pageNumber, { focusEditor: false });
        if (expanded) this.openCoursePreviewStage(card);
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
            if (this.coursePreviewRequest !== request) return;
            if (card && Array.isArray(data.focus_cues)) {
                card._focusCues = data.focus_cues;
                card._focusEvents = Array.isArray(data.focus_events) ? data.focus_events : null;
                this.renderCourseFocusEditor(card);
            }
            await this.playCoursePreviewAudio(data.audio_url, pageNumber, title);
        } catch (error) {
            if (this.coursePreviewRequest !== request) return;
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
        const cues = card?._focusCues || [];
        const fallback = this.makeSubtitleCues(
            card?.querySelector('.course-preview-script')?.value || ''
        );
        this.activateCoursePreviewSubtitles(card);
        this.updateCoursePreviewPagePlayerState(pageNumber, '正在播放本页');
        let focusFrame = null;
        const stopFocusFrames = () => {
            if (focusFrame !== null) cancelAnimationFrame(focusFrame);
            focusFrame = null;
        };
        const updateFocusFrame = () => {
            focusFrame = null;
            if (this.coursePreviewAudio !== audio || audio.paused || audio.ended) return;
            this.syncPlayingFocus(audio, card);
            focusFrame = requestAnimationFrame(updateFocusFrame);
        };
        audio.addEventListener('play', () => {
            stopFocusFrames();
            updateFocusFrame();
        });
        ['pause', 'ended', 'error'].forEach(event => audio.addEventListener(event, stopFocusFrames));
        ['seeking', 'seeked'].forEach(event => audio.addEventListener(event, () => this.syncPlayingFocus(audio, card)));
        audio.addEventListener('timeupdate', () => {
            if (this.coursePreviewAudio !== audio) return;
            this.syncPlayingSubtitleCue(audio, card, cues, fallback);
        });
        audio.addEventListener('loadedmetadata', () => {
            if (this.coursePreviewAudio !== audio) return;
            this.syncPlayingSubtitleCue(audio, card, cues, fallback);
        }, { once: true });
        audio.addEventListener('ended', () => {
            if (this.coursePreviewAudio !== audio) return;
            this.clearCoursePreviewSubtitlePlayback(card);
            const nextPage = this.elements.previewAutoplay?.checked
                ? this.nextPreviewPageNumber(pageNumber) : null;
            if (nextPage) {
                this.playCoursePreviewPage(nextPage);
            } else {
                this.stopCoursePreviewPlayback(this.elements.previewAutoplay?.checked ? '课程预览播放完成' : '本页预览播放完成');
            }
        }, { once: true });
        audio.addEventListener('error', () => {
            if (this.coursePreviewAudio !== audio) return;
            this.stopCoursePreviewPlayback('预览音频播放失败');
            this.showStatus('error', '预览音频播放失败');
        }, { once: true });
        try {
            await audio.play();
        } catch (error) {
            if (this.coursePreviewAudio !== audio) return;
            throw error;
        }
    }

    updateCoursePreviewPagePlayerState(activePageNumber = null, status = '') {
        if (this.elements.previewPlaybackDock) {
            this.elements.previewPlaybackDock.hidden = !this.coursePreviewPlaying;
        }
        if (this.elements.previewPlaybackStatus) {
            this.elements.previewPlaybackStatus.textContent = `第 ${activePageNumber || this.coursePreviewActivePage} 页 · ${status}`;
        }
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
                    statusNode.textContent = isActive ? status
                        : Number(card.dataset.pageNumber) === Number(this.coursePreviewActivePage) && status
                            ? status : '使用本页讲稿预览 PPT、字幕和配音';
                }
            });
    }

    activateCoursePreviewSubtitles(card) {
        this.clearCoursePreviewSubtitlePlayback();
        if (!card) return;
        this.coursePreviewSubtitlePage = card;
        card.classList.add('playing-preview');
        this.renderCourseFocusEditor(card);
        this.syncCourseFocusCue(card, -1);
    }

    clearCoursePreviewSubtitlePlayback(card = null) {
        const target = card || this.coursePreviewSubtitlePage;
        if (target) {
            target.classList.remove('playing-preview');
            target.querySelectorAll('.course-focus-cue-seek').forEach(button => {
                button.disabled = true;
            });
            target.querySelectorAll('.course-focus-target.active').forEach(node => node.classList.remove('active'));
            const now = target.querySelector('.course-focus-now');
            if (now) {
                now.textContent = '当前讲解位置将在播放时显示';
                now.classList.remove('low-confidence');
            }
            const sample = target.querySelector('.course-preview-subtitle-sample');
            if (sample) sample.hidden = false;
            this.updatePageSubtitleSample(target);
        }
        if (!card) {
            this.coursePreviewSubtitlePage = null;
        }
    }

    syncPlayingSubtitleCue(audio, card, cues, fallback) {
        if (!card || audio !== this.coursePreviewAudio) return;
        const timed = cues.length > 0 && cues.every(cue =>
            Number.isFinite(cue.start) && Number.isFinite(cue.end) && cue.end > cue.start
        );
        const index = timed ? cues.findIndex(cue =>
            audio.currentTime >= cue.start && audio.currentTime < cue.end
        ) : -1;
        let text = cues[index]?.text || '';
        if (!timed && audio.duration > 0 && fallback.length) {
            const fallbackIndex = Math.min(fallback.length - 1,
                Math.floor(audio.currentTime / audio.duration * fallback.length));
            text = fallback[fallbackIndex] || '';
        }
        const sample = card.querySelector('.course-preview-subtitle-sample');
        if (sample) sample.hidden = !text;
        if (text) this.renderSubtitlePreviewImage(card, text);
        this.syncPlayingFocus(audio, card);
    }

    previewFocusEvents(cues) {
        const events = [];
        cues.forEach(cue => {
            const ids = cue.target_ids || (cue.target_id ? [cue.target_id] : []);
            const manual = Boolean(cue.manual || cue.reviewed);
            if (!ids.length || !Number.isFinite(cue.start) || !Number.isFinite(cue.end)) return;
            const previous = events[events.length - 1];
            if (previous && JSON.stringify(previous.target_ids) === JSON.stringify(ids)
                && previous.manual === manual && previous.end === cue.start) {
                previous.end = cue.end;
            } else {
                events.push({ start: cue.start, end: cue.end, target_id: cue.target_id, target_ids: ids, manual, mapping_source: cue.mapping_source || cue.source || 'fallback', confidence: cue.confidence });
            }
        });
        return events;
    }

    smoothPreviewFocusEvents(events, maxSeconds) {
        if (!(maxSeconds > 0)) return events;
        const result = [];
        const targets = event => JSON.stringify([...(event.target_ids || [event.target_id]).filter(Boolean)].sort());
        for (let i = 0; i < events.length; i += 1) {
            const left = events[i], middle = events[i + 1], right = events[i + 2];
            if (middle && right && targets(left) === targets(right) && targets(left) !== targets(middle)
                && ![left, middle, right].some(event => event.reviewed || event.manual)
                && ['fallback', 'automatic'].includes(middle.mapping_source)
                && middle.confidence != null && Number(middle.confidence) < 0.5
                && middle.end - middle.start > 0 && middle.end - middle.start <= maxSeconds
                && Math.abs(left.end - middle.start) < 0.000001
                && Math.abs(middle.end - right.start) < 0.000001) {
                result.push({ ...left, end: right.end });
                i += 2;
            } else {
                result.push(left);
            }
        }
        return result;
    }

    visibleCourseFocusEvents(card, events) {
        if (card._focusMode === 'off') return [];
        if (card._focusMode === 'manual') return events.filter(event => event.manual || event.reviewed);
        return events;
    }

    underlineDrawProgress(events, index, targetId, time) {
        const contains = event => (event?.target_ids || [event?.target_id]).includes(targetId);
        if (index < 0 || !contains(events[index])) return 0;
        let first = index, last = index;
        while (first > 0 && contains(events[first - 1])
            && Math.abs(events[first - 1].end - events[first].start) < .000001) first--;
        while (last + 1 < events.length && contains(events[last + 1])
            && Math.abs(events[last].end - events[last + 1].start) < .000001) last++;
        const seconds = Math.min(.4, (events[last].end - events[first].start) / 2);
        return seconds > 0 ? Math.max(0, Math.min(1, (time - events[first].start) / seconds)) : 1;
    }

    syncPlayingFocus(audio, card) {
        if (!card || audio !== this.coursePreviewAudio) return;
        const events = card._focusEvents ?? this.previewFocusEvents(card._focusCues || []);
        const visible = this.visibleCourseFocusEvents(card, events);
        const smoothed = this.smoothPreviewFocusEvents(visible, Number(this.elements.focusSmoothingSeconds?.value || 0));
        const index = smoothed.findIndex(event => audio.currentTime >= event.start && audio.currentTime < event.end);
        card.querySelectorAll('.course-focus-target').forEach(node => {
            const progress = this.underlineDrawProgress(smoothed, index, node.dataset.targetId, audio.currentTime);
            node.style.setProperty('--focus-draw-progress', progress);
            const focus = smoothed[index];
            node.classList.toggle('active', Boolean(focus) && (focus.target_ids || [focus.target_id]).includes(node.dataset.targetId));
        });
    }

    scheduleCourseFocusSave() {
        this.elements.coursePreviewSaveState.textContent = '等待自动保存…';
        this.elements.coursePreviewSaveState.classList.remove('saved');
        clearTimeout(this.previewAutoSaveTimer);
        this.previewAutoSaveTimer = setTimeout(() => this.savePreviewScripts({ automatic: true }), 400);
    }

    updateCourseFocusCueTarget(card, index, targetId) {
        const cue = card._focusCues[index];
        const automatic = targetId === null;
        const targetIds = targetId ? [targetId] : [];
        const updated = { ...cue };
        if (automatic) {
            for (const key of ['anchor_id', 'model_target_id', 'action', 'original_target_id', 'reviewed']) delete updated[key];
        }
        card._focusCues[index] = {
            ...updated, target_id: targetId || '', target_ids: targetIds,
            focus_mode: automatic ? 'auto' : targetId ? 'target' : 'off',
            confidence: automatic ? 0 : 1, source: automatic ? 'fallback' : 'manual',
            mapping_source: automatic ? 'automatic' : 'manual', manual: !automatic
        };
        if (!automatic) card._focusCues[index].anchor_id = targetId;
        card._focusEventsManualClear = false;
        if (!Array.isArray(card._focusEvents)
            || !Number.isFinite(cue.start) || !Number.isFinite(cue.end)
            || cue.end <= cue.start) return;
        // Replace only this narration interval, preserving calibration on either side.
        const events = card._focusEvents.flatMap(event => {
            if (event.end <= cue.start || event.start >= cue.end) return [event];
            const remaining = [];
            if (event.start < cue.start) remaining.push({ ...event, end: cue.start });
            if (event.end > cue.end) remaining.push({ ...event, start: cue.end });
            return remaining;
        });
        if (!automatic) events.push({
            start: cue.start, end: cue.end, target_ids: targetIds,
            binding: 'cue',
            reviewed: true, manual: true, needs_review: false,
            mapping_source: 'manual', confidence: 1
        });
        card._focusEvents = events.sort((a, b) => a.start - b.start);
    }

    renderCourseFocusEditor(card) {
        const overlayRoot = card.querySelector('.course-focus-overlays');
        const editor = card.querySelector('.course-focus-editor');
        const targets = card._focusTargets || [];
        const cues = card._focusCues || [];
        if (!overlayRoot || !editor) return;
        overlayRoot.dataset.focusStyle = this.elements.focusHighlightStyle?.value || 'underline';
        overlayRoot.style.setProperty('--focus-color', this.elements.focusHighlightColor?.value || '#FFAE1F');
        overlayRoot.style.setProperty('--focus-line-width', this.elements.focusHighlightWidth?.value || 2);
        overlayRoot.innerHTML = '';
        targets.forEach(target => {
            const box = document.createElement('button');
            box.type = 'button';
            box.className = 'course-focus-target';
            box.dataset.targetId = target.id;
            box.title = target.text || '页面元素';
            box.style.left = `${Number(target.x || 0) * 100}%`;
            box.style.top = `${Number(target.y || 0) * 100}%`;
            box.style.width = `${Number(target.width || 0) * 100}%`;
            box.style.height = `${Number(target.height || 0) * 100}%`;
            box.style.setProperty('--focus-line-unit', `${100 / (1080 * Math.max(.001, Number(target.height || 0)))}%`);
            overlayRoot.appendChild(box);
        });
        editor.innerHTML = '<strong>讲解焦点与校准</strong>';
        const controls = document.createElement('label');
        controls.className = 'course-focus-mode-control';
        controls.innerHTML = `本页焦点
            <select aria-label="本页讲解焦点模式">
                <option value="auto">自动判断</option>
                <option value="off">整页不显示</option>
                <option value="manual">仅显示手动指定</option>
            </select>`;
        const modeSelect = controls.querySelector('select');
        modeSelect.value = card._focusMode || 'auto';
        modeSelect.addEventListener('change', () => {
            card._focusMode = modeSelect.value;
            this.renderCourseFocusEditor(card);
            this.scheduleCourseFocusSave();
        });
        editor.appendChild(controls);
        const hint = document.createElement('span');
        hint.textContent = card._focusMode === 'off'
            ? '本页视频和预览均不显示焦点；原有校准已保留。'
            : card._focusMode === 'manual'
                ? '仅显示手动指定的片段或时间区间，其余内容不显示焦点。'
                : '概述、过渡和无明确对应位置的讲解不显示焦点；可逐条覆盖自动判断。';
        editor.appendChild(hint);
        if (!targets.length) {
            const empty = document.createElement('span');
            empty.className = 'course-focus-empty';
            empty.textContent = '本页未识别到可跟随的页面对象';
            editor.appendChild(empty);
            return;
        }
        cues.forEach((cue, index) => {
            const row = document.createElement('label');
            row.className = 'course-focus-cue-row';
            const manual = Boolean(cue.manual || cue.reviewed);
            const cueMode = cue.target_id
                ? (['segment_audio', 'tts_word_boundary'].includes(cue.timing_source) ? '锚点 · 真实音频时间' : '锚点 · 待生成时间')
                : '仅同步讲稿 · 不强行框选';
            row.innerHTML = `
                <span>${this._esc(cue.text || `讲解片段 ${index + 1}`)}<small>${manual ? '手动' : '自动'} · ${cueMode}</small></span>
                <select aria-label="讲解片段 ${index + 1} 对应位置">
                    <option value="__auto__" ${manual ? '' : 'selected'}>自动判断${!manual ? (card._focusMode === 'off' ? '（整页已关闭）' : card._focusMode === 'manual' || !cue.target_id ? '（当前不显示）' : '（当前显示）') : ''}</option>
                    <option value="" ${manual && !cue.target_id ? 'selected' : ''}>此片段不显示焦点</option>
                    ${targets.map(target => `<option value="${this._escAttr(target.id)}" ${manual && target.id === cue.target_id ? 'selected' : ''}>${this._esc(target.text || target.id)}</option>`).join('')}
                </select>
            `;
            row.querySelector('select').addEventListener('change', event => {
                this.updateCourseFocusCueTarget(card, index, event.target.value === '__auto__' ? null : event.target.value);
                this.renderCourseFocusEditor(card);
                if (this.coursePreviewSubtitlePage !== card) this.syncCourseFocusCue(card, index);
                this.scheduleCourseFocusSave();
            });
            const seek = document.createElement('button');
            seek.type = 'button';
            seek.className = 'course-focus-cue-seek';
            seek.textContent = '试听';
            seek.disabled = this.coursePreviewSubtitlePage !== card || !Number.isFinite(cue.start);
            seek.addEventListener('click', () => {
                if (this.coursePreviewSubtitlePage === card && this.coursePreviewAudio) {
                    this.coursePreviewAudio.currentTime = cue.start;
                }
            });
            row.prepend(seek);
            row.addEventListener('mouseenter', () => {
                if (this.coursePreviewSubtitlePage !== card) this.syncCourseFocusCue(card, index);
            });
            editor.appendChild(row);
        });
        const events = card._focusEvents ?? this.previewFocusEvents(cues).map(event => ({
            start: event.start, end: event.end, target_ids: event.target_ids || [event.target_id],
            reviewed: event.manual, mapping_source: event.mapping_source, confidence: event.confidence
        }));
        {
            const heading = document.createElement('strong');
            heading.textContent = events.some(event => event.needs_review)
                ? '独立焦点时间（讲稿已修改，请重新核对）' : '独立焦点时间';
            editor.appendChild(heading);
            events.forEach((item, index) => {
                const row = document.createElement('div');
                row.className = 'course-focus-cue-row';
                row.innerHTML = `
                    <span>第 ${index + 1} 段
                        <input type="number" class="focus-start" min="0" step="0.01" value="${Number(item.start)}" aria-label="焦点开始秒数">
                        至 <input type="number" class="focus-end" min="0" step="0.01" value="${Number(item.end)}" aria-label="焦点结束秒数">
                    </span>
                    <select multiple aria-label="焦点对应位置">
                        ${targets.map(target => `<option value="${this._escAttr(target.id)}" ${(item.target_ids || []).includes(target.id) ? 'selected' : ''}>${this._esc(target.text || target.id)}</option>`).join('')}
                    </select>
                `;
                row.addEventListener('change', () => {
                    const start = Number(row.querySelector('.focus-start').value);
                    const end = Number(row.querySelector('.focus-end').value);
                    const previous = events[index - 1];
                    const next = events[index + 1];
                    if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 ||
                        end <= start || (previous && start < previous.end) || (next && end > next.start)) {
                        this.showStatus('error', '焦点时间须按顺序排列且不能重叠');
                        this.renderCourseFocusEditor(card);
                        return;
                    }
                    events[index] = {
                        ...item, start, end, binding: 'interval',
                        target_ids: Array.from(row.querySelector('select').selectedOptions, option => option.value),
                        reviewed: true, manual: true, needs_review: false, mapping_source: 'manual', confidence: 1
                    };
                    card._focusEvents = events;
                    card._focusEventsManualClear = false;
                    this.scheduleCourseFocusSave();
                });
                const remove = document.createElement('button');
                remove.type = 'button';
                remove.textContent = '不显示';
                remove.addEventListener('click', () => {
                    // Preserve this deletion as an explicit no-focus interval.
                    events[index] = { ...item, binding: 'interval', target_ids: [], manual: true, reviewed: true, mapping_source: 'manual' };
                    card._focusEvents = events;
                    card._focusEventsManualClear = false;
                    this.renderCourseFocusEditor(card);
                    this.scheduleCourseFocusSave();
                });
                row.appendChild(remove);
                editor.appendChild(row);
            });
            const add = document.createElement('button');
            add.type = 'button';
            add.textContent = '添加焦点区间';
            add.addEventListener('click', () => {
                const duration = Math.max(0, ...cues.map(cue => Number(cue.end) || 0));
                let start = 0;
                let end = 0;
                for (const event of events) {
                    if (event.start - start >= 0.01) {
                        end = event.start;
                        break;
                    }
                    start = Math.max(start, event.end);
                }
                if (!end) end = duration;
                if (end - start < 0.01) {
                    this.showStatus('error', '请先生成配音，并为新焦点留出时间区间');
                    return;
                }
                events.push({
                    start, end, target_ids: [], reviewed: true, binding: 'interval',
                    manual: true, mapping_source: 'manual', confidence: 1
                });
                events.sort((a, b) => a.start - b.start);
                card._focusEvents = events;
                card._focusEventsManualClear = false;
                this.renderCourseFocusEditor(card);
                this.scheduleCourseFocusSave();
            });
            editor.appendChild(add);
        }
    }

    syncCourseFocusCue(card, cueIndex) {
        if (!card) return;
        const candidate = (card._focusCues || [])[cueIndex];
        const cue = this.visibleCourseFocusEvents(card, candidate ? [candidate] : [])[0];
        card.querySelectorAll('.course-focus-target').forEach(node => {
            node.classList.toggle('active', Boolean(cue) && node.dataset.targetId === cue.target_id);
        });
        const now = card.querySelector('.course-focus-now');
        if (now) {
            if (!cue) {
                now.textContent = '当前讲解位置将在播放时显示';
                now.classList.remove('low-confidence');
            } else {
                const confidence = Number(cue.confidence);
                const precise = Boolean(cue.target_id) && (!Number.isFinite(confidence) || confidence >= 0.34);
                now.textContent = `${precise ? '当前知识点' : '当前讲解'}：${cue.text || '未命名片段'}`;
                now.classList.toggle('low-confidence', !precise);
            }
        }
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
            reviewed: card.querySelector('.page-reviewed').checked,
            focus_mode: card._focusMode || 'auto',
            focus_cues: card._focusCues || [],
            focus_events_manual_clear: Boolean(card._focusEventsManualClear),
            ...(card._focusEvents !== null ? { focus_events: card._focusEvents } : {})
        }));
    }

    filterPreviewPages() {
        const onlyUnreviewed = this.elements.unreviewedOnly.checked;
        this.elements.coursePreviewPages.querySelectorAll('.course-preview-page').forEach(card => {
            card.hidden = onlyUnreviewed && card.querySelector('.page-reviewed').checked;
        });
    }

    estimatePreviewScriptSeconds(text) {
        const normalized = String(text || '').replace(/\s+/g, '');
        if (!normalized) return 3;
        const cjkChars = (normalized.match(/[\u3400-\u9fff]/g) || []).length;
        const latinTokens = normalized.match(/[A-Za-z0-9]+/g) || [];
        const latinChars = latinTokens.reduce((sum, token) => sum + token.length, 0);
        const otherChars = Math.max(0, normalized.length - cjkChars - latinChars);
        const strongPauses = (normalized.match(/[。！？!?；;]/g) || []).length * 0.45;
        const softPauses = (normalized.match(/[，、,：:]/g) || []).length * 0.22;
        const seconds = (
            cjkChars / 4.2
            + latinTokens.length / 2.6
            + otherChars / 5
            + strongPauses
            + softPauses
        );
        return Math.max(4, Math.round(seconds));
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
            const segmentSeconds = this.collectPreviewPageDurations()
                .filter(page => page.pageNumber >= segment.start_page && page.pageNumber <= segment.end_page)
                .reduce((sum, page) => sum + page.seconds, 0);
            const row = document.createElement('div');
            row.className = 'smart-cut-row';
            row.innerHTML = `
                <span class="smart-cut-index">${index + 1}</span>
                <input type="text" class="smart-cut-title"
                       value="${this._escAttr(segment.title || `第 ${index + 1} 课`)}"
                       aria-label="第 ${index + 1} 段标题">
                <label class="smart-cut-page">起始页
                    <input type="number" class="smart-cut-start" min="1"
                           value="${Number(segment.start_page) || 1}"
                           aria-label="第 ${index + 1} 段起始页">
                </label>
                <span class="smart-cut-dash">—</span>
                <label class="smart-cut-page">结束页
                    <input type="number" class="smart-cut-end" min="1"
                           value="${Number(segment.end_page) || 1}"
                           aria-label="第 ${index + 1} 段结束页">
                </label>
                <span class="smart-cut-estimate">${this.formatCourseDuration(segmentSeconds)}</span>
            `;
            row.querySelectorAll('input').forEach(input => {
                input.addEventListener('input', () => {
                    this.smartCutRecommendationOptions = null;
                    this.smartCutApplied = false;
                    smartCutSummary.textContent = '切课范围已修改，尚未应用；请点击“应用切课”，或继续生成完整视频';
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
        if (!await this.savePreviewScripts({ automatic: true })) return;
        const button = this.elements.smartCutRecommendBtn;
        button.disabled = true;
        button.textContent = '分析中...';
        try {
            const recommendationOptions = {
                target_minutes: Number(this.elements.cutDurationMinutes.value) || 5,
                priority: this.getSmartCutPriority()
            };
            const response = await fetch(`/api/course-segments/${taskId}/recommend`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(recommendationOptions)
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '智能切课失败');
            this.smartCutSegments = data.segments || [];
            this.smartCutRecommendationOptions = recommendationOptions;
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
        clearTimeout(this.previewAutoSaveTimer);
        if (!await this.savePreviewScripts({ automatic: true })) return;
        const segments = this.collectSmartCutSegments();
        if (!segments.length) return;
        const button = this.elements.smartCutApplyBtn;
        button.disabled = true;
        button.textContent = '应用中...';
        try {
            const response = await fetch(`/api/course-segments/${taskId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ segments, recommendation_options: this.smartCutRecommendationOptions || null })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '应用切课失败');
            this.smartCutSegments = data.segments || [];
            this.smartCutApplied = this.smartCutSegments.length > 0;
            this.renderSmartCutSegments();
            await this.savePreviewScripts({ automatic: true });
            this.showStatus('success', data.message || '已应用智能切课');
        } catch (error) {
            this.showStatus('error', error.message);
        } finally {
            button.disabled = this.smartCutApplied;
            button.textContent = '应用';
        }
    }

    collectSpeechSettings() {
        return {
            tts_engine: this.elements.ttsEngine.value,
            voice: this.elements.customVoice.value.trim() || this.elements.voiceSelect.value,
            tts_rate: this.elements.ttsRate.value,
            tts_emotion: this.elements.ttsEmotion.value,
            tts_emotion_scale: Number(this.elements.ttsEmotionScale.value),
            tts_sentence_pause: Number(this.elements.ttsSentencePause.value)
        };
    }

    collectPreviewMediaSettings() {
        return {
            burn_subtitles: this.elements.burnSubtitles.checked,
            focus_highlight: this.elements.focusHighlight?.checked !== false,
            focus_highlight_style: this.elements.focusHighlightStyle?.value || 'underline',
            focus_highlight_color: this.elements.focusHighlightColor?.value || '#FFAE1F',
            focus_highlight_width: Number(this.elements.focusHighlightWidth?.value || 2),
            focus_smoothing_seconds: Number(this.elements.focusSmoothingSeconds?.value || 0),
            ...this.collectCoursePackagingOptions(),
            ...this.collectVideoOptions(),
            ...this.collectSubtitleOptions()
        };
    }

    syncPreviewSpeechControls() {
        const host = document.getElementById('preview-speech-controls');
        if (!host) return;
        host.replaceChildren();
        for (const [key, label] of [['ttsEngine', '语音引擎'], ['voiceSelect', '音色'], ['ttsRate', '语速']]) {
            const original = this.elements[key];
            const wrapper = document.createElement('label');
            wrapper.textContent = label;
            const select = original.cloneNode(true);
            select.removeAttribute('id');
            select.removeAttribute('aria-hidden');
            select.className = 'select-input';
            select.value = original.value;
            select.setAttribute('aria-label', `审核区${label}`);
            select.addEventListener('change', () => {
                original.value = select.value;
                if (key === 'voiceSelect') this.elements.customVoice.value = '';
                original.dispatchEvent(new Event('change', { bubbles: true }));
            });
            wrapper.appendChild(select);
            host.appendChild(wrapper);
        }
    }

    updatePreviewSpeechSummary() {
        const summary = document.getElementById('preview-speech-summary');
        if (!summary) return;
        const speechSignature = JSON.stringify(this.collectSpeechSettings());
        if (this.previewSpeechSignature && this.previewSpeechSignature !== speechSignature) {
            this.stopCoursePreviewPlayback('语音设置已更新，请重新播放预览确认');
        }
        this.previewSpeechSignature = speechSignature;
        this.syncPreviewSpeechControls?.();
        const name = this.elements.customVoice.value.trim()
            || this.elements.voiceSelect.selectedOptions[0]?.textContent || '请选择音色';
        const engine = this.elements.ttsEngine.selectedOptions[0]?.textContent || '';
        summary.textContent = `当前配音：${engine} · ${name}。播放预览、保存或继续生成时应用当前设置；音色改变后将重新生成配音。`;
    }

    previewDraftKey(taskId) {
        return `vidppt.preview.${document.body.dataset.username || 'local'}.${taskId}`;
    }

    storePreviewDraft() {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        if (!taskId) return;
        this.previewDirty = true;
        try {
            localStorage.setItem(this.previewDraftKey(taskId), JSON.stringify({ pages: this.collectPreviewScripts(), strategy: this.collectCurrentStrategy() }));
        } catch (error) { console.warn('本地草稿保存失败', error); }
    }

    async reopenCourse(taskId) {
        try {
            const response = await fetch(`/api/tasks/${taskId}/reopen`, { method: 'POST' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error);
            const found = this.getItemByTaskId(taskId);
            if (found) this.updateItem(found.index, { status: 'awaiting_confirmation',
                videoPath: data.video_path, subtitlesPath: data.subtitles_path,
                cueTimelinePath: data.cue_timeline_path, videoSegments: data.video_segments });
            this.renderResultsGrid();
            await this.loadCoursePreview(taskId);
        } catch (error) { this.showStatus('error', error.message); }
    }

    async savePreviewScripts({ automatic = false } = {}) {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        if (!taskId) return false;
        this.storePreviewDraft?.();
        const save = () => this.persistPreviewScripts({ automatic, taskId });
        this.previewSaveQueue = (this.previewSaveQueue || Promise.resolve()).then(save, save);
        return this.previewSaveQueue;
    }

    async persistPreviewScripts({ automatic, taskId }) {
        if (taskId !== this.elements.coursePreviewModule.dataset.taskId) return false;
        if (!this.smartCutApplied && this.smartCutSegments.length) {
            this.smartCutSegments = this.collectSmartCutSegments();
        }
        const sequence = ++this.previewSaveSequence;
        const submittedPages = this.collectPreviewScripts();
        const submittedSpeech = this.collectSpeechSettings();
        const submittedMedia = this.collectPreviewMediaSettings();
        this.elements.coursePreviewSaveState.textContent = '保存中…';
        try {
            const response = await fetch(`/api/course-preview/${taskId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pages: submittedPages,
                    ...submittedSpeech,
                    media_settings: submittedMedia,
                    recommendation_options: this.smartCutRecommendationOptions || null
                })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '保存讲稿失败');
            if (taskId !== this.elements.coursePreviewModule.dataset.taskId) return false;
            if (JSON.stringify(submittedPages) !== JSON.stringify(this.collectPreviewScripts())
                || JSON.stringify(submittedSpeech) !== JSON.stringify(this.collectSpeechSettings())
                || JSON.stringify(submittedMedia) !== JSON.stringify(this.collectPreviewMediaSettings())) {
                return this.persistPreviewScripts({ automatic, taskId });
            }
            if (sequence !== this.previewSaveSequence) return false;
            (data.pages || []).forEach(page => {
                const card = this.previewCardByPage(page.page_number);
                if (!card) return;
                card._focusMode = page.focus_mode || 'auto';
                card._focusEventsManualClear = Boolean(page.focus_events_manual_clear);
                card._focusCues = page.focus_cues || [];
                card._focusEvents = page.focus_events || null;
                card.dataset.estimatedSeconds = String(page.estimated_seconds || 0);
                const seconds = Math.round(Number(page.estimated_seconds) || 0);
                card.querySelector('.course-preview-length').textContent =
                    `${page.script.trim().length} 字 · 预计 ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
                const label = card.querySelector('.course-preview-segment');
                if (label && page.lesson_segment) {
                    label.textContent = `第 ${page.lesson_segment.id} 段 · ${page.lesson_segment.title}`;
                }
                this.renderCourseFocusEditor(card);
            });
            if (data.ai_review) {
                this.renderCourseReview(data.ai_review, this.elements.coursePreviewModule.dataset.qualityMode || 'balanced');
            }
            if (!this.smartCutApplied && this.smartCutSegments.length) {
                // Keep manual drafts; regenerate automatic drafts from the saved script.
                if (Array.isArray(data.recommended_segments)) this.smartCutSegments = data.recommended_segments;
                this.renderSmartCutSegments();
            } else if (Array.isArray(data.lesson_segments)) {
                this.smartCutSegments = data.lesson_segments;
                this.smartCutApplied = this.smartCutSegments.length > 0;
                this.renderSmartCutSegments();
            } else {
                this.updateCourseDurationEstimate(data.duration_estimate || null);
            }
            this.elements.coursePreviewSaveState.textContent = data.speech_changed
                ? '草稿设置已保存，下次播放使用新音色'
                : (automatic ? '讲稿、配音、字幕和包装设置已自动保存' : '讲稿、配音、字幕和包装设置已保存');
            this.elements.coursePreviewSaveState.classList.add('saved');
            this.previewDirty = false;
            if (typeof localStorage !== 'undefined') {
                try { localStorage.removeItem(this.previewDraftKey(taskId)); } catch (_) {}
            }
            return true;
        } catch (error) {
            if (sequence !== this.previewSaveSequence) return false;
            this.elements.coursePreviewSaveState.textContent = '自动保存失败，请手动保存';
            this.elements.coursePreviewSaveState.classList.remove('saved');
            this.showStatus('error', error.message);
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
            this.renderCoursePreview(taskId, data.pages || [], [], null, null, this.elements.coursePreviewModule.dataset.qualityMode || 'balanced');
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
        if (!await this.savePreviewScripts({ automatic: true })) return;
        const button = this.elements.continueCourseBtn;
        button.disabled = true;
        if (!await this.confirmCourseReviewBeforeContinue()) {
            button.disabled = false;
            return;
        }
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
                    apply_segments: this.smartCutApplied,
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
                    focus_highlight: this.elements.focusHighlight?.checked !== false,
                    focus_highlight_style: this.elements.focusHighlightStyle?.value || 'underline',
                    focus_highlight_color: this.elements.focusHighlightColor?.value || '#FFAE1F',
                    focus_highlight_width: Number(this.elements.focusHighlightWidth?.value || 2),
                    focus_smoothing_seconds: Number(this.elements.focusSmoothingSeconds?.value || 0),
                    ...this.collectCoursePackagingOptions(),
                    ...this.collectVideoOptions(),
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

    async confirmCourseReviewBeforeContinue() {
        const qualityMode = this.elements.coursePreviewModule.dataset.qualityMode || 'balanced';
        if (qualityMode === 'economy') return true;
        const review = this.currentAIReview;
        if (review?.status === 'passed') return true;
        const expected = qualityMode === 'premium' ? '全课二审' : '抽检';
        const statusText = review
            ? `当前 AI 审查状态为“${review.status || '未知'}”。`
            : `当前尚未完成 ChatGPT ${expected}。`;
        return window.VidPPTUI.confirm(
            `${statusText}\n\n继续后会开始配音、字幕和视频合成；若之后再改讲稿，需要重跑后半段。是否仍继续？`,
            {
                title: 'AI 审查尚未通过',
                confirmText: '仍然继续'
            }
        );
    }

    async cancelCourse() {
        const taskId = this.elements.coursePreviewModule.dataset.taskId;
        const found = this.getItemByTaskId(taskId);
        if (!taskId || !found) return;
        if (!await window.VidPPTUI.confirm(
            '将放弃当前草稿及其讲稿修改、质检结果和切课范围，保留上传文件。重新提交时使用生成策略区的最新设置。仅修改音色可直接调整后重新播放，无需放弃草稿。',
            { title: '放弃草稿并返回策略？', confirmText: '放弃草稿' }
        )) return;
        clearTimeout(this.previewAutoSaveTimer);
        this.stopCoursePreviewPlayback();

        const button = this.elements.cancelCourseBtn;
        button.disabled = true;
        try {
            await this.previewSaveQueue;
            const response = await fetch(`/api/course-cancel/${taskId}`, {
                method: 'POST'
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '取消失败');

            this.updateItem(found.index, {
                taskId: null,
                strategy: null,
                strategySource: 'batch',
                status: 'pending',
                percentage: 0,
                stage: null,
                message: '请调整生成策略后重新生成',
                courseJsonPath: null,
                presentationPath: null,
                subtitlesPath: null,
                cueTimelinePath: null,
                previewPath: null,
                videoPath: null,
                error: null
            });
            this.elements.coursePreviewModule.hidden = true;
            delete this.elements.coursePreviewModule.dataset.taskId;
            this.smartCutSegments = [];
            this.smartCutApplied = false;
            this.smartCutRecommendationOptions = null;
            this.currentAIReview = null;
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
