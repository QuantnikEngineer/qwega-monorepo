import React, { useEffect, useState, useMemo } from 'react';
import { api } from '../lib/api.js';
import { ScreenFrame, Pill, Btn, KeyCap, S, SectionLabel } from './ui.jsx';

const TEMPLATE = `---
name: my-skill
description: One-line description shown when Claude decides whether to use this skill
---

# my-skill

Steps for Claude to follow when invoking this skill.
`;

function guessCategory(name, desc) {
  const t = `${name} ${desc || ''}`.toLowerCase();
  if (/orchestrat|pipeline|sdlc-orch/.test(t)) return 'orchestrate';
  if (/plan|brd|stor|spec/.test(t)) return 'plan';
  if (/test|playwright|gherkin|xray/.test(t)) return 'test';
  if (/explain|teach|how|review/.test(t)) return 'explain';
  return 'build';
}

const CAT_TONE = { build: 'phosphor', plan: 'cyan', test: 'amber', explain: 'violet', orchestrate: 'magenta' };

function SkillCard({ name, blurb, cat, owner, inherited, runs, onOpen, onRemove, onRun }) {
  const borderColor = cat === 'orchestrate' ? 'var(--w-magenta)' : cat === 'plan' ? 'var(--w-cyan)' : cat === 'test' ? 'var(--w-amber)' : cat === 'explain' ? 'var(--w-violet)' : 'var(--w-phosphor)';
  return (
    <div style={{
      border: '1px solid var(--w-line)',
      borderLeft: `2px solid ${borderColor}`,
      borderRadius: 3,
      background: 'var(--w-bg-2)',
      padding: '14px 16px',
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
        <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: 'var(--w-text-3)', font: '11px/1 var(--w-mono)' }}>/</span>
            <span style={{ color: 'var(--w-text-0)', font: '600 14px/1.2 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{name}</span>
            {inherited && <Pill>inherited</Pill>}
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            <Pill tone={CAT_TONE[cat]}>{cat}</Pill>
            <Pill style={{ textTransform: 'lowercase' }}>{owner === 'user' ? '~/.claude' : 'project'}</Pill>
          </div>
        </div>
        {runs != null && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
            <span style={{ color: 'var(--w-phosphor)', font: '16px/1 var(--w-display)' }}>{runs}</span>
            <span style={{ color: 'var(--w-text-3)', font: '9.5px/1 var(--w-mono)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>runs</span>
          </div>
        )}
      </div>
      <div style={{ color: 'var(--w-text-1)', font: '11.5px/1.55 var(--w-mono)' }}>{blurb}</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
        <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)' }}>SKILL.md</span>
        <span style={{ display: 'flex', gap: 8 }}>
          {onOpen && <span onClick={onOpen} style={{ color: 'var(--w-cyan)', font: '10.5px/1 var(--w-mono)', cursor: 'pointer' }}>[ open ]</span>}
          {onRun && <span onClick={onRun} style={{ color: 'var(--w-phosphor)', font: '10.5px/1 var(--w-mono)', cursor: 'pointer' }}>[ ↺ run ]</span>}
          {onRemove && <span onClick={onRemove} style={{ color: 'var(--w-red)', font: '10.5px/1 var(--w-mono)', cursor: 'pointer' }}>[ del ]</span>}
        </span>
      </div>
    </div>
  );
}

const ALL_CATS = ['all', 'plan', 'build', 'test', 'explain', 'orchestrate'];

export function SkillsPanel({ project }) {
  const hasProject = !!project?.id;
  const [skills, setSkills] = useState([]);
  const [inherited, setInherited] = useState({ user: [], plugins: [] });
  const [selected, setSelected] = useState(null);
  const [content, setContent] = useState('');
  const [search, setSearch] = useState('');
  const [filterCat, setFilterCat] = useState('all');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);

  const flash = (kind, text) => {
    setStatus({ kind, text });
    setTimeout(() => setStatus((s) => (s && s.text === text ? null : s)), 3000);
  };

  const load = async () => {
    if (hasProject) {
      try { setSkills(await api.listSkills(project.id)); } catch (e) { flash('error', e.message); }
    } else {
      setSkills([]);
    }
    try { setInherited(await api.inheritedSkills()); } catch { /* ignore */ }
  };

  useEffect(() => { load(); setSelected(null); setContent(''); setStatus(null); }, [project?.id]);

  const open = async (name) => {
    if (!hasProject) return;
    try {
      setSelected(name);
      const s = await api.getSkill(project.id, name);
      setContent(s.content);
    } catch (e) { flash('error', e.message); }
  };

  const save = async () => {
    if (!selected || busy) return;
    setBusy(true);
    try {
      await api.saveSkill(project.id, selected, content);
      flash('ok', `saved "${selected}"`);
      await load();
    } catch (e) { flash('error', e.message); }
    setBusy(false);
  };

  const create = async () => {
    if (!hasProject) {
      flash('error', 'create a project first to add project-local skills');
      return;
    }
    const name = prompt('new skill name (a-zA-Z0-9_-)');
    if (!name || !/^[a-zA-Z0-9_-]+$/.test(name.trim())) return;
    const n = name.trim();
    try {
      await api.saveSkill(project.id, n, TEMPLATE.replaceAll('my-skill', n));
      await load();
      open(n);
      flash('ok', `created "${n}"`);
    } catch (e) { flash('error', e.message); }
  };

  const remove = async (name) => {
    if (!hasProject) return;
    if (!confirm(`delete skill "${name}"?`)) return;
    try {
      await api.deleteSkill(project.id, name);
      if (selected === name) { setSelected(null); setContent(''); }
      await load();
      flash('ok', `deleted "${name}"`);
    } catch (e) { flash('error', e.message); }
  };

  const inheritedCards = useMemo(() => {
    const cards = (inherited.user || []).map((s) => ({
      ...s, owner: 'user', cat: guessCategory(s.name, s.description), inherited: true,
    }));
    return cards.filter((c) => {
      if (filterCat !== 'all' && c.cat !== filterCat) return false;
      if (search && !`${c.name} ${c.description || ''}`.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [inherited, search, filterCat]);

  const totalInherited = (inherited.user || []).length;

  return (
    <ScreenFrame
      breadcrumb={<><S c="var(--w-phosphor)">~/{hasProject ? project.name : 'workbench'}</S> ─ skills</>}
      title="Skills"
      subtitle={
        hasProject
          ? <>Skills live in <S c="var(--w-cyan)">.claude/skills/&lt;name&gt;/SKILL.md</S>. Project skills override user-scoped skills with the same name. Both scopes are passed to the Agent SDK as <S c="var(--w-amber)">settingSources</S>.</>
          : <>Inherited skills are available before a project exists. Create or select a project to add project-local <S c="var(--w-cyan)">SKILL.md</S> workflows.</>
      }
      action={
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn tone="primary" onClick={create} disabled={!hasProject}>[ + ] new skill</Btn>
        </div>
      }
    >
      {/* Search + filters */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
        <div style={{
          flex: 1,
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '8px 12px',
          border: '1px solid var(--w-line)',
          background: 'var(--w-bg-2)',
          borderRadius: 3,
        }}>
          <span style={{ color: 'var(--w-phosphor)' }}>⌕</span>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder='search skills... e.g. "jira" or category:test'
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: 'var(--w-text-0)', font: '12.5px/1.4 var(--w-mono)' }}
          />
          <KeyCap>⌘P</KeyCap>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {ALL_CATS.map((c) => (
            <Pill
              key={c}
              tone={c === filterCat ? (c === 'all' ? 'phosphor' : CAT_TONE[c]) : 'default'}
              dot={c === filterCat}
              onClick={() => setFilterCat(c)}
            >
              {c}{c === 'all' ? ` (${totalInherited + skills.length})` : ''}
            </Pill>
          ))}
        </div>
      </div>

      {status && (
        <div style={{
          marginBottom: 12, padding: '6px 10px', borderRadius: 3,
          background: status.kind === 'ok' ? 'var(--w-phosphor-veil)' : 'rgba(255,71,87,0.1)',
          color: status.kind === 'ok' ? 'var(--w-phosphor)' : 'var(--w-red)',
          border: `1px solid ${status.kind === 'ok' ? 'var(--w-line-strong)' : 'rgba(255,71,87,0.3)'}`,
          font: '11.5px/1.4 var(--w-mono)',
        }}>{status.text}</div>
      )}

      {/* Local section */}
      <div style={{ marginBottom: 18 }}>
        <SectionLabel tone="phosphor" right={<Pill>{skills.length === 0 ? 'none yet' : `${skills.length} skill${skills.length === 1 ? '' : 's'}`}</Pill>}>
          // local · {hasProject ? project.name : 'no project selected'}
        </SectionLabel>
        {!hasProject ? (
          <div style={{
            border: '1px dashed var(--w-line)',
            borderRadius: 3,
            padding: '16px 20px',
            background: 'var(--w-bg-1)',
            color: 'var(--w-text-2)',
            font: '12px/1.5 var(--w-mono)',
          }}>
            Project-local skills are stored inside a project's <S c="var(--w-cyan)">.claude/skills</S> directory. The inherited skills below remain visible globally.
          </div>
        ) : skills.length === 0 ? (
          <div style={{
            border: '1px dashed var(--w-line)',
            borderRadius: 3,
            padding: '16px 20px',
            background: 'var(--w-bg-1)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16,
          }}>
            <div>
              <div style={{ color: 'var(--w-text-0)', font: '13px/1.3 var(--w-mono)', marginBottom: 4 }}>
                no project skills yet. <S c="var(--w-text-2)">create one to bind a domain-specific workflow to this project.</S>
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{ color: 'var(--w-phosphor)' }}>$</span>
                <span style={{ color: 'var(--w-syn-str)', font: '11.5px/1 var(--w-mono)' }}>mkdir -p .claude/skills/&lt;name&gt; {'&&'} touch SKILL.md</span>
              </div>
            </div>
            <Btn tone="line" onClick={create}>[ + ] new local skill</Btn>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
            {skills.map((s) => (
              <SkillCard
                key={s.name}
                name={s.name}
                blurb={s.hasSkillMd ? 'project-scoped skill' : 'incomplete (missing SKILL.md)'}
                cat={guessCategory(s.name)}
                owner="project"
                onOpen={() => open(s.name)}
                onRemove={() => remove(s.name)}
              />
            ))}
          </div>
        )}

        {selected && (
          <div style={{ marginTop: 16 }}>
            <SectionLabel tone="cyan" right={<>
              <Btn tone="ghost" onClick={() => { setSelected(null); setContent(''); }}>close</Btn>
              <Btn tone="primary" onClick={save} disabled={busy} style={{ marginLeft: 6 }}>{busy ? 'saving…' : '[ ⤓ ] save'}</Btn>
            </>}>
              // editing · {selected}/SKILL.md
            </SectionLabel>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              spellCheck={false}
              style={{
                width: '100%', minHeight: 280,
                padding: '12px 14px',
                background: 'var(--w-bg-1)',
                color: 'var(--w-text-0)',
                border: '1px solid var(--w-line-strong)',
                borderRadius: 3,
                font: '11.5px/1.55 var(--w-mono)',
                resize: 'vertical',
              }}
            />
          </div>
        )}
      </div>

      {/* Inherited grid */}
      <div>
        <SectionLabel tone="cyan" right={<>
          <Pill tone="cyan">{totalInherited} skills</Pill>
          <span style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)', marginLeft: 8 }}>read-only</span>
        </>}>
          // inherited · ~/.claude
        </SectionLabel>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
          {inheritedCards.map((s) => (
            <SkillCard
              key={s.name}
              name={s.name}
              blurb={s.description || 'no description'}
              cat={s.cat}
              owner="user"
              inherited
            />
          ))}
        </div>
      </div>
    </ScreenFrame>
  );
}
