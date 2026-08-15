import assert from 'node:assert/strict';
import test from 'node:test';
import path from 'node:path';
import { isWithinRoot } from '../src/paths.js';

test('path traversal is rejected', () => {
  const root = path.resolve('workspace');
  assert.equal(isWithinRoot(root, path.join(root, 'src', 'app.js')), true);
  assert.equal(isWithinRoot(root, path.resolve(root, '..', 'secret.txt')), false);
});