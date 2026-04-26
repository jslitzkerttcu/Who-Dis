# Phase 3: SandCastle Containerization & Deployment — Pattern Map

**Mapped:** 2026-04-26
**Files analyzed:** 7 (modified; no net-new files except script extension)
**Analogs found:** 7 / 7

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog / Section | Match Quality |
|---|---|---|---|---|
| `app/__init__.py` (Limiter init + startup warning) | config / middleware init | request-response | `app/__init__.py:86-102` (DB init + SQLite warning) | exact — same module, same init pattern |
| `requirements.txt` (add `redis>=5,<6`) | config | n/a | `requirements.txt:17` (existing Flask-Limiter line) | exact |
| `.env.sandcastle.example` (add `RATELIMIT_STORAGE_URI`) | config | n/a | `.env.sandcastle.example:13-14` (DATABASE_URL block) | exact |
| `app/database.py:get_database_uri()` (DATABASE_URL refactor) | utility / bootstrap | request-response | `app/database.py:13-29` (current POSTGRES_* composition) | exact — replacing this function |
| `.env.example` (replace POSTGRES_* with DATABASE_URL) | config | n/a | `.env.example:4-11` (current POSTGRES_* block) | exact |
| `README.md` (lines 186, 716 pointer fix; lines 683-693 unchanged) | documentation | n/a | `README.md:683-693` (current SandCastle paragraph) | exact — adjacent lines |
| `docs/sandcastle.md` (append "Operational Verification" section) | documentation | n/a | `docs/sandcastle.md:207-234` (existing "Health monitoring" + "Phase 9 reference") | role-match — same doc, same voice |
| `scripts/verify_deployment.py` (extend with 3 live checks) | utility script | request-response | `scripts/verify_deployment.py:206-235` (`check_flask_application` method) | exact — same class, same HTTP-check pattern |

---

## Pattern Assignments

### Plan 03-01 — `app/__init__.py` (Limiter init line 27 + startup warning)

**Analog:** `app/__init__.py:86-102` (DB init warning block), lines 107-111 (current Limiter init block)

**Current Limiter init state** (`app/__init__.py:17-27`):
```python
# Module-level Limiter so route modules can `from app import limiter`.
#
# SEC-03: per-user rate limiting on search endpoints. Storage is in-memory
# (Flask-Limiter's default) — Flask-Limiter v3.x dropped the PostgreSQL
# backend, so we ship in-memory now and will swap to Redis during the
# SandCastle integration phase (Redis is available on the SandCastle
# internal network — see .planning/SANDCASTLE-INTEGRATION-REQUIREMENTS.md
# WD-NET-01 and WD-CONT-02). In-memory limits enforce per-worker, which is
# acceptable for the current single/low-worker deployment but MUST be
# revisited when moving to multi-worker on SandCastle.
limiter = Limiter(key_func=get_remote_address)
```

**Target pattern — D-G2-02 specifies:**
```python
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
)
```

**Startup warning analog** (`app/__init__.py:94-102` — SQLite fallback warning using `app.logger.warning`):
```python
        app.logger.error(f"Database initialization failed: {str(e)}")
        # Fallback to SQLite if PostgreSQL fails
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///logs/app.db"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        from app.database import db

        db.init_app(app)
        app.logger.warning("Falling back to SQLite database")
```

**Startup warning for D-G2-02 must follow the same `app.logger.warning(...)` call pattern** — use `app.logger.warning` (not a bare `print` or module-level `logger`) so the message flows through the JSON handler already initialized at that point. The warning fires inside `create_app()` after `limiter.init_app(app)` (line 111). Guard condition: `os.environ.get("FLASK_ENV") == "production"` and `RATELIMIT_STORAGE_URI` is absent or `"memory://"`.

**Limiter `init_app` block** (`app/__init__.py:107-111`):
```python
    # SEC-03: initialize Flask-Limiter against this app. Default in-memory
    # storage; Retry-After/RateLimit-* headers enabled so 429 responses
    # carry actionable backoff data for clients.
    app.config["RATELIMIT_HEADERS_ENABLED"] = True
    limiter.init_app(app)
```
The startup warning is added immediately after `limiter.init_app(app)` so the `app` logger is available.

---

### Plan 03-01 — `requirements.txt` (add redis client)

