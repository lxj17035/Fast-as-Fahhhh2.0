# Domain 2 V2 backend phase verification

Branch: `codex/feat-domain2-v2`. User authorized completion of Backend B2–B5,
then a stop and handoff to a new chat for Phase 2. B1 is `6b77031` with its
[separate report](BUSINESS_PROFILES.md). No Replit redeployment is part of this
phase; providers remain mocked in tests.

## B2 — Telegram routing and assignment

Implemented conservative classification in `backend/routing.py`, transactional
receipt/association persistence in `app/database.py` and `app/routing.py`,
Staff-only resolution/history with scope and chat validation, and preservation
of command/unassigned receipts across backfill/restart. Follow-up and reference
messages appear chronologically in enquiry detail and draft source text.

Other changed source: `app/activity.py`, `app/main.py`, `app/telegram.py`,
`app/automatic_drafting.py`, `app/enquiries.py`, `backend/store.py`.
Tests: `tests/test_routing_v2.py`; independent-order fixtures updated in
`tests/test_enquiries.py`, `tests/test_business_profiles.py`,
`frontend/tests/preview_backend.py`. Contract updated in `docs/ENQUIRIES.md`.

SQLite regression command:
`.\.venv\Scripts\python.exe -m pytest -q tests/test_routing_v2.py tests/test_enquiries.py tests/test_telegram_webhook.py tests/test_automatic_drafting.py tests/test_activity.py tests/test_business_profiles.py`
returned **99 passed, 1 skipped**, one existing deprecation warning.

With `TEST_DATABASE_URL` pointing to the disposable localhost PostgreSQL 16 DB:
`.\.venv\Scripts\python.exe -m pytest -q tests/test_routing_v2.py --basetemp=.input/v2-b2-pg -p no:cacheprovider`
returned **22 passed** across SQLite and PostgreSQL. `node
frontend/tests/integration.mjs`: **7 passed**. `git diff --check`: passed.

The classifier only uses explicit independent-order cues, a validated Telegram
reply reference, or a clearly phrased follow-up when one candidate exists.
Ambiguity deliberately requires Staff. AI reassessment is Phase 2 work; this
section provides a validated association action that cannot overwrite confirmed
decisions. No customer text replies are sent by this section.

## B3 — Conversation Room APIs

Added `backend/conversation.py` and `app/conversations.py`. Staff with enabled
demo controls can explicitly POST `{text, request_id}` to
`/api/enquiries/{id}/messages`; GET `/api/enquiries/{id}/conversation` combines
incoming/outgoing records with attribution, timestamps and delivery outcomes.
Recipient is loaded from the original enquiry. Provider calls run outside the
reservation transaction; request replay returns the committed pending/sent/
failed/unknown record without sending again. A failed outcome save retains a
pending hold. Original inbound receipts remain unchanged. Telegram replies to
a Staff message also resolve to its enquiry in the same profile/chat.

Changed files: `app/database.py`, `app/activity.py`, `app/main.py`,
`app/routing.py`, `app/telegram_client.py`, `app/delivery.py`,
`backend/errors.py`, plus the new services and `tests/test_conversations_v2.py`.
The delivery error sanitizer is shared with existing quotation delivery.

- `.\.venv\Scripts\python.exe -m pytest -q tests/test_conversations_v2.py tests/test_routing_v2.py tests/test_telegram_client.py`:
  **45 passed** (isolated SQLite and mocked transports).
- With disposable `TEST_DATABASE_URL`,
  `.\.venv\Scripts\python.exe -m pytest -q tests/test_conversations_v2.py tests/test_delivery.py --basetemp=.input/v2-b3-pg -p no:cacheprovider`:
  **107 passed** across SQLite/PostgreSQL and pure transport checks.
- Diff checks passed; existing Starlette/httpx deprecation warning remains.

No live Telegram request was made. This supplies the backend conversation
contract; frontend composer and AI clarification suggestions remain F3/A3.

## B4 — Shared quotation items and versions

Generic items persist `item_name`, positive/unknown `quantity`, `unit`, nullable
`unit_price`, computed `amount`, and `notes`. Legacy description/unitPrice/
lineTotal aliases remain available while F4 is pending. Conflicting aliases,
computed input amounts and malformed data are rejected. Legacy edits preserve
existing unit/notes when those descriptive fields are omitted.

