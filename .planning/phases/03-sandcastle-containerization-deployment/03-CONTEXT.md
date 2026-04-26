# Phase 3: SandCastle Containerization & Deployment - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning (gap-closure mode)

<domain>
## Phase Boundary

Package WhoDis as a SandCastle-hosted application: production Docker image, gunicorn behind Traefik with HTTPS, env-var-only configuration, structured JSON logs, health probes, and portal registration. Delivers WD-CONT-01..05, WD-CFG-01..05, WD-HEALTH-01..04, WD-NET-01..05, WD-OPS-01..04, WD-DOC-01..02 (25 requirements).

**Special framing — gap closure, not greenfield:** PR #25 (`fdb6ff2`, "Phase 9 SandCastle onboarding") shipped ~80% of this phase before it was ever planned through GSD. This phase scope is therefore (a) a retroactive verification of what PR #25 delivered, plus (b) three surgical gap-closure plans for what remains.

In scope: Redis-backed Flask-Limiter swap, `DATABASE_URL` refactor in `app/database.py`, README deployment-pointer cleanup, operational evidence for WD-OPS-01/04, retroactive `03-VERIFICATION.md`. Out of scope: Authlib OIDC (Phase 4 — also shipped via PR #25), Alembic infrastructure (Phase 5 — also shipped via PR #25; cross-phase audit covers both).

</domain>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Single source of truth — START HERE
- `.planning/PR-25-AUDIT.md` — Cross-phase audit of what PR #25 shipped vs what remains for Phases 3, 4, 5. **Contains the gap-closure HOW decisions for every Phase 3 plan (D-G1-* through D-G5-*).** Read this before planning any of the 03-* plans.

### Project Planning
- `.planning/ROADMAP.md` §"Phase 3: SandCastle Containerization & Deployment" — 5 success criteria, 25 requirements
- `.planning/REQUIREMENTS.md` §"SandCastle — Containerization", "— Configuration", "— Health & Observability", "— Networking & Routing", "— Deployment & Operations", "— Documentation" — WD-CONT/CFG/HEALTH/NET/OPS/DOC acceptance criteria
- `.planning/STATE.md` — Phase 1/2 decisions (Flask-Limiter D-08 deviation that this phase closes), follow-ups list

### Codebase Maps
- `.planning/codebase/STACK.md` — Flask 3.1, gunicorn 25, Authlib 1.7, alembic 1.18 (already in `requirements.txt`)
- `.planning/codebase/ARCHITECTURE.md` — DI container, blueprint structure
- `.planning/codebase/CONVENTIONS.md` — snake_case, decorator stacks, `os.environ.get` for bootstrap config

### Existing Code (must read before changing)
- `Dockerfile` — Production image (DO NOT change for Phase 3 work; it's already correct)
- `docker-compose.sandcastle.yml` — Compose file (DO NOT change unless adding REDIS_URL service def — D-G2-01 specifies the URL only, the service is provided by SandCastle's `internal` network)
- `docker-entrypoint.sh` — Alembic + gunicorn boot (DO NOT change; relies on DATABASE_URL which Plan 03-02 fixes the app side of)
- `.env.sandcastle.example` — Env-var contract (Plan 03-01 adds `RATELIMIT_STORAGE_URI`; otherwise unchanged)
- `.env.example` — Local dev env (Plan 03-02 replaces POSTGRES_* with DATABASE_URL)
- `app/__init__.py:27` — Flask-Limiter init site (Plan 03-01 changes one line + adds startup warning)
- `app/database.py:13-29` — `get_database_uri()` POSTGRES_* composition (Plan 03-02 rewrites)
- `README.md:186, 683-693, 716` — Deployment pointer scattered (Plan 03-03 consolidates)
- `docs/sandcastle.md` — SandCastle deploy guide (Plan 03-03 adds "Operational Verification" section)
- `scripts/verify_deployment.py` — Existing verification script (Plan 03-03 extends with WD-OPS-01/04 checks)

### Phase 1 prior decisions to respect
- `.planning/phases/01-foundation/01-CONTEXT.md` D-08 (Flask-Limiter PostgreSQL backend) — superseded by D-G2-01 (Redis); update STATE.md "Key Decisions Locked In" entry per D-G2-05
- D-05/D-06 (Request ID + JSON logging) — already wired in PR #25; tests must keep capturing both

### Project Conventions
- `CLAUDE.md` §"Important Database Notes" — Bootstrap problem: `os.getenv()` in `app/database.py`, NOT `config_get()` — preserved by D-G1-01 (DATABASE_URL is still a bootstrap value)

</canonical_refs>

<decisions>
## Implementation Decisions

### Phase 3 Framing
- **D-01:** Phase 3 is **verify + close gaps**, not fresh implementation. PR #25 already shipped ~80%; this phase formalizes closure rather than rewriting work.
- **D-02:** **Single retroactive `03-VERIFICATION.md`** produced after gap-closure plans complete (via `/gsd-verify-work 3`). Mirrors `02-VERIFICATION.md` structure. Single source of truth for the 25 requirements.
- **D-03:** **Three separate atomic plans:**
  - 03-01 — Redis-backed Flask-Limiter swap
  - 03-02 — `DATABASE_URL` refactor in `app/database.py`
  - 03-03 — README deployment-pointer cleanup + operational evidence script
  Plans 03-01 and 03-02 touch disjoint files and may wave-parallelize. 03-03 runs after.
- **D-04:** **Cross-phase triage performed:** PR #25 also shipped Phase 4 (Authlib OIDC) and Phase 5 (Alembic baseline). A unified audit at `.planning/PR-25-AUDIT.md` maps every PR #25 commit → requirement → phase across 3/4/5 with one set of HOW decisions for the gap-closure plans. Phase 4 and Phase 5 receive thin CONTEXT.md stubs that defer to the audit.
- **D-05:** **HOW decisions live in `PR-25-AUDIT.md`** (D-G1-* through D-G5-*), not duplicated here. The plan-phase agent reads the audit for closure detail. This CONTEXT.md captures the framing only.

### Cross-phase coordination
- **D-06:** WD-CFG-02 (Phase 3) and WD-DB-01 (Phase 5) describe the same `DATABASE_URL` refactor. Plan 03-02 satisfies both. Mark complete in REQUIREMENTS.md under both phase rows after 03-02 ships. Phase 5 retains ownership of WD-DB-02..05 only.
- **D-07:** WD-AUTH-08 (the X-MS-CLIENT-PRINCIPAL-NAME sweep) is Phase 4 work, not Phase 3 — even though the residual references showed up during this audit. Captured in `PR-25-AUDIT.md` Gap G3 / D-G3-* and deferred to Phase 4's Plan 04-01.

### Operator-confirmed requirements
- **D-08:** WD-OPS-01 (portal catalog registration) and WD-OPS-04 (GitHub webhook) close via **operator confirmation in 03-VERIFICATION.md**, not code. Plan 03-03 extends `scripts/verify_deployment.py` with three live-deployment checks; the operator runs them and records the date/initials in 03-VERIFICATION.md.

### Claude's Discretion (planner decides during 03-* PLAN.md generation)
- Exact wording of the production-mode warning when `RATELIMIT_STORAGE_URI=memory://` (D-G2-02 requires the warning; phrasing is tactical)
- Whether to extract `get_database_uri()` into a small helper (`_resolve_database_url()`) for testability or inline the os.environ read
- README.md line-by-line wording for the deployment-pointer rewrite (D-G5-01..03 specify intent; planner picks copy)
- Whether `verify_deployment.py` writes its checklist to stdout, JSON, or markdown (D-G4-01 requires the three checks; output format is tactical)

</decisions>

<specifics>
## Specific Ideas

- The audit doc references real commit SHAs (`fdb6ff2`, `11161a0`, `e760af5`, `fbbfa4d`, `4ee7d3c`, `35c1c1f`, `01b291c`) for traceability — use these when annotating verification entries.
- Operator runbook style: `scripts/cutover/README.md` is the established reference for operational sequences (numbered steps, env-var prerequisites, idempotent re-run guidance). Plan 03-03's verify script and ops-evidence section should match that voice.
- Per Phase 1 SEC-03 deviation note: the Flask-Limiter swap is a **scope deferral closure** — the deviation was knowingly logged with this phase as the closure point. Reference the deviation explicitly in 03-01 SUMMARY.md.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/verify_deployment.py` — already exists per `README.md:518`; extend rather than create a new script (D-G4-01)
- `scripts/cutover/README.md` — operator-runbook voice reference for the WD-OPS evidence section
- `Limiter` import pattern at `app/__init__.py:9-27` — single-line storage_uri swap is the only initialization change needed (D-G2-02)
- `DatabaseConnection` class at `app/database.py:60-93` — uses `get_database_uri()` so a single helper rewrite covers both Flask-app and standalone-script paths (D-G1-04)

### Established Patterns
- `os.environ.get("VAR", default)` for bootstrap config (CLAUDE.md "Bootstrap problem") — preserved by D-G1-01
- Phase 1 D-06 JSON logging — Plan 03-01's startup warning should emit through the JSON logger so it surfaces in `docker logs` (not a print statement)
- Phase 2 testcontainers Postgres fixture (`tests/conftest.py`) returns a full DSN string — already compatible with D-G1-01 (no test changes needed)

### Integration Points
- `.env.sandcastle.example` is a contract file — every key listed here must be set in the SandCastle portal before container starts. Plan 03-01 adds `RATELIMIT_STORAGE_URI=redis://redis:6379/0`; Plan 03-02 documents that `POSTGRES_*` keys are no longer needed.
- The portal env-var injection sequence (worker writes `.env`, compose loads via `env_file`) is fixed by post-PR commit `4ee7d3c` — Plan 03-01's REDIS_URL addition must work through the same path. No compose-file changes required.

</code_context>

<deferred>
## Deferred Ideas

- **Decommission `docs/deployment.md`** — keep with DEPRECATED banner; defer deletion to a future cleanup phase once the legacy Azure App Service environment is fully retired (per D-G5-04). Out of scope for Phase 3.
- **Add Redis to `/health/ready`** — explicitly rejected (D-G2-04). Rate-limit failure is degraded-but-functional; promoting it to readiness would cause unnecessary 503s during Redis maintenance.
- **`flask-oidc` migration** — Authlib was chosen for Phase 4 and is already shipped. Not revisiting library choice.
- **Image size optimization (multi-stage Dockerfile, distroless base)** — Current image meets WD-CONT-03 (<500 MB) per audit. Future optimization is roadmap backlog material, not Phase 3.
- **CI pipeline (GitHub Actions running tests on PR)** — Phase 2 deferred this. Now that the SandCastle webhook deploy path exists (WD-OPS-04), CI is a natural follow-up but explicitly out of Phase 3 scope.

</deferred>

---

*Phase: 03-sandcastle-containerization-deployment*
*Context gathered: 2026-04-26*
