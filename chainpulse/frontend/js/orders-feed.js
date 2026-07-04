window.CPOrders = (function () {
  let listEl = null;
  const cache = new Map(); // order_id → order dict
  const STATUS_ORDER = ['CRITICAL_DELAY', 'DELAY_RISK', 'MONITOR', 'ON_SCHEDULE', 'DELIVERED'];

  function init() {
    listEl = document.getElementById('orders-list');
    return reload();
  }

  function authHeaders() {
    const tok = localStorage.getItem('cp_token');
    return tok ? { Authorization: `Bearer ${tok}` } : {};
  }

  async function reload() {
    if (!listEl) return;
    try {
      const r = await fetch(`${window.CP.API_BASE}/orders`, { headers: authHeaders() });
      if (!r.ok) {
        // 401 = token expired or missing — clear stale token and prompt sign-in
        if (r.status === 401) localStorage.removeItem('cp_token');
        listEl.innerHTML = `<li class="empty-state">Sign in to track supplier orders.<br>
          <a href="./onboarding.html" style="color:var(--accent-cyan)">→ Sign up / Sign in</a></li>`;
        return;
      }
      const orders = await r.json();
      cache.clear();
      orders.forEach((o) => cache.set(o.id, o));
      render();
    } catch (e) {
      console.error('orders reload failed', e);
    }
  }

  function render() {
    if (!listEl) return;
    const orders = Array.from(cache.values()).sort((a, b) => {
      const da = STATUS_ORDER.indexOf(a.status);
      const db = STATUS_ORDER.indexOf(b.status);
      return da - db;
    });
    if (orders.length === 0) {
      listEl.innerHTML = `<li class="empty-state">No orders yet. Click <strong>+ Add Order</strong> to track a supplier.</li>`;
    } else {
      listEl.innerHTML = orders.map(renderCard).join('');
      attachCardHandlers();
    }
    if (window.CPTabs) window.CPTabs.setOrdersBadge(atRiskCount());
    if (window.CPStats && window.CPStats.updateOrdersAtRisk) window.CPStats.updateOrdersAtRisk();
  }

  function renderCard(o) {
    const status = o.status || 'ON_SCHEDULE';
    const causes = (o.matched_events || []).map((m) => `
      <div class="cause-item">
        · ${escapeHTML(m.title || '')}
        ${m.source_url ? `<a href="${m.source_url}" target="_blank" rel="noopener">[${escapeHTML(m.source_name || 'source')} ↗]</a>` : ''}
        ${m.timestamp_utc ? `<span class="cause-date">${shortDate(m.timestamp_utc)}</span>` : ''}
      </div>
    `).join('') || '<div class="cause-item" style="color:var(--text-muted)">No active disruptions matched.</div>';

    const eta = (o.new_eta_earliest && o.new_eta_latest)
      ? `${o.new_eta_earliest} → ${o.new_eta_latest}`
      : `${o.expected_delivery}`;

    return `
      <li class="order-card" data-order-id="${o.id}" data-status="${status}">
        <div class="order-card-header">
          <span class="status-badge status-${status}">${statusLabel(status)}</span>
          <div class="order-actions">
            <button onclick="window.openEditDrawer('${o.id}')">Edit</button>
            <button onclick="window.deleteOrder('${o.id}')" title="Delete">✕</button>
          </div>
        </div>
        <div class="order-supplier-name">${escapeHTML(o.supplier_name)}</div>
        <div class="order-supplier-location">${escapeHTML(o.supplier_city)}, ${escapeHTML(o.supplier_country)}</div>
        <div class="order-details">
          <span class="label">Material</span><span>${escapeHTML(o.materials)}</span>
          <span class="label">Qty</span><span>${o.quantity != null ? `${o.quantity} ${escapeHTML(o.quantity_unit || '')}` : '—'}</span>
          <span class="label">Expected</span><span>${o.expected_delivery}</span>
        </div>
        <div class="order-delay-block">
          <div class="delay-label">ESTIMATED DELAY</div>
          <div class="delay-value">+${o.delay_min_days} to +${o.delay_max_days} days</div>
          <div class="new-eta">New ETA: ${eta}</div>
        </div>
        <div class="order-causes">
          <div class="causes-label">Driven by:</div>
          ${causes}
        </div>
        <div class="order-card-actions">
          <button onclick="window.flyToSupplier('${o.id}', ${o.supplier_lat}, ${o.supplier_lng})">📍 Show on map</button>
          <button onclick="window.openDelayModal('${o.id}')">📊 Full analysis</button>
        </div>
      </li>
    `;
  }

  function attachCardHandlers() {
    // most actions are inline onclick; nothing else to wire here yet.
  }

  function statusLabel(s) {
    return ({
      CRITICAL_DELAY: '🔴 Critical delay',
      DELAY_RISK:     '⚠ Delay risk',
      MONITOR:        '~ Monitor',
      ON_SCHEDULE:    '✓ On schedule',
      DELIVERED:      '✓ Delivered',
    })[s] || s;
  }

  function escapeHTML(s) {
    return String(s || '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }
  function shortDate(iso) {
    try { return new Date(iso).toISOString().slice(0, 10); } catch { return ''; }
  }

  function add(order) { cache.set(order.id, order); render(); }
  function update(payload) {
    const cur = cache.get(payload.order_id);
    const merged = Object.assign({}, cur || {}, {
      id:               payload.order_id,
      supplier_name:    payload.supplier_name,
      supplier_lat:     payload.supplier_lat,
      supplier_lng:     payload.supplier_lng,
      status:           payload.status,
      delay_min_days:   payload.delay_min_days,
      delay_max_days:   payload.delay_max_days,
      expected_delivery: payload.original_eta,
      new_eta_earliest: payload.new_eta_earliest,
      new_eta_latest:   payload.new_eta_latest,
      matched_events:   payload.matched_events || [],
    });
    cache.set(payload.order_id, merged);
    render();
  }
  function remove(orderId) { cache.delete(orderId); render(); }
  function get(orderId) { return cache.get(orderId); }
  function all() { return Array.from(cache.values()); }
  function atRiskCount() {
    return all().filter((o) => o.status === 'CRITICAL_DELAY' || o.status === 'DELAY_RISK' || o.status === 'MONITOR').length;
  }
  function totalCount() { return cache.size; }

  // exported helpers
  window.deleteOrder = async (orderId) => {
    if (!confirm('Delete this order?')) return;
    await fetch(`${window.CP.API_BASE}/orders/${orderId}`, { method: 'DELETE', headers: authHeaders() });
    remove(orderId);
    if (window.CPMap && window.CPMap.removeSupplier) window.CPMap.removeSupplier(orderId);
  };
  window.flyToSupplier = (orderId, lat, lng) => {
    if (window.CPMap && window.CPMap.flyToSupplier) window.CPMap.flyToSupplier(orderId, lat, lng);
  };
  window.openDelayModal = async (orderId) => {
    const r = await fetch(`${window.CP.API_BASE}/orders/${orderId}/analysis`, { headers: authHeaders() });
    if (!r.ok) return alert('Could not load analysis');
    const data = await r.json();
    const lines = (data.matched_events || []).map(m =>
      `• ${m.title}\n  ${m.source_name}: ${m.source_url}\n  ${m.distance_km}km away, +${m.delay_contribution_days}d`
    ).join('\n\n') || 'No active matches.';
    alert(`Full analysis — ${data.order.supplier_name}\n` +
          `Status: ${data.order.status}  delay: +${data.order.delay_min_days} to +${data.order.delay_max_days} days\n` +
          `Overlap adj: ${data.overlap_adjustment_days}d\n\n${lines}`);
  };
  window.openEditDrawer = (orderId) => {
    if (window.CPOrderDrawer && window.CPOrderDrawer.openForEdit) window.CPOrderDrawer.openForEdit(orderId);
  };

  return { init, reload, add, update, remove, get, all, atRiskCount, totalCount };
})();
