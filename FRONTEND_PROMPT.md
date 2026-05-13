# Frontend Build Prompt — Supply Chain Intelligence Dashboard

## Project Context

You are building the frontend for **ChainPulse**, a real-time supply chain intelligence dashboard used by supply chain engineers and procurement managers. The interface must be professional, data-dense, and technically credible — comparable to Bloomberg Terminal or Palantir Gotham in visual authority.

There is **no user input on this screen**. All data is driven by a WebSocket connection to the backend. The only time user input is collected is during the one-time account onboarding flow (separate page). This dashboard is a **read-only operational display**.

---

## Tech Stack

- **HTML5** — semantic structure
- **Tailwind CSS** (via CDN) — utility-first layout and spacing
- **Vanilla JavaScript (ES6+)** — WebSocket handling, DOM manipulation, map interaction
- **Leaflet.js** — interactive world map
- **D3.js** — graph visualizations and supplementary charts
- **neovis.js** — Neo4j knowledge graph rendering in the modal panel
- **Font**: Inter (Google Fonts) for UI chrome, JetBrains Mono for data/code elements

Do **not** use React, Vue, or any SPA framework. Do **not** use Streamlit or any Python UI framework.

---

## Color Palette & Design Tokens

```css
:root {
  --bg-primary:     #0A0E1A;   /* deep navy — main background */
  --bg-secondary:   #0F1629;   /* slightly lighter — panels */
  --bg-tertiary:    #151D35;   /* cards and drawers */
  --bg-elevated:    #1C2540;   /* elevated surfaces, modal bg */

  --border-subtle:  #1E2A45;   /* hairline panel borders */
  --border-default: #2A3A5C;   /* component borders */
  --border-active:  #3B5BDB;   /* focused/selected */

  --accent-blue:    #3B82F6;   /* primary interactive */
  --accent-cyan:    #06B6D4;   /* data highlights */
  --accent-indigo:  #6366F1;   /* secondary accent */

  --severity-critical: #EF4444;  /* red    — critical event */
  --severity-high:     #F97316;  /* orange — high severity */
  --severity-medium:   #EAB308;  /* yellow — medium severity */
  --severity-low:      #22C55E;  /* green  — low / informational */

  --text-primary:   #E8EBF4;
  --text-secondary: #8B9CC8;
  --text-muted:     #4A5A82;
  --text-data:      #06B6D4;   /* monospace data values */

  --map-pin-pulse-critical: rgba(239, 68, 68, 0.4);
  --map-pin-pulse-high:     rgba(249, 115, 22, 0.35);
  --map-pin-pulse-medium:   rgba(234, 179, 8, 0.3);
}
```

---

## Page Layout — Single Page, No Scroll

The entire viewport is the dashboard. No vertical scroll on the outer container. Layout is fixed at `100vw × 100vh`.

```
┌─────────────────────────────────────────────────────────────────────┐
│  TITLE BAR                                              [status bar] │  ← 52px
├─────────────────────────────────────────────────────────────────────┤
│                                                   │                  │
│                                                   │   NEWS LOG       │
│              WORLD MAP                            │   SIDEBAR        │
│              (Leaflet.js)                         │   (20% width)    │
│              80% width                            │                  │
│                                                   │                  │
│                                                   │                  │
├────────────────────────────┬──────────────────────┤                  │
│  DELAY IMPACT TICKER       │  ACTIVE EVENT COUNT  │                  │
│  (scrolling bottom bar)    │  STATS STRIP         │                  │  ← 48px
└─────────────────────────────────────────────────────────────────────┘
```

### Exact proportions

| Region | Width | Height |
|---|---|---|
| Title bar | 100% | 52px |
| Map canvas | 80vw | calc(100vh - 52px - 48px) |
| News log sidebar | 20vw | calc(100vh - 52px - 48px) |
| Bottom stats bar | 100% | 48px |

---

