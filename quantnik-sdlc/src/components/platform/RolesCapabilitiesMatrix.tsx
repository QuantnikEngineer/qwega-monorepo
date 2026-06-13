/**
 * RolesCapabilitiesMatrix
 *
 * Standalone, embeddable component that displays the live RBAC matrix
 * fetched from the auth service. Shows roles as columns and capabilities
 * grouped by category as rows — with accordion-based category collapsing.
 *
 * Props:
 *  - compact: Omit the section header/description (for embedding in other contexts)
 *  - className: Additional CSS classes for the wrapper
 *
 * Data source: GET /api/roles/capabilities (via useCapabilityMatrix hook)
 * Caching: 5-min staleTime on TanStack Query + backend Cache-Control: 300s
 */

import { Fragment, useState } from 'react';
import { Check, AlertCircle, RefreshCw, ChevronDown, Shield } from 'lucide-react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Skeleton } from '../ui/skeleton';
import { useRoles, useCapabilityMatrix } from '../../admin/hooks/useRoles';
import { getRoleDisplayName } from '../../constants/roleLabels';
import { getCapabilityLabel, CATEGORY_ORDER } from '../../constants/capabilityLabels';
import { cn } from '../ui/utils';

interface RolesCapabilitiesMatrixProps {
  compact?: boolean;
  className?: string;
}

/** Brand colors for role badges (consistent with platform palette). */
const ROLE_COLORS: Record<string, string> = {
  superadmin: '#351A55',
  pm: '#355493',
  po_sm_ba: '#3498B3',
  developer: '#746FA7',
  tester: '#BE266A',
  mlops: '#00ADE4',
};

export function RolesCapabilitiesMatrix({ compact = false, className }: RolesCapabilitiesMatrixProps) {
  const { data: rolesData, isLoading: rolesLoading } = useRoles();
  const { data: matrixData, isLoading: matrixLoading, isError, refetch } = useCapabilityMatrix();

  const isLoading = rolesLoading || matrixLoading;
  const roles = rolesData?.roles ?? [];
  const categories = matrixData?.categories ?? {};
  const roleNames = roles.map((r) => r.name);

  // Sort categories by defined order
  const sortedCategories = [
    ...CATEGORY_ORDER.filter((c) => c in categories),
    ...Object.keys(categories).filter((c) => !CATEGORY_ORDER.includes(c)),
  ];

  // Accordion state: all categories expanded by default
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());

  const toggleCategory = (category: string) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  return (
    <div className={cn('w-full', className)}>
      {/* Section header (omitted in compact mode) */}
      {!compact && (
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2.5 rounded-lg bg-[#746FA7]/10">
              <Shield className="w-6 h-6 text-[#746FA7]" />
            </div>
            <h2 className="text-foreground">Platform Access &amp; Capabilities</h2>
          </div>
          <p className="text-muted-foreground max-w-3xl">
            Explore the role-based access model that powers QUANTNIK — every team member gets exactly the
            tools and permissions they need for their function.
          </p>
        </div>
      )}

      {/* Error state */}
      {isError ? (
        <Card className="p-8">
          <div className="flex flex-col items-center justify-center text-center gap-3">
            <AlertCircle className="size-8 text-destructive" />
            <p className="text-sm text-muted-foreground">Failed to load capability data</p>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="size-3 mr-1" />
              Retry
            </Button>
          </div>
        </Card>
      ) : isLoading ? (
        /* Skeleton loading state */
        <Card className="p-6">
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        </Card>
      ) : (
        <Card className="p-0 overflow-hidden">
          {/* Desktop: scrollable table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-card border-b">
                <tr>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground min-w-[200px]">
                    Capability
                  </th>
                  {roleNames.map((name) => (
                    <th
                      key={name}
                      className="text-center py-3 px-3 font-medium whitespace-nowrap"
                    >
                      <Badge
                        variant="outline"
                        className="text-xs font-semibold"
                        style={{
                          borderColor: ROLE_COLORS[name] ?? '#6b7280',
                          color: ROLE_COLORS[name] ?? '#6b7280',
                        }}
                      >
                        {getRoleDisplayName(name)}
                      </Badge>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedCategories.map((category) => {
                  const isCollapsed = collapsedCategories.has(category);
                  const caps = categories[category] ?? [];
                  return (
                    <Fragment key={`cat-${category}`}>
                      {/* Category header row — clickable to collapse */}
                      <tr
                        className="cursor-pointer hover:bg-muted/50 transition-colors"
                        onClick={() => toggleCategory(category)}
                      >
                        <td
                          colSpan={roleNames.length + 1}
                          className="py-2.5 px-4 bg-muted/30"
                        >
                          <div className="flex items-center gap-2">
                            <ChevronDown
                              className={cn(
                                'size-4 text-muted-foreground transition-transform duration-200',
                                isCollapsed && '-rotate-90'
                              )}
                            />
                            <span className="text-sm font-semibold text-muted-foreground">
                              {category}
                            </span>
                            <span className="text-xs text-muted-foreground/60">
                              ({caps.length})
                            </span>
                          </div>
                        </td>
                      </tr>
                      {/* Capability rows (hidden when collapsed) */}
                      {!isCollapsed &&
                        caps.map((cap) => (
                          <tr
                            key={cap.name}
                            className="border-b border-border/30 hover:bg-muted/20 transition-colors"
                          >
                            <td className="py-2.5 px-4 text-sm text-foreground pl-8">
                              {getCapabilityLabel(cap.name)}
                            </td>
                            {roleNames.map((role) => (
                              <td key={role} className="text-center py-2.5 px-3">
                                {cap.roles.includes(role) ? (
                                  <Check className="inline-block h-4 w-4 text-green-600" />
                                ) : (
                                  <span className="inline-block h-4 w-4 text-muted-foreground/30">—</span>
                                )}
                              </td>
                            ))}
                          </tr>
                        ))}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile: card-per-role layout */}
          <div className="md:hidden p-4 space-y-4">
            {roleNames.map((roleName) => {
              const roleCapabilities = sortedCategories.flatMap((cat) =>
                (categories[cat] ?? [])
                  .filter((cap) => cap.roles.includes(roleName))
                  .map((cap) => ({ ...cap, category: cat }))
              );
              return (
                <Card key={roleName} className="p-4 border">
                  <div className="flex items-center gap-2 mb-3">
                    <Badge
                      className="text-xs font-semibold text-white"
                      style={{ backgroundColor: ROLE_COLORS[roleName] ?? '#6b7280' }}
                    >
                      {getRoleDisplayName(roleName)}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {roleCapabilities.length} capabilities
                    </span>
                  </div>
                  <div className="space-y-1">
                    {roleCapabilities.map((cap) => (
                      <div key={cap.name} className="flex items-center gap-2 text-sm">
                        <Check className="h-3.5 w-3.5 text-green-600 flex-shrink-0" />
                        <span className="text-foreground">{getCapabilityLabel(cap.name)}</span>
                      </div>
                    ))}
                  </div>
                </Card>
              );
            })}
          </div>

          {/* Footer */}
          <div className="px-4 py-3 border-t bg-muted/20">
            <p className="text-xs text-muted-foreground">
              Roles are system-defined and evolve with the platform. This matrix reflects the current
              deployed configuration.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
