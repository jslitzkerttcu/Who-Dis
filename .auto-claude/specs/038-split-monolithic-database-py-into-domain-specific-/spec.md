# Split monolithic database.py into domain-specific modules

## Overview

The file app/blueprints/admin/database.py has grown to 2532 lines with 43+ functions handling unrelated concerns: database health, table stats, session management, cache operations, error logs, API token management, and extensive HTML rendering. This violates single responsibility and makes the code difficult to navigate, test, and maintain.

## Rationale

This 'god module' pattern increases cognitive load, makes code reviews extremely difficult, leads to merge conflicts, and prevents modular testing. Functions for cache management have no logical connection to error logging functions, yet they share the same file.

---
*This spec was created from ideation and is pending detailed specification.*
