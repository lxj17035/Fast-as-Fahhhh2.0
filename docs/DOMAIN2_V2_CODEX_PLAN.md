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
- [x] B4 — Shared quotation items and versions — `5dbac4b`; verification below.
- [x] B5 — Manager review, approval & delivery contracts — `734d232`; verification below.
- [x] A1 - Core AI System Prompt and dynamic context - `dc2a39c`; 51 passed; [report](V2_AI_PROGRESS.md).
- [x] A2 - Requirement extraction and sufficiency - `33f7ecf`; 88 passed; [report](V2_AI_PROGRESS.md).
- [x] A3 - Clarification suggestions and follow-up analysis - `3ca6165`; 96 passed; [report](V2_AI_PROGRESS.md).
- [x] A4 - Quotation change suggestions - `c3702bd`; 106 passed; [report](V2_AI_PROGRESS.md).
- [x] A5 - Telegram outbound orchestration - `7f28fe7`; full 640 passed; final focused 67 passed; [report](V2_AI_PROGRESS.md).
- [x] F1 — Business Profile Settings - `00d6565`; [verification](V2_FRONTEND_PROGRESS.md).
- [x] F2 — Enquiry list & Needs Assignment - `520ee21`; [verification](V2_FRONTEND_PROGRESS.md).
- [x] F3 — Conversation Room - `4355e3c`; [verification](V2_FRONTEND_PROGRESS.md).
- [x] F4 — Generic Quotation Editor - `6d2d26b`; [verification](V2_FRONTEND_PROGRESS.md).
- [x] F5 — Manager Review & Send - `9fef80d`; [verification](V2_FRONTEND_PROGRESS.md).
- [x] T1 — Printing end to end; SQLite/PostgreSQL + actual desktop/mobile UI, [evidence](V2_INTEGRATION_PROGRESS.md).
- [ ] T2 — Cleaning and Repair compatibility.
- [ ] T3 — Post-send changes.
- [x] RP1 - One bounded live V2 Runpod check: HTTP 200; 1,362 tokens; [sanitized evidence](V2_RUNPOD_RP1.md).
- [ ] RP2 — Release/T1: verify the published Replit app actually calls Runpod and capture submission proof.

Current implementation branch: `codex/feat-domain2-v2` (includes B1).
User authorized completing **one whole phase per chat**, testing and committing
one section at a time. Phases 1 and 2 (A1-A5) are complete and committed.
Phase 3 F1-F5 is complete; next chat is Phase 4 T1-T3/RP2. Completed phases must be pushed to origin
and origin/main under the phase-end rule below; deployment is verified separately.
Use [the handoff](V2_PHASE_HANDOFF.md) and [Phase 2 evidence](V2_AI_PROGRESS.md).

## Goal

Implement an approachable Malaysian SME enquiry-to-quotation workflow, adaptable to Printing, Cleaning and Repair. Retain SME-familiar operations: customer enquiries, staff clarification, manager pricing/approval, quotation PDF delivery. Reuse existing code and UI patterns; do not build unnecessary configuration or collaboration frameworks.

## Mandatory Codex instructions

1. **Inspect the entire existing repository first**, including backend, automation/AI, frontend, data models, existing system prompts, Telegram connector, PDF generation, tests, and documentation. Produce a brief gap analysis: already implemented / partly implemented / missing. Do not assume listed requirements are absent.
2. Implement in this order: **Backend → Automation / AI → Frontend → Integration tests**. Within each phase, work **one section at a time**. Do not jump ahead or make unrelated edits. Preserve existing architectural patterns and migrations.
3. For every section: inspect impacted files, make minimal necessary edits, add or update tests, run relevant tests, review `git diff`, then **commit that section only if tests pass**. If blocked, report the blocker and do not claim success or make a misleading commit. Stage specific paths, not `git add .`.
4. Never commit `.env`, tokens, private data, `.input/`, `.output/`, or generated scratch files. Check `.gitignore` and staged diffs. Do not change the Codex model configuration as part of V2 work.
5. Preserve immutable sent PDFs and their historical metadata, human approval for pricing and sending, and a traceable customer conversation. No AI-initiated customer messages.
6. After each completed section, update this document's implementation checklist and the section's verification record with changed files, exact test commands/results, implementation commit hash and remaining gaps. Report the result after committing. The user authorized one whole phase per chat: continue its sections in order, then stop at the phase boundary and provide a written handoff for a new chat.


