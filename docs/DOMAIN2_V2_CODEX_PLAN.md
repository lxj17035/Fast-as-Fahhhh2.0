# Fast-as-Fahhhh — Domain 2 System Flow V2

**Status:** Confirmed business requirements and section-by-section implementation instructions; **not evidence of implementation or passing tests**.

## Implementation checklist

Updated 24 October 2026 (Asia/Kuala_Lumpur). Check a section only after its
implementation and required tests pass. Record its implementation commit and
verification below; an unchecked section may contain reusable existing code.
After each section, update this checklist before handing work back.

- [x] B1 — Business Profiles & shared data scope — `6b77031`; verification below.
- [x] B2 — Telegram enquiry routing & assignment — `ce5daac`; verification below.
- [x] B3 — Conversation Room APIs — `f5e2f7f`; verification below.
- [ ] B4 — Shared quotation items and versions — **next section**.
- [ ] B5 — Manager review, approval & delivery contracts.
- [ ] A1 — Core AI System Prompt and dynamic context.
- [ ] A2 — Requirement extraction & sufficiency.
- [ ] A3 — Clarification suggestions and follow-up analysis.
- [ ] A4 — Quotation change suggestions.
- [ ] A5 — Telegram outbound orchestration.
- [ ] F1 — Business Profile Settings.
- [ ] F2 — Enquiry list & Needs Assignment.
- [ ] F3 — Conversation Room.
- [ ] F4 — Generic Quotation Editor.
- [ ] F5 — Manager Review & Send.
- [ ] T1 — Printing end to end.
- [ ] T2 — Cleaning and Repair compatibility.
- [ ] T3 — Post-send changes.

Current implementation branch: `codex/feat-domain2-v2` (includes B1).
User authorized completing **one whole phase at a time**: finish Backend B2–B5,
updating this checklist after every tested section, then stop and hand off to a
new chat for Phase 2. Do not start Automation/AI or frontend in this chat.
Backend V2 changes remain local and undeployed until explicitly published.

## Goal

Implement an approachable Malaysian SME enquiry-to-quotation workflow, adaptable to Printing, Cleaning and Repair. Retain SME-familiar operations: customer enquiries, staff clarification, manager pricing/approval, quotation PDF delivery. Reuse existing code and UI patterns; do not build unnecessary configuration or collaboration frameworks.

## Mandatory Codex instructions

1. **Inspect the entire existing repository first**, including backend, automation/AI, frontend, data models, existing system prompts, Telegram connector, PDF generation, tests, and documentation. Produce a brief gap analysis: already implemented / partly implemented / missing. Do not assume listed requirements are absent.
2. Implement in this order: **Backend → Automation / AI → Frontend → Integration tests**. Within each phase, work **one section at a time**. Do not jump ahead or make unrelated edits. Preserve existing architectural patterns and migrations.
3. For every section: inspect impacted files, make minimal necessary edits, add or update tests, run relevant tests, review `git diff`, then **commit that section only if tests pass**. If blocked, report the blocker and do not claim success or make a misleading commit. Stage specific paths, not `git add .`.
4. Never commit `.env`, tokens, private data, `.input/`, `.output/`, or generated scratch files. Check `.gitignore` and staged diffs. Do not change the Codex model configuration as part of V2 work.
5. Preserve immutable sent PDFs and their historical metadata, human approval for pricing and sending, and a traceable customer conversation. No AI-initiated customer messages.
6. After each completed section, update this document's implementation checklist and the section's verification record with changed files, exact test commands/results, implementation commit hash and remaining gaps. Report the result after committing. Wait for a user instruction before starting the next section if operating interactively.

## Confirmed V2 business rules

### Business Profiles / tenancy
- Shared **Core AI System Prompt**, dynamically supplied with the active SME Business Profile. Demo profiles: Printing, Cleaning, Repair.
- Profiles configured through Settings; one demo Telegram bot with a **manually selected active profile** for new incoming enquiries. **AI never selects or changes business identity.**
- New enquiries attach to the active profile at intake; existing enquiries retain their original `business_profile_id` even if the demo active profile changes. Validate tenant/business isolation.
- Future dedicated bots per SME are out of V2 scope.

