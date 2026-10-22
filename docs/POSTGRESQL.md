# Shared PostgreSQL setup

## Decision

PostgreSQL is the runtime database for both quotations and Telegram reception, including the planned Replit deployment. Configure one private DATABASE_URL. There is no runtime SQLite fallback and QUOTATION_DB is obsolete.

The combined FastAPI application serves both modules. `python -m backend.server` starts it on localhost port 8004. The standard-library handler remains only as a test harness for the quotation contract.

## Local configuration

1. Install Python 3.12+ and `python -m pip install -r requirements-dev.txt` in a virtual environment.
2. Copy .env.example to .env only if .env does not exist.
3. Add your own private DATABASE_URL and TELEGRAM_WEBHOOK_SECRET to .env. Keep actual passwords, keys, tokens, and connection strings out of Git and chat logs.
4. Optionally configure OPENAI_API_KEY and OPENAI_MODEL. Leaving these blank uses a labelled manual drafting fallback.
5. Start `python -m backend.server`; visit `http://127.0.0.1:8004/api/health`.

PostgreSQL URL schemes `postgresql://`, `postgres://`, and `postgresql+psycopg://` are normalized to the installed Psycopg driver. Encoded passwords and query options such as sslmode are preserved. Existing process environment takes precedence over .env. On Replit, supply the private connection through the environment; this change does not deploy the application.

The shared database must already exist. Startup creates missing prototype tables but does not create the database or alter existing schemas. Existing SQLite files are left untouched; no automatic import of older SQLite records is performed.

## Tables and handoff

- `telegram_updates`: original message content and provider identifiers.
- `enquiries`: normalized inbox records linked to receipts.
- `quotation_records`: PostgreSQL JSONB records for business settings, clients, quotation snapshots, cached PDFs, draft activity, and per-enquiry client context.

Quotation drafting reads the existing Telegram enquiry ID directly. Unknown senders receive distinct empty contact records for PM review; no customer identity is guessed. Source chat IDs and original messages are preserved. `/api/enquiries` keeps Sweeway's paginated snake_case API contract; quotation payloads remain camelCase as documented in XINJIE_HANDOFF.md.

Posting an enquiry does not yet automatically invoke AI. The explicit draft endpoint is connected to the shared records. Outbound PDF sending still returns 501 until implemented; receiving an enquiry and producing a draft/PDF is not a complete send demonstration.

## Verification

Run `python -m pytest -q` for the combined suite. SQLite is an explicitly injected adapter for fast isolated tests/offline PDF fixtures only. It is not a deployment database.

For real PostgreSQL coverage, set TEST_DATABASE_URL in the test process to a disposable test database, then run pytest. The fixture creates and removes unique test schemas there. Never point it to customer/team production data. PostgreSQL checks cover storage/reopen, JSONB, nested rollback, immutable PDFs, cross-instance approval serialization, Telegram receipt/enquiry regression tests, and shared enquiry-to-draft-to-PDF HTTP routes.

Runtime quotation writes use a transaction-scoped advisory lock for this small prototype. This preserves check-version-then-write behavior across application instances; it is deliberately simple and can be refined for higher throughput later.

References: [SQLAlchemy PostgreSQL/Psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html), [PostgreSQL transaction/advisory locking](https://www.postgresql.org/docs/18/explicit-locking.html).
