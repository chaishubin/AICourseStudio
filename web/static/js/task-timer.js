class TaskTimerDashboard {
    constructor(options = {}) {
        this.options = {
            container: options.container || '#dashboard-column',
            refreshInterval: options.refreshInterval || 1000,
            visible: options.visible || false,
        };

        this.STAGE_COLORS = {
            extract: '#64d2ff',
            tts: '#bf5af2',
            video: '#ffd60a',
        };

        this.STAGE_NAMES = {
            extract: '提取内容',
            tts: '文字转语音',
            video: '合成视频',
        };

        this.DISPLAY_STAGES = ['extract', 'tts', 'video'];

        this.state = {
            active: false,
            no_task: true,
            status: null,
            current_stage: null,
            started_at: null,
            stage_started_at: null,
            stage_timings: {},
            completed_at: null,
            error: null,
        };

        this._intervalId = null;
        this._tickId = null;
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
        this.el.id = 'timer-module';

        const legendItems = this.DISPLAY_STAGES.map(stage => {
            const color = this.STAGE_COLORS[stage];
            const glow = color.replace(/^#/, 'rgba(') ? `rgba(${parseInt(color.slice(1,3),16)},${parseInt(color.slice(3,5),16)},${parseInt(color.slice(5,7),16)},0.4)` : 'rgba(255,255,255,0.3)';
            return `
            <div class="timer-legend-item" data-stage="${stage}" style="--dot-glow:${glow}">
                <span class="timer-legend-dot" style="background:${color}"></span>
                <span class="timer-legend-name">${this.STAGE_NAMES[stage]}</span>
                <span class="timer-legend-time">--:--</span>
            </div>`;
        }).join('');

        this.el.innerHTML = `
            <div class="dashboard-header">
                <span class="dashboard-title">任务计时</span>
                <button class="dashboard-close" aria-label="关闭计时面板">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                        <line x1="4" y1="4" x2="12" y2="12"/><line x1="12" y1="4" x2="4" y2="12"/>
                    </svg>
                </button>
            </div>
            <div class="timer-body" id="timer-body" style="display:none">
                <div class="timer-pie-wrap">
                    <div class="timer-pie" id="timer-pie"></div>
                    <div class="timer-pie-center">
                        <span class="timer-total" id="timer-total">--:--</span>
                        <span class="timer-status" id="timer-status">等待任务</span>
                    </div>
                    <div class="timer-hand" id="timer-hand" style="display:none">
                        <div class="timer-hand-tip"></div>
                    </div>
                </div>
                <div class="timer-legend">
                    ${legendItems}
                    <div class="timer-legend-divider"></div>
                    <div class="timer-legend-total">
                        <span class="timer-legend-name">总计</span>
                        <span class="timer-legend-time" id="timer-legend-total">--:--</span>
                    </div>
                </div>
            </div>
            <div class="timer-empty" id="timer-empty">暂无进行中的任务</div>
        `;

        container.appendChild(this.el);
        this.el.querySelector('.dashboard-close').addEventListener('click', () => this.hide());

        this._els = {
            body: this.el.querySelector('#timer-body'),
            pie: this.el.querySelector('#timer-pie'),
            hand: this.el.querySelector('#timer-hand'),
            total: this.el.querySelector('#timer-total'),
            status: this.el.querySelector('#timer-status'),
            legendTotal: this.el.querySelector('#timer-legend-total'),
            empty: this.el.querySelector('#timer-empty'),
        };
    }

    _createToggleButton() {
        this._toggleBtn = document.createElement('button');
        this._toggleBtn.className = 'dashboard-toggle timer-toggle';
        this._toggleBtn.setAttribute('aria-label', '任务计时');
        this._toggleBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
            </svg>
        `;
        this._toggleBtn.addEventListener('click', () => this.toggle());
        document.body.appendChild(this._toggleBtn);
    }

    /* ── Data Fetching ── */

    async fetchData() {
        try {
            const resp = await fetch('/api/task-timing');
            if (!resp.ok) return;
            const data = await resp.json();
            this.state = data;
            this._updateUI();
        } catch { /* ignore */ }
    }

    /* ── UI Update ── */

    _updateUI() {
        if (!this._els) return;

        if (this.state.no_task) {
            this._els.body.style.display = 'none';
            this._els.empty.style.display = 'block';
            this._clearTick();
            return;
        }

        this._els.empty.style.display = 'none';
        this._els.body.style.display = 'flex';

        this._updateLegend();
        this._updatePie();

        const { status, current_stage, error } = this.state;
        const isComplete = (status === 'completed' || status === 'error');

        if (isComplete) {
            this._els.status.textContent = status === 'completed' ? '已完成' : (error || '转换失败');
            this._clearTick();
        } else if (current_stage && this.STAGE_NAMES[current_stage]) {
            this._els.status.textContent = this.STAGE_NAMES[current_stage] + '中';
            this._startTick();
        }
    }

    /* ── Legend ── */

    _updateLegend() {
        const { stage_timings, current_stage, stage_started_at } = this.state;
        const now = Date.now() / 1000;

        for (const stage of this.DISPLAY_STAGES) {
            const item = this.el.querySelector(`.timer-legend-item[data-stage="${stage}"]`);
            if (!item) continue;
            const timeEl = item.querySelector('.timer-legend-time');

            item.classList.remove('completed', 'active');

            if (stage_timings && stage_timings[stage]) {
                item.classList.add('completed');
                timeEl.textContent = this._fmtDur(stage_timings[stage].duration);
            } else if (current_stage === stage && stage_started_at) {
                item.classList.add('active');
                timeEl.textContent = this._fmtDur(now - stage_started_at);
            } else {
                timeEl.textContent = '--:--';
            }
        }
    }

    /* ── Pie Chart ── */

    _updatePie() {
        const now = Date.now() / 1000;
        const { stage_timings, current_stage, stage_started_at, status, started_at, completed_at } = this.state;
        const isComplete = (status === 'completed' || status === 'error');

        if (!started_at) {
            this._resetPie();
            return;
        }

        /* Gather durations for each display stage */
        const durations = {};
        for (const stage of this.DISPLAY_STAGES) {
            if (stage_timings && stage_timings[stage]) {
                durations[stage] = stage_timings[stage].duration;
            }
        }
        if (current_stage && stage_started_at && !isComplete) {
            durations[current_stage] = now - stage_started_at;
        }

        const totalDuration = Object.values(durations).reduce((a, b) => a + b, 0);
        if (totalDuration === 0) {
            this._resetPie();
            return;
        }

        const totalElapsed = isComplete && completed_at
            ? completed_at - started_at
            : now - started_at;

        const isFirstRotation = totalElapsed < 60;

        /* Build conic-gradient stops */
        const stops = [];
        let cumPct = 0;

        for (const stage of this.DISPLAY_STAGES) {
            if (!(stage in durations) || durations[stage] <= 0) continue;

            const color = this.STAGE_COLORS[stage];
            let stagePct;

            if (isFirstRotation) {
                /* Sweep mode: 6° per second */
                stagePct = (durations[stage] * 6 / 360) * 100;
            } else {
                /* Proportional mode: fraction of total */
                stagePct = (durations[stage] / totalDuration) * 100;
            }

            if (cumPct >= 100) break;
            const endPct = Math.min(cumPct + stagePct, 100);
            stops.push(`${color} ${cumPct}% ${endPct}%`);
            cumPct = endPct;
        }

        /* Fill remaining with surface-3 */
        if (cumPct < 99.9) {
            stops.push(`var(--color-surface-3) ${cumPct}% 100%`);
        }

        this._els.pie.style.background = `conic-gradient(${stops.join(', ')})`;

        /* Hand */
        if (isComplete) {
            this._els.hand.style.display = 'none';
        } else {
            const handAngle = (totalElapsed * 6) % 360;
            this._els.hand.style.display = '';
            this._els.hand.style.transform = `rotate(${handAngle}deg)`;
        }

        /* Times */
        this._els.total.textContent = this._fmtDur(totalDuration);
        this._els.legendTotal.textContent = this._fmtDur(totalDuration);
    }

    _resetPie() {
        if (!this._els) return;
        this._els.pie.style.background = 'var(--color-surface-3)';
        this._els.hand.style.display = 'none';
        this._els.total.textContent = '--:--';
        this._els.legendTotal.textContent = '--:--';
    }

    /* ── Live Tick ── */

    _startTick() {
        if (this._tickId) return;
        this._tick();
        this._tickId = setInterval(() => this._tick(), 200);
    }

    _clearTick() {
        if (this._tickId) {
            clearInterval(this._tickId);
            this._tickId = null;
        }
    }

    _tick() {
        this._updateLegend();
        this._updatePie();
    }

    _fmtDur(seconds) {
        const s = Math.max(0, Math.floor(seconds));
        const m = Math.floor(s / 60);
        const sec = s % 60;
        return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
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
        if (this._visible) this.hide();
        else this.show();
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
        this._clearTick();
    }

    /* ── Cleanup ── */

    destroy() {
        this.stopPolling();
        if (this.el && this.el.parentNode) this.el.parentNode.removeChild(this.el);
        if (this._toggleBtn && this._toggleBtn.parentNode) this._toggleBtn.parentNode.removeChild(this._toggleBtn);
    }
}