window.CPOrderDrawer = (function () {
  const COUNTRIES = [
    ['CN','China'],['HK','Hong Kong'],['TW','Taiwan'],['JP','Japan'],['KR','South Korea'],
    ['SG','Singapore'],['VN','Vietnam'],['TH','Thailand'],['MY','Malaysia'],['ID','Indonesia'],
    ['IN','India'],['LK','Sri Lanka'],['PH','Philippines'],
    ['DE','Germany'],['NL','Netherlands'],['BE','Belgium'],['FR','France'],['GB','United Kingdom'],
    ['ES','Spain'],['IT','Italy'],['GR','Greece'],['PL','Poland'],['SE','Sweden'],
    ['US','United States'],['CA','Canada'],['MX','Mexico'],['BR','Brazil'],['AR','Argentina'],
    ['EG','Egypt'],['AE','United Arab Emirates'],['SA','Saudi Arabia'],['IL','Israel'],
    ['TR','Turkey'],['ZA','South Africa'],['AU','Australia'],['NZ','New Zealand'],
  ];

  let drawer = null, overlay = null, fab = null, miniMap = null, miniMarker = null;
  let editingId = null;
  let built = false;

  function build() {
    if (built) return;
    drawer = document.getElementById('order-drawer');
    overlay = document.getElementById('drawer-overlay');

    drawer.innerHTML = `
      <div class="drawer-header">+ Add Supplier Order</div>
      <form class="drawer-form" id="order-form" onsubmit="return false;">
        <div class="field">
          <label>Supplier company name *</label>
          <input type="text" name="supplier_name" required placeholder="e.g. Foxconn, Tata Steel">
        </div>
        <div class="drawer-row">
          <div class="field">
            <label>Supplier city *</label>
            <input type="text" name="supplier_city" id="supplier-city" required placeholder="Shenzhen">
          </div>
          <div class="field">
            <label>Country *</label>
            <select name="supplier_country" id="supplier-country" required>
              <option value="">—</option>
              ${COUNTRIES.map(([code, name]) => `<option value="${code}">${name}</option>`).join('')}
            </select>
          </div>
        </div>
        <div id="mini-map" class="mini-map" style="display:none"></div>
        <div class="drawer-row" id="manual-latlng" style="display:none">
          <div class="field"><label>Latitude</label><input type="number" step="any" name="supplier_lat"></div>
          <div class="field"><label>Longitude</label><input type="number" step="any" name="supplier_lng"></div>
        </div>
        <input type="hidden" name="hidden_lat" id="hidden-lat">
        <input type="hidden" name="hidden_lng" id="hidden-lng">

        <div class="field">
          <label>Materials ordered *</label>
          <textarea name="materials" rows="2" required placeholder="e.g. Capacitors 100nF, Steel coil Grade-B"></textarea>
        </div>
        <div class="drawer-row">
          <div class="field"><label>Quantity</label><input type="number" name="quantity" step="any"></div>
          <div class="field">
            <label>Unit</label>
            <select name="quantity_unit">
              <option>units</option><option>kg</option><option>tonnes</option><option>containers</option>
            </select>
          </div>
        </div>
        <div class="field">
          <label>Expected delivery date *</label>
          <input type="date" name="expected_delivery" required>
        </div>
        <div class="field">
          <label>PO reference</label>
          <input type="text" name="po_reference" placeholder="PO-2026-0441">
        </div>
        <div class="field">
          <label>Shipping mode</label>
          <select name="shipping_mode">
            <option>Sea freight</option><option>Air freight</option>
            <option>Rail</option><option>Road</option><option>Multimodal</option>
          </select>
        </div>
        <div class="field">
          <label>Notes</label>
          <textarea name="notes" rows="2"></textarea>
        </div>
        <div id="form-error" class="field-error"></div>
        <div class="drawer-actions">
          <button type="button" class="btn-cancel" onclick="window.CPOrderDrawer.close()">Cancel</button>
          <button type="button" class="btn-save" onclick="window.CPOrderDrawer.submit()">Analyse &amp; Save →</button>
        </div>
      </form>
    `;
    document.getElementById('supplier-city').addEventListener('blur', onGeoBlur);
    document.getElementById('supplier-country').addEventListener('change', onGeoBlur);
    overlay.addEventListener('click', close);
    built = true;
  }

  function wireFab() {
    fab = document.getElementById('add-order-fab');
    if (fab) fab.addEventListener('click', () => open());
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireFab);
  } else {
    wireFab();
  }

  async function onGeoBlur() {
    const city = document.getElementById('supplier-city').value.trim();
    const country = document.getElementById('supplier-country').value;
    if (!city || !country) return;
    try {
      const r = await fetch(`${window.CP.API_BASE}/suppliers/geo-resolve?city=${encodeURIComponent(city)}&country=${country}`);
      if (!r.ok) throw new Error('geo-resolve failed');
      const { lat, lng, resolved_name } = await r.json();
      document.getElementById('hidden-lat').value = lat;
      document.getElementById('hidden-lng').value = lng;
      document.getElementById('manual-latlng').style.display = 'none';
      showMiniMap(lat, lng, resolved_name);
    } catch (e) {
      document.getElementById('mini-map').style.display = 'none';
      document.getElementById('manual-latlng').style.display = 'flex';
    }
  }

  function showMiniMap(lat, lng, label) {
    const el = document.getElementById('mini-map');
    el.style.display = 'block';
    if (!miniMap) {
      miniMap = L.map('mini-map', { zoomControl: false, attributionControl: false }).setView([lat, lng], 5);
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { subdomains: 'abcd' }).addTo(miniMap);
    } else {
      miniMap.setView([lat, lng], 5);
    }
    setTimeout(() => miniMap.invalidateSize(), 50);
    if (miniMarker) miniMarker.remove();
    miniMarker = L.marker([lat, lng]).addTo(miniMap).bindPopup(label).openPopup();
  }

  function open() {
    build();
    editingId = null;
    drawer.classList.add('open');
    overlay.classList.add('open');
  }

  function openForEdit(orderId) {
    open();
    editingId = orderId;
    const o = window.CPOrders.get(orderId);
    if (!o) return;
    const f = document.getElementById('order-form');
    f.supplier_name.value = o.supplier_name || '';
    f.supplier_city.value = o.supplier_city || '';
    f.supplier_country.value = o.supplier_country || '';
    f.materials.value = o.materials || '';
    f.quantity.value = o.quantity ?? '';
    f.quantity_unit.value = o.quantity_unit || 'units';
    f.expected_delivery.value = o.expected_delivery || '';
    f.po_reference.value = o.po_reference || '';
    f.shipping_mode.value = o.shipping_mode || 'Sea freight';
    f.notes.value = o.notes || '';
    document.getElementById('hidden-lat').value = o.supplier_lat;
    document.getElementById('hidden-lng').value = o.supplier_lng;
    showMiniMap(o.supplier_lat, o.supplier_lng, o.supplier_name);
  }

  function close() {
    if (drawer) drawer.classList.remove('open');
    if (overlay) overlay.classList.remove('open');
  }

  function readForm() {
    const f = document.getElementById('order-form');
    const lat = parseFloat(document.getElementById('hidden-lat').value || f.supplier_lat?.value);
    const lng = parseFloat(document.getElementById('hidden-lng').value || f.supplier_lng?.value);
    if (!f.supplier_name.value || !f.supplier_city.value || !f.supplier_country.value
        || !f.materials.value || !f.expected_delivery.value
        || Number.isNaN(lat) || Number.isNaN(lng)) {
      throw new Error('Fill all required fields and resolve city to lat/lng');
    }
    return {
      supplier_name:     f.supplier_name.value.trim(),
      supplier_city:     f.supplier_city.value.trim(),
      supplier_country:  f.supplier_country.value,
      supplier_lat:      lat,
      supplier_lng:      lng,
      materials:         f.materials.value.trim(),
      quantity:          f.quantity.value ? parseFloat(f.quantity.value) : null,
      quantity_unit:     f.quantity_unit.value || null,
      expected_delivery: f.expected_delivery.value,
      po_reference:      f.po_reference.value || null,
      shipping_mode:     f.shipping_mode.value,
      notes:             f.notes.value || null,
    };
  }

  async function submit() {
    const errEl = document.getElementById('form-error');
    errEl.textContent = '';
    let body;
    try { body = readForm(); } catch (e) { errEl.textContent = e.message; return; }

    const tok = localStorage.getItem('cp_token');
    if (!tok) {
      errEl.innerHTML = 'Please sign in first → <a href="./onboarding.html" style="color:var(--accent-cyan)">/onboarding</a>';
      return;
    }
    const r = await fetch(`${window.CP.API_BASE}/orders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tok}` },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const t = await r.text();
      errEl.textContent = `Save failed: ${t.slice(0, 160)}`;
      return;
    }
    const payload = await r.json();
    const order = payload.order;
    order.matched_events = payload.matched_events;

    close();
    if (window.CPTabs) window.CPTabs.activate('orders');
    window.CPOrders.add(order);
    if (window.CPMap && window.CPMap.addSupplier) window.CPMap.addSupplier(order);
    if (window.CPToast && order.delay_min_days > 0) {
      window.CPToast.show(`⚠ Delay detected: +${order.delay_min_days}–${order.delay_max_days}d for ${order.supplier_name}`);
    }
  }

  return { open, openForEdit, close, submit };
})();
