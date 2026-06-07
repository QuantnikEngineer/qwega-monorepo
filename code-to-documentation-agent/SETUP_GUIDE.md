# 🚀 Code To Documentation Agent - Setup Guide

## Overview

This application has been transformed from a Functional Testing Agent into a **Code To Documentation Agent** that:
- Lists repositories from an external API
- Retrieves code chunks for selected repositories
- Generates comprehensive documentation using Azure OpenAI (GPT-4o)
- Provides interactive Q&A about repository code

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│  - Repository List UI                                           │
│  - Chat Interface                                               │
│  - Documentation Download                                       │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                          │
│  - Repository Endpoints (/api/repos/*)                         │
│  - Documentation Agent (AI-powered)                            │
│  - Repository Service (External API client)                    │
└────────────────────┬────────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│  External Repo   │    │   Azure OpenAI       │
│  API Service     │    │   GPT-4o             │
│  (localhost:8000)│    │                      │
└──────────────────┘    └──────────────────────┘
```

---

## 📋 Prerequisites

1. **Python 3.10+** and pip
2. **Node.js 16+** and npm
3. **External Repository API** running at `http://localhost:8000` with:
   - `GET /list_repo_contexts` - Returns list of repositories
   - `GET /retrieve_repo_chunks?repo_id=<id>` - Returns code chunks for a repo
4. **Azure OpenAI** account and API key

---

## 🔧 Backend Setup

### Step 1: Create Environment File

Create a file: `/Users/pr20606566/Desktop/agent_document/backend/.env`

```env
# Azure OpenAI Configuration
AZURE_OPENAI_MODEL_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2023-07-01-preview
AZURE_OPENAI_ENDPOINT=https://ai360-dev-azure-openai-westus.openai.azure.com/
AZURE_OPENAI_API_KEY=762e0e8e45f1498d8668cfad81694a46
```

### Step 2: Install Dependencies

```bash
cd /Users/pr20606566/Desktop/agent_documentation/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Start Backend Server

```bash
# Make sure you're in the backend directory with venv activated
python main.py
```

The backend will run at: **http://localhost:8001**

---

## 🎨 Frontend Setup

### Step 1: Install Dependencies

```bash
cd /Users/pr20606566/Desktop/agent_document/frontend
npm install
```

### Step 2: Start Frontend Development Server

```bash
npm start
```

The frontend will open at: **http://localhost:3000**

---

## 🔌 API Endpoints

### Backend Endpoints Created:

1. **GET /api/repos/list**
   - Lists all repositories from external API
   - Response: `{ success: true, repos: [...] }`

2. **GET /api/repos/{repo_id}/chunks**
   - Gets code chunks for a specific repository
   - Response: `{ success: true, repo_id: "...", chunks: [...] }`

3. **POST /api/repos/generate-documentation**
   - Generates comprehensive documentation
   - Request Body:
     ```json
     {
       "repo_id": "c5f4cc5a872c...",
       "repo_name": "my-project",
       "llm_provider": "azure_openai",
       "llm_model": "gpt-4o"
     }
     ```
   - Response: `{ success: true, documentation: "..." }`

4. **POST /api/repos/chat**
   - Chat about a repository
   - Request Body:
     ```json
     {
       "repo_id": "c5f4cc5a872c...",
       "repo_name": "my-project",
       "message": "What does this project do?",
       "llm_provider": "azure_openai",
       "llm_model": "gpt-4o"
     }
     ```
   - Response: `{ source: "agent", content: "..." }`

---

## 📁 Files Created/Modified

### Backend:
- ✅ **models.py** - Added repository models
- ✅ **repo_service.py** - NEW: External API client
- ✅ **doc_generation_agent.py** - NEW: AI documentation generator
- ✅ **main.py** - Added repository endpoints

### Frontend:
- ✅ **RepositorySection.tsx** - NEW: Repository list component
- ✅ **Agent.tsx** - Completely rewritten (simplified from 1685 → 550 lines)
- ✅ **Header.tsx** - Updated to "Code To Documentation Agent"
- ✅ **jwt-auth/services/JWTAuthService.ts** - Dev mode bypass

### Backup:
- ✅ **Agent.tsx.backup** - Original file saved

---

## 🎯 How to Use

1. **Start External Repo API** (must be running on port 8000)
2. **Start Backend** (runs on port 8001)
3. **Start Frontend** (runs on port 3000)
4. **Open Browser**: Navigate to http://localhost:3000
5. **Select Repository**: Click any repo in the sidebar
6. **Generate Documentation**: Click "Generate Documentation" button
7. **Ask Questions**: Type questions about the repo in the chat
8. **Download**: Save generated documentation as Markdown

---

## 🔄 Data Flow Example

### 1. List Repositories
```
Frontend → Backend (/api/repos/list)
       → External API (localhost:8000/list_repo_contexts)
       → Returns: [{ id: "...", name: "...", ... }]
```

### 2. Generate Documentation
```
Frontend → Backend (/api/repos/generate-documentation)
       → Backend retrieves chunks (localhost:8000/retrieve_repo_chunks)
       → Backend sends to Azure OpenAI GPT-4o
       → OpenAI analyzes code and generates documentation
       → Returns: Comprehensive Markdown documentation
```

### 3. Chat About Repository
```
Frontend → Backend (/api/repos/chat)
       → Backend retrieves chunks
       → Backend sends question + code context to OpenAI
       → OpenAI answers based on code
       → Returns: AI response
```

---

## 🧪 Testing the Setup

### 1. Test Backend Health
```bash
curl http://localhost:8001/health
```
Expected: `{"status": "healthy", "service": "agent-documentation-backend"}`

### 2. Test Repository List
```bash
curl http://localhost:8001/api/repos/list
```
Expected: `{"success": true, "repos": [...]}`

### 3. Test Frontend
- Open http://localhost:3000
- You should see the Code To Documentation Agent interface
- No authentication error (dev mode bypass is active)

---

## 🐛 Troubleshooting

### Issue: "Failed to fetch repositories"
**Solution**: Make sure the external repo API is running on port 8000

```bash
# Check if the API is running
curl http://localhost:8000/list_repo_contexts
```

### Issue: "Failed to generate documentation"
**Solution**: 
1. Check Azure OpenAI credentials in `.env`
2. Verify API key is valid
3. Check backend logs for detailed errors

### Issue: Authentication Required
**Solution**: The app should auto-authenticate on localhost. If not:
- Clear browser localStorage
- Reload the page

### Issue: TypeScript Errors
**Solution**: All fixed! If you see any:
```bash
cd frontend
npm install
```

---

## ✨ Features

- ✅ **Repository Listing**: Browse all available repositories
- ✅ **Code Analysis**: AI analyzes repository code chunks
- ✅ **Documentation Generation**: Comprehensive project docs including:
  - Project Overview
  - Architecture & Design Patterns
  - Components & APIs
  - Setup Instructions
  - Usage Examples
  - Best Practices
- ✅ **Interactive Chat**: Ask questions about the code
- ✅ **Markdown Export**: Download documentation
- ✅ **Modern UI**: Material-UI components
- ✅ **Error Handling**: Graceful error messages
- ✅ **Loading States**: Real-time progress indicators

---

## 🚀 Production Deployment

For production, you'll need to:

1. **Update `.env`** with production Azure OpenAI endpoint
2. **Set Environment Variables** in your deployment platform
3. **Update Repo API URL** in `repo_service.py` if not localhost
4. **Build Frontend**:
   ```bash
   cd frontend
   npm run build
   ```
5. **Deploy Backend** with proper WSGI server (e.g., Gunicorn)
6. **Configure CORS** in `main.py` for your production domain

---

## 📞 Support

For issues or questions:
1. Check backend logs: `python main.py` terminal output
2. Check frontend console: Browser Developer Tools (F12)
3. Verify external API is responding
4. Verify Azure OpenAI API key is valid

---

## 🎉 Summary

You now have a complete **Code To Documentation Agent** that:
- ✅ Connects to your external repository API
- ✅ Fetches code chunks
- ✅ Generates AI-powered documentation
- ✅ Provides interactive Q&A
- ✅ Has a clean, modern UI
- ✅ Removed all Jira/SharePoint complexity

**Next Steps**: 
1. Create the `.env` file with your credentials
2. Start the external repo API
3. Start the backend and frontend
4. Test the complete flow!

