import assert from 'node:assert/strict';
import test from 'node:test';
import { createIntentContract, validateIntentContract } from '../src/contracts.js';

test('intent contract preserves and hashes the original request', () => {
  const contract = createIntentContract({
    request: 'Fix the failing authentication test',
    workspace: 'C:/workspace'
  });
  assert.equal(contract.original_request, 'Fix the failing authentication test');
  assert.equal(contract.original_request_hash.length, 64);
  assert.equal(validateIntentContract(contract), true);
});

test('tampered intent contract is rejected', () => {
  const contract = createIntentContract({ request: 'Read only', workspace: '/workspace' });
  assert.throws(
    () => validateIntentContract({ ...contract, original_request: 'Delete everything' }),
    /hash mismatch/
  );
});