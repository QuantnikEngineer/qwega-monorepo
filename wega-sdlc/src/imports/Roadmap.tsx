import { useState } from 'react';
import { motion } from 'motion/react';
import { ArrowRight } from 'lucide-react';

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

export default function Roadmap() {
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);
  const [hoveredPhase, setHoveredPhase] = useState<string | null>(null);

  const toggleSelection = (key: string) => {
    setSelectedItems((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(key)) {
        newSet.delete(key);
      } else {
        newSet.add(key);
      }
      return newSet;
    });
  };

  return (
    <div className="relative w-full flex items-center justify-center p-8 bg-card" data-name="Roadmap">
      <div className="bg-card p-8 text-foreground w-full">
        {/* Main Grid */}
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
  );
}
