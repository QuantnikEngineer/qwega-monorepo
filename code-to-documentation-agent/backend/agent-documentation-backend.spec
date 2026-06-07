# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Agent Documentation backend."""

import pathlib
import os

block_cipher = None

project_root = pathlib.Path(os.getcwd()).resolve()

hidden_imports = [
    # FastAPI and Uvicorn
    "uvicorn",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
    "fastapi",
    "starlette",
    "starlette.middleware",
    "starlette.middleware.cors",
    "pydantic",
    "pydantic_core",
    "multipart",
    
    # Autogen
    "autogen_agentchat",
    "autogen_agentchat.agents",
    "autogen_agentchat.ui",
    "autogen_agentchat.messages",
    "autogen_core",
    "autogen_ext",
    "autogen_ext.azure",
    "autogen_ext.tools",
    "autogen_ext.tools.mcp",
    "pyautogen",
    "typing_extensions",
    
    # LiteLLM and AI providers
    "litellm",
    "litellm.llms",
    "litellm.llms.anthropic",
    "litellm.llms.openai",
    "litellm.llms.vertex_ai",
    "litellm.llms.bedrock",
    "litellm.proxy",
    "litellm.litellm_core_utils",
    "litellm.litellm_core_utils.core_helpers",
    "litellm.litellm_core_utils.tokenizers",
    "litellm.caching",
    "openai",
    "openai.types",
    "openai.resources",
    
    # AWS
    "boto3",
    "botocore",
    "botocore.auth",
    "botocore.credentials",
    
    # Microsoft/Azure
    "msal",
    
    # Google Cloud
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "google.cloud",
    "google.cloud.aiplatform",
    "google.oauth2",
    "google.auth.compute_engine",
    
    # HTTP clients
    "httpx",
    "httpx._transports",
    "httpx._transports.default",
    "requests",
    "urllib3",
    "certifi",
    "charset_normalizer",
    "idna",
    
    # Document processing
    "docx",
    "docx.oxml",
    "docx.shared",
    "docx.text",
    "PIL",
    "PIL.Image",
    
    # Websockets
    "websockets",
    "websockets.server",
    "websockets.client",
    
    # FastMCP
    "fastmcp",
    "mcp",
    
    # Tiktoken for LiteLLM token counting
    "tiktoken",
    "tiktoken.core",
    "tiktoken.load",
    "tiktoken.registry",
    "tiktoken.model",
    "tiktoken_ext",
    "tiktoken_ext.openai_public",
    "regex",  # Required by tiktoken
    
    # Other dependencies
    "dotenv",
    "python_dotenv",
    "asyncio",
    
    # Local modules - Document Agent specific
    "models",
    "secrets_manager",
    "semantic_intent",
    "run_workflow",
    "sharepoint_client",
    "llm_config",
    "litellm_client",
    "mcp_server",
    "repo_service",
    "doc_generation_agent",
]

# Collect instruction files and other data files
datas = []

# Add tiktoken encoding data files (CRITICAL for LiteLLM token counting)
try:
    import tiktoken
    if hasattr(tiktoken, '__file__') and tiktoken.__file__ is not None:
        tiktoken_dir = pathlib.Path(tiktoken.__file__).parent
        # Include all tiktoken files and subdirectories
        datas.append((str(tiktoken_dir), "tiktoken"))
        print(f"✓ Added tiktoken data from: {tiktoken_dir}")
    else:
        print("⚠ Warning: tiktoken module has no __file__ attribute")
except (ImportError, AttributeError, TypeError) as e:
    print(f"⚠ Warning: Could not import tiktoken: {e}")

# Add tiktoken_ext for OpenAI public models
try:
    import tiktoken_ext
    if hasattr(tiktoken_ext, '__file__') and tiktoken_ext.__file__ is not None:
        tiktoken_ext_dir = pathlib.Path(tiktoken_ext.__file__).parent
        datas.append((str(tiktoken_ext_dir), "tiktoken_ext"))
        print(f"✓ Added tiktoken_ext data from: {tiktoken_ext_dir}")
    else:
        print("⚠ Warning: tiktoken_ext is a namespace package, skipping")
except (ImportError, AttributeError, TypeError) as e:
    print(f"⚠ Warning: Could not import tiktoken_ext: {e}")

# Add LiteLLM data files (CRITICAL for model routing and token counting)
try:
    import litellm
    if hasattr(litellm, '__file__') and litellm.__file__ is not None:
        litellm_dir = pathlib.Path(litellm.__file__).parent
        
        # Add the entire litellm_core_utils directory (includes tokenizers)
        litellm_core_utils = litellm_dir / "litellm_core_utils"
        if litellm_core_utils.exists():
            datas.append((str(litellm_core_utils), "litellm/litellm_core_utils"))
            print(f"✓ Added litellm_core_utils from: {litellm_core_utils}")
        
        # Add LiteLLM model cost data
        litellm_model_prices = litellm_dir / "model_prices_and_context_window.json"
        if litellm_model_prices.exists():
            datas.append((str(litellm_model_prices), "litellm"))
            print(f"✓ Added litellm model prices: {litellm_model_prices}")
        
        # Add proxy cost map if exists
        proxy_cost_map = litellm_dir / "proxy" / "proxy_cost_map.json"
        if proxy_cost_map.exists():
            datas.append((str(proxy_cost_map), "litellm/proxy"))
            print(f"✓ Added litellm proxy cost map: {proxy_cost_map}")
    else:
        print("⚠ Warning: litellm module has no __file__ attribute")
        
except (ImportError, AttributeError, TypeError) as e:
    print(f"⚠ Warning: Could not import litellm: {e}")

# Add vertexai.json if exists
vertexai_json = project_root / "vertexai.json"
if vertexai_json.exists():
    datas.append((str(vertexai_json), "."))
    print(f"✓ Added vertexai.json")

# Add mcp_config.json if exists
mcp_config = project_root / "mcp_config.json"
if mcp_config.exists():
    datas.append((str(mcp_config), "."))
    print(f"✓ Added mcp_config.json")

# Add global-bundle.pem if exists (SSL certificates)
global_pem = project_root / "global-bundle.pem"
if global_pem.exists():
    datas.append((str(global_pem), "."))
    print(f"✓ Added global-bundle.pem")

# Add any instruction or config directories
instructions_dir = project_root / "instructions"
if instructions_dir.exists():
    datas.append((str(instructions_dir), "instructions"))
    print(f"✓ Added instructions directory")

# Add .env file if exists (for development/testing)
env_file = project_root / ".env"
if env_file.exists():
    datas.append((str(env_file), "."))
    print(f"✓ Added .env file")

print(f"\n📦 Total data files to bundle: {len(datas)}")

analysis = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="agent-documentation-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Console mode for logging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="agent-documentation-backend",
)
