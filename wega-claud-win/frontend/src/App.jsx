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
import { ContextEnginePanel } from './components/ContextEnginePanel.jsx';
import { AuthGate, AuthHeader } from './components/AuthGate.jsx';
import { WindowFrame, TabBar, StatusBar } from './components/ui.jsx';
import { api, authToken } from './lib/api.js';

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
const LS_TAB     = 'quantnik.app.tab';
const LS_PROJECT = 'quantnik.app.activeProjectId';

// URL → state mapping. The Context Engine is a quantnik-level surface as well
// as a per-project tab, so we recognise both:
//   /context                   → global (org) Context Engine
//   /skills, /mcp, /settings   → global workbench surfaces
//   /projects/:id              → project, tab defaults to chat
//   /projects/:id/:tab         → project + specific tab
//   anything else (incl. "/")  → home page
function parsePath(pathname) {
  const global = pathname.match(/^\/([a-z-]+)\/?$/);
  if (global && TABS.some((t) => t.id === global[1])) {
    return { projectId: null, tab: null, globalRoute: global[1] };
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
  const [user, setUser] = useState(null); // populated once after /auth/me; null for unauthed
  const [projectScope, setProjectScope] = useState(() => {
    // Admin opt-in: see every project across the workbench. Default 'own'.
    // Persisted so the toggle survives reloads. The backend silently
    // downgrades scope=all from a non-admin, so saving it for a future-admin
    // user is safe — it'll just be ignored until they actually have the flag.
    try { return localStorage.getItem('quantnik.admin.projectScope') === 'all' ? 'all' : 'own'; }
    catch { return 'own'; }
  });
  const [theme, setTheme] = useState(() => {
    const stored = localStorage.getItem('quantnik-theme');
    // migrate legacy/dark values to the current Quantnik light surface.
    if (stored === 'dark' || stored === 'cyber-dark' || stored === 'sunset-dark') return 'sunset-light';
    if (stored === 'light' || stored === 'cyber-light') return 'sunset-light';
    return stored || 'sunset-light';
  });
  const [sessionInfo, setSessionInfo] = useState({ tools: [], mcpServers: [], usage: null });

  useEffect(() => {
    const polarity = theme.endsWith('-light') ? 'light' : 'dark';
    document.body.className = `theme-${theme} ${polarity}`;
    localStorage.setItem('quantnik-theme', theme);
  }, [theme]);

  // Navigation actions — both fire pushState through react-router so back /
  // forward + URL-bar typing work naturally. Tab change preserves the
  // current project; project change preserves the current tab.
  const setActiveId = (id) => {
    if (id == null) navigate('/');
    else navigate(`/projects/${id}/${tab}`);
  };
  const setTab = (newTab) => {
    if (activeId == null) navigate(`/${newTab}`);
    else navigate(`/projects/${activeId}/${newTab}`);
  };

  const sendToChat = (message) => {
    setPendingSend({ message, at: Date.now() });
    setTab('chat');
  };

  const refresh = async () => {
    if (!authToken.get()) {
      setProjects([]);
      return;
    }
    let list;
    try {
      list = await api.listProjects({ scope: projectScope });
    } catch (e) {
      // During logout/login transitions, an in-flight refresh can race a
      // token clear. Preserve the current list unless the user is truly
      // unauthenticated, so projects do not appear to vanish transiently.
      if (!authToken.get()) setProjects([]);
      return;
    }
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

  useEffect(() => {
    const handler = () => refresh();
    window.addEventListener('quantnik:auth-changed', handler);
    window.addEventListener('quantnik:auth-expired', handler);
    window.addEventListener('quantnik:auth-logout', handler);
    return () => {
      window.removeEventListener('quantnik:auth-changed', handler);
      window.removeEventListener('quantnik:auth-expired', handler);
      window.removeEventListener('quantnik:auth-logout', handler);
    };
    /* eslint-disable-next-line */
  }, [projectScope, urlProjectId]);

  // Fetch the logged-in user once so the sidebar can show admin-only UI
  // (the scope toggle). Non-admins never see it; the API endpoint is the
  // ultimate gate, so showing the toggle is purely cosmetic.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authToken.get()) {
        if (!cancelled) setUser(null);
        return;
      }
      const me = await api.me();
      if (!cancelled && me?.user) setUser(me.user);
    })();
    const handler = async () => {
      if (!authToken.get()) { setUser(null); return; }
      const me = await api.me();
      if (me?.user) setUser(me.user);
    };
    window.addEventListener('quantnik:auth-changed', handler);
    window.addEventListener('quantnik:auth-expired', handler);
    window.addEventListener('quantnik:auth-logout', handler);
    return () => {
      cancelled = true;
      window.removeEventListener('quantnik:auth-changed', handler);
      window.removeEventListener('quantnik:auth-expired', handler);
      window.removeEventListener('quantnik:auth-logout', handler);
    };
  }, []);

  // Re-fetch projects whenever the admin scope toggle flips. Persist the
  // choice so it survives reloads.
  const setProjectScopePersisted = (next) => {
    setProjectScope(next);
    try { localStorage.setItem('quantnik.admin.projectScope', next); } catch {}
  };
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [projectScope]);

  const active = projects.find((p) => p.id === activeId);
  const activeTab = active ? tab : globalRoute;

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
        title={active ? `${active.name} / ${tab}` : 'Quantnik'}
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
          user={user}
          projectScope={projectScope}
          onChangeProjectScope={setProjectScopePersisted}
        />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <TabBar
            tabs={tabsWithBadges}
            active={activeTab}
            onSelect={setTab}
            model={active?.model}
            permissionMode={active?.permission_mode}
          />
          {!active && !globalRoute && (
            <HomePage projects={projects} onPickProject={setActiveId} />
          )}
          {!active && globalRoute === 'context' && <ContextEnginePanel mode="global" />}
          {!active && globalRoute === 'skills' && <SkillsPanel project={null} />}
          {!active && globalRoute === 'mcp' && <McpPanel project={null} sessionInfo={sessionInfo} />}
          {!active && globalRoute === 'settings' && <SettingsPanel project={null} onChanged={refresh} />}
          {!active && globalRoute && !['context', 'skills', 'mcp', 'settings'].includes(globalRoute) && (
            <ProjectRequired tab={globalRoute} onCreate={() => document.querySelector('aside button')?.click()} />
          )}
          {active && (
            <>
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
                {tab === 'context' && <ContextEnginePanel mode="project" project={active} />}
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
                  <>Quantnik light</>,
                  <>v0.4.2-α</>,
                ]}
              />
            </>
          )}
          {!active && (
            <StatusBar
              left={[
                <><span style={{ color: 'var(--w-phosphor)' }}>●</span> workbench ready</>,
                <>project <span style={{ color: 'var(--w-text-1)' }}>none selected</span></>,
              ]}
              right={[
                <>Quantnik light</>,
                <>v0.4.2-α</>,
              ]}
            />
          )}
        </div>
      </WindowFrame>
    </div>
    </AuthGate>
  );
}

