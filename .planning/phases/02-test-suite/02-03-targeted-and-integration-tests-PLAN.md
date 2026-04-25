---
phase: 02-test-suite
plan: 03
type: tdd
wave: 3
depends_on: [02-02-fixtures-fakes-factories]
files_modified:
  - tests/unit/services/__init__.py
  - tests/unit/services/test_search_orchestrator.py
  - tests/unit/services/test_ldap_service.py
  - tests/unit/services/test_genesys_service.py
  - tests/integration/test_auth_pipeline.py
  - tests/integration/test_search_flow.py
autonomous: true
requirements: [TEST-01, TEST-02, TEST-03]
tags: [testing, pytest, unit-tests, integration-tests, tdd]

must_haves:
  truths:
    - "`pytest tests/unit/services/test_search_orchestrator.py -v` passes — orchestrator concurrent merge, multiple_results path, timeout path, too_many_results path all covered"
    - "`pytest tests/unit/services/test_ldap_service.py -v` passes — search_user happy path, no-result path, multiple-result path, test_connection failure path all covered with mocked ldap3.Connection"
    - "`pytest tests/unit/services/test_genesys_service.py -v` passes — search_user happy path, refresh_token_if_needed path with mocked requests.request, ApiToken row written on token fetch all covered"
    - "`pytest tests/integration/test_auth_pipeline.py -v` passes — valid header → user provisioned with viewer; missing header → 401; insufficient role → 403; existing user role retained (4+ test cases per D-13)"
    - "`pytest tests/integration/test_search_flow.py -v` passes — GET /search?term=jdoe with all three fakes pre-loaded → orchestrator merges → HTMX fragment contains data from all three sources (~6-8 tests per D-14)"
  artifacts:
    - path: "tests/unit/services/test_search_orchestrator.py"
      provides: "Targeted unit tests for SearchOrchestrator (D-12)"
      contains: "def test_"
      min_lines: 100
    - path: "tests/unit/services/test_ldap_service.py"
      provides: "Targeted unit tests for LDAPService (D-12)"
      contains: "def test_"
      min_lines: 80
    - path: "tests/unit/services/test_genesys_service.py"
      provides: "Targeted unit tests for GenesysCloudService (D-12)"
      contains: "def test_"
      min_lines: 80
    - path: "tests/integration/test_auth_pipeline.py"
      provides: "Auth middleware pipeline integration tests (D-13)"
      contains: "def test_"
      min_lines: 80
    - path: "tests/integration/test_search_flow.py"
      provides: "Full search-flow integration tests (D-14)"
      contains: "def test_"
      min_lines: 100
  key_links:
    - from: "tests/integration/test_search_flow.py"
      to: "FakeLDAP/FakeGraph/FakeGenesys via container.register"
      via: "fake_ldap/fake_graph/fake_genesys fixtures"
      pattern: "fake_ldap"
    - from: "tests/integration/test_auth_pipeline.py"
      to: "app/middleware/auth.py + authentication_handler.py + user_provisioner.py"
      via: "authenticated_client fixture (header injection)"
      pattern: "authenticated_client\\|admin_client"
---

<objective>
Write the actual test bodies that satisfy TEST-01/02/03 and drive coverage to ≥60% on `app/services/` + `app/middleware/`. TDD plan: each file follows RED → GREEN cycles per test case.

Three unit-test files target the three hot service files identified in D-12 (search_orchestrator.py, ldap_service.py 652L, genesys_service.py 668L) — these are the auth/search hot paths Phases 3-5 will refactor. Two integration-test files exercise the full request → middleware → orchestrator → fakes → merger → template path (D-13 auth pipeline + D-14 search flow).

Purpose: Lock in regression protection for the code Phases 3-5 (containerization, Keycloak auth migration, Alembic) will refactor. Without these tests, the refactors are blind.
Output: 5 new test modules, ~30-40 test cases total, ≥60% coverage on services + middleware packages.

