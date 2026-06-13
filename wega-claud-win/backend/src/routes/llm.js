import { Router } from 'express';
import { db } from '../db.js';
import { writeQuantnikProjectFile } from './atlassian.js';
import { projectForRead, projectForWrite } from './projectAccess.js';

export const llm = Router();

// Provider catalog — describes what each one stores, whether the quantnik
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
    label: 'AWS Bedrock (Claude) · house default',
    wired: true,
    note: 'Claude Sonnet 4.6 via AWS Bedrock — the house default for new projects. Sets CLAUDE_CODE_USE_BEDROCK + AWS creds on the SDK process. Reads AWS_BEARER_TOKEN_BEDROCK + AWS_REGION + QUANTNIK_CHAT_BEDROCK_MODEL from the service .env.',
    defaultModel: 'us.anthropic.claude-sonnet-4-6-20251001-v1:0',
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
    note: 'Stored only — the quantnik agent runtime is built on the Claude Agent SDK which is Claude-only. Switching to OpenAI requires a different agent runtime. Config persists so it can be wired later.',
    defaultModel: 'gpt-4o',
  },
  gemini: {
    label: 'Google Gemini',
    wired: false,
    note: 'Stored only — same caveat as OpenAI. Config persists so it can be wired later.',
    defaultModel: 'gemini-2.5-flash',
  },
};

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
  const project = projectForRead(req.params.projectId, req, res);
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
  const project = projectForWrite(req.params.projectId, req, res);
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
  writeQuantnikProjectFile(row);
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
  // Default is now Bedrock (house default, Sonnet 4.6). Older projects whose
  // llm_provider column is NULL fall through to this default. Operators can
  // explicitly opt back to anthropic/vertex/foundry/etc per project from the
  // Settings panel.
  const provider = project.llm_provider || 'bedrock';
  let cfg = {};
  if (project.llm_config) {
    try { cfg = JSON.parse(project.llm_config); } catch {}
  }
  // Capture the service-wide AWS bearer + region BEFORE stripping; the
  // bedrock branch falls back to these env-level values when a project
  // has no per-project cfg.awsBearerToken (the common case now that
  // Bedrock is the default for new projects).
  const envAwsBearer = targetEnv.AWS_BEARER_TOKEN_BEDROCK || null;
  const envAwsRegion = targetEnv.AWS_REGION || null;
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
      // Strip direct-Anthropic creds so the SDK can't fall back to them.
      delete targetEnv.ANTHROPIC_API_KEY;
      delete targetEnv.CLAUDE_CODE_OAUTH_TOKEN;
      targetEnv.CLAUDE_CODE_USE_BEDROCK = '1';
      // Region: per-project cfg → env-level → us-east-1 fallback.
      targetEnv.AWS_REGION = cfg.awsRegion || envAwsRegion || 'us-east-1';
      // Bearer / IAM credentials: per-project cfg takes precedence; when
      // absent, fall back to the service-wide env-level AWS_BEARER_TOKEN_BEDROCK
      // captured above (the common case for projects using the house default).
      if (cfg.awsBearerToken) {
        // Long-term Bedrock API key (ABSK… format). Takes precedence over
        // IAM creds — and strip the IAM trio so a stale combo can't leak.
        targetEnv.AWS_BEARER_TOKEN_BEDROCK = cfg.awsBearerToken;
        delete targetEnv.AWS_ACCESS_KEY_ID;
        delete targetEnv.AWS_SECRET_ACCESS_KEY;
        delete targetEnv.AWS_SESSION_TOKEN;
      } else if (envAwsBearer) {
        // House default: env-level bearer from backend/.env. Strip IAM trio
        // for the same reason — no stale combos.
        targetEnv.AWS_BEARER_TOKEN_BEDROCK = envAwsBearer;
        delete targetEnv.AWS_ACCESS_KEY_ID;
        delete targetEnv.AWS_SECRET_ACCESS_KEY;
        delete targetEnv.AWS_SESSION_TOKEN;
      } else {
        if (cfg.awsAccessKeyId) targetEnv.AWS_ACCESS_KEY_ID = cfg.awsAccessKeyId;
        if (cfg.awsSecretAccessKey) targetEnv.AWS_SECRET_ACCESS_KEY = cfg.awsSecretAccessKey;
        if (cfg.awsSessionToken) targetEnv.AWS_SESSION_TOKEN = cfg.awsSessionToken;
      }
      return {
        wired: true,
        model: project.llm_model
            || process.env.QUANTNIK_CHAT_BEDROCK_MODEL
            || PROVIDERS.bedrock.defaultModel,
      };
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
        error: `Provider "${provider}" is not yet wired into the quantnik agent runtime (which uses the Claude Agent SDK, Claude-only). Switch the project's LLM provider back to Anthropic, Bedrock, Vertex, or Foundry to run chat turns.`,
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
    targetEnv.QUANTNIK_CHAT_BEDROCK_MODEL  ||
    targetEnv.QUANTNIK_BRAIN_BEDROCK_MODEL ||
    'us.anthropic.claude-haiku-4-5-20251001-v1:0';

  return {
    available: true,
    model,
    hint: `Bedrock fallback via ${hasBearer ? 'AWS_BEARER_TOKEN_BEDROCK' : 'AWS_ACCESS_KEY_ID'} · region ${targetEnv.AWS_REGION} · model ${model}`,
  };
}
