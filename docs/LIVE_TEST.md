# Member 2: controlled live journey verification

This is the only remaining item in DELIVERY_CHECKLIST.md. Local mocked tests do not complete this verification.

## Private setup

Replace the blank entries in your ignored .env with your own DATABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, the selected AI provider configuration (AI_PROVIDER=runpod and RUNPOD_API_KEY), and LIVE_TEST_CHAT_ID. Keep secret fields in .env.example blank. Set ENABLE_DEMO_APPROVAL=true only for the supervised test. LIVE_TEST_CHAT_ID must identify a team-controlled chat that is permitted to receive one fictional test quotation; never use a customer conversation.

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_live_config
```

The report prints boolean checks and the public provider name, not secret values. Exit 1 means missing/invalid-looking configuration. Exit 0 only confirms presence/format; it is not evidence that credentials, database access, or chat ownership work. Restart the backend after changing configuration.

## Live run

1. Start the combined API on port 8004 with `python -m backend.server`. Confirm the private PostgreSQL connection succeeds and GET /api/health responds.
2. Member 2 configures Telegram's webhook to the reachable HTTPS URL for `/api/webhooks/telegram`, using the same private secret token as TELEGRAM_WEBHOOK_SECRET. Localhost alone is not reachable by Telegram. This document does not set up a tunnel, register the webhook, or deploy a public service.
3. From the authorized test chat, send a fictional enquiry with a unique test reference, e.g. “LIVE-DEMO: Example Events needs 20 printed T-shirts, address 12 Demo Road.” Do not send real personal/customer/business records.
4. GET /api/enquiries and identify that exact message and the expected original chat. This verifies real receipt, not a simulated POST fixture. Use GET /api/enquiries/:id/quotation to obtain the automatically created draft.
5. Verify draftMode is ai. If it is manual, the fallback works but live AI verification has not passed; check private provider/model configuration. Ensure unknown facts and prices were not invented.
6. As the simulated PM, fill reviewed client details, quantity 20, unitPrice 25.00, and resolve missingInformation through PATCH /api/quotations/:id with the current version. Check total 500.00 in the configured currency and the issue/expiry dates.
7. Retrieve and review GET /api/quotations/:id/pdf?version=N. Confirm the PDF matches the saved values.
8. Only after review, approve with the body shown in PM_APPROVAL.md. The backend routes the saved PDF to the original stored chat; it does not accept a recipient override. Submit only for the known team test enquiry.
9. Confirm the PDF actually appears in that test chat. Check GET /api/quotations/:id/activity for receipt, draft, PM approval, and Telegram acceptance with a provider reference. Acceptance is not a read receipt.
10. Repeat the same send request once and verify it returns 409 without another Telegram PDF; inspect the persisted original attempt/reference in enquiry detail. If any outcome is uncertain, check the chat and stop; do not force a blind resend.

## Record the result

Replace the remaining unchecked delivery item only after these steps pass. Record the date, environment, synthetic quotation reference, and pass/fail for actual inbound receipt, live AI, reviewed PDF, approved outbound delivery, activity, and duplicate protection. Keep credentials and private chat IDs out of committed evidence.

The current role simulation is for a supervised prototype; this test does not establish production access control, deployment readiness, or customer-data privacy compliance.
