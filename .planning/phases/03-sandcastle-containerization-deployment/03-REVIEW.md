---
phase: 03-sandcastle-containerization-deployment
reviewed: 2026-04-26T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - .env.example
  - .env.sandcastle.example
  - README.md
  - app/__init__.py
  - app/database.py
  - docs/sandcastle.md
  - requirements.txt
  - scripts/verify_deployment.py
  - tests/conftest.py
findings:
  critical: 4
  warning: 6
  info: 4
  total: 14
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-04-26
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 3 closes three Sandcastle-deployment gaps: Flask-Limiter Redis swap (03-01),
DATABASE_URL refactor (03-02), and README/docs/verifier polish (03-03). The diffs
are mostly correct in their stated targets, but the review surfaces several
material defects:

1. The DATABASE_URL refactor installed a "fail-loud" `RuntimeError` in
   `get_database_uri()`, but the **caller in `app/__init__.py` swallows it and
   silently falls back to SQLite** — defeating the entire purpose of D-G1-01 and
   producing a worse-than-before failure mode (app appears healthy while writing
   to a stray `logs/app.db`).
2. **README installation steps still tell new operators to populate
   `POSTGRES_HOST/PORT/DB/USER/PASSWORD` in `.env`.** Anyone following the
   README literally now hits the new `RuntimeError` because nothing reads those
   vars anymore. The "must_haves" of Plan 03-03 / Plan 03-02 only fixed the
   deployment-pointer lines, not the install block at lines 134-148.
3. **README still describes auth as Azure AD SSO** in multiple places, even
   though Phase 9 cut over to Keycloak OIDC. Coupled with #2 this leaves the
   user-facing onboarding doc in a partially-correct state.
4. The Flask-Limiter `storage_uri` is captured at module import time, BEFORE
   `run.py` calls `load_dotenv()`. Local-dev developers who set
   `RATELIMIT_STORAGE_URI` in `.env` get the **memory://** fallback silently;
   the production-mode warning block also misses it for the same reason.
5. `app/__init__.py:75` generates a random `SECRET_KEY` per worker when the env
   var is unset — sessions silently break across multi-worker gunicorn.

The `SandcastleVerifier` SSRF mitigation (hardcoded host constants, no user
input) is correct. `psycopg2.connect(dsn=...)` migration in `verify_deployment`
is correct. `redis>=5,<6` pin is correct. tests/conftest.py DATABASE_URL
projection is sound for happy-path but does not unset on teardown.

## Critical Issues

### CR-01: SQLite fallback in `app/__init__.py` defeats the entire DATABASE_URL hard-fail design

**File:** `app/__init__.py:91-104`
**Issue:** Plan 03-02's stated purpose was: *"The new implementation fails
loudly (RuntimeError) instead of silently connecting to the wrong database"*
(03-02-PLAN.md line 64). However, the caller of `init_db()` wraps it in a broad
`except Exception` that catches the new `RuntimeError` and silently falls back
to a SQLite database at `sqlite:///logs/app.db`:

```python
try:
    init_db(app)
    app.logger.info(...)
except Exception as e:
    app.logger.error(f"Database initialization failed: {str(e)}")
    # Fallback to SQLite if PostgreSQL fails
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///logs/app.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    from app.database import db
    db.init_app(app)
    app.logger.warning("Falling back to SQLite database")
```

Concrete failure modes this enables:
1. **DATABASE_URL missing:** App boots on SQLite, claims healthy, writes
   encrypted config + audit logs to a stray file. `/health/ready` may still
   return 200 because `db.session.execute("SELECT 1")` works against SQLite.
   The portal sees green; users see broken.
2. **DATABASE_URL points at a temporarily-down Postgres:** Same outcome —
   permanent SQLite cutover until restart, even after Postgres recovers.
3. **In SandCastle container:** `logs/` is not writable in many container
   layouts, so the SQLite path fails too — but only after the warning has
   already been logged at WARNING level (not ERROR), making automated alerting
   miss it.
4. **Encryption salt mismatch + SQLite cutover:** Encrypted config in the real
   Postgres becomes orphaned; new writes go to SQLite with a different schema.
   Recovery requires manual intervention.

