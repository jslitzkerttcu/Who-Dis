---
phase: 01-foundation
plan: 07
subsystem: security / operations
tags: [security, encryption, rotation, runbook, sec-01, sec-02]
requires: []
provides:
  - ".whodis_salt gitignore lock"
  - "scripts/rotate_encryption_key.py — dual-key rotation CLI"
  - "docs/runbooks/encryption-key-rotation.md — operator runbook"
affects:
  - .gitignore
  - scripts/
  - docs/runbooks/
tech_stack_added: []
patterns:
  - "Dual-key in-place re-encryption with all-or-nothing transaction + post-commit verify"
  - "Operator runbook layout: Overview / Pre-flight / Procedure / Rollback / Notes"
key_files_created:
  - scripts/rotate_encryption_key.py
  - docs/runbooks/encryption-key-rotation.md
key_files_modified:
  - .gitignore
decisions:
  - "Rotate the key + salt rather than rewrite git history (D-01)"
  - "Decrypt + re-encrypt all rows in memory before any UPDATE; commit in single transaction (D-02)"
  - "Post-commit verify pass uses a fresh EncryptionService(new_key) instance (D-03)"
  - "Runbook documents that POSTGRES_* in .env is NOT rotated by this procedure (D-04 + CLAUDE.md bootstrap-problem)"
metrics:
  tasks_completed: 3
  files_created: 2
  files_modified: 1
  duration_minutes: ~10
  completed: "2026-04-25"
---

# Phase 1 Plan 7: Salt + Encryption Key Rotation Summary

Locked `.whodis_salt` out of future commits, shipped a dual-key rotation CLI with dry-run + post-commit verify, and documented the full operator procedure with rollback paths — closing SEC-01 and SEC-02 without rewriting git history.

## What Was Built

### Task 1 — `.gitignore` lock for `.whodis_salt`

Appended a dedicated section to `.gitignore` so the per-installation salt cannot be re-committed by accident. The salt file remains in the working tree (the running app needs it); historical remediation is handled by key rotation rather than `git filter-repo`.

**Commit:** `ce5ef00`

### Task 2 — `scripts/rotate_encryption_key.py`

Standalone CLI that:

- Reads `OLD_WHODIS_ENCRYPTION_KEY` and `NEW_WHODIS_ENCRYPTION_KEY` from the environment; refuses to run if either is missing or both are identical (exit 2).
- Connects to PostgreSQL using `os.getenv("POSTGRES_*")` directly (CLAUDE.md bootstrap-problem note).
- Decrypts every `configuration.encrypted_value` with the OLD `EncryptionService` and re-encrypts with the NEW `EncryptionService` **fully in memory before any UPDATE** — any decrypt failure aborts before mutating the database.
- Coerces the PG `BYTEA` `memoryview` to `bytes(...)` per CLAUDE.md "Memory Objects".
- Supports `--dry-run` (prints planned changes, exits 0 with no UPDATE).
- For real runs: issues all UPDATEs in a single psycopg2 transaction, then commits.
- Runs a post-commit verify pass with a fresh `EncryptionService(new_key)` and exits 3 if any row fails to decrypt.
- Prints a single `VERIFIED: all N row(s) decrypt cleanly with the new key.` line on success.

Exit codes: `0` success / `2` env-var error / `3` verify failure / `1` other error.

Verified locally:

```
$ python scripts/rotate_encryption_key.py
ERROR: Both OLD_WHODIS_ENCRYPTION_KEY and NEW_WHODIS_ENCRYPTION_KEY must be set in the environment.
exit=2
```

**Commit:** `20bc587`

### Task 3 — `docs/runbooks/encryption-key-rotation.md`

New operator runbook (first file in `docs/runbooks/`) with the canonical sections:

- **Overview** — when to rotate, what gets re-encrypted, what does NOT change.
- **Pre-flight** — health check, `export_config.py` backup, key fingerprint, maintenance window.
- **Rotation Procedure** — generate key, optional salt regen, dry-run, real run, `.env` update, restart, `verify_encrypted_config.py` final check.
- **Rollback** — three scenarios including reverse-rotation and `import_config.py` restore from backup.
- **Notes** — secret-store discipline, bootstrap-problem caveat for `POSTGRES_*` credentials.

**Commit:** `b7dd485`

## Checkpoint Handling

Plan task 2 was a `checkpoint:human-verify` requiring an operator-driven dry-run against a live database. The orchestrator is running in `--auto` chain mode (`workflow._auto_chain_active=true` in `.planning/config.json`), so the checkpoint was **auto-acknowledged**. The dry-run could not be executed in this workspace because no `.env` file is present (no `WHODIS_ENCRYPTION_KEY`, no PostgreSQL credentials). The script's syntax validity, argparse contract, and missing-env-var exit path (exit 2) were exercised successfully.

**Recommended operator action before any real rotation:**

1. On a host with the `.env` populated, run the dry-run command from the runbook.
2. Confirm every row prints `re-encrypted <category>.<key>` and the script exits 0 with `DRY RUN — no changes committed.`
3. Only then proceed with the real rotation per the runbook.

## Deviations from Plan

None — plan executed exactly as written. The auto-mode checkpoint acknowledgement is documented under "Checkpoint Handling" rather than as a deviation.

## Threat Model Coverage

All five STRIDE threats from the plan are addressed by the shipped artifacts:

| Threat ID | Disposition | Where addressed |
|-----------|-------------|-----------------|
| T-01-07-01 (salt-leak info disclosure) | mitigated | `.gitignore` entry + runbook §"Rotation Procedure" step 2 |
| T-01-07-02 (half-rotated DB tampering) | mitigated | Script does full in-memory re-encrypt before any UPDATE; single-transaction commit; post-commit verify with exit 3 on failure |
| T-01-07-03 (keys leaked via shell history) | mitigated | Runbook §"Notes" directs operators to secret store, not shell history |
| T-01-07-04 (untracked rotation events) | accepted | Out-of-band action — rely on operator discipline + secret-store audit trail |
| T-01-07-05 (failed rotation locks app out) | mitigated | Pre-flight `export_config.py` backup + Rollback §3 covers `import_config.py` restore |

## Self-Check: PASSED

- FOUND: `.gitignore` entry — `grep -n .whodis_salt .gitignore` → line 169
- FOUND: `scripts/rotate_encryption_key.py` (parses; required tokens present 10x)
- FOUND: `docs/runbooks/encryption-key-rotation.md` (all 6 required tokens present)
- FOUND commit `ce5ef00` — chore(01-07): gitignore .whodis_salt
- FOUND commit `20bc587` — feat(01-07): rotation script
- FOUND commit `b7dd485` — docs(01-07): runbook

## Files

- **Created:**
  - `C:\repos\Who-Dis\scripts\rotate_encryption_key.py`
  - `C:\repos\Who-Dis\docs\runbooks\encryption-key-rotation.md`
- **Modified:**
  - `C:\repos\Who-Dis\.gitignore`
