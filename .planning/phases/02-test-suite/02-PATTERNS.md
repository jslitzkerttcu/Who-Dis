# Phase 02: Test Suite - Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 18 (15 new, 3 modified)
**Analogs found:** 13 / 18

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/conftest.py` (new) | test-fixture/config | session-scoped DB + app | `app/__init__.py` (`create_app`) + `database/create_tables.sql` | role-adjacent |
| `tests/unit/conftest.py` (new) | test-fixture | request-context | `app/__init__.py` `before_request` | role-adjacent |
| `tests/integration/conftest.py` (new) | test-fixture | authenticated client | `app/middleware/auth.py` (`authenticate()`) | role-adjacent |
| `tests/fakes/fake_ldap_service.py` (new) | fake/test double | request-response | `app/services/ldap_service.py` | exact (interface) |
| `tests/fakes/fake_graph_service.py` (new) | fake/test double | request-response | `app/services/graph_service.py` | exact (interface) |
| `tests/fakes/fake_genesys_service.py` (new) | fake/test double | request-response + token | `app/services/genesys_service.py` | exact (interface) |
| `tests/factories/user.py` (new) | factory | CRUD seed | `app/models/user.py` | role-adjacent |
| `tests/factories/api_token.py` (new) | factory | CRUD seed | `app/models/api_token.py` | role-adjacent |
| `tests/factories/job_code.py` (new) | factory | CRUD seed | `app/models/job_code.py` | role-adjacent |
| `tests/factories/system_role.py` (new) | factory | CRUD seed | `app/models/system_role.py` | role-adjacent |
| `tests/integration/test_auth_pipeline.py` (new) | integration test | request-response | `app/middleware/auth.py` + `authentication_handler.py` | role-match |
| `tests/integration/test_search_flow.py` (new) | integration test | request-response | `app/services/search_orchestrator.py` | role-match |
| `tests/unit/services/test_search_orchestrator.py` (new) | unit test | concurrent request-response | `app/services/search_orchestrator.py` | exact |
| `tests/unit/services/test_ldap_service.py` (new) | unit test | request-response | `app/services/ldap_service.py` | exact |
| `tests/unit/services/test_genesys_service.py` (new) | unit test | request-response + token | `app/services/genesys_service.py` | exact |
| `requirements-dev.txt` (new) | dependency manifest | static config | `requirements.txt` | exact |
| `pyproject.toml` (new) | tool config | static config | `mypy.ini` | role-adjacent |
| `Makefile` (new) | task runner | static config | (none) | no-analog |
| `.githooks/pre-push` (new) | git hook | shell invocation | (none) | no-analog |
| `app/__init__.py` (MOD: D-06 TESTING gate) | factory | startup | self (lines 143, 173-183) | self |
| `.gitignore` (MOD: htmlcov verify) | config | static | self | already present |

## Pattern Assignments

### `tests/conftest.py` (test-fixture, session-scoped DB + Flask app)

**Analog:** `app/__init__.py` (boot sequence) + `database/create_tables.sql` (schema source per D-02)

**App factory reuse pattern** — call production `create_app()` with `TESTING=True` override (D-06, "Claude's Discretion: Test app factory"). Ref `app/__init__.py:51-90`:
```python
def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = secrets.token_hex(32)
    _configure_json_logging()
    init_request_id(app)
    from app.database import init_db
    init_db(app)
    inject_dependencies(app)
