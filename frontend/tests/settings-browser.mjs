// Browser plugin unavailable: use an installed Playwright module without adding a dependency.
const { chromium } = await import(process.env.QF_PLAYWRIGHT_MODULE || 'playwright');
import { spawn } from 'node:child_process';
import { createStaticServer } from '../server.mjs';
import assert from 'node:assert/strict';
const child=spawn(process.env.QF_TEST_PYTHON || (process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python'),['-m','frontend.tests.preview_backend'],{env:{...process.env,FRONTEND_QA_PORT:'8195'},stdio:['pipe','ignore','pipe']});
child.stderr.on('data',()=>{});
const server=createStaticServer({apiPort:8195});await new Promise(r=>server.listen(8196,'127.0.0.1',r));
let browser;
try {
 for(let i=0;i<100;i++){try{if((await fetch('http://127.0.0.1:8195/api/health')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1365,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8196/#/settings');await page.getByRole('heading',{name:'Business details',exact:true}).waitFor();
 assert.equal(await page.getByLabel('Company name',{exact:true}).isDisabled(),true);
 assert.equal(await page.getByText('Demo tools',{exact:true}).count(),0);
 await page.locator('#role').selectOption('pm');
 const save=page.getByRole('button',{name:'Save business details',exact:true});assert.equal(await save.isDisabled(),true);
 assert.equal(await page.locator('.settings-demo').evaluate(e=>e.open),false);
 const original=await page.getByLabel('Company name',{exact:true}).inputValue();
 await page.getByLabel('Company name',{exact:true}).fill('Changed');assert.equal(await save.isEnabled(),true);
 await page.getByLabel('Company name',{exact:true}).fill(original);assert.equal(await save.isDisabled(),true);
 await page.getByLabel('Company name',{exact:true}).fill('Fictional saved settings');await save.click();await page.getByText('Business details saved.',{exact:true}).waitFor();
 await page.reload();await page.getByRole('heading',{name:'Business details',exact:true}).waitFor();assert.equal(await page.getByLabel('Company name',{exact:true}).inputValue(),'Fictional saved settings');
 if (!await page.locator('.settings-demo').evaluate(e=>e.open)) await page.getByText('Demo tools',{exact:true}).click();assert.equal(await page.locator('#record-actor').isChecked(),true);
 await page.getByLabel('Company name',{exact:true}).fill('Unsaved');await page.locator('#business-profile').selectOption('cleaning');await page.getByRole('button',{name:'Switch business profile',exact:true}).click();
 await page.getByRole('button',{name:'Cancel',exact:true}).click();assert.equal(await page.getByLabel('Company name',{exact:true}).inputValue(),'Unsaved');
 await page.locator('#business-profile').selectOption('cleaning');await page.getByRole('button',{name:'Switch business profile',exact:true}).click();await page.getByRole('button',{name:'Save and switch',exact:true}).click();
 await page.getByText('Business profile switched.',{exact:false}).waitFor();assert.match(await page.locator('.page-heading').innerText(),/Cleaning/);
 if (!await page.locator('.settings-demo').evaluate(e=>e.open)) await page.getByText('Demo tools',{exact:true}).click();await page.locator('#business-profile').selectOption('printing');await page.getByRole('button',{name:'Switch business profile',exact:true}).click();await page.getByText('Business profile switched.',{exact:false}).waitFor();assert.equal(await page.getByLabel('Company name',{exact:true}).inputValue(),'Unsaved');
 if (!await page.locator('.settings-demo').evaluate(e=>e.open)) await page.getByText('Demo tools',{exact:true}).click();await page.getByLabel('Company name',{exact:true}).fill('Discard me');await page.locator('#business-profile').selectOption('repair');await page.getByRole('button',{name:'Switch business profile',exact:true}).click();await page.getByRole('button',{name:'Discard and switch',exact:true}).click();await page.getByText('Business profile switched.',{exact:false}).waitFor();
 await page.screenshot({path:'.input/settings-desktop.png',fullPage:true});await page.setViewportSize({width:360,height:800});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);if (!await page.locator('.settings-demo').evaluate(e=>e.open)) await page.getByText('Demo tools',{exact:true}).click();await page.screenshot({path:'.input/settings-mobile.png',fullPage:true});
 await page.locator('#role').selectOption('sales');assert.equal(await page.getByLabel('Company name',{exact:true}).isDisabled(),true);assert.equal(await page.getByRole('button',{name:'Save business details',exact:true}).count(),0);

 await page.locator('#role').selectOption('pm');
 if (!await page.locator('.settings-demo').evaluate(e=>e.open)) await page.getByText('Demo tools',{exact:true}).click();
 await page.getByLabel('Company name',{exact:true}).fill('');
 await page.locator('#business-profile').selectOption('printing');
 await page.getByRole('button',{name:'Switch business profile',exact:true}).click();
 await page.getByRole('button',{name:'Save and switch',exact:true}).click();
 await page.getByRole('dialog').waitFor({state:'hidden'});
 assert.match(await page.locator('.page-heading').innerText(),/Repair/);
 assert.equal(await page.getByLabel('Company name',{exact:true}).inputValue(),'');
 assert.equal((await (await fetch('http://127.0.0.1:8195/api/settings')).json()).business_profile_id,'repair');
 await page.getByLabel('Company name',{exact:true}).fill('Example Repair Studio (fictional)');
 await page.route('**/api/demo/capabilities',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({demoApprovalEnabled:false})}));
 await page.reload();await page.getByRole('heading',{name:'Business details',exact:true}).waitFor();
 if (!await page.locator('.settings-demo').evaluate(e=>e.open)) await page.getByText('Demo tools',{exact:true}).click();
 assert.equal(await page.locator('#record-actor').isDisabled(),true);
 await page.getByText('Not available on this server.',{exact:true}).waitFor();
 await page.getByLabel('Company name',{exact:true}).focus();await page.keyboard.press('Tab');
 assert.equal(await page.evaluate(()=>document.activeElement.name),'companyAddress');
 assert.deepEqual(errors,[]);console.log('PASS: Manager/Staff, dirty undo, save/reload, collapsed tools, cancel/save/discard switch, active profile, 360px, no browser errors.');
}finally{if(browser)await browser.close();await new Promise(r=>server.close(r));child.stdin.end('stop\n');}
