# Part 4: persistent activity history

Activity records live in `activities` in the same database as enquiries,
quotations and delivery attempts. Startup creates the missing table using the
existing prototype bootstrap. No extra database or audit service is required.

## Recorded events

| Action | Result | Recorded with |
| --- | --- | --- |
| `telegram_received` | received | Original receipt and enquiry transaction |
| `enquiry_created` | created | Original receipt and enquiry transaction |
| `quotation_draft_created` | manual / ai | Xinjie's actual saved draft creation |
| `quotation_updated` | saved | Successful quotation PATCH and saved version |
| `pm_approved` | approved | Reserved quotation, approval and pending send attempt |
| `pdf_send_attempted` | pending | Same reservation transaction before Telegram |
| `pdf_send_succeeded` | sent | Persisted Telegram acceptance and quotation outcome |
| `pdf_send_failed` | failed | Persisted explicit rejection and quotation outcome |
| `delivery_unknown` | unknown | Persisted timeout/unconfirmed outcome |

An attempt means the local delivery workflow was initiated. It is not proof the
network request reached Telegram. A process interruption can leave only approval
and attempt events with a pending delivery. The enquiry's unknown state and
`delivery_attempts` remain visible; no success or failure event is invented.
Telegram acceptance does not prove the customer read the document.

## Event fields

- `id`: stable UUID event identifier.
- `enquiry_id`, optional `quotation_id`, `version`, and `attempt_id`: traceable links.
- `timestamp`: timezone-aware UTC time, serialized as an ISO timestamp.
- `actor_id`, `role`, `actor_origin`: actual recorded attribution.
- `action`, `result`: the event and observed local outcome.
- Optional `provider_reference` and `safe_error_code`: provider/update/message
  reference and an allowlisted diagnostic code.

System receipt/draft events identify the system. PM approval identifies the
explicit simulated PM. Quotation edits may use `X-Demo-Actor: sales` or `pm` when
`ENABLE_DEMO_APPROVAL=true`. Unknown header values are rejected; an explicit demo
actor while demo selection is disabled is rejected. Without that header, edits
remain compatible with existing callers and use null actor/role with origin
`unknown`. No identity is inferred from customer text or AI output. These demo
identities remain impersonable and are not production authentication.

Activities contain no customer message text, PDF bytes, bot token, raw exception
or provider error description. The enquiry detail already exposes the original
message separately for review; activity logging does not copy it into the timeline.

## Reading history

`GET /api/enquiries/{id}` now includes `activity`, ordered by UTC timestamp then
event ID. An enquiry with no recorded history returns an empty list. Each enquiry
returns only its own events. Quotation IDs use canonical UUID strings in activities;
they refer to the same UUIDs returned in hexadecimal by Xinjie's quotation routes.

Illustrative event (fictional identifiers):

```json
{
  "id": "14f3d583-f938-4a49-89f1-7daf75aaf153",
  "enquiry_id": "d6b52be3-f6f0-4356-9873-c08f987d883b",
  "quotation_id": "bca936c7-b132-44df-b9ce-dba779828d74",
  "version": 2,
  "attempt_id": "27c09413-f990-4b17-a87f-37e270f05698",
  "timestamp": "2026-10-23T00:00:00Z",
  "actor_id": "pm",
  "role": "pm",
  "actor_origin": "simulated",
  "action": "pm_approved",
  "result": "approved",
  "provider_reference": null,
  "safe_error_code": null
}
```

YieXian can render this timeline alongside messages, quotation preview and delivery
attempts. Treat all text as data and escape it in the UI. Read APIs remain limited
to the supervised local/team demo, pending production access controls.

## Atomicity, duplicates and retention

Application code only inserts activities; it exposes no edit/delete activity
endpoint. This is application-level append-only behavior, not a claim of database
tamper resistance. A database administrator or privileged SQL client can still
change rows. Production audit permissions and retention/deletion rules are future
work.

Receipt deduplication, existing-draft guards and send reservations ensure duplicate
requests do not produce another event sequence. The helper never upserts an event
to alter history. Xinjie's draft-created event is normalized in the Store adapter
using its original ID/time, while their imported service source stays unchanged.
New draft events are not duplicated into a second JSON activity store.

An activity-write failure rolls back its associated database mutation. Before
Telegram, approval/log failure prevents a send. After provider acceptance, an
outcome-log failure rolls back finalization, leaving the committed pending attempt,
reserved quotation and unknown enquiry state; automatic retries remain blocked.

There is no automatic historical reconstruction. Existing enquiries, saved
quotations, attempts and legacy JSON draft events remain intact, but missing
historical activity is not fabricated. New canonical history begins with recorded
operations after this feature is installed. Reopening the app does not invent
backdated approval, send or failure events.

## Part 4 verification — 23 October 2026

- **262 tests passed** in 28.75 seconds on Python 3.14.7, SQLite and PostgreSQL 18.6.
  Telegram delivery was mocked and live AI was disabled.
- Covered complete linked history, simulated/unknown actor attribution, duplicate
  webhooks/drafts/concurrent sends, restart persistence, scoped chronological
  history, legacy-history gaps and safe error codes.
- Injected logging failures verified rollback for receipt, draft, edit, approval
  and send initiation. Accepted-delivery logging failure preserved pending/unknown
  state and blocked resend without adding a false success event.
- Independent review found no blocking defects. Compilation, Git whitespace and
  targeted credential-pattern checks passed. Xinjie's source modules were unchanged.
- One existing Starlette/HTTPX test-client deprecation warning remains.
- The isolated PostgreSQL test server was stopped after testing. Frontend display,
  separately approved live Telegram testing, and final handover remain final QA work.
