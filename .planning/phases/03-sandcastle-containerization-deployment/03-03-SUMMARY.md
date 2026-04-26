---
phase: 03-sandcastle-containerization-deployment
plan: 03
subsystem: docs-and-ops
tags: [readme, deployment-pointers, sandcastle, verification-script, ops-evidence, operator-confirmation]

# Dependency graph
requires:
  - phase: 03-sandcastle-containerization-deployment
    provides: Plan 03-01 (Redis Limiter swap) and Plan 03-02 (DATABASE_URL refactor) — README must reflect post-refactor state
  - phase: 09-sandcastle-onboarding
    provides: docs/sandcastle.md base content; scripts/cutover/README.md voice analog
provides:
  - "README.md deployment pointers consolidated — sandcastle.md canonical, deployment.md flagged as Legacy/Deprecated"
  - "docs/sandcastle.md Operational Verification section — exact operator steps for WD-OPS-01 and WD-OPS-04 closure"
  - "scripts/verify_deployment.py --sandcastle mode — three live-deployment checks (DNS, /health, /health/ready) with [PASS]/[FAIL] reporting and 0/1 exit codes"
  - "In-repo audit trail for portal registration + GitHub webhook configuration (operator records date + initials in 03-VERIFICATION.md)"
affects:
  - 03-VERIFICATION.md (downstream — produced by /gsd-verify-work 3 after this plan)
  - phase: 04-keycloak-oidc-authentication
  - phase: 05-database-migration-alembic

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hardcoded module-level URL constants for SSRF mitigation when --flag mode targets a known production host (no user input reaches the URL value)"
    - "Operator runbook voice: numbered confirmation steps + bash fence + explicit expected output + failure-recovery bullet"
    - "Documentation pointer pattern: canonical doc gets a positive label (canonical), deprecated doc gets explicit Legacy/Deprecated treatment with timeline note"

key-files:
  created: []
  modified:
    - README.md
    - docs/sandcastle.md
    - scripts/verify_deployment.py

key-decisions:
  - "README.md line 186 split into two lines: canonical sandcastle.md + Legacy deployment.md (D-G5-01) — preserves discoverability of the legacy path while making canonical unambiguous"
  - "README.md line 716 sysadmin pointer renamed to 'SandCastle Deployment Guide' (D-G5-02) — keeps verbiage operator-facing without breaking the existing link list ordering"
  - "README.md lines 683-693 (Deployment section) deliberately unchanged (D-G5-03) — already accurate post-PR-25; rewriting would introduce regression risk for zero benefit"
  - "scripts/verify_deployment.py SandcastleVerifier uses module-level SANDCASTLE_URL/SANDCASTLE_HOST constants, NOT a CLI URL argument (T-03-03-01) — eliminates SSRF vector entirely; --sandcastle is a boolean switch only"
  - "Three live checks chosen for the script: DNS resolution + /health (200) + /health/ready (200). Rate-limit/Redis NOT included (D-G2-04 — readiness deliberately excludes Redis)"
  - "docs/sandcastle.md Operational Verification appended after Phase 9 reference table (D-G4-02) — keeps Phase 9 reference contiguous and lets ops content live at end-of-doc where it is easiest to bookmark"

patterns-established:
  - "Hardcoded module-level URL constants for production-host-targeted CLI scripts (SSRF mitigation pattern)"
  - "Numbered-step operator runbook voice for in-repo evidence sections (mirrors scripts/cutover/README.md)"
  - "[PASS]/[FAIL] prefix log format for live-deployment checks (machine-greppable for CI integration if needed in future)"

requirements-completed:
  - WD-DOC-02

# Metrics
duration: ~6min
completed: 2026-04-26
---

# Phase 03 Plan 03: README Pointer Cleanup + Operational Verification Summary

**README deployment pointers consolidated to sandcastle.md as canonical, docs/sandcastle.md gained an Operational Verification section for WD-OPS-01/04 operator confirmation, and scripts/verify_deployment.py grew a `--sandcastle` mode running three live checks (DNS, /health, /health/ready) against the production URL.**

