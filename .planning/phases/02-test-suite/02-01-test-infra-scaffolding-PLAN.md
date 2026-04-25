---
phase: 02-test-suite
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - requirements.txt
  - requirements-dev.txt
  - pyproject.toml
  - Makefile
  - .githooks/pre-push
  - .gitignore
autonomous: true
requirements: [TEST-01, TEST-04]
tags: [testing, pytest, infra, scaffolding]

must_haves:
  truths:
    - "Developer can run `make test` and pytest is invoked with coverage gating enabled"
    - "Production install (`pip install -r requirements.txt`) does NOT pull pytest, factory-boy, testcontainers, ruff, or mypy"
    - "Pre-push git hook exists at `.githooks/pre-push` that calls `make test` and exits non-zero on failure"
  artifacts:
    - path: "requirements-dev.txt"
      provides: "Dev-only dependencies (pytest, pytest-cov, pytest-mock, factory-boy, testcontainers[postgres], beautifulsoup4, ruff, mypy, types-*)"
      contains: "pytest"
    - path: "pyproject.toml"
      provides: "[tool.pytest.ini_options] + [tool.coverage.run] config per D-11"
      contains: "tool.pytest.ini_options"
    - path: "Makefile"
      provides: "`make test` target wrapping pytest invocation per D-10"
      contains: "test:"
    - path: ".githooks/pre-push"
      provides: "Pre-push gate per D-09"
      contains: "make test"
  key_links:
    - from: "Makefile"
      to: "pyproject.toml"
      via: "pytest reads addopts from [tool.pytest.ini_options]"
      pattern: "cov-fail-under"
    - from: ".githooks/pre-push"
      to: "Makefile"
      via: "shell exec"
      pattern: "make test"
---

<objective>
Bootstrap the test-tooling scaffolding so Plans 02-03 have a working pytest harness to write tests against. Adds the dev/prod requirements split (per code_context "WD-CONT-03 — no dev tools in image"), pytest+coverage config in `pyproject.toml` (per Discretion §1), `Makefile` task runner (D-10), pre-push enforcement hook (D-09), and verifies `.gitignore` covers test artifacts. No application code is modified in this plan.

Purpose: Establish the run-the-suite infrastructure before any test code or fakes are written, so downstream plans only have to focus on test content.
Output: New `requirements-dev.txt`, modified `requirements.txt` (dev tools removed), new `pyproject.toml`, new `Makefile`, new `.githooks/pre-push`, verified `.gitignore`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/02-test-suite/02-CONTEXT.md
@.planning/phases/02-test-suite/02-PATTERNS.md
@requirements.txt
@mypy.ini
@.gitignore

<interfaces>
<!-- Existing dev tooling already in requirements.txt (lines 19-26) — these MOVE to requirements-dev.txt -->
ruff
mypy
types-tabulate
types-flask
types-requests
types-psycopg2
types-pytz
types-cryptography

