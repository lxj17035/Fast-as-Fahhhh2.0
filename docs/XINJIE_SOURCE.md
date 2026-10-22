# Reused Xinjie service source

Source: `origin/feat/xinjie`, commit
`2b1d36d974a4f14f5fa2563bb2b39d3cdce3f103` in this repository.

The following modules are copied unchanged from that commit:

- `backend/__init__.py`
- `backend/errors.py`
- `backend/settings.py`
- `backend/quotations.py`
- `backend/drafting.py`
- `backend/pdf.py`

These remain Xinjie's business logic. Integration adds `app/xinjie_store.py`,
`app/xinjie_adapter.py` and thin FastAPI routes, rather than rewriting their rules.
Xinjie's SQLite `Store`, standalone HTTP server and competing enquiry/send-stub
routes are not imported. The existing application and PostgreSQL database remain
the shared runtime. No Git merge or teammate-branch changes are performed.

The bridge projects existing relational enquiries into the service interface;
fictional `demo-client` is an explicit seeded association. Business settings,
client snapshots, saved quotations, cached PDFs and the service's draft-created
event use `xinjie_records` in the same database. This draft event does not complete
Part 4's general activity history.

Xinjie's source uses ReportLab 4.4.9, retained in project dependencies. PDF
rendering and AI extraction behavior remain theirs. External extraction is disabled
in the integration wrapper unless an extractor is explicitly injected.

When updating these copied modules, review the source commit and rerun the real
integration suite, especially transaction rollback, edit/send concurrency, saved
PDF equality and quotation-ID normalization.
