# ChainPulse — V2 Feature Prompt
## Add Personalized Supplier Delay Tracking

---

## Context

You are extending an existing supply chain intelligence dashboard. The app already has:
- A full-screen Leaflet.js world map with live disruption event pins (pulsing, severity-colored, 5-min TTL fade)
- A right sidebar (20vw) showing a live news feed with clickable `[Source ↗]` links
- A WebSocket connection pushing real-time disruption events from the backend
- A bottom bar with a scrolling delay ticker and stat chips
- A FastAPI backend with Kafka, PostgreSQL, Neo4j, Redis, and an NLP pipeline
- The Guardian API (`8b5963f9-03cd-416b-99cd-bb8ad51872a5`) as the primary news source

**Do not change any of the above.** Only add what is described below.

---

## The Problem You Are Solving

Right now the app shows generic global disruptions. A manufacturing company looking at the dashboard sees "Port strike in Shanghai — 8–14 day delay" but has no idea if that affects *their* orders. They need to know: **"My supplier Shenzhen Electronics Co. is 300km from that port — my capacitor order due July 12 is now delayed by 11 days."**

---

## What to Build

Three things, in this order:

### 1. Orders Database Table (backend first)

Add this table to PostgreSQL:

```sql
CREATE TABLE orders (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID REFERENCES users(id) ON DELETE CASCADE,
  supplier_name     TEXT NOT NULL,
  supplier_city     TEXT NOT NULL,
  supplier_country  CHAR(2) NOT NULL,
  supplier_lat      DOUBLE PRECISION NOT NULL,
  supplier_lng      DOUBLE PRECISION NOT NULL,
  materials         TEXT NOT NULL,
  quantity          NUMERIC,
  quantity_unit     TEXT,
  expected_delivery DATE NOT NULL,
  po_reference      TEXT,
  shipping_mode     TEXT DEFAULT 'Sea freight',
  notes             TEXT,
  status            TEXT NOT NULL DEFAULT 'ON_SCHEDULE',
  delay_min_days    INT NOT NULL DEFAULT 0,
  delay_max_days    INT NOT NULL DEFAULT 0,
  new_eta_earliest  DATE,
  new_eta_latest    DATE,
  created_at        TIMESTAMPTZ DEFAULT now(),
  updated_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE order_event_impacts (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id                UUID REFERENCES orders(id) ON DELETE CASCADE,
  event_id                UUID REFERENCES events(id),
  distance_km             NUMERIC(8,2),
  delay_contribution_days INT,
  recorded_at             TIMESTAMPTZ DEFAULT now()
);
```

---

### 2. Four Backend Endpoints

#### `GET /suppliers/geo-resolve`
```python
# Query params: city (str), country (str)
# Call GeoNames API to turn city+country into lat/lng
# Return: { lat, lng, resolved_name }
# If GeoNames fails, fall back to port_gazetteer.json lookup
```

#### `POST /orders`
```python
# Body: supplier_name, city, country_code, lat, lng, materials,
#       quantity, quantity_unit, expected_delivery, po_reference,
#       shipping_mode, notes
# 1. Save to orders table
# 2. Run delay analysis against all Redis-cached active events (see logic below)
# 3. Update orders table with status + delay_min/max + new_eta
# 4. Insert order_event_impacts rows for each matched event
# Return: full order object + matched_events array + overlap_adjustment_days
```

#### `GET /orders`
```python
# Return all orders for authenticated user, ordered by status severity:
# CRITICAL_DELAY → DELAY_RISK → MONITOR → ON_SCHEDULE → DELIVERED
```

#### `GET /orders/{order_id}/analysis`
```python
# Return order + all matched events with:
#   source_url, source_name, severity, distance_km,
#   delay_contribution_days, timestamp_utc
# Also return overlap_adjustment_days and chart_data array for D3
```

---

### 3. Delay Calculation Logic

Put this in `services/delay_engine.py`. Call it from `POST /orders` and from the Kafka consumer whenever a new event is processed.

