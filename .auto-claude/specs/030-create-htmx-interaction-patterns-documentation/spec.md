# Create HTMX interaction patterns documentation

## Overview

The application uses a hybrid Jinja2 + HTMX architecture but there's no documentation explaining how HTMX fragments work, which endpoints return partials vs full pages, or patterns for adding new HTMX-enabled features. Developers must reverse-engineer existing templates.

## Rationale

HTMX is central to the modern UI architecture. Without documentation, developers may incorrectly implement endpoints (returning full pages instead of fragments) or miss important patterns like hx-target, hx-swap, and request context preservation. This slows feature development.

---
*This spec was created from ideation and is pending detailed specification.*
