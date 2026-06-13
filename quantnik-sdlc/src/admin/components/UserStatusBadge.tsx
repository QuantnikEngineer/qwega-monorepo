/**
 * UserStatusBadge
 *
 * Color-coded badge for user account status.
 * Uses inline styles for reliable dark-mode rendering (Tailwind v4 doesn't
 * generate all color utilities in the compiled CSS).
 */

import type React from 'react';
import { Badge } from '../../components/ui/badge';

interface UserStatusBadgeProps {
  status: string;
}

const STATUS_STYLES: Record<string, React.CSSProperties> = {
  active: { backgroundColor: 'rgba(34, 197, 94, 0.15)', color: '#4ade80', borderColor: 'rgba(34, 197, 94, 0.3)' },
  pending: { backgroundColor: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', borderColor: 'rgba(245, 158, 11, 0.3)' },
  suspended: { backgroundColor: 'rgba(249, 115, 22, 0.15)', color: '#fb923c', borderColor: 'rgba(249, 115, 22, 0.3)' },
  deactivated: { backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#f87171', borderColor: 'rgba(239, 68, 68, 0.3)' },
};

const FALLBACK_STYLE: React.CSSProperties = {
  backgroundColor: 'rgba(148, 163, 184, 0.15)',
  color: '#94a3b8',
  borderColor: 'rgba(148, 163, 184, 0.3)',
};

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function UserStatusBadge({ status }: UserStatusBadgeProps) {
  const label = capitalize(status);
  const styles = STATUS_STYLES[status] ?? FALLBACK_STYLE;

  return (
    <Badge variant="outline" style={styles} aria-label={`Status: ${label}`}>
      {label}
    </Badge>
  );
}
