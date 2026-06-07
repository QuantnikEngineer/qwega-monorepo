/**
 * Xray Cloud GraphQL API Service
 *
 * Authenticates via client credentials and fetches test steps
 * for Jira test cases managed by Xray.
 *
 * All requests are proxied through /xray-api to bypass CORS.
 * Credentials are kept server-side in production (env vars);
 * in dev they are injected by the Vite proxy or read from .env.
 */

const XRAY_AUTH_URL = '/xray-api/api/v2/authenticate';
const XRAY_GRAPHQL_URL = '/xray-api/api/v2/graphql';

const XRAY_CLIENT_ID = '8E9A25DB5B1A46E485E0961F1935FDD3';
const XRAY_CLIENT_SECRET = '6942bd6602616626062e311ada575ac2bbf045312249ebcb1b6b2a5231bfbf98';

// ---------------------------------------------------------------------------
// Token cache — Xray tokens are short-lived, so we cache + auto-refresh
// ---------------------------------------------------------------------------
let cachedToken: string | null = null;
let tokenExpiresAt = 0; // epoch ms

async function getXrayToken(): Promise<string> {
  // Return cached token if still valid (with 60s buffer)
  if (cachedToken && Date.now() < tokenExpiresAt - 60_000) {
    return cachedToken;
  }

  const res = await fetch(XRAY_AUTH_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_id: XRAY_CLIENT_ID,
      client_secret: XRAY_CLIENT_SECRET,
    }),
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => '');
    throw new Error(`Xray authentication failed (${res.status}): ${errText}`);
  }

  // The response is a plain JWT string (quoted)
  const token = await res.json();
  if (typeof token !== 'string' || !token) {
    throw new Error('Xray authentication returned an invalid token');
  }

  cachedToken = token;
  // Xray tokens typically last ~10 minutes; cache for 9 minutes
  tokenExpiresAt = Date.now() + 9 * 60 * 1000;
  return cachedToken;
}

// ---------------------------------------------------------------------------
// GraphQL helper
// ---------------------------------------------------------------------------
async function xrayGraphQL<T = any>(query: string, variables?: Record<string, any>): Promise<T> {
  const token = await getXrayToken();

  const res = await fetch(XRAY_GRAPHQL_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ query, variables }),
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => '');
    throw new Error(`Xray GraphQL request failed (${res.status}): ${errText}`);
  }

  const json = await res.json();
  if (json.errors?.length) {
    console.warn('Xray GraphQL errors:', json.errors);
    throw new Error(json.errors[0]?.message || 'Xray GraphQL error');
  }
  return json.data as T;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface XrayTestStep {
  Step: string;
  Expected: string;
}

/**
 * Fetch test steps for a Jira test case key (e.g. "WEGAAIDEMO-123") from Xray Cloud.
 *
 * Uses Xray's GraphQL API to query getTests → steps.
 */
export async function fetchTestStepsFromXray(testCaseKey: string): Promise<XrayTestStep[]> {
  const query = `
    query GetTestSteps($jql: String!, $limit: Int!) {
      getTests(jql: $jql, limit: $limit) {
        results {
          jira(fields: ["key", "summary"])
          testType {
            name
          }
          steps {
            id
            action
            data
            result
          }
        }
      }
    }
  `;

  try {
    const data = await xrayGraphQL<{
      getTests: {
        results: {
          jira: Record<string, any>;
          testType: { name: string } | null;
          steps: { id: string; action: string; data: string; result: string }[] | null;
        }[];
      };
    }>(query, {
      jql: `key = "${testCaseKey}"`,
      limit: 1,
    });

    const testResult = data?.getTests?.results?.[0];
    if (!testResult?.steps?.length) {
      return [];
    }

    return testResult.steps.map(step => ({
      Step: stripHtml(step.action || ''),
      Expected: stripHtml(step.result || ''),
    }));
  } catch (err) {
    console.warn('Failed to fetch test steps from Xray for', testCaseKey, err);
    return [];
  }
}

/**
 * Strip basic HTML tags from Xray step text (they sometimes return HTML).
 */
function stripHtml(html: string): string {
  if (!html) return '';
  return html.replace(/<[^>]*>/g, '').trim();
}
