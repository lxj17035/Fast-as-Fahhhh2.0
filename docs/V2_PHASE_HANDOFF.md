# Domain 2 V2 — phase handoff

Updated 24 October 2026, Asia/Kuala_Lumpur.
Working branch: `codex/feat-domain2-v2` in the existing repository.

## User goal and working agreement

Finish the complete V2 plan, successfully redeploy on Replit, and record a demo
video. The target is 2 PM on 24 October 2026; it is a target, not a guarantee.
Work **one whole phase per chat**, testing and committing one section at a time.
After each tested section update `docs/DOMAIN2_V2_CODEX_PLAN.md` with the checkbox,
implementation commit and actual evidence. At phase end, stop and hand off to a
new chat. Do not silently start the next phase or report untested work complete.

Read `AGENTS.md`, README, `docs/WORKFLOW.md`, the canonical V2 plan and
`docs/V2_BACKEND_PROGRESS.md`. The plan in `docs/` is the tracked continuation
source; do not depend on the original Downloads file or old chat history.

## Current phase checkpoint

Backend Phase 1 B1–B5 is complete, committed and checked off. This chat stops
here. Continue Phase 2 only in the next chat.

- B1 `6b77031`: three profiles, manual active selection, immutable enquiry scope.
- B2 `ce5daac`: command exclusion, conservative association, Needs Assignment.
- B3 `f5e2f7f`: explicit Staff conversation send and persistent delivery history.
- B4 `5dbac4b`: generic items, selected changes, source guards, revisions/history.
- B5 `734d232`: Manager pricing and saved-version review/PDF/summary contracts.

Final acceptance: with `TEST_DATABASE_URL` set to a disposable localhost
PostgreSQL 16 instance,
`.\.venv\Scripts\python.exe -m pytest -q --basetemp=.input/v2-backend-phase1-final-source -p no:cacheprovider`
completed **590 passed, 4 skipped, 1 existing Starlette deprecation warning**
in 591.11s. Four PostgreSQL-only checks skip under SQLite; all PostgreSQL
counterparts passed (advisory locking and three legacy schema upgrades).
Frontend `node --test frontend/tests/*.test.mjs`: **24 passed**;
`node frontend/tests/integration.mjs`: **7 passed**. Providers were mocked.
The disposable test container was stopped/removed. PDF visual review and
per-section commands/files are in `docs/V2_BACKEND_PROGRESS.md`.

Changes are local. No V2 push, Replit publication or live provider check has
been performed. The already-published Basic Auth removal is separate. Keep the
anonymous synthetic preview arrangement; login is deferred until initial
screening succeeds. Do not add production identity/tenancy/queues/channels.

## Next chat: Phase 2 A1–A5 only

Runpod verification is explicitly required: see the plan's "Runpod usage and
verification checkpoints". A1 connects dynamic context to its adapter; A2–A4
use it for extraction, clarification and change suggestions. A5 sends approved
data with a deterministic summary and needs no extra inference. At Phase 2 end,
RP1 performs a bounded synthetic live check with a sanitized evidence report,
separate from mocked tests. RP2 verifies the actual published Replit → Runpod
path during release/T1 and captures submission proof. Both remain unchecked.
The 23 October live success is historical, not proof of V2 or hosted usage.

- Core prompt/schema live in `backend/drafting.py`; Runpod reuses them through
  `backend/runpod.py`. A1 must actually edit the core prompt/schema, inject the
  pinned backend-validated profile, and cover Printing/Cleaning/Repair.
- The current extractor still has the original small output schema. Clarification,
  industry notes/units, sufficiency and suggestion generation are not finished.
  `DraftService.create` returns an existing latest quote without overwriting
  Staff work. Add renewed analysis as suggestions, not silent quotation updates.
- `QuotationService.create` independently clears all provider prices. Unit-price
  changes require explicit `role="pm"` in the business service and the enabled
  simulated PM header at HTTP boundaries. No AI price/recipient/send authority.
- Intake uses `message_links` plus immutable `telegram_updates`. Classifier is
  conservative and deterministic; ambiguous messages remain Needs Assignment.
  `assign_message` validates same profile/chat and refuses already-resolved
  records, including Staff decisions. AI reassignment of unresolved messages
  still needs explicit backend-validated clarification evidence in A3; do not
  let an arbitrary model-chosen ID become sufficient evidence. Preserve reply
  references needed for later reassessment rather than relying on model claims.
- Conversation GET `/api/enquiries/{id}/conversation` has attributed incoming/
  outgoing history. Explicit Staff POST `/api/enquiries/{id}/messages` requires
  `{text, request_id}` and never accepts a recipient. Stable request UUIDs block
  replays, including pending/unknown. Text transport is `TelegramSender.send_text`.
  For AI context on a pinned old profile, avoid incorrectly using the current
  active-profile HTTP scope after a profile switch; use validated internal data.
- `QuotationChanges.suggest` stores ADD_ITEM/UPDATE_ITEM/UPDATE_FIELD sets with
  source evidence and base version. Human-selected/edited application is already
  atomic and audited. No prices/profile/recipient fields are accepted. Use this
  small mechanism for A4 rather than a proposal-management framework.
- `reviewedMessageIds` is the exact chronological incoming ID list acknowledged
  by Staff. New or unassigned same-chat messages block unsent PDF/review/send.
  `DraftService` passes the IDs captured before extraction into quotation
  creation; preserve this boundary when adding renewed analysis. Messages
  arriving during the provider call must remain unreviewed.
  Staff edits are never silently overwritten. Incomplete PDF previews say DRAFT;
  formal review/send are blocked. Historical sent PDFs remain accessible.
- Fork endpoint creates explicit revision/additional relationships. Revisions
  have a new quote ID/number, blank prices and required review; Additional uses
  a distinct enquiry in the same profile/customer chat. Ambiguous grouping asks
  Staff/customer. The singular quotation endpoint returns the latest quote.
- `ReviewService` returns one saved quotation, actual PDF URL/version/SHA-256
  and deterministic summary. `SavedQuotation.telegram_summary` and
  `source_message_ids` are frozen into `send_attempts` with PDF bytes/hash.
  **A5 must implement actual PDF PLUS summary transport. Currently only PDF is
  delivered.** A persisted summary is not a sent summary. Track component
  outcomes and retain the existing duplicate/unknown-result safeguards. In
  particular, do not resend an accepted PDF when only its summary failed, or
  mark Sent while required delivery is incomplete/uncertain.

## Later phases and release boundary

After A1–A5, stop for another chat for frontend F1–F5. The current UI is the
original interface and has not implemented the new profile/conversation/change/
review flows. It can omit the role header on price saves; F4 must fix that and
keep Staff/Manager permissions visible. Finally run T1–T3, live team-controlled
checks, deployment verification and the recording rehearsal. Do not redeploy
this intermediate backend and call the full V2 demo complete.

Use real PostgreSQL only at runtime. Tests must use temporary databases and
mocked providers. Docker's PostgreSQL 16 image is cached locally; create a new
disposable localhost-only container for tests. Set `TEST_DATABASE_URL` to that
test database. Windows elevated pytest could not read an older temp directory;
use a fresh ignored `--basetemp=.input/<unique-name>` and `-p no:cacheprovider`.
Never use a live Replit/customer database for tests or print `.env` values.
No PDF template change after B4; its five samples/all multipage pages were
rendered and visually checked. Generated output and intermediate files stay
ignored. No secrets or generated artifacts belong in commits.
