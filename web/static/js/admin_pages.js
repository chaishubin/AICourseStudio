class AdminDataPages {
    constructor() {
        this.assetTableBody = document.getElementById('asset-table-body');
        this.assetSearchInput = document.getElementById('asset-search-input');
        this.assetStatusFilter = document.getElementById('asset-status-filter');
        this.assetFilterReset = document.getElementById('asset-filter-reset');
        this.assetPagination = document.getElementById('asset-pagination');
        this.operationLogBody = document.getElementById('operation-log-body');
        this.accountTableBody = document.getElementById('account-table-body');
        this.accountForm = document.getElementById('account-form');
        this.accountEditUsername = document.getElementById('account-edit-username');
        this.accountUsername = document.getElementById('account-username');
        this.accountDisplayName = document.getElementById('account-display-name');
        this.accountRole = document.getElementById('account-role');
        this.accountPassword = document.getElementById('account-password');
        this.accountActive = document.getElementById('account-active');
        this.accountSubmit = document.getElementById('account-submit');
        this.accountReset = document.getElementById('account-reset');
        this.accounts = [];
        this.assetPage = 1;
        this.assetPageSize = 10;
        this.assetPaginationState = { page: 1, page_size: 10, total: 0, total_pages: 1 };
        this.init();
    }

    init() {
        if (this.assetTableBody) {
            this.bindAssetFilters();
            this.loadAssets();
        }
        if (this.operationLogBody) this.loadOperationLogs();
        if (this.accountTableBody) {
            this.bindAccountForm();
            this.loadAccounts();
        }
    }

    bindAssetFilters() {
        this.assetSearchInput?.addEventListener('input', () => this.loadAssets(1));
        this.assetStatusFilter?.addEventListener('change', () => this.loadAssets(1));
        this.assetFilterReset?.addEventListener('click', () => {
            if (this.assetSearchInput) this.assetSearchInput.value = '';
            if (this.assetStatusFilter) this.assetStatusFilter.value = '';
            this.loadAssets(1);
        });
    }

    async loadAssets(page = this.assetPage) {
        this.assetPage = page;
        try {
            const params = new URLSearchParams({
                page: String(this.assetPage),
                page_size: String(this.assetPageSize)
            });
            const keyword = (this.assetSearchInput?.value || '').trim();
            const status = this.assetStatusFilter?.value || '';
            if (keyword) params.set('q', keyword);
            if (status) params.set('status', status);
            const response = await fetch(`/api/tasks?${params.toString()}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '读取课程数据失败');
            this.assetPaginationState = data.pagination || {
                page: this.assetPage,
                page_size: this.assetPageSize,
                total: (data.tasks || []).length,
                total_pages: 1
            };
            this.assetPage = this.assetPaginationState.page || 1;
            this.renderAssetTable(data.tasks || [], this.assetPaginationState.total || 0);
            this.renderAssetPagination();
        } catch (error) {
            this.assetTableBody.innerHTML = `<tr><td colspan="7" class="table-empty">${this.escape(error.message)}</td></tr>`;
            if (this.assetPagination) this.assetPagination.hidden = true;
        }
    }

    renderAssetTable(tasks, totalCount = tasks.length) {
        if (!tasks.length) {
            const message = totalCount ? '没有符合筛选条件的课程数据' : '暂无课程数据';
            this.assetTableBody.innerHTML = `<tr><td colspan="7" class="table-empty">${message}</td></tr>`;
            return;
        }
        this.assetTableBody.innerHTML = tasks.map(task => {
            const actions = [];
            const reviewUrl = this.reviewUrl(task.task_id);
            if (task.source_file_exists) {
                actions.push(`
                    <span class="table-action-group" aria-label="上传文件操作">
                        <span class="table-action-label">源文件</span>
                        ${this.sourcePreviewAction(task, reviewUrl)}
                        <a class="table-action" href="${this.sourceFileUrl(task.task_id, 'download')}" title="下载上传文件">下载</a>
                    </span>
                `);
            }
            if (task.status === 'completed' && task.video_path) {
                const videoUrl = `/api/video?path=${encodeURIComponent(task.video_path)}`;
                const url = `/api/download?task_id=${encodeURIComponent(task.task_id)}&path=${encodeURIComponent(task.video_path)}`;
                actions.push(`
                    <span class="table-action-group" aria-label="生成视频操作">
                        <span class="table-action-label">视频</span>
                        <a class="table-action" href="${videoUrl}" target="_blank" rel="noopener" title="预览生成视频">预览</a>
                        <a class="table-action" href="${url}" title="下载生成视频">下载</a>
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
            if (['completed', 'error', 'interrupted', 'awaiting_confirmation'].includes(task.status)) {
                actions.push(`<button type="button" class="table-action danger" data-delete-task="${this.escapeAttr(task.task_id)}">删除</button>`);
            }
            return `
                <tr>
                    <td><strong>${this.escape(task.original_name || '未知文件')}</strong><small>${this.escape(task.task_id || '')}</small></td>
                    <td>${this.escape(task.owner_username || task.created_by || '-')}</td>
                    <td><span class="status-pill status-${this.escapeAttr(task.status || 'unknown')}">${this.escape(this.statusText(task))}</span></td>
                    <td>${Math.round(task.percentage || 0)}%</td>
                    <td>${this.formatTime(task.created_at)}</td>
                    <td>${this.formatTime(task.updated_at || task.completed_at || task.started_at || task.created_at)}</td>
                    <td class="table-actions">${actions.join('') || '-'}</td>
                </tr>
            `;
        }).join('');
        this.assetTableBody.querySelectorAll('[data-delete-task]').forEach(button => {
            button.addEventListener('click', () => this.deleteTask(button.dataset.deleteTask, button));
        });
    }

    renderAssetPagination() {
        if (!this.assetPagination) return;
        const { page, page_size: pageSize, total, total_pages: totalPages } = this.assetPaginationState;
        if (!total || totalPages <= 1) {
            this.assetPagination.hidden = !total;
            this.assetPagination.innerHTML = total
                ? `<span>共 ${total} 条</span>`
                : '';
            return;
        }
        const start = (page - 1) * pageSize + 1;
        const end = Math.min(page * pageSize, total);
        this.assetPagination.hidden = false;
        this.assetPagination.innerHTML = `
            <span>第 ${start}-${end} 条，共 ${total} 条</span>
            <div class="pagination-actions">
                <button type="button" class="table-action" data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>上一页</button>
                <span>${page} / ${totalPages}</span>
                <button type="button" class="table-action" data-page="${page + 1}" ${page >= totalPages ? 'disabled' : ''}>下一页</button>
            </div>
        `;
        this.assetPagination.querySelectorAll('[data-page]').forEach(button => {
            button.addEventListener('click', () => {
                const nextPage = Number(button.dataset.page);
                if (!Number.isNaN(nextPage)) this.loadAssets(nextPage);
            });
        });
    }

    reviewUrl(taskId) {
        if (!taskId) return '';
        return `/?preview_task=${encodeURIComponent(taskId)}#course-preview-module`;
    }

    sourceFileUrl(taskId, mode = 'download') {
        return `/api/tasks/${encodeURIComponent(taskId)}/source-file?mode=${encodeURIComponent(mode)}`;
    }

    sourcePreviewAction(task, reviewUrl) {
        const fileName = task.original_name || '';
        if (/\.pdf$/i.test(fileName)) {
            return `<a class="table-action" href="${this.sourceFileUrl(task.task_id, 'preview')}" target="_blank" rel="noopener" title="预览上传文件">预览</a>`;
        }
        if (task.preview_path && reviewUrl) {
            return `<a class="table-action" href="${reviewUrl}" title="预览上传文件">预览</a>`;
        }
        return '<button type="button" class="table-action" disabled title="该格式暂不支持在线预览，请下载查看">预览</button>';
    }

    async deleteTask(taskId, button) {
        const confirmed = await window.VidPPTUI.confirm('确定物理删除该课程产物吗？该操作无法恢复。', {
            title: '删除课程产物',
            confirmText: '永久删除',
            danger: true
        });
        if (!confirmed) return;
        button.disabled = true;
        try {
            const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '删除失败');
            await this.loadAssets(this.assetPage);
            window.VidPPTUI.toast(data.message || '课程产物已删除', { type: 'success' });
        } catch (error) {
            button.disabled = false;
            await window.VidPPTUI.alert(error.message, { type: 'error' });
        }
    }

    async loadOperationLogs() {
        try {
            const response = await fetch('/api/operation-logs?limit=120');
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '读取操作日志失败');
            this.renderOperationLogs(data.logs || []);
        } catch (error) {
            this.operationLogBody.innerHTML = `<tr><td colspan="5" class="table-empty">${this.escape(error.message)}</td></tr>`;
        }
    }

    renderOperationLogs(logs) {
        if (!logs.length) {
            this.operationLogBody.innerHTML = '<tr><td colspan="5" class="table-empty">暂无操作日志</td></tr>';
            return;
        }
        this.operationLogBody.innerHTML = logs.map(log => `
            <tr>
                <td>${this.formatTime(log.created_at)}</td>
                <td>${this.escape(log.actor || '-')}</td>
                <td>${this.escape(this.operationText(log.action))}</td>
                <td><strong>${this.escape(log.target_name || log.task_id || '-')}</strong><small>${this.escape(log.message || '')}</small></td>
                <td>${log.success ? '成功' : '失败'}</td>
            </tr>
        `).join('');
    }

    bindAccountForm() {
        this.accountForm?.addEventListener('submit', event => {
            event.preventDefault();
            this.saveAccount();
        });
        this.accountReset?.addEventListener('click', () => this.resetAccountForm());
    }

    async loadAccounts() {
        try {
            const response = await fetch('/api/accounts');
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '读取账号失败');
            this.accounts = data.accounts || [];
            this.renderAccountTable();
        } catch (error) {
            this.accountTableBody.innerHTML = `<tr><td colspan="6" class="table-empty">${this.escape(error.message)}</td></tr>`;
        }
    }

    renderAccountTable() {
        if (!this.accounts.length) {
            this.accountTableBody.innerHTML = '<tr><td colspan="6" class="table-empty">暂无账号</td></tr>';
            return;
        }
        this.accountTableBody.innerHTML = this.accounts.map(account => {
            const isCurrent = account.username === window.currentUsername;
            return `
                <tr>
                    <td><strong>${this.escape(account.username)}</strong>${isCurrent ? '<small>当前账号</small>' : ''}</td>
                    <td>${this.escape(account.display_name || account.username)}</td>
                    <td>${account.role === 'super_admin' ? '超级管理员' : '普通账号'}</td>
                    <td><span class="status-pill ${account.active ? 'status-completed' : 'status-interrupted'}">${account.active ? '启用' : '停用'}</span></td>
                    <td>${this.formatTime(account.updated_at || account.created_at)}</td>
                    <td class="table-actions">
                        <button type="button" class="table-action" data-edit-account="${this.escapeAttr(account.username)}">编辑</button>
                        <button type="button" class="table-action danger" data-disable-account="${this.escapeAttr(account.username)}" ${isCurrent || !account.active ? 'disabled' : ''}>停用</button>
                    </td>
                </tr>
            `;
        }).join('');
        this.accountTableBody.querySelectorAll('[data-edit-account]').forEach(button => {
            button.addEventListener('click', () => this.editAccount(button.dataset.editAccount));
        });
        this.accountTableBody.querySelectorAll('[data-disable-account]').forEach(button => {
            button.addEventListener('click', () => this.disableAccount(button.dataset.disableAccount, button));
        });
    }

    editAccount(username) {
        const account = this.accounts.find(item => item.username === username);
        if (!account) return;
        this.accountEditUsername.value = account.username;
        this.accountUsername.value = account.username;
        this.accountUsername.disabled = true;
        this.accountDisplayName.value = account.display_name || account.username;
        this.accountRole.value = account.role || 'user';
        this.accountPassword.value = '';
        this.accountActive.checked = Boolean(account.active);
        this.accountSubmit.textContent = '保存账号';
        this.accountPassword.placeholder = '留空则不修改密码';
        this.accountForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    resetAccountForm() {
        this.accountForm.reset();
        this.accountEditUsername.value = '';
        this.accountUsername.disabled = false;
        this.accountActive.checked = true;
        this.accountSubmit.textContent = '创建账号';
        this.accountPassword.placeholder = '新建必填，编辑留空则不修改';
    }

    accountPayload() {
        return {
            username: this.accountUsername.value.trim(),
            display_name: this.accountDisplayName.value.trim(),
            role: this.accountRole.value,
            password: this.accountPassword.value,
            active: this.accountActive.checked
        };
    }

    async saveAccount() {
        const editing = this.accountEditUsername.value;
        const payload = this.accountPayload();
        if (!editing && !payload.password) {
            await window.VidPPTUI.alert('新建账号必须设置密码', { type: 'error' });
            return;
        }
        this.accountSubmit.disabled = true;
        try {
            const response = await fetch(
                editing ? `/api/accounts/${encodeURIComponent(editing)}` : '/api/accounts',
                {
                    method: editing ? 'PATCH' : 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                }
            );
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '保存账号失败');
            this.resetAccountForm();
            await this.loadAccounts();
            window.VidPPTUI.toast(editing ? '账号已更新' : '账号已创建', { type: 'success' });
        } catch (error) {
            await window.VidPPTUI.alert(error.message, { type: 'error' });
        } finally {
            this.accountSubmit.disabled = false;
        }
    }

    async disableAccount(username, button) {
        const confirmed = await window.VidPPTUI.confirm(`确定停用账号“${username}”吗？`, {
            title: '停用账号',
            confirmText: '停用',
            danger: true
        });
        if (!confirmed) return;
        button.disabled = true;
        try {
            const response = await fetch(`/api/accounts/${encodeURIComponent(username)}`, {
                method: 'DELETE'
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '停用账号失败');
            await this.loadAccounts();
            window.VidPPTUI.toast(data.message || '账号已停用', { type: 'success' });
        } catch (error) {
            button.disabled = false;
            await window.VidPPTUI.alert(error.message, { type: 'error' });
        }
    }

    statusText(task) {
        const labels = {
            queued: '排队中',
            pending: '等待执行',
            processing: '生产中',
            awaiting_confirmation: '等待审核',
            completed: '已完成',
            error: '失败',
            interrupted: '已中断'
        };
        return labels[task.status] || task.message || task.status || '-';
    }

    operationText(action) {
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
            upload_reviewed_ppt: '上传审核 PPT',
            create_account: '创建账号',
            update_account: '更新账号',
            delete_account: '停用账号'
        };
        return labels[action] || action || '-';
    }

    formatTime(value) {
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

    escape(value) {
        const node = document.createElement('div');
        node.textContent = value == null ? '' : String(value);
        return node.innerHTML;
    }

    escapeAttr(value) {
        return this.escape(value).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
}

document.addEventListener('DOMContentLoaded', () => new AdminDataPages());
