---
phase: 01-foundation
plan: 06
type: execute
wave: 1
depends_on: []
files_modified:
  - app/utils/pagination.py
  - app/templates/partials/pagination.html
  - app/blueprints/admin/database.py
  - app/blueprints/admin/__init__.py
  - app/templates/admin/audit_logs.html
  - app/templates/admin/error_logs.html
  - app/templates/admin/sessions.html
autonomous: true
requirements: [OPS-04]
must_haves:
  truths:
    - "Calling paginate(query, page, size) returns a PageResult with items, page, per_page, total, pages, has_prev, has_next, prev_num, next_num, start_index, end_index"
    - "The render_pagination(...) Jinja macro emits accessible HTML matching UI-SPEC verbatim, including page-size selector and hx-push-url='true'"
    - "Admin audit log, error log, and access attempts/sessions tables paginate using the new helper + macro — bookmarkable URLs ?page=N&size=M work"
    - "When total <= 100 rows, only the status text renders (no nav controls); when total == 0, the macro renders nothing"
  artifacts:
    - path: "app/utils/pagination.py"
      provides: "paginate(query, page, size) helper + PageResult"
      contains: "def paginate"
    - path: "app/templates/partials/pagination.html"
      provides: "render_pagination Jinja macro"
      contains: "macro render_pagination"
  key_links:
    - from: "app/blueprints/admin/database.py"
      to: "app/utils/pagination.py"
      via: "from app.utils.pagination import paginate"
      pattern: "from app.utils.pagination"
    - from: "app/templates/admin/audit_logs.html"
      to: "app/templates/partials/pagination.html"
      via: "{% from 'partials/pagination.html' import render_pagination %}"
      pattern: "render_pagination"
---

<objective>
Build a reusable `paginate()` helper + Jinja `render_pagination` macro and apply them to the three admin tables that currently roll their own pagination (audit log, error log, sessions/access attempts). Satisfies OPS-04.