<!-- Existing mypy.ini configuration (DO NOT migrate; pytest config goes to pyproject.toml only per Discretion §1) -->
[mypy]
python_version = 3.8
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = False
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Split requirements into runtime + dev manifests</name>
  <files>requirements.txt, requirements-dev.txt</files>
  <read_first>
    - requirements.txt (full file — current contents and ordering)
    - .planning/phases/02-test-suite/02-PATTERNS.md (§"requirements-dev.txt" — pinned-version style + exact dep list)
    - .planning/phases/02-test-suite/02-CONTEXT.md (D-01, D-04, D-07, D-09, D-11 — drives dep selection)
  </read_first>
  <action>
    Create `requirements-dev.txt` (new file) at repo root with the following pinned dev dependencies, one per line, in this order:

    ```
    # Test framework + coverage
    pytest>=8,<9
    pytest-cov>=5,<6
    pytest-mock>=3.14,<4

    # Fixtures, factories, ephemeral DB
    factory-boy>=3.3,<4
    testcontainers[postgres]>=4,<5

    # HTML response assertions (Discretion §4 — used in integration tests)
    beautifulsoup4>=4.12,<5

    # Linting + type-checking (moved from requirements.txt — dev-only per WD-CONT-03)
    ruff
    mypy
    types-tabulate
    types-flask
    types-requests
    types-psycopg2
    types-pytz
    types-cryptography
    ```

    Then edit `requirements.txt` and DELETE the following lines (they live in dev-only now):
    - `ruff`
    - `mypy`
    - `types-tabulate`
    - `types-flask`
    - `types-requests`
    - `types-psycopg2`
    - `types-pytz`
    - `types-cryptography`
    - The blank separator line above `ruff` (lines 18-26 in current file)

    DO NOT touch any runtime line (Flask, SQLAlchemy, ldap3, msal, etc.). DO NOT add new runtime deps. The runtime file should end after the last runtime dependency (`Flask-Limiter>=3.5,<4`).

    Reasoning: Phase 3 (containerization) per code_context will install only `requirements.txt` into the production image; pytest/factory-boy/testcontainers must be excluded.
  </action>
  <verify>
    <automated>grep -E "^(pytest|factory-boy|testcontainers|beautifulsoup4|ruff|mypy|types-)" requirements.txt; test $? -eq 1 &amp;&amp; grep -E "^pytest>=8,&lt;9$" requirements-dev.txt &amp;&amp; grep -E "^testcontainers\[postgres\]>=4,&lt;5$" requirements-dev.txt &amp;&amp; grep -E "^factory-boy>=3.3,&lt;4$" requirements-dev.txt &amp;&amp; grep -E "^ruff$" requirements-dev.txt &amp;&amp; grep -E "^mypy$" requirements-dev.txt</automated>
  </verify>
  <acceptance_criteria>
    - File `requirements-dev.txt` exists at repo root.
    - `grep -c "^pytest>=8,<9$" requirements-dev.txt` returns 1.
    - `grep -c "^testcontainers\[postgres\]>=4,<5$" requirements-dev.txt` returns 1.
    - `grep -c "^factory-boy>=3.3,<4$" requirements-dev.txt` returns 1.
    - `grep -c "^pytest-cov>=5,<6$" requirements-dev.txt` returns 1.
    - `grep -c "^pytest-mock>=3.14,<4$" requirements-dev.txt` returns 1.
    - `grep -c "^beautifulsoup4>=4.12,<5$" requirements-dev.txt` returns 1.
    - `grep -c "^ruff$" requirements-dev.txt` returns 1; `grep -c "^mypy$" requirements-dev.txt` returns 1.
    - All 6 `types-*` lines present in `requirements-dev.txt`.
    - `grep -cE "^(ruff|mypy|types-)" requirements.txt` returns 0 (no dev deps left in runtime file).
    - `grep -cE "^Flask==3.1.3$" requirements.txt` returns 1 (runtime untouched).
    - `grep -cE "^Flask-Limiter>=3.5,<4$" requirements.txt` returns 1 (runtime untouched).
  </acceptance_criteria>
  <done>requirements split clean; runtime file holds only runtime deps; all dev tools (test + lint) live in requirements-dev.txt with versions per spec.</done>
</task>

