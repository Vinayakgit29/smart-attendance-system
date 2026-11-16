// Global theme engine: the toggle control lives only on the starting (home) page,
// but the chosen theme is remembered and applied automatically on every page.
(function () {
    function apply(mode) {
        if (mode === 'dark') document.documentElement.classList.add('dark-mode');
        else document.documentElement.classList.remove('dark-mode');
        const text = mode === 'dark' ? '☀️' : '🌙';
        document.querySelectorAll('[data-theme-toggle]').forEach(function (b) {
            b.textContent = text;
            b.setAttribute('aria-pressed', mode === 'dark' ? 'true' : 'false');
        });
    }

    function toggle() {
        const cur = document.documentElement.classList.contains('dark-mode') ? 'dark' : 'light';
        const next = cur === 'dark' ? 'light' : 'dark';
        apply(next);
        try { localStorage.setItem('theme', next); } catch (e) {}
    }

    document.addEventListener('DOMContentLoaded', function () {
        // Always apply the saved preference, on every page, as soon as it loads.
        const stored = (function () {
            try { return localStorage.getItem('theme') || 'light'; }
            catch (e) { return 'light'; }
        })();
        apply(stored);

        // Only wire up click handlers on toggle buttons that already exist in the
        // page markup (the home page places one deliberately) — never create one.
        document.querySelectorAll('[data-theme-toggle]').forEach(function (b) {
            if (!b.__themeToggleAttached) {
                b.addEventListener('click', toggle);
                b.__themeToggleAttached = true;
            }
        });
    });
})();
