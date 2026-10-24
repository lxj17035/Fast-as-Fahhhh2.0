# V2 AI analysis contract

One shared prompt/schema in `backend/drafting.py` is used by Runpod and the
optional OpenAI adapter. Backend supplies pinned validated profile, company/client
and attributed conversation context. Unknowns remain unknown; industry details
are notes, and prices/recipient/approval/send fields are rejected.

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
