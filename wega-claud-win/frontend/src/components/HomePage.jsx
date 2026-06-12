import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Pill, Btn, S } from './ui.jsx';

// Layout primitives sized to match the rest of the app's mono aesthetic.
const Section = ({ kicker, title, children, style }) => (
  <section style={{ marginBottom: 28, ...style }}>
    {kicker && (
      <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.16em', textTransform: 'uppercase', marginBottom: 6 }}>
        // {kicker}
      </div>
    )}
    {title && (
      <h2 style={{ color: 'var(--w-text-0)', font: '600 17px/1.3 var(--w-mono)', margin: '0 0 12px' }}>
        {title}
      </h2>
    )}
    {children}
  </section>
);

const TabCard = ({ glyph, name, oneLine, children }) => (
  <div style={{
    border: '1px solid var(--w-line)',
    background: 'var(--w-bg-2)',
    borderRadius: 3,
    padding: '12px 14px',
    display: 'flex',
    gap: 12,
  }}>
    <div style={{
      flex: '0 0 38px',
      height: 38,
      borderRadius: 3,
      background: 'var(--w-bg-1)',
      border: '1px solid var(--w-line)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: 'var(--w-phosphor)',
      font: '14px/1 var(--w-mono)',
    }}>{glyph}</div>
    <div style={{ minWidth: 0, flex: 1 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
        <span style={{ color: 'var(--w-text-0)', font: '600 13px/1 var(--w-mono)' }}>{name}</span>
        <span style={{ color: 'var(--w-text-3)', font: '11px/1.3 var(--w-mono)' }}>· {oneLine}</span>
      </div>
      <div style={{ color: 'var(--w-text-1)', font: '11.5px/1.55 var(--w-mono)' }}>{children}</div>
    </div>
  </div>
);

const SkillCard = ({ slash, kicker, title, children }) => (
  <div style={{
    border: '1px solid var(--w-phosphor)',
    background: 'var(--w-bg-2)',
    borderLeft: '3px solid var(--w-phosphor)',
    borderRadius: 3,
    padding: '16px 18px',
    marginBottom: 14,
  }}>
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
      <code style={{ color: 'var(--w-phosphor)', font: '600 14px/1 var(--w-mono)' }}>{slash}</code>
      <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>{kicker}</span>
    </div>
    <h3 style={{ color: 'var(--w-text-0)', font: '600 14px/1.3 var(--w-mono)', margin: '0 0 10px' }}>{title}</h3>
    <div style={{ color: 'var(--w-text-1)', font: '12px/1.6 var(--w-mono)' }}>{children}</div>
  </div>
);

export function HomePage({ projects, onPickProject }) {
  const navigate = useNavigate();
  const openProject = (id) => {
    if (onPickProject) onPickProject(id);
    else navigate(`/projects/${id}/chat`);
  };

  return (
    <div style={{
      flex: 1,
      overflow: 'auto',
      background: 'var(--w-bg-0)',
      padding: '40px 56px',
    }}>
      <div style={{ maxWidth: 980, margin: '0 auto' }}>

        {/* Hero */}
        <div style={{ marginBottom: 36 }}>
          <div style={{ color: 'var(--w-phosphor)', font: '10.5px/1 var(--w-mono)', letterSpacing: '0.2em', textTransform: 'uppercase', marginBottom: 10 }}>
            Quantnik · v0.4.2-α
          </div>
          <h1 style={{
            color: 'var(--w-text-0)', font: '700 32px/1.15 var(--w-mono)',
            letterSpacing: '-0.01em', margin: '0 0 10px',
            textShadow: '0 0 16px var(--w-phosphor-glow)',
          }}>
            Welcome to <span style={{ color: 'var(--w-phosphor)' }}>Quantnik</span>
          </h1>
          <div style={{ color: 'var(--w-text-1)', font: '15px/1.5 var(--w-mono)', maxWidth: 700 }}>
            The integrated, one-stop build platform. Plan, build, test, deploy, and ship — all
            from one workspace, with Claude doing the heavy lifting through skills you orchestrate.
          </div>
        </div>

        {/* Quick start */}
        <Section kicker="getting started" title="How to use the platform">
          <ol style={{ color: 'var(--w-text-1)', font: '12.5px/1.7 var(--w-mono)', paddingLeft: 22, margin: 0 }}>
            <li><strong>Create a project</strong> from the left sidebar — click <code style={{ color: 'var(--w-phosphor)' }}>[ + ] new project</code>.</li>
            <li><strong>Hook it up</strong> — connect a git repo (Repos tab), configure your Atlassian targets (Settings), add MCP servers (MCP tab) for Jira / Confluence / Figma access.</li>
            <li><strong>Upload requirements</strong> — drop a BRD, transcript, or idea doc into the Files tab.</li>
            <li><strong>Pick a skill</strong> — type <code style={{ color: 'var(--w-phosphor)' }}>/sdlc-tokenomics</code> to budget, or <code style={{ color: 'var(--w-phosphor)' }}>/sdlc-orchestrator</code> to execute end-to-end. Or just chat with Claude directly.</li>
            <li><strong>Watch artifacts arrive</strong> — generated code lands in your repos, reports in Confluence, test scripts in git, deployed apps at <code style={{ color: 'var(--w-cyan)' }}>https://claude.wegaplatform.com/&lt;slug&gt;</code>.</li>
          </ol>
        </Section>

        {/* Tab overview */}
        <Section kicker="anatomy" title="The seven tabs">
          <div style={{ color: 'var(--w-text-2)', font: '11.5px/1.5 var(--w-mono)', marginBottom: 14 }}>
            Every project has the same surface. Tabs are scoped to the currently-selected project, so context is preserved as you switch projects.
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <TabCard glyph=">_" name="chat" oneLine="primary work surface">
              Talk to Claude. Attach files, invoke skills with <S c="var(--w-phosphor)">/&lt;name&gt;</S>, watch streaming tool use. Every turn's token usage feeds the Admin Overview.
            </TabCard>
            <TabCard glyph="◫" name="dashboard" oneLine="project pulse">
              At-a-glance view of repos, recent activity, and per-phase orchestrator status. Server-authoritative — the panel reads phase state from <S c="var(--w-cyan)">/api/phases/&lt;projectId&gt;</S>.
            </TabCard>
            <TabCard glyph="▤" name="files" oneLine="inbox + outbox">
              Upload requirement docs (PDF, DOCX, MD, images). Skills also drop their artifacts here — tokenomics PDFs / xlsx, deployment manifests, generated reports.
            </TabCard>
            <TabCard glyph="▣" name="repos" oneLine="git working trees">
              Register source repos by remote URL. Quantnik clones them locally; skills like feature-dev and orchestrator write generated code straight to these working copies on a fresh branch.
            </TabCard>
            <TabCard glyph="⚙" name="skills" oneLine="agent capabilities">
              Per-project skill files (live alongside the user-level seed catalog). Each skill is a <S c="var(--w-cyan)">SKILL.md</S> that teaches Claude how to do one job — read, edit, ship via slash command.
            </TabCard>
            <TabCard glyph="⌬" name="mcp" oneLine="external tool access">
              Model Context Protocol servers — Atlassian (Jira + Confluence), Figma, custom. The agent reaches out through these to talk to systems beyond the local filesystem.
            </TabCard>
            <TabCard glyph="✦" name="settings" oneLine="per-project config">
              Permission mode (how autonomously the agent acts), LLM provider/model (Anthropic / Bedrock / Vertex / Foundry), lifecycle hooks. Admins get the cross-user usage + cost overview here.
            </TabCard>
          </div>
        </Section>

        {/* Featured skills */}
        <Section kicker="flagship skills" title="Two skills you'll use a lot">
          <SkillCard slash="/sdlc-tokenomics" kicker="budget · plan" title="Phase-by-phase LLM cost mapping">
            <p style={{ margin: '0 0 8px' }}>
              Upload a requirement document to the Files tab, then invoke <code style={{ color: 'var(--w-phosphor)' }}>/sdlc-tokenomics</code>. The skill reads the document, classifies its complexity, walks the eleven sdlc-orchestrator phases (BRD → User Stories → Feature Dev → Vulnerability → Tech Debt → Test Cases → Test Scripts → Boot → Test Execution → Deployment → Sanity Check), and picks the best-fit LLM for each phase from a Jan 2026 catalog spanning Anthropic, OpenAI, Google, Meta, Mistral, DeepSeek, and xAI.
            </p>
            <p style={{ margin: '0 0 8px' }}>
              For each phase you get: recommended model, estimated input + output tokens, per-phase cost, and a total. Heavy reasoning phases (BRD shape, Feature Dev architecture, Test Case coverage) get frontier models; mechanical phases (Boot scripts, Deployment YAML) get fast cheap ones.
            </p>
            <p style={{ margin: 0 }}>
              <S c="var(--w-text-2)">Outputs:</S> markdown report at the repo root, multi-sheet Excel workbook in the Files tab, 3-page presentation-ready PDF in the Files tab, and optionally a Confluence page if <code>wega.json</code> declares a space.
            </p>
          </SkillCard>

          <SkillCard slash="/sdlc-orchestrator" kicker="execute · ship" title="End-to-end autonomous SDLC pipeline">
            <p style={{ margin: '0 0 8px' }}>
              The flagship. After a single Phase-0 intake questionnaire, it runs eleven phases in sequence — fully autonomous except for one deliberate auto-fix prompt during test execution. Phase 0 starts with a hard-gate <code style={{ color: 'var(--w-phosphor)' }}>config-check</code> that verifies git remotes, Jira + Confluence MCPs, and the Quantnik service itself, so the run never burns minutes against a broken integration.
            </p>
            <p style={{ margin: '0 0 8px' }}>
              Pipeline: <S c="var(--w-cyan)">BRD generation</S> → INVEST user stories pushed to Jira → full-stack code scaffold → vulnerability scan + auto-fix → tech-debt scan + auto-fix → Jira/Xray test cases → Playwright test scripts → install + boot dev servers → run Playwright suite + log Jira bugs for failures → production build deployed under <code style={{ color: 'var(--w-cyan)' }}>claude.wegaplatform.com/&lt;slug&gt;</code> → deploy-time sanity check published to Confluence.
            </p>
            <p style={{ margin: 0 }}>
              Every Confluence write is gated by <code>wega.json.atlassian.confluenceSpaceKey</code> and every Jira write by <code>jiraProjectKey</code> — the pipeline halts rather than writing to the wrong space.
            </p>
          </SkillCard>

          <div style={{ color: 'var(--w-text-3)', font: '11px/1.5 var(--w-mono)' }}>
            Other skills you'll see in your slash menu: <code>sdlc-planning</code>, <code>user-stories</code>, <code>feature-dev</code>, <code>vulnerability-check</code>, <code>tech-debt-check</code>, <code>test-case-generator</code>, <code>test-script-generator</code>, <code>test-script-executor</code>, <code>deploy-to-platform</code>, <code>sanity-check</code>, <code>dotnet-modernize</code>. Each one shows up in the Skills tab with its full SKILL.md ready to read.
          </div>
        </Section>

        {/* Quantnik Brain — hero card. The chatbot lives inside every project's
            Chat tab; the most direct way in is to pick a project below and
            it'll be the first thing you see. */}
        <Section kicker="ask anything" title="Quantnik Brain — your project's autobiographer">
          <div style={{
            display: 'flex',
            gap: 14,
            padding: '18px 22px',
            border: '1.5px solid var(--w-phosphor)',
            borderLeft: '4px solid var(--w-phosphor)',
            background: 'linear-gradient(120deg, var(--w-phosphor-veil), transparent 70%)',
            borderRadius: 5,
            alignItems: 'flex-start',
          }}>
            <div style={{
              flex: '0 0 48px',
              height: 48,
              borderRadius: 24,
              border: '2px solid var(--w-phosphor)',
              background: 'var(--w-phosphor-veil)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              font: '24px/1 var(--w-mono)',
              textShadow: '0 0 14px var(--w-phosphor-glow)',
            }}>🧠</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ color: 'var(--w-text-0)', font: '14px/1.55 var(--w-mono)', marginBottom: 8 }}>
                I'm a chatbot living inside every project's Chat tab. I've read everything you've
                ingested into the Context Fabric — code, BRDs, websites, prior agent runs — and I'll
                answer questions about your project conversationally. Lines of code? BRD risks?
                What does Phase 6 actually do? Just ask.
              </div>
              <div style={{ color: 'var(--w-text-2)', font: '11.5px/1.55 var(--w-mono)' }}>
                Pick a project below to start a conversation. Quantnik Brain auto-expands at the top of
                that project's chat — addresses you by name, holds the thread, grounds answers in
                facts and cites the sources.
              </div>
            </div>
          </div>
        </Section>

        {/* Cross-project knowledge */}
        <Section kicker="cross-project" title="Knowledge that spans every project">
          <button
            onClick={() => navigate('/context')}
            style={{
              width: '100%',
              textAlign: 'left',
              padding: '14px 18px',
              border: '1px solid var(--w-cyan)',
              borderLeft: '3px solid var(--w-cyan)',
              background: 'var(--w-bg-2)',
              borderRadius: 3,
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--w-phosphor-veil)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--w-bg-2)'; }}
          >
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
              <span style={{ color: 'var(--w-cyan)', font: '14px/1 var(--w-mono)' }}>◈</span>
              <span style={{ color: 'var(--w-text-0)', font: '600 14px/1 var(--w-mono)' }}>Context Fabric — Global</span>
              <span style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)' }}>/context</span>
            </div>
            <div style={{ color: 'var(--w-text-1)', font: '12px/1.5 var(--w-mono)' }}>
              The Quantnik-level RAG knowledge layer. Register runbooks, brand guides, architecture
              decisions, or policy documents once — every project's queries (incl. Quantnik Brain) see them.
              Admin-managed.
            </div>
          </button>
        </Section>

        {/* Your projects shortcut */}
        {projects && projects.length > 0 && (
          <Section kicker="resume" title="Your projects">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
              {projects.map((p) => (
                <button
                  key={p.id}
                  onClick={() => openProject(p.id)}
                  style={{
                    textAlign: 'left',
                    padding: '10px 12px',
                    border: '1px solid var(--w-line)',
                    background: 'var(--w-bg-2)',
                    color: 'var(--w-text-0)',
                    font: '500 12.5px/1.3 var(--w-mono)',
                    borderRadius: 3,
                    cursor: 'pointer',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--w-phosphor)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--w-line)'; }}
                >
                  <div style={{ color: 'var(--w-phosphor)', marginBottom: 4 }}>▸ {p.name}</div>
                  <div style={{ color: 'var(--w-text-3)', font: '10.5px/1.3 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={p.path}>{p.path}</div>
                </button>
              ))}
            </div>
          </Section>
        )}

        {/* Footer */}
        <div style={{
          marginTop: 40, paddingTop: 18,
          borderTop: '1px dashed var(--w-line)',
          color: 'var(--w-text-3)',
          font: '10.5px/1.6 var(--w-mono)',
          display: 'flex', justifyContent: 'space-between',
        }}>
          <span>Click the <S c="var(--w-phosphor)">Quantnik</S> logo in the sidebar any time to come back here.</span>
          <span>build · v0.4.2-α</span>
        </div>
      </div>
    </div>
  );
}
