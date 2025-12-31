# Extract inline HTML rendering to Jinja2 templates

## Overview

There are 26+ _render_* functions across the codebase generating HTML strings directly in Python code. The largest offenders are in search/__init__.py (15 functions, ~1400 lines of HTML) and admin/database.py (10 functions, ~800 lines of HTML). This violates separation of concerns and makes the HTML difficult to maintain.

## Rationale

Inline HTML in Python is an anti-pattern that: 1) Makes HTML changes require Python expertise, 2) Prevents IDE HTML syntax highlighting/validation, 3) Complicates template inheritance and reuse, 4) Makes XSS vulnerabilities harder to spot, 5) Bloats Python files unnecessarily. The project already uses Jinja2 templates for other views.

---
*This spec was created from ideation and is pending detailed specification.*
