import { opendir, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { sha256 } from './hash.js';
import { isWithinRoot } from './paths.js';

const IGNORED_DIRS = new Set(['.git', '.arbel', 'node_modules', 'target', 'dist', 'build', '.next', '.cache']);
const TEXT_EXTENSIONS = new Set([
  '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.json', '.md', '.txt', '.toml', '.yaml', '.yml',
  '.rs', '.go', '.py', '.java', '.kt', '.cs', '.cpp', '.c', '.h', '.hpp', '.html', '.css', '.sql', '.sh', '.ps1'
]);

const SENSITIVE_NAME_PATTERNS = [
  /^\.env(\.|$)/i,
  /(^|[._-])(secret|credentials?|private[_-]?key)([._-]|$)/i,
  /(^|[._-])id_(rsa|dsa|ecdsa|ed25519)([._-]|$)/i,
  /\.(pem|p12|pfx|key|keystore)$/i
];

function isSensitiveFilename(name) {
  return SENSITIVE_NAME_PATTERNS.some((pattern) => pattern.test(name));
}

async function walk(root, current, output, maxFileBytes) {
  let dir;
  try {
    dir = await opendir(current);
  } catch (error) {
    if (error?.code === 'EACCES' || error?.code === 'EPERM') return;
    throw error;
  }
  for await (const entry of dir) {
    if (entry.name.startsWith('.') && entry.name !== '.env.example') continue;
    if (IGNORED_DIRS.has(entry.name)) continue;
    const absolute = path.join(current, entry.name);
    if (!isWithinRoot(root, absolute)) continue;
    if (entry.isSymbolicLink()) continue;
    if (entry.isDirectory()) {
      await walk(root, absolute, output, maxFileBytes);
      continue;
    }
    if (!entry.isFile()) continue;
    if (isSensitiveFilename(entry.name)) continue;
    const extension = path.extname(entry.name).toLowerCase();
    if (!TEXT_EXTENSIONS.has(extension) && entry.name !== 'Dockerfile' && entry.name !== 'Makefile') continue;
    let fileStat;
    try {
      fileStat = await stat(absolute);
    } catch (error) {
      if (error?.code === 'EACCES' || error?.code === 'EPERM' || error?.code === 'ENOENT') continue;
      throw error;
    }
    if (fileStat.size > maxFileBytes) continue;
    output.push({ absolute, relative: path.relative(root, absolute), size: fileStat.size, mtime_ms: fileStat.mtimeMs });
  }
}

export async function inventoryWorkspace(root, { maxFileBytes = 524288 } = {}) {
  const output = [];
  await walk(root, root, output, maxFileBytes);
  output.sort((a, b) => a.relative.localeCompare(b.relative));
  return output;
}

function queryTerms(request) {
  return [...new Set(request.toLowerCase().split(/[^\p{L}\p{N}_]+/u).filter((term) => term.length >= 3))].slice(0, 24);
}

function selectRelevantLines(text, terms, maxLines = 32) {
  const lines = text.split(/\r?\n/);
  const selected = new Set();
  for (let index = 0; index < lines.length; index += 1) {
    const lower = lines[index].toLowerCase();
    if (!terms.some((term) => lower.includes(term))) continue;
    for (let candidate = Math.max(0, index - 2); candidate <= Math.min(lines.length - 1, index + 2); candidate += 1) {
      selected.add(candidate);
      if (selected.size >= maxLines) break;
    }
    if (selected.size >= maxLines) break;
  }
  return [...selected].sort((a, b) => a - b).map((index) => ({ line: index + 1, text: lines[index] }));
}

export async function compileContext({ root, request, policyDecision, includeContent = false }) {
  const fullInventory = await inventoryWorkspace(root, { maxFileBytes: policyDecision.max_file_bytes ?? 524288 });
  const inventory = fullInventory.slice(0, policyDecision.max_scan_files ?? 200);
  const terms = queryTerms(request);
  const budgetCharacters = policyDecision.max_context_tokens * 4;
  const maxScanBytes = policyDecision.max_scan_bytes ?? 8388608;
  let usedCharacters = 0;
  let scannedBytes = 0;
  const evidence = [];

  for (const file of inventory) {
    const nameScore = terms.filter((term) => file.relative.toLowerCase().includes(term)).length;
    if (!includeContent) {
      if (usedCharacters + file.relative.length > budgetCharacters) continue;
      usedCharacters += file.relative.length;
      evidence.push({
        path: file.relative,
        size: file.size,
        hash: sha256(`${file.relative}:${file.size}:${file.mtime_ms}`),
        provenance: 'PROJECT_UNTRUSTED',
        reason: nameScore > 0 ? 'filename_match' : 'workspace_inventory',
        content_included: false
      });
      continue;
    }

    if (scannedBytes + file.size > maxScanBytes) continue;
    scannedBytes += file.size;
    let text;
    try {
      text = await readFile(file.absolute, 'utf8');
    } catch (error) {
      if (error?.code === 'EACCES' || error?.code === 'EPERM' || error?.code === 'ENOENT') continue;
      throw error;
    }
    const lines = selectRelevantLines(text, terms);
    if (nameScore === 0 && lines.length === 0) continue;
    const excerpt = lines.map((item) => `${item.line}:${item.text}`).join('\n');
    if (usedCharacters + excerpt.length > budgetCharacters) continue;
    usedCharacters += excerpt.length;
    evidence.push({
      path: file.relative,
      size: file.size,
      hash: sha256(text),
      provenance: 'PROJECT_UNTRUSTED',
      reason: nameScore > 0 ? 'filename_or_content_match' : 'content_match',
      content_included: true,
      excerpt,
      estimated_tokens: Math.ceil(excerpt.length / 4)
    });
  }

  const manifest = {
    protocol_version: policyDecision.protocol_version,
    root,
    content_mode: includeContent ? 'targeted' : 'metadata_only',
    budget_tokens: policyDecision.max_context_tokens,
    estimated_tokens: Math.ceil(usedCharacters / 4),
    inventory_total: fullInventory.length,
    inventory_considered: inventory.length,
    inventory_truncated: fullInventory.length > inventory.length,
    scanned_bytes: scannedBytes,
    evidence,
    created_at: new Date().toISOString()
  };
  return Object.freeze({ ...manifest, manifest_hash: sha256(manifest) });
}