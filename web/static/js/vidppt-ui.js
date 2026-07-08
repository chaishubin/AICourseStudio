(function () {
    const ICONS = {
        success: '✓',
        error: '!',
        warning: '!',
        info: 'i'
    };

    class VidPPTUI {
        constructor() {
            this.toastRoot = null;
            this.modalRoot = null;
        }

        ensureToastRoot() {
            if (this.toastRoot) return this.toastRoot;
            this.toastRoot = document.createElement('div');
            this.toastRoot.className = 'vidppt-toast-root';
            this.toastRoot.setAttribute('aria-live', 'polite');
            document.body.appendChild(this.toastRoot);
            return this.toastRoot;
        }

        ensureModalRoot() {
            if (this.modalRoot) return this.modalRoot;
            this.modalRoot = document.createElement('div');
            document.body.appendChild(this.modalRoot);
            return this.modalRoot;
        }

        toast(message, options = {}) {
            if (!message) return null;
            const root = this.ensureToastRoot();
            const type = options.type || 'info';
            const toast = document.createElement('div');
            toast.className = `vidppt-toast vidppt-toast-${type}`;
            toast.innerHTML = `
                <span class="vidppt-toast-icon">${ICONS[type] || ICONS.info}</span>
                <span class="vidppt-toast-message"></span>
                <button type="button" class="vidppt-toast-close" aria-label="关闭提示">×</button>
            `;
            toast.querySelector('.vidppt-toast-message').textContent = message;
            const close = () => {
                toast.classList.add('leaving');
                window.setTimeout(() => toast.remove(), 180);
            };
            toast.querySelector('.vidppt-toast-close').addEventListener('click', close);
            root.appendChild(toast);
            window.setTimeout(() => toast.classList.add('visible'), 20);
            window.setTimeout(close, options.duration || 3600);
            return toast;
        }

        alert(message, options = {}) {
            return this.openModal({
                title: options.title || '提示',
                message,
                type: options.type || 'info',
                confirmText: options.confirmText || '知道了',
                cancelText: null
            }).then(() => true);
        }

        confirm(message, options = {}) {
            return this.openModal({
                title: options.title || '请确认',
                message,
                type: options.type || 'warning',
                confirmText: options.confirmText || '确认',
                cancelText: options.cancelText || '取消',
                danger: options.danger || false
            });
        }

        prompt(message, options = {}) {
            return this.openModal({
                title: options.title || '请输入',
                message,
                type: options.type || 'info',
                confirmText: options.confirmText || '保存',
                cancelText: options.cancelText || '取消',
                input: true,
                inputValue: options.value || '',
                placeholder: options.placeholder || ''
            });
        }

        openModal(options) {
            return new Promise(resolve => {
                const root = this.ensureModalRoot();
                const overlay = document.createElement('div');
                overlay.className = 'vidppt-modal-overlay';
                overlay.innerHTML = `
                    <section class="vidppt-modal" role="dialog" aria-modal="true" aria-labelledby="vidppt-modal-title">
                        <div class="vidppt-modal-icon vidppt-modal-icon-${options.type || 'info'}">
                            ${ICONS[options.type] || ICONS.info}
                        </div>
                        <div class="vidppt-modal-content">
                            <h2 id="vidppt-modal-title">${this.escape(options.title || '提示')}</h2>
                            <div class="vidppt-modal-message"></div>
                            ${options.input ? '<input class="vidppt-modal-input" type="text">' : ''}
                        </div>
                        <div class="vidppt-modal-actions">
                            ${options.cancelText ? '<button type="button" class="vidppt-modal-button secondary" data-action="cancel"></button>' : ''}
                            <button type="button" class="vidppt-modal-button primary${options.danger ? ' danger' : ''}" data-action="confirm"></button>
                        </div>
                    </section>
                `;
                overlay.querySelector('.vidppt-modal-message').textContent = options.message || '';
                overlay.querySelector('[data-action="confirm"]').textContent = options.confirmText || '确认';
                const cancelButton = overlay.querySelector('[data-action="cancel"]');
                if (cancelButton) cancelButton.textContent = options.cancelText || '取消';
                const input = overlay.querySelector('.vidppt-modal-input');
                if (input) {
                    input.value = options.inputValue || '';
                    input.placeholder = options.placeholder || '';
                }

                const finish = value => {
                    overlay.classList.remove('visible');
                    window.removeEventListener('keydown', onKeyDown);
                    window.setTimeout(() => overlay.remove(), 180);
                    resolve(value);
                };
                const onKeyDown = event => {
                    if (event.key === 'Escape') finish(options.input ? null : false);
                    if (event.key === 'Enter' && input) finish(input.value);
                };
                overlay.addEventListener('click', event => {
                    const action = event.target.dataset?.action;
                    if (action === 'cancel') finish(options.input ? null : false);
                    if (action === 'confirm') finish(input ? input.value : true);
                });
                window.addEventListener('keydown', onKeyDown);
                root.appendChild(overlay);
                window.setTimeout(() => {
                    overlay.classList.add('visible');
                    (input || overlay.querySelector('[data-action="confirm"]')).focus();
                }, 20);
            });
        }

        escape(value) {
            const node = document.createElement('div');
            node.textContent = value == null ? '' : String(value);
            return node.innerHTML;
        }
    }

    window.VidPPTUI = window.VidPPTUI || new VidPPTUI();
})();
