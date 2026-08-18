import path from 'node:path';
import { realpath } from 'node:fs/promises';
import { createIntentContract, validateIntentContract } from './contracts.js';
import { compileContext } from './context.js';
import { sha256 } from './hash.js';
import { Ledger } from './ledger.js';
import { decidePolicy, normalizePolicy } from './policy.js';

export class ArbelKernel {
  constructor({ workspace, policy }) {
    this.workspace = workspace;
    this.policy = normalizePolicy(policy);
  }

  async prepare({ request, acceptance = [], explicitApproval = false, includeContent = false }) {
    const root = await realpath(this.workspace);
    const intent = createIntentContract({ request, workspace: root, acceptance });
    validateIntentContract(intent);
    const policyDecision = decidePolicy(intent, this.policy, { explicitApproval });

    const canReadContent = ['advisor', 'managed-read', 'managed-write'].includes(policyDecision.mode);
    const context = await compileContext({
      root,
      request,
      policyDecision,
      includeContent: includeContent && canReadContent
    });

    const action = this.#chooseAction(policyDecision, includeContent);
    const taskId = sha256({ request: intent.original_request_hash, context: context.manifest_hash, policy: policyDecision.decision_hash }).slice(0, 24);
    const receipt = {
      protocol_version: intent.protocol_version,
      task_id: taskId,
      action,
      intent_hash: intent.original_request_hash,
      policy_decision_hash: policyDecision.decision_hash,
      context_manifest_hash: context.manifest_hash,
      executor: null,
      usage: {
        source: 'estimated',
        context_tokens: context.estimated_tokens,
        input_tokens: null,
        output_tokens: null
      },
      verification: ['protocol_valid', 'policy_evaluated', 'context_budget_enforced'],
      result: policyDecision.permitted ? 'prepared' : 'blocked',
      created_at: new Date().toISOString()
    };
    receipt.receipt_hash = sha256(receipt);

    const ledger = await new Ledger(path.join(root, '.arbel', 'state.sqlite')).open();
    try {
      ledger.recordTask({ taskId, intent, policy: policyDecision, context, status: receipt.result });
      ledger.append('evidence_receipt', receipt);
    } finally {
      ledger.close();
    }

    return { intent, policy: policyDecision, context, receipt };
  }

  #chooseAction(policyDecision, includeContent) {
    if (!policyDecision.permitted) return 'BLOCK';
    if (policyDecision.mode === 'observe-local') return 'OBSERVE';
    if (includeContent) return 'PREPARE';
    return 'BYPASS';
  }
}