7. **At the end of every completed phase, push the tested section commits and updated plan/handoff to `origin` on the working branch, and integrate/push the completed phase to `origin/main` before stopping.** This is standing user authorization; do not ask again for routine phase-end pushes. Fetch first, preserve remote changes, use a fast-forward when possible or a normal merge when needed, and never force-push or overwrite unrelated work. Resolve and verify any integration changes before pushing. Verify both remote refs contain the completed phase and report their commit IDs. If branch protection, authentication or another actual blocker prevents publication, report it explicitly rather than calling the push complete. A Git push is not evidence of successful deployment; verify the hosted app separately.

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

**Completed — 24 October 2026.** Implementation commit `5dbac4b`. Generic
items/notes/units, version-bound human-selected changes and audit, explicit
revision/additional relationships, preserved historical PDFs, and stale/unassigned
customer-message guards implemented. Incomplete previews are clearly labelled
drafts. SQLite regression: **62 passed, 1 skipped**; final B4 SQLite **15 passed**.
Quotation/activity SQLite + PostgreSQL rerun: **52 passed**; final malformed-input
subset **10 passed, 20 deselected**. Existing mocked real-API integration:
**7 passed**. Five saved-version PDF samples rendered and visually reviewed,
including all nine multipage pages. A PostgreSQL synthetic-activity FK issue
found during verification was fixed. Exact files/commands and limitations:
[backend phase report](V2_BACKEND_PROGRESS.md). AI generation/UI remain A4/F4.

### B5 — Manager review, approval & delivery contracts
Enforce Staff/Manager permissions, manager pricing and send authority, reuse current issue date/valid-for calculation and implement preview/send-ready data contracts and PDF snapshot logic. Tests: Staff cannot approve/send, Manager can, expiry consistent, PDF unchanged after send, failures not falsely marked Sent. Commit: `feat(backend): enforce manager quotation approval`.

**Completed — 24 October 2026.** Implementation commit `734d232`. Enforced
Manager-only pricing, rejected provider-supplied prices, added version-bound
final review with actual PDF/hash and deterministic summary, and saved approved
summary/source snapshots. Messages arriving during AI analysis or delivery
remain subject to fresh review; immutable sent PDFs and unknown-result holds
are preserved. Full merged SQLite + disposable PostgreSQL regression:
**590 passed, 4 skipped, 1 existing deprecation warning**. The four skips are
PostgreSQL-only cases under SQLite; their PostgreSQL counterparts all passed.
Frontend unit tests **24 passed**; mocked API integration **7 passed**. Exact
commands/files and focused checks: [backend phase report](V2_BACKEND_PROGRESS.md).
Actual PDF-plus-summary transport is A5; product UI is F1–F5. No live-provider
check, V2 push or deployment was performed. Stop here for a new Phase 2 chat.

## Phase 2 — Automation / AI (after Backend)

### Runpod usage and verification checkpoints

Runpod is the selected AI provider. The call path is
`backend/drafting.py` provider selection → `backend/runpod.py` → configured
Runpod GLM-5.3 Public Endpoint. Local configuration is not proof that Replit
Secrets or the published deployment use the same provider.

- **A1:** adapt the shared prompt/schema and pass backend-validated business
  context through the Runpod adapter.
- **A2:** Runpod extracts enquiry requirements/items and missing information.
- **A3:** use Runpod for clarification suggestions and renewed analysis of
  customer replies, subject to backend evidence/assignment validation.
- **A4:** use Runpod for proposed quotation changes; Staff applies selections.
- **A5:** outbound Telegram orchestration is not a Runpod inference step.
  Build the approved short summary deterministically from saved quotation data;
  no extra model call is needed to price, approve, render a PDF or send it.

