"""Authlib OIDC integration with the SandCastle Keycloak realm.

Auth-code flow with PKCE-or-client-secret negotiated via discovery. Tokens are
stored in the Flask signed-cookie session (D-02). Only minimal claims live in
the session to avoid the >4 KB cookie limit (Pitfall 3 in 09-RESEARCH.md).

Routes:
- GET /auth/login        — redirect to Keycloak; stashes ?next= for return
- GET /auth/authorize    — OIDC callback; exchanges code, populates session
- GET /auth/logout       — RP-initiated logout (WD-AUTH-07)
"""

import logging
import os
from typing import List, Optional
from urllib.parse import urlencode, urlparse

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, abort, redirect, request, session, url_for

logger = logging.getLogger(__name__)

# Roles known to Who-Dis (D-05 two-tier hierarchy mirrored in role_resolver).
_KNOWN_ROLES = frozenset({"admin", "viewer"})


def _grant_default_role_if_missing(email: str, claim_roles: List[str]) -> Optional[str]:
    """Auto-grant a who-dis client role on first federated login.

    Returns the role that was newly granted (so the caller can inject it into
    the in-flight session for this same request), or None if no grant was
    performed — either because the user already has a known role in their JWT
    claims or because the env opted out of auto-grant.

    Decision:
    - If the user's email (case-insensitive) is in WHODIS_LEGACY_ADMINS,
      grant `admin`. This is the migration path for the 5 legacy App Proxy
      admins captured in Phase 9 09-LEGACY-CAPTURE.md.
    - Otherwise grant `viewer` (least-privileged baseline).

    Failures are logged and swallowed — auth still succeeds, the user simply
    won't have a role this session and will hit the standard nope.html
    response. Set WHODIS_AUTOGRANT_DISABLED=1 to short-circuit entirely.
    """
    if any(r in _KNOWN_ROLES for r in claim_roles):
        return None
    if os.environ.get("WHODIS_AUTOGRANT_DISABLED", "").lower() in ("1", "true", "yes"):
        return None

    legacy_admins_csv = os.environ.get("WHODIS_LEGACY_ADMINS", "")
    legacy_admins = {
        a.strip().lower() for a in legacy_admins_csv.split(",") if a.strip()
    }
    target_role = "admin" if email in legacy_admins else "viewer"
    client_id = os.environ["KEYCLOAK_CLIENT_ID"]

    try:
        from app.services.keycloak_admin import KeycloakAdminClient

        admin = KeycloakAdminClient()
        user_id = admin.find_user_id_by_email(email)
        if not user_id:
            logger.warning("auto-grant: Keycloak user not found for %s", email)
            return None
        newly_assigned = admin.assign_client_role(
            user_id=user_id, client_id=client_id, role_name=target_role
        )
        if newly_assigned:
            logger.info(
                "auto-grant: granted %s.%s to %s", client_id, target_role, email
            )
        else:
            logger.info(
                "auto-grant: %s already had %s.%s", email, client_id, target_role
            )
        return target_role
    except Exception as exc:  # noqa: BLE001 — never block login on grant failure
        logger.error("auto-grant: failed for %s (%s): %s", email, target_role, exc)
        return None


# Singleton OAuth registry; init_app called from create_app() via init_oauth()
oauth = OAuth()


