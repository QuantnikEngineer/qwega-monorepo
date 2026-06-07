import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Sidebar } from './components/Sidebar.jsx';
import { Chat } from './components/Chat.jsx';
import { SkillsPanel } from './components/SkillsPanel.jsx';
import { SettingsPanel } from './components/SettingsPanel.jsx';
import { McpPanel } from './components/McpPanel.jsx';
import { ReposPanel } from './components/ReposPanel.jsx';
import { FilesPanel } from './components/FilesPanel.jsx';
import { DashboardPanel } from './components/DashboardPanel.jsx';
import { HomePage } from './components/HomePage.jsx';
import { ContextFabricPanel } from './components/ContextFabricPanel.jsx';
import { AuthGate, AuthHeader } from './components/AuthGate.jsx';
import { WindowFrame, TabBar, StatusBar } from './components/ui.jsx';
import { api } from './lib/api.js';

const TABS = [
  { id: 'chat',      glyph: '>_' },
  { id: 'dashboard', glyph: '◫' },
  { id: 'files',     glyph: '▤' },
  { id: 'repos',     glyph: '▣' },
  { id: 'context',   glyph: '◈' },
  { id: 'skills',    glyph: '⚙' },
  { id: 'mcp',       glyph: '⌬' },
  { id: 'settings',  glyph: '✦' },
];

// Legacy localStorage keys — kept only for one-shot migration into the URL
// the first time a user hits this build. Removed after migration so the URL
// is the single source of truth going forward.
const LS_TAB     = 'wega.app.tab';
const LS_PROJECT = 'wega.app.activeProjectId';

