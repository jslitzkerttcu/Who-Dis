---
phase: 03-sandcastle-containerization-deployment
audited: 2026-04-26
status: secured
asvs_level: standard
threats_total: 14
threats_closed: 14
threats_open: 0
unregistered_flags: 0
---

# Phase 3 Security Audit Report

**Phase:** 03 — SandCastle Containerization & Deployment
**Plans Audited:** 03-01, 03-02, 03-03, 03-04
**Audit Date:** 2026-04-26
**ASVS Level:** Standard
**Result:** SECURED — all 14 declared threats verified closed in implementation

---

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-03-01-01 | Information Disclosure | mitigate | CLOSED | `app/__init__.py:133` reads value via `os.environ.get("RATELIMIT_STORAGE_URI", "memory://")` and assigns to local `storage_uri`. Warning block at lines 144-151 logs only the string literal key name and corrective instruction text — never the URI value. Grep `RATELIMIT_STORAGE_URI` in the warning body returns 0 value echoes. |
| T-03-01-02 | Tampering | mitigate | CLOSED | `app/__init__.py:144-151` — `if os.environ.get("FLASK_ENV") == "production" and (not storage_uri or storage_uri == "memory://"):` fires `app.logger.warning(...)`. Warning fires when storage is unset or memory:// in production. Reads from the resolved local `storage_uri` variable (not a re-fetch), so non-container deploys using python-dotenv also trigger it correctly (CR-04 fix). |
| T-03-01-03 | Denial of Service | accept | CLOSED | Accepted risk. Redis is on the SandCastle internal network (WD-NET-01). The `internal` Docker network in `docker-compose.sandcastle.yml` is not reachable from the public proxy network. Adding Redis auth is a SandCastle platform concern. See accepted risks log below. |
| T-03-02-01 | Information Disclosure | mitigate | CLOSED | `app/database.py:24` — `url = os.getenv("DATABASE_URL")`. Value is never logged; the RuntimeError message at lines 26-30 contains only the literal key name `DATABASE_URL` and operator-actionable hints. No `url` variable appears in any log call. Verified: `grep -c "POSTGRES_" app/database.py` = 0. |
| T-03-02-02 | Tampering | mitigate | CLOSED | POSTGRES_* composition path deleted (0 occurrences in `app/database.py`). `app/__init__.py:121` calls `init_db(app)` as a bare call with no try/except wrapper — RuntimeError from `get_database_uri()` propagates unwrapped. `grep -c "sqlite:///logs/app.db" app/__init__.py` = 0; `grep -c "Falling back to SQLite" app/__init__.py` = 0. End-to-end correctness restored by Plan 03-04 Task 1 (CR-01). |
| T-03-02-03 | Spoofing | mitigate | CLOSED | `.env.example:8` contains `DATABASE_URL=postgresql://...` with zero POSTGRES_* references (verified: count = 0). `README.md` install block: POSTGRES_* count = 0, `DATABASE_URL=postgresql://whodis_user:...` present at line 142. Operator following either template cannot populate POSTGRES_* vars that the app no longer reads. |
| T-03-03-01 | Elevation of Privilege (SSRF) | mitigate | CLOSED | `scripts/verify_deployment.py:369-371` — `SANDCASTLE_URL = "https://who-dis.sandcastle.ttcu.com"` and `SANDCASTLE_HOST = "who-dis.sandcastle.ttcu.com"` are module-level string constants. The `--sandcastle` argparse argument uses `action="store_true"` (boolean switch — no URL value accepted). All `requests.get` and `socket.getaddrinfo` calls in `SandcastleVerifier` reference only these constants. No user input reaches the target URL. |
| T-03-03-02 | Information Disclosure | accept | CLOSED | Accepted risk. `/health` is intentionally unauthenticated (WD-HEALTH-01, OPS-01). `app/blueprints/health/__init__.py:36` returns only `jsonify({"status": "healthy"}), 200` — no user data, no secrets, no version details, no internal paths. `@auth_required` decorator is absent by design. See accepted risks log below. |
| T-03-03-03 | Tampering | accept | CLOSED | Accepted risk. README.md is a documentation file in a private repository. No security boundary is crossed by editing it. Changes are git-tracked and reviewed per the standard pull-request workflow. See accepted risks log below. |
| T-03-04-01 | Spoofing | mitigate | CLOSED | `app/__init__.py:84-100` — `secret_key = os.environ.get("SECRET_KEY"); if not secret_key: if os.environ.get("FLASK_ENV") == "production": raise RuntimeError("SECRET_KEY environment variable is not set. ...")`. The `or os.urandom(32).hex()` chain that allowed per-worker random fallback is gone (verified: `grep -c 'os.environ.get("SECRET_KEY") or os.urandom' app/__init__.py` = 0). Dev mode retains ephemeral key behind a `logging.getLogger(__name__).warning(...)`. |
| T-03-04-02 | Tampering | mitigate | CLOSED | `app/__init__.py:119-124` — `init_db(app)` called directly without any surrounding try/except block. The RuntimeError raised by `get_database_uri()` when DATABASE_URL is missing propagates unwrapped to docker-entrypoint.sh / gunicorn / run.py and aborts startup. No stray `sqlite:///logs/app.db` file is created. Grep evidence: count of "sqlite:///logs/app.db" = 0; count of "Falling back to SQLite" = 0. Cross-reference: this restores end-to-end correctness for T-03-02-02's mitigation (the SQLite fallback in the original caller was masking Plan 03-02's RuntimeError). |
| T-03-04-03 | Information Disclosure | mitigate | CLOSED | `README.md` install block (line 142): `DATABASE_URL=postgresql://whodis_user:your-secure-password@localhost:5432/whodis_db`. `POSTGRES_` count in README = 0. `EncryptionService.generate_key` count = 0. Encryption key generation uses `Fernet.generate_key().decode()` (count = 2 — install block + key-rotation section). A new operator following README verbatim will set DATABASE_URL correctly and trigger the clean RuntimeError on misconfiguration rather than a stack-trace-producing wrong-variable error. |
| T-03-04-04 | Denial of Service | mitigate | CLOSED | `app/__init__.py:34` — `limiter = Limiter(key_func=get_remote_address)` with no `storage_uri=` kwarg (verified: `grep -c "storage_uri=" app/__init__.py` = 0). Inside `create_app()`, `storage_uri = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")` at line 133 is resolved after `load_dotenv()` has executed in `run.py`. `app.config["RATELIMIT_STORAGE_URI"] = storage_uri` at line 134 sets the value Flask-Limiter 3.x reads at `limiter.init_app(app)` time (line 138). Both container deploys and non-container (python-dotenv) deploys see the correct value. |
| T-03-04-05 | Repudiation | mitigate | CLOSED | `README.md:80` — `\| Authentication \| Keycloak OIDC (Authlib) \|...` with link to `docs/sandcastle.md#keycloak-oidc-setup`. Lines 30, 55: "SSO Only" with "Keycloak OIDC via SandCastle" parenthetical. Lines 388-393: full Keycloak OIDC Authorization Code flow description. Grep evidence: `X-MS-CLIENT-PRINCIPAL-NAME` count = 0; `Azure AD SSO` count = 0; `Azure AD Only` count = 0; `Keycloak OIDC` count = 4. Audit reviewers reading README.md see the correct authentication mechanism. |

