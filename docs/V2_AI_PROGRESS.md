# Domain 2 V2 Phase 2 verification

Branch: `codex/feat-domain2-v2`. Complete A1-A5, then stop before frontend.
All automated tests use mocked providers and disposable storage. PostgreSQL 16
is localhost-only on port 55439; no runtime/customer database is used.

## A1 — Core prompt and dynamic context

Status: changed and tested. Implementation commit: `dc2a39c`.

Changed `backend/drafting.py`, added `tests/test_ai_v2.py`. Shared SME-agnostic
prompt explicitly forbids pricing/approval/send/recipient/profile authority.
Both adapters receive pinned validated profile identity, industry, company and
client. Schema includes generic unit/notes; legacy extraction remains readable.
Unknown unit uses the neutral `unit` placeholder, never an inferred industry unit.

With disposable `TEST_DATABASE_URL`:
`.\.venv\Scripts\python.exe -m pytest -q tests/test_ai_v2.py tests/test_drafting.py tests/test_runpod.py --basetemp=.input/v2-a1-schema -p no:cacheprovider`:
**51 passed**, existing Starlette deprecation warning. `git diff --check` passed.
Initial tests ran during an external checkout to main and failed for missing
Phase 1 APIs; user authorized restoration, and the final run used the V2 branch.
No live inference. Sufficiency, clarification and change generation remain A2-A4.

## A2 — Requirements and sufficiency

Status: changed and tested. Implementation commit: `33f7ecf`.

Changed `backend/drafting.py`, `tests/test_ai_v2.py`. Shared prompt covers stated
units, industry notes and critical scope uncertainty. Server independently flags
empty items, unknown quantities and neutral/unknown units even if the model omits
them. Existing validation blocks formal review/send and labels incomplete PDFs
as drafts. No template changes. Unknowns/prices stay blank; no industry defaults.

With disposable `TEST_DATABASE_URL`:
`.\.venv\Scripts\python.exe -m pytest -q tests/test_ai_v2.py tests/test_drafting.py tests/test_runpod.py tests/test_quotation_v2.py --basetemp=.input/v2-a2 -p no:cacheprovider`:
**88 passed**, existing warning. Three profiles tested with notes and unknowns.
Industry scope sufficiency still depends on model flags plus explicit Staff review;
no new per-industry rules engine. No live provider check in this section.

## A3 — Clarification and renewed analysis

Status: changed and tested. Implementation commit: `3ca6165`.

Changed `backend/drafting.py`, new `backend/analysis.py`, `app/routing.py`,
`app/automatic_drafting.py`, `app/telegram.py`, `app/quotation_routes.py`,
`tests/test_ai_v2.py`. Contract: `docs/AI_ANALYSIS.md`.
Initial and renewed snapshots retain source evidence and editable questions.
Customer follow-ups trigger analysis; existing Staff edits remain untouched.
Unchanged completed analysis is reused; duplicates do not consume another call.
Provider-time races are stale and never acknowledge new messages. AI association
requires an actual later customer reply, exact unresolved-message reference and
explicit enquiry/quote reference; arbitrary claims and confirmed decisions block.

With disposable `TEST_DATABASE_URL`:
`.\.venv\Scripts\python.exe -m pytest -q tests/test_ai_v2.py tests/test_drafting.py tests/test_runpod.py tests/test_routing_v2.py tests/test_automatic_drafting.py --basetemp=.input/v2-a3-verified -p no:cacheprovider`:
**96 passed**, existing warning; diff checks passed. Earlier runs exposed duplicate
analysis and synthetic fixture/manual-cache issues; corrected before this rerun.
No customer send or quotation overwrite. Conservative assignment needs Staff to
associate a confirmation first; vague evidence stays Needs Assignment. UI is F3.

## A4 — Quotation change suggestions

Status: changed and tested. Implementation commit: `c3702bd`.

Changed `backend/drafting.py`, `backend/analysis.py`, new `backend/ai_changes.py`,
`tests/test_ai_v2.py`. Schema adds ADD_ITEM/UPDATE_ITEM/UPDATE_FIELD and advisory
relationshipIntent. Backend validates allowed fields, de-duplicates additions,
rejects invalid item indices/authority, drops conflicting updates for clarification,
and stores existing version-bound suggestion sets. Only explicit human selection
applies them; Staff prices/notes are preserved. Sent quotes require an explicit
fork before changes can be proposed against an editable draft.

With disposable `TEST_DATABASE_URL`:
`.\.venv\Scripts\python.exe -m pytest -q tests/test_ai_v2.py tests/test_quotation_v2.py tests/test_drafting.py tests/test_runpod.py --basetemp=.input/v2-a4 -p no:cacheprovider`:
**106 passed**, existing warning; diff checks passed. Includes revision/additional/
unclear intent, duplicate suppression, human apply, authority rejection, immutable
sent content and the existing revision/PDF tests. No inference creates a fork.