def init_oauth(app) -> None:
    """Register the Keycloak provider on the given Flask app.

    Reads KEYCLOAK_ISSUER, KEYCLOAK_CLIENT_ID, KEYCLOAK_CLIENT_SECRET from env.
    KEYCLOAK_CLIENT_SECRET is REQUIRED (confidential client per Phase 9 Plan 01).
    """
    oauth.init_app(app)

    issuer = os.environ["KEYCLOAK_ISSUER"]
    client_id = os.environ["KEYCLOAK_CLIENT_ID"]
    client_secret = os.environ[
        "KEYCLOAK_CLIENT_SECRET"
    ]  # confidential client (Plan 01)

    oauth.register(
        name="keycloak",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=f"{issuer.rstrip('/')}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _is_safe_next_url(target: Optional[str]) -> bool:
    """Reject open-redirects: only allow same-origin relative paths."""
    if not target:
        return False
    parsed = urlparse(target)
    # Only same-host or relative path. No scheme + netloc means relative.
    if parsed.netloc and parsed.netloc != request.host:
        return False
    return True


@auth_bp.route("/login")
def login():
    """Redirect to Keycloak for auth-code flow. Stashes ?next= for post-login return (WD-AUTH-04)."""
    next_url = request.args.get("next")
    if _is_safe_next_url(next_url):
        session["post_login_redirect"] = next_url
    redirect_uri = url_for(
        "auth.authorize", _external=True
    )  # https:// via ProxyFix (Plan 02)
    return oauth.keycloak.authorize_redirect(redirect_uri)


@auth_bp.route("/authorize")
def authorize():
    """OIDC callback. Exchanges code for tokens, populates session, provisions user (WD-AUTH-06)."""
    try:
        token = oauth.keycloak.authorize_access_token()
    except Exception as exc:  # noqa: BLE001 — surface failure as a re-login prompt
        logger.error("OIDC token exchange failed: %s", exc)
        return redirect(url_for("auth.login", reason="auth_failed"))
    # Authlib parses id_token claims when 'openid' scope was requested
    userinfo = token.get("userinfo") or oauth.keycloak.userinfo()
    claims = token.get("id_token_claims") or userinfo

    email_raw = userinfo.get("email") or claims.get("email")
    if not email_raw:
        logger.error("OIDC callback missing email claim; rejecting login")
        abort(401)
    email = str(email_raw).strip().lower()

    # Pitfall 3 mitigation — store ONLY minimal claims (cookie size limit).
    client_id = os.environ["KEYCLOAK_CLIENT_ID"]
    claim_roles = list(
        claims.get("resource_access", {}).get(client_id, {}).get("roles", [])
    )

    # Auto-grant default client role on first federated login. This closes the
    # "logged in but unauthorized" gap from Phase 9 — Keycloak doesn't grant
    # client roles to broker-federated users by default, so the JWT
    # resource_access list is empty until someone manually assigns one.
    granted = _grant_default_role_if_missing(email, claim_roles)
    effective_roles = claim_roles + ([granted] if granted else [])

    session["user"] = {
        "email": email,
        "sub": userinfo.get("sub") or claims.get("sub"),
        "name": userinfo.get("name") or claims.get("name"),
        "roles": effective_roles,
    }
    session.permanent = True

    # WD-AUTH-06 — first-time SSO provisions a local DB record (preserves audit FK).
    try:
        from app.middleware.user_provisioner import UserProvisioner

        role = "admin" if "admin" in effective_roles else "viewer"
        UserProvisioner().get_or_create_user(email=email, role=role)
    except Exception as exc:  # noqa: BLE001 — non-fatal; auth still succeeds
        logger.warning("User auto-provision failed for %s: %s", email, exc)

    target = session.pop("post_login_redirect", None)
    if not _is_safe_next_url(target):
        target = "/"
    return redirect(target)


@auth_bp.route("/logout")
def logout():
    """RP-initiated logout (WD-AUTH-07): clear Flask session AND end Keycloak session."""
    session.clear()
    try:
        metadata = oauth.keycloak.load_server_metadata()
        end_session = metadata.get("end_session_endpoint")
        post_logout = request.host_url
        if end_session:
            client_id = os.environ["KEYCLOAK_CLIENT_ID"]
            query = urlencode(
                {
                    "post_logout_redirect_uri": post_logout,
                    "client_id": client_id,
                }
            )
            return redirect(f"{end_session}?{query}")
    except Exception as exc:  # noqa: BLE001 — fall back to local redirect if metadata unavailable
        logger.warning("Could not load Keycloak metadata for logout: %s", exc)
    return redirect("/")
