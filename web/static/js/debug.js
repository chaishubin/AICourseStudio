class DebugWorkbench {
    constructor() {
        this.taskBody = document.getElementById('debug-task-body');
        this.detailTitle = document.getElementById('debug-detail-title');
        this.detail = document.getElementById('debug-task-detail');
        this.environment = document.getElementById('debug-environment');
        this.logBody = document.getElementById('debug-log-body');
        this.logNote = document.getElementById('debug-log-note');
        this.logSearch = document.getElementById('debug-log-search');
        this.refreshBtn = document.getElementById('debug-refresh-btn');
        this.selectedTaskId = null;
        this.init();
    }

    init() {
        this.refreshBtn?.addEventListener('click', () => this.loadOverview());
        this.logSearch?.addEventListener('input', () => this.loadLogs());
        this.loadOverview();
        this.loadLogs();
    }

    async loadOverview() {
        if (this.refreshBtn) this.refreshBtn.disabled = true;
        try {
            const response = await fetch('/api/debug/overview');
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '读取调试概览失败');
            this.renderMetrics(data);
            this.renderTasks(data.tasks || []);
            this.renderEnvironment(data);
            if (this.selectedTaskId) this.loadTask(this.selectedTaskId);
        } catch (error) {
            this.taskBody.innerHTML = `<tr><td colspan="6" class="table-empty">${this.escape(error.message)}</td></tr>`;
        } finally {
            if (this.refreshBtn) this.refreshBtn.disabled = false;
        }
    }

    renderMetrics(data) {
        const counts = data.counts || {};
        this.setText('debug-total', (data.tasks || []).length);
        this.setText('debug-queued', counts.queued || 0);
        this.setText('debug-review', counts.awaiting_confirmation || 0);
        this.setText('debug-progress-queues', data.progress_queue_count || 0);
        this.setText('debug-queue-size', data.queue_size || 0);
    }

    renderTasks(tasks) {
        if (!tasks.length) {
            this.taskBody.innerHTML = '<tr><td colspan="6" class="table-empty">暂无任务</td></tr>';
            return;
        }
        this.taskBody.innerHTML = tasks.map(task => {
            const outputFlags = [
                task.preview_path ? 'preview' : '',
                task.course_json_path ? 'course' : '',
                task.presentation_path ? 'pptx' : '',
                task.subtitles_path ? 'srt' : '',
                task.video_path ? 'mp4' : '',
                (task.video_segments || []).length ? `segments:${task.video_segments.length}` : '',
            ].filter(Boolean);
            return `
                <tr class="${task.task_id === this.selectedTaskId ? 'debug-selected-row' : ''}" data-task-id="${this.escapeAttr(task.task_id)}">
                    <td><strong>${this.escape(task.original_name || task.course_name || '未知任务')}</strong><small>${this.escape(task.task_id || '')}</small></td>
                    <td><span class="status-pill status-${this.escapeAttr(task.status || 'unknown')}">${this.escape(this.statusText(task.status))}</span></td>
                    <td>${this.escape(task.stage || '-')}</td>
                    <td>${Math.round(task.percentage || 0)}%</td>
                    <td>${outputFlags.length ? outputFlags.map(flag => `<span class="debug-chip">${this.escape(flag)}</span>`).join('') : '-'}</td>
                    <td>${this.formatTime(task.updated_at || task.completed_at || task.started_at || task.created_at)}</td>
                </tr>
            `;
        }).join('');
        this.taskBody.querySelectorAll('[data-task-id]').forEach(row => {
            row.addEventListener('click', () => this.loadTask(row.dataset.taskId));
        });
    }

    renderEnvironment(data) {
        const paths = data.paths || {};
        const environment = data.environment || {};
        const envStatus = environment.env_status || [];
        const tools = environment.tools || [];
        const pathHtml = Object.entries(paths).map(([key, info]) => `
            <div class="debug-kv-item">
                <span>${this.escape(key)}</span>
                <strong title="${this.escapeAttr(info.path || '')}">${this.escape(info.exists ? info.path : `${info.path || '-'}（不存在）`)}</strong>
            </div>
        `).join('');
        const envHtml = envStatus.map(item => `
            <span class="debug-chip ${item.configured ? 'debug-chip-ok' : ''}">${this.escape(item.name)}: ${item.configured ? '已配置' : '未配置'}</span>
        `).join('');
        const toolHtml = tools.map(item => `
            <span class="debug-chip ${item.available ? 'debug-chip-ok' : ''}" title="${this.escapeAttr(item.path || '')}">${this.escape(item.name)}: ${item.available ? '可用' : '缺失'}</span>
        `).join('');
        this.environment.innerHTML = `
            <div class="debug-kv-group">
                <h4>关键路径</h4>
                ${pathHtml || '<div class="debug-empty">暂无路径信息</div>'}
            </div>
            <div class="debug-kv-group">
                <h4>环境变量状态</h4>
                <div class="debug-chip-list">${envHtml}</div>
            </div>
            <div class="debug-kv-group">
                <h4>系统工具</h4>
                <div class="debug-chip-list">${toolHtml}</div>
            </div>
            <div class="debug-kv-group">
                <h4>资源阈值</h4>
                <pre class="debug-json">${this.escape(JSON.stringify(environment.resource_limits || {}, null, 2))}</pre>
            </div>
        `;
    }

    async loadTask(taskId) {
        this.selectedTaskId = taskId;
        this.detailTitle.textContent = taskId;
        this.detail.innerHTML = '<div class="debug-empty">正在读取任务详情...</div>';
        this.taskBody?.querySelectorAll('[data-task-id]').forEach(row => {
            row.classList.toggle('debug-selected-row', row.dataset.taskId === taskId);
        });
        try {
            const response = await fetch(`/api/debug/tasks/${encodeURIComponent(taskId)}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '读取任务详情失败');
            this.renderTaskDetail(data);
        } catch (error) {
            this.detail.innerHTML = `<div class="debug-empty">${this.escape(error.message)}</div>`;
        }
    }

    renderTaskDetail(data) {
        const paths = data.paths || {};
        const files = data.output_files || [];
        const artifact = data.json_artifacts || {};
        this.detail.innerHTML = `
            <div class="debug-detail-section">
                <h4>关键路径</h4>
                <div class="debug-kv-list">
                    ${Object.entries(paths).map(([key, info]) => `
                        <div class="debug-kv-item">
                            <span>${this.escape(key)}</span>
                            <strong title="${this.escapeAttr(info.path || '')}">${this.escape(info.exists ? info.path : `${info.path || '-'}（不存在）`)}</strong>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div class="debug-detail-section">
                <h4>任务原始状态</h4>
                <pre class="debug-json">${this.escape(JSON.stringify(data.task || {}, null, 2))}</pre>
            </div>
            <div class="debug-detail-section">
                <h4>preview.json</h4>
                ${this.renderJsonArtifact(artifact.preview_json)}
            </div>
            <div class="debug-detail-section">
                <h4>course.json</h4>
                ${this.renderJsonArtifact(artifact.course_json)}
            </div>
            <div class="debug-detail-section">
                <h4>state.json 条目</h4>
                <pre class="debug-json">${this.escape(JSON.stringify(artifact.state_entry || null, null, 2))}</pre>
            </div>
            <div class="debug-detail-section">
                <h4>输出文件</h4>
                ${this.renderFiles(files)}
            </div>
        `;
    }

    renderJsonArtifact(artifact) {
        if (!artifact) return '<div class="debug-empty">无数据</div>';
        if (artifact.error) {
            return `<div class="debug-note">${this.escape(artifact.error)}</div><pre class="debug-json">${this.escape(JSON.stringify(artifact.info || {}, null, 2))}</pre>`;
        }
        if (!artifact.data) {
            return `<pre class="debug-json">${this.escape(JSON.stringify(artifact.info || {}, null, 2))}</pre>`;
        }
        return `<pre class="debug-json">${this.escape(JSON.stringify(artifact.data, null, 2))}</pre>`;
    }

    renderFiles(files) {
        if (!files.length) return '<div class="debug-empty">暂无输出文件</div>';
        return `
            <div class="management-table-wrap">
                <table class="management-table debug-file-table">
                    <thead><tr><th>文件</th><th>类型</th><th>大小</th><th>更新时间</th></tr></thead>
                    <tbody>
                        ${files.map(file => `
                            <tr>
                                <td><strong title="${this.escapeAttr(file.path)}">${this.escape(file.name)}</strong><small>${this.escape(file.path)}</small></td>
                                <td>${this.escape(file.suffix || '-')}</td>
                                <td>${this.formatBytes(file.size)}</td>
                                <td>${this.formatTime(file.mtime)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    async loadLogs() {
        try {
            const params = new URLSearchParams({ limit: '200' });
            const keyword = (this.logSearch?.value || '').trim();
            if (keyword) params.set('q', keyword);
            const response = await fetch(`/api/debug/logs?${params.toString()}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '读取日志失败');
            this.logNote.textContent = data.note || '';
            this.renderLogs(data.logs || []);
        } catch (error) {
            this.logBody.innerHTML = `<tr><td colspan="5" class="table-empty">${this.escape(error.message)}</td></tr>`;
        }
    }

    renderLogs(logs) {
        if (!logs.length) {
            this.logBody.innerHTML = '<tr><td colspan="5" class="table-empty">暂无匹配日志</td></tr>';
            return;
        }
        this.logBody.innerHTML = logs.map(log => `
            <tr>
                <td>${this.formatTime(log.created_at)}</td>
                <td>${this.escape(log.actor || '-')}</td>
                <td>${this.escape(log.action || '-')}</td>
                <td><strong>${this.escape(log.target_name || log.task_id || '-')}</strong><small>${this.escape(log.message || '')}</small></td>
                <td>${log.success ? '成功' : '失败'}</td>
            </tr>
        `).join('');
    }

    statusText(status) {
        const labels = {
            queued: '排队中',
            pending: '等待执行',
            processing: '生产中',
            awaiting_confirmation: '等待审核',
            completed: '已完成',
            error: '失败',
            interrupted: '已中断'
        };
        return labels[status] || status || '-';
    }

    setText(id, value) {
        const node = document.getElementById(id);
        if (node) node.textContent = value;
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

    formatBytes(value) {
        const size = Number(value || 0);
        if (size < 1024) return `${size} B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
        if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
        return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`;
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

document.addEventListener('DOMContentLoaded', () => new DebugWorkbench());
