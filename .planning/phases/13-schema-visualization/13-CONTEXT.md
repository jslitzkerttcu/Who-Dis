# Phase 13: Schema Visualization - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Admins can explore the live database schema visually without leaving the WhoDis admin interface. A new "Schema" tab on the existing database admin page renders an interactive ER diagram generated dynamically from PostgreSQL metadata, showing all tables, columns, types, keys, and foreign key relationships as an SVG with zoom, pan, and click-to-highlight-connected-tables interaction.

</domain>

<decisions>
## Implementation Decisions

### Diagram Engine
- **D-01:** Use **Mermaid.js** for client-side ER diagram rendering — server generates Mermaid erDiagram text from live PostgreSQL metadata (`pg_catalog`/`information_schema`), client-side Mermaid.js renders it to interactive SVG
- **D-02:** Include Mermaid.js via **CDN** (consistent with how HTMX and Tailwind are already loaded)
- **D-03:** CSP (Content Security Policy) must be updated to allow the Mermaid CDN domain

### Table Node Detail
- **D-04:** Each table node shows **column name, PostgreSQL type, and PK/FK markers** — no nullable flags, defaults, indexes, or constraints in the diagram nodes
- **D-05:** Mermaid erDiagram entity syntax: `TABLE_NAME { type column_name PK/FK }`

### Interaction Behavior
- **D-06:** Clicking a table node **highlights it and all FK-connected tables**, dimming unrelated tables to 50% opacity. Click again or click background to reset
- **D-07:** Use Mermaid's **built-in zoom capabilities** with CSS `overflow: auto` on the container for scroll-based panning — no additional pan/zoom library
- **D-08:** Mermaid click callbacks on entities trigger the highlight logic via a small vanilla JS function

### Page Placement
- **D-09:** Schema visualization lives as a **new tab on the existing database admin page** (`/admin/database`) alongside Health, Tables, Errors, Sessions tabs
- **D-10:** Schema tab content is **lazy-loaded via HTMX** (`hx-get`) when the tab is clicked — avoids slowing down the initial database page load

### Claude's Discretion
- **Caching vs live generation:** Claude determines whether to cache the Mermaid definition or generate it fresh on each request, based on query performance against pg_catalog for the current table count (~30 tables)
- **Table grouping:** Claude determines whether to add logical grouping (comments or visual separation) for different table categories (core, cache, logging) based on the rendered diagram readability
- **Mermaid configuration:** Claude picks the optimal Mermaid config options (theme, securityLevel, useMaxWidth, etc.) for the admin UI context

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Database Introspection (existing code to extend)
- `app/blueprints/admin/database.py` — Existing `database_tables()` function at line 124 uses SQLAlchemy `inspect()` and `pg_class` for table metadata. Reuse/extend this pattern for ER diagram data extraction
- `app/blueprints/admin/__init__.py` — Admin blueprint route registration (lines 113-128) — add new schema endpoint here

### Admin UI Structure
- `app/templates/admin/database.html` — Existing database admin page with tab structure — add Schema tab here
- `app/templates/admin/index.html` — Admin dashboard layout for navigation context

### Project Context
- `.planning/REQUIREMENTS.md` — SCHEMA-01, SCHEMA-02, SCHEMA-03 requirement definitions
- `.planning/ROADMAP.md` — Phase 13 success criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `database_tables()` in `app/blueprints/admin/database.py`: Already queries `pg_class` for table names, row counts, and uses SQLAlchemy `inspect()` for table metadata — extend for column types and FK relationships
- Admin database page tab structure in `database.html`: Existing tab UI pattern to add the Schema tab to
- HTMX lazy-loading pattern used in other admin tabs: `hx-get` with `hx-trigger="click"` for on-demand content loading

### Established Patterns
- Tailwind CSS utility classes for all UI components — diagram container should use Tailwind for layout/styling
- HTMX fragments returned from Flask routes — schema endpoint returns an HTML fragment with the Mermaid definition embedded
- `@auth_required` + `@require_role("admin")` on all admin routes
- `@handle_errors` decorator on route handlers for consistent error handling

### Integration Points
- `app/blueprints/admin/__init__.py`: Register new route for schema API endpoint
- `app/blueprints/admin/database.py`: Add schema generation function alongside existing database introspection functions
- `app/templates/admin/database.html`: Add Schema tab to the tab bar and container
- `app/middleware/security_headers.py`: Update CSP to allow Mermaid CDN domain
- CDN script tag in base template or database page for Mermaid.js include

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-Schema Visualization*
*Context gathered: 2026-05-18*