## Component 1 — Title Bar

**Height:** 52px  
**Background:** `var(--bg-secondary)` with a 1px bottom border in `var(--border-subtle)`  
**Layout:** flex row, items-center, justify-between, px-5

### Left section
- Logo mark: a small SVG hexagon icon in `--accent-cyan` (16×16px)
- Product name: `CHAINPULSE` in Inter 13px, font-weight 600, letter-spacing 0.12em, color `--text-primary`
- Version tag: `v1.0` in a small pill — `--bg-tertiary` background, `--text-muted` text, 10px font, border `--border-default`
- Separator: 1px vertical line `--border-subtle`, height 20px, mx-4
- Page label: `SUPPLY CHAIN INTELLIGENCE` in 11px, font-weight 500, letter-spacing 0.08em, color `--text-secondary`

### Center section
- Live clock: current UTC time in `JetBrains Mono` 13px, `--text-data` color, updated every second
- Format: `2025-06-14  14:32:07 UTC`

### Right section
- **WebSocket status indicator**: a 8px dot, animated pulse when connected (green `--severity-low`), static red when disconnected
- Text next to dot: `LIVE` or `RECONNECTING` in 11px caps, `--text-secondary`
- Separator
- **Event counter badge**: shows total events processed in current session. Format: `847 EVENTS` — `--accent-cyan` text, `--bg-tertiary` bg, border `--border-default`, rounded-full, px-3 py-1, 11px mono font
- Separator
- **User profile avatar**: 28px circle, initials, `--accent-indigo` background. Clicking opens account profile drawer (separate overlay).

---

## Component 2 — World Map (Leaflet.js)

### Map initialization

```javascript
const map = L.map('map-canvas', {
  center: [20, 10],
  zoom: 2.5,
  minZoom: 2,
  maxZoom: 7,
  zoomControl: false,
  attributionControl: false,
  worldCopyJump: false
});
```

### Tile layer

Use **CartoDB Dark Matter** tiles for the dark base map:

```javascript
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  subdomains: 'abcd',
  maxZoom: 20
}).addTo(map);
```

Add a custom attribution string bottom-right in 9px muted text.

### Custom map controls

Place zoom controls in the **bottom-left** of the map, styled to match the dark theme:
- `+` / `−` buttons: `--bg-elevated` background, `--border-default` border, `--text-primary` text, 32×32px
- Add a **"Fit World"** button below zoom: globe icon, same styling, resets to initial center/zoom

### Event pins (custom Leaflet markers)

Each supply chain event renders as a **pulsing circular pin**:

```javascript
// Pin structure (created via L.divIcon)
// Outer ring: animated CSS pulse expanding from center
// Inner dot: solid filled circle, color = severity color
// Label: event type abbreviation below dot (PORT, WEATHER, STRIKE, etc.)
```

Pin sizes by severity:

| Severity | Inner dot | Outer pulse max size | Pulse duration |
|---|---|---|---|
| Critical | 14px | 40px | 1.2s |
| High | 12px | 34px | 1.6s |
| Medium | 10px | 28px | 2.0s |
| Low | 8px | 22px | 2.5s |

**Fade-out behavior**: Each pin appears with a CSS `opacity` transition from 0 → 1 over 600ms. The pin's TTL is 5 minutes (300 seconds). At 240 seconds, begin a linear opacity fade from 1 → 0 over 60 seconds, then `map.removeLayer(marker)`.

```javascript
function addEventPin(event) {
  const marker = createStyledMarker(event);
  marker.addTo(map);
  marker.fadeInAnimation();

  // Schedule fade-out
  setTimeout(() => marker.beginFade(), 240000);
  setTimeout(() => map.removeLayer(marker), 300000);
}
```

### Popup on pin click

Clicking a pin opens a Leaflet popup with custom HTML content. The popup should be **320px wide**, dark themed (`--bg-elevated` background), with the following sections:

