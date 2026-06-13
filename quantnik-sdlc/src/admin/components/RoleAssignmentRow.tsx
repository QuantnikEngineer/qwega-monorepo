/**
 * @deprecated Phase 5: replaced by inline single-role Select in CreateEditUserPanel.
 * Kept for backward compatibility during rolling deploy.
 *
 * RoleAssignmentRow
 *
 * Repeatable card for assigning a role + scope + project to a user.
 * Hides scope radio for superadmin/orgadmin (always org-scoped).
 * Shows project dropdown only when scope_type = "project".
 */

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { RadioGroup, RadioGroupItem } from '../../components/ui/radio-group';
import { Label } from '../../components/ui/label';
import { Button } from '../../components/ui/button';
import { Trash2 } from 'lucide-react';
import type { RoleInfo, ProjectInfo } from '../api/adminApi';

interface RoleAssignmentValue {
  role_name: string;
  scope_type: string;
  scope_id?: string;
}

interface RoleAssignmentRowProps {
  index: number;
  value: RoleAssignmentValue;
  roles: RoleInfo[];
  projects: ProjectInfo[];
  onChange: (value: RoleAssignmentValue) => void;
  onRemove: () => void;
  canRemove: boolean;
}

/** Roles that are always organization-scoped (no project scope option) */
const ORG_ONLY_ROLES = ['superadmin', 'orgadmin'];

export function RoleAssignmentRow({
  index,
  value,
  roles,
  projects,
  onChange,
  onRemove,
  canRemove,
}: RoleAssignmentRowProps) {
  const isOrgOnly = ORG_ONLY_ROLES.includes(value.role_name);
  const showProjectSelect = value.scope_type === 'project' && !isOrgOnly;

  const handleRoleChange = (roleName: string) => {
    const nextIsOrgOnly = ORG_ONLY_ROLES.includes(roleName);
    onChange({
      role_name: roleName,
      scope_type: nextIsOrgOnly ? 'org' : value.scope_type,
      scope_id: nextIsOrgOnly ? undefined : value.scope_id,
    });
  };

  const handleScopeChange = (scopeType: string) => {
    onChange({
      ...value,
      scope_type: scopeType,
      scope_id: scopeType === 'org' ? undefined : value.scope_id,
    });
  };

  const handleProjectChange = (projectId: string) => {
    onChange({ ...value, scope_id: projectId });
  };

  return (
    <div className="rounded-lg border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-medium">Role Assignment {index + 1}</Label>
        {canRemove && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-destructive"
            onClick={onRemove}
            aria-label={`Remove role assignment ${index + 1}`}
          >
            <Trash2 className="size-4" />
          </Button>
        )}
      </div>

      {/* Role Select */}
      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">Role</Label>
        <Select value={value.role_name} onValueChange={handleRoleChange}>
          <SelectTrigger>
            <SelectValue placeholder="Select a role" />
          </SelectTrigger>
          <SelectContent>
            {roles.map((r) => (
              <SelectItem key={r.id} value={r.name}>
                {r.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Scope RadioGroup — hidden for org-only roles */}
      {!isOrgOnly && (
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Scope</Label>
          <RadioGroup
            value={value.scope_type}
            onValueChange={handleScopeChange}
            className="flex gap-4"
          >
            <div className="flex items-center gap-2">
              <RadioGroupItem value="org" id={`scope-org-${index}`} />
              <Label htmlFor={`scope-org-${index}`} className="text-sm font-normal">
                Organization-wide
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <RadioGroupItem value="project" id={`scope-project-${index}`} />
              <Label htmlFor={`scope-project-${index}`} className="text-sm font-normal">
                Project-scoped
              </Label>
            </div>
          </RadioGroup>
        </div>
      )}

      {/* Project Select — only when project-scoped */}
      {showProjectSelect && (
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Project</Label>
          <Select value={value.scope_id ?? ''} onValueChange={handleProjectChange}>
            <SelectTrigger>
              <SelectValue placeholder="Select a project" />
            </SelectTrigger>
            <SelectContent>
              {projects.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
    </div>
  );
}
