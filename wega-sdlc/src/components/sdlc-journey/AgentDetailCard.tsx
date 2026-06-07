import { X, CheckCircle, Zap, TrendingUp, Users, FileText, Lightbulb, CheckCircle as Check, Network, MessageSquare, Calendar, Target, Shield, Lock, Eye, Key, Bug, AlertCircle, AlertTriangle, Search, Activity, Server, RefreshCw, ClipboardCheck, FileCheck } from 'lucide-react';
import { LucideIcon } from 'lucide-react';

interface AgentDetail {
  name: string;
  icon: LucideIcon;
  color: string;
  tagline: string;
  description: string;
  keyCapabilities: string[];
  benefits: string[];
  useCases: string[];
  technicalDetails: string;
}

interface AgentDetailCardProps {
  agent: AgentDetail;
  onClose: () => void;
}

export const agentDetails: Record<string, AgentDetail> = {
  'Market Research Analyst': {
    name: 'Market Research Analyst',
    icon: Users,
    color: 'from-cyan-500 to-cyan-600',
    tagline: 'Transform raw market data into actionable business insights',
    description: 'The Market Research Analyst agent leverages advanced NLP and machine learning algorithms to analyze market trends, competitor landscapes, and customer feedback. It processes unstructured data from multiple sources to identify opportunities, threats, and strategic recommendations for your product planning.',
    keyCapabilities: [
      'Automated stakeholder interview analysis and sentiment extraction',
      'Competitive landscape mapping with SWOT analysis generation',
      'Customer persona creation from feedback and behavior patterns',
      'Market trend identification using predictive analytics',
      'Gap analysis between current offerings and market demands'
    ],
    benefits: [
      'Reduce market research time by 70% with automated data processing',
      'Eliminate bias in stakeholder analysis with AI-driven insights',
      'Identify emerging trends 3-6 months ahead of competitors',
      'Generate comprehensive market reports in minutes, not weeks'
    ],
    useCases: [
      'New product ideation and validation',
      'Feature prioritization based on market demand',
      'Competitive positioning strategy development',
      'Customer pain point identification for requirement gathering'
    ],
    technicalDetails: 'Powered by transformer-based NLP models fine-tuned on business and market research data. Integrates with survey platforms, social media APIs, and industry databases for real-time data collection.'
  },
  'Business Requirement Document': {
    name: 'Business Requirement Document',
    icon: FileText,
    color: 'from-purple-500 to-purple-600',
    tagline: 'Generate comprehensive BRDs with zero manual writing',
    description: 'This agent automatically creates professional, standardized Business Requirement Documents by analyzing inputs from stakeholders, market research, and strategic goals. It ensures consistency, completeness, and traceability across all project requirements.',
    keyCapabilities: [
      'Auto-generate BRD sections including scope, objectives, and constraints',
      'Extract and structure requirements from unstructured stakeholder inputs',
      'Apply industry-standard BRD templates (IEEE, IIBA frameworks)',
      'Create requirement traceability matrices automatically',
      'Generate visual diagrams (use case, context, data flow)'
    ],
    benefits: [
      'Save 15-20 hours per project on documentation',
      'Ensure 100% consistency across requirement documents',
      'Automatic version control and change tracking',
      'Reduce requirement ambiguity by 85% with AI refinement'
    ],
    useCases: [
      'Enterprise software project initiation',
      'RFP response requirement documentation',
      'Legacy system modernization planning',
      'Compliance-driven requirement gathering'
    ],
    technicalDetails: 'Uses template-based generation with GPT-4 for natural language synthesis. Incorporates ontology-based requirement classification and dependency mapping algorithms.'
  },
  'User Story Generator': {
    name: 'User Story Generator',
    icon: Lightbulb,
    color: 'from-blue-500 to-blue-600',
    tagline: 'Create perfectly formatted user stories at scale',
    description: 'Transform high-level requirements into detailed, actionable user stories following Agile best practices. This agent automatically generates stories with acceptance criteria, estimates, and dependencies while maintaining the "As a [role], I want [feature], So that [benefit]" format.',
    keyCapabilities: [
      'Auto-decompose epics into granular user stories',
      'Generate acceptance criteria using Gherkin syntax (Given-When-Then)',
      'Assign story points using ML-based estimation models',
      'Identify story dependencies and suggest sprint groupings',
      'Create personas-aligned user stories with context'
    ],
    benefits: [
      'Generate 50-100 user stories per hour vs. 5-10 manually',
      'Achieve 90% consistency in story format across teams',
      'Reduce backlog grooming time by 60%',
      'Automatically link stories to business objectives'
    ],
    useCases: [
      'Sprint planning and backlog creation',
      'Feature breakdown for MVP scoping',
      'Refinement of vague requirements into actionable items',
      'Migration of waterfall requirements to Agile stories'
    ],
    technicalDetails: 'Employs sequence-to-sequence models trained on 500K+ validated user stories. Uses hierarchical clustering for epic decomposition and reinforcement learning for story point prediction.'
  },
  'User Story Validator': {
    name: 'User Story Validator',
    icon: Check,
    color: 'from-emerald-500 to-emerald-600',
    tagline: 'Ensure every story meets INVEST criteria',
    description: 'Quality-check user stories against industry best practices and your team\'s standards. This agent validates stories for completeness, clarity, testability, and adherence to the INVEST principles (Independent, Negotiable, Valuable, Estimable, Small, Testable).',
    keyCapabilities: [
      'Automated INVEST criteria validation with scoring',
      'Detect ambiguous language and suggest clarifications',
      'Identify missing acceptance criteria and edge cases',
      'Check for duplicate or conflicting stories',
      'Validate story sizing and recommend splitting when needed'
    ],
    benefits: [
      'Reduce defects by 40% through better story quality',
      'Eliminate 95% of incomplete or ambiguous stories before sprint',
      'Save 3-5 hours per sprint on refinement meetings',
      'Increase team velocity by 25% with clear requirements'
    ],
    useCases: [
      'Pre-sprint story readiness assessment',
      'Quality gates for backlog acceptance',
      'Onboarding validation for new team members',
      'Cross-team story standardization'
    ],
    technicalDetails: 'Uses multi-criteria decision analysis with NLP-based ambiguity detection. Implements rule-based validators combined with ML classifiers trained on thousands of accepted vs. rejected stories.'
  },
  'Knowledge Graph Builder': {
    name: 'Knowledge Graph Builder',
    icon: Network,
    color: 'from-indigo-500 to-indigo-600',
    tagline: 'Map the entire relationship network of your project',
    description: 'Automatically construct comprehensive knowledge graphs from project documents, requirements, and code. This agent reveals hidden relationships, dependencies, and insights by creating a semantic network of all project entities and their connections.',
    keyCapabilities: [
      'Extract entities (features, components, stakeholders) from documents',
      'Map relationships between requirements, code, and tests',
      'Identify implicit dependencies and potential conflicts',
      'Generate visual graph representations with interactive exploration',
      'Enable semantic search across the entire knowledge base'
    ],
    benefits: [
      'Discover 80% more requirement dependencies than manual review',
      'Reduce integration issues by 50% through dependency visibility',
      'Enable instant impact analysis for requirement changes',
      'Facilitate knowledge transfer with visual documentation'
    ],
    useCases: [
      'Complex system requirement analysis',
      'Impact assessment for feature changes',
      'Technical debt identification',
      'Onboarding visualization for new developers'
    ],
    technicalDetails: 'Built on Neo4j graph database with custom entity recognition models. Uses graph neural networks for link prediction and community detection algorithms for clustering related concepts.'
  },
  'Document Query & FAQ Generator': {
    name: 'Document Query & FAQ Generator',
    icon: MessageSquare,
    color: 'from-pink-500 to-pink-600',
    tagline: 'Instant answers from your entire documentation',
    description: 'Transform your project documentation into an intelligent Q&A system. This agent automatically generates FAQs from documents and enables natural language querying, making critical information instantly accessible to all team members.',
    keyCapabilities: [
      'Generate contextual FAQs from requirements and technical docs',
      'Natural language querying with semantic understanding',
      'Multi-document search with relevance ranking',
      'Auto-update FAQs when documents change',
      'Citation and source linking for all answers'
    ],
    benefits: [
      'Reduce information search time by 75%',
      'Decrease repetitive questions to senior team members by 60%',
      'Ensure consistent answers across the organization',
      'Onboard new team members 3x faster with instant answers'
    ],
    useCases: [
      'Developer onboarding and training',
      'Technical support knowledge base creation',
      'Compliance documentation querying',
      'Cross-team information sharing'
    ],
    technicalDetails: 'Implements RAG (Retrieval-Augmented Generation) architecture with vector embeddings using FAISS for similarity search. Fine-tuned LLM for domain-specific question answering.'
  },
  'Effort Planner': {
    name: 'Effort Planner',
    icon: Calendar,
    color: 'from-orange-500 to-orange-600',
    tagline: 'AI-powered estimation with historical accuracy',
    description: 'Leverage machine learning and historical project data to generate accurate effort estimates for user stories and epics. This agent considers complexity, team velocity, and risk factors to provide reliable timelines and resource planning.',
    keyCapabilities: [
      'Story point estimation using ML trained on historical data',
      'Team velocity prediction based on past performance',
      'Risk-adjusted timeline generation with confidence intervals',
      'Resource allocation optimization across sprints',
      'Bottleneck identification and mitigation suggestions'
    ],
    benefits: [
      'Improve estimation accuracy by 35-45%',
      'Reduce overruns by 40% with risk-adjusted planning',
      'Save 5-8 hours per sprint on planning poker sessions',
      'Enable data-driven commitment with confidence levels'
    ],
    useCases: [
      'Sprint capacity planning',
      'Release timeline forecasting',
      'Resource allocation across multiple projects',
      'Risk assessment for fixed-bid projects'
    ],
    technicalDetails: 'Uses ensemble models (Random Forest + XGBoost) trained on story attributes, team metrics, and historical outcomes. Implements Monte Carlo simulation for probabilistic forecasting.'
  },
  'MVP Analyzer': {
    name: 'MVP Analyzer',
    icon: Target,
    color: 'from-violet-500 to-violet-600',
    tagline: 'Identify the minimum feature set for maximum value',
    description: 'Analyze your product backlog to identify the optimal Minimum Viable Product scope that delivers maximum business value with minimum development effort. This agent uses multi-criteria optimization to recommend what should (and shouldn\'t) be in your MVP.',
    keyCapabilities: [
      'Value vs. effort analysis for all features using MoSCoW method',
      'Dependency-aware feature clustering for viable releases',
      'Risk assessment for each potential MVP scope',
      'Customer segment analysis to validate MVP assumptions',
      'Alternative MVP scenario generation with trade-off analysis'
    ],
    benefits: [
      'Reduce time-to-market by 40% with focused scope',
      'Increase MVP success rate by 55% through data-driven selection',
      'Save 30-50% development costs by avoiding non-essential features',
      'Validate product-market fit 60% faster'
    ],
    useCases: [
      'Startup product launch planning',
      'New feature set prioritization',
      'Pivot analysis and scope adjustment',
      'Proof-of-concept definition'
    ],
    technicalDetails: 'Employs multi-objective optimization algorithms (NSGA-II) with custom fitness functions for value, cost, and risk. Integrates with A/B testing platforms for validation feedback loops.'
  },
  'Architecture Designer': {
    name: 'Architecture Designer',
    icon: Network,
    color: 'from-purple-500 to-purple-600',
    tagline: 'AI-powered system architecture generation',
    description: 'Automatically design scalable, maintainable system architectures based on your requirements. This agent analyzes functional and non-functional requirements to generate architecture diagrams, component specifications, and technology recommendations.',
    keyCapabilities: [
      'Generate multi-tier architecture diagrams automatically',
      'Recommend optimal technology stack based on requirements',
      'Design microservices boundaries and communication patterns',
      'Create C4 model diagrams (Context, Container, Component, Code)',
      'Analyze and optimize for scalability, performance, and security'
    ],
    benefits: [
      'Reduce architecture design time by 65%',
      'Ensure architectural consistency across projects',
      'Automatically identify potential bottlenecks and risks',
      'Generate comprehensive architecture documentation'
    ],
    useCases: [
      'New system architecture design',
      'Legacy system re-architecture planning',
      'Technology stack evaluation and selection',
      'Microservices decomposition strategy'
    ],
    technicalDetails: 'Uses graph-based architecture modeling with constraint satisfaction algorithms. Incorporates architecture pattern libraries and cloud-native design principles. Integrates with ADR (Architecture Decision Records) systems.'
  },
  'UX/UI Analyzer': {
    name: 'UX/UI Analyzer',
    icon: Lightbulb,
    color: 'from-pink-500 to-pink-600',
    tagline: 'Intelligent user experience optimization',
    description: 'Analyze user interfaces and experiences using AI-powered heuristics and best practices. This agent evaluates designs for usability, accessibility, and engagement, providing actionable recommendations for improvement.',
    keyCapabilities: [
      'Automated accessibility (WCAG) compliance checking',
      'Heuristic evaluation against Nielsen\'s 10 usability principles',
      'User flow optimization and friction point identification',
      'Design consistency analysis across screens',
      'Mobile responsiveness and adaptive design validation'
    ],
    benefits: [
      'Improve user satisfaction scores by 45%',
      'Reduce usability testing time by 50%',
      'Achieve 100% WCAG compliance automatically',
      'Decrease user churn by 30% through UX optimization'
    ],
    useCases: [
      'Design review and validation',
      'Accessibility audit and remediation',
      'Conversion rate optimization',
      'Mobile-first design validation'
    ],
    technicalDetails: 'Implements computer vision models for UI element detection and classification. Uses rule-based engines for accessibility checks combined with ML models trained on successful UX patterns.'
  },
  'API Designer': {
    name: 'API Designer',
    icon: FileText,
    color: 'from-blue-500 to-blue-600',
    tagline: 'Automated RESTful and GraphQL API design',
    description: 'Generate complete API specifications from requirements and data models. This agent creates OpenAPI/Swagger documentation, GraphQL schemas, and API gateway configurations following industry best practices.',
    keyCapabilities: [
      'Auto-generate OpenAPI 3.0 specifications from requirements',
      'Design RESTful endpoints following REST maturity model',
      'Create GraphQL schemas with resolvers and mutations',
      'Generate API documentation with examples',
      'Design authentication and authorization flows'
    ],
    benefits: [
      'Reduce API design time by 70%',
      'Ensure API consistency across services',
      'Generate production-ready API documentation',
      'Identify security vulnerabilities early'
    ],
    useCases: [
      'Microservices API design',
      'API gateway configuration',
      'Third-party integration planning',
      'API versioning strategy'
    ],
    technicalDetails: 'Uses schema inference algorithms and REST/GraphQL best practice templates. Integrates with API management platforms (Apigee, Kong, AWS API Gateway).'
  },
  'Database Schema Generator': {
    name: 'Database Schema Generator',
    icon: Check,
    color: 'from-cyan-500 to-cyan-600',
    tagline: 'Optimized database design from requirements',
    description: 'Automatically generate normalized database schemas from business requirements and data models. This agent designs tables, relationships, indexes, and constraints while optimizing for performance and data integrity.',
    keyCapabilities: [
      'Generate normalized database schemas (1NF through BCNF)',
      'Design optimal indexes for query performance',
      'Create entity-relationship diagrams automatically',
      'Recommend partitioning and sharding strategies',
      'Generate migration scripts for multiple databases'
    ],
    benefits: [
      'Reduce database design time by 60%',
      'Optimize query performance by 3-5x',
      'Prevent data anomalies with proper normalization',
      'Support multi-database deployment (PostgreSQL, MySQL, MongoDB)'
    ],
    useCases: [
      'New application database design',
      'Database migration and modernization',
      'Data model optimization',
      'Multi-tenant architecture planning'
    ],
    technicalDetails: 'Implements functional dependency analysis and normal form algorithms. Uses cost-based optimization for index selection. Generates dialect-specific SQL for major databases.'
  },
  'Design Pattern Advisor': {
    name: 'Design Pattern Advisor',
    icon: Calendar,
    color: 'from-indigo-500 to-indigo-600',
    tagline: 'Intelligent design pattern recommendations',
    description: 'Recommend and apply proven design patterns based on your specific requirements and constraints. This agent analyzes your architecture to suggest creational, structural, and behavioral patterns that improve maintainability and scalability.',
    keyCapabilities: [
      'Recommend design patterns from GoF and modern catalogs',
      'Analyze code to identify pattern opportunities',
      'Generate pattern implementation examples',
      'Detect anti-patterns and suggest refactoring',
      'Provide trade-off analysis for pattern choices'
    ],
    benefits: [
      'Improve code maintainability by 50%',
      'Reduce technical debt through proven patterns',
      'Accelerate developer onboarding with standard patterns',
      'Decrease defect rate by 35% with tested solutions'
    ],
    useCases: [
      'Code refactoring and modernization',
      'Architecture review and optimization',
      'Design pattern training and adoption',
      'Technical debt reduction'
    ],
    technicalDetails: 'Uses pattern matching algorithms and code analysis tools. Incorporates pattern catalog from Gang of Four, Martin Fowler, and cloud-native patterns. Generates language-specific implementations.'
  },
  'Component Library Builder': {
    name: 'Component Library Builder',
    icon: Target,
    color: 'from-orange-500 to-orange-600',
    tagline: 'Automated reusable component generation',
    description: 'Create comprehensive component libraries from design systems and UI specifications. This agent generates React, Vue, or Angular components with TypeScript support, storybook documentation, and unit tests.',
    keyCapabilities: [
      'Generate framework-specific components (React, Vue, Angular)',
      'Create Storybook stories and documentation automatically',
      'Generate unit tests with high coverage',
      'Ensure design system consistency',
      'Build accessible components (ARIA, keyboard navigation)'
    ],
    benefits: [
      'Accelerate component development by 80%',
      'Ensure 100% design system compliance',
      'Achieve 90%+ test coverage automatically',
      'Reduce UI inconsistencies by 95%'
    ],
    useCases: [
      'Design system implementation',
      'Component library creation',
      'UI framework migration',
      'White-label product development'
    ],
    technicalDetails: 'Uses AST (Abstract Syntax Tree) manipulation for code generation. Integrates with Figma, Sketch APIs for design token extraction. Implements template engines for multiple frameworks.'
  },
  // RELIABILITY AGENTS
  'Test Data Generator': {
    name: 'Test Data Generator',
    icon: ClipboardCheck,
    color: 'from-violet-500 to-violet-600',
    tagline: 'Generate structured test data from test cases automatically',
    description: 'The Test Data Generator agent creates comprehensive, structured test data from your test cases using AI. It analyzes test case descriptions, identifies required data fields, and generates realistic test data in JSON or Excel format, ensuring thorough coverage of edge cases, boundary values, and negative scenarios.',
    keyCapabilities: [
      'Automated test data generation from test case descriptions',
      'Support for JSON and Excel (XLSX) output formats',
      'Intelligent data field identification and realistic value generation',
      'Edge case and boundary value data generation',
      'Bulk processing of multiple test cases simultaneously'
    ],
    benefits: [
      'Reduce test data preparation time by 90%',
      'Ensure comprehensive data coverage for all scenarios',
      'Eliminate manual data creation errors',
      'Generate consistent, repeatable test datasets'
    ],
    useCases: [
      'Functional testing data preparation',
      'API testing with realistic payloads',
      'Database testing with structured datasets',
      'Performance testing data generation at scale'
    ],
    technicalDetails: 'Powered by Vertex AI for intelligent data field extraction and value generation. Processes test cases in bulk with support for complex data relationships and constraints. Outputs in JSON or Excel format for seamless integration with test automation frameworks.'
  },
  'RCA Agent': {
    name: 'RCA Agent',
    icon: Search,
    color: 'from-red-500 to-red-600',
    tagline: 'AI-powered root cause analysis for faster incident resolution',
    description: 'The RCA Agent employs advanced machine learning algorithms to automatically investigate incidents, analyze system logs, trace dependencies, and identify root causes. It correlates data across multiple sources to pinpoint the exact origin of failures, reducing mean time to resolution (MTTR) by up to 80%.',
    keyCapabilities: [
      'Automated log analysis across distributed systems with anomaly detection',
      'Dependency graph traversal to identify cascading failure points',
      'Pattern recognition to match incidents with historical root causes',
      'Real-time correlation of metrics, logs, and traces',
      'Generate comprehensive RCA reports with actionable remediation steps'
    ],
    benefits: [
      'Reduce MTTR by 80% with automated investigation',
      'Eliminate manual log analysis saving 10+ hours per incident',
      'Identify 95% of root causes within 5 minutes',
      'Prevent recurring incidents with pattern-based insights'
    ],
    useCases: [
      'Production incident investigation',
      'Post-mortem analysis automation',
      'Proactive failure pattern detection',
      'Multi-service dependency issue resolution'
    ],
    technicalDetails: 'Powered by causal inference algorithms and graph neural networks for dependency analysis. Integrates with observability platforms (Datadog, New Relic, Prometheus) and log aggregation systems (ELK, Splunk). Uses time-series analysis with LSTM networks for anomaly correlation.'
  },
  'Observability Agent': {
    name: 'Observability Agent',
    icon: Eye,
    color: 'from-blue-500 to-blue-600',
    tagline: 'Real-time monitoring with intelligent insights',
    description: 'The Observability Agent provides comprehensive system visibility through intelligent monitoring of metrics, logs, and traces. It automatically discovers services, establishes baselines, and alerts on anomalies while offering actionable insights into system health and performance.',
    keyCapabilities: [
      'Automatic service discovery and dependency mapping',
      'Dynamic baseline establishment with ML-driven anomaly detection',
      'Distributed tracing across microservices architectures',
      'Real-time performance metrics with intelligent alerting',
      'Predictive analytics for capacity and performance trends'
    ],
    benefits: [
      'Achieve complete system visibility in under 10 minutes',
      'Reduce false alerts by 90% with intelligent thresholds',
      'Detect performance degradation 15 minutes before user impact',
      'Decrease incident detection time from hours to seconds'
    ],
    useCases: [
      'Microservices monitoring and tracing',
      'Application performance management (APM)',
      'Infrastructure health monitoring',
      'SLA compliance tracking'
    ],
    technicalDetails: 'Built on OpenTelemetry standards with custom anomaly detection using isolation forests and autoencoders. Implements distributed tracing with Jaeger/Zipkin integration. Uses time-series databases (InfluxDB, TimescaleDB) for metrics storage and Prometheus for real-time monitoring.'
  },
  'Self-Heal Agent': {
    name: 'Self-Heal Agent',
    icon: RefreshCw,
    color: 'from-emerald-500 to-emerald-600',
    tagline: 'Autonomous remediation for zero-touch operations',
    description: 'The Self-Heal Agent automatically detects, diagnoses, and remediates common system issues without human intervention. It executes pre-approved remediation playbooks, validates fixes, and escalates complex issues while learning from each resolution to improve over time.',
    keyCapabilities: [
      'Automated issue detection and classification',
      'Intelligent playbook execution with rollback capabilities',
      'Progressive remediation with validation checkpoints',
      'Self-learning from successful and failed remediation attempts',
      'Safe-mode operation with approval gates for critical changes'
    ],
    benefits: [
      'Achieve 99.99% uptime with autonomous healing',
      'Resolve 70% of incidents without human intervention',
      'Reduce incident response time from hours to minutes',
      'Save 40+ hours per week on manual remediation tasks'
    ],
    useCases: [
      'Automatic service restart and recovery',
      'Resource scaling and optimization',
      'Configuration drift correction',
      'Database connection pool management'
    ],
    technicalDetails: 'Implements reinforcement learning for remediation strategy optimization. Uses Ansible/Terraform for infrastructure automation and Kubernetes operators for container orchestration. Integrates with ChatOps platforms (Slack, Teams) for approval workflows and notifications.'
  },
  'Incident Detector': {
    name: 'Incident Detector',
    icon: AlertTriangle,
    color: 'from-orange-500 to-orange-600',
    tagline: 'Early warning system with predictive alerting',
    description: 'The Incident Detector continuously monitors system health using advanced ML models to identify anomalies and predict failures before they impact users. It provides intelligent, context-aware alerts with prioritization to reduce alert fatigue and ensure rapid response.',
    keyCapabilities: [
      'Multi-dimensional anomaly detection across metrics, logs, and traces',
      'Predictive alerting 10-30 minutes before critical failures',
      'Intelligent alert correlation to reduce noise by 85%',
      'Context-enriched notifications with impact assessment',
      'Adaptive thresholds that learn from system behavior'
    ],
    benefits: [
      'Detect incidents 30 minutes before user impact',
      'Reduce alert fatigue by 85% with smart correlation',
      'Improve incident response time by 60%',
      'Prevent 50% of potential outages with early detection'
    ],
    useCases: [
      'Proactive incident prevention',
      'SLA violation prediction',
      'Performance degradation early warning',
      'Security threat detection'
    ],
    technicalDetails: 'Uses ensemble models combining ARIMA, Prophet, and LSTM for time-series prediction. Implements clustering algorithms (DBSCAN, K-means) for alert correlation. Integrates with PagerDuty, OpsGenie for incident management workflows.'
  },
  'Monitoring Agent': {
    name: 'Monitoring Agent',
    icon: Activity,
    color: 'from-purple-500 to-purple-600',
    tagline: 'Intelligent performance tracking and optimization',
    description: 'The Monitoring Agent provides continuous performance tracking with intelligent insights into application and infrastructure health. It automatically identifies performance bottlenecks, suggests optimizations, and tracks SLO/SLA compliance with detailed reporting.',
    keyCapabilities: [
      'Real-time application and infrastructure performance metrics',
      'Automatic bottleneck identification and performance profiling',
      'SLO/SLA tracking with budget alerts and burn-rate analysis',
      'Custom dashboard generation based on service criticality',
      'Performance trend analysis with capacity forecasting'
    ],
    benefits: [
      'Improve application performance by 40% with targeted optimizations',
      'Achieve 100% SLA compliance with proactive monitoring',
      'Reduce monitoring setup time by 90% with auto-configuration',
      'Save 20+ hours per month on manual performance analysis'
    ],
    useCases: [
      'Application performance optimization',
      'SLA/SLO compliance monitoring',
      'Capacity planning and forecasting',
      'Business KPI tracking'
    ],
    technicalDetails: 'Built on Prometheus and Grafana stack with custom exporters for application metrics. Uses statistical process control (SPC) for performance baseline tracking. Implements CUSUM and Bollinger Bands for trend detection and alerting.'
  },
  'Capacity Agent': {
    name: 'Capacity Agent',
    icon: Server,
    color: 'from-indigo-500 to-indigo-600',
    tagline: 'Predictive capacity planning and auto-scaling',
    description: 'The Capacity Agent analyzes historical usage patterns and predicts future resource requirements to ensure optimal capacity allocation. It provides recommendations for scaling decisions and automates resource provisioning to maintain performance while optimizing costs.',
    keyCapabilities: [
      'Predictive capacity forecasting using ML time-series models',
      'Automated scaling recommendations based on traffic patterns',
      'Cost optimization through right-sizing analysis',
      'What-if scenario modeling for capacity planning',
      'Multi-cloud resource optimization'
    ],
    benefits: [
      'Reduce infrastructure costs by 35% through optimal sizing',
      'Prevent capacity-related outages with 95% forecast accuracy',
      'Automate 80% of scaling decisions',
      'Save 15+ hours per month on capacity planning'
    ],
    useCases: [
      'Auto-scaling strategy optimization',
      'Black Friday / peak traffic planning',
      'Multi-region capacity allocation',
      'Cloud cost optimization'
    ],
    technicalDetails: 'Uses SARIMA and Prophet for seasonal demand forecasting. Implements multi-objective optimization for cost vs. performance trade-offs. Integrates with cloud provider APIs (AWS, Azure, GCP) for automated provisioning. Uses reinforcement learning for scaling policy optimization.'
  },
  // SECURITY AGENTS
  'Vulnerability Scanner': {
    name: 'Vulnerability Scanner',
    icon: Shield,
    color: 'from-teal-500 to-teal-600',
    tagline: 'Comprehensive security vulnerability detection',
    description: 'The Vulnerability Scanner performs continuous security assessments across your codebase, dependencies, containers, and infrastructure. It identifies known CVEs, misconfigurations, and security weaknesses while prioritizing findings based on exploitability and business impact.',
    keyCapabilities: [
      'Automated scanning of code, dependencies, and container images',
      'CVE database integration with real-time vulnerability feeds',
      'OWASP Top 10 and CWE pattern detection',
      'Risk-based prioritization with CVSS scoring',
      'Integration with CI/CD pipelines for shift-left security'
    ],
    benefits: [
      'Detect 95% of vulnerabilities before production deployment',
      'Reduce security scan time from hours to minutes',
      'Prioritize critical vulnerabilities with 99% accuracy',
      'Achieve continuous compliance with automated scanning'
    ],
    useCases: [
      'Continuous security scanning in CI/CD',
      'Third-party dependency auditing',
      'Container image security validation',
      'Infrastructure as Code (IaC) security checks'
    ],
    technicalDetails: 'Integrates with Snyk, Trivy, and OWASP Dependency-Check. Uses static application security testing (SAST) with SonarQube and Checkmarx. Implements dynamic analysis (DAST) with OWASP ZAP. Leverages NVD and vendor security advisories for CVE intelligence.'
  },
  'Threat Analyzer': {
    name: 'Threat Analyzer',
    icon: Eye,
    color: 'from-red-500 to-red-600',
    tagline: 'AI-powered threat intelligence and detection',
    description: 'The Threat Analyzer continuously monitors for security threats using advanced behavioral analysis and threat intelligence feeds. It identifies suspicious activities, potential attacks, and zero-day exploits while providing actionable intelligence for incident response.',
    keyCapabilities: [
      'Real-time threat detection using behavioral analytics',
      'Integration with global threat intelligence feeds',
      'Advanced persistent threat (APT) detection',
      'User and entity behavior analytics (UEBA)',
      'Automated threat hunting and investigation'
    ],
    benefits: [
      'Detect zero-day threats 70% faster than traditional methods',
      'Reduce false positives by 80% with ML-based analysis',
      'Identify compromised accounts within minutes',
      'Prevent 90% of targeted attacks with early detection'
    ],
    useCases: [
      'Advanced threat detection and response',
      'Insider threat monitoring',
      'Zero-day exploit detection',
      'Security incident investigation'
    ],
    technicalDetails: 'Uses machine learning models trained on MITRE ATT&CK framework. Integrates with SIEM platforms (Splunk, Elastic Security). Implements graph-based attack path analysis and kill chain modeling. Leverages threat intelligence platforms (ThreatConnect, MISP).'
  },
  'Compliance Checker': {
    name: 'Compliance Checker',
    icon: Lock,
    color: 'from-blue-500 to-blue-600',
    tagline: 'Automated compliance validation and enforcement',
    description: 'The Compliance Checker ensures continuous compliance with security standards and regulations including SOC2, HIPAA, GDPR, and PCI-DSS. It automatically validates controls, generates evidence, and creates audit-ready reports while tracking compliance drift.',
    keyCapabilities: [
      'Automated compliance checks for SOC2, HIPAA, GDPR, PCI-DSS',
      'Continuous control validation and evidence collection',
      'Compliance drift detection with automatic remediation',
      'Audit-ready report generation',
      'Policy-as-code enforcement'
    ],
    benefits: [
      'Achieve 100% compliance with automated validation',
      'Reduce audit preparation time by 70%',
      'Detect compliance violations within minutes',
      'Save 30+ hours per month on compliance reporting'
    ],
    useCases: [
      'Regulatory compliance automation',
      'Security control validation',
      'Audit preparation and evidence collection',
      'Policy enforcement across environments'
    ],
    technicalDetails: 'Implements compliance-as-code using Open Policy Agent (OPA) and Cloud Custodian. Integrates with security frameworks (CIS Benchmarks, NIST). Uses evidence collection automation with Drata, Vanta integration. Generates compliance reports in multiple formats.'
  },
  'Secret Manager': {
    name: 'Secret Manager',
    icon: Key,
    color: 'from-purple-500 to-purple-600',
    tagline: 'Intelligent secret detection and lifecycle management',
    description: 'The Secret Manager automatically detects, rotates, and manages secrets across your codebase and infrastructure. It scans for exposed credentials, enforces secret policies, and integrates with vault solutions to ensure secure secret management practices.',
    keyCapabilities: [
      'Automated secret detection in code, logs, and configuration',
      'Secret rotation with zero-downtime deployment',
      'Integration with HashiCorp Vault, AWS Secrets Manager',
      'Policy enforcement for secret complexity and expiration',
      'Secret sprawl detection and remediation'
    ],
    benefits: [
      'Detect 100% of exposed secrets before they reach production',
      'Automate secret rotation saving 15+ hours per month',
      'Prevent credential-based breaches with policy enforcement',
      'Achieve complete secret lifecycle visibility'
    ],
    useCases: [
      'Secret scanning in Git repositories',
      'Automated credential rotation',
      'Secret centralization and management',
      'Compliance with secret management policies'
    ],
    technicalDetails: 'Uses regex patterns and entropy analysis for secret detection. Integrates with GitGuardian, TruffleHog for repository scanning. Implements automated rotation workflows with HashiCorp Vault, AWS Secrets Manager, Azure Key Vault. Supports just-in-time secret provisioning.'
  },
  'Penetration Tester': {
    name: 'Penetration Tester',
    icon: Bug,
    color: 'from-orange-500 to-orange-600',
    tagline: 'Automated penetration testing and security validation',
    description: 'The Penetration Tester performs continuous security assessments by simulating real-world attacks against your applications and infrastructure. It identifies exploitable vulnerabilities, validates security controls, and provides remediation guidance.',
    keyCapabilities: [
      'Automated penetration testing with OWASP testing guides',
      'API security testing and fuzzing',
      'Authentication and authorization bypass testing',
      'SQL injection and XSS vulnerability exploitation',
      'Network penetration testing and lateral movement simulation'
    ],
    benefits: [
      'Identify exploitable vulnerabilities before attackers do',
      'Reduce penetration testing costs by 60%',
      'Validate security fixes with automated retesting',
      'Continuous security validation in CI/CD pipelines'
    ],
    useCases: [
      'Web application security testing',
      'API security validation',
      'Pre-production security assessment',
      'Red team automation'
    ],
    technicalDetails: 'Built on OWASP ZAP, Burp Suite APIs, and Metasploit framework. Implements intelligent fuzzing with AFL and custom payload generation. Uses ML for attack path optimization. Integrates with bug bounty platforms for vulnerability reporting.'
  },
  'Incident Responder': {
    name: 'Incident Responder',
    icon: AlertCircle,
    color: 'from-rose-500 to-rose-600',
    tagline: 'Automated security incident response and containment',
    description: 'The Incident Responder automatically detects, contains, and remediates security incidents using pre-defined playbooks and AI-driven decision making. It orchestrates response actions, collects forensic evidence, and coordinates with security teams for rapid incident resolution.',
    keyCapabilities: [
      'Automated incident detection and classification',
      'Intelligent playbook execution for common attack scenarios',
      'Automatic threat containment and isolation',
      'Forensic evidence collection and chain of custody',
      'Post-incident analysis and lessons learned generation'
    ],
    benefits: [
      'Reduce security incident response time by 75%',
      'Contain threats within minutes instead of hours',
      'Automate 60% of incident response tasks',
      'Maintain complete forensic audit trail'
    ],
    useCases: [
      'Malware outbreak containment',
      'Compromised account remediation',
      'Data breach response',
      'Ransomware attack mitigation'
    ],
    technicalDetails: 'Integrates with SOAR platforms (Palo Alto XSOAR, Splunk Phantom). Implements NIST incident response framework automation. Uses ML for incident classification and priority assignment. Connects with EDR solutions (CrowdStrike, SentinelOne) for endpoint isolation.'
  },
  // GOVERNANCE AGENTS
  'Policy Enforcer': {
    name: 'Policy Enforcer',
    icon: Target,
    color: 'from-violet-500 to-violet-600',
    tagline: 'Automated policy compliance and enforcement',
    description: 'The Policy Enforcer ensures organizational policies are consistently applied across all environments and teams. It validates changes against policy rules, prevents non-compliant deployments, and provides real-time policy violation alerts with remediation guidance.',
    keyCapabilities: [
      'Policy-as-code definition and version control',
      'Real-time policy validation in CI/CD pipelines',
      'Automated policy enforcement with preventive controls',
      'Policy violation detection and reporting',
      'Multi-environment policy management'
    ],
    benefits: [
      'Achieve 100% policy compliance across all environments',
      'Prevent non-compliant changes before deployment',
      'Reduce policy violations by 90%',
      'Save 25+ hours per month on manual policy reviews'
    ],
    useCases: [
      'Infrastructure policy enforcement',
      'Security baseline validation',
      'Change management compliance',
      'Resource tagging and naming standards'
    ],
    technicalDetails: 'Built on Open Policy Agent (OPA) with Rego policy language. Integrates with Kubernetes admission controllers, Terraform Sentinel, and AWS Config. Implements policy testing frameworks and continuous policy validation. Supports hierarchical policy inheritance.'
  },
  'Audit Trail Generator': {
    name: 'Audit Trail Generator',
    icon: FileCheck,
    color: 'from-blue-500 to-blue-600',
    tagline: 'Comprehensive audit logging and compliance reporting',
    description: 'The Audit Trail Generator automatically captures, indexes, and analyzes all system activities to create comprehensive audit trails. It ensures tamper-proof logging, generates compliance reports, and provides forensic analysis capabilities for security and compliance teams.',
    keyCapabilities: [
      'Automated capture of all system and user activities',
      'Tamper-proof audit log storage with cryptographic validation',
      'Intelligent log correlation and pattern detection',
      'Compliance report generation (SOX, HIPAA, SOC2)',
      'Advanced search and filtering for forensic investigation'
    ],
    benefits: [
      'Achieve 100% activity visibility with automated logging',
      'Reduce audit preparation time by 80%',
      'Ensure tamper-proof audit evidence',
      'Generate compliance reports in minutes instead of days'
    ],
    useCases: [
      'Regulatory audit preparation',
      'Security incident investigation',
      'Change tracking and accountability',
      'Compliance reporting automation'
    ],
    technicalDetails: 'Implements write-once-read-many (WORM) storage with blockchain-based integrity verification. Uses centralized logging with ELK, Splunk integration. Implements log enrichment with contextual metadata. Supports SIEM integration for security correlation.'
  },
  'Risk Assessor': {
    name: 'Risk Assessor',
    icon: TrendingUp,
    color: 'from-orange-500 to-orange-600',
    tagline: 'AI-powered risk analysis and mitigation',
    description: 'The Risk Assessor continuously evaluates technical, security, and business risks across your software lifecycle. It uses predictive analytics to identify emerging risks, assesses impact and likelihood, and recommends prioritized mitigation strategies.',
    keyCapabilities: [
      'Automated risk identification across multiple dimensions',
      'Quantitative risk scoring using FAIR methodology',
      'Risk trend analysis and predictive modeling',
      'Impact assessment with business context',
      'Mitigation strategy recommendations with cost-benefit analysis'
    ],
    benefits: [
      'Reduce overall risk exposure by 60%',
      'Identify emerging risks 30 days earlier',
      'Prioritize mitigation efforts with data-driven insights',
      'Save 20+ hours per month on risk assessments'
    ],
    useCases: [
      'Continuous risk assessment',
      'Third-party vendor risk evaluation',
      'Change impact risk analysis',
      'Security risk quantification'
    ],
    technicalDetails: 'Implements FAIR (Factor Analysis of Information Risk) quantitative model. Uses Monte Carlo simulation for risk modeling. Integrates with vulnerability management and threat intelligence platforms. Supports risk register automation and heat map generation.'
  },
  'Access Controller': {
    name: 'Access Controller',
    icon: Users,
    color: 'from-purple-500 to-purple-600',
    tagline: 'Intelligent access control and permissions management',
    description: 'The Access Controller manages user access rights with intelligent recommendations based on role, context, and risk. It enforces least privilege principles, detects permission anomalies, and automates access reviews to ensure appropriate authorization across all systems.',
    keyCapabilities: [
      'Role-based access control (RBAC) automation',
      'Intelligent access recommendations based on peer analysis',
      'Automated access certification and reviews',
      'Privilege escalation detection',
      'Just-in-time (JIT) access provisioning'
    ],
    benefits: [
      'Reduce over-privileged accounts by 70%',
      'Automate 90% of access review processes',
      'Detect unauthorized access within seconds',
      'Save 30+ hours per month on access management'
    ],
    useCases: [
      'User access provisioning and deprovisioning',
      'Periodic access reviews and certification',
      'Privileged access management',
      'Separation of duties enforcement'
    ],
    technicalDetails: 'Implements attribute-based access control (ABAC) and policy-based access control (PBAC). Integrates with identity providers (Okta, Azure AD, Auth0). Uses graph analysis for access path discovery. Supports zero trust architecture with continuous verification.'
  },
  'Compliance Monitor': {
    name: 'Compliance Monitor',
    icon: Shield,
    color: 'from-emerald-500 to-emerald-600',
    tagline: 'Real-time compliance monitoring and alerts',
    description: 'The Compliance Monitor provides continuous compliance monitoring across all systems and environments. It tracks compliance status in real-time, detects drift from standards, and alerts teams immediately when violations occur with automated remediation suggestions.',
    keyCapabilities: [
      'Real-time compliance status tracking across frameworks',
      'Automated compliance drift detection',
      'Proactive alerts for compliance violations',
      'Compliance dashboard with executive reporting',
      'Automated remediation workflow triggering'
    ],
    benefits: [
      'Maintain 99.9% compliance posture',
      'Detect compliance drift within minutes',
      'Reduce compliance violations by 85%',
      'Generate real-time compliance reports for stakeholders'
    ],
    useCases: [
      'Continuous compliance monitoring',
      'Regulatory change impact assessment',
      'Multi-framework compliance tracking',
      'Executive compliance dashboard'
    ],
    technicalDetails: 'Uses event-driven architecture with real-time stream processing. Integrates with compliance automation platforms (Drata, Vanta, Secureframe). Implements compliance scoring algorithms. Supports multiple frameworks (SOC2, ISO 27001, GDPR, HIPAA).'
  },
  'Quality Gate Validator': {
    name: 'Quality Gate Validator',
    icon: ClipboardCheck,
    color: 'from-cyan-500 to-cyan-600',
    tagline: 'Automated quality gates and validation',
    description: 'The Quality Gate Validator enforces quality standards at every stage of the software delivery pipeline. It validates code quality, test coverage, security scans, and compliance checks before allowing progression, ensuring only production-ready code advances.',
    keyCapabilities: [
      'Multi-criteria quality gate definition and enforcement',
      'Automated quality checks in CI/CD pipelines',
      'Code quality analysis with technical debt assessment',
      'Test coverage and quality validation',
      'Security and compliance gate integration'
    ],
    benefits: [
      'Reduce production defects by 65%',
      'Prevent 95% of quality issues from reaching production',
      'Ensure consistent quality standards across teams',
      'Decrease rollback rate by 75%'
    ],
    useCases: [
      'CI/CD quality gate enforcement',
      'Release readiness validation',
      'Technical debt prevention',
      'Multi-stage approval workflows'
    ],
    technicalDetails: 'Integrates with SonarQube, CodeClimate for code quality metrics. Uses JUnit, pytest for test validation. Implements custom quality gate policies with configurable thresholds. Supports GitLab, Jenkins, GitHub Actions pipeline integration.'
  }
};

