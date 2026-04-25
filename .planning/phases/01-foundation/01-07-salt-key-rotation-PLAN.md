---
phase: 01-foundation
plan: 07
type: execute
wave: 1
depends_on: []
files_modified:
  - .gitignore
  - scripts/rotate_encryption_key.py
  - docs/runbooks/encryption-key-rotation.md
autonomous: false
requirements: [SEC-01, SEC-02]
must_haves:
  truths:
    - ".whodis_salt is listed in .gitignore so it is never re-committed"
    - "scripts/rotate_encryption_key.py exists, supports --dry-run, and re-encrypts every Configuration row from OLD_WHODIS_ENCRYPTION_KEY to NEW_WHODIS_ENCRYPTION_KEY in a single transaction"
    - "After commit the script verifies every row decrypts cleanly with the new key"
    - "docs/runbooks/encryption-key-rotation.md exists with pre-flight, rotation-order, and rollback sections"
  artifacts:
    - path: "scripts/rotate_encryption_key.py"
      provides: "CLI tool — dry-run + commit + post-commit verify"
      contains: "OLD_WHODIS_ENCRYPTION_KEY"
    - path: "docs/runbooks/encryption-key-rotation.md"
      provides: "Operator runbook with ordered steps"
      contains: "Pre-flight"
    - path: ".gitignore"
      provides: "Excludes .whodis_salt from version control"
      contains: ".whodis_salt"
  key_links:
    - from: "scripts/rotate_encryption_key.py"
      to: "app/services/encryption_service.py"
      via: "EncryptionService(old_key) / EncryptionService(new_key) instances"
      pattern: "EncryptionService"
---

<objective>
Remediate the salt-file leak via rotation (not git history rewrite) and ship a CLI tool that safely rotates `WHODIS_ENCRYPTION_KEY` with dual-key in-place re-encryption. Satisfies SEC-01, SEC-02.

Purpose: The historical `.whodis_salt` commit is read-only history; rotating the key + salt makes any leaked artifact useless. The script + runbook become the operator's primary key-rotation tool for the life of the project.
Output: `.gitignore` updated, new script in `scripts/`, new runbook in `docs/runbooks/`. One human checkpoint to confirm the script's dry-run output before committing for real.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation/01-CONTEXT.md
@.planning/phases/01-foundation/01-PATTERNS.md
@CLAUDE.md
@scripts/verify_encrypted_config.py
@scripts/export_config.py
@app/services/encryption_service.py
@.gitignore
</context>

<tasks>

