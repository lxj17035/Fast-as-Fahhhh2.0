import { Api } from './api.js';
import { API_BASE_URL } from '../config.js';
import { loadPDF, paintPDF, releasePDF } from './pdf-viewer.js';
import { VALIDITIES, STATUS, escapeHTML as e, sameId, editable, quotePatch, editorForm, sendBlockers, deliveryHoldResolved } from './model.js';

const api = new Api(API_BASE_URL);
const root = document.querySelector('#app');
const readSession = (key, fallback = '') => { try { return sessionStorage.getItem(key) ?? fallback; } catch { return fallback; } };
const writeSession = (key, value) => { try { sessionStorage.setItem(key, value); } catch { /* Browser storage may be disabled. */ } };
const state = {
  route: '', role: readSession('qf-role', 'sales') === 'pm' ? 'pm' : 'sales',
  recordActor: readSession('qf-actor') === 'true', connected: null, busy: false, loading: false,
  error: null, notice: '', offset: 0, limit: 25, items: [], filter: 'all', search: '',
  detail: null, quote: null, form: null, dirty: false, previewVersion: null, pdfURL: null,
  settings: null, client: null, settingsDirty: false, clientDirty: false, hold: false, holdBaseline: [],
  pdfReady: false, pdfPage: 1, pdfPages: 0, companyName: 'Demo business workspace',
};
let loadId = 0;
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
function showError(error) { state.error = { message: error.message || 'Something went wrong.', fields: error.fields || {}, status: error.status }; }
function errorBox() {
  if (!state.error) return '';
  return `<div class="message error" role="alert">${icon('alert')}<div><strong>${e(state.error.message)}</strong>${Object.keys(state.error.fields).length ? `<ul>${Object.entries(state.error.fields).map(([key, value]) => `<li>${e(key)}: ${e(value)}</li>`).join('')}</ul>` : ''}${state.error.status === 409 && state.quote ? '<p>Your edits have been kept. Refresh the saved quotation before continuing.</p>' : ''}</div></div>`;
}
function connection() { return `<span class="connection ${state.connected === false ? 'offline' : ''}"><i></i>${state.connected === null ? 'Connecting…' : state.connected ? 'API connected' : 'API unavailable'}</span>`; }
function hasEdits() { return state.dirty || state.settingsDirty || state.clientDirty; }
function revokePDF() { if (state.pdfURL) URL.revokeObjectURL(state.pdfURL); state.pdfURL = null; state.previewVersion = null; state.pdfReady = false; state.pdfPage = 1; state.pdfPages = 0; releasePDF().catch(() => {}); }

