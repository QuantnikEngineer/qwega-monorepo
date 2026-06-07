import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import mermaid from "mermaid";
import {
  Box,
  TextField,
  IconButton,
  Typography,
  Paper,
  Button,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from "@mui/material";
import { Send, AttachFile, Close, Download, ExpandMore, CloudUpload } from "@mui/icons-material";
import API_CONFIG, { FULL_ACCESS_PROJECTS } from "../config/agentConfig";
import { PROVIDERS, LLM_MODELS } from "../config/llmConfig";
import CircularProgress from "@mui/material/CircularProgress";
// Import new components
import Header from "./layout/Header";
import PromptLibrary from "./PromptLibrary";
import { RepositorySection } from "./RepositorySection";
import SharePointFiles from "./SharePointFiles";
// import ConfluenceFiles from "./content/ConfluenceFiles"; // COMMENTED OUT: Confluence functionality not needed for now - uncomment if needed in future
import Resizer from "../utils/resizer";
import { useJWTAuth } from "../jwt-auth/contexts/JWTAuthContext";

// Initialize Mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
});

// Interfaces
interface Message {
  sender: "user" | "agent";
  text: string;
  files?: File[];
  timestamp?: string;
}

interface Repository {
  id: string;
  name: string;
  description?: string;
  language?: string;
  updated_at?: string;
  size?: number;
  project_id?: string;
  [key: string]: any;
}

interface SaveToSharePointRequest {
  file_content: string;
  file_name: string;
  folder_path?: string;
  site_name?: string;
}

const Agent: React.FC = () => {
  // JWT Authentication
  const { authData } = useJWTAuth();
  
  // Repository-related state
  const [repos, setRepos] = useState<Repository[]>([]);
  const [filteredRepos, setFilteredRepos] = useState<Repository[]>([]);
  const [isLoadingRepos, setIsLoadingRepos] = useState<boolean>(false);
  const [reposError, setReposError] = useState<string>("");
  const [selectedRepoIds, setSelectedRepoIds] = useState<string[]>([]);
  const [selectedRepoName, setSelectedRepoName] = useState<string | null>(null);
  const [generatedDocumentation, setGeneratedDocumentation] = useState<string>("");
  const [isGeneratingDoc, setIsGeneratingDoc] = useState<boolean>(false);
  const [savingToSharePoint, setSavingToSharePoint] = useState<boolean>(false);
  // COMMENTED OUT: Confluence state variables - Available for future use if needed
  // const [savingToConfluence, setSavingToConfluence] = useState<boolean>(false);
  // const [uploadedConfluencePageUrl, setUploadedConfluencePageUrl] = useState<string | null>(null);

  // LLM Provider and Model options - fetched from backend (GitHub config)
  const [providers, setProviders] = useState<{ key: string; label: string; default?: boolean }[]>([]);
  const [models, setModels] = useState<{ key: string; label: string; provider: string; default?: boolean }[]>([]);
  const [configLoaded, setConfigLoaded] = useState(false);
  
  // Default to AWS Bedrock (fallback if config not loaded)
  const defaultProvider = "aws_bedrock";
  const defaultModel = ""; // Will be set from fetched config

  const [selectedModel, setSelectedModel] = useState<string>(defaultModel);
  const [selectedProvider, setSelectedProvider] = useState<string>(defaultProvider);

  // Chat states
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "agent",
      text: "Hello! I'm an AI-powered Code To Documentation Agent. You are interacting with an AI system that helps generate comprehensive documentation and answer questions about your code. Select a context from the sidebar to get started.",
      timestamp: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }),
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Sidebar expansion states
  const [isPromptLibraryExpanded, setIsPromptLibraryExpanded] = useState(true);
  const [isRepoSectionExpanded, setIsRepoSectionExpanded] = useState(true);
  const [isSharePointExpanded, setIsSharePointExpanded] = useState(true);
  // COMMENTED OUT: Confluence expansion state - Available for future use if needed
  // const [isConfluenceExpanded, setIsConfluenceExpanded] = useState(true);

  // Panel sizing states
  const [leftPanelWidth, setLeftPanelWidth] = useState(450); // Default width for left panel
  const [rightPanelWidth, setRightPanelWidth] = useState(450); // Default width for right panel
  const containerRef = useRef<HTMLDivElement>(null);

  const baseUrl = window.location.origin + window.location.pathname.replace(/\/$/, "");

  // Helper function to construct API URLs
  const constructApiUrl = (endpoint: string) => {
    if (baseUrl.includes("localhost")) {
      return `${API_CONFIG.DOMAIN}:${API_CONFIG.PORT}${endpoint}`;
    } else {
      return `${baseUrl}${endpoint}`;
    }
  };

  // Helper function to get current time
  const getCurrentTime = () => {
    const now = new Date();
    return now.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit',
      hour12: true 
    });
  };

  // Resize handlers for Resizer component
  const handleLeftResize = (delta: number) => {
    setLeftPanelWidth((prevWidth) => {
      const newWidth = prevWidth + delta;
      return Math.max(300, Math.min(newWidth, window.innerWidth * 0.6));
    });
  };

  const handleRightResize = (delta: number) => {
    setRightPanelWidth((prevWidth) => {
      const newWidth = prevWidth - delta;
      return Math.max(300, Math.min(newWidth, window.innerWidth * 0.6));
    });
  };

  // Mermaid code block component
  const CodeBlock = ({ node, inline, className, children, ...props }: any) => {
    const elementRef = useRef<HTMLDivElement>(null);
    const match = /language-(\w+)/.exec(className || '');
    const language = match ? match[1] : '';

    useEffect(() => {
      if (language === 'mermaid' && elementRef.current && !inline) {
        const code = String(children).replace(/\n$/, '');
        const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
        
        try {
          mermaid.render(id, code).then(({ svg }) => {
            if (elementRef.current) {
              elementRef.current.innerHTML = svg;
            }
          }).catch((error) => {
            console.error('Mermaid render error:', error);
            if (elementRef.current) {
              elementRef.current.innerHTML = `<pre style="color: #d32f2f; background: #ffebee; padding: 12px; border-radius: 4px;">Error rendering diagram: ${error.message}</pre>`;
            }
          });
        } catch (error: any) {
          console.error('Mermaid error:', error);
        }
      }
    }, [language, children, inline]);

    if (language === 'mermaid' && !inline) {
      return (
        <div
          ref={elementRef}
          style={{
            maxWidth: '100%',
            overflow: 'auto',
            padding: '16px',
            margin: '16px 0',
            backgroundColor: '#fafafa',
            borderRadius: '8px',
            border: '1px solid #e0e0e0',
          }}
        >
          Loading diagram...
        </div>
      );
    }

    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  };

  // Fetch LLM config from backend (GitHub config via GITHUB_LLM_CONFIG secret)
  useEffect(() => {
    const loadLLMConfig = async () => {
      try {
        const url = constructApiUrl(API_CONFIG.ENDPOINTS.LLM_CONFIG);
        const resp = await fetch(url);
        if (!resp.ok) throw new Error("Failed to fetch /llm-config");
        const data = await resp.json();

        console.log("[DEBUG] Fetched LLM config:", data);

        const fetchedProviders = Array.isArray(data.providers) ? data.providers : [];
        const fetchedModels = Array.isArray(data.models) ? data.models : [];

        const providerObjs = fetchedProviders.map((p: any) =>
          typeof p === "string" ? { key: p, label: p } : p
        );
        const modelObjs = fetchedModels.map((m: any) =>
          typeof m === "string"
            ? {
                key: m,
                label: m,
                provider: m.includes("/") ? m.split("/")[0] : "",
              }
            : m
        );

        setProviders(providerObjs);
        setModels(modelObjs);
        setConfigLoaded(true);

        // Set default provider to AWS Bedrock (or first provider with default=true)
        const defaultProviderObj = providerObjs.find((p: any) => p.default) || providerObjs.find((p: any) => p.key === "aws_bedrock") || providerObjs[0];
        if (defaultProviderObj) {
          setSelectedProvider(defaultProviderObj.key);
          
          // Set default model for the selected provider
          const providerModels = modelObjs.filter((m: any) => m.provider === defaultProviderObj.key);
          if (providerModels.length > 0) {
            const defaultModelObj = providerModels.find((m: any) => m.default) || providerModels[0];
            if (defaultModelObj) {
              setSelectedModel(defaultModelObj.key);
            }
          }
        }
      } catch (e) {
        console.error("[ERROR] Failed to load LLM config:", e);
        // Use fallback config
        setProviders(PROVIDERS);
        setModels(LLM_MODELS);
        setConfigLoaded(true);
        const fallbackProvider = PROVIDERS.find((p: { key: string; label: string; default?: boolean }) => p.default) || PROVIDERS[0];
        if (fallbackProvider) {
          setSelectedProvider(fallbackProvider.key);
          const fallbackModel = LLM_MODELS.find((m: any) => m.provider === fallbackProvider.key && m.default) || LLM_MODELS.find((m: any) => m.provider === fallbackProvider.key);
          if (fallbackModel) {
            setSelectedModel(fallbackModel.key);
          }
        }
      }
    };

    loadLLMConfig();
  }, []);

  // When provider changes, set model to first available for that provider
  useEffect(() => {
    if (!selectedProvider || !models.length) return;

    const providerModels = models.filter((model: any) => model.provider === selectedProvider);
    if (providerModels.length > 0) {
      const defaultModelObj = providerModels.find((m: any) => m.default) || providerModels[0];
      setSelectedModel(defaultModelObj.key);
    }
  }, [selectedProvider, models]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isTyping]);

  // Fetch repositories on mount
  useEffect(() => {
    fetchRepositories();
  }, []);

  // Re-filter repositories when authData changes
  useEffect(() => {
    if (repos.length > 0) {
      const jwtProjectId = authData?.project?.id;
      const jwtProjectName = authData?.project?.name;
      
      // Check if project ID or name is in the full access list
      const isAllAccess = !jwtProjectId || 
        FULL_ACCESS_PROJECTS.includes(jwtProjectId.toLowerCase()) ||
        (jwtProjectName && FULL_ACCESS_PROJECTS.includes(jwtProjectName.toLowerCase()));
      
      if (isAllAccess) {
        console.log(`Showing all ${repos.length} repositories (project_id: ${jwtProjectId || 'not set'}, project_name: ${jwtProjectName || 'not set'}, full_access_list: ${FULL_ACCESS_PROJECTS.join(', ')})`);
        setFilteredRepos(repos);
      } else {
        // Filter by specific project_id for other projects
        const filtered = repos.filter((repo: Repository) => {
          return repo.project_id === jwtProjectId;
        });
        
        console.log(`Re-filtered ${filtered.length} repos out of ${repos.length} for project: ${jwtProjectId}`);
        setFilteredRepos(filtered);
      }
    }
  }, [authData, repos]);

  // SharePoint upload functions
  const handleUploadToSharePoint = async (content: string, repoName: string) => {
    setSavingToSharePoint(true);
    try {
      const fileName = `${repoName}_documentation_${new Date().toISOString().split('T')[0]}.docx`;
      
      const url = constructApiUrl(`${API_CONFIG.ENDPOINTS.UPLOAD_TO_SHAREPOINT}`);
      
      // Send raw content - backend will handle document formatting
      const documentContent = content;
      
      // Create form data as backend expects FormData
      const formData = new FormData();
      formData.append('file_content', documentContent);
      formData.append('file_name', fileName);
      formData.append('folder_path', 'BuilderAI');
      formData.append('site_name', 'demo566');

      const response = await fetch(url, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Failed to save to SharePoint: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.success) {
        // Add a success message to chat
        const successMessage: Message = {
          sender: "agent",
          text: `✅ **Documentation saved to SharePoint successfully!**\n\n📁 **File:** ${fileName}\n🔗 **[Open in SharePoint](${data.file_url})**\n\nYou can access the document from the SharePoint Files panel or click the link above.`,
          timestamp: getCurrentTime(),
        };
        setMessages((prev) => [...prev, successMessage]);
      } else {
        throw new Error(data.error || "Failed to save to SharePoint");
      }
    } catch (error: any) {
      console.error("Error saving to SharePoint:", error);
      const errorMessage: Message = {
        sender: "agent",
        text: `❌ **Error saving to SharePoint:** ${error.message}`,
        timestamp: getCurrentTime(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setSavingToSharePoint(false);
    }
  };

  // COMMENTED OUT: Confluence upload function - Available for future use if needed
  // const handleUploadToConfluence = async (content: string, repoName: string) => {
  //   setSavingToConfluence(true);
  //   try {
  //     const pageTitle = `${repoName}_Documentation_${new Date().toISOString().split('T')[0]}`;
  //     
  //     const url = constructApiUrl(`${API_CONFIG.ENDPOINTS.UPLOAD_TO_CONFLUENCE}`);
  //     
  //     const response = await fetch(url, {
  //       method: "POST",
  //       headers: {
  //         "Content-Type": "application/json",
  //       },
  //       body: JSON.stringify({
  //         page_title: pageTitle,
  //         content: content,
  //       }),
  //     });
  //
  //     if (!response.ok) {
  //       throw new Error(`Failed to upload to Confluence: ${response.statusText}`);
  //     }
  //
  //     const data = await response.json();
  //
  //     if (data.success) {
  //       // Set the uploaded page URL for the viewer
  //       setUploadedConfluencePageUrl(data.web_url);
  //       
  //       // Add a success message to chat
  //       const successMessage: Message = {
  //         sender: "agent",
  //         text: `✅ **Documentation uploaded to Confluence successfully!**\n\n📄 **Page:** ${data.page_title}\n🔗 **[Open in Confluence](${data.web_url})**\n\nYou can view the page in the Confluence panel on the left sidebar.`,
  //         timestamp: getCurrentTime(),
  //       };
  //       setMessages((prev) => [...prev, successMessage]);
  //     } else {
  //       throw new Error(data.error || "Failed to upload to Confluence");
  //     }
  //   } catch (error: any) {
  //     console.error("Error uploading to Confluence:", error);
  //     const errorMessage: Message = {
  //       sender: "agent",
  //       text: `❌ **Error uploading to Confluence:** ${error.message}`,
  //       timestamp: getCurrentTime(),
  //     };
  //     setMessages((prev) => [...prev, errorMessage]);
  //   } finally {
  //     setSavingToConfluence(false);
  //   }
  // };

  // Check if a message contains documentation
  const isDocumentationMessage = (message: Message) => {
    const text = message.text.toLowerCase();
    
    // Check for various documentation patterns that different LLMs might generate
    const documentationPatterns = [
      "# 📄 documentation for",
      "documentation for",
      "# documentation",
      "## documentation",
      "### documentation",
      "# overview",
      "## overview",
      "# introduction",
      "## introduction",
      "# project documentation",
      "# code documentation",
      "# technical documentation",
      "# api documentation",
      "# readme",
      "## readme",
      "# summary",
      "## summary",
      "# architecture",
      "## architecture",
      "# table of contents",
      "## table of contents",
    ];
    
    const hasDocumentationPattern = documentationPatterns.some(pattern => 
      text.includes(pattern)
    );
    
    // Also check for markdown headers with common documentation keywords
    const markdownHeaders = text.match(/^#+\s/gm);
    const hasMarkdownStructure = (
      (text.includes("#") && text.includes("##")) || // Has multiple heading levels
      (markdownHeaders && markdownHeaders.length >= 3) // Has at least 3 markdown headers
    );
    
    // Check for code blocks which are common in documentation
    const hasCodeBlocks = text.includes("```");
    
    return (
      message.sender === "agent" &&
      message.text.length > 500 && // Documentation messages are typically long
      (
        hasDocumentationPattern ||
        (hasMarkdownStructure && hasCodeBlocks) ||
        (text.includes("generate") && text.includes("documentation"))
      )
    );
  };

  // Fetch repositories from backend
  const fetchRepositories = async () => {
    setIsLoadingRepos(true);
    setReposError("");
    try {
      const url = constructApiUrl("/api/repos/list");
      const response = await fetch(url, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch repositories: ${response.statusText}`);
      }

      const data = await response.json();
      
      if (data.success) {
        const allRepos = data.repos || [];
        setRepos(allRepos);
        
        // Filter repositories based on JWT project_id
        const jwtProjectId = authData?.project?.id;
        const jwtProjectName = authData?.project?.name;
        
        // Check if project ID or name is in the full access list
        const isAllAccess = !jwtProjectId || 
          FULL_ACCESS_PROJECTS.includes(jwtProjectId.toLowerCase()) ||
          (jwtProjectName && FULL_ACCESS_PROJECTS.includes(jwtProjectName.toLowerCase()));
        
        if (isAllAccess) {
          console.log(`Showing all ${allRepos.length} repositories (project_id: ${jwtProjectId || 'not set'}, project_name: ${jwtProjectName || 'not set'}, full_access_list: ${FULL_ACCESS_PROJECTS.join(', ')})`);
          setFilteredRepos(allRepos);
        } else {
          // Filter by specific project_id for other projects
          const filtered = allRepos.filter((repo: Repository) => {
            // Match repos where project_id matches JWT project_id
            return repo.project_id === jwtProjectId;
          });
          
          console.log(`Filtered ${filtered.length} repos out of ${allRepos.length} for project: ${jwtProjectId}`);
          setFilteredRepos(filtered);
        }
      } else {
        setReposError(data.error || "Failed to fetch repositories");
      }
    } catch (error: any) {
      console.error("Error fetching repositories:", error);
      setReposError(error.message || "Failed to fetch repositories");
    } finally {
      setIsLoadingRepos(false);
    }
  };

  // Handle repository selection (toggle)
  const handleRepoClick = async (repoId: string) => {
    const repo = filteredRepos.find((r: Repository) => r.id === repoId);
    if (!repo) return;

    // Check if already selected
    const isCurrentlySelected = selectedRepoIds.includes(repoId);
    
    if (isCurrentlySelected) {
      // Deselect
      const newSelection = selectedRepoIds.filter((id: string) => id !== repoId);
      setSelectedRepoIds(newSelection);
      
      // Add a message indicating repo deselection
      // const deselectionMessage: Message = {
      //   sender: "agent",
      //   text: `❌ Deselected repository: **${repo.name || repoId}**\n\n${newSelection.length > 0 ? `${newSelection.length} repositories still selected.` : 'No repositories selected.'}`,
      //   timestamp: getCurrentTime(),
      // };
      // setMessages((prev) => [...prev, deselectionMessage]);
    } else {
      // Select
      const newSelection = [...selectedRepoIds, repoId];
      setSelectedRepoIds(newSelection);
      
      // Add a message indicating repo selection
      const selectionMessage: Message = {
        sender: "agent",
        text: `✅ Selected repository: **${repo.name || repoId}**\n\n${newSelection.length} repository(ies) selected. You can:\n- Create comprehensive docs\n- Ask me questions about ${newSelection.length === 1 ? 'this repository' : 'these repositories'}`,
        timestamp: getCurrentTime(),
      };
      setMessages((prev) => [...prev, selectionMessage]);
      
      // Update selected repo name for the most recently selected one
      setSelectedRepoName(repo.name || repoId);
    }
  };

  // Generate documentation for selected repository
  const handleGenerateDocumentation = async () => {
    if (selectedRepoIds.length === 0) {
      alert("Please select at least one repository first");
      return;
    }

    const selectedRepoId = selectedRepoIds[0]; // Use first selected repo for now
    const repo = filteredRepos.find((r: Repository) => r.id === selectedRepoId);
    const repoName = repo?.name || selectedRepoId;

    setIsGeneratingDoc(true);
    const loadingMessage: Message = {
      sender: "agent",
      text: "🔄 Generating documentation for **" + repoName + "**...\nThis may take a moment.",
      timestamp: getCurrentTime(),
    };
    setMessages((prev) => [...prev, loadingMessage]);

    try {
      const url = constructApiUrl("/api/repos/generate-documentation");
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_id: selectedRepoId,
          repo_name: repoName,
          llm_provider: selectedProvider,
          llm_model: selectedModel,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to generate documentation: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.success) {
        setGeneratedDocumentation(data.documentation);
        const docMessage: Message = {
          sender: "agent",
          text: `# 📄 Documentation for ${data.repo_name || data.repo_id}\n\n${data.documentation}`,
          timestamp: getCurrentTime(),
        };
        // Remove the loading message and add the documentation
        setMessages((prev) => [...prev.slice(0, -1), docMessage]);
      } else {
        throw new Error(data.error || "Failed to generate documentation");
      }
    } catch (error: any) {
      console.error("Error generating documentation:", error);
      const errorMessage: Message = {
        sender: "agent",
        text: `❌ Error generating documentation: ${error.message}`,
        timestamp: getCurrentTime(),
      };
      setMessages((prev) => [...prev.slice(0, -1), errorMessage]);
    } finally {
      setIsGeneratingDoc(false);
    }
  };

  // Helper function to read file content as text
  const readFileAsText = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = () => reject(new Error(`Failed to read file: ${file.name}`));
      reader.readAsText(file);
    });
  };

  // Send message or chat with repository
  const sendMessage = async () => {
    if (!input.trim() && selectedFiles.length === 0) return;

    const filesToProcess = [...selectedFiles];
    const userMessage: Message = {
      sender: "user",
      text: input,
      files: filesToProcess.length > 0 ? filesToProcess : undefined,
      timestamp: getCurrentTime(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setSelectedFiles([]);
    setIsTyping(true);

    try {
      // If files are uploaded, process them with or without repo context
      if (filesToProcess.length > 0) {
        // Check if any file is a zip file
        const hasZipFile = filesToProcess.some(file => file.name.toLowerCase().endsWith('.zip'));
        
        if (hasZipFile) {
          // Use FormData for zip file upload
          const zipFile = filesToProcess.find(file => file.name.toLowerCase().endsWith('.zip'));
          if (zipFile) {
            const formData = new FormData();
            formData.append('message', input || 'Please analyze the contents of this zip file');
            formData.append('llm_provider', selectedProvider);
            formData.append('llm_model', selectedModel);
            formData.append('user_id', authData?.user?.username || authData?.user?.email || 'anonymous');
            formData.append('tenant_id', authData?.project?.id || 'default');
            formData.append('session_id', `session_${Date.now()}`);
            formData.append('zip_file', zipFile);
            
            const url = constructApiUrl("/execute-chat-with-zip");
            const response = await fetch(url, {
              method: "POST",
              body: formData,
            });

            if (!response.ok) {
              const errorText = await response.text();
              console.error("Backend error:", response.status, errorText);
              throw new Error(`Failed to get response (${response.status}): ${errorText || response.statusText}`);
            }

            const data = await response.json();
            const responseContent = Array.isArray(data) && data.length > 0 
              ? data[0].content 
              : data.content || "No response received";
            
            const agentMessage: Message = {
              sender: "agent",
              text: responseContent,
              timestamp: getCurrentTime(),
            };
            setMessages((prev) => [...prev, agentMessage]);
          }
        } else {
          // Read file contents for non-zip files
          const fileContents = await Promise.all(
            filesToProcess.map(async (file) => {
              try {
                const content = await readFileAsText(file);
                return `--- File: ${file.name} ---\n${content}\n--- End of ${file.name} ---`;
              } catch (error) {
                return `--- File: ${file.name} (failed to read) ---`;
              }
            })
          );
          
          // Combine user message with file contents
          const messageWithFiles = input 
            ? `${input}\n\n${fileContents.join('\n\n')}`
            : `Please analyze the following file(s):\n\n${fileContents.join('\n\n')}`;

          // If a repository is also selected, include repo context
          if (selectedRepoIds.length > 0) {
            const selectedRepoId = selectedRepoIds[0];
            const repo = filteredRepos.find((r: Repository) => r.id === selectedRepoId);
            const url = constructApiUrl("/api/repos/chat");
            const response = await fetch(url, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                repo_id: selectedRepoId,
                repo_name: repo?.name || selectedRepoId,
                message: messageWithFiles,
                llm_provider: selectedProvider,
                llm_model: selectedModel,
              }),
            });

            if (!response.ok) {
              throw new Error(`Failed to get response: ${response.statusText}`);
            }

            const data = await response.json();
            const agentMessage: Message = {
              sender: "agent",
              text: data.content || "No response received",
              timestamp: getCurrentTime(),
            };
            setMessages((prev) => [...prev, agentMessage]);
          } else {
            // No repo selected, use general chat endpoint with file contents
            const url = constructApiUrl("/execute-chat");
            const response = await fetch(url, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                content: messageWithFiles,
                message: messageWithFiles,
                llm_provider: selectedProvider,
                llm_model: selectedModel,
                user_id: authData?.user?.username || authData?.user?.email || "anonymous",
                tenant_id: authData?.project?.id || "default",
                session_id: `session_${Date.now()}`,
              }),
            });

            if (!response.ok) {
              throw new Error(`Failed to get response: ${response.statusText}`);
            }

            const data = await response.json();
            // Handle response array format from execute-chat
            const responseContent = Array.isArray(data) && data.length > 0 
              ? data[0].content 
              : data.content || "No response received";
            
            const agentMessage: Message = {
              sender: "agent",
              text: responseContent,
              timestamp: getCurrentTime(),
            };
            setMessages((prev) => [...prev, agentMessage]);
          }
        }
      } else if (selectedRepoIds.length > 0) {
        // No files, but repo is selected - chat about repository
        const selectedRepoId = selectedRepoIds[0];
        const repo = filteredRepos.find((r: Repository) => r.id === selectedRepoId);
        const url = constructApiUrl("/api/repos/chat");
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            repo_id: selectedRepoId,
            repo_name: repo?.name || selectedRepoId,
            message: input,
            llm_provider: selectedProvider,
            llm_model: selectedModel,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to get response: ${response.statusText}`);
        }

        const data = await response.json();
        const agentMessage: Message = {
          sender: "agent",
          text: data.content || "No response received",
          timestamp: getCurrentTime(),
        };
        setMessages((prev) => [...prev, agentMessage]);
      } else {
        // No files and no repo selected - prompt user to select context
        const agentMessage: Message = {
          sender: "agent",
          text: "Please select a repository from the sidebar or upload a file to ask questions about it.",
          timestamp: getCurrentTime(),
        };
        setMessages((prev) => [...prev, agentMessage]);
      }
    } catch (error: any) {
      console.error("Error sending message:", error);
      const errorMessage: Message = {
        sender: "agent",
        text: `Error: ${error.message}`,
        timestamp: getCurrentTime(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setSelectedFiles(Array.from(e.target.files));
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev: File[]) => prev.filter((_: File, i: number) => i !== index));
  };

  // Download documentation as markdown
  const handleDownloadDocumentation = () => {
    if (!generatedDocumentation) return;

    const blob = new Blob([generatedDocumentation], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedRepoName || "repository"}_documentation.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };
  
  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100vh", bgcolor: "#f5f5f5" }}>
      {/* Header */}
      <Header
        selectedProvider={selectedProvider}
        selectedModel={selectedModel}
        onProviderChange={setSelectedProvider}
        onModelChange={setSelectedModel}
      />

      <Box ref={containerRef} sx={{ display: "flex", flex: 1, overflow: "hidden", opacity: 1 }}>
        {/* Left Panel - Prompt Library + GitHub Repository */}
        <Box
          sx={{
            width: `${leftPanelWidth}px`,
            minWidth: '300px',
            boxShadow: "none",
            overflowY: "auto",
            p: 1,
            ml: 1,
            mr: 0.5,
            display: "flex",
            flexDirection: "column",
            gap: 2,
            "&::-webkit-scrollbar": {
              width: "0px",
              display: "none",
            },
          }}
        >
          {/* Prompt Library */}
          <PromptLibrary
            isExpanded={isPromptLibraryExpanded}
            onToggle={() => setIsPromptLibraryExpanded(!isPromptLibraryExpanded)}
            onFaqClick={(prompt: string) => setInput(prompt)}
          />

          {/* Repository Section */}
          <RepositorySection
            repos={filteredRepos}
            isLoadingRepos={isLoadingRepos}
            reposError={reposError}
            selectedRepoIds={selectedRepoIds}
            isExpanded={isRepoSectionExpanded}
            onToggle={() => setIsRepoSectionExpanded(!isRepoSectionExpanded)}
            onRepoClick={handleRepoClick}
            onRefreshRepos={fetchRepositories}
            projectId={authData?.project?.id}
            projectName={authData?.project?.name}
          />

          {/* Generate Documentation Button */}
          {/* {selectedRepoId && (
            <Button
              variant="contained"
              fullWidth
              onClick={handleGenerateDocumentation}
              disabled={isGeneratingDoc}
              startIcon={isGeneratingDoc ? <CircularProgress size={20} sx={{ color: "#fff" }} /> : <Download />}
              sx={{
                mt: 2,
                py: 2,
                textTransform: "none",
                fontSize: "15px",
                fontWeight: 600,
                background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
                color: "#ffffff",
                borderRadius: "12px",
                boxShadow: "0 4px 14px 0 rgba(99, 102, 241, 0.3)",
                transition: "all 0.3s ease",
                "&:hover": {
                  background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
                  boxShadow: "0 6px 20px 0 rgba(99, 102, 241, 0.4)",
                  transform: "translateY(-2px)",
                },
                "&:disabled": {
                  background: "linear-gradient(135deg, #cbd5e1 0%, #94a3b8 100%)",
                  color: "#ffffff",
                },
              }}
            >
              {isGeneratingDoc ? "Generating Documentation..." : "Generate Documentation"}
            </Button>
          )} */}

          {/* Download Documentation Button */}
          {generatedDocumentation && (
            <Button
              variant="outlined"
              fullWidth
              onClick={handleDownloadDocumentation}
              startIcon={<Download />}
              sx={{
                py: 2,
                textTransform: "none",
                fontSize: "15px",
                fontWeight: 600,
                borderRadius: "12px",
                borderColor: "#6366f1",
                color: "#6366f1",
                borderWidth: "2px",
                transition: "all 0.3s ease",
                "&:hover": {
                  borderColor: "#4f46e5",
                  backgroundColor: "rgba(99, 102, 241, 0.05)",
                  borderWidth: "2px",
                  transform: "translateY(-2px)",
                  boxShadow: "0 4px 12px 0 rgba(99, 102, 241, 0.2)",
                },
              }}
            >
              Download Documentation (MD)
            </Button>
          )}
        </Box>

        {/* Left Resizer */}
        <Resizer onResize={handleLeftResize} isVertical={true} />

        {/* Main Chat Area - Middle Panel */}
        <Box
          sx={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            bgcolor: "#f5f5f5",
            borderRadius: "16px",
            mx: 1,
            my: 0.5,
            mb: 1,
            overflow: "hidden",
            boxShadow: '0 12px 40px rgba(0, 0, 0, 0.18)',
          }}
        >
          {/* Chat Messages */}
          <Box
            sx={{
              flex: 1,
              overflowY: "auto",
              p: 2,
              bgcolor: "white",
              display: "flex",
              flexDirection: "column",
              gap: 1.5,
              "&::-webkit-scrollbar": {
                width: "8px",
              },
              "&::-webkit-scrollbar-track": {
                background: "#f1f1f1",
                borderRadius: "4px",
              },
              "&::-webkit-scrollbar-thumb": {
                background: "#c1c1c1",
                borderRadius: "4px",
                "&:hover": {
                  background: "#a8a8a8",
                },
              },
            }}
          >
            {messages.map((message, index) => (
              <Box
                key={index}
                sx={{
                  alignSelf: message.sender === "user" ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                  mb: 1,
                }}
              >
                <Paper
                  elevation={0}
                  sx={{
                    p: 1.5,
                    bgcolor: message.sender === "user" ? "#6b46c1" : "#f8f9fa",
                    color: message.sender === "user" ? "white" : "#1f2937",
                    borderRadius: message.sender === "user" 
                      ? "16px 16px 4px 16px" 
                      : "16px 16px 16px 4px",
                    boxShadow: message.sender === "user" 
                      ? "0 1px 4px rgba(107, 70, 193, 0.2)" 
                      : "0 1px 4px rgba(0, 0, 0, 0.06)",
                    border: message.sender === "user" 
                      ? "none" 
                      : "1px solid #e5e7eb",
                    overflow: 'auto',
                    wordBreak: 'break-word',
                  }}
                >
                  <ReactMarkdown
                    rehypePlugins={[rehypeSanitize, rehypeHighlight]}
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code: CodeBlock,
                    }}
                  >
                    {message.text}
                  </ReactMarkdown>

                  {/* Add Save to SharePoint and Confluence buttons inside the message for documentation */}
                  {isDocumentationMessage(message) && (
                    <Box sx={{ mt: 1.5, display: "flex", gap: 1, flexWrap: "wrap" }}>
                      <Button
                        variant="contained"
                        size="small"
                        onClick={() => handleUploadToSharePoint(message.text, selectedRepoName || "repository")}
                        disabled={savingToSharePoint}
                        startIcon={
                          savingToSharePoint ? (
                            <CircularProgress size={12} sx={{ color: "white" }} />
                          ) : (
                            <CloudUpload />
                          )
                        }
                        sx={{
                          fontSize: "12px",
                          fontWeight: 500,
                          textTransform: "none",
                          color: "white",
                          bgcolor: "info.main",
                          "&:hover": {
                            bgcolor: savingToSharePoint ? "info.main" : "info.dark",
                          },
                          "&:disabled": {
                            bgcolor: "info.main",
                            color: "white",
                            opacity: 0.6,
                          },
                        }}
                      >
                        {savingToSharePoint ? "Uploading..." : "Upload to SharePoint"}
                      </Button>
                      {/* COMMENTED OUT: Confluence upload button - Available for future use if needed
                      <Button
                        variant="contained"
                        size="small"
                        onClick={() => handleUploadToConfluence(message.text, selectedRepoName || "repository")}
                        disabled={savingToConfluence}
                        startIcon={
                          savingToConfluence ? (
                            <CircularProgress size={12} sx={{ color: "white" }} />
                          ) : (
                            <CloudUpload />
                          )
                        }
                        sx={{
                          fontSize: "12px",
                          fontWeight: 500,
                          textTransform: "none",
                          color: "white",
                          bgcolor: "#0052CC", // Atlassian Confluence blue
                          "&:hover": {
                            bgcolor: savingToConfluence ? "#0052CC" : "#0747A6",
                          },
                          "&:disabled": {
                            bgcolor: "#0052CC",
                            color: "white",
                            opacity: 0.6,
                          },
                        }}
                      >
                        {savingToConfluence ? "Uploading..." : "Upload to Confluence"}
                      </Button>
                      */}
                    </Box>
                  )}
                </Paper>
                {message.timestamp && (
                  <Typography
                    variant="caption"
                    sx={{
                      color: "#9ca3af",
                      fontSize: "10px",
                      textAlign: message.sender === "user" ? "right" : "left",
                      mt: 0.5,
                      display: "block",
                      ml: message.sender === "agent" ? 0 : 0,
                    }}
                  >
                    {message.timestamp}
                  </Typography>
                )}
              </Box>
            ))}

            {isTyping && (
              <Box
                sx={{
                  alignSelf: "flex-start",
                  maxWidth: "80%",
                  mb: 2,
                }}
              >
                <Paper
                  sx={{
                    p: 2,
                    bgcolor: "white",
                    borderRadius: "16px 16px 16px 4px",
                    boxShadow: 1,
                  }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      AI is typing
                    </Typography>
                    <Box sx={{ display: "flex", gap: 0.5 }}>
                      {[0, 1, 2].map((i) => (
                        <Box
                          key={i}
                          sx={{
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            bgcolor: "primary.main",
                            animation: `pulse 1.4s ease-in-out ${i * 0.2}s infinite`,
                            "@keyframes pulse": {
                              "0%, 80%, 100%": { opacity: 0.3 },
                              "40%": { opacity: 1 },
                            },
                          }}
                        />
                      ))}
                    </Box>
                  </Box>
                </Paper>
              </Box>
            )}

            <div ref={chatEndRef} />
          </Box>

          {/* File Preview */}
          {selectedFiles.length > 0 && (
            <Box sx={{ p: 2, backgroundColor: "white", borderTop: "1px solid #e5e7eb" }}>
              <Box
                sx={{
                  mb: 1,
                  p: 1.5,
                  bgcolor: "#f1f5f9",
                  borderRadius: 2,
                  border: "1px solid #cbd5e1",
                }}
              >
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    mb: 1,
                  }}
                >
                  <Typography
                    variant="subtitle2"
                    color="#475569"
                    fontWeight={600}
                  >
                    Selected files:
                  </Typography>
                  <Typography
                    component="span"
                    onClick={() => setSelectedFiles([])}
                    sx={{
                      cursor: "pointer",
                      color: "#dc2626",
                      fontSize: "12px",
                      fontWeight: 500,
                      "&:hover": { textDecoration: "underline" },
                    }}
                  >
                    Clear All
                  </Typography>
                </Box>
                {selectedFiles.map((file, index) => (
                  <Box
                    key={index}
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      py: 0.5,
                    }}
                  >
                    <Typography
                      variant="body2"
                      sx={{ flex: 1, color: "#64748b" }}
                    >
                      📄 {file.name}
                    </Typography>
                    <IconButton
                      size="small"
                      onClick={() => handleRemoveFile(index)}
                      sx={{ ml: 1, color: "#dc2626" }}
                    >
                      <Close sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Box>
                ))}
              </Box>
            </Box>
          )}

          {/* Input Area */}
          <Box
            sx={{
              p: 2,
              bgcolor: "white",
              borderTop: "1px solid #e5e7eb",
            }}
          >
            <Box
              sx={{
                display: "flex",
                gap: 1,
                alignItems: "flex-end",
                bgcolor: "#f8fafc",
                p: 1,
                borderRadius: 3,
                border: "2px solid #e2e8f0",
                "&:focus-within": {
                  borderColor: "#6b46c1",
                  boxShadow: "0 0 0 3px rgba(107, 70, 193, 0.1)",
                },
              }}
            >
              <input
                type="file"
                ref={fileInputRef}
                style={{ display: "none" }}
                onChange={handleFileChange}
                multiple
                accept=".zip"
              />
              
              <IconButton
                onClick={() => fileInputRef.current?.click()}
                sx={{
                  color: "#6b46c1",
                  "&:hover": { bgcolor: "#f3f4f6" },
                }}
              >
                <AttachFile />
              </IconButton>

              <TextField
                fullWidth
                multiline
                maxRows={4}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={
                  selectedRepoIds.length > 0
                    ? `Ask about ${selectedRepoIds.length === 1 ? 'the selected repository' : selectedRepoIds.length + ' repositories'} or request documentation...`
                    : "Select a repository to start chatting..."
                }
                disabled={isTyping}
                sx={{
                  flex: 1,
                  "& .MuiOutlinedInput-root": {
                    bgcolor: "white",
                    borderRadius: 2,
                    "& fieldset": {
                      border: "none",
                    },
                  },
                }}
                size="small"
              />

              <IconButton
                onClick={sendMessage}
                disabled={(!input.trim() && selectedFiles.length === 0) || isTyping}
                sx={{
                  bgcolor: "#6b46c1",
                  color: "white",
                  "&:hover": {
                    bgcolor: "#553c9a",
                  },
                  "&:disabled": {
                    bgcolor: "#9ca3af",
                    color: "white",
                  },
                }}
              >
                <Send />
              </IconButton>
            </Box>
            <Typography
              variant="caption"
              sx={{
                color: "#94a3b8",
                fontSize: "11px",
                mt: 0.5,
                textAlign: "center",
                display: "block",
              }}
            >
              Allowed formats: .zip (compressed folder)
            </Typography>
          </Box>
        </Box>

        {/* Right Resizer */}
        <Resizer onResize={handleRightResize} isVertical={true} />

        {/* Right Panel - Documents Section */}
        <Box
          sx={{
            width: `${rightPanelWidth}px`,
            minWidth: '300px',
            boxShadow: "none",
            overflowY: "auto",
            p: 1,
            ml: 0.5,
            mr: 1,
            display: "flex",
            flexDirection: "column",
            gap: 2,
            "&::-webkit-scrollbar": {
              width: "0px",
              display: "none",
            },
          }}
        >
          {/* COMMENTED OUT: Confluence Documents Section - Available for future use if needed
          <Accordion
            expanded={isConfluenceExpanded}
            onChange={() => setIsConfluenceExpanded(!isConfluenceExpanded)}
            style={{
              boxShadow: "0 2px 8px rgba(0, 0, 0, 0.1)",
              border: "none",
              borderRadius: "8px",
              marginBottom: "8px",
              backgroundColor: "#ffffff",
            }}
          >
            <AccordionSummary
              expandIcon={
                <ExpandMore style={{ fontSize: "20px", color: "#666" }} />
              }
              style={{
                padding: "8px 12px",
                backgroundColor: "#ffffff",
                borderRadius: "8px 8px 0 0",
                minHeight: "40px",
              }}
            >
              <Box display="flex" alignItems="center" gap={1.5}>
                <Typography
                  variant="subtitle1"
                  fontWeight="600"
                  color="#0052CC"
                >
                  📄 Confluence Documents
                </Typography>
              </Box>
            </AccordionSummary>

            <AccordionDetails
              style={{ padding: "8px 12px", backgroundColor: "#f8f9fa" }}
            >
              <Box sx={{ 
                maxHeight: "400px", 
                overflowY: "auto",
                "&::-webkit-scrollbar": {
                  width: "8px",
                },
                "&::-webkit-scrollbar-track": {
                  background: "#f1f1f1",
                  borderRadius: "4px",
                },
                "&::-webkit-scrollbar-thumb": {
                  background: "#c1c1c1",
                  borderRadius: "4px",
                  "&:hover": {
                    background: "#a8a8a8",
                  },
                },
              }}>
                <ConfluenceFiles />
              </Box>
            </AccordionDetails>
          </Accordion>
          */}

          {/* SharePoint Files Section */}
          <Accordion
            expanded={isSharePointExpanded}
            onChange={() => setIsSharePointExpanded(!isSharePointExpanded)}
            style={{
              boxShadow: "0 2px 8px rgba(0, 0, 0, 0.1)",
              border: "none",
              borderRadius: "8px",
              marginBottom: "8px",
              backgroundColor: "#ffffff",
            }}
          >
            <AccordionSummary
              expandIcon={
                <ExpandMore style={{ fontSize: "20px", color: "#666" }} />
              }
              style={{
                padding: "8px 12px",
                backgroundColor: "#ffffff",
                borderRadius: "8px 8px 0 0",
                minHeight: "40px",
              }}
            >
              <Box display="flex" alignItems="center" gap={1.5}>
                <Typography
                  variant="subtitle1"
                  fontWeight="600"
                  color="#2c3e50"
                >
                  📁 SharePoint Documents
                </Typography>
              </Box>
            </AccordionSummary>

            <AccordionDetails
              style={{ padding: "8px 12px", backgroundColor: "#f8f9fa" }}
            >
              <Box sx={{ 
                maxHeight: "400px", 
                overflowY: "auto",
                "&::-webkit-scrollbar": {
                  width: "8px",
                },
                "&::-webkit-scrollbar-track": {
                  background: "#f1f1f1",
                  borderRadius: "4px",
                },
                "&::-webkit-scrollbar-thumb": {
                  background: "#c1c1c1",
                  borderRadius: "4px",
                  "&:hover": {
                    background: "#a8a8a8",
                  },
                },
              }}>
                <SharePointFiles />
              </Box>
            </AccordionDetails>
          </Accordion>
        </Box>
      </Box>
    </Box>
  );
};

export default Agent;

