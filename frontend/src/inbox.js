import { escapeHTML as e, editorForm, decimalValid, businessDate } from './model.js';
import { preparationIssues } from './experience.js';
export const UNDO_SECONDS = 10;
export const STAGES = { sort: 'Needs sorting', 'need-info': 'Needs info', 'need-price': 'Needs price', ready: 'Ready to send', sent: 'Sent', attention: 'Needs checking' };
export const SOURCES = { telegram: 'Telegram', whatsapp: 'WhatsApp', instagram: 'Instagram (ad)', facebook: 'Facebook (ad)' };
export const owner = stage => ['need-price', 'ready', 'attention'].includes(stage) ? 'pm' : ['sort', 'need-info'].includes(stage) ? 'sales' : '';
export function submissionCurrent(quote, detail) {
  const submission = quote?.reviewSubmission;
  return !!submission && submission.version === quote.version && !submission.invalidatedBy &&
    JSON.stringify(submission.sourceMessageIds) === JSON.stringify((detail?.messages || []).map(m => String(m.update_id)));
}
export function managerHandoff(quote, detail) {
  const submission = quote?.reviewSubmission;
  return submissionCurrent(quote, detail) || !!submission && submission.invalidatedBy === 'pm' &&
    JSON.stringify(submission.sourceMessageIds) === JSON.stringify((detail?.messages || []).map(m => String(m.update_id)));
}
export function stageFor(item, quote, detail, unresolved = [], today = businessDate()) {
  if (['failed', 'unknown', 'pending'].includes(item.status) || ['send_failed', 'send_uncertain', 'sending'].includes(quote?.status) || detail?.delivery_attempts?.some(a => a.quotation_id === quote?.id && ['pending', 'unknown'].includes(a.status))) return 'attention';
  if (item.status === 'sent' && quote?.status === 'sent') return 'sent';
  if (!quote || !detail) return 'need-info';
  const ids = detail.messages.map(m => String(m.update_id));
  if (JSON.stringify((quote.reviewedMessageIds || []).map(String)) !== JSON.stringify(ids) || unresolved.some(m => String(m.chat_id) === String(item.telegram_chat_id))) return 'need-info';
  if (preparationIssues(editorForm(quote), today, 'sales').length || quote.items.some(i => !(i.unit || '').trim()) || quote.expiryDate < today) return 'need-info';
  if (quote.status === 'sent') return 'need-info';
  if (!managerHandoff(quote, detail)) return 'need-info';
  return quote.items.some(i => !decimalValid(i.unitPrice, true)) ? 'need-price' : 'ready';
}
export function enquiryRow(item, quote, detail, assignments, failed = false) {
  const stage = stageFor(item, quote, detail, assignments);
  const original = item.original_text || '';
  const savedSummary = quote?.summary?.trim();
  const summary = /[\u3400-\u9fff]/u.test(original) && !/[\u3400-\u9fff]/u.test(savedSummary || '') ? '' : savedSummary;
  const savedTitle = quote?.shortTitle?.trim();
  const firstItem = quote?.items?.[0];
  const itemTitle = firstItem ? `${firstItem.quantity ?? ''} ${firstItem.description || ''}`.trim() : '';
  const candidate = savedTitle || (itemTitle ? itemTitle.split(/\s+/).slice(0,4).join(' ') : '') || summary || original;
  const title = /[\u3400-\u9fff]/u.test(original) && !/[\u3400-\u9fff]/u.test(candidate) ? original.slice(0,15) : /[\u3400-\u9fff]/u.test(candidate) ? candidate.slice(0,15) : candidate.split(/\s+/).slice(0,6).join(' ');
  const closedSignature = JSON.stringify([item.status, quote?.version, detail?.messages?.map(m => m.update_id), quote?.reviewSubmission?.submittedAt]);
  return { key: item.id, id: item.id, title: title.length > 40 ? title.slice(0, 39) + '…' : title, name: quote?.client?.name || 'Customer', source: item.source || 'telegram', date: item.created_at, stage, signature: closedSignature,
    text: failed ? 'Details unavailable · Open to check' : ({ 'need-info': 'Check customer details and latest messages', 'need-price': 'Needs a price', ready: 'Saved prices · Manager review required', sent: 'Sent to customer', attention: 'Check delivery history before another send' })[stage] };
}
export function inTab(row, tab, role, closed) { return tab === 'closed' ? !!closed[row.key] : !closed[row.key] && (tab === 'all' || owner(row.stage) === role); }
export function filtered(rows, tab, role, closed, source = '', stage = '') { return rows.filter(r => inTab(r, tab, role, closed) && (!source || r.source === source) && (!stage || r.stage === stage)); }
export const DEMO_ROWS = [
  ['50 tote bags', 'Aiman R. (fictional)', 'instagram', 'need-info'],
  ['Packaging stickers', 'Dapur Mak Jah (fictional)', 'whatsapp', 'need-info'],
  ['T-shirt promo enquiry', 'Daniel L. (fictional)', 'facebook', 'need-info'],
  ['1 roll-up banner', 'Kopi Kita Café (fictional)', 'whatsapp', 'need-price'],
  ['30 polo shirts', 'Greenway Logistics (fictional)', 'facebook', 'need-price'],
  ['200 wedding cards', 'Siti N. (fictional)', 'whatsapp', 'ready'],
  ['5,000 sticker labels', 'Bumi Herbs (fictional)', 'facebook', 'sent'],
].map(([title, name, source, stage], i) => ({ key: 'mock-' + i, title, name, source, stage, date: '2026-10-24T06:00:00Z', mock: true, signature: 'synthetic-v1', text: STAGES[stage] + ' · Synthetic example' }));
export function inboxMarkup(s, rows, closed, dateTime, assignmentForm) {
  const selected = filtered(rows, s.inboxTab, s.role, closed, s.inboxSource, s.inboxStage);
  const base = rows.filter(r => inTab(r, s.inboxTab, s.role, closed));
  const counts = (key, values, otherKey, otherValue) => Object.entries(values).map(([value,label]) => `<option value="${e(value)}" ${s[key] === value ? 'selected' : ''}>${e(label)} (${base.filter(r => (!value || r[key === 'inboxSource' ? 'source' : 'stage'] === value) && (!otherValue || r[otherKey] === otherValue)).length})</option>`).join('');
  const allMatches = filtered(rows, 'all', s.role, closed, s.inboxSource, s.inboxStage).length;
  return `<section class="inbox-title"><h1>What needs you</h1><p>${s.role === 'pm' ? 'Your tasks are pricing and approval. You can also open anything in All.' : 'Finish the customer details, then pass it to the Manager. Only the Manager can add prices and approve.'}</p></section>
  <div class="inbox-toolbar"><div class="inbox-tabs" role="group" aria-label="Inbox view">${[['todo','To do'],['all','All'],['closed','Closed']].map(([tab,label]) => `<button type="button" data-action="inbox-tab" data-tab="${tab}" aria-pressed="${s.inboxTab === tab}">${label} <b>${rows.filter(r => inTab(r,tab,s.role,closed)).length}</b></button>`).join('')}</div><div class="inbox-filters"><select id="inbox-source" aria-label="Filter by source">${counts('inboxSource', {'':'All sources',...SOURCES}, 'stage', s.inboxStage)}</select><select id="inbox-stage" aria-label="Filter by status">${counts('inboxStage', {'':'All statuses',...STAGES}, 'source', s.inboxSource)}</select></div></div>
  <div class="inbox-rows">${selected.map(r => {
    const localClosed = closed[r.key], mine = owner(r.stage) === s.role;
    const canAct = s.role === 'pm' || owner(r.stage) === 'sales';
    const closable = canAct && ['sort','need-info'].includes(r.stage);
    const label = !canAct || r.stage === 'sent' ? 'View' : ({sort:'Sort','need-info':'Open','need-price':'Add price',ready:'Check & send',attention:'Check status'})[r.stage];
    const action = r.stage === 'sort' ? 'inbox-sort' : r.mock ? 'inbox-mock' : 'inbox-open';
    return `<article class="inbox-row"><div class="inbox-line"><div class="inbox-text"><h2 title="${e(r.title)}">${e(r.title)}</h2><p>${e(r.name)} · ${e(SOURCES[r.source] || r.source)} · ${e(dateTime(r.date,true))}${r.mock ? ' · Synthetic' : ''}</p><div class="inbox-status stage-${localClosed ? 'closed' : r.stage}"><i></i>${localClosed ? `Closed by ${e(localClosed.role)} · ${e(dateTime(localClosed.at))}` : e(r.text) + (!canAct && ['need-price','ready','attention'].includes(r.stage) ? ' · Manager only' : '')}</div></div><div class="inbox-actions">${localClosed ? `<button type="button" class="btn primary" data-action="inbox-restore" data-key="${e(r.key)}">Restore</button>` : `${closable ? `<button type="button" class="btn quiet" data-action="inbox-close" data-key="${e(r.key)}">Close</button>` : ''}<button type="button" class="btn ${mine ? 'primary' : 'secondary'}" data-action="${action}" data-key="${e(r.key)}" ${r.mock && r.stage === 'ready' && canAct ? 'disabled title="Sending is only available for Telegram"' : ''} ${r.stage === 'sort' ? `aria-expanded="${s.sortOpen === r.key}"` : ''}>${label}</button>`}</div></div>${!localClosed && r.stage === 'sort' && s.sortOpen === r.key ? assignmentForm(r.message) : ''}</article>`;
  }).join('') || `<div class="inbox-empty"><p>${s.inboxSource || s.inboxStage ? (s.inboxTab === 'todo' ? 'Nothing in your To do matches these filters.' : 'Nothing matches these filters.') : s.inboxTab === 'todo' ? 'All clear. Nothing needs you right now.' : s.inboxTab === 'closed' ? 'Closed messages appear here. You can restore them any time.' : 'No enquiries yet.'}</p>${s.inboxSource || s.inboxStage ? '<button type="button" class="btn secondary" data-action="inbox-clear">Clear filters</button>' : ''}${s.inboxTab === 'todo' && (s.inboxSource || s.inboxStage) && allMatches ? `<button type="button" class="btn primary" data-action="inbox-all">Show ${allMatches} in All</button>` : ''}</div>`}</div>
  <div class="inbox-pagination"><span>Counts and filters cover this loaded page.</span><div><button type="button" class="btn secondary" data-action="previous" ${s.offset === 0 ? 'disabled' : ''}>Previous</button><button type="button" class="btn secondary" data-action="next" ${s.items.length < s.limit ? 'disabled' : ''}>Next</button></div></div>`;
}