function ProjectRequired({ tab, onCreate }) {
  return (
    <div style={{ flex: 1, display: 'grid', placeItems: 'center', background: 'var(--w-bg-0)', padding: 28 }}>
      <div style={{
        width: 'min(560px, 100%)',
        border: '1px dashed var(--w-line)',
        background: 'var(--w-bg-1)',
        borderRadius: 3,
        padding: '22px 24px',
      }}>
        <div style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8 }}>
          // {tab}
        </div>
        <div style={{ color: 'var(--w-text-0)', font: '20px/1.25 var(--w-display)', marginBottom: 8 }}>
          Project required
        </div>
        <div style={{ color: 'var(--w-text-2)', font: '12px/1.55 var(--w-mono)', marginBottom: 16 }}>
          This tab reads project files, sessions, repos, uploads, or chat history. Global tabs like Skills, MCP, Context, and Settings are available without a project.
        </div>
        <button
          type="button"
          onClick={onCreate}
          style={{
            padding: '8px 12px',
            background: 'var(--w-phosphor)',
            color: '#03110a',
            border: '1px solid var(--w-phosphor)',
            borderRadius: 3,
            font: '500 12px/1 var(--w-mono)',
            cursor: 'pointer',
          }}
        >
          [ + ] new project
        </button>
      </div>
    </div>
  );
}
