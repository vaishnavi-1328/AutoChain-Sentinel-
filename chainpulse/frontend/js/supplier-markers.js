// Extends window.CPMap with supplier layer + diamond markers.
(function () {
  let layer = null;
  const markers = {}; // order_id → marker
  const orders = {};  // order_id → order dict (for popup rebuild on update)

  function getMap() {
    return window._cpLeaflet; // set by map-manager after init
  }

  function popupHTML(o) {
    const status = o.status || 'ON_SCHEDULE';
    const m = (o.matched_events || [])[0];
    const causes = m
      ? `Driven by: ${escapeHTML(m.title || '')} ${m.source_url ? `<a href="${m.source_url}" target="_blank" rel="noopener">[${escapeHTML(m.source_name || 'source')} ↗]</a>` : ''}`
      : 'No active disruptions matched.';
    return `
      <div class="cp-popup__row"><strong>${escapeHTML(o.supplier_name)}</strong></div>
      <div class="cp-popup__sub">${escapeHTML(o.supplier_city)}, ${escapeHTML(o.supplier_country)}</div>
      <hr class="cp-popup__hr" />
      <div class="cp-popup__metric">Material: ${escapeHTML(o.materials || '')}</div>
      ${o.quantity != null ? `<div class="cp-popup__metric">Qty: ${o.quantity} ${escapeHTML(o.quantity_unit || '')}</div>` : ''}
      <div class="cp-popup__metric">Expected: ${o.expected_delivery}</div>
      <hr class="cp-popup__hr" />
      <div class="cp-popup__metric">Status: <strong style="color:${statusColor(status)}">${status.replace('_', ' ')}</strong></div>
      <div class="cp-popup__delay">+${o.delay_min_days} to +${o.delay_max_days} days</div>
      <div class="cp-popup__metric">${causes}</div>
      <button class="cp-popup__btn" onclick="window.openDelayModal('${o.id}')">📊 Full analysis</button>
    `;
  }

  function escapeHTML(s) {
    return String(s || '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }
  function statusColor(s) {
    return ({
      CRITICAL_DELAY: '#EF4444', DELAY_RISK: '#F97316', MONITOR: '#EAB308',
      ON_SCHEDULE: '#10B981', DELIVERED: '#4A5A82',
    })[s] || '#10B981';
  }

  function buildIcon(o) {
    const status = o.status || 'ON_SCHEDULE';
    const label = (o.supplier_name || '').slice(0, 6);
    return L.divIcon({
      className: '',
      html: `<div class="supplier-diamond" data-status="${status}">
               <span class="supplier-label">${escapeHTML(label)}</span>
             </div>`,
      iconSize: [14, 14],
      iconAnchor: [7, 7],
    });
  }

  function initSupplierLayer() {
    const map = getMap();
    if (!map) return;
    if (!layer) layer = L.layerGroup().addTo(map);
  }

  function addSupplier(order) {
    initSupplierLayer();
    const map = getMap();
    if (!map) return;
    orders[order.id] = order;
    if (markers[order.id]) markers[order.id].remove();
    const marker = L.marker([order.supplier_lat, order.supplier_lng], { icon: buildIcon(order) })
      .addTo(layer)
      .bindPopup(popupHTML(order), { maxWidth: 320 });
    markers[order.id] = marker;
  }

  function updateSupplier(payload) {
    const merged = Object.assign({}, orders[payload.order_id] || {}, {
      id:               payload.order_id,
      supplier_name:    payload.supplier_name,
      supplier_lat:     payload.supplier_lat,
      supplier_lng:     payload.supplier_lng,
      status:           payload.status,
      delay_min_days:   payload.delay_min_days,
      delay_max_days:   payload.delay_max_days,
      expected_delivery: payload.original_eta,
      matched_events:   payload.matched_events || [],
    });
    addSupplier(merged); // rebuild icon + popup
  }

  function removeSupplier(orderId) {
    if (markers[orderId]) { markers[orderId].remove(); delete markers[orderId]; }
    delete orders[orderId];
  }

  function flyToSupplier(orderId, lat, lng) {
    const map = getMap();
    if (!map) return;
    map.flyTo([lat, lng], Math.max(map.getZoom(), 4), { duration: 0.6 });
    if (markers[orderId]) markers[orderId].openPopup();
  }

  Object.assign(window.CPMap, { initSupplierLayer, addSupplier, updateSupplier, removeSupplier, flyToSupplier });
})();
