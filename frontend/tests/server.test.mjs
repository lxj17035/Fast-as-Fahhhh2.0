import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer as createHttpServer } from 'node:http';
import { createStaticServer } from '../server.mjs';

const auth = 'Basic ' + Buffer.from('old-demo-user:old-demo-password').toString('base64');

function listen(server) {
  return new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
}

function close(server) {
  return new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
}

test('demo preview serves UI and assets anonymously without a browser login challenge', async () => {
  const server = createStaticServer();
  await listen(server);
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const home = await fetch(base);
    assert.equal(home.status, 200);
    assert.equal(home.headers.get('www-authenticate'), null);
    assert.equal((await fetch(base, { headers: { Authorization: 'Basic invalid' } })).status, 200);
    assert.match(await home.text(), /QuoteFlow/);
    const appAsset = await fetch(base + '/src/api.js');
    assert.equal(appAsset.status, 200);
    assert.match(appAsset.headers.get('content-type'), /javascript/);
    assert.equal((await fetch(base + '/vendor/pdfjs/build/pdf.mjs')).status, 200);
    assert.equal((await fetch(base + '/vendor/pdfjs/build/pdf.worker.mjs')).status, 200);
    for (const path of ['/.env', '/package.json', '/tests/api.test.mjs', '/../backend/config.py', '/%2e%2e%2f.env', '/node_modules/pdfjs-dist/package.json', '/vendor/pdfjs/../../.env']) {
      assert.equal((await fetch(base + path)).status, 404);
    }
  } finally {
    await close(server);
  }
});

test('healthz is public and does not disclose backend or configuration details', async () => {
  const server = createStaticServer();
  await listen(server);
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const response = await fetch(base + '/healthz');
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { status: 'ok' });
  } finally {
    await close(server);
  }
});

test('anonymous API proxy preserves webhook validation and strips stale browser credentials', async () => {
  const requests = [];
  const api = createHttpServer((req, res) => {
    const chunks = [];
    req.on('data', chunk => chunks.push(chunk));
    req.on('end', () => {
      requests.push({
        method: req.method,
        url: req.url,
        origin: req.headers.origin,
        authorization: req.headers.authorization,
        secret: req.headers['x-telegram-bot-api-secret-token'],
        body: Buffer.concat(chunks).toString(),
      });
      if (req.url.startsWith('/api/webhooks/telegram') &&
          req.headers['x-telegram-bot-api-secret-token'] !== 'test-webhook-secret') {
        res.writeHead(401, { 'Content-Type': 'application/json' }).end('{"detail":"Invalid webhook secret"}');
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json' }).end('{"status":"ok"}');
    });
  });
  await listen(api);
  const server = createStaticServer({ apiPort: api.address().port });
  await listen(server);
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const health = await fetch(base + '/api/health');
    assert.equal(health.status, 200);
    assert.equal(health.headers.get('www-authenticate'), null);

    const invalid = await fetch(base + '/api/webhooks/telegram?source=test', {
      method: 'POST',
      headers: { Origin: 'https://public.example', 'Content-Type': 'application/json', Authorization: auth },
      body: '{"update_id":1}',
    });
    assert.equal(invalid.status, 401);
    assert.match((await invalid.json()).detail, /Invalid webhook secret/);

    const valid = await fetch(base + '/api/webhooks/telegram?source=test', {
      method: 'POST',
      headers: {
        Origin: 'https://public.example',
        'Content-Type': 'application/json',
        'X-Telegram-Bot-Api-Secret-Token': 'test-webhook-secret',
      },
      body: '{"update_id":2}',
    });
    assert.equal(valid.status, 200);
    assert.deepEqual(requests.map(request => request.method), ['GET', 'POST', 'POST']);
    assert.equal(requests[1].url, '/api/webhooks/telegram?source=test');
    assert.equal(requests[1].secret, undefined);
    assert.equal(requests[1].authorization, undefined);
    assert.equal(requests[1].origin, undefined);
    assert.equal(requests[2].secret, 'test-webhook-secret');
    assert.equal(requests[2].body, '{"update_id":2}');
  } finally {
    await Promise.all([close(server), close(api)]);
  }
});