## Performance

- **Duration:** ~6 min (code changes only; live-deployment checkpoint pending operator action)
- **Started:** 2026-04-26T17:42:00Z (approx)
- **Completed (code):** 2026-04-26T17:48:00Z (approx)
- **Tasks:** 2 code tasks committed; 1 human-verify checkpoint awaiting operator
- **Files modified:** 3

## Accomplishments

- README.md line 186 split into two lines: `[Deployment Guide](docs/sandcastle.md)` (canonical) and `[Legacy Deployment](docs/deployment.md)` (deprecated). Discoverability preserved, canonical path unambiguous.
- README.md line 716 (Learn More section) updated so sysadmins land on the SandCastle Deployment Guide, not the deprecated Azure App Service guide.
- README.md lines 683-693 (`## Deployment` section) verified unchanged — already accurate per D-G5-03; intentionally left alone.
- `docs/sandcastle.md` Operational Verification section appended after the Phase 9 reference table (file grew from 234 → 281 lines). Section covers:
  - Numbered confirmation steps for WD-OPS-01 (portal catalog registration with `who-dis` green badge + WHODIS_APP_ID recording)
  - Numbered confirmation steps for WD-OPS-04 (GitHub webhook listing + last-delivery green tick + smoke-test redeliver)
  - Live-deployment checklist invoking `python scripts/verify_deployment.py --sandcastle` with exact expected `[PASS]` output block
  - Failure-recovery hint when `/health/ready` returns 503 (DATABASE_URL / Postgres provisioning pointer)
- `scripts/verify_deployment.py` extended with:
  - `import socket` (added to existing imports — no duplicate)
  - Module-level `SANDCASTLE_URL` and `SANDCASTLE_HOST` constants (hardcoded — T-03-03-01 SSRF mitigation)
  - `SandcastleVerifier` class with three methods (`check_sandcastle_health`, `check_sandcastle_ready`, `check_sandcastle_dns`) using the same `self.checks_total / self.checks_passed / self.errors` accounting as `DeploymentVerifier`
  - `run_all_checks()` runs all three, prints summary, and emits an explicit closure-recording reminder pointing at `03-VERIFICATION.md` on success
  - `main()` updated to handle `--sandcastle` flag — when present, instantiate `SandcastleVerifier` instead of `DeploymentVerifier`; both paths feed `sys.exit(0 if success else 1)`

## Task Commits

Each task committed atomically:

1. **Task 1: Fix README deployment pointers + add SandcastleVerifier + --sandcastle flag** — `d36ddc0` (feat)
2. **Task 2: Append Operational Verification section to docs/sandcastle.md** — `3b28f6a` (docs)

_Plan metadata commit will be added by execute-plan.md (or the orchestrator) after this SUMMARY is written._

## Files Created/Modified

- `README.md`
  - Line 186: replaced `[Deployment Guide](docs/deployment.md)` with two new lines — `[Deployment Guide](docs/sandcastle.md) - SandCastle deployment (canonical)` + `[Legacy Deployment](docs/deployment.md) - Deprecated; pre-Phase-9 Azure App Service notes`
  - Line 717 (was 716 pre-edit): replaced `Deployment Guide` link to `deployment.md` with `SandCastle Deployment Guide` link to `sandcastle.md`
  - Lines 686-694 (was 683-693): unchanged
- `docs/sandcastle.md`
  - Added 47 new lines after the Phase 9 reference table (line 234 was the last row): `## Operational Verification (WD-OPS-01, WD-OPS-04)` heading + WD-OPS-01 / WD-OPS-04 / Live-deployment checklist subsections
  - Existing content (lines 1-234) untouched
- `scripts/verify_deployment.py`
  - Added `import socket` to the imports block (line 23)
  - Added `SANDCASTLE_URL` and `SANDCASTLE_HOST` constants (lines 370-371)
  - Added `SandcastleVerifier` class (lines 374-465) with three check methods + `run_all_checks()`
  - Replaced `main()` to add `--sandcastle` flag and route between `DeploymentVerifier` and `SandcastleVerifier`
  - File grew from 386 → 519 lines

