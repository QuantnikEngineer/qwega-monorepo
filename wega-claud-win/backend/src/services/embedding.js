// Local embeddings via @xenova/transformers — pure-JS / ONNX, runs on the
// wega2 host CPU. No external embedding vendor, no API key. The model is
// downloaded once to a local cache on first use and cached on disk
// thereafter.
//
// Why local: the user's "use the Claude Code subscription LLM" intent comes
// down to not paying for a second vendor. Anthropic doesn't ship an
// embeddings API (they partner with Voyage AI), so the cleanest fit is to
// run the embedder locally and reserve Claude — via the existing wega2
// CLAUDE_CODE_OAUTH_TOKEN / ANTHROPIC_API_KEY env vars — for the generation
// side when the /ask skill is wired.
//
// Config (all via wega2 backend .env, hot-loadable):
//   EMBEDDING_MODEL          (default: Xenova/bge-base-en-v1.5)
//   EMBEDDING_DIM            (default: 768 — matches bge-base)
//   TRANSFORMERS_CACHE       (default: <backend>/data/models — where ONNX
//                              models + tokenisers get cached after first
//                              download; ~134 MB for bge-base)
//   EMBEDDING_BATCH          (default: 16 — true batch passed to the
//                              pipeline; bigger = faster but more RAM)
//
// Output: Float32Array, normalised. Same shape as the previous Bedrock
// path, so downstream services (ingest, retrieval, cosine math) didn't
// have to change.
//
// First-call latency: 10-60 sec on cold cache (model download). Subsequent
// calls: ~30-150 ms per chunk on CPU. Batches of 16 typically take
// ~500-1500 ms total — significantly faster than serial.

import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BACKEND_ROOT = path.resolve(__dirname, '..', '..');
const DEFAULT_CACHE = path.join(BACKEND_ROOT, 'data', 'models');

// Set the cache dir BEFORE we import @xenova/transformers — the library
// reads env.cacheDir on import. We can also override via env.localModelPath.
if (!process.env.TRANSFORMERS_CACHE) {
  process.env.TRANSFORMERS_CACHE = DEFAULT_CACHE;
}
fs.mkdirSync(process.env.TRANSFORMERS_CACHE, { recursive: true });

let _xform = null;          // dynamic import handle, kept hot after first call
let _pipeline = null;       // resolved feature-extraction pipeline
let _modelName = null;      // tracks the currently-loaded model
let _pipelinePromise = null; // serialises concurrent first-load calls

function readEnv() {
  return {
    model:     process.env.EMBEDDING_MODEL || 'Xenova/bge-base-en-v1.5',
    dim:       parseInt(process.env.EMBEDDING_DIM || '768', 10),
    cacheDir:  process.env.TRANSFORMERS_CACHE,
    batchSize: Math.max(1, parseInt(process.env.EMBEDDING_BATCH || '16', 10)),
  };
}

async function getXform() {
  if (_xform) return _xform;
  _xform = await import('@xenova/transformers');
  // Configure the library's cache dir + remote model behaviour.
  _xform.env.cacheDir = readEnv().cacheDir;
  _xform.env.allowLocalModels = true;
  _xform.env.allowRemoteModels = true;
  return _xform;
}

async function getPipeline() {
  const env = readEnv();
  if (_pipeline && _modelName === env.model) return _pipeline;
  if (_pipelinePromise) return _pipelinePromise;

  _pipelinePromise = (async () => {
    const { pipeline } = await getXform();
    const p = await pipeline('feature-extraction', env.model, {
      // quantized: smaller model, ~4x smaller download, minimal quality
      // hit for bge-base. Set false if you want the full FP32 weights.
      quantized: process.env.EMBEDDING_QUANTIZED !== '0',
    });
    _pipeline = p;
    _modelName = env.model;
    _pipelinePromise = null;
    return p;
  })();
  return _pipelinePromise;
}

/**
 * Embed a single text. Returns { embedding: Float32Array, tokens }.
 * The embedding is mean-pooled + L2-normalised so cosine === dot product.
 */
