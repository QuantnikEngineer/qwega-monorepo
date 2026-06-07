import { useState } from 'react';
import { ArrowLeft, Play, CheckCircle, Plus, X, Save, Download, RefreshCw, Eye, EyeOff, GitBranch, GitCommit, Activity, MoreVertical, Upload, Copy, Trash2, Package, Settings, Hammer, Cog, Container, TestTube, Link, Target, Lock, Shield, Rocket, Send, Star, Hand, StopCircle, MessageSquare, Mail, Home } from 'lucide-react';

import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from './ui/breadcrumb';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { ScrollArea } from './ui/scroll-area';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { Progress } from './ui/progress';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Switch } from './ui/switch';

interface Pipeline {
  id: string;
  name: string;
  repository: string;
  branch: string;
  status: 'running' | 'success' | 'failed' | 'pending' | 'cancelled';
  lastRun: string;
  duration: string;
  commitHash: string;
  commitMessage: string;
  author: string;
  buildNumber: number;
}

interface PipelineStage {
  id: string;
  name: string;
  type: string;
  status: 'pending' | 'running' | 'success' | 'failed' | 'cancelled';
  duration: string;
  startTime: string;
  position: { x: number; y: number };
  configuration: Record<string, any>;
  dependencies: string[];
}

interface StageTemplate {
  id: string;
  name: string;
  type: string;
  description: string;
  category: string;
  icon: React.ReactNode;
  color: string;
}

interface PipelineStudioProps {
  pipeline: Pipeline;
  onBack: () => void;
  onBackToDashboard: () => void;
  isDarkMode: boolean;
  onToggleTheme: () => void;
}