<task type="auto">
  <name>Task 1: gitignore .whodis_salt (SEC-01)</name>
  <read_first>
    - .gitignore (current contents — confirm .whodis_salt not already ignored)
    - .planning/phases/01-foundation/01-CONTEXT.md §"Salt File & Encryption Key" D-01 (rationale)
  </read_first>
  <action>
    Per D-01 / SEC-01:

    1. Read current `.gitignore`. If `.whodis_salt` is already listed, this task is a no-op — confirm and proceed.
    2. If not listed, append a section to `.gitignore`:
       ```
       # Per-installation encryption salt — never commit
       .whodis_salt
       ```
    3. Do NOT delete `.whodis_salt` from the working tree (the running app needs it). Do NOT run `git rm --cached .whodis_salt` here — that step is part of the runbook the operator follows during rotation. We're locking the gate going forward; the runbook covers historical remediation via key rotation.
  </action>
  <verify>
    <automated>grep -q '.whodis_salt' .gitignore</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "\.whodis_salt" .gitignore` returns at least one match
    - Entry is on its own line (not part of a wildcard pattern that may also match unrelated files)
    - `.whodis_salt` (if currently present in working tree) still exists locally — this task does not remove it
  </acceptance_criteria>
  <done>.whodis_salt cannot be re-committed by accident.</done>
</task>

<task type="auto">
  <name>Task 2: scripts/rotate_encryption_key.py — dual-key re-encrypt + verify</name>
  <read_first>
    - scripts/verify_encrypted_config.py (header + DB-connect pattern per PATTERNS.md lines 218–244)
    - scripts/export_config.py (decrypt-loop pattern per PATTERNS.md lines 246–258)
    - app/services/encryption_service.py (constructor accepts passphrase=Optional[str], confirm encrypt/decrypt signatures, line 118 memoryview gotcha)
    - CLAUDE.md "Memory Objects" + "Encryption Key Management" sections
  </read_first>
  <action>
    Per D-02 / D-03 / SEC-02 + PATTERNS.md "scripts/rotate_encryption_key.py":

    1. Create `scripts/rotate_encryption_key.py` starting with the verbatim header pattern from `scripts/verify_encrypted_config.py:1-17`:
       ```python
       #!/usr/bin/env python3
       """Rotate WHODIS_ENCRYPTION_KEY by re-encrypting every Configuration row.

       Reads OLD_WHODIS_ENCRYPTION_KEY and NEW_WHODIS_ENCRYPTION_KEY from the
       environment. Decrypts each row with the old key, re-encrypts with the new
       key, commits the transaction, then verifies every row decrypts cleanly
       with the new key.

       Usage:
           OLD_WHODIS_ENCRYPTION_KEY=... NEW_WHODIS_ENCRYPTION_KEY=... \\
               python scripts/rotate_encryption_key.py [--dry-run]
       """
       import argparse
       import os
       import sys
       import psycopg2
       from pathlib import Path
       from dotenv import load_dotenv

       sys.path.insert(0, str(Path(__file__).parent.parent))
       from app.services.encryption_service import EncryptionService

       load_dotenv()
       ```

    2. argparse setup — `--dry-run` flag (default False per D-03).
    3. Read env vars; refuse to proceed if either is missing:
       ```python
       old_key = os.getenv("OLD_WHODIS_ENCRYPTION_KEY")
       new_key = os.getenv("NEW_WHODIS_ENCRYPTION_KEY")
       if not old_key or not new_key:
           print("ERROR: Both OLD_WHODIS_ENCRYPTION_KEY and NEW_WHODIS_ENCRYPTION_KEY must be set.")
           sys.exit(2)
       if old_key == new_key:
           print("ERROR: OLD and NEW keys are identical — refusing to rotate.")
           sys.exit(2)
       ```
    4. DB connection — copy the verbatim block from PATTERNS.md lines 235–244 (uses `os.getenv("POSTGRES_*")` directly per CLAUDE.md bootstrap-problem note).
    5. Re-encrypt loop — copy and adapt from PATTERNS.md lines 246–258, MUST use `bytes(memoryview)` per CLAUDE.md "Memory Objects":
       ```python
       old_svc = EncryptionService(old_key)
       new_svc = EncryptionService(new_key)
       cursor.execute("SELECT id, category, setting_key, encrypted_value FROM configuration WHERE encrypted_value IS NOT NULL")
       rows = cursor.fetchall()
       updates = []
       for row_id, category, key, encrypted_value in rows:
           plaintext = old_svc.decrypt(bytes(encrypted_value))   # bytes() coerces memoryview
           new_encrypted = new_svc.encrypt(plaintext)
           updates.append((new_encrypted, row_id))
           print(f"  re-encrypted {category}.{key} (id={row_id})")
       print(f"\nPrepared {len(updates)} row(s) for rotation.")
       if args.dry_run:
           print("DRY RUN — no changes committed.")
           sys.exit(0)
       for new_encrypted, row_id in updates:
           cursor.execute("UPDATE configuration SET encrypted_value = %s WHERE id = %s", (new_encrypted, row_id))
       conn.commit()
       print(f"Committed {len(updates)} row(s).")
       ```
       The decrypt/re-encrypt step happens BEFORE any UPDATE so a decrypt failure aborts before mutating anything.
    6. Post-commit verify step (required by D-03):
       ```python
       verify_svc = EncryptionService(new_key)
       cursor.execute("SELECT id, category, setting_key, encrypted_value FROM configuration WHERE encrypted_value IS NOT NULL")
       failures = []
       for row_id, category, key, encrypted_value in cursor.fetchall():
           try:
               verify_svc.decrypt(bytes(encrypted_value))
           except Exception as exc:
               failures.append((row_id, category, key, str(exc)[:120]))
       if failures:
           print("ERROR — post-rotation verify failed for these rows:")
           for f in failures:
               print(" ", f)
           sys.exit(3)
       print(f"VERIFIED: all {len(rows)} row(s) decrypt cleanly with the new key.")
       ```
    7. Wrap mutation in a single transaction — psycopg2 default is per-connection transactional; explicit `conn.commit()` only on success, otherwise `conn.rollback()` in an except handler that re-raises after printing.
    8. Make the script executable and shebang-friendly: `chmod +x` not required on Windows; the shebang is informational.
  </action>
  <verify>
    <automated>test -f scripts/rotate_encryption_key.py &amp;&amp; grep -q 'OLD_WHODIS_ENCRYPTION_KEY' scripts/rotate_encryption_key.py &amp;&amp; grep -q 'NEW_WHODIS_ENCRYPTION_KEY' scripts/rotate_encryption_key.py &amp;&amp; grep -q -- '--dry-run' scripts/rotate_encryption_key.py &amp;&amp; grep -q 'bytes(encrypted_value)' scripts/rotate_encryption_key.py &amp;&amp; grep -q 'VERIFIED' scripts/rotate_encryption_key.py &amp;&amp; python -c 'import ast; ast.parse(open(\"scripts/rotate_encryption_key.py\").read())'</automated>
  </verify>
  <acceptance_criteria>
    - `scripts/rotate_encryption_key.py` exists and parses as valid Python (`python -c "import ast; ast.parse(open(...).read())"`)
    - Script reads `OLD_WHODIS_ENCRYPTION_KEY` AND `NEW_WHODIS_ENCRYPTION_KEY` env vars (both grep matches present)
    - Script accepts `--dry-run` flag (grep matches)
    - Script uses `bytes(encrypted_value)` to coerce memoryview before decrypt (grep matches at least once)
    - Script includes a post-commit verify pass that prints `VERIFIED:` on success (grep matches)
    - Script exits non-zero (specifically: 2 for missing env vars / identical keys, 3 for verify failure)
    - Running with no env vars: `python scripts/rotate_encryption_key.py` prints the missing-env-var error and exits 2
  </acceptance_criteria>
  <done>Operator can dry-run, then commit a key rotation; verify pass guarantees no row was lost.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>The dual-key rotation script with dry-run mode.</what-built>
  <how-to-verify>
    Before approving, the user should:
    1. Take a backup: `python scripts/export_config.py > /tmp/config-backup.json` (existing tool).
    2. Generate a candidate new key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
    3. Run dry-run with the current key as OLD and the candidate as NEW:
       ```
       OLD_WHODIS_ENCRYPTION_KEY=$WHODIS_ENCRYPTION_KEY \
       NEW_WHODIS_ENCRYPTION_KEY=<candidate> \
           python scripts/rotate_encryption_key.py --dry-run
       ```
    4. Confirm the dry-run output enumerates every Configuration row, prints "DRY RUN — no changes committed.", and exits 0.
    5. Confirm with: `python scripts/verify_encrypted_config.py` shows current state still healthy (no commit happened).

    DO NOT run the script for real yet — the runbook (next task) walks through the full rotation procedure including app restart.
  </how-to-verify>
  <resume-signal>Type "approved" if dry-run produced the expected output, or describe any issues for the planner to address.</resume-signal>
</task>

<task type="auto">
  <name>Task 3: docs/runbooks/encryption-key-rotation.md</name>
  <read_first>
    - docs/database.md (markdown style reference per PATTERNS.md "No Analog Found")
    - docs/architecture.md (markdown style reference)
    - .planning/phases/01-foundation/01-CONTEXT.md D-04 (runbook content requirements)
    - PATTERNS.md "No Analog Found" row for runbooks
  </read_first>
  <action>
    Per D-04 / SEC-01 + PATTERNS.md runbook guidance:

    1. Create `docs/runbooks/` directory if it doesn't exist (the path is new).
    2. Create `docs/runbooks/encryption-key-rotation.md` with these sections in this order:
       - `# Encryption Key Rotation Runbook`
       - `## Overview` — when to rotate (suspected leak, scheduled rotation, after personnel change), what gets re-encrypted (every `Configuration` row), what does NOT change (database password in `.env`).
       - `## Pre-flight` — numbered list:
         1. Confirm app health: `curl http://localhost:5000/health` returns 200.
         2. Backup config: `python scripts/export_config.py > /tmp/whodis-config-backup-$(date +%Y%m%d-%H%M).json`. Verify the file is non-empty and human-readable.
         3. Note current key fingerprint: `python -c "import os, hashlib; print(hashlib.sha256(os.getenv('WHODIS_ENCRYPTION_KEY').encode()).hexdigest()[:12])"`.
         4. Schedule a brief (~2 min) maintenance window — app restart is required after rotation.
       - `## Rotation Procedure` — numbered list:
         1. Generate the new key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` — record it in your secret store, NOT in shell history.
         2. (Only if the salt file is suspected leaked per SEC-01) Generate a fresh salt: delete `.whodis_salt` from the working directory; the encryption service will generate a new one on next instantiation. Confirm `.whodis_salt` is gitignored (`git check-ignore .whodis_salt`).
         3. Run dry-run: `OLD_WHODIS_ENCRYPTION_KEY=<current> NEW_WHODIS_ENCRYPTION_KEY=<new> python scripts/rotate_encryption_key.py --dry-run`. Inspect output — every row should print "re-encrypted …".
         4. Run for real: same command without `--dry-run`. Look for `Committed N row(s).` and `VERIFIED: all N row(s) decrypt cleanly with the new key.`
         5. Update the application's environment with the new key: edit `.env` and replace `WHODIS_ENCRYPTION_KEY=...` with the new value.
         6. Restart the application: `python run.py` (or your process manager equivalent). Confirm `/health` returns 200.
         7. Run `python scripts/verify_encrypted_config.py` — every row should decrypt cleanly under the new key.
       - `## Rollback` — numbered list:
         1. If verify failed and the script aborted before commit: nothing to roll back; restore your `.env` to the original key and restart.
         2. If commit succeeded but the app fails to start with the new key: re-set `.env`'s `WHODIS_ENCRYPTION_KEY` back to the OLD key and run the rotation script again with OLD/NEW reversed.
         3. If the database is in a corrupt half-rotated state (should be impossible — script commits all-or-nothing): restore `Configuration` table from your backup using `python scripts/import_config.py /tmp/whodis-config-backup-*.json` (existing tool).
       - `## Notes` — bullets:
         - Keep `WHODIS_ENCRYPTION_KEY` in your secret store (not in version control, not in shell history).
         - The PostgreSQL credentials in `.env` are NOT rotated by this procedure — they are the bootstrap and have a different lifecycle (CLAUDE.md "Environment Variables Bootstrap Problem").
         - This runbook supersedes any ad-hoc key-rotation guidance in older docs.

    3. Use existing markdown style: H1 title, `## Section`, fenced code blocks for shell, ordered numbered lists for procedures.
  </action>
  <verify>
    <automated>test -f docs/runbooks/encryption-key-rotation.md &amp;&amp; grep -q 'Pre-flight' docs/runbooks/encryption-key-rotation.md &amp;&amp; grep -q 'Rotation Procedure' docs/runbooks/encryption-key-rotation.md &amp;&amp; grep -q 'Rollback' docs/runbooks/encryption-key-rotation.md &amp;&amp; grep -q 'export_config.py' docs/runbooks/encryption-key-rotation.md &amp;&amp; grep -q 'rotate_encryption_key.py --dry-run' docs/runbooks/encryption-key-rotation.md</automated>
  </verify>
  <acceptance_criteria>
    - `docs/runbooks/encryption-key-rotation.md` exists
    - File contains the literal headings `## Pre-flight`, `## Rotation Procedure`, `## Rollback`
    - File references `scripts/export_config.py` (backup step)
    - File contains the exact command `rotate_encryption_key.py --dry-run`
    - File contains the rollback procedure (≥3 steps)
    - File contains the verify step using `verify_encrypted_config.py`
  </acceptance_criteria>
  <done>Operator has a single document covering pre-flight, rotation, and rollback for key rotation.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator shell → DB | Rotation script reads/writes every encrypted config row |