```
┌─────────────────────────────────────────┐
│  [CRITICAL]  Port Strike                │  ← severity badge + event type
│  Port of Shanghai · China               │  ← location
│  14 Jun 2025 · 09:41 UTC                │  ← timestamp
├─────────────────────────────────────────┤
│  Predicted delay: 8–14 days             │  ← delay estimate (bold, cyan)
│  Affected routes: 12 shipping lanes     │
│  SKUs at risk: 47 in your profile       │  ← personalised from user account
├─────────────────────────────────────────┤
│  [🔗 Read original source]              │  ← external link to news article
│  [◈ View supply chain graph]            │  ← opens Neo4j graph modal
└─────────────────────────────────────────┘
```

Styling: popup uses `--bg-elevated`, `--border-default` border, `--text-primary` text. Severity badge is a pill using the severity color. Delay estimate in `--accent-cyan`, `JetBrains Mono` 14px. Both action buttons are full-width, `--bg-tertiary` background, hover `--border-active` border.

### Shipping lane overlays

Render the top 20 major global shipping lanes as **thin polylines** (`#2A3A5C`, 0.8px opacity, 1.5px width) permanently on the map. When an event pin is active near a lane, that lane briefly highlights to `--accent-cyan` with 0.6 opacity for 3 seconds, then returns to default.

---

## Component 3 — News Log Sidebar (20% right panel)

**Width:** 20vw (min 280px)  
**Background:** `var(--bg-secondary)`  
**Left border:** 1px solid `var(--border-subtle)`  
**Overflow-y:** scroll (custom styled scrollbar, 3px wide, `--border-default` color)

### Sidebar header

```
┌────────────────────────────┐
│ LIVE FEED           [⏸ 12] │
│ Showing: All Regions ▾     │
└────────────────────────────┘
```

- `LIVE FEED` title: 11px caps, font-weight 600, letter-spacing 0.1em, `--text-secondary`
- Pause button with count of queued events shown when paused
- Filter dropdown: regions list from user profile (All Regions / Asia Pacific / Europe / Americas / Middle East)

### News log item structure

Each news item is a card (`--bg-tertiary` bg, `--border-subtle` border-bottom, no rounded corners on the dividing border):

```
┌────────────────────────────┐
│ ● CRITICAL   PORT STRIKE   │  ← severity dot + type badge
│ Port of Shanghai            │  ← location, 13px, --text-primary
│ Cargo delays expected...    │  ← headline snippet, 11px, --text-secondary
│                             │
│ 09:41 UTC  [Source ↗] [◈]  │  ← timestamp + action icons
└────────────────────────────┘
```

- Severity dot: 7px filled circle, left-aligned, color from severity palette
- Type badge: `PORT`, `WEATHER`, `STRIKE`, `SANCTIONS`, `GEOPOLITICAL`, `LOGISTICS` — 10px caps, `--bg-elevated` bg, colored text matching severity
- Location: 13px `--text-primary`, truncated with ellipsis if >28 chars
- Headline: 11px `--text-secondary`, max 2 lines, `line-clamp: 2`
- Timestamp: 10px `JetBrains Mono`, `--text-muted`
- **Source link icon** `↗`: clicking opens the original news URL in a new tab. This is the validation feature — every item MUST have a traceable source
- **Graph icon** `◈`: clicking opens the Neo4j graph modal for this event's entity network

New items animate in from the top of the list: `translateY(-12px)` → `translateY(0)` over 300ms ease-out. A brief left border flash in the severity color (200ms) draws attention.

When paused, new items queue. Resuming plays them in smoothly at 150ms intervals.

---

## Component 4 — Bottom Stats Bar

**Height:** 48px  
**Background:** `var(--bg-secondary)` with 1px top border `var(--border-subtle)`  
**Layout:** flex row, divide into left ticker and right stats

### Left — Scrolling delay ticker

