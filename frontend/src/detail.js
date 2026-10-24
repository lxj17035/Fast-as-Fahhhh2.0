import { preparationIssues } from './experience.js';
import { sameId, editable, decimalValid, businessDate } from './model.js';
import { stageFor, submissionCurrent } from './inbox.js';
export function pendingCustomerMessages(quote, detail) {
  const reviewed = new Set((quote?.reviewedMessageIds || []).map(String));
  return (detail?.messages || []).filter(m => !reviewed.has(String(m.update_id)));
}
export function detailStage(context) {
  const {quote,detail,assignments=[]} = context;
  if (!quote) return 'need-info';
  return stageFor(detail,quote,detail,assignments,context.today);
}
export function canSavePrices(form) {
  return !!form?.items.length && form.items.every(i => decimalValid(i.unitPrice,true));
}
export function submissionIssues(context) {
  const {quote, detail, form, dirty, hold, assignments = []} = context;
  if (!quote || !editable(quote) || hold || detail?.delivery_attempts?.some(a => sameId(a.quotation_id, quote.id) && (a.pdf_status === 'sent' || ['pending','unknown'].includes(a.status)))) return ['Quotation is protected.'];
  const issues = preparationIssues(form, context.today || businessDate(), 'sales').map(i => i.message);
  if (dirty) issues.push('Save your draft first.');
  if (pendingCustomerMessages(quote,detail).length) issues.push('Check and confirm the latest customer requirements.');
  if (assignments.some(a => String(a.chat_id) === String(detail?.telegram_chat_id))) issues.push('Sort the unassigned messages first.');
  if (form?.items.some(i => !i.unit.trim())) issues.push('Enter a unit for each item.');
  if (quote.expiryDate < (context.today || businessDate())) issues.push('Update the expired quotation date.');
  return issues;
}
export function initialDetailTab(quote, detail) { return pendingCustomerMessages(quote,detail).length ? 'messages' : 'quote'; }
export function detailNext(context) {
  const {quote,form,role,dirty,hold,busy,detail} = context;
  const stage = detailStage(context);
  if (busy) return {stage,title:'Working on your quote…',body:'Please wait.',buttons:[]};
  if (hold || ['sending','send_uncertain'].includes(quote?.status) || detail?.delivery_attempts?.some(a=>sameId(a.quotation_id,quote?.id)&&['unknown','pending'].includes(a.status))) return {stage:'attention',title:'Check the Telegram conversation',body:'Delivery is unconfirmed. Check the original chat before any further action.',buttons:[['Refresh status','refresh',false]]};
  if (!quote) return {stage,title:'Prepare a draft',body:'Start from the customer message. AI leaves prices for the Manager.',buttons:[['Prepare draft','draft-ai',true],['Write it myself','draft-manual',false]]};
  if (quote.status === 'sent') return {stage:'sent',title:'Sent to the customer',body:'The sent quotation is protected. Use a revision for changes to this order, or link an additional quotation for a separate request.',buttons:[['Create revision','detail-revision',false],['Create additional quote','detail-additional',false]]};
  if (!editable(quote)) return {stage:'attention',title:'This quote is protected',body:'Refresh to check delivery before continuing.',buttons:[['Refresh status','refresh',false]]};
  if (role === 'sales') {
    const issues = submissionIssues(context);
    if (submissionCurrent(quote,detail) && !dirty) return {stage,title:'Submitted for Manager review',body:'The saved details are in Manager To do. Editing them requires another submission.',buttons:[['Preview draft','detail-preview',false]]};
    return {stage,title:dirty?'Save your draft':issues.length?'Check the details before submitting':'Submit the saved details for review',body:issues[0] || 'Prices and PDF preview are optional for Staff submission.',buttons:[['Save draft','detail-save',false],['Submit for review','submit-review',true,issues.length > 0]]};
  }
  if (dirty && role==='pm' && stage==='need-price') return {stage,title:'Add prices',body:'Enter a price for every item, then save and preview. Zero is allowed.',buttons:[['Save prices','detail-save-prices',true,!canSavePrices(form)]]};
  if (dirty) return {stage,title:'Save changes and preview again',body:'Your changes are not saved yet. Existing Manager prices are retained.',buttons:[['Save draft','detail-save',false],['View preview','detail-preview',true]]};
  if (stage === 'attention') return {stage,title:'Check the delivery result',body:'Review the previous attempt and the original chat. Retry only a confirmed failure after fresh Manager approval.',buttons:[['View delivery','detail-activity',false],...(role==='pm'?[['Review retry','approve',true]]:[])]};
  if (stage === 'need-price') return {stage,title:role==='pm'?'Add prices':'Waiting for the Manager to add prices',body:role==='pm'?'Enter a price for every item. Zero is allowed.':'You can still review or update the details. Only a Manager can enter prices.',buttons:role==='pm'?[['Save prices','detail-save-prices',true,!canSavePrices(form)]]:[]};
  if (stage === 'ready') return {stage,title:role==='pm'?'Check the quote, then send':'Waiting for Manager approval',body:role==='pm'?'Review the saved PDF and summary before approving. Any edit requires saving and previewing again.':'The Manager checks the saved PDF and approves delivery.',buttons:role==='pm'?[['View preview','detail-preview',false],['Review & send','approve',true]]:[]};
  const pending = pendingCustomerMessages(quote,detail).length;
  const count = form?.missingInformation?.length || 0;
  return {stage,title:'Check the details, then preview the quote',body:pending?'The customer sent a new message. Check its requirements against this draft.':count?`${count} ${count===1?'point is':'points are'} still to check in the Quote tab.`:'Review the customer and item details, then preview the draft.',buttons:[['Save draft','detail-save',false],['View preview','detail-preview',true]]};
}
export const EVENT_LABELS = {
 quotation_submitted:'Submitted for Manager review',telegram_received:'Telegram enquiry received',enquiry_created:'Added to the inbox',quotation_draft_created:'Quotation draft created',quotation_updated:'Quotation changes saved',pm_approved:'Manager approved delivery',pdf_send_attempted:'PDF delivery started',pdf_send_succeeded:'Telegram accepted the PDF',pdf_send_failed:'Telegram rejected delivery',delivery_unknown:'Delivery requires verification',message_assigned:'Message assigned to this enquiry',staff_message_requested:'Customer reply prepared for delivery',staff_message_sent:'Reply sent to the customer',staff_message_failed:'Customer reply was rejected',staff_message_unknown:'Customer reply delivery needs checking',quotation_revision_created:'Revision created',quotation_additional_created:'Additional quotation linked',quotation_pdf:'Quotation PDF',quotation_summary:'Quotation summary',ai_changes_applied:'Selected AI changes applied',ai_analysis_completed:'AI analysis updated'
};
export function eventLabel(action) { return EVENT_LABELS[action] || 'Quotation activity recorded'; }
