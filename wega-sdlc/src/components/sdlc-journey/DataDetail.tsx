import { Database, BarChart3, LineChart, TrendingUp, Home } from 'lucide-react';
import { useState } from 'react';
import { AgentDetailCard, agentDetails } from './AgentDetailCard';

const agents = [
  { name: 'Data Quality Checker', icon: Database, color: 'from-sky-500 to-sky-600', description: 'Automated data quality assessment' },
  { name: 'ETL Pipeline Builder', icon: LineChart, color: 'from-blue-500 to-blue-600', description: 'Intelligent ETL pipeline generation' },
  { name: 'Analytics Engine', icon: BarChart3, color: 'from-purple-500 to-purple-600', description: 'AI-powered data analytics and insights' },
  { name: 'Data Governance Agent', icon: TrendingUp, color: 'from-cyan-500 to-cyan-600', description: 'Ensure data compliance and governance' }
];

export function DataDetail({ onBack }: { onBack: () => void }) {
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
              <h1 className="text-2xl lg:text-3xl bg-gradient-to-r from-sky-600 to-sky-300 bg-clip-text text-transparent mb-8 font-normal">Data</h1>
              <p className="text-gray-300 text-[0.72rem] leading-relaxed mb-6">Harness the power of your data with AI-driven analytics, quality assurance, and pipeline automation. Transform raw data into actionable insights while ensuring governance and compliance.</p>
            </div>
            <div className="flex flex-col justify-between lg:w-[32%]">
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-sky-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1">
                <h3 className="text-sky-300 font-bold text-lg mb-3">85% Better Data Quality</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Automated quality checks and cleansing</p>
              </div>
              <div className="bg-slate-900/80 backdrop-blur-sm border-2 border-blue-500/50 rounded-xl p-8 flex flex-col justify-center shadow-lg flex-1 my-3">
                <h3 className="text-blue-300 font-bold text-lg mb-3">10x Faster Insights</h3>
                <p className="text-gray-300 text-sm leading-relaxed">Real-time analytics and visualization</p>
              </div>
            </div>
          </div>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          {agents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div key={agent.name} className="bg-[#1a2642]/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-6 hover:border-sky-500/30 transition-all duration-300 hover:shadow-lg hover:shadow-sky-500/10 cursor-pointer hover:scale-105" onClick={() => setSelectedAgent(agent.name)}>
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
