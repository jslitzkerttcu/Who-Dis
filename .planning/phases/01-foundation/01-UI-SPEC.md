---
phase: 1
slug: foundation
status: draft
shadcn_initialized: false
preset: none
created: 2026-04-24
---

# Phase 1 — UI Design Contract

> Visual and interaction contract for Phase 1 (foundation). This phase introduces NO new screens. It codifies two reusable UI primitives — a **pagination partial** and an **admin "Run now" button** — that extend existing admin patterns without inventing new visual language. Phases 4 and 5 inherit the pagination contract.

**Source-of-truth principle:** Existing admin templates (`audit_logs.html`, `error_logs.html`, `_cache_actions.html`, `_compliance_violations_table.html`) ARE the design system. This document locks current conventions; it does not propose changes.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (no shadcn — this is a Flask/Jinja2 + HTMX server-rendered app) |
| Preset | not applicable |
| Component library | none — Tailwind utilities + FontAwesome icons |
| Icon library | FontAwesome 6.5.1 (loaded via CDN in `base.html`) |
| Font | Tailwind default (system font stack) |
| CSS framework | Tailwind CSS via CDN (configured inline in `base.html`) |
| Interactivity | HTMX 1.9.10 fragments, minimal vanilla JS |

**Brand tokens already defined in `app/templates/base.html` (Tailwind config):**
- `ttcu-green: #007c59` — primary brand / accent
- `genesys-orange: #FF4F1F` — Genesys-specific accents
- `ttcu-yellow: #f2c655` — secondary brand accent

---

## Spacing Scale

Phase 1 reuses existing Tailwind spacing utilities. No new tokens introduced.

| Token | Value | Usage in this phase |
|-------|-------|---------------------|
| `px-2 py-2` | 8px | Pagination icon-only chevron buttons |
| `px-3 py-2` | 12px / 8px | Compact action buttons (Run now, Refresh) |
| `px-4 py-2` | 16px / 8px | Pagination number buttons, secondary buttons |
| `px-4 py-3` | 16px / 12px | Pagination footer container |
| `px-6 py-4` | 24px / 16px | Card headers, table cell padding |
| `space-x-2` / `-space-x-px` | 8px / -1px | Button group separators |
| `mb-6` | 24px | Section vertical rhythm |

Exceptions: `-space-x-px` (Tailwind utility) is intentionally used in pagination button groups to collapse adjacent borders into a single shared edge — this is the existing convention in `_compliance_violations_table.html` and must be preserved.

---

## Typography

Phase 1 reuses existing Tailwind type scale. No new sizes introduced.

| Role | Size | Weight | Line Height | Where Used |
|------|------|--------|-------------|------------|
| Body | `text-sm` (14px) | `font-medium` (500) for emphasis, default (400) for prose | Tailwind default (1.25rem) | Pagination labels ("Showing X to Y of Z"), button text |
| Label / micro | `text-xs` (12px) | `font-medium` (500) | Tailwind default | Page-size selector label, "Run now" feedback messages, action button text in `_cache_actions.html` |
| Heading | `text-base` (16px) | `font-semibold` (600) | Tailwind default | Card section headings (Cache Management Actions tone) |
| Page title | `text-3xl` (30px) | `font-bold` (700) | Tailwind default | Not introduced in this phase |

Pagination uses `text-sm font-medium` for page-number buttons and `text-sm` for the "Showing… of…" status line — this matches the existing compliance violations table verbatim.

---

## Color