export function PipelineStudio({ pipeline, onBack, onBackToDashboard, isDarkMode, onToggleTheme }: PipelineStudioProps) {
  const [activeTab, setActiveTab] = useState('visual');
  const [selectedStage, setSelectedStage] = useState<PipelineStage | null>(null);
  const [showYamlEditor, setShowYamlEditor] = useState(false);
  const [showStageLibrary, setShowStageLibrary] = useState(false);
  const [pipelineStages, setPipelineStages] = useState<PipelineStage[]>([
    {
      id: '1',
      name: 'Git Clone',
      type: 'source',
      status: 'success',
      duration: '32s',
      startTime: '8 minutes ago',
      position: { x: 100, y: 100 },
      configuration: {},
      dependencies: []
    },
    {
      id: '2',
      name: 'Install Dependencies',
      type: 'build',
      status: 'success',
      duration: '1m 24s',
      startTime: '7 minutes ago',
      position: { x: 350, y: 100 },
      configuration: {},
      dependencies: ['1']
    },
    {
      id: '3',
      name: 'Run Unit Tests',
      type: 'testing',
      status: 'success',
      duration: '2m 15s',
      startTime: '5 minutes ago',
      position: { x: 600, y: 100 },
      configuration: {},
      dependencies: ['2']
    },
    {
      id: '4',
      name: 'Security Scan',
      type: 'security',
      status: 'success',
      duration: '1m 45s',
      startTime: '3 minutes ago',
      position: { x: 850, y: 100 },
      configuration: {},
      dependencies: ['3']
    },
    {
      id: '5',
      name: 'Deploy to Production',
      type: 'deploy',
      status: 'pending',
      duration: '-',
      startTime: '-',
      position: { x: 1100, y: 100 },
      configuration: {},
      dependencies: ['4']
    }
  ]);

  const stageTemplates: StageTemplate[] = [
    // Source Control
    { id: 'git-clone', name: 'Git Clone', type: 'source', description: 'Clone repository from Git', category: 'Source', icon: <GitBranch className="w-4 h-4" />, color: '#2196F3' },
    { id: 'git-checkout', name: 'Git Checkout', type: 'source', description: 'Checkout specific branch or commit', category: 'Source', icon: <GitCommit className="w-4 h-4" />, color: '#2196F3' },
    
    // Build & CI
    { id: 'build', name: 'Build', type: 'build', description: 'Compile and build the application', category: 'Build', icon: <Hammer className="w-4 h-4" />, color: '#FF9800' },
    { id: 'docker-build', name: 'Docker Build', type: 'build', description: 'Build Docker container image', category: 'Build', icon: <Container className="w-4 h-4" />, color: '#FF9800' },
    { id: 'package', name: 'Package', type: 'build', description: 'Package application artifacts', category: 'Build', icon: <Package className="w-4 h-4" />, color: '#FF9800' },
    
    // Testing
    { id: 'unit-test', name: 'Unit Tests', type: 'testing', description: 'Run unit tests', category: 'Testing', icon: <TestTube className="w-4 h-4" />, color: '#4CAF50' },
    { id: 'integration-test', name: 'Integration Tests', type: 'testing', description: 'Run integration tests', category: 'Testing', icon: <Link className="w-4 h-4" />, color: '#4CAF50' },
    { id: 'e2e-test', name: 'E2E Tests', type: 'testing', description: 'Run end-to-end tests', category: 'Testing', icon: <Target className="w-4 h-4" />, color: '#4CAF50' },
    
    // Security
    { id: 'security-scan', name: 'Security Scan', type: 'security', description: 'Scan for security vulnerabilities', category: 'Security', icon: <Shield className="w-4 h-4" />, color: '#F44336' },
    { id: 'sast-scan', name: 'SAST Scan', type: 'security', description: 'Static Application Security Testing', category: 'Security', icon: <Lock className="w-4 h-4" />, color: '#F44336' },
    
    // Approval & Control
    { id: 'manual-approval', name: 'Manual Approval', type: 'approval', description: 'Require manual approval', category: 'Control', icon: <Hand className="w-4 h-4" />, color: '#9C27B0' },
    { id: 'gate', name: 'Quality Gate', type: 'gate', description: 'Quality gate checkpoint', category: 'Control', icon: <StopCircle className="w-4 h-4" />, color: '#9C27B0' },
    
    // Deployment
    { id: 'deploy', name: 'Deploy', type: 'deploy', description: 'Deploy to environment', category: 'Deployment', icon: <Rocket className="w-4 h-4" />, color: '#673AB7' },
    { id: 'k8s-deploy', name: 'K8s Deploy', type: 'deploy', description: 'Deploy to Kubernetes', category: 'Deployment', icon: <Settings className="w-4 h-4" />, color: '#673AB7' },
    
    // Communication
    { id: 'notification', name: 'Notification', type: 'notification', description: 'Send notifications', category: 'Communication', icon: <Send className="w-4 h-4" />, color: '#00BCD4' },
    { id: 'email', name: 'Email', type: 'notification', description: 'Send email notification', category: 'Communication', icon: <Mail className="w-4 h-4" />, color: '#00BCD4' },
    { id: 'slack', name: 'Slack', type: 'notification', description: 'Send Slack message', category: 'Communication', icon: <MessageSquare className="w-4 h-4" />, color: '#00BCD4' }
  ];

  const getStageColor = (type: string) => {
    const template = stageTemplates.find(t => t.type === type);
    return template ? template.color : '#666';
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success': return '#4CAF50';
      case 'failed': return '#F44336';
      case 'running': return '#2196F3';
      case 'pending': return '#FF9800';
      case 'cancelled': return '#9E9E9E';
      default: return '#9E9E9E';
    }
  };

  const addStage = (template: StageTemplate) => {
    const newStage: PipelineStage = {
      id: `stage-${Date.now()}`,
      name: template.name,
      type: template.type,
      status: 'pending',
      duration: '-',
      startTime: '-',
      position: { x: 100 + (pipelineStages.length * 250), y: 100 },
      configuration: {},
      dependencies: pipelineStages.length > 0 ? [pipelineStages[pipelineStages.length - 1].id] : []
    };
    setPipelineStages([...pipelineStages, newStage]);
    setShowStageLibrary(false);
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Breadcrumb */}
      <div className="bg-card border-b border-border px-6 py-3 pt-8">
        <div className="max-w-7xl mx-auto">
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink onClick={onBackToDashboard} className="text-muted-foreground hover:text-[#3498B3] cursor-pointer">
                  <Home className="w-4 h-4" />
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink onClick={onBack} className="text-muted-foreground hover:text-[#3498B3] cursor-pointer">
                  Pipelines
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage className="text-card-foreground">Pipeline Studio</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </div>
      </div>
      
      {/* Page Header */}
      <div className="bg-card border-b border-border px-6 py-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-card-foreground">Pipeline Studio</h1>
              <p className="text-muted-foreground mt-1">Visual pipeline editor for {pipeline.name}</p>
            </div>
            <div className="flex items-center space-x-3">
              <Badge variant="outline" className="px-3 py-1">
                <GitBranch className="w-3 h-3 mr-1" />
                {pipeline.branch}
              </Badge>
              <Button variant="outline" size="sm">
                <Download className="w-4 h-4 mr-2" />
                Export
              </Button>
              <Button variant="outline" size="sm">
                <Save className="w-4 h-4 mr-2" />
                Save
              </Button>
              <Button size="sm" className="bg-[#351A55] hover:bg-[#2a1444] text-white">
                <Play className="w-4 h-4 mr-2" />
                Run Pipeline
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto px-6 py-8 w-full">
        <div className="flex-1 flex flex-col">
          <div className="flex flex-1">
            {/* Center Canvas */}
            <div className="flex-1 flex flex-col">
              <div className="p-4 border-b border-border bg-card">
                <div className="w-full">
                  <Tabs value={activeTab} onValueChange={setActiveTab}>
                    <div className="flex items-center justify-between">
                      <TabsList>
                        <TabsTrigger value="visual">Visual Editor</TabsTrigger>
                        <TabsTrigger value="yaml">YAML Editor</TabsTrigger>
                        <TabsTrigger value="variables">Variables</TabsTrigger>
                        <TabsTrigger value="triggers">Triggers</TabsTrigger>
                        <TabsTrigger value="settings">Settings</TabsTrigger>
                        <TabsTrigger value="information">Information</TabsTrigger>
                      </TabsList>
                      
                      <div className="flex items-center space-x-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setShowStageLibrary(!showStageLibrary)}
                          className="flex items-center"
                        >
                          <Plus className="w-4 h-4 mr-2" />
                          Add Stage
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setShowYamlEditor(!showYamlEditor)}
                          className="flex items-center"
                        >
                          {showYamlEditor ? <EyeOff className="w-4 h-4 mr-2" /> : <Eye className="w-4 h-4 mr-2" />}
                          {showYamlEditor ? 'Hide YAML' : 'Show YAML'}
                        </Button>
                      </div>
                    </div>

                    <TabsContent value="visual" className="mt-4">
                      <div className="relative">
                        {/* Pipeline Canvas */}
                        <div className="border-2 border-dashed border-border rounded-lg p-8 min-h-[600px] bg-muted/20 relative overflow-x-auto">
                          {/* Stage Library Panel */}
                          {showStageLibrary && (
                            <div className="absolute top-4 left-4 z-10 bg-card border border-border rounded-lg shadow-lg w-80 max-h-96 overflow-y-auto">
                              <div className="p-4 border-b border-border">
                                <div className="flex items-center justify-between">
                                  <h3 className="font-medium text-card-foreground">Stage Library</h3>
                                  <Button 
                                    variant="ghost" 
                                    size="sm" 
                                    onClick={() => setShowStageLibrary(false)}
                                    className="h-6 w-6 p-0"
                                  >
                                    <X className="w-4 h-4" />
                                  </Button>
                                </div>
                              </div>
                              <div className="p-4 space-y-4">
                                {['Source', 'Build', 'Testing', 'Security', 'Control', 'Deployment', 'Communication'].map(category => (
                                  <div key={category} className="space-y-2">
                                    <h4 className="text-sm font-semibold text-foreground">{category}</h4>
                                    <div className="space-y-1">
                                      {stageTemplates.filter(template => template.category === category).map(template => (
                                        <TooltipProvider key={template.id}>
                                          <Tooltip>
                                            <TooltipTrigger asChild>
                                              <div
                                                className="flex items-center p-2 rounded-lg border border-border cursor-pointer hover:bg-accent hover:border-[#3498B3] transition-all group"
                                                onClick={() => addStage(template)}
                                              >
                                                <div 
                                                  className="w-6 h-6 rounded flex items-center justify-center text-white text-sm mr-2 flex-shrink-0"
                                                  style={{ backgroundColor: template.color }}
                                                >
                                                  {template.icon}
                                                </div>
                                                <span className="text-sm text-foreground">{template.name}</span>
                                              </div>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                              <p className="max-w-xs">{template.description}</p>
                                            </TooltipContent>
                                          </Tooltip>
                                        </TooltipProvider>
                                      ))}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Pipeline Stages */}
                          <div className="relative min-w-fit">
                            {pipelineStages.map((stage, index) => (
                              <div key={stage.id} className="absolute flex items-center" style={{ left: stage.position.x, top: stage.position.y }}>
                                {/* Connection Line */}
                                {index > 0 && (
                                  <div 
                                    className="absolute h-0.5 bg-border" 
                                    style={{ 
                                      left: -250, 
                                      top: '50%',
                                      width: 240,
                                      zIndex: 1
                                    }}
                                  />
                                )}

                                {/* Stage Card */}
                                <div className="relative group">
                                  <div
                                    className={`bg-card border rounded-lg p-4 w-52 min-w-52 h-32 cursor-pointer transition-all duration-200 hover:shadow-md hover:border-[#3498B3] group flex flex-col ${
                                      selectedStage?.id === stage.id 
                                        ? 'border-[#3498B3] shadow-md' 
                                        : 'border-border'
                                    }`}
                                    onClick={() => setSelectedStage(stage)}
                                  >
                                    {/* Header Section */}
                                    <div className="flex items-start justify-between mb-3">
                                      <div className="flex items-center space-x-3 flex-1 min-w-0">
                                        <div 
                                          className="w-8 h-8 rounded-lg flex items-center justify-center text-white flex-shrink-0"
                                          style={{ backgroundColor: getStageColor(stage.type) }}
                                        >
                                          {stageTemplates.find(t => t.type === stage.type)?.icon}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                          <h4 className="text-sm font-medium text-card-foreground truncate">{stage.name}</h4>
                                          <p className="text-xs text-muted-foreground capitalize">{stage.type}</p>
                                        </div>
                                      </div>
                                      <div className="flex items-center space-x-1">
                                        <TooltipProvider>
                                          <Popover>
                                            <PopoverTrigger asChild>
                                              <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-muted"
                                              >
                                                <Settings className="w-3 h-3" />
                                              </Button>
                                            </PopoverTrigger>
                                            <PopoverContent className="w-80 p-0" side="bottom" align="start">
                                              <div className="p-4 border-b border-border">
                                                <div className="flex items-center space-x-3">
                                                  <div 
                                                    className="w-8 h-8 rounded-lg flex items-center justify-center text-white flex-shrink-0"
                                                    style={{ backgroundColor: getStageColor(stage.type) }}
                                                  >
                                                    {stageTemplates.find(t => t.type === stage.type)?.icon}
                                                  </div>
                                                  <div>
                                                    <h3 className="text-sm font-medium text-card-foreground">{stage.name}</h3>
                                                    <p className="text-xs text-muted-foreground capitalize">{stage.type} Configuration</p>
                                                  </div>
                                                </div>
                                              </div>
                                              
                                              <div className="p-4 space-y-4 max-h-96 overflow-y-auto">
                                                {/* Basic Settings */}
                                                <div className="space-y-3">
                                                  <h4 className="text-sm font-medium">Basic Settings</h4>
                                                  <div className="space-y-2">
                                                    <div>
                                                      <Label htmlFor="stage-name" className="text-xs">Stage Name</Label>
                                                      <Input id="stage-name" defaultValue={stage.name} className="h-8" />
                                                    </div>
                                                    <div>
                                                      <Label htmlFor="description" className="text-xs">Description</Label>
                                                      <Textarea id="description" placeholder="Enter description..." rows={2} />
                                                    </div>
                                                  </div>
                                                </div>

                                                {/* Stage-specific settings */}
                                                {stage.type === 'build' && (
                                                  <div className="space-y-3">
                                                    <h4 className="text-sm font-medium">Build Settings</h4>
                                                    <div className="space-y-2">
                                                      <div>
                                                        <Label htmlFor="build-command" className="text-xs">Build Command</Label>
                                                        <Input id="build-command" placeholder="npm run build" className="h-8" />
                                                      </div>
                                                      <div>
                                                        <Label htmlFor="docker-image" className="text-xs">Docker Image</Label>
                                                        <Input id="docker-image" placeholder="node:18-alpine" className="h-8" />
                                                      </div>
                                                    </div>
                                                  </div>
                                                )}

                                                {stage.type === 'testing' && (
                                                  <div className="space-y-3">
                                                    <h4 className="text-sm font-medium">Test Settings</h4>
                                                    <div className="space-y-2">
                                                      <div>
                                                        <Label htmlFor="test-command" className="text-xs">Test Command</Label>
                                                        <Input id="test-command" placeholder="npm test" className="h-8" />
                                                      </div>
                                                      <div className="flex items-center space-x-2">
                                                        <Switch id="coverage" />
                                                        <Label htmlFor="coverage" className="text-xs">Generate Coverage</Label>
                                                      </div>
                                                    </div>
                                                  </div>
                                                )}

                                                {stage.type === 'deploy' && (
                                                  <div className="space-y-3">
                                                    <h4 className="text-sm font-medium">Deploy Settings</h4>
                                                    <div className="space-y-2">
                                                      <div>
                                                        <Label htmlFor="target" className="text-xs">Target Environment</Label>
                                                        <Select>
                                                          <SelectTrigger className="h-8">
                                                            <SelectValue placeholder="Select target" />
                                                          </SelectTrigger>
                                                          <SelectContent>
                                                            <SelectItem value="prod">Production</SelectItem>
                                                            <SelectItem value="staging">Staging</SelectItem>
                                                            <SelectItem value="dev">Development</SelectItem>
                                                          </SelectContent>
                                                        </Select>
                                                      </div>
                                                      <div className="flex items-center space-x-2">
                                                        <Switch id="auto-rollback" />
                                                        <Label htmlFor="auto-rollback" className="text-xs">Auto Rollback</Label>
                                                      </div>
                                                    </div>
                                                  </div>
                                                )}

                                                {/* Advanced Settings */}
                                                <div className="space-y-3">
                                                  <h4 className="text-sm font-medium">Advanced</h4>
                                                  <div className="space-y-2">
                                                    <div className="grid grid-cols-2 gap-2">
                                                      <div>
                                                        <Label htmlFor="timeout" className="text-xs">Timeout (min)</Label>
                                                        <Input id="timeout" type="number" placeholder="30" className="h-8" />
                                                      </div>
                                                      <div>
                                                        <Label htmlFor="retries" className="text-xs">Retries</Label>
                                                        <Input id="retries" type="number" placeholder="3" className="h-8" />
                                                      </div>
                                                    </div>
                                                    <div className="flex items-center space-x-2">
                                                      <Switch id="parallel" />
                                                      <Label htmlFor="parallel" className="text-xs">Allow Parallel</Label>
                                                    </div>
                                                  </div>
                                                </div>
                                              </div>
                                            </PopoverContent>
                                          </Popover>
                                        </TooltipProvider>
                                        
                                        <DropdownMenu>
                                          <DropdownMenuTrigger asChild>
                                            <Button
                                              variant="ghost"
                                              size="sm"
                                              className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-muted"
                                            >
                                              <MoreVertical className="w-3 h-3" />
                                            </Button>
                                          </DropdownMenuTrigger>
                                          <DropdownMenuContent align="end">
                                            <DropdownMenuItem>
                                              <Copy className="w-4 h-4 mr-2" />
                                              Duplicate
                                            </DropdownMenuItem>
                                            <DropdownMenuItem className="text-destructive">
                                              <Trash2 className="w-4 h-4 mr-2" />
                                              Delete
                                            </DropdownMenuItem>
                                          </DropdownMenuContent>
                                        </DropdownMenu>
                                      </div>
                                    </div>

                                    {/* Status Section */}
                                    <div className="flex items-center justify-between mt-auto">
                                      <div className="flex items-center space-x-2">
                                        <div 
                                          className="w-2 h-2 rounded-full"
                                          style={{ backgroundColor: getStatusColor(stage.status) }}
                                        />
                                        <span className="text-xs text-muted-foreground capitalize">{stage.status}</span>
                                      </div>
                                      <span className="text-xs text-muted-foreground">{stage.duration}</span>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </TabsContent>

                    <TabsContent value="yaml" className="mt-4">
                      <div className="border border-border rounded-lg p-6 bg-card">
                        <h3 className="text-lg font-medium text-card-foreground mb-4">Pipeline YAML Configuration</h3>
                        <div className="bg-muted p-4 rounded-lg font-mono text-sm text-muted-foreground">
                          <pre>{`
name: ${pipeline.name}
trigger:
  branches:
    include:
      - ${pipeline.branch}

variables:
  - name: buildConfiguration
    value: 'Release'

stages:
${pipelineStages.map(stage => `  - stage: ${stage.name}
    displayName: '${stage.name}'
    jobs:
      - job: ${stage.type}
        displayName: '${stage.name}'
        steps:
          - task: ${stage.type}@1
            displayName: '${stage.name}'`).join('\n\n')}
                          `}</pre>
                        </div>
                      </div>
                    </TabsContent>

                    <TabsContent value="variables" className="mt-4">
                      <div className="border border-border rounded-lg p-6 bg-card">
                        <h3 className="text-lg font-medium text-card-foreground mb-4">Pipeline Variables</h3>
                        <p className="text-muted-foreground">Configure pipeline-wide variables and parameters.</p>
                      </div>
                    </TabsContent>

                    <TabsContent value="triggers" className="mt-4">
                      <div className="border border-border rounded-lg p-6 bg-card">
                        <h3 className="text-lg font-medium text-card-foreground mb-4">Pipeline Triggers</h3>
                        <p className="text-muted-foreground">Configure when this pipeline should be triggered.</p>
                      </div>
                    </TabsContent>

                    <TabsContent value="settings" className="mt-4">
                      <div className="border border-border rounded-lg p-6 bg-card">
                        <h3 className="text-lg font-medium text-card-foreground mb-4">Pipeline Settings</h3>
                        <p className="text-muted-foreground">Configure pipeline-wide settings and permissions.</p>
                      </div>
                    </TabsContent>

                    <TabsContent value="information" className="mt-4">
                      <div className="border border-border rounded-lg p-6 bg-card">
                        <h3 className="text-lg font-medium text-card-foreground mb-4">Pipeline Information</h3>
                        <div className="grid grid-cols-2 gap-6">
                          <div>
                            <h4 className="text-sm font-medium text-card-foreground mb-2">General Information</h4>
                            <div className="space-y-2 text-sm">
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Pipeline ID:</span>
                                <span className="text-card-foreground">{pipeline.id}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Repository:</span>
                                <span className="text-card-foreground">{pipeline.repository}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Branch:</span>
                                <span className="text-card-foreground">{pipeline.branch}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Last Run:</span>
                                <span className="text-card-foreground">{pipeline.lastRun}</span>
                              </div>
                            </div>
                          </div>
                          <div>
                            <h4 className="text-sm font-medium text-card-foreground mb-2">Stage Summary</h4>
                            <div className="space-y-2 text-sm">
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Total Stages:</span>
                                <span className="text-card-foreground">{pipelineStages.length}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Success:</span>
                                <span className="text-green-600">{pipelineStages.filter(s => s.status === 'success').length}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Pending:</span>
                                <span className="text-orange-600">{pipelineStages.filter(s => s.status === 'pending').length}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Failed:</span>
                                <span className="text-red-600">{pipelineStages.filter(s => s.status === 'failed').length}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </TabsContent>
                  </Tabs>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}