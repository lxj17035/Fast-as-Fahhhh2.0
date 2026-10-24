# QuoteFlow

> QuoteFlow helps Malaysian small business teams turn social and messaging enquiries into AI-assisted quotations with Staff preparation, Manager pricing, and approved PDF delivery.

Built for the **Orbyte Smart SME Challenge: Less Busywork, Better Business (Domain 2)**.

QuoteFlow addresses customer enquiries across social and messaging channels such as WhatsApp, Telegram, Instagram, and Facebook. The intended journey connects each enquiry to an AI-assisted draft, Staff preparation, Manager pricing and review, and approved quotation delivery. It keeps messages, quotation versions, delivery outcomes, and activity together.

**Demo scope:** Telegram is the implemented channel used to demonstrate this journey. WhatsApp, Instagram, and Facebook integrations are planned future extensions.

This README reflects the code in `origin/main` at `90a8491` (24 October 2026). The prototype uses fictional business/customer data and simulated roles for a supervised demo.

## Team Information

| Field | Details |
| --- | --- |
| Team Name | Fast as Fahhhhh |
| Team Domain | Domain 2 |
| Team leader | LIM XIN JIE |
| University | EDUVO Academy |
| Number of Members | 3 |
| SDG track | SDG 8: Decent Work and Economic Growth, especially productivity (8.2) and small-enterprise growth (8.3) |

## Links

