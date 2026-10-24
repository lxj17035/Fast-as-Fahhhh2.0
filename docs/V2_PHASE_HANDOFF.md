# Domain 2 V2 - phase handoff

Updated 24 October 2026, Asia/Kuala_Lumpur.
Branch: `codex/feat-domain2-v2`, existing repository. Work one phase per chat,
test and commit each section, then stop. Do not switch checkout during a run.

## Current checkpoint

Phase 1 B1-B5 and Phase 2 A1-A5 are complete and committed. Stop here.
Next chat: Phase 3 F1-F5 only. No V2 push or Replit redeployment was performed.
Anonymous synthetic preview remains; production identity/channels/queues remain
out of scope. Live Telegram and hosted Runpod proof remain release work.

| Section | Commit | Section verification |
| --- | --- | --- |
| A1 dynamic core prompt/context | `dc2a39c` | 51 passed |
| A2 extraction/sufficiency | `33f7ecf` | 88 passed |
| A3 clarification/renewed analysis | `3ca6165` | 96 passed |
| A4 suggested changes | `c3702bd` | 106 passed |
| A5 approved PDF plus summary | `7f28fe7` | full 640 passed, 5 skipped; final focus 67 passed, 2 skipped |

All automated provider tests are mocked; SQLite adapters and disposable localhost
PostgreSQL 16 exercised. Skips are PostgreSQL-only cases under SQLite; PostgreSQL
counterparts passed. Full merged suite used
`.\.venv\Scripts\python.exe -m pytest -q --basetemp=.input/v2-phase2-full -p no:cacheprovider`
with disposable `TEST_DATABASE_URL`: 640 passed, 5 skipped, existing Starlette
warning, 589.33s. The final frozen-preview/review adjustment was then checked with
`tests/test_pdf.py tests/test_outbound_v2.py tests/test_manager_review_v2.py`
using `--basetemp=.input/v2-a5-final-review -p no:cacheprovider`: 67 passed,
2 skipped. Frontend unit checks 24 passed; mocked API integration 7 passed.
Exact source files/commands: [Phase 2 report](V2_AI_PROGRESS.md).
Phase 1 history: [backend report](V2_BACKEND_PROGRESS.md).
No PDF template change; saved bytes/hash and summary dates/totals are tested.

## Phase 3 contracts and implementation notes

Read AGENTS.md, README, docs/WORKFLOW.md, the canonical plan, this handoff,
[AI analysis contract](AI_ANALYSIS.md), [approval contract](PM_APPROVAL.md),
and existing frontend docs/source before changes. Use the applicable frontend
skills, preserve existing UI patterns, and test rendered interactions.

- F1: profile settings and active selection exist at `/api/business-profiles`.
  Intake pins identity; AI never selects it. Old enquiries retain their scope.
- F2: `/api/assignments` lists Needs Assignment. Explicit Staff assignment/new/
  unrelated actions preserve history and enforce same profile/chat.
- F3: GET `/api/enquiries/{id}/conversation` includes attributed incoming,
  Staff outgoing, quotation PDF and summary attempts. POST `/messages` takes
  `{text, request_id}` with enabled simulated Staff header, never recipient.
  GET/POST `/analysis` reads/requests analysis; POST requires explicit Staff.
  Customer follow-ups automatically request renewed analysis; duplicates do not.
  Initial draft analysis is retained without a second inference request.
  Display `extraction.clarificationSuggestions` as editable suggestions; Staff
  must click Send. AI has no sender. Failed/manual analysis permits manual work.
- Analysis snapshots include quotation/baseVersion, source/unresolved IDs,
  business context and attributed evidence in `signature`. Compare with current
  quote/conversation as well as checking `stale`; never treat old analysis as
  acknowledgement of messages arriving later. Pinned internal analysis works
  after active-profile switches; HTTP views still respect active scope.
- AI assignment is intentionally conservative: exact later customer confirmation
  replying to the unresolved message and naming enquiry/quote reference, with
  backend validation. Staff may associate confirmation first. Vague/model-only
  claims remain Needs Assignment. No Staff decision can be overridden.
- F4: common item_name/quantity/unit/unit_price/amount/notes exist with legacy
  aliases. Staff must retain Manager prices; every price save needs enabled
  `X-Demo-Actor: pm`. AI proposedChanges are validated and de-duplicated, then
  stored via existing QuotationChanges sets. Renewed analysis returns
  `suggestionSetId`, `changeWarnings`, advisory `relationshipIntent`. Use GET
  quotation `/suggestions` and explicit POST `/apply-changes` selections/edits.
  Initial extraction already supplies draft items; do not apply them twice.
- `reviewedMessageIds` is the exact current chronological incoming ID list.
  Staff explicitly reviews it on save. Unassigned/new messages block formal
  review/send. Incomplete PDF previews remain labelled drafts; prices stay blank.
- Revisions/additional quotations require explicit Staff `/fork` actions.
  AI relationship intent never creates a fork. Sent PDFs remain immutable.
- F5: Manager GET quotation `/review?version=N` returns the exact saved quote,
  PDF URL/version/hash and deterministic `telegram_summary`. Final page must show
  these together and use explicit approval/current version for `/send`.
  `delivery_mode` is `pdf_and_summary` normally or `summary_only` after confirmed
  summary failure with accepted PDF. In that recovery, content is frozen and
  Back to Edit must explain the lock. Fresh approval references the exact failed
  `retry_of_attempt_id`; accepted PDF is reused and only the same summary sent.
  Frozen preview/review remains available if newer messages arrive, but delivery
  completion leaves enquiry Needs review. It does not apply newer requirements.
- Delivery attempts expose pdf_status, summary_status and summary provider ID.
  Overall Sent requires both accepted. Pending/unknown/save failures hold; never
  retry them automatically. Old rows have nullable component metadata, not proof
  of summary delivery. Expired partial snapshots cannot be retried. Show errors.

## Release boundary

After F1-F5, stop for Phase 4 T1-T3/RP2 and release. Verify actual Replit provider
selection, a team-controlled Telegram journey, hosted Runpod evidence, deployment
and recording rehearsal separately. Current UI has not implemented these V2
flows; backend tests are not a full hosted demonstration.

For tests create a new disposable localhost-only PostgreSQL container. The Phase 2
container is removed at handoff. Never use local runtime/Replit/customer databases.
Use fresh ignored `.input/<unique>` basetemp paths and `-p no:cacheprovider`.
Secrets stay local; no generated/raw artifacts in Git. No live customer sends.


## RP1 result

Passed: exactly one synthetic live Runpod glm-5.3 request, HTTP 200, 12:30
Malaysia time on 24 October 2026. Request ID and 1,362-token usage captured in
[sanitized evidence](V2_RUNPOD_RP1.md). This verifies changed V2 prompt/context,
not the hosted app. Model left unit unknown despite stated visits, and listed
unagreed pricing as missing: Staff must review those flags, Manager sets prices.
No pricing/recipient/send authority was granted. No retry or billing-balance
verification. RP2 remains required after frontend and before demo recording.
