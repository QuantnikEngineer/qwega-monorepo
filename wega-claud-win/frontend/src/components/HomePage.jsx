import React from 'react';
import { useNavigate } from 'react-router-dom';
import { S } from './ui.jsx';

const Card = ({ children, style, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    style={{
      textAlign: 'left',
      border: '1px solid var(--w-line)',
      background: '#fff',
      borderRadius: 16,
      padding: 18,
      color: 'var(--w-text-0)',
      boxShadow: '0 12px 34px rgba(31,41,55,0.06)',
      cursor: onClick ? 'pointer' : 'default',
      fontFamily: 'var(--w-display)',
      ...style,
    }}
  >
    {children}
  </button>
);

const SectionTitle = ({ eyebrow, title, right }) => (
  <div style={{ display: 'flex', alignItems: 'end', justifyContent: 'space-between', gap: 18, marginBottom: 14 }}>
    <div>
      <div style={{ color: 'var(--w-text-3)', font: '700 11px/1 var(--w-display)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 7 }}>
        {eyebrow}
      </div>
      <h2 style={{ margin: 0, color: 'var(--w-text-0)', font: '800 22px/1.2 var(--w-display)' }}>{title}</h2>
    </div>
    {right}
  </div>
);

const Step = ({ n, title, text }) => (
  <div style={{ display: 'flex', gap: 14 }}>
    <div style={{
      width: 30,
      height: 30,
      borderRadius: 10,
      background: n === 1 ? '#2563eb' : n === 2 ? '#0d9488' : '#7c5cff',
      color: '#fff',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      font: '800 13px/1 var(--w-display)',
      flex: '0 0 auto',
    }}>{n}</div>
    <div>
      <div style={{ font: '800 14px/1.25 var(--w-display)', color: 'var(--w-text-0)', marginBottom: 4 }}>{title}</div>
      <div style={{ font: '500 13px/1.55 var(--w-display)', color: 'var(--w-text-2)' }}>{text}</div>
    </div>
  </div>
);

const ToolCard = ({ accent, title, text }) => (
  <Card>
    <div style={{ width: 34, height: 34, borderRadius: 12, background: accent, marginBottom: 14 }} />
    <div style={{ font: '800 15px/1.2 var(--w-display)', marginBottom: 8 }}>{title}</div>
    <div style={{ font: '500 13px/1.55 var(--w-display)', color: 'var(--w-text-2)' }}>{text}</div>
  </Card>
);

export function HomePage({ projects, onPickProject }) {
  const navigate = useNavigate();
  const openProject = (id) => {
    if (onPickProject) onPickProject(id);
    else navigate(`/projects/${id}/chat`);
  };

  const projectCount = projects?.length || 0;

  return (
    <div style={{
      flex: 1,
      overflow: 'auto',
      background: '#f5f7fa',
      padding: '34px clamp(22px, 5vw, 58px)',
      fontFamily: 'var(--w-display)',
    }}>
      <div style={{ maxWidth: 1160, margin: '0 auto' }}>
        <section style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: 22,
          alignItems: 'stretch',
          marginBottom: 28,
        }}>
          <div style={{
            borderRadius: 22,
            padding: '34px 36px',
            background: 'linear-gradient(135deg, #eff6ff 0%, #ffffff 52%, #f0fdfa 100%)',
            border: '1px solid var(--w-line)',
            boxShadow: '0 18px 55px rgba(31,41,55,0.08)',
            minHeight: 260,
          }}>
            <div style={{ color: 'var(--w-phosphor)', font: '800 12px/1 var(--w-display)', letterSpacing: '0.11em', textTransform: 'uppercase', marginBottom: 14 }}>
              Quantnik · Workbench
            </div>
            <h1 style={{
              margin: '0 0 16px',
              maxWidth: 640,
              color: 'var(--w-text-0)',
              font: '800 42px/1.05 var(--w-display)',
            }}>
              Plan, build, test, and deploy from one focused workspace.
            </h1>
            <p style={{ margin: 0, maxWidth: 680, color: 'var(--w-text-2)', font: '500 16px/1.65 var(--w-display)' }}>
              Quantnik connects projects, repositories, uploaded requirements, Jira, Confluence, MCP servers, and skills into one agent workbench.
            </p>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 26 }}>
              <span style={pillStyle}>Project-scoped context</span>
              <span style={pillStyle}>Atlassian ready</span>
              <span style={pillStyle}>Skills-driven delivery</span>
            </div>
          </div>

          <Card onClick={() => navigate('/context')} style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ color: 'var(--w-text-3)', font: '800 11px/1 var(--w-display)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>
                Knowledge layer
              </div>
              <div style={{ font: '800 24px/1.15 var(--w-display)', marginBottom: 12 }}>Context Fabric</div>
              <div style={{ font: '500 13.5px/1.6 var(--w-display)', color: 'var(--w-text-2)' }}>
                Register shared runbooks, product notes, source material, and architecture decisions once.
              </div>
            </div>
            <div style={{ color: 'var(--w-phosphor)', font: '800 13px/1 var(--w-display)', marginTop: 26 }}>Open global context</div>
          </Card>
        </section>

        <section style={{ marginBottom: 28 }}>
          <SectionTitle eyebrow="Get moving" title="Recommended flow" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14 }}>
            <Card><Step n={1} title="Create or open a project" text="Each project gets its own files, repos, skills, chat history, settings, and Context Fabric scope." /></Card>
            <Card><Step n={2} title="Connect the working sources" text="Add repositories, upload requirements, and configure Jira or Confluence targets from the project tabs." /></Card>
            <Card><Step n={3} title="Run skills or chat" text="Use slash skills for repeatable workflows, or ask Quantnik directly in the chat surface." /></Card>
          </div>
        </section>

        <section style={{ marginBottom: 28 }}>
          <SectionTitle eyebrow="Surfaces" title="What this workspace manages" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
            <ToolCard accent="linear-gradient(135deg,#2563eb,#5b9bff)" title="Chat" text="Ask, attach files, invoke skills, and watch tool activity stream in place." />
            <ToolCard accent="linear-gradient(135deg,#0d9488,#34d399)" title="Repos" text="Register source repositories so generated changes land in real working trees." />
            <ToolCard accent="linear-gradient(135deg,#7c5cff,#a78bfa)" title="Skills" text="Keep repeatable delivery workflows as project-local or inherited SKILL.md files." />
            <ToolCard accent="linear-gradient(135deg,#f59e0b,#f97316)" title="MCP" text="Connect external systems such as Atlassian through configured MCP servers." />
          </div>
        </section>

        <section style={{ marginBottom: 28 }}>
          <SectionTitle
            eyebrow="Resume"
            title="Your projects"
            right={<span style={{ color: 'var(--w-text-3)', font: '700 12px/1 var(--w-display)' }}>{projectCount} available</span>}
          />
          {projectCount === 0 ? (
            <Card>
              <div style={{ font: '800 16px/1.3 var(--w-display)', marginBottom: 8 }}>No projects yet</div>
              <div style={{ color: 'var(--w-text-2)', font: '500 13px/1.6 var(--w-display)' }}>
                Use the New project action in the sidebar to create your first Quantnik workspace.
              </div>
            </Card>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12 }}>
              {projects.map((p) => (
                <Card key={p.id} onClick={() => openProject(p.id)}>
                  <div style={{ color: 'var(--w-phosphor)', font: '800 15px/1.25 var(--w-display)', marginBottom: 8 }}>{p.name}</div>
                  <div style={{ color: 'var(--w-text-3)', font: '500 12px/1.45 var(--w-display)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={p.path}>
                    {p.path}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </section>

        <footer style={{
          display: 'flex',
          justifyContent: 'space-between',
          gap: 16,
          padding: '18px 0 4px',
          color: 'var(--w-text-3)',
          font: '600 12px/1.6 var(--w-display)',
        }}>
          <span>Click the <S c="var(--w-phosphor)">Quantnik</S> lockup in the sidebar to return here.</span>
          <span>v0.4.2-alpha</span>
        </footer>
      </div>
    </div>
  );
}

const pillStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  padding: '8px 11px',
  borderRadius: 999,
  background: '#fff',
  border: '1px solid var(--w-line)',
  color: 'var(--w-text-1)',
  font: '700 12px/1 var(--w-display)',
};
