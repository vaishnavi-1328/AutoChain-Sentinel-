window.CPSidebar = (function () {
  const list = document.getElementById('sb-list');
  const pauseBtn = document.getElementById('sb-pause');
  const queueEl = document.getElementById('sb-queue');
  const regionSel = document.getElementById('sb-region');

  let paused = false;
  const queue = [];

  const REGION_MAP = {
    AP: new Set(['CN','HK','TW','JP','KR','SG','VN','TH','MY','ID','PH','IN','LK','AU','NZ']),
    EU: new Set(['DE','NL','BE','FR','GB','ES','GR','IT','PL','SE','NO','FI','DK']),
    AM: new Set(['US','CA','MX','BR','AR','CL','CO','PE']),
    ME: new Set(['EG','AE','SA','IL','IR','QA','KW','OM','TR']),
  };

  function passesFilter(event) {
    const f = regionSel.value;
    if (f === 'ALL') return true;
    const set = REGION_MAP[f] || new Set();
    return set.has((event.country_code || '').toUpperCase());
  }

  function render(event) {
    const sev = (event.severity || 'low').toLowerCase();
    const type = (event.type || 'OTHER').replace(/_/g, ' ');
    const li = document.createElement('li');
    li.className = `sb-item sb-item--${sev}`;
    const ts = new Date(event.timestamp_utc || Date.now()).toISOString().slice(11, 19) + ' UTC';
    li.innerHTML = `
      <div class="sb-item__row1">
        <span class="sb-dot sb-dot--${sev}"></span>
        <span class="sb-sev sb-sev--${sev}">${sev}</span>
        <span class="sb-type">${type}</span>
      </div>
      <div class="sb-loc">${event.location_name || event.country_code || 'Unknown'}</div>
      <div class="sb-head">${(event.title || '').slice(0, 160)}</div>
      <div class="sb-row2">
        <span class="sb-time">${ts}</span>
        <span class="sb-actions">
          ${event.source_url ? `<a class="sb-action" href="${event.source_url}" target="_blank" rel="noopener" title="Open source">↗</a>` : ''}
          ${event.id ? `<a class="sb-action" href="#" data-evt="${event.id}" title="Show on map">◎</a>` : ''}
          ${event.neo4j_event_node_id ? `<a class="sb-action" href="#" data-graph="${event.neo4j_event_node_id}" title="Graph">◈</a>` : ''}
        </span>
      </div>
    `;
    li.querySelectorAll('[data-evt]').forEach(a => a.addEventListener('click', (e) => {
      e.preventDefault();
      window.CPMap.highlight(a.dataset.evt);
    }));
    li.querySelectorAll('[data-graph]').forEach(a => a.addEventListener('click', (e) => {
      e.preventDefault();
      window.CPModal && window.CPModal.open(a.dataset.graph);
    }));
    list.insertBefore(li, list.firstChild);
    while (list.children.length > window.CP.SIDEBAR_MAX) list.removeChild(list.lastChild);
  }

  function add(event) {
    if (!passesFilter(event)) return;
    if (paused) {
      queue.push(event);
      queueEl.textContent = queue.length;
      return;
    }
    render(event);
  }

  pauseBtn.addEventListener('click', () => {
    paused = !paused;
    pauseBtn.firstChild.nodeValue = paused ? '▶' : '⏸';
    if (!paused && queue.length) {
      const drain = queue.splice(0);
      queueEl.textContent = '0';
      let i = 0;
      const next = () => {
        if (i >= drain.length) return;
        render(drain[i++]);
        setTimeout(next, 150);
      };
      next();
    }
  });

  regionSel.addEventListener('change', () => {
    // soft re-filter: future events filtered; existing list untouched.
  });

  return { add };
})();
