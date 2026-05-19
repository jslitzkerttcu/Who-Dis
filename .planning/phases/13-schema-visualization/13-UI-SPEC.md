---
phase: 13
slug: schema-visualization
status: draft
shadcn_initialized: false
preset: none
created: 2026-05-18
---

# Phase 13 — UI Design Contract

> Visual and interaction contract for the Schema Visualization feature (SCHEMA-01, SCHEMA-02, SCHEMA-03). Admins see a live ER diagram on a new tab of the existing database admin page, rendered by Mermaid.js from PostgreSQL metadata.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (Flask/Jinja2 project — shadcn not applicable) |
| Preset | not applicable |
| Component library | none (server-rendered Jinja2 templates) |
| Icon library | FontAwesome 6.5.1 (CDN) |
| Font | Tailwind CDN default (system font stack: ui-sans-serif, system-ui, sans-serif) |
| Diagram engine | Mermaid.js (CDN — per CONTEXT D-01, D-02) |

---

## Spacing Scale

Declared values (must be multiples of 4):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Icon-to-text gap in tab labels |
| sm | 8px | Tab label internal padding |
| md | 16px | Diagram container padding |
| lg | 24px | Section padding around diagram area |
| xl | 32px | Not used this phase |
| 2xl | 48px | Not used this phase |
| 3xl | 64px | Not used this phase |

Exceptions: Diagram container uses `min-height: 500px` (content-driven constraint to ensure diagram has adequate render space without scroll on typical screen). Mermaid internal node spacing is controlled by Mermaid config, not Tailwind.

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Tab label | 14px (text-sm) | 600 (font-semibold) for active, 400 (font-normal) for inactive | 1.5 |
| Section heading (card header) | 20px (text-xl) | 600 (font-semibold) | 1.2 |
| Diagram entity text (Mermaid-rendered) | Mermaid default (~12px) | Mermaid default (400) | Mermaid default |
| Loading/empty/error state text | 14px (text-sm) | 400 (font-normal) | 1.5 |

Note: Only 2 weights used: 400 (normal) and 600 (semibold). Mermaid controls its own internal SVG text rendering — do not override via CSS.

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | white / bg-white | Page background, diagram container background |
| Secondary (30%) | gray-50 / gray-100 | Card borders, tab borders, inactive tab text |
| Accent (10%) | blue-600 #2563EB | Active tab underline, Schema tab header gradient |
| Destructive | Not used this phase | No destructive actions |

### Schema Tab Header

| Element | Class | Hex |
|---------|-------|-----|
| Tab header gradient start | bg-gradient-to-r from-indigo-600 | #4F46E5 |
| Tab header gradient end | to-indigo-700 | #4338CA |
| Tab header text | text-white | #FFFFFF |
| Tab header icon | fas fa-project-diagram | FontAwesome |

### Diagram Interaction Colors

| Element | Class/Style | Hex |
|---------|-------------|-----|
| Highlighted table node | SVG fill opacity 1.0 | Mermaid default entity fill |
| Dimmed table node (unrelated) | SVG opacity 0.3 | N/A (opacity, not color) |
| Highlighted FK relationship line | SVG stroke-width 2.5px, stroke opacity 1.0 | Mermaid default line color |
| Dimmed relationship line | SVG opacity 0.15 | N/A (opacity, not color) |
| Background click reset | All nodes/lines return to opacity 1.0 | N/A |

Accent reserved for: active Schema tab underline border, tab header gradient. Not used inside the Mermaid SVG itself (Mermaid uses its own theme colors).

---

## Component Inventory

### Schema Tab (added to existing database.html tab bar)

**Placement:** New card section in the existing database admin page (database.html), positioned as a full-width row after the existing Table Statistics section (per CONTEXT D-09).

