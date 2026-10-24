# Local development — 24 October 2026

## Existing short titles
Reviewed prompt/schema/storage and legacy fallback. `.venv/Scripts/python.exe -m pytest -q tests/test_short_titles.py tests/test_drafting.py`: 14 passed. System `python` lacks pytest; project virtualenv is used for all backend checks. No live providers.

## Existing Inbox and detail preview
Reviewed existing uncommitted UI helpers, session-only Close/Restore, local-only synthetic channels, source-ID confirmation and readonly polling. node --test frontend/tests/*.test.mjs: 39 passed. node frontend/tests/integration.mjs: 10 passed with temporary DB and mocked providers. Browser journeys will be rerun after the next workflow changes. No current full-backend-green claim.

## Durable review submission
Added transactional submit-review, saved version/source evidence and activity. Saves/AI applications invalidate old evidence; new/unassigned source checks reject stale handoffs. Tests: submission + Manager review 26 passed/1 skipped on SQLite; same command with disposable TEST_DATABASE_URL on localhost:55439: 53 passed/1 skipped (SQLite + PostgreSQL). Initial test found missing activity allowlist; fixed before this passing run. No real provider calls.
