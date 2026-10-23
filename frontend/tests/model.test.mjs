import test from 'node:test';
import assert from 'node:assert/strict';
import { quotePatch, editorForm, sendBlockers, escapeHTML, businessDate } from '../src/model.js';

const quote = { id: 'abcd', status: 'draft', version: 2, client: { name: 'Example', address: '' }, issueDate: '2026-10-23', expiryDate: '2026-11-23', validity: '1m', notes: '', missingInformation: [], items: [{ description: 'Shirts', quantity: '20', unitPrice: '25.00', lineTotal: '500.00' }], total: '500.00' };
const ready = { quote, detail: { source: 'telegram', telegram_chat_id: '-100123', delivery_attempts: [] }, role: 'pm', previewVersion: 2, today: '2026-10-23' };
test('blank prices stay null, zero stays explicit, derived fields stay out of PATCH', () => {
  const form = editorForm(quote);
  form.items[0].unitPrice = '';
  assert.equal(quotePatch(form, 2).items[0].unitPrice, null);
  form.items[0].unitPrice = '0';
  assert.equal(quotePatch(form, 2).items[0].unitPrice, '0');
  assert.equal(quotePatch(form, 2).total, undefined);
  assert.equal(quotePatch(form, 2).items[0].lineTotal, undefined);
});
test('approval requires PM, saved edits, current preview and unambiguous state', () => {
  assert.deepEqual(sendBlockers(ready), []);
  for (const change of [{ role: 'sales' }, { dirty: true }, { previewVersion: 1 }, { hold: true }, { busy: true }]) {
    assert.ok(sendBlockers({ ...ready, ...change }).length);
  }
});
test('unknown, pending and sent attempts block sending even if quote appears editable', () => {
  for (const status of ['pending', 'unknown', 'sent']) {
    assert.ok(sendBlockers({ ...ready, detail: { ...ready.detail, delivery_attempts: [{ quotation_id: 'ab-cd', status, can_retry: false }] } }).length);
  }
  assert.deepEqual(sendBlockers({ ...ready, detail: { ...ready.detail, delivery_attempts: [{ quotation_id: 'ab-cd', status: 'failed', can_retry: true }] } }), []);
});
test('unresolved facts, blank prices, expired and future quotations block approval', () => {
  for (const change of [{ missingInformation: ['Colour?'] }, { expiryDate: '2026-10-22' }, { issueDate: '2026-10-24' }, { items: [{ description: 'Shirts', quantity: '20', unitPrice: null }] }]) {
    assert.ok(sendBlockers({ ...ready, quote: { ...quote, ...change } }).length);
  }
});
test('customer markup is escaped and Kuala Lumpur date crosses UTC midnight correctly', () => {
  assert.equal(escapeHTML('<script>"&'), '&lt;script&gt;&quot;&amp;');
  assert.equal(businessDate(new Date('2026-10-22T17:00:00Z')), '2026-10-23');
});
