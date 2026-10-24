// Actual UI -> same-origin proxy -> actual FastAPI -> temporary DB. Providers mocked.
// Use installed Playwright, optionally via QF_PLAYWRIGHT_MODULE; no dependency install.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { createHash } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createStaticServer } from '../server.mjs';
import { Api } from '../src/api.js';

const { chromium } = await import(process.env.QF_PLAYWRIGHT_MODULE || 'playwright');
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.QF_TEST_PYTHON || resolve(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
const reservation = createServer();
await new Promise(r => reservation.listen(0, '127.0.0.1', r));
const apiPort = reservation.address().port;
await new Promise(r => reservation.close(r));
const child = spawn(python, ['-m', 'frontend.tests.journey_backend'], {
  cwd: root, env: { ...process.env, FRONTEND_QA_PORT: String(apiPort), PYTHONUNBUFFERED: '1' },
  stdio: ['pipe', 'ignore', 'pipe'],
});
let startupError;
child.on('error', e => { startupError = e; });
let backendLog = '';
child.stderr.on('data', data => { backendLog = (backendLog + data).slice(-4000); });
const server = createStaticServer({ apiPort });
let browser;
const errors = [];
const cases = [{ profile: 'printing', name: 'Event T-shirts', unit: 'pcs', quantity: '30', price: '25.00', total: '750.00',
  notes: 'Cotton; blue front print', initial: 'Fictional Events needs 20 cotton T-shirts with front print; please quote.',
  answer: 'Actually 30 cotton T-shirts, blue front print, please revise the quantity.' },
  { profile: 'cleaning', name: 'Office cleaning', unit: 'visit', quantity: '2', price: '180.50', total: '361.00',
    notes: '120 square metres; windows excluded', initial: 'Fictional Office requests cleaning; please quote. Scope to be confirmed.',
    answer: 'Please quote 2 visits for 120 square metres; windows excluded.' },
  { profile: 'repair', name: 'Laptop keyboard replacement', unit: 'job', quantity: '1', price: '95.75', total: '95.75',
    notes: 'Fictional Model X; replace keyboard only', initial: 'Fictional Workshop needs laptop repair; please quote. Scope to be confirmed.',
    answer: 'Please quote 1 job: Fictional Model X; replace keyboard only.' }];

try {
  const backend = new Api(`http://127.0.0.1:${apiPort}`);
  let ready = false;
  for (let i = 0; i < 100; i++) {
    if (startupError || child.exitCode !== null) throw Error(`Synthetic API startup failed: ${startupError || backendLog}`);
    try { await backend.health(); ready = true; break; } catch { await new Promise(r => setTimeout(r, 150)); }
  }
  assert.ok(ready, 'Synthetic API startup timeout');
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const url = `http://127.0.0.1:${server.address().port}`;
  const api = new Api(url);
  await mkdir(resolve(root, '.input/phase4'), { recursive: true });
  browser = await chromium.launch({ channel: process.env.QF_BROWSER_CHANNEL || 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (['error', 'warning'].includes(m.type())) errors.push(m.text()); });
  const notice = text => page.getByRole('status').filter({ hasText: text }).waitFor();
  for (const [index, c] of cases.entries()) {
    await api.selectProfile(c.profile);
    const updateId = 60000 + index * 100;
    async function incoming(offset, text, reply) {
      const body = { update_id: updateId + offset, message: { message_id: updateId + offset,
        chat: { id: -1009000001, type: 'supergroup' }, text,
        ...(reply ? { reply_to_message: { message_id: Number(reply) } } : {}) } };
      const response = await fetch(`${url}/api/webhooks/telegram`, { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Telegram-Bot-Api-Secret-Token': 'synthetic-phase4-secret' }, body: JSON.stringify(body) });
      assert.equal(response.status, 200);
    }
    await incoming(0, c.initial);
    let enquiry, quote;
    for (let i = 0; i < 100; i++) {
      enquiry = (await api.enquiries()).items[0];
      if (enquiry) { try { quote = await api.quotation(enquiry.id); break; } catch {} }
      await new Promise(r => setTimeout(r, 100));
    }
    assert.equal(quote.draftMode, 'ai'); assert.equal(quote.total, null);
    assert.equal(quote.items[0].description, c.name);
    await page.goto(url);
    assert.equal(new URL(page.url()).origin, url);
    await page.getByRole('heading', { name: 'Enquiries.', exact: true }).waitFor();
    await page.locator('.enquiry-link').first().click();
    await page.getByRole('heading', { name: 'Conversation Room', exact: true }).waitFor();
    assert.match(await page.title(), /Quotation review/);
    await page.getByLabel('Simulated role').selectOption('sales');
    assert.ok(await page.getByLabel('Item 1 unit price', { exact: true }).getAttribute('readonly') !== null);
    assert.equal((await api.conversation(enquiry.id)).items.length, 1);
    await page.getByRole('button', { name: 'Use suggestion', exact: true }).click();
    const question = (await page.getByLabel('Message to customer').inputValue()) + ' Thank you.';
    await page.getByLabel('Message to customer').fill(question);
    assert.equal((await api.conversation(enquiry.id)).items.length, 1);
    await page.getByRole('button', { name: 'Send message', exact: true }).click();
    await notice('Telegram accepted your message');
    const outgoing = (await api.conversation(enquiry.id)).items.at(-1);
    assert.equal(outgoing.actor, 'sales'); assert.equal(outgoing.text, question);
    await incoming(1, c.answer, outgoing.provider_message_id);
    for (let i = 0; i < 100; i++) {
      const analysis = await api.analysis(enquiry.id);
      if (analysis?.signature.sourceMessageIds.length === 2) break;
      await new Promise(r => setTimeout(r, 100));
    }
    await page.reload();
    await page.getByRole('heading', { name: 'Conversation Room', exact: true }).waitFor();
    assert.ok((await page.locator('.conversation-list').innerText()).includes(c.answer));
    await page.getByLabel('Item 1 quantity', { exact: true }).fill(c.quantity);
    await page.getByLabel('Item 1 unit', { exact: true }).fill(c.unit);
    await page.getByLabel('Item 1 notes', { exact: true }).fill(c.notes);
    while (await page.getByRole('button', { name: 'Mark checked', exact: true }).count()) {
      await page.getByRole('button', { name: 'Mark checked', exact: true }).first().click();
      await page.getByRole('dialog').getByRole('button', { name: 'Mark checked', exact: true }).click();
    }
    await page.locator('#review-messages').check();
    await page.getByRole('button', { name: 'Save draft', exact: true }).click();
    await notice('Your draft is saved');
    quote = await api.quotation(enquiry.id);
    assert.deepEqual(quote.reviewedMessageIds, [String(updateId), String(updateId + 1)]);
    assert.equal(quote.items[0].unitPrice, null);
    await page.getByLabel('Simulated role').selectOption('pm');
    await page.getByLabel('Item 1 unit price', { exact: true }).fill(c.price);
    await page.getByRole('button', { name: 'Save draft', exact: true }).click();
    await notice('Your draft is saved');
    quote = await api.quotation(enquiry.id);
    assert.equal(quote.total, c.total);
    assert.equal(quote.items[0].unit, c.unit); assert.equal(quote.items[0].notes, c.notes);
    assert.equal(quote.business_profile_id, c.profile);
    await page.getByRole('button', { name: 'Manager Review & Send', exact: true }).click();
    const approve = page.getByRole('button', { name: 'Approve & Send', exact: true });
    await approve.waitFor();
    await page.waitForFunction(() => !document.querySelector('[data-action="final-send"]')?.disabled);
    const review = await api.review(quote.id, quote.version);
    const pdf = await api.pdf(quote.id, quote.version);
    assert.equal(createHash('sha256').update(Buffer.from(await pdf.blob.arrayBuffer())).digest('hex'), review.pdf.sha256);
    assert.equal(await page.locator('.summary-preview').innerText(), review.telegram_summary);
    assert.ok(review.telegram_summary.includes(quote.total) && review.telegram_summary.includes(quote.expiryDate));
    assert.ok(await page.locator('#pdf-canvas').evaluate(el => el.width > 0 && el.height > 0));
    for (const [label, viewport] of [['desktop', { width: 1365, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
      await page.setViewportSize(viewport);
      await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await page.screenshot({ path: resolve(root, `.input/phase4/${c.profile}-${label}.png`), fullPage: true });
    }
    await page.setViewportSize({ width: 1365, height: 900 });
    await approve.click();
    await notice('accepted by Telegram');
    const history = (await api.conversation(enquiry.id)).items;
    assert.deepEqual(history.map(m => m.actor), ['customer', 'sales', 'customer', 'pm', 'pm']);
    assert.deepEqual(history.slice(-2).map(m => m.kind), ['quotation_pdf', 'quotation_summary']);
    assert.equal(history.at(-1).text, review.telegram_summary);
    assert.equal((await api.enquiry(enquiry.id)).status, 'sent');
    console.log(`PASS ${c.profile}: webhook -> Runpod mocked HTTP -> Staff clarification -> answer -> current-message review -> Manager price -> rendered saved PDF/summary -> approved delivery/history; desktop/mobile`);
  }
  assert.deepEqual(errors, []);
  console.log(`PASS browser identity/content/no overlay/console/interaction/screenshots; ${cases.length} journey(s)`);
} finally {
  if (browser) await browser.close();
  if (server.listening) await new Promise(r => server.close(r));
  if (child.exitCode === null && !startupError) {
    const exited = new Promise(r => child.once('exit', r));
    child.stdin.end('stop\n');
    const timeout = setTimeout(() => child.kill(), 5000);
    await exited; clearTimeout(timeout);
  }
}
