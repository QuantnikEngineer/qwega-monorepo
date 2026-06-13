/**
 * Confluence Cloud REST API Service
 *
 * Uses the Confluence Cloud REST API v2 to fetch spaces and pages from the
 * configured Atlassian site, building a proper parent-child tree from the
 * flat page list using parentId / parentType fields.
 *
 * Client-side environment variable (set in .env, used as fallback):
 *   VITE_CONFLUENCE_SPACE_ID – specific space ID to load
 *
 * Authentication:
 *   - Browser sends JWT Bearer token to the gateway.
 *   - Gateway resolves project-scoped Atlassian credentials and injects
 *     Basic auth for upstream Confluence calls.
 *   - The browser NEVER handles Atlassian credentials.
 */

import { getAccessToken } from '../auth/tokenManager';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ConfluenceSpace {
  id: string;
  key: string;
  name: string;
  type: string;
}

export interface ConfluencePage {
  id: string;
  title: string;
  date: string; // formatted date string
  children?: ConfluencePage[];
  parentId?: string | null;
  parentType?: string | null;
  isFolder?: boolean; // true for folder-type parents
}

interface ConfluenceV2Page {
  id: string;
  title: string;
  status: string;
  createdAt?: string;
  version?: { createdAt?: string };
  childPosition?: number;
  parentId?: string | null;
  parentType?: string | null;
  spaceId?: string;
}

interface ConfluenceV2PagesResponse {
  results: ConfluenceV2Page[];
  _links?: { next?: string };
}

// ---------------------------------------------------------------------------
// Config helpers
// ---------------------------------------------------------------------------

/* eslint-disable @typescript-eslint/no-explicit-any */
const _FALLBACK_SPACE_ID: string = import.meta.env.VITE_CONFLUENCE_SPACE_ID || '36569092';

const _FALLBACK_BASE_URL: string = import.meta.env.VITE_ATLASSIAN_BASE_URL || 'https://quantnikbuildiq.atlassian.net';

// Runtime config — set by Execute.tsx when project tool settings load
let _runtimeConfig: { spaceId?: string; spaceKey?: string; baseUrl?: string } = {};

/**
 * Set runtime Confluence config from project tool settings.
 * Called by Execute.tsx when useProjectToolConfig returns data.
 */
export function setConfluenceConfig(config: { spaceId?: string; spaceKey?: string; baseUrl?: string }): void {
  _runtimeConfig = config;
}

function getSpaceId(): string {
  return _runtimeConfig.spaceId || _FALLBACK_SPACE_ID;
}

function getBaseUrl(): string {
  return _runtimeConfig.baseUrl || _FALLBACK_BASE_URL;
}

/**
 * Build a browser-navigable URL for a Confluence page.
 */
