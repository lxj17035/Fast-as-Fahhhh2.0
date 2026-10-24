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

## Inbox reference preview (24 October 2026)

The owner supplied quoteflow-inbox.html and quoteflow-inbox-spec.md and approved
a local-only inbox redesign. Route #/ uses a dark #142c28 header, #1f6b55 actions,
760px centered column, task rows, role-owned To do, All/Closed and native source/
stage filters. Settings remains in the header; assisted/synthetic notices remain
in the footer. Scope all overrides under .inbox-shell in frontend/src/inbox.css;
the detail editor, Settings and PDF surfaces retain their existing design.
Do not show internal enquiry Copy ID buttons; assignment uses the dropdown.
Assignment stays an inline explicit action with history.
Close/Restore is browser-session-only, approved for preview; it does not alter
backend routing, send guards or records. Non-Telegram examples require an explicit
localhost-only switch and cannot send. No extra live AI calls for short titles.

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

Owner refinement: Inbox restores the existing left sidebar and Settings navigation,
matching the Settings page. Keep the compact task list in the remaining content
column. Use saved shortTitle first, compact saved item/quantity for legacy rows.

## Detail review reference (24 October 2026, local preview)

Use the supplied quoteflow-detail.html/spec as the layout reference: centered
820px content, one next-step panel, Quote/Preview/Messages/Activity tabs, and
an amber new-customer-message notice containing the actual text. Keep the shared
sidebar. Staff remains able to edit unsent details; Manager owns pricing and
approval. No new handover state or duplicate Save-for-Manager button.
Use explicit Confirm handled & save quote only for unreviewed incoming source
IDs; no permanent review checkbox. Preserve the current saved PDF renderer and
Manager's saved PDF/summary verification before a final send dialog. Changes
retain existing prices and require saving/previewing again. Technical history
stays collapsed in Activity; old quotation browsing remains future work.
