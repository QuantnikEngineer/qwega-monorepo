// SharePoint source — stub for v1. SharePoint ingest needs an OAuth handshake
// against Microsoft Graph (`/sites/{site-id}/drives/{drive-id}/root/children`
// + delegated/app permissions), which is non-trivial setup specific to each
// tenant. The Context Engine UI exposes the form so users can register their
// intent; ingest is intentionally rejected until the Graph plumbing is wired.
//
// To implement: take cfg.siteUrl + cfg.driveId + OAuth tokens (from a quantnik-
// level Microsoft Graph app), enumerate drive items, download text/PDF
// content, emit one document per file.

export async function fetchDocuments(/* source */) {
  throw new Error(
    'SharePoint ingest is not yet wired. Needs a Microsoft Graph OAuth app + ' +
    'delegated permissions per tenant. The source registration is recorded so ' +
    'the UI shows the planned scope, but ingest will fail until Graph is plumbed.'
  );
}
