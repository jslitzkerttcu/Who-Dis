# Phase 9 — `@require_role("editor")` remap audit

Auto-mode decision: editor → admin (more restrictive). Surface to Plan 06 UAT for confirmation.

| File:Line | Before | After | Notes |
|-----------|--------|-------|-------|
| app/blueprints/search/__init__.py:728 | `@require_role("editor")` on `remove_genesys_license` | `@require_role("admin")` | Genesys license removal is an elevated operation; admin is appropriate |
| app/blueprints/utilities/blocked_numbers.py:50 | `@require_role("editor")` on `add_blocked_number` | `@require_role("admin")` | Writing to Genesys blocked-numbers list; admin-only post-D-05 |
| app/blueprints/utilities/blocked_numbers.py:118 | `@require_role("editor")` on `update_blocked_number` | `@require_role("admin")` | Updating Genesys blocked-numbers entry; admin-only post-D-05 |
| app/blueprints/utilities/blocked_numbers.py:187 | `@require_role("editor")` on `delete_blocked_number` | `@require_role("admin")` | Deleting from Genesys blocked-numbers list; admin-only post-D-05 |
| app/blueprints/search/__init__.py:720,754,2161,2185,2211 | `g.role in ("editor", "admin")` / `g.role in ["editor", "admin"]` UI can_edit guards | `g.role in ("admin",)` / `g.role in ["admin"]` | Informational UI guards for note/license edit buttons; now admin-only |
| app/blueprints/admin/users.py:423 | `roles = ["viewer", "editor", "admin"]` in edit modal dropdown | `roles = ["viewer", "admin"]` | Removes editor from new-user role choices in admin UI |
| app/blueprints/admin/users.py:565 | `role_colors = {"admin": "purple", "editor": "blue", "viewer": "gray"}` | `editor` key removed | Role badge color dict — no editor badge needed |
| app/blueprints/admin/users.py:591 | `"editor": "fas fa-edit text-blue-500"` in role_icons | Line commented out | No editor icon needed; existing DB rows with role=editor will fall back to default icon |
| app/blueprints/session/__init__.py:324,376 | `g.role not in ["viewer", "editor", "admin"]` | `g.role not in ["viewer", "admin"]` | Session extend/logout permission guards updated to two-tier list |
| app/models/user.py:17 | `ROLE_EDITOR = "editor"` (constant definition) | Kept; added `# DEPRECATED` comment | Legacy DB rows still hold value; constant retained to avoid breaking reads |
| app/models/user.py:138 | `ROLE_EDITOR: 2` in `has_permission` local hierarchy | `ROLE_EDITOR: 1` (mapped to viewer level) | Legacy DB rows with role=editor treated as viewer until migrated by cutover script |

## Open questions for UAT

- **Blocked numbers write access:** The three blocked-numbers mutation endpoints (add/update/delete) were formerly editor-accessible. Under the new two-tier model they require admin. Confirm during Plan 06 UAT whether any non-admin staff need write access to the blocked-numbers list — if so, this is the primary candidate for `editor → viewer` relaxation.
- **Note authoring:** `can_edit` guards for search notes are now admin-only. Confirm whether viewers should be allowed to add/edit notes (which would mean `can_edit = g.role in ["viewer", "admin"]`). The conservative default (admin only) is UAT-verifiable.
- **Genesys license removal:** Was previously editor-accessible. Confirm admin-only is appropriate for license operations.

## Scan commands used

```bash
# Pass 1: grep
grep -rn -E "require_role\(\s*['\"]editor['\"]\s*\)|ROLE_EDITOR\b|role\s*[=!]=\s*['\"]editor['\"]" app/ --include='*.py' \
  | grep -v -E "app/middleware/(role_resolver|auth)\.py"

# Pass 2: AST scanner (authoritative)
python scripts/cutover/_scan_editor_callsites.py
```

Post-remap scan confirms zero `require_role("editor")` decorator calls remain in non-excluded files.
The one remaining AST hit (`app/models/user.py:143 ROLE_EDITOR attribute`) is in the `has_permission` compatibility block — intentional, documented with DEPRECATED comment.