---

## Accepted Risks Log

The following threats carry `accept` dispositions. Each is documented here as the required in-repo evidence of accepted risk.

### T-03-01-03 — Unauthenticated Redis on internal network (DoS)

**Category:** Denial of Service
**Component:** Redis rate-limit counter store on SandCastle internal network
**Risk:** An attacker with access to the SandCastle internal network could send forged Redis commands to reset or inflate rate-limit counters, bypassing per-user search limits.
**Acceptance Rationale:** Redis is exposed only on the Docker `internal` network defined in `docker-compose.sandcastle.yml`. This network is not reachable from the public proxy network or the internet. Adding Redis authentication (`requirepass`) is a SandCastle platform configuration concern, not a Who-Dis application concern. The Who-Dis application cannot meaningfully enforce Redis auth independently of the platform's network topology decisions.
**Residual Risk:** Low. Exploitation requires internal network access equivalent to full container escape on the SandCastle host.
**Owner:** SandCastle platform team.
**Review Cycle:** Revisit if Who-Dis moves to a shared-tenant SandCastle environment where the internal network is not Who-Dis-exclusive.

### T-03-03-02 — Information Disclosure via /health endpoint (unauthenticated)

**Category:** Information Disclosure
**Component:** `GET /health` endpoint (`app/blueprints/health/__init__.py`)
**Risk:** The `/health` endpoint is intentionally unauthenticated and publicly reachable via Traefik. An attacker could confirm that the Who-Dis service is running.
**Acceptance Rationale:** The endpoint returns only `{"status": "healthy"}` with HTTP 200. No user data, credentials, internal hostnames, version strings, or diagnostic information is returned. The unauthenticated design is required by WD-HEALTH-01 (SandCastle portal poller) and the Dockerfile `HEALTHCHECK` directive. Both the portal and Docker daemon must be able to probe liveness without authentication tokens. Confirming that a service is running at a known subdomain is not a meaningful security boundary for an enterprise-internal IT operations tool.
**Residual Risk:** Negligible. Service existence is already known from the DNS record `who-dis.sandcastle.ttcu.com`.
**Owner:** Phase 1 design decision (D-11/D-12). No change expected.

