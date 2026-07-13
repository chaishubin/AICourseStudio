class CoursePackagingDesigner {
    constructor() {
        this.storageKey = 'vidppt.currentStrategy.v1';
        this.editingTemplateId = new URLSearchParams(window.location.search).get('edit_template');
        this.editingTemplate = null;
        this.activeSide = 'intro';
        this.layout = {
            intro: { x: 9.5, y: 30, width: 70 },
            mid: { x: 9.5, y: 34, width: 70 },
            outro: { x: 9.5, y: 34, width: 70 }
        };
        this.logoLayout = {
            intro: { x: 75.5, y: 10 },
            mid: { x: 75.5, y: 10 },
            outro: { x: 75.5, y: 10 }
        };
        this.assets = {
            intro_background: null,
            mid_background: null,
            outro_background: null,
            intro_music: null,
            mid_music: null,
            outro_music: null,
            intro_video: null,
            mid_video: null,
            outro_video: null
        };
        this.templates = new Map();
        this.fields = {
            packaging_template: 'packaging-template',
            packaging_organization: 'packaging-organization',
            packaging_department: 'packaging-department',
            packaging_instructor: 'packaging-instructor',
            packaging_instructor_title: 'packaging-instructor-title',
            packaging_copyright: 'packaging-copyright',
            packaging_duration_seconds: 'packaging-duration',
            packaging_transition_seconds: 'packaging-transition-seconds',
            packaging_outro_text: 'packaging-outro-text',
            packaging_intro_label: 'packaging-intro-label',
            packaging_intro_title: 'packaging-intro-title',
            packaging_intro_subtitle: 'packaging-intro-subtitle',
            packaging_intro_duration_seconds: 'packaging-intro-duration',
            packaging_mid_title: 'packaging-mid-title',
            packaging_mid_subtitle: 'packaging-mid-subtitle',
            packaging_mid_label: 'packaging-mid-label',
            packaging_mid_duration_seconds: 'packaging-mid-duration',
            packaging_outro_title: 'packaging-outro-title',
            packaging_outro_subtitle: 'packaging-outro-subtitle',
            packaging_outro_duration_seconds: 'packaging-outro-duration',
            packaging_intro_accent_color: 'packaging-intro-accent-color',
            packaging_mid_accent_color: 'packaging-mid-accent-color',
            packaging_outro_accent_color: 'packaging-outro-accent-color',
            packaging_intro_primary_color: 'packaging-intro-primary-color',
            packaging_mid_primary_color: 'packaging-mid-primary-color',
            packaging_outro_primary_color: 'packaging-outro-primary-color',
            packaging_intro_text_color: 'packaging-intro-text-color',
            packaging_mid_text_color: 'packaging-mid-text-color',
            packaging_outro_text_color: 'packaging-outro-text-color',
            packaging_intro_visual_preset: 'packaging-intro-visual-preset',
            packaging_mid_visual_preset: 'packaging-mid-visual-preset',
            packaging_outro_visual_preset: 'packaging-outro-visual-preset',
            packaging_intro_background_source: 'packaging-intro-background-source',
            packaging_mid_background_source: 'packaging-mid-background-source',
            packaging_outro_background_source: 'packaging-outro-background-source',
            packaging_intro_background_style: 'packaging-intro-background-style',
            packaging_mid_background_style: 'packaging-mid-background-style',
            packaging_outro_background_style: 'packaging-outro-background-style',
            packaging_intro_logo_position: 'packaging-intro-logo-position',
            packaging_mid_logo_position: 'packaging-mid-logo-position',
            packaging_outro_logo_position: 'packaging-outro-logo-position',
            packaging_intro_logo_x: 'packaging-intro-logo-x',
            packaging_intro_logo_y: 'packaging-intro-logo-y',
            packaging_mid_logo_x: 'packaging-mid-logo-x',
            packaging_mid_logo_y: 'packaging-mid-logo-y',
            packaging_outro_logo_x: 'packaging-outro-logo-x',
            packaging_outro_logo_y: 'packaging-outro-logo-y',
            packaging_intro_motion_style: 'packaging-intro-motion-style',
            packaging_mid_motion_style: 'packaging-mid-motion-style',
            packaging_outro_motion_style: 'packaging-outro-motion-style',
            packaging_intro_music_style: 'packaging-intro-music-style',
            packaging_mid_music_style: 'packaging-mid-music-style',
            packaging_outro_music_style: 'packaging-outro-music-style'
        };
        this.checkboxes = {
            enable_intro: 'enable-intro',
            enable_mid: 'enable-mid',
            enable_outro: 'enable-outro',
            packaging_apply_to_segments: 'packaging-apply-segments',
            packaging_intro_use_slide_background: 'packaging-intro-use-slide-background',
            packaging_mid_use_slide_background: 'packaging-mid-use-slide-background',
            packaging_outro_use_slide_background: 'packaging-outro-use-slide-background',
            packaging_intro_enable_motion: 'packaging-intro-enable-motion',
            packaging_mid_enable_motion: 'packaging-mid-enable-motion',
            packaging_outro_enable_motion: 'packaging-outro-enable-motion',
            packaging_intro_enable_music: 'packaging-intro-enable-music',
            packaging_mid_enable_music: 'packaging-mid-enable-music',
            packaging_outro_enable_music: 'packaging-outro-enable-music'
        };
        this.restore();
        this.bind();
        this.syncLayoutBoxes();
        this.syncAssets();
        this.syncDesignerState();
        this.loadMusicLibrary();
        this.loadVideoLibraries();
        this.loadTemplates();
        this.refreshPreview();
    }

    element(id) { return document.getElementById(id); }

    storedStrategy() {
        try { return JSON.parse(localStorage.getItem(this.storageKey) || '{}') || {}; }
        catch (error) { console.warn('读取课程包装配置失败:', error); return {}; }
    }

    restore() {
        const strategy = this.storedStrategy();
        Object.entries(this.fields).forEach(([key, id]) => {
            if (strategy[key] !== undefined && this.element(id)) this.element(id).value = strategy[key];
        });
        Object.entries(this.checkboxes).forEach(([key, id]) => {
            if (strategy[key] !== undefined && this.element(id)) this.element(id).checked = Boolean(strategy[key]);
        });
        ['intro', 'mid', 'outro'].forEach(kind => {
            ['x', 'y', 'width'].forEach(name => {
                const value = Number(strategy[`packaging_${kind}_content_${name}`]);
                if (Number.isFinite(value)) this.layout[kind][name] = value;
            });
            ['x', 'y'].forEach(name => {
                const value = Number(strategy[`packaging_${kind}_logo_${name}`]);
                if (Number.isFinite(value)) this.logoLayout[kind][name] = value;
            });
        });
        ['intro', 'mid', 'outro'].forEach(side => {
            this.assets[`${side}_background`] = strategy[`packaging_${side}_background_path`] || strategy.packaging_background_path || null;
            this.assets[`${side}_music`] = strategy[`packaging_${side}_music_path`] || strategy.packaging_music_path || null;
            this.assets[`${side}_video`] = strategy[`packaging_${side}_video_path`] || null;
        });
    }

    bind() {
        this.element('packaging-save-btn').addEventListener('click', () => this.save());
        this.element('packaging-preview-refresh').addEventListener('click', () => this.refreshPreview());
        this.element('packaging-layout-reset').addEventListener('click', () => {
            this.layout[this.activeSide] = this.activeSide === 'intro'
                ? { x: 9.5, y: 30, width: 70 }
                : { x: 9.5, y: 34, width: 70 };
            this.syncLayoutBoxes();
            this.markDirty();
            this.refreshPreview();
        });
        this.element('packaging-preview-current').addEventListener('click', () => this.refreshPreview());
        this.element('packaging-show-safe-area').addEventListener('change', event => {
            document.querySelector('.packaging-preview-panel').classList.toggle('show-safe-area', event.target.checked);
        });
        this.element('packaging-copy-intro-style').addEventListener('click', () => this.copyCurrentStyle());
        this.element('packaging-template').addEventListener('change', event => {
            const template = this.templates.get(event.target.value);
            if (template && !template.builtin) this.applyTemplateConfig(template);
        });
        document.querySelectorAll('[data-packaging-tab]').forEach(tab => {
            tab.addEventListener('click', () => this.setActiveSide(tab.dataset.packagingTab));
        });
        document.querySelectorAll('[data-packaging-select]').forEach(group => {
            const select = this.element(group.dataset.packagingSelect);
            group.querySelectorAll('[data-value]').forEach(button => {
                button.addEventListener('click', () => {
                    select.value = button.dataset.value;
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                    this.syncDesignerState();
                });
            });
        });
        document.querySelectorAll('[data-packaging-presets]').forEach(group => {
            group.querySelectorAll('[data-preset]').forEach(button => {
                button.addEventListener('click', () => this.applyVisualPreset(group.dataset.packagingPresets, button));
            });
        });
        document.querySelectorAll('[data-packaging-source]').forEach(group => {
            group.querySelectorAll('[data-value]').forEach(button => {
                button.addEventListener('click', () => {
                    this.setBackgroundSource(group.dataset.packagingSource, button.dataset.value);
                    this.refreshPreview(group.dataset.packagingSource);
                });
            });
        });
        document.querySelectorAll('[data-packaging-palettes]').forEach(group => {
            group.querySelectorAll('button').forEach(button => {
                button.addEventListener('click', () => this.applyPalette(group.dataset.packagingPalettes, button.dataset));
            });
        });
        document.querySelectorAll('[data-logo-position-grid]').forEach(group => {
            group.querySelectorAll('[data-value]').forEach(button => {
                button.addEventListener('click', () => this.setLogoPosition(group.dataset.logoPositionGrid, button.dataset.value));
            });
        });
        document.querySelectorAll('.packaging-manager-page input, .packaging-manager-page select').forEach(control => {
            if (control.type !== 'file') control.addEventListener('change', () => {
                this.markDirty();
                if (/-(primary|accent|text)-color$/.test(control.id)) {
                    const side = control.id.split('-')[1];
                    this.element(`packaging-${side}-visual-preset`).value = 'custom';
                }
                this.syncDesignerState();
            });
        });
        ['intro', 'mid', 'outro'].forEach(side => {
            const video = this.element(`packaging-${side}-preview`);
            const canvas = video.closest('.packaging-preview-canvas');
            video.addEventListener('play', () => canvas.classList.add('is-playing'));
            ['pause', 'ended', 'emptied'].forEach(eventName => {
                video.addEventListener(eventName, () => canvas.classList.remove('is-playing'));
            });
            ['background', 'music', 'video'].forEach(media => {
                const kind = `${side}_${media}`;
                this.bindAsset(kind, `packaging-${side}-${media}-button`, `packaging-${side}-${media}-input`);
                this.bindRemove(kind, `packaging-${side}-${media}-remove`);
            });
            this.element(`packaging-${side}-music-library`).addEventListener('change', event => {
                this.assets[`${side}_music`] = event.target.value || null;
                this.element(`packaging-${side}-music-preview`).src = event.target.selectedOptions[0]?.dataset.url || '';
                this.syncAssets();
                this.markDirty();
            });
            this.element(`packaging-${side}-video-library`).addEventListener('change', event => {
                this.assets[`${side}_video`] = event.target.value || null;
                if (this.assets[`${side}_video`]) this.setBackgroundSource(side, 'video');
                this.syncAssets();
                this.markDirty();
                this.refreshPreview();
            });
        });
        this.bindLayoutEditor();
        this.bindLogoEditor();
    }

    async loadTemplates() {
        try {
            const suffix = this.editingTemplateId ? '?include_disabled=1' : '';
            const response = await fetch(`/api/course-packaging-templates${suffix}`);
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || '模板加载失败');
            this.templates = new Map(result.templates.map(template => [template.id, template]));
            const select = this.element('packaging-template');
            const stored = this.storedStrategy().packaging_template;
            select.replaceChildren();
            const system = document.createElement('optgroup');
            system.label = '系统模板';
            const custom = document.createElement('optgroup');
            custom.label = '自定义模板';
            result.templates.filter(template => !this.editingTemplateId || template.builtin).forEach(template => {
                const option = new Option(`${template.name}${template.is_default ? ' · 默认' : ''}`, template.id);
                (template.builtin ? system : custom).append(option);
            });
            if (system.children.length) select.append(system);
            if (custom.children.length) select.append(custom);
            const editingTemplate = this.editingTemplateId ? this.templates.get(this.editingTemplateId) : null;
            if (this.editingTemplateId && (!editingTemplate || editingTemplate.builtin)) {
                throw new Error('只能编辑自定义模板的详细内容');
            }
            this.editingTemplate = editingTemplate || null;
            const selected = editingTemplate?.base_template || (this.templates.has(stored) ? stored : result.default_template_id);
            select.value = selected;
            if (editingTemplate) {
                this.applyTemplateConfig(editingTemplate);
                this.enterTemplateEditMode(editingTemplate);
            }
        } catch (error) {
            console.warn('加载包装模板失败:', error);
            this.element('packaging-save-status').textContent = error.message;
        }
    }

    enterTemplateEditMode(template) {
        const heading = document.querySelector('.packaging-page-intro h2');
        const description = document.querySelector('.packaging-page-intro p');
        if (heading) heading.textContent = `编辑模板：${template.name}`;
        if (description) description.textContent = '正在编辑此模板保存的片头、片中、片尾内容、视觉、动效、声音和版式；保存后，所有使用该模板的新任务都会应用更新。';
        this.element('packaging-save-btn').textContent = '保存模板详细内容';
        this.element('packaging-save-scope').textContent = '保存范围：共享模板（影响后续使用）';
        this.element('packaging-save-status').textContent = '模板详细内容已载入';
    }

    applyTemplateConfig(template) {
        const config = template.config || {};
        Object.entries(this.fields).forEach(([key, id]) => {
            if (key !== 'packaging_template' && config[key] !== undefined && this.element(id)) {
                this.element(id).value = config[key];
            }
        });
        Object.entries(this.checkboxes).forEach(([key, id]) => {
            if (config[key] !== undefined && this.element(id)) this.element(id).checked = Boolean(config[key]);
        });
        ['intro', 'mid', 'outro'].forEach(side => {
            ['x', 'y', 'width'].forEach(name => {
                const value = Number(config[`packaging_${side}_content_${name}`]);
                if (Number.isFinite(value)) this.layout[side][name] = value;
            });
            ['x', 'y'].forEach(name => {
                const value = Number(config[`packaging_${side}_logo_${name}`]);
                if (Number.isFinite(value)) this.logoLayout[side][name] = value;
            });
            ['background', 'music', 'video'].forEach(media => {
                const key = `packaging_${side}_${media}_path`;
                if (config[key] !== undefined) this.assets[`${side}_${media}`] = config[key] || null;
            });
            if (!config[`packaging_${side}_background_source`]) {
                const inferred = this.assets[`${side}_video`] ? 'video'
                    : this.assets[`${side}_background`] ? 'image'
                        : config[`packaging_${side}_background_style`] === 'ppt' ? 'ppt' : 'theme';
                this.element(`packaging-${side}-background-source`).value = inferred;
            }
        });
        this.syncLayoutBoxes();
        this.syncAssets();
        this.syncDesignerState();
        this.markDirty();
        this.refreshPreview();
    }

    setActiveSide(side) {
        if (!['intro', 'mid', 'outro'].includes(side)) return;
        this.activeSide = side;
        document.querySelectorAll('[data-packaging-tab]').forEach(tab => {
            const active = tab.dataset.packagingTab === side;
            tab.classList.toggle('is-active', active);
            tab.setAttribute('aria-selected', String(active));
            tab.tabIndex = active ? 0 : -1;
        });
        document.querySelectorAll('[data-packaging-panel]').forEach(panel => {
            const active = panel.dataset.packagingPanel === side;
            panel.hidden = !active;
            panel.classList.toggle('is-active', active);
        });
        document.querySelectorAll('[data-packaging-preview]').forEach(preview => {
            preview.hidden = preview.dataset.packagingPreview !== side;
        });
        const names = { intro: '片头', mid: '片中转场', outro: '片尾' };
        this.element('packaging-preview-title').textContent = `${names[side]}预览`;
        this.syncLayoutBoxes();
        const video = this.element(`packaging-${side}-preview`);
        if (!video.src) this.refreshPreview(side);
        else this.element('packaging-preview-status').textContent = '使用当前已生成预览，修改后可重新生成';
    }

    syncDesignerState() {
        ['intro', 'mid', 'outro'].forEach(side => {
            const duration = this.element(`packaging-${side}-duration`);
            const durationLabel = document.querySelector(`[data-packaging-duration-label="${side}"]`);
            if (duration && durationLabel) durationLabel.textContent = `${Number(duration.value || 0)} 秒`;
            const enabled = this.element(`enable-${side}`)?.checked;
            const tab = this.element(`packaging-${side}-tab`);
            tab?.classList.toggle('is-disabled', !enabled);
            ['primary', 'accent', 'text'].forEach(name => {
                const color = this.element(`packaging-${side}-${name}-color`);
                const colorLabel = document.querySelector(`[data-packaging-color-label="${side}-${name}"]`);
                if (color && colorLabel) colorLabel.textContent = color.value.toUpperCase();
            });
            const preset = this.element(`packaging-${side}-visual-preset`)?.value;
            document.querySelectorAll(`[data-packaging-presets="${side}"] [data-preset]`).forEach(button => {
                button.classList.toggle('is-active', button.dataset.preset === preset);
            });
            const source = this.element(`packaging-${side}-background-source`)?.value || 'ppt';
            document.querySelectorAll(`[data-packaging-source="${side}"] [data-value]`).forEach(button => {
                button.classList.toggle('is-active', button.dataset.value === source);
            });
            document.querySelectorAll(`#packaging-${side}-panel [data-background-source-panel]`).forEach(panel => {
                panel.hidden = panel.dataset.backgroundSourcePanel !== source;
            });
            const logoPosition = this.element(`packaging-${side}-logo-position`)?.value;
            document.querySelectorAll(`[data-logo-position-grid="${side}"] [data-value]`).forEach(button => {
                button.classList.toggle('is-active', button.dataset.value === logoPosition);
            });
        });
        document.querySelectorAll('[data-packaging-select]').forEach(group => {
            const value = this.element(group.dataset.packagingSelect)?.value;
            group.querySelectorAll('[data-value]').forEach(button => {
                const active = button.dataset.value === value;
                button.classList.toggle('is-active', active);
                button.setAttribute('aria-pressed', String(active));
            });
        });
        this.syncLogoGuides();
    }

    copyCurrentStyle() {
        const source = this.activeSide;
        const fieldSuffixes = ['visual-preset', 'background-source', 'primary-color', 'accent-color', 'text-color', 'background-style', 'logo-position', 'logo-x', 'logo-y', 'motion-style', 'music-style'];
        const checkboxSuffixes = ['use-slide-background', 'enable-motion', 'enable-music'];
        ['intro', 'mid', 'outro'].filter(side => side !== source).forEach(side => {
            fieldSuffixes.forEach(suffix => {
                this.element(`packaging-${side}-${suffix}`).value = this.element(`packaging-${source}-${suffix}`).value;
            });
            checkboxSuffixes.forEach(suffix => {
                this.element(`packaging-${side}-${suffix}`).checked = this.element(`packaging-${source}-${suffix}`).checked;
            });
            this.logoLayout[side] = { ...this.logoLayout[source] };
        });
        this.syncDesignerState();
        this.markDirty();
        this.element('packaging-save-status').textContent = '已将当前段视觉应用到其他分段，尚未保存';
    }

    applyVisualPreset(side, button) {
        this.element(`packaging-${side}-visual-preset`).value = button.dataset.preset;
        this.element(`packaging-${side}-primary-color`).value = button.dataset.primary;
        this.element(`packaging-${side}-accent-color`).value = button.dataset.accent;
        this.element(`packaging-${side}-text-color`).value = button.dataset.text;
        this.element(`packaging-${side}-motion-style`).value = button.dataset.motion;
        this.setBackgroundSource(side, button.dataset.source, button.dataset.style);
        this.markDirty();
        this.syncDesignerState();
        this.refreshPreview(side);
    }

    applyPalette(side, palette) {
        this.element(`packaging-${side}-primary-color`).value = palette.primary;
        this.element(`packaging-${side}-accent-color`).value = palette.accent;
        this.element(`packaging-${side}-text-color`).value = palette.text;
        this.element(`packaging-${side}-visual-preset`).value = 'custom';
        this.syncDesignerState();
        this.markDirty();
        this.refreshPreview(side);
    }

    setBackgroundSource(side, source, style = null) {
        this.element(`packaging-${side}-background-source`).value = source;
        const backgroundStyle = this.element(`packaging-${side}-background-style`);
        const usePpt = this.element(`packaging-${side}-use-slide-background`);
        if (style) backgroundStyle.value = style;
        if (source === 'ppt') { backgroundStyle.value = 'ppt'; usePpt.checked = true; }
        if (source === 'theme') { if (backgroundStyle.value === 'ppt') backgroundStyle.value = 'gradient'; usePpt.checked = false; }
        if (source === 'image') { backgroundStyle.value = 'ppt'; usePpt.checked = false; }
        if (source === 'video') usePpt.checked = false;
        this.syncDesignerState();
        this.markDirty();
    }

    setLogoPosition(side, position) {
        this.element(`packaging-${side}-logo-position`).value = position;
        const fixed = {
            'top-left': { x: 6.5, y: 10 }, 'top-right': { x: 75.5, y: 10 },
            'bottom-left': { x: 6.5, y: 72 }, 'bottom-right': { x: 75.5, y: 72 }
        }[position];
        if (fixed) this.logoLayout[side] = fixed;
        this.writeLogoLayout(side);
        this.syncDesignerState();
        this.markDirty();
        this.refreshPreview(side);
    }

    markDirty() { this.element('packaging-save-status').textContent = '有未保存修改'; }

    collect() {
        const options = {};
        Object.entries(this.fields).forEach(([key, id]) => {
            const control = this.element(id);
            options[key] = control.type === 'number' ? Number(control.value) : control.value.trim();
        });
        Object.entries(this.checkboxes).forEach(([key, id]) => { options[key] = this.element(id).checked; });
        Object.entries(this.assets).forEach(([kind, path]) => { options[`packaging_${kind}_path`] = path; });
        ['intro', 'mid', 'outro'].forEach(kind => {
            const source = this.element(`packaging-${kind}-background-source`).value;
            if (source !== 'image') options[`packaging_${kind}_background_path`] = null;
            if (source !== 'video') options[`packaging_${kind}_video_path`] = null;
            options[`packaging_${kind}_content_x`] = this.layout[kind].x;
            options[`packaging_${kind}_content_y`] = this.layout[kind].y;
            options[`packaging_${kind}_content_width`] = this.layout[kind].width;
        });
        return options;
    }

    async save() {
        if (this.editingTemplate) {
            const button = this.element('packaging-save-btn');
            button.disabled = true;
            this.element('packaging-save-status').textContent = '正在保存模板…';
            try {
                const response = await fetch(`/api/course-packaging-templates/${encodeURIComponent(this.editingTemplate.id)}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ base_template: this.element('packaging-template').value, config: this.collect() })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || '模板保存失败');
                this.editingTemplate = result.template;
                this.element('packaging-save-status').textContent = '模板详细内容已保存';
            } catch (error) {
                this.element('packaging-save-status').textContent = error.message;
            } finally {
                button.disabled = false;
            }
            return;
        }
        try {
            localStorage.setItem(this.storageKey, JSON.stringify({ ...this.storedStrategy(), ...this.collect() }));
            this.element('packaging-save-status').textContent = '已保存，生产工作台将自动应用';
        } catch (error) {
            this.element('packaging-save-status').textContent = '保存失败，请检查浏览器存储权限';
        }
    }

    bindAsset(kind, buttonId, inputId) {
        const input = this.element(inputId);
        this.element(buttonId).addEventListener('click', () => input.click());
        input.addEventListener('change', async event => {
            const file = event.target.files[0];
            event.target.value = '';
            if (!file) return;
            const formData = new FormData();
            formData.append('kind', kind);
            formData.append('asset', file);
            const status = this.assetStatus(kind);
            status.textContent = '上传中...';
            try {
                const response = await fetch('/api/course-packaging-asset-upload', { method: 'POST', body: formData });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || '素材上传失败');
                this.assets[kind] = result.asset_path;
                const [side, media] = kind.split('_');
                if (media === 'background') this.setBackgroundSource(side, 'image');
                if (media === 'video') this.setBackgroundSource(side, 'video');
                this.syncAssets();
                if (kind.endsWith('_music')) await this.loadMusicLibrary();
                if (kind.endsWith('_video')) await this.loadVideoLibraries();
                this.markDirty();
                if (!kind.endsWith('_music')) this.refreshPreview();
            } catch (error) { status.textContent = error.message; }
        });
    }

    bindRemove(kind, buttonId) {
        this.element(buttonId).addEventListener('click', () => {
            this.assets[kind] = null;
            const [side, media] = kind.split('_');
            if ((media === 'background' && this.element(`packaging-${side}-background-source`).value === 'image')
                || (media === 'video' && this.element(`packaging-${side}-background-source`).value === 'video')) {
                this.setBackgroundSource(side, 'theme');
            }
            this.syncAssets();
            this.markDirty();
            if (!kind.endsWith('_music')) this.refreshPreview();
        });
    }

    assetStatus(kind) {
        return this.element(`packaging-${kind.replace('_', '-')}-status`);
    }

    syncAssets() {
        Object.keys(this.assets).forEach(kind => {
            const media = kind.split('_')[1];
            this.element(`packaging-${kind.replace('_', '-')}-remove`).hidden = !this.assets[kind];
            const active = media === 'background' ? '已使用自定义背景图' : media === 'music' ? '已使用自定义背景音乐' : '已使用动态背景视频';
            const empty = media === 'background' ? '未上传，使用背景模式' : media === 'music' ? '未上传，使用内置音乐' : '支持 MP4/MOV';
            this.assetStatus(kind).textContent = this.assets[kind] ? active : empty;
        });
        ['intro', 'mid', 'outro'].forEach(side => { this.element(`packaging-${side}-music-library`).value = this.assets[`${side}_music`] || ''; });
        ['intro', 'mid', 'outro'].forEach(side => { this.element(`packaging-${side}-video-library`).value = this.assets[`${side}_video`] || ''; });
    }

    async loadMusicLibrary() {
        try {
            const response = await fetch('/api/course-packaging-assets?kind=music');
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || '音乐素材库加载失败');
            ['intro', 'mid', 'outro'].forEach(side => {
                const select = this.element(`packaging-${side}-music-library`);
                select.replaceChildren(new Option('使用内置风格音乐', ''));
                result.assets.forEach(asset => {
                    const option = new Option(asset.name, asset.path);
                    option.dataset.url = asset.url;
                    select.add(option);
                });
                select.value = this.assets[`${side}_music`] || '';
                this.element(`packaging-${side}-music-preview`).src = select.selectedOptions[0]?.dataset.url || '';
            });
        } catch (error) { console.warn('加载音乐素材库失败:', error); }
    }

    async loadVideoLibraries() {
        await Promise.all(['intro', 'mid', 'outro'].map(async side => {
            try {
                const response = await fetch(`/api/course-packaging-assets?kind=${side}_video`);
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || '视频素材库加载失败');
                const select = this.element(`packaging-${side}-video-library`);
                select.replaceChildren(new Option('未选择视频素材', ''));
                result.assets.forEach(asset => select.add(new Option(asset.name, asset.path)));
                select.value = this.assets[`${side}_video`] || '';
            } catch (error) { console.warn(`加载${side === 'intro' ? '片头' : side === 'mid' ? '片中' : '片尾'}视频素材库失败:`, error); }
        }));
    }

    previewUrl(kind, media = 'video') {
        const values = this.collect();
        const params = new URLSearchParams({
            kind,
            ...Object.fromEntries(Object.entries(values).filter(([, value]) => value !== null)),
            course_title: '人工智能课程示例',
            segment_title: kind === 'intro' ? '第一讲 课程导入' : ''
        });
        return `/api/course-packaging-preview-${media}?${params.toString()}`;
    }

    refreshPreview(kind = this.activeSide) {
        const status = this.element('packaging-preview-status');
        const video = this.element(`packaging-${kind}-preview`);
        status.textContent = '正在合成当前分段预览，请稍候...';
        video.pause();
        video.onloadedmetadata = () => { status.textContent = '视频预览已更新，可播放查看动效与声音'; };
        video.onerror = () => { status.textContent = '视频预览生成失败'; };
        video.poster = this.previewUrl(kind, 'image');
        video.src = this.previewUrl(kind);
        video.load();
    }

    bindLayoutEditor() {
        document.querySelectorAll('[data-packaging-layout]').forEach(box => {
            box.addEventListener('pointerdown', event => {
                const kind = box.dataset.packagingLayout;
                const canvas = box.parentElement;
                const resizing = event.target.tagName === 'I';
                const start = { x: event.clientX, y: event.clientY };
                const original = { ...this.layout[kind] };
                const rect = canvas.getBoundingClientRect();
                box.classList.add('is-editing');
                box.setPointerCapture(event.pointerId);
                const move = moveEvent => {
                    const dx = (moveEvent.clientX - start.x) / rect.width * 100;
                    const dy = (moveEvent.clientY - start.y) / rect.height * 100;
                    if (resizing) this.layout[kind].width = Math.max(18, Math.min(95 - original.x, original.width + dx));
                    else {
                        this.layout[kind].x = Math.max(0, Math.min(100 - original.width, original.x + dx));
                        this.layout[kind].y = Math.max(0, Math.min(78, original.y + dy));
                    }
                    this.syncLayoutBoxes();
                };
                const up = () => {
                    box.removeEventListener('pointermove', move);
                    box.removeEventListener('pointerup', up);
                    box.removeEventListener('pointercancel', up);
                    box.classList.remove('is-editing');
                    this.markDirty();
                    this.refreshPreview();
                };
                box.addEventListener('pointermove', move);
                box.addEventListener('pointerup', up);
                box.addEventListener('pointercancel', up);
                event.preventDefault();
            });
        });
    }

    bindLogoEditor() {
        document.querySelectorAll('[data-packaging-logo]').forEach(guide => {
            guide.addEventListener('pointerdown', event => {
                const kind = guide.dataset.packagingLogo;
                if (this.element(`packaging-${kind}-logo-position`).value === 'none') return;
                const canvas = guide.parentElement;
                const rect = canvas.getBoundingClientRect();
                const start = { x: event.clientX, y: event.clientY };
                const original = { ...this.logoLayout[kind] };
                guide.classList.add('is-editing');
                guide.setPointerCapture(event.pointerId);
                const move = moveEvent => {
                    this.logoLayout[kind].x = Math.max(0, Math.min(82, original.x + (moveEvent.clientX - start.x) / rect.width * 100));
                    this.logoLayout[kind].y = Math.max(0, Math.min(84, original.y + (moveEvent.clientY - start.y) / rect.height * 100));
                    this.element(`packaging-${kind}-logo-position`).value = 'custom';
                    this.writeLogoLayout(kind);
                    this.syncDesignerState();
                };
                const up = () => {
                    guide.removeEventListener('pointermove', move);
                    guide.removeEventListener('pointerup', up);
                    guide.removeEventListener('pointercancel', up);
                    guide.classList.remove('is-editing');
                    this.markDirty();
                    this.refreshPreview(kind);
                };
                guide.addEventListener('pointermove', move);
                guide.addEventListener('pointerup', up);
                guide.addEventListener('pointercancel', up);
                event.preventDefault();
            });
        });
    }

    writeLogoLayout(kind) {
        this.element(`packaging-${kind}-logo-x`).value = this.logoLayout[kind].x.toFixed(2);
        this.element(`packaging-${kind}-logo-y`).value = this.logoLayout[kind].y.toFixed(2);
    }

    syncLogoGuides() {
        document.querySelectorAll('[data-packaging-logo]').forEach(guide => {
            const kind = guide.dataset.packagingLogo;
            const position = this.element(`packaging-${kind}-logo-position`)?.value;
            const layout = this.logoLayout[kind];
            guide.hidden = position === 'none';
            guide.style.left = `${layout.x}%`;
            guide.style.top = `${layout.y}%`;
        });
    }

    syncLayoutBoxes() {
        document.querySelectorAll('[data-packaging-layout]').forEach(box => {
            const layout = this.layout[box.dataset.packagingLayout];
            box.style.left = `${layout.x}%`;
            box.style.top = `${layout.y}%`;
            box.style.width = `${layout.width}%`;
            box.style.height = '34%';
        });
    }
}

document.addEventListener('DOMContentLoaded', () => new CoursePackagingDesigner());
