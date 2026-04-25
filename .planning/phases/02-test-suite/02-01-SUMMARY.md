---
phase: 02-test-suite
plan: 01
subsystem: testing
tags: [pytest, pytest-cov, factory-boy, testcontainers, makefile, git-hooks, infra]

requires:
  - phase: 01-foundation
    provides: existing requirements.txt with ruff/mypy/types-* mixed in runtime deps
provides:
  - requirements-dev.txt — dev-only dependency manifest (test framework + lint/type-check)
  - pyproject.toml — pytest + coverage configuration with 60% gate on app/services + app/middleware
  - Makefile — single source of truth for test/lint/typecheck task invocations
  - .githooks/pre-push — bash gate calling `make test` before every push
  - cleaned runtime requirements.txt (no dev tools — ready for Phase 3 container build)
affects: [02-test-suite plans 02/03/04, 03-containerization]

tech-stack:
  added: [pytest, pytest-cov, pytest-mock, factory-boy, "testcontainers[postgres]", beautifulsoup4]
  patterns: [dev/runtime requirements split, pyproject.toml tool config, Makefile task runner, githooks-based pre-push gate]

key-files:
  created:
    - requirements-dev.txt
    - pyproject.toml
    - Makefile
    - .githooks/pre-push
  modified:
    - requirements.txt (removed ruff, mypy, types-* — moved to dev manifest)

key-decisions:
  - "Pytest + coverage config in pyproject.toml (D-11 + Discretion §1) — mypy stays in mypy.ini (no migration mandated)"
  - "Coverage gate scoped to app/services + app/middleware only (D-11) — blueprints/models/utils excluded from --cov-fail-under enforcement"
  - "Pre-push hook is bare bash in .githooks/ (D-09) — no pre-commit framework installed in repo; bypass via --no-verify is intentional emergency escape"
  - "Makefile `test:` target runs `pytest -x` only — coverage flags live in pyproject.toml addopts so there is one source of truth"
  - "--strict-markers enforced to prevent typos in @pytest.mark.unit / @pytest.mark.integration silently passing as no-op"

patterns-established:
  - "Dev/runtime split: requirements.txt holds prod deps; requirements-dev.txt overlays test + lint tooling. Phase 3 Dockerfile installs only requirements.txt."
  - "Tool config in pyproject.toml using TOML tables ([tool.pytest.ini_options], [tool.coverage.run], [tool.coverage.report]) — INI-style mypy.ini retained alongside (no forced migration)."
  - "Makefile + githooks pattern: task runner invoked by hook ensures `make test` and `git push` exercise identical commands."

requirements-completed: [TEST-01, TEST-04]

duration: 2min
completed: 2026-04-25
---

# Phase 2 Plan 1: Test Infrastructure Scaffolding Summary

**Bootstrap pytest harness with dev/runtime requirements split, pyproject.toml coverage config (60% gate on services+middleware), Makefile task runner, and pre-push git hook — no application code changed.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-25T17:26:43Z
- **Completed:** 2026-04-25T17:28:07Z
- **Tasks:** 3
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments

- Split requirements into runtime (`requirements.txt`) and dev (`requirements-dev.txt`) manifests so Phase 3 container builds will not pull pytest/factory-boy/testcontainers into production images
- Added `pyproject.toml` with pytest discovery (`testpaths = ["tests"]`), coverage gate `--cov-fail-under=60` scoped to `app.services` + `app.middleware` (per D-11), `unit`/`integration` markers, and `--strict-markers` typo guard
- Created `Makefile` with `test`, `test-unit`, `test-integration`, `test-cov-html`, `lint`, `typecheck` targets (TAB-indented; verified)
- Created `.githooks/pre-push` (mode 100755) that calls `make test`; `git push --no-verify` remains the documented bypass per D-09
- Verified `.gitignore` already covers `htmlcov/`, `.coverage`, `.coverage.*`, `.pytest_cache/` — no edit required

## Task Commits

