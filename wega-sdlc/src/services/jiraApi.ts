/**
 * Jira Cloud REST API Service
 *
 * Uses the NEW Jira Cloud REST API v3 search/jql endpoint.
 * The old /rest/api/2/search and /rest/api/3/search have been removed.
 * See: https://developer.atlassian.com/changelog/#CHANGE-2046
 *
 * Client-side environment variables (set in .env, used as fallbacks):
 *   VITE_ATLASSIAN_BASE_URL – e.g. https://wegabuildiq.atlassian.net (for browse links)
 *   VITE_JIRA_PROJECT_KEY   – Jira project key to display
 *
 * Authentication:
 *   - Browser sends JWT Bearer token to the gateway.
 *   - Gateway resolves project-scoped Atlassian credentials and injects
 *     Basic auth for upstream Jira calls.
 *   - The browser NEVER handles Atlassian credentials.
 */

import { getAccessToken } from '../auth/tokenManager';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface JiraProject {
  id: string;
  key: string;
  name: string;
  avatarUrl?: string;
}

export interface JiraIssue {
  id: string;
  key: string;
  summary: string;
  description?: string;
  status: string;
  issueType: string;
  priority?: string;
  assignee?: string;
  updated: string;
  children?: JiraIssue[];
  /** Full URL to the issue in Jira, e.g. https://wegabuildiq.atlassian.net/browse/WEGAAIDEMO-1 */
  url: string;
}

interface JiraSearchResponse {
  issues: {
    id: string;
    key: string;
    fields: {
      summary: string;
      status: { name: string };
      issuetype: { name: string };
      priority?: { name: string };
      assignee?: { displayName: string } | null;
      updated: string;
    };
  }[];
  total: number;
  maxResults: number;
  startAt: number;
}

interface JiraProjectsResponse {
  values?: {
    id: string;
    key: string;
    name: string;
    avatarUrls?: { '24x24'?: string };
  }[];
  [index: number]: any;
}

// ---------------------------------------------------------------------------
// Config helpers
// ---------------------------------------------------------------------------

/* eslint-disable @typescript-eslint/no-explicit-any */
const _env = (import.meta as any).env ?? {};

// Fallback values from build-time env vars (used when no project config is available)
const _FALLBACK_BASE_URL: string = _env.VITE_ATLASSIAN_BASE_URL || 'https://wegabuildiq.atlassian.net';
const _FALLBACK_PROJECT_KEY: string = _env.VITE_JIRA_PROJECT_KEY || 'WEGAAIDEMO';

// Runtime config — set by Execute.tsx when project tool settings load
let _runtimeConfig: { baseUrl?: string; projectKey?: string } = {};

/**
 * Set runtime Jira config from project tool settings.
 * Called by Execute.tsx when useProjectToolConfig returns data.
 */
export function setJiraConfig(config: { baseUrl?: string; projectKey?: string }): void {
  _runtimeConfig = config;
}

function getBaseUrl(): string {
  return _runtimeConfig.baseUrl || _FALLBACK_BASE_URL;
}

function getProjectKey(): string {
  return _runtimeConfig.projectKey || _FALLBACK_PROJECT_KEY;
}

/**
 * Standard request headers.
 * Authentication is handled by the gateway (JWT → Atlassian Basic auth injection).
 */
