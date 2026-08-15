import { validateMode } from './contracts.js';
import { sha256 } from './hash.js';
import path from 'node:path';

const FORBIDDEN_GLOBAL_PATTERNS = [
  /\b(proxy|openai_base_url|http_proxy|https_proxy|all_proxy)\b/i,
  /\b(registry|firewall|hosts file|scheduled task|system service)\b/i,
  /(פרוקסי|חומת אש|קובץ hosts|משתני סביבה גלובליים)/i
];

const ELEVATED_PATTERNS = [
  /\b(delete|remove|erase|purge|uninstall|format)\b/i,
  /\b(proxy|openai_base_url|http_proxy|https_proxy|all_proxy)\b/i,
  /\b(registry|firewall|hosts file|scheduled task|service)\b/i,
  /\b(purchase|payment|publish|send email|post publicly)\b/i,
  /(מחק|מחיקה|הסר|פרוקסי|חומת אש|רישום|רכישה|פרסם|שלח)/i
];

const WRITE_PATTERNS = [
  /\b(write|edit|fix|implement|create|update|install|change|refactor)\b/i,
  /(כתוב|ערוך|תקן|בנה|צור|עדכן|התקן|שנה|ממש)/i
];

const SECRET_PATTERNS = [
  /\b(api[_ -]?key|access[_ -]?token|private[_ -]?key|password|secret)\b/i,
  /(סיסמה|מפתח פרטי|טוקן גישה|סוד)/i
];

export const DEFAULT_POLICY = Object.freeze({
  policy_version: '0.1.0',
  mode: 'observe-local',
  network: 'deny',
  telemetry: false,
  global_configuration_changes: false,
  external_ports: false,
  semantic_answer_cache: false,
  max_context_tokens: 4000,
  max_file_bytes: 524288,
  max_scan_files: 200,
  max_scan_bytes: 8388608,
  max_retries: 1,
  allowed_roots: [],
  allowed_providers: []
});

export function normalizePolicy(value = {}) {
  const policy = { ...DEFAULT_POLICY, ...value };
  validateMode(policy.mode);
  if (!Number.isInteger(policy.max_context_tokens) || policy.max_context_tokens < 0) {
    throw new Error('max_context_tokens must be a non-negative integer');
  }
  if (!Number.isInteger(policy.max_retries) || policy.max_retries < 0 || policy.max_retries > 2) {
    throw new Error('max_retries must be an integer between 0 and 2');
  }
  if (!Number.isInteger(policy.max_scan_files) || policy.max_scan_files < 1 || policy.max_scan_files > 5000) {
    throw new Error('max_scan_files must be an integer between 1 and 5000');
  }
  if (!Number.isInteger(policy.max_scan_bytes) || policy.max_scan_bytes < 1024) {
    throw new Error('max_scan_bytes must be an integer of at least 1024');
  }
  return policy;
}

export function decidePolicy(intentContract, policyInput, { explicitApproval = false } = {}) {
  const policy = normalizePolicy(policyInput);
  const request = intentContract.original_request;
  const elevated = ELEVATED_PATTERNS.some((pattern) => pattern.test(request));
  const forbiddenGlobalChange = FORBIDDEN_GLOBAL_PATTERNS.some((pattern) => pattern.test(request));
  const writeIntent = elevated || WRITE_PATTERNS.some((pattern) => pattern.test(request));
  const possibleSecrets = SECRET_PATTERNS.some((pattern) => pattern.test(request));

  let risk = 'low';
  if (writeIntent) risk = 'medium';
  if (elevated) risk = 'elevated';

  let permitted = policy.mode !== 'off';
  const reasons = [];
  if (policy.mode === 'off') reasons.push('mode_off');
  if (policy.mode === 'observe-local' && writeIntent) reasons.push('observe_mode_has_no_side_effects');
  if (writeIntent && !['managed-write'].includes(policy.mode)) reasons.push('mode_does_not_allow_write');
  if (elevated && !explicitApproval) reasons.push('elevated_action_requires_explicit_approval');
  if (forbiddenGlobalChange && !policy.global_configuration_changes) {
    reasons.push('global_configuration_changes_forbidden');
  }
  if (possibleSecrets && policy.network !== 'deny') reasons.push('possible_secret_requires_local_only_review');

  if (reasons.length > 0) permitted = false;

  const decision = {
    protocol_version: intentContract.protocol_version,
    policy_version: policy.policy_version,
    mode: policy.mode,
    risk,
    privacy: possibleSecrets ? 'possible_secret' : 'project_private',
    permitted,
    reasons,
    network: policy.network,
    allowed_providers: policy.allowed_providers,
    max_context_tokens: policy.max_context_tokens,
    max_scan_files: policy.max_scan_files,
    max_scan_bytes: policy.max_scan_bytes,
    max_file_bytes: policy.max_file_bytes,
    max_retries: policy.max_retries,
    decision_hash: ''
  };
  decision.decision_hash = sha256({ ...decision, decision_hash: undefined });
  return Object.freeze(decision);
}

export function createCapabilityGrant({ policyDecision, operation, target, beforeHash, maxBytes, ttlSeconds = 300 }) {
  if (!policyDecision.permitted) throw new Error('Policy decision does not permit a capability grant');
  if (policyDecision.mode !== 'managed-write') throw new Error('Capability grants require managed-write mode');
  if (!operation || !target || !beforeHash) throw new Error('Capability grant requires operation, target and beforeHash');
  const normalizedTarget = path.normalize(target);
  if (path.isAbsolute(target) || normalizedTarget === '..' || normalizedTarget.startsWith(`..${path.sep}`)) {
    throw new Error('Capability grant target must be a workspace-relative path');
  }
  if (!/^[a-f0-9]{64}$/i.test(beforeHash)) throw new Error('beforeHash must be a SHA-256 digest');
  if (!Number.isInteger(maxBytes) || maxBytes < 0) throw new Error('maxBytes must be a non-negative integer');
  const now = Date.now();
  const grant = {
    protocol_version: policyDecision.protocol_version,
    policy_decision_hash: policyDecision.decision_hash,
    operation,
    target: normalizedTarget,
    expected_before_hash: beforeHash,
    max_bytes: maxBytes,
    network: false,
    issued_at: new Date(now).toISOString(),
    expires_at: new Date(now + ttlSeconds * 1000).toISOString()
  };
  return Object.freeze({ ...grant, grant_hash: sha256(grant) });
}