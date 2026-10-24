export const VALIDITIES = { '7d': '7 days', '14d': '14 days', '1m': '1 month', '2m': '2 months', '3m': '3 months' };
export const STATUS = {
  needs_review: ['To review', 'amber'], draft: ['Draft', 'amber'],
  sent: ['Sent', 'green'], failed: ['Not sent', 'red'], send_failed: ['Not sent', 'red'],
  unknown: ['Check Telegram', 'amber'], send_uncertain: ['Check Telegram', 'amber'], sending: ['Sending', 'blue'], pending: ['Sending', 'blue'],
};
export function matchesInboxFilter(item, filter) {
  if (filter === 'all') return true;
  if (filter === 'attention') return ['failed', 'unknown'].includes(item.status);
  return item.status === filter;
}
export function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}
export const sameId = (a, b) => String(a).replaceAll('-', '').toLowerCase() === String(b).replaceAll('-', '').toLowerCase();
export const editable = quote => quote && ['draft', 'send_failed'].includes(quote.status);
export function deliveryHoldResolved(baseline, attempts) {
  // Old failures cannot resolve a newer request whose response was lost.
  return attempts.some(attempt => !baseline.includes(attempt.attempt_id) && ['failed', 'sent'].includes(attempt.status));
}
export function businessDate(now = new Date()) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kuala_Lumpur', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
}
export function quotePatch(form, version) {
  return {
    version, client: { name: form.client.name.trim(), address: form.client.address.trim() },
    issueDate: form.issueDate, validity: form.validity, notes: form.notes,
    items: form.items.map(item => ({ description: item.description.trim(), quantity: item.quantity === '' ? null : item.quantity, unitPrice: item.unitPrice === '' ? null : item.unitPrice })),
    missingInformation: [...form.missingInformation],
  };
}
export function editorForm(quote) {
  return {
    client: { name: quote.client.name, address: quote.client.address }, issueDate: quote.issueDate,
    validity: quote.validity, notes: quote.notes || '', missingInformation: [...quote.missingInformation],
    items: quote.items.map(item => ({ description: item.description, quantity: item.quantity ?? '', unitPrice: item.unitPrice ?? '' })),
  };
}
export function decimalValid(value, price = false) {
  if (value === '' || value == null) return false;
  const pattern = price ? /^\d+(\.\d{1,2})?$/ : /^\d+(\.\d{1,3})?$/;
  return pattern.test(String(value)) && Number(value) <= (price ? 1e9 : 1e6) && (price || Number(value) > 0);
}
export function sendBlockers({ quote, detail, role, dirty, previewVersion, busy, hold, today = businessDate() }) {
  const reasons = [];
  if (role !== 'pm') reasons.push('Switch to PM to approve delivery.');
  if (!quote || !editable(quote)) reasons.push('This quotation is locked.');
  if (busy) reasons.push('An operation is in progress.');
  if (dirty) reasons.push('Save your changes before previewing and sending.');
  if (quote && previewVersion !== quote.version) reasons.push('Open the current saved PDF preview.');
  if (hold) reasons.push('A previous request is unconfirmed. Check the original chat and refresh delivery history.');
  if (!detail || detail.source !== 'telegram' || !detail.telegram_chat_id) reasons.push('The original Telegram recipient is unavailable.');
  if (quote) {
    if (!quote.client.name.trim()) reasons.push('Enter a client name.');
    if (!quote.items.length) reasons.push('Add at least one quotation item.');
    if (quote.items.some(item => !item.description.trim() || !decimalValid(item.quantity) || !decimalValid(item.unitPrice, true))) reasons.push('Complete item descriptions, quantities, and prices.');
    if (quote.missingInformation.length) reasons.push('Resolve or dismiss the missing information.');
    if (quote.issueDate > today) reasons.push('The issue date is in the future.');
    if (quote.expiryDate < today) reasons.push('The quotation has expired.');
    const attempts = (detail?.delivery_attempts || []).filter(attempt => sameId(attempt.quotation_id, quote.id));
    if (attempts.some(attempt => attempt.status !== 'failed')) reasons.push('Delivery is pending, sent, or uncertain. Resending is blocked.');
    else if (attempts.length && !attempts.some(attempt => attempt.can_retry)) reasons.push('No failed attempt is available for a new approval.');
  }
  return [...new Set(reasons)];
}

export function analysisCurrent(analysis, quote, detail, conversation = [], assignments = []) {
  if (!analysis || analysis.stale || analysis.status !== 'completed' || !detail) return false;
  const signature = analysis.signature;
  return !!signature && sameId(signature.quotationId, quote?.id) && signature.baseVersion === quote?.version &&
    analysis.business_profile_id === detail.business_profile_id &&
    JSON.stringify(signature.sourceMessageIds) === JSON.stringify(detail.messages.map(m => m.update_id)) &&
    JSON.stringify(signature.unassignedMessageIds || []) === JSON.stringify(assignments.filter(m => m.chat_id === detail.telegram_chat_id).map(m => m.update_id)) &&
    JSON.stringify((signature.conversation?.outgoing || []).map(m => [m.text, m.provider_message_id])) ===
      JSON.stringify(conversation.filter(m => m.direction === 'outgoing' && !m.kind && m.status === 'sent').map(m => [m.text, m.provider_message_id]));
}
