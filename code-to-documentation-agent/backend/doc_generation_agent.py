"""
Documentation Generation Agent - Generates project documentation from repository chunks
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from litellm_client import LiteLLMRunner
from secrets_manager import get_secret
import asyncio

logger = logging.getLogger(__name__)

class DocumentationAgent:
    """Agent that generates comprehensive documentation from repository code chunks"""
    
    def __init__(self):
        """Initialize the documentation generation agent"""
        self.llm_runner = None
        # Token limits per model (leaving 20% buffer for safety)
        self.max_tokens_per_batch = {
            "gpt-4o": 100000,  # 128K limit, use 100K for safety
            "gpt-4": 6000,
            "gpt-3.5-turbo": 12000,
            "gemini-2.0-flash-001": 800000,  # Very large context
            "claude-3-5-sonnet": 160000
        }
        self.default_max_tokens = 80000  # Default safe limit
    
    def _initialize_llm(self, provider: str = "azure_openai", model: str = "gpt-4o"):
        """
        Initialize LLM client with the specified provider and model
        
        Args:
            provider: LLM provider (azure_openai, openai, etc.)
            model: Model name to use
        """
        try:
            # Get the model name from environment if available
            # get_secret(secret_key, auth_provider=None, default_value="")
            azure_model_name = get_secret("AZURE_OPENAI_MODEL_NAME", None, model)
            
            # Initialize LiteLLM runner (it will handle environment setup internally)
            self.llm_runner = LiteLLMRunner(
                provider=provider,
                model=azure_model_name
            )
            
            logger.info(f"Initialized LLM with provider={provider}, model={azure_model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text (approximately 4 chars per token)
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
    
    def _extract_file_structure(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract file structure and metadata from chunks
        
        Args:
            chunks: List of code chunks
            
        Returns:
            Dictionary with file structure information
        """
        files_info = {}
        
        for chunk in chunks:
            if isinstance(chunk, dict):
                file_path = chunk.get("file_path", chunk.get("path", "Unknown"))
                content = chunk.get("content", chunk.get("code", chunk.get("text", "")))
                file_extension = chunk.get("file_extension", "")
                
                if file_path and file_path != "Unknown":
                    if file_path not in files_info:
                        files_info[file_path] = {
                            "path": file_path,
                            "extension": file_extension,
                            "content_preview": content[:500] if content else "",
                            "size": len(content) if content else 0
                        }
        
        return files_info
    
    def _generate_project_structure(self, files_info: Dict[str, Any]) -> str:
        """
        Generate a tree-like project structure from file information
        
        Args:
            files_info: Dictionary of file information
            
        Returns:
            Formatted project structure string
        """
        # Sort files by path for organized display
        sorted_files = sorted(files_info.keys())
        
        structure = "# Project Structure\n\n```\n"
        
        # Build directory tree
        dir_tree = {}
        for file_path in sorted_files:
            parts = file_path.split('/')
            current = dir_tree
            for part in parts[:-1]:  # directories
                if part not in current:
                    current[part] = {}
                current = current[part]
            # Add file to final directory
            if parts:
                current[parts[-1]] = None  # None indicates it's a file
        
        # Generate tree representation
        def build_tree(node, prefix="", is_last=True):
            items = sorted(node.items(), key=lambda x: (x[1] is not None, x[0]))
            result = ""
            
            for i, (name, children) in enumerate(items):
                is_last_item = (i == len(items) - 1)
                connector = "└── " if is_last_item else "├── "
                
                if children is None:  # File
                    result += f"{prefix}{connector}{name}\n"
                else:  # Directory
                    result += f"{prefix}{connector}{name}/\n"
                    extension = "    " if is_last_item else "│   "
                    result += build_tree(children, prefix + extension, is_last_item)
            
            return result
        
        structure += build_tree(dir_tree)
        structure += "```\n"
        
        return structure
    
    def _generate_file_descriptions(self, files_info: Dict[str, Any], chunks: List[Dict[str, Any]]) -> str:
        """
        Generate descriptions for files based on their content
        
        Args:
            files_info: Dictionary of file information
            chunks: List of code chunks
            
        Returns:
            Formatted file descriptions
        """
        descriptions = "## File Descriptions\n\n"
        
        # Group files by directory for better organization
        files_by_dir = {}
        for file_path in sorted(files_info.keys()):
            parts = file_path.split('/')
            if len(parts) > 1:
                dir_name = '/'.join(parts[:-1])
            else:
                dir_name = "root"
            
            if dir_name not in files_by_dir:
                files_by_dir[dir_name] = []
            files_by_dir[dir_name].append(file_path)
        
        # Generate descriptions
        for dir_name, files in sorted(files_by_dir.items()):
            descriptions += f"\n**{dir_name}/**\n"
            for file_path in files:
                file_name = file_path.split('/')[-1]
                extension = files_info[file_path].get("extension", "")
                
                # Infer file type from extension
                file_type = self._infer_file_type(file_name, extension)
                descriptions += f"- `{file_name}` - {file_type}\n"
        
        return descriptions
    
    def _infer_file_type(self, filename: str, extension: str) -> str:
        """Infer file purpose from name and extension"""
        filename_lower = filename.lower()
        
        # Common file patterns
        if filename_lower == "main.py" or filename_lower == "app.py":
            return "Main application entry point"
        elif filename_lower == "models.py":
            return "Data models and schemas"
        elif filename_lower == "config.py" or filename_lower == "settings.py":
            return "Configuration settings"
        elif filename_lower == "requirements.txt":
            return "Python dependencies"
        elif filename_lower == "package.json":
            return "Node.js dependencies and scripts"
        elif filename_lower == "dockerfile":
            return "Docker container configuration"
        elif filename_lower == "readme.md":
            return "Project documentation"
        elif filename_lower.startswith("test_"):
            return "Test suite"
        elif "service" in filename_lower:
            return "Service layer implementation"
        elif "client" in filename_lower:
            return "Client/API integration"
        elif "utils" in filename_lower or "helper" in filename_lower:
            return "Utility functions"
        
        # Extension-based inference
        if extension == ".py":
            return "Python module"
        elif extension in [".ts", ".tsx"]:
            return "TypeScript/React component"
        elif extension in [".js", ".jsx"]:
            return "JavaScript module"
        elif extension == ".yaml" or extension == ".yml":
            return "YAML configuration"
        elif extension == ".json":
            return "JSON configuration/data"
        elif extension == ".md":
            return "Markdown documentation"
        elif extension == ".css":
            return "Stylesheet"
        elif extension == ".html":
            return "HTML template"
        
        return f"Source file ({extension})" if extension else "File"
    
    def _format_chunks_for_analysis(self, chunks: List[Dict[str, Any]], max_chunks: Optional[int] = None) -> str:
        """
        Format repository chunks into a structured text for analysis
        
        Args:
            chunks: List of code chunks from the repository
            max_chunks: Maximum number of chunks to format (None = all)
            
        Returns:
            Formatted string representation of the chunks
        """
        formatted_text = "# Repository Code Structure\n\n"
        
        chunks_to_process = chunks[:max_chunks] if max_chunks else chunks
        
        for i, chunk in enumerate(chunks_to_process, 1):
            formatted_text += f"## Chunk {i}\n\n"
            
            # Handle different chunk formats
            if isinstance(chunk, dict):
                # Extract relevant fields
                file_path = chunk.get("file_path", chunk.get("path", "Unknown"))
                content = chunk.get("content", chunk.get("code", chunk.get("text", "")))
                chunk_type = chunk.get("type", "code")
                
                formatted_text += f"**File:** `{file_path}`\n"
                formatted_text += f"**Type:** {chunk_type}\n\n"
                formatted_text += f"```\n{content}\n```\n\n"
                
            elif isinstance(chunk, str):
                formatted_text += f"```\n{chunk}\n```\n\n"
            else:
                formatted_text += f"```\n{str(chunk)}\n```\n\n"
        
        if max_chunks and len(chunks) > max_chunks:
            formatted_text += f"\n\n*[Note: Showing {max_chunks} of {len(chunks)} total chunks]*\n"
        
        return formatted_text
    
    def _create_chunk_batches(self, chunks: List[Dict[str, Any]], max_tokens: int) -> List[List[Dict[str, Any]]]:
        """
        Split chunks into batches that fit within token limits
        
        Args:
            chunks: List of all chunks
            max_tokens: Maximum tokens per batch
            
        Returns:
            List of chunk batches
        """
        batches = []
        current_batch = []
        current_tokens = 0
        
        # Reserve tokens for system prompt and formatting (roughly 2000 tokens)
        available_tokens = max_tokens - 2000
        
        for chunk in chunks:
            # Estimate tokens for this chunk
            if isinstance(chunk, dict):
                content = chunk.get("content", chunk.get("code", chunk.get("text", "")))
                file_path = chunk.get("file_path", "")
                chunk_text = f"{file_path}\n{content}"
            else:
                chunk_text = str(chunk)
            
            chunk_tokens = self._estimate_tokens(chunk_text)
            
            # If adding this chunk exceeds limit, start new batch
            if current_tokens + chunk_tokens > available_tokens and current_batch:
                batches.append(current_batch)
                current_batch = [chunk]
                current_tokens = chunk_tokens
            else:
                current_batch.append(chunk)
                current_tokens += chunk_tokens
        
        # Add remaining chunks
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    async def _generate_batch_summary(
        self,
        batch_chunks: List[Dict[str, Any]],
        batch_number: int,
        total_batches: int,
        repo_display_name: str
    ) -> str:
        """
        Generate a summary for a single batch of chunks
        
        Args:
            batch_chunks: Chunks in this batch
            batch_number: Current batch number (1-indexed)
            total_batches: Total number of batches
            repo_display_name: Name of the repository
            
        Returns:
            Summary text for this batch
        """
        formatted_chunks = self._format_chunks_for_analysis(batch_chunks)
        
        system_prompt = """You are a technical documentation analyst. Analyze the provided code chunks and create a structured summary focusing on:

1. **Key Components**: Main files, classes, functions, and modules
2. **Technologies**: Programming languages, frameworks, libraries used
3. **Architecture Patterns**: Design patterns, architectural decisions
4. **Features**: What functionality is implemented
5. **Configuration**: Environment variables, config files, setup requirements
6. **APIs/Interfaces**: Endpoints, public APIs, interfaces exposed

Be concise but comprehensive. Focus on facts extracted from the code."""

        user_prompt = f"""Analyze batch {batch_number} of {total_batches} from repository **{repo_display_name}**:

{formatted_chunks}

Provide a structured summary of the key components, technologies, and features found in this batch."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self.llm_runner.completion(messages)
        
        if response.get("success"):
            return response.get("response", "")
        else:
            logger.warning(f"Batch {batch_number} summary failed: {response.get('error')}")
            return f"*Batch {batch_number} analysis incomplete*"
    
    async def generate_documentation(
        self,
        repo_id: str,
        repo_name: Optional[str],
        chunks: List[Dict[str, Any]],
        provider: str = "azure_openai",
        model: str = "gpt-4o"
    ) -> str:
        """
        Generate comprehensive documentation from repository chunks.
        Handles large repositories by processing in batches.
        
        Args:
            repo_id: Repository ID
            repo_name: Repository name (optional)
            chunks: List of code chunks from the repository
            provider: LLM provider to use
            model: LLM model to use
            
        Returns:
            Generated documentation in markdown format
        """
        try:
            # Initialize LLM if not already initialized
            if not self.llm_runner:
                self._initialize_llm(provider, model)
            
            repo_display_name = repo_name or repo_id
            total_chunks = len(chunks)
            
            # Extract file structure from all chunks (for project structure section)
            logger.info(f"Extracting file structure from {total_chunks} chunks")
            files_info = self._extract_file_structure(chunks)
            project_structure = self._generate_project_structure(files_info)
            logger.info(f"Generated project structure with {len(files_info)} files")
            
            # Get max tokens for this model
            max_tokens = self.max_tokens_per_batch.get(model, self.default_max_tokens)
            
            logger.info(f"Generating documentation for repo {repo_id} with {total_chunks} chunks")
            logger.info(f"Using model {model} with max {max_tokens} tokens per batch")
            
            # Check if we need to batch process
            formatted_all = self._format_chunks_for_analysis(chunks)
            estimated_tokens = self._estimate_tokens(formatted_all)
            
            logger.info(f"Estimated total tokens: {estimated_tokens}")
            
            # If small enough, process in single call
            if estimated_tokens <= max_tokens:
                logger.info("Repository fits in single batch - processing directly")
                return await self._generate_single_batch_documentation(
                    chunks, repo_id, repo_display_name, project_structure, files_info
                )
            
            # Large repository - use batch processing
            logger.info(f"Repository too large ({estimated_tokens} tokens) - using batch processing")
            
            # Split into batches
            batches = self._create_chunk_batches(chunks, max_tokens)
            total_batches = len(batches)
            
            logger.info(f"Split into {total_batches} batches")
            
            # Process each batch to get summaries
            batch_summaries = []
            for i, batch in enumerate(batches, 1):
                logger.info(f"Processing batch {i}/{total_batches} ({len(batch)} chunks)")
                summary = await self._generate_batch_summary(
                    batch, i, total_batches, repo_display_name
                )
                batch_summaries.append(f"## Batch {i} Analysis\n\n{summary}")
            
            # Combine all batch summaries
            combined_summaries = "\n\n---\n\n".join(batch_summaries)
            
            # Generate final documentation from summaries
            logger.info("Generating final documentation from batch summaries")
            final_doc = await self._generate_final_documentation(
                combined_summaries, repo_id, repo_display_name, total_chunks, total_batches,
                project_structure, files_info
            )
            
            logger.info(f"Successfully generated documentation for repo {repo_id}")
            return final_doc
            
        except Exception as e:
            logger.error(f"Error generating documentation for repo {repo_id}: {e}")
            raise Exception(f"Failed to generate documentation: {str(e)}")
    
    async def _generate_single_batch_documentation(
        self,
        chunks: List[Dict[str, Any]],
        repo_id: str,
        repo_display_name: str,
        project_structure: str,
        files_info: Dict[str, Any]
    ) -> str:
        """Generate documentation for small repos that fit in one batch"""
        
        formatted_chunks = self._format_chunks_for_analysis(chunks)
        
        # Create file descriptions from chunks
        file_descriptions = self._generate_file_descriptions(files_info, chunks)
        
        system_prompt = """You are a technical documentation expert. Given a GitHub repository's code structure and content, generate complete, professional project documentation in clear Markdown format.

