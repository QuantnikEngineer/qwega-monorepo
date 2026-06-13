---
name: sdlc-tokenomics
description: Given a requirement document uploaded via the Files tab, produces a phase-by-phase model-mapping table for the 11-phase sdlc-orchestrator workflow (BRD → User Stories → Feature Dev → Vulnerability Check → Tech Debt Check → Test Cases → Test Scripts → Boot → Test Execution → Deployment → Sanity Check). For each phase the skill picks the best-fit LLM from a catalog of commonly available models (Claude Opus/Sonnet/Haiku, GPT-4.1/4o/4o-mini/o1/o1-mini/o3-mini, Gemini 2.0 Flash/1.5 Pro/Flash/Flash-8b, Llama 3.x, DeepSeek V3/R1, Mistral Large, Grok-3), estimates input + output tokens given the document's size and the phase's typical work profile, computes per-phase cost, and rolls up to a total project cost. The optimisation target is best-quality output per dollar: heavy-reasoning phases (BRD generation, Test Case design, Feature Dev synthesis) route to frontier models; structured-text phases (User Stories, Tech Debt) route to mid-tier models; repetitive formatting/validation/summarisation phases (Boot, Deployment) route to fast cheap models. Output: a markdown table + a one-paragraph recommendation explaining the trade-offs. Invoke as /sdlc-tokenomics after uploading the requirement document via the Files tab.
---

When invoked, follow the steps below in order. Halt only when a guardrail trips — otherwise run autonomously and surface the table + recommendation in a single message at the end.

**Objective:** best results at the optimal price point. Pick frontier models for steps where reasoning quality changes the output materially (BRD shape, test coverage, code architecture). Pick fast cheap models for steps where the work is mechanical or where the failure mode is "slightly less polished prose" rather than "wrong answer". Justify each pick. Add the numbers up so the user can see where their money goes.

---

## Step 0 — Get the requirement document

1. `Glob` `uploads/*` from the project cwd. The cwd is the project root; `uploads/` is a sibling (also check `../uploads/*` if the first pattern returns nothing — different deployments lay this out differently).
2. If multiple files match, pick the **most recently uploaded** — the quantnik upload route prepends a `<unix-timestamp>-` to every stored filename, so a descending sort by name puts the newest first.
3. If zero files found, halt with this exact message:

   > No file in `uploads/`. Upload the requirement document via the **Files** tab (the `[ + ]` upload button), then re-run `/sdlc-tokenomics`.

4. Ingest the file based on extension:

   | Extension | How |
   |---|---|
   | `.txt`, `.md` | `Read` the file directly |
   | `.pdf` | `Read` with the `pages` parameter. For PDFs > 10 pages, paginate in 20-page chunks until the whole document is read. |
   | `.docx` | Convert first: `Bash` `pandoc <path> -t plain -o /tmp/req_<n>.txt` (or `textutil -convert txt` on macOS), then `Read` the converted file. |
   | `.png`, `.jpg`, `.jpeg`, `.webp` | `Read` — image content is presented visually. Transcribe visible text + extract wireframe / flow elements into a structured outline. |
   | anything else | halt: *"Unsupported file type for tokenomics analysis. Use .txt, .md, .pdf, .docx, or an image."* |

Cache the ingested text in run-context. You need both the character count and a structural sense of the document to estimate complexity in Step 1.

---

## Step 1 — Size and classify the document

Compute three numbers and one label:

- `char_count` = length of the ingested text in characters
- `doc_input_tokens` ≈ `round(char_count / 4)` — Anthropic/OpenAI/Google tokenizers all sit within ~10-15% of `chars/4` on English prose, which is precision enough for budget estimates
- `word_count` ≈ `chars / 5.5` — useful for the report header
- `complexity` = one of `simple` / `medium` / `complex`, computed from the signals below

**Complexity scoring (count hits → bucket):**

| Signal in the document | Hits |
|---|---|
| Mentions API contracts (OpenAPI, REST endpoints, GraphQL schema), data models, ERDs, sequence diagrams | +1 |
| Lists ≥ 10 distinct user-facing features / screens / workflows | +1 |
| Each external integration mentioned (payments, auth provider, SMS, email, analytics, ERP) | +1 per integration |
| Explicit non-functional requirements (perf SLAs, compliance — PCI/HIPAA/SOC2/GDPR, accessibility level) | +1 each (cap at +2) |
| Multi-tenancy, role-based access, audit trails | +1 |
| Mobile + web + offline-capable | +1 |