### T-03-03-03 — Tampering with README documentation

**Category:** Tampering
**Component:** `README.md`
**Risk:** An attacker with write access to the repository could modify README.md to mislead operators about configuration or security requirements.
**Acceptance Rationale:** README.md is a documentation file in a private repository with access controls enforced by GitHub. Any modification is git-tracked with author attribution and subject to branch-protection rules and pull-request review. The repository's branch-protection rules (main branch) require reviewed PRs. Tampering with README is equivalent to gaining write access to the entire codebase — if that access exists, README manipulation is the least severe outcome.
**Residual Risk:** Low. Mitigated by repository access controls and PR review process.
**Owner:** Repository administrators.

---

## Unregistered Threat Flags

None. All SUMMARY.md `## Threat Flags` sections across plans 03-01 through 03-04 explicitly report no new threat surface beyond the declared threat register. No implementation-introduced attack surface was identified outside the 14 registered threats.

---

## Auditor Notes

### T-03-02-02 end-to-end correctness (cross-plan dependency)

Plan 03-02 introduced `get_database_uri()` raising `RuntimeError` when `DATABASE_URL` is missing. However, the original caller in `app/__init__.py` wrapped `init_db()` in a `try/except Exception` that silently fell back to SQLite, defeating the mitigation entirely. Plan 03-04 Task 1 (CR-01) deleted this fallback block, making `RuntimeError` propagate unwrapped. Both plans are required together for T-03-02-02 to be correctly mitigated; neither alone is sufficient. The audit confirms both changes are present in the implementation.

### T-03-04-04 timing correctness (CR-04 fix)

Plan 03-01 introduced `storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://")` in the module-level `Limiter()` constructor. This was later found to execute before `load_dotenv()` runs in `run.py` (module body executes at `from app import create_app` time, before `load_dotenv()` on the next line). Plan 03-04 Task 3 (CR-04) moved the read inside `create_app()` and uses `app.config["RATELIMIT_STORAGE_URI"]` as the vehicle. The audit confirms the module-level constructor has `storage_uri=` removed (count = 0) and the `create_app()`-level assignment is present at line 134. The threat T-03-04-04 mitigation is correctly implemented.

### Health endpoint disclosure scope

`GET /health/ready` at `app/blueprints/health/__init__.py:46-71` returns `{"status": "ready", "database": {"connected": true, "latency_ms": N}, "version": "3.0.0-sandcastle", "request_id": "..."}` on success. This returns a version string and request ID. T-03-03-02 covers only `/health` as the accepted risk; the `/health/ready` endpoint returns marginally more data. This is noted for awareness but is within the scope of the accepted WD-HEALTH-01/WD-HEALTH-02 design decisions. The version string (`3.0.0-sandcastle`) and request ID do not constitute secrets or PII. No new threat registration is required.

---

_Audited by: Claude (gsd-security-auditor)_
_Phase plans audited: 03-01-PLAN.md, 03-02-PLAN.md, 03-03-PLAN.md, 03-04-PLAN.md_
_Implementation files verified: app/__init__.py, app/database.py, app/blueprints/health/__init__.py, scripts/verify_deployment.py, .env.example, .env.sandcastle.example, README.md_
