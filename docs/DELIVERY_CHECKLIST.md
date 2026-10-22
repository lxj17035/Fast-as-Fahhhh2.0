# Remaining backend delivery work

Completed items are removed from this active list and recorded below.

- [ ] PM approval sends the saved PDF back to the original Telegram chat.
- [ ] Approval and delivery outcomes appear in a persisted activity log.
- [ ] Member 2 configures private credentials and a team-controlled test chat; verify the real end-to-end journey.

## Completion evidence

### Automatic drafting on receipt

- Incoming authenticated text updates persist first, then trigger a background draft without a second HTTP request.
- Duplicate updates can retry interrupted drafting and return existing quotations without overwriting PM edits.
- Expected AI failure creates a labelled manual-review draft. Unexpected background failure preserves the enquiry for retry.
- `pytest tests/test_automatic_drafting.py tests/test_shared_quotation_api.py tests/test_telegram_webhook.py -q`: **38 passed** using isolated test storage and mocked AI.
- This in-process background task is for the demo. An interrupted process leaves the enquiry in the inbox; retry via the draft endpoint or a repeated webhook. No durable worker/queue is claimed.

### Merge

- No MERGE_HEAD or unmerged entries exist in this checkout.
- The earlier merge is already committed as `8aa59b9` (Merge branch main into feat/xinjie); no extra merge commit is necessary.

## Live configuration

Readiness check reports DATABASE_URL present; TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, OPENAI_API_KEY, and OPENAI_MODEL missing. Presence is not a successful connection test. Member 2 owns filling these privately in .env and identifying the controlled test chat. Never paste credentials into chat or fixtures.
