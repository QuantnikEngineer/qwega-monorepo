/**
 * ProjectMembersPanel
 *
 * Sheet for managing members of a specific project.
 * Add org users to the project with a role; remove existing members.
 */

import { useState, useMemo } from 'react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
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
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { UserPlus, ArrowLeft, Users, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import {
  useProjectMembers,
  useAddProjectMember,
  useRemoveProjectMember,
} from '../hooks/useProjects';
import { useUsers } from '../hooks/useUsers';
import { useRoles } from '../hooks/useRoles';
import type { ProjectInfo, ProjectMember } from '../api/adminApi';
import { getRoleDisplayName } from '../../constants/roleLabels';

// Roles that can be assigned at project scope (excludes superadmin — org-only)
const PROJECT_ASSIGNABLE_ROLES = ['pm', 'po_sm_ba', 'developer', 'tester', 'mlops'];

interface ProjectMembersPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  project: ProjectInfo;
}

export function ProjectMembersPanel({ open, onOpenChange, project }: ProjectMembersPanelProps) {
  const { data: membersData, isLoading } = useProjectMembers(project.id);
  const { data: usersData } = useUsers();
  const { data: rolesData } = useRoles();
  const addMutation = useAddProjectMember();
  const removeMutation = useRemoveProjectMember();

  const [showAddDialog, setShowAddDialog] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [selectedRole, setSelectedRole] = useState('');
  const [removeTarget, setRemoveTarget] = useState<ProjectMember | null>(null);

  const members = membersData?.members ?? [];
  const allUsers = usersData?.users ?? [];

  // Users not already in the project (candidates for adding)
  const memberUserIds = useMemo(
    () => new Set(members.map((m) => m.userId)),
    [members],
  );
  const eligibleUsers = useMemo(
    () => allUsers.filter((u) => u.status === 'active' && !memberUserIds.has(u.id)),
    [allUsers, memberUserIds],
  );

  // Filter available roles to project-assignable ones that exist in backend
  const assignableRoles = useMemo(() => {
    const backendRoles = rolesData?.roles ?? [];
    return backendRoles.filter((r) => PROJECT_ASSIGNABLE_ROLES.includes(r.name));
  }, [rolesData]);

  const handleAdd = async () => {
    if (!selectedUserId || !selectedRole) {
      toast.error('Select a user and a role');
      return;
    }
    try {
      await addMutation.mutateAsync({
        projectId: project.id,
        data: { user_id: selectedUserId, role_name: selectedRole },
      });
      toast.success('Member added');
      setShowAddDialog(false);
      setSelectedUserId('');
      setSelectedRole('');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add member');
    }
  };

  const handleRemove = async () => {
    if (!removeTarget) return;
    try {
      await removeMutation.mutateAsync({
        projectId: project.id,
        userId: removeTarget.userId,
      });
      toast.success('Member removed');
      setRemoveTarget(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove member');
    }
  };

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="w-full sm:max-w-2xl p-0 flex flex-col">
          <SheetHeader className="px-6 pt-6 pb-4 border-b border-border flex-shrink-0">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
                <ArrowLeft className="w-4 h-4" />
              </Button>
              <div className="flex-1">
                <SheetTitle className="flex items-center gap-2">
                  <Users className="w-5 h-5" />
                  Members — {project.name}
                </SheetTitle>
                <SheetDescription>
                  {members.length} member{members.length !== 1 ? 's' : ''} in this project
                </SheetDescription>
              </div>
              <Button size="sm" onClick={() => setShowAddDialog(true)}>
                <UserPlus className="w-4 h-4 mr-2" />
                Add Member
              </Button>
            </div>
          </SheetHeader>

          <ScrollArea className="flex-1 min-h-0">
            {isLoading ? (
              <div className="p-6 space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full rounded-md" />
                ))}
              </div>
            ) : members.length === 0 ? (
              <div className="p-12 text-center text-muted-foreground">
                <Users className="w-12 h-12 mx-auto mb-3 opacity-40" />
                <p className="text-sm font-medium">No members yet</p>
                <p className="text-xs mt-1">Add team members to this project.</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {members.map((member) => (
                    <TableRow key={member.userId}>
                      <TableCell>
                        <div>
                          <p className="font-medium text-sm">{member.displayName}</p>
                          <p className="text-xs text-muted-foreground">{member.email}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {member.roles.map((r) => (
                            <Badge key={r.roleName} variant="outline">
                              {getRoleDisplayName(r.roleName)}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => setRemoveTarget(member)}
                          title="Remove from project"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </ScrollArea>
        </SheetContent>
      </Sheet>

      {/* Add Member Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Member</DialogTitle>
            <DialogDescription>
              Select a user and assign a project role.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">User</label>
              <Select value={selectedUserId} onValueChange={setSelectedUserId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a user…" />
                </SelectTrigger>
                <SelectContent>
                  {eligibleUsers.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.displayName} ({u.email})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Role</label>
              <Select value={selectedRole} onValueChange={setSelectedRole}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a role…" />
                </SelectTrigger>
                <SelectContent>
                  {assignableRoles.map((r) => (
                    <SelectItem key={r.name} value={r.name}>
                      {getRoleDisplayName(r.name)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleAdd} disabled={addMutation.isPending}>
              {addMutation.isPending ? 'Adding…' : 'Add Member'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Remove Confirmation */}
      <AlertDialog open={!!removeTarget} onOpenChange={() => setRemoveTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove member?</AlertDialogTitle>
            <AlertDialogDescription>
              Remove <strong>{removeTarget?.displayName}</strong> ({removeTarget?.roles.map(r => getRoleDisplayName(r.roleName)).join(', ') ?? ''})
              from <strong>{project.name}</strong>? They will lose access to this project.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRemove}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {removeMutation.isPending ? 'Removing…' : 'Remove'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
