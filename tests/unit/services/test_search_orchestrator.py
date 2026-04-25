"""Targeted unit tests for SearchOrchestrator (D-12).

Exercises the concurrent-merge, multiple_results, too_many_results, timeout, and
DN-second-pass code paths in app/services/search_orchestrator.py without making
real network calls — fakes are container-injected per the conftest fixtures.
"""
import time
import pytest

from app.services.search_orchestrator import SearchOrchestrator

pytestmark = pytest.mark.unit


def _build_orchestrator(app):
    """SearchOrchestrator is not container-registered; instantiate directly.

    Verified via grep: app/blueprints/search/__init__.py constructs it inline at
    multiple call sites (lines 338, 772, 832, 2664). No container key exists.
    """
    return SearchOrchestrator()


def test_concurrent_search_all_three_return_results(
    request_context, fake_ldap, fake_graph, fake_genesys, app
):
    fake_ldap.add_user(
        {"sAMAccountName": "jdoe", "mail": "jdoe@x.com", "displayName": "J Doe", "memberOf": []}
    )
    fake_graph.add_user(
        {
            "userPrincipalName": "jdoe@x.com",
            "id": "g-1",
            "assignedLicenses": [],
            "signInActivity": {},
        }
    )
    fake_genesys.add_user({"id": "gn-1", "email": "jdoe@x.com", "routingStatus": "AVAILABLE"})

    orch = _build_orchestrator(app)
    ldap_r, gen_r, graph_r = orch.execute_concurrent_search(search_term="jdoe")

    assert ldap_r["result"]["sAMAccountName"] == "jdoe"
    assert gen_r["result"]["routingStatus"] == "AVAILABLE"
    assert graph_r["result"]["userPrincipalName"] == "jdoe@x.com"
    assert all(r["error"] is None for r in (ldap_r, gen_r, graph_r))
    assert all(r["multiple"] is False for r in (ldap_r, gen_r, graph_r))


def test_concurrent_search_no_results(
    request_context, fake_ldap, fake_graph, fake_genesys, app
):
    orch = _build_orchestrator(app)
    ldap_r, gen_r, graph_r = orch.execute_concurrent_search(search_term="nobody")
    assert ldap_r["result"] is None
    assert gen_r["result"] is None
    assert graph_r["result"] is None
    assert all(r["error"] is None for r in (ldap_r, gen_r, graph_r))


def test_ldap_multiple_results_path(
    request_context, fake_ldap, fake_graph, fake_genesys, app
):
    fake_ldap.add_user({"sAMAccountName": "jdoe1", "mail": "jdoe1@x.com", "displayName": "J Doe1", "memberOf": []})
    fake_ldap.add_user({"sAMAccountName": "jdoe2", "mail": "jdoe2@x.com", "displayName": "J Doe2", "memberOf": []})

    orch = _build_orchestrator(app)
    ldap_r, _, _ = orch.execute_concurrent_search(search_term="jdoe")

    assert ldap_r["multiple"] is True
    assert ldap_r["result"]["multiple_results"] is True
    assert ldap_r["result"]["total"] == 2


def test_genesys_too_many_results_path(request_context, fake_ldap, fake_graph, container_reset, app):
    """FakeGenesys with too_many=True surfaces the orchestrator's degraded path
    (search_orchestrator.py:238-242). The error message gets normalized into
    genesys_result['error'] (a string), and result stays None."""
    from tests.fakes.fake_genesys_service import FakeGenesysService

    too_many = FakeGenesysService(too_many=True, too_many_total=500)
    container_reset.register("genesys_service", lambda c: too_many)
    container_reset.reset()

    orch = _build_orchestrator(app)
    _, gen_r, _ = orch.execute_concurrent_search(search_term="anything")

    assert gen_r["error"] is not None
    assert "500" in gen_r["error"] or "results" in gen_r["error"].lower()
    assert gen_r["result"] is None
    assert gen_r["multiple"] is False


class _SleepyLDAP:
    """Minimal ISearchService that sleeps to force a FutureTimeoutError."""

    def __init__(self, sleep_for):
        self._sleep_for = sleep_for

    @property
    def service_name(self):
        return "ldap"

    def test_connection(self):
        return True

    def search_user(self, search_term):
        time.sleep(self._sleep_for)
        return None

    def get_user_by_dn(self, dn):
        time.sleep(self._sleep_for)
        return None


