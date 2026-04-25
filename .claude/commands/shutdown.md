# WHO-DIS SHUTDOWN PROTOCOL

Execute these steps sequentially before ending a session.

## PHASE 1: CODE HYGIENE & VALIDATION

### 1. Remove Debug Artifacts
- Search modified files for ad-hoc `print()` statements added this session
- Remove `# DEBUG`, `# TODO: remove`, or temporary scratch comments
- **Keep** established logging via `logger.info()` / `logger.debug()` / `logger.error(..., exc_info=True)`

### 2. Project-Specific Security Checks
**CRITICAL for Who-Dis:**

- ✅ No credentials in code (`.env`, encryption keys, API secrets, connection strings)
- ✅ No new routes missing `@auth_required` and `@require_role(...)` decorators
- ✅ No state-changing routes missing CSRF token validation
- ✅ All new write operations emit an audit log via `audit_service`
- ✅ No raw user input concatenated into LDAP filters or SQL strings (use parameterized queries / ldap3 escaping)
- ✅ No PII or session tokens written to logs in plaintext
- ✅ Memoryview/buffer returns from PostgreSQL BYTEA wrapped with `bytes(...)` before crypto
- ✅ No new configuration values hardcoded (use `config_get(...)` with encryption)

### 3. Run Linters and Type Checks
```bash
ruff check --fix
ruff format .
mypy app/ scripts/
```

All three must pass before commit. If `mypy` flags issues in third-party stubs, confirm `mypy.ini` already excludes that library before silencing.

### 4. Smoke-Test the App (if app code changed)
```bash
python run.py
```
- Confirm the app boots without errors and `/` responds
- Confirm any changed routes load (auth handled by Azure AD headers in production; locally use the configured dev bypass if applicable)
- Stop the server before continuing

### 5. Verify Configuration Health (if config code or migrations changed)
```bash
python scripts/check_config_status.py
python scripts/verify_encrypted_config.py
python scripts/diagnose_config.py
```

## PHASE 2: UPDATE GSD STATE & HANDOFF

### 1. Update `.planning/STATE.md`
- Reflect current phase status (active phase, completed plans, next action)
- Update any phase-level notes if a plan was completed or deviated from
- If a phase finished: confirm `.planning/ROADMAP.md` checkbox is updated

### 2. Update `AI_HANDOFF.md` (if present, optional but recommended)
**CRITICAL**: Clear previous content. Keep under 50 lines. Transient state only.

```markdown
## Current State
- Date: [Today's date]
- Status: [In Progress / Blocked / Complete]
- Active Phase: [phase number/name from .planning/]
- Last Action: [Brief description]

## Session Summary
- Accomplishments: [Bulleted list]
- Key Files Modified: [List paths]
- GSD Artifacts Updated: [PLAN.md, STATE.md, ROADMAP.md, etc.]

## Next Tasks
1. [Specific task with WHY context]
2. [Next priority item]

## Known Issues
- [Any blockers or bugs discovered]
```

## PHASE 3: FILE TRACKING & GIT COMMIT

### 1. Review ALL Untracked Files
```bash
git ls-files --others --exclude-standard
```

**Action Required:**
- List each untracked file with its purpose
- **ASK USER**: "Found untracked files: [list]. Which should be tracked and committed?"
- **Default: TRACK** unless the file matches an EXCLUSION below

**Who-Dis EXCLUSIONS** (never track):
- ❌ Environment / secrets: `.env`, `.env.local`, `.whodis_salt`, `credentials.json`, `*.key`, `*.pem`
- ❌ Exported configuration backups (may contain decrypted secrets): `config_export*.json`, `config_backup*.json`
- ❌ Python cache: `__pycache__/`, `*.pyc`, `*.pyo`
- ❌ Virtual environments: `venv/`, `.venv/`, `env/`
- ❌ IDE files: `.vscode/`, `.idea/` (unless shared workspace config)
- ❌ Logs / temp output: `*.log`, `logs/`, `tmp/`
- ❌ Local SQLite fallbacks: `*.db`, `*.sqlite`, `*.sqlite3` (PostgreSQL is the source of truth)
- ❌ Ad-hoc scratch files: `test_*.py`, `debug_*.py`, `check_*.py`, `scratch_*.py` at repo root
- ❌ OS detritus: `.DS_Store`, `Thumbs.db`, `NUL`

**Files to ALWAYS TRACK** (when modified):
- ✅ `.planning/` artifacts (PROJECT, ROADMAP, STATE, phase PLAN/REVIEW/VERIFICATION docs)
- ✅ `app/` Python source (blueprints, services, models, middleware, interfaces, utils)
- ✅ `scripts/` (admin / migration / diagnostic scripts)
- ✅ `database/*.sql` (schema, analyze, migration scripts)
- ✅ `app/templates/`, `app/static/` (Jinja2, Tailwind, JS)
- ✅ Documentation: `*.md`, `docs/**/*`
- ✅ Configuration: `requirements.txt`, `mypy.ini`, `pyproject.toml`, `.env.template` / `.env.example`