**Current state** (`requirements.txt:17`):
```
Flask-Limiter>=3.5,<4
```

**Target:** Insert `redis>=5,<6` immediately after Flask-Limiter (D-G2-03). No other lines change.

---

### Plan 03-01 — `.env.sandcastle.example` (add RATELIMIT_STORAGE_URI)

**Analog pattern** (`.env.sandcastle.example:13-14` — grouped section with comment header):
```
# --- Database (WD-CFG-02 / WD-DB-01) ------------------------------------------
# Provided by `provision-db.sh who-dis` on the SandCastle host
DATABASE_URL=postgresql://who-dis_user:CHANGEME@postgres:5432/who-dis_db
```

**Target pattern** — new section added below Genesys block (D-G2-01):
```
# --- Rate limiting (WD-NET / SEC-03) ------------------------------------------
# Redis service is provided by the SandCastle internal network (WD-NET-01).
# The 'redis' hostname resolves inside the internal network without compose changes.
RATELIMIT_STORAGE_URI=redis://redis:6379/0
```

---

### Plan 03-02 — `app/database.py:get_database_uri()` (DATABASE_URL refactor)

**Current state to be replaced** (`app/database.py:13-29`):
```python
def get_database_uri():
    """Get PostgreSQL database URI from environment variables

    Note: We must use os.getenv here instead of config_get because
    the configuration service needs a database connection to function.
    PostgreSQL credentials must remain in environment variables.
    """
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "whodis_db")
    user = os.getenv("POSTGRES_USER", "whodis_user")
    password = os.getenv("POSTGRES_PASSWORD", "")

    if not password:
        logger.warning("POSTGRES_PASSWORD not set in environment variables")

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"
```

**Bootstrap pattern analog** (`app/database.py:13-29` docstring + CLAUDE.md "Bootstrap problem"):
The `os.getenv()` call (not `config_get()`) is the mandatory pattern for all bootstrap values — `DATABASE_URL` is a bootstrap value, same as the POSTGRES_* vars it replaces.

**Target pattern** — D-G1-01 (delete composition, read single URL, preserve bootstrap pattern):
```python
def get_database_uri() -> str:
    """Return the database connection URI from the DATABASE_URL environment variable.

    Note: We must use os.getenv here instead of config_get because the
    configuration service needs a database connection to function — bootstrap
    problem (see CLAUDE.md). DATABASE_URL is the single canonical connection
    string for both Flask-SQLAlchemy and Alembic (docker-entrypoint.sh:12).
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Set it in .env (local dev) or the portal env-var store (SandCastle)."
        )
    return url
```

**`DatabaseConnection` coverage** (`app/database.py:60-78`):
```python
class DatabaseConnection:
    """Standalone database connection for background tasks"""

    def connect(self):
        """Create database engine and session factory"""
        if not self.engine:
            self.engine = create_engine(
                get_database_uri(),   # <-- single call site; no other change needed
                poolclass=pool.QueuePool,
                pool_size=5,
                pool_recycle=3600,
                pool_pre_ping=True,
            )
```
D-G1-04: `DatabaseConnection.connect()` already delegates to `get_database_uri()` — no change required beyond the function rewrite above. This is the single point of change.

---

### Plan 03-02 — `.env.example` (replace POSTGRES_* with DATABASE_URL)

**Current state to be replaced** (`.env.example:4-11`):
```
# --- PostgreSQL connection (required) -----------------------------------
# These bootstrap the database connection BEFORE encrypted config is
# accessible, so they must live in .env (not in the configuration table).
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=whodis_db
POSTGRES_USER=whodis_user
POSTGRES_PASSWORD=
```

**Target pattern** — D-G1-02 (single DATABASE_URL, retain bootstrap comment):
```
# --- Database connection (required) -------------------------------------
# DATABASE_URL bootstraps the database connection before encrypted config
# is accessible, so it must live in .env (not in the configuration table).
# SandCastle: use the value emitted by `./scripts/provision-db.sh who-dis`.
DATABASE_URL=postgresql://whodis_user:password@localhost:5432/whodis_db
```

The `WHODIS_ENCRYPTION_KEY` block and `DANGEROUS_DEV_AUTH_BYPASS_USER` block below the postgres section are unchanged.

---

### Plan 03-03 — `README.md` pointer cleanup

**Exact lines that change:**

