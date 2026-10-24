# Inbox short-title prompt

Implemented in local source on 24 October 2026 after owner approval. The shared
AI schema requests shortTitle alongside extraction; validation normalizes it to
six English words / 15 Chinese characters and saves it in quotation JSON.
Legacy responses without the field remain compatible. No schema migration,
historical-record backfill, live inference or Replit publication was performed.
Restart/redeploy the backend to use the new prompt; the running local preview
uses mocked providers. Existing rows display a compact saved-item fallback.

## Prompt

Append this instruction to the existing extraction prompt when implementing
short titles:

```text
Generate a short enquiry title for the inbox from the customer's stated request.

- Use the customer's language.
- Include the main product or service and quantity, when explicitly stated.
- Use at most 6 words for English or 15 characters for Chinese.
- Exclude customer names, addresses, deadlines and introductory phrases.
- Do not invent missing information, quantities, products or specifications.
- If the message contains no clear product or service, use a neutral short title
  in the customer's language, such as "Enquiry" or "客户询问".
- Do not include prices, approval instructions or recipient information.
- Return the title as the string field "shortTitle" in the existing extraction
  JSON object. Continue returning all other required extraction fields.
- Return JSON only, without markdown or explanations.

Examples of title values:
"20 black T-shirts"
"500 business cards"
"20件黑色T恤"
"办公室清洁"
```

## Implementation notes for later

- Generate the title alongside the existing extraction, not with an extra call
  on every inbox load. Preserve the full summary for the detail page.
- Update the shared extraction schema, server-side validation and persistence
  before enabling this prompt. A prompt alone cannot add a supported field.
- Make the inbox prefer the saved shortTitle with a safe fallback for old rows.
- Update mocked providers and relevant tests; do not call live providers merely
  to improve preview labels.
- Existing records require a separate, explicitly chosen backfill approach;
  this document does not regenerate their titles or spend inference credit.
