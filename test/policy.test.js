import assert from 'node:assert/strict';
import test from 'node:test';
import { createIntentContract } from '../src/contracts.js';
import { createCapabilityGrant, decidePolicy } from '../src/policy.js';

function intent(request) {
  return createIntentContract({ request, workspace: 'C:/workspace' });
}

test('observe mode cannot authorize writes', () => {
  const decision = decidePolicy(intent('Fix the source code'), { mode: 'observe-local' });
  assert.equal(decision.permitted, false);
  assert.ok(decision.reasons.includes('observe_mode_has_no_side_effects'));
});

test('global proxy changes are elevated and require explicit approval', () => {
  const decision = decidePolicy(
    intent('Change OPENAI_BASE_URL and configure proxy'),
    { mode: 'managed-write' }
  );
  assert.equal(decision.risk, 'elevated');
  assert.equal(decision.permitted, false);
  assert.ok(decision.reasons.includes('elevated_action_requires_explicit_approval'));
  assert.ok(decision.reasons.includes('global_configuration_changes_forbidden'));
});

test('model cannot receive a write grant from a denied decision', () => {
  const decision = decidePolicy(intent('Delete the configuration'), { mode: 'managed-write' });
  assert.throws(
    () => createCapabilityGrant({
      policyDecision: decision,
      operation: 'write_file',
      target: 'config.json',
      beforeHash: 'a'.repeat(64),
      maxBytes: 100
    }),
    /does not permit/
  );
});

test('approved managed write receives a short lived, networkless grant', () => {
  const decision = decidePolicy(
    intent('Fix src/app.js'),
    { mode: 'managed-write', network: 'deny' },
    { explicitApproval: true }
  );
  assert.equal(decision.permitted, true);
  const grant = createCapabilityGrant({
    policyDecision: decision,
    operation: 'write_file',
    target: 'src/app.js',
    beforeHash: 'a'.repeat(64),
    maxBytes: 100
  });
  assert.equal(grant.network, false);
  assert.equal(grant.grant_hash.length, 64);
});

test('explicit approval still cannot authorize forbidden global interception', () => {
  const decision = decidePolicy(
    intent('Change OPENAI_BASE_URL and configure proxy'),
    { mode: 'managed-write', global_configuration_changes: false },
    { explicitApproval: true }
  );
  assert.equal(decision.permitted, false);
  assert.ok(decision.reasons.includes('global_configuration_changes_forbidden'));
});

test('capability grant rejects a path outside the workspace', () => {
  const decision = decidePolicy(
    intent('Fix src/app.js'),
    { mode: 'managed-write' },
    { explicitApproval: true }
  );
  assert.throws(
    () => createCapabilityGrant({
      policyDecision: decision,
      operation: 'write_file',
      target: '../outside.txt',
      beforeHash: 'a'.repeat(64),
      maxBytes: 100
    }),
    /workspace-relative/
  );
});