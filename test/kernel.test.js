import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { ArbelKernel } from '../src/kernel.js';

test('kernel defaults to local observation with an evidence receipt', async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'arbel-kernel-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(path.join(root, 'app.js'), 'export const answer = 42;\n');
  const kernel = new ArbelKernel({ workspace: root, policy: { mode: 'observe-local' } });
  const result = await kernel.prepare({ request: 'Inspect app.js' });
  assert.equal(result.receipt.action, 'OBSERVE');
  assert.equal(result.receipt.result, 'prepared');
  assert.equal(result.context.content_mode, 'metadata_only');
  assert.equal(result.receipt.receipt_hash.length, 64);
  const databaseBytes = await readFile(path.join(root, '.arbel', 'state.sqlite'));
  assert.equal(databaseBytes.includes(Buffer.from('Inspect app.js')), false);
});

test('kernel blocks elevated work without explicit approval', async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'arbel-block-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const kernel = new ArbelKernel({ workspace: root, policy: { mode: 'managed-write' } });
  const result = await kernel.prepare({ request: 'Configure the global proxy' });
  assert.equal(result.receipt.action, 'BLOCK');
  assert.equal(result.receipt.result, 'blocked');
});