```

**Container override pattern** for fake injection (D-04). Re-register over the existing entries from `app/container.py:149-151`:
```python
container.register("ldap_service", lambda c: LDAPService())
container.register("genesys_service", lambda c: GenesysCloudService())
container.register("graph_service", lambda c: GraphService())
```
Container exposes `register()` as a public mutator (`app/container.py:27-37`) and `reset()` to drop singletons (`app/container.py:88-92`) — fixtures call `container.reset()` between tests if they swap fakes.

**Schema load pattern** (D-02): execute `database/create_tables.sql` verbatim, then `database/analyze_tables.sql` (per code_context "ANALYZE post-creation"). Closest existing executor of raw SQL files is `scripts/verify_encrypted_config.py:7-15`:
```python
import psycopg2
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))
```
Use the same `psycopg2.connect()` + `cursor.execute(sql_text)` shape against the testcontainers-provided DSN.

**SAVEPOINT-per-test pattern** (D-03) — no analog in repo; this is a standard SQLAlchemy 2.0 event-listener pattern. Wire onto the `db.session` exposed by `app/database.py`. Reference contract: each test gets a nested transaction; `event.listen(session, "after_transaction_end", restart_savepoint)`.

---

### `tests/unit/conftest.py` (test-fixture, request-context)

**Analog:** `app/__init__.py:226-237` (request lifecycle)

**Request-context establishment pattern** — orchestrator unit tests need `app.test_request_context()` because `SearchOrchestrator` calls `copy_current_request_context` (`app/services/search_orchestrator.py:11, 141, 146, 155, 160, 174, 180`). Mirror the `before_request` setup:
```python
@app.before_request
def before_request():
    g.user = None
    g.role = None
```
Fixture should yield with `g.user` populated to the test user email so service code that reads `g.user` doesn't crash.

---

### `tests/integration/conftest.py` (test-fixture, authenticated client)

**Analog:** `app/middleware/authentication_handler.py:44-47` and `app/middleware/auth.py:59-87`

**Authenticated-client fixture pattern** — set the configured principal header on the Flask test client. Header name comes from `auth.principal_header` config, default `X-MS-CLIENT-PRINCIPAL-NAME`:
```python
header_name = config_get("auth.principal_header", "X-MS-CLIENT-PRINCIPAL-NAME")
principal = request.headers.get(header_name)
```
The `authenticate()` orchestrator (`app/middleware/auth.py:59-87`) drives the full pipeline: `auth_handler.authenticate_user()` → `role_resolver.get_user_role()` → `auth_handler.set_user_context()` → `user_provisioner.get_or_create_user()` → `session_manager.get_or_create_session()` → `audit_logger.log_authentication_success()`. Fixture seeds the `users` table (via factory) and sets the header — let the real middleware do everything else.

**Bypass alternative** (DO NOT USE in tests per D-13): `DANGEROUS_DEV_AUTH_BYPASS_USER` env var (`authentication_handler.py:35-42`) — listed for awareness only; tests should use real header injection so the auth audit/provisioner paths exercise.

---

### `tests/fakes/fake_ldap_service.py` (fake, request-response)

**Analog:** `app/services/ldap_service.py`

**Interface implementation pattern** — implement `ISearchService` directly without inheriting `BaseSearchService` (per code_context "fakes can implement the interface directly without inheriting the base"). Mirror class signature from `app/services/ldap_service.py:18-21`:
```python
from app.interfaces.search_service import ISearchService

class LDAPService(BaseSearchService, ISearchService):
    def __init__(self):
        super().__init__(config_prefix="ldap")
```
Fake variant:
```python
class FakeLDAPService(ISearchService):
    def __init__(self, users: list[dict] | None = None):
        self._users = users or []
```

**Required interface methods** (`app/interfaces/search_service.py:10-41`):
```python
@abstractmethod
def search_user(self, search_term: str) -> Optional[Dict[str, Any]]: ...
@abstractmethod
def test_connection(self) -> bool: ...
@property
@abstractmethod
def service_name(self) -> str: ...
```

**Multiple-results wrapper contract** (specifics §1; from `app/services/base.py:377-394`):
```python
return {
    "multiple_results": True,
    "results": results,
    "total": total or len(results),
}
```
Plus the orchestrator-side switch (`app/services/search_orchestrator.py:198`) — fake must return single dict for 1 hit, `{"multiple_results": True, ...}` for >1, `None` for 0.

**Required fake fields** (specifics §2): `sAMAccountName`, `mail`, `displayName`, `memberOf`. Also support `get_user_by_dn(dn)` because the orchestrator calls it on the second-pass selection (`search_orchestrator.py:141-143`).

---

### `tests/fakes/fake_graph_service.py` (fake, request-response)

**Analog:** `app/services/graph_service.py` + interfaces `ISearchService`, `ITokenService`

**Pattern mirrors fake_ldap_service** above. Required record fields (specifics §2): `userPrincipalName`, `assignedLicenses`, `signInActivity`. Implement `search_user(term, include_photo=False)` and `get_user_by_id(id, include_photo=False)` to match the orchestrator call shapes (`search_orchestrator.py:174-183`). Also implement `ITokenService` methods (`app/interfaces/token_service.py:10-34`) returning a static fake token so the startup token-refresh loop in `app/__init__.py:156-170` doesn't fail when called against fakes.

---

### `tests/fakes/fake_genesys_service.py` (fake, request-response + token)

**Analog:** `app/services/genesys_service.py:13-15`
```python
class GenesysCloudService(BaseAPITokenService, ISearchService, ITokenService):
    def __init__(self):
        super().__init__(config_prefix="genesys", token_service_name="genesys")