```python
from geopy.distance import geodesic

PROXIMITY_KM = 800    # candidate if supplier is within this distance of event
ROUTE_BUFFER_KM = 120 # candidate if event is within this of the shipping lane

SHIPPING_MODE_FACTORS = {
    "Sea freight":  1.00,
    "Multimodal":   0.85,
    "Rail":         0.60,
    "Road":         0.50,
    "Air freight":  0.15,   # largely immune to port strikes
}

def distance_factor(km):
    if km < 200:  return 1.00
    if km < 500:  return 0.85
    if km < 800:  return 0.60
    return 0.40

def derive_status(delay_min, severity):
    if delay_min >= 14 or severity == "critical": return "CRITICAL_DELAY"
    if delay_min >= 3:  return "DELAY_RISK"
    if delay_min >= 1:  return "MONITOR"
    return "ON_SCHEDULE"

def analyse_order(order, active_events):
    """
    active_events: list of processed event dicts from Redis cache
    Each event has: lat, lng, delay_min_days, delay_max_days, severity, id, source_url, source_name, title
    """
    matched = []

    for event in active_events:
        dist = geodesic((event["lat"], event["lng"]),
                        (order.supplier_lat, order.supplier_lng)).km

        if dist > PROXIMITY_KM:
            continue  # skip (add route-intersection check later as enhancement)

        df = distance_factor(dist)
        mf = SHIPPING_MODE_FACTORS.get(order.shipping_mode, 1.0)

        contrib_min = round(event["delay_min_days"] * df * mf)
        contrib_max = round(event["delay_max_days"] * df * mf)

        if contrib_min > 0:
            matched.append({
                "event_id":               event["id"],
                "title":                  event["title"],
                "source_url":             event["source_url"],
                "source_name":            event["source_name"],
                "severity":               event["severity"],
                "distance_km":            round(dist, 1),
                "delay_contribution_days": contrib_min,
                "delay_contribution_max":  contrib_max,
            })

    if not matched:
        return { "status": "ON_SCHEDULE", "delay_min": 0, "delay_max": 0,
                 "matched": [], "overlap_adjustment_days": 0 }

    # Sort by contribution descending
    matched.sort(key=lambda m: m["delay_contribution_days"], reverse=True)

    # Aggregate: full credit for biggest event, 50% for each additional
    # (concurrent events overlap in time — they are not additive)
    total_min = matched[0]["delay_contribution_days"]
    total_max = matched[0]["delay_contribution_max"]
    overlap_adj = 0
    for m in matched[1:]:
        add_min = round(m["delay_contribution_days"] * 0.5)
        add_max = round(m["delay_contribution_max"] * 0.5)
        overlap_adj -= round(m["delay_contribution_days"] * 0.5)
        total_min += add_min
        total_max += add_max

    from datetime import timedelta
    new_eta_min = order.expected_delivery + timedelta(days=total_min)
    new_eta_max = order.expected_delivery + timedelta(days=total_max)

    return {
        "status":                  derive_status(total_min, matched[0]["severity"]),
        "delay_min":               total_min,
        "delay_max":               total_max,
        "new_eta_earliest":        new_eta_min.isoformat(),
        "new_eta_latest":          new_eta_max.isoformat(),
        "overlap_adjustment_days": overlap_adj,
        "matched":                 matched,
    }
```

**Also wire this into the Kafka consumer:** after writing each processed event to Redis, loop through all active orders, call `analyse_order`, update the orders table, and publish an `order_delay_update` message to Redis pub/sub so the WebSocket broadcasts it to the correct user.

---

## WebSocket — New Message Type

The existing `{ msg_type: "event", ... }` messages are unchanged.

Add a second message type the backend publishes when an order's delay status changes:

```json
{
  "msg_type": "order_delay_update",
  "order_id": "ord_8bc21d",
  "supplier_name": "Shenzhen Electronics Co.",
  "supplier_lat": 22.5431,
  "supplier_lng": 114.0579,
  "status": "DELAY_RISK",
  "delay_min_days": 9,
  "delay_max_days": 14,
  "original_eta": "2025-07-12",
  "new_eta_earliest": "2025-07-21",
  "new_eta_latest": "2025-07-26",
  "matched_events": [
    {
      "event_id": "evt_3f8a1c",
      "title": "Port of Shenzhen partial closure",
      "source_url": "https://www.theguardian.com/...",
      "source_name": "The Guardian",
      "severity": "high",
      "distance_km": 298,
      "delay_contribution_days": 11
    }
  ],
  "overlap_adjustment_days": -2
}
```

---

## Frontend Changes

Keep everything. Add three things:

### A. Sidebar tab bar

Replace the sidebar header with two tabs:

```
┌──────────────────────────────────────┐
│  [ NEWS FEED ]    [ MY ORDERS (3⚡) ]│  36px
└──────────────────────────────────────┘
```

- Each tab is 50% width
- Active tab: `background: #1C2540`, `border-bottom: 2px solid #3B5BDB`, `color: #E8EBF4`
- Inactive tab: `background: #151D35`, `color: #4A5A82`
- Badge `(3⚡)` = count of at-risk orders, color `#F97316`
- The content area below switches between news list and orders list

The news feed content is exactly as it was — just now lives under the `NEWS FEED` tab.

---

### B. My Orders tab content

On load: call `GET /orders` and render one card per order. On WebSocket `order_delay_update`: update the matching card in-place (do not re-render the list).

**Order card HTML structure:**

