# Xinjie's implementation checklist

Work in small sections: implement -> run that section's tests -> update this checklist -> commit. Do not mark live integrations complete based on mocked tests.

## 1. Settings and client storage

- [ ] Python backend package and SQLite persistence with fictional seed data.
- [ ] Read/update company details, currency, default validity, and client name/address.
- [ ] Validate settings and preserve stored data after reopening the database.
- [ ] Run `python -m unittest tests.test_settings -v` and commit `feat: persist business settings and clients`.

## 2. Quotation rules and persistence

- [ ] Save drafts with copied company/client details, manual prices, and version checks.
- [ ] Calculate all validity durations and exact money totals on the backend.
- [ ] Validate sending (PM role, required fields, expiry, saved version).
- [ ] Preserve sent snapshots and expose a helper for Sweeway's send handler.
- [ ] Run `python -m unittest tests.test_quotations -v` and commit `feat: implement quotation rules and draft storage`.

## 3. AI extraction and manual fallback

- [ ] Configurable OpenAI Responses API structured extraction with no pricing/send authority.
- [ ] Validate AI output and preserve unknown fields; never overwrite PM edits.
- [ ] Persist a clearly labelled manual draft if credentials/provider output are unavailable.
- [ ] Test valid output, malformed output, refusal/timeout, missing credentials, and repeat draft requests.
- [ ] Run `python -m unittest tests.test_drafting -v` and commit `feat: add structured enquiry drafting and fallback`.
- [ ] Live provider verification with a real API key (requires user configuration).

## 4. PDF, HTTP API, and handoff

- [ ] Fixed PDF template for saved quotation data, including multipage tables.
- [ ] HTTP settings/client/draft/save/PDF endpoints with predictable errors.
- [ ] Integration instructions and fictional sample for Sweeway/YieXian.
- [ ] Run PDF/API tests, inspect generated PDFs, and run the full suite.
- [ ] Commit `feat: expose quotation API and PDF preview`.

## Ownership boundary

Sweeway still owns live Telegram receive/send, inbox integration, approval/send activity persistence, and optional email. YieXian owns frontend screens and PDF display. Xinjie's local demo API and test fixtures are integration aids, not live channel implementations.

## Verification log

Record commands, results, and limitations here as each section is completed. Commits remain local unless pushing is separately requested.
