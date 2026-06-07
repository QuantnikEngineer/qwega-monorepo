import { Cpu, Brain, Sparkles, Zap, Home } from 'lucide-react';
import { useState } from 'react';
import { AgentDetailCard, agentDetails } from './AgentDetailCard';

const agents = [
  { name: 'Code Copilot', icon: Brain, color: 'from-orange-500 to-orange-600', description: 'AI pair programming assistant' },
  { name: 'Smart Debugger', icon: Zap, color: 'from-yellow-500 to-yellow-600', description: 'Intelligent bug detection and fixing' },
  { name: 'ML Model Trainer', icon: Cpu, color: 'from-purple-500 to-purple-600', description: 'Automated machine learning model training' },
  { name: 'AI Code Reviewer', icon: Sparkles, color: 'from-pink-500 to-pink-600', description: 'Advanced AI-powered code review' }
];

export function AIEnablersDetail({ onBack }: { onBack: () => void }) {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  return (
    <div className="relative min-h-[600px] bg-gradient-to-br from-[#0a1628] via-[#132340] to-[#0f1e36] overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(120,119,198,0.05),transparent_50%)]"></div>
      <div className="container mx-auto px-6 py-16 relative z-10">
        <div className="mb-12 max-w-7xl mx-auto relative">
          <button onClick={onBack} className="mb-8 flex items-center gap-2 text-white hover:text-gray-300 transition-colors duration-300 group">
            <div className="w-8 h-8 rounded flex items-center justify-center transition-all duration-300"><Home className="w-5 h-5" /></div>
            <span className="text-xs font-medium">Back to Home</span>
          </button>
          <div className="flex flex-col lg:flex-row gap-5 items-stretch">
            <div className="lg:w-[30%] flex flex-col">
              <h1 className="text-2xl lg:text-3xl bg-gradient-to-r from-orange-600 to-orange-300 bg-clip-text text-transparent mb-8 font-normal">AI Enablers</h1>
              <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">Supercharge your development with cutting-edge AI assistants. From intelligent code completion to automated debugging, our AI enablers amplify developer productivity.</p>
            </div>
            <div className="flex flex-col justify-between lg:w-[32%]">
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-orange-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-orange-300 font-bold text-lg mb-3">3x Developer Velocity</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Accelerate coding with AI assistance</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-yellow-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1 my-3">
                <h3 className="text-yellow-300 font-bold text-lg mb-3">90% Faster Debugging</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Identify and fix issues instantly</p>
              </div>
            </div>
          </div>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          {agents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div key={agent.name} className="bg-[#1a2642]/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6 hover:border-orange-500/30 transition-all duration-300 hover:shadow-lg hover:shadow-orange-500/10 cursor-pointer hover:scale-105" onClick={() => setSelectedAgent(agent.name)}>
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
