import { useState } from 'react';
import { 
  ArrowRight, 
  CheckCircle, 
  Code, 
  Cloud, 
  Shield, 
  Zap, 
  Users, 
  BarChart3, 
  GitBranch, 
  Rocket,
  Star,
  Target,
  TrendingUp,
  Clock,
  Mail,
  Phone,
  MapPin,
  Send,
  Play,
  Award,
  Globe,
  Settings,
  Lock,
  Gauge,
  X,
  Grid,
  Maximize2,
  Sparkles,
  ArrowDownRight,
  FileText,
  Bug,
  TestTube,
  Database,
  CloudUpload,
  AlertTriangle,
  RefreshCw,
  ChevronUp,
  ChevronDown,
  Plus,
  Trash2,
  User,
  UserCheck,
  Bot
} from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Separator } from './ui/separator';
import { Dialog, DialogContent, DialogTrigger, DialogTitle, DialogDescription } from './ui/dialog';
import { Select } from './ui/select';
import { ImageWithFallback } from './figma/ImageWithFallback';
import wegaFramework from "figma:asset/0b25508f2bf48f950882df101afce14ebad87683.png";
import heroImage from "figma:asset/3a6715133ddab9f24952e945a1541705e1b62f24.png";
import mcpCatalogGrid from "figma:asset/c53cae069fb3afd2b24f3c01b327f0f6e0b32781.png";
import img05HowTheRolesAreChanging1 from "figma:asset/1d4d6ffdca8238ab019b9d66c0a15ecbfd4a66e4.png";
import Roadmap from "../imports/Roadmap";
import BuildIqLayers from "../imports/BuildIqLayers";
import VibeProgrammer from "../imports/VibeProgrammer";
import LifeVibeProgrammer from "../imports/LifeVibeProgrammer";
import ModernEngineeringMetrics from "../imports/ModernEngineeringMetrics";
import HowTheRolesAreChanging from "../imports/HowTheRolesAreChanging";
import { AgentCard } from './AgentCardWithOptions';
import { OrchestrationBuildProgress } from './OrchestrationBuildProgress';

interface MarketingLandingPageProps {
  onNavigateToCodeRepo?: () => void;
  onNavigateToPipelines?: () => void;
  onScrollToSignup?: () => void;
  onNavigateToMLOps?: () => void;
  onNavigateToDemoVideos?: () => void;
  isDarkMode?: boolean;
}

