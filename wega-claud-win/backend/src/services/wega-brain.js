// Quantnik Brain — RAG generation. Given a question, retrieve top-K context
// chunks (from the Context Fabric), pass them to Claude as system context,
// and return a grounded answer with citations.
//
// Auth: reads ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN from the wega2
// .env — same env vars routes/llm.js uses for direct-Anthropic LLM calls.
// No extra subscription, no new vendor. The Claude Code subscription token
// works because the SDK accepts it as an authToken bearer.
//
// Model:  WEGA_BRAIN_MODEL env var, default claude-sonnet-4-6 (balanced for
// Q&A — Haiku is too thin for nuanced grounding, Opus is overkill).
//
// Usage cost is recorded in the existing usage_events table with model name
// "wega-brain:<model>" so the admin overview rolls it up next to chat usage.

import Anthropic from '@anthropic-ai/sdk';
import { BedrockRuntimeClient, InvokeModelCommand } from '@aws-sdk/client-bedrock-runtime';
import { db } from '../db.js';
import { retrieve } from './retrieval.js';

const DEFAULT_MODEL          = 'claude-sonnet-4-6';
// House default for Bedrock: Sonnet 4.6 inference profile. Was 3.7 Sonnet
// (now retired). Override per-instance via WEGA_BRAIN_BEDROCK_MODEL in .env.
const DEFAULT_BEDROCK_MODEL  = 'us.anthropic.claude-sonnet-4-6-20251001-v1:0';
const DEFAULT_BEDROCK_REGION = 'us-east-1';

function buildSystemPrompt(userName) {
  const name = userName ? userName.split(/[.@\s]/)[0].replace(/^./, (c) => c.toUpperCase()) : null;
  const addressed = name ? name : 'friend';
  return `You are Quantnik Brain — the Quantnik platform's resident know-it-all. You live inside the user's project, you've read everything they've ingested, and your job is to be useful and a little bit fun about it.

WHO YOU'RE TALKING TO
${name ? `The human's first name is ${name}. Address them by name occasionally (not every message — only when it feels natural, like "Yeah ${name}, …" or "Good question, ${name} —"). Never overdo it.` : `You don't know the user's name in this session, so call them "friend" sparingly or just skip the address.`}

PERSONALITY
- Conversational, not robotic. You're a smart colleague at a whiteboard, not a search engine UI.
- Light humor is welcome — dry wit, the occasional aside, the occasional emoji. NEVER cringe-quirky. NEVER over-explain the joke. If you're not sure something will land, drop it.
- You have OPINIONS when context supports them ("…that's a lot of CSS for a Vite project — typical React app spread", or "the orchestrator's Phase 6 budget always looks scarier than it actually is"). Don't manufacture opinions when you don't have grounding for them.
- Short. Snappy. Bullet lists are great. A 3-paragraph reply when 4 sentences would do is a wasted reader's afternoon.
- You can use casual phrasings: "honestly", "fair point", "give or take", "to be clear", "rough math". You can use one emoji per message tops (👀 🧠 ⚡ ☕ 📊 etc.) — never two.

GROUNDING (this is non-negotiable — don't drift on facts)

You have two kinds of grounding material in every turn:

  1. PROJECT FACTS — a structured summary at the top of the user message: project name, repos, LOC count, file mix, ingested sources, activity. Treat these as **authoritative** facts about the project. Answer metadata questions ("how many lines of code?", "which repos are wired?", "what's ingested?") DIRECTLY and conversationally from this section — no citations needed.

  2. CONTEXT EXCERPTS — passages retrieved from the user's ingested sources. Each is numbered [1], [2], etc. When you state a NARRATIVE fact pulled from an excerpt ("the BRD says …", "the test plan covers …"), cite the source inline with its number — e.g. "the BRD describes a card discovery flow with three steps [3]". Cite the SMALLEST set of excerpts that supports each claim. Don't pile on numbers for effect.

When you genuinely can't answer (the facts don't cover it AND no excerpt does), say so honestly. Phrases that work:
  - "I don't see that in this project's context — want to add it to the Context Fabric?"
  - "Not in what's been ingested yet — but if you point me at a doc or repo, I'll have it next time."
  - For project-shape questions that fall outside the project's actual knowledge: just be direct that the question is outside scope.

Never invent file paths, function names, numeric values, URLs, or quotes that aren't in PROJECT FACTS or excerpts. Better to admit a gap than to bluff.

CONVERSATIONAL CONTEXT

You may receive prior turns of this same conversation. Use them — if the user asked about "the BRD" two turns ago and now says "show me its risks section", that's a follow-up, treat it as such. Reference what was said earlier when it makes the answer tighter; don't repeat yourself.

OPENING MOVES (only if the very first user message is a generic greeting like "hi" / "hello" / "what's up")
Don't just say hi back — show value. Glance at PROJECT FACTS and offer 2-3 things you can actually help with right now. Format:
  "Hey${name ? ` ${name}` : ''} — quick lay of the land: <one sentence project summary from facts>. A few things I can dig into right now:
   - <concrete option pulled from facts: e.g. 'tell you about that 90-chunk agent_output we just indexed'>
   - <another concrete option>
   - <another>
   Or ask me anything else. What's up?"

Now answer the user's question.`;
}

