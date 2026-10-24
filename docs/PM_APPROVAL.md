# PM approval and Telegram PDF sending

This is the canonical API after merging Sweeway's integration. The previous body
fields `version`, `previewedVersion`, `actor`, `role`, and `retry` are superseded
for the public send endpoint. Do not use the isolated compatibility SendService
contract in the frontend.

## Read, price, preview, approve

1. Receive a fictional Telegram enquiry. Drafting starts automatically after durable receipt.
2. Read `GET /api/enquiries/:id/quotation`; 404 means drafting has not completed. The explicit draft endpoint can retry.
3. Staff prepares details; only `X-Demo-Actor: pm` with enabled demo approval may change unit prices through PATCH. Both `unit_price` and legacy `unitPrice`, including clearing a price, are protected. Staff may retain an existing PM price while editing description/quantity. AI-created drafts always have blank prices.
4. Resolve missing requirements and unassigned messages. After new incoming messages, Staff explicitly saves the full current `reviewedMessageIds`. Manager opens `GET /api/quotations/:id/review?version=N` with `X-Demo-Actor: pm`. It returns saved customer/company/items/notes/dates, actual saved PDF URL/version/SHA-256 and a deterministic Telegram summary preview. Changes require a refreshed saved review/PDF. The normal `/pdf?version=N` route remains available.
5. With private `TELEGRAM_BOT_TOKEN` and `ENABLE_DEMO_APPROVAL=true` configured, POST `/api/quotations/:id/send`:

```http
X-Demo-Actor: pm
Content-Type: application/json
```

```json
{"expected_version": 2, "approved": true}
```

`X-Demo-Actor` is simulated identity for a supervised demo. Sales is blocked.
The server validates the current saved version, cached PDF, required client/items,
prices, missing information and dates. The recipient comes only from the stored
Telegram chat. The send request cannot override recipients or upload PDF URLs.

V2 B5 snapshots the approved summary text and reviewed incoming message IDs in
`send_attempts`, alongside the exact PDF bytes/hash. Summary fields come only
from saved data. **PDF-plus-summary transport is A5 work:** the current document
sender still delivers PDF only. A summary snapshot is not evidence of delivery.

New customer messages during an approved upload do not change its PDF or summary
snapshot. After successful delivery, they leave the enquiry in `needs_review`;
unknown delivery stays held. Data readiness in review does not guarantee provider
availability; sending still checks configuration and actual transport outcome.

The frontend still requires F4/F5: send its explicit simulated role on price
edits, acknowledge new incoming IDs, and render one final review page. Complete
those phases and A5 before deploying/recording the full V2 demo.

## Outcomes

- 200 `sent`: Telegram accepted the document; not proof of customer reading.
- 502 `failed`: explicit Telegram rejection.
- 202 `unknown`: ambiguous response or timeout; check the original chat.
- 409: duplicate/stale approval, pending/sent/unknown delivery, or stale version/preview. Repeated clicks never upload again.
- 503: approval disabled, missing token, storage/preparation failure, or result could not be persisted.

Responses after an attempt include `attempt_id` and `status`. Read the provider
message reference, attempt state and chronological activity from
`GET /api/enquiries/:id`; activity-only endpoints return the same history under `items`.

## Retry a confirmed failure

Only an explicitly recorded `failed` outcome can be retried. After fixing the
cause, GET enquiry detail and find the delivery attempt with `can_retry: true`.
The PM reviews the current quotation/PDF and explicitly approves again:

```json
{"expected_version": 2, "approved": true, "retry_of_attempt_id": "UUID of the failed attempt"}
```

Use the same `X-Demo-Actor: pm` header. `can_retry` describes delivery state;
normal PM/configuration, validity, version and saved-preview checks still apply.
If the quotation was edited, save and preview the new version before retrying.

Every retry gets a new `attempt_id` and records its `retry_of_attempt_id` link;
older attempts, their exact PDF bytes and activity remain intact. If the retry
also explicitly fails, refresh and approve its NEW failed attempt ID. Replaying
an earlier approval returns 409 even if a later retry failed. No boolean `retry`
flag, automatic resend or automatic message to the customer is used.

`pending`, `sent` and `unknown` outcomes cannot be retried. Check the original
chat for unknown results. Pending attempts remain locked if finalization fails;
never delete history to force a resend. Approval, attempt and outcome logs remain
transactional. The frontend should show Retry only to PM when `can_retry` is true,
and disable the button while its request is running.

See [delivery details](DELIVERY.md) for validation, response codes and boundaries.
