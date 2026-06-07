import { Activity, AlertTriangle, Clock, Server, Home } from 'lucide-react';
import { useState } from 'react';
import { AgentDetailCard, agentDetails } from './AgentDetailCard';
import { MiniSDLCJourney } from './MiniSDLCJourney';

const agents = [
  { name: 'RCA Agent', icon: Clock, color: 'from-red-500 to-red-600', description: 'Root cause analysis and incident investigation' },
  { name: 'Observability Agent', icon: Activity, color: 'from-blue-500 to-blue-600', description: 'Real-time monitoring and observability insights' },
  { name: 'Self-Heal Agent', icon: AlertTriangle, color: 'from-emerald-500 to-emerald-600', description: 'Autonomous issue remediation and recovery' },
  { name: 'Incident Detector', icon: AlertTriangle, color: 'from-orange-500 to-orange-600', description: 'AI-powered incident detection and alerting' },
  { name: 'Monitoring Agent', icon: Activity, color: 'from-purple-500 to-purple-600', description: 'Intelligent monitoring and performance tracking' },
  { name: 'Capacity Agent', icon: Server, color: 'from-indigo-500 to-indigo-600', description: 'Predictive capacity planning and scaling' }
];

interface ReliabilityDetailProps {
  onBack: () => void;
  onStageClick?: (stageName: string) => void;
  currentStage?: string;
}

