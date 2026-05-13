(function () {
  window.CPMap.init();

  // Backfill recent events on load (REST), then go live.
  fetch(`${window.CP.API_BASE}/events/recent?limit=50`)
    .then(r => r.ok ? r.json() : { events: [] })
    .then((data) => {
      (data.events || []).reverse().forEach((evt) => {
        window.CPMap.add(evt);
        window.CPSidebar.add(evt);
        window.CPStats.update(evt);
        window.CPTicker.add(evt);
      });
    })
    .catch(() => {})
    .finally(() => {
      window.CPWS.onEvent((event) => {
        window.CPMap.add(event);
        window.CPSidebar.add(event);
        window.CPStats.update(event);
        window.CPTicker.add(event);
      });
      window.CPWS.connect();
    });
})();
