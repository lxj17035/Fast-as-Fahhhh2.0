> Merged integration: use [PM_APPROVAL.md](PM_APPROVAL.md) for the current send body/header and [MERGE_REVIEW.md](MERGE_REVIEW.md) for verification.

# Xinjie's backend handoff

## Implemented scope

Python 3.12+ backend with shared PostgreSQL via SQLAlchemy/Psycopg, editable business/client details, versioned quotations, exact totals, calendar validity, structured AI extraction/manual fallback, cached saved-version PDFs, and a local HTTP API.

Telegram reception and quotations now run in one FastAPI application and use the same DATABASE_URL. Automatic drafting, approved outbound PDF sending, and receipt/approval/outcome activity are implemented and tested. The frontend, real-credential end-to-end verification, and optional email remain pending. The `/api/demo/enquiries` route is explicitly simulated (`source: demo`); it never receives a real Telegram message. Receipt, draft, PM approval, and Telegram outcome events are persisted. Member 2 owns real bot credentials and controlled-chat live verification.

## Setup (PowerShell from repository root)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# Only if .env does not already exist:
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m backend.server
```

The API binds to `127.0.0.1:8004`. This is a supervised local synthetic-data demo with no production authentication. Keep it local. The frontend can run on localhost/127.0.0.1 ports 3000, 5173, or 8004; those origins receive CORS access. The backend does not serve frontend files.

The local `.env` contains user-specific configuration placeholders. Set DATABASE_URL and TELEGRAM_WEBHOOK_SECRET before starting. Add real values there only. Existing process environment overrides `.env`; the loader supports `KEY=value`, optional surrounding quotes, and whole-line comments, without interpolation or shell execution. No extra dotenv dependency is required.

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Private server-side provider key; blank produces manual fallback |
| `OPENAI_MODEL` | Account-accessible Responses model supporting structured outputs; deliberately no assumed model |
| `DATABASE_URL` | Required private PostgreSQL connection URL shared by Telegram and quotations; no SQLite runtime fallback |
| `PORT` | Local API port, default 8004 |
| `TELEGRAM_WEBHOOK_SECRET` | Required private secret for the unified application webhook |
| `TELEGRAM_BOT_TOKEN` | Optional for inbound receipt; required later for bot registration/outbound delivery |

AI requests use [official Responses structured output](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses). No live provider request has been verified. Without credentials or on refusal/failure, the original enquiry is retained and the returned quotation has `draftMode: manual` and a safe `draftError` explanation. Explicit manual mode does not call AI. No fixture is presented as live AI.

## Run tests by section

```powershell
python -m unittest tests.test_settings -v
python -m unittest tests.test_quotations -v
python -m unittest tests.test_drafting -v
python -m unittest tests.test_pdf tests.test_api -v
python -m pytest -q
python -m scripts.demo_pdfs
```

PDF tests require `requirements-dev.txt`. Samples are generated in ignored `output/pdf/`. Fonts support Latin text and Chinese through ReportLab's CJK font support; arbitrary emoji and every writing system are not promised. Test actual customer-facing scripts/fonts before deployment.

Tests use isolated adapters and optional unique PostgreSQL test schemas, local test HTTP servers, and mocked AI transport. They do not send messages or use real secrets. See XINJIE_CHECKLIST.md for verified counts and remaining checks.

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
| `GET /api/enquiries` | Shared Telegram inbox: paginated `{items, limit, offset}` with snake_case fields, described in ENQUIRIES.md |
| `GET /api/enquiries/:id` | Shared original-message detail, described in ENQUIRIES.md; quotation routes use camelCase payloads |
| `POST /api/enquiries/:id/draft` | Read the stored Telegram enquiry directly; `{ "manual": false }` for AI/fallback or `true` for manual; returns existing draft on repeat |
| `GET /api/quotations/:id` | Saved quotation and version |
| `PATCH /api/quotations/:id` | Current version plus allowed client/items/issueDate/validity/notes/missingInformation changes |
| `GET /api/quotations/:id/pdf?version=2` | PDF bytes; header `X-Quotation-Version: 2`; use expected version to reject stale preview requests |
| `POST /api/quotations/:id/send` | Explicit PM approval of current saved preview; original-chat-only delivery and duplicate protection; see PM_APPROVAL.md |

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

FastAPI quotation errors return `{ "detail": { "message": "Quotation request rejected", "fields": {} } }`; validation/delivery errors may have a string or list under `detail`. Invalid data -> 422 (field errors included when checking readiness); malformed JSON -> 400; unsupported content type -> 415; missing records -> 404; stale/locked version -> 409; non-PM send validation -> 403. Failed AI processing returns a saved manual draft, not a fabricated AI success. Unexpected server errors return a generic 500.

## Integrated delivery boundary

Telegram receipt and enquiry rows remain normalized in the shared database. Receipt now schedules automatic drafting after commit. Repeated receipts return existing drafts without overwriting PM edits; failed background work preserves the enquiry for manual retry or repeated receipt.

Use GET /api/enquiries/:id/quotation to retrieve the automatically generated draft. Unknown senders get distinct empty client records. Review/pricing remains manual. Display the saved PDF version, then use the explicit PM send payload documented in PM_APPROVAL.md. The integrated delivery handler reserves one attempt, uploads the cached bytes to the stored original chat, and persists the result/inbox status and activity together. Do not bypass it with low-level helpers.

GET /api/enquiries/:id/activity and GET /api/quotations/:id/activity expose chronological receipt/draft/approval/provider-result events. Provider acceptance is not proof of reading. All previous attempts block resending, including known failures; unknown outcomes require checking the chat.

Sent/sending/uncertain quotations remain locked. A known failed quotation can be edited, but the merged delivery endpoint does not permit a second attempt. Local mocked checks do not complete live AI/Telegram verification; Member 2 follows LIVE_TEST.md after filling private configuration.

## Review commits

Run `git log --oneline feat/xinjie` to find the small commits. Use `git show <commit>` to review one section. No push, deployment, or live API verification is implied by these local commits.

## PostgreSQL integration update

See POSTGRESQL.md for the shared schema, DATABASE_URL setup, test isolation, and remaining integration boundaries. The combined FastAPI application exposes Telegram reception, inbox, settings, clients, draft, quotation edit, and PDF routes on port 8004. Automatic drafting and approved outbound sending are implemented; live verification is the remaining delivery checklist item. Simulated `/api/demo/enquiries` records are for quotation API testing and are not included in the normalized Telegram inbox.
