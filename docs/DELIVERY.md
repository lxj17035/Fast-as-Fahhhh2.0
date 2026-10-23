> Current merged contract: [PM approval](PM_APPROVAL.md); combined merge evidence: [merge review](MERGE_REVIEW.md). Historical branch test counts below are not the merged result.

# Part 3: PM-approved PDF delivery

The existing FastAPI application now reuses Xinjie's real settings, drafting,
quotation and saved-PDF services. Their storage interface is adapted to the same
SQLAlchemy/PostgreSQL database as enquiries and delivery attempts. No second
HTTP server or SQLite application is started. See [source provenance](XINJIE_SOURCE.md).

## Setup and demo approval

Install `.[test]` and follow [the application setup](TELEGRAM.md). Startup adds
`quotation_records`, `activities` and `send_attempts` to the shared database. Existing enquiries
remain the source of original text and chat IDs; there is no duplicate enquiry store.

`ENABLE_DEMO_APPROVAL=false` by default. For a supervised local test, enable it
and provide the server's `TELEGRAM_BOT_TOKEN`. The header `X-Demo-Actor: pm` selects
the simulated PM; `sales` is rejected by the send handler. This is impersonable
demo identity, not production authentication or proof of human approval. Keep
these routes local/restricted. AI must not call the send endpoint. Production
requires trusted identity and a human approval flow.

## Reused service routes

| Route | Contract |
| --- | --- |
| `GET/PATCH /api/settings` | Xinjie's fictional business defaults |
| `GET/PATCH /api/clients/{id}` | Existing seeded client; initially `demo-client` |
| `POST /api/enquiries/{id}/draft` | `{"manual":true}` creates a saved manual draft |
| `GET/PATCH /api/quotations/{id}` | Read/update with Xinjie's camelCase versioned contract |
| `GET /api/quotations/{id}/pdf?version=N` | Preview/cache the exact saved version |
| `POST /api/quotations/{id}/send` | Explicit PM approval of the previewed version |

Authenticated receipt now schedules automatic drafting. Both automatic and explicit
draft requests reuse one service and the existing `quotation_records` table.
Configured OPENAI_API_KEY/OPENAI_MODEL enable the current OpenAI extractor; blank
values yield a labelled manual fallback. RunPod support is still pending.

Unknown Telegram senders receive distinct empty client records, rather than being
associated with the seeded demo client. The PM reviews and fills their details.
Company/client snapshots remain unchanged when settings later change.

Quotation services return their existing 32-character UUID hex IDs. Route UUIDs
accept that format or the equivalent hyphenated UUID. Delivery normalizes IDs
consistently so the same quotation cannot bypass duplicate protection through
alternate spellings. Provider chat/update/message IDs remain decimal strings in
enquiry responses to preserve JavaScript integer precision.

Example pricing PATCH (use the current saved version):

```json
{
  "version": 1,
  "client": {"name": "Example Print Customer", "address": "12 Demo Road"},
  "items": [{"description": "Printed T-shirts", "quantity": "20", "unitPrice": "25.00"}],
  "missingInformation": []
}
```

The result is saved version 2 with total `500.00`. Fetch its PDF with `version=2`,
then have the PM explicitly approve it:

```json
{"expected_version": 2, "approved": true}
```

The send request accepts no recipient, PDF URL or role override. A PDF must already
be cached for that version; the first PDF preview is never generated during send.
After edits, preview the newly saved version again. No separate preview-confirmation
service is needed.

## Validation and atomic reservation

`XinjieQuotationProvider` calls Xinjie's readiness validation and `begin_send` in
the same transaction as the approval/send-attempt record. Missing client/item
fields, unresolved `missingInformation`, invalid quantities/prices, expiry, stale
versions, missing cached previews and locked quotations prevent sending. Additional
delivery checks enforce finite positive quantities, explicit nonnegative prices,
nonblank descriptions, current dates, matching PDF version/signature and a 10 MiB cap.
Expiry is inclusive in `Asia/Kuala_Lumpur`.

