/**
 * ProjectAgentConfigPanel
 *
 * PM panel for managing which agents each role can access within their project.
 * Operates within the global ceiling set by SuperAdmin.
 * Requires `project:manage_agents` capability.
 */

import { useState, useMemo, useCallback, useEffect } from 'react';
import { Bot, Save, Loader2, RotateCcw, ShieldCheck, Info } from 'lucide-react';
import { toast } from 'sonner';

import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../../components/ui/sheet';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Checkbox } from '../../components/ui/checkbox';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { useProjectAgents, useUpdateProjectRoleAgents, useResetProjectRoleAgents } from '../hooks/useAgents';
import { useAgentCatalog } from '../hooks/useAgents';
import { getRoleDisplayName } from '../../constants/roleLabels';
import type { AgentCatalogEntry, ProjectRoleAgentConfig } from '../api/adminApi';

interface ProjectAgentConfigPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  projectName: string;
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

export function ProjectAgentConfigPanel({ open, onOpenChange, projectId, projectName }: ProjectAgentConfigPanelProps) {
  const { data: projectAgentsData, isLoading: projectAgentsLoading } = useProjectAgents(open ? projectId : null);
  const { data: catalogData, isLoading: catalogLoading } = useAgentCatalog();
  const updateMutation = useUpdateProjectRoleAgents();
  const resetMutation = useResetProjectRoleAgents();

  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [checkedAgents, setCheckedAgents] = useState<Set<string>>(new Set());
  const [isDirty, setIsDirty] = useState(false);

  const roles = useMemo(
    () => (projectAgentsData?.roles ?? []).filter((r) => r.role_name !== 'superadmin'),
    [projectAgentsData],
  );

  const selectedRoleConfig: ProjectRoleAgentConfig | undefined = useMemo(
    () => roles.find((r) => r.role_id === selectedRoleId),
    [roles, selectedRoleId],
  );

  // Sync checkbox state when role data loads or selection changes
  useEffect(() => {
    if (selectedRoleConfig) {
      setCheckedAgents(new Set(selectedRoleConfig.effective_agent_ids));
      setIsDirty(false);
    }
  }, [selectedRoleConfig]);

  const agentGroups = useMemo(
    () => groupByCategory(catalogData?.agents ?? []),
    [catalogData],
  );

  // Global ceiling for the selected role — agents available to toggle
  const globalCeiling = useMemo(
    () => new Set(selectedRoleConfig?.global_agent_ids ?? []),
    [selectedRoleConfig],
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
    setCheckedAgents(new Set(selectedRoleConfig?.global_agent_ids ?? []));
    setIsDirty(true);
  }, [selectedRoleConfig]);

  const handleClearAll = useCallback(() => {
    setCheckedAgents(new Set());
    setIsDirty(true);
  }, []);

  const handleSave = useCallback(async () => {
    if (!selectedRoleId) return;
    try {
      await updateMutation.mutateAsync({
        projectId,
        roleId: selectedRoleId,
        agentIds: Array.from(checkedAgents),
      });
      setIsDirty(false);
      toast.success('Project agent access updated', {
        description: `${selectedRoleConfig?.role_name ? getRoleDisplayName(selectedRoleConfig.role_name) : 'Role'} agents saved for this project.`,
      });
    } catch (err) {
      toast.error('Failed to update project agent access', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  }, [selectedRoleId, projectId, checkedAgents, updateMutation, selectedRoleConfig]);

  const handleResetToGlobal = useCallback(async () => {
    if (!selectedRoleId) return;
    try {
      await resetMutation.mutateAsync({ projectId, roleId: selectedRoleId });
      setIsDirty(false);
      toast.success('Reset to global defaults', {
        description: `${selectedRoleConfig?.role_name ? getRoleDisplayName(selectedRoleConfig.role_name) : 'Role'} now inherits global agent access.`,
      });
    } catch (err) {
      toast.error('Failed to reset agent access', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  }, [selectedRoleId, projectId, resetMutation, selectedRoleConfig]);

  const isLoading = projectAgentsLoading || catalogLoading;

  const hasFooter = !!(selectedRoleId && selectedRoleConfig);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-xl p-0 flex flex-col">
        {/* ── Header ── */}
        <SheetHeader className="px-6 pt-6 pb-4 border-b border-border flex-shrink-0">
          <SheetTitle className="flex items-center gap-2 text-base">
            <Bot className="w-5 h-5 text-[#746FA7]" />
            Project Agent Access
          </SheetTitle>
          <SheetDescription>
            Configure which SDLC agents each role can access in <strong>{projectName}</strong>.
            You can only restrict agents within the global ceiling set by platform admin.
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
                    {roles.map((r) => (
                      <SelectItem key={r.role_id} value={r.role_id}>
                        <span className="flex items-center gap-2">
                          {getRoleDisplayName(r.role_name)}
                          {r.mode === 'override' && (
                            <Badge variant="outline" className="ml-1 text-[10px] px-1.5 py-0 text-amber-600 border-amber-300">
                              customized
                            </Badge>
                          )}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Mode indicator */}
              {selectedRoleConfig && (
                <div className="flex items-start gap-2.5 rounded-lg border border-border bg-muted/40 px-4 py-3 text-xs text-muted-foreground">
                  {selectedRoleConfig.mode === 'inherit' ? (
                    <>
                      <ShieldCheck className="w-4 h-4 mt-0.5 flex-shrink-0 text-green-500" />
                      <span>
                        Inheriting global defaults ({selectedRoleConfig.global_agent_ids.length} agents).
                        Changes below will create a project-level override.
                      </span>
                    </>
                  ) : (
                    <>
                      <Info className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-500" />
                      <span>
                        Custom override active — {selectedRoleConfig.effective_agent_ids.length} of {selectedRoleConfig.global_agent_ids.length} global agents enabled.
                      </span>
                    </>
                  )}
                </div>
              )}

              {/* Agent Checklist */}
              {selectedRoleId && selectedRoleConfig ? (
                <>
                  {/* Bulk actions */}
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      {checkedAgents.size} of {selectedRoleConfig.global_agent_ids.length} agents selected
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
                    const relevantAgents = agents.filter((a) => globalCeiling.has(a.id));
                    if (relevantAgents.length === 0) return null;

                    return (
                      <div key={cat} className="space-y-2">
                        <div className="flex items-center gap-2">
                          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            {CATEGORY_LABELS[cat] ?? cat}
                          </h4>
                          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                            {relevantAgents.filter((a) => checkedAgents.has(a.id)).length}/{relevantAgents.length}
                          </Badge>
                        </div>
                        <div className="space-y-1">
                          {relevantAgents.map((agent) => (
                            <label
                              key={agent.id}
                              className="flex items-start gap-3 cursor-pointer rounded-lg p-2.5 hover:bg-accent/50 transition-colors"
                            >
                              <Checkbox
                                checked={checkedAgents.has(agent.id)}
                                onCheckedChange={(checked) => handleToggle(agent.id, checked === true)}
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

                  {/* Uncategorized agents in the ceiling */}
                  {(() => {
                    const otherAgents = (catalogData?.agents ?? []).filter(
                      (a) => globalCeiling.has(a.id) && !CATEGORY_ORDER.includes(a.category || ''),
                    );
                    if (otherAgents.length === 0) return null;
                    return (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Other</h4>
                          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                            {otherAgents.filter((a) => checkedAgents.has(a.id)).length}/{otherAgents.length}
                          </Badge>
                        </div>
                        <div className="space-y-1">
                          {otherAgents.map((agent) => (
                            <label
                              key={agent.id}
                              className="flex items-start gap-3 cursor-pointer rounded-lg p-2.5 hover:bg-accent/50 transition-colors"
                            >
                              <Checkbox
                                checked={checkedAgents.has(agent.id)}
                                onCheckedChange={(checked) => handleToggle(agent.id, checked === true)}
                                disabled={!agent.is_active}
                                className="mt-0.5"
                              />
                              <div className="space-y-0.5 min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm font-medium leading-none">{agent.name}</span>
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
                  })()}
                </>
              ) : (
                /* No role selected hint */
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Info className="w-8 h-8 text-muted-foreground/50 mb-3" />
                  <p className="text-sm text-muted-foreground">
                    Select a role above to configure its agent access for this project.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Fixed footer ── */}
        {hasFooter && (
          <div className="px-6 py-4 border-t border-border flex-shrink-0">
            <div className="flex items-center gap-3">
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
              {selectedRoleConfig?.mode === 'override' && (
                <Button
                  variant="outline"
                  onClick={handleResetToGlobal}
                  disabled={resetMutation.isPending}
                  className="flex-shrink-0"
                >
                  {resetMutation.isPending ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <RotateCcw className="w-4 h-4 mr-2" />
                  )}
                  Reset
                </Button>
              )}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
