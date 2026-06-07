import { Shield, Lock, Key, Eye, FileCheck, AlertTriangle, Home } from 'lucide-react';
import { useState } from 'react';
import { AgentDetailCard, agentDetails } from './AgentDetailCard';
import { MiniSDLCJourney } from './MiniSDLCJourney';

const agents = [
  { name: 'Vulnerability Scanner', icon: Shield, color: 'from-teal-500 to-teal-600', description: 'Automated security vulnerability detection' },
  { name: 'Threat Analyzer', icon: Eye, color: 'from-red-500 to-red-600', description: 'AI-powered threat intelligence and analysis' },
  { name: 'Compliance Checker', icon: Lock, color: 'from-blue-500 to-blue-600', description: 'Automated compliance and policy enforcement' },
  { name: 'Secret Manager', icon: Key, color: 'from-purple-500 to-purple-600', description: 'Secure secret detection and management' },
  { name: 'Penetration Tester', icon: AlertTriangle, color: 'from-orange-500 to-orange-600', description: 'AI-powered penetration testing and security validation' },
  { name: 'Incident Responder', icon: FileCheck, color: 'from-rose-500 to-rose-600', description: 'Automated security incident response and remediation' }
];

interface SecurityDetailProps {
  onBack: () => void;
  onStageClick?: (stageName: string) => void;
  currentStage?: string;
}

