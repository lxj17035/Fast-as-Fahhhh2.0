import { availableChanges, analysisAction } from './ai-assistance.js';
import { pendingCustomerMessages, detailStage, detailNext, canSavePrices, eventLabel, initialDetailTab, submissionIssues } from './detail.js';
import { UNDO_SECONDS, enquiryRow, inboxMarkup, DEMO_ROWS } from './inbox.js';
import { Api } from './api.js';
import { API_BASE_URL } from '../config.js';
import { preparationIssues, reviewGuidance } from './experience.js';
import { loadPDF, paintPDF, releasePDF } from './pdf-viewer.js';
import { VALIDITIES, STATUS, escapeHTML as e, sameId, editable, quotePatch, editorForm, sendBlockers, deliveryHoldResolved, analysisCurrent } from './model.js';

const api = new Api(API_BASE_URL);
const root = document.querySelector('#app');
const readSession = (key, fallback = '') => { try { return sessionStorage.getItem(key) ?? fallback; } catch { return fallback; } };
const writeSession = (key, value) => { try { sessionStorage.setItem(key, value); } catch { /* Browser storage may be disabled. */ } };
const state = {
  route: '', role: readSession('qf-role', 'sales') === 'pm' ? 'pm' : 'sales',
  recordActor: readSession('qf-actor', 'true') === 'true', demoApproval: null, savedSettings: null, connected: null, busy: false, loading: false,
  error: null, notice: '', noticeKind: 'info', offset: 0, limit: 25, items: [], filter: 'all', search: '',
  detail: null, quote: null, form: null, dirty: false, previewVersion: null, pdfURL: null,
  settings: null, client: null, settingsDirty: false, clientDirty: false, hold: false, holdBaseline: [],
  detailTab: 'quote', checkedPoints: [], questionChoices: [],
  inboxTab: 'todo', inboxSource: '', inboxStage: '', inboxRows: [], inboxClosed: {}, sortOpen: null, inboxDemo: false, undo: null,
  assignmentTargets: {}, suggestionValues: {}, selectedChanges: [], suggestionDirty: false, finalReview: null, suggestions: [], reviewed: false, conversation: [], analysis: null, composer: '', messageRequest: null, messageHold: false, assignments: [], profiles: [], activeProfile: '', selectedProfile: '', profileLabel: '',
  pdfReady: false, pdfPage: 1, pdfPages: 0, companyName: 'Demo business workspace', focusPreview: false, expanded: {},
};
let loadId = 0;
let undoTimer;
const localInboxDemo = ['localhost', '127.0.0.1'].includes(location.hostname);
function closedKey() { return 'qf-inbox-closed-' + (state.items[0]?.business_profile_id || state.activeProfile || 'printing'); }
function saveClosed() { writeSession(closedKey(), JSON.stringify(state.inboxClosed)); }
function clearUndo() { clearInterval(undoTimer); state.undo = null; }
function inboxRows() { return [...state.inboxRows, ...(localInboxDemo && state.inboxDemo ? DEMO_ROWS : [])]; }
function inboxToast() { return state.undo ? `<div class="inbox-toast" role="status"><span>Moved to Closed: ${e(state.undo.title)}</span><button type="button" data-action="inbox-undo">Undo (${state.undo.left}s)</button></div>` : ''; }

