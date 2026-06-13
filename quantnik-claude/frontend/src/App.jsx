import React, { useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar.jsx';
import { Chat } from './components/Chat.jsx';
import { SkillsPanel } from './components/SkillsPanel.jsx';
import { SettingsPanel } from './components/SettingsPanel.jsx';
import { McpPanel } from './components/McpPanel.jsx';
import { ReposPanel } from './components/ReposPanel.jsx';
import { FilesPanel } from './components/FilesPanel.jsx';
import { api } from './lib/api.js';

const TABS = ['chat', 'files', 'repos', 'skills', 'mcp', 'settings'];

export default function App() {
  const [projects, setProjects] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [tab, setTab] = useState('chat');
  const [pendingSend, setPendingSend] = useState(null);

  const sendToChat = (message) => {
    setPendingSend({ message, at: Date.now() });
    setTab('chat');
  };

  const refresh = async () => {
    const list = await api.listProjects();
    setProjects(list);
    setActiveId((curr) => (list.find((p) => p.id === curr) ? curr : list[0]?.id ?? null));
  };

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, []);

  const active = projects.find((p) => p.id === activeId);

  return (
    <div className="app">
      <Sidebar
        projects={projects}
        activeId={activeId}
        onSelect={setActiveId}
        onChanged={refresh}
      />
      <main className="main">
        {!active && <div className="empty">Create a project to get started.</div>}
        {active && (
          <>
            <div className="tabs">
              {TABS.map((t) => (
                <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
                  {t}
                </button>
              ))}
              <div style={{ flex: 1 }} />
              <div style={{ padding: '12px 18px', color: 'var(--muted)', fontSize: 12 }}>
                {active.model} · {active.permission_mode}
              </div>
            </div>
            {tab === 'chat' && (
              <Chat
                project={active}
                onProjectUpdated={refresh}
                pendingSend={pendingSend}
                onPendingSent={() => setPendingSend(null)}
              />
            )}
            {tab === 'files' && <FilesPanel project={active} onSendToSkill={sendToChat} />}
            {tab === 'repos' && <ReposPanel project={active} />}
            {tab === 'skills' && <SkillsPanel project={active} />}
            {tab === 'mcp' && <McpPanel project={active} />}
            {tab === 'settings' && <SettingsPanel project={active} onChanged={refresh} />}
          </>
        )}
      </main>
    </div>
  );
}
