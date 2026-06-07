# Wegaum — User Manual Writer

A production-grade FastAPI service that turns a folder of source documents
(or a Confluence page tree) into a complete, end-user friendly **user
manual** and publishes it as a native Confluence page. The core is a
sequential, persona-locked **User Manual Writer** agent built on Google ADK
+ Gemini.

---

## Why this exists

Hand-written user manuals are slow and inconsistent. Existing "doc
generators" tend to either hallucinate content not in the source, or skip
the things end users actually need — diagrams, role-specific screens,
glossaries, FAQs.

Wegaum is built around three production guarantees:

1. **Grounding over fluency.** Every section is written by a stage that is
   explicitly told it is a **User Manual Writer** and that it must use
   *only* the structured facts extracted from the source. No invented
   features, role names, SLAs, or steps.
2. **Visuals where they belong.** Architecture diagrams are extracted and
   embedded under the Overview. Figma/UI screenshots are matched per role
   and embedded under the relevant role section. Sections that do not
   need an image never get one.
3. **Confluence is a first-class output.** Local image paths are
   rewritten and uploaded as page attachments so the published page
   actually renders the images instead of broken `<img>` links.

---

## Architecture overview

```
                      ┌────────────────────────┐
   Source URL ─────▶  │  POST /generate-manual │
                      └───────────┬────────────┘
                                  │
                                  ▼
        ┌───────────────────────────────────────────────────┐
        │            ADK SequentialAgent root               │
        │     (User Manual Writer pipeline, 3 stages)       │
        └───────────────────────────────────────────────────┘
   1. folder_reader_agent  ─ ingests SharePoint/Confluence/local
                              docs, extracts & classifies images,
                              writes raw_corpus + image lists to
                              session state.
   2. extraction_agent      ─ reads raw_corpus from state and
                              produces a strictly-grounded JSON
                              of title, roles, workflows, terms.
   3. content_generation_group   (ParallelAgent – run concurrently)
        a. common_sections_agent  – Overview + Getting Started.
                                    Embeds architecture diagram in
                                    Overview if one was extracted.
                                    Embeds login/landing screen in
                                    Getting Started if present.
        b. role_based_agent       – Per role: picks at most one
                                    relevant Figma/UI image and
                                    writes the role section.
        c. faq_agent              – 8–15 grounded FAQs.
        d. glossary_agent         – Alphabetised glossary.

   (Markdown assembly is done in Python — `_assemble_manual_from_state`
   in main.py — rather than a 4th LLM call, saving 30–60 s per run.)
                                  │
                                  ▼
                      ┌────────────────────────┐
                      │ Confluence publisher    │
                      │  • md → storage HTML    │
                      │  • upload local images  │
                      │    as page attachments  │
                      │  • rewrite <img> →      │
                      │    <ac:image>           │
                      └───────────┬────────────┘
                                  │
                                  ▼
                          Confluence child page
                          (returned URL)
```

---

## Image handling rules

The pipeline extracts every embedded image from PDFs (`pdfplumber`),
DOCX (`word/media/`), PPTX (picture shapes), plus standalone images
(`.png/.jpg/.jpeg/.gif/.bmp/.webp/.svg`) and any image attachments on
input Confluence pages. Each image is then classified as one of:

| Category       | Examples                                              |
|----------------|-------------------------------------------------------|
| `architecture` | system diagrams, data-flow, deployment, C4, ER, HLD   |
| `figma`        | Figma frames, wireframes, mockups, prototypes, UI     |
| `screenshot`   | anything else (in-app screen captures, UI snippets)   |

Classification is **hybrid**:

1. **Deterministic first pass** on filename, source-document name and
   surrounding text using curated keyword vocabularies.
2. **Gemini Vision fallback** only when keywords are inconclusive.
   Bounded by `MAX_VISION_CLASSIFICATIONS` (default 12) per pipeline run
   to keep cost predictable.

Where images go in the manual:

- **Overview** → at most one *architecture* image (if any).
- **Getting Started** → at most one *login / landing / home / dashboard*
  screen, selected by score against the keywords `login, sign-in,
  landing, home, homepage, welcome, dashboard, main page, after login`.
  Threshold: `LANDING_IMAGE_SCORE_THRESHOLD` (default 1.0).