### 2. Stage Files for Commit
```bash
git add <specific files>
git status
```
Prefer staging by name over `git add .` to avoid sweeping in stray files.

**Final Verification:**
- Review staged file list — no `.env`, `.whodis_salt`, exported config dumps, or large binaries
- Confirm `.planning/` and code changes commit together when they relate to the same phase

### 3. Create Commit with Conventional Message
Follow the existing repo style (recent commits use lowercase `type: description` and a scope when useful):

```bash
git commit -m "$(cat <<'EOF'
type(scope): short description

Optional body explaining the WHY, not the WHAT.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

**Conventional Commit Types**:
- `feat:` — new feature (search source, admin page, API endpoint, blueprint route)
- `fix:` — bug fix (auth, config decryption, search merge, cache TTL)
- `docs:` — README, CLAUDE.md, docs/, .planning/ artifacts
- `refactor:` — restructure without behavior change (DI wiring, model split, mixin extraction)
- `perf:` — performance (query optimization, N+1 fixes, caching)
- `test:` — tests (once a test framework is added)
- `chore:` — deps, mypy.ini, ruff config, scripts, tooling
- `security:` — auth/CSRF/encryption fixes, audit log additions

**Useful scopes**: `auth`, `search`, `admin`, `config`, `ldap`, `genesys`, `graph`, `db`, `models`, `services`, `middleware`, `templates`, `planning`

**Examples** (matching this repo's style):
```
feat(search): add Genesys queue membership to merged result
fix(config): handle memoryview wrapping when decrypting BYTEA values
docs: update CLAUDE.md with GSD project context
refactor(services): extract BaseAPITokenService for Genesys/Graph
chore: bump cryptography to 46.0.7
```

### 4. Review and Push Branches

#### A. Check Local Branches
```bash
git branch -vv
```
Identify branches that are ahead of origin or have no remote tracking branch.

#### B. Push Current Branch
```bash
git push origin HEAD
```

> **Note:** No pre-push hooks are configured in this repo today. If hooks get added later (pytest, ruff, mypy), document the trigger here and never bypass with `--no-verify` unless the user explicitly approves.

#### C. Handle Other Local Branches
For each unpushed local branch:
- **ASK USER**: "Local branch '[branch-name]' has unpushed commits. Push to remote? (Default: YES)"
- If YES: `git push origin [branch-name]`
- If NO and clearly temporary: consider `git branch -d [branch-name]` (only with explicit user confirmation)
- **Err on side of pushing** — preserve work unless user confirms it's disposable

#### D. Verify All Work is Remote
```bash
git log --branches --not --remotes --oneline
git branch -vv | grep -E "ahead|behind" || echo "All branches in sync"
```

If unpushed commits remain: **STOP and ASK USER** before ending the session.

## PHASE 4: FINAL CONFIRMATION & PROJECT HEALTH

### 1. Confirm Push Success
- ✅ `git push` succeeded with no errors
- ✅ No untracked files except known exclusions
- ✅ No uncommitted changes
- ✅ No unpushed commits on any branch

### 2. Verify Complete Remote Sync
```bash
git ls-files --others --exclude-standard
git status --short
git log --branches --not --remotes --oneline
```
All three should be empty (or only show items in the EXCLUSIONS list).

### 3. Verify GSD State is Coherent
- ✅ `.planning/STATE.md` reflects current phase status
- ✅ `.planning/ROADMAP.md` checkboxes match reality
- ✅ Any active phase has its `PLAN.md` (and, when applicable, `VERIFICATION.md` / `REVIEW.md`) committed
- ✅ `AI_HANDOFF.md` (if used) is under 50 lines and contains actionable Next Tasks with WHY context

### 4. Project Health Summary
Provide a one-sentence summary:

**Template:**
```
✅ Who-Dis Health: <phase> | Lint: <status> | Types: <status> | DB Config: <status> | Branch: <name> @ <short-sha>
```

**Example:**
```
✅ Who-Dis Health: Milestone v3 / Phase 2 in progress | Lint: clean | Types: clean | DB Config: encrypted OK | Branch: main @ 354fa06
```

**Status Options:**
- **Phase**: pulled from `.planning/STATE.md`
- **Lint**: `clean` / `warnings` / `errors`
- **Types**: `clean` / `warnings` / `errors`
- **DB Config**: `encrypted OK` / `decryption error` / `not checked`
