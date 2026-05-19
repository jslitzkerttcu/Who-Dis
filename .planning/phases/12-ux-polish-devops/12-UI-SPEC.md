---
phase: 12
slug: ux-polish-devops
status: draft
shadcn_initialized: false
preset: none
created: 2026-05-18
---

# Phase 12 — UI Design Contract

> Visual and interaction contract for the SKU license tooltip feature (UXP-01). DevOps requirements (DEVOPS-01 through DEVOPS-03) have no UI surface and are excluded from this contract.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (Flask/Jinja2 project — shadcn not applicable) |
| Preset | not applicable |
| Component library | none (server-rendered Jinja2 templates) |
| Icon library | FontAwesome 6.5.1 (CDN) |
| Font | Tailwind CDN default (system font stack: ui-sans-serif, system-ui, sans-serif) |

---

## Spacing Scale

Declared values (must be multiples of 4):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Tooltip arrow offset, list item gap |
| sm | 8px | Tooltip internal padding (horizontal), list item vertical spacing |
| md | 16px | Tooltip internal padding (vertical on larger tooltips) |
| lg | 24px | Not used this phase |
| xl | 32px | Not used this phase |
| 2xl | 48px | Not used this phase |
| 3xl | 64px | Not used this phase |

Exceptions: Tooltip max-width is 280px (not on scale — content-driven constraint for readability on narrow viewports).

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Tooltip heading (license name) | 12px (text-xs) | 600 (font-semibold) | 1.5 |
| Tooltip list item (service plan) | 11px (custom or text-xs) | 400 (font-normal) | 1.4 |
| Tooltip overflow text ("+N more") | 11px | 400 (font-normal) | 1.4 |
| Badge text (existing, unchanged) | 12px (text-xs) | 500 (font-medium) | 1.5 |

Note: 11px is achieved via Tailwind arbitrary value `text-[11px]`. Only 2 weights used: 400 (normal) and 600 (semibold).

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | white / bg-white | Page background, content areas (existing) |
| Secondary (30%) | gray-50 / gray-100 | Card backgrounds, section dividers (existing) |
| Accent (10%) | ttcu-green #007c59 | Primary CTAs, active nav items (existing) |
| Destructive | red-600 | License remove button (existing, unchanged) |

### Tooltip-Specific Colors

| Element | Class | Hex |
|---------|-------|-----|
| Tooltip background | bg-gray-900 | #111827 |
| Tooltip text | text-gray-100 | #F3F4F6 |
| Tooltip heading text | text-white | #FFFFFF |
| Tooltip "+N more" text | text-gray-400 | #9CA3AF |
| Tooltip arrow | bg-gray-900 (matching background) | #111827 |
| Badge (existing, unchanged) | bg-blue-100 text-blue-800 | #DBEAFE / #1E40AF |

Accent reserved for: primary navigation active state, "Sign In" CTA button, admin action buttons. Not used in tooltip.

---

## Component Inventory

### SKU License Tooltip

**Trigger:** Hover on license badge `<span>` (existing `group` class already present).

**Positioning:** Centered below the badge, with a 4px upward-pointing arrow. Falls back to above-badge if near viewport bottom edge.

**Structure:**
```
+----------------------------------+
| License Display Name       (bold)|
|----------------------------------|
| * Exchange Online (Plan 2)       |
| * Microsoft Teams                |
| * SharePoint Online (Plan 2)     |
| * Office for the Web             |
| * Microsoft Entra ID P1          |
| +7 more service plans            |
+----------------------------------+
         ^  (arrow)
   [ Badge Label ]
```

**Dimensions:**
- Min width: 200px
- Max width: 280px
- Padding: 8px horizontal, 8px vertical
- Border radius: 6px (rounded-md)
- Arrow: 6px x 6px rotated square

**Behavior:**
- Show on hover after 150ms delay (prevents flash on cursor pass-through)
- Hide on mouse leave after 100ms delay (allows cursor to move into tooltip)
- Tooltip itself is hoverable (keeps tooltip open while cursor is inside)
- No tooltip on touch devices — tap badge to show, tap elsewhere to dismiss
- Transition: opacity 0 to 1, 150ms ease-in-out

**Accessibility:**
- Badge gets `aria-describedby` pointing to tooltip `id`
- Tooltip has `role="tooltip"`
- Tooltip content is accessible via screen reader even when visually hidden (use `sr-only` fallback or `aria-label` on badge with full plan list)
- Keyboard: tooltip shows on badge focus, hides on blur

**States:**
| State | Appearance |
|-------|------------|
| Default (no hover) | Tooltip hidden, badge displays as current |
| Hover / Focus | Tooltip fades in below badge |
| Loading (plans not cached yet) | Tooltip shows "Loading..." in italic gray-400 text |
| No service plans available | Tooltip shows "No service plan details available" |
| Error (cache miss) | No tooltip shown — badge functions as current (graceful degradation) |

**Implementation notes:**
- Replace existing `title="{{ lic.get('skuId') }}"` with the styled tooltip
- Use Tailwind `group/badge` and `group-hover/badge:` for show/hide (CSS-only where possible)
- If CSS-only positioning is insufficient for viewport awareness, use a minimal vanilla JS snippet (under 30 lines) for repositioning
- Service plan data comes from `SkuCatalogCache` — template receives plans as part of license dict

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA | Not applicable (no CTA in this phase — tooltip is passive display) |
| Empty state heading | Not applicable (no new views or pages added) |
| Empty state body | Not applicable |
| Tooltip loading | "Loading..." |
| Tooltip no data | "No service plan details available" |
| Tooltip overflow | "+{N} more service plans" |
| Error state | No visible error — tooltip simply does not appear (graceful degradation per D-02) |
| Destructive confirmation | Not applicable (no new destructive actions; existing license remove unchanged) |

---

## Interaction Contract

| Interaction | Behavior |
|-------------|----------|
| Mouse hover on badge | Show tooltip after 150ms delay |
| Mouse leave badge+tooltip | Hide tooltip after 100ms delay |
| Mouse enter tooltip | Keep tooltip visible |
| Keyboard focus on badge | Show tooltip immediately |
| Keyboard blur from badge | Hide tooltip immediately |
| Touch tap on badge | Toggle tooltip visibility |
| Touch tap outside tooltip | Hide tooltip |
| Window resize / scroll | Reposition or hide tooltip |

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| Not applicable | N/A | N/A — no component registry (Flask/Jinja2 project) |

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
