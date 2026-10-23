# Confirmed Telegram failure retry

- [x] PM must explicitly approve the current failed attempt ID; no automatic resend.
- [x] Each retry preserves previous attempts/PDF bytes and links its predecessor.
- [x] Duplicate/replayed approvals and concurrent clicks cannot upload twice.
- [x] Sent, pending and unknown outcomes block retry.
- [x] Edited quotations require current version and saved PDF preview.
- [x] Approval log failure rolls back retry; outcome log failure leaves pending state.
- [x] Enquiry detail exposes retry_of_attempt_id and can_retry for frontend controls.
- [x] PostgreSQL upgrades the existing unique-quotation schema without losing history; repeated startup is safe.
- [x] Final full regression suite and dedicated fix commit.

Targeted SQLite/PostgreSQL retry checks before the final outcome-persistence case:
19 passed, 1 skipped (SQLite cannot run the PostgreSQL legacy-schema migration).
All messaging is mocked; no customer or real Telegram messages were sent.

Frontend contract: PM_APPROVAL.md. Recovery of unknown outcomes remains outside
this fix. Do not expose a force-resend button or delete attempts to bypass guards.

Final combined SQLite/PostgreSQL suite: **394 passed, 2 skipped**, 278.30 seconds. Both skips are PostgreSQL-only checks under SQLite; their PostgreSQL cases passed. One existing Starlette/httpx deprecation warning.
