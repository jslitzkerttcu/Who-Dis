---
phase: 03-sandcastle-containerization-deployment
verified: 2026-04-26T00:00:00Z
status: gaps_found
score: 22/27 must-haves verified
overrides_applied: 0
gaps:
  - truth: "App fails fast when DATABASE_URL is missing or unreachable (no silent fallback to a degraded data store)"
    status: failed
    reason: "Plan 03-02 made get_database_uri() raise RuntimeError on missing DATABASE_URL, but app/__init__.py:91-104 wraps init_db() in a broad except Exception and silently falls back to sqlite:///logs/app.db. The system-level fail-fast contract is not met. Encrypted config + audit logs would be written to a stray SQLite file while /health/ready may still return 200 because db.session.execute('SELECT 1') works against SQLite. This violates Plan 03-02's stated purpose, threat T-03-02-02 mitigation, and the Phase 3 goal that the app is 'configured entirely via environment variables' — POSTGRES is silently substituted with SQLite at /app/logs/app.db."
    artifacts:
      - path: "app/__init__.py"
        issue: "Lines 91-104: `try: init_db(app) except Exception: ... SQLALCHEMY_DATABASE_URI = sqlite:///logs/app.db ... db.init_app(app) ... 'Falling back to SQLite database'`. Catches the new RuntimeError and masks it."
    missing:
      - "Delete the SQLite fallback block (app/__init__.py:96-104). Let init_db() propagate so RuntimeError surfaces and aborts startup."
      - "If softer failure is required, log at ERROR and sys.exit(1) instead of continuing on SQLite."
      - "Update threat-model record T-03-02-02 evidence to reflect the actual call-site behavior."

  - truth: "README install/onboarding instructions match the new DATABASE_URL-only contract (no removed POSTGRES_* env vars)"
    status: failed
    reason: "Plan 03-02 deleted POSTGRES_HOST/PORT/DB/USER/PASSWORD from app/database.py and .env.example, and Plan 03-03 fixed the deployment-pointer lines in README. But README.md:134-148 'Configure minimal environment' step still demands operators write the five removed POSTGRES_* keys into .env. A new contributor following step 5 verbatim ends up without DATABASE_URL, and step 7 (`python run.py`) raises RuntimeError. The onboarding flow is broken end-to-end."
    artifacts:
      - path: "README.md"
        issue: "Lines 134-148: 'cat > .env << EOF / POSTGRES_HOST=localhost / POSTGRES_PORT=5432 / POSTGRES_DB=whodis_db / POSTGRES_USER=whodis_user / POSTGRES_PASSWORD=your-secure-password / WHODIS_ENCRYPTION_KEY=...'"
    missing:
      - "Replace lines 134-148 with the DATABASE_URL form: `DATABASE_URL=postgresql://whodis_user:your-secure-password@localhost:5432/whodis_db`"
      - "Verify the EncryptionService.generate_key() invocation referenced in the same block — confirm it still exists or replace with the Fernet form used in .env.sandcastle.example."

  - truth: "SECRET_KEY is sourced from environment with no per-worker random fallback in production (sessions remain stable across multi-worker gunicorn)"
    status: failed
    reason: "WD-CFG-05 requires every key in .env.sandcastle.example to be set before the container starts, and WD-CONT-02 ships multi-worker gunicorn (default 2). But app/__init__.py:75 reads `os.environ.get('SECRET_KEY') or os.urandom(32).hex()` — if SECRET_KEY is absent (or accidentally blank), each gunicorn worker generates a different random key. Sessions signed by worker A are rejected by worker B, breaking session continuity, CSRF tokens, and audit attribution intermittently. Failure is silent — no warning, no /health/ready breakage. This is a critical hardening gap for the goal 'WhoDis runs as a hosted SandCastle application'."
    artifacts:
      - path: "app/__init__.py"
        issue: "Line 75: `app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(32).hex()`"
    missing:
      - "Replace with: if SECRET_KEY missing AND FLASK_ENV=production, raise RuntimeError with operator hint pointing at .env.sandcastle.example. Otherwise (dev) warn and use ephemeral key."

  - truth: "Production-mode startup warning fires when FLASK_ENV=production and RATELIMIT_STORAGE_URI is unset/memory:// (Plan 03-01 truth #3 — works for both container and non-container deploys)"
    status: partial
    reason: "Plan 03-01 truth #3 holds for SandCastle (env vars injected by container before Python launches), but the warning is silently bypassed for any non-container deployment relying on python-dotenv. app/__init__.py module body (line 28) reads RATELIMIT_STORAGE_URI at import time, before run.py:4 calls load_dotenv(). The same env var is then re-read at line 117 inside create_app(); for SandCastle this works because the portal injects env vars pre-process, but for local dev/laptop testing of FLASK_ENV=production the warning would never fire AND the limiter would silently sit on memory:// even with the var set in .env. Container deploys are safe; non-container deploys are not. SC#2 is satisfied for the SandCastle target, so this is a partial gap rather than a full blocker."
    artifacts:
      - path: "app/__init__.py"
        issue: "Lines 26-29: module-level Limiter(...) constructor reads os.environ.get('RATELIMIT_STORAGE_URI', 'memory://') before run.py invokes load_dotenv()."
      - path: "run.py"
        issue: "Lines 1-4: `from app import create_app` is line 1; `load_dotenv()` is line 4. Module-level code in app/__init__.py runs before load_dotenv."
    missing:
      - "Either move load_dotenv() into app/__init__.py before the limiter constructor, or defer storage_uri selection to limiter.init_app(app) time using app.config['RATELIMIT_STORAGE_URI'] (Flask-Limiter 3.x recommended pattern)."

  - truth: "Tech-stack/auth documentation in README accurately reflects the Phase-9 Keycloak OIDC migration (no stale Azure AD SSO claims)"
    status: failed
    reason: "Plan 03-03 fixed deployment-pointer lines but did not sweep auth references. README.md:80 ('| Authentication | Azure AD SSO |') and README.md:391 ('Azure AD SSO: Checks X-MS-CLIENT-PRINCIPAL-NAME header from Azure App Service') still describe pre-Phase-9 auth. Combined with the broken install block (CR-02), the user-facing onboarding doc is partially incorrect for a SandCastle-deployed app. Although WD-AUTH-08 (Azure header sweep) is formally Phase 4 work per CONTEXT D-07, the README inconsistencies surface during Phase 3 verification because they intersect with the 'WhoDis runs as a hosted SandCastle application' goal claim that the doc points new operators at the canonical deploy path."
    artifacts:
      - path: "README.md"
        issue: "Line 80: Tech Stack table row 'Authentication | Azure AD SSO | Single sign-on with role-based access control'"
      - path: "README.md"
        issue: "Line 391: 'Azure AD SSO: Checks `X-MS-CLIENT-PRINCIPAL-NAME` header from Azure App Service'"
      - path: "README.md"
        issue: "Lines 30, 55: incidental 'Azure AD'-flavored language (per REVIEW WR-01 / WR-02)"
    missing:
      - "Update line 80 Tech Stack row to 'Keycloak OIDC (Authlib)' with link to docs/sandcastle.md §'Keycloak OIDC setup'"
      - "Update line 391-393 auth description to reference the Keycloak OIDC flow"
      - "Sweep lines 30, 55 for stale Azure AD wording — accept Phase 4 will revisit but do not leave as-is during Phase 3 close"