let _anthropicClient = null;
function anthropicClient() {
  if (_anthropicClient) return _anthropicClient;
  // Prefer ANTHROPIC_API_KEY (api key); fall back to CLAUDE_CODE_OAUTH_TOKEN
  // (the long-lived OAuth bearer the Claude Code subscription mints).
  const apiKey = process.env.ANTHROPIC_API_KEY || null;
  const oauth  = process.env.CLAUDE_CODE_OAUTH_TOKEN || null;
  if (!apiKey && !oauth) return null;
  _anthropicClient = new Anthropic({
    apiKey: apiKey || undefined,
    authToken: oauth || undefined,
  });
  return _anthropicClient;
}

let _bedrockClient = null;
let _bedrockClientRegion = null;
function bedrockClient() {
  // Bedrock fallback. Activates when AWS_BEARER_TOKEN_BEDROCK is present in
  // env (the SDK reads it natively for AuthV4-with-bearer signing). Other
  // AWS_* credentials are also honoured if present. Region defaults to
  // us-east-1 unless overridden via AWS_REGION.
  if (!process.env.AWS_BEARER_TOKEN_BEDROCK
      && !process.env.AWS_ACCESS_KEY_ID) return null;
  const region = process.env.AWS_REGION || DEFAULT_BEDROCK_REGION;
  if (_bedrockClient && _bedrockClientRegion === region) return _bedrockClient;
  _bedrockClient = new BedrockRuntimeClient({ region });
  _bedrockClientRegion = region;
  return _bedrockClient;
}

function isRateLimitOrOverloaded(err) {
  // Anthropic SDK throws RateLimitError (429) and InternalServerError /
  // OverloadedError (529). Match by status code AND name string for
  // robustness across SDK versions.
  const status = err?.status || err?.statusCode;
  if (status === 429 || status === 529 || status === 503 || status === 502) return true;
  const name = (err?.name || '').toLowerCase();
  if (name.includes('ratelimit') || name.includes('overloaded')) return true;
  // Some Anthropic 429s surface as plain errors with the body in the message.
  const msg = (err?.message || '').toLowerCase();
  if (msg.includes('429') || msg.includes('rate_limit') || msg.includes('overloaded')) return true;
  return false;
}

/**
 * Direct-Anthropic generation path. Throws on failure (caller decides
 * whether to fall back to Bedrock).
 */
async function generateViaAnthropic({ model, system, messages }) {
  const client = anthropicClient();
  if (!client) throw new Error('anthropic_unconfigured: no ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN');
  const resp = await client.messages.create({
    model, max_tokens: 1536, system,
    messages,
  });
  return {
    text: resp.content.filter((b) => b.type === 'text').map((b) => b.text).join(''),
    usage: resp.usage || {},
    modelUsed: model,
    via: 'anthropic',  // fallback path now (was the primary in the prior version).
  };
}

/**
 * Bedrock generation path. Wraps the same messages-style payload Bedrock's
 * Anthropic adapter expects (`anthropic_version: bedrock-2023-05-31`).
 */
