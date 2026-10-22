# Xinjie's implementation checklist

Work in small sections: implement -> run that section's tests -> update this checklist -> commit. Do not mark live integrations complete based on mocked tests.

## 1. Settings and client storage

- [x] Python backend package and SQLite persistence with fictional seed data.
- [x] Read/update company details, currency, default validity, and client name/address.
- [x] Validate settings and preserve stored data after reopening the database.
- [x] Run `python -m unittest tests.test_settings -v` and commit `feat: persist business settings and clients`.

## 2. Quotation rules and persistence

- [x] Save drafts with copied company/client details, manual prices, and version checks.
- [x] Calculate all validity durations and exact money totals on the backend.
- [x] Validate sending (PM role, required fields, expiry, saved version).
- [x] Preserve sent snapshots and expose a helper for Sweeway's send handler.
- [x] Run `python -m unittest tests.test_quotations -v` and commit `feat: implement quotation rules and draft storage`.

## 3. AI extraction and manual fallback

- [x] Configurable OpenAI Responses API structured extraction with no pricing/send authority.
- [x] Validate AI output and preserve unknown fields; never overwrite PM edits.
- [x] Persist a clearly labelled manual draft if credentials/provider output are unavailable.
- [x] Test valid output, malformed output, refusal/timeout, missing credentials, and repeat draft requests.
- [x] Run `python -m unittest tests.test_drafting -v` and commit `feat: add structured enquiry drafting and fallback`.
- [ ] Live provider verification with a real API key (requires user configuration).


## 4. PDF, HTTP API, and handoff

- [x] Fixed PDF template for saved quotation data, including multipage tables.
- [x] HTTP settings/client/draft/save/PDF endpoints with predictable errors.
- [x] Integration instructions and fictional sample for Sweeway/YieXian.
- [x] Run PDF/API tests, inspect generated PDFs, and run the full suite.
- [x] Commit `feat: expose quotation API and PDF preview`.

## Ownership boundary

Sweeway still owns live Telegram receive/send, inbox integration, approval/send activity persistence, and optional email. YieXian owns frontend screens and PDF display. Xinjie's local demo API and test fixtures are integration aids, not live channel implementations.

## Verification log

Record commands, results, and limitations here as each section is completed. Commits remain local unless pushing is separately requested.

### Section 1

- `python -m unittest tests.test_settings -v`: 6 tests passed.
- Verified fictional seeds, all validity settings, invalid-update rollback, client editing, and persistence after reopen.
- Added AGENTS.md/SKILLS.md, ignored .input and .env, and placeholder .env.example.
- Runtime for local verification: bundled Python 3.12; no real credentials used.

### Section 2

- `python -m unittest tests.test_quotations -v`: 12 tests passed.
- Verified calendar/month-end/leap-year dates, decimal rounding, blank vs zero prices, stale versions, snapshots, concurrent approvals, PM role, expiry, and uncertain-send lockout.
- `begin_send` / `record_send_result` are service helpers for Sweeway; no external message was sent.

### Section 3

- `python -m unittest tests.test_drafting tests.test_settings tests.test_quotations -v`: 29 tests passed (11 drafting, 6 settings, 12 quotation).
- Mocked Responses API requests verify strict schema, no prices/tools, timeout/refusal/invalid response fallback, retry idempotency, and atomic draft/activity rollback.
- `.env` loader preserves process environment and never executes shell content.
- Live AI remains unverified: configure OPENAI_API_KEY and OPENAI_MODEL in local .env. No real key was used or printed.

### Section 4

- `python -m unittest tests.test_pdf tests.test_api -v`: PDF and HTTP integration checks passed; final suite includes 7 PDF and 9 API tests.
- `python -m unittest discover -s tests`: **46 tests passed** (6 settings, 12 quotations, 12 drafting, 7 PDF, 9 API).
- API tests exercise a real localhost HTTP server: fictional enquiry -> manual draft -> saved prices -> PDF, plus stale versions, invalid JSON, CORS, and explicit 501 for unfinished Telegram sending.
- Fixed orphan totals/short notes, repeated headers within a page, and mixed Latin/Chinese font rendering during visual review. Added regression checks for table headings and long CJK row splitting.
- Rendered single-page and nine-page fictional samples with Poppler; visually inspected the sample plus first/second/final multipage layouts. Review images are ignored under .input/pdf-review; useful samples remain in ignored output/pdf.
- Added a regression test ensuring a message received during AI extraction is preserved.
- Confirmed Markdown links, code fences, clean diff formatting, ignored .env/.input, and trackable .env.example.
- No live AI, Telegram, email, or frontend integration was claimed or tested. See XINJIE_HANDOFF.md for exact ownership boundaries.

## Commit review guide

| Section | Commit / subject |
| --- | --- |
| Checklist baseline | `11290ab` - docs: add Xinjie section-by-section checklist |
| 1. Settings/clients and repo conventions | `f572a43` - feat: persist business settings and clients |
| 2. Quotation rules | `a0ca19b` - feat: implement quotation rules and draft storage |
| 3. AI/manual drafting | `2b4cfe3` - feat: add structured enquiry drafting and fallback |
| 4. PDF/API/handoff | `feat: expose quotation API and PDF preview` (see git log for hash) |

Review one section with `git show <commit>`. All implementation commits are on `feat/xinjie`; none were pushed. The checklist-baseline commit predates branch creation and is an ancestor of the feature branch.

### Port configuration follow-up

- Changed the default/local port to 8004 in server configuration, .env.example, local ignored .env, CORS origins, and setup docs.
- Verified 127.0.0.1:8004 was available at the time of the check; no other project process was stopped.
- `python -m unittest tests.test_api tests.test_drafting`: 21 tests passed, including CORS for localhost/127.0.0.1:8004 and environment-file loading.

### README submission overview

- Reworked README around the supplied screenshot: project description, team information, links, overview, workflow, current status, setup, and demo instructions.
- Used the configured GitHub remote; Replit, hosted demo, RunPod, slides, and YouTube remain explicitly pending. Final project/team name, leader, university, and member count await user confirmation.
- Kept intended workflow separate from implemented features; no live integration or measured impact was invented.
- Verified local Markdown links, fenced blocks, required overview sections, and PowerShell syntax for all three command blocks. Application tests were not rerun because no application code changed.
