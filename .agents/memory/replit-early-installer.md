---
name: Replit early installer
description: Distinguishing deployment's automatic package phase from the explicit build command.
---

Do not assume `enabledForHosting=false` skips the deployment's early package-install phase, or that a passing custom build verifies that phase.

**Why:** On 2026-10-23, deployment logs showed an automatic `pip install -r requirements.txt` before the configured build despite that flag. It attempted to install the local application package into read-only Nix Python directories, although the explicit target-based build passed locally.

**How to apply:** Test the automatic command separately with its intended environment and a clean writable target. Confirm hosted environment injection from a real build before claiming deployment success. A local test with explicitly supplied environment variables cannot establish what Replit passes to its early installer. Do not start a deployment for this check without the user's authorization.
