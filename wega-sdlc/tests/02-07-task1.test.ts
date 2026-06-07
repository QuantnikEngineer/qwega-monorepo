import assert from 'node:assert/strict';
import { apiFetch } from '../src/services/apiClient';
import { clearTokens, getAccessToken } from '../src/auth/tokenManager';
import { login } from '../src/services/authApi';

type FetchFn = typeof fetch;

const originalFetch = globalThis.fetch;

function setMockFetch(mock: FetchFn) {
  globalThis.fetch = mock;
}

async function testLoginMapsMustChangePasswordFromUser() {
  setMockFetch(async () => {
    return new Response(
      JSON.stringify({
        access_token: 'token-1',
        expires_in: 900,
        user: {
          id: 'u1',
          email: 'user@wipro.com',
          display_name: 'User One',
          roles: ['viewer'],
          capabilities: [],
          org_id: 'org-1',
          must_change_password: true,
        },
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  });

  const result = await login('user@wipro.com', 'Password123!');
  assert.equal(result.mustChangePassword, true);
  assert.equal(result.user.mustChangePassword, true);
}

async function testLoginTopLevelFallbackMappingSafe() {
  setMockFetch(async () => {
    return new Response(
      JSON.stringify({
        access_token: 'token-2',
        expires_in: 900,
        must_change_password: true,
        user: {
          id: 'u2',
          email: 'user2@wipro.com',
          display_name: 'User Two',
          roles: [],
          capabilities: [],
          org_id: 'org-2',
        },
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  });

  const result = await login('user2@wipro.com', 'Password123!');
  assert.equal(result.mustChangePassword, true);
  assert.equal(result.user.mustChangePassword, true);
}

async function testApiFetch401RetriesRefreshWithoutPreRequestToken() {
  clearTokens();
  let call = 0;

  setMockFetch(async (input, init) => {
    call += 1;
    const url = typeof input === 'string' ? input : input.url;

    if (call === 1) {
      assert.equal(url, '/api/protected');
      assert.equal(getAccessToken(), null);
      return new Response('Unauthorized', { status: 401 });
    }

    if (call === 2) {
      assert.equal(url, '/auth/refresh');
      return new Response(JSON.stringify({ access_token: 'token-3', expires_in: 900 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (call === 3) {
      assert.equal(url, '/api/protected');
      const headers = new Headers(init?.headers);
      assert.equal(headers.get('Authorization'), 'Bearer token-3');
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    throw new Error(`Unexpected fetch call #${call}`);
  });

  const response = await apiFetch('/api/protected');
  assert.equal(response.status, 200);
  assert.equal(call, 3);
}

async function run() {
  try {
    await testLoginMapsMustChangePasswordFromUser();
    await testLoginTopLevelFallbackMappingSafe();
    await testApiFetch401RetriesRefreshWithoutPreRequestToken();
  } finally {
    globalThis.fetch = originalFetch;
    clearTokens();
  }
}

void run();