async function generateViaBedrock({ system, messages }) {
  const client = bedrockClient();
  if (!client) throw new Error('bedrock_unconfigured: no AWS_BEARER_TOKEN_BEDROCK or AWS_ACCESS_KEY_ID');
  const modelId = process.env.WEGA_BRAIN_BEDROCK_MODEL || DEFAULT_BEDROCK_MODEL;
  const resp = await client.send(new InvokeModelCommand({
    modelId,
    contentType: 'application/json',
    accept: 'application/json',
    body: JSON.stringify({
      anthropic_version: 'bedrock-2023-05-31',
      max_tokens: 1536,
      system,
      messages,
    }),
  }));
  const parsed = JSON.parse(new TextDecoder().decode(resp.body));
  return {
    text: (parsed.content || []).filter((b) => b.type === 'text').map((b) => b.text).join(''),
    usage: parsed.usage || {},
    modelUsed: modelId,
    via: 'bedrock',  // was 'bedrock-fallback' — Bedrock is the primary path now.
  };
}

// In-memory cache for project facts — keyed by projectId. 5-min TTL.
// gatherProjectFacts walks the repo for LOC each call otherwise, which on a
// medium codebase can take 300-2000 ms. Caching keeps Quantnik Brain snappy for
// follow-up questions on the same project within a working session.
const FACTS_TTL_MS = 5 * 60 * 1000;
const factsCache = new Map(); // projectId → { at, value }

async function gatherProjectFacts(projectId) {
  if (!projectId) return null;
  const cached = factsCache.get(projectId);
  if (cached && (Date.now() - cached.at) < FACTS_TTL_MS) return cached.value;

  const project = db.prepare(`SELECT * FROM projects WHERE id = ?`).get(projectId);
  if (!project) return null;

  // Repos configured in the Repos tab
  const repos = db.prepare(`SELECT id, name, path, remote_url FROM project_repos WHERE project_id = ?`).all(projectId);

  // Context Fabric sources for this project
  const sources = db.prepare(`
    SELECT s.type, s.label, s.status, s.last_ingested_at,
      (SELECT COUNT(*) FROM context_chunks ch
        JOIN context_documents d ON d.id = ch.document_id
        WHERE d.source_id = s.id) AS chunks,
      (SELECT COUNT(*) FROM context_documents d WHERE d.source_id = s.id) AS docs
    FROM context_sources s
    WHERE s.scope = 'project' AND s.project_id = ?
    ORDER BY s.type
  `).all(projectId);

  // Org sources also visible to this project (inherited via scope filter)
  const orgSources = db.prepare(`
    SELECT type, label,
      (SELECT COUNT(*) FROM context_chunks ch
        JOIN context_documents d ON d.id = ch.document_id
        WHERE d.source_id = context_sources.id) AS chunks
    FROM context_sources
    WHERE scope = 'org' AND status = 'ready'
  `).all();

  // Recent activity (last assistant message timestamp + how long ago)
  const lastMsg = db.prepare(`
    SELECT created_at FROM messages WHERE project_id = ?
    ORDER BY id DESC LIMIT 1
  `).get(projectId);
  const totalMsgs = db.prepare(`SELECT COUNT(*) AS n FROM messages WHERE project_id = ?`).get(projectId).n;

  // Code stats — call the existing /api/code-stats route over loopback (the
  // requireAuthOrLocal mount lets the request through with no token). This
  // reuses the route's repo discovery + walk logic. ~100-2000 ms on a real
  // repo; cached above for the next 5 min.
  let codeStats = null;
  try {
    const port = process.env.PORT || 6060;
    const r = await fetch(`http://127.0.0.1:${port}/api/code-stats/${projectId}`);
    if (r.ok) codeStats = await r.json();
  } catch (e) {
    // Non-fatal — Project Facts will simply omit the LOC block.
  }

  const facts = { project, repos, sources, orgSources, lastMsg, totalMsgs, codeStats };
  factsCache.set(projectId, { at: Date.now(), value: facts });
  return facts;
}

