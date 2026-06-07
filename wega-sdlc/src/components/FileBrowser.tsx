import { useState } from 'react';
import { 
  Search, 
  FolderOpen,
  Home,
  File,
  FileText,
  Download,
  Copy,
  ArrowLeft,
  ChevronRight,
  Filter,
  MoreVertical,
  Eye,
  Edit,
  Trash2,
  GitCommit,
  Clock,
  User,
  Code,
  Plus,
  FolderPlus
} from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from './ui/breadcrumb';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/dropdown-menu';

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

interface FileItem {
  name: string;
  type: 'file' | 'folder';
  size: string;
  modified: string;
  lastCommitDate: string;
  lastCommitHash: string;
  lastCommitMessage: string;
  lastCommitAuthor: string;
  path: string;
}

interface FileBrowserProps {
  repository: Repository;
  folderPath: string;
  onBack: () => void;
  onBackToRepo: () => void;
  onNavigateToFolder: (folderPath: string) => void;
  onNavigateToFile: (filePath: string) => void;
  isDarkMode?: boolean;
  onToggleTheme?: () => void;
}

export function FileBrowser({ 
  repository, 
  folderPath, 
  onBack, 
  onBackToRepo, 
  onNavigateToFolder,
  onNavigateToFile,
  isDarkMode,
  onToggleTheme
}: FileBrowserProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [copySuccess, setCopySuccess] = useState('');
  const [showCreateFile, setShowCreateFile] = useState(false);
  const [newFileName, setNewFileName] = useState('');

  const handleCopyToClipboard = async (text: string, type: string = 'hash') => {
    try {
      await navigator.clipboard.writeText(text);
      setCopySuccess(`${type} copied!`);
      setTimeout(() => setCopySuccess(''), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleCloneRepository = async () => {
    const cloneUrl = `https://github.com/wipro-digital/${repository.name}.git`;
    try {
      await navigator.clipboard.writeText(cloneUrl);
      setCopySuccess('Clone URL copied to clipboard!');
      setTimeout(() => setCopySuccess(''), 3000);
    } catch (err) {
      console.error('Failed to copy clone URL:', err);
    }
  };

  // Sample file structure for the folder
  const getFilesForPath = (path: string) => {
    if (!path || path === '') {
      // Root directory
      return [
        {
          name: 'src',
          type: 'folder' as const,
          size: '-',
          modified: '2 days ago',
          lastCommitDate: 'Dec 15, 2024',
          lastCommitHash: 'a7b3c9d',
          lastCommitMessage: 'feat: add new components structure',
          lastCommitAuthor: 'Vishnuprasad Jahagirdar',
          path: 'src'
        },
        {
          name: 'public',
          type: 'folder' as const,
          size: '-',
          modified: '1 week ago',
          lastCommitDate: 'Dec 8, 2024',
          lastCommitHash: 'b8c4d1e',
          lastCommitMessage: 'feat: update public assets',
          lastCommitAuthor: 'Sarah Chen',
          path: 'public'
        },
        {
          name: 'package.json',
          type: 'file' as const,
          size: '2.1 KB',
          modified: '5 days ago',
          lastCommitDate: 'Dec 12, 2024',
          lastCommitHash: 'd1e6f3a',
          lastCommitMessage: 'deps: update dependencies',
          lastCommitAuthor: 'Priya Sharma',
          path: 'package.json'
        },
        {
          name: 'README.md',
          type: 'file' as const,
          size: '4.3 KB',
          modified: '1 day ago',
          lastCommitDate: 'Dec 16, 2024',
          lastCommitHash: 'e2f7a4b',
          lastCommitMessage: 'docs: improve installation instructions',
          lastCommitAuthor: 'David Kim',
          path: 'README.md'
        }
      ];
    } else if (path === 'src') {
      return [
        {
          name: 'components',
          type: 'folder' as const,
          size: '-',
          modified: '1 day ago',
          lastCommitDate: 'Dec 16, 2024',
          lastCommitHash: 'e2f7a4b',
          lastCommitMessage: 'feat: add new UI components',
          lastCommitAuthor: 'Sarah Chen',
          path: 'src/components'
        },
        {
          name: 'utils',
          type: 'folder' as const,
          size: '-',
          modified: '3 days ago',
          lastCommitDate: 'Dec 14, 2024',
          lastCommitHash: 'c1d4e7f',
          lastCommitMessage: 'refactor: utility functions',
          lastCommitAuthor: 'Michael Rodriguez',
          path: 'src/utils'
        },
        {
          name: 'App.tsx',
          type: 'file' as const,
          size: '3.4 KB',
          modified: '1 day ago',
          lastCommitDate: 'Dec 16, 2024',
          lastCommitHash: 'e2f7a4b',
          lastCommitMessage: 'feat: main application component',
          lastCommitAuthor: 'Sarah Chen',
          path: 'src/App.tsx'
        },
        {
          name: 'index.tsx',
          type: 'file' as const,
          size: '1.2 KB',
          modified: '2 days ago',
          lastCommitDate: 'Dec 15, 2024',
          lastCommitHash: 'a7b3c9d',
          lastCommitMessage: 'feat: main entry point setup',
          lastCommitAuthor: 'Vishnuprasad Jahagirdar',
          path: 'src/index.tsx'
        }
      ];
    } else {
      return [
        {
          name: 'example.md',
          type: 'file' as const,
          size: '156 B',
          modified: '1 month ago',
          lastCommitDate: 'Nov 15, 2024',
          lastCommitHash: 'x1y2z3a',
          lastCommitMessage: 'docs: placeholder file',
          lastCommitAuthor: 'System',
          path: `${path}/example.md`
        }
      ];
    }
  };

  const files = getFilesForPath(folderPath);

  const filteredFiles = files.filter(file =>
    file.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const sortedFiles = [...filteredFiles].sort((a, b) => {
    if (sortBy === 'name') {
      return a.name.localeCompare(b.name);
    } else if (sortBy === 'modified') {
      return new Date(b.modified).getTime() - new Date(a.modified).getTime();
    } else if (sortBy === 'size') {
      return a.size.localeCompare(b.size);
    }
    return 0;
  });

  const getFileIcon = (type: string, fileName: string) => {
    if (type === 'folder') {
      return <FolderOpen className="w-5 h-5 text-blue-500 dark:brightness-150" />;
    } else {
      return <FileText className="w-5 h-5 text-muted-foreground dark:brightness-150" />;
    }
  };

  const handleItemClick = (file: FileItem) => {
    if (file.type === 'folder') {
      onNavigateToFolder(file.path);
    } else {
      onNavigateToFile(file.path);
    }
  };

  const pathSegments = folderPath ? folderPath.split('/') : [];

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
                  {repository.name}
                </BreadcrumbLink>
              </BreadcrumbItem>
              {pathSegments.map((segment, index) => (
                <div key={index} className="flex items-center">
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    {index === pathSegments.length - 1 ? (
                      <BreadcrumbPage>{segment}</BreadcrumbPage>
                    ) : (
                      <BreadcrumbLink 
                        href="#" 
                        onClick={(e) => {
                          e.preventDefault();
                          const newPath = pathSegments.slice(0, index + 1).join('/');
                          onNavigateToFolder(newPath);
                        }}
                        className="cursor-pointer"
                      >
                        {segment}
                      </BreadcrumbLink>
                    )}
                  </BreadcrumbItem>
                </div>
              ))}
            </BreadcrumbList>
          </Breadcrumb>
        </div>
      </div>

      {/* Page Header */}
      <div className="bg-card border-b border-border px-6 py-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-foreground">File Browser</h1>
              <p className="text-muted-foreground mt-1">
                Browse files in {repository.name}{folderPath ? ` / ${folderPath}` : ''}
              </p>
            </div>
            <div className="flex items-center space-x-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground dark:brightness-150 w-4 h-4" />
                <Input
                  placeholder="Search files..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 w-80 border border-border dark:border-gray-600"
                />
              </div>
              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="name">Name</SelectItem>
                  <SelectItem value="modified">Modified</SelectItem>
                  <SelectItem value="size">Size</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline">
                <Plus className="w-4 h-4 mr-2 dark:brightness-150" />
                New File
              </Button>
              <Button variant="outline">
                <FolderPlus className="w-4 h-4 mr-2 dark:brightness-150" />
                New Folder
              </Button>
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
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Code className="w-5 h-5 dark:brightness-200" style={{ color: '#351A55' }} />
              <span>Files ({sortedFiles.length})</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {/* Go up directory if not at root */}
              {folderPath && (
                <div 
                  className="flex items-center space-x-3 p-3 rounded-lg hover:bg-muted cursor-pointer transition-colors"
                  onClick={() => {
                    const parentPath = pathSegments.slice(0, -1).join('/');
                    onNavigateToFolder(parentPath);
                  }}
                >
                  <ArrowLeft className="w-5 h-5 text-muted-foreground dark:brightness-150" />
                  <span className="text-muted-foreground">.. (parent directory)</span>
                </div>
              )}

              {/* File listing */}
              {sortedFiles.map((file, index) => (
                <div 
                  key={index}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-muted cursor-pointer transition-colors group"
                  onClick={() => handleItemClick(file)}
                >
                  <div className="flex items-center space-x-3 flex-1 min-w-0">
                    {getFileIcon(file.type, file.name)}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <span className="text-card-foreground truncate">{file.name}</span>
                        {file.type === 'folder' && (
                          <ChevronRight className="w-4 h-4 text-muted-foreground dark:brightness-150" />
                        )}
                      </div>
                      <div className="flex items-center space-x-4 text-xs text-muted-foreground mt-1">
                        <span>{file.size}</span>
                        <span className="flex items-center space-x-1">
                          <Clock className="w-3 h-3 dark:brightness-150" />
                          <span>{file.modified}</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <User className="w-3 h-3 dark:brightness-150" />
                          <span>{file.lastCommitAuthor}</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button 
                      variant="ghost" 
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCopyToClipboard(file.lastCommitHash, 'Commit hash');
                      }}
                    >
                      <Copy className="w-4 h-4 dark:brightness-150" />
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" onClick={(e) => e.stopPropagation()}>
                          <MoreVertical className="w-4 h-4 dark:brightness-150" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent>
                        <DropdownMenuItem>
                          <Eye className="w-4 h-4 mr-2 dark:brightness-150" />
                          View
                        </DropdownMenuItem>
                        <DropdownMenuItem>
                          <Edit className="w-4 h-4 mr-2 dark:brightness-150" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem>
                          <Download className="w-4 h-4 mr-2 dark:brightness-150" />
                          Download
                        </DropdownMenuItem>
                        <DropdownMenuItem className="text-destructive">
                          <Trash2 className="w-4 h-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>

                  <div className="text-xs text-muted-foreground ml-4 hidden lg:block">
                    <div className="flex items-center space-x-1">
                      <GitCommit className="w-3 h-3 dark:brightness-150" />
                      <span className="font-mono">{file.lastCommitHash}</span>
                    </div>
                    <div className="truncate max-w-xs" title={file.lastCommitMessage}>
                      {file.lastCommitMessage}
                    </div>
                  </div>
                </div>
              ))}

              {sortedFiles.length === 0 && (
                <div className="text-center py-12 text-muted-foreground">
                  <FolderOpen className="w-12 h-12 mx-auto mb-4 dark:brightness-150" />
                  <p>No files found</p>
                  {searchQuery && <p className="text-sm">Try adjusting your search terms</p>}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </main>

    </div>
  );
}