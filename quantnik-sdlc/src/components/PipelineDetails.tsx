import { useState } from 'react';
import { ArrowLeft, Play, CheckCircle, AlertCircle, Clock, X, GitBranch, Calendar, User, Hash, Download, ExternalLink, Settings, MoreVertical, Home } from 'lucide-react';
import { Header } from './Header';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from './ui/breadcrumb';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Progress } from './ui/progress';
import { Separator } from './ui/separator';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/dropdown-menu';

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

interface PipelineDetailsProps {
  pipeline: Pipeline;
  onBack: () => void;
  onBackToDashboard: () => void;
  onConfigure: () => void;
  isDarkMode: boolean;
  onToggleTheme: () => void;
}

interface PipelineRun {
  id: string;
  buildNumber: number;
  status: 'running' | 'success' | 'failed' | 'pending' | 'cancelled';
  trigger: 'manual' | 'commit' | 'schedule';
  branch: string;
  commitHash: string;
  commitMessage: string;
  author: string;
  startTime: string;
  duration: string;
  stages: {
    name: string;
    status: 'running' | 'success' | 'failed' | 'pending' | 'cancelled' | 'skipped';
    duration?: string;
  }[];
}

const mockPipelineRuns: PipelineRun[] = [
  {
    id: '1',
    buildNumber: 245,
    status: 'success',
    trigger: 'commit',
    branch: 'main',
    commitHash: 'a1b2c3d',
    commitMessage: 'feat: add user authentication system',
    author: 'John Doe',
    startTime: '2 hours ago',
    duration: '4m 32s',
    stages: [
      { name: 'Build', status: 'success', duration: '1m 45s' },
      { name: 'Test', status: 'success', duration: '2m 15s' },
      { name: 'Deploy', status: 'success', duration: '32s' }
    ]
  },
  {
    id: '2',
    buildNumber: 244,
    status: 'failed',
    trigger: 'commit',
    branch: 'feature/auth',
    commitHash: 'x9y8z7w',
    commitMessage: 'fix: resolve authentication bug',
    author: 'Jane Smith',
    startTime: '6 hours ago',
    duration: '2m 18s',
    stages: [
      { name: 'Build', status: 'success', duration: '1m 30s' },
      { name: 'Test', status: 'failed', duration: '48s' },
      { name: 'Deploy', status: 'skipped' }
    ]
  },
  {
    id: '3',
    buildNumber: 243,
    status: 'running',
    trigger: 'manual',
    branch: 'develop',
    commitHash: 'p5q4r3s',
    commitMessage: 'refactor: improve code structure',
    author: 'Mike Wilson',
    startTime: '10 minutes ago',
    duration: '2m 15s',
    stages: [
      { name: 'Build', status: 'success', duration: '1m 20s' },
      { name: 'Test', status: 'running', duration: '55s' },
      { name: 'Deploy', status: 'pending' }
    ]
  }
];

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'success':
      return <CheckCircle className="w-4 h-4 text-green-500" />;
    case 'failed':
      return <X className="w-4 h-4 text-red-500" />;
    case 'running':
      return <Clock className="w-4 h-4 text-blue-500 animate-spin" />;
    case 'pending':
      return <Clock className="w-4 h-4 text-yellow-500" />;
    case 'cancelled':
      return <X className="w-4 h-4 text-gray-500" />;
    default:
      return <Clock className="w-4 h-4 text-gray-400" />;
  }
};

const getStatusBadge = (status: string) => {
  const variants = {
    success: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    failed: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    running: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    cancelled: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
    skipped: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
  };

  return (
    <Badge variant="secondary" className={variants[status as keyof typeof variants] || variants.pending}>
      {status}
    </Badge>
  );
};

