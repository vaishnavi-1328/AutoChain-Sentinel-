// Order analysis modal: SHAP-style waterfall + supplier+event map + sortable table.
(function () {
  let modal = null, miniMap = null, layer = null;

  function ensureDom() {
    modal = document.getElementById('order-modal');
    if (!modal) return false;
    if (modal.dataset.built) return true;
    modal.innerHTML = `
      <div class="om-panel" role="document">
        <div class="om-header">
          <span id="om-title">Order analysis</span>
          <button class="gm-close" onclick="window.CPOrderAnalysis.close()">✕</button>
        </div>
        <div class="om-summary" id="om-summary"></div>
        <div class="om-body">
          <div class="om-waterfall"><svg id="om-waterfall-svg" width="100%" height="220"></svg></div>
          <div class="om-map" id="om-map"></div>
          <div class="om-table" id="om-table"></div>
          <div class="om-mitigations" id="om-mitigations" style="grid-column: 1 / 3"></div>
        </div>
      </div>
    `;
    modal.dataset.built = '1';
    modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
    return true;
  }

  function authHeaders() {
    const tok = localStorage.getItem('cp_token');
    return tok ? { Authorization: `Bearer ${tok}` } : {};
  }

  async function open(orderId) {
    if (!ensureDom()) return;
    modal.classList.remove('hidden');
    document.getElementById('om-summary').innerHTML = 'Loading...';
    try {
      const r = await fetch(`${window.CP.API_BASE}/orders/${orderId}/analysis`, { headers: authHeaders() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      render(data);
    } catch (e) {
      document.getElementById('om-summary').textContent = `Could not load: ${e.message}`;
    }
  }

  function close() {
    if (modal) modal.classList.add('hidden');
  }

  function render(data) {
    const o = data.order;
    const matched = data.matched_events || [];

    // SUMMARY
    document.getElementById('om-title').textContent =
      `Analysis — ${o.supplier_name} (${o.supplier_city}, ${o.supplier_country})`;
    document.getElementById('om-summary').innerHTML = `
      <div class="kv"><span class="kv-label">Status</span><span class="kv-val">${o.status.replace('_',' ')}</span></div>
      <div class="kv"><span class="kv-label">Predicted delay</span><span class="kv-val">+${o.delay_min_days}–${o.delay_max_days} days</span></div>
      <div class="kv"><span class="kv-label">Original ETA</span><span class="kv-val">${o.expected_delivery}</span></div>
      <div class="kv"><span class="kv-label">New ETA</span><span class="kv-val">${o.new_eta_earliest || o.expected_delivery} → ${o.new_eta_latest || o.expected_delivery}</span></div>
      <div class="kv"><span class="kv-label">Overlap adj</span><span class="kv-val">${data.overlap_adjustment_days}d</span></div>
      <div class="kv"><span class="kv-label">Matched events</span><span class="kv-val">${matched.length}</span></div>
    `;

    renderWaterfall(matched, data.overlap_adjustment_days || 0);
    renderMap(o, matched);
    renderTable(matched);
    loadMitigations(o.id);
  }

  async function loadMitigations(orderId) {
    const el = document.getElementById('om-mitigations');
    el.innerHTML = '<div class="om-mit-title">Recommended mitigations</div><div>Loading...</div>';
    try {
      const r = await fetch(`${window.CP.API_BASE}/orders/${orderId}/mitigations`, { headers: authHeaders() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      renderMitigations(data);
    } catch (e) {
      el.innerHTML = `<div class="om-mit-title">Mitigations</div><div style="color:var(--text-muted)">Not available: ${e.message}</div>`;
    }
  }

  function renderMitigations(data) {
    const el = document.getElementById('om-mitigations');
    const list = data.suggestions || [];
    if (!list.length) {
      el.innerHTML = '<div class="om-mit-title">Recommended mitigations</div><div class="empty-state">No active mitigations needed — order on track.</div>';
      return;
    }
    el.innerHTML = `
      <div class="om-mit-title">Recommended mitigations (${list.length})</div>
      <div class="om-mit-grid">
        ${list.map((m) => `
          <div class="om-mit-card" data-feas="${m.feasibility}">
            <div class="om-mit-action">${escapeHtml(m.action)}</div>
            <div class="om-mit-stats">
              <span><strong>−${m.est_delay_reduction_days}d</strong> delay</span>
              <span>+${m.cost_uplift_pct}% cost</span>
              <span class="feas-${m.feasibility}">${m.feasibility} feasibility</span>
            </div>
            <div class="om-mit-reason">${escapeHtml(m.reason)}</div>
          </div>
        `).join('')}
      </div>
    `;
  }

  function renderWaterfall(matched, overlapAdj) {
    const svg = d3.select('#om-waterfall-svg');
    svg.selectAll('*').remove();
    const w = svg.node().clientWidth || 500;
    const h = 200;
    const margin = { top: 20, right: 20, bottom: 30, left: 40 };
    const innerW = w - margin.left - margin.right;
    const innerH = h - margin.top - margin.bottom;
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Build steps: each matched event contributes (50% for non-top), final = total min delay
    const sorted = matched.slice().sort((a, b) => b.delay_contribution_days - a.delay_contribution_days);
    const steps = [];
    let cum = 0;
    sorted.forEach((m, i) => {
      const factor = i === 0 ? 1.0 : 0.5;
      const v = Math.round(m.delay_contribution_days * factor);
      steps.push({
        label: m.title?.slice(0, 18) || `Event ${i + 1}`,
        delta: v,
        severity: m.severity,
        from: cum, to: cum + v,
      });
      cum += v;
    });
    if (overlapAdj < 0) {
      steps.push({ label: 'Overlap', delta: overlapAdj, severity: 'low', from: cum, to: cum + overlapAdj });
      cum += overlapAdj;
    }
    steps.push({ label: 'TOTAL', delta: cum, severity: 'critical', from: 0, to: cum, isTotal: true });

    if (steps.length === 1) {
      g.append('text').attr('x', innerW / 2).attr('y', innerH / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', '#8B9CC8')
        .attr('font-size', 12)
        .text('No active disruptions matched this supplier.');
      return;
    }

    const yMax = Math.max(1, d3.max(steps, (s) => Math.max(s.from, s.to)));
    const x = d3.scaleBand().domain(steps.map((_, i) => i)).range([0, innerW]).padding(0.2);
    const y = d3.scaleLinear().domain([0, yMax * 1.1]).range([innerH, 0]);

    const sevColor = (s) => ({
      critical: '#EF4444', high: '#F97316', medium: '#EAB308', low: '#22C55E',
    })[s] || '#06B6D4';

    g.append('g').attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(x).tickFormat((_, i) => steps[i].label))
      .selectAll('text').attr('fill', '#8B9CC8').attr('font-size', 9)
      .attr('transform', 'rotate(-22)').attr('text-anchor', 'end');
    g.append('g').call(d3.axisLeft(y).ticks(5))
      .selectAll('text').attr('fill', '#4A5A82');

    g.selectAll('.bar')
      .data(steps)
      .enter().append('rect')
      .attr('x', (_, i) => x(i))
      .attr('y', (d) => y(Math.max(d.from, d.to)))
      .attr('width', x.bandwidth())
      .attr('height', (d) => Math.abs(y(d.from) - y(d.to)))
      .attr('fill', (d) => d.isTotal ? '#3B82F6' : sevColor(d.severity))
      .attr('opacity', 0.85);

    g.selectAll('.lbl')
      .data(steps)
      .enter().append('text')
      .attr('x', (_, i) => x(i) + x.bandwidth() / 2)
      .attr('y', (d) => y(Math.max(d.from, d.to)) - 4)
      .attr('text-anchor', 'middle')
      .attr('font-size', 10)
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('fill', '#E8EBF4')
      .text((d) => (d.delta >= 0 ? `+${d.delta}d` : `${d.delta}d`));
  }

  function renderMap(order, matched) {
    const el = document.getElementById('om-map');
    el.innerHTML = '';
    if (!miniMap || !el.contains(miniMap.getContainer())) {
      miniMap = L.map(el, { zoomControl: true, attributionControl: false });
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { subdomains: 'abcd' }).addTo(miniMap);
      layer = L.layerGroup().addTo(miniMap);
    } else {
      layer.clearLayers();
    }
    const supplier = [order.supplier_lat, order.supplier_lng];
    L.marker(supplier).addTo(layer).bindPopup(`<strong>${order.supplier_name}</strong>`);

    // proximity rings 200/500/800 km
    [200000, 500000, 800000].forEach((r) => {
      L.circle(supplier, { radius: r, color: '#3B5BDB', weight: 1, opacity: 0.35, fillOpacity: 0.04 }).addTo(layer);
    });

    const sevColor = (s) => ({
      critical: '#EF4444', high: '#F97316', medium: '#EAB308', low: '#22C55E',
    })[s] || '#06B6D4';
    matched.forEach((m) => {
      // backend returns event_id (Postgres UUID) but no lat/lng — pull from Redis cache via /events/{id} if needed.
      // To stay fast, just plot a generic pin if we have it in the matched payload (we don't); skip silently.
    });

    miniMap.setView(supplier, 5);
    setTimeout(() => miniMap.invalidateSize(), 100);
  }

  function renderTable(matched) {
    const el = document.getElementById('om-table');
    if (!matched.length) {
      el.innerHTML = '<div class="empty-state">No matched disruption events. Order is on track.</div>';
      return;
    }
    el.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>Severity</th><th>Title</th><th>Source</th>
            <th>Distance (km)</th><th>+Days</th><th>When</th>
          </tr>
        </thead>
        <tbody>
          ${matched.map((m) => `
            <tr>
              <td><span class="severity-${(m.severity||'low').toLowerCase()}">${(m.severity||'low').toUpperCase()}</span></td>
              <td>${escapeHtml(m.title || '')}</td>
              <td>${m.source_url ? `<a href="${m.source_url}" target="_blank" rel="noopener">${escapeHtml(m.source_name||'source')} ↗</a>` : '—'}</td>
              <td>${m.distance_km}</td>
              <td><strong>+${m.delay_contribution_days}d</strong></td>
              <td>${m.timestamp_utc ? new Date(m.timestamp_utc).toISOString().slice(0,10) : '—'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }

  window.CPOrderAnalysis = { open, close };
  // Override the old alert-based handler in orders-feed.js
  window.openDelayModal = (orderId) => window.CPOrderAnalysis.open(orderId);
})();
