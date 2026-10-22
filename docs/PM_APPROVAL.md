# PM approval and Telegram PDF sending

## Read, price, preview, approve

1. Receive a team-created fictional enquiry via the Telegram webhook; drafting starts automatically after receipt.
2. Read its draft with `GET /api/enquiries/:id/quotation`. While drafting is still in progress this may return 404; retry or use the existing draft endpoint after a failed attempt.
3. PATCH the quotation with its current version, manual prices, and reviewed client/items. Resolve or dismiss missingInformation.
4. Display `GET /api/quotations/:id/pdf?version=N` to the PM. The saved PDF is cached for that version. Edits require a new preview.
5. POST `/api/quotations/:id/send` after the PM explicitly approves:

```json
{
  "version": 2,
  "previewedVersion": 2,
  "actor": "Fictional PM",
  "role": "pm",
  "approved": true
}
```

Actor and role are labelled demo identities, not production authentication. The server requires the PM role, approval=true, the latest version, a cached preview, complete prices/details, and an unexpired quotation. It derives the recipient from the original Telegram enquiry. Request/AI recipient overrides are rejected.

TELEGRAM_BOT_TOKEN must be configured privately before starting the app. Missing/invalid token configuration returns 503 before approval is consumed. The PDF is uploaded through Telegram sendDocument as multipart data; the exact saved bytes are used. No message is sent automatically by drafting.

## Outcomes and repeat clicks

- 200, status sent: Telegram accepted the document; providerReference is its message ID. readConfirmed is always false.
- 202, status sending: an existing attempt is still in progress. Repeated clicks return the same attempt instead of another upload.
- 502, status send_failed: Telegram explicitly rejected the upload. Fix the cause, then submit a new PM approval with `retry: true` for a known failure. No automatic network retry occurs.
- 202, status send_uncertain: timeout, ambiguous response, or provider 5xx. Check the original chat; the API blocks blind resend.
- Repeating an already accepted request returns its persisted result without another upload, including after application restart.
- If saving a result fails after an upload, the pending reservation remains locked and the API returns 503. Check the chat before any operational recovery; no exactly-once delivery guarantee is claimed.

The enquiry inbox reflects sent/failed/unknown outcomes. Send attempts persist in PostgreSQL alongside immutable quotation/PDF snapshots. Read the chronological activity log at GET /api/enquiries/:id/activity or GET /api/quotations/:id/activity. Receipt, draft, approval, and Telegram result events persist in PostgreSQL. Retried requests do not overwrite or duplicate existing events. Approval is recorded atomically before upload; result/attempt/inbox changes and the result event are committed together.

Reference: [Telegram Bot API sendDocument](https://core.telegram.org/bots/api#senddocument).