export function PipelineDetails({ 
  pipeline, 
  onBack, 
  onBackToDashboard, 
  onConfigure, 
  isDarkMode, 
  onToggleTheme 
}: PipelineDetailsProps) {
  const [activeTab, setActiveTab] = useState('runs');

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header 
        onLogoClick={onBackToDashboard} 
        isDarkMode={isDarkMode} 
        onToggleTheme={onToggleTheme} 
      />
      
      <div className="flex-1">
        {/* Header Section */}
        <div className="px-6 py-4 bg-secondary border-b border-border">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center justify-between mb-4">
              <Breadcrumb>
                <BreadcrumbList>
                  <BreadcrumbItem>
                    <BreadcrumbLink 
                      href="#" 
                      onClick={(e) => {
                        e.preventDefault();
                        onBackToDashboard();
                      }}
                      className="flex items-center space-x-1 cursor-pointer"
                    >
                      <Home className="w-4 h-4" />
                      <span>Dashboard</span>
                    </BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    <BreadcrumbLink 
                      href="#" 
                      onClick={(e) => {
                        e.preventDefault();
                        onBack();
                      }}
                      className="cursor-pointer"
                    >
                      Pipelines
                    </BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator />
                  <BreadcrumbPage>{pipeline.name}</BreadcrumbPage>
                </BreadcrumbList>
              </Breadcrumb>

              <div className="flex items-center space-x-2">
                <Button onClick={onConfigure} className="bg-[#3498B3] hover:bg-[#2980A9] text-white">
                  <Settings className="w-4 h-4 mr-2" />
                  Configure
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="icon">
                      <MoreVertical className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem>
                      <Download className="w-4 h-4 mr-2" />
                      Export Logs
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <ExternalLink className="w-4 h-4 mr-2" />
                      View in GitHub
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>

            {/* Pipeline Overview */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
              <div className="lg:col-span-3">
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 bg-[#3498B3] rounded-lg flex items-center justify-center">
                    <GitBranch className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h1 className="text-foreground">{pipeline.name}</h1>
                    <div className="flex items-center space-x-4 mt-1">
                      <span className="text-muted-foreground">{pipeline.repository}</span>
                      <span className="text-muted-foreground">•</span>
                      <span className="text-muted-foreground">{pipeline.branch}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-end space-x-4">
                {getStatusIcon(pipeline.status)}
                {getStatusBadge(pipeline.status)}
              </div>
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
              <Card>
                <CardContent className="p-4">
                  <div className="text-muted-foreground">Last Run</div>
                  <div className="text-foreground mt-1">{pipeline.lastRun}</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <div className="text-muted-foreground">Duration</div>
                  <div className="text-foreground mt-1">{pipeline.duration}</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <div className="text-muted-foreground">Build #</div>
                  <div className="text-foreground mt-1">#{pipeline.buildNumber}</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <div className="text-muted-foreground">Success Rate</div>
                  <div className="text-foreground mt-1">92.3%</div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>

        {/* Content Tabs */}
        <div className="px-6 py-6">
          <div className="max-w-7xl mx-auto">
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="grid w-full grid-cols-4 max-w-md">
                <TabsTrigger value="runs">Runs</TabsTrigger>
                <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
                <TabsTrigger value="metrics">Metrics</TabsTrigger>
                <TabsTrigger value="settings">Settings</TabsTrigger>
              </TabsList>

              <TabsContent value="runs" className="mt-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Pipeline Runs</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Build</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Trigger</TableHead>
                          <TableHead>Branch</TableHead>
                          <TableHead>Commit</TableHead>
                          <TableHead>Author</TableHead>
                          <TableHead>Started</TableHead>
                          <TableHead>Duration</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {mockPipelineRuns.map((run) => (
                          <TableRow key={run.id}>
                            <TableCell>#{run.buildNumber}</TableCell>
                            <TableCell>
                              <div className="flex items-center space-x-2">
                                {getStatusIcon(run.status)}
                                {getStatusBadge(run.status)}
                              </div>
                            </TableCell>
                            <TableCell>{run.trigger}</TableCell>
                            <TableCell>
                              <div className="flex items-center space-x-1">
                                <GitBranch className="w-3 h-3" />
                                <span>{run.branch}</span>
                              </div>
                            </TableCell>
                            <TableCell>
                              <div>
                                <div className="flex items-center space-x-1">
                                  <Hash className="w-3 h-3" />
                                  <code className="text-xs">{run.commitHash}</code>
                                </div>
                                <div className="text-muted-foreground truncate max-w-48">
                                  {run.commitMessage}
                                </div>
                              </div>
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center space-x-1">
                                <User className="w-3 h-3" />
                                <span>{run.author}</span>
                              </div>
                            </TableCell>
                            <TableCell>{run.startTime}</TableCell>
                            <TableCell>{run.duration}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="artifacts" className="mt-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Build Artifacts</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-center py-8 text-muted-foreground">
                      No artifacts available for this pipeline
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="metrics" className="mt-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Card>
                    <CardHeader>
                      <CardTitle>Success Rate</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        <div>
                          <div className="flex justify-between mb-2">
                            <span>Last 30 days</span>
                            <span>92.3%</span>
                          </div>
                          <Progress value={92.3} className="h-2" />
                        </div>
                        <Separator />
                        <div className="text-muted-foreground">
                          <div>Total runs: 156</div>
                          <div>Successful: 144</div>
                          <div>Failed: 12</div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Average Duration</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        <div className="text-foreground">4m 32s</div>
                        <Separator />
                        <div className="text-muted-foreground space-y-1">
                          <div>Fastest: 2m 18s</div>
                          <div>Slowest: 8m 45s</div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              <TabsContent value="settings" className="mt-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Pipeline Settings</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-center py-8 text-muted-foreground">
                      Pipeline settings will be configured in the Pipeline Studio
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>

    </div>
  );
}