import test from 'node:test';
import assert from 'node:assert/strict';
import {pendingCustomerMessages,detailNext,canSavePrices,eventLabel,submissionIssues,initialDetailTab} from '../src/detail.js';
const quote={id:'q',status:'draft',version:1,client:{name:'Example'},items:[{description:'Shirts',quantity:'20',unit:'pcs',unitPrice:null}],missingInformation:[],issueDate:'2026-10-24',expiryDate:'2026-11-24',reviewedMessageIds:['1']};
const detail={status:'needs_review',messages:[{update_id:'1',text:'20 black shirts'},{update_id:'2',text:'Also 10 white shirts'}],delivery_attempts:[]};
const context={quote,form:quote,detail,assignments:[],role:'sales',today:'2026-10-24'};
test('new requirement alert compares source IDs rather than read timestamps',()=>{
 assert.deepEqual(pendingCustomerMessages(quote,detail).map(m=>m.update_id),['2']);
 assert.equal(pendingCustomerMessages({...quote,reviewedMessageIds:['1','2']},detail).length,0);
 assert.match(detailNext(context).body,/latest customer requirements/);
});
test('Staff never gets pricing/approval tasks and Manager retains zero-price support',()=>{
 const current={...context,quote:{...quote,reviewedMessageIds:['1','2']}};
 assert.equal(detailNext(current).title,'Submit the saved details for review');
 assert.equal(detailNext(current).buttons[1][0],'Submit for review');
 assert.equal(canSavePrices(quote),false);
 assert.equal(canSavePrices({...quote,items:[{unitPrice:'0'}]}),true);
 assert.equal(submissionIssues(current).length,0);
});
test('edits retain prices but require save/preview, holds and sent states remain distinct',()=>{
 assert.equal(detailNext({...context,dirty:true}).title,'Save your draft');
 assert.equal(detailNext({...context,hold:true}).stage,'attention');
 assert.equal(detailNext({...context,quote:{...quote,status:'sent'}}).stage,'sent');
 assert.equal(eventLabel('quotation_pdf'),'Quotation PDF');
 assert.equal(eventLabel('internal_unmapped_event'),'Quotation activity recorded');
});

test('submission needs saved complete latest data but no price or PDF',()=>{
 const q={...quote,reviewedMessageIds:['1','2']};
 const c={...context,quote:q,form:q};
 assert.deepEqual(submissionIssues(c),[]);
 assert.ok(submissionIssues({...c,dirty:true}).length);
 assert.ok(submissionIssues(context).length);
 assert.ok(submissionIssues({...c,form:{...q,missingInformation:['Colour?']}}).length);
 assert.equal(initialDetailTab(quote,detail),'messages');
 assert.equal(initialDetailTab(q,detail),'quote');
 assert.equal(detailNext({...c,quote:{...q,reviewSubmission:{version:1,sourceMessageIds:['1','2']}}}).title,'Submitted for Manager review');
});
