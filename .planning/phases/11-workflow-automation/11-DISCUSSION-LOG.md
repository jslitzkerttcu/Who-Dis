# Phase 11: Workflow Automation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 11-workflow-automation
**Areas discussed:** Checklist Generation, Completion Tracking, Offboarding Reversal, Dashboard Design

---

## Checklist Generation

### How should onboarding checklists be created?

| Option | Description | Selected |
|--------|-------------|----------|
| Manual trigger only | Admin selects a job code + employee name, clicks 'Generate Checklist'. Items pre-populated from JobRoleMapping entries for that job code. | |
| Template-first | Admin creates/edits checklist templates per job code (seeded from mappings but customizable). When onboarding, pick a template + employee to instantiate it. | |
| You decide | Claude picks the best approach based on the 4-5 person team size and existing data model. | ✓ |

**User's choice:** You decide
**Notes:** None

### Should checklists include items beyond system role assignments?

| Option | Description | Selected |
|--------|-------------|----------|
| Roles only | Checklist items come exclusively from JobRoleMapping entries (AD groups, Genesys queues, Keystone apps). Pure system provisioning. | |
| Roles + custom items | Auto-populate from mappings, but admin can add freeform checklist items (equipment, orientation, etc.) before or after generation. | |
| You decide | Claude picks based on WKFL-01..04 requirements and team workflow. | ✓ |

**User's choice:** You decide
**Notes:** None

### When generating a checklist, how should the admin identify the target employee?

| Option | Description | Selected |
|--------|-------------|----------|
| Search-first | Admin searches for the employee (reusing existing search), then clicks 'Start Onboarding' from their profile. Employee data auto-populated. | |
| Form entry | Admin fills out a form with employee name, email, job code. Works even if the employee isn't in AD/Graph yet (brand new hire). | |
| Both paths | Search-first for existing employees, form entry for net-new hires not yet in any system. | ✓ |

**User's choice:** Both paths
**Notes:** None

### Should checklist items linked to Phase 9 write operations have an 'Execute' button?

| Option | Description | Selected |
|--------|-------------|----------|
| Manual checkboxes | All items are checkboxes. Admin performs the action elsewhere, then marks it done here. Simpler, lower risk. | |
| Actionable items | Items linked to write operations show an 'Execute' button that performs the action AND marks the item complete. | |
| You decide | Claude picks based on team size, risk tolerance, and v2 requirements (AUTO-01 defers auto-execute to future milestone). | ✓ |

**User's choice:** You decide
**Notes:** None

---

## Completion Tracking

### How should admins mark checklist items as complete?

| Option | Description | Selected |
|--------|-------------|----------|
| Individual checkboxes | Each item has a checkbox. Click to mark done — records who and when. Simple, one at a time. | |
| Individual + bulk | Individual checkboxes plus a 'Mark all as complete' or multi-select for batch completion. | |
| You decide | Claude picks based on typical checklist size and team workflow. | ✓ |

**User's choice:** You decide
**Notes:** None

### Can checklist items be skipped or marked N/A?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, with reason | Items can be marked 'Skipped' or 'N/A' with a required note explaining why. Still shows in the audit trail. | ✓ |
| No skipping | Every item must be completed or the workflow stays open. Strictest compliance posture. | |
| You decide | Claude picks based on practical IT operations workflow. | |

**User's choice:** Yes, with reason
**Notes:** None

### Should checklist items have due dates or SLA expectations?

| Option | Description | Selected |
|--------|-------------|----------|
| No due dates | Items are either done or not done. The dashboard shows age/staleness but no per-item deadlines. | |
| Optional due dates | Each item can have an optional due date. Overdue items highlighted on the dashboard. | ✓ |
| You decide | Claude picks based on WKFL-04 'highlights overdue items' requirement. | |

**User's choice:** Optional due dates
**Notes:** None

### Can multiple admins work on the same checklist?

| Option | Description | Selected |
|--------|-------------|----------|
| Any admin | Any admin can complete any item on any workflow. Whoever does it gets recorded in the audit trail. No formal assignment. | ✓ |
| Assigned owner | Each workflow has an assigned admin. Others can still complete items, but one person is 'responsible'. | |
| You decide | Claude picks based on the 4-5 person team size. | |

**User's choice:** Any admin
**Notes:** None

---

## Offboarding Reversal

### How should offboarding checklists relate to onboarding?

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-reverse from mappings | Generate offboarding directly from the job code's role mappings. Each 'required' role becomes a 'remove' item. No dependency on prior onboarding records. | ✓ |
| Reverse completed onboarding | Generate offboarding by reversing a specific completed onboarding workflow. Requires the employee to have been onboarded through WhoDis. | |
| You decide | Claude picks the most practical approach given that existing employees won't have onboarding records in WhoDis. | |

**User's choice:** Auto-reverse from mappings
**Notes:** None

### Should offboarding include items beyond role removals?

| Option | Description | Selected |
|--------|-------------|----------|
| Roles only | Offboarding checklist only includes system role removals derived from mappings. | |
| Roles + standard extras | Include role removals PLUS a configurable set of standard offboarding items that apply to everyone. | ✓ |
| You decide | Claude picks based on WKFL-02 requirement and practical IT offboarding needs. | |

**User's choice:** Roles + standard extras
**Notes:** None

### Where should the standard offboarding extras be configured?

| Option | Description | Selected |
|--------|-------------|----------|
| Admin UI | Admins manage the list through the admin interface. Add/remove/reorder at any time. | ✓ |
| Database seed | Standard items defined in a migration/seed. Changing them requires a code deploy. | |
| You decide | Claude picks based on how often these would change for a small team. | |

**User's choice:** Admin UI
**Notes:** None

---

## Dashboard Design

### Where should the workflow dashboard live in the navigation?

| Option | Description | Selected |
|--------|-------------|----------|
| Admin sub-section | New tab/page under /admin/workflows. Consistent with existing admin structure. | |
| Top-level nav item | New 'Workflows' item in the main navigation bar. More prominent. | |
| You decide | Claude picks based on existing nav structure and admin-only access requirement. | ✓ |

**User's choice:** You decide
**Notes:** None

### What should the dashboard prioritize showing at a glance?

| Option | Description | Selected |
|--------|-------------|----------|
| Active workflows list | Table of all in-progress workflows with employee name, type, progress bar, and days open. | |
| KPI cards + list | Summary cards at top followed by the active workflows table below. | |
| You decide | Claude picks based on reporting patterns from Phase 8 (KPI cards + data table). | ✓ |

**User's choice:** You decide
**Notes:** None

### Should completed workflows be visible on the dashboard?

| Option | Description | Selected |
|--------|-------------|----------|
| Active only + archive link | Dashboard shows only active workflows. Completed accessible via 'View History'. | |
| Tabbed: Active / Completed | Dashboard has tabs switching between active and completed. Everything in one place. | |
| You decide | Claude picks based on dashboard clarity and typical admin workflow. | ✓ |

**User's choice:** You decide
**Notes:** None

---

## Claude's Discretion

The following areas were deferred to Claude's judgment:
- Checklist generation approach (manual trigger vs. template-first)
- Item scope (roles-only vs. roles + custom freeform items)
- Actionable execute buttons vs. manual checkboxes for write-operation items
- Individual vs. individual + bulk completion marking
- Dashboard navigation placement
- Dashboard layout (list-only vs. KPI cards + list)
- Completed workflow visibility (tabbed vs. separate archive)

## Deferred Ideas

- **AUTO-01:** Auto-execute checklist items (v2 requirement)
- **AUTO-02:** Self-service portal for common IT requests (v2 requirement)