```html
<div class="order-card" data-order-id="{{order_id}}" data-status="{{status}}">

  <!-- Header row -->
  <div class="order-card-header">
    <span class="status-badge status-{{status}}">{{status_label}}</span>
    <div class="order-actions">
      <button onclick="openEditDrawer('{{order_id}}')">Edit</button>
      <button onclick="deleteOrder('{{order_id}}')">✕</button>
    </div>
  </div>

  <!-- Supplier info -->
  <div class="order-supplier-name">{{supplier_name}}</div>
  <div class="order-supplier-location">{{supplier_city}}, {{supplier_country}}</div>

  <!-- Order details -->
  <div class="order-details">
    <span class="label">Material</span>  <span>{{materials}}</span>
    <span class="label">Qty</span>       <span>{{quantity}} {{quantity_unit}}</span>
    <span class="label">Expected</span>  <span>{{expected_delivery}}</span>
  </div>

  <!-- Delay estimate — this is the core value -->
  <div class="order-delay-block">
    <div class="delay-label">ESTIMATED DELAY</div>
    <div class="delay-value">+{{delay_min_days}} to +{{delay_max_days}} days</div>
    <div class="new-eta">New ETA: {{new_eta_earliest}} → {{new_eta_latest}}</div>
  </div>

  <!-- What caused the delay — every item must have a source link -->
  <div class="order-causes">
    <div class="causes-label">Driven by:</div>
    {{#each matched_events}}
    <div class="cause-item">
      · {{title}}
      <a href="{{source_url}}" target="_blank" rel="noopener">[{{source_name}} ↗]</a>
      <span class="cause-date">{{timestamp_utc | date}}</span>
    </div>
    {{/each}}
  </div>

  <!-- Actions -->
  <div class="order-card-actions">
    <button onclick="flyToSupplier('{{order_id}}', {{supplier_lat}}, {{supplier_lng}})">
      📍 Show on map
    </button>
    <button onclick="openDelayModal('{{order_id}}')">
      📊 Full analysis
    </button>
  </div>

</div>
```

**Status badge text and colors:**

| `status` value | Badge text | Color |
|---|---|---|
| `CRITICAL_DELAY` | 🔴 Critical delay | `#EF4444` |
| `DELAY_RISK` | ⚠ Delay risk | `#F97316` |
| `MONITOR` | ~ Monitor | `#EAB308` |
| `ON_SCHEDULE` | ✓ On schedule | `#10B981` |
| `DELIVERED` | ✓ Delivered | `#4A5A82` |

**`delay-value` styling:**
```css
.delay-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 18px;
  color: var(--status-color);   /* match the badge color */
}
/* ON_SCHEDULE shows "+0 days" in #10B981 */
```

Card sort order: CRITICAL_DELAY first, then DELAY_RISK, MONITOR, ON_SCHEDULE, DELIVERED last.

---

### C. Order Entry Drawer

A panel that slides in from the left over the map. Open it with a floating button fixed to the bottom-left of the map area.

**Trigger button:**
```html
<button id="add-order-fab" onclick="openOrderDrawer()">
  + Add Order
</button>
```
```css
#add-order-fab {
  position: absolute;
  bottom: 64px;    /* above bottom bar */
  left: 16px;
  z-index: 1000;
  background: #3B82F6;
  color: white;
  border: none;
  border-radius: 24px;
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
```

**Drawer:**
```css
#order-drawer {
  position: fixed;
  top: 0; left: 0;
  width: 420px;
  height: 100vh;
  background: #0F1629;
  border-right: 1px solid #2A3A5C;
  z-index: 2000;
  transform: translateX(-420px);
  transition: transform 250ms cubic-bezier(0.4, 0, 0.2, 1);
  overflow-y: auto;
}
#order-drawer.open {
  transform: translateX(0);
}
#drawer-overlay {
  position: fixed; inset: 0;
  background: rgba(10,14,26,0.72);
  z-index: 1999;
  display: none;
}
#drawer-overlay.open { display: block; }
```

**Form fields inside the drawer** (in order, all required unless marked optional):

```
Supplier company name *
  <input type="text" placeholder="e.g. Tata Steel, Foxconn, COSCO">

Supplier city *
  <input type="text" id="supplier-city" placeholder="e.g. Shenzhen, Mumbai">
  (on blur: call GET /suppliers/geo-resolve, show mini Leaflet map on success)

Supplier country *
  <select> — full ISO country list </select>

Materials ordered *
  <textarea rows="3" placeholder="e.g. Capacitors 100nF, Steel coil Grade-B">

Quantity  (optional)
  <input type="number">  <select> units | kg | tonnes | containers </select>

Expected delivery date *
  <input type="date" min="today">

PO reference  (optional)
  <input type="text" placeholder="PO-2025-0441">

Shipping mode
  <select> Sea freight | Air freight | Rail | Road | Multimodal </select>
  (default: Sea freight — affects delay calculation)

Notes  (optional)
  <textarea rows="2" placeholder="Any additional context...">
```

