# Encryption Key Rotation Runbook

## Overview

Rotate `WHODIS_ENCRYPTION_KEY` (and optionally the per-installation salt at
`.whodis_salt`) by re-encrypting every row in the `configuration` table from
the old key to a new one in a single transaction.

**When to rotate:**

- Suspected leak of the encryption key or salt file (e.g. `.whodis_salt` was
  accidentally committed to git history — see SEC-01)
- Scheduled rotation per your security policy
- After personnel change with prior key access
- Compliance event requiring fresh cryptographic material

**What gets re-encrypted:** every row in the `configuration` table where
`encrypted_value IS NOT NULL`.

**What does NOT change:**

- PostgreSQL credentials in `.env` (`POSTGRES_*`) — these are the bootstrap
  credentials and have a different lifecycle (see CLAUDE.md "Environment
  Variables Bootstrap Problem").
- Application code, schema, or non-encrypted configuration values.

## Pre-flight

1. **Confirm app health:** `curl http://localhost:5000/health` returns HTTP 200.
2. **Backup configuration:**

   ```bash
   python scripts/export_config.py > /tmp/whodis-config-backup-$(date +%Y%m%d-%H%M).json
   ```

   Verify the file is non-empty and human-readable. Keep this backup until
   the rotation is fully verified in production.

3. **Note current key fingerprint** (for audit / debugging):

   ```bash
   python -c "import os, hashlib; print(hashlib.sha256(os.getenv('WHODIS_ENCRYPTION_KEY').encode()).hexdigest()[:12])"
   ```

4. **Schedule a brief (~2 min) maintenance window.** An application restart is
   required after rotation so the running process picks up the new key.

## Rotation Procedure

1. **Generate the new key** and record it in your secret store (NOT in shell
   history):

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. **Optional — only if the salt file is suspected leaked (SEC-01):** delete
   `.whodis_salt` from the working directory. The encryption service will
   generate a fresh salt on next instantiation. Confirm `.whodis_salt` is
   gitignored before continuing:

   ```bash
   git check-ignore .whodis_salt
   ```

3. **Run dry-run** to confirm every row decrypts under the OLD key:

   ```bash
   OLD_WHODIS_ENCRYPTION_KEY=<current> NEW_WHODIS_ENCRYPTION_KEY=<new> \
       python scripts/rotate_encryption_key.py --dry-run
   ```

   Inspect the output — every row should print `re-encrypted <category>.<key>`
   followed by `DRY RUN — no changes committed.` The script must exit 0.

4. **Run for real** (same command without `--dry-run`):

   ```bash
   OLD_WHODIS_ENCRYPTION_KEY=<current> NEW_WHODIS_ENCRYPTION_KEY=<new> \
       python scripts/rotate_encryption_key.py
   ```

   Look for `Committed N row(s).` followed by
   `VERIFIED: all N row(s) decrypt cleanly with the new key.`

5. **Update the application's environment** with the new key: edit `.env` and
   replace `WHODIS_ENCRYPTION_KEY=...` with the new value. Update your secret
   store accordingly.

6. **Restart the application:** `python run.py` (or your process manager
   equivalent). Confirm `/health` returns 200.

7. **Final verification:** run `python scripts/verify_encrypted_config.py` —
   every row should decrypt cleanly under the new key.

## Rollback

1. **If verify failed and the script aborted before commit:** nothing to
   roll back at the database layer. Restore your `.env` to the original key
   if you changed it, then restart the app.

2. **If commit succeeded but the app fails to start with the new key:**
   re-set `.env`'s `WHODIS_ENCRYPTION_KEY` back to the OLD key and run the
   rotation script again with OLD/NEW reversed:

   ```bash
   OLD_WHODIS_ENCRYPTION_KEY=<new> NEW_WHODIS_ENCRYPTION_KEY=<original> \
       python scripts/rotate_encryption_key.py
   ```

3. **If the database is in a corrupt half-rotated state** (this should be
   impossible — the script commits all-or-nothing): restore the
   `Configuration` table from your backup using the existing import tool:

   ```bash
   python scripts/import_config.py /tmp/whodis-config-backup-*.json
   ```

## Notes

- Keep `WHODIS_ENCRYPTION_KEY` in your secret store. Do not commit it to
  version control. Do not paste it into shell history — use a secret manager
  CLI or a here-doc that pipes from the secret store.
- The PostgreSQL credentials in `.env` are NOT rotated by this procedure —
  they are the bootstrap credentials and have a different lifecycle (see
  CLAUDE.md "Environment Variables Bootstrap Problem").
- This runbook supersedes any ad-hoc key-rotation guidance in older docs.
