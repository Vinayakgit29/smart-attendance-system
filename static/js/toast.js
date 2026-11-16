/**
 * Toast Notification System
 * Usage: showToast('success'|'error'|'warning'|'info', title, message)
 */
(function() {
    function ensureContainer() {
        let c = document.getElementById('toast-container');
        if (!c) {
            c = document.createElement('div');
            c.id = 'toast-container';
            document.body.appendChild(c);
        }
        return c;
    }

    const ICONS = {
        success: '✅',
        error:   '❌',
        warning: '⚠️',
        info:    'ℹ️'
    };

    const LABELS = {
        success: 'Success',
        error:   'Error',
        warning: 'Warning',
        info:    'Info'
    };

    window.showToast = function(type, title, message, duration) {
        const container = ensureContainer();
        duration = duration || 4000;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div class="toast-icon">${ICONS[type] || 'ℹ️'}</div>
            <div class="toast-body">
                <p class="toast-title">${title || LABELS[type]}</p>
                ${message ? `<p class="toast-msg">${message}</p>` : ''}
            </div>
            <button class="toast-close" aria-label="Close">✕</button>
            <div class="toast-progress"></div>
        `;

        container.appendChild(toast);

        const close = toast.querySelector('.toast-close');
        let timer;

        function dismiss() {
            clearTimeout(timer);
            toast.classList.add('hiding');
            toast.addEventListener('animationend', () => toast.remove(), { once: true });
        }

        close.addEventListener('click', dismiss);
        timer = setTimeout(dismiss, duration);
        return toast;
    };

    // Auto-init: convert data-toast attributes on page load
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('[data-toast]').forEach(function(el) {
            const type = el.dataset.toast;
            const title = el.dataset.toastTitle;
            const msg = el.dataset.toastMsg;
            if (type) showToast(type, title, msg);
        });
    });
})();
