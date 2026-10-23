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
