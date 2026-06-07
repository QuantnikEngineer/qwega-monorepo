import React, { useEffect, useState, useMemo } from 'react';
import { api } from '../lib/api.js';
import { ScreenFrame, Pill, Btn, S, SectionLabel } from './ui.jsx';
import {
  aggregateUsage,
  extractAtlassian,
  extractLatestRuns,
  aggregateActivity,
} from '../lib/dashboard.js';

function fmt(n) {
  if (n == null) return '—';
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return n.toLocaleString();
  return String(n);
}

function fmtCost(c) {
  if (c == null) return '—';
  if (c >= 100) return `$${c.toFixed(0)}`;
  if (c >= 1) return `$${c.toFixed(2)}`;
  return `$${c.toFixed(4)}`;
}

function timeAgo(sec) {
  if (!sec) return '—';
  const s = Math.floor(Date.now() / 1000 - sec);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function Metric({ label, value, hint, accent = 'phosphor' }) {
  return (
    <div style={{
      border: '1px solid var(--w-line)',
      borderLeft: `2px solid var(--w-${accent})`,
      background: 'var(--w-bg-2)',
      borderRadius: 3,
      padding: '14px 16px',
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      minHeight: 92,
    }}>
      <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
        {label}
      </div>
      <div style={{ color: `var(--w-${accent})`, font: '600 24px/1 var(--w-display)' }}>
        {value}
      </div>
      {hint && (
        <div style={{ color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)' }}>
          {hint}
        </div>
      )}
    </div>
  );
}

function SeverityBar({ critical = 0, high = 0, medium = 0, low = 0, info = 0 }) {
  const total = critical + high + medium + low + info;
  if (total === 0) return <div style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)' }}>no findings</div>;
  const seg = (n, color) => (
    n > 0 && <div style={{
      flex: n,
      background: color,
      borderRight: '1px solid var(--w-bg-0)',
    }} />
  );
  return (
    <>
      <div style={{ display: 'flex', height: 8, background: 'var(--w-bg-1)', border: '1px solid var(--w-line)', borderRadius: 2, overflow: 'hidden' }}>
        {seg(critical, 'var(--w-red)')}
        {seg(high, 'var(--w-amber)')}
        {seg(medium, 'var(--w-cyan)')}
        {seg(low, 'var(--w-phosphor)')}
        {seg(info, 'var(--w-text-3)')}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', font: '10px/1.4 var(--w-mono)', marginTop: 6 }}>
        <span style={{ color: 'var(--w-red)' }}>Crit {critical}</span>
        <span style={{ color: 'var(--w-amber)' }}>High {high}</span>
        <span style={{ color: 'var(--w-cyan)' }}>Med {medium}</span>
        <span style={{ color: 'var(--w-phosphor)' }}>Low {low}</span>
        <span style={{ color: 'var(--w-text-3)' }}>Info {info}</span>
      </div>
    </>
  );
}

function ArtifactList({ items, renderItem, emptyText = 'none yet', max = 6 }) {
  if (!items || items.length === 0) {
    return <div style={{ color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)', padding: '6px 0' }}>{emptyText}</div>;
  }
  const shown = items.slice(0, max);
  const remaining = items.length - shown.length;
  return (
    <>
      {shown.map(renderItem)}
      {remaining > 0 && (
        <div style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)', padding: '6px 2px' }}>
          +{remaining} more
        </div>
      )}
    </>
  );
}

function Card({ children, accent = 'phosphor', title, count, action }) {
  return (
    <div style={{
      border: '1px solid var(--w-line)',
      borderLeft: `2px solid var(--w-${accent})`,
      background: 'var(--w-bg-2)',
      borderRadius: 3,
      padding: '14px 16px',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
      minHeight: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flex: '0 0 auto' }}>
        <span style={{ color: `var(--w-${accent})`, font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
          // {title}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {count != null && <Pill tone={accent}>{count}</Pill>}
          {action}
        </div>
      </div>
      <div style={{ flex: '1 1 auto', overflowY: 'auto', minHeight: 0 }}>{children}</div>
    </div>
  );
}

function AtlassianLink({ icon, accent, primary, secondary, url }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      title={url}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 4px',
        borderBottom: '1px dashed var(--w-line)',
        textDecoration: 'none',
        color: 'var(--w-text-1)',
      }}
    >
      <span style={{
        color: `var(--w-${accent})`,
        font: '600 10.5px/1 var(--w-mono)',
        flex: '0 0 auto',
        minWidth: icon.length > 2 ? 56 : 'auto',
      }}>
        {icon}
      </span>
      <span style={{
        font: '11px/1.3 var(--w-mono)',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
      }}>
        {primary}
      </span>
      {secondary && (
        <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', flex: '0 0 auto' }}>
          {secondary}
        </span>
      )}
      <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', flex: '0 0 auto' }}>↗</span>
    </a>
  );
}