**Geo-resolve behavior:**
When `supplier-city` loses focus AND `supplier-country` has a value:
1. Call `GET /suppliers/geo-resolve?city=...&country=...`
2. Show a 150px tall mini Leaflet map below the country field with a pin at the returned coordinates
3. Store `lat` and `lng` as hidden field values for the POST body
4. If the call fails, show two manual inputs: `Latitude` / `Longitude`

**Drawer footer buttons:**
```html
<button onclick="closeOrderDrawer()">Cancel</button>
<button id="save-order-btn" onclick="submitOrder()">Analyse & Save →</button>
```

`submitOrder()` flow:
1. Validate required fields — show inline error below each failing field
2. `POST /orders` with all form data
3. On success:
   - Close drawer
   - Switch sidebar to My Orders tab
   - Prepend the new order card (sorted by status)
   - Drop a diamond marker on the map at `(lat, lng)` — see map section below
   - Show a toast if delay was detected: `"⚠ Delay detected: +N to +M days for [supplier]"`
4. On API error: show error message below the Save button

---

### D. Map — Supplier Diamond Markers

When an order is saved (or on page load from `GET /orders`), add a marker to the `supplierLayer` Leaflet layer group:

```javascript
function addSupplierMarker(order) {
  const icon = L.divIcon({
    className: '',
    html: `<div class="supplier-diamond" data-status="${order.status}">
             <span class="supplier-label">${order.supplier_name.slice(0,6)}</span>
           </div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
  const marker = L.marker([order.supplier_lat, order.supplier_lng], { icon })
    .addTo(supplierLayer);
  marker.bindPopup(buildSupplierPopup(order));
  supplierMarkers[order.order_id] = marker;
}
```

```css
.supplier-diamond {
  width: 12px; height: 12px;
  transform: rotate(45deg);
  border: 1.5px solid #2A3A5C;
  cursor: pointer;
}
/* Color by status */
[data-status="ON_SCHEDULE"]   { background: #10B981; }
[data-status="MONITOR"]       { background: #EAB308; }
[data-status="DELAY_RISK"]    { background: #F97316; }
[data-status="CRITICAL_DELAY"]{ background: #EF4444; }

.supplier-label {
  transform: rotate(-45deg);
  font-family: 'JetBrains Mono', monospace;
  font-size: 8px;
  color: #E8EBF4;
  position: absolute;
  top: 14px; left: -4px;
  white-space: nowrap;
}
```

Supplier popup content:
```
Supplier name
City, Country
──────────────────
Material: ...
Qty: ... units
Expected: ...
──────────────────
Status: ⚠ DELAY RISK
Est. delay: +9 to +14 days
Driven by: Port of Shenzhen closure (The Guardian)
──────────────────
[📊 Full analysis]
```

On `order_delay_update` WebSocket message: update `supplierMarkers[order_id]` icon color by changing the `data-status` attribute.

---

### E. WebSocket handler addition

```javascript
// Existing handler (unchanged):
if (payload.msg_type === 'event') {
  addEventPin(payload);
  addSidebarNewsItem(payload);
  updateStatsBar(payload);
  updateTicker(payload);
}

// Add this:
if (payload.msg_type === 'order_delay_update') {
  updateOrderCard(payload);        // update card values in-place by data-order-id
  updateSupplierMarker(payload);   // change diamond color
  updateOrdersAtRiskChip(payload); // update "MY ORDERS AT RISK" chip in bottom bar
  if (payload.status !== 'ON_SCHEDULE') {
    showToast(`⚠ ${payload.supplier_name}: +${payload.delay_min_days}–${payload.delay_max_days}d delay`, 4000);
  }
}
```

---

### F. Bottom bar — one new chip

Add to the right-side stat chips:

```
MY ORDERS AT RISK    3 / 7
```

Format: `affected count / total count`. Color `#F97316`. Same chip styling as existing chips.
Clicking this chip switches the sidebar to the My Orders tab.

---

## What NOT to Change

- The world map, event pins, TTL fade, and pin popups — unchanged
- The news feed tab content and card structure — unchanged
- The WebSocket `event` message type and its handlers — unchanged
- The title bar — unchanged (you may add an order alert badge if you want, it is not required)
- The bottom delay ticker — unchanged
- The existing stat chips — unchanged (only add the new one)
- All existing API endpoints — unchanged
- The NLP pipeline, Kafka, Neo4j graph modal — unchanged

---

## Acceptance Criteria

Every delay estimate shown to a user must:
1. Show a specific number: `+9 to +14 days` — not "some delay" or "affected"
2. Show the new ETA dates: `New ETA: Jul 21 → Jul 26`
3. Link to at least one real news article that caused the delay — `[The Guardian ↗]`
4. Update automatically (without page refresh) when new news arrives via WebSocket
An order with no active disruptions nearby must show `+0 days` and `✓ On schedule` clearly.