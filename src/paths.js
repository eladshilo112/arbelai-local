import { lstat, realpath } from 'node:fs/promises';
import path from 'node:path';

function normalizedForComparison(value) {
  const resolved = path.resolve(value);
  return process.platform === 'win32' ? resolved.toLowerCase() : resolved;
}

export function isWithinRoot(root, candidate) {
  const normalizedRoot = normalizedForComparison(root);
  const normalizedCandidate = normalizedForComparison(candidate);
  const relative = path.relative(normalizedRoot, normalizedCandidate);
  return relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative));
}

export async function resolveSafePath(root, candidate, { mustExist = true } = {}) {
  const rootReal = await realpath(root);
  const resolved = path.resolve(rootReal, candidate);
  if (!isWithinRoot(rootReal, resolved)) {
    throw new Error(`Path escapes workspace: ${candidate}`);
  }

  if (!mustExist) return resolved;
  const candidateReal = await realpath(resolved);
  if (!isWithinRoot(rootReal, candidateReal)) {
    throw new Error(`Resolved path escapes workspace: ${candidate}`);
  }

  const stat = await lstat(candidateReal);
  if (stat.isSymbolicLink()) {
    throw new Error(`Symbolic links are not accepted as direct targets: ${candidate}`);
  }
  return candidateReal;
}