**Card Structure:**
```
+----------------------------------------------------------+
| [indigo gradient header]                                  |
|   fa-project-diagram  Database Schema                     |
+----------------------------------------------------------+
| [diagram container, HTMX lazy-loaded]                     |
|                                                           |
|   +---------------------------------------------------+  |
|   |                                                   |  |
|   |          Mermaid ER Diagram (SVG)                 |  |
|   |                                                   |
|   |   [TABLE_A]----[TABLE_B]----[TABLE_C]             |  |
|   |       |                        |                  |  |
|   |   [TABLE_D]              [TABLE_E]                |  |
|   |                                                   |  |
|   +---------------------------------------------------+  |
|                                                           |
+----------------------------------------------------------+
```

**Card Dimensions:**
- Full width within `max-w-7xl mx-auto` container (matches existing cards)
- Border radius: `rounded-2xl` (matches existing cards)
- Shadow: `shadow-md` with `hover:shadow-lg` transition (matches existing cards)
- Border: `border border-gray-200` (matches existing cards)

**Diagram Container:**
- `overflow: auto` for scroll-based panning (per CONTEXT D-07)
- `min-height: 500px` to prevent layout collapse before render
- Background: `bg-white`
- Padding: `p-4` (16px)
- Cursor: `cursor-grab` when hovering diagram, `cursor-grabbing` when dragging (if implementing drag-pan)

**Accordion Behavior:**
- Card header is clickable to expand/collapse (matching Table Statistics pattern)
- Chevron icon rotates on toggle (matching existing `toggleTableStats()` pattern)
- Content is hidden by default via `hidden` class
- HTMX lazy-load triggers on `revealed` event (per CONTEXT D-10)

### Loading State

**Trigger:** HTMX request in-flight for schema data.

**Appearance:**
```
+----------------------------------------------------------+
|                                                           |
|        [spinning circle]  Loading schema diagram...       |
|                                                           |
+----------------------------------------------------------+
```

- Spinner: `animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600` (matches existing database page spinners, using indigo instead of blue to match section header)
- Text: `text-gray-600` 14px
- Centered vertically and horizontally in container
- `py-8` vertical padding around spinner

### Error State

**Trigger:** HTMX request fails or backend returns error fragment.

**Appearance:**
```
+----------------------------------------------------------+
|                                                           |
|   [fa-exclamation-circle]                                 |
|   Unable to load schema diagram                           |
|   Check database connectivity and try refreshing          |
|   the page.                                               |
|                                                           |
|   [ Retry ]                                               |
|                                                           |
+----------------------------------------------------------+
```

- Icon: `fas fa-exclamation-circle text-red-500 text-3xl`
- Heading: `text-gray-700 text-base font-semibold mt-3`
- Body: `text-gray-500 text-sm mt-1`
- Retry button: `px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg mt-4` with `hx-get` to re-request schema endpoint
- All content centered

### Empty State

**Trigger:** Database has zero tables (extremely unlikely in production, but must be handled).

**Appearance:**
```
+----------------------------------------------------------+
|                                                           |
|   [fa-database]                                           |
|   No tables found                                         |
|   The database schema is empty. Tables will appear        |
|   here once the database is initialized.                  |
|                                                           |
+----------------------------------------------------------+
```

- Icon: `fas fa-database text-gray-400 text-3xl`
- Heading: `text-gray-700 text-base font-semibold mt-3`
- Body: `text-gray-500 text-sm mt-1`
- All content centered

---

## Interaction Contract

| Interaction | Behavior |
|-------------|----------|
| Click card header | Toggle expand/collapse of schema diagram section (accordion) |
| Accordion expand (first time) | HTMX fires `hx-get` to `/admin/database/schema` endpoint, loads Mermaid definition |
| Mermaid render complete | Vanilla JS initializes click callbacks on SVG entity nodes (per CONTEXT D-08) |
| Click table node in SVG | Highlight clicked table + all FK-connected tables to full opacity; dim all unrelated tables/relationships to 30% opacity (per CONTEXT D-06) |
| Click same table again | Reset all tables/relationships to full opacity |
| Click SVG background | Reset all tables/relationships to full opacity (per CONTEXT D-06) |
| Scroll inside diagram container | Native browser scroll panning (per CONTEXT D-07 — `overflow: auto`) |
| Pinch-to-zoom (touch) | Browser-native zoom on the SVG element |
| Window resize | Mermaid SVG reflows if `useMaxWidth: true` is set; otherwise container scrolls |

