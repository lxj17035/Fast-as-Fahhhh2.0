# Future improvements

## Browse previous quotations and revisions

Requested during the detail-page design discussion, 24 October 2026.

Current behavior: the backend preserves sent quotation records and exact PDF
snapshots when a revision is created. The detail page opens the latest quotation;
it does not yet provide a quotation-history selector or a link back to the
original quotation. Activity/delivery history is not a previous-version browser.

Proposed improvement:

- Show the original quotation and linked revisions/additional quotations in a
  history list, using saved quotation numbers, dates and relationship labels.
- Allow Staff and Manager to open previous quotations and their saved PDFs in
  read-only mode, then return to the current draft.
- Clearly label historical documents so users can distinguish them from the
  current draft; do not silently replace the selected version with the latest.
- Viewing a previous version must not restore, edit or resend it. Changes use
  the existing explicit revision and Manager approval process.
- Reuse the existing enquiry quotation-history API and saved PDF/version
  contracts. Do not regenerate historical PDFs from current settings.

Status: future work only; not implemented by this documentation change.
