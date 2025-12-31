# Add ruff/mypy configuration and pre-commit hooks

## Overview

While ruff and mypy are in requirements.txt, there is no configuration file (pyproject.toml, ruff.toml) to define linting rules, and no pre-commit hooks to enforce code quality. This means code style and type checking are not consistently enforced across the team.

## Rationale

Without standardized linting configuration: 1) Different developers may use different settings, 2) CI/CD cannot enforce consistent code quality, 3) Type errors may go unnoticed until runtime, 4) Code formatting inconsistencies persist. Pre-commit hooks catch issues before they enter the codebase.

---
*This spec was created from ideation and is pending detailed specification.*
