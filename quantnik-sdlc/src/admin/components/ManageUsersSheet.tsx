/**
 * ManageUsersSheet
 *
 * Full-viewport data table of users with search, status filter, role filter,
 * sortable columns, deactivation confirmation, and row-level action menus.
 * Integrates CreateEditUserPanel for create/edit workflows.
 */

import { useState, useMemo, useCallback } from 'react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from '../../components/ui/sheet';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../../components/ui/alert-dialog';
import { ScrollArea } from '../../components/ui/scroll-area';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { UserPlus, Search, ArrowUpDown, Users } from 'lucide-react';
import { toast } from 'sonner';

import { useUsers, useDeactivateUser, useDeleteUser, useReactivateUser, useResetPassword, useResendActivation } from '../hooks/useUsers';
import { useRoles } from '../hooks/useRoles';
import { UserStatusBadge } from './UserStatusBadge';
import { UserActionsMenu } from './UserActionsMenu';
import { CreateEditUserPanel } from './CreateEditUserPanel';
import type { AdminUser } from '../api/adminApi';
import { getRoleDisplayName } from '../../constants/roleLabels';

interface ManageUsersSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentUserId: string;
  mode?: 'admin' | 'team';  // 'admin' = SA: all users, 'team' = PM: my users only
}

type SortColumn = 'displayName' | 'email' | 'status' | 'createdAt';
type SortDirection = 'asc' | 'desc';