### Highlight Logic (vanilla JS, per CONTEXT D-08)

```
function onTableClick(tableName):
  if tableName is already highlighted:
    reset all nodes and edges to opacity 1.0
    return
  
  connectedTables = find all tables linked by FK to tableName
  for each node in SVG:
    if node.id == tableName or node.id in connectedTables:
      set node opacity to 1.0
    else:
      set node opacity to 0.3
  
  for each edge in SVG:
    if edge connects tableName to a connectedTable:
      set edge opacity to 1.0, stroke-width to 2.5px
    else:
      set edge opacity to 0.15
```

---

## Mermaid Configuration Contract

Per CONTEXT D-01 and Claude's Discretion on Mermaid config:

| Setting | Value | Rationale |
|---------|-------|-----------|
| `theme` | `default` | Clean, neutral colors appropriate for admin tooling |
| `securityLevel` | `loose` | Required to enable click callbacks on entity nodes (per D-08) |
| `er.useMaxWidth` | `true` | Diagram scales to container width |
| `er.layoutDirection` | `TB` | Top-to-bottom layout for readability with ~30 tables |
| `er.minEntityWidth` | `100` | Ensures column names are readable |

CDN URL: `https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs` (ESM module) or equivalent UMD bundle. CSP must allow `cdn.jsdelivr.net` (per CONTEXT D-03).

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA | Not applicable (read-only visualization — no primary action) |
| Card header title | "Database Schema" |
| Card header icon | `fa-project-diagram` |
| Loading state | "Loading schema diagram..." |
| Empty state heading | "No tables found" |
| Empty state body | "The database schema is empty. Tables will appear here once the database is initialized." |
| Error state heading | "Unable to load schema diagram" |
| Error state body | "Check database connectivity and try refreshing the page." |
| Error state CTA | "Retry" |
| Destructive confirmation | Not applicable (no destructive actions in this phase) |

---

## Accessibility Contract

| Requirement | Implementation |
|-------------|----------------|
| SVG `role` | `role="img"` on the Mermaid-generated SVG |
| SVG `aria-label` | "Entity-relationship diagram of the WhoDis database schema" |
| Keyboard focus on nodes | SVG entity `<g>` elements receive `tabindex="0"` and `role="button"` |
| Keyboard activation | `Enter` or `Space` triggers the same highlight logic as click |
| Focus indicator | `outline: 2px solid #2563EB` (blue-600) on focused node |
| Reduced motion | Respect `prefers-reduced-motion: reduce` — skip opacity transition animation |
| Color contrast | Mermaid default theme meets WCAG AA for entity text on light backgrounds |
| Screen reader summary | Hidden `<p class="sr-only">` above SVG with table count: "Database schema with {N} tables and {M} relationships" |

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| Not applicable | N/A | N/A — no component registry (Flask/Jinja2 project) |

---

## CDN Dependencies

| Library | Version | CDN | CSP Domain |
|---------|---------|-----|------------|
| Mermaid.js | 11.x (latest stable) | cdn.jsdelivr.net | `script-src cdn.jsdelivr.net` |
| HTMX | 1.9.10 (existing) | unpkg.com | Already allowed |
| Tailwind CSS | CDN (existing) | cdn.tailwindcss.com | Already allowed |
| FontAwesome | 6.5.1 (existing) | cdnjs.cloudflare.com | Already allowed |

CSP update required: Add `cdn.jsdelivr.net` to `script-src` directive in `app/middleware/security_headers.py` (per CONTEXT D-03).

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
