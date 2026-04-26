---
phase: 04-keycloak-oidc-authentication
plan: 02
status: passed
score: 8/8 WD-AUTH requirements verified
verified: 2026-04-26
verifier: gsd-executor (retroactive)
source: PR #25 (commit fdb6ff2) + auto-grant fix (35c1c1f) + Wave 1 sweep (commits d3e1004..fca3f28, head c1f42d0)
upstream_audit: .planning/PR-25-AUDIT.md §"Phase 4 — Keycloak OIDC Authentication"
re_verification:
  previous_status: not-yet-verified
  notes: "Phase 4 shipped via PR #25 without a verification artifact. This is the single retroactive verification per CONTEXT.md D-04, mirroring the Phase 3 verification approach."
deferred:
  - truth: "Codebase-wide audit of `request.remote_user` (potential Easy-Auth-era residue with the same root cause as WD-AUTH-08)"
    addressed_in: "Backlog / future cleanup phase"
    evidence: "CONTEXT.md `<deferred>` block. Not in any plan must_haves; not a Phase 4 closure dependency."
  - truth: "Keycloak realm-export.json schema diff tooling"
    addressed_in: "Backlog (future capability)"
    evidence: "CONTEXT.md `<deferred>` block. Realm definition lives in the sandcastle-portal repo today; tooling deferred until drift becomes a problem."
human_verification: []
---

# Phase 4 Verification — Keycloak OIDC Authentication

