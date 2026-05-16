window.CPTabs = (function () {
  const tabs = {};
  const panels = {};
  let badgeEl = null;

  function init() {
    document.querySelectorAll('.tab').forEach((btn) => {
      const name = btn.dataset.tab;
      tabs[name] = btn;
      btn.addEventListener('click', () => activate(name));
    });
    document.querySelectorAll('.tab-panel').forEach((p) => {
      const name = p.dataset.tab;
      panels[name] = p;
    });
    badgeEl = document.querySelector('.tab[data-tab="orders"] .tab-badge');
    setOrdersBadge(0);
  }

  function activate(name) {
    Object.entries(tabs).forEach(([n, btn]) => btn.classList.toggle('active', n === name));
    Object.entries(panels).forEach(([n, panel]) => panel.classList.toggle('active', n === name));
  }

  function setOrdersBadge(n) {
    if (!badgeEl) return;
    badgeEl.textContent = n > 0 ? `(${n}⚡)` : '';
  }

  return { init, activate, setOrdersBadge };
})();
