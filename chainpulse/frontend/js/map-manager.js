window.CPMap = (function () {
  let map = null;
  const markers = new Map(); // id → { marker, ttlTimer, fadeTimer }

  function init() {
    map = L.map('map-canvas', {
      center: [20, 10],
      zoom: 2,
      minZoom: 2,
      maxZoom: 7,
      zoomControl: false,
      attributionControl: true,
      worldCopyJump: false,
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      subdomains: 'abcd',
      maxZoom: 20,
      attribution: '© CARTO',
    }).addTo(map);

    L.control.zoom({ position: 'bottomleft' }).addTo(map);
  }

  function popupHTML(event) {
    const sev = (event.severity || 'low').toLowerCase();
    const type = (event.type || 'OTHER').replace(/_/g, ' ');
    const loc = event.location_name || event.country_code || 'Unknown';
    const ts = new Date(event.timestamp_utc || Date.now()).toISOString().replace('T', ' ').replace(/\..+/, ' UTC');
    const dMin = event.predicted_delay_min_days, dMax = event.predicted_delay_max_days;
    const delayLine = (dMin != null && dMax != null)
      ? `<div class="cp-popup__delay">${dMin}–${dMax} days delay</div>`
      : '';
    const skuCount = event.affected_sku_count || 0;
    const routes = event.affected_route_count || 0;

    return `
      <div class="cp-popup__row">
        <span class="cp-popup__badge cp-popup__badge--${sev}">${sev}</span>
        <span class="cp-popup__title">${type}</span>
      </div>
      <div class="cp-popup__sub">${loc}</div>
      <div class="cp-popup__sub mono">${ts}</div>
      <hr class="cp-popup__hr" />
      ${delayLine}
      <div class="cp-popup__metric">Affected routes: ${routes}</div>
      <div class="cp-popup__metric">SKUs at risk: ${skuCount}</div>
      ${event.source_url ? `<a class="cp-popup__btn" href="${event.source_url}" target="_blank" rel="noopener">🔗 Read original source</a>` : ''}
      ${event.neo4j_event_node_id ? `<button class="cp-popup__btn" onclick="window.CPModal && window.CPModal.open('${event.neo4j_event_node_id}')">◈ View supply chain graph</button>` : ''}
    `;
  }

  function typeAbbr(type) {
    return ({
      PORT_STRIKE: 'PORT',
      WEATHER_EVENT: 'WTHR',
      FACTORY_CLOSURE: 'FACT',
      SANCTIONS: 'SNCT',
      GEOPOLITICAL: 'GEO',
      LOGISTICS_DELAY: 'LOGI',
      OTHER: 'INFO',
    })[type] || 'INFO';
  }

  function buildIcon(event) {
    const sev = (event.severity || 'low').toLowerCase();
    const html = `
      <div class="cp-pin cp-pin--${sev}">
        <span class="cp-pin__pulse"></span>
        <span class="cp-pin__dot"></span>
        <span class="cp-pin__label">${typeAbbr(event.type)}</span>
      </div>`;
    return L.divIcon({ html, className: '', iconSize: [0, 0], iconAnchor: [0, 0] });
  }

  function add(event) {
    if (event.lat == null || event.lng == null) return;
    if (markers.has(event.id)) return;
    const marker = L.marker([event.lat, event.lng], { icon: buildIcon(event) }).addTo(map);
    marker.bindPopup(popupHTML(event), { maxWidth: 320 });

    const fadeT = setTimeout(() => {
      const el = marker.getElement();
      if (el) el.style.transition = 'opacity 60s linear';
      if (el) el.style.opacity = '0';
    }, window.CP.EVENT_FADE_START_MS);

    const ttlT = setTimeout(() => {
      map.removeLayer(marker);
      markers.delete(event.id);
    }, window.CP.EVENT_TTL_MS);

    markers.set(event.id, { marker, fadeT, ttlT });
  }

  function activeCount() { return markers.size; }

  function highlight(id) {
    const rec = markers.get(id);
    if (!rec) return;
    rec.marker.openPopup();
    map.flyTo(rec.marker.getLatLng(), Math.max(map.getZoom(), 4), { duration: 0.6 });
  }

  return { init, add, activeCount, highlight };
})();
