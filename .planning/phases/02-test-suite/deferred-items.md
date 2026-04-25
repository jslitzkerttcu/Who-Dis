# Deferred Items — Phase 02 Test Suite

Items discovered during plan execution that are out of scope for this phase.

## Plan 02-03 Discoveries

### Production bug: `_render_unified_profile` crashes on missing services

**File:** `app/blueprints/search/__init__.py:1065`

**Symptom:** `AttributeError: 'NoneType' object has no attribute 'get'` when
either `genesys_data`, `azure_ad_result`, or `keystone_data` is None at the
template-render step. Reproduces for any single-source-only search hit, AND
when Genesys returns `too_many_results`.

**Tests that exercise it:**
- `test_search_only_ldap_match_renders` — xfailed
- `test_search_only_genesys_match` — xfailed
- `test_search_only_graph_match` — xfailed
- `test_search_genesys_too_many_results_does_not_break_render` — xfailed

**Why deferred:** 02-CONTEXT.md explicitly excludes blueprint hardening from
Phase 02 (search/__init__.py is 2720 lines). The xfail markers (strict=True)
will surface a passing test if a future fix lands; remove the markers at that
time.

### Pre-existing bug: `simple_config` set/get table mismatch

**File:** `app/services/simple_config.py`

**Symptom:** `config_set(key, value)` writes to the `configuration` table
(line 159: `INSERT INTO configuration ...`); `config_get(key)` reads from the
`simple_config` table (line 102: `SELECT value FROM simple_config WHERE...`).
Cache short-circuits the round-trip in production hot paths so this isn't
visible day-to-day, but breaks any test that wants to drive behavior via DB
seeding.

**Workaround in tests:** Pre-populate `service._config_cache` directly, or
patch the orchestrator's timeout properties via `mocker.patch.object(...,
new_callable=PropertyMock)`.

**Why deferred:** Beyond the scope of "write tests against existing code".
Fixing the simple_config tables would be its own plan.

### Pre-existing bug: `ApiToken.is_expired` is a method but treated as truthy

**File:** `app/models/api_token.py:117`

**Symptom:** `if not token.is_expired:` always evaluates to `if not <bound
method>` → always falsy → `get_token` returns None even for valid tokens. The
production code masks this because the next path (fetch new token) succeeds
when credentials are present.

**Workaround in tests:** Mock `ApiToken.get_token` to return a fake token
when exercising the cached-token path of `refresh_token_if_needed`.

**Why deferred:** Same as above — fixing requires changing model behavior
that production code already works around.

## Plan 02-03 Auto-Fixes Applied (in scope)

These were fixed inline because they blocked all test execution:

1. `tests/conftest.py` — psycopg2 DSN scheme stripping (testcontainers returns
   `postgresql+psycopg2://`, psycopg2 wants `postgresql://`).
2. `tests/conftest.py` — replaced SAVEPOINT-rollback with TRUNCATE-on-teardown
   for `db_session` (the savepoint pattern broke under sequential commits in
   integration tests).
3. `app/__init__.py` — gated `validate_required_config()` and four other
   `TESTING` checks on `os.environ.get("TESTING")` (was only checking
   `app.config["TESTING"]` which gets set AFTER `create_app()` returns).
