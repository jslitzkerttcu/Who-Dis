# Phase 8: Reporting - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 08-reporting
**Areas discussed:** Report navigation, Data aggregation, Cache strategy, Report scheduling

---

## Report Navigation

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated reports page | Tabbed interface on one page | |
| Sidebar sub-pages | Separate routes with shared sidebar nav | |
| You decide | Let Claude pick | ✓ |

**User's choice:** You decide
**Notes:** Claude has discretion on structure.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Summary cards + table | KPI cards at top with drill-down table below | ✓ |
| Table only | Jump straight to sortable/filterable table | |
| You decide | Let Claude pick | |

**User's choice:** Summary cards + table
**Notes:** Admins get headline numbers at a glance, then scroll for details.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Date range picker | Two date inputs (from/to) | |
| Preset windows | Quick buttons: 24h, 7d, 30d | |
| Both | Preset buttons plus custom date picker | ✓ |

**User's choice:** Both
**Notes:** Most flexible — presets for common ranges, custom picker for edge cases.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, per report | Each tab gets Download CSV button | ✓ |
| No export needed | View-only dashboards | |
| You decide | Let Claude decide | |

**User's choice:** Yes, per report
**Notes:** Reuses Phase 7 CSV export pattern.

---

## Data Aggregation

| Option | Description | Selected |
|--------|-------------|----------|
| subscribedSkus only | Org-wide counts, no user iteration | |
| Full user iteration | Iterate all users for precise data | ✓ |
| You decide | Let Claude pick | |

**User's choice:** Full user iteration via scheduled sync job
**Notes:** User specified it should run as a sync job (like warehouse sync) to keep daytime usage fast. Not on-demand.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Same sync job | Bundle MFA into same user-iteration pass | |
| Separate sync | Dedicated MFA sync job | |
| You decide | Let Claude optimize | ✓ |

**User's choice:** You decide
**Notes:** Claude decides based on Graph API call patterns.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Sync job pulls audit logs | Background job fetches, stores locally | |
| On-demand from Graph | Query Graph directly when admin opens report | |
| Hybrid | Sync caches recent failures, Graph for extended ranges | ✓ |

**User's choice:** Hybrid
**Notes:** Fast for common views (cached recent data), full history available via Graph fallback.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Live presence API | Hit Genesys on page load | ✓ |
| Cached + manual refresh | Show from cache with refresh button | |
| You decide | Let Claude pick | |

**User's choice:** Live presence API but lazy-loaded
**Notes:** Lazy-load on tab open. Matches 5min freshness without background polling.

**Additional:** User clarified sign-in history should show ~72 hours default, paginated. Not just a handful of recent entries.

---

## Cache Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| New ReportCache model | Dedicated table with JSONB data, TTL | |
| Reuse EmployeeProfile | Extend existing cache table | |
| You decide | Let Claude pick | ✓ |

**User's choice:** You decide
**Notes:** Claude picks based on existing patterns and tiered TTL needs.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Timestamp + badge | "Last updated: 2h ago" with stale badge | |
| Auto-refresh notice | Banner + auto-trigger refresh | |
| You decide | Let Claude pick simplest | ✓ |

**User's choice:** You decide
**Notes:** Claude picks simplest effective approach.

---

## Report Scheduling

| Option | Description | Selected |
|--------|-------------|----------|
| Cache refresh only | Refreshes cache, no file output | |
| Saved snapshot | Timestamped snapshot for history view | |
| Email delivery | CSV/PDF emailed to recipients | |
| Snapshot + optional email | Save snapshot, email deferred | |

**User's choice:** You decide (best approach), but NO email delivery
**Notes:** User explicitly excluded email option. Claude decides between cache-refresh and snapshots.

---

| Option | Description | Selected |
|--------|-------------|----------|
| SandCastle portal only | Jobs in manifest, portal handles scheduling | ✓ |
| In-app schedule UI | Admin manages schedules within WhoDis | |
| Both | Portal + in-app control | |

**User's choice:** SandCastle portal only
**Notes:** Consistent with Phase 7 pattern.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Run history view only | Read-only history in WhoDis | ✓ |
| Schedule CRUD in WhoDis | Full schedule management UI | |
| You decide | Let Claude interpret REPT-06 | |

**User's choice:** Run history view only
**Notes:** No in-app schedule CRUD. REPT-06 satisfied via portal scheduling + WhoDis history display.

---

## Claude's Discretion

- Report section structure (tabs vs. sidebar)
- MFA sync strategy (bundled vs. separate)
- Cache model design (new table vs. pattern extension)
- Stale-cache indicator design
- Report generation output type (cache-only vs. snapshots)

## Deferred Ideas

- SKU friendly-name tooltip on profile cards (Phase 6 UI refinement)
- Email delivery of scheduled reports (explicitly excluded)
- In-app schedule CRUD (portal handles it)
