import { Bug, Shield, Zap, CheckCircle, AlertTriangle, Activity, Home, Database } from 'lucide-react';
import { useState } from 'react';
import { AgentDetailCard, agentDetails } from './AgentDetailCard';
import { MiniSDLCJourney } from './MiniSDLCJourney';

const agents = [
  {
    name: 'Test Case Generator',
    icon: CheckCircle,
    color: 'from-cyan-500 to-cyan-600',
    description: 'Auto-generate comprehensive test cases'
  },
  {
    name: 'Test Data Generator',
    icon: Database,
    color: 'from-violet-500 to-violet-600',
    description: 'Generate structured test data from test cases'
  },
  {
    name: 'Bug Predictor',
    icon: Bug,
    color: 'from-red-500 to-red-600',
    description: 'Predict and prevent bugs before deployment'
  },
  {
    name: 'Test Coverage Analyzer',
    icon: AlertTriangle,
    color: 'from-emerald-500 to-emerald-600',
    description: 'Analyze and improve test coverage'
  },
  {
    name: 'Performance Tester',
    icon: Zap,
    color: 'from-orange-500 to-orange-600',
    description: 'Automated performance and load testing'
  },
  {
    name: 'Security Tester',
    icon: Shield,
    color: 'from-purple-500 to-purple-600',
    description: 'Identify security vulnerabilities automatically'
  }
];

interface TestingDetailProps {
  onBack: () => void;
  onStageClick?: (stageName: string) => void;
  currentStage?: string;
}