### Telegram / Enquiries
- `/start` and `/help` are commands, not quotation enquiries.
- Associate clear customer follow-up messages with the correct existing enquiry using business identity, Telegram chat, enquiry state, and conversation context. Do not create one enquiry per message.
- Clearly distinct quotation requests create new enquiries; do not merge independent orders automatically.
- Ambiguous association goes to **Needs Assignment**: Staff can assign to an existing enquiry, create a new one, or mark unrelated. AI may resolve unresolved messages if later clarification makes one backend-validated association clear; never override Staff-confirmed assignment. Preserve original messages and assignment history.

### Conversation Room / Staff
- An enquiry links to the relevant customer conversation. Staff can read customer messages and write outgoing Telegram replies.
- AI extracts requirements, flags missing information and suggests clarification questions; Staff may edit and must explicitly send them. **AI cannot send customer messages independently.**
- Customer replies trigger renewed analysis. Keep message attribution and chronology.
- When information needed for an accurate quotation is unclear or missing, **do not generate/send a formal quotation**; Staff asks customer first. Existing sent quotation revisions can be worked on internally but never sent incomplete.

### Quotation
- Generic item fields for all SMEs: `item_name`, `quantity`, `unit`, `unit_price`, computed `amount`, `notes`. Quantity positive; unit e.g. pcs, job, visit, hour. Industry-specific size/material/area/device/service scope goes in **notes** for V2. Use MYR for demo.
- Staff reviews/prepares draft; **Manager owns pricing, final approval and authorization of sending**. AI must not invent/approve prices, fabricate missing specs, or authorize sending.
- Existing Issue Date and **Valid For** fields are reused; derive and display Valid Until consistently. Do not create duplicate validity settings or a new validity engine. Never assume a universal number of days if existing settings differ.
- Keep simple AI Suggested Changes within the quotation review (add item, update item, update field); Staff can review, edit, exclude and apply selected changes. Do not create a separate complex proposal-management UI. Never silently overwrite Staff-edited fields. Preserve original source conversation evidence and an audit trail.
- Sent PDFs are immutable snapshots; post-send changes use a new version or separate quotation. **Hybrid:** clear amendment or explicit request to combine → Revision; explicit independent quotation → Additional; unclear grouping → AI suggests Staff ask customer. Different purposes are only a hint for Additional, never an automatic hard rule.

### Manager single Review & Send
Show on **one final confirmation page** before sending:
- Customer and Business Profile
- All Items with quantity, unit, unit price, amount and notes
- Quotation notes and total (RM)
- Issue Date, existing Valid For, derived Valid Until
- Actual PDF preview for the version about to be sent
- Short Telegram summary preview sourced from approved quotation data (quotation number, concise item summary, total, valid until, prompt to review/respond before expiry)
- `Back to Edit` and Manager-only `Approve & Send`.
- On Manager authorization, deliver PDF **plus** summary. Do not mark Sent if delivery fails; handle ambiguous transport results without duplicating sends. Log sent content/version and preserve PDF and conversation history. The summary cannot have amounts/dates inconsistent with PDF.

## Phase 1 — Backend (finish first)

### B1 — Business Profiles & shared data scope
Review existing tenant/company/business data and Settings APIs. Add only missing profile persistence/read/update needed for Printing, Cleaning, Repair; ensure a newly created enquiry's business identity is pinned and validated. Tests: profile selection, cross-profile isolation, immutable existing enquiry profile. Commit suggestion: `feat(backend): support demo SME business profiles`.

**Completed — 24 October 2026.** Implementation commit: `6b77031` on
`codex/feat-business-profiles`. Added three independent synthetic profiles,
manual active selection, immutable enquiry profile association, scoped
client/quotation/PDF/activity/send access, and additive PostgreSQL upgrade.
Existing settings and historical sent PDFs are preserved.

Verification (temporary databases and mocked providers):

