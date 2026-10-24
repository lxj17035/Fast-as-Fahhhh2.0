# Local development — 24 October 2026

## Existing short titles
Reviewed prompt/schema/storage and legacy fallback. `.venv/Scripts/python.exe -m pytest -q tests/test_short_titles.py tests/test_drafting.py`: 14 passed. System `python` lacks pytest; project virtualenv is used for all backend checks. No live providers.

## Existing Inbox and detail preview
Reviewed existing uncommitted UI helpers, session-only Close/Restore, local-only synthetic channels, source-ID confirmation and readonly polling. node --test frontend/tests/*.test.mjs: 39 passed. node frontend/tests/integration.mjs: 10 passed with temporary DB and mocked providers. Browser journeys will be rerun after the next workflow changes. No current full-backend-green claim.

## Durable review submission
Added transactional submit-review, saved version/source evidence and activity. Saves/AI applications invalidate old evidence; new/unassigned source checks reject stale handoffs. Tests: submission + Manager review 26 passed/1 skipped on SQLite; same command with disposable TEST_DATABASE_URL on localhost:55439: 53 passed/1 skipped (SQLite + PostgreSQL). Initial test found missing activity allowlist; fixed before this passing run. No real provider calls.

## Staff handoff UI and navigation
42 frontend checks passed. Updated journeys.mjs passed Printing/Cleaning/Repair desktop 1365x900/mobile 390x844, automatic new-message notice with unsaved input retained, formal unpriced submission, Manager pricing, current saved PDF/hash/summary, cancel/confirm send, Revision/Additional and original PDF retention. Browser plugin absent; existing Playwright/Edge used on ephemeral ports with temporary DB/mocked Runpod HTTP/Telegram. First browser run exposed a test assuming Quote on new-message reopening; corrected to explicitly select Quote. Existing 8091/8092 preview processes are preserved. No publish/live providers.

## Synthetic-channel switch placement
Owner follow-up: place Show synthetic channel examples below Refresh inbox. CSS-only layout change; existing toggle stays local-only. Verified on existing 8091 without restarting it at 1365/390/360: below-button geometry, toggle interaction, no overflow/page errors; 5 inbox checks passed. Screenshots under ignored .input/local-preview/refresh-switch-*.png.