A CSS marquee-style horizontal scroll showing active delay impacts:

```
⚠ Shanghai Port → 8–14d delay  ·  ⛈ Typhoon Mawar → 3–5d delay  ·  ✈ Air freight surcharge +34% Indonesia  ·  ...
```

- Font: `JetBrains Mono` 11px, `--text-secondary`
- Active disruptions scroll continuously at 40px/sec, loop seamlessly
- Each item separated by ` · ` in `--text-muted`
- Severity icons colorized

### Right — Live stat chips

Five stat chips in a row, each 100px wide:

| Chip label | Value example | Color |
|---|---|---|
| ACTIVE EVENTS | `12` | `--accent-cyan` |
| CRITICAL | `3` | `--severity-critical` |
| HIGH RISK | `5` | `--severity-high` |
| AVG DELAY | `9.2d` | `--text-data` |
| ROUTES AFFECTED | `24` | `--text-secondary` |

Each chip: `--bg-tertiary` bg, `--border-subtle` border, 11px label in `--text-muted`, 18px value in the color above, `JetBrains Mono` font for values.

---

## Component 5 — Neo4j Knowledge Graph Modal

Triggered by clicking the `◈` icon on any pin popup or sidebar item. This is a **full-screen overlay modal** — `position: fixed`, `inset: 0`, `z-index: 9999`, background `rgba(10, 14, 26, 0.92)`.

### Modal inner panel

Centered card: 80vw × 80vh, `--bg-elevated` background, `--border-default` border, `border-radius: 12px`.

```
┌────────────────────────────────────────────────────────┐
│  Supply chain impact graph  ·  Port of Shanghai  [✕]   │
├──────────────────────┬─────────────────────────────────┤
│                      │  Node legend                     │
│   neovis.js graph    │  ● Port / Terminal               │
│   canvas             │  ● OEM / Manufacturer            │
│   (D3 force layout)  │  ● Shipping Line                 │
│                      │  ● Your SKUs (highlighted)       │
│                      │─────────────────────────────────-│
│                      │  Traversal depth  [1] [2] [3]   │
│                      │  Relationship filter  ▾          │
│                      │                                  │
│                      │  [Export as PNG]                 │
└──────────────────────┴─────────────────────────────────┘
```

**Graph canvas** (left 70%): rendered by `neovis.js` connecting to Neo4j via the backend proxy API. Nodes are colored by type. The event's origin node is highlighted with a pulsing border. Edges show relationship type labels (`SUPPLIES_TO`, `ROUTES_THROUGH`, `DEPENDS_ON`).

**Right panel** (30%): node legend with color chips, traversal depth selector (highlights how many hops from the origin to trace), relationship type filter checkboxes.

Clicking a graph node shows a small tooltip: node name, type, and if it's a user SKU, the SKU number and estimated delay impact.

The `[✕]` button and clicking outside the modal close it with a 200ms fade-out.

---

## Component 6 — Account Onboarding Page (separate `/onboarding` route)

This is the **only page where users provide input**. It is shown once on first login, and accessible later from Settings.

### Page layout

Full-page centered card (600px wide), `--bg-secondary` background, light step indicator at the top.

### Steps

**Step 1 — Company & role**
- Company name (text input)
- Role: dropdown [Procurement, Logistics, Operations, Finance, Executive]
- Team size: dropdown [1–10, 11–50, 51–200, 200+]

**Step 2 — Customer geographies**
- Multi-select world region checklist with a small Leaflet mini-map highlighting selected regions
- Regions: Asia Pacific, South & Southeast Asia, Europe, Middle East & Africa, Americas

**Step 3 — Products & SKUs**
- Tag input: type product categories (e.g. "Semiconductors", "Textiles", "Automotive Parts")
- Optional: upload a CSV of SKU codes for personalized tracking

**Step 4 — Key suppliers & OEMs (optional)**
- Text inputs for up to 5 supplier names + country
- Note: "We use this to build your personal supply chain graph in Neo4j"

