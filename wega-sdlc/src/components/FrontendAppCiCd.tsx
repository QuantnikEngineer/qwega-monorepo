import { ReactNode } from 'react';
import { Header } from './Header';
import { FinalBreadcrumb } from './FinalBreadcrumb';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { 
  GitBranch, 
  Clock, 
  User, 
  Calendar,
  Play,
  Pause,
  RotateCcw,
  Download,
  FileText,
  AlertCircle,
  CheckCircle,
  XCircle
} from 'lucide-react';

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

interface FrontendAppCiCdProps {
  pipeline: Pipeline;
  onBack: () => void;
  onBackToDashboard: () => void;
  isDarkMode: boolean;
  onToggleTheme: () => void;
  menuBar: ReactNode;
}

export function FrontendAppCiCd({ 
  pipeline, 
  onBack, 
  onBackToDashboard, 
  isDarkMode, 
  onToggleTheme,
  menuBar 
}: FrontendAppCiCdProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'running':
        return <Play className="h-4 w-4 text-blue-500" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      case 'cancelled':
        return <Pause className="h-4 w-4 text-gray-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'bg-green-100 text-green-800 border-green-300';
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-300';
      case 'running':
        return 'bg-blue-100 text-blue-800 border-blue-300';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'cancelled':
        return 'bg-gray-100 text-gray-800 border-gray-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  const breadcrumbItems = [
    { label: 'Dashboard', href: '#', onClick: onBackToDashboard },
    { label: 'Pipelines', href: '#', onClick: onBack },
    { label: pipeline.name, href: '#' }
  ];

  const buildStages = [
    { name: 'Source', status: 'success', duration: '2m 15s' },
    { name: 'Build', status: 'success', duration: '8m 30s' },
    { name: 'Test', status: 'running', duration: '5m 12s' },
    { name: 'Security Scan', status: 'pending', duration: '-' },
    { name: 'Deploy', status: 'pending', duration: '-' }
  ];

  const artifacts = [
    { name: 'frontend-app.zip', size: '15.2 MB', type: 'Build Artifact' },
    { name: 'test-results.xml', size: '234 KB', type: 'Test Results' },
    { name: 'coverage-report.html', size: '1.8 MB', type: 'Coverage Report' }
  ];

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <Header onLogoClick={onBackToDashboard} isDarkMode={isDarkMode} onToggleTheme={onToggleTheme} />
      
      {/* MenuBar */}
      {menuBar}
      
      {/* Breadcrumb */}
      <FinalBreadcrumb pipelineName={pipeline.name} onBackToDashboard={onBackToDashboard} onBackToPipelines={onBack} />
      
      {/* Page Title */}
      <div className="border-b border-border bg-card">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">{pipeline.name}</h1>
              <p className="text-muted-foreground mt-1">
                Build #{pipeline.buildNumber} • {pipeline.repository}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge className={`${getStatusColor(pipeline.status)} flex items-center gap-1`}>
                {getStatusIcon(pipeline.status)}
                {pipeline.status.charAt(0).toUpperCase() + pipeline.status.slice(1)}
              </Badge>
              <Button variant="outline" size="sm">
                <RotateCcw className="h-4 w-4 mr-2" />
                Retry Build
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto px-6 py-6 w-full">
        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="stages">Build Stages</TabsTrigger>
            <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
            <TabsTrigger value="logs">Build Logs</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Build Information */}
              <div className="lg:col-span-2">
                <Card className="p-6">
                  <h3 className="text-lg font-semibold mb-4">Build Information</h3>
                  <div className="space-y-4">
                    <div className="flex items-center gap-3">
                      <GitBranch className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="text-sm text-muted-foreground">Branch</p>
                        <p className="font-medium">{pipeline.branch}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <User className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="text-sm text-muted-foreground">Triggered by</p>
                        <p className="font-medium">{pipeline.author}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Calendar className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="text-sm text-muted-foreground">Started</p>
                        <p className="font-medium">{pipeline.lastRun}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Clock className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="text-sm text-muted-foreground">Duration</p>
                        <p className="font-medium">{pipeline.duration}</p>
                      </div>
                    </div>
                  </div>
                </Card>

                {/* Commit Information */}
                <Card className="p-6 mt-6">
                  <h3 className="text-lg font-semibold mb-4">Commit Information</h3>
                  <div className="space-y-3">
                    <div>
                      <p className="text-sm text-muted-foreground">Commit Hash</p>
                      <p className="font-mono text-sm">{pipeline.commitHash}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Commit Message</p>
                      <p className="font-medium">{pipeline.commitMessage}</p>
                    </div>
                  </div>
                </Card>
              </div>

              {/* Quick Actions */}
              <div>
                <Card className="p-6">
                  <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
                  <div className="space-y-3">
                    <Button className="w-full" variant="outline">
                      <Play className="h-4 w-4 mr-2" />
                      Run Pipeline
                    </Button>
                    <Button className="w-full" variant="outline">
                      <Download className="h-4 w-4 mr-2" />
                      Download Artifacts
                    </Button>
                    <Button className="w-full" variant="outline">
                      <FileText className="h-4 w-4 mr-2" />
                      View Logs
                    </Button>
                  </div>
                </Card>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="stages" className="mt-6">
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4">Build Stages</h3>
              <div className="space-y-4">
                {buildStages.map((stage, index) => (
                  <div key={index} className="flex items-center justify-between p-4 border border-border rounded-lg">
                    <div className="flex items-center gap-3">
                      {getStatusIcon(stage.status)}
                      <div>
                        <p className="font-medium">{stage.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {stage.status === 'running' ? 'In Progress' : stage.status.charAt(0).toUpperCase() + stage.status.slice(1)}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">{stage.duration}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="artifacts" className="mt-6">
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4">Build Artifacts</h3>
              <div className="space-y-4">
                {artifacts.map((artifact, index) => (
                  <div key={index} className="flex items-center justify-between p-4 border border-border rounded-lg">
                    <div className="flex items-center gap-3">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="font-medium">{artifact.name}</p>
                        <p className="text-sm text-muted-foreground">{artifact.type}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <p className="text-sm text-muted-foreground">{artifact.size}</p>
                      <Button size="sm" variant="outline">
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="logs" className="mt-6">
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4">Build Logs</h3>
              <div className="bg-muted p-4 rounded-lg font-mono text-sm max-h-96 overflow-y-auto">
                <div className="space-y-1">
                  <p className="text-green-600">[2024-01-15 10:30:15] Starting build process...</p>
                  <p className="text-blue-600">[2024-01-15 10:30:16] Checking out code from repository</p>
                  <p className="text-blue-600">[2024-01-15 10:30:18] Installing dependencies...</p>
                  <p className="text-green-600">[2024-01-15 10:32:45] Dependencies installed successfully</p>
                  <p className="text-blue-600">[2024-01-15 10:32:46] Running build script...</p>
                  <p className="text-blue-600">[2024-01-15 10:35:12] Compiling TypeScript...</p>
                  <p className="text-green-600">[2024-01-15 10:37:28] TypeScript compilation successful</p>
                  <p className="text-blue-600">[2024-01-15 10:37:30] Running tests...</p>
                  <p className="text-yellow-600">[2024-01-15 10:40:15] Test suite running...</p>
                  <p className="text-muted-foreground">[2024-01-15 10:42:30] Waiting for test completion...</p>
                </div>
              </div>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}