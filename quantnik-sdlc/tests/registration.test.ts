/**
 * Tests for direct-to-project registration — authApi functions.
 * ==============================================================
 * Validates register() sends correct payloads and fetchRegistrationDefaults()
 * handles success, failure, and network errors gracefully.
 *
 * Uses the same pattern as existing tests: node:assert/strict + fetch mock.
 */

import assert from 'node:assert/strict';
import { register, fetchRegistrationDefaults } from '../src/services/authApi';

type FetchFn = typeof fetch;
const originalFetch = globalThis.fetch;

function setMockFetch(mock: FetchFn) {
  globalThis.fetch = mock;
}

// ── register() tests ──────────────────────────────────────────────

async function testRegisterWithoutProjectSlug() {
  let capturedBody: Record<string, unknown> | null = null;
  let capturedUrl = '';

  setMockFetch(async (input: RequestInfo | URL, init?: RequestInit) => {
    capturedUrl = String(input);
    capturedBody = JSON.parse(init?.body as string);
    return new Response(
      JSON.stringify({ status: 'registered', message: 'Account created.' }),
      { status: 201, headers: { 'Content-Type': 'application/json' } }
    );
  });

  await register('user@wipro.com', 'Test User', 'SecureP@ss123!');

  assert.ok(capturedUrl.includes('/auth/register'), 'Should call /auth/register');
  assert.ok(capturedBody, 'Should have sent a body');
  assert.equal(capturedBody!.email, 'user@wipro.com');
  assert.equal(capturedBody!.display_name, 'Test User');
  assert.equal(capturedBody!.password, 'SecureP@ss123!');
  // project_slug must NOT be present when not provided
  assert.equal(capturedBody!.project_slug, undefined, 'project_slug should be absent');
  console.log('  ✓ register without project_slug');
}

async function testRegisterWithProjectSlug() {
  let capturedBody: Record<string, unknown> | null = null;

  setMockFetch(async (_input: RequestInfo | URL, init?: RequestInit) => {
    capturedBody = JSON.parse(init?.body as string);
    return new Response(
      JSON.stringify({ status: 'registered', message: 'Account created.' }),
      { status: 201, headers: { 'Content-Type': 'application/json' } }
    );
  });

  await register('user@wipro.com', 'Test User', 'SecureP@ss123!', 'demo-project');

  assert.ok(capturedBody, 'Should have sent a body');
  assert.equal(capturedBody!.project_slug, 'demo-project', 'project_slug should be present');
  console.log('  ✓ register with project_slug');
}

async function testRegisterHandles400Error() {
  setMockFetch(async () => {
    return new Response(
      JSON.stringify({ detail: 'This project is not available for registration.' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } }
    );
  });

  await assert.rejects(
    () => register('user@wipro.com', 'User', 'SecureP@ss123!', 'bad-slug'),
    (err: Error) => {
      assert.ok(err.message.includes('not available'), `Error message: ${err.message}`);
      return true;
    }
  );
  console.log('  ✓ register handles 400 error');
}

async function testRegisterHandlesNetworkError() {
  setMockFetch(async () => {
    throw new TypeError('Failed to fetch');
  });

  await assert.rejects(
    () => register('user@wipro.com', 'User', 'SecureP@ss123!'),
    (err: Error) => {
      assert.ok(err instanceof Error);
      return true;
    }
  );
  console.log('  ✓ register handles network error');
}

// ── fetchRegistrationDefaults() tests ─────────────────────────────

async function testDefaultsProjectMode() {
  setMockFetch(async () => {
    return new Response(
      JSON.stringify({
        mode: 'project',
        project_slug: 'demo-project',
        project_name: 'Demo Project',
        role: 'po_sm_ba',
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  });

  const defaults = await fetchRegistrationDefaults();
  assert.equal(defaults.mode, 'project');
  assert.equal(defaults.project_slug, 'demo-project');
  assert.equal(defaults.project_name, 'Demo Project');
  assert.equal(defaults.role, 'po_sm_ba');
  console.log('  ✓ fetchRegistrationDefaults project mode');
}

async function testDefaultsPMMode() {
  setMockFetch(async () => {
    return new Response(
      JSON.stringify({ mode: 'pm' }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  });

  const defaults = await fetchRegistrationDefaults();
  assert.equal(defaults.mode, 'pm');
  assert.equal(defaults.project_slug, undefined);
  console.log('  ✓ fetchRegistrationDefaults PM mode');
}

async function testDefaultsHttpErrorFallsToPM() {
  setMockFetch(async () => {
    return new Response('Server error', { status: 500 });
  });

  const defaults = await fetchRegistrationDefaults();
  assert.equal(defaults.mode, 'pm', 'Should fall back to PM on HTTP error');
  console.log('  ✓ fetchRegistrationDefaults falls back to PM on HTTP error');
}

async function testDefaultsNetworkErrorFallsToPM() {
  setMockFetch(async () => {
    throw new TypeError('Failed to fetch');
  });

  const defaults = await fetchRegistrationDefaults();
  assert.equal(defaults.mode, 'pm', 'Should fall back to PM on network error');
  console.log('  ✓ fetchRegistrationDefaults falls back to PM on network error');
}

async function testDefaultsMalformedJsonFallsToPM() {
  setMockFetch(async () => {
    return new Response('not json', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });

  const defaults = await fetchRegistrationDefaults();
  assert.equal(defaults.mode, 'pm', 'Should fall back to PM on malformed JSON');
  console.log('  ✓ fetchRegistrationDefaults falls back to PM on malformed JSON');
}

// ── SAST: verify no sensitive data in register payloads ───────────

async function testRegisterDoesNotLeakPasswordInUrl() {
  let capturedUrl = '';

  setMockFetch(async (input: RequestInfo | URL) => {
    capturedUrl = String(input);
    return new Response(
      JSON.stringify({ status: 'registered', message: 'ok' }),
      { status: 201, headers: { 'Content-Type': 'application/json' } }
    );
  });

  await register('user@wipro.com', 'User', 'SuperSecret123!');
  assert.ok(!capturedUrl.includes('SuperSecret'), 'Password must not appear in URL');
  console.log('  ✓ SAST: password not leaked in URL');
}

// ── Runner ────────────────────────────────────────────────────────

async function run() {
  console.log('\nRegistration API tests');
  console.log('────────────────────────────────────────');

  try {
    // register() tests
    await testRegisterWithoutProjectSlug();
    await testRegisterWithProjectSlug();
    await testRegisterHandles400Error();
    await testRegisterHandlesNetworkError();

    // fetchRegistrationDefaults() tests
    await testDefaultsProjectMode();
    await testDefaultsPMMode();
    await testDefaultsHttpErrorFallsToPM();
    await testDefaultsNetworkErrorFallsToPM();
    await testDefaultsMalformedJsonFallsToPM();

    // SAST
    await testRegisterDoesNotLeakPasswordInUrl();

    console.log('\n✅ All registration tests passed\n');
  } catch (err) {
    console.error('\n❌ Test failed:', err);
    process.exitCode = 1;
  } finally {
    globalThis.fetch = originalFetch;
  }
}

void run();
