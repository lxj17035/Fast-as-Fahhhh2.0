---
version: alpha
name: QuoteFlow
description: A supervised SME quotation workbench with a forest green rail and quiet document surfaces.
colors:
  primary: "#227961"
  primary-dark: "#185b49"
  ink: "#203b32"
  muted: "#7a8580"
  border: "#e5eae7"
  sidebar: "#152e27"
  background: "#f6f8f7"
typography:
  sans:
    fontFamily: "Inter, 'Segoe UI', Arial, sans-serif"
    fontSize: "14px"
omitted:
  - section: spacing
    reason: Existing CSS owns responsive geometry; no generated spacing layer.
  - section: rounded
    reason: Existing component CSS owns corner geometry.
  - section: components
    reason: Shared markup helpers and component CSS are canonical.
---

# QuoteFlow design context

## Overview

Product register: a sales desk reviewing an actual document beside a customer
message. Audience: Malaysian SME Staff and Managers in a supervised synthetic
demo (README.md and docs/WORKFLOW.md). English UI, MYR demo, Kuala Lumpur time.
The green workspace rail is the signature; editing, prices and sending remain
quiet and explicit. Preserve the existing UI. No marketing hero, decorative
analytics, new font downloads or speculative rebrand.

Runtime source of truth: frontend/src/styles.css. Frontmatter mirrors its root
palette and type stack; it does not generate a second theme. Changes to these
values require updating both. Existing browser fallbacks remain system owned.

## Colors

Green identifies primary actions; neutral borders separate document sections.
Status always has text. Light theme only; forced colors retain usable scrollbars.
Scrollbar track/thumb/hover/active map to background/muted/primary/primary-dark.

## Typography

Reuse the local CSS font stack without network requests. Headings, labels and
technical references retain their existing CSS roles. Long business/customer
values must wrap without pushing actions outside the viewport.

## Layout

Reuse settings-grid, panel, field, field-grid and form-bottom. The profile panel
spans the settings columns. Main document scrolling remains natural; tables own
horizontal overflow. Existing CSS breakpoints control narrow layouts.

## Elevation & Depth

Existing panel borders/shadows remain canonical. Dialogs are the only blocking
overlay; ordinary settings saves remain inline.

## Shapes

Reuse existing button, badge, field and panel geometry from styles.css.

## Components

app.js owns shared button/input/validitySelect/ask/noticeBox/errorBox helpers.
Native selects and dates retain platform-owned popups. Use real labels, visible
focus and explicit busy/disabled state. Profile switching uses the shared
unsaved-edit dialog; errors preserve edits. See docs/FRONTEND.md for behavior.

## Do's and Don'ts

- Reuse existing shell, form and feedback patterns across F1–F5.
- Keep active business context visible; AI never selects a profile.
- Keep blank prices distinct from zero; show backend totals and expiry.
- Never imply a mocked delivery proves live Telegram or hosted integration.

## V2 review surfaces

Reuse panel/field/button/table-scroll across assignments, Conversation Room,
suggested changes and the final review. v2-panel is their shared content padding
adapter. Staff/Manager labels map to existing simulated sales/pm roles. Prices
are readonly for Staff. A final review uses the saved version, actual PDF and
server summary together. Frozen partial delivery explains the protected edit
state. Horizontal scrolling belongs to the item table; the page scrolls naturally.
