# Frontend handoff

Branch: `feature/frontend`. Frontend implementation and tests are under
`frontend/`. No existing Python application code, backend tests, dependencies,
API contracts, environment files, or runtime database configuration were changed.
The work is committed locally for review; no push or deployment is included.

## Structure

```text
frontend/
  index.html                Browser entry and accessibility landmarks
  config.js                 Public API base address only
  server.mjs                Local-only static server; serves frontend assets
  src/
    app.js                  Routes, state, screens, and interactions
    api.js                  Existing FastAPI endpoint adapter and error handling
    model.js                Payload normalization and frontend approval guards
    experience.js           Next-step guidance and links to incomplete details
    pdf-viewer.js           Local PDF.js rendering of the backend's saved bytes
    styles.css              Responsive green/neutral workspace design
  tests/
    *.test.mjs              Node API/model/static-server checks
    integration.mjs         JS client against the real, isolated Python app
    preview_backend.py      Optional temporary QA fixture with mocked providers
```

Vanilla JavaScript ES modules keep the application small and avoid a build step.
PDF.js is the one frontend dependency; pnpm-lock.yaml pins its distribution.
PDF rendering follows the [official PDF.js examples](https://mozilla.github.io/pdf.js/examples/).
The static server exposes only application files and selected PDF.js resources;
it does not proxy API requests or serve the repository, `.env`, or tests.

## Screens and routes

Hash routes preserve refresh/deep links without backend routing changes:

- `#/`: Telegram enquiry inbox, current-page counts/search/status filters,
  previous/next pagination, source and timestamps, and open-enquiry links.
- `#/enquiries/:id`: original message/chat, AI/manual summary and fallback
  reason, missing-information review, client/date/item/note editing, backend
  totals/expiry, saved PDF, PM approval, attempts and chronological activity.
- `#/settings`: business profile, currency/default validity, existing-client
  load/edit, and optional demo-role attribution on edits.

The review follows Details -> Preview -> Send, with a next-step card explaining
what needs attention. On desktop, the customer message and editor share the main
column beside the saved PDF. On mobile, these become a single column and the
inbox becomes a compact list with visible status badges. Navigation is an icon
rail at narrow widths, with accessible names. Dates/notes, technical references,
draft summaries, and activity are expandable; unresolved facts stay prominent.

The inbox offers All, To review, Sent, and Needs checking filters. The latter
groups confirmed failures and uncertain deliveries, retaining distinct Not sent
and Check Telegram labels. Empty inboxes explain how to get started. Business
settings emphasize the company profile; client lookup and demo options expand
only when needed.

## Existing backend integration

The default API is `http://127.0.0.1:8004`, configured in `frontend/config.js`.
Only public addresses belong there. The frontend server binds
`127.0.0.1:5173`, already allowed by the existing backend's CORS configuration.

| Operation | Existing API used |
| --- | --- |
| Connection | `GET /api/health` |
| Inbox | `GET /api/enquiries?limit=25&offset=N` |
| Messages, attempts, activity | `GET /api/enquiries/:id` |
| Saved draft | `GET /api/enquiries/:id/quotation` |
| Missing draft | `POST /api/enquiries/:id/draft`, `{manual: boolean}` |
| Save edits | `PATCH /api/quotations/:id`, current `version` and allowed fields |
| PDF | `GET /api/quotations/:id/pdf?version=N`, verify version header |
| Approval | `POST /api/quotations/:id/send`, `X-Demo-Actor: pm` |
| Business | `GET/PATCH /api/settings` |
| Client | `GET/PATCH /api/clients/:id` |

Inbox/activity snake_case and quotation camelCase fields are retained. Provider
IDs remain strings. The frontend never calculates payable totals or expiry;
it labels unsaved totals as the last saved values. Blank quantity/price becomes
null in PATCH, while explicit zero prices remain explicit. Unknown customer
information is not filled in by the UI. Untrusted message/AI text is escaped.

## Approval, uncertainty, and version handling

1. Save draft permits incomplete work. Save & preview saves edits with the current
   version and then loads the saved PDF; it never sends. A 409 keeps local edits visible and asks
   the user to reload the saved record; it never silently overwrites a conflict.
   If PDF loading fails after a successful save, the saved version stays current
   and the user can retry preview without repeating the save.
2. Explicitly load the actual backend PDF for that saved version. PDF.js renders
   those bytes locally, with page navigation and an Open PDF link. Rendering must
   succeed before approval is enabled. Edited or reloaded quotations need preview
   again. PDF bytes and object URLs are released on replacement/navigation.
3. PM checks an explicit confirmation containing quotation number/version,
   total, client and original Telegram chat. The request contains only
   `expected_version`, `approved: true`, and an optional `retry_of_attempt_id`.
4. Confirmed failures (HTTP 502 with a recorded failed attempt) remain visible.
   Retry requires the API's `can_retry` flag and a new explicit PM confirmation
   naming the exact failed attempt. Pending/sent/unknown never expose retry.
5. A lost/unreadable/ambiguous response is not retried. A browser-session hold
   blocks another click until history identifies a new terminal failed/sent
   attempt. Older failed attempts cannot clear a newer unknown request. A 4xx
   rejection from this handler occurs before upload and clears the local hold;
   persisted attempts still govern whether sending is possible. An unconfirmed
   request with no persisted outcome remains blocked for manual verification.

The API remains authoritative for every mutation and delivery check. The UI's
guards improve the review flow; they are not authentication. Roles are visibly
simulated. Enable the existing backend `ENABLE_DEMO_APPROVAL=true` only for the
supervised demo. Edit attribution is off by default so normal edits work when
that flag is false; the timeline correctly shows an unspecified actor. Turn the
attribution checkbox on in Settings only when backend demo approval is enabled.

Only role/attribution preferences and ambiguous-send guards are kept in session
storage. Customer messages, quotes, keys, or database URLs are not stored there.
There are no background sends or provider requests from the browser.

## Limits and review

- Search/filter/counts apply to the currently loaded inbox page, explicitly labelled.
  The backend has no global filtering or total-count API.
- Clients load by ID because the backend exposes no client-list endpoint. The
  relevant Telegram client ID appears under More details in quotation review.
- Simulated `/api/demo/enquiries` records are not part of the normalized Telegram
  inbox. The UI does not invent inbox rows from them.
- Refresh is explicit; the UI does not poll over unsaved edits. Navigation/reload
  protects unsaved work. Failed mutation responses preserve the entered values.
- Browser QA uses fictional data and mocked providers. No live Telegram, AI,
  webhook registration, PostgreSQL runtime mutation, public hosting, or end-to-end
  live demonstration is claimed by frontend verification.
- Local backend regression: 274 passed, 2 skipped (PostgreSQL-only cases), one
  existing Starlette/httpx deprecation warning. Historical combined PostgreSQL
  results in other docs were not rerun as part of this frontend work.

Setup and safe QA commands are in [frontend/README.md](../frontend/README.md).

Usability verification: **22 frontend tests and 7 isolated API checks passed**.
Browser review covered desktop and 390px mobile, unsaved navigation, saved-version
PDFs, Sales/PM guidance, explicit approval, failed retry, sent protection, and
unknown-delivery protection. Providers were mocked; no customer messages were sent.

## Canonical UI Map

Visual context: [DESIGN.md](../DESIGN.md). Preserve existing shared primitives.
Product sources: [workflow](WORKFLOW.md), [profile scope](BUSINESS_PROFILES.md),
[approval](PM_APPROVAL.md), [AI analysis](AI_ANALYSIS.md).

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
| --- | --- | --- | --- | --- |
| Select/Listbox | app.js native select and validitySelect | DESIGN.md; platform owns popup geometry | native | profile browser QA and API integration |
| Date | app.js input helper; native date | WORKFLOW.md existing validity engine | native | saved PDF/API checks |
| Form | app.js input, task, errorBox and submit handler | API validation; edits remain after rejection | settings/client/quotation | API tests and browser QA |
| Scrollbar | styles.css global baseline | DESIGN.md runtime token mapping | geometry only | desktop/mobile browser QA |
| Toast | app.js noticeBox and errorBox | inline role=status and role=alert | success/warning/error | browser QA |
| CRUD | app.js loadRoute, navigate, discardEdits and task | profile and quotation API contracts | stay on successful edit | isolated actual API integration |

F1: Settings lists Printing, Cleaning and Repair from `/api/business-profiles`.
An explicit switch writes the shared active selection, discards old workspace
records/PDF/client state, resets inbox paging/search and reloads settings. Unsaved
edits use the existing discard dialog; cancellation retains them. Business edits
PATCH the named profile, so another browser changing active scope cannot redirect
the save. Existing enquiries and sent snapshots stay with the original profile.
The profile label remains in the sidebar; profile choice never comes from AI.
Native select/date popup geometry is deliberately platform owned. Textareas grow
with entered content. No frontend package install or build is required for F1.

V2 F2: Inbox includes Needs Assignment, original chat and association history.
Staff explicitly assigns a same-chat enquiry reference, creates a new enquiry,
or marks the message unrelated. Server validation remains authoritative.

Local preview usability update (24 October 2026; not published): assignment uses
a native select of same-chat enquiries on the loaded inbox page, labelled by
date and original message. A collapsed manual-ID fallback handles other pages.
Empty assignment gives an actionable local prompt. Each inbox row has Copy ID;
successful clipboard writes show Copied!, while blocked clipboard access shows
the ID for manual copying. PDF source-review conflicts explain the review
checkbox/save step instead of implying another person edited the quotation.
Verification: 31 frontend checks and 10 mocked actual-API checks passed for the
assignment update; 31 frontend checks passed again after Copy ID. Local browser
confirmed the empty-assignment prompt and successful Copy ID status. Changes
remain uncommitted pending the user's local preview; Replit is unchanged.

User-approved role guidance refinement: Staff preparation guidance excludes
price-entry tasks, shows Waiting for Manager pricing for blank saved amounts,
and labels preview actions Preview draft. Manager retains price validation and
Preview quote. Once Staff details are ready and saved/previewed, blank prices
lead to Waiting for Manager pricing rather than an uneditable price task.
Required customer/item checks and backend approval guards remain unchanged.
32 frontend checks passed, including role-specific unpriced draft guidance;
local browser confirmed no Staff price task, waiting labels and Preview draft.

### Inbox reference redesign — local preview only

Owner-approved reference: supplied `quoteflow-inbox.html` / `quoteflow-inbox-spec.md`.
Only the inbox route receives the compact header/760px task-list layout. Settings
is in its header; role identity remains sales/pm. Copy ID is retained. Assignment
expands inline with same-chat choices and association history; Mark unrelated
remains available as a server-recorded decision, distinct from local Close.

No API/schema changes. The existing paginated list is enriched with read-only
quotation/detail requests in batches of five enquiries. Counts cover the loaded
page, explicitly labelled. Stage mapping in `frontend/src/inbox.js` requires
reviewed incoming IDs, no unresolved same-chat assignment, valid customer/items/
units/dates and resolved missing facts before Needs price; saved nonblank prices
yield Ready to send. This is a navigation hint, not send authorization. Actual
Manager review/PDF/approval validation remains mandatory. Failed/pending/unknown
states retain a separate Needs checking stage owned by Manager, never Ready.

The owner approved sessionStorage-only Close/Restore for local preview. Records
include role/time and a source/version signature, scoped by business profile.
Updated source/version reopens a locally closed item. Close does not mutate the
server, mark unresolved messages unrelated, cancel work or clear send holds.
Both roles can restore; Undo lasts 10 seconds and ends on tab/role/navigation.
Closing a browser session loses these records; other browsers do not share them.

The owner approved synthetic WhatsApp/Instagram/Facebook rows only behind an
explicit localhost checkbox. They are never stored in backend data. Mock actions
explain the display-only limitation; non-Telegram Manager Check & send is disabled.
No new integration or ad attribution is claimed. Titles use saved AI summary,
falling back to 40-character message text; Chinese messages retain Chinese when
the summary is English. No new inference is performed. Long summaries may still
be truncated; the current fixed mock extractor repeats the same summary.

Verification: 35 frontend tests passed; 10 actual-API tests with isolated SQLite
and mocked providers passed on retry after an initial startup timeout. Browser
plugin unavailable; existing Playwright/Edge used for automated QA alongside IAB
inspection. Desktop 1365x900, mobile 390x844 and 360x800: role task ownership,
combined filters/counts and empty recovery, Close/Undo expiration/Restore/reload,
disabled mock sends, inline sorting/history/empty validation/assignment payload,
keyboard focus and original detail navigation passed. No page/console errors or
horizontal overflow. Screenshots/scripts are ignored under .input/local-preview.
No backend/PDF template changes, live providers, Replit publish or new commits.

V2 F3: Conversation Room shares panel/form/feedback helpers. The original chat
is immutable; AI text is advisory and editable. Explicit Send is attributed to
Staff or Manager, using a request ID; unknown/pending outcomes hold further sends.
Analyze requests never send text. Stale evidence hides clarification actions.

V2 F4: Existing item rows own item name, quantity, unit, Manager-only price,
saved amount and notes. AI Suggested Changes uses native labelled selection
checkboxes and existing fields, explicit apply and stale version rejection.
An explicit message-review checkbox acknowledges exactly the loaded incoming IDs.
Sent quotation forks require a confirmed revision/additional choice.

V2 F5: Manager Review & Send is one final view within the enquiry route.
It uses GET /review?version=N, verifies the actual PDF bytes against its saved
fingerprint, and shows saved data plus the server summary together. Back to Edit
returns to the same enquiry. Frozen summary-only retries keep the editor locked.
Approval always references the saved version and exact eligible failed attempt.
Delivery history distinguishes PDF/summary acceptance and historical null data.
The existing helpers own navigation, forms, notices and busy states; v2-panel
adds shared padding and wrapping. Mobile tables scroll and PDF canvases scale.

Latest owner refinement: remove Copy ID from inbox rows because assignment uses
the dropdown. Internal IDs/API associations remain unchanged; the collapsed
manual-ID assignment fallback remains available for records on another page.
35 frontend checks passed after removal. Local preview only.

Latest approved refinement: restore the shared left sidebar/Settings position on
Inbox; retain responsive 238/210/74/58px navigation widths. Inbox titles prefer
saved shortTitle, then compact saved item/quantity, then existing text. Chinese
message titles remain Chinese. Backend prompt/schema/validation now generate
and store shortTitle for new drafts without an additional provider call; restart
is needed for the running local mock backend to load changed Python source.
No historical records were rewritten or live Runpod requests performed.
Verification: 36 frontend checks; focused drafting/Runpod 39 passed; full merged
SQLite + disposable localhost PostgreSQL run: 659 passed, 5 skipped, one new test
fixture failure (incorrect Store context manager). That fixture was corrected
without application changes and both short-title tests then passed. Full suite
was not rerun after that test-only correction. Disposable container removed.
Desktop/mobile 390/360 Inbox browser checks passed after sidebar adjustment.

### Detail page reference redesign — local preview

Owner-approved decisions: retain Staff editing permissions on all editable
unsent quotations, Manager-only price/approval authority, saved price retention
after edits and fresh preview. Do not introduce a handover status, notifications
or Save-for-Manager action. No backend/API/schema or PDF template change here.

- Quote: canonical customer/item/unit/notes/date fields, saved state and totals;
  actual missingInformation points with Mark checked / local Undo until route
  reload; AI Suggested Changes and Analyze current messages stay in a disclosure.
- Preview: existing versioned PDF.js renderer, prices-missing notice and review
  checkpoint. Unreviewed incoming sources prevent an updated unsent preview;
  already delivered/frozen PDFs retain their existing preview exception.
- Messages: attributed chronological conversation bubbles, highlighted new
  incoming messages, selected actual clarification suggestions copied to the
  composer, explicit Send only. Stale AI suggestions remain unavailable.
- Activity: newest-first plain-English events, delivery attempts and technical
  references, saved version/client/source IDs and full summary. Unknown event
  keys use a neutral label instead of displaying implementation names.

Unreviewed messages are derived from saved reviewedMessageIds versus current
incoming update IDs, not a read timestamp. The yellow notice contains all pending
customer text and links to Messages. Confirm handled & save quote explicitly
saves current edits and the exact incoming ID set through the existing endpoint.
No new incoming messages means no review-confirmation control. Saving a draft
without that confirmation does not silently acknowledge new requirements.

Every 15 seconds, while the detail page is visible, an idle client makes a
read-only detail request. Changed message IDs refresh conversation/analysis,
invalidate the preview and show the notice. Existing form/composer edits remain;
input focus is restored. No extra AI POST, send, background queue or auto-reply.
Final Manager review still verifies the saved PDF hash and matching summary.
Final approval opens Send this quotation? / Send to Telegram; Cancel sends nothing.
Confirmed failure retry and frozen summary-only delivery retain backend guards.
Sent Revision/Additional controls use the existing fork confirmation form and
contracts. Historical quotation browsing remains in FUTURE_IMPROVEMENTS.md.

Files: frontend/src/app.js, detail.js, detail.css, index.html, detail.test.mjs and
updated existing journeys.mjs. Desktop/mobile references and checks are under
ignored .input/local-preview and .input/phase4. New-message screenshots use an
explicit browser-only synthetic incoming fixture, not live provider proof.

Verification: 39 frontend checks and 10 isolated mocked actual-API checks passed.
Updated journeys.mjs passed complete Printing/Cleaning/Repair journeys and
post-send unclear grouping -> clarification -> Revision -> independent Additional,
with new Manager approval and unchanged original PDF bytes/metadata. Journeys
verify automatic new-message refresh without reloading and retention of unsaved
notes, exact reviewed source IDs, Staff price read-only, saved totals, rendered
PDF hash/summary, and cancellation/final confirmation before mocked delivery.
Desktop 1365x900/mobile 390x844 passed without overflow/page or console errors;
separate 360px notice, Reply-to-Messages and keyboard-tab checks passed. Browser
plugin absent; regular Playwright/Edge was used. No new live Telegram/Runpod call,
Replit deployment or Git commit is claimed. Backend/PDF tests were not rerun for
this frontend-only section; the earlier short-title backend results remain above.
## Current local workflow — 24 October 2026

This section supersedes the historical no-handover/preview-first notes above.
Inbox retains a top-right `↻ Refresh inbox`. Tabs are Messages, Quote, Preview,
Activity. New incoming source IDs select Messages; reopening without new sources
selects Quote. Tabs retain quote/composer/suggestion state.

Save draft permits incomplete details. Submit for review requires a saved,
complete Staff draft and explicit current-message confirmation, but no prices or
preview. It calls the durable submit-review endpoint. Only current handoffs move
normal preparation tasks to Manager To do. Staff edits (including AI apply) return
the preparation task to Staff; another submission is required. Manager's own
edits retain Manager routing while the source IDs remain current, but invalidate
the submitted version and require fresh saved PDF/summary review. New or unsorted
customer requirements return preparation to Staff. Delivery holds stay Manager
Needs checking. This does not implement Manager notification.

### Current AI placement
Messages owns editable AI Suggested Changes between conversation and composer.
No usable changes means no region. Explicit apply reports Changes applied to
Quote and offers Go to Quote. Recovery-only Analyze messages / Retry analysis
uses running/completed/failed state and existing source/version checks. Quote
always keeps manual editing and draft saving. No AI automatic overwrite or send.
