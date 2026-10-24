# Local development — 24 October 2026

## Existing short titles
Reviewed prompt/schema/storage and legacy fallback. `.venv/Scripts/python.exe -m pytest -q tests/test_short_titles.py tests/test_drafting.py`: 14 passed. System `python` lacks pytest; project virtualenv is used for all backend checks. No live providers.

## Existing Inbox and detail preview
Reviewed existing uncommitted UI helpers, session-only Close/Restore, local-only synthetic channels, source-ID confirmation and readonly polling. node --test frontend/tests/*.test.mjs: 39 passed. node frontend/tests/integration.mjs: 10 passed with temporary DB and mocked providers. Browser journeys will be rerun after the next workflow changes. No current full-backend-green claim.
