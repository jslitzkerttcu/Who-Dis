#!/usr/bin/env python3
"""Rotate WHODIS_ENCRYPTION_KEY by re-encrypting every Configuration row.

Reads OLD_WHODIS_ENCRYPTION_KEY and NEW_WHODIS_ENCRYPTION_KEY from the
environment. Decrypts each row with the old key, re-encrypts with the new
key, commits the transaction, then verifies every row decrypts cleanly
with the new key.

Usage:
    OLD_WHODIS_ENCRYPTION_KEY=... NEW_WHODIS_ENCRYPTION_KEY=... \\
        python scripts/rotate_encryption_key.py [--dry-run]

Exit codes:
    0  success (or dry-run completed)
    2  missing/invalid env vars (OLD/NEW unset, or identical)
    3  post-commit verify failed (some row will not decrypt under the new key)
    1  any other unexpected error (DB connection failure, decrypt error, etc.)
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rotate WHODIS_ENCRYPTION_KEY by re-encrypting Configuration rows."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Decrypt + re-encrypt every row in memory but do not UPDATE the database.",
    )
    args = parser.parse_args()

    # 1. Validate env vars
    old_key = os.getenv("OLD_WHODIS_ENCRYPTION_KEY")
    new_key = os.getenv("NEW_WHODIS_ENCRYPTION_KEY")
    if not old_key or not new_key:
        print(
            "ERROR: Both OLD_WHODIS_ENCRYPTION_KEY and NEW_WHODIS_ENCRYPTION_KEY "
            "must be set in the environment."
        )
        return 2
    if old_key == new_key:
        print("ERROR: OLD and NEW keys are identical — refusing to rotate.")
        return 2

    # 2. DB connection — use os.getenv() per CLAUDE.md bootstrap-problem note
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "whodis_db"),
            user=os.getenv("POSTGRES_USER", "whodis_user"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
        )
    except Exception as exc:
        print(f"ERROR: Database connection failed: {exc}")
        return 1

    cursor = conn.cursor()

    try:
        # 3. Build dual encryption services
        old_svc = EncryptionService(old_key)
        new_svc = EncryptionService(new_key)

        # 4. Read every encrypted row
        cursor.execute(
            "SELECT id, category, setting_key, encrypted_value "
            "FROM configuration WHERE encrypted_value IS NOT NULL"
        )
        rows = cursor.fetchall()
        if not rows:
            print("No encrypted Configuration rows found — nothing to rotate.")
            conn.close()
            return 0

        # 5. Decrypt + re-encrypt fully BEFORE any UPDATE — all-or-nothing
        updates = []
        for row_id, category, key, encrypted_value in rows:
            # bytes() coerces memoryview from PG BYTEA per CLAUDE.md "Memory Objects"
            plaintext = old_svc.decrypt(bytes(encrypted_value))
            new_encrypted = new_svc.encrypt(plaintext)
            updates.append((new_encrypted, row_id))
            print(f"  re-encrypted {category}.{key} (id={row_id})")

        print(f"\nPrepared {len(updates)} row(s) for rotation.")

        if args.dry_run:
            print("DRY RUN — no changes committed.")
            conn.close()
            return 0

        # 6. Single-transaction UPDATE pass
        for new_encrypted, row_id in updates:
            cursor.execute(
                "UPDATE configuration SET encrypted_value = %s WHERE id = %s",
                (new_encrypted, row_id),
            )
        conn.commit()
        print(f"Committed {len(updates)} row(s).")

        # 7. Post-commit verify — required by D-03
        verify_svc = EncryptionService(new_key)
        cursor.execute(
            "SELECT id, category, setting_key, encrypted_value "
            "FROM configuration WHERE encrypted_value IS NOT NULL"
        )
        failures = []
        verify_rows = cursor.fetchall()
        for row_id, category, key, encrypted_value in verify_rows:
            try:
                verify_svc.decrypt(bytes(encrypted_value))
            except Exception as exc:
                failures.append((row_id, category, key, str(exc)[:120]))

        if failures:
            print("ERROR — post-rotation verify failed for these rows:")
            for f in failures:
                print(" ", f)
            conn.close()
            return 3

        print(
            f"VERIFIED: all {len(verify_rows)} row(s) decrypt cleanly with the new key."
        )
        conn.close()
        return 0

    except Exception as exc:
        # Anything thrown before commit() leaves the DB untouched (psycopg2 default).
        # We still rollback() defensively in case partial UPDATEs ran.
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"ERROR: rotation aborted — {exc}")
        try:
            conn.close()
        except Exception:
            pass
        # Re-raise nothing; surface as exit 1
        return 1


if __name__ == "__main__":
    sys.exit(main())