export function ManageUsersSheet({ open, onOpenChange, currentUserId, mode = 'admin' }: ManageUsersSheetProps) {
  // Data hooks
  const { data, isLoading } = useUsers();
  const { data: rolesData } = useRoles();
  const deactivateMutation = useDeactivateUser();
  const deleteMutation = useDeleteUser();
  const reactivateMutation = useReactivateUser();
  const resetPasswordMutation = useResetPassword();
  const resendActivationMutation = useResendActivation();

  // Filter & sort state
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [roleFilter, setRoleFilter] = useState('all');
  const [sortColumn, setSortColumn] = useState<SortColumn>('displayName');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Panel state
  const [showCreatePanel, setShowCreatePanel] = useState(false);
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [createPanelKey, setCreatePanelKey] = useState(0);

  // Deactivation dialog state
  const [deactivateTarget, setDeactivateTarget] = useState<AdminUser | null>(null);
  // Delete dialog state
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);

  const users = data?.users ?? [];
  const roles = rolesData?.roles ?? [];

  // Filter logic (client-side per D-37)
  const filteredUsers = useMemo(() => {
    // In team mode, show only project-tier users (exclude superadmin + pm + self)
    let result = mode === 'team'
      ? users.filter(u =>
          u.id !== currentUserId &&
          !u.roles.some(r => r.roleName === 'superadmin' || r.roleName === 'pm')
        )
      : [...users];

    // Search filter
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (u) =>
          u.displayName.toLowerCase().includes(q) ||
          u.email.toLowerCase().includes(q),
      );
    }

    // Status filter
    if (statusFilter !== 'all') {
      result = result.filter((u) => u.status === statusFilter);
    }

    // Role filter
    if (roleFilter !== 'all') {
      result = result.filter((u) =>
        u.roles.some((r) => r.roleName === roleFilter),
      );
    }

    // Sort
    result.sort((a, b) => {
      const aVal = a[sortColumn] ?? '';
      const bVal = b[sortColumn] ?? '';
      const cmp = String(aVal).localeCompare(String(bVal));
      return sortDirection === 'asc' ? cmp : -cmp;
    });

    return result;
  }, [users, searchQuery, statusFilter, roleFilter, sortColumn, sortDirection]);

  const toggleSort = useCallback(
    (column: SortColumn) => {
      if (sortColumn === column) {
        setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortColumn(column);
        setSortDirection('asc');
      }
    },
    [sortColumn],
  );

  // Deactivation handler
  const handleConfirmDeactivate = useCallback(() => {
    if (!deactivateTarget) return;
    deactivateMutation.mutate(deactivateTarget.id, {
      onSuccess: () => {
        toast.success('User deactivated');
        setDeactivateTarget(null);
      },
      onError: (error) => {
        toast.error(error.message);
        setDeactivateTarget(null);
      },
    });
  }, [deactivateTarget, deactivateMutation]);

  // Permanent delete handler
  const handleConfirmDelete = useCallback(() => {
    if (!deleteTarget) return;
    deleteMutation.mutate(deleteTarget.id, {
      onSuccess: () => {
        toast.success('User account purged');
        setDeleteTarget(null);
      },
      onError: (error) => {
        toast.error(error.message);
        setDeleteTarget(null);
      },
    });
  }, [deleteTarget, deleteMutation]);

  // Reactivation handler
  const handleReactivate = useCallback(
    (user: AdminUser) => {
      reactivateMutation.mutate(user.id, {
        onSuccess: () => toast.success(`${user.displayName} reactivated`),
        onError: (error) => toast.error(error.message),
      });
    },
    [reactivateMutation],
  );

  // Reset password handler
  const handleResetPassword = useCallback(
    (user: AdminUser) => {
      resetPasswordMutation.mutate(user.id, {
        onSuccess: (result) => {
          navigator.clipboard.writeText(result.activation_url).then(() => {
            toast.success(`Password reset link copied to clipboard for ${user.displayName}`);
          });
        },
        onError: (error) => toast.error(error.message),
      });
    },
    [resetPasswordMutation],
  );

  // Copy activation link handler
  const handleCopyActivationLink = useCallback(
    (user: AdminUser) => {
      resendActivationMutation.mutate(user.id, {
        onSuccess: (result) => {
          navigator.clipboard.writeText(result.activation_url).then(() => {
            toast.success('Activation link copied to clipboard');
          });
        },
        onError: (error) => toast.error(error.message),
      });
    },
    [resendActivationMutation],
  );

  const isFiltered = searchQuery || statusFilter !== 'all' || roleFilter !== 'all';

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="w-full sm:max-w-5xl flex flex-col">
          <SheetHeader className="flex flex-row items-center justify-between space-y-0 pb-4 pr-16 border-b border-[#3498B3]/20">
            <div className="space-y-1">
              <SheetTitle>{mode === 'team' ? 'Manage My Team' : 'Manage Users'}</SheetTitle>
              <SheetDescription>
                {mode === 'team'
                  ? 'Manage team members in the organization (non-admin users).'
                  : 'Manage all users in the organization.'}
              </SheetDescription>
            </div>
            <Button onClick={() => { setEditingUserId(null); setCreatePanelKey((k) => k + 1); setShowCreatePanel(true); }} className="bg-[#3498B3] hover:bg-[#3498B3]/90 text-white">
              <UserPlus className="size-4" />
              {mode === 'team' ? 'Add Team Member' : 'Add User'}
            </Button>
          </SheetHeader>

          {/* Filter row */}
          <div className="flex flex-wrap items-center gap-3 px-4 pb-4 flex-shrink-0">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="suspended">Suspended</SelectItem>
                <SelectItem value="deactivated">Deactivated</SelectItem>
              </SelectContent>
            </Select>

            <Select value={roleFilter} onValueChange={setRoleFilter}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="All Roles" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Roles</SelectItem>
                {roles.map((r) => (
                  <SelectItem key={r.id} value={r.name}>
                    {getRoleDisplayName(r.name)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
              <Input
                placeholder="Search by name or email…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          {/* Table */}
          <ScrollArea className="flex-1 min-h-0 px-4">
            {isLoading ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Role(s)</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="w-[50px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-36" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-8" /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : filteredUsers.length === 0 && !isFiltered ? (
              mode === 'team' ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Users className="w-10 h-10 mb-3" />
                  <p className="text-sm font-semibold">No team members yet</p>
                  <p className="text-xs mt-1">Add your first team member to get started. They'll receive an activation link to set up their account.</p>
                </div>
              ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Users className="size-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold">No users yet</h3>
                <p className="text-muted-foreground mt-1 mb-4">
                  Create a user to get started with role-based access control.
                </p>
                <Button onClick={() => { setEditingUserId(null); setCreatePanelKey((k) => k + 1); setShowCreatePanel(true); }}>
                  <UserPlus className="size-4" />
                  Create User
                </Button>
              </div>
              )
            ) : (
              <div className="overflow-x-auto">
              <Table className="min-w-[600px]">
                <TableHeader className="border-b border-[#3498B3]/20">
                  <TableRow>
                    <TableHead>
                      <Button variant="ghost" size="sm" className="-ml-3 h-8" onClick={() => toggleSort('displayName')}>
                        Name <ArrowUpDown className="ml-1 size-3" />
                      </Button>
                    </TableHead>
                    <TableHead>
                      <Button variant="ghost" size="sm" className="-ml-3 h-8" onClick={() => toggleSort('email')}>
                        Email <ArrowUpDown className="ml-1 size-3" />
                      </Button>
                    </TableHead>
                    <TableHead>Role(s)</TableHead>
                    <TableHead className="hidden lg:table-cell">Project(s)</TableHead>
                    <TableHead>
                      <Button variant="ghost" size="sm" className="-ml-3 h-8" onClick={() => toggleSort('status')}>
                        Status <ArrowUpDown className="ml-1 size-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="hidden md:table-cell">
                      <Button variant="ghost" size="sm" className="-ml-3 h-8" onClick={() => toggleSort('createdAt')}>
                        Created <ArrowUpDown className="ml-1 size-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[50px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell className="font-medium">{user.displayName}</TableCell>
                      <TableCell className="truncate max-w-[200px]">{user.email}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {user.roles.map((r, idx) => (
                            <Badge key={idx} variant="secondary" className="bg-[#3498B3]/10 text-[#3498B3] border-[#3498B3]/20">
                              {getRoleDisplayName(r.roleName)}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        <div className="flex flex-wrap gap-1">
                          {(user.projects ?? []).length > 0 ? (
                            user.projects!.map((p) => (
                              <Badge key={p.id} variant="outline" className="text-xs">
                                {p.name}
                              </Badge>
                            ))
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <UserStatusBadge status={user.status} />
                      </TableCell>
                      <TableCell className="text-muted-foreground hidden md:table-cell">
                        {new Date(user.createdAt).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <UserActionsMenu
                          user={user}
                          currentUserId={currentUserId}
                          onEdit={() => setEditingUserId(user.id)}
                          onResetPassword={() => handleResetPassword(user)}
                          onCopyActivationLink={() => handleCopyActivationLink(user)}
                          onDeactivate={() => setDeactivateTarget(user)}
                          onReactivate={() => handleReactivate(user)}
                          onDelete={() => setDeleteTarget(user)}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              </div>
            )}
          </ScrollArea>

          {/* Footer */}
          {!isLoading && (
            <SheetFooter className="border-t pt-3">
              <p className="text-sm text-muted-foreground">
                {isFiltered
                  ? `Showing ${filteredUsers.length} of ${users.length} user${users.length !== 1 ? 's' : ''}`
                  : `Showing ${users.length} user${users.length !== 1 ? 's' : ''}`}
              </p>
            </SheetFooter>
          )}
        </SheetContent>
      </Sheet>

      {/* Deactivation confirmation dialog */}
      <AlertDialog
        open={!!deactivateTarget}
        onOpenChange={(o) => !o && setDeactivateTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Deactivate {deactivateTarget?.displayName}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will immediately revoke all active sessions. The user will not
              be able to sign in until reactivated.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={handleConfirmDeactivate}
              disabled={deactivateMutation.isPending}
            >
              {deactivateMutation.isPending ? 'Deactivating…' : 'Deactivate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Purge account confirmation dialog (only for deactivated users) */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Purge account for {deleteTarget?.displayName}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove the user account, credentials,
              and sessions. This action cannot be undone. If the user has
              created projects or configured settings, purge will be blocked
              — use deactivation instead.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={handleConfirmDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Purging…' : 'Purge Account'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Create/Edit user panel (nested sheet) */}
      <CreateEditUserPanel
        key={editingUserId ?? `create-${createPanelKey}`}
        open={showCreatePanel || !!editingUserId}
        onOpenChange={(o) => {
          if (!o) {
            setShowCreatePanel(false);
            setEditingUserId(null);
          }
        }}
        userId={editingUserId ?? undefined}
        mode={mode}
        onSuccess={() => {
          setShowCreatePanel(false);
          setEditingUserId(null);
        }}
      />
    </>
  );
}