60/30/10 split applied to the Phase 1 surfaces:

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `bg-white` (#FFFFFF) for surfaces, `text-gray-700` / `text-gray-900` for text | Pagination footer background, table rows, button labels |
| Secondary (30%) | `bg-gray-50` / `bg-gray-100` (#F9FAFB / #F3F4F6) | Hover states (`hover:bg-gray-50`), filter card surfaces, table header rows |
| Accent (10%) | `bg-blue-50` + `border-blue-500` + `text-blue-600` (active page indicator); `bg-blue-500 hover:bg-blue-600` (primary action button — "Run now", "Apply Filters" tone) | **Reserved-for list:** active pagination page number, primary admin action buttons (Run now), filter Apply buttons |
| Brand accent (overrides blue when context is brand-tied) | `bg-ttcu-green` (#007c59) `hover:bg-green-700` | Cache Refresh confirmations and primary brand CTAs only — NOT used for pagination |
| Destructive | `bg-red-500 hover:bg-red-600` text-white | Cache Clear buttons; not used in Phase 1 (cleanup job is non-destructive from user POV — it only removes already-expired rows) |
| Neutral border | `border-gray-300` / `border-gray-200` | Pagination button borders, card outlines |
| Muted text | `text-gray-500` | Pagination chevron color, supporting copy |

**Accent is reserved for:**
1. The currently-active page number in the paginator (`bg-blue-50 border-blue-500 text-blue-600`)
2. The primary "Run now" admin action button (`bg-blue-500`)
3. The "Apply Filters" submit button on existing filter forms

Accent is NOT used for: row hover states, every interactive element, decorative purposes, or to indicate non-active pagination buttons.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Pagination status (desktop) | `Showing {start} to {end} of {total} {item_noun}` — caller passes `item_noun` (e.g. "audit log entries", "errors", "access attempts"). Default: "results" |
| Pagination status (no results) | Empty state replaces paginator entirely — see "Empty state" below |
| Pagination prev (mobile) | `Previous` |
| Pagination next (mobile) | `Next` |
| Pagination prev (desktop) | icon-only `<i class="fas fa-chevron-left">` with `aria-label="Previous page"` |
| Pagination next (desktop) | icon-only `<i class="fas fa-chevron-right">` with `aria-label="Next page"` |
| Page-size selector label | `Per page` |
| Page-size options | `25`, `50`, `100` (default 50 per D-14) |
| Empty state heading (audit/error/access tables) | `No entries found` |
| Empty state body | `Adjust your filters or expand the time range to see more results.` |
| **Primary CTA — cache cleanup "Run now"** | Button label: `Run now` with `<i class="fas fa-broom mr-1.5">` icon. Subtitle in parent card: `Search Cache Cleanup` / description `Remove expired cache entries (runs hourly automatically)` |
| Run-now success feedback | `Cleaned up {count} expired entries · {timestamp}` (rendered into result `<div>` via HTMX swap) |
| Run-now error feedback | `Cleanup failed: {error_summary}. Check error logs for details.` rendered in red-50/red-700 alert box |
| Run-now in-progress (HTMX indicator) | Spinner `<i class="fas fa-spinner fa-spin">` appears inline with button text; button stays enabled but `htmx-request:disabled` styling applied (existing pattern) |
| Destructive confirmation | **Not applicable in Phase 1.** The cache cleanup job is non-destructive from the user perspective (deletes already-expired rows). No confirmation modal required. Do NOT add one — it would be friction without safety value. |

---

## Component Contract — Pagination Partial

**File:** `app/templates/partials/pagination.html` (new — moved from admin/partials so Phases 4 and 5 can use it from non-admin contexts)

**Helper:** `app/utils/pagination.py` exposing `paginate(query, page, size) -> PageResult` with attributes: `items, page, per_page, total, pages, has_prev, has_next, prev_num, next_num, start_index, end_index`.

**Macro signature:**
```jinja
{% from "partials/pagination.html" import render_pagination %}
{{ render_pagination(
     pagination=page_result,
     endpoint=url_for('admin.api_audit_logs'),
     target='#logsTable',
     include='#filterForm',
     item_noun='audit log entries'
) }}
```

**Visual structure (desktop ≥ sm breakpoint):**
1. Outer container: `<div class="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">`
2. Left zone: status text `<p class="text-sm text-gray-700">Showing <span class="font-medium">{start}</span> to <span class="font-medium">{end}</span> of <span class="font-medium">{total}</span> {item_noun}</p>`
3. Center zone (NEW vs existing): page-size selector `<select class="px-2 py-1 text-sm border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">` with options 25/50/100; triggers `hx-get` on change preserving current page param OR resetting to page 1 (reset to 1 — standard UX)
4. Right zone: `<nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">` containing:
   - Prev chevron button (rounded-l-md, icon `fa-chevron-left`)
   - Up to 5 numbered page buttons centered on current page (window: `range(max(1, page-2), min(pages+1, page+3))`)
   - Optional ellipsis indicators if window doesn't reach edges (`<span class="px-4 py-2 border border-gray-300 bg-white text-sm text-gray-500">…</span>`) — keep simple, no clickable jump-to-edge in Phase 1
   - Next chevron button (rounded-r-md, icon `fa-chevron-right`)

**Active page button:** `z-10 bg-blue-50 border-blue-500 text-blue-600` (verbatim from existing convention).
**Inactive page button:** `bg-white border-gray-300 text-gray-500 hover:bg-gray-50`.
**Disabled prev/next:** simply not rendered (existing convention — `{% if has_prev %}`).

**Mobile structure (< sm breakpoint):**
- Two buttons only: Prev / Next, full-width split with `flex-1 flex justify-between sm:hidden`
- No page numbers, no page-size selector on mobile (defer to URL/desktop)

**HTMX contract:**
- All page buttons: `hx-get="{endpoint}?page={n}&size={size}"` `hx-target="{target}"` `hx-include="{include}"` `hx-swap="innerHTML"`
- Page-size selector: `hx-get="{endpoint}?page=1&size={selected}"` same target/include
- URL updates: `hx-push-url="true"` so `?page=3&size=50` is bookmarkable per D-13
- Loading indicator: optional `hx-indicator` parameter on macro; defaults to none (table fragment swap is fast enough)

**Empty state contract:**
When `total == 0`, the partial renders NOTHING. The calling template is responsible for the empty-state block (consistent with `_compliance_violations_table.html` pattern where empty state replaces the table). Macro must NOT render an empty paginator.

**Visibility threshold (D-14):**
Per D-14, paginator UI shows only when `total > 100`. Implementation: macro takes optional `min_total=100` parameter. If `total <= min_total`, macro renders only the status text ("Showing 1 to 47 of 47 results") with no nav controls. Below 100 rows the user sees the full table without pagination chrome.

**Accessibility:**
- `<nav aria-label="Pagination">` wraps the button group
- Active page: `aria-current="page"` attribute
- Icon-only chevrons: `aria-label="Previous page"` / `aria-label="Next page"` (FontAwesome `<i>` is decorative — `aria-hidden="true"` on icon)
- Page-size selector: associated `<label>` with `for` attribute
- Keyboard: native button focus order; `:focus` ring inherits Tailwind defaults (no custom focus styles introduced)

---

## Component Contract — Admin "Run now" Button (DEBT-03)

**Location:** Lives inside the existing `_cache_actions.html` partial, rendered as a fourth row in the cache actions list (matching the existing Search Cache / Genesys Cache / Employee Profiles row pattern).

**Visual structure:**
```html
<div class="border rounded-lg p-4 hover:shadow-md transition-shadow duration-200">
  <div class="flex items-center justify-between">
    <div class="flex items-center min-w-0 flex-1">
      <div class="flex-shrink-0 w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
        <i class="fas fa-broom text-blue-600 text-lg"></i>
      </div>
      <div class="ml-4 min-w-0 flex-1">
        <h5 class="font-semibold text-gray-900 text-sm">Search Cache Cleanup</h5>
        <p class="text-xs text-gray-500 mt-0.5">Remove expired entries (runs hourly automatically)</p>
      </div>
    </div>
    <div class="flex items-center space-x-2 ml-4">
      <button class="px-3 py-2 bg-blue-500 hover:bg-blue-600 text-white text-xs font-medium rounded-md transition duration-150 flex items-center whitespace-nowrap"
              hx-post="{{ url_for('admin.api_cache_cleanup_run') }}"
              hx-target="#cleanup-result"
              hx-swap="innerHTML"
              hx-indicator="#cleanup-spinner">
        <i class="fas fa-broom mr-1.5"></i>
        Run now
        <span id="cleanup-spinner" class="htmx-indicator ml-1.5">
          <i class="fas fa-spinner fa-spin"></i>
        </span>
      </button>
    </div>
  </div>
  <div id="cleanup-result" class="mt-3"></div>
</div>
```

**State contract:**
- **Idle:** Blue button, broom icon, "Run now" text. Spinner hidden.
- **In flight:** HTMX `htmx-request` class triggers `.htmx-indicator { display: inline-block }` (existing CSS in `error_logs.html`). Button remains visible but spinner appears inline.
- **Success:** `#cleanup-result` is replaced with `<div class="p-2 bg-green-50 border border-green-200 rounded text-xs text-green-800"><i class="fas fa-check-circle mr-1"></i>Cleaned up {count} expired entries at {HH:MM:SS}</div>`
- **Error:** `#cleanup-result` is replaced with `<div class="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-800"><i class="fas fa-exclamation-triangle mr-1"></i>Cleanup failed: {error}. Check error logs for details.</div>`

**Behavioral contract:**
- No confirmation modal (idempotent, non-destructive — only deletes already-expired rows)
- Server endpoint returns the HTML fragment directly (HTMX-style), not JSON
- Endpoint MUST be admin-role-gated: `@auth_required` + `@require_role("admin")`
- Audit log entry written via `audit_service.log_admin_action()` on every invocation regardless of outcome
- Result fragment auto-clears after 30 seconds OR persists until next click (pick: persist — matches existing cache-refresh feedback behavior)

**Accessibility:**
- Button has visible text label "Run now" (icon is decorative, `aria-hidden="true"`)
- Result `<div>` should be wrapped with `role="status"` `aria-live="polite"` so screen readers announce success/error feedback after HTMX swap

---

## Reuse Inventory (existing patterns being inherited, NOT redefined)

| Existing pattern | Source file | Inherited as-is |
|------------------|-------------|------------------|
| Table layout (`min-w-full divide-y divide-gray-200`, `bg-gray-50` thead, `text-xs uppercase tracking-wider` headers) | `_compliance_violations_table.html` | YES |
| Card surface (`bg-white rounded-lg shadow-md border border-gray-200`) | `error_logs.html`, `_cache_actions.html` | YES |
| Card header gradient (e.g. `bg-gradient-to-r from-blue-600 to-blue-700`) | `audit_logs.html` | YES — admin pages already use these; pagination/run-now do not introduce new headers |
| HTMX loading spinner (`animate-spin rounded-full h-8 w-8 border-b-2 border-ttcu-green`) | `audit_logs.html` | YES for table-level loading |
| HTMX inline indicator (`fa-spinner fa-spin` inside `.htmx-indicator`) | `error_logs.html`, `_cache_actions.html` | YES for button-level loading |
| Cache action row layout (icon-circle + title/subtitle + actions on right) | `_cache_actions.html` | YES — Run-now button reuses this exactly |
| Button sizes: `px-3 py-2 text-xs font-medium rounded-md` (admin row actions) | `_cache_actions.html` | YES |
| Color signaling: blue=primary action, green=brand/confirmation, red=destructive, orange=Genesys, yellow=warning | All admin templates | YES |

---

## Out of Scope for This Phase

The following UI concerns are intentionally NOT addressed in Phase 1:
- New page layouts, new screens, new admin entry points (no new menu items in `index.html`)
- New colors, new fonts, new spacing tokens
- Redesign of existing pagination in `_compliance_violations_table.html` (stays as-is; if convergence is desired later it's a follow-up to refactor it onto the new partial)
- Dark mode (project does not have one today)
- Mobile-first redesign of admin tables (current responsive split — desktop full nav, mobile prev/next only — is preserved)
- Replacement of inline `<script>` blocks with external JS (DEBT-04 scope is asyncio, not frontend JS)

---

## Flagged Assumptions

These were resolved by inspection of existing code rather than user input (auto mode). Flagged so the planner/executor can verify:

1. **Page-size selector is NEW in this codebase.** No existing paginator offers per-page selection. Adding it is implied by D-14 ("Page-size selector offers 25/50/100"). The visual style (`px-2 py-1 text-sm border border-gray-300 rounded-md focus:border-ttcu-green`) matches existing form `<select>` elements in `audit_logs.html` and `error_logs.html`. **Verify acceptable during planning.**
2. **`hx-push-url="true"` for bookmarkable pagination** is implied by D-13 ("Bookmarkable URLs `?page=3&size=50`"). Existing pagination in `_compliance_violations_table.html` does NOT push URL. New partial introduces this — consistent with the requirement.
3. **Item-noun parameterization** (`audit log entries` / `errors` / `access attempts`) — chose to make this a macro parameter rather than hardcode "results" so each surface reads naturally. Alternative is generic "results" everywhere; chose specificity per copywriting best practice.
4. **No confirmation modal on "Run now"** — D-14 mentions "Run now" but doesn't specify confirmation. Chose no-modal because the operation only removes already-expired rows (idempotent and non-destructive). **If product intent is "show a confirmation anyway for parity with cache Clear buttons", add a modal mirroring `_cache_actions.html` clearModal pattern.**
5. **Result fragment persists until next click** rather than auto-clearing. Matches existing cache-refresh feedback in `_cache_actions.html`.

---

## Copywriting Contract (consolidated table for checker)

| Element | Copy |
|---------|------|
| Primary CTA | `Run now` (admin cache cleanup) |
| Secondary CTA | `Per page` selector label / `Previous` / `Next` |
| Empty state heading | `No entries found` |
| Empty state body | `Adjust your filters or expand the time range to see more results.` |
| Error state | `Cleanup failed: {error}. Check error logs for details.` |
| Success state | `Cleaned up {count} expired entries at {time}` |
| Destructive confirmation | n/a — no destructive actions in Phase 1 |
| Pagination status | `Showing {start} to {end} of {total} {item_noun}` |

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| n/a (no shadcn — Flask/Jinja2 + Tailwind CDN only) | none | not applicable |

No third-party UI registries are used. Tailwind CDN and FontAwesome CDN are already loaded in `base.html` and remain unchanged.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
