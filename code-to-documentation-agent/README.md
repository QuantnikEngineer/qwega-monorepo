# Code To Documentation Agent

An AI-powered agent that generates comprehensive documentation from Git repository code chunks using Azure OpenAI (GPT-4o).

## 🎯 Features

- **Repository Discovery**: Browse and select from available repositories
- **AI-Powered Documentation**: Automatically generate comprehensive project documentation
- **Interactive Chat**: Ask questions about repository code and get intelligent answers
- **Code Analysis**: Analyzes code structure, architecture, and patterns
- **Markdown Export**: Download generated documentation
- **Modern UI**: Clean, responsive interface built with React and Material-UI

## 🏗️ Architecture

```
Frontend (React/TypeScript) → Backend (FastAPI/Python) → External Repo API
                                                       ↓
                                                Azure OpenAI (GPT-4o)
```

## 📋 Prerequisites

- **Python 3.10+** and pip
- **Node.js 16+** and npm
- **Azure OpenAI** account and API key
- **External Repository API** running on `http://localhost:8000` with:
  - `GET /list_repo_contexts` - Lists all repositories
  - `GET /retrieve_repo_chunks?repo_id=<id>` - Returns code chunks

## 🚀 Quick Start

### 1. Backend Setup

Create `.env` file in `backend/` directory:

```env
AZURE_OPENAI_MODEL_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2023-07-01-preview
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
```

Install and run:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

Backend runs at: `http://localhost:8001`

### 2. Frontend Setup

```bash
cd frontend
npm install
npm start
```

Frontend opens at: `http://localhost:3000`

### 3. External Repository API

Ensure your repository API is running at `http://localhost:8000`

## 📡 API Endpoints

### Backend Endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/repos/list` | GET | List all repositories |
| `/api/repos/{repo_id}/chunks` | GET | Get code chunks for a repo |
| `/api/repos/generate-documentation` | POST | Generate documentation |
| `/api/repos/chat` | POST | Chat about a repository |

## 🎨 UI Components

- **Repository Section**: Lists repositories with metadata (language, size, last updated)
- **Chat Interface**: Interactive conversation about repositories
- **Documentation Generator**: One-click documentation generation
- **Prompt Library**: Quick action prompts
- **Header**: LLM provider and model selection

## 📖 Usage

1. **Select a Repository**: Click on any repository in the sidebar
2. **Generate Documentation**: Click "Generate Documentation" button
3. **Chat**: Ask questions like:
   - "What does this project do?"
   - "Explain the architecture"
   - "How do I set this up?"
4. **Download**: Export documentation as Markdown

## 🔧 Configuration

### LLM Providers Supported:
- Azure OpenAI (default)
- OpenAI
- Other providers via LiteLLM

### Models:
- GPT-4o (default)
- GPT-4
- GPT-3.5-turbo

## 📁 Project Structure

```
agent_documentation/
├── backend/
│   ├── main.py                      # FastAPI app with endpoints
│   ├── models.py                    # Pydantic models
│   ├── repo_service.py              # External API client
│   ├── doc_generation_agent.py      # AI documentation generator
│   ├── litellm_client.py            # LLM client wrapper
│   ├── secrets_manager.py           # Environment config
│   └── requirements.txt             # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Agent.tsx            # Main chat interface
│   │   │   ├── RepositorySection.tsx # Repo list component
│   │   │   ├── PromptLibrary.tsx    # Quick actions
│   │   │   └── layout/
│   │   │       └── Header.tsx        # App header
│   │   ├── config/
│   │   │   ├── agentConfig.ts       # API configuration
│   │   │   └── llmConfig.ts         # LLM provider config
│   │   └── jwt-auth/                # Authentication
│   └── package.json
├── SETUP_GUIDE.md                   # Detailed setup instructions
└── README.md                        # This file
```

## 🧪 Testing

### Test Backend:
```bash
# Health check
curl http://localhost:8001/health

# List repositories
curl http://localhost:8001/api/repos/list
```

### Test Frontend:
- Navigate to http://localhost:3000
- Should see Code To Documentation Agent interface
- No authentication required on localhost (dev mode)

## 🐛 Troubleshooting

### "Failed to fetch repositories"
- Ensure external repo API is running on port 8000
- Check: `curl http://localhost:8000/list_repo_contexts`

### "Failed to generate documentation"
- Verify Azure OpenAI credentials in `.env`
- Check backend logs for detailed errors
- Ensure API key is valid and has quota

### Authentication Issues
- Clear browser localStorage
- Reload the page (dev mode auto-authenticates on localhost)

## 🔒 Security

- **JWT Authentication**: Disabled in dev mode (localhost only)
- **Production**: Update `JWTAuthService.ts` to enable full auth
- **Environment Variables**: Never commit `.env` files
- **CORS**: Configure in `main.py` for production domains

## 📊 Generated Documentation Includes:

1. **Project Overview** - High-level description
2. **Architecture** - System design and patterns
3. **Components** - Key modules and their roles
4. **APIs & Interfaces** - Public APIs and endpoints
5. **Data Models** - Schemas and structures
6. **Configuration** - Environment setup
7. **Dependencies** - External libraries
8. **Setup Instructions** - Installation guide
9. **Usage Examples** - Code samples
10. **Best Practices** - Development guidelines

## 🚀 Production Deployment

1. Update `.env` with production credentials
2. Set environment variables in deployment platform
3. Build frontend: `cd frontend && npm run build`
4. Deploy backend with Gunicorn or similar
5. Configure CORS for your domain
6. Set up proper authentication

## 📚 Documentation

See [SETUP_GUIDE.md](./SETUP_GUIDE.md) for detailed setup instructions and troubleshooting.

## 🤝 Contributing

This project was created as a Code To Documentation Agent. To modify:
- Backend: Update `backend/main.py` and related services
- Frontend: Modify components in `frontend/src/components/`
- AI Prompts: Edit `backend/doc_generation_agent.py`

## 📄 License

[Your License Here]

## 🙏 Acknowledgments

- Built with FastAPI, React, and Azure OpenAI
- Uses Material-UI for components
- Powered by GPT-4o for documentation generation

---

**Note**: This agent requires an external repository API service that provides:
- Repository listings
- Code chunk retrieval

Make sure this service is running before starting the agent.
