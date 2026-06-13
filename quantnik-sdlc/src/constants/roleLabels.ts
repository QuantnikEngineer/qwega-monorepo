/**
 * Role Display Names
 *
 * Maps role keys (from backend) to human-readable labels for all UI surfaces (D-20).
 * Single source of truth — use getRoleDisplayName() everywhere.
 */

export const ROLE_DISPLAY_NAMES: Record<string, string> = {
  superadmin: 'SuperAdmin',
  pm: 'PM',
  po_sm_ba: 'PO / SM / BA',
  developer: 'Developer',
  tester: 'Tester',
  mlops: 'MLOps',
};

export function getRoleDisplayName(roleKey: string): string {
  return ROLE_DISPLAY_NAMES[roleKey] ?? roleKey;
}