export function SecurityDetail({ onBack, onStageClick, currentStage = 'Security' }: SecurityDetailProps) {
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
                <h1 className="text-2xl lg:text-3xl bg-gradient-to-r from-teal-600 to-teal-300 bg-clip-text text-transparent mb-8 font-normal">Security</h1>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">
                  Protect your applications with AI-powered security scanning, threat detection, and compliance monitoring. Identify and remediate vulnerabilities before they become breaches.
                </p>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">
                  The Security Orchestrator coordinates specialized agents to perform comprehensive vulnerability scanning, threat analysis, and compliance checking across your entire application stack.
                </p>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed">
                  Built-in penetration testing and incident response capabilities ensure your systems are protected against both known and emerging threats while maintaining regulatory compliance.
                </p>
              </div>
            </div>

            {/* Middle: 3D Security Flow Diagram */}
            <div className="lg:w-[40%] flex items-start justify-center mt-6">
              <div className="relative w-full max-w-full overflow-hidden">
                {/* Animated Flow Diagram */}
                <div className="relative bg-gradient-to-br from-slate-900/80 to-slate-800/80 backdrop-blur-sm rounded-2xl p-6 border border-teal-500/30 shadow-2xl">
                  <svg className="w-full h-auto" viewBox="0 0 480 400" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
                    {/* Animated flowing lines */}
                    <defs>
                      {/* Gradient for teal flow */}
                      <linearGradient id="tealFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(20, 184, 166, 0)" />
                        <stop offset="50%" stopColor="rgba(20, 184, 166, 1)" />
                        <stop offset="100%" stopColor="rgba(20, 184, 166, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      {/* Gradient for red flow */}
                      <linearGradient id="redFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(239, 68, 68, 0)" />
                        <stop offset="50%" stopColor="rgba(239, 68, 68, 1)" />
                        <stop offset="100%" stopColor="rgba(239, 68, 68, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="2.5s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="2.5s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      {/* Gradient for blue flow */}
                      <linearGradient id="securityBlueFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(59, 130, 246, 0)" />
                        <stop offset="50%" stopColor="rgba(59, 130, 246, 1)" />
                        <stop offset="100%" stopColor="rgba(59, 130, 246, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3.5s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3.5s" repeatCount="indefinite" />
                      </linearGradient>

                      {/* Gradient for purple flow */}
                      <linearGradient id="securityPurpleFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(168, 85, 247, 0)" />
                        <stop offset="50%" stopColor="rgba(168, 85, 247, 1)" />
                        <stop offset="100%" stopColor="rgba(168, 85, 247, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="2.8s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="2.8s" repeatCount="indefinite" />
                      </linearGradient>

                      {/* Gradient for orange flow */}
                      <linearGradient id="securityOrangeFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(249, 115, 22, 0)" />
                        <stop offset="50%" stopColor="rgba(249, 115, 22, 1)" />
                        <stop offset="100%" stopColor="rgba(249, 115, 22, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3.2s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3.2s" repeatCount="indefinite" />
                      </linearGradient>

                      {/* Gradient for rose flow */}
                      <linearGradient id="securityRoseFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(244, 63, 94, 0)" />
                        <stop offset="50%" stopColor="rgba(244, 63, 94, 1)" />
                        <stop offset="100%" stopColor="rgba(244, 63, 94, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3.7s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3.7s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      {/* Glow effect */}
                      <filter id="securityGlow">
                        <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                        <feMerge>
                          <feMergeNode in="coloredBlur"/>
                          <feMergeNode in="SourceGraphic"/>
                        </feMerge>
                      </filter>
                    </defs>
                    
                    {/* Security Orchestrator - Left Center */}
                    <rect x="20" y="170" width="110" height="60" rx="10" fill="none" stroke="#14b8a6" strokeWidth="1.5" filter="url(#securityGlow)"/>
                    <text x="75" y="192" textAnchor="middle" fill="white" fontSize="11" fontWeight="400">Security</text>
                    <text x="75" y="208" textAnchor="middle" fill="white" fontSize="11" fontWeight="400">Orchestrator</text>
                    
                    {/* Row 1 Agents */}
                    {/* Vulnerability Scanner - Top Left */}
                    <rect x="200" y="30" width="110" height="50" rx="10" fill="none" stroke="#14b8a6" strokeWidth="1.5" filter="url(#securityGlow)"/>
                    <text x="255" y="52" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Vulnerability</text>
                    <text x="255" y="65" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Scanner</text>
                    
                    {/* Threat Analyzer - Top Right */}
                    <rect x="340" y="30" width="110" height="50" rx="10" fill="none" stroke="#ef4444" strokeWidth="1.5" filter="url(#securityGlow)"/>
                    <text x="395" y="52" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Threat</text>
                    <text x="395" y="65" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Analyzer</text>
                    
                    {/* Row 2 Agents */}
                    {/* Compliance Checker - Middle Left */}
                    <rect x="200" y="110" width="110" height="50" rx="10" fill="none" stroke="#3b82f6" strokeWidth="1.5" filter="url(#securityGlow)"/>
                    <text x="255" y="132" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Compliance</text>
                    <text x="255" y="145" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Checker</text>
                    
                    {/* Secret Manager - Middle Right */}
                    <rect x="340" y="110" width="110" height="50" rx="10" fill="none" stroke="#a855f7" strokeWidth="1.5" filter="url(#securityGlow)"/>
                    <text x="395" y="132" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Secret</text>
                    <text x="395" y="145" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Manager</text>
                    
                    {/* Row 3 Agents */}
                    {/* Penetration Tester - Bottom Left */}
                    <rect x="200" y="190" width="110" height="50" rx="10" fill="none" stroke="#f97316" strokeWidth="1.5" filter="url(#securityGlow)"/>
                    <text x="255" y="212" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Penetration</text>
                    <text x="255" y="225" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Tester</text>
                    
                    {/* Incident Responder - Bottom Right */}
                    <rect x="340" y="190" width="110" height="50" rx="10" fill="none" stroke="#f43f5e" strokeWidth="1.5" filter="url(#securityGlow)"/>
                    <text x="395" y="212" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Incident</text>
                    <text x="395" y="225" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Responder</text>
                    
                    {/* Flowing connection lines from Orchestrator to all agents */}
                    {/* To Vulnerability Scanner */}
                    <path d="M 130 185 Q 165 55, 200 55" fill="none" stroke="url(#tealFlow)" strokeWidth="2.5" opacity="0.9"/>
                    
                    {/* To Threat Analyzer */}
                    <path d="M 130 185 Q 235 55, 340 55" fill="none" stroke="url(#redFlow)" strokeWidth="2.5" opacity="0.9"/>
                    
                    {/* To Compliance Checker */}
                    <path d="M 130 195 L 200 135" fill="none" stroke="url(#securityBlueFlow)" strokeWidth="2.5" opacity="0.9"/>
                    
                    {/* To Secret Manager */}
                    <path d="M 130 195 Q 235 135, 340 135" fill="none" stroke="url(#securityPurpleFlow)" strokeWidth="2.5" opacity="0.9"/>
                    
                    {/* To Penetration Tester */}
                    <path d="M 130 205 L 200 215" fill="none" stroke="url(#securityOrangeFlow)" strokeWidth="2.5" opacity="0.9"/>
                    
                    {/* To Incident Responder */}
                    <path d="M 130 205 Q 235 215, 340 215" fill="none" stroke="url(#securityRoseFlow)" strokeWidth="2.5" opacity="0.9"/>
                    
                    {/* Feedback loops */}
                    <path d="M 255 80 L 255 110" fill="none" stroke="url(#securityBlueFlow)" strokeWidth="2" opacity="0.7" strokeDasharray="3,3"/>
                    <path d="M 395 80 L 395 110" fill="none" stroke="url(#securityPurpleFlow)" strokeWidth="2" opacity="0.7" strokeDasharray="3,3"/>
                    <path d="M 255 160 L 255 190" fill="none" stroke="url(#securityOrangeFlow)" strokeWidth="2" opacity="0.7" strokeDasharray="3,3"/>
                    
                    {/* Directional Arrows */}
                    <polygon points="202,55 197,52 197,58" fill="#14b8a6" filter="url(#securityGlow)"/>
                    <polygon points="342,55 337,52 337,58" fill="#ef4444" filter="url(#securityGlow)"/>
                    <polygon points="202,135 197,132 197,138" fill="#3b82f6" filter="url(#securityGlow)"/>
                    <polygon points="342,135 337,132 337,138" fill="#a855f7" filter="url(#securityGlow)"/>
                    <polygon points="202,215 197,212 197,218" fill="#f97316" filter="url(#securityGlow)"/>
                    <polygon points="342,215 337,212 337,218" fill="#f43f5e" filter="url(#securityGlow)"/>
                    
                    {/* Animated particles along paths */}
                    <circle r="3" fill="#14b8a6" opacity="0.8">
                      <animateMotion dur="3s" repeatCount="indefinite" path="M 130 185 Q 165 55, 200 55"/>
                    </circle>
                    <circle r="3" fill="#ef4444" opacity="0.8">
                      <animateMotion dur="2.5s" repeatCount="indefinite" path="M 130 185 Q 235 55, 340 55"/>
                    </circle>
                    <circle r="3" fill="#3b82f6" opacity="0.8">
                      <animateMotion dur="3.5s" repeatCount="indefinite" path="M 130 195 L 200 135"/>
                    </circle>
                    <circle r="3" fill="#a855f7" opacity="0.8">
                      <animateMotion dur="2.8s" repeatCount="indefinite" path="M 130 195 Q 235 135, 340 135"/>
                    </circle>
                    <circle r="3" fill="#f97316" opacity="0.8">
                      <animateMotion dur="3.2s" repeatCount="indefinite" path="M 130 205 L 200 215"/>
                    </circle>
                    <circle r="3" fill="#f43f5e" opacity="0.8">
                      <animateMotion dur="3.7s" repeatCount="indefinite" path="M 130 205 Q 235 215, 340 215"/>
                    </circle>
                  </svg>
                </div>
              </div>
            </div>

            {/* Right: Benefits Cards */}
            <div className="flex flex-col justify-between lg:w-[32%] mt-6 h-full">
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-teal-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-teal-300 font-bold text-lg mb-3">95% Threat Detection</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Identify vulnerabilities before exploitation</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-blue-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1 my-3">
                <h3 className="text-blue-300 font-bold text-lg mb-3">100% Compliance</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Maintain regulatory compliance automatically</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-red-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-red-300 font-bold text-lg mb-3">Zero-Day Protection</h3>
                <p className="text-gray-300 text-sm leading-relaxed">AI-powered threat intelligence and analysis</p>
              </div>
            </div>
          </div>
        </div>
        
        {/* Agents Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          {agents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div key={agent.name} className="bg-[#1a2642]/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6 hover:border-teal-500/30 transition-all duration-300 hover:shadow-lg hover:shadow-teal-500/10 cursor-pointer hover:scale-105" onClick={() => setSelectedAgent(agent.name)}>
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