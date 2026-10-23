> Historical merge review: the one-attempt limitation below was subsequently fixed. See [PM_APPROVAL.md](PM_APPROVAL.md) and [DELIVERY_RETRY_CHECKLIST.md](DELIVERY_RETRY_CHECKLIST.md) for current behavior and verification.

# Sweeway merge review - 23 October 2026

## Scope and resolutions

Merged `origin/feature/sweeway-telegram-integration` at `2e3ebfb` into Xinjie's
backend based on `8f8a7c8`. Resolved eight conflicting files and reviewed
cleanly merged files for behavior conflicts too.

- One FastAPI application, one PostgreSQL database, one public handler per operation.
- Reused existing `quotation_records` data instead of a second `xinjie_records` store.
- Shared transaction/advisory locks across automatic drafts, editor/PDF operations and send reservations.
- PostgreSQL race testing found a lock-order inversion between edits and sends; all paths now acquire the process lock before the database lock.
- Preserved automatic drafting and distinct empty client records for unknown senders.
- Automatic and explicit drafting share one saved record and injected AI provider.
- Retained Sweeway's transactional receipt/draft/edit/approval/delivery history and detailed inbox state.
- Fixed ENABLE_DEMO_APPROVAL being dropped during database URL normalization.
- Allowed X-Demo-Actor in local frontend CORS preflight.
- Preserved blank secrets, port 8004, ignored .env/.input, and script packaging.
- Updated frontend/API handoff and failure/repeat-click instructions.

## Public API decision

Use `POST /api/quotations/:id/send` with `X-Demo-Actor: pm` and
`{"expected_version": N, "approved": true}`. Set private ENABLE_DEMO_APPROVAL=true
only for the supervised test. First save and display `/pdf?version=N`.

Send responses use `attempt_id` and `status` (sent/failed/unknown). Poll enquiry
detail for attempt/provider references and canonical `activity` entries.
Activity-only endpoints return the same entries under `items`.

The merged MVP allows one attempt per quotation. Duplicate clicks return 409.
Known failure retry is deliberately unavailable in this public handler, as is
blind resend after uncertainty. The older body-based approval and retry contract
is superseded; compatibility SendService tests remain isolated from public routes.

Existing quote/PDF records remain in their original table. Older JSON activity
is retained but not invented into the new canonical history; no historical
receipt/approval/delivery backfill is claimed. Startup creates missing prototype
tables, not schema migrations or imports from already-used alternate branch stores.

## Verification

- Portable merged suite before final regression additions: 232 passed, 1 skipped.
- Added regressions for one handler per operation, one automatic/explicit saved
  quotation, shared activity reads, CORS actor header, approval configuration
  normalization and configuration-readiness reporting.
- Final combined SQLite/PostgreSQL suite: **373 passed, 1 skipped**, 231.88 seconds. One existing Starlette/httpx deprecation warning.
- Strengthened the cross-instance PostgreSQL approval test with separate engine identities (separate Python locks): **1 passed, 1 SQLite skip**.
- The SQLite skip is the PostgreSQL advisory-lock concurrency case; verify its
  PostgreSQL instance separately in the combined run.
- External AI/Telegram calls are mocked. Tests remove ambient live AI keys.
- Temporary local PostgreSQL uses synthetic credentials; no team database is read.
  Asynchronous WAL commits reduce test disk waits; power-loss durability is not tested.
- PDF template is unchanged; tests compare delivered bytes with the saved preview.

## Remaining work and owners

- [ ] Xinjie: add RunPod Chat Completions support; current extractor still calls OpenAI Responses.
- [ ] Sweeway: configure private bot/webhook/provider settings and verify the real team-chat journey, including receipt, AI draft, approved PDF and activity.
- [ ] YieXian: frontend inbox/editor/settings, saved-version PDF preview, simulated role selector, approve button and activity/send states.
- [ ] Team: configure Replit hosting/PostgreSQL and reachable HTTPS webhook; current server binds localhost for the supervised demo.
- [ ] Team: fill submission links, slides/video, rehearse and measure preparation time.

Email, additional messaging channels, production identity and retry/recovery UI
are deferred. Mocked test success is not a completed live demonstration.
