# Phase 6: Enriched Profiles & Search Export - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 06-enriched-profiles-search-export
**Areas discussed:** Last sign-in & MFA data sources, License display (M365 SKUs), Section layout & lazy-load split, Export & copy-to-clipboard scope/format

---

## Last sign-in & MFA data sources

### Last sign-in source

| Option | Description | Selected |
|--------|-------------|----------|
| `user.signInActivity` field | One Graph field returns lastSignInDateTime; cheapest. Requires AuditLog.Read.All + Azure AD Premium P1. | ✓ |
| Latest from auditLogs/signIns | Reuse existing `get_sign_in_logs()` and surface most recent. Already permissioned; heavier per call. | |
| Both — timestamp eager, log list lazy | Timestamp via signInActivity in default card; existing log endpoint stays for the expanded list. | |

**User's choice:** signInActivity field. Premium P1 acceptable.

### MFA source

| Option | Description | Selected |
|--------|-------------|----------|
| Per-user `/authentication/methods` | Returns method list. Requires UserAuthenticationMethod.Read.All. Fits lazy-load. | ✓ |
| Bulk userRegistrationDetails report | Returns isMfaRegistered + summary. Requires AuditLog.Read.All + Reports.Read.All + P1. Built for batch. | |
| Status only — no method enumeration | Cheapest endpoint, just yes/no badge. | |

**User's choice:** Per-user `/authentication/methods`.

### Permission degradation

| Option | Description | Selected |
|--------|-------------|----------|
| Section renders with "Not available" + log warning | Inline message naming the missing permission; one-time-per-startup ERROR. | ✓ |
| Hide section on 403 | No section renders at all. | |
| Hard-fail on startup if perms missing | Health probe refuses boot. | |

**User's choice:** Inline "Not available" + permission name + one-time startup log.

### Cache TTL

| Option | Description | Selected |
|--------|-------------|----------|
| Match EmployeeProfile 24h TTL | Reuse existing layer; force-refresh button already exists. | ✓ |
| Live every time | No cache. Highest accuracy, slowest, hammers Graph. | |
| Short TTL (15 min) for these fields | Separate cache layer just for these fields. | |

**User's choice:** 24h TTL via EmployeeProfile.

---

## License display (M365 SKUs)

### SKU name resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Cache `/subscribedSkus` from Graph | Daily background refresh; tenant-accurate; mirror of genesys_cache_db. Requires Organization.Read.All. | ✓ |
| Static lookup table (Microsoft CSV) | No Graph call; drifts. | |
| Show skuPartNumber raw | No mapping; IT staff usually recognize codes. | |

**User's choice:** Cache `/subscribedSkus` daily.

### License detail level

| Option | Description | Selected |
|--------|-------------|----------|
| SKU name + assignedDateTime | Compact. Answers "does this user have E3?" + "since when?" | ✓ |
| SKU + per-service-plan status | Full per-plan enabled/disabled list. Verbose. | |
| SKU name only | No dates, no plans. | |

**User's choice:** SKU name + assigned date.

---

## Section layout & lazy-load split

### Section structure

| Option | Description | Selected |
|--------|-------------|----------|
| Two collapsibles: M365 + Genesys | Default card unchanged; two sections below, each lazy. | ✓ |
| Four collapsibles: Identity / Org / M365 / Genesys | Finer split; default card shrinks. | |
| One mega-section "Extended details" | Single collapsible loads everything at once. | |

**User's choice:** Two collapsibles (Microsoft 365 + Genesys Cloud). Default card unchanged.

### Lazy split

| Option | Description | Selected |
|--------|-------------|----------|
| Section renders empty, expand triggers HTMX load | Strict PROF-05; mirrors existing `/api/signin-logs/<id>`. | ✓ |
| Eager summary line, lazy details | One cheap line per result, full data on expand. | |
| Hover / intersection-observer auto-load | JS-driven auto-expand. | |

**User's choice:** Click-to-expand only. No eager summary, no hover auto-load.

---

## Export & copy-to-clipboard scope/format

### Export scope

| Option | Description | Selected |
|--------|-------------|----------|
| Per-profile only (button on each card) | Single-user paste workflow. | ✓ |
| Per-profile + multi-result CSV | Both buttons. | |
| Multi-result CSV only | One global button. | |

**User's choice:** Per-profile only.

### Lazy on export

| Option | Description | Selected |
|--------|-------------|----------|
| WYSIWYG — mark unloaded "Not loaded" with attribution column | No surprise Graph calls; predictable. | ✓ |
| Auto-fetch all sections on export | Complete data; slow + permission errors mid-export. | |
| Disable export until at least one section expanded | Forces explicit choice. | |

**User's choice:** WYSIWYG with source-attribution column.

### Copy format

| Option | Description | Selected |
|--------|-------------|----------|
| Plain text key:value | Pastes everywhere; no markdown surprises. | ✓ |
| Markdown with bold labels | Renders nicely in Teams/Slack; ugly in plain-text systems. | |
| Both ("Copy as text" + "Copy as markdown") | Two buttons, max flexibility, more clutter. | |

**User's choice:** Plain text key:value lines.

---

## Claude's Discretion

- Whether `/subscribedSkus` cache lives in a new model + service file or extends `genesys_cache_db`-style infra (planner's call).
- CSV/clipboard generation location: per-profile route vs dedicated export module (planner's call).
- Whether to extract the existing inline HTML at `app/blueprints/search/__init__.py:1584+` into a partial template (recommended; final call to planner).

## Deferred Ideas

- Multi-result / bulk CSV export
- Markdown copy variant
- Per-service-plan license breakdown
- License assignment / removal from profile view (Phase 9)
- Auto-fetch all sections on export click
- Hover / intersection-observer auto-expand