function formatFactsBlock(facts) {
  if (!facts) return null;
  const out = [];
  const p = facts.project;

  out.push('PROJECT FACTS');
  out.push(`  Name:           ${p.name}`);
  out.push(`  Path:           ${p.path}`);
  out.push(`  Model:          ${p.model || 'claude-opus-4-7 (default)'}`);
  out.push(`  Permission:     ${p.permission_mode || 'acceptEdits'}`);
  out.push(`  Created:        ${new Date((p.created_at || 0) * 1000).toISOString().slice(0, 10)}`);
  if (p.is_public) out.push(`  Visibility:     PUBLIC (shared with all users)`);

  if (facts.codeStats && (facts.codeStats.totalLines > 0 || facts.codeStats.totalFiles > 0)) {
    out.push('');
    out.push('  CODE METRICS');
    out.push(`    Total lines of code:  ${facts.codeStats.totalLines.toLocaleString()}`);
    out.push(`    Total source files:   ${facts.codeStats.totalFiles.toLocaleString()}`);
    if (facts.codeStats.specFiles) out.push(`    Test / spec files:    ${facts.codeStats.specFiles.toLocaleString()}`);
    if (facts.codeStats.byExt) {
      const tops = Object.entries(facts.codeStats.byExt).sort((a, b) => b[1] - a[1]).slice(0, 6);
      out.push(`    By extension:         ${tops.map(([k, v]) => `${k} ${v.toLocaleString()}`).join(', ')}`);
    }
    if (facts.codeStats.targets?.length) {
      out.push(`    Scanned roots:        ${facts.codeStats.targets.length}`);
      facts.codeStats.targets.slice(0, 4).forEach((t) => out.push(`      - ${t}`));
    }
  }

  out.push('');
  out.push('  REGISTERED REPOS');
  if (facts.repos.length === 0) out.push('    (none — no entries in the Repos tab)');
  else facts.repos.forEach((r) => out.push(`    - ${r.name}  ${r.path}${r.remote_url ? `  (${r.remote_url})` : ''}`));

  out.push('');
  out.push('  CONTEXT FABRIC SOURCES (project-scoped)');
  if (facts.sources.length === 0) out.push('    (none yet — visit /projects/' + p.id + '/context to add)');
  else facts.sources.forEach((s) => {
    out.push(`    - ${s.type.padEnd(14)} ${s.status.padEnd(10)} ${s.chunks} chunk${s.chunks === 1 ? '' : 's'} / ${s.docs} doc${s.docs === 1 ? '' : 's'}${s.label ? `  · ${s.label}` : ''}`);
  });

  if (facts.orgSources.length > 0) {
    out.push('');
    out.push('  CONTEXT FABRIC SOURCES (inherited from org)');
    facts.orgSources.forEach((s) => out.push(`    - ${s.type.padEnd(14)} ${s.chunks} chunk${s.chunks === 1 ? '' : 's'}${s.label ? `  · ${s.label}` : ''}`));
  }

  out.push('');
  out.push('  ACTIVITY');
  out.push(`    Total chat messages:  ${facts.totalMsgs}`);
  if (facts.lastMsg?.created_at) {
    const ago = Math.floor(Date.now() / 1000 - facts.lastMsg.created_at);
    const human = ago < 60 ? `${ago}s ago` : ago < 3600 ? `${Math.floor(ago/60)}m ago` : ago < 86400 ? `${Math.floor(ago/3600)}h ago` : `${Math.floor(ago/86400)}d ago`;
    out.push(`    Last message:         ${human}`);
  }

  return out.join('\n');
}

function buildUserMessage(question, retrieved, factsBlock) {
  const lines = [];
  if (factsBlock) {
    lines.push(factsBlock);
    lines.push('');
    lines.push('───');
    lines.push('');
  }
  if (retrieved.length > 0) {
    lines.push('CONTEXT EXCERPTS');
    lines.push('');
    retrieved.forEach((r, i) => {
      const n = i + 1;
      const docTitle = r.document.title || r.document.externalId || r.document.uri || '(untitled)';
      const sourceTag = `${r.source.type}:${r.source.scope === 'org' ? 'org' : `project#${r.source.projectId}`}`;
      lines.push(`[${n}] (${sourceTag}) ${docTitle}`);
      lines.push(r.content.trim());
      lines.push('');
    });
    lines.push('───');
    lines.push('');
  }
  lines.push(`QUESTION: ${question}`);
  return lines.join('\n');
}

