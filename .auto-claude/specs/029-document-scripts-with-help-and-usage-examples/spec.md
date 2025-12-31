# Document scripts with --help and usage examples

## Overview

The scripts/ directory contains 8 utility scripts (check_config_status.py, diagnose_config.py, refresh_employee_profiles.py, etc.) but none have argparse/--help documentation. Users must read source code to understand script arguments, options, and expected behavior.

## Rationale

IT administrators and developers frequently use these scripts for maintenance tasks. Without proper CLI documentation, users may run scripts incorrectly or miss important options. The refresh_employee_profiles.py script is particularly critical as it has a 'refresh' argument that isn't self-documenting.

---
*This spec was created from ideation and is pending detailed specification.*
