# Domain 2 V2 Phase 2 verification

Branch: `codex/feat-domain2-v2`. Complete A1-A5, then stop before frontend.
All automated tests use mocked providers and disposable storage. PostgreSQL 16
is localhost-only on port 55439; no runtime/customer database is used.

## A1 â€” Core prompt and dynamic context

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

## A2 — Requirements and sufficiency

Changed `backend/drafting.py`, `tests/test_ai_v2.py`. Shared prompt covers stated
units, industry notes and critical scope uncertainty. Server independently flags
empty items, unknown quantities and neutral/unknown units even if the model omits
them. Existing validation blocks formal review/send and labels incomplete PDFs
as drafts. No template changes. Unknowns/prices stay blank; no industry defaults.

With disposable `TEST_DATABASE_URL`:
`.\.venv\Scripts\python.exe -m pytest -q tests/test_ai_v2.py tests/test_drafting.py tests/test_runpod.py tests/test_quotation_v2.py --basetemp=.input/v2-a2 -p no:cacheprovider`:
**88 passed**, existing warning. Three profiles tested with notes and unknowns.
Industry scope sufficiency still depends on model flags plus explicit Staff review;
no new per-industry rules engine. No live provider check in this section.

## A3 — Clarification and renewed analysis

Changed `backend/drafting.py`, new `backend/analysis.py`, `app/routing.py`,
`app/automatic_drafting.py`, `app/telegram.py`, `app/quotation_routes.py`,
`tests/test_ai_v2.py`. Contract: `docs/AI_ANALYSIS.md`.
Initial and renewed snapshots retain source evidence and editable questions.
Customer follow-ups trigger analysis; existing Staff edits remain untouched.
Unchanged completed analysis is reused; duplicates do not consume another call.
Provider-time races are stale and never acknowledge new messages. AI association
requires an actual later customer reply, exact unresolved-message reference and
explicit enquiry/quote reference; arbitrary claims and confirmed decisions block.

With disposable `TEST_DATABASE_URL`:
`.\.venv\Scripts\python.exe -m pytest -q tests/test_ai_v2.py tests/test_drafting.py tests/test_runpod.py tests/test_routing_v2.py tests/test_automatic_drafting.py --basetemp=.input/v2-a3-verified -p no:cacheprovider`:
**96 passed**, existing warning; diff checks passed. Earlier runs exposed duplicate
analysis and synthetic fixture/manual-cache issues; corrected before this rerun.
No customer send or quotation overwrite. Conservative assignment needs Staff to
associate a confirmation first; vague evidence stays Needs Assignment. UI is F3.
