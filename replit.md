# Running QuoteFlow on Replit

## Run command

The single project Run command is `node scripts/run-replit.mjs`. It manages:

- The existing FastAPI application bound only to `127.0.0.1:8004`.
- The authenticated frontend/web entry bound to `0.0.0.0:$PORT`, defaulting to
  port `8080`.

The frontend server serves the existing UI and locally installed PDF.js assets.
It proxies `/api/*` to the loopback API without retrying requests. The UI calls
the API on its own origin.

## Required Replit Secrets

- `DEMO_ACCESS_USERNAME`
- `DEMO_ACCESS_PASSWORD`
- `DATABASE_URL`
- `TELEGRAM_WEBHOOK_SECRET`

The public `/healthz` endpoint requires no authentication and returns only
`{"status":"ok"}`. All staff pages and API calls require HTTP Basic
authentication, except `POST /api/webhooks/telegram`, which keeps the existing
Telegram webhook-secret check. Do not put secret values in source files or
logs.

AI drafting and Telegram sending use their existing optional provider
configuration. Do not register a Telegram webhook or send messages as part of
local setup or deployment configuration.

## Deployment build

The configured build installs the Python package and runtime dependencies from
`requirements.txt`, then installs the locked frontend dependencies with pnpm.
