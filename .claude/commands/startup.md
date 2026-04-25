# WHO-DIS STARTUP PROTOCOL

Execute these steps sequentially when starting a new session.

## PHASE 1: GIT SYNC & REMOTE WORK RETRIEVAL

### 1. Check Current State
```bash
git status
```
- If uncommitted changes exist, review and decide: stash, commit, or keep for continuation

### 2. Fetch All Remote Work
```bash
git fetch --all --prune
```

### 3. Pull Latest from Default Branch
```bash
git pull origin main
```

### 4. Review Remote Branches
```bash
git branch -r --sort=-committerdate | head -10
```

**Action Required:**
- If remote branches exist (other than `origin/main` and `origin/HEAD`):
  - List them with last commit dates
  - **ASK USER**: "Found remote branches: [list]. Would you like to review or checkout any of these branches?"
  - If yes: `git checkout -b <local-name> origin/<branch-name>`

### 5. Verify Untracked Files
```bash
git ls-files --others --exclude-standard
```

**Action Required:**
- If untracked files exist:
  - List them for user review
  - **ASK USER**: "Found untracked files: [list]. Should any of these be tracked? (Default: YES unless explicitly ignored)"
  - **Err on side of tracking**: Track files unless user confirms they should be ignored
  - Verify nothing matches the EXCLUSIONS list in `shutdown.md` before tracking

### 6. Check .planning/ Directory (GSD Workflow)
```bash
git ls-files .planning/ | wc -l
find .planning/ -type f ! -path '*/node_modules/*' | wc -l
```

**Action Required:**
- Compare tracked vs total files in `.planning/`
- If mismatch: **ASK USER**: "Track all `.planning/` files? (Default: YES)"
- `.planning/` artifacts (PROJECT.md, ROADMAP.md, STATE.md, phase plans) should always be committed

## PHASE 2: ENVIRONMENT CHECK

1. Verify Python venv is active (prompt shows `venv` or `.venv`)
   - If not: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)

2. Verify dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```

3. Verify `.env` is present and contains required variables:
   - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`
   - `WHODIS_ENCRYPTION_KEY` (Fernet key — DO NOT regenerate without exporting config first)
   - `SECRET_KEY` (Flask)

4. Verify PostgreSQL connectivity and encrypted configuration:
   ```bash
   python scripts/check_config_status.py
   python scripts/verify_encrypted_config.py
   ```
   - If decryption fails: confirm `WHODIS_ENCRYPTION_KEY` matches the key used at install time
   - If `.whodis_salt` is missing: this is the per-installation salt and must be preserved

5. (Optional) Confirm app starts cleanly:
   ```bash
   python run.py
   ```
   - Should bind to `http://localhost:5000` without errors
   - Stop after confirming startup; do not leave running unless actively developing

## PHASE 3: CONTEXT RETRIEVAL

**Primary Context Sources** (in priority order):

1. **`.planning/STATE.md`** — current GSD workflow state, active phase, next action
2. **`.planning/ROADMAP.md`** — phase breakdown for the current milestone
3. **`.planning/PROJECT.md`** — project goals, constraints, milestone context
4. **`AI_HANDOFF.md`** (if present) — transient session-handoff notes
5. **`CLAUDE.md`** — architecture overview, DI container, auth decorators, model patterns
6. **`docs/architecture.md`** — detailed architecture and design patterns
7. **`docs/database.md`** — database setup, encryption, troubleshooting
8. **`CHANGELOG.md`** — recent version history

## PHASE 4: HEALTH CHECK (Quick — counts only, no listing)

1. Database health (no row counts that could be slow):
   ```bash
   python scripts/check_config_status.py
   ```

2. Recent commit:
   ```bash
   git log --oneline -1
   ```

3. Confirm linters available (do not run full lint yet):
   ```bash
   ruff --version && mypy --version
   ```

## PHASE 5: PLAN FORMULATION

1. Determine entry point based on `.planning/STATE.md`:
   - If a phase is active and planned → suggest `/gsd-execute-phase`
   - If a phase needs planning → suggest `/gsd-plan-phase`
   - If a phase is unclear → suggest `/gsd-discuss-phase`
   - If a small ad-hoc fix is needed → suggest `/gsd-quick`
   - If investigating a bug → suggest `/gsd-debug`
2. Present the plan to the user and wait for approval before coding.

## KEY REMINDERS — WHO-DIS SPECIFICS

### GSD Workflow Enforcement
- **Always route file edits through a GSD command.** Direct edits outside GSD are only allowed when the user explicitly bypasses the workflow.
- `.planning/` artifacts must stay in sync with code changes — commit them together.

### Architecture Patterns (see `CLAUDE.md`)
- **Dependency Injection**: retrieve services via `current_app.container.get("service_name")`. Never use module-level globals.
- **Auth decorators**: every protected route requires `@auth_required` and `@require_role("viewer"|"editor"|"admin")`.
- **Models**: extend `BaseModel` and the appropriate mixins (`TimestampMixin`, `UserTrackingMixin`, `ExpirableMixin`, `JSONDataMixin`).
- **Services**: implement the matching interface from `app/interfaces/` and extend the appropriate base service.
- **Frontend**: HTMX fragments + Jinja2 + Tailwind. Return HTML, not JSON, for partial updates.

### Security & Data Safety
- **Never commit** `.env`, `.whodis_salt`, `credentials.json`, `*.key`, `*.pem`
- **Never log** plaintext credentials, tokens, or session cookies
- **Never bypass** auth decorators on routes
- **All write operations** must produce an audit log entry via `audit_service`
- **CSRF**: state-changing routes must accept the double-submit token from `app/middleware/csrf.py`
- **PostgreSQL BYTEA**: wrap memoryview returns with `bytes(...)` before encryption/decryption

### Configuration
- Database creds live in `.env` (bootstrap problem — `config_get` requires DB to work)
- All other config is encrypted in the `configuration` table; access via `config_get("category", "key", "default")`
- After changing `WHODIS_ENCRYPTION_KEY`: run `python scripts/export_config.py` first or data becomes unreadable

### Code Quality
- **Lint**: `ruff check --fix`
- **Type check**: `mypy app/ scripts/`
- **Format**: `ruff format .` (or `black .`)
- **No test framework configured yet** — if adding tests, add `pytest` to `requirements.txt` and document the command here
