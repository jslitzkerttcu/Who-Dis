# Phase 3: SandCastle Containerization & Deployment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 03-sandcastle-containerization-deployment
**Areas discussed:** Phase 3 framing (Areas 2–4 skipped per user pivot to cross-phase audit)

---

## Pre-discussion situational findings

Before opening the gray-area selection, this audit established that PR #25 (`fdb6ff2`, "Phase 9 SandCastle onboarding" — sandcastle-portal numbering, not Who-Dis Phase 9) shipped most of Phase 3 plus all of Phase 4 and parts of Phase 5. Key gaps surfaced from code reading:

- `app/database.py:13-29` still composes URI from `POSTGRES_*` (WD-CFG-02 / WD-DB-01 open)
- `app/__init__.py:27` Limiter has no `storage_uri` (Phase 3 SC#2 / folded backlog 999.1 open)
- `README.md:186, 716` still treat `docs/deployment.md` as canonical (WD-DOC-02 partial)
- WD-OPS-01 / WD-OPS-04 lack in-repo evidence
- 35+ `X-MS-CLIENT-PRINCIPAL-NAME` references survive across 8 files (WD-AUTH-08 open — Phase 4 territory)
- No prior `.planning/phases/03-*` directory existed — work shipped without GSD planning records

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 3 framing | Verify-and-close-gaps audit, implement-only-the-remaining-gaps plan, or hybrid? | ✓ |
| Flask-Limiter Redis swap | REDIS_URL contract, dev fallback, where to set RATELIMIT_STORAGE_URI, Redis health probe? | ✓ |
| DATABASE_URL refactor (WD-CFG-02) | Switch now in Phase 3, hold for Phase 5, rip out POSTGRES_* or keep dev fallback, coordinate with Phase 5? | ✓ |
| Operational evidence (WD-OPS-01, 04, WD-DOC-02) | How to close infrastructure facts (operator checklist, verify script, screenshots) and how aggressively to clean README? | ✓ |

**User's choice:** All four areas selected.
**Notes:** User then chose to skip Areas 2–4 in favor of producing a single cross-phase audit document covering all three phases.

---

## Phase 3 framing — Q1: How should Phase 3 be framed?

| Option | Description | Selected |
|--------|-------------|----------|
| Verify + close gaps (Recommended) | Audit + closure: verify what PR #25 shipped, implement only the remaining gaps, backfill REQUIREMENTS.md status. Cheapest path; preserves work history. | ✓ |
| Implement-only-gaps, no audit | Surgical plans for open gaps; mark rest done by inspection. Faster but verification thin. | |
| Treat as fresh phase with retroactive plan records | Backfill 03-01..03-* PLAN.md files describing PR #25's work + new plans for gaps. Maximum bookkeeping fidelity; highest cost. | |

**User's choice:** Verify + close gaps.
**Notes:** Drives D-01 in CONTEXT.md.

---

## Phase 3 framing — Q2: What form should the audit take?

| Option | Description | Selected |
|--------|-------------|----------|
| Single retroactive 03-VERIFICATION.md (Recommended) | After gap-closure plans, run `/gsd-verify-work` to produce one verification doc scoring all 25 WD-* requirements with evidence. Mirrors 02-VERIFICATION.md structure. | ✓ |
| Per-requirement checkboxes in REQUIREMENTS.md | Mark each WD-* line `[x]` with inline evidence pointer. No separate doc. Lighter weight, fragmented evidence. | |
| Run /gsd-secure-phase + /gsd-validate-phase | Use existing retroactive-audit skills. Heavier than needed; wrong scope (threat models / test coverage, not deployment posture). | |

**User's choice:** Single retroactive 03-VERIFICATION.md.
**Notes:** Drives D-02 in CONTEXT.md.

---

## Phase 3 framing — Q3: How should the gap-closure plans be structured?

| Option | Description | Selected |
|--------|-------------|----------|
| Three separate plans (Recommended) | 03-01 Redis-Limiter, 03-02 DATABASE_URL, 03-03 README + ops. Each independently verifiable, atomic-committable. 03-01 and 03-02 can wave-parallelize. | ✓ |
| One bundled plan | Single 03-01-gap-closure-PLAN.md covering all gaps. Smaller bookkeeping; mixes a hot-path refactor (DB) with config (Redis) and docs (README). Harder to revert pieces. | |
| Two plans: code + docs/ops | 03-01 covers both code refactors, 03-02 covers README + ops. Compromise. | |

**User's choice:** Three separate plans.
**Notes:** Drives D-03 in CONTEXT.md and the plan-structure table in PR-25-AUDIT.md.

---

## Phase 3 framing — Q4: How to handle PR #25's Phase 4/5 overlap?

| Option | Description | Selected |
|--------|-------------|----------|
| Stay strictly in Phase 3 lane (Recommended) | This CONTEXT.md only tracks WD-CONT/CFG/HEALTH/NET/OPS/DOC. Note overlap, defer Phase 4/5 framing to their own discussions. | |
| Capture cross-phase audit notes here | "Cross-Phase Notes" section in 03-CONTEXT.md inventories Phase 4/5 satisfaction. Saves time later but blurs boundaries. | |
| Triage all three phases now | Audit PR #25 against Phases 3, 4, AND 5 here; produce three CONTEXT.md files. Comprehensive but inflates session. | ✓ |

**User's choice:** Triage all three phases now.
**Notes:** Drives D-04 in CONTEXT.md.

---

## Phase 3 framing — Q5: What's the execution model for the triage?

| Option | Description | Selected |
|--------|-------------|----------|
| Continue this discuss-phase 3, then chain into 4 and 5 (Recommended) | Finish discussing Phase 3, then run `/gsd-discuss-phase 4` and `5` as separate sessions. Clean phase boundaries; three discrete artifacts. | |
| Produce a single PR-25-AUDIT.md now spanning all three phases | Skip Areas 2–4 of this discussion. Write one cross-phase audit in `.planning/` mapping every PR #25 commit → requirement → phase, identify all gaps, then spawn three thin CONTEXT.md files pointing at it. Custom artifact. | ✓ |
| Inline mini-triage in 03-CONTEXT.md 'Cross-Phase Notes', then chain into 4 and 5 | Same as option 1 plus a cross-phase inventory section in 03-CONTEXT.md. Middle ground. | |

**User's choice:** Single cross-phase PR-25-AUDIT.md.
**Notes:** Caused Areas 2–4 to be skipped; the HOW decisions for each gap moved into the audit doc instead of being discussed individually.

---

## Phase 3 framing — Q6: Where do gap-closure HOW decisions get made?

| Option | Description | Selected |
|--------|-------------|----------|
| Capture them in PR-25-AUDIT.md alongside the gap inventory (Recommended) | Audit doc has both gap inventory AND HOW decisions. Drives gap-closure plans. CONTEXT.md files stay thin and reference the audit. | ✓ |
| Defer all HOW decisions to /gsd-plan-phase 3 | Audit only identifies gaps; planner decides HOW when generating PLAN.md. Faster discussion; more planner autonomy. | |
| Quick batch of remaining HOW questions in this session, then write the audit | ~10 minutes in --batch mode for critical HOW decisions, then audit + thin CONTEXT.md files. | |

**User's choice:** Capture HOW decisions in PR-25-AUDIT.md.
**Notes:** Drives D-05 in CONTEXT.md and the §"Gap Closure — HOW decisions" section of PR-25-AUDIT.md (D-G1-* through D-G5-*).

---

## Areas not discussed (per user pivot)

The following areas were initially selected but skipped after the user chose option 2 in Q5 ("single cross-phase audit"). Their HOW decisions live in `PR-25-AUDIT.md` §"Gap Closure" rather than being discussed individually:

- **Flask-Limiter Redis swap** — closed in PR-25-AUDIT.md G2 / D-G2-01..05
- **DATABASE_URL refactor** — closed in PR-25-AUDIT.md G1 / D-G1-01..05
- **Operational evidence + README cleanup** — closed in PR-25-AUDIT.md G4/G5 / D-G4-01..03 + D-G5-01..04

---

## Cross-phase artifacts produced in this session

This discussion produced four files (more than a normal `/gsd-discuss-phase` run, due to the user's triage pivot):

1. `.planning/PR-25-AUDIT.md` — Cross-phase audit with gap inventory + HOW decisions
2. `.planning/phases/03-sandcastle-containerization-deployment/03-CONTEXT.md` — Phase 3 context (this phase's primary deliverable)
3. `.planning/phases/04-keycloak-oidc-authentication/04-CONTEXT.md` — Phase 4 triage stub
4. `.planning/phases/05-database-migration-alembic/05-CONTEXT.md` — Phase 5 triage stub

Phase 4 and Phase 5 stubs are clearly marked for refinement via their own `/gsd-discuss-phase {N}` sessions before planning.

---

## Claude's Discretion

The following were not asked because the audit had enough context to record them as discretionary planning decisions:

- Exact wording of the production-mode warning when `RATELIMIT_STORAGE_URI=memory://` (D-G2-02 specifies the warning is required; phrasing tactical)
- Whether to extract `get_database_uri()` into a small helper for testability vs inline (Plan 03-02 planner picks)
- README.md line-by-line wording for the deployment-pointer rewrite (D-G5-01..03 specify intent; planner picks copy)
- Whether `verify_deployment.py` writes its checklist to stdout, JSON, or markdown (D-G4-01 requires the three checks; format tactical)

---

## Deferred Ideas

Captured during the audit, not Phase 3 scope:

- Decommission `docs/deployment.md` once legacy Azure App Service environment retires (D-G5-04 keeps the DEPRECATED banner for now)
- Add Redis to `/health/ready` — explicitly rejected (D-G2-04); rate-limit failure is degraded-but-functional
- Multi-stage Dockerfile / distroless base — image already meets WD-CONT-03 (<500 MB)
- CI pipeline (GitHub Actions on PR) — natural follow-up now that webhook deploy exists; explicitly out of Phase 3 scope
- Cutover rehearsal runbook + alembic drift smoke test — Phase 5 refinement candidates
- `request.remote_user` audit — possibly Easy-Auth residue with same root cause as WD-AUTH-08 (Phase 4 refinement candidate)
