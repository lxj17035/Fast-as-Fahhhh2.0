import { Api } from './api.js';
import { API_BASE_URL } from '../config.js';
import { preparationIssues, reviewGuidance } from './experience.js';
import { loadPDF, paintPDF, releasePDF } from './pdf-viewer.js';
import { VALIDITIES, STATUS, escapeHTML as e, sameId, editable, quotePatch, editorForm, sendBlockers, deliveryHoldResolved, matchesInboxFilter } from './model.js';

const api = new Api(API_BASE_URL);
const root = document.querySelector('#app');
const readSession = (key, fallback = '') => { try { return sessionStorage.getItem(key) ?? fallback; } catch { return fallback; } };
const writeSession = (key, value) => { try { sessionStorage.setItem(key, value); } catch { /* Browser storage may be disabled. */ } };
const state = {
  route: '', role: readSession('qf-role', 'sales') === 'pm' ? 'pm' : 'sales',
  recordActor: readSession('qf-actor') === 'true', connected: null, busy: false, loading: false,
  error: null, notice: '', noticeKind: 'info', offset: 0, limit: 25, items: [], filter: 'all', search: '',
  detail: null, quote: null, form: null, dirty: false, previewVersion: null, pdfURL: null,
  settings: null, client: null, settingsDirty: false, clientDirty: false, hold: false, holdBaseline: [],
  profiles: [], activeProfile: '', selectedProfile: '', profileLabel: '',
  pdfReady: false, pdfPage: 1, pdfPages: 0, companyName: 'Demo business workspace', focusPreview: false, expanded: {},
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
function growTextarea(field) { field.style.height = 'auto'; field.style.height = field.scrollHeight + 2 + 'px'; }
function showError(error) { state.error = { message: error.message || 'Something went wrong.', fields: error.fields || {}, status: error.status }; }
function noticeBox() { return state.notice ? `<div data-page-notice class="message ${state.noticeKind}" role="status">${icon(state.noticeKind === 'warning' ? 'alert' : 'check')}<span>${e(state.notice)}</span></div>` : ''; }
function errorBox() {
  if (!state.error) return '';
  return `<div class="message error" role="alert">${icon('alert')}<div><strong>${e(state.error.message)}</strong>${Object.keys(state.error.fields).length ? `<ul>${Object.entries(state.error.fields).map(([key, value]) => `<li>${e(key)}: ${e(value)}</li>`).join('')}</ul>` : ''}${state.error.status === 409 && state.quote ? '<p>Your edits are still here. Someone may have updated the quote. Refresh it to review the latest saved version.</p>' : ''}</div></div>`;
}
function connection() { return `<span class="connection ${state.connected === false ? 'offline' : ''}"><i></i>${state.connected === null ? 'Connecting…' : state.connected ? 'Connected' : 'Connection lost'}</span>`; }
function hasEdits() { return state.dirty || state.settingsDirty || state.clientDirty; }
function revokePDF() { if (state.pdfURL) URL.revokeObjectURL(state.pdfURL); state.pdfURL = null; state.previewVersion = null; state.pdfReady = false; state.pdfPage = 1; state.pdfPages = 0; state.focusPreview = false; releasePDF().catch(() => {}); }

function render() {
  const review = state.route.startsWith('/enquiries/');
  const settings = state.route === '/settings';
  document.title = `${settings ? 'Settings' : review ? 'Quotation review' : 'Inbox'} · QuoteFlow`;
  root.innerHTML = `<aside class="sidebar">
    <a href="#/" class="brand" data-nav="/" aria-label="QuoteFlow inbox"><span class="brand-symbol">${icon('inbox')}</span>QuoteFlow<span class="brand-dot">.</span></a>
    <div class="workspace"><span class="workspace-avatar">QF</span><div><strong id="company-name">${e(state.companyName)}</strong><span id="profile-label">${e(state.profileLabel || 'Fictional business workspace')}</span></div></div>
    <p class="nav-label">WORKSPACE</p><nav aria-label="Main navigation"><a href="#/" data-nav="/" aria-label="Enquiry inbox" class="nav-item ${!settings ? 'active' : ''}" ${!settings ? 'aria-current="page"' : ''}>${icon('inbox')}<span>Enquiry inbox</span>${state.items.length ? `<span class="nav-count">${state.items.length}</span>` : ''}</a><a href="#/settings" data-nav="/settings" aria-label="Settings" class="nav-item ${settings ? 'active' : ''}" ${settings ? 'aria-current="page"' : ''}>${icon('settings')}<span>Settings</span></a></nav>
    <div class="sidebar-bottom"><div class="human-note">${icon('shield')}<strong>Assisted by AI.<br>Approved by you.</strong><p>You stay in control of pricing and every outgoing quotation.</p></div><div class="demo-label"><i></i>SYNTHETIC DATA DEMO</div><small>Orbyte Smart SME Challenge</small></div>
    </aside><div class="app-body"><header class="topbar"><div class="breadcrumb">Workspace <span>/</span> <strong>${settings ? 'Settings' : review ? 'Quotation review' : 'Enquiry inbox'}</strong></div><div class="topbar-right"><div id="connection">${connection()}</div><div class="role-control"><span class="avatar">${state.role === 'pm' ? 'PM' : 'S'}</span><label>Demo role<select id="role" aria-label="Simulated role"><option value="sales" ${state.role === 'sales' ? 'selected' : ''}>Sales</option><option value="pm" ${state.role === 'pm' ? 'selected' : ''}>PM</option></select></label></div></div></header>
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
function statCard(title, value, symbol, color, filter) { return `<button type="button" class="stat-card stat-button" data-action="filter" data-filter="${filter}" aria-pressed="${state.filter === filter}"><span class="stat-top"><span>${title}</span><span class="stat-icon ${color}">${icon(symbol)}</span></span><strong class="stat-number">${value}</strong><span class="stat-hint">View enquiries ${icon('arrow')}</span></button>`; }
function inboxPage() {
  return `<section class="page-heading"><div><h1>Enquiries<span class="heading-dot">.</span></h1><p>Open a message, check the details, and prepare a quote.</p></div>${button('Refresh', 'refresh', { symbol: 'refresh' })}</section>${errorBox()}
    ${state.items.length ? `<section class="stats-grid simple-stats" aria-label="Enquiries on this page">${statCard('To review', state.items.filter(item => item.status === 'needs_review').length, 'clock', 'amber', 'needs_review')}${statCard('Sent', state.items.filter(item => item.status === 'sent').length, 'check', 'green', 'sent')}${statCard('Needs checking', state.items.filter(item => ['failed', 'unknown'].includes(item.status)).length, 'alert', 'rose', 'attention')}</section>` : ''}
    <section class="panel inbox-panel"><div class="panel-heading"><div><h2>Customer messages <span class="count-pill">${state.items.length}</span></h2><p>Choose a message to get started.</p></div><span class="channel-label">${icon('telegram')} Telegram</span></div>
    <div class="table-toolbar"><div class="tabs" role="group" aria-label="Filter loaded enquiries">${[['all', 'All'], ['needs_review', 'To review'], ['sent', 'Sent'], ['attention', 'Needs checking']].map(([value, title]) => `<button type="button" data-action="filter" data-filter="${value}" class="tab ${state.filter === value ? 'selected' : ''}" aria-pressed="${state.filter === value}">${title}</button>`).join('')}</div><label class="search">${icon('search')}<input id="search" type="search" placeholder="Find a message…" aria-label="Search loaded enquiries" value="${e(state.search)}" /></label></div>
    <div id="enquiry-results">${inboxResults()}</div><div class="table-footer"><span>Page ${Math.floor(state.offset / state.limit) + 1} · Search, counts, and filters apply to this page</span><div>${button('Previous', 'previous', { disabled: state.offset === 0 })}${button('Next', 'next', { disabled: state.items.length < state.limit })}</div></div></section>
    <p class="inbox-help">${icon('shield')} You review the details and prices. A project manager approves every send.</p>`;
}
function inboxResults() {
  const list = state.items.filter(item => matchesInboxFilter(item, state.filter) && `${item.original_text} ${item.id} ${item.telegram_chat_id}`.toLowerCase().includes(state.search.toLowerCase()));
  if (!list.length) return `<div class="empty-state"><span class="empty-icon">${icon(state.search ? 'search' : 'inbox')}</span><h3>${state.items.length ? 'No matching messages' : state.error ? 'Let’s reconnect your inbox' : 'Your first enquiry starts in Telegram'}</h3><p>${state.items.length ? 'Try a different search or choose All to see the messages on this page.' : state.error ? 'Your saved messages will appear when the connection is restored.' : 'Send a fictional customer message to your connected Telegram bot, then refresh this page.'}</p>${state.items.length ? button('Show all messages', 'clear-filters') : button('Refresh messages', 'refresh', { symbol: 'refresh' })}${!state.items.length && !state.error ? '<details class="arrival-help"><summary>Nothing arriving?</summary><p>The Telegram bot needs to be connected before messages can appear here. Ask the teammate managing the bot to check the connection. No messages are sent from this page.</p></details>' : ''}</div>`;
  return `<div class="table-scroll"><table class="enquiries-table"><thead><tr><th scope="col">ENQUIRY</th><th scope="col">SOURCE</th><th scope="col">RECEIVED</th><th scope="col">STATUS</th><th scope="col"><span class="sr-only">Open</span></th></tr></thead><tbody>${list.map(item => `<tr><td><a class="enquiry-link" href="#/enquiries/${e(item.id)}" data-nav="/enquiries/${e(item.id)}"><span class="enquiry-avatar">${icon('file')}</span><span><strong>${e(item.original_text.slice(0, 90))}${item.original_text.length > 90 ? '…' : ''}</strong><small>Customer enquiry</small></span></a></td><td><span class="source-tag">${icon('telegram')} Telegram</span></td><td><span class="received-date">${e(dateTime(item.created_at, true))}</span><small>${e(dateTime(item.created_at).split(', ').slice(1).join(', '))}</small></td><td>${badge(item.status)}</td><td><a href="#/enquiries/${e(item.id)}" data-nav="/enquiries/${e(item.id)}" class="row-arrow" aria-label="Review enquiry ${e(item.id.slice(0, 8))}"><span>Review</span>${icon('arrow')}</a></td></tr>`).join('')}</tbody></table></div>`;
}
function disclosure(key, defaultOpen = false) {
  return `data-disclosure="${key}" ${(state.expanded[key] ?? defaultOpen) ? 'open' : ''}`;
}
function guidance() { return reviewGuidance(state); }
function progressMarkup() {
  const next = guidance();
  return `<ol class="review-progress" aria-label="Quotation progress">${['Details', 'Preview', 'Send'].map((label, i) => `<li data-step="${i + 1}" class="${next.kind === 'complete' || i + 1 < next.stage ? 'done' : i + 1 === next.stage ? 'current' : ''}" ${i + 1 === next.stage ? 'aria-current="step"' : ''}><span>${next.kind === 'complete' || i + 1 < next.stage ? icon('check') : i + 1}</span><strong>${label}</strong></li>`).join('')}</ol>`;
}
function nextStepMarkup() {
  const next = guidance();
  const actionable = next.action && !state.busy && !(next.action === 'approve' && reasons().length);
  return `<div class="next-step-heading">${icon(next.kind === 'complete' ? 'check' : next.kind === 'warning' ? 'alert' : 'arrow')}<span>${next.kind === 'complete' ? 'ALL DONE' : 'YOUR NEXT STEP'}</span></div><h3>${e(next.title)}</h3><p>${e(next.body)}</p>
    ${next.issues.length ? `<ul class="review-checklist">${next.issues.slice(0, 3).map(issue => `<li><button type="button" data-action="fix-field" data-field="${e(issue.field)}">${e(issue.message)} ${icon('arrow')}</button></li>`).join('')}</ul>${next.issues.length > 3 ? `<p class="field-note">${next.issues.length - 3} more details to check in the form.</p>` : ''}` : ''}
    ${next.kind !== 'complete' ? `<button type="button" id="next-step-button" class="btn primary full-width" data-action="${next.action || ''}" ${actionable ? '' : 'disabled'}>${next.action === 'approve' ? icon('send') : icon('arrow')} ${e(next.label || 'Please wait')}</button>` : '<p class="field-note">Telegram acceptance does not confirm the customer has read it.</p>'}`;
}
function reviewPage() {
  if (!state.detail) return `${button('Back to enquiries', 'inbox', { symbol: 'back' })}${errorBox()}<div class="empty-state"><h2>We couldn’t open this enquiry</h2>${button('Try again', 'refresh')}</div>`;
  const d = state.detail, q = state.quote;
  const customer = q?.client.name.trim();
  return `<div class="review-top"><a href="#/" data-nav="/" class="back-link">${icon('back')} All enquiries</a>${button('Refresh', 'refresh', { symbol: 'refresh', disabled: state.busy })}</div>
    <section class="page-heading review-heading"><div><h1>${customer ? `Quote for ${e(customer.slice(0, 70))}` : 'Prepare a quote'}</h1><p>${q ? `${e(q.number)} · ${e(q.currency)}` : 'Start with the customer’s message below.'}</p></div>${badge(q?.status || d.status)}</section>
    <div id="review-progress">${progressMarkup()}</div>${errorBox()}${noticeBox()}
    <section class="panel approval-panel next-step-panel" data-kind="${guidance().kind}" aria-label="Next step"><div id="next-step-content">${nextStepMarkup()}</div></section><div class="review-grid simple-review"><div class="review-main">
      <details class="panel customer-request" ${disclosure('message', true)}><summary><span>${icon('telegram')} Customer message</span><small>${e(dateTime(d.created_at))}</small></summary><div class="request-content">${d.messages.map(message => `<blockquote>${e(message.text)}</blockquote>`).join('')}
        ${q ? `<div class="draft-caption">${icon(q.draftMode === 'ai' ? 'spark' : 'file')}<span>${q.draftMode === 'ai' ? 'AI prepared this draft. Check it against the message.' : 'Manual draft. Add the details from this message.'}</span></div><details class="quiet-details" ${disclosure('draft')}><summary>Draft summary${q.draftError ? ' and fallback information' : ''}</summary><p class="summary">${e(q.summary || 'Use the original message to complete the quote.')}</p>${q.draftError ? `<p class="fallback-note">${e(q.draftError)}</p>` : ''}</details>` : `<div class="draft-start"><p>We’ll prepare a draft from this message. You’ll add prices and check it before sending.</p>${button('Prepare draft', 'draft-ai', { symbol: 'spark', kind: 'primary', disabled: state.busy })}${button('Write it myself', 'draft-manual', { disabled: state.busy })}</div>`}
      </div></details>
      <section class="panel editor-panel"><div class="panel-heading"><div><h2>Quote details</h2><p>Check the customer and add your prices.</p></div><span id="save-state" class="save-state"></span></div>${q ? editor() : '<div class="empty-state"><span class="empty-icon">' + icon('file') + '</span><h3>Start with a draft</h3><p>Choose Prepare draft or Write it myself above.</p></div>'}</section>
      <details class="quiet-details references" ${disclosure('references')}><summary>More details</summary><dl><dt>Enquiry reference</dt><dd><code>${e(d.id)}</code></dd>${q ? `<dt>Client reference</dt><dd><code>${e(q.client.id)}</code></dd><dt>Saved version</dt><dd>${q.version}</dd>` : ''}<dt>Original Telegram chat</dt><dd><code>${e(d.telegram_chat_id)}</code></dd></dl><p>Delivery always goes to this original conversation.</p></details>
    </div><aside class="preview-column">
        <section class="panel preview-panel" id="preview-panel"><div class="panel-heading"><div><h2>Quote preview</h2><p id="preview-status">The document your customer will receive.</p></div>${icon('file')}</div>${pdfContent()}<div class="preview-actions">${button(state.pdfURL ? 'Refresh preview' : 'Preview quote', 'preview', { symbol: 'file', disabled: !q || state.dirty || state.busy })}${state.pdfURL ? `<a class="text-link" href="${e(state.pdfURL)}" target="_blank" rel="noopener">Open full PDF ↗</a>` : ''}</div></section>
    </aside></div>${deliveryHistory()}${activityHistory()}`;
}
function input(label, name, value, { type = 'text', max = 500, placeholder = '', extra = '' } = {}) { return `<label class="field"><span>${label}</span><input name="${name}" type="${type}" value="${e(value)}" maxlength="${max}" placeholder="${e(placeholder)}" ${extra} /></label>`; }
function validitySelect(value, name = 'validity') { return `<label class="field"><span>Valid for</span><select name="${name}">${Object.entries(VALIDITIES).map(([code, label]) => `<option value="${code}" ${code === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>`; }
function editor() {
  const q = state.quote, f = state.form, locked = !editable(q) || state.busy;
  return `<form id="quote-form" novalidate><fieldset ${locked ? 'disabled' : ''}>
    <div class="editor-section"><h3 class="form-section-title">Customer</h3><div class="field-grid">${input('Customer name', 'clientName', f.client.name, { placeholder: 'Name on the quotation' })}<label class="field"><span>Address <small>Optional</small></span><textarea style="resize: none" name="clientAddress" rows="2" maxlength="500" placeholder="Leave blank if unknown">${e(f.client.address)}</textarea></label></div></div>
    <div class="editor-section"><h3 class="form-section-title">Items & prices</h3><p class="field-note pricing-note">Prices in ${e(q.currency)}. Leave a price blank if you’re still checking it.</p>
      <div class="item-head"><span>Item description</span><span>Quantity</span><span>Unit price</span><span></span></div><div id="item-rows" tabindex="-1">${f.items.map((item, i) => `<div class="item-row"><textarea style="resize: none" name="item-description-${i}" rows="2" maxlength="2000" aria-label="Item ${i + 1} description" placeholder="What are you quoting for?">${e(item.description)}</textarea><input name="item-quantity-${i}" inputmode="decimal" aria-label="Item ${i + 1} quantity" placeholder="Qty" value="${e(item.quantity)}" /><input name="item-price-${i}" inputmode="decimal" aria-label="Item ${i + 1} unit price" placeholder="Price" value="${e(item.unitPrice)}" /><button type="button" class="icon-button" data-action="remove-item" data-index="${i}" aria-label="Remove item ${i + 1}">${icon('close')}</button></div>`).join('')}</div>
      ${!f.items.length ? '<p class="no-items">Add the first item to begin.</p>' : ''}${button('Add another item', 'add-item', { symbol: 'plus', kind: 'text', disabled: locked || f.items.length >= 100 })}
      <div class="total-bar"><div><span id="total-label">Saved total</span><small id="total-note">Valid through ${e(dateOnly(q.expiryDate))}</small></div><strong>${q.total === null ? 'Prices needed' : `${e(q.currency)} ${e(q.total)}`}</strong></div>
    </div>
    ${f.missingInformation.length ? `<div class="editor-section" id="missing-review" tabindex="-1"><div class="missing-info"><strong>${icon('alert')} Please check</strong><p>Confirm each point using the customer’s message. Mark it checked once it’s resolved or you’ve decided it isn’t needed.</p>${f.missingInformation.map((item, i) => `<div class="missing-row"><span>${e(item)}</span><button type="button" class="text-link" data-action="dismiss-missing" data-index="${i}">Mark checked</button></div>`).join('')}</div></div>` : ''}
    <details class="editor-options" ${disclosure('options')}><summary>Dates & notes <span>Optional changes</span></summary><div class="drawer-content"><div class="field-grid">${input('Issue date', 'issueDate', f.issueDate, { type: 'date' })}${validitySelect(f.validity)}</div><p class="field-note">The saved quote is valid through ${e(dateOnly(q.expiryDate))}. Save date changes to update this.</p><label class="field notes-field"><span>Notes for the customer <small>Optional</small></span><textarea style="resize: none" name="notes" rows="3" maxlength="4000" placeholder="Add any reviewed terms or a helpful note…">${e(f.notes)}</textarea></label></div></details>
    </fieldset><div class="editor-bottom"><span>${locked && !state.busy ? 'Protected after sending or while delivery is unconfirmed.' : 'Save a draft at any time. Preview before sending.'}</span><div class="editor-buttons"><button class="btn secondary" type="submit" id="save-quote" ${locked || !state.dirty ? 'disabled' : ''}>Save draft</button><button class="btn primary" type="button" id="save-preview" data-action="save-preview" ${locked ? 'disabled' : ''}>${icon('file')} ${state.dirty ? 'Save & preview' : 'Preview quote'}</button></div></div></form>`;
}
function pdfContent() {
  if (state.pdfURL) return `<div class="pdf-renderer"><canvas id="pdf-canvas" role="img" aria-label="Saved quotation PDF version ${state.previewVersion}, page ${state.pdfPage} of ${state.pdfPages}"></canvas></div><p class="pdf-render-status" id="pdf-render-status"></p><div class="pdf-pagination">${button('Previous page', 'pdf-previous', { disabled: state.pdfPage <= 1 })}<span>Page ${state.pdfPage} / ${state.pdfPages}</span>${button('Next page', 'pdf-next', { disabled: state.pdfPage >= state.pdfPages })}</div>`;
  return `<div class="pdf-empty"><div class="paper-art"><div class="paper-brand"></div><div class="paper-title"></div><div class="paper-line"></div><div class="paper-line short"></div><div class="paper-table"></div><div class="paper-line short right"></div><span>${icon('file')}</span></div><h3>Check it before you send.</h3><p>Save the quote, then preview the PDF your customer will receive.</p></div>`;
}
function reasons() { return sendBlockers({ ...state, previewVersion: state.pdfReady ? state.previewVersion : null }); }
function retryAttempt() { return state.detail?.delivery_attempts.find(attempt => sameId(attempt.quotation_id, state.quote?.id) && attempt.can_retry); }
function updateEditorIndicators() {
  const el = document.querySelector('#save-state'); if (!el || !state.quote) return;
  el.textContent = state.busy ? 'Working…' : state.dirty ? 'Not saved yet' : 'All changes saved';
  el.classList.toggle('unsaved', state.dirty);
  document.querySelector('#save-quote').disabled = state.busy || !state.dirty || !editable(state.quote);
  const savePreview = document.querySelector('#save-preview');
  savePreview.disabled = state.busy || !editable(state.quote);
  savePreview.innerHTML = icon('file') + ' ' + (state.dirty ? 'Save & preview' : 'Preview quote');
  document.querySelectorAll('[data-action="preview"]').forEach(button => { button.disabled = state.busy || state.dirty; });
  document.querySelector('#total-label').textContent = state.dirty ? 'Last saved total' : 'Saved total';
  document.querySelector('#total-note').textContent = state.dirty ? 'Save to update the total and dates' : `Valid through ${dateOnly(state.quote.expiryDate)}`;
  document.querySelector('#preview-status').textContent = state.dirty ? 'Save your changes for an updated preview.' : state.pdfReady && state.previewVersion === state.quote.version ? 'Matches your saved quote.' : state.pdfURL ? 'Preparing your preview…' : 'The document your customer will receive.';
  document.querySelector('#next-step-content').innerHTML = nextStepMarkup();
  document.querySelector('.next-step-panel').dataset.kind = guidance().kind;
  document.querySelector('#review-progress').innerHTML = progressMarkup();
}
function deliveryHistory() {
  const attempts = state.detail.delivery_attempts;
  if (!attempts.length && !state.hold) return '';
  return `<details class="panel history-panel simple-history" ${disclosure('delivery', true)}><summary>Delivery history <span>${attempts.length} ${attempts.length === 1 ? 'attempt' : 'attempts'}</span></summary>
    ${state.hold ? `<div class="message warning">${icon('alert')}<p>Check the original Telegram chat. We’re still waiting for a confirmed result, so sending again is blocked.</p></div>` : ''}
    <div class="attempts">${attempts.map(a => `<div class="attempt"><div>${badge(a.status)}<span>${e(dateTime(a.approved_at))}</span></div><p>${a.status === 'sent' ? 'Telegram accepted the quote. This does not confirm it has been read.' : a.status === 'failed' ? 'Telegram rejected this attempt. A PM can review and approve a new attempt when available.' : 'Check the original conversation before taking any further action.'}</p><details class="quiet-details"><summary>Technical reference</summary><p>Attempt <code>${e(a.attempt_id)}</code>${a.retry_of_attempt_id ? ` · Previous attempt <code>${e(a.retry_of_attempt_id)}</code>` : ''}</p><p>Saved version: ${a.version}${a.provider_message_id ? ` · Telegram reference: ${e(a.provider_message_id)}` : ''}</p>${a.safe_error_code ? `<p>Diagnostic: ${e(a.safe_error_code)}</p>` : ''}</details></div>`).join('')}</div></details>`;
}
const actionLabels = { telegram_received: 'Telegram enquiry received', enquiry_created: 'Added to the inbox', quotation_draft_created: 'Quotation draft created', quotation_updated: 'Quotation changes saved', pm_approved: 'PM approved delivery', pdf_send_attempted: 'PDF delivery started', pdf_send_succeeded: 'Telegram accepted the PDF', pdf_send_failed: 'Telegram rejected delivery', delivery_unknown: 'Delivery requires verification' };
function activityHistory() {
  return `<details class="panel history-panel simple-history" ${disclosure('activity')}><summary>Activity <span>${state.detail.activity.length} updates</span></summary><ol class="timeline">${state.detail.activity.map(a => `<li><span class="timeline-dot ${a.result === 'failed' ? 'failed' : ''}">${icon(a.action.includes('send') ? 'send' : 'check')}</span><div><strong>${e(actionLabels[a.action] || a.action)}</strong><p>${e(a.actor_origin === 'simulated' ? `${a.role?.toUpperCase() || 'Team member'} (demo role)` : a.actor_origin === 'system' ? 'System' : 'Actor not recorded')}</p></div><time datetime="${e(a.timestamp)}">${e(dateTime(a.timestamp))}</time></li>`).join('') || '<li class="muted">No updates recorded yet.</li>'}</ol></details>`;
}
function settingsPage() {
    return `<section class="page-heading"><div><h1>Business settings<span class="heading-dot">.</span></h1><p>Your company details and defaults for new quotes.</p></div>${button('Refresh', 'refresh', { symbol: 'refresh', disabled: state.busy })}</section>${errorBox()}${noticeBox()}
    <div class="settings-grid">
      <section class="panel settings-panel profile-panel"><div class="panel-heading"><div><h2>Demo business profile</h2><p>Choose the business for this workspace and new enquiries.</p></div>${icon('settings')}</div>
        <form id="profile-form" novalidate><fieldset ${state.busy || !state.profiles.length ? 'disabled' : ''}><label class="field"><span>Business profile</span><select name="business_profile_id" id="business-profile" aria-label="Business profile" aria-describedby="profile-help">${state.profiles.map(profile => `<option value="${e(profile.id)}" ${profile.id === state.selectedProfile ? 'selected' : ''}>${e(profile.industry)} — ${e(profile.companyName)}</option>`).join('')}</select></label><p id="profile-help" class="field-note">Active: <strong>${e(state.profileLabel || 'Unavailable')}</strong>. Switching changes the workspace for everyone using this demo. Existing enquiries stay with their original business. AI cannot choose this profile.</p></fieldset><div class="form-bottom"><p>Save your edits before switching, or discard them when asked.</p><button class="btn primary" ${state.busy || !state.profiles.length || state.selectedProfile === state.activeProfile ? 'disabled' : ''}>Switch business profile</button></div></form>
      </section>
      <section class="panel settings-panel"><div class="panel-heading"><div><h2>Your business</h2><p>These details appear on new quotations.</p></div>${icon('settings')}</div>
        ${state.settings ? `<form id="settings-form" novalidate><fieldset ${state.busy ? 'disabled' : ''}>
          ${input('Company name', 'companyName', state.settings.companyName, { extra: 'required' })}
          <label class="field"><span>Company address</span><textarea style="resize: none" name="companyAddress" rows="3" maxlength="500">${e(state.settings.companyAddress)}</textarea></label>
          <div class="field-grid">${input('Currency', 'currency', state.settings.currency, { max: 3, extra: 'required pattern="[A-Z]{3}" title="Three uppercase letters, e.g. MYR"' })}${validitySelect(state.settings.defaultValidity, 'defaultValidity')}</div>
          <p class="field-note">Dates use Kuala Lumpur time. You can change the validity on each quote.</p>
        </fieldset><div class="form-bottom"><p>Quotes you already saved keep their original details.</p><button type="submit" class="btn primary" ${state.busy ? 'disabled' : ''}>Save business details</button></div></form>` : `<div class="empty-state"><p>We couldn’t load your business details.</p>${button('Try again', 'refresh')}</div>`}
      </section>
      <div class="settings-aside"><section class="panel settings-explainer"><span class="note-icon">${icon('file')}</span><h2>Set up once. Review each quote.</h2><p>Your company details and usual validity are added to new drafts.</p><p>Check the customer’s name and address directly in their quotation. You can leave an unknown address blank.</p><div class="review-clear">${icon('shield')} Updating settings won’t change a sent quote.</div></section>
      <details class="panel settings-panel client-drawer" ${state.client ? 'open' : ''}><summary>Manage a saved client</summary><div class="drawer-content"><p class="field-note">For an existing client record. You can find its reference under More details in their quotation.</p>
        <form novalidate id="load-client" class="client-lookup">${input('Client reference', 'clientId', state.client?.id || (state.activeProfile === 'printing' ? 'demo-client' : 'demo-client-' + state.activeProfile), { extra: 'required' })}<button class="btn secondary" ${state.busy ? 'disabled' : ''}>Find client</button></form>
        <div id="client-editor">${state.client ? `<form id="client-form" novalidate><fieldset ${state.busy ? 'disabled' : ''}>${input('Client name', 'name', state.client.name, { extra: 'required' })}<label class="field"><span>Client address <small>Optional</small></span><textarea style="resize: none" name="address" rows="3" maxlength="500">${e(state.client.address)}</textarea></label></fieldset><div class="form-bottom"><p>Previously saved quotes keep their original client details.</p><button class="btn primary" ${state.busy ? 'disabled' : ''}>Save client</button></div></form>` : ''}</div>
      </div></details></div>
      <details class="panel demo-options"><summary>Demo and connection options</summary><div class="drawer-content"><p>Roles are simulated for this supervised demo. A project manager must approve each send.</p><label class="checkbox-label"><input type="checkbox" id="record-actor" ${state.recordActor ? 'checked' : ''} /> Record the selected demo role on quotation edits</label><p class="field-note">Use this only when your backend has <code>ENABLE_DEMO_APPROVAL=true</code>. Otherwise, edits are recorded without a named actor.</p><p class="field-note">Server: <code>${e(API_BASE_URL || 'same origin')}</code>. Private keys stay on the server.</p></div></details>
    </div>`;
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
  const token = ++loadId;
    state.route = route; state.loading = true; state.error = null; state.notice = ''; state.noticeKind = 'info'; state.dirty = false;
  state.settingsDirty = false; state.clientDirty = false; revokePDF();
  state.profiles = []; state.detail = null; state.quote = null; state.form = null; state.client = null; state.settings = null; state.hold = false; state.holdBaseline = []; state.expanded = {};
  render(); health();
  try {
    if (route === '/settings') {
      const profiles = await api.profiles(); if (token !== loadId) return;
      state.profiles = profiles.items; state.activeProfile = profiles.active_business_profile_id;
      state.selectedProfile = state.activeProfile;
      const profile = state.profiles.find(item => item.id === state.activeProfile);
      if (!profile) throw Error('The active business profile could not be loaded. Refresh to try again.');
      state.settings = { ...profile, business_profile_id: profile.id };
      state.companyName = profile.companyName; state.profileLabel = profile.industry;
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
    const previousFocus = document.activeElement;
    const dialog = document.createElement('dialog'); dialog.className = 'confirm-dialog'; dialog.setAttribute('aria-labelledby', 'dialog-title');
    dialog.innerHTML = `<form method="dialog" novalidate><div class="dialog-icon">${icon(approval ? 'send' : 'alert')}</div><h2 id="dialog-title">${e(title)}</h2>${content}${approval ? '<label class="checkbox-label approval-check"><input type="checkbox" id="confirm-approval" required /> I checked this PDF and approve sending it to this Telegram chat.</label>' : ''}<div class="dialog-actions"><button type="button" class="btn secondary" data-cancel>Cancel</button><button type="submit" class="btn ${danger ? 'danger' : 'primary'}" ${approval ? 'disabled' : ''}>${e(confirm)}</button></div></form>`;
    document.body.append(dialog);
    const finish = value => { dialog.close(); dialog.remove(); if (previousFocus?.isConnected) previousFocus.focus(); resolve(value); };
    dialog.querySelector('[data-cancel]').onclick = () => finish(false);
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
  state.form.items = state.form.items.map((_, i) => ({ description: data.get(`item-description-${i}`) || '', quantity: data.get(`item-quantity-${i}`) || '', unitPrice: data.get(`item-price-${i}`) || '' }));
}
async function refreshDetail() {
  const [detail, quote] = await Promise.all([api.enquiry(state.detail.id), api.quotation(state.detail.id)]);
  state.detail = detail; setQuote(quote); syncHold();
}
async function loadSavedPreview() {
  const result = await api.pdf(state.quote.id, state.quote.version);
  if (result.version !== state.quote.version) throw Error('The quote changed. Refresh it before previewing again.');
  revokePDF(); state.pdfPages = await loadPDF(result.blob);
  state.pdfURL = URL.createObjectURL(result.blob); state.previewVersion = result.version;
  state.focusPreview = true;
}
function saveQuoteAndPreview(preview) {
  if (!state.quote || !editable(state.quote) || state.busy) return;
  const form = document.querySelector('#quote-form');
  if (state.dirty && form) captureQuote(form);
  const patch = state.dirty ? quotePatch(state.form, state.quote.version) : null;
  if (!patch && !preview) return;
  return task(async () => {
    if (patch) {
      setQuote(await api.saveQuote(state.quote.id, patch, state.recordActor ? state.role : undefined));
      revokePDF();
      state.notice = 'Your draft is saved.';
    }
    // Keep the successfully saved version even if fetching/rendering its PDF fails.
    if (preview) { await loadSavedPreview(); state.notice = 'Check the PDF before approving or handing it to your project manager.'; }
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
const actions = {
  inbox: () => navigate('/'),
  refresh: async () => { if (state.busy || !(await discardEdits())) return; await loadRoute(state.route); },
  previous: async () => { state.offset = Math.max(0, state.offset - state.limit); await loadRoute('/'); },
  next: async () => { state.offset += state.limit; await loadRoute('/'); },
  filter: el => { state.filter = el.dataset.filter; render(); }, 'clear-filters': () => { state.filter = 'all'; state.search = ''; render(); },
  'draft-ai': () => createDraft(false), 'draft-manual': () => createDraft(true),
  'fix-field': el => focusField(el.dataset.field),
  'fix-details': () => { const issue = preparationIssues(state.form)[0] || guidance().issues[0]; if (issue) focusField(issue.field); },
  'save-preview': () => saveQuoteAndPreview(true),
  'pdf-previous': () => { if (state.pdfPage > 1) { state.pdfPage--; render(); } },
  'pdf-next': () => { if (state.pdfPage < state.pdfPages) { state.pdfPage++; render(); } },
  'add-item': () => { if (!editable(state.quote) || state.busy || state.form.items.length >= 100) return; state.form.items.push({ description: '', quantity: '', unitPrice: '' }); state.dirty = true; render(); },
  'remove-item': el => { if (!editable(state.quote) || state.busy) return; state.form.items.splice(Number(el.dataset.index), 1); state.dirty = true; render(); },
  'dismiss-missing': async el => {
    if (!editable(state.quote) || state.busy) return; const i = Number(el.dataset.index);
    if (await ask({ title: 'Mark this detail as checked?', content: `<p>${e(state.form.missingInformation[i])}</p><p>Confirm that it’s resolved in the quote, or that you reviewed it and decided it isn’t needed.</p>`, confirm: 'Mark checked' })) { state.form.missingInformation.splice(i, 1); state.dirty = true; render(); }
  },
  preview: () => task(async () => {
    if (!state.quote || state.dirty) return;
    await loadSavedPreview();
  }),
  approve: async () => {
    if (reasons().length) return; const retry = retryAttempt();
    const approved = await ask({ title: retry ? 'Approve sending this quote again?' : 'Send this quotation?', content: `<p>You’re approving <strong>${e(state.quote.number)}, version ${state.quote.version}</strong>.</p><div class="approval-summary"><span>Customer<strong>${e(state.quote.client.name)}</strong></span><span>Total<strong>${e(state.quote.currency)} ${e(state.quote.total)}</strong></span><span>Original Telegram chat<strong>${e(state.detail.telegram_chat_id)}</strong></span></div>${retry ? `<p>The last attempt was rejected. This starts a new attempt after your approval.</p><details class="quiet-details"><summary>Previous attempt reference</summary><code>${e(retry.attempt_id)}</code></details>` : ''}`, confirm: retry ? 'Approve & send again' : 'Approve & send', approval: true });
    if (!approved || reasons().length) return;
    await task(async () => {
      setHold(true);
      try {
        const result = await api.send(state.quote.id, state.quote.version, retry?.attempt_id);
        if (['sent', 'failed'].includes(result.status)) setHold(false);
        state.noticeKind = result.status === 'sent' ? 'info' : 'warning';
        state.notice = { sent: 'Your quote was accepted by Telegram. This doesn’t confirm it has been read.', failed: 'The quote wasn’t sent: Telegram rejected this attempt. Check the cause before approving another try.', unknown: 'We can’t confirm delivery. Check the original Telegram chat. Sending again is blocked.' }[result.status];
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
  if (event.target.closest('#quote-form') && !state.busy) { captureQuote(event.target.form); state.dirty = true; state.notice = ''; root.querySelector('[data-page-notice]')?.remove(); updateEditorIndicators(); }
  if (event.target.id === 'search') { state.search = event.target.value; document.querySelector('#enquiry-results').innerHTML = inboxResults(); }
  if (event.target.closest('#settings-form')) { state.settingsDirty = true; state.settings[event.target.name] = event.target.value; }
  if (event.target.closest('#client-form')) { state.clientDirty = true; state.client[event.target.name] = event.target.value; }
});
root.addEventListener('toggle', event => {
  if (event.target.dataset?.disclosure) state.expanded[event.target.dataset.disclosure] = event.target.open;
}, true);
root.addEventListener('change', event => {
  if (event.target.id === 'business-profile') { state.selectedProfile = event.target.value; render(); }
  if (event.target.id === 'role') { if (state.busy) { event.target.value = state.role; return; } state.role = event.target.value; writeSession('qf-role', state.role); render(); }
  if (event.target.id === 'record-actor') { state.recordActor = event.target.checked; writeSession('qf-actor', String(state.recordActor)); }
});
root.addEventListener('submit', async event => {
  event.preventDefault(); if (state.busy) return; const form = event.target;
  if (form.id === 'quote-form') {
    await saveQuoteAndPreview(false);
  } else if (form.id === 'profile-form') {
    const identity = state.selectedProfile;
    if (!identity || identity === state.activeProfile || !(await discardEdits())) return;
    await task(async () => {
      await api.selectProfile(identity);
      state.items = []; state.offset = 0; state.filter = 'all'; state.search = '';
      state.client = null; state.detail = null; state.quote = null; state.form = null; revokePDF();
      state.dirty = state.settingsDirty = state.clientDirty = false;
      // Invalidate every in-flight request from the previous workspace.
      await loadRoute('/settings');
      state.notice = 'Business profile switched. New enquiries use this business; existing enquiries keep their original profile.';
    });
  } else if (form.id === 'settings-form') {
    const data = new FormData(form); const patch = Object.fromEntries(['companyName', 'companyAddress', 'currency', 'defaultValidity'].map(key => [key, data.get(key)]));
    await task(async () => { state.settings = await api.saveProfile(state.settings.business_profile_id, patch); state.companyName = state.settings.companyName; state.profiles = state.profiles.map(profile => profile.id === state.settings.business_profile_id ? { ...profile, ...state.settings } : profile); state.settingsDirty = false; state.notice = 'Business settings saved. Existing quotation snapshots are unchanged.'; });
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
