---
title: Wire LDAP ServerPool for tp-dc1 / tp-dc2 failover
status: pending
created: 2026-04-25
area: who-dis-services
priority: medium
source: Phase 9 SandCastle onboarding deploy
---

# Wire LDAP ServerPool for tp-dc1 / tp-dc2 failover

## What

`app/services/ldap_service.py:73-80` (and the duplicate sites at lines 118, 298, 624)
constructs a single `ldap3.Server` from `self.host`. There is no failover.

Refactor to:

1. Treat `LDAP_SERVER` as a comma-separated list (single host stays valid).
2. Build a `ServerPool([Server(h, ...) for h in hosts], pool_strategy=ROUND_ROBIN, active=True, exhaust=False)`
   once per `LDAPService` instance.
3. Pass that pool wherever the existing single-`Server` value goes today (test_connection,
   search_user, all four call sites).

## Why

Phase 9 SandCastle deploy currently sets `LDAP_SERVER=tp-dc1.ttcu.com`. `tp-dc2.ttcu.com`
is reachable from the SandCastle host and is meant to be a fallback, but the current code
can only target one host — if `tp-dc1` goes down, every Who-Dis search fails.

`sdc-dc2.ttcu.com` was also discussed but does not resolve from the SandCastle host's
DNS view; that one is a separate question.

## How to apply

When you pick this up, also collapse the four `Server(...)` constructor sites in
`app/services/ldap_service.py` to a single `_build_server_pool()` helper — they have
diverged slightly across the file and the new pool needs to live in one place.

## Acceptance

- `LDAP_SERVER=tp-dc1.ttcu.com,tp-dc2.ttcu.com` works end-to-end
- Manual fail test (point primary at a closed port; second host serves search)
- Existing single-host tests stay green

## Source

Caught during Phase 9 SandCastle onboarding deploy (Apr 2026), tracked in
`.planning/phases/09-who-dis-onboarding/` of `sandcastle-portal`.
