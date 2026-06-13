/**
 * ManageProjectsSheet
 *
 * Compact modal dialog for project CRUD management.
 * SuperAdmin sees all projects, PM sees own projects.
 * Includes project member management and tool settings sub-panels.
 */

import { useState, useMemo, useCallback } from 'react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../../components/ui/sheet';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
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
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { Textarea } from '../../components/ui/textarea';
import {
  FolderPlus,
  Search,
  ArrowUpDown,
  FolderOpen,
  Users,
  Wrench,
  Trash2,
  Pencil,
  AlertTriangle,
  Copy,
  Link,
} from 'lucide-react';
import { toast } from 'sonner';

import { useProjects, useCreateProject, useUpdateProject, useDeleteProject } from '../hooks/useProjects';
import type { ProjectInfo } from '../api/adminApi';
import { ProjectMembersPanel } from './ProjectMembersPanel';
import { ProjectToolSettingsPanel } from './ProjectToolSettingsPanel';

interface ManageProjectsSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentUserId: string;
  /** 'admin' = SuperAdmin full CRUD; 'pm' = PM sees own project only */
  mode?: 'admin' | 'pm';
}

type SortColumn = 'name' | 'slug' | 'createdAt';
type SortDirection = 'asc' | 'desc';

export function ManageProjectsSheet({ open, onOpenChange, currentUserId, mode = 'admin' }: ManageProjectsSheetProps) {
  const isPM = mode === 'pm';
  const { data, isLoading, isError } = useProjects();
  const createMutation = useCreateProject();
  const updateMutation = useUpdateProject();
  const deleteMutation = useDeleteProject();

  const [searchQuery, setSearchQuery] = useState('');
  const [sortColumn, setSortColumn] = useState<SortColumn>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Create / Edit dialog
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [editingProject, setEditingProject] = useState<ProjectInfo | null>(null);
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formOpenForRegistration, setFormOpenForRegistration] = useState(false);

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<ProjectInfo | null>(null);

  // Sub-panels
  const [membersProject, setMembersProject] = useState<ProjectInfo | null>(null);
  const [settingsProject, setSettingsProject] = useState<ProjectInfo | null>(null);

  const projects = data?.projects ?? [];
  const hasActiveProject = projects.some((p) => p.isActive);

  const filteredProjects = useMemo(() => {
    let result = [...projects];

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.slug.toLowerCase().includes(q) ||
          (p.description ?? '').toLowerCase().includes(q),
      );
    }

    result.sort((a, b) => {
      let cmp = 0;
      if (sortColumn === 'name') cmp = a.name.localeCompare(b.name);
      else if (sortColumn === 'slug') cmp = a.slug.localeCompare(b.slug);
      else if (sortColumn === 'createdAt') cmp = (a.createdAt ?? '').localeCompare(b.createdAt ?? '');
      return sortDirection === 'asc' ? cmp : -cmp;
    });

    return result;
  }, [projects, searchQuery, sortColumn, sortDirection]);

  const toggleSort = useCallback((col: SortColumn) => {
    if (sortColumn === col) {
      setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortColumn(col);
      setSortDirection('asc');
    }
  }, [sortColumn]);

  const openCreate = () => {
    setEditingProject(null);
    setFormName('');
    setFormDescription('');
    setFormOpenForRegistration(false);
    setShowCreateDialog(true);
  };

  const openEdit = (project: ProjectInfo) => {
    setEditingProject(project);
    setFormName(project.name);
    setFormDescription(project.description ?? '');
    setFormOpenForRegistration(project.openForRegistration ?? false);
    setShowCreateDialog(true);
  };

  const handleSave = async () => {
    if (!formName.trim()) {
      toast.error('Project name is required');
      return;
    }
    try {
      if (editingProject) {
        await updateMutation.mutateAsync({
          projectId: editingProject.id,
          data: {
            name: formName.trim(),
            description: formDescription.trim() || undefined,
            open_for_registration: formOpenForRegistration,
          },
        });
        toast.success('Project updated');
      } else {
        await createMutation.mutateAsync({
          name: formName.trim(),
          description: formDescription.trim() || undefined,
          open_for_registration: formOpenForRegistration,
        });
        toast.success('Project created');
      }
      setShowCreateDialog(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Operation failed');
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget.id);
      toast.success(`"${deleteTarget.name}" deactivated`);
      setDeleteTarget(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to deactivate');
    }
  };

  const SortableHeader = ({ column, children }: { column: SortColumn; children: React.ReactNode }) => (
    <button
      className="flex items-center gap-1 hover:text-foreground transition-colors"
      onClick={() => toggleSort(column)}
    >
      {children}
      <ArrowUpDown className="w-3 h-3" />
    </button>
  );

  // Sub-panels render as separate Sheets
  if (membersProject) {
    return (
      <ProjectMembersPanel
        open
        onOpenChange={() => setMembersProject(null)}
        project={membersProject}
      />
    );
  }

  if (settingsProject) {
    return (
      <ProjectToolSettingsPanel
        open
        onOpenChange={() => setSettingsProject(null)}
        project={settingsProject}
      />
    );
  }

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="sm:max-w-5xl p-0 flex flex-col">
          <SheetHeader className="px-6 pt-6 pb-4 border-b border-border flex-shrink-0">
            <div className="flex items-center justify-between pr-12">
              <div>
                <SheetTitle className="flex items-center gap-2">
                  <FolderOpen className="w-5 h-5" />
                  {isPM ? 'My Project' : 'Manage Projects'}
                </SheetTitle>
                <SheetDescription>
                  {isPM
                    ? 'View and manage your project details'
                    : 'Create, edit, and manage organization projects'}
                </SheetDescription>
              </div>
              {(!isPM || !hasActiveProject) && (
                <Button size="sm" onClick={openCreate}>
                  <FolderPlus className="w-4 h-4 mr-2" />
                  New Project
                </Button>
              )}
            </div>

            {/* Search — admin mode only */}
            {!isPM && (
              <div className="mt-4 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Search projects…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
            )}
          </SheetHeader>

          <ScrollArea className="flex-1 min-h-0 px-6">
            {isLoading ? (
              <div className="p-6 space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full rounded-md" />
                ))}
              </div>
            ) : isError ? (
              <div className="p-12 text-center text-muted-foreground">
                <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-destructive opacity-70" />
                <p className="text-sm font-medium text-destructive">Failed to load projects</p>
                <p className="text-xs mt-1">There was a server error. Try restarting the auth service and refreshing.</p>
              </div>
            ) : filteredProjects.length === 0 ? (
              <div className="p-12 text-center text-muted-foreground">
                <FolderOpen className="w-12 h-12 mx-auto mb-3 opacity-40" />
                <p className="text-sm font-medium">No projects found</p>
                <p className="text-xs mt-1">Create your first project to get started.</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead><SortableHeader column="name">Name</SortableHeader></TableHead>
                    <TableHead><SortableHeader column="slug">Slug</SortableHeader></TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead><SortableHeader column="createdAt">Created</SortableHeader></TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredProjects.map((project) => (
                    <TableRow key={project.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium text-sm">{project.name}</p>
                          {project.description && (
                            <p className="text-xs text-muted-foreground truncate max-w-[200px]">
                              {project.description}
                            </p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{project.slug}</code>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <Badge variant={project.isActive ? 'default' : 'secondary'}>
                            {project.isActive ? 'Active' : 'Inactive'}
                          </Badge>
                          {project.openForRegistration && (
                            <Badge variant="outline" className="text-xs border-emerald-500/40 text-emerald-600 dark:text-emerald-400">
                              Open
                            </Badge>
                          )}
                          {project.openForRegistration && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 w-6 p-0"
                              onClick={(e) => {
                                e.stopPropagation();
                                const url = `${window.location.origin}/register?project=${project.slug}`;
                                navigator.clipboard.writeText(url);
                                toast.success('Registration link copied');
                              }}
                              title={`${window.location.origin}/register?project=${project.slug}`}
                            >
                              <Copy className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {project.createdAt
                          ? new Date(project.createdAt).toLocaleDateString()
                          : '—'}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setMembersProject(project)}
                            title="Members"
                          >
                            <Users className="w-4 h-4" />
                          </Button>
                          {!isPM && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setSettingsProject(project)}
                              title="Tool Settings"
                            >
                              <Wrench className="w-4 h-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEdit(project)}
                            title="Edit"
                          >
                            <Pencil className="w-4 h-4" />
                          </Button>
                          {!isPM && project.isActive && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setDeleteTarget(project)}
                              title="Deactivate"
                              className="text-destructive hover:text-destructive"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </ScrollArea>
        </SheetContent>
      </Sheet>

      {/* Create / Edit Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingProject ? 'Edit Project' : 'Create Project'}</DialogTitle>
            <DialogDescription>
              {editingProject
                ? 'Update the project name and description.'
                : 'A URL slug will be auto-generated from the project name.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="project-name">Name</Label>
              <Input
                id="project-name"
                placeholder="e.g. QUANTNIK AI Platform"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-desc">Description</Label>
              <Textarea
                id="project-desc"
                placeholder="Brief project description…"
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                rows={3}
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border px-4 py-3">
              <div className="space-y-0.5">
                <Label htmlFor="open-registration" className="text-sm font-medium">
                  Open for Registration
                </Label>
                <p className="text-xs text-muted-foreground">
                  Allow users to self-register directly into this project
                </p>
              </div>
              <button
                id="open-registration"
                type="button"
                role="switch"
                aria-checked={formOpenForRegistration}
                onClick={() => setFormOpenForRegistration(!formOpenForRegistration)}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                  formOpenForRegistration ? 'bg-primary' : 'bg-input'
                }`}
              >
                <span
                  className={`pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform ${
                    formOpenForRegistration ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
            {formOpenForRegistration && editingProject?.slug && (
              <div className="mt-2 flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2">
                <Link className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
                <code className="text-xs break-all flex-1">
                  {`${window.location.origin}/register?project=${editingProject.slug}`}
                </code>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 shrink-0"
                  onClick={() => {
                    const url = `${window.location.origin}/register?project=${editingProject.slug}`;
                    navigator.clipboard.writeText(url);
                    toast.success('Registration link copied');
                  }}
                  title="Copy registration link"
                >
                  <Copy className="w-3.5 h-3.5" />
                </Button>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {createMutation.isPending || updateMutation.isPending
                ? 'Saving…'
                : editingProject ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate project?</AlertDialogTitle>
            <AlertDialogDescription>
              This will deactivate <strong>{deleteTarget?.name}</strong>. The project data is
              preserved but it will no longer appear in active project lists.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Deactivating…' : 'Deactivate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
