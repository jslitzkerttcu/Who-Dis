# Phase 13: Schema Visualization - Research

**Researched:** 2026-05-19
**Domain:** PostgreSQL metadata introspection, Mermaid.js ER diagram rendering, HTMX lazy-loading
**Confidence:** HIGH

## Summary

Phase 13 adds an interactive ER diagram to the existing database admin page, generated dynamically from live PostgreSQL metadata. The server queries `pg_catalog` for table names, columns, types, primary keys, and foreign key relationships, then assembles a Mermaid `erDiagram` text definition. The client renders this via Mermaid.js (CDN) into an SVG, with vanilla JS providing click-to-highlight interaction on SVG entity nodes.

**Critical finding:** Mermaid.js ER diagrams do NOT support native click callbacks. The `click` syntax available in flowcharts has an open feature request (issue #3966) and an unmerged PR (#6985, still open as of May 2026). The CONTEXT decision D-08 references "Mermaid click callbacks on entities" -- this must be implemented as **post-render vanilla JS DOM manipulation** on the SVG elements, not through Mermaid's API. The SVG entity nodes are `<g>` elements with identifiable class names that can be targeted with `querySelectorAll`.

**Primary recommendation:** Generate Mermaid erDiagram text server-side from `pg_catalog` queries, render client-side with `mermaid.run()` after HTMX swap, and implement highlight interaction entirely in vanilla JS by manipulating SVG element opacity.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Use Mermaid.js for client-side ER diagram rendering -- server generates Mermaid erDiagram text from live PostgreSQL metadata (pg_catalog/information_schema), client-side Mermaid.js renders it to interactive SVG
- D-02: Include Mermaid.js via CDN (consistent with how HTMX and Tailwind are already loaded)
- D-03: CSP (Content Security Policy) must be updated to allow the Mermaid CDN domain
- D-04: Each table node shows column name, PostgreSQL type, and PK/FK markers -- no nullable flags, defaults, indexes, or constraints
- D-05: Mermaid erDiagram entity syntax: `TABLE_NAME { type column_name PK/FK }`
- D-06: Clicking a table node highlights it and all FK-connected tables, dimming unrelated tables to 50% opacity. Click again or click background to reset
- D-07: Use Mermaid's built-in zoom capabilities with CSS `overflow: auto` on the container for scroll-based panning
- D-08: Mermaid click callbacks on entities trigger the highlight logic via a small vanilla JS function
- D-09: Schema visualization lives as a new tab on the existing database admin page (`/admin/database`) alongside Health, Tables, Errors, Sessions tabs
- D-10: Schema tab content is lazy-loaded via HTMX (hx-get) when the tab is clicked

### Claude's Discretion
- Caching vs live generation: Determine whether to cache the Mermaid definition or generate fresh each request
- Table grouping: Whether to add logical grouping for table categories (core, cache, logging)
- Mermaid configuration: Pick optimal Mermaid config options (theme, securityLevel, useMaxWidth, etc.)

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCHEMA-01 | Admin can view an ER diagram of the live database schema on a dedicated admin page | Server-side pg_catalog queries generate Mermaid erDiagram text; Mermaid.js renders to SVG on the Database Management page |
| SCHEMA-02 | ER diagram renders as interactive SVG with zoom, pan, and clickable table nodes | Mermaid renders native SVG; overflow:auto provides pan; vanilla JS click handlers on SVG `<g>` nodes provide highlight interaction |
| SCHEMA-03 | Diagram is generated from live PostgreSQL metadata, not a static file | Three pg_catalog queries (tables, columns+types+PK, foreign keys) produce the Mermaid definition dynamically per request |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Schema metadata extraction | Database / PostgreSQL | -- | pg_catalog is the authoritative source for live schema |
| Mermaid definition generation | API / Backend (Flask) | -- | Server assembles erDiagram text from query results |
| SVG rendering | Browser / Client | -- | Mermaid.js runs client-side, renders SVG in DOM |
| Click-to-highlight interaction | Browser / Client | -- | Vanilla JS manipulates SVG opacity after render |
| HTMX lazy-loading | Browser / Client | Frontend Server (Flask) | HTMX triggers request; Flask returns HTML fragment |
| CSP configuration | Frontend Server (Flask) | -- | Security headers middleware sets policy |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Mermaid.js | 11.15.0 (CDN) | Client-side ER diagram rendering to SVG | Locked decision D-01; most widely used text-to-diagram JS library [ASSUMED] |
| Flask (existing) | 3.1.3 | Backend route handler returning HTML fragments | Already in stack per CLAUDE.md |
| SQLAlchemy (existing) | 2.0.45 | Execute raw SQL via `text()` for pg_catalog queries | Already in stack; used by existing `database_tables()` function |
| PostgreSQL pg_catalog | N/A (built-in) | Live schema metadata source | PostgreSQL system catalog -- authoritative metadata source [CITED: postgresql.org/docs] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| HTMX (existing) | 1.9.10 | Lazy-load schema fragment on accordion expand | Already in stack; pattern used by Table Statistics section |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Mermaid.js | D3.js or vis.js | More control but far more code; Mermaid is locked decision |
| pg_catalog queries | SQLAlchemy Inspector | Inspector API is simpler but less control over exact output; pg_catalog gives PK/FK markers directly |
| CDN include | npm bundle | Locked decision D-02; CDN is consistent with existing HTMX/Tailwind/FontAwesome pattern |

**Installation:**
No installation needed -- Mermaid.js loaded via CDN script tag. No new Python packages required.

## Package Legitimacy Audit

No new packages are installed in this phase. Mermaid.js is loaded via CDN (`cdn.jsdelivr.net`), not installed as a project dependency.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| mermaid (CDN only) | npm | 9+ yrs | ~3M/wk | github.com/mermaid-js/mermaid | N/A (CDN) | Approved -- well-known project [ASSUMED] |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
[Admin clicks "Database Schema" accordion]
        |
        v
[HTMX hx-get="/admin/database/schema"]
        |
        v
[Flask route: database_schema()]
        |
        v
[pg_catalog queries via SQLAlchemy text()]
  |-- Query 1: tables in public schema
  |-- Query 2: columns, types, PK flags per table
  |-- Query 3: foreign key relationships
        |
        v
[Assemble Mermaid erDiagram text string]
        |
        v
[Return HTML fragment with <pre class="mermaid"> + JS init]
        |
        v
[HTMX swaps fragment into DOM]
        |
        v
[htmx:afterSwap event triggers mermaid.run()]
        |
        v
[Mermaid renders SVG in container]
        |
        v
[Vanilla JS attaches click handlers to SVG <g> entity nodes]
        |
        v
[Click toggles opacity on connected/unconnected entities]
```

### Recommended Project Structure
```
app/
  blueprints/admin/
    database.py              # Add schema_data() + _render_schema() + _generate_mermaid_er()
    __init__.py              # Add route: /api/database/schema
  middleware/
    security_headers.py      # Update CSP for cdn.jsdelivr.net (already allowed)
  templates/admin/
    database.html            # Add Schema accordion card section
```

### Pattern 1: PostgreSQL Metadata Queries for Mermaid Generation

**What:** Three SQL queries against pg_catalog to extract tables, columns with types/PK markers, and FK relationships, then assemble into Mermaid erDiagram syntax.

**When to use:** Every time the schema endpoint is hit (or cached).

**Example:**
```python
# Source: PostgreSQL pg_catalog documentation + Mermaid erDiagram syntax docs
from sqlalchemy import text

def _get_schema_metadata():
    """Query PostgreSQL metadata for ER diagram generation."""
    
    # 1. Get all tables in public schema
    tables_query = text("""
        SELECT c.relname AS table_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY c.relname
    """)
    
    # 2. Get columns with types and PK markers
    columns_query = text("""
        SELECT 
            c.relname AS table_name,
            a.attname AS column_name,
            pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
            CASE WHEN pk.contype = 'p' THEN true ELSE false END AS is_pk
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        LEFT JOIN (
            SELECT conrelid, unnest(conkey) AS attnum, contype
            FROM pg_constraint
            WHERE contype = 'p'
        ) pk ON pk.conrelid = c.oid AND pk.attnum = a.attnum
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY c.relname, a.attnum
    """)
    
    # 3. Get foreign key relationships
    fk_query = text("""
        SELECT
            c1.relname AS source_table,
            a1.attname AS source_column,
            c2.relname AS target_table,
            a2.attname AS target_column
        FROM pg_constraint con
        JOIN pg_class c1 ON c1.oid = con.conrelid
        JOIN pg_class c2 ON c2.oid = con.confrelid
        JOIN pg_namespace n ON n.oid = c1.relnamespace
        JOIN pg_attribute a1 ON a1.attrelid = con.conrelid 
            AND a1.attnum = ANY(con.conkey)
        JOIN pg_attribute a2 ON a2.attrelid = con.confrelid 
            AND a2.attnum = ANY(con.confkey)
        WHERE con.contype = 'f'
          AND n.nspname = 'public'
        ORDER BY c1.relname
    """)
    
    return tables_query, columns_query, fk_query
```

[CITED: postgresql.org/docs/current/catalogs.html]

### Pattern 2: Mermaid erDiagram Text Assembly

**What:** Convert query results into valid Mermaid erDiagram syntax.

**When to use:** After metadata queries return results.

**Example:**
```python
# Source: mermaid.js.org/syntax/entityRelationshipDiagram.html
def _generate_mermaid_er(tables_data, columns_data, fk_data):
    """Generate Mermaid erDiagram definition from metadata."""
    lines = ["erDiagram"]
    
    # Group columns by table
    table_columns = {}
    for col in columns_data:
        table_columns.setdefault(col.table_name, []).append(col)
    
    # Build FK lookup for marking FK columns and relationships
    fk_lookup = {}  # {(source_table, source_col): (target_table, target_col)}
    for fk in fk_data:
        fk_lookup[(fk.source_table, fk.source_column)] = (
            fk.target_table, fk.target_column
        )
    
    # Emit entity definitions
    for table in tables_data:
        name = table.table_name
        cols = table_columns.get(name, [])
        lines.append(f"    {name} {{")
        for col in cols:
            # Sanitize type for Mermaid (replace spaces, parens)
            mermaid_type = col.data_type.replace(" ", "_")
            mermaid_type = mermaid_type.replace("(", "").replace(")", "")
            marker = ""
            if col.is_pk:
                marker = " PK"
            elif (name, col.column_name) in fk_lookup:
                marker = " FK"
            lines.append(f"        {mermaid_type} {col.column_name}{marker}")
        lines.append("    }")
    
    # Emit relationships from FK data
    seen_rels = set()
    for fk in fk_data:
        rel_key = (fk.source_table, fk.target_table)
        if rel_key not in seen_rels:
            seen_rels.add(rel_key)
            # Default to many-to-one (FK source }|--|| target)
            lines.append(
                f"    {fk.target_table} ||--o{{ {fk.source_table} : \"{fk.source_column}\""
            )
    
    return "\n".join(lines)
```

[CITED: mermaid.js.org/syntax/entityRelationshipDiagram.html]

### Pattern 3: HTMX Fragment with Mermaid Init

**What:** Return an HTML fragment containing the Mermaid definition in a `<pre class="mermaid">` tag, plus a small script to trigger rendering after HTMX swap.

**When to use:** Response from the `/admin/database/schema` endpoint.

**Example:**
```python
def _render_schema(mermaid_definition, table_count, fk_count):
    """Render schema diagram HTML fragment for HTMX."""
    return f"""
    <p class="sr-only">Database schema with {table_count} tables 
       and {fk_count} relationships</p>
    <div id="schema-diagram-container" 
         class="overflow-auto bg-white p-4"
         style="min-height: 500px;">
        <pre class="mermaid">
{mermaid_definition}
        </pre>
    </div>
    <script>
        if (typeof mermaid !== 'undefined') {{
            mermaid.run();
        }}
        // Attach click handlers after Mermaid renders
        setTimeout(function() {{
            initSchemaInteraction();
        }}, 500);
    </script>
    """
```

[CITED: mostlylucid.net/blog/mermaidandhtmx]

### Pattern 4: SVG Click-to-Highlight (Vanilla JS)

**What:** After Mermaid renders the SVG, attach click handlers to entity `<g>` elements. Since Mermaid ER diagrams do NOT support native click callbacks (issue #3966, PR #6985 unmerged), this must be done by querying the rendered SVG DOM.

**When to use:** After `mermaid.run()` completes rendering.

**Example:**
```javascript
// Source: Custom implementation -- Mermaid ER has no native click support
function initSchemaInteraction() {
    const svg = document.querySelector('#schema-diagram-container svg');
    if (!svg) return;
    
    // Mermaid ER entities are rendered as <g> elements with class "er entityBox"
    // or similar -- the exact class depends on Mermaid version
    const entities = svg.querySelectorAll('g[id^="entity-"]');
    // Alternative selector: svg.querySelectorAll('.entityBox')
    
    let highlightedTable = null;
    
    // Build FK adjacency map from data attribute or server-provided JSON
    // (inject fk_map as a JSON script block in the fragment)
    const fkMap = window.__schemaFkMap || {};
    
    entities.forEach(entity => {
        entity.style.cursor = 'pointer';
        entity.setAttribute('tabindex', '0');
        entity.setAttribute('role', 'button');
        
        entity.addEventListener('click', () => handleEntityClick(entity));
        entity.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleEntityClick(entity);
            }
        });
    });
    
    // Click background to reset
    svg.addEventListener('click', (e) => {
        if (e.target === svg || e.target.tagName === 'rect') {
            resetHighlight();
        }
    });
    
    function handleEntityClick(entity) {
        const tableName = extractTableName(entity);
        if (highlightedTable === tableName) {
            resetHighlight();
            return;
        }
        highlightTable(tableName);
    }
    
    function highlightTable(tableName) {
        highlightedTable = tableName;
        const connected = fkMap[tableName] || [];
        const allConnected = new Set([tableName, ...connected]);
        
        entities.forEach(e => {
            const name = extractTableName(e);
            e.style.opacity = allConnected.has(name) ? '1.0' : '0.3';
        });
        
        // Dim/highlight relationship lines
        const lines = svg.querySelectorAll('.er relationshipLine, line, path');
        lines.forEach(line => {
            // Check if line connects to highlighted table
            // Implementation depends on Mermaid SVG structure
            line.style.opacity = '0.15';
        });
    }
    
    function resetHighlight() {
        highlightedTable = null;
        entities.forEach(e => { e.style.opacity = '1.0'; });
        const lines = svg.querySelectorAll('line, path');
        lines.forEach(l => { l.style.opacity = '1.0'; });
    }
    
    function extractTableName(entity) {
        // Extract from entity ID or text content
        return entity.id?.replace('entity-', '') 
            || entity.querySelector('text')?.textContent?.trim() 
            || '';
    }
}
```

### Anti-Patterns to Avoid
- **Relying on Mermaid click callbacks for ER diagrams:** They do not exist. PR #6985 is unmerged. Must use post-render DOM manipulation. [VERIFIED: GitHub API -- PR #6985 state: open, merged: false]
- **Using `information_schema` instead of `pg_catalog`:** information_schema is SQL-standard but slower and less detailed than pg_catalog for PostgreSQL-specific features. The existing `database_tables()` already uses `pg_class` -- follow the same pattern.
- **Generating Mermaid definition client-side:** The server already has database access. Sending raw metadata to the client and assembling Mermaid text in JS adds complexity with no benefit.
- **Using `mermaid.initialize({ startOnLoad: true })` with HTMX:** Content loaded after page load via HTMX will not be picked up by `startOnLoad`. Must call `mermaid.run()` explicitly after HTMX swap.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ER diagram rendering | Custom SVG generation | Mermaid.js erDiagram | Handles layout, entity sizing, relationship lines, cardinality markers |
| PostgreSQL metadata extraction | Manual catalog joins | pg_catalog standard queries | Well-documented, stable across PostgreSQL versions 12+ |
| Diagram zoom/pan | Custom zoom/pan library | CSS `overflow: auto` on container | Locked decision D-07; native scroll panning is sufficient for ~30 tables |

**Key insight:** The only custom code needed is (1) the SQL-to-Mermaid-text assembly function and (2) the SVG click-to-highlight vanilla JS. Everything else is handled by existing tools.

## Common Pitfalls

### Pitfall 1: Mermaid Type Names with Spaces/Parens
**What goes wrong:** PostgreSQL types like `character varying(255)` or `timestamp without time zone` contain spaces and parentheses that break Mermaid entity attribute syntax.
**Why it happens:** Mermaid type names must be single tokens (no spaces, limited special chars).
**How to avoid:** Sanitize type strings: replace spaces with underscores, strip parentheses, or map to short aliases (e.g., `varchar`, `timestamptz`, `int4`).
**Warning signs:** Mermaid rendering fails silently or shows parse errors in console.

### Pitfall 2: HTMX Swap Timing vs Mermaid Render
**What goes wrong:** Calling `mermaid.run()` before the `<pre class="mermaid">` element is in the DOM, or attaching click handlers before Mermaid has finished rendering the SVG.
**Why it happens:** HTMX swaps content, but Mermaid rendering is asynchronous.
**How to avoid:** Use `htmx:afterSwap` event to trigger `mermaid.run()`, then use a `MutationObserver` or `setTimeout` to wait for the SVG to appear before attaching click handlers.
**Warning signs:** Empty diagram container, or click handlers not working.

### Pitfall 3: Mermaid securityLevel and Script Injection
**What goes wrong:** Setting `securityLevel: 'loose'` was recommended in CONTEXT D-08 for click callbacks, but since ER diagrams don't support click callbacks anyway, `loose` mode only adds XSS risk.
**Why it happens:** The CONTEXT decision was based on the assumption that Mermaid ER supports click callbacks.
**How to avoid:** Use `securityLevel: 'strict'` (default) since click interaction is handled by post-render JS, not Mermaid callbacks. This is safer.
**Warning signs:** N/A -- this is a preventive measure.

### Pitfall 4: SVG Entity Selector Fragility
**What goes wrong:** Mermaid's internal SVG class names and ID patterns can change between versions. Hardcoding selectors like `.er.entityBox` may break on version updates.
**Why it happens:** Mermaid's SVG output structure is an implementation detail, not a stable API.
**How to avoid:** Use resilient selectors -- query by `[id^="entity-"]` or by text content matching known table names. Test with the specific Mermaid version pinned in the CDN URL.
**Warning signs:** Click handlers stop working after a Mermaid version bump.

### Pitfall 5: CSP Already Allows cdn.jsdelivr.net
**What goes wrong:** The CONTEXT D-03 says CSP must be updated, but the current `security_headers.py` already includes `https://cdn.jsdelivr.net` in `script-src` and `style-src`.
**Why it happens:** CSP was already configured for jsdelivr (possibly for another library).
**How to avoid:** Verify the existing CSP before adding duplicate entries. No CSP change may be needed.
**Warning signs:** Duplicate domain in CSP directives (harmless but sloppy).

