import { Code2, GitBranch, CheckCircle, Zap, RefreshCw, Cpu, Home } from 'lucide-react';
import { useState } from 'react';
import { AgentDetailCard, agentDetails } from './AgentDetailCard';
import { MiniSDLCJourney } from './MiniSDLCJourney';

const agents = [
  {
    name: 'Code Generator',
    icon: Code2,
    color: 'from-blue-500 to-blue-600',
    description: 'AI-powered code generation from specifications'
  },
  {
    name: 'Code Reviewer',
    icon: GitBranch,
    color: 'from-purple-500 to-purple-600',
    description: 'Automated code review and quality analysis'
  },
  {
    name: 'Refactoring Assistant',
    icon: RefreshCw,
    color: 'from-cyan-500 to-cyan-600',
    description: 'Intelligent code refactoring recommendations'
  },
  {
    name: 'Unit Test Generator',
    icon: Zap,
    color: 'from-emerald-500 to-emerald-600',
    description: 'Auto-generate comprehensive unit tests'
  },
  {
    name: 'Documentation Generator',
    icon: CheckCircle,
    color: 'from-indigo-500 to-indigo-600',
    description: 'Create technical documentation automatically'
  },
  {
    name: 'Performance Optimizer',
    icon: Cpu,
    color: 'from-orange-500 to-orange-600',
    description: 'Identify and fix performance bottlenecks'
  }
];

interface BuildDetailProps {
  onBack: () => void;
  onStageClick?: (stageName: string) => void;
  currentStage?: string;
}

