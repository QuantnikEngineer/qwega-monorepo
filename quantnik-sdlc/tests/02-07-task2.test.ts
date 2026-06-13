import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const root = join(process.cwd(), 'src');

function read(relativePath: string): string {
  return readFileSync(join(root, relativePath), 'utf8');
}

function testProtectedRouteHasVisibleLoadingUi() {
  const source = read('auth/ProtectedRoute.tsx');
  assert.match(source, /if \(isLoading\)/);
  assert.doesNotMatch(source, /if \(isLoading\)\s*\{\s*return null;?\s*\}/s);
}

function testAuthContextUsesRefreshLockHelpers() {
  const source = read('auth/AuthContext.tsx');
  assert.match(source, /broadcastRefreshStarted/);
  assert.match(source, /isRefreshInProgress/);
  assert.match(source, /broadcastRefreshComplete/);
}

function testBroadcastLockCanReleaseOnCompletion() {
  const source = read('auth/broadcastSync.ts');
  assert.match(source, /export function broadcastRefreshComplete/);
  assert.match(source, /type:\s*'REFRESH_COMPLETE'/);
}

function run() {
  testProtectedRouteHasVisibleLoadingUi();
  testAuthContextUsesRefreshLockHelpers();
  testBroadcastLockCanReleaseOnCompletion();
}

run();
