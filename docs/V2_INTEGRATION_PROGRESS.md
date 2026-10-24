# V2 Phase 4 verification

24 October 2026, Asia/Kuala_Lumpur. Branch `codex/feat-domain2-v2`.

Repository review: backend profiles/routing/conversation/generic quotation/version/
review/delivery services, dynamic AI prompt/Runpod validation, PDF snapshots,
frontend editor and existing focused tests are implemented. Missing acceptance
evidence was a single repeatable complete Printing scenario, equivalent complete
Cleaning/Repair scenarios, integrated post-send scenarios and hosted RP2 evidence.
No production identity, extra channels, queues or runtime SQLite are introduced.

## T1 — Printing (passed)

Files: `tests/phase4_support.py`, `tests/test_phase4_journeys.py`,
`frontend/tests/journey_backend.py`, `frontend/tests/journeys.mjs`, this report
and the canonical plan. No application behavior or PDF template changed.

Complete fictional webhook enquiry -> actual Runpod adapter with mocked HTTP ->
editable Staff clarification -> explicit Send -> customer answer replying to the
accepted Staff message -> explicit current-message review -> Manager pricing ->
saved PDF/hash + deterministic summary -> approved PDF/summary -> attributed,
chronological history. Unknown quantity/price remain blank initially; 20 shirts
are corrected to 30, total MYR 750.00. Saved draft is not silently overwritten.
Stale message review is rejected; clarification request replay does not resend.
PDF text, summary dates/total, saved version, exact uploaded bytes and database
attempt snapshot agree. The existing calendar-month validity engine is retained.

Commands/results:

- `$env:TEST_DATABASE_URL='postgresql+psycopg://<disposable-local-test-db>'; .venv/Scripts/python.exe -m pytest -q tests/test_phase4_journeys.py --basetemp=.input/v2-t1-api-accepted -p no:cacheprovider`: **2 passed**, SQLite + fresh disposable localhost PostgreSQL 16, one existing Starlette warning.
- With `QF_PLAYWRIGHT_MODULE` pointing to the already installed Playwright module,
  `node frontend/tests/journeys.mjs`: **1 complete browser journey passed**.
  Actual API/proxy, temporary SQLite, mocked providers. Edge 1365x900 and 390x844:
  correct page/title/content, no error overlay, no console/page errors, no page
  overflow, Staff price readonly, editable explicit clarification, saved reviewed
  IDs, Manager price, rendered saved PDF fingerprint, matching summary and delivery.
  Browser plugin not available; regular installed Playwright/Edge used.
- Desktop/mobile screenshots saved under ignored `.input/phase4/`; mobile reviewed
  visually. Tables intentionally scroll within their container on narrow screens.
- `git diff --check`: passed. Section commit is recorded in the next checkpoint.

All providers in these tests are mocked. This is repeatable local acceptance,
not live Telegram/Runpod or hosted deployment evidence.

## RP2 — hosted release (blocked, unchecked)

User supplied `https://fast-as-fahhhh-20.replit.app/`. Read-only in-app browser
inspection shows the older Sales/PM UI and no V2 profile context. Navigating to
`/api/business-profiles` returned `{"detail":"Not Found"}`. No writes were made
to hosted storage and no Telegram message was sent. The generic web fetch could
not access this site; local urllib also failed, so only browser evidence is claimed.

`python -m scripts.check_live_config` reports local Runpod/key/webhook/test-chat
configuration present, but `ENABLE_DEMO_APPROVAL` false and live readiness false.
This prints only booleans/provider name; it neither validates credentials/chat
ownership nor proves Replit's private configuration. Do not copy local secrets
into reports. The hosted V2 build, sanitized Replit provider configuration,
fresh controlled Telegram intake and correlated Runpod request/usage evidence
remain required. No extra live call was made merely to spend credit.
