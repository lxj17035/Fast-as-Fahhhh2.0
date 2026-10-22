# Part 2: enquiry management

Use the same FastAPI application and PostgreSQL database as
[Part 1](TELEGRAM.md). No additional service or database is required.

## Persistence and upgrade

Each accepted Telegram text message creates one enquiry with a UUID `id`, source
`telegram`, status `needs_review`, and the original receipt timestamp. A unique
foreign key `telegram_update_id` links it to the immutable original receipt.
Original text, chat ID, message ID and update ID remain stored in that receipt.
Two distinct messages in the same chat create separate enquiries; no implicit
conversation grouping or customer matching occurs.

The receipt and enquiry commit together. If enquiry creation fails, neither new
row is saved, and the webhook returns a retryable failure. Duplicate delivery
does not create another enquiry or replace its status or original text.

Startup creates missing tables, then backfills enquiries for Part 1 receipts
before serving requests. Backfill preserves original receipt times and ignores
already-linked receipts. It can be repeated without overwriting existing records.
This is additive prototype setup, not a general schema migration system; initialize
the schema with one application instance before starting additional workers.

## Inbox API

`GET /api/enquiries?limit=50&offset=0`

`limit` must be 1–100; `offset` must be 0–9223372036854775807. Invalid values return 422.
Results are ordered by `created_at` descending, then `id` descending to break ties.
An empty page returns `items: []`. Offsets are not snapshots: newly received
messages may shift page boundaries between requests.

Illustrative response (fictional data):

```json
{
  "items": [{
    "id": "ea28df69-5682-462c-996e-05012137eace",
    "source": "telegram",
    "status": "needs_review",
    "created_at": "2026-10-23T00:00:00Z",
    "telegram_chat_id": "-1001234567890",
    "original_text": "Example Print Customer needs 20 printed T-shirts."
  }],
  "limit": 50,
  "offset": 0
}
```

## Detail API

`GET /api/enquiries/{id}`

Returns the same enquiry fields plus `messages`, currently one original message:

```json
{
  "update_id": "10001",
  "message_id": "42",
  "chat_id": "-1001234567890",
  "text": "Example Print Customer needs 20 printed T-shirts.",
  "received_at": "2026-10-23T00:00:00Z"
}
```

The object above is an element of `messages`, not the complete response.
Unknown enquiry UUIDs return 404; malformed UUIDs return 422. Storage failures
return a generic 503 without SQL, credentials or customer content. All response
timestamps are UTC. Provider identifiers are decimal **strings** so JavaScript
clients preserve integer precision; do not convert them to JavaScript numbers.

## Status and team handoff

New enquiries are `needs_review`. The database permits future `sent`, `failed`,
and `unknown` delivery states, but Part 2 exposes no status-changing endpoint and
does not claim a send occurred. Part 3 will set these states from actual outcomes.

YieXian can use the list and detail routes for the inbox. Xinjie can associate
quotations using the stable enquiry UUID and read the stored message through
the shared database. Business/client context, AI summaries, missing-information
analysis, quotations and activity history are not implemented or fabricated in
these responses; extend the contract as those modules become available.

The read APIs have no production authentication. Keep the app bound to localhost
or behind team-controlled access restrictions, using fictional data. If exposing
the webhook through a tunnel/proxy, expose only the webhook path, not these read
routes. Trusted identity, authorization and data isolation remain production work.

## Verification

Use the test instructions in [Telegram setup](TELEGRAM.md). With
`TEST_DATABASE_URL` set to a disposable PostgreSQL database, the same suite also
checks PostgreSQL behavior using isolated schemas. Tests make no Telegram calls.

### Part 2 results — 23 October 2026

- Python 3.14.7 and PostgreSQL 18.6: **107 tests passed** in 7.41 seconds,
  including the SQLite suite and Part 1 regressions.
- Verified atomic receipt/enquiry rollback, concurrent duplicates, persistence
  after restart, repeated/concurrent backfill, preserved status and timestamps,
  identifier precision, pagination, missing records, and safe storage errors.
- Independent review identified an oversized-offset edge case; it was fixed by
  bounding the offset to signed 64-bit range and adding a rejection test.
- One existing Starlette/HTTPX test-client deprecation warning remains.
- No live Telegram calls were made; the isolated PostgreSQL test server was stopped.
