> Final merged SQLite/PostgreSQL verification: **373 passed, 1 skipped** (the PostgreSQL case of the skipped SQLite check passed). After the Sweeway merge, use MERGE_REVIEW.md for current evidence and PM_APPROVAL.md for the send contract. Historical results below refer to earlier commits. The integrated API permits one attempt per quotation; retry is deferred.

# Remaining backend delivery work

Completed items are removed from this active list and recorded below.

- [ ] Member 2 configures private credentials and a team-controlled test chat; verify the real end-to-end journey.

## Completion evidence

### Automatic drafting on receipt

- Incoming authenticated text updates persist first, then trigger a background draft without a second HTTP request.
- Duplicate updates can retry interrupted drafting and return existing quotations without overwriting PM edits.
- Expected AI failure creates a labelled manual-review draft. Unexpected background failure preserves the enquiry for retry.
- `pytest tests/test_automatic_drafting.py tests/test_shared_quotation_api.py tests/test_telegram_webhook.py -q`: **38 passed** using isolated test storage and mocked AI.
- This in-process background task is for the demo. An interrupted process leaves the enquiry in the inbox; retry via the draft endpoint or a repeated webhook. No durable worker/queue is claimed.

### Merge

- No MERGE_HEAD or unmerged entries exist in this checkout.
- The earlier merge is already committed as `8aa59b9` (Merge branch main into feat/xinjie); the newer Sweeway delivery/activity commits are incorporated by the merge recorded in MERGE_REVIEW.md.

## Live configuration

Readiness check reports DATABASE_URL present; TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, OPENAI_API_KEY, and OPENAI_MODEL missing. Presence is not a successful connection test. Member 2 owns filling these privately in .env and identifying the controlled test chat. Never paste credentials into chat or fixtures.

### PM approval and Telegram PDF sending

- Implemented version/preview/role/approval validation and original-chat-only PDF uploads.
- Persisted send reservations prevent repeated/concurrent clicks and restart retries from uploading twice. Known failures require explicit retry approval; uncertain outcomes block blind resend.
- Targeted send/adapter/webhook/shared API regression tests with real PostgreSQL and mocked Telegram: **67 passed**. Read-only enquiry quotation lookup was also checked in both database adapters.
- New API contract: docs/PM_APPROVAL.md. No live Telegram message was sent during tests.

### Approval and delivery activity log

- Added chronological read-only enquiry/quotation activity endpoints.
- Receipt events use stable keys, approval events are atomic with send reservations, and result events are atomic with the persisted outcome/inbox status.
- Duplicate webhooks/clicks do not duplicate events. Audit-write failure before upload rolls back approval; failure after upload leaves the pending attempt locked against duplicate sending.
- Outcomes distinguish Telegram acceptance from reading, rejection, and uncertainty. Tests use only mocked uploads.

- Activity/send/automatic-drafting regression checks with PostgreSQL: **56 passed**.

### Live verification preparation (not completed)

- `python -m scripts.check_live_config` safely reports presence/format without printing values or calling services. Its three tests passed.
- Current check: DATABASE_URL has a valid-looking PostgreSQL scheme. Bot token, webhook secret, OpenAI key/model, and LIVE_TEST_CHAT_ID are missing. Exit 1 is expected until Member 2 supplies them privately.
- Prepared docs/LIVE_TEST.md for actual inbound receipt, AI draft, PM pricing/preview, approved outbound PDF, activity, and repeat-click verification. This procedure has not been run against real services.

## Final local regression verification

- Full combined pytest suite with a disposable PostgreSQL database: **245 passed, 1 skipped**. The skip is a PostgreSQL-only concurrency test under the SQLite test adapter; its PostgreSQL case passed.
- One Starlette/httpx dependency deprecation warning remains; no test failure.
- Verified documentation links/fences, blank private fields in .env.example, ignored .env, and no pending merge.
- No real AI call or Telegram message was sent. The remaining live verification is intentionally unchecked.

## Review commits

- `d05a822`: automatic drafting after receipt (38 targeted checks).
- `5a131a7`: explicit PM approval and guarded Telegram PDF sending (67 targeted checks plus read API verification).
- `c1c3565`: persisted approval/provider-outcome activity (56 targeted checks).
- Live-test readiness/helper documentation is committed separately; it does not complete the live test.
