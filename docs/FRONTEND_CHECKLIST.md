# Frontend implementation — feature/frontend

Frontend-only work. Existing Python code and API contracts remain unchanged.
No deployment or Git push is part of this work.

## 1. Foundation and API client

- [x] Dependency-free ES modules, local static server on 127.0.0.1:5173.
- [x] API client targets the existing FastAPI server on 127.0.0.1:8004.
- [x] Preserve nullable prices, quotation versions, PM approval and exact retry links.
- [x] Test API payloads, server file restrictions, and approval guards.

Verification: `node --test frontend/tests/*.test.mjs`: **11 passed**.
`git diff --check` passed. No backend files changed.

## 2. Connected workspace

- [x] Inbox, current-page search/filter, pagination, loading/error/empty states.
- [x] Message context, quotation editor, explicit saved PDF preview, PM approval.
- [x] Delivery history, confirmed-failure retry, uncertainty guards and activity.
- [x] Business settings and existing-client editing.
- [x] Responsive layout, keyboard access and unsaved-edit protection.

Verification: **12 frontend tests passed**; JavaScript syntax and whitespace checks
passed. Browser exercised the actual FastAPI app with a temporary SQLite test
adapter and injected synthetic AI/Telegram providers: price/save, MYR 500.00,
saved-version PDF, PM confirmation, explicit rejection, linked approved retry,
accepted-send lock, chronological activity, settings save and client load/save.
The in-app browser did not render native PDF embeds, so the workspace now uses
locally installed PDF.js to render the exact backend PDF bytes. The saved PDF was
visually verified in the canvas preview. There are no CDN dependencies.

The foundation started without third-party browser dependencies; PDF.js is now
the one frontend dependency, pinned in package.json and pnpm-lock.yaml.

## 3. Verification and handoff

- [x] Browser checks using actual FastAPI with explicitly mocked providers; no live provider calls.
- [x] API integration verification using the shipped JavaScript client and isolated Python app.
- [x] Setup and limitation documentation; backend changes verified absent.

Final evidence:

- `node --test frontend/tests/*.test.mjs`: **14 passed**.
- `node frontend/tests/integration.mjs`: **7 passed**. The runner creates its own
  temporary database, uses an ephemeral localhost port, and shuts down/cleans up.
- `.venv/Scripts/python.exe -m pytest -q`: **274 passed, 2 skipped**, one existing
  Starlette/httpx deprecation warning, 31.39 seconds. This run explicitly omitted
  TEST_DATABASE_URL; no live PostgreSQL database or external providers were used.
- Browser: real API reads and mutations; price/save and exact saved total;
  PDF.js canvas visibly matched the saved PDF; explicit PM approval; confirmed
  failure and linked retry; sent locking; company/client saving; literal escaped
  customer markup; cancelled navigation preserved unsaved pricing; unknown
  delivery locked editing/resend and stayed blocked after a full browser reload.
- Responsive screenshots at 1440px desktop and 390px mobile using ignored QA
  iframe harnesses. Mobile inbox shows status badges without horizontal scrolling.
  Temporary screenshots/harnesses are under ignored `.input/frontend-review/`.
- Improved malformed-delivery handling, unknown-outcome session guards, PDF
  pagination, small-screen item layout and reviewable CSS formatting.
- JavaScript syntax, whitespace and changed-file checks passed. Existing
  `app/`, `backend/`, `tests/`, Python dependency/config files and `.env.example`
  have no differences from `main`. No push or deployment performed.

Live Telegram/AI, real PostgreSQL integration in this environment, and hosted
deployment remain outside this verification. See FRONTEND.md for exact limits.

## 4. Code walkthrough and Mermaid topology

- [x] Added `docs/CODE_WALKTHROUGH.md` explaining the combined frontend/backend,
  startup, Telegram receipt, AI/manual drafting, forms/state, quotation rules,
  versioned PDFs, approved delivery/retry, storage, and activity.
- [x] Added nine Mermaid architecture, flow, sequence, state, and storage diagrams.
- [x] Linked the walkthrough from README.

Verification: all nine diagrams parsed successfully with Mermaid 12.2.0 using a
temporary DOM environment. Markdown fences are balanced and every local guide
link resolves. Validation packages/scripts remain under ignored `.input/docs-check/`;
no application dependencies changed. `git diff --check` passed. This section is
documentation only, so application tests were not rerun.

## 5. Simpler everyday use

### A. Inbox and settings

- [x] Replace dashboard clutter with three actionable inbox counts and four filters.
- [x] Distinguish Not sent from Check Telegram, while grouping both under Needs checking.
- [x] Give the empty inbox a clear first step and expandable connection help.
- [x] Keep business settings prominent; move client references and demo/connection controls into disclosures.
- [x] Increase working text/input sizes and use plain labels.

Verification: **16 frontend tests passed**; JavaScript syntax and whitespace checks
passed. Browser checked the running project's empty inbox and business settings;
no runtime records were changed. Backend code is unchanged.

### B. Guided quotation review

- [x] Show Details -> Preview -> Send and a single next-step explanation.
- [x] Add Save & preview without weakening version or explicit approval checks.
- [x] Keep delivery diagnostics and long activity histories out of the primary flow.
- [x] Verify edit/save/preview, sent/failed/unknown, mobile, and unsaved-edit behavior.

