/**
 * CreateEditUserPanel
 *
 * Side panel form for creating/editing users with multi-role assignment.
 * Uses react-hook-form with zodResolver for @wipro.com domain validation.
 * Transitions to ActivationLinkCopy view after successful user creation.
 *
 * Phase 2 Wave 2: Multi-role checkbox selection — users can hold one or more roles.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { toast } from 'sonner';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from '../../components/ui/sheet';
import { ScrollArea } from '../../components/ui/scroll-area';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Separator } from '../../components/ui/separator';
import { Checkbox } from '../../components/ui/checkbox';

import { createUserSchema, editUserSchema } from '../schemas/userFormSchema';
import type { CreateUserFormValues, EditUserFormValues } from '../schemas/userFormSchema';
import { useCreateUser, useUpdateUser, useUsers } from '../hooks/useUsers';
import { useRoles } from '../hooks/useRoles';
import { useProjects } from '../hooks/useProjects';
import { getRoleDisplayName } from '../../constants/roleLabels';
import { ActivationLinkCopy } from './ActivationLinkCopy';
import { useAuth } from '../../auth/AuthContext';

/** Roles that only SuperAdmin can assign (org-scoped, above project tier) */
const ORG_TIER_ROLES = ['superadmin', 'pm'];

/** Roles scoped to a project (below PM tier) */
const PROJECT_TIER_ROLES = ['po_sm_ba', 'developer', 'tester', 'mlops'];

interface CreateEditUserPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userId?: string;
  mode?: 'admin' | 'team';
  onSuccess?: () => void;
}

type FormValues = CreateUserFormValues | EditUserFormValues;