export function MarketingLandingPage({ onNavigateToCodeRepo, onNavigateToPipelines, onScrollToSignup, onNavigateToMLOps, onNavigateToDemoVideos, isDarkMode }: MarketingLandingPageProps) {
  const [contactForm, setContactForm] = useState({
    name: '',
    email: '',
    company: '',
    message: ''
  });
  
  const [isImageDialogOpen, setIsImageDialogOpen] = useState(false);
  const [userRequest, setUserRequest] = useState('');
  const [orchestrationPlan, setOrchestrationPlan] = useState<{
    agents: Array<{ name: string; description: string; icon: any; color: string }>;
    sequence: string;
  } | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isAgentEditorOpen, setIsAgentEditorOpen] = useState(false);
  const [editedAgents, setEditedAgents] = useState<Array<{ name: string; description: string; icon: any; color: string }>>([]);
  const [autonomyLevel, setAutonomyLevel] = useState(3); // 0: HITL, 1: Semi-HITL, 2: Semi-Autonomous, 3: Fully Autonomous

  // Orchestration build states
  const [isBuilding, setIsBuilding] = useState(false);
  const [buildProgress, setBuildProgress] = useState(0);
  const [currentBuildStep, setCurrentBuildStep] = useState('');
  const [isBuildComplete, setIsBuildComplete] = useState(false);

  // Define which agents have options (child agents)
  const agentOptions: Record<string, Array<{ name: string; description: string; icon: any; color: string }>> = {
    'UI/UX Design': [
      {
        name: 'Figma',
        description: 'AI-powered UI/UX design creation and prototyping',
        icon: Maximize2,
        color: '#F24E1E'
      },
      {
        name: 'Co-pilot',
        description: 'Microsoft Co-pilot for intelligent UI/UX design assistance',
        icon: Sparkles,
        color: '#00A4EF'
      }
    ],
    'User Story Generation': [
      {
        name: 'Co-pilot',
        description: 'GitHub Co-pilot for AI-assisted user story generation',
        icon: Sparkles,
        color: '#00A4EF'
      },
      {
        name: 'Gemini',
        description: 'Google Gemini for intelligent user story creation',
        icon: Sparkles,
        color: '#8E75F0'
      },
      {
        name: 'Jira Rovo',
        description: 'Atlassian Jira Rovo for AI-powered user story generation and backlog management',
        icon: FileText,
        color: '#0052CC'
      }
    ],
    'CI/CD Pipeline Setup': [
      {
        name: 'Harness',
        description: 'Harness CI/CD for modern software delivery',
        icon: Rocket,
        color: '#00ADE4'
      },
      {
        name: 'GitHub Actions',
        description: 'GitHub Actions for automated workflows and deployments',
        icon: GitBranch,
        color: '#2088FF'
      },
      {
        name: 'GitLab',
        description: 'GitLab CI/CD for complete DevOps platform',
        icon: CloudUpload,
        color: '#FC6D26'
      }
    ],
    'Code Generation': [
      {
        name: 'Factory.AI',
        description: 'Factory.AI for intelligent code generation',
        icon: Code,
        color: '#351A55'
      },
      {
        name: 'Windsurf',
        description: 'Windsurf AI coding assistant for seamless development',
        icon: Sparkles,
        color: '#0EA5E9'
      },
      {
        name: 'Gemini',
        description: 'Google Gemini for advanced code generation',
        icon: Sparkles,
        color: '#8E75F0'
      },
      {
        name: 'Amazon Q',
        description: 'Amazon Q for AWS-optimized code generation',
        icon: Code,
        color: '#FF9900'
      },
      {
        name: 'Co-Pilot',
        description: 'GitHub Co-Pilot for AI-powered code completion',
        icon: Code,
        color: '#00A4EF'
      },
      {
        name: 'Cursor',
        description: 'Cursor AI for intelligent code editing',
        icon: Code,
        color: '#000000'
      }
    ],
    'Anomaly Detection': [
      {
        name: 'Datadog',
        description: 'Datadog for comprehensive anomaly detection and monitoring',
        icon: AlertTriangle,
        color: '#632CA6'
      },
      {
        name: 'Dynatrace',
        description: 'Dynatrace for AI-powered anomaly detection',
        icon: AlertTriangle,
        color: '#1496FF'
      }
    ],
    'Self Healing': [
      {
        name: 'Datadog',
        description: 'Datadog for automated issue resolution and recovery',
        icon: RefreshCw,
        color: '#632CA6'
      },
      {
        name: 'Dynatrace',
        description: 'Dynatrace for intelligent self-healing capabilities',
        icon: RefreshCw,
        color: '#1496FF'
      }
    ]
  };

  // State to track selected options for each agent
  const [selectedOptions, setSelectedOptions] = useState<Record<number, { name: string; description: string; icon: any; color: string } | null>>({});
  const [optionsDialogOpen, setOptionsDialogOpen] = useState<number | null>(null);

  // Comprehensive AI Agent definitions covering all SDLC activities
  const aiAgents = {
    // Requirements & Planning
    requirementGathering: { 
      name: 'Requirements Gathering', 
      description: 'AI-powered stakeholder interview analysis and requirement extraction',
      icon: Users,
      color: '#351A55',
      keywords: ['requirement gathering', 'gather requirements', 'elicit requirements', 'stakeholder interview', 'requirement analysis']
    },
    userStoryGeneration: { 
      name: 'User Story Generation', 
      description: 'Automated user story creation from requirements',
      icon: FileText,
      color: '#746FA7',
      keywords: ['user story', 'user stories', 'story creation', 'epic', 'backlog']
    },
    jiraRovo: { 
      name: 'Jira Rovo', 
      description: 'AI-powered user story generation, documentation and decision making',
      icon: FileText,
      color: '#0052CC',
      keywords: ['jira', 'rovo', 'user story', 'documentation', 'decision making', 'agile', 'backlog management']
    },
    requirementDoc: { 
      name: 'BRD Generator', 
      description: 'Business requirement document generation',
      icon: FileText,
      color: '#746FA7',
      keywords: ['requirement', 'brd', 'business requirement', 'specification', 'functional spec']
    },
    technicalSpec: { 
      name: 'Technical Specification', 
      description: 'Generate detailed technical specifications and architecture docs',
      icon: FileText,
      color: '#355493',
      keywords: ['technical spec', 'tech spec', 'architecture doc', 'design document', 'technical design']
    },

    // Design & Architecture
    systemArchitecture: { 
      name: 'System Architecture Design', 
      description: 'AI-powered system architecture and design patterns',
      icon: Grid,
      color: '#351A55',
      keywords: ['architecture', 'system design', 'architectural design', 'design pattern', 'microservice architecture']
    },
    databaseDesign: { 
      name: 'Database Design', 
      description: 'Intelligent database schema design and optimization',
      icon: Database,
      color: '#355493',
      keywords: ['database design', 'schema design', 'data model', 'database architecture', 'erd']
    },
    apiDesign: { 
      name: 'API Design', 
      description: 'RESTful and GraphQL API design and documentation',
      icon: Globe,
      color: '#3498B3',
      keywords: ['api design', 'rest api', 'graphql', 'api specification', 'swagger', 'openapi']
    },
    uiuxDesign: { 
      name: 'UI/UX Design', 
      description: 'User interface and experience design automation',
      icon: Maximize2,
      color: '#BE266A',
      keywords: ['ui design', 'ux design', 'interface design', 'user experience', 'wireframe', 'mockup']
    },
    figma: { 
      name: 'Figma', 
      description: 'AI-powered UI/UX design creation and prototyping',
      icon: Maximize2,
      color: '#F24E1E',
      keywords: ['figma', 'ui', 'ux', 'design', 'prototype', 'wireframe', 'interface design', 'mockup']
    },

    // Development & Code
    codeGeneration: { 
      name: 'Code Generation', 
      description: 'AI-powered code generation from requirements',
      icon: Code,
      color: '#351A55',
      keywords: ['generate code', 'create code', 'write code', 'develop', 'implement', 'build feature', 'coding', 'programming']
    },
    windsurf: { 
      name: 'Windsurf', 
      description: 'AI agent for code generation, debugging and refactoring',
      icon: Code,
      color: '#0EA5E9',
      keywords: ['windsurf', 'code generation', 'code debugging', 'code refactoring', 'ai coding', 'ai development']
    },
    codeReview: { 
      name: 'Code Review', 
      description: 'Automated code review and quality analysis',
      icon: CheckCircle,
      color: '#3498B3',
      keywords: ['code review', 'review code', 'peer review', 'code analysis', 'code quality']
    },
    codeRefactoring: { 
      name: 'Code Refactoring', 
      description: 'Intelligent code refactoring and optimization',
      icon: RefreshCw,
      color: '#355493',
      keywords: ['refactor', 'refactoring', 'code cleanup', 'optimize code', 'improve code']
    },
    codeDebugging: { 
      name: 'Code Debugging', 
      description: 'Intelligent debugging and error resolution',
      icon: Bug,
      color: '#BE266A',
      keywords: ['debug', 'fix bug', 'error', 'troubleshoot', 'resolve issue', 'bug fix', 'debugging']
    },
    staticAnalysis: { 
      name: 'Static Code Analysis', 
      description: 'Automated static code analysis and linting',
      icon: Shield,
      color: '#746FA7',
      keywords: ['static analysis', 'code analysis', 'linting', 'code smell', 'sonarqube']
    },

    // Testing
    unitTesting: { 
      name: 'Unit Testing', 
      description: 'Automated unit test generation and execution',
      icon: TestTube,
      color: '#3498B3',
      keywords: ['unit test', 'unit testing', 'test coverage', 'junit', 'pytest']
    },
    integrationTesting: { 
      name: 'Integration Testing', 
      description: 'Automated integration test creation and execution',
      icon: GitBranch,
      color: '#355493',
      keywords: ['integration test', 'integration testing', 'api testing', 'service testing']
    },
    systemTesting: { 
      name: 'System Testing', 
      description: 'End-to-end system testing and validation',
      icon: Settings,
      color: '#351A55',
      keywords: ['system test', 'system testing', 'end to end', 'e2e testing', 'functional testing']
    },
    regressionTesting: { 
      name: 'Regression Testing', 
      description: 'Automated regression test suite execution',
      icon: RefreshCw,
      color: '#BE266A',
      keywords: ['regression test', 'regression testing', 'regression suite', 'automated regression']
    },
    uatTesting: { 
      name: 'User Acceptance Testing', 
      description: 'UAT test case generation and execution support',
      icon: Users,
      color: '#746FA7',
      keywords: ['uat', 'user acceptance test', 'acceptance testing', 'user testing']
    },
    performanceTesting: { 
      name: 'Performance Testing', 
      description: 'Load, stress, and performance testing automation',
      icon: Gauge,
      color: '#3498B3',
      keywords: ['performance test', 'load test', 'stress test', 'performance testing', 'jmeter', 'gatling']
    },
    securityTesting: { 
      name: 'Security Testing', 
      description: 'Security vulnerability scanning and penetration testing',
      icon: Lock,
      color: '#BE266A',
      keywords: ['security test', 'security testing', 'penetration test', 'vulnerability scan', 'security audit']
    },
    testDataGeneration: { 
      name: 'Test Data Generation', 
      description: 'Intelligent test data creation and management',
      icon: Database,
      color: '#355493',
      keywords: ['test data', 'generate data', 'mock data', 'sample data', 'test data generation']
    },

    // Deployment & Release
    cicdPipeline: { 
      name: 'CI/CD Pipeline Setup', 
      description: 'Automated CI/CD pipeline configuration',
      icon: GitBranch,
      color: '#351A55',
      keywords: ['ci/cd', 'pipeline', 'jenkins', 'github actions', 'gitlab ci', 'continuous integration', 'continuous deployment']
    },
    harnessCICD: { 
      name: 'Harness CI-CD', 
      description: 'Modern CI/CD platform for automated deployments and releases',
      icon: Rocket,
      color: '#00ADE4',
      keywords: ['harness', 'ci cd', 'deployment', 'pipeline', 'release automation', 'continuous delivery']
    },
    deployment: { 
      name: 'Production Deployment', 
      description: 'Automated deployment orchestration',
      icon: CloudUpload,
      color: '#3498B3',
      keywords: ['deploy', 'deployment', 'release', 'production', 'publish', 'launch', 'rollout']
    },
    rollback: { 
      name: 'Automated Rollback', 
      description: 'Intelligent rollback and recovery mechanisms',
      icon: RefreshCw,
      color: '#BE266A',
      keywords: ['rollback', 'revert', 'roll back', 'undo deployment', 'restore']
    },
    releaseManagement: { 
      name: 'Release Management', 
      description: 'Release planning and version management',
      icon: Rocket,
      color: '#355493',
      keywords: ['release management', 'version control', 'release planning', 'release notes']
    },

    // Infrastructure & DevOps
    infrastructureProvisioning: { 
      name: 'Infrastructure Provisioning', 
      description: 'Automated infrastructure as code deployment',
      icon: Cloud,
      color: '#3498B3',
      keywords: ['infrastructure', 'provisioning', 'terraform', 'cloudformation', 'iac', 'infrastructure as code']
    },
    containerization: { 
      name: 'Containerization', 
      description: 'Docker and container orchestration',
      icon: Grid,
      color: '#355493',
      keywords: ['docker', 'container', 'containerization', 'kubernetes', 'k8s', 'orchestration']
    },
    configManagement: { 
      name: 'Configuration Management', 
      description: 'Automated configuration management and version control',
      icon: Settings,
      color: '#746FA7',
      keywords: ['configuration', 'config management', 'ansible', 'puppet', 'chef']
    },

    // Monitoring & Operations
    monitoring: { 
      name: 'Application Monitoring', 
      description: 'Real-time application performance monitoring',
      icon: BarChart3,
      color: '#3498B3',
      keywords: ['monitor', 'monitoring', 'observability', 'apm', 'application monitoring']
    },
    datadog: { 
      name: 'Datadog', 
      description: 'Comprehensive monitoring and observability platform',
      icon: BarChart3,
      color: '#632CA6',
      keywords: ['datadog', 'monitoring', 'observability', 'apm', 'metrics', 'logs', 'traces']
    },
    logging: { 
      name: 'Log Management', 
      description: 'Centralized logging and log analysis',
      icon: FileText,
      color: '#355493',
      keywords: ['logging', 'log management', 'log analysis', 'elk', 'splunk']
    },
    anomalyDetection: { 
      name: 'Anomaly Detection', 
      description: 'Real-time anomaly detection and alerting',
      icon: AlertTriangle,
      color: '#BE266A',
      keywords: ['anomaly', 'detect anomaly', 'anomaly detection', 'unusual behavior']
    },
    alerting: { 
      name: 'Alert Management', 
      description: 'Intelligent alerting and notification system',
      icon: AlertTriangle,
      color: '#BE266A',
      keywords: ['alert', 'alerting', 'notification', 'incident alert', 'pagerduty']
    },
    selfHealing: { 
      name: 'Self Healing', 
      description: 'Automated issue resolution and recovery',
      icon: RefreshCw,
      color: '#355493',
      keywords: ['heal', 'auto fix', 'recover', 'restore', 'self-healing', 'automatic repair', 'auto recovery']
    },

    // Security & Compliance
    vulnerabilityScanning: { 
      name: 'Vulnerability Scanning', 
      description: 'Automated security vulnerability detection',
      icon: Shield,
      color: '#BE266A',
      keywords: ['vulnerability', 'vulnerability scan', 'security scan', 'cve', 'security vulnerability']
    },
    complianceCheck: { 
      name: 'Compliance Validation', 
      description: 'Automated compliance checking and reporting',
      icon: CheckCircle,
      color: '#746FA7',
      keywords: ['compliance', 'audit', 'regulatory compliance', 'gdpr', 'hipaa', 'sox']
    },
    secretsManagement: { 
      name: 'Secrets Management', 
      description: 'Secure secrets and credentials management',
      icon: Lock,
      color: '#351A55',
      keywords: ['secrets', 'credentials', 'api keys', 'vault', 'secrets management']
    },

    // Performance & Optimization
    performanceOptimization: { 
      name: 'Performance Optimization', 
      description: 'AI-powered performance tuning and optimization',
      icon: Zap,
      color: '#3498B3',
      keywords: ['optimize', 'optimization', 'performance optimization', 'tuning', 'performance tuning']
    },
    codeProfiler: { 
      name: 'Code Profiling', 
      description: 'Application profiling and bottleneck detection',
      icon: Gauge,
      color: '#355493',
      keywords: ['profiling', 'profiler', 'performance profiling', 'bottleneck', 'performance analysis']
    },
    costOptimization: { 
      name: 'Cost Optimization', 
      description: 'Cloud cost analysis and optimization',
      icon: TrendingUp,
      color: '#746FA7',
      keywords: ['cost optimization', 'finops', 'cloud cost', 'cost analysis', 'cost reduction']
    },

    // Documentation
    apiDocumentation: { 
      name: 'API Documentation', 
      description: 'Automated API documentation generation',
      icon: FileText,
      color: '#3498B3',
      keywords: ['api documentation', 'api docs', 'swagger docs', 'postman']
    },
    technicalDocumentation: { 
      name: 'Technical Documentation', 
      description: 'Automated technical documentation creation',
      icon: FileText,
      color: '#355493',
      keywords: ['technical documentation', 'technical docs', 'developer docs', 'readme']
    },
    userManual: { 
      name: 'User Manual Generation', 
      description: 'End-user documentation and help guides',
      icon: Users,
      color: '#746FA7',
      keywords: ['user manual', 'user guide', 'help documentation', 'user documentation']
    },

    // Data & Analytics
    dataAnalysis: { 
      name: 'Data Analysis', 
      description: 'Automated data analysis and insights generation',
      icon: BarChart3,
      color: '#3498B3',
      keywords: ['data analysis', 'analytics', 'data insights', 'business intelligence']
    },
    reportGeneration: { 
      name: 'Report Generation', 
      description: 'Automated reporting and dashboard creation',
      icon: BarChart3,
      color: '#355493',
      keywords: ['report', 'reporting', 'dashboard', 'metrics report', 'analytics report']
    }
  };

  const analyzeRequest = (request: string) => {
    setIsAnalyzing(true);
    
    // Simulate AI analysis
    setTimeout(() => {
      const lowerRequest = request.toLowerCase();
      let selectedAgents: any[] = [];
      
      // Intelligent intent detection
      const intent = {
        // Actions/Verbs
        isCreating: /\b(create|creating|make|making|generate|generating)\b/.test(lowerRequest),
        isBuilding: /\b(build|building|develop|developing|implement|implementing)\b/.test(lowerRequest),
        isDesigning: /\b(design|designing|architect|architecting|plan|planning)\b/.test(lowerRequest),
        isTesting: /\b(test|testing|qa|quality|verify|verifying|validate|validating)\b/.test(lowerRequest),
        isDeploying: /\b(deploy|deploying|release|releasing|launch|launching)\b/.test(lowerRequest),
        isMonitoring: /\b(monitor|monitoring|observe|observing|track|tracking)\b/.test(lowerRequest),
        isSecuring: /\b(secure|securing|security|protect|protecting)\b/.test(lowerRequest),
        isOptimizing: /\b(optimize|optimizing|improve|improving|enhance|enhancing|performance)\b/.test(lowerRequest),
        isDebugging: /\b(debug|debugging|fix|fixing|troubleshoot|troubleshooting)\b/.test(lowerRequest),
        isDocumenting: /\b(document|documenting|documentation)\b/.test(lowerRequest),
        
        // Scope/Objects
        isApplication: /\b(application|app|system|software|service|platform)\b/.test(lowerRequest),
        isAPI: /\b(api|endpoint|rest|graphql|interface)\b/.test(lowerRequest),
        isDatabase: /\b(database|db|data|schema|storage)\b/.test(lowerRequest),
        isInfrastructure: /\b(infrastructure|infra|cloud|server|container|kubernetes)\b/.test(lowerRequest),
        isCode: /\b(code|coding|programming|script|function)\b/.test(lowerRequest),
        
        // Modifiers
        isOnlyOrJust: /\b(only|just|solely)\b/.test(lowerRequest),
        isComplete: /\b(complete|full|entire|comprehensive|end-to-end|scratch)\b/.test(lowerRequest),
        isFromScratch: /\b(scratch|beginning|start)\b/.test(lowerRequest)
      };
      
      // Decision logic based on intent understanding
      
      // UI/UX Design requests (check this FIRST before general design)
      if ((intent.isCreating || intent.isDesigning) && 
          (lowerRequest.includes('ui') || lowerRequest.includes('ux') || 
           lowerRequest.includes('interface') || lowerRequest.includes('mockup') ||
           lowerRequest.includes('wireframe') || lowerRequest.includes('prototype') ||
           lowerRequest.includes('figma'))) {
        selectedAgents = [
          aiAgents.uiuxDesign
        ];
      }
      // Design-only requests (system architecture, database, API)
      else if ((intent.isCreating || intent.isDesigning) && 
          (lowerRequest.includes('design') || lowerRequest.includes('architect')) &&
          !intent.isBuilding && !lowerRequest.includes('code')) {
        selectedAgents = [
          aiAgents.systemArchitecture,
          aiAgents.databaseDesign,
          aiAgents.apiDesign
        ];
      }
      // Testing-only requests
      else if (intent.isTesting && intent.isApplication && !intent.isBuilding) {
        selectedAgents = [
          aiAgents.testDataGeneration,
          aiAgents.unitTesting,
          aiAgents.integrationTesting,
          aiAgents.systemTesting,
          aiAgents.regressionTesting,
          aiAgents.performanceTesting,
          aiAgents.securityTesting,
          aiAgents.uatTesting
        ];
      }
      // Complete application build from scratch
      else if ((intent.isBuilding || (intent.isCreating && intent.isApplication)) && 
               (intent.isComplete || intent.isFromScratch)) {
        selectedAgents = [
          aiAgents.requirementGathering,
          aiAgents.requirementDoc,
          aiAgents.systemArchitecture,
          aiAgents.databaseDesign,
          aiAgents.apiDesign,
          aiAgents.uiuxDesign,
          aiAgents.userStoryGeneration,
          aiAgents.codeGeneration,
          aiAgents.codeReview,
          aiAgents.unitTesting,
          aiAgents.integrationTesting,
          aiAgents.cicdPipeline,
          aiAgents.deployment
        ];
      }
      // Security-focused requests
      else if (intent.isSecuring) {
        selectedAgents = [
          aiAgents.securityTesting,
          aiAgents.vulnerabilityScanning,
          aiAgents.complianceCheck,
          aiAgents.secretsManagement,
          aiAgents.staticAnalysis
        ];
      }
      // Monitoring and operations
      else if (intent.isMonitoring) {
        selectedAgents = [
          aiAgents.monitoring,
          aiAgents.logging,
          aiAgents.anomalyDetection,
          aiAgents.alerting,
          aiAgents.selfHealing
        ];
      }
      // Performance optimization
      else if (intent.isOptimizing) {
        selectedAgents = [
          aiAgents.performanceTesting,
          aiAgents.performanceOptimization,
          aiAgents.costOptimization,
          aiAgents.monitoring
        ];
      }
      // Deployment requests
      else if (intent.isDeploying) {
        selectedAgents = [
          aiAgents.cicdPipeline,
          aiAgents.deployment,
          aiAgents.containerization,
          aiAgents.monitoring
        ];
      }
      // Debugging requests
      else if (intent.isDebugging) {
        selectedAgents = [
          aiAgents.codeDebugging,
          aiAgents.logging,
          aiAgents.anomalyDetection
        ];
      }
      // Documentation requests
      else if (intent.isDocumenting) {
        selectedAgents = [
          aiAgents.requirementDoc,
          aiAgents.apiDocumentation,
          aiAgents.technicalDocumentation
        ];
      }
      // API-specific requests
      else if (intent.isAPI && (intent.isCreating || intent.isBuilding || intent.isDesigning)) {
        selectedAgents = [
          aiAgents.apiDesign,
          aiAgents.codeGeneration,
          aiAgents.apiDocumentation,
          aiAgents.unitTesting,
          aiAgents.integrationTesting
        ];
      }
      // Database-specific requests
      else if (intent.isDatabase && (intent.isCreating || intent.isBuilding || intent.isDesigning)) {
        selectedAgents = [
          aiAgents.databaseDesign,
          aiAgents.databaseDesign,
          aiAgents.testDataGeneration
        ];
      }
      // Code generation requests
      else if (intent.isCode && (intent.isCreating || intent.isBuilding)) {
        selectedAgents = [
          aiAgents.codeGeneration,
          aiAgents.codeReview,
          aiAgents.unitTesting
        ];
      }
      // Infrastructure requests
      else if (intent.isInfrastructure) {
        selectedAgents = [
          aiAgents.infrastructureProvisioning,
          aiAgents.containerization,
          aiAgents.monitoring
        ];
      }
      // General keyword matching fallback
      else {
        Object.values(aiAgents).forEach(agent => {
          // Skip jiraRovo - it's only available in User Story Generation dialog
          if (agent.name === 'Jira Rovo') return;
          if (agent.keywords.some(keyword => lowerRequest.includes(keyword))) {
            selectedAgents.push(agent);
          }
        });
      }
      
      // If no specific matches, provide a comprehensive default workflow
      if (selectedAgents.length === 0) {
        selectedAgents = [
          aiAgents.requirementDoc,
          aiAgents.systemArchitecture,
          aiAgents.databaseDesign,
          aiAgents.apiDesign,
          aiAgents.userStoryGeneration,
          aiAgents.codeGeneration,
          aiAgents.codeReview,
          aiAgents.unitTesting,
          aiAgents.integrationTesting,
          aiAgents.cicdPipeline,
          aiAgents.deployment,
          aiAgents.monitoring
        ];
      }
      
      // Remove duplicates while preserving order, and filter out jiraRovo
      const uniqueAgents = selectedAgents
        .filter((agent, index, self) =>
          index === self.findIndex((a) => a.name === agent.name)
        )
        .filter(agent => agent.name !== 'Jira Rovo'); // Exclude Jira Rovo from orchestration
      
      // Create orchestration plan
      const plan = {
        agents: uniqueAgents,
        sequence: uniqueAgents.map(a => a.name).join(' → ')
      };
      
      setOrchestrationPlan(plan);
      setIsAnalyzing(false);
    }, 1500);
  };

  const handleSubmitRequest = (e: React.FormEvent) => {
    e.preventDefault();
    if (userRequest.trim()) {
      analyzeRequest(userRequest);
    }
  };

  const handleContactSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Handle contact form submission
    console.log('Contact form submitted:', contactForm);
    // Reset form
    setContactForm({ name: '', email: '', company: '', message: '' });
  };

  // Agent editor handlers
  const handleOpenAgentEditor = () => {
    if (orchestrationPlan) {
      setEditedAgents([...orchestrationPlan.agents]);
      setIsAgentEditorOpen(true);
    }
  };

  const handleMoveAgentUp = (index: number) => {
    if (index > 0) {
      const newAgents = [...editedAgents];
      [newAgents[index - 1], newAgents[index]] = [newAgents[index], newAgents[index - 1]];
      setEditedAgents(newAgents);
    }
  };

  const handleMoveAgentDown = (index: number) => {
    if (index < editedAgents.length - 1) {
      const newAgents = [...editedAgents];
      [newAgents[index], newAgents[index + 1]] = [newAgents[index + 1], newAgents[index]];
      setEditedAgents(newAgents);
    }
  };

  const handleRemoveAgent = (index: number) => {
    const newAgents = editedAgents.filter((_, i) => i !== index);
    setEditedAgents(newAgents);
  };

  const handleAddAgent = (agentKey: string) => {
    const agent = aiAgents[agentKey as keyof typeof aiAgents];
    if (agent && !editedAgents.some(a => a.name === agent.name)) {
      setEditedAgents([...editedAgents, agent]);
    }
  };

  const handleSaveAgentChanges = () => {
    if (editedAgents.length > 0) {
      setOrchestrationPlan({
        agents: editedAgents,
        sequence: editedAgents.map(a => a.name).join(' → ')
      });
      setIsAgentEditorOpen(false);
    }
  };

  const handleCancelAgentEdit = () => {
    setIsAgentEditorOpen(false);
    setEditedAgents([]);
  };

  // Handle building orchestration
  const handleBuildOrchestration = () => {
    if (!orchestrationPlan) return;
    
    setIsBuilding(true);
    setBuildProgress(0);
    setIsBuildComplete(false);
    
    const agents = orchestrationPlan.agents;
    const buildSteps = [
      'Initializing agent containers...',
      'Setting up communication protocols...',
      'Configuring data pipelines...',
      'Establishing API integrations...',
      'Synchronizing agent workflows...',
      'Building agent orchestration network...',
      'Validating integration connections...',
      'Finalizing orchestration setup...'
    ];
    
    let currentStep = 0;
    const totalSteps = buildSteps.length;
    const stepDuration = 800; // ms per step
    
    const interval = setInterval(() => {
      if (currentStep < totalSteps) {
        setCurrentBuildStep(buildSteps[currentStep]);
        setBuildProgress(((currentStep + 1) / totalSteps) * 100);
        currentStep++;
      } else {
        clearInterval(interval);
        setIsBuildComplete(true);
        setIsBuilding(false);
      }
    }, stepDuration);
  };

  const features = [
    {
      icon: Code,
      title: "AI-Enhanced DevEX",
      description: "Intelligent developer experience with AI-powered code repositories, smart pipelines, and predictive insights.",
      color: "#351A55"
    },
    {
      icon: Cloud,
      title: "Smart Infrastructure",
      description: "AI-driven infrastructure automation, intelligent cost optimization, and predictive scaling with enterprise security.",
      color: "#355493"
    },
    {
      icon: Shield,
      title: "Intelligent Testing",
      description: "AI-powered test generation, automated quality assurance, and intelligent defect prediction for comprehensive testing.",
      color: "#3498B3"
    },
    {
      icon: Rocket,
      title: "AI-Driven Releases",
      description: "Intelligent deployment pipelines with AI-powered risk assessment, automated rollbacks, and smart approval workflows.",
      color: "#351A55"
    },
    {
      icon: BarChart3,
      title: "Predictive Analytics",
      description: "Advanced AI analytics platform with intelligent anomaly detection, predictive insights, and automated optimization.",
      color: "#746FA7"
    },
    {
      icon: Zap,
      title: "AI Asset Library",
      description: "Intelligent templates, AI-powered development agents, and smart accelerators that adapt to your workflow patterns.",
      color: "#BE266A"
    }
  ];

  const benefits = [
    {
      icon: TrendingUp,
      title: "80% Faster Development (Projected)",
      description: "Our early testing shows significant acceleration in development lifecycle with automated workflows"
    },
    {
      icon: Clock,
      title: "50% Reduced Time-to-Market (Target)",
      description: "Designed to dramatically reduce product delivery time with streamlined processes"
    },
    {
      icon: Target,
      title: "99.9% Platform Reliability (Goal)",
      description: "Built with enterprise-grade reliability, automated monitoring and self-healing capabilities"
    },
    {
      icon: Users,
      title: "Unified Developer Experience",
      description: "One platform for all development, testing, and deployment needs - coming soon"
    }
  ];

  const stats = [
    { number: "2024", label: "Launch Year" },
    { number: "8", label: "Integrated Modules" },
    { number: "50+", label: "Beta Partners" },
    { number: "95%", label: "Development Complete" }
  ];

  const testimonials = [
    {
      name: "Sarah Chen",
      role: "CTO, Design Partner",
      company: "Fortune 500 Technology Company",
      quote: "We're excited to be part of WEGA's development journey. The early previews show tremendous potential for transforming enterprise development workflows.",
      rating: 5
    },
    {
      name: "Michael Rodriguez",
      role: "VP Engineering, Beta Partner",
      company: "High-Growth SaaS Startup",
      quote: "The vision for AI-powered insights and unified development experience is exactly what the industry needs. Can't wait for the full launch.",
      rating: 5
    },
    {
      name: "David Kumar",
      role: "Lead DevOps, Early Adopter",
      company: "Global Financial Services",
      quote: "Based on our early access sessions, WEGA will set a new standard for enterprise development platforms. The security-first approach is impressive.",
      rating: 5
    }
  ];

  return (
    <div className="flex flex-col">
      {/* AI Orchestration Hero Section */}
      <section className="relative bg-gradient-to-br from-[#351A55] via-[#355493] to-[#3498B3] text-white overflow-hidden">
        <div className="absolute inset-0 bg-black/50" />
        <div className="relative max-w-7xl mx-auto px-6 py-20 lg:py-32">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 mb-6 bg-white/10 backdrop-blur-sm rounded-full px-6 py-3">
              <Sparkles className="w-5 h-5 text-yellow-400" />
              <span className="text-sm font-medium">AI-Powered Software Engineering Platform</span>
            </div>
            <h1 className="font-bold leading-tight text-[56px] mb-6">
              What do you want to <span className="bg-gradient-to-r from-yellow-400 to-orange-500 bg-clip-text text-transparent">accomplish</span> today?
            </h1>
            <p className="text-xl text-white/90 max-w-3xl mx-auto mb-12">
              Describe your software engineering task, and our AI orchestrator will identify the optimal sequence of AI agents to accomplish your goal.
            </p>
          </div>

          {/* Request Input Form */}
          <div className="max-w-4xl mx-auto mb-16">
            <form onSubmit={handleSubmitRequest} className="space-y-4">
              <div className="relative">
                <Textarea
                  value={userRequest}
                  onChange={(e) => setUserRequest(e.target.value)}
                  placeholder="E.g., 'I need to create a new REST API endpoint, write unit tests for it, and deploy it to production' or 'Debug the authentication issue in our mobile app and fix it'"
                  className="w-full h-32 bg-white/95 dark:bg-slate-900/95 text-card-foreground border-2 border-white/20 rounded-2xl px-6 py-4 text-lg resize-none focus:ring-2 focus:ring-yellow-400 focus:border-transparent"
                  required
                />
                {userRequest && (
                  <button
                    type="button"
                    onClick={() => {
                      setUserRequest('');
                      setOrchestrationPlan(null);
                    }}
                    className="absolute top-4 right-4 p-2 hover:bg-muted rounded-lg transition-colors"
                  >
                    <X className="w-5 h-5 text-muted-foreground" />
                  </button>
                )}
              </div>

              {/* AI Autonomy Level Slider */}
              <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-6 border border-white/20">
                <div className="mb-4">
                  <label className="text-white mb-2 flex items-center gap-2">
                    <Settings className="w-5 h-5" />
                    AI Autonomy Level
                  </label>
                  <p className="text-white/70 text-sm">
                    Control how much human oversight is required during execution
                  </p>
                </div>
                
                <div className="relative px-2">
                  {/* Slider Track */}
                  <input
                    type="range"
                    min="0"
                    max="3"
                    value={autonomyLevel}
                    onChange={(e) => setAutonomyLevel(parseInt(e.target.value))}
                    className="w-full h-2 bg-white/20 rounded-lg appearance-none cursor-pointer slider-thumb"
                    style={{
                      background: `linear-gradient(to right, #BE266A 0%, #746FA7 33%, #3498B3 66%, #351A55 100%)`
                    }}
                  />
                  
                  {/* Level Labels */}
                  <div className="flex justify-between mt-4 text-sm">
                    <div className={`flex flex-col items-center gap-1 transition-all ${autonomyLevel === 0 ? 'text-white scale-110' : 'text-white/60'}`}>
                      <User className="w-5 h-5" />
                      <span className="text-xs">Human in</span>
                      <span className="text-xs">the Loop</span>
                    </div>
                    <div className={`flex flex-col items-center gap-1 transition-all ${autonomyLevel === 1 ? 'text-white scale-110' : 'text-white/60'}`}>
                      <UserCheck className="w-5 h-5" />
                      <span className="text-xs">Semi-HITL</span>
                      <span className="text-xs opacity-0">.</span>
                    </div>
                    <div className={`flex flex-col items-center gap-1 transition-all ${autonomyLevel === 2 ? 'text-white scale-110' : 'text-white/60'}`}>
                      <Settings className="w-5 h-5" />
                      <span className="text-xs">Semi-</span>
                      <span className="text-xs">Autonomous</span>
                    </div>
                    <div className={`flex flex-col items-center gap-1 transition-all ${autonomyLevel === 3 ? 'text-white scale-110' : 'text-white/60'}`}>
                      <Bot className="w-5 h-5" />
                      <span className="text-xs">Fully</span>
                      <span className="text-xs">Autonomous</span>
                    </div>
                  </div>
                  
                  {/* Description based on level */}
                  <div className="mt-4 p-4 bg-white/5 rounded-lg border border-white/10">
                    {autonomyLevel === 0 && (
                      <p className="text-white/90 text-sm">
                        <strong>Human in the Loop:</strong> AI agents will pause and request approval before each major action. Maximum human control and oversight.
                      </p>
                    )}
                    {autonomyLevel === 1 && (
                      <p className="text-white/90 text-sm">
                        <strong>Semi-HITL:</strong> AI agents will execute most tasks autonomously but will request approval for critical decisions and deployments.
                      </p>
                    )}
                    {autonomyLevel === 2 && (
                      <p className="text-white/90 text-sm">
                        <strong>Semi-Autonomous:</strong> AI agents work independently with periodic checkpoints. Human intervention only for high-risk operations.
                      </p>
                    )}
                    {autonomyLevel === 3 && (
                      <p className="text-white/90 text-sm">
                        <strong>Fully Autonomous:</strong> AI agents execute the entire workflow independently. Humans are notified of results but no approvals required.
                      </p>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex justify-center gap-4">
                <Button 
                  type="submit" 
                  size="lg"
                  disabled={isAnalyzing || !userRequest.trim()}
                  className="bg-white text-[#351A55] hover:bg-white/90 px-8 py-6 text-lg"
                >
                  {isAnalyzing ? (
                    <>
                      <RefreshCw className="w-5 h-5 mr-2 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5 mr-2" />
                      Orchestrate AI Agents
                    </>
                  )}
                </Button>
                <Button 
                  size="lg"
                  variant="outline"
                  className="border-white text-white hover:bg-white/10 px-8 py-6 text-lg"
                  onClick={onNavigateToDemoVideos}
                >
                  <Play className="w-5 h-5 mr-2" />
                  Watch Demo
                </Button>
              </div>
            </form>
          </div>

          {/* Orchestration Plan Display */}
          {orchestrationPlan && (
            <div className="max-w-6xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-700">
              <div className="bg-white/95 dark:bg-slate-900/95 rounded-2xl p-8 shadow-2xl">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-full bg-green-500 flex items-center justify-center">
                    <CheckCircle className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-bold text-card-foreground">
                      AI Orchestration Plan Generated
                    </h3>
                    <p className="text-muted-foreground">
                      {orchestrationPlan.agents.length} AI agent{orchestrationPlan.agents.length > 1 ? 's' : ''} will be activated in sequence
                    </p>
                  </div>
                </div>

                {/* Sequence Summary */}
                <div className="mb-8 p-4 bg-muted/50 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <GitBranch className="w-5 h-5 text-muted-foreground" />
                    <span className="font-medium text-card-foreground">Execution Sequence:</span>
                  </div>
                  <p className="text-sm text-muted-foreground pl-7">
                    {orchestrationPlan.sequence}
                  </p>
                </div>

                {/* Agent Cards */}
                <div className="space-y-4">
                  {orchestrationPlan.agents.map((agent, index) => (
                    <AgentCard
                      key={index}
                      agent={agent}
                      index={index}
                      hasOptions={agentOptions[agent.name]}
                      selectedOption={selectedOptions[index]}
                      onSelectOption={(option) => {
                        setSelectedOptions(prev => ({
                          ...prev,
                          [index]: option
                        }));
                      }}
                      showArrow={index > 0}
                    />
                  ))}
                </div>

                {/* Action Buttons */}
                <div className="mt-8 pt-6 border-t border-border flex justify-center gap-4">
                  <Button
                    size="lg"
                    className="bg-[#351A55] hover:bg-[#2a1444] text-white"
                    onClick={handleBuildOrchestration}
                  >
                    Continue
                    <ArrowRight className="w-5 h-5 ml-2" />
                  </Button>
                  <Button
                    size="lg"
                    className="bg-gradient-to-r from-[#3498B3] to-[#355493] hover:from-[#2a7a99] hover:to-[#2a4475] text-white border-2 border-white/20 shadow-lg hover:shadow-xl transition-all"
                    onClick={handleOpenAgentEditor}
                  >
                    <Settings className="w-5 h-5 mr-2" />
                    Modify Agent Orchestration
                  </Button>
                  <Button
                    size="lg"
                    variant="outline"
                    onClick={() => {
                      setUserRequest('');
                      setOrchestrationPlan(null);
                    }}
                  >
                    <RefreshCw className="w-5 h-5 mr-2" />
                    Reset
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Build Progress Display */}
          {orchestrationPlan && (
            <OrchestrationBuildProgress
              isBuilding={isBuilding}
              isBuildComplete={isBuildComplete}
              buildProgress={buildProgress}
              currentBuildStep={currentBuildStep}
              agents={orchestrationPlan.agents}
              onComplete={() => document.getElementById('signup-section')?.scrollIntoView({ behavior: 'smooth' })}
              onViewDetails={() => {
                setIsBuildComplete(false);
                setBuildProgress(0);
                setCurrentBuildStep('');
              }}
            />
          )}

          {/* Quick Examples */}
          {!orchestrationPlan && !isAnalyzing && (
            <div className="max-w-4xl mx-auto">
              <p className="text-center text-white/70 mb-4">Try these examples:</p>
              <div className="grid md:grid-cols-2 gap-3">
                {[
                  "I want to create application design",
                  "I want to test an application",
                  "Build a complete e-commerce application from scratch",
                  "Secure our application and scan for vulnerabilities",
                  "Monitor our production system and auto-heal issues",
                  "Optimize application performance and reduce cloud costs"
                ].map((example, index) => (
                  <button
                    key={index}
                    onClick={() => {
                      setUserRequest(example);
                      setTimeout(() => analyzeRequest(example), 100);
                    }}
                    className="text-left p-4 bg-white/10 hover:bg-white/20 backdrop-blur-sm rounded-lg border border-white/20 text-sm text-white/90 hover:text-white transition-all hover:scale-105"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Agent Editor Dialog */}
      <Dialog open={isAgentEditorOpen} onOpenChange={setIsAgentEditorOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogTitle>Modify Agent Orchestration</DialogTitle>
          <DialogDescription>
            Customize your AI agent workflow by reordering, removing, or adding agents to the sequence.
          </DialogDescription>

          <div className="space-y-6 mt-6">
            {/* Current Agents List */}
            <div>
              <h4 className="font-semibold text-card-foreground mb-4">
                Current Agents ({editedAgents.length})
              </h4>
              <div className="space-y-2">
                {editedAgents.length === 0 ? (
                  <p className="text-muted-foreground text-sm py-8 text-center">
                    No agents selected. Add agents from the list below.
                  </p>
                ) : (
                  editedAgents.map((agent, index) => {
                    const Icon = agent.icon;
                    return (
                      <div
                        key={index}
                        className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg border border-border"
                      >
                        <div
                          className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                          style={{ backgroundColor: agent.color }}
                        >
                          <Icon className="w-5 h-5 text-white" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-xs">
                              Step {index + 1}
                            </Badge>
                            <h5 className="font-medium text-sm text-card-foreground truncate">
                              {agent.name}
                            </h5>
                          </div>
                          <p className="text-xs text-muted-foreground truncate mt-0.5">
                            {agent.description}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleMoveAgentUp(index)}
                            disabled={index === 0}
                            className="h-8 w-8 p-0"
                          >
                            <ChevronUp className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleMoveAgentDown(index)}
                            disabled={index === editedAgents.length - 1}
                            className="h-8 w-8 p-0"
                          >
                            <ChevronDown className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleRemoveAgent(index)}
                            className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            <Separator />

            {/* Add Agent Section */}
            <div>
              <h4 className="font-semibold text-card-foreground mb-4">
                Add Agent
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-96 overflow-y-auto p-1">
                {Object.entries(aiAgents).map(([key, agent]) => {
                  const Icon = agent.icon;
                  const isAlreadyAdded = editedAgents.some(a => a.name === agent.name);
                  
                  return (
                    <button
                      key={key}
                      onClick={() => !isAlreadyAdded && handleAddAgent(key)}
                      disabled={isAlreadyAdded}
                      className={`flex items-start gap-2 p-3 rounded-lg border-2 text-left transition-all ${
                        isAlreadyAdded
                          ? 'border-border bg-muted/30 opacity-50 cursor-not-allowed'
                          : 'border-border hover:border-primary/50 hover:bg-muted/50 cursor-pointer'
                      }`}
                    >
                      <div
                        className="w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5"
                        style={{ backgroundColor: agent.color }}
                      >
                        <Icon className="w-4 h-4 text-white" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h5 className="text-xs font-medium text-card-foreground truncate">
                          {agent.name}
                        </h5>
                        <p className="text-[10px] text-muted-foreground line-clamp-2 mt-0.5">
                          {agent.description}
                        </p>
                      </div>
                      {isAlreadyAdded && (
                        <CheckCircle className="w-4 h-4 text-primary flex-shrink-0" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Dialog Actions */}
            <div className="flex justify-end gap-3 pt-4 border-t border-border">
              <Button variant="outline" onClick={handleCancelAgentEdit}>
                Cancel
              </Button>
              <Button
                onClick={handleSaveAgentChanges}
                disabled={editedAgents.length === 0}
                className="bg-[#351A55] hover:bg-[#2a1444]"
              >
                <CheckCircle className="w-4 h-4 mr-2" />
                Save Changes
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* About Section */}
      <section className="py-20 bg-card">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl lg:text-4xl font-bold text-card-foreground mb-4">
              How Does WEGA Work?
            </h2>
            <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
              WEGA uses intelligent AI orchestration to analyze your software engineering tasks and automatically activate the right AI agents in the optimal sequence.
            </p>
          </div>

          <div className="grid lg:grid-cols-4 gap-8 mb-12">
            {/* Step 1 */}
            <div className="bg-card rounded-xl p-8 border border-border shadow-sm">
              <div className="w-12 h-12 rounded-full bg-[#351A55] text-white flex items-center justify-center mb-4 text-xl font-bold">
                1
              </div>
              <h3 className="text-xl font-semibold text-card-foreground mb-3">
                Describe Your Task
              </h3>
              <p className="text-muted-foreground leading-relaxed">
                Simply tell WEGA what you want to accomplish in natural language. Whether it's "create a REST API endpoint," "debug authentication issues," or "deploy to production with full testing coverage."
              </p>
            </div>

            {/* Step 2 */}
            <div className="bg-card rounded-xl p-8 border border-border shadow-sm">
              <div className="w-12 h-12 rounded-full bg-[#3498B3] text-white flex items-center justify-center mb-4 text-xl font-bold">
                2
              </div>
              <h3 className="text-xl font-semibold text-card-foreground mb-3">
                Intelligent Analysis
              </h3>
              <p className="text-muted-foreground leading-relaxed">
                WEGA's AI orchestrator analyzes your request using intelligent intent detection to understand exactly what needs to be done, selecting from 50+ specialized AI agents across the entire SDLC.
              </p>
            </div>

            {/* Step 3 */}
            <div className="bg-card rounded-xl p-8 border border-border shadow-sm">
              <div className="w-12 h-12 rounded-full bg-[#355493] text-white flex items-center justify-center mb-4 text-xl font-bold">
                3
              </div>
              <h3 className="text-xl font-semibold text-card-foreground mb-3">
                Sequential Execution
              </h3>
              <p className="text-muted-foreground leading-relaxed">
                The platform activates only the relevant agents in the proper sequence—from requirements and design through code generation, comprehensive testing, deployment, and monitoring.
              </p>
            </div>

            {/* Step 4 */}
            <div className="bg-card rounded-xl p-8 border border-border shadow-sm">
              <div className="w-12 h-12 rounded-full bg-[#746FA7] text-white flex items-center justify-center mb-4 text-xl font-bold">
                4
              </div>
              <h3 className="text-xl font-semibold text-card-foreground mb-3">
                Containerized Deployment
              </h3>
              <p className="text-muted-foreground leading-relaxed">
                The identified agents are containerized for deployment, ensuring consistent execution environments, scalability, and seamless orchestration across your infrastructure.
              </p>
            </div>
          </div>

          {/* Agent Coverage */}
          <div className="bg-gradient-to-br from-[#351A55]/5 to-[#3498B3]/5 rounded-2xl p-8 border border-border">
            <h3 className="text-2xl font-semibold text-card-foreground mb-6 text-center">
              Comprehensive AI Agent Coverage
            </h3>
            <div className="grid md:grid-cols-2 lg:grid-cols-5 gap-6">
              <div className="space-y-3">
                <h4 className="font-medium text-card-foreground flex items-center gap-2">
                  <FileText className="w-5 h-5 text-[#351A55]" />
                  Requirements & Design
                </h4>
                <ul className="text-sm text-muted-foreground space-y-1 pl-7">
                  <li>User Story Generator</li>
                  <li>System Architecture Design</li>
                  <li>Database Design</li>
                  <li>API Design</li>
                  <li>Technical Specification</li>
                </ul>
              </div>
              <div className="space-y-3">
                <h4 className="font-medium text-card-foreground flex items-center gap-2">
                  <Code className="w-5 h-5 text-[#3498B3]" />
                  Development
                </h4>
                <ul className="text-sm text-muted-foreground space-y-1 pl-7">
                  <li>Code Generation</li>
                  <li>Code Review</li>
                  <li>Debugging Agent</li>
                  <li>Refactoring Agent</li>
                  <li>Static Analysis</li>
                </ul>
              </div>
              <div className="space-y-3">
                <h4 className="font-medium text-card-foreground flex items-center gap-2">
                  <TestTube className="w-5 h-5 text-[#355493]" />
                  Testing
                </h4>
                <ul className="text-sm text-muted-foreground space-y-1 pl-7">
                  <li>Unit Testing</li>
                  <li>Integration Testing</li>
                  <li>Performance Testing</li>
                  <li>Security Testing</li>
                  <li>And 10+ more test types</li>
                </ul>
              </div>
              <div className="space-y-3">
                <h4 className="font-medium text-card-foreground flex items-center gap-2">
                  <CloudUpload className="w-5 h-5 text-[#746FA7]" />
                  Deployment & Operations
                </h4>
                <ul className="text-sm text-muted-foreground space-y-1 pl-7">
                  <li>CI/CD Pipeline</li>
                  <li>Container Orchestration</li>
                  <li>Anomaly Detection</li>
                  <li>Self-Healing</li>
                  <li>Infrastructure as Code</li>
                </ul>
              </div>
              <div className="space-y-3">
                <h4 className="font-medium text-card-foreground flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-[#BE266A]" />
                  Partner-Led
                </h4>
                <ul className="text-sm text-muted-foreground space-y-1 pl-7">
                  <li><strong className="text-[#0052CC]">Jira Rovo</strong> - AI user stories & decisions</li>
                  <li><strong className="text-[#F24E1E]">Figma</strong> - UI/UX design & prototyping</li>
                  <li><strong className="text-[#0EA5E9]">Windsurf</strong> - AI coding assistant</li>
                  <li><strong className="text-[#00ADE4]">Harness CI-CD</strong> - Modern deployments</li>
                  <li><strong className="text-[#632CA6]">Datadog</strong> - Full observability</li>
                </ul>
              </div>
            </div>
            <div className="mt-6 text-center">
              <p className="text-sm text-muted-foreground">
                <strong className="text-card-foreground">55+ specialized AI agents</strong> working together across the entire software development lifecycle
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}