This also breaks the threat model in 03-02-PLAN.md `T-03-02-02` ("Tampering /
POSTGRES_* path removed — *misconfiguration fails fast with a clear error*").
It does NOT fail fast.

**Fix:** Delete the SQLite fallback. PostgreSQL is mandatory per CLAUDE.md
("PostgreSQL 12+ required, SQLite fallback available but not recommended") and
per the DATABASE_URL-only design. Let `init_db()` propagate:

```python
# Initialize database — fail fast on missing/bad DATABASE_URL (D-G1-01).
# No SQLite fallback: silent fallback would mask config errors and write
# encrypted data to a stray file. PostgreSQL is mandatory in all environments.
from app.database import init_db
init_db(app)
app.logger.info(
    f"Database initialized: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')}"
)
```

If a softer failure is required, log at ERROR and `sys.exit(1)` rather than
continuing on SQLite.

---

### CR-02: README installation instructions still demand removed POSTGRES_* env vars

**File:** `README.md:134-148`
**Issue:** Plan 03-02 deleted `POSTGRES_HOST/PORT/DB/USER/PASSWORD` from
`.env.example` and from `app/database.py`. README's "Configure minimal
environment" step still tells operators to write exactly those keys:

```bash
cat > .env << EOF
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=whodis_db
POSTGRES_USER=whodis_user
POSTGRES_PASSWORD=your-secure-password

# Encryption key for configuration
WHODIS_ENCRYPTION_KEY=...
EOF
```

A new contributor following step 5 verbatim ends up with a `.env` that has no
`DATABASE_URL`. Step 7 (`python run.py`) then throws:
`RuntimeError: DATABASE_URL environment variable is not set.`

Plan 03-03's "must_haves" (truths) only require the *deployment-guide pointer*
lines to be fixed (line 186, line 716). The install block at line 134-148 was
out of scope and remains stale. This is a documentation/code consistency
defect that breaks new-developer onboarding.

**Fix:** Replace lines 134-148 with the new `DATABASE_URL=...` form to match
`.env.example`:

```bash
cat > .env << EOF
# PostgreSQL connection
DATABASE_URL=postgresql://whodis_user:your-secure-password@localhost:5432/whodis_db

# Encryption key for configuration
WHODIS_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
EOF
```

Also update the `EncryptionService.generate_key()` call — the project no longer
has that method (the `.env.example` and SandCastle docs both use the Fernet
form). Verify the right call before publishing.

---

### CR-03: `SECRET_KEY` falls back to per-worker random bytes — sessions silently break under multi-worker gunicorn

**File:** `app/__init__.py:75`
**Issue:**
```python
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(32).hex()
```

In SandCastle, the Dockerfile exports `FLASK_ENV=production` and the entrypoint
spawns 2+ gunicorn workers. If the operator forgets to set `SECRET_KEY` in the
portal env-var store, EACH worker generates a *different* random
`SECRET_KEY`. Sessions signed by worker A are rejected by worker B — every
other request the user is logged out, CSRF tokens fail, and audit logs
attribute to nobody. The failure is silent: no warning, no `/health/ready`
breakage, just intermittent sign-outs that look like flaky auth.

`.env.sandcastle.example` lists `SECRET_KEY=replace-with-random-bytes` but
there is no enforcement that it is actually present. WD-CFG-05 mandates that
every key in `.env.sandcastle.example` must be set before the container starts;
this fallback violates that contract.

**Fix:** Fail fast in production:

```python
secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError(
            "SECRET_KEY environment variable is not set. "
            "Set it in the portal env-var store (see .env.sandcastle.example). "
            "Multi-worker gunicorn requires a stable shared key — random fallback "
            "would break sessions across workers."
        )
    # Local dev only: warn and use a stable per-process random key
    secret_key = os.urandom(32).hex()
    app.logger.warning("SECRET_KEY not set — using ephemeral random key (dev only)")
app.config["SECRET_KEY"] = secret_key
```

---

### CR-04: Limiter `storage_uri` and the production-mode warning are evaluated before `load_dotenv()`

**File:** `app/__init__.py:26-29` and `app/__init__.py:117-126`
**Issue:** `app/__init__.py` is imported by `run.py` at line 1 (`from app
import create_app`). The module body executes immediately, including:

```python
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
)
```

`run.py` only calls `load_dotenv()` AT LINE 4 — *after* `app/__init__.py` has
already finished its module-level code. Therefore:

- Any `RATELIMIT_STORAGE_URI` set in `.env` (local dev) is **ignored** — the
  limiter is constructed with `memory://` no matter what.
- The production-mode warning at lines 117-126 reads the env var again. In a
  container this works (env-vars are injected pre-process) but for any host
  that relies on `python-dotenv` (local dev, the legacy Azure path,
  developer-laptop testing of FLASK_ENV=production) the warning never fires
  *and* the limiter is on memory:// silently.
- Tests bypass the issue by registering `RATELIMIT_ENABLED=False` post-create,
  but production deployments do not.

For SandCastle this is currently masked because the portal injects env-vars
into the container's runtime environment before Python launches. Anyone
running outside the portal flow gets a silent broken state.

**Fix:** Either (a) move `load_dotenv()` into `app/__init__.py` *before* the
`limiter = Limiter(...)` line, or (b) defer storage_uri selection to
`limiter.init_app(app)` time:

Option B (preferred, keeps run.py canonical):
```python
limiter = Limiter(key_func=get_remote_address)  # storage_uri set in init_app

# inside create_app(), AFTER load_dotenv has had a chance to run:
storage_uri = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
app.config["RATELIMIT_STORAGE_URI"] = storage_uri
app.config["RATELIMIT_HEADERS_ENABLED"] = True
limiter.init_app(app)  # Flask-Limiter reads RATELIMIT_STORAGE_URI from app.config
if os.environ.get("FLASK_ENV") == "production" and storage_uri == "memory://":
    app.logger.warning(...)
```

Flask-Limiter 3.x supports `RATELIMIT_STORAGE_URI` via `app.config`, which is
the recommended pattern.

## Warnings

### WR-01: README still describes authentication as Azure AD SSO; Phase 9 migrated to Keycloak OIDC

**File:** `README.md:30, 55, 80, 391-393, 401-402`
**Issue:** Lines like `"Auth: Azure AD SSO with role-based access control"`
(line 80), `"Authentication Method: Azure AD SSO ... Checks
X-MS-CLIENT-PRINCIPAL-NAME header from Azure App Service"` (lines 391-393),
and `"Azure AD Only: Streamlined authentication removing basic auth"` (line
30). After Phase 9 the canonical auth path is Keycloak OIDC (Authlib) per
`docs/sandcastle.md` lines 42-67 and `.env.sandcastle.example` KEYCLOAK_*
block. New users reading README will look for X-MS-CLIENT-PRINCIPAL-NAME
header handling and find none.

**Fix:** Either (a) update the auth sections to describe Keycloak OIDC and
point to `docs/sandcastle.md` §"Keycloak OIDC setup", or (b) wrap them with a
"⚠️ Pre-Phase-9 / legacy" banner if the codebase still has the Azure AD
header path for transitional reasons. Plan 03-03 was the natural place to do
this; it slipped.

### WR-02: README "Tech Stack" table claims Authentication = Azure AD SSO

**File:** `README.md:80`
**Issue:** The Tech Stack table row reads:
```
| Authentication | Azure AD SSO | Single sign-on with role-based access control |
```
Same root cause as WR-01. Listed separately because tooling that scrapes
README tables for stack inventory will record incorrect data.

**Fix:** Replace with Keycloak OIDC (Authlib) and link to docs/sandcastle.md.

### WR-03: tests/conftest.py mutates `os.environ['DATABASE_URL']` without restoring it

**File:** `tests/conftest.py:66`
**Issue:** The session-scoped `app` fixture sets:
```python
os.environ["DATABASE_URL"] = plain_dsn
```
There is no `try/finally` or `monkeypatch.setenv` to restore the previous
value. If the developer runs `pytest` and then drops into a Python shell from
the same shell session, or if any other code executes after the test session
exits in the same process (a custom pytest plugin, a `--pdb` postmortem),
`DATABASE_URL` is left pointing at the now-stopped testcontainer.

**Fix:** Use `monkeypatch.setenv` (built into pytest, automatic teardown) or a
manual try/finally:

```python
@pytest.fixture(scope="session")
def app(database_url, _set_testing_env, monkeypatch_session):
    plain_dsn = database_url.replace("postgresql+psycopg2://", "postgresql://")
    monkeypatch_session.setenv("DATABASE_URL", plain_dsn)
    ...
```
(monkeypatch is function-scoped by default; use `pytest-monkeysession` or
provide a session-scoped wrapper.)

### WR-04: `verify_deployment.py` Flask check assumes localhost:5000 even when local app is on a different port

**File:** `scripts/verify_deployment.py:55, 215`
**Issue:** `self.app_url = "http://localhost:5000"` is hardcoded. Operators
who configured `flask.port` in DB to something else (per the project
configuration model) hit a connection refused. The check then fails and the
overall verifier returns 1, masking the actual schema/service health (which
may all be fine).

**Fix:** Read the port from environment or accept a `--app-url` flag:
```python
self.app_url = os.environ.get("WHODIS_APP_URL", "http://localhost:5000")
```

### WR-05: `verify_deployment.py` `with self.get_db_connection() as conn:` does not close the connection

**File:** `scripts/verify_deployment.py:83`
**Issue:** psycopg2's connection context manager commits/rolls-back the
transaction on `__exit__` but does NOT close the connection (per psycopg2
docs). For a one-shot script this leaks one connection per call. There is one
call (`check_database_schema`), so impact is small, but it's a footgun if more
methods adopt the same pattern.

**Fix:** Wrap explicitly:
```python
conn = self.get_db_connection()
try:
    with conn:
        cursor = conn.cursor()
        # ...
finally:
    conn.close()
```

### WR-06: `init_db()` swallows `db.create_all()` exceptions silently

**File:** `app/database.py:53-58`
**Issue:**
```python
with app.app_context():
    try:
        db.create_all()
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
```
The `except` block logs but does not re-raise. After the DATABASE_URL refactor,
this means: connection succeeds (DSN was valid) but the model metadata is
broken or the user lacks `CREATE TABLE`, the app boots, and every query at
runtime 500s. Combined with CR-01's SQLite fallback this gets even worse.

**Fix:** Either re-raise or downgrade gracefully — but at minimum, set a
flag/raise so `app/__init__.py` can decide. In Phase 9 the entrypoint guard
(`docker-entrypoint.sh:33`) checks `public.users` exists post-Alembic, so the
container would fail there — but only in containerized mode. Local dev still
silently boots a broken app.

## Info

### IN-01: `.env.sandcastle.example` ships placeholder secrets that look like template values but use the literal token `CHANGEME`

**File:** `.env.sandcastle.example:14, 19, 24, 29, 33`
**Issue:** Multiple `=CHANGEME` lines. These are template-only and not real
secrets — confirmed safe. However, an operator could conceivably leave one of
them at `CHANGEME` and the app would boot (Keycloak OIDC will fail at first
login, LDAP at first search, etc.) without a startup-time check. Not a
secret-leak issue, but a hardening gap.

**Fix:** Add a startup validation pass that rejects `CHANGEME` as a value for
any `*_SECRET` / `*_PASSWORD` env var when `FLASK_ENV=production`. Optional —
out of scope for this phase but worth a backlog item.

### IN-02: `tests/conftest.py` fallback message is silently swallowed when alembic upgrade fails

**File:** `tests/conftest.py:80-82`
**Issue:** When `alembic upgrade head` returns non-zero, the fixture prints
the stderr to stdout but continues. Plan 04 docstring says this is intentional
(baseline migration is empty pre-cutover, `db.create_all()` will compensate).
But a real Alembic regression — say a syntax error in `alembic/env.py` — gets
masked: tests still go green because `db.create_all()` builds the schema from
SQLAlchemy metadata. The migration path is left untested.

**Fix:** When `returncode != 0`, inspect stderr — if it contains "no such
revision" or similar pre-cutover-expected text, swallow; otherwise raise.
Alternatively, gate this on an env var like `ALEMBIC_REQUIRED=1` for CI.

### IN-03: `docs/sandcastle.md` line 49 says "Client Roles: viewer, admin (collapsed from legacy three-tier per D-05)"

**File:** `docs/sandcastle.md:49`
**Issue:** Code (`app/middleware/role_resolver.py`, CLAUDE.md, `User` model
constants) still references three roles (Viewer, Editor, Admin). Either the
sandcastle.md doc is wrong about the collapse, or the code wasn't migrated.
Either way the two docs disagree and operators reading sandcastle.md before
provisioning roles will be misled.

**Fix:** Reconcile. If three-tier is canonical, remove the "collapsed from
legacy three-tier" line. If two-tier is canonical, file a bug for the missing
code migration. (Likely out of scope for Phase 3, but flag for Phase 4
Keycloak work.)

### IN-04: `verify_deployment.py` module docstring usage block does not mention `--sandcastle`

**File:** `scripts/verify_deployment.py:8-13`
**Issue:** The docstring still reads:
```
Usage:
    python scripts/verify_deployment.py [--skip-photos] [--verbose]
```
The new `--sandcastle` flag is documented in argparse `help=` but not in this
top-of-file usage block. Operators who `head` the script for orientation see
incomplete usage.

**Fix:** Add `[--sandcastle]` to the usage line and a brief description of the
new mode.

---

_Reviewed: 2026-04-26_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
