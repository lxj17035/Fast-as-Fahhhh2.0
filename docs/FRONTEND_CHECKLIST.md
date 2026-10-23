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

- [ ] Browser checks using explicitly mocked API responses; no live provider calls.
- [ ] API integration verification where local dependencies permit.
- [ ] Setup and limitation documentation; backend changes verified absent.