`QuotationChanges.suggest` stores minimal ADD_ITEM/UPDATE_ITEM/UPDATE_FIELD
suggestions with base version and validated source evidence; it never updates a
draft. GET `/api/quotations/{id}/suggestions` exposes them. Explicit Staff POST
`/api/quotations/{id}/apply-changes` takes `{version, suggestion_set_id,
selected, edits?}`. All selected edits apply atomically to one new saved version;
unselected fields are preserved, stale sets rejected and human-applied content
recorded in the suggestion audit. Prices/profile/recipient/send authority cannot
be proposed or injected through suggestion edits. AI generation remains A4.

New incoming or unassigned messages block refreshing an unsent PDF and approval.
Staff explicitly acknowledges every current incoming ID using
`reviewedMessageIds` in a saved quotation edit. An acknowledged source set must
exactly match the conversation. Unassigned messages must first be assigned/new/
unrelated through B2. Incomplete PDFs are visibly DRAFT QUOTATION; formal sending
remains blocked for missing requirements, blank prices or required fields.

Explicit Staff POST `/api/quotations/{id}/fork` takes `{version, relationship}`
for `revision`, or adds `enquiry_id` for `additional`. Revisions create a new
quotation ID/number linked to the sent original, with prices cleared and review
required. Additional requires a distinct enquiry in the same customer chat and
profile, retaining that independent request's draft. Ambiguous grouping is
rejected for Staff clarification. GET `/api/enquiries/{id}/quotations` lists
history; the existing singular quotation endpoint now selects the latest draft.
The original sent quote JSON and cached PDF are retained byte-for-byte.

Changed files: `backend/quotations.py`, new `backend/quotation_changes.py`,
`backend/store.py`, `backend/drafting.py`, `backend/server.py`, `backend/pdf.py`,
`app/activity.py`, `app/quotation_routes.py`, `app/routing.py`,
`scripts/demo_pdfs.py`, new `tests/test_quotation_v2.py`.
PostgreSQL verification also exposed a pre-existing synthetic enquiry/activity
foreign-key mismatch. `record_quotation_activity` now keeps synthetic activity
in JSON storage and native Telegram activity in its FK-backed table.

Verification:

- SQLite quotation/PDF/drafting/profile regression:
  `.\.venv\Scripts\python.exe -m pytest -q tests/test_quotation_v2.py tests/test_quotations.py tests/test_pdf.py tests/test_drafting.py tests/test_business_profiles.py`:
  **62 passed, 1 skipped** before final extra validation cases.
- Final `tests/test_quotation_v2.py` SQLite run: **15 passed**.
- With disposable `TEST_DATABASE_URL`,
  `.\.venv\Scripts\python.exe -m pytest -q tests/test_quotation_v2.py tests/test_activity.py --basetemp=.input/v2-b4-verified -p no:cacheprovider`:
  **52 passed** including the unassigned-message guard, before extra malformed
  input cases. Initial PostgreSQL run had 3 failures exposing the activity FK
  issue; the rerun passed after the fix.
- `node frontend/tests/integration.mjs`: **7 passed**.
- Final malformed-item/forbidden-suggestion cases with both adapters:
  `.\.venv\Scripts\python.exe -m pytest -q tests/test_quotation_v2.py -k 'invalid_generic or stale_invalid' --basetemp=.input/v2-b4-validation-pg -p no:cacheprovider`:
  **10 passed, 20 deselected**.
- `.\.venv\Scripts\python.exe -m scripts.demo_pdfs` generated 5 synthetic saved
  PDFs. All pages were rendered using `pdftoppm -r 90 -png` into ignored
  `.input/pdf-review-v2-b4/` and visually inspected: three industry samples,
  the CJK client sample, and all 9 pages of the multipage sample. Unit/notes,
  dates/totals, repeated headings, last item/total and footers were legible and
  aligned. Poppler reported its existing STSong font substitution; the inspected
  Chinese client text rendered correctly.
- Diff checks passed. No real providers or hosted migration/deployment tested.

## B5 — Manager review, approval and delivery contracts

`QuotationService.update(..., role=...)` defaults to no pricing authority. Only
PM can change normalized unit prices (including clearing them); Staff can edit
descriptions/quantities while retaining existing prices. Both price aliases are
checked. AI draft creation clears supplied prices independently of provider
validation. Trusted sample/test calls pass `role="pm"` explicitly. HTTP routes
require enabled demo controls and a simulated PM header for pricing.

New `backend/review.py` builds Manager-only final review from one saved version:
customer/company snapshot, items/notes/total, existing issue date/validity/expiry,
actual PDF URL/version/SHA-256 and deterministic Telegram summary preview.
`GET /api/quotations/{id}/review?version=N` is exposed in FastAPI and the
standalone route. Missing fields, blank prices, stale/new/unassigned messages,
expired/future dates and non-PM review are blocked.

