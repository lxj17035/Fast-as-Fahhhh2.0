# Shared service provenance after merge

Sweeway originally imported Xinjie business modules from commit `2b1d36d`.
The branches are now merged; source files are maintained together rather than
promised to match that historical snapshot byte for byte.

The integrated FastAPI runtime uses one PostgreSQL database and Xinjie's existing
`quotation_records` storage for settings, clients, quotes and cached PDFs.
`app/xinjie_store.py` reuses `backend.store.Store`, joins externally supplied
transactions and writes draft events to Sweeway's canonical `activities` table.
All mutation paths share the same PostgreSQL advisory lock; SQLite is test-only.

Unknown senders retain Xinjie's separate empty client records. Automatic drafting
and explicit retry use the same service. The public send handler is Sweeway's
`app/delivery.py`, with `X-Demo-Actor: pm` and `expected_version`; it permits only
one attempt per quotation. The older standalone handler and SendService remain
isolated compatibility/test helpers and are not registered public send routes.

Do not edit copied modules independently or restore a second runtime store.
See MERGE_REVIEW.md and PM_APPROVAL.md for current evidence and frontend contract.
