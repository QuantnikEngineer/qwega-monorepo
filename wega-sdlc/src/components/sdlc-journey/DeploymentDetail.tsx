import { Rocket, GitBranch, Server, Activity, Shield, Cloud, Home } from 'lucide-react';
import { useState } from 'react';
import { AgentDetailCard, agentDetails } from './AgentDetailCard';
import { MiniSDLCJourney } from './MiniSDLCJourney';

const agents = [
  { name: 'CI/CD Pipeline Builder', icon: GitBranch, color: 'from-indigo-500 to-indigo-600', description: 'Automated CI/CD pipeline configuration' },
  { name: 'Container Orchestrator', icon: Server, color: 'from-blue-500 to-blue-600', description: 'Intelligent container deployment and scaling' },
  { name: 'Release Manager', icon: Rocket, color: 'from-purple-500 to-purple-600', description: 'Automated release planning and execution' },
  { name: 'Environment Configurator', icon: Cloud, color: 'from-cyan-500 to-cyan-600', description: 'Multi-environment configuration management' },
  { name: 'Deployment Validator', icon: Shield, color: 'from-emerald-500 to-emerald-600', description: 'Validate deployments and ensure stability' },
  { name: 'Rollback Agent', icon: Activity, color: 'from-orange-500 to-orange-600', description: 'Automated rollback and recovery mechanisms' }
];

interface DeploymentDetailProps {
  onBack: () => void;
  onStageClick?: (stageName: string) => void;
  currentStage?: string;
}

