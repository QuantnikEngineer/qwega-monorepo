import { Router } from 'express';
import { db } from '../db.js';
import { writeWegaProjectFile } from './atlassian.js';

export const llm = Router();

// Provider catalog — describes what each one stores, whether the wega2
// agent runtime can actually use it today, and what models are typical.
// Keep this in sync with PROVIDERS in frontend/src/components/SettingsPanel.jsx.
export const PROVIDERS = {
  anthropic: {
    label: 'Anthropic (default)',
    wired: true,
    note: 'Direct Anthropic API. Uses CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY from the service .env.',
    defaultModel: 'claude-opus-4-7',
  },
  bedrock: {
    label: 'AWS Bedrock (Claude)',
    wired: true,
    note: 'Claude via AWS Bedrock. Sets CLAUDE_CODE_USE_BEDROCK + AWS creds on the SDK process.',
    defaultModel: 'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
  },
  vertex: {
    label: 'GCP Vertex AI (Claude)',
    wired: true,
    note: 'Claude via Google Vertex AI. Sets CLAUDE_CODE_USE_VERTEX + project + region.',
    defaultModel: 'claude-3-7-sonnet@20250219',
  },
  foundry: {
    label: 'Azure AI Foundry (Claude)',
    wired: true,
    note: 'Claude via Azure AI Foundry. Sets CLAUDE_CODE_USE_FOUNDRY + endpoint + key.',
    defaultModel: 'claude-opus-4-7',
  },
  openai: {
    label: 'OpenAI',
    wired: false,
    note: 'Stored only — the wega2 agent runtime is built on the Claude Agent SDK which is Claude-only. Switching to OpenAI requires a different agent runtime. Config persists so it can be wired later.',
    defaultModel: 'gpt-4o',
  },
  gemini: {
    label: 'Google Gemini',
    wired: false,
    note: 'Stored only — same caveat as OpenAI. Config persists so it can be wired later.',
    defaultModel: 'gemini-2.5-flash',
  },
};

function projectOr404(id, res) {
  const p = db.prepare('SELECT * FROM projects WHERE id = ?').get(id);
  if (!p) { res.status(404).json({ error: 'project not found' }); return null; }
  return p;
}

// Strip secrets for the GET path. Stored values stay in DB; the response
// only signals whether each secret is set, not the value.
function maskSecrets(cfg) {
  const out = { ...cfg };
  for (const k of Object.keys(out)) {
    if (/key|token|secret|password/i.test(k) && typeof out[k] === 'string' && out[k]) {
      out[k] = '••••••••' + out[k].slice(-4);
    }
  }
  return out;
}

llm.get('/:projectId', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  const provider = project.llm_provider || 'anthropic';
  let config = {};
  if (project.llm_config) {
    try { config = JSON.parse(project.llm_config); } catch {}
  }
  res.json({
    provider,
    model: project.llm_model || PROVIDERS[provider]?.defaultModel || null,
    config: maskSecrets(config),
    providers: PROVIDERS,
  });
});

llm.put('/:projectId', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  const { provider, model, config } = req.body || {};
  if (!provider || !PROVIDERS[provider]) {
    return res.status(400).json({ error: `unknown provider "${provider}" — expected one of: ${Object.keys(PROVIDERS).join(', ')}` });
  }
  // Preserve any secrets already stored when the client sends back masks.
  let existing = {};
  if (project.llm_config) {
    try { existing = JSON.parse(project.llm_config); } catch {}
  }
  const merged = { ...existing };
  if (config && typeof config === 'object') {
    for (const [k, v] of Object.entries(config)) {
      if (typeof v === 'string' && v.startsWith('••••••••')) continue; // mask placeholder
      merged[k] = v;
    }
  }
  const resolvedModel = typeof model === 'string' && model.trim()
    ? model.trim()
    : (PROVIDERS[provider].defaultModel || null);
  db.prepare(`
    UPDATE projects SET llm_provider = ?, llm_model = ?, llm_config = ?, model = ? WHERE id = ?
  `).run(
    provider,
    resolvedModel,
    Object.keys(merged).length ? JSON.stringify(merged) : null,
    resolvedModel, // mirror into legacy `model` column so the UI's read sites stay in sync
    project.id,
  );
  const row = db.prepare('SELECT * FROM projects WHERE id = ?').get(project.id);
  writeWegaProjectFile(row);
  let cfgOut = {};
  if (row.llm_config) { try { cfgOut = JSON.parse(row.llm_config); } catch {} }
  res.json({
    provider: row.llm_provider,
    model: row.llm_model,
    config: maskSecrets(cfgOut),
    providers: PROVIDERS,
  });
});