## A5 - Outbound orchestration (changed, tested)

Status: changed and tested. Implementation commit: `7f28fe7`.

Changed production source: `app/activity.py`, `app/database.py`, `app/delivery.py`,
`app/enquiries.py`, `app/migrations.py`, `app/quotation_contract.py`,
`app/routing.py`, `app/xinjie_adapter.py`, `backend/conversation.py`,
`backend/quotations.py`, `backend/pdf.py`, `backend/review.py`. Test/mock adaptations: `tests/test_activity.py`,
`tests/test_delivery.py`, `tests/test_sweeway_workflow.py`,
`tests/test_xinjie_integration.py`, `frontend/tests/preview_backend.py`.
New coverage: `tests/test_outbound_v2.py`. Contracts: `docs/PM_APPROVAL.md`,
`docs/DELIVERY.md`, README.

Staff explicit sends reuse B3. Manager approvals now deliver PDF and saved
deterministic summary without inference. Persisted component outcomes and provider
references distinguish PDF acceptance from summary acceptance. A confirmed summary
failure freezes the approved content and only retries that exact summary after
fresh Manager approval; never reuploads the accepted PDF. Pending/unknown outcomes
or failed persistence retain a hold. Conversation includes quotation delivery;
replies to either accepted component retain enquiry/profile/chat association.
PostgreSQL upgrade adds nullable metadata without inventing legacy outcomes.

Component run with disposable `TEST_DATABASE_URL`:
`.\.venv\Scripts\python.exe -m pytest -q tests/test_outbound_v2.py --basetemp=.input/v2-a5-component-events -p no:cacheprovider`:
**15 passed, 1 skipped**, existing warning. The skip is PostgreSQL migration under
SQLite; PostgreSQL counterpart passed. Initial runs exposed unsupported new
activity action names; added the explicit action allowlist and reran successfully.

Frontend `node --test frontend/tests/*.test.mjs`: **24 passed**;
`node frontend/tests/integration.mjs`: **7 passed**. Providers mocked throughout.
No PDF layout/template changed. Real saved-version bytes/hash and PDF text are
compared with summary dates/totals by the component tests. Live Telegram and
Replit verification remain pending. Legacy standalone SendService is retained as
its existing test/service contract; the actual `backend.server` entry starts the
shared FastAPI application and component-aware delivery route.

Final merged regression with disposable `TEST_DATABASE_URL`:
`.\.venv\Scripts\python.exe -m pytest -q --basetemp=.input/v2-phase2-full -p no:cacheprovider`:
**640 passed, 5 skipped, 1 existing deprecation warning**, 589.33s.
All five skips are PostgreSQL-only checks under SQLite; their PostgreSQL cases
passed. This run preceded the final frozen-preview/review recovery adjustment.
After that adjustment, final focused PDF/review/component run:
`.\.venv\Scripts\python.exe -m pytest -q tests/test_pdf.py tests/test_outbound_v2.py tests/test_manager_review_v2.py --basetemp=.input/v2-a5-final-review -p no:cacheprovider`:
**67 passed, 2 skipped**, existing warning. Both skipped migration checks passed
on PostgreSQL. This includes the two added edge cases (4 adapter cases), separately
also **4 passed, 16 deselected** with `-k 'replies_to_reused or summary_acceptance_save'`
and `--basetemp=.input/v2-a5-final-edges`. `git diff --check` passed.

Limitations: live Telegram/hosted V2 are not verified. Crashes or unknown results
require manual verification, never blind retries. An expired partial delivery
cannot be retried. Frontend F1-F5 and release T1-T3/RP2 remain for later chats.

## RP1 - Separate live verification

Exactly one request passed on 24 October 2026 at 12:30 Malaysia / 04:30 UTC.
Runpod glm-5.3 returned HTTP 200, request ID and token counts: 1,180 input,
182 output, 1,362 total. Configured cap 1,024 output tokens; no retry. Fictional
Cleaning input and backend-validated profile used isolated disposable PostgreSQL;
no Telegram or runtime/hosted database. Full sanitized output and endpoint:
[V2_RUNPOD_RP1.md](V2_RUNPOD_RP1.md). No billing evidence was retrieved.

The model conservatively returned an unknown unit despite stated visits, and
included unagreed pricing among missing information. Staff must review the unit
and dismiss/resolve the pricing flag through Manager pricing, not ask AI to price.
This is validated safe extraction, not proof that all inferred fields are perfect.
No extra live call was made to improve the result. RP2 and live Telegram remain.

Phase 2 complete. Phase 3 product UI and Phase 4 full V2/hosted journeys are not
implemented or demonstrated here. No V2 deployment/push or video recording.
