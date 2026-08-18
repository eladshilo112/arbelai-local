import { createHash } from 'node:crypto';

export function stableStringify(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  const keys = Object.keys(value).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(',')}}`;
}

export function sha256(value) {
  const input = typeof value === 'string' || Buffer.isBuffer(value)
    ? value
    : stableStringify(value);
  return createHash('sha256').update(input).digest('hex');
}