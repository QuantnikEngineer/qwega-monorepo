import { useState } from 'react';
import { 
  Search, 
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
  File,
  FileText,
  Download,
  Copy,
  Settings,
  Plus,
  ArrowLeft,
  Activity,
  Tag,
  Shield,
  Zap,
  ChevronDown,
  Globe,
  Lock,
  History,
  BarChart3,
  GitFork,
  ChevronRight
} from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from './ui/breadcrumb';
import { Separator } from './ui/separator';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';

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

interface RepoDetailsProps {
  repository: Repository;
  onBack: () => void;
  onBackToRepo: () => void;
  onNavigateToFolder: (folderPath: string) => void;
  onNavigateToFile: (filePath: string) => void;
  isDarkMode?: boolean;
  onToggleTheme?: () => void;
}

export function RepoDetails({ repository, onBack, onBackToRepo, onNavigateToFolder, onNavigateToFile, isDarkMode, onToggleTheme }: RepoDetailsProps) {
  const [currentPath, setCurrentPath] = useState('');
  const [selectedCloneOption, setSelectedCloneOption] = useState('HTTPS');
  const [selectedBranch, setSelectedBranch] = useState('main');
  const [selectedTag, setSelectedTag] = useState('');
  const [copySuccess, setCopySuccess] = useState('');
  const [branchSearchTerm, setBranchSearchTerm] = useState('');
  const [tagSearchTerm, setTagSearchTerm] = useState('');

  const handleCopyToClipboard = async (text: string, type: string = 'hash') => {
    try {
      await navigator.clipboard.writeText(text);
      setCopySuccess(`${type} copied!`);
      setTimeout(() => setCopySuccess(''), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  // Function to get files for a specific path
  const getFilesForPath = (path: string) => {
    if (!path) {
      // Root level files
      return [
        { 
          name: 'src', 
          type: 'folder', 
          size: '-', 
          modified: '2 days ago',
          lastCommitDate: 'Dec 15, 2024',
          lastCommitHash: 'a7b3c9d',
          lastCommitMessage: 'feat: add new components structure',
          lastCommitAuthor: 'Vishnuprasad Jahagirdar'
        },
        { 
          name: 'public', 
          type: 'folder', 
          size: '-', 
          modified: '1 week ago',
          lastCommitDate: 'Dec 8, 2024',
          lastCommitHash: 'b8c4d1e',
          lastCommitMessage: 'feat: update public assets',
          lastCommitAuthor: 'Sarah Chen'
        },
        { 
          name: 'components', 
          type: 'folder', 
          size: '-', 
          modified: '3 hours ago',
          lastCommitDate: 'Dec 17, 2024',
          lastCommitHash: 'c9d5e2f',
          lastCommitMessage: 'refactor: optimize component performance',
          lastCommitAuthor: 'Michael Rodriguez'
        },
        { 
          name: 'package.json', 
          type: 'file', 
          size: '2.1 KB', 
          modified: '5 days ago',
          lastCommitDate: 'Dec 12, 2024',
          lastCommitHash: 'd1e6f3a',
          lastCommitMessage: 'deps: update dependencies to latest versions',
          lastCommitAuthor: 'Priya Sharma'
        },
        { 
          name: 'README.md', 
          type: 'file', 
          size: '4.3 KB', 
          modified: '1 day ago',
          lastCommitDate: 'Dec 16, 2024',
          lastCommitHash: 'e2f7a4b',
          lastCommitMessage: 'docs: improve installation instructions',
          lastCommitAuthor: 'David Kim'
        },
        { 
          name: 'tsconfig.json', 
          type: 'file', 
          size: '1.2 KB', 
          modified: '2 weeks ago',
          lastCommitDate: 'Dec 3, 2024',
          lastCommitHash: 'f3a8b5c',
          lastCommitMessage: 'config: update TypeScript configuration',
          lastCommitAuthor: 'Lisa Wang'
        },
        { 
          name: '.gitignore', 
          type: 'file', 
          size: '847 B', 
          modified: '3 weeks ago',
          lastCommitDate: 'Nov 26, 2024',
          lastCommitHash: 'a4b9c6d',
          lastCommitMessage: 'chore: update gitignore patterns',
          lastCommitAuthor: 'Ahmed Hassan'
        },
        { 
          name: 'tailwind.config.js', 
          type: 'file', 
          size: '1.8 KB', 
          modified: '1 week ago',
          lastCommitDate: 'Dec 10, 2024',
          lastCommitHash: 'b5c1d7e',
          lastCommitMessage: 'style: configure Tailwind CSS settings',
          lastCommitAuthor: 'Vishnuprasad Jahagirdar'
        }
      ];
    } else if (path === 'src') {
      return [
        {
          name: 'components',
          type: 'folder',
          size: '-',
          modified: '1 day ago',
          lastCommitDate: 'Dec 16, 2024',
          lastCommitHash: 'e2f7a4b',
          lastCommitMessage: 'feat: add new UI components',
          lastCommitAuthor: 'Sarah Chen'
        },
        {
          name: 'utils',
          type: 'folder',
          size: '-',
          modified: '3 days ago',
          lastCommitDate: 'Dec 14, 2024',
          lastCommitHash: 'c1d4e7f',
          lastCommitMessage: 'refactor: utility functions cleanup',
          lastCommitAuthor: 'Michael Rodriguez'
        },
        {
          name: 'hooks',
          type: 'folder',
          size: '-',
          modified: '1 week ago',
          lastCommitDate: 'Dec 10, 2024',
          lastCommitHash: 'f8e2b5c',
          lastCommitMessage: 'feat: custom React hooks',
          lastCommitAuthor: 'David Kim'
        },
        {
          name: 'index.tsx',
          type: 'file',
          size: '1.2 KB',
          modified: '2 days ago',
          lastCommitDate: 'Dec 15, 2024',
          lastCommitHash: 'a7b3c9d',
          lastCommitMessage: 'feat: main entry point setup',
          lastCommitAuthor: 'Vishnuprasad Jahagirdar'
        },
        {
          name: 'App.tsx',
          type: 'file',
          size: '3.4 KB',
          modified: '1 day ago',
          lastCommitDate: 'Dec 16, 2024',
          lastCommitHash: 'e2f7a4b',
          lastCommitMessage: 'feat: main application component',
          lastCommitAuthor: 'Sarah Chen'
        }
      ];
    } else if (path === 'src/components') {
      return [
        {
          name: 'ui',
          type: 'folder',
          size: '-',
          modified: '6 hours ago',
          lastCommitDate: 'Dec 17, 2024',
          lastCommitHash: 'c9d5e2f',
          lastCommitMessage: 'feat: shadcn UI components',
          lastCommitAuthor: 'Lisa Wang'
        },
        {
          name: 'Header.tsx',
          type: 'file',
          size: '2.8 KB',
          modified: '1 day ago',
          lastCommitDate: 'Dec 16, 2024',
          lastCommitHash: 'e2f7a4b',
          lastCommitMessage: 'feat: application header component',
          lastCommitAuthor: 'Sarah Chen'
        },
        {
          name: 'Footer.tsx',
          type: 'file',
          size: '1.5 KB',
          modified: '2 days ago',
          lastCommitDate: 'Dec 15, 2024',
          lastCommitHash: 'a7b3c9d',
          lastCommitMessage: 'feat: application footer component',
          lastCommitAuthor: 'Michael Rodriguez'
        },
        {
          name: 'Dashboard.tsx',
          type: 'file',
          size: '4.2 KB',
          modified: '3 hours ago',
          lastCommitDate: 'Dec 17, 2024',
          lastCommitHash: 'c9d5e2f',
          lastCommitMessage: 'feat: main dashboard component',
          lastCommitAuthor: 'Vishnuprasad Jahagirdar'
        }
      ];
    } else if (path === 'public') {
      return [
        {
          name: 'images',
          type: 'folder',
          size: '-',
          modified: '1 week ago',
          lastCommitDate: 'Dec 8, 2024',
          lastCommitHash: 'b8c4d1e',
          lastCommitMessage: 'feat: add image assets',
          lastCommitAuthor: 'Sarah Chen'
        },
        {
          name: 'favicon.ico',
          type: 'file',
          size: '15.1 KB',
          modified: '2 weeks ago',
          lastCommitDate: 'Dec 3, 2024',
          lastCommitHash: 'f3a8b5c',
          lastCommitMessage: 'feat: add favicon',
          lastCommitAuthor: 'David Kim'
        },
        {
          name: 'index.html',
          type: 'file',
          size: '1.8 KB',
          modified: '1 week ago',
          lastCommitDate: 'Dec 8, 2024',
          lastCommitHash: 'b8c4d1e',
          lastCommitMessage: 'feat: HTML template setup',
          lastCommitAuthor: 'Sarah Chen'
        },
        {
          name: 'manifest.json',
          type: 'file',
          size: '492 B',
          modified: '2 weeks ago',
          lastCommitDate: 'Dec 1, 2024',
          lastCommitHash: 'a4b9c6d',
          lastCommitMessage: 'feat: PWA manifest',
          lastCommitAuthor: 'Ahmed Hassan'
        }
      ];
    } else if (path === 'components') {
      return [
        {
          name: 'ui',
          type: 'folder',
          size: '-',
          modified: '6 hours ago',
          lastCommitDate: 'Dec 17, 2024',
          lastCommitHash: 'c9d5e2f',
          lastCommitMessage: 'feat: UI component library',
          lastCommitAuthor: 'Lisa Wang'
        },
        {
          name: 'Layout.tsx',
          type: 'file',
          size: '3.1 KB',
          modified: '1 day ago',
          lastCommitDate: 'Dec 16, 2024',
          lastCommitHash: 'e2f7a4b',
          lastCommitMessage: 'feat: layout component',
          lastCommitAuthor: 'Michael Rodriguez'
        },
        {
          name: 'Navigation.tsx',
          type: 'file',
          size: '2.7 KB',
          modified: '2 days ago',
          lastCommitDate: 'Dec 15, 2024',
          lastCommitHash: 'a7b3c9d',
          lastCommitMessage: 'feat: navigation component',
          lastCommitAuthor: 'Priya Sharma'
        }
      ];
    }
    
    // Default empty folder
    return [
      {
        name: 'empty-folder.md',
        type: 'file',
        size: '156 B',
        modified: '1 month ago',
        lastCommitDate: 'Nov 15, 2024',
        lastCommitHash: 'x1y2z3a',
        lastCommitMessage: 'docs: placeholder file',
        lastCommitAuthor: 'System'
      }
    ];
  };

  // Get current file structure based on path
  const fileStructure = getFilesForPath(currentPath);

  const recentCommits = [
    {
      message: 'feat: add repository details page with file browser',
      author: 'Vishnuprasad Jahagirdar',
      time: '2 hours ago',
      hash: 'a7b3c9d',
      verified: true
    },
    {
      message: 'fix: resolve component import issues',
      author: 'Sarah Chen',
      time: '1 day ago',
      hash: 'e2f5a8b',
      verified: true
    },
    {
      message: 'docs: update component documentation',
      author: 'Michael Rodriguez',
      time: '2 days ago',
      hash: 'c1d4e7f',
      verified: false
    },
    {
      message: 'refactor: optimize build performance',
      author: 'Priya Sharma',
      time: '3 days ago',
      hash: 'f8e2b5c',
      verified: true
    }
  ];

  const pullRequests = [
    {
      title: 'Add comprehensive error handling for API calls',
      author: 'David Kim',
      status: 'open',
      createdAt: '1 day ago',
      reviews: 2,
      commits: 5
    },
    {
      title: 'Implement real-time file synchronization',
      author: 'Lisa Wang',
      status: 'review',
      createdAt: '3 days ago',
      reviews: 1,
      commits: 8
    },
    {
      title: 'Add unit tests for core components',
      author: 'Ahmed Hassan',
      status: 'approved',
      createdAt: '5 days ago',
      reviews: 3,
      commits: 12
    }
  ];

  const branches = [
    { name: 'main', isDefault: true, lastCommit: '2 hours ago', behind: 0, ahead: 0 },
    { name: 'develop', isDefault: false, lastCommit: '1 day ago', behind: 2, ahead: 5 },
    { name: 'feature/dashboard-redesign', isDefault: false, lastCommit: '3 days ago', behind: 8, ahead: 15 },
    { name: 'hotfix/security-patch', isDefault: false, lastCommit: '1 week ago', behind: 12, ahead: 2 }
  ];

  const contributors = [
    { name: 'Vishnuprasad Jahagirdar', commits: 47, avatar: 'VJ' },
    { name: 'Sarah Chen', commits: 32, avatar: 'SC' },
    { name: 'Michael Rodriguez', commits: 28, avatar: 'MR' },
    { name: 'Priya Sharma', commits: 24, avatar: 'PS' },
    { name: 'David Kim', commits: 19, avatar: 'DK' },
    { name: 'Lisa Wang', commits: 15, avatar: 'LW' }
  ];

  const tags = [
    { name: 'v2.1.0', date: 'Dec 15, 2024', commit: 'a7b3c9d' },
    { name: 'v2.0.3', date: 'Dec 10, 2024', commit: 'e2f5a8b' },
    { name: 'v2.0.2', date: 'Dec 5, 2024', commit: 'c1d4e7f' },
    { name: 'v2.0.1', date: 'Nov 28, 2024', commit: 'f8e2b5c' },
    { name: 'v2.0.0', date: 'Nov 20, 2024', commit: 'b5c1d7e' },
    { name: 'v1.9.5', date: 'Nov 15, 2024', commit: 'a4b9c6d' }
  ];

  const cloneUrls = {
    HTTPS: `https://github.com/wipro/${repository.name}.git`,
    SSH: `git@github.com:wipro/${repository.name}.git`,
    'GitHub CLI': `gh repo clone wipro/${repository.name}`
  };

  const readmeContent = `# ${repository.name}

${repository.description}

## Overview
This repository contains the source code for the ${repository.name} project, part of the ${repository.project}. The project is built using ${repository.language} and follows modern development practices.

## Features
- Modern ${repository.language} architecture
- Comprehensive test coverage
- Automated CI/CD pipeline
- Docker containerization
- Production-ready deployment

## Getting Started

### Prerequisites
- ${repository.language} (latest LTS version)
- Docker and Docker Compose
- Git

### Installation
1. Clone the repository
   \`\`\`bash
   git clone ${cloneUrls.HTTPS}
   \`\`\`

2. Install dependencies
   \`\`\`bash
   npm install
   \`\`\`

3. Start the development server
   \`\`\`bash
   npm run dev
   \`\`\`

## Contributing
We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
`;

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

  const getFileIcon = (type: string) => {
    return type === 'folder' ? <FolderOpen className="w-4 h-4 text-blue-500 dark:brightness-150" /> : <FileText className="w-4 h-4 text-muted-foreground dark:brightness-150" />;
  };

  const handleFolderClick = (folderName: string) => {
    const newPath = currentPath ? `${currentPath}/${folderName}` : folderName;
    setCurrentPath(newPath);
  };

  const handleBreadcrumbClick = (pathIndex: number) => {
    const pathSegments = currentPath.split('/').filter(Boolean);
    const newPath = pathSegments.slice(0, pathIndex + 1).join('/');
    setCurrentPath(newPath);
  };

  // Filter branches based on search term
  const filteredBranches = branches.filter(branch =>
    branch.name.toLowerCase().includes(branchSearchTerm.toLowerCase())
  );

  // Filter tags based on search term
  const filteredTags = tags.filter(tag =>
    tag.name.toLowerCase().includes(tagSearchTerm.toLowerCase())
  );

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
                <BreadcrumbLink 
                  href="#" 
                  onClick={(e) => {
                    e.preventDefault();
                    onBackToRepo();
                  }}
                  className="cursor-pointer"
                >
                  Code Repositories
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>{repository.name}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </div>
      </div>

      {/* Repository Header */}
      <div className="bg-card border-b border-border px-6 py-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center space-x-2">
              <Code className="w-6 h-6 dark:brightness-200" style={{ color: '#351A55' }} />
              <h1 className="text-foreground">{repository.name}</h1>
              <Badge
                variant="outline"
                className="dark:brightness-150 dark:saturate-125"
                style={{ 
                  borderColor: getStatusColor(repository.status),
                  color: getStatusColor(repository.status)
                }}
              >
                {repository.status}
              </Badge>
            </div>
            <div className="flex items-center space-x-3">
              <Button variant="outline" size="sm" className="cursor-pointer">
                <Star className="w-4 h-4 mr-2 dark:brightness-150" />
                Star
              </Button>
              <Button variant="outline" size="sm" className="cursor-pointer">
                <Eye className="w-4 h-4 mr-2 dark:brightness-150" />
                Watch
              </Button>
              <Button variant="outline" size="sm" className="cursor-pointer">
                <GitFork className="w-4 h-4 mr-2 dark:brightness-150" />
                Fork
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button className="cursor-pointer bg-[rgba(226,223,251,1)] dark:bg-[#5A3B7D] hover:bg-[#2D1248] dark:hover:bg-[#6B46A3] text-white dark:text-white">
                    <Download className="w-4 h-4 mr-2" />
                    Code
                    <ChevronDown className="w-4 h-4 ml-2" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-80">
                  <div className="p-4">
                    <div className="flex items-center space-x-2 mb-3">
                      <Button 
                        variant={selectedCloneOption === 'HTTPS' ? 'default' : 'outline'} 
                        size="sm" 
                        className="cursor-pointer"
                        onClick={() => setSelectedCloneOption('HTTPS')}
                      >
                        HTTPS
                      </Button>
                      <Button 
                        variant={selectedCloneOption === 'SSH' ? 'default' : 'outline'} 
                        size="sm"
                        className="cursor-pointer"
                        onClick={() => setSelectedCloneOption('SSH')}
                      >
                        SSH
                      </Button>
                      <Button 
                        variant={selectedCloneOption === 'GitHub CLI' ? 'default' : 'outline'} 
                        size="sm"
                        className="cursor-pointer"
                        onClick={() => setSelectedCloneOption('GitHub CLI')}
                      >
                        GitHub CLI
                      </Button>
                    </div>
                    <div className="flex items-center space-x-2 p-2 bg-muted rounded">
                      <Input 
                        value={cloneUrls[selectedCloneOption as keyof typeof cloneUrls]} 
                        readOnly 
                        className="text-sm font-mono"
                      />
                      <Button 
                        variant="outline" 
                        size="sm" 
                        className="cursor-pointer"
                        onClick={() => handleCopyToClipboard(cloneUrls[selectedCloneOption as keyof typeof cloneUrls], 'Clone URL')}
                      >
                        <Copy className="w-4 h-4" />
                      </Button>
                    </div>
                    <Separator className="my-3" />
                    <DropdownMenuItem className="cursor-pointer">
                      <Download className="w-4 h-4 mr-2" />
                      Download ZIP
                    </DropdownMenuItem>
                  </div>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          <p className="text-muted-foreground mb-4">{repository.description}</p>

          {/* Repository Stats */}
          <div className="flex items-center space-x-6 text-sm text-muted-foreground">
            <div className="flex items-center space-x-1">
              <div 
                className="w-3 h-3 rounded-full" 
                style={{ backgroundColor: getLanguageColor(repository.language) }}
              ></div>
              <span>{repository.language}</span>
            </div>
            <div className="flex items-center space-x-1">
              <Star className="w-4 h-4 dark:brightness-150" />
              <span>{repository.stars} stars</span>
            </div>
            <div className="flex items-center space-x-1">
              <Eye className="w-4 h-4 dark:brightness-150" />
              <span>{repository.watchers} watching</span>
            </div>
            <div className="flex items-center space-x-1">
              <GitBranch className="w-4 h-4 dark:brightness-150" />
              <span>{repository.branches} branches</span>
            </div>
            <div className="flex items-center space-x-1">
              <GitPullRequest className="w-4 h-4 dark:brightness-150" />
              <span>{repository.pullRequests} pull requests</span>
            </div>
            <div className="flex items-center space-x-1">
              <Clock className="w-4 h-4 dark:brightness-150" />
              <span>Updated {repository.lastUpdated}</span>
            </div>
          </div>

          {/* Contributors */}
          <div className="mt-4">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <span className="text-sm font-medium text-card-foreground">Contributors:</span>
                <TooltipProvider>
                  <div className="flex space-x-1">
                    {contributors.slice(0, 5).map((contributor, index) => (
                      <Tooltip key={index}>
                        <TooltipTrigger asChild>
                          <div className="cursor-pointer hover:scale-105 transform transition-transform">
                            <Avatar className="w-8 h-8 border-2 border-white shadow-sm hover:shadow-md transition-shadow">
                              <AvatarFallback className="text-xs font-medium">{contributor.avatar}</AvatarFallback>
                            </Avatar>
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="font-medium text-foreground">{contributor.name}</p>
                          <p className="text-xs text-muted-foreground">{contributor.commits} commits</p>
                        </TooltipContent>
                      </Tooltip>
                    ))}
                    {contributors.length > 5 && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="w-8 h-8 rounded-full bg-muted border-2 border-card shadow-sm hover:shadow-md flex items-center justify-center cursor-pointer hover:scale-105 transform transition-all hover:bg-accent">
                            <span className="text-xs text-muted-foreground font-medium">+{contributors.length - 5}</span>
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="font-medium text-foreground">{contributors.length - 5} more contributors</p>
                          <div className="text-xs text-muted-foreground mt-1">
                            {contributors.slice(5).map((contributor, index) => (
                              <div key={index} className="flex justify-between">
                                <span>{contributor.name}</span>
                                <span className="ml-2">{contributor.commits} commits</span>
                              </div>
                            ))}
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    )}
                  </div>
                </TooltipProvider>
              </div>
              <div className="flex items-center space-x-1 text-sm text-muted-foreground">
                <History className="w-4 h-4 dark:brightness-150" />
                <span>{recentCommits.length + 143} commits</span>
              </div>
              <div className="flex items-center space-x-1 text-sm text-muted-foreground">
                <Lock className="w-4 h-4 dark:brightness-150" />
                <span>MIT License</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Success Notification */}
      {copySuccess && (
        <div className="fixed top-20 right-6 bg-green-500 text-white px-4 py-2 rounded-md shadow-lg z-50 transition-all duration-300">
          {copySuccess}
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto px-6 py-8 w-full">
        <Tabs defaultValue="code" className="space-y-6">
          <TabsList className="grid w-full grid-cols-5 max-w-2xl">
            <TabsTrigger value="code" className="cursor-pointer">
              <Code className="w-4 h-4 mr-2 dark:brightness-150" />
              Code
            </TabsTrigger>
            <TabsTrigger value="commits" className="cursor-pointer">
              <GitCommit className="w-4 h-4 mr-2 dark:brightness-150" />
              Commits
            </TabsTrigger>
            <TabsTrigger value="branches" className="cursor-pointer">
              <GitBranch className="w-4 h-4 mr-2 dark:brightness-150" />
              Branches
            </TabsTrigger>
            <TabsTrigger value="pullrequests" className="cursor-pointer">
              <GitPullRequest className="w-4 h-4 mr-2 dark:brightness-150" />
              Pull Requests
            </TabsTrigger>
            <TabsTrigger value="insights" className="cursor-pointer">
              <Activity className="w-4 h-4 mr-2 dark:brightness-150" />
              Insights
            </TabsTrigger>
          </TabsList>

          <TabsContent value="code" className="space-y-6 min-h-[600px]">
            {/* Branch Selector and Actions */}
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                {/* Branch Selector */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm" className="cursor-pointer">
                      <GitBranch className="w-4 h-4 mr-2 dark:brightness-150" />
                      {selectedBranch}
                      <ChevronDown className="w-4 h-4 ml-2 dark:brightness-150" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent className="w-64">
                    <div className="p-2">
                      <div className="text-sm font-medium text-card-foreground mb-2 px-2">Switch branches</div>
                      
                      {/* Search Input */}
                      <div className="relative mb-3">
                        <div className="relative">
                          <div className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 rounded-full bg-muted flex items-center justify-center">
                            <Search className="w-3 h-3 text-muted-foreground" />
                          </div>
                          <Input
                            placeholder="Search branches..."
                            value={branchSearchTerm}
                            onChange={(e) => setBranchSearchTerm(e.target.value)}
                            className="pl-11 h-9 text-sm rounded-full transition-all duration-200"
                          />
                        </div>
                      </div>

                      {/* Branch List */}
                      <div className="space-y-1 max-h-64 overflow-y-auto">
                        {filteredBranches.length > 0 ? (
                          filteredBranches.map((branch, index) => (
                            <DropdownMenuItem
                              key={index}
                              className="cursor-pointer flex items-center justify-between px-3 py-2.5 rounded-lg mx-1 hover:bg-muted"
                              onClick={() => {
                                setSelectedBranch(branch.name);
                                setBranchSearchTerm('');
                              }}
                            >
                              <div className="flex items-center space-x-3">
                                <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center">
                                  <GitBranch className="w-3 h-3 text-blue-600" />
                                </div>
                                <div className="flex items-center space-x-2">
                                  <span className="font-medium text-sm text-foreground">{branch.name}</span>
                                  {branch.isDefault && (
                                    <Badge variant="outline" className="text-xs rounded-full">
                                      Default
                                    </Badge>
                                  )}
                                </div>
                              </div>
                              {selectedBranch === branch.name && (
                                <div className="w-5 h-5 rounded-full bg-green-100 flex items-center justify-center">
                                  <CheckCircle className="w-3 h-3 text-green-600" />
                                </div>
                              )}
                            </DropdownMenuItem>
                          ))
                        ) : (
                          <div className="px-3 py-6 text-center">
                            <div className="w-8 h-8 rounded-full bg-muted mx-auto mb-2 flex items-center justify-center">
                              <Search className="w-4 h-4 text-muted-foreground" />
                            </div>
                            <div className="text-sm text-muted-foreground">
                              No branches found matching "{branchSearchTerm}"
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </DropdownMenuContent>
                </DropdownMenu>

                {/* Tag Selector */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm" className="cursor-pointer">
                      <Tag className="w-4 h-4 mr-2" />
                      {selectedTag || 'Tags'}
                      <ChevronDown className="w-4 h-4 ml-2" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent className="w-72">
                    <div className="p-2">
                      <div className="text-sm font-medium text-card-foreground mb-2 px-2">Repository tags</div>
                      
                      {/* Search Input */}
                      <div className="relative mb-3">
                        <div className="relative">
                          <div className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 rounded-full bg-muted flex items-center justify-center">
                            <Search className="w-3 h-3 text-muted-foreground" />
                          </div>
                          <Input
                            placeholder="Search tags..."
                            value={tagSearchTerm}
                            onChange={(e) => setTagSearchTerm(e.target.value)}
                            className="pl-11 h-9 text-sm rounded-full transition-all duration-200"
                          />
                        </div>
                      </div>

                      {/* Clear Selection Button */}
                      {selectedTag && (
                        <DropdownMenuItem
                          className="cursor-pointer flex items-center px-3 py-2.5 mb-2 mx-1 rounded-lg hover:bg-red-50 text-red-600 hover:text-red-700"
                          onClick={() => {
                            setSelectedTag('');
                            setTagSearchTerm('');
                          }}
                        >
                          <div className="w-5 h-5 rounded-full bg-red-100 flex items-center justify-center mr-3">
                            <XCircle className="w-3 h-3 text-red-600" />
                          </div>
                          <span className="text-sm font-medium">Clear selection</span>
                        </DropdownMenuItem>
                      )}

                      {/* Tags List */}
                      <div className="space-y-1 max-h-64 overflow-y-auto">
                        {filteredTags.length > 0 ? (
                          filteredTags.map((tag, index) => (
                            <DropdownMenuItem
                              key={index}
                              className="cursor-pointer flex items-center justify-between px-3 py-2.5 rounded-lg mx-1 hover:bg-muted"
                              onClick={() => {
                                setSelectedTag(tag.name);
                                setTagSearchTerm('');
                              }}
                            >
                              <div className="flex items-center space-x-3">
                                <div className="w-6 h-6 rounded-full bg-purple-100 flex items-center justify-center">
                                  <Tag className="w-3 h-3 text-purple-600" />
                                </div>
                                <div>
                                  <div className="font-medium text-sm text-foreground">{tag.name}</div>
                                  <div className="text-xs text-muted-foreground">
                                    {tag.date} • {tag.commit}
                                  </div>
                                </div>
                              </div>
                              {selectedTag === tag.name && (
                                <div className="w-5 h-5 rounded-full bg-green-100 flex items-center justify-center">
                                  <CheckCircle className="w-3 h-3 text-green-600" />
                                </div>
                              )}
                            </DropdownMenuItem>
                          ))
                        ) : (
                          <div className="px-3 py-6 text-center">
                            <div className="w-8 h-8 rounded-full bg-muted mx-auto mb-2 flex items-center justify-center">
                              <Search className="w-4 h-4 text-muted-foreground" />
                            </div>
                            <div className="text-sm text-muted-foreground">
                              No tags found matching "{tagSearchTerm}"
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
              <div className="flex items-center space-x-2">
                <Button variant="outline" size="sm" className="cursor-pointer">
                  <Plus className="w-4 h-4 mr-2" />
                  Add file
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="cursor-pointer"
                  onClick={() => handleCopyToClipboard(cloneUrls[selectedCloneOption as keyof typeof cloneUrls], 'Clone URL')}
                >
                  <Copy className="w-4 h-4 mr-2" />
                  Clone
                </Button>
              </div>
            </div>

            {/* File Browser */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center space-x-2">
                    <File className="w-5 h-5" style={{ color: '#351A55' }} />
                    <span>Files</span>
                    {selectedTag && (
                      <Badge variant="outline" className="text-xs" style={{ borderColor: '#BE266A', color: '#BE266A' }}>
                        {selectedTag}
                      </Badge>
                    )}
                    {selectedBranch !== 'main' && (
                      <Badge variant="outline" className="text-xs" style={{ borderColor: '#3498B3', color: '#3498B3' }}>
                        {selectedBranch}
                      </Badge>
                    )}
                  </CardTitle>
                  <div className="text-sm text-muted-foreground">
                    {fileStructure.length} items {currentPath && `in ${currentPath.split('/').pop()}`}
                  </div>
                </div>

              </CardHeader>
              
              {/* Explorer Style Breadcrumb */}
              <div className="px-6 py-3 bg-muted border-b border-border">
                <div className="flex items-center space-x-2">
                  {currentPath && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        const pathSegments = currentPath.split('/').filter(Boolean);
                        if (pathSegments.length > 1) {
                          const parentPath = pathSegments.slice(0, -1).join('/');
                          setCurrentPath(parentPath);
                        } else {
                          setCurrentPath('');
                        }
                      }}
                      className="h-8 w-8 p-0 hover:bg-accent"
                    >
                      <ArrowLeft className="w-4 h-4" />
                    </Button>
                  )}
                  <FolderOpen className="w-4 h-4 text-muted-foreground" />
                  <div className="flex items-center space-x-1 text-sm">
                    <button
                      onClick={() => setCurrentPath('')}
                      className={`px-2 py-1 rounded transition-colors duration-200 font-medium ${
                        !currentPath
                          ? 'bg-accent text-accent-foreground cursor-default'
                          : 'text-foreground hover:text-foreground hover:bg-accent cursor-pointer'
                      }`}
                    >
                      {repository.name}
                    </button>
                    {currentPath && currentPath.split('/').filter(Boolean).map((folder, index, array) => (
                      <div key={index} className="flex items-center space-x-1">
                        <ChevronRight className="w-3 h-3 text-muted-foreground" />
                        <button
                          onClick={() => {
                            if (index < array.length - 1) {
                              handleBreadcrumbClick(index);
                            }
                          }}
                          className={`px-2 py-1 rounded transition-colors duration-200 ${
                            index === array.length - 1
                              ? 'bg-blue-100 text-blue-800 font-medium cursor-default'
                              : 'hover:bg-accent text-foreground hover:text-foreground font-medium cursor-pointer'
                          }`}
                        >
                          {folder}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              
              <CardContent className="p-0">
                {/* Table Header */}
                <div className="grid grid-cols-12 gap-4 px-6 py-3 bg-muted border-b border-border text-sm font-medium text-muted-foreground">
                  <div className="col-span-3">Name</div>
                  <div className="col-span-2">Last Commit Date</div>
                  <div className="col-span-2">Last Commit</div>
                  <div className="col-span-4">Last Commit Details</div>
                  <div className="col-span-1">Size</div>
                </div>
                {/* Table Body */}
                <div className="divide-y divide-border">
                  {fileStructure.map((file, index) => (
                    <div 
                      key={index} 
                      className="grid grid-cols-12 gap-4 px-6 py-3 hover:bg-muted cursor-pointer items-center group transition-colors duration-200"
                      onClick={() => {
                        if (file.type === 'folder') {
                          handleFolderClick(file.name);
                        } else {
                          const filePath = currentPath ? `${currentPath}/${file.name}` : file.name;
                          onNavigateToFile(filePath);
                        }
                      }}
                    >
                      {/* Name */}
                      <div className="col-span-3 flex items-center space-x-3">
                        {getFileIcon(file.type)}
                        <span className="font-medium text-foreground truncate group-hover:text-blue-600 transition-colors duration-200">
                          {file.name}
                        </span>
                        {file.type === 'folder' && (
                          <ChevronRight className="w-4 h-4 text-muted-foregroup-hover:text-blue-500 transition-colors duration-200" />
                        )}
                      </div>
                      
                      {/* Last Commit Date */}
                      <div className="col-span-2 text-sm text-muted-foreground">
                        {file.lastCommitDate}
                      </div>
                      
                      {/* Last Commit + Copy */}
                      <div className="col-span-2 flex items-center space-x-2">
                        <span className="text-sm font-mono text-muted-foreground">{file.lastCommitHash}</span>
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="h-6 w-6 p-0 hover:bg-accent opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCopyToClipboard(file.lastCommitHash, 'Commit hash');
                          }}
                        >
                          <Copy className="w-3 h-3" />
                        </Button>
                      </div>
                      
                      {/* Last Commit Details */}
                      <div className="col-span-4">
                        <div className="space-y-1">
                          <p className="text-sm font-medium text-foreground truncate" title={file.lastCommitMessage}>
                            {file.lastCommitMessage}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            by {file.lastCommitAuthor}
                          </p>
                        </div>
                      </div>
                      
                      {/* Size */}
                      <div className="col-span-1 text-sm text-muted-foreground">
                        {file.size}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Latest Commit */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <GitCommit className="w-5 h-5" style={{ color: '#351A55' }} />
                  <span>Latest Commit</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                      <GitCommit className="w-4 h-4 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="font-medium text-foreground">{recentCommits[0].message}</p>
                      <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                        <span>{recentCommits[0].author}</span>
                        <span>{recentCommits[0].time}</span>
                        {recentCommits[0].verified && (
                          <Badge variant="outline" className="text-xs">
                            <Shield className="w-3 h-3 mr-1" />
                            Verified
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="text-sm text-muted-foreground font-mono">{recentCommits[0].hash}</span>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-6 w-6 p-0 hover:bg-accent"
                      onClick={() => handleCopyToClipboard(recentCommits[0].hash, 'Commit hash')}
                    >
                      <Copy className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* README */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <FileText className="w-5 h-5" style={{ color: '#351A55' }} />
                  <span>README.md</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="prose prose-sm max-w-none">
                  <pre className="whitespace-pre-wrap text-sm text-muted-foreground leading-relaxed">
{readmeContent}
                  </pre>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="commits" className="space-y-6 min-h-[600px]">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <GitCommit className="w-5 h-5" style={{ color: '#351A55' }} />
                  <span>Commit History</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {recentCommits.map((commit, index) => (
                  <div key={index} className="flex items-start space-x-4 p-4 bg-muted rounded-lg">
                    <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center">
                      <GitCommit className="w-4 h-4 text-muted-foreground" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-foreground mb-1">{commit.message}</p>
                      <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                        <span className="flex items-center space-x-1">
                          <Users className="w-4 h-4" />
                          <span>{commit.author}</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <Calendar className="w-4 h-4" />
                          <span>{commit.time}</span>
                        </span>
                        {commit.verified && (
                          <Badge variant="outline" className="text-xs">
                            <Shield className="w-3 h-3 mr-1" />
                            Verified
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm text-muted-foreground font-mono">{commit.hash}</span>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="h-6 w-6 p-0 hover:bg-accent"
                        onClick={() => handleCopyToClipboard(commit.hash, 'Commit hash')}
                      >
                        <Copy className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="branches" className="space-y-6 min-h-[600px]">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <GitBranch className="w-5 h-5" style={{ color: '#351A55' }} />
                  <span>Branches</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {branches.map((branch, index) => (
                  <div key={index} className="flex items-center justify-between p-4 bg-muted rounded-lg">
                    <div className="flex items-center space-x-3">
                      <GitBranch className="w-4 h-4 text-muted-foreground" />
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-medium text-foreground">{branch.name}</span>
                          {branch.isDefault && (
                            <Badge variant="outline" className="text-xs">
                              Default
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">Last commit {branch.lastCommit}</p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                      {branch.ahead > 0 && (
                        <span className="text-green-600">{branch.ahead} ahead</span>
                      )}
                      {branch.behind > 0 && (
                        <span className="text-red-600">{branch.behind} behind</span>
                      )}
                      <Button variant="outline" size="sm" className="cursor-pointer">
                        View
                      </Button>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="pullrequests" className="space-y-6 min-h-[600px]">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <GitPullRequest className="w-5 h-5" style={{ color: '#351A55' }} />
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
                      <h4 className="font-medium text-foreground mb-1">{pr.title}</h4>
                      <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                        <span className="flex items-center space-x-1">
                          <Users className="w-4 h-4" />
                          <span>{pr.author}</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <Calendar className="w-4 h-4" />
                          <span>{pr.createdAt}</span>
                        </span>
                      </div>
                      <div className="flex items-center space-x-4 mt-2 text-xs text-muted-foreground">
                        <span>{pr.reviews} reviews</span>
                        <span>{pr.commits} commits</span>
                      </div>
                    </div>
                    <Button variant="outline" size="sm" className="cursor-pointer">
                      View
                    </Button>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="insights" className="space-y-6 min-h-[600px]">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <Activity className="w-5 h-5" style={{ color: '#351A55' }} />
                    <span>Repository Activity</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Commits this month</span>
                      <span className="font-semibold text-foreground">47</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Contributors</span>
                      <span className="font-semibold text-foreground">{contributors.length}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Issues closed</span>
                      <span className="font-semibold text-foreground">12</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">PRs merged</span>
                      <span className="font-semibold text-foreground">23</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <Zap className="w-5 h-5" style={{ color: '#351A55' }} />
                    <span>Performance Metrics</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Build success rate</span>
                      <span className="font-semibold text-green-600">98.2%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Average build time</span>
                      <span className="font-semibold">3m 24s</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Test coverage</span>
                      <span className="font-semibold">87.3%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Code quality score</span>
                      <span className="font-semibold">A+</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <BarChart3 className="w-5 h-5" style={{ color: '#351A55' }} />
                    <span>Top Contributors</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {contributors.slice(0, 4).map((contributor, index) => (
                      <div key={index} className="flex items-center space-x-3">
                        <Avatar className="w-6 h-6">
                          <AvatarFallback className="text-xs">{contributor.avatar}</AvatarFallback>
                        </Avatar>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {contributor.name}
                          </p>
                          <p className="text-xs text-gray-500">{contributor.commits} commits</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Language Statistics */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Code className="w-5 h-5" style={{ color: '#351A55' }} />
                  <span>Language Statistics</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: getLanguageColor(repository.language) }}></div>
                      <span className="text-sm font-medium">{repository.language}</span>
                    </div>
                    <span className="text-sm text-gray-500">78.5%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div className="h-2 rounded-full" style={{ backgroundColor: getLanguageColor(repository.language), width: '78.5%' }}></div>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                      <span>JavaScript</span>
                      <span className="text-gray-500">12.3%</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                      <span>CSS</span>
                      <span className="text-gray-500">6.8%</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 rounded-full bg-red-500"></div>
                      <span>HTML</span>
                      <span className="text-gray-500">2.4%</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>

    </div>
  );
}