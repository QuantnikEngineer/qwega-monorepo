import Database from 'better-sqlite3';
import { config } from './config.js';

export const db = new Database(config.dbPath);
// DELETE journal mode (not WAL): the DB lives on a GCS Fuse mount in
// deployment, which does not support the shared-memory fcntl calls WAL needs.
db.pragma('journal_mode = DELETE');

db.exec(`
  CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    path TEXT NOT NULL,
    model TEXT DEFAULT 'claude-opus-4-7[1m]',
    permission_mode TEXT DEFAULT 'acceptEdits',
    last_session_id TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
  );

  -- Auth: users + sessions. Email is the unique identity; registration is
  -- gated to @wipro.com domains in the route handler. Sessions store an
  -- opaque token (32 bytes hex) with a TTL — clients send it in the
  -- Authorization header or as a query param on the WS upgrade.
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    last_login_at INTEGER
  );

  CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    expires_at INTEGER NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

  CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
  );

  CREATE INDEX IF NOT EXISTS idx_messages_project ON messages(project_id, id);

  CREATE TABLE IF NOT EXISTS project_repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    remote_url TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
  );

  CREATE INDEX IF NOT EXISTS idx_project_repos_project ON project_repos(project_id);
`);

// Lightweight migrations — additive columns only.
function ensureColumn(table, column, ddl) {
  const cols = db.prepare(`PRAGMA table_info(${table})`).all();
  if (!cols.find((c) => c.name === column)) {
    db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${ddl}`);
  }
}

ensureColumn('projects', 'jira_project_key', 'TEXT');
ensureColumn('projects', 'confluence_space_id', 'TEXT');
ensureColumn('projects', 'confluence_space_key', 'TEXT');
ensureColumn('projects', 'atlassian_labels', 'TEXT'); // JSON-encoded string[]

// LLM provider — defaults to Anthropic; Bedrock/Vertex/Foundry route Claude
// through alt clouds; OpenAI/Gemini store config but are not yet wired into
// the wega2 agent runtime (which uses the Claude Agent SDK).
ensureColumn('projects', 'llm_provider', "TEXT DEFAULT 'anthropic'");
ensureColumn('projects', 'llm_model', 'TEXT');
ensureColumn('projects', 'llm_config', 'TEXT'); // JSON blob — provider-specific fields

// Project ownership. NULL means "legacy / un-owned"; the first registered
// user inherits every NULL row via a one-shot claim in routes/auth.js.
// New projects get the creating user's id on POST /api/projects.
ensureColumn('projects', 'owner_user_id', 'INTEGER REFERENCES users(id) ON DELETE SET NULL');

// Shared projects. is_public = 1 makes a project visible in every user's
// project list and grants every authenticated user read + chat + file +
// skill access. Destructive operations (PATCH/DELETE/reset-session) still
// require ownership — see ownProjectOr404 vs accessibleProjectOr404 in
// routes/projects.js.
ensureColumn('projects', 'is_public', 'INTEGER DEFAULT 0');

// One-shot data migration: project "Mobile" is a shared workspace.
// Idempotent — re-running this on every startup is a no-op once set.
// Case-insensitive name match so "mobile" / "Mobile" / "MOBILE" all hit.
try {
  db.prepare(`UPDATE projects SET is_public = 1
              WHERE LOWER(name) = 'mobile' AND (is_public IS NULL OR is_public = 0)`).run();
} catch (e) {
  console.warn('[db] mobile-public migration:', e?.message);
}

// Admin flag on users. is_admin = 1 unlocks /api/admin/* endpoints and the
// Admin section inside the SettingsPanel. Owner-equivalent at the route
// level — admins can see *everyone's* projects, users, and token spend, but
// they don't bypass per-project ownership for destructive operations
// (rename/delete/reset still require being the project owner).
ensureColumn('users', 'is_admin', 'INTEGER DEFAULT 0');

// One-shot data migration: the wega2 administrator. Same idempotent
// pattern as the Mobile project. Case-insensitive email match.
try {
  db.prepare(`UPDATE users SET is_admin = 1
              WHERE LOWER(email) = 'abhinav.krishna@wipro.com'
                AND (is_admin IS NULL OR is_admin = 0)`).run();
} catch (e) {
  console.warn('[db] admin-flag migration:', e?.message);
}

// Per-turn usage capture. One row per agent turn — the SDK emits a `result`
// event at the end of each turn with the total cost and final usage block.
// The streaming usage_update / stream_event ticks are not persisted (would
// be 10-100× per turn, and ws.js explicitly classifies them as EPHEMERAL).
//
// user_id is FK to users; NULL is allowed if the user is deleted, so the
// audit trail survives account removal (we can still see "user X spent $Y
// before being deleted" rolled into the projects view).
db.exec(`
  CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    model TEXT,
    session_id TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cache_creation_input_tokens INTEGER DEFAULT 0,
    cache_read_input_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0,
    duration_ms INTEGER,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
  );

  CREATE INDEX IF NOT EXISTS idx_usage_events_project ON usage_events(project_id);
  CREATE INDEX IF NOT EXISTS idx_usage_events_user    ON usage_events(user_id);
  CREATE INDEX IF NOT EXISTS idx_usage_events_created ON usage_events(created_at);
`);

// ───────────────────────────────────────────────────────────────────────────
// Context Fabric — the RAG knowledge layer
// ───────────────────────────────────────────────────────────────────────────
// Three tables back the Context Fabric tab:
//
//   context_sources    one row per registered input (a repo, a website, an
//                      uploaded document, a Confluence space, etc.). Has
//                      scope=org|project + type + JSON config. Carries ingest
//                      status, last-ingested timestamp, doc/chunk/token counts.
//
//   context_documents  one row per logical document materialised from a source
//                      — e.g. a file inside a repo, a single fetched web page,
//                      a Confluence page, an uploaded PDF. Holds the title +
//                      content hash so we can skip re-embedding unchanged docs.
//
//   context_chunks     the embedded units. content + embedding BLOB (1024-dim
//                      float32 from Bedrock Titan v2). In-memory cosine search
//                      for v1; trivial to swap for sqlite-vec / pgvector when
//                      scale demands it. The embedding column being part of
//                      the relational row keeps the migration path simple.
db.exec(`
  CREATE TABLE IF NOT EXISTS context_sources (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    scope            TEXT NOT NULL CHECK (scope IN ('org','project')),
    project_id       INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    type             TEXT NOT NULL CHECK (type IN
                       ('repo','document','website','confluence','sharepoint','agent_output')),
    config           TEXT NOT NULL DEFAULT '{}',
    label            TEXT,
    status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN
                       ('pending','ingesting','ready','failed','disabled')),
    error            TEXT,
    last_ingested_at INTEGER,
    document_count   INTEGER DEFAULT 0,
    chunk_count      INTEGER DEFAULT 0,
    total_tokens     INTEGER DEFAULT 0,
    added_by         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at       INTEGER DEFAULT (strftime('%s','now')),
    updated_at       INTEGER DEFAULT (strftime('%s','now')),
    CHECK ((scope='org' AND project_id IS NULL) OR
           (scope='project' AND project_id IS NOT NULL))
  );

  CREATE INDEX IF NOT EXISTS idx_context_sources_scope    ON context_sources(scope, project_id);
  CREATE INDEX IF NOT EXISTS idx_context_sources_status   ON context_sources(status);
  CREATE INDEX IF NOT EXISTS idx_context_sources_type     ON context_sources(type);

  CREATE TABLE IF NOT EXISTS context_documents (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    INTEGER NOT NULL REFERENCES context_sources(id) ON DELETE CASCADE,
    external_id  TEXT,
    title        TEXT,
    uri          TEXT,
    content_hash TEXT,
    char_count   INTEGER,
    token_count  INTEGER,
    created_at   INTEGER DEFAULT (strftime('%s','now'))
  );

  CREATE INDEX IF NOT EXISTS idx_context_documents_source ON context_documents(source_id);

  CREATE TABLE IF NOT EXISTS context_chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES context_documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    content      TEXT NOT NULL,
    token_count  INTEGER,
    start_char   INTEGER,
    end_char     INTEGER,
    embedding    BLOB,
    created_at   INTEGER DEFAULT (strftime('%s','now'))
  );

  CREATE INDEX IF NOT EXISTS idx_context_chunks_document  ON context_chunks(document_id);