Bucket: `0–1` = **simple**, `2–4` = **medium**, `≥5` = **complex**.

Complexity drives both the **output-token midpoint** (longer artifacts on complex projects) and the **routing aggressiveness** (a simple project doesn't need Opus for every phase).

---

## Step 2 — Model catalog (pricing reference)

Use this catalog. Prices are **USD per 1 million tokens** (input / output), last refreshed **January 2026**.

| Family | Model id (display) | $/M input | $/M output | Sweet spot |
|---|---|---|---|---|
| Anthropic | Claude Opus 4.7 (1M ctx) | 15.00 | 75.00 | deep reasoning, long context, agentic flows |
| Anthropic | Claude Sonnet 4.6 | 3.00 | 15.00 | balanced reasoning, coding, default workhorse |
| Anthropic | Claude Haiku 4.5 | 0.80 | 4.00 | fast structured generation, summarisation |
| OpenAI | GPT-4.1 | 2.00 | 8.00 | strong general-purpose, slightly cheaper than Opus |
| OpenAI | GPT-4o | 2.50 | 10.00 | multimodal, general-purpose |
| OpenAI | GPT-4o-mini | 0.15 | 0.60 | cheap, fast, high-volume utility |
| OpenAI | o1 | 15.00 | 60.00 | hard reasoning + math (slow) |
| OpenAI | o1-mini | 3.00 | 12.00 | mid-tier reasoning |
| OpenAI | o3-mini | 1.10 | 4.40 | newer reasoning, cheaper than o1-mini |
| Google | Gemini 1.5 Pro | 1.25 | 5.00 | very long context (1–2M), good reasoning |
| Google | Gemini 2.0 Flash | 0.10 | 0.40 | very cheap, multimodal, fast |
| Google | Gemini 1.5 Flash | 0.075 | 0.30 | very cheap structured outputs |
| Google | Gemini 1.5 Flash-8b | 0.0375 | 0.15 | absolute cheapest viable production model |
| Meta | Llama 3.3 70B (Together/Groq) | 0.60 | 0.60 | open-weight, mid-tier reasoning |
| Meta | Llama 3.1 405B (Together) | 3.50 | 3.50 | open-weight frontier-class |
| Mistral | Mistral Large 2 | 2.00 | 6.00 | EU-hosted, code-strong |
| DeepSeek | DeepSeek V3 | 0.27 | 1.10 | very cheap general-purpose |
| DeepSeek | DeepSeek R1 | 0.55 | 2.19 | very cheap reasoning |
| xAI | Grok-3 | 5.00 | 15.00 | recent training data + web search |

Treat these as directional. Real-world API rates shift, and bulk-commit / enterprise contracts can adjust them ±50%. Note in the output that the prices are January 2026 and advise the user to verify against vendor pages before committing budget.

---

## Step 3 — Per-phase work profile

For every phase from the `sdlc-orchestrator` workflow, the work profile (input multiplier, output token range) is:

| # | Phase                  | Skill that runs it       | Reasoning depth   | Input mult. (× doc tokens) | Output tokens (simple / medium / complex) |
|---|------------------------|--------------------------|-------------------|---------------------------:|-------------------------------------------|
| 1 | BRD                    | sdlc-planning            | **high**          | 1.0                        |   6,000 /  9,000 / 12,000                 |
| 2 | User Stories           | user-stories             | medium-high       | 2.5  (BRD becomes input)   |   8,000 / 12,000 / 15,000                 |
| 3 | Feature Dev            | feature-dev              | **high**          | 3.0                        |  40,000 / 60,000 / 80,000  (code)         |
| 4 | Vulnerability Check    | vulnerability-check      | low-medium        | 1.5                        |   3,000 /  4,500 /  6,000                 |
| 5 | Tech Debt Check        | tech-debt-check          | medium            | 2.0                        |   4,000 /  6,000 /  8,000                 |
| 6 | Test Cases             | test-case-generator      | **high**          | 3.0                        |  12,000 / 18,000 / 25,000                 |
| 7 | Test Scripts           | test-script-generator    | medium-high       | 2.0                        |  20,000 / 30,000 / 40,000  (Playwright)   |
| 8 | Boot                   | (orchestrator)           | low               | 1.5                        |   2,000 /  3,000 /  4,000                 |
| 9 | Test Execution         | test-script-executor     | low-medium        | 3.0  (failing test stacks) |   4,000 /  6,000 /  8,000                 |
| 10| Deployment             | deploy-to-platform       | low               | 1.5                        |   2,000 /  3,000 /  4,000                 |
| 11| Sanity Check           | sanity-check             | medium            | 2.5                        |   4,000 /  6,000 /  8,000                 |

These multipliers assume the agent re-ingests the BRD + earlier artifacts as input on later phases — that's why the multiplier climbs above 1.0 even though the source doc didn't grow. Phase 9's input multiplier accounts for failing-test stack traces, which the agent has to read in full.

Phase 3 (Feature Dev) and Phase 7 (Test Scripts) output code, not prose — tokens per artifact are 3-5× higher than text-only phases.

---

## Step 4 — Routing matrix (by reasoning depth)

| Reasoning depth | **Primary** (default pick) | Secondary | Cheap alternative (only if budget-constrained) |
|---|---|---|---|
| **high**        | Claude Opus 4.7    | GPT-4.1, Gemini 1.5 Pro          | Claude Sonnet 4.6, DeepSeek R1   |
| medium-high     | Claude Sonnet 4.6  | GPT-4o, Gemini 1.5 Pro           | Llama 3.3 70B, DeepSeek V3        |
| medium          | Claude Sonnet 4.6  | GPT-4o, GPT-4.1                  | Gemini 2.0 Flash, DeepSeek V3     |
| low-medium      | Claude Haiku 4.5   | GPT-4o-mini, o3-mini             | Gemini 1.5 Flash                  |
| **low**         | Claude Haiku 4.5   | GPT-4o-mini, Gemini 2.0 Flash    | Gemini 1.5 Flash-8b               |

**Default mapping for the 11 phases** (best-quality-per-dollar — what you should pick unless the user asks to optimise differently):

| # | Phase             | Recommended model     | Why                                                                 |
|---|-------------------|-----------------------|---------------------------------------------------------------------|
| 1 | BRD               | Claude Opus 4.7       | shape of the BRD downstream-affects every subsequent phase          |
| 2 | User Stories      | Claude Sonnet 4.6     | structured decomposition; Sonnet is the proven workhorse            |
| 3 | Feature Dev       | Claude Opus 4.7       | code architecture matters; Opus produces cleaner scaffolding        |
| 4 | Vulnerability     | Claude Haiku 4.5      | scanning is shallow; speed > depth                                  |
| 5 | Tech Debt         | Claude Sonnet 4.6     | hotspot ranking needs some judgement, not deep reasoning            |
| 6 | Test Cases        | Claude Opus 4.7       | coverage gaps later become production bugs — spend here             |
| 7 | Test Scripts      | Claude Sonnet 4.6     | Playwright code is templated; Sonnet handles it cleanly             |
| 8 | Boot              | Gemini 2.0 Flash      | install commands + health check; trivial structured outputs         |
| 9 | Test Execution    | Claude Haiku 4.5      | parsing TRX + Jira-formatting; structured                           |
| 10| Deployment        | Gemini 2.0 Flash      | manifest YAML + slug routing; trivial                               |
| 11| Sanity Check      | Claude Sonnet 4.6     | maps probe results to stories; needs context but not deep reasoning |

If the user has asked for a **budget profile**, swap as follows:
- **Cost-optimised:** Phase 1/3/6 → Claude Sonnet 4.6 (saves ~40-50% on the heavy phases). Quality drops modestly on BRD shape and test coverage edge cases.
- **Quality-maximised:** Phase 2/5/11 → Claude Opus 4.7. Marginal gains; usually not worth the spend.
- **Multi-vendor:** mirror Anthropic picks to GPT-4.1 (high), GPT-4o (medium), GPT-4o-mini (low) for the Anthropic-skeptical path.

---

## Step 5 — Compute the per-phase numbers

For each of the 11 phases:

1. `phase_input_tokens = round(doc_input_tokens × phase_multiplier)` (from Step 3)
2. `phase_output_tokens = output_midpoint_for_complexity` (from Step 3 — pick the simple/medium/complex column matching Step 1)
3. `phase_input_cost  = (phase_input_tokens  / 1_000_000) × model_input_price`
4. `phase_output_cost = (phase_output_tokens / 1_000_000) × model_output_price`
5. `phase_cost = phase_input_cost + phase_output_cost`

Sum across all 11 phases: `total_cost = Σ phase_cost`.

Round costs to 2 decimal places (cents). Use exact integer tokens — no rounding inside the calculation.

---

## Step 6 — Render the table

Output exactly this shape so the quantnik chat panel renders it cleanly:

```
## SDLC Tokenomics for `<source filename>`

Document: <char_count> chars · ~<doc_input_tokens> tokens · complexity = <simple|medium|complex>
Prices last refreshed: January 2026 · figures are directional (±30%)

| #  | Phase                  | Recommended model     | Input tok | Output tok | Cost (USD) |
|----|------------------------|-----------------------|----------:|-----------:|-----------:|
| 1  | BRD                    | Claude Opus 4.7       |    10,000 |      9,000 |      $0.83 |
| 2  | User Stories           | Claude Sonnet 4.6     |    25,000 |     12,000 |      $0.26 |
| 3  | Feature Dev            | Claude Opus 4.7       |    30,000 |     60,000 |      $4.95 |
| 4  | Vulnerability Check    | Claude Haiku 4.5      |    15,000 |      4,500 |      $0.03 |
| 5  | Tech Debt Check        | Claude Sonnet 4.6     |    20,000 |      6,000 |      $0.15 |
| 6  | Test Cases             | Claude Opus 4.7       |    30,000 |     18,000 |      $1.80 |
| 7  | Test Scripts           | Claude Sonnet 4.6     |    20,000 |     30,000 |      $0.51 |
| 8  | Boot                   | Gemini 2.0 Flash      |    15,000 |      3,000 |      $0.00 |
| 9  | Test Execution         | Claude Haiku 4.5      |    30,000 |      6,000 |      $0.05 |
| 10 | Deployment             | Gemini 2.0 Flash      |    15,000 |      3,000 |      $0.00 |
| 11 | Sanity Check           | Claude Sonnet 4.6     |    25,000 |      6,000 |      $0.17 |
|----|------------------------|-----------------------|----------:|-----------:|-----------:|
|    | **TOTAL**              |                       |   235,000 |    157,500 |  **$8.75** |
```

Token counts are illustrative — substitute the real computed values. Always include the TOTAL row.

After the table, render this paragraph (substitute the real numbers and the actual top-3 phases by cost):

> **Recommendation.** Estimated end-to-end spend for this project is **$<total>**, of which **<phases X / Y / Z>** account for **~<pct>%**. That concentration is intentional — those are the phases where model-quality directly shapes the output downstream. If budget is the binding constraint, the cheapest viable substitution is **Phase 3 (Feature Dev) → Claude Sonnet 4.6** (~$<delta> saved, modest architecture-quality penalty) followed by **Phase 6 (Test Cases) → Claude Sonnet 4.6** (~$<delta> saved, slightly thinner edge-case coverage). Phases 8 and 10 are already at the cost floor with Gemini 2.0 Flash — don't downgrade further; Gemini Flash-8b introduces a quality cliff on structured outputs. The figures are directional (±30%): real spend will vary with retry loops, prompt-engineering overhead, and any iterative refinement the agent does mid-phase.

---

## Step 7 — Persist the report (always run)

The skill writes the report in three formats. None of them block the chat reply; failures in one path don't stop the others.

### 7a — Markdown (always)

Always write to `<repo-root>/SDLC_TOKENOMICS_<YYYY-MM-DD>.md` so the report travels with the project regardless of UI surface.

### 7b — Excel workbook (.xlsx) in the **Files** tab (always)

Write a multi-sheet Excel file into the project's `uploads/` folder so it appears in the quantnik **Files** tab alongside the source requirement document. Three sheets: **Summary** (project + doc + complexity + total cost), **Phase mapping** (the 11 phases with model + tokens + cost + rationale + a TOTAL row), and **Model catalog** (the price reference table from Step 2).

**Naming convention.** quantnik's upload route prepends `<unix-timestamp-ms>-` to every stored file, and the FilesPanel strips that prefix when displaying the name. Mirror that convention so your generated file lists cleanly:

```
uploads/<13-digit-ms>-sdlc-tokenomics-<YYYY-MM-DD>.xlsx
       ^^^^^^^^^^^^^                                  ← display strips this prefix → user sees `sdlc-tokenomics-<YYYY-MM-DD>.xlsx`
```

**How to write it.** The skill folder ships with `xlsx-generator.js` (sibling of this SKILL.md). It reads a JSON payload from stdin and writes the workbook to the path given as `argv[2]`. Invoke it with `NODE_PATH` pointing at the quantnik backend's `node_modules` (where the `exceljs` dependency lives).

```bash
# 1. Resolve the quantnik backend dir (where exceljs is installed)
QUANTNIK_BE="${QUANTNIK_BACKEND:-}"
if [ ! -d "$QUANTNIK_BE/node_modules/exceljs" ]; then
  for candidate in "$PWD/backend" "$PWD" "$(git rev-parse --show-toplevel 2>/dev/null)/backend"; do
    if [ -d "$candidate/node_modules/exceljs" ]; then QUANTNIK_BE="$candidate"; break; fi
  done
fi
if [ ! -d "$QUANTNIK_BE/node_modules/exceljs" ]; then
  # Last-resort fallback: install into a tempdir once and reuse.
  TMP="$HOME/.cache/quantnik-tokenomics-deps"
  if [ ! -d "$TMP/node_modules/exceljs" ]; then
    mkdir -p "$TMP" && (cd "$TMP" && npm install --silent --no-audit --no-fund exceljs)
  fi
  QUANTNIK_BE="$TMP"
fi

# 2. Build the output path (13-digit ms timestamp matches quantnik upload route)
TS=$(node -e "console.log(Date.now())")
DATE=$(date +%Y-%m-%d)
mkdir -p "$PWD/uploads"
OUT="$PWD/uploads/${TS}-sdlc-tokenomics-${DATE}.xlsx"

# 3. Find the bundled generator (sibling of this SKILL.md)
GEN="$HOME/.claude/skills/sdlc-tokenomics/xlsx-generator.js"
[ -f "$GEN" ] || GEN="$(dirname "$0")/xlsx-generator.js"  # fallback if invoked differently

# 4. Pipe the JSON data into the generator. The JSON shape is documented below.
NODE_PATH="$QUANTNIK_BE/node_modules" node "$GEN" "$OUT" <<'JSON'
{
  "project": "<project name>",
  "document": "<source filename from uploads/>",
  "char_count": 38400,
  "doc_input_tokens": 9600,
  "complexity": "medium",
  "generated_at": "2026-05-26 12:18",
  "total_input": 240400,
  "total_output": 158500,
  "total_cost": 8.77,
  "phases": [
    { "phase_n":  1, "phase": "BRD",                 "model": "Claude Opus 4.7",   "input_tokens":  9600, "output_tokens":  9000, "cost": 0.82, "rationale": "shape sets everything downstream" },
    { "phase_n":  2, "phase": "User Stories",        "model": "Claude Sonnet 4.6", "input_tokens": 24000, "output_tokens": 12000, "cost": 0.25, "rationale": "structured decomposition workhorse" },
    { "phase_n":  3, "phase": "Feature Dev",         "model": "Claude Opus 4.7",   "input_tokens": 28800, "output_tokens": 60000, "cost": 4.93, "rationale": "code architecture matters" },
    { "phase_n":  4, "phase": "Vulnerability Check", "model": "Claude Haiku 4.5",  "input_tokens": 14400, "output_tokens":  4500, "cost": 0.03, "rationale": "shallow scan; speed > depth" },
    { "phase_n":  5, "phase": "Tech Debt Check",     "model": "Claude Sonnet 4.6", "input_tokens": 19200, "output_tokens":  6000, "cost": 0.15, "rationale": "hotspot ranking needs some judgement" },
    { "phase_n":  6, "phase": "Test Cases",          "model": "Claude Opus 4.7",   "input_tokens": 28800, "output_tokens": 18000, "cost": 1.78, "rationale": "coverage gaps become bugs — spend here" },
    { "phase_n":  7, "phase": "Test Scripts",        "model": "Claude Sonnet 4.6", "input_tokens": 19200, "output_tokens": 30000, "cost": 0.51, "rationale": "Playwright code is templated" },
    { "phase_n":  8, "phase": "Boot",                "model": "Gemini 2.0 Flash",  "input_tokens": 14400, "output_tokens":  3000, "cost": 0.00, "rationale": "trivial structured output" },
    { "phase_n":  9, "phase": "Test Execution",      "model": "Claude Haiku 4.5",  "input_tokens": 28800, "output_tokens":  6000, "cost": 0.05, "rationale": "TRX parse + Jira format" },
    { "phase_n": 10, "phase": "Deployment",          "model": "Gemini 2.0 Flash",  "input_tokens": 14400, "output_tokens":  3000, "cost": 0.00, "rationale": "manifest YAML, trivial" },
    { "phase_n": 11, "phase": "Sanity Check",        "model": "Claude Sonnet 4.6", "input_tokens": 24000, "output_tokens":  6000, "cost": 0.16, "rationale": "maps probes to stories" }
  ],
  "catalog": [
    { "family": "Anthropic", "model": "Claude Opus 4.7 (1M ctx)", "in": 15.00,  "out": 75.00, "note": "deep reasoning, long context, agentic flows" },
    { "family": "Anthropic", "model": "Claude Sonnet 4.6",        "in":  3.00,  "out": 15.00, "note": "balanced reasoning, coding, default workhorse" },
    { "family": "Anthropic", "model": "Claude Haiku 4.5",         "in":  0.80,  "out":  4.00, "note": "fast structured generation, summarisation" },
    { "family": "OpenAI",    "model": "GPT-4.1",                  "in":  2.00,  "out":  8.00, "note": "strong general-purpose" },
    { "family": "OpenAI",    "model": "GPT-4o",                   "in":  2.50,  "out": 10.00, "note": "multimodal, general-purpose" },
    { "family": "OpenAI",    "model": "GPT-4o-mini",              "in":  0.15,  "out":  0.60, "note": "cheap, fast, high-volume utility" },
    { "family": "OpenAI",    "model": "o1",                       "in": 15.00,  "out": 60.00, "note": "hard reasoning + math (slow)" },
    { "family": "OpenAI",    "model": "o1-mini",                  "in":  3.00,  "out": 12.00, "note": "mid-tier reasoning" },
    { "family": "OpenAI",    "model": "o3-mini",                  "in":  1.10,  "out":  4.40, "note": "newer reasoning, cheaper" },
    { "family": "Google",    "model": "Gemini 1.5 Pro",           "in":  1.25,  "out":  5.00, "note": "very long context (1–2M)" },
    { "family": "Google",    "model": "Gemini 2.0 Flash",         "in":  0.10,  "out":  0.40, "note": "very cheap, multimodal" },
    { "family": "Google",    "model": "Gemini 1.5 Flash",         "in":  0.075, "out":  0.30, "note": "cheap structured outputs" },
    { "family": "Google",    "model": "Gemini 1.5 Flash-8b",      "in":  0.0375,"out":  0.15, "note": "absolute cheapest viable" },
    { "family": "Meta",      "model": "Llama 3.3 70B (Together)", "in":  0.60,  "out":  0.60, "note": "open-weight, mid-tier" },
    { "family": "Meta",      "model": "Llama 3.1 405B (Together)","in":  3.50,  "out":  3.50, "note": "open-weight frontier" },
    { "family": "Mistral",   "model": "Mistral Large 2",          "in":  2.00,  "out":  6.00, "note": "EU-hosted, code-strong" },
    { "family": "DeepSeek",  "model": "DeepSeek V3",              "in":  0.27,  "out":  1.10, "note": "very cheap general-purpose" },
    { "family": "DeepSeek",  "model": "DeepSeek R1",              "in":  0.55,  "out":  2.19, "note": "very cheap reasoning" },
    { "family": "xAI",       "model": "Grok-3",                   "in":  5.00,  "out": 15.00, "note": "recent training data + web search" }
  ]
}
JSON
```

Substitute the real per-phase numbers (computed in Step 5), the source filename, the project name, and the per-doc summary fields. The catalog block is static — copy it as-is unless the user explicitly asked for a different model pool.

After the script reports `wrote <path> · <N> bytes`, the file shows up immediately in the **Files** tab the next time the user refreshes the panel (the upload listing route just reads `readdirSync` on `uploads/`).

### 7c — PDF (always — presentation-ready format)

After the xlsx is written, run the bundled `pdf-generator.js` against the **same JSON payload** to produce a 3-page presentation-ready PDF in `uploads/`. Same naming convention as 7b so the FilesPanel strips the timestamp prefix on display.

```bash
TS_PDF=$(node -e "console.log(Date.now())")
OUT_PDF="$PWD/uploads/${TS_PDF}-sdlc-tokenomics-${DATE}.pdf"
GEN_PDF="$HOME/.claude/skills/sdlc-tokenomics/pdf-generator.js"
[ -f "$GEN_PDF" ] || GEN_PDF="$(dirname "$0")/pdf-generator.js"

# Same payload, same NODE_PATH resolution. exceljs and pdfkit both live in
# quantnik backend node_modules — the QUANTNIK_BE discovery from 7b applies here.
NODE_PATH="$QUANTNIK_BE/node_modules" node "$GEN_PDF" "$OUT_PDF" <<'JSON'
{ ...same payload as 7b, optionally with these extra fields for richer rendering... }
JSON
```

The PDF generator accepts a few **optional** fields in the JSON payload beyond what xlsx-generator.js uses:

| Field | Type | Effect |
|---|---|---|
| `recommendation` | `string[]` — array of paragraphs | Page 2 body. Falls back to a generic recommendation derived from the top-3-cost phases. |
| `cost_optimised_total` | `number` (USD) | Renders a "Cost-optimised alternative" callout box on page 2 with the savings delta. |
| `caveats` | `string[]` | Page 2 caveat list (each rendered as a bullet inside an amber-bordered box). Defaults to the three standard caveats (±30% directional, system-prompt overhead, quantnik-Claude-only). |

PDF structure:
- **Page 1** — title bar + summary card (source doc, size, complexity, total cost prominent in accent green) + phase mapping table (6 cols: #, Phase, Model, Input tok, Output tok, Cost) with alternating row shading and a bolded TOTAL row + cost-concentration callout below.
- **Page 2** — Recommendation paragraphs + optional Cost-optimised alternative box + Caveats list.
- **Page 3** — Model catalog reference (Family, Model, $/M input, $/M output, Best for).
- **Footer** on every page — "Generated by quantnik · sdlc-tokenomics · YYYY-MM-DD" and "Page N of 3".

### 7d — Confluence (only if `quantnik.json` declares a space)

If the project has a `.claude/quantnik.json` with `atlassian.confluenceSpaceKey`, publish the markdown table from Step 6 as a Confluence page titled `<project> — SDLC Tokenomics — <YYYY-MM-DD>`. Apply the project's `atlassian.labels` so the page lands in the right dashboard. Use the body-size-aware publish path (stdio MCP for ≤ 30 KB, curl + REST for larger) — this report is small enough that the stdio path always wins.

If `quantnik.json` is absent, skip silently — 7a (markdown) and 7b (xlsx) are enough.

---

### Final user message

After all four persistence paths complete, end the chat reply with:

> ✅ Tokenomics report saved.
> - **Files tab**: `sdlc-tokenomics-<YYYY-MM-DD>.xlsx` (3 sheets) + `sdlc-tokenomics-<YYYY-MM-DD>.pdf` (3 pages)
> - **Repo root**: `SDLC_TOKENOMICS_<YYYY-MM-DD>.md`
> - **Confluence**: <page URL>   (omit this line if 7d was skipped)

---

## Guardrails

- **Estimates are directional.** ±30% is typical. Real spend will diverge based on: retry loops mid-phase, prompt-engineering overhead, the agent reading tool results back as context, mid-phase iteration. Surface this caveat in the output paragraph — never claim a specific cost is exact.
- **Prices last refreshed January 2026.** If asked "is this still current?", advise verifying against vendor pricing pages before committing budget.
- **quantnik's agent runtime is Claude-only today.** Non-Claude picks (GPT, Gemini, Llama, etc.) can be **costed** but cannot yet be **executed** by the quantnik agent runtime (which uses the Claude Agent SDK). Surface this in the recommendation so non-Anthropic picks read as future-state options, not immediate actions.
- **Don't over-engineer.** The output is a one-screen table + one paragraph. Don't pad with sub-sections, methodology essays, or futurology. Two artifacts: the table, the recommendation. Stop.
- **Idempotent.** Re-invoking on the same document produces the same table. If the user uploads a different document, the new one wins (Step 0's most-recently-uploaded rule).
