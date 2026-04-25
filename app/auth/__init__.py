"""Phase 9 SandCastle auth module — Authlib server-side OIDC against Keycloak.

Replaces the old Easy-Auth header-based path (D-04). The OAuth instance is
initialized via init_oauth(app) from create_app(); the blueprint exposes
/auth/login, /auth/authorize, /auth/logout (WD-AUTH-01..04, WD-AUTH-07).
"""
from app.auth.oidc import auth_bp, init_oauth, oauth

__all__ = ["auth_bp", "init_oauth", "oauth"]