export function DeploymentDetail({ onBack, onStageClick, currentStage = 'Deployment' }: DeploymentDetailProps) {
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
                <h1 className="text-2xl lg:text-3xl bg-gradient-to-r from-indigo-600 to-indigo-300 bg-clip-text text-transparent mb-8 font-normal">
                  Deployment
                </h1>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">
                  Streamline your deployment process with AI-powered automation. Build robust CI/CD pipelines, orchestrate containers, and manage releases across multiple environments with confidence.
                </p>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">
                  The Deployment Orchestrator coordinates specialized agents to automate your entire deployment workflow. After deployment, the Deployment Validator performs comprehensive health checks and stability verification. If validation fails, it automatically triggers the Rollback Agent to revert to the previous stable version, ensuring zero-impact to production.
                </p>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed">
                  This intelligent safety mechanism guarantees that only validated, stable deployments reach production, while failed deployments are instantly rolled back without manual intervention, maintaining system reliability and uptime.
                </p>
              </div>
            </div>

            {/* Middle: Deployment Flow Diagram */}
            <div className="lg:w-[40%] flex items-start justify-center mt-6">
              <div className="relative w-full max-w-full overflow-hidden">
                <div className="relative bg-gradient-to-br from-slate-900/80 to-slate-800/80 backdrop-blur-sm rounded-2xl p-6 border border-indigo-500/30 shadow-2xl">
                  <svg className="w-full h-auto" viewBox="0 0 440 420" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
                    <defs>
                      <linearGradient id="indigoFlowDeploy" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(99, 102, 241, 0)" />
                        <stop offset="50%" stopColor="rgba(99, 102, 241, 1)" />
                        <stop offset="100%" stopColor="rgba(99, 102, 241, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      <linearGradient id="purpleFlowDeploy" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(168, 85, 247, 0)" />
                        <stop offset="50%" stopColor="rgba(168, 85, 247, 1)" />
                        <stop offset="100%" stopColor="rgba(168, 85, 247, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="2.5s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="2.5s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      <linearGradient id="successFlowDeploy" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(34, 197, 94, 0)" />
                        <stop offset="50%" stopColor="rgba(34, 197, 94, 1)" />
                        <stop offset="100%" stopColor="rgba(34, 197, 94, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3.5s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3.5s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      <linearGradient id="failureFlowDeploy" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(249, 115, 22, 0)" />
                        <stop offset="50%" stopColor="rgba(249, 115, 22, 1)" />
                        <stop offset="100%" stopColor="rgba(249, 115, 22, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="2.8s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="2.8s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      <filter id="deployGlow">
                        <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                        <feMerge>
                          <feMergeNode in="coloredBlur"/>
                          <feMergeNode in="SourceGraphic"/>
                        </feMerge>
                      </filter>
                    </defs>
                    
                    {/* Deployment Orchestrator - Left Center */}
                    <rect x="20" y="150" width="100" height="60" rx="10" fill="none" stroke="#6366f1" strokeWidth="1.5" filter="url(#deployGlow)"/>
                    <text x="70" y="172" textAnchor="middle" fill="white" fontSize="11" fontWeight="400">Deployment</text>
                    <text x="70" y="188" textAnchor="middle" fill="white" fontSize="11" fontWeight="400">Orchestrator</text>
                    
                    {/* CI/CD Pipeline Builder - Top */}
                    <rect x="180" y="15" width="110" height="50" rx="10" fill="none" stroke="#6366f1" strokeWidth="1.5" filter="url(#deployGlow)"/>
                    <text x="235" y="33" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">CI/CD Pipeline</text>
                    <text x="235" y="47" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Builder</text>
                    
                    {/* Container Orchestrator */}
                    <rect x="180" y="75" width="110" height="50" rx="10" fill="none" stroke="#6366f1" strokeWidth="1.5" filter="url(#deployGlow)"/>
                    <text x="235" y="93" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Container</text>
                    <text x="235" y="107" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Orchestrator</text>
                    
                    {/* Release Manager */}
                    <rect x="180" y="135" width="110" height="50" rx="10" fill="none" stroke="#6366f1" strokeWidth="1.5" filter="url(#deployGlow)"/>
                    <text x="235" y="153" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Release</text>
                    <text x="235" y="167" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Manager</text>
                    
                    {/* Environment Configurator */}
                    <rect x="180" y="195" width="110" height="50" rx="10" fill="none" stroke="#6366f1" strokeWidth="1.5" filter="url(#deployGlow)"/>
                    <text x="235" y="213" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Environment</text>
                    <text x="235" y="227" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Configurator</text>
                    
                    {/* Deployment Validator - Right Upper */}
                    <rect x="320" y="100" width="100" height="50" rx="10" fill="none" stroke="#10b981" strokeWidth="1.5" filter="url(#deployGlow)"/>
                    <text x="370" y="118" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Deployment</text>
                    <text x="370" y="132" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Validator</text>
                    
                    {/* Decision Diamond */}
                    <path d="M 370 160 L 390 180 L 370 200 L 350 180 Z" fill="none" stroke="#10b981" strokeWidth="1.5" filter="url(#deployGlow)"/>
                    <text x="370" y="183" textAnchor="middle" fill="#10b981" fontSize="14" fontWeight="600">?</text>
                    
                    {/* Live Production - Right Top */}
                    <rect x="320" y="20" width="100" height="50" rx="10" fill="none" stroke="#22c55e" strokeWidth="1.5" filter="url(#deployGlow)"/>
                    <text x="370" y="38" textAnchor="middle" fill="white" fontSize="11" fontWeight="400">Live</text>
                    <text x="370" y="52" textAnchor="middle" fill="white" fontSize="11" fontWeight="400">Production</text>
                    
                    {/* Rollback Agent - Bottom Right */}
                    <rect x="320" y="240" width="100" height="50" rx="10" fill="none" stroke="#f97316" strokeWidth="1.5" filter="url(#deployGlow)"/>
                    <text x="370" y="258" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Rollback</text>
                    <text x="370" y="272" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Agent</text>
                    
                    {/* Previous Version - Bottom Left */}
                    <rect x="180" y="255" width="110" height="50" rx="10" fill="none" stroke="#f97316" strokeWidth="1.5" filter="url(#deployGlow)"/>
                    <text x="235" y="273" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Previous</text>
                    <text x="235" y="287" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Version</text>
                    
                    {/* Flowing connection lines from Orchestrator to agents */}
                    <path d="M 120 160 Q 150 40, 180 40" fill="none" stroke="url(#indigoFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 168 Q 150 100, 180 100" fill="none" stroke="url(#indigoFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 176 Q 150 160, 180 160" fill="none" stroke="url(#indigoFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 184 Q 150 220, 180 220" fill="none" stroke="url(#indigoFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Vertical purple flows in middle column */}
                    <line x1="235" y1="65" x2="235" y2="75" stroke="url(#purpleFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="125" x2="235" y2="135" stroke="url(#purpleFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="185" x2="235" y2="195" stroke="url(#purpleFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Flow from middle agents to Deployment Validator */}
                    <path d="M 290 40 Q 305 40, 305 80 Q 305 125, 320 125" fill="none" stroke="url(#purpleFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 100 Q 300 100, 300 120 Q 300 125, 320 125" fill="none" stroke="url(#purpleFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 160 Q 305 160, 305 135 Q 305 125, 320 125" fill="none" stroke="url(#purpleFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 220 Q 300 220, 300 160 Q 300 135, 320 135" fill="none" stroke="url(#purpleFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Success path: Validator to Production (Green) */}
                    <path d="M 370 100 L 370 70" fill="none" stroke="url(#successFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    <text x="385" y="88" fill="#22c55e" fontSize="9" fontWeight="600">Pass</text>
                    
                    {/* Failure path: Validator Decision to Rollback (Orange) */}
                    <path d="M 370 200 L 370 240" fill="none" stroke="url(#failureFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    <text x="385" y="222" fill="#f97316" fontSize="9" fontWeight="600">Fail</text>
                    
                    {/* Rollback to Previous Version */}
                    <path d="M 320 265 L 290 280" fill="none" stroke="url(#failureFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Previous Version back to Orchestrator (loop) */}
                    <path d="M 180 280 Q 100 280, 100 220 L 100 210" fill="none" stroke="url(#failureFlowDeploy)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Validator to Decision Diamond */}
                    <line x1="370" y1="150" x2="370" y2="160" stroke="#10b981" strokeWidth="2" opacity="0.9"/>
                    
                    {/* Directional Arrows */}
                    <polygon points="235,77 230,72 240,72" fill="#6366f1" filter="url(#deployGlow)"/>
                    <polygon points="235,137 230,132 240,132" fill="#6366f1" filter="url(#deployGlow)"/>
                    <polygon points="235,197 230,192 240,192" fill="#6366f1" filter="url(#deployGlow)"/>
                    <polygon points="318,125 314,122 314,128" fill="#a855f7" filter="url(#deployGlow)"/>
                    <polygon points="370,72 367,76 373,76" fill="#22c55e" filter="url(#deployGlow)"/>
                    <polygon points="370,242 367,238 373,238" fill="#f97316" filter="url(#deployGlow)"/>
                    <polygon points="292,278 296,275 296,281" fill="#f97316" filter="url(#deployGlow)"/>
                    <polygon points="100,212 97,216 103,216" fill="#f97316" filter="url(#deployGlow)"/>
                    
                    {/* Animated particles */}
                    <circle r="4" fill="#6366f1" opacity="0.8">
                      <animateMotion dur="3s" repeatCount="indefinite" path="M 100 160 Q 145 40, 190 40"/>
                    </circle>
                    <circle r="4" fill="#a855f7" opacity="0.8">
                      <animateMotion dur="2.5s" repeatCount="indefinite" path="M 235 65 L 235 185"/>
                    </circle>
                    <circle r="4" fill="#22c55e" opacity="0.8">
                      <animateMotion dur="3.5s" repeatCount="indefinite" path="M 370 100 L 370 70"/>
                    </circle>
                    <circle r="4" fill="#f97316" opacity="0.8">
                      <animateMotion dur="2.8s" repeatCount="indefinite" path="M 370 200 L 370 240"/>
                    </circle>
                  </svg>
                </div>
              </div>
            </div>

            {/* Right: Benefits Cards */}
            <div className="flex flex-col justify-between lg:w-[32%] mt-6 h-full">
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-indigo-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-indigo-300 font-bold text-lg mb-3">90% Faster Deployments</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Automate the entire deployment pipeline</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-emerald-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1 my-3">
                <h3 className="text-emerald-300 font-bold text-lg mb-3">100% Validation</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Every deployment verified before going live</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-orange-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-orange-300 font-bold text-lg mb-3">Auto Rollback</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Instant revert on validation failure</p>
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
                className="bg-[#1a2642]/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6 hover:border-indigo-500/30 transition-all duration-300 hover:shadow-lg hover:shadow-indigo-500/10 cursor-pointer hover:scale-105"
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