export async function embedText(text) {
  const p = await getPipeline();
  const out = await p(text, { pooling: 'mean', normalize: true });
  // Tensors from transformers.js have a typed-array .data field.
  return {
    embedding: Float32Array.from(out.data),
    tokens:    Math.ceil(text.length / 4),
  };
}

/**
 * Embed many texts using the pipeline's true batch support — single forward
 * pass per batch, much faster than serial calls.
 */
export async function embedBatch(texts, { concurrency /* unused locally */ } = {}) {
  if (!texts.length) return { results: [], totalTokens: 0 };
  const p = await getPipeline();
  const env = readEnv();
  const out = [];
  let totalTokens = 0;
  for (let i = 0; i < texts.length; i += env.batchSize) {
    const slice = texts.slice(i, i + env.batchSize);
    const tensor = await p(slice, { pooling: 'mean', normalize: true });
    // For batched input, the tensor shape is [batchSize, dim]; .data is a
    // flat Float32Array of length batchSize*dim. Split into per-row arrays.
    const dim = tensor.dims[tensor.dims.length - 1];
    for (let j = 0; j < slice.length; j++) {
      const embedding = Float32Array.from(tensor.data.subarray(j * dim, (j + 1) * dim));
      out.push({
        embedding,
        tokens: Math.ceil(slice[j].length / 4),
      });
      totalTokens += Math.ceil(slice[j].length / 4);
    }
  }
  return { results: out, totalTokens };
}

/** Pack a Float32Array into a SQLite-storable Buffer. */
export function floatsToBlob(f32) {
  return Buffer.from(f32.buffer, f32.byteOffset, f32.byteLength);
}

/** Inverse of floatsToBlob — read a BLOB back into a Float32Array. */
export function blobToFloats(buf) {
  return new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4);
}

/** Cosine similarity for two normalized float arrays. */
export function cosineSim(a, b) {
  let dot = 0;
  const len = Math.min(a.length, b.length);
  for (let i = 0; i < len; i++) dot += a[i] * b[i];
  return dot;
}

// Re-export model id / dim via getters so .env hot-edits are honoured.
export function getEmbeddingModel() { return readEnv().model; }
export function getEmbeddingDim()   { return readEnv().dim; }
// Back-compat constants (read at module load — don't track hot reloads).
export const EMBEDDING_MODEL = readEnv().model;
export const EMBEDDING_DIM   = readEnv().dim;

/**
 * Report the embedding backend's posture for /api/context/health.
 * Local-only — no remote credentials to misconfigure.
 *
 *   mode:    'local'
 *   ready:   true if the pipeline is loaded (model already cached)
 *   cached:  true if the model is present on disk
 *   cacheDir: where the model lives
 */
export function authMode() {
  const env = readEnv();
  // Detecting "model is cached" heuristically: transformers.js stores files
  // under <cacheDir>/<model-name-with-slashes>/. Check for the config.json
  // or onnx/ subfolder. False here means a download will happen on next
  // embed call (10-60 sec, one-time).
  const safeName = env.model.replace(/\\/g, '/');
  const modelDir = path.join(env.cacheDir, safeName);
  const cached =
    fs.existsSync(path.join(modelDir, 'config.json')) ||
    fs.existsSync(path.join(modelDir, 'onnx', 'model_quantized.onnx')) ||
    fs.existsSync(path.join(modelDir, 'onnx', 'model.onnx'));
  return {
    mode:     'local',
    ready:    !!_pipeline,
    cached,
    cacheDir: env.cacheDir,
    hint:     cached
      ? `local model "${env.model}" — cached at ${env.cacheDir}`
      : `local model "${env.model}" — first ingest will download to ${env.cacheDir} (one-time, ~134MB for bge-base)`,
  };
}

/**
 * True if the embedder is usable. For local embeddings there's no credential
 * gate — disk space + Node version is all that's required, so this is always
 * true. Kept for API compatibility with callers that previously checked
 * Bedrock creds.
 */
export function isConfigured() { return true; }
