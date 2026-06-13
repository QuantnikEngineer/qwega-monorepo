// ── Cron Job API Service ──
// Types and functions for tracking long-running test case generation jobs
// All requests route through API Gateway via apiFetch (ENFC-02).

import { apiFetch } from './apiClient';

const ALLOWED_POLL_PATH = /^\/?(?:api\/)?v1\/jobs\//;

// ── Types ──

export interface BulkUserStory {
  userStoryJiraId: string;
  userStory: string;
}

export interface BulkTestCaseRequest {
  userStories: BulkUserStory[];
  ScenarioType: string;
}

export interface BulkTestCaseResponse {
  job_id: string;
  total: number;
  message: string;
  poll_url: string;
}

export type CronJobStoryStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface CronJobStory {
  index: number;
  userStoryJiraId: string;
  status: CronJobStoryStatus;
  error?: string;
}

export type CronJobStatus = 'queued' | 'running' | 'processing' | 'pending' | 'scheduled' | 'completed' | 'failed';

export interface CronJobDetail {
  job_id: string;
  status: CronJobStatus;
  total: number;
  completed_count: number;
  failed_count: number;
  stories: CronJobStory[];
}

export interface CronJob {
  jobId: string;
  jobName: string;
  status: CronJobStatus;
  agentType: 'Test Case Agent' | 'Test Script Agent';
  /** Alias used by the UI panel ('test-case' | 'test-script') */
  type: 'test-case' | 'test-script';
  total: number;
  completedCount: number;
  failedCount: number;
  createdAt: string;
  /** Jira story keys + summaries submitted with this job */
  stories?: { key: string; summary: string }[];
  detail?: CronJobDetail;
}

// ── API Functions ──

/**
 * Submit user stories for bulk test case generation.
 * Returns a job_id that can be polled for status.
 */
export async function submitBulkTestCases(
  request: BulkTestCaseRequest,
): Promise<BulkTestCaseResponse> {
  const response = await apiFetch('/api/v1/generate-test-cases/bulk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const errBody = await response.text();
    throw new Error(`Bulk submit failed (${response.status}): ${errBody}`);
  }
  return response.json();
}

/**
 * Normalize a poll URL to a gateway-safe relative path.
 * Strips absolute origins and validates the path matches the expected jobs route.
 * Preserves query parameters for forward compatibility.
 */
function normalizePollUrl(pollUrl: string): string | null {
  try {
    const parsed = new URL(pollUrl, window.location.origin);
    const pathWithSearch = parsed.pathname + parsed.search;
    if (ALLOWED_POLL_PATH.test(parsed.pathname)) {
      const normalized = pathWithSearch.startsWith('/') ? pathWithSearch : `/${pathWithSearch}`;
      return normalized.startsWith('/api/') ? normalized : `/api${normalized}`;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Fetch the latest status for a given job, including per-story breakdown.
 */
export async function fetchJobStatus(jobId: string, pollUrl?: string): Promise<CronJobDetail> {
  let url = `/api/v1/jobs/${encodeURIComponent(jobId)}`;
  if (pollUrl) {
    const normalized = normalizePollUrl(pollUrl);
    if (normalized) {
      url = normalized;
    }
  }
  const response = await apiFetch(url, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    const errBody = await response.text();
    throw new Error(`Job status fetch failed (${response.status}): ${errBody}`);
  }
  return response.json();
}

/**
 * Retry failed stories for a given job.
 * POST /v1/jobs/{job-id}/retry-failed
 */
export async function retryFailedStories(jobId: string): Promise<void> {
  const url = `/api/v1/jobs/${encodeURIComponent(jobId)}/retry-failed`;
  const response = await apiFetch(url, {
    method: 'POST',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    const errBody = await response.text();
    throw new Error(`Retry failed stories failed (${response.status}): ${errBody}`);
  }
}

/**
 * Generate a human-readable job name from the first user story key + timestamp.
 */
export function generateJobName(prefix: string, count: number): string {
  const ts = new Date().toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  return `${prefix}_${count}stories_${ts}`;
}