deferred:
  - truth: "Stub validation of CHANGEME placeholders in .env.sandcastle.example secrets (rejection at startup)"
    addressed_in: "Backlog / Future hardening"
    evidence: "REVIEW IN-01 explicitly notes 'out of scope for this phase but worth a backlog item' — not in any plan must_haves; not a Phase 3 closure dependency."
  - truth: "tests/conftest.py DATABASE_URL teardown / monkeypatch usage"
    addressed_in: "Phase 5 (Database Migration)"
    evidence: "Phase 5 owns Alembic infrastructure and test-fixture parity per ROADMAP. WR-03 is a test-isolation defect, not a Phase 3 must-have."
  - truth: "init_db() should re-raise db.create_all() exceptions instead of swallowing them"
    addressed_in: "Phase 5 (Database Migration)"
    evidence: "Phase 5 success criteria include schema-application via Alembic on container start; Plan 04 docstring (alembic baseline) makes this exception path obsolete in steady-state."

human_verification: []
---

# Phase 3: SandCastle Containerization & Deployment Verification Report

**Phase Goal:** WhoDis runs as a hosted SandCastle application — packaged in a production Docker image, served by gunicorn through Traefik at `whodis.sandcastle.ttcu.com`, configured entirely via environment variables, observable through structured logs and health probes
**Verified:** 2026-04-26T00:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

The phase goal is **mostly achieved** but five gaps undermine the "configured entirely via environment variables" pillar of the goal statement. The container, networking, health-probe, and operational pieces are confirmed working in production (operator confirmed live SandcastleVerifier --sandcastle PASS on 2026-04-26 and the SandCastle portal shows who-dis green). The Redis-backed Flask-Limiter swap, DATABASE_URL refactor at the function level, and ops-evidence script all shipped per Plans 03-01/02/03.

The gaps are concentrated in **fail-fast configuration discipline** and **documentation accuracy**:
- A SQLite fallback in app/__init__.py masks the DATABASE_URL fail-fast contract (CR-01).
- The README install block still demands removed POSTGRES_* env vars (CR-02).
- SECRET_KEY has a per-worker random fallback that silently breaks multi-worker sessions (CR-03).
- Limiter storage_uri is read before load_dotenv() — masked in containers but broken locally (CR-04).
- README tech-stack/auth sections still describe Azure AD SSO (WR-01/WR-02).