function getAuthHeaders(): HeadersInit {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = getAccessToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Build the full Jira API URL.
 * Routes through the gateway at `/jira/` to bypass CORS.
 */
function apiUrl(path: string): string {
  return `/jira-api${path}`;
}

/**
 * Build the browse URL for a Jira issue (for hyperlinks).
 */
function browseUrl(issueKey: string): string {
  return `${getBaseUrl()}/browse/${issueKey}`;
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatDate(isoString?: string): string {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString('en-US', {
      month: 'numeric',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return isoString;
  }
}

/**
 * Extract plain text from a Jira v3 ADF (Atlassian Document Format) description.
 * Falls back to returning the value as-is if it's already a string.
 */
function extractDescription(desc: any): string {
  if (!desc) return '';
  if (typeof desc === 'string') return desc;
  // ADF format: { type: 'doc', content: [...] }
  if (typeof desc === 'object' && desc.content) {
    const extractText = (node: any): string => {
      if (!node) return '';
      if (node.type === 'text') return node.text || '';
      if (Array.isArray(node.content)) {
        return node.content.map(extractText).join('');
      }
      return '';
    };
    return (desc.content as any[])
      .map((block: any) => extractText(block))
      .filter(Boolean)
      .join('\n');
  }
  return String(desc);
}

function mapIssue(issue: any): JiraIssue {
  return {
    id: issue.id,
    key: issue.key,
    summary: issue.fields?.summary || 'Untitled',
    description: extractDescription(issue.fields?.description),
    status: issue.fields?.status?.name || 'Unknown',
    issueType: issue.fields?.issuetype?.name || 'Unknown',
    priority: issue.fields?.priority?.name,
    assignee: issue.fields?.assignee?.displayName,
    updated: formatDate(issue.fields?.updated),
    url: browseUrl(issue.key),
  };
}

// ---------------------------------------------------------------------------
// Core search helper — uses new /rest/api/3/search/jql endpoint
// ---------------------------------------------------------------------------

/**
 * Search Jira issues using the new /rest/api/3/search/jql endpoint.
 * Falls back to /rest/api/2/search if the new endpoint fails.
 */
async function searchJql(jql: string, maxResults = 50): Promise<any[]> {
  const fields = 'summary,description,status,issuetype,priority,assignee,updated';
  
  // Try new v3 /search/jql endpoint first
  const v3Url = apiUrl(
    `/rest/api/3/search/jql?jql=${encodeURIComponent(jql)}&fields=${fields}&maxResults=${maxResults}`
  );

  try {
    const res = await fetch(v3Url, {
      headers: getAuthHeaders(),
      signal: AbortSignal.timeout(15000),
    });

    if (res.ok) {
      const data = await res.json();
      return data.issues || [];
    }

    // If 404 or other error, try fallback
    console.warn(`v3 search/jql returned ${res.status}, trying v2 fallback...`);
  } catch (err: any) {
    console.warn('v3 search/jql failed:', err.message);
  }

  // Fallback to v2 /search (in case the v3 endpoint isn't available yet)
  const v2Url = apiUrl(
    `/rest/api/2/search?jql=${encodeURIComponent(jql)}&fields=${fields}&maxResults=${maxResults}`
  );

  const res = await fetch(v2Url, {
    headers: getAuthHeaders(),
    signal: AbortSignal.timeout(15000),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => '');
    throw new Error(`Jira search failed (${res.status}): ${errorText}`);
  }

  const data = await res.json();
  return data.issues || [];
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Fetch all Jira projects using the project search endpoint.
 */
export async function fetchJiraProjects(): Promise<JiraProject[]> {
  // Fetch all projects
  let res: Response;

  try {
    res = await fetch(
      apiUrl('/rest/api/3/project/search?maxResults=50&orderBy=name'),
      { headers: getAuthHeaders(), signal: AbortSignal.timeout(15000) }
    );
  } catch {
    res = await fetch(
      apiUrl('/rest/api/2/project/search?maxResults=50&orderBy=name'),
      { headers: getAuthHeaders(), signal: AbortSignal.timeout(15000) }
    );
  }

  if (!res.ok) {
    if (res.status >= 400) {
      res = await fetch(
        apiUrl('/rest/api/2/project/search?maxResults=50&orderBy=name'),
        { headers: getAuthHeaders(), signal: AbortSignal.timeout(15000) }
      );
    }
    if (!res.ok) {
      throw new Error(`Failed to fetch Jira projects: ${res.status} ${res.statusText}`);
    }
  }

  const data = await res.json();
  const projects = data.values ?? data ?? [];

  return projects.map((p: any) => ({
    id: p.id,
    key: p.key,
    name: p.name,
    avatarUrl: p.avatarUrls?.['24x24'],
  }));
}

/**
 * Fetch epics in a given Jira project.
 * Tries issuetype=Epic first, then hierarchyLevel=1, then all issues.
 */
export async function fetchEpics(projectKey: string): Promise<JiraIssue[]> {
  // Approach 1: Standard Epic issuetype
  try {
    const issues = await searchJql(
      `project=${projectKey} AND issuetype=Epic ORDER BY updated DESC`
    );
    if (issues.length > 0) {
      return issues.map(mapIssue);
    }
  } catch (err) {
    console.warn('Epic query failed, trying fallbacks:', err);
  }

  // Approach 2: hierarchyLevel=1 (next-gen projects where Epic may have different name)
  try {
    const issues = await searchJql(
      `project=${projectKey} AND hierarchyLevel=1 ORDER BY updated DESC`
    );
    if (issues.length > 0) {
      return issues.map(mapIssue);
    }
  } catch (err) {
    console.warn('hierarchyLevel query failed:', err);
  }

  // Approach 3: All issues as fallback
  const issues = await searchJql(
    `project=${projectKey} ORDER BY updated DESC`
  );
  return issues.map(mapIssue);
}

/**
 * Fetch user stories (Story type) that belong to a specific epic.
 * Uses parent=KEY for next-gen projects, "Epic Link"=KEY for classic.
 */
export async function fetchUserStoriesByEpic(epicKey: string): Promise<JiraIssue[]> {
  // Approach 1: parent=KEY (next-gen / team-managed projects)
  try {
    const issues = await searchJql(
      `parent=${epicKey} ORDER BY updated DESC`,
      100
    );
    if (issues.length > 0) {
      return issues.map(mapIssue);
    }
  } catch (err) {
    console.warn('parent= query failed, trying Epic Link:', err);
  }

  // Approach 2: "Epic Link"=KEY (classic / company-managed projects)
  try {
    const issues = await searchJql(
      `"Epic Link"=${epicKey} AND issuetype=Story ORDER BY updated DESC`,
      100
    );
    return issues.map(mapIssue);
  } catch (err) {
    console.warn('Epic Link query also failed:', err);
  }

  return [];
}

/**
 * Fetch all epics in a project with their user stories populated.
 * Fetches stories in batches to avoid Jira API rate limiting,
 * and retries once on failure per epic.
 */
export async function fetchEpicsWithStories(projectKey: string): Promise<JiraIssue[]> {
  const epics = await fetchEpics(projectKey);

  // Process epics in batches of 5 to avoid overwhelming the Jira API
  const BATCH_SIZE = 5;
  const epicsWithStories: JiraIssue[] = [];

  for (let i = 0; i < epics.length; i += BATCH_SIZE) {
    const batch = epics.slice(i, i + BATCH_SIZE);
    const results = await Promise.all(
      batch.map(async (epic) => {
        try {
          const stories = await fetchUserStoriesByEpic(epic.key);
          if (stories.length > 0) {
            return { ...epic, children: stories };
          }
          return epic;
        } catch {
          // Retry once after a short delay
          try {
            await new Promise(r => setTimeout(r, 1000));
            const stories = await fetchUserStoriesByEpic(epic.key);
            if (stories.length > 0) {
              return { ...epic, children: stories };
            }
          } catch {
            // Give up for this epic
          }
          return epic;
        }
      })
    );
    epicsWithStories.push(...results);
  }

  return epicsWithStories;
}

/**
 * Search Jira issues by text (summary).
 */
export async function searchJiraIssues(
  query: string,
  projectKey?: string
): Promise<JiraIssue[]> {
  const trimmed = query.trim();
  if (!trimmed) return [];

  const isFullKey = /^[A-Z][A-Z0-9]+-\d+$/i.test(trimmed);     // e.g. WEGAAIDEMO-2652
  const isNumeric = /^\d+$/.test(trimmed);                       // e.g. 2652

  const conditions: string[] = [];

  if (isFullKey) {
    conditions.push(`key = "${trimmed.toUpperCase()}"`);
  } else if (isNumeric && projectKey) {
    // User typed just a number — search by full key like PROJECT-NUMBER
    conditions.push(`key = "${projectKey}-${trimmed}"`);
  }

  // Always also do text search on summary & description
  conditions.push(`summary~"${trimmed}"`);
  conditions.push(`description~"${trimmed}"`);

  let jql = `(${conditions.join(' OR ')}) AND issuetype in (Epic, Story)`;
  if (projectKey) {
    jql += ` AND project=${projectKey}`;
  }
  jql += ' ORDER BY updated DESC';

  const issues = await searchJql(jql, 50);
  return issues.map(mapIssue);
}

/**
 * Fetch test cases linked to a given story key.
 * Primary approach: search by label matching the story key (e.g. labels = "WEGAAIDEMO-701").
 * Fallbacks: parent=KEY, linkedIssues, all children.
 */
export async function fetchTestCasesByStory(storyKey: string): Promise<JiraIssue[]> {
  // Approach 1 (primary): Test cases labeled with the story key
  try {
    const issues = await searchJql(
      `labels = "${storyKey}" ORDER BY key ASC`,
      100
    );
    if (issues.length > 0) {
      return issues.map(mapIssue);
    }
  } catch (err) {
    console.warn('label query for test cases failed:', err);
  }

  // Approach 2: child issues of type Test under the story
  try {
    const issues = await searchJql(
      `parent=${storyKey} AND issuetype in (Test, "Test Case", Bug, Sub-task, Task) ORDER BY key ASC`,
      100
    );
    if (issues.length > 0) {
      return issues.map(mapIssue);
    }
  } catch (err) {
    console.warn('parent= query for test cases failed:', err);
  }

  // Approach 3: linked issues (issue in linkedIssues)
  try {
    const issues = await searchJql(
      `issue in linkedIssues(${storyKey}) AND issuetype in (Test, "Test Case") ORDER BY key ASC`,
      100
    );
    if (issues.length > 0) {
      return issues.map(mapIssue);
    }
  } catch (err) {
    console.warn('linkedIssues query for test cases failed:', err);
  }

  // Approach 4: All child issues regardless of type
  try {
    const issues = await searchJql(
      `parent=${storyKey} ORDER BY key ASC`,
      100
    );
    if (issues.length > 0) {
      return issues.map(mapIssue);
    }
  } catch (err) {
    console.warn('All child issues query failed:', err);
  }

  return [];
}

/**
 * Fetch test steps (child issues) for a given test case key.
 * Primary: fetches from Xray Cloud GraphQL API.
 * Fallback: fetches child issues from Jira if Xray returns nothing.
 */
export async function fetchTestStepsByTestCase(testCaseKey: string): Promise<{ Step: string; Expected: string }[]> {
  // Primary: Xray Cloud test steps
  try {
    const { fetchTestStepsFromXray } = await import('./xrayApi');
    const xraySteps = await fetchTestStepsFromXray(testCaseKey);
    if (xraySteps.length > 0) {
      return xraySteps;
    }
  } catch (err) {
    console.warn('Xray test steps fetch failed for', testCaseKey, ', falling back to Jira:', err);
  }

  // Fallback: child issues of the test case (sub-tasks / steps)
  try {
    const issues = await searchJql(
      `parent=${testCaseKey} ORDER BY key ASC`,
      100
    );
    if (issues.length > 0) {
      return issues.map((issue: any) => ({
        Step: issue.fields?.summary || '',
        Expected: extractDescription(issue.fields?.description) || '',
      }));
    }
  } catch (err) {
    console.warn('Jira child-issue fallback also failed for', testCaseKey, err);
  }

  return [];
}