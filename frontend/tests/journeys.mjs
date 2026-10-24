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
    await page.getByRole('heading', { name: 'What needs you', exact: true }).waitFor();
    await page.getByLabel('Simulated role').selectOption('sales');
    await page.locator('.inbox-row [data-action="inbox-open"]').first().click();
    await page.getByRole('tab', {name:/^Messages/}).click();
    await page.getByRole('heading', { name: 'Messages', exact: true }).waitFor();
    assert.match(await page.title(), /Quotation review/);
    await page.getByLabel('Simulated role').selectOption('sales');
    assert.ok(await page.getByLabel('Item 1 unit price', { exact: true }).getAttribute('readonly') !== null);
    assert.equal((await api.conversation(enquiry.id)).items.length, 1);
    await page.getByRole('tab', {name:/^Messages/}).click();
    await page.locator('.detail-questions input[type=checkbox]').first().check();
    await page.getByRole('button', {name:'Add selected questions to message',exact:true}).click();
    const question = (await page.getByLabel('Message to customer').inputValue()) + ' Thank you.';
    await page.getByLabel('Message to customer').fill(question);
    assert.equal((await api.conversation(enquiry.id)).items.length, 1);
    await page.getByRole('button', { name: 'Send message', exact: true }).click();
    await notice('Telegram accepted your message');
    const outgoing = (await api.conversation(enquiry.id)).items.at(-1);
    assert.equal(outgoing.actor, 'sales'); assert.equal(outgoing.text, question);
    await page.getByRole('tab',{name:'Quote',exact:true}).click();
    await page.getByLabel('Item 1 notes',{exact:true}).fill('Unsaved edit retained during new-message refresh');
    await incoming(1, c.answer, outgoing.provider_message_id);
    for (let i = 0; i < 100; i++) {
      const analysis = await api.analysis(enquiry.id);
      if (analysis?.signature.sourceMessageIds.length === 2) break;
      await new Promise(r => setTimeout(r, 100));
    }
    await page.locator('.detail-message-alert').waitFor({timeout:25000});
    assert.equal(await page.getByLabel('Item 1 notes',{exact:true}).inputValue(),'Unsaved edit retained during new-message refresh');
    await page.getByRole('tab', {name:/^Messages/}).click();
    await page.getByRole('heading', { name: 'Messages', exact: true }).waitFor();
    assert.ok((await page.locator('.conversation-list').innerText()).includes(c.answer));
    assert.equal(await page.getByRole('heading',{name:'AI Suggested Changes',exact:true}).count(),1);
    assert.equal(await page.getByRole('button',{name:'Apply selected changes',exact:true}).isDisabled(),true);
    await page.locator('[data-action="detail-save"]').first().click();
    await notice('Your draft is saved');
    await page.getByRole('button',{name:'Analyze messages',exact:true}).click();
    await notice('Analysis updated');
    assert.equal(await page.getByRole('button',{name:'Analyze messages',exact:true}).count(),0);
    await page.getByLabel('Message to customer').fill('Unsent clarification retained');
    await page.locator('.suggestion-form input[name$=":notes"]').fill(c.notes + ' (Staff checked)');
    await page.locator('.suggestion-form [name="selected"]').first().check();
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:resolve(root,`.input/phase4/${c.profile}-suggestions-mobile.png`),fullPage:true});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.setViewportSize({width:1365,height:900});
    await page.getByRole('button',{name:'Apply selected changes',exact:true}).click();
    await notice('Changes applied to Quote');
    assert.equal((await api.quotation(enquiry.id)).items[0].notes,c.notes + ' (Staff checked)');
    assert.equal(await page.getByLabel('Message to customer').inputValue(),'Unsent clarification retained');
    await page.getByLabel('Message to customer').fill('');
    await page.getByRole('button',{name:'Go to Quote',exact:true}).click();
    assert.equal(await page.locator('#detail-pane-quote .suggestion-form').count(),0);
    await page.getByRole('tab', {name:'Quote',exact:true}).click();
    await page.getByLabel('Item 1 quantity', { exact: true }).fill(c.quantity);
    await page.getByLabel('Item 1 unit', { exact: true }).fill(c.unit);
    await page.getByLabel('Item 1 notes', { exact: true }).fill(c.notes);
    while (await page.getByRole('button', { name: 'Mark checked', exact: true }).count()) {
      await page.getByRole('button', { name: 'Mark checked', exact: true }).first().click();
      await page.getByRole('dialog').getByRole('button', { name: 'Mark checked', exact: true }).click();
    }
    if (await page.getByRole('button',{name:'Confirm handled & save quote',exact:true}).count()) await page.getByRole('button',{name:'Confirm handled & save quote',exact:true}).click();
    else await page.locator('#save-quote').click();
    await notice('Your draft is saved');
    quote = await api.quotation(enquiry.id);
    assert.deepEqual(quote.reviewedMessageIds, [String(updateId), String(updateId + 1)]);
    assert.equal(quote.items[0].unitPrice, null);
    await page.getByRole('button',{name:'Submit for review',exact:true}).last().click();
    await notice('Submitted for Manager review');
    const submitted = await api.quotation(enquiry.id);
    assert.equal(submitted.reviewSubmission.version,submitted.version);
    await page.locator('#quote-form .editor-options > summary').click();
    await page.locator('#quote-form [name="notes"]').fill('Staff rechecked the requirements');
    await page.locator('#save-quote').click();
    await notice('Your draft is saved');
    const edited = await api.quotation(enquiry.id);
    assert.ok(edited.reviewSubmission.version < edited.version);
    await page.getByRole('button',{name:'Submit for review',exact:true}).last().click();
    await notice('Submitted for Manager review');
    await page.locator('.back-link').click();
    await page.getByRole('heading',{name:'What needs you',exact:true}).waitFor();
    assert.equal(await page.locator(`.inbox-row [data-key="${enquiry.id}"]`).count(),0);
    await page.getByLabel('Simulated role').selectOption('pm');
    await page.locator(`.inbox-row [data-key="${enquiry.id}"]`).click();
    await page.getByRole('heading',{name:'Quote details',exact:true}).waitFor();
    await page.getByLabel('Item 1 unit price', { exact: true }).fill(c.price);
    await page.locator('#save-quote').click();
    await notice('Your draft is saved');
    quote = await api.quotation(enquiry.id);
    assert.equal(quote.total, c.total);
    assert.equal(quote.items[0].unit, c.unit); assert.equal(quote.items[0].notes, c.notes);
    assert.equal(quote.business_profile_id, c.profile);
    await page.getByRole('button', { name: 'Review & send', exact: true }).click();
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
    const beforeApproval=(await api.conversation(enquiry.id)).items.length;
    await approve.click();
    await page.getByRole('dialog').getByRole('button',{name:'Cancel',exact:true}).click();
    assert.equal((await api.conversation(enquiry.id)).items.length,beforeApproval);
    await approve.click();
    await page.getByRole('dialog').getByRole('button',{name:'Send to Telegram',exact:true}).click();
    await notice('accepted by Telegram');
    const history = (await api.conversation(enquiry.id)).items;
    assert.deepEqual(history.map(m => m.actor), ['customer', 'sales', 'customer', 'pm', 'pm']);
    assert.deepEqual(history.slice(-2).map(m => m.kind), ['quotation_pdf', 'quotation_summary']);
    assert.equal(history.at(-1).text, review.telegram_summary);
    assert.equal((await api.enquiry(enquiry.id)).status, 'sent');
    console.log(`PASS ${c.profile}: webhook -> Runpod mocked HTTP -> Staff clarification -> answer -> current-message review -> Manager price -> rendered saved PDF/summary -> approved delivery/history; desktop/mobile`);
    if (c.profile === 'printing') {
      const oldPDF = new Uint8Array(await (await api.pdf(quote.id, quote.version)).blob.arrayBuffer());
      const oldQuote = await api.quotation(enquiry.id);
      await incoming(2, 'I need 40 shirts; not sure how to group this', history.at(-1).provider_message_id);
      async function reloadAfterAnalysis(count) {
        let ready = false;
        for (let i = 0; i < 100; i++) {
          const analysis = await api.analysis(enquiry.id);
          if (analysis?.signature.sourceMessageIds.length === count) { ready = true; break; }
          await new Promise(r => setTimeout(r, 100));
        }
        assert.ok(ready, 'Follow-up analysis completed');
        await page.reload();
        await page.getByRole('tab',{name:'Quote',exact:true}).click();
        await page.getByRole('heading', { name: 'Post-send request', exact: true }).waitFor();
      }
      await reloadAfterAnalysis(3);
      assert.equal((await api.analysis(enquiry.id)).relationshipIntent, 'unclear');
      assert.equal((await api.request(`/api/enquiries/${enquiry.id}/quotations`)).items.length, 1);
      await page.getByRole('tab', {name:/^Messages/}).click();
    await page.locator('.detail-questions input[type=checkbox]').first().check();
    await page.getByRole('button', {name:'Add selected questions to message',exact:true}).click();
      await page.getByRole('button', { name: 'Send message', exact: true }).click();
      await notice('Telegram accepted your message');
      const clarification = (await api.conversation(enquiry.id)).items.at(-1);
      await incoming(3, 'Amend the original quotation to 40 shirts', clarification.provider_message_id);
      await reloadAfterAnalysis(4);
      assert.equal((await api.analysis(enquiry.id)).relationshipIntent, 'revision');
      await page.locator('#fork-form select[name="relationship"]').selectOption('revision');
      await page.getByRole('button', { name: 'Create quotation from confirmed request', exact: true }).click();
      await notice('Created a draft');

      async function prepareAndSendChild(targetId) {
        await page.getByLabel('Simulated role').selectOption('sales');
        await page.getByLabel('Item 1 quantity', { exact: true }).fill('40');
        await page.getByLabel('Item 1 unit', { exact: true }).fill('pcs');
        await page.getByLabel('Item 1 notes', { exact: true }).fill('Confirmed blue cotton');
        while (await page.getByRole('button', { name: 'Mark checked', exact: true }).count()) {
          await page.getByRole('button', { name: 'Mark checked', exact: true }).first().click();
          await page.getByRole('dialog').getByRole('button', { name: 'Mark checked', exact: true }).click();
        }
        if (await page.getByRole('button',{name:'Confirm handled & save quote',exact:true}).count()) await page.getByRole('button',{name:'Confirm handled & save quote',exact:true}).click();
    else await page.locator('#save-quote').click();
        await notice('Your draft is saved');
        assert.equal((await api.quotation(targetId)).total, null);
        await page.getByRole('button',{name:'Submit for review',exact:true}).last().click();
        await notice('Submitted for Manager review');
        await page.getByLabel('Simulated role').selectOption('pm');
        await page.getByLabel('Item 1 unit price', { exact: true }).fill('25.00');
        await page.locator('#save-quote').click();
        await notice('Your draft is saved');
        await page.getByRole('button', { name: 'Review & send', exact: true }).click();
        await page.waitForFunction(() => document.querySelector('[data-action="final-send"]') && !document.querySelector('[data-action="final-send"]').disabled);
        await page.getByRole('button', { name: 'Approve & Send', exact: true }).click();
        await page.getByRole('dialog').getByRole('button',{name:'Send to Telegram',exact:true}).click();
        await notice('accepted by Telegram');
        const saved = await api.quotation(targetId);
        assert.equal(saved.total, '1000.00'); assert.equal(saved.status, 'sent');
        assert.deepEqual(new Uint8Array(await (await api.pdf(quote.id, quote.version)).blob.arrayBuffer()), oldPDF);
        return saved;
      }
      const revision = await prepareAndSendChild(enquiry.id);
      assert.equal(revision.parentQuotationId, quote.id); assert.equal(revision.relationship, 'revision');
      await incoming(4, 'New quotation for a separate independent order of 40 shirts');
      let additional;
      for (let i = 0; i < 100; i++) {
        additional = (await api.enquiries()).items.find(e => e.id !== enquiry.id);
        if (additional) { try { await api.quotation(additional.id); break; } catch {} }
        await new Promise(r => setTimeout(r, 100));
      }
      assert.ok(additional);
      await page.reload();
      await page.getByRole('tab',{name:'Quote',exact:true}).click();
      await page.getByRole('heading', { name: 'Post-send request', exact: true }).waitFor();
      await page.locator('#fork-form select[name="relationship"]').selectOption('additional');
      await page.getByLabel('Additional enquiry reference', { exact: true }).fill(additional.id);
      await page.getByRole('button', { name: 'Create quotation from confirmed request', exact: true }).click();
      await page.waitForURL(`**/#/enquiries/${additional.id}`);
      await page.getByRole('heading', { name: 'Quote details', exact: true }).waitFor();
      const extra = await prepareAndSendChild(additional.id);
      assert.equal(extra.parentQuotationId, revision.id); assert.equal(extra.relationship, 'additional');
      assert.deepEqual(await api.request(`/api/quotations/${quote.id}`), oldQuote);
      console.log('PASS post-send UI: unclear -> explicit clarification/answer -> Revision -> new Manager price/approval -> independent Additional -> approved delivery; original PDF/metadata unchanged');
    }
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