Purpose: Establish THE pagination pattern Phases 4 (compliance results) and 5 (reports) inherit. Phase 1 ships the contract + the first three consumers.
Output: New utility, new partial, three admin endpoints rewritten to use them.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation/01-CONTEXT.md
@.planning/phases/01-foundation/01-PATTERNS.md
@.planning/phases/01-foundation/01-UI-SPEC.md
@CLAUDE.md
@app/utils/error_handler.py
@app/templates/admin/partials/_compliance_violations_table.html
@app/templates/admin/audit_logs.html
@app/templates/admin/error_logs.html
@app/blueprints/admin/database.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: paginate() helper and render_pagination macro</name>
  <read_first>
    - app/utils/error_handler.py lines 1–10 (module conventions per PATTERNS.md)
    - app/templates/admin/partials/_compliance_violations_table.html lines 143–223 (verbatim visual structure to copy)
    - .planning/phases/01-foundation/01-UI-SPEC.md §"Component Contract — Pagination Partial" (full spec)
    - PATTERNS.md "app/utils/pagination.py" section
  </read_first>
  <action>
    Per D-13 / D-14 / D-15 / OPS-04 + UI-SPEC:

    1. Create `app/utils/pagination.py`:
       ```python
       import logging
       from dataclasses import dataclass
       from typing import Any, Iterable
       from flask import request

       logger = logging.getLogger(__name__)

       MAX_PAGE_SIZE = 200
       DEFAULT_PAGE_SIZE = 50
       ALLOWED_SIZES = (25, 50, 100)

       @dataclass
       class PageResult:
           items: Iterable[Any]
           page: int
           per_page: int
           total: int
           pages: int
           has_prev: bool
           has_next: bool
           prev_num: int | None
           next_num: int | None
           start_index: int
           end_index: int

       def paginate(query, page: int | None = None, size: int | None = None) -> PageResult:
           if page is None:
               page = request.args.get("page", 1, type=int)
           if size is None:
               size = request.args.get("size", DEFAULT_PAGE_SIZE, type=int)
           page = max(1, int(page or 1))
           size = max(1, min(int(size or DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE))
           pag = query.paginate(page=page, per_page=size, error_out=False)
           start = ((pag.page - 1) * pag.per_page) + 1 if pag.total else 0
           end = min(pag.page * pag.per_page, pag.total)
           return PageResult(
               items=pag.items, page=pag.page, per_page=pag.per_page,
               total=pag.total, pages=pag.pages,
               has_prev=pag.has_prev, has_next=pag.has_next,
               prev_num=pag.prev_num, next_num=pag.next_num,
               start_index=start, end_index=end,
           )
       ```
    2. Create `app/templates/partials/pagination.html` defining the macro:
       ```jinja
       {% macro render_pagination(pagination, endpoint, target, include='', item_noun='results', min_total=100) -%}
         {% if pagination.total == 0 %}{# caller owns empty state #}
         {% elif pagination.total <= min_total %}
           <div class="bg-white px-4 py-3 border-t border-gray-200 sm:px-6">
             <p class="text-sm text-gray-700">
               Showing <span class="font-medium">{{ pagination.start_index }}</span>
               to <span class="font-medium">{{ pagination.end_index }}</span>
               of <span class="font-medium">{{ pagination.total }}</span> {{ item_noun }}
             </p>
           </div>
         {% else %}
           <div class="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
             {# mobile prev/next #}
             <div class="flex-1 flex justify-between sm:hidden">
               {% if pagination.has_prev %}
                 <a class="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                    hx-get="{{ endpoint }}?page={{ pagination.prev_num }}&size={{ pagination.per_page }}"
                    hx-target="{{ target }}" hx-swap="innerHTML"
                    {% if include %}hx-include="{{ include }}"{% endif %}
                    hx-push-url="true">Previous</a>
               {% endif %}
               {% if pagination.has_next %}
                 <a class="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                    hx-get="{{ endpoint }}?page={{ pagination.next_num }}&size={{ pagination.per_page }}"
                    hx-target="{{ target }}" hx-swap="innerHTML"
                    {% if include %}hx-include="{{ include }}"{% endif %}
                    hx-push-url="true">Next</a>
               {% endif %}
             </div>
             {# desktop: status + page-size selector + nav #}
             <div class="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
               <div>
                 <p class="text-sm text-gray-700">
                   Showing <span class="font-medium">{{ pagination.start_index }}</span>
                   to <span class="font-medium">{{ pagination.end_index }}</span>
                   of <span class="font-medium">{{ pagination.total }}</span> {{ item_noun }}
                 </p>
               </div>
               <div class="flex items-center space-x-4">
                 <label class="text-sm text-gray-700">
                   Per page
                   <select class="ml-2 px-2 py-1 text-sm border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green"
                           hx-get="{{ endpoint }}?page=1"
                           hx-target="{{ target }}" hx-swap="innerHTML"
                           {% if include %}hx-include="{{ include }}"{% endif %}
                           hx-push-url="true"
                           name="size">
                     {% for opt in [25, 50, 100] %}
                       <option value="{{ opt }}" {% if opt == pagination.per_page %}selected{% endif %}>{{ opt }}</option>
                     {% endfor %}
                   </select>
                 </label>
                 <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                   {% if pagination.has_prev %}
                     <a class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50"
                        aria-label="Previous page"
                        hx-get="{{ endpoint }}?page={{ pagination.prev_num }}&size={{ pagination.per_page }}"
                        hx-target="{{ target }}" hx-swap="innerHTML"
                        {% if include %}hx-include="{{ include }}"{% endif %}
                        hx-push-url="true"><i class="fas fa-chevron-left" aria-hidden="true"></i></a>
                   {% endif %}
                   {% set window_start = [1, pagination.page - 2]|max %}
                   {% set window_end = [pagination.pages, pagination.page + 2]|min %}
                   {% for n in range(window_start, window_end + 1) %}
                     {% if n == pagination.page %}
                       <span aria-current="page"
                             class="z-10 bg-blue-50 border-blue-500 text-blue-600 relative inline-flex items-center px-4 py-2 border text-sm font-medium">{{ n }}</span>
                     {% else %}
                       <a class="bg-white border-gray-300 text-gray-500 hover:bg-gray-50 relative inline-flex items-center px-4 py-2 border text-sm font-medium"
                          hx-get="{{ endpoint }}?page={{ n }}&size={{ pagination.per_page }}"
                          hx-target="{{ target }}" hx-swap="innerHTML"
                          {% if include %}hx-include="{{ include }}"{% endif %}
                          hx-push-url="true">{{ n }}</a>
                     {% endif %}
                   {% endfor %}
                   {% if pagination.has_next %}
                     <a class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50"
                        aria-label="Next page"
                        hx-get="{{ endpoint }}?page={{ pagination.next_num }}&size={{ pagination.per_page }}"
                        hx-target="{{ target }}" hx-swap="innerHTML"
                        {% if include %}hx-include="{{ include }}"{% endif %}
                        hx-push-url="true"><i class="fas fa-chevron-right" aria-hidden="true"></i></a>
                   {% endif %}
                 </nav>
               </div>
             </div>
           </div>
         {% endif %}
       {%- endmacro %}
       ```
  </action>
  <verify>
    <automated>grep -q 'def paginate' app/utils/pagination.py &amp;&amp; grep -q 'class PageResult' app/utils/pagination.py &amp;&amp; grep -q 'macro render_pagination' app/templates/partials/pagination.html &amp;&amp; grep -q 'hx-push-url="true"' app/templates/partials/pagination.html &amp;&amp; grep -q 'aria-current="page"' app/templates/partials/pagination.html &amp;&amp; python -c 'from app.utils.pagination import paginate, PageResult, MAX_PAGE_SIZE; assert MAX_PAGE_SIZE == 200'</automated>
  </verify>
  <acceptance_criteria>
    - `app/utils/pagination.py` exists with `def paginate` and `class PageResult`
    - `MAX_PAGE_SIZE = 200`, `DEFAULT_PAGE_SIZE = 50`, `ALLOWED_SIZES = (25, 50, 100)` constants present
    - `app/templates/partials/pagination.html` exists with `{% macro render_pagination`
    - Macro emits `hx-push-url="true"` on every nav action (≥3 occurrences in file)
    - Macro emits `aria-current="page"` on the active page button
    - Macro emits the page-size `<select>` with options 25, 50, 100
    - Calling paginate with `size=500` clamps `per_page` to `200` (MAX_PAGE_SIZE)
    - When `pagination.total == 0`, macro renders nothing (output is whitespace-only)
  </acceptance_criteria>
  <done>Reusable helper + macro ready; bookmarkable URLs work via hx-push-url; visibility threshold honored.</done>
