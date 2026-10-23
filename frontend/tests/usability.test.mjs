import test from 'node:test';
import assert from 'node:assert/strict';
import { matchesInboxFilter, STATUS } from '../src/model.js';

test('needs checking includes known failures and unknown outcomes without mixing their labels', () => {
  assert.equal(matchesInboxFilter({ status: 'failed' }, 'attention'), true);
  assert.equal(matchesInboxFilter({ status: 'unknown' }, 'attention'), true);
  assert.equal(matchesInboxFilter({ status: 'sent' }, 'attention'), false);
  assert.equal(matchesInboxFilter({ status: 'needs_review' }, 'attention'), false);
  assert.equal(STATUS.failed[0], 'Not sent');
  assert.equal(STATUS.unknown[0], 'Check Telegram');
});
test('all and to-review filters retain the existing inbox scope', () => {
  assert.equal(matchesInboxFilter({ status: 'sent' }, 'all'), true);
  assert.equal(matchesInboxFilter({ status: 'needs_review' }, 'needs_review'), true);
  assert.equal(matchesInboxFilter({ status: 'sent' }, 'needs_review'), false);
});
