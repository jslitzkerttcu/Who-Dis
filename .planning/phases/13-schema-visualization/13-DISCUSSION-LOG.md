# Phase 13: Schema Visualization - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 13-Schema Visualization
**Areas discussed:** Diagram engine, Table node detail, Interaction behavior, Page placement

---

## Diagram Engine

### Q1: What should render the ER diagram SVG?

| Option | Description | Selected |
|--------|-------------|----------|
| Mermaid.js | Markdown-like ER syntax, renders client-side to SVG, lightweight CDN include, supports click events | :white_check_mark: |
| D3.js custom | Full control over layout and interaction, much more code to write and maintain | |
| Server-side Graphviz | Generate SVG on server with pygraphviz, no client-side JS but adds ~50MB to Docker image | |
| Let Claude decide | Claude picks the best rendering approach | |

**User's choice:** Mermaid.js
**Notes:** Server generates Mermaid text from metadata, client renders to SVG.

### Q2: Should the Mermaid definition be cached or generated on each load?

| Option | Description | Selected |
|--------|-------------|----------|
| Generate on each load | Schema rarely changes, pg_catalog query is fast (<100ms) | |
| Cache with manual refresh | Cache with TTL or Refresh button, adds complexity | |
| Let Claude decide | Claude picks based on query performance | :white_check_mark: |

**User's choice:** Let Claude decide
**Notes:** Deferred to Claude's discretion based on performance characteristics.

### Q3: How should Mermaid.js be included?

| Option | Description | Selected |
|--------|-------------|----------|
| CDN | Load from cdnjs/unpkg, consistent with existing HTMX/Tailwind pattern | :white_check_mark: |
| Vendored in static/ | Download mermaid.min.js into app/static/js/, works offline but adds ~2MB | |
| Let Claude decide | Claude picks based on existing frontend asset patterns | |

**User's choice:** CDN
**Notes:** Consistent with how HTMX and Tailwind are already loaded in the app.

---

## Table Node Detail

### Q1: What should each table node show?

| Option | Description | Selected |
|--------|-------------|----------|
| Columns + types + keys | Table name as header, columns with PostgreSQL type and PK/FK markers | :white_check_mark: |
| Name + columns only | Table name and column names without types | |
| Full detail | Columns, types, keys, nullable flags, and default values | |
| Let Claude decide | Claude picks the right level of detail | |

**User's choice:** Columns + types + keys
**Notes:** Shows column name, type, PK/FK markers. Skips nullable, defaults, indexes, constraints.

### Q2: Should tables be visually grouped or categorized?

| Option | Description | Selected |
|--------|-------------|----------|
| No grouping | All tables shown equally, FK relationships provide structure | |
| Logical grouping with comments | Add Mermaid comments to organize definition | |
| Let Claude decide | Claude determines if grouping adds value | :white_check_mark: |

**User's choice:** Let Claude decide
**Notes:** Deferred to Claude's judgment based on table count and relationships.

---

## Interaction Behavior

### Q1: What should happen when you click a table node?

| Option | Description | Selected |
|--------|-------------|----------|
| Highlight connected tables | Click highlights table and FK-connected tables, dims others to 50% opacity | :white_check_mark: |
| Show detail sidebar | Opens sidebar with full column details, indexes, row count, constraints | |
| No click interaction | View-only, zoom and pan work but clicking does nothing | |
| Let Claude decide | Claude picks based on Mermaid's click API | |

**User's choice:** Highlight connected tables
**Notes:** Click again or click background to reset.

### Q2: How should zoom and pan work?

| Option | Description | Selected |
|--------|-------------|----------|
| Mermaid's built-in zoom | Built-in SVG rendering with CSS overflow: auto for panning | :white_check_mark: |
| SVG pan-zoom library | Add svg-pan-zoom.js or panzoom.js for smoother controls | |
| Let Claude decide | Claude picks simplest approach | |

**User's choice:** Mermaid's built-in zoom
**Notes:** CSS overflow: auto on container for scroll-based panning, mouse wheel zoom.

---

## Page Placement

### Q1: Where should the schema visualization live?

| Option | Description | Selected |
|--------|-------------|----------|
| New tab on database page | Add Schema tab alongside existing Health/Tables/Errors/Sessions tabs | :white_check_mark: |
| Standalone admin page | New route at /admin/schema with its own nav entry | |
| Let Claude decide | Claude picks based on existing admin navigation patterns | |

**User's choice:** New tab on database page
**Notes:** Keeps all database tools together. Database page already has table stats — ER diagram is a natural companion.

### Q2: Should the schema tab load immediately or lazily?

| Option | Description | Selected |
|--------|-------------|----------|
| Lazy load on tab click | HTMX hx-get loads diagram fragment on tab click | :white_check_mark: |
| Eager load | Render diagram when database page first loads | |
| Let Claude decide | Claude picks based on existing tab loading patterns | |

**User's choice:** Lazy load on tab click
**Notes:** Consistent with how other admin tabs load content via HTMX.

---

## Claude's Discretion

- Caching vs live generation of Mermaid definition
- Table grouping/categorization in the diagram
- Mermaid configuration options (theme, securityLevel, useMaxWidth)

## Deferred Ideas

None — discussion stayed within phase scope
