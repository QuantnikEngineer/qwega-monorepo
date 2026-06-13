import { Network, RefreshCw, Code2, GitCompare, Home } from 'lucide-react';
import { useState } from 'react';
import { AgentDetailCard, agentDetails } from './AgentDetailCard';

const agents = [
  { name: 'Legacy Analyzer', icon: Network, color: 'from-rose-500 to-rose-600', description: 'Analyze and map legacy system architecture' },
  { name: 'Code Modernizer', icon: Code2, color: 'from-purple-500 to-purple-600', description: 'Automated code migration and refactoring' },
  { name: 'API Migrator', icon: RefreshCw, color: 'from-blue-500 to-blue-600', description: 'Migrate APIs to modern frameworks' },
  { name: 'Technology Advisor', icon: GitCompare, color: 'from-cyan-500 to-cyan-600', description: 'Recommend optimal technology stack' }
];

export function ModernizationDetail({ onBack }: { onBack: () => void }) {
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
              <h1 className="text-2xl lg:text-3xl bg-gradient-to-r from-rose-600 to-rose-300 bg-clip-text text-transparent mb-8 font-normal">Modernization</h1>
              <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">Transform legacy systems into modern, cloud-native applications with AI-powered migration tools. Analyze, refactor, and migrate codebases automatically while preserving business logic.</p>
            </div>
            <div className="flex flex-col justify-between lg:w-[32%]">
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-rose-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-rose-300 font-bold text-lg mb-3">70% Faster Migration</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Automate legacy system modernization</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-purple-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1 my-3">
                <h3 className="text-purple-300 font-bold text-lg mb-3">95% Code Preservation</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Maintain business logic during migration</p>
              </div>
            </div>
          </div>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          {agents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div key={agent.name} className="bg-[#1a2642]/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6 hover:border-rose-500/30 transition-all duration-300 hover:shadow-lg hover:shadow-rose-500/10 cursor-pointer hover:scale-105" onClick={() => setSelectedAgent(agent.name)}>
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