**RP1, before the Phase 2 handoff:** after mocked tests pass, perform a separately
identified, bounded live Runpod check with fictional input and isolated test
storage. Start with one request and the configured token cap; no automatic retry
or repeated calls merely to make the balance decrease. Record UTC/Malaysia time,
provider/model, safe endpoint identity, HTTP result, provider request ID and token
usage if supplied, plus validated extraction output. Clearly distinguish absent
metadata from captured evidence. Save a sanitized verification report in `docs/`;
keep disposable/raw intermediates ignored. If credentials/network/access are
unavailable, leave RP1 unchecked and report the blocker. Mocked tests, a local
request counter, key "Used" date and configuration readiness do not prove a
successful live inference. Existing 23 October success is historical only; it
does not verify the changed V2 prompt or published application.

**RP2, release/T1 after the frontend is ready:** verify Replit's selected provider
without exposing secrets, then use a fresh fictional enquiry in a team-controlled
Telegram chat to demonstrate the published app's Runpod extraction. Existing
saved drafts may be reused without a new model request. Capture matching app
output and sanitized provider evidence; include account usage/billing evidence
where available. Check the actual event submission requirements: shared Public
Endpoint code alone does not establish a team-owned Serverless deployment.
Do not promise that a tiny call will visibly change a rounded credit balance.
Mark RP2 complete only after actual hosted verification, before recording the
final demo. Never put API keys, Authorization headers or private chat data into
the report, screenshots or video. No live call is performed by this plan update.

### A1 — **Review AND edit the Core AI System Prompt** + dynamic context

**Completed - 24 October 2026.** Implementation `dc2a39c`; 51 mocked SQLite/PostgreSQL checks passed. Exact files, command and limits: [Phase 2 verification](V2_AI_PROGRESS.md).
**Mandatory implementation, not optional.** Locate the existing prompt(s), remove any **hard-coded Printing Shop identity or assumptions**, preserve general instruction and safety constraints, inject the selected backend-validated profile's business details at runtime, and maintain a single SME-agnostic Core Prompt. Demo with Printing, Cleaning and Repair. Never let model output override `business_profile_id`. State in the prompt: AI may classify/extract/suggest but cannot set/approve price, send Telegram customer messages, approve quotations or invent missing information. Adapt the existing structured output minimally to represent extracted item fields/notes, missing information, clarification suggestions and proposed changes. Tests: each profile yields contextual extraction without cross-profile leakage; forbidden actions blocked by backend regardless of prompt. Commit: `feat(ai): use dynamic SME context in core prompt`.

### A2 — Requirement extraction & sufficiency

**Completed - 24 October 2026.** Implementation `33f7ecf`; 88 mocked SQLite/PostgreSQL checks passed. Exact files, command and limits: [Phase 2 verification](V2_AI_PROGRESS.md).
Extract common item fields and keep industry specifics in notes; identify what needs customer clarification without manufacturing data. Missing critical details → remain in enquiry/Conversation Room; no formal quotation. Tests across 3 profiles. Commit: `feat(ai): extract SME enquiry requirements`.

### A3 — Clarification suggestions and follow-up analysis

**Completed - 24 October 2026.** Implementation `3ca6165`; 96 mocked SQLite/PostgreSQL checks passed. Exact files, command and limits: [Phase 2 verification](V2_AI_PROGRESS.md).
Produce editable suggested questions for Staff, handle customer answers and reassess previously ambiguous requirements/assignments through backend validation. No automatic customer reply. Tests: successive 1000→1500 corrections, uncertain values, customer confirmation tied to correct message, unrelated enquiries not mixed. Commit: `feat(ai): suggest enquiry clarifications`.

### A4 — Quotation change suggestions

**Completed - 24 October 2026.** Implementation `c3702bd`; 106 mocked SQLite/PostgreSQL checks passed. Exact files, command and limits: [Phase 2 verification](V2_AI_PROGRESS.md).
Support minimal categories `ADD_ITEM`, `UPDATE_ITEM`, `UPDATE_FIELD` for Staff review. Consolidate related messages, avoid duplicate items, never directly update saved quotation or sent PDF, respect Staff edits. Tests: revision and additional intent, ambiguity escalated to Staff, human apply requirement. Commit: `feat(ai): suggest quotation draft changes`.

