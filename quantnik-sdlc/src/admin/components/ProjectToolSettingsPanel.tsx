/**
 * ProjectToolSettingsPanel
 *
 * Sheet for configuring project tool integrations (service registry).
 * MLOps and SuperAdmin can enable/disable tools and set config + secrets.
 * Platform-disabled tools are greyed out (unavailable).
 */

import { useState, useCallback } from 'react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '../../components/ui/sheet';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { ScrollArea } from '../../components/ui/scroll-area';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Switch } from '../../components/ui/switch';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { Card } from '../../components/ui/card';
import {
  ArrowLeft,
  Wrench,
  ExternalLink,
  Check,
  Key,
  Lock,
  Settings,
} from 'lucide-react';
import { toast } from 'sonner';

import { useProjectSettings, useUpdateToolConfig } from '../hooks/useProjects';
import type { ProjectInfo, ProjectToolInfo } from '../api/adminApi';

interface ProjectToolSettingsPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  project: ProjectInfo;
  readOnly?: boolean;
}

// Field definition type for tool config forms
interface FieldDef {
  key: string;
  label: string;
  placeholder?: string;
  type?: string;       // 'text' | 'secret' — maps to isSecret
  isSecret?: boolean;
}

// Well-known config fields for each tool type (legacy fallback)
const TOOL_CONFIG_FIELDS: Record<string, FieldDef[]> = {
  jira: [
    { key: 'url', label: 'Instance URL', placeholder: 'https://your-org.atlassian.net' },
    { key: 'projectKey', label: 'Project Key', placeholder: 'PROJ' },
    { key: 'email', label: 'Service Account Email', placeholder: 'user@company.com' },
    { key: 'patToken', label: 'PAT Token', placeholder: 'Enter your Jira PAT', isSecret: true },
  ],
  github: [
    { key: 'url', label: 'Repository URL', placeholder: 'https://github.com/org/repo' },
    { key: 'patToken', label: 'Personal Access Token', placeholder: 'ghp_…', isSecret: true },
  ],
  confluence: [
    { key: 'url', label: 'Instance URL', placeholder: 'https://your-org.atlassian.net' },
    { key: 'spaceKey', label: 'Space Key', placeholder: 'DOCS' },
    { key: 'spaceId', label: 'Space ID', placeholder: '36569092' },
    { key: 'email', label: 'Service Account Email', placeholder: 'user@company.com' },
    { key: 'patToken', label: 'PAT Token', placeholder: 'Enter your Confluence PAT', isSecret: true },
  ],
  sharepoint: [
    { key: 'url', label: 'Site URL', placeholder: 'https://your-org.sharepoint.com/sites/...' },
    { key: 'patToken', label: 'Access Token', placeholder: 'Enter access token', isSecret: true },
  ],
  sonarqube: [
    { key: 'url', label: 'Instance URL', placeholder: 'https://sonarqube.example.com' },
    { key: 'patToken', label: 'Token', placeholder: 'Enter SonarQube token', isSecret: true },
  ],
  qtest: [
    { key: 'url', label: 'API URL', placeholder: 'https://your-org.qtestnet.com/api/v3' },
    { key: 'qtestProjectId', label: 'Project ID', placeholder: '123456' },
    { key: 'patToken', label: 'API Token', placeholder: 'Enter qTest API token', isSecret: true },
  ],
  'harness-pipelines': [
    { key: 'url', label: 'Harness URL', placeholder: 'https://app.harness.io' },
    { key: 'accountId', label: 'Account ID', placeholder: 'abc123' },
    { key: 'orgIdentifier', label: 'Org Identifier', placeholder: 'default' },
    { key: 'projectIdentifier', label: 'Project Identifier', placeholder: 'my_project' },
    { key: 'patToken', label: 'API Key', placeholder: 'Enter Harness API key', isSecret: true },
  ],
  'harness-repo': [
    { key: 'url', label: 'Harness URL', placeholder: 'https://app.harness.io' },
    { key: 'accountId', label: 'Account ID', placeholder: 'abc123' },
    { key: 'orgIdentifier', label: 'Org Identifier', placeholder: 'default' },
    { key: 'repoIdentifier', label: 'Repo Identifier', placeholder: 'my_repo' },
    { key: 'patToken', label: 'API Key', placeholder: 'Enter Harness API key', isSecret: true },
  ],
  snyk: [
    { key: 'orgId', label: 'Snyk Org ID', placeholder: 'your-snyk-org-id' },
    { key: 'patToken', label: 'API Token', placeholder: 'Enter Snyk API token', isSecret: true },
  ],
  trivy: [
    { key: 'serverUrl', label: 'Trivy Server URL', placeholder: 'http://trivy-server:4954' },
    { key: 'patToken', label: 'Token (optional)', placeholder: 'Enter token if required', isSecret: true },
  ],
};