def _seed_timeout_config(db_session, key, seconds=0):
    """Pre-populate the configuration_service in-memory cache so SearchOrchestrator's
    _get_config(key) hits a tiny timeout value. We poke the cache directly because
    simple_config.set_with_result writes to a different table than its get() reads
    from (a pre-existing pre-existing dual-table bug in simple_config.py — see
    Plan 02-03 SUMMARY.md "Deviations" for the trace). Tests that need to drive
    config behavior should fix the underlying bug; for timeout exercise, cache
    poking is sufficient and isolated."""
    from app.services.configuration_service import get_configuration_service

    svc = get_configuration_service()
    svc._cache[key] = str(seconds)


def test_ldap_timeout(db_session, container_reset, request_context, fake_graph, fake_genesys, app, mocker):
    container_reset.register("ldap_service", lambda c: _SleepyLDAP(sleep_for=1.0))
    container_reset.reset()

    orch = _build_orchestrator(app)
    # Patch the timeout property directly — simple_config's set/get table-name mismatch
    # makes DB-roundtrip seeding unreliable; tested via direct attribute override.
    mocker.patch.object(SearchOrchestrator, "ldap_timeout", new_callable=mocker.PropertyMock, return_value=0)
    ldap_r, _, _ = orch.execute_concurrent_search(search_term="x")

    assert ldap_r["error"] is not None
    assert "timed out" in ldap_r["error"].lower() or "timeout" in ldap_r["error"].lower()


class _SleepyGraph:
    def __init__(self, sleep_for):
        self._sleep_for = sleep_for

    @property
    def service_name(self):
        return "graph"

    @property
    def token_service_name(self):
        return "graph"

    def test_connection(self):
        return True

    def get_access_token(self):
        return "fake"

    def refresh_token_if_needed(self):
        return True

    def search_user(self, search_term, include_photo=False):
        time.sleep(self._sleep_for)
        return None

    def get_user_by_id(self, user_id, include_photo=False):
        time.sleep(self._sleep_for)
        return None


def test_graph_timeout(db_session, container_reset, request_context, fake_ldap, fake_genesys, app, mocker):
    container_reset.register("graph_service", lambda c: _SleepyGraph(sleep_for=1.0))
    container_reset.reset()

    orch = _build_orchestrator(app)
    mocker.patch.object(SearchOrchestrator, "graph_timeout", new_callable=mocker.PropertyMock, return_value=0)
    _, _, graph_r = orch.execute_concurrent_search(search_term="x")
    assert graph_r["error"] is not None
    assert "timed out" in graph_r["error"].lower() or "timeout" in graph_r["error"].lower()


class _SleepyGenesys:
    def __init__(self, sleep_for):
        self._sleep_for = sleep_for

    @property
    def service_name(self):
        return "genesys"

    @property
    def token_service_name(self):
        return "genesys"

    def test_connection(self):
        return True

    def get_access_token(self):
        return "fake"

    def refresh_token_if_needed(self):
        return True

    def search_user(self, search_term):
        time.sleep(self._sleep_for)
        return None

    def get_user_by_id(self, user_id):
        time.sleep(self._sleep_for)
        return None


def test_genesys_timeout(db_session, container_reset, request_context, fake_ldap, fake_graph, app, mocker):
    container_reset.register("genesys_service", lambda c: _SleepyGenesys(sleep_for=1.0))
    container_reset.reset()

    orch = _build_orchestrator(app)
    mocker.patch.object(SearchOrchestrator, "genesys_timeout", new_callable=mocker.PropertyMock, return_value=0)
    _, gen_r, _ = orch.execute_concurrent_search(search_term="x")
    assert gen_r["error"] is not None
    assert "timed out" in gen_r["error"].lower() or "timeout" in gen_r["error"].lower()


def test_dn_second_pass(request_context, fake_ldap, fake_graph, fake_genesys, app):
    """Orchestrator's get_user_by_dn second-pass branch (search_orchestrator.py:139-143)."""
    fake_ldap.add_user({
        "sAMAccountName": "jdoe",
        "mail": "jdoe@x.com",
        "displayName": "J Doe",
        "memberOf": [],
        "distinguishedName": "CN=jdoe,DC=x,DC=com",
    })

    orch = _build_orchestrator(app)
    ldap_r, _, _ = orch.execute_concurrent_search(
        search_term="ignored", ldap_user_dn="CN=jdoe,DC=x,DC=com"
    )
    assert ldap_r["result"] is not None
    assert ldap_r["result"]["sAMAccountName"] == "jdoe"


def test_orchestrator_uses_request_context(request_context, fake_ldap, fake_graph, fake_genesys, app):
    """Sanity check: orchestrator's copy_current_request_context wrappers don't crash
    when invoked inside a test_request_context (provided by request_context fixture)."""
    orch = _build_orchestrator(app)
    result = orch.execute_concurrent_search(search_term="x")
    assert isinstance(result, tuple)
    assert len(result) == 3
