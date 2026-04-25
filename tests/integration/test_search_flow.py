"""Integration tests for the full search flow (D-14).

Path: POST /search → @require_role('viewer') → SearchOrchestrator.execute_concurrent_search
→ ResultMerger → SearchEnhancer → HTMX HTML fragment.

Search route is POST /search (URL prefix /search → effective /search/search) with
form param `query`. Verified against app/blueprints/search/__init__.py:793.
"""
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def viewer_client(client, db_session):
    """Test client with a pre-seeded viewer user + populated OIDC session —
    needed for @require_role('viewer') to pass on /search.

    Phase 9 (WD-AUTH-01): session replaces the principal header as the auth source.
    """
    from tests.factories.user import UserFactory

    UserFactory(email="test-viewer@example.com", role="viewer")
    with client.session_transaction() as sess:
        sess["user"] = {
            "email": "test-viewer@example.com",
            "sub": "test-sub-viewer",
            "name": "test-viewer",
            "roles": ["viewer"],
        }
    return client


def _post_search(client, term):
    """POST to /search/search (the URL-prefix-mounted POST /search route)."""
    return client.post("/search/search", data={"query": term})


def test_search_returns_merged_result_from_all_three_sources(
    viewer_client, fake_ldap, fake_graph, fake_genesys
):
    fake_ldap.add_user({
        "sAMAccountName": "jdoe", "mail": "jdoe@x.com",
        "displayName": "J Doe", "memberOf": [],
    })
    fake_graph.add_user({
        "userPrincipalName": "jdoe@x.com", "id": "g-1",
        "assignedLicenses": [], "signInActivity": {},
    })
    fake_genesys.add_user({
        "id": "gn-1", "email": "jdoe@x.com",
        "routingStatus": "AVAILABLE", "name": "J Doe",
    })

    response = _post_search(viewer_client, "jdoe")
    assert response.status_code == 200
    body = response.data
    # At least one identifying string from the merged result should appear
    assert b"jdoe" in body.lower() or b"J Doe" in body or b"AVAILABLE" in body, (
        f"None of the expected fragments rendered. First 500 bytes: {body[:500]!r}"
    )


def test_search_no_results_returns_empty_state(viewer_client, fake_ldap, fake_graph, fake_genesys):
    response = _post_search(viewer_client, "nobody-exists-xyz")
    assert response.status_code == 200
    # Empty result should still render (even if just an empty card grid)
    assert response.data is not None


@pytest.mark.xfail(
    reason="DEFERRED: app/blueprints/search/__init__.py:1065 _render_unified_profile "
    "crashes with AttributeError when genesys_data is None (single-source LDAP-only "
    "match). Production bug — out of scope for Phase 02 (blueprint hardening is "
    "deferred per 02-CONTEXT.md). Phase 8 'reporting' or a dedicated blueprint-"
    "hardening phase will fix.",
    strict=True,
)
def test_search_only_ldap_match_renders(viewer_client, fake_ldap, fake_graph, fake_genesys):
    fake_ldap.add_user({
        "sAMAccountName": "ldaponly", "mail": "ldaponly@x.com",
        "displayName": "LDAP Only", "memberOf": [],
    })
    response = _post_search(viewer_client, "ldaponly")
    assert response.status_code == 200


@pytest.mark.xfail(
    reason="DEFERRED: same _render_unified_profile crash as test_search_only_ldap_match_renders.",
    strict=True,
)
def test_search_only_genesys_match(viewer_client, fake_ldap, fake_graph, fake_genesys):
    fake_genesys.add_user({
        "id": "gn-2", "email": "genonly@x.com",
        "routingStatus": "AVAILABLE", "name": "Genesys Only",
    })
    response = _post_search(viewer_client, "genonly")
    assert response.status_code == 200


@pytest.mark.xfail(
    reason="DEFERRED: same _render_unified_profile crash as test_search_only_ldap_match_renders.",
    strict=True,
)
def test_search_only_graph_match(viewer_client, fake_ldap, fake_graph, fake_genesys):
    fake_graph.add_user({
        "userPrincipalName": "graphonly@x.com", "id": "g-2",
        "displayName": "Graph Only", "assignedLicenses": [], "signInActivity": {},
    })
    response = _post_search(viewer_client, "graphonly")
    assert response.status_code == 200


def test_search_multiple_ldap_results_renders(viewer_client, fake_ldap, fake_graph, fake_genesys):
    """Multiple LDAP hits should render without crashing — the disambiguation
    template is exercised (azureAD_multiple branch in the search route)."""
    fake_ldap.add_user({
        "sAMAccountName": "jdoe1", "mail": "jdoe1@x.com",
        "displayName": "J Doe 1", "memberOf": [],
    })
    fake_ldap.add_user({
        "sAMAccountName": "jdoe2", "mail": "jdoe2@x.com",
        "displayName": "J Doe 2", "memberOf": [],
    })
    response = _post_search(viewer_client, "jdoe")
    assert response.status_code == 200


@pytest.mark.xfail(
    reason="DEFERRED: when Genesys returns too_many_results, genesys_data is None; "
    "_render_unified_profile crashes (same bug as test_search_only_*_match tests). "
    "Out of scope per 02-CONTEXT.md (blueprint hardening deferred).",
    strict=True,
)
def test_search_genesys_too_many_results_does_not_break_render(
    viewer_client, fake_ldap, fake_graph, container_reset
):
    """too_many_results error path through ResultMerger should not 500 the
    search route — Genesys section may render an error marker or omit data."""
    from tests.fakes.fake_genesys_service import FakeGenesysService

    too_many = FakeGenesysService(too_many=True, too_many_total=500)
    container_reset.register("genesys_service", lambda c: too_many)
    container_reset.reset()

    fake_ldap.add_user({
        "sAMAccountName": "jdoe", "mail": "jdoe@x.com",
        "displayName": "J Doe", "memberOf": [],
    })
    response = _post_search(viewer_client, "jdoe")
    assert response.status_code == 200


def test_search_unauthenticated_blocked(client, db_session, fake_ldap, fake_graph, fake_genesys):
    """No principal header → @require_role('viewer') denies the request."""
    response = client.post("/search/search", data={"query": "x"}, follow_redirects=False)
    assert response.status_code in (301, 302, 401, 403)


def test_search_empty_term_returns_prompt(viewer_client, fake_ldap, fake_graph, fake_genesys):
    """Empty term short-circuits before orchestrator dispatch — see search/__init__.py:801-802."""
    response = viewer_client.post("/search/search", data={"query": ""})
    assert response.status_code == 200
    assert b"search term" in response.data.lower() or b"please enter" in response.data.lower()
