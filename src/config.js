import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { DEFAULT_POLICY, normalizePolicy } from './policy.js';

export async function readPolicy(workspace) {
  const file = path.join(workspace, '.arbel', 'policy.json');
  try {
    return normalizePolicy(JSON.parse(await readFile(file, 'utf8')));
  } catch (error) {
    if (error?.code === 'ENOENT') return normalizePolicy(DEFAULT_POLICY);
    throw error;
  }
}

export async function initializeWorkspace(workspace, { mode = 'observe-local' } = {}) {
  const directory = path.join(workspace, '.arbel');
  await mkdir(directory, { recursive: true });
  const policy = normalizePolicy({ ...DEFAULT_POLICY, mode, allowed_roots: [workspace] });
  const target = path.join(directory, 'policy.json');
  try {
    await writeFile(target, `${JSON.stringify(policy, null, 2)}\n`, { encoding: 'utf8', flag: 'wx' });
  } catch (error) {
    if (error?.code === 'EEXIST') {
      throw new Error(`Policy already exists. Refusing to overwrite: ${target}`);
    }
    throw error;
  }
  return { directory, policy_file: target, policy };
}