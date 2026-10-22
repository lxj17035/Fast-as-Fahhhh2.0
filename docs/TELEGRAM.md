# Part 1: Telegram reception

The shared Python application receives text messages at `POST /api/webhooks/telegram`.
Part 2 adds [enquiry persistence and APIs](ENQUIRIES.md). Quotation services,
delivery, and activity history remain later parts.

## Setup

Use Python 3.12+ and one team-controlled PostgreSQL database shared by all modules.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
$env:DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@localhost:5432/sweeway"
$env:TELEGRAM_WEBHOOK_SECRET = "YOUR_RANDOM_SECRET"
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1
```

If Python's Windows alias fails, use an installed Python's absolute path. If pip
is unavailable, use `uv pip install --python .venv/Scripts/python.exe -e ".[test]"`.
`.env.example` lists configuration names. `.env` is ignored, but not automatically
loaded: set environment variables before launch. Use a random webhook secret with
1–256 letters, digits, underscores or hyphens. Keep `TELEGRAM_BOT_TOKEN` in the
server environment for bot setup and later sending. It is optional for reception;
this endpoint makes no Telegram calls. Never commit credentials.

Startup creates missing `telegram_updates` and `enquiries` tables; it does not
alter existing tables. Part 2 backfills enquiries for existing receipts. Run one
instance for initial schema setup. Future changes need migrations.

## API contract

Supply the matching `X-Telegram-Bot-Api-Secret-Token` header. Authentication runs
before reading or validating the body. Fictional example:

```json
{"update_id":10001,"message":{"message_id":42,"chat":{"id":-1001234567890},"text":"Example Print Customer needs 20 printed T-shirts."}}
```

| HTTP | Meaning |
| --- | --- |
| 200 `{"status":"received"}` | Original text and IDs committed |
| 200 `{"status":"duplicate"}` | Update already saved; no overwrite |
| 200 `{"status":"ignored"}` | Unsupported/non-text update; no row saved |
| 401 | Missing/incorrect secret |
| 400 / 422 | Malformed JSON / invalid message fields |
| 413 | Body exceeds 64 KiB |
| 503 | Storage failed; receipt is not acknowledged |

Text must be nonblank, at most 4096 characters, valid Unicode and contain no NUL.
Original whitespace is preserved. IDs must be integers without coercion; signed
chat IDs are supported. Edited messages, callbacks and attachments are outside
Part 1. Extra fields are ignored for provider compatibility. Errors do not echo
credentials, customer content or database details.

## Handoff

`app.main.create_app` mounts `app.telegram.router`. `telegram_updates` stores
`update_id` (primary key), `message_id`, `chat_id`, `original_text`, and UTC
`received_at`. The database arbitrates concurrent duplicates; success follows
commit. One bot per database is assumed; multiple bots need a composite key.

Part 2 now saves a linked enquiry in the same transaction as each new receipt,
preserving IDs and recording source as `telegram`. Startup backfills old receipts
without replacing existing enquiries. Each text message creates a separate enquiry;
new messages do not overwrite existing enquiries. Activity logging and teammate
modules remain unimplemented.

## Tests and live setup

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

To also run the API suite against PostgreSQL, set `TEST_DATABASE_URL` to a
disposable test database URL using `postgresql+psycopg://`. Tests create a uniquely
named schema per case and drop only that schema afterward. The database user must
have schema creation permission. Do not point this variable at production.
If sandbox temp-folder permissions interfere, pass
`--basetemp=.pytest_tmp` to pytest (pytest clears that test-only directory).

Tests use fictional messages. SQLite is only a portable test adapter; the normal
environment-configured application requires PostgreSQL. Automated tests do not
register webhooks, contact Telegram, or send messages.

Live setup requires separate approval and a team-controlled bot/chat. When approved,
configure `setWebhook` with an HTTPS URL ending in `/api/webhooks/telegram`, matching
`secret_token`, and `allowed_updates=["message"]`. See the official
[Telegram webhook documentation](https://core.telegram.org/bots/api#setwebhook).
Keep bot tokens out of scripts and logs.

Production follow-up includes trusted identity, API access controls, retention,
per-business isolation, rate limits, and privacy review. This supervised prototype
does not claim live Telegram verification or completion of the whole journey.

## Part 1 verification — 23 October 2026

- Python 3.14.7; PostgreSQL 18.6 in an isolated local test cluster.
- `pytest -q --basetemp=.pytest_tmp_final` with `TEST_DATABASE_URL` configured:
  **71 passed** (4.68 seconds), covering SQLite and PostgreSQL.
- Includes concurrent duplicates, app/connection restart, preserved original data,
  malformed input, secret checks, size limits, and retry after storage failure.
- Editable package installation, Python compilation, and Git whitespace checks passed.
- Independent architecture/integration review found no blocking defects.
- One dependency deprecation warning: Starlette plans to replace HTTPX in its
  test client. Current tests pass; revisit the test adapter on dependency updates.
- No live Telegram request or bot registration was performed. The test server was
  stopped afterward. Enquiry conversion and later modules remain unimplemented.
