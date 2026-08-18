import { access, realpath } from 'node:fs/promises';
import path from 'node:path';
import { initializeWorkspace, readPolicy } from './config.js';
import { ArbelKernel } from './kernel.js';
import { Ledger } from './ledger.js';

function parseArguments(args) {
  const [command = 'help', ...rest] = args;
  const options = { _: [] };
  for (let index = 0; index < rest.length; index += 1) {
    const item = rest[index];
    if (!item.startsWith('--')) {
      options._.push(item);
      continue;
    }
    const key = item.slice(2);
    const next = rest[index + 1];
    if (!next || next.startsWith('--')) {
      options[key] = true;
    } else {
      options[key] = next;
      index += 1;
    }
  }
  return { command, options };
}

function printHelp() {
  process.stdout.write(`ARBELAI Reflex 0.1.0\n\n`);
  process.stdout.write(`Usage:\n`);
  process.stdout.write(`  arbel init [workspace] [--mode observe-local]\n`);
  process.stdout.write(`  arbel prepare --task "..." [--workspace .] [--include-content]\n`);
  process.stdout.write(`  arbel status [--workspace .]\n`);
  process.stdout.write(`  arbel doctor [--workspace .]\n\n`);
  process.stdout.write(`Safety defaults: no proxy, no ports, no daemon, no telemetry, no provider calls.\n`);
}

async function resolveWorkspace(value = '.') {
  return realpath(path.resolve(value));
}

export async function runCli(args) {
  const { command, options } = parseArguments(args);
  if (command === 'help' || options.help) return printHelp();

  if (command === 'init') {
    const workspace = await resolveWorkspace(options._[0] ?? '.');
    const result = await initializeWorkspace(workspace, { mode: options.mode ?? 'observe-local' });
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return;
  }

  const workspace = await resolveWorkspace(options.workspace ?? '.');

  if (command === 'prepare') {
    if (typeof options.task !== 'string') throw new Error('prepare requires --task');
    const policy = await readPolicy(workspace);
    const kernel = new ArbelKernel({ workspace, policy });
    const result = await kernel.prepare({
      request: options.task,
      acceptance: typeof options.acceptance === 'string' ? options.acceptance.split(',') : [],
      explicitApproval: options.approve === true,
      includeContent: options['include-content'] === true
    });
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return;
  }

  if (command === 'status') {
    const databasePath = path.join(workspace, '.arbel', 'state.sqlite');
    await access(databasePath);
    const ledger = await new Ledger(databasePath).open();
    try {
      process.stdout.write(`${JSON.stringify(ledger.status(), null, 2)}\n`);
    } finally {
      ledger.close();
    }
    return;
  }

  if (command === 'doctor') {
    const checks = {
      node_version: process.versions.node,
      node_supported: Number(process.versions.node.split('.')[0]) >= 24,
      platform: process.platform,
      architecture: process.arch,
      workspace,
      policy_present: true,
      ledger_present: false,
      ledger_chain_valid: null,
      network_listener: false,
      proxy_mutation: false,
      telemetry: false
    };
    try {
      await access(path.join(workspace, '.arbel', 'policy.json'));
    } catch {
      checks.policy_present = false;
    }
    try {
      const ledgerPath = path.join(workspace, '.arbel', 'state.sqlite');
      await access(ledgerPath);
      const ledger = await new Ledger(ledgerPath).open();
      checks.ledger_present = true;
      checks.ledger_chain_valid = ledger.verifyChain();
      ledger.close();
    } catch {
      checks.ledger_present = false;
    }
    checks.healthy = checks.node_supported && checks.policy_present && checks.ledger_chain_valid !== false;
    process.stdout.write(`${JSON.stringify(checks, null, 2)}\n`);
    return;
  }

  throw new Error(`Unknown command: ${command}`);
}