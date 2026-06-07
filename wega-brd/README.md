BRD Agent API
==============


BRD Agent is a FastAPI service that guides users through collecting information for a Business Requirements Document (BRD), generates a `.docx` file, and can optionally publish that document to a Confluence page. It supports both greenfield (new) and brownfield (update existing) BRD flows.

---

## Project Structure

- `api/` — FastAPI app and all HTTP endpoints
- `agents/` — Conversation and update agents (LLM flows)
- `models/` — Pydantic models and enums for sessions, stakeholders, etc.
- `utils/` — Helpers for docx generation, Confluence, file extraction, prompts, validation
- `output/` — Generated BRD `.docx` files

---

## API Endpoints

- `POST   /sessions` — Create a new session (mode: new or update)
- `POST   /sessions/{id}/chat` — Send a chat message (project name, stakeholders, etc.)
- `POST   /sessions/{id}/upload-docs` — Upload .pdf/.docx/.txt files (with optional one-shot metadata)
- `GET    /sessions/{id}` — Get session status
- `GET    /sessions/{id}/download` — Download generated BRD `.docx`
- `POST   /sessions/{id}/publish` — Upload BRD `.docx` to Confluence
- `POST   /sessions/{id}/confluence-link` — Attach/validate a Confluence page for update mode
- `GET    /health` — Health check

---

## Environment Variables

Set these in a `.env` file or your environment:

- `GOOGLE_API_KEY` — Required for LLM calls
- `CONFLUENCE_PARENT_PAGE_URL` — (Recommended) Full Confluence page URL
- `CONFLUENCE_EMAIL` — Atlassian account email
- `CONFLUENCE_API_TOKEN` — Atlassian API token

Legacy/fallback vars (if not using `CONFLUENCE_PARENT_PAGE_URL`):
- `CONFLUENCE_BASE_URL` or `CONFLUENCE_URL`
- `CONFLUENCE_PAGE_ID`

Other optional vars:
- `LOG_FORMAT` — `text` (default) or `json`
- `LOG_LEVEL` — `INFO` (default), `DEBUG`, etc.
- `BRD_OUTPUT_DIR` — Output directory for generated files (default: `./output`)

---

## Dependencies

**Python:** (see `requirements.txt`)
- fastapi, uvicorn, python-docx, pdfplumber, python-dotenv, pydantic, requests, mcp-atlassian, pytest, httpx, etc.

**Node.js:** (see `package.json`)
- docx (for `generate_brd_docx.js`)

---

## Usage

1. Install Python dependencies:
	```sh
	pip install -r requirements.txt
	```
2. Install Node.js dependencies:
	```sh
	npm install
	```
3. Set up your `.env` file with required variables.
4. Run the API server:
	```sh
	uvicorn api.main:app --host 0.0.0.0 --port 8000
	```
5. The service will generate `.docx` files in the `output/` directory.

---

## Features

- **Conversational BRD creation:** Guides user through project name, stakeholders, and document upload
- **One-shot upload:** Provide all metadata and files in a single request to auto-generate a BRD
- **Brownfield update:** Update an existing Confluence BRD by providing a page link/ID
- **Stakeholder roles:** 9 predefined roles with responsibilities (see code for full list)
- **Document extraction:** Supports `.pdf`, `.docx`, `.doc`, `.txt` (with validation)
- **Confluence integration:** Uploads BRDs as versioned attachments, with robust retry and config parsing
- **Session management:** In-memory sessions with TTL and per-session document caps

---

## Output

- Generated BRDs are saved as `output/BRD_<sanitised-project-name>_vN.docx`
- Versioning: Each publish to Confluence increments `N` (v1, v2, ...)

---

## Testing

- Run all tests with:
  ```sh
  pytest
  ```

---

## Example .env

```
GOOGLE_API_KEY=your-google-api-key
CONFLUENCE_PARENT_PAGE_URL=https://your-domain.atlassian.net/wiki/spaces/SPACE/pages/123456/Page+Title
CONFLUENCE_EMAIL=your-email@domain.com
CONFLUENCE_API_TOKEN=your-api-token
```

---

## Notes

- The service uses both Python and Node.js. Node is required for `.docx` generation.
- For full details on flows, see the code in `api/`, `agents/`, and `utils/`.

---

Confluence integration
----------------------

To enable upload of generated BRD files to Confluence, set the following
environment variables (for example in `.env`):

- `CONFLUENCE_BASE_URL` – e.g. `https://your-domain.atlassian.net/wiki`
- `CONFLUENCE_EMAIL` – Atlassian account email used with the API token
- `CONFLUENCE_API_TOKEN` – API token generated from your Atlassian account
- `CONFLUENCE_PAGE_ID` – ID of the target Confluence page ("BRD Page")

When configured, the API exposes:

- `GET  /sessions/{id}/download` – download the generated BRD `.docx`.
- `POST /sessions/{id}/publish`  – upload the generated BRD `.docx` to the
	configured Confluence page as a new attachment.

The `publish` endpoint is intended to be called **only after** the user has
reviewed the document and explicitly confirmed they are happy to publish it.
The recommended client flow is:

1. Create a session and walk through the conversation as usual.
2. Wait for `final_brd_path` in the session status to be non-null.
3. Let the user download/open the `.docx` and review.
4. Ask the user: "Do you want to publish this BRD to Confluence?".
5. If the user agrees, call `POST /sessions/{id}/publish`.

Versioned filenames in Confluence
---------------------------------

Each upload to Confluence is stored as a new attachment on the same page.
The attachment filenames follow the pattern:

`BRD_<sanitised-project-name>_vN.docx`

- On first publish, `N = 1` (v1).
- On subsequent publishes, the service scans the existing attachments for the
	same project prefix and chooses the next integer `N` (v2, v3, ...).

This keeps a clear version trail on the Confluence page while still allowing
Confluence to maintain its own internal attachment versioning.

