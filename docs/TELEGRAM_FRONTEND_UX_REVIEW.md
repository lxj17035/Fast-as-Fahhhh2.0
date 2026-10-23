# Telegram and frontend usability review — proposals for discussion

Recorded: 24 October 2026 (Asia/Kuala_Lumpur).

Status: user feedback and proposed changes only. This file does not implement,
approve, or claim completion of a new workflow. Discuss the decisions below
before changing shared contracts or code. The original scope remains documented
in [WORKFLOW.md](WORKFLOW.md); deployment history is in
[REPLIT_DEPLOYMENT_GUIDE.md](REPLIT_DEPLOYMENT_GUIDE.md).

## User experience observed during the live walkthrough

The user needed repeated guidance to save, preview and approve. Disabled buttons
did not make the next action obvious. This is direct usability feedback, not
evidence that the intended ease-of-use goal has been achieved. No measured
productivity improvement or novice-user success is claimed.

| Observation | User impact |
| --- | --- |
| `/start` appears as a To review enquiry | A bot command becomes unnecessary quotation work |
| Each incoming text creates its own enquiry/draft | Sizes, colour and dates get separated from the original request |
| Missing-information warnings remain after fields are filled | Staff must manually dismiss apparently outdated warnings |
| AI asks for phone/email or optional address | Staff think optional information is mandatory |
| Multiple preview/save/check actions block approval | Staff do not understand why they cannot continue |
| Sales and PM use essentially the same editor | Responsibilities and next steps are unclear |
| No staff text-reply composer | Sales cannot ask the customer for missing information through this system |
| No dedicated fulfilment/date fields | Colour, sizes, delivery date and collection arrangements become unstructured notes |
| No close/archive action | Commands, abandoned requests and test messages remain in active work |
| Potential for repeated revised PDFs | Customers may not know which version to use |

Current implementation intentionally treats each received text as a separate
enquiry. These session/grouping improvements therefore need backend and contract
changes, not only redesigned buttons. Existing sent PDF snapshots must remain
unchanged.

## Proposed simplest workflow

```text
Customer messages → one enquiry conversation → Sales prepares details
→ PM prices/reviews the saved PDF → explicit approval → PDF to original chat
```

### Sales and PM responsibilities

| Role | Main view | Allowed work |
| --- | --- | --- |
| Sales | Enquiries / conversations | Read/reply, collect requirements, edit draft details, save incomplete work, submit for PM review |
| PM | Pending review, Needs attention, Sent | Review requirements, enter/finalize prices, inspect PDF, return for changes, explicitly approve/send |

Both roles can review information and close an enquiry. PM retains final pricing
and send authority; AI cannot choose prices, recipients or approval. These remain
simulated demo roles; separate pages do not create trusted authentication.

“Submit for PM review” and “Return for changes” are proposed persisted operations,
not existing API features. New customer information must flag the review as
outdated before approval. Needs attention should distinguish missing information,
confirmed delivery failure and unknown delivery, rather than inviting a blind retry.

### Saving and missing information

- Save draft should allow incomplete work.
- On save, validate known structured fields server-side: name, item description,
  quantity, and any entered price. Resolve matching field warnings automatically.
- Put remaining issues beside the relevant fields and show one short summary,
  such as “Saved. Add a product description before submitting.” Avoid repeated
  popups or a long checklist that staff must dismiss item by item.
- Block submit/approval only for clearly defined required information. Explain
  each blocker with a direct link to the field or next action.
- Use ordinary validation for ordinary fields; do not pay for an AI request on
  every save. AI can suggest whether narrative requirements were addressed, but
  cannot verify an unstated fact or treat a save as customer confirmation.
- For genuine business ambiguity, offer an explicit disposition: ask the
  customer, retain a visible qualification, or record that the detail is not
  required. Do not silently dismiss all warnings.
- Keep internal review questions separate from customer-facing PDF notes.

### PM review without a separate Preview button

When PM opens a submitted quotation, automatically load/render the current saved
PDF alongside the requirements and total. Show Return for changes and Approve &
send as the main actions. Preserve one explicit final confirmation.

Automatic display does not remove the saved-version requirement. Unsaved changes,
new customer requirements, a changed version or PDF load/render failure must
prevent approval with a clear explanation. After edits, save and refresh the PDF
before approval becomes available. Reuse the backend's version and send guards.

