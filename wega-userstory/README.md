# WEGA User Story Agent API

FastAPI-based service for generating epics and user stories from a BRD document, exporting them to Jira, and updating existing Jira issues.

## Features

- Provide a Jira/Confluence BRD URL and generate:
  - Epics
  - User stories per epic
- Export generated epics and stories to Jira
- Update one or more existing Jira issues (summary and/or description)
- Create additional Jira stories under existing Jira epics
- Delete Jira issues in bulk (with optional subtask deletion)
- Structured logging to console and rotating log files

## Requirements

- Python 3.10+
- pip
- A Jira Cloud instance and API token
- Google GenAI / ADK credentials (for the underlying agent)

## Setup

1. **Clone / open the project**

   ```bash
   cd WEGA-UserStory
   ```

2. **Create and activate a virtual environment (recommended)**

   ```bash
   python -m venv .venv
   .venv\\Scripts\\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment variables**

   Create a `.env` file in the project root (same folder as `main.py`) and add the required settings. `main.py` loads this file using `python-dotenv`.

   **Jira configuration** (used in `tools/exporter.py`):

   ```env
   JIRA_BASE_URL=https://your-domain.atlassian.net
   JIRA_EMAIL=your.email@company.com
   JIRA_API_TOKEN=your_jira_api_token
   JIRA_PROJECT_KEY=YOURPROJ
  JIRA_TEST_LINK_DISPLAY_LABEL=tests
   ```

  `JIRA_TEST_LINK_DISPLAY_LABEL` is optional. Use `tests` if you want the
  Jira issue to show the test case under Linked work items -> tests. Use
  `is tested by` if you want Jira to show the inverse wording instead.

  **Google / Agent configuration** (Vertex AI via Google GenAI / ADK):

  This project uses Vertex AI (no direct API key here) and reads the
  model name and other settings from the environment. See the `.env`
  file in this repo for the full, current list, but at minimum you
  will typically need:

  ```env
  GOOGLE_GENAI_USE_VERTEXAI=TRUE
  GOOGLE_CLOUD_PROJECT=digital-rig-poc           # or your own GCP project
  GOOGLE_CLOUD_LOCATION=global                   # or your chosen region
  GEMINI_MODEL=gemini-3-flash-preview           # LLM model name used by the agent
  ```

  The `GEMINI_MODEL` value is picked up in `userstory/agent.py` via
  the `GEMINI_MODEL` environment variable and defaults to
  `gemini-3-flash-preview` if not set.

## Running the API

From the project root (folder containing `main.py`):

```bash
uvicorn main:app --reload
```

The API will be available at:

- Base URL: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## API Endpoints

### 1. Generate User Stories

**POST** `/generate-user-stories`

Provide a Confluence/Jira BRD page URL and get back generated epics and user stories.

- **Content type**: `multipart/form-data`
- **Field**:
  - `brd_confluence_link` (required): Confluence page URL containing the BRD content. Jira credentials (`JIRA_EMAIL` / `JIRA_API_TOKEN`) are used for authentication.

**Response (simplified)**

```json
{
  "status": "success",
  "summary": "High-level summary of the BRD / stories",
  "epics": [
    {
      "epic_title": "Epic 1",
      "epic_description": "...",
      "user_stories": [
        {
          "title": "As a user, I want ...",
          "description": "...",
          "acceptance_criteria": [
            { "criterion": "Given ..., when ..., then ..." }
          ]
        }
      ]
    }
  ],
  "stories": [
    {
      "title": "As a user, I want ...",
      "description": "...",
      "acceptance_criteria": [
        { "criterion": "..." }
      ]
    }
  ],
}
```

Note: the service enforces a hard limit of 7 user stories per epic. If the agent returns more, they are truncated server-side.

---

### 2. Export Epics & Stories to Jira

**POST** `/export-to-jira`

Export generated epics and user stories to a Jira project. This uses the same structure as the agent output.

**Request body (Pydantic model `AgentOutput`):**

```json
{
  "epics": [
    {
      "epic_title": "Epic 1",
      "epic_description": "Optional description",
      "user_stories": [
        {
          "title": "Story title",
          "description": "Story description",
          "acceptance_criteria": [
            { "criterion": "Given ..., when ..., then ..." }
          ]
        }
      ]
    }
  ]
}
```

**Response (simplified)**

```json
{
  "status": "success",
  "jira_export_result": {
    "status": "success",
    "created": {
      "epics": [
        { "key": "PROJ-1", "browse_url": "https://.../browse/PROJ-1" }
      ],
      "stories": [
        { "key": "PROJ-2", "browse_url": "https://.../browse/PROJ-2" }
      ]
    }
  }
}
```

If something goes wrong, `status` will be `error` and an `error_message` will be included.

---

### 3. Update Existing Jira Issues (Batch)

**PUT** `/jira-issue`

Update one or more existing Jira issues' summary (title) and/or description.

- **Request body**: JSON array of `JiraIssueUpdate` objects.
- **Model** (`JiraIssueUpdate`):
  - `issue_key` (string, required) – e.g. `"PROJ-123"`.
  - `summary` (string, optional) – new issue summary/title.
  - `description` (string, optional) – new issue description (will be converted to Jira's ADF format internally).

You can update only the title, only the description, or both for each issue. At least one of `summary` or `description` must be provided per item; otherwise that item's update will return an error (`"No fields provided to update."`).

**Example request body**

```json
[
  {
    "issue_key": "PROJ-123",
    "summary": "New title for PROJ-123"
  },
  {
    "issue_key": "PROJ-456",
    "description": "Updated description for PROJ-456"
  },
  {
    "issue_key": "PROJ-789",
    "summary": "New title for PROJ-789",
    "description": "New description for PROJ-789"
  }
]
```

**Response (simplified)**

```json
{
  "status": "success" | "partial_error",
  "jira_update_results": [
    {
      "status": "success",
      "issue_key": "PROJ-123",
      "browse_url": "https://your-domain.atlassian.net/browse/PROJ-123"
    },
    {
      "status": "error",
      "error_message": "No fields provided to update."
    },
    {
      "status": "success",
      "issue_key": "PROJ-789",
      "browse_url": "https://your-domain.atlassian.net/browse/PROJ-789"
    }
  ]
}
```

- `status` is:
  - `"success"` if all items updated successfully.
  - `"partial_error"` if at least one item failed while others succeeded.
- Each element in `jira_update_results` corresponds to one input item and contains either a success object or an error with `error_message`.

---

### 4. Create Additional Jira Stories

**POST** `/create-additional-stories`

Create new Jira Story issues under existing Jira Epics. This is typically used for additional stories suggested by a validator agent.

- **Request body**: JSON array of `AdditionalUserStory` objects.
- **Model** (`AdditionalUserStory`):
  - `epic_issue_key` (string, required) – Jira key of the target Epic (e.g. `"PROJ-1"`).
  - `title` (string, required)
  - `description` (string, required)
  - `acceptance_criteria` (array of objects, required) – each with a `criterion` string.

On success, the response mirrors the Jira creation result:

```json
{
  "status": "success" | "partial_error",
  "jira_export_result": {
    "status": "success" | "partial_error",
    "created": {
      "stories": [
        { "key": "PROJ-10", "browse_url": "https://.../browse/PROJ-10" }
      ]
    }
  }
}
```

---

### 5. Delete Jira Issues

**DELETE** `/delete-jira-issues`

Delete one or more Jira issues by their keys, optionally including their subtasks.

- **Request body**: JSON array of `JiraIssueDelete` objects.
- **Model** (`JiraIssueDelete`):
  - `issue_key` (string, required) – e.g. `"PROJ-123"`.
  - `delete_subtasks` (boolean, optional, default `false`) – whether to also delete any subtasks.

**Response (simplified)**

```json
{
  "status": "success" | "partial_error",
  "jira_delete_results": [
    {
      "status": "success",
      "issue_key": "PROJ-123",
      "browse_url": "https://your-domain.atlassian.net/browse/PROJ-123"
    },
    {
      "status": "error",
      "error_message": "Failed to delete Jira issue ..."
    }
  ]
}
```

---

### 6. Health Check

**GET** `/health`

Simple health check endpoint to verify that the API is running.

**Response**

```json
{
  "status": "healthy",
  "agent": "user_story_agent"
}
```

---

## Logging

- Logs are written to the `logs/` directory as `app.log` with rotation (up to 10 MB per file, 5 backups).
- Logs are also streamed to stdout.
- Logging is configured in `main.py` using Python's `logging` module and `RotatingFileHandler`.

---

## Notes

- The agent behavior (how epics and stories are generated) is defined in `userstory/agent.py` and may be customized to fit your BRD format or Jira conventions.
- The Jira integration logic (issue creation and updates) lives in `tools/exporter.py`.
- This README reflects the current behavior where `/jira-issue` accepts a **list** of updates with optional `summary` and/or `description` per issue.