<task type="auto">
  <name>Task 2: Create pyproject.toml with pytest + coverage config</name>
  <files>pyproject.toml</files>
  <read_first>
    - mypy.ini (current tool-config style in repo)
    - .planning/phases/02-test-suite/02-PATTERNS.md (§"pyproject.toml" — exact section layout)
    - .planning/phases/02-test-suite/02-CONTEXT.md (D-11 — coverage scope `app/services/` + `app/middleware/` only; D-09 — `--cov-fail-under=60`; "Claude's Discretion" — pyproject.toml location, `unit`/`integration` markers)
  </read_first>
  <action>
    Create `pyproject.toml` (new file) at repo root with EXACTLY these sections:

    ```toml
    [tool.pytest.ini_options]
    testpaths = ["tests"]
    addopts = "--cov=app.services --cov=app.middleware --cov-fail-under=60 --cov-report=term-missing --cov-report=html --strict-markers"
    markers = [
      "unit: fast unit tests with mocked dependencies",
      "integration: tests exercising the Flask app end-to-end against fakes",
    ]
    filterwarnings = [
      "ignore::DeprecationWarning:pkg_resources.*",
    ]

    [tool.coverage.run]
    source = ["app/services", "app/middleware"]
    branch = true
    omit = [
      "app/services/__init__.py",
      "app/middleware/__init__.py",
    ]

    [tool.coverage.report]
    show_missing = true
    skip_covered = false
    precision = 1
    ```

    DO NOT add `[tool.mypy]` — mypy stays in `mypy.ini` per CONTEXT Discretion ("mypy can stay in mypy.ini; Discretion didn't mandate move").
    DO NOT add `[build-system]` or `[project]` tables — Flask app is not a packaged distribution.
    DO NOT change the coverage scope. Per D-11 the gate is `app/services/` + `app/middleware/` ONLY; `app/blueprints/`, `app/models/`, `app/utils/` are deliberately excluded from `--cov-fail-under` enforcement (they'll appear in HTML if invoked indirectly).

    The `--strict-markers` flag prevents typos in `@pytest.mark.unit` / `@pytest.mark.integration` from silently passing as no-op markers.
  </action>
  <verify>
    <automated>grep -c "^\[tool.pytest.ini_options\]$" pyproject.toml &amp;&amp; grep -c "^\[tool.coverage.run\]$" pyproject.toml &amp;&amp; grep -c "cov-fail-under=60" pyproject.toml &amp;&amp; grep -c "app.services" pyproject.toml &amp;&amp; grep -c "app.middleware" pyproject.toml &amp;&amp; grep -c "strict-markers" pyproject.toml</automated>
  </verify>
  <acceptance_criteria>
    - `pyproject.toml` exists at repo root.
    - Contains `[tool.pytest.ini_options]` table.
    - `addopts` line contains all of: `--cov=app.services`, `--cov=app.middleware`, `--cov-fail-under=60`, `--cov-report=term-missing`, `--cov-report=html`, `--strict-markers`.
    - `markers` array contains both `unit:` and `integration:` entries.
    - `[tool.coverage.run]` table has `source = ["app/services", "app/middleware"]` and `branch = true`.
    - File contains NO `[tool.mypy]` table (mypy stays in mypy.ini per Discretion).
    - File contains NO `[build-system]` or `[project]` tables.
  </acceptance_criteria>
  <done>pytest reads config from pyproject.toml; running `pytest --collect-only` (after Plan 02 creates `tests/`) will pick up the testpaths and apply coverage gate.</done>
</task>

<task type="auto">
  <name>Task 3: Create Makefile, pre-push hook, and verify .gitignore</name>
  <files>Makefile, .githooks/pre-push, .gitignore</files>
  <read_first>
    - .gitignore (verify htmlcov/, .coverage, .coverage.*, .pytest_cache/ already present per PATTERNS.md §".gitignore (MODIFIED)")
    - .planning/phases/02-test-suite/02-PATTERNS.md (§"Makefile", §".githooks/pre-push" — exact bodies)
    - .planning/phases/02-test-suite/02-CONTEXT.md (D-09, D-10)
  </read_first>
  <action>
    1. Create `Makefile` (new file) at repo root with EXACTLY these contents (TAB-indented bodies, not spaces — make is whitespace-sensitive):

    ```makefile
    .PHONY: test test-unit test-integration test-cov-html lint typecheck

    # D-10: single source of truth for the test command. Pre-push hook calls this.
    # The pytest config lives in pyproject.toml; addopts there enforces --cov-fail-under=60.
    test:
    	pytest -x

    test-unit:
    	pytest -x -m unit

    test-integration:
    	pytest -x -m integration

    test-cov-html:
    	pytest --cov-report=html
    	@echo "HTML coverage report at htmlcov/index.html"

    lint:
    	ruff check --fix
    	ruff format

    typecheck:
    	mypy app/ scripts/
    ```

    Use literal TAB characters (0x09) for the recipe lines, not spaces. The `-x` flag stops at the first failure (matches D-09 hook behavior).

    2. Create `.githooks/` directory and `.githooks/pre-push` (new file) with EXACTLY:

    ```bash
    #!/usr/bin/env bash
    # D-09: pre-push gate. Blocks `git push` when tests fail or coverage drops below 60%.
    # Bypass with `git push --no-verify` (explicit emergency escape only).
    # Install once per clone: git config core.hooksPath .githooks
    set -euo pipefail
    echo "[pre-push] running test suite..."
    make test
    ```

    Set executable bit: `chmod +x .githooks/pre-push` (on Windows the file mode bit is preserved by git when committed via `git update-index --chmod=+x .githooks/pre-push`).

    3. Verify `.gitignore` already contains `htmlcov/`, `.coverage`, `.coverage.*`, and `.pytest_cache/` per PATTERNS.md. If any are missing, append them under a new section header `# Test artifacts (Phase 2)`. Do NOT add `.benchmarks/` or other unrelated entries — only what's actually produced by this phase's tooling.
  </action>
  <verify>
    <automated>test -f Makefile &amp;&amp; grep -E "^test:" Makefile &amp;&amp; grep "pytest -x" Makefile &amp;&amp; test -f .githooks/pre-push &amp;&amp; grep "make test" .githooks/pre-push &amp;&amp; grep -E "^htmlcov/$|^htmlcov$" .gitignore &amp;&amp; grep -E "^\.coverage$" .gitignore &amp;&amp; grep -E "^\.pytest_cache/$|^\.pytest_cache$" .gitignore</automated>
  </verify>
  <acceptance_criteria>
    - `Makefile` exists at repo root.
    - `grep -c "^test:" Makefile` returns 1.
    - `grep -c "^.PHONY: test" Makefile` returns 1.
    - Recipe under `test:` calls `pytest -x` (no extra flags — addopts in pyproject.toml supplies coverage args).
    - `.githooks/pre-push` exists.
    - `grep -c "make test" .githooks/pre-push` returns 1.
    - `.githooks/pre-push` first line is `#!/usr/bin/env bash`.
    - `.gitignore` contains `htmlcov/`, `.coverage`, `.coverage.*`, `.pytest_cache/` (one per line, case-sensitive match).
    - On a Unix-like shell: `test -x .githooks/pre-push` returns 0 (executable bit set). On Windows, file exists and `git ls-files --stage .githooks/pre-push` shows mode `100755`.
  </acceptance_criteria>
  <done>Makefile and pre-push hook exist with correct contents; .gitignore covers test artifacts; the hook is wired (caller still needs `git config core.hooksPath .githooks` — that's documented in Plan 04 README update, not enforced here).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| developer-machine → repo | Pre-push hook runs locally; bypass via `--no-verify` is intentional |
| runtime container → PyPI (Phase 3) | Production image must NOT install dev deps (factory-boy can `.create()` unrestricted DB rows) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01 | E (Elevation of Privilege) | requirements-dev.txt deps shipped to prod | mitigate | Strict split: requirements.txt holds runtime only; Phase 3 Dockerfile installs `-r requirements.txt` only. Verified by Task 1 acceptance criteria (no `pytest`/`factory-boy`/`testcontainers` in runtime file). |
| T-02-02 | T (Tampering) | Pre-push hook bypass via `--no-verify` | accept | Solo-dev project, intentional emergency escape per D-09. Documented in hook comment. |
| T-02-03 | I (Information Disclosure) | Coverage HTML report committed to git | mitigate | `.gitignore` enforces `htmlcov/` exclusion (verified Task 3). |
</threat_model>

<verification>
- `pip install -r requirements-dev.txt` succeeds (does NOT run as part of automated CI yet — Plan 04 verifies end-to-end on a fresh checkout)
- `pytest --collect-only` does NOT error on missing config (will report "no tests collected" until Plan 03 adds tests; that's fine for this plan)
- Runtime requirements.txt unchanged in semantics — `pip install -r requirements.txt` still installs Flask 3.1.3 + all production deps with no test tooling
</verification>

<success_criteria>
- All Task 1-3 acceptance criteria pass
- requirements-dev.txt installable on Python 3.8+ (pytest 8 supports 3.8)
- pyproject.toml is valid TOML (parseable by Python's `tomllib`/`tomli`)
- Makefile parses without GNU make errors (`make -n test` prints the command without executing)
- pre-push hook is bash-syntactically valid (`bash -n .githooks/pre-push` exits 0)
</success_criteria>

<output>
After completion, create `.planning/phases/02-test-suite/02-01-SUMMARY.md` documenting:
- Exact dep versions added to requirements-dev.txt
- Confirmation that runtime requirements.txt no longer carries ruff/mypy/types-*
- pyproject.toml sections created
- Makefile targets exposed
- pre-push hook installation note (`git config core.hooksPath .githooks` — documented for Plan 04 to surface in README)
</output>
