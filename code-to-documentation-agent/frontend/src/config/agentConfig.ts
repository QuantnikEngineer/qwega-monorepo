const API_CONFIG = {
  DOMAIN: 'http://localhost', // Replace with your actual API domain
  PORT: 8002, // Updated to match backend port (documentation agent)
  ENDPOINTS: {
    INIT_SECRETS: "/api/init-secrets", // Endpoint to initialize secrets from backend
    GET_AGENT_PROMPTS: "/get-agent-prompts", // New endpoint for getting agent prompts
    EXECUTE_CHAT: '/execute-chat', // Example endpoint for agent chat
    DOWNLOAD_DOCUMENT: '/download', // Endpoint to download documents (append /{document_id})
    UPLOAD_TO_SHAREPOINT: "/upload-to-sharepoint",
    UPLOAD_TO_CONFLUENCE: "/upload-to-confluence",
    LIST_CONFLUENCE_PAGES: "/confluence-pages", // Endpoint for listing Confluence pages
    CONTENT_FROM_CONFLUENCE_PAGE: "/confluence-page-content", // Endpoint for extracting Confluence page content (append /{page_id})
    LIST_SHAREPOINT_FILES: "/sharepoint-files",
    DOWNLOAD_SHAREPOINT_FILE: "/sharepoint-files",
    LLM_CONFIG: "/llm-config", // New endpoint for fetching LLM config
    RAG_KB_DOCS: "/rag-kb-docs", // Endpoint for generating RAG embeddings
  },
};

const runtimeEnv =
  typeof window !== 'undefined' && (window as any).__env
    ? (window as any).__env
    : undefined;

const readEnv = (key: string): string | undefined =>
  runtimeEnv?.[key] ?? process.env[key as keyof typeof process.env];

const FALLBACK_FRONTEND_URL =
  typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000';

const rawFrontendUrl = readEnv('BUILD_AI_FRONTEND_URL');
export const BUILD_AI_FRONTEND_URL = rawFrontendUrl != null && rawFrontendUrl !== ''
  ? rawFrontendUrl.replace(/\/+$/, '')
  : FALLBACK_FRONTEND_URL.replace(/\/+$/, '');

// Full access projects - comma-separated list of project IDs/names that have access to all repositories
const rawFullAccessProjects = readEnv('REACT_APP_FULL_ACCESS_PROJECTS');
export const FULL_ACCESS_PROJECTS: string[] = rawFullAccessProjects 
  ? rawFullAccessProjects.split(',').map(p => p.trim().toLowerCase())
  : ['allprojects', 'demo1']; // Default fallback list

// Items per page for pagination - configurable via deployment YAML
export const getItemsPerPage = (): number => {
  const rawItemsPerPage = readEnv('REACT_APP_ITEMS_PER_PAGE');
  if (rawItemsPerPage != null && rawItemsPerPage !== '') {
    const parsed = parseInt(rawItemsPerPage, 10);
    if (!isNaN(parsed) && parsed > 0) {
      return parsed;
    }
  }
  return 20; // Default fallback value
};

export default API_CONFIG;