## Code Examples

### PostgreSQL Column Type Sanitization
```python
# Source: Custom -- handles PostgreSQL type names for Mermaid compatibility
TYPE_ALIASES = {
    "character varying": "varchar",
    "timestamp without time zone": "timestamp",
    "timestamp with time zone": "timestamptz",
    "double precision": "float8",
    "boolean": "bool",
    "integer": "int",
    "bigint": "int8",
    "smallint": "int2",
    "text": "text",
    "bytea": "bytea",
    "jsonb": "jsonb",
    "json": "json",
    "uuid": "uuid",
    "date": "date",
}

def _sanitize_pg_type(pg_type: str) -> str:
    """Convert PostgreSQL type to Mermaid-safe single token."""
    # Check aliases first
    base_type = pg_type.split("(")[0].strip().lower()
    if base_type in TYPE_ALIASES:
        return TYPE_ALIASES[base_type]
    # Fallback: replace spaces with underscores, strip parens
    return pg_type.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "")
```

### Mermaid CDN Include in base.html or database.html
```html
<!-- Source: mermaid.js.org/config/usage.html -->
<!-- Add to database.html block, NOT base.html (only needed on this page) -->
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.15.0/dist/mermaid.min.js"></script>
<script>
    mermaid.initialize({
        startOnLoad: false,
        theme: 'default',
        securityLevel: 'strict',
        er: {
            layoutDirection: 'TB',
            minEntityWidth: 100,
            minEntityHeight: 75,
            entityPadding: 15,
            fontSize: 12
        }
    });
    
    // Re-render after HTMX content swap
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        if (evt.detail.target.id === 'schema-content' 
            || evt.detail.target.closest('#schema-content')) {
            mermaid.run().then(function() {
                initSchemaInteraction();
            });
        }
    });
</script>
```