`SavedQuotation` adds optional summary/source snapshot fields; the real adapter
fills them from the same saved version before reservation. PostgreSQL upgrade
adds `summary_text` and `source_message_ids` to send attempts without rewriting
old PDF bytes/outcomes. Customer messages arriving during approved upload keep
the enquiry Needs review after document success; approved PDF/summary snapshots
remain unchanged. Incoming routing cannot clear pending/unknown delivery holds.
Draft creation records only the source IDs captured before the provider call;
messages arriving during analysis remain unreviewed and block approval until
Staff reviews them. A faulty provider cannot silently acknowledge new evidence.

**A5 remains required:** the current document transport sends PDF only. This
phase supplies the summary preview/snapshot contract. The current UI still
requires F4/F5 role-aware pricing, explicit message review and the final review
page. No product frontend code was changed, and no full V2 demo is claimed.

Changed production source: `backend/quotations.py`, `backend/quotation_changes.py`,
`backend/server.py`, `backend/routing.py`, `backend/drafting.py`, new `backend/review.py`, `app/main.py`, `app/routing.py`,
`app/quotation_routes.py`, `app/quotation_contract.py`, `app/xinjie_adapter.py`,
`app/database.py`, `app/migrations.py`, `app/enquiries.py`, `app/delivery.py`.
Trusted sample script updated: `scripts/demo_pdfs.py`. Price/action fixtures
updated in `tests/test_api.py`, `tests/test_quotations.py`, `tests/test_pdf.py`,
`tests/test_store.py`, `tests/test_drafting.py`, `tests/test_sending.py`,
`tests/test_xinjie_integration.py`, `tests/test_activity.py`,
`tests/test_shared_quotation_api.py`, `tests/test_quotation_v2.py`, `tests/test_routing_v2.py`,
`tests/test_sweeway_workflow.py`, and
`frontend/tests/integration.mjs`. New cases: `tests/test_manager_review_v2.py`.
Shared contract: `docs/PM_APPROVAL.md` and README setup example.

Checks before final merged suite:

- `.\.venv\Scripts\python.exe -m pytest -q tests/test_api.py tests/test_quotations.py tests/test_pdf.py tests/test_activity.py tests/test_quotation_v2.py tests/test_shared_quotation_api.py tests/test_xinjie_integration.py tests/test_delivery.py tests/test_store.py tests/test_drafting.py tests/test_sending.py`:
  **141 passed, 1 skipped** (SQLite plus pure service tests).
- `.\.venv\Scripts\python.exe -m pytest -q tests/test_manager_review_v2.py`:
  **18 passed, 1 skipped** (PostgreSQL migration skipped on SQLite).
- `node --test frontend/tests/*.test.mjs`: **24 passed**.
- `node frontend/tests/integration.mjs`: **7 passed**, with explicit PM pricing.
- Final reply-reference/Manager SQLite regression:
  `.\.venv\Scripts\python.exe -m pytest -q tests/test_routing_v2.py tests/test_manager_review_v2.py`:
  **31 passed, 1 skipped**. Customer replies to an accepted PDF route through its
  saved provider reference. Unverifiable/cross-profile references remain Needs
  Assignment, with the reference preserved in assignment history for later AI
  evidence validation.
- `.\.venv\Scripts\python.exe -m pytest -q tests/test_sweeway_workflow.py`:
  **5 passed**; manual recovery price corrections explicitly use the PM role.
- `.\.venv\Scripts\python.exe -m pytest -q tests/test_manager_review_v2.py tests/test_drafting.py tests/test_automatic_drafting.py tests/test_sweeway_workflow.py`:
  **41 passed, 1 skipped**, including a customer message arriving during AI
  extraction. The skip is the PostgreSQL migration case under SQLite.

Final merged acceptance, with `TEST_DATABASE_URL` pointing to the disposable
localhost PostgreSQL 16 container (no live/customer database):

- `.\.venv\Scripts\python.exe -m pytest -q --basetemp=.input/v2-backend-phase1-final-source -p no:cacheprovider`:
  **590 passed, 4 skipped, 1 existing Starlette deprecation warning**, in 591.11s.
- All four skips are PostgreSQL-specific checks under SQLite: cross-instance
  advisory locking, legacy delivery schema, legacy profile scope column and
  legacy summary/source snapshot columns. All four PostgreSQL counterparts
  passed in this same run.
- `git diff --check` passed. No real Telegram/AI calls or Replit deployment.

Backend Phase 1 is complete. Stop here and continue A1–A5 in a new chat using
`docs/V2_PHASE_HANDOFF.md`; product frontend and final release acceptance remain.