export function TestingDetail({ onBack, onStageClick, currentStage = 'Testing' }: TestingDetailProps) {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  return (
    <div className="relative min-h-[600px] bg-gradient-to-br from-[#0a1628] via-[#132340] to-[#0f1e36] overflow-hidden">
      {/* Mini SDLC Journey at the top */}
      {onStageClick && (
        <MiniSDLCJourney currentStage={currentStage} onStageClick={onStageClick} />
      )}
      
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(120,119,198,0.05),transparent_50%)]"></div>
      
      <div className="container mx-auto px-6 py-16 relative z-10">
        <div className="mb-12 max-w-7xl mx-auto relative">
          <button
            onClick={onBack}
            className="mb-8 flex items-center gap-2 text-white hover:text-gray-300 transition-colors duration-300 group"
          >
            <div className="w-8 h-8 rounded flex items-center justify-center transition-all duration-300">
              <Home className="w-5 h-5" />
            </div>
            <span className="text-xs font-medium">Back to Home</span>
          </button>

          <div className="flex flex-col lg:flex-row gap-5 items-stretch">
            {/* Left: Title and Description */}
            <div className="lg:w-[22%] flex flex-col">
              <div>
                <h1 className="text-2xl lg:text-3xl bg-gradient-to-r from-cyan-600 to-cyan-300 bg-clip-text text-transparent mb-8 font-normal">
                  Testing
                </h1>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">
                  Enhance your testing process with AI-powered agents that generate test cases, predict bugs, and ensure comprehensive coverage. Our intelligent testing suite automates tedious testing tasks and identifies issues before they reach production.
                </p>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">
                  The Testing Orchestrator coordinates specialized agents to execute comprehensive quality assurance workflows. From unit tests to security assessments, each agent ensures your software meets the highest quality standards.
                </p>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed">
                  Our AI-driven testing approach combines test generation, bug prediction, coverage analysis, and performance validation to deliver defect-free software with confidence and speed.
                </p>
              </div>
            </div>

            {/* Middle: Testing Flow Diagram */}
            <div className="lg:w-[40%] flex items-start justify-center mt-6">
              <div className="relative w-full max-w-full overflow-hidden">
                <div className="relative bg-gradient-to-br from-slate-900/80 to-slate-800/80 backdrop-blur-sm rounded-2xl p-6 border border-cyan-500/30 shadow-2xl">
                  <svg className="w-full h-auto" viewBox="0 0 440 400" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
                    <defs>
                      <linearGradient id="cyanFlowTest" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(6, 182, 212, 0)" />
                        <stop offset="50%" stopColor="rgba(6, 182, 212, 1)" />
                        <stop offset="100%" stopColor="rgba(6, 182, 212, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      <linearGradient id="redFlowTest" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(239, 68, 68, 0)" />
                        <stop offset="50%" stopColor="rgba(239, 68, 68, 1)" />
                        <stop offset="100%" stopColor="rgba(239, 68, 68, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="2.5s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="2.5s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      <linearGradient id="emeraldFlowTest" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(16, 185, 129, 0)" />
                        <stop offset="50%" stopColor="rgba(16, 185, 129, 1)" />
                        <stop offset="100%" stopColor="rgba(16, 185, 129, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3.5s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3.5s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      <filter id="testGlow">
                        <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                        <feMerge>
                          <feMergeNode in="coloredBlur"/>
                          <feMergeNode in="SourceGraphic"/>
                        </feMerge>
                      </filter>
                    </defs>
                    
                    {/* Testing Orchestrator - Left Center */}
                    <rect x="20" y="165" width="100" height="60" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#testGlow)"/>
                    <text x="70" y="187" textAnchor="middle" fill="white" fontSize="12" fontWeight="400">Testing</text>
                    <text x="70" y="203" textAnchor="middle" fill="white" fontSize="12" fontWeight="400">Orchestrator</text>
                    
                    {/* Test Case Generator - Top */}
                    <rect x="180" y="15" width="110" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#testGlow)"/>
                    <text x="235" y="33" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Test Case</text>
                    <text x="235" y="47" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Generator</text>
                    
                    {/* Bug Predictor */}
                    <rect x="180" y="75" width="110" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#testGlow)"/>
                    <text x="235" y="93" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Bug</text>
                    <text x="235" y="107" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Predictor</text>
                    
                    {/* Test Coverage Analyzer */}
                    <rect x="180" y="135" width="110" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#testGlow)"/>
                    <text x="235" y="153" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Test Coverage</text>
                    <text x="235" y="167" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Analyzer</text>
                    
                    {/* Performance Tester */}
                    <rect x="180" y="195" width="110" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#testGlow)"/>
                    <text x="235" y="213" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Performance</text>
                    <text x="235" y="227" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Tester</text>
                    
                    {/* Security Tester */}
                    <rect x="180" y="255" width="110" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#testGlow)"/>
                    <text x="235" y="273" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Security</text>
                    <text x="235" y="287" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Tester</text>
                    
                    {/* Test Data Generator */}
                    <rect x="180" y="315" width="110" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#testGlow)"/>
                    <text x="235" y="333" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Test Data</text>
                    <text x="235" y="347" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Generator</text>
                    
                    {/* Output: Quality Report - Right */}
                    <rect x="320" y="170" width="100" height="60" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#testGlow)"/>
                    <text x="370" y="192" textAnchor="middle" fill="white" fontSize="11" fontWeight="400">Quality</text>
                    <text x="370" y="208" textAnchor="middle" fill="white" fontSize="11" fontWeight="400">Report</text>
                    
                    {/* Flowing connection lines from Orchestrator to agents */}
                    <path d="M 120 175 Q 150 40, 180 40" fill="none" stroke="url(#cyanFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 183 Q 150 100, 180 100" fill="none" stroke="url(#cyanFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 191 Q 150 160, 180 160" fill="none" stroke="url(#cyanFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 199 Q 150 220, 180 220" fill="none" stroke="url(#cyanFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 207 Q 150 280, 180 280" fill="none" stroke="url(#cyanFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 215 Q 150 340, 180 340" fill="none" stroke="url(#cyanFlowTest)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Vertical red flows in middle column */}
                    <line x1="235" y1="65" x2="235" y2="75" stroke="url(#redFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="125" x2="235" y2="135" stroke="url(#redFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="185" x2="235" y2="195" stroke="url(#redFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="245" x2="235" y2="255" stroke="url(#redFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="305" x2="235" y2="315" stroke="url(#redFlowTest)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Emerald flows from middle column agents to output */}
                    <path d="M 290 40 Q 305 40, 305 120 Q 305 200, 320 200" fill="none" stroke="url(#emeraldFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 100 Q 300 100, 300 150 Q 300 200, 320 200" fill="none" stroke="url(#emeraldFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 160 Q 300 160, 300 180 Q 300 200, 320 200" fill="none" stroke="url(#emeraldFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 220 Q 300 220, 300 210 Q 300 200, 320 200" fill="none" stroke="url(#emeraldFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 280 Q 305 280, 305 240 Q 305 200, 320 200" fill="none" stroke="url(#emeraldFlowTest)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 340 Q 310 340, 310 270 Q 310 200, 320 200" fill="none" stroke="url(#emeraldFlowTest)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Directional Arrows */}
                    <polygon points="235,77 230,72 240,72" fill="#06b6d4" filter="url(#testGlow)"/>
                    <polygon points="235,137 230,132 240,132" fill="#06b6d4" filter="url(#testGlow)"/>
                    <polygon points="235,197 230,192 240,192" fill="#06b6d4" filter="url(#testGlow)"/>
                    <polygon points="235,257 230,252 240,252" fill="#06b6d4" filter="url(#testGlow)"/>
                    <polygon points="235,317 230,312 240,312" fill="#06b6d4" filter="url(#testGlow)"/>
                    <polygon points="318,198 314,195 314,201" fill="#10b981" filter="url(#testGlow)"/>
                    
                    {/* Animated particles */}
                    <circle r="4" fill="#06b6d4" opacity="0.8">
                      <animateMotion dur="3s" repeatCount="indefinite" path="M 120 175 Q 150 40, 190 40"/>
                    </circle>
                    <circle r="4" fill="#06b6d4" opacity="0.8">
                      <animateMotion dur="3s" repeatCount="indefinite" path="M 120 207 Q 150 280, 190 280"/>
                    </circle>
                    <circle r="4" fill="#ef4444" opacity="0.8">
                      <animateMotion dur="2.5s" repeatCount="indefinite" path="M 235 65 L 235 305"/>
                    </circle>
                    <circle r="4" fill="#10b981" opacity="0.8">
                      <animateMotion dur="3.5s" repeatCount="indefinite" path="M 290 200 L 320 200"/>
                    </circle>
                  </svg>
                </div>
              </div>
            </div>

            {/* Right: Benefits Cards */}
            <div className="flex flex-col justify-between lg:w-[32%] mt-6 h-full">
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-cyan-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-cyan-300 font-bold text-lg mb-3">85% Faster Testing</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Automate test creation and execution with AI</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-emerald-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1 my-3">
                <h3 className="text-emerald-300 font-bold text-lg mb-3">95% Coverage</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Achieve comprehensive test coverage automatically</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-red-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-red-300 font-bold text-lg mb-3">70% Fewer Defects</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Catch bugs before they reach production</p>
              </div>
            </div>
          </div>
        </div>

        {/* Agents Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          {agents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div
                key={agent.name}
                className="bg-[#1a2642]/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6 hover:border-cyan-500/30 transition-all duration-300 hover:shadow-lg hover:shadow-cyan-500/10 cursor-pointer hover:scale-105"
                onClick={() => setSelectedAgent(agent.name)}
              >
                <div className="flex items-start gap-4">
                  <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${agent.color} flex items-center justify-center shadow-lg flex-shrink-0`}>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  <div className="flex-1">
                    <h3 className="text-white font-semibold text-base mb-2">{agent.name}</h3>
                    <p className="text-gray-400 text-sm leading-relaxed">{agent.description}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {selectedAgent && agentDetails[selectedAgent] && (
          <AgentDetailCard
            agent={agentDetails[selectedAgent]}
            onClose={() => setSelectedAgent(null)}
          />
        )}
      </div>
    </div>
  );
}