# Runpod GLM-5.3 setup and spend controls

## What runs where

Replit hosts the application and its PostgreSQL connection. Runpod's shared
Public Endpoint provides AI inference. No GPU Pod, dedicated model deployment,
fine-tuning or always-on GPU is needed for this integration.

The public URL and model below come from the event announcement. One live
synthetic extraction on 23 October 2026 returned HTTP 200, one quotation item and
blank prices. This verifies the AI boundary, not the live Telegram or Replit journey.

## Private configuration

Set the following locally in ignored .env, or in Replit Secrets when deploying:

```dotenv
AI_PROVIDER=runpod
RUNPOD_API_KEY=
RUNPOD_API_BASE_URL=https://api.runpod.ai/v2/b1dd8hy2hqo1nb/openai/v1
RUNPOD_MODEL=glm-5.3
RUNPOD_MAX_TOKENS=1024
RUNPOD_DAILY_REQUEST_LIMIT=100
```

Put your own key after RUNPOD_API_KEY= only in private configuration. Never commit
it or put it in browser/frontend code. The shared .env.example key remains blank.
Restricted credentials may leave GraphQL management access disabled and grant
AI API access needed to invoke the public model. A live call verifies whether
the selected key actually has permission. No account management key is needed.

DATABASE_URL remains PostgreSQL. AI usage counters live in quotation_records in
the same team database; there is no extra runtime database or service. Restart
the backend after changing configuration.

AI_PROVIDER=openai selects the existing OpenAI adapter and requires that
provider's own key/model. AI_PROVIDER=manual disables external drafting. Failure
never switches silently to another paid account/provider.

## Spend controls and behavior

- reasoning_effort is fixed at low.
- max_tokens defaults to 1024 and accepts 256-2048; invalid settings fall back to manual review.
- Total serialized prompt input is limited to 16,000 UTF-8 bytes; oversized enquiries/context fall back without an AI request.
- At most 100 attempted AI calls per Kuala Lumpur calendar day by default (configurable 1-1000).
- The counter is shared and reserved transactionally across application instances before each request. Failed/ambiguous requests count too.
- No automatic network retry or model-repair request is made. Duplicate enquiries with existing drafts do not call AI again.
- Exhausted budget, missing keys, HTTP errors, truncation or invalid JSON preserve a labelled manual draft.
- JSON instructions include the required schema; all returned fields are validated on the server. This does not claim provider-enforced JSON Schema support.
- AI may extract stated facts and missing information. It cannot set prices, select recipients, approve or send a quotation.

The daily limit controls this application's calls in its shared database. It does
not limit other applications, Playground usage or the Runpod account as a whole.
It is not a dollar-denominated spending guarantee. Restrict the supervised demo;
review actual usage in Runpod. Repeated manual fallback requests return the saved
manual draft rather than automatically paying for another extraction.

## Will US$25 last until 1 November?

Using the event announcement's rates (not independently confirmed account pricing):
input US$0.77/M tokens, output US$2.42/M, cached input US$0.143/M.
We assume no cache savings for these estimates.

| Workload assumption | Estimated cost |
| --- | --- |
| 2,000 input + 1,000 output tokens | US$0.00396 per call |
| 100 such calls/day | US$0.396/day |
| 1,000 such calls (10 days including 23 Oct-1 Nov) | US$3.96 |
| 5,000 input + 1,024 output tokens, 1,000 calls | US$6.33 |

US$25 is likely sufficient for a small demo under those assumptions. Actual token
usage (including billable reasoning), pricing, other account activity and credit
expiry may differ. The balance screenshot does not establish an expiry date;
check event-credit terms/account billing. No exact balance deduction was retrieved.

## Verification and remaining work

`python -m scripts.check_live_config` prints selected-provider readiness without
printing keys or making requests. readyForAI is configuration presence/format,
not a live test. readyForLiveTest additionally requires Telegram/test-chat setup.

Mocked tests cover request format, limits, validation, safe errors, no hidden
retries, shared budget concurrency, factory selection and automatic webhook drafts.
One separately authorized live synthetic call passed; Telegram messages were not sent.
The live probe used an ignored, explicit test database for its counter, not the
application runtime. Tests do not reuse real credentials.

Frontend and Replit hosting, Member 2's live Telegram receipt/approval/PDF journey,
and optional email remain separate work. Replit must receive its own private
secrets; local .env does not upload automatically.

Sources: [Runpod Public Endpoints](https://docs.runpod.io/public-endpoints/overview),
[API requests](https://docs.runpod.io/public-endpoints/requests),
[credentials](https://docs.runpod.io/get-started/credentials), plus the supplied event announcement.

Final combined SQLite/PostgreSQL regression: **423 passed, 2 skipped**, 362.59 seconds, one existing Starlette/httpx deprecation warning. Skips are PostgreSQL-only checks under SQLite; their PostgreSQL cases passed. This automated suite used mocked AI; the one live synthetic probe is recorded separately above.
