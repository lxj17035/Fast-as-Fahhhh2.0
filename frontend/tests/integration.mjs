// Exercise the shipped JS client against the actual Python app, never live providers.
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Api } from '../src/api.js';
import { editorForm, quotePatch, sendBlockers } from '../src/model.js';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.QF_TEST_PYTHON || resolve(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
const reservation = createServer();
await new Promise(resolve => reservation.listen(0, '127.0.0.1', resolve));
const port = reservation.address().port;
await new Promise(resolve => reservation.close(resolve));
const child = spawn(python, ['-m', 'frontend.tests.preview_backend'], {
  cwd: root, env: { ...process.env, FRONTEND_QA_PORT: String(port), PYTHONUNBUFFERED: '1' },
  stdio: ['pipe', 'ignore', 'pipe'],
});
let startupError;
child.on('error', error => { startupError = error; });
child.stderr.on('data', () => {});
const api = new Api(`http://127.0.0.1:${port}`);
let quote, enquiry, originalPDF, failedAttempt;

async function pricedDraft(id) {
  const draft = await api.quotation(id);
  const form = editorForm(draft);
  form.items[0].unitPrice = '25.00'; form.missingInformation = [];
  return api.saveQuote(draft.id, quotePatch(form, draft.version), 'pm');
}

try {
  let ready = false;
  for (let attempt = 0; attempt < 80; attempt++) {
    if (startupError || child.exitCode !== null) throw Error('QA backend could not start. Install requirements-dev.txt into .venv.');
    try { await api.health(); ready = true; break; } catch { await new Promise(resolve => setTimeout(resolve, 150)); }
  }
  if (!ready) throw Error('QA backend did not become ready.');

  await test('actual API: inbox/detail/draft, original IDs and blank prices', async () => {
    const page = await api.enquiries(); assert.equal(page.items.length, 4);
    enquiry = await api.enquiry(page.items.find(item => item.original_text.startsWith('Example Events')).id);
    assert.equal(typeof enquiry.telegram_chat_id, 'string');
    assert.equal(enquiry.messages[0].text, enquiry.original_text);
    quote = await api.quotation(enquiry.id);
    assert.equal(quote.items[0].unitPrice, null); assert.equal(quote.total, null);
    assert.equal((await api.draft(enquiry.id, true)).id, quote.id);
  });
  await test('actual API: generic units, Staff price protection and selected AI changes', async () => {
    const form = editorForm(quote); form.items[0].unit = 'pcs'; form.items[0].notes = 'Front print';
    quote = await api.saveQuote(quote.id, quotePatch(form, quote.version), 'sales');
    assert.equal(quote.items[0].unit, 'pcs'); assert.equal(quote.items[0].notes, 'Front print');
    const forbidden = quotePatch(editorForm(quote), quote.version); forbidden.items[0].unitPrice = '10';
    await assert.rejects(api.saveQuote(quote.id, forbidden, 'sales'), error => error.status === 403);
    const analysis = await api.analysis(enquiry.id, 'sales'); assert.ok(analysis.suggestionSetId);
    const set = (await api.suggestions(quote.id)).items.find(s => s.id === analysis.suggestionSetId);
    quote = await api.applyChanges(quote.id, {version: quote.version, suggestion_set_id: set.id, selected: [set.changes[0].id], edits: {[set.changes[0].id]: {type:'UPDATE_ITEM',index:0,data:{notes:'Staff reviewed blue'}}}}, 'sales');
    assert.equal(quote.items[0].notes, 'Staff reviewed blue'); assert.equal(quote.items[0].unitPrice, null);
    await assert.rejects(api.applyChanges(quote.id, {version:quote.version,suggestion_set_id:set.id,selected:[set.changes[0].id]}, 'sales'), error => error.status === 409);
  });
  await test('actual API: save recalculates exact total and rejects stale edits', async () => {
    quote = await pricedDraft(enquiry.id);
    assert.equal(quote.total, '500.00'); assert.equal(quote.version, 4);
    const stale = quotePatch(editorForm(quote), 1);
    await assert.rejects(api.saveQuote(quote.id, stale), error => error.status === 409);
    assert.equal((await api.quotation(enquiry.id)).version, 4);
  });
  await test('actual API: PDF and approval require the current saved version', async () => {
    await assert.rejects(api.send(quote.id, quote.version), error => error.status === 409);
    await assert.rejects(api.pdf(quote.id, 1), error => error.status === 409);
    const preview = await api.pdf(quote.id, quote.version);
    assert.equal(preview.version, quote.version); originalPDF = new Uint8Array(await preview.blob.arrayBuffer());
    assert.equal(new TextDecoder().decode(originalPDF.slice(0, 5)), '%PDF-');
    await assert.rejects(api.request(`/api/quotations/${quote.id}/send`, { method: 'POST', role: 'sales', body: { approved: true, expected_version: quote.version } }), error => error.status === 403);
  });
  await test('actual API: Manager review matches the saved PDF and deterministic summary', async () => {
    const review = await api.review(quote.id, quote.version);
    assert.equal(review.quotation.version, quote.version); assert.equal(review.delivery_mode, 'pdf_and_summary');
    assert.equal(review.pdf.version, quote.version); assert.match(review.pdf.sha256, /^[a-f0-9]{64}$/);
    assert.ok(review.telegram_summary.includes('RM 500.00')); assert.ok(review.telegram_summary.includes(quote.expiryDate));
    assert.deepEqual(review.source_message_ids, enquiry.messages.map(m => m.update_id));
    await assert.rejects(api.request(`/api/quotations/${quote.id}/review?version=${quote.version}`, {role:'sales'}), error=>error.status===403);
  });
  await test('actual API: confirmed rejection needs the exact failed-attempt approval', async () => {
    const result = await api.send(quote.id, quote.version);
    assert.equal(result.status, 'failed'); failedAttempt = result.attempt_id;
    await assert.rejects(api.send(quote.id, quote.version), error => error.status === 409);
    const detail = await api.enquiry(enquiry.id);
    assert.equal(detail.delivery_attempts[0].can_retry, true);
    assert.equal(detail.delivery_attempts[0].attempt_id, failedAttempt);
  });
  await test('actual API: approved retry succeeds, keeps history and blocks duplicate send', async () => {
    assert.equal((await api.send(quote.id, quote.version, failedAttempt)).status, 'sent');
    await assert.rejects(api.send(quote.id, quote.version, failedAttempt), error => error.status === 409);
    const detail = await api.enquiry(enquiry.id);
    assert.equal(detail.delivery_attempts.length, 2);
    assert.equal(detail.delivery_attempts[1].retry_of_attempt_id, failedAttempt);
    assert.equal(detail.status, 'sent');
    assert.equal(detail.activity.filter(item => item.action === 'pm_approved').length, 2);
    assert.equal((await api.quotation(enquiry.id)).status, 'sent');
  });
  await test('actual API: settings/client edits preserve the sent PDF snapshot', async () => {
    await api.saveSettings({ companyName: 'Updated fictional company', defaultValidity: '14d' });
    await api.saveClient(quote.client.id, { name: 'Updated fictional client', address: '' });
    assert.equal((await api.settings()).companyName, 'Updated fictional company');
    assert.equal((await api.client(quote.client.id)).name, 'Updated fictional client');
    const after = await api.pdf(quote.id, quote.version);
    assert.deepEqual(new Uint8Array(await after.blob.arrayBuffer()), originalPDF);
  });
  await test('actual API: unknown delivery persists and cannot be retried', async () => {
    const page = await api.enquiries();
    const other = page.items.find(item => item.id !== enquiry.id);
    const q = await pricedDraft(other.id); await api.pdf(q.id, q.version);
    const result = await api.send(q.id, q.version); assert.equal(result.status, 'unknown');
    const detail = await api.enquiry(other.id);
    assert.equal(detail.delivery_attempts[0].requires_verification, true);
    assert.equal(detail.delivery_attempts[0].can_retry, false);
    assert.ok(sendBlockers({ quote: await api.quotation(other.id), detail, role: 'pm', previewVersion: q.version }).length);
    await assert.rejects(api.send(q.id, q.version, result.attempt_id), error => error.status === 409);
  });
  await test('actual API: profile switches isolate enquiries and preserve named settings and saved PDFs', async () => {
    const profiles = await api.profiles();
    assert.deepEqual(profiles.items.map(item => item.id), ['printing', 'cleaning', 'repair']);
    for (const identity of ['cleaning', 'repair']) {
      assert.equal((await api.selectProfile(identity)).business_profile_id, identity);
      assert.equal((await api.settings()).business_profile_id, identity);
      assert.equal((await api.enquiries()).items.length, 0);
      await assert.rejects(api.enquiry(enquiry.id), error => error.status === 404);
      await assert.rejects(api.pdf(quote.id, quote.version), error => error.status === 404);
    }
    await api.saveProfile('cleaning', { companyName: 'Fictional Cleaning Service' });
    assert.equal((await api.settings()).business_profile_id, 'repair');
    await api.selectProfile('cleaning');
    assert.equal((await api.settings()).companyName, 'Fictional Cleaning Service');
    await api.selectProfile('printing');
    assert.equal((await api.enquiry(enquiry.id)).business_profile_id, 'printing');
    assert.deepEqual(new Uint8Array(await (await api.pdf(quote.id, quote.version)).blob.arrayBuffer()), originalPDF);
    await assert.rejects(api.selectProfile('unknown'), error => error.status === 422);
    assert.equal((await api.settings()).business_profile_id, 'printing');
  });
} finally {
  const exited = new Promise(resolve => child.once('exit', resolve));
  if (child.exitCode === null && !startupError) {
    child.stdin.end('stop\n');
    const timeout = setTimeout(() => child.kill(), 4000);
    await exited; clearTimeout(timeout);
  }
}
