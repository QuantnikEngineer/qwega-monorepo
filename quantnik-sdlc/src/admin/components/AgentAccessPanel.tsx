/**
 * AgentAccessPanel
 *
 * Admin panel for managing which agents each role can access.
 * SuperAdmin only (admin:manage_agents capability).
 */

import { useState, useMemo, useCallback, useEffect } from 'react';
import { Bot, Save, Loader2, ShieldAlert, Info } from 'lucide-react';
import { toast } from 'sonner';

import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../../components/ui/sheet';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Checkbox } from '../../components/ui/checkbox';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { useRoles } from '../hooks/useRoles';
import { useAgentCatalog, useRoleAgents, useUpdateRoleAgents } from '../hooks/useAgents';
import { getRoleDisplayName } from '../../constants/roleLabels';
import type { AgentCatalogEntry } from '../api/adminApi';

interface AgentAccessPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const CATEGORY_ORDER = ['planning', 'analysis', 'testing', 'build'];
const CATEGORY_LABELS: Record<string, string> = {
  planning: 'Planning',
  analysis: 'Analysis & Design',
  testing: 'Testing',
  build: 'Build',
};

function groupByCategory(agents: AgentCatalogEntry[]) {
  const groups: Record<string, AgentCatalogEntry[]> = {};
  for (const agent of agents) {
    const cat = agent.category || 'other';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(agent);
  }
  return groups;
}

