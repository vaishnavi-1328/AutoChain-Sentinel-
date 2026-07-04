(function () {
  window.CPMap.init();
  window.CPTabs.init();
  window.CPMap.initSupplierLayer();

  // hydrate orders only when a token exists — avoids spurious 401s in dev tools
  if (window.CPOrders && localStorage.getItem('cp_token')) {
    window.CPOrders.init().then(() => {
      window.CPOrders.all().forEach((o) => window.CPMap.addSupplier(o));
    });
  }

  // backfill recent events
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
      window.CPWS.on('event', (event) => {
        window.CPMap.add(event);
        window.CPSidebar.add(event);
        window.CPStats.update(event);
        window.CPTicker.add(event);
      });
      window.CPWS.on('order_delay_update', (payload) => {
        window.CPOrders.update(payload);
        window.CPMap.updateSupplier(payload);
        window.CPStats.updateOrdersAtRisk && window.CPStats.updateOrdersAtRisk();
        if (payload.status !== 'ON_SCHEDULE' && window.CPToast) {
          window.CPToast.show(
            `⚠ ${payload.supplier_name}: +${payload.delay_min_days}–${payload.delay_max_days}d delay`
          );
        }
      });
      window.CPWS.connect();
    });

  // chip click → switch to orders tab
  const chipRisk = document.querySelector('.chip.orders-at-risk');
  if (chipRisk) chipRisk.addEventListener('click', () => window.CPTabs.activate('orders'));
})();
