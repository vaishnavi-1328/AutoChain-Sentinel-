(function () {
  const el = document.getElementById('tb-clock');
  function fmt() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}  `
      + `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())} UTC`;
  }
  function tick() { el.textContent = fmt(); }
  tick();
  setInterval(tick, 1000);
})();
