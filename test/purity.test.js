import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';

const ROOT = path.resolve(import.meta.dirname, '..');

async function sourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await sourceFiles(absolute));
    if (entry.isFile() && /\.(?:js|mjs|cjs)$/.test(entry.name)) files.push(absolute);
  }
  return files;
}

test('runtime has no dependency or install scripts', async () => {
  const packageJson = JSON.parse(await readFile(path.join(ROOT, 'package.json'), 'utf8'));
  assert.deepEqual(packageJson.dependencies ?? {}, {});
  assert.deepEqual(packageJson.optionalDependencies ?? {}, {});
  assert.deepEqual(packageJson.peerDependencies ?? {}, {});
  for (const lifecycle of ['preinstall', 'install', 'postinstall', 'prepare']) {
    assert.equal(packageJson.scripts?.[lifecycle], undefined);
  }
});

test('runtime cannot listen, proxy, spawn, or mutate process environment', async () => {
  const files = [
    ...await sourceFiles(path.join(ROOT, 'src')),
    ...await sourceFiles(path.join(ROOT, 'bin'))
  ];
  const forbidden = [
    /from\s+['"]node:(?:net|http|https|http2|tls|dgram|child_process|cluster)['"]/,
    /require\(['"]node:(?:net|http|https|http2|tls|dgram|child_process|cluster)['"]\)/,
    /\b(?:listen|createServer|spawn|execFile|fork)\s*\(/,
    /process\.env\s*(?:\.|\[)[^\n=]*=/,
    /OPENAI_BASE_URL\s*=/,
    /HTTP_PROXY\s*=/,
    /HTTPS_PROXY\s*=/,
    /ALL_PROXY\s*=/
  ];

  for (const file of files) {
    const source = await readFile(file, 'utf8');
    for (const pattern of forbidden) {
      assert.equal(pattern.test(source), false, `${path.relative(ROOT, file)} violates ${pattern}`);
    }
  }
});