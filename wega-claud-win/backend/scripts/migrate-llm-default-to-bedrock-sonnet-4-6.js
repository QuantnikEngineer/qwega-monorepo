// One-shot migration: set every project's LLM to Bedrock + Sonnet 4.6.
// Wega2's house default is now Bedrock + Sonnet 4.6 (per the change in
// commit e9f63dd), but pre-existing projects keep whatever was in their
// llm_provider/llm_model columns at create time — which for older rows
// is 'anthropic' + 'claude-opus-4-7'. This script normalises them so the
// UI + the agent runtime both report Sonnet 4.6 across the workbench.
//
// Idempotent — re-running is a no-op once everything's already Sonnet 4.6.
// Per-project AWS_BEARER_TOKEN_BEDROCK overrides in llm_config are
// preserved (the bedrock branch of applyProviderEnv prefers cfg.awsBearerToken
// over the env-level value).
//
// Run: node --env-file=.env scripts/migrate-llm-default-to-bedrock-sonnet-4-6.js

import Database from 'better-sqlite3';

const TARGET_MODEL = process.env.WEGA_CHAT_BEDROCK_MODEL || 'us.anthropic.claude-sonnet-4-6';
const db = new Database('data/wega2.db');

const before = db.prepare('SELECT id, name, llm_provider, llm_model, model FROM projects ORDER BY id').all();
console.log('BEFORE:');
for (const r of before) console.log(' ', String(r.id).padStart(3), '·', String(r.name).padEnd(22), '·', String(r.llm_provider||'(null)').padEnd(10), '·', r.model || '(null)');

const stmt = db.prepare(`
  UPDATE projects
  SET llm_provider = 'bedrock',
      llm_model    = ?,
      model        = ?
`);
const r = stmt.run(TARGET_MODEL, TARGET_MODEL);
console.log('\nrows updated:', r.changes);

const after = db.prepare('SELECT id, name, llm_provider, llm_model, model FROM projects ORDER BY id').all();
console.log('\nAFTER:');
for (const row of after) console.log(' ', String(row.id).padStart(3), '·', String(row.name).padEnd(22), '·', row.llm_provider.padEnd(10), '·', row.model);