export function AgentDetailCard({ agent, onClose }: AgentDetailCardProps) {
  const Icon = agent.icon;
  
  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="relative w-full max-w-4xl bg-gradient-to-br from-[#0f1e36] via-[#132340] to-[#0a1628] rounded-xl shadow-2xl border border-cyan-500/30 my-8">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 w-8 h-8 bg-slate-800/80 hover:bg-slate-700 rounded-full flex items-center justify-center transition-all duration-300 group z-10"
        >
          <X className="w-4 h-4 text-gray-400 group-hover:text-white" />
        </button>

        <div className="p-6 md:p-8">
          {/* Header Section */}
          <div className="flex items-start gap-4 mb-6">
            <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${agent.color} flex items-center justify-center shadow-2xl flex-shrink-0`}>
              <Icon className="w-7 h-7 text-white" />
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-bold text-white mb-1">{agent.name}</h2>
              <p className="text-base text-cyan-300 font-light italic">{agent.tagline}</p>
            </div>
          </div>

          {/* Description */}
          <div className="mb-6">
            <p className="text-gray-300 text-sm leading-relaxed">
              {agent.description}
            </p>
          </div>

          {/* Three Column Layout */}
          <div className="grid md:grid-cols-3 gap-4 mb-6">
            {/* Key Capabilities */}
            <div className="bg-slate-900/50 backdrop-blur-sm rounded-lg p-4 border border-cyan-500/20">
              <div className="flex items-center gap-2 mb-3">
                <Zap className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-white">Key Capabilities</h3>
              </div>
              <ul className="space-y-2">
                {agent.keyCapabilities.map((capability, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <CheckCircle className="w-3 h-3 text-cyan-400 flex-shrink-0 mt-0.5" />
                    <span className="text-gray-300 text-xs leading-relaxed">{capability}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Benefits */}
            <div className="bg-slate-900/50 backdrop-blur-sm rounded-lg p-4 border border-emerald-500/20">
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                <h3 className="text-sm font-semibold text-white">Benefits</h3>
              </div>
              <ul className="space-y-2">
                {agent.benefits.map((benefit, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <CheckCircle className="w-3 h-3 text-emerald-400 flex-shrink-0 mt-0.5" />
                    <span className="text-gray-300 text-xs leading-relaxed">{benefit}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Use Cases */}
            <div className="bg-slate-900/50 backdrop-blur-sm rounded-lg p-4 border border-purple-500/20">
              <div className="flex items-center gap-2 mb-3">
                <Target className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-semibold text-white">Use Cases</h3>
              </div>
              <ul className="space-y-2">
                {agent.useCases.map((useCase, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <CheckCircle className="w-3 h-3 text-purple-400 flex-shrink-0 mt-0.5" />
                    <span className="text-gray-300 text-xs leading-relaxed">{useCase}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Technical Details */}
          <div className="bg-gradient-to-r from-slate-900/80 to-slate-800/80 backdrop-blur-sm rounded-lg p-4 border border-blue-500/30">
            <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
              <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
              Technical Architecture
            </h3>
            <p className="text-gray-300 text-xs leading-relaxed">
              {agent.technicalDetails}
            </p>
          </div>

          {/* Action Button */}
          <div className="mt-6 flex justify-center">
            <button
              onClick={onClose}
              className="px-6 py-2 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-white text-sm font-semibold rounded-lg transition-all duration-300 shadow-lg hover:shadow-cyan-500/50"
            >
              Got it, thanks!
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}