</task>

<task type="auto">
  <name>Task 2: Wire paginate() + render_pagination into admin audit log, error log, and sessions tables</name>
  <read_first>
    - app/blueprints/admin/database.py (find existing pagination in api_error_logs and api_sessions handlers)
    - app/blueprints/admin/__init__.py (find audit log endpoint and existing pagination dict construction)
    - app/templates/admin/audit_logs.html, error_logs.html, sessions.html (current paginator markup to replace)
    - PATTERNS.md "Apply to:" section under app/utils/pagination.py
  </read_first>
  <action>
    Per OPS-04 Claude's Discretion ("apply the new helper to admin audit log, error log, and access attempts tables"):

    1. For each of the three admin endpoints currently rendering >100-row tables:
       - Audit log endpoint (in `app/blueprints/admin/__init__.py` — find the route returning `audit_logs.html`)
       - `app/blueprints/admin/database.py::api_error_logs`
       - `app/blueprints/admin/database.py::api_sessions` (or the access-attempts-equivalent endpoint, whichever is the >100-row table per PATTERNS.md)

       Replace the inline pagination dict construction with:
       ```python
       from app.utils.pagination import paginate
       page_result = paginate(query)  # reads page/size from request.args
       return render_template("admin/<surface>.html", pagination=page_result, items=page_result.items, ...)
       ```

    2. In each template (`audit_logs.html`, `error_logs.html`, `sessions.html`), replace the existing inline pagination markup with:
       ```jinja
       {% from "partials/pagination.html" import render_pagination %}
       {{ render_pagination(
            pagination=pagination,
            endpoint=url_for('admin.<endpoint_name>'),
            target='#<table-fragment-id>',
            include='#<filter-form-id>',
            item_noun='audit log entries'  {# or 'errors' / 'sessions' #}
       ) }}
       ```
       Use these `item_noun` values:
       - audit_logs.html → `'audit log entries'`
       - error_logs.html → `'errors'`
       - sessions.html → `'sessions'`

    3. Verify HTMX still swaps the table fragment correctly — the new partial fires `hx-get` against the same endpoints. Endpoints must continue to support both initial render (full page) and HX request (fragment) — the existing pattern is a `request.headers.get("HX-Request")` branch; preserve it.
    4. Do NOT remove the existing pagination from `_compliance_violations_table.html` (it stays as-is per UI-SPEC "Out of Scope").
  </action>
  <verify>
    <automated>grep -l 'from app.utils.pagination import paginate' app/blueprints/admin/ -r &amp;&amp; grep -l 'render_pagination' app/templates/admin/audit_logs.html app/templates/admin/error_logs.html app/templates/admin/sessions.html &amp;&amp; ! grep -q 'item_noun' app/templates/admin/partials/_compliance_violations_table.html</automated>
  </verify>
  <acceptance_criteria>
    - `grep -rn "from app.utils.pagination import paginate" app/blueprints/admin/` returns at least 1 match (audit, errors, sessions all use it — exact file count = 1 or 2 depending on co-location, but at least one import line)
    - `grep -l "render_pagination" app/templates/admin/audit_logs.html app/templates/admin/error_logs.html app/templates/admin/sessions.html` lists all three files
    - Each template's call to `render_pagination` uses a distinct `item_noun` string from the set {`audit log entries`, `errors`, `sessions`}
    - `_compliance_violations_table.html` is unchanged (existing inline paginator preserved per UI-SPEC out-of-scope rule)
    - Hitting `/admin/audit-logs?page=2&size=25` renders page 2 with 25 rows AND the URL bar updates on subsequent paginator clicks (hx-push-url verified manually)
    - App boots: `python -c "from app import create_app; create_app()"` exits 0
  </acceptance_criteria>
  <done>Three admin tables paginate via the shared partial; bookmarkable URLs work; pattern locked for Phases 4–5.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → admin endpoint | `page` and `size` query params are user-controllable |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-06-01 | Denial of Service | Runaway page size | mitigate | `paginate()` clamps `size` to `MAX_PAGE_SIZE=200` regardless of input; negative values clamped to 1 |
| T-01-06-02 | Information Disclosure | Pagination across role-restricted data | mitigate | All wired endpoints already enforce `@require_role("admin")`; pagination does not change auth — it operates over the same authorized SQLAlchemy queries |
| T-01-06-03 | Tampering | Crafted page query | mitigate | `request.args.get("page", 1, type=int)` rejects non-integers, falls back to default. SQLAlchemy paginate uses parameterized OFFSET/LIMIT — no SQL injection surface |
</threat_model>

<verification>
- `/admin/audit-logs` initial render: paginator visible only when total > 100; status text always visible
- Click page 2 → URL updates to `?page=2&size=50`, table fragment swaps, browser back button returns to page 1
- Change Per Page selector to 25 → resets to page 1 with 25 rows, URL `?page=1&size=25`
- Compliance violations table (Phase 4 territory) unchanged
</verification>

<success_criteria>
OPS-04 acceptance criterion satisfied: admin tables with 100+ rows paginate using offset/limit; reusable helper + partial established for downstream phases.
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-06-SUMMARY.md`.
</output>