These are the same critical issues surfaced by 03-REVIEW.md. They overlap with the Plan must_haves (truths around fail-fast DATABASE_URL, .env-vars-only configuration, and README accuracy) — not merely follow-up cleanup outside scope. Phase goal language explicitly says "configured entirely via environment variables", which the SQLite fallback and SECRET_KEY random fallback both undermine.

### Observable Truths

| #   | Truth (from ROADMAP Success Criteria + Plan must_haves) | Status     | Evidence                                                                                                                                                                                                                                                                                              |
| --- | -------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `docker compose -f docker-compose.sandcastle.yml up` brings the app online and serves traffic at https://whodis.sandcastle.ttcu.com through Traefik with HTTPS-only and a valid Let's Encrypt cert (SC#1) | ✓ VERIFIED | docker-compose.sandcastle.yml:23-29 has Traefik labels with `Host(\`who-dis.sandcastle.ttcu.com\`)`, `tls=true`, `certresolver=letsencrypt`, `loadbalancer.server.port=5000`. Operator confirmed SandcastleVerifier --sandcastle returned all PASS on 2026-04-26 and portal shows who-dis green.       |
| 2   | The container runs gunicorn as a non-root user with `GUNICORN_WORKERS` configurable (default 2) (SC#2 part 1)             | ✓ VERIFIED | Dockerfile:5 (`useradd -r -g app -u 10001 app`), Dockerfile:28 (`USER app`), docker-entrypoint.sh:56-63 invokes gunicorn with `--workers "${GUNICORN_WORKERS:-2}"`, Dockerfile:36 sets default `GUNICORN_WORKERS=2`.                                                                                  |
| 3   | Flask-Limiter rate counters are shared across workers via Redis (REDIS_URL from the SandCastle internal network) (SC#2 part 2) | ✓ VERIFIED | app/__init__.py:26-29 `Limiter(storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"))`. requirements.txt:18 `redis>=5,<6`. .env.sandcastle.example:40 documents `RATELIMIT_STORAGE_URI=redis://redis:6379/0`. Production deploy (operator confirmed) reads from the portal env-var store.   |
| 4   | All runtime configuration comes from environment variables documented in `.env.sandcastle.example` — no hardcoded secrets, no `instance/` files, no JSON config baked into the image (SC#3) | ✗ FAILED   | **CR-01 BLOCKER:** app/__init__.py:91-104 silently falls back to `sqlite:///logs/app.db` when init_db() raises (e.g., DATABASE_URL missing or Postgres temporarily down). This violates the "configured entirely via env vars" claim — when the env-var contract fails, the app silently substitutes a non-env-configured data store. **CR-03 also relevant:** SECRET_KEY falls back to per-worker random bytes if the env var is unset, undermining "all runtime configuration comes from environment variables". |
| 5   | `/health` returns 200 unauthenticated for the SandCastle poller (SC#4 part 1)                                              | ✓ VERIFIED | app/blueprints/health/__init__.py:32-36 `@health_bp.route("/health")` returns `jsonify({"status": "healthy"}), 200`. No `@auth_required` decorator. SandcastleVerifier confirmed live PASS on 2026-04-26.                                                                                              |
| 6   | `/health/ready` returns 503 when the database is unreachable (SC#4 part 2)                                                 | ✓ VERIFIED | app/blueprints/health/__init__.py:46-71 executes `db.session.execute(text("SELECT 1"))`, returns 503 with `{"status": "degraded", "database": {"connected": false, ...}}` on exception.                                                                                                              |
| 7   | Structured JSON logs go to stdout/stderr (SC#4 part 3)                                                                     | ✓ VERIFIED | app/__init__.py:32-53 `_configure_json_logging()` installs `jsonlogger.JsonFormatter` on root logger via StreamHandler (stdout). RequestIdFilter injects request_id into every record.                                                                                                                |
| 8   | The Dockerfile `HEALTHCHECK` exercises `/health` every 30s (SC#4 part 4)                                                   | ✓ VERIFIED | Dockerfile:32-33 `HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 CMD curl -fsS http://localhost:5000/health \|\| exit 1`.                                                                                                                                                          |
| 9   | WhoDis is registered in the SandCastle portal catalog with auto-deploy on `main` push via webhook (SC#5 part 1)            | ✓ VERIFIED | Operator confirmed 2026-04-26: SandCastle portal shows who-dis with green badge; GitHub webhook last delivery shows green tick. Recorded per docs/sandcastle.md "Operational Verification" runbook.                                                                                                   |
| 10  | `docs/sandcastle.md` documents the env var matrix, deployment flow, and rollback procedure (SC#5 part 2)                   | ✓ VERIFIED | docs/sandcastle.md has §"Environment variable matrix (WD-CFG-05)" (line 17), §"Deploy flow (WD-OPS-02)" (line 136), §"Rollback / Disaster Recovery (DEPL-04)" (line 169), §"Health monitoring" (line 208), §"Operational Verification" (line 235).                                                |
| 11  | Legacy Azure App Service notes are removed or marked deprecated (SC#5 part 3)                                              | ✓ VERIFIED | README.md:186 `**[Legacy Deployment](docs/deployment.md)** - Deprecated; pre-Phase-9 Azure App Service notes`. README.md:694 `The legacy Azure App Service deployment path... is deprecated and will be decommissioned post-Phase-9 verification.`                                                   |
| 12  | app/database.py reads DATABASE_URL exclusively — no POSTGRES_* variable reads remain (Plan 03-02 truth)                    | ✓ VERIFIED | grep -c "POSTGRES_" app/database.py = 0; app/database.py:24 `url = os.getenv("DATABASE_URL")`.                                                                                                                                                                                                       |
| 13  | get_database_uri() raises RuntimeError with a clear message when DATABASE_URL is not set (Plan 03-02 truth)                | ✓ VERIFIED (function-level) | app/database.py:25-30 raises RuntimeError with operator-actionable hint.                                                                                                                                                                                                                            |
| 14  | App fails fast when DATABASE_URL is missing (system-level — caller does not silently catch and fallback) — derived from Plan 03-02 purpose statement | ✗ FAILED   | **CR-01 BLOCKER:** app/__init__.py:96-104 catches the RuntimeError and falls back to SQLite. See gap entry above.                                                                                                                                                                                  |
| 15  | .env.example uses DATABASE_URL instead of POSTGRES_HOST/PORT/DB/USER/PASSWORD (Plan 03-02 truth)                           | ✓ VERIFIED | grep -c "POSTGRES_" .env.example = 0; .env.example:8 `DATABASE_URL=postgresql://whodis_user:password@localhost:5432/whodis_db`.                                                                                                                                                                       |
| 16  | scripts/verify_deployment.py get_db_connection() uses DATABASE_URL (not POSTGRES_* vars) (Plan 03-02 truth)                | ✓ VERIFIED | scripts/verify_deployment.py:63-71 uses `psycopg2.connect(dsn=os.getenv("DATABASE_URL"))`; grep "POSTGRES_" returns 0.                                                                                                                                                                              |
| 17  | DatabaseConnection.connect() and init_db() continue to call get_database_uri() unchanged (Plan 03-02 truth)                | ✓ VERIFIED | app/database.py:36 (init_db), app/database.py:74 (DatabaseConnection.connect) both call get_database_uri() unchanged.                                                                                                                                                                                |
| 18  | Flask-Limiter falls back to memory:// when RATELIMIT_STORAGE_URI is unset (local dev and tests work unchanged) (Plan 03-01 truth) | ✓ VERIFIED | app/__init__.py:28 `storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://")`. Plan 03-01 SUMMARY shows `python -c "from app import limiter; print('OK')"` succeeded without Redis.                                                                                                       |
| 19  | A structured JSON warning fires at startup when FLASK_ENV=production and RATELIMIT_STORAGE_URI is absent or memory:// (Plan 03-01 truth) | ⚠️ PARTIAL | Container path works (env vars injected pre-process). Non-container deploys (relying on load_dotenv) miss it because Limiter is initialized at module import time (CR-04). For SandCastle target, this passes. For full goal coverage, partial.                                                  |
| 20  | requirements.txt lists redis>=5,<6 immediately after Flask-Limiter (Plan 03-01 truth)                                      | ✓ VERIFIED | requirements.txt:17 `Flask-Limiter>=3.5,<4`, line 18 `redis>=5,<6`.                                                                                                                                                                                                                                  |
| 21  | .env.sandcastle.example documents RATELIMIT_STORAGE_URI=redis://redis:6379/0 in a labeled section (Plan 03-01 truth)       | ✓ VERIFIED | .env.sandcastle.example:36-40 has `# --- Rate limiting (WD-NET-01 / SEC-03)` block with `RATELIMIT_STORAGE_URI=redis://redis:6379/0`.                                                                                                                                                                |
| 22  | README.md line ~186 points to docs/sandcastle.md as canonical deployment guide (Plan 03-03 truth)                          | ✓ VERIFIED | README.md:186 `**[Deployment Guide](docs/sandcastle.md)** - SandCastle deployment (canonical)`. README.md:187 marks docs/deployment.md as Legacy.                                                                                                                                                    |
| 23  | README.md line ~716 points to docs/sandcastle.md (not docs/deployment.md) for sysadmins (Plan 03-03 truth)                 | ✓ VERIFIED | README.md:717 `**System administrators?** Check the [Admin Tasks Guide](docs/user-guide/admin-tasks.md) and [SandCastle Deployment Guide](docs/sandcastle.md)`.                                                                                                                                       |
| 24  | docs/sandcastle.md has an Operational Verification section for WD-OPS-01 and WD-OPS-04 (Plan 03-03 truth)                  | ✓ VERIFIED | docs/sandcastle.md:235-280 contains "## Operational Verification (WD-OPS-01, WD-OPS-04)" with subsections, bash code fence, and expected [PASS] output.                                                                                                                                              |
| 25  | scripts/verify_deployment.py --sandcastle flag runs 3 live-deployment checks with 0/1 exit (Plan 03-03 truth)              | ✓ VERIFIED | scripts/verify_deployment.py:374-485 SandcastleVerifier class with check_sandcastle_dns/health/ready; main() routes --sandcastle to it; sys.exit(0 if success else 1).                                                                                                                                |
| 26  | Operator confirmed WD-OPS-01 and WD-OPS-04 by running the script and recording results (Plan 03-03 truth)                  | ✓ VERIFIED | Operator confirmed in user prompt: "SandcastleVerifier --sandcastle script returned all PASS, SandCastle portal shows who-dis green, GitHub webhook shows green tick on last delivery."                                                                                                              |
| 27  | README install/onboarding instructions match the new DATABASE_URL-only contract — derived from goal "configured entirely via env vars documented in .env.sandcastle.example" | ✗ FAILED   | **CR-02 BLOCKER:** README.md:134-148 still demands operators set POSTGRES_HOST/PORT/DB/USER/PASSWORD in .env. New operators following onboarding hit RuntimeError. See gap entry above.                                                                                                              |

**Score:** 22/27 truths verified (1 PARTIAL, 4 FAILED including derived system-level fail-fast and onboarding accuracy)

### Required Artifacts

| Artifact                                | Expected                                                              | Status     | Details                                                                                                  |
| --------------------------------------- | --------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------- |
| `Dockerfile`                            | Production image, non-root, gunicorn, HEALTHCHECK, FLASK_ENV=production | ✓ VERIFIED | 39 lines; non-root app user UID 10001; HEALTHCHECK --interval=30s; ENV FLASK_ENV=production GUNICORN_WORKERS=2 |
| `docker-compose.sandcastle.yml`         | Traefik labels, proxy + internal networks, healthcheck                | ✓ VERIFIED | 41 lines; Host rule `who-dis.sandcastle.ttcu.com`; certresolver=letsencrypt; networks proxy + internal external=true |
| `docker-entrypoint.sh`                  | DATABASE_URL guard, alembic upgrade, gunicorn exec                    | ✓ VERIFIED | Line 12 `: "${DATABASE_URL:?...}"`; line 31 `alembic upgrade head`; line 56-63 gunicorn with GUNICORN_WORKERS |
| `app/blueprints/health/__init__.py`     | /health (200), /health/ready (200/503), unauthenticated               | ✓ VERIFIED | Three routes; no @auth_required; SELECT 1 probe in readiness                                             |
| `app/__init__.py`                       | Limiter with storage_uri from env, ProxyFix, JSON logging             | ⚠️ ORPHANED | Limiter init correct but storage_uri read before load_dotenv (CR-04). SQLite fallback masks DATABASE_URL contract (CR-01). SECRET_KEY per-worker random fallback (CR-03). |
| `app/database.py`                       | DATABASE_URL-only resolution, RuntimeError on missing                 | ⚠️ ORPHANED | get_database_uri() correct at function level, but caller's behavior negates fail-fast intent (system-level, see CR-01) |
| `requirements.txt`                      | redis>=5,<6 added                                                     | ✓ VERIFIED | Line 18                                                                                                  |
| `.env.sandcastle.example`               | All required env vars documented including RATELIMIT_STORAGE_URI       | ✓ VERIFIED | 41 lines; FLASK_ENV, SECRET_KEY, GUNICORN_WORKERS, DATABASE_URL, KEYCLOAK_*, LDAP_*, GRAPH_*, GENESYS_*, RATELIMIT_STORAGE_URI |
| `.env.example`                          | DATABASE_URL replaces POSTGRES_*                                      | ✓ VERIFIED | Line 8 DATABASE_URL; POSTGRES_ count = 0                                                                 |
| `scripts/verify_deployment.py`          | --sandcastle flag, 3 live checks                                      | ✓ VERIFIED | SandcastleVerifier class lines 374-485; main() routes via argparse                                       |
| `docs/sandcastle.md`                    | Env var matrix, Keycloak setup, deploy flow, rollback, ops evidence   | ✓ VERIFIED | 280 lines; all required sections present including Operational Verification                              |
| `README.md` (deployment pointers)       | line 186 + line 717 point at docs/sandcastle.md                       | ✓ VERIFIED | Both lines updated per Plan 03-03                                                                         |
| `README.md` (install block)             | DATABASE_URL replaces POSTGRES_*                                      | ✗ STUB     | Lines 134-148 still demand POSTGRES_HOST/PORT/DB/USER/PASSWORD — onboarding broken                       |
| `README.md` (auth/tech-stack rows)      | Reflect Phase 9 Keycloak OIDC migration                               | ✗ STUB     | Lines 80, 391-393 still describe Azure AD SSO and X-MS-CLIENT-PRINCIPAL-NAME header                       |

### Key Link Verification

| From                                    | To                                          | Via                                       | Status      | Details                                                                                                  |
| --------------------------------------- | ------------------------------------------- | ----------------------------------------- | ----------- | -------------------------------------------------------------------------------------------------------- |
| app/__init__.py:limiter                 | RATELIMIT_STORAGE_URI env var               | os.environ.get at module level            | ⚠️ PARTIAL  | Read at module-import time, before load_dotenv. Works for container deploys; broken for non-container.   |
| app/__init__.py:create_app              | app.logger.warning (production-mode warn)   | post-init guard after limiter.init_app    | ⚠️ PARTIAL  | Same root cause — env var read inconsistency between module body and create_app body                     |
| app/database.py:get_database_uri()      | DATABASE_URL env var                        | os.getenv with RuntimeError on missing    | ✓ WIRED     | RuntimeError raised correctly at function level                                                          |
| app/__init__.py:create_app              | app/database.py:init_db                     | Direct call inside try/except             | ✗ NOT_WIRED | except Exception swallows RuntimeError and switches to SQLite — fail-fast contract broken                |
| app/database.py:DatabaseConnection.connect | get_database_uri()                       | direct call                               | ✓ WIRED     | Unchanged from pre-refactor                                                                              |
| app/database.py:init_db                 | get_database_uri()                          | direct call                               | ✓ WIRED     | Unchanged from pre-refactor                                                                              |
| README.md:186                           | docs/sandcastle.md                          | markdown link                             | ✓ WIRED     | Plan 03-03 fix verified                                                                                   |
| docs/sandcastle.md Operational Verification | scripts/verify_deployment.py --sandcastle | bash code fence                           | ✓ WIRED     | Plan 03-03 fix verified                                                                                   |
| scripts/verify_deployment.py --sandcastle | https://who-dis.sandcastle.ttcu.com/health | requests.get with hardcoded const         | ✓ WIRED     | SANDCASTLE_URL constant; SSRF mitigation per T-03-03-01                                                  |

### Behavioral Spot-Checks

| Behavior                                                | Command                                              | Result | Status |
| ------------------------------------------------------- | ---------------------------------------------------- | ------ | ------ |
| Python syntax valid in scripts/verify_deployment.py     | `python -c "import ast; ast.parse(open(...))"`      | OK     | ✓ PASS |
| Python syntax valid in app/database.py                  | (verified by import in Plan 03-02)                   | OK     | ✓ PASS |
| Python syntax valid in app/__init__.py                  | (verified by Plan 03-01 `from app import limiter`)   | OK     | ✓ PASS |
| POSTGRES_ env vars removed from app/database.py          | `grep -c POSTGRES_ app/database.py`                  | 0      | ✓ PASS |
| POSTGRES_ env vars removed from .env.example             | `grep -c POSTGRES_ .env.example`                     | 0      | ✓ PASS |
| POSTGRES_ env vars removed from verify_deployment.py     | `grep -c POSTGRES_ scripts/verify_deployment.py`     | 0      | ✓ PASS |
| POSTGRES_ env vars NOT in README.md install block        | `grep -c POSTGRES_ README.md`                        | 5      | ✗ FAIL (lines 139-143) |
| redis pin in requirements.txt                            | `grep -c "^redis>=" requirements.txt`                | 1      | ✓ PASS |
| Live SandcastleVerifier --sandcastle exits 0             | (operator-confirmed 2026-04-26)                      | PASS   | ✓ PASS |

### Requirements Coverage

| Requirement   | Source Plan       | Description                                                                                  | Status      | Evidence                                                                                       |
| ------------- | ----------------- | -------------------------------------------------------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------- |
| WD-CONT-01    | 03-03             | Dockerfile builds runnable image on python:3.12-slim, runs as non-root user                 | ✓ SATISFIED | Dockerfile:2 base; line 5 useradd; line 28 USER app                                            |
| WD-CONT-02    | 03-01, 03-03      | gunicorn, GUNICORN_WORKERS configurable default 2                                            | ✓ SATISFIED | Dockerfile:36 default; entrypoint:57 `--workers "${GUNICORN_WORKERS:-2}"`                      |
| WD-CONT-03    | 03-03             | Production-only deps; image < 500 MB                                                         | ✓ SATISFIED | Dockerfile:21 only requirements.txt; no dev/test installs; live deploy operates in prod (operator confirmed) |
| WD-CONT-04    | 03-03             | docker-compose.sandcastle.yml with Traefik labels and proxy+internal networks               | ✓ SATISFIED | compose file lines 19-29                                                                        |
| WD-CONT-05    | 03-03             | Container starts cleanly with `docker compose up` against populated .env                    | ✓ SATISFIED | Operator confirmed live deploy passing 2026-04-26                                              |
| WD-CFG-01     | 03-02             | All runtime config from env vars; no instance/, no JSON config baked in                     | ✗ BLOCKED   | **CR-01:** SQLite fallback creates a non-env-configured datastore at logs/app.db when DATABASE_URL fails. **CR-03:** SECRET_KEY random fallback per worker — config is not "from env vars" when env var missing. |
| WD-CFG-02     | 03-02             | DATABASE_URL replaces composition logic; app connects only via this URL                     | ⚠️ PARTIAL   | Function-level satisfied (app/database.py reads DATABASE_URL only). System-level violated by CR-01 SQLite fallback. |
| WD-CFG-03     | 03-03             | Encrypted-config secrets exposed via env vars OR encrypted-config reads master key from env | ✓ SATISFIED | .env.sandcastle.example documents direct env-var injection for KEYCLOAK_*, LDAP_*, GRAPH_*, GENESYS_*; portal worker writes .env from portal env-var store (per docs/sandcastle.md) |
| WD-CFG-04     | 03-03             | FLASK_ENV=production and DEBUG forced false; DB toggle remains available defaulting off    | ✓ SATISFIED | Dockerfile:35 `ENV FLASK_ENV=production`; FLASK_DEBUG read via get_flask_config_from_env (app/__init__.py:131-136) |
| WD-CFG-05     | 03-01, 03-03      | .env.sandcastle.example documents every required env var                                    | ✓ SATISFIED | File lists FLASK_ENV, SECRET_KEY, GUNICORN_WORKERS, DATABASE_URL, KEYCLOAK_*, LDAP_*, GRAPH_*, GENESYS_*, RATELIMIT_STORAGE_URI |
| WD-HEALTH-01  | 03-03             | GET /health returns 200 unauthenticated                                                     | ✓ SATISFIED | health/__init__.py:32-36; live PASS confirmed                                                  |
| WD-HEALTH-02  | 03-03             | GET /health/ready returns 200 only when DB reachable; 503 otherwise                        | ✓ SATISFIED | health/__init__.py:46-71; live PASS confirmed                                                  |
| WD-HEALTH-03  | 03-03             | Logs to stdout/stderr in JSON format; no file logging in container                          | ✓ SATISFIED | app/__init__.py:32-53 JsonFormatter on root logger StreamHandler                               |
| WD-HEALTH-04  | 03-03             | Dockerfile HEALTHCHECK hits /health every 30s with 10s timeout                              | ✓ SATISFIED | Dockerfile:32-33                                                                               |
| WD-NET-01     | 03-01, 03-03      | Compose service on proxy + internal networks                                                | ✓ SATISFIED | compose file lines 19-21, 37-41                                                                 |
| WD-NET-02     | 03-03             | Traefik labels HTTPS-only, certResolver=letsencrypt                                         | ✓ SATISFIED | compose file lines 23-29                                                                        |
| WD-NET-03     | 03-03             | Outbound calls to Graph and Genesys work from container                                     | ✓ SATISFIED | Confirmed by live deploy operator (token refresh background job per app/__init__.py:188-192)   |
| WD-NET-04     | 03-03             | App honors X-Forwarded-Proto/Host via ProxyFix                                              | ✓ SATISFIED | app/__init__.py:62 `ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=0)`         |
| WD-NET-05     | 03-03             | Static assets served correctly through Traefik                                              | ✓ SATISFIED | No special path assumptions; live deploy operator did not flag                                |
| WD-OPS-01     | 03-03             | App registered in SandCastle portal catalog                                                 | ✓ SATISFIED | Operator confirmed: portal shows who-dis green badge on 2026-04-26                            |
| WD-OPS-02     | 03-01, 03-03      | Portal-triggered deploys succeed end-to-end without manual intervention                     | ✓ SATISFIED | Operator confirmed: GitHub webhook last delivery green tick                                    |
| WD-OPS-03     | 03-03             | docs/deployment.md updated; legacy Azure App Service notes deprecated                        | ✓ SATISFIED | README.md:187 marks legacy; README.md:694 deprecation note                                     |
| WD-OPS-04     | 03-03             | GitHub webhook configured for /api/webhooks/github auto-deploy on main push                 | ✓ SATISFIED | Operator confirmed: webhook last delivery green                                                |
| WD-DOC-01     | 03-03             | docs/sandcastle.md exists with env var matrix, Keycloak setup, DB provisioning, deploy flow, rollback | ✓ SATISFIED | docs/sandcastle.md sections covering all required topics                                       |
| WD-DOC-02     | 03-03             | README.md Deployment section points at docs/sandcastle.md and notes local dev with python run.py | ⚠️ PARTIAL   | Deployment section (lines 684-695) is correct. But adjacent install block (134-148) and tech-stack/auth rows (80, 391) contradict the canonical SandCastle path. Documentation pointer correct; documentation accuracy partial. |

**Orphaned requirements:** None — all 25 requirement IDs from REQUIREMENTS.md Phase 3 traceability appear in at least one Plan's `requirements:` field.

**Summary of requirement closure:**
- 22 SATISFIED
- 2 PARTIAL (WD-CFG-02, WD-DOC-02 — function-level satisfied, system-level concerns)
- 1 BLOCKED (WD-CFG-01 — CR-01 + CR-03)

### Anti-Patterns Found

| File                  | Line(s)   | Pattern                                                                       | Severity   | Impact                                                                                          |
| --------------------- | --------- | ----------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------- |
| app/__init__.py       | 75        | `os.environ.get("SECRET_KEY") or os.urandom(32).hex()` per-worker random fallback | 🛑 Blocker | Multi-worker session breakage; silent failure (CR-03)                                          |
| app/__init__.py       | 91-104    | `try: init_db() / except Exception: ... SQLite fallback`                      | 🛑 Blocker | DATABASE_URL fail-fast contract masked; encrypted config / audit logs to stray SQLite (CR-01)  |
| app/__init__.py       | 26-29     | Module-level read of RATELIMIT_STORAGE_URI before load_dotenv()                | ⚠️ Warning | Non-container deploys silently use memory:// even when .env sets the URI (CR-04)               |
| README.md             | 134-148   | Install block demanding removed POSTGRES_* env vars                          | 🛑 Blocker | New-developer onboarding broken (CR-02)                                                        |
| README.md             | 80, 391-393 | "Azure AD SSO" / "X-MS-CLIENT-PRINCIPAL-NAME" still listed as auth path     | ⚠️ Warning | Tech-stack/onboarding accuracy (WR-01/WR-02)                                                   |
| app/database.py       | 53-58     | `db.create_all()` exception swallowed (logs but does not re-raise)            | ⚠️ Warning | Combined with CR-01, silently boots a broken app (WR-06) — deferred to Phase 5                |
| tests/conftest.py     | 66        | `os.environ["DATABASE_URL"] = ...` without try/finally restore                | ℹ️ Info    | Test-isolation concern; deferred to Phase 5                                                    |
| scripts/verify_deployment.py | 8-13 | Module docstring usage block missing --sandcastle                          | ℹ️ Info    | Cosmetic; --sandcastle is in argparse help                                                    |

### Human Verification Required

None — operator already confirmed live SandcastleVerifier --sandcastle PASS, portal green badge, and GitHub webhook green tick on 2026-04-26 (per user prompt). The remaining gaps are all programmatically observable code and documentation defects.

### Gaps Summary

**Five gaps block clean Phase 3 closure.** The phase goal pillar "configured entirely via environment variables" is undermined at three points (CR-01 SQLite fallback, CR-02 README install block, CR-03 SECRET_KEY random fallback), and one supporting truth (production-mode rate-limit warning) is partially broken outside container deploys (CR-04). Documentation accuracy (WR-01/WR-02 Azure AD references) is a fifth gap that overlaps with both the CR-02 onboarding break and the goal that the README points operators at the correct deploy path.

**These gaps are NOT mere follow-up cleanup** — they directly contradict Plan 03-02's stated purpose ("fails loudly... instead of silently connecting to the wrong database"), the threat-model record T-03-02-02 mitigation evidence, the goal statement language ("configured entirely via environment variables"), and the must_have truth derived from the plans about README onboarding parity. The 03-REVIEW.md correctly classified them as critical.

**Operationally the live deployment is up and passing health checks** (operator-confirmed 2026-04-26), so 22 of 27 truths are verified and all the runtime/networking/health-probe pieces of the goal are achieved. But the verification is incomplete because the configuration discipline pillar of the goal has observable defects in the codebase regardless of the green portal badge.

**Group these gaps for a single closure plan** — all five touch app/__init__.py, app/database.py interaction, and README.md, and a single Plan 03-04 (Configuration Discipline Hardening + README Onboarding Sweep) can address them in 4-6 atomic tasks: delete SQLite fallback, fail-fast SECRET_KEY in production, fix Limiter timing, rewrite README install block, sweep README auth rows.

---

_Verified: 2026-04-26_
_Verifier: Claude (gsd-verifier)_