`);

// Deployments — the deploy-to-platform skill writes here. Each row is one
// deployed app served by wega2 at /<slug>. Backend (if present) is a child
// process bound to a wega2-allocated port; /<slug>/api/* is reverse-proxied
// to it. status='running' deployments are re-spawned on wega2 startup.
db.exec(`
  CREATE TABLE IF NOT EXISTS deployments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    slug TEXT NOT NULL UNIQUE,
    frontend_path TEXT NOT NULL,
    backend_path TEXT,
    backend_port INTEGER,
    backend_start_cmd TEXT,
    backend_start_args TEXT,
    backend_env TEXT,
    status TEXT DEFAULT 'pending',
    pid INTEGER,
    url TEXT NOT NULL,
    log_path TEXT,
    deployed_at INTEGER DEFAULT (strftime('%s', 'now')),
    last_started_at INTEGER
  );

  CREATE INDEX IF NOT EXISTS idx_deployments_project ON deployments(project_id);

  -- Orchestrator phase state. Server-authoritative replacement for client-
  -- side message parsing. Skills POST each phase transition; the panel
  -- reads from here so accuracy doesn't depend on the agent emitting
  -- well-formed text. One row per (project, phase number).
  CREATE TABLE IF NOT EXISTS project_phases (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase_number INTEGER NOT NULL,
    name TEXT,
    status TEXT NOT NULL,
    note TEXT,
    started_at INTEGER,
    updated_at INTEGER DEFAULT (strftime('%s', 'now')),
    PRIMARY KEY (project_id, phase_number)
  );
`);
