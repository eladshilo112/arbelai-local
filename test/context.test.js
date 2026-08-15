import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { compileContext } from '../src/context.js';

test('observe context contains metadata but no file content', async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'arbel-context-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(path.join(root, 'src'));
  await writeFile(path.join(root, 'src', 'auth.js'), 'const password = "must-not-leak";\n');
  const manifest = await compileContext({
    root,
    request: 'inspect auth',
    policyDecision: { protocol_version: '0.1.0', max_context_tokens: 100 },
    includeContent: false
  });
  assert.equal(manifest.content_mode, 'metadata_only');
  assert.equal(manifest.evidence[0].content_included, false);
  assert.equal(JSON.stringify(manifest).includes('must-not-leak'), false);
});

test('targeted context respects its token budget', async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'arbel-budget-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(path.join(root, 'auth.js'), `${'authentication failure '.repeat(100)}\n`);
  const manifest = await compileContext({
    root,
    request: 'authentication failure',
    policyDecision: { protocol_version: '0.1.0', max_context_tokens: 20 },
    includeContent: true
  });
  assert.ok(manifest.estimated_tokens <= 20);
});

test('sensitive filenames are never inventoried or read', async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'arbel-secrets-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(path.join(root, '.env'), 'API_KEY=super-secret\n');
  await writeFile(path.join(root, 'credentials.txt'), 'super-secret\n');
  await writeFile(path.join(root, 'safe.txt'), 'safe content\n');
  const manifest = await compileContext({
    root,
    request: 'inspect secret credentials',
    policyDecision: {
      protocol_version: '0.1.0',
      max_context_tokens: 100,
      max_scan_files: 200,
      max_scan_bytes: 10000
    },
    includeContent: true
  });
  assert.equal(JSON.stringify(manifest).includes('super-secret'), false);
  assert.equal(manifest.evidence.some((item) => item.path.includes('credentials')), false);
});