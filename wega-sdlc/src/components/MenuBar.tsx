import { useState, useRef, useEffect } from 'react';
import { 
  ChevronDown,
  // Design Icons
  Palette,
  Trello,
  FileText,
  TrendingUp,
  BookOpen,
  // DevEX Icons
  Monitor,
  UserPlus,
  Code,
  Settings,
  GitBranch,
  BookMarked,
  BarChart3,
  UserCheck,
  // TestX Icons
  TestTube,
  FileCode,
  Database,
  Package,
  // InfraX Icons
  Cloud,
  Layers,
  DollarSign,
  Shield,
  Lock,
  // Assets Icons
  Box,
  Bot,
  Zap,
  // AIRE Icons
  AlertTriangle,
  Search,
  Telescope,  
  Activity,
  Wrench,
  Crown,
  // Release Management Icons
  Calendar,
  CheckCircle,
  // Security Icons
  ShieldAlert,
  AlertOctagon,
  // Execute Icons
  Play
} from 'lucide-react';
import { Button } from './ui/button';
import { useAbility } from '../auth/abilities';

interface MenuBarProps {
  onNavigateToCodeRepo?: () => void;
  onNavigateToPipelines?: () => void;
  onNavigateToExecute?: () => void;
  onNavigateToMarketResearch?: () => void;
  isDarkMode?: boolean;
}

interface MenuItem {
  name: string;
  icon: any;
  description: string;
  onClick?: () => void;
  url?: string;
  disabled?: boolean;
  hidden?: boolean;
}

interface MenuSection {
  title: string;
  color: string;
  icon: any;
  items: MenuItem[];
}

