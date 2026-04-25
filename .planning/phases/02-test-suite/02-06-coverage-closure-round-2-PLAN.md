---
phase: 02-test-suite
plan: 06
type: execute
wave: 6
depends_on: [02-05-coverage-closure]
gap_closure: true
files_modified:
  - tests/unit/services/test_result_merger.py
  - tests/unit/services/test_search_enhancer.py
  - tests/unit/services/test_graph_service.py
  - tests/unit/services/test_token_refresh_service.py
  - tests/unit/services/test_audit_service_postgres.py
autonomous: true
requirements: [TEST-04]
tags: [testing, coverage, gap-closure, round-2]

must_haves:
  truths:
    - "Combined statement+branch coverage on `app/services/` + `app/middleware/` is ≥60% (the `--cov-fail-under=60` gate in pyproject.toml passes)"
    - "`pytest tests/` exits 0 with the existing pyproject.toml addopts (no `--no-cov`, no `--cov-fail-under` override on the CLI)"
    - "Pre-push hook (`.githooks/pre-push` → `make test`) unblocks ordinary pushes from a clean clone without `--no-verify`"
    - "Each of the 5 previously low-coverage service files has at least one passing pytest module under `tests/unit/services/` that exercises happy-path + at-least-one error path"
    - "No production code in `app/services/` is modified by this plan (coverage rises purely from new tests, not by deleting branches)"
    - "pyproject.toml `[tool.pytest.ini_options]` `--cov-fail-under=60` value is unchanged (gate scope per D-11 preserved)"
  artifacts:
    - path: "tests/unit/services/test_result_merger.py"
      provides: "Boundary tests for ResultMerger (closes ~50% of 173 missed stmts; search-flow critical path)"
      contains: "def test_"
      min_lines: 80
    - path: "tests/unit/services/test_search_enhancer.py"
      provides: "Boundary tests for SearchEnhancer (closes ~50% of 112 missed stmts; currently 0% covered)"
      contains: "def test_"
      min_lines: 60
    - path: "tests/unit/services/test_graph_service.py"
      provides: "Boundary tests for GraphService — REAL implementation, not FakeGraphService (closes ~40% of 191 missed stmts)"
      contains: "def test_"
      min_lines: 80
    - path: "tests/unit/services/test_token_refresh_service.py"
      provides: "Boundary tests for TokenRefreshService background runner (closes ~50% of 92 missed stmts)"
      contains: "def test_"
      min_lines: 60
    - path: "tests/unit/services/test_audit_service_postgres.py"
      provides: "Boundary tests for AuditServicePostgres (closes ~40% of 155 missed stmts)"
      contains: "def test_"
      min_lines: 60
  key_links:
    - from: "tests/unit/services/test_result_merger.py"
      to: "app/services/result_merger.py"
      via: "Direct ResultMerger() instantiation; build merged-record dicts in fixtures, assert on merge output"
      pattern: "from app.services.result_merger"
    - from: "tests/unit/services/test_search_enhancer.py"
      to: "app/services/search_enhancer.py"
      via: "Direct SearchEnhancer() instantiation; mock LDAP/Graph calls at module boundary"
      pattern: "from app.services.search_enhancer"
    - from: "tests/unit/services/test_graph_service.py"
      to: "app.services.graph_service.requests + msal"
      via: "mocker.patch on module-imported symbols (NOT FakeGraphService — exercise real code)"
      pattern: "patch\\(.app\\.services\\.graph_service"
    - from: "tests/unit/services/test_token_refresh_service.py"
      to: "app.services.token_refresh_service.<service registrations>"
      via: "mocker.patch on container.get to inject fakes; do NOT spawn the real background thread"
      pattern: "patch.*container"
    - from: "tests/unit/services/test_audit_service_postgres.py"
      to: "app.services.audit_service_postgres.AuditServicePostgres"
      via: "Direct instantiation + db_session fixture; assert on AuditLog rows"
      pattern: "from app.services.audit_service_postgres"
---

