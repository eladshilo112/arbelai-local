import { sha256 } from './hash.js';

export const PROTOCOL_VERSION = '0.1.0';

const MODES = new Set(['off', 'observe-local', 'advisor', 'managed-read', 'managed-write']);

function requireString(value, name) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`${name} must be a non-empty string`);
  }
  return value.trim();
}

export function validateMode(mode) {
  if (!MODES.has(mode)) throw new Error(`Unsupported mode: ${mode}`);
  return mode;
}

export function createIntentContract({ request, workspace, acceptance = [] }) {
  const originalRequest = requireString(request, 'request');
  const criteria = acceptance.length > 0
    ? acceptance.map((item) => requireString(item, 'acceptance item'))
    : ['requested_outcome_addressed', 'evidence_receipt_produced'];

  const contract = {
    protocol_version: PROTOCOL_VERSION,
    original_request: originalRequest,
    original_request_hash: sha256(originalRequest),
    workspace,
    acceptance: criteria,
    created_at: new Date().toISOString()
  };
  return Object.freeze(contract);
}

export function validateIntentContract(contract) {
  if (!contract || contract.protocol_version !== PROTOCOL_VERSION) {
    throw new Error('Unsupported or missing protocol version');
  }
  requireString(contract.original_request, 'original_request');
  requireString(contract.original_request_hash, 'original_request_hash');
  if (sha256(contract.original_request) !== contract.original_request_hash) {
    throw new Error('Intent contract hash mismatch');
  }
  if (!Array.isArray(contract.acceptance) || contract.acceptance.length === 0) {
    throw new Error('Intent contract requires acceptance criteria');
  }
  return true;
}