// Apply the provider's env vars to a target env object. Used by session.js
// to prepare the SDK call. Returns true if the provider is wired and the
// env was successfully prepared; false if the provider is config-only.
export function applyProviderEnv(project, targetEnv) {
  const provider = project.llm_provider || 'anthropic';
  let cfg = {};
  if (project.llm_config) {
    try { cfg = JSON.parse(project.llm_config); } catch {}
  }
  // Always strip prior provider envs so a stale earlier-call state can't leak.
  delete targetEnv.CLAUDE_CODE_USE_BEDROCK;
  delete targetEnv.CLAUDE_CODE_USE_VERTEX;
  delete targetEnv.CLAUDE_CODE_USE_FOUNDRY;
  delete targetEnv.AWS_BEARER_TOKEN_BEDROCK;
  delete targetEnv.ANTHROPIC_VERTEX_PROJECT_ID;
  delete targetEnv.CLOUD_ML_REGION;
  delete targetEnv.ANTHROPIC_API_URL;

  switch (provider) {
    case 'anthropic':
      // Per-project Anthropic key overrides the service-wide .env value.
      // Also strip CLAUDE_CODE_OAUTH_TOKEN so the SDK uses the explicit key,
      // not whichever credential the OAuth token resolved to.
      if (cfg.anthropicApiKey) {
        targetEnv.ANTHROPIC_API_KEY = cfg.anthropicApiKey;
        delete targetEnv.CLAUDE_CODE_OAUTH_TOKEN;
      }
      return { wired: true, model: project.llm_model || PROVIDERS.anthropic.defaultModel };
    case 'bedrock':
      targetEnv.CLAUDE_CODE_USE_BEDROCK = '1';
      if (cfg.awsRegion) targetEnv.AWS_REGION = cfg.awsRegion;
      if (cfg.awsBearerToken) {
        // Long-term Bedrock API key (ABSK… format). Takes precedence over
        // IAM creds — and strip the IAM trio so a stale combo can't leak.
        targetEnv.AWS_BEARER_TOKEN_BEDROCK = cfg.awsBearerToken;
        delete targetEnv.AWS_ACCESS_KEY_ID;
        delete targetEnv.AWS_SECRET_ACCESS_KEY;
        delete targetEnv.AWS_SESSION_TOKEN;
      } else {
        if (cfg.awsAccessKeyId) targetEnv.AWS_ACCESS_KEY_ID = cfg.awsAccessKeyId;
        if (cfg.awsSecretAccessKey) targetEnv.AWS_SECRET_ACCESS_KEY = cfg.awsSecretAccessKey;
        if (cfg.awsSessionToken) targetEnv.AWS_SESSION_TOKEN = cfg.awsSessionToken;
      }
      return { wired: true, model: project.llm_model || PROVIDERS.bedrock.defaultModel };
    case 'vertex':
      targetEnv.CLAUDE_CODE_USE_VERTEX = '1';
      if (cfg.gcpProjectId) targetEnv.ANTHROPIC_VERTEX_PROJECT_ID = cfg.gcpProjectId;
      if (cfg.gcpRegion) targetEnv.CLOUD_ML_REGION = cfg.gcpRegion;
      if (cfg.googleApplicationCredentials) targetEnv.GOOGLE_APPLICATION_CREDENTIALS = cfg.googleApplicationCredentials;
      return { wired: true, model: project.llm_model || PROVIDERS.vertex.defaultModel };
    case 'foundry':
      targetEnv.CLAUDE_CODE_USE_FOUNDRY = '1';
      if (cfg.azureEndpoint) targetEnv.ANTHROPIC_API_URL = cfg.azureEndpoint;
      if (cfg.azureApiKey) targetEnv.ANTHROPIC_API_KEY = cfg.azureApiKey;
      return { wired: true, model: project.llm_model || PROVIDERS.foundry.defaultModel };
    case 'openai':
    case 'gemini':
      return {
        wired: false,
        error: `Provider "${provider}" is not yet wired into the wega2 agent runtime (which uses the Claude Agent SDK, Claude-only). Switch the project's LLM provider back to Anthropic, Bedrock, Vertex, or Foundry to run chat turns.`,
      };
    default:
      return { wired: false, error: `Unknown provider: ${provider}` };
  }
}

// Force the spawn env onto the Bedrock path, ignoring whatever the project's
// configured provider says. Used by session.js as a runtime fallback when the
// primary provider throws a rate-limit / overloaded error. Service-wide AWS
// creds in .env (AWS_BEARER_TOKEN_BEDROCK or the IAM access-key trio) carry
// the auth. Returns { available, model, hint } so the caller can decide
// whether the fallback is even possible.
export function applyBedrockFallbackEnv(targetEnv) {
  const hasBearer = !!targetEnv.AWS_BEARER_TOKEN_BEDROCK;
  const hasKey    = !!(targetEnv.AWS_ACCESS_KEY_ID && targetEnv.AWS_SECRET_ACCESS_KEY);
  if (!hasBearer && !hasKey) {
    return { available: false, hint: 'No AWS creds in env — set AWS_BEARER_TOKEN_BEDROCK or AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY in backend/.env' };
  }

  // Strip every NON-Bedrock provider marker so the SDK doesn't reach for
  // Anthropic-direct again on the retry.
  delete targetEnv.CLAUDE_CODE_USE_VERTEX;
  delete targetEnv.CLAUDE_CODE_USE_FOUNDRY;
  delete targetEnv.ANTHROPIC_API_URL;
  delete targetEnv.ANTHROPIC_VERTEX_PROJECT_ID;
  delete targetEnv.CLOUD_ML_REGION;
  delete targetEnv.GOOGLE_APPLICATION_CREDENTIALS;
  // Drop direct-Anthropic auth so the SDK can't fall back to it.
  delete targetEnv.ANTHROPIC_API_KEY;
  delete targetEnv.CLAUDE_CODE_OAUTH_TOKEN;

  targetEnv.CLAUDE_CODE_USE_BEDROCK = '1';
  if (!targetEnv.AWS_REGION) targetEnv.AWS_REGION = 'us-east-1';

  // Model cascade: chat-specific env var → BRAIN's var (shared default) →
  // known-good fallback. Haiku 4.5 has been verified live on the test
  // account's Bedrock; safer than older Sonnet ids that are now retired.
  const model =
    targetEnv.WEGA_CHAT_BEDROCK_MODEL  ||
    targetEnv.WEGA_BRAIN_BEDROCK_MODEL ||
    'us.anthropic.claude-haiku-4-5-20251001-v1:0';

  return {
    available: true,
    model,
    hint: `Bedrock fallback via ${hasBearer ? 'AWS_BEARER_TOKEN_BEDROCK' : 'AWS_ACCESS_KEY_ID'} · region ${targetEnv.AWS_REGION} · model ${model}`,
  };
}
