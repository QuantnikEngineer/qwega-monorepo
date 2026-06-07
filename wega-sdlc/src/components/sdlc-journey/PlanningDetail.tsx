import { FileText, Users, Lightbulb, CheckCircle, Network, MessageSquare, Calendar, Target, Home, TrendingUp } from 'lucide-react';
import { useState } from 'react';
import { AgentDetailCard, agentDetails } from './AgentDetailCard';
import { MiniSDLCJourney } from './MiniSDLCJourney';

const agents = [
  {
    name: 'Market Research Analyst',
    icon: Users,
    color: 'from-cyan-500 to-cyan-600',
    description: 'AI-powered stakeholder analysis and requirement extraction'
  },
  {
    name: 'Business Requirement Document',
    icon: FileText,
    color: 'from-purple-500 to-purple-600',
    description: 'Business requirement document generation'
  },
  {
    name: 'User Story Generator',
    icon: Lightbulb,
    color: 'from-blue-500 to-blue-600',
    description: 'Automated user story creation from requirements'
  },
  {
    name: 'User Story Validator',
    icon: CheckCircle,
    color: 'from-emerald-500 to-emerald-600',
    description: 'Validate and refine user stories for quality'
  },
  {
    name: 'User Story Estimator',
    icon: TrendingUp,
    color: 'from-amber-500 to-amber-600',
    description: 'AI-powered story point estimation and sizing'
  },
  {
    name: 'Knowledge Graph Builder',
    icon: Network,
    color: 'from-indigo-500 to-indigo-600',
    description: 'Build comprehensive knowledge graphs from documents'
  },
  {
    name: 'Document Query & FAQ Generator',
    icon: MessageSquare,
    color: 'from-pink-500 to-pink-600',
    description: 'Generate FAQs and enable document querying'
  },
  {
    name: 'Effort Planner',
    icon: Calendar,
    color: 'from-orange-500 to-orange-600',
    description: 'AI-driven effort estimation and planning'
  },
  {
    name: 'MVP Analyzer',
    icon: Target,
    color: 'from-violet-500 to-violet-600',
    description: 'Analyze and identify minimum viable product scope'
  }
];

interface PlanningDetailProps {
  onBack: () => void;
  onStageClick?: (stageName: string) => void;
  currentStage?: string;
}