| filesystem → process | `.whodis_salt` and env keys live on disk |
| git history → public | Historical commit of `.whodis_salt` is the SEC-01 root cause |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-07-01 | Information Disclosure | `.whodis_salt` in git history | mitigate | Per D-01: rotate the encryption key + salt rather than rewrite history. Once the key changes, the historical salt is useless. `.gitignore` prevents recurrence. |
| T-01-07-02 | Tampering | Half-rotated DB state | mitigate | Script decrypts and re-encrypts ALL rows BEFORE issuing UPDATEs; UPDATEs run inside a single transaction; `conn.commit()` only on success. Post-commit verify confirms every row decrypts under the new key — exits 3 on any failure. |
| T-01-07-03 | Information Disclosure | Keys leaked via shell history | mitigate | Runbook directs operators to use a secret store, not shell history. Variables are exported per-invocation, not persisted in `~/.bash_history`-friendly form. |
| T-01-07-04 | Repudiation | Untracked rotation events | accept | Rotation is an out-of-band operator action; tracking it via app audit log is impractical (the app is stopped/restarted). Rely on operator runbook discipline + the secret store's audit trail. |
| T-01-07-05 | Denial of Service | Failed rotation locks app out | mitigate | Pre-flight requires a config backup via `export_config.py`. Rollback section walks through restoring from the backup with the existing `import_config.py`. |
</threat_model>

<verification>
- `git check-ignore .whodis_salt` exits 0 (file is ignored)
- Dry-run with both env vars enumerates all configuration rows and exits 0
- Dry-run with missing env vars exits 2 with a clear error
- Real run on a test DB completes with `VERIFIED:` line
- Runbook exists at `docs/runbooks/encryption-key-rotation.md` with all four required sections
</verification>

<success_criteria>
SEC-01 + SEC-02 acceptance criteria satisfied: salt file gitignored; CLI tool exists for safe key rotation with dual-key migration and verification; operator runbook documents the procedure.
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-07-SUMMARY.md`.
</output>