## Telegram conversations and customer follow-up

### Commands and enquiry routing

| Incoming content | Proposed behavior |
| --- | --- |
| `/start` or `/help` | Welcome/help; no new quotation and no reset of an active enquiry |
| Greeting or thanks | Conversation message; no automatic standalone quotation |
| A clear new quotation request with no active enquiry | Create an enquiry and draft from the stated facts |
| Additional information for the single active enquiry | Append to that conversation and flag possible draft changes |
| Another distinct order / multiple plausible enquiries | Ask staff/customer to choose; do not guess an association |
| Explicit New enquiry button or `/new` | Begin a separate enquiry after handling any ambiguity |

Do not depend entirely on keyword filtering: greetings can contain a real order,
and “10 M, 10 L” can be important follow-up. Keep raw receipts, deduplicate updates
and preserve source IDs. Routing decisions and any draft suggestions must not
overwrite PM edits or prices. Start with private team test chats; group-chat
attribution requires a separate decision before grouping messages by chat alone.

### Staff replies

Add a text composer inside the enquiry: Sales writes a clarification and explicitly
clicks Send to customer. The reply goes to the stored original Telegram chat;
show outgoing and incoming messages in one timeline with delivery state.

AI may prepare an editable suggested question. Staff decides whether to send it.
This is a separate operation from sending a PDF: Sales can send clarification
text, but cannot thereby gain quotation approval authority. Persist attempts and
handle uncertain outcomes without automatically resending. Never use AI output
or a browser-supplied recipient to select the destination.

### Product specifications and fulfilment

Proposed editable information, shown consistently in the editor, saved quotation
and PDF where relevant:

| Information | Example / rule |
| --- | --- |
| Customer name | Required quotation addressee; do not invent it |
| Fulfilment method | Delivery / Pickup / Not decided |
| Customer address | Optional by default; do not automatically require it for pickup |
| Delivery destination | Collect when delivery is selected and a destination is needed to price/commit fulfilment |
| Product / printing specification | T-shirt, front print; capture requirements that affect price |
| Colour | Black; pending if unstated |
| Size allocation | M × 10, L × 10; check consistency with item quantity |
| Requested delivery or pickup date | Customer's desired date, distinct from a confirmed commitment |
| Confirmed fulfilment date | Staff-confirmed date, only if actually agreed |

Issue date and quotation validity/expiry are not delivery dates. Validate and
display them separately. Do not interpret ambiguous numeric dates or infer the
year silently. The field shape for reusable non-printing businesses remains to
be agreed; avoid forcing T-shirt-specific fields onto every business.

Phone/email are not mandatory for the Telegram-only journey. The extraction
prompt should not routinely request them. Optional fields should not become
approval blockers merely because AI emitted a missing-information string.

## Closing enquiries

Add Close enquiry with reasons such as Cancelled, No response, Duplicate/test or
Completed. Keep history and allow explicit reopening. Closed enquiries should
leave active lists and remain searchable in a Closed view. Do not delete receipts
or sent PDFs. Do not automatically close a request just because the customer sent
`/start` or did not reply for an arbitrary period.

Sent describes a delivery outcome; Closed describes enquiry lifecycle. Keep those
concepts separate so an enquiry can have a sent PDF and still need follow-up.
Do not allow closing/reopening to unlock a pending or unknown upload or bypass
delivery reconciliation. A subsequent customer message on a closed enquiry
needs an explicit routing/reopen policy rather than silently disappearing.

## Same-day additions and next-day quotations — decision pending

User proposal: after receiving a PDF, the customer can add items to the same
quotation on the same day; a request tomorrow should start a new quotation.

This can be a convenient default, but calendar date alone is not enough. A
customer may revise yesterday's order today, or place two different orders on
the same day. Do not create empty new quotations at midnight or close unresolved
work automatically. Use Asia/Kuala_Lumpur dates if a day boundary is adopted.

Recommended discussion option:

1. Keep the chat conversation/history across days.
2. Before any PDF is sent, relevant follow-ups update the current enquiry as
   suggestions, preserving manual edits and invalidating outdated PM review.
