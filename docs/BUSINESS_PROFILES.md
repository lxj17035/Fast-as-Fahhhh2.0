# B1: demo SME business profiles

Implemented on `codex/feat-business-profiles`, 24 October 2026.
This is the backend section of the supplied Domain 2 V2 plan. Frontend profile
selection (F1), Telegram conversation routing (B2), and AI prompt/output changes
(A1 onwards) remain separate sections.

## Data and scope

Three fixed synthetic profiles are seeded: `printing`, `cleaning`, `repair`.
Each has independently editable company name/address, currency and the existing
default validity. All new profiles default to MYR and one calendar month; this
section reuses the existing validity calculation and validation.

Profile records use the existing `quotation_records` JSON/JSONB storage with
kind `business_profiles`. The selected profile is persisted under
`settings/active_profile`. The original `settings/business` record is retained
and copied into Printing only on first profile initialization, preserving local
company edits, currency and validity. Seeding never resets an existing profile
or selection.

Telegram enquiries store a non-null `business_profile_id` at receipt, in the
same transaction as the message, enquiry and activity. Active-profile selection
and receipt use the existing shared transaction lock, including PostgreSQL's
advisory lock. Duplicate update delivery cannot repin an enquiry. Synthetic
demo intake follows the same selection rule and rejects a foreign client.

Clients, synthetic enquiries and quotations also carry `business_profile_id`.
The store rejects changing an existing record's profile and validates associated
client/enquiry scope. Background drafting uses the enquiry's pinned company and
client even if the active profile changes before drafting completes. Provider
output cannot set the profile. New quotations snapshot that company's settings;
existing sent PDFs and saved company details are retained.

The demo has one shared, manually selected active profile, not one per browser.
Inbox and client/quotation read, edit, preview, activity and send routes operate
within it. Foreign IDs return 404; select the original profile to work with its
records again. The internal store can read across profiles for background work;
HTTP boundaries enforce the active scope. The profile configuration endpoints
remain shared demo settings controls. These controls provide no production
identity or secure tenant authorization, especially with anonymous demo access.

## Settings API

| Method / path | Contract |
| --- | --- |
| `GET /api/business-profiles` | `{active_business_profile_id, items}`; items contain `id`, fixed `industry` label and existing company settings. |
| `GET /api/business-profiles/{id}` | One configured profile. IDs are `printing`, `cleaning`, `repair`. |
| `PATCH /api/business-profiles/{id}` | Existing companyName/companyAddress/currency/defaultValidity patch rules; does not change the active profile. Returns settings with `business_profile_id`. |
| `PATCH /api/business-profiles/active` | Exactly `{"business_profile_id":"cleaning"}` (or another known ID). Returns the saved selection. |
| `GET /api/settings` | Existing flat settings fields plus `business_profile_id`, for the active profile. |
| `PATCH /api/settings` | Existing partial patch, applied only to the active profile. |

Unknown profile IDs, identity/industry edits and extra selection fields are
rejected with 422. Invalid patches do not partially save or change selection.
Both the combined FastAPI app and standalone `Application.route` service expose
the same profile operations.

The fictional seeded client IDs are `demo-client`, `demo-client-cleaning` and
`demo-client-repair`. Existing client routes apply the active profile scope.
Unknown Telegram senders still receive separate initially blank client records;
they are not silently matched to these fictional seeds.

Illustrative local API selection (no provider calls or messages):

```powershell
Invoke-RestMethod -Method Patch -Uri 'http://127.0.0.1:8004/api/business-profiles/active' `
  -ContentType 'application/json' -Body '{"business_profile_id":"cleaning"}'
```

Until F1 is implemented, select profiles through this API, then reload the
existing frontend. Old open records from another profile return 404. Do not
switch profiles during a supervised demo review/send unless you intend to
change the workspace context for every browser.

## Existing PostgreSQL databases

Startup adds `enquiries.business_profile_id` if missing, with the original
Printing identity as the non-null default. It runs before legacy enquiry
backfill or record reads. Legacy receipts always backfill to Printing, regardless
of the subsequently selected active profile. Repeated startup preserves IDs,
timestamps, statuses, activity, quotation JSON and cached PDF bytes.

Legacy JSON clients, demo enquiries and quotations without a profile are read
as Printing; their stored historical JSON is not rewritten during startup.
Runtime remains PostgreSQL via `DATABASE_URL`; SQLite remains a disposable test
adapter. As with the existing prototype migrations, initialize with one app
instance before adding workers. An old application revision must not run
concurrently with this profile-aware revision: it cannot preserve the new scope
rules.

## Implementation files and verification

- Profile settings/scopes: `backend/settings.py`, `backend/store.py`.
- Pinned intake/upgrade: `app/database.py`, `app/migrations.py`, `app/main.py`.
- Pinned draft/quote context: `backend/drafting.py`, `backend/quotations.py`.
- API boundaries: `backend/server.py`, `app/quotation_routes.py`,
  `app/enquiries.py`, `app/quotations.py`, `app/delivery.py`.
- Regression cases: `tests/test_business_profiles.py`.

Focused SQLite check: `.\.venv\Scripts\python.exe -m pytest -q tests/test_business_profiles.py`
returned **21 passed, 1 skipped**.

With `TEST_DATABASE_URL` set to a disposable localhost PostgreSQL 16 container,
the following focused run exercised both database adapters and returned
**43 passed, 1 skipped**:

```powershell
.\.venv\Scripts\python.exe -m pytest -xq tests/test_business_profiles.py --tb=short --basetemp=.input/b1-pg-focused-20261024 -p no:cacheprovider
```

The skipped case is the PostgreSQL migration on the SQLite adapter; the same
case passed on PostgreSQL. A first attempt failed before executing tests because
the escalated process could not access an existing Windows pytest temp directory.
Using a new ignored workspace temp directory resolved that setup issue.

Final full merged backend run, with the same disposable `TEST_DATABASE_URL`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.input/b1-full-final-20261024 -p no:cacheprovider
```

Result: **466 passed, 3 skipped, 1 warning in 320.00 seconds**. All three skips
are PostgreSQL-only cases under the SQLite adapter; those cases passed under
PostgreSQL. The existing Starlette/httpx test-client deprecation warning remains.
This final run includes the extra foreign-profile duplicate-send rejection
check added during review. `git diff --check` and the staged equivalent passed.
The disposable PostgreSQL container was stopped after verification.

`node --test frontend/tests/*.test.mjs`: **24 passed**.
`node frontend/tests/integration.mjs`: **7 passed**, with isolated storage and
mocked providers. The PDF template/layout was not changed; snapshot tests compare
the saved PDF bytes across sending, profile edits/switching and schema upgrade.
Live AI/Telegram, hosted PostgreSQL migration and Replit deployment were not run.

Remaining V2 sections: B2–B5, A1–A5, F1–F5 and the complete T1–T3 journeys.
The existing safety checks and original flow do not establish those sections as
complete. B1 adds no login page and does not republish the demo.
