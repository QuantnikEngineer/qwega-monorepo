/**
 * Capability Display Labels
 *
 * Human-readable labels for system-defined capabilities.
 * Used by both the AdminFAB Roles dialog and the University RBAC matrix.
 * Only capabilities returned by /api/roles/capabilities are rendered —
 * this map provides friendly display names as a fallback.
 */

export const CAPABILITY_LABELS: Record<string, string> = {
  'platform:manage': 'Manage Platform',
  'org:manage_users': 'Manage Users',
  'org:manage_settings': 'Manage Org Settings',
  'project:manage': 'Manage Project',
  'project:create': 'Create Project',
  'project:manage_members': 'Manage Team Members',
  'project:configure_integrations': 'Configure Integrations',
  'team:manage_users': 'Manage Team Users',
  'sdlc:execute': 'Execute SDLC Agents',
  'sdlc:view_pipelines': 'View Pipelines',
  'integration:configure_tools': 'Configure Tools',
  'integration:use_tools': 'Use Integration Tools',
  'settings:manage_own': 'Manage Own Settings',
  'admin:view_audit_log': 'View Audit Log',
  'admin:manage_sessions': 'Manage Sessions',
};

/** Category display ordering — matches backend _CAPABILITY_CATEGORIES keys. */
export const CATEGORY_ORDER = [
  'Platform',
  'Organization',
  'Project',
  'Team',
  'SDLC',
  'Integrations',
  'Settings',
  'Admin',
  'Other',
];

export function getCapabilityLabel(capName: string): string {
  return CAPABILITY_LABELS[capName] ?? capName;
}