3. After a PDF is sent, same-day additions normally create a **revision draft
   linked to the same quotation reference**. Never edit the already-sent
   version/PDF in place; the current backend locks those records intentionally.
   A revision needs new versioned storage and explicit PM approval.
4. For next-day requests, offer New quotation as the default, with an explicit
   Revise previous quotation choice when the message refers to that order.
   A strict automatic next-day split is still an open product decision.
5. Let staff select New enquiry for a distinct order at any time, even the same day.

An automated routing decision is not permission to send a new PDF. Accumulate
changes into one revision draft and send only after deliberate PM approval.

## Reduce PDF clutter and explain revisions

- Do not generate/send a Telegram document for every customer message or save.
- Consolidate additions before the next PM-approved send.
- Send the approved PDF with a concise caption/summary derived from the same
  saved quotation, rather than a second unrelated automated message where possible.
- Include quotation reference/revision, item summary, total, and relevant agreed
  fulfilment details. Never turn a requested date into a confirmed promise.
- For a revision, say which earlier version it supersedes. Keep the previously
  sent PDF and activity unchanged. Do not assume Telegram can silently replace
  or remove an already-delivered document; verify provider capabilities separately
  if message editing is later proposed.
- Do not claim a PDF was read just because Telegram accepted it.

Illustrative customer caption, not implemented copy:

```text
Quotation Q-EXAMPLE, revision 2
20 black T-shirts: 10 M and 10 L. Total: MYR 500.00.
Requested delivery: 30 Nov 2026; confirmation pending.
This revision replaces revision 1. Please refer to the attached PDF.
```

Caption values must come from the approved snapshot, not unchecked AI-generated
facts. A caption reduces ambiguity; it cannot guarantee only one PDF remains in
the customer's Telegram history.

## Proposed order of work after discussion

1. Correct command handling and message association, including clarification
   replies and preserving manual work. Otherwise redesigned screens still show
   fragmented requests.
2. Add the smallest agreed fulfilment/specification fields and fresh validation.
3. Simplify Sales preparation and PM review, automatic saved PDF display and
   understandable blockers.
4. Add close/reopen lifecycle and filters.
5. Implement the agreed post-send revision policy and approved PDF caption.

Owners follow AGENTS.md: Sweeway owns Telegram receipt/replies/delivery/activity;
Xinjie owns extraction, quotation rules/storage and PDF; YieXian owns role views,
forms and explanations. Shared contracts and migrations must be agreed together.
No production identity, additional channel or queue infrastructure is proposed.

## Acceptance examples for later implementation

These are proposed checks, not completed tests:

- `/start` creates no enquiry or quotation; duplicate receipts still deduplicate.
- Sizes/colour/date follow-ups appear in the intended active enquiry; ambiguous
  messages do not merge unrelated orders.
- Customer follow-up during AI work or PM review does not overwrite staff edits,
  prices or a sent snapshot; stale approval is blocked clearly.
- Sales text replies reach only the original test chat and do not authorize PDF send.
- Filled required fields clear matching warnings; optional address/phone/email
  do not block a pickup quotation.
- Missing price still blocks approval, while Save draft still works.
- Requested and confirmed fulfilment dates are distinct in the saved PDF.
- PM can finish a clean review without searching for a Preview button; an updated
  version or failed PDF render clearly explains why approval is unavailable.
- Closed enquiries leave active lists; reopening never bypasses send-state locks.
- Same-day revisions preserve old sent bytes, require fresh PM approval and name
  the superseded revision. Next-day behavior follows the explicitly agreed policy.
- A novice teammate can complete the revised workflow without chat guidance;
  record actual task time, confusing steps and errors instead of claiming ease
  of use from feature completion alone.

## Decisions to settle before implementation

- Confirm Sales preparation versus PM pricing responsibilities and return flow.
- Choose one-active-enquiry defaults, explicit new-order handling and reopening rules.
- Decide strict next-day splitting versus the suggested new/revision choice.
- Define revision reference/version storage and the meaning of Closed after Sent.
- Define which specifications/fulfilment details are required for this fictional business.
- Confirm the minimum UI and backend changes for the hackathon time available.

Documentation verification: Markdown structure, relative links and diff formatting
are checked when these files are added. No application code, external messages,
provider settings or deployment is changed by this document.
