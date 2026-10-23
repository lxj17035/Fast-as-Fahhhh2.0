# QuoteFlow frontend

Responsive enquiry inbox, quotation editor, exact saved-PDF preview, simulated
Sales/PM controls, approved delivery/retry, activity history, business settings,
and existing-client editing. All data comes from the existing FastAPI API.
There is no automatic fallback to mock data in the application.

## Run with the existing backend

Requires Node.js 22.13+ and pnpm. From the repository root:

```powershell
pnpm --dir frontend install --frozen-lockfile
node frontend/server.mjs
```

Open **http://127.0.0.1:5173**. No build step is needed. Keep this terminal open.
In another terminal, start your existing configured backend:

```powershell
.\.venv\Scripts\python.exe -m backend.server
```

The backend needs the PostgreSQL connection and webhook secret described in the
root README. Frontend installation does not create a runtime database, edit
`.env`, register a webhook, or enable demo sending. The existing API remains at
http://127.0.0.1:8004. Its existing CORS configuration allows this frontend origin.

The frontend's only dependency is locally served PDF.js, pinned by the lockfile.
There are no external fonts, image services, analytics, or CDN requests. If you
already installed the frontend dependencies in this checkout, `node
frontend/server.mjs` is sufficient to start it.

## Review without provider credentials

To exercise the real backend using disposable test data, stop any backend on
port 8004 first, then run this **QA-only** fixture from the repository root:

```powershell
.\.venv\Scripts\python.exe -m frontend.tests.preview_backend
```

Start the frontend normally and open the inbox. This fixture uses a temporary
SQLite test adapter under ignored `.input/` and injected synthetic AI/Telegram
providers. It never reads `.env`, uses the runtime PostgreSQL database, or makes
external provider calls. This is test infrastructure, not a runtime database
fallback. Stop it with Ctrl+C after review.

Four fictional enquiries are created. The first approved mock send explicitly
fails, the second succeeds, and the third has an unknown result. Counters reset
when this fixture restarts. Price an item at 25.00, resolve its missing-information
flag, save, load the PDF, switch to PM, and explicitly approve. Review and retry
only a confirmed failed attempt. An unknown result stays blocked.

## Checks

From the repository root:

```powershell
node --test frontend/tests/*.test.mjs
node frontend/tests/integration.mjs
```

The integration runner starts its own instance of the actual backend on an
ephemeral localhost port, with isolated test storage and mocked providers,
then stops it and removes its temporary database. It uses the root `.venv` by
default; set `QF_TEST_PYTHON` to a different Python executable if needed. Install
the existing `requirements-dev.txt` there first. This does not require a live
bot, AI key, or PostgreSQL. Real PostgreSQL and live-provider checks are separate.

See [the frontend handoff](../docs/FRONTEND.md) and
[section-by-section evidence](../docs/FRONTEND_CHECKLIST.md).
