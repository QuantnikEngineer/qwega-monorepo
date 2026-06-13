interface MiniSDLCJourneyProps {
  currentStage: string;
  onStageClick: (stageName: string) => void;
}

export function MiniSDLCJourney({ currentStage, onStageClick }: MiniSDLCJourneyProps) {
  const stages = [
    { name: 'Planning', icon: '📋', color: 'from-blue-500 to-cyan-500', borderColor: 'border-blue-500' },
    { name: 'Analysis & Design', icon: '🎨', color: 'from-purple-500 to-pink-500', borderColor: 'border-purple-500' },
    { name: 'Build', icon: '⚡', color: 'from-orange-500 to-yellow-500', borderColor: 'border-orange-500' },
    { name: 'Testing', icon: '🔍', color: 'from-green-500 to-emerald-500', borderColor: 'border-green-500' },
    { name: 'Deployment', icon: '🚀', color: 'from-indigo-500 to-blue-500', borderColor: 'border-indigo-500' },
    { name: 'Reliability', icon: '📊', color: 'from-pink-500 to-rose-500', borderColor: 'border-pink-500' },
    { name: 'Security', icon: '🔒', color: 'from-teal-500 to-cyan-500', borderColor: 'border-teal-500' },
    { name: 'Governance', icon: '🛡️', color: 'from-rose-500 to-red-500', borderColor: 'border-rose-500' }
  ];

  return (
    <div className="w-full bg-gradient-to-r from-slate-900/50 via-slate-800/50 to-slate-900/50 backdrop-blur-sm py-1.5 px-2 border-b border-blue-500/20">
      <div className="max-w-3xl mx-auto">
        {/* Desktop View - Horizontal */}
        <div className="hidden lg:flex items-center justify-center gap-0">
          {stages.map((stage, index) => {
            const isActive = stage.name === currentStage;
            
            return (
              <div key={stage.name} className="flex items-center">
                {/* Stage Button */}
                <button
                  onClick={() => onStageClick(stage.name)}
                  className={`
                    group relative flex flex-col items-center gap-0 transition-all duration-300
                    ${isActive ? 'scale-105' : 'scale-100 opacity-70 hover:opacity-100 hover:scale-100'}
                  `}
                  title={stage.name}
                >
                  {/* Stage Circle */}
                  <div
                    className={`
                      w-6 h-6 rounded-full flex items-center justify-center text-xs
                      transition-all duration-300
                      ${isActive 
                        ? `bg-gradient-to-br ${stage.color} border ${stage.borderColor} shadow-lg` 
                        : 'bg-slate-700/50 border border-slate-600 group-hover:bg-slate-600/50'
                      }
                    `}
                    style={{
                      boxShadow: isActive ? `0 0 15px rgba(59, 130, 246, 0.4)` : 'none'
                    }}
                  >
                    <span>{stage.icon}</span>
                  </div>
                  
                  {/* Stage Name */}
                  <span 
                    className={`
                      text-[7px] font-medium text-center max-w-[50px] leading-tight mt-0.5
                      ${isActive 
                        ? `text-transparent bg-clip-text bg-gradient-to-r ${stage.color}` 
                        : 'text-gray-400 group-hover:text-gray-300'
                      }
                    `}
                  >
                    {stage.name}
                  </span>

                  {/* Active Indicator */}
                  {isActive && (
                    <div className="absolute -bottom-0 left-1/2 -translate-x-1/2 w-0.5 h-0.5 bg-blue-500 rounded-full animate-pulse" />
                  )}
                </button>

                {/* Connector Line */}
                {index < stages.length - 1 && (
                  <div className={`h-px w-1 ${isActive || stages[index + 1].name === currentStage ? 'bg-blue-500' : 'bg-slate-700'} transition-colors duration-300`} />
                )}
              </div>
            );
          })}
        </div>

        {/* Mobile View - Horizontal Scroll */}
        <div className="lg:hidden flex items-center gap-1.5 overflow-x-auto pb-1.5 scrollbar-hide">
          {stages.map((stage) => {
            const isActive = stage.name === currentStage;
            
            return (
              <button
                key={stage.name}
                onClick={() => onStageClick(stage.name)}
                className={`
                  flex-shrink-0 flex items-center gap-1 px-2 py-1 rounded-lg transition-all duration-300
                  ${isActive 
                    ? `bg-gradient-to-r ${stage.color} border ${stage.borderColor}` 
                    : 'bg-slate-700/50 border border-slate-600 hover:bg-slate-600/50'
                  }
                `}
              >
                <span className="text-sm">{stage.icon}</span>
                <span className={`text-[9px] font-medium whitespace-nowrap ${isActive ? 'text-white' : 'text-gray-300'}`}>
                  {stage.name}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}