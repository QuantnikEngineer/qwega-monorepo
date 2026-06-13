"""
LLM-powered code generator.
Produces a React + Node.js/Express full-stack application from user stories.
"""
import json
from typing import Dict, List, Optional
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


CODE_GEN_PROMPT = """You are an expert full-stack developer. Generate a complete, working application.

## Project: {project_name}
## Description: {description}

## User Stories:
{user_stories}

## Tech Stack:
- Frontend: React (Vite + TypeScript + Tailwind CSS)
- Backend: Node.js + Express + better-sqlite3

## Requirements:
1. Generate ALL files needed for a working application
2. Frontend runs on port 3000, backend on port 4000
3. Backend exposes a REST API consumed by the frontend
4. Include proper error handling, loading states, and responsive UI
5. Use modern React patterns (hooks, functional components)
6. Include a README.md with setup instructions

## Output format — respond with ONLY a valid JSON object:
{{
  "files": {{
    "frontend/package.json": "<content>",
    "frontend/vite.config.ts": "<content>",
    "frontend/index.html": "<content>",
    "frontend/src/main.tsx": "<content>",
    "frontend/src/App.tsx": "<content>",
    "frontend/src/index.css": "<content>",
    "frontend/src/components/...": "<content>",
    "backend/package.json": "<content>",
    "backend/src/index.js": "<content>",
    "backend/src/routes/...": "<content>",
    "docker-compose.yml": "<content>",
    "README.md": "<content>"
  }},
  "deployment_notes": "How to deploy this app"
}}

Generate real, working code — not placeholders."""


async def generate_code(
    project_name: str,
    description: str,
    user_stories: List[Dict],
    tech_stack: Dict[str, str],
) -> Dict[str, str]:
    """
    Call the configured LLM to generate a full-stack codebase.
    Returns a dict of {file_path: content}.
    """
    stories_text = "\n".join(
        f"- [{s.get('key', i+1)}] {s.get('summary', s.get('title', str(s)))}"
        for i, s in enumerate(user_stories)
    ) if user_stories else f"Build a {project_name} application: {description}"

    prompt = CODE_GEN_PROMPT.format(
        project_name=project_name,
        description=description,
        user_stories=stories_text,
    )

    # Try Anthropic first, fall back to Google Gemini
    if settings.anthropic_api_key:
        return await _generate_with_anthropic(prompt, project_name, description)
    elif settings.google_api_key:
        return await _generate_with_gemini(prompt, project_name, description)
    else:
        logger.warning("No LLM API key configured — returning scaffold code")
        return _scaffold(project_name, description)


async def _generate_with_anthropic(prompt: str, project_name: str, description: str) -> Dict[str, str]:
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        msg = await client.messages.create(
            model="claude-opus-4-8-20251101",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text
        return _parse_llm_output(raw, project_name, description)
    except Exception as e:
        logger.error("Anthropic code generation failed", error=str(e))
        return _scaffold(project_name, description)


async def _generate_with_gemini(prompt: str, project_name: str, description: str) -> Dict[str, str]:
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.google_api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return _parse_llm_output(response.text, project_name, description)
    except Exception as e:
        logger.error("Gemini code generation failed", error=str(e))
        return _scaffold(project_name, description)


def _parse_llm_output(raw: str, project_name: str, description: str) -> Dict[str, str]:
    """Extract JSON from LLM response and return file map."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    try:
        data = json.loads(text)
        files = data.get("files", {})
        if files:
            return files
    except json.JSONDecodeError:
        pass

    logger.warning("Could not parse LLM JSON output — falling back to scaffold")
    return _scaffold(project_name, description)


def _scaffold(project_name: str, description: str) -> Dict[str, str]:
    """Minimal working scaffold when LLM is unavailable."""
    safe_name = project_name.lower().replace(" ", "-")
    return {
        "README.md": f"# {project_name}\n\n{description}\n\n## Setup\n\n```bash\n# Backend\ncd backend && npm install && npm start\n\n# Frontend\ncd frontend && npm install && npm run dev\n```\n",
        "docker-compose.yml": f"""services:
  backend:
    build: ./backend
    ports: ["4000:4000"]
    environment:
      NODE_ENV: production
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [backend]
""",
        "frontend/package.json": json.dumps({
            "name": f"{safe_name}-frontend", "version": "0.1.0", "private": True,
            "scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
            "dependencies": {"react": "^18.3.1", "react-dom": "^18.3.1"},
            "devDependencies": {"@vitejs/plugin-react": "^4.3.1", "vite": "^5.4.0",
                                "typescript": "^5.5.3", "tailwindcss": "^3.4.0"}
        }, indent=2),
        "frontend/vite.config.ts": 'import { defineConfig } from "vite"\nimport react from "@vitejs/plugin-react"\nexport default defineConfig({ plugins: [react()], server: { port: 3000, proxy: { "/api": "http://localhost:4000" } } })\n',
        "frontend/index.html": f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>{project_name}</title></head><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>\n',
        "frontend/src/main.tsx": 'import React from "react"\nimport ReactDOM from "react-dom/client"\nimport App from "./App"\nimport "./index.css"\nReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>)\n',
        "frontend/src/App.tsx": f'import React from "react"\nexport default function App() {{\n  return <div className="min-h-screen bg-gray-50 flex items-center justify-center"><h1 className="text-4xl font-bold text-gray-900">{project_name}</h1></div>\n}}\n',
        "frontend/src/index.css": '@tailwind base;\n@tailwind components;\n@tailwind utilities;\n',
        "frontend/Dockerfile": 'FROM node:20-alpine AS build\nWORKDIR /app\nCOPY package*.json ./\nRUN npm ci\nCOPY . .\nRUN npm run build\nFROM nginx:alpine\nCOPY --from=build /app/dist /usr/share/nginx/html\nEXPOSE 80\n',
        "backend/package.json": json.dumps({
            "name": f"{safe_name}-backend", "version": "1.0.0",
            "type": "module",
            "scripts": {"start": "node src/index.js", "dev": "node --watch src/index.js"},
            "dependencies": {"express": "^4.18.2", "cors": "^2.8.5", "better-sqlite3": "^9.4.3"}
        }, indent=2),
        "backend/src/index.js": f"""import express from 'express'
import cors from 'cors'

const app = express()
app.use(cors())
app.use(express.json())

app.get('/api/health', (_req, res) => res.json({{ status: 'ok', service: '{project_name}' }}))

app.get('/api/items', (_req, res) => res.json({{ items: [] }}))

const PORT = process.env.PORT || 4000
app.listen(PORT, () => console.log(`{project_name} backend running on port ${{PORT}}`))
""",
        "backend/Dockerfile": 'FROM node:20-alpine\nWORKDIR /app\nCOPY package*.json ./\nRUN npm ci --omit=dev\nCOPY . .\nEXPOSE 4000\nCMD ["node","src/index.js"]\n',
    }
