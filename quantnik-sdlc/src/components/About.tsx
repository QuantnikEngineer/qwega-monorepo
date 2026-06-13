import { 
  ArrowLeft, 
  Sparkles, 
  Zap, 
  Shield, 
  Brain,
  Code,
  Network,
  TrendingUp,
  CheckCircle,
  Target,
  Users,
  Award,
  Rocket,
  ArrowRight,
  Play,
  Maximize2
} from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogTitle, 
  DialogTrigger 
} from './ui/dialog';
import { useState } from 'react';
import { motion } from 'motion/react';
import { ImageWithFallback } from './figma/ImageWithFallback';
import quantnikFrameworkImage from 'figma:asset/8d22fc96f13915bddaccf1f591d30c4d310c1e04.png';
import buildIqLayersImage from 'figma:asset/775ed2e43cc13e184ec6cb74e5db1bbe12bad9b6.png';
import mcpCatalogGrid from 'figma:asset/c53cae069fb3afd2b24f3c01b327f0f6e0b32781.png';
import assetsPartnershipsGrid from 'figma:asset/89f866b414d95f8203a3b29a5d7043068be4982f.png';

type Status = 'available' | 'inProgress' | 'comingSoon' | 'implementation';

interface Item {
  text: string;
  status: Status;
  tooltip: string;
  hasArrow?: boolean;
}

interface Phase {
  name: string;
  items: Item[];
  tooltip?: string;
}

interface AboutProps {
  onBack: () => void;
  isDarkMode: boolean;
}

