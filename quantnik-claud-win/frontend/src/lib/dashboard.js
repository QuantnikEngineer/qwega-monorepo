// Aggregations for the Dashboard tab. Pure functions over the message stream
// returned by api.getMessages(projectId) — same shape as Chat.jsx consumes via
// the WS, except `payload` here is already a parsed object (not a JSON string).

const SITE = 'sandboxwipro2025';

function payloadOf(m) {
  return m?.payload || null;
}

function textOfToolResult(content) {
  if (Array.isArray(content)) {
    return content
      .map((c) => (typeof c === 'string' ? c : c?.text || JSON.stringify(c)))
      .join('\n');
  }
  if (typeof content === 'string') return content;
  return content ? JSON.stringify(content) : '';
}

// ---------- Token + cost totals ----------

export function aggregateUsage(messages) {
  let input = 0, output = 0, cacheRead = 0, cacheCreate = 0;
  let cost = 0;
  let turns = 0;
  let lastTurnAt = null;
  for (const m of messages) {
    const p = payloadOf(m);
    if (!p || p.type !== 'result') continue;
    turns++;
    const u = p.usage || {};
    input += u.input_tokens || 0;
    output += u.output_tokens || 0;
    cacheRead += u.cache_read_input_tokens || 0;
    cacheCreate += u.cache_creation_input_tokens || 0;
    if (typeof p.totalCostUsd === 'number') cost += p.totalCostUsd;
    if (m.created_at && (!lastTurnAt || m.created_at > lastTurnAt)) {
      lastTurnAt = m.created_at;
    }
  }
  return { input, output, cacheRead, cacheCreate, cost, turns, lastTurnAt };
}

// ---------- Confluence + Jira artifacts ----------
// (Same extraction pattern as Chat.jsx atlassianRefs, but trimmed for the
// dashboard and lifted out so it can be reused.)

