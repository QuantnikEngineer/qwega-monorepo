import { useState } from 'react';
import { 
  Search, 
  Plus, 
  GitBranch, 
  GitCommit, 
  GitPullRequest, 
  Star, 
  Eye, 
  Code, 
  Users, 
  Calendar,
  Clock,
  CheckCircle,
  AlertCircle,
  XCircle,
  FolderOpen,
  Home,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Activity,
  Target,
  GitMerge,
  FileCode,
  Database
} from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from './ui/breadcrumb';
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from './ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';

interface Repository {
  name: string;
  description: string;
  project: string;
  language: string;
  stars: number;
  watchers: number;
  lastUpdated: string;
  status: string;
  branches: number;
  pullRequests: number;
}

interface CodeRepoProps {
  onBack: () => void;
  onNavigateToRepoDetails: (repository: Repository) => void;
  isDarkMode?: boolean;
  onToggleTheme?: () => void;
}

export function CodeRepo({ onBack, onNavigateToRepoDetails, isDarkMode, onToggleTheme }: CodeRepoProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  const repositories = [
    {
      name: 'wipro-wega-frontend',
      description: 'Main frontend application for WEGA platform',
      project: 'WEGA Platform',
      language: 'TypeScript',
      stars: 24,
      watchers: 8,
      lastUpdated: '2 hours ago',
      status: 'active',
      branches: 12,
      pullRequests: 3
    },
    {
      name: 'wipro-wega-backend',
      description: 'Backend services and APIs for WEGA',
      project: 'WEGA Platform',
      language: 'Java',
      stars: 18,
      watchers: 6,
      lastUpdated: '4 hours ago',
      status: 'active',
      branches: 8,
      pullRequests: 2
    },
    {
      name: 'wipro-infra-automation',
      description: 'Infrastructure as Code automation scripts',
      project: 'Cloud Infrastructure',
      language: 'Python',
      stars: 15,
      watchers: 12,
      lastUpdated: '1 day ago',
      status: 'stable',
      branches: 5,
      pullRequests: 1
    },
    {
      name: 'wipro-devops-pipeline',
      description: 'CI/CD pipeline configurations and templates',
      project: 'DevOps Automation',
      language: 'YAML',
      stars: 32,
      watchers: 15,
      lastUpdated: '3 days ago',
      status: 'active',
      branches: 7,
      pullRequests: 0
    },
    {
      name: 'wipro-security-scanner',
      description: 'Automated security vulnerability scanning tools',
      project: 'Security Operations',
      language: 'Go',
      stars: 28,
      watchers: 9,
      lastUpdated: '5 days ago',
      status: 'active',
      branches: 4,
      pullRequests: 1
    },
    {
      name: 'wipro-monitoring-stack',
      description: 'Comprehensive monitoring and alerting solution',
      project: 'Infrastructure Monitoring',
      language: 'Python',
      stars: 22,
      watchers: 11,
      lastUpdated: '1 week ago',
      status: 'stable',
      branches: 6,
      pullRequests: 2
    },
    {
      name: 'wipro-data-analytics',
      description: 'Business intelligence and data processing pipelines',
      project: 'Data Platform',
      language: 'Scala',
      stars: 19,
      watchers: 7,
      lastUpdated: '2 weeks ago',
      status: 'maintenance',
      branches: 9,
      pullRequests: 0
    },
    {
      name: 'wipro-api-gateway',
      description: 'Centralized API gateway for microservices architecture',
      project: 'Platform Infrastructure',
      language: 'Node.js',
      stars: 31,
      watchers: 14,
      lastUpdated: '3 days ago',
      status: 'active',
      branches: 8,
      pullRequests: 4
    },
    {
      name: 'wipro-testing-framework',
      description: 'Automated testing framework for end-to-end tests',
      project: 'Quality Assurance',
      language: 'JavaScript',
      stars: 26,
      watchers: 10,
      lastUpdated: '1 week ago',
      status: 'stable',
      branches: 11,
      pullRequests: 2
    },
    {
      name: 'wipro-config-management',
      description: 'Configuration management and environment setup tools',
      project: 'DevOps Automation',
      language: 'Ansible',
      stars: 17,
      watchers: 8,
      lastUpdated: '4 days ago',
      status: 'active',
      branches: 5,
      pullRequests: 1
    },
    {
      name: 'wipro-ml-platform',
      description: 'Machine learning model training and deployment platform',
      project: 'AI/ML Platform',
      language: 'Python',
      stars: 42,
      watchers: 18,
      lastUpdated: '6 hours ago',
      status: 'active',
      branches: 15,
      pullRequests: 6
    },
    {
      name: 'wipro-mobile-app',
      description: 'Cross-platform mobile application for WEGA',
      project: 'Mobile Development',
      language: 'React Native',
      stars: 35,
      watchers: 13,
      lastUpdated: '1 day ago',
      status: 'active',
      branches: 9,
      pullRequests: 3
    },
    {
      name: 'wipro-database-migration',
      description: 'Database schema migration and version control tools',
      project: 'Database Management',
      language: 'SQL',
      stars: 21,
      watchers: 9,
      lastUpdated: '2 days ago',
      status: 'stable',
      branches: 6,
      pullRequests: 1
    },
    {
      name: 'wipro-kubernetes-operator',
      description: 'Custom Kubernetes operators for application deployment',
      project: 'Container Orchestration',
      language: 'Go',
      stars: 38,
      watchers: 16,
      lastUpdated: '12 hours ago',
      status: 'active',
      branches: 10,
      pullRequests: 4
    },
    {
      name: 'wipro-notification-service',
      description: 'Multi-channel notification and messaging service',
      project: 'Communication Platform',
      language: 'Node.js',
      stars: 29,
      watchers: 12,
      lastUpdated: '8 hours ago',
      status: 'active',
      branches: 7,
      pullRequests: 2
    },
    {
      name: 'wipro-backup-solution',
      description: 'Automated backup and disaster recovery system',
      project: 'Data Protection',
      language: 'Bash',
      stars: 16,
      watchers: 6,
      lastUpdated: '1 week ago',
      status: 'stable',
      branches: 4,
      pullRequests: 0
    },
    {
      name: 'wipro-performance-monitor',
      description: 'Real-time application performance monitoring dashboard',
      project: 'Observability',
      language: 'TypeScript',
      stars: 33,
      watchers: 14,
      lastUpdated: '3 hours ago',
      status: 'active',
      branches: 11,
      pullRequests: 5
    },
    {
      name: 'wipro-load-balancer',
      description: 'High-availability load balancing and traffic management',
      project: 'Network Infrastructure',
      language: 'C++',
      stars: 27,
      watchers: 11,
      lastUpdated: '2 days ago',
      status: 'stable',
      branches: 8,
      pullRequests: 1
    },
    {
      name: 'wipro-documentation-portal',
      description: 'Centralized documentation and knowledge management system',
      project: 'Developer Tools',
      language: 'Markdown',
      stars: 23,
      watchers: 8,
      lastUpdated: '5 days ago',
      status: 'active',
      branches: 5,
      pullRequests: 2
    },
    {
      name: 'wipro-legacy-migration',
      description: 'Tools and utilities for migrating legacy systems',
      project: 'System Modernization',
      language: 'Java',
      stars: 14,
      watchers: 5,
      lastUpdated: '3 weeks ago',
      status: 'maintenance',
      branches: 3,
      pullRequests: 0
    }
  ];

  const recentCommits = [
    {
      message: 'feat: add new dashboard analytics component',
      author: 'Vishnuprasad Jahagirdar',
      time: '2 hours ago',
      hash: 'a7b3c9d',
      repository: 'wipro-wega-frontend'
    },
    {
      message: 'fix: resolve API timeout issues in user service',
      author: 'Sarah Chen',
      time: '4 hours ago',
      hash: 'e2f5a8b',
      repository: 'wipro-wega-backend'
    },
    {
      message: 'docs: update deployment documentation',
      author: 'Michael Rodriguez',
      time: '6 hours ago',
      hash: 'c1d4e7f',
      repository: 'wipro-infra-automation'
    },
    {
      message: 'chore: update dependencies and security patches',
      author: 'Priya Sharma',
      time: '1 day ago',
      hash: 'f8e2b5c',
      repository: 'wipro-devops-pipeline'
    }
  ];

  const pullRequests = [
    {
      title: 'Implement real-time notifications system',
      author: 'David Kim',
      repository: 'wipro-wega-frontend',
      status: 'open',
      createdAt: '2 days ago',
      reviews: 2,
      commits: 8
    },
    {
      title: 'Add performance monitoring middleware',
      author: 'Lisa Wang',
      repository: 'wipro-wega-backend',
      status: 'review',
      createdAt: '3 days ago',
      reviews: 1,
      commits: 5
    },
    {
      title: 'Update Kubernetes deployment manifests',
      author: 'Ahmed Hassan',
      repository: 'wipro-infra-automation',
      status: 'approved',
      createdAt: '5 days ago',
      reviews: 3,
      commits: 3
    }
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return '#3498B3';
      case 'stable': return '#355493';
      case 'maintenance': return '#BE266A';
      default: return '#746FA7';
    }
  };

  const getLanguageColor = (language: string) => {
    switch (language) {
      case 'TypeScript': return '#3178c6';
      case 'JavaScript': return '#f7df1e';
      case 'Java': return '#ed8b00';
      case 'Python': return '#3776ab';
      case 'Go': return '#00add8';
      case 'Scala': return '#dc322f';
      case 'Node.js': return '#339933';
      case 'Ansible': return '#ee0000';
      case 'YAML': return '#cb171e';
      case 'React Native': return '#61dafb';
      case 'SQL': return '#336791';
      case 'Bash': return '#4eaa25';
      case 'C++': return '#00599c';
      case 'Markdown': return '#083fa1';
      default: return '#6366f1';
    }
  };

  const getPRStatusIcon = (status: string) => {
    switch (status) {
      case 'open': return <GitPullRequest className="w-4 h-4 text-blue-500 dark:brightness-150" />;
      case 'review': return <AlertCircle className="w-4 h-4 text-yellow-500 dark:brightness-150" />;
      case 'approved': return <CheckCircle className="w-4 h-4 text-green-500 dark:brightness-150" />;
      case 'closed': return <XCircle className="w-4 h-4 text-red-500 dark:brightness-150" />;
      default: return <GitPullRequest className="w-4 h-4 text-muted-foreground dark:brightness-150" />;
    }
  };

  const filteredRepositories = repositories.filter(repo =>
    repo.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    repo.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    repo.project.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalPages = Math.ceil(filteredRepositories.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentRepositories = filteredRepositories.slice(startIndex, endIndex);

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
                <BreadcrumbPage>Code Repositories</BreadcrumbPage>
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
              <h1 className="text-foreground">Code Repositories</h1>
              <p className="text-muted-foreground mt-1">Manage your source code and development projects</p>
            </div>
            <div className="flex items-center space-x-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground dark:brightness-150 w-4 h-4" />
                <Input
                  placeholder="Search repositories..."
                  value={searchQuery}
                  onChange={handleSearchChange}
                  className="pl-10 w-80 border border-border dark:border-gray-600"
                />
              </div>
              <Button className="flex items-center space-x-2 cursor-pointer bg-[#351A55] dark:bg-[#5A3B7D] hover:bg-[#2D1248] dark:hover:bg-[#6B46A3] text-[rgba(255,255,255,1)]">
                <Plus className="w-4 h-4" />
                <span className="text-[rgba(255,255,255,1)]">New Repository</span>
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Analytics Cards */}
      <div className="bg-background border-b border-border px-6 py-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {/* Total Repositories Card */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Repositories</p>
                    <div className="flex items-center space-x-2 mt-1">
                      <span className="text-2xl font-medium text-card-foreground">{repositories.length}</span>
                      <div className="flex items-center text-green-600 dark:text-green-400">
                        <TrendingUp className="w-3 h-3 mr-1" />
                        <span className="text-xs">+3</span>
                      </div>
                    </div>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/20 flex items-center justify-center">
                    <Code className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  </div>
                </div>
                <div className="mt-4">
                  <div className="text-xs text-muted-foreground">vs last month</div>
                </div>
              </CardContent>
            </Card>

            {/* Active Pull Requests Card */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Active Pull Requests</p>
                    <div className="flex items-center space-x-2 mt-1">
                      <span className="text-2xl font-medium text-card-foreground">
                        {repositories.reduce((sum, repo) => sum + repo.pullRequests, 0)}
                      </span>
                      <div className="flex items-center text-blue-600 dark:text-blue-400">
                        <TrendingUp className="w-3 h-3 mr-1" />
                        <span className="text-xs">+7</span>
                      </div>
                    </div>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/20 flex items-center justify-center">
                    <GitPullRequest className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                  </div>
                </div>
                <div className="mt-4">
                  <div className="text-xs text-muted-foreground">vs last week</div>
                </div>
              </CardContent>
            </Card>

            {/* Total Stars Card */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Stars</p>
                    <div className="flex items-center space-x-2 mt-1">
                      <span className="text-2xl font-medium text-card-foreground">
                        {repositories.reduce((sum, repo) => sum + repo.stars, 0)}
                      </span>
                      <div className="flex items-center text-yellow-600 dark:text-yellow-400">
                        <TrendingUp className="w-3 h-3 mr-1" />
                        <span className="text-xs">+42</span>
                      </div>
                    </div>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-yellow-100 dark:bg-yellow-900/20 flex items-center justify-center">
                    <Star className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
                  </div>
                </div>
                <div className="mt-4">
                  <div className="text-xs text-muted-foreground">vs last month</div>
                </div>
              </CardContent>
            </Card>

            {/* Active Branches Card */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Active Branches</p>
                    <div className="flex items-center space-x-2 mt-1">
                      <span className="text-2xl font-medium text-card-foreground">
                        {repositories.reduce((sum, repo) => sum + repo.branches, 0)}
                      </span>
                      <div className="flex items-center text-green-600 dark:text-green-400">
                        <TrendingUp className="w-3 h-3 mr-1" />
                        <span className="text-xs">+12</span>
                      </div>
                    </div>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/20 flex items-center justify-center">
                    <GitBranch className="w-5 h-5 text-green-600 dark:text-green-400" />
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
            {/* Repository Health Score */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-card-foreground">Repository Health</h3>
                  <Activity className="w-5 h-5 text-muted-foreground" />
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-3xl font-medium text-card-foreground">91</span>
                    <div className="text-right">
                      <div className="text-xs text-green-600 dark:text-green-400 flex items-center">
                        <TrendingUp className="w-3 h-3 mr-1" />
                        +5 pts
                      </div>
                      <div className="text-xs text-muted-foreground">vs last week</div>
                    </div>
                  </div>
                  <div className="w-full bg-muted rounded-full h-2">
                    <div className="bg-green-500 h-2 rounded-full" style={{ width: '91%' }}></div>
                  </div>
                  <div className="text-xs text-muted-foreground">Good repository hygiene</div>
                </div>
              </CardContent>
            </Card>

            {/* Language Distribution */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-card-foreground">Language Distribution</h3>
                  <BarChart3 className="w-5 h-5 text-muted-foreground" />
                </div>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                      <span className="text-xs text-muted-foreground">TypeScript</span>
                    </div>
                    <span className="text-xs font-medium text-card-foreground">25%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 rounded-full bg-green-500"></div>
                      <span className="text-xs text-muted-foreground">Python</span>
                    </div>
                    <span className="text-xs font-medium text-card-foreground">20%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 rounded-full bg-orange-500"></div>
                      <span className="text-xs text-muted-foreground">Java</span>
                    </div>
                    <span className="text-xs font-medium text-card-foreground">15%</span>
                  </div>
                  <div className="pt-1 text-xs text-muted-foreground">10+ other languages</div>
                </div>
              </CardContent>
            </Card>

            {/* Recent Activity */}
            <Card className="border border-border hover:shadow-lg transition-shadow duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-card-foreground">Recent Activity</h3>
                  <Target className="w-5 h-5 text-muted-foreground" />
                </div>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">Commits Today</span>
                    <div className="flex items-center text-green-600 dark:text-green-400">
                      <span className="text-xs font-medium">23</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">PRs Merged</span>
                    <div className="flex items-center text-blue-600 dark:text-blue-400">
                      <span className="text-xs font-medium">8</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">Issues Resolved</span>
                    <div className="flex items-center text-purple-600 dark:text-purple-400">
                      <span className="text-xs font-medium">12</span>
                    </div>
                  </div>
                  <div className="pt-1 text-xs text-muted-foreground">Last updated 1 hour ago</div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto px-6 py-8 w-full">
        <Tabs defaultValue="repositories" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3 max-w-md">
            <TabsTrigger value="repositories" className="cursor-pointer">Repositories</TabsTrigger>
            <TabsTrigger value="commits" className="cursor-pointer">Recent Commits</TabsTrigger>
            <TabsTrigger value="pullrequests" className="cursor-pointer">Pull Requests</TabsTrigger>
          </TabsList>

          <TabsContent value="repositories" className="space-y-6 min-h-[800px]">
            {/* Results Summary */}
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <p className="text-sm text-muted-foreground">
                  Showing {startIndex + 1}-{Math.min(endIndex, filteredRepositories.length)} of {filteredRepositories.length} repositories
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
              {currentRepositories.map((repo, index) => (
                <Card 
                  key={index} 
                  className="border border-border hover:shadow-xl hover:border-blue-300 dark:hover:border-blue-600 transition-all duration-300 cursor-pointer group hover:bg-gradient-to-br hover:from-blue-50 hover:to-purple-50 dark:hover:from-blue-950/20 dark:hover:to-purple-950/20 transform hover:-translate-y-1"
                  onClick={() => onNavigateToRepoDetails(repo)}
                >
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          <div className="flex items-center space-x-2">
                            <Code className="w-5 h-5 text-foreground group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors duration-300" />
                            <h3 className="text-card-foreground group-hover:text-blue-900 dark:group-hover:text-blue-200 transition-colors duration-300">{repo.name}</h3>
                          </div>
                          <Badge
                            variant="outline"
                            className="group-hover:border-blue-400 group-hover:text-blue-700 dark:group-hover:text-blue-300 transition-colors duration-300 dark:brightness-150 dark:saturate-125"
                            style={{ 
                              borderColor: getStatusColor(repo.status),
                              color: getStatusColor(repo.status)
                            }}
                          >
                            {repo.status}
                          </Badge>
                        </div>
                        <p className="text-muted-foreground group-hover:text-gray-700 dark:group-hover:text-gray-300 transition-colors duration-300 mb-4">{repo.description}</p>
                        <div className="flex items-center space-x-6 text-sm text-muted-foreground group-hover:text-gray-600 dark:group-hover:text-gray-400 transition-colors duration-300">
                          <div className="flex items-center space-x-1">
                            <FolderOpen className="w-4 h-4 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors duration-300 dark:brightness-150" />
                            <span>{repo.project}</span>
                          </div>
                          <div className="flex items-center space-x-1">
                            <div 
                              className="w-3 h-3 rounded-full group-hover:ring-2 group-hover:ring-blue-200 dark:group-hover:ring-blue-800 transition-all duration-300" 
                              style={{ backgroundColor: getLanguageColor(repo.language) }}
                            ></div>
                            <span>{repo.language}</span>
                          </div>
                          <div className="flex items-center space-x-1">
                            <Star className="w-4 h-4 group-hover:text-yellow-500 dark:group-hover:text-yellow-400 transition-colors duration-300 dark:brightness-150" />
                            <span>{repo.stars}</span>
                          </div>
                          <div className="flex items-center space-x-1">
                            <Eye className="w-4 h-4 group-hover:text-green-500 dark:group-hover:text-green-400 transition-colors duration-300 dark:brightness-150" />
                            <span>{repo.watchers}</span>
                          </div>
                          <div className="flex items-center space-x-1">
                            <GitBranch className="w-4 h-4 group-hover:text-purple-500 dark:group-hover:text-purple-400 transition-colors duration-300 dark:brightness-150" />
                            <span>{repo.branches} branches</span>
                          </div>
                          <div className="flex items-center space-x-1">
                            <GitPullRequest className="w-4 h-4 group-hover:text-indigo-500 dark:group-hover:text-indigo-400 transition-colors duration-300 dark:brightness-150" />
                            <span>{repo.pullRequests} PRs</span>
                          </div>
                          <div className="flex items-center space-x-1">
                            <Clock className="w-4 h-4 group-hover:text-gray-500 dark:group-hover:text-gray-400 transition-colors duration-300 dark:brightness-150" />
                            <span>Updated {repo.lastUpdated}</span>
                          </div>
                        </div>
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

          <TabsContent value="commits" className="space-y-6 min-h-[800px]">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <GitCommit className="w-5 h-5 dark:brightness-200" style={{ color: '#351A55' }} />
                  <span>Recent Commits</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {recentCommits.map((commit, index) => (
                  <div key={index} className="flex items-start space-x-4 p-4 bg-muted rounded-lg">
                    <div className="w-8 h-8 rounded-full bg-muted-foreground/20 flex items-center justify-center">
                      <GitCommit className="w-4 h-4 text-muted-foreground dark:brightness-150" />
                    </div>
                    <div className="flex-1">
                      <p className="text-card-foreground mb-1">{commit.message}</p>
                      <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                        <span className="flex items-center space-x-1">
                          <Users className="w-4 h-4 dark:brightness-150" />
                          <span>{commit.author}</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <Calendar className="w-4 h-4 dark:brightness-150" />
                          <span>{commit.time}</span>
                        </span>
                        <Badge variant="outline" className="text-xs">
                          {commit.repository}
                        </Badge>
                      </div>
                    </div>
                    <div className="text-sm text-muted-foreground font-mono">
                      {commit.hash}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="pullrequests" className="space-y-6 min-h-[800px]">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <GitPullRequest className="w-5 h-5 dark:brightness-200" style={{ color: '#351A55' }} />
                  <span>Pull Requests</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {pullRequests.map((pr, index) => (
                  <div key={index} className="flex items-start space-x-4 p-4 bg-muted rounded-lg">
                    <div className="mt-1">
                      {getPRStatusIcon(pr.status)}
                    </div>
                    <div className="flex-1">
                      <h4 className="text-card-foreground mb-1">{pr.title}</h4>
                      <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                        <span className="flex items-center space-x-1">
                          <Users className="w-4 h-4 dark:brightness-150" />
                          <span>{pr.author}</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <Calendar className="w-4 h-4 dark:brightness-150" />
                          <span>{pr.createdAt}</span>
                        </span>
                        <Badge variant="outline" className="text-xs">
                          {pr.repository}
                        </Badge>
                      </div>
                      <div className="flex items-center space-x-4 mt-2 text-xs text-muted-foreground">
                        <span>{pr.commits} commits</span>
                        <span>{pr.reviews} reviews</span>
                      </div>
                    </div>
                    <Badge
                      variant="outline"
                      className="capitalize"
                      style={{
                        borderColor: pr.status === 'open' ? '#3498B3' : 
                                   pr.status === 'review' ? '#BE266A' : 
                                   pr.status === 'approved' ? '#355493' : '#746FA7',
                        color: pr.status === 'open' ? '#3498B3' : 
                               pr.status === 'review' ? '#BE266A' : 
                               pr.status === 'approved' ? '#355493' : '#746FA7'
                      }}
                    >
                      {pr.status}
                    </Badge>
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