import test from 'node:test';
import assert from 'node:assert/strict';
import { createStaticServer } from '../server.mjs';

test('local server serves application assets and never repository/private files', async () => {
  const server = createStaticServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    assert.equal((await fetch(base)).status, 200);
    assert.match((await fetch(base + '/src/api.js')).headers.get('content-type'), /javascript/);
    for (const path of ['/.env', '/package.json', '/tests/api.test.mjs', '/../backend/config.py', '/%2e%2e%2f.env']) {
      assert.equal((await fetch(base + path)).status, 404);
    }
  } finally { await new Promise(resolve => server.close(resolve)); }
});
