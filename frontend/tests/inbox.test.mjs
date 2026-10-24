import test from 'node:test';
import assert from 'node:assert/strict';
import {stageFor,submissionCurrent,filtered,DEMO_ROWS,inboxMarkup,enquiryRow} from '../src/inbox.js';
const item={id:'a',status:'needs_review',telegram_chat_id:'42',original_text:'20件黑色T恤',created_at:'2026-10-24'};
const quote={status:'draft',version:1,client:{name:'Example',address:''},items:[{description:'Shirts',unit:'pcs',quantity:'20',unitPrice:null}],issueDate:'2026-10-24',expiryDate:'2026-11-24',validity:'1m',notes:'',missingInformation:[],reviewedMessageIds:['1'],reviewSubmission:{version:1,sourceMessageIds:['1']}};
const detail={messages:[{update_id:'1'}],delivery_attempts:[]};
test('inbox prefers saved AI title and uses compact saved-item fallback for legacy records',()=>{
 assert.equal(enquiryRow(item,{...quote,shortTitle:'20件黑色T恤'},detail,[]).title,'20件黑色T恤');
 assert.equal(enquiryRow({...item,original_text:'Customer asks for shirts'},quote,detail,[]).title,'20 Shirts');
 assert.ok(enquiryRow(item,{...quote,summary:'English summary'},detail,[]).title.startsWith('20件'));
});
test('inbox stages require reviewed current source, details and prices in order',()=>{
 assert.equal(stageFor(item,quote,detail,[],'2026-10-24'),'need-price');
 assert.equal(stageFor(item,{...quote,items:[{...quote.items[0],unitPrice:'0'}]},detail,[],'2026-10-24'),'ready');
 assert.equal(stageFor(item,{...quote,reviewedMessageIds:[]},detail,[],'2026-10-24'),'need-info');
 assert.equal(stageFor(item,quote,detail,[{chat_id:'42'}],'2026-10-24'),'need-info');
 assert.equal(stageFor(item,{...quote,missingInformation:['Colour?']},detail,[],'2026-10-24'),'need-info');
 assert.equal(stageFor({...item,status:'unknown'},quote,detail,[],'2026-10-24'),'attention');
 assert.equal(stageFor({...item,status:'needs_review'},{...quote,status:'sent'},detail,[],'2026-10-24'),'need-info');
 assert.equal(stageFor({...item,status:'sent'},{...quote,status:'sent'},detail,[],'2026-10-24'),'sent');
});
test('role tabs and combined filters exclude closed rows and preserve restore stage',()=>{
 assert.ok(filtered(DEMO_ROWS,'todo','sales',{}).every(r=>r.stage==='need-info'));
 assert.ok(filtered(DEMO_ROWS,'todo','pm',{}).every(r=>['need-price','ready'].includes(r.stage)));
 const closed={'mock-0':{role:'Staff',at:'now'}};
 assert.equal(filtered(DEMO_ROWS,'closed','pm',closed).length,1);
 assert.equal(filtered(DEMO_ROWS,'all','pm',closed).length,DEMO_ROWS.length-1);
 assert.equal(filtered(DEMO_ROWS,'todo','pm',{},'whatsapp','ready').length,1);
 assert.equal(filtered(DEMO_ROWS,'todo','sales',{},'whatsapp','ready').length,0);
});
test('inbox escapes titles, hides unused internal ID, labels Manager-only and disables mock send',()=>{
 const s={inboxTab:'all',role:'sales',inboxSource:'',inboxStage:'',items:[],offset:0,limit:25};
 const html=inboxMarkup(s,[{...DEMO_ROWS[5],id:'internal-enquiry-id',title:'<script>bad</script>'}],{},()=> '24 Oct',()=> '');
 assert.ok(html.includes('&lt;script&gt;'));
 assert.ok(!html.includes('Copy ID'));
 assert.ok(!html.includes('copy-enquiry-id'));
 assert.ok(html.includes('Manager only'));
 assert.ok(!html.includes('disabled title="Sending is only available for Telegram"'));
 const manager=inboxMarkup({...s,role:'pm'},[DEMO_ROWS[5]],{},()=> '24 Oct',()=> '');
 assert.ok(manager.includes('disabled title="Sending is only available for Telegram"'));
 const empty=inboxMarkup({...s,inboxTab:'todo',inboxSource:'whatsapp',inboxStage:'ready'},DEMO_ROWS,{},()=>'',()=> '');
 assert.ok(empty.includes('Show 1 in All'));
});

test('only formal current handoff routes to Manager; Staff edits and new messages return to Staff',()=>{
 assert.equal(stageFor(item,{...quote,reviewSubmission:null},detail,[],'2026-10-24'),'need-info');
 assert.equal(stageFor(item,{...quote,version:2,reviewSubmission:{...quote.reviewSubmission,invalidatedBy:'sales'}},detail,[],'2026-10-24'),'need-info');
 assert.equal(stageFor(item,{...quote,version:2,reviewSubmission:{...quote.reviewSubmission,invalidatedBy:'pm'}},detail,[],'2026-10-24'),'need-price');
 assert.equal(submissionCurrent({...quote,version:2},detail),false);
 assert.equal(stageFor(item,quote,{...detail,messages:[{update_id:'1'},{update_id:'2'}]},[],'2026-10-24'),'need-info');
});