// Status visuals — mirror the Chat-side floating panel for consistency. ◐ on
// the active row gets a subtle pulse so the user can spot the live phase
// without staring at the icons.
const STATUS_ICON = {
  pending: { icon: '○', color: 'var(--w-text-3)' },
  running: { icon: '◐', color: 'var(--w-cyan)',     pulse: true },
  done:    { icon: '✓', color: 'var(--w-phosphor)' },
  skipped: { icon: '↷', color: 'var(--w-text-2)' },
  failed:  { icon: '✕', color: 'var(--w-red)' },
};

function PhaseTracker({ phases, anyTracked }) {
  const total = phases.length || 11;
  const doneCount    = phases.filter((p) => p.status === 'done' || p.status === 'skipped').length;
  const runningCount = phases.filter((p) => p.status === 'running').length;
  const failedCount  = phases.filter((p) => p.status === 'failed').length;
  const percent      = total ? Math.round(((doneCount + runningCount * 0.5) / total) * 100) : 0;
  const complete     = anyTracked && phases.every((p) => p.status === 'done' || p.status === 'skipped');
  const headerColor  = failedCount > 0
    ? 'var(--w-red)'
    : complete
      ? 'var(--w-phosphor)'
      : anyTracked
        ? 'var(--w-cyan)'
        : 'var(--w-text-3)';
  const subtitle = !anyTracked
    ? 'no run yet — invoke /sdlc-orchestrator in chat'
    : complete
      ? 'pipeline complete'
      : runningCount > 0
        ? `running · ${doneCount} of ${total} done`
        : failedCount > 0
          ? `${failedCount} failed · ${doneCount} done`
          : `${doneCount} of ${total} done`;

  return (
    <div style={{
      border: '1px solid var(--w-line)',
      borderLeft: `2px solid ${headerColor}`,
      background: 'var(--w-bg-2)',
      borderRadius: 3,
      padding: '14px 16px',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span style={{ color: headerColor, font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
            // orchestrator pipeline
          </span>
          <span style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)' }}>{subtitle}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.08em' }}>{percent}%</span>
          <Pill tone={failedCount > 0 ? 'red' : complete ? 'phosphor' : anyTracked ? 'cyan' : 'phosphor'}>
            {doneCount}/{total}
          </Pill>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ height: 4, background: 'var(--w-bg-1)', border: '1px solid var(--w-line)', borderRadius: 2, overflow: 'hidden', display: 'flex' }}>
        {doneCount > 0 && <div style={{ flex: doneCount,    background: 'var(--w-phosphor)' }} />}
        {runningCount > 0 && <div style={{ flex: runningCount, background: 'var(--w-cyan)' }} />}
        {failedCount > 0 && <div style={{ flex: failedCount,  background: 'var(--w-red)' }} />}
        {(total - doneCount - runningCount - failedCount) > 0 && (
          <div style={{ flex: total - doneCount - runningCount - failedCount, background: 'transparent' }} />
        )}
      </div>

      {/* 11-row grid — compact, vertical, scannable */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', columnGap: 16, rowGap: 4 }}>
        {phases.map((p) => {
          const s = STATUS_ICON[p.status] || STATUS_ICON.pending;
          return (
            <div key={p.number} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '4px 6px',
              borderBottom: '1px dashed var(--w-line)',
              opacity: p.status === 'pending' ? 0.6 : 1,
            }}>
              <span style={{
                color: s.color,
                font: '13px/1 var(--w-mono)',
                width: 14,
                animation: s.pulse ? 'w-pulse 1.2s ease-in-out infinite' : undefined,
              }}>{s.icon}</span>
              <span style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)', width: 18, textAlign: 'right' }}>
                {String(p.number).padStart(2, '0')}
              </span>
              <span style={{ color: 'var(--w-text-1)', font: '11.5px/1.3 var(--w-mono)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {p.name}
              </span>
              <span style={{
                color: s.color,
                font: '9.5px/1 var(--w-mono)',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                flex: '0 0 auto',
              }}>
                {p.status}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function DashboardPanel({ project }) {
  const [messages, setMessages] = useState([]);
  const [skills, setSkills] = useState([]);
  const [mcp, setMcp] = useState({ local: {}, runtime: [] });
  const [uploads, setUploads] = useState([]);
  const [repos, setRepos] = useState([]);
  const [atlassianLive, setAtlassianLive] = useState(null);
  const [atlassianConfig, setAtlassianConfig] = useState(null);
  const [codeStats, setCodeStats] = useState(null);
  const [showConfig, setShowConfig] = useState(false);
  const [configForm, setConfigForm] = useState({ jiraProjectKey: '', confluenceSpaceId: '', confluenceSpaceKey: '', labels: '' });
  const [savingConfig, setSavingConfig] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  // Phase tracker — polled separately from the heavy Promise.all so live
  // status updates don't have to wait for the slow MCP/atlassian pulls.
  const [phaseState, setPhaseState] = useState({ phases: [], anyTracked: false });
  useEffect(() => {
    let cancelled = false;
    const fetchPhases = () => {
      api.listPhases(project.id).then((d) => {
        if (cancelled || !d) return;
        setPhaseState({ phases: d.phases || [], anyTracked: !!d.anyTracked });
      }).catch(() => {});
    };
    fetchPhases();
    const t = setInterval(fetchPhases, 5000);
    return () => { cancelled = true; clearInterval(t); };
  }, [project.id, refreshKey]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      api.getMessages(project.id).catch(() => []),
      api.listSkills(project.id).catch(() => []),
      api.listMcp(project.id).catch(() => ({ local: {}, runtime: [] })),
      api.listUploads(project.id).catch(() => []),
      api.listRepos(project.id).catch(() => []),
      api.getAtlassianConfig(project.id).catch(() => null),
      api.getAtlassianArtifacts(project.id).catch((e) => ({ configured: false, reason: 'fetch-failed', message: e.message })),
      api.getCodeStats(project.id).catch(() => null),
      api.inheritedSkills().catch(() => ({ user: [], plugins: [] })),
    ]).then(([m, s, mc, u, r, cfg, atl, cs, inh]) => {
      if (cancelled) return;
      setMessages(m);
      // Merge project-local + user-level inherited skills (dedup by name) so the
      // Skills card and overview reflect what's actually available to the agent.
      const seen = new Set();
      const merged = [
        ...s.map((x) => ({ ...x, scope: 'project' })),
        ...(inh.user || []).map((x) => ({ ...x, scope: 'user' })),
        ...(inh.plugins || []).map((x) => ({ ...x, scope: `plugin:${x.plugin}` })),
      ].filter((x) => (seen.has(x.name) ? false : seen.add(x.name)));
      setSkills(merged);
      setMcp(mc);
      setUploads(u);
      setRepos(r);
      setAtlassianConfig(cfg);
      setAtlassianLive(atl);
      setCodeStats(cs);
      if (cfg) {
        setConfigForm({
          jiraProjectKey: cfg.jiraProjectKey || '',
          confluenceSpaceId: cfg.confluenceSpaceId || '',
          confluenceSpaceKey: cfg.confluenceSpaceKey || '',
          labels: (cfg.labels || []).join(', '),
        });
      }
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [project.id, refreshKey]);

  const saveConfig = async () => {
    setSavingConfig(true);
    try {
      await api.saveAtlassianConfig(project.id, {
        jiraProjectKey: configForm.jiraProjectKey,
        confluenceSpaceId: configForm.confluenceSpaceId,
        confluenceSpaceKey: configForm.confluenceSpaceKey,
        labels: configForm.labels.split(',').map((s) => s.trim()).filter(Boolean),
      });
      setShowConfig(false);
      setRefreshKey((k) => k + 1);
    } catch (e) { alert(`save failed: ${e.message}`); }
    setSavingConfig(false);
  };

  const usage = useMemo(() => aggregateUsage(messages), [messages]);
  const activity = useMemo(() => aggregateActivity(messages), [messages]);
  const chatRefs = useMemo(() => extractAtlassian(messages), [messages]);
  const runs = useMemo(() => extractLatestRuns(messages), [messages]);

  // Merge live Atlassian pull with chat-history refs. Live data is the source
  // of truth for things that exist in the configured Jira/Confluence project;
  // chat-history fills in cross-project references mentioned in this chat.
  const atlassian = useMemo(() => {
    const liveJira = (atlassianLive?.jira?.issues || []).map((iss) => ({
      key: iss.key, summary: iss.summary, url: iss.url, type: iss.type,
      status: iss.status, priority: iss.priority,
    }));
    const liveConfluence = (atlassianLive?.confluence?.pages || []).map((p) => ({
      title: p.title, url: p.url, isBrd: p.isBrd,
    }));

    // De-dupe: live wins; chat-history only contributes keys/urls not already present.
    const jiraByKey = new Map(liveJira.map((j) => [j.key, j]));
    for (const j of chatRefs.jiraAll) {
      if (!jiraByKey.has(j.key)) jiraByKey.set(j.key, j);
    }
    const confluenceByUrl = new Map(liveConfluence.map((p) => [p.url, p]));
    for (const p of chatRefs.confluenceAll) {
      if (!confluenceByUrl.has(p.url)) confluenceByUrl.set(p.url, p);
    }
    const jiraAll = [...jiraByKey.values()];
    const confluenceAll = [...confluenceByUrl.values()];
    const epicSet = new Set(jiraAll.filter((j) => j.type === 'Epic').map((e) => e.key));
    // Count a "story" as: any Story issuetype, OR a Task whose parent is one
    // of the captured Epics — that's the orchestrator's fallback when the
    // target Jira project doesn't expose a Story issuetype.
    const isStoryLike = (j) => j.type === 'Story' || (j.type === 'Task' && j.parent && epicSet.has(j.parent));
    return {
      jiraAll,
      epics: jiraAll.filter((j) => j.type === 'Epic'),
      stories: jiraAll.filter(isStoryLike),
      testCases: jiraAll.filter((j) => j.type === 'Test' || j.type === 'Sub-task' || j.type === 'Subtask'),
      tasks: jiraAll.filter((j) => j.type === 'Task' && !isStoryLike(j)),
      confluenceAll,
      brds: confluenceAll.filter((p) => p.isBrd),
      confluenceOther: confluenceAll.filter((p) => !p.isBrd),
      liveCounts: {
        jira: atlassianLive?.jira?.total ?? atlassianLive?.jira?.issues?.length ?? 0,
        confluence: atlassianLive?.confluence?.pages?.length ?? 0,
      },
      liveConfigured: !!atlassianLive?.configured,
      liveErrors: atlassianLive?.errors || {},
      liveReason: atlassianLive?.reason,
    };
  }, [atlassianLive, chatRefs]);

  const totalTokens = usage.input + usage.cacheRead + usage.cacheCreate + usage.output;

  return (
    <ScreenFrame
      breadcrumb={<><S c="var(--w-phosphor)">~/{project.name}</S> ─ dashboard</>}
      title="Project dashboard"
      subtitle={
        <>Observability surface — tokens, cost, Atlassian artifacts (BRDs, Epics, Stories, Test cases), security & tech-debt scans, plus repos, skills, MCP servers, uploads. All derived from this project's message history; nothing is stored separately.</>
      }
      action={
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn tone="ghost" onClick={() => setShowConfig((v) => !v)}>[ ⚙ ] atlassian scope</Btn>
          <Btn tone="ghost" onClick={() => setRefreshKey((k) => k + 1)}>[ ↻ ] refresh</Btn>
        </div>
      }
    >
      {loading ? (
        <div style={{ color: 'var(--w-text-3)', font: '12px/1.6 var(--w-mono)' }}>loading…</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {showConfig && (
            <div style={{
              border: '1px solid var(--w-line-strong)',
              background: 'var(--w-bg-2)',
              borderRadius: 3,
              padding: '14px 18px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <span style={{ color: 'var(--w-phosphor)', font: '11px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
                  // atlassian scope for {project.name}
                </span>
                <span style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)' }}>
                  {atlassianConfig?.credsConfigured ? 'creds ✓' : 'creds missing — set MCP_ATLASSIAN_* in backend .env'}
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 10 }}>
                <div>
                  <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>jira project key</label>
                  <input
                    value={configForm.jiraProjectKey}
                    onChange={(e) => setConfigForm({ ...configForm, jiraProjectKey: e.target.value })}
                    placeholder="BL"
                    style={{ width: '100%' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>confluence space id</label>
                  <input
                    value={configForm.confluenceSpaceId}
                    onChange={(e) => setConfigForm({ ...configForm, confluenceSpaceId: e.target.value })}
                    placeholder="40435714"
                    style={{ width: '100%' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>or space key</label>
                  <input
                    value={configForm.confluenceSpaceKey}
                    onChange={(e) => setConfigForm({ ...configForm, confluenceSpaceKey: e.target.value })}
                    placeholder="BuildIQ"
                    style={{ width: '100%' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>labels filter (optional, csv)</label>
                  <input
                    value={configForm.labels}
                    onChange={(e) => setConfigForm({ ...configForm, labels: e.target.value })}
                    placeholder="chirp-v1, mpi"
                    style={{ width: '100%' }}
                  />
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
                <Btn tone="ghost" onClick={() => setShowConfig(false)}>cancel</Btn>
                <Btn tone="primary" onClick={saveConfig} disabled={savingConfig}>{savingConfig ? 'saving…' : '[ ⤓ ] save & refresh'}</Btn>
              </div>
              {atlassian.liveErrors.jira && (
                <div style={{ marginTop: 8, color: 'var(--w-red)', font: '10.5px/1.4 var(--w-mono)' }}>
                  jira pull failed: {atlassian.liveErrors.jira}
                </div>
              )}
              {atlassian.liveErrors.confluence && (
                <div style={{ marginTop: 4, color: 'var(--w-red)', font: '10.5px/1.4 var(--w-mono)' }}>
                  confluence pull failed: {atlassian.liveErrors.confluence}
                </div>
              )}
            </div>
          )}

          {!atlassian.liveConfigured && atlassianLive?.reason === 'no-scope' && (
            <div style={{
              border: '1px dashed var(--w-line)',
              borderLeft: '2px solid var(--w-amber)',
              background: 'var(--w-bg-2)',
              borderRadius: 3,
              padding: '10px 14px',
              font: '11px/1.5 var(--w-mono)',
              color: 'var(--w-text-1)',
            }}>
              Atlassian scope not set for this project. Click <S c="var(--w-phosphor)">[ ⚙ ] atlassian scope</S> above to point this dashboard at a Jira project key and Confluence space. Without a scope, only chat-history-derived artifacts appear.
            </div>
          )}
          {/* Row 1 — top metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
            <Metric
              label="total tokens"
              value={fmt(totalTokens)}
              hint={`in ${fmt(usage.input)} · cache ${fmt(usage.cacheRead)} · out ${fmt(usage.output)}`}
            />
            <Metric
              label="total cost"
              value={fmtCost(usage.cost)}
              hint={`${usage.turns} turn${usage.turns === 1 ? '' : 's'} · last ${timeAgo(usage.lastTurnAt)}`}
              accent="amber"
            />
            <Metric
              label="tool calls"
              value={fmt(activity.toolCalls)}
              hint={`${activity.toolErrors} error${activity.toolErrors === 1 ? '' : 's'} · ${activity.assistantTexts} replies`}
              accent="cyan"
            />
            <Metric
              label="messages"
              value={fmt(messages.length)}
              hint={`${activity.userMessages} from you`}
              accent="violet"
            />
            <Metric
              label="session"
              value={(project.last_session_id || '—').slice(0, 7)}
              hint={`model ${(project.model || 'opus-4-7').replace(/^claude-/, '')} · ${project.permission_mode}`}
              accent="phosphor"
            />
          </div>

          {/* Row 1.5 — Orchestrator phase tracker. Renders all 11 phases
              even before a run starts (all-pending) so the pipeline shape
              is visible. Polled every 5 s independently of the heavy
              dashboard refresh. */}
          <PhaseTracker phases={phaseState.phases} anyTracked={phaseState.anyTracked} />

          {/* Row 2 — BRDs, Epics, Overview (counts) */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, height: 260 }}>
            <Card title="BRDs · confluence" accent="cyan" count={atlassian.brds.length}>
              <ArtifactList
                items={atlassian.brds}
                emptyText="no BRDs yet"
                renderItem={(p) => (
                  <AtlassianLink key={p.url} icon="▤" accent="cyan" primary={p.title} url={p.url} />
                )}
              />
              {atlassian.confluenceOther.length > 0 && (
                <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px dashed var(--w-line)' }}>
                  <div style={{ color: 'var(--w-text-3)', font: '9.5px/1 var(--w-mono)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 4 }}>
                    other pages ({atlassian.confluenceOther.length})
                  </div>
                  <ArtifactList
                    items={atlassian.confluenceOther}
                    max={3}
                    renderItem={(p) => (
                      <AtlassianLink key={p.url} icon="▤" accent="cyan" primary={p.title} url={p.url} />
                    )}
                  />
                </div>
              )}
            </Card>

            <Card title="Epics · jira" accent="amber" count={atlassian.epics.length}>
              <ArtifactList
                items={atlassian.epics}
                emptyText="no epics yet"
                renderItem={(j) => (
                  <AtlassianLink
                    key={j.key}
                    icon={j.key}
                    accent="amber"
                    primary={j.summary || j.key}
                    url={j.url}
                  />
                )}
              />
            </Card>

            <Card title="Overview · counts" accent="phosphor">
              {(() => {
                const stats = [
                  { label: 'User stories', value: atlassian.stories.length, accent: 'violet' },
                  { label: 'Epics',         value: atlassian.epics.length,   accent: 'amber' },
                  { label: 'Test cases',    value: atlassian.testCases.length, accent: 'magenta' },
                  { label: 'Test scripts',  value: codeStats?.specFiles ?? '—', accent: 'cyan' },
                  { label: 'Lines of code', value: codeStats?.totalLines != null ? fmt(codeStats.totalLines) : '—', accent: 'phosphor' },
                ];
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {stats.map((s) => (
                      <div key={s.label} style={{
                        display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
                        padding: '6px 8px',
                        borderLeft: `2px solid var(--w-${s.accent})`,
                        background: 'var(--w-bg-1)',
                        borderRadius: 2,
                      }}>
                        <span style={{ color: 'var(--w-text-2)', font: '10.5px/1 var(--w-mono)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                          {s.label}
                        </span>
                        <span style={{ color: `var(--w-${s.accent})`, font: '600 18px/1 var(--w-display)' }}>
                          {s.value}
                        </span>
                      </div>
                    ))}
                    {codeStats?.totalFiles != null && (
                      <div style={{ marginTop: 4, color: 'var(--w-text-3)', font: '9.5px/1.4 var(--w-mono)', letterSpacing: '0.04em' }}>
                        across {codeStats.totalFiles} source file{codeStats.totalFiles === 1 ? '' : 's'}
                        {codeStats.targets?.length ? ` · ${codeStats.targets.length} ${codeStats.targets.length === 1 ? 'tree' : 'trees'}` : ''}
                      </div>
                    )}
                  </div>
                );
              })()}
            </Card>
          </div>

          {/* Row 3 — Code quality scans */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <Card
              title="Vulnerabilities · /vulnerability-check"
              accent="red"
              count={runs.vulnerability ? runs.vulnerability.total : '—'}
              action={runs.vulnerability?.url && (
                <a
                  href={runs.vulnerability.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: 'var(--w-cyan)', font: '10.5px/1 var(--w-mono)', textDecoration: 'none' }}
                >report ↗</a>
              )}
            >
              {!runs.vulnerability ? (
                <div style={{ color: 'var(--w-text-3)', font: '11px/1.5 var(--w-mono)' }}>
                  no scans yet. run <S c="var(--w-phosphor)">/vulnerability-check</S> in chat to populate.
                </div>
              ) : (
                <>
                  <SeverityBar {...runs.vulnerability} />
                  <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, font: '11px/1.4 var(--w-mono)' }}>
                    {runs.vulnerability.fixed != null && (
                      <div><span style={{ color: 'var(--w-text-3)' }}>fixed</span> <span style={{ color: 'var(--w-phosphor)' }}>{runs.vulnerability.fixed}</span></div>
                    )}
                    {runs.vulnerability.refactor != null && (
                      <div><span style={{ color: 'var(--w-text-3)' }}>pending</span> <span style={{ color: 'var(--w-amber)' }}>{runs.vulnerability.refactor}</span></div>
                    )}
                    {runs.vulnerability.remaining != null && (
                      <div><span style={{ color: 'var(--w-text-3)' }}>open</span> <span style={{ color: 'var(--w-red)' }}>{runs.vulnerability.remaining}</span></div>
                    )}
                  </div>
                  {runs.vulnerability.at && (
                    <div style={{ marginTop: 8, color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)' }}>
                      last run {timeAgo(runs.vulnerability.at)}
                    </div>
                  )}
                </>
              )}
            </Card>

            <Card
              title="Tech debt · /tech-debt-check"
              accent="amber"
              count={runs.techDebt ? runs.techDebt.total : '—'}
              action={runs.techDebt?.url && (
                <a
                  href={runs.techDebt.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: 'var(--w-cyan)', font: '10.5px/1 var(--w-mono)', textDecoration: 'none' }}
                >report ↗</a>
              )}
            >
              {!runs.techDebt ? (
                <div style={{ color: 'var(--w-text-3)', font: '11px/1.5 var(--w-mono)' }}>
                  no scans yet. run <S c="var(--w-phosphor)">/tech-debt-check</S> in chat to populate.
                </div>
              ) : (
                <>
                  <SeverityBar {...runs.techDebt} />
                  <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, font: '11px/1.4 var(--w-mono)' }}>
                    {runs.techDebt.fixed != null && (
                      <div><span style={{ color: 'var(--w-text-3)' }}>fixed</span> <span style={{ color: 'var(--w-phosphor)' }}>{runs.techDebt.fixed}</span></div>
                    )}
                    {runs.techDebt.refactor != null && (
                      <div><span style={{ color: 'var(--w-text-3)' }}>refactor</span> <span style={{ color: 'var(--w-amber)' }}>{runs.techDebt.refactor}</span></div>
                    )}
                    {runs.techDebt.remaining != null && (
                      <div><span style={{ color: 'var(--w-text-3)' }}>still-debt</span> <span style={{ color: 'var(--w-red)' }}>{runs.techDebt.remaining}</span></div>
                    )}
                  </div>
                  {runs.techDebt.at && (
                    <div style={{ marginTop: 8, color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)' }}>
                      last run {timeAgo(runs.techDebt.at)}
                    </div>
                  )}
                </>
              )}
            </Card>
          </div>

          {/* Row 4 — Surrounding project state */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, minHeight: 220 }}>
            <Card title={`Repos · ${repos.length}`} accent="phosphor">
              <ArtifactList
                items={repos}
                emptyText="no repos configured"
                renderItem={(r) => (
                  <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 4px', borderBottom: '1px dashed var(--w-line)' }}>
                    <span style={{ color: r.exists ? 'var(--w-phosphor)' : 'var(--w-red)', font: '11px/1 var(--w-mono)', flex: '0 0 auto' }}>▸</span>
                    <span style={{ font: '11px/1.3 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={r.path}>
                      {r.name}
                    </span>
                    <Pill tone={r.exists ? (r.isGit ? 'phosphor' : 'amber') : 'red'} style={{ padding: '1px 5px', fontSize: 9.5 }}>
                      {r.exists ? (r.isGit ? 'git' : 'dir') : 'missing'}
                    </Pill>
                  </div>
                )}
              />
            </Card>

            <Card title={`MCP · ${(mcp.runtime || []).length}/${Object.keys(mcp.local || {}).length}`} accent="cyan">
              <ArtifactList
                items={Object.entries(mcp.local || {}).map(([name, cfg]) => {
                  const runtime = (mcp.runtime || []).find((s) => s.name === name);
                  return { name, transport: cfg.type || (cfg.command ? 'stdio' : 'http'), status: runtime?.status || 'pending' };
                })}
                emptyText="no servers configured"
                renderItem={(m) => (
                  <div key={m.name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 4px', borderBottom: '1px dashed var(--w-line)' }}>
                    <span className="w-dot" style={{
                      background: m.status === 'connected' ? 'var(--w-phosphor)' : m.status === 'needs-auth' ? 'var(--w-amber)' : m.status === 'failed' ? 'var(--w-red)' : 'var(--w-cyan)',
                      color: m.status === 'connected' ? 'var(--w-phosphor)' : m.status === 'needs-auth' ? 'var(--w-amber)' : m.status === 'failed' ? 'var(--w-red)' : 'var(--w-cyan)',
                      flex: '0 0 auto',
                    }} />
                    <span style={{ font: '11px/1.3 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                      {m.name}
                    </span>
                    <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', flex: '0 0 auto' }}>{m.transport}</span>
                  </div>
                )}
              />
            </Card>

            <Card title={`Skills · ${skills.length}`} accent="violet">
              <ArtifactList
                items={skills}
                emptyText="no project skills (user-level skills still apply)"
                renderItem={(s) => (
                  <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 4px', borderBottom: '1px dashed var(--w-line)' }}>
                    <span style={{ color: 'var(--w-violet)', font: '11px/1 var(--w-mono)', flex: '0 0 auto' }}>⚙</span>
                    <span style={{ font: '11px/1.3 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                      /{s.name}
                    </span>
                  </div>
                )}
              />
            </Card>

            <Card title={`Uploads · ${uploads.length}`} accent="amber">
              <ArtifactList
                items={uploads}
                emptyText="no files uploaded"
                renderItem={(f) => (
                  <div key={f.name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 4px', borderBottom: '1px dashed var(--w-line)' }}>
                    <span style={{ color: 'var(--w-amber)', font: '11px/1 var(--w-mono)', flex: '0 0 auto' }}>▤</span>
                    <span style={{ font: '11px/1.3 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={f.name}>
                      {f.name.replace(/^\d+-/, '')}
                    </span>
                    <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', flex: '0 0 auto' }}>
                      {f.size < 1024 ? `${f.size}B` : f.size < 1024 * 1024 ? `${(f.size / 1024).toFixed(0)}K` : `${(f.size / 1024 / 1024).toFixed(1)}M`}
                    </span>
                  </div>
                )}
              />
            </Card>
          </div>

          {/* Row 5 — Top tools (debug surface) */}
          {activity.topTools.length > 0 && (
            <div style={{ border: '1px solid var(--w-line)', background: 'var(--w-bg-2)', borderRadius: 3, padding: '14px 16px' }}>
              <SectionLabel tone="phosphor">// top tools · this project</SectionLabel>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 8 }}>
                {activity.topTools.map((t) => (
                  <div key={t.name} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span style={{ color: 'var(--w-text-3)', font: '9.5px/1 var(--w-mono)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                      {t.name.replace(/^mcp__[^_]+__/, '').slice(0, 22)}
                    </span>
                    <span style={{ color: 'var(--w-text-0)', font: '15px/1 var(--w-display)' }}>{t.count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </ScreenFrame>
  );
}
