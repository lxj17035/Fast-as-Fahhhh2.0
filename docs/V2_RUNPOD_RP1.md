# V2 Runpod RP1 verification

Separate from mocked tests. Not a Replit or Telegram verification.

```json
{
  "checkpoint": "RP1",
  "utc": "2026-10-24T04:30:59.749514+00:00",
  "malaysia": "2026-10-24T12:30:59.749551+08:00",
  "status": "passed",
  "calls": 1,
  "provider": "Runpod",
  "scope": "One fictional Cleaning enquiry, disposable local PostgreSQL, no Telegram or hosted app",
  "http_status": 200,
  "provider_request_id": "chatcmpl-01a16c2d-4845-71d1-81d1-49698103fe34",
  "token_usage": {
    "prompt_tokens": 1180,
    "completion_tokens": 182,
    "total_tokens": 1362
  },
  "endpoint": "https://api.runpod.ai/v2/b1dd8hy2hqo1nb/openai/v1",
  "model": "glm-5.3",
  "configured_max_tokens": 1024,
  "validated_extraction": {
    "summary": "Fictional Demo Office requested 2 cleaning visits for a 120 square metre office. Scope includes desks and floors; windows excluded. No visit dates or address provided; no prices agreed.",
    "clientName": "Fictional Demo Office",
    "clientAddress": null,
    "items": [
      {
        "description": "Cleaning visit",
        "quantity": "2",
        "unitPrice": null,
        "unit": "unit",
        "notes": "120 sqm office; scope includes desks and floors; excludes windows. Visit dates not specified."
      }
    ],
    "missingInformation": [
      "Customer address unknown",
      "Visit dates not specified",
      "No prices agreed",
      "Confirm unit for item 1"
    ],
    "clarificationSuggestions": [
      "Confirm the requested visit dates with the customer",
      "Ask Staff to obtain the customer's address",
      "Confirm whether cleaning supplies are included or provided by client"
    ],
    "assignmentSuggestions": [],
    "proposedChanges": [],
    "relationshipIntent": "none"
  },
  "metadata_note": "Null fields mean unavailable, not captured evidence. No billing/account balance evidence retrieved."
}
```
