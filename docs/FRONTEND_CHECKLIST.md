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

- [ ] Inbox, current-page search/filter, pagination, loading/error/empty states.
- [ ] Message context, quotation editor, explicit saved PDF preview, PM approval.
- [ ] Delivery history, confirmed-failure retry, uncertainty guards and activity.
- [ ] Business settings and existing-client editing.
- [ ] Responsive layout, keyboard access and unsaved-edit protection.

## 3. Verification and handoff

- [ ] Browser checks using explicitly mocked API responses; no live provider calls.
- [ ] API integration verification where local dependencies permit.
- [ ] Setup and limitation documentation; backend changes verified absent.
