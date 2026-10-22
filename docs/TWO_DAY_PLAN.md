# Two-day build plan

## Goal and schedule

Deliver one working quotation journey with connected data, PM approval, and an activity log. Assume three contributors and two focused working days. Use relative Day 1/Day 2 blocks because the actual remaining deadline and progress have not been confirmed; this update does not reset the event deadline.

The brief permits a rough prototype and simulated platform foundations. Prioritize the core feature and explain how the proposal covers every required feature. Email, visual polish, and production infrastructure are secondary.

## Responsibilities

| Person | Owns | Handoff |
| --- | --- | --- |
| Xinjie | Business/client settings, AI extraction, quotation data, prices/totals/validity, backend PDF generation | Saved quotation and PDF endpoint |
| Sweeway | Telegram receive/send, enquiry source tracking, send result, activity-log persistence | Normalized enquiry and PDF delivery |
| YieXian | Inbox/editor/settings UI, PDF preview, simulated role controls, activity-log display | PM review and approval flow |

All three agree data shapes at kickoff, integrate before Day 1 ends, and share demo/pitch preparation. PM-only send must be checked in the backend's simulated-role logic as well as shown in the UI.

## First 30 minutes

- Use the selected stack: Python/FastAPI with SQLAlchemy/Psycopg, one shared PostgreSQL DATABASE_URL (also on Replit), and one PDF layout.
- Agree the small contract in IMPLEMENTATION.md and one fictional enquiry/client/company dataset.
- Obtain the bot token and AI key. Prove message receipt, a bot response, and basic PDF generation early.
- Create the GitHub repository and local setup instructions. Ensure judges can access the repo at submission; never commit credentials.
- Confirm the round, deadline, proposal format, and length limits from event instructions. The supplied PDF gives preliminary weights but not exact submission length limits.

## Day 1: complete the path

| Block | Xinjie | Sweeway | YieXian | Checkpoint |
| --- | --- | --- | --- | --- |
| First half | Seed business/client context; settings; AI draft; totals and dates; basic PDF | Receive/persist Telegram enquiry and source; prove reply | Inbox, quotation editor, and connected-context display with sample data | Telegram enquiry visible with editable draft |
| Second half | Connect draft/save/PDF to UI; validate required fields | Send generated PDF to original chat; record actor/action/result | Preview, simulated Sales/PM controls, approve/send, activity log | One complete enquiry-to-PDF run |

Day 1 exit: demonstrate the entire path, even with rough styling. Do not defer integration until the end of Day 2.

## Day 2: verify and prepare evidence

| Block | Team focus | Result |
| --- | --- | --- |
| First half | Fix integration; check totals, validity, missing prices, PM-only sending, duplicate inputs/clicks, and visible send failure | Stable core journey |
| Third quarter | Time manual vs assisted preparation; run a novice-user walkthrough; prepare Orbyte/reuse/SDG explanation | Evidence and concise pitch |
| Final quarter | Freeze features; verify repository access and setup; rehearse twice; fix blockers | Repeatable live demo and submission |

If only one day remains, reserve the first half for the working journey and the second half for validation/pitch. Drop email and polish immediately; retain human approval, activity log, and the explicit Orbyte explanation.

## Risk and fallback

Hardest risk: integrating Telegram, AI, and PDF rendering from scratch in the available time.

- If Telegram setup blocks progress, use a clearly labelled simulated inbound enquiry and a recorded outbound result so the working draft/review/PDF feature can still be shown. Disclose that live Telegram delivery is incomplete; this is a reduced preliminary demo, not completion of our chosen live journey.
- If AI fails, permit manual drafting to exercise review/send. Clearly state that AI drafting is incomplete; do not present a fixture as live AI.
- If email setup takes time, omit it. The Needs review inbox remains the PM alert.
- Do not wait for live Orbyte access: the brief expects synthetic data and team-defined interfaces.
- Simulate identity/roles in a supervised local demo; do not expose that setup as a production service.

## Demo and pitch

1. State the problem: staff copy enquiries into quotations and can lose track of pending replies.
2. Send a fictional Telegram enquiry: “Example Print Customer needs 20 printed T-shirts. Address: 12 Demo Road.”
3. Show the message joined with fictional company/client data and quotation settings; AI drafts the item and leaves price blank.
4. Show Sales can edit but cannot send. Switch to the labelled PM role; review details, enter 25.00 per item, and verify total 500.00 in the configured currency.
5. Select issue date and validity; preview the PDF, approve, and send to the original test chat.
6. Show the visible outcome and activity log identifying the approving PM.
7. Present actual timing/error observations, Orbyte module assumptions, reuse for other SMEs, and SDG 8 contribution. Label unmeasured targets as targets.
8. Provide the judge-accessible GitHub link and disclose any simulated integrations or unfinished parts.

## Pitch effort by preliminary rubric

- 30% innovation: explain the specific workflow capability and why context plus controlled document delivery adds value beyond chat.
- 25% fit: explain the recurring pain, ease of learning, human control, and Orbyte reuse.
- 25% feasibility: show working code, data assumptions, core feature, and the integration fallback.
- 20% clarity: use problem -> approach -> measured/expected outcome; stay within confirmed submission limits.

Source: supplied Domain 2 PDF, physical pages 4-9. Role assignments, time blocks, and fallback choices are our plan.