1. **Task 1: Split requirements into runtime + dev manifests** — `0ae0efa` (chore)
2. **Task 2: Create pyproject.toml with pytest + coverage config** — `447c22d` (chore)
3. **Task 3: Create Makefile, pre-push hook, and verify .gitignore** — `688a6f6` (chore)

## Files Created/Modified

- `requirements-dev.txt` (created) — pytest>=8,<9, pytest-cov>=5,<6, pytest-mock>=3.14,<4, factory-boy>=3.3,<4, testcontainers[postgres]>=4,<5, beautifulsoup4>=4.12,<5, plus ruff/mypy/types-* relocated from runtime
- `requirements.txt` (modified) — removed ruff, mypy, types-tabulate, types-flask, types-requests, types-psycopg2, types-pytz, types-cryptography (8 lines removed). Runtime deps (Flask 3.1.3 .. Flask-Limiter>=3.5,<4) untouched.
- `pyproject.toml` (created) — `[tool.pytest.ini_options]` + `[tool.coverage.run]` + `[tool.coverage.report]` per spec; no `[tool.mypy]`, no `[build-system]`, no `[project]`
- `Makefile` (created) — `.PHONY: test test-unit test-integration test-cov-html lint typecheck` plus tab-indented recipes
- `.githooks/pre-push` (created, mode 100755) — `set -euo pipefail; echo "[pre-push] running test suite..."; make test`

## Decisions Made

- **mypy config left in `mypy.ini`** rather than migrated into `pyproject.toml` — CONTEXT D-11 / Discretion §1 explicitly noted this was acceptable, and avoiding the move keeps the diff focused on test infra.
- **Makefile `test:` recipe is `pytest -x` (no flags)** — all coverage flags live in `pyproject.toml` `addopts`, so `make test`, `pytest`, and the pre-push hook all exercise identical configuration.
- **`.gitignore` not modified** — verified all four required entries (`htmlcov/`, `.coverage`, `.coverage.*`, `.pytest_cache/`) already present in the existing Python-template .gitignore. Adding a redundant "# Test artifacts (Phase 2)" section would create unnecessary churn.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `make` is not on PATH on this Windows development host, so `make -n test` could not be executed as a final smoke check. The Makefile parses correctly (TABs verified via `cat -A`), uses standard GNU make syntax, and will run successfully wherever `make` is installed (developer machines / CI). The pre-push hook's `bash -n` syntax check passed.

## User Setup Required

None for this plan. Two follow-ups for Plan 04 (README update) to surface to developers:
- One-time per clone: `git config core.hooksPath .githooks` to activate the pre-push hook
- One-time per dev environment: `pip install -r requirements-dev.txt` (in addition to `requirements.txt`)

## Next Phase Readiness

- Plan 02-02 (test DB harness + fakes + factories) can now write `tests/conftest.py` knowing pytest will discover `tests/`, apply the coverage gate, and respect `unit`/`integration` markers
- Plan 02-03 (integration + targeted unit tests) inherits the same harness — no further infra needed
- Plan 02-04 (README + verification) will document the `git config core.hooksPath .githooks` installer line

## Self-Check: PASSED

- requirements-dev.txt exists at repo root — FOUND
- requirements.txt no longer contains ruff/mypy/types-* (grep returns 0 matches) — VERIFIED
- pyproject.toml exists with required tables, no [tool.mypy] / [build-system] / [project] — VERIFIED
- Makefile exists with `test:` target invoking `pytest -x` (TAB-indented) — VERIFIED
- .githooks/pre-push exists (mode 100755), calls `make test`, bash syntax valid — VERIFIED
- .gitignore covers htmlcov/, .coverage, .coverage.*, .pytest_cache/ — VERIFIED
- Commits 0ae0efa, 447c22d, 688a6f6 present in git log — VERIFIED
- TOML parses via tomllib — VERIFIED

---
*Phase: 02-test-suite*
*Completed: 2026-04-25*
