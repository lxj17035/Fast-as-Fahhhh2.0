import { businessDate, decimalValid, editable, editorForm, sameId, sendBlockers } from './model.js';

// Explain what to do next. The existing send guards and API remain authoritative.
export function preparationIssues(form, today = businessDate(), role = 'pm') {
  if (!form) return [];
  const issues = [];
  if (!form.client.name.trim()) issues.push({ field: 'clientName', message: 'Add the customer’s name.' });
  if (!form.issueDate) issues.push({ field: 'issueDate', message: 'Choose an issue date.' });
  else if (form.issueDate > today) issues.push({ field: 'issueDate', message: 'Use today or an earlier issue date.' });
  if (!form.items.length) issues.push({ field: 'items', message: 'Add an item to the quote.' });
  form.items.forEach((item, i) => {
    if (!item.description.trim()) issues.push({ field: `item-description-${i}`, message: `Describe item ${i + 1}.` });
    if (!decimalValid(item.quantity)) issues.push({ field: `item-quantity-${i}`, message: `Check the quantity for item ${i + 1}.` });
    if (role === 'pm' && !decimalValid(item.unitPrice, true)) issues.push({ field: `item-price-${i}`, message: `Enter a price for item ${i + 1}. Zero is allowed.` });
  });
  if (form.missingInformation.length) issues.push({ field: 'missing-review', message: `Review ${form.missingInformation.length === 1 ? 'the flagged detail' : 'the flagged details'} below.` });
  return issues;
}

export function reviewGuidance(context) {
  const { quote, detail, dirty, previewVersion, pdfReady, hold, role, busy } = context;
  const today = context.today || businessDate();
  const attempts = (detail?.delivery_attempts || []).filter(a => sameId(a.quotation_id, quote?.id));
  if (quote?.status === 'sent' || attempts.some(a => a.status === 'sent')) {
    return { stage: 3, kind: 'complete', title: 'Quote sent to Telegram', body: 'Telegram accepted this quote. Its saved details are now protected.', action: null, issues: [] };
  }
  if (hold || ['sending', 'send_uncertain'].includes(quote?.status) || attempts.some(a => ['pending', 'unknown'].includes(a.status))) {
    return { stage: 3, kind: 'warning', title: 'Check the Telegram conversation', body: 'We can’t confirm delivery yet. Check the original chat, then refresh the status. Sending again is blocked.', action: 'refresh', label: 'Refresh status', issues: [] };
  }
  if (busy) return { stage: 1, kind: 'working', title: 'Working on your quote…', body: 'Please wait before taking the next step.', action: null, issues: [] };
  if (!quote) return { stage: 1, kind: 'review', title: 'Start with a draft', body: 'Use the customer’s message to prepare a quote. You’ll review every detail before sending.', action: 'draft-ai', label: 'Prepare draft', issues: [] };
  const form = context.form || editorForm(quote);
  const issues = preparationIssues(form, today, role);
  if (!dirty && quote.expiryDate < today) issues.push({ field: 'issueDate', message: 'This quote has expired. Update the date and save it again.' });
  if (issues.length) return { stage: 1, kind: 'review', title: 'Check the quote details', body: 'Complete these details before sending. You can save an unfinished draft at any time.', action: 'fix-details', label: 'Review details', issues };
  if (dirty) return { stage: 1, kind: 'review', title: 'Save and check the document', body: 'Your changes are ready to save. Open the updated PDF to check how the quote will look.', action: 'save-preview', label: 'Save & preview', issues: [] };
  if (!editable(quote)) return { stage: 3, kind: 'warning', title: 'This quote is protected', body: 'Refresh the record to check its latest delivery status.', action: 'refresh', label: 'Refresh status', issues: [] };
  if (!pdfReady || previewVersion !== quote.version) return { stage: 2, kind: 'preview', title: 'Preview your quote', body: 'Check the saved PDF your customer will receive, including the items, prices and dates.', action: 'preview', label: role === 'pm' ? 'Preview quote' : 'Preview draft', issues: [] };
  if (role !== 'pm' && form.items.some(item => !decimalValid(item.unitPrice, true))) return { stage: 3, kind: 'review', title: 'Waiting for Manager pricing', body: 'Your details are saved and the draft is previewed. A Manager needs to enter prices and approve sending.', action: null, issues: [] };
  if (role !== 'pm') return { stage: 3, kind: 'review', title: 'Ready for a project manager', body: 'The quote is saved and previewed. A PM needs to review it and approve sending. The role selector is for this supervised demo.', action: null, label: 'PM approval needed', issues: [] };
  const blockers = sendBlockers({ ...context, today });
  if (blockers.length) return { stage: 3, kind: 'warning', title: 'Check before sending', body: 'Refresh the record to check the original conversation and delivery status.', action: 'refresh', label: 'Refresh status', issues: [] };
  const retry = attempts.some(a => a.can_retry);
  return { stage: 3, kind: 'ready', title: retry ? 'Ready to try again' : 'Ready for your approval', body: retry ? 'The last send was rejected. Check the quote and approve a new attempt.' : 'You’ve saved and previewed the quote. Review the recipient and confirm when you’re ready.', action: 'approve', label: retry ? 'Review & send again' : 'Approve & send', issues: [] };
}