const URL_RE = /https?:\/\/([\w-]+)\.atlassian\.net\/(browse\/[A-Z][A-Z0-9_]+-\d+|wiki\/[^\s)"'`<]+)/g;

export function extractAtlassian(messages) {
  const jira = new Map();         // key -> { key, summary, url, type }
  const confluence = new Map();   // url -> { title, url, isBrd }

  let siteFromUrl = null;

  // Pass 1 — bare-URL regex over all text/tool_result.
  const scanText = (s) => {
    if (!s) return;
    let m;
    URL_RE.lastIndex = 0;
    while ((m = URL_RE.exec(s)) !== null) {
      const site = m[1];
      const path = m[2];
      const url = `https://${site}.atlassian.net/${path}`;
      siteFromUrl = siteFromUrl || site;
      if (path.startsWith('browse/')) {
        const key = path.slice('browse/'.length);
        if (!jira.has(key)) jira.set(key, { key, url });
      } else {
        let title = '';
        const slug = path.match(/\/pages\/\d+\/([^/?#]+)/);
        if (slug) {
          try { title = decodeURIComponent(slug[1]).replace(/\+/g, ' '); }
          catch { title = slug[1].replace(/\+/g, ' '); }
        } else {
          const pid = path.match(/pageId=(\d+)/);
          title = pid ? `Page ${pid[1]}` : 'Confluence page';
        }
        if (!confluence.has(url)) {
          confluence.set(url, { title, url, isBrd: /BRD|Business Requirements/i.test(title) });
        }
      }
    }
  };

  for (const m of messages) {
    const p = payloadOf(m);
    if (!p) continue;
    if (p.type === 'assistant_text' && p.text) scanText(p.text);
    if (p.type === 'tool_result') scanText(textOfToolResult(p.content));
    if (m.role === 'user' && typeof p.text === 'string') scanText(p.text);
  }

  // Pass 1b — catch test-case batches emitted by orchestrator subagents.
  // Two shapes produced by test-case-generator's bulk output:
  //   "WSKB-74 ← WSKB-61 functional"         per-row mapping
  //   "Tests: WSKB-74..138  (65 Sub-tasks)"  range summary
  // These never produce a tool_use in the parent chat (subagent-delegated),
  // so the only signal is the final summary text. Mark each as Sub-task.
  const ARROW_RE = /\b([A-Z][A-Z0-9_]+-\d+)\s*[←⟵<\-]{1,3}\s*([A-Z][A-Z0-9_]+-\d+)\s+(functional|non[\s-]?functional|boundary[\s-]?negative|system[\s-]?architecture|gherkin|positive|negative|edge|boundary)/gi;
  const RANGE_RE = /\b([A-Z][A-Z0-9_]+)-(\d+)\s*\.\.\s*(?:\1-)?(\d+)\b/g;
  function recordTestCase(key, parent) {
    if (jira.has(key)) {
      const existing = jira.get(key);
      if (!existing.type) existing.type = 'Sub-task';
      if (!existing.parent && parent) existing.parent = parent;
      return;
    }
    const site = siteFromUrl || SITE;
    jira.set(key, {
      key,
      url: `https://${site}.atlassian.net/browse/${key}`,
      type: 'Sub-task',
      parent: parent || null,
      summary: null,
    });
  }
  function applyTcPatterns(s) {
    if (!s) return;
    let m;
    ARROW_RE.lastIndex = 0;
    while ((m = ARROW_RE.exec(s)) !== null) recordTestCase(m[1], m[2]);
    RANGE_RE.lastIndex = 0;
    while ((m = RANGE_RE.exec(s)) !== null) {
      const prefix = m[1];
      const lo = Number(m[2]);
      const hi = Number(m[3]);
      if (hi <= lo || hi - lo > 200) continue;
      const start = Math.max(0, m.index - 80);
      const end = Math.min(s.length, m.index + m[0].length + 80);
      const context = s.slice(start, end);
      if (!/Sub[\s-]?task|TCs?|test\s+case|Tests?:/i.test(context)) continue;
      for (let n = lo; n <= hi; n++) recordTestCase(`${prefix}-${n}`, null);
    }
  }
  for (const m of messages) {
    const p = payloadOf(m);
    if (!p) continue;
    if (p.type === 'assistant_text' && p.text) applyTcPatterns(p.text);
    if (p.type === 'tool_result') applyTcPatterns(textOfToolResult(p.content));
  }

  // Pass 2 — pair create tool_use calls with the next tool_result to get
  // titles/types directly from the request, not just slug heuristics.
  const pending = [];
  for (const m of messages) {
    const p = payloadOf(m);
    if (!p) continue;
    if (p.type === 'tool_use') {
      const name = p.name || '';
      const input = p.input || {};
      if (
        name === 'mcp__Jira__jira_post' &&
        typeof input.path === 'string' &&
        /\/rest\/api\/\d+\/issue(\/|\?|$)/.test(input.path) &&
        input.body?.fields?.summary
      ) {
        pending.push({
          kind: 'jira',
          summary: input.body.fields.summary,
          type: input.body.fields.issuetype?.name || '',
          parent: input.body.fields.parent?.key || null,
        });
      } else if (name === 'mcp__claude_ai_Atlassian__createJiraIssue' && input.summary) {
        pending.push({
          kind: 'jira',
          summary: input.summary,
          type: input.issueTypeName || '',
          parent: input.parent || null,
        });
      } else if (
        name === 'mcp__Confluence__conf_post' &&
        typeof input.path === 'string' &&
        /\/wiki\/api\/v2\/pages/.test(input.path) &&
        input.body?.title
      ) {
        pending.push({ kind: 'confluence', summary: input.body.title });
      } else if (name === 'mcp__claude_ai_Atlassian__createConfluencePage' && input.title) {
        pending.push({ kind: 'confluence', summary: input.title });
      }
    }
    if (p.type === 'tool_result' && pending.length > 0) {
      const pc = pending.shift();
      const t = textOfToolResult(p.content);
      if (pc.kind === 'jira') {
        const km = t.match(/\bkey:\s*"?([A-Z][A-Z0-9_]+-\d+)"?/) || t.match(/"key"\s*:\s*"([A-Z][A-Z0-9_]+-\d+)"/);
        if (km) {
          const key = km[1];
          const url = `https://${siteFromUrl || SITE}.atlassian.net/browse/${key}`;
          jira.set(key, { key, summary: pc.summary, url, type: pc.type, parent: pc.parent });
        }
      } else {
        const im = t.match(/\bid:\s*"?(\d+)"?/) || t.match(/"id"\s*:\s*"(\d+)"/);
        const wm = t.match(/\bwebui:\s*"?([^"\s]+)"?/) || t.match(/"webui"\s*:\s*"([^"]+)"/);
        if (im) {
          const id = im[1];
          const url = wm
            ? `https://${siteFromUrl || SITE}.atlassian.net/wiki${wm[1]}`
            : `https://${siteFromUrl || SITE}.atlassian.net/wiki/pages/viewpage.action?pageId=${id}`;
          confluence.set(url, { title: pc.summary, url, isBrd: /BRD|Business Requirements/i.test(pc.summary) });
        }
      }
    }
  }

  const jiraArr = [...jira.values()];
  const confluenceArr = [...confluence.values()];
  return {
    confluenceAll: confluenceArr,
    brds: confluenceArr.filter((p) => p.isBrd),
    confluenceOther: confluenceArr.filter((p) => !p.isBrd),
    jiraAll: jiraArr,
    epics: jiraArr.filter((j) => j.type === 'Epic'),
    stories: jiraArr.filter((j) => j.type === 'Story'),
    testCases: jiraArr.filter((j) => j.type === 'Test' || j.type === 'Sub-task' || j.type === 'Subtask'),
    tasks: jiraArr.filter((j) => j.type === 'Task'),
  };
}

// ---------- Tech-debt + vulnerability run summaries ----------
// The skills end with a structured "Findings: N total (c Critical, h High, ...)"
// block. Parse the latest one of each from assistant_text.

// Four finding-count shapes to recognise (some skills don't print "Findings:"):
//   STANDALONE skill: "Findings: 5 total (2 Critical, 5 High, 3 Medium, 2 Low, 1 Info)"
//   ORCHESTRATOR summary: "Findings: 5 (Crit 0 · High 0 · Med 1 · Low 1 · Info 3)"
//   PHASE-STATUS line (Mobile run actually emits this):
//     "Phase 4 — Vulnerability: ✅ done (0 Crit · 0 High · 2 Med · 2 Low · 3 Info pos)"
//     "Phase 5 — Tech Debt: ✅ done (0 Crit · 1 High · 1 Med · 2 Low + 2 positive)"
// Plus loose "Findings: N (...)" with any combination of severity labels.
const SEV_RE_STANDALONE = /Findings:\s*(\d+)\s*total\s*\(\s*(\d+)\s*Critical[,·]\s*(\d+)\s*High[,·]\s*(\d+)\s*Medium[,·]\s*(\d+)\s*Low(?:[,·]\s*(\d+)\s*Info)?\s*\)/i;
const SEV_RE_LOOSE = /Findings:\s*(\d+)\s*(?:total\s*)?\(([^)]+)\)/i;

// Match the phase-status line shape — captures the parenthetical body so the
// existing readCount() helper can pick out per-severity numbers. We don't
// require a "Findings:" prefix; we accept ANY parenthetical that contains a
// Crit/High/Med/Low/Info severity label after a Phase 4 (vuln) or Phase 5
// (debt) marker. Total is derived by summing the severities.
const SEV_RE_PHASE_VULN = /Phase\s*4[^(]{0,80}\(\s*([^)]*(?:Crit|High|Med|Low|Info)[^)]*)\)/i;
const SEV_RE_PHASE_DEBT = /Phase\s*5[^(]{0,80}\(\s*([^)]*(?:Crit|High|Med|Low|Info)[^)]*)\)/i;

function readCount(label, body) {
  // Two layouts in the wild:
  //   "Crit 0 · High 0 · Med 1 · Low 1 · Info 3"   (label-first)
  //   "0 Crit · 0 High · 2 Med · 2 Low · 3 Info"   (number-first)
  // Plus "Critical: 5" / "Med = 2" variants. Try both orderings.
  const labelFirst = new RegExp(`\\b${label}\\b\\s*[:=]?\\s*(\\d+)`, 'i');
  const numberFirst = new RegExp(`(\\d+)\\s+${label}\\b`, 'i');
  const m = body.match(labelFirst) || body.match(numberFirst);
  return m ? Number(m[1]) : 0;
}

function parseRun(text, isVuln) {
  let total, critical, high, medium, low, info;

  const m1 = text.match(SEV_RE_STANDALONE);
  if (m1) {
    [, total, critical, high, medium, low, info] = m1.map((x, i) => (i === 0 ? x : Number(x)));
  } else {
    let body = null;
    const m2 = text.match(SEV_RE_LOOSE);
    if (m2) {
      total = Number(m2[1]);
      body = m2[2];
    } else {
      // Fallback: phase-status-line shape (the orchestrator's actual output
      // for Mobile didn't use "Findings:" at all — the breakdown is inside
      // the phase-status line).
      const m3 = text.match(isVuln ? SEV_RE_PHASE_VULN : SEV_RE_PHASE_DEBT);
      if (!m3) return null;
      body = m3[1];
      total = undefined; // derive from the sum below
    }
    critical = readCount('Crit(?:ical)?', body);
    high     = readCount('High',          body);
    medium   = readCount('Med(?:ium)?',   body);
    low      = readCount('Low',           body);
    info     = readCount('Info',          body);
    if (total === undefined) total = critical + high + medium + low + info;
  }

  // Auto-fixed / refactor / remaining counts — best-effort across both shapes.
  const fixed     = (text.match(/(?:Fixed|Auto-fixed):\s*(\d+)/i) || [])[1];
  const refactor  = (text.match(/(?:Pending review|Needs[\s-]?refactor|Refactor):\s*(\d+)/i) || [])[1];
  const remaining = (text.match(/(?:Still vulnerable|Still[\s-]?debt|Still|Open):\s*(\d+)/i) || [])[1];

  // Report URL — accept the standalone form, the orchestrator emoji-section form,
  // AND the phase-line announcement form the Mobile run actually used
  // ("Phase 4 complete. Vulnerability report published: <url>",
  //  "Phase 5 published: <url>", "Phase 4 complete — report URL: <url>").
  // Accepts both absolute (https://…) and relative (/wiki/…) — the latter is
  // normalised to absolute against the known quantnik.json site below.
  const URL_TOKEN = '(https?:\\/\\/[^\\s`\\\'"]+|\\/wiki\\/[^\\s`\\\'"]+)';
  const mk = (pat, flags = 'i') => new RegExp(pat, flags);
  let url = (
    text.match(mk(`(?:Security audit|Tech-debt)\\s+report\\s+published:\\s*[\`'"]?${URL_TOKEN}`)) ||
    text.match(/Report saved locally:\s*(\S+)/i) ||
    (isVuln && text.match(mk(`🔒\\s*Security audit[\\s\\S]{0,200}?Report:\\s*${URL_TOKEN}`))) ||
    (!isVuln && text.match(mk(`🧹\\s*Tech debt[\\s\\S]{0,200}?Report:\\s*${URL_TOKEN}`))) ||
    (isVuln && text.match(mk(`Phase\\s*4[^.]{0,40}(?:report\\s+(?:url|published)|complete)[:\\s—]*[\`'"]?${URL_TOKEN}`))) ||
    (!isVuln && text.match(mk(`Phase\\s*5\\s+(?:published|complete)[:\\s—]*[\`'"]?${URL_TOKEN}`))) ||
    []
  )[1];
  // Relative `/wiki/…` paths emitted by some skills — promote to absolute.
  if (url && url.startsWith('/wiki/')) {
    url = `https://quantnik.atlassian.net${url}`;
  }

  return {
    kind: isVuln ? 'vulnerability' : 'tech-debt',
    total: Number(total),
    critical: Number(critical) || 0,
    high: Number(high) || 0,
    medium: Number(medium) || 0,
    low: Number(low) || 0,
    info: Number(info) || 0,
    fixed: fixed != null ? Number(fixed) : null,
    refactor: refactor != null ? Number(refactor) : null,
    remaining: remaining != null ? Number(remaining) : null,
    url: url || null,
  };
}

// Each text block can have ONE vuln block and ONE debt block (e.g. the
// orchestrator's final summary lists both). Scope the search to the relevant
// emoji section so we don't cross-talk between the two.
function sliceForKind(text, isVuln) {
  const lead = isVuln ? /🔒\s*Security\s+audit/i : /🧹\s*Tech\s*debt/i;
  const m = text.match(lead);
  if (!m) return text; // standalone-skill output — single context, return as-is
  const start = m.index;
  const end = text.length;
  return text.slice(start, Math.min(end, start + 800));
}

export function extractLatestRuns(messages) {
  let vuln = null;
  let debt = null;
  // Scan oldest-to-newest so we capture URLs that appear in different
  // messages than the severity breakdown — and apply latest-wins per kind.
  // (Mobile run example: severity is on the Phase 4 status line; URL is on
  // an earlier "Phase 4 complete. Vulnerability report published: …" line.)
  let vulnUrl = null, debtUrl = null;
  for (let i = 0; i < messages.length; i++) {
    const p = payloadOf(messages[i]);
    if (!p || p.type !== 'assistant_text' || !p.text) continue;
    const txt = p.text;
    // Free-floating URLs that might pair with a later severity-line match.
    // Accept both absolute and relative /wiki/… forms; normalise relative.
    const normalise = (u) => (u && u.startsWith('/wiki/')) ? `https://quantnik.atlassian.net${u}` : u;
    const vUrl = (txt.match(/Phase\s*4[^.]{0,80}(?:report\s+(?:url|published)|complete|published)[:\s—]*[`'"]?(https?:\/\/[^\s`'"]+|\/wiki\/[^\s`'"]+)/i) || [])[1];
    if (vUrl) vulnUrl = normalise(vUrl);
    const dUrl = (txt.match(/Phase\s*5[^.]{0,80}(?:report\s+(?:url|published)|complete|published)[:\s—]*[`'"]?(https?:\/\/[^\s`'"]+|\/wiki\/[^\s`'"]+)/i) || [])[1];
    if (dUrl) debtUrl = normalise(dUrl);

    // Vulnerability — accept any of: standalone header, orchestrator emoji
    // section, OR a Phase 4 status line with a severity-bearing paren.
    if (/Security audit complete/i.test(txt)
        || /🔒\s*Security\s+audit/i.test(txt)
        || SEV_RE_PHASE_VULN.test(txt)) {
      const parsed = parseRun(sliceForKind(txt, true), true);
      if (parsed) { vuln = parsed; vuln.at = messages[i].created_at; }
    }
    if (/Tech-debt scan complete/i.test(txt)
        || /🧹\s*Tech\s*debt/i.test(txt)
        || SEV_RE_PHASE_DEBT.test(txt)) {
      const parsed = parseRun(sliceForKind(txt, false), false);
      if (parsed) { debt = parsed; debt.at = messages[i].created_at; }
    }
  }
  // Cross-message URL fallback: severity matched but URL was in another msg.
  if (vuln && !vuln.url && vulnUrl) vuln.url = vulnUrl;
  if (debt && !debt.url && debtUrl) debt.url = debtUrl;
  return { vulnerability: vuln, techDebt: debt };
}

// ---------- Tool / session activity ----------

export function aggregateActivity(messages) {
  let toolCalls = 0;
  let toolErrors = 0;
  let assistantTexts = 0;
  let userMessages = 0;
  const toolNames = new Map();
  let firstAt = null, lastAt = null;
  for (const m of messages) {
    const p = payloadOf(m);
    if (m.created_at) {
      if (!firstAt || m.created_at < firstAt) firstAt = m.created_at;
      if (!lastAt || m.created_at > lastAt) lastAt = m.created_at;
    }
    if (m.role === 'user') { userMessages++; continue; }
    if (!p) continue;
    if (p.type === 'tool_use') {
      toolCalls++;
      const n = p.name || 'unknown';
      toolNames.set(n, (toolNames.get(n) || 0) + 1);
    }
    if (p.type === 'tool_result' && p.isError) toolErrors++;
    if (p.type === 'assistant_text') assistantTexts++;
  }
  const topTools = [...toolNames.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([name, count]) => ({ name, count }));
  return { toolCalls, toolErrors, assistantTexts, userMessages, topTools, firstAt, lastAt };
}
