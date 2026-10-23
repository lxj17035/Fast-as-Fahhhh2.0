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

## Deployment gap

The checked-in `frontend/server.mjs` already serves the UI anonymously. Neither
it, `app/main.py`, nor the checked-in nginx configurations implements Basic Auth.
`docs/REPLIT_DEPLOYMENT_GUIDE.md` records a different Replit entrance that adds
Basic Auth using `DEMO_ACCESS_USERNAME` and `DEMO_ACCESS_PASSWORD`, along with
an API proxy and process runner. Those runtime changes are absent from GitHub
at the reviewed revision. Removing authentication from the local static server
cannot change the hosted entrance.

The actual fix is pending synchronization of Replit's runtime source. Review
that source before removing its authentication guard and challenge response.
Keep the existing proxy, runner and asset routing working. Verify anonymous
homepage, application assets and API access without `WWW-Authenticate`; verify
that an invalid webhook secret is still rejected and Sales still cannot send.
Republish and check the hosted URL separately before claiming the prompt is gone.
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

No application behavior changed in this review. Hosted authentication removal,
real PostgreSQL verification and live provider checks remain pending.
