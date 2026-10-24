# V2 frontend progress

Branch: `codex/feat-domain2-v2`. Synthetic local QA only; no push/deployment.

## F1 — Business Profile Settings (24 October 2026)

Changed: `frontend/src/api.js`, `frontend/src/app.js`,
`frontend/src/styles.css`, `frontend/tests/api.test.mjs`,
`frontend/tests/integration.mjs`, `docs/FRONTEND.md`, `DESIGN.md`,
`premium-ui.json`, README.md, docs/WORKFLOW.md, docs/BUSINESS_PROFILES.md,
docs/V2_PHASE_HANDOFF.md, and canonical-plan progress.

Explicit Printing/Cleaning/Repair selection, named-profile settings writes,
shared-scope explanation, safe state reset, unsaved cancellation/discard and
visible business context. Existing form/feedback patterns retained. Shared
textareas auto-grow, validation remains server owned, scrollbars have a global
baseline. No backend business logic or PDF template changed.

Verification:
- `node --test frontend/tests/*.test.mjs`: **25 passed**.
- `node frontend/tests/integration.mjs`: **8 passed**, actual API, temporary
  SQLite adapter and mocked AI/Telegram. Switch isolation, invalid selection,
  named settings persistence and original saved PDF bytes verified.
- Local Edge/Playwright browser: switch Printing/Cleaning/Repair, save, preserve
  edits after cancel, discard before switching, restore named settings. Screenshots
  reviewed at 1365x900 and 390x844; no horizontal overflow or page errors.
  Injected rejected save/switch responses also preserve entered values and active
  scope; field errors have accessible descriptions. Dialogs restore prior focus.
  In-app browser failed with `Tab 1 is not part of browser session`; used the
  existing runtime Playwright and installed Edge. No dependency changes.
- `node --check frontend/src/app.js` and `git diff --check`: passed.
- Strict skill audit ran; 3 actionless-button findings are false positives on
  existing delegated `data-action` filter/checklist/remove buttons. Their actual
  handlers are in app.js. No unresolved ownership or other findings. Evidence
  under ignored `.input/v2-f1-audit.json`.
- DESIGN.md lint attempted offline; package unavailable in npm cache. No package
  installed solely for lint. Runtime token mapping manually checked.

Limitations: no PostgreSQL rerun (frontend-only change), live provider call,
Telegram send, hosted verification, full accessibility certification or cross-tab
sync claim. Global selection remains shared; a different browser can change it.
The server still enforces record scope, and named-profile settings saves remain
pinned. F2–F5 and T1–T3 remain separate sections.

Commit checkpoint: **blocked**. `git add` and `git commit` failed because the
session permits read-only `.git` access: `Unable to create .../.git/index.lock:
Permission denied`. No commit hash, push or checkout change. F2–F5 were not edited;
continue with the F1 commit in a Git-writable session before F2, following AGENTS.md.