**TDD posture (workflow.tdd_mode disabled per default → opportunistic):** This plan IS marked `type: tdd` because every test in it is a written-first contract. Each test goes RED (asserts the production behavior, fails because production behavior isn't yet exercised under test) → GREEN (passes against existing production code). No production code changes in this plan — coverage emerges from exercising existing paths.

**Phase 4 caveat:** Tests in `test_auth_pipeline.py` use Azure AD header injection per D-13. Phase 4 will rewrite these against Keycloak OIDC. Tag the file with the carry-over comment block.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/02-test-suite/02-CONTEXT.md
@.planning/phases/02-test-suite/02-PATTERNS.md
@.planning/phases/02-test-suite/02-02-SUMMARY.md
@app/services/search_orchestrator.py
@app/services/ldap_service.py
@app/services/genesys_service.py
@app/services/result_merger.py
@app/middleware/auth.py
@app/middleware/authentication_handler.py
@app/middleware/user_provisioner.py
@app/middleware/role_resolver.py
@app/blueprints/search/__init__.py

<interfaces>
<!-- SearchOrchestrator return contract (search_orchestrator.py — verify exact line numbers when reading) -->
# Returns three-tuple: (ldap_result, genesys_result, graph_result)
# Each: {"result": dict|None, "error": str|None, "multiple": bool}

# Timeout config keys (with defaults):
#   search.ldap_timeout    -> 3 seconds
#   search.genesys_timeout -> 5 seconds
#   search.graph_timeout   -> 4 seconds

# Multiple-results dispatch (search_orchestrator.py:198-203):
if isinstance(ldap_data, dict) and ldap_data.get("multiple_results"):
    result["multiple"] = True
    result["result"] = ldap_data

# Auth pipeline call chain (app/middleware/auth.py:59-87):
# auth_handler.authenticate_user() -> role_resolver.get_user_role() ->
# auth_handler.set_user_context() -> user_provisioner.get_or_create_user() ->
# session_manager.get_or_create_session() -> audit_logger.log_authentication_success()

# Header config (app/middleware/authentication_handler.py:44-47):
header_name = config_get("auth.principal_header", "X-MS-CLIENT-PRINCIPAL-NAME")
principal = request.headers.get(header_name)

# Role decorator failure (app/middleware/auth.py:167-171):
# Renders nope.html with 401 (NOT 403 per current code — verify in implementation)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Targeted unit tests for the 3 hottest service files</name>
  <files>tests/unit/services/__init__.py, tests/unit/services/test_search_orchestrator.py, tests/unit/services/test_ldap_service.py, tests/unit/services/test_genesys_service.py</files>
  <read_first>
    - app/services/search_orchestrator.py (full file — 332L; identify the 3 result processors + ThreadPoolExecutor block + timeout handling)
    - app/services/ldap_service.py (full file 652L; identify search_user, test_connection, _connect, _format_user method signatures)
    - app/services/genesys_service.py (full file 668L; identify search_user, _fetch_new_token, _store_token, refresh_token_if_needed; verify they call BaseAPIService._make_request)
    - app/services/base.py (lines 35-55 _get_config + _clear_config_cache; lines 137-XXX _make_request implementation; lines 377-394 multiple-results helper)
    - tests/conftest.py (db_session, container_reset, fake_ldap/fake_graph/fake_genesys fixtures from Plan 02)
    - tests/unit/conftest.py (request_context fixture)
    - tests/factories/api_token.py (ApiTokenFactory + expiring trait)
    - .planning/phases/02-test-suite/02-PATTERNS.md (§"tests/unit/services/test_*.py" sections)
    - .planning/phases/02-test-suite/02-CONTEXT.md (D-12 — these 3 are the chosen targets)
  </read_first>
  <behavior>
    **`test_search_orchestrator.py` cases (target 8-12 tests):**
    - `test_concurrent_search_all_three_return_results` — all 3 fakes return single dict; orchestrator returns 3-tuple with each `result["result"]` populated, `result["error"] is None`, `result["multiple"] is False`
    - `test_concurrent_search_no_results` — all 3 fakes return None; tuple has `result["result"] is None` for each, no error
    - `test_ldap_multiple_results_path` — FakeLDAP returns `{"multiple_results": True, ...}`; assert `ldap_result["multiple"] is True`
    - `test_genesys_too_many_results_path` — FakeGenesys with `too_many=True`; assert `genesys_result["error"] == "too_many_results"` (or whatever the orchestrator normalizes it to — verify by reading lines 238-242)
    - `test_ldap_timeout` — Override `search.ldap_timeout` config to 0.001s, use a fake that sleeps; assert `ldap_result["error"]` is a timeout indicator
    - `test_graph_timeout` — same pattern for graph
    - `test_genesys_timeout` — same pattern for genesys
    - `test_dn_second_pass` — Trigger orchestrator's `get_user_by_dn` second-pass branch (search_orchestrator.py:141-143); assert `FakeLDAPService.get_user_by_dn` was called
    - `test_orchestrator_uses_request_context` — Verify orchestrator runs inside `app.test_request_context()` without crashing on `copy_current_request_context`

    **`test_ldap_service.py` cases (target 6-10 tests):**
    - `test_service_name_property` — returns `"ldap"`
    - `test_test_connection_success` — mock `ldap3.Connection` to return open connection; `test_connection()` returns True
    - `test_test_connection_failure` — mock `ldap3.Connection` to raise; `test_connection()` returns False; `caplog` shows ERROR
    - `test_search_user_happy_path` — mock `Connection.search` to return single result entry; assert returned dict has `sAMAccountName`, `mail`, `displayName`, `memberOf`
    - `test_search_user_no_results` — mock `Connection.search` returns empty; `search_user()` returns None
    - `test_search_user_multiple_results` — mock `Connection.search` returns multiple entries; `search_user()` returns `{"multiple_results": True, ...}` shape
    - `test_config_round_trip` — Write config rows via DB (NOT patched), call `_get_config("host")`, assert correct value returned
    - `test_handle_service_errors_decorator` — Force exception in mocked Connection; verify `@handle_service_errors` swallows + logs (does not raise)

    **`test_genesys_service.py` cases (target 6-10 tests):**
    - `test_service_name_property` — returns `"genesys"`
    - `test_token_service_name_property` — returns `"genesys"`
    - `test_search_user_happy_path` — mock `requests.request` to return JSON with `entities: [...]`; assert `search_user()` returns dict with `id`, `email`, `routingStatus`
    - `test_search_user_no_results` — mock returns empty entities; `search_user()` returns None
    - `test_refresh_token_when_expired` — Pre-seed expiring `ApiToken` via factory; mock the OAuth token endpoint via `requests.request`; call `refresh_token_if_needed()`; assert returns True AND a new ApiToken row exists in DB with later expires_at
    - `test_refresh_token_when_valid` — Pre-seed non-expiring token; `refresh_token_if_needed()` returns True without HTTP call (assert `requests.request` mock NOT called)
    - `test_token_storage_round_trip` — Force `_fetch_new_token()` path; assert `ApiToken` row written with `service_name="genesys"`
    - `test_too_many_results_emission` — mock returns >MAX results; assert returned dict has `error == "too_many_results"` shape
  </behavior>
  <action>
    Create `tests/unit/services/__init__.py` (empty) and the three test modules.

    For each test file:
    1. Mark all tests with `@pytest.mark.unit` (so `make test-unit` filters work)
    2. Use `pytest-mock`'s `mocker` fixture (per CONTEXT Discretion §3) — NOT `unittest.mock.patch`
    3. Use the `db_session` and `container_reset` fixtures from Plan 02
    4. For `test_ldap_service.py`: mock at `app.services.ldap_service.Connection` (or wherever ldap3.Connection is imported from in the module — verify with grep)
    5. For `test_genesys_service.py`: mock at `app.services.base.requests.request` (the BaseAPIService._make_request call site, base.py:137 per PATTERNS) — verify with grep
    6. For `test_search_orchestrator.py`: use the `fake_ldap` / `fake_graph` / `fake_genesys` convenience fixtures; instantiate orchestrator via `app.container.get("search_orchestrator")` (or directly if not container-registered — verify)
    7. Configuration round-trip tests: write `Configuration` rows via direct SQLAlchemy `db.session.add(Configuration(...))` then call service method — DO NOT call `mocker.patch("app.services.base.config_get")`. Per PATTERNS.md "Configuration Access" shared pattern.

    **CRITICAL — request context for orchestrator tests:**
    Use the `request_context` fixture from `tests/unit/conftest.py`:
    ```python
    def test_concurrent_search_all_three_return_results(request_context, fake_ldap, fake_graph, fake_genesys, app):
        fake_ldap.add_user({"sAMAccountName": "jdoe", "mail": "jdoe@x.com", "displayName": "J Doe", "memberOf": []})
        fake_graph.add_user({"userPrincipalName": "jdoe@x.com", "id": "g-1", "assignedLicenses": [], "signInActivity": {}})
        fake_genesys.add_user({"id": "gn-1", "email": "jdoe@x.com", "routingStatus": "AVAILABLE"})

        orch = app.container.get("search_orchestrator")
        ldap_r, gen_r, graph_r = orch.execute_concurrent_search(search_term="jdoe", ...)
        # ^^ verify exact method name + signature when reading orchestrator source

        assert ldap_r["result"]["sAMAccountName"] == "jdoe"
        assert gen_r["result"]["routingStatus"] == "AVAILABLE"
        assert graph_r["result"]["userPrincipalName"] == "jdoe@x.com"
        assert all(r["error"] is None for r in (ldap_r, gen_r, graph_r))
        assert all(r["multiple"] is False for r in (ldap_r, gen_r, graph_r))
    ```

    **For LDAP test mocking** — typical pattern:
    ```python
    def test_search_user_happy_path(mocker, db_session, app):
        mock_conn = mocker.MagicMock()
        mock_conn.search.return_value = True
        mock_conn.entries = [mocker.MagicMock(
            sAMAccountName="jdoe", mail="jdoe@x.com",
            displayName="J Doe", memberOf=[],
        )]
        mocker.patch("app.services.ldap_service.Connection", return_value=mock_conn)
        # ^ verify import path with: grep "from ldap3" app/services/ldap_service.py

        ldap_svc = app.container.get("ldap_service")
        result = ldap_svc.search_user("jdoe")
        assert result is not None
        assert result["sAMAccountName"] == "jdoe"
    ```

    **For Genesys test mocking** — verify the actual HTTP call site by grepping `requests` imports in `app/services/base.py` and `app/services/genesys_service.py`. Patch at the module that owns the call (likely `app.services.base.requests` or `app.services.base.requests.request`).

    **For Genesys token-storage tests:**
    ```python
    def test_token_storage_round_trip(mocker, db_session, app):
        mocker.patch("app.services.base.requests.request", return_value=mocker.MagicMock(
            status_code=200, json=lambda: {"access_token": "new-tok", "expires_in": 3600}
        ))
        # Pre-condition: no genesys token in DB
        from app.models.api_token import ApiToken
        assert ApiToken.query.filter_by(service_name="genesys").first() is None

        gen_svc = app.container.get("genesys_service")
        ok = gen_svc.refresh_token_if_needed()
        assert ok is True

        token = ApiToken.query.filter_by(service_name="genesys").first()
        assert token is not None
        assert token.access_token == "new-tok"
    ```

    **DO NOT** chase 100% line coverage in these files. Target the documented critical paths in `<behavior>`. Coverage gating happens at the package level (60% across services+middleware), not per-file.
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; python -m pytest tests/unit/services/ -v --no-cov 2>&amp;1 | tail -40</automated>
  </verify>
  <acceptance_criteria>
    - All four files exist (`__init__.py` + 3 test modules).
    - `pytest tests/unit/services/test_search_orchestrator.py -v --no-cov` reports ≥8 tests collected, all PASS.
    - `pytest tests/unit/services/test_ldap_service.py -v --no-cov` reports ≥6 tests collected, all PASS.
    - `pytest tests/unit/services/test_genesys_service.py -v --no-cov` reports ≥6 tests collected, all PASS.
    - `grep -rc "@pytest.mark.unit" tests/unit/services/ | awk -F: '{sum+=$2} END {print sum}'` returns ≥20 (every test marked across the directory).
    - `grep -rE "patch\(.*config_get" tests/unit/services/` returns 0 (no direct config_get patching — uses DB-driven config per PATTERNS).
    - `grep -rE "from unittest" tests/unit/services/` returns 0 (uses pytest-mock, not unittest.mock).
    - `grep -c "ApiToken.query.filter_by(service_name=\"genesys\")" tests/unit/services/test_genesys_service.py` returns ≥1 (token round-trip test exists).
    - No real LDAP/Graph/Genesys network calls — verified by running without internet (`pytest tests/unit/services/ --no-cov` succeeds even with `unset HTTP_PROXY HTTPS_PROXY` and Docker offline mode).
    - `ruff check tests/unit/services/` clean.
  </acceptance_criteria>
  <done>20+ unit tests across the three hot service files all pass; mocks operate at the boundary (ldap3.Connection, requests.request); config exercised via real DB round-trip.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Auth pipeline + search flow integration tests (D-13, D-14)</name>
  <files>tests/integration/test_auth_pipeline.py, tests/integration/test_search_flow.py</files>
  <read_first>
    - app/middleware/auth.py (full file; lines 59-87 authenticate(); lines 101-119 missing-header path; lines 167-171 require_role failure)
    - app/middleware/authentication_handler.py (full file; header reading, dev bypass — DO NOT use bypass in tests per D-13)
    - app/middleware/user_provisioner.py (full file; first-login provisioning logic)
    - app/middleware/role_resolver.py (full file; role lookup chain)
    - app/blueprints/search/__init__.py (search route definitions; identify GET /search and the HTMX response shape — note this file is 2720 lines, focus only on the route handler for /search)
    - app/services/search_orchestrator.py (lines 79-133 execute_concurrent_search)
    - app/services/result_merger.py (full file or at least the merge() entry point — exercised end-to-end)
    - tests/integration/conftest.py (authenticated_client + admin_client fixtures from Plan 02)
    - tests/conftest.py (fake_ldap/fake_graph/fake_genesys fixtures)
    - tests/factories/user.py
    - .planning/phases/02-test-suite/02-PATTERNS.md (§"tests/integration/test_auth_pipeline.py", §"tests/integration/test_search_flow.py")
    - .planning/phases/02-test-suite/02-CONTEXT.md (D-13, D-14)
    - .planning/phases/01-foundation/01-CONTEXT.md (D-05/06 — request-ID + JSON logging; tests should verify request_id appears in caplog records when applicable; D-08 — Flask-Limiter, RATELIMIT_ENABLED=False set in conftest)
  </read_first>
  <behavior>
    **`test_auth_pipeline.py` (D-13 — target 4-6 tests):**
    - `test_valid_header_provisions_viewer_user` — `client.get("/", headers={principal_header: "newuser@example.com"})` → status 200; `User.query.filter_by(email="newuser@example.com").first()` exists with `role == "viewer"`; `g.user` was set (assert by hitting an endpoint that reflects it)
    - `test_missing_header_returns_401_or_redirect` — `client.get("/")` with no header → status 401 (or redirect to login per current behavior — verify by reading auth.py:101-119)
    - `test_existing_user_role_retained` — Pre-seed admin user via `UserFactory(email="admin@example.com", role="admin")`, then call `client.get("/admin/", headers={...: "admin@example.com"})` → status 200; user's role still `"admin"` (provisioner did NOT downgrade)
    - `test_insufficient_role_returns_401_with_nope_template` — Use `authenticated_client` (viewer), hit an admin-only route, assert status 401 (per auth.py:167-171 — verify exact code; spec says nope.html); assert response body contains "nope" or appropriate template marker
    - `test_audit_log_written_on_successful_auth` — Hit any auth-required endpoint successfully; query `AuditLog.query.filter_by(...)` and assert a row exists for the auth event
    - `test_request_id_present_in_log_records` — Hit endpoint, use `caplog`; assert at least one log record has `request_id` attribute (Phase 1 D-05 verification)

    **`test_search_flow.py` (D-14 — target 6-8 tests):**
    - `test_search_returns_merged_result_from_all_three_sources` — Pre-load fakes (ldap+graph+genesys with same email); `authenticated_client.get("/search?term=jdoe")` → status 200; response.data contains identifying string from each source (e.g., `b"jdoe@x.com" in response.data`, `b"AVAILABLE" in response.data` for Genesys status)
    - `test_search_no_results_returns_empty_state` — All three fakes empty; `authenticated_client.get("/search?term=nobody")` → status 200; response contains an empty-state marker (verify exact template — likely "No results" or similar)
    - `test_search_only_ldap_match_renders_partial_card` — Only fake_ldap loaded; assert response contains LDAP fields, no Genesys/Graph data
    - `test_search_only_genesys_match` — same pattern, Genesys-only
    - `test_search_only_graph_match` — same pattern, Graph-only
    - `test_search_multiple_ldap_results_renders_disambiguation` — fake_ldap returns multiple; assert response contains a disambiguation UI marker (e.g., "Multiple users found" or list of candidates)
    - `test_search_genesys_too_many_results_does_not_break_render` — `fake_genesys = FakeGenesysService(too_many=True)` (re-register); other two fakes loaded normally; assert status 200 and Genesys section shows graceful error (not a stack trace)
    - `test_search_unauthenticated_returns_401_or_redirect` — `client.get("/search?term=x")` (no header); status 401 or redirect (NOT 200)
  </behavior>
  <action>
    Create both test modules. Mark all tests with `@pytest.mark.integration`.

    **`tests/integration/test_auth_pipeline.py`** — top of file:
    ```python
    """Integration tests for the auth middleware pipeline (D-13).

    PHASE 4 NOTE: When Keycloak OIDC ships, this entire file gets rewritten against
    OIDC-callback flow. The fixtures (authenticated_client, admin_client) abstract
    the header-injection detail; only the test bodies that assert on header-specific
    behavior need to change.
    """
    import pytest

    pytestmark = pytest.mark.integration
    ```

    Use the `client` (unauthenticated) fixture for missing-header tests; use the `authenticated_client` and `admin_client` fixtures (from Plan 02 `tests/integration/conftest.py`) for the rest.

    For `test_request_id_present_in_log_records`:
    ```python
    def test_request_id_present_in_log_records(authenticated_client, caplog):
        import logging
        with caplog.at_level(logging.INFO):
            authenticated_client.get("/")
        # Phase 1 D-05: request_id is injected via RequestIdFilter into every log record
        records_with_id = [r for r in caplog.records if hasattr(r, "request_id")]
        assert len(records_with_id) > 0, "No log records carried request_id; OPS-02 broken"
    ```

    **`tests/integration/test_search_flow.py`** — top of file:
    ```python
    """Integration tests for the full search flow (D-14): /search → orchestrator → fakes → merger → HTMX fragment."""
    import pytest

    pytestmark = pytest.mark.integration
    ```

    For multi-fake setup, each test composes the three fixtures:
    ```python
    def test_search_returns_merged_result_from_all_three_sources(
        authenticated_client, fake_ldap, fake_graph, fake_genesys
    ):
        fake_ldap.add_user({"sAMAccountName": "jdoe", "mail": "jdoe@x.com", "displayName": "J Doe", "memberOf": []})
        fake_graph.add_user({"userPrincipalName": "jdoe@x.com", "id": "g-1", "assignedLicenses": [{"skuId": "x"}], "signInActivity": {"lastSignInDateTime": "2024-01-01T00:00:00Z"}})
        fake_genesys.add_user({"id": "gn-1", "email": "jdoe@x.com", "routingStatus": "AVAILABLE", "name": "J Doe"})

        response = authenticated_client.get("/search?term=jdoe")

        assert response.status_code == 200
        assert b"jdoe@x.com" in response.data
        assert b"AVAILABLE" in response.data  # Genesys status rendered
        # Optionally: BeautifulSoup for structural assertions
    ```

    **HTMX assertion strategy** (Discretion §4): use substring `in response.data` for simple presence checks, BeautifulSoup only when asserting on structure (e.g., specific section element exists). Pick the cleaner option per test.

    **For `test_search_genesys_too_many_results_does_not_break_render`** — needs to override the default `fake_genesys` fixture mid-test:
    ```python
    def test_search_genesys_too_many_results_does_not_break_render(
        authenticated_client, fake_ldap, fake_graph, container_reset
    ):
        from tests.fakes.fake_genesys_service import FakeGenesysService
        too_many_genesys = FakeGenesysService(too_many=True, too_many_total=500)
        container_reset.register("genesys_service", lambda c: too_many_genesys)
        container_reset.reset()

        fake_ldap.add_user({"sAMAccountName": "jdoe", "mail": "jdoe@x.com", "displayName": "J Doe", "memberOf": []})
        response = authenticated_client.get("/search?term=jdoe")
        assert response.status_code == 200
        # Either a graceful Genesys-error marker OR a missing-Genesys-section — pick what the template actually does
        assert b"500" in response.data or b"too many" in response.data.lower() or b"Genesys" in response.data
    ```

    **CRITICAL — exact route shape:** Read `app/blueprints/search/__init__.py` to confirm the search endpoint is `/search?term=...` vs `/search?q=...` vs POST. Adjust assertions to whatever the actual route accepts. Same for the HTMX fragment shape — read the template invocation in the route handler.

    **Rate limiting (Phase 1 D-08):** Verified disabled in Plan 02 conftest via `RATELIMIT_ENABLED=False`. NO rate-limit tests required in this plan — Phase 1's plan 01-08 already shipped the rate-limit tests; this phase does NOT need to retest.
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; python -m pytest tests/integration/ -v --no-cov 2>&amp;1 | tail -40</automated>
  </verify>
  <acceptance_criteria>
    - Both files exist with module-level `pytestmark = pytest.mark.integration`.
    - `pytest tests/integration/test_auth_pipeline.py -v --no-cov` reports ≥4 tests collected, all PASS.
    - `pytest tests/integration/test_search_flow.py -v --no-cov` reports ≥6 tests collected, all PASS.
    - `grep -c "PHASE 4 NOTE" tests/integration/test_auth_pipeline.py` returns 1.
    - `grep -c "fake_ldap\|fake_graph\|fake_genesys" tests/integration/test_search_flow.py` returns ≥6.
    - `grep -c "request_id" tests/integration/test_auth_pipeline.py` returns ≥1 (Phase 1 D-05 verification test exists).
    - `grep -rE "DANGEROUS_DEV_AUTH_BYPASS_USER" tests/` returns 0 (per D-13: tests must use real header injection, NOT the bypass).
    - `pytest tests/ -v --no-cov` (full suite) reports ≥30 tests total (sum across Plans 02-03), all PASS.
    - `ruff check tests/integration/` clean.
  </acceptance_criteria>
  <done>4+ auth tests cover the documented D-13 cases (provision, missing, insufficient, retained); 6+ search-flow tests cover the documented D-14 cases (merged, empty, single-source, multiple, too-many, unauthenticated); Phase 4 caveat documented; no real network calls.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| test client → Flask app | Tests inject Azure AD principal header directly; production trust comes from Azure App Service edge |
| fake services → orchestrator | Fakes return data shapes matching real services; orchestrator cannot tell them apart |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-08 | S (Spoofing) | Header injection in auth-pipeline tests | accept | Tests intentionally drive the real middleware via header injection (D-13). Production header trust is Azure App Service responsibility, not the app's. Phase 4 will replace with Keycloak. |
| T-02-09 | T (Tampering) | Tests assert on log content (caplog) — log injection scenarios untested | accept | Log injection mitigation lives in Phase 1's request-ID validator (regex `^[0-9a-fA-F-]{8,64}$`). Re-testing here would duplicate Phase 1 plan 04 coverage. |
| T-02-10 | I (Information Disclosure) | Test failure output may dump fake user data to CI logs | accept | Fake data is synthetic (`@test.local` emails, no real PII). |
</threat_model>

<verification>
- `pytest tests/ -v --no-cov` (full suite, coverage gate measured separately in Plan 04) returns success — every test in this plan and prior plans passes
- All tests marked `@pytest.mark.unit` or `@pytest.mark.integration` (no unmarked tests)
- Zero real LDAP/Graph/Genesys HTTP calls — verified by mocked transport at the right boundary in unit tests, fakes-only in integration tests
- Phase 4 caveat present at top of `test_auth_pipeline.py`
</verification>

<success_criteria>
- All Task 1-2 acceptance criteria pass
- Combined unit + integration test count ≥30
- Coverage measurement and the ≥60% gate are owned by Plan 04 (this plan only asserts test pass/fail behavior; coverage is verified end-to-end in Plan 04).
- No `mocker.patch("app.services.configuration_service.config_get")` or similar — config exercised via real DB round-trip
- No use of `DANGEROUS_DEV_AUTH_BYPASS_USER` in any test
</success_criteria>

<output>
After completion, create `.planning/phases/02-test-suite/02-03-SUMMARY.md` documenting:
- Exact test count per file
- Coverage delta achieved on services + middleware (rough number from initial run)
- Any test cases skipped/deferred + rationale
- Confirmation Phase 4 marker present in test_auth_pipeline.py
</output>
