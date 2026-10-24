# QuoteFlow (Working Title)

> An assisted quotation workflow for small businesses that turns customer enquiries into editable drafts while keeping a PM in control of pricing and sending.


Updated 23 October 2026 against the supplied Domain 2 challenge brief.

**QuoteFlow** is a proposed name for the team's next discussion; it is not final. Other options are EnquiryFlow, QuoteBridge, and ReplyReady.

Built for the **Orbyte Smart SME Challenge: Less Busywork, Better Business (Domain 2)**.

## Team information

| Field | Details |
| --- | --- |
| Team name | Fast as Fahhhhh |
| Domain | Domain 2 - Orbyte Smart SME Challenge |
| SDG track | SDG 8 - Decent Work and Economic Growth; intended contribution to productivity (8.2) and small-enterprise growth (8.3) |
| Team leader | LIM XIN JIE |
| University / Institution | EDUVO Academy |
| Number of members | 3 |

| Contributor | Responsibility |
| --- | --- |
| Xinjie | Business/client settings, AI extraction, quotation rules/storage, backend PDF generation |
| Sweeway | Telegram receive/send integration, enquiry source tracking, send activity, optional email alerts |
| YieXian | Frontend inbox/editor, PDF preview, simulated role controls, activity display |

## Project links

| Resource | Link or status |
| --- | --- |
| GitHub repository | [Fast-as-Fahhhh2.0](https://github.com/lxj17035/Fast-as-Fahhhh2.0) |
| Replit project | Not set up yet - link pending |
| Hosted live demo | Not deployed yet - link pending |
| RunPod endpoint | [GLM-5.3 public API base](https://api.runpod.ai/v2/b1dd8hy2hqo1nb/openai/v1); local synthetic extraction verified |
| Pitch slides | Not created yet - link pending |
| YouTube pitching/demo video | Not recorded or uploaded yet - link pending |

The GitHub URL is taken from this repository's configured remote. Submission links above will be added when available; they are not working deliverables yet. The localhost API described below is a development backend, not a hosted demo.

## Overview

Small sales teams often receive customer enquiries in messages, copy details into documents, calculate prices manually, and keep track of replies themselves. This repeated work can delay quotations and leave interested customers without follow-up.

Our proposed product connects the enquiry with business/client information, drafts the quotation content, and puts it in a review workflow. A PM checks the requirements, enters prices, previews the PDF, and approves sending. The intended result is less copying and document preparation, consistent quotation details, and a visible record of what needs review and what was sent.

For a code-level explanation with Mermaid architecture and workflow diagrams, read [how the code works](docs/CODE_WALKTHROUGH.md).

The initial use case is a small printing business preparing quotations for items such as event T-shirts. The same workflow could serve repair shops and other service businesses by changing business settings and item descriptions.

## Intended workflow

1. A customer sends an enquiry to the business's Telegram bot.
2. The system stores the enquiry and connects it with client/company details and quotation defaults.
3. AI extracts the stated requirements, drafts item descriptions, and flags missing information. Prices remain blank.
4. The PM reviews the draft, edits client details, and enters quantities and prices.
5. The backend calculates totals and expiry; the PM previews the saved PDF.
6. The PM approves sending to the original Telegram conversation.
7. The system shows the outcome and records the action in an activity log.

Telegram is the selected first channel. WhatsApp, Instagram, and Facebook are future integrations. Email notifications are a stretch goal; the review inbox is the core alert mechanism.

**The backend journey and connected frontend are implemented and locally tested. Live verification with Member 2's credentials/test chat remains pending; a complete live demonstration is not yet claimed.**

## Current implementation status

| Component | Status |
| --- | --- |
| Editable business/client settings and PostgreSQL persistence | Implemented and locally tested |
| V2 B1: Printing/Cleaning/Repair profile persistence and pinned enquiry scope | Backend implemented; frontend selection remains pending. See [profile contract and checks](docs/BUSINESS_PROFILES.md). |
| Quotation drafts, exact totals, configurable validity, version checks | Implemented and locally tested |
| PM-role validation and send-state helpers | Implemented and locally tested; not a production identity system |
| AI extraction | Runpod GLM-5.3 integrated; one live synthetic extraction passed. OpenAI remains an optional mocked/tested alternative |
| Manual draft fallback | Implemented and locally tested |
| Saved-version PDF generation and local HTTP API | Implemented, tested, and sample layouts visually reviewed |
| Activity record | Receipt, draft, PM approval, and Telegram acceptance/rejection/uncertainty are persisted and exposed by read-only APIs |
| Frontend inbox, editor, settings, PDF display, role controls and activity | Implemented on `feature/frontend`; locally verified against the actual API with mocked providers |
| Telegram reception | Implemented; shares the database and application with quotations; live bot verification pending |
| Automatic drafting | Starts after persisted receipt; preserves existing PM edits on duplicate updates |
| Telegram document sending | Implemented with explicit PM approval and saved-preview/version validation; live verification pending |
| Replit deployment, video, and slides | Not prepared yet; Runpod public inference is configured |

The merged combined suite passed **423 tests**, with two PostgreSQL-only checks skipped for the SQLite adapter, using isolated adapters and a disposable PostgreSQL instance. This covers automatic drafting, PM approval, saved PDF upload, duplicate protection, and activity logging with mocked providers. Live AI and Telegram verification remains pending with Member 2. Tests use fictional records, local test servers, and mocked AI responses; they do not prove live provider or messaging integration.

## Key quotation rules

- Default validity: one calendar month. Available options: 7 days, 14 days, 1 month, 2 months, and 3 months.
- Validity is calculated from the selected issue date, with calendar-month clamping at month end.
- Client name/address and draft items are editable. Unknown information remains visible instead of being invented.
- The PM enters prices. AI cannot set prices, approve a quotation, or choose a recipient.
- The backend calculates totals using decimal arithmetic. Blank prices are distinct from explicitly entered zero prices.
- Stale edits, missing required details, expired quotations, and non-PM sending are blocked by the service helpers.
- Sent quotation details and cached PDFs remain unchanged when settings or client details change later.

## Technology

| Area | Current choice |
| --- | --- |
| Backend | Python 3.12+, FastAPI, and SQLAlchemy/Psycopg |
| Storage | Shared PostgreSQL via DATABASE_URL, locally and on Replit |
| AI adapter | Runpod GLM-5.3 Chat Completions with server-validated JSON; optional OpenAI Responses adapter |
| PDF generation | ReportLab |
| Tests | pytest, unittest, and pypdf; PostgreSQL integration coverage |
| Frontend | Responsive JavaScript ES modules, CSS, local PDF.js preview; no build step |
| Messaging | Telegram reception, automatic drafting, and approved PDF sending implemented; live bot verification pending |
| Hosting / RunPod | Replit pending; Runpod public inference verified locally |

## Run on Replit

The Replit Run command starts the existing Python API on `127.0.0.1:8004` and
one public web entry on `0.0.0.0:$PORT` (default `8080`). The web entry serves
the existing frontend and local PDF.js files, and proxies `/api/*` to the
private API without retries. The frontend uses same-origin API requests.

The UI and API open without a browser login for the organisers' synthetic demo
preview. `DEMO_ACCESS_USERNAME` and `DEMO_ACCESS_PASSWORD` are no longer required
or used. An application login page is deferred until after successful initial
screening. Anyone with the demo URL can use the simulated roles; use fictional
data and team-controlled test chats. Explicit PM approval is still required for
sending. The Telegram webhook continues to require the existing
`TELEGRAM_WEBHOOK_SECRET`. `/healthz` is public and returns only a
generic health status. Configure the existing `DATABASE_URL` and webhook secret
in Replit Secrets before running; AI and Telegram sending still depend on their
respective existing secrets. This setup does not register a Telegram webhook
or send messages.

`requirements.txt` lists only the runtime dependencies, with the exact constraints
from `pyproject.toml`'s `project.dependencies`; keep these lists synchronized.
The application itself runs from the repository rather than being pip-installed.
`PIP_USER=false` and `PIP_TARGET=.pythonlibs` direct pip into a writable project
directory. `PIP_TARGET` is configured in `.replit` and as a shared environment
variable inherited by production; the deployment build also passes
`--target .pythonlibs` explicitly. The backend adds the resolved target to
`PYTHONPATH`. The build installs locked frontend dependencies from
`frontend/pnpm-lock.yaml`. The single Run command supervises both processes and
stops the other if either one exits.

## How to run the backend

For an Ubuntu server using Docker, follow the [Docker + Ubuntu setup guide](docs/DOCKER_UBUNTU.md).
It includes frontend/API/PostgreSQL containers, private SSH access, persistence,
updates, and backup commands. The existing backend code remains unchanged.
For `hackathon.nailstore.online`, use the [Cloudflare Tunnel hosting guide](docs/CLOUDFLARE_UBUNTU.md).

Use PowerShell from the repository root, with Python 3.12 or newer and an accessible PostgreSQL database.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# Create the local config only if it does not already exist.
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

.\.venv\Scripts\python.exe -m backend.server
```

The API listens at **http://127.0.0.1:8004**. Check
**http://127.0.0.1:8004/api/health**. The public web entry serves the frontend
and proxies same-origin API calls. On Replit, use the single configured Run
command; locally, start the API and web entry separately as described below.

### Start the frontend

With Node.js 22.13+ and pnpm installed, run the existing locked dependency
install from the repository root:

```powershell
pnpm --dir frontend install --frozen-lockfile
```

The web entry listens on `0.0.0.0:$PORT` (default `8080`), serves the enquiry
inbox/editor/PDF preview/settings and local PDF.js files, and proxies `/api/*`
to `127.0.0.1:8004`. Pages and APIs are available without login for demo preview;
the Telegram webhook POST retains its secret validation. See
[frontend setup](frontend/README.md) for a
safe, isolated review fixture and [the frontend handoff](docs/FRONTEND.md) for
route and behavior details.

Frontend verification: **14 frontend checks and 7 real-API integration checks
passed**, with injected mocked AI/Telegram providers. Desktop/mobile layouts and
the saved PDF were visually checked. The existing backend suite passed **274
tests, 2 skipped** in the local SQLite-adapter run; PostgreSQL-only cases were not
rerun. Live provider verification remains separate.

### Backend approval configuration

For supervised Manager pricing, review and sending, set `ENABLE_DEMO_APPROVAL=true` before startup. Price changes require `X-Demo-Actor: pm`; Staff can prepare details while retaining existing Manager prices. For sending use that header with `{"expected_version": N, "approved": true}` after reviewing the current saved version. The final-review endpoint is `GET /api/quotations/:id/review?version=N`. Confirmed failures may be retried only after fresh PM approval referencing the failed `retry_of_attempt_id`. Enquiry detail exposes `can_retry`; duplicate approvals and pending/sent/unknown outcomes return 409. See [the current approval contract](docs/PM_APPROVAL.md); V2 AI/frontend and PDF-plus-summary orchestration remain later phases.

Set your private `DATABASE_URL` and `TELEGRAM_WEBHOOK_SECRET` in local `.env`
before starting. Both modules use this same PostgreSQL database. Set
`AI_PROVIDER=runpod` and your private `RUNPOD_API_KEY` for GLM-5.3. Defaults are
low reasoning, max 1024 output tokens and 100 attempted calls/day in the shared
database. Missing configuration, exhausted quota or provider failure produces
a labelled manual draft. The optional `AI_PROVIDER=openai` alternative uses its
own `OPENAI_API_KEY` and `OPENAI_MODEL`. The API always stays bound to
`127.0.0.1:8004`; `PORT` selects the public web-entry port.

Secrets belong only in `.env`, which is ignored by Git. `.env.example` contains placeholders. Keep this backend local: simulated roles are for the supervised prototype. FastAPI/Uvicorn runs the combined backend.

### Try the implemented flow without AI credentials

With the server running, open another PowerShell terminal in the repository root:

```powershell
$base = 'http://127.0.0.1:8004'
$enquiry = Invoke-RestMethod -Method Post -Uri "$base/api/demo/enquiries" -ContentType 'application/json' -Body (@{
    text = 'Example Events needs 20 printed T-shirts. Address: 12 Demo Road.'
} | ConvertTo-Json)

$quote = Invoke-RestMethod -Method Post -Uri "$base/api/enquiries/$($enquiry.id)/draft" -ContentType 'application/json' -Body '{"manual":true}'

$edit = @{
    version = $quote.version
    client = @{ name = 'Example Events'; address = '12 Demo Road' }
    items = @(@{ description = 'Printed T-shirts'; quantity = '20'; unitPrice = '25.00' })
    missingInformation = @()
} | ConvertTo-Json -Depth 5

# Enable demo approval before backend startup; this price edit is a simulated PM action.
$quote = Invoke-RestMethod -Method Patch -Uri "$base/api/quotations/$($quote.id)" -Headers @{ 'X-Demo-Actor' = 'pm' } -ContentType 'application/json' -Body $edit
$quote.total # Expected: 500.00 in the seeded demo currency (MYR).

New-Item -ItemType Directory -Force output/pdf | Out-Null
Invoke-WebRequest -Uri "$base/api/quotations/$($quote.id)/pdf?version=$($quote.version)" -OutFile 'output/pdf/quotation-preview.pdf'
```

This creates a **simulated** enquiry (`source: demo`), a manual draft, and a priced PDF. It does not call Telegram or demonstrate live AI. To send a real document, the send endpoint requires configured bot credentials and explicit PM approval of the current saved PDF preview. Use only the authorized team test chat for live verification.

### Run tests and generate sample PDFs

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.demo_pdfs
```

Generated PDFs are stored under ignored `output/pdf/`. Runtime records live in PostgreSQL; SQLite is only used in explicit isolated test/offline adapters. Existing SQLite files are not automatically migrated or deleted.

## Orbyte fit, business benefit, and SDG

The product is designed as an enquiry-to-quotation module in an Orbyte-style connected business hub. Business context and roles are currently synthetic, team-defined assumptions; no live Orbyte API integration is claimed. The same module could be reused across SMEs with different company details and services.

We plan to compare manual and assisted preparation using the same fictional enquiries, measuring elapsed time, copying steps, and quotation errors. A 30% reduction in preparation time is a **target to test**, not an achieved result. The intended SDG 8 contribution is improved SME productivity and support for small-business growth.

## Demo boundaries and next steps

- Use team-created fictional business/customer records only.
- Review the frontend and have Member 2 verify the real receipt-to-draft-to-approved-PDF journey with private credentials and a controlled chat.
- Configure the real credentials privately and run `python -m scripts.check_live_config`; this reports configuration only, without printing secrets or calling providers.
- Prepare the hosted demo/Replit link, slides, and YouTube video; update the links table when ready.
- Confirm the final project name and event submission requirements before submitting.
- Keep production authentication, multi-tenancy, extra channels, payments, and advanced commercial rules outside this prototype.

## License

See [LICENSE](LICENSE).
