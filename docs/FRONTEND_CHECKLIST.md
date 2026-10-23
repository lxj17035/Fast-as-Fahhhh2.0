# Frontend implementation — feature/frontend

Frontend-only work. Existing Python code and API contracts remain unchanged.
No deployment or Git push is part of this work.

## 1. Foundation and API client

- [x] Dependency-free ES modules, local static server on 127.0.0.1:5173.
- [x] API client targets the existing FastAPI server on 127.0.0.1:8004.
- [x] Preserve nullable prices, quotation versions, PM approval and exact retry links.
- [x] Test API payloads, server file restrictions, and approval guards.

Verification: `node --test frontend/tests/*.test.mjs`: **11 passed**.
`git diff --check` passed. No backend files changed.

## 2. Connected workspace

- [x] Inbox, current-page search/filter, pagination, loading/error/empty states.
- [x] Message context, quotation editor, explicit saved PDF preview, PM approval.
- [x] Delivery history, confirmed-failure retry, uncertainty guards and activity.
- [x] Business settings and existing-client editing.
- [x] Responsive layout, keyboard access and unsaved-edit protection.

Verification: **12 frontend tests passed**; JavaScript syntax and whitespace checks
passed. Browser exercised the actual FastAPI app with a temporary SQLite test
adapter and injected synthetic AI/Telegram providers: price/save, MYR 500.00,
saved-version PDF, PM confirmation, explicit rejection, linked approved retry,
accepted-send lock, chronological activity, settings save and client load/save.
The in-app browser did not render native PDF embeds, so the workspace now uses
locally installed PDF.js to render the exact backend PDF bytes. The saved PDF was
visually verified in the canvas preview. There are no CDN dependencies.

The foundation started without third-party browser dependencies; PDF.js is now
the one frontend dependency, pinned in package.json and pnpm-lock.yaml.

## 3. Verification and handoff

- [x] Browser checks using actual FastAPI with explicitly mocked providers; no live provider calls.
- [x] API integration verification using the shipped JavaScript client and isolated Python app.
- [x] Setup and limitation documentation; backend changes verified absent.

Final evidence:

- `node --test frontend/tests/*.test.mjs`: **14 passed**.
- `node frontend/tests/integration.mjs`: **7 passed**. The runner creates its own
  temporary database, uses an ephemeral localhost port, and shuts down/cleans up.
- `.venv/Scripts/python.exe -m pytest -q`: **274 passed, 2 skipped**, one existing
  Starlette/httpx deprecation warning, 31.39 seconds. This run explicitly omitted
  TEST_DATABASE_URL; no live PostgreSQL database or external providers were used.
- Browser: real API reads and mutations; price/save and exact saved total;
  PDF.js canvas visibly matched the saved PDF; explicit PM approval; confirmed
  failure and linked retry; sent locking; company/client saving; literal escaped
  customer markup; cancelled navigation preserved unsaved pricing; unknown
  delivery locked editing/resend and stayed blocked after a full browser reload.
- Responsive screenshots at 1440px desktop and 390px mobile using ignored QA
  iframe harnesses. Mobile inbox shows status badges without horizontal scrolling.
  Temporary screenshots/harnesses are under ignored `.input/frontend-review/`.
- Improved malformed-delivery handling, unknown-outcome session guards, PDF
  pagination, small-screen item layout and reviewable CSS formatting.
- JavaScript syntax, whitespace and changed-file checks passed. Existing
  `app/`, `backend/`, `tests/`, Python dependency/config files and `.env.example`
  have no differences from `main`. No push or deployment performed.

Live Telegram/AI, real PostgreSQL integration in this environment, and hosted
deployment remain outside this verification. See FRONTEND.md for exact limits.

## 4. Code walkthrough and Mermaid topology

- [x] Added `docs/CODE_WALKTHROUGH.md` explaining the combined frontend/backend,
  startup, Telegram receipt, AI/manual drafting, forms/state, quotation rules,
  versioned PDFs, approved delivery/retry, storage, and activity.
- [x] Added nine Mermaid architecture, flow, sequence, state, and storage diagrams.
- [x] Linked the walkthrough from README.

Verification: all nine diagrams parsed successfully with Mermaid 12.2.0 using a
temporary DOM environment. Markdown fences are balanced and every local guide
link resolves. Validation packages/scripts remain under ignored `.input/docs-check/`;
no application dependencies changed. `git diff --check` passed. This section is
documentation only, so application tests were not rerun.

## 5. Simpler everyday use

### A. Inbox and settings

- [x] Replace dashboard clutter with three actionable inbox counts and four filters.
- [x] Distinguish Not sent from Check Telegram, while grouping both under Needs checking.
- [x] Give the empty inbox a clear first step and expandable connection help.
- [x] Keep business settings prominent; move client references and demo/connection controls into disclosures.
- [x] Increase working text/input sizes and use plain labels.

Verification: **16 frontend tests passed**; JavaScript syntax and whitespace checks
passed. Browser checked the running project's empty inbox and business settings;
no runtime records were changed. Backend code is unchanged.

### B. Guided quotation review

- [ ] Show Details -> Preview -> Send and a single next-step explanation.
- [ ] Add Save & preview without weakening version or explicit approval checks.
- [ ] Keep delivery diagnostics and long activity histories out of the primary flow.
- [ ] Verify edit/save/preview, sent/failed/unknown, mobile, and unsaved-edit behavior.
