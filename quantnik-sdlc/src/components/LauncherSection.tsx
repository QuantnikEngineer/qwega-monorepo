import { 
  Code, 
  GitBranch, 
  Server, 
  Kanban, 
  Cloud, 
  Eye, 
  Trash2, 
  Activity,
  BarChart3,
  Calendar,
  Shield,
  Users,
  Package,
  DollarSign,
  AlertTriangle,
  Bot,
  Search,
  FileCode,
  BookOpen,
  Zap,
  Laptop,
  Rocket,
  Brain
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';

interface LauncherSectionProps {
  onNavigateToCodeRepo?: () => void;
  onNavigateToPipelines?: () => void;
  isDarkMode?: boolean;
}

export function LauncherSection({ onNavigateToCodeRepo, onNavigateToPipelines, isDarkMode }: LauncherSectionProps) {
  const handleCodeRepoClick = () => {
    if (onNavigateToCodeRepo) {
      onNavigateToCodeRepo();
    }
  };

  const handlePipelinesClick = () => {
    if (onNavigateToPipelines) {
      onNavigateToPipelines();
    }
  };

  const sections = [
    {
      title: "DevEx",
      description: "Developer Experience Tools",
      color: "#351A55",
      icon: Laptop,
      items: [
        { name: "Code Repo", icon: Code, description: "Source code repositories" },
        { name: "Pipelines", icon: GitBranch, description: "CI/CD pipelines" },
        { name: "Infra", icon: Server, description: "Infrastructure tools" },
        { name: "Task Board", icon: Kanban, description: "Project management" }
      ]
    },
    {
      title: "InfraEx",
      description: "Infrastructure Experience",
      color: "#3498B3",
      icon: Server,
      items: [
        { name: "Spin Infrastructure", icon: Cloud, description: "Create new infrastructure" },
        { name: "View Infrastructure", icon: Eye, description: "Monitor infrastructure" },
        { name: "Teardown Infrastructure", icon: Trash2, description: "Remove infrastructure" },
        { name: "Recent Activities", icon: Activity, description: "Infrastructure logs" }
      ]
    },
    {
      title: "Engineering Insights",
      description: "Analytics & Metrics",
      color: "#355493",
      icon: BarChart3,
      items: [
        { name: "Engineering Insights", icon: BarChart3, description: "Development metrics" },
        { name: "Agile and Planning", icon: Calendar, description: "Project planning tools" },
        { name: "Security and Vulnerability", icon: Shield, description: "Security analysis" },
        { name: "Developer Productivity", icon: Users, description: "Team performance" }
      ]
    },
    {
      title: "Release Management",
      description: "Release & Deployment",
      color: "#746FA7",
      icon: Rocket,
      items: [
        { name: "Release Planning", icon: Calendar, description: "Plan releases" },
        { name: "Deployment Pipeline", icon: GitBranch, description: "Manage deployments" },
        { name: "Version Control", icon: Package, description: "Version management" },
        { name: "Release Notes", icon: FileCode, description: "Documentation" }
      ]
    },
    {
      title: "FinOps",
      description: "Financial Operations",
      color: "#BE266A",
      icon: DollarSign,
      items: [
        { name: "Cost Analysis", icon: DollarSign, description: "Analyze costs" },
        { name: "Budget Management", icon: BarChart3, description: "Manage budgets" },
        { name: "Resource Optimization", icon: Zap, description: "Optimize resources" },
        { name: "Financial Reports", icon: FileCode, description: "Generate reports" }
      ]
    },
    {
      title: "SRE",
      description: "Site Reliability Engineering",
      color: "#351A55",
      icon: Shield,
      items: [
        { name: "Monitoring", icon: Activity, description: "System monitoring" },
        { name: "Alerting", icon: AlertTriangle, description: "Alert management" },
        { name: "Incident Response", icon: Shield, description: "Handle incidents" },
        { name: "Performance", icon: BarChart3, description: "Performance metrics" }
      ]
    },
    {
      title: "Assets",
      description: "AI & Knowledge Assets",
      color: "#3498B3",
      icon: Brain,
      items: [
        { name: "AI-360 Build", icon: Bot, description: "AI-powered build tools" },
        { name: "Market Research & Analysis", icon: Search, description: "Market insights" },
        { name: "Story & Code Generation", icon: FileCode, description: "Auto-generate code" },
        { name: "Remediation Tracker", icon: Shield, description: "Track fixes" },
        { name: "Wiki", icon: BookOpen, description: "Knowledge base" },
        { name: "AI Agents", icon: Zap, description: "Intelligent automation" }
      ]
    }
  ];

  return (
    <div className="px-6 py-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <div>
            <h2 className="text-foreground">Platform Launcher</h2>
            <p className="text-muted-foreground mt-1">Access all your development tools and services across the enterprise</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-6">
          {sections.map((section, sectionIndex) => {
            const SectionIcon = section.icon;
            const isAssets = section.title === "Assets";
            return (
              <Card key={sectionIndex} className={`bg-card hover:shadow-lg transition-all duration-200 border border-border hover:border-muted-foreground flex flex-col ${isAssets ? 'col-span-3' : 'min-h-[380px]'}`}>
              <CardHeader className="pb-4 border-b border-border">
                <div className="flex items-center space-x-4">
                  <div 
                    className="w-14 h-14 rounded-xl flex items-center justify-center shadow-sm"
                    style={{ backgroundColor: section.color }}
                  >
                    <SectionIcon className="w-7 h-7 text-white" />
                  </div>
                  <div className="flex-1">
                    <CardTitle className="text-card-foreground">{section.title}</CardTitle>
                    <p className="text-muted-foreground mt-1">{section.description}</p>
                  </div>
                </div>
              </CardHeader>
            <CardContent className="pt-4 flex-1">
              {isAssets ? (
                <div className="grid grid-cols-3 gap-6">
                  <div className="space-y-2">
                    {section.items.slice(0, 2).map((item, itemIndex) => {
                      const Icon = item.icon;
                      return (
                        <Button
                          key={itemIndex}
                          variant="ghost"
                          className="w-full h-auto p-3 flex items-center justify-between hover:bg-muted text-left group rounded-lg transition-colors cursor-default"
                        >
                          <div className="flex items-center space-x-4">
                            <div 
                              className="w-8 h-8 rounded-lg flex items-center justify-center"
                              style={{ backgroundColor: `${section.color}${isDarkMode ? '15' : '40'}` }}
                            >
                              <Icon className="w-4 h-4 dark:brightness-300 dark:saturate-200" style={{ color: section.color }} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-card-foreground truncate">
                                {item.name}
                              </p>
                              <p className="text-muted-foreground mt-0.5 truncate">
                                {item.description}
                              </p>
                            </div>
                          </div>
                          <div className="text-muted-foreground group-hover:text-foreground transition-colors ml-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </div>
                        </Button>
                      );
                    })}
                  </div>
                  <div className="space-y-2">
                    {section.items.slice(2, 4).map((item, itemIndex) => {
                      const Icon = item.icon;
                      return (
                        <Button
                          key={itemIndex + 2}
                          variant="ghost"
                          className="w-full h-auto p-3 flex items-center justify-between hover:bg-muted text-left group rounded-lg transition-colors cursor-default"
                        >
                          <div className="flex items-center space-x-4">
                            <div 
                              className="w-8 h-8 rounded-lg flex items-center justify-center"
                              style={{ backgroundColor: `${section.color}${isDarkMode ? '15' : '40'}` }}
                            >
                              <Icon className="w-4 h-4 dark:brightness-300 dark:saturate-200" style={{ color: section.color }} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-card-foreground truncate">
                                {item.name}
                              </p>
                              <p className="text-muted-foreground mt-0.5 truncate">
                                {item.description}
                              </p>
                            </div>
                          </div>
                          <div className="text-muted-foreground group-hover:text-foreground transition-colors ml-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </div>
                        </Button>
                      );
                    })}
                  </div>
                  <div className="space-y-2">
                    {section.items.slice(4, 6).map((item, itemIndex) => {
                      const Icon = item.icon;
                      return (
                        <Button
                          key={itemIndex + 4}
                          variant="ghost"
                          className="w-full h-auto p-3 flex items-center justify-between hover:bg-muted text-left group rounded-lg transition-colors cursor-default"
                        >
                          <div className="flex items-center space-x-4">
                            <div 
                              className="w-8 h-8 rounded-lg flex items-center justify-center"
                              style={{ backgroundColor: `${section.color}${isDarkMode ? '15' : '40'}` }}
                            >
                              <Icon className="w-4 h-4 dark:brightness-300 dark:saturate-200" style={{ color: section.color }} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-card-foreground truncate">
                                {item.name}
                              </p>
                              <p className="text-muted-foreground mt-0.5 truncate">
                                {item.description}
                              </p>
                            </div>
                          </div>
                          <div className="text-muted-foreground group-hover:text-foreground transition-colors ml-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </div>
                        </Button>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="space-y-2 h-full flex flex-col">
                  {section.items.map((item, itemIndex) => {
                    const Icon = item.icon;
                    const isCodeRepo = section.title === "DevEx" && item.name === "Code Repo";
                    const isPipelines = section.title === "DevEx" && item.name === "Pipelines";
                    const isClickable = isCodeRepo || isPipelines;
                    return (
                      <Button
                        key={itemIndex}
                        variant="ghost"
                        className={`w-full h-auto p-3 flex items-center justify-between hover:bg-muted dark:hover:bg-accent text-left group rounded-lg transition-colors ${isClickable ? 'cursor-pointer' : 'cursor-default'}`}
                        onClick={isCodeRepo ? handleCodeRepoClick : isPipelines ? handlePipelinesClick : undefined}
                      >
                        <div className="flex items-center space-x-4">
                          <div 
                            className="w-8 h-8 rounded-lg flex items-center justify-center dark:brightness-150 dark:saturate-125"
                            style={{ backgroundColor: `${section.color}${isDarkMode ? '15' : '40'}` }}
                          >
                            <Icon className="w-4 h-4 dark:brightness-300 dark:saturate-200" style={{ color: section.color }} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-card-foreground truncate">
                              {item.name}
                            </p>
                            <p className="text-muted-foreground mt-0.5 truncate">
                              {item.description}
                            </p>
                          </div>
                        </div>
                        <div className="text-muted-foreground group-hover:text-foreground transition-colors ml-2">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </div>
                      </Button>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}