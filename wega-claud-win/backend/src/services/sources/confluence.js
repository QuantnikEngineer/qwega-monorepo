// Confluence source — stub for v1. The orchestrator's Atlassian MCP path
// already authenticates against Confluence, but pulling pages by space/label
// and dumping their storage HTML into clean text for embedding is its own
// project. Marked as "not yet wired" so the UI surface is honest about the
// gap rather than silently shipping empty results.
//
// To implement when ready: read cfg.spaceKey + cfg.label, call the Atlassian
// MCP getPagesInConfluenceSpace + getConfluencePage tools, run each page's
// storage HTML through cheerio (same pattern as website.js), emit one
// document per page.

export async function fetchDocuments(/* source */) {
  throw new Error(
    'Confluence ingest is not yet wired. The Atlassian MCP is authenticated for chat, ' +
    'but the Context Fabric ingest path needs an explicit pages-pull implementation. ' +
    'Tracked as a follow-up.'
  );
}
