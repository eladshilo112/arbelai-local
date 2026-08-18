import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { sha256, stableStringify } from './hash.js';

export class Ledger {
  constructor(databasePath) {
    this.databasePath = databasePath;
    this.database = null;
  }

  async open() {
    await mkdir(path.dirname(this.databasePath), { recursive: true });
    this.database = new DatabaseSync(this.databasePath);
    this.database.exec(`
      PRAGMA journal_mode=WAL;
      PRAGMA foreign_keys=ON;
      CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        previous_hash TEXT NOT NULL,
        event_hash TEXT NOT NULL UNIQUE
      );
      CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        intent_json TEXT NOT NULL,
        policy_json TEXT NOT NULL,
        context_json TEXT NOT NULL,
        status TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS benefit_certificates (
        certificate_id TEXT PRIMARY KEY,
        task_class TEXT NOT NULL,
        certificate_json TEXT NOT NULL,
        expires_at TEXT NOT NULL
      );
    `);
    return this;
  }

  close() {
    this.database?.close();
    this.database = null;
  }

  append(eventType, payload) {
    if (!this.database) throw new Error('Ledger is not open');
    const previous = this.database.prepare('SELECT event_hash FROM events ORDER BY id DESC LIMIT 1').get();
    const previousHash = previous?.event_hash ?? 'GENESIS';
    const createdAt = new Date().toISOString();
    const sanitizedPayload = sanitizeForLedger(payload);
    const payloadJson = stableStringify(sanitizedPayload);
    const eventHash = sha256({ createdAt, eventType, payloadJson, previousHash });
    this.database.prepare(`
      INSERT INTO events(created_at, event_type, payload_json, previous_hash, event_hash)
      VALUES (?, ?, ?, ?, ?)
    `).run(createdAt, eventType, payloadJson, previousHash, eventHash);
    return { created_at: createdAt, event_type: eventType, previous_hash: previousHash, event_hash: eventHash };
  }

  recordTask({ taskId, intent, policy, context, status = 'prepared' }) {
    if (!this.database) throw new Error('Ledger is not open');
    this.database.prepare(`
      INSERT INTO tasks(task_id, created_at, intent_json, policy_json, context_json, status)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(
      taskId,
      new Date().toISOString(),
      stableStringify(intentForLedger(intent)),
      stableStringify(sanitizeForLedger(policy)),
      stableStringify(contextForLedger(context)),
      status
    );
    return this.append('task_recorded', { task_id: taskId, status });
  }

  verifyChain() {
    if (!this.database) throw new Error('Ledger is not open');
    const rows = this.database.prepare('SELECT * FROM events ORDER BY id').all();
    let previousHash = 'GENESIS';
    for (const row of rows) {
      if (row.previous_hash !== previousHash) return false;
      const expected = sha256({
        createdAt: row.created_at,
        eventType: row.event_type,
        payloadJson: row.payload_json,
        previousHash: row.previous_hash
      });
      if (expected !== row.event_hash) return false;
      previousHash = row.event_hash;
    }
    return true;
  }

  status() {
    if (!this.database) throw new Error('Ledger is not open');
    const tasks = this.database.prepare('SELECT COUNT(*) AS count FROM tasks').get().count;
    const events = this.database.prepare('SELECT COUNT(*) AS count FROM events').get().count;
    return { tasks, events, chain_valid: this.verifyChain() };
  }
}

function intentForLedger(intent) {
  return {
    protocol_version: intent.protocol_version,
    original_request_hash: intent.original_request_hash,
    workspace_hash: sha256(intent.workspace),
    acceptance_hash: sha256(intent.acceptance),
    created_at: intent.created_at
  };
}

function contextForLedger(context) {
  return {
    protocol_version: context.protocol_version,
    root_hash: sha256(context.root),
    content_mode: context.content_mode,
    budget_tokens: context.budget_tokens,
    estimated_tokens: context.estimated_tokens,
    inventory_total: context.inventory_total,
    inventory_considered: context.inventory_considered,
    inventory_truncated: context.inventory_truncated,
    scanned_bytes: context.scanned_bytes,
    manifest_hash: context.manifest_hash,
    evidence: context.evidence.map((item) => ({
      path_hash: sha256(item.path),
      content_hash: item.hash,
      provenance: item.provenance,
      reason: item.reason,
      estimated_tokens: item.estimated_tokens ?? 0
    }))
  };
}

export function sanitizeForLedger(value) {
  if (Array.isArray(value)) return value.map(sanitizeForLedger);
  if (!value || typeof value !== 'object') return value;
  const output = {};
  for (const [key, item] of Object.entries(value)) {
    if (/secret|password|token|authorization|api[_-]?key/i.test(key)) {
      output[key] = '[REDACTED]';
    } else {
      output[key] = sanitizeForLedger(item);
    }
  }
  return output;
}