- With `TEST_DATABASE_URL` set to a disposable PostgreSQL database,
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp=.input/b1-full-final-20261024 -p no:cacheprovider`:
  **466 passed, 3 skipped, 1 existing deprecation warning**. The three skips
  were PostgreSQL-only cases under SQLite; all three passed under PostgreSQL.
- `node --test frontend/tests/*.test.mjs`: **24 passed**.
- `node frontend/tests/integration.mjs`: **7 passed**.
- `git diff --check` and staged diff check: passed.

Exact changed files, focused tests and migration details:
[B1 implementation report](BUSINESS_PROFILES.md). Frontend profile selection
remains F1; AI prompt/output changes remain A1 onwards. Live provider checks
and hosted migration/deployment have not been performed for B1.

### B2 — Telegram enquiry routing & assignment
Implement/reuse inbound message persistence, command handling, enquiry association and Needs Assignment actions/history. Tests: `/start`, `/help`, clear follow-up, new distinct order, ambiguous message, later clarification, Staff-confirmed assignment not overwritten, profile switching. Commit: `feat(backend): route telegram messages to enquiries`.

**Completed — 24 October 2026.** Implementation commit `ce5daac`. Commands,
conservative follow-up/new-order routing, validated reply references, Staff
assignment actions/history, profile/chat isolation and restart-safe backfill
implemented. Exact files/commands: [backend phase report](V2_BACKEND_PROGRESS.md).
SQLite regression: **99 passed, 1 skipped**. Focused SQLite + PostgreSQL B2:
**22 passed**. Existing real-API mocked integration: **7 passed**. Diff checks
passed. No live customer messages or deployment. AI reassessment remains A3;
confirmed Staff assignment cannot be overwritten through the backend action.

### B3 — Conversation Room APIs
Support message listing, staff-authored outgoing message actions, message attribution and history. Prevent AI outbound authority. Tests: correct enquiry conversation, role/permission checks, original messages retained, outbound delivery failure recorded. Commit: `feat(backend): support enquiry conversations`.

**Completed — 24 October 2026.** Implementation commit `f5e2f7f`. Chronological
conversation API, explicit Staff text send, original-chat routing, persistent
delivery outcomes and request-id replay protection implemented. SQLite routing/
transport/conversation regression: **45 passed**. Combined conversation and
existing delivery suite with SQLite + PostgreSQL: **107 passed**. Diff checks
passed. Exact files/commands: [backend phase report](V2_BACKEND_PROGRESS.md).
Live providers not called; AI suggestion generation and frontend remain A3/F3.

### B4 — Shared quotation items and versions
Reuse existing Quotation models where possible. Implement generic item fields and notes, draft workflow, selected change application, basic stale-data/atomicity protection, revision vs additional relationship and immutable sent version. Tests: printing/cleaning/repair items, amount totals, incomplete input blocking formal quotation, revision preserves prior PDF, additional independent quotation. Commit: `feat(backend): support generic quotation drafts and revisions`.

### B5 — Manager review, approval & delivery contracts
Enforce Staff/Manager permissions, manager pricing and send authority, reuse current issue date/valid-for calculation and implement preview/send-ready data contracts and PDF snapshot logic. Tests: Staff cannot approve/send, Manager can, expiry consistent, PDF unchanged after send, failures not falsely marked Sent. Commit: `feat(backend): enforce manager quotation approval`.

## Phase 2 — Automation / AI (after Backend)

### A1 — **Review AND edit the Core AI System Prompt** + dynamic context
**Mandatory implementation, not optional.** Locate the existing prompt(s), remove any **hard-coded Printing Shop identity or assumptions**, preserve general instruction and safety constraints, inject the selected backend-validated profile's business details at runtime, and maintain a single SME-agnostic Core Prompt. Demo with Printing, Cleaning and Repair. Never let model output override `business_profile_id`. State in the prompt: AI may classify/extract/suggest but cannot set/approve price, send Telegram customer messages, approve quotations or invent missing information. Adapt the existing structured output minimally to represent extracted item fields/notes, missing information, clarification suggestions and proposed changes. Tests: each profile yields contextual extraction without cross-profile leakage; forbidden actions blocked by backend regardless of prompt. Commit: `feat(ai): use dynamic SME context in core prompt`.

### A2 — Requirement extraction & sufficiency
Extract common item fields and keep industry specifics in notes; identify what needs customer clarification without manufacturing data. Missing critical details → remain in enquiry/Conversation Room; no formal quotation. Tests across 3 profiles. Commit: `feat(ai): extract SME enquiry requirements`.

### A3 — Clarification suggestions and follow-up analysis
Produce editable suggested questions for Staff, handle customer answers and reassess previously ambiguous requirements/assignments through backend validation. No automatic customer reply. Tests: successive 1000→1500 corrections, uncertain values, customer confirmation tied to correct message, unrelated enquiries not mixed. Commit: `feat(ai): suggest enquiry clarifications`.

### A4 — Quotation change suggestions
Support minimal categories `ADD_ITEM`, `UPDATE_ITEM`, `UPDATE_FIELD` for Staff review. Consolidate related messages, avoid duplicate items, never directly update saved quotation or sent PDF, respect Staff edits. Tests: revision and additional intent, ambiguity escalated to Staff, human apply requirement. Commit: `feat(ai): suggest quotation draft changes`.

### A5 — Telegram outbound orchestration
Wire Staff explicitly sent messages and Manager-authorized quotation PDF + deterministic short summary. Verify delivery record, retry safeguards, identical PDF/summary dates and totals. No autonomous AI messaging. Commit: `feat(automation): send approved quotation summaries`.

## Phase 3 — Frontend (after Automation/AI)

### F1 — Business Profile Settings
Reuse existing Settings UI patterns; choose active demo profile and show business context. Do not let AI choose profile. Test UX and switching. Commit: `feat(ui): configure demo SME profiles`.

### F2 — Enquiry list & Needs Assignment
Show association status, Staff resolve options, related message history. Reuse existing components. Commit: `feat(ui): review enquiry assignments`.

### F3 — Conversation Room
Show incoming/outgoing messages, editable AI clarification suggestions and explicit Staff Send. Keep the current enquiry context clear. Commit: `feat(ui): add enquiry conversation room`.

### F4 — Generic Quotation Editor
Item name, quantity, unit, Manager-controlled unit price, amount, notes; Staff reviews AI suggested changes within existing quotation UI. Use existing Dates & Notes / Valid For. No complex separate proposal manager, lock/presence/multiuser editing engine or offline auto-save engine. Commit: `feat(ui): support shared SME quotation items`.

### F5 — Manager Review & Send
Single final page with all confirmed fields, PDF preview, Telegram short summary preview, `Back to Edit` and Manager-only `Approve & Send`; display clear send errors. Commit: `feat(ui): add manager review and send`.

## Phase 4 — Integration tests (after per-section tests)

### T1 — Printing end to end
Incoming Telegram enquiry → AI extraction → Staff clarification in Conversation Room → customer follow-up → generic items → Manager pricing → final preview → Manager approves/sends PDF + summary. Verify message/PDF history and expiry consistency.

### T2 — Cleaning and Repair compatibility
Repeat representative cases using dynamic profiles and item notes. Ensure no Printing-specific behavior leaks.

### T3 — Post-send changes
Clear Revision; explicit Additional; ambiguous grouping asks Staff; historical PDFs untouched. Include negative tests for unauthorized AI send/pricing, wrong business profile, duplicate sends and unknown delivery result. Commit tests in the relevant section or one final tests commit only after passing.

## Explicitly deferred / not to invent
- Customer acceptance and binding confirmed-order processing, quotation expiry/re-quotation workflows beyond display, closed enquiry reopening rules, future production dedicated Telegram bots, advanced per-SME validation rule engines.
- Editing access locks, leases, takeover, real-time presence, Google-Docs-style concurrency, complex field-level conflict merging, elaborate proposal lifecycle/history UI, offline auto-save/retry engines, new validity configuration system.
- Do not silently decide any deferred business policy. Flag implementation blockers clearly; use the smallest safe behavior for the agreed happy path.

## Required final implementation report (from Codex)
For each section provide: status (existing / changed / blocked), exact files, tests executed with pass/fail counts, meaningful risks, commit hash if committed. For the full V2 report the demonstrated E2E path, what was not tested, and remaining gaps. Never report hypothetical tests as passed.
