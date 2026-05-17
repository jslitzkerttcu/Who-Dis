# Phase 9: Write Operations - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 09-write-operations
**Areas discussed:** Confirmation UX, AD action scope, License atomicity, Action placement

---

## Confirmation UX

### Confirmation flow

| Option | Description | Selected |
|--------|-------------|----------|
| Reason-only modal | Modal with textarea for reason. Simple, fast. | |
| Reason + target echo | Modal shows target user name/email, requires reason. | ✓ |
| Reason + type-to-confirm | Must type target name AND reason before Confirm enables. | |

**User's choice:** Reason + target echo

### Post-action feedback

| Option | Description | Selected |
|--------|-------------|----------|
| Inline toast + icon | Toast at top + button icon change. Non-blocking. | ✓ |
| Modal stays open | Modal shows result, user dismisses manually. | |
| You decide | Claude picks based on existing patterns. | |

**User's choice:** Inline toast + icon

### Reason input format

| Option | Description | Selected |
|--------|-------------|----------|
| Freeform only | Plain textarea, admin types whatever. | ✓ |
| Presets + custom | Dropdown of common reasons plus freeform field. | |
| You decide | Claude picks for audit log usefulness. | |

**User's choice:** Freeform only

### Risk tiering

| Option | Description | Selected |
|--------|-------------|----------|
| Same flow for all | Every action uses identical confirmation modal. | |
| Two tiers | Low-risk: standard. High-risk: adds warning banner. | |
| You decide | Claude determines based on AD/Graph reversibility. | ✓ |

**User's choice:** You decide

---

## AD Action Scope

### Operations in v1

| Option | Description | Selected |
|--------|-------------|----------|
| All four in v1 | Unlock, reset, enable, disable all ship together. | ✓ |
| Unlock + reset first | Ship low-risk first, enable/disable follow later. | |
| You decide | Claude determines safe ordering. | |

**User's choice:** All four in v1

### Password display

| Option | Description | Selected |
|--------|-------------|----------|
| One-time reveal in modal | Shown once, gone when dismissed. | |
| Clipboard auto-copy | Auto-copied, never displayed. | |
| Reveal + copy button | Dismissible banner with show/hide and copy. Stays until dismissed. | ✓ |

**User's choice:** Reveal + copy button

### Password generation

| Option | Description | Selected |
|--------|-------------|----------|
| Random (secure) | 16-char cryptographically random. Hard to read aloud. | |
| Readable pattern | Word+digits+symbol (e.g., "Sunset42!"). Easy verbal. | ✓ |
| Configurable | Admin sets strategy in config. | |

**User's choice:** Readable pattern

### AD credentials

| Option | Description | Selected |
|--------|-------------|----------|
| Same bind account | Use existing LDAP bind DN. Simpler. | ✓ |
| Separate write account | New config keys for dedicated write account. | |
| You decide | Claude determines based on AD best practices. | |

**User's choice:** Same bind account

---

## License Atomicity

### Swap failure handling

| Option | Description | Selected |
|--------|-------------|----------|
| Graph single call | POST /assignLicense with both add and remove. Truly atomic. | |
| Two calls + rollback | Remove first, assign second, rollback on failure. | ✓ |
| You decide | Claude researches Graph capabilities. | |

**User's choice:** Two calls + rollback

### Double-failure UX

| Option | Description | Selected |
|--------|-------------|----------|
| Error with manual steps | Clear error explaining partial state + retry button. | |
| Admin alert + log | Error to admin + high-severity audit entry. | |
| You decide | Claude picks safest for small IT team. | ✓ |

**User's choice:** You decide

### Graph permissions

| Option | Description | Selected |
|--------|-------------|----------|
| Already has write perms | Existing app registration has User.ReadWrite.All. | |
| Will need new perms | New permissions needed, document as dependency. | |
| Not sure | Flag as external dependency for planner. | ✓ |

**User's choice:** Not sure — planner must research and document

---

## Action Placement

### Button location

| Option | Description | Selected |
|--------|-------------|----------|
| Inside expanded profile | Actions in Phase 6 collapsible sections. Contextual. | ✓ |
| Action bar on card | Dedicated bar always visible on each result. | |
| Contextual dropdown | Kebab menu on each card. Clean but extra click. | |

**User's choice:** Inside expanded profile

### Visibility for non-admins

| Option | Description | Selected |
|--------|-------------|----------|
| Hidden for non-admins | Only admins see buttons. Cleaner for read-only users. | |
| Visible but disabled | All see buttons grayed out with "Admin only" tooltip. | |
| You decide | Claude picks for ~4-5 person team context. | ✓ |

**User's choice:** You decide

### License UI structure

| Option | Description | Selected |
|--------|-------------|----------|
| Inline in M365 section | Buttons next to each license row. | |
| Dedicated sub-panel | Separate "Manage Licenses" modal/panel. | |
| You decide | Claude picks based on complexity and patterns. | ✓ |

**User's choice:** You decide

---

## Claude's Discretion

- Risk tiering for confirmation modals (same flow vs. two tiers)
- Double-failure UX for license swap rollback failure
- Action button visibility for non-admins (hidden vs. disabled)
- License management UI structure (inline vs. sub-panel)

## Deferred Ideas

None — discussion stayed within phase scope