<objective>
**Round 2 of Phase 2 gap closure.** After Plan 02-05, combined services+middleware coverage sits at **47.08%** (post-PR-#25 merge), still below the **60%** `--cov-fail-under` gate (D-11). Five further service files account for the remaining ~13pp gap:

| File | Coverage | Missed Stmts | Priority Reason |
|------|---------:|-------------:|-----------------|
| search_enhancer.py | 0.0% | 112 | Search-flow critical path; cheapest lift (no current tests at all) |
| result_merger.py | 9.6% | 173 | Search-flow critical path; cross-provider merge logic |
| graph_service.py | 10.2% | 191 | Real GraphService never runs in suite — FakeGraphService shadows it |
| audit_service_postgres.py | 16.6% | 155 | Compliance/audit critical; only exercised indirectly via middleware |
| token_refresh_service.py | 17.0% | 92 | Background-thread runner; OAuth token rotation |

This plan adds boundary-style tests for each, targeting ~50% per-file coverage. Combined with side-effect lift on already-partly-covered base classes (`base.py` 71.9%, `configuration_service.py` 52.6%), this should push aggregate coverage to **~60-62%** and unblock the pre-push hook permanently.

**Boundary-style means:** for each file, write ~6-10 tests covering (a) instantiation + 1 happy path, (b) 1-2 key error / fallback paths, (c) any auth/header/config edge that's cheap to exercise. Do NOT chase per-file 100% — the gate is package-level.

Purpose: close the final Phase 2 gap so `git push` from a clean tree succeeds without `--no-verify` and the merge-protection contract from D-09 / SC #4 stops silently degrading to "developers always bypass."

Output: 5 new test modules; combined coverage ≥60%; `pytest tests/` exits 0.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/phases/02-test-suite/02-CONTEXT.md
@.planning/phases/02-test-suite/02-PATTERNS.md
@.planning/phases/02-test-suite/02-VERIFICATION.md
@.planning/phases/02-test-suite/02-05-SUMMARY.md
@.planning/phases/02-test-suite/deferred-items.md
@app/services/result_merger.py
@app/services/search_enhancer.py
@app/services/graph_service.py
@app/services/token_refresh_service.py
@app/services/audit_service_postgres.py
@app/services/base.py
@tests/conftest.py
@tests/unit/conftest.py
@tests/unit/services/test_search_orchestrator.py
@tests/unit/services/test_genesys_service.py
@tests/unit/services/test_genesys_cache_db.py
@tests/unit/services/test_refresh_employee_profiles.py

<interfaces>
<!-- Public methods to target on each file under test. Verify exact signatures
     by reading source — these are extracted for orienting the executor. -->

# app/services/result_merger.py — class ResultMerger
#   merge_results(ldap_data, graph_data, genesys_data) -> Dict          [main orchestrator]
#   _normalize_email(email) -> str                                       [pure]
#   _identify_primary_match(ldap, graph, genesys) -> str                [pure]
#   _merge_ad_section(ldap, graph) -> Dict                              [pure-ish]
#   _merge_genesys_section(genesys) -> Dict                             [pure]
#   _detect_conflicts(merged) -> List[Dict]                             [pure]
#   _build_unified_profile(merged) -> Dict                              [pure]
#   handle_no_results() -> Dict                                         [pure]
#   handle_too_many_results(source, total) -> Dict                      [pure]

# app/services/search_enhancer.py — class SearchEnhancer
#   This module is currently 0.0% covered — entire file is fresh ground.
#   Read the source to identify entry points; likely:
#   enhance(merged_result) -> Dict       [adds derived fields like is_active, primary_email]
#   _flag_compliance_issues(...) -> List
#   _resolve_display_name(ldap, graph) -> str
#   _compute_account_status(ldap, graph) -> str

# app/services/graph_service.py — class GraphService(BaseAPIService, ITokenService)
#   uses module-level `import requests` and `import msal`. Patch both at
#   `app.services.graph_service.requests` / `app.services.graph_service.msal`.
#   _get_access_token() -> Optional[str]                       [DB lookup via ApiToken + msal refresh]
#   refresh_token_if_needed() -> bool                          [token-service interface]
#   search_user(term: str) -> Optional[Dict[str, Any]]         [main entry]
#   get_user_photo(upn: str) -> Optional[bytes]                [HTTP GET, returns None on 404]
#   get_user_groups(upn: str) -> List[str]                     [paginated]
#   get_user_signin_activity(upn: str) -> Optional[Dict]
#   _make_graph_request(method, url, ...) -> Optional[Dict]    [shared HTTP plumbing]

# app/services/token_refresh_service.py — class TokenRefreshService
#   This is the BACKGROUND THREAD orchestrator (TESTING gate prevents auto-start in tests).
#   refresh_all_tokens() -> Dict[str, bool]                    [calls each ITokenService impl]
#   refresh_service_token(service_name) -> bool                [single-service refresh]
#   get_token_status() -> Dict                                 [health check]
#   _run_refresh_loop() -> None                                [DO NOT call directly in tests]

# app/services/audit_service_postgres.py — class AuditServicePostgres(IAuditService)
#   log_search(user_email, search_term, ...) -> AuditLog       [INSERT]
#   log_admin_action(user_email, action, target, ...) -> AuditLog
#   log_authentication_success(user_email, role, ...) -> AuditLog
#   log_access_denied(user_email, role, ...) -> AccessAttempt
#   log_error(error_type, message, ...) -> ErrorLog
#   get_recent_audit_logs(limit=100) -> List[AuditLog]
#   get_audit_logs_paginated(page, size, filters) -> Tuple[List, int]
#   cleanup_old_logs(days_to_keep=90) -> Dict[str, int]
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: SearchEnhancer boundary tests (cheapest lift — currently 0% covered)</name>
  <files>tests/unit/services/test_search_enhancer.py</files>
  <read_first>
    - app/services/search_enhancer.py (full file — identify all public entry points; this is currently 0% covered so the test module is greenfield)
    - app/services/result_merger.py (sister module — SearchEnhancer often consumes ResultMerger output)
    - tests/unit/services/test_search_orchestrator.py (analog test layout — pytestmark, fixtures, marker usage)
    - .planning/phases/02-test-suite/02-PATTERNS.md (test patterns)
  </read_first>
  <behavior>
    Target 6-10 tests covering ~50% of 112 missed statements:
    - 1 instantiation/smoke test
    - 2-3 happy-path tests for the main `enhance()` (or equivalent) entry point with merged-result fixtures
    - 2-3 edge cases: missing genesys section, missing graph section, missing ldap section
    - 1-2 helper/pure-function tests if the file exposes any (display-name resolution, account-status computation)

    All inputs should be plain dicts. Avoid DB. Avoid HTTP. Pure-function-style tests where possible.
  </behavior>
  <action>
    Create `tests/unit/services/test_search_enhancer.py`:
    ```python
    """Boundary tests for SearchEnhancer (Plan 02-06 gap closure round 2)."""
    import pytest

    pytestmark = pytest.mark.unit
    ```
    Use the existing `app` fixture if SearchEnhancer needs Flask context. Otherwise instantiate directly.
    Build merged-result fixtures inline:
    ```python
    @pytest.fixture
    def merged_result():
        return {
            "ad": {"sAMAccountName": "jdoe", "mail": "jdoe@x.com", ...},
            "graph": {"userPrincipalName": "jdoe@x.com", "id": "g-1", ...},
            "genesys": {"id": "gn-1", "email": "jdoe@x.com", ...},
        }
    ```
    Use `pytest-mock` for any patches. NO `unittest.mock`.
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; python -m pytest tests/unit/services/test_search_enhancer.py -v --no-cov 2>&amp;1 | tail -15</automated>
  </verify>
  <acceptance_criteria>
    - File exists.
    - `pytest tests/unit/services/test_search_enhancer.py -v --no-cov` reports ≥6 tests, all PASS.
    - `grep -c "def test_" tests/unit/services/test_search_enhancer.py` returns ≥6.
    - Per-file coverage check: `pytest tests/unit/services/test_search_enhancer.py --cov=app.services.search_enhancer --cov-report=term --no-cov-on-fail 2>&1 | grep search_enhancer.py` shows coverage ≥40% (was 0.0%).
    - `ruff check tests/unit/services/test_search_enhancer.py` clean.
    - `grep -rE "from unittest" tests/unit/services/test_search_enhancer.py` returns 0.
  </acceptance_criteria>
  <done>6+ unit tests passing; per-file coverage on search_enhancer.py ≥40% (was 0.0%).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: ResultMerger boundary tests (search-flow critical path)</name>
  <files>tests/unit/services/test_result_merger.py</files>
  <read_first>
    - app/services/result_merger.py (full 537L — focus on merge_results main entry, _identify_primary_match, _merge_ad_section, _detect_conflicts, handle_no_results, handle_too_many_results)
    - tests/integration/test_search_flow.py (analog — this exercises ResultMerger end-to-end, but unit tests should hit it directly)
    - tests/unit/services/test_search_orchestrator.py (analog test layout)
  </read_first>
  <behavior>
    Target 8-10 tests covering ~50% of 173 missed stmts. Pure functions are the cheap wins:
    - `test_merge_results_all_three_sources_present` — happy path; assert merged dict has ad/graph/genesys/unified sections
    - `test_merge_results_only_ldap` — graph and genesys empty/None; assert merged result is still well-formed (NOT the deferred AttributeError bug — assert on the merge output, not on _render_unified_profile)
    - `test_merge_results_only_graph` — same shape
    - `test_merge_results_only_genesys` — same shape
    - `test_merge_results_no_sources_returns_empty_state` — all three None/empty; assert merged result has empty sections, no exception
    - `test_normalize_email_strips_and_lowercases` — pure helper
    - `test_identify_primary_match_prefers_ldap_when_present` — pure helper precedence test
    - `test_handle_no_results_returns_empty_dict_with_marker` — pure
    - `test_handle_too_many_results_includes_count` — pure
    - `test_detect_conflicts_when_emails_disagree` — pure; assert returns ≥1 conflict dict

    Skip `_build_unified_profile` deeply — that's the buggy path covered by xfail-strict markers in test_search_flow.py. Don't try to fix the bug here.
  </behavior>
  <action>
    Create `tests/unit/services/test_result_merger.py`. Build dict fixtures inline. NO DB, NO HTTP. All tests should be sub-millisecond.

    For the `merge_results_only_*` cases, mirror the xfail bug landscape: if the merge logic itself works fine but downstream blueprint rendering breaks, the unit test on the merger should still pass — it's the consumer (search blueprint) that has the bug.

    Pre-existing production bugs (per `deferred-items.md`) — if encountered, mark `@pytest.mark.xfail(strict=True, reason=...)`. Otherwise PASS.
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; python -m pytest tests/unit/services/test_result_merger.py -v --no-cov 2>&amp;1 | tail -20</automated>
  </verify>
  <acceptance_criteria>
    - File exists.
    - `pytest tests/unit/services/test_result_merger.py -v --no-cov` reports ≥8 tests, all PASS or xfail-strict.
    - `grep -c "def test_" tests/unit/services/test_result_merger.py` returns ≥8.
    - Per-file coverage: `pytest tests/unit/services/test_result_merger.py --cov=app.services.result_merger --cov-report=term --no-cov-on-fail` shows coverage ≥45% (was 9.6%).
    - `grep -rE "from unittest" tests/unit/services/test_result_merger.py` returns 0.
    - `ruff check tests/unit/services/test_result_merger.py` clean.
  </acceptance_criteria>
  <done>8+ tests passing; per-file coverage on result_merger.py ≥45% (was 9.6%).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: GraphService boundary tests (real impl, not FakeGraphService)</name>
  <files>tests/unit/services/test_graph_service.py</files>
  <read_first>
    - app/services/graph_service.py (full file — confirm `import requests` + `import msal` are module-level; method signatures for search_user, get_user_photo, get_user_groups, get_user_signin_activity, _get_access_token, refresh_token_if_needed)
    - app/services/base.py (BaseAPIService methods graph_service inherits)
    - app/models/api_token.py (ApiToken model — graph_service may load tokens from DB)
    - tests/unit/services/test_genesys_service.py (analog test layout — uses `mocker.patch("app.services.base.requests.request")` for HTTP mocking; graph_service may use a different module path)
    - tests/unit/services/test_genesys_cache_db.py (analog — module-boundary HTTP patching pattern)
  </read_first>
  <behavior>
    Target 8-10 tests covering ~40% of 191 missed stmts. The CRITICAL distinction is: the integration tests use FakeGraphService (registered via `fake_graph` fixture in conftest); these unit tests must exercise the REAL `app.services.graph_service.GraphService` class.

    - `test_search_user_returns_none_when_no_token` — patch `_get_access_token` to return None; assert `search_user("x") is None`, no exception
    - `test_search_user_happy_path_single_match` — mock requests + msal at module boundary; assert returned dict has expected fields
    - `test_search_user_happy_path_multiple_matches` — mock returns 2+ users; assert `multiple_results=True` flag in response
    - `test_search_user_handles_404` — mock returns 404; assert returns None
    - `test_search_user_handles_timeout` — mock raises TimeoutError; assert returns None (NOT raises)
    - `test_get_user_photo_returns_bytes_on_200` — mock returns 200 with bytes content; assert returned bytes match
    - `test_get_user_photo_returns_none_on_404` — mock returns 404; assert None
    - `test_get_user_groups_paginated` — mock returns 2 pages of groups; assert all groups across pages collected
    - `test_refresh_token_if_needed_returns_false_when_msal_fails` — mock msal.acquire_token_for_client to return error dict; assert False, no exception
    - `test_refresh_token_if_needed_returns_true_on_success` — mock msal returns valid token; assert True; assert new ApiToken row written

    DO NOT use the `fake_graph` fixture in this file — that overrides the container, defeating the point.
  </behavior>
  <action>
    Create `tests/unit/services/test_graph_service.py`. Top:
    ```python
    """Boundary tests for GraphService (real impl) — Plan 02-06 gap closure.

    The integration tests use FakeGraphService via the `fake_graph` fixture.
    These unit tests exercise the actual app.services.graph_service.GraphService
    so that the 191 missed statements (msal flow, requests plumbing, error
    handling) are covered.
    """
    import pytest

    pytestmark = pytest.mark.unit
    ```

    Patch at the right module path. `graph_service.py` likely imports `requests` directly — patch `app.services.graph_service.requests` (verify by reading source line 1-30). msal usage: patch `app.services.graph_service.msal` or `msal.ConfidentialClientApplication` depending on import style.

    For DB-touching paths (ApiToken read/write), use `db_session` fixture + ApiTokenFactory. For pure HTTP paths, use only `mocker`.

    No real network. No real msal. Verify by `grep -rE "import requests|from requests" tests/unit/services/test_graph_service.py` returns only the patch lines, no real imports.
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; python -m pytest tests/unit/services/test_graph_service.py -v --no-cov 2>&amp;1 | tail -20</automated>
  </verify>
  <acceptance_criteria>
    - File exists.
    - `pytest tests/unit/services/test_graph_service.py -v --no-cov` reports ≥8 tests, all PASS or xfail-strict.
    - `grep -c "def test_" tests/unit/services/test_graph_service.py` returns ≥8.
    - `grep -c "patch\(.app\.services\.graph_service" tests/unit/services/test_graph_service.py` returns ≥3 (correct module-path patching).
    - `grep -rE "fake_graph" tests/unit/services/test_graph_service.py` returns 0 (no FakeGraphService usage).
    - Per-file coverage: `pytest tests/unit/services/test_graph_service.py --cov=app.services.graph_service --cov-report=term --no-cov-on-fail` shows coverage ≥40% (was 10.2%).
    - `ruff check tests/unit/services/test_graph_service.py` clean.
  </acceptance_criteria>
  <done>8+ tests passing; per-file coverage on graph_service.py ≥40% (was 10.2%); FakeGraphService not used.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: TokenRefreshService boundary tests</name>
  <files>tests/unit/services/test_token_refresh_service.py</files>
  <read_first>
    - app/services/token_refresh_service.py (full file — confirm method signatures for refresh_all_tokens, refresh_service_token, get_token_status; identify how the background thread is gated by TESTING)
    - app/__init__.py (lines 141, 163, 184, 193, 201 — TESTING gate confirms thread doesn't auto-start in tests)
    - app/interfaces/token_service.py (ITokenService interface — services that get refreshed)
    - tests/unit/services/test_genesys_service.py (analog test for a service implementing ITokenService)
  </read_first>
  <behavior>
    Target 6-8 tests covering ~50% of 92 missed stmts. The background thread MUST NOT run in tests (TESTING gate); these tests call public methods directly.

    - `test_refresh_all_tokens_calls_each_token_service` — patch container.get_all_by_interface to return 3 fake services; assert each `refresh_token_if_needed` is called once
    - `test_refresh_all_tokens_returns_status_per_service` — assert returned dict has key per service name with bool value
    - `test_refresh_all_tokens_handles_one_failure` — one fake raises; assert other services still refreshed; assert returned dict has False for the failer
    - `test_refresh_service_token_unknown_service_returns_false` — call with name not in container; assert False
    - `test_refresh_service_token_happy_path` — mock service returns True; assert True returned
    - `test_get_token_status_aggregates_apit_token_rows` — pre-seed 2 ApiToken rows via factory; assert returned dict has token info per service

    DO NOT call `_run_refresh_loop` (the background thread entry).
  </behavior>
  <action>
    Create `tests/unit/services/test_token_refresh_service.py`. Use `container_reset` fixture to swap in fake ITokenService implementations:
    ```python
    @pytest.fixture
    def fake_token_services(container_reset, mocker):
        fake1 = mocker.MagicMock(name="genesys")
        fake1.refresh_token_if_needed.return_value = True
        fake2 = mocker.MagicMock(name="graph")
        fake2.refresh_token_if_needed.return_value = True
        # register against ITokenService interface — verify exact registration mechanism
        # by reading container.get_all_by_interface implementation
        ...
        return [fake1, fake2]
    ```

    Read `app/container.py` `get_all_by_interface` to verify how to inject fakes that satisfy the interface lookup.
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; python -m pytest tests/unit/services/test_token_refresh_service.py -v --no-cov 2>&amp;1 | tail -15</automated>
  </verify>
  <acceptance_criteria>
    - File exists.
    - `pytest tests/unit/services/test_token_refresh_service.py -v --no-cov` reports ≥6 tests, all PASS.
    - `grep -c "def test_" tests/unit/services/test_token_refresh_service.py` returns ≥6.
    - `grep -rE "_run_refresh_loop|while True" tests/unit/services/test_token_refresh_service.py` returns 0 (no thread-loop invocation).
    - Per-file coverage: `pytest tests/unit/services/test_token_refresh_service.py --cov=app.services.token_refresh_service --cov-report=term --no-cov-on-fail` shows coverage ≥45% (was 17.0%).
    - `ruff check tests/unit/services/test_token_refresh_service.py` clean.
  </acceptance_criteria>
  <done>6+ tests passing; per-file coverage on token_refresh_service.py ≥45% (was 17.0%); no background thread invocation.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 5: AuditServicePostgres boundary tests</name>
  <files>tests/unit/services/test_audit_service_postgres.py</files>
  <read_first>
    - app/services/audit_service_postgres.py (full file — method signatures for log_search, log_admin_action, log_authentication_success, log_access_denied, log_error, get_recent_audit_logs, get_audit_logs_paginated, cleanup_old_logs)
    - app/models/audit_log.py + app/models/access_attempt.py + app/models/error_log.py (assertion targets)
    - tests/unit/services/test_search_orchestrator.py (analog test layout)
  </read_first>
  <behavior>
    Target 6-8 tests covering ~40% of 155 missed stmts. All DB-driven (uses `db_session` fixture):

    - `test_log_search_inserts_audit_row` — call `log_search("user@x", "jdoe", ip="1.1.1.1")`; assert AuditLog row exists with matching fields
    - `test_log_admin_action_inserts_with_target` — call `log_admin_action("admin@x", "user_role_change", target="other@x")`; assert row exists with action_type=admin_action
    - `test_log_authentication_success_records_role` — call; assert AuditLog row contains role string
    - `test_log_access_denied_creates_access_attempt_row` — call; assert AccessAttempt row exists (different table than AuditLog)
    - `test_log_error_creates_error_log_row` — call `log_error(error_type="db_error", message="...")`; assert ErrorLog row exists
    - `test_get_recent_audit_logs_orders_by_timestamp_desc` — pre-seed 3 AuditLog rows with different timestamps; assert returned list is desc-ordered
    - `test_get_audit_logs_paginated_returns_tuple` — pre-seed 5 rows; call with page=1, size=2; assert returned tuple is (list-of-2, total=5)
    - `test_cleanup_old_logs_deletes_rows_older_than_threshold` — pre-seed 1 old (created_at = now - 100 days) + 1 recent; call cleanup with days_to_keep=90; assert old deleted, recent retained

    No HTTP mocking needed (this service is pure DB). No external IO.
  </behavior>
  <action>
    Create `tests/unit/services/test_audit_service_postgres.py`. Use `db_session` + `app` fixtures. Direct service instantiation:
    ```python
    @pytest.fixture
    def audit_svc(app, db_session):
        from app.services.audit_service_postgres import AuditServicePostgres
        return AuditServicePostgres()
    ```

    Sanity-check assertion shape against the actual model columns by reading `app/models/audit_log.py` etc. before writing the tests.
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; python -m pytest tests/unit/services/test_audit_service_postgres.py -v --no-cov 2>&amp;1 | tail -15</automated>
  </verify>
  <acceptance_criteria>
    - File exists.
    - `pytest tests/unit/services/test_audit_service_postgres.py -v --no-cov` reports ≥6 tests, all PASS.
    - `grep -c "def test_" tests/unit/services/test_audit_service_postgres.py` returns ≥6.
    - Per-file coverage: `pytest tests/unit/services/test_audit_service_postgres.py --cov=app.services.audit_service_postgres --cov-report=term --no-cov-on-fail` shows coverage ≥40% (was 16.6%).
    - `ruff check tests/unit/services/test_audit_service_postgres.py` clean.
  </acceptance_criteria>
  <done>6+ tests passing; per-file coverage on audit_service_postgres.py ≥40% (was 16.6%).</done>
</task>

<task type="auto">
  <name>Task 6: Run full suite, verify 60% gate passes, update VERIFICATION.md</name>
  <files>.planning/phases/02-test-suite/02-VERIFICATION.md (append; do NOT overwrite canonical content)</files>
  <read_first>
    - .planning/phases/02-test-suite/02-VERIFICATION.md (append a "Gap Closure Round 2 (Plan 02-06)" section at the end)
    - pyproject.toml (confirm `--cov-fail-under=60` unchanged)
  </read_first>
  <action>
    1. Run the full suite with the configured gate:
       ```bash
       cd C:/repos/Who-Dis && pytest tests/ 2>&1 | tee /tmp/phase02-06-run.log
       ```
       Capture exit code, total test count, coverage line.

    2. **Verify exit code is 0.** If non-zero, identify which file's per-file coverage didn't lift enough; add 2-3 more tests in the corresponding test_*.py until the gate passes.

    3. **Verify pyproject.toml gate value unchanged:** `grep "cov-fail-under" pyproject.toml` MUST still show `--cov-fail-under=60`. If lowered, REVERT.

    4. **Verify pre-push hook unblocks ordinary pushes:**
       ```bash
       bash .githooks/pre-push 2>&1
       echo "hook_exit=$?"
       ```
       Must exit 0.

    5. **Append a "Gap Closure Round 2 (Plan 02-06)" section to VERIFICATION.md** at the bottom. Use the same shape as Plan 02-05's appended section:
       - Coverage delta table (services / middleware / combined)
       - Per-file coverage table (5 files this plan targets)
       - Tests added table
       - Gate status (exit code, gate value, hook status)
       - Verification status flip from `gaps_found` → `verified`

    6. **Sanity-check no production code modified:**
       ```bash
       git diff --stat app/ requirements.txt pyproject.toml Makefile .githooks/
       ```
       Should be empty.
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; pytest tests/ 2>&amp;1 | tail -5 &amp;&amp; echo "===" &amp;&amp; grep "cov-fail-under" pyproject.toml &amp;&amp; echo "===" &amp;&amp; bash .githooks/pre-push &amp;&amp; echo "hook=PASS" &amp;&amp; grep -c "Gap Closure Round 2 (Plan 02-06)" .planning/phases/02-test-suite/02-VERIFICATION.md</automated>
  </verify>
  <acceptance_criteria>
    - `pytest tests/` (no `--no-cov`, no CLI override) exits 0.
    - Run output contains the pytest-cov success line `Required test coverage of 60% reached. Total coverage: \d+\.\d+%`.
    - `grep -c "cov-fail-under=60" pyproject.toml` returns ≥1 (gate unchanged).
    - `bash .githooks/pre-push` exits 0.
    - `git diff --stat app/ requirements.txt pyproject.toml Makefile .githooks/ | wc -l` returns 0.
    - VERIFICATION.md contains a `## Gap Closure Round 2 (Plan 02-06)` H2 section with real numbers (no leftover `<X>` placeholders).
    - Full suite test count is ≥110 (pre-plan baseline) + ≥34 added by Tasks 1-5 = ≥144 tests.
  </acceptance_criteria>
  <done>Phase 2 gap CLOSED: `pytest tests/` exits 0, coverage gate passes ≥60%, pre-push hook unblocks ordinary pushes, VERIFICATION.md flips to `verified`.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| test process → mocked external services | Tests patch `requests`, `msal`, `pyodbc` at module-import boundaries; no real network or DB-warehouse calls. Same pattern as Plan 02-03 / 02-05. |
| test DB → application code | Tests drive real SQLAlchemy operations against the testcontainers Postgres instance — same trust boundary as Plan 02-05's DB-driven tests. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-16 | T (Tampering) | GraphService unit tests could pass while production msal flow is broken if mock returns are too permissive | mitigate | Patch at `app.services.graph_service.requests` and `.msal`, exercise both happy + error paths. Per-file coverage threshold ≥40% forces real branch coverage. |
| T-02-17 | I (Information Disclosure) | AuditServicePostgres tests insert real-looking PII | accept | Test DB is ephemeral testcontainer; data synthetic via factories (`@test.local` emails). |
| T-02-18 | D (Denial of Service) | Token-refresh tests could accidentally spawn the background thread | mitigate | Acceptance criterion bans `_run_refresh_loop` invocation; TESTING env var gates thread start in `app/__init__.py`. |
</threat_model>

<verification>
- All 5 implementation tasks (1-5) pass acceptance criteria; per-file coverage on each of the 5 targeted services is ≥40% (up from 0-17%).
- Task 6 confirms aggregate coverage ≥60% by running `pytest tests/` with the existing pyproject.toml gate and getting exit 0.
- pyproject.toml `--cov-fail-under=60` value verified unchanged (D-11 preserved).
- No production code modifications in `app/`, `requirements*.txt`, `Makefile`, `.githooks/`.
- VERIFICATION.md retains canonical content + "Gap Closure (Plan 02-05)" section + new "Gap Closure Round 2 (Plan 02-06)" section with real numbers.
- Pre-push hook (`bash .githooks/pre-push`) exits 0 from a clean tree, demonstrating ordinary pushes are no longer blocked.
- Phase 2 verification status flips from `gaps_found` to `verified`.
</verification>

<success_criteria>
- All Task 1-6 acceptance criteria pass.
- Combined services+middleware coverage ≥60% (the contract from D-11 / TEST-04 / ROADMAP SC #2).
- `pytest tests/` exits 0 from a clean clone with no `--no-verify` workaround needed.
- VERIFICATION.md flipped from `gaps_found` to `verified`.
- Phase 2 fully closed.
</success_criteria>

<output>
After completion, create `.planning/phases/02-test-suite/02-06-SUMMARY.md` documenting:
- Final combined coverage percentage (services + middleware, line+branch as the gate measures)
- Per-file coverage delta for the 5 targeted services (before vs after)
- Total tests added (count per file + grand total)
- Any new xfail-strict markers added
- Confirmation that pyproject.toml `--cov-fail-under=60` value is unchanged
- One-paragraph note: "Phase 2 verification flipped to `verified` — what changed for the developer" (e.g., `git push` no longer requires `--no-verify`, the gate is finally green, Phase 2 is complete)
</output>
