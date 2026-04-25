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