- **Each role section** → at most one *figma* or *screenshot* image,
  selected by a relevance score against the role's name and
  extraction-derived keywords. Threshold: `ROLE_IMAGE_SCORE_THRESHOLD`
  (default 1.5). Cap: `ROLE_IMAGES_MAX` (default 1).
- **FAQ, Glossary** → never include images.

When the manual is published to Confluence, every local image path
is uploaded as a page attachment and the `<img>` tag is rewritten to a
proper Confluence `<ac:image>` storage element so it renders inline.

---

## Anti-hallucination posture

Each agent is locked to a **User Manual Writer** persona with explicit
rules:

- Use only what is in the upstream session state.
- Return `null` / `[]` for any field not grounded in the corpus.
- No general world-knowledge fill-in.
- No filename leakage into the user-facing manual.

State is propagated via ADK `output_key` + `ToolContext.state` (not
conversation history) so each stage reads from a single, reliable source
of truth.

---

## API

### `POST /generate-manual`

Request:

```json
{
  "url": "https://tenant.sharepoint.com/sites/MySite/Shared Documents/MyFolder",
  "project_name": "MyProduct User Manual"
}
```

Accepted source URL types:

| Source                              | Example                                                                                |
|-------------------------------------|----------------------------------------------------------------------------------------|
| SharePoint folder                   | `https://tenant.sharepoint.com/sites/MySite/Shared Documents/MyFolder`                 |
| SharePoint folder (browser view)    | `https://tenant.sharepoint.com/...AllItems.aspx?id=%2Fsites%2F...%2FMyFolder`          |
| SharePoint single file              | `https://tenant.sharepoint.com/.../MyDoc.pdf`                                          |
| Confluence page                     | `https://tenant.atlassian.net/wiki/spaces/KEY/pages/12345678/Page+Title`               |

Supported document types: `.pdf .docx .txt .xls .xlsx .csv .json .pptx`
plus standalone image files.

Response:

```json
{
  "status": "success",
  "session_id": "manual-a1b2c3d4e5f6",
  "confluence_url": "https://tenant.atlassian.net/wiki/spaces/KEY/pages/.../MyProduct+User+Manual"
}
```

Error codes:

| Code | Reason                                                         |
|------|----------------------------------------------------------------|
| 409  | A Confluence page with the same `project_name` already exists. |
| 429  | Service at capacity — retry shortly.                           |
| 500  | Pipeline or Confluence publish failed.                         |
| 502  | Could not reach Gemini / Vertex AI.                            |
| 504  | Pipeline exceeded its time budget (`PIPELINE_TIMEOUT_SECS`).  |

### `GET /health`

Returns service status & version.

### Interactive docs

Browse `/docs` (Swagger UI) or `/redoc`.

---

## Environment variables

### Google AI (required)

| Var                          | Purpose                                               |
|------------------------------|-------------------------------------------------------|
| `GOOGLE_GENAI_USE_VERTEXAI`  | `1` to use Vertex AI auth.                            |
| `GOOGLE_CLOUD_PROJECT`       | GCP project id.                                       |
| `GOOGLE_CLOUD_LOCATION`      | e.g. `us-central1`.                                   |
| `GEMINI_MODEL`               | e.g. `gemini-2.5-pro`.                                |

### SharePoint input (use either this or Confluence)

| Var                         | Purpose                                                    |
|-----------------------------|------------------------------------------------------------|
| `SHAREPOINT_URL`            | Folder or single-file URL (or use legacy site/folder pair).|
| `SHAREPOINT_CLIENT_ID`      | Azure AD application (client) ID.                          |
| `SHAREPOINT_CLIENT_SECRET`  | Azure AD client secret.                                    |
| `SHAREPOINT_TENANT_ID`      | Azure AD tenant (directory) ID.                            |

The Azure AD app must have Microsoft Graph **`Sites.ReadWrite.All`**
Application permission with admin consent.

### Confluence (output target — required, also used when input is Confluence)

| Var                            | Purpose                                                       |
|--------------------------------|---------------------------------------------------------------|
| `CONFLUENCE_BASE_URL`          | e.g. `https://tenant.atlassian.net/wiki`.                     |
| `CONFLUENCE_EMAIL`             | API user email.                                               |
| `CONFLUENCE_API_TOKEN`         | API token.                                                    |
| `CONFLUENCE_SPACE_KEY`         | (Optional) Space key. Auto-resolved from parent if omitted.   |
| `CONFLUENCE_PARENT_PAGE_ID`    | Parent page id under which manuals are published.             |

