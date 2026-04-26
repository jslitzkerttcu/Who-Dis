---
phase: 05
slug: database-migration-alembic
status: secured
threats_total: 0
threats_closed: 0
threats_open: 0
unregistered_flags: 0
asvs_level: standard
created: 2026-04-26
audited: 2026-04-26
---

# Phase 5 — Security

> Cross-phase security closure. Phase 5's threat surface is owned by other phases that shipped the work; this file records the cross-references and confirms `threats_open: 0`.

---

## Cross-Phase Coverage

Phase 5 has no `05-PLAN.md` or `05-SUMMARY.md` because the work landed via two upstream paths (per `05-CONTEXT.md` and `.planning/PR-25-AUDIT.md` §"Phase 5"):

| WD-DB Req | Where it shipped | Threat coverage |
|-----------|------------------|-----------------|
| WD-DB-01 — `DATABASE_URL` is sole connection string | Phase 3 Plan 03-02 (commits `8b90fb2`, `fc44ccf`, `9bdceaf`) + Plan 03-04 (`1c0b9a2`) | `03-SECURITY.md` — **T-03-02-01** (info-disclosure: URL never logged), **T-03-02-02** (tampering: POSTGRES_* composition deleted, no SQLite fallback), **T-03-02-03** (spoofing: `.env.example` + README cleansed), **T-03-04-02** (tampering: `init_db` propagates RuntimeError unwrapped), **T-03-04-03** (info-disclosure: README install block uses `DATABASE_URL`). All CLOSED. |
| WD-DB-02 — Alembic auto-applies on container start | PR #25 (`fdb6ff2`) `docker-entrypoint.sh:31`; baseline body populated by `01b291c` | No standalone threat register. Substance is operational sequencing — `alembic upgrade head` runs before gunicorn binds. The container-startup sequence is itself covered by Phase 3 entrypoint review (Plan 03-04 task set). No new attack surface introduced. |
| WD-DB-03 — SandCastle data-migration runbook | PR #25 (`fdb6ff2`) `scripts/cutover/{README.md, *.py, *.sh}` | Operator-only documentation + one-off scripts. `migrate_secrets_to_portal.py` handles secret material; secrets are read from the live env, posted to the SandCastle portal API over TLS, and never written to disk. Reviewed under PR #25 code-review. No new attack surface in production runtime. |
| WD-DB-04 — SQLAlchemy pool tuned for containers | PR #25 (`fdb6ff2`) `app/database.py:41-46` (`pool_size=5`, `pool_pre_ping=True`, `pool_recycle=1800`, `max_overflow=5`) | Pool tuning is a reliability/availability control, not a security control. Pool exhaustion produces structured logs (no stack traces with user data) per the original spec. No new attack surface. |
| WD-DB-05 — Schema-change roundtrip without manual `psql` | Alembic toolchain (PR #25) + Phase 3 deploy webhook | No standalone threat register. Eliminates the need for operator `psql` access, which **reduces** attack surface (no interactive DB shell required in the deploy path). Net-positive for security posture. |

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Container ↔ SandCastle Postgres | App connects via `DATABASE_URL` over the SandCastle internal Docker network | SQL traffic (TLS at SandCastle network boundary, plain on internal `internal` network per WD-NET-01) |
| Operator ↔ Cutover scripts | One-time data migration via `scripts/cutover/` | DB dumps, secret material in transit to SandCastle portal API |

Both boundaries are inherited from Phase 3's threat model — no Phase-5-specific boundaries introduced.

---

## Threat Register

No phase-local threats. All Phase-5-relevant threats are owned and closed by `03-SECURITY.md`:

| Cross-Ref | Source File | Status |
|-----------|-------------|--------|
| T-03-02-01 | `03-SECURITY.md` | CLOSED |
| T-03-02-02 | `03-SECURITY.md` | CLOSED |
| T-03-02-03 | `03-SECURITY.md` | CLOSED |
| T-03-04-02 | `03-SECURITY.md` | CLOSED |
| T-03-04-03 | `03-SECURITY.md` | CLOSED |

---

## Accepted Risks Log

No Phase-5-specific accepted risks. Phase-3 accepted risks (`T-03-01-03` Redis on internal network, `T-03-03-02` unauthenticated `/health`, `T-03-03-03` README docs) carry forward as the operational baseline; they are not re-asserted here.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-26 | 0 (cross-referenced to Phase 3) | 0 | 0 | `/gsd-secure-phase 5` (cross-phase resolution) |

---

## Sign-Off

- [x] All threats have a disposition (cross-referenced to `03-SECURITY.md`)
- [x] Accepted risks documented (none Phase-5-specific; Phase-3 baseline carries forward)
- [x] `threats_open: 0` confirmed
- [x] `status: secured` set in frontmatter

**Approval:** verified 2026-04-26 — cross-phase closure per `05-CONTEXT.md` D-01..D-03.
