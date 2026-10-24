# V2 hosted Runpod RP2 verification

Historical notes preserved from the pre-existing local working tree. This local
development session did not revisit the hosted site or call Runpod/Telegram.
RP2 remains incomplete pending correlated request/usage evidence.

24 October 2026, Asia/Kuala_Lumpur. Status: in progress; RP2 remains unchecked.

Published application: https://fast-as-fahhhh-20.replit.app/

## Direct hosted observations

- In-app browser inspection reached `Inbox · QuoteFlow` and showed Connected,
  the Staff simulated role with Manager available, and Needs Assignment.
- `/api/business-profiles` returned the V2 Printing, Cleaning and Repair list,
  with `active_business_profile_id` equal to `printing`.
- Initial inbox baseline: seven older enquiries, five to review and two sent;
  no fresh RP2 marker was present. Older records do not prove new inference.
- Generic web fetch could not access this site; the observations above came
  from the actual in-app browser.

The prior old-build observation in V2_INTEGRATION_PROGRESS.md is historical;
the V2 interface and profile API are now accessible at the published URL.

## Controlled fresh test pending

Fresh hosted intake and saved draft were subsequently observed directly:

- Marker: `RP2-20261024-A`.
- Enquiry: `03fff564-9da1-4bc0-bd60-40f778adf2bb`.
- Quotation reference: `QUO-4B706C7BFA50`.
- Customer message displayed 24 October, 02:50 pm Malaysia time.
- Activity displayed inbox receipt, Staff assignment and quotation draft creation
  at 02:52 pm; Staff clarification requested/sent at 02:53 pm.
- UI explicitly states: "AI prepared this draft. Check it against the message."
- Saved draft: Black event T-shirt with front printing; quantity 20; unit pcs;
  notes retain 10 M/10 L and required-by 30 November 2026. Unit price and total
  remain unset. Address remains blank and unconfirmed.
- Summary accurately retains the quantity, sizes, print scope and deadline.
- Quality finding: customer name is blank despite "Fictional Example Events"
  in the input; missing-information text says no client name/address provided.
  A PM/Staff correction is required; extraction is not fully accurate.
- Subsequent AI suggestions mention an address from a separate incoming message;
  it appears as an unchecked proposed change, not a silently saved address.

These observations establish fresh hosted intake and AI-labelled draft behavior,
but correlated provider request/usage evidence is still outstanding. The agent
opened read-only detail/summary/activity controls only, initiated no analysis and
sent no messages. Subsequent Staff activity was already present when inspected.

Requested one incoming message from the user's team-controlled Telegram chat:

> RP2-20261024-A: Fictional Example Events needs 20 black event T-shirts,
> 10 size M and 10 size L, with front printing, required by 30 November 2026.
> Delivery address is not confirmed. Please prepare a quotation.

Capture the receipt timestamp/enquiry ID, fresh AI result and activity, blank
prices, unknown address and matching provider evidence. Do not fabricate an
incoming webhook or use a cached draft as live intake proof. No outgoing
Telegram message or provider call was initiated by this verification so far.

## Configuration and provider proof pending

The user supplied the following sanitized Replit configuration report after
the initial inspection (user-provided evidence; not independently executed):

```json
{
  "readyForAI": true,
  "aiProvider": "runpod",
  "readyForLiveTest": true,
  "checks": {
    "DATABASE_URL": true,
    "ENABLE_DEMO_APPROVAL": true,
    "TELEGRAM_BOT_TOKEN": true,
    "TELEGRAM_WEBHOOK_SECRET": true,
    "LIVE_TEST_CHAT_ID": true,
    "RUNPOD_API_KEY": true,
    "RUNPOD_CONFIG": true
  },
  "scope": "Configuration presence/format only; database access, API credentials and chat ownership are not verified"
}
```

This supports selected-provider/configuration readiness; it does not establish
successful inference or independently identify the published process environment.

The user was asked to run `python -m scripts.check_live_config` in the Replit
environment used by the published deployment and supply only sanitized JSON.
Workspace/local configuration alone does not establish deployment configuration.
The script verifies presence/format, not credential validity or chat ownership.

`backend/runpod.py` currently validates the extraction but does not retain the
provider response ID or token usage. Therefore application output alone cannot
supply those metadata. Obtain correlated sanitized Runpod dashboard evidence
or deployment logs if available; do not claim metadata was captured otherwise.

Submission requirements must be checked against the actual event brief.
The deployment guide records a requirement for team-account/endpoint evidence
for RunPod Serverless. A shared public inference endpoint alone does not prove
a team-owned Serverless deployment. Account usage/billing, current submission
eligibility and the hosted security scan have not been verified here.

No source behavior changed; no local mocked tests or historical RP1 results
are presented as hosted provider proof. Final verification completion awaits evidence; preserving these notes in Git does not complete RP2.
