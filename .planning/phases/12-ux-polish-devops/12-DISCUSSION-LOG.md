# Phase 12: UX Polish & DevOps - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 12-UX Polish & DevOps
**Areas discussed:** Tooltip content, Docker stage strategy, Image size target

---

## Tooltip Content

### What should the tooltip show?

| Option | Description | Selected |
|--------|-------------|----------|
| Friendly name + GUID | Show display name and SKU GUID for IT debugging | |
| Service plan breakdown | Show what's included in the license (Exchange, SharePoint, Teams, etc.) | ✓ |
| Just the friendly name | Replace GUID with display name only — minimal change | |

**User's choice:** Service plan breakdown
**Notes:** Adds real value beyond badge text which already shows the friendly name

### How to handle long service plan lists?

| Option | Description | Selected |
|--------|-------------|----------|
| Top 5 + count | Show 5 most recognizable plans plus "+N more" | ✓ |
| Full list, scrollable | All plans in a scrollable styled tooltip | |
| Grouped by category | Plans grouped by type with section headers | |

**User's choice:** Top 5 + count
**Notes:** Keeps tooltip compact and scannable

### Tooltip presentation?

| Option | Description | Selected |
|--------|-------------|----------|
| Styled Tailwind tooltip | Custom tooltip with background, padding, shadow. Can format service plans as a clean list | ✓ |
| Native browser title | Zero-JS, just title attribute. Can't format a list | |

**User's choice:** Styled Tailwind tooltip

### Include SKU GUID in tooltip?

| Option | Description | Selected |
|--------|-------------|----------|
| Include GUID | Small/muted text at bottom for IT debugging | |
| Plans only | Keep tooltip focused on license contents | ✓ |

**User's choice:** Plans only

---

## Docker Stage Strategy

### Runtime stage contents?

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal runtime | Only Python + ODBC runtime libs + pip packages + app code | |
| Runtime + convenience tools | Keep curl and postgresql-client, strip gnupg2 | |
| You decide | Let Claude determine optimal split | ✓ |

**User's choice:** You decide

### Healthcheck approach without curl?

| Option | Description | Selected |
|--------|-------------|----------|
| Python healthcheck script | Tiny Python script using urllib | |
| Keep curl in runtime | Small (~7MB), useful for debugging | |
| wget (already in slim) | python:3.12-slim may include wget | |

**User's choice:** You decide

### Base image?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep slim | Debian-based, ODBC driver has official packages, well-tested | ✓ |
| Switch to alpine | Smaller base but ODBC compilation is complex on musl libc | |
| You decide | Let Claude pick based on 30% reduction target | |

**User's choice:** Keep slim

---

## Image Size Target

### Exclude .planning/ from .dockerignore?

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude .planning | Planning artifacts have no runtime purpose | ✓ |
| Already handled | Existing *.md exclusion may cover most of it | |

**User's choice:** Exclude .planning

### Size verification approach?

| Option | Description | Selected |
|--------|-------------|----------|
| Manual verification | Document before/after sizes, no automated gate | ✓ |
| Add size check script | Automated comparison to prevent regressions | |
| You decide | Let Claude determine approach | |

**User's choice:** Manual verification

---

## Claude's Discretion

- Docker runtime stage composition (minimal vs convenience tools)
- Healthcheck replacement for curl
- ODBC driver installation strategy across build stages

## Deferred Ideas

None — discussion stayed within phase scope
