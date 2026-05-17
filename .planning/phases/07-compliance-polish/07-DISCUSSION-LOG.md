# Phase 7: Compliance Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-16
**Phase:** 07-compliance-polish
**Areas discussed:** Progress feedback mechanism, Severity sorting behavior, Warehouse sync visibility, CSV export format

---

## Progress Feedback Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Background thread + HTMX poll | Kick off in background thread, return run_id, poll every 2s | |
| Synchronous with streaming | Keep in-request, chunked transfer encoding | |
| You decide | Let Claude pick | |

**User's choice:** User suggested using arq scheduler in SandCastle portal pattern (like Queue-Tip and ProjectCrystalBall). After reviewing both repos, confirmed the SandCastle job manifest pattern (no arq — uses thread-pool executor + HTTP trigger from portal).

| Option | Description | Selected |
|--------|-------------|----------|
| Add arq worker | New arq + Redis worker container | |
| Background thread + poll | Simpler, no new dependency | |
| You decide | Let Claude pick | |

**User's choice:** Directed to check CrystalBall and Queue-Tip implementations. Found they use thread-pool executor with HTTP job endpoints (not arq). Adopted same pattern.

| Option | Description | Selected |
|--------|-------------|----------|
| Both paths | Admin UI button + Portal scheduling, same backend | ✓ |
| Portal only | Remove in-app trigger | |
| You decide | | |

**User's choice:** Both paths

| Option | Description | Selected |
|--------|-------------|----------|
| Progress bar + counter | "42/150 employees checked" with percentage, 2s poll | ✓ |
| Step-by-step log | Scrolling batch completion messages | |
| Simple spinner + count | Minimal spinner with count | |

**User's choice:** Progress bar + counter

---

## Severity Sorting Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Client-side JS sort | Clickable headers, rank map, no server trip | |
| Server-side HTMX swap | hx-get with sort params, re-query | |
| You decide | Let Claude pick | ✓ |

**User's choice:** You decide
**Notes:** Claude chose client-side JS — small team (<5 users), results under 1000 rows, meets "no page reload" requirement directly.

| Option | Description | Selected |
|--------|-------------|----------|
| All columns sortable | Employee, job code, system, violation type, severity, date | ✓ |
| Severity + date only | Only two columns sortable | |
| You decide | | |

**User's choice:** All columns sortable

---

## Warehouse Sync Visibility

| Option | Description | Selected |
|--------|-------------|----------|
| SandCastle job status | Timestamp from job_manager completed_at | |
| Dedicated DB column | New sync_metadata table/config entry | |
| Both (job + local cache) | SandCastle job AND local sync_metadata record | ✓ |

**User's choice:** Both — job for scheduling history, local record for UI display

| Option | Description | Selected |
|--------|-------------|----------|
| Categorized error messages | Map pyodbc codes to human-readable categories | ✓ |
| Simple generic + detail toggle | "Sync failed" with expandable raw error | |
| You decide | | |

**User's choice:** Categorized error messages

| Option | Description | Selected |
|--------|-------------|----------|
| Disable during sync | Button grays out, shows "Syncing..." | ✓ |
| Allow queue | Queue follow-up run if already active | |

**User's choice:** Disable during sync

---

## CSV Export Format

| Option | Description | Selected |
|--------|-------------|----------|
| Metadata header rows | Run ID, Date, Scope, Triggered By as first rows | ✓ |
| Data only | Standard CSV, column headers on row 1 | |
| You decide | | |

**User's choice:** Metadata header rows

| Option | Description | Selected |
|--------|-------------|----------|
| On the results table | Button above violations table after check completes | |
| In the compliance dashboard | Dedicated export section with more options | |
| You decide | Let Claude pick | ✓ |

**User's choice:** You decide
**Notes:** Claude chose results table button — matches Phase 6 per-profile export pattern, simple and discoverable.

| Option | Description | Selected |
|--------|-------------|----------|
| Full run always | Download ALL violations regardless of filters | |
| Respect current view | WYSIWYG, only filtered results exported | |
| You decide | Let Claude pick | ✓ |

**User's choice:** You decide
**Notes:** Claude chose full run always — compliance reports need complete picture for audit purposes.

---

## Claude's Discretion

- Sorting approach: client-side JS (small dataset, no page reload requirement)
- Export button placement: on results table (consistent with Phase 6 pattern)
- Export scope: full run always (compliance audit completeness)

## Deferred Ideas

None — discussion stayed within phase scope