// Fallback fields for unknown tool types
const DEFAULT_CONFIG_FIELDS: FieldDef[] = [
  { key: 'url', label: 'URL', placeholder: 'https://...' },
  { key: 'patToken', label: 'Access Token', placeholder: 'Enter token', isSecret: true },
];

export function ProjectToolSettingsPanel({ open, onOpenChange, project, readOnly = false }: ProjectToolSettingsPanelProps) {
  const { data, isLoading } = useProjectSettings(project.id);
  const updateMutation = useUpdateToolConfig();

  const [configuringTool, setConfiguringTool] = useState<ProjectToolInfo | null>(null);
  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [secretValues, setSecretValues] = useState<Record<string, string>>({});
  const [enabledState, setEnabledState] = useState(false);

  const tools = data?.tools ?? [];

  const openConfigDialog = useCallback((tool: ProjectToolInfo) => {
    setConfiguringTool(tool);
    // Populate form with existing config values
    const cfg: Record<string, string> = {};
    if (tool.config && typeof tool.config === 'object') {
      for (const [k, v] of Object.entries(tool.config)) {
        cfg[k] = String(v ?? '');
      }
    }
    setConfigValues(cfg);
    setSecretValues({});
    setEnabledState(tool.projectEnabled);
  }, []);

  const handleToggle = useCallback(async (tool: ProjectToolInfo, enabled: boolean) => {
    try {
      await updateMutation.mutateAsync({
        projectId: project.id,
        serviceId: tool.serviceId,
        data: {
          config: (tool.config as Record<string, unknown>) ?? {},
          is_enabled: enabled,
          secrets: {},
        },
      });
      toast.success(`${tool.name} ${enabled ? 'enabled' : 'disabled'}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update');
    }
  }, [project.id, updateMutation]);

  const handleSaveConfig = async () => {
    if (!configuringTool) return;

    // Build full config object (non-secret fields)
    const fullConfig: Record<string, unknown> = { ...configValues };

    // Build secrets (only send non-empty values)
    const secrets: Record<string, string> = {};
    for (const [k, v] of Object.entries(secretValues)) {
      if (v.trim()) secrets[k] = v.trim();
    }

    try {
      await updateMutation.mutateAsync({
        projectId: project.id,
        serviceId: configuringTool.serviceId,
        data: {
          config: fullConfig,
          is_enabled: enabledState,
          secrets,
        },
      });
      toast.success(`${configuringTool.name} configuration saved`);
      setConfiguringTool(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save');
    }
  };

  const getFieldsForTool = (tool: ProjectToolInfo): FieldDef[] => {
    // Priority: structured defaultConfig.fields → hardcoded TOOL_CONFIG_FIELDS → DEFAULT_CONFIG_FIELDS
    const dynamicFields = (tool.defaultConfig as { fields?: FieldDef[] })?.fields;
    if (Array.isArray(dynamicFields) && dynamicFields.length > 0) {
      return dynamicFields.map(f => ({
        ...f,
        isSecret: f.isSecret ?? f.type === 'secret',
      }));
    }
    return TOOL_CONFIG_FIELDS[tool.toolId] ?? DEFAULT_CONFIG_FIELDS;
  };

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="w-full sm:max-w-3xl p-0 flex flex-col">
          <SheetHeader className="px-6 pt-6 pb-4 border-b border-border flex-shrink-0">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
                <ArrowLeft className="w-4 h-4" />
              </Button>
              <div className="flex-1">
                <SheetTitle className="flex items-center gap-2">
                  <Wrench className="w-5 h-5" />
                  Tool Settings — {project.name}
                </SheetTitle>
                <SheetDescription>
                  {readOnly
                    ? 'View integration status for this project. Contact MLOps to make changes.'
                    : 'Configure integrations for this project. Platform-disabled tools are unavailable.'}
                </SheetDescription>
              </div>
            </div>
          </SheetHeader>

          <ScrollArea className="flex-1 min-h-0">
            {isLoading ? (
              <div className="p-6 space-y-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-20 w-full rounded-md" />
                ))}
              </div>
            ) : tools.length === 0 ? (
              <div className="p-12 text-center text-muted-foreground">
                <Wrench className="w-12 h-12 mx-auto mb-3 opacity-40" />
                <p className="text-sm font-medium">No platform services registered</p>
                <p className="text-xs mt-1">Ask your SuperAdmin to register services.</p>
              </div>
            ) : (
              <div className="p-4 space-y-3">
                {tools.map((tool) => (
                  <Card
                    key={tool.serviceId}
                    className={`p-4 transition-all ${
                      !tool.available
                        ? 'opacity-50 bg-muted/30'
                        : tool.projectEnabled && tool.configured
                          ? 'border-green-500/40 bg-green-950/10'
                          : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                            tool.color
                              ? `bg-gradient-to-br ${tool.color}`
                              : 'bg-muted'
                          }`}
                        >
                          <span className="text-lg">{tool.icon ?? '🔧'}</span>
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium">{tool.name}</p>
                            {!tool.available && (
                              <Badge variant="secondary" className="text-[10px]">
                                <Lock className="w-3 h-3 mr-1" />
                                Platform Disabled
                              </Badge>
                            )}
                            {tool.available && tool.configured && tool.projectEnabled && (
                              <Badge variant="outline" className="text-[10px] border-green-500/40 text-green-500">
                                <Check className="w-3 h-3 mr-1" />
                                Configured
                              </Badge>
                            )}
                            {tool.hasSecrets && (
                              <Badge variant="outline" className="text-[10px]">
                                <Key className="w-3 h-3 mr-1" />
                                {tool.secretKeys.length} secret{tool.secretKeys.length !== 1 ? 's' : ''}
                              </Badge>
                            )}
                          </div>
                          {tool.description && (
                            <p className="text-xs text-muted-foreground">{tool.description}</p>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        {tool.available && !readOnly && (
                          <>
                            <Switch
                              checked={tool.projectEnabled}
                              onCheckedChange={(checked) => handleToggle(tool, checked)}
                              disabled={updateMutation.isPending}
                            />
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => openConfigDialog(tool)}
                            >
                              <Settings className="w-4 h-4 mr-1" />
                              Configure
                            </Button>
                          </>
                        )}
                        {tool.available && readOnly && (
                          <Badge variant={tool.projectEnabled ? 'outline' : 'secondary'} className="text-[10px]">
                            {tool.projectEnabled ? 'Enabled' : 'Disabled'}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </ScrollArea>
        </SheetContent>
      </Sheet>

      {/* Configure Tool Dialog */}
      <Dialog open={!!configuringTool} onOpenChange={() => setConfiguringTool(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <span className="text-lg">{configuringTool?.icon ?? '🔧'}</span>
              Configure {configuringTool?.name}
            </DialogTitle>
            <DialogDescription>
              Set up the connection details for this integration. Secrets are encrypted server-side.
            </DialogDescription>
          </DialogHeader>

          {configuringTool && (
            <div className="space-y-4 py-2">
              {/* Enable toggle */}
              <div className="flex items-center justify-between">
                <Label>Enabled for this project</Label>
                <Switch checked={enabledState} onCheckedChange={setEnabledState} />
              </div>

              {/* Config fields */}
              {getFieldsForTool(configuringTool).map((field) => (
                <div key={field.key} className="space-y-2">
                  <Label className="flex items-center gap-1">
                    {field.isSecret && <Key className="w-3 h-3" />}
                    {field.label}
                  </Label>
                  {field.isSecret ? (
                    <div>
                      <Input
                        type="password"
                        placeholder={
                          configuringTool.secretKeys.includes(field.key)
                            ? '••••••••  (stored — leave blank to keep)'
                            : field.placeholder
                        }
                        value={secretValues[field.key] ?? ''}
                        onChange={(e) =>
                          setSecretValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                        }
                      />
                      {configuringTool.secretKeys.includes(field.key) && (
                        <p className="text-[10px] text-muted-foreground mt-1">
                          A secret is already stored. Leave blank to keep it.
                        </p>
                      )}
                    </div>
                  ) : (
                    <Input
                      placeholder={field.placeholder}
                      value={configValues[field.key] ?? ''}
                      onChange={(e) =>
                        setConfigValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                      }
                    />
                  )}
                </div>
              ))}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setConfiguringTool(null)}>
              Cancel
            </Button>
            <Button onClick={handleSaveConfig} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? 'Saving…' : 'Save Configuration'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
