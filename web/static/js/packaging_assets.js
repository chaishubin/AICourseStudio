class PackagingAssetManager {
    constructor() {
        this.assets = [];
        this.grid = document.getElementById('packaging-assets-grid');
        this.count = document.getElementById('packaging-assets-count');
        this.search = document.getElementById('packaging-asset-search');
        this.type = document.getElementById('packaging-asset-type');
        this.side = document.getElementById('packaging-asset-side');
        this.addForm = document.getElementById('packaging-asset-add-form');
        this.addKind = document.getElementById('packaging-asset-add-kind');
        this.addFile = document.getElementById('packaging-asset-add-file');
        this.addFileName = document.getElementById('packaging-asset-add-file-name');
        this.addSubmit = document.getElementById('packaging-asset-add-submit');
        this.addStatus = document.getElementById('packaging-asset-add-status');
        this.bind();
        this.load();
    }

    bind() {
        document.getElementById('packaging-asset-add-file-button').addEventListener('click', () => this.addFile.click());
        this.addKind.addEventListener('change', () => this.syncUploadType(true));
        this.addFile.addEventListener('change', () => this.syncSelectedFiles());
        this.addForm.addEventListener('submit', event => this.upload(event));
        [this.search, this.type, this.side].forEach(control => control.addEventListener(control === this.search ? 'input' : 'change', () => this.render()));
        document.getElementById('packaging-asset-reset').addEventListener('click', () => {
            this.search.value = '';
            this.type.value = '';
            this.side.value = '';
            this.render();
        });
        this.syncUploadType(false);
    }

    syncSelectedFiles() {
        const files = Array.from(this.addFile.files || []);
        if (!files.length) {
            this.addFileName.textContent = '尚未选择文件';
            return;
        }
        const names = files.slice(0, 3).map(file => file.name).join('、');
        this.addFileName.textContent = files.length > 3 ? `已选 ${files.length} 个：${names} 等` : `已选 ${files.length} 个：${names}`;
        this.addFileName.title = files.map(file => file.name).join('\n');
    }

    syncUploadType(clearFile) {
        const media = this.addKind.value.split('_').pop();
        this.addFile.accept = media === 'background' ? '.png,.jpg,.jpeg,.webp' : media === 'music' ? '.mp3,.wav,.m4a,.aac' : '.mp4,.mov,.m4v,.webm';
        if (clearFile) {
            this.addFile.value = '';
            this.addFileName.textContent = '尚未选择文件';
            this.addStatus.textContent = '';
        }
    }

    async upload(event) {
        event.preventDefault();
        const files = Array.from(this.addFile.files || []);
        if (!files.length) {
            this.addStatus.textContent = '请先选择要上传的文件';
            return;
        }
        this.addSubmit.disabled = true;
        const failures = [];
        let succeeded = 0;
        for (let index = 0; index < files.length; index += 1) {
            const file = files[index];
            this.addStatus.textContent = `正在上传 ${index + 1} / ${files.length}：${file.name}`;
            const formData = new FormData();
            formData.append('kind', this.addKind.value);
            formData.append('asset', file);
            try {
                const response = await fetch('/api/course-packaging-asset-upload', {method: 'POST', body: formData});
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || '上传失败');
                succeeded += 1;
            } catch (error) {
                failures.push(`${file.name}：${error.message}`);
            }
        }
        try {
            this.addFile.value = '';
            this.addFileName.textContent = '尚未选择文件';
            this.addFileName.title = '';
            this.addStatus.textContent = failures.length ? `成功 ${succeeded} 个，失败 ${failures.length} 个：${failures.join('；')}` : `已成功添加 ${succeeded} 个素材`;
            await this.load();
        } finally {
            this.addSubmit.disabled = false;
        }
    }

    async load() {
        try {
            const response = await fetch('/api/course-packaging-assets?kind=all');
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || '素材库加载失败');
            this.assets = result.assets || [];
            this.render();
        } catch (error) {
            this.grid.innerHTML = `<p class="table-empty">${this.escape(error.message)}</p>`;
            this.count.textContent = '加载失败';
        }
    }

    filtered() {
        const keyword = this.search.value.trim().toLowerCase();
        return this.assets.filter(asset => {
            const side = asset.kind.startsWith('intro_') ? 'intro' : asset.kind.startsWith('mid_') ? 'mid' : asset.kind.startsWith('outro_') ? 'outro' : 'shared';
            return (!keyword || asset.name.toLowerCase().includes(keyword)) && (!this.type.value || asset.media_type === this.type.value) && (!this.side.value || side === this.side.value);
        });
    }

    render() {
        const assets = this.filtered();
        this.count.textContent = `显示 ${assets.length} / ${this.assets.length} 项`;
        if (!assets.length) {
            this.grid.innerHTML = '<p class="table-empty">没有符合条件的包装素材</p>';
            return;
        }
        this.grid.innerHTML = assets.map(asset => `
            <article class="packaging-asset-card">
                <div class="packaging-asset-preview">${this.preview(asset)}</div>
                <div class="packaging-asset-card-body">
                    <span class="status-pill">${this.escape(this.kindLabel(asset.kind))}</span>
                    <strong title="${this.escapeAttr(asset.name)}">${this.escape(asset.name)}</strong>
                    <small>${this.formatSize(asset.size)} · ${this.formatTime(asset.updated_at)}</small>
                    <div class="packaging-asset-card-actions">
                        <button type="button" class="table-action" data-rename="${this.escapeAttr(asset.filename)}">重命名</button>
                        <button type="button" class="table-action danger" data-delete="${this.escapeAttr(asset.filename)}">删除</button>
                    </div>
                </div>
            </article>`).join('');
        this.grid.querySelectorAll('[data-rename]').forEach(button => button.addEventListener('click', () => this.rename(button.dataset.rename)));
        this.grid.querySelectorAll('[data-delete]').forEach(button => button.addEventListener('click', () => this.remove(button.dataset.delete)));
    }

    preview(asset) {
        const url = this.escapeAttr(asset.url);
        if (asset.media_type === 'image') return `<img src="${url}" alt="${this.escapeAttr(asset.name)}" loading="lazy">`;
        if (asset.media_type === 'audio') return `<audio src="${url}" controls preload="none"></audio>`;
        return `<video src="${url}" controls preload="metadata"></video>`;
    }

    async rename(filename) {
        const asset = this.assets.find(item => item.filename === filename);
        if (!asset) return;
        const name = window.prompt('输入新的素材名称', asset.name);
        if (name === null || !name.trim() || name.trim() === asset.name) return;
        const response = await fetch(`/api/course-packaging-asset/${encodeURIComponent(filename)}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: name.trim()})});
        const result = await response.json();
        if (!response.ok) return window.alert(result.error || '重命名失败');
        await this.load();
    }

    async remove(filename) {
        const asset = this.assets.find(item => item.filename === filename);
        if (!asset || !window.confirm(`确定永久删除素材“${asset.name}”吗？已保存方案中的该素材也将不可用。`)) return;
        const response = await fetch(`/api/course-packaging-asset/${encodeURIComponent(filename)}`, {method: 'DELETE'});
        const result = await response.json();
        if (!response.ok) return window.alert(result.error || '删除失败');
        this.assets = this.assets.filter(item => item.filename !== filename);
        this.render();
    }

    kindLabel(kind) {
        return {intro_background: '片头背景', mid_background: '片中背景', outro_background: '片尾背景', intro_video: '片头视频', mid_video: '片中视频', outro_video: '片尾视频', intro_music: '片头音乐', mid_music: '片中音乐', outro_music: '片尾音乐', background: '通用背景', music: '通用音乐'}[kind] || '包装素材';
    }

    formatSize(bytes) { return bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`; }
    formatTime(value) { return value ? new Date(value * 1000).toLocaleString('zh-CN', {month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'}) : '-'; }
    escape(value) { const div = document.createElement('div'); div.textContent = String(value ?? ''); return div.innerHTML; }
    escapeAttr(value) { return this.escape(value).replace(/"/g, '&quot;'); }
}

document.addEventListener('DOMContentLoaded', () => new PackagingAssetManager());