export function AgentAccessPanel({ open, onOpenChange }: AgentAccessPanelProps) {
  const { data: rolesData, isLoading: rolesLoading } = useRoles();
  const { data: catalogData, isLoading: catalogLoading } = useAgentCatalog();
  const updateMutation = useUpdateRoleAgents();

  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [checkedAgents, setCheckedAgents] = useState<Set<string>>(new Set());
  const [isDirty, setIsDirty] = useState(false);

  const { data: roleAgentsData, isLoading: roleAgentsLoading } = useRoleAgents(selectedRoleId);

  // Roles excluding superadmin (immutable)
  const editableRoles = useMemo(
    () => (rolesData?.roles ?? []).filter((r) => r.name !== 'superadmin'),
    [rolesData],
  );

  // When role agents load, sync checkbox state
  useEffect(() => {
    if (roleAgentsData) {
      setCheckedAgents(new Set(roleAgentsData.agent_ids));
      setIsDirty(false);
    }
  }, [roleAgentsData]);

  // Reset when role changes
  useEffect(() => {
    setIsDirty(false);
  }, [selectedRoleId]);

  const selectedRole = useMemo(
    () => (rolesData?.roles ?? []).find((r) => r.id === selectedRoleId),
    [rolesData, selectedRoleId],
  );

  const agentGroups = useMemo(
    () => groupByCategory(catalogData?.agents ?? []),
    [catalogData],
  );

  const handleToggle = useCallback(
    (agentId: string, checked: boolean) => {
      setCheckedAgents((prev) => {
        const next = new Set(prev);
        if (checked) next.add(agentId);
        else next.delete(agentId);
        return next;
      });
      setIsDirty(true);
    },
    [],
  );

  const handleSelectAll = useCallback(() => {
    const allIds = (catalogData?.agents ?? []).filter((a) => a.is_active).map((a) => a.id);
    setCheckedAgents(new Set(allIds));
    setIsDirty(true);
  }, [catalogData]);

  const handleClearAll = useCallback(() => {
    setCheckedAgents(new Set());
    setIsDirty(true);
  }, []);

  const handleSave = useCallback(async () => {
    if (!selectedRoleId) return;
    try {
      await updateMutation.mutateAsync({
        roleId: selectedRoleId,
        agentIds: Array.from(checkedAgents),
      });
      setIsDirty(false);
      toast.success('Agent access updated', {
        description: `${selectedRole?.name ? getRoleDisplayName(selectedRole.name) : 'Role'} agents saved.`,
      });
    } catch (err) {
      toast.error('Failed to update agent access', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  }, [selectedRoleId, checkedAgents, updateMutation, selectedRole]);

  const isLoading = rolesLoading || catalogLoading;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-xl p-0 flex flex-col">
        {/* ── Header ── */}
        <SheetHeader className="px-6 pt-6 pb-4 border-b border-border flex-shrink-0">
          <SheetTitle className="flex items-center gap-2 text-base">
            <Bot className="w-5 h-5 text-[#746FA7]" />
            Agent Access
          </SheetTitle>
          <SheetDescription>
            Configure which SDLC agents each role can access. Changes take effect on next login or token refresh.
          </SheetDescription>
        </SheetHeader>

        {/* ── Scrollable body ── */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="px-6 py-6 space-y-6">
              {/* Role Selector */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Select Role</label>
                <Select
                  value={selectedRoleId ?? ''}
                  onValueChange={(val) => setSelectedRoleId(val || null)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Choose a role to configure..." />
                  </SelectTrigger>
                  <SelectContent>
                    {editableRoles.map((role) => (
                      <SelectItem key={role.id} value={role.id}>
                        {getRoleDisplayName(role.name)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* SuperAdmin info */}
              <div className="flex items-start gap-2.5 rounded-lg border border-border bg-muted/40 px-4 py-3 text-xs text-muted-foreground">
                <ShieldAlert className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>SuperAdmin always has access to all agents and cannot be modified.</span>
              </div>

              {/* Agent Checklist */}
              {selectedRoleId && (
                <>
                  {roleAgentsLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                    </div>
                  ) : (
                    <>
                      {/* Bulk actions */}
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">
                          {checkedAgents.size} of {(catalogData?.agents ?? []).length} agents selected
                        </span>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="sm" className="text-xs h-7 px-2" onClick={handleSelectAll}>
                            Select All
                          </Button>
                          <Button variant="ghost" size="sm" className="text-xs h-7 px-2" onClick={handleClearAll}>
                            Clear
                          </Button>
                        </div>
                      </div>

                      {/* Grouped agents */}
                      {CATEGORY_ORDER.map((cat) => {
                        const agents = agentGroups[cat];
                        if (!agents?.length) return null;
                        return (
                          <div key={cat} className="space-y-2">
                            <div className="flex items-center gap-2">
                              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                {CATEGORY_LABELS[cat] ?? cat}
                              </h4>
                              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                                {agents.filter((a) => checkedAgents.has(a.id)).length}/{agents.length}
                              </Badge>
                            </div>
                            <div className="space-y-1">
                              {agents.map((agent) => (
                                <label
                                  key={agent.id}
                                  className="flex items-start gap-3 cursor-pointer rounded-lg p-2.5 hover:bg-accent/50 transition-colors"
                                >
                                  <Checkbox
                                    checked={checkedAgents.has(agent.id)}
                                    onCheckedChange={(checked) =>
                                      handleToggle(agent.id, checked === true)
                                    }
                                    disabled={!agent.is_active}
                                    className="mt-0.5"
                                  />
                                  <div className="space-y-0.5 min-w-0">
                                    <div className="flex items-center gap-2">
                                      <span className="text-sm font-medium leading-none">{agent.name}</span>
                                      {!agent.is_active && (
                                        <Badge variant="outline" className="text-[10px] text-muted-foreground">
                                          Inactive
                                        </Badge>
                                      )}
                                    </div>
                                    {agent.description && (
                                      <p className="text-xs text-muted-foreground leading-relaxed">
                                        {agent.description}
                                      </p>
                                    )}
                                  </div>
                                </label>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </>
                  )}
                </>
              )}

              {/* No role selected hint */}
              {!selectedRoleId && (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Info className="w-8 h-8 text-muted-foreground/50 mb-3" />
                  <p className="text-sm text-muted-foreground">
                    Select a role above to view and edit its agent access.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Fixed footer ── */}
        {selectedRoleId && !roleAgentsLoading && (
          <div className="px-6 py-4 border-t border-border flex-shrink-0">
            <Button
              onClick={handleSave}
              disabled={!isDirty || updateMutation.isPending}
              className="w-full"
            >
              {updateMutation.isPending ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
