# Business Settings implementation — 24 October 2026

Branch: `codex/feat-domain2-v2`. Owner authorized implementation, tests, commit,
push and merge to origin/main. Reference: supplied quoteflow-settings-spec.md
and quoteflow-settings.html; prototype data is not imported.

## Mapping and decisions

- Company fields map to existing profile companyName/companyAddress/currency/
  defaultValidity and PATCH /api/business-profiles/:id. Currency remains the
  existing validated uppercase three-letter text field; no fabricated option list.
- Retain all five supported validity values, including saved 7d/2m, rather than
  silently losing existing settings. Native select/date ownership stays unchanged.
- Manager-only UI editing and collapsed Demo tools. Staff view-only; existing
  backend settings APIs remain simulated and do not enforce Manager authorization,
  as explicitly requested by the reference. No production login is added.
- Profile changes retain existing explicit shared-workspace selection and pinned
  enquiry scope. Shared dialog adds Cancel / Discard and switch / Save and switch.
- Remove saved-client lookup and explainer from this page only; client APIs/data remain.
- GET /api/demo/capabilities returns only {demoApprovalEnabled: boolean}; no secrets.
- Record-role preference defaults on, honors stored preference, and is unavailable
  when demo capability is off/unknown. Existing quotation saves always supplied a
  role for price authorization, making the old checkbox ineffective. New optional
  X-Record-Demo-Actor: false suppresses quotation_updated attribution only, retaining
  X-Demo-Actor and all pricing/review/send permission checks. CORS allows this header.
- No schema change, new dependencies, customer page, provider automation changes,
  PDF template changes, inbox change or sending behavior change.

## Checklist

- [x] Implement the settings section and supporting capability/logging contract.
- [x] Browser: Staff view-only/no Save/no tools; Manager dirty undo, save/reload;
  collapsed tools; all three switch dialog choices; active profile values; 360px.
- [x] Frontend unit suite: 47 passed.
- [x] Mocked real API integration: 10 passed, including immutable sent PDF after
  settings/profile changes. Live providers were not called.
- [x] Final backend SQLite/PostgreSQL regression passed; implementation ready to commit.

Browser plugin not available; installed Playwright/Edge used with temporary actual
FastAPI fixture and mocked providers. Disposable screenshots/scripts in .input/.
Strict premium audit was run: remaining findings are existing dynamic buttons
whose data-action or direct dialog listeners the literal static checker cannot
recognize; no customer controls are actionless. Settings textarea explicitly uses
resize:none and existing auto-grow behavior. Shell remains unchanged.

Repeatable browser check (installed Playwright required; no new project dependency):
`node frontend/tests/settings-browser.mjs` from repository root. Set
`QF_PLAYWRIGHT_MODULE` to an installed Playwright module URL when it is not resolvable
by name. Uses an isolated actual backend on localhost:8195 and frontend on :8196;
stop any earlier QA fixture using those ports. QF_TEST_PYTHON can override the
repository .venv Python. The runner closes browser/server and stops its fixture.
It also checks failed save-and-switch, capability-off rendering and keyboard focus.

SQLite-only full backend run: `.venv/Scripts/python.exe -m pytest -q`:
**407 passed, 5 skipped**, 132.42 seconds. Existing Starlette/httpx deprecation
warning only. Added tests cover both capability states and recording-off price
authorization; the combined run below additionally exercises PostgreSQL.
Final browser automation passed after correcting the test's disclosure-state
assumption; it now opens Demo tools only when closed. Product disclosure behavior
correctly survives same-route role changes and resets after route/profile loading.

Audit baseline comparison: the unmodified branch and final source both produce the
same five affordance.actionless-button findings (app.js lines 132/144/190 and
inbox.js lines 59/66). No new findings. These are existing dynamic templates
with delegated actions. The strict tool still exits 1; no clean-audit claim is made.


Final combined backend command: TEST_DATABASE_URL pointing to the isolated
localhost PostgreSQL container, `.venv/Scripts/python.exe -m pytest -q`:
**679 passed, 5 skipped**, 641.22 seconds. Existing Starlette/httpx deprecation
warning only. PostgreSQL container is disposable and removed after verification.
Final source: frontend **47 passed**, mocked real API **10 passed**, desktop/360px
browser automation passed, JavaScript syntax and `git diff --check` passed.
No live provider check, external customer message or deployment was performed.

Implementation commit message: `feat: simplify business settings and demo tools`.
Owner authorized pushing codex/feat-domain2-v2 and fast-forwarding origin/main;
the baseline remote main is an ancestor of this tested branch. Retain the working
checkout on codex/feat-domain2-v2.
