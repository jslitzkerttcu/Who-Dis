# Phase 4: Keycloak OIDC Authentication - Context (TRIAGE STUB)

**Gathered:** 2026-04-26
**Status:** Triage stub — refine via `/gsd-discuss-phase 4` before planning

> ⚠ **This is a triage stub created during the Phase 3 cross-phase audit, not a full discussion.** PR #25 already shipped Phase 4 work; this file captures the audit findings and pending closure decision so a future `/gsd-discuss-phase 4` session can refine, not rebuild.

<domain>
## Phase Boundary

Replace Azure AD header-based auth with Authlib-driven Keycloak OIDC. Preserve `g.user`, `g.role`, and `@require_role()` decorator semantics. Auto-provision local user records on first SSO. Delivers WD-AUTH-01..08 (8 requirements).

**Special framing — gap closure, not greenfield:** PR #25 (`fdb6ff2`, "Phase 9 SandCastle onboarding") + post-merge auto-grant fix `35c1c1f` shipped 7 of 8 WD-AUTH requirements. One requirement (WD-AUTH-08) has a meaningful code-debt gap.

</domain>

<canonical_refs>
## Canonical References

### Single source of truth — START HERE
- `.planning/PR-25-AUDIT.md` §"Phase 4 — Keycloak OIDC Authentication" — Per-requirement audit. **§"Gap Closure — G3" contains decisions D-G3-01 through D-G3-04 for the WD-AUTH-08 cleanup.**

### Project Planning
- `.planning/ROADMAP.md` §"Phase 4: Keycloak OIDC Authentication" — 5 success criteria
- `.planning/REQUIREMENTS.md` §"SandCastle — Authentication (Keycloak OIDC)" — WD-AUTH-01..08

### Existing Code (already shipped — do NOT redesign)
- `app/auth/oidc.py` — Authlib OIDC integration; auth-code flow; PKCE; RP-initiated logout
- `app/auth/__init__.py` — Module surface
- `app/middleware/authentication_handler.py` — Reads `session.get("user")` populated by OIDC callback (WD-AUTH-01 done)
- `app/services/keycloak_admin.py` — Used by `35c1c1f` auto-grant feature
- `requirements.txt:18` — `Authlib==1.7.0`
- `docs/sandcastle.md` §"Keycloak OIDC setup" — WD-AUTH-03 documentation

### The one open requirement — WD-AUTH-08
- `app/blueprints/search/__init__.py` (4 sites: lines 331, 590, 825, 2657)
- `app/blueprints/admin/cache.py` (7 sites)
- `app/blueprints/admin/admin_users.py` (3 sites)
- `app/blueprints/admin/users.py` (9 sites)
- `app/blueprints/admin/audit.py` (1 site)
- `app/blueprints/admin/job_role_compliance.py` (3 sites)
- `app/blueprints/admin/database.py` (6 sites)
- `app/utils/error_handler.py` (3 sites — line 239 is intentionally retained per D-G3-04)

</canonical_refs>

<decisions>
## Implementation Decisions

### From the cross-phase audit (locked)
- **D-01:** Phase 4 is **verify + close one gap** — 7/8 requirements verified done by audit; only WD-AUTH-08 needs work.
- **D-02:** Single plan **04-01-azure-header-removal-PLAN.md** sweeps the 35+ `X-MS-CLIENT-PRINCIPAL-NAME` references across 8 files, replacing each with `g.user or "unknown"` (or the existing site-specific fallback string). See `PR-25-AUDIT.md` D-G3-01..04.
- **D-03:** `app/utils/error_handler.py:239` retains the literal `"X-MS-CLIENT-PRINCIPAL-NAME"` in the sensitive-headers redaction list as a defensive measure. This is the only acceptable surviving reference. WD-AUTH-08's `grep` acceptance criterion needs an exception note in the verification doc.
- **D-04:** **Single retroactive `04-VERIFICATION.md`** produced after Plan 04-01 ships, scoring all 8 WD-AUTH requirements with file/line evidence (mirroring the Phase 3 verification approach).

### Pending — refine via `/gsd-discuss-phase 4`
- Whether the sweep is one mechanical commit or split per-blueprint
- Whether to add a regression test (integration) that asserts audit rows show `g.user` instead of `"unknown"` after a write action
- Whether to grep more broadly for `request.remote_user` (could be a legacy Azure App Service / Easy-Auth idiom that has the same root cause)

</decisions>

<deferred>
## Deferred Ideas

- **`request.remote_user` audit** — May be Easy-Auth-era residue with the same fix pattern. Capture during the refinement discussion if scope allows; otherwise own backlog item.
- **Keycloak realm-export.json schema diff tooling** — Future capability if realm config drift becomes a problem.

</deferred>

---

*Phase: 04-keycloak-oidc-authentication*
*Context gathered: 2026-04-26 (triage stub)*
