---
phase: 02-test-suite
plan: 04
type: execute
wave: 4
depends_on: [02-03-targeted-and-integration-tests]
files_modified:
  - README.md
  - .planning/phases/02-test-suite/02-VERIFICATION.md
autonomous: false
requirements: [TEST-04]
tags: [testing, coverage, docs, verification]

must_haves:
  truths:
    - "Running `pytest tests/ -v` from a fresh `pip install -r requirements.txt -r requirements-dev.txt` produces a passing run with coverage ≥60% on `app/services/` + `app/middleware/`"
    - "Running `make test` produces the same result as `pytest tests/ -v`"
    - "Running `git push` on a branch with a deliberately broken test is BLOCKED (pre-push hook returns non-zero)"
    - "README.md documents the one-line installer for the pre-push hook (`git config core.hooksPath .githooks`) and the `make test` target"
    - "VERIFICATION.md records the actual coverage percentage achieved on services and middleware (per-file table)"
  artifacts:
    - path: "README.md"
      provides: "Developer-facing test/coverage/hook setup docs"
      contains: "core.hooksPath .githooks"
    - path: ".planning/phases/02-test-suite/02-VERIFICATION.md"
      provides: "End-to-end Phase 2 acceptance verification report"
      contains: "Coverage achieved"
  key_links:
    - from: "README.md §Testing"
      to: ".githooks/pre-push"
      via: "`git config core.hooksPath .githooks` installer"
      pattern: "core.hooksPath"
    - from: "VERIFICATION.md"
      to: "pyproject.toml --cov-fail-under=60"
      via: "Asserted gate value"
      pattern: "60"
---

<objective>
Final wave: end-to-end verification of the Phase 2 deliverable + developer-facing docs. Run the full suite from a clean state, capture the actual coverage numbers, deliberately break a test to prove the pre-push hook gate fires, and document the one-line hook installer in the README.

Purpose: Without this plan, the suite "exists" but isn't proven to work for a developer pulling the repo for the first time. This plan closes that gap.
Output: README updates, VERIFICATION.md report, human checkpoint confirming the gate behavior is acceptable.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/phases/02-test-suite/02-CONTEXT.md
@.planning/phases/02-test-suite/02-01-SUMMARY.md
@.planning/phases/02-test-suite/02-02-SUMMARY.md
@.planning/phases/02-test-suite/02-03-SUMMARY.md
@README.md
@requirements-dev.txt
@pyproject.toml
@Makefile
@.githooks/pre-push
</context>

<tasks>