export function confluenceBrowseUrl(pageId: string, pageTitle: string, spaceKey?: string): string {
  const base = getBaseUrl();
  const space = spaceKey || _runtimeConfig.spaceKey || 'WAAD';
  const encodedTitle = encodeURIComponent(pageTitle).replace(/%20/g, '+');
  return `${base}/wiki/spaces/${space}/pages/${pageId}/${encodedTitle}`;
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
 * Build the full API URL.
 * Routes through the gateway at `/confluence-api/` to bypass CORS.
 */
function apiUrl(path: string): string {
  return `/confluence-api${path}`;
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

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Return the configured space ID from the environment variable, if any.
 */
export function getConfiguredSpaceId(): string | undefined {
  return getSpaceId();
}

/**
 * Fetch a single Confluence space by its ID.
 * Uses the v2 API: GET /api/v2/spaces/{id}
 */
export async function fetchConfluenceSpaceById(spaceId: string): Promise<ConfluenceSpace> {
  const res = await fetch(apiUrl(`/api/v2/spaces/${encodeURIComponent(spaceId)}`), {
    headers: getAuthHeaders(),
    signal: AbortSignal.timeout(15000),
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch Confluence space ${spaceId}: ${res.status} ${res.statusText}`);
  }

  const s: any = await res.json();
  return {
    id: s.id,
    key: s.key,
    name: s.name,
    type: s.type,
  };
}

/**
 * Fetch all Confluence spaces the authenticated user can see.
 */
export async function fetchConfluenceSpaces(): Promise<ConfluenceSpace[]> {
  const res = await fetch(apiUrl('/api/v2/spaces?limit=50&sort=name'), {
    headers: getAuthHeaders(),
    signal: AbortSignal.timeout(15000),
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch Confluence spaces: ${res.status} ${res.statusText}`);
  }

  const data = await res.json();

  return (data.results ?? []).map((s: any) => ({
    id: s.id,
    key: s.key,
    name: s.name,
    type: s.type,
  }));
}

/**
 * Fetch all pages in a space using the v2 API and build a parent-child tree.
 *
 * The v2 endpoint GET /api/v2/spaces/{spaceId}/pages returns a flat list
 * where each page has:
 *   - parentId: null (root page) or an ID
 *   - parentType: null | "page" | "folder"
 *
 * Pages with parentType "folder" are children of a Confluence folder (not a page).
 * We fetch those folders separately to get their titles, then assemble the tree.
 */
export async function fetchConfluencePagesTree(spaceKey: string): Promise<ConfluencePage[]> {
  const spaceId = getSpaceId() || spaceKey;

  // Step 1: Fetch all pages in the space (flat list)
  const pagesRes = await fetch(
    apiUrl(`/api/v2/spaces/${encodeURIComponent(spaceId)}/pages?limit=250&sort=-modified-date`),
    {
      headers: getAuthHeaders(),
      signal: AbortSignal.timeout(15000),
    }
  );
  if (!pagesRes.ok) throw new Error(`Failed to fetch pages: ${pagesRes.status}`);
  const pagesData = await pagesRes.json();
  const allPages: any[] = pagesData.results || [];

  // Filter out pages that have no parentId (root pages / space overview)
  const pagesWithParent = allPages.filter(
    (page) => page.parentId !== null && page.parentId !== undefined
  );

  // Step 2: Collect unique folder parentIds (parentType === "folder")
  const folderIds = new Set<string>();
  for (const page of pagesWithParent) {
    if (page.parentType === 'folder' && page.parentId) {
      folderIds.add(page.parentId);
    }
  }

  // Step 3: Fetch folder details to get folder titles
  const folderMap = new Map<string, { id: string; title: string }>();
  for (const folderId of folderIds) {
    try {
      const folderRes = await fetch(
        apiUrl(`/api/v2/folders/${encodeURIComponent(folderId)}`),
        {
          headers: getAuthHeaders(),
          signal: AbortSignal.timeout(15000),
        }
      );
      if (folderRes.ok) {
        const folderData = await folderRes.json();
        folderMap.set(folderId, {
          id: folderData.id,
          title: folderData.title || `Folder ${folderId}`,
        });
      }
    } catch (err) {
      console.warn(`Failed to fetch folder ${folderId}:`, err);
      folderMap.set(folderId, { id: folderId, title: `Folder ${folderId}` });
    }
  }

  // Step 4: Build tree structure
  // Group pages by their parentId
  const childrenByParent = new Map<string, ConfluencePage[]>();
  const standalonePages: ConfluencePage[] = [];

  for (const page of pagesWithParent) {
    const confluencePage: ConfluencePage = {
      id: page.id,
      title: page.title,
      date: page.createdAt
        ? new Date(page.createdAt).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
          })
        : '',
      parentId: page.parentId,
      parentType: page.parentType,
    };

    if (page.parentType === 'folder' && page.parentId) {
      // This page belongs to a folder
      if (!childrenByParent.has(page.parentId)) {
        childrenByParent.set(page.parentId, []);
      }
      childrenByParent.get(page.parentId)!.push(confluencePage);
    } else if (page.parentType === 'page' && page.parentId) {
      // This page is a child of another page
      if (!childrenByParent.has(page.parentId)) {
        childrenByParent.set(page.parentId, []);
      }
      childrenByParent.get(page.parentId)!.push(confluencePage);
    } else {
      // Page has parentId but unknown parentType — treat as standalone
      standalonePages.push(confluencePage);
    }
  }

  // Step 5: Build final tree
  const tree: ConfluencePage[] = [];

  // Add folders as parent nodes with their child pages
  for (const [folderId, folderInfo] of folderMap) {
    const children = childrenByParent.get(folderId) || [];
    tree.push({
      id: folderId,
      title: folderInfo.title,
      date: '',
      children: children.length > 0 ? children : [],
    });
  }

  // Add standalone pages (pages with parent but not folder/page type)
  for (const page of standalonePages) {
    tree.push(page);
  }

  return tree;
}

/**
 * Fetch child pages of a given parent page (for lazy loading on expand).
 */
export async function fetchChildPages(parentPageId: string): Promise<ConfluencePage[]> {
  const res = await fetch(
    apiUrl(`/api/v2/pages/${encodeURIComponent(parentPageId)}/children?limit=100`),
    {
      headers: getAuthHeaders(),
      signal: AbortSignal.timeout(15000),
    }
  );

  if (!res.ok) {
    throw new Error(`Failed to fetch child pages: ${res.status} ${res.statusText}`);
  }

  const data: ConfluenceV2PagesResponse = await res.json();

  return (data.results || []).map((p) => ({
    id: p.id,
    title: p.title,
    date: formatDate(p.createdAt || p.version?.createdAt),
  }));
}

/**
 * Search Confluence pages by title (CQL query).
 */
export async function searchConfluencePages(query: string, spaceKey?: string): Promise<ConfluencePage[]> {
  let cql = `type=page AND title~"${query}"`;
  if (spaceKey) {
    cql += ` AND space.key="${spaceKey}"`;
  }

  const res = await fetch(
    apiUrl(`/rest/api/content/search?cql=${encodeURIComponent(cql)}&expand=version,history&limit=25`),
    {
      headers: getAuthHeaders(),
      signal: AbortSignal.timeout(15000),
    }
  );

  if (!res.ok) {
    throw new Error(`Confluence search failed: ${res.status} ${res.statusText}`);
  }

  const data = await res.json();

  return (data.results || []).map((p: any) => ({
    id: p.id,
    title: p.title,
    date: formatDate(p.version?.when || p.history?.createdDate),
  }));
}