function render() {
  const review = state.route.startsWith('/enquiries/');
  const settings = state.route === '/settings';
  document.title = `${settings ? 'Settings' : review ? 'Quotation review' : 'Inbox'} · QuoteFlow`;
  root.innerHTML = `<aside class="sidebar">
    <a href="#/" class="brand" data-nav="/" aria-label="QuoteFlow inbox"><span class="brand-symbol">${icon('inbox')}</span>QuoteFlow<span class="brand-dot">.</span></a>
    <div class="workspace"><span class="workspace-avatar">QF</span><div><strong id="company-name">${e(state.companyName)}</strong><span>Fictional business workspace</span></div></div>
    <p class="nav-label">WORKSPACE</p><nav aria-label="Main navigation"><a href="#/" data-nav="/" aria-label="Enquiry inbox" class="nav-item ${!settings ? 'active' : ''}" ${!settings ? 'aria-current="page"' : ''}>${icon('inbox')}<span>Enquiry inbox</span>${state.items.length ? `<span class="nav-count">${state.items.length}</span>` : ''}</a><a href="#/settings" data-nav="/settings" aria-label="Settings" class="nav-item ${settings ? 'active' : ''}" ${settings ? 'aria-current="page"' : ''}>${icon('settings')}<span>Settings</span></a></nav>
    <div class="sidebar-bottom"><div class="human-note">${icon('shield')}<strong>Assisted by AI.<br>Approved by you.</strong><p>You stay in control of pricing and every outgoing quotation.</p></div><div class="demo-label"><i></i>SYNTHETIC DATA DEMO</div><small>Orbyte Smart SME Challenge</small></div>
    </aside><div class="app-body"><header class="topbar"><div class="breadcrumb">Workspace <span>/</span> <strong>${settings ? 'Settings' : review ? 'Quotation review' : 'Enquiry inbox'}</strong></div><div class="topbar-right"><div id="connection">${connection()}</div><div class="role-control"><span class="avatar">${state.role === 'pm' ? 'PM' : 'S'}</span><label>Simulated role<select id="role" aria-label="Simulated role"><option value="sales" ${state.role === 'sales' ? 'selected' : ''}>Sales</option><option value="pm" ${state.role === 'pm' ? 'selected' : ''}>PM</option></select></label></div></div></header>
    <main id="main" tabindex="-1" ${state.loading ? 'aria-busy="true"' : ''}>${state.loading ? '<div class="loading"><span class="spinner"></span><h2>Opening your workspace</h2><p>Loading saved information from the API…</p></div>' : settings ? settingsPage() : review ? reviewPage() : inboxPage()}</main>
    <footer class="app-footer"><span>QuoteFlow <span>/</span> Enquiry to quotation, connected.</span><span>Supervised demo · Times in Kuala Lumpur</span></footer></div>`;
  if (!state.loading && review && state.form) updateEditorIndicators();
  const canvas = document.querySelector('#pdf-canvas');
  if (canvas) {
    state.pdfReady = false; updateEditorIndicators();
    paintPDF(canvas, state.pdfPage).then(painted => {
      if (painted) { state.pdfReady = true; updateEditorIndicators(); }
    }).catch(() => {
      if (canvas.isConnected) {
        state.pdfReady = false;
        document.querySelector('#pdf-render-status').textContent = 'PDF display failed. Reload the PDF or open it separately.';
        updateEditorIndicators();
      }
    });
  }
}
function statCard(title, value, symbol, color, note) { return `<div class="stat-card"><div class="stat-top"><span>${title}</span><span class="stat-icon ${color}">${icon(symbol)}</span></div><strong class="stat-number">${value.toString().padStart(2, '0')}</strong><p>${note}</p></div>`; }
function inboxPage() {
  return `<section class="page-heading"><div><p class="eyebrow">A LITTLE LESS ADMIN. A LOT MORE FLOW.</p><h1>Your enquiry inbox<span class="heading-dot">.</span></h1><p>Every conversation, one step closer to a quotation.</p></div>${button('Refresh inbox', 'refresh', { symbol: 'refresh' })}</section>${errorBox()}
    <section class="stats-grid" aria-label="Current page overview">${statCard('Enquiries on this page', state.items.length, 'inbox', 'slate', 'From your connected Telegram inbox')}${statCard('Ready for your attention', state.items.filter(item => item.status === 'needs_review').length, 'clock', 'amber', 'Draft, review, and prepare a reply')}${statCard('Quotations sent', state.items.filter(item => item.status === 'sent').length, 'check', 'green', 'Documents accepted by Telegram')}${statCard('Delivery needs a look', state.items.filter(item => ['failed', 'unknown'].includes(item.status)).length, 'alert', 'rose', 'Failed or unconfirmed outcomes')}</section>
    <section class="panel inbox-panel"><div class="panel-heading"><div><h2>All enquiries <span class="count-pill">${state.items.length}</span></h2><p>Your original messages, with a clear next step.</p></div><span class="channel-label">${icon('telegram')} Telegram</span></div>
    <div class="table-toolbar"><div class="tabs" role="group" aria-label="Filter loaded enquiries">${[['all', 'All enquiries'], ['needs_review', 'Needs review'], ['sent', 'Sent'], ['failed', 'Failed'], ['unknown', 'Unknown']].map(([value, title]) => `<button type="button" data-action="filter" data-filter="${value}" class="tab ${state.filter === value ? 'selected' : ''}" aria-pressed="${state.filter === value}">${title}</button>`).join('')}</div><label class="search">${icon('search')}<input id="search" type="search" placeholder="Search this page…" aria-label="Search loaded enquiries" value="${e(state.search)}" /></label></div>
    <div id="enquiry-results">${inboxResults()}</div><div class="table-footer"><span>Page ${Math.floor(state.offset / state.limit) + 1} · Search, counts, and filters apply to this page</span><div>${button('Previous', 'previous', { disabled: state.offset === 0 })}${button('Next', 'next', { disabled: state.items.length < state.limit })}</div></div></section>
    <div class="workflow-note"><span class="note-icon">${icon('spark')}</span><div><strong>A head start, with a human touch.</strong><p>AI drafts the requirements. You review the details, set the prices, and approve the send.</p></div><span class="workflow-path">Enquiry <span>→</span> Draft <span>→</span> Review <span>→</span> Send</span></div>`;
}
function inboxResults() {
  const list = state.items.filter(item => (state.filter === 'all' || item.status === state.filter) && `${item.original_text} ${item.id} ${item.telegram_chat_id}`.toLowerCase().includes(state.search.toLowerCase()));
  if (!list.length) return `<div class="empty-state"><span class="empty-icon">${icon(state.search ? 'search' : 'inbox')}</span><h3>${state.items.length ? 'No enquiries match this view' : state.error ? 'Your inbox is waiting to connect' : 'A clear inbox. A fresh start.'}</h3><p>${state.items.length ? 'Try another search or status filter on this page.' : state.error ? 'Start the existing backend, then refresh to load your enquiries.' : 'Send a fictional enquiry to your team’s Telegram bot. It will appear here after the backend receives it.'}</p>${state.items.length ? button('Clear filters', 'clear-filters') : button('Refresh inbox', 'refresh', { symbol: 'refresh' })}</div>`;
  return `<div class="table-scroll"><table class="enquiries-table"><thead><tr><th scope="col">ENQUIRY</th><th scope="col">SOURCE</th><th scope="col">RECEIVED</th><th scope="col">STATUS</th><th scope="col"><span class="sr-only">Open</span></th></tr></thead><tbody>${list.map(item => `<tr><td><a class="enquiry-link" href="#/enquiries/${e(item.id)}" data-nav="/enquiries/${e(item.id)}"><span class="enquiry-avatar">${icon('file')}</span><span><strong>${e(item.original_text.slice(0, 90))}${item.original_text.length > 90 ? '…' : ''}</strong><small>ENQ-${e(item.id.slice(0, 8).toUpperCase())}</small></span></a></td><td><span class="source-tag">${icon('telegram')} Telegram</span></td><td><span class="received-date">${e(dateTime(item.created_at, true))}</span><small>${e(dateTime(item.created_at).split(', ').slice(1).join(', '))}</small></td><td>${badge(item.status)}</td><td><a href="#/enquiries/${e(item.id)}" data-nav="/enquiries/${e(item.id)}" class="row-arrow" aria-label="Review enquiry ${e(item.id.slice(0, 8))}">${icon('arrow')}</a></td></tr>`).join('')}</tbody></table></div>`;
}
function reviewPage() {
  if (!state.detail) return `${button('Back to inbox', 'inbox', { symbol: 'back' })}${errorBox()}<div class="empty-state"><h2>Unable to open this enquiry</h2>${button('Try again', 'refresh')}</div>`;
  const d = state.detail, q = state.quote;
  return `<div class="review-top"><a href="#/" data-nav="/" class="back-link">${icon('back')} Back to inbox</a>${button('Refresh saved data', 'refresh', { symbol: 'refresh', disabled: state.busy })}</div><section class="page-heading review-heading"><div><p class="eyebrow">ENQUIRY / ${e(d.id.slice(0, 8).toUpperCase())}</p><h1>${q ? e(q.number) : 'Prepare a quotation'}<span class="heading-dot">.</span></h1><p>${q ? `Saved version ${q.version} · ${e(q.currency)} · ${e(dateOnly(q.issueDate))}` : 'Turn the original enquiry into a reviewed, priced document.'}</p></div>${badge(q?.status || d.status)}</section>
    ${errorBox()}${state.notice ? `<div class="message info" role="status">${icon('check')}<span>${e(state.notice)}</span></div>` : ''}<div class="review-grid"><aside class="context-column">
    <section class="panel context-panel"><div class="section-label">${icon('telegram')} ORIGINAL ENQUIRY</div><div class="message-meta"><strong>Telegram conversation</strong><span>${e(dateTime(d.created_at))}</span></div>${d.messages.map(message => `<blockquote>${e(message.text)}</blockquote>`).join('')}<div class="recipient"><span>Original recipient</span><code>${e(d.telegram_chat_id)}</code><small>Delivery always goes to this saved chat.</small></div></section>
    <section class="panel context-panel"><div class="section-label">${icon('spark')} DRAFT ASSISTANT</div>${q ? `<span class="badge ${q.draftMode === 'ai' ? 'green' : 'gray'}">${q.draftMode === 'ai' ? 'AI-assisted draft' : 'Manual draft'}</span><p class="summary">${e(q.summary || 'Review the original enquiry and prepare the quotation details.')}</p>${q.draftError ? `<p class="fallback-note">${e(q.draftError)}</p>` : ''}<div class="context-tip">${icon('shield')}<span>Prices are entered by you. Unknown details stay visible for review.</span></div>` : `<p>The original enquiry is safely stored. Create a draft to begin reviewing.</p>${button('Create AI draft', 'draft-ai', { symbol: 'spark', kind: 'primary', disabled: state.busy })}${button('Start manually', 'draft-manual', { disabled: state.busy })}<small>Unavailable AI produces a labelled manual draft.</small>`}</section></aside>
    <section class="panel editor-panel"><div class="panel-heading"><div><h2>Quotation details</h2><p>Review the facts. Make it yours.</p></div><span id="save-state" class="save-state"></span></div>${q ? editor() : '<div class="empty-state"><span class="empty-icon">' + icon('file') + '</span><h3>Your draft starts here</h3><p>Create an AI-assisted or manual draft from the enquiry on the left.</p></div>'}</section>
    <aside class="preview-column"><section class="panel preview-panel"><div class="panel-heading"><div><h2>Document preview</h2><p id="preview-status">Preview the saved PDF before approval</p></div>${icon('file')}</div>${pdfContent()}<div class="preview-actions">${button(state.pdfURL ? 'Refresh PDF' : 'Load saved PDF', 'preview', { symbol: 'refresh', disabled: !q || state.dirty || state.busy })}${state.pdfURL ? `<a class="text-link" href="${e(state.pdfURL)}" target="_blank" rel="noopener">Open PDF ↗</a>` : ''}</div></section>
    <section class="panel approval-panel"><div class="section-label">${icon('shield')} HUMAN APPROVAL</div><h3>${state.role === 'pm' ? 'Ready when you are.' : 'Prepared by Sales. Approved by PM.'}</h3><p>Send the reviewed PDF to the original Telegram conversation.</p><div id="approval-reasons"></div><button type="button" class="btn primary full-width" id="approve-button" data-action="approve" disabled>${icon('send')}<span>Approve and send</span></button><small>Explicit PM approval is required for every attempt.</small></section></aside></div>${deliveryHistory()}${activityHistory()}`;
}
function input(label, name, value, { type = 'text', max = 500, placeholder = '', extra = '' } = {}) { return `<label class="field"><span>${label}</span><input name="${name}" type="${type}" value="${e(value)}" maxlength="${max}" placeholder="${e(placeholder)}" ${extra} /></label>`; }
function validitySelect(value, name = 'validity') { return `<label class="field"><span>Valid for</span><select name="${name}">${Object.entries(VALIDITIES).map(([code, label]) => `<option value="${code}" ${code === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>`; }
function editor() {
  const q = state.quote, f = state.form, locked = !editable(q) || state.busy;
  return `<form id="quote-form"><fieldset ${locked ? 'disabled' : ''}><div class="editor-section"><div class="section-number">01 <span>CLIENT DETAILS</span></div><div class="field-grid">${input('Client name', 'clientName', f.client.name, { placeholder: 'Name on the quotation' })}<label class="field"><span>Client address <small>Optional</small></span><textarea name="clientAddress" rows="2" maxlength="500" placeholder="Leave blank if unknown">${e(f.client.address)}</textarea></label></div><p class="field-note">Client ID: <code>${e(q.client.id)}</code> · Details are copied into this quotation.</p></div>
    <div class="editor-section"><div class="section-number">02 <span>DATES & VALIDITY</span></div><div class="field-grid">${input('Issue date', 'issueDate', f.issueDate, { type: 'date' })}${validitySelect(f.validity)}</div><p class="expiry-line">${icon('clock')} Saved expiry: <strong>${e(dateOnly(q.expiryDate))}</strong><span>Updated by the backend on save</span></p></div>
    <div class="editor-section"><div class="section-number">03 <span>ITEMS & PRICING</span></div><p class="field-note pricing-note">${e(q.currency)} · Enter prices manually. A blank price stays unknown.</p><div class="item-head"><span>Description</span><span>Qty</span><span>Unit price</span><span></span></div><div id="item-rows">${f.items.map((item, i) => `<div class="item-row"><textarea name="item-description-${i}" rows="2" maxlength="2000" aria-label="Item ${i + 1} description" placeholder="Describe the requested item">${e(item.description)}</textarea><input name="item-quantity-${i}" inputmode="decimal" aria-label="Item ${i + 1} quantity" placeholder="—" value="${e(item.quantity)}" /><input name="item-price-${i}" inputmode="decimal" aria-label="Item ${i + 1} unit price" placeholder="—" value="${e(item.unitPrice)}" /><button type="button" class="icon-button" data-action="remove-item" data-index="${i}" aria-label="Remove item ${i + 1}">${icon('close')}</button></div>`).join('')}</div>${!f.items.length ? '<p class="no-items">No items yet. Add your first quotation line.</p>' : ''}${button('Add item', 'add-item', { symbol: 'plus', kind: 'text', disabled: locked || f.items.length >= 100 })}<div class="total-bar"><div><span id="total-label">Saved total</span><small id="total-note">Calculated by the backend</small></div><strong>${q.total === null ? 'Pending pricing' : `${e(q.currency)} ${e(q.total)}`}</strong></div></div>
    <div class="editor-section"><div class="section-number">04 <span>REVIEW & NOTES</span></div>${f.missingInformation.length ? `<div class="missing-info"><strong>${icon('alert')} Missing information</strong><p>Resolve each point in your edits, or explicitly dismiss it.</p>${f.missingInformation.map((item, i) => `<div class="missing-row"><span>${e(item)}</span><button type="button" class="text-link" data-action="dismiss-missing" data-index="${i}">Dismiss</button></div>`).join('')}</div>` : `<div class="review-clear">${icon('check')} No unresolved missing-information flags</div>`}<label class="field"><span>Quotation notes <small>Optional</small></span><textarea name="notes" rows="3" maxlength="4000" placeholder="Add reviewed terms or a note for the client…">${e(f.notes)}</textarea></label></div></fieldset>
    <div class="editor-bottom"><span>${locked && !state.busy ? 'This quotation is locked.' : state.recordActor ? `Edits attributed to simulated ${e(state.role.toUpperCase())}` : 'Edit actor: unspecified (demo attribution off)'}</span><button class="btn primary" type="submit" id="save-quote" ${locked || !state.dirty ? 'disabled' : ''}>${icon('check')} Save changes</button></div></form>`;
}
function pdfContent() {
  if (state.pdfURL) return `<div class="pdf-renderer"><canvas id="pdf-canvas" role="img" aria-label="Saved quotation PDF version ${state.previewVersion}, page ${state.pdfPage} of ${state.pdfPages}"></canvas></div><p class="pdf-render-status" id="pdf-render-status"></p><div class="pdf-pagination">${button('Previous page', 'pdf-previous', { disabled: state.pdfPage <= 1 })}<span>Page ${state.pdfPage} / ${state.pdfPages}</span>${button('Next page', 'pdf-next', { disabled: state.pdfPage >= state.pdfPages })}</div>`;
  return `<div class="pdf-empty"><div class="paper-art"><div class="paper-brand"></div><div class="paper-title"></div><div class="paper-line"></div><div class="paper-line short"></div><div class="paper-table"></div><div class="paper-line short right"></div><span>${icon('file')}</span></div><h3>Your quotation, on paper.</h3><p>Save your details, then load the actual PDF generated by the backend.</p></div>`;
}
function reasons() { return sendBlockers({ ...state, previewVersion: state.pdfReady ? state.previewVersion : null }); }
function retryAttempt() { return state.detail?.delivery_attempts.find(attempt => sameId(attempt.quotation_id, state.quote?.id) && attempt.can_retry); }
function updateEditorIndicators() {
  const el = document.querySelector('#save-state'); if (!el || !state.quote) return;
  el.textContent = state.busy ? 'Working…' : state.dirty ? 'Unsaved changes' : `Saved · v${state.quote.version}`;
  el.classList.toggle('unsaved', state.dirty);
  document.querySelector('#save-quote').disabled = state.busy || !state.dirty || !editable(state.quote);
  document.querySelector('[data-action="preview"]').disabled = state.busy || state.dirty;
  document.querySelector('#total-label').textContent = state.dirty ? 'Last saved total' : 'Saved total';
  document.querySelector('#total-note').textContent = state.dirty ? 'Save to recalculate your changes' : 'Calculated by the backend';
  document.querySelector('#preview-status').textContent = state.dirty ? 'Edits unsaved · save and refresh the PDF' : state.previewVersion === state.quote.version ? `Saved version ${state.previewVersion} · ready to review` : 'Preview the current saved version';
  const blockers = reasons();
  document.querySelector('#approval-reasons').innerHTML = blockers.length ? `<ul class="approval-list">${blockers.map(reason => `<li>${e(reason)}</li>`).join('')}</ul>` : `<div class="review-clear">${icon('check')} Current version saved and preview loaded</div>`;
  document.querySelector('#approve-button').disabled = !!blockers.length;
  document.querySelector('#approve-button span').textContent = retryAttempt() ? 'Review and retry' : 'Approve and send';
}
function deliveryHistory() {
  const attempts = state.detail.delivery_attempts;
  if (!attempts.length && !state.hold) return '';
  return `<section class="panel history-panel"><div class="panel-heading"><div><h2>Delivery history</h2><p>Each approval and its observed outcome are kept together.</p></div>${icon('send')}</div>${state.hold ? `<div class="message warning">${icon('alert')}<div><strong>Delivery is unconfirmed.</strong><p>Check the original Telegram chat and refresh this record. Sending is blocked while the previous request is unresolved.</p></div></div>` : ''}<div class="attempts">${attempts.map(a => `<div class="attempt"><div>${badge(a.status)}<strong>Version ${a.version}</strong><span>${e(dateTime(a.approved_at))}</span></div><p>Attempt <code>${e(a.attempt_id)}</code>${a.retry_of_attempt_id ? ` · Retry of <code>${e(a.retry_of_attempt_id)}</code>` : ''}</p>${a.provider_message_id ? `<p>Telegram reference: ${e(a.provider_message_id)} · Acceptance is not a read receipt.</p>` : ''}${a.safe_error_code ? `<p>Diagnostic: ${e(a.safe_error_code)}</p>` : ''}${a.requires_verification ? '<p class="warning-text">Check the original chat. Do not retry a pending or unknown outcome.</p>' : ''}</div>`).join('')}</div></section>`;
}
const actionLabels = { telegram_received: 'Telegram enquiry received', enquiry_created: 'Added to the inbox', quotation_draft_created: 'Quotation draft created', quotation_updated: 'Quotation changes saved', pm_approved: 'PM approved delivery', pdf_send_attempted: 'PDF delivery started', pdf_send_succeeded: 'Telegram accepted the PDF', pdf_send_failed: 'Telegram rejected delivery', delivery_unknown: 'Delivery requires verification' };
function activityHistory() {
  return `<section class="panel history-panel"><div class="panel-heading"><div><h2>Activity timeline</h2><p>A clear record of what happened, and when.</p></div><span class="count-pill">${state.detail.activity.length} events</span></div><ol class="timeline">${state.detail.activity.map(a => `<li><span class="timeline-dot ${a.result === 'failed' ? 'failed' : ''}">${icon(a.action.includes('send') ? 'send' : 'check')}</span><div><strong>${e(actionLabels[a.action] || a.action)}</strong><p>${e(a.actor_origin === 'simulated' ? `Simulated ${a.role?.toUpperCase() || 'actor'}` : a.actor_origin === 'system' ? 'System' : 'Actor unspecified')}${a.version ? ` · Version ${a.version}` : ''} · ${e(a.result)}</p>${a.safe_error_code ? `<small>${e(a.safe_error_code)}</small>` : ''}</div><time datetime="${e(a.timestamp)}">${e(dateTime(a.timestamp))}</time></li>`).join('') || '<li class="muted">No recorded activity yet.</li>'}</ol></section>`;
}
function settingsPage() {
  return `<section class="page-heading"><div><p class="eyebrow">THE DETAILS THAT MAKE IT YOURS</p><h1>Workspace settings<span class="heading-dot">.</span></h1><p>Your business context, ready for the next quotation.</p></div>${button('Refresh settings', 'refresh', { symbol: 'refresh', disabled: state.busy })}</section>${errorBox()}${state.notice ? `<div class="message info" role="status">${icon('check')} ${e(state.notice)}</div>` : ''}<div class="settings-grid">
    <section class="panel settings-panel"><div class="panel-heading"><div><h2>Business profile</h2><p>The starting point for new quotation snapshots.</p></div>${icon('settings')}</div>${state.settings ? `<form id="settings-form"><fieldset ${state.busy ? 'disabled' : ''}>${input('Company name', 'companyName', state.settings.companyName, { extra: 'required' })}<label class="field"><span>Company address</span><textarea name="companyAddress" rows="3" maxlength="500">${e(state.settings.companyAddress)}</textarea></label><div class="field-grid">${input('Currency code', 'currency', state.settings.currency, { max: 3, extra: 'required pattern="[A-Z]{3}" title="Three uppercase letters, e.g. MYR"' })}${validitySelect(state.settings.defaultValidity, 'defaultValidity')}</div><div class="timezone-note">${icon('clock')} Asia/Kuala_Lumpur <span>Fixed business timezone</span></div></fieldset><div class="form-bottom"><p>Existing quotations retain their saved company details.</p><button type="submit" class="btn primary" ${state.busy ? 'disabled' : ''}>Save settings</button></div></form>` : `<div class="empty-state"><p>Business settings could not be loaded.</p>${button('Try again', 'refresh')}</div>`}</section>
    <section class="panel settings-panel"><div class="panel-heading"><div><h2>Client details</h2><p>Load an existing client by their saved ID.</p></div>${icon('file')}</div><form id="load-client" class="client-lookup">${input('Client ID', 'clientId', state.client?.id || 'demo-client', { extra: 'required' })}<button class="btn secondary" ${state.busy ? 'disabled' : ''}>Load client</button></form><p class="field-note">Telegram clients use the client ID shown in their quotation. The API has no client-list endpoint.</p><div id="client-editor">${state.client ? `<form id="client-form"><fieldset ${state.busy ? 'disabled' : ''}>${input('Client name', 'name', state.client.name, { extra: 'required' })}<label class="field"><span>Client address <small>Optional</small></span><textarea name="address" rows="3" maxlength="500">${e(state.client.address)}</textarea></label></fieldset><div class="form-bottom"><p>Updates the stored client record.</p><button class="btn primary" ${state.busy ? 'disabled' : ''}>Save client</button></div></form>` : `<div class="client-placeholder">${icon('file')}<p>Load a client to review their stored details.</p></div>`}</div></section>
    <section class="panel demo-panel"><div><div class="section-label">${icon('shield')} SUPERVISED DEMO</div><h2>Role attribution</h2><p>The role selector is simulated identity. Sending requires PM and backend demo approval.</p><label class="checkbox-label"><input type="checkbox" id="record-actor" ${state.recordActor ? 'checked' : ''} /> Record the selected demo role on quotation edits</label><p class="field-note">Enable this only when <code>ENABLE_DEMO_APPROVAL=true</code> is configured in the backend. Otherwise, edits use the API’s unspecified actor.</p></div><div class="api-note">${icon('shield')}<span>Connected API<code>${e(API_BASE_URL)}</code><small>Provider keys stay on the Python server.</small></span></div></section></div>`;
}
async function health() {
  try { await api.health(); state.connected = true; } catch { state.connected = false; }
  const el = document.querySelector('#connection'); if (el) el.innerHTML = connection();
  try {
    const settings = await api.settings(); state.companyName = settings.companyName;
    const name = document.querySelector('#company-name'); if (name) name.textContent = state.companyName;
  } catch { /* Connection errors are displayed by the page's own request. */ }
}
async function loadRoute(route) {
  const token = ++loadId;
  state.route = route; state.loading = true; state.error = null; state.notice = ''; state.dirty = false;
  state.settingsDirty = false; state.clientDirty = false; revokePDF();
  state.detail = null; state.quote = null; state.form = null; state.client = null; state.settings = null; state.hold = false; state.holdBaseline = [];
  render(); health();
  try {
    if (route === '/settings') {
      const settings = await api.settings(); if (token !== loadId) return; state.settings = settings;
    } else if (/^\/enquiries\/[a-fA-F0-9-]{32,36}$/.test(route)) {
      const id = route.split('/')[2];
      const [d, q] = await Promise.allSettled([api.enquiry(id), api.quotation(id)]);
      if (token !== loadId) return;
      if (d.status === 'rejected') throw d.reason;
      state.detail = d.value;
      if (q.status === 'fulfilled') setQuote(q.value);
      else if (q.reason.status !== 404) throw q.reason;
      syncHold();
    } else {
      if (route !== '/') { state.route = '/'; history.replaceState(null, '', '#/'); }
      const page = await api.enquiries(state.offset, state.limit); if (token !== loadId) return; state.items = page.items;
    }
  } catch (error) { if (token === loadId) showError(error); }
  if (token !== loadId) return;
  state.loading = false; render();
  document.querySelector('#main').focus({ preventScroll: true });
  window.scrollTo(0, 0);
}
function setQuote(quote) { state.quote = quote; state.form = editorForm(quote); state.dirty = false; }
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
function ask({ title, content, confirm = 'Continue', danger = false, approval = false }) {
  return new Promise(resolve => {
    const dialog = document.createElement('dialog'); dialog.className = 'confirm-dialog'; dialog.setAttribute('aria-labelledby', 'dialog-title');
    dialog.innerHTML = `<form method="dialog"><div class="dialog-icon">${icon(approval ? 'send' : 'alert')}</div><h2 id="dialog-title">${e(title)}</h2>${content}${approval ? '<label class="checkbox-label approval-check"><input type="checkbox" id="confirm-approval" required /> I reviewed this saved PDF and approve sending it to this chat.</label>' : ''}<div class="dialog-actions"><button type="button" class="btn secondary" data-cancel>Cancel</button><button type="submit" class="btn ${danger ? 'danger' : 'primary'}" ${approval ? 'disabled' : ''}>${e(confirm)}</button></div></form>`;
    document.body.append(dialog);
    const finish = value => { dialog.close(); dialog.remove(); resolve(value); };
    dialog.querySelector('[data-cancel]').onclick = () => finish(false);
    dialog.addEventListener('cancel', event => { event.preventDefault(); finish(false); });
    dialog.querySelector('form').onsubmit = event => { event.preventDefault(); finish(true); };
    if (approval) dialog.querySelector('#confirm-approval').onchange = event => { dialog.querySelector('[type="submit"]').disabled = !event.target.checked; };
    dialog.showModal();
  });
}
async function discardEdits() { return !hasEdits() || ask({ title: 'Leave unsaved changes?', content: '<p>Your changes have not been saved to the backend. Leaving this view will discard them.</p>', confirm: 'Discard changes', danger: true }); }
async function navigate(route) { if (state.busy || route === state.route || !(await discardEdits())) return; state.dirty = state.settingsDirty = state.clientDirty = false; location.hash = route; }
async function task(work) {
  if (state.busy) return; state.busy = true; state.error = null; state.notice = ''; render();
  try { await work(); } catch (error) { showError(error); } finally { state.busy = false; render(); }
}
function captureQuote(form) {
  const data = new FormData(form);
  state.form.client = { name: data.get('clientName') || '', address: data.get('clientAddress') || '' };
  state.form.issueDate = data.get('issueDate'); state.form.validity = data.get('validity'); state.form.notes = data.get('notes') || '';
  state.form.items = state.form.items.map((_, i) => ({ description: data.get(`item-description-${i}`) || '', quantity: data.get(`item-quantity-${i}`) || '', unitPrice: data.get(`item-price-${i}`) || '' }));
}
async function refreshDetail() {
  const [detail, quote] = await Promise.all([api.enquiry(state.detail.id), api.quotation(state.detail.id)]);
  state.detail = detail; setQuote(quote); syncHold();
}
const actions = {
  inbox: () => navigate('/'),
  refresh: async () => { if (state.busy || !(await discardEdits())) return; await loadRoute(state.route); },
  previous: async () => { state.offset = Math.max(0, state.offset - state.limit); await loadRoute('/'); },
  next: async () => { state.offset += state.limit; await loadRoute('/'); },
  filter: el => { state.filter = el.dataset.filter; render(); }, 'clear-filters': () => { state.filter = 'all'; state.search = ''; render(); },
  'draft-ai': () => createDraft(false), 'draft-manual': () => createDraft(true),
  'pdf-previous': () => { if (state.pdfPage > 1) { state.pdfPage--; render(); } },
  'pdf-next': () => { if (state.pdfPage < state.pdfPages) { state.pdfPage++; render(); } },
  'add-item': () => { if (!editable(state.quote) || state.busy || state.form.items.length >= 100) return; state.form.items.push({ description: '', quantity: '', unitPrice: '' }); state.dirty = true; render(); },
  'remove-item': el => { if (!editable(state.quote) || state.busy) return; state.form.items.splice(Number(el.dataset.index), 1); state.dirty = true; render(); },
  'dismiss-missing': async el => {
    if (!editable(state.quote) || state.busy) return; const i = Number(el.dataset.index);
    if (await ask({ title: 'Dismiss this missing detail?', content: `<p>${e(state.form.missingInformation[i])}</p><p>Confirm that you resolved this point in the quotation, or reviewed it and decided it is unnecessary.</p>`, confirm: 'Dismiss detail' })) { state.form.missingInformation.splice(i, 1); state.dirty = true; render(); }
  },
  preview: () => task(async () => {
    if (!state.quote || state.dirty) return;
    const result = await api.pdf(state.quote.id, state.quote.version);
    if (result.version !== state.quote.version) throw Error('PDF version mismatch. Refresh the saved quotation.');
    revokePDF(); state.pdfPages = await loadPDF(result.blob);
    state.pdfURL = URL.createObjectURL(result.blob); state.previewVersion = result.version;
  }),
  approve: async () => {
    if (reasons().length) return; const retry = retryAttempt();
    const approved = await ask({ title: retry ? 'Approve another delivery attempt?' : 'Approve and send quotation?', content: `<p>You are approving <strong>${e(state.quote.number)}, version ${state.quote.version}</strong>.</p><div class="approval-summary"><span>Client<strong>${e(state.quote.client.name)}</strong></span><span>Total<strong>${e(state.quote.currency)} ${e(state.quote.total)}</strong></span><span>Original Telegram chat<strong>${e(state.detail.telegram_chat_id)}</strong></span></div>${retry ? `<p>This retries confirmed failed attempt <code>${e(retry.attempt_id)}</code>.</p>` : ''}`, confirm: retry ? 'Approve retry' : 'Approve and send', approval: true });
    if (!approved || reasons().length) return;
    await task(async () => {
      setHold(true);
      try {
        const result = await api.send(state.quote.id, state.quote.version, retry?.attempt_id);
        if (['sent', 'failed'].includes(result.status)) setHold(false);
        state.notice = { sent: 'Telegram accepted the saved PDF. This is not a read receipt.', failed: 'Telegram explicitly rejected the document. Review the cause before approving a retry.', unknown: 'Delivery is uncertain. Check the original chat. Resending is blocked.' }[result.status];
        await refreshDetail();
      } catch (error) {
        // All 4xx responses from this handler reject before upload; persisted
        // attempts still independently block duplicate/pending/unknown sends.
        if (error.status >= 400 && error.status < 500) setHold(false);
        try { await refreshDetail(); } catch { /* Unavailable reconciliation keeps the hold. */ }
        throw error;
      }
    });
  },
};
function createDraft(manual) { return task(async () => { setQuote(await api.draft(state.detail.id, manual)); await refreshDetail(); state.notice = state.quote.draftMode === 'ai' ? 'AI draft saved. Review the details and enter prices.' : 'Manual draft saved. Review the original message and add your items.'; }); }
root.addEventListener('click', async event => {
  const nav = event.target.closest('[data-nav]');
  if (nav) { if (event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return; event.preventDefault(); await navigate(nav.dataset.nav); return; }
  const target = event.target.closest('[data-action]');
  if (!target || target.disabled || state.loading || state.busy) return;
  const action = actions[target.dataset.action]; if (action) await action(target);
});
root.addEventListener('input', event => {
  if (event.target.closest('#quote-form') && !state.busy) { captureQuote(event.target.form); state.dirty = true; updateEditorIndicators(); }
  if (event.target.id === 'search') { state.search = event.target.value; document.querySelector('#enquiry-results').innerHTML = inboxResults(); }
  if (event.target.closest('#settings-form')) { state.settingsDirty = true; state.settings[event.target.name] = event.target.value; }
  if (event.target.closest('#client-form')) { state.clientDirty = true; state.client[event.target.name] = event.target.value; }
});
root.addEventListener('change', event => {
  if (event.target.id === 'role') { if (state.busy) { event.target.value = state.role; return; } state.role = event.target.value; writeSession('qf-role', state.role); render(); }
  if (event.target.id === 'record-actor') { state.recordActor = event.target.checked; writeSession('qf-actor', String(state.recordActor)); }
});
root.addEventListener('submit', async event => {
  event.preventDefault(); if (state.busy) return; const form = event.target;
  if (form.id === 'quote-form') {
    captureQuote(form); const patch = quotePatch(state.form, state.quote.version);
    await task(async () => {
      setQuote(await api.saveQuote(state.quote.id, patch, state.recordActor ? state.role : undefined)); revokePDF();
      state.notice = 'Changes saved. Load and review the new PDF version before approval.';
      try { state.detail = await api.enquiry(state.detail.id); } catch { state.notice += ' Activity could not refresh; refresh saved data to check it.'; }
    });
  } else if (form.id === 'settings-form') {
    const data = new FormData(form); const patch = Object.fromEntries(['companyName', 'companyAddress', 'currency', 'defaultValidity'].map(key => [key, data.get(key)]));
    await task(async () => { state.settings = await api.saveSettings(patch); state.companyName = state.settings.companyName; state.settingsDirty = false; state.notice = 'Business settings saved. Existing quotation snapshots are unchanged.'; });
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
