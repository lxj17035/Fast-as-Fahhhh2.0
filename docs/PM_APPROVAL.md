# PM approval and Telegram PDF sending

This is the canonical API after merging Sweeway's integration. The previous body
fields `version`, `previewedVersion`, `actor`, `role`, and `retry` are superseded
for the public send endpoint. Do not use the isolated compatibility SendService
contract in the frontend.

## Read, price, preview, approve

1. Receive a fictional Telegram enquiry. Drafting starts automatically after durable receipt.
2. Read `GET /api/enquiries/:id/quotation`; 404 means drafting has not completed. The explicit draft endpoint can retry.
3. PATCH the quotation with its current `version`, reviewed client details/items and manual prices. Resolve `missingInformation`.
4. Display `GET /api/quotations/:id/pdf?version=N`. Changes require a new preview.
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

## Outcomes

- 200 `sent`: Telegram accepted the document; not proof of customer reading.
- 502 `failed`: explicit Telegram rejection.
- 202 `unknown`: ambiguous response or timeout; check the original chat.
- 409: a previous attempt exists, or the version/preview is stale. Repeated clicks never upload again.
- 503: approval disabled, missing token, storage/preparation failure, or result could not be persisted.

Responses after an attempt include `attempt_id` and `status`. Read the provider
message reference, attempt state and chronological activity from
`GET /api/enquiries/:id`; activity-only endpoints return the same history under `items`.

The merged MVP allows one send attempt per quotation, including failed attempts.
A retry/recovery interface for known failures is deferred. Never delete attempts
or force a resend after an unknown outcome. Pending attempts remain visible and
locked if finalization fails. Approval, attempt and outcome logs are transactional.

See [delivery details](DELIVERY.md) for validation, response codes and boundaries.
