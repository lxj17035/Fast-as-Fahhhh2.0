# V2 AI analysis contract

One shared prompt/schema in `backend/drafting.py` is used by Runpod and the
optional OpenAI adapter. Backend supplies pinned validated profile, company/client
and attributed conversation context. Unknowns remain unknown; industry details
are notes, and prices/recipient/approval/send fields are rejected.

The extraction schema now requests display-only `shortTitle`, in the customer's
language, with stated quantity/product and no client identity, dates or prices.
Validation caps Chinese titles at 15 characters and English at six words/60
characters. Older provider fixtures without this field remain compatible.
Initial quotations save it in JSON alongside the full summary; later analysis
does not silently overwrite the saved title. Old inbox rows use compact saved
item/quantity text, then message/summary fallback, without extra inference.

Initial draft creation retains its analysis. A newly received assigned customer
reply triggers renewed analysis, without updating the saved quotation. Duplicate
updates do not spend another request. Completed unchanged snapshots are reused;
manual/failed/stale snapshots can be analyzed again explicitly.

- GET `/api/enquiries/{id}/analysis`: latest snapshot or null in active scope.
- POST same URL: explicitly request analysis; enabled simulated Staff/Manager
  header required. IDs may be native Telegram UUIDs or synthetic demo IDs.
- Snapshot includes `signature` (quotation/version, source IDs, unresolved IDs,
  business context and attributed conversation), `extraction`, `status`, `error`,
  `stale`, and `resolvedAssignments`. Initial/manual analysis never sends messages.
- `extraction.clarificationSuggestions` is editable text for the Conversation Room.
  Staff sends chosen/edited text through existing POST `/messages` with its own
  stable `request_id`. Analysis has no sender and never invokes that endpoint.
- A message or edit arriving during inference makes the result stale. It cannot
  acknowledge new messages or silently alter Staff content. Staff must review the
  current evidence before formal review/send.

AI may propose `assignmentSuggestions` with `update_id` and
`confirmation_update_id`. Backend only resolves an unresolved same-profile/chat
message when a later already-assigned customer reply references that exact
Telegram message and says `This message is for <enquiry UUID or quotation number>`.
Staff can assign the confirmation first. Anything less clear stays Needs
Assignment; model claims or target IDs alone are insufficient. Original receipts
and Staff decisions are retained. This intentionally conservative path does not
interpret vague confirmations or create a new grouping policy.

Runtime uses PostgreSQL. Provider failures return sanitized manual/failed analysis,
and tests mock all providers. Frontend integration is Phase 3.


Renewed analysis also exposes `suggestionSetId`, `changeWarnings` and
`relationshipIntent`. GET quotation `/suggestions` and POST `/apply-changes`
remain the existing explicit review mechanism. Raw model changes do not update
quotation fields. Identical changes are collapsed; duplicate additions or
conflicting updates are flagged. Sent quotes only yield an advisory relationship
and warning; Staff explicitly forks first. Initial extraction already supplies
new-draft items, so its proposed changes are not reapplied as duplicate additions.
## AI suggestions in Messages (24 October 2026)

Quote has no AI assistance disclosure. Messages places usable, editable/selectable
AI Suggested Changes after the conversation/questions and before the composer.
Empty or stale sets are hidden. Explicit apply keeps backend source/version and
price guards, invalidates an earlier Staff submission and saved PDF review, and
shows Changes applied to Quote with Go to Quote. Unsaved composer text survives.
Analyze/Retry appears only for missing/failed/stale analysis with no active job;
manual Quote editing and Save draft remain available during AI failure.

Analysis snapshots now expose running while renewed analysis is in progress.
The existing transaction reserves a signature before inference; duplicate requests
reuse an active signature. The same row is replaced by completion/failure. After
180 seconds an abandoned running snapshot is reported as retryable failure. No
worker queue or external notification was added. Read-only detail polling also
refreshes unfinished/stale analysis without overwriting quote/composer edits.
