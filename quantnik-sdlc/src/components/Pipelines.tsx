import { useState } from 'react';
import { 
  Search, 
  Plus, 
  GitBranch, 
  GitCommit, 
  Play, 
  Pause, 
  RotateCcw, 
  CheckCircle, 
  AlertCircle, 
  XCircle, 
  Clock, 
  Calendar,
  Settings,
  Download,
  Eye,
  Filter,
  Home,
  Activity,
  Timer,
  Code,
  Upload,
  TestTube,
  Shield,
  Package,
  FileCode,
  Users,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Zap,
  Target,
  Gauge
} from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from './ui/breadcrumb';
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from './ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Progress } from './ui/progress';

interface PipelineRun {
  id: string;
  buildNumber: number;
  status: 'running' | 'success' | 'failed' | 'pending' | 'cancelled';
  duration: string;
  timestamp: string;
  commitHash: string;
}

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
  stages?: number;
  environment?: string;
  project?: string;
}

interface RecentActivity {
  id: string;
  pipeline: string;
  action: string;
  author: string;
  timestamp: string;
  status: 'success' | 'failed' | 'running';
}

interface PipelinesProps {
  onBack: () => void;
  onNavigateToPipelineStudio: (pipeline: Pipeline) => void;
  isDarkMode?: boolean;
  onToggleTheme?: () => void;
}