export function PlanningDetail({ onBack, onStageClick, currentStage = 'Planning' }: PlanningDetailProps) {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  return (
    <div className="relative min-h-[600px] bg-gradient-to-br from-[#0a1628] via-[#132340] to-[#0f1e36] overflow-hidden">
      {/* Mini SDLC Journey at the top */}
      {onStageClick && (
        <MiniSDLCJourney currentStage={currentStage} onStageClick={onStageClick} />
      )}
      
      {/* Background Pattern */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(120,119,198,0.05),transparent_50%)]"></div>
      
      <div className="container mx-auto px-6 py-16 relative z-10">
        {/* Header Section */}
        <div className="mb-12 max-w-7xl mx-auto relative">
          {/* Home Button */}
          <button
            onClick={onBack}
            className="mb-8 flex items-center gap-2 text-white hover:text-gray-300 transition-colors duration-300 group"
          >
            <div className="w-8 h-8 rounded flex items-center justify-center transition-all duration-300">
              <Home className="w-5 h-5" />
            </div>
            <span className="text-xs font-medium">Back to Home</span>
          </button>

          {/* Content Layout: Text on Left, Icon in Middle, Benefits on Right */}
          <div className="flex flex-col lg:flex-row gap-5 items-stretch">
            {/* Left: Title and Description */}
            <div className="lg:w-[22%] flex flex-col">
              <div>
                <h1 className="text-2xl lg:text-3xl bg-gradient-to-r from-cyan-600 to-cyan-300 bg-clip-text text-transparent mb-8 font-normal">
                  Planning
                </h1>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">
                  Transform your software planning process with AI-powered agents that automate requirement gathering, user story generation, and effort estimation. Our intelligent planning suite leverages advanced natural language processing and machine learning to extract insights from stakeholder inputs, validate requirements, and create comprehensive project roadmaps in minutes instead of weeks.
                </p>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">
                  The Planning Orchestrator coordinates multiple specialized agents to analyze market research, generate business requirement documents, and create validated user stories. Each agent brings domain expertise to ensure requirements are comprehensive, actionable, and aligned with business objectives.
                </p>
                <p className="text-gray-300 text-[0.72rem] leading-relaxed">
                  Built-in knowledge graph capabilities map relationships between requirements, while intelligent FAQ generation and document querying enable teams to quickly access critical information. Effort planning algorithms consider historical data and complexity patterns to provide accurate time and resource estimates for your projects.
                </p>
              </div>
            </div>

            {/* Middle: 3D Planning Flow Diagram */}
            <div className="lg:w-[40%] flex items-start justify-center mt-6">
              <div className="relative w-full max-w-full overflow-hidden">
                {/* Animated Flow Diagram */}
                <div className="relative bg-gradient-to-br from-slate-900/80 to-slate-800/80 backdrop-blur-sm rounded-2xl p-6 border border-cyan-500/30 shadow-2xl">
                  <svg className="w-full h-auto" viewBox="0 0 440 420" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
                    {/* Animated flowing lines */}
                    <defs>
                      {/* Enhanced gradients for flowing lines */}
                      <linearGradient id="cyanFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(6, 182, 212, 0)" />
                        <stop offset="30%" stopColor="rgba(6, 182, 212, 0.3)" />
                        <stop offset="50%" stopColor="rgba(6, 182, 212, 1)" />
                        <stop offset="70%" stopColor="rgba(6, 182, 212, 0.3)" />
                        <stop offset="100%" stopColor="rgba(6, 182, 212, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="2s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="2s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      <linearGradient id="magentaFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(236, 72, 153, 0)" />
                        <stop offset="30%" stopColor="rgba(236, 72, 153, 0.3)" />
                        <stop offset="50%" stopColor="rgba(236, 72, 153, 1)" />
                        <stop offset="70%" stopColor="rgba(236, 72, 153, 0.3)" />
                        <stop offset="100%" stopColor="rgba(236, 72, 153, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="2.5s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="2.5s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      <linearGradient id="greenFlow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(34, 197, 94, 0)" />
                        <stop offset="30%" stopColor="rgba(34, 197, 94, 0.3)" />
                        <stop offset="50%" stopColor="rgba(34, 197, 94, 1)" />
                        <stop offset="70%" stopColor="rgba(34, 197, 94, 0.3)" />
                        <stop offset="100%" stopColor="rgba(34, 197, 94, 0)" />
                        <animate attributeName="x1" values="-100%;200%" dur="3s" repeatCount="indefinite" />
                        <animate attributeName="x2" values="0%;300%" dur="3s" repeatCount="indefinite" />
                      </linearGradient>
                      
                      {/* Enhanced glow effect for particles */}
                      <filter id="glow">
                        <feGaussianBlur stdDeviation="2.5" result="coloredBlur"/>
                        <feMerge>
                          <feMergeNode in="coloredBlur"/>
                          <feMergeNode in="SourceGraphic"/>
                        </feMerge>
                      </filter>
                      
                      {/* Motion blur for particles */}
                      <filter id="motionBlur">
                        <feGaussianBlur in="SourceGraphic" stdDeviation="1.5,0" />
                      </filter>
                      
                      {/* Radial gradient for particle glow */}
                      <radialGradient id="particleGlowCyan">
                        <stop offset="0%" stopColor="#06b6d4" stopOpacity="1"/>
                        <stop offset="50%" stopColor="#06b6d4" stopOpacity="0.6"/>
                        <stop offset="100%" stopColor="#06b6d4" stopOpacity="0"/>
                      </radialGradient>
                      
                      <radialGradient id="particleGlowMagenta">
                        <stop offset="0%" stopColor="#ec4899" stopOpacity="1"/>
                        <stop offset="50%" stopColor="#ec4899" stopOpacity="0.6"/>
                        <stop offset="100%" stopColor="#ec4899" stopOpacity="0"/>
                      </radialGradient>
                      
                      <radialGradient id="particleGlowGreen">
                        <stop offset="0%" stopColor="#22c55e" stopOpacity="1"/>
                        <stop offset="50%" stopColor="#22c55e" stopOpacity="0.6"/>
                        <stop offset="100%" stopColor="#22c55e" stopOpacity="0"/>
                      </radialGradient>
                    </defs>
                    
                    {/* Planning Orchestrator - Left Center */}
                    <rect x="20" y="170" width="100" height="60" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#glow)"/>
                    <text x="70" y="192" textAnchor="middle" fill="white" fontSize="12" fontWeight="400">Planning</text>
                    <text x="70" y="208" textAnchor="middle" fill="white" fontSize="12" fontWeight="400">Orchestrator</text>
                    
                    {/* Market Research Analyst - Top */}
                    <rect x="180" y="15" width="110" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#glow)"/>
                    <text x="235" y="33" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Market Research</text>
                    <text x="235" y="47" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Analyst</text>
                    
                    {/* Business Requirement Document */}
                    <rect x="180" y="75" width="110" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#glow)"/>
                    <text x="235" y="93" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Business Requirement</text>
                    <text x="235" y="107" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Document</text>
                    
                    {/* User Story Generator */}
                    <rect x="180" y="135" width="110" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#glow)"/>
                    <text x="235" y="153" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">User Story</text>
                    <text x="235" y="167" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Generator</text>
                    
                    {/* Knowledge Graph Builder */}
                    <rect x="180" y="195" width="110" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#glow)"/>
                    <text x="235" y="213" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Knowledge Graph</text>
                    <text x="235" y="227" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Builder</text>
                    
                    {/* Document Query & FAQ Generator */}
                    <rect x="180" y="255" width="110" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#glow)"/>
                    <text x="235" y="273" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">Document Query &</text>
                    <text x="235" y="287" textAnchor="middle" fill="white" fontSize="9.5" fontWeight="400">FAQ Generator</text>
                    
                    {/* Effort Planner */}
                    <rect x="180" y="315" width="110" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#glow)"/>
                    <text x="235" y="338" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Effort Planner</text>
                    
                    {/* User Story Validator - Right */}
                    <rect x="320" y="95" width="100" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#glow)"/>
                    <text x="370" y="113" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">User Story</text>
                    <text x="370" y="127" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Validator</text>
                    
                    {/* User Story Estimator - Right Middle */}
                    <rect x="320" y="155" width="100" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#glow)"/>
                    <text x="370" y="173" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">User Story</text>
                    <text x="370" y="187" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">Estimator</text>
                    
                    {/* MVP Analyzer - Right */}
                    <rect x="320" y="215" width="100" height="50" rx="10" fill="none" stroke="#06b6d4" strokeWidth="1.5" filter="url(#glow)"/>
                    <text x="370" y="238" textAnchor="middle" fill="white" fontSize="10" fontWeight="400">MVP Analyzer</text>
                    
                    {/* Flowing connection lines with animation */}
                    {/* Cyan flows from Orchestrator to middle column */}
                    <path d="M 120 180 Q 150 40, 180 40" fill="none" stroke="url(#cyanFlow)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 188 Q 150 100, 180 100" fill="none" stroke="url(#cyanFlow)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 196 Q 150 160, 180 160" fill="none" stroke="url(#cyanFlow)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 204 Q 150 220, 180 220" fill="none" stroke="url(#cyanFlow)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 212 Q 150 280, 180 280" fill="none" stroke="url(#cyanFlow)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 120 220 Q 150 340, 180 340" fill="none" stroke="url(#cyanFlow)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Vertical magenta flows in middle column */}
                    <line x1="235" y1="65" x2="235" y2="75" stroke="url(#magentaFlow)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="125" x2="235" y2="135" stroke="url(#magentaFlow)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="185" x2="235" y2="195" stroke="url(#magentaFlow)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="245" x2="235" y2="255" stroke="url(#magentaFlow)" strokeWidth="3" opacity="0.9"/>
                    <line x1="235" y1="305" x2="235" y2="315" stroke="url(#magentaFlow)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Magenta flows from middle to right column */}
                    <path d="M 290 160 L 320 120" fill="none" stroke="url(#magentaFlow)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 160 L 320 180" fill="none" stroke="url(#magentaFlow)" strokeWidth="3" opacity="0.9"/>
                    <path d="M 290 160 L 320 240" fill="none" stroke="url(#magentaFlow)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Vertical connection in right column */}
                    <line x1="370" y1="145" x2="370" y2="155" stroke="url(#magentaFlow)" strokeWidth="3" opacity="0.9"/>
                    <line x1="370" y1="205" x2="370" y2="215" stroke="url(#magentaFlow)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Green feedback loop from right back to bottom */}
                    <path d="M 370 265 L 370 380 Q 370 400, 350 400 L 235 400 Q 215 400, 215 380 L 215 365" fill="none" stroke="url(#greenFlow)" strokeWidth="3" opacity="0.9"/>
                    
                    {/* Directional Arrows with glow */}
                    <polygon points="235,77 230,72 240,72" fill="#06b6d4" filter="url(#glow)"/>
                    <polygon points="235,137 230,132 240,132" fill="#06b6d4" filter="url(#glow)"/>
                    <polygon points="235,197 230,192 240,192" fill="#06b6d4" filter="url(#glow)"/>
                    <polygon points="235,257 230,252 240,252" fill="#06b6d4" filter="url(#glow)"/>
                    <polygon points="235,317 230,312 240,312" fill="#06b6d4" filter="url(#glow)"/>
                    <polygon points="318,118 314,115 314,121" fill="#ec4899" filter="url(#glow)"/>
                    <polygon points="318,178 314,175 314,181" fill="#ec4899" filter="url(#glow)"/>
                    <polygon points="318,238 314,235 314,241" fill="#ec4899" filter="url(#glow)"/>
                    <polygon points="370,157 367,153 373,153" fill="#ec4899" filter="url(#glow)"/>
                    <polygon points="370,217 367,213 373,213" fill="#ec4899" filter="url(#glow)"/>
                    <polygon points="215,367 212,371 218,371" fill="#22c55e" filter="url(#glow)"/>
                    
                    {/* Animated particles along paths */}
                    {/* Cyan Path 1 - Multiple particles with glow halos */}
                    <g>
                      <circle r="10" fill="url(#particleGlowCyan)" opacity="0.3" filter="url(#glow)">
                        <animateMotion dur="2.5s" repeatCount="indefinite" path="M 120 180 Q 150 40, 180 40"/>
                      </circle>
                      <circle r="5" fill="#06b6d4" opacity="1" filter="url(#glow)">
                        <animateMotion dur="2.5s" repeatCount="indefinite" path="M 120 180 Q 150 40, 180 40"/>
                        <animate attributeName="r" values="4;6;4" dur="1s" repeatCount="indefinite"/>
                      </circle>
                    </g>
                    
                    {/* Cyan Path 2 - Particle with delay */}
                    <g>
                      <circle r="10" fill="url(#particleGlowCyan)" opacity="0.3" filter="url(#glow)">
                        <animateMotion dur="2.8s" begin="0.5s" repeatCount="indefinite" path="M 120 188 Q 150 100, 180 100"/>
                      </circle>
                      <circle r="5" fill="#06b6d4" opacity="1" filter="url(#glow)">
                        <animateMotion dur="2.8s" begin="0.5s" repeatCount="indefinite" path="M 120 188 Q 150 100, 180 100"/>
                        <animate attributeName="r" values="4;6;4" dur="1.2s" repeatCount="indefinite"/>
                      </circle>
                    </g>
                    
                    {/* Cyan Path 3 */}
                    <g>
                      <circle r="10" fill="url(#particleGlowCyan)" opacity="0.3" filter="url(#glow)">
                        <animateMotion dur="2.6s" begin="1s" repeatCount="indefinite" path="M 120 196 Q 150 160, 180 160"/>
                      </circle>
                      <circle r="5" fill="#06b6d4" opacity="1" filter="url(#glow)">
                        <animateMotion dur="2.6s" begin="1s" repeatCount="indefinite" path="M 120 196 Q 150 160, 180 160"/>
                        <animate attributeName="r" values="4;6;4" dur="0.9s" repeatCount="indefinite"/>
                      </circle>
                    </g>
                    
                    {/* Cyan Path 4 */}
                    <g>
                      <circle r="10" fill="url(#particleGlowCyan)" opacity="0.3" filter="url(#glow)">
                        <animateMotion dur="3s" begin="0.3s" repeatCount="indefinite" path="M 120 204 Q 150 220, 180 220"/>
                      </circle>
                      <circle r="5" fill="#06b6d4" opacity="1" filter="url(#glow)">
                        <animateMotion dur="3s" begin="0.3s" repeatCount="indefinite" path="M 120 204 Q 150 220, 180 220"/>
                        <animate attributeName="r" values="4;6;4" dur="1.1s" repeatCount="indefinite"/>
                      </circle>
                    </g>
                    
                    {/* Magenta Vertical Path - Multiple particles */}
                    <g>
                      <circle r="10" fill="url(#particleGlowMagenta)" opacity="0.3" filter="url(#glow)">
                        <animateMotion dur="3.5s" repeatCount="indefinite" path="M 235 65 L 235 365"/>
                      </circle>
                      <circle r="5" fill="#ec4899" opacity="1" filter="url(#glow)">
                        <animateMotion dur="3.5s" repeatCount="indefinite" path="M 235 65 L 235 365"/>
                        <animate attributeName="r" values="4;7;4" dur="1s" repeatCount="indefinite"/>
                      </circle>
                    </g>
                    
                    {/* Magenta to Right Path 1 */}
                    <g>
                      <circle r="10" fill="url(#particleGlowMagenta)" opacity="0.3" filter="url(#glow)">
                        <animateMotion dur="2.2s" begin="0.6s" repeatCount="indefinite" path="M 290 160 L 320 120"/>
                      </circle>
                      <circle r="5" fill="#ec4899" opacity="1" filter="url(#glow)">
                        <animateMotion dur="2.2s" begin="0.6s" repeatCount="indefinite" path="M 290 160 L 320 120"/>
                        <animate attributeName="r" values="4;6;4" dur="0.8s" repeatCount="indefinite"/>
                      </circle>
                    </g>
                    
                    {/* Magenta to Right Path 2 */}
                    <g>
                      <circle r="10" fill="url(#particleGlowMagenta)" opacity="0.3" filter="url(#glow)">
                        <animateMotion dur="2s" begin="0.2s" repeatCount="indefinite" path="M 290 160 L 320 180"/>
                      </circle>
                      <circle r="5" fill="#ec4899" opacity="1" filter="url(#glow)">
                        <animateMotion dur="2s" begin="0.2s" repeatCount="indefinite" path="M 290 160 L 320 180"/>
                        <animate attributeName="r" values="4;6;4" dur="1.3s" repeatCount="indefinite"/>
                      </circle>
                    </g>
                    
                    {/* Magenta to Right Path 3 */}
                    <g>
                      <circle r="10" fill="url(#particleGlowMagenta)" opacity="0.3" filter="url(#glow)">
                        <animateMotion dur="2.4s" begin="0.8s" repeatCount="indefinite" path="M 290 160 L 320 240"/>
                      </circle>
                      <circle r="5" fill="#ec4899" opacity="1" filter="url(#glow)">
                        <animateMotion dur="2.4s" begin="0.8s" repeatCount="indefinite" path="M 290 160 L 320 240"/>
                        <animate attributeName="r" values="4;6;4" dur="1s" repeatCount="indefinite"/>
                      </circle>
                    </g>
                    
                    {/* Green Feedback Loop - Multiple particles */}
                    <g>
                      <circle r="10" fill="url(#particleGlowGreen)" opacity="0.3" filter="url(#glow)">
                        <animateMotion dur="4s" repeatCount="indefinite" path="M 370 265 L 370 380 Q 370 400, 350 400 L 235 400 Q 215 400, 215 380 L 215 365"/>
                      </circle>
                      <circle r="5" fill="#22c55e" opacity="1" filter="url(#glow)">
                        <animateMotion dur="4s" repeatCount="indefinite" path="M 370 265 L 370 380 Q 370 400, 350 400 L 235 400 Q 215 400, 215 380 L 215 365"/>
                        <animate attributeName="r" values="4;7;4" dur="1.2s" repeatCount="indefinite"/>
                      </circle>
                    </g>
                    
                    {/* Green Feedback Loop - Second particle with delay */}
                    <g>
                      <circle r="10" fill="url(#particleGlowGreen)" opacity="0.3" filter="url(#glow)">
                        <animateMotion dur="4s" begin="2s" repeatCount="indefinite" path="M 370 265 L 370 380 Q 370 400, 350 400 L 235 400 Q 215 400, 215 380 L 215 365"/>
                      </circle>
                      <circle r="5" fill="#22c55e" opacity="1" filter="url(#glow)">
                        <animateMotion dur="4s" begin="2s" repeatCount="indefinite" path="M 370 265 L 370 380 Q 370 400, 350 400 L 235 400 Q 215 400, 215 380 L 215 365"/>
                        <animate attributeName="r" values="4;7;4" dur="1s" repeatCount="indefinite"/>
                      </circle>
                    </g>
                  </svg>
                </div>
              </div>
            </div>

            {/* Right: Benefits Cards */}
            <div className="flex flex-col justify-between lg:w-[32%] mt-6 h-full">
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-teal-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-teal-300 font-bold text-lg mb-3">80% Faster Planning</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Reduce planning cycles from weeks to days with automated requirement analysis</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-blue-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1 my-3">
                <h3 className="text-blue-300 font-bold text-lg mb-3">95% Accuracy</h3>
                <p className="text-gray-300 text-sm leading-relaxed">AI-validated user stories and requirements ensure high-quality deliverables</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-purple-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-purple-300 font-bold text-lg mb-3">Intelligent Insights</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Knowledge graphs reveal hidden dependencies and optimization opportunities</p>
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
                className="bg-[#1a2642]/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6 hover:border-emerald-500/30 transition-all duration-300 hover:shadow-lg hover:shadow-emerald-500/10 cursor-pointer hover:scale-105"
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

        {/* Agent Detail Card */}
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