[CITED: mermaid.js.org/config/usage.html, mermaid.js.org/config/schema-docs/config-defs-er-diagram-config.html]

### FK Adjacency Map for Highlight Logic
```python
# Source: Custom -- server generates the FK map, injects as JSON for client JS
def _build_fk_adjacency_map(fk_data):
    """Build bidirectional adjacency map for FK highlight logic."""
    adjacency = {}
    for fk in fk_data:
        adjacency.setdefault(fk.source_table, set()).add(fk.target_table)
        adjacency.setdefault(fk.target_table, set()).add(fk.source_table)
    # Convert sets to lists for JSON serialization
    return {k: list(v) for k, v in adjacency.items()}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Mermaid `mermaid.init()` | `mermaid.run()` | Mermaid v10+ | `init()` is deprecated; `run()` is the current API for re-rendering |
| Mermaid UMD bundle | ESM module available | Mermaid v10+ | Both UMD and ESM available; UMD `<script>` tag is simpler for CDN use |
| startOnLoad only | Manual `mermaid.run()` | Mermaid v10+ | Required for HTMX/SPA patterns where content loads after page init |

**Deprecated/outdated:**
- `mermaid.init()`: Replaced by `mermaid.run()` in Mermaid 10+ [ASSUMED]
- `mermaid.contentLoaded()`: Legacy method, use `mermaid.run()` instead [ASSUMED]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Mermaid 11.15.0 is latest stable version | Standard Stack | Low -- version pinned in CDN URL, any 11.x should work |
| A2 | Mermaid SVG entity elements use `[id^="entity-"]` selector pattern | Pattern 4 | Medium -- may need different selector; must inspect actual rendered SVG during implementation |
| A3 | `mermaid.run()` returns a Promise that resolves after render | Code Examples | Medium -- if not, use MutationObserver or setTimeout fallback |
| A4 | ~30 tables renders acceptably without performance issues | Discretion: Caching | Low -- Mermaid handles hundreds of nodes; 30 is trivial |
| A5 | `mermaid.init()` is deprecated in favor of `mermaid.run()` in v10+ | State of the Art | Low -- both likely still work, but run() is documented as current |

## Open Questions

1. **Exact SVG selector for Mermaid ER entity nodes**
   - What we know: Mermaid renders entities as `<g>` elements inside the SVG. Flowcharts use `.node` class.
   - What's unclear: The exact class/ID pattern for ER diagram entity `<g>` elements in Mermaid 11.x.
   - Recommendation: During implementation, render a test diagram and inspect the SVG DOM to identify the correct selectors. Pin Mermaid to exact version (11.15.0) to prevent selector drift.

2. **Mermaid.run() Promise behavior**
   - What we know: `mermaid.run()` triggers rendering of `<pre class="mermaid">` elements.
   - What's unclear: Whether it returns a Promise that resolves only after SVG is in DOM.
   - Recommendation: Test during implementation. If not a Promise, use MutationObserver on the container to detect when `<svg>` appears, then attach click handlers.

3. **Caching decision (Claude's Discretion)**
   - What we know: ~30 tables, pg_catalog queries are fast (metadata, not data).
   - Recommendation: Generate fresh on each request. pg_catalog queries against ~30 tables execute in <10ms. Caching adds complexity (invalidation on schema changes) with negligible performance benefit. If profiling shows otherwise, add simple in-memory cache with 5-minute TTL.

4. **securityLevel deviation from CONTEXT D-08**
   - What we know: D-08 says "Mermaid click callbacks" but ER diagrams don't support them.
   - Recommendation: Use `securityLevel: 'strict'` instead of `'loose'` since click interaction is entirely post-render JS. This is safer and functionally equivalent. Flag this deviation to the user in planning.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (to be added per CLAUDE.md) |
| Config file | none -- see Wave 0 |
| Quick run command | `pytest tests/test_schema.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCHEMA-01 | Schema endpoint returns HTML fragment with Mermaid erDiagram text | unit | `pytest tests/test_schema.py::test_schema_endpoint_returns_mermaid -x` | No -- Wave 0 |
| SCHEMA-02 | Fragment contains interaction JS and accessibility attributes | unit | `pytest tests/test_schema.py::test_schema_fragment_has_interaction_js -x` | No -- Wave 0 |
| SCHEMA-03 | Mermaid definition includes all public tables from pg_catalog | integration | `pytest tests/test_schema.py::test_schema_includes_all_tables -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_schema.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_schema.py` -- covers SCHEMA-01, SCHEMA-02, SCHEMA-03
- [ ] `tests/conftest.py` -- shared fixtures (if not already present)
- [ ] pytest in requirements.txt (per CLAUDE.md: "add pytest to requirements.txt")

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing `@auth_required` + `@require_role("admin")` decorators |
| V3 Session Management | no | No new session behavior |
| V4 Access Control | yes | Admin-only endpoint; enforce via existing role decorator |
| V5 Input Validation | no | No user input -- endpoint reads pg_catalog only |
| V6 Cryptography | no | No crypto operations |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Schema metadata exposure | Information Disclosure | Admin-only access via `@require_role("admin")` |
| XSS via Mermaid rendering | Tampering | `securityLevel: 'strict'` prevents script injection in diagram text |
| CSP bypass via CDN | Tampering | Pin specific Mermaid version in CDN URL; CSP already restricts to cdn.jsdelivr.net |

