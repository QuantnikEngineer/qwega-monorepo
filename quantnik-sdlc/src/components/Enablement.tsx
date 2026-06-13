import { useState, useRef, useEffect } from 'react';
import { 
  ArrowLeft, 
  BookOpen, 
  Video, 
  FileText, 
  Award,
  Users,
  Code,
  TestTube,
  CloudUpload,
  Sparkles,
  CheckCircle,
  Download,
  Rocket,
  RefreshCw,
  GitBranch,
  Maximize2,
  Bug,
  Database,
  Globe,
  Settings,
  Lock,
  Gauge,
  Grid,
  Shield,
  AlertTriangle,
  BarChart3,
  TrendingUp,
  Zap,
  Loader2
} from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Checkbox } from './ui/checkbox';
import { Separator } from './ui/separator';
import { Badge } from './ui/badge';
import { OrchestrationBuildProgress } from './OrchestrationBuildProgress';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';

interface EnablementProps {
  onBack: () => void;
  isDarkMode: boolean;
}

export function Enablement({ onBack, isDarkMode }: EnablementProps) {
  const [customerName, setCustomerName] = useState('');
  const [projectName, setProjectName] = useState('');
  const [selectedAgents, setSelectedAgents] = useState<Record<string, boolean>>({});
  const [isBuilding, setIsBuilding] = useState(false);
  const [buildProgress, setBuildProgress] = useState(0);
  const [currentBuildStep, setCurrentBuildStep] = useState('');
  const [isBuildComplete, setIsBuildComplete] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [showUIUXDialog, setShowUIUXDialog] = useState(false);
  const [uiuxSubOptions, setUiuxSubOptions] = useState({
    figma: false,
    copilot: false
  });
  const [showUserStoryDialog, setShowUserStoryDialog] = useState(false);
  const [userStorySubOptions, setUserStorySubOptions] = useState({
    copilot: false,
    gemini: false,
    jiraRovo: false
  });
  const [showCICDDialog, setShowCICDDialog] = useState(false);
  const [cicdSubOptions, setCicdSubOptions] = useState({
    harness: false,
    githubActions: false,
    gitlab: false
  });
  const [showCodeGenDialog, setShowCodeGenDialog] = useState(false);
  const [codeGenSubOptions, setCodeGenSubOptions] = useState({
    factoryAI: false,
    windsurf: false,
    gemini: false,
    amazonQ: false,
    copilot: false,
    cursor: false
  });
  const [showAnomalyDialog, setShowAnomalyDialog] = useState(false);
  const [anomalySubOptions, setAnomalySubOptions] = useState({
    datadog: false,
    dynatrace: false
  });
  const [showSelfHealingDialog, setShowSelfHealingDialog] = useState(false);
  const [selfHealingSubOptions, setSelfHealingSubOptions] = useState({
    datadog: false,
    dynatrace: false
  });

  // Add refs to track the build interval and current step
  const buildIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const buildStepIndexRef = useRef<number>(0);

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (buildIntervalRef.current) {
        clearInterval(buildIntervalRef.current);
        buildIntervalRef.current = null;
      }
    };
  }, []);

  // Comprehensive AI Agent definitions
  const aiAgents = {
    // Requirements & Design
    requirementGathering: { 
      name: 'Requirements Gathering', 
      description: 'AI-powered stakeholder interview analysis and requirement extraction',
      icon: Users,
      color: '#351A55',
      category: 'Requirements & Design'
    },
    userStoryGeneration: { 
      name: 'User Story Generation', 
      description: 'Automated user story creation from requirements',
      icon: FileText,
      color: '#746FA7',
      category: 'Requirements & Design'
    },
    jiraRovo: { 
      name: 'Jira Rovo', 
      description: 'AI-powered user story generation, documentation and decision making',
      icon: FileText,
      color: '#0052CC',
      category: 'Partner-Led'
    },
    requirementDoc: { 
      name: 'BRD Generator', 
      description: 'Business requirement document generation',
      icon: FileText,
      color: '#746FA7',
      category: 'Requirements & Design'
    },
    technicalSpec: { 
      name: 'Technical Specification', 
      description: 'Generate detailed technical specifications and architecture docs',
      icon: FileText,
      color: '#355493',
      category: 'Requirements & Design'
    },
    systemArchitecture: { 
      name: 'System Architecture Design', 
      description: 'AI-powered system architecture and design patterns',
      icon: Grid,
      color: '#351A55',
      category: 'Requirements & Design'
    },
    databaseDesign: { 
      name: 'Database Design', 
      description: 'Intelligent database schema design and optimization',
      icon: Database,
      color: '#355493',
      category: 'Requirements & Design'
    },
    apiDesign: { 
      name: 'API Design', 
      description: 'RESTful and GraphQL API design and documentation',
      icon: Globe,
      color: '#3498B3',
      category: 'Requirements & Design'
    },
    uiuxDesign: { 
      name: 'UI/UX Design', 
      description: 'User interface and experience design automation',
      icon: Maximize2,
      color: '#BE266A',
      category: 'Requirements & Design'
    },
    figma: { 
      name: 'Figma', 
      description: 'AI-powered UI/UX design creation and prototyping',
      icon: Maximize2,
      color: '#F24E1E',
      category: 'Partner-Led'
    },

    // Development & Code
    codeGeneration: { 
      name: 'Code Generation', 
      description: 'AI-powered code generation from requirements',
      icon: Code,
      color: '#351A55',
      category: 'Development'
    },
    windsurf: { 
      name: 'Windsurf', 
      description: 'AI agent for code generation, debugging and refactoring',
      icon: Code,
      color: '#0EA5E9',
      category: 'Partner-Led'
    },
    codeReview: { 
      name: 'Code Review', 
      description: 'Automated code review and quality analysis',
      icon: CheckCircle,
      color: '#3498B3',
      category: 'Development'
    },
    codeRefactoring: { 
      name: 'Code Refactoring', 
      description: 'Intelligent code refactoring and optimization',
      icon: RefreshCw,
      color: '#355493',
      category: 'Development'
    },
    codeDebugging: { 
      name: 'Code Debugging', 
      description: 'Intelligent debugging and error resolution',
      icon: Bug,
      color: '#BE266A',
      category: 'Development'
    },
    staticAnalysis: { 
      name: 'Static Code Analysis', 
      description: 'Automated static code analysis and linting',
      icon: Shield,
      color: '#746FA7',
      category: 'Development'
    },

    // Testing
    unitTesting: { 
      name: 'Unit Testing', 
      description: 'Automated unit test generation and execution',
      icon: TestTube,
      color: '#3498B3',
      category: 'Testing'
    },
    integrationTesting: { 
      name: 'Integration Testing', 
      description: 'Automated integration test creation and execution',
      icon: GitBranch,
      color: '#355493',
      category: 'Testing'
    },
    systemTesting: { 
      name: 'System Testing', 
      description: 'End-to-end system testing and validation',
      icon: Settings,
      color: '#351A55',
      category: 'Testing'
    },
    regressionTesting: { 
      name: 'Regression Testing', 
      description: 'Automated regression test suite execution',
      icon: RefreshCw,
      color: '#BE266A',
      category: 'Testing'
    },
    uatTesting: { 
      name: 'User Acceptance Testing', 
      description: 'UAT test case generation and execution support',
      icon: Users,
      color: '#746FA7',
      category: 'Testing'
    },
    performanceTesting: { 
      name: 'Performance Testing', 
      description: 'Load, stress, and performance testing automation',
      icon: Gauge,
      color: '#3498B3',
      category: 'Testing'
    },
    securityTesting: { 
      name: 'Security Testing', 
      description: 'Security vulnerability scanning and penetration testing',
      icon: Lock,
      color: '#BE266A',
      category: 'Testing'
    },
    testDataGeneration: { 
      name: 'Test Data Generation', 
      description: 'Intelligent test data creation and management',
      icon: Database,
      color: '#355493',
      category: 'Testing'
    },

    // Deployment & Release
    cicdPipeline: { 
      name: 'CI/CD Pipeline Setup', 
      description: 'Automated CI/CD pipeline configuration',
      icon: GitBranch,
      color: '#351A55',
      category: 'Deployment & Operations'
    },
    harnessCICD: { 
      name: 'Harness CI-CD', 
      description: 'Modern CI/CD platform for automated deployments and releases',
      icon: Rocket,
      color: '#00ADE4',
      category: 'Partner-Led'
    },
    deployment: { 
      name: 'Production Deployment', 
      description: 'Automated deployment orchestration',
      icon: CloudUpload,
      color: '#3498B3',
      category: 'Deployment & Operations'
    },
    rollback: { 
      name: 'Automated Rollback', 
      description: 'Intelligent rollback and recovery mechanisms',
      icon: RefreshCw,
      color: '#BE266A',
      category: 'Deployment & Operations'
    },
    releaseManagement: { 
      name: 'Release Management', 
      description: 'Release planning and version management',
      icon: Rocket,
      color: '#355493',
      category: 'Deployment & Operations'
    },

    // Infrastructure & DevOps
    infrastructureProvisioning: { 
      name: 'Infrastructure Provisioning', 
      description: 'Automated infrastructure as code deployment',
      icon: CloudUpload,
      color: '#3498B3',
      category: 'Deployment & Operations'
    },
    containerization: { 
      name: 'Containerization', 
      description: 'Docker and container orchestration',
      icon: Grid,
      color: '#355493',
      category: 'Deployment & Operations'
    },
    configManagement: { 
      name: 'Configuration Management', 
      description: 'Automated configuration management and version control',
      icon: Settings,
      color: '#746FA7',
      category: 'Deployment & Operations'
    },

    // Monitoring & Operations
    monitoring: { 
      name: 'Application Monitoring', 
      description: 'Real-time application performance monitoring',
      icon: BarChart3,
      color: '#3498B3',
      category: 'Deployment & Operations'
    },
    datadog: { 
      name: 'Datadog', 
      description: 'Comprehensive monitoring and observability platform',
      icon: BarChart3,
      color: '#632CA6',
      category: 'Partner-Led'
    },
    logging: { 
      name: 'Log Management', 
      description: 'Centralized logging and log analysis',
      icon: FileText,
      color: '#355493',
      category: 'Deployment & Operations'
    },
    anomalyDetection: { 
      name: 'Anomaly Detection', 
      description: 'Real-time anomaly detection and alerting',
      icon: AlertTriangle,
      color: '#BE266A',
      category: 'Deployment & Operations'
    },
    alerting: { 
      name: 'Alert Management', 
      description: 'Intelligent alerting and notification system',
      icon: AlertTriangle,
      color: '#BE266A',
      category: 'Deployment & Operations'
    },
    selfHealing: { 
      name: 'Self Healing', 
      description: 'Automated issue resolution and recovery',
      icon: RefreshCw,
      color: '#355493',
      category: 'Deployment & Operations'
    },

    // Security & Compliance
    vulnerabilityScanning: { 
      name: 'Vulnerability Scanning', 
      description: 'Automated security vulnerability detection',
      icon: Shield,
      color: '#BE266A',
      category: 'Security & Compliance'
    },
    complianceCheck: { 
      name: 'Compliance Validation', 
      description: 'Automated compliance checking and reporting',
      icon: CheckCircle,
      color: '#746FA7',
      category: 'Security & Compliance'
    },
    secretsManagement: { 
      name: 'Secrets Management', 
      description: 'Secure secrets and credentials management',
      icon: Lock,
      color: '#351A55',
      category: 'Security & Compliance'
    },

    // Performance & Optimization
    performanceOptimization: { 
      name: 'Performance Optimization', 
      description: 'AI-powered performance tuning and optimization',
      icon: Zap,
      color: '#3498B3',
      category: 'Performance & Optimization'
    },
    codeProfiler: { 
      name: 'Code Profiling', 
      description: 'Application profiling and bottleneck detection',
      icon: Gauge,
      color: '#355493',
      category: 'Performance & Optimization'
    },
    costOptimization: { 
      name: 'Cost Optimization', 
      description: 'Cloud cost analysis and optimization',
      icon: TrendingUp,
      color: '#746FA7',
      category: 'Performance & Optimization'
    },

    // Documentation
    apiDocumentation: { 
      name: 'API Documentation', 
      description: 'Automated API documentation generation',
      icon: FileText,
      color: '#3498B3',
      category: 'Documentation'
    },
    technicalDocumentation: { 
      name: 'Technical Documentation', 
      description: 'Automated technical documentation creation',
      icon: FileText,
      color: '#355493',
      category: 'Documentation'
    },
    userManual: { 
      name: 'User Manual Generation', 
      description: 'End-user documentation and help guides',
      icon: Users,
      color: '#746FA7',
      category: 'Documentation'
    }
  };

  // Group agents by category (exclude Partner-Led from display)
  const categories = [
    'Requirements & Design',
    'Development',
    'Testing',
    'Deployment & Operations',
    'Security & Compliance',
    'Performance & Optimization',
    'Documentation'
  ];

  const getAgentsByCategory = (category: string) => {
    return Object.entries(aiAgents)
      .filter(([key, agent]) => {
        // Exclude jiraRovo from main display - it's only in User Story Generation dialog
        if (key === 'jiraRovo') return false;
        return agent.category === category;
      })
      .map(([key, agent]) => ({ key, ...agent }));
  };

  const handleToggleAgent = (agentKey: string) => {
    // Special handling for UI/UX Design agent
    if (agentKey === 'uiuxDesign') {
      setShowUIUXDialog(true);
      return;
    }
    
    // Special handling for User Story Generation agent
    if (agentKey === 'userStoryGeneration') {
      setShowUserStoryDialog(true);
      return;
    }
    
    // Special handling for CI/CD Pipeline agent
    if (agentKey === 'cicdPipeline') {
      setShowCICDDialog(true);
      return;
    }
    
    // Special handling for Code Generation agent
    if (agentKey === 'codeGeneration') {
      setShowCodeGenDialog(true);
      return;
    }
    
    // Special handling for Anomaly Detection agent
    if (agentKey === 'anomalyDetection') {
      setShowAnomalyDialog(true);
      return;
    }
    
    // Special handling for Self Healing agent
    if (agentKey === 'selfHealing') {
      setShowSelfHealingDialog(true);
      return;
    }
    
    setSelectedAgents(prev => ({
      ...prev,
      [agentKey]: !prev[agentKey]
    }));
  };

  const handleUIUXDialogConfirm = () => {
    // Update selection based on dialog choices
    if (uiuxSubOptions.figma || uiuxSubOptions.copilot) {
      setSelectedAgents(prev => ({
        ...prev,
        uiuxDesign: true,
        ...(uiuxSubOptions.figma ? { uiuxDesignFigma: true } : {}),
        ...(uiuxSubOptions.copilot ? { uiuxDesignCopilot: true } : {})
      }));
    } else {
      setSelectedAgents(prev => ({
        ...prev,
        uiuxDesign: false,
        uiuxDesignFigma: false,
        uiuxDesignCopilot: false
      }));
    }
    setShowUIUXDialog(false);
  };

  const handleUIUXDialogCancel = () => {
    setShowUIUXDialog(false);
  };

  const handleUserStoryDialogConfirm = () => {
    // Update selection based on dialog choices
    if (userStorySubOptions.copilot || userStorySubOptions.gemini || userStorySubOptions.jiraRovo) {
      setSelectedAgents(prev => ({
        ...prev,
        userStoryGeneration: true,
        ...(userStorySubOptions.copilot ? { userStoryGenerationCopilot: true } : {}),
        ...(userStorySubOptions.gemini ? { userStoryGenerationGemini: true } : {}),
        ...(userStorySubOptions.jiraRovo ? { userStoryGenerationJiraRovo: true } : {})
      }));
    } else {
      setSelectedAgents(prev => ({
        ...prev,
        userStoryGeneration: false,
        userStoryGenerationCopilot: false,
        userStoryGenerationGemini: false,
        userStoryGenerationJiraRovo: false
      }));
    }
    setShowUserStoryDialog(false);
  };

  const handleUserStoryDialogCancel = () => {
    setShowUserStoryDialog(false);
  };

  const handleCICDDialogConfirm = () => {
    if (cicdSubOptions.harness || cicdSubOptions.githubActions || cicdSubOptions.gitlab) {
      setSelectedAgents(prev => ({
        ...prev,
        cicdPipeline: true,
        ...(cicdSubOptions.harness ? { cicdPipelineHarness: true } : {}),
        ...(cicdSubOptions.githubActions ? { cicdPipelineGithubActions: true } : {}),
        ...(cicdSubOptions.gitlab ? { cicdPipelineGitlab: true } : {})
      }));
    } else {
      setSelectedAgents(prev => ({
        ...prev,
        cicdPipeline: false,
        cicdPipelineHarness: false,
        cicdPipelineGithubActions: false,
        cicdPipelineGitlab: false
      }));
    }
    setShowCICDDialog(false);
  };

  const handleCICDDialogCancel = () => {
    setShowCICDDialog(false);
  };

  const handleCodeGenDialogConfirm = () => {
    if (codeGenSubOptions.factoryAI || codeGenSubOptions.windsurf || codeGenSubOptions.gemini || 
        codeGenSubOptions.amazonQ || codeGenSubOptions.copilot || codeGenSubOptions.cursor) {
      setSelectedAgents(prev => ({
        ...prev,
        codeGeneration: true,
        ...(codeGenSubOptions.factoryAI ? { codeGenerationFactoryAI: true } : {}),
        ...(codeGenSubOptions.windsurf ? { codeGenerationWindsurf: true } : {}),
        ...(codeGenSubOptions.gemini ? { codeGenerationGemini: true } : {}),
        ...(codeGenSubOptions.amazonQ ? { codeGenerationAmazonQ: true } : {}),
        ...(codeGenSubOptions.copilot ? { codeGenerationCopilot: true } : {}),
        ...(codeGenSubOptions.cursor ? { codeGenerationCursor: true } : {})
      }));
    } else {
      setSelectedAgents(prev => ({
        ...prev,
        codeGeneration: false,
        codeGenerationFactoryAI: false,
        codeGenerationWindsurf: false,
        codeGenerationGemini: false,
        codeGenerationAmazonQ: false,
        codeGenerationCopilot: false,
        codeGenerationCursor: false
      }));
    }
    setShowCodeGenDialog(false);
  };

  const handleCodeGenDialogCancel = () => {
    setShowCodeGenDialog(false);
  };

  const handleAnomalyDialogConfirm = () => {
    if (anomalySubOptions.datadog || anomalySubOptions.dynatrace) {
      setSelectedAgents(prev => ({
        ...prev,
        anomalyDetection: true,
        ...(anomalySubOptions.datadog ? { anomalyDetectionDatadog: true } : {}),
        ...(anomalySubOptions.dynatrace ? { anomalyDetectionDynatrace: true } : {})
      }));
    } else {
      setSelectedAgents(prev => ({
        ...prev,
        anomalyDetection: false,
        anomalyDetectionDatadog: false,
        anomalyDetectionDynatrace: false
      }));
    }
    setShowAnomalyDialog(false);
  };

  const handleAnomalyDialogCancel = () => {
    setShowAnomalyDialog(false);
  };

  const handleSelfHealingDialogConfirm = () => {
    if (selfHealingSubOptions.datadog || selfHealingSubOptions.dynatrace) {
      setSelectedAgents(prev => ({
        ...prev,
        selfHealing: true,
        ...(selfHealingSubOptions.datadog ? { selfHealingDatadog: true } : {}),
        ...(selfHealingSubOptions.dynatrace ? { selfHealingDynatrace: true } : {})
      }));
    } else {
      setSelectedAgents(prev => ({
        ...prev,
        selfHealing: false,
        selfHealingDatadog: false,
        selfHealingDynatrace: false
      }));
    }
    setShowSelfHealingDialog(false);
  };

  const handleSelfHealingDialogCancel = () => {
    setShowSelfHealingDialog(false);
  };

  const handleSelectAll = () => {
    const allSelected = Object.keys(aiAgents).reduce((acc, key) => {
      acc[key] = true;
      return acc;
    }, {} as Record<string, boolean>);
    setSelectedAgents(allSelected);
  };

  const handleDeselectAll = () => {
    setSelectedAgents({});
  };

  const handleBuildAutomatically = () => {
    // Clear any existing interval first
    if (buildIntervalRef.current) {
      clearInterval(buildIntervalRef.current);
      buildIntervalRef.current = null;
    }

    // Reset the step index
    buildStepIndexRef.current = 0;

    setIsBuilding(true);
    setBuildProgress(0);
    setIsBuildComplete(false);
    setCurrentBuildStep('');
    
    toast.info('Starting orchestration build...', {
      description: 'Building your AI agent network',
    });
    
    // Scroll to show the build progress
    setTimeout(() => {
      window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    }, 100);
    
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
    
    const totalSteps = buildSteps.length;
    const stepDuration = 800;
    
    // Use ref-based approach for reliable interval execution
    const runNextStep = () => {
      const currentIndex = buildStepIndexRef.current;
      
      if (currentIndex < totalSteps) {
        setCurrentBuildStep(buildSteps[currentIndex]);
        setBuildProgress(((currentIndex + 1) / totalSteps) * 100);
        buildStepIndexRef.current = currentIndex + 1;
      } else {
        // Clear the interval when done
        if (buildIntervalRef.current) {
          clearInterval(buildIntervalRef.current);
          buildIntervalRef.current = null;
        }
        setIsBuildComplete(true);
        setIsBuilding(false);
        toast.success('Orchestration Complete!', {
          description: 'Your AI agent network is ready to use',
        });
      }
    };
    
    // Start the interval and store the reference
    buildIntervalRef.current = setInterval(runNextStep, stepDuration);
  };

  const handleDownloadContainer = () => {
    setIsDownloading(true);
    // Create configuration object
    const config = {
      customer: customerName,
      project: projectName,
      agents: Object.entries(selectedAgents)
        .filter(([_, enabled]) => enabled)
        .map(([key]) => aiAgents[key as keyof typeof aiAgents]),
      timestamp: new Date().toISOString()
    };

    // Convert to JSON and create download
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `quantnik-config-${projectName.replace(/\s+/g, '-').toLowerCase()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setIsDownloading(false);
    toast.success('Configuration file downloaded successfully!');
  };

  const handleReset = () => {
    // Clear any running build interval
    if (buildIntervalRef.current) {
      clearInterval(buildIntervalRef.current);
      buildIntervalRef.current = null;
    }
    
    // Reset the step index
    buildStepIndexRef.current = 0;
    
    setIsResetting(true);
    setCustomerName('');
    setProjectName('');
    setSelectedAgents({});
    setIsBuilding(false);
    setBuildProgress(0);
    setCurrentBuildStep('');
    setIsBuildComplete(false);
    setIsResetting(false);
  };

  const selectedCount = Object.values(selectedAgents).filter(Boolean).length;
  const isFormValid = customerName.trim() && projectName.trim() && selectedCount > 0;

  const selectedAgentsList = Object.entries(selectedAgents)
    .filter(([_, enabled]) => enabled)
    .map(([key]) => aiAgents[key as keyof typeof aiAgents])
    .filter(agent => agent !== undefined); // Filter out undefined agents (sub-options that don't exist in aiAgents)

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-800">
      {/* Decorative background elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-[#3498B3]/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-[#351A55]/10 rounded-full blur-3xl" />
      </div>
      
      <div className="relative max-w-7xl mx-auto px-6 py-8">
        {/* Back Button */}
        <Button
          variant="ghost"
          onClick={onBack}
          className="mb-6 text-foreground hover:text-[#3498B3] hover:bg-[#3498B3]/10"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Home
        </Button>

        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-foreground mb-4 bg-gradient-to-r from-[#351A55] to-[#3498B3] bg-clip-text text-transparent">AI Agent Enablement</h1>
          <p className="text-muted-foreground max-w-3xl mx-auto">
            Configure and enable AI agents for your project. Select the agents you need and choose how to deploy them.
          </p>
        </div>

        {/* Customer and Project Information */}
        <Card className="p-6 mb-8 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm border-2 border-[#3498B3]/20 shadow-lg hover:shadow-xl transition-shadow">
          <h2 className="text-foreground mb-6 flex items-center gap-2">
            <Settings className="w-5 h-5 text-[#351A55]" />
            Project Configuration
          </h2>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="customerName">Customer Name *</Label>
              <Input
                id="customerName"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="Enter customer name"
                className="bg-white dark:bg-slate-800 border-[#3498B3]/30 focus:border-[#3498B3]"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="projectName">Project Name *</Label>
              <Input
                id="projectName"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="Enter project name"
                className="bg-white dark:bg-slate-800 border-[#3498B3]/30 focus:border-[#3498B3]"
              />
            </div>
          </div>
        </Card>

        {/* AI Agent Selection */}
        <Card className="p-6 mb-8 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm border-2 border-[#355493]/20 shadow-lg hover:shadow-xl transition-shadow">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-foreground mb-2 flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-[#3498B3]" />
                Select AI Agents
              </h2>
              <p className="text-sm text-muted-foreground">
                <Badge variant="secondary" className="bg-[#3498B3]/10 text-[#3498B3] border-[#3498B3]/30">
                  {selectedCount} agent{selectedCount !== 1 ? 's' : ''} selected
                </Badge>
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleSelectAll} className="hover:bg-[#3498B3]/10 hover:border-[#3498B3] hover:text-[#3498B3]">
                Select All
              </Button>
              <Button variant="outline" size="sm" onClick={handleDeselectAll} className="hover:bg-[#BE266A]/10 hover:border-[#BE266A] hover:text-[#BE266A]">
                Deselect All
              </Button>
            </div>
          </div>

          <Separator className="mb-6 bg-gradient-to-r from-transparent via-[#3498B3]/30 to-transparent" />

          {/* Agent Categories */}
          <div className="space-y-8">
            {categories.map((category) => {
              const agents = getAgentsByCategory(category);
              if (agents.length === 0) return null;

              return (
                <div key={category}>
                  <h3 className="text-foreground mb-4 flex items-center gap-2">
                    {category === 'Requirements & Design' && <FileText className="w-5 h-5 text-[#351A55]" />}
                    {category === 'Development' && <Code className="w-5 h-5 text-[#3498B3]" />}
                    {category === 'Testing' && <TestTube className="w-5 h-5 text-[#355493]" />}
                    {category === 'Deployment & Operations' && <CloudUpload className="w-5 h-5 text-[#746FA7]" />}
                    {category === 'Security & Compliance' && <Shield className="w-5 h-5 text-[#BE266A]" />}
                    {category === 'Performance & Optimization' && <Zap className="w-5 h-5 text-[#3498B3]" />}
                    {category === 'Documentation' && <FileText className="w-5 h-5 text-[#355493]" />}
                    {category}
                  </h3>
                  <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {agents.map((agent) => {
                      const Icon = agent.icon;
                      const isSelected = selectedAgents[agent.key];

                      return (
                        <div
                          key={agent.key}
                          onClick={() => handleToggleAgent(agent.key)}
                          className={`flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all hover:shadow-md bg-white dark:bg-slate-800/50 ${
                            isSelected
                              ? 'border-[#3498B3] bg-gradient-to-br from-[#3498B3]/10 to-[#3498B3]/5 shadow-md'
                              : 'border-slate-200 dark:border-slate-700 hover:border-[#3498B3]/50'
                          }`}
                        >
                          <Checkbox
                            checked={!!isSelected}
                            onCheckedChange={() => handleToggleAgent(agent.key)}
                            className="mt-1"
                          />
                          <div
                            className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 shadow-sm"
                            style={{ backgroundColor: agent.color }}
                          >
                            <Icon className="w-5 h-5 text-white" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <h4 className="text-sm font-medium text-card-foreground mb-1">
                              {agent.name}
                            </h4>
                            <p className="text-xs text-muted-foreground line-clamp-2">
                              {agent.description}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Action Buttons */}
        {!isBuilding && !isBuildComplete && (
          <Card className="p-6 bg-gradient-to-br from-white to-slate-50 dark:from-slate-900 dark:to-slate-800 backdrop-blur-sm border-2 border-[#746FA7]/20 shadow-lg">
            <h2 className="text-foreground mb-6 flex items-center gap-2">
              <Rocket className="w-5 h-5 text-[#351A55]" />
              Deployment Options
            </h2>
            <div className="grid md:grid-cols-3 gap-4">
              <Button
                size="lg"
                onClick={handleBuildAutomatically}
                disabled={!isFormValid}
                className="bg-gradient-to-r from-[#351A55] to-[#3498B3] hover:from-[#2a1444] hover:to-[#2a7a9e] text-white h-auto py-6 flex-col gap-2 shadow-lg hover:shadow-xl transition-all"
              >
                <Rocket className="w-6 h-6" />
                <div>
                  <div className="font-semibold">Build Automatically</div>
                  <div className="text-xs opacity-90">Start orchestration now</div>
                </div>
              </Button>
              <Button
                size="lg"
                variant="outline"
                onClick={handleDownloadContainer}
                disabled={!isFormValid}
                className="h-auto py-6 flex-col gap-2 bg-white dark:bg-slate-800 border-2 hover:bg-[#3498B3] hover:text-white hover:border-[#3498B3] hover:shadow-lg transition-all"
              >
                {isDownloading ? (
                  <Loader2 className="w-6 h-6 animate-spin" />
                ) : (
                  <Download className="w-6 h-6" />
                )}
                <div>
                  <div className="font-semibold">Download Container</div>
                  <div className="text-xs opacity-90">Get configuration file</div>
                </div>
              </Button>
              <Button
                size="lg"
                variant="outline"
                onClick={handleReset}
                className="h-auto py-6 flex-col gap-2 bg-white dark:bg-slate-800 border-2 hover:bg-[#BE266A] hover:text-white hover:border-[#BE266A] hover:shadow-lg transition-all"
              >
                {isResetting ? (
                  <Loader2 className="w-6 h-6 animate-spin" />
                ) : (
                  <RefreshCw className="w-6 h-6" />
                )}
                <div>
                  <div className="font-semibold">Reset</div>
                  <div className="text-xs opacity-90">Start over</div>
                </div>
              </Button>
            </div>
            {!isFormValid && (
              <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900 rounded-lg">
                <p className="text-sm text-amber-800 dark:text-amber-400 text-center">
                  ⚠️ Please fill in customer name, project name, and select at least one AI agent to continue.
                </p>
              </div>
            )}
          </Card>
        )}

        {/* Build Progress Display */}
        {(isBuilding || isBuildComplete) && (
          <OrchestrationBuildProgress
            isBuilding={isBuilding}
            isBuildComplete={isBuildComplete}
            buildProgress={buildProgress}
            currentBuildStep={currentBuildStep}
            agents={selectedAgentsList}
            onComplete={() => {
              setIsBuildComplete(false);
              handleReset();
            }}
            onViewDetails={() => {
              setIsBuildComplete(false);
              setBuildProgress(0);
              setCurrentBuildStep('');
            }}
            onDownloadContainer={handleDownloadContainer}
          />
        )}
      </div>

      {/* UI/UX Design Dialog */}
      <Dialog open={showUIUXDialog} onOpenChange={setShowUIUXDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>UI/UX Design Options</DialogTitle>
            <DialogDescription>
              Choose the tools you want to use for UI/UX design. You can select one or both.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setUiuxSubOptions(prev => ({ ...prev, figma: !prev.figma }))}>
              <Checkbox
                id="figma"
                checked={uiuxSubOptions.figma}
                onCheckedChange={(checked) => setUiuxSubOptions(prev => ({ ...prev, figma: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="figma" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Maximize2 className="w-4 h-4 text-[#F24E1E]" />
                    <span>Figma</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    AI-powered UI/UX design creation and prototyping
                  </p>
                </Label>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setUiuxSubOptions(prev => ({ ...prev, copilot: !prev.copilot }))}>
              <Checkbox
                id="copilot"
                checked={uiuxSubOptions.copilot}
                onCheckedChange={(checked) => setUiuxSubOptions(prev => ({ ...prev, copilot: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="copilot" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-[#BE266A]" />
                    <span>Co-pilot</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    AI assistant for design guidance and automation
                  </p>
                </Label>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={handleUIUXDialogCancel}
            >
              Cancel
            </Button>
            <Button
              onClick={handleUIUXDialogConfirm}
              className="bg-[#3498B3] hover:bg-[#2980a1]"
            >
              Confirm
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* User Story Generation Dialog */}
      <Dialog open={showUserStoryDialog} onOpenChange={setShowUserStoryDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>User Story Generation Options</DialogTitle>
            <DialogDescription>
              Choose the tools you want to use for user story generation. You can select one or more.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setUserStorySubOptions(prev => ({ ...prev, copilot: !prev.copilot }))}>
              <Checkbox
                id="userstory-copilot"
                checked={userStorySubOptions.copilot}
                onCheckedChange={(checked) => setUserStorySubOptions(prev => ({ ...prev, copilot: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="userstory-copilot" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-[#BE266A]" />
                    <span>Co-pilot</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    AI assistant for user story generation and documentation
                  </p>
                </Label>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setUserStorySubOptions(prev => ({ ...prev, gemini: !prev.gemini }))}>
              <Checkbox
                id="userstory-gemini"
                checked={userStorySubOptions.gemini}
                onCheckedChange={(checked) => setUserStorySubOptions(prev => ({ ...prev, gemini: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="userstory-gemini" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-[#BE266A]" />
                    <span>Gemini</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Google's AI assistant for user story generation and documentation
                  </p>
                </Label>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setUserStorySubOptions(prev => ({ ...prev, jiraRovo: !prev.jiraRovo }))}>
              <Checkbox
                id="userstory-jiraRovo"
                checked={userStorySubOptions.jiraRovo}
                onCheckedChange={(checked) => setUserStorySubOptions(prev => ({ ...prev, jiraRovo: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="userstory-jiraRovo" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-[#0052CC]" />
                    <span>Jira Rovo</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Jira's AI for user stories, documentation, and decision making
                  </p>
                </Label>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={handleUserStoryDialogCancel}
            >
              Cancel
            </Button>
            <Button
              onClick={handleUserStoryDialogConfirm}
              className="bg-[#3498B3] hover:bg-[#2980a1]"
            >
              Confirm
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* CI/CD Pipeline Dialog */}
      <Dialog open={showCICDDialog} onOpenChange={setShowCICDDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>CI/CD Pipeline Options</DialogTitle>
            <DialogDescription>
              Choose the CI/CD tools you want to use. You can select one or more.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setCicdSubOptions(prev => ({ ...prev, harness: !prev.harness }))}>
              <Checkbox
                id="cicd-harness"
                checked={cicdSubOptions.harness}
                onCheckedChange={(checked) => setCicdSubOptions(prev => ({ ...prev, harness: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="cicd-harness" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Rocket className="w-4 h-4 text-[#00ADE4]" />
                    <span>Harness CI-CD</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Modern CI/CD platform for automated deployments and releases
                  </p>
                </Label>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setCicdSubOptions(prev => ({ ...prev, githubActions: !prev.githubActions }))}>
              <Checkbox
                id="cicd-githubActions"
                checked={cicdSubOptions.githubActions}
                onCheckedChange={(checked) => setCicdSubOptions(prev => ({ ...prev, githubActions: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="cicd-githubActions" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <GitBranch className="w-4 h-4 text-[#351A55]" />
                    <span>GitHub Actions</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Automate your build, test, and deployment workflows
                  </p>
                </Label>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setCicdSubOptions(prev => ({ ...prev, gitlab: !prev.gitlab }))}>
              <Checkbox
                id="cicd-gitlab"
                checked={cicdSubOptions.gitlab}
                onCheckedChange={(checked) => setCicdSubOptions(prev => ({ ...prev, gitlab: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="cicd-gitlab" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <GitBranch className="w-4 h-4 text-[#351A55]" />
                    <span>GitLab CI/CD</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Automate your build, test, and deployment workflows
                  </p>
                </Label>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={handleCICDDialogCancel}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCICDDialogConfirm}
              className="bg-[#3498B3] hover:bg-[#2980a1]"
            >
              Confirm
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Code Generation Dialog */}
      <Dialog open={showCodeGenDialog} onOpenChange={setShowCodeGenDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Code Generation Options</DialogTitle>
            <DialogDescription>
              Choose the code generation tools you want to use. You can select one or more.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setCodeGenSubOptions(prev => ({ ...prev, factoryAI: !prev.factoryAI }))}>
              <Checkbox
                id="codegen-factoryAI"
                checked={codeGenSubOptions.factoryAI}
                onCheckedChange={(checked) => setCodeGenSubOptions(prev => ({ ...prev, factoryAI: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="codegen-factoryAI" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Code className="w-4 h-4 text-[#351A55]" />
                    <span>Factory AI</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    AI-powered code generation from requirements
                  </p>
                </Label>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setCodeGenSubOptions(prev => ({ ...prev, windsurf: !prev.windsurf }))}>
              <Checkbox
                id="codegen-windsurf"
                checked={codeGenSubOptions.windsurf}
                onCheckedChange={(checked) => setCodeGenSubOptions(prev => ({ ...prev, windsurf: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="codegen-windsurf" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Code className="w-4 h-4 text-[#0EA5E9]" />
                    <span>Windsurf</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    AI agent for code generation, debugging and refactoring
                  </p>
                </Label>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setCodeGenSubOptions(prev => ({ ...prev, gemini: !prev.gemini }))}>
              <Checkbox
                id="codegen-gemini"
                checked={codeGenSubOptions.gemini}
                onCheckedChange={(checked) => setCodeGenSubOptions(prev => ({ ...prev, gemini: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="codegen-gemini" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-[#BE266A]" />
                    <span>Gemini</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Google's AI assistant for code generation and documentation
                  </p>
                </Label>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setCodeGenSubOptions(prev => ({ ...prev, amazonQ: !prev.amazonQ }))}>
              <Checkbox
                id="codegen-amazonQ"
                checked={codeGenSubOptions.amazonQ}
                onCheckedChange={(checked) => setCodeGenSubOptions(prev => ({ ...prev, amazonQ: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="codegen-amazonQ" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-[#BE266A]" />
                    <span>Amazon Q</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Amazon's AI assistant for code generation and documentation
                  </p>
                </Label>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setCodeGenSubOptions(prev => ({ ...prev, copilot: !prev.copilot }))}>
              <Checkbox
                id="codegen-copilot"
                checked={codeGenSubOptions.copilot}
                onCheckedChange={(checked) => setCodeGenSubOptions(prev => ({ ...prev, copilot: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="codegen-copilot" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-[#BE266A]" />
                    <span>Co-pilot</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    AI assistant for code generation and documentation
                  </p>
                </Label>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setCodeGenSubOptions(prev => ({ ...prev, cursor: !prev.cursor }))}>
              <Checkbox
                id="codegen-cursor"
                checked={codeGenSubOptions.cursor}
                onCheckedChange={(checked) => setCodeGenSubOptions(prev => ({ ...prev, cursor: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="codegen-cursor" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-[#BE266A]" />
                    <span>Cursor</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    AI assistant for code generation and documentation
                  </p>
                </Label>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={handleCodeGenDialogCancel}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCodeGenDialogConfirm}
              className="bg-[#3498B3] hover:bg-[#2980a1]"
            >
              Confirm
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Anomaly Detection Dialog */}
      <Dialog open={showAnomalyDialog} onOpenChange={setShowAnomalyDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Anomaly Detection Options</DialogTitle>
            <DialogDescription>
              Choose the anomaly detection tools you want to use. You can select one or more.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setAnomalySubOptions(prev => ({ ...prev, datadog: !prev.datadog }))}>
              <Checkbox
                id="anomaly-datadog"
                checked={anomalySubOptions.datadog}
                onCheckedChange={(checked) => setAnomalySubOptions(prev => ({ ...prev, datadog: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="anomaly-datadog" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-[#632CA6]" />
                    <span>Datadog</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Comprehensive monitoring and observability platform
                  </p>
                </Label>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setAnomalySubOptions(prev => ({ ...prev, dynatrace: !prev.dynatrace }))}>
              <Checkbox
                id="anomaly-dynatrace"
                checked={anomalySubOptions.dynatrace}
                onCheckedChange={(checked) => setAnomalySubOptions(prev => ({ ...prev, dynatrace: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="anomaly-dynatrace" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-[#BE266A]" />
                    <span>Dynatrace</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Real-time anomaly detection and alerting
                  </p>
                </Label>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={handleAnomalyDialogCancel}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAnomalyDialogConfirm}
              className="bg-[#3498B3] hover:bg-[#2980a1]"
            >
              Confirm
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Self Healing Dialog */}
      <Dialog open={showSelfHealingDialog} onOpenChange={setShowSelfHealingDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Self Healing Options</DialogTitle>
            <DialogDescription>
              Choose the self healing tools you want to use. You can select one or more.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setSelfHealingSubOptions(prev => ({ ...prev, datadog: !prev.datadog }))}>
              <Checkbox
                id="selfhealing-datadog"
                checked={selfHealingSubOptions.datadog}
                onCheckedChange={(checked) => setSelfHealingSubOptions(prev => ({ ...prev, datadog: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="selfhealing-datadog" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-[#632CA6]" />
                    <span>Datadog</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Comprehensive monitoring and observability platform
                  </p>
                </Label>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 border rounded-lg hover:bg-accent cursor-pointer" onClick={() => setSelfHealingSubOptions(prev => ({ ...prev, dynatrace: !prev.dynatrace }))}>
              <Checkbox
                id="selfhealing-dynatrace"
                checked={selfHealingSubOptions.dynatrace}
                onCheckedChange={(checked) => setSelfHealingSubOptions(prev => ({ ...prev, dynatrace: checked as boolean }))}
              />
              <div className="flex-1">
                <Label htmlFor="selfhealing-dynatrace" className="cursor-pointer">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-[#BE266A]" />
                    <span>Dynatrace</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Real-time anomaly detection and alerting
                  </p>
                </Label>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={handleSelfHealingDialogCancel}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSelfHealingDialogConfirm}
              className="bg-[#3498B3] hover:bg-[#2980a1]"
            >
              Confirm
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}