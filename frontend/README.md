# QuoteFlow frontend

Responsive enquiry inbox, quotation editor, exact saved-PDF preview, simulated
Sales/PM controls, approved delivery/retry, activity history, business settings,
and existing-client editing. All data comes from the existing FastAPI API.
There is no automatic fallback to mock data in the application.

## Run with the existing backend

Requires Node.js 22.13+ and pnpm. From the repository root:

```powershell
pnpm --dir frontend install --frozen-lockfile
```

Start the existing configured backend:

```powershell
.\.venv\Scripts\python.exe -m backend.server
```

In another terminal, start the public web entry:

```powershell
node frontend/server.mjs
```

It listens on `0.0.0.0:8080` by default; set `PORT` to override it. Open
**http://127.0.0.1:8080** to preview without login. The old
`DEMO_ACCESS_USERNAME` / `DEMO_ACCESS_PASSWORD` settings are unused. The page
and `/api/*` routes use the same origin; the entry proxies API calls to the
private backend at `127.0.0.1:8004`.

The backend needs the PostgreSQL connection and webhook secret described in the
root README. Frontend installation does not create a runtime database, edit
`.env`, register a webhook, or enable demo sending. The API remains bound to
`127.0.0.1:8004`; the web entry forwards the webhook POST,
and the API retains its existing webhook-secret validation.

The frontend's only dependency is locally served PDF.js, pinned by the lockfile.
There are no external fonts, image services, analytics, or CDN requests. If you
already installed the frontend dependencies in this checkout, `node
frontend/server.mjs` is sufficient to start it.

## Review without provider credentials

Phase 4 repeatable acceptance is available with `node frontend/tests/journeys.mjs`
from the repository root. It launches the actual UI/proxy/API on ephemeral
localhost ports, uses a temporary SQLite test adapter and mocked Runpod HTTP and
Telegram, and closes the servers when finished. It requires existing Playwright
and Edge (`QF_PLAYWRIGHT_MODULE` can identify an installed module;
`QF_BROWSER_CHANNEL` and `QF_TEST_PYTHON` are optional overrides). It never reads
`.env`, accesses runtime records or sends customer messages. See
[Phase 4 evidence and commands](../docs/V2_INTEGRATION_PROGRESS.md).

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