## Project Constraints (from CLAUDE.md)

- Tech stack: Flask/PostgreSQL/HTMX -- no new frameworks (Mermaid is a CDN library, not a framework)
- Auth: Azure AD SSO -- new endpoint must use `@auth_required` + `@require_role("admin")`
- Code quality: `ruff check --fix` and `mypy app/` must pass
- DI container: Services accessed via `current_app.container.get()` (no new services needed for this phase)
- Error handling: Use `@handle_errors` decorator on route handler
- HTMX pattern: Return HTML fragments for partial updates
- Inline HTML fragments via f-string `_render_*` functions (established pattern in database.py)

## Sources

### Primary (HIGH confidence)
- PostgreSQL pg_catalog documentation -- table/column/FK metadata queries [CITED: postgresql.org/docs/current/catalogs.html]
- Mermaid ER diagram syntax -- entity/relationship definitions [CITED: mermaid.js.org/syntax/entityRelationshipDiagram.html]
- Mermaid ER config schema -- layoutDirection, minEntityWidth, etc. [CITED: mermaid.js.org/config/schema-docs/config-defs-er-diagram-config.html]
- Mermaid usage/initialization -- CDN setup, mermaid.run() [CITED: mermaid.js.org/config/usage.html]
- GitHub API verification -- PR #6985 (ER click callbacks) confirmed unmerged [VERIFIED: GitHub API, state: open, merged: false]

### Secondary (MEDIUM confidence)
- HTMX + Mermaid integration pattern -- htmx:afterSwap + mermaid.run() [CITED: mostlylucid.net/blog/mermaidandhtmx]
- Existing codebase patterns -- database.py _render_* functions, security_headers.py CSP [VERIFIED: codebase inspection]

### Tertiary (LOW confidence)
- Mermaid SVG DOM structure for ER entities -- exact selectors need runtime verification [ASSUMED]
- mermaid.run() Promise behavior -- needs testing [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Mermaid.js is locked decision; PostgreSQL pg_catalog is well-documented
- Architecture: HIGH -- follows established patterns in existing database.py
- Pitfalls: HIGH -- critical finding about missing ER click callbacks verified via GitHub API

**Research date:** 2026-05-19
**Valid until:** 2026-06-19 (stable -- Mermaid ER click PR unlikely to merge imminently)
