class SystemDashboard {
    constructor(options = {}) {
        this.options = {
            container: options.container || '#dashboard-column',
            refreshInterval: options.refreshInterval || 3000,
            visible: options.visible || false,
        };

        this.state = {
            cpu: { percent: 0, count: 0 },
            memory: { percent: 0, total_gb: 0, used_gb: 0, available_gb: 0 },
            available: true,
        };

        this._intervalId = null;
        this._visible = this.options.visible;

        this._createDOM();
        this._createToggleButton();

        if (this._visible) {
            this.show();
        }
    }

    /* ── DOM Creation ── */

    _createDOM() {
        const container = document.querySelector(this.options.container);
        if (!container) return;

        this.el = document.createElement('section');
        this.el.className = 'card dashboard-card';
        this.el.id = 'dashboard-module';

        this.el.innerHTML = `
            <div class="dashboard-header">
                <span class="dashboard-title">系统监控</span>
                <button class="dashboard-close" aria-label="关闭仪表盘">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                        <line x1="4" y1="4" x2="12" y2="12"/><line x1="12" y1="4" x2="4" y2="12"/>
                    </svg>
                </button>
            </div>
            <div class="dashboard-gauges">
                <div class="gauge-wrapper">
                    <span class="gauge-label">CPU</span>
                    <div class="gauge-track gauge-ok" id="cpu-gauge">
                        <div class="gauge-center">
                            <span class="gauge-value" id="cpu-value">0</span>
                            <span class="gauge-unit">%</span>
                        </div>
                    </div>
                    <span class="gauge-sub" id="cpu-sub"></span>
                </div>
                <div class="gauge-wrapper">
                    <span class="gauge-label">内存</span>
                    <div class="gauge-track gauge-ok" id="mem-gauge">
                        <div class="gauge-center">
                            <span class="gauge-value" id="mem-value">0</span>
                            <span class="gauge-unit">%</span>
                        </div>
                    </div>
                    <span class="gauge-sub" id="mem-sub"></span>
                </div>
            </div>
            <div class="dashboard-unavailable" style="display:none" id="dashboard-unavailable">
                系统监控不可用（psutil 未安装）
            </div>
        `;

        container.appendChild(this.el);

        this.el.querySelector('.dashboard-close').addEventListener('click', () => this.hide());

        // Cache element references
        this._els = {
            cpuGauge: this.el.querySelector('#cpu-gauge'),
            cpuValue: this.el.querySelector('#cpu-value'),
            cpuSub: this.el.querySelector('#cpu-sub'),
            memGauge: this.el.querySelector('#mem-gauge'),
            memValue: this.el.querySelector('#mem-value'),
            memSub: this.el.querySelector('#mem-sub'),
            gauges: this.el.querySelector('.dashboard-gauges'),
            unavailable: this.el.querySelector('#dashboard-unavailable'),
        };
    }

    _createToggleButton() {
        this._toggleBtn = document.createElement('button');
        this._toggleBtn.className = 'dashboard-toggle';
        this._toggleBtn.setAttribute('aria-label', '系统监控');
        this._toggleBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="3" width="20" height="14" rx="2"/>
                <line x1="8" y1="21" x2="16" y2="21"/>
                <line x1="12" y1="17" x2="12" y2="21"/>
            </svg>
        `;
        this._toggleBtn.addEventListener('click', () => this.toggle());
        document.body.appendChild(this._toggleBtn);
    }

    /* ── Data Fetching ── */

    async fetchData() {
        try {
            const resp = await fetch('/api/system-stats');
            if (!resp.ok) {
                if (resp.status === 503 || resp.status === 404) {
                    this.state.available = false;
                    this._showUnavailable();
                }
                return;
            }
            const data = await resp.json();
            if (!data.success) {
                this.state.available = false;
                this._showUnavailable();
                return;
            }
            this.state.available = true;
            this.state.cpu = data.cpu;
            this.state.memory = data.memory;
            this._updateGauges();
        } catch {
            this.state.available = false;
            this._showUnavailable();
        }
    }

    _showUnavailable() {
        if (this._els) {
            this._els.gauges.style.display = 'none';
            this._els.unavailable.style.display = 'block';
        }
    }

    _updateGauges() {
        if (!this._els) return;

        const cpu = this.state.cpu.percent;
        const mem = this.state.memory.percent;

        this._els.cpuGauge.style.setProperty('--gauge-percent', cpu);
        this._els.cpuValue.textContent = Math.round(cpu);
        this._els.cpuSub.textContent = this.state.cpu.count
            ? `${this.state.cpu.count} 核心`
            : '';

        this._els.memGauge.style.setProperty('--gauge-percent', mem);
        this._els.memValue.textContent = Math.round(mem);
        this._els.memSub.textContent = `${this.state.memory.used_gb} / ${this.state.memory.total_gb} GB`;

        this._applyGaugeColor(this._els.cpuGauge, cpu);
        this._applyGaugeColor(this._els.memGauge, mem);
    }

    _applyGaugeColor(gaugeEl, value) {
        gaugeEl.classList.remove('gauge-ok', 'gauge-warn', 'gauge-danger');
        if (value < 60) {
            gaugeEl.classList.add('gauge-ok');
        } else if (value < 85) {
            gaugeEl.classList.add('gauge-warn');
        } else {
            gaugeEl.classList.add('gauge-danger');
        }
    }

    /* ── Visibility ── */

    show() {
        this._visible = true;
        this.el.classList.add('dashboard-visible');
        this._toggleBtn.classList.add('dashboard-active');
        this.startPolling();
    }

    hide() {
        this._visible = false;
        this.el.classList.remove('dashboard-visible');
        this._toggleBtn.classList.remove('dashboard-active');
        this.stopPolling();
    }

    toggle() {
        if (this._visible) {
            this.hide();
        } else {
            this.show();
        }
    }

    /* ── Polling ── */

    startPolling() {
        if (this._intervalId) return;
        this.fetchData();
        this._intervalId = setInterval(() => this.fetchData(), this.options.refreshInterval);
    }

    stopPolling() {
        if (this._intervalId) {
            clearInterval(this._intervalId);
            this._intervalId = null;
        }
    }

    /* ── Cleanup ── */

    destroy() {
        this.stopPolling();
        if (this.el && this.el.parentNode) {
            this.el.parentNode.removeChild(this.el);
        }
        if (this._toggleBtn && this._toggleBtn.parentNode) {
            this._toggleBtn.parentNode.removeChild(this._toggleBtn);
        }
    }
}