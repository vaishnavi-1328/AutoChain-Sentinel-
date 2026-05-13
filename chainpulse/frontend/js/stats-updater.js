window.CPStats = (function () {
  const els = {
    eventCount: document.getElementById('tb-event-count'),
    active:   document.getElementById('chip-active'),
    critical: document.getElementById('chip-critical'),
    high:     document.getElementById('chip-high'),
    avg:      document.getElementById('chip-avg'),
    routes:   document.getElementById('chip-routes'),
  };
  let total = 0;
  let critical = 0, high = 0;
  let delaySum = 0, delayCount = 0;
  let routeSum = 0;

  function update(event) {
    total++;
    const sev = (event.severity || 'low').toLowerCase();
    if (sev === 'critical') critical++;
    if (sev === 'high') high++;
    if (event.predicted_delay_max_days != null) {
      delaySum += Number(event.predicted_delay_max_days);
      delayCount++;
    }
    if (event.affected_route_count != null) routeSum += Number(event.affected_route_count);
    render();
  }

  function render() {
    els.eventCount.textContent = `${total} EVENTS`;
    els.active.textContent   = window.CPMap.activeCount();
    els.critical.textContent = critical;
    els.high.textContent     = high;
    els.avg.textContent      = delayCount ? (delaySum / delayCount).toFixed(1) + 'd' : '0d';
    els.routes.textContent   = routeSum;
  }

  setInterval(render, 5000);
  return { update };
})();