### Tuning (optional)

| Var                                | Default | Effect                                                            |
|------------------------------------|--------:|-------------------------------------------------------------------|
| `LOG_LEVEL`                        | `INFO`  | Service log level.                                                |
| `OUTPUT_DIR`                       | `/tmp/outputs` | Local scratch dir for outputs.                             |
| `MAX_VISION_CLASSIFICATIONS`       | `12`    | Cap on Gemini Vision classification calls per run.                |
| `MAX_VISION_DESCRIPTIONS`          | `12`    | Cap on Gemini Vision description calls (caption enrichment).      |
| `ROLE_IMAGE_SCORE_THRESHOLD`       | `1.5`   | Min relevance score to attach an image to a role.                 |
| `ROLE_IMAGES_MAX`                  | `1`     | Max images per role section.                                      |
| `LANDING_IMAGE_SCORE_THRESHOLD`    | `1.0`   | Min score to attach a login/landing image to Getting Started.     |
| `VISION_CONCURRENCY`               | `6`     | Parallel workers for Gemini Vision classification + description.  |
| `CAPTION_DESCRIPTION_THRESHOLD`    | `120`   | Skip vision-description call when existing caption ≥ this many chars. |
| `CONFLUENCE_UPLOAD_CONCURRENCY`    | `4`     | Parallel workers for uploading image attachments to Confluence.   |
| `MAX_CORPUS_CHARS`                 | `500000`| Truncate aggregated corpus beyond this size (head + tail kept).   |
| `MAX_CONCURRENT_PIPELINES`         | `3`     | Max pipelines running simultaneously.                             |
| `MAX_QUEUED_PIPELINES`             | `5`     | Max pipelines waiting to run (overflow returns HTTP 429).         |
| `PIPELINE_TIMEOUT_SECS`            | `900`   | Hard wall-clock timeout per pipeline (returns HTTP 504).          |

---

## Run locally

```powershell
# 1. Create venv & install
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Populate .env (see .env.example)

# 3. Start
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Then `POST` to `http://localhost:8080/generate-manual` with the JSON body
shown above.

---

## Run with Docker

```powershell
docker build -t wegaum:latest .
docker run --rm -p 8080:8080 --env-file .env wegaum:latest
```

---

## Repo layout

```
.
├─ main.py                         FastAPI app, ADK runner, Python assembler
├─ userstory/
│  ├─ agent.py                     Pipeline composition (SequentialAgent + ParallelAgent)
│  ├─ file_reader_agent.py         Stage 1 – ingestion
│  ├─ file_reader_tools.py         Document + image extractors, classifiers
│  ├─ extract_agent.py             Stage 2 – grounded extraction
│  ├─ common_sections_agent.py     Stage 3a (parallel) – Overview + Getting Started
│  ├─ role_based_agent.py          Stage 3b (parallel) – Role sections + per-role images
│  ├─ faq_agent.py                 Stage 3c (parallel) – FAQs
│  ├─ glossary_agent.py            Stage 3d (parallel) – Glossary
│  ├─ renderer_agent.py            (inactive – assembly moved to main.py Python fn)
│  ├─ confluence_tools.py          Confluence read / publish + image attaching
│  └─ pdf_exporter_agent.py        Optional PDF export
├─ data/extracted_images/          Per-session image cache
├─ outputs/                        Optional PDF / debug outputs
├─ requirements.txt
├─ Dockerfile
└─ README.md (this file)
```

---

## Operational notes

- **Single env-var lock.** Concurrent `/generate-manual` calls are
  serialised by an asyncio lock so the pipeline-scoped env overrides
  (`SHAREPOINT_URL` / `CONFLUENCE_SOURCE_URL`) cannot be clobbered. If
  you expect heavy concurrency, add a semaphore-based admission limit
  in front of the endpoint.
- **Idempotent project names.** A pre-flight check returns **HTTP 409**
  if a Confluence page with the requested title already exists under the
  parent. Pick a different name or delete the existing page.
- **Per-session image folder.** Every run creates
  `data/extracted_images/<random12>/`. After Confluence publish those
  files are no longer needed and may be cleaned up by an external job.