// URL → state mapping. The Context Fabric is a wega2-level surface as well
// as a per-project tab, so we recognise both:
//   /context                   → global (org) Context Fabric
//   /projects/:id              → project, tab defaults to chat
//   /projects/:id/:tab         → project + specific tab
//   anything else (incl. "/")  → home page
function parsePath(pathname) {
  if (/^\/context\/?$/.test(pathname)) {
    return { projectId: null, tab: null, globalRoute: 'context' };
  }
  const m = pathname.match(/^\/projects\/(\d+)(?:\/([a-z-]+))?\/?$/);
  if (!m) return { projectId: null, tab: null, globalRoute: null };
  return {
    projectId: Number(m[1]),
    tab: m[2] && TABS.some((t) => t.id === m[2]) ? m[2] : null,
    globalRoute: null,
  };
}

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const { projectId: urlProjectId, tab: urlTab, globalRoute } = parsePath(location.pathname);

  // URL is the source of truth for active project + tab. setActiveId/setTab
  // below are navigation actions, not setState calls.
  const activeId = urlProjectId;
  const tab = urlTab || 'chat';

  const [projects, setProjects] = useState([]);
  const [pendingSend, setPendingSend] = useState(null);
  const [theme, setTheme] = useState(() => {
    const stored = localStorage.getItem('wega-theme');
    // migrate legacy values to the sunset family (the new default)
    if (stored === 'dark' || stored === 'cyber-dark') return 'sunset-dark';
    if (stored === 'light' || stored === 'cyber-light') return 'sunset-light';
    return stored || 'sunset-dark';
  });
  const [sessionInfo, setSessionInfo] = useState({ tools: [], mcpServers: [], usage: null });

  useEffect(() => {
    const polarity = theme.endsWith('-light') ? 'light' : 'dark';
    document.body.className = `theme-${theme} ${polarity}`;
    localStorage.setItem('wega-theme', theme);
  }, [theme]);

  // Navigation actions — both fire pushState through react-router so back /
  // forward + URL-bar typing work naturally. Tab change preserves the
  // current project; project change preserves the current tab.
  const setActiveId = (id) => {
    if (id == null) navigate('/');
    else navigate(`/projects/${id}/${tab}`);
  };
  const setTab = (newTab) => {
    if (activeId == null) return;
    navigate(`/projects/${activeId}/${newTab}`);
  };

  const sendToChat = (message) => {
    setPendingSend({ message, at: Date.now() });
    setTab('chat');
  };

  const refresh = async () => {
    const list = await api.listProjects();
    setProjects(list);

    if (urlProjectId == null) {
      // "/" is the home page now (HomePage.jsx). Only auto-redirect off "/"
      // if the user has legacy localStorage state from before URL routing
      // shipped — one-shot migration so people who upgrade mid-session land
      // back where they were. After migration, "/" stays as the home page.
      let migratedId = null;
      let migratedTab = 'chat';
      try {
        const lsId = Number(localStorage.getItem(LS_PROJECT));
        if (Number.isFinite(lsId) && list.find((p) => p.id === lsId)) migratedId = lsId;
        const lsTab = localStorage.getItem(LS_TAB);
        if (lsTab && TABS.some((t) => t.id === lsTab)) migratedTab = lsTab;
      } catch {}
      if (migratedId != null) {
        navigate(`/projects/${migratedId}/${migratedTab}`, { replace: true });
      }
      try { localStorage.removeItem(LS_TAB); localStorage.removeItem(LS_PROJECT); } catch {}
    } else if (!list.find((p) => p.id === urlProjectId)) {
      // URL points to a project the user can't see (deleted / not theirs /
      // not public). Roll forward to first available or back to "/".
      const fallback = list[0]?.id ?? null;
      if (fallback != null) navigate(`/projects/${fallback}/chat`, { replace: true });
      else navigate('/', { replace: true });
    }
  };

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, []);

  const active = projects.find((p) => p.id === activeId);

  const tabsWithBadges = TABS.map((t) => {
    let badge = null;
    let badgeTone = 'phosphor';
    if (t.id === 'mcp') {
      const needsAuth = (sessionInfo.mcpServers || []).some((s) => s.status === 'needs-auth' || s.status === 'failed');
      if (needsAuth) { badge = 'auth'; badgeTone = 'amber'; }
    }
    return { ...t, badge, badgeTone };
  });

  return (
    <AuthGate>
    <div className="app-root">
      <WindowFrame
        title={active ? `${active.name} / ${tab}` : 'wega'}
        theme={theme.endsWith('-light') ? 'light' : 'dark'}
        headerExtras={<AuthHeader />}
      >
        <Sidebar
          projects={projects}
          activeId={activeId}
          onSelect={setActiveId}
          onChanged={refresh}
          theme={theme}
          onChangeTheme={setTheme}
        />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {!active && globalRoute === 'context' && (
            <ContextFabricPanel mode="global" />
          )}
          {!active && globalRoute !== 'context' && (
            <HomePage projects={projects} onPickProject={setActiveId} />
          )}
          {active && (
            <>
              <TabBar
                tabs={tabsWithBadges}
                active={tab}
                onSelect={setTab}
                model={active.model}
                permissionMode={active.permission_mode}
              />
              <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>
                {tab === 'chat' && (
                  <Chat
                    project={active}
                    onProjectUpdated={refresh}
                    pendingSend={pendingSend}
                    onPendingSent={() => setPendingSend(null)}
                    onSessionInfo={setSessionInfo}
                  />
                )}
                {tab === 'dashboard' && <DashboardPanel project={active} />}
                {tab === 'files' && <FilesPanel project={active} onSendToSkill={sendToChat} />}
                {tab === 'repos' && <ReposPanel project={active} />}
                {tab === 'context' && <ContextFabricPanel mode="project" project={active} />}
                {tab === 'skills' && <SkillsPanel project={active} />}
                {tab === 'mcp' && <McpPanel project={active} sessionInfo={sessionInfo} />}
                {tab === 'settings' && <SettingsPanel project={active} onChanged={refresh} />}
              </div>
              <StatusBar
                left={[
                  <><span style={{ color: 'var(--w-phosphor)' }}>●</span> agent ready</>,
                  <>session <span style={{ color: 'var(--w-text-1)' }}>{(active.last_session_id || '—').slice(0, 7)}</span></>,
                  <>tools <span style={{ color: 'var(--w-text-1)' }}>{sessionInfo.tools.length}</span></>,
                  <>mcp <span style={{ color: 'var(--w-text-1)' }}>{(sessionInfo.mcpServers || []).length}</span></>,
                ]}
                right={[
                  <>{theme} · CRT</>,
                  <>v0.4.2-α</>,
                ]}
              />
            </>
          )}
        </div>
      </WindowFrame>
    </div>
    </AuthGate>
  );
}
