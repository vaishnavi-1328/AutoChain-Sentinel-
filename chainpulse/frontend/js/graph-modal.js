// Supply-chain graph modal — D3 force layout fed by /graph/{event_id}.
// No external lib beyond D3 (already CDN-loaded).
window.CPModal = (function () {
  let modal = null;
  let simulation = null;

  function ensureDom() {
    modal = document.getElementById('graph-modal');
    if (!modal) return;
    modal.innerHTML = `
      <div class="gm-panel" role="document">
        <div class="gm-header">
          <span id="gm-title">Supply chain impact graph</span>
          <button class="gm-close" onclick="window.CPModal.close()" aria-label="Close">✕</button>
        </div>
        <svg id="gm-svg" class="gm-canvas"></svg>
        <aside class="gm-legend">
          <div class="gm-legend-title">Node types</div>
          <div class="gm-legend-row"><span class="gm-chip" style="background:#EF4444"></span>Disruption Event</div>
          <div class="gm-legend-row"><span class="gm-chip" style="background:#06B6D4"></span>Port</div>
          <div class="gm-legend-row"><span class="gm-chip" style="background:#3B82F6"></span>City</div>
          <div class="gm-legend-row"><span class="gm-chip" style="background:#6366F1"></span>OEM</div>
          <div class="gm-legend-row"><span class="gm-chip" style="background:#22C55E"></span>SKU</div>
          <div class="gm-legend-row"><span class="gm-chip" style="background:#8B9CC8"></span>Region / other</div>
          <hr/>
          <div class="gm-stat" id="gm-stats">—</div>
          <div class="gm-tip" id="gm-tip"></div>
          <hr/>
          <div class="gm-legend-title">Why this delay (SHAP)</div>
          <svg id="gm-shap" width="100%" height="180"></svg>
        </aside>
      </div>
    `;
    modal.addEventListener('click', (e) => {
      if (e.target === modal) close();
    });
  }

  function colorFor(labels) {
    if (!labels) return '#8B9CC8';
    if (labels.includes('DisruptionEvent')) return '#EF4444';
    if (labels.includes('Port'))            return '#06B6D4';
    if (labels.includes('City'))            return '#3B82F6';
    if (labels.includes('OEM'))             return '#6366F1';
    if (labels.includes('SKU'))             return '#22C55E';
    return '#8B9CC8';
  }
  function radiusFor(labels) {
    if (labels && labels.includes('DisruptionEvent')) return 11;
    return 7;
  }

  async function open(eventNodeIdOrEventId) {
    ensureDom();
    if (!modal) return;
    modal.classList.remove('hidden');
    document.getElementById('gm-stats').textContent = 'Loading...';
    document.getElementById('gm-tip').textContent = '';

    // Backend expects event.id (the evt_<hex>), not Neo4j elementId. Strip if needed.
    const id = String(eventNodeIdOrEventId || '');
    let target = id;
    if (id.includes(':')) {
      // neo4j elementId format "4:host:n" — fall back: just attempt as-is, backend will 404
      target = id;
    }

    try {
      const r = await fetch(`${window.CP.API_BASE}/graph/${encodeURIComponent(target)}?depth=2`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      render(data);
    } catch (e) {
      document.getElementById('gm-stats').textContent = `Graph unavailable: ${e.message}`;
    }
    // Also fetch SHAP feature contributions
    try {
      const r2 = await fetch(`${window.CP.API_BASE}/events/${encodeURIComponent(target)}/shap`);
      if (r2.ok) renderShap(await r2.json());
    } catch {}
  }

  function renderShap(data) {
    const svg = d3.select('#gm-shap');
    svg.selectAll('*').remove();
    const w = svg.node().clientWidth || 240;
    const h = 180;
    const margin = { top: 6, right: 10, bottom: 18, left: 80 };
    const innerW = w - margin.left - margin.right;
    const innerH = h - margin.top - margin.bottom;
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const contribs = data.contributions || [];
    // sort by abs shap_max
    contribs.sort((a, b) => Math.abs(b.shap_max) - Math.abs(a.shap_max));
    const xExtent = d3.extent([0, ...contribs.flatMap((c) => [c.shap_min, c.shap_max])]);
    const x = d3.scaleLinear().domain([Math.min(0, xExtent[0]), Math.max(0, xExtent[1])]).range([0, innerW]);
    const y = d3.scaleBand().domain(contribs.map((c) => c.name)).range([0, innerH]).padding(0.2);

    g.append('line').attr('x1', x(0)).attr('x2', x(0)).attr('y1', 0).attr('y2', innerH).attr('stroke', '#2A3A5C');

    g.selectAll('.bar-max')
      .data(contribs)
      .enter().append('rect')
      .attr('y', (d) => y(d.name))
      .attr('x', (d) => Math.min(x(0), x(d.shap_max)))
      .attr('width', (d) => Math.abs(x(d.shap_max) - x(0)))
      .attr('height', y.bandwidth())
      .attr('fill', (d) => d.shap_max > 0 ? '#F97316' : '#22C55E')
      .attr('opacity', 0.85);

    g.append('g')
      .call(d3.axisLeft(y).tickSize(0))
      .selectAll('text').attr('fill', '#8B9CC8').attr('font-size', 9);
    g.append('g').attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(x).ticks(3))
      .selectAll('text').attr('fill', '#4A5A82').attr('font-size', 8);
  }

  function close() {
    if (!modal) return;
    modal.classList.add('hidden');
    if (simulation) { simulation.stop(); simulation = null; }
  }

  function render(data) {
    const svg = document.getElementById('gm-svg');
    if (!svg || !window.d3) {
      document.getElementById('gm-stats').textContent =
        `${(data.nodes || []).length} nodes / ${(data.edges || []).length} edges (D3 not loaded)`;
      return;
    }
    const w = svg.clientWidth || 700;
    const h = svg.clientHeight || 460;
    const d3 = window.d3;
    const root = d3.select(svg);
    root.selectAll('*').remove();

    const nodes = (data.nodes || []).map((n) => ({
      id: n.id,
      labels: n.labels || [],
      props: n.props || {},
    }));
    const idIndex = new Map(nodes.map((n) => [n.id, n]));
    const links = (data.edges || [])
      .filter((e) => idIndex.has(e.from) && idIndex.has(e.to))
      .map((e) => ({ source: e.from, target: e.to, type: e.type }));

    document.getElementById('gm-stats').textContent =
      `${nodes.length} nodes · ${links.length} edges`;

    const g = root.append('g');
    root.call(d3.zoom().scaleExtent([0.25, 4]).on('zoom', (ev) => g.attr('transform', ev.transform)));

    const link = g.append('g')
      .attr('stroke', '#2A3A5C')
      .attr('stroke-opacity', 0.7)
      .selectAll('line')
      .data(links)
      .enter().append('line')
      .attr('stroke-width', 1.2);

    const linkLabel = g.append('g')
      .selectAll('text')
      .data(links)
      .enter().append('text')
      .text((d) => d.type)
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('font-size', 8)
      .attr('fill', '#4A5A82')
      .attr('text-anchor', 'middle');

    const node = g.append('g')
      .selectAll('circle')
      .data(nodes)
      .enter().append('circle')
      .attr('r', (d) => radiusFor(d.labels))
      .attr('fill', (d) => colorFor(d.labels))
      .attr('stroke', '#0A0E1A')
      .attr('stroke-width', 1.5)
      .style('cursor', 'pointer')
      .on('mouseover', (event, d) => {
        const p = d.props || {};
        const label = (d.labels || []).join(':') || '?';
        const name = p.name || p.title || p.id || d.id.slice(0, 12);
        let lines = [`<strong>${escapeHtml(label)}</strong>: ${escapeHtml(name)}`];
        if (p.country_code) lines.push(`Country: ${p.country_code}`);
        if (p.severity)     lines.push(`Severity: ${p.severity}`);
        if (p.type)         lines.push(`Type: ${p.type}`);
        if (p.delay_min_days != null) lines.push(`Delay: ${p.delay_min_days}–${p.delay_max_days}d`);
        document.getElementById('gm-tip').innerHTML = lines.join('<br/>');
      })
      .on('mouseout', () => document.getElementById('gm-tip').innerHTML = '')
      .call(d3.drag()
        .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y; })
        .on('end',   (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }));

    const labels = g.append('g')
      .selectAll('text')
      .data(nodes)
      .enter().append('text')
      .text((d) => {
        const p = d.props || {};
        return (p.name || p.title || (d.labels || ['?'])[0]).slice(0, 18);
      })
      .attr('font-family', 'Inter, sans-serif')
      .attr('font-size', 10)
      .attr('fill', '#E8EBF4')
      .attr('dx', 12)
      .attr('dy', 4);

    simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((d) => d.id).distance(80).strength(0.6))
      .force('charge', d3.forceManyBody().strength(-220))
      .force('center', d3.forceCenter(w / 2, h / 2))
      .force('collision', d3.forceCollide().radius(18))
      .on('tick', () => {
        link
          .attr('x1', (d) => d.source.x).attr('y1', (d) => d.source.y)
          .attr('x2', (d) => d.target.x).attr('y2', (d) => d.target.y);
        linkLabel
          .attr('x', (d) => (d.source.x + d.target.x) / 2)
          .attr('y', (d) => (d.source.y + d.target.y) / 2 - 2);
        node.attr('cx', (d) => d.x).attr('cy', (d) => d.y);
        labels.attr('x', (d) => d.x).attr('y', (d) => d.y);
      });
  }

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }

  return { open, close };
})();
