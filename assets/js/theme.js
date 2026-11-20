(() => {
  const root = document.documentElement;
  const key = 'industryReadyPortfolioTheme';
  let saved = null;
  try { saved = localStorage.getItem(key); } catch (_) {}
  const preferred = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  const initial = saved === 'dark' || saved === 'light' ? saved : preferred;
  root.dataset.theme = initial;
  const mount = () => {
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      const update = () => {
        const dark = root.dataset.theme === 'dark';
        button.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
        button.setAttribute('aria-pressed', dark ? 'true' : 'false');
        button.innerHTML = `<span class="theme-icon" aria-hidden="true">${dark ? '☀' : '☾'}</span><span class="theme-label">${dark ? 'Light mode' : 'Dark mode'}</span>`;
      };
      if (!button.dataset.themeReady) {
        button.addEventListener('click', () => {
          root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
          try { localStorage.setItem(key, root.dataset.theme); } catch (_) {}
          update();
        });
        button.dataset.themeReady = '1';
      }
      update();
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
