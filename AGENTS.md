# Project instructions

## Product and scope

Read README.md and docs/WORKFLOW.md before changing behavior. Deliver the synthetic-data Telegram enquiry -> AI draft -> PM review/pricing -> PDF -> approved send journey. Orbyte interfaces and staff roles are simulated. Do not add production identity, additional channels, or queue infrastructure to this MVP.

## Ownership

- Xinjie: settings, clients, quotation rules/storage, AI extraction/manual fallback, PDF API.
- Sweeway: live Telegram receive/send, inbox integration, send activity, optional email.
- YieXian: frontend editor, preview, role controls, activity display.
- Shared contracts belong in docs; update them when implemented behavior changes.

## Work and verification

- Xinjie's branch is `feat/xinjie`; work in the existing repository, not its parent workspace.
- Implement one checklist section, run its tests, record the result, then commit it. Do not combine untested later sections into earlier commits.
- Use `python -m unittest discover -s tests -v` for the full backend suite. Tests must use temporary databases and mocked external providers; never send real customer messages.
- Keep backend business logic independent of HTTP and frontend code. Use SQLite transactions and server-side validation for mutations.
- Preserve unknown AI fields and blank prices. Only PM may approve; AI must not set prices, recipients, or send authority.
- Report live provider checks separately from local mocked tests. Never mark an unavailable integration complete.
- Review rendered PDFs after template/layout changes and test that the PDF uses the saved quotation version.

## Files and secrets

- Store real keys only in local `.env`; commit placeholder variable names in `.env.example`.
- Never print, commit, or copy secrets into fixtures, logs, or docs. Environment values take precedence over `.env`.
- Put source references and disposable intermediate files in ignored `.input/`. Keep useful specs/checklists/handoff docs in `docs/` and source/tests in their normal directories.
- Ignore local databases and generated output. Do not move or delete unrelated user files.
- Simulated access control is for a supervised local demo; bind the backend to localhost.

Postman CLI is installed and may be used for API engineering, but unit/integration tests remain the repeatable verification source.
