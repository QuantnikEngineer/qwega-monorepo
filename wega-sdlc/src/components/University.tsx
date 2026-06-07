import { ArrowLeft, GraduationCap, BookOpen, Trophy, Users, Star, Clock, Code, Sparkles, Maximize2, GitBranch, TestTube, BarChart3, RefreshCw, FileText, Shield, Zap, Database, Play, Award, CheckCircle, ArrowRight } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { RolesCapabilitiesMatrix } from './platform/RolesCapabilitiesMatrix';

interface UniversityProps {
  onBack: () => void;
  isDarkMode: boolean;
}

export function University({ onBack, isDarkMode }: UniversityProps) {
  // AI Fundamentals Courses
  const aiFundamentalsCourses = [
    {
      title: 'Introduction to Artificial Intelligence',
      description: 'Learn the foundational concepts of AI, machine learning, and neural networks.',
      level: 'Beginner',
      duration: '6 hours',
      modules: 10,
      icon: Sparkles,
      color: '#3498B3',
      status: 'Available',
      topics: ['AI History', 'Machine Learning Basics', 'Neural Networks', 'AI Ethics', 'Use Cases']
    },
    {
      title: 'Generative AI & Large Language Models',
      description: 'Understand how LLMs work, their capabilities, and practical applications in software engineering.',
      level: 'Intermediate',
      duration: '8 hours',
      modules: 12,
      icon: Sparkles,
      color: '#355493',
      status: 'Available',
      topics: ['Transformer Models', 'Prompt Engineering', 'Fine-tuning', 'RAG Systems', 'LLM APIs']
    },
    {
      title: 'AI Agents & Autonomous Systems',
      description: 'Deep dive into AI agents, multi-agent systems, and autonomous decision-making.',
      level: 'Advanced',
      duration: '10 hours',
      modules: 15,
      icon: Users,
      color: '#746FA7',
      status: 'Available',
      topics: ['Agent Architecture', 'Multi-Agent Orchestration', 'Tool Use', 'Memory Systems', 'Evaluation']
    },
    {
      title: 'Prompt Engineering Masterclass',
      description: 'Master the art and science of crafting effective prompts for AI systems.',
      level: 'Intermediate',
      duration: '5 hours',
      modules: 8,
      icon: FileText,
      color: '#BE266A',
      status: 'Available',
      topics: ['Prompt Patterns', 'Chain-of-Thought', 'Few-Shot Learning', 'System Prompts', 'Optimization']
    }
  ];

  // WEGA Platform Courses
  const wegaPlatformCourses = [
    {
      title: 'WEGA Platform Fundamentals',
      description: 'Master the core concepts and features of the WEGA enterprise platform.',
      level: 'Beginner',
      duration: '4 hours',
      modules: 8,
      icon: GraduationCap,
      color: '#3498B3',
      status: 'Available',
      topics: ['Platform Overview', 'Architecture', 'Agent Ecosystem', 'Orchestration', 'Best Practices']
    },
    {
      title: 'AI Agent Orchestration with WEGA',
      description: 'Learn to configure, deploy, and optimize AI agents across the entire SDLC.',
      level: 'Intermediate',
      duration: '6 hours',
      modules: 12,
      icon: Users,
      color: '#355493',
      status: 'Available',
      topics: ['Agent Selection', 'Workflow Design', 'Integration Patterns', 'Monitoring', 'Optimization']
    },
    {
      title: 'Enterprise Integration & Deployment',
      description: 'Integrate WEGA into your existing enterprise ecosystem and manage deployments.',
      level: 'Advanced',
      duration: '8 hours',
      modules: 14,
      icon: Database,
      color: '#746FA7',
      status: 'Available',
      topics: ['Enterprise Architecture', 'Security', 'Compliance', 'Scalability', 'Migration Strategies']
    }
  ];

  // Tool-Specific Courses
  const toolSpecificCourses = [
    {
      title: 'GitHub Copilot for Developers',
      description: 'Master GitHub Copilot for accelerated code generation and development workflows.',
      level: 'Beginner',
      duration: '3 hours',
      modules: 6,
      icon: Code,
      color: '#00A4EF',
      status: 'Available',
      topics: ['Setup & Configuration', 'Code Completion', 'Chat Features', 'Best Practices', 'Troubleshooting']
    },
    {
      title: 'Google Gemini AI Development',
      description: 'Build applications using Google Gemini for code generation and multimodal AI.',
      level: 'Intermediate',
      duration: '5 hours',
      modules: 9,
      icon: Sparkles,
      color: '#8E75F0',
      status: 'Available',
      topics: ['Gemini API', 'Multimodal Inputs', 'Code Generation', 'Integration', 'Advanced Features']
    },
    {
      title: 'Cursor AI Editor Mastery',
      description: 'Leverage Cursor AI for intelligent code editing and refactoring.',
      level: 'Beginner',
      duration: '2 hours',
      modules: 5,
      icon: Code,
      color: '#000000',
      status: 'Available',
      topics: ['Editor Setup', 'AI-Assisted Editing', 'Refactoring', 'Debugging', 'Productivity Tips']
    },
    {
      title: 'Windsurf Code Generation',
      description: 'Learn to use Windsurf AI for advanced code generation and debugging.',
      level: 'Intermediate',
      duration: '4 hours',
      modules: 7,
      icon: Code,
      color: '#0EA5E9',
      status: 'Available',
      topics: ['Platform Overview', 'Code Generation', 'Debugging Tools', 'Refactoring', 'Integration']
    },
    {
      title: 'Amazon Q Developer',
      description: 'Build AWS applications faster with Amazon Q AI assistant.',
      level: 'Intermediate',
      duration: '4 hours',
      modules: 8,
      icon: Code,
      color: '#FF9900',
      status: 'Available',
      topics: ['AWS Integration', 'Code Generation', 'Security Scanning', 'Optimization', 'Best Practices']
    },
    {
      title: 'Factory.AI Platform',
      description: 'Master Factory.AI for enterprise-scale AI-driven code generation.',
      level: 'Advanced',
      duration: '6 hours',
      modules: 10,
      icon: Code,
      color: '#351A55',
      status: 'Available',
      topics: ['Platform Architecture', 'Custom Models', 'Enterprise Integration', 'Scaling', 'Governance']
    },
    {
      title: 'Figma AI for Design',
      description: 'Use Figma with AI capabilities for rapid UI/UX design and prototyping.',
      level: 'Beginner',
      duration: '4 hours',
      modules: 8,
      icon: Maximize2,
      color: '#F24E1E',
      status: 'Available',
      topics: ['Figma Basics', 'AI Features', 'Design Systems', 'Prototyping', 'Collaboration']
    },
    {
      title: 'Jira Rovo AI',
      description: 'Leverage Jira Rovo for AI-powered project management and documentation.',
      level: 'Beginner',
      duration: '3 hours',
      modules: 6,
      icon: FileText,
      color: '#0052CC',
      status: 'Available',
      topics: ['Rovo Overview', 'User Story Generation', 'Documentation', 'Decision Making', 'Team Collaboration']
    }
  ];

  // DevOps & Deployment Courses
  const devOpsCourses = [
    {
      title: 'Harness CI/CD Platform',
      description: 'Master modern CI/CD with Harness for automated deployments and releases.',
      level: 'Intermediate',
      duration: '5 hours',
      modules: 10,
      icon: GitBranch,
      color: '#00ADE4',
      status: 'Available',
      topics: ['Platform Setup', 'Pipeline Design', 'Deployment Strategies', 'Monitoring', 'Optimization']
    },
    {
      title: 'GitHub Actions Workflows',
      description: 'Build automated workflows with GitHub Actions for CI/CD and automation.',
      level: 'Beginner',
      duration: '4 hours',
      modules: 8,
      icon: GitBranch,
      color: '#2088FF',
      status: 'Available',
      topics: ['Workflow Basics', 'Actions Marketplace', 'Custom Actions', 'Security', 'Best Practices']
    },
    {
      title: 'GitLab CI/CD Advanced',
      description: 'Implement comprehensive DevOps pipelines with GitLab.',
      level: 'Intermediate',
      duration: '6 hours',
      modules: 11,
      icon: GitBranch,
      color: '#FC6D26',
      status: 'Available',
      topics: ['Pipeline Configuration', 'Auto DevOps', 'Security Scanning', 'Deployment', 'Monitoring']
    },
    {
      title: 'Datadog Observability Platform',
      description: 'Monitor, troubleshoot, and optimize applications with Datadog.',
      level: 'Intermediate',
      duration: '7 hours',
      modules: 12,
      icon: BarChart3,
      color: '#632CA6',
      status: 'Available',
      topics: ['Platform Setup', 'Metrics & Logs', 'APM', 'Anomaly Detection', 'Self-Healing']
    },
    {
      title: 'Dynatrace AI Operations',
      description: 'Leverage Dynatrace for AI-powered monitoring and self-healing systems.',
      level: 'Advanced',
      duration: '8 hours',
      modules: 13,
      icon: BarChart3,
      color: '#1496FF',
      status: 'Available',
      topics: ['Davis AI Engine', 'Root Cause Analysis', 'Automated Remediation', 'Performance', 'AIOps']
    }
  ];

  // Learning Paths
  const learningPaths = [
    {
      name: 'AI-Powered Developer Track',
      description: 'For engineers looking to leverage AI tools in their daily development workflow',
      courses: 8,
      duration: '35 hours',
      icon: Code,
      color: '#3498B3'
    },
    {
      name: 'WEGA Platform Engineer Track',
      description: 'For platform teams implementing and managing WEGA across the organization',
      courses: 10,
      duration: '45 hours',
      icon: Database,
      color: '#355493'
    },
    {
      name: 'AI Agent Specialist Track',
      description: 'Master AI agents, orchestration, and autonomous systems',
      courses: 6,
      duration: '30 hours',
      icon: Users,
      color: '#746FA7'
    },
    {
      name: 'DevOps with AI Track',
      description: 'Integrate AI into your CI/CD, monitoring, and deployment workflows',
      courses: 7,
      duration: '38 hours',
      icon: GitBranch,
      color: '#BE266A'
    }
  ];

  const renderCourseCard = (course: any, index: number) => {
    const Icon = course.icon;
    return (
      <Card
        key={index}
        className="p-6 bg-card border border-border hover:border-[#3498B3] transition-all group"
      >
        <div className="flex items-start justify-between mb-4">
          <div
            className="p-3 rounded-lg"
            style={{ backgroundColor: `${course.color}20` }}
          >
            <Icon className="w-6 h-6" style={{ color: course.color }} />
          </div>
          <Badge
            variant="outline"
            className={course.status === 'Available' ? 'bg-green-500/10 text-green-500 border-green-500/30' : 'bg-orange-500/10 text-orange-500 border-orange-500/30'}
          >
            {course.status}
          </Badge>
        </div>
        <h3 className="text-foreground mb-2">{course.title}</h3>
        <p className="text-muted-foreground text-sm mb-4">{course.description}</p>
        
        {/* Topics */}
        {course.topics && (
          <div className="mb-4">
            <div className="flex flex-wrap gap-1">
              {course.topics.slice(0, 3).map((topic: string, i: number) => (
                <Badge key={i} variant="outline" className="text-xs">
                  {topic}
                </Badge>
              ))}
              {course.topics.length > 3 && (
                <Badge variant="outline" className="text-xs">
                  +{course.topics.length - 3} more
                </Badge>
              )}
            </div>
          </div>
        )}

        <div className="flex items-center space-x-4 text-xs text-muted-foreground mb-4">
          <div className="flex items-center">
            <Star className="w-4 h-4 mr-1" />
            {course.level}
          </div>
          <div className="flex items-center">
            <Clock className="w-4 h-4 mr-1" />
            {course.duration}
          </div>
          <div>{course.modules} modules</div>
        </div>
        <Button
          variant="outline"
          className="w-full hover:bg-[#3498B3] hover:text-white hover:border-[#3498B3] group-hover:bg-[#3498B3] group-hover:text-white"
          disabled={course.status === 'Coming Soon'}
        >
          <Play className="w-4 h-4 mr-2" />
          {course.status === 'Available' ? 'Start Course' : 'Coming Soon'}
        </Button>
      </Card>
    );
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Hero Banner Section */}
      <div className="relative h-[400px] w-full overflow-hidden bg-gradient-to-r from-[#351A55] to-[#3498B3] mb-8">
        <div className="absolute inset-0">
          <img 
            src="https://images.unsplash.com/photo-1762330917056-e69b34329ddf?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxvbmxpbmUlMjBsZWFybmluZyUyMHRlY2hub2xvZ3l8ZW58MXx8fHwxNzYzMDU5NTE1fDA&ixlib=rb-4.1.0&q=80&w=1080"
            alt="WEGA University"
            className="w-full h-full object-cover opacity-20"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[#351A55]/80 to-[#3498B3]/80"></div>
        </div>
        <div className="relative max-w-7xl mx-auto px-6 h-full flex flex-col justify-center">
          <Button
            variant="ghost"
            onClick={onBack}
            className="mb-6 text-white hover:text-white hover:bg-white/10 self-start"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Home
          </Button>
          <div className="flex items-center space-x-4 mb-6">
            <div className="p-4 bg-white/10 rounded-2xl backdrop-blur-sm">
              <GraduationCap className="w-12 h-12 text-white" />
            </div>
            <div>
              <h1 className="text-white mb-2">WEGA University</h1>
              <p className="text-white/90 max-w-2xl">
                Transform your career with AI-powered learning. Master cutting-edge tools and techniques.
              </p>
            </div>
          </div>
          <div className="flex gap-4">
            <Button className="bg-white text-[#351A55] hover:bg-white/90">
              <Play className="w-4 h-4 mr-2" />
              Start Learning
            </Button>
            <Button variant="outline" className="border-white text-white hover:bg-white/10">
              View Catalog
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-12">
          <Card className="p-4 bg-card border border-border">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl text-[#3498B3]">12+</div>
                <div className="text-sm text-muted-foreground">Courses</div>
              </div>
              <BookOpen className="w-8 h-8 text-[#3498B3] opacity-50" />
            </div>
          </Card>
          <Card className="p-4 bg-card border border-border">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl text-[#355493]">50+</div>
                <div className="text-sm text-muted-foreground">Hours Content</div>
              </div>
              <Clock className="w-8 h-8 text-[#355493] opacity-50" />
            </div>
          </Card>
          <Card className="p-4 bg-card border border-border">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl text-[#746FA7]">5,000+</div>
                <div className="text-sm text-muted-foreground">Learners</div>
              </div>
              <Users className="w-8 h-8 text-[#746FA7] opacity-50" />
            </div>
          </Card>
          <Card className="p-4 bg-card border border-border">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl text-[#BE266A]">3</div>
                <div className="text-sm text-muted-foreground">Certifications</div>
              </div>
              <Trophy className="w-8 h-8 text-[#BE266A] opacity-50" />
            </div>
          </Card>
        </div>

        {/* Learning Paths */}
        <div className="mb-12">
          <h2 className="text-foreground mb-6">Learning Paths</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {learningPaths.map((path, index) => {
              const PathIcon = path.icon;
              return (
                <Card
                  key={index}
                  className="p-6 bg-card border border-border hover:border-[#3498B3] transition-all cursor-pointer group relative overflow-hidden"
                >
                  <div 
                    className="absolute top-0 right-0 w-32 h-32 opacity-5 group-hover:opacity-10 transition-opacity"
                    style={{ color: path.color }}
                  >
                    <PathIcon className="w-full h-full" />
                  </div>
                  <div className="relative">
                    <div 
                      className="w-12 h-12 rounded-lg flex items-center justify-center mb-4"
                      style={{ backgroundColor: `${path.color}20` }}
                    >
                      <PathIcon className="w-6 h-6" style={{ color: path.color }} />
                    </div>
                    <h3 className="text-foreground mb-2">{path.name}</h3>
                    <p className="text-muted-foreground text-sm mb-4">{path.description}</p>
                    <div className="flex items-center justify-between text-xs text-muted-foreground mb-4">
                      <span>{path.courses} courses</span>
                      <span>{path.duration}</span>
                    </div>
                    <Button variant="outline" className="w-full hover:bg-[#3498B3] hover:text-white hover:border-[#3498B3] group-hover:bg-[#3498B3] group-hover:text-white">
                      Start Path
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>

        {/* Featured Categories with Images */}
        <div className="mb-12">
          <h2 className="text-foreground mb-6">Featured Categories</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            {/* AI & Machine Learning Category */}
            <Card className="overflow-hidden group cursor-pointer hover:shadow-lg transition-shadow">
              <div className="relative h-48 overflow-hidden">
                <ImageWithFallback 
                  src="https://images.unsplash.com/photo-1620712943543-bcc4688e7485?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxhcnRpZmljaWFsJTIwaW50ZWxsaWdlbmNlJTIwZWR1Y2F0aW9ufGVufDF8fHx8MTc2MzExMzQ1OHww&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
                  alt="AI & Machine Learning"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent"></div>
                <div className="absolute bottom-4 left-4 right-4">
                  <Badge className="bg-[#3498B3] text-white mb-2">4 Courses</Badge>
                  <h3 className="text-white">AI Fundamentals & Machine Learning</h3>
                </div>
              </div>
              <div className="p-4">
                <p className="text-muted-foreground text-sm mb-3">
                  Master the foundations of AI, from neural networks to advanced LLMs and prompt engineering.
                </p>
                <Button variant="ghost" className="w-full justify-between text-[#3498B3] hover:text-[#3498B3]">
                  Explore Courses
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </div>
            </Card>

            {/* Development Tools Category */}
            <Card className="overflow-hidden group cursor-pointer hover:shadow-lg transition-shadow">
              <div className="relative h-48 overflow-hidden">
                <ImageWithFallback 
                  src="https://images.unsplash.com/photo-1566915896913-549d796d2166?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjb2RpbmclMjB3b3Jrc3BhY2UlMjBkZXZlbG9wZXJ8ZW58MXx8fHwxNzYzMDQxNzg0fDA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
                  alt="Development Tools"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent"></div>
                <div className="absolute bottom-4 left-4 right-4">
                  <Badge className="bg-[#355493] text-white mb-2">8 Courses</Badge>
                  <h3 className="text-white">AI-Powered Development Tools</h3>
                </div>
              </div>
              <div className="p-4">
                <p className="text-muted-foreground text-sm mb-3">
                  Learn to use cutting-edge AI tools like Copilot, Cursor, Windsurf, and more.
                </p>
                <Button variant="ghost" className="w-full justify-between text-[#355493] hover:text-[#355493]">
                  Explore Courses
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </div>
            </Card>

            {/* DevOps & Infrastructure Category */}
            <Card className="overflow-hidden group cursor-pointer hover:shadow-lg transition-shadow">
              <div className="relative h-48 overflow-hidden">
                <ImageWithFallback 
                  src="https://images.unsplash.com/flagged/photo-1579274216947-86eaa4b00475?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxzZXJ2ZXIlMjB0ZWNobm9sb2d5JTIwZGF0YXxlbnwxfHx8fDE3NjMwNDkwMDl8MA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
                  alt="DevOps & Infrastructure"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent"></div>
                <div className="absolute bottom-4 left-4 right-4">
                  <Badge className="bg-[#746FA7] text-white mb-2">5 Courses</Badge>
                  <h3 className="text-white">DevOps & Cloud Operations</h3>
                </div>
              </div>
              <div className="p-4">
                <p className="text-muted-foreground text-sm mb-3">
                  Master CI/CD pipelines, monitoring, and AI-powered observability platforms.
                </p>
                <Button variant="ghost" className="w-full justify-between text-[#746FA7] hover:text-[#746FA7]">
                  Explore Courses
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </div>
            </Card>

            {/* WEGA Platform Category */}
            <Card className="overflow-hidden group cursor-pointer hover:shadow-lg transition-shadow">
              <div className="relative h-48 overflow-hidden">
                <ImageWithFallback 
                  src="https://images.unsplash.com/photo-1752650735943-d0fbf1edce21?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHx0ZWFtJTIwY29sbGFib3JhdGlvbiUyMHdvcmtzcGFjZXxlbnwxfHx8fDE3NjMwNjIwMjB8MA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
                  alt="WEGA Platform"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent"></div>
                <div className="absolute bottom-4 left-4 right-4">
                  <Badge className="bg-[#BE266A] text-white mb-2">3 Courses</Badge>
                  <h3 className="text-white">WEGA Platform Mastery</h3>
                </div>
              </div>
              <div className="p-4">
                <p className="text-muted-foreground text-sm mb-3">
                  Learn to leverage WEGA for enterprise-scale AI-driven software engineering.
                </p>
                <Button variant="ghost" className="w-full justify-between text-[#BE266A] hover:text-[#BE266A]">
                  Explore Courses
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </div>
            </Card>
          </div>
        </div>

        {/* Platform RBAC Matrix */}
        <div className="mb-12">
          <RolesCapabilitiesMatrix />
        </div>

        {/* Courses */}
        <div>
          <h2 className="text-foreground mb-6">Available Courses</h2>
          <Tabs defaultValue="ai-fundamentals" className="w-full">
            <TabsList className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <TabsTrigger value="ai-fundamentals">AI Fundamentals</TabsTrigger>
              <TabsTrigger value="wega-platform">WEGA Platform</TabsTrigger>
              <TabsTrigger value="tool-specific">Tool-Specific</TabsTrigger>
              <TabsTrigger value="devops">DevOps & Deployment</TabsTrigger>
            </TabsList>
            <TabsContent value="ai-fundamentals">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {aiFundamentalsCourses.map((course, index) => renderCourseCard(course, index))}
              </div>
            </TabsContent>
            <TabsContent value="wega-platform">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {wegaPlatformCourses.map((course, index) => renderCourseCard(course, index))}
              </div>
            </TabsContent>
            <TabsContent value="tool-specific">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {toolSpecificCourses.map((course, index) => renderCourseCard(course, index))}
              </div>
            </TabsContent>
            <TabsContent value="devops">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {devOpsCourses.map((course, index) => renderCourseCard(course, index))}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}