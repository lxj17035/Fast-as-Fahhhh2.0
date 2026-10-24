import test from 'node:test';
import assert from 'node:assert/strict';
import { matchesInboxFilter, STATUS } from '../src/model.js';
import { preparationIssues, reviewGuidance } from '../src/experience.js';
import { editorForm, sendBlockers } from '../src/model.js';

test('needs checking includes known failures and unknown outcomes without mixing their labels', () => {
  assert.equal(matchesInboxFilter({ status: 'failed' }, 'attention'), true);
  assert.equal(matchesInboxFilter({ status: 'unknown' }, 'attention'), true);
  assert.equal(matchesInboxFilter({ status: 'sent' }, 'attention'), false);
  assert.equal(matchesInboxFilter({ status: 'needs_review' }, 'attention'), false);
  assert.equal(STATUS.failed[0], 'Not sent');
  assert.equal(STATUS.unknown[0], 'Check Telegram');
});
test('all and to-review filters retain the existing inbox scope', () => {
  assert.equal(matchesInboxFilter({ status: 'sent' }, 'all'), true);
  assert.equal(matchesInboxFilter({ status: 'needs_review' }, 'needs_review'), true);
  assert.equal(matchesInboxFilter({ status: 'sent' }, 'needs_review'), false);
});

const quote = { id: 'abcd', status: 'draft', version: 2, client: { name: 'Example', address: '' }, issueDate: '2026-10-23', expiryDate: '2026-11-23', validity: '1m', notes: '', missingInformation: [], items: [{ description: 'Shirts', quantity: '20', unitPrice: '25.00' }], total: '500.00' };
const ready = { quote, detail: { source: 'telegram', telegram_chat_id: '-100', delivery_attempts: [] }, form: editorForm(quote), role: 'pm', previewVersion: 2, pdfReady: true, today: '2026-10-23' };
test('guidance follows unsaved details, saved PDF, then explicit approval', () => {
  assert.equal(reviewGuidance({ ...ready, dirty: true }).action, 'save-preview');
  assert.equal(reviewGuidance({ ...ready, pdfReady: false }).action, 'preview');
  assert.equal(reviewGuidance(ready).action, 'approve');
  assert.deepEqual(sendBlockers(ready), []);
});
test('guidance describes the current form without treating its edits as saved', () => {
  const form = editorForm(quote); form.items[0].unitPrice = '';
  assert.equal(reviewGuidance({ ...ready, form, dirty: true }).action, 'fix-details');
  assert.equal(preparationIssues(form, '2026-10-23')[0].field, 'item-price-0');
  form.items[0].unitPrice = '0';
  assert.deepEqual(preparationIssues(form, '2026-10-23'), []);
});
test('Sales cannot reach the approval action and stale previews require refresh', () => {
  assert.equal(reviewGuidance({ ...ready, role: 'sales' }).action, null);
  assert.equal(reviewGuidance({ ...ready, previewVersion: 1 }).action, 'preview');
});

test('Staff can preview unpriced drafts while Manager still owns price validation', () => {
  const form = editorForm(quote); form.items[0].unitPrice = '';
  const staff = { ...ready, form, role: 'sales' };
  assert.deepEqual(preparationIssues(form, ready.today, 'sales'), []);
  assert.equal(preparationIssues(form, ready.today, 'pm')[0].field, 'item-price-0');
  assert.equal(reviewGuidance({ ...staff, dirty: true }).action, 'save-preview');
  assert.equal(reviewGuidance({ ...staff, pdfReady: false }).label, 'Preview draft');
  assert.equal(reviewGuidance(staff).title, 'Waiting for Manager pricing');
  assert.equal(reviewGuidance(staff).action, null);
  form.client.name = '';
  assert.equal(reviewGuidance(staff).action, 'fix-details');
});
test('sent and unknown states do not invite another send', () => {
  assert.equal(reviewGuidance({ ...ready, quote: { ...quote, status: 'sent' } }).kind, 'complete');
  for (const status of ['pending', 'unknown']) {
    const guidance = reviewGuidance({ ...ready, detail: { ...ready.detail, delivery_attempts: [{ quotation_id: 'ab-cd', status }] } });
    assert.equal(guidance.kind, 'warning');
    assert.equal(guidance.action, 'refresh');
  }
  assert.equal(reviewGuidance({ ...ready, hold: true }).action, 'refresh');
});
test('only the current eligible confirmed failure offers fresh approval', () => {
  const failed = { quotation_id: 'abcd', status: 'failed', can_retry: true };
  assert.equal(reviewGuidance({ ...ready, detail: { ...ready.detail, delivery_attempts: [failed] } }).action, 'approve');
  assert.equal(reviewGuidance({ ...ready, detail: { ...ready.detail, delivery_attempts: [{ ...failed, can_retry: false }] } }).action, 'refresh');
});
test('missing facts, blank client, expiry and future issue dates stay in review', () => {
  const form = editorForm(quote); form.client.name = ''; form.missingInformation = ['Colour?'];
  assert.equal(preparationIssues(form, '2026-10-23').length, 2);
  assert.equal(reviewGuidance({ ...ready, quote: { ...quote, expiryDate: '2026-10-22' } }).action, 'fix-details');
  form.client.name = 'Example'; form.missingInformation = []; form.issueDate = '2026-10-24';
  assert.equal(reviewGuidance({ ...ready, form }).action, 'fix-details');
});
