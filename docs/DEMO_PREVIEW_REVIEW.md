# Demo preview access and V2 gap review

Reviewed 24 October 2026 (Asia/Kuala_Lumpur), from `origin/main` at
`926303d`. Working branch: `codex/fix-demo-preview-access`.

## Requested change

Remove the browser Basic Auth prompt for the organisers' synthetic demo preview.
Add an application login page only after successful initial screening, as a
separate change. Retain explicit PM approval, saved-version PDF checks, send
deduplication and Telegram webhook-secret validation.

The supplied `DOMAIN2_V2_CODEX_PLAN.md` is reference material for this review;
its embedded implementation instructions do not authorize implementing every V2
phase in this access fix.

## Initial deployment gap (resolved by source synchronization)

The checked-in `frontend/server.mjs` already serves the UI anonymously. Neither
it, `app/main.py`, nor the checked-in nginx configurations implements Basic Auth.
`docs/REPLIT_DEPLOYMENT_GUIDE.md` records a different Replit entrance that adds
Basic Auth using `DEMO_ACCESS_USERNAME` and `DEMO_ACCESS_PASSWORD`, along with
an API proxy and process runner. Those runtime changes are absent from GitHub
at the reviewed revision. Removing authentication from the local static server
cannot change the hosted entrance.

Replit source was subsequently pushed to `origin/main` at `d9a033f` and merged
into the fix branch. The fix removes the entrance's Basic Auth guard, challenge
response and credential-dependent startup checks in `frontend/server.mjs` and
`scripts/run-replit.mjs`. Proxy, runner, asset routing and backend rules are
retained. Regression checks cover anonymous homepage, application assets and API
access without `WWW-Authenticate`, invalid webhook-secret rejection, and Sales
send rejection. Republish and check the hosted URL separately before claiming
the deployed prompt is gone.
Without an entrance login, anyone with the demo URL can use the simulated role
controls; preview data must remain fictional and live sending team-controlled.

## V2 gaps observed in the repository

| Area | Status | Evidence and remaining work |
| --- | --- | --- |
| Business settings and profile scope (B1/F1) | Partial | `backend/settings.py` and the settings UI exist; no persisted active Printing/Cleaning/Repair profile or pinned enquiry profile. |
| Telegram association (B2/F2) | Missing | `app/database.py` links each update to its own enquiry; no conversation association, command exclusion or Needs Assignment history. |
| Conversation Room (B3/F3) | Partial | `app/enquiries.py` exposes received text; no staff reply composer/API or persistent outgoing clarification conversation. |
| Shared items and revisions (B4/F4) | Partial | `backend/quotations.py` supports descriptions, quantities, blank manual prices, totals and stale versions; dedicated unit/item notes, selected AI changes and Revision/Additional relationships are absent. |
| Approval and final review (B5/F5) | Partial | `app/delivery.py` enforces simulated PM approval, preview version and delivery safeguards; pricing is not Manager-only and no single final review page includes a Telegram summary. |
| Core prompt/context (A1) | Partial | `backend/drafting.py` has a shared fact-only prompt and runtime business context already; three-profile isolation and the V2 output contract remain unimplemented. |
| Extraction/sufficiency (A2) | Partial | Structured extraction and manual fallback exist; no profile-aware critical-detail clarification stage before formal PDF generation. |
| Follow-up/change suggestions (A3/A4) | Missing | No conversation reanalysis or selectable ADD_ITEM/UPDATE_ITEM/UPDATE_FIELD workflow. |
| Outbound orchestration (A5) | Partial | Approved PDF delivery, retry guards and history exist; staff clarification sends and deterministic PDF-plus-summary delivery are absent. |
| V2 end-to-end cases (T1–T3) | Partial | Current mocked integration checks cover the original quotation flow; no complete three-profile conversation/revision journey. |

This is a code review, not live provider verification or a claim that V2 is
implemented. Detailed V2 policy decisions remain in the supplied plan.

## Local baseline verification

- `.\.venv\Scripts\python.exe -m pytest -q`: 274 passed, 2 skipped;
  one Starlette/httpx deprecation warning. PostgreSQL-only checks were skipped;
  `TEST_DATABASE_URL` was unset. These results exercise isolated SQLite adapters,
  not the real PostgreSQL driver.
- `node --test frontend/tests/*.test.mjs`: 22 passed.
- `node frontend/tests/integration.mjs`: 7 passed against the actual local API
  with temporary storage and mocked providers.
- `git diff --check`: passed.

## Access fix verification

- `.\.venv\Scripts\python.exe -m pytest -q`: 274 passed, 2 skipped,
  one existing Starlette/httpx deprecation warning. `TEST_DATABASE_URL` remained
  unset; real PostgreSQL checks were not run.
- `node --check scripts/run-replit.mjs`: passed.
- `node --test frontend/tests/*.test.mjs`: 24 passed, including anonymous
  entrance/assets/API and webhook-validation proxy checks.
- `node frontend/tests/integration.mjs`: 7 passed with mocked providers,
  including PM approval, saved-version PDF, retry and unknown-outcome checks.
- CLI smoke check: launched `node frontend/server.mjs` on a temporary port with
  both `DEMO_ACCESS_*` variables absent; anonymous homepage returned 200 with no
  `WWW-Authenticate` header. Stopped the child process after checking.
- `git diff --check`: passed.

The old `DEMO_ACCESS_USERNAME` / `DEMO_ACCESS_PASSWORD` secrets may remain in
Replit but no longer gate startup or access. Pull this fix branch into Replit
and Republish to deploy. Hosting checks, real PostgreSQL verification and live
provider checks remain pending. No login page or other V2 feature was added.