/**
 * Run a Quantnik Brain query end-to-end.
 *
 * @param {{
 *   question: string,
 *   scope:    { kind:'org' } | { kind:'project', projectId: number },
 *   topK?:    number,
 *   model?:   string,
 *   userId?:  number | null,
 *   userName?: string | null,
 *   history?: Array<{ role:'user'|'assistant', content:string }>,
 *   trackUsage?: boolean,
 * }} args
 */
export async function ask({ question, scope, topK = 6, model, userId = null, userName = null, history = [], trackUsage = true }) {
  if (!question || !question.trim()) throw new Error('question required');

  // --- 1. retrieve + gather project facts in parallel ----------------------
  const t0 = Date.now();
  const projectIdForFacts = scope.kind === 'project' ? scope.projectId : null;
  const [r, facts] = await Promise.all([
    retrieve(question, scope, { topK }),
    gatherProjectFacts(projectIdForFacts),
  ]);
  const retrievedAt = Date.now();
  const factsBlock = formatFactsBlock(facts);

  // If we have neither retrieved excerpts NOR project facts (org-scope query
  // with no ingested sources), tell the user honestly. With project facts
  // available, we can still answer metadata questions even if retrieval
  // returns nothing — so we continue to Claude in that case.
  if (!r.results.length && !factsBlock) {
    return {
      answer: 'No context available for this scope yet — register sources in the Context Fabric and try again.',
      citations: [],
      retrieved: 0,
      candidateCount: r.candidateCount ?? 0,
      model:   model || process.env.WEGA_BRAIN_MODEL || DEFAULT_MODEL,
      usage:   { input_tokens: 0, output_tokens: 0 },
      costUsd: 0,
      durationMs: Date.now() - t0,
      retrievalMs: retrievedAt - t0,
    };
  }

  // --- 2. compose prompt + invoke Claude -----------------------------------
  const chosenModel = model || process.env.WEGA_BRAIN_MODEL || DEFAULT_MODEL;
  const systemPrompt = buildSystemPrompt(userName);

  // Multi-turn messages array: prior turns from `history` (sanity-trimmed),
  // then this turn's user message — which carries the Project Facts and the
  // freshly-retrieved excerpts. Putting facts+excerpts on EVERY user turn
  // (rather than once in the system prompt) keeps grounding tight across
  // long conversations even when the retrieval result differs per question.
  const trimmedHistory = Array.isArray(history)
    ? history
        .filter((m) => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string' && m.content.trim().length)
        .slice(-12) // keep at most last 12 turns to bound prompt size
    : [];
  const userMsg = buildUserMessage(question, r.results, factsBlock);
  const messages = [...trimmedHistory, { role: 'user', content: userMsg }];

  // Two-path generation: try Anthropic-direct first; on rate-limit /
  // overloaded / 5xx, fall back to Bedrock if AWS credentials are wired.
  // If Anthropic credentials aren't wired at all, go straight to Bedrock.
  // If neither is wired, surface a clear error to the route handler.
  const hasAnthropic = !!(process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_CODE_OAUTH_TOKEN);
  const hasBedrock   = !!(process.env.AWS_BEARER_TOKEN_BEDROCK || process.env.AWS_ACCESS_KEY_ID);

  if (!hasAnthropic && !hasBedrock) {
    throw new Error(
      'No LLM credential — set ANTHROPIC_API_KEY / CLAUDE_CODE_OAUTH_TOKEN ' +
      'and/or AWS_BEARER_TOKEN_BEDROCK in backend/.env. ' +
      'wega2 will use Anthropic-direct first and fall back to Bedrock on rate-limit.'
    );
  }

  let resp;
  let fellBackReason = null;
  // PRIMARY = Bedrock (Sonnet 4.6 — wega2's house default). Anthropic-direct
  // is the FALLBACK now, the reverse of the old order. If Bedrock fails for
  // a rate-limit / overload reason and Anthropic creds are present, retry
  // there. Any other error from Bedrock propagates.
  if (hasBedrock) {
    try {
      resp = await generateViaBedrock({ system: systemPrompt, messages });
    } catch (err) {
      if (hasAnthropic && isRateLimitOrOverloaded(err)) {
        fellBackReason = `bedrock ${err?.status || err?.name || 'failed'} — using Anthropic direct`;
        resp = await generateViaAnthropic({ model: chosenModel, system: systemPrompt, messages });
      } else {
        throw err;
      }
    }
  } else {
    resp = await generateViaAnthropic({ model: chosenModel, system: systemPrompt, messages });
  }

  const generationDoneAt = Date.now();
  const answerText = resp.text;

  // --- 3. cost estimate. Rates vary by platform AND model. ----------------
  // Anthropic direct: published per-million input/output rates.
  // Bedrock: same Claude model price + a thin AWS markup; we use the same
  //          numbers since the wega-brain "cost" line is directional.
  const costPerMillion = {
    'claude-opus-4-7':                                       { in: 15,   out: 75 },
    'claude-sonnet-4-6':                                     { in:  3,   out: 15 },
    'claude-haiku-4-5':                                      { in:  0.8, out:  4 },
    // Bedrock model ids (matched verbatim against resp.modelUsed)
    'us.anthropic.claude-3-7-sonnet-20250219-v1:0':          { in:  3,   out: 15 },
    'us.anthropic.claude-3-5-sonnet-20241022-v2:0':          { in:  3,   out: 15 },
    'us.anthropic.claude-3-5-haiku-20241022-v1:0':           { in:  0.8, out:  4 },
    'us.anthropic.claude-3-opus-20240229-v1:0':              { in: 15,   out: 75 },
  };
  const rate = costPerMillion[resp.modelUsed] || { in: 3, out: 15 };
  const inT  = resp.usage?.input_tokens  || 0;
  const outT = resp.usage?.output_tokens || 0;
  const costUsd = (inT * rate.in + outT * rate.out) / 1_000_000;

  // --- 4. record usage in the existing usage_events table ------------------
  if (trackUsage) {
    try {
      const projectId = scope.kind === 'project' ? scope.projectId : null;
      if (projectId) {
        const modelTag = `wega-brain:${resp.via === 'bedrock' ? 'bedrock:' : ''}${resp.modelUsed}`;
        db.prepare(`
          INSERT INTO usage_events
            (project_id, user_id, model, session_id,
             input_tokens, output_tokens,
             cache_creation_input_tokens, cache_read_input_tokens,
             total_cost_usd, duration_ms)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `).run(
          projectId, userId,
          modelTag, null,
          inT, outT,
          resp.usage?.cache_creation_input_tokens || 0,
          resp.usage?.cache_read_input_tokens     || 0,
          costUsd, Date.now() - t0,
        );
      }
    } catch (e) {
      console.warn('[wega-brain] usage_events insert failed:', e?.message);
    }
  }

  // --- 5. shape citations for the client -----------------------------------
  const citations = r.results.map((chunk, i) => ({
    n: i + 1,
    score: chunk.score,
    chunkId: chunk.chunkId,
    document: chunk.document,
    source:   chunk.source,
    preview:  chunk.content.slice(0, 280),
  }));

  return {
    answer: answerText,
    citations,
    retrieved: r.results.length,
    candidateCount: r.candidateCount ?? 0,
    model: resp.modelUsed,
    via: resp.via,                   // 'bedrock' (primary, default) | 'anthropic' (fallback)
    fellBackReason,                  // populated only when Bedrock kicked in
    usage: {
      input_tokens:  inT,
      output_tokens: outT,
      cache_creation_input_tokens: resp.usage?.cache_creation_input_tokens || 0,
      cache_read_input_tokens:     resp.usage?.cache_read_input_tokens     || 0,
    },
    costUsd,
    durationMs:   Date.now() - t0,
    retrievalMs:  retrievedAt - t0,
    generationMs: generationDoneAt - retrievedAt,
  };
}
