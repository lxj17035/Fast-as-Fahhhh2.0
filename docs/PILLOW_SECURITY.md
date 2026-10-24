# Replit Pillow finding — release follow-up

24 October 2026, Asia/Kuala_Lumpur.

The supplied Replit screenshot reports Pillow 9.5.0 and several critical/high
findings. For [GHSA-332p-7hrc-92wf](https://github.com/advisories/GHSA-332p-7hrc-92wf),
the GitHub reviewed advisory lists Pillow versions before 13.0.0 as affected and
13.0.0 as patched. Its trigger is saving TIFF data to an in-memory destination.
No exploit was run. The current quotation renderer uses text/tables, with no
application TIFF upload/re-encoding flow found in `app/` or `backend/`; that does
not establish that every scanned dependency is safe.

Local `.venv` already contains Pillow **13.0.0** and ReportLab **4.4.9**. ReportLab
only requires `pillow>=9.0.0`, so its dependency alone permits the reported old
version. Both `pyproject.toml` and `requirements.txt` now explicitly require
`pillow>=13.0.0,<14`. Replit's deployment build uses `pip install --upgrade --target
.pythonlibs -r requirements.txt` so existing target files are replaced, rather
than leaving an older target copy in place. README and deployment guide agree.

Local checks:

- `.venv/Scripts/python.exe -m pytest -q tests/test_pdf.py tests/test_live_readiness.py --basetemp=.input/v2-pillow-final -p no:cacheprovider`:
  **10 passed**, one existing Starlette warning.
- `uv --cache-dir .input/uv-phase4-check pip check --python .venv/Scripts/python.exe`:
  **32 installed packages compatible**. `python -m pip check` was unavailable
  because pip is absent in this uv-created virtualenv; the first uv check used
  an inaccessible default cache, then succeeded with the workspace cache.
- Parsed `.replit` as TOML and checked its upgrade/target command; exact runtime
  dependency lists match. Local import metadata confirms Pillow 13.0.0.
- No PDF template, customer data, secrets or Replit runtime were changed.

## Before republishing

1. Sync the tested GitHub main into Replit while preserving its local changes and
   private Secrets. Do not reset or overwrite unrelated Replit files.
2. Rebuild dependencies with the committed deployment build. For a development
   Shell check, the equivalent install is:

   ```bash
   PIP_USER=false python -m pip install --upgrade --target .pythonlibs -r requirements.txt
   PYTHONPATH=.pythonlibs python -c "import PIL; print(PIL.__version__); print(PIL.__file__)"
   ```

3. Confirm the application interpreter resolves Pillow 13.x from the intended
   target, then restart/republish with the updated build. Local imports do not
   prove the hosted interpreter or deployment dependency inventory.
4. Rerun Replit Security. If it still finds 9.5.0, identify the flagged installed
   path/environment: an older base/system copy may remain even when the app uses
   the new target. Resolve that environment with Replit; do not blindly delete
   system packages. Review the remaining findings individually.
5. Run hosted V2/RP2 checks after the new build is actually published.

**Pending:** hosted Pillow version, clean rebuild, scan result, other reported
findings, hosted V2 and RP2. No claim that the screenshot's entire finding list is
fixed, that Replit has been updated, or that the deployment is secure is made.