Line 186 — current:
```
- **[Deployment Guide](docs/deployment.md)** - Production deployment for Azure App Service, Ubuntu, and Docker
```
Target (D-G5-01):
```
- **[Deployment Guide](docs/sandcastle.md)** - SandCastle deployment (canonical)
- **[Legacy Deployment](docs/deployment.md)** - Deprecated; pre-Phase-9 Azure App Service notes
```

Lines 683-693 — unchanged per D-G5-03 (already accurate):
```
## Deployment

Who-Dis runs on the SandCastle internal platform at
`https://who-dis.sandcastle.ttcu.com`. See [`docs/sandcastle.md`](docs/sandcastle.md)
for the canonical deployment guide (env vars, Keycloak setup, DB provisioning,
deploy flow, rollback).

For local development, `python run.py` continues to work against a local
Postgres and a Keycloak dev client. See `CLAUDE.md` for local-dev setup.

The legacy Azure App Service deployment path (`docs/deployment.md`) is
deprecated and will be decommissioned post-Phase-9 verification.
```

Line 716 — current:
```
- **System administrators?** Check the [Admin Tasks Guide](docs/user-guide/admin-tasks.md) and [Deployment Guide](docs/deployment.md)
```
Target (D-G5-02):
```
- **System administrators?** Check the [Admin Tasks Guide](docs/user-guide/admin-tasks.md) and [SandCastle Deployment Guide](docs/sandcastle.md)
```

---

### Plan 03-03 — `docs/sandcastle.md` (append "Operational Verification" section)

**Voice analog** (`scripts/cutover/README.md` — numbered steps, env-var prerequisites, idempotent re-run guidance):
```markdown
### Step 6 — Verify (Plan 06 UAT checkpoint)

- https://who-dis.sandcastle.ttcu.com/ -> Keycloak login -> land on home page
- Existing user can search a name; cached results visible (audit_log preserved)
- Admin user can reach admin pages (legacy editor users mapped to admin per
  `--include-editors`)
- Portal catalog shows who-dis as healthy
```

**Append location:** After `docs/sandcastle.md:234` (end of "Phase 9 reference" table) — D-G4-02.

**Structure to emit** (matches existing doc section style):
```markdown
## Operational Verification (WD-OPS-01, WD-OPS-04)

These two requirements close via operator confirmation, not code.

### WD-OPS-01 — SandCastle portal catalog registration

Confirm: Portal UI → Apps shows `who-dis` with a green status badge. Record
the app UUID as `WHODIS_APP_ID` in `scripts/cutover/README.md` step 4.

### WD-OPS-04 — GitHub webhook configured for `main` push

Confirm: GitHub → Who-Dis repo → Settings → Webhooks shows the SandCastle
webhook (`https://sandcastle.ttcu.com/api/webhooks/github`) with a green
tick (last delivery successful).

Smoke test: push a trivial change to `main` (or re-deliver the last event
from the GitHub webhook UI) and confirm the portal deploy log shows a
successful build.

### Live-deployment checklist

Run the bundled verification script against the production URL:

```bash
python scripts/verify_deployment.py --sandcastle
```

Expected output:
```
[PASS] GET https://who-dis.sandcastle.ttcu.com/health -> 200
[PASS] GET https://who-dis.sandcastle.ttcu.com/health/ready -> 200
[PASS] DNS who-dis.sandcastle.ttcu.com resolves
```

Record the date and your initials in `03-VERIFICATION.md` once all three
pass. That is the in-repo evidence for WD-OPS-01 and WD-OPS-04 closure.
```

---

### Plan 03-03 — `scripts/verify_deployment.py` (extend with 3 SandCastle live checks)

**Closest analog** (`scripts/verify_deployment.py:206-235` — `check_flask_application` method):
```python
    def check_flask_application(self) -> bool:
        """Verify Flask application starts and responds."""
        logger.info("🔍 Checking Flask application...")
        self.checks_total += 1

        try:
            # Check if app is running
            response = requests.get(f"{self.app_url}/", timeout=5)

            if response.status_code != 200:
                self.errors.append(
                    f"Flask app not responding correctly (status: {response.status_code})"
                )
                return False

            # Check for basic content
            if "Who Dis?" not in response.text:
                self.errors.append("Flask app not returning expected content")
                return False

            logger.info("✅ Flask application responding correctly")
            self.checks_passed += 1
            return True

        except requests.exceptions.RequestException as e:
            self.errors.append(f"Flask application check failed: {e}")
            logger.warning(
                "⚠️  Flask app check failed - make sure app is running on localhost:5000"
            )
            return False
