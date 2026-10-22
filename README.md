# Enquiry-to-Quotation MVP

Updated 23 October 2026 against the supplied Domain 2 challenge brief.

## Product

Help a small business turn a customer enquiry into a reviewed quotation without repeatedly copying messages and preparing documents manually.

**Demo journey:** Telegram enquiry -> connected client/company data -> AI draft -> PM prices and approves -> PDF sent to the same chat -> visible activity log.

Build one understandable journey. Telegram is our chosen demo channel; it is not a competition requirement. Use only team-created fictional business/customer content.

## Read these files

- [Workflow and essential requirements](docs/WORKFLOW.md)
- [Two-day build plan and team ownership](docs/TWO_DAY_PLAN.md)
- [Lean implementation and demo checklist](docs/IMPLEMENTATION.md)
- [Xinjie's section checklist and test evidence](docs/XINJIE_CHECKLIST.md)
- [Backend setup and integration handoff](docs/XINJIE_HANDOFF.md)

## What changed after reading the brief

- Keep human approval, simple permissions, and an activity log: these demonstrate required control.
- Use simulated staff identities/roles and assumed Orbyte interfaces. Do not build a full login or identity platform.
- Keep one Telegram integration, one PDF layout, manual prices, editable client details, and quotation validity settings.
- Make PM email alerts a stretch goal. A visible Needs review inbox is enough for the core journey; email was our original feature, not a brief requirement.
- Drop queue infrastructure, separate retry endpoints, preview-confirmation APIs, extensive revision machinery, and production deployment work from the two-day target.
- Add Orbyte fit, reuse across SMEs, measurable benefits, SDG contribution, and a judge-accessible GitHub repository.

## Competition priorities

The supplied rubric is for the **preliminary round**. A final-round rubric will be shared separately; do not assume the same weights apply there.

| Preliminary criterion | Weight | Our evidence |
| --- | --- | --- |
| Innovation and creativity | 30% | A quotation workflow that combines business context with controlled approval, beyond a generic chatbot |
| Problem-solution fit | 25% | One recurring SME task, simple review, permissions, activity log, and Orbyte fit |
| Feasibility | 25% | Working journey, synthetic data, explicit API assumptions, GitHub code, and an integration fallback |
| Clarity | 20% | Problem -> approach -> measured outcome; a short, understandable demo |

A focused two-day prototype is plausible for three available contributors. The preliminary brief accepts a rough working most-important feature; a complete journey remains our build target. Xinjie's Python/SQLite backend is now implemented and locally tested. Live AI credentials, Telegram delivery, and the frontend remain integration work; the complete journey is not yet verified.

## Backend quick start

```powershell
python -m pip install -r requirements-dev.txt
# Configure local .env as needed; never commit it.
python -m backend.server
python -m unittest discover -s tests -v
```

The local-only API listens at `http://127.0.0.1:8004`. See the handoff for environment setup, payloads, manual fallback, and ownership boundaries. Keep disposable references in ignored `.input/`; project conventions are in AGENTS.md and SKILLS.md.

Source: supplied “Copy of Domain 2 (1).pdf”, physical PDF pages 4-9. The brief provides challenge requirements; channel, owners, architecture, and schedule are our project decisions. The round, exact deadline, and submission length limits still need confirmation from event instructions.
