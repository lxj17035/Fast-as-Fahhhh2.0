# Domain 2 V2 Phase 2 verification

Branch: `codex/feat-domain2-v2`. Complete A1-A5, then stop before frontend.
All automated tests use mocked providers and disposable storage. PostgreSQL 16
is localhost-only on port 55439; no runtime/customer database is used.

## A1 — Core prompt and dynamic context

Changed `backend/drafting.py`, added `tests/test_ai_v2.py`. Shared SME-agnostic
prompt explicitly forbids pricing/approval/send/recipient/profile authority.
Both adapters receive pinned validated profile identity, industry, company and
client. Schema includes generic unit/notes; legacy extraction remains readable.
Unknown unit uses the neutral `unit` placeholder, never an inferred industry unit.

With disposable `TEST_DATABASE_URL`:
`.\.venv\Scripts\python.exe -m pytest -q tests/test_ai_v2.py tests/test_drafting.py tests/test_runpod.py --basetemp=.input/v2-a1-schema -p no:cacheprovider`:
**51 passed**, existing Starlette deprecation warning. `git diff --check` passed.
Initial tests ran during an external checkout to main and failed for missing
Phase 1 APIs; user authorized restoration, and the final run used the V2 branch.
No live inference. Sufficiency, clarification and change generation remain A2-A4.
