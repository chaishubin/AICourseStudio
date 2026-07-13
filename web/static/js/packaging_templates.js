class PackagingTemplateManager {
    constructor() {
        this.storageKey = 'vidppt.currentStrategy.v1';
        this.templates = [];
        this.elements = {
            grid: document.getElementById('packaging-templates-grid'),
            count: document.getElementById('packaging-templates-count'),
            search: document.getElementById('packaging-template-search'),
            type: document.getElementById('packaging-template-type'),
            status: document.getElementById('packaging-template-status'),
            panel: document.getElementById('packaging-template-create-panel'),
            form: document.getElementById('packaging-template-create-form'),
            createStatus: document.getElementById('packaging-template-create-status')
        };
        this.bind();
        this.load();
    }

    bind() {
        document.getElementById('packaging-template-create-toggle').addEventListener('click', () => { this.elements.panel.hidden = false; document.getElementById('packaging-template-name').focus(); });
        document.getElementById('packaging-template-create-cancel').addEventListener('click', () => { this.elements.panel.hidden = true; });
        this.elements.form.addEventListener('submit', event => { event.preventDefault(); this.create(); });
        [this.elements.search, this.elements.type, this.elements.status].forEach(control => control.addEventListener('input', () => this.render()));
        document.getElementById('packaging-template-reset').addEventListener('click', () => {
            this.elements.search.value = '';
            this.elements.type.value = '';
            this.elements.status.value = '';
            this.render();
        });
        this.elements.grid.addEventListener('click', event => {
            const action = event.target.closest('[data-template-action]');
            if (action) this.handleAction(action.dataset.templateAction, action.dataset.templateId);
        });
    }

    async load() {
        try {
            const response = await fetch('/api/course-packaging-templates?include_disabled=1');
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || '模板加载失败');
            this.templates = result.templates;
            this.render();
        } catch (error) {
            this.elements.grid.innerHTML = `<div class="management-empty">${this.escape(error.message)}</div>`;
        }
    }

    currentConfig() {
        try {
            const strategy = JSON.parse(localStorage.getItem(this.storageKey) || '{}') || {};
            return Object.fromEntries(Object.entries(strategy).filter(([key]) => key.startsWith('packaging_') || ['enable_intro', 'enable_mid', 'enable_outro'].includes(key)));
        } catch (_) { return {}; }
    }

    async create() {
        const name = document.getElementById('packaging-template-name').value.trim();
        const base = document.getElementById('packaging-template-base').value;
        const description = document.getElementById('packaging-template-description').value.trim();
        this.elements.createStatus.textContent = '正在创建…';
        try {
            await this.request('/api/course-packaging-templates', { method: 'POST', body: JSON.stringify({ name, description, base_template: base, config: { ...this.currentConfig(), packaging_template: base } }) });
            this.elements.form.reset();
            this.elements.panel.hidden = true;
            this.elements.createStatus.textContent = '模板已创建';
            await this.load();
        } catch (error) { this.elements.createStatus.textContent = error.message; }
    }

    filtered() {
        const query = this.elements.search.value.trim().toLowerCase();
        return this.templates.filter(template => {
            if (query && !`${template.name} ${template.description}`.toLowerCase().includes(query)) return false;
            if (this.elements.type.value === 'builtin' && !template.builtin) return false;
            if (this.elements.type.value === 'custom' && template.builtin) return false;
            if (this.elements.status.value === 'enabled' && !template.enabled) return false;
            if (this.elements.status.value === 'disabled' && template.enabled) return false;
            return true;
        });
    }

    render() {
        const templates = this.filtered();
        this.elements.count.textContent = `${templates.length} / ${this.templates.length} 个模板`;
        if (!templates.length) {
            this.elements.grid.innerHTML = '<div class="management-empty">没有符合条件的包装模板</div>';
            return;
        }
        this.elements.grid.innerHTML = templates.map(template => {
            const params = new URLSearchParams({ kind: 'intro', packaging_template: template.id, course_title: '人工智能课程示例', packaging_intro_title: '课程品牌片头' });
            const badge = template.builtin ? '系统模板' : '自定义模板';
            return `<article class="packaging-template-card${template.enabled ? '' : ' is-disabled'}">
                <div class="packaging-template-preview"><img src="/api/course-packaging-preview-image?${params}" alt="${this.escape(template.name)}预览" loading="lazy"><span>${this.escape(badge)}</span>${template.is_default ? '<b>默认</b>' : ''}</div>
                <div class="packaging-template-card-body"><div><h4>${this.escape(template.name)}</h4><p>${this.escape(template.description || '暂无模板说明')}</p></div>
                <dl><div><dt>基础风格</dt><dd>${this.escape(this.baseName(template.base_template))}</dd></div><div><dt>状态</dt><dd>${template.enabled ? '已启用' : '已停用'}</dd></div></dl>
                <div class="packaging-template-actions">
                    ${template.is_default ? '' : `<button class="btn-preview" data-template-action="default" data-template-id="${template.id}">设为默认</button>`}
                    <button class="btn-preview" data-template-action="copy" data-template-id="${template.id}">复制</button>
                    ${template.builtin
                        ? `<button class="btn-preview" data-template-action="copy-edit" data-template-id="${template.id}">复制并编辑</button>`
                        : `<a class="btn-preview" href="/course-packaging?edit_template=${encodeURIComponent(template.id)}">编辑详细内容</a>`}
                    <button class="btn-preview" data-template-action="rename" data-template-id="${template.id}">编辑基本信息</button>
                    <button class="btn-preview" data-template-action="toggle" data-template-id="${template.id}">${template.enabled ? '停用' : '启用'}</button>
                    ${template.builtin ? '' : `<button class="btn-preview packaging-template-delete" data-template-action="delete" data-template-id="${template.id}">删除</button>`}
                </div></div></article>`;
        }).join('');
    }

    async handleAction(action, id) {
        const template = this.templates.find(item => item.id === id);
        if (!template) return;
        try {
            if (action === 'copy') {
                await this.request('/api/course-packaging-templates', { method: 'POST', body: JSON.stringify({ source_id: id }) });
            } else if (action === 'copy-edit') {
                const result = await this.request('/api/course-packaging-templates', { method: 'POST', body: JSON.stringify({ source_id: id }) });
                window.location.href = `/course-packaging?edit_template=${encodeURIComponent(result.template.id)}`;
                return;
            } else if (action === 'default') {
                await this.update(id, { is_default: true });
            } else if (action === 'toggle') {
                await this.update(id, { enabled: !template.enabled });
            } else if (action === 'rename') {
                const name = window.prompt('模板名称', template.name);
                if (name === null) return;
                const description = window.prompt('模板说明', template.description || '');
                if (description === null) return;
                await this.update(id, { name, description });
            } else if (action === 'delete') {
                if (!window.confirm(`确认删除自定义模板“${template.name}”？`)) return;
                await this.request(`/api/course-packaging-templates/${encodeURIComponent(id)}`, { method: 'DELETE' });
            }
            await this.load();
        } catch (error) { window.alert(error.message); }
    }

    update(id, payload) { return this.request(`/api/course-packaging-templates/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(payload) }); }

    async request(url, options) {
        const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || '操作失败');
        return result;
    }

    baseName(id) { return ({ academic: '高校课程', university: '高校片头', credits: '片尾鸣谢', modern: '现代培训', minimal: '简洁微课' })[id] || id; }
    escape(value) { const node = document.createElement('span'); node.textContent = String(value ?? ''); return node.innerHTML; }
}

document.addEventListener('DOMContentLoaded', () => new PackagingTemplateManager());
