# Domain 2 V2 backend phase verification

Branch: `codex/feat-domain2-v2`. User authorized completion of Backend B2–B5,
then a stop and handoff to a new chat for Phase 2. B1 is `6b77031` with its
[separate report](BUSINESS_PROFILES.md). No Replit redeployment is part of this
phase; providers remain mocked in tests.

## B2 — Telegram routing and assignment

Implemented conservative classification in `backend/routing.py`, transactional
receipt/association persistence in `app/database.py` and `app/routing.py`,
Staff-only resolution/history with scope and chat validation, and preservation
of command/unassigned receipts across backfill/restart. Follow-up and reference
messages appear chronologically in enquiry detail and draft source text.

Other changed source: `app/activity.py`, `app/main.py`, `app/telegram.py`,
`app/automatic_drafting.py`, `app/enquiries.py`, `backend/store.py`.
Tests: `tests/test_routing_v2.py`; independent-order fixtures updated in
`tests/test_enquiries.py`, `tests/test_business_profiles.py`,
`frontend/tests/preview_backend.py`. Contract updated in `docs/ENQUIRIES.md`.

SQLite regression command:
`.\.venv\Scripts\python.exe -m pytest -q tests/test_routing_v2.py tests/test_enquiries.py tests/test_telegram_webhook.py tests/test_automatic_drafting.py tests/test_activity.py tests/test_business_profiles.py`
returned **99 passed, 1 skipped**, one existing deprecation warning.

With `TEST_DATABASE_URL` pointing to the disposable localhost PostgreSQL 16 DB:
`.\.venv\Scripts\python.exe -m pytest -q tests/test_routing_v2.py --basetemp=.input/v2-b2-pg -p no:cacheprovider`
returned **22 passed** across SQLite and PostgreSQL. `node
frontend/tests/integration.mjs`: **7 passed**. `git diff --check`: passed.

The classifier only uses explicit independent-order cues, a validated Telegram
reply reference, or a clearly phrased follow-up when one candidate exists.
Ambiguity deliberately requires Staff. AI reassessment is Phase 2 work; this
section provides a validated association action that cannot overwrite confirmed
decisions. No customer text replies are sent by this section.
