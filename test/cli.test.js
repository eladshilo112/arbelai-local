import assert from 'node:assert/strict';
import test from 'node:test';
import { access, mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const cli = path.resolve('bin', 'arbel.js');

function run(args) {
  return spawnSync(process.execPath, [cli, ...args], { encoding: 'utf8' });
}

test('CLI init, doctor, prepare and status form a safe end to end flow', async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'arbel-cli-'));
  t.after(() => rm(root, { recursive: true, force: true }));

  const initialized = run(['init', root]);
  assert.equal(initialized.status, 0, initialized.stderr);

  const doctorBefore = run(['doctor', '--workspace', root]);
  assert.equal(doctorBefore.status, 0, doctorBefore.stderr);
  const before = JSON.parse(doctorBefore.stdout);
  assert.equal(before.ledger_present, false);
  await assert.rejects(access(path.join(root, '.arbel', 'state.sqlite')));

  const prepared = run(['prepare', '--workspace', root, '--task', 'Inspect the workspace']);
  assert.equal(prepared.status, 0, prepared.stderr);
  const result = JSON.parse(prepared.stdout);
  assert.equal(result.receipt.action, 'OBSERVE');

  const status = run(['status', '--workspace', root]);
  assert.equal(status.status, 0, status.stderr);
  assert.deepEqual(JSON.parse(status.stdout), { tasks: 1, events: 2, chain_valid: true });
});

test('CLI init refuses to overwrite an existing policy', async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'arbel-init-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  assert.equal(run(['init', root]).status, 0);
  const second = run(['init', root]);
  assert.notEqual(second.status, 0);
  assert.match(second.stderr, /Refusing to overwrite/);
});