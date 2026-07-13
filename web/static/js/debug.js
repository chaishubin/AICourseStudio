class DebugWorkbench {
    constructor() {
        this.taskBody = document.getElementById('debug-task-body');
        this.detailTitle = document.getElementById('debug-detail-title');
        this.detail = document.getElementById('debug-task-detail');
        this.environment = document.getElementById('debug-environment');
        this.logBody = document.getElementById('debug-log-body');
        this.logNote = document.getElementById('debug-log-note');
        this.logSearch = document.getElementById('debug-log-search');
        this.logPagination = document.getElementById('debug-log-pagination');
        this.logPage = 1;
        this.logPageSize = 20;
        this.logPaginationState = { page: 1, page_size: 20, total: 0, total_pages: 1 };
        this.refreshBtn = document.getElementById('debug-refresh-btn');
        this.diagnostics = document.getElementById('debug-diagnostics');
        this.healthBadge = document.getElementById('debug-health-badge');
        this.runtimeOutput = document.getElementById('debug-runtime-output');
        this.runtimeNote = document.getElementById('debug-runtime-note');
        this.runtimeSearch = document.getElementById('debug-runtime-search');
        this.runtimeTask = document.getElementById('debug-runtime-task');
        this.runtimeLevel = document.getElementById('debug-runtime-level');
        this.runtimeRefresh = document.getElementById('debug-runtime-refresh');
        this.runtimeCopy = document.getElementById('debug-runtime-copy');
        this.runtimeDownload = document.getElementById('debug-runtime-download');
        this.serverOutput = document.getElementById('debug-server-output');
        this.serverNote = document.getElementById('debug-server-note');
        this.serverSearch = document.getElementById('debug-server-search');
        this.serverTask = document.getElementById('debug-server-task');
        this.serverRefresh = document.getElementById('debug-server-refresh');
        this.serverCopy = document.getElementById('debug-server-copy');
        this.serverDownload = document.getElementById('debug-server-download');
        this.serverAutoRefresh = document.getElementById('debug-server-auto-refresh');
        this.serverLoading = false;
        this.selectedTaskId = null;
        this.init();
    }

    init() {
        this.refreshBtn?.addEventListener('click', () => this.loadOverview());
        this.logSearch?.addEventListener('input', () => this.loadLogs(1));
        this.runtimeRefresh?.addEventListener('click', () => this.loadRuntimeLogs());
        this.runtimeSearch?.addEventListener('input', () => this.loadRuntimeLogs());
        this.runtimeTask?.addEventListener('input', () => this.loadRuntimeLogs());
        this.runtimeLevel?.addEventListener('change', () => this.loadRuntimeLogs());
        this.runtimeCopy?.addEventListener('click', () => this.copyRuntimeLogs());
        this.serverRefresh?.addEventListener('click', () => this.loadServerLogs());
        this.serverSearch?.addEventListener('input', () => this.loadServerLogs());
        this.serverTask?.addEventListener('input', () => this.loadServerLogs());
        this.serverCopy?.addEventListener('click', () => this.copyServerLogs());
        this.loadOverview();
        this.loadLogs();
        this.loadRuntimeLogs();
        this.loadServerLogs();
        window.setInterval(() => {
            if (this.serverAutoRefresh?.checked && !document.hidden) this.loadServerLogs();
        }, 3000);
    }

    async loadOverview() {
        if (this.refreshBtn) this.refreshBtn.disabled = true;
        try {
            const response = await fetch('/api/debug/overview');
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '读取调试概览失败');
            this.renderMetrics(data);
            this.renderDiagnostics(data.diagnostics || {});
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

    renderDiagnostics(diagnostics) {
        const items = diagnostics.items || [];
        const labels = { success: '运行正常', info: '请注意', warning: '建议处理', error: '需要处理' };
        const status = diagnostics.status || 'info';
        this.healthBadge.textContent = labels[status] || '请检查';
        this.healthBadge.className = `debug-health-badge debug-health-${status}`;
        this.diagnostics.innerHTML = items.map(item => `
            <article class="debug-diagnostic debug-diagnostic-${this.escapeAttr(item.severity || 'info')}">
                <span class="debug-diagnostic-icon">${item.severity === 'success' ? '✓' : item.severity === 'error' ? '!' : 'i'}</span>
                <div><strong>${this.escape(item.title || '诊断提示')}</strong><p>${this.escape(item.detail || '')}</p><small>建议：${this.escape(item.action || '无需处理')}</small></div>
            </article>
        `).join('') || '<div class="debug-empty">暂无诊断结论</div>';
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
        if (this.runtimeTask) this.runtimeTask.value = taskId;
        if (this.serverTask) this.serverTask.value = taskId;
        this.loadRuntimeLogs();
        this.loadServerLogs();
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
        const task = data.task || {};
        const status = this.statusText(task.status);
        const issue = task.error || task.message || '未记录异常信息';
        const nextStep = task.status === 'error'
            ? '先查看下方运行日志中的 ERROR，再检查缺失文件或外部服务配置。'
            : task.status === 'interrupted'
                ? '确认是否由管理员停止或服务重启；如需继续，请回到生产工作台重新提交。'
                : task.status === 'awaiting_confirmation'
                    ? '任务正在等待内容审核，不是系统故障。'
                    : '当前无需人工处理；如进度长时间不变，可按任务 ID 查看运行日志。';
        this.detail.innerHTML = `
            <div class="debug-detail-section">
                <h4>管理员摘要</h4>
                <div class="debug-admin-summary">
                    <div><span>当前状态</span><strong>${this.escape(status)}</strong></div>
                    <div><span>当前阶段</span><strong>${this.escape(this.stageText(task.stage))}</strong></div>
                    <div class="debug-summary-wide"><span>系统信息</span><strong>${this.escape(issue)}</strong></div>
                    <div class="debug-summary-wide"><span>处理建议</span><strong>${this.escape(nextStep)}</strong></div>
                </div>
            </div>
            <details class="debug-technical-details">
                <summary>展开技术详情（路径、原始状态与 JSON）</summary>
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
            </details>
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

    async loadLogs(page = this.logPage) {
        this.logPage = page;
        try {
            const params = new URLSearchParams({
                page: String(this.logPage),
                page_size: String(this.logPageSize)
            });
            const keyword = (this.logSearch?.value || '').trim();
            if (keyword) params.set('q', keyword);
            const response = await fetch(`/api/debug/logs?${params.toString()}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '读取日志失败');
            this.logNote.textContent = data.note || '';
            this.logPaginationState = data.pagination || {
                page: this.logPage,
                page_size: this.logPageSize,
                total: (data.logs || []).length,
                total_pages: 1
            };
            this.logPage = this.logPaginationState.page || 1;
            this.renderLogs(data.logs || []);
            this.renderLogPagination();
        } catch (error) {
            this.logBody.innerHTML = `<tr><td colspan="6" class="table-empty">${this.escape(error.message)}</td></tr>`;
            if (this.logPagination) this.logPagination.hidden = true;
        }
    }

    renderLogs(logs) {
        if (!logs.length) {
            this.logBody.innerHTML = '<tr><td colspan="6" class="table-empty">暂无匹配日志</td></tr>';
            return;
        }
        this.logBody.innerHTML = logs.map(log => `
            <tr>
                <td>${this.formatTime(log.created_at)}</td>
                <td>${this.escape(log.actor || '-')}</td>
                <td>${this.escape(log.ip_address || '-')}</td>
                <td>${this.escape(log.action || '-')}</td>
                <td><strong>${this.escape(log.target_name || log.task_id || '-')}</strong><small>${this.escape(log.message || '')}</small></td>
                <td>${log.success ? '成功' : '失败'}</td>
            </tr>
        `).join('');
    }

    renderLogPagination() {
        if (!this.logPagination) return;
        const { page, page_size: pageSize, total, total_pages: totalPages } = this.logPaginationState;
        if (!total || totalPages <= 1) {
            this.logPagination.hidden = !total;
            this.logPagination.innerHTML = total ? `<span>共 ${total} 条</span>` : '';
            return;
        }
        const start = (page - 1) * pageSize + 1;
        const end = Math.min(page * pageSize, total);
        this.logPagination.hidden = false;
        this.logPagination.innerHTML = `
            <span>第 ${start}-${end} 条，共 ${total} 条</span>
            <div class="pagination-actions">
                <button type="button" class="table-action" data-debug-log-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>上一页</button>
                <span>${page} / ${totalPages}</span>
                <button type="button" class="table-action" data-debug-log-page="${page + 1}" ${page >= totalPages ? 'disabled' : ''}>下一页</button>
            </div>
        `;
        this.logPagination.querySelectorAll('[data-debug-log-page]').forEach(button => {
            button.addEventListener('click', () => {
                const nextPage = Number(button.dataset.debugLogPage);
                if (!Number.isNaN(nextPage)) this.loadLogs(nextPage);
            });
        });
    }

    runtimeParams(includeDownload = false) {
        const params = new URLSearchParams({ limit: '1000' });
        const keyword = (this.runtimeSearch?.value || '').trim();
        const taskId = (this.runtimeTask?.value || '').trim();
        const level = this.runtimeLevel?.value || '';
        if (keyword) params.set('q', keyword);
        if (taskId) params.set('task_id', taskId);
        if (level) params.set('level', level);
        if (includeDownload) params.set('download', '1');
        return params;
    }

    async loadRuntimeLogs() {
        if (!this.runtimeOutput) return;
        this.runtimeRefresh.disabled = true;
        try {
            const params = this.runtimeParams();
            const response = await fetch(`/api/debug/runtime-logs?${params.toString()}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '读取运行日志失败');
            this.runtimeOutput.textContent = (data.lines || []).join('\n') || '暂无匹配的运行日志。';
            const shown = (data.lines || []).length;
            const prefix = data.truncated ? `共匹配 ${data.matched_count} 行，页面显示最近 ${shown} 行。` : `共匹配 ${data.matched_count} 行。`;
            this.runtimeNote.textContent = `${prefix} ${data.note || ''}`;
            this.runtimeDownload.href = `/api/debug/runtime-logs?${this.runtimeParams(true).toString()}`;
        } catch (error) {
            this.runtimeOutput.textContent = error.message;
        } finally {
            this.runtimeRefresh.disabled = false;
        }
    }

    async copyRuntimeLogs() {
        try {
            await navigator.clipboard.writeText(this.runtimeOutput?.textContent || '');
            window.VidPPTUI?.toast('当前日志已复制', { type: 'success' });
        } catch (error) {
            window.VidPPTUI?.toast('复制失败，请手动选择日志文本', { type: 'error' });
        }
    }

    serverParams(includeDownload = false) {
        const params = new URLSearchParams({ limit: '1500' });
        const keyword = (this.serverSearch?.value || '').trim();
        const taskId = (this.serverTask?.value || '').trim();
        if (keyword) params.set('q', keyword);
        if (taskId) params.set('task_id', taskId);
        if (includeDownload) params.set('download', '1');
        return params;
    }

    async loadServerLogs() {
        if (!this.serverOutput || this.serverLoading) return;
        this.serverLoading = true;
        this.serverRefresh.disabled = true;
        const nearBottom = this.serverOutput.scrollHeight - this.serverOutput.scrollTop - this.serverOutput.clientHeight < 80;
        const previousTop = this.serverOutput.scrollTop;
        try {
            const response = await fetch(`/api/debug/server-logs?${this.serverParams().toString()}`, {
                cache: 'no-store'
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '读取服务器日志失败');
            this.serverOutput.textContent = (data.lines || []).join('\n') || '暂无服务器日志。';
            const shown = (data.lines || []).length;
            const prefix = data.truncated
                ? `共匹配 ${data.matched_count} 行，页面显示最近 ${shown} 行。`
                : `共匹配 ${data.matched_count} 行。`;
            this.serverNote.textContent = `${prefix} ${data.note || ''}`;
            this.serverNote.classList.toggle('debug-note-warning', !data.available);
            this.serverDownload.href = `/api/debug/server-logs?${this.serverParams(true).toString()}`;
            if (nearBottom) this.serverOutput.scrollTop = this.serverOutput.scrollHeight;
            else this.serverOutput.scrollTop = previousTop;
        } catch (error) {
            this.serverOutput.textContent = error.message;
        } finally {
            this.serverLoading = false;
            this.serverRefresh.disabled = false;
        }
    }

    async copyServerLogs() {
        try {
            await navigator.clipboard.writeText(this.serverOutput?.textContent || '');
            window.VidPPTUI?.toast('当前服务器日志已复制', { type: 'success' });
        } catch (error) {
            window.VidPPTUI?.toast('复制失败，请手动选择日志文本', { type: 'error' });
        }
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

    stageText(stage) {
        const labels = {
            queue: '等待资源', extract: '提取内容', analyze: '分析内容',
            course: '生成课程', render: '渲染幻灯片', tts: '生成语音',
            subtitle: '生成字幕', video: '合成视频', packaging: '课程包装',
            review: '内容审核', completed: '已完成'
        };
        return labels[stage] || stage || '未开始';
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