export function Pipelines({ onBack, onNavigateToPipelineStudio, isDarkMode, onToggleTheme }: PipelinesProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  const mockPipelines: Pipeline[] = [
    {
      id: '1',
      name: 'frontend-app-ci-cd',
      repository: 'ecommerce-frontend',
      project: 'E-Commerce Platform',
      branch: 'main',
      status: 'success',
      lastRun: '2 hours ago',
      duration: '8m 32s',
      commitHash: 'a1b2c3d',
      commitMessage: 'Fix header navigation and update dependencies',
      author: 'Alice Johnson',
      buildNumber: 156,
      stages: 3,
      environment: 'Production'
    },
    {
      id: '2',
      name: 'backend-service-ci-cd',
      repository: 'user-management-api',
      project: 'User Management',
      branch: 'develop',
      status: 'running',
      lastRun: '5 minutes ago',
      duration: '12m 15s',
      commitHash: 'e4f5g6h',
      commitMessage: 'Implement user authentication service with JWT',
      author: 'Bob Smith',
      buildNumber: 98,
      stages: 4,
      environment: 'Staging'
    },
    {
      id: '3',
      name: 'mobile-app-ci-cd',
      repository: 'mobile-shopping-app',
      project: 'Mobile Platform',
      branch: 'release/v2.1',
      status: 'failed',
      lastRun: '1 day ago',
      duration: '15m 08s',
      commitHash: 'i7j8k9l',
      commitMessage: 'Add new payment integration and fix checkout flow',
      author: 'Carol Davis',
      buildNumber: 203,
      stages: 5,
      environment: 'Production'
    },
    {
      id: '4',
      name: 'infrastructure-pipeline',
      repository: 'terraform-infrastructure',
      project: 'Infrastructure',
      branch: 'main',
      status: 'success',
      lastRun: '6 hours ago',
      duration: '22m 44s',
      commitHash: 'm0n1o2p',
      commitMessage: 'Update EKS cluster configuration and scaling policies',
      author: 'David Wilson',
      buildNumber: 87,
      stages: 6,
      environment: 'Production'
    },
    {
      id: '5',
      name: 'data-pipeline-etl',
      repository: 'analytics-data-pipeline',
      project: 'Data Analytics',
      branch: 'feature/enhanced-metrics',
      status: 'pending',
      lastRun: '3 days ago',
      duration: '31m 12s',
      commitHash: 'q3r4s5t',
      commitMessage: 'Implement new data transformation logic for customer analytics',
      author: 'Emma Brown',
      buildNumber: 45,
      stages: 4,
      environment: 'Staging'
    },
    {
      id: '6',
      name: 'microservice-auth-ci-cd',
      repository: 'auth-microservice',
      project: 'Authentication Service',
      branch: 'hotfix/security-patch',
      status: 'cancelled',
      lastRun: '12 hours ago',
      duration: '3m 17s',
      commitHash: 'u6v7w8x',
      commitMessage: 'Critical security patch for authentication vulnerability',
      author: 'Frank Miller',
      buildNumber: 156,
      stages: 3,
      environment: 'Production'
    },
    {
      id: '7',
      name: 'notification-service-deploy',
      repository: 'notification-microservice',
      project: 'Communication Platform',
      branch: 'main',
      status: 'success',
      lastRun: '4 hours ago',
      duration: '6m 22s',
      commitHash: 'y9z0a1b',
      commitMessage: 'Improve email delivery performance and add SMS support',
      author: 'Grace Lee',
      buildNumber: 234,
      stages: 4,
      environment: 'Production'
    },
    {
      id: '8',
      name: 'payment-gateway-ci-cd',
      repository: 'payment-processing-api',
      project: 'Payment Platform',
      branch: 'feature/stripe-integration',
      status: 'running',
      lastRun: '30 minutes ago',
      duration: '18m 45s',
      commitHash: 'c2d3e4f',
      commitMessage: 'Integrate Stripe payment gateway with webhook handling',
      author: 'Henry Zhang',
      buildNumber: 412,
      stages: 5,
      environment: 'Staging'
    },
    {
      id: '9',
      name: 'monitoring-stack-deploy',
      repository: 'observability-platform',
      project: 'DevOps Tools',
      branch: 'main',
      status: 'failed',
      lastRun: '8 hours ago',
      duration: '25m 16s',
      commitHash: 'g5h6i7j',
      commitMessage: 'Deploy Prometheus and Grafana monitoring stack',
      author: 'Isabella Rodriguez',
      buildNumber: 89,
      stages: 7,
      environment: 'Production'
    },
    {
      id: '10',
      name: 'api-gateway-deployment',
      repository: 'api-gateway-service',
      project: 'API Management',
      branch: 'develop',
      status: 'success',
      lastRun: '1 day ago',
      duration: '11m 33s',
      commitHash: 'k8l9m0n',
      commitMessage: 'Add rate limiting and enhanced security middleware',
      author: 'Jack Thompson',
      buildNumber: 178,
      stages: 4,
      environment: 'Staging'
    },
    {
      id: '11',
      name: 'database-migration-pipeline',
      repository: 'database-schemas',
      project: 'Data Platform',
      branch: 'main',
      status: 'running',
      lastRun: '15 minutes ago',
      duration: '28m 41s',
      commitHash: 'p1q2r3s',
      commitMessage: 'Add new customer analytics tables and indexes',
      author: 'Kevin Park',
      buildNumber: 67,
      stages: 5,
      environment: 'Production'
    },
    {
      id: '12',
      name: 'security-scanner-ci-cd',
      repository: 'security-audit-tools',
      project: 'Security Operations',
      branch: 'feature/vulnerability-detection',
      status: 'failed',
      lastRun: '2 hours ago',
      duration: '19m 24s',
      commitHash: 't4u5v6w',
      commitMessage: 'Implement automated vulnerability scanning for containers',
      author: 'Laura Martinez',
      buildNumber: 134,
      stages: 6,
      environment: 'Staging'
    },
    {
      id: '13',
      name: 'content-management-deploy',
      repository: 'cms-platform',
      project: 'Content Platform',
      branch: 'release/v3.2',
      status: 'success',
      lastRun: '3 hours ago',
      duration: '14m 17s',
      commitHash: 'x7y8z9a',
      commitMessage: 'Add multilingual support and improved content editor',
      author: 'Maria Santos',
      buildNumber: 245,
      stages: 4,
      environment: 'Production'
    },
    {
      id: '14',
      name: 'load-testing-pipeline',
      repository: 'performance-testing',
      project: 'Quality Assurance',
      branch: 'main',
      status: 'pending',
      lastRun: '5 hours ago',
      duration: '45m 22s',
      commitHash: 'b2c3d4e',
      commitMessage: 'Add comprehensive load testing for checkout process',
      author: 'Nathan Wright',
      buildNumber: 89,
      stages: 3,
      environment: 'Staging'
    },
    {
      id: '15',
      name: 'search-service-ci-cd',
      repository: 'elasticsearch-service',
      project: 'Search Platform',
      branch: 'feature/faceted-search',
      status: 'cancelled',
      lastRun: '6 hours ago',
      duration: '7m 55s',
      commitHash: 'f5g6h7i',
      commitMessage: 'Implement faceted search and auto-suggestions',
      author: 'Olivia Chang',
      buildNumber: 156,
      stages: 4,
      environment: 'Staging'
    },
    {
      id: '16',
      name: 'backup-automation-pipeline',
      repository: 'backup-orchestration',
      project: 'Data Protection',
      branch: 'hotfix/retention-policy',
      status: 'success',
      lastRun: '8 hours ago',
      duration: '35m 12s',
      commitHash: 'j8k9l0m',
      commitMessage: 'Fix backup retention policy and add encryption',
      author: 'Peter Johnson',
      buildNumber: 78,
      stages: 7,
      environment: 'Production'
    },
    {
      id: '17',
      name: 'chatbot-service-deploy',
      repository: 'ai-chatbot-service',
      project: 'AI Platform',
      branch: 'develop',
      status: 'running',
      lastRun: '10 minutes ago',
      duration: '21m 38s',
      commitHash: 'n1o2p3q',
      commitMessage: 'Improve natural language processing and response accuracy',
      author: 'Quinn Davis',
      buildNumber: 312,
      stages: 5,
      environment: 'Staging'
    },
    {
      id: '18',
      name: 'analytics-dashboard-ci-cd',
      repository: 'business-intelligence',
      project: 'Analytics Platform',
      branch: 'feature/real-time-metrics',
      status: 'failed',
      lastRun: '12 hours ago',
      duration: '26m 47s',
      commitHash: 'r4s5t6u',
      commitMessage: 'Add real-time dashboard updates and custom visualizations',
      author: 'Rachel Green',
      buildNumber: 189,
      stages: 6,
      environment: 'Staging'
    },
    {
      id: '19',
      name: 'video-processing-pipeline',
      repository: 'media-processing-service',
      project: 'Media Platform',
      branch: 'main',
      status: 'success',
      lastRun: '14 hours ago',
      duration: '52m 15s',
      commitHash: 'v7w8x9y',
      commitMessage: 'Add support for 4K video transcoding and thumbnail generation',
      author: 'Samuel Lee',
      buildNumber: 423,
      stages: 8,
      environment: 'Production'
    },
    {
      id: '20',
      name: 'email-service-deployment',
      repository: 'email-notification-service',
      project: 'Communication Platform',
      branch: 'feature/template-engine',
      status: 'pending',
      lastRun: '16 hours ago',
      duration: '9m 28s',
      commitHash: 'z0a1b2c',
      commitMessage: 'Implement dynamic email templates and personalization',
      author: 'Tina Wilson',
      buildNumber: 267,
      stages: 3,
      environment: 'Staging'
    }
  ];

  const recentActivities: RecentActivity[] = [
    {
      id: '1',
      pipeline: 'frontend-app-ci-cd',
      action: 'Pipeline completed successfully',
      author: 'Alice Johnson',
      timestamp: '2 hours ago',
      status: 'success'
    },
    {
      id: '2',
      pipeline: 'backend-service-ci-cd',
      action: 'Build stage started',
      author: 'Bob Smith',
      timestamp: '5 minutes ago',
      status: 'running'
    },
    {
      id: '3',
      pipeline: 'mobile-app-ci-cd',
      action: 'Pipeline failed at test stage',
      author: 'Carol Davis',
      timestamp: '1 day ago',
      status: 'failed'
    },
    {
      id: '4',
      pipeline: 'infrastructure-pipeline',
      action: 'Deployment to production completed',
      author: 'David Wilson',
      timestamp: '6 hours ago',
      status: 'success'
    }
  ];

  const recentExecutions = [
    {
      id: '1',
      pipeline: 'frontend-app-ci-cd',
      buildNumber: 156,
      status: 'success',
      duration: '8m 32s',
      timestamp: '2 hours ago',
      author: 'Alice Johnson'
    },
    {
      id: '2',
      pipeline: 'backend-service-ci-cd',
      buildNumber: 98,
      status: 'running',
      duration: '12m 15s',
      timestamp: '5 minutes ago',
      author: 'Bob Smith'
    },
    {
      id: '3',
      pipeline: 'mobile-app-ci-cd',
      buildNumber: 203,
      status: 'failed',
      duration: '15m 08s',
      timestamp: '1 day ago',
      author: 'Carol Davis'
    },
    {
      id: '4',
      pipeline: 'infrastructure-pipeline',
      buildNumber: 87,
      status: 'success',
      duration: '22m 44s',
      timestamp: '6 hours ago',
      author: 'David Wilson'
    }
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success': return '#27AE60';
      case 'failed': return '#E74C3C';
      case 'running': return '#3498DB';
      case 'pending': return '#F39C12';
      case 'cancelled': return '#95A5A6';
      default: return '#95A5A6';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success': return <CheckCircle className="w-4 h-4" />;
      case 'failed': return <XCircle className="w-4 h-4" />;
      case 'running': return <Play className="w-4 h-4" />;
      case 'pending': return <Clock className="w-4 h-4" />;
      case 'cancelled': return <Pause className="w-4 h-4" />;
      default: return <Clock className="w-4 h-4" />;
    }
  };

  const filteredPipelines = mockPipelines.filter(pipeline =>
    pipeline.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    pipeline.repository.toLowerCase().includes(searchQuery.toLowerCase()) ||
    pipeline.project?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    pipeline.author.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalPages = Math.ceil(filteredPipelines.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentPipelines = filteredPipelines.slice(startIndex, endIndex);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
    setCurrentPage(1); // Reset to first page when searching
  };

  const handleItemsPerPageChange = (value: string) => {
    setItemsPerPage(parseInt(value));
    setCurrentPage(1); // Reset to first page when changing items per page
  };

  const RunHistoryVisualization = ({ runs }: { runs: PipelineRun[] }) => {
    return (
      <div className="flex items-center space-x-1">
        {runs.slice(0, 8).map((run, index) => (
          <div
            key={run.id}
            className="w-3 h-3 rounded-full border border-border"
            style={{ backgroundColor: getStatusColor(run.status) }}
            title={`Build #${run.buildNumber} • ${run.status} • ${run.timestamp} • ${run.duration !== '-' ? run.duration : 'No duration'}`}
          >
            {run.status === 'running' && (
              <div className="w-1.5 h-1.5 bg-white rounded-full animate-pulse mx-auto mt-0.5"></div>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Breadcrumb */}
      <div className="bg-card border-b border-border px-6 py-4 pt-8">
        <div className="max-w-7xl mx-auto">
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink 
                  href="#" 
                  onClick={(e) => {
                    e.preventDefault();
                    onBack();
                  }}
                  className="flex items-center space-x-1 cursor-pointer"
                >
                  <Home className="w-4 h-4 dark:brightness-200" />
                  <span>Dashboard</span>
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>CI/CD Pipelines</BreadcrumbPage>
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
              <h1 className="text-foreground">CI/CD Pipelines</h1>
              <p className="text-muted-foreground mt-1">Manage your continuous integration and deployment pipelines</p>
            </div>
            <div className="flex items-center space-x-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground dark:brightness-150 w-4 h-4" />
                <Input
                  placeholder="Search pipelines..."
                  value={searchQuery}
                  onChange={handleSearchChange}
                  className="pl-10 w-80 border border-border dark:border-gray-600"
                />
              </div>
              <Button className="flex items-center space-x-2 cursor-pointer bg-[#351A55] dark:bg-[#5A3B7D] hover:bg-[#2D1248] dark:hover:bg-[#6B46A3] text-[rgba(255,255,255,1)]">
                <Plus className="w-4 h-4" />
                <span className="text-[rgba(255,255,255,1)]">New Pipeline</span>
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Analytics Cards */}
      <div className="bg-background border-b border-border px-6 py-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {/* Success Rate Card */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Success Rate</p>
                    <div className="flex items-center space-x-2 mt-1">
                      <span className="text-2xl font-medium text-card-foreground">87.3%</span>
                      <div className="flex items-center text-green-600 dark:text-green-400">
                        <TrendingUp className="w-3 h-3 mr-1" />
                        <span className="text-xs">+2.1%</span>
                      </div>
                    </div>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/20 flex items-center justify-center">
                    <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
                  </div>
                </div>
                <div className="mt-4">
                  <div className="text-xs text-muted-foreground">vs last week</div>
                </div>
              </CardContent>
            </Card>

            {/* Average Build Time Card */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Avg Build Time</p>
                    <div className="flex items-center space-x-2 mt-1">
                      <span className="text-2xl font-medium text-card-foreground">8m 34s</span>
                      <div className="flex items-center text-green-600 dark:text-green-400">
                        <TrendingDown className="w-3 h-3 mr-1" />
                        <span className="text-xs">-45s</span>
                      </div>
                    </div>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/20 flex items-center justify-center">
                    <Timer className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  </div>
                </div>
                <div className="mt-4">
                  <div className="text-xs text-muted-foreground">vs last week</div>
                </div>
              </CardContent>
            </Card>

            {/* Active Pipelines Card */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Active Pipelines</p>
                    <div className="flex items-center space-x-2 mt-1">
                      <span className="text-2xl font-medium text-card-foreground">24</span>
                      <div className="flex items-center text-blue-600 dark:text-blue-400">
                        <TrendingUp className="w-3 h-3 mr-1" />
                        <span className="text-xs">+3</span>
                      </div>
                    </div>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/20 flex items-center justify-center">
                    <Activity className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                  </div>
                </div>
                <div className="mt-4">
                  <div className="text-xs text-muted-foreground">vs last month</div>
                </div>
              </CardContent>
            </Card>

            {/* Deployment Frequency Card */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Deployments/Day</p>
                    <div className="flex items-center space-x-2 mt-1">
                      <span className="text-2xl font-medium text-card-foreground">12.4</span>
                      <div className="flex items-center text-green-600 dark:text-green-400">
                        <TrendingUp className="w-3 h-3 mr-1" />
                        <span className="text-xs">+1.8</span>
                      </div>
                    </div>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-orange-100 dark:bg-orange-900/20 flex items-center justify-center">
                    <Zap className="w-5 h-5 text-orange-600 dark:text-orange-400" />
                  </div>
                </div>
                <div className="mt-4">
                  <div className="text-xs text-muted-foreground">vs last week</div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Additional Analytics Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Pipeline Health Score */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-card-foreground">Pipeline Health Score</h3>
                  <Gauge className="w-5 h-5 text-muted-foreground" />
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-3xl font-medium text-card-foreground">94</span>
                    <div className="text-right">
                      <div className="text-xs text-green-600 dark:text-green-400 flex items-center">
                        <TrendingUp className="w-3 h-3 mr-1" />
                        +3 pts
                      </div>
                      <div className="text-xs text-muted-foreground">vs last week</div>
                    </div>
                  </div>
                  <div className="w-full bg-muted rounded-full h-2">
                    <div className="bg-green-500 h-2 rounded-full" style={{ width: '94%' }}></div>
                  </div>
                  <div className="text-xs text-muted-foreground">Excellent pipeline performance</div>
                </div>
              </CardContent>
            </Card>

            {/* Top Performing Repository */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-card-foreground">Top Performer</h3>
                  <Target className="w-5 h-5 text-muted-foreground" />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <Code className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                    <span className="text-sm font-medium text-card-foreground">frontend-app-ci-cd</span>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <div className="text-muted-foreground">Success Rate</div>
                      <div className="text-green-600 dark:text-green-400 font-medium">98.5%</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Avg Duration</div>
                      <div className="text-card-foreground font-medium">6m 12s</div>
                    </div>
                  </div>
                  <div className="pt-2">
                    <div className="text-xs text-muted-foreground">156 successful builds this week</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Recent Trends */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-card-foreground">Recent Trends</h3>
                  <BarChart3 className="w-5 h-5 text-muted-foreground" />
                </div>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">Failed Builds</span>
                    <div className="flex items-center text-red-600 dark:text-red-400">
                      <TrendingDown className="w-3 h-3 mr-1" />
                      <span className="text-xs">-23%</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">Build Speed</span>
                    <div className="flex items-center text-green-600 dark:text-green-400">
                      <TrendingUp className="w-3 h-3 mr-1" />
                      <span className="text-xs">+12%</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">Code Coverage</span>
                    <div className="flex items-center text-green-600 dark:text-green-400">
                      <TrendingUp className="w-3 h-3 mr-1" />
                      <span className="text-xs">+5.2%</span>
                    </div>
                  </div>
                  <div className="pt-1 text-xs text-muted-foreground">Data from last 30 days</div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto px-6 py-8 w-full">
        <Tabs defaultValue="pipelines" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3 max-w-md">
            <TabsTrigger value="pipelines" className="cursor-pointer">Pipelines</TabsTrigger>
            <TabsTrigger value="activity" className="cursor-pointer">Recent Activity</TabsTrigger>
            <TabsTrigger value="executions" className="cursor-pointer">Executions</TabsTrigger>
          </TabsList>

          <TabsContent value="pipelines" className="space-y-6 min-h-[800px]">
            {/* Results Summary */}
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <p className="text-sm text-muted-foreground">
                  Showing {startIndex + 1}-{Math.min(endIndex, filteredPipelines.length)} of {filteredPipelines.length} pipelines
                </p>
                <div className="flex items-center space-x-2">
                  <label className="text-sm text-muted-foreground">Items per page:</label>
                  <Select value={itemsPerPage.toString()} onValueChange={handleItemsPerPageChange}>
                    <SelectTrigger className="w-20 cursor-pointer">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="5" className="cursor-pointer">5</SelectItem>
                      <SelectItem value="10" className="cursor-pointer">10</SelectItem>
                      <SelectItem value="20" className="cursor-pointer">20</SelectItem>
                      <SelectItem value="50" className="cursor-pointer">50</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <p className="text-sm text-muted-foreground">
                Page {currentPage} of {totalPages}
              </p>
            </div>

            <div className="grid gap-6">
              {currentPipelines.map((pipeline, index) => (
                <Card 
                  key={pipeline.id} 
                  className="border border-border hover:shadow-xl hover:border-blue-300 dark:hover:border-blue-600 transition-all duration-300 cursor-pointer group hover:bg-gradient-to-br hover:from-blue-50 hover:to-purple-50 dark:hover:from-blue-950/20 dark:hover:to-purple-950/20 transform hover:-translate-y-1"
                  onClick={() => onNavigateToPipelineStudio(pipeline)}
                >
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-3">
                          <div className="flex items-center space-x-2">
                            <GitBranch className="w-5 h-5 text-foreground group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors duration-300" />
                            <h3 className="text-card-foreground group-hover:text-blue-900 dark:group-hover:text-blue-200 transition-colors duration-300">{pipeline.name}</h3>
                          </div>
                          <Badge 
                            className="px-2 py-1 flex items-center space-x-1 group-hover:border-blue-400 group-hover:text-blue-700 dark:group-hover:text-blue-300 transition-colors duration-300"
                            style={{ 
                              backgroundColor: 'transparent',
                              color: getStatusColor(pipeline.status),
                              border: `1px solid ${getStatusColor(pipeline.status)}`
                            }}
                          >
                            {getStatusIcon(pipeline.status)}
                            <span>{pipeline.status}</span>
                          </Badge>
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4 text-sm">
                          <div className="flex items-center space-x-2 text-muted-foreground group-hover:text-gray-600 dark:group-hover:text-gray-400 transition-colors duration-300">
                            <Code className="w-4 h-4 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors duration-300" />
                            <span>{pipeline.repository}</span>
                          </div>
                          <div className="flex items-center space-x-2 text-muted-foreground group-hover:text-gray-600 dark:group-hover:text-gray-400 transition-colors duration-300">
                            <GitCommit className="w-4 h-4 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors duration-300" />
                            <span>{pipeline.branch}</span>
                          </div>
                          <div className="flex items-center space-x-2 text-muted-foreground group-hover:text-gray-600 dark:group-hover:text-gray-400 transition-colors duration-300">
                            <Timer className="w-4 h-4 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors duration-300" />
                            <span>{pipeline.duration}</span>
                          </div>
                          <div className="flex items-center space-x-2 text-muted-foreground group-hover:text-gray-600 dark:group-hover:text-gray-400 transition-colors duration-300">
                            <Clock className="w-4 h-4 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors duration-300" />
                            <span>{pipeline.lastRun}</span>
                          </div>
                        </div>

                        <div className="flex items-center justify-between">
                          <div className="text-sm text-muted-foreground group-hover:text-gray-600 dark:group-hover:text-gray-400 transition-colors duration-300">
                            <span>Build #{pipeline.buildNumber} • {pipeline.commitHash} • {pipeline.author}</span>
                          </div>
                          <RunHistoryVisualization runs={[
                            { id: '1', buildNumber: pipeline.buildNumber, status: pipeline.status, duration: pipeline.duration, timestamp: pipeline.lastRun, commitHash: pipeline.commitHash },
                            { id: '2', buildNumber: pipeline.buildNumber - 1, status: 'success', duration: '7m 45s', timestamp: '1 day ago', commitHash: 'x9y8z7w' },
                            { id: '3', buildNumber: pipeline.buildNumber - 2, status: 'failed', duration: '5m 12s', timestamp: '2 days ago', commitHash: 'p6q5r4s' },
                            { id: '4', buildNumber: pipeline.buildNumber - 3, status: 'success', duration: '9m 18s', timestamp: '3 days ago', commitHash: 'l3m2n1o' },
                            { id: '5', buildNumber: pipeline.buildNumber - 4, status: 'cancelled', duration: '2m 05s', timestamp: '4 days ago', commitHash: 'h0i9j8k' },
                            { id: '6', buildNumber: pipeline.buildNumber - 5, status: 'success', duration: '8m 22s', timestamp: '5 days ago', commitHash: 'a1b2c3d' },
                            { id: '7', buildNumber: pipeline.buildNumber - 6, status: 'success', duration: '6m 55s', timestamp: '6 days ago', commitHash: 'e4f5g6h' },
                            { id: '8', buildNumber: pipeline.buildNumber - 7, status: 'failed', duration: '4m 33s', timestamp: '1 week ago', commitHash: 'i7j8k9l' }
                          ]} />
                        </div>
                      </div>

                      <div className="flex items-center space-x-2 ml-4">
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            onNavigateToPipelineStudio(pipeline);
                          }}
                          className="cursor-pointer"
                        >
                          <Settings className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex justify-center mt-8">
                <Pagination>
                  <PaginationContent>
                    <PaginationItem>
                      <PaginationPrevious 
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          if (currentPage > 1) handlePageChange(currentPage - 1);
                        }}
                        className={currentPage === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                      />
                    </PaginationItem>
                    
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                      <PaginationItem key={page}>
                        <PaginationLink
                          href="#"
                          onClick={(e) => {
                            e.preventDefault();
                            handlePageChange(page);
                          }}
                          isActive={currentPage === page}
                          className="cursor-pointer"
                        >
                          {page}
                        </PaginationLink>
                      </PaginationItem>
                    ))}
                    
                    <PaginationItem>
                      <PaginationNext 
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          if (currentPage < totalPages) handlePageChange(currentPage + 1);
                        }}
                        className={currentPage === totalPages ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                      />
                    </PaginationItem>
                  </PaginationContent>
                </Pagination>
              </div>
            )}
          </TabsContent>

          <TabsContent value="activity" className="space-y-6 min-h-[800px]">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Activity className="w-5 h-5 dark:brightness-200" style={{ color: '#351A55' }} />
                  <span>Recent Activity</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {recentActivities.map((activity, index) => (
                  <div key={activity.id} className="flex items-start space-x-4 p-4 bg-muted rounded-lg">
                    <div className="mt-1">
                      <div 
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: getStatusColor(activity.status) }}
                      ></div>
                    </div>
                    <div className="flex-1">
                      <p className="text-card-foreground mb-1">{activity.action}</p>
                      <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                        <span className="flex items-center space-x-1">
                          <Users className="w-4 h-4 dark:brightness-150" />
                          <span>{activity.author}</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <Calendar className="w-4 h-4 dark:brightness-150" />
                          <span>{activity.timestamp}</span>
                        </span>
                        <Badge variant="outline" className="text-xs">
                          {activity.pipeline}
                        </Badge>
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="executions" className="space-y-6 min-h-[800px]">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Play className="w-5 h-5 dark:brightness-200" style={{ color: '#351A55' }} />
                  <span>Recent Executions</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {recentExecutions.map((execution, index) => (
                  <div key={execution.id} className="flex items-start space-x-4 p-4 bg-muted rounded-lg">
                    <div className="mt-1">
                      <div 
                        className="w-8 h-8 rounded-full flex items-center justify-center text-white"
                        style={{ backgroundColor: getStatusColor(execution.status) }}
                      >
                        {getStatusIcon(execution.status)}
                      </div>
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <h4 className="text-card-foreground">{execution.pipeline}</h4>
                        <span className="text-sm text-muted-foreground">#{execution.buildNumber}</span>
                      </div>
                      <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                        <span className="flex items-center space-x-1">
                          <Users className="w-4 h-4 dark:brightness-150" />
                          <span>{execution.author}</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <Timer className="w-4 h-4 dark:brightness-150" />
                          <span>{execution.duration}</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <Calendar className="w-4 h-4 dark:brightness-150" />
                          <span>{execution.timestamp}</span>
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}