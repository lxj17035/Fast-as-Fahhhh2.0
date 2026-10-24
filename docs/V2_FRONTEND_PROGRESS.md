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

Commit checkpoint superseded: F1 was committed as `00d6565` before this chat.

## F2 — Enquiry list and Needs Assignment

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

## F5 - Manager Review & Send

Changed frontend/src/api.js, app.js, styles.css, frontend/tests/api.test.mjs,
frontend/tests/integration.mjs and preview_backend.py. One final page shows
saved customer/profile/items/notes/total/dates, actual PDF and deterministic
Telegram summary. Its PDF SHA-256 is compared with the loaded bytes before
approval. Manager approves the exact version; confirmed failures require fresh
approval and the exact retry ID. Partial summary failure freezes the accepted
PDF, explains Back to Edit, and offers summary-only approval. Delivery history
shows separate PDF/summary outcomes; missing legacy component data is labelled.
Message holds persist across reloads; invalid assignment and suggestion edits
survive error rendering. Staff/Manager labels retain server sales/pm values.
Shared panel spacing, wrapping preview actions and responsive PDF scaling fixed.
No backend business logic or PDF template changed.

Final verification (24 October 2026):
- `node --test frontend/tests/*.test.mjs`: **31 passed**.
- `node frontend/tests/integration.mjs`: **10 passed** against actual FastAPI,
  temporary SQLite and mocked AI/Telegram. Adds generic fields, price authority,
  selected edited AI changes, stale replay, Manager review/PDF/summary agreement.
- `.venv/Scripts/python.exe -m pytest -q --basetemp=.input/v2-phase3-full -p no:cacheprovider`
  with TEST_DATABASE_URL pointing to a new disposable localhost PostgreSQL 16:
  **644 passed, 5 skipped, 1 existing Starlette deprecation warning**, 665.87s.
  Five skips are PostgreSQL-only tests under SQLite; PostgreSQL counterparts ran.
- Edge/Playwright 1365x900 and 390x844: saved final PDF/summary, Back to Edit,
  explicit rejection, fresh approval retry, sent lock and component history.
  Separate actual-API mocked partial-summary scenario passed: accepted PDF frozen,
  Back to Edit protected, only summary retried. No page errors or page overflow.
  Desktop and mobile screenshots inspected. A native select retains platform
  ownership. Earlier QA exposed refresh/encoding/wrapping issues; fixed and rerun.
- `node --check frontend/src/app.js`, `git diff --check`: passed.
- Strict premium UI audit: encoding issue fixed; three remaining actionless-button
  reports are false positives on delegated filter/remove/dismiss buttons, which
  have actual data-action handlers. No unresolved ownership findings. Static JSON
  under ignored `.input/v2-phase3-audit.json`. DESIGN.md token mapping unchanged;
  no configured formatter/typecheck/build step (plain ES modules, no build).

Existing screen patterns and simulated permissions are retained. All external
providers are mocked here. No live Telegram, hosted Runpod/RP2, deployment,
production identity, full accessibility certification or cross-browser claim.
T1-T3/RP2 remain Phase 4. F4 commit: `6d2d26b`.