export function ReliabilityDetail({ onBack, onStageClick, currentStage = 'Reliability' }: ReliabilityDetailProps) {
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
          <button onClick={onBack} className="mb-8 flex items-center gap-2 text-white hover:text-gray-300 transition-colors duration-300 group">
            <div className="w-8 h-8 rounded flex items-center justify-center transition-all duration-300"><Home className="w-5 h-5" /></div>
            <span className="text-xs font-medium">Back to Home</span>
          </button>
          <div className="flex flex-col lg:flex-row gap-5 items-stretch">
            {/* Left: Title and Description */}
            <div className="lg:w-[22%] flex flex-col">
              <div>
                <h1 className="text-2xl lg:text-3xl bg-gradient-to-r from-pink-600 to-pink-300 bg-clip-text text-transparent mb-8 font-normal">Reliability</h1>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">
                  Ensure system reliability with AI-powered monitoring, incident detection, and auto-healing capabilities. Prevent downtime and maintain optimal performance 24/7.
                </p>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">
                  The Reliability Orchestrator coordinates specialized agents to provide comprehensive observability, perform root cause analysis, and execute autonomous remediation actions when issues are detected.
                </p>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed">
                  Built-in self-healing capabilities automatically resolve common incidents while intelligent monitoring provides real-time insights into system health and performance metrics.
                </p>
              </div>
            </div>

            {/* Middle: 3D Reliability Flow Diagram */}
            <div className="lg:w-[40%] flex items-start justify-center mt-6">
              <div className="relative w-full max-w-full overflow-hidden">
                {/* Animated Flow Diagram */}
                <div className="relative bg-gradient-to-br from-slate-900/80 to-slate-800/80 backdrop-blur-sm rounded-2xl p-6 border border-blue-500/30 shadow-2xl">
                  <svg className="w-full h-auto" viewBox="0 0 480 400" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
                    {/* Animated flowing lines */}
                    <defs>
                      {/* Gradient for blue flow */}
                      <linearGradient id="reliabilityBlueFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(59, 130, 246, 0)" />
                        <stop offset="50%" stopColor="rgba(59, 130, 246, 1)" />
                        <stop offset="100%" stopColor="rgba(59, 130, 246, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      {/* Gradient for red flow */}
                      <linearGradient id="reliabilityRedFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(239, 68, 68, 0)" />
                        <stop offset="50%" stopColor="rgba(239, 68, 68, 1)" />
                        <stop offset="100%" stopColor="rgba(239, 68, 68, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="2.5s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="2.5s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      {/* Gradient for emerald flow */}
                      <linearGradient id="reliabilityEmeraldFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(16, 185, 129, 0)" />
                        <stop offset="50%" stopColor="rgba(16, 185, 129, 1)" />
                        <stop offset="100%" stopColor="rgba(16, 185, 129, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3.5s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3.5s" repeatCount="indefinite" />
                      </linearGradient>

                      {/* Gradient for orange flow */}
                      <linearGradient id="reliabilityOrangeFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(249, 115, 22, 0)" />
                        <stop offset="50%" stopColor="rgba(249, 115, 22, 1)" />
                        <stop offset="100%" stopColor="rgba(249, 115, 22, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="2.8s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="2.8s" repeatCount="indefinite" />
                      </linearGradient>

                      {/* Gradient for purple flow */}
                      <linearGradient id="reliabilityPurpleFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(168, 85, 247, 0)" />
                        <stop offset="50%" stopColor="rgba(168, 85, 247, 1)" />
                        <stop offset="100%" stopColor="rgba(168, 85, 247, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3.2s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3.2s" repeatCount="indefinite" />
                      </linearGradient>

                      {/* Gradient for indigo flow */}
                      <linearGradient id="reliabilityIndigoFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(99, 102, 241, 0)" />
                        <stop offset="50%" stopColor="rgba(99, 102, 241, 1)" />
                        <stop offset="100%" stopColor="rgba(99, 102, 241, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3.7s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3.7s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      {/* Glow effect */}
                      <filter id="reliabilityGlow">
                        <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                        <feMerge>
                          <feMergeNode in="coloredBlur"/>
                          <feMergeNode in="SourceGraphic"/>
                        </feMerge>
                      </filter>
                    </defs>
                    
                    {/* Reliability Orchestrator - Left Center */}
                    <rect x="20" y="170" width="110" height="60" rx="10" fill="none" stroke="#3b82f6" strokeWidth="1.5" filter="url(#reliabilityGlow)"/>
                    <text x="75" y="192" textAnchor="middle" fill="white" fontSize="11" fontWeight="400">Reliability</text>
                    <text x="75" y="208" textAnchor="middle" fill="white" fontSize="11" fontWeight="400">Orchestrator</text>
                    
                    {/* Row 1 Agents */}
                    {/* RCA Agent - Top Left */}
                    <rect x="200" y="30" width="110" height="50" rx="10" fill="none" stroke="#ef4444" strokeWidth="1.5" filter="url(#reliabilityGlow)"/>
                    <text x="255" y="60" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">RCA Agent</text>
                    
                    {/* Observability Agent - Top Right */}
                    <rect x="340" y="30" width="110" height="50" rx="10" fill="none" stroke="#3b82f6" strokeWidth="1.5" filter="url(#reliabilityGlow)"/>
                    <text x="395" y="52" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Observability</text>
                    <text x="395" y="65" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Agent</text>
                    
                    {/* Row 2 Agents */}
                    {/* Self-Heal Agent - Middle Left */}
                    <rect x="200" y="110" width="110" height="50" rx="10" fill="none" stroke="#10b981" strokeWidth="1.5" filter="url(#reliabilityGlow)"/>
                    <text x="255" y="132" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Self-Heal</text>
                    <text x="255" y="145" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Agent</text>
                    
                    {/* Incident Detector - Middle Right */}
                    <rect x="340" y="110" width="110" height="50" rx="10" fill="none" stroke="#f97316" strokeWidth="1.5" filter="url(#reliabilityGlow)"/>
                    <text x="395" y="132" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Incident</text>
                    <text x="395" y="145" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Detector</text>
                    
                    {/* Row 3 Agents */}
                    {/* Monitoring Agent - Bottom Left */}
                    <rect x="200" y="190" width="110" height="50" rx="10" fill="none" stroke="#a855f7" strokeWidth="1.5" filter="url(#reliabilityGlow)"/>
                    <text x="255" y="212" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Monitoring</text>
                    <text x="255" y="225" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Agent</text>
                    
                    {/* Capacity Agent - Bottom Right */}
                    <rect x="340" y="190" width="110" height="50" rx="10" fill="none" stroke="#6366f1" strokeWidth="1.5" filter="url(#reliabilityGlow)"/>
                    <text x="395" y="212" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Capacity</text>
                    <text x="395" y="225" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Agent</text>
                    
                    {/* Flowing connection lines from Orchestrator to all agents */}
                    {/* To RCA Agent */}
                    <path d="M 130 185 Q 165 55, 200 55" fill="none" stroke="url(#reliabilityRedFlow)" strokeWidth="2.5" opacity="0.9"/>
                    
                    {/* To Observability Agent */}
                    <path d="M 130 185 Q 235 55, 340 55" fill="none" stroke="url(#reliabilityBlueFlow)" strokeWidth="2.5" opacity="0.9"/>
                    
                    {/* To Self-Heal Agent */}
                    <path d="M 130 195 L 200 135" fill="none" stroke="url(#reliabilityEmeraldFlow)" strokeWidth="2.5" opacity="0.9"/>
                    
                    {/* To Incident Detector */}
                    <path d="M 130 195 Q 235 135, 340 135" fill="none" stroke="url(#reliabilityOrangeFlow)" strokeWidth="2.5" opacity="0.9"/>
                    
                    {/* To Monitoring Agent */}
                    <path d="M 130 205 L 200 215" fill="none" stroke="url(#reliabilityPurpleFlow)" strokeWidth="2.5" opacity="0.9"/>
                    
                    {/* To Capacity Agent */}
                    <path d="M 130 205 Q 235 215, 340 215" fill="none" stroke="url(#reliabilityIndigoFlow)" strokeWidth="2.5" opacity="0.9"/>
                    
                    {/* Feedback loops */}
                    <path d="M 255 80 L 255 110" fill="none" stroke="url(#reliabilityBlueFlow)" strokeWidth="2" opacity="0.7" strokeDasharray="3,3"/>
                    <path d="M 395 80 L 395 110" fill="none" stroke="url(#reliabilityEmeraldFlow)" strokeWidth="2" opacity="0.7" strokeDasharray="3,3"/>
                    <path d="M 255 160 L 255 190" fill="none" stroke="url(#reliabilityOrangeFlow)" strokeWidth="2" opacity="0.7" strokeDasharray="3,3"/>
                    
                    {/* Directional Arrows */}
                    <polygon points="202,55 197,52 197,58" fill="#ef4444" filter="url(#reliabilityGlow)"/>
                    <polygon points="342,55 337,52 337,58" fill="#3b82f6" filter="url(#reliabilityGlow)"/>
                    <polygon points="202,135 197,132 197,138" fill="#10b981" filter="url(#reliabilityGlow)"/>
                    <polygon points="342,135 337,132 337,138" fill="#f97316" filter="url(#reliabilityGlow)"/>
                    <polygon points="202,215 197,212 197,218" fill="#a855f7" filter="url(#reliabilityGlow)"/>
                    <polygon points="342,215 337,212 337,218" fill="#6366f1" filter="url(#reliabilityGlow)"/>
                    
                    {/* Animated particles along paths */}
                    <circle r="3" fill="#ef4444" opacity="0.8">
                      <animateMotion dur="3s" repeatCount="indefinite" path="M 130 185 Q 165 55, 200 55"/>
                    </circle>
                    <circle r="3" fill="#3b82f6" opacity="0.8">
                      <animateMotion dur="3.5s" repeatCount="indefinite" path="M 130 185 Q 235 55, 340 55"/>
                    </circle>
                    <circle r="3" fill="#10b981" opacity="0.8">
                      <animateMotion dur="2.8s" repeatCount="indefinite" path="M 130 195 L 200 135"/>
                    </circle>
                    <circle r="3" fill="#f97316" opacity="0.8">
                      <animateMotion dur="3.2s" repeatCount="indefinite" path="M 130 195 Q 235 135, 340 135"/>
                    </circle>
                    <circle r="3" fill="#a855f7" opacity="0.8">
                      <animateMotion dur="3.7s" repeatCount="indefinite" path="M 130 205 L 200 215"/>
                    </circle>
                    <circle r="3" fill="#6366f1" opacity="0.8">
                      <animateMotion dur="3s" repeatCount="indefinite" path="M 130 205 Q 235 215, 340 215"/>
                    </circle>
                  </svg>
                </div>
              </div>
            </div>

            {/* Right: Benefits Cards */}
            <div className="flex flex-col justify-between lg:w-[32%] mt-6 h-full">
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-pink-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-pink-300 font-bold text-lg mb-3">99.99% Uptime</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Maximize availability with auto-healing</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-red-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1 my-3">
                <h3 className="text-red-300 font-bold text-lg mb-3">80% Faster Recovery</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Reduce MTTR with intelligent detection</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-emerald-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-emerald-300 font-bold text-lg mb-3">Real-time Insights</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Comprehensive observability across all systems</p>
              </div>
            </div>
          </div>
        </div>
        
        {/* Agents Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          {agents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div key={agent.name} className="bg-[#1a2642]/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6 hover:border-pink-500/30 transition-all duration-300 hover:shadow-lg hover:shadow-pink-500/10 cursor-pointer hover:scale-105" onClick={() => setSelectedAgent(agent.name)}>
                <div className="flex items-start gap-4">
                  <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${agent.color} flex items-center justify-center shadow-lg flex-shrink-0`}><Icon className="w-6 h-6 text-white" /></div>
                  <div className="flex-1"><h3 className="text-white font-semibold text-base mb-2">{agent.name}</h3><p className="text-gray-400 text-sm leading-relaxed">{agent.description}</p></div>
                </div>
              </div>
            );
          })}
        </div>
        {selectedAgent && agentDetails[selectedAgent] && <AgentDetailCard agent={agentDetails[selectedAgent]} onClose={() => setSelectedAgent(null)} />}
      </div>
    </div>
  );
}