const paths = {
  inbox: '<path d="M4 4h16v16H4zM4 13h5l2 3h2l2-3h5"/>',
  settings: '<path d="m10 3-1 3-3 1-2 3 2 2-1 3 3 2 3-1 2 3 3-1 1-3 3-1v-4l-3-1-1-3z"/><circle cx="12" cy="11" r="3"/>',
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>', back: '<path d="M19 12H5m6-6-6 6 6 6"/>',
  search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
  refresh: '<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>', plus: '<path d="M12 5v14M5 12h14"/>', close: '<path d="m6 6 12 12M6 18 18 6"/>',
  file: '<path d="M5 3h9l5 5v13H5zM14 3v6h5M8 13h8M8 17h6"/>', check: '<path d="m5 12 4 4L19 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>', send: '<path d="m3 3 19 8-8 3-3 8zM3 3l11 11"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12l3 3 5-6"/>', telegram: '<path d="m3 10 18-7-4 18-6-6-4 3 1-6 10-6-11 7z"/>',
  spark: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>', alert: '<path d="m12 3 10 18H2zM12 9v5M12 17v1"/>',
};
function icon(name) { return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.file}</svg>`; }
function badge(status) { const [label, color] = STATUS[status] || [status || 'Unknown', 'gray']; return `<span class="badge ${color}"><i></i>${e(label)}</span>`; }
function dateTime(value, short = false) {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('en-MY', { timeZone: 'Asia/Kuala_Lumpur', day: 'numeric', month: 'short', ...(short ? {} : { hour: '2-digit', minute: '2-digit' }) }).format(date);
}
function dateOnly(value) { return value ? new Intl.DateTimeFormat('en-MY', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(value + 'T00:00:00Z')) : '—'; }
function button(label, action, { kind = 'secondary', symbol, disabled = false } = {}) {
  return `<button type="button" class="btn ${kind}" data-action="${action}" ${disabled ? 'disabled' : ''}>${symbol ? icon(symbol) : ''}${label}</button>`;
}
function growTextarea(field) { field.style.height = 'auto'; field.style.height = field.scrollHeight + 2 + 'px'; }
function showError(error) { state.error = { message: error.message || 'Something went wrong.', fields: error.fields || {}, status: error.status }; }
function noticeBox() { return state.notice ? `<div data-page-notice class="message ${state.noticeKind}" role="status">${icon(state.noticeKind === 'warning' ? 'alert' : 'check')}<span>${e(state.notice)}${state.notice==='Changes applied to Quote'?button('Go to Quote','detail-quote'):''}</span></div>` : ''; }
function errorBox() {
  if (!state.error) return '';
  return `<div class="message error" role="alert">${icon('alert')}<div><strong>${e(state.error.message)}</strong>${Object.keys(state.error.fields).length ? `<ul>${Object.entries(state.error.fields).map(([key, value]) => `<li>${e(key)}: ${e(value)}</li>`).join('')}</ul>` : ''}${state.error.status === 409 && state.quote ? (state.error.message.includes('Review the latest customer messages') ? '<p>Read the customer messages, tick the review checkbox below the quote details, and save the draft before previewing.</p>' : '<p>Your edits are still here. Follow the message above. If the saved quotation changed, refresh and review its latest version.</p>') : ''}</div></div>`;
}
function connection() { return `<span class="connection ${state.connected === false ? 'offline' : ''}"><i></i>${state.connected === null ? 'Connecting…' : state.connected ? 'Connected' : 'Connection lost'}</span>`; }
function hasEdits() { return state.dirty || state.settingsDirty || state.clientDirty || !!state.composer || state.suggestionDirty; }
function revokePDF() { if (state.pdfURL) URL.revokeObjectURL(state.pdfURL); state.pdfURL = null; state.previewVersion = null; state.pdfReady = false; state.pdfPage = 1; state.pdfPages = 0; state.focusPreview = false; releasePDF().catch(() => {}); }

function render() {
  const review = state.route.startsWith('/enquiries/');
  const settings = state.route === '/settings';
  document.title = `${settings ? 'Settings' : review ? 'Quotation review' : 'Inbox'} · QuoteFlow`;
  root.innerHTML = !review && !settings ? `<div class="inbox-shell"><aside class="sidebar"><a href="#/" class="brand" data-nav="/" aria-label="QuoteFlow inbox">${icon('inbox')}QuoteFlow.</a><div class="workspace"><span class="workspace-avatar">QF</span><div><strong id="company-name">${e(state.companyName)}</strong><span id="profile-label">${e(state.profileLabel || 'Printing')}</span></div></div><p class="nav-label">WORKSPACE</p><nav aria-label="Main navigation"><a class="nav-item active" href="#/" data-nav="/" aria-current="page" aria-label="Enquiry inbox">${icon('inbox')}<span>Enquiry inbox</span></a><a class="nav-item" href="#/settings" data-nav="/settings" aria-label="Settings">${icon('settings')}<span>Settings</span></a></nav><div class="sidebar-bottom"><div class="human-note">${icon('shield')}<strong>Assisted by AI.<br>Approved by you.</strong></div><div class="demo-label">SYNTHETIC DATA DEMO</div></div></aside><div class="inbox-body"><header class="inbox-header"><div class="inbox-bar"><a class="inbox-brand" href="#/" data-nav="/">QuoteFlow.</a><div class="inbox-header-actions"><label>Demo role <select id="role" aria-label="Simulated role"><option value="sales" ${state.role === 'sales' ? 'selected' : ''}>Staff</option><option value="pm" ${state.role === 'pm' ? 'selected' : ''}>Manager</option></select></label></div></div></header><main id="main" tabindex="-1" class="inbox-main">${state.loading ? '<p role="status">Loading enquiries…</p>' : inboxPage()}</main><footer class="inbox-footer">Assisted by AI. Approved by you. · Synthetic data demo<br>Close / Restore is saved in this browser session only. New messages reopen locally closed items.</footer>${inboxToast()}</div></div>` : `<aside class="sidebar">
    <a href="#/" class="brand" data-nav="/" aria-label="QuoteFlow inbox"><span class="brand-symbol">${icon('inbox')}</span>QuoteFlow<span class="brand-dot">.</span></a>
    <div class="workspace"><span class="workspace-avatar">QF</span><div><strong id="company-name">${e(state.companyName)}</strong><span id="profile-label">${e(state.profileLabel || 'Fictional business workspace')}</span></div></div>
    <p class="nav-label">WORKSPACE</p><nav aria-label="Main navigation"><a href="#/" data-nav="/" aria-label="Enquiry inbox" class="nav-item ${!settings ? 'active' : ''}" ${!settings ? 'aria-current="page"' : ''}>${icon('inbox')}<span>Enquiry inbox</span>${state.items.length ? `<span class="nav-count">${state.items.length}</span>` : ''}</a><a href="#/settings" data-nav="/settings" aria-label="Settings" class="nav-item ${settings ? 'active' : ''}" ${settings ? 'aria-current="page"' : ''}>${icon('settings')}<span>Settings</span></a></nav>
    <div class="sidebar-bottom"><div class="human-note">${icon('shield')}<strong>Assisted by AI.<br>Approved by you.</strong><p>You stay in control of pricing and every outgoing quotation.</p></div><div class="demo-label"><i></i>SYNTHETIC DATA DEMO</div><small>Orbyte Smart SME Challenge</small></div>
    </aside><div class="app-body"><header class="topbar"><div class="breadcrumb">Workspace <span>/</span> <strong>${settings ? 'Settings' : review ? 'Quotation review' : 'Enquiry inbox'}</strong></div><div class="topbar-right"><div id="connection">${connection()}</div><div class="role-control"><span class="avatar">${state.role === 'pm' ? 'PM' : 'S'}</span><label>Demo role<select id="role" aria-label="Simulated role"><option value="sales" ${state.role === 'sales' ? 'selected' : ''}>Staff</option><option value="pm" ${state.role === 'pm' ? 'selected' : ''}>Manager</option></select></label></div></div></header>
    <main id="main" tabindex="-1" ${state.loading ? 'aria-busy="true"' : ''}>${state.loading ? '<div class="loading"><span class="spinner"></span><h2>Loading your workspace</h2><p>Getting your saved details…</p></div>' : settings ? settingsPage() : review ? reviewPage() : inboxPage()}</main>
    <footer class="app-footer"><span>QuoteFlow <span>/</span> Enquiry to quotation, connected.</span><span>Supervised demo · Times in Kuala Lumpur</span></footer></div>`;
  root.querySelectorAll('textarea').forEach(growTextarea);
  for (const [name, message] of Object.entries(state.error?.fields || {})) {
    const field = Array.from(root.querySelectorAll('[name]')).find(item => item.name === name);
    if (!field) continue;
    field.setAttribute('aria-invalid', 'true');
    const hint = document.createElement('small'); hint.id = 'field-error-' + name.replace(/[^a-z0-9-]/gi, '-');
    hint.className = 'field-error'; hint.textContent = message; field.setAttribute('aria-describedby', hint.id); (field.closest('label') || field).after(hint);
  }
  if (!state.loading && review && state.form) updateEditorIndicators();
  const canvas = document.querySelector('#pdf-canvas');
  if (canvas) {
    state.pdfReady = false; updateEditorIndicators();
    paintPDF(canvas, state.pdfPage).then(painted => {
      if (painted) { state.pdfReady = true; updateEditorIndicators(); if (state.focusPreview) { state.focusPreview = false; document.querySelector('#preview-panel').scrollIntoView({ behavior: 'smooth', block: 'start' }); } }
    }).catch(() => {
      if (canvas.isConnected) {
        state.pdfReady = false;
        document.querySelector('#pdf-render-status').textContent = 'PDF display failed. Reload the PDF or open it separately.';
        updateEditorIndicators();
      }
    });
  }
}
function assignmentForm(message) {
  return `<form class="assignment-form inbox-sort-panel" data-update="${e(message.update_id)}" novalidate><blockquote>${e(message.text)}</blockquote><label class="field"><span>Add to an existing enquiry…</span><select name="enquiry_id"><option value="">Choose an enquiry from this page…</option>${state.items.filter(item => sameId(item.telegram_chat_id,message.chat_id)).map(item => `<option value="${e(item.id)}" ${state.assignmentTargets[message.update_id] === item.id ? 'selected' : ''}>${e(dateTime(item.created_at))} · ${e(item.original_text.slice(0,100))}</option>`).join('')}</select></label><div class="editor-buttons"><button class="btn primary" name="action" value="assign">Add</button><button class="btn secondary" name="action" value="new">New enquiry</button><button class="btn secondary" name="action" value="unrelated">Mark unrelated</button></div><details><summary>Association history</summary>${(message.history || []).map(h => `<p>${e(h.actor)} · ${e(h.action)} · ${e(dateTime(h.timestamp))}</p>`).join('') || '<p>No assignment decisions yet.</p>'}</details><details><summary>Enquiry not on this page?</summary><label class="field"><span>Enquiry ID</span><input name="manual_enquiry_id" placeholder="Paste a copied enquiry ID" /></label></details><p class="field-note">Close hides this message locally. Mark unrelated records a decision on the server.</p></form>`;
}
function inboxPage() {
  return `${errorBox()}${noticeBox()}<div class="inbox-tools"><button type="button" class="btn secondary" data-action="refresh">↻ Refresh inbox</button>${localInboxDemo ? `<label><input id="inbox-demo" type="checkbox" ${state.inboxDemo ? 'checked' : ''} /> Show synthetic channel examples</label>` : ''}</div>${inboxMarkup(state, inboxRows(), state.inboxClosed, dateTime, assignmentForm)}${localInboxDemo && state.inboxDemo ? '<p class="field-note">Extra channels are synthetic display examples. Sending is available only for Telegram.</p>' : ''}`;
}
function disclosure(key, defaultOpen = false) {
  return `data-disclosure="${key}" ${(state.expanded[key] ?? defaultOpen) ? 'open' : ''}`;
}
function guidance() { return reviewGuidance(state); }
function progressMarkup() {
  const stage = detailStage(state);
  const current = state.quote?.status === 'sent' ? 3 : state.detailTab === 'preview' ? 2 : 1;
  return `<ol class="review-progress" aria-label="Quotation progress">${['Details','Preview','Send'].map((label,i)=>`<li class="${i+1 === current ? 'current' : i+1 < current ? 'done' : ''}" ${i+1===current?'aria-current="step"':''}><span>${i+1}</span><strong>${label}</strong></li>`).join('')}</ol>`;
}
function nextStepMarkup() {
  const next = detailNext(state);
  return `<div class="detail-next-copy"><h3>${e(next.title)}</h3><p>${e(next.body)}</p></div><div class="detail-next-actions">${next.buttons.map(([label,action,primary,disabled])=>button(e(label),action,{kind:primary?'primary':'secondary',disabled:state.busy || !!disabled})).join('')}</div>`;
}
function newMessageAlert() {
  const messages = pendingCustomerMessages(state.quote,state.detail);
  if (!messages.length || !state.quote) return '';
  const canAcknowledge = editable(state.quote) && !frozenDelivery();
  return `<section class="detail-message-alert" role="status" aria-label="New customer messages"><h2>${messages.length===1?'New customer message after your draft':`${messages.length} new customer messages after your draft`}</h2>${messages.map(m=>`<blockquote>${e(m.text)}</blockquote><time>${e(dateTime(m.received_at))}</time>`).join('')}<p>Check these requirements against the quote. Confirm only after you have handled them.</p><div class="editor-buttons">${canAcknowledge?button('Confirm handled & save quote','confirm-messages',{disabled:state.busy}):'<span>A sent quotation stays protected. Create a revision if these requirements change it.</span>'}${button('Reply to customer','detail-messages',{disabled:state.busy})}</div></section>`;
}
function detailChecks() {
  if (!state.form) return '';
  const remaining = state.form.missingInformation;
  const all = [...remaining,...state.checkedPoints.filter(p=>!remaining.includes(p))];
  if (!all.length) return '';
  return `<section class="detail-checks" id="missing-review" tabindex="-1"><h3>Please check (${all.length-remaining.length} of ${all.length} done)</h3><p>Found in the customer messages. Mark each point once resolved, or after deciding it is not needed.</p>${all.map(point=>{const index=remaining.indexOf(point);return `<div class="missing-row ${index<0?'point-done':''}"><span>${e(point)}</span><button type="button" class="text-link" data-action="${index<0?'undo-check':'dismiss-missing'}" data-index="${index}" data-point="${e(point)}" ${state.busy||!editable(state.quote)||frozenDelivery()?'disabled':''}>${index<0?'Undo':'Mark checked'}</button></div>`}).join('')}</section>`;
}
function detailReferences() {
  const d=state.detail,q=state.quote;
  return `<details class="quiet-details references" ${disclosure('references')}><summary>More details</summary><dl><dt>Enquiry reference</dt><dd><code>${e(d.id)}</code></dd>${q?`<dt>Client reference</dt><dd><code>${e(q.client.id)}</code></dd><dt>Saved version</dt><dd>${q.version}</dd><dt>Full AI summary</dt><dd>${e(q.summary)}</dd>${q.draftError?`<dt>Manual fallback information</dt><dd>${e(q.draftError)}</dd>`:''}`:''}<dt>Original Telegram chat</dt><dd><code>${e(d.telegram_chat_id)}</code></dd></dl><p>Delivery always goes to this original conversation.</p></details>`;
}
function reviewPage() {
  if (!state.detail) return `${button('Back to enquiries','inbox')}${errorBox()}<p>We could not open this enquiry.</p>`;
  if (state.finalReview) return finalReviewPage();
  const d=state.detail,q=state.quote,stage=detailStage(state),next=detailNext(state),pending=pendingCustomerMessages(q,d);
  const stageLabel=q?.status==='sent'?'Sent':({ 'need-info':'Draft · needs info','need-price':'Draft · needs price',ready:'Ready to send',attention:'Needs checking' })[stage] || 'Draft';
  return `<div class="detail-workspace"><div class="review-top"><a href="#/" data-nav="/" class="back-link">${icon('back')} All enquiries</a>${button('Refresh','refresh',{disabled:state.busy})}</div><section class="page-heading review-heading"><div><h1>${q?.client.name.trim()?`Quote for ${e(q.client.name)}`:'Prepare a quote'}</h1><p>${q?`${e(q.number)} · ${e(q.currency)} · Telegram`:'Telegram enquiry'}</p></div><span class="badge ${stage==='sent'?'green':stage==='ready'?'blue':'amber'}">${e(stageLabel)}</span></section><div id="review-progress">${progressMarkup()}</div>${errorBox()}${noticeBox()}<section class="detail-next next-step-panel" data-kind="${next.stage}" aria-label="Next step"><div id="next-step-content">${nextStepMarkup()}</div></section>${newMessageAlert()}
  <div class="detail-tabs" role="tablist" aria-label="Quotation sections">${[['messages',`Messages${pending.length?` (${pending.length} new)`:''}`],['quote','Quote'],['preview','Preview'],['activity','Activity']].map(([tab,label])=>`<button type="button" role="tab" id="detail-tab-${tab}" aria-selected="${state.detailTab===tab}" aria-controls="detail-pane-${tab}" data-action="detail-tab" data-tab="${tab}">${label}</button>`).join('')}</div>
  <section id="detail-pane-quote" role="tabpanel" aria-labelledby="detail-tab-quote" ${state.detailTab!=='quote'?'hidden':''}>${detailChecks()}${relationshipPanel()}<section class="panel editor-panel"><div class="panel-heading"><div><h2>Quote details</h2><p>${state.role==='pm'?'Edit the details and prices before sending.':'Prepare the details. Only a Manager can enter prices.'}</p></div><span id="save-state" class="save-state"></span></div>${q?editor():`<div class="settings-panel"><p>Prepare a draft first, or open Messages to read the enquiry.</p>${button('Prepare draft','draft-ai',{disabled:state.busy})}${button('Write it myself','draft-manual',{disabled:state.busy})}</div>`}</section></section>
  <section id="detail-pane-preview" role="tabpanel" aria-labelledby="detail-tab-preview" ${state.detailTab!=='preview'?'hidden':''}><section class="panel preview-panel" id="preview-panel"><div class="panel-heading"><div><h2>Quote preview</h2><p id="preview-status">${q?.total===null?'Draft preview. Prices are not set yet.':'The saved PDF your customer will receive.'}</p></div></div>${state.detailTab==='preview'?pdfContent():''}<div class="preview-actions">${button(state.pdfURL?'Refresh preview':'Load saved PDF','detail-preview',{disabled:state.busy||!q||(pending.length>0&&q.status!=='sent'&&!frozenDelivery())})}${state.pdfURL?`<a class="text-link" href="${e(state.pdfURL)}" target="_blank" rel="noopener">Open full PDF ↗</a>`:''}</div></section>${q&&editable(q)?`<section class="detail-checkpoint"><h3>Before final Manager approval</h3><p>${pending.length?'Latest customer requirements need checking.':'Latest customer requirements are checked.'} ${pending.length?button('Go to Messages','detail-messages'):''}</p><p>${state.form.missingInformation.length?`${state.form.missingInformation.length} points still to check.`:'All flagged points checked.'} ${state.form.missingInformation.length?button('Go to checks','detail-quote'):''}</p><div class="editor-buttons">${button('Back to edit','detail-quote')}${button('Save draft','detail-save',{disabled:state.busy||!state.dirty})}${state.role==='pm'?button('Manager Review & Send','approve',{kind:'primary',disabled:state.busy||state.dirty||pending.length>0||state.hold||!canSavePrices(state.form)||state.form.missingInformation.length>0}):'<span>Only a Manager can price and approve. Saving does not notify a Manager.</span>'}</div></section>`:''}</section>
  <section id="detail-pane-messages" role="tabpanel" aria-labelledby="detail-tab-messages" ${state.detailTab!=='messages'?'hidden':''}>${conversationPanel()}</section>
  <section id="detail-pane-activity" role="tabpanel" aria-labelledby="detail-tab-activity" ${state.detailTab!=='activity'?'hidden':''}>${deliveryHistory()}${activityHistory()}${detailReferences()}</section></div>`;
}
function frozenDelivery() { return (state.detail?.delivery_attempts || []).some(a => sameId(a.quotation_id, state.quote?.id) && a.pdf_status === 'sent' && a.status !== 'sent'); }
function finalSendReady() { return state.finalReview?.send_ready && state.role === 'pm' && !state.busy && !state.hold && !state.dirty && state.pdfReady && state.previewVersion === state.finalReview.quotation.version; }
function finalReviewPage() {
  const review = state.finalReview, q = review.quotation;
  return `<section class="page-heading"><div><h1>Manager Review & Send</h1><p>${e(q.number)} · saved version ${q.version}</p></div>${badge(q.status)}</section>${errorBox()}${noticeBox()}<div class="review-grid simple-review"><section class="panel settings-panel v2-panel"><h2>Confirmed quotation</h2><dl><dt>Customer</dt><dd>${e(q.client.name)}<br>${e(q.client.address)}</dd><dt>Business profile</dt><dd>${e(review.business_profile.industry)} · ${e(review.business_profile.companyName)}</dd><dt>Issue date</dt><dd>${e(dateOnly(q.issueDate))}</dd><dt>Valid for</dt><dd>${e(VALIDITIES[q.validity])}</dd><dt>Valid until</dt><dd>${e(dateOnly(q.expiryDate))}</dd></dl><div class="table-scroll"><table><thead><tr><th>Item</th><th>Qty / unit</th><th>Unit price</th><th>Amount</th><th>Notes</th></tr></thead><tbody>${q.items.map(item => `<tr><td>${e(item.item_name || item.description)}</td><td>${e(item.quantity)} ${e(item.unit)}</td><td>${e(item.unitPrice)}</td><td>${e(item.amount ?? item.lineTotal)}</td><td>${e(item.notes)}</td></tr>`).join('')}</tbody></table></div><p>Quotation notes: ${e(q.notes || 'None')}</p><h3>Total: ${e(q.currency)} ${e(q.total)}</h3><h2>Telegram summary preview</h2><blockquote class="summary-preview">${e(review.telegram_summary)}</blockquote><p>Recipient: original Telegram chat ${e(state.detail.telegram_chat_id)}</p>${review.delivery_mode === 'summary_only' ? '<p class="message warning">The PDF was already accepted. Its content is frozen. This approval retries only the identical saved summary. New customer requirements still need separate review.</p>' : '<p>Approval sends this saved PDF and its matching summary.</p>'}<div class="editor-buttons">${button('Back to Edit', 'back-edit', {disabled: state.busy})}${button(review.delivery_mode === 'summary_only' ? 'Approve & Send summary' : 'Approve & Send', 'final-send', {kind:'primary',disabled:!finalSendReady()})}</div></section><section class="panel preview-panel" id="preview-panel"><div class="panel-heading"><h2>Saved PDF · version ${q.version}</h2></div>${pdfContent()}<p class="field-note">Saved PDF fingerprint: ${e(review.pdf.sha256)}</p></section></div>`;
}
function suggestionsPanel() {
  const available = availableChanges(state);
  if (!available.length) return '';
  return `<section class="settings-panel v2-panel"><h2>AI Suggested Changes</h2><p class="field-note">Review, edit and select changes before applying. Saved edits are never overwritten automatically.</p>${(state.analysis?.changeWarnings || []).map(w => `<p>${e(w)}</p>`).join('')}${available.map(set => `<form class="suggestion-form" data-set="${e(set.id)}" novalidate><fieldset ${state.busy || state.dirty || !editable(state.quote) ? 'disabled' : ''}>${set.changes.map(c => `<div class="suggestion-change"><label class="checkbox-label"><input type="checkbox" name="selected" value="${e(c.id)}" ${state.selectedChanges.includes(c.id) ? 'checked' : ''} /> ${e(({ADD_ITEM:'Add item',UPDATE_ITEM:'Update item',UPDATE_FIELD:'Update detail'})[c.type] || 'Suggested change')}${c.type === 'UPDATE_ITEM' ? ` - item ${c.index + 1}` : ''}</label>${c.type === 'UPDATE_FIELD' ? input(e(c.field), c.id + ':value', state.suggestionValues[c.id + ':value'] ?? c.value) : Object.entries(c.data).map(([key,value]) => input(e(key), c.id + ':' + key, state.suggestionValues[c.id + ':' + key] ?? value ?? '')).join('')}</div>`).join('')}<button class="btn primary">Apply selected changes</button></fieldset></form>`).join('')}</section>`;
}
function relationshipPanel() {
  if (state.quote?.status !== 'sent') return '';
  return `<section class="panel settings-panel v2-panel"><h2>Post-send request</h2><p>Confirm grouping with the customer. A revision keeps the original PDF; an additional quote needs a separate enquiry in the same chat.</p><p>AI advice: ${e(state.analysis?.relationshipIntent || 'Ask the customer if grouping is unclear.')}</p><form id="fork-form" novalidate><label class="field"><span>Relationship</span><select name="relationship"><option value="revision">Revision</option><option value="additional">Additional quotation</option></select></label>${input('Additional enquiry reference', 'enquiry_id', '')}<button class="btn secondary" ${state.busy ? 'disabled' : ''}>Create quotation from confirmed request</button></form></section>`;
}
function conversationPanel() {
  const current = analysisCurrent(state.analysis,state.quote,state.detail,state.conversation,state.assignments);
  const pending = new Set(pendingCustomerMessages(state.quote,state.detail).map(m=>String(m.update_id)));
  const questions = current ? state.analysis.extraction?.clarificationSuggestions || [] : [];
  const conversation = state.conversation.length ? state.conversation : state.detail.messages.map(m=>({...m,direction:'incoming',created_at:m.received_at}));
  return `<section class="panel detail-conversation"><div class="panel-heading"><h2>Messages</h2></div><ol class="conversation-list">${conversation.map(m=>`<li class="${m.direction==='incoming'?'customer-bubble':'team-bubble'} ${m.direction==='incoming'&&pending.has(String(m.update_id ?? m.id?.replace(/^in-/,'')))?'new-bubble':''}"><strong>${m.kind?e(eventLabel(m.kind)):m.direction==='incoming'?'Customer':m.actor==='pm'?'Manager':'Staff'}</strong><time>${e(dateTime(m.created_at))}</time><blockquote>${e(m.text)}</blockquote><span>${e(m.status==='sent'?'Accepted by Telegram':m.status==='received'?'Received':m.status)}</span></li>`).join('')}</ol><section class="detail-questions"><h3>Suggested questions</h3><p class="field-note">${current?'Select questions to put in your message. You decide what is sent.':'Suggestions need updating. You can also write a message yourself.'}</p>${questions.map((q,i)=>`<label class="checkbox-label"><input type="checkbox" name="question-choice" value="${i}" ${state.questionChoices.includes(i)?'checked':''} />${e(q)}</label>`).join('')}<div class="editor-buttons">${button('Add selected questions to message','add-questions',{disabled:state.busy||!questions.length})}</div></section>${suggestionsPanel()}${analysisAction(state)?`<div class="analysis-recovery"><p class="field-note">${state.analysis?.status==='failed'?'AI analysis failed. You can edit Quote manually or retry.':'Analysis is missing or out of date. You can edit Quote manually or analyze these messages.'}</p>${button(analysisAction(state),'analyze',{disabled:state.busy||state.dirty})}${state.dirty?'<p class="field-note">Save your Quote edits before analyzing.</p>':''}</div>`:state.analysis?.status==='running'?'<p class="field-note" role="status">Analyzing customer messages… You can keep editing Quote.</p>':''}<form id="message-form" novalidate><label class="field"><span>Message to customer</span><textarea name="message" rows="4" maxlength="4000" ${state.busy||state.messageHold?'disabled':''}>${e(state.composer)}</textarea></label><p class="field-note">${state.messageHold?'Delivery unconfirmed. Check the original chat before any further send.':'Only your explicit Send delivers this text to the original Telegram chat.'}</p><button class="btn primary" ${state.busy||state.messageHold?'disabled':''}>Send message</button></form></section>`;
}
async function loadConversation(id) {
  const token = loadId;
  const [conversation, analysis, assignments] = await Promise.all([api.conversation(id), api.analysis(id), api.assignments()]);
  if (token !== loadId || state.detail?.id !== id) return;
  state.conversation = conversation.items; state.analysis = analysis; state.assignments = assignments.items;
  if (state.quote) state.suggestions = (await api.suggestions(state.quote.id)).items;
  const heldRequest = readSession('qf-message-hold-' + id);
  const resolved = state.conversation.find(m => m.request_id === heldRequest && ['sent', 'failed'].includes(m.status));
  if (resolved) writeSession('qf-message-hold-' + id, '');
  state.messageHold = (!!heldRequest && !resolved) || state.conversation.some(m => m.direction === 'outgoing' && !m.kind && ['unknown', 'pending'].includes(m.status));
}
function input(label, name, value, { type = 'text', max = 500, placeholder = '', extra = '' } = {}) { return `<label class="field"><span>${label}</span><input name="${name}" type="${type}" value="${e(value)}" maxlength="${max}" placeholder="${e(placeholder)}" ${extra} /></label>`; }
function validitySelect(value, name = 'validity') { return `<label class="field"><span>Valid for</span><select name="${name}">${Object.entries(VALIDITIES).map(([code, label]) => `<option value="${code}" ${code === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>`; }
function editor() {
  const q = state.quote, f = state.form, locked = !editable(q) || frozenDelivery() || state.busy;
  return `<form id="quote-form" novalidate><fieldset ${locked ? 'disabled' : ''}>
    <div class="editor-section"><h3 class="form-section-title">Customer</h3><div class="field-grid">${input('Customer name', 'clientName', f.client.name, { placeholder: 'Name on the quotation' })}<label class="field"><span>Address <small>Optional</small></span><textarea style="resize: none" name="clientAddress" rows="2" maxlength="500" placeholder="Leave blank if unknown">${e(f.client.address)}</textarea></label></div></div>
    <div class="editor-section"><h3 class="form-section-title">Items & prices</h3><p class="field-note pricing-note">Prices in ${e(q.currency)}. Leave a price blank if you’re still checking it.</p>
      <p class="field-note">Staff prepares items; only a Manager enters or clears prices.</p><div id="item-rows" tabindex="-1">${f.items.map((item, i) => `<div class="item-row"><textarea style="resize: none" name="item-description-${i}" rows="2" maxlength="2000" aria-label="Item ${i + 1} description" placeholder="What are you quoting for?">${e(item.description)}</textarea><input name="item-quantity-${i}" inputmode="decimal" aria-label="Item ${i + 1} quantity" placeholder="Qty" value="${e(item.quantity)}" /><input name="item-price-${i}" inputmode="decimal" aria-label="Item ${i + 1} unit price" ${state.role !== 'pm' ? 'readonly' : ''} placeholder="Price" value="${e(item.unitPrice)}" /><button type="button" class="icon-button" data-action="remove-item" data-index="${i}" aria-label="Remove item ${i + 1}">${icon('close')}</button><label class="field"><span>Unit</span><input name="item-unit-${i}" aria-label="Item ${i + 1} unit" maxlength="40" value="${e(item.unit)}" placeholder="pcs, job, visit, hour" /></label><label class="field item-notes"><span>Item notes</span><textarea style="resize: none" name="item-notes-${i}" aria-label="Item ${i + 1} notes" rows="2" maxlength="2000">${e(item.notes)}</textarea></label><p class="field-note">Saved amount: ${e(q.items[i]?.amount ?? q.items[i]?.lineTotal ?? (state.role === 'pm' ? 'Price needed' : 'Waiting for Manager pricing'))}</p></div>`).join('')}</div>
      ${!f.items.length ? '<p class="no-items">Add the first item to begin.</p>' : ''}${button('Add another item', 'add-item', { symbol: 'plus', kind: 'text', disabled: locked || f.items.length >= 100 })}
      <div class="total-bar"><div><span id="total-label">Saved total</span><small id="total-note">Valid through ${e(dateOnly(q.expiryDate))}</small></div><strong>${q.total === null ? (state.role === 'pm' ? 'Prices needed' : 'Waiting for Manager pricing') : `${e(q.currency)} ${e(q.total)}`}</strong></div>
    </div>
    <details class="editor-options" ${disclosure('options')}><summary>Dates & notes <span>Optional changes</span></summary><div class="drawer-content"><div class="field-grid">${input('Issue date', 'issueDate', f.issueDate, { type: 'date' })}${validitySelect(f.validity)}</div><p class="field-note">The saved quote is valid through ${e(dateOnly(q.expiryDate))}. Save date changes to update this.</p><label class="field notes-field"><span>Notes for the customer <small>Optional</small></span><textarea style="resize: none" name="notes" rows="3" maxlength="4000" placeholder="Add any reviewed terms or a helpful note…">${e(f.notes)}</textarea></label></div></details>
    </fieldset><div class="editor-bottom"><span>${locked && !state.busy ? 'Protected after sending or while delivery is unconfirmed.' : 'Save a draft at any time. Preview before sending.'}</span><div class="editor-buttons"><button class="btn secondary" type="submit" id="save-quote" ${locked || !state.dirty ? 'disabled' : ''}>Save draft</button>${state.role==='sales'?button('Submit for review','submit-review',{kind:'primary',disabled:state.busy||submissionIssues(state).length>0}):''}<button class="btn secondary" type="button" id="save-preview" data-action="save-preview" ${locked ? 'disabled' : ''}>${icon('file')} ${state.dirty ? 'Save & preview' : state.role === 'pm' ? 'Preview quote' : 'Preview draft'}</button></div></div></form>`;
}
function pdfContent() {
  if (state.pdfURL) return `<div class="pdf-renderer"><canvas id="pdf-canvas" role="img" aria-label="Saved quotation PDF version ${state.previewVersion}, page ${state.pdfPage} of ${state.pdfPages}"></canvas></div><p class="pdf-render-status" id="pdf-render-status"></p><div class="pdf-pagination">${button('Previous page', 'pdf-previous', { disabled: state.pdfPage <= 1 })}<span>Page ${state.pdfPage} / ${state.pdfPages}</span>${button('Next page', 'pdf-next', { disabled: state.pdfPage >= state.pdfPages })}</div>`;
  return `<div class="pdf-empty"><div class="paper-art"><div class="paper-brand"></div><div class="paper-title"></div><div class="paper-line"></div><div class="paper-line short"></div><div class="paper-table"></div><div class="paper-line short right"></div><span>${icon('file')}</span></div><h3>Check it before you send.</h3><p>Save the quote, then preview the PDF your customer will receive.</p></div>`;
}
function reasons() { return sendBlockers({ ...state, previewVersion: state.pdfReady ? state.previewVersion : null }); }
function retryAttempt() { return state.detail?.delivery_attempts.find(attempt => sameId(attempt.quotation_id, state.quote?.id) && attempt.can_retry); }
function updateEditorIndicators() {
  if (state.finalReview) { const send = document.querySelector('[data-action="final-send"]'); if (send) send.disabled = !finalSendReady(); return; }
  const el = document.querySelector('#save-state'); if (!el || !state.quote) return;
  el.textContent = state.busy ? 'Working…' : state.dirty ? 'Not saved yet' : 'All changes saved';
  el.classList.toggle('unsaved', state.dirty);
  document.querySelector('#save-quote').disabled = state.busy || !state.dirty || !editable(state.quote) || frozenDelivery();
  const savePreview = document.querySelector('#save-preview');
  savePreview.disabled = state.busy || !editable(state.quote) || frozenDelivery();
  savePreview.innerHTML = icon('file') + ' ' + (state.dirty ? 'Save & preview' : state.role === 'pm' ? 'Preview quote' : 'Preview draft');
  document.querySelectorAll('[data-action="submit-review"]').forEach(button => { button.disabled = state.busy || submissionIssues(state).length > 0; });
  document.querySelectorAll('[data-action="preview"]').forEach(button => { button.disabled = state.busy || state.dirty; });
  document.querySelector('#total-label').textContent = state.dirty ? 'Last saved total' : 'Saved total';
  document.querySelector('#total-note').textContent = state.dirty ? 'Save to update the total and dates' : `Valid through ${dateOnly(state.quote.expiryDate)}`;
  document.querySelector('#preview-status').textContent = state.dirty ? 'Save your changes for an updated preview.' : state.pdfReady && state.previewVersion === state.quote.version ? 'Matches your saved quote.' : state.pdfURL ? 'Preparing your preview…' : 'The document your customer will receive.';
  document.querySelector('#next-step-content').innerHTML = nextStepMarkup();
  document.querySelector('.next-step-panel').dataset.kind = detailNext(state).stage;
  document.querySelector('#review-progress').innerHTML = progressMarkup();
}
function deliveryHistory() {
  const attempts = state.detail.delivery_attempts;
  if (!attempts.length && !state.hold) return '';
  return `<details class="panel history-panel simple-history" ${disclosure('delivery', true)}><summary>Delivery history <span>${attempts.length} ${attempts.length === 1 ? 'attempt' : 'attempts'}</span></summary>
    ${state.hold ? `<div class="message warning">${icon('alert')}<p>Check the original Telegram chat. We’re still waiting for a confirmed result, so sending again is blocked.</p></div>` : ''}
    <div class="attempts">${attempts.map(a => `<div class="attempt"><div>${badge(a.status)}<span>${e(dateTime(a.approved_at))}</span></div><p>${a.status === 'sent' ? (a.pdf_status === 'sent' && a.summary_status === 'sent' ? 'Telegram accepted the PDF and summary. This does not confirm it has been read.' : 'Telegram accepted the quotation. Component delivery details were not recorded for this historical attempt.') : a.status === 'failed' ? 'Telegram rejected this attempt. A PM can review and approve a new attempt when available.' : 'Check the original conversation before taking any further action.'}</p><p>PDF: ${e(a.pdf_status || 'Not recorded')} · Summary: ${e(a.summary_status || 'Not recorded')}</p><details class="quiet-details"><summary>Technical reference</summary><p>Attempt <code>${e(a.attempt_id)}</code>${a.retry_of_attempt_id ? ` · Previous attempt <code>${e(a.retry_of_attempt_id)}</code>` : ''}</p><p>Saved version: ${a.version}${a.provider_message_id ? ` · Telegram reference: ${e(a.provider_message_id)}` : ''}</p>${a.safe_error_code ? `<p>Diagnostic: ${e(a.safe_error_code)}</p>` : ''}</details></div>`).join('')}</div></details>`;
}
const actionLabels = { telegram_received: 'Telegram enquiry received', enquiry_created: 'Added to the inbox', quotation_draft_created: 'Quotation draft created', quotation_updated: 'Quotation changes saved', pm_approved: 'PM approved delivery', pdf_send_attempted: 'PDF delivery started', pdf_send_succeeded: 'Telegram accepted the PDF', pdf_send_failed: 'Telegram rejected delivery', delivery_unknown: 'Delivery requires verification' };
function activityHistory() {
  return `<details class="panel history-panel simple-history" ${disclosure('activity', true)}><summary>Activity <span>${state.detail.activity.length} updates</span></summary><ol class="timeline">${[...state.detail.activity].reverse().map(a => `<li><span class="timeline-dot ${a.result === 'failed' ? 'failed' : ''}">${icon(a.action.includes('send') ? 'send' : 'check')}</span><div><strong>${e(eventLabel(a.action))}</strong><p>${e(a.actor_origin === 'simulated' ? `${a.role === 'pm' ? 'Manager' : a.role === 'sales' ? 'Staff' : 'Team member'} (demo role)` : a.actor_origin === 'system' ? 'System' : 'Actor not recorded')}</p></div><time datetime="${e(a.timestamp)}">${e(dateTime(a.timestamp))}</time></li>`).join('') || '<li class="muted">No updates recorded yet.</li>'}</ol></details>`;
}
function settingsPatch() { return Object.fromEntries(['companyName','companyAddress','currency','defaultValidity'].map(key => [key, state.settings[key]])); }
function settingsChanged() { return JSON.stringify(settingsPatch()) !== JSON.stringify(state.savedSettings); }
async function saveBusinessSettings() {
  state.settings = await api.saveProfile(state.settings.business_profile_id, settingsPatch());
  state.savedSettings = settingsPatch(); state.settingsDirty = false;
  state.companyName = state.settings.companyName;
  state.profiles = state.profiles.map(profile => profile.id === state.settings.business_profile_id ? {...profile,...state.settings} : profile);
  state.notice = 'Business details saved.';
}
function settingsPage() {
  const manager = state.role === 'pm';
  return `<div class="business-settings"><section class="page-heading"><div><h1>Business settings<span class="heading-dot">.</span></h1><p>Used on every new quotation. Active business: <strong>${e(state.profileLabel)}</strong>.</p></div>${button('Refresh','refresh',{symbol:'refresh',disabled:state.busy})}</section>${errorBox()}${noticeBox()}
  ${!manager ? '<p class="settings-view-note">You can view these settings. Only a Manager can change them.</p>' : ''}
  <section class="panel settings-panel v2-panel"><div class="panel-heading"><h2>Business details</h2></div>
  ${state.settings ? `<form id="settings-form" novalidate><fieldset ${state.busy || !manager ? 'disabled' : ''}>
  ${input('Company name','companyName',state.settings.companyName,{extra:'required'})}
  <label class="field"><span>Company address</span><textarea style="resize: none" name="companyAddress" rows="3" maxlength="500">${e(state.settings.companyAddress)}</textarea></label>
  <div class="field-grid">${input('Currency','currency',state.settings.currency,{max:3,extra:'required pattern="[A-Z]{3}" title="Three uppercase letters, e.g. MYR"'})}${validitySelect(state.settings.defaultValidity,'defaultValidity').replace('Valid for','Quotes are valid for')}</div>
  <p class="field-note">Dates use Kuala Lumpur time. You can change the validity on each quote.</p></fieldset>
  <div class="form-bottom"><p>Changes apply to new quotes only. Sent quotes are not changed. <strong id="settings-dirty" ${state.settingsDirty ? '' : 'hidden'}>Unsaved changes</strong></p>${manager ? `<button type="submit" class="btn primary" ${state.busy || !state.settingsDirty ? 'disabled' : ''}>Save business details</button>` : ''}</div></form>` : '<p>Business details unavailable. Use Refresh to try again.</p>'}</section>
  ${manager ? `<details class="panel settings-demo" ${disclosure('settings-demo',false)}><summary>Demo tools</summary><div class="drawer-content">
  <form id="profile-form" novalidate><fieldset ${state.busy || !state.profiles.length ? 'disabled' : ''}><label class="field"><span>Demo business profile</span><select name="business_profile_id" id="business-profile">${state.profiles.map(profile=>`<option value="${e(profile.id)}" ${profile.id===state.selectedProfile?'selected':''}>${e(profile.industry)} — ${e(profile.companyName)}</option>`).join('')}</select></label>
  <p class="field-note">Switching changes the workspace for everyone using this demo. Existing enquiries keep their original business. AI cannot choose this profile.</p></fieldset><button class="btn secondary" ${state.busy || state.selectedProfile===state.activeProfile ? 'disabled' : ''}>Switch business profile</button></form>
  <div class="settings-demo-section"><label class="checkbox-label"><input type="checkbox" id="record-actor" ${state.recordActor?'checked':''} ${state.demoApproval !== true || state.busy?'disabled':''}> Record the selected demo role on quotation edits</label><p class="field-note">${state.demoApproval === true ? 'Server status: demo approval is on.' : 'Not available on this server.'}</p></div>
  <p class="field-note settings-demo-section">Roles are simulated for this supervised demo. A project manager must approve each send.<br>Server: ${e(API_BASE_URL || 'same origin')}. Private keys stay on the server.</p></div></details>` : ''}</div>`;
}
async function health() {
  const token = loadId;
  try { await api.health(); state.connected = true; } catch { state.connected = false; }
  const el = document.querySelector('#connection'); if (el) el.innerHTML = connection();
  try {
    const settings = await api.settings(); if (token !== loadId) return; state.companyName = settings.companyName;
    state.activeProfile = settings.business_profile_id;
    state.profileLabel = ({ printing: 'Printing', cleaning: 'Cleaning', repair: 'Repair' })[state.activeProfile] || '';
    const name = document.querySelector('#company-name'); if (name) name.textContent = state.companyName;
    const label = document.querySelector('#profile-label'); if (label) label.textContent = state.profileLabel;
  } catch { /* Connection errors are displayed by the page's own request. */ }
}
async function loadRoute(route) {
  const token = ++loadId; clearUndo(); state.detailTab = 'quote'; state.checkedPoints = []; state.questionChoices = [];
    state.route = route; state.loading = true; state.error = null; state.notice = ''; state.noticeKind = 'info'; state.dirty = false;
  state.settingsDirty = false; state.clientDirty = false; revokePDF();
  state.assignmentTargets = {}; state.suggestionValues = {}; state.selectedChanges = []; state.suggestionDirty = false; state.finalReview = null; state.suggestions = []; state.reviewed = false; state.conversation = []; state.analysis = null; state.composer = ''; state.messageRequest = null; state.messageHold = false; state.profiles = []; state.detail = null; state.quote = null; state.form = null; state.client = null; state.settings = null; state.hold = false; state.holdBaseline = []; state.expanded = {};
  render(); health();
  try {
    if (route === '/settings') {
      const profiles = await api.profiles(); if (token !== loadId) return;
      state.profiles = profiles.items; state.activeProfile = profiles.active_business_profile_id;
      state.selectedProfile = state.activeProfile;
      const profile = state.profiles.find(item => item.id === state.activeProfile);
      if (!profile) throw Error('The active business profile could not be loaded. Refresh to try again.');
      state.settings = { ...profile, business_profile_id: profile.id };
      state.savedSettings = settingsPatch();
      try { state.demoApproval = (await api.demoCapabilities()).demoApprovalEnabled === true; } catch { state.demoApproval = null; }
      if (token !== loadId) return;
      state.companyName = profile.companyName; state.profileLabel = profile.industry;
    } else if (/^\/enquiries\/[a-fA-F0-9-]{32,36}$/.test(route)) {
      const id = route.split('/')[2];
      const [d, q] = await Promise.allSettled([api.enquiry(id), api.quotation(id)]);
      if (token !== loadId) return;
      if (d.status === 'rejected') throw d.reason;
      state.detail = d.value;
      if (q.status === 'fulfilled') setQuote(q.value);
      else if (q.reason.status !== 404) throw q.reason;
      await loadConversation(id); if (token !== loadId) return;
      state.detailTab = initialDetailTab(state.quote, state.detail);
      syncHold();
    } else {
      if (route !== '/') { state.route = '/'; history.replaceState(null, '', '#/'); }
      const [page, assignments] = await Promise.all([api.enquiries(state.offset, state.limit), api.assignments()]); if (token !== loadId) return; state.items = page.items; state.assignments = assignments.items;
      const rows = [];
      // Bound read-only enrichment to five enquiries at a time; no AI requests.
      for (let i = 0; i < page.items.length; i += 5) {
        const batch = await Promise.all(page.items.slice(i,i+5).map(async item => {
          const [q,d] = await Promise.allSettled([api.quotation(item.id), api.enquiry(item.id)]);
          return enquiryRow(item, q.status === 'fulfilled' ? q.value : null, d.status === 'fulfilled' ? d.value : null, assignments.items, q.status === 'rejected' && q.reason.status !== 404 || d.status === 'rejected');
        }));
        if (token !== loadId) return; rows.push(...batch);
      }
      state.inboxRows = [...assignments.items.map(m => ({key:'sort-' + m.update_id, title: m.text.length > 40 ? m.text.slice(0,39) + '…' : m.text, name:'Unsorted message', source:'telegram', date:m.received_at || m.created_at || m.history?.[0]?.timestamp, stage:'sort', text:'Which enquiry is this for?', message:m, signature:String(m.update_id)})), ...rows];
      try { state.inboxClosed = JSON.parse(readSession(closedKey(), '{}')); } catch { state.inboxClosed = {}; }
      if (!state.inboxClosed || typeof state.inboxClosed !== 'object' || Array.isArray(state.inboxClosed)) state.inboxClosed = {};
      for (const row of state.inboxRows) if (state.inboxClosed[row.key] && state.inboxClosed[row.key].signature !== row.signature) delete state.inboxClosed[row.key];
      saveClosed();
    }
  } catch (error) { if (token === loadId) showError(error); }
  if (token !== loadId) return;
  state.loading = false; render();
  document.querySelector('#main').focus({ preventScroll: true });
  window.scrollTo(0, 0);
}
function setQuote(quote) { state.reviewed = false; state.quote = quote; state.form = editorForm(quote); state.dirty = false; }
function holdKey() { return 'qf-delivery-hold-' + state.quote?.id; }
function syncHold() {
  const saved = readSession(holdKey());
  if (saved) {
    state.hold = true;
    try { state.holdBaseline = JSON.parse(saved).baseline || []; } catch { state.holdBaseline = []; }
  }
  const attempts = state.detail?.delivery_attempts.filter(a => sameId(a.quotation_id, state.quote?.id)) || [];
  if (state.hold && deliveryHoldResolved(state.holdBaseline, attempts)) setHold(false);
}
function setHold(value) {
  state.hold = value;
  if (value) state.holdBaseline = (state.detail?.delivery_attempts || []).map(a => a.attempt_id);
  writeSession(holdKey(), value ? JSON.stringify({ baseline: state.holdBaseline }) : '');
}
function ask({ title, content, confirm = 'Continue', danger = false, approval = false, alternate = '' }) {
  return new Promise(resolve => {
    const previousFocus = document.activeElement;
    const dialog = document.createElement('dialog'); dialog.className = 'confirm-dialog'; dialog.setAttribute('aria-labelledby', 'dialog-title');
    const alternateButton = alternate ? `<button type="button" class="btn secondary" data-action="dialog-alternate" data-alternate>${e(alternate)}</button>` : '';
    dialog.innerHTML = `<form method="dialog" novalidate><div class="dialog-icon">${icon(approval ? 'send' : 'alert')}</div><h2 id="dialog-title">${e(title)}</h2>${content}${approval ? '<label class="checkbox-label approval-check"><input type="checkbox" id="confirm-approval" required /> I checked this PDF and approve sending it to this Telegram chat.</label>' : ''}<div class="dialog-actions"><button type="button" class="btn secondary" data-cancel>Cancel</button>${alternateButton}<button type="submit" class="btn ${danger ? 'danger' : 'primary'}" ${approval ? 'disabled' : ''}>${e(confirm)}</button></div></form>`;
    document.body.append(dialog);
    const finish = value => { dialog.close(); dialog.remove(); if (previousFocus?.isConnected) previousFocus.focus(); resolve(value); };
    dialog.querySelector('[data-cancel]').onclick = () => finish(false);
    if (alternate) dialog.querySelector('[data-alternate]').onclick = () => finish('alternate');
    dialog.addEventListener('cancel', event => { event.preventDefault(); finish(false); });
    dialog.querySelector('form').onsubmit = event => { event.preventDefault(); finish(true); };
    if (approval) dialog.querySelector('#confirm-approval').onchange = event => { dialog.querySelector('[type="submit"]').disabled = !event.target.checked; };
    dialog.showModal();
    dialog.querySelector(approval ? '#confirm-approval' : '[data-cancel]').focus();
  });
}
async function discardEdits() { return !hasEdits() || ask({ title: 'Leave unsaved changes?', content: '<p>Your changes haven’t been saved. Leave this page and discard them?</p>', confirm: 'Discard changes', danger: true }); }
async function navigate(route) { if (state.busy || route === state.route || !(await discardEdits())) return; state.dirty = state.settingsDirty = state.clientDirty = false; location.hash = route; }
async function task(work) {
    if (state.busy) return; state.busy = true; state.error = null; state.notice = ''; state.noticeKind = 'info'; render();
  try { await work(); } catch (error) { showError(error); } finally { state.busy = false; render(); if (state.error) root.querySelector('[aria-invalid="true"]')?.focus(); }
}
function captureQuote(form) {
  const data = new FormData(form);
  state.form.client = { name: data.get('clientName') || '', address: data.get('clientAddress') || '' };
  state.form.issueDate = data.get('issueDate'); state.form.validity = data.get('validity'); state.form.notes = data.get('notes') || '';
  state.form.items = state.form.items.map((item, i) => ({ unit: data.get(`item-unit-${i}`) || '', notes: data.get(`item-notes-${i}`) || '', description: data.get(`item-description-${i}`) || '', quantity: data.get(`item-quantity-${i}`) || '', unitPrice: state.role === 'pm' ? (data.get(`item-price-${i}`) || '') : item.unitPrice }));
}
async function refreshDetail() {
  const [detail, quote] = await Promise.all([api.enquiry(state.detail.id), api.quotation(state.detail.id)]);
  state.detail = detail; setQuote(quote); syncHold();
}
async function loadSavedPreview(expectedHash) {
  const result = await api.pdf(state.quote.id, state.quote.version);
  if (result.version !== state.quote.version) throw Error('The quote changed. Refresh it before previewing again.');
  if (expectedHash) { const bytes = await crypto.subtle.digest('SHA-256', await result.blob.arrayBuffer()); const hash = Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join(''); if (hash !== expectedHash) throw Error('The saved PDF no longer matches this review. Refresh before sending.'); }
  revokePDF(); state.pdfPages = await loadPDF(result.blob);
  state.pdfURL = URL.createObjectURL(result.blob); state.previewVersion = result.version;
  state.detailTab = 'preview'; state.focusPreview = true;
}
function saveQuoteAndPreview(preview) {
  if (!state.quote || !editable(state.quote) || state.busy) return;
  const form = document.querySelector('#quote-form');
  if (state.dirty && form) captureQuote(form);
  const patch = state.dirty ? quotePatch(state.form, state.quote.version) : null;
  if (patch && state.reviewed) patch.reviewedMessageIds = state.detail.messages.map(m => m.update_id);
  if (!patch && !preview) return;
  return task(async () => {
    if (patch) {
      setQuote(await api.saveQuote(state.quote.id, patch, state.role, state.recordActor));
      revokePDF();
      state.notice = 'Your draft is saved.';
    }
    // Keep the successfully saved version even if fetching/rendering its PDF fails.
    if (preview) { await loadSavedPreview(); state.notice = 'Preview matches the saved quotation. Only a Manager can approve sending.'; }
    if (patch) {
      try { state.detail = await api.enquiry(state.detail.id); }
      catch { state.notice += ' We couldn’t refresh activity. Your saved quote is safe; refresh to check the latest updates.'; }
    }
  });
}
function focusField(field) {
  if (field === 'items' && !state.form.items.length) { actions['add-item'](); field = 'item-description-0'; }
  const target = field === 'missing-review' ? document.querySelector('#missing-review') : document.querySelector(`[name="${field}"]`);
  if (!target) return;
  for (let parent = target.parentElement; parent; parent = parent.parentElement) {
    if (parent.tagName === 'DETAILS') parent.open = true;
  }
  target.focus({ preventScroll: true }); target.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
async function openDetailPreview() {
  state.detailTab = 'preview';
  if (pendingCustomerMessages(state.quote,state.detail).length && !state.reviewed && state.quote?.status !== 'sent' && !frozenDelivery()) { render(); return; }
  if (editable(state.quote) && !frozenDelivery()) return saveQuoteAndPreview(true);
  return task(async()=>{ await loadSavedPreview(); });
}
const actions = {
  'detail-tab': target => { const tab=target.dataset.tab; if (tab==='preview') return openDetailPreview(); state.detailTab=tab; render(); root.querySelector('#detail-tab-' + tab)?.focus({preventScroll:true}); },
  'detail-preview': () => openDetailPreview(),
  'submit-review': () => task(async () => {
    if (submissionIssues(state).length) throw Error(submissionIssues(state)[0]);
    setQuote(await api.submitReview(state.quote.id,state.quote.version,state.detail.messages.map(m=>String(m.update_id)),state.role));
    await refreshDetail(); state.notice='Submitted for Manager review. The saved details are in Manager To do.';
  }),
  'detail-save': () => saveQuoteAndPreview(false),
  'detail-save-prices': () => { if (state.role==='pm' && canSavePrices(state.form)) return saveQuoteAndPreview(true); },
  'detail-messages': () => { state.detailTab='messages'; render(); },
  'detail-quote': () => { state.detailTab='quote'; render(); },
  'detail-activity': () => { state.detailTab='activity'; state.expanded.delivery=true; state.expanded.activity=true; render(); },
  'confirm-messages': () => { if (!editable(state.quote)||frozenDelivery()) return; state.reviewed=true; state.dirty=true; return saveQuoteAndPreview(false); },
  'undo-check': target => { if (!editable(state.quote)||frozenDelivery()) return; const point=target.dataset.point; state.checkedPoints=state.checkedPoints.filter(p=>p!==point); if (!state.form.missingInformation.includes(point)) state.form.missingInformation.push(point); state.dirty=true; render(); },
  'detail-revision': () => { state.detailTab='quote'; render(); const field=root.querySelector('#fork-form [name="relationship"]'); if (field) { field.value='revision'; field.focus(); field.scrollIntoView({block:'center'}); } },
  'detail-additional': () => { state.detailTab='quote'; render(); const field=root.querySelector('#fork-form [name="relationship"]'); if (field) { field.value='additional'; field.focus(); field.scrollIntoView({block:'center'}); } },
  'add-questions': async () => {
    const questions=state.questionChoices.map(i=>state.analysis?.extraction?.clarificationSuggestions?.[i]).filter(Boolean);
    if (!questions.length) { state.notice='Select a suggested question first.'; render(); return; }
    if (state.composer && !(await ask({title:'Replace your message?',content:'<p>Replace the current unsent message with the selected questions?</p>',confirm:'Replace message'}))) return;
    state.composer=questions.map((q,i)=>`${i+1}. ${q}`).join('\n'); state.messageRequest=null; render(); root.querySelector('[name="message"]').focus();
  },
  'inbox-tab': target => { clearUndo(); state.inboxTab = target.dataset.tab; state.sortOpen = null; render(); },
  'inbox-clear': () => { state.inboxSource = state.inboxStage = ''; render(); },
  'inbox-all': () => { clearUndo(); state.inboxTab = 'all'; render(); },
  'inbox-sort': target => { state.sortOpen = state.sortOpen === target.dataset.key ? null : target.dataset.key; render(); },
  'inbox-open': target => navigate('/enquiries/' + target.dataset.key),
  'inbox-mock': () => ask({title:'Synthetic channel example', content:'<p>This row demonstrates the inbox layout only. Customer messaging and quotations for this channel are not connected. Sending is only available for Telegram.</p>', confirm:'Got it'}),
  'inbox-close': target => {
    const row = inboxRows().find(r => r.key === target.dataset.key);
    if (!row || !['sort','need-info'].includes(row.stage) || !(state.role === 'pm' || row.stage === 'sort' || row.stage === 'need-info')) return;
    clearUndo(); state.inboxClosed[row.key] = {role:state.role === 'pm' ? 'Manager' : 'Staff',at:new Date().toISOString(),signature:row.signature}; saveClosed();
    state.sortOpen = null; state.undo = {key:row.key,title:row.title,left:UNDO_SECONDS};
    undoTimer = setInterval(() => { if (!state.undo || --state.undo.left <= 0) clearUndo(); const toast = root.querySelector('.inbox-toast'); if (toast) { if (!state.undo) toast.remove(); else toast.querySelector('button').textContent = `Undo (${state.undo.left}s)`; } },1000); render();
  },
  'inbox-restore': target => { delete state.inboxClosed[target.dataset.key]; saveClosed(); clearUndo(); render(); },
  'inbox-undo': () => { if (state.undo) delete state.inboxClosed[state.undo.key]; saveClosed(); clearUndo(); render(); },
  'copy-enquiry-id': async target => {
    const id = target.dataset.enquiryId;
    try {
      await navigator.clipboard.writeText(id);
      target.textContent = 'Copied!';
      target.setAttribute('aria-label', 'Enquiry ID copied');
      let feedback = document.querySelector('#copy-id-feedback');
      if (!feedback) { feedback = document.createElement('p'); feedback.id = 'copy-id-feedback'; feedback.className = 'sr-only'; feedback.setAttribute('role', 'status'); root.append(feedback); }
      feedback.textContent = 'Copied enquiry ID: ' + id;
    } catch {
      showError(Error('Copy was blocked by your browser. Enquiry ID: ' + id));
      render();
    }
  },
  analyze: () => task(async () => { state.analysis = await api.analysis(state.detail.id, state.role); if (state.quote) state.suggestions = (await api.suggestions(state.quote.id)).items; state.notice = 'Analysis updated. Review suggestions before use.'; }),
  'use-question': async el => { if (state.composer && !(await ask({title: 'Replace your message?', content: '<p>Replace the current unsent message with this suggestion?</p>', confirm: 'Replace message'}))) return; state.composer = state.analysis.extraction.clarificationSuggestions[Number(el.dataset.index)]; state.messageRequest = null; render(); document.querySelector('[name="message"]').focus(); },
  inbox: () => navigate('/'),
  refresh: async () => { if (state.busy || !(await discardEdits())) return; await loadRoute(state.route); },
  previous: async () => { state.offset = Math.max(0, state.offset - state.limit); await loadRoute('/'); },
  next: async () => { state.offset += state.limit; await loadRoute('/'); },
  filter: el => { state.filter = el.dataset.filter; render(); }, 'clear-filters': () => { state.filter = 'all'; state.search = ''; render(); },
  'draft-ai': () => createDraft(false), 'draft-manual': () => createDraft(true),
  'fix-field': el => focusField(el.dataset.field),
  'fix-details': () => { const issue = preparationIssues(state.form, undefined, state.role)[0] || guidance().issues[0]; if (issue) focusField(issue.field); },
  'save-preview': () => openDetailPreview(),
  'pdf-previous': () => { if (state.pdfPage > 1) { state.pdfPage--; render(); } },
  'pdf-next': () => { if (state.pdfPage < state.pdfPages) { state.pdfPage++; render(); } },
  'add-item': () => { if (!editable(state.quote) || state.busy || state.form.items.length >= 100) return; state.form.items.push({ description: '', quantity: '', unit: '', notes: '', unitPrice: '' }); state.dirty = true; render(); },
  'remove-item': el => { if (!editable(state.quote) || state.busy) return; state.form.items.splice(Number(el.dataset.index), 1); state.dirty = true; render(); },
  'dismiss-missing': async el => {
    if (!editable(state.quote) || state.busy) return; const i = Number(el.dataset.index);
    if (await ask({ title: 'Mark this detail as checked?', content: `<p>${e(state.form.missingInformation[i])}</p><p>Confirm that it’s resolved in the quote, or that you reviewed it and decided it isn’t needed.</p>`, confirm: 'Mark checked' })) { state.checkedPoints.push(state.form.missingInformation[i]); state.form.missingInformation.splice(i, 1); state.dirty = true; render(); }
  },
  preview: () => task(async () => {
    if (!state.quote || state.dirty) return;
    await loadSavedPreview();
  }),
  'back-edit': () => { if (state.busy) return; const frozen = state.finalReview.delivery_mode === 'summary_only'; state.finalReview = null; if (frozen) state.notice = 'The accepted PDF is frozen. Finish summary delivery; new requirements need a revision after delivery.'; render(); },
  approve: () => task(async () => {
    if (state.role !== 'pm' || state.dirty || state.hold || !state.quote) return;
    const review = await api.review(state.quote.id, state.quote.version);
    await loadSavedPreview(review.pdf.sha256); state.finalReview = review; state.focusPreview = false;
  }),
  'final-send': async () => {
    if (!finalSendReady()) return;
    const summaryOnly=state.finalReview.delivery_mode==='summary_only';
    if (!(await ask({title:summaryOnly?'Send the saved summary?':'Send this quotation?',content:summaryOnly?'<p>The PDF was already accepted. Only the identical saved summary will be retried.</p>':'<p>The saved PDF and matching summary will be sent to the original Telegram chat. A sent quotation cannot be edited.</p>',confirm:'Send to Telegram'})) || !finalSendReady()) return;
    const retry = retryAttempt();
    await task(async () => {
      setHold(true);
      try {
        const result = await api.send(state.quote.id, state.quote.version, retry?.attempt_id);
        if (['sent', 'failed'].includes(result.status)) setHold(false);
        state.noticeKind = result.status === 'sent' ? 'info' : 'warning';
        state.notice = { sent: 'Your quote was accepted by Telegram. This doesn’t confirm it has been read.', failed: 'The quote wasn’t sent: Telegram rejected this attempt. Check the cause before approving another try.', unknown: 'We can’t confirm delivery. Check the original Telegram chat. Sending again is blocked.' }[result.status];
        state.finalReview = null; await refreshDetail(); await loadConversation(state.detail.id);
        if (result.status === 'failed' && frozenDelivery()) state.notice = 'Telegram accepted the PDF, but rejected its summary. The PDF is protected. Review and approve summary-only delivery after checking the cause.';
      } catch (error) {
        // All 4xx responses from this handler reject before upload; persisted
        // attempts still independently block duplicate/pending/unknown sends.
        if (error.status >= 400 && error.status < 500) setHold(false);
        state.finalReview = null;
        try { await refreshDetail(); } catch { /* Unavailable reconciliation keeps the hold. */ }
        throw error;
      }
    });
  },
};
function createDraft(manual) { return task(async () => { setQuote(await api.draft(state.detail.id, manual)); await refreshDetail(); state.notice = state.quote.draftMode === 'ai' ? 'Your draft is ready. Check the details and add your prices.' : 'Your manual draft is ready. Add the details from the customer’s message.'; }); }
root.addEventListener('click', async event => {
  const nav = event.target.closest('[data-nav]');
  if (nav) { if (event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return; event.preventDefault(); await navigate(nav.dataset.nav); return; }
  const target = event.target.closest('[data-action]');
  if (!target || target.disabled || state.loading || state.busy) return;
  const action = actions[target.dataset.action]; if (action) await action(target);
});
root.addEventListener('input', event => {
  if (event.target.tagName === 'TEXTAREA') growTextarea(event.target);
  if (event.target.closest('.assignment-form') && event.target.name === 'enquiry_id') state.assignmentTargets[event.target.closest('.assignment-form').dataset.update] = event.target.value;
  if (event.target.closest('.suggestion-form')) { state.suggestionDirty = true; if (event.target.name === 'selected') state.selectedChanges = [...root.querySelectorAll('.suggestion-form [name="selected"]:checked')].map(el => el.value); else state.suggestionValues[event.target.name] = event.target.value; }
  if (event.target.closest('#message-form')) { state.composer = event.target.value; state.messageRequest = null; }
  if (event.target.closest('#quote-form') && !state.busy) { captureQuote(event.target.form); state.dirty = true; state.notice = ''; root.querySelector('[data-page-notice]')?.remove(); updateEditorIndicators(); }
  if (event.target.id === 'search') { state.search = event.target.value; document.querySelector('#enquiry-results').innerHTML = inboxResults(); }
  if (event.target.closest('#settings-form') && state.role === 'pm' && !state.busy) { state.settings[event.target.name] = event.target.value; state.settingsDirty = settingsChanged(); document.querySelector('#settings-dirty').hidden = !state.settingsDirty; document.querySelector('#settings-form [type=submit]').disabled = !state.settingsDirty; }
  if (event.target.closest('#client-form')) { state.clientDirty = true; state.client[event.target.name] = event.target.value; }
});
root.addEventListener('toggle', event => {
  if (event.target.dataset?.disclosure) state.expanded[event.target.dataset.disclosure] = event.target.open;
}, true);
root.addEventListener('change', event => {
  if (event.target.name === 'question-choice') state.questionChoices=[...root.querySelectorAll('[name="question-choice"]:checked')].map(el=>Number(el.value));
  if (event.target.id === 'review-messages') { state.reviewed = event.target.checked; state.dirty = true; updateEditorIndicators(); }
  if (event.target.id === 'business-profile') { state.selectedProfile = event.target.value; render(); }
  if (event.target.id === 'inbox-source') { state.inboxSource = event.target.value; render(); }
  if (event.target.id === 'inbox-stage') { state.inboxStage = event.target.value; render(); }
  if (event.target.id === 'inbox-demo') { state.inboxDemo = event.target.checked; render(); }
  if (event.target.id === 'role') { clearUndo(); state.inboxTab = 'todo'; if (state.busy) { event.target.value = state.role; return; } state.finalReview = null; state.role = event.target.value; writeSession('qf-role', state.role); render(); }
  if (event.target.id === 'record-actor') { state.recordActor = event.target.checked; writeSession('qf-actor', String(state.recordActor)); }
});
root.addEventListener('submit', async event => {
  event.preventDefault(); if (state.busy) return; const form = event.target;
  if (form.matches('.suggestion-form')) {
    const data = new FormData(form), set = state.suggestions.find(s => s.id === form.dataset.set);
    const selected = data.getAll('selected'); if (!selected.length) { showError(Error('Select at least one change.')); render(); return; }
    const edits = Object.fromEntries(selected.map(id => { const c = structuredClone(set.changes.find(c => c.id === id)); delete c.id; if (c.type === 'UPDATE_FIELD') c.value = data.get(id + ':value'); else for (const key of Object.keys(c.data)) c.data[key] = data.get(id + ':' + key); return [id,c]; }));
    await task(async () => { setQuote(await api.applyChanges(state.quote.id, {version: state.quote.version, suggestion_set_id: set.id, selected, edits}, state.role)); revokePDF(); await loadConversation(state.detail.id); state.suggestionDirty = false; state.selectedChanges = []; state.suggestionValues = {}; state.notice = 'Changes applied to Quote'; });
  } else if (form.id === 'fork-form') {
    const data = new FormData(form), body = {version: state.quote.version, relationship: data.get('relationship')};
    if (body.relationship === 'additional') body.enquiry_id = data.get('enquiry_id').trim();
    await task(async () => { const quote = await api.fork(state.quote.id, body, state.role); if (sameId(quote.enquiryId, state.detail.id)) { setQuote(quote); revokePDF(); await loadConversation(state.detail.id); } else { state.dirty = false; location.hash = '/enquiries/' + quote.enquiryId; } state.notice = 'Created a draft. Historical sent PDFs are preserved; Manager must price and approve it.'; });
  } else if (form.id === 'message-form') {
    if (!state.composer.trim() || state.messageHold) return;
    const body = { text: state.composer.trim(), request_id: state.messageRequest || crypto.randomUUID() };
    state.messageRequest = body.request_id;
    await task(async () => {
      state.messageHold = true; writeSession('qf-message-hold-' + state.detail.id, body.request_id);
      const result = await api.message(state.detail.id, body, state.role);
      if (['sent', 'failed'].includes(result.status)) { state.messageHold = false; state.messageRequest = null; writeSession('qf-message-hold-' + state.detail.id, ''); }
      if (result.status === 'sent') state.composer = '';
      state.notice = result.status === 'sent' ? 'Telegram accepted your message.' : result.status === 'failed' ? 'Telegram rejected your message. Review the cause before a new send.' : 'Message delivery is unconfirmed. Check the original chat.';
      state.noticeKind = result.status === 'sent' ? 'info' : 'warning';
      await loadConversation(state.detail.id);
    });
  } else if (form.matches('.assignment-form')) {
    const body = { action: event.submitter?.value };
    if (body.action === 'assign') {
      const data = new FormData(form);
      body.enquiry_id = String(data.get('manual_enquiry_id') || data.get('enquiry_id') || '').trim();
      if (!body.enquiry_id) { showError(Error('Choose an existing enquiry below. For a separate order, click Create new enquiry.')); render(); return; }
    }
    await task(async () => { await api.assign(form.dataset.update, body, state.role); await loadRoute('/'); state.notice = 'Assignment saved. Original message and decision history retained.'; });
  } else if (form.id === 'quote-form') {
    await saveQuoteAndPreview(false);
  } else if (form.id === 'profile-form') {
    const identity = state.selectedProfile;
    if (state.role !== 'pm' || !identity || identity === state.activeProfile) return;
    let choice = true;
    if (state.settingsDirty) choice = await ask({title:'You have unsaved changes',content:'<p>Switching the business profile replaces the values on this page.</p>',confirm:'Save and switch',alternate:'Discard and switch'});
    if (!choice) {state.selectedProfile = state.activeProfile; render(); return;}
    await task(async () => {
      if (state.settingsDirty && choice === true) await saveBusinessSettings();
      await api.selectProfile(identity);
      state.items = []; state.offset = 0; state.filter = 'all'; state.search = '';
      state.client = null; state.detail = null; state.quote = null; state.form = null; revokePDF();
      state.dirty = state.settingsDirty = state.clientDirty = false;
      // Invalidate every in-flight request from the previous workspace.
      await loadRoute('/settings');
      state.notice = 'Business profile switched. New enquiries use this business; existing enquiries keep their original profile.';
    });
  } else if (form.id === 'settings-form') {
    if (state.role !== 'pm' || !state.settingsDirty) return;
    await task(saveBusinessSettings);
  } else if (form.id === 'load-client') {
    const id = new FormData(form).get('clientId').trim();
    if (state.clientDirty && !(await ask({ title: 'Discard client edits?', content: '<p>Loading another client will discard the current unsaved client changes.</p>', confirm: 'Discard and load', danger: true }))) return;
    await task(async () => { state.client = await api.client(id); state.clientDirty = false; });
  } else if (form.id === 'client-form') {
    const data = new FormData(form); const patch = { name: data.get('name'), address: data.get('address') };
    await task(async () => { state.client = await api.saveClient(state.client.id, patch); state.clientDirty = false; state.notice = 'Client details saved. Existing quotations retain their saved client snapshot.'; });
  }
});
window.addEventListener('beforeunload', event => { if (hasEdits() || state.busy) { event.preventDefault(); event.returnValue = ''; } });
document.querySelector('.skip-link').addEventListener('click', event => { event.preventDefault(); document.querySelector('#main').focus(); });
window.addEventListener('hashchange', async () => {
  const route = location.hash.slice(1) || '/'; if (route === state.route) return;
  if (state.busy || !(await discardEdits())) { history.replaceState(null, '', '#' + state.route); return; }
  await loadRoute(route);
});
loadRoute(location.hash.slice(1) || '/');

let detailPollBusy = false;
setInterval(async()=>{
  if (document.hidden || detailPollBusy || state.busy || state.loading || state.finalReview || !state.detail || !state.route.startsWith('/enquiries/')) return;
  detailPollBusy=true; const id=state.detail.id, token=loadId;
  try {
    const d=await api.enquiry(id);
    if (token!==loadId || state.busy || state.detail?.id!==id) return;
    const before=JSON.stringify(state.detail.messages.map(m=>m.update_id));
    const newMessages=before!==JSON.stringify(d.messages.map(m=>m.update_id));
    if (newMessages || state.analysis?.status==='running' || !analysisCurrent(state.analysis,state.quote,d,state.conversation,state.assignments)) {
      state.detail=d; if(newMessages) {state.reviewed=false; state.detailTab='messages'; revokePDF();}
      await loadConversation(id);
      if (token===loadId && !state.busy) {
        const active=document.activeElement, name=active?.getAttribute('name'), pos=active?.selectionStart;
        render(); const field=name?[...root.querySelectorAll('[name]')].find(el=>el.name===name):null;
        if (field) {field.focus();if(typeof pos==='number'&&field.setSelectionRange)field.setSelectionRange(pos,pos);}
      }
    }
  } catch { /* Keep saved data and edits; explicit Refresh still reports failures. */ }
  finally {detailPollBusy=false;}
},15000);

root.addEventListener('keydown',event=>{
  if (!event.target.matches('.detail-tabs [role="tab"]') || !['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
  const tabs=[...root.querySelectorAll('.detail-tabs [role="tab"]')], i=tabs.indexOf(event.target);
  const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(i+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
  event.preventDefault(); tabs[next].focus();
});