**Step 5 — Review & activate**
- Summary card of all entered data
- "Activate dashboard" button: deep `--accent-blue` background, white text, 48px height, full-width

Input styling: all inputs use `--bg-tertiary` background, `--border-default` border, `--text-primary` placeholder and text, `--border-active` on focus (no box-shadow, just border color change), `border-radius: 8px`, `padding: 10px 14px`.

---

## WebSocket Integration (Frontend)

```javascript
const ws = new WebSocket('wss://api.chainpulse.io/ws/events');

ws.onopen = () => updateStatus('connected');
ws.onclose = () => { updateStatus('disconnected'); scheduleReconnect(); };

ws.onmessage = (msg) => {
  const event = JSON.parse(msg.data);
  // event shape:
  // {
  //   id: "evt_abc123",
  //   type: "PORT_STRIKE" | "WEATHER" | "SANCTIONS" | "GEOPOLITICAL" | "LOGISTICS",
  //   severity: "critical" | "high" | "medium" | "low",
  //   title: "Port workers strike at Port of Shanghai",
  //   summary: "...",
  //   source_url: "https://reuters.com/...",
  //   lat: 31.2304,
  //   lng: 121.4737,
  //   location_name: "Port of Shanghai, China",
  //   predicted_delay_min_days: 8,
  //   predicted_delay_max_days: 14,
  //   affected_sku_count: 47,
  //   affected_routes: 12,
  //   neo4j_event_id: "node_7x9a2b",
  //   timestamp_utc: "2025-06-14T09:41:00Z",
  //   ttl_seconds: 300
  // }

  addEventPin(event);       // → World map
  addSidebarItem(event);    // → News log
  updateStatsBar(event);    // → Bottom stats
  updateTicker(event);      // → Scrolling ticker
};
```

Reconnection logic: exponential back-off starting at 2s, max 30s. Show a non-intrusive top banner during reconnection: `RECONNECTING TO LIVE FEED…` in `--severity-medium` color.

---

## File Structure

```
/frontend
  index.html          ← single dashboard page
  onboarding.html     ← account setup page
  /css
    theme.css         ← CSS variables, global resets
    map.css           ← Leaflet overrides, pin animations
    sidebar.css       ← news log, scrollbar, item styles
    modal.css         ← graph modal, overlay
    titlebar.css      ← header, status indicators
    ticker.css        ← bottom bar, marquee
  /js
    ws-client.js      ← WebSocket connection + reconnect logic
    map-manager.js    ← Leaflet init, pin lifecycle, lane overlays
    sidebar-feed.js   ← news item render, queue, filter
    graph-modal.js    ← neovis init, traversal controls, modal open/close
    stats-updater.js  ← bottom bar chip values
    ticker.js         ← delay ticker scroll content
    onboarding.js     ← multi-step form logic
  /assets
    logo.svg
    shipping-lanes.geojson   ← pre-baked shipping lane polylines
```

---

## Accessibility & Performance Notes

- All icon-only buttons must have `aria-label` attributes
- Live region updates (sidebar) use `aria-live="polite"` on the feed container
- The WebSocket feed must be pausable — users presenting on screen need control
- Map tiles are lazy-loaded; initial load should show the dark background immediately while tiles stream in
- Do not block the main thread during pin creation — batch DOM insertions using `requestAnimationFrame`
- Keep the sidebar list to the last **200 items** max; virtualize older items out of the DOM

---

## Do Not

- Do not use any color lighter than `#8B9CC8` for body text on the dark background
- Do not use drop shadows (use borders instead)
- Do not show any loading spinner visible longer than 800ms at initial load
- Do not use emoji in the UI (use SVG icons or Tabler icon font)
- Do not add any user input fields to the main dashboard page
- Do not use `alert()`, `confirm()`, or `prompt()` — use styled inline notifications only