export function CreateEditUserPanel({
  open,
  onOpenChange,
  userId,
  mode = 'admin',
  onSuccess,
}: CreateEditUserPanelProps) {
  const isEditMode = !!userId;

  // Data hooks
  const { user: currentUser } = useAuth();
  const { data: usersData } = useUsers();
  const { data: rolesData } = useRoles();
  const { data: projectsData } = useProjects();
  const createMutation = useCreateUser();
  const updateMutation = useUpdateUser();

  // Projects available in the org (for admin mode project-tier role assignment)
  const orgProjects = useMemo(() => projectsData?.projects ?? [], [projectsData]);
  const hasProjects = orgProjects.length > 0;

  // Available roles: admin sees all, team mode (PM) sees only project-tier roles
  // In admin mode, project-tier roles are disabled when no project exists
  const availableRoles = mode === 'admin'
    ? (rolesData?.roles ?? []).map((r: any) => ({ name: r.name }))
    : (rolesData?.roles ?? [])
        .filter((r: any) => PROJECT_TIER_ROLES.includes(r.name))
        .map((r: any) => ({ name: r.name }));

  // Activation link state (shown after successful creation)
  const [activationUrl, setActivationUrl] = useState<string | null>(null);

  // Selected project for project-tier roles (admin mode only — PM uses currentUser.projectId)
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');

  // Auto-select the only project when there's exactly one
  useEffect(() => {
    if (mode === 'admin' && orgProjects.length === 1 && !selectedProjectId) {
      setSelectedProjectId(orgProjects[0].id);
    }
  }, [mode, orgProjects, selectedProjectId]);

  // Form setup
  const form = useForm<FormValues>({
    resolver: zodResolver(isEditMode ? editUserSchema : createUserSchema),
    defaultValues: {
      ...(isEditMode ? {} : { email: '' }),
      display_name: '',
      role_names: [],
    },
  });

  const selectedRoles: string[] = form.watch('role_names') ?? [];

  // Whether any project-tier role is selected
  const hasProjectTierSelection = selectedRoles.some((r) => PROJECT_TIER_ROLES.includes(r));

  // Show project selector in admin mode when project-tier roles are selected
  const showProjectSelector = mode === 'admin' && hasProjectTierSelection && hasProjects;

  const toggleRole = useCallback(
    (roleName: string) => {
      const current: string[] = form.getValues('role_names') ?? [];
      const next = current.includes(roleName)
        ? current.filter((r) => r !== roleName)
        : [...current, roleName];
      form.setValue('role_names', next, { shouldValidate: true });
    },
    [form],
  );

  // Pre-populate form for edit mode
  useEffect(() => {
    if (isEditMode && userId && usersData?.users) {
      const user = usersData.users.find((u) => u.id === userId);
      if (user) {
        const currentRoles = (user.roles ?? []).map((r) => r.roleName);
        form.reset({
          display_name: user.displayName,
          role_names: currentRoles,
        });
      }
    }
  }, [isEditMode, userId, usersData, form]);

  // Reset form and activation URL when panel opens/closes
  useEffect(() => {
    if (!open) {
      setActivationUrl(null);
      setSelectedProjectId('');
      form.reset();
    }
  }, [open, form]);

  // Belt-and-suspenders: reset form when opening in create mode
  useEffect(() => {
    if (open && !isEditMode) {
      form.reset({ display_name: '', email: '', role_names: [] } as FormValues);
    }
  }, [open, isEditMode, form]);

  const handleSubmit = useCallback(
    async (values: FormValues) => {
      const roleAssignments = (values.role_names ?? []).map((name) => {
        const isProjectRole = PROJECT_TIER_ROLES.includes(name);
        if (isProjectRole) {
          // In team mode, use PM's own project; fall back to first org project
          // (handles case where project was just created but JWT hasn't refreshed yet)
          const projectId = mode === 'team'
            ? (currentUser?.projectId ?? orgProjects[0]?.id ?? null)
            : selectedProjectId;
          return {
            role_name: name,
            scope_type: 'project',
            scope_id: projectId || null,
          };
        }
        return {
          role_name: name,
          scope_type: 'org',
          scope_id: null as string | null,
        };
      });

      if (isEditMode && userId) {
        updateMutation.mutate(
          { userId, data: { display_name: values.display_name, role_assignments: roleAssignments } },
          {
            onSuccess: () => {
              toast.success('User updated successfully');
              onOpenChange(false);
              onSuccess?.();
            },
            onError: (error) => toast.error(error.message),
          },
        );
      } else {
        const payload = {
          email: (values as CreateUserFormValues).email ?? '',
          display_name: values.display_name ?? '',
          role_assignments: roleAssignments,
        };
        createMutation.mutate(payload, {
          onSuccess: (result) => {
            setActivationUrl(result.activation_url);
          },
          onError: (error) => toast.error(error.message),
        });
      }
    },
    [isEditMode, userId, mode, currentUser, createMutation, updateMutation, onOpenChange, onSuccess],
  );

  const handleDone = useCallback(() => {
    setActivationUrl(null);
    onOpenChange(false);
    onSuccess?.();
  }, [onOpenChange, onSuccess]);

  const isPending = createMutation.isPending || updateMutation.isPending;

  // Get the editing user for display
  const editingUser = isEditMode && userId
    ? usersData?.users?.find((u) => u.id === userId)
    : null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="sm:max-w-lg flex flex-col">
        <SheetHeader className="border-b border-[#3498B3]/20 pb-4">
          <SheetTitle>
            {isEditMode ? `Edit User: ${editingUser?.displayName ?? ''}` : 'Create User'}
          </SheetTitle>
          <SheetDescription>
            {isEditMode
              ? 'Update user details and role assignments'
              : 'Add a new user to the organization'}
          </SheetDescription>
        </SheetHeader>

        {activationUrl ? (
          <ActivationLinkCopy activationUrl={activationUrl} onDone={handleDone} />
        ) : (
          <>
            <ScrollArea className="flex-1 px-4" style={{ minHeight: 0 }}>
              <form
                id="user-form"
                onSubmit={form.handleSubmit(handleSubmit)}
                className="space-y-6 pb-4"
                noValidate
              >
                {/* Section: User Details */}
                <div className="space-y-4">
                  <h4 className="text-sm font-semibold text-[#3498B3]">User Details</h4>

                  {/* Full Name */}
                  <div className="space-y-1.5">
                    <Label htmlFor="display_name">Full Name</Label>
                    <Input
                      id="display_name"
                      placeholder="Jane Doe"
                      {...form.register('display_name')}
                    />
                    {form.formState.errors.display_name && (
                      <p className="text-sm text-destructive">
                        {form.formState.errors.display_name.message}
                      </p>
                    )}
                  </div>

                  {/* Email — only in create mode */}
                  {!isEditMode && (
                    <div className="space-y-1.5">
                      <Label htmlFor="email">Email</Label>
                      <Input
                        id="email"
                        type="email"
                        placeholder="jane@wipro.com"
                        disabled={isEditMode}
                        {...form.register('email' as never)}
                      />
                      {(form.formState.errors as Record<string, { message?: string }>).email && (
                        <p className="text-sm text-destructive">
                          {(form.formState.errors as Record<string, { message?: string }>).email?.message}
                        </p>
                      )}
                    </div>
                  )}
                </div>

                <Separator />

                {/* Section: Role Assignment — multi-role checkboxes */}
                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-semibold text-[#3498B3]">Assign Roles</h4>
                    <p className="text-xs text-muted-foreground mt-1">
                      Select one or more roles. The user inherits capabilities and agent access from all assigned roles.
                    </p>
                  </div>

                  {/* Org-tier roles (no project needed) */}
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Organization Roles</p>
                    {availableRoles.filter((r) => ORG_TIER_ROLES.includes(r.name)).map((r) => (
                      <label
                        key={r.name}
                        className={`flex items-center gap-3 rounded-lg border px-4 py-3 transition-colors has-[[data-state=checked]]:border-[#3498B3] has-[[data-state=checked]]:bg-[#3498B3]/5 cursor-pointer hover:bg-accent/50`}
                      >
                        <Checkbox
                          checked={selectedRoles.includes(r.name)}
                          onCheckedChange={() => toggleRole(r.name)}
                        />
                        <div className="flex flex-col">
                          <span className="text-sm font-medium">{getRoleDisplayName(r.name)}</span>
                          <span className="text-xs text-muted-foreground">No project assignment needed</span>
                        </div>
                      </label>
                    ))}
                  </div>

                  {/* Project-tier roles (need project) */}
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Project Roles</p>
                    {availableRoles.filter((r) => PROJECT_TIER_ROLES.includes(r.name)).map((r) => {
                      const isDisabled = mode === 'admin' && !hasProjects;
                      return (
                        <label
                          key={r.name}
                          className={`flex items-center gap-3 rounded-lg border px-4 py-3 transition-colors has-[[data-state=checked]]:border-[#3498B3] has-[[data-state=checked]]:bg-[#3498B3]/5 ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-accent/50'}`}
                        >
                          <Checkbox
                            checked={selectedRoles.includes(r.name)}
                            onCheckedChange={() => toggleRole(r.name)}
                            disabled={isDisabled}
                          />
                          <div className="flex flex-col">
                            <span className="text-sm font-medium">{getRoleDisplayName(r.name)}</span>
                            {isDisabled && (
                              <span className="text-xs text-muted-foreground">Requires an active project</span>
                            )}
                          </div>
                        </label>
                      );
                    })}
                  </div>
                  {form.formState.errors.role_names && (
                    <p className="text-xs text-destructive">
                      {(form.formState.errors.role_names as { message?: string })?.message}
                    </p>
                  )}

                  {/* Project selector — shown in admin mode when project-tier roles are selected */}
                  {showProjectSelector && (
                    <div className="space-y-1.5 mt-4">
                      <Separator />
                      <h4 className="text-sm font-semibold text-[#3498B3] pt-2">Project Assignment</h4>
                      <p className="text-xs text-muted-foreground">
                        Project-tier roles are scoped to a project. Select the target project.
                      </p>
                      <select
                        value={selectedProjectId}
                        onChange={(e) => setSelectedProjectId(e.target.value)}
                        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        {orgProjects.length > 1 && <option value="">Select a project…</option>}
                        {orgProjects.map((p: any) => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              </form>
            </ScrollArea>

            <SheetFooter className="shrink-0 border-t border-[#3498B3]/20 pt-4 flex-row gap-2">
              <Button variant="outline" type="button" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" form="user-form" disabled={isPending} className="bg-[#3498B3] hover:bg-[#3498B3]/90 text-white">
                {isPending
                  ? isEditMode
                    ? 'Saving…'
                    : 'Creating…'
                  : isEditMode
                    ? 'Save Changes'
                    : 'Create User'}
              </Button>
            </SheetFooter>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
