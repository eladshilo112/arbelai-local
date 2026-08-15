import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { Ledger, sanitizeForLedger } from '../src/ledger.js';

test('ledger creates a verifiable hash chain', async (t) => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'arbel-ledger-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const ledger = await new Ledger(path.join(directory, 'state.sqlite')).open();
  ledger.append('first', { value: 1 });
  ledger.append('second', { value: 2 });
  assert.equal(ledger.verifyChain(), true);
  assert.deepEqual(ledger.status(), { tasks: 0, events: 2, chain_valid: true });
  ledger.close();
});

test('ledger sanitizer redacts nested secrets', () => {
  const sanitized = sanitizeForLedger({
    safe: 'visible',
    api_key: 'never-log-me',
    nested: { authorization: 'Bearer secret' }
  });
  assert.deepEqual(sanitized, {
    safe: 'visible',
    api_key: '[REDACTED]',
    nested: { authorization: '[REDACTED]' }
  });
});