## Decisions Made

- **Followed plan as written** — all five HOW decisions (D-G5-01, D-G5-02, D-G5-03, D-G4-01, D-G4-02) from `PR-25-AUDIT.md` applied verbatim. No tactical rewording needed; the plan author already nailed the section voice and the constant names.
- **No destructive cleanup** — `docs/deployment.md` retained per D-G5-04 deferred decision (decommission post-Phase-9 verification once legacy Azure App Service environment is fully retired).
- **Static verification only at executor stage** — `python scripts/verify_deployment.py --sandcastle` exit-0 verification is the human-verify checkpoint deliverable; operator runs the script against live production. Running it from this dev/CI worktree against the public URL would be a half-truth at best (DNS resolves from anywhere; /health and /health/ready depend on whether the operator's network has VPN access to the SandCastle internal platform).

## Deviations from Plan

None — plan executed exactly as written. Both code tasks completed with all acceptance criteria met on first attempt; no auto-fixes (Rules 1/2/3) needed. No architectural deviations (Rule 4).

## Issues Encountered

None substantive. The Windows shell does not natively decode UTF-8 emoji in stdout when running `python scripts/verify_deployment.py --help` under default `cp1252`, but the new `SandcastleVerifier` log lines use ASCII-only `[PASS]` / `[FAIL]` prefixes — so this is not a runtime issue for the new code path. (Existing `DeploymentVerifier` class still uses ✅ / ❌ glyphs, which is pre-existing and out of scope per Rule 4 / scope-boundary.)

## Threat Model Compliance

The plan's threat register (T-03-03-01 through T-03-03-03) was honored:

- **T-03-03-01 (Elevation of Privilege / SSRF in SandcastleVerifier HTTP checks):** `SANDCASTLE_URL` and `SANDCASTLE_HOST` are hardcoded module-level string constants. The `--sandcastle` argparse flag is `action="store_true"` (boolean only), not a URL argument. No user-supplied input ever reaches the requests.get / socket.getaddrinfo calls. ✓ Mitigated.
- **T-03-03-02 (Information Disclosure via /health endpoint):** Risk **accepted** by design (WD-HEALTH-01, OPS-01 from Phase 1). `/health` is intentionally unauthenticated and returns only `{"status": "healthy"}`. No code change required.
- **T-03-03-03 (Tampering of README documentation):** Risk **accepted** — README.md is a documentation file in a private repository; no security boundary crossed.

## Plan-Level Verification (5 of 6 checks PASS — 1 awaits operator)

```
=== Verify 1: docs/sandcastle.md (canonical) ===              PASS
  README.md:186  - **[Deployment Guide](docs/sandcastle.md)** - SandCastle deployment (canonical)

=== Verify 2: docs/deployment.md (Legacy) ===                 PASS
  README.md:187  - **[Legacy Deployment](docs/deployment.md)** - Deprecated; pre-Phase-9 ...

=== Verify 3: Operational Verification heading ===            PASS
  docs/sandcastle.md:235  ## Operational Verification (WD-OPS-01, WD-OPS-04)

=== Verify 4: SandcastleVerifier class ===                    PASS
  scripts/verify_deployment.py:374  class SandcastleVerifier:

=== Verify 5: live --sandcastle exits 0 ===                   PENDING (human-verify checkpoint)

=== Verify 6: Python syntax ===                               PASS
  ast.parse OK
```

Static checks 1-4 + 6 all pass. Check 5 (live deployment) is the human-verify checkpoint — operator must run `python scripts/verify_deployment.py --sandcastle` against the live production URL and confirm all three `[PASS]` lines.

## Human-Verify Checkpoint Status

**STATUS: AWAITING OPERATOR**

The plan terminates at a `checkpoint:human-verify` gate. All code work is complete and committed; the orchestrator must surface the following to the user before declaring the plan closed:

1. Run live-deployment script:
   ```
   python scripts/verify_deployment.py --sandcastle
   ```
   Expected: three `[PASS]` lines + exit code 0.
2. Confirm SandCastle portal at `https://sandcastle.ttcu.com` shows `who-dis` with a healthy/green badge (WD-OPS-01).
3. Confirm GitHub webhook last delivery is green (WD-OPS-04).
4. Eyeball README.md changes (lines ~186 and ~717).

Once the operator confirms (or returns a failure trace), they record date + initials in `03-VERIFICATION.md` for WD-OPS-01 and WD-OPS-04. That recording is owned by `/gsd-verify-work 3` and is downstream of this plan.

## User Setup Required

**For the human-verify checkpoint** (operator action):

- Network access to `who-dis.sandcastle.ttcu.com` (typically requires SandCastle VPN or internal-network presence — DNS may resolve from anywhere, but `/health` and `/health/ready` only respond from within the network)
- Active SandCastle portal session at `https://sandcastle.ttcu.com`
- Access to the Who-Dis GitHub repo Settings → Webhooks page

For local development: no setup required. The `--sandcastle` flag is opt-in; existing `python scripts/verify_deployment.py` (no flag) continues to run the local-mode `DeploymentVerifier` checks unchanged.

## Threat Flags

None — no new security-relevant surface introduced beyond what the plan's `<threat_model>` already covers. The hardcoded production URL constants are the SSRF mitigation, not a new surface.

## Cross-Phase Note

- **WD-DOC-02** (canonical deployment pointer) is the requirement materially closed by this plan's README cleanup. Other requirements listed in the plan frontmatter (WD-OPS-01, WD-OPS-04, WD-HEALTH-01..04, WD-NET-01..05, WD-CONT-01..05, WD-OPS-02, WD-OPS-03, WD-DOC-01) are operationally driven and close via `03-VERIFICATION.md` once the operator runs the script — not by code shipping in this plan.
- **Phase 3 plans 03-01, 03-02, 03-03 complete.** Phase 3 gap closure work done. Next step: run `/gsd-verify-work 3` to produce `03-VERIFICATION.md` covering all 25 WD-* requirements.

## Next Plan Readiness

- **`/gsd-verify-work 3`** — ready to run after the human-verify checkpoint resolves. Will produce `03-VERIFICATION.md` consolidating the closure evidence from 03-01 (Redis swap), 03-02 (DATABASE_URL refactor), and 03-03 (README + ops evidence + operator confirmation).
- **Phase 4 (Keycloak OIDC)** — independent of this plan; can begin in parallel once the orchestrator advances STATE.md beyond Phase 3.
- **`docs/deployment.md` decommission** — deferred per D-G5-04. Out of scope for Phase 3; revisit after the legacy Azure App Service deployment is fully retired.

## Self-Check

- [x] `README.md` modified — line 186 split into canonical + Legacy lines (FOUND)
- [x] `README.md` modified — line 717 (was 716) updated to SandCastle Deployment Guide (FOUND)
- [x] `README.md` lines 686-694 (Deployment section) unchanged (VERIFIED)
- [x] `docs/sandcastle.md` modified — new Operational Verification section appended (FOUND)
- [x] `scripts/verify_deployment.py` modified — SandcastleVerifier class + --sandcastle flag (FOUND)
- [x] `scripts/verify_deployment.py` syntax valid (ast.parse OK)
- [x] Commit `d36ddc0` (Task 1) exists in git log
- [x] Commit `3b28f6a` (Task 2) exists in git log
- [x] All 5 static plan-level verification checks pass
- [ ] Live `--sandcastle` execution exits 0 — **PENDING operator (human-verify checkpoint)**

## Self-Check: PASSED (static); LIVE CHECK PENDING OPERATOR

---
*Phase: 03-sandcastle-containerization-deployment*
*Completed (code work): 2026-04-26*
*Awaiting human-verify checkpoint resolution before plan is fully closed*
