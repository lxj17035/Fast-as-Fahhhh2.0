# Domain 2 V2 - phase handoff

Updated 24 October 2026, Asia/Kuala_Lumpur.
Existing branch: `codex/feat-domain2-v2`. Do not switch checkout during a run.

## Current checkpoint

Phases 1 (B1-B5), 2 (A1-A5), 3 (F1-F5) and local Phase 4 T1-T3 are complete.
Next step: Replit dependency rebuild/security scan, publish V2, then RP2 live
verification. RP2 is blocked and remains unchecked. No V2 deployment or
new live provider call was performed in Phase 4. Synthetic preview and simulated
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

## Phase 4 local acceptance checkpoint

| Section | Commit | Verification |
| --- | --- | --- |
| T1 complete Printing | `9ffb415` | 2 SQLite/PostgreSQL cases; full actual UI desktop/mobile |
| T2 complete Cleaning/Repair | `7adf602` | Combined 6 database cases; 3 industry UI journeys |
| T3 post-send/negative | `de48358` | Combined 14 database cases; unclear/Revision/Additional UI flows |
| Pillow dependency/build floor | `fcc7c71` | Pillow 13.0.0 locally; 10 PDF/readiness tests; 32 compatible packages |

Detailed files, exact commands, evidence, browser environment and release blockers:
[Phase 4 report](V2_INTEGRATION_PROGRESS.md). External AI/Telegram transports
were mocked; real services, routing, storage, API, JS client, PDF renderer and
browser were used. Original sent PDF bytes/metadata remain unchanged after forks.
No application behavior/PDF template changed. Replit's published older UI and
`/api/business-profiles` returning Not Found were checked read-only.

Remote `origin/main` publication commit `1f6eca4` was preserved through normal
merge `c2f2c48`. Publication is distinct from hosted deployment.

Final Phase 4 merged regression (including Pillow source/build fix): **658 passed,
5 skipped, 1 existing Starlette warning**, 872.69s, isolated SQLite and fresh
localhost PostgreSQL 16. Container removed afterwards. Frontend **31 passed**,
mocked actual API **10 passed**; all three complete profile UI journeys and
post-send unclear/Revision/Additional flows passed. Exact commands and limitations
are in the [Phase 4 report](V2_INTEGRATION_PROGRESS.md).

## Continue release verification

Read AGENTS.md, README.md, docs/WORKFLOW.md and
[canonical plan](DOMAIN2_V2_CODEX_PLAN.md) before changes. Use
[AI analysis contract](AI_ANALYSIS.md), [approval contract](PM_APPROVAL.md),
[frontend contract](FRONTEND.md) and current source as authoritative behavior.
T1-T3 were tested/committed separately. Stop at the phase boundary;
perform the plan's standing-authorized origin/working-branch and origin/main
publication while preserving remote changes. Publication is not deployment.

- T1 (passed locally): complete synthetic Printing journey through real UI/API with attributed
  clarification/customer answer, explicit current-message review, Manager pricing,
  final saved PDF plus matching summary and approved send. Verify histories/dates.
- T2 (passed locally): representative Cleaning and Repair cases, dynamic context and generic notes;
  no Printing assumptions. Phase 3 verified profile switching and generic field
  contracts; it does not replace these complete cross-profile scenarios.
- T3 (passed locally): explicit Revision/Additional and unclear grouping, immutable old PDF,
  negative authority/scope/stale/duplicate/unknown cases. Phase 3 includes focused
  backend/API safeguards; retain the full integration acceptance checklist.
- RP2: separately verify the published Replit provider configuration, then a fresh
  fictional enquiry in a team-controlled Telegram chat. Capture sanitized matching
  hosted application and Runpod evidence before recording. No customer sends.
  Missing access is a blocker, never evidence of completion.

Before RP2, sync the tested main into Replit without overwriting private Secrets
or unrelated local changes. Follow [Pillow remediation](PILLOW_SECURITY.md): the
local source now requires Pillow >=13.0.0,<14 and upgrades existing `.pythonlibs`
files during deployment build. The user-reported Replit scan still needs an
actual hosted dependency rebuild/import check and fresh scan. Other critical/high
findings are not claimed fixed. Republish only after reviewing those results.
The user confirmed the old hosted UI was expected because V2 had not been republished.

Published URL: `https://fast-as-fahhhh-20.replit.app/`. Local configuration presence
shows a bot token, webhook secret, Runpod configuration/key and LIVE_TEST_CHAT_ID;
demo approval is disabled locally. No secret values were printed or changed. A test chat
means a team-controlled conversation with the bot, not its token. Verify ownership
before sending; local `.env` is not proof of hosted Secrets/provider selection.

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