### A5 — Telegram outbound orchestration

**Completed - 24 October 2026.** Implementation `7f28fe7`. Full merged suite: 640 passed, 5 PostgreSQL-only skips under SQLite. Final frozen-preview/review recovery checks: 67 passed, 2 skips; PostgreSQL counterparts passed. Frontend 24 + mocked integration 7 passed. Exact files/commands and limitations: [Phase 2 report](V2_AI_PROGRESS.md).
Wire Staff explicitly sent messages and Manager-authorized quotation PDF + deterministic short summary. Verify delivery record, retry safeguards, identical PDF/summary dates and totals. No autonomous AI messaging. Commit: `feat(automation): send approved quotation summaries`.

## Phase 3 — Frontend (after Automation/AI)

### F1 — Business Profile Settings

**Completed - 24 October 2026.** Commit `00d6565`; 25 frontend and 8 isolated API checks. [Frontend verification](V2_FRONTEND_PROGRESS.md).

Reuse existing Settings UI patterns; choose active demo profile and show business context. Do not let AI choose profile. Test UX and switching. Commit: `feat(ui): configure demo SME profiles`.

### F2 — Enquiry list & Needs Assignment

**Completed - 24 October 2026.** Section tests and browser checks passed. Exact files, counts and commits: [frontend verification](V2_FRONTEND_PROGRESS.md).
Show association status, Staff resolve options, related message history. Reuse existing components. Commit: `feat(ui): review enquiry assignments`.

### F3 — Conversation Room

**Completed - 24 October 2026.** Section tests and browser checks passed. Exact files, counts and commits: [frontend verification](V2_FRONTEND_PROGRESS.md).
Show incoming/outgoing messages, editable AI clarification suggestions and explicit Staff Send. Keep the current enquiry context clear. Commit: `feat(ui): add enquiry conversation room`.

### F4 — Generic Quotation Editor

**Completed - 24 October 2026.** Section tests and browser checks passed. Exact files, counts and commits: [frontend verification](V2_FRONTEND_PROGRESS.md).
Item name, quantity, unit, Manager-controlled unit price, amount, notes; Staff reviews AI suggested changes within existing quotation UI. Use existing Dates & Notes / Valid For. No complex separate proposal manager, lock/presence/multiuser editing engine or offline auto-save engine. Commit: `feat(ui): support shared SME quotation items`.

### F5 — Manager Review & Send

**Completed - 24 October 2026.** Section tests and browser checks passed. Exact files, counts and commits: [frontend verification](V2_FRONTEND_PROGRESS.md).
Single final page with all confirmed fields, PDF preview, Telegram short summary preview, `Back to Edit` and Manager-only `Approve & Send`; display clear send errors. Commit: `feat(ui): add manager review and send`.

## Phase 4 — Integration tests (after per-section tests)

### T1 — Printing end to end
Incoming Telegram enquiry → AI extraction → Staff clarification in Conversation Room → customer follow-up → generic items → Manager pricing → final preview → Manager approves/sends PDF + summary. Verify message/PDF history and expiry consistency.

**Completed locally — 24 October 2026.** Two SQLite/PostgreSQL acceptance cases
and one complete actual UI journey passed on desktop/mobile with mocked Runpod
HTTP/Telegram. Exact files/commands/limits: [Phase 4 report](V2_INTEGRATION_PROGRESS.md).
Hosted/live RP2 remains separate and blocked on the published V2 build/evidence.

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


## Phase 2 completion checkpoint

A1-A5 committed separately after section tests; stop before F1-F5. Full source
files, commands/counts and risks: [Phase 2 report](V2_AI_PROGRESS.md).
RP1 used exactly one live synthetic Runpod request at 12:30 Malaysia time on
24 October 2026, HTTP 200, provider request ID and token usage captured. It
verified the changed core prompt/schema and pinned Cleaning context, with
blank prices. This does not verify Telegram, Replit or billing balance. RP2
remains unchecked. Continue Phase 3 in a new chat with [handoff](V2_PHASE_HANDOFF.md).
