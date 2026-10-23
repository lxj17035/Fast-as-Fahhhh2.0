> This records Sweeway branch history. The current merged behavior and test result are in [MERGE_REVIEW.md](MERGE_REVIEW.md); use [PM_APPROVAL.md](PM_APPROVAL.md) for the public send contract.

# Sweeway final backend QA and handover

Scope: Sweeway's Telegram receipt, enquiry tracking, PM-controlled PDF delivery,
and activity history. Xinjie's reused service logic remains unchanged. Frontend
implementation and live AI activation belong to their owners and are outside this
handover's completion claim.

## Final results — 23 October 2026

- **272 passed**, one warning, in **32.54 seconds** using Python 3.14.7,
  PostgreSQL 18.6 and SQLite. The database suite used isolated PostgreSQL schemas.
- The final Sweeway workflow used Xinjie's real structured-output parser and saved
  PDF services plus Sweeway's real multipart Telegram sender. Both external
  transports were mocked. It verified blank draft prices, original chat and
  previewed bytes, Sales rejection, explicit PM approval, persisted provider
  reference, seven linked activity events, and duplicate prevention.
- Mocked extraction timeout/refusal and out-of-contract price/recipient output
  retained the original enquiry and an editable manual draft with no outgoing send.
- Earlier regression coverage for authentication, concurrency, transaction rollback,
  uncertain outcomes, restart protection and activity isolation also passed.
- Independent QA review found no blocking scope/test defects. Compilation, Git
  whitespace and targeted credential-pattern checks passed. This QA step changed
  no application or teammate service implementation.
- One existing Starlette/HTTPX test-client deprecation warning remains. The test
  PostgreSQL server was stopped after execution.
- Live Telegram/AI, frontend integration, production authentication and reconciliation
  with the team's advanced `main` remain unverified or outstanding as described below.

## Implemented features and endpoints

| Sweeway route | Behavior |
| --- | --- |
| `POST /api/webhooks/telegram` | Secret-checked text receipt, original IDs/text, durable duplicate prevention |
| `GET /api/enquiries` | Bounded paginated Telegram inbox |
| `GET /api/enquiries/{id}` | Original messages, safe delivery attempts and canonical activity history |
| `POST /api/quotations/{id}/send` | Explicit simulated PM approval, saved preview/version validation, original recipient, one attempt |

The existing FastAPI/PostgreSQL runtime adapts Xinjie's real settings, quotation,
drafting and saved-PDF services. No second app or database is started. See
[delivery](DELIVERY.md), [enquiries](ENQUIRIES.md), [activity](ACTIVITY.md), and
[reused-source provenance](XINJIE_SOURCE.md) for the precise contracts.

## Verification boundaries

- Automated incoming updates and provider responses are synthetic.
- The final workflow tests inject a mocked extraction transport into Xinjie's
  existing parser and a mocked HTTP transport into Sweeway's real Telegram sender.
  They verify the integration contract, not a live model or Telegram delivery.
- Existing integration tests also cover the manual drafting path and real PDF
  rendering/cache. Tests use the actual shared database adapter.
- PostgreSQL tests use isolated schemas in an explicit disposable database;
  SQLite is the portable test adapter. Production migrations, load and
  multi-process resilience are not claimed.
- Live Telegram registration/delivery requires separate approval and a
  team-controlled bot/chat. No real customer or payment data is used.

## Reproduce automated checks

From the repository root, install `.[test]` into a Python 3.12+ environment.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
```

To include PostgreSQL, set `TEST_DATABASE_URL` to a disposable database using the
`postgresql+psycopg://` driver before running the same command. The test user needs
schema creation permission. Tests drop only their uniquely named schemas. Keep
credentials in the environment, out of source files and shared terminal output.

For the complete Sweeway workflow alone:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_sweeway_workflow.py --basetemp=.pytest_tmp_workflow
```

`tests/__init__.py` and package-qualified helper imports make the suite compatible
with the test-package layout already present on the team's updated `main`.

## Security and correctness review

Focused independent reviews covered webhook authentication, safe errors,
transactional deduplication, original recipient lookup, PM checks, PDF-version
consistency, concurrent sends/edits, and activity accuracy. They found no remaining
blocking defects in the reviewed scope. This is not a claim of a complete formal
security audit or production readiness.

Important retained limitations:

- `X-Demo-Actor` is a supervised-demo selector, not trusted authentication.
  Demo approval is disabled by default. Inbox/read routes need production access
  controls before deployment.
- Pending/unknown attempts block resending. Even known failures currently have
  no retry endpoint; reconciliation policy is future work.
- Activity is insert-only in application code, not database-enforced tamper-proof
  storage. Historical events are not reconstructed.
- Provider acceptance does not prove customer reading.
- Fictional `demo-client` association is explicit seeded context, not customer
  identity matching or advertisement attribution.
- A Starlette/HTTPX test-client deprecation warning remains; current tests pass.

## Synthetic local demo

Follow [Telegram setup](TELEGRAM.md) to start the one app bound to localhost using
a team-controlled PostgreSQL database. For a receive-only demo, a real bot token
is unnecessary. Configure a random webhook secret in the server environment.

1. Submit a synthetic text update to the local webhook with its matching secret
   header. Use a fictional message and chat ID; repeat it to demonstrate deduplication.
2. Read the inbox and detail APIs; confirm exact text, source and original IDs.
3. Create a manual draft with `{"manual":true}`. Price 20 fictional shirts at
   `25.00` using Xinjie's quotation PATCH route; observe saved total `500.00`.
4. Preview the saved PDF with its returned version. Edit it and demonstrate that
   the old version cannot be approved.
5. Run the targeted workflow test above to demonstrate PM authorization, exact
   PDF/chat delivery and outcome/activity recording with provider calls mocked.
   This automated step sends no document to Telegram.
6. Read activity history and explain actual system versus simulated/unknown actors.

Do not invoke a live send during this demo without the separately required approval.
For actual live verification, confirm the team bot/chat, approved test quotation,
current preview and expected destination first. Configure Telegram as documented
in the setup guide; check the test chat after an unknown result instead of retrying.

## Commits and review handoff

| Part | Verified commit | Subject |
| --- | --- | --- |
| 1 | `a2620e0` | `feat(telegram): implement secure webhook integration` |
| 2 | `cedc46d` | `feat(enquiry): implement enquiry persistence and tracking` |
| 3 | `7a7e844` | `feat(delivery): implement PM-approved PDF sending` |
| 4 | `8324a4a` | `feat(activity): implement persistent activity logging` |

The final QA commit uses `test(integration): verify enquiry-to-quotation workflow`.
Use `git log --oneline` for its actual hash; this report does not invent a
self-referential commit ID.

The prepared [PR description](SWEEWAY_PR.md) targets `main` from
`feature/sweeway-telegram-integration`. No automatic merge is authorized.

## Remaining integration work

- The team's `main` advanced to `8aa59b9` during development and already includes
  Xinjie's work plus Sweeway Parts 1–2. Read-only compatibility inspection found
  conflicts in `.env.example`, `.gitignore`, and `docs/IMPLEMENTATION.md`; README
  also changed on both sides. These need an explicitly approved reconciliation.
- The six reused business modules match the reviewed upstream source; upstream
  legacy server/store files absent here are not intended deletions. Preserve team
  files during reconciliation, while keeping one active application/database.
- GitHub connector access returned 404 for this repository; Git remote reads
  worked. A prepared PR body does not mean a hosted pull request was created.
- Frontend linkage, live provider tests, judge access, timing measurements and
  rehearsals remain team/final-demo tasks. They are not marked complete here.
