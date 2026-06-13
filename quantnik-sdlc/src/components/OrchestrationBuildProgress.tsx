import React from 'react';
import { Button } from './ui/button';
import { CheckCircle, Settings, RefreshCw, Rocket, Download } from 'lucide-react';

interface OrchestrationBuildProgressProps {
  isBuilding: boolean;
  isBuildComplete: boolean;
  buildProgress: number;
  currentBuildStep: string;
  agents: Array<{ name: string; description: string; icon: any; color: string }>;
  onComplete?: () => void;
  onViewDetails?: () => void;
  onDownloadContainer?: () => void;
}

export function OrchestrationBuildProgress({
  isBuilding,
  isBuildComplete,
  buildProgress,
  currentBuildStep,
  agents,
  onComplete,
  onViewDetails,
  onDownloadContainer
}: OrchestrationBuildProgressProps) {
  if (isBuildComplete) {
    return (
      <div className="max-w-6xl mx-auto mt-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
        <div className="bg-white/95 dark:bg-slate-900/95 rounded-2xl p-8 shadow-2xl border-2 border-green-500">
          <div className="text-center">
            <div className="w-20 h-20 rounded-full bg-green-500 flex items-center justify-center mx-auto mb-6 animate-in zoom-in duration-500">
              <CheckCircle className="w-12 h-12 text-white" />
            </div>
            <h3 className="text-3xl font-bold text-card-foreground mb-3">
              Orchestration Complete!
            </h3>
            <p className="text-xl text-muted-foreground mb-6">
              Your AI agent network is ready to use
            </p>
            
            <div className="bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-900 rounded-lg p-6 mb-8">
              <p className="text-sm text-green-800 dark:text-green-400 mb-4">
                ✓ All {agents.length} AI agents successfully containerized<br/>
                ✓ Inter-agent communication protocols established<br/>
                ✓ Data pipelines configured and validated<br/>
                ✓ API integrations verified<br/>
                ✓ Orchestration network fully operational
              </p>
            </div>

            <div className="flex justify-center gap-4">
              <Button
                size="lg"
                className="bg-green-600 hover:bg-green-700 text-white"
                onClick={onComplete}
              >
                <Rocket className="w-5 h-5 mr-2" />
                Start Using QUANTNIK
              </Button>
              <Button
                size="lg"
                variant="outline"
                onClick={onViewDetails}
              >
                View Details
              </Button>
              <Button
                size="lg"
                variant="outline"
                onClick={onDownloadContainer}
              >
                <Download className="w-5 h-5 mr-2" />
                Download Container
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!isBuilding) return null;

  return (
    <div className="max-w-6xl mx-auto mt-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="bg-white/95 dark:bg-slate-900/95 rounded-2xl p-8 shadow-2xl">
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-full bg-[#3498B3] flex items-center justify-center mx-auto mb-4 animate-pulse">
            <Settings className="w-8 h-8 text-white animate-spin" />
          </div>
          <h3 className="text-2xl font-bold text-card-foreground mb-2">
            Building Orchestration Network
          </h3>
          <p className="text-muted-foreground">
            Setting up integrations between AI agents...
          </p>
        </div>

        {/* Progress Bar */}
        <div className="mb-6">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm text-muted-foreground">Progress</span>
            <span className="text-sm font-semibold text-card-foreground">{Math.round(buildProgress)}%</span>
          </div>
          <div className="w-full h-3 bg-muted rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-[#3498B3] to-[#355493] transition-all duration-500 ease-out"
              style={{ width: `${buildProgress}%` }}
            />
          </div>
        </div>

        {/* Current Step */}
        <div className="p-4 bg-muted/50 rounded-lg mb-6">
          <div className="flex items-center gap-3">
            <RefreshCw className="w-5 h-5 text-[#3498B3] animate-spin" />
            <span className="text-sm text-card-foreground">{currentBuildStep}</span>
          </div>
        </div>

        {/* Agent Integration Visualization */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {agents.slice(0, 8).map((agent, index) => {
            const Icon = agent.icon;
            const isActive = buildProgress > (index / agents.length) * 100;
            return (
              <div
                key={index}
                className={`flex flex-col items-center gap-2 p-3 rounded-lg border-2 transition-all duration-500 ${
                  isActive
                    ? 'border-[#3498B3] bg-[#3498B3]/10'
                    : 'border-border bg-muted/30 opacity-50'
                }`}
              >
                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-500 ${
                    isActive ? 'scale-110' : ''
                  }`}
                  style={{ backgroundColor: agent.color }}
                >
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <span className="text-xs text-center text-card-foreground line-clamp-2">
                  {agent.name}
                </span>
                {isActive && (
                  <CheckCircle className="w-4 h-4 text-green-500" />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}