# Xinjie's backend handoff

## Implemented scope

Python 3.11+ backend with SQLite, editable business/client details, versioned quotations, exact totals, calendar validity, structured AI extraction/manual fallback, cached saved-version PDFs, and a local HTTP API.

The frontend, real Telegram webhook/send integration, PM approval/send activity events, and email are not implemented here. The `/api/demo/enquiries` route is explicitly simulated (`source: demo`); it never receives a real Telegram message. Draft creation records one system activity event. Sweeway owns remaining activity events and transport.

## Setup (PowerShell from repository root)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# Only if .env does not already exist:
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m backend.server
```

The API binds to `127.0.0.1:8004`. This is a supervised local synthetic-data demo with no production authentication. Keep it local. The frontend can run on localhost/127.0.0.1 ports 3000, 5173, or 8004; those origins receive CORS access. The backend does not serve frontend files.

The local `.env` already contains placeholders. Add real values there only. Existing process environment overrides `.env`; the loader supports `KEY=value`, optional surrounding quotes, and whole-line comments, without interpolation or shell execution. No extra dotenv dependency is required.

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Private server-side provider key; blank produces manual fallback |
| `OPENAI_MODEL` | Account-accessible Responses model supporting structured outputs; deliberately no assumed model |
| `QUOTATION_DB` | SQLite path, default `data/quotation.sqlite3`, relative to repository root |
| `PORT` | Local API port, default 8004 |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` | Reserved for Sweeway; unused by Xinjie's backend |

AI requests use [official Responses structured output](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses). No live provider request has been verified. Without credentials or on refusal/failure, the original enquiry is retained and the returned quotation has `draftMode: manual` and a safe `draftError` explanation. Explicit manual mode does not call AI. No fixture is presented as live AI.

## Run tests by section

```powershell
python -m unittest tests.test_settings -v
python -m unittest tests.test_quotations -v
python -m unittest tests.test_drafting -v
python -m unittest tests.test_pdf tests.test_api -v
python -m unittest discover -s tests -v
python -m scripts.demo_pdfs
```

PDF tests require `requirements-dev.txt`. Samples are generated in ignored `output/pdf/`. Fonts support Latin text and Chinese through ReportLab's CJK font support; arbitrary emoji and every writing system are not promised. Test actual customer-facing scripts/fonts before deployment.

Tests use temporary/in-memory databases, a local test HTTP server, and mocked AI transport. They do not send messages or use real secrets. See XINJIE_CHECKLIST.md for verified counts and remaining checks.

## HTTP contract

Send JSON with `Content-Type: application/json` for POST/PATCH, including `{}` when no fields are needed. Money is returned as decimal strings, not floating-point totals. Null quantity/price/total means unknown, not zero.

| Method / path | Input / result |
| --- | --- |
| `GET /api/health` | Local-demo status |
| `GET /api/settings` | companyName/companyAddress/currency/defaultValidity/timezone |
| `PATCH /api/settings` | Partial companyName/companyAddress/currency/defaultValidity; timezone is fixed |
| `GET /api/clients/demo-client` | Fictional seeded client |
| `PATCH /api/clients/:id` | Partial name/address for an existing client |
| `POST /api/demo/enquiries` | `{ "text": "Need 20 fictional shirts", "clientId": "demo-client" }`; returns enquiry with id |
| `GET /api/enquiries` | Local persisted enquiry list (integration scaffold) |
| `GET /api/enquiries/:id` | Enquiry plus context, quotations, and activity |
| `POST /api/enquiries/:id/draft` | `{ "manual": false }` for AI/fallback; `true` for explicit manual; repeated requests return existing draft |
| `GET /api/quotations/:id` | Saved quotation and version |
| `PATCH /api/quotations/:id` | Current version plus allowed client/items/issueDate/validity/notes/missingInformation changes |
| `GET /api/quotations/:id/pdf?version=2` | PDF bytes; header `X-Quotation-Version: 2`; use expected version to reject stale preview requests |
| `POST /api/quotations/:id/send` | Intentionally returns 501 until Sweeway supplies the send integration |

PDF rendering caches bytes per saved quotation version. Save changes, refresh the PDF preview using the returned version, then approve that version. Do not include derived fields (`total`, `lineTotal`, expiry, status, company, currency) in PATCH. The API rejects unknown fields.

Example quotation edit:

```json
{
  "version": 1,
  "client": { "name": "Example Events", "address": "12 Demo Road" },
  "issueDate": "2026-10-23",
  "validity": "1m",
  "items": [
    { "description": "Printed T-shirts", "quantity": "20", "unitPrice": "25.00" }
  ],
  "missingInformation": [],
  "notes": "Fictional demo quotation"
}
```

Result: version 2, total `500.00`, expiry `2026-11-23`. Draft edits allow unknown fields to remain blank, but send validation blocks unresolved required information. Resolve or explicitly dismiss `missingInformation` during PM review. Prices allow two decimal places; quantities allow three; line amounts round half-up to two decimals and totals sum rounded line amounts. Demo currency amounts assume two decimal places.

Errors return `{ "error": "message", "fields": {} }`. Invalid data -> 422 (field errors included when checking readiness); malformed JSON -> 400; unsupported content type -> 415; missing records -> 404; stale/locked version -> 409; non-PM send validation -> 403. Failed AI processing returns a saved manual draft, not a fabricated AI success. Unexpected server errors return a generic 500.

## Sweeway integration boundary

1. Use the shared `Store` instance. Persist normalized enquiry records under `enquiries` with `id`, combined original `text`, existing `clientId`, `source`, `chatId`, and status; add provider identifiers and message history as needed. Deduplicate provider updates and preserve source chat identity. New clients need a creation path in Sweeway's ingestion before drafting; current routes only edit seeded/existing clients.
2. Call `app.drafts.create(enquiry_id)`. Repeated calls return the existing quotation; this intentionally avoids overwriting PM edits. Later customer messages must be shown to the PM and reconciled manually in this MVP.
3. In the future send handler, require explicit PM approval of the current previewed version and latest messages. Simulate actor/role only for this controlled demo; do not treat client-provided roles as trusted production identity.
4. Call `app.quotations.begin_send(id, version, actor, role)` to atomically validate and reserve one send. It blocks Sales, missing details/prices, expired/stale quotations, and duplicate approval attempts.
5. Retrieve exactly that version's bytes with `app.pdfs.get(id, version)` and send to the stored original chat; do not accept AI/request-provided recipient overrides. Handle PDF retrieval failure before calling the provider by recording a known failed attempt.
6. Call `app.quotations.record_send_result(id, outcome, provider_reference)` with `accepted`, `failed`, or `uncertain`. Acceptance is not proof of reading. Only known failures may retry; unknown outcomes block blind resend.
7. Persist receipt, approving actor/time, and outbound result events in `activity`. The begin/result helpers change quotation state but do not supply Telegram transport or its activity records. Do not claim the full audit journey is complete before these are wired up.

Sent/sending/uncertain quotations are locked. A known failed quotation can be edited or retried; sent quotation details and PDF bytes remain unchanged by later client/company settings edits.

## Review commits

Run `git log --oneline feat/xinjie` to find the small commits. Use `git show <commit>` to review one section. No push, deployment, or live API verification is implied by these local commits.