export function MenuBar({ onNavigateToCodeRepo, onNavigateToPipelines, onNavigateToExecute, onNavigateToMarketResearch, isDarkMode }: MenuBarProps) {
  const [activeDropdown, setActiveDropdown] = useState<number | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const ability = useAbility();
  const canExecute = ability.can('execute', 'sdlc');

  const menuSections: MenuSection[] = [
    {
      title: "Design",
      color: "#746FA7",
      icon: Palette,
      items: [
        { name: "Market Research Agent", icon: TrendingUp, description: "AI-powered market research and analysis", onClick: onNavigateToMarketResearch, hidden: !canExecute },
        { name: "Requirement Document", icon: BookOpen, description: "Requirements documentation", disabled: true },
        { name: "User Story", icon: FileText, description: "User story creation and management", url: "http://34.134.112.33/assets?q=copilot" },
        { name: "Jira / Azure DevOps", icon: Trello, description: "Project management and issue tracking", url: "https://dev.azure.com/WiproPracticeWork/WEGA2.0/_backlogs/backlog/WEGA2.0%20Team/Epics" },
        { name: "User Experience Design", icon: Palette, description: "UX/UI design tools and templates", disabled: true }
      ]
    },
    {
      title: "DevEX",
      color: "#351A55",
      icon: Monitor,
      items: [
        { name: "Onboarding", icon: UserPlus, description: "Developer onboarding process", disabled: true },
        { name: "Workspace", icon: Monitor, description: "Development environment setup", url: "https://remotedesktop.google.com/access/session/af517606-27cf-6885-8828-25a65c984fbb" },
        { name: "Code Repository", icon: Code, description: "Source code repositories", url: "https://app.harness.io/ng/account/2KolbecvR0aAcgQ5uXBObA/module/code/orgs/WiproPOC/projects/Harness_POC/repos/BuildIQ" },
        { name: "Environment", icon: Settings, description: "Environment configuration", disabled: true },
        { name: "My Pipelines", icon: GitBranch, description: "Personal CI/CD pipelines", url: "https://app.harness.io/ng/account/2KolbecvR0aAcgQ5uXBObA/module/ci/orgs/WiproPOC/projects/Harness_POC/pipelines" },
        { name: "Wiki", icon: BookMarked, description: "Developer documentation", url: "https://dev.azure.com/WiproPracticeWork/WEGA2.0/_wiki/wikis/WEGA%20wiki/1/Developer's-Platform" },
        { name: "Insights", icon: BarChart3, description: "Development analytics", url: "https://app.harness.io/ng/account/2KolbecvR0aAcgQ5uXBObA/module/sei/orgs/WiproPOC/projects/Harness_POC/dashboards/4?OU=3&workspace_id=2&range=last_30_days" },
        { name: "Assignment", icon: UserCheck, description: "Task and project assignments", disabled: true }
      ]
    },
    {
      title: "TestX",
      color: "#3498B3",
      icon: TestTube,
      items: [
        { name: "Pipeline", icon: GitBranch, description: "Test automation pipelines", disabled: true },
        { name: "Test Case Generation", icon: FileCode, description: "Automated test case creation", disabled: true },
        { name: "Test Data Generation", icon: Database, description: "Test data management", disabled: true },
        { name: "Test Suite Generation", icon: Package, description: "Test suite automation", disabled: true },
        { name: "Insights", icon: BarChart3, description: "Testing analytics and reports", disabled: true },
        { name: "Environment", icon: Settings, description: "Test environment management", disabled: true }
      ]
    },
    {
      title: "InfraX",
      color: "#355493",
      icon: Cloud,
      items: [
        { name: "Environment", icon: Settings, description: "Infrastructure environment setup", disabled: true },
        { name: "Scaffolds", icon: Layers, description: "Infrastructure scaffolding tools", url: "https://demobuilder.waip.wiprocms.com/agentic-chat" },
        { name: "Cost Management", icon: DollarSign, description: "Infrastructure cost optimization", disabled: true },
        { name: "FinOps", icon: DollarSign, description: "Cloud cost management", url: "https://app.harness.io/ng/account/2KolbecvR0aAcgQ5uXBObA/module/ce/overview" },
        { name: "Policies and Guardrails", icon: Shield, description: "Governance and compliance", disabled: true },
        { name: "Security", icon: Lock, description: "Infrastructure security management", disabled: true }
      ]
    },
    {
      title: "Assets",  
      color: "#BE266A",
      icon: Box,
      items: [
        { name: "Scaffolds", icon: Layers, description: "Application scaffolding templates", url: "https://demobuilder.waip.wiprocms.com/agentic-chat" },
        { name: "Wiki", icon: BookMarked, description: "Asset documentation and guides", url: "https://dev.azure.com/WiproPracticeWork/WEGA2.0/_wiki/wikis/WEGA%20wiki/9/02.-Solution-Overview" },
        { name: "AI Agents", icon: Bot, description: "AI-powered automation agents", url: "https://demobuilder.waip.wiprocms.com/" },
        { name: "Accelerators", icon: Zap, description: "Development accelerators and tools", disabled: true }
      ]
    },
    {
      title: "AIRE",
      color: "#746FA7", 
      icon: Bot,
      items: [
        { name: "Chaos", icon: AlertTriangle, description: "Chaos engineering tools", url: "https://app.harness.io/ng/account/2KolbecvR0aAcgQ5uXBObA/module/chaos/orgs/WiproPOC/projects/ChaosDemoDG/chaos-dashboards" },
        { name: "Anomaly Detection", icon: Search, description: "System anomaly detection", disabled: true },
        { name: "Insights", icon: BarChart3, description: "AI-driven insights and analytics", disabled: true },
        { name: "Observability", icon: Telescope, description: "System monitoring and observability", url: "https://app.datadoghq.com/dashboard/4vk-yhn-iju/obsevability-ops?fromUser=false&refresh_mode=sliding&from_ts=1762247296394&to_ts=1762333696394&live=true" },
        { name: "ServiceNow", icon: Activity, description: "ServiceNow integration", disabled: true },
        { name: "Self-healing", icon: Wrench, description: "Automated system recovery", disabled: true },
        { name: "Governance", icon: Crown, description: "AI governance and compliance", disabled: true }
      ]
    },
    {
      title: "Release Management",
      color: "#351A55",
      icon: Package,
      items: [
        { name: "Pipeline", icon: GitBranch, description: "Release pipeline management", disabled: true },
        { name: "Environment", icon: Settings, description: "Release environment configuration", disabled: true },
        { name: "Release Plan", icon: Calendar, description: "Release planning and scheduling", disabled: true },
        { name: "Calendar", icon: Calendar, description: "Release calendar and timeline", disabled: true },
        { name: "Approvals", icon: CheckCircle, description: "Release approval workflows", disabled: true }
      ]
    },
    {
      title: "Security",
      color: "#3498B3",
      icon: Shield,
      items: [
        { name: "Vulnerability", icon: ShieldAlert, description: "Vulnerability assessment and management", url: "https://app.harness.io/ng/account/2KolbecvR0aAcgQ5uXBObA/module/sto/orgs/WiproPOC/projects/Harness_POC/issues?exemptionStatus=None%2CPending%2CRejected%2CExpired" },
        { name: "Application Security", icon: Lock, description: "Application security testing", disabled: true },
        { name: "Risk Management", icon: AlertOctagon, description: "Security risk assessment and mitigation", disabled: true }
      ]
    }
  ];

  const handleMouseEnter = (index: number) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      setActiveDropdown(index);
    }, 150);
  };

  const handleMouseLeave = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      setActiveDropdown(null);
    }, 150);
  };

  const handleItemClick = (item: MenuItem) => {
    if (item.disabled) {
      return;
    }
    
    if (item.onClick) {
      item.onClick();
      setActiveDropdown(null);
    } else if (item.url) {
      window.open(item.url, '_blank', 'noopener,noreferrer');
      setActiveDropdown(null);
    }
  };

  // Clean up timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return (
    <div className="border-b border-border bg-card relative">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex items-center space-x-1 py-3" ref={menuRef}>
          {menuSections.map((section, index) => {
            const SectionIcon = section.icon;
            const isActive = activeDropdown === index;
            
            return (
              <div
                key={index}
                className="relative"
                onMouseEnter={() => handleMouseEnter(index)}
                onMouseLeave={handleMouseLeave}
              >
                <Button 
                  variant="ghost" 
                  className={`flex items-center space-x-2 px-3 py-2 rounded-md transition-colors whitespace-nowrap ${
                    isActive ? 'bg-accent' : 'hover:bg-accent'
                  }`}
                >
                  <div 
                    className="w-5 h-5 rounded flex items-center justify-center"
                    style={{ backgroundColor: section.color }}
                  >
                    <SectionIcon className="w-3 h-3 text-white" />
                  </div>
                  <span className="font-medium">{section.title}</span>
                  <ChevronDown className={`w-3 h-3 opacity-60 transition-transform ${isActive ? 'rotate-180' : ''}`} />
                </Button>
                
                {/* Custom Dropdown */}
                {isActive && (
                  <div className="absolute top-full left-0 mt-2 w-72 bg-popover border border-border rounded-lg shadow-lg z-50 p-1">
                    {section.items.filter(item => !item.hidden).map((item, itemIndex) => {
                      const ItemIcon = item.icon;
                      const isDisabled = item.disabled;
                      const hasAction = item.onClick || item.url;
                      
                      return (
                        <div
                          key={itemIndex}
                          className={`flex items-center space-x-3 p-3 rounded-md transition-colors ${
                            isDisabled 
                              ? 'opacity-50 cursor-not-allowed' 
                              : hasAction 
                                ? 'cursor-pointer hover:bg-accent' 
                                : 'cursor-default'
                          }`}
                          onClick={() => handleItemClick(item)}
                        >
                          <div 
                            className="w-8 h-8 rounded-md flex items-center justify-center"
                            style={{ 
                              backgroundColor: isDarkMode ? `${section.color}20` : `${section.color}15`,
                            }}
                          >
                            <ItemIcon 
                              className="w-4 h-4" 
                              style={{ color: isDarkMode ? 'white' : section.color }}
                            />
                          </div>
                          <div className="flex-1">
                            <div className="font-medium text-popover-foreground">{item.name}</div>
                            <div className="text-muted-foreground mt-0.5 text-sm">
                              {item.description}
                            </div>
                          </div>
                          {hasAction && !isDisabled && (
                            <div className="text-muted-foreground">
                              {item.url ? (
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                </svg>
                              ) : (
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}