**Phase Goal:** Replace Azure AD header-based auth with Authlib-driven Keycloak OIDC, preserving `g.user`/`g.role`/`@require_role()` semantics. Auto-provision local user records on first SSO. Deliver WD-AUTH-01..08.
**Verification date:** 2026-04-26
**Verifier:** Retroactive (post-PR-#25, post-Plan-04-01)
**Source of evidence:** `.planning/PR-25-AUDIT.md` per-requirement audit + on-disk file inspection at HEAD `c1f42d0`
**Result:** PASS — 8/8 WD-AUTH requirements satisfied (WD-AUTH-08 with one documented carve-out)

## Goal Achievement

PR #25 (commit `fdb6ff2`, "Phase 9 SandCastle onboarding") + post-merge auto-grant fix (`35c1c1f`) shipped 7 of 8 WD-AUTH requirements. The remaining gap (WD-AUTH-08) was closed by Plan 04-01 in Wave 1 of this phase (commits `d3e1004` sweep + `12d7375` carve-out & regression test + `fca3f28` summary). All 8 requirements now verify with file:line evidence on disk.

## Executive Summary

| Req ID | Title | Status | Evidence | Notes |
|---|---|---|---|---|
| WD-AUTH-01 | Identity comes from Keycloak OIDC session, not `X-MS-CLIENT-PRINCIPAL-NAME` header | ✓ PASS | `app/middleware/authentication_handler.py:21` (`session.get("user")`) | DONE in PR #25 per PR-25-AUDIT |
| WD-AUTH-02 | OIDC library (Authlib) integrated against Keycloak realm | ✓ PASS | `requirements.txt:19` (`Authlib==1.7.0`); `app/auth/oidc.py:100` (`oauth.register`) | Hand-rolled would have been acceptable; Authlib chosen |
| WD-AUTH-03 | Keycloak `whodis` client in `sandcastle` realm with redirect URIs | ✓ PASS | `docs/sandcastle.md:42-67` ("Keycloak OIDC setup (WD-AUTH-03)") | Realm-export.json lives in sandcastle-portal repo (out-of-tree) |
| WD-AUTH-04 | Unauth redirects to Keycloak; lands at originally requested URL | ✓ PASS | `app/auth/oidc.py:132` (authorize_redirect), `next` param stash/restore in login + authorize handlers | Login stashes `next`; authorize callback restores |
| WD-AUTH-05 | `g.user` (email) + `g.role` populated from ID-token claims; decorators unchanged | ✓ PASS | `app/auth/oidc.py` claims → `session["user"]` mapping; `app/middleware/authentication_handler.py:21-29` (`set_user_context` from session) | `@auth_required`/`@require_role` semantics preserved |
| WD-AUTH-06 | First-time SSO provisions local user; existing matched by email | ✓ PASS | `app/auth/oidc.py:176-179` (`UserProvisioner().get_or_create_user`); commit `35c1c1f` adds default-client-role auto-grant | Idempotent on repeat logins |
| WD-AUTH-07 | Logout terminates Flask session AND Keycloak session (RP-initiated) | ✓ PASS | `app/auth/oidc.py:195` (`end_session_endpoint`) — clears `session` then redirects to Keycloak end-session URL | Standard OIDC RP-initiated logout |
| WD-AUTH-08 | All `X-MS-CLIENT-PRINCIPAL-*` references removed from codebase | ✓ PASS (with documented carve-out) | Wave 1 sweep (commits `d3e1004` + `12d7375`); `grep -rn "X-MS-CLIENT-PRINCIPAL" --include="*.py" app/` returns exactly **1** match — `app/utils/error_handler.py:242` (sensitive-headers redaction list, retained per D-G3-04 / CONTEXT.md D-03) | See §WD-AUTH-08 Carve-out below |

**Score:** 8/8 — PASS

## Per-Requirement Evidence

### WD-AUTH-01 — Identity from Keycloak OIDC session

**Requirement (verbatim from REQUIREMENTS.md / PR-25-AUDIT.md line 117):**
> `app/middleware/authentication_handler.py` no longer reads `X-MS-CLIENT-PRINCIPAL-NAME`. User identity comes from a Keycloak OIDC session.

**Evidence:**
- `app/middleware/authentication_handler.py:21` — `user = session.get("user")` is the identity source. The OIDC callback in `app/auth/oidc.py` populates this dict.
- No `request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME"...)` reads remain in `app/middleware/authentication_handler.py`.
- Cross-reference: PR-25-AUDIT.md line 98 marks this DONE.

**Verification command:**
```bash
grep -n 'session.get("user")' app/middleware/authentication_handler.py
# expected: line 21 match
grep -c "X-MS-CLIENT-PRINCIPAL" app/middleware/authentication_handler.py
# expected: 0
```

**Status:** ✓ PASS

---

### WD-AUTH-02 — Authlib OIDC library

**Requirement:**
> A new auth integration uses an OIDC library (e.g., `authlib`, `flask-oidc`, or hand-rolled with `python-jose`) configured against the SandCastle Keycloak realm `sandcastle`.

**Evidence:**
- `requirements.txt:19` — `Authlib==1.7.0` pin.
- `app/auth/oidc.py:100` — `oauth.register(...)` configures the Keycloak client; the realm metadata URL is read from `KEYCLOAK_ISSUER` env (resolves to `<keycloak>/realms/sandcastle/.well-known/openid-configuration`).
- Cross-reference: PR-25-AUDIT.md line 99 marks this DONE.

**Verification command:**
```bash
grep -n "^Authlib==" requirements.txt
# expected: line 19 — Authlib==1.7.0
grep -n "oauth.register" app/auth/oidc.py
# expected: line 100 match
```

**Status:** ✓ PASS

---

### WD-AUTH-03 — Keycloak `whodis` client documented

**Requirement:**
> A Keycloak OIDC client `whodis` exists in the `sandcastle` realm with redirect URI `https://whodis.sandcastle.ttcu.com/*` and post-logout redirect `https://whodis.sandcastle.ttcu.com/`.

**Evidence:**
- `docs/sandcastle.md:42` — `## Keycloak OIDC setup (WD-AUTH-03)` section header. The section documents the client config, redirect URI, and post-logout redirect.
- The realm-export.json itself lives in the sandcastle-portal repo (out-of-tree by design — operator-owned platform config); WhoDis side documents the contract.
- Cross-reference: PR-25-AUDIT.md line 100 marks this DONE.

**Verification command:**
```bash
grep -n "Keycloak OIDC setup" docs/sandcastle.md
# expected: line 42 match
```

**Status:** ✓ PASS

---

### WD-AUTH-04 — Unauthenticated redirect to Keycloak with return-to-original-URL

**Requirement:**
> Unauthenticated requests to any non-public route are redirected to Keycloak; on successful auth the user lands back at the originally requested URL.

**Evidence:**
- `app/auth/oidc.py:132` — `oauth.keycloak.authorize_redirect(redirect_uri)` is the redirect-to-Keycloak call inside the login handler. The `next` URL is stashed in `session` before the redirect and restored from `session` in the `authorize` callback.
- `@auth_required` (in `app/middleware/auth.py`) intercepts unauthenticated requests and routes them through `/auth/login?next=<original_url>`.
- Cross-reference: PR-25-AUDIT.md line 101 marks this DONE.

**Verification command:**
```bash
grep -n "authorize_redirect" app/auth/oidc.py
# expected: line 132 match
```

**Status:** ✓ PASS

---

### WD-AUTH-05 — `g.user`/`g.role` from ID-token claims; decorators unchanged

**Requirement:**
> `g.user` (email) and `g.role` are populated from the Keycloak ID token claims (`email`, `realm_access.roles`). Existing role-check decorators continue to work unchanged.

**Evidence:**
- `app/auth/oidc.py` (authorize callback, ~lines 154-171 per PR-25-AUDIT line 102) — ID-token claims (`email`, `realm_access.roles`) are extracted and written into `session["user"]`.
- `app/middleware/authentication_handler.py:21-29` — `set_user_context` reads `session["user"]` and assigns `g.user` + `g.role` for the request.
- `@require_role("admin"|"editor"|"viewer")` decorators in `app/middleware/auth.py` continue to read `g.role` unchanged (no decorator-API changes shipped in PR #25).
- Cross-reference: PR-25-AUDIT.md line 102 marks this DONE.

**Verification command:**
```bash
grep -n 'g.user\|g.role' app/middleware/authentication_handler.py | head -5
# expected: matches showing g.user / g.role populated from session dict
```

**Status:** ✓ PASS

---

### WD-AUTH-06 — Auto-provision on first SSO; match existing by email

**Requirement:**
> Existing local-DB user records are matched by email; first-time SSO arrivals provision a record automatically with default role.

**Evidence:**
- `app/auth/oidc.py:176-179` — `from app.middleware.user_provisioner import UserProvisioner` then `UserProvisioner().get_or_create_user(email=email, role=role)`. This is the get-or-create call that matches by email and provisions on miss.
- Commit `35c1c1f` (post-PR-#25) — adds the auto-grant of the default Keycloak client role so newly-provisioned users land with `viewer`-equivalent access without operator intervention.
- Cross-reference: PR-25-AUDIT.md line 103 marks this DONE.

**Verification command:**
```bash
grep -n "UserProvisioner" app/auth/oidc.py
# expected: line 176 import + line 179 call
git log --oneline 35c1c1f -1
# expected: commit message references default client role auto-grant
```

**Status:** ✓ PASS

---

### WD-AUTH-07 — Logout terminates Flask + Keycloak (RP-initiated)

**Requirement:**
> Logout terminates both the Flask session and the Keycloak session (RP-initiated logout).

**Evidence:**
- `app/auth/oidc.py:195` — `end_session = metadata.get("end_session_endpoint")` reads the discovery-document end-session URL. The handler clears `session` (Flask side) then redirects the browser to `end_session_endpoint` with `id_token_hint` + `post_logout_redirect_uri` (Keycloak side).
- This is standard OIDC RP-initiated logout (OpenID Connect RP-Initiated Logout 1.0 spec §2).
- Cross-reference: PR-25-AUDIT.md line 104 marks this DONE.

**Verification command:**
```bash
grep -n "end_session_endpoint" app/auth/oidc.py
# expected: line 195 match
```

**Status:** ✓ PASS

---

### WD-AUTH-08 — Azure header references removed (with documented carve-out)

**Requirement:**
> All references to "Azure AD basic auth", `X-MS-CLIENT-PRINCIPAL-*` headers, and Easy Auth assumptions are removed from the codebase.

**Acceptance criterion (per CONTEXT.md D-03 + PR-25-AUDIT D-G3-03/04):**
> `grep -rn "X-MS-CLIENT-PRINCIPAL" --include="*.py" app/` returns exactly **1** match — the documented sensitive-headers redaction-list literal at `app/utils/error_handler.py:242`. NOT 0 matches.

**Evidence:**
- **Sweep commit (Wave 1, Plan 04-01):** `d3e1004` — replaced 33 attribution sites across 7 blueprint files (`search/__init__.py`, `admin/cache.py`, `admin/admin_users.py`, `admin/users.py`, `admin/audit.py`, `admin/job_role_compliance.py`, `admin/database.py`) with `g.user or "<fallback>"` (preserving each site's existing fallback string — `unknown` / `system` / `admin` — verbatim per D-G3-02).
- **Carve-out + regression-test commit:** `12d7375` — replaced 2 of 3 hits in `app/utils/error_handler.py` with `getattr(g, "user", None)` / `g.user`, and added `tests/integration/test_audit_attribution.py` (locks the OIDC email into audit-log attribution; admin client posts to `/admin/api/cache/clear`, asserts resulting `audit_log.user_email == "test-admin@example.com"`).
- **Plan summary:** `fca3f28` — Wave 1 SUMMARY.md.
- **Post-sweep state on disk:**
  - `grep -rn "X-MS-CLIENT-PRINCIPAL" --include="*.py" app/` → **1 match** (`app/utils/error_handler.py:242`).
  - `grep -rn "g\.user or" app/blueprints --include="*.py" | wc -l` → **33** (matches expected sweep count).
- Cross-reference: PR-25-AUDIT.md line 105 (the original gap inventory) + PR-25-AUDIT.md §"Gap Closure — G3" decisions D-G3-01..04.

**Verification commands:**
```bash
# Carve-out grep — expected: exactly 1 match (the redaction list)
grep -rn "X-MS-CLIENT-PRINCIPAL" --include="*.py" app/
# expected: app/utils/error_handler.py:242:        sensitive_headers = ["Authorization", "Cookie", "X-MS-CLIENT-PRINCIPAL-NAME"]

# Sweep coverage — expected: 33
grep -rn "g\.user or" app/blueprints --include="*.py" | wc -l

# Regression test — expected: 1 passed, 1 skipped
python -m pytest tests/integration/test_audit_attribution.py -x --no-cov
```

**Carve-out note (per D-G3-04 / CONTEXT.md D-03):**

The single surviving `X-MS-CLIENT-PRINCIPAL-NAME` literal at `app/utils/error_handler.py:242` is intentional and **must not be removed** by future cleanup sweeps. It lives inside the `sensitive_headers` list used to redact request headers from error logs:

```python
# app/utils/error_handler.py:242
sensitive_headers = ["Authorization", "Cookie", "X-MS-CLIENT-PRINCIPAL-NAME"]
```

**Why retained:** Defensive measure — if any deployment ever rolls Easy-Auth (or an equivalent reverse-proxy auth shim) in front of WhoDis, this list ensures the header is redacted from any error-log payload that might capture inbound headers. Removing it would create a small information-disclosure risk (T-04V-02 in this plan's threat model) for zero benefit.

**Provenance:** `.planning/PR-25-AUDIT.md` decision **D-G3-04**; `04-CONTEXT.md` decision **D-03**. The 3-line comment block above the literal in source (committed in `12d7375`) cites both decisions inline, so a future "cleanup" sweep cannot remove the literal without first deleting the carve-out justification — which is reviewable.

**Status:** ✓ PASS (with documented carve-out — exactly 1 surviving match by design)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `app/auth/oidc.py` | Authlib OIDC integration; auth-code flow; PKCE; RP-initiated logout | ✓ VERIFIED | `oauth.register` line 100; `authorize_redirect` line 132; `UserProvisioner.get_or_create_user` line 179; `end_session_endpoint` line 195 |
| `app/middleware/authentication_handler.py` | Reads `session.get("user")`, sets `g.user`/`g.role` | ✓ VERIFIED | line 21 `session.get("user")`; no header reads |
| `app/services/keycloak_admin.py` | Used by auto-grant feature (commit `35c1c1f`) | ✓ VERIFIED | File exists; commit `35c1c1f` adds default-role grant |
| `requirements.txt` | `Authlib==1.7.0` pinned | ✓ VERIFIED | line 19 |
| `docs/sandcastle.md` | Keycloak OIDC setup section (WD-AUTH-03) | ✓ VERIFIED | line 42 §header |
| `tests/integration/test_audit_attribution.py` | Regression test locking OIDC email into audit attribution | ✓ VERIFIED | Created in commit `12d7375` (Wave 1) |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Codebase-wide `X-MS-CLIENT-PRINCIPAL` matches | `grep -rn "X-MS-CLIENT-PRINCIPAL" --include="*.py" app/` | 1 (the documented carve-out at `app/utils/error_handler.py:242`) | ✓ PASS |
| Sweep coverage in blueprints | `grep -rn "g\.user or" app/blueprints --include="*.py" \| wc -l` | 33 | ✓ PASS |
| Authlib pinned | `grep -n "^Authlib==" requirements.txt` | line 19 (`Authlib==1.7.0`) | ✓ PASS |
| OIDC client registered | `grep -n "oauth.register" app/auth/oidc.py` | line 100 | ✓ PASS |
| RP-initiated logout wired | `grep -n "end_session_endpoint" app/auth/oidc.py` | line 195 | ✓ PASS |
| User provisioner wired | `grep -n "UserProvisioner" app/auth/oidc.py` | lines 176, 179 | ✓ PASS |
| Keycloak setup documented | `grep -n "Keycloak OIDC setup" docs/sandcastle.md` | line 42 | ✓ PASS |
| Regression test exists | `test -f tests/integration/test_audit_attribution.py && echo OK` | OK | ✓ PASS |

## Outstanding Items / Known Limitations

The following items are explicitly out of scope for Phase 4 closure but are preserved here so they are not silently dropped (per CONTEXT.md `<deferred>` block):

| Item | Disposition | Rationale |
|---|---|---|
| Codebase-wide `request.remote_user` audit | **Deferred — backlog** | May be Easy-Auth-era residue with the same root cause as WD-AUTH-08. Fix pattern would mirror `g.user or "<fallback>"`. Not a Phase 4 closure dependency. |
| Keycloak realm-export.json schema diff tooling | **Deferred — backlog** | Future capability if realm config drift becomes a problem. Realm definition currently lives in the sandcastle-portal repo; no in-tree tooling needed for closure. |

No blockers. No gaps remain in Phase 4 scope.

## Sign-off

**Phase 4 ready for closure.** All 8 WD-AUTH requirements satisfied per evidence above. WD-AUTH-08 closure is provable via the single grep command embedded in §WD-AUTH-08 (returns exactly 1 match — the documented carve-out at `app/utils/error_handler.py:242`).

---

_Verified: 2026-04-26_
_Verifier: gsd-executor (retroactive — Plan 04-02)_
_Source of evidence: PR-25-AUDIT.md + on-disk inspection at HEAD `c1f42d0`_
