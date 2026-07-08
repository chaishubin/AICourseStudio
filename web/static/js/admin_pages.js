class AdminDataPages {
    constructor() {
        this.assetTableBody = document.getElementById('asset-table-body');
        this.assetSearchInput = document.getElementById('asset-search-input');
        this.assetStatusFilter = document.getElementById('asset-status-filter');
        this.assetFilterReset = document.getElementById('asset-filter-reset');
        this.operationLogBody = document.getElementById('operation-log-body');
        this.assetTasks = [];
        this.init();
    }

    init() {
        if (this.assetTableBody) {
            this.bindAssetFilters();
            this.loadAssets();
        }
        if (this.operationLogBody) this.loadOperationLogs();
    }

    bindAssetFilters() {
        this.assetSearchInput?.addEventListener('input', () => this.applyAssetFilters());
        this.assetStatusFilter?.addEventListener('change', () => this.applyAssetFilters());
        this.assetFilterReset?.addEventListener('click', () => {
            if (this.assetSearchInput) this.assetSearchInput.value = '';
            if (this.assetStatusFilter) this.assetStatusFilter.value = '';
            this.applyAssetFilters();
        });
    }

    async loadAssets() {
        try {
            const response = await fetch('/api/tasks');
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '读取课程数据失败');
            this.assetTasks = data.tasks || [];
            this.applyAssetFilters();
        } catch (error) {
            this.assetTableBody.innerHTML = `<tr><td colspan="7" class="table-empty">${this.escape(error.message)}</td></tr>`;
        }
    }

    applyAssetFilters() {
        const keyword = (this.assetSearchInput?.value || '').trim().toLowerCase();
        const status = this.assetStatusFilter?.value || '';
        const filtered = this.assetTasks.filter(task => {
            const matchesStatus = !status || task.status === status;
            const haystack = [
                task.original_name,
                task.task_id,
                task.owner_username,
                task.created_by
            ].filter(Boolean).join(' ').toLowerCase();
            const matchesKeyword = !keyword || haystack.includes(keyword);
            return matchesStatus && matchesKeyword;
        });
        this.renderAssetTable(filtered, this.assetTasks.length);
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
            if (task.status === 'awaiting_confirmation' && reviewUrl) {
                actions.push(`<a class="table-action" href="${reviewUrl}">预览审核</a>`);
            } else if (task.status === 'completed' && task.video_path) {
                const videoUrl = `/api/video?path=${encodeURIComponent(task.video_path)}`;
                actions.push(`<a class="table-action" href="${videoUrl}" target="_blank" rel="noopener">预览</a>`);
            } else if (task.preview_path && reviewUrl) {
                actions.push(`<a class="table-action" href="${reviewUrl}">预览</a>`);
            }
            if (task.status === 'completed' && task.video_path) {
                const url = `/api/download?task_id=${encodeURIComponent(task.task_id)}&path=${encodeURIComponent(task.video_path)}`;
                actions.push(`<a class="table-action" href="${url}">下载</a>`);
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

    reviewUrl(taskId) {
        if (!taskId) return '';
        return `/?preview_task=${encodeURIComponent(taskId)}#course-preview-module`;
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
            await this.loadAssets();
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
            upload_reviewed_ppt: '上传审核 PPT'
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
