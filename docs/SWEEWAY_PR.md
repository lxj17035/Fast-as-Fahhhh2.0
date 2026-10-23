> This records Sweeway branch history. The current merged behavior and test result are in [MERGE_REVIEW.md](MERGE_REVIEW.md); use [PM_APPROVAL.md](PM_APPROVAL.md) for the public send contract.

# Sweeway: secure Telegram enquiry-to-PDF delivery and activity history

The current main branch already contains Telegram receipt and enquiry tracking.
This change connects those records to PM-approved delivery of the exact saved PDF
version, sent only to the original chat. Durable send attempts prevent duplicate
or uncertain retries, and transactional activity records expose the real receipt,
draft, edit, approval and delivery events.

Xinjie's service modules are reused unchanged through a shared PostgreSQL storage
adapter in the existing FastAPI application. This scope does not implement the
frontend or activate live AI.

## Validation

**272 tests passed** across PostgreSQL and SQLite (one existing test-client
deprecation warning). See `docs/SWEEWAY_QA.md` for final results and repeatable commands.
Tests exercise PostgreSQL and SQLite, real saved PDF rendering/cache, mocked
extraction and Telegram HTTP transport, concurrent inputs/sends/edits, transactional
rollback and pending-state recovery. Live Telegram delivery remains unverified.

## Review notes

- Base: `main`; head: `feature/sweeway-telegram-integration`.
- Demo actor selection is not production authentication; sending is disabled by
  default. Keep the supervised prototype local/restricted.
- Unknown outcomes block resend. Activity storage is application-level append-only.
- Upstream main advanced during this work. Reconcile `.env.example`, `.gitignore`
  and `docs/IMPLEMENTATION.md`, review README changes, and retain upstream-only
  files. No automatic merge or deletion of teammate work is intended.
- Backend test helpers now use package-qualified imports to match main's test layout.
- Frontend integration, approved live Telegram validation and final rehearsal remain
  outside this Sweeway backend QA completion claim.
