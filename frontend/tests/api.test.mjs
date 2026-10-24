import test from 'node:test';
import assert from 'node:assert/strict';
import { Api, ApiError, errorDetails } from '../src/api.js';

test('profile selection and edits use explicit profile contracts', async () => {
  const calls = [];
  const api = new Api('http://api', async (url, options) => {
    calls.push({ url, ...options }); return Response.json({});
  });
  await api.profiles(); await api.selectProfile('cleaning');
  await api.saveProfile('printing', { companyName: 'Fictional Print' });
  assert.equal(calls[0].url, 'http://api/api/business-profiles');
  assert.deepEqual(JSON.parse(calls[1].body), { business_profile_id: 'cleaning' });
  assert.equal(calls[2].url, 'http://api/api/business-profiles/printing');
  assert.deepEqual(JSON.parse(calls[2].body), { companyName: 'Fictional Print' });
});

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
test('ambiguous server finalization is returned as unknown for reconciliation', async () => {
  const api = new Api('http://api', async () => Response.json({ attempt_id: 'pending-id', status: 'unknown', detail: 'Delivery outcome could not be saved' }, { status: 503 }));
  assert.equal((await api.send('quote', 2)).status, 'unknown');
});
test('malformed success cannot be mistaken for a confirmed delivery', async () => {
  for (const payload of [null, [], { status: 'sent' }, { attempt_id: 'id', status: 'unexpected' }]) {
    let calls = 0;
    const api = new Api('http://api', async () => { calls++; return Response.json(payload); });
    await assert.rejects(api.send('quote', 2), error => error instanceof ApiError);
    assert.equal(calls, 1);
  }
});

test('assignment actions use explicit human role and no chat override', async () => {
  const calls = []; const api = new Api('', async (url, options) => { calls.push({url, ...options}); return Response.json({}); });
  await api.assignments(); await api.assign('123', {action: 'assign', enquiry_id: 'same-chat'}, 'sales');
  assert.equal(calls[0].url, '/api/assignments'); assert.equal(calls[1].headers['X-Demo-Actor'], 'sales');
  assert.deepEqual(JSON.parse(calls[1].body), {action: 'assign', enquiry_id: 'same-chat'});
});

test('conversation deliveries retain explicit failures and do not grant AI authority', async () => {
  let call; const api = new Api('', async (url, options) => { call = {url, ...options}; return Response.json({id: 'message-id', status: 'failed'}, {status: 502}); });
  assert.equal((await api.message('enquiry', {text: 'Human reviewed', request_id: 'stable-id'}, 'sales')).status, 'failed');
  assert.equal(call.headers['X-Demo-Actor'], 'sales'); assert.deepEqual(JSON.parse(call.body), {text: 'Human reviewed', request_id: 'stable-id'});
});
test('analysis absence is allowed only on the nullable analysis contract', async () => {
  const api = new Api('', async () => Response.json(null));
  assert.equal(await api.analysis('enquiry'), null); await assert.rejects(api.settings());
});

test('final review uses an explicit Manager role and exact saved version', async () => {
  let call; const api = new Api('', async (url, options) => {call={url,...options};return Response.json({send_ready:true});});
  await api.review('abc', 7); assert.equal(call.url, '/api/quotations/abc/review?version=7'); assert.equal(call.headers['X-Demo-Actor'], 'pm'); assert.equal(call.method, 'GET');
});

test('review submission sends saved version, source IDs and explicit human role only', async () => {
 let call; const api = new Api('', async (url, options) => {call={url,...options};return Response.json({});});
 await api.submitReview('abc',7,['123'],'sales');
 assert.equal(call.url,'/api/quotations/abc/submit-review');
 assert.equal(call.headers['X-Demo-Actor'],'sales');
 assert.deepEqual(JSON.parse(call.body),{version:7,sourceMessageIds:['123']});
});