```
Fake implements both `ISearchService` and `ITokenService` directly. Required record fields (specifics §2): `id`, `email`, `routingStatus`. Support `get_user_by_id(genesys_user_id)` (`search_orchestrator.py:155`).

**Token methods** (`app/interfaces/token_service.py`):
```python
def get_access_token(self) -> Optional[str]: return "fake-token"
def refresh_token_if_needed(self) -> bool: return True
@property
def token_service_name(self) -> str: return "genesys"
```

**`too_many_results` error shape** (orchestrator-aware, `search_orchestrator.py:238-242`):
```python
return {"error": "too_many_results", "message": "...", "total": N}
```
Fake should support emitting this when constructor flag is set, so tests can exercise the orchestrator's degraded path.

---

### `tests/factories/user.py` (factory, CRUD seed)

**Analog:** `app/models/user.py:10-25`
```python
class User(BaseModel, TimestampMixin):
    __tablename__ = "users"
    ROLE_VIEWER = "viewer"
    ROLE_EDITOR = "editor"
    ROLE_ADMIN = "admin"
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    role = db.Column(db.String(50), nullable=False, default=ROLE_VIEWER, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
```

**factory_boy SQLAlchemy pattern** (D-07): use `factory.alchemy.SQLAlchemyModelFactory` with `Meta.sqlalchemy_session = db.session` (bound by the SAVEPOINT fixture). Email factory should use `factory.Sequence(lambda n: f"user{n}@test.local")` to satisfy the unique constraint. Default `role=User.ROLE_VIEWER` to mirror the model default and the `user_provisioner` first-login path (`app/middleware/user_provisioner.py:22-29`).

**Email normalization contract** (`app/models/user.py:42-44`):
```python
return cls.query.filter_by(email=email.lower().strip()).first()
```
Factory must generate already-lowercased emails so `User.get_by_email()` lookups in tests find them.

---

### `tests/factories/api_token.py`, `tests/factories/job_code.py`, `tests/factories/system_role.py` (factory, CRUD seed)

**Analog:** corresponding model files in `app/models/`. Apply the same `SQLAlchemyModelFactory` pattern as `tests/factories/user.py`. Each model uses `BaseModel + TimestampMixin` per `app/models/base.py:15-29`:
```python
class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
```
Factories don't set `created_at`/`updated_at` — defer to model defaults.

`api_token` factory must respect the `expires_at` requirement (token-refresh logic at `app/services/token_refresh_service.py:92-102` checks `expires_at` for `<= 10 minutes`). Default to `now + 1 hour` for "valid", expose a parameter for "expiring" variant.

---

### `tests/integration/test_auth_pipeline.py` (integration test, request-response)

**Analog:** `app/middleware/auth.py:59-87` (full auth chain)

**Test cases per D-13:**
1. Valid header → user auto-provisioned with `viewer` (drives `user_provisioner.get_or_create_user`, `role_resolver.get_user_role`, `g.user`/`g.role` populated)
2. Missing header → 401 redirect (`auth.py:101-119`)
3. Header present, role insufficient for `@require_role("admin")` → 401 with `nope.html` (`auth.py:167-171`)
4. Existing user → role retained (no overwrite by provisioner)

**Header-injection pattern** — set the principal header per `authentication_handler.py:44-47`:
```python
header_name = config_get("auth.principal_header", "X-MS-CLIENT-PRINCIPAL-NAME")
principal = request.headers.get(header_name)
```
Use Flask test client `client.get("/", headers={"X-MS-CLIENT-PRINCIPAL-NAME": "test@example.com"})`.

**Phase 4 caveat** (specifics §3, D-13): rewrite required when Keycloak OIDC replaces the header — tag tests with a comment block.

**Rate-limit interaction** (canonical_refs Phase 1 D-08): Flask-Limiter is initialized in `app/__init__.py:96` with in-memory storage. Tests should either disable via `app.config["RATELIMIT_ENABLED"] = False` in the test fixture, or assert 429 on intentional overage.

---

### `tests/integration/test_search_flow.py` (integration test, request-response)

**Analog:** `app/services/search_orchestrator.py:79-133` (full concurrent path) + search blueprint route

**Flow per D-14:** `GET /search?term=jdoe` with all three fakes pre-loaded → `SearchOrchestrator.execute_concurrent_search()` → `ResultMerger` → HTMX fragment.

**Concurrent-execution contract** (`search_orchestrator.py:112-131`):
```python
with ThreadPoolExecutor(max_workers=3) as executor:
    ldap_future = self._submit_ldap_search(executor, search_term, ldap_user_dn)
    genesys_future = self._submit_genesys_search(executor, search_term, genesys_user_id)
    graph_future = self._submit_graph_search(executor, search_term, graph_user_id, include_photo)
    ldap_result = self._process_ldap_result(ldap_future, search_term, ldap_user_dn)
```
Each submitted callable is wrapped in `copy_current_request_context` — Flask test client provides this context naturally.

**HTMX response assertion** (Discretion §4): use substring `in response.data` for simple checks (e.g., `b"jdoe@example.com" in response.data`), BeautifulSoup for structural assertions. Pick whichever reads cleanly.

---

### `tests/unit/services/test_search_orchestrator.py` (unit test, concurrent request-response)

**Analog:** `app/services/search_orchestrator.py`

**Setup pattern** — orchestrator pulls services from container via lazy properties (`search_orchestrator.py:30-48`). Test instantiates orchestrator, registers fakes in a per-test container, asserts on result-tuple shape:
```python
return ldap_result, genesys_result, graph_result
# Each: {"result": ..., "error": ..., "multiple": False}
```

**Timeout exercise** — config keys `search.ldap_timeout` (default 3), `search.genesys_timeout` (default 5), `search.graph_timeout` (default 4) (`search_orchestrator.py:56-68`). Override via test config to force `FutureTimeoutError` paths (`search_orchestrator.py:210-214, 259-263, 300-304`).

**Multiple-results path** (`search_orchestrator.py:198-203`):
```python
if isinstance(ldap_data, dict) and ldap_data.get("multiple_results"):
    result["multiple"] = True
    result["result"] = ldap_data
```
Fakes feed the orchestrator the wrapped dict; assert `result["multiple"] is True`.

---

### `tests/unit/services/test_ldap_service.py` (unit test, request-response)

**Analog:** `app/services/ldap_service.py`

**Service contract** — implements `ISearchService`. Test methods on `service_name` property (`ldap_service.py:65-67`), `test_connection()` (`ldap_service.py:69-80`), `search_user(term)`. Mock `ldap3.Connection` (per Discretion §3, pytest-mock).

**Config-injection pattern** — service reads config via `self._get_config(...)` from `BaseConfigurableService` (`app/services/base.py:35-51`). Per code_context "do not patch `config_get` directly": tests should write rows to the test DB's `Configuration` table (via factory) so the encryption layer round-trips. Categories per `ldap_service.py:23-62`: `ldap.host`, `ldap.port`, `ldap.bind_dn`, `ldap.bind_password`, etc.

---

### `tests/unit/services/test_genesys_service.py` (unit test, request-response + token)

**Analog:** `app/services/genesys_service.py`

**Inheritance contract** (`genesys_service.py:13`):
```python
class GenesysCloudService(BaseAPITokenService, ISearchService, ITokenService):
```
Test both `search_user()` and `refresh_token_if_needed()` paths. Mock `requests.request` (used inside `BaseAPIService._make_request()` at `app/services/base.py:137`).

**Token storage round-trip** — `_fetch_new_token()` calls `_store_token()` (`genesys_service.py:87`) which writes to `api_tokens` table. Test asserts an `ApiToken` row appears with `service_name="genesys"`. Use `tests/factories/api_token.py` for any pre-seeded token tests.

---

### `requirements-dev.txt` (dependency manifest)

**Analog:** `requirements.txt` (lines 1-26)

**Format pattern** — pinned versions, blank line separating runtime/dev tooling (already used; lines 18-19 separator before `ruff`/`mypy`). New file mirrors style:
```
pytest>=8,<9
pytest-cov>=5,<6
pytest-mock>=3.14,<4
factory-boy>=3.3,<4
testcontainers[postgres]>=4,<5
beautifulsoup4>=4.12,<5
```
Move `ruff`, `mypy`, `types-*` from `requirements.txt:19-26` into `requirements-dev.txt` per code_context "Phase 2 introduces the dev/prod requirements split".

---

### `pyproject.toml` (tool config)

**Analog:** `mypy.ini` (only existing tool config in repo)

**Existing mypy config** (entire file):
```ini
[mypy]
python_version = 3.8
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = False
```
Plus per-package `ignore_missing_imports` blocks. Per Discretion §1, pytest config goes in `pyproject.toml`. Sections:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=app.services --cov=app.middleware --cov-fail-under=60 --cov-report=html --cov-report=term"
markers = ["unit", "integration"]

[tool.coverage.run]
source = ["app/services", "app/middleware"]
branch = true
```
Per D-11, gate on `app/services/` + `app/middleware/` only. mypy can stay in `mypy.ini` (no migration required; Discretion didn't mandate move).

---

### `Makefile` (task runner) — NO ANALOG

No Makefile exists in repo. Per D-10, single target `test`:
```makefile
test:
	pytest -x --cov-fail-under=60
```
Hook calls this so there's one source of truth.

---

### `.githooks/pre-push` (git hook) — NO ANALOG

No `.githooks/` directory exists; no `.pre-commit-config.yaml` exists. Per D-09 ("plain bash hook ... one-liner installer in the README"):
```bash
#!/usr/bin/env bash
set -e
make test
```
Plus README installer line: `git config core.hooksPath .githooks`.

---

### `app/__init__.py` (MODIFIED — D-06 TESTING gate)

**Existing background-thread starts to gate** (the file you must edit):

`app/__init__.py:143` — already gated by `WERKZEUG_RUN_MAIN`/`app.debug`; D-06 adds `TESTING` skip:
```python
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
```

`app/__init__.py:173-177` — `token_refresh.start()`:
```python
token_refresh = app.container.get("token_refresh")
token_refresh.app = app
token_refresh.container = app.container
token_refresh.start()
app.logger.info("Token refresh background service started")
```

`app/__init__.py:180-183` — `cache_cleanup.start()`:
```python
cache_cleanup = app.container.get("cache_cleanup")
cache_cleanup.app = app
cache_cleanup.start()
app.logger.info("Cache cleanup background service started")
```

`employee_profiles_refresh_service` is registered in container (`app/container.py:155`) but isn't started in `__init__.py` — verify in the plan whether it auto-starts elsewhere; if so, gate that site too.

**Edit pattern** — wrap each `.start()` call in `if not app.config.get("TESTING"):` per D-06 ("small, surgical edit").

---

### `.gitignore` (MODIFIED — htmlcov verification)

**Already present** at lines containing:
```
htmlcov/
.coverage
.coverage.*
.pytest_cache/
```
Per code_context "`htmlcov/` should be added to `.gitignore`" — already covered. Plan should verify and add only if a test run reveals new artifacts (e.g., `.benchmarks/`).

---

## Shared Patterns

### Container Override (applies to all fake fixtures)

**Source:** `app/container.py:27-37, 88-92`
```python
def register(self, name: str, factory: Callable[["ServiceContainer"], Any]) -> None:
    with self._lock:
        self._factories[name] = factory

def reset(self) -> None:
    with self._lock:
        self._services.clear()
```
**Apply to:** Every test that injects a fake — `app.container.register("ldap_service", lambda c: FakeLDAPService(...))`. Reset between tests requiring different fakes.

### Configuration Access (applies to all service tests)

**Source:** `app/services/base.py:35-51`
```python
def _get_config(self, key: str, default: Any = None) -> Any:
    full_key = f"{self._config_prefix}.{key}"
    if full_key not in self._config_cache:
        self._config_cache[full_key] = config_get(full_key, default)
    return self._config_cache[full_key]
```
**Apply to:** All `tests/unit/services/*.py`. Per code_context: write rows to test DB `Configuration` table (factory), don't patch `config_get`. After mutating, call `service._clear_config_cache()` (`app/services/base.py:53-55`).

### Logging Capture (applies to all tests asserting on log output)

**Source:** `logger = logging.getLogger(__name__)` per module (universal pattern, e.g., `app/services/ldap_service.py:15`, `app/services/search_orchestrator.py:16`)

**Apply to:** Tests using pytest's `caplog` fixture. Per code_context "no special instrumentation needed" — JSON log formatter is installed in `_configure_json_logging()` (`app/__init__.py:27-48`); `caplog` reads from the standard logging handlers.

### Service Interface Contract (applies to all fakes)

**Source:** `app/interfaces/search_service.py:7-41`, `app/interfaces/token_service.py:7-34`
- `ISearchService`: `search_user(term)`, `test_connection()`, `service_name` property
- `ITokenService`: `get_access_token()`, `refresh_token_if_needed()`, `token_service_name` property

**Apply to:** All fakes in `tests/fakes/`. Per code_context: implement the interface directly, do NOT inherit `BaseSearchService` or `BaseAPIService` (avoids dragging real HTTP/timeout logic).

### Multiple-Results Wrapper (applies to all fakes + integration tests)

**Source:** `app/services/base.py:377-394`
```python
return {
    "multiple_results": True,
    "results": results,
    "total": total or len(results),
}
```
**Apply to:** Every fake's `search_user` return value when constructed with >1 user. Orchestrator's three result-processors (`search_orchestrator.py:198, 243, 286`) all switch on `multiple_results`.

### Memoryview/BYTEA Handling (applies to encryption-touching tests)

**Source:** CLAUDE.md §"Memory Objects" — `bytes(memoryview_object)` before encryption/decryption.
**Apply to:** Any test that round-trips encrypted config via `EncryptionService` or writes to BYTEA columns directly.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `Makefile` | task runner | static config | No build-tool make targets exist anywhere in repo |
| `.githooks/pre-push` | git hook | shell invocation | No `.githooks/` or `.pre-commit-config.yaml` exists; this is greenfield infra |
| SAVEPOINT event-listener wiring inside `tests/conftest.py` | test-fixture | DB transaction control | No prior pytest-flask-sqlalchemy usage in repo; standard external pattern, not a project analog |
| `pyproject.toml` `[tool.pytest.ini_options]` block | tool config | static config | `mypy.ini` is the only existing tool config and uses INI format; no toml precedent — but Discretion §1 mandates `pyproject.toml` |

For these, the planner should reference RESEARCH.md or pytest-flask-sqlalchemy / testcontainers-python documentation directly. CONTEXT.md is the authoritative source (no RESEARCH.md exists for this phase).

## Metadata

**Analog search scope:** `app/`, `database/`, `scripts/`, repo root
**Files scanned:** `app/__init__.py`, `app/container.py`, `app/services/base.py`, `app/services/ldap_service.py`, `app/services/genesys_service.py`, `app/services/search_orchestrator.py`, `app/services/token_refresh_service.py`, `app/services/cache_cleanup_service.py`, `app/middleware/auth.py`, `app/middleware/authentication_handler.py`, `app/middleware/user_provisioner.py`, `app/middleware/role_resolver.py`, `app/interfaces/search_service.py`, `app/interfaces/token_service.py`, `app/models/user.py`, `app/models/base.py`, `database/create_tables.sql`, `requirements.txt`, `mypy.ini`, `.gitignore`, `scripts/verify_encrypted_config.py`
**Pattern extraction date:** 2026-04-25