export function About({ onBack, isDarkMode }: AboutProps) {
  const features = [
    {
      icon: Brain,
      title: 'AI-Powered Intelligence',
      description: 'Multiple specialized AI agents working in harmony to handle every aspect of software engineering.',
      color: '#351A55'
    },
    {
      icon: Code,
      title: 'Complete SDLC Coverage',
      description: 'From requirements gathering to deployment, QUANTNIK covers the entire software development lifecycle.',
      color: '#3498B3'
    },
    {
      icon: Zap,
      title: 'Autonomous Operations',
      description: 'Configure autonomy levels from Human-in-the-Loop to fully autonomous operations.',
      color: '#355493'
    },
    {
      icon: Shield,
      title: 'Enterprise-Grade Security',
      description: 'Built-in security scanning, compliance validation, and secrets management.',
      color: '#BE266A'
    },
    {
      icon: Network,
      title: 'Seamless Integrations',
      description: 'Native integration with popular tools like GitHub, GitLab, Jira, Harness, and more.',
      color: '#746FA7'
    },
    {
      icon: TrendingUp,
      title: 'Continuous Optimization',
      description: 'AI-driven performance tuning, cost optimization, and self-healing capabilities.',
      color: '#3498B3'
    }
  ];

  const capabilities = [
    'Code Generation & Refactoring',
    'Automated Testing & Quality Assurance',
    'CI/CD Pipeline Management',
    'Anomaly Detection & Monitoring',
    'Self-Healing Infrastructure',
    'Security Vulnerability Scanning',
    'Performance Optimization',
    'API Documentation Generation',
    'Technical Documentation',
    'Compliance Validation'
  ];

  const values = [
    {
      icon: Target,
      title: 'Innovation First',
      description: 'Pushing the boundaries of what\'s possible in AI-powered software engineering.'
    },
    {
      icon: Users,
      title: 'Developer Empowerment',
      description: 'Augmenting human developers with AI capabilities, not replacing them.'
    },
    {
      icon: Award,
      title: 'Quality Excellence',
      description: 'Maintaining the highest standards of code quality and security.'
    }
  ];

  const [isImageDialogOpen, setIsImageDialogOpen] = useState(false);
  const [hoveredPhase, setHoveredPhase] = useState<string | null>(null);
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);

  const toggleSelection = (itemKey: string) => {
    setSelectedItems(prev => {
      const newSet = new Set(prev);
      if (newSet.has(itemKey)) {
        newSet.delete(itemKey);
      } else {
        newSet.add(itemKey);
      }
      return newSet;
    });
  };

  const statusColors = {
    available: 'bg-emerald-500 text-white',
    inProgress: 'bg-yellow-400 text-black',
    comingSoon: 'bg-emerald-500 text-white',
    implementation: 'bg-gray-300 text-gray-700',
  };

  const statusBorderColors = {
    available: 'border-emerald-500',
    inProgress: 'border-yellow-400',
    comingSoon: 'border-emerald-500',
    implementation: 'border-gray-300',
  };

  const phases: Phase[] = [
    {
      name: 'Design',
      tooltip: 'Design phase capabilities for product development',
      items: [
        { text: 'Market Research Analysis', status: 'available', tooltip: 'This Agent helps in generating analysis report based upon different requirements against their market feasibility' },
        { text: 'Design Documentation', status: 'inProgress', tooltip: 'The Agent will streamline the creation, maintenance, and enhancement of design documentation across software, systems, and product development lifecycles.' },
        { text: 'UI/UX Design', status: 'inProgress', tooltip: 'The Agent is to  accelerate user interface and user experience design workflows. It help teams conceptualize, prototype, and refine digital experiences.' },
        { text: 'Requirements -> Architecture', status: 'inProgress', tooltip: 'This agent interprets functional and non-functional requirements to generate context-aware architecture designs—accelerating solution planning and reducing manual effort.' },
        { text: 'Architecture Recommendation', status: 'implementation', tooltip: 'The Agent is designed to support in designing scalable, secure, and efficient system architectures.' },
        { text: 'Design Validation', status: 'implementation', tooltip: 'The  Agent is to evaluate and validate design artifacts across UI/UX, system architecture, and solution workflows.' },
        { text: 'Compliance Checks', status: 'implementation', tooltip: 'The agent automates compliance validation across architecture, design, and operational workflows' },
        { text: 'UI Improvement based on User Behavior', status: 'implementation', tooltip: 'This Agent identifies usability issues, friction points, and engagement patterns to recommend targeted improvements that boost user satisfaction, retention, and conversion.' },
      ],
    },
    {
      name: 'Planning',
      tooltip: 'Planning phase capabilities for project management',
      items: [
        { text: 'User Story Creation', status: 'available', tooltip: 'The Agent is a product-centric assistant designed to transform business requirements, stakeholder inputs, and feature ideas into well-structured, actionable user stories.' },
        { text: 'User Story Validation', status: 'inProgress', tooltip: 'This Agent is a quality-focused assistant designed to ensure that user stories are complete, clear, and actionable' },
        { text: 'Dependency Mapping', status: 'inProgress', tooltip: 'The Agent  to identifies, visualizes, and manages dependencies across features, components, teams, and timelines.' },
        { text: 'Risk Identification and Mitigation', status: 'inProgress', tooltip: 'The Agent detects potential risks across project planning, solution design, and delivery workflows.' },
        { text: 'Cost Estimation', status: 'implementation', tooltip: 'The Agent is designed to provide accurate and data-driven cost projections for digital solutions, infrastructure, and product development.' },
        { text: 'Prioritizing Features by Impact & Feasibility', status: 'implementation', tooltip: 'The Agent is to help product teams identify and prioritize features based on their business impact and implementation feasibility.' },
        { text: 'Operating Model Recommendation', status: 'implementation', tooltip: 'The  Agent is help define and optimize the operating models.' },
        { text: 'Roadmap Recommendation', status: 'implementation', tooltip: 'This agent helps build actionable, impact-driven roadmaps.' },
        { text: 'Sentiment Analysis', status: 'implementation', tooltip: 'This agent is designed to help understand user, customer, or employee sentiment across channels for product refinement, and strategic decision-making.' },
      ],
    },
    {
      name: 'Build & Test',
      items: [
        { text: 'Azure DevOps Integration with Windsurf', status: 'available', tooltip: 'This is a workflow automation assistant designed to seamlessly connect Azure DevOps (ADO) with Windsurf. It simplifies integration setup, manages data flow, and ensures alignment between planning and execution layers.' },
        { text: 'Windsurf MCP Server for ADO Integration', status: 'available', tooltip: 'The MCP-ADO Integration Agent enables seamless connectivity between Azure DevOps and Windsurf MCP' },
        { text: 'Windsurf Auto-fetch from ADO', status: 'available', tooltip: 'It enables real-time, rule-based extraction of work item data, ensuring that delivery artifacts in Windsurf are always up-to-date and aligned with engineering execution' },
        { text: 'Windsurf Rationalization and Code Development', status: 'available', tooltip: 'The Agent is a delivery optimization assistant designed to streamline the rationalization of Windsurf configurations and automate code generation for Azure DevOps (ADO) integration' },
        { text: 'Windsurf Unit Test Case Development', status: 'available', tooltip: 'This is a quality assurance agent designed to automate the creation of unit test cases while using Windsurf' },
        { text: 'Repo Commit from Windsurf', status: 'available', tooltip: 'This is a delivery automation agent  to enable seamless code commits from Windsurf MCP Server into designated code repositories' },
        { text: 'Cloud Development Environment', status: 'inProgress', tooltip: 'The Agent automates the setup of secure, scalable, and ready-to-code cloud-based development environments.' },
        { text: 'Coding Validation and Bug Detection', status: 'implementation', tooltip: 'The quality assurance agent to automatically analyze source code for errors, inconsistencies, and potential bugs.' },
        { text: 'Coding Standard Enforcement', status: 'implementation', tooltip: 'The quality agent to ensure that code written across teams adheres to predefined coding standards and best practices. It automates code reviews, validating code against organizational or industry-standard guidelines.' },
        { text: 'Bug-Prone Module Prediction (Complexity)', status: 'implementation', tooltip: 'The agent designed to identify high-risk areas in codebases by analyzing structural complexity and historical defect patterns.' },
        { text: 'Test Case and Test Data Generation', status: 'implementation', tooltip: 'The agent designed to automate the creation of test scenarios and corresponding data sets based on application requirements, user stories, and code logic.' },
        { text: 'CI-CD Pipeline Scan for Weaknesses', status: 'implementation', tooltip: 'The Agent will proactively detect vulnerabilities, misconfigurations, and process gaps within continuous integration and continuous deployment (CI/CD) pipelines.' },
      ],
    },
    {
      name: 'Deployment',
      items: [
        { text: 'Harness Pipeline Trigger from Windsurf Commit', status: 'available', tooltip: 'The agent will initiate CI/CD workflows in Harness based on commit events originating from Windsurf MCP Server.' },
        { text: 'Harness Pipeline Auto Deploy', status: 'available', tooltip: 'This agent will streamline and accelerate software deployment workflows by automatically triggering Harness pipelines based on predefined conditions, code commits, or delivery milestones.' },
        { text: 'Harness Pipeline Creation from Prompts', status: 'available', tooltip: 'A smart DevOps assistant designed to automatically generate CI/CD pipeline configurations in Harness.' },
        { text: 'Harness Pipeline Creation from Prompts (Scaffolds)', status: 'available', tooltip: 'A smart DevOps assistant designed to automatically generate CI/CD pipeline configurations in Harness using existing re-usable sets.' },
        { text: 'On-demand CDE Creation', status: 'inProgress', tooltip: 'The agent to provision secure, scalable, and pre-configured cloud-based development environments instantly.' },
        { text: 'Deployment Decision', status: 'inProgress', tooltip: 'This is a delivery intelligence agent to guide teams in making informed, risk-aware deployment decisions.' },
        { text: 'Deployment Risk Assessment', status: 'inProgress', tooltip: 'The agent designed to evaluate the potential risks associated with software deployments.' },
        { text: 'Anomaly Detection', status: 'inProgress', tooltip: 'The monitoring and diagnostics agent to identify unusual patterns, behaviors, or deviations across systems, applications, and data pipelines.' },
        { text: 'Intelligent Rollback', status: 'implementation', tooltip: 'This agent can detect failed or risky deployments and automatically initiate safe rollback procedures.' },
        { text: 'Release Notes Generation', status: 'implementation', tooltip: 'Theis agent will help to create clear, concise, and user-friendly release notes based on code commits, issue trackers, deployment logs, and feature updates' },
      ],
    },
    {
      name: 'Reliability',
      items: [
        { text: 'Datadog Integration with Harness', status: 'available', tooltip: 'The agent is to seamlessly connect Datadog\'s monitoring and alerting capabilities with Harness\'s CI/CD pipelines.' },
        { text: 'Datadog Observability of Harness Pipeline Run', status: 'available', tooltip: 'The agent is to seamlessly connect Datadog\'s monitoring and observability capabilities with Harness\'s CI/CD pipelines.' },
        { text: 'Datadog Error Remediation', status: 'available', tooltip: 'The observability agent which can automatically detect, diagnose, and resolve errors surfaced through Datadog monitoring.' },
        { text: 'Datadog Self-healing', status: 'inProgress', tooltip: 'The observability agent which can automatically resolve errors surfaced through Datadog monitoring and put system back on track.' },
        { text: 'Anomaly Detection', status: 'inProgress', tooltip: 'The monitoring and diagnostics agent to identify unusual patterns, behaviors, or deviations across systems, infrastructure , production environments and live apps.' },
        { text: 'Root Cause Analysis', status: 'inProgress', tooltip: 'Diagnostics and reliability agent to identify the underlying causes of system failures, performance issues, or deployment anomalies.' },
        { text: 'Ticket and Log Analysis', status: 'inProgress', tooltip: 'The agent which analyzes incident tickets and system logs to uncover patterns, root causes, and resolution paths.' },
        { text: 'Auto-classification & Incident Prioritization', status: 'implementation', tooltip: 'The agent to streamline incident management by automatically categorizing incoming tickets and assigning priority levels based on impact, urgency, and historical patterns.' },
        { text: 'Intelligent Threshold Setting', status: 'implementation', tooltip: 'The monitoring optimization agent which dynamically determines and adjust alert thresholds across systems, services, and metrics.' },
        { text: 'Capacity Planning and Resource Optimization', status: 'implementation', tooltip: 'The Agent to analyze system usage patterns, forecast future demand, and recommend optimal resource allocation across environments.' },
        { text: 'Security Related Use Cases', status: 'implementation', tooltip: 'The agent supports a wide range of security-related use cases across cloud, infrastructure, application, and DevOps environments.' },
        { text: 'Health Monitoring', status: 'implementation', tooltip: 'This is an observability agent to continuously assess the health and performance of systems, applications, and infrastructure.' },
      ],
    },
    {
      name: 'Infrastructure & Security',
      tooltip: 'Infrastructure and security management capabilities',
      items: [
        { text: 'Infrastructure Creation', status: 'inProgress', tooltip: 'The Agent creates Infrastructure setup based on end user inputs utilizing the available scaffolds or creating new scaffolds if needed' },
        { text: 'Infrastructure Vulnerability Remediation', status: 'inProgress', tooltip: 'The Agent runs the vulnerability scanning and publishes the report along with root cause analysis, remediation and self heal capabilities' },
        { text: 'Health Monitor', status: 'inProgress', tooltip: 'The agent monitors the health of the infrastructure and publishes alerts along with needed remediation' },
        { text: 'Environment Management & Tracking', status: 'implementation', tooltip: 'The Agent helps in intelligent Environment Management, ensuring unused environments for auto-deallocation and tear down' },
        { text: 'Infrastructure Upgrade', status: 'implementation', tooltip: 'The agent takes care of periodic upgrades, powered with its alert and track mechanism' },
        { text: 'Infra Policy and Guardrails Validation', status: 'implementation', tooltip: 'The agent validates policy enforcement, can publish available guardrails, and can enforce policies as per need' },
        { text: 'Security Scan & Remediator', status: 'implementation', tooltip: 'The agent helps in security scanning, shares alerts and security scan reports with remediations & self-heal' },
        { text: 'Infrastructure Cost Predictor', status: 'implementation', tooltip: 'The agent scans through the infrastructure and helps in forecasting the cost along with solution around cost savings' },
      ],
    },
  ];

  return (
    <div className="min-h-screen bg-[#1a1f3a] dark:bg-[#1a1f3a]">
      <div className="relative max-w-7xl mx-auto px-6 py-8">
        {/* Back Button */}
        <Button
          variant="ghost"
          onClick={onBack}
          className="mb-6 text-white hover:text-[#3498B3] hover:bg-[#3498B3]/10"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Home
        </Button>

        {/* Hero Section - Matching Figma Design */}
        <div className="mb-16 bg-gradient-to-r from-[#2a2f5a] to-[#1e2340] rounded-3xl p-12 relative overflow-hidden">
          {/* Decorative background elements */}
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-[#3498B3]/10 rounded-full blur-3xl" />
            <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-[#351A55]/10 rounded-full blur-3xl" />
          </div>

          <div className="relative grid md:grid-cols-2 gap-12 items-center">
            {/* Left Side - Text Content */}
            <div>
              <h1 className="text-5xl leading-tight mb-6">
                <span className="text-white">Enterprise </span>
                <span className="text-[#FF9500]">Software Engineering</span>
                <br />
                <span className="text-white">Platform </span>
                <span className="bg-gradient-to-r from-[#667BC6] to-[#9D84B7] bg-clip-text text-transparent">infused by AI</span>
              </h1>
              
              <p className="text-slate-300 text-lg leading-relaxed mb-8">
                QUANTNIK transforms enterprise software engineering with AI-powered automation, intelligent insights, and unified development workflows. Experience the next-generation platform that seamlessly integrates development, testing, infrastructure, and deployment into one powerful AI-enhanced ecosystem.
              </p>

              <div className="flex gap-4">
                <Button 
                  size="lg" 
                  className="bg-[#5B73E8] hover:bg-[#4a5fc9] text-white px-6"
                >
                  Request Demo
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
                <Button 
                  size="lg" 
                  variant="outline"
                  className="border-2 border-slate-500 text-white hover:bg-white/10 px-6"
                >
                  <Play className="w-4 h-4 mr-2" />
                  See Preview
                </Button>
              </div>
            </div>

            {/* Right Side - Image */}
            <div className="relative">
              <div className="relative h-[400px] rounded-2xl overflow-hidden shadow-2xl border border-slate-700/50 bg-gradient-to-br from-[#2a2f5a] via-[#1e2340] to-[#2a2f5a]">
                {/* AI Platform Visual - Decorative Elements */}
                <div className="absolute inset-0 flex items-center justify-center p-8">
                  <div className="relative w-full h-full">
                    {/* Animated grid background */}
                    <div className="absolute inset-0 opacity-20">
                      <div className="grid grid-cols-8 grid-rows-8 gap-4 h-full w-full">
                        {Array.from({ length: 64 }).map((_, i) => (
                          <div 
                            key={i}
                            className="border border-[#3498B3]/30 rounded"
                            style={{
                              animation: `pulse ${2 + (i % 3)}s infinite`,
                              animationDelay: `${i * 0.1}s`
                            }}
                          />
                        ))}
                      </div>
                    </div>
                    
                    {/* Central AI node */}
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
                      <div className="relative">
                        <div className="w-32 h-32 rounded-full bg-gradient-to-r from-[#3498B3] to-[#355493] flex items-center justify-center shadow-2xl">
                          <Brain className="w-16 h-16 text-white" />
                        </div>
                        {/* Orbiting elements */}
                        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64">
                          {[0, 72, 144, 216, 288].map((angle, i) => (
                            <div
                              key={i}
                              className="absolute top-1/2 left-1/2 w-12 h-12 rounded-lg bg-gradient-to-br from-[#351A55] to-[#BE266A] shadow-lg flex items-center justify-center"
                              style={{
                                transform: `rotate(${angle}deg) translate(120px) rotate(-${angle}deg)`,
                                animation: `spin ${10 + i}s linear infinite`
                              }}
                            >
                              {i === 0 && <Code className="w-6 h-6 text-white" />}
                              {i === 1 && <Shield className="w-6 h-6 text-white" />}
                              {i === 2 && <Zap className="w-6 h-6 text-white" />}
                              {i === 3 && <Network className="w-6 h-6 text-white" />}
                              {i === 4 && <TrendingUp className="w-6 h-6 text-white" />}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                    
                    {/* Connecting lines */}
                    <svg className="absolute inset-0 w-full h-full opacity-30">
                      <line x1="50%" y1="50%" x2="20%" y2="20%" stroke="#3498B3" strokeWidth="2" />
                      <line x1="50%" y1="50%" x2="80%" y2="20%" stroke="#3498B3" strokeWidth="2" />
                      <line x1="50%" y1="50%" x2="20%" y2="80%" stroke="#3498B3" strokeWidth="2" />
                      <line x1="50%" y1="50%" x2="80%" y2="80%" stroke="#3498B3" strokeWidth="2" />
                    </svg>
                  </div>
                </div>
                
                {/* Overlay gradient */}
                <div className="absolute inset-0 bg-gradient-to-t from-[#1e2340]/60 to-transparent pointer-events-none" />
              </div>
            </div>
          </div>
        </div>

        {/* Vision Statement */}
        <div className="max-w-7xl mx-auto px-6 mb-20">
          <Card className="p-8 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm border-2 border-[#355493]/20 shadow-lg">
            <div className="text-center mb-16" style={{ marginBottom: 'calc(4rem + 2px)' }}>
              <h2 className="text-3xl lg:text-4xl font-bold text-card-foreground mb-4">
                Introducing QUANTNIK
              </h2>
              <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
                QUANTNIK is Wipro's AI-powered enterprise software engineering platform designed to transform how organizations approach development, testing, and deployment through intelligent automation and unified workflows.
              </p>
            </div>

            <div className="grid lg:grid-cols-2 gap-12 items-center">
              <div className="space-y-6">
                <h3 className="text-2xl font-semibold text-card-foreground">
                  AI-Powered Engineering Excellence
                </h3>
                <p className="text-muted-foreground leading-relaxed">
                  QUANTNIK leverages advanced artificial intelligence to unify eight comprehensive modules into a single, intelligent platform. Every aspect of your software engineering lifecycle is enhanced with AI-driven insights, automated workflows, and predictive capabilities that optimize for speed, quality, and enterprise scale.
                </p>
                
                <div className="space-y-4">
                  <div className="flex items-start space-x-3">
                    <CheckCircle className="w-5 h-5 text-blue-500 mt-1" />
                    <div>
                      <h4 className="font-medium text-card-foreground">AI-Powered Automation</h4>
                      <p className="text-sm text-muted-foreground">Intelligent workflows that will learn and adapt to your team's patterns</p>
                    </div>
                  </div>
                  <div className="flex items-start space-x-3">
                    <CheckCircle className="w-5 h-5 text-blue-500 mt-1" />
                    <div>
                      <h4 className="font-medium text-card-foreground">Enterprise Security</h4>
                      <p className="text-sm text-muted-foreground">Bank-grade security with compliance frameworks built-in from day one</p>
                    </div>
                  </div>
                  <div className="flex items-start space-x-3">
                    <CheckCircle className="w-5 h-5 text-blue-500 mt-1" />
                    <div>
                      <h4 className="font-medium text-card-foreground">Global Scale</h4>
                      <p className="text-sm text-muted-foreground">Architected to handle enterprise workloads across multiple regions</p>
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="relative">
                <div className="w-full h-96 relative overflow-hidden rounded-2xl shadow-lg bg-muted/50">
                  <Dialog open={isImageDialogOpen} onOpenChange={setIsImageDialogOpen}>
                    <DialogTrigger asChild>
                      <div className="relative group cursor-pointer h-full">
                        <img 
                          src={quantnikFrameworkImage}
                          alt="QUANTNIK Framework"
                          className="w-full h-full object-contain hover:opacity-90 transition-opacity"
                        />
                        {/* Expand Icon Button */}
                        <div className="absolute top-4 right-4 bg-black/50 backdrop-blur-sm rounded-lg p-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                          <Maximize2 className="w-5 h-5 text-white" />
                        </div>
                        {/* Hover overlay */}
                        <div className="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity duration-200 rounded-2xl" />
                      </div>
                    </DialogTrigger>
                    <DialogContent className="!w-[1200px] !h-[912px] !max-w-none !max-h-none p-0 overflow-hidden">
                      <DialogTitle className="sr-only">QUANTNIK Framework</DialogTitle>
                      <DialogDescription className="sr-only">
                        Expanded view of the QUANTNIK AI-powered enterprise software engineering platform framework
                      </DialogDescription>
                      <div className="relative">
                        <img 
                          src={quantnikFrameworkImage}
                          alt="QUANTNIK Framework"
                          className="w-full h-auto"
                        />
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
                
                {/* Framework Title */}
                <div className="mt-4 text-center">
                  <h4 className="text-lg font-semibold text-card-foreground mb-1">
                    QUANTNIK Framework
                  </h4>
                  <p className="text-sm text-muted-foreground">
                    Click to expand and explore our comprehensive platform architecture
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Use Cases and Integration Roadmap */}
        <section className="py-20 bg-muted/30 mb-16">
          <div className="max-w-7xl mx-auto px-6">
            <div className="text-center mb-16">
              <h2 className="text-3xl lg:text-4xl font-bold text-card-foreground mb-4">
                Use Cases and Integration Roadmap
              </h2>
              <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
                Discover how QUANTNIK transforms enterprise workflows and see our strategic integration timeline for comprehensive platform deployment
              </p>
            </div>

            <div className="flex justify-center">
              <div className="max-w-[1800px] mx-auto w-full">
                {/* Phase Headers with Connecting Lines */}
                <div className="relative mb-8 px-6">
                  <div className="grid grid-cols-6 gap-4 relative">
                    {phases.map((phase, idx) => (
                      <div key={phase.name} className="relative flex justify-center items-center">
                        <motion.div
                          className="relative"
                          onMouseEnter={() => setHoveredPhase(phase.name)}
                          onMouseLeave={() => setHoveredPhase(null)}
                        >
                          <div className="bg-[#7470a8] rounded-full px-4 py-2.5 text-center text-xs cursor-pointer border-2 border-gray-600 text-white whitespace-nowrap min-w-[140px]">
                            {phase.name}
                          </div>
                          
                          {/* Tooltip for phase */}
                          {phase.tooltip && hoveredPhase === phase.name && (
                            <motion.div
                              initial={{ opacity: 0, y: 10 }}
                              animate={{ opacity: 1, y: 0 }}
                              className="absolute -top-12 left-1/2 -translate-x-1/2 bg-gray-800 text-white px-3 py-2 rounded text-xs whitespace-nowrap z-50 border border-gray-600"
                            >
                              {phase.tooltip}
                              <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-gray-800 rotate-45 border-r border-b border-gray-600" />
                            </motion.div>
                          )}
                        </motion.div>
                        
                        {/* Connector line to next phase */}
                        {idx < phases.length - 1 && (
                          <div 
                            className="absolute top-1/2 h-[2px] bg-gray-600 z-0" 
                            style={{
                              left: 'calc(50% + 70px)',
                              width: 'calc(100% + 1rem - 70px)'
                            }}
                          />
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Columns */}
                <div className="border border-gray-600 rounded-lg p-6 bg-muted/30">
                  <div className="grid grid-cols-6 gap-4">
                    {phases.map((phase, phaseIdx) => (
                      <div key={phase.name}>
                        <div className="space-y-2.5">
                          {phase.items.map((item, itemIdx) => {
                            const itemKey = `${phaseIdx}-${itemIdx}`;
                            const isSelected = selectedItems.has(itemKey);
                            const isHovered = hoveredItem === itemKey;
                            
                            return (
                              <div key={itemIdx} className="relative">
                                <motion.button
                                  className={`w-full px-3 py-2 rounded-full text-xs text-center transition-all relative min-h-[52px] ${
                                    statusColors[item.status]
                                  } ${
                                    isSelected ? 'ring-4 ring-blue-500 ring-offset-2 ring-offset-card' : ''
                                  } cursor-pointer flex items-center justify-center gap-1 hover:shadow-lg`}
                                  whileHover={{ scale: 1.05 }}
                                  whileTap={{ scale: 0.98 }}
                                  onClick={() => toggleSelection(itemKey)}
                                  onMouseEnter={() => setHoveredItem(itemKey)}
                                  onMouseLeave={() => setHoveredItem(null)}
                                  transition={{ duration: 0.2 }}
                                >
                                  <span className="flex-1 leading-tight break-words">{item.text.replace(' → ', ' ')}</span>
                                  {item.hasArrow && <ArrowRight className="w-3 h-3 flex-shrink-0" />}
                                </motion.button>
                                
                                {/* Tooltip */}
                                {isHovered && (
                                  <motion.div
                                    initial={{ opacity: 0, x: phaseIdx < 3 ? -5 : 5 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    className={`absolute top-1/2 -translate-y-1/2 ${
                                      phaseIdx < 3 ? 'left-full ml-2' : 'right-full mr-2'
                                    } bg-gray-800 text-white px-3 py-2 rounded text-xs z-50 border border-gray-600 max-w-[250px] whitespace-normal`}
                                  >
                                    {item.tooltip}
                                    <div className={`absolute top-1/2 -translate-y-1/2 w-2 h-2 bg-gray-800 rotate-45 ${
                                      phaseIdx < 3 
                                        ? '-left-1 border-l border-b' 
                                        : '-right-1 border-r border-t'
                                    } border-gray-600`} />
                                  </motion.div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Legend */}
                <div className="mt-10 flex items-center justify-center gap-8">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-emerald-500" />
                    <span className="text-sm text-muted-foreground">Available</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-yellow-400" />
                    <span className="text-sm text-muted-foreground">In Progress</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-gray-300" />
                    <span className="text-sm text-muted-foreground">Coming Soon</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Capabilities */}
        <Card className="p-8 mb-12 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm border-2 border-[#355493]/20 shadow-lg">
          <div className="max-w-7xl mx-auto px-6">
            <div className="text-center mb-16">
              <h2 className="text-3xl lg:text-4xl font-bold text-card-foreground mb-4">
                QUANTNIK Target state aligned to different fabric layers and Wipro Ecosystem
              </h2>
              <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
                We have enabled a composable & scalable modern agentic architecture that will address the entire SDLC stages across client and Wipro ecosystem
              </p>
            </div>

            <div className="flex justify-center">
              <div className="relative w-full max-w-[1200px] h-[531px] rounded-2xl overflow-hidden shadow-xl">
                <img 
                  src={buildIqLayersImage}
                  alt="QUANTNIK BuildIQ Layers Architecture"
                  className="w-full h-full object-contain"
                />
              </div>
            </div>
          </div>
        </Card>

        {/* BuildIQ Grid - MCP Catalog Section */}
      <section className="relative bg-gradient-to-br from-[#351A55] via-[#355493] to-[#3498B3] text-white overflow-hidden">
        <div className="absolute inset-0 bg-black/30" />
        <div className="relative max-w-7xl mx-auto px-6 py-20">
          <div className="text-center mb-16">
            <h2 className="text-3xl lg:text-4xl font-bold text-white mb-4">
              QUANTNIK Grid – MCP Catalog (Our Assets, Partnership)
            </h2>
            <p className="text-xl text-white/90 max-w-3xl mx-auto">
              Explore our comprehensive ecosystem of enterprise assets, partnerships, and microservices that power QUANTNIK's intelligent platform capabilities
            </p>
          </div>

          <div className="flex justify-center">
            <div className="relative w-full max-w-[1200px] h-[550px] rounded-2xl overflow-hidden shadow-2xl">
              <ImageWithFallback 
                src={assetsPartnershipsGrid} 
                alt="QUANTNIK Grid – MCP Catalog showing our assets and partnerships" 
                className="w-full h-full object-contain"
              />
            </div>
          </div>
        </div>
      </section>

        {/* CTA Section */}
        <Card className="p-8 bg-gradient-to-r from-[#351A55] to-[#3498B3] border-0 shadow-2xl">
          <div className="text-center text-white">
            <Rocket className="w-12 h-12 mx-auto mb-4" />
            <h2 className="text-3xl font-bold mb-4">Ready to Transform Your Development Process?</h2>
            <p className="text-lg mb-6 opacity-90">
              QUANTNIK is currently in pre-launch. Request early access to experience the future of AI-powered software engineering.
            </p>
            <div className="flex gap-4 justify-center">
              <Button 
                size="lg" 
                className="bg-white text-[#351A55] hover:bg-slate-100"
              >
                Request a Demo
              </Button>
              <Button 
                size="lg" 
                variant="outline"
                className="border-2 border-white text-white hover:bg-white/10"
              >
                Learn More
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}