Verification: **22 frontend tests passed** and **7 isolated real-API checks passed**
with temporary storage and mocked providers. Browser review covered field-focus
links, reviewed facts, save/versioned PDF, Sales/PM guidance, an unsaved-navigation
cancel, fresh explicit approval, failed retry, sent locking, and uncertain-send
locking. Mobile inbox, PDF and approval were checked at 390px. Temporary QA
screenshots and harnesses are under ignored `.input/usability-review/`.
JavaScript syntax and whitespace checks passed. Backend code is unchanged;
no live provider calls, runtime database writes, push, or deployment were performed
for this usability update. The walkthrough and frontend handoff reflect the UI.

## 6. Docker packaging and Ubuntu handoff

- [x] Add Python and frontend/Nginx Dockerfiles without changing Python source.
- [x] Use the existing localhost-bound API through a shared Nginx network namespace.
- [x] Add Compose PostgreSQL persistence, health checks, bounded logs, and private host access.
- [x] Exclude local secrets, virtual environments, QA fixtures, and databases from image build contexts.
- [x] Document Ubuntu installation, server `.env`, build/start, SSH access, backups, updates, and Telegram ingress limits.

Verification: official **Docker Compose 5.6.1** accepted the configuration using
synthetic placeholder values. Checked loopback-only published web access, no
published database/API ports, the db service URL, and database readiness.
Official **Nginx 1.30.6 for Windows** accepted the config with only test paths and
listen address adjusted. A temporary listener passed **9 HTTP checks** for assets,
same-origin config, actual local API health forwarding, PDF worker MIME type, and
blocked private paths. It was stopped afterward. This does not establish Linux
image execution or the Docker shared network namespace at runtime.

**22 frontend tests and 7 isolated API checks passed** with mocked providers.
Python package wheel creation passed. The guide's Bash syntax, Mermaid topology,
relative links, Markdown fences, and whitespace checks passed. Validation tools
and fixtures are under ignored `.input/docker-check/` and `.input/docs-check/`.
The existing Python source and dependency declarations have no changes.

Docker Engine is unavailable on this Windows host. Image builds, Compose startup,
PostgreSQL container persistence/restarts, server SSH, and live providers were
**not run**. The Ubuntu guide provides the deployment-time verification commands.
No server deployment, real messages, or Git push was performed.

## 7. Cloudflare Tunnel domain handoff

- [x] Push `feature/frontend` to `origin` at the user's explicit request.
- [x] Add an optional `compose.cloudflare.yaml` connector with a private server token.
- [x] Document `hackathon.nailstore.online` -> HTTP `web:8080` and Cloudflare Access with a team email allowlist.
- [x] Add an optional, separate webhook hostname -> `web:8081`, serving only POST `/api/webhooks/telegram`.
- [x] Explain Ubuntu startup, Cloudflare zone/tunnel/routing, HTTPS, endpoint checks and maintenance.

Verification: official Compose 5.6.1 accepted the merged configuration using a
synthetic token. Checked four services, readiness dependencies, namespace sharing,
the webhook config mount and absence of additional published ports. Nginx 1.30.6
accepted both listeners with test ports/paths and an isolated mocked-provider
backend. **8 HTTP checks passed**: five private paths blocked, GET webhook
blocked, missing-secret POST rejected with 401, and staff API health forwarded.
The temporary listeners/backend were stopped; user development servers were left
running. **22 frontend tests passed**. Guide Bash syntax, Mermaid, local links,
Markdown fences and whitespace checks passed. Python source is unchanged.

Cloudflare dashboard/DNS/Access/HTTPS and Docker runtime have not been configured
or tested here. No tunnel token or live webhook was used. The new guide records
these limits and the server-side checks needed before a live demo.

## 8. Standalone server deployment instructions

- [x] Add `docs/SERVER_DEPLOYMENT_STEP_BY_STEP.md` for the user's exact hosting outcome.
- [x] Assume Docker is installed; include SSH, prerequisites, clone/update, private environment creation, Cloudflare Access/tunnel/routing, launch, and browser verification in one file.
- [x] Include full maintenance, backup, diagnostics and troubleshooting commands, plus a Mermaid topology and expected results.
- [x] Link the guide from README and distinguish prepared instructions from an actual remote deployment.

Verification: all Bash command blocks passed `bash -n`; Mermaid topology parsed;
relative links and Markdown fences passed. Official Compose accepted the exact
two-file configuration referenced by the guide using synthetic placeholders.
Whitespace checks passed. This section changes documentation only; application
tests were not rerun. No backend code, server configuration, real secrets, DNS,
Cloudflare account settings, or live messages were changed.

## 9. Reuse the user's existing Cloudflare Tunnel

- [x] Revise the standalone guide for an existing tunnel with the dashboard hostname not yet routed.
- [x] Reuse existing zone, tunnel, Access application and credentials where configured; preserve other routes.
- [x] Distinguish host-service, external Docker, and project Docker connectors, retaining origin port 8080.
- [x] Use COMPOSE_FILE in the server `.env` so startup and maintenance commands select the matching services.

Verification: Compose accepted both selections using synthetic placeholders:
three app services without a connector token for external connectors, and four
services for the project-managed connector. Bash syntax, Mermaid, relative links,
Markdown fences and whitespace checks passed. Documentation-only change;
application tests were not rerun. No tunnel, token, DNS record, server process,
application source, or Cloudflare account setting was changed.