| Resource | Link or status |
| --- | --- |
| Repository | [Fast-as-Fahhhh2.0](https://github.com/lxj17035/Fast-as-Fahhhh2.0) |
| Published demo URL | [QuoteFlow on Replit](https://fast-as-fahhhh-20.replit.app/) — recorded in the release handoff; current V2 publication and hosted verification remain pending |
| RunPod Endpoint | [GLM-5.3 API base](https://api.runpod.ai/v2/b1dd8hy2hqo1nb/openai/v1) |
| Slide Deck | Link pending |
| Demo Video | Link pending |

The published URL is not evidence that the latest source or complete live journey has been verified. See [release handoff](docs/V2_PHASE_HANDOFF.md).

## Overview

### Problem

Malaysian micro and small businesses receive customer enquiries across WhatsApp, Telegram, Instagram, and Facebook, then manually copy requirements from messages into quotations. Missing details, repeated edits, and unclear handoffs can delay replies and create inconsistent documents. Staff and managers need a shared view of what needs clarification, pricing, approval, or follow-up.

### Solution

QuoteFlow aims to connect social and messaging enquiries with stored business/client context. The current demo implements this through Telegram. AI extracts stated requirements, suggests draft items and clarification questions, and leaves unknown facts and prices for people to resolve. Staff prepares the quotation, while Manager controls pricing and approves the saved PDF and summary before delivery.

### Workflow (Telegram Demo)

1. **Receive:** Telegram receipt stores an enquiry and starts an AI draft or labelled manual fallback. Each enquiry retains its selected business profile: Printing, Cleaning, or Repair.
2. **Prepare:** Staff reads Messages, checks AI suggestions, asks clarification questions, and edits Quote. Incomplete requirements can be saved as drafts. AI preserves unknown information and leaves prices blank.
3. **Submit:** Staff explicitly selects Submit for review once requirements are complete and questions/assignments are resolved. The handoff records the saved quotation version and reviewed source IDs; prices and Staff PDF preview are optional.
4. **Price and review:** Manager (the simulated PM role) enters prices and saves. The backend calculates totals and expiry. Manager reviews the exact saved PDF and matching Telegram summary.
5. **Approve and send:** Manager explicitly approves delivery to the original Telegram chat. Changes invalidate the relevant saved review evidence; new customer requirements or Staff edits require another submission.
6. **Track:** The application records delivery and activity. Confirmed failures need fresh approval to retry. Pending or unknown outcomes block resending. If the PDF succeeds but the summary fails, the saved PDF stays frozen and only the matching summary can be retried.

The inbox also supports Needs Assignment, conversation history, and explicit Revision/Additional flows after sending. Switching the active profile changes the shared demo workspace without moving existing enquiries.

See [workflow](docs/WORKFLOW.md), [Staff/Manager approval contract](docs/PM_APPROVAL.md), and [code walkthrough](docs/CODE_WALKTHROUGH.md).

## Key Features

| Area | Current behavior |
| --- | --- |
| Business context | Editable business/client settings, three fictional profiles, PostgreSQL persistence |
| Inbox and conversation | Scoped enquiries, assignment, original messages, Staff clarification and activity |
| AI assistance | Runpod GLM-5.3 extraction/analysis, editable selected suggestions, manual fallback; optional OpenAI adapter |
| Quotation editor | Generic items with units/notes, blank prices, version checks, explicit Staff handoff and Manager pricing |
| PDF and final review | ReportLab PDF from the saved version, local PDF.js preview, matching saved summary |
| Delivery | Approved Telegram PDF/summary delivery, duplicate protection, confirmed-failure retry and uncertainty holds |
| Hosting configuration | Replit web/API launcher, Docker/Ubuntu packaging, optional Cloudflare Tunnel guide |

These features have local test evidence. Live Telegram delivery, current hosted V2 acceptance, and RP2 provider/usage verification remain incomplete. A historical synthetic Runpod request succeeded; it does not prove the complete hosted workflow.

## Quotation rules

- AI cannot set prices, choose recipients, approve, or authorize sending. Only Manager may price and approve.
- Unknown information remains visible; a blank price differs from an explicitly entered zero.
- The backend calculates totals with decimal arithmetic. One currency is used per quotation; no tax/discount engine is included.
- Default validity is one calendar month. Options are 7 days, 14 days, 1 month, 2 months, or 3 months. Calendar-month calculations clamp at month end.
- Sending requires complete validated details, nonnegative prices, an unexpired quotation, and current saved review evidence.
- Later settings/client changes do not alter historical sent quotations or their PDFs.

## Tech Stack

| Area | Stack |
| --- | --- |
| Backend | Python 3.12+, FastAPI, SQLAlchemy, Psycopg |
| Runtime database | PostgreSQL shared by quotation and Telegram modules through `DATABASE_URL` |
| AI | Runpod GLM-5.3 Chat Completions; optional OpenAI Responses adapter |
| PDF | ReportLab; locally served PDF.js for browser preview |
| Frontend | JavaScript ES modules and CSS; no frontend build step |
| Verification | pytest, pypdf, Node tests, isolated actual-API integration and browser journeys |

## Project Structure

```text
.
├── app/                     # FastAPI routes, Telegram integration, shared persistence
├── backend/                 # Quotation rules, AI adapters, PDF and review services
│   ├── server.py            # Local backend entry point
│   └── runpod.py            # Runpod Chat Completions adapter
├── frontend/                # JavaScript/CSS UI and Node web proxy
├── docs/                    # Contracts, setup, workflow and verification records
├── deploy/                  # Container/proxy configuration
├── scripts/                 # Replit launcher, demo PDFs and configuration checks
├── tests/                   # Backend unit/integration tests
├── .env.example             # Placeholder configuration
├── .replit                  # Replit run/deployment configuration
├── compose.yaml             # Docker deployment configuration
├── requirements.txt         # Runtime Python dependencies
├── requirements-dev.txt     # Development/test dependencies
├── LICENSE
└── README.md
```

The organiser's sample `src/` and `runpod/handler.py` are not used by this implementation. Required submission PDFs are still pending; a `submission/` directory has not yet been added.

## Architecture

```text
Customer Telegram message
          |
          v
Replit: Node web entry / FastAPI API <---- Staff / Manager browser
          |                    |
          v                    v
PostgreSQL             Runpod GLM-5.3 API
messages, versions,     requirement extraction,
review and delivery    analysis and suggestions
          |
          v
Saved quotation -> ReportLab PDF -> Manager review/approval
                                           |
                                           v
                              Original Telegram chat
```

The web entry proxies `/api/*` to the localhost-bound backend. Runpod provides AI inference; application code validates results and calculates totals. Manager approval authorizes outgoing quotation delivery.

## How to Run

### Option 1 — Run on Replit

Import this repository into Replit, install dependencies through the configured build, and configure the variables below in Replit Secrets. Supply a PostgreSQL database. Click Run: `.replit` starts `PORT=5000 node scripts/run-replit.mjs`, which supervises the private Python API and public Node web entry. This project uses `RUNPOD_API_BASE_URL` and `RUNPOD_MODEL`, rather than the sample's `RUNPOD_ENDPOINT_ID` variable.

See [Replit setup](docs/REPLIT_DEPLOYMENT_GUIDE.md) and the configuration table below. Running the app does not register a webhook or prove a published deployment is current.

### Option 2 — Run Locally

```powershell
git clone https://github.com/lxj17035/Fast-as-Fahhhh2.0.git
cd Fast-as-Fahhhh2.0
```


Requires Python 3.12+, Node.js 22.13+, pnpm, and an accessible PostgreSQL database. Run commands from the repository root in PowerShell.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
pnpm --dir frontend install --frozen-lockfile

if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Before starting, configure the following in your private `.env`:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Your PostgreSQL connection URL; required for runtime storage |
| `TELEGRAM_WEBHOOK_SECRET` | Your private webhook validation secret; required at startup |
| `AI_PROVIDER` | `manual` for no-provider drafting, `runpod`, or `openai` |
| `RUNPOD_API_KEY` | Required for Runpod calls; model/base URL defaults are in `.env.example` |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Required only for the optional OpenAI provider |
| `TELEGRAM_BOT_TOKEN` | Required for real Telegram operations |
| `ENABLE_DEMO_APPROVAL` | Set to `true` only for supervised Manager pricing/approval/sending |
| `LIVE_TEST_CHAT_ID` | Team-controlled chat used for separately authorized live verification |

Environment values take precedence over `.env`. Keep real credentials only in `.env` or hosting Secrets. Missing AI configuration, quota exhaustion, or provider failure yields a labelled manual draft.

Start the API:

```powershell
.\.venv\Scripts\python.exe -m backend.server
```

In a second terminal, start the frontend/web proxy:

```powershell
$env:PORT = '8080'
node frontend/server.mjs
```

Open [QuoteFlow locally](http://127.0.0.1:8080). The API stays bound to `127.0.0.1:8004`; its [health endpoint](http://127.0.0.1:8004/api/health) can be checked separately. The frontend serves local PDF.js assets and proxies same-origin `/api/*` requests to the backend. Starting these processes does not register a Telegram webhook.

The demo opens without login. Staff/Manager selection is simulated access control, so use fictional records and team-controlled test chats. The Telegram webhook still validates its secret.

For an isolated preview without provider credentials or runtime PostgreSQL, follow the QA-only fixture in [frontend setup](frontend/README.md). It uses temporary test storage and mocked providers.

## Hosting

On Replit, configure PostgreSQL and the private provider/webhook values in Secrets, then use the configured Run command. `.replit` sets the public web port to `5000`; the API remains private on `127.0.0.1:8004`. The launcher supervises both processes.

Runtime dependencies are declared in `pyproject.toml` and mirrored in `requirements.txt`. The Replit build installs Python packages into `.pythonlibs` and frontend packages from the pnpm lockfile. Hosted publication, dependency checks/security rescan, and the live acceptance journey still require verification.

- [Replit deployment guide](docs/REPLIT_DEPLOYMENT_GUIDE.md)
- [Docker and Ubuntu setup](docs/DOCKER_UBUNTU.md)
- [Cloudflare Tunnel hosting](docs/CLOUDFLARE_UBUNTU.md)
- [Pillow dependency remediation and hosted checks](docs/PILLOW_SECURITY.md)

## Run Tests

Run the repeatable checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --test frontend/tests/*.test.mjs
node frontend/tests/integration.mjs
```

Set `TEST_DATABASE_URL` to a **disposable PostgreSQL test database** to exercise the real driver alongside isolated SQLite test adapters. Never point tests at runtime or customer storage. Providers are mocked for local verification; SQLite is not a runtime fallback.

The latest recorded source verification is **679 backend tests passed, 5 skipped; 47 frontend tests passed; 10 mocked actual-API checks passed**, plus desktop/mobile browser checks. These are historical results from [the settings verification record](docs/SETTINGS_REDESIGN_20261024.md), not fresh runs for this README edit. Earlier journey evidence is in [local development](docs/LOCAL_DEVELOPMENT_20261024.md) and [V2 integration](docs/V2_INTEGRATION_PROGRESS.md).

Generate synthetic sample PDFs with:

```powershell
.\.venv\Scripts\python.exe -m scripts.demo_pdfs
```

Generated output is ignored under `output/pdf/`. Review rendered PDFs after layout changes and verify they match the saved quotation version. Live checks must be reported separately; [RP1](docs/V2_RUNPOD_RP1.md) records a historical successful Runpod request, while [RP2](docs/V2_RUNPOD_RP2.md) remains incomplete.

## How We Use Replit (Required)

Replit provides the configured demo app environment and a recorded published demo URL. The repository contains its run/deployment configuration and a launcher for the Node web entry and Python API. Private values belong in Replit Secrets. Current V2 publication and hosted acceptance remain pending; collaborative Multiplayer development is not claimed.

**Proof of use:** required PDF pending. Planned file: `submission/SDC2026_Fast_as_Fahhhhh_Replit_POU.pdf`. See [release handoff](docs/V2_PHASE_HANDOFF.md) for current evidence and limits.

## How We Use RunPod (Required)

The backend calls the provided Runpod GLM-5.3 OpenAI-compatible API for requirement extraction and analysis. It sends authenticated requests to the configured API base plus `/chat/completions`, validates returned JSON, and preserves human control of prices and approval. No custom serverless handler is deployed in this repository.

Integration variables are `RUNPOD_API_KEY`, `RUNPOD_API_BASE_URL`, and `RUNPOD_MODEL`, with token and daily-attempt limits in `.env.example`. See [the adapter](backend/runpod.py) and [Runpod configuration](docs/RUNPOD.md).

Request shape (illustrative only; not an additional verification call):

```http
POST https://api.runpod.ai/v2/b1dd8hy2hqo1nb/openai/v1/chat/completions
Authorization: Bearer <private RUNPOD_API_KEY>
Content-Type: application/json

{"model":"glm-5.3","messages":[{"role":"user","content":"Extract requirements from this fictional enquiry."}],"max_tokens":1024}
```

[RP1 evidence](docs/V2_RUNPOD_RP1.md) records one synthetic request with HTTP 200 and 1,362 total tokens on 24 October 2026. It does not establish hosted Telegram acceptance or billing evidence. RP2 remains incomplete.

**Proof of use:** required PDF pending. Planned file: `submission/SDC2026_Fast_as_Fahhhhh_Runpod_POU.pdf`. Existing Markdown evidence is not a substitute for the organiser's required submission PDF.

## Challenges & Learnings

- **Incomplete AI output:** server validation, visible missing information and a manual fallback keep drafts editable when AI cannot supply usable results.
- **Stale approvals:** quotation versions and reviewed source IDs bind the handoff and final review to the saved content.
- **Partial or uncertain delivery:** distinct delivery states prevent automatic duplicate sends and preserve the accepted PDF during summary-only recovery.
- **Local versus hosted evidence:** mocked tests verify repeatable behavior, while separate provider and release records identify what still needs live acceptance.

## Future Improvements

- [ ] Publish and verify the current V2 build and complete controlled Telegram/RP2 acceptance.
- [ ] Measure preparation time and errors with paired fictional-enquiry trials.
- [ ] Complete slides, demo video and required submission PDFs.
- [ ] Evaluate production identity, per-business isolation and privacy requirements after the supervised MVP.
- [ ] Extend the Telegram demonstration to WhatsApp, Instagram, and Facebook integrations after validating the core journey; email alerts remain optional.

## Team

| Name | Role | GitHub |
| --- | --- | --- |
| LIM XIN JIE (Xinjie) | Team lead; settings, clients, AI extraction/manual fallback, quotation storage/rules, PDF API | To confirm |
| Sweeway | Telegram receive/send, inbox integration, send activity, optional email | To confirm |
| YieXian | Frontend editor, preview, role controls, activity display | To confirm |

## Orbyte Fit and SDG Contribution

QuoteFlow is an enquiry-to-quotation module for an Orbyte-style connected business hub. Orbyte interfaces, business context, and staff roles are simulated; no real Orbyte integration is claimed.

The intended benefit is less copying, clearer review ownership, and consistent quotations for Malaysian micro and small businesses. A 30% reduction in preparation time is a target to measure with paired fictional-enquiry trials, not an achieved result. The intended SDG 8 contribution is improved SME productivity and support for small-business growth.

Current release work is to publish and verify the tested V2 build, complete controlled Telegram/provider acceptance and RP2 evidence, and prepare submission slides/video. Production identity, multi-tenancy, extra channels, queue infrastructure, payments, and advanced commercial rules are outside this MVP. The inbox is the core alert mechanism; email remains optional.

## Submission Checklist

- [x] Team name, Domain 2 and SDG track filled in.
- [ ] Slide deck link added.
- [ ] Demo video link added.
- [ ] Replit proof of use PDF added under `submission/`.
- [ ] Runpod proof of use PDF added under `submission/`.
- [ ] Preliminary submission completed: `SDC2026_Fast_as_Fahhhhh_Preliminary.pdf`.
- [ ] Technology declaration completed: `SDC2026_Fast_as_Fahhhhh_TechDeclaration.pdf`.
- [ ] All required PDFs use the confirmed team-name filename format.
- [ ] How to Run steps verified on a fresh local setup and current Replit build.
- [ ] Final repository secret review completed before submission.

Unchecked items require evidence or completion. Planned filenames use `Fast_as_Fahhhhh`; confirm the organiser's accepted team-name formatting before exporting the PDFs. Real secrets must remain outside Git.

## License

This project is licensed under the **Apache License 2.0**. See [LICENSE](LICENSE).