All wrapper mutations and send reservations share a transaction lock. PostgreSQL
uses a short advisory transaction lock; nested service transactions join the outer
SQLAlchemy transaction and never commit it independently. This preserves Xinjie's
serialized mutation semantics across workers, including concurrent first drafts
and settings seeds. The lock is released before the external Telegram call. The
persisted `sending` state then blocks quotation edits. SQLite remains a test adapter
with an in-process lock, not the deployed database.

The sender obtains the destination exclusively from the quotation's linked
enquiry and original Telegram receipt. It saves the approval actor/time/version,
exact PDF bytes and SHA-256, plus a `pending` attempt before network delivery.
The enquiry becomes `unknown`, including while the request is in flight.

## Outcomes and retries

| HTTP | Meaning |
| --- | --- |
| 200 | `sent`: Telegram accepted the document; not proof of reading |
| 202 | `unknown`: verify the team-controlled chat; do not resend |
| 502 | `failed`: explicit Telegram rejection |
| 401 / 403 | Unknown demo actor / Sales cannot approve |
| 404 | Saved quotation missing |
| 409 | Stale/missing preview, locked quotation or previous attempt |
| 422 | Invalid approval/quotation or missing original chat |
| 503 | Approval disabled, token absent, storage/preparation failure or unsaved outcome |

Responses after an attempt include `attempt_id` and `status`. One Telegram
`sendDocument` multipart request is made with explicit timeouts, no redirects,
no proxy environment and no transport retries. Timeouts/network ambiguity,
malformed responses and server errors are unknown; confirmed 4xx API rejection
is failed. Error descriptions and credentials are not stored or returned. The
transport avoids HTTPX's INFO URL log because Telegram embeds the token in its URL.
See [Telegram's sendDocument contract](https://core.telegram.org/bots/api#senddocument).

Final persistence updates the attempt, enquiry and Xinjie quotation state in one
transaction. Outcomes map to Xinjie's `accepted`/`failed`/`uncertain`, including
the Telegram message reference. If persistence fails after sending, the response
is 503 with `status:unknown`; the durable pending attempt still blocks resending.

A unique quotation reference blocks subsequent attempts, including another saved
version and known failed sends. This delivery policy is stricter than Xinjie's
standalone known-failure retry support. There is no retry endpoint. Agree a future
reconciliation policy before allowing retries; never delete attempt rows merely
to resend. Pending attempts after crashes must not be automatically resumed.

Enquiry detail includes safe `delivery_attempts` with state, timestamps, provider
reference and `requires_verification` for pending/unknown. Pending means processing
or unresolved. PDF bytes are not exposed there. The inbox therefore retains the
unconfirmed outcome after reload. Part 4 now adds [persistent activity history](ACTIVITY.md)
in the same transactions as receipt, drafting, edits, approval and outcomes.

## Verification boundary

The integration tests use Xinjie's actual services and ReportLab renderer, the
shared database, and a mocked Telegram transport. Live Telegram registration and
delivery require separate approval. No live AI or Telegram claim follows from
passing these tests. Frontend integration and the complete live journey remain
final QA work.

### Part 3 verification — 23 October 2026

- Full suite: **232 passed** in 23.74 seconds on Python 3.14.7, SQLite and
  PostgreSQL 18.6. All Telegram calls were mocked; manual drafting did not call AI.
- Actual service integration exercised receipt → saved manual draft → pricing →
  versioned PDF preview → PM approval → mocked delivery → persisted outcomes.
- PostgreSQL cases exercised advisory locking through independent pooled
  connections, including simultaneous drafts and an edit/send race. This is not
  a multi-process load or production resilience test.
- Verified exact cached-PDF delivery, stale preview rejection, immutable sent
  snapshots, missing information, invalid quantities/prices, expiry, duplicate
  prevention, rollback, outcome-save failure and visible pending-state recovery.
- All six imported service modules match Xinjie's source commit byte-for-byte.
- Independent integration review found no blocking defects. Compilation, package
  installation, Git whitespace checks and a targeted credential-pattern check passed.
- Rendered the integration test's saved PDF with Poppler and visually inspected it;
  template source was unchanged.
- One existing Starlette/HTTPX test-client deprecation warning remains.
- The isolated PostgreSQL server was stopped after testing. No live Telegram or
  AI verification is claimed. Frontend and complete live workflow remain final QA.