<task type="auto">
  <name>Task 1: Run full suite + capture coverage report</name>
  <files>.planning/phases/02-test-suite/02-VERIFICATION.md</files>
  <read_first>
    - .planning/phases/02-test-suite/02-01-SUMMARY.md
    - .planning/phases/02-test-suite/02-02-SUMMARY.md
    - .planning/phases/02-test-suite/02-03-SUMMARY.md
    - pyproject.toml
    - Makefile
  </read_first>
  <action>
    1. Verify a clean dev install works:
       ```
       pip install -r requirements.txt -r requirements-dev.txt
       ```
       Capture any install warnings or errors. If `testcontainers[postgres]` requires Docker daemon — verify Docker is running before proceeding.

    2. Run the full suite with coverage:
       ```
       pytest tests/ -v
       ```
       Capture the full output. Note:
       - Total tests collected
       - Total passed / failed / skipped
       - Coverage line for `app/services/` and `app/middleware/`
       - Whether `--cov-fail-under=60` gate passed

    3. Run via the Makefile entrypoint (proves D-10):
       ```
       make test
       ```
       Should produce equivalent result.

    4. Run with HTML coverage report and inspect `htmlcov/index.html` exists:
       ```
       make test-cov-html
       ls htmlcov/index.html
       ```

    5. Generate a per-file coverage table for the documented hot paths:
       ```
       pytest --cov=app.services --cov=app.middleware --cov-report=term-missing 2>&1 | grep -E "^app/(services|middleware)/" | sort
       ```

    6. Create `.planning/phases/02-test-suite/02-VERIFICATION.md` with this template:

       ```markdown
       # Phase 2 Verification Report

       **Run date:** YYYY-MM-DD
       **Run command:** `pytest tests/ -v`

       ## Suite Result

       - Tests collected: <N>
       - Passed: <N>
       - Failed: <N>
       - Skipped: <N>
       - Wall time: <Xs>

       ## Coverage Summary

       | Package | Statements | Missed | Coverage |
       |---------|-----------|--------|----------|
       | app/services | <N> | <N> | <X.X%> |
       | app/middleware | <N> | <N> | <X.X%> |
       | **Combined gate** | <N> | <N> | **<X.X%>** |

       Gate: `--cov-fail-under=60` — **PASS / FAIL**

       ## Per-File Coverage (services + middleware)

       <paste output of the `grep` command from step 5>

       ## D-12 Hot-Path File Coverage

       | File | Lines | Coverage | Notes |
       |------|-------|----------|-------|
       | app/services/search_orchestrator.py | 332 | <X%> | Targeted in Plan 03 |
       | app/services/ldap_service.py | 652 | <X%> | Targeted in Plan 03 |
       | app/services/genesys_service.py | 668 | <X%> | Targeted in Plan 03 |

       ## ROADMAP §Phase 2 Success Criteria — Verification

       1. ✅/❌ `pytest tests/ -v` runs to completion without real LDAP, Graph, or Genesys calls
          - Evidence: <how verified — fakes/mocks at boundary, no network requests>
       2. ✅/❌ Coverage report shows 60%+ on services and middleware packages
          - Evidence: combined coverage <X.X%>
       3. ✅/❌ Authentication middleware pipeline and full search flow are verified by integration tests
          - Evidence: tests/integration/test_auth_pipeline.py (<N> tests), tests/integration/test_search_flow.py (<N> tests)
       4. ✅/❌ A failing test blocks a developer from merging
          - Evidence: see Task 2 (pre-push hook gate verification)

       ## Issues Encountered

       <list any flaky tests, slow tests >5s, deprecation warnings worth tracking>
       ```

    Fill in every `<...>` placeholder with real numbers from the run. If coverage is below 60%, do NOT manipulate the gate — instead, return to Plan 03 and add tests until coverage clears. Document the gap in this report so the planner knows where to add coverage.
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; pytest tests/ 2>&amp;1 | tee /tmp/phase02-final-run.log | tail -20 &amp;&amp; test -f .planning/phases/02-test-suite/02-VERIFICATION.md &amp;&amp; grep -c "Combined gate" .planning/phases/02-test-suite/02-VERIFICATION.md</automated>
  </verify>
  <acceptance_criteria>
    - `pytest tests/ -v` exits with code 0.
    - Output contains a line like `Required test coverage of 60% reached` (or pyproject.toml's `--cov-fail-under=60` is satisfied — pytest-cov prints this on success).
    - `htmlcov/index.html` exists after `make test-cov-html`.
    - `.planning/phases/02-test-suite/02-VERIFICATION.md` exists.
    - Report contains all five sections: Suite Result, Coverage Summary, Per-File Coverage, D-12 Hot-Path File Coverage, ROADMAP Success Criteria Verification.
    - Every `<...>` placeholder replaced with real data (no leftover angle brackets).
    - All four ROADMAP success criteria marked ✅ (if any are ❌, this plan is BLOCKED — return to Plan 03).
  </acceptance_criteria>
  <done>Verification report exists with concrete numbers; coverage gate proven at ≥60%; htmlcov exists for visual inspection.</done>
</task>

<task type="auto">
  <name>Task 2: Update README.md with test/hook docs</name>
  <files>README.md</files>
  <read_first>
    - README.md (full file — find existing "Testing" or "Development" section, or determine where to insert a new one)
    - Makefile (target list to document)
    - .githooks/pre-push (hook contents to reference)
    - pyproject.toml (coverage gate value to cite)
  </read_first>
  <action>
    Edit `README.md` to add a "Testing" section. If a Testing section already exists, REPLACE its body (don't append duplicate content). If no section exists, insert under or near the existing "Development" / "Quality" / "Code Quality" section.

    Section content (use this exact structure):

    ```markdown
    ## Testing

    WhoDis ships with a pytest-based test suite that runs against an ephemeral PostgreSQL container. The suite covers `app/services/` and `app/middleware/` with a 60% coverage gate.

    ### Prerequisites

    - Docker (for the ephemeral PostgreSQL container used by integration tests)
    - Python 3.8+ with `requirements-dev.txt` installed:
      ```bash
      pip install -r requirements.txt -r requirements-dev.txt
      ```

    ### Running tests

    ```bash
    make test                # full suite, coverage gate enforced
    make test-unit           # unit tests only (-m unit)
    make test-integration    # integration tests only (-m integration)
    make test-cov-html       # full suite + HTML coverage report at htmlcov/index.html
    ```

    Or directly:

    ```bash
    pytest tests/ -v
    ```

    Coverage gate (`--cov-fail-under=60`) is configured in `pyproject.toml` under `[tool.pytest.ini_options]`. The gate measures `app/services/` + `app/middleware/` only.

    ### Pre-push hook (recommended)

    A pre-push git hook is provided at `.githooks/pre-push`. It runs `make test` before every push and blocks pushes that fail tests or the coverage gate. Install it once per clone:

    ```bash
    git config core.hooksPath .githooks
    ```

    To bypass in an emergency:

    ```bash
    git push --no-verify
    ```

    ### Test architecture

    - **Fakes** (`tests/fakes/`) — `FakeLDAPService`, `FakeGraphService`, `FakeGenesysService` implement the same interfaces as the real services. No real network calls occur during tests.
    - **Factories** (`tests/factories/`) — `factory_boy` factories for `User`, `ApiToken`, `JobCode`, `SystemRole` against an ephemeral PostgreSQL container.
    - **Container override** — Tests inject fakes via `app.container.register()` against the real DI container — same wiring as production.
    - **Per-test isolation** — Each test runs in a SAVEPOINT that rolls back at teardown; no data leak between tests.
    ```

    DO NOT remove or modify any other section of the README. DO NOT change the project description, installation instructions, or feature list.

    Confirm the existing "Code Quality" section (which references `ruff check --fix` and `mypy`) is left intact — it complements the Testing section, doesn't duplicate it.
  </action>
  <verify>
    <automated>grep -c "core.hooksPath .githooks" README.md &amp;&amp; grep -c "## Testing" README.md &amp;&amp; grep -c "make test" README.md &amp;&amp; grep -c "factory_boy\|factory-boy" README.md</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "^## Testing$" README.md` returns 1 (exactly one Testing H2 section).
    - `grep -c "core.hooksPath .githooks" README.md` returns 1.
    - `grep -c "make test" README.md` returns ≥1 (Testing section references it).
    - `grep -c "make test-unit" README.md` returns 1.
    - `grep -c "make test-integration" README.md` returns 1.
    - `grep -c "60%" README.md` returns ≥1 (coverage gate documented).
    - `grep -c "FakeLDAPService" README.md` returns 1.
    - `grep -c "SAVEPOINT" README.md` returns 1.
    - Existing "Code Quality" / `ruff check --fix` references still present (`grep -c "ruff check" README.md` ≥1 — pre-existing line preserved).
  </acceptance_criteria>
  <done>README documents the test invocation, the hook installer, and the test architecture in one cohesive Testing section; existing content preserved.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Human verifies pre-push hook gate fires (D-09 criterion 4)</name>
  <what-built>
    Pre-push git hook at `.githooks/pre-push` that runs `make test` before every push and blocks on test failure or coverage drop. Plans 01-03 created the hook + suite + coverage gate; Task 1 here verified the suite runs green; this checkpoint asks the human to PROVE the gate fires by deliberately breaking it.
  </what-built>
  <how-to-verify>
    Run these steps locally and confirm each behaves as described:

    1. **Install the hook** (one-time per clone):
       ```bash
       git config core.hooksPath .githooks
       ```

    2. **Verify hook installation:**
       ```bash
       git config --get core.hooksPath
       ```
       Should print `.githooks`.

    3. **Verify the green path** — on the current branch (no broken tests):
       ```bash
       git commit --allow-empty -m "test: pre-push hook smoke test"
       git push --dry-run
       ```
       Hook should run `make test`, suite should pass, push should be permitted (dry-run prints what would be pushed).

    4. **Verify the red path** — deliberately break a test and confirm the gate blocks:
       ```bash
       # Add a failing test in a scratch file
       cat > tests/unit/test_phase2_gate_check.py <<'EOF'
       import pytest
       @pytest.mark.unit
       def test_phase2_gate_must_block_this():
           assert False, "Intentional failure to verify pre-push gate"
       EOF
       git add tests/unit/test_phase2_gate_check.py
       git commit -m "test: deliberate failure for gate verification"
       git push --dry-run
       ```
       **Expected:** Push is BLOCKED. Hook output shows the failing test. `git push` exits non-zero.

    5. **Verify the bypass works** (emergency escape):
       ```bash
       git push --no-verify --dry-run
       ```
       **Expected:** Push proceeds (dry-run output appears). The bypass is intentional per D-09.

    6. **Clean up:**
       ```bash
       git reset HEAD~2          # drop the two test commits
       rm tests/unit/test_phase2_gate_check.py
       ```

    7. **Verify coverage gate also blocks** (separate scenario — optional but recommended):
       Temporarily lower a test to skip critical coverage, run `make test`, confirm `--cov-fail-under=60` triggers a non-zero exit when coverage drops below 60%.

    Confirm:
    - [ ] Hook is installed (`core.hooksPath = .githooks`)
    - [ ] Green push works (passing tests → hook permits push)
    - [ ] Red push BLOCKED (failing test → hook exits non-zero, push prevented)
    - [ ] `--no-verify` bypass works (intentional emergency escape)
    - [ ] Workspace cleaned up (no leftover scratch test file or commits)
  </how-to-verify>
  <resume-signal>Type "approved" if all four gate behaviors verified, or describe what failed (hook not running, gate not blocking, etc.)</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| developer machine → remote git | Pre-push hook is the last local gate; once pushed, code reaches main with no further test enforcement (no CI yet — deferred per CONTEXT) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-11 | T (Tampering) | Developer bypasses hook with --no-verify | accept | Documented escape per D-09; solo-dev project. CI in Phase 3 will close this gap with a non-bypassable webhook gate. |
| T-02-12 | E (Elevation of Privilege) | Hook not installed (developer skipped one-time setup) | mitigate | README §Testing surfaces the install command prominently; future onboarding doc could enforce via setup script. |
</threat_model>

<verification>
- Task 1: full suite passes, coverage ≥60%, VERIFICATION.md complete with real data
- Task 2: README has cohesive Testing section with hook installer + Make targets + architecture summary
- Task 3: human confirms all four hook gate behaviors (green/red/bypass/installed)
</verification>

<success_criteria>
- All Task 1-3 acceptance criteria pass / human approves
- VERIFICATION.md is canonical record of Phase 2 success criteria pass
- README documents the one-line hook installer + `make test*` invocations
- Pre-push hook is proven to block on failing tests AND on coverage drops
- All four ROADMAP §"Phase 2: Test Suite" success criteria marked ✅
</success_criteria>

<output>
After completion, create `.planning/phases/02-test-suite/02-04-SUMMARY.md` documenting:
- Final coverage percentages on services + middleware
- Total test count
- Confirmation that hook gate was human-verified to block failing tests
- Any deferred follow-ups (e.g., CI in Phase 3, blueprint-hardening backlog)
- A one-paragraph "Phase 2 done — what changed for the developer" summary suitable for the milestone retrospective
</output>
