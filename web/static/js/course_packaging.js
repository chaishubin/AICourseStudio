class CoursePackagingDesigner {
    constructor() {
        this.storageKey = 'vidppt.currentStrategy.v1';
        this.layout = {
            intro: { x: 9.5, y: 30, width: 70 },
            outro: { x: 9.5, y: 34, width: 70 }
        };
        this.assets = {
            background: null,
            music: null,
            intro_video: null,
            outro_video: null
        };
        this.fields = {
            packaging_template: 'packaging-template',
            packaging_organization: 'packaging-organization',
            packaging_instructor: 'packaging-instructor',
            packaging_duration_seconds: 'packaging-duration',
            packaging_outro_text: 'packaging-outro-text',
            packaging_intro_label: 'packaging-intro-label',
            packaging_intro_title: 'packaging-intro-title',
            packaging_intro_subtitle: 'packaging-intro-subtitle',
            packaging_intro_duration_seconds: 'packaging-intro-duration',
            packaging_outro_title: 'packaging-outro-title',
            packaging_outro_subtitle: 'packaging-outro-subtitle',
            packaging_outro_duration_seconds: 'packaging-outro-duration',
            packaging_accent_color: 'packaging-accent-color',
            packaging_background_style: 'packaging-background-style',
            packaging_logo_position: 'packaging-logo-position',
            packaging_motion_style: 'packaging-motion-style',
            packaging_music_style: 'packaging-music-style'
        };
        this.checkboxes = {
            enable_intro: 'enable-intro',
            enable_outro: 'enable-outro',
            packaging_apply_to_segments: 'packaging-apply-segments',
            packaging_use_slide_background: 'packaging-use-slide-background',
            packaging_enable_motion: 'packaging-enable-motion',
            packaging_enable_music: 'packaging-enable-music'
        };
        this.restore();
        this.bind();
        this.syncLayoutBoxes();
        this.syncAssets();
        this.loadMusicLibrary();
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
        ['intro', 'outro'].forEach(kind => {
            ['x', 'y', 'width'].forEach(name => {
                const value = Number(strategy[`packaging_${kind}_content_${name}`]);
                if (Number.isFinite(value)) this.layout[kind][name] = value;
            });
        });
        this.assets.background = strategy.packaging_background_path || null;
        this.assets.music = strategy.packaging_music_path || null;
        this.assets.intro_video = strategy.packaging_intro_video_path || null;
        this.assets.outro_video = strategy.packaging_outro_video_path || null;
    }

    bind() {
        this.element('packaging-save-btn').addEventListener('click', () => this.save());
        this.element('packaging-preview-refresh').addEventListener('click', () => this.refreshPreview());
        this.element('packaging-layout-reset').addEventListener('click', () => {
            this.layout = { intro: { x: 9.5, y: 30, width: 70 }, outro: { x: 9.5, y: 34, width: 70 } };
            this.syncLayoutBoxes();
            this.markDirty();
            this.refreshPreview();
        });
        document.querySelectorAll('.packaging-manager-page input, .packaging-manager-page select').forEach(control => {
            if (control.type !== 'file') control.addEventListener('change', () => this.markDirty());
        });
        this.bindAsset('background', 'packaging-background-button', 'packaging-background-input');
        this.bindAsset('music', 'packaging-music-button', 'packaging-music-input');
        this.bindAsset('intro_video', 'packaging-intro-video-button', 'packaging-intro-video-input');
        this.bindAsset('outro_video', 'packaging-outro-video-button', 'packaging-outro-video-input');
        this.bindRemove('background', 'packaging-background-remove');
        this.bindRemove('music', 'packaging-music-remove');
        this.bindRemove('intro_video', 'packaging-intro-video-remove');
        this.bindRemove('outro_video', 'packaging-outro-video-remove');
        this.element('packaging-music-library').addEventListener('change', event => {
            this.assets.music = event.target.value || null;
            this.element('packaging-music-preview').src = event.target.selectedOptions[0]?.dataset.url || '';
            this.syncAssets();
            this.markDirty();
        });
        this.bindLayoutEditor();
    }

    markDirty() { this.element('packaging-save-status').textContent = '有未保存修改'; }

    collect() {
        const options = {};
        Object.entries(this.fields).forEach(([key, id]) => {
            const control = this.element(id);
            options[key] = control.type === 'number' ? Number(control.value) : control.value.trim();
        });
        Object.entries(this.checkboxes).forEach(([key, id]) => { options[key] = this.element(id).checked; });
        options.packaging_background_path = this.assets.background;
        options.packaging_music_path = this.assets.music;
        options.packaging_intro_video_path = this.assets.intro_video;
        options.packaging_outro_video_path = this.assets.outro_video;
        ['intro', 'outro'].forEach(kind => {
            options[`packaging_${kind}_content_x`] = this.layout[kind].x;
            options[`packaging_${kind}_content_y`] = this.layout[kind].y;
            options[`packaging_${kind}_content_width`] = this.layout[kind].width;
        });
        return options;
    }

    save() {
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
                this.syncAssets();
                if (kind === 'music') await this.loadMusicLibrary();
                this.markDirty();
                if (kind === 'background') this.refreshPreview();
            } catch (error) { status.textContent = error.message; }
        });
    }

    bindRemove(kind, buttonId) {
        this.element(buttonId).addEventListener('click', () => {
            this.assets[kind] = null;
            this.syncAssets();
            this.markDirty();
            if (kind === 'background') this.refreshPreview();
        });
    }

    assetStatus(kind) {
        return this.element(kind === 'background' ? 'packaging-background-status' : kind === 'music' ? 'packaging-music-status' : kind === 'intro_video' ? 'packaging-intro-video-status' : 'packaging-outro-video-status');
    }

    syncAssets() {
        const labels = {
            background: ['packaging-background-remove', '已使用自定义背景图', '片头片尾共用'],
            music: ['packaging-music-remove', '已使用自定义背景音乐', '自动裁剪到包装时长'],
            intro_video: ['packaging-intro-video-remove', '已使用片头视频', '支持 MP4/MOV'],
            outro_video: ['packaging-outro-video-remove', '已使用片尾视频', '可使用不同素材']
        };
        Object.entries(labels).forEach(([kind, [buttonId, active, empty]]) => {
            this.element(buttonId).hidden = !this.assets[kind];
            this.assetStatus(kind).textContent = this.assets[kind] ? active : empty;
        });
        this.element('packaging-music-library').value = this.assets.music || '';
    }

    async loadMusicLibrary() {
        try {
            const response = await fetch('/api/course-packaging-assets?kind=music');
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || '音乐素材库加载失败');
            const select = this.element('packaging-music-library');
            select.replaceChildren(new Option('使用内置风格音乐', ''));
            result.assets.forEach(asset => {
                const option = new Option(asset.name, asset.path);
                option.dataset.url = asset.url;
                select.add(option);
            });
            select.value = this.assets.music || '';
            this.element('packaging-music-preview').src = select.selectedOptions[0]?.dataset.url || '';
        } catch (error) { console.warn('加载音乐素材库失败:', error); }
    }

    previewUrl(kind) {
        const values = this.collect();
        const params = new URLSearchParams({
            kind,
            ...Object.fromEntries(Object.entries(values).filter(([, value]) => value !== null)),
            course_title: '人工智能课程示例',
            segment_title: kind === 'intro' ? '第一讲 课程导入' : '',
            t: String(Date.now())
        });
        return `/api/course-packaging-preview-image?${params.toString()}`;
    }

    refreshPreview() {
        const status = this.element('packaging-preview-status');
        const images = [this.element('packaging-intro-preview'), this.element('packaging-outro-preview')];
        status.textContent = '正在生成预览...';
        let loaded = 0;
        images.forEach((image, index) => {
            image.onload = () => { loaded += 1; if (loaded === 2) status.textContent = '预览已更新'; };
            image.onerror = () => { status.textContent = '预览生成失败'; };
            image.src = this.previewUrl(index === 0 ? 'intro' : 'outro');
        });
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
