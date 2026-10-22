# Project workflow guide

This is a repository guide, not an installed Codex skill package.

## Required working loop

1. Read AGENTS.md, the relevant product doc, and docs/XINJIE_CHECKLIST.md.
2. Implement the smallest complete section within the assigned ownership.
3. Run that section's tests. Fix failures before continuing.
4. Update checklist evidence, review `git diff --check` and staged changes, and commit with a concrete feature message.
5. At handoff, run the full suite and identify remaining live dependencies.

## Backend

Use Python 3.12+, FastAPI, SQLAlchemy/Psycopg, and one shared PostgreSQL DATABASE_URL. SQLite is limited to explicitly injected test/offline-fixture adapters. Use pytest for the combined suite and decimal arithmetic for money. ReportLab renders the fixed PDF layout; pypdf checks PDF content in tests. Avoid introducing a separate service just to support this demo.

## AI

Consult official OpenAI documentation when changing the Responses API adapter. Use structured output, validate it locally, bound request size/time, and test refusal/invalid response/provider failures. Manual fallback must be explicitly labelled. Keep API keys in `.env`.

## PDF

Use the PDF skill when changing layout. Generate a fictional sample and a multipage example, render them, and inspect for clipping, overlapping text, and repeated table headings. Store intermediate source/reference files under `.input/` and generated deliverables under ignored `output/`.

## Handoff

Document route payloads, version handling, error responses, environment variable names, and setup commands in docs/XINJIE_HANDOFF.md. Frontend and Telegram collaborators should not need to read implementation details to use the API.
