class AdminDataPages {
    constructor() {
        this.assetTableBody = document.getElementById('asset-table-body');
        this.operationLogBody = document.getElementById('operation-log-body');
        this.init();
    }

    init() {
        if (this.assetTableBody) this.loadAssets();
        if (this.operationLogBody) this.loadOperationLogs();
    }

    async loadAssets() {
        try {
            const response = await fetch('/api/tasks');
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '读取课程数据失败');
            this.renderAssetTable(data.tasks || []);
        } catch (error) {
            this.assetTableBody.innerHTML = `<tr><td colspan="6" class="table-empty">${this.escape(error.message)}</td></tr>`;
        }
    }

    renderAssetTable(tasks) {
        if (!tasks.length) {
            this.assetTableBody.innerHTML = '<tr><td colspan="6" class="table-empty">暂无课程数据</td></tr>';
            return;
        }
        this.assetTableBody.innerHTML = tasks.map(task => {
            const actions = [];
            if (task.status === 'awaiting_confirmation') {
                actions.push(`<a class="table-action" href="/#course-preview-module">预览审核</a>`);
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
                    <td>${this.formatTime(task.updated_at || task.completed_at || task.started_at || task.created_at)}</td>
                    <td class="table-actions">${actions.join('') || '-'}</td>
                </tr>
            `;
        }).join('');
        this.assetTableBody.querySelectorAll('[data-delete-task]').forEach(button => {
            button.addEventListener('click', () => this.deleteTask(button.dataset.deleteTask, button));
        });
    }

    async deleteTask(taskId, button) {
        if (!window.confirm('确定物理删除该课程产物吗？该操作无法恢复。')) return;
        button.disabled = true;
        try {
            const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '删除失败');
            await this.loadAssets();
        } catch (error) {
            button.disabled = false;
            window.alert(error.message);
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