export function BuildDetail({ onBack, onStageClick, currentStage = 'Build' }: BuildDetailProps) {
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
                <h1 className="text-2xl lg:text-3xl bg-gradient-to-r from-blue-600 to-blue-300 bg-clip-text text-transparent mb-8 font-normal">
                  Build
                </h1>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">
                  Accelerate your development process with AI-powered agents that write, review, and optimize code. Our intelligent build suite automates repetitive coding tasks, ensures code quality, and generates comprehensive tests and documentation.
                </p>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">
                  The Build Orchestrator coordinates multiple specialized agents to generate production-ready code, conduct thorough reviews, and optimize performance. Each agent brings expertise to ensure code is clean, efficient, and well-documented.
                </p>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed">
                  From initial code generation to final optimization, our agents work in harmony to deliver high-quality, maintainable code that meets industry standards and best practices while dramatically reducing development time.
                </p>
              </div>
            </div>

            {/* Middle: Build Flow Diagram */}
            <div className="lg:w-[40%] flex items-start justify-center mt-6">
              <div className="relative w-full max-w-full overflow-hidden">
                <div className="relative bg-gradient-to-br from-slate-900/80 to-slate-800/80 backdrop-blur-sm rounded-2xl p-6 border border-blue-500/30 shadow-2xl">
                  <svg className="w-full h-auto" viewBox="0 0 440 380" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
                    <defs>
                      <linearGradient id="blueFlowBuild" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(59, 130, 246, 0)" />
                        <stop offset="50%" stopColor="rgba(59, 130, 246, 1)" />
                        <stop offset="100%" stopColor="rgba(59, 130, 246, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      <linearGradient id="cyanFlowBuild" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(6, 182, 212, 0)" />
                        <stop offset="50%" stopColor="rgba(6, 182, 212, 1)" />
                        <stop offset="100%" stopColor="rgba(6, 182, 212, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="2.5s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="2.5s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      <linearGradient id="greenFlowBuild" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(16, 185, 129, 0)" />
                        <stop offset="50%" stopColor="rgba(16, 185, 129, 1)" />
                        <stop offset="100%" stopColor="rgba(16, 185, 129, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3.5s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3.5s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      <filter id="buildGlow">
                        <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                        <feMerge>
                          <feMergeNode in="coloredBlur"/>
                          <feMergeNode in="SourceGraphic"/>
                        </feMerge>
                      </filter>
                    </defs>
                    
                    {/* Build Orchestrator - Left Center */}
                    <rect x="20" y="160" width="100" height="60" rx="10" fill="none" stroke="#3b82f6" strokeWidth="1.5" filter="url(#buildGlow)"/>
                    <text x="70" y="182" textAnchor="middle" fill="white" fontSize="12" fontWeight="400">Build</text>
                    <text x="70" y="198" textAnchor="middle" fill="white" fontSize="12" fontWeight="400">Orchestrator</text>
                    
                    {/* Code Generator - Top */}
                    <rect x="180" y="15" width="110" height="50" rx="10" fill="none" stroke="#3b82f6" strokeWidth="1.5" filter="url(#buildGlow)"/>
                    <text x="235" y="33" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Code</text>
                    <text x="235" y="47" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Generator</text>
                    
                    {/* Code Reviewer */}
                    <rect x="180" y="75" width="110" height="50" rx="10" fill="none" stroke="#3b82f6" strokeWidth="1.5" filter="url(#buildGlow)"/>
                    <text x="235" y="93" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Code</text>
                    <text x="235" y="107" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Reviewer</text>
                    
                    {/* Refactoring Assistant */}
                    <rect x="180" y="135" width="110" height="50" rx="10" fill="none" stroke="#3b82f6" strokeWidth="1.5" filter="url(#buildGlow)"/>
                    <text x="235" y="153" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Refactoring</text>
                    <text x="235" y="167" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Assistant</text>
                    
                    {/* Unit Test Generator */}
                    <rect x="180" y="195" width="110" height="50" rx="10" fill="none" stroke="#3b82f6" strokeWidth="1.5" filter="url(#buildGlow)"/>
                    <text x="235" y="213" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Unit Test</text>
                    <text x="235" y="227" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Generator</text>
                    
                    {/* Documentation Generator */}
                    <rect x="180" y="255" width="110" height="50" rx="10" fill="none" stroke="#3b82f6" strokeWidth="1.5" filter="url(#buildGlow)"/>
                    <text x="235" y="273" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Documentation</text>
                    <text x="235" y="287" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Generator</text>
                    
                    {/* Performance Optimizer */}
                    <rect x="180" y="315" width="110" height="50" rx="10" fill="none" stroke="#3b82f6" strokeWidth="1.5" filter="url(#buildGlow)"/>
                    <text x="235" y="333" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Performance</text>
                    <text x="235" y="347" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Optimizer</text>
                    
                    {/* Output: Production Code - Right */}
                    <rect x="320" y="160" width="100" height="60" rx="10" fill="none" stroke="#3b82f6" strokeWidth="1.5" filter="url(#buildGlow)"/>
                    <text x="370" y="182" textAnchor="middle" fill="white" fontSize="11" fontWeight="400">Production</text>
                    <text x="370" y="198" textAnchor="middle" fill="white" fontSize="11" fontWeight="400">Code</text>
                    
                    {/* Flowing connection lines from Orchestrator to agents */}
                    <path d="M 120 170 Q 150 40, 180 40" fill="none" stroke="url(#blueFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 178 Q 150 100, 180 100" fill="none" stroke="url(#blueFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 186 Q 150 160, 180 160" fill="none" stroke="url(#blueFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 194 Q 150 220, 180 220" fill="none" stroke="url(#blueFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 202 Q 150 280, 180 280" fill="none" stroke="url(#blueFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 210 Q 150 340, 180 340" fill="none" stroke="url(#blueFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Vertical cyan flows in middle column */}
                    <line x1="235" y1="65" x2="235" y2="75" stroke="url(#cyanFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="125" x2="235" y2="135" stroke="url(#cyanFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="185" x2="235" y2="195" stroke="url(#cyanFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="245" x2="235" y2="255" stroke="url(#cyanFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="305" x2="235" y2="315" stroke="url(#cyanFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Green flows from middle column agents to output */}
                    <path d="M 290 40 Q 305 40, 305 100 Q 305 190, 320 190" fill="none" stroke="url(#greenFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 100 Q 300 100, 300 140 Q 300 190, 320 190" fill="none" stroke="url(#greenFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 160 L 320 180" fill="none" stroke="url(#greenFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 220 Q 300 220, 300 200 Q 300 190, 320 190" fill="none" stroke="url(#greenFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 280 Q 305 280, 305 240 Q 305 190, 320 190" fill="none" stroke="url(#greenFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 340 Q 310 340, 310 260 Q 310 190, 320 190" fill="none" stroke="url(#greenFlowBuild)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Directional Arrows */}
                    <polygon points="235,77 230,72 240,72" fill="#3b82f6" filter="url(#buildGlow)"/>
                    <polygon points="235,137 230,132 240,132" fill="#3b82f6" filter="url(#buildGlow)"/>
                    <polygon points="235,197 230,192 240,192" fill="#3b82f6" filter="url(#buildGlow)"/>
                    <polygon points="235,257 230,252 240,252" fill="#3b82f6" filter="url(#buildGlow)"/>
                    <polygon points="235,317 230,312 240,312" fill="#3b82f6" filter="url(#buildGlow)"/>
                    <polygon points="318,188 314,185 314,191" fill="#10b981" filter="url(#buildGlow)"/>
                    
                    {/* Animated particles */}
                    <circle r="4" fill="#3b82f6" opacity="0.8">
                      <animateMotion dur="3s" repeatCount="indefinite" path="M 100 170 Q 145 40, 190 40"/>
                    </circle>
                    <circle r="4" fill="#3b82f6" opacity="0.8">
                      <animateMotion dur="3s" repeatCount="indefinite" path="M 100 194 Q 145 220, 190 220"/>
                    </circle>
                    <circle r="4" fill="#06b6d4" opacity="0.8">
                      <animateMotion dur="2.5s" repeatCount="indefinite" path="M 235 65 L 235 305"/>
                    </circle>
                    <circle r="4" fill="#10b981" opacity="0.8">
                      <animateMotion dur="3.5s" repeatCount="indefinite" path="M 290 160 L 320 180"/>
                    </circle>
                  </svg>
                </div>
              </div>
            </div>

            {/* Right: Benefits Cards */}
            <div className="flex flex-col justify-between lg:w-[32%] mt-6 h-full">
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-blue-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-blue-300 font-bold text-lg mb-3">75% Faster Coding</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Accelerate development with AI-generated code and tests</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-cyan-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1 my-3">
                <h3 className="text-cyan-300 font-bold text-lg mb-3">90% Test Coverage</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Automatically generate comprehensive test suites</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-emerald-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-emerald-300 font-bold text-lg mb-3">50% Fewer Bugs</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Reduce defects with AI-powered code review</p>
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
                className="bg-[#1a2642]/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6 hover:border-blue-500/30 transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/10 cursor-pointer hover:scale-105"
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