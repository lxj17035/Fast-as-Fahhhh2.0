# V2 frontend progress

Branch: `codex/feat-domain2-v2`. Synthetic local QA only; no push/deployment.

## F1 — Business Profile Settings (24 October 2026)

Changed: `frontend/src/api.js`, `frontend/src/app.js`,
`frontend/src/styles.css`, `frontend/tests/api.test.mjs`,
`frontend/tests/integration.mjs`, `docs/FRONTEND.md`, `DESIGN.md`,
`premium-ui.json`, README.md, docs/WORKFLOW.md, docs/BUSINESS_PROFILES.md,
docs/V2_PHASE_HANDOFF.md, and canonical-plan progress.

Explicit Printing/Cleaning/Repair selection, named-profile settings writes,
shared-scope explanation, safe state reset, unsaved cancellation/discard and
visible business context. Existing form/feedback patterns retained. Shared
textareas auto-grow, validation remains server owned, scrollbars have a global
baseline. No backend business logic or PDF template changed.

Verification:
- `node --test frontend/tests/*.test.mjs`: **25 passed**.
- `node frontend/tests/integration.mjs`: **8 passed**, actual API, temporary
  SQLite adapter and mocked AI/Telegram. Switch isolation, invalid selection,
  named settings persistence and original saved PDF bytes verified.
- Local Edge/Playwright browser: switch Printing/Cleaning/Repair, save, preserve
  edits after cancel, discard before switching, restore named settings. Screenshots
  reviewed at 1365x900 and 390x844; no horizontal overflow or page errors.
  Injected rejected save/switch responses also preserve entered values and active
  scope; field errors have accessible descriptions. Dialogs restore prior focus.
  In-app browser failed with `Tab 1 is not part of browser session`; used the
  existing runtime Playwright and installed Edge. No dependency changes.
- `node --check frontend/src/app.js` and `git diff --check`: passed.
- Strict skill audit ran; 3 actionless-button findings are false positives on
  existing delegated `data-action` filter/checklist/remove buttons. Their actual
  handlers are in app.js. No unresolved ownership or other findings. Evidence
  under ignored `.input/v2-f1-audit.json`.
- DESIGN.md lint attempted offline; package unavailable in npm cache. No package
  installed solely for lint. Runtime token mapping manually checked.

Limitations: no PostgreSQL rerun (frontend-only change), live provider call,
Telegram send, hosted verification, full accessibility certification or cross-tab
sync claim. Global selection remains shared; a different browser can change it.
The server still enforces record scope, and named-profile settings saves remain
pinned. F2–F5 and T1–T3 remain separate sections.

Commit checkpoint: **blocked**. `git add` and `git commit` failed because the
session permits read-only `.git` access: `Unable to create .../.git/index.lock:
Permission denied`. No commit hash, push or checkout change. F2–F5 were not edited;
continue with the F1 commit in a Git-writable session before F2, following AGENTS.md.

## F2 � Enquiry list and Needs Assignment

Changed frontend/src/api.js, app.js, styles.css, frontend/tests/api.test.mjs.
Inbox lists unresolved messages, source chat and association history. Explicit
Staff assignment/new/unrelated actions use the existing server scope validation.
Existing enquiry references are pasted from More details; no cross-chat lookup.
Verification: `node --test frontend/tests/*.test.mjs`: 26 passed;
`node frontend/tests/integration.mjs`: 8 passed. Edge browser at 1365x900
and 390x844: empty/list, rejected invalid assignment, unrelated resolution,
no horizontal overflow or page errors. Browser plugin unavailable; bundled
Playwright used. Evidence ignored under .input/v2-f2-*. No backend changes.

## F3 - Conversation Room

Changed frontend/src/api.js, app.js, model.js, styles.css and API/model tests.
Attributed chronological customer, Staff, PDF and summary history, editable
clarification suggestions and explicit human text sends. Analysis is rejected
as current after quote/message/unresolved-assignment/outgoing-evidence changes.
Unknown/pending text outcomes hold sends; no automatic retries.
`node --test frontend/tests/*.test.mjs`: 29 passed;
`node frontend/tests/integration.mjs`: 8 passed. Edge desktop/mobile browser:
conversation attribution, explicit mocked send, renewed analysis, no page errors
or horizontal overflow. Screenshots .input/v2-f3-*. No live providers called.
F2 implementation commit: 520ee21. F1 already committed as 00d6565.

## F4 - Generic quotation editor

Changed frontend/src/api.js, app.js, model.js, styles.css; API fixture, model
tests and integration.mjs. Units, item notes and saved amounts now survive edits.
Staff retains Manager prices; mutations always use the selected human role.
Explicit current-message acknowledgement is included only when checked.
AI change sets are selected/edited/applied within the review, with version and
evidence validation on the server. Sent quotes offer explicit revision/additional
creation (additional requires a distinct same-chat enquiry). Historical PDFs
remain server-owned snapshots.
`node --test frontend/tests/*.test.mjs`: 30 passed;
`node frontend/tests/integration.mjs`: 9 passed, including generic fields, Staff
price rejection, edited selected changes and stale replay rejection. Edge
1365x900/390x844: unit/notes save, Staff readonly prices, editable clarification,
selected edited change apply, Manager pricing, no overflow/page errors. Initial
browser run caught suggestion refresh gap; fixed and the same script passed.
No PDF template or backend source changed. F3 commit: 4355e3c.
