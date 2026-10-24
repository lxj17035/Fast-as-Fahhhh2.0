# V2 Phase 4 verification

24 October 2026, Asia/Kuala_Lumpur. Branch `codex/feat-domain2-v2`.

Local environment: Python 3.14.7, Node 24.15.0, installed Edge through Playwright,
and disposable PostgreSQL 16 bound only to localhost. Replit Python 3.12 was not
executed here. Pillow 13's installed metadata requires Python >=3.11, which
includes the configured Replit interpreter version; actual hosted install still
needs verification.

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

The user subsequently confirmed V2 has not been republished. Continue RP2 only
after the hosted dependency/security work and new publish:

1. Confirm the hosted `/api/business-profiles` returns the V2 profile list and
   the UI exposes Staff/Manager and the selected profile.
2. In Replit's private environment, run `python -m scripts.check_live_config` and
   capture only its booleans/provider label. Confirm published deployment Secrets
   select Runpod, not merely the development workspace/local `.env`.
3. From the verified team-controlled Telegram chat, send one new fictional enquiry
   with a unique marker. Do not substitute a fabricated webhook for live intake.
4. Match that marker/time with the hosted enquiry and new AI draft/analysis, blank
   prices and missing facts. Capture sanitized matching Runpod request ID/usage
   evidence where supplied. Existing/cached drafts do not prove a fresh call.
5. Keep private tokens/chat IDs and raw logs out of committed screenshots
   or demo video. Account usage/billing evidence and current submission rules
   (including whether shared Public Endpoint usage satisfies them) remain unverified.

No live transport, provider/account-management access or clean Replit security
scan is claimed from local configuration or these mocked acceptance tests.

## T2 — Cleaning and Repair (passed)

T1 implementation commit: `9ffb415`. T2 changes `tests/phase4_support.py`,
`tests/test_phase4_journeys.py`, `frontend/tests/journeys.mjs`, this report and
the plan. No application code changed. Both profiles repeat the full clarification
and approved PDF/summary journey: Cleaning 2 visits at MYR 180.50 = 361.00;
Repair 1 keyboard-replacement job at MYR 95.75. Scope/device details stay in
generic notes. Captured validated Runpod context uses the chosen business and
custom company, with no Printing identity/items. PDF text retains the correct
company/service/unit/notes; switching scope hides the prior enquiry/conversation/
quotation/PDF and switching back preserves its exact sent PDF bytes.

- `TEST_DATABASE_URL=<disposable-local-db> .venv/Scripts/python.exe -m pytest -q tests/test_phase4_journeys.py --basetemp=.input/v2-t2-api -p no:cacheprovider`:
  **6 passed** (T1 + T2, SQLite/PostgreSQL), one existing Starlette warning.
- `QF_PLAYWRIGHT_MODULE=<installed-module> node frontend/tests/journeys.mjs`:
  **3 complete browser journeys passed**, all three profiles, actual UI/proxy/API,
  temporary SQLite, mocked providers. Desktop/mobile, rendered saved PDF/hash,
  unit/notes/price/total, explicit clarification/review/approval and history passed.
  No page/console errors or page overflow. Cleaning desktop and Repair mobile
  screenshots visually reviewed; artifacts remain ignored `.input/phase4/`.
- `git diff --check`: passed. Live/hosted checks remain separate.

## T3 — post-send and negative integration (passed)

T2 commit: `7adf602`. Changed `tests/test_phase4_journeys.py`,
`frontend/tests/journeys.mjs`, this report and the plan. Existing safeguards
required no business logic/UI changes.

Three complete post-send scenarios retain exact original quote metadata/PDF and
summary history while delivering new Manager-priced/approved content: explicit
Revision; explicit independent Additional in a distinct same-chat enquiry; unclear
grouping -> editable Staff question -> explicit send -> customer confirmation ->
Revision. AI advice never forks/sends/applies to a sent quote. New revision prices
are blank. Additional rejects the same original enquiry as its target.

Negative integration combines AI/Staff send/pricing denial, recipient override,
duplicate original approval, stale version/PDF, wrong-profile read/edit/send/text
actions, transactional rollback after rejected scope, and unknown PDF delivery.
Unknown delivery records a verification hold, skips summary, blocks normal/retry
approval and preserves the original accepted PDF.

- `TEST_DATABASE_URL=<disposable-local-db> .venv/Scripts/python.exe -m pytest -q tests/test_phase4_journeys.py --basetemp=.input/v2-t3-api-final -p no:cacheprovider`:
  **14 passed**, SQLite + PostgreSQL, one existing Starlette warning.
- `QF_PLAYWRIGHT_MODULE=<installed-module> node frontend/tests/journeys.mjs`:
  all **3 industry journeys plus post-send unclear/Revision/Additional browser
  flows passed**. New forks were priced, reviewed and approved through actual UI,
  with immutable original PDF bytes/metadata checked. Desktop/mobile screenshots
  and no console/page errors/overflow retained. Fork selects are scoped to their
  form in the test to avoid an exact-label lookup ambiguity.
- `git diff --check`: passed. Earlier test-fixture completion metadata and selector
  mistakes were corrected before these passing runs; no application fix needed.

Run browser acceptance with existing Playwright installed/resolvable, or set
`QF_PLAYWRIGHT_MODULE` to its module URL. `QF_BROWSER_CHANNEL` defaults to `msedge`;
`QF_TEST_PYTHON` can override the repository virtualenv. Both local servers use
reserved ephemeral localhost ports, mock external transports and clean up temporary
SQLite on exit. These are test adapters, never runtime storage.

T3 implementation commit: `de48358`. Remote `origin/main` had an additional empty
Replit publication commit `1f6eca4`; normal merge `c2f2c48` preserves it before
final regression/publication. No remote files were discarded.

The user's Pillow finding is handled separately from T1-T3 in
[Pillow security follow-up](PILLOW_SECURITY.md). It requires hosted dependency
rebuild/import/scan verification before republish; no hosted fix is claimed.

## Final merged verification

After preserving remote `origin/main` and applying the Pillow source/build fix:

- With `TEST_DATABASE_URL` set only to the fresh disposable localhost PostgreSQL
  16 database, `.venv/Scripts/python.exe -m pytest -q --basetemp=.input/v2-phase4-full -p no:cacheprovider`:
  **658 passed, 5 skipped, 1 existing Starlette deprecation warning**, **872.69s**.
  Both isolated SQLite and PostgreSQL parameters ran. Five runtime-PostgreSQL-only
  cases skip under SQLite; PostgreSQL counterparts ran. The session's named test
  container was removed after verification; unrelated containers were untouched.
- `node --test frontend/tests/*.test.mjs`: **31 passed**.
- `node frontend/tests/integration.mjs`: **10 passed** against actual temporary
  API with mocked providers.
- `node frontend/tests/journeys.mjs` with installed Playwright: **3 complete
  profile journeys plus post-send unclear/Revision/Additional UI flows passed**.
  Edge desktop 1365x900/mobile 390x844, no page/console errors or page overflow;
  screenshots visually reviewed under ignored `.input/phase4/`.
- `node --check frontend/tests/journeys.mjs`, final `git diff --check`: passed.
- Pillow focused tests: **10 passed**; **32 installed packages compatible**;
  dependency lists and Replit build TOML validated as recorded above.

No frontend product code, backend business logic or PDF template changed. No
production identity, live provider call, customer message, hosted write or deploy
was performed. Complete local acceptance does not complete RP2 or resolve the
entire Replit scanner finding list. Do not record the final hosted demo until
the release checks have actual evidence.