```

**Pattern to copy for the three new checks** (D-G4-01):

1. `check_sandcastle_health()` — `GET https://who-dis.sandcastle.ttcu.com/health` → 200
2. `check_sandcastle_ready()` — `GET https://who-dis.sandcastle.ttcu.com/health/ready` → 200
3. `check_sandcastle_dns()` — `socket.getaddrinfo("who-dis.sandcastle.ttcu.com", 443)` succeeds

All three follow the same `self.checks_total += 1` / `self.checks_passed += 1` / `self.errors.append(...)` accounting pattern from the existing class.

**CLI flag analog** (`scripts/verify_deployment.py:367-379` — argparse block):
```python
    parser.add_argument(
        "--skip-photos", action="store_true", help="Skip photo loading tests"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
```
Add `--sandcastle` flag: when set, run only the three SandCastle live checks; when absent, run existing local checks. This makes the script usable in both dev and ops contexts.

**`get_db_connection` note:** The existing method reads `POSTGRES_HOST/PORT/DB/USER/PASSWORD` (lines 63-72). After Plan 03-02 ships, this method should be updated to use `DATABASE_URL` (via `psycopg2.connect(dsn=os.getenv("DATABASE_URL"))`). Bundle this one-line fix into Plan 03-02 or note it as a follow-up in the 03-03 plan.

---

## Shared Patterns

### Bootstrap env-var reads
**Source:** `app/database.py:20-24` and CLAUDE.md §"Important Database Notes"
**Apply to:** `app/database.py:get_database_uri()` (Plan 03-02), `app/__init__.py` Limiter init (Plan 03-01)
```python
# Correct: os.getenv() for bootstrap values (before config service is available)
url = os.getenv("DATABASE_URL")

# Also correct — with default for non-critical bootstrap:
storage_uri = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

# Never: config_get() for bootstrap values (chicken-and-egg)
```

### JSON-logger-aware startup warning
**Source:** `app/__init__.py:86-102` and `_configure_json_logging()` at lines 30-51
**Apply to:** Plan 03-01 production-mode `RATELIMIT_STORAGE_URI` warning

The JSON logging handler is installed at line 76 (`_configure_json_logging()`), before database init (line 88) and before Limiter init (line 111). Therefore `app.logger.warning(...)` at line 111+ will emit a properly structured JSON log line that surfaces in `docker logs`. Do NOT use a bare `print()` or module-level `logger.warning()` at import time (the JSON handler is not yet attached at module import).

```python
# Pattern (inside create_app(), after limiter.init_app(app)):
_storage = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
if os.environ.get("FLASK_ENV") == "production" and (
    not _storage or _storage == "memory://"
):
    app.logger.warning(
        "RATELIMIT_STORAGE_URI is unset or memory:// in production — "
        "rate-limit counters are per-worker and will not enforce correctly "
        "under multi-worker gunicorn. Set RATELIMIT_STORAGE_URI=redis://redis:6379/0 "
        "in the portal env-var store (see .env.sandcastle.example)."
    )
```

### Numbered-step operator runbook voice
**Source:** `scripts/cutover/README.md:38-96` and `docs/sandcastle.md:100-135`
**Apply to:** Plan 03-03's `docs/sandcastle.md` "Operational Verification" section

Use numbered steps, bash fences for commands, explicit "dry run first" guidance, idempotent re-run note, and failure-recovery bullets. Avoid prose paragraphs in favor of checklists.

---

## No Analog Found

None — all seven files have direct analogs in the existing codebase.

---

## Metadata

**Analog search scope:** `app/`, `scripts/`, `docs/`, `.env.sandcastle.example`, `.env.example`, `requirements.txt`, `README.md`
**Files read:** 11 (app/__init__.py, app/database.py, scripts/verify_deployment.py, scripts/cutover/README.md, docs/sandcastle.md, .env.sandcastle.example, .env.example, requirements.txt, README.md lines 180-191 and 678-720, app/services/configuration_service.py)
**Pattern extraction date:** 2026-04-26
