# Domain 2 V2 - phase handoff

Updated 24 October 2026, Asia/Kuala_Lumpur.
Existing branch: `codex/feat-domain2-v2`. Do not switch checkout during a run.

## Current checkpoint

Phases 1 (B1-B5), 2 (A1-A5) and 3 (F1-F5) are complete.
Next chat: Phase 4 T1-T3/RP2 and release verification. No V2 deployment or
new live provider call was performed in Phase 3. Synthetic preview and simulated
Staff/Manager roles remain; production identity/channels/queues are out of scope.

| Section | Implementation commit | Section verification |
| --- | --- | --- |
| F1 profile settings | `00d6565` (existing) | 25 frontend + 8 API; desktop/mobile |
| F2 Needs Assignment | `520ee21` | 26 frontend + 8 API; desktop/mobile |
| F3 Conversation Room | `4355e3c` | 29 frontend + 8 API; desktop/mobile |
| F4 generic editor/change application | `6d2d26b` | 30 frontend + 9 API; desktop/mobile |
| F5 Manager Review & Send | `9fef80d` | 31 frontend + 10 API; desktop/mobile and partial-summary recovery |

Full merged backend suite used TEST_DATABASE_URL on a fresh disposable localhost
PostgreSQL 16 container and isolated SQLite adapters: **644 passed, 5 skipped,
1 existing Starlette warning**, 665.87s. PostgreSQL-only skips under SQLite had
PostgreSQL counterparts. The container was removed after verification.

Exact source files, commands, limitations and static audit exceptions:
[frontend progress](V2_FRONTEND_PROGRESS.md). Earlier backend/AI reports remain
[V2 backend](V2_BACKEND_PROGRESS.md), [V2 AI](V2_AI_PROGRESS.md).
No backend business logic or PDF template changed in Phase 3. Saved PDF bytes
are verified against the final review SHA-256 in the browser before approval.

## Continue Phase 4

Read AGENTS.md, README.md, docs/WORKFLOW.md and
[canonical plan](DOMAIN2_V2_CODEX_PLAN.md) before changes. Use
[AI analysis contract](AI_ANALYSIS.md), [approval contract](PM_APPROVAL.md),
[frontend contract](FRONTEND.md) and current source as authoritative behavior.
Test and commit each section before the next. Stop at the phase boundary;
perform the plan's standing-authorized origin/working-branch and origin/main
publication while preserving remote changes. Publication is not deployment.

- T1: complete synthetic Printing journey through real UI/API with attributed
  clarification/customer answer, explicit current-message review, Manager pricing,
  final saved PDF plus matching summary and approved send. Verify histories/dates.
- T2: representative Cleaning and Repair cases, dynamic context and generic notes;
  no Printing assumptions. Phase 3 verified profile switching and generic field
  contracts; it does not replace these complete cross-profile scenarios.
- T3: explicit Revision/Additional and unclear grouping, immutable old PDF,
  negative authority/scope/stale/duplicate/unknown cases. Phase 3 includes focused
  backend/API safeguards; retain the full integration acceptance checklist.
- RP2: separately verify the published Replit provider configuration, then a fresh
  fictional enquiry in a team-controlled Telegram chat. Capture sanitized matching
  hosted application and Runpod evidence before recording. No customer sends.
  Missing access is a blocker, never evidence of completion.

## Frontend behavior to retain

Inbox exposes Needs Assignment with explicit Staff actions and original history.
Conversation Room uses attributed messages and editable AI questions; only explicit
Send calls /messages with a stable request ID. Pending/unknown text sends hold
across reloads. No automatic resend. Analysis evidence is compared with current
quotation version, source IDs, unresolved messages and accepted Staff messages.

Generic items retain units/notes and blank prices. Staff cannot enter prices;
Manager mutation headers are explicit. Selected AI changes can be edited/excluded
and applied through version/evidence-bound /apply-changes. New incoming messages
need an explicit review checkbox when saving. Sent quote forks are explicit;
Additional requires a distinct enquiry in the same original chat.

Manager Review & Send shows server-saved fields, actual PDF and deterministic
summary together. Approval uses current version and exact eligible retry ID.
Confirmed summary failure freezes the accepted PDF and offers summary-only retry.
Back to Edit explains that lock. New messages are not silently acknowledged.
Unknown/pending outcomes hold. Nullable legacy component data is not evidence of
summary acceptance. Existing Valid For engine and server totals remain canonical.

## Live evidence and release limits

RP1 is historical: one V2 Runpod request on 24 October 2026, HTTP 200, 1,362
tokens; [sanitized report](V2_RUNPOD_RP1.md). It does not verify hosted Replit,
Telegram or billing. RP2 stays unchecked. Phase 3 providers were all mocked.
No hosted deployment, production identity, full accessibility certification,
all-browser validation or measured productivity result is claimed.

For later backend tests create a new disposable localhost-only PostgreSQL
container. Never use runtime, Replit or customer storage. Keep raw artifacts,
screenshots and scripts ignored under .input; secrets remain local and unprinted.
