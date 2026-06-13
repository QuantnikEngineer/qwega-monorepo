import { useState, useEffect } from 'react';
import { 
  ArrowLeft, 
  Edit3, 
  Save, 
  X, 
  Download, 
  Copy, 
  Eye, 
  FileText, 
  Calendar, 
  User, 
  HardDrive, 
  Clock, 
  GitCommit, 
  Star, 
  Share2,
  MoreVertical,
  Code,
  Maximize2,
  ZoomIn,
  ZoomOut,
  WrapText,
  Monitor,
  Shield,
  Home
} from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { Textarea } from './ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from './ui/breadcrumb';

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

interface FileViewerProps {
  repository: Repository;
  filePath: string;
  onBack: () => void;
  onBackToRepo: () => void;
  isDarkMode?: boolean;
  onToggleTheme?: () => void;
}

export function FileViewer({ repository, filePath, onBack, onBackToRepo, isDarkMode, onToggleTheme }: FileViewerProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [fileContent, setFileContent] = useState('');
  const [originalContent, setOriginalContent] = useState('');
  const [copySuccess, setCopySuccess] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fontSize, setFontSize] = useState(14);
  const [wordWrap, setWordWrap] = useState(true);
  const [scrollTop, setScrollTop] = useState(0);
  const [currentLine, setCurrentLine] = useState(1);
  const [activeTab, setActiveTab] = useState('contents');

  // Get file extension and determine language
  const getFileExtension = (filename: string) => {
    return filename.split('.').pop()?.toLowerCase() || '';
  };

  const getLanguageFromExtension = (ext: string) => {
    const languageMap: { [key: string]: string } = {
      'js': 'JavaScript',
      'jsx': 'JavaScript JSX',
      'ts': 'TypeScript',
      'tsx': 'TypeScript JSX',
      'py': 'Python',
      'java': 'Java',
      'cpp': 'C++',
      'c': 'C',
      'cs': 'C#',
      'php': 'PHP',
      'rb': 'Ruby',
      'go': 'Go',
      'rs': 'Rust',
      'swift': 'Swift',
      'kt': 'Kotlin',
      'html': 'HTML',
      'css': 'CSS',
      'scss': 'SCSS',
      'less': 'LESS',
      'sql': 'SQL',
      'json': 'JSON',
      'xml': 'XML',
      'yaml': 'YAML',
      'yml': 'YAML',
      'md': 'Markdown',
      'txt': 'Text',
      'sh': 'Shell',
      'bash': 'Bash'
    };
    return languageMap[ext] || 'Text';
  };

  const fileName = filePath.split('/').pop() || '';
  const fileExtension = getFileExtension(fileName);
  const language = getLanguageFromExtension(fileExtension);

  // Mock file content based on file type
  useEffect(() => {
    let content = '';
    
    if (fileName === 'README.md') {
      content = `# ${repository.name}

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
   git clone https://github.com/wipro/${repository.name}.git
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
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.`;
    } else if (fileName === 'package.json') {
      content = `{
  "name": "${repository.name.toLowerCase()}",
  "version": "2.1.0",
  "description": "${repository.description}",
  "main": "index.js",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "jest",
    "test:watch": "jest --watch",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "next": "^14.0.0",
    "typescript": "^5.0.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0"
  },
  "devDependencies": {
    "eslint": "^8.0.0",
    "eslint-config-next": "^14.0.0",
    "jest": "^29.0.0",
    "@types/jest": "^29.0.0"
  },
  "keywords": [
    "react",
    "nextjs",
    "typescript",
    "enterprise"
  ],
  "author": "Wipro Digital",
  "license": "MIT"
}`;
    } else if (fileName.endsWith('.tsx') || fileName.endsWith('.ts')) {
      content = `import React from 'react';
import { useState, useEffect } from 'react';

interface ${fileName.replace(/\.[^/.]+$/, "")}Props {
  title: string;
  description?: string;
  onAction?: () => void;
}

export const ${fileName.replace(/\.[^/.]+$/, "")}: React.FC<${fileName.replace(/\.[^/.]+$/, "")}Props> = ({
  title,
  description,
  onAction
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [data, setData] = useState(null);

  useEffect(() => {
    // Initialize component
    setIsLoading(true);
    
    // Simulate data loading
    setTimeout(() => {
      setData({ loaded: true });
      setIsLoading(false);
    }, 1000);
  }, []);

  const handleClick = () => {
    if (onAction) {
      onAction();
    }
  };

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="component-container">
      <h1>{title}</h1>
      {description && <p>{description}</p>}
      <button onClick={handleClick}>
        Execute Action
      </button>
    </div>
  );
};

export default ${fileName.replace(/\.[^/.]+$/, "")};`;
    } else {
      content = `// ${fileName}
// This is a sample file for demonstration purposes

/**
 * Sample ${language} file
 * Repository: ${repository.name}
 * Project: ${repository.project}
 */

// File contents would go here
console.log('Hello from ${fileName}');

// Example function
function sampleFunction() {
  return 'This is a sample ${language} file';
}

export default sampleFunction;`;
    }

    setFileContent(content);
    setOriginalContent(content);
  }, [fileName, repository]);

  const handleCopyToClipboard = async (text: string, type: string = 'content') => {
    try {
      await navigator.clipboard.writeText(text);
      setCopySuccess(`${type} copied!`);
      setTimeout(() => setCopySuccess(''), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleSave = () => {
    setOriginalContent(fileContent);
    setIsEditing(false);
    setCopySuccess('File saved successfully!');
    setTimeout(() => setCopySuccess(''), 2000);
  };

  const handleCancel = () => {
    setFileContent(originalContent);
    setIsEditing(false);
  };

  const adjustFontSize = (delta: number) => {
    const newSize = Math.max(10, Math.min(24, fontSize + delta));
    setFontSize(newSize);
  };

  const getLineCount = () => {
    return fileContent.split('\n').length;
  };

  const pathSegments = filePath.split('/').filter(Boolean);

  // Mock file metadata
  const fileMetadata = {
    size: '3.2 KB',
    lines: getLineCount(),
    lastModified: '2 hours ago',
    lastCommit: {
      hash: 'a7b3c9d',
      message: `feat: update ${fileName}`,
      author: 'Vishnuprasad Jahagirdar',
      date: 'Dec 17, 2024',
      verified: true
    }
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
                      <BreadcrumbLink href="#" className="cursor-pointer">
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

      {/* Success Notification */}
      {copySuccess && (
        <div className="fixed top-20 right-6 bg-green-500 text-white px-4 py-2 rounded-md shadow-lg z-50 transition-all duration-300">
          {copySuccess}
        </div>
      )}

      {/* File Header */}
      <div className="bg-card border-b border-border px-6 py-4">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <FileText className="w-6 h-6 text-blue-500 dark:brightness-150" />
              <div>
                <h1 className="text-foreground">{fileName}</h1>
                <div className="flex items-center space-x-4 text-sm text-muted-foreground mt-1">
                  <span>{fileMetadata.size}</span>
                  <span>{fileMetadata.lines} lines</span>
                  <Badge variant="outline" className="dark:brightness-150">
                    {language}
                  </Badge>
                </div>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              {!isEditing ? (
                <>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => adjustFontSize(-2)}
                        >
                          <ZoomOut className="w-4 h-4 dark:brightness-150" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Decrease font size</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  
                  <span className="text-sm text-muted-foreground px-2">{fontSize}px</span>
                  
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => adjustFontSize(2)}
                        >
                          <ZoomIn className="w-4 h-4 dark:brightness-150" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Increase font size</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>

                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => setWordWrap(!wordWrap)}
                  >
                    <WrapText className={`w-4 h-4 dark:brightness-150 ${wordWrap ? 'text-blue-500' : ''}`} />
                  </Button>

                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => setIsEditing(true)}
                  >
                    <Edit3 className="w-4 h-4 mr-2 dark:brightness-150" />
                    Edit
                  </Button>

                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => handleCopyToClipboard(fileContent, 'File content')}
                  >
                    <Copy className="w-4 h-4 mr-2 dark:brightness-150" />
                    Copy
                  </Button>

                  <Button 
                    variant="outline" 
                    size="sm"
                  >
                    <Download className="w-4 h-4 mr-2 dark:brightness-150" />
                    Download
                  </Button>

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm">
                        <MoreVertical className="w-4 h-4 dark:brightness-150" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuItem>
                        <Star className="w-4 h-4 mr-2 dark:brightness-150" />
                        Star File
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Share2 className="w-4 h-4 mr-2 dark:brightness-150" />
                        Share
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Eye className="w-4 h-4 mr-2 dark:brightness-150" />
                        View Raw
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </>
              ) : (
                <div className="flex items-center space-x-2">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={handleCancel}
                  >
                    <X className="w-4 h-4 mr-2 dark:brightness-150" />
                    Cancel
                  </Button>
                  <Button 
                    size="sm"
                    onClick={handleSave}
                    className="bg-[#351A55] dark:bg-[#5A3B7D] hover:bg-[#2D1248] dark:hover:bg-[#6B46A3] text-[rgba(255,255,255,1)]"
                  >
                    <Save className="w-4 h-4 mr-2" />
                    Save
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto px-6 py-8 w-full">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList>
            <TabsTrigger value="contents" className="cursor-pointer">
              <Code className="w-4 h-4 mr-2 dark:brightness-150" />
              Contents
            </TabsTrigger>
            <TabsTrigger value="history" className="cursor-pointer">
              <GitCommit className="w-4 h-4 mr-2 dark:brightness-150" />
              History
            </TabsTrigger>
            <TabsTrigger value="blame" className="cursor-pointer">
              <User className="w-4 h-4 mr-2 dark:brightness-150" />
              Blame
            </TabsTrigger>
          </TabsList>

          <TabsContent value="contents" className="space-y-6">
            {/* File Metadata */}
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                    <div className="flex items-center space-x-1">
                      <User className="w-4 h-4 dark:brightness-150" />
                      <span>{fileMetadata.lastCommit.author}</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <GitCommit className="w-4 h-4 dark:brightness-150" />
                      <span 
                        className="font-mono cursor-pointer hover:text-blue-500 dark:hover:brightness-150"
                        onClick={() => handleCopyToClipboard(fileMetadata.lastCommit.hash, 'Commit hash')}
                      >
                        {fileMetadata.lastCommit.hash}
                      </span>
                      {fileMetadata.lastCommit.verified && (
                        <Shield className="w-3 h-3 text-green-500 dark:brightness-150" />
                      )}
                    </div>
                    <div className="flex items-center space-x-1">
                      <Clock className="w-4 h-4 dark:brightness-150" />
                      <span>{fileMetadata.lastModified}</span>
                    </div>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {fileMetadata.lastCommit.message}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* File Content */}
            <Card>
              <CardContent className="p-0">
                {isEditing ? (
                  <Textarea
                    value={fileContent}
                    onChange={(e) => setFileContent(e.target.value)}
                    className="min-h-[600px] border-0 rounded-t-none font-mono resize-none"
                    style={{ fontSize: `${fontSize}px` }}
                  />
                ) : (
                  <div className="relative">
                    <pre 
                      className={`overflow-auto p-6 bg-muted/20 dark:bg-muted/10 font-mono text-sm ${wordWrap ? 'whitespace-pre-wrap' : 'whitespace-pre'}`}
                      style={{ fontSize: `${fontSize}px` }}
                    >
                      <code className="text-card-foreground">{fileContent}</code>
                    </pre>
                    
                    {/* Line numbers overlay for better UX */}
                    <div className="absolute left-0 top-0 bottom-0 w-12 bg-muted/40 dark:bg-muted/20 border-r border-border p-6 text-xs text-muted-foreground font-mono select-none">
                      {Array.from({ length: getLineCount() }, (_, i) => (
                        <div key={i + 1} className="leading-5">
                          {i + 1}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="history" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>File History</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {[
                    { hash: 'a7b3c9d', message: `feat: update ${fileName}`, author: 'Vishnuprasad Jahagirdar', date: 'Dec 17, 2024', verified: true },
                    { hash: 'e2f5a8b', message: `refactor: improve ${fileName} structure`, author: 'Sarah Chen', date: 'Dec 15, 2024', verified: true },
                    { hash: 'c1d4e7f', message: `fix: resolve issues in ${fileName}`, author: 'Michael Rodriguez', date: 'Dec 12, 2024', verified: false },
                  ].map((commit, index) => (
                    <div key={index} className="flex items-center justify-between p-4 rounded-lg border border-border">
                      <div className="flex items-center space-x-3">
                        <Avatar className="w-8 h-8">
                          <AvatarFallback>{commit.author.split(' ').map(n => n[0]).join('')}</AvatarFallback>
                        </Avatar>
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="font-medium text-card-foreground">{commit.message}</span>
                            {commit.verified && (
                              <Shield className="w-4 h-4 text-green-500 dark:brightness-150" />
                            )}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {commit.author} • {commit.date}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span 
                          className="font-mono text-sm text-muted-foreground cursor-pointer hover:text-blue-500 dark:hover:brightness-150"
                          onClick={() => handleCopyToClipboard(commit.hash, 'Commit hash')}
                        >
                          {commit.hash}
                        </span>
                        <Button variant="outline" size="sm">
                          <Eye className="w-4 h-4 dark:brightness-150" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="blame" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>File Blame</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-muted-foreground mb-4">
                  Shows who last modified each line of the file
                </div>
                <div className="bg-muted/20 dark:bg-muted/10 rounded-lg p-4 font-mono text-sm">
                  {fileContent.split('\n').slice(0, 20).map((line, index) => (
                    <div key={index} className="flex items-start space-x-4 py-1">
                      <div className="w-20 text-muted-foreground">
                        {index + 1}
                      </div>
                      <div className="w-24 text-muted-foreground">
                        a7b3c9d
                      </div>
                      <div className="w-32 text-muted-foreground">
                        Vishnuprasad
                      </div>
                      <div className="flex-1 text-card-foreground">
                        {line || ' '}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>

    </div>
  );
}