Your output MUST include the following sections in this exact order:

1. **Project Overview** – Summarize what the project does, its purpose, and main features.

2. **Project Structure** – Show a detailed tree structure of the repository with explanations:
   - Use proper tree formatting with ├── and └── symbols
   - For EACH file and directory, provide a comment explaining its purpose (use # comments)
   - Group related files together
   - Example format:
     ```
     repository_name/
     ├── backend/                  # Backend API and services
     │   ├── main.py              # Main entry point for FastAPI application
     │   ├── models.py            # Pydantic models for validation
     │   └── ...                  # Other backend modules
     ├── frontend/                 # Frontend React application
     │   ├── src/
     │   │   ├── App.tsx          # Main React component
     │   │   └── components/      # React UI components
     │   └── package.json         # Node.js dependencies
     └── README.md                 # Project documentation
     ```

3. **Architecture & Design** – Explain the tech stack, system design, and key components. Include architectural patterns and design decisions.

4. **Setup & Installation** – Step-by-step instructions for installing dependencies, configuring environments, and running setup commands. Include prerequisites.

5. **Usage / How to Run** – Commands or code examples for running or using the project. Include sample inputs/outputs or API examples if applicable.

6. **Testing** – How to run tests, tools used, and any CI/CD details. Include test commands and coverage information if available.

7. **Deployment** – How to deploy locally, via Docker, or to cloud services. Include deployment configurations.

8. **Contributing Guidelines** – Explain contribution workflow, coding standards, and issue reporting. Include pull request process.

9. **License** – Include the project's license details or note if license information is not found.

10. **Acknowledgements / Credits** – List contributors, libraries, and references used in the project.

11. **Future Work / Roadmap** – Mention upcoming features, improvements, or known limitations.

**CRITICAL REQUIREMENTS FOR PROJECT STRUCTURE SECTION:**
- The Project Structure section MUST be detailed and comprehensive
- Every file and directory MUST have a description/comment
- Use the tree format shown in the example above
- Infer file purposes from their names, extensions, and content
- Group logically (backend/, frontend/, config/, tests/, etc.)
- Be specific about what each file does, not generic

**Additional Requirements:**
- Format the documentation cleanly in Markdown using proper headers (#, ##, ###)
- Use bullet points, code blocks (```), and tables where helpful
- Be professional, clear, and comprehensive
- Include actual code examples from the repository where relevant"""

        user_prompt = f"""Generate comprehensive project documentation for the repository: **{repo_display_name}** (ID: {repo_id})

**Project Structure Reference:**
{project_structure}

**File Descriptions:**
{file_descriptions}

**Code Chunks for Analysis:**
{formatted_chunks}

Using the project structure and file information above, generate detailed, professional documentation. Pay special attention to creating a comprehensive Project Structure section with descriptions for every file and directory."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self.llm_runner.completion(messages)
        
        if response.get("success"):
            return response.get("response", "")
        else:
            raise Exception(f"LLM completion failed: {response.get('error', 'Unknown error')}")
    
    async def _generate_final_documentation(
        self,
        batch_summaries: str,
        repo_id: str,
        repo_display_name: str,
        total_chunks: int,
        total_batches: int,
        project_structure: str,
        files_info: Dict[str, Any]
    ) -> str:
        """Generate final comprehensive documentation from batch summaries"""
        
        # Create file descriptions
        file_descriptions = self._generate_file_descriptions(files_info, [])
        
        system_prompt = """You are a technical documentation expert. You have been provided with analysis summaries from different parts of a large repository. Your task is to synthesize these summaries into a single, cohesive, professional README.md document.

Your output MUST include the following sections in this exact order:

1. **Project Overview** – Summarize what the project does, its purpose, and main features based on all batch analyses.

2. **Project Structure** – Show a detailed tree structure of the repository with explanations:
   - Use proper tree formatting with ├── and └── symbols
   - For EACH file and directory, provide a comment explaining its purpose (use # comments)
   - Group related files together
   - Example format:
     ```
     repository_name/
     ├── backend/                  # Backend API and services
     │   ├── main.py              # Main entry point for FastAPI application
     │   ├── models.py            # Pydantic models for validation
     │   └── ...                  # Other backend modules
     ├── frontend/                 # Frontend React application
     │   ├── src/
     │   │   ├── App.tsx          # Main React component
     │   │   └── components/      # React UI components
     │   └── package.json         # Node.js dependencies
     └── README.md                 # Project documentation
     ```

3. **Architecture & Design** – Explain the overall tech stack, system design, and key components. Include architectural patterns and design decisions.

4. **Setup & Installation** – Step-by-step instructions for installing dependencies, configuring environments, and running setup commands. Include prerequisites.

5. **Usage / How to Run** – Commands or code examples for running or using the project. Include sample inputs/outputs or API examples if applicable.

6. **Testing** – How to run tests, tools used, and any CI/CD details. Include test commands and coverage information if available.

7. **Deployment** – How to deploy locally, via Docker, or to cloud services. Include deployment configurations.

8. **Contributing Guidelines** – Explain contribution workflow, coding standards, and issue reporting. Include pull request process.

9. **License** – Include the project's license details or note if license information is not found.

10. **Acknowledgements / Credits** – List contributors, libraries, and references used in the project.

11. **Future Work / Roadmap** – Mention upcoming features, improvements, or known limitations.

**CRITICAL REQUIREMENTS FOR PROJECT STRUCTURE SECTION:**
- The Project Structure section MUST be detailed and comprehensive
- Every file and directory MUST have a description/comment
- Use the tree format shown in the example above
- Infer file purposes from their names, extensions, and the batch analyses
- Group logically (backend/, frontend/, config/, tests/, etc.)
- Be specific about what each file does, not generic

**Important:**
- Synthesize information from all batches into a cohesive narrative
- Don't mention "batches" or "summaries" in the final output
- Present as if you analyzed the entire codebase
- Be professional, clear, and comprehensive
- Use proper Markdown formatting"""

        user_prompt = f"""Generate comprehensive project documentation for the repository: **{repo_display_name}** (ID: {repo_id})

This repository contains {total_chunks} code chunks analyzed from {total_batches} different sections.

**Project Structure Reference:**
{project_structure}

**File Descriptions:**
{file_descriptions}

**Analysis Summaries from Repository Sections:**

{batch_summaries}

Based on the project structure and analyses above, generate a complete, professional README.md document. Pay special attention to creating a comprehensive Project Structure section with descriptions for every file and directory."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self.llm_runner.completion(messages)
        
        if response.get("success"):
            return response.get("response", "")
        else:
            raise Exception(f"Final documentation generation failed: {response.get('error', 'Unknown error')}")
    
    async def chat_about_repository(
        self,
        repo_id: str,
        repo_name: Optional[str],
        chunks: List[Dict[str, Any]],
        user_question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Answer questions about a repository based on its code chunks.
        Handles large repositories by using smart sampling or summarization.
        
        Args:
            repo_id: Repository ID
            repo_name: Repository name (optional)
            chunks: List of code chunks from the repository
            user_question: User's question about the repository
            conversation_history: Previous conversation messages
            provider: LLM provider to use
            model: LLM model to use
            
        Returns:
            AI response to the user's question
        """
        try:
            # Initialize LLM if not already initialized
            if not self.llm_runner:
                self._initialize_llm(provider, model)
            logger.info(f"Initialized LLM with provider={provider}, model={model}")
            repo_display_name = repo_name or repo_id
            total_chunks = len(chunks)
            
            # Get max tokens for this model
            max_tokens = self.max_tokens_per_batch.get(model, self.default_max_tokens)
            
            # Reserve tokens for system prompt, question, and response (roughly 5000 tokens)
            available_tokens = max_tokens - 5000
            
            logger.info(f"Processing chat question for repo {repo_id} with {total_chunks} chunks")
            
            # Check if we can include all chunks
            formatted_all = self._format_chunks_for_analysis(chunks)
            estimated_tokens = self._estimate_tokens(formatted_all)
            
            # If small enough, use all chunks
            if estimated_tokens <= available_tokens:
                logger.info("Using all chunks for chat context")
                formatted_chunks = formatted_all
            else:
                # Large repo - sample or limit chunks intelligently
                logger.info(f"Repo too large ({estimated_tokens} tokens) - sampling chunks")
                
                # Strategy: Take first 50 chunks (usually contains main files, README, config)
                # and random sample from the rest to give broad coverage
                sample_size = min(100, total_chunks)
                
                # Take first 50 chunks (usually most important)
                sampled_chunks = chunks[:50]
                
                # Add random samples from the rest if we have more
                if total_chunks > 50:
                    import random
                    remaining_chunks = chunks[50:]
                    additional_samples = min(50, len(remaining_chunks))
                    sampled_chunks.extend(random.sample(remaining_chunks, additional_samples))
                
                formatted_chunks = self._format_chunks_for_analysis(sampled_chunks, max_chunks=sample_size)
                logger.info(f"Sampled {len(sampled_chunks)} chunks for chat context")
            
            # Detect architecture questions
            architecture_keywords = ["architecture", "component", "structure", "design", "diagram", "main components"]
            is_architecture = any(keyword in user_question.lower() for keyword in architecture_keywords)
            
            if is_architecture:
                system_prompt = f"""You are an expert software architect. You have access to code from: **{repo_display_name}** (ID: {repo_id}).

**CRITICAL: You MUST include a Mermaid diagram when discussing architecture!**

Your role is to:
- Provide comprehensive architecture analysis with visual Mermaid diagrams
- Explain ALL major components and how they interact
- Show complete system architecture with clear layers

**REQUIRED FORMAT:**

## Architecture Overview

[2-3 paragraphs explaining the architecture, tech stack, and design patterns]

### System Architecture Diagram

```mermaid
graph TD
    A[Frontend/UI Layer] --> B[Backend API]
    B --> C[Authentication]
    B --> D[Business Logic]
    D --> E[Service 1]
    D --> F[Service 2]
    E --> G[Database]
    F --> H[External APIs]
```

### Component Details

**Frontend Layer:**
- **Component 1** - Description
- **Component 2** - Description

**Backend Layer:**
- **API Gateway** - Description
- **Business Logic** - Description

**Services Layer:**
- **Service 1** - Description
- **Service 2** - Description

**Data Layer:**
- **Database** - Description

**External Integrations:**
- **External API** - Description

### Data Flow

[Explain how data flows through the system]

### Technology Stack

[List technologies: React, FastAPI, etc.]

**CRITICAL:** The Mermaid diagram MUST:
- Use ```mermaid code blocks
- Show 8-12 major components
- Include all layers (Frontend, Backend, Services, Data, External)
- Use clear labels like [Component Name]
- Show arrows for data flow

Note: For large repos, you have a sample. Provide best analysis based on available code."""
            else:
                system_prompt = f"""You are a helpful AI assistant with expertise in code analysis and software documentation. You have access to code from the repository: **{repo_display_name}** (ID: {repo_id}).

Your role is to:
- Answer questions about the repository's code structure and functionality
- Explain how different components work
- Provide code examples and usage guidance
- Help users understand the project architecture
- Suggest improvements or best practices when asked

Be concise but thorough in your responses. Use code examples when relevant.

Note: For large repositories, you may have access to a representative sample of the codebase. If you don't have specific details, acknowledge this and provide your best answer based on available information."""

            # Build context with repository chunks
            context = f"""# Repository Context: {repo_display_name}

{formatted_chunks}

---

User Question: {user_question}"""

            # Format messages for LiteLLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ]
            
            response = await self.llm_runner.completion(messages)
            
            # Extract response
            if response.get("success"):
                answer = response.get("response", "")
            else:
                raise Exception(f"LLM completion failed: {response.get('error', 'Unknown error')}")
            
            logger.info(f"Successfully generated chat response for repo {repo_id}")
            return answer
            
        except Exception as e:
            logger.error(f"Error processing chat question for repo {repo_id}: {e}")
            raise Exception(f"Failed to process question: {str(e)}")

# Create singleton instance
doc_agent = DocumentationAgent()

