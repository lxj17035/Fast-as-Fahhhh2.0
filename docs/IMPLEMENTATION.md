# Lean implementation and demo checklist

This document records the shared target contract. Xinjie's backend is now implemented; see [the handoff](XINJIE_HANDOFF.md) for actual routes, setup, and integration boundaries, and [his checklist](XINJIE_CHECKLIST.md) for test evidence. The shared full-journey acceptance items below remain unverified until frontend and live channel integration.

## Keep the architecture small

One application and database:

`Telegram input -> saved enquiry + business context -> AI draft -> PM review -> PDF -> Telegram output + activity log`

Use the simplest processing that works in the chosen runtime. No separate queue service, job dashboard, production identity service, or Orbyte SDK is required for this prototype. Persist enquiries, quotations, and activity records.

## Minimum data

| Record | Fields to agree |
| --- | --- |
| Business context | Fictional business id/name/address, currency, default validity; seeded fictional client id/name/address |
| Enquiry | Id, source, Telegram chat id, provider message/update id, original text/messages, client id, summary, missing information, status |
| Quotation | Id/number, enquiry id, copied client/company details, issue date, validity, expiry, items with quantity and nullable unit price, calculated total, status, saved PDF/version |
| Activity | Enquiry/quotation id, timestamp, simulated actor/role, action, outcome, provider reference or safe error summary |

Log receipt, draft creation, PM approval, and send outcome. Do not overwrite a sent quotation when client/settings change. Keep bot/AI keys in server environment variables and out of GitHub.

## Assumed hub interface

For the demo, a local seed/provider returns business context and a labelled simulated actor with role `sales` or `pm`. Document these as team-defined assumptions, not actual Orbyte API routes.

Future hub integration would replace the seed/provider with business context and trusted identity from the platform. For now, show a role check in the server send handler so the permissions concept is demonstrated. A role selector/request value is not secure authentication and is only for the supervised prototype.

## Small app API contract

Routes are suggestions; an equivalent server-action implementation is fine. Agree request/response fields before dividing work.

| Route | Purpose | Owner |
| --- | --- | --- |
| `POST /api/webhooks/telegram` | Receive/deduplicate a test message and preserve source/chat identity | Sweeway |
| `GET /api/enquiries` and `GET /api/enquiries/:id` | Inbox, messages, connected context, quotation, activity | Sweeway |
| `GET/PATCH /api/settings` and `PATCH /api/clients/:id` | Editable business defaults and client details | Xinjie |
| `POST /api/enquiries/:id/draft` | Extract requirements and create quotation draft | Xinjie |
| `PATCH /api/quotations/:id` | Save edits and calculate totals/expiry | Xinjie |
| `GET /api/quotations/:id/pdf` | Return PDF for saved quotation, `application/pdf` | Xinjie |
| `POST /api/quotations/:id/send` | Check PM role, validate saved version, record approval, send, log result | Sweeway with Xinjie's validation |

YieXian connects the UI to these operations. Include activity in enquiry detail; no separate audit service is needed. Email has no required endpoint in this scope.

## Essential safeguards

- AI returns structured summary/client details/items/missing fields. Extract known facts only; leave prices for PM input. Customer text cannot override the workflow or choose a recipient.
- Save the draft before preview and send that same saved version. If edited, refresh the preview before approval. Do not build a separate preview-confirmation service.
- Backend blocks Sales sending, missing required fields, blank prices, invalid quantities, expired quotations, and stale saved versions.
- Calculate totals and dates server-side. Validity codes: `7d`, `14d`, `1m`, `2m`, `3m`; default `1m`.
- Deduplicate provider update IDs. Disable Send while pending and guard the saved quotation from a concurrent duplicate send.
- Send only to the stored source chat. Preserve the sent PDF/details and activity record.
- Show failure visibly. If a timeout leaves delivery unknown, do not retry automatically; verify the test chat first. Provider acceptance is not proof of reading.
- If AI fails, retain the enquiry and offer manual editing. New messages must not silently overwrite PM edits.
- For a webhook, validate its configured secret. Keep the simulated-role prototype local or otherwise restricted to team-controlled demonstration.

## Acceptance checklist

All items are initially unchecked. Record actual results during implementation.

- [ ] A fictional Telegram enquiry appears in the inbox with original text and source chat.
- [ ] The draft uses both the message and seeded business/client context.
- [ ] AI extracts requirements, exposes missing information, and leaves prices blank.
- [ ] PM can edit client name/address, quantities/prices, and issue date.
- [ ] All five validity options work; 31 January 2027 + 1 month gives 28 February 2027.
- [ ] Quantity 20 at 25.00 totals 500.00; PDF and editor agree.
- [ ] Sales cannot approve/send; PM approval is required and logged with actor/time.
- [ ] Saving changes refreshes the preview before the approved version is sent.
- [ ] The PDF reaches the original test chat, with a visible result and activity record.
- [ ] Duplicate input/clicks do not produce parallel duplicate work/sends; failures remain visible.
- [ ] Client/settings edits do not change a previously sent PDF.
- [ ] Synthetic data and all simulated identity/API assumptions are clearly labelled.
- [ ] Manual vs assisted timing/error observations are recorded, or unmeasured benefits remain clearly labelled targets.
- [ ] Pitch covers SME pain, ease of learning, Orbyte hub fit/reuse, human control, SDG 8, and future privacy considerations.
- [ ] GitHub repository is accessible to judges, matches the demo, excludes secrets, and includes setup steps.
- [ ] Two rehearsals pass; unfinished or simulated integrations are disclosed.

Full identity/RBAC infrastructure and live Orbyte integration are deliberately omitted under the brief's prototype allowances. Production security, tenant isolation, and operational recovery remain future work.

Source: supplied Domain 2 PDF, physical pages 4-9. Data shapes and routes above are our assumptions.
