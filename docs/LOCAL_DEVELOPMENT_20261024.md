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

## AI changes in Messages
45 frontend checks passed. tests/test_analysis_progress.py + tests/test_ai_v2.py: 39 passed with SQLite + disposable PostgreSQL. Browser journeys passed all three industries, editing/selecting/applying Messages suggestions, composer retention, Go to Quote, hidden stale/empty sets, manual save of incomplete data, Staff resubmission and both-role inbox routing, plus saved PDF/summary/confirmed send/Revision/Additional. Screenshots in ignored .input/phase4/*-suggestions-mobile.png. A newly added browser step initially targeted collapsed optional notes; updated the test to open Dates & notes. No provider calls or deployment.

## Mobile action containment and failure recovery
Actual mobile recovery check found Staff Save/Submit/Preview actions extending behind the sidebar. Narrow editor actions now stack vertically. 45 frontend checks passed. Browser on 390px verified AI failure still permits manual save/submission; explicit PDF rejection needs a fresh Manager approval and then succeeds; unknown delivery locks editing and offers no retry; PDF accepted/summary rejected freezes editing and retries only the identical saved summary/PDF snapshot. Saved PDF bytes matched before/after recovery. Both recovery scripts use temporary DB/mocked services; screenshots/scripts under .input/local-preview/recovery-*. No live provider proof.

## Preview and static audit notes

The current-code synthetic preview is http://127.0.0.1:8093/ (API 8094). Its
SQLite test adapter uses a consistent backup of the five original 8091/8092
synthetic records; the original database/processes were left running unchanged.
The two previews diverge after backup. No runtime PostgreSQL settings or .env
were changed. Browser checked the new submit endpoint is loaded, preserved IDs,
desktop/360px refresh/switch geometry, no overflow/page errors. The old preview
must not be used to validate newly loaded Python endpoints.

Strict premium UI audit was executed, evidence at ignored
.input/review-final-ui-audit.json. It reports five actionless-button findings
for existing data-action controls (missing-detail check, tabs, remove item and
Inbox actions). Inspection of audit_project.py lines 722-726 shows it recognizes
inline onclick/Vue handlers but not this application's delegated data-action
handler. These are scanner false positives, not a clean audit result. The shared
root click dispatcher and corresponding actions remain present; actual browser
journeys verify the controls. No inline handler or fake action was added to
silence the scanner. DESIGN.md/runtime palette and canonical shared form/button,
sidebar, settings, PDF and final confirmation ownership remain unchanged. No new
build/typecheck/a11y command is configured in premium-ui.json/package.json;
Node checks, real browser checks and project API tests supply runtime evidence.

## Local commit sections

| Commit | Section |
| --- | --- |
| 241cc8a | Existing short-title extraction and saved display metadata |
| 9b692bb | Existing task Inbox and tabbed detail workbench |
| cb2f5e1 | Transactional persisted review submission |
| 91c5268 | Staff/Manager routing, submission controls and tab order |
| 1eb68c4 | Synthetic channel switch below Refresh inbox |
| 64ba066 | Messages-owned AI changes and analysis progress/recovery |
| 074fe92 | Preserve deferred history browsing and incomplete RP2 notes |
| add0ae3 | Narrow-screen Staff draft actions |
| 34b155f | Reopen locally closed records on formal handoff |

Branch stayed codex/feat-domain2-v2. All commits are local; no push/deployment.

## Final regression result

- `.venv/Scripts/python.exe -m pytest -q` with disposable
  `TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55439/quoteflow_test`:
  **676 passed, 5 skipped**, 888.99 seconds. This is the final source run including
  analysis progress; the earlier pre-AI run was 672 passed / 5 skipped.
- One existing FastAPI/Starlette httpx deprecation warning; no failing test.
- `node --test frontend/tests/*.test.mjs`: **46 passed**.
- `node frontend/tests/integration.mjs`: **10 passed** against actual isolated API.
- Updated journeys.mjs: Printing/Cleaning/Repair, both roles, desktop/mobile,
  current-source review, manual save, AI edit/apply, composer/unsaved-input
  retention, submit/edit/resubmit, inbox ownership, saved-version PDF/hash/summary,
  explicit send cancellation/confirmation, Revision/Additional all passed.
- Additional actual API/browser checks: switch placement at 1365/390/360,
  same-version submission reopens session-closed row, AI failure manual fallback,
  explicit rejection retry, unknown hold, frozen summary-only retry passed.
- Final git diff --check passed. Strict static scanner limitations are recorded
  above and are not presented as a clean static audit.

All backend verification used isolated SQLite adapters and the disposable local
PostgreSQL database, with mocked external providers. The dedicated Docker test
container was stopped/removed after verification; the pre-existing container was
untouched. No real Telegram/Runpod checks, pushes or Replit publication. RP2 still
requires matched Runpod request/usage evidence and remains incomplete.

## README refresh (24 October 2026)

- [x] Reviewed `origin/main` at `90a8491`, README, workflow, startup/configuration and latest verification records.
- [x] Confirmed QuoteFlow as the project name; consolidated current features, Staff/Manager handoff, setup, hosting and release limits.
- [x] Verified all 15 README local links resolve, Markdown fences are balanced, and `git diff --check` passes.

Documentation-only change. Application tests and live provider/hosted checks were not rerun; README test counts are explicitly attributed to historical source verification. The existing checkout remains on `codex/feat-domain2-v2`, matching the reviewed remote-tracking main before this edit.

## Organiser README format (24 October 2026)

- [x] Matched the supplied organiser sample sections to QuoteFlow's actual implementation, tree, entry points, Runpod Chat Completions integration and Apache 2.0 license.
- [x] Added explicit pending submission PDFs, contributor handles, slide/video links and evidence checklist without claiming completion.
- [x] Verified required section headings, local link targets, balanced Markdown fences and git diff whitespace checks.

Documentation only; application suites, fresh setup and live hosted/provider checks were not rerun. Reviewed current template options for a separate slide-style recommendation; no presentation was created.
