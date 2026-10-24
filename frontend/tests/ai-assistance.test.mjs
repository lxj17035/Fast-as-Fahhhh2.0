import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {availableChanges,analysisAction} from '../src/ai-assistance.js';
const quote={id:'q',version:2};
const detail={business_profile_id:'printing',messages:[{update_id:'1'}]};
const analysis={status:'completed',business_profile_id:'printing',signature:{quotationId:'q',baseVersion:2,sourceMessageIds:['1']}};
const set={baseVersion:2,conversationMessageIds:['1'],changes:[{id:'a'}]};
const state={quote,detail,analysis,suggestions:[set],conversation:[],assignments:[]};
test('only usable unapplied changes appear, without an empty AI panel',()=>{
 assert.equal(availableChanges(state).length,1);
 for(const patch of [{applied:true},{baseVersion:1},{conversationMessageIds:['0']},{changes:[]}]) assert.deepEqual(availableChanges({...state,suggestions:[{...set,...patch}]}),[]);
});
test('analysis recovery appears only when missing, failed or stale and not running',()=>{
 assert.equal(analysisAction(state),null);
 assert.equal(analysisAction({...state,analysis:null}),'Analyze messages');
 assert.equal(analysisAction({...state,analysis:{...analysis,status:'failed'}}),'Retry analysis');
 assert.equal(analysisAction({...state,analysis:{...analysis,stale:true}}),'Analyze messages');
 assert.equal(analysisAction({...state,analysis:{status:'running'}}),null);
 assert.equal(analysisAction({...state,analysis:null,busy:true}),null);
});
test('Messages owns suggestions between conversation and composer, Quote remains manual',async()=>{
 const source=await readFile(new URL('../src/app.js',import.meta.url),'utf8');
 const quotePane=source.slice(source.indexOf('<section id="detail-pane-quote"'),source.indexOf('<section id="detail-pane-preview"'));
 assert.ok(!quotePane.includes('suggestionsPanel()'));
 assert.ok(!source.includes('No current changes to apply'));
 assert.ok(!source.includes('AI assistance & suggested changes'));
 const conversation=source.slice(source.indexOf('function conversationPanel()'),source.indexOf('async function loadConversation'));
 assert.ok(conversation.indexOf('conversation-list')<conversation.indexOf('${suggestionsPanel()}'));
 assert.ok(conversation.indexOf('${suggestionsPanel()}')<conversation.indexOf('<form id="message-form"'));
 assert.ok(source.includes('Changes applied to Quote'));
 assert.ok(source.includes("button('Go to Quote','detail-quote')"));
});
