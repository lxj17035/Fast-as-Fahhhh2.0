import test from 'node:test';
import assert from 'node:assert/strict';
import { Api, ApiError, errorDetails } from '../src/api.js';

test('quotation mutation uses current backend contract and simulated actor header', async () => {
  const calls = [];
  const api = new Api('http://127.0.0.1:8004/', async (url, options) => {
    calls.push({ url, ...options }); return Response.json({ version: 3 });
  });
  await api.saveQuote('abc', { version: 2, items: [] }, 'sales');
  assert.equal(calls[0].url, 'http://127.0.0.1:8004/api/quotations/abc');
  assert.equal(calls[0].method, 'PATCH');
  assert.equal(calls[0].headers['X-Demo-Actor'], 'sales');
  assert.deepEqual(JSON.parse(calls[0].body), { version: 2, items: [] });
});
test('send and retry never include recipient or legacy approval fields', async () => {
  let body;
  const api = new Api('http://api', async (_, options) => {
    body = JSON.parse(options.body);
    assert.equal(options.headers['X-Demo-Actor'], 'pm');
    return Response.json({ status: 'failed', attempt_id: 'attempt-2' }, { status: 502 });
  });
  assert.equal((await api.send('quote', 2, 'attempt-1')).status, 'failed');
  assert.deepEqual(body, { expected_version: 2, approved: true, retry_of_attempt_id: 'attempt-1' });
});
test('server validation fields and stale conflicts remain available to UI', async () => {
  const api = new Api('http://api', async () => Response.json({ detail: { message: 'Rejected', fields: { version: 'Reload' } } }, { status: 409 }));
  await assert.rejects(api.settings(), error => error instanceof ApiError && error.status === 409 && error.fields.version === 'Reload');
  assert.equal(errorDetails({ detail: [{ loc: ['body', 'items', 0], msg: 'Invalid' }] }).fields['items.0'], 'Invalid');
});
test('PDF preview requires version header and PDF media type', async () => {
  const api = new Api('http://api', async () => new Response('%PDF-example', { headers: { 'Content-Type': 'application/pdf', 'X-Quotation-Version': '4' } }));
  assert.equal((await api.pdf('quote', 4)).version, 4);
  const bad = new Api('http://api', async () => new Response('html'));
  await assert.rejects(bad.pdf('quote', 4));
});
test('network failure does not retry a send', async () => {
  let count = 0;
  const api = new Api('http://api', async () => { count++; throw Error('private transport'); });
  await assert.rejects(api.send('quote', 2), /Do not send again/);
  assert.equal(count, 1);
});
