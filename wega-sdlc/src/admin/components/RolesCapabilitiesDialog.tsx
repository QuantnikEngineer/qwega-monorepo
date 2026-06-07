/**
 * RolesCapabilitiesDialog
 *
 * Read-only dialog showing the system-defined capability matrix.
 * Displays roles as columns and capabilities grouped by category as rows.
 * Check marks indicate which roles have which capabilities.
 * No edit actions — roles are system-defined (D-05/D-06).
 */

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { Skeleton } from '../../components/ui/skeleton';
import { Button } from '../../components/ui/button';
import { Check, AlertCircle, RefreshCw } from 'lucide-react';
import { Fragment } from 'react';

import { useRoles } from '../hooks/useRoles';
import { useCapabilityMatrix } from '../hooks/useRoles';
import { getRoleDisplayName } from '../../constants/roleLabels';
import { getCapabilityLabel, CATEGORY_ORDER } from '../../constants/capabilityLabels';

interface RolesCapabilitiesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RolesCapabilitiesDialog({ open, onOpenChange }: RolesCapabilitiesDialogProps) {
  const { data: rolesData, isLoading: rolesLoading } = useRoles();
  const { data: matrixData, isLoading: matrixLoading, isError, refetch } = useCapabilityMatrix();

  const isLoading = rolesLoading || matrixLoading;
  const roles = rolesData?.roles ?? [];
  const categories = matrixData?.categories ?? {};
  const roleNames = roles.map((r) => r.name);

  // Category display order
  const sortedCategories = [
    ...CATEGORY_ORDER.filter((c) => c in categories),
    ...Object.keys(categories).filter((c) => !CATEGORY_ORDER.includes(c)),
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>Roles &amp; Capabilities</DialogTitle>
          <DialogDescription>
            System-defined roles and their capabilities. Roles cannot be modified.
          </DialogDescription>
        </DialogHeader>

        {isError ? (
          <div className="flex flex-col items-center justify-center py-12 text-center gap-3">
            <AlertCircle className="size-8 text-destructive" />
            <p className="text-sm text-muted-foreground">Failed to load capability data</p>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="size-3 mr-1" />
              Retry
            </Button>
          </div>
        ) : isLoading ? (
          <div className="space-y-3 py-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : (
          <>
            <div className="flex-1 min-h-0 overflow-auto scrollbar-thin">
              <table className="min-w-[600px] w-full text-sm">
                <thead className="sticky top-0 z-10 bg-card">
                  <tr className="border-b">
                    <th className="text-left py-2 px-3 font-medium text-muted-foreground">
                      Capability
                    </th>
                    {roleNames.map((name) => (
                      <th
                        key={name}
                        className="text-center py-2 px-2 font-medium text-muted-foreground whitespace-nowrap"
                      >
                        {getRoleDisplayName(name)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedCategories.map((category) => (
                    <Fragment key={`cat-group-${category}`}>
                      {/* Category header row */}
                      <tr key={`cat-${category}`}>
                        <td
                          colSpan={roleNames.length + 1}
                          className="text-sm font-semibold text-muted-foreground bg-muted/50 py-2 px-3"
                        >
                          {category}
                        </td>
                      </tr>
                      {/* Capability rows */}
                      {(categories[category] ?? []).map((cap) => (
                        <tr key={cap.name} className="border-b border-border/50 hover:bg-muted/30">
                          <td className="py-2 px-3 text-sm text-foreground">
                            <span title={cap.name}>
                              {getCapabilityLabel(cap.name)}
                            </span>
                          </td>
                          {roleNames.map((role) => (
                            <td key={role} className="text-center py-2 px-2">
                              {cap.roles.includes(role) ? (
                                <Check className="inline-block h-4 w-4 text-green-600" />
                              ) : null}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-xs text-muted-foreground pt-2 border-t">
              Roles are system-defined and cannot be created or modified.
            </p>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
