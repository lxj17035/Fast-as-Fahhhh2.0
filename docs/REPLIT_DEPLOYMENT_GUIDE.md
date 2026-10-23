# Replit deployment guide and troubleshooting record

Recorded: 24 October 2026 (Asia/Kuala_Lumpur).

This guide records the deployment performed with the user on 23–24 October.
Replit changes and checks below were reported by the Replit Agent or supplied by
the user. They are not a claim that those remote changes exist in this local
checkout. Review and sync the Replit changes before reproducing this setup from
GitHub. No credentials or private chat IDs are included here.

## 1. Import the repository

1. Open [Replit Import](https://replit.com/import) and select GitHub.
2. Import the team's merged repository and confirm the intended branch/commit.
3. Select **Leave it as imported for now** if asked what Agent should do.
4. Open tools using **Tools** or the **+** next to Preview. Search for Shell,
   Secrets, or Database as needed.

Do not import a local `.env` into Git or paste credentials into Agent messages.

## 2. Configure the runtime

The imported runtime originally used Python 3.12 and Node 20. The frontend
requires Node 22.13 or newer. The verified Replit Node version was 22.23.4.

In the existing `.replit` modules list, preserve Python and web modules and
replace `nodejs-20` with `nodejs-22`. Reopen the Shell and check:

```bash
python --version
node --version
pnpm --version
```

The session used pnpm 10.26.1. Its optional upgrade notice did not require an
upgrade. Preserve the committed frontend lockfile.

## 3. Configure PostgreSQL and private environment values

Open **Database → Development Database → Settings**. The development database
was already Active and had a managed `DATABASE_URL`. Confirm the application
receives it; do not replace it with a URL pointing to a developer laptop.

Add the following in Secrets, without surrounding quotation marks in the UI:

| Name | Purpose |
| --- | --- |
| `DATABASE_URL` | Managed PostgreSQL connection; ensure production uses its production database |
| `TELEGRAM_BOT_TOKEN` | Team-controlled bot credential |
| `TELEGRAM_WEBHOOK_SECRET` | Private secret: 1–256 letters, digits, underscores or hyphens |
| `LIVE_TEST_CHAT_ID` | Team-controlled synthetic test chat; not a send-recipient override |
| `AI_PROVIDER` | `runpod` |
| `RUNPOD_API_KEY` | Private provider key |
| `ENABLE_DEMO_APPROVAL` | `true` for the supervised demo |
| `DEMO_ACCESS_USERNAME` | Staff entrance username |
| `DEMO_ACCESS_PASSWORD` | Strong staff entrance password |
| `PIP_USER` | `false`, as used in the final installation configuration |
| `PIP_TARGET` | `.pythonlibs`, also available to the early hosted installation phase |

Keep the existing provider base URL/model defaults only if they identify the
endpoint actually being used. A shared event endpoint is not evidence of an
endpoint owned by the team's RunPod account.

Replit had also generated `SESSION_SECRET`; it was retained. Its presence does
not establish that this application's Basic authentication uses it.

Check configuration in Shell:

```bash
python -m scripts.check_live_config
```

All checks passed in the user's Replit workspace. This validates presence and
format only, not connectivity, ownership, or actual delivery. Process environment
values take precedence over local `.env` values.

## 4. Configure one web entrance and two supervised processes

The Replit implementation reported these responsibilities:

| File | Responsibility |
| --- | --- |
| `.replit` | Runtime, workflow, deployment commands, environment and port mapping |
| `scripts/run-replit.mjs` | Start/supervise the web entrance and Python API; configure backend dependency path |
| `frontend/server.mjs` | Serve frontend/PDF.js, staff Basic authentication, API proxy, webhook exception and health route |
| `frontend/config.js` and frontend API code | Same-origin API requests rather than browser requests to localhost |
| `backend/server.py` | Keep the API on `127.0.0.1:8004` |

Routing:

```text
Browser / Telegram → Replit HTTPS → web entrance :5000
                                      → API 127.0.0.1:8004
```

Requirements for the entrance:

- Listen on `0.0.0.0:5000`; map internal 5000 to external 80.
- Serve frontend and locally installed PDF.js assets.
- Forward `/api/*` to port 8004 without automatic mutation retries.
- Protect staff UI and APIs with Basic authentication.
- Allow only the Telegram webhook POST route to bypass staff authentication;
  retain the backend's webhook-secret validation.
- Provide a non-sensitive `/healthz` route.
- Keep provider credentials server-side. Basic authentication and simulated
  Sales/PM roles are demonstration controls, not production identity.

Use this workflow/start command:

```bash
PORT=5000 node scripts/run-replit.mjs
```

Do not launch another copy while the workflow is running. The script's default
web port was 8080, so deployment must explicitly set 5000 to match the mapping.

## 5. Install dependencies in a writable project directory

The final reported `requirements.txt` lists the eight runtime dependency
constraints from `pyproject.toml`, without `.` or `-e .`. No runtime dependency
constraints were changed. Keep these two dependency declarations aligned.

Final reported build command:

```bash
bash -c "PIP_USER=false python -m pip install --target .pythonlibs -r requirements.txt && pnpm --dir frontend install --frozen-lockfile"
```

Final reported deployment start command:

```bash
bash -c "PORT=5000 node scripts/run-replit.mjs"
```

The runner prepends that exact `.pythonlibs` directory to the Python child's
`PYTHONPATH`; resolve it against the project directory. Ignore `.pythonlibs/` in
Git. A successful installation into a temporary directory is not sufficient:
test imports and startup using the actual configured directory.

The final configuration also includes:

```toml
[packager.features]
enabledForHosting = false
```

Earlier hosted logs still showed an automatic installation phase despite this
setting. Do not rely on it alone. The early phase must receive `PIP_USER=false`
and the writable `PIP_TARGET` too. Confirm this in the actual deployment logs.
The Replit Agent reported project guidance against virtual environments, so the
final approach uses a target directory rather than a venv or system-directory
permission override.

## 6. Verify before publishing

```bash
pnpm --dir frontend test
QF_TEST_PYTHON=python pnpm --dir frontend test:integration
```

The initial Replit checks passed 22 frontend tests and 7 isolated API checks.
After the entrance/authentication changes, the Agent reported 24 frontend tests
and 7 API checks passing. Providers in these tests are mocked; storage is
temporary. These checks do not prove live messaging or PostgreSQL behavior.

Also verify the exact build/start commands and these HTTP outcomes:

| Request | Expected outcome |
| --- | --- |
| `/healthz` | 200 with a small, non-sensitive response |
| Anonymous staff UI/API | 401 |
| Authenticated `/api/health` | 200, `status: ok` |
| Webhook POST without staff login and with an invalid webhook secret | Backend rejects the secret, normally 401 |

## 7. Publish

1. Open **Publish → Settings**.
2. Confirm the final build/start commands and 5000 → 80 mapping.
3. Confirm deployment secrets, including the installation environment values.
4. Configure a production PostgreSQL database. The session selected copying the
   existing fictional development data for initial setup. Do not assume later
   development edits automatically sync to production, or overwrite production
   data on updates without reviewing the platform's options.
5. The session selected Asia and Public access. The staff entrance still requires
   its own password; the webhook must be reachable without interactive login.
6. Leave the optional feedback widget off if it is not needed.
7. Review costs, then Publish. On updates, use Republish and inspect the new logs.

Published address used in this session:
[QuoteFlow demo](https://fast-as-fahhhh-20.replit.app/).

In the same authenticated browser, open `/api/health`. The user confirmed:

```json
{"status":"ok","mode":"local-synthetic-demo"}
```

`local-synthetic-demo` labels the demo mode; it does not mean the request was
served from the user's laptop. An anonymous external check returned 401 for the
homepage and API, as intended. It returned 404 for `/healthz`, despite the earlier
local 200 result. This public health-route discrepancy remains unresolved in the
available evidence and should be checked against the deployed revision.

## 8. Register the Telegram webhook

Project Telegram bot: [@yu_xin_bot](https://t.me/yu_xin_bot), as identified by the team.
This is the public bot username, not its private API token.

Run in the configured Replit Shell. This changes the bot's webhook destination;
use the intended team bot. It does not send a message or discard pending updates.

```bash
python - <<'PY'
import os
import httpx

try:
    response = httpx.post(
        "https://api.telegram.org/bot" + os.environ["TELEGRAM_BOT_TOKEN"] + "/setWebhook",
        json={
            "url": "https://fast-as-fahhhh-20.replit.app/api/webhooks/telegram",
            "secret_token": os.environ["TELEGRAM_WEBHOOK_SECRET"],
            "allowed_updates": ["message"],
        },
        timeout=30,
    )
    result = response.json()
    print({"http_status": response.status_code,
           "registered": result.get("ok", False)})
except Exception:
    print("Registration could not be confirmed; check configuration and connectivity.")
PY
```

The user reported HTTP 200 and `registered: True`. Keep the production secret
identical to the value used here. Registration alone does not prove successful
delivery to the application.

## 9. Exercise the real journey and record evidence

1. Send a fictional enquiry from the authorized Telegram test chat.
2. Refresh the published inbox and confirm original text/source.
3. Confirm an AI-labelled draft, stated quantities, unknown facts, and blank prices.
4. Review customer requirements; enter PM-reviewed prices and save.
5. Inspect the saved PDF: correct items, total, dates, Chinese text and version.
6. As PM, explicitly approve the reviewed version for the original chat.
7. Confirm the PDF actually arrives in Telegram, not only a Sent badge.
8. Check persisted receipt/draft/approval/delivery activity and send lockout.
   Use mocked tests for repeat-request checks unless another live check is
   explicitly approved; do not cause extra real sends just to test a button.

Session evidence: user screenshots show live inbound messages, AI-labelled
drafts, blank initial prices, activity, Sent entries, and an opened downloaded
quotation PDF. Actual receipt of that PDF in the Telegram chat and complete final
delivery activity were not independently shown. Do not label every live
acceptance item complete solely from these screenshots. See [the UX review](TELEGRAM_FRONTEND_UX_REVIEW.md)
for problems discovered during the walkthrough.

## Troubleshooting

| Symptom | Finding and action |
| --- | --- |
| Shell not visible | Open the + tool selector and search for Shell |
| Node 20 | Change only the Node runtime module to Node 22; reopen Shell |
| Invalid webhook secret | Use allowed characters; check environment precedence and restart |
| Port 5000 already used | An existing workflow may own it; inspect and restart only that project instance |
| `--user` install forbidden | Disable user mode in the early installation environment, not just custom build |
| `externally-managed-environment` | Do not install into managed system Python; use the writable target directory |
| Project wheel writes into `/nix/store` | Remove local-project installation from deployment requirements and configure the early phase's target directory |
| Custom `--target` does not help | Failure may occur before custom build; inspect the first actual deployment error |
| UI loads but says API unavailable | Inspect production Python child logs, imports, database settings and localhost proxy; workspace health alone is insufficient |
| Anonymous API returns 401 | Expected staff protection; test with an authenticated browser |
| Public `/healthz` returns 404 | Check current published revision and route configuration; unresolved in this record |
| pypdf security warnings | Separate from the observed installation failures; inspect each advisory and fixed version before changing dependencies |

Do not use “Fix all” to change many unrelated packages during deployment
diagnosis. Do not print complete environment variables, raw provider URLs with
tokens, database connection strings, or credential-bearing error objects.

## Submission proof and remaining notes

- The supplied event instructions allow a live Replit deployment URL, an
  accessible Replit project/history link, or a credits-exhausted screenshot.
  Verify evaluator access; do not spend credits just to create evidence.
- For RunPod Serverless, the supplied instructions require endpoint evidence and
  the team's own account in the screenshot. A shared public endpoint in source
  code alone does not establish team-account usage. Never include an API key.
- Reconcile Replit-only source/config changes back into Git after reviewing the
  diff. This guide does not perform that sync or claim deployment changes were
  committed locally.
- This is a supervised synthetic-data prototype. Hosted runtime behavior,
  PostgreSQL regression, security advisories, and usability issues remain separate
  verification tracks.

## References

- [Replit import](https://docs.replit.com/build/import-from-providers)
- [Replit Secrets](https://docs.replit.com/core-concepts/project-editor/app-setup/secrets)
- [Replit Database](https://docs.replit.com/features/data-and-storage/sql-database)
- [pip configuration](https://pip.pypa.io/en/stable/topics/configuration/)
- [Telegram setWebhook](https://core.telegram.org/bots/api#setwebhook)
- [Existing live checklist](LIVE_TEST.md)
