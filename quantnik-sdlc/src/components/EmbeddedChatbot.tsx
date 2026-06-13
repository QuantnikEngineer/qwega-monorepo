import { useState, useRef, useEffect, forwardRef, useImperativeHandle, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Send, Loader2, Trash2, ChevronDown, ChevronRight, Table2, ExternalLink, Pencil, Copy, Bot as BotIcon, User as UserIcon, AlertTriangle, Settings, Upload, RotateCcw, Lock, Unlock, GitBranch, FolderOpen, X, Code2, ArrowDownToLine, ArrowUpFromLine, Link, Sparkles, Check } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { ScrollArea } from './ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { submitBulkTestCases, generateJobName, type CronJob } from '../services/cronJobApi';
import { clearTokens } from '../auth/tokenManager';
import { apiFetch } from '../services/apiClient';
import { DroidTerminal, type DroidTerminalEvent } from './DroidTerminal';
import projectConfigSettings from '../constants/projectConfigSettings.json';
import '../styles/chatbot.css';

// ---- Orchestrator Chat API ----
const GATEWAY_BASE_URL = (import.meta.env.VITE_GATEWAY_URL || '').replace(/\/$/, '');
const gatewayUrl = (path: string) => (GATEWAY_BASE_URL ? `${GATEWAY_BASE_URL}${path}` : path);
const CHAT_ENDPOINT = gatewayUrl('/api/v1/chat');
export const CHAT_STREAM_ENDPOINT = gatewayUrl('/api/v1/chat/stream');
const CHAT_SIMPLE_ENDPOINT = gatewayUrl('/api/v1/chat/simple');
const BRAIN_QUERY_ENDPOINT = gatewayUrl('/api/brain/v1/query');
const BRD_GENERATE_ENDPOINT = gatewayUrl('/api/planning/api/v1/generate-brd');
const BRD_UPDATE_ENDPOINT = gatewayUrl('/api/planning/api/v1/update-brd');
const HEALTH_ENDPOINT = gatewayUrl('/health');
const CHAT_TIMEOUT_MS = 900000;

/** Sanitize filename to only allow alphanumeric, underscores, hyphens, and dots. */
function sanitizeFilename(name: string): string {
  return name.replace(/[^a-zA-Z0-9._-]/g, '_');
}

// ---- QUANTNIK Code Assistant (Droid) API — routed via Gateway → SDLC Orchestrator ----
// All Code Assistant operations now go through the SDLC Orchestrator for centralized routing
const QUANTNIK_CODE_ASSISTANT_CONFIG_ENDPOINT = gatewayUrl('/api/v1/code-assistant/config');
const QUANTNIK_REPO_LOCK_ENDPOINT = gatewayUrl('/api/v1/code-assistant/repo/lock');
const QUANTNIK_REPO_SYNC_ENDPOINT = gatewayUrl('/api/v1/code-assistant/repo/sync');
const QUANTNIK_MODELS_ENDPOINT = gatewayUrl('/api/v1/code-assistant/models');
const QUANTNIK_CODE_ASSISTANT_SESSION_ENDPOINT = gatewayUrl('/api/v1/code-assistant/session');

interface GatewayErrorPayload {
  code?: string;
  message?: string;
  detail?: string;
  request_id?: string;
}

function parseGatewayError(rawBody: string, status: number): { message: string; code?: string; shouldRedirect: boolean } {
  let parsed: GatewayErrorPayload = {};
  try {
    parsed = JSON.parse(rawBody) as GatewayErrorPayload;
  } catch {
    parsed = {};
  }

  const code = parsed.code;
  const requestId = parsed.request_id ? ` (request id: ${parsed.request_id})` : '';
  const fallback = parsed.message || parsed.detail || `Server error: ${status}`;

  if (code === 'missing_token') {
    return {
      code,
      shouldRedirect: true,
      message: `Your session is missing. Please sign in again.${requestId}`,
    };
  }

  if (code === 'invalid_token') {
    return {
      code,
      shouldRedirect: true,
      message: `Your session is invalid. Please sign in again.${requestId}`,
    };
  }

  if (code === 'token_expired') {
    return {
      code,
      shouldRedirect: true,
      message: `Your session expired and refresh failed. Please sign in again.${requestId}`,
    };
  }

  return { code, shouldRedirect: false, message: `${fallback}${requestId}` };
}

interface ChatRequestPayload {
  session_id: string;
  message: string;
  context?: Record<string, any>;
  history?: Array<{ role: string; content: string }>;
  explicit_intent?: string;
  target_orchestrator?: string;
}

interface SuggestedActionItem {
  action: string;
  intent?: string;
  orchestrator?: string;
  confidence?: number;
}

interface ChatResponsePayload {
  session_id: string;
  message: string;
  status: 'success' | 'error' | 'pending';
  nextagentflow: string;
  data?: {
    intent?: string;
    entities?: Record<string, any>;
    action_results?: any[];
    child_response?: any;
    push_results?: Record<string, string[]>;
    [key: string]: any;
  };
  suggested_actions: SuggestedActionItem[];
  metadata?: Record<string, any>;
  routed_to?: string;
  timestamp?: string;
}

// ---- SSE Streaming Event Types ----
type MilestoneStage = 'received' | 'thinking' | 'analyzing' | 'routing' | 'planning' | 'executing' | 'calling_agent' | 'processing' | 'synthesizing' | 'complete' | 'error';

interface MilestoneEvent {
  type: 'milestone';
  stage: MilestoneStage;
  title: string;
  description: string;
  progress: number;
  icon: string;
  animation?: string;
  details?: Record<string, any>;
  duration_hint_ms?: number | null;
  timestamp: string;
}

interface ChildAgentEvent {
  type: 'child_agent_event';
  source_agent: string;
  original_event: any;
  timestamp: string;
}

interface StreamingResponse {
  type: 'response';
  session_id: string;
  message: string;
  status: 'success' | 'error';
  nextagentflow?: string;
  data?: ChatResponsePayload['data'];
  suggested_actions: SuggestedActionItem[];
  total_duration_ms?: number;
}

interface StreamingError {
  type: 'error';
  stage: string;
  title: string;
  message: string;
  icon: string;
  source_agent?: string;
  timestamp: string;
}

interface CodeAssistantChunk {
  type: 'code_assistant_chunk';
  event: 'message' | 'stdout' | 'stderr';
  text: string;
  role?: string;
  data?: any;
  _forwarded_from?: string;
  _source_orchestrator?: string;
}

type SSEEvent = MilestoneEvent | ChildAgentEvent | StreamingResponse | StreamingError | CodeAssistantChunk | DroidTerminalEvent;

interface Message {
  id: string;
  type: 'bot' | 'user' | 'error';
  content: string;
}

interface SelectedJiraStory {
  id: string;
  key: string;
  url: string;
  summary: string;
  description: string;
  epicKey?: string;
  epicSummary?: string;
}

interface EmbeddedChatbotProps {
  isDarkMode?: boolean;
  onAgentChange?: (nextagentflow: string) => void;
  selectedPromptText?: string;
  selectedNextagentflow?: string;
  // BRD mandatory fields from parent (read-only, derived from admin team members)
  projectName?: string;
  productOwner?: { name: string; role: string; email: string };
  /** Business stakeholders for BRD agent (from Team Modal, NOT auth RBAC members) */
  businessStakeholders?: { name: string; role: string; email: string }[];
  /** Jira user stories selected in the left sidebar */
  selectedJiraStories?: SelectedJiraStory[];
  /** Jira test cases selected in the left sidebar */
  selectedTestCasesFromJira?: { key: string; summary: string; description: string; url: string; steps?: { Step: string; Expected: string }[] }[];
  /** Whether test cases are currently being fetched from Jira */
  isLoadingTestCases?: boolean;
  /** Callback to lock/unlock Jira panel selection */
  onJiraSelectionLock?: (locked: boolean) => void;
  /** Confluence page URL selected from the left sidebar */
  selectedConfluencePageUrl?: string;
  /** Callback to clear Jira & Confluence selections in the left sidebar */
  onClearSelections?: () => void;
  /** Callback when BRD is generated â€” triggers Confluence refresh and auto-select */
  onBrdGenerated?: (brdLink: string, brdProjectName: string) => void;
  /** Callback when user stories are generated â€” triggers Jira refresh and auto-select epics */
  onUserStoryGenerated?: (epicKeys: string[]) => void | Promise<void>;
  /** Callback when validated user stories are saved â€” triggers Jira refresh and auto-select stories in respective epics */
  onValidatedUserStorySaved?: (epicKeys: string[]) => void | Promise<void>;
  /** Callback when a cron/long-running job is submitted */
  onCronJobSubmitted?: (job: CronJob) => void;
  /** Callback to open the Project Settings modal */
  onOpenProjectSettings?: () => void;
  /** Callback when processing state changes (loading/streaming) */
  onProcessingChange?: (isProcessing: boolean) => void;
  /** Callback to open the Manage Project Team modal */
  onOpenProjectTeamModal?: () => void;
  /** Backend Harness repo tool config (from useProjectToolConfig in parent) */
  harnessToolConfig?: { ready: boolean; config: Record<string, string | undefined>; secretKeys?: string[] };
  /** Project ID for secure credential lookup from auth-service */
  projectId?: string | null;
  /** Quantnik Brain: when ON, the RAG service also searches the non-critical KB */
  quantnikBrainIncludeNonCritical?: boolean;
}

export interface EmbeddedChatbotRef {
  clearAllFields: () => void;
  clearFieldsForPromptSwitch: () => void;
  triggerContextFabricProceed: (payload: { url?: string; files?: File[]; projectName?: string }) => Promise<void>;
}

export const EmbeddedChatbot = forwardRef<EmbeddedChatbotRef, EmbeddedChatbotProps>(({
  isDarkMode, 
  onAgentChange, 
  selectedPromptText, 
  selectedNextagentflow,
  projectName: externalProjectName,
  productOwner: externalProductOwner,
  businessStakeholders: externalStakeholders,
  selectedJiraStories = [],
  selectedTestCasesFromJira = [],
  isLoadingTestCases = false,
  onJiraSelectionLock,
  selectedConfluencePageUrl,
  onClearSelections,
  onBrdGenerated,
  onUserStoryGenerated,
  onValidatedUserStorySaved,
  onCronJobSubmitted,
  onOpenProjectSettings,
  onProcessingChange,
  onOpenProjectTeamModal,
  harnessToolConfig,
  projectId,
  quantnikBrainIncludeNonCritical = true,
}, ref) => {
  // Session ID for orchestrator conversation memory
  const [sessionId, setSessionId] = useState<string | null>(() => {
    return sessionStorage.getItem('chatbot_session_id');
  });
  // Brain panel conversation continuity — persists across messages for multi-turn RAG queries
  const [brainConversationId, setBrainConversationId] = useState<string | null>(null);

  const messageIdCounter = useRef(0);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      type: 'bot',
      content: `Welcome! I am quantnik agent. How can I help you?`,
    },
  ]);

  // Fetch session ID from backend on mount if not cached
  useEffect(() => {
    if (sessionId) return;

    const fetchSessionId = async () => {
      try {
        const res = await apiFetch(CHAT_SIMPLE_ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: 'hello', context: {} }),
        });
        const data = await res.json();
        if (data.status === 'success' && data.session_id) {
          sessionStorage.setItem('chatbot_session_id', data.session_id);
          setSessionId(data.session_id);
        } else {
          throw new Error('Invalid response');
        }
      } catch {
        const fallback = `sess_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
        sessionStorage.setItem('chatbot_session_id', fallback);
        setSessionId(fallback);
      }
    };

    fetchSessionId();
  }, []);
  const [queryInputText, setQueryInputText] = useState('');
  const [createUserStoryText, setCreateUserStoryText] = useState('');

  const [createUserStoryBrowse, setCreateUserStoryBrowse] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [inputTestTextE2E, setInputTestTextE2E] = useState('');
  const [instructionsE2E, setInstructionsE2E] = useState('');
  const [userStoryNameE2E, setUserStoryNameE2E] = useState('');

  const [scenarioTypes, setScenarioTypes] = useState('');
  const [scenarioTypesOptions, setScenarioTypesOptions] = useState<string[]>([]);
  const [selectedScenarioTypes, setSelectedScenarioTypes] = useState<string[]>([]);
  const [isAllScenarioTypesSelected, setIsAllScenarioTypesSelected] = useState(false);
  const [testScenarios, setTestScenarios] = useState('');
  const [testCaseFormat, setTestCaseFormat] = useState('');
  const [testCases, setTestCases] = useState('');
  const [frameworkType, setFrameworkType] = useState('');
  const [language, setLanguage] = useState('');
  const [scriptGenerationType, setScriptGenerationType] = useState('');
  const [showCombinationsPopup, setShowCombinationsPopup] = useState(false);
  const [selectedTcKey, setSelectedTcKey] = useState('');
  const [selectedTcSummary, setSelectedTcSummary] = useState('');
  const [selectedTcDescription, setSelectedTcDescription] = useState('');
  const [testCaseValidationError, setTestCaseValidationError] = useState('');
  const [testCaseStoryDropdownOpen, setTestCaseStoryDropdownOpen] = useState(false);
  const [selectedTestCaseKeys, setSelectedTestCaseKeys] = useState<Set<string>>(new Set());
  const [testDataOutputFormat, setTestDataOutputFormat] = useState<'json' | 'excel'>('json');
  // Store generated test cases from API responses for the dropdown
  const [generatedTestCasesList, setGeneratedTestCasesList] = useState<{ id: string; name: string; description: string; raw: any }[]>([]);

  // Supported Framework Ãƒâ€” Language Ãƒâ€” Generation Type combinations
  const SUPPORTED_COMBINATIONS = [
    { framework: 'Selenium BDD',    language: 'Java',       generationTypes: ['Greenfield', 'Brownfield'] },
    { framework: 'Selenium BDD',    language: 'C#',         generationTypes: ['Greenfield', 'Brownfield'] },
    { framework: 'Playwright',      language: 'JavaScript', generationTypes: ['Greenfield', 'Brownfield'] },
    { framework: 'Playwright',      language: 'TypeScript', generationTypes: ['Greenfield', 'Brownfield'] },
    { framework: 'Selenium TestNG', language: 'Java',       generationTypes: ['Greenfield', 'Brownfield'] },
    { framework: 'Selenium TestNG', language: 'Python',     generationTypes: ['Greenfield', 'Brownfield'] },
    { framework: 'Selenium TestNG', language: 'C#',         generationTypes: ['Greenfield', 'Brownfield'] },
    { framework: 'Selenium TestNG', language: 'JavaScript', generationTypes: ['Greenfield', 'Brownfield'] },
  ];
  const [nextagentflow, setNextagentflow] = useState('');
  const [lastIntent, setLastIntent] = useState<string>('');
  const [lastSentMessage, setLastSentMessage] = useState<string>('');
  const [chosenJiraStoryKey, setChosenJiraStoryKey] = useState<string | null>(null);

  // Modal state for editing individual story descriptions
  const [storyEditModalOpen, setStoryEditModalOpen] = useState(false);
  const [editingStoryKey, setEditingStoryKey] = useState<string | null>(null);
  const [editingStoryText, setEditingStoryText] = useState('');
  // Stores user-edited descriptions per story key
  const [editedStoryDescriptions, setEditedStoryDescriptions] = useState<Record<string, string>>({});
  // SharePoint URL for User Manual agent
  const [sharepointUrl, setSharepointUrl] = useState('');
  const [nextSuggestedAction, setNextSuggestedAction] = useState('');
  const [lastSuggestedActions, setLastSuggestedActions] = useState<SuggestedActionItem[]>([]);
  const [userStoryUri, setUserStoryUri] = useState('');
  const [brdUri, setBrdUri] = useState('');
  const [finalBrdConfluenceLink, setFinalBrdConfluenceLink] = useState(() => {
    return sessionStorage.getItem('brdConfluenceLink') || '';
  });
  const [isLoading, setIsLoading] = useState(false);
  const [showUserStoryUri, setShowUserStoryUri] = useState(false);
  const [showBrdUri, setShowBrdUri] = useState(false);
  const [isOrchestratorActive, setIsOrchestratorActive] = useState<boolean | null>(null);
  // Track if we're awaiting user confirmation to reuse existing BRD for user story creation
  const [awaitingBrdUserStoryConfirm, setAwaitingBrdUserStoryConfirm] = useState(false);
  const [awaitingValidateUserStoryConfirm, setAwaitingValidateUserStoryConfirm] = useState(false);
  const [awaitingTestCaseConfirm, setAwaitingTestCaseConfirm] = useState(false);
  const [isRefreshingJiraEpics, setIsRefreshingJiraEpics] = useState(false);

  // Validated user stories for intentOfUpdateUserStory flow
  const [validatedStories, setValidatedStories] = useState<any>(null);
  const [validatedStoryEditModalOpen, setValidatedStoryEditModalOpen] = useState(false);
  const [editingValidatedKey, setEditingValidatedKey] = useState<string | null>(null);
  const [editingValidatedText, setEditingValidatedText] = useState('');
  const [editedValidatedDescriptions, setEditedValidatedDescriptions] = useState<Record<string, string>>({});
  const [editedValidatedTitles, setEditedValidatedTitles] = useState<Record<string, string>>({});
  const [isSavingValidatedStory, setIsSavingValidatedStory] = useState(false);
  const [lastValidationPayload, setLastValidationPayload] = useState<any>(null);
  // jira_dictionary from validate-userstory response: keys like QUANTNIKAIDEMO531, values are validated text
  const [jiraDictionary, setJiraDictionary] = useState<Record<string, string>>({});
  // new_jira_createlist from validate-userstory response: list of new user stories to be created
 const [newJiraCreateList, setNewJiraCreateList] = useState<Record<string, Array<{title: string; story: string}>>>({});
  // Track which new stories are selected via checkboxes (by index)
   const [selectedNewJiraStories, setSelectedNewJiraStories] = useState<Set<string>>(new Set());
  // Epic issue key from validate-userstory payload for creating new stories
  const [epicIssueKey, setEpicIssueKey] = useState<string>('');
  // Dynamic label for user story text area (changes after validation)
  const [userStoryTextLabel, setUserStoryTextLabel] = useState<string>('User Story Text');

  // Comparison modal state for intentOfUpdateUserStory flow
  const [comparisonModalOpen, setComparisonModalOpen] = useState(false);
  const [comparisonStoryKey, setComparisonStoryKey] = useState<string | null>(null);
  const [comparisonJiraTitle, setComparisonJiraTitle] = useState('');
  const [comparisonJiraDescription, setComparisonJiraDescription] = useState('');
  const [comparisonValidatedText, setComparisonValidatedText] = useState('');
  const [comparisonValidatedTitle, setComparisonValidatedTitle] = useState('');
  // New story edit modal state
  const [newStoryEditModalOpen, setNewStoryEditModalOpen] = useState(false);
  const [editingNewStoryCompoundKey, setEditingNewStoryCompoundKey] = useState<string | null>(null);
  const [editingNewStoryText, setEditingNewStoryText] = useState('');
  const [editedNewStoryTexts, setEditedNewStoryTexts] = useState<Record<string, string>>({});
  // Track discarded (deleted) existing stories
  const [discardedExistingStories, setDiscardedExistingStories] = useState<Set<string>>(new Set());
  
  // New BRD parameters
  const [projectName, setProjectName] = useState(() => {
    // Initialize from sessionStorage if available
    const stored = sessionStorage.getItem('projectName');
    return stored || '';
  });
  // --- Project Name Override (BRD demo support) ---
  // Allows PO/BA to temporarily edit the project name for demo runs without
  // mutating auth-governed data. See PROJECT_NAME_OVERRIDE.md for removal guide.
  const isProjectNameOverriddenRef = useRef(false);
  const [isEditingProjectName, setIsEditingProjectName] = useState(false);
  const [brdStakeholders, setBrdStakeholders] = useState<{ name: string; role: string; email: string }[]>([
    { name: '', role: 'Product Owner', email: '' },
    { name: '', role: 'Business Sponsor', email: '' },
    { name: '', role: 'Business SME', email: '' },
    { name: '', role: 'Process Analyst', email: '' },
    { name: '', role: 'UX Researcher', email: '' },
    { name: '', role: 'Solution Architect', email: '' },
    { name: '', role: 'Compliance', email: '' },
    { name: '', role: 'Information Security Officer', email: '' }
  ]);
  const [activeRoleDropdown, setActiveRoleDropdown] = useState<number | null>(null);
  const [brdFiles, setBrdFiles] = useState<File[]>([]);
  const brdFileInputRef = useRef<HTMLInputElement>(null);
  // BRD flow choice: null = show create/update choice, 'create' = new BRD, 'update' = update existing BRD
  const [brdFlowChoice, setBrdFlowChoice] = useState<'create' | 'update' | null>(null);
  // BRD Update mode: null = show chat/upload choice, 'chat' = show text area, 'upload' = show file upload
  const [brdUpdateMode, setBrdUpdateMode] = useState<'chat' | 'upload' | null>(null);
  const [brdUpdateInstructions, setBrdUpdateInstructions] = useState('');

  // User Story flow choice: null = show create/update choice, 'create' = new stories, 'update' = update existing stories
  const [userStoryFlowChoice, setUserStoryFlowChoice] = useState<'create' | 'update' | null>(null);

  // Handle external prompt/nextagentflow selection
  useEffect(() => {
    if (selectedPromptText !== undefined && selectedPromptText !== '') {
      setQueryInputText(selectedPromptText);
    }
  }, [selectedPromptText]);

  useEffect(() => {
    if (selectedNextagentflow !== undefined && selectedNextagentflow !== '') {
      // Close droid terminal when leaving Code Assistant
      setDroidTerminalVisible(false);
      setDroidTerminalActive(false);
      setDroidTerminalEvents([]);

      // When BRD generator is selected, clear ALL state for a fresh start
      if (selectedNextagentflow === 'confirmedCreateBrd') {
        // Clear sessionStorage so previous BRD data doesn't carry over
        sessionStorage.removeItem('brdConfluenceLink');
        sessionStorage.removeItem('brdDocumentName');
        sessionStorage.removeItem('projectName');

        // Reset messages to welcome state
        messageIdCounter.current = 0;
        setMessages([
          {
            id: '1',
            type: 'bot',
            content: `\u{1F44B} Welcome! I can help you with BRD documents. Would you like to <strong>create a new BRD</strong> or <strong>update an existing one</strong>? Choose an option below:`,
          },
        ]);

        // Reset all input fields
        setQueryInputText('');
        setCreateUserStoryText('');
        setCreateUserStoryBrowse(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        setInputTestTextE2E('');
        setInstructionsE2E('');
        setUserStoryNameE2E('');

        // Reset scenario / test fields
        setScenarioTypes('');
        setScenarioTypesOptions([]);
        setSelectedScenarioTypes([]);
        setIsAllScenarioTypesSelected(false);
        setTestScenarios('');
        setTestCaseFormat('');
        setTestCases('');
        setFrameworkType('');
        setLanguage('');
        setScriptGenerationType('');
        setShowCombinationsPopup(false);
        setTestDataOutputFormat('json');

        // Reset agent flow state
        setChosenJiraStoryKey(null);
        setNextSuggestedAction('');
        setLastSuggestedActions([]);
        setUserStoryUri('');
        setBrdUri('');
        setFinalBrdConfluenceLink('');
        setShowUserStoryUri(false);
        setShowBrdUri(false);
        setIsOrchestratorActive(null);

        // Reset story edit modal state
        setStoryEditModalOpen(false);
        setEditingStoryKey(null);
        setEditingStoryText('');
        setEditedStoryDescriptions({});

        // Reset validated stories state
        setValidatedStories(null);
        setValidatedStoryEditModalOpen(false);
        setEditingValidatedKey(null);
        setEditingValidatedText('');
        setEditedValidatedDescriptions({});
        setEditedValidatedTitles({});
        setIsSavingValidatedStory(false);
        setLastValidationPayload(null);
        setJiraDictionary({});
        setNewJiraCreateList({});
        setSelectedNewJiraStories(new Set());
        setUserStoryTextLabel('User Story Text');

        // Reset comparison modal state
        setComparisonModalOpen(false);
        setComparisonStoryKey(null);
        setComparisonJiraTitle('');
        setComparisonJiraDescription('');
        setComparisonValidatedText('');
        setComparisonValidatedTitle('');

        // Reset BRD file uploads (preserve auth-backed project name)
        isProjectNameOverriddenRef.current = false;
        setIsEditingProjectName(false);
        setProjectName(externalProjectName || '');
        setActiveRoleDropdown(null);
        setBrdFiles([]);
        setBrdFlowChoice(null);
        setBrdUpdateMode(null);
        setBrdUpdateInstructions('');
        if (brdFileInputRef.current) brdFileInputRef.current.value = '';
        // Reset user story flow state
        setUserStoryFlowChoice(null);
      } else if (selectedNextagentflow === 'confirmedCreateUserStory') {
        // When User Story Creator is selected, show welcome with create/update choice
        messageIdCounter.current = 0;
        setMessages([
          {
            id: '1',
            type: 'bot',
            content: `\u{1F44B} Welcome! I can help you with User Stories. Would you like to <strong>create new user stories</strong> or <strong>update existing ones</strong>? Choose an option below:`,
          },
        ]);

        // Reset user story flow state
        setUserStoryFlowChoice(null);

        // Reset common fields
        setCreateUserStoryText('');
        setCreateUserStoryBrowse(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        setUserStoryUri('');
        setBrdUri('');
        const storedBrdLink = sessionStorage.getItem('brdConfluenceLink') || '';
        setFinalBrdConfluenceLink(storedBrdLink);
        setActiveRoleDropdown(null);
        setBrdFiles([]);
        setBrdFlowChoice(null);
        setBrdUpdateMode(null);
        setBrdUpdateInstructions('');
        if (brdFileInputRef.current) brdFileInputRef.current.value = '';
      } else {
        // For non-BRD agents, do a lighter reset
        setCreateUserStoryText('');
        setCreateUserStoryBrowse(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        setUserStoryUri('');
        setBrdUri('');
        // Restore BRD confluence link from sessionStorage so it's prepopulated across agents
        const storedBrdLink = sessionStorage.getItem('brdConfluenceLink') || '';
        setFinalBrdConfluenceLink(storedBrdLink);
        setActiveRoleDropdown(null);
        setBrdFiles([]);
        setBrdFlowChoice(null);
        setBrdUpdateMode(null);
        setBrdUpdateInstructions('');
        if (brdFileInputRef.current) brdFileInputRef.current.value = '';
        // Reset user story flow state
        setUserStoryFlowChoice(null);
      }

      // Clear stale intent and map to the newly selected agent's intent
      const nextagentflowToIntent: Record<string, string> = {
        confirmedCreateBrd: 'create_brd',
        confirmedCreateUserStory: 'create_user_story',
        confirmedValidateUserStory: 'validate_user_story',
        intentOfUpdateUserStory: 'save_validated_user_stories',
        confirmedUserStoryToTestScenario: 'generate_test_cases',
        confirmedTestCaseToTestScript: 'generate_test_script',
        confirmedTestDataGenerator: 'generate_test_data',
        confirmedBrdSummary: 'brd_summary',
        confirmedCreateUserManual: 'create_user_manual',
        confirmedCodeAssistant: 'code_assistant',
        // Quantnik Brain: explicit intent so the orchestrator skips the
        // "Is that correct? Yes/No" confirmation step.
        confirmedQueryKnowledgeBase: 'context_enrich_query',
      };
      setLastIntent(nextagentflowToIntent[selectedNextagentflow] || '');

      setNextagentflow(selectedNextagentflow);
    }
  }, [selectedNextagentflow]);

  // Auto-fill BRD confluence link when a confluence page is selected from the left sidebar;
  // fall back to stored BRD link when unselected
  useEffect(() => {
    const storedBrdLink = sessionStorage.getItem('brdConfluenceLink') || '';
    setFinalBrdConfluenceLink(selectedConfluencePageUrl || storedBrdLink);
  }, [selectedConfluencePageUrl]);

  // Sync external admin team data to internal BRD state
  useEffect(() => {
    if (externalProjectName !== undefined && !isProjectNameOverriddenRef.current) {
      setProjectName(externalProjectName);
      sessionStorage.setItem('projectName', externalProjectName);
    }
  }, [externalProjectName]);

  useEffect(() => {
    if (externalProductOwner) {
      setBrdStakeholders(prev => {
        const updated = [...prev];
        updated[0] = { ...updated[0], name: externalProductOwner.name, email: externalProductOwner.email };
        return updated;
      });
    }
  }, [externalProductOwner]);

  // Sync business stakeholders from parent (Team Modal save / sessionStorage restore).
  // Business stakeholders ≠ platform RBAC members — see QUANTNIK-2002.
  useEffect(() => {
    if (externalStakeholders && externalStakeholders.length > 0) {
      setBrdStakeholders(externalStakeholders);
    }
  }, [externalStakeholders]);


  
  // Available roles for dropdown
  const availableRoles = [
    'Product Owner',
    'Business Sponsor',
    'Business SME',
    'Process Analyst',
    'UX Researcher',
    'Solution Architect',
    'Compliance',
    'Information Security Officer'
  ];
  
  const chatMessagesRef = useRef<HTMLDivElement>(null);
  const executingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [isExecutingMode, setIsExecutingMode] = useState(false);

  // ---- Code Assistant (Droid) State ----
  const caConfigDefaults = (projectConfigSettings as any).codeAssistant;
  const [codeAssistantActive, setCodeAssistantActive] = useState(false);
  const [codeAssistantLocked, setCodeAssistantLocked] = useState(false);
  const [codeAssistantLockInfo, setCodeAssistantLockInfo] = useState<{
    localPath: string;
    branchName: string;
    folderName: string;
  } | null>(null);
  const [caFolderName, setCaFolderName] = useState(caConfigDefaults?.repoConfig?.fields?.folderName?.defaultValue || '');
  const [caFolderMode, setCaFolderMode] = useState<'new' | 'existing'>(caConfigDefaults?.repoConfig?.fields?.folderMode?.defaultValue || 'new');
  const [caLockMode, setCaLockMode] = useState<'new' | 'existing'>(caConfigDefaults?.repoConfig?.fields?.branchMode?.defaultValue || 'new');
  const [caBranchName, setCaBranchName] = useState(caConfigDefaults?.repoConfig?.fields?.branchName?.defaultValue || '');
  const [caModel, setCaModel] = useState(caConfigDefaults?.aiSettings?.fields?.model?.defaultValue || '');
  const [caAutonomy, setCaAutonomy] = useState<'high' | 'medium' | 'low'>(caConfigDefaults?.aiSettings?.fields?.autonomy?.defaultValue || 'high');
  const [caReasoning, setCaReasoning] = useState<'high' | 'medium' | 'low'>(caConfigDefaults?.aiSettings?.fields?.reasoning?.defaultValue || 'high');
  const [caModelOptions, setCaModelOptions] = useState<{ label: string; value: string }[]>(
    caConfigDefaults?.aiSettings?.fields?.model?.options || []
  );
  const [caLocking, setCaLocking] = useState(false);
  const [caOverwriteConfirm, setCaOverwriteConfirm] = useState(false);
  const [caSyncing, setCaSyncing] = useState<'pull' | 'push' | null>(null);

  // ---- Code Assistant: Git/Repo Configuration (from backend tool config) ----
  const [caRepoRemoteUrl, setCaRepoRemoteUrl] = useState('');
  const [caGitToken, setCaGitToken] = useState('');
  const [caGitUsername, setCaGitUsername] = useState(caConfigDefaults?.gitConnection?.fields?.gitUsername?.defaultValue || 'git');
  // Display-only flag: backend has a stored Harness PAT (never used as a runtime credential)
  const [hasBackendGitToken, setHasBackendGitToken] = useState(false);

  // Build Harness Git URL from config fields
  // Harness Git URL format: https://git.harness.io/{accountId}/{orgIdentifier}/{projectIdentifier}/{repoIdentifier}.git
  const buildHarnessRepoUrl = useCallback((cfg: Record<string, string | undefined>): string => {
    const url = (cfg.url || '').replace(/\/+$/, '');
    
    // If URL already ends with .git, it's a complete git URL - use it directly
    if (url.endsWith('.git')) {
      return url;
    }
    
    // If URL is already a git.harness.io URL with path segments, add .git suffix
    if (url.includes('git.harness.io') && (url.match(/\//g) || []).length > 3) {
      return `${url}.git`;
    }
    
    // Build Harness Git URL from separate fields
    const accountId = cfg.accountId;
    const orgIdentifier = cfg.orgIdentifier;
    const projectIdentifier = cfg.projectIdentifier;
    let repoIdentifier = cfg.repoIdentifier || '';
    
    // Remove .git suffix if user accidentally added it (we'll add it at the end)
    repoIdentifier = repoIdentifier.replace(/\.git$/, '');
    
    if (accountId && orgIdentifier && repoIdentifier) {
      // Harness Git uses git.harness.io subdomain, not app.harness.io
      // Format: https://git.harness.io/{accountId}/{orgIdentifier}/{projectIdentifier}/{repoIdentifier}.git
      // Note: repoIdentifier might already include projectIdentifier as "project/repo" format
      
      // Check if repoIdentifier already contains a slash (includes project path)
      if (repoIdentifier.includes('/')) {
        // repoIdentifier is already in "projectIdentifier/repoName" format
        return `https://git.harness.io/${accountId}/${orgIdentifier}/${repoIdentifier}.git`;
      }
      
      // If projectIdentifier is provided separately, include it
      if (projectIdentifier) {
        return `https://git.harness.io/${accountId}/${orgIdentifier}/${projectIdentifier}/${repoIdentifier}.git`;
      }
      
      // No projectIdentifier - just use accountId/orgIdentifier/repoIdentifier
      return `https://git.harness.io/${accountId}/${orgIdentifier}/${repoIdentifier}.git`;
    }
    
    // Fallback: if URL looks like a git URL (has harness domain), ensure .git suffix
    if (url && (url.includes('harness.io') || url.includes('github.com') || url.includes('gitlab.com'))) {
      return `${url}.git`;
    }
    
    // Return as-is for non-git URLs or empty strings
    return url;
  }, []);

  // Stable key for harnessToolConfig to prevent infinite re-renders
  const harnessConfigKey = useMemo(() => {
    if (!harnessToolConfig?.config) return '';
    return JSON.stringify(harnessToolConfig.config);
  }, [harnessToolConfig?.config]);

  const harnessSecretKeysKey = useMemo(() => {
    return JSON.stringify(harnessToolConfig?.secretKeys ?? []);
  }, [harnessToolConfig?.secretKeys]);

  // Sync Code Assistant git fields when backend harness-repo config is available
  useEffect(() => {
    // Check if harness config has any URL configured (ready or not)
    const cfg = harnessToolConfig?.config;
    if (cfg?.url && !caRepoRemoteUrl) {
      setCaRepoRemoteUrl(buildHarnessRepoUrl(cfg));
    }
    // Check if patToken secret is stored using secretKeys from backend
    const hasStoredToken = harnessToolConfig?.secretKeys?.includes('patToken') ?? false;
    setHasBackendGitToken(hasStoredToken);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- use stable keys instead of object references
  }, [harnessConfigKey, harnessSecretKeysKey]);

  // ---- Droid Terminal State ----
  const [droidTerminalEvents, setDroidTerminalEvents] = useState<DroidTerminalEvent[]>([]);
  const [droidTerminalVisible, setDroidTerminalVisible] = useState(false);
  const [droidTerminalActive, setDroidTerminalActive] = useState(false);
  const [exitConfirmOpen, setExitConfirmOpen] = useState(false);
  const droidSessionClosedRef = useRef(false);

/*
  // Check orchestrator health status
  useEffect(() => {
    const checkOrchestratorHealth = async () => {
      try {
        const response = await fetch(HEALTH_ENDPOINT, {
          method: 'GET',
          signal: AbortSignal.timeout(5000),
        });
        setIsOrchestratorActive(response.ok);
      } catch {
        setIsOrchestratorActive(false);
      }
    };
    checkOrchestratorHealth();
    const interval = setInterval(checkOrchestratorHealth, 30000);
    return () => clearInterval(interval);
  }, []);
*/
  // ---- Code Assistant Helpers ----
  // Fetch available models from QUANTNIK Code Assistant
  const fetchCodeAssistantModels = useCallback(async () => {
    try {
      const res = await apiFetch(QUANTNIK_MODELS_ENDPOINT, { method: 'GET', signal: AbortSignal.timeout(5000) });
      if (res.ok) {
        const contentType = res.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
          const data = await res.json();
          if (data.models && Array.isArray(data.models)) {
            setCaModelOptions(data.models);
            if (!caModel && data.models.length > 0) {
              setCaModel(data.models[0].value);
            }
            return;
          }
        }
      }
    } catch {
      // Fallback models if QUANTNIK server unreachable
      setCaModelOptions([
        { label: 'GPT-5.2 Codex', value: 'gpt-5.2-codex' },
        { label: 'Sonnet 4.5', value: 'claude-sonnet-4-5-20250929' },
        { label: 'Opus 4.6', value: 'claude-opus-4-6' },
        { label: 'GLM-5', value: 'glm-5' },
      ]);
      if (!caModel) setCaModel('gpt-5.2-codex');
    }
  }, [caModel]);

  // Check if user message is a code assistant trigger
  const isCodeAssistantTrigger = (message: string): boolean => {
    const lower = message.toLowerCase().trim();
    const triggers = [
      'code assistant', 'code generation', 'generate code', 'write code',
      'code help', 'coding assistant', 'code agent', 'droid', 'factory droid',
      'start coding', 'code review', 'refactor code', 'debug code',
      'implement code', 'programming help', 'code droid',
    ];
    return triggers.some(t => lower.includes(t));
  };

  // Handle repo lock for code assistant
  const handleCodeAssistantLock = async () => {
    if (!caFolderName.trim() || !caBranchName.trim()) {
      addMessage('Please provide both a folder name and branch name.', 'error');
      return;
    }
    // Validate folder name (alphanumeric, dots, underscores, hyphens)
    if (!/^[a-zA-Z0-9._-]+$/.test(caFolderName.trim())) {
      addMessage('Folder name must contain only alphanumeric characters, dots, underscores, or hyphens.', 'error');
      return;
    }
    setCaLocking(true);
    try {
      // Step 1: Send session config via SDLC Orchestrator
      // Use project_id for secure credential lookup from auth-service (preferred)
      // Falls back to direct git_token if user entered one manually
      const hasManualCredentials = caGitToken.trim();
      
      // Always send config if we have repo URL, project_id, or manual credentials
      // The orchestrator will fetch PAT from auth-service if project_id is provided
      if (caRepoRemoteUrl.trim() || projectId || hasManualCredentials) {
        try {
          console.log('[Code Assistant] Sending config with project_id:', projectId, 'hasBackendGitToken:', hasBackendGitToken);
          await apiFetch(QUANTNIK_CODE_ASSISTANT_CONFIG_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              session_id: sessionId,
              // Always pass project_id if available - orchestrator will fetch PAT from auth-service
              project_id: projectId || undefined,
              repo_remote_url: caRepoRemoteUrl.trim() || undefined,
              // Only pass git_token if manually entered (as fallback if auth-service lookup fails)
              git_token: hasManualCredentials ? caGitToken.trim() : undefined,
              git_username: caGitUsername.trim() || undefined,
            }),
          });
        } catch (err) {
          // Non-critical: config may already be set via env, continue with lock
          console.warn('Failed to send session config via orchestrator (non-critical):', err);
        }
      }

      // Step 2: Lock the repository workspace via SDLC Orchestrator
      const res = await apiFetch(QUANTNIK_REPO_LOCK_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          mode: caLockMode,
          folder_mode: caFolderMode,
          folder_name: caFolderName.trim(),
          branch_name: caBranchName.trim(),
          overwrite_existing: caOverwriteConfirm,
        }),
      });
      
      // Handle non-JSON error responses
      const contentType = res.headers.get('content-type') || '';
      let data: any;
      if (contentType.includes('application/json')) {
        data = await res.json();
      } else {
        const textBody = await res.text();
        if (!res.ok) {
          addMessage(`<strong>Repo Lock Error:</strong> ${escapeHtml(textBody || `HTTP ${res.status}`)}`, 'error');
          return;
        }
        data = { message: textBody };
      }
      
      if (!res.ok) {
        // Extract error message - prioritize 'message' field, avoid object fields like 'details'
        const errMsg = data.message || data.detail || data.error || 
          (typeof data.details === 'string' ? data.details : null) || 
          'Failed to lock repository';
        addMessage(`<strong>Repo Lock Error:</strong> ${escapeHtml(errMsg)}`, 'error');
        return;
      }
      // Check if requires overwrite confirmation
      if (data.requiresConfirmation) {
        addMessage(`<strong>Warning:</strong> ${escapeHtml(data.warning || 'Local folder is out of sync with remote.')} Please confirm overwrite.`, 'error');
        setCaOverwriteConfirm(true);
        return;
      }
      setCodeAssistantLocked(true);
      setCodeAssistantLockInfo({
        localPath: data.localPath,
        branchName: data.branchName || caBranchName.trim(),
        folderName: caFolderName.trim(),
      });
      setCaOverwriteConfirm(false);
      addMessage(
        `<div><strong>Repository locked for session</strong></div>` +
        `<div style="font-size:0.8rem;margin-top:4px;opacity:0.85;">` +
        `<div><strong>Branch:</strong> ${escapeHtml(data.branchName || caBranchName.trim())}</div>` +
        `<div><strong>Folder:</strong> ${escapeHtml(caFolderName.trim())}</div>` +
        `<div><strong>Path:</strong> ${escapeHtml(data.localPath || '')}</div>` +
        `</div><div style="font-size:0.75rem;margin-top:6px;color:#3498B3;">You can now send code generation prompts. Type your request below.</div>`,
        'bot'
      );
    } catch (error: any) {
      const msg = error instanceof Error ? error.message : 'Network error connecting to QUANTNIK Code Assistant';
      addMessage(`<strong>Connection Error:</strong> ${escapeHtml(msg)}. Make sure the SDLC Orchestrator is running.`, 'error');
    } finally {
      setCaLocking(false);
    }
  };

  // Handle repo sync (pull/push) via SDLC Orchestrator
  const handleCodeAssistantSync = async (direction: 'pull' | 'push') => {
    if (!codeAssistantLockInfo) return;
    setCaSyncing(direction);
    try {
      const res = await apiFetch(QUANTNIK_REPO_SYNC_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          direction,
          local_path: codeAssistantLockInfo.localPath,
          branch_name: codeAssistantLockInfo.branchName,
        }),
      });
      
      // Handle non-JSON error responses
      const contentType = res.headers.get('content-type') || '';
      let data: any;
      if (contentType.includes('application/json')) {
        data = await res.json();
      } else {
        const textBody = await res.text();
        if (!res.ok) {
          addMessage(`<strong>Sync Error:</strong> ${escapeHtml(textBody || `HTTP ${res.status}`)}`, 'error');
          return;
        }
        data = { message: textBody };
      }
      
      if (!res.ok) {
        addMessage(`<strong>Sync Error:</strong> ${escapeHtml(data.detail || data.details || data.error || 'Sync failed')}`, 'error');
        return;
      }
      addMessage(
        `<strong>${direction === 'pull' ? 'Pulled from' : 'Pushed to'}</strong> origin/${escapeHtml(codeAssistantLockInfo.branchName)}`,
        'bot'
      );
    } catch (error: any) {
      addMessage(`<strong>Sync Error:</strong> ${escapeHtml(error instanceof Error ? error.message : 'Unknown error')}`, 'error');
    } finally {
      setCaSyncing(null);
    }
  };

  // Exit code assistant session — show confirm modal
  const handleExitCodeAssistant = () => {
    setExitConfirmOpen(true);
  };

  // Actually close the session after user confirms
  const confirmExitCodeAssistant = () => {
    setExitConfirmOpen(false);
    droidSessionClosedRef.current = true;

    // Kill the droid process via SDLC Orchestrator + clean up session (fire-and-forget)
    if (sessionId) {
      apiFetch(`${QUANTNIK_CODE_ASSISTANT_SESSION_ENDPOINT}/${encodeURIComponent(sessionId)}`, { method: 'DELETE' }).catch(() => {});
    }
    setCodeAssistantActive(false);
    setCodeAssistantLocked(false);
    setCodeAssistantLockInfo(null);
    setCaFolderName('');
    setCaFolderMode('new');
    setCaLockMode('new');
    setCaBranchName('');
    setCaOverwriteConfirm(false);
    setNextagentflow('');
    // Stop loading and remove any in-flight progress / executing messages
    setIsLoading(false);
    removeAnalyzingMessage();
    setMessages(prev => prev.filter(msg => !msg.id.includes('-progress-')));
    // Close droid terminal window
    setDroidTerminalVisible(false);
    setDroidTerminalActive(false);
    setDroidTerminalEvents([]);
    // Reset repo config — re-apply backend defaults if available
    setCaGitToken('');
    setCaGitUsername('git');
    setCaRepoRemoteUrl(harnessToolConfig?.config?.url ? buildHarnessRepoUrl(harnessToolConfig.config) : '');
    addMessage(
      '<div><strong>Code Assistant session closed</strong></div>' +
      '<div style="font-size:0.75rem;margin-top:4px;opacity:0.7;">The droid process has been terminated. You can start a new session anytime.</div>',
      'bot'
    );
  };

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatMessagesRef.current) {
      chatMessagesRef.current.scrollTop = chatMessagesRef.current.scrollHeight;
    }
  }, [messages]);

  // Notify parent component when nextagentflow changes
  useEffect(() => {
    if (nextagentflow && onAgentChange) {
      onAgentChange(nextagentflow);
    }
  }, [nextagentflow, onAgentChange]);

  // Notify parent component when processing state changes
  useEffect(() => {
    if (onProcessingChange) {
      onProcessingChange(isLoading);
    }
  }, [isLoading, onProcessingChange]);

  // Sync edited descriptions when Jira stories change from left sidebar
  useEffect(() => {
    const agentsUsingUserStoryText = [
      'confirmedUserStoryToTestScenario',
      'confirmedValidateUserStory',
      'confirmedCreateUserManual',
      'intentOfUpdateUserStory',
      'confirmedCreateUserStory',
    ];
    if (!nextagentflow || agentsUsingUserStoryText.includes(nextagentflow)) {
      if (selectedJiraStories.length === 0) {
        setChosenJiraStoryKey(null);
        setCreateUserStoryText('');
        setEditedStoryDescriptions({});
      } else {
        // Initialize edited descriptions for new stories, keep existing edits
        setEditedStoryDescriptions(prev => {
          const next: Record<string, string> = {};
          for (const story of selectedJiraStories) {
            next[story.key] = prev[story.key] ?? story.description;
          }
          return next;
        });
        // Build combined text from (edited) descriptions
        setCreateUserStoryText(
          selectedJiraStories.map(s => `[${s.key}] ${editedStoryDescriptions[s.key] ?? s.description}`).join('\n\n')
        );
      }
    }
  }, [selectedJiraStories, nextagentflow]);

  // Keep createUserStoryText in sync when user edits individual story descriptions
  useEffect(() => {
    if (selectedJiraStories.length > 0 && Object.keys(editedStoryDescriptions).length > 0) {
      setCreateUserStoryText(
        selectedJiraStories.map(s => `[${s.key}] ${editedStoryDescriptions[s.key] ?? s.description}`).join('\n\n')
      );
    }
  }, [editedStoryDescriptions]);

  // Auto-populate testCases textarea when test cases are selected from left panel
  // For confirmedTestCaseToTestScript and confirmedTestDataGenerator: display ALL test cases from selected epics' user stories
  useEffect(() => {
    if (nextagentflow === 'confirmedTestCaseToTestScript' || nextagentflow === 'confirmedTestDataGenerator') {
      if (selectedTestCasesFromJira.length > 0) {
        // Combine all selected test cases into the textarea
        const formattedTestCases = selectedTestCasesFromJira
          .map(tc => `[${tc.key}] ${tc.summary}\n${tc.description}`)
          .join('\n\n');
        setTestCases(formattedTestCases);
        // Use the first test case for the primary selection fields (backward compat)
        const firstTc = selectedTestCasesFromJira[0];
        setSelectedTcKey(firstTc.key);
        setSelectedTcSummary(firstTc.summary);
        setSelectedTcDescription(firstTc.description);
        setTestCaseValidationError('');
      } else {
        setTestCases('');
        setSelectedTcKey('');
        setSelectedTcSummary('');
        setSelectedTcDescription('');
      }
    }
  }, [selectedTestCasesFromJira, nextagentflow]);

  // Helper to open modal for a specific story
  const openStoryEditModal = (storyKey: string) => {
    const story = selectedJiraStories.find(s => s.key === storyKey);
    if (!story) return;
    setEditingStoryKey(storyKey);
    setEditingStoryText(editedStoryDescriptions[storyKey] ?? story.description);
    setStoryEditModalOpen(true);
  };

  // Save modal edits
  const saveStoryEdit = () => {
    if (editingStoryKey) {
      setEditedStoryDescriptions(prev => ({ ...prev, [editingStoryKey]: editingStoryText }));
    }
    setStoryEditModalOpen(false);
    setEditingStoryKey(null);
  };

  // Build epicâ†’stories JSON for payload
  const buildEpicStoriesPayload = () => {
    const epicMap = new Map<string, { epic_key: string; epic_summary: string; user_stories: { id: string; key: string; summary: string; description: string }[] }>();
    for (const story of selectedJiraStories) {
      const eKey = story.epicKey || 'ungrouped';
      if (!epicMap.has(eKey)) {
        epicMap.set(eKey, {
          epic_key: eKey,
          epic_summary: story.epicSummary || '',
          user_stories: [],
        });
      }
      epicMap.get(eKey)!.user_stories.push({
        id: story.id,
        key: story.key,
        summary: story.summary,
        description: editedStoryDescriptions[story.key] ?? story.description,
      });
    }
    return Array.from(epicMap.values());
  };

  const buildSelectedEpicKeys = () => {
    return Array.from(
      new Set(
        selectedJiraStories
          .map(story => story.epicKey?.trim())
          .filter((epicKey): epicKey is string => Boolean(epicKey && epicKey !== 'ungrouped'))
      )
    );
  };

  const findSuccessfulActionResult = (actionResults: any, actionName: string) => {
    if (!Array.isArray(actionResults)) return null;
    return actionResults.find((result: any) => result?.action === actionName && result?.success);
  };

  const refreshJiraAfterStoryUpdate = (epicKeys: string[]) => {
    if (epicKeys.length === 0) return;

    setIsRefreshingJiraEpics(true);
    const refreshPromise = onValidatedUserStorySaved?.(epicKeys) ?? onUserStoryGenerated?.(epicKeys);
    if (refreshPromise instanceof Promise) {
      refreshPromise.finally(() => setIsRefreshingJiraEpics(false));
    } else {
      setIsRefreshingJiraEpics(false);
    }
  };

  // Build context object from current UI state for /v1/chat
  // Only includes agent-specific fields when an agent flow is active (nextagentflow is set).
  // Free-form chat messages send an empty context so the orchestrator classifies intent first.
  const buildChatContext = useCallback((): Record<string, any> => {
    const ctx: Record<string, any> = {};

    // Use nextagentflow if set; fall back to parent-selected flow for follow-up messages
    const effectiveFlow = nextagentflow || selectedNextagentflow || '';

    // No agent flow active — return empty context for intent classification.
    // Sending project_name during classification causes the orchestrator to
    // skip its "collect details" step and attempt direct execution, which
    // fails for agents that require a multi-step form flow (BRD, User Story).
    if (!effectiveFlow) return ctx;

    // Include project_name when an agent flow is active so the orchestrator
    // doesn't ask "which project?" and can route directly.
    if (projectName.trim()) {
      ctx.project_name = projectName.trim();
    }

    // Quantnik Brain: forward the Critical / Non-Critical toggle so the RAG
    // service knows whether to also search the non-critical KB.
    if (effectiveFlow === 'confirmedQueryKnowledgeBase') {
      ctx.include_non_critical = !!quantnikBrainIncludeNonCritical;
    }

    if (finalBrdConfluenceLink.trim()) {
      ctx.brd_link = finalBrdConfluenceLink.trim();
    }

    // User Manual: forward the source URL (SharePoint folder or Confluence page)
    // through the chat/intent pipeline so the orchestrator's _validate_generic_inputs
    // for CREATE_USER_MANUAL passes and call_user_manual_agent receives it.
    if (nextagentflow === 'confirmedCreateUserManual' && sharepointUrl.trim()) {
      ctx.user_manual_source_url = sharepointUrl.trim();
    }

    if (selectedTestCasesFromJira.length > 0) {
      if (nextagentflow === 'confirmedTestCaseToTestScript') {
        // Format test_cases with Test Case ID, Test Case Name, and Steps for test script generation
        ctx.test_cases = JSON.stringify(selectedTestCasesFromJira.map(tc => ({
          'Test Case ID': tc.key,
          'Test Case Name': tc.summary,
          'Steps': (tc.steps && tc.steps.length > 0)
            ? tc.steps
            : [{ Step: tc.description || tc.summary, Expected: '' }],
        })));
      } else {
        ctx.test_cases = selectedTestCasesFromJira.map(tc => ({
          key: tc.key,
          summary: tc.summary,
          description: tc.description,
        }));
      }
    }

    if (selectedScenarioTypes.length > 0) ctx.scenario_types = selectedScenarioTypes;
    if (frameworkType.trim()) ctx.framework_type = frameworkType.trim();
    if (language.trim()) ctx.language = language.trim();
    if (scriptGenerationType.trim()) ctx.script_generation_type = scriptGenerationType.trim();
    if (nextagentflow === 'confirmedTestDataGenerator') {
      ctx.output_format = testDataOutputFormat;
      if (selectedTestCasesFromJira.length > 0) {
        ctx.test_cases = selectedTestCasesFromJira.map(tc => ({
          key: tc.key,
          summary: tc.summary,
          description: tc.description,
        }));
      }
    }
    if (nextagentflow === 'confirmedValidateUserStory' && selectedJiraStories.length > 0) {
      ctx.create_user_story_text = buildEpicStoriesPayload();
    } else if (nextagentflow === 'confirmedUserStoryToTestScenario' && selectedJiraStories.length > 0) {
      ctx.create_user_story_text = buildEpicStoriesPayload();
    } else if (nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'update') {
      const selectedEpicKeys = buildSelectedEpicKeys();
      if (finalBrdConfluenceLink.trim()) {
        ctx.brd_confluence_link = finalBrdConfluenceLink.trim();
      }
      if (selectedEpicKeys.length > 0) {
        ctx.jira_epic_keys = selectedEpicKeys;
      }
    } else if (createUserStoryText.trim()) {
      ctx.create_user_story_text = createUserStoryText.trim();
    }
    if (userStoryUri.trim()) ctx.usg_document_uri = userStoryUri.trim();

    // Code assistant context
    if (nextagentflow === 'confirmedCodeAssistant' && codeAssistantLocked && codeAssistantLockInfo) {
      ctx.code_assistant = {
        repo_path: codeAssistantLockInfo.localPath,
        branch_name: codeAssistantLockInfo.branchName,
        folder_name: codeAssistantLockInfo.folderName,
        model: caModel,
        autonomy: caAutonomy,
        reasoning: caReasoning,
      };
      // Include repo config so orchestrator can forward to QUANTNIK for session config
      ctx.repo_config = {
        repoRemoteUrl: caRepoRemoteUrl.trim() || undefined,
        gitToken: caGitToken.trim() || undefined,
        gitUsername: caGitUsername.trim() || undefined,
      };
    }

    return ctx;
  }, [
    finalBrdConfluenceLink, projectName, selectedJiraStories, selectedTestCasesFromJira,
    brdStakeholders, selectedScenarioTypes, frameworkType, language, scriptGenerationType,
    createUserStoryText, userStoryUri, buildEpicStoriesPayload, nextagentflow, testDataOutputFormat,
    codeAssistantLocked, codeAssistantLockInfo, caModel, caAutonomy, caReasoning,
    caRepoRemoteUrl, caGitToken, caGitUsername,
    quantnikBrainIncludeNonCritical, selectedNextagentflow,
  ]);

  // Unified chat API call â€” single endpoint for all interactions
  const callChatApi = async (
    message: string,
    extraContext?: Record<string, any>,
    files?: File[],
  ): Promise<ChatResponsePayload> => {
    const context = { ...buildChatContext(), ...extraContext };
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);

    try {
      let response: Response;

      if (files && files.length > 0) {
        // Multipart request for file uploads (e.g. BRD creation)
        const formData = new FormData();
        formData.append('session_id', sessionId!);
        formData.append('message', message);
        formData.append('context', JSON.stringify(context));
        files.forEach(file => formData.append('file', file, sanitizeFilename(file.name)));

        response = await apiFetch(CHAT_ENDPOINT, {
          method: 'POST',
          body: formData,
          signal: controller.signal,
        });
      } else {
        // JSON request
        const payload: ChatRequestPayload = {
          session_id: sessionId!,
          message,
          context,
        };

        response = await apiFetch(CHAT_ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          signal: controller.signal,
        });
      }

      clearTimeout(timeoutId);
      const data: ChatResponsePayload = await response.json();

      if (!response.ok && data.status !== 'success') {
        throw new Error(data.message || `Server error: ${response.status}`);
      }

      return data;
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  };

  // Build milestone progress HTML for a streaming progress message
  const buildMilestoneHtml = (milestone: MilestoneEvent): string => {
    const pct = Math.round(milestone.progress * 100);
    const barColor = milestone.stage === 'error' ? '#EF4444' : milestone.stage === 'complete' ? '#22C55E' : '#3498B3';
    const animStyle = milestone.stage === 'complete' || milestone.stage === 'error' ? '' : 'animation: milestoneShimmer 1.5s ease-in-out infinite;';
    const isActive = milestone.stage !== 'complete' && milestone.stage !== 'error';
    const dotColor = milestone.stage === 'error' ? '#EF4444' : '#22C55E';
    const dotsHtml = `<span class="milestone-dots${isActive ? ' milestone-dots--active' : ''}">
      <span class="milestone-dot" style="background:${dotColor};"></span>
      <span class="milestone-dot" style="background:${dotColor};"></span>
      <span class="milestone-dot" style="background:${dotColor};"></span>
    </span>`;
    return `<div style="display: flex; flex-direction: column; gap: 6px; min-width: 220px;">
      <div style="display: flex; align-items: center; gap: 8px;">
        ${dotsHtml}
        <span style="font-weight: 600; font-size: 0.85rem; color: inherit;">${milestone.title}</span>
      </div>
      <div style="font-size: 0.75rem; opacity: 0.8;">${milestone.description}</div>
      <div style="position: relative; height: 6px; background: rgba(128,128,128,0.2); border-radius: 3px; overflow: hidden;">
        <div style="position: absolute; top: 0; left: 0; height: 100%; width: ${pct}%; background: ${barColor}; border-radius: 3px; transition: width 0.4s ease; ${animStyle}"></div>
      </div>
      <div style="font-size: 0.7rem; opacity: 0.6; text-align: right;">${pct}%</div>
    </div>`;
  };

  // Build streaming HTML for real-time code assistant output
  const buildCodeAssistantStreamingHtml = (text: string): string => {
    // Escape HTML entities for safe rendering
    const escaped = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    // Convert markdown-style code blocks to <pre><code> 
    let formatted = escaped;
    // Handle fenced code blocks: ```lang\n...\n```
    formatted = formatted.replace(
      /```(\w*)\n([\s\S]*?)```/g,
      (_match, lang, code) =>
        `<pre style="background: rgba(0,0,0,0.3); border-radius: 6px; padding: 12px; overflow-x: auto; margin: 8px 0; font-size: 0.82rem;"><code class="language-${lang}">${code}</code></pre>`
    );
    // Handle inline code: `code`
    formatted = formatted.replace(
      /`([^`]+)`/g,
      '<code style="background: rgba(0,0,0,0.2); padding: 2px 5px; border-radius: 3px; font-size: 0.85rem;">$1</code>'
    );
    // Convert **bold**
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Convert newlines
    formatted = formatted.replace(/\n/g, '<br>');
    // Blinking cursor removed — streaming text itself is visible feedback
    return `<div class="code-assistant-stream" style="font-family:'Fira Code','Consolas',monospace;white-space:pre-wrap;word-break:break-word;line-height:1.5;font-size:0.82rem;margin:0;padding:0;">${formatted}</div>`;
  };

  // SSE streaming chat call - uses /v1/chat/stream, shows real-time milestones
  const callChatStreamApi = async (
    message: string,
    progressMessageId: string,
    extraContext?: Record<string, any>,
    files?: File[],
    explicitIntent?: string,
  ): Promise<ChatResponsePayload> => {
    const context = { ...buildChatContext(), ...extraContext };
    const controller = new AbortController();
    let timeoutId = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);
    const resetTimeout = () => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);
    };

    try {
      let response: Response;

      if (files && files.length > 0) {
        // File uploads fall back to non-streaming endpoint
        const formData = new FormData();
        formData.append('session_id', sessionId!);
        formData.append('message', message);
        formData.append('context', JSON.stringify(context));
        if (explicitIntent) formData.append('explicit_intent', explicitIntent);
        files.forEach(file => formData.append('file', file, sanitizeFilename(file.name)));

        response = await apiFetch(CHAT_ENDPOINT, {
          method: 'POST',
          body: formData,
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        const data: ChatResponsePayload = await response.json();
        if (!response.ok && data.status !== 'success') {
          throw new Error(data.message || `Server error: ${response.status}`);
        }
        return data;
      }

      // JSON request to streaming endpoint
      const payload: ChatRequestPayload = {
        session_id: sessionId!,
        message,
        context,
        ...(explicitIntent ? { explicit_intent: explicitIntent } : {}),
      };

      response = await apiFetch(CHAT_STREAM_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!response.ok) {
        clearTimeout(timeoutId);
        const errBody = await response.text();
        const mapped = parseGatewayError(errBody, response.status);
        if (mapped.shouldRedirect) {
          clearTokens();
          setTimeout(() => window.location.assign('/login'), 0);
        }
        let errMsg = mapped.message;
        if (response.status >= 500) {
          errMsg = `Reconnecting… gateway returned ${response.status}. Retry request.`;
        }
        throw new Error(errMsg);
      }

      if (!response.body) {
        clearTimeout(timeoutId);
        throw new Error('No response body for streaming');
      }

      // Read the SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let finalResponse: ChatResponsePayload | null = null;
      let codeAssistantText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        resetTimeout();

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data:')) continue;

          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr || jsonStr === '[DONE]') continue;

          let event: SSEEvent;
          try {
            event = JSON.parse(jsonStr);
          } catch {
            continue;
          }

          switch (event.type) {
            case 'milestone': {
              // Update the progress message in-place
              const html = buildMilestoneHtml(event);
              setMessages(prev => prev.map(msg =>
                msg.id === progressMessageId ? { ...msg, content: html } : msg
              ));
              break;
            }

            case 'child_agent_event': {
              // Forward child agent milestone if it has progress info
              const orig = event.original_event;
              if (orig && orig.type === 'milestone') {
                const childMilestone: MilestoneEvent = {
                  ...orig,
                  title: `[${event.source_agent}] ${orig.title || ''}`,
                };
                const html = buildMilestoneHtml(childMilestone);
                setMessages(prev => prev.map(msg =>
                  msg.id === progressMessageId ? { ...msg, content: html } : msg
                ));
              }
              break;
            }

            case 'code_assistant_chunk': {
              // Real-time streaming text from code assistant
              const chunkText = event.text || '';
              const role = event.role || 'assistant';
              if (chunkText && role !== 'user') {
                codeAssistantText += chunkText;
                const streamingHtml = buildCodeAssistantStreamingHtml(codeAssistantText);
                setMessages(prev => prev.map(msg =>
                  msg.id === progressMessageId ? { ...msg, content: streamingHtml } : msg
                ));
                // Stop loading indicator — the user can already see the response text
                setIsLoading(false);
              }
              break;
            }

            case 'droid_terminal': {
              // Ignore terminal events after session was closed by user
              if (droidSessionClosedRef.current) break;
              // Droid terminal events — show in the terminal panel
              const termEvent: DroidTerminalEvent = {
                ...event as DroidTerminalEvent,
                timestamp: Date.now(),
              };
              setDroidTerminalEvents(prev => [...prev, termEvent]);
              setDroidTerminalVisible(true);
              setDroidTerminalActive(true);
              // Mark terminal as idle when turn completes (session stays alive for follow-ups)
              if (termEvent.event === 'turn_complete') {
                setDroidTerminalActive(false);
              }
              // Mark terminal as finished when exit event arrives (session ended)
              if (termEvent.event === 'exit') {
                setDroidTerminalActive(false);
              }
              break;
            }

            case 'response': {
              // Final response - convert to ChatResponsePayload
              finalResponse = {
                session_id: event.session_id,
                message: event.message,
                status: event.status,
                data: event.data,
                nextagentflow: event.nextagentflow ?? '',
                suggested_actions: event.suggested_actions || [],
                metadata: event.total_duration_ms != null ? { total_duration_ms: event.total_duration_ms } : undefined,
              };
              // Set nextagentflow from streaming response to update UI
              if (event.nextagentflow) {
                setNextagentflow(event.nextagentflow);
              }
              // Capture intent from streaming response for next request's explicit_intent
              if (event.data?.intent) {
                setLastIntent(event.data.intent);
              }
              break;
            }

            case 'error': {
              // Stream error event
              const errHtml = buildMilestoneHtml({
                type: 'milestone',
                stage: 'error',
                title: event.title || 'Error',
                description: event.message,
                progress: 0,
                icon: event.icon || '\u274C',
                timestamp: event.timestamp,
              });
              setMessages(prev => prev.map(msg =>
                msg.id === progressMessageId ? { ...msg, content: errHtml } : msg
              ));
              throw new Error(event.message || 'Streaming error');
            }
          }
        }
      }

      clearTimeout(timeoutId);

      if (!finalResponse) {
        if (codeAssistantText) {
          // Code assistant streamed text via chunks but no final response event arrived.
          // Construct a synthetic response so the caller can proceed normally.
          finalResponse = {
            session_id: '',
            message: codeAssistantText,
            status: 'success',
            data: { intent: 'code_assistant' },
            nextagentflow: '',
            suggested_actions: [],
          };
        } else {
          throw new Error('Stream ended without a final response');
        }
      }

      return finalResponse;
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  };

  /**
   * Direct Brain query — bypasses SDLC Orchestrator and calls RAG service directly
   * via the gateway's /api/brain/v1/query route. Eliminates 2 unnecessary hops
   * (Orchestrator + Integration Service) for dedicated Brain panel queries.
   */
  const callBrainQueryDirect = async (
    message: string,
    progressMessageId: string,
  ): Promise<ChatResponsePayload> => {
    const context = buildChatContext();
    const ragPayload = {
      query: message,
      project_name: context.project_name || null,
      include_non_critical: !!context.include_non_critical,
      conversation_id: brainConversationId || null,
      conversation_history: [],
      top_k: 5,
      include_sources: true,
    };

    const response = await apiFetch(BRAIN_QUERY_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ragPayload),
    });

    if (!response.ok) {
      const errBody = await response.text();
      const mapped = parseGatewayError(errBody, response.status);
      if (mapped.shouldRedirect) {
        clearTokens();
        setTimeout(() => window.location.assign('/login'), 0);
      }
      throw new Error(mapped.message);
    }

    const ragResponse = await response.json();

    // Persist conversation_id for multi-turn Brain conversations
    if (ragResponse.conversation_id) {
      setBrainConversationId(ragResponse.conversation_id);
    }

    // Map RAG QueryResponse → ChatResponsePayload for unified rendering
    return {
      session_id: sessionId || '',
      message: ragResponse.answer || 'No response received.',
      status: 'success',
      nextagentflow: 'confirmedQueryKnowledgeBase',
      suggested_actions: [],
      data: {
        intent: 'context_enrich_query',
        sources: ragResponse.sources,
      },
    };
  };

  // Handle successful /v1/chat response - process all data from orchestrator
  const handleChatSuccess = (data: ChatResponsePayload) => {
    const childResponse = data.data?.child_response;
    const intent = data.data?.intent;
    const parts: string[] = [];

    // 1. Main bot message
    if (data.message) {
      const cleaned = cleanBotResponseText(data.message);
      if (cleaned) parts.push(formatTextResponse(cleaned));
    }

    //set nextagentflow variable here — clear input fields when flow is complete
    if (data.nextagentflow) {
      setNextagentflow(data.nextagentflow);
    } else {
      // Response indicates flow is complete (nextagentflow is null/empty) — remove input fields
      setNextagentflow('');
    }
    // 2. Process child orchestrator response data
    if (childResponse) {
      const result = childResponse.data?.result ?? childResponse.result;

      // Display result content
      if (result) {
        // Clean meta fields
        const displayResult = typeof result === 'object' && result !== null && !Array.isArray(result)
          ? (() => {
              const copy = { ...result };
              ['tool', 'agentflow', 'action_taken', 'next_suggested_action', 'nextagentflow',
               'updatedNextQuery', 'nextuserflow', 'timestamp', 'push_results', 'scenario_types_options'].forEach(k => delete copy[k]);
              return copy;
            })()
          : result;

        if (typeof displayResult === 'string') {
          const cleaned = cleanBotResponseText(displayResult);
          if (cleaned) parts.push(formatTextResponse(cleaned));
        } else if (typeof displayResult === 'object' && displayResult !== null && Object.keys(displayResult).length > 0) {
          const cleaned = cleanBotResponseObject(displayResult);
          if (typeof cleaned === 'string') {
            const ct = cleanBotResponseText(cleaned);
            if (ct) parts.push(formatTextResponse(ct));
          } else if (Object.keys(cleaned).length > 0) {
            parts.push(formatJsonResult(cleaned));
          }
        }
      }

      // BRD creation: store confluence link
      const brdLink = childResponse.brd_content_link ?? childResponse.data?.brd_content_link;
      if (brdLink?.trim()) {
        setFinalBrdConfluenceLink(brdLink.trim());
        sessionStorage.setItem('brdConfluenceLink', brdLink.trim());
        const brdName = childResponse.project_name ?? childResponse.data?.project_name ?? projectName ?? '';
        if (brdName) {
          sessionStorage.setItem('brdDocumentName', brdName);
          if (!isProjectNameOverriddenRef.current) {
            setProjectName(brdName);
            sessionStorage.setItem('projectName', brdName);
          }
        }
        onBrdGenerated?.(brdLink.trim(), brdName);
        parts.push(`<strong>BRD Document:</strong> <a href="${escapeHtml(brdLink.trim())}" target="_blank" rel="noopener noreferrer" style="color: #3498B3; text-decoration: underline;">${escapeHtml(brdName || 'View BRD')}</a>`);
      }

      // User Manual: render the published Confluence page as a clickable link.
      const userManualLink = childResponse.confluence_url ?? childResponse.data?.confluence_url;
      if (userManualLink?.trim()) {
        const manualName = childResponse.project_name ?? childResponse.data?.project_name ?? projectName ?? 'View User Manual';
        parts.push(`<strong>User Manual:</strong> <a href="${escapeHtml(userManualLink.trim())}" target="_blank" rel="noopener noreferrer" style="color: #3498B3; text-decoration: underline;">${escapeHtml(manualName || 'View User Manual')}</a>`);
      }

      // User story creation: handle epics
      const epics = childResponse.epics ?? childResponse.data?.epics;
      if (epics && typeof epics === 'object' && Object.keys(epics).length > 0) {
        let epicItems = '';
        Object.keys(epics).forEach((epicKey) => {
          const epic = epics[epicKey];
          if (epic.browse_url) {
            epicItems += `<li style="margin-left: 8px; margin-bottom: 4px;"><span style="margin-right: 6px;">â—</span><a href="${escapeHtml(epic.browse_url)}" target="_blank" rel="noopener noreferrer" style="color: #3498B3; text-decoration: underline;">${escapeHtml(epicKey)}</a></li>`;
          }
        });
        if (epicItems) parts.push(`<strong>Created Epics:</strong><ul style="margin-top: 6px; padding-left: 8px;">${epicItems}</ul>`);

        // Notify parent to refresh Jira sidebar
        const generatedEpicKeys = Object.keys(epics);
        setIsRefreshingJiraEpics(true);
        const refreshPromise = onUserStoryGenerated?.(generatedEpicKeys);
        if (refreshPromise instanceof Promise) {
          refreshPromise.finally(() => setIsRefreshingJiraEpics(false));
        } else {
          setIsRefreshingJiraEpics(false);
        }
      }

      // Validation response: handle jira_dictionary and intentOfUpdateUserStory
      const childNextagentflow = childResponse.nextagentflow ?? childResponse.data?.nextagentflow ?? result?.nextagentflow;
      
      if (childNextagentflow === 'intentOfUpdateUserStory' || intent === 'validate_user_story') {
        const resultData = childResponse.data?.result ?? result;
        const dict = childResponse.jira_dictionary ?? childResponse.data?.jira_dictionary ?? result?.jira_dictionary;
        const newCreateList = childResponse.new_jira_createlist ?? childResponse.data?.new_jira_createlist ?? result?.new_jira_createlist;

        if (dict || resultData) {
          setValidatedStories(resultData);
          setLastValidationPayload(childResponse);
          setEditedValidatedDescriptions({});
          setEditedValidatedTitles({});
          if (dict && typeof dict === 'object') setJiraDictionary(dict);
          if (newCreateList) {
            if (Array.isArray(newCreateList)) {
              setNewJiraCreateList({ 'New Stories': newCreateList });
            } else if (typeof newCreateList === 'object') {
              setNewJiraCreateList(newCreateList);
            }
          }
          if (!childNextagentflow && intent === 'validate_user_story') {
            setNextagentflow('intentOfUpdateUserStory');
          }
          onJiraSelectionLock?.(true);
          setUserStoryTextLabel('Please validate your Jira Story by opening below jira link');
        }
      }

      // Scenario types options
      const scenarioOpts = childResponse.data?.scenario_types_options ?? result?.scenario_types_options;
      if (scenarioOpts && Array.isArray(scenarioOpts)) {
        setScenarioTypesOptions(scenarioOpts);
      }

      // Generated test cases list
      const genTestCases = childResponse.data?.generated_test_cases ?? result?.generated_test_cases;
      if (genTestCases && Array.isArray(genTestCases) && genTestCases.length > 0) {
        const parsed = genTestCases.map((tc: any, idx: number) => ({
          id: tc['Test Case ID'] || tc['test_case_id'] || `TC-${idx + 1}`,
          name: tc['Test Case Name'] || tc['test_case_name'] || '',
          description: tc['Test Case Description'] || tc['test_case_description'] || '',
          raw: tc,
        }));
        setGeneratedTestCasesList(parsed);
      }

      // Cron job handling
      const jobId = childResponse.data?.job_id ?? result?.job_id;
      if (jobId && onCronJobSubmitted) {
        const totalCount = childResponse.data?.total ?? result?.total ?? selectedJiraStories.length;
        const isTestScript = intent === 'generate_test_script';
        const jobName = generateJobName(isTestScript ? 'TS' : 'TC', totalCount);
        const cronJob: CronJob = {
          jobId: String(jobId),
          jobName,
          status: 'queued',
          agentType: isTestScript ? 'Test Script Agent' : 'Test Case Agent',
          type: isTestScript ? 'test-script' : 'test-case',
          total: totalCount,
          completedCount: 0,
          failedCount: 0,
          createdAt: new Date().toISOString(),
          stories: selectedJiraStories?.map(s => ({ key: s.key, summary: s.summary })) || [],
        };
        onCronJobSubmitted(cronJob);
      }
    }

    const childActionResults = childResponse?.data?.action_results ?? childResponse?.action_results;
    const applyActionResult =
      findSuccessfulActionResult(childActionResults, 'execute_apply_brd_updates')
      ?? findSuccessfulActionResult(data.data?.action_results, 'execute_apply_brd_updates');

    if (applyActionResult) {
      const applyPayload = applyActionResult.result?.applied ? applyActionResult.result : applyActionResult.result?.result;
      const applied = applyPayload?.applied;
      const createdEpics = Array.isArray(applied?.created_epics) ? applied.created_epics : [];

      if (createdEpics.length > 0) {
        const epicItems = createdEpics
          .filter((epic: any) => typeof epic?.issue_key === 'string' && epic.issue_key.trim().length > 0 && typeof epic?.browse_url === 'string' && epic.browse_url.trim().length > 0)
          .map((epic: any) => `<li style="margin-left: 8px; margin-bottom: 4px;"><span style="margin-right: 6px;">\u25CF</span><a href="${escapeHtml(epic.browse_url)}" target="_blank" rel="noopener noreferrer" style="color: #3498B3; text-decoration: underline;">${escapeHtml(epic.issue_key)}</a></li>`)
          .join('');

        if (epicItems) {
          parts.push(`<strong>Created Epics:</strong><ul style="margin-top: 6px; padding-left: 8px;">${epicItems}</ul>`);
        }
      }

      const affectedEpicKeys = Array.from(
        new Set([
          ...buildSelectedEpicKeys(),
          ...createdEpics
            .map((epic: any) => epic?.issue_key)
            .filter((issueKey: unknown): issueKey is string => typeof issueKey === 'string' && issueKey.trim().length > 0),
        ])
      );

      const hasAppliedChanges = Boolean(
        applied?.updated_epics?.length
        || applied?.updated_stories?.length
        || applied?.created_stories?.length
        || applied?.created_epics?.length
      );

      if (hasAppliedChanges) {
        refreshJiraAfterStoryUpdate(affectedEpicKeys);
      }
    }

    // 2b. Fallback: process action_results when child_response is absent (new streaming format)
    const actionResults = data.data?.action_results;
    if (!childResponse && actionResults && Array.isArray(actionResults)) {
      for (const ar of actionResults) {
        if (!ar.success || !ar.result) continue;
        const arResult = ar.result;

        // BRD link validation
        if (ar.action === 'validate_brd_link' && arResult.brd_link) {
          setFinalBrdConfluenceLink(arResult.brd_link);
          sessionStorage.setItem('brdConfluenceLink', arResult.brd_link);
        }

        // User Manual agent result — render confluence link as styled hyperlink
        if (ar.action === 'call_user_manual_agent' && arResult.confluence_url?.trim()) {
          const manualLink = arResult.confluence_url.trim();
          const manualName = arResult.project_name ?? projectName ?? 'View User Manual';
          parts.push(`<strong>User Manual:</strong> <a href="${escapeHtml(manualLink)}" target="_blank" rel="noopener noreferrer" style="color: #3498B3; text-decoration: underline;">${escapeHtml(manualName || 'View User Manual')}</a>`);
        }

        // User story agent result — epics, stories, docx download
        if (ar.action === 'call_user_story_agent' && arResult.success) {
          // Agent message
          if (arResult.message) {
            const cleaned = cleanBotResponseText(arResult.message);
            if (cleaned) parts.push(formatTextResponse(cleaned));
          }

          // Render epics with user stories & acceptance criteria
          if (Array.isArray(arResult.epics) && arResult.epics.length > 0) {
            let epicHtml = '';
            for (const epic of arResult.epics) {
              epicHtml += `<div style="margin-bottom: 12px;">`;
              epicHtml += `<strong style="font-size: 0.9rem;">\uD83D\uDCC1 ${escapeHtml(epic.epic_title)}</strong>`;
              if (Array.isArray(epic.user_stories)) {
                for (const story of epic.user_stories) {
                  let storyBody = '';
                  if (story.description) {
                    storyBody += `<div class="collapsible-field">${formatTextResponse(story.description)}</div>`;
                  }
                  if (Array.isArray(story.acceptance_criteria) && story.acceptance_criteria.length > 0) {
                    storyBody += `<div class="collapsible-field"><strong>Acceptance Criteria:</strong><ul style="margin: 4px 0 0 16px;">`;
                    for (const ac of story.acceptance_criteria) {
                      storyBody += `<li style="margin-bottom: 4px; font-size: 0.8rem;">${formatTextResponse(ac.criterion)}</li>`;
                    }
                    storyBody += `</ul></div>`;
                  }
                  epicHtml += `<details class="collapsible-test-item" style="margin-left: 8px; margin-top: 6px;">`;
                  epicHtml += `<summary>${escapeHtml(story.title)}</summary>`;
                  epicHtml += `<div class="collapsible-test-body">${storyBody}</div>`;
                  epicHtml += `</details>`;
                }
              }
              epicHtml += `</div>`;
            }
            parts.push(`<div class="collapsible-section"><div class="collapsible-section-header">\uD83D\uDCCB Generated Epics & User Stories</div>${epicHtml}</div>`);
          }

          // DOCX download link
          if (arResult.docx_download_url) {
            const downloadUrl = arResult.docx_download_url.startsWith('http')
              ? arResult.docx_download_url
              : gatewayUrl(arResult.docx_download_url.startsWith('/') ? arResult.docx_download_url : `/${arResult.docx_download_url}`);
            parts.push(`<strong>\uD83D\uDCE5 Download:</strong> <a href="${escapeHtml(downloadUrl)}" target="_blank" rel="noopener noreferrer" style="color: #3498B3; text-decoration: underline;">Download User Stories (.docx)</a>`);
          }
        }

        // Jira epic links — object format { "EPIC-KEY": { browse_url, ... } }
        const epicsObj = arResult.epics ?? arResult;
        if (epicsObj && typeof epicsObj === 'object' && !Array.isArray(epicsObj)) {
          let epicItems = '';
          const epicKeys: string[] = [];
          Object.keys(epicsObj).forEach((epicKey) => {
            const epic = epicsObj[epicKey];
            if (epic && typeof epic === 'object' && epic.browse_url) {
              epicKeys.push(epicKey);
              epicItems += `<li style="margin-left: 8px; margin-bottom: 4px;"><span style="margin-right: 6px;">\u25CF</span><a href="${escapeHtml(epic.browse_url)}" target="_blank" rel="noopener noreferrer" style="color: #3498B3; text-decoration: underline;">${escapeHtml(epicKey)}</a></li>`;
            }
          });
          if (epicItems) {
            parts.push(`<strong>Created Epics:</strong><ul style="margin-top: 6px; padding-left: 8px;">${epicItems}</ul>`);
            // Notify parent to refresh Jira sidebar
            setIsRefreshingJiraEpics(true);
            const refreshPromise = onUserStoryGenerated?.(epicKeys);
            if (refreshPromise instanceof Promise) {
              refreshPromise.finally(() => setIsRefreshingJiraEpics(false));
            } else {
              setIsRefreshingJiraEpics(false);
            }
          }
        }

        // RAG Query result - display sources from execute_query action
        if (ar.action === 'execute_query' && arResult.sources && Array.isArray(arResult.sources) && arResult.sources.length > 0) {
          const topSources = arResult.sources.slice(0, 5);
          const sourceItems = topSources.map((src: any) => {
            const filename = src.filename || src.source || 'Unknown';
            const score = src.score ? (src.score * 100).toFixed(1) : null;
            const isUrl = filename.startsWith('http://') || filename.startsWith('https://');
            const displayName = isUrl ? filename : filename.split('/').pop() || filename;
            const scoreDisplay = score ? ` <span style="color: #6b7280; font-size: 0.75rem;">(${score}% match)</span>` : '';
            if (isUrl) {
              return `<li style="margin-bottom: 4px;"><a href="${escapeHtml(filename)}" target="_blank" rel="noopener noreferrer" style="color: #3498B3; text-decoration: underline;">${escapeHtml(displayName)}</a>${scoreDisplay}</li>`;
            }
            return `<li style="margin-bottom: 4px;">${escapeHtml(displayName)}${scoreDisplay}</li>`;
          }).join('');
          parts.push(`<strong>📚 Sources (Top ${topSources.length}):</strong><ul style="margin-top: 6px; padding-left: 16px; list-style-type: disc;">${sourceItems}</ul>`);
        }
      }
    }

    // 2c. Fallback: extract jira_dictionary & new_jira_createlist from data.data when child_response is absent
    if (!childResponse && intent === 'validate_user_story') {
      const dict = data.data?.jira_dictionary;
      const newCreateList = data.data?.new_jira_createlist;
      // Also try extracting from action_results
      let arDict = dict;
      let arNewList = newCreateList;
      if (actionResults && Array.isArray(actionResults)) {
        for (const ar of actionResults) {
          if (!ar.success || !ar.result) continue;
          if (!arDict && ar.result.jira_dictionary) arDict = ar.result.jira_dictionary;
          if (!arNewList && ar.result.new_jira_createlist) arNewList = ar.result.new_jira_createlist;
        }
      }
      const resultData = data.data?.result ?? data.data?.result_text;
      if (arDict || resultData) {
        setValidatedStories(resultData || true);
        setLastValidationPayload(data);
        setEditedValidatedDescriptions({});
        setEditedValidatedTitles({});
        if (arDict && typeof arDict === 'object') setJiraDictionary(arDict);
        // Convert flat array to Record<string, string[]> if needed
        if (arNewList) {
          if (Array.isArray(arNewList)) {
            setNewJiraCreateList({ 'New Stories': arNewList });
          } else if (typeof arNewList === 'object') {
            setNewJiraCreateList(arNewList);
          }
        }
        setNextagentflow('intentOfUpdateUserStory');
        onJiraSelectionLock?.(true);
        setUserStoryTextLabel('Please validate your Jira Story by opening below jira link');
      }
    }

    // 2d. Fallback cron job handling — extract job_id from data.data when child_response is absent
    if (!childResponse && onCronJobSubmitted) {
      const fallbackJobId = data.data?.job_id;
      if (fallbackJobId) {
        const fallbackTotal = data.data?.total ?? selectedJiraStories.length;
        const isTestScript = intent === 'generate_test_script';
        const jobName = generateJobName(isTestScript ? 'TS' : 'TC', fallbackTotal);
        const cronJob: CronJob = {
          jobId: String(fallbackJobId),
          jobName,
          status: 'queued',
          agentType: isTestScript ? 'Test Script Agent' : 'Test Case Agent',
          type: isTestScript ? 'test-script' : 'test-case',
          total: fallbackTotal,
          completedCount: 0,
          failedCount: 0,
          createdAt: new Date().toISOString(),
          stories: selectedJiraStories?.map(s => ({ key: s.key, summary: s.summary })) || [],
        };
        onCronJobSubmitted(cronJob);
      }
    }

    // 3. Push results (test scripts to Harness repo) - check data.data.push_results
    const pushResults = data.data?.push_results;
    if (pushResults && typeof pushResults === 'object' && Object.keys(pushResults).length > 0) {
      const pushKeys = Object.keys(pushResults);
      const links = pushKeys.map((key) => {
        const urlArray = pushResults[key];
        const firstUrl = Array.isArray(urlArray) && urlArray.length > 0 ? urlArray[0] : '';
        const fullUrlStr = typeof firstUrl === 'string' ? firstUrl : String(firstUrl ?? '');
        const hrefValue = fullUrlStr.substring(0, fullUrlStr.lastIndexOf('/') + 1);
        return `<a href="${hrefValue}" target="_blank" rel="noopener noreferrer" style="color: #0278D5; text-decoration: underline;">${escapeHtml(key)}</a>`;
      }).join('<br>');
      if (pushKeys.length > 10) {
        parts.push(`<strong>Scripts are pushed to Code Repo:</strong><div style="max-height: 280px; overflow-y: auto; margin-top: 6px; padding-right: 6px; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 8px;">${links}</div>`);
      } else {
        parts.push(`<strong>Scripts are pushed to Code Repo:</strong><br>${links}`);
      }
    }

    // 3b. Test Data harness file URLs - check data.data.test_data.harness_file_urls
    const testData = data.data?.test_data;
    if (testData && testData.status === 'success' && Array.isArray(testData.harness_file_urls) && testData.harness_file_urls.length > 0) {
      const fileLinks = testData.harness_file_urls.map((url: string) => {
        const safeUrl = escapeHtml(url);
        return `<div style="display: flex; align-items: center; gap: 12px; margin-top: 6px; flex-wrap: wrap;">`
          + `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer" style="display: inline-flex; align-items: center; color: #0278D5; text-decoration: underline;">View Generated Test Data</a>`
          + `</div>`;
      }).join('');
      parts.push(`<strong>Test data generated and pushed to Code Repo.</strong>${fileLinks}`);
    }

    // 3c. RAG Query sources - display top 5 source filenames from knowledge base query
    const sources = data.data?.sources || data.data?.result?.sources || childResponse?.data?.result?.sources || childResponse?.result?.sources;
    if (sources && Array.isArray(sources) && sources.length > 0) {
      const topSources = sources.slice(0, 5);
      const sourceItems = topSources.map((src: any, idx: number) => {
        const filename = src.filename || src.source || 'Unknown';
        const score = src.score ? (src.score * 100).toFixed(1) : null;
        const isUrl = filename.startsWith('http://') || filename.startsWith('https://');
        const displayName = isUrl ? filename : filename.split('/').pop() || filename;
        const scoreDisplay = score ? ` <span style="color: #6b7280; font-size: 0.75rem;">(${score}% match)</span>` : '';
        if (isUrl) {
          return `<li style="margin-bottom: 4px;"><a href="${escapeHtml(filename)}" target="_blank" rel="noopener noreferrer" style="color: #3498B3; text-decoration: underline;">${escapeHtml(displayName)}</a>${scoreDisplay}</li>`;
        }
        return `<li style="margin-bottom: 4px;">${escapeHtml(displayName)}${scoreDisplay}</li>`;
      }).join('');
      parts.push(`<strong>📚 Sources (Top ${topSources.length}):</strong><ul style="margin-top: 6px; padding-left: 16px; list-style-type: disc;">${sourceItems}</ul>`);
    }

    // 4. Suggested actions
    if (data.suggested_actions && data.suggested_actions.length > 0) {
      setLastSuggestedActions(data.suggested_actions);
      setNextSuggestedAction(data.suggested_actions[0].action);
    } else {
      setLastSuggestedActions([]);
    }

    if (parts.length > 0) {
      addMessage(parts.join('<br><br>'), 'bot');
    }

  };

  const escapeHtml = (text: string): string => {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  };

  // Convert an HTML fragment to a plain-text representation that preserves
  // visible block formatting (paragraphs, <br>, bullet/ordered lists,
  // headings). Used by the "Copy to Jira" action so the right-side
  // description mirrors the layout shown on the left.
  const htmlToFormattedText = (html: string): string => {
    if (!html) return '';
    const container = document.createElement('div');
    container.innerHTML = html;

    const walk = (node: Node, listCtx?: { type: 'ul' | 'ol'; index: number }): string => {
      if (node.nodeType === Node.TEXT_NODE) {
        return (node.textContent || '').replace(/\s+/g, ' ');
      }
      if (node.nodeType !== Node.ELEMENT_NODE) return '';
      const el = node as HTMLElement;
      const tag = el.tagName.toLowerCase();

      if (tag === 'br') return '\n';
      if (tag === 'hr') return '\n---\n';

      if (tag === 'li') {
        const inner = Array.from(el.childNodes)
          .map(c => walk(c))
          .join('')
          .trim();
        const bullet = listCtx?.type === 'ol' ? `${listCtx.index}.` : '-';
        return `${bullet} ${inner}\n`;
      }

      if (tag === 'ul' || tag === 'ol') {
        const items = Array.from(el.children).filter(c => c.tagName.toLowerCase() === 'li');
        let out = '';
        items.forEach((li, idx) => {
          out += walk(li, { type: tag as 'ul' | 'ol', index: idx + 1 });
        });
        return `\n${out}\n`;
      }

      const blockTags = new Set(['p', 'div', 'section', 'article', 'header', 'footer', 'pre', 'blockquote', 'details', 'summary']);
      const headingTags = new Set(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']);

      const inner = Array.from(el.childNodes).map(c => walk(c)).join('');

      if (headingTags.has(tag)) {
        return `\n${inner.trim()}\n`;
      }
      if (blockTags.has(tag)) {
        return `\n${inner}\n`;
      }
      return inner;
    };

    const raw = walk(container);
    return raw
      .replace(/\u00a0/g, ' ')
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  };

  const formatTextResponse = (text: string): string => {
    // Extract and store hidden variables before removing them from display
    let hiddenVars = '';
    
    const refinedStoryMatch = text.match(/(Refined User Story:[\s\S]*?)(?=\n\n[A-Z]|\n\n##|$)/);
    if (refinedStoryMatch) {
      const cleanedSection = refinedStoryMatch[1].replace(/>/g, '');
      text = text.replace(refinedStoryMatch[1], cleanedSection);
    }
    
    // Escape HTML
    let formatted = escapeHtml(text);
    
    // Convert ## headings to bold (remove ## and make text bold)
    formatted = formatted.replace(/##\s*(.*?)(?=\n|$)/g, '<strong>$1</strong>');
    
    // Convert **text** to bold
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Add line break before Status: if it's not already on a new line
    formatted = formatted.replace(/([^\n])(Status:)/g, '$1\n\n$2');
    
    // Convert \n\n to paragraph breaks
    formatted = formatted.replace(/\n\n/g, '<br><br>');
    
    // Convert single \n to line breaks
    formatted = formatted.replace(/\n/g, '<br>');
    
    // Add hidden variables at the end
    return hiddenVars + formatted;
  };

  /* â”€â”€ Collapsible formatters for test scenarios / test cases / Jira â”€â”€ */

  // Format a single test case object into collapsible HTML
  const formatTestCase = (tc: any): string => {
    const id = tc['Test Case ID'] || tc['test_case_id'] || 'Unknown ID';
    const name = tc['Test Case Name'] || tc['test_case_name'] || '';
    const desc = tc['Test Case Description'] || tc['test_case_description'] || '';
    const steps = tc['Steps'] || tc['steps'] || [];

    let inner = '';
    if (desc) {
      inner += `<div class="collapsible-field"><strong>Description:</strong> ${formatTextResponse(String(desc))}</div>`;
    }

    // Render any other fields that aren't already handled
    for (const [k, v] of Object.entries(tc)) {
      if (['Test Case ID', 'test_case_id', 'Test Case Name', 'test_case_name', 'Test Case Description', 'test_case_description', 'Steps', 'steps'].includes(k)) continue;
      const label = k.replace(/_/g, ' ').replace(/\b\w/g, l => (l as string).toUpperCase());
      inner += `<div class="collapsible-field"><strong>${escapeHtml(label)}:</strong> ${formatTextResponse(String(v))}</div>`;
    }

    if (Array.isArray(steps) && steps.length > 0) {
      inner += `<div class="collapsible-steps"><strong>Steps:</strong>`;
      inner += `<table class="collapsible-steps-table"><thead><tr><th>#</th><th>Step</th><th>Expected Result</th></tr></thead><tbody>`;
      steps.forEach((step: any) => {
        const num = step['Step Number'] || step['step_number'] || '';
        const action = step['Test Case Step'] || step['test_case_step'] || '';
        const expected = step['Expected Results'] || step['expected_results'] || step['Expected Result'] || '';
        inner += `<tr><td>${escapeHtml(String(num))}</td><td>${formatTextResponse(String(action))}</td><td>${formatTextResponse(String(expected))}</td></tr>`;
      });
      inner += `</tbody></table></div>`;
    }

    const summaryText = name ? `${escapeHtml(String(id))} â€” ${escapeHtml(String(name))}` : escapeHtml(String(id));
    return `<details class="collapsible-test-item"><summary>${summaryText}</summary><div class="collapsible-test-body">${inner}</div></details>`;
  };

  // Format a single test scenario object into collapsible HTML
  const formatTestScenarioObj = (ts: any): string => {
    const id = ts['Test Scenario ID'] || ts['test_scenario_id'] || ts['Scenario ID'] || ts['scenario_id'] || 'Unknown';
    const desc = ts['Test Scenario Description'] || ts['test_scenario_description'] || ts['Description'] || ts['description'] || '';
    const expected = ts['Expected Results'] || ts['expected_results'] || ts['Expected Result'] || '';
    const priority = ts['Priority'] || ts['priority'] || '';
    const preCond = ts['Pre-Condition'] || ts['pre_condition'] || ts['Precondition'] || ts['precondition'] || '';

    let inner = '';
    if (desc) inner += `<div class="collapsible-field"><strong>Description:</strong> ${formatTextResponse(String(desc))}</div>`;
    if (expected) inner += `<div class="collapsible-field"><strong>Expected Results:</strong> ${formatTextResponse(String(expected))}</div>`;
    if (priority) inner += `<div class="collapsible-field"><strong>Priority:</strong> ${escapeHtml(String(priority))}</div>`;
    if (preCond) inner += `<div class="collapsible-field"><strong>Pre-Condition:</strong> ${formatTextResponse(String(preCond))}</div>`;

    // Render any remaining fields
    const handled = ['Test Scenario ID','test_scenario_id','Scenario ID','scenario_id','Test Scenario Description','test_scenario_description','Description','description','Expected Results','expected_results','Expected Result','Priority','priority','Pre-Condition','pre_condition','Precondition','precondition'];
    for (const [k, v] of Object.entries(ts)) {
      if (handled.includes(k)) continue;
      const label = k.replace(/_/g, ' ').replace(/\b\w/g, l => (l as string).toUpperCase());
      inner += `<div class="collapsible-field"><strong>${escapeHtml(label)}:</strong> ${formatTextResponse(String(v))}</div>`;
    }

    return `<details class="collapsible-test-item"><summary>${escapeHtml(String(id))}</summary><div class="collapsible-test-body">${inner}</div></details>`;
  };

  // Format test scenarios (string OR array) into collapsible sections
  const formatTestScenarios = (scenarios: any): string => {
    // If it's an array of objects, render each as collapsible
    if (Array.isArray(scenarios)) {
      let html = `<div class="collapsible-section"><div class="collapsible-section-header">ðŸ“‹ Generated Test Scenarios (${scenarios.length})</div>`;
      scenarios.forEach((ts: any) => {
        if (typeof ts === 'object' && ts !== null) {
          html += formatTestScenarioObj(ts);
        } else {
          html += `<div class="collapsible-field">&#8226; ${formatTextResponse(String(ts))}</div>`;
        }
      });
      html += `</div>`;
      return html;
    }

    // It's a string â€” parse scenario blocks
    const text = String(scenarios);
    const lines = text.split(/\n/);
    const scenarioBlocks: { id: string; content: string }[] = [];
    let currentId = '';
    let currentContent = '';

    for (const line of lines) {
      // Match patterns like "Test Scenario ID: TS_010" or "Scenario ID: SC_001" or just "TS_010"
      const idMatch = line.match(/^(?:Test\s+)?Scenario\s*(?:ID)?\s*[:\-]\s*(\S+)/i) || line.match(/^(TS[-_]\d+\S*)/i);
      if (idMatch) {
        if (currentId) {
          scenarioBlocks.push({ id: currentId, content: currentContent.trim() });
        }
        currentId = idMatch[1].trim();
        currentContent = line.substring(idMatch[0].length).trim();
      } else {
        currentContent += '\n' + line;
      }
    }
    if (currentId) {
      scenarioBlocks.push({ id: currentId, content: currentContent.trim() });
    }

    if (scenarioBlocks.length > 0) {
      let html = `<div class="collapsible-section"><div class="collapsible-section-header">ðŸ“‹ Generated Test Scenarios (${scenarioBlocks.length})</div>`;
      scenarioBlocks.forEach(block => {
        // Parse the content string into labeled fields for nicer display
        let body = block.content;
        body = body.replace(/(?:Test\s+)?Scenario\s+Description\s*:\s*/gi, '<br><strong>Description:</strong> ');
        body = body.replace(/Expected\s+Results?\s*:\s*/gi, '<br><strong>Expected Results:</strong> ');
        body = body.replace(/Priority\s*:\s*/gi, '<br><strong>Priority:</strong> ');
        body = body.replace(/Pre-?Condition\s*:\s*/gi, '<br><strong>Pre-Condition:</strong> ');
        html += `<details class="collapsible-test-item"><summary>${escapeHtml(block.id)}</summary><div class="collapsible-test-body">${body}</div></details>`;
      });
      html += `</div>`;
      return html;
    }

    // Fallback: single collapsible with the entire text
    return `<div class="collapsible-section"><div class="collapsible-section-header">ðŸ“‹ Generated Test Scenarios</div><details class="collapsible-test-item"><summary>View Scenarios</summary><div class="collapsible-test-body">${formatTextResponse(text)}</div></details></div>`;
  };

  // Format Jira push result as one collapsible block
  const formatJiraPushResult = (result: any): string => {
    let inner = '';
    if (typeof result === 'object' && result !== null) {
      inner = formatJsonResult(result, 0);
    } else {
      inner = formatTextResponse(String(result));
    }
    return `<div class="collapsible-section"><details class="collapsible-test-item collapsible-jira"><summary class="collapsible-jira-summary">&#127915; Jira Push Result</summary><div class="collapsible-test-body">${inner}</div></details></div>`;
  };

  const formatJsonResult = (obj: any, indent = 0): string => {
    let html = '';
    const spacing = '&nbsp;&nbsp;'.repeat(indent);

    for (const [key, value] of Object.entries(obj)) {
      const formattedKey = key.replace(/_/g, ' ').replace(/\b\w/g, l => (l as string).toUpperCase());

      // --- Collapsible: generated_test_scenarios (string or array) ---
      if (key === 'generated_test_scenarios') {
        html += formatTestScenarios(value);
        continue;
      }

      // --- Collapsible: jira_push_result ---
      if (key === 'jira_push_result') {
        html += formatJiraPushResult(value);
        continue;
      }

      // --- Collapsible: generated_test_cases ---
      if (key === 'generated_test_cases' && Array.isArray(value)) {
        html += `<div class="collapsible-section"><div class="collapsible-section-header">&#129514; Generated Test Cases (${value.length})</div>`;
        value.forEach((tc: any) => {
          if (typeof tc === 'object' && tc !== null) {
            html += formatTestCase(tc);
          } else {
            html += `<div class="collapsible-field">â€¢ ${formatTextResponse(String(tc))}</div>`;
          }
        });
        html += `</div>`;
        continue;
      }

      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        html += `${spacing}<strong>${escapeHtml(formattedKey)}:</strong><br>`;
        html += formatJsonResult(value, indent + 1);
      } else if (Array.isArray(value)) {
        html += `${spacing}<strong>${escapeHtml(formattedKey)}:</strong><br>`;
        value.forEach((item, index) => {
          if (typeof item === 'object') {
            html += `${spacing}&nbsp;&nbsp;<em>Item ${index + 1}:</em><br>`;
            html += formatJsonResult(item, indent + 2);
          } else {
            html += `${spacing}&nbsp;&nbsp;â€¢ ${formatTextResponse(String(item))}<br>`;
          }
        });
      } else {
        const formattedValue = typeof value === 'string' ? formatTextResponse(value) : escapeHtml(String(value));
        html += `${spacing}<strong>${escapeHtml(formattedKey)}:</strong> ${formattedValue}<br>`;
      }
    }

    return html;
  };

  const addMessage = (content: string, type: 'bot' | 'user' | 'error' = 'bot') => {
    messageIdCounter.current += 1;
    const newMessage: Message = {
      id: `${Date.now()}-${messageIdCounter.current}`,
      type,
      content,
    };
    setMessages((prev) => [...prev, newMessage]);
  };

  const removeAnalyzingMessage = () => {
    // Clear the executing timer if it exists
    if (executingTimerRef.current) {
      clearTimeout(executingTimerRef.current);
      executingTimerRef.current = null;
    }
    setIsExecutingMode(false);
    setMessages((prev) => prev.filter((msg) => 
      !msg.content.includes('Analyzing your request...') && 
      !msg.content.includes('>Executing</span>') &&
      !msg.content.includes('Validating user stories...') &&
      !msg.content.includes('Generating test cases...')
    ));
  };

  const updateToExecutingMessage = () => {
    const executingIcon = `<span style="display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; position: relative; margin-right: 6px; vertical-align: middle;">
      <span style="position: absolute; width: 6px; height: 6px; background-color: #F97316; border-radius: 50%; animation: executingSquare 1.6s linear infinite; animation-delay: 0s;"></span>
      <span style="position: absolute; width: 6px; height: 6px; background-color: #F97316; border-radius: 50%; animation: executingSquare 1.6s linear infinite; animation-delay: 0.4s;"></span>
      <span style="position: absolute; width: 6px; height: 6px; background-color: #F97316; border-radius: 50%; animation: executingSquare 1.6s linear infinite; animation-delay: 0.8s;"></span>
    </span>`;
    const executingText = `<span style="display: inline-flex; align-items: center;">
      <span style="color: #F97316; font-weight: 500;">Executing</span>
      <span style="display: inline-flex; margin-left: 2px;">
        <span style="color: #F97316; animation: executingDots 1.4s infinite; animation-delay: 0s;">.</span>
        <span style="color: #F97316; animation: executingDots 1.4s infinite; animation-delay: 0.2s;">.</span>
        <span style="color: #F97316; animation: executingDots 1.4s infinite; animation-delay: 0.4s;">.</span>
      </span>
    </span>`;
    setMessages((prev) => prev.map((msg) => 
      msg.content.includes('Analyzing your request...') 
        ? { ...msg, content: `${executingIcon} ${executingText}` }
        : msg
    ));
    setIsExecutingMode(true);
  };

  const cleanBotResponseText = (text: string): string => {
    // Remove "Query: <text>" lines entirely
    let cleaned = text.replace(/^Query:\s*.*$/gm, '');
    // Remove the word "Analysis:" but keep the text after it
    cleaned = cleaned.replace(/\bAnalysis:\s*/g, '');
    // Trim leading/trailing whitespace and collapse excessive newlines
    cleaned = cleaned.replace(/^\s*\n+/, '').replace(/\n{3,}/g, '\n\n').trim();
    return cleaned;
  };

  const cleanBotResponseObject = (obj: any): any => {
    if (typeof obj !== 'object' || obj === null || Array.isArray(obj)) return obj;
    // If both "analysis" and "result" string fields exist, combine them without labels
    const analysisVal = Object.entries(obj).find(([k]) => k.toLowerCase() === 'analysis')?.[1];
    const resultVal = Object.entries(obj).find(([k]) => k.toLowerCase() === 'result')?.[1];
    if (typeof analysisVal === 'string' && typeof resultVal === 'string') {
      return [analysisVal, resultVal].filter(Boolean).join('\n\n');
    }
    const cleaned: any = {};
    for (const [key, value] of Object.entries(obj)) {
      const lowerKey = key.toLowerCase();
      // Remove "query" and "job_id" keys entirely
      if (lowerKey === 'query' || lowerKey === 'job_id') continue;
      // For "analysis" key, unwrap its value if it's the only meaningful field
      if (lowerKey === 'analysis') {
        if (typeof value === 'string') {
          return value;
        }
        cleaned[key] = value;
        continue;
      }
      cleaned[key] = value;
    }
    return cleaned;
  };

  const displayAnalysisResult = (result: any) => {
    if (typeof result === 'string') {
      const cleaned = cleanBotResponseText(result);
      if (!cleaned) return;
      const formattedResult = formatTextResponse(cleaned);
      addMessage(`${formattedResult}`, 'bot');
    } else if (typeof result === 'object') {
      const cleaned = cleanBotResponseObject(result);
      // If cleaning unwrapped to a string, format as text
      if (typeof cleaned === 'string') {
        const cleanedText = cleanBotResponseText(cleaned);
        if (!cleanedText) return;
        const formattedResult = formatTextResponse(cleanedText);
        addMessage(`${formattedResult}`, 'bot');
      } else {
        // Check if cleaned object is empty
        if (Object.keys(cleaned).length === 0) return;
        const formattedResult = formatJsonResult(cleaned);
        addMessage(`${formattedResult}`, 'bot');
      }
    } else {
      const cleaned = cleanBotResponseText(String(result));
      if (!cleaned) return;
      const formattedResult = formatTextResponse(cleaned);
      addMessage(`${formattedResult}`, 'bot');
    }
  };  
  

  const displayNextAction = (nextSuggestedAction: string, nextagentflow: string) => {  
    // Display next suggested action is now handled in the UI input section
    // Values are stored in state and rendered before the Query Text label
  };  

  // Handle click on a suggested action button - sends the action through the chat stream
  const handleSuggestedActionClick = async (action: SuggestedActionItem) => {
    if (isLoading || !sessionId) return;
    setLastSuggestedActions([]);
    setNextSuggestedAction('');

    // "Ask another question" is a UI-reset action, not a query to send.
    // Focus the input so the user can type their next question.
    const resetActions = ['ask another question', 'ask a follow-up question'];
    if (resetActions.includes(action.action.toLowerCase())) {
      setQueryInputText('');
      return;
    }

    addMessage(escapeHtml(action.action), 'user');
    setIsLoading(true);

    messageIdCounter.current += 1;
    const progressMsgId = `suggested-action-${Date.now()}-${messageIdCounter.current}`;
    const initialProgressHtml = buildMilestoneHtml({
      type: 'milestone', stage: 'received', title: 'Processing',
      description: 'Starting...', progress: 0.05, icon: '📥', timestamp: new Date().toISOString(),
    });
    setMessages(prev => [...prev, { id: progressMsgId, type: 'bot' as const, content: initialProgressHtml }]);

    // Sanitize message: strip "from this BRD" / "from BRD" which triggers
    // an unhandled error in the SDLC orchestrator's BRD-reference resolution.
    const sanitizedMessage = action.action.replace(/\s+from\s+(this\s+)?BRD/gi, '').trim();

    // buildChatContext() returns {} when nextagentflow isn't set (suggested
    // actions bypass the regular agent-selection flow).  Carry forward the
    // BRD link and project name so the orchestrator has the context it needs.
    const extraCtx: Record<string, any> = {};
    if (finalBrdConfluenceLink.trim()) extraCtx.brd_link = finalBrdConfluenceLink.trim();
    if (projectName.trim()) extraCtx.project_name = projectName.trim();

    try {
      const data = await callChatStreamApi(
        sanitizedMessage,
        progressMsgId,
        Object.keys(extraCtx).length > 0 ? extraCtx : undefined,
        undefined,
        action.intent,
      );
      setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));
      handleChatSuccess(data);
    } catch (error: any) {
      setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      addMessage(`<strong>Please RETRY, ❌ Error:</strong> ${escapeHtml(errorMessage)}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const displayBrdConfluenceLink= (brdLink: string) => {
    // Display BRD Confluence link if available
    if (brdLink && brdLink.trim() && projectName && projectName.trim()) {
      const confluenceIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="display: inline-block; vertical-align: middle; margin-right: 4px;"><path d="M2.5 2C2.22386 2 2 2.22386 2 2.5V21.5C2 21.7761 2.22386 22 2.5 22H21.5C21.7761 22 22 21.7761 22 21.5V2.5C22 2.22386 21.7761 2 21.5 2H2.5ZM5.71429 17.1429C5.71429 17.1429 5.28571 17.5714 4.85714 17.5714C4.42857 17.5714 4 17.1429 4 16.7143V7.28571C4 6.85714 4.42857 6.42857 4.85714 6.42857C5.28571 6.42857 5.71429 6.85714 5.71429 7.28571V17.1429ZM11.5714 11.5714C11.5714 11.5714 11.1429 12 10.7143 12C10.2857 12 9.85714 11.5714 9.85714 11.1429V7.28571C9.85714 6.85714 10.2857 6.42857 10.7143 6.42857C11.1429 6.42857 11.5714 6.85714 11.5714 7.28571V11.5714ZM17.4286 17.1429C17.4286 17.1429 17 17.5714 16.5714 17.5714C16.1429 17.5714 15.7143 17.1429 15.7143 16.7143V7.28571C15.7143 6.85714 16.1429 6.42857 16.5714 6.42857C17 6.42857 17.4286 6.85714 17.4286 7.28571V17.1429Z" fill="#0052CC"/></svg>`;
      addMessage(`ðŸ“‹ <strong>BRD Document:</strong> ${confluenceIcon}<a href="${escapeHtml(brdLink)}" target="_blank" rel="noopener noreferrer" style="color: #3498B3; text-decoration: underline;">${projectName}</a>`, 'bot');
    }
  };

  const displayEpicValues = (epics: any) => {
    // Display epic links if epics object is not empty
    if (epics && typeof epics === 'object' && Object.keys(epics).length > 0) {
   
      const jiraIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="display: inline-block; vertical-align: middle; margin-right: 4px;"><path d="M11.5719 0.513916L2.32129 9.76453L0.513672 11.5722L11.5719 22.6304L13.3796 20.8227L4.91113 12.3543L2.34951 9.79274L11.5719 0.570312L20.7943 9.79274L18.2327 12.3543L16.4533 14.1337L11.5719 19.0151L13.3796 20.8227L22.63 11.5722L20.8224 9.76453L11.5719 0.513916Z" fill="#2684FF"/></svg>`;
      
      let epicItems = '';
      Object.keys(epics).forEach((epicKey) => {
        const epic = epics[epicKey];
        if (epic.browse_url) {
          epicItems += `<li style="margin-left: 8px; margin-bottom: 4px;"><span style="margin-right: 6px;">â—</span><a href="${escapeHtml(epic.browse_url)}" target="_blank" rel="noopener noreferrer" style="color: #3498B3; text-decoration: underline;">${escapeHtml(epicKey)}</a></li>`;
        }
      });
      
      if (epicItems) {
        addMessage(`<strong>Created Epics:</strong><ul style="margin-top: 6px; padding-left: 8px;">${epicItems}</ul>`, 'bot');
      }
    }
  };

  // Parse validated stories result into epicâ†’stories tree structure
  const parseValidatedStories = (result: any): { epicKey: string; epicSummary: string; stories: { key: string; summary: string; description: string }[] }[] => {
    if (Array.isArray(result)) {
      const hasEpics = result.some((item: any) => item.epic_key && item.user_stories);
      if (hasEpics) {
        return result.map((epic: any) => ({
          epicKey: epic.epic_key || 'ungrouped',
          epicSummary: epic.epic_summary || '',
          stories: (epic.user_stories || []).map((s: any) => ({
            key: s.key || s.id || 'unknown',
            summary: s.summary || '',
            description: s.description || (typeof s === 'string' ? s : JSON.stringify(s)),
          })),
        }));
      }
      return [{
        epicKey: 'stories',
        epicSummary: 'Validated User Stories',
        stories: result.map((s: any, idx: number) => ({
          key: s.key || s.id || `story-${idx + 1}`,
          summary: s.summary || s.title || '',
          description: s.description || (typeof s === 'string' ? s : JSON.stringify(s, null, 2)),
        })),
      }];
    }
    if (typeof result === 'object' && result !== null) {
      const epics: { epicKey: string; epicSummary: string; stories: { key: string; summary: string; description: string }[] }[] = [];
      for (const [key, value] of Object.entries(result)) {
        if (Array.isArray(value)) {
          epics.push({
            epicKey: key,
            epicSummary: key,
            stories: (value as any[]).map((s: any, idx: number) => ({
              key: s.key || s.id || `${key}-${idx + 1}`,
              summary: s.summary || s.title || '',
              description: s.description || (typeof s === 'string' ? s : JSON.stringify(s, null, 2)),
            })),
          });
        }
      }
      if (epics.length > 0) return epics;
      return [{
        epicKey: 'result',
        epicSummary: 'Validation Result',
        stories: [{
          key: 'result',
          summary: 'Validated Story',
          description: typeof result === 'string' ? result : JSON.stringify(result, null, 2),
        }],
      }];
    }
    return [{
      epicKey: 'result',
      epicSummary: 'Validation Result',
      stories: [{
        key: 'result',
        summary: 'Validated Story',
        description: String(result),
      }],
    }];
  };

  const openValidatedStoryEditModal = (storyKey: string, description: string) => {
    setEditingValidatedKey(storyKey);
    setEditingValidatedText(editedValidatedDescriptions[storyKey] ?? description);
    setValidatedStoryEditModalOpen(true);
  };

  const saveValidatedStoryEdit = () => {
    if (editingValidatedKey) {
      // Only mark as edited if the text actually changed from the original Jira description
      const originalStory = selectedJiraStories.find(s => s.key === editingValidatedKey);
      const originalDescription = originalStory?.description || '';
      if (editingValidatedText !== originalDescription) {
        setEditedValidatedDescriptions(prev => ({ ...prev, [editingValidatedKey]: editingValidatedText }));
      } else {
        // Remove from edited if user reverted back to original
        setEditedValidatedDescriptions(prev => {
          const next = { ...prev };
          delete next[editingValidatedKey!];
          return next;
        });
      }
    }
    setValidatedStoryEditModalOpen(false);
    setEditingValidatedKey(null);
  };

  // Helper to find validated description for a story key from the validate-userstories response
  const getValidatedDescriptionForKey = (storyKey: string): { summary: string; description: string } | null => {
    if (!validatedStories) return null;
    const parsed = parseValidatedStories(validatedStories);
    for (const epic of parsed) {
      const story = epic.stories.find(s => s.key === storyKey);
      if (story) return { summary: story.summary, description: story.description };
    }
    return null;
  };

  // Open comparison modal: left = validated response (formatted like chat), right = current Jira data
  const openComparisonModal = (storyKey: string) => {
    const jiraStory = selectedJiraStories.find(s => s.key === storyKey);
    if (!jiraStory) return;

    let htmlContent = '';

    console.log('openComparisonModal â€” storyKey:', storyKey, 'jiraDictionary:', jiraDictionary);

    // Show only the jira_dictionary value for this Jira ID (keys already contain hyphens, e.g. QUANTNIKAIDEMO-531)
    let validatedTitle = '';
    if (jiraDictionary && Object.keys(jiraDictionary).length > 0) {
      const dictValue = jiraDictionary[storyKey];
      if (dictValue) {
        if (typeof dictValue === 'object' && 'title' in (dictValue as Record<string, unknown>)) {
          validatedTitle = (dictValue as any).title || '';
          htmlContent = formatTextResponse((dictValue as any).story || '');
        } else {
          htmlContent = typeof dictValue === 'string' ? formatTextResponse(dictValue) : formatJsonResult(dictValue);
        }
      } else {
        htmlContent = '<span class="text-muted-foreground italic">No AI-validated story found for this Jira ID.</span>';
      }
    }
    setComparisonStoryKey(storyKey);
    setComparisonValidatedTitle(validatedTitle);
    setComparisonValidatedText(htmlContent);
    setComparisonJiraTitle(editedValidatedTitles[storyKey] ?? (jiraStory.summary || ''));
    setComparisonJiraDescription(editedValidatedDescriptions[storyKey] ?? (jiraStory.description || ''));
    setComparisonModalOpen(true);
  };

  // Save comparison modal edits (right section) into editedValidatedDescriptions / editedValidatedTitles
  const saveComparisonEdit = () => {
    if (comparisonStoryKey) {
      // Only mark as edited if the text actually changed from the original Jira description
      const originalStory = selectedJiraStories.find(s => s.key === comparisonStoryKey);
      const originalDescription = originalStory?.description || '';
      const originalTitle = originalStory?.summary || '';
      if (comparisonJiraDescription !== originalDescription) {
        setEditedValidatedDescriptions(prev => ({ ...prev, [comparisonStoryKey]: comparisonJiraDescription }));
      } else {
        // Remove from edited if user reverted back to original
        setEditedValidatedDescriptions(prev => {
          const next = { ...prev };
          delete next[comparisonStoryKey!];
          return next;
        });
      }
      if (comparisonJiraTitle !== originalTitle) {
        setEditedValidatedTitles(prev => ({ ...prev, [comparisonStoryKey]: comparisonJiraTitle }));
      } else {
        setEditedValidatedTitles(prev => {
          const next = { ...prev };
          delete next[comparisonStoryKey!];
          return next;
        });
      }
      // Un-discard if previously discarded
      setDiscardedExistingStories(prev => {
        if (!prev.has(comparisonStoryKey)) return prev;
        const next = new Set(prev);
        next.delete(comparisonStoryKey);
        return next;
      });
    }
    setComparisonModalOpen(false);
    setComparisonStoryKey(null);
  };

  // Discard an existing Jira story â€” mark as discarded locally (delete API called on Save)
  const handleDiscardExistingStory = (storyKey: string) => {
    setDiscardedExistingStories(prev => {
      const next = new Set(prev);
      next.add(storyKey);
      return next;
    });
    setComparisonModalOpen(false);
    setComparisonStoryKey(null);
  };

  // Open new story edit modal
  const openNewStoryEditModal = (compoundKey: string, storyText: string) => {
    setEditingNewStoryCompoundKey(compoundKey);
    setEditingNewStoryText(editedNewStoryTexts[compoundKey] ?? storyText);
    setNewStoryEditModalOpen(true);
  };

  // Save new story edit â€” save text and auto-check the checkbox
  const saveNewStoryEdit = () => {
    if (editingNewStoryCompoundKey) {
      setEditedNewStoryTexts(prev => ({ ...prev, [editingNewStoryCompoundKey]: editingNewStoryText }));
      setSelectedNewJiraStories(prev => {
        const next = new Set(prev);
        next.add(editingNewStoryCompoundKey);
        return next;
      });
    }
    setNewStoryEditModalOpen(false);
    setEditingNewStoryCompoundKey(null);
  };

  // Discard new story edit â€” close modal without checking checkbox
  const discardNewStoryEdit = () => {
    if (editingNewStoryCompoundKey) {
      setSelectedNewJiraStories(prev => {
        const next = new Set(prev);
        next.delete(editingNewStoryCompoundKey);
        return next;
      });
    }
    setNewStoryEditModalOpen(false);
    setEditingNewStoryCompoundKey(null);
  };

  const handleSaveValidatedUserStory = async () => {
    if (!validatedStories) return;

    setIsSavingValidatedStory(true);

    try {
      // Build update_stories: existing stories that were edited (title and/or description)
      const updateStories: { issue_key: string; summary: string; description: string }[] = [];
      if (selectedJiraStories.length > 0) {
        for (const story of selectedJiraStories) {
          if (discardedExistingStories.has(story.key)) continue;
          const titleEdited = editedValidatedTitles[story.key] !== undefined;
          const descEdited = editedValidatedDescriptions[story.key] !== undefined;
          if (!titleEdited && !descEdited) continue;
          const summary = editedValidatedTitles[story.key] ?? story.summary ?? story.key;
          const description = editedValidatedDescriptions[story.key] ?? story.description ?? '';
          updateStories.push({
            issue_key: story.key,
            summary: summary && summary.trim().length > 0 ? summary : story.key,
            description,
          });
        }
      }

      // Build create_stories: selected new Jira stories
      const createStories: { epic_issue_key: string; title: string; description: string; acceptance_criteria: { criterion: string }[] }[] = [];
      for (const [epicKey, stories] of Object.entries(newJiraCreateList)) {
        stories.forEach((storyItem, idx) => {
          const compoundKey = `${epicKey}-${idx}`;
          if (!selectedNewJiraStories.has(compoundKey)) return;
          const storyTitle = typeof storyItem === 'object' ? storyItem.title : (storyItem as string).split('\n')[0];
          const storyText = typeof storyItem === 'object' ? storyItem.story : storyItem as string;
          const finalText = editedNewStoryTexts[compoundKey] ?? storyText;
          const lines = finalText.split('\n');
          const acHeaderIndex = lines.findIndex(l => l.trim().toLowerCase().startsWith('acceptance criteria'));
          const description = acHeaderIndex >= 0
            ? lines.slice(0, acHeaderIndex).filter(l => l.trim()).join('\n')
            : finalText;
          const acceptanceCriteria = acHeaderIndex >= 0
            ? lines.slice(acHeaderIndex + 1)
                .map(l => l.trim().replace(/^-\s*/, ''))
                .filter(l => l.length > 0)
                .map(criterion => ({ criterion }))
            : [];
          createStories.push({
            epic_issue_key: epicKey,
            title: storyTitle,
            description,
            acceptance_criteria: acceptanceCriteria,
          });
        });
      }

      // Build delete_stories: discarded existing stories
      const deleteStories: { issue_key: string; delete_subtasks: boolean }[] = [];
      if (discardedExistingStories.size > 0) {
        for (const storyKey of Array.from(discardedExistingStories)) {
          deleteStories.push({ issue_key: storyKey, delete_subtasks: true });
        }
      }

      // Collect ALL epic keys BEFORE API calls (state may reset after)
      const epicKeysFromStories = selectedJiraStories.map(s => s.epicKey).filter(Boolean) as string[];
      const epicKeysFromNewStories = Object.keys(newJiraCreateList);
      const allEpicKeys = [...new Set([...epicKeysFromStories, ...epicKeysFromNewStories])];

      // Create a progress message that will be updated via SSE milestones
      messageIdCounter.current += 1;
      const progressMsgId = `save-progress-${Date.now()}-${messageIdCounter.current}`;
      setMessages(prev => [...prev, {
        id: progressMsgId,
        type: 'bot' as const,
        content: buildMilestoneHtml({
          type: 'milestone', stage: 'received', title: 'Saving',
          description: 'Connecting to orchestrator...', progress: 0.02,
          icon: '💾', timestamp: new Date().toISOString(),
        }),
      }]);

      // Build create_user_story_text from selected new stories in the required schema
      const createUserStoryTextPayload = createStories.map(s => ({
        epic_issue_key: s.epic_issue_key,
        title: s.title,
        description: s.description,
        acceptance_criteria: s.acceptance_criteria,
      }));

      // Call the existing chat stream with explicit intent and save data in context
      const data = await callChatStreamApi(
        'Save validated user stories',
        progressMsgId,
        {
          update_stories: updateStories,
          create_stories: createStories,
          delete_stories: deleteStories,
          ...(createUserStoryTextPayload.length > 0 ? { create_user_story_text: createUserStoryTextPayload } : {}),
        },
        undefined,
        'save_validated_user_stories',
      );

      // Remove the progress milestone message
      setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));

      const saveSuccess = data.status === 'success';
      const saveData = data.data?.action_results?.find(
        (r: any) => r.action === 'execute_save_validated_stories' && r.success
      )?.result || data.data || {};

      if (saveSuccess) {
        // Show success summary
        const summaryParts: string[] = [];
        const uc = saveData?.update_count ?? updateStories.length;
        const cc = saveData?.create_count ?? createStories.length;
        const dc = saveData?.delete_count ?? deleteStories.length;
        if (uc > 0) summaryParts.push(`Updated ${uc} user stories`);
        if (cc > 0) summaryParts.push(`Created ${cc} new stories`);
        if (dc > 0) summaryParts.push(`Deleted ${dc} stories`);
        const summaryText = summaryParts.length > 0 ? summaryParts.join(', ') : 'No changes to save';
        addMessage(`<strong>Save completed:</strong> ${summaryText}`, 'bot');

        // Show errors from individual operations if any
        if (saveData?.errors && saveData.errors.length > 0) {
          for (const err of saveData.errors) {
            addMessage(`<strong>Warning:</strong> ${escapeHtml(err)}`, 'error');
          }
        }

        setValidatedStories(null);
        setLastValidationPayload(null);
        setEditedValidatedDescriptions({});
        onJiraSelectionLock?.(false);
        setUserStoryTextLabel('User Story Text');
      } else {
        const errorMsg = data.message || 'An error occurred while saving validated user stories';
        addMessage(`<strong>Error:</strong> ${escapeHtml(errorMsg)}`, 'error');
      }

      // After saving, refresh Jira and auto-select ALL stories under the epics
      const anyActionTaken = updateStories.length > 0 || createStories.length > 0 || deleteStories.length > 0;
      if (anyActionTaken && allEpicKeys.length > 0) {
        const refreshIcon = `<span style="display: inline-flex; align-items: center; gap: 2px; vertical-align: middle; margin-right: 6px;">
          <span style="width: 6px; height: 6px; background-color: #3498B3; border-radius: 50%; display: inline-block; animation: thinkingPulse 1.4s ease-in-out infinite;"></span>
          <span style="width: 6px; height: 6px; background-color: #3498B3; border-radius: 50%; display: inline-block; animation: thinkingPulse 1.4s ease-in-out 0.2s infinite;"></span>
          <span style="width: 6px; height: 6px; background-color: #3498B3; border-radius: 50%; display: inline-block; animation: thinkingPulse 1.4s ease-in-out 0.4s infinite;"></span>
        </span>`;
        addMessage(`${refreshIcon} Refreshing Jira Stories...`, 'bot');
        try {
          await onValidatedUserStorySaved?.(allEpicKeys);
        } finally {
          setMessages(prev => prev.filter(msg => !msg.content.includes('Refreshing Jira Stories...')));
        }
      }

      // Set suggested actions from backend response, or fallback to default
      const backendSuggestions = data.suggested_actions && data.suggested_actions.length > 0
        ? data.suggested_actions
        : [{ action: 'Create Testcases for validated user stories', intent: 'generate_test_cases', orchestrator: 'test' }];
      setLastSuggestedActions(backendSuggestions);
      setNextSuggestedAction(backendSuggestions[0].action);

      // Reset new story selections
      setNewJiraCreateList({});
      setSelectedNewJiraStories(new Set());
      setEditedNewStoryTexts({});
      setDiscardedExistingStories(new Set());

      // Clear input fields and set next prompt text
      setCreateUserStoryText('');
      setCreateUserStoryBrowse(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setUserStoryTextLabel('User Story Text');
      setScenarioTypes('');
      setSelectedScenarioTypes([]);
      setIsAllScenarioTypesSelected(false);
      setTestScenarios('');
      setTestCaseFormat('');
      setTestCases('');
      setQueryInputText('');
      setNextagentflow('');
      setAwaitingTestCaseConfirm(true);
    } catch (error) {
      console.error('Error saving validated user stories:', error);
      let errorMessage: string;
      if (error instanceof DOMException && error.name === 'AbortError') {
        errorMessage = 'The server is taking longer than expected. Please try again.';
      } else {
        errorMessage = error instanceof Error ? error.message : 'Unknown error';
      }
      addMessage(`${escapeHtml(errorMessage)}`, 'error');
    } finally {
      setIsSavingValidatedStory(false);
    }
  };

  const downloadFileFromBase64 = (base64Content: string, filename: string = 'user_story.docx') => {
    try {
      console.log('Downloading file:', filename);
      console.log('Base64 content length:', base64Content?.length);
      
      // Remove data URL prefix if present
      const base64Data = base64Content.includes(',') 
        ? base64Content.split(',')[1] 
        : base64Content;
      
      // Convert base64 to binary
      const binaryString = window.atob(base64Data);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      
      // Create blob
      const blob = new Blob([bytes], { 
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' 
      });
      
      console.log('Blob created, size:', blob.size);
      
      // Create download link and trigger download
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      console.log('Download triggered successfully');
      addMessage(`ðŸ“¥ <strong>File downloaded:</strong> ${escapeHtml(filename)}`, 'bot');
    } catch (error) {
      console.error('Error downloading file:', error);
      addMessage(`${escapeHtml(error instanceof Error ? error.message : 'Unknown error')}`, 'error');
    }
  };


  // Handle BRD generation - calls /api/v1/generate-brd with multipart/form-data
  const handleBrdGeneration = async () => {
    setNextSuggestedAction('');
    setLastSuggestedActions([]);

    // Validation
    if (!projectName.trim() || !brdStakeholders[0]?.name.trim() || !brdStakeholders[0]?.email.trim() || brdFiles.length === 0) {
      addMessage('Please provide project name, product owner details, and at least one file.', 'error');
      return;
    }

    // Build user message display
    const userMessageParts: string[] = [];
    userMessageParts.push(`<strong>Generate BRD</strong>`);
    userMessageParts.push(`<strong>Project:</strong> ${escapeHtml(projectName.trim())}`);
    userMessageParts.push(`<strong>Files:</strong> ${brdFiles.map(f => '📎 ' + escapeHtml(f.name)).join(', ')}`);
    addMessage(userMessageParts.join('<br>'), 'user');

    // Capture files before clearing
    const filesToUpload = [...brdFiles];
    const projectNameToSend = projectName.trim();
    const stakeholdersToSend = brdStakeholders.filter(s => s.name.trim() && s.email.trim());

    // Clear BRD file inputs
    setBrdFiles([]);
    if (brdFileInputRef.current) brdFileInputRef.current.value = '';

    // Show loading
    setIsLoading(true);
    messageIdCounter.current += 1;
    const progressMsgId = `brd-progress-${Date.now()}-${messageIdCounter.current}`;
    const initialProgressHtml = `<div style="display: flex; flex-direction: column; gap: 6px; min-width: 220px;">
      <div style="display: flex; align-items: center; gap: 8px;">
        <span class="milestone-dots milestone-dots--active">
          <span class="milestone-dot" style="background:#22C55E;"></span>
          <span class="milestone-dot" style="background:#22C55E;"></span>
          <span class="milestone-dot" style="background:#22C55E;"></span>
        </span>
        <span style="font-weight: 600; font-size: 0.85rem; color: inherit;">Generating BRD...</span>
      </div>
      <div style="font-size: 0.75rem; opacity: 0.8;">Processing your files and creating BRD document...</div>
      <div style="position: relative; height: 6px; background: rgba(128,128,128,0.2); border-radius: 3px; overflow: hidden;">
        <div style="position: absolute; top: 0; left: 0; height: 100%; width: 10%; background: #3498B3; border-radius: 3px; transition: width 0.4s ease; animation: milestoneShimmer 1.5s ease-in-out infinite;"></div>
      </div>
    </div>`;
    setMessages(prev => [...prev, { id: progressMsgId, type: 'bot' as const, content: initialProgressHtml }]);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);

      const formData = new FormData();
      formData.append('project_name', projectNameToSend);

      // Add stakeholder fields
      stakeholdersToSend.forEach((stakeholder) => {
        formData.append('name', stakeholder.name.trim());
        formData.append('role', stakeholder.role.trim());
        formData.append('email', stakeholder.email.trim());
      });

      // Add files
      filesToUpload.forEach(file => formData.append('files', file, sanitizeFilename(file.name)));

      const response = await apiFetch(BRD_GENERATE_ENDPOINT, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Remove the progress message
      setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));

      const data = await response.json();

      // Handle "Confluence page already exists" — offer update flow instead of error
      if (response.ok && data.page_exists) {
        setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));
        const pageMsg = data.result || data.message || 'A Confluence page with this project name already exists.';
        addMessage(
          `<div style="display:flex;flex-direction:column;gap:8px;">` +
          `<div>⚠️ <strong>${escapeHtml(pageMsg)}</strong></div>` +
          `<div style="font-size:0.85rem;opacity:0.85;">You can either <strong>edit the Project Name</strong> above and regenerate, or switch to <strong>"Update BRD"</strong> to modify the existing document.</div>` +
          `</div>`,
          'bot'
        );
        setIsEditingProjectName(true);
        setIsLoading(false);
        return;
      }

      if (response.ok && (data.status === 'success' || data.brd_content_link)) {
        // Normalize to ChatResponsePayload and handle success
        const normalizedData: ChatResponsePayload = {
          session_id: sessionId!,
          message: data.message || 'BRD generated successfully',
          status: 'success',
          nextagentflow: data.nextagentflow || '',
          data: {
            child_response: data,
          },
          suggested_actions: data.suggested_actions || [],
          metadata: data.metadata,
        };
        handleChatSuccess(normalizedData);
      } else {
        const errorMsg = data.message || data.error || 'Failed to generate BRD';
        addMessage(`${escapeHtml(errorMsg)}`, 'error');
      }
    } catch (error: any) {
      // Remove the progress message
      setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));
      let errorMessage: string;
      if (error instanceof DOMException && error.name === 'AbortError') {
        errorMessage = 'The server is taking longer than expected. Please try again.';
      } else {
        errorMessage = error instanceof Error ? error.message : 'Unknown error';
      }
      addMessage(`<strong>We couldn’t complete this request through the gateway.</strong> ${escapeHtml(errorMessage)} <em>Retry request.</em>`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle BRD Update - calls planning orchestrator /api/v1/update-brd with multipart/form-data
  const handleBrdUpdate = async () => {
    setNextSuggestedAction('');
    setLastSuggestedActions([]);

    // Validation
    if (!finalBrdConfluenceLink.trim()) {
      addMessage('Please enter a BRD Confluence page link.', 'error');
      return;
    }
    if (brdUpdateMode === 'chat' && !brdUpdateInstructions.trim()) {
      addMessage('Please describe the changes you want to make.', 'error');
      return;
    }
    if (brdUpdateMode === 'upload' && brdFiles.length === 0) {
      addMessage('Please upload at least one document with the updates.', 'error');
      return;
    }

    // Build user message display
    const userMessageParts: string[] = [];
    if (finalBrdConfluenceLink.trim()) userMessageParts.push(`<strong>BRD Page:</strong> ${escapeHtml(finalBrdConfluenceLink.trim())}`);
    if (brdUpdateMode === 'chat' && brdUpdateInstructions.trim()) userMessageParts.push(`<strong>Update via:</strong> Chat`);
    if (brdUpdateMode === 'upload' && brdFiles.length > 0) userMessageParts.push(`<strong>Update via:</strong> Document upload — ${brdFiles.map(f => '📎 ' + escapeHtml(f.name)).join(', ')}`);
    addMessage(userMessageParts.join('<br>'), 'user');

    // Capture inputs before clearing
    const trimmedQueryInputText = brdUpdateInstructions.trim();
    const filesToUpload = [...brdFiles];
    const trimmedBrdUri = brdUri.trim() || finalBrdConfluenceLink.trim();

    // Clear inputs
    setBrdUpdateInstructions('');
    setBrdFiles([]);
    if (brdFileInputRef.current) brdFileInputRef.current.value = '';

    // Show loading
    setIsLoading(true);
    messageIdCounter.current += 1;
    const progressMsgId = `brd-update-progress-${Date.now()}-${messageIdCounter.current}`;
    const initialProgressHtml = `<div style="display: flex; flex-direction: column; gap: 6px; min-width: 220px;">
      <div style="display: flex; align-items: center; gap: 8px;">
        <span class="milestone-dots milestone-dots--active">
          <span class="milestone-dot" style="background:#22C55E;"></span>
          <span class="milestone-dot" style="background:#22C55E;"></span>
          <span class="milestone-dot" style="background:#22C55E;"></span>
        </span>
        <span style="font-weight: 600; font-size: 0.85rem; color: inherit;">Updating BRD...</span>
      </div>
      <div style="font-size: 0.75rem; opacity: 0.8;">Processing your request and updating BRD document...</div>
      <div style="position: relative; height: 6px; background: rgba(128,128,128,0.2); border-radius: 3px; overflow: hidden;">
        <div style="position: absolute; top: 0; left: 0; height: 100%; width: 10%; background: #3498B3; border-radius: 3px; transition: width 0.4s ease; animation: milestoneShimmer 1.5s ease-in-out infinite;"></div>
      </div>
    </div>`;
    setMessages(prev => [...prev, { id: progressMsgId, type: 'bot' as const, content: initialProgressHtml }]);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);

      const formData = new FormData();
      formData.append('query_text', trimmedQueryInputText || 'Update Existing BRD');
      formData.append('nextagentflow', 'confirmedUpdateBrd');
      if (trimmedBrdUri) formData.append('brd_document_uri', trimmedBrdUri);
      if (brdUpdateMode) formData.append('update_mode', brdUpdateMode);

      // Add stakeholder fields
      const filledStakeholders = brdStakeholders.filter(s => s.name.trim() && s.email.trim());
      const allNames = filledStakeholders.map(s => s.name.trim());
      const allRoles = filledStakeholders.map(s => s.role.trim());
      const allEmails = filledStakeholders.map(s => s.email.trim());
      if (projectName.trim()) formData.append('project_name', projectName.trim());
      if (allNames.length > 0) formData.append('brd_name', allNames.join(', '));
      if (allRoles.length > 0) formData.append('brd_role', allRoles.join(', '));
      if (allEmails.length > 0) formData.append('brd_email', allEmails.join(', '));
      if (allNames.length > 0) formData.append('name', JSON.stringify(allNames));
      if (allRoles.length > 0) formData.append('role', JSON.stringify(allRoles));
      if (allEmails.length > 0) formData.append('email', JSON.stringify(allEmails));

      // Include files if present (upload mode)
      filesToUpload.forEach((file, index) => {
        formData.append(`file_${index}`, file, sanitizeFilename(file.name));
      });
      filesToUpload.forEach((file) => {
        formData.append('files', file, sanitizeFilename(file.name));
      });

      const response = await apiFetch(BRD_UPDATE_ENDPOINT, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Remove the progress message
      setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));

      const data = await response.json();

      if (response.ok && data.success) {
        // Extract fields from response
        const projectNameFromApi = data.project_name;
        if (projectNameFromApi && !isProjectNameOverriddenRef.current) {
          setProjectName(projectNameFromApi);
          sessionStorage.setItem('projectName', projectNameFromApi);
        }

        // Reset nextagentflow to hide fields
        setNextagentflow('');
        setBrdFiles([]);
        setBrdFlowChoice(null);
        setBrdUpdateMode(null);
        setBrdUpdateInstructions('');
        if (brdFileInputRef.current) brdFileInputRef.current.value = '';

        // Set BRD confluence link if available
        if (data['brd_content_link'] && data['brd_content_link'].trim()) {
          const brdLink = data['brd_content_link'].trim();
          setFinalBrdConfluenceLink(brdLink);
          sessionStorage.setItem('brdConfluenceLink', brdLink);
          sessionStorage.setItem('brdDocumentName', projectName || projectNameFromApi || '');
          onBrdGenerated?.(brdLink, projectName || projectNameFromApi || '');
        }

        // Display success result
        const messageText = data['message'] ? cleanBotResponseText(data['message']) : '';
        const brdLink = data['brd_content_link']?.trim() || finalBrdConfluenceLink.trim();
        const brdName = projectName || projectNameFromApi || '';
        let combinedMsg = '';
        if (messageText) combinedMsg += formatTextResponse(messageText);
        // Show updated sections summary and link
        const sectionsUpdated = data['sections_updated'] || [];
        if (sectionsUpdated.length > 0) {
          combinedMsg += `<br><br><strong>Sections Updated:</strong> ${sectionsUpdated.map((s: string) => escapeHtml(s)).join(', ')}`;
        }
        if (brdLink) {
          combinedMsg += `<br><strong>Updated BRD:</strong> <a href="${escapeHtml(brdLink)}" target="_blank" rel="noopener noreferrer" style="color: #3498B3; text-decoration: underline;">${escapeHtml(brdName || 'View on Confluence')}</a>`;
        }
        if (combinedMsg) addMessage(combinedMsg, 'bot');
      } else {
        const errorMsg = data.message || data.error || 'An error occurred during BRD update';
        addMessage(`${escapeHtml(errorMsg)}`, 'error');
      }
    } catch (error: any) {
      // Remove the progress message
      setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));
      let errorMessage: string;
      if (error instanceof DOMException && error.name === 'AbortError') {
        errorMessage = 'The server is taking longer than expected. Please try again.';
      } else {
        errorMessage = error instanceof Error ? error.message : 'Unknown error';
      }
      addMessage(`${escapeHtml(errorMessage)}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle User Story Update via orchestrator streaming API.
  // Sends BRD link + selected Jira epic keys so the backend can run the
  // analyze -> apply brownfield flow.
  const handleUserStoryUpdate = async () => {
    setNextSuggestedAction('');
    setLastSuggestedActions([]);
    if (!sessionId) return;

    if (!finalBrdConfluenceLink.trim()) {
      addMessage('Please enter a BRD Confluence page link.', 'error');
      return;
    }

    if (selectedJiraStories.length === 0) {
      addMessage('Please select user stories from the Jira panel.', 'error');
      return;
    }

    const selectedEpicKeys = buildSelectedEpicKeys();
    if (selectedEpicKeys.length === 0) {
      addMessage('Please select Jira stories that belong to one or more epics.', 'error');
      return;
    }

    const trimmedBrdUri = finalBrdConfluenceLink.trim();
    const userMessageParts: string[] = [];
    userMessageParts.push(`<strong>BRD Page:</strong> ${escapeHtml(trimmedBrdUri)}`);
    userMessageParts.push(`<strong>Jira Epics:</strong> ${selectedEpicKeys.map(key => escapeHtml(key)).join(', ')}`);
    userMessageParts.push(`<strong>Jira Stories:</strong> ${selectedJiraStories.map(story => escapeHtml(story.key)).join(', ')}`);
    addMessage(userMessageParts.join('<br>'), 'user');

    setIsLoading(true);
    messageIdCounter.current += 1;
    const progressMsgId = `userstory-update-progress-${Date.now()}-${messageIdCounter.current}`;
    const initialProgressHtml = `<div style="display: flex; flex-direction: column; gap: 6px; min-width: 220px;">
      <div style="display: flex; align-items: center; gap: 8px;">
        <span class="milestone-dots milestone-dots--active">
          <span class="milestone-dot" style="background:#22C55E;"></span>
          <span class="milestone-dot" style="background:#22C55E;"></span>
          <span class="milestone-dot" style="background:#22C55E;"></span>
        </span>
        <span style="font-weight: 600; font-size: 0.85rem; color: inherit;">Updating User Stories...</span>
      </div>
      <div style="font-size: 0.75rem; opacity: 0.8;">Comparing the updated BRD against selected Jira epics and applying the changes...</div>
      <div style="position: relative; height: 6px; background: rgba(128,128,128,0.2); border-radius: 3px; overflow: hidden;">
        <div style="position: absolute; top: 0; left: 0; height: 100%; width: 10%; background: #3498B3; border-radius: 3px; transition: width 0.4s ease; animation: milestoneShimmer 1.5s ease-in-out infinite;"></div>
      </div>
    </div>`;
    setMessages(prev => [...prev, { id: progressMsgId, type: 'bot' as const, content: initialProgressHtml }]);

    try {
      const data = await callChatStreamApi(
        'Update existing user stories based on the updated BRD',
        progressMsgId,
        {
          brd_confluence_link: trimmedBrdUri,
          jira_epic_keys: selectedEpicKeys,
        },
        undefined,
        'update_user_story',
      );


      setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));

      if (data.status === 'success') {
        setUserStoryFlowChoice(null);
        handleChatSuccess(data);
      } else {
        addMessage(`${escapeHtml(data.message || 'Failed to update user stories')}`, 'error');
      }
    } catch (error: any) {
      setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));
      let errorMessage = 'Failed to update user stories';
      if (error?.name === 'AbortError') {
        errorMessage = 'The server is taking longer than expected. Please try again.';
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      addMessage(`${escapeHtml(errorMessage)}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnalyze = async () => {
    setNextSuggestedAction('');
    setLastSuggestedActions([]);
    const trimmedQueryInputText = queryInputText.trim();

    // --- Handle confirmation for suggested next actions ---
    const isAffirmative = /^(yes|y|yeah|yep|sure|ok|okay|confirm|go ahead|proceed|do it|please)$/i.test(trimmedQueryInputText);

    if (awaitingTestCaseConfirm && isAffirmative) {
      setAwaitingTestCaseConfirm(false);
      addMessage(escapeHtml(trimmedQueryInputText), 'user');
      setQueryInputText('');

      // Set the agent flow so context fields are included
      setNextagentflow('confirmedUserStoryToTestScenario');

      // Build context with currently selected Jira stories & BRD link
      const confirmContext: Record<string, any> = {};
      if (finalBrdConfluenceLink.trim()) confirmContext.brd_link = finalBrdConfluenceLink.trim();
      if (projectName.trim()) confirmContext.project_name = projectName.trim();
      if (selectedJiraStories.length > 0) {
        confirmContext.create_user_story_text = buildEpicStoriesPayload();
      }

      // Show progress
      setIsLoading(true);
      messageIdCounter.current += 1;
      const progressMsgId = `confirm-tc-progress-${Date.now()}-${messageIdCounter.current}`;
      setMessages(prev => [...prev, {
        id: progressMsgId, type: 'bot' as const,
        content: buildMilestoneHtml({
          type: 'milestone', stage: 'received', title: 'Processing',
          description: 'Setting up test case generation...', progress: 0.05,
          icon: '🧪', timestamp: new Date().toISOString(),
        }),
      }]);

      try {
        let data: ChatResponsePayload;
        try {
          data = await callChatStreamApi(
            'Generate test scenarios for the user stories',
            progressMsgId,
            confirmContext,
            undefined,
            'generate_test_cases',
          );
        } catch (firstError: any) {
          if (firstError instanceof DOMException && firstError.name === 'AbortError') {
            setMessages(prev => prev.map(msg =>
              msg.id === progressMsgId ? { ...msg, content: `<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;font-size:0.85rem;color:inherit;opacity:0.9;">
                <span style="display:inline-flex;align-items:center;gap:2px;">
                  <span style="width:6px;height:6px;background:#f59e0b;border-radius:50%;animation:thinkingPulse 1.4s ease-in-out infinite;"></span>
                  <span style="width:6px;height:6px;background:#f59e0b;border-radius:50%;animation:thinkingPulse 1.4s ease-in-out 0.2s infinite;"></span>
                  <span style="width:6px;height:6px;background:#f59e0b;border-radius:50%;animation:thinkingPulse 1.4s ease-in-out 0.4s infinite;"></span>
                </span>
                <span>Connection timed out — retrying automatically...</span>
              </div>` } : msg
            ));
            data = await callChatStreamApi(
              'Generate test scenarios for the user stories',
              progressMsgId,
              confirmContext,
              undefined,
              'generate_test_cases',
            );
          } else {
            throw firstError;
          }
        }
        setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));

        if (data.status === 'success') {
          handleChatSuccess(data);
        } else {
          addMessage(`${escapeHtml(data.message || 'An error occurred')}`, 'error');
        }
      } catch (error: any) {
        setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));
        const errorMessage = error instanceof DOMException && error.name === 'AbortError'
          ? 'The server is taking longer than expected. Please try again.' : (error instanceof Error ? error.message : 'Unknown error');
        addMessage(`${escapeHtml(errorMessage)}`, 'error');
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // If user typed "no" to a confirmation prompt, just clear the awaiting state
    if (awaitingTestCaseConfirm && /^(no|nah|nope|skip|cancel|not now)$/i.test(trimmedQueryInputText)) {
      setAwaitingTestCaseConfirm(false);
    }

    // --- Intercept code assistant trigger: show project config inside chat ---
    if (trimmedQueryInputText && !nextagentflow && !codeAssistantActive && isCodeAssistantTrigger(trimmedQueryInputText)) {
      addMessage(escapeHtml(trimmedQueryInputText), 'user');
      setQueryInputText('');
      setCodeAssistantActive(true);
      droidSessionClosedRef.current = false;
      setNextagentflow('confirmedCodeAssistant');
      fetchCodeAssistantModels();
      addMessage(
        '<div style="margin-bottom:4px;"><strong style="color:#3498B3;">Code Assistant — Project Configuration</strong></div>' +
        '<div style="font-size:0.8rem;opacity:0.85;">Configure the repository workspace below, then click <strong>Proceed</strong> to start the code generation session.</div>',
        'bot'
      );
      return;
    }

    // --- If code assistant is locked, route message through orchestrator as code_assistant intent ---
    if (codeAssistantActive && codeAssistantLocked && trimmedQueryInputText) {
      // Pass through to orchestrator with code_assistant explicit intent
      // (falls through to normal handleAnalyze flow below)
    }

    // Special validation for User Manual agent: only needs project name + source URL
    // (source URL accepts a SharePoint folder URL or a Confluence page URL).
    if (nextagentflow === 'confirmedCreateUserManual') {
      if (!projectName.trim()) {
        addMessage('Please enter a project name.', 'error');
        return;
      }
      if (!sharepointUrl.trim()) {
        addMessage('Please enter a Source URL (SharePoint folder or Confluence page).', 'error');
        return;
      }
    } else {
      // Basic validation: need either text, files, or flow-specific inputs
      const hasFlowInput = createUserStoryText.trim() || selectedJiraStories.length > 0 || finalBrdConfluenceLink.trim() || selectedTestCasesFromJira.length > 0;
      if (!trimmedQueryInputText && brdFiles.length === 0 && !hasFlowInput) {
        addMessage('Please type a message or provide required inputs.', 'error');
        return;
      }
    }

    // Build user message display — only show context fields when an agent flow is active
    const userMessageParts: string[] = [];
    if (nextagentflow === 'confirmedCreateUserManual') {
      userMessageParts.push(`<strong>Generate User Manual</strong>`);
      userMessageParts.push(`<strong>Project:</strong> ${escapeHtml(projectName.trim())}`);
      userMessageParts.push(`<strong>Source URL:</strong> ${escapeHtml(sharepointUrl.trim())}`);
    } else {
    if (trimmedQueryInputText) userMessageParts.push(escapeHtml(trimmedQueryInputText));
    if (nextagentflow && nextagentflow !== 'confirmedCodeAssistant') {
      if (brdFiles.length > 0) userMessageParts.push(`<strong>Files:</strong> ${brdFiles.map(f => 'ðŸ“Ž ' + escapeHtml(f.name)).join(', ')}`);
      if (projectName.trim()) userMessageParts.push(`<strong>Project:</strong> ${escapeHtml(projectName.trim())}`);
      if (selectedConfluencePageUrl?.trim()) userMessageParts.push(`<strong>BRD Link:</strong> ${escapeHtml(finalBrdConfluenceLink.trim())}`);
      if (selectedJiraStories.length > 0) userMessageParts.push(`<strong>Jira Stories:</strong> ${selectedJiraStories.map(s => escapeHtml(s.key)).join(', ')}`);
      if (selectedTestCasesFromJira.length > 0) userMessageParts.push(`<strong>Test Cases:</strong> ${selectedTestCasesFromJira.map(tc => escapeHtml(tc.key)).join(', ')}`);
      if (frameworkType.trim()) userMessageParts.push(`<strong>Framework:</strong> ${escapeHtml(frameworkType.trim())}`);
      if (language.trim()) userMessageParts.push(`<strong>Language:</strong> ${escapeHtml(language.trim())}`);
      if (scriptGenerationType.trim()) userMessageParts.push(`<strong>Generation Type:</strong> ${escapeHtml(scriptGenerationType.trim())}`);
      if (nextagentflow === 'confirmedTestDataGenerator') userMessageParts.push(`<strong>Output Format:</strong> ${escapeHtml(testDataOutputFormat)}`);
      if (scenarioTypes.trim()) userMessageParts.push(`<strong>Scenario Types:</strong> ${escapeHtml(scenarioTypes.trim())}`);
    }
    }

    // Remove any existing error messages from the chat
    setMessages(prev => prev.filter(msg => msg.type !== 'error'));

    addMessage(userMessageParts.join('<br><br>'), 'user');

    // User Manual now flows through the standard chat/streaming pipeline
    // (orchestrator intent=create_user_manual). We just need to clear the
    // source URL field after the message is captured.
    if (nextagentflow === 'confirmedCreateUserManual') {
      setSharepointUrl('');
    }

    // Capture values before clearing; use last sent message as fallback for flow-specific Proceed buttons
    const messageText = trimmedQueryInputText || lastSentMessage || 'Process request';
    // Store for next request's fallback
    setLastSentMessage(messageText);
    const filesToUpload = [...brdFiles];

    // Clear all input fields
    setQueryInputText('');
    setCreateUserStoryText('');
    setCreateUserStoryBrowse(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    setInputTestTextE2E('');
    setInstructionsE2E('');
    setUserStoryNameE2E('');
    setScenarioTypes('');
    setSelectedScenarioTypes([]);
    setIsAllScenarioTypesSelected(false);
    setTestScenarios('');
    setTestCaseFormat('');
    setTestCases('');
    setFrameworkType('');
    setLanguage('');
    setScriptGenerationType('');
    setBrdFiles([]);
    if (brdFileInputRef.current) brdFileInputRef.current.value = '';
    setSelectedTcKey('');
    setSelectedTcSummary('');
    setSelectedTcDescription('');
    setUserStoryUri('');
    setBrdUri('');

    // Show loading - create a progress message with a known ID for streaming updates
    setIsLoading(true);
    setIsExecutingMode(false);
    messageIdCounter.current += 1;
    const progressMsgId = `stream-progress-${Date.now()}-${messageIdCounter.current}`;
    const initialProgressHtml = `<div style="display: flex; flex-direction: column; gap: 6px; min-width: 220px;">
      <div style="display: flex; align-items: center; gap: 8px;">
        <span class="milestone-dots milestone-dots--active">
          <span class="milestone-dot" style="background:#22C55E;"></span>
          <span class="milestone-dot" style="background:#22C55E;"></span>
          <span class="milestone-dot" style="background:#22C55E;"></span>
        </span>
        <span style="font-weight: 600; font-size: 0.85rem; color: inherit;">Connecting secure stream…</span>
      </div>
      <div style="font-size: 0.75rem; opacity: 0.8;">Sending your request through the API gateway…</div>
      <div style="position: relative; height: 6px; background: rgba(128,128,128,0.2); border-radius: 3px; overflow: hidden;">
        <div style="position: absolute; top: 0; left: 0; height: 100%; width: 2%; background: #3498B3; border-radius: 3px; transition: width 0.4s ease; animation: milestoneShimmer 1.5s ease-in-out infinite;"></div>
      </div>
      <div style="font-size: 0.7rem; opacity: 0.6; text-align: right;">2%</div>
    </div>`;
    setMessages(prev => [...prev, { id: progressMsgId, type: 'bot' as const, content: initialProgressHtml }]);

    // Derive explicit intent from current agent flow
    const nextagentflowToIntent: Record<string, string> = {
      confirmedCreateBrd: 'create_brd',
      confirmedCreateUserStory: 'create_user_story',
      confirmedValidateUserStory: 'validate_user_story',
      intentOfUpdateUserStory: 'save_validated_user_stories',
      confirmedUserStoryToTestScenario: 'generate_test_cases',
      confirmedTestCaseToTestScript: 'generate_test_script',
      confirmedTestDataGenerator: 'generate_test_data',
      confirmedBrdSummary: 'brd_summary',
      confirmedCreateUserManual: 'create_user_manual',
      confirmedCodeAssistant: 'code_assistant',
      // Quantnik Brain: explicit intent so the orchestrator skips the
      // "Is that correct? Yes/No" confirmation step.
      confirmedQueryKnowledgeBase: 'context_enrich_query',
    };
    // Use nextagentflow if set; fall back to the parent-selected flow so follow-up
    // messages in Brain panel also carry the explicit intent (avoids re-classification).
    const effectiveFlow = nextagentflow || selectedNextagentflow || '';
    const currentExplicitIntent = nextagentflowToIntent[effectiveFlow] || undefined;

    // Clear and prepare droid terminal for new code assistant session
    if (currentExplicitIntent === 'code_assistant') {
      // On follow-up messages, keep existing terminal events (append mode)
      // Only clear on the very first message of a session
      if (droidTerminalEvents.length === 0) {
        setDroidTerminalEvents([]);
      }
      setDroidTerminalVisible(true);
      setDroidTerminalActive(true);
    }

    try {
      let data: ChatResponsePayload;
      try {
        // Brain panel: direct RAG call (no orchestrator/integration hops)
        if (currentExplicitIntent === 'context_enrich_query' && !filesToUpload.length) {
          data = await callBrainQueryDirect(messageText, progressMsgId);
        } else {
          data = await callChatStreamApi(
            messageText,
            progressMsgId,
            undefined,
            filesToUpload.length > 0 ? filesToUpload : undefined,
            currentExplicitIntent,
          );
        }
      } catch (firstError: any) {
        // Auto-retry once on timeout (handles Cloud Run cold starts / transient delays)
        if (firstError instanceof DOMException && firstError.name === 'AbortError') {
          setMessages(prev => prev.map(msg =>
            msg.id === progressMsgId ? { ...msg, content: `<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;font-size:0.85rem;color:inherit;opacity:0.9;">
              <span style="display:inline-flex;align-items:center;gap:2px;">
                <span style="width:6px;height:6px;background:#f59e0b;border-radius:50%;animation:thinkingPulse 1.4s ease-in-out infinite;"></span>
                <span style="width:6px;height:6px;background:#f59e0b;border-radius:50%;animation:thinkingPulse 1.4s ease-in-out 0.2s infinite;"></span>
                <span style="width:6px;height:6px;background:#f59e0b;border-radius:50%;animation:thinkingPulse 1.4s ease-in-out 0.4s infinite;"></span>
              </span>
              <span>Connection timed out — retrying automatically...</span>
            </div>` } : msg
          ));
          if (currentExplicitIntent === 'context_enrich_query' && !filesToUpload.length) {
            data = await callBrainQueryDirect(messageText, progressMsgId);
          } else {
            data = await callChatStreamApi(
              messageText,
              progressMsgId,
              undefined,
              filesToUpload.length > 0 ? filesToUpload : undefined,
              currentExplicitIntent,
            );
          }
        } else {
          throw firstError;
        }
      }

      // Remove the progress message
      setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));

      if (data.status === 'success') {
        handleChatSuccess(data);
      } else {
        const errorMsg = data.message || 'An error occurred';
        addMessage(`${escapeHtml(errorMsg)}`, 'error');
      }
    } catch (error: any) {
      // Remove the progress message
      setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));
      let errorMessage: string;
      if (error instanceof DOMException && error.name === 'AbortError') {
        errorMessage = 'The server is taking longer than expected. Please try sending your message again.';
      } else {
        errorMessage = error instanceof Error ? error.message : 'Unknown error';
      }
      addMessage(`<strong>We couldn’t complete this request through the gateway.</strong> ${escapeHtml(errorMessage)} <em>Retry request.</em>`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = () => {
    setQueryInputText('');
    setCreateUserStoryText('');
    setCreateUserStoryBrowse(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    setInputTestTextE2E('');
    setInstructionsE2E('');
    setUserStoryNameE2E('');
    setScenarioTypes('');
    setTestScenarios('');
    setTestCaseFormat('');
    setTestCases('');
    setTestCaseStoryDropdownOpen(false);
    setSelectedTestCaseKeys(new Set());
    setGeneratedTestCasesList([]);
    setFrameworkType('');
    setLanguage('');
    setScriptGenerationType('');
    setNextagentflow('');

    setUserStoryUri('');
    setBrdUri('');
    // Clear all sessionStorage variables
    sessionStorage.removeItem('brdConfluenceLink');
    sessionStorage.removeItem('brdDocumentName');
    sessionStorage.removeItem('projectName');
    setFinalBrdConfluenceLink('');

    // Reset BRD file uploads only (projectName and stakeholders are managed by admin team)
    isProjectNameOverriddenRef.current = false;
    setIsEditingProjectName(false);
    setActiveRoleDropdown(null);
    setBrdFiles([]);
    setBrdFlowChoice(null);
    setBrdUpdateMode(null);
    setBrdUpdateInstructions('');
    setUserStoryFlowChoice(null);
    if (brdFileInputRef.current) {
      brdFileInputRef.current.value = '';
    }

    // Reset validated stories state
    setValidatedStories(null);
    setLastValidationPayload(null);
    setEditedValidatedDescriptions({});
    setValidatedStoryEditModalOpen(false);
    setEditingValidatedKey(null);
    setNewJiraCreateList({});
    setSelectedNewJiraStories(new Set());
    // Reset user story text label
    setUserStoryTextLabel('User Story Text');

    // Unlock Jira panel selection
    onJiraSelectionLock?.(false);

    // Clear Jira & Confluence selections in left sidebar
    onClearSelections?.();

    // Reset code assistant state
    setCodeAssistantActive(false);
    setCodeAssistantLocked(false);
    setCodeAssistantLockInfo(null);
    setCaFolderName('');
    setCaFolderMode('new');
    setCaLockMode('new');
    setCaBranchName('');
    setCaOverwriteConfirm(false);
    // Reset repo config — re-apply backend defaults if available
    setCaGitToken('');
    setCaGitUsername('git');
    setCaRepoRemoteUrl(harnessToolConfig?.config?.url ? buildHarnessRepoUrl(harnessToolConfig.config) : '');

    // Reset droid terminal
    setDroidTerminalEvents([]);
    setDroidTerminalVisible(false);
    setDroidTerminalActive(false);

  };

  // Lighter reset for prompt library switches â€” clears chatbot fields but preserves Confluence selection
  const handleClearForPromptSwitch = () => {
    setQueryInputText('');
    setCreateUserStoryText('');
    setCreateUserStoryBrowse(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    setInputTestTextE2E('');
    setInstructionsE2E('');
    setUserStoryNameE2E('');
    setScenarioTypes('');
    setTestScenarios('');
    setTestCaseFormat('');
    setTestCases('');
    setTestCaseStoryDropdownOpen(false);
    setSelectedTestCaseKeys(new Set());
    setGeneratedTestCasesList([]);
    setFrameworkType('');
    setLanguage('');
    setScriptGenerationType('');
    setNextagentflow('');
    setUserStoryUri('');
    setBrdUri('');
    setActiveRoleDropdown(null);
    setBrdFiles([]);
    setBrdFlowChoice(null);
    setBrdUpdateMode(null);
    setBrdUpdateInstructions('');
    setUserStoryFlowChoice(null);
    if (brdFileInputRef.current) {
      brdFileInputRef.current.value = '';
    }
    setValidatedStories(null);
    setLastValidationPayload(null);
    setEditedValidatedDescriptions({});
    setValidatedStoryEditModalOpen(false);
    setEditingValidatedKey(null);
    setNewJiraCreateList({});
    setSelectedNewJiraStories(new Set());
    setUserStoryTextLabel('User Story Text');
    setNextSuggestedAction('');
    setLastSuggestedActions([]);
    setSelectedScenarioTypes([]);
    setIsAllScenarioTypesSelected(false);
    onJiraSelectionLock?.(false);
    // Reset code assistant state on prompt switch
    setCodeAssistantActive(false);
    setCodeAssistantLocked(false);
    setCodeAssistantLockInfo(null);
    setCaFolderName('');
    setCaFolderMode('new');
    setCaLockMode('new');
    setCaBranchName('');
    setCaOverwriteConfirm(false);
    // Close droid terminal on prompt switch
    setDroidTerminalVisible(false);
    setDroidTerminalActive(false);
    setDroidTerminalEvents([]);
    // NOTE: Does NOT call onClearSelections â€” preserves Confluence & Jira selections
  };

  const triggerContextFabricProceed = async ({ url, files, projectName: overrideProjectName }: { url?: string; files?: File[]; projectName?: string }) => {
    const trimmedUrl = url?.trim() || '';
    const filesToUpload = files || [];

    if (!trimmedUrl && filesToUpload.length === 0) {
      addMessage('Please provide a URL or at least one file for Context Fabric.', 'error');
      throw new Error('Please provide a URL or at least one file.');
    }

    const effectiveProjectName = (overrideProjectName || projectName || '').trim();

    if (!effectiveProjectName) {
      addMessage('❌ <strong>Project name is required.</strong> Please configure your project name in Manage Project Team or Project Settings before proceeding.', 'error');
      throw new Error('Project name is required. Please configure it in Manage Project Team or Project Settings.');
    }

    console.log('[triggerContextFabricProceed] overrideProjectName:', overrideProjectName, '| projectName:', projectName, '| effectiveProjectName:', effectiveProjectName);

    const isUploadFlow = filesToUpload.length > 0;
    const explicitIntent = isUploadFlow ? 'context_enrich_upload' : 'context_enrich_ingest';
    const extraContext: Record<string, any> = {
      project_name: effectiveProjectName,
      ...(isUploadFlow ? {} : { source: 'website', urls: [trimmedUrl] }),
    };

    const messageText = isUploadFlow
      ? `Upload ${filesToUpload.length} file(s) to Context Fabric.`
      : `Ingest website content from ${trimmedUrl}`;

    const displayParts: string[] = [
      `<strong>Context Fabric:</strong> ${isUploadFlow ? 'Document Upload' : 'Web Ingest'}`,
    ];
    if (trimmedUrl) {
      displayParts.push(`<strong>URL:</strong> ${escapeHtml(trimmedUrl)}`);
    }
    if (filesToUpload.length > 0) {
      displayParts.push(`<strong>Files:</strong> ${filesToUpload.map(f => '📎 ' + escapeHtml(f.name)).join(', ')}`);
    }
    addMessage(displayParts.join('<br><br>'), 'user');

    setIsLoading(true);
    setIsExecutingMode(false);
    messageIdCounter.current += 1;
    const progressMsgId = `stream-progress-${Date.now()}-${messageIdCounter.current}`;
    const initialProgressHtml = `<div style="display: flex; flex-direction: column; gap: 6px; min-width: 220px;">
      <div style="display: flex; align-items: center; gap: 8px;">
        <span class="milestone-dots milestone-dots--active">
          <span class="milestone-dot" style="background:#22C55E;"></span>
          <span class="milestone-dot" style="background:#22C55E;"></span>
          <span class="milestone-dot" style="background:#22C55E;"></span>
        </span>
        <span style="font-weight: 600; font-size: 0.85rem; color: inherit;">Connecting...</span>
      </div>
      <div style="font-size: 0.75rem; opacity: 0.8;">Sending your request to the orchestrator...</div>
      <div style="position: relative; height: 6px; background: rgba(128,128,128,0.2); border-radius: 3px; overflow: hidden;">
        <div style="position: absolute; top: 0; left: 0; height: 100%; width: 2%; background: #3498B3; border-radius: 3px; transition: width 0.4s ease; animation: milestoneShimmer 1.5s ease-in-out infinite;"></div>
      </div>
      <div style="font-size: 0.7rem; opacity: 0.6; text-align: right;">2%</div>
    </div>`;
    setMessages(prev => [...prev, { id: progressMsgId, type: 'bot' as const, content: initialProgressHtml }]);

    try {
      const data = await callChatStreamApi(
        messageText,
        progressMsgId,
        extraContext,
        isUploadFlow ? filesToUpload : undefined,
        explicitIntent,
      );

      setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));

      if (data.status === 'success') {
        handleChatSuccess(data);
      } else {
        const errorMsg = data.message || 'An error occurred';
        addMessage(`<strong>❌ Error:</strong> ${escapeHtml(errorMsg)}`, 'error');
        throw new Error(errorMsg);
      }
    } catch (error: any) {
      setMessages(prev => prev.filter(msg => msg.id !== progressMsgId));
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      if (!(error instanceof Error && error.message && !error.message.startsWith('Unknown'))) {
        // Network/timeout errors
      } else {
        addMessage(`<strong>Please RETRY, ❌ Network Error:</strong> ${escapeHtml(errorMessage)}`, 'error');
      }
      throw error; // Re-throw so caller (Execute.tsx) can catch it
    } finally {
      setIsLoading(false);
    }
  };

  // Expose handleClear to parent component via ref
  useImperativeHandle(ref, () => ({
    clearAllFields: handleClear,
    clearFieldsForPromptSwitch: handleClearForPromptSwitch,
    triggerContextFabricProceed,
  }));

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAnalyze();
    }
  };

  // Function to handle text change and show/hide appropriate divs
  const handleUserStoryChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = e.target.value;
    setQueryInputText(text);
    
    // Don't reset agent flow when code assistant is locked (user is typing code prompts)
    if (codeAssistantActive && codeAssistantLocked) return;

    // Don't reset agent flow for Brain queries — user types their question after selecting the prompt
    if (nextagentflow === 'confirmedQueryKnowledgeBase') return;

    // Reset nextagentflow when user changes the query text
    setNextagentflow('');
    setCreateUserStoryText('');
    setCreateUserStoryBrowse(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    setUserStoryUri('');
    setBrdUri('');
    // projectName and stakeholders are managed by admin team â€” only reset file uploads
    isProjectNameOverriddenRef.current = false;
    setIsEditingProjectName(false);
    setActiveRoleDropdown(null);
    setBrdFiles([]);
    setBrdFlowChoice(null);
    setBrdUpdateMode(null);
    if (brdFileInputRef.current) {
      brdFileInputRef.current.value = '';
    }
    // When nextagentflow is reset, hide all conditional fields
    setShowUserStoryUri(false);
    setShowBrdUri(false);
    // Reset validated stories
    setValidatedStories(null);
    setLastValidationPayload(null);
    setEditedValidatedDescriptions({});
    setNewJiraCreateList({});
    setSelectedNewJiraStories(new Set());
  };

  return (
    <div className="embedded-chatbot-container">

      {/* ---- Code Assistant: Sticky Locked Header ---- */}
      {codeAssistantActive && codeAssistantLocked && codeAssistantLockInfo && (
        <div
          className="flex-shrink-0"
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 20,
            background: isDarkMode
              ? '#161b22'
              : '#f0f3f6',
            borderBottom: isDarkMode ? '1px solid rgba(34,197,94,0.25)' : '1px solid rgba(34,197,94,0.3)',
            padding: '6px 12px',
          }}
        >
          {/* Single row: Lock | Branch | Folder | Model | [Centered Label] | Pull | Push | Close */}
          <div className="flex items-center gap-2 text-[10px]" style={{ position: 'relative' }}>
            <Lock className="w-3 h-3 flex-shrink-0" style={{ color: '#22C55E' }} />
            <div style={{ width: 1, height: 14, background: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)' }} className="flex-shrink-0" />
            <span className="text-muted-foreground flex-shrink-0">Branch:</span>
            <span className="font-medium truncate" style={{ fontFamily: "'Fira Code', monospace", color: '#3498B3', maxWidth: '120px' }}>
              {codeAssistantLockInfo.branchName}
            </span>
            <div style={{ width: 1, height: 14, background: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)' }} className="flex-shrink-0" />
            <span className="text-muted-foreground flex-shrink-0">Folder:</span>
            <span className="font-medium truncate" style={{ fontFamily: "'Fira Code', monospace", maxWidth: '120px' }}>
              {codeAssistantLockInfo.folderName}
            </span>
            <div style={{ width: 1, height: 14, background: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)' }} className="flex-shrink-0" />
            <span className="text-muted-foreground flex-shrink-0">Model:</span>
            <span className="font-medium truncate" style={{ maxWidth: '100px' }}>
              {caModelOptions.find(m => m.value === caModel)?.label || caModel}
            </span>
            {/* Centered Code Assistant label */}
            <div className="flex items-center gap-1.5" style={{
              position: 'absolute', left: '50%', transform: 'translateX(-50%)',
              pointerEvents: 'none',
              animation: 'codeAssistantLabelGlow 3s ease-in-out infinite',
            }}>
              <Code2 className="w-3 h-3" style={{ color: '#3498B3', animation: 'codeAssistantLabelGlow 3s ease-in-out infinite' }} />
              <span style={{
                fontSize: '11px',
                fontWeight: 700,
                letterSpacing: '0.3px',
                background: 'linear-gradient(90deg, #3498B3, #0ac4c5)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                whiteSpace: 'nowrap',
                animation: 'codeAssistantLabelGlow 3s ease-in-out infinite',
              }}>
                Code Assistant
              </span>
            </div>
            <div className="flex items-center gap-1.5 ml-auto flex-shrink-0">
              <button
                onClick={() => handleCodeAssistantSync('pull')}
                disabled={caSyncing !== null}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-[10px] font-medium border transition-colors whitespace-nowrap"
                style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent', minWidth: '52px' }}
                title="Pull from remote"
              >
                {caSyncing === 'pull' ? <Loader2 className="w-3 h-3 animate-spin" /> : <><ArrowDownToLine className="w-3 h-3 flex-shrink-0" /> Pull</>}
              </button>
              <button
                onClick={() => handleCodeAssistantSync('push')}
                disabled={caSyncing !== null}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-[10px] font-medium border transition-colors whitespace-nowrap"
                style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent', minWidth: '52px' }}
                title="Push to remote"
              >
                {caSyncing === 'push' ? <Loader2 className="w-3 h-3 animate-spin" /> : <><ArrowUpFromLine className="w-3 h-3 flex-shrink-0" /> Push</>}
              </button>
              <button
                onClick={handleExitCodeAssistant}
                className="p-0.5 rounded hover:bg-red-500/15 transition-colors"
                title="Terminate Code Assistant session"
              >
                <X className="w-3.5 h-3.5" style={{ color: '#ef4444' }} />
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Chat Messages + Agent Fields (scrollable together) */}
      <div ref={chatMessagesRef} className="embedded-chat-messages">
        {messages.map((message, index) => (
          <div key={message.id} className={`embedded-message embedded-${message.type}-message`}>
            {/* Icon inline with bubble */}
            {message.type === 'bot' && (
              <div className="embedded-avatar embedded-avatar-bot">
                <BotIcon className="w-3.5 h-3.5" />
              </div>
            )}
            {/* Message Bubble */}
            <div className="embedded-message-content">
              <div dangerouslySetInnerHTML={{ __html: message.content }} />
              {/* Next Suggested Actions - clickable buttons inside the last bot message bubble */}
              {message.type === 'bot' && index === messages.length - 1 && lastSuggestedActions.length > 0 && !isLoading && !isRefreshingJiraEpics && !isSavingValidatedStory && (
                <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid rgba(224,165,38,0.2)' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#e0a526', display: 'block', marginBottom: '6px' }}>Suggested Next Actions:</span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {lastSuggestedActions.map((sa, saIdx) => (
                      <button
                        key={saIdx}
                        onClick={() => handleSuggestedActionClick(sa)}
                        style={{
                          fontSize: '0.75rem',
                          padding: '4px 10px',
                          borderRadius: '12px',
                          border: '1px solid rgba(224,165,38,0.4)',
                          background: 'rgba(224,165,38,0.08)',
                          color: '#e0a526',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(224,165,38,0.2)'; e.currentTarget.style.borderColor = '#e0a526'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(224,165,38,0.08)'; e.currentTarget.style.borderColor = 'rgba(224,165,38,0.4)'; }}
                      >
                        {sa.action}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {/* Refreshing Jira epics loader â€” shown below next suggested action after user story generation */}
              {message.type === 'bot' && index === messages.length - 1 && isRefreshingJiraEpics && (
                <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid rgba(52,152,179,0.2)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Loader2 className="w-4 h-4 animate-spin" style={{ color: '#3498B3' }} />
                  <span style={{ fontSize: '0.75rem', fontWeight: 500, color: '#3498B3' }}>Refreshing Jira epics</span>
                </div>
              )}
            </div>
            {message.type === 'user' && (
              <div className="embedded-avatar embedded-avatar-user"><UserIcon className="w-3.5 h-3.5" /></div>
            )}
          </div>
        ))}

        {/* Agent-specific input fields rendered inside chat area â€” hidden while loading */}
        {!isLoading && (
        <div className="embedded-agent-fields">

        {/* User Story tree with comparison modal â€” shown when nextagentflow is intentOfUpdateUserStory */}
        {nextagentflow === 'intentOfUpdateUserStory' && validatedStories && (
          <>
            <div className="embedded-input-group">
              <div className="flex items-center justify-between mb-1">
                <Label className="text-xs font-semibold">{userStoryTextLabel}{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
                <div className="text-xs">
                  {selectedJiraStories.length === 0 && (
                    <span className="text-muted-foreground italic">Select stories from Jira panel</span>
                  )}
                  {selectedJiraStories.length > 0 && (
                    <span className="text-muted-foreground">{selectedJiraStories.length} selected</span>
                  )}
                </div>
              </div>

              {/* Tree view of selected epics and their stories â€” click story key to compare */}
              {selectedJiraStories.length > 0 && (
                <div className="mb-2 p-2 rounded-md border border-border bg-muted/30 max-h-[200px] overflow-y-auto">
                  {(() => {
                    const epicMap = new Map<string, { epicKey: string; epicSummary: string; stories: typeof selectedJiraStories }>();
                    for (const story of selectedJiraStories) {
                      const eKey = story.epicKey || 'ungrouped';
                      if (!epicMap.has(eKey)) {
                        epicMap.set(eKey, { epicKey: eKey, epicSummary: story.epicSummary || 'Other', stories: [] });
                      }
                      epicMap.get(eKey)!.stories.push(story);
                    }
                    return Array.from(epicMap.values()).map(({ epicKey, epicSummary, stories }) => {
                      const newStoriesForEpic = newJiraCreateList[epicKey] || [];
                      return (
                      <div key={epicKey} className="mb-1 last:mb-0">
                        <div className="flex items-center gap-1 py-0.5">
                          <ChevronDown className="w-3 h-3 text-muted-foreground" />
                          <span className="text-xs font-medium" style={{ color: '#746FA7' }}>{epicKey}</span>
                          <span className="text-xs text-foreground truncate">- {epicSummary}</span>
                        </div>
                        <div className="ml-4">
                          {stories.map(story => {
                            if (discardedExistingStories.has(story.key)) {
                              return (
                                <div key={story.key} className="flex items-center gap-1.5 py-0.5">
                                  <div className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />
                                  <span className="text-xs opacity-50 line-through" style={{ color: '#746FA7' }}>{story.key}</span>
                                  <span className="text-xs text-muted-foreground opacity-50 line-through truncate flex-1">- {story.summary}</span>
                                  <span className="text-[10px] text-red-500 flex-shrink-0">Discarded</span>
                                  <Pencil
                                    className="w-3 h-3 text-muted-foreground cursor-pointer hover:text-[#3498B3] transition-colors flex-shrink-0"
                                    onClick={() => openComparisonModal(story.key)}
                                  />
                                </div>
                              );
                            }
                            const isEdited = editedValidatedDescriptions[story.key] !== undefined;
                            return (
                              <div key={story.key} className="flex items-center gap-1.5 py-0.5 group/vstory">
                                <div className="w-1.5 h-1.5 rounded-full bg-[#0052CC] flex-shrink-0" />
                                <button
                                  type="button"
                                  onClick={() => openComparisonModal(story.key)}
                                  className="text-xs hover:underline truncate cursor-pointer"
                                  style={{ color: '#746FA7' }}
                                  title="Click to compare & edit"
                                >
                                  {story.key}
                                </button>
                                <span className="text-xs text-muted-foreground truncate flex-1">- {story.summary}</span>
                                {isEdited && (
                                  <span className="text-[10px] text-green-500 flex-shrink-0">Edited</span>
                                )}
                                <Pencil
                                  className="w-3 h-3 text-muted-foreground cursor-pointer hover:text-[#3498B3] transition-colors flex-shrink-0"
                                  onClick={() => openComparisonModal(story.key)}
                                />
                              </div>
                            );
                          })}
                          {/* New AI-suggested stories under this epic */}
                          {newStoriesForEpic.map((storyItem, idx) => {
                            const compoundKey = `${epicKey}-${idx}`;
                            const storyId = `New_Story_${String(idx + 1).padStart(3, '0')}`;
                            const storyTitle = typeof storyItem === 'object' ? storyItem.title : (storyItem as string).split('\n')[0];
                            const storyText = typeof storyItem === 'object' ? storyItem.story : storyItem as string;
                            const displayText = editedNewStoryTexts[compoundKey] ?? storyText;
                            const lines = displayText.split('\n');
                            const acHeaderIndex = lines.findIndex(l => l.trim().toLowerCase().startsWith('acceptance criteria'));
                            const storyDescription = acHeaderIndex >= 0
                              ? lines.slice(0, acHeaderIndex).filter(l => l.trim()).join('\n')
                              : lines.filter(l => l.trim()).join('\n');
                            const acLines = acHeaderIndex >= 0
                              ? lines.slice(acHeaderIndex + 1).filter(l => l.trim())
                              : [];
                            const isSelected = selectedNewJiraStories.has(compoundKey);
                            const isNewEdited = editedNewStoryTexts[compoundKey] !== undefined;
                            return (
                              <details key={compoundKey} className="new-jira-story-item mb-0.5 last:mb-0">
                                <summary className="flex items-center gap-1.5 py-0.5 px-1 cursor-pointer rounded hover:bg-[#3498B3]/10 group/nstory" style={{ listStyle: 'none' }}>
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={(e) => {
                                      e.stopPropagation();
                                      setSelectedNewJiraStories(prev => {
                                        const next = new Set(prev);
                                        if (next.has(compoundKey)) next.delete(compoundKey);
                                        else next.add(compoundKey);
                                        return next;
                                      });
                                    }}
                                    onClick={(e) => e.stopPropagation()}
                                    className="w-3 h-3 cursor-pointer flex-shrink-0"
                                    style={{ accentColor: '#3498B3' }}
                                  />
                                  <ChevronRight className="w-3 h-3 flex-shrink-0 new-jira-chevron" style={{ color: '#3498B3' }} />
                                  <span className="text-xs font-semibold" style={{ color: '#3498B3' }}>{storyId}</span>
                                  <span className="text-[10px] px-1 rounded" style={{ background: 'rgba(52, 152, 179, 0.15)', color: '#3498B3', fontWeight: 600 }}>NEW</span>
                                  <span className="text-xs text-foreground truncate flex-1">- {storyTitle.length > 80 ? storyTitle.substring(0, 80) + '...' : storyTitle}</span>
                                  {isNewEdited && (
                                    <span className="text-[10px] text-green-500 flex-shrink-0">edited</span>
                                  )}
                                  <Pencil
                                    className="w-3 h-3 text-muted-foreground cursor-pointer hover:text-[#3498B3] transition-colors flex-shrink-0"
                                    onClick={(e) => { e.stopPropagation(); e.preventDefault(); openNewStoryEditModal(compoundKey, storyText); }}
                                  />
                                </summary>
                                <div className="ml-6 py-1 px-2">
                                  <div className="text-xs font-semibold text-foreground mb-1" style={{ lineHeight: 1.5, color: '#3498B3' }}><strong>Title:</strong> <span style={{ color: 'var(--foreground)', fontWeight: 500 }}>{storyTitle}</span></div>
                                  <div className="text-xs font-semibold text-foreground mb-1" style={{ lineHeight: 1.5, color: '#3498B3' }}><strong>Story:</strong> <span style={{ color: 'var(--foreground)', fontWeight: 500 }}>{storyDescription}</span></div>
                                  {acLines.length > 0 && (
                                    <div className="mt-1">
                                      <div className="text-xs" style={{ color: '#3498B3', fontWeight: 600, lineHeight: 1.6 }}>Acceptance Criteria:</div>
                                      {acLines.map((line, li) => (
                                        <div key={li} className="text-xs" style={{ color: 'var(--muted-foreground)', fontWeight: 400, paddingLeft: '8px', lineHeight: 1.6 }}>
                                          {line.trim()}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </details>
                            );
                          })}
                        </div>
                      </div>
                      );
                    });
                  })()}
                  {/* New stories for epics not currently in the selected Jira stories */}
                  {(() => {
                    const existingEpicKeys = new Set(selectedJiraStories.map(s => s.epicKey || 'ungrouped'));
                    const orphanEpics = Object.entries(newJiraCreateList).filter(([epicKey]) => !existingEpicKeys.has(epicKey));
                    return orphanEpics.map(([epicKey, stories]) => (
                      <div key={epicKey} className="mb-1 last:mb-0">
                        <div className="flex items-center gap-1 py-0.5">
                          <ChevronDown className="w-3 h-3 text-muted-foreground" />
                          <span className="text-xs font-medium" style={{ color: '#3498B3' }}>{epicKey}</span>
                          <span className="text-[10px] px-1 rounded" style={{ background: 'rgba(52, 152, 179, 0.15)', color: '#3498B3', fontWeight: 600 }}>NEW EPIC</span>
                        </div>
                        <div className="ml-4">
                          {stories.map((storyItem, idx) => {
                            const compoundKey = `${epicKey}-${idx}`;
                            const storyId = `New_Story_${String(idx + 1).padStart(3, '0')}`;
                            const storyTitle = typeof storyItem === 'object' ? storyItem.title : (storyItem as string).split('\n')[0];
                            const storyText = typeof storyItem === 'object' ? storyItem.story : storyItem as string;
                            const displayText = editedNewStoryTexts[compoundKey] ?? storyText;
                            const lines = displayText.split('\n');
                            const acHeaderIndex = lines.findIndex(l => l.trim().toLowerCase().startsWith('acceptance criteria'));
                            const storyDescription = acHeaderIndex >= 0
                              ? lines.slice(0, acHeaderIndex).filter(l => l.trim()).join('\n')
                              : lines.filter(l => l.trim()).join('\n');
                            const acLines = acHeaderIndex >= 0
                              ? lines.slice(acHeaderIndex + 1).filter(l => l.trim())
                              : [];
                            const isSelected = selectedNewJiraStories.has(compoundKey);
                            const isNewEdited = editedNewStoryTexts[compoundKey] !== undefined;
                            return (
                              <details key={compoundKey} className="new-jira-story-item mb-0.5 last:mb-0">
                                <summary className="flex items-center gap-1.5 py-0.5 px-1 cursor-pointer rounded hover:bg-[#3498B3]/10 group/nstory" style={{ listStyle: 'none' }}>
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={(e) => {
                                      e.stopPropagation();
                                      setSelectedNewJiraStories(prev => {
                                        const next = new Set(prev);
                                        if (next.has(compoundKey)) next.delete(compoundKey);
                                        else next.add(compoundKey);
                                        return next;
                                      });
                                    }}
                                    onClick={(e) => e.stopPropagation()}
                                    className="w-3 h-3 cursor-pointer flex-shrink-0"
                                    style={{ accentColor: '#3498B3' }}
                                  />
                                  <ChevronRight className="w-3 h-3 flex-shrink-0 new-jira-chevron" style={{ color: '#3498B3' }} />
                                  <span className="text-xs font-semibold" style={{ color: '#3498B3' }}>{storyId}</span>
                                  <span className="text-[10px] px-1 rounded" style={{ background: 'rgba(52, 152, 179, 0.15)', color: '#3498B3', fontWeight: 600 }}>NEW</span>
                                  <span className="text-xs text-foreground truncate flex-1">- {storyTitle.length > 80 ? storyTitle.substring(0, 80) + '...' : storyTitle}</span>
                                  {isNewEdited && (
                                    <span className="text-[10px] text-green-500 flex-shrink-0">edited</span>
                                  )}
                                  <Pencil
                                    className="w-3 h-3 text-muted-foreground cursor-pointer hover:text-[#3498B3] transition-colors flex-shrink-0"
                                    onClick={(e) => { e.stopPropagation(); e.preventDefault(); openNewStoryEditModal(compoundKey, storyText); }}
                                  />
                                </summary>
                                <div className="ml-6 py-1 px-2">
                                  <div className="text-xs font-semibold text-foreground mb-1" style={{ lineHeight: 1.5, color: '#3498B3' }}><strong>Title:</strong> <span style={{ color: 'var(--foreground)', fontWeight: 500 }}>{storyTitle}</span></div>
                                  <div className="text-xs font-semibold text-foreground mb-1" style={{ lineHeight: 1.5, color: '#3498B3' }}><strong>Story:</strong> <span style={{ color: 'var(--foreground)', fontWeight: 500 }}>{storyDescription}</span></div>
                                  {acLines.length > 0 && (
                                    <div className="mt-1">
                                      <div className="text-xs" style={{ color: '#3498B3', fontWeight: 600, lineHeight: 1.6 }}>Acceptance Criteria:</div>
                                      {acLines.map((line, li) => (
                                        <div key={li} className="text-xs" style={{ color: 'var(--muted-foreground)', fontWeight: 400, paddingLeft: '8px', lineHeight: 1.6 }}>
                                          {line.trim()}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </details>
                            );
                          })}
                        </div>
                      </div>
                    ));
                  })()}
                </div>
              )}

              {/* Select all / count bar for new stories */}
              {Object.keys(newJiraCreateList).length > 0 && (
                <div className="new-jira-create-tree mb-2 p-2 rounded-md border" style={{ borderColor: '#3498B3', background: 'rgba(52, 152, 179, 0.05)' }}>
                  {(() => {
                    const allCompoundKeys: string[] = [];
                    for (const [epicKey, stories] of Object.entries(newJiraCreateList)) {
                      stories.forEach((_, idx) => allCompoundKeys.push(`${epicKey}-${idx}`));
                    }
                    const totalNew = allCompoundKeys.length;
                    return (
                      <div className="flex items-center gap-1.5">
                        <input
                          type="checkbox"
                          checked={totalNew > 0 && selectedNewJiraStories.size === totalNew}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedNewJiraStories(new Set(allCompoundKeys));
                            } else {
                              setSelectedNewJiraStories(new Set());
                            }
                          }}
                          className="w-3.5 h-3.5 cursor-pointer"
                          style={{ accentColor: '#3498B3' }}
                        />
                        <span style={{ color: '#3498B3', fontSize: '12px', fontWeight: 700 }}>Select All New Stories</span>
                        {selectedNewJiraStories.size > 0 && (
                          <span className="text-[10px] text-muted-foreground">({selectedNewJiraStories.size}/{totalNew} selected)</span>
                        )}
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>

            {/* Save validated User Story button */}
            <div className="flex justify-start mt-2">
              <Button
                onClick={handleSaveValidatedUserStory}
                disabled={isSavingValidatedStory}
                variant="outline"
                className="text-xs px-4 py-1.5 h-8 transition-all duration-300"
                style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
              >
                {isSavingValidatedStory ? (
                  <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Saving...</>
                ) : (
                  'Save validated User Story'
                )}
              </Button>
            </div>

            {/* Comparison modal: left = validated response, right = current Jira (editable) */}
            <Dialog open={comparisonModalOpen} onOpenChange={setComparisonModalOpen}>
              <DialogContent
                className="sm:max-w-5xl"
                style={{
                  maxHeight: '88vh',
                  height: '88vh',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                  borderRadius: '16px',
                  padding: 0,
                  gap: 0,
                }}
              >
                {/* Header */}
                <div style={{ flexShrink: 0, padding: '20px 24px 16px', borderBottom: '1px solid var(--border)', background: 'linear-gradient(135deg, rgba(116, 111, 167, 0.08) 0%, rgba(52, 152, 179, 0.08) 100%)' }}>
                  <DialogHeader>
                    <DialogTitle className="text-base font-semibold" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'linear-gradient(135deg, #746FA7, #3498B3)' }} />
                      <span>Compare & Update</span>
                      <span style={{ fontSize: '13px', fontWeight: 500, color: '#746FA7', background: 'rgba(116, 111, 167, 0.12)', padding: '2px 10px', borderRadius: '12px' }}>{comparisonStoryKey}</span>
                    </DialogTitle>
                  </DialogHeader>
                </div>

                {/* Content grid */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0', flex: 1, minHeight: 0, overflow: 'hidden' }}>
                  {/* Left section: Validated story from API (read-only) */}
                  <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden', padding: '16px 20px', borderRight: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0, marginBottom: '12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '3px', height: '16px', borderRadius: '2px', background: '#746FA7' }} />
                        <Label className="text-xs font-semibold" style={{ color: '#746FA7', letterSpacing: '0.02em' }}>AI Validated Story</Label>
                      </div>
                      <button
                        type="button"
                        title="Copy AI suggestion to Jira"
                        className="flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-md hover:bg-[#746FA7]/10 transition-all duration-200"
                        style={{ color: '#746FA7', border: '1px solid rgba(116, 111, 167, 0.25)' }}
                        onClick={() => {
                          if (comparisonValidatedTitle) {
                            setComparisonJiraTitle(comparisonValidatedTitle);
                          }
                          // Convert the rendered HTML on the left into a
                          // structured plain-text representation that mirrors
                          // the visible layout (paragraphs, line breaks,
                          // bullet lists, headings) instead of collapsing
                          // everything onto one line via textContent.
                          const formattedText = htmlToFormattedText(comparisonValidatedText);
                          setComparisonJiraDescription(formattedText);
                        }}
                      >
                        <Copy className="w-3 h-3" />
                        <span>Copy to Jira</span>
                      </button>
                    </div>
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '12px', minHeight: 0, overflowY: 'auto' }} className="themed-scroll">
                      {comparisonValidatedTitle && (
                        <div style={{ flexShrink: 0 }}>
                          <Label className="text-[11px] mb-1.5 block text-muted-foreground font-medium">Title</Label>
                          <div
                            className="text-sm"
                            style={{ borderRadius: '8px', padding: '8px 12px', border: '1px solid var(--border)', background: 'var(--muted)', boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.04)' }}
                          >
                            {comparisonValidatedTitle}
                          </div>
                        </div>
                      )}
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                        <Label className="text-[11px] mb-1.5 block text-muted-foreground font-medium" style={{ flexShrink: 0 }}>Description</Label>
                        <div
                          style={{ flex: 1, minHeight: '120px', overflowY: 'auto', padding: '16px', borderRadius: '10px', border: '1px solid var(--border)', background: 'var(--muted)', boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.04)' }}
                        >
                          <div
                            className="text-xs text-foreground embedded-message-content"
                            style={{ lineHeight: 1.7 }}
                            dangerouslySetInnerHTML={{ __html: comparisonValidatedText }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Right section: Current Jira story (editable) */}
                  <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden', padding: '16px 20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0, marginBottom: '12px' }}>
                      <div style={{ width: '3px', height: '16px', borderRadius: '2px', background: '#0052CC' }} />
                      <Label className="text-xs font-semibold" style={{ color: '#0052CC', letterSpacing: '0.02em' }}>Current Jira Story</Label>
                    </div>
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '12px', minHeight: 0, overflowY: 'auto' }} className="themed-scroll">
                      <div style={{ flexShrink: 0 }}>
                        <Label className="text-[11px] mb-1.5 block text-muted-foreground font-medium">Title</Label>
                        <Input
                          value={comparisonJiraTitle}
                          onChange={(e) => setComparisonJiraTitle(e.target.value)}
                          className="text-sm"
                          style={{ borderRadius: '8px', padding: '8px 12px' }}
                        />
                      </div>
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                        <Label className="text-[11px] mb-1.5 block text-muted-foreground font-medium" style={{ flexShrink: 0 }}>Description</Label>
                        <textarea
                          value={comparisonJiraDescription}
                          onChange={(e) => setComparisonJiraDescription(e.target.value)}
                          style={{ flex: 1, minHeight: '120px', borderRadius: '8px', lineHeight: 1.7 }}
                          className="w-full px-3 py-2.5 text-sm border border-border rounded-md bg-background text-foreground resize-vertical focus:outline-none focus:ring-2 focus:ring-[#3498B3] focus:border-transparent"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Footer */}
                <div style={{ flexShrink: 0, display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '10px', padding: '14px 24px', borderTop: '1px solid var(--border)', background: 'var(--muted)' }}>
                  <Button variant="outline" size="sm" onClick={() => setComparisonModalOpen(false)} style={{ borderRadius: '8px', padding: '6px 16px' }}>Cancel</Button>
                  <Button variant="outline" size="sm" onClick={() => comparisonStoryKey && handleDiscardExistingStory(comparisonStoryKey)} style={{ borderColor: '#ef4444', color: '#ef4444', borderRadius: '8px', padding: '6px 16px' }}>
                    <Trash2 className="w-3 h-3 mr-1.5" />Discard
                  </Button>
                  <Button size="sm" onClick={saveComparisonEdit} style={{ backgroundColor: '#3498B3', borderRadius: '8px', padding: '6px 20px', boxShadow: '0 2px 8px rgba(52, 152, 179, 0.3)' }}>Save</Button>
                </div>
              </DialogContent>
            </Dialog>

            {/* New story edit modal */}
            <Dialog open={newStoryEditModalOpen} onOpenChange={setNewStoryEditModalOpen}>
              <DialogContent
                className="sm:max-w-2xl"
                style={{
                  maxHeight: '70vh',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                }}
              >
                <DialogHeader style={{ flexShrink: 0 }}>
                  <DialogTitle className="text-sm">
                    Edit New User Story
                  </DialogTitle>
                </DialogHeader>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, paddingTop: '8px', paddingBottom: '8px' }}>
                  <Label className="text-[11px] mb-1 block text-muted-foreground" style={{ flexShrink: 0 }}>User Story</Label>
                  <textarea
                    value={editingNewStoryText}
                    onChange={(e) => setEditingNewStoryText(e.target.value)}
                    style={{ flex: 1, minHeight: '200px' }}
                    className="w-full px-3 py-2 text-sm border border-border rounded-md bg-background text-foreground resize-vertical focus:outline-none focus:ring-2 focus:ring-[#3498B3]"
                  />
                </div>
                <div style={{ flexShrink: 0, display: 'flex', justifyContent: 'flex-end', gap: '8px', paddingTop: '12px', borderTop: '1px solid var(--border)' }}>
                  <Button variant="outline" size="sm" onClick={() => setNewStoryEditModalOpen(false)}>Cancel</Button>
                  <Button variant="outline" size="sm" onClick={discardNewStoryEdit} style={{ borderColor: '#ef4444', color: '#ef4444' }}>Discard</Button>
                  <Button size="sm" onClick={saveNewStoryEdit} style={{ backgroundColor: '#3498B3' }}>Save</Button>
                </div>
              </DialogContent>
            </Dialog>
          </>
        )}

        {showUserStoryUri && (
          <>
            <div className="embedded-input-group">
              <Label htmlFor="createUserStoryText" className="text-xs mb-1">Create User Story Text{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
              <textarea
                id="createUserStoryText"
                placeholder="Enter user story text to create..."
                value={createUserStoryText}
                onChange={(e) => setCreateUserStoryText(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 text-sm border border-border rounded-md bg-background text-foreground resize-none focus:outline-none focus:ring-2 focus:ring-[#3498B3]"
              />
            </div>

          </>
        )}
        {/* Project Name & Source URL inputs for User Manual agent */}
        {nextagentflow === 'confirmedCreateUserManual' && (
          <>
            <div className="embedded-input-group" style={{ marginBottom: 12 }}>
              <Label htmlFor="user-manual-project-name">Project Name<span className="text-red-500 ml-1">*</span></Label>
              <Input
                id="user-manual-project-name"
                type="text"
                placeholder="Enter project name"
                value={projectName}
                onChange={e => setProjectName(e.target.value)}
                required
              />
            </div>
            <div className="embedded-input-group" style={{ marginBottom: 12 }}>
              <Label htmlFor="sharepoint-url">Source URL (SharePoint folder or Confluence page)<span className="text-red-500 ml-1">*</span></Label>
              <Input
                id="sharepoint-url"
                type="text"
                placeholder="https://...sharepoint.com/...  or  https://...atlassian.net/wiki/..."
                value={sharepointUrl}
                onChange={e => setSharepointUrl(e.target.value)}
                required
              />
            </div>
            {/* Proceed button — triggers the same analyze/chat-stream flow */}
            <div className="flex justify-start mt-2">
              <Button
                onClick={handleAnalyze}
                disabled={isLoading || !sessionId || !projectName.trim() || !sharepointUrl.trim()}
                variant="outline"
                className="text-xs px-4 py-1.5 h-8 transition-all duration-300"
                style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
              >
                {isLoading ? (
                  <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Processing...</>
                ) : (
                  'Proceed'
                )}
              </Button>
            </div>
          </>
        )}

        {/* Show create_user_story_text for: confirmedUserStoryToTestScenario, confirmedValidateUserStory, and update user stories */}
        {(nextagentflow === 'confirmedUserStoryToTestScenario' || 
          nextagentflow === 'confirmedValidateUserStory' || 
          (nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'update')) && (
          <>
            <div className="embedded-input-group">
              {/* Label row with Jira story link / status */}
              <div className="flex items-center justify-between mb-1">
                <Label htmlFor="createUserStoryText" className="text-xs">{userStoryTextLabel}{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
                <div className="text-xs">
                  {selectedJiraStories.length === 0 && (
                    <span className="text-muted-foreground italic">Select stories from Jira panel</span>
                  )}
                  {selectedJiraStories.length > 0 && (
                    <span className="text-muted-foreground">{selectedJiraStories.length} selected</span>
                  )}
                </div>
              </div>

              {/* Tree view of selected epics and their stories â€” click story key to edit */}
              {selectedJiraStories.length > 0 && (
                <div className="mb-2 p-2 rounded-md border border-border bg-muted/30 max-h-[200px] overflow-y-auto">
                  {(() => {
                    const epicMap = new Map<string, { epicKey: string; epicSummary: string; stories: typeof selectedJiraStories }>();
                    for (const story of selectedJiraStories) {
                      const eKey = story.epicKey || 'ungrouped';
                      if (!epicMap.has(eKey)) {
                        epicMap.set(eKey, { epicKey: eKey, epicSummary: story.epicSummary || 'Other', stories: [] });
                      }
                      epicMap.get(eKey)!.stories.push(story);
                    }
                    return Array.from(epicMap.values()).map(({ epicKey, epicSummary, stories }) => (
                      <div key={epicKey} className="mb-1 last:mb-0">
                        <div className="flex items-center gap-1 py-0.5">
                          <ChevronDown className="w-3 h-3 text-muted-foreground" />
                          <span className="text-xs font-medium" style={{ color: '#746FA7' }}>{epicKey}</span>
                          <span className="text-xs text-foreground truncate">- {epicSummary}</span>
                        </div>
                        <div className="ml-4">
                          {stories.map(story => (
                            <div key={story.key} className="flex items-center gap-1.5 py-0.5 group/story">
                              <div className="w-1.5 h-1.5 rounded-full bg-[#0052CC] flex-shrink-0" />
                              <button
                                type="button"
                                onClick={() => openStoryEditModal(story.key)}
                                className="text-xs hover:underline truncate cursor-pointer"
                                style={{ color: '#746FA7' }}
                                title={(nextagentflow === 'confirmedValidateUserStory' || nextagentflow === 'confirmedUserStoryToTestScenario' || (nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'update')) ? 'Click to view description' : 'Click to view/edit description'}
                              >
                                {story.key}
                              </button>
                              <span className="text-xs text-muted-foreground truncate flex-1">- {story.summary}</span>
                              {nextagentflow !== 'confirmedValidateUserStory' && nextagentflow !== 'confirmedUserStoryToTestScenario' && (
                                <Pencil
                                  className="w-3 h-3 text-muted-foreground opacity-0 group-hover/story:opacity-100 cursor-pointer hover:text-[#3498B3] transition-opacity flex-shrink-0"
                                  onClick={() => openStoryEditModal(story.key)}
                                />
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ));
                  })()}
                </div>
              )}
            </div>

            {/* Modal for viewing/editing a single story description */}
            <Dialog open={storyEditModalOpen} onOpenChange={setStoryEditModalOpen}>
              <DialogContent className={(nextagentflow === 'confirmedValidateUserStory' || nextagentflow === 'confirmedUserStoryToTestScenario' || (nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'update')) ? 'sm:max-w-3xl' : 'sm:max-w-lg'}>
                <DialogHeader>
                  <DialogTitle className="text-sm">
                    {(nextagentflow === 'confirmedValidateUserStory' || nextagentflow === 'confirmedUserStoryToTestScenario' || (nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'update')) ? 'View Story' : 'Edit Story'} â€” {editingStoryKey}
                  </DialogTitle>
                </DialogHeader>
                <div className="py-2">
                  <Label className="text-xs mb-1 block">Description</Label>
                  <textarea
                    value={editingStoryText}
                    onChange={(e) => setEditingStoryText(e.target.value)}
                    readOnly={nextagentflow === 'confirmedValidateUserStory' || nextagentflow === 'confirmedUserStoryToTestScenario' || (nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'update')}
                    rows={(nextagentflow === 'confirmedValidateUserStory' || nextagentflow === 'confirmedUserStoryToTestScenario' || (nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'update')) ? 16 : 8}
                    className={`w-full px-3 py-2 text-sm border border-border rounded-md bg-background text-foreground resize-vertical focus:outline-none focus:ring-2 focus:ring-[#3498B3] ${(nextagentflow === 'confirmedValidateUserStory' || nextagentflow === 'confirmedUserStoryToTestScenario' || (nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'update')) ? 'cursor-default opacity-80' : ''}`}
                  />
                </div>
                {nextagentflow !== 'confirmedValidateUserStory' && nextagentflow !== 'confirmedUserStoryToTestScenario' && !(nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'update') && (
                  <DialogFooter>
                    <Button variant="outline" size="sm" onClick={() => setStoryEditModalOpen(false)}>Cancel</Button>
                    <Button size="sm" onClick={saveStoryEdit} style={{ backgroundColor: '#3498B3' }}>Save</Button>
                  </DialogFooter>
                )}
              </DialogContent>
            </Dialog>
          </>
        )}

        {/* Show User Story flow: conversational choice → Create New or Update Existing */}
        {nextagentflow === 'confirmedCreateUserStory' && !userStoryFlowChoice && (
          <div className="flex gap-2 mt-2">
            <Button
              onClick={() => {
                addMessage('I want to create new user stories.', 'user');
                addMessage('Great! Please provide the BRD Confluence link to generate user stories.', 'bot');
                setFinalBrdConfluenceLink('');
                setUserStoryFlowChoice('create');
              }}
              variant="outline"
              className="text-xs px-4 py-1.5 h-8 transition-all duration-300 flex items-center gap-1.5"
              style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
            >
              <Sparkles className="w-3 h-3" /> Create New Stories
            </Button>
            <Button
              onClick={() => {
                addMessage('I want to update existing user stories.', 'user');
                addMessage('Enter or Review below details to update user stories. Please select the Confluence URL and its associated epics from the Jira panel to proceed for updation.', 'bot');
                setFinalBrdConfluenceLink('');
                setUserStoryFlowChoice('update');
              }}
              variant="outline"
              className="text-xs px-4 py-1.5 h-8 transition-all duration-300 flex items-center gap-1.5"
              style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
            >
              <Pencil className="w-3 h-3" /> Update Existing Stories
            </Button>
          </div>
        )}
        {/* Show create user story inputs for: confirmedCreateUserStory with 'create' choice */}
        {nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'create' && (
          <>
            
            <div className="embedded-input-group">
              {finalBrdConfluenceLink  && projectName && projectName.trim() && (
              <>
              <Label htmlFor="createUserStoryBrowse" className="text-xs mb-1" style={{ color: '#0ac4c5' }}>Creating User Story from Confluence Link:{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
              <div className="flex items-center gap-2 px-3 py-2 text-sm">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ display: 'inline-block', verticalAlign: 'middle' }}>
                  <path d="M2.5 2C2.22386 2 2 2.22386 2 2.5V21.5C2 21.7761 2.22386 22 2.5 22H21.5C21.7761 22 22 21.7761 22 21.5V2.5C22 2.22386 21.7761 2 21.5 2H2.5ZM5.71429 17.1429C5.71429 17.1429 5.28571 17.5714 4.85714 17.5714C4.42857 17.5714 4 17.1429 4 16.7143V7.28571C4 6.85714 4.42857 6.42857 4.85714 6.42857C5.28571 6.42857 5.71429 6.85714 5.71429 7.28571V17.1429ZM11.5714 11.5714C11.5714 11.5714 11.1429 12 10.7143 12C10.2857 12 9.85714 11.5714 9.85714 11.1429V7.28571C9.85714 6.85714 10.2857 6.42857 10.7143 6.42857C11.1429 6.42857 11.5714 6.85714 11.5714 7.28571V11.5714ZM17.4286 17.1429C17.4286 17.1429 17 17.5714 16.5714 17.5714C16.1429 17.5714 15.7143 17.1429 15.7143 16.7143V7.28571C15.7143 6.85714 16.1429 6.42857 16.5714 6.42857C17 6.42857 17.4286 6.85714 17.4286 7.28571V17.1429Z" fill="#0052CC"/>
                </svg>
                <a 
                  href={finalBrdConfluenceLink} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  style={{ color: '#3498B3', textDecoration: 'underline', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'inline-block', maxWidth: 'calc(100% - 24px)', verticalAlign: 'middle' }}
                >
                  {projectName}
                </a>
              </div>
              <>
              or,
              </>
              </>
            )}
              <>
              <Label htmlFor="brdConfluenceLinkInput" className="text-xs mb-1 mt-3" style={{ color: '#0ac4c5' }}>Enter any BRD Confluence Page Link:<span className="text-red-500 ml-1">*</span></Label>
              </>
              <Input
                id="brdConfluenceLinkInput"
                type="text"
                placeholder="Enter BRD Confluence Page link..."
                value={finalBrdConfluenceLink}
                onChange={(e) => setFinalBrdConfluenceLink(e.target.value)}
                className="text-sm"
              />
            </div>

            {/* Proceed button â€” triggers the same analyze flow */}
            <div className="flex justify-start mt-2">
              <Button
                onClick={handleAnalyze}
                disabled={isLoading || !sessionId || !finalBrdConfluenceLink.trim()}
                variant="outline"
                className="text-xs px-4 py-1.5 h-8 transition-all duration-300"
                style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
              >
                {isLoading ? (
                  <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Processing...</>
                ) : (
                  'Proceed'
                )}
              </Button>
            </div>
          </>
        )}
        {/* Show create_user_story_text for: confirmedBrdSummary */}
        {(nextagentflow === 'confirmedBrdSummary') && (
          <>
            
            <div className="embedded-input-group">
              {finalBrdConfluenceLink  && projectName && projectName.trim() && (
              <>
              <Label htmlFor="createUserStoryBrowse" className="text-xs mb-1">Creating BRD Summary from Confluence Link:{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
              <div className="flex items-center gap-2 px-3 py-2 text-sm">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ display: 'inline-block', verticalAlign: 'middle' }}>
                  <path d="M2.5 2C2.22386 2 2 2.22386 2 2.5V21.5C2 21.7761 2.22386 22 2.5 22H21.5C21.7761 22 22 21.7761 22 21.5V2.5C22 2.22386 21.7761 2 21.5 2H2.5ZM5.71429 17.1429C5.71429 17.1429 5.28571 17.5714 4.85714 17.5714C4.42857 17.5714 4 17.1429 4 16.7143V7.28571C4 6.85714 4.42857 6.42857 4.85714 6.42857C5.28571 6.42857 5.71429 6.85714 5.71429 7.28571V17.1429ZM11.5714 11.5714C11.5714 11.5714 11.1429 12 10.7143 12C10.2857 12 9.85714 11.5714 9.85714 11.1429V7.28571C9.85714 6.85714 10.2857 6.42857 10.7143 6.42857C11.1429 6.42857 11.5714 6.85714 11.5714 7.28571V11.5714ZM17.4286 17.1429C17.4286 17.1429 17 17.5714 16.5714 17.5714C16.1429 17.5714 15.7143 17.1429 15.7143 16.7143V7.28571C15.7143 6.85714 16.1429 6.42857 16.5714 6.42857C17 6.42857 17.4286 6.85714 17.4286 7.28571V17.1429Z" fill="#0052CC"/>
                </svg>
                <a 
                  href={finalBrdConfluenceLink} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  style={{ color: '#3498B3', textDecoration: 'underline', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'inline-block', maxWidth: 'calc(100% - 24px)', verticalAlign: 'middle' }}
                >
                  {projectName}
                </a>
              </div>
              <>
              <label></label>
              <Label htmlFor="brdConfluenceLinkInput" className="text-xs my-4" style={{ color: '#0ac4c5' }}> OR {nextagentflow && <span className="text-red-500 ml-1"></span>}</Label>
              <label></label>
              </>
              </>
            )}
              <>
              <Label htmlFor="brdConfluenceLinkInput" className="text-xs mb-1 mt-3" style={{ color: '#0ac4c5' }}>Enter any BRD Confluence Page Link:<span className="text-red-500 ml-1">*</span></Label>
              </>
              <Input
                id="brdConfluenceLinkInput"
                type="text"
                placeholder="Enter BRD Confluence Page link..."
                value={finalBrdConfluenceLink}
                onChange={(e) => setFinalBrdConfluenceLink(e.target.value)}
                className="text-sm"
              />

              {/* Proceed button â€" triggers the same analyze flow */}
              <div className="flex justify-start mt-2">
                <Button
                  onClick={handleAnalyze}
                  disabled={isLoading || !sessionId || !finalBrdConfluenceLink.trim()}
                  variant="outline"
                  className="text-xs px-4 py-1.5 h-8 transition-all duration-300"
                  style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
                >
                  {isLoading ? (
                    <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Processing...</>
                  ) : (
                    'Proceed'
                  )}
                </Button>
              </div>
            </div>
          </>
        )}

        {/* Show scenario_types for: confirmedUserStoryToTestScenario */}
        {nextagentflow === 'confirmedUserStoryToTestScenario' && (() => {
          const DEFAULT_SCENARIO_TYPES = [
            "Functional",
            "Non Functional",
            "Boundary & Negative",
            "Gherkin Functional",
            "Gherkin Boundary & Negative",
            "Buttons Enabled-Disabled",
            "Dropdown-Picklist",
            "System Architecture",
            "Combinatorial",
            "Bug Related",
            "Patch Related"
          ];
          const options = scenarioTypesOptions.length > 0 ? scenarioTypesOptions : DEFAULT_SCENARIO_TYPES;

          const handleAllCheckboxChange = () => {
            if (isAllScenarioTypesSelected) {
              setIsAllScenarioTypesSelected(false);
              setSelectedScenarioTypes([]);
              setScenarioTypes('');
            } else {
              setIsAllScenarioTypesSelected(true);
              setSelectedScenarioTypes([...options]);
              setScenarioTypes(options.join(', '));
            }
          };

          const handleOptionCheckboxChange = (option: string) => {
            if (isAllScenarioTypesSelected) return;
            const isSelected = selectedScenarioTypes.includes(option);
            if (isSelected) {
              const updated = selectedScenarioTypes.filter(t => t !== option);
              setSelectedScenarioTypes(updated);
              setScenarioTypes(updated.join(', '));
            } else {
              const updated = [...selectedScenarioTypes, option];
              setSelectedScenarioTypes(updated);
              setScenarioTypes(updated.join(', '));
            }
          };

          return (
            <div className="embedded-input-group">
              <Label htmlFor="scenarioTypes" className="text-xs mb-1">Scenario Types{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
              <div className="w-full px-3 py-2 border border-border rounded-md bg-background max-h-52 overflow-y-auto themed-scroll">
                {/* All checkbox */}
                <div
                  onClick={handleAllCheckboxChange}
                  className={`py-1.5 cursor-pointer flex items-center gap-2 ${isAllScenarioTypesSelected ? 'text-[#3498B3] font-medium' : 'text-foreground'}`}
                  style={{ fontSize: '0.78rem', fontFamily: 'inherit' }}
                >
                  <span
                    className={`w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center ${isAllScenarioTypesSelected ? 'bg-[#3498B3] border-[#3498B3]' : 'border-muted-foreground/40'}`}
                  >
                    {isAllScenarioTypesSelected && (
                      <svg width="10" height="10" viewBox="0 0 12 12" fill="none"><path d="M2.5 6L5 8.5L9.5 3.5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                    )}
                  </span>
                  All
                </div>
                <div className="border-t border-border my-1"></div>
                {/* Individual scenario type checkboxes - 3 per row */}
                <div className="grid grid-cols-3 gap-1">
                  {options.map((option, index) => {
                    const isSelected = selectedScenarioTypes.includes(option);
                    const isDisabled = isAllScenarioTypesSelected;
                    return (
                      <div
                        key={index}
                        onClick={() => handleOptionCheckboxChange(option)}
                        className={`py-1.5 flex items-center gap-2 ${isDisabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'} ${isSelected && !isDisabled ? 'text-[#3498B3] font-medium' : 'text-foreground'}`}
                        style={{ fontSize: '0.78rem', fontFamily: 'inherit' }}
                      >
                        <span
                          className={`w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center ${isSelected ? 'bg-[#3498B3] border-[#3498B3]' : 'border-muted-foreground/40'}`}
                        >
                          {isSelected && (
                            <svg width="10" height="10" viewBox="0 0 12 12" fill="none"><path d="M2.5 6L5 8.5L9.5 3.5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                          )}
                        </span>
                        {option}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          );
        })()}

        {/* Proceed button for confirmedUserStoryToTestScenario */}
        {nextagentflow === 'confirmedUserStoryToTestScenario' && (
          <div className="flex justify-start mt-2">
            <Button
              onClick={handleAnalyze}
              disabled={isLoading || !sessionId || selectedJiraStories.length === 0 || selectedScenarioTypes.length === 0}
              variant="outline"
              className="text-xs px-4 py-1.5 h-8 transition-all duration-300"
              style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
            >
              {isLoading ? (
                <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Processing...</>
              ) : (
                'Proceed'
              )}
            </Button>
          </div>
        )}

        {/* Show test_scenarios for: confirmedTestScenarioToTestCase */}
        {nextagentflow === 'confirmedTestScenarioToTestCase' && (
          <div className="embedded-input-group">
            <Label htmlFor="testScenarios" className="text-xs mb-1">Test Scenarios{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
            <textarea
              id="testScenarios"
              placeholder="Enter test scenarios..."
              value={testScenarios}
              onChange={(e) => setTestScenarios(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 text-sm border border-border rounded-md bg-background text-foreground resize-none focus:outline-none focus:ring-2 focus:ring-[#3498B3]"
            />
          </div>
        )}

        {/* Show test_case_format for: confirmedTestScenarioToTestCase */}
        {nextagentflow === 'confirmedTestScenarioToTestCase' && (
          <div className="embedded-input-group">
            <Label htmlFor="testCaseFormat" className="text-xs mb-1">Test Case Format{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
            <textarea
              id="testCaseFormat"
              placeholder="Enter test case format..."
              value={testCaseFormat}
              onChange={(e) => setTestCaseFormat(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 text-sm border border-border rounded-md bg-background text-foreground resize-none focus:outline-none focus:ring-2 focus:ring-[#3498B3]"
            />
          </div>
        )}

        {/* Validation error for confirmedTestCaseToTestScript */}
        {nextagentflow === 'confirmedTestCaseToTestScript' && testCaseValidationError && (
          <div className="embedded-input-group">
            <Label className="text-xs font-semibold" style={{ color: 'red' }}>{testCaseValidationError}</Label>
          </div>
        )}

        {/* Show test_cases for: confirmedTestCaseToTestScript */}
        {nextagentflow === 'confirmedTestCaseToTestScript' && (
          <div className="embedded-input-group">
           <Label htmlFor="testCases" className="text-xs font-semibold mb-1" style={{ letterSpacing: '0.02em' }}>
             Test Cases{nextagentflow && <span className="text-red-500 ml-1">*</span>}
             {selectedTestCasesFromJira.length > 0 && (
               <span className="ml-2 text-muted-foreground font-normal">({selectedTestCasesFromJira.length} selected)</span>
             )}
           </Label>

            {/* Read-only test case content display â€” scrollable list for all selected test cases */}
            {isLoadingTestCases ? (
              <div className="w-full px-3 py-4 border border-border rounded-md bg-muted/30 flex flex-col items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-[#3498B3]" />
                <p className="text-xs text-muted-foreground">Fetching test cases from Jira...</p>
              </div>
            ) : selectedTestCasesFromJira.length > 0 ? (
              <div
                className="w-full px-3 py-2 border border-border rounded-md bg-muted/30 overflow-y-auto themed-scroll text-sm"
                style={{ maxHeight: '180px' }}
              >
                {selectedTestCasesFromJira.map((tc, idx) => (
                  <div key={tc.key} className={`flex items-baseline gap-1.5 ${idx > 0 ? 'mt-1 pt-1 border-t border-border/30' : ''}`}>
                    <span className="text-xs font-semibold shrink-0" style={{ color: '#3498B3' }}>{tc.key}</span>
                    <span className="text-xs text-foreground truncate">{tc.summary}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="w-full px-3 py-2 text-center border border-dashed border-border rounded-md bg-muted/20">
                <p className="text-xs text-muted-foreground">
                  Select epics from the left panel to load all corresponding test cases
                </p>
              </div>
            )}

            {/* Hidden field to keep testCases value in sync for form submission */}
            <input type="hidden" id="testCases" value={testCases} />
          </div>
        )}

        {/* Supported Combinations link + popup â€” between Test Cases and Framework */}
        {nextagentflow === 'confirmedTestCaseToTestScript' && (
          <div className="embedded-input-group">
            {/* Row 1: View Combinations link */}
            <button
              type="button"
              onClick={() => setShowCombinationsPopup(!showCombinationsPopup)}
              className="flex items-center gap-1 text-xs font-semibold transition-colors mb-2"
              style={{ color: '#3498B3', letterSpacing: '0.02em', textDecoration: 'underline' }}
            >
              <Table2 className="w-3 h-3" />
              {showCombinationsPopup ? 'Hide' : 'View'} Supported Combinations
            </button>

            {/* Row 2: Framework | Language | Script horizontal */}
            <div className="flex gap-2 w-full">
              <div className="flex-1 min-w-0">
                <Label htmlFor="frameworkType" className="text-xs mb-1">Framework{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
                <input
                  id="frameworkType"
                  placeholder="Select from combinations"
                  value={frameworkType}
                  readOnly
                  className="w-full px-3 py-2 text-sm border border-dashed border-border rounded-md bg-muted/20 text-foreground cursor-default focus:outline-none"
                />
              </div>
              <div className="flex-1 min-w-0">
                <Label htmlFor="language" className="text-xs mb-1">Language{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
                <input
                  id="language"
                  placeholder="Select from combinations"
                  value={language}
                  readOnly
                  className="w-full px-3 py-2 text-sm border border-dashed border-border rounded-md bg-muted/20 text-foreground cursor-default focus:outline-none"
                />
              </div>
              <div className="flex-1 min-w-0">
                <Label htmlFor="scriptGenerationType" className="text-xs mb-1">Script{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
                <input
                  id="scriptGenerationType"
                  placeholder="Select from combinations"
                  value={scriptGenerationType}
                  readOnly
                  className="w-full px-3 py-2 text-sm border border-dashed border-border rounded-md bg-muted/20 text-foreground cursor-default focus:outline-none"
                />
              </div>
            </div>

            {/* Modal-style popup â€” centered, semi-transparent so fields visible behind */}
            {showCombinationsPopup && (
              <div
                className="fixed inset-0 flex items-center justify-center px-4 py-10"
                style={{ zIndex: 9999, backgroundColor: 'rgba(0,0,0,0.15)' }}
                onClick={(e) => { if (e.target === e.currentTarget) setShowCombinationsPopup(false); }}
              >
                <div
                  className="w-full max-w-2xl rounded-xl shadow-2xl border border-border flex flex-col"
                  style={{
                    maxHeight: 'calc(100vh - 8rem)',
                    backgroundColor: isDarkMode ? 'rgba(26, 26, 46, 0.70)' : 'rgba(255, 255, 255, 0.65)',
                    backdropFilter: 'blur(10px)',
                    WebkitBackdropFilter: 'blur(10px)',
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  {/* Modal Header */}
                  <div className="flex items-center justify-between px-6 py-4 border-b border-border flex-shrink-0"
                       style={{ backgroundColor: isDarkMode ? 'rgba(53, 26, 85, 0.5)' : 'rgba(53, 26, 85, 0.08)' }}>
                    <div>
                      <h3 className="text-base font-bold text-foreground">Supported Combinations</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">Select a framework, language &amp; generation type combination</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowCombinationsPopup(false)}
                      className="text-muted-foreground hover:text-foreground p-1.5 hover:bg-muted rounded-lg transition-colors"
                    >
                      <span className="text-lg font-bold">&times;</span>
                    </button>
                  </div>

                  {/* Modal Body â€” scrollable table */}
                  <div className="flex-1 overflow-y-auto min-h-0">
                    <table className="w-full text-sm border-collapse">
                      <thead>
                        <tr style={{ backgroundColor: isDarkMode ? 'rgba(53, 26, 85, 0.4)' : 'rgba(53, 26, 85, 0.06)' }}>
                          <th className="px-4 py-2.5 text-left font-semibold border-b border-border" style={{ width: '44px' }}>
                            <span className="text-xs text-muted-foreground">Row Select</span>
                          </th>
                          <th className="px-4 py-2.5 text-left font-semibold border-b border-border">Framework</th>
                          <th className="px-4 py-2.5 text-left font-semibold border-b border-border">Language</th>
                          <th className="px-4 py-2.5 text-center font-semibold border-b border-border" colSpan={2}>Generation Types</th>
                        </tr>
                        <tr style={{ backgroundColor: isDarkMode ? 'rgba(53, 26, 85, 0.25)' : 'rgba(53, 26, 85, 0.03)' }}>
                          <th className="border-b border-border"></th>
                          <th className="border-b border-border"></th>
                          <th className="border-b border-border"></th>
                          <th className="px-4 py-1.5 text-center text-xs font-medium border-b border-border">Greenfield</th>
                          <th className="px-4 py-1.5 text-center text-xs font-medium border-b border-border">Brownfield</th>
                        </tr>
                      </thead>
                      <tbody>
                        {SUPPORTED_COMBINATIONS.map((combo, idx) => {
                          const isRowSelected = frameworkType === combo.framework && language === combo.language;
                          const selectedGenTypes = isRowSelected ? scriptGenerationType.split(',').map(s => s.trim()).filter(Boolean) : [];
                          const isGreenfieldChecked = isRowSelected && selectedGenTypes.includes('Greenfield');
                          const isBrownfieldChecked = isRowSelected && selectedGenTypes.includes('Brownfield');
                          return (
                            <tr
                              key={idx}
                              className={`cursor-pointer transition-colors ${
                                isRowSelected
                                  ? (isDarkMode ? 'bg-[#3498B3]/30' : 'bg-[#3498B3]/15')
                                  : 'hover:bg-muted/30'
                              }`}
                              onClick={() => {
                                if (isRowSelected) {
                                  // Deselect entire row
                                  setFrameworkType('');
                                  setLanguage('');
                                  setScriptGenerationType('');
                                } else {
                                  // Select row â†’ set framework, language, and first generation type only
                                  setFrameworkType(combo.framework);
                                  setLanguage(combo.language);
                                  setScriptGenerationType(combo.generationTypes[0] || '');
                                }
                              }}
                            >
                              <td className="px-4 py-2.5 border-b border-border text-center">
                                <input
                                  type="radio"
                                  name="comboRowSelect"
                                  checked={isRowSelected}
                                  readOnly
                                  className="w-4 h-4 accent-[#3498B3] cursor-pointer"
                                />
                              </td>
                              <td className="px-4 py-2.5 border-b border-border font-medium">{combo.framework}</td>
                              <td className="px-4 py-2.5 border-b border-border">{combo.language}</td>
                              {combo.generationTypes.map((gt) => {
                                const isGtChecked = gt === 'Greenfield' ? isGreenfieldChecked : isBrownfieldChecked;
                                return (
                                  <td key={gt} className="px-4 py-2.5 border-b border-border text-center">
                                    <input
                                      type="radio"
                                      name={`genType-${combo.framework}-${combo.language}`}
                                      checked={isGtChecked}
                                      className="w-4 h-4 accent-[#3498B3] cursor-pointer"
                                      onClick={(e) => e.stopPropagation()}
                                      onChange={() => {
                                        setFrameworkType(combo.framework);
                                        setLanguage(combo.language);
                                        setScriptGenerationType(isGtChecked ? '' : gt);
                                      }}
                                    />
                                  </td>
                                );
                              })}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Modal Footer */}
                  <div className="flex items-center justify-between px-6 py-3 border-t border-border flex-shrink-0"
                       style={{ backgroundColor: isDarkMode ? 'rgba(53, 26, 85, 0.3)' : 'rgba(53, 26, 85, 0.05)' }}>
                    <p className="text-xs text-muted-foreground">
                      {SUPPORTED_COMBINATIONS.length} combinations available
                    </p>
                    <button
                      type="button"
                      onClick={() => setShowCombinationsPopup(false)}
                      className="px-4 py-1.5 rounded-lg text-sm font-medium text-white transition-colors"
                      style={{ background: 'linear-gradient(135deg, #351A55, #3498B3)' }}
                    >
                      Done
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Proceed button for confirmedTestCaseToTestScript */}
        {nextagentflow === 'confirmedTestCaseToTestScript' && (
          <div className="flex justify-start mt-2">
            <Button
              onClick={handleAnalyze}
              disabled={isLoading || !sessionId || selectedTestCasesFromJira.length === 0 || !frameworkType.trim() || !language.trim() || !scriptGenerationType.trim()}
              variant="outline"
              className="text-xs px-4 py-1.5 h-8 transition-all duration-300"
              style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
            >
              {isLoading ? (
                <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Processing...</>
              ) : (
                'Proceed'
              )}
            </Button>
          </div>
        )}

        {/* Test Data Generator: Test Cases input */}
        {nextagentflow === 'confirmedTestDataGenerator' && (
          <div className="embedded-input-group">
            <Label htmlFor="testDataCases" className="text-xs font-semibold mb-1" style={{ letterSpacing: '0.02em' }}>
              Test Cases{nextagentflow && <span className="text-red-500 ml-1">*</span>}
              {selectedTestCasesFromJira.length > 0 && (
                <span className="ml-2 text-muted-foreground font-normal">({selectedTestCasesFromJira.length} selected)</span>
              )}
            </Label>

            {isLoadingTestCases ? (
              <div className="w-full px-3 py-4 border border-border rounded-md bg-muted/30 flex flex-col items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-[#3498B3]" />
                <p className="text-xs text-muted-foreground">Fetching test cases from Jira...</p>
              </div>
            ) : selectedTestCasesFromJira.length > 0 ? (
              <div
                className="w-full px-3 py-2 border border-border rounded-md bg-muted/30 overflow-y-auto themed-scroll text-sm"
                style={{ maxHeight: '180px' }}
              >
                {selectedTestCasesFromJira.map((tc, idx) => (
                  <div key={tc.key} className={`flex items-baseline gap-1.5 ${idx > 0 ? 'mt-1 pt-1 border-t border-border/30' : ''}`}>
                    <span className="text-xs font-semibold shrink-0" style={{ color: '#3498B3' }}>{tc.key}</span>
                    <span className="text-xs text-foreground truncate">{tc.summary}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="w-full px-3 py-2 text-center border border-dashed border-border rounded-md bg-muted/20">
                <p className="text-xs text-muted-foreground">
                  Select epics from the left panel to load all corresponding test cases
                </p>
              </div>
            )}
          </div>
        )}

        {/* Test Data Generator: Output Format selector */}
        {nextagentflow === 'confirmedTestDataGenerator' && (
          <div className="embedded-input-group">
            <Label htmlFor="testDataOutputFormat" className="font-semibold mb-1" style={{ fontSize: '0.78rem', fontFamily: 'inherit', letterSpacing: '0.02em' }}>
              Output Format{nextagentflow && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <div className="flex gap-3">
              <label
                className={`flex items-center gap-2 px-4 py-2 rounded-md border cursor-pointer transition-all ${
                  testDataOutputFormat === 'json'
                    ? 'border-[#3498B3] bg-[#3498B3]/10 text-[#3498B3] font-semibold'
                    : 'border-border bg-muted/20 text-muted-foreground hover:border-[#3498B3]/50'
                }`}
                style={{ fontSize: '0.78rem', fontFamily: 'inherit' }}
              >
                <input
                  type="radio"
                  name="testDataOutputFormat"
                  value="json"
                  checked={testDataOutputFormat === 'json'}
                  onChange={() => setTestDataOutputFormat('json')}
                  className="w-4 h-4 accent-[#3498B3]"
                />
                JSON
              </label>
              <label
                className={`flex items-center gap-2 px-4 py-2 rounded-md border cursor-pointer transition-all ${
                  testDataOutputFormat === 'excel'
                    ? 'border-[#3498B3] bg-[#3498B3]/10 text-[#3498B3] font-semibold'
                    : 'border-border bg-muted/20 text-muted-foreground hover:border-[#3498B3]/50'
                }`}
                style={{ fontSize: '0.78rem', fontFamily: 'inherit' }}
              >
                <input
                  type="radio"
                  name="testDataOutputFormat"
                  value="excel"
                  checked={testDataOutputFormat === 'excel'}
                  onChange={() => setTestDataOutputFormat('excel')}
                  className="w-4 h-4 accent-[#3498B3]"
                />
                Excel (XLSX)
              </label>
            </div>
          </div>
        )}

        {/* Proceed button for confirmedTestDataGenerator */}
        {nextagentflow === 'confirmedTestDataGenerator' && (
          <div className="flex justify-start mt-2">
            <Button
              onClick={handleAnalyze}
              disabled={isLoading || !sessionId || selectedTestCasesFromJira.length === 0}
              variant="outline"
              className="text-xs px-4 py-1.5 h-8 transition-all duration-300"
              style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
            >
              {isLoading ? (
                <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Processing...</>
              ) : (
                'Proceed'
              )}
            </Button>
          </div>
        )}

        {/* Show brd_document_uri for: confirmedValidateUserStory and Update User Stories */}
        {(nextagentflow === 'confirmedValidateUserStory' || (nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'update')) && (
          <div className="embedded-input-group">
            
            {nextagentflow === 'confirmedValidateUserStory' && finalBrdConfluenceLink  && projectName && projectName.trim() && (
            <>
            <Label htmlFor="brdUri" className="text-xs mb-1">BRD Document Confluence Page:{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
              <div className="flex items-center gap-2 px-3 py-2 text-sm">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ display: 'inline-block', verticalAlign: 'middle' }}>
                  <path d="M2.5 2C2.22386 2 2 2.22386 2 2.5V21.5C2 21.7761 2.22386 22 2.5 22H21.5C21.7761 22 22 21.7761 22 21.5V2.5C22 2.22386 21.7761 2 21.5 2H2.5ZM5.71429 17.1429C5.71429 17.1429 5.28571 17.5714 4.85714 17.5714C4.42857 17.5714 4 17.1429 4 16.7143V7.28571C4 6.85714 4.42857 6.42857 4.85714 6.42857C5.28571 6.42857 5.71429 6.85714 5.71429 7.28571V17.1429ZM11.5714 11.5714C11.5714 11.5714 11.1429 12 10.7143 12C10.2857 12 9.85714 11.5714 9.85714 11.1429V7.28571C9.85714 6.85714 10.2857 6.42857 10.7143 6.42857C11.1429 6.42857 11.5714 6.85714 11.5714 7.28571V11.5714ZM17.4286 17.1429C17.4286 17.1429 17 17.5714 16.5714 17.5714C16.1429 17.5714 15.7143 17.1429 15.7143 16.7143V7.28571C15.7143 6.85714 16.1429 6.42857 16.5714 6.42857C17 6.42857 17.4286 6.85714 17.4286 7.28571V17.1429Z" fill="#0052CC"/>
                </svg>
                <a 
                  href={finalBrdConfluenceLink} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  style={{ color: '#3498B3', textDecoration: 'underline' }}
                >
                  {projectName}
                </a>
              </div>
              or,
            </>
            )}
            <div className="flex items-center justify-between">
              <Label htmlFor="brdConfluenceLinkInput" className="text-xs mb-1 mt-3" style={{ color: '#0ac4c5' }}>Enter any BRD Confluence Page Link:<span className="text-red-500 ml-1">*</span></Label>
              {(nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'update') && (
                <span className="text-muted-foreground italic text-xs">Select BRD from Confluence panel</span>
              )}
            </div>
              <Input
                id="brdConfluenceLinkInput"
                type="text"
                placeholder="Enter BRD Confluence Page link..."
                value={finalBrdConfluenceLink}
                onChange={(e) => setFinalBrdConfluenceLink(e.target.value)}
                className="text-sm"
              />

            {/* Proceed button â€” triggers the same analyze flow */}
            <div className="flex justify-start mt-2">
              <Button
                onClick={(nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'update') ? handleUserStoryUpdate : handleAnalyze}
                disabled={isLoading || selectedJiraStories.length === 0 || ((nextagentflow === 'confirmedCreateUserStory' && userStoryFlowChoice === 'update') ? !finalBrdConfluenceLink.trim() : !sessionId)}
                variant="outline"
                className="text-xs px-4 py-1.5 h-8 transition-all duration-300"
                style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
              >
                {isLoading ? (
                  <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Processing...</>
                ) : (
                  'Proceed'
                )}
              </Button>
            </div>
          </div>
        )}
        {/* Show Update Existing BRD inputs — Confluence link + chat/upload */}
        {nextagentflow === 'confirmedCreateBrd' && brdFlowChoice === 'update' && (
          <>
            {/* Confluence link input (reuses same pattern as validator) */}
            <div className="embedded-input-group">
              <div className="flex items-center justify-between">
                <Label htmlFor="brdUpdateConfluenceLinkInput" className="text-xs mb-1" style={{ color: '#0ac4c5' }}>Enter any BRD Confluence Page Link:<span className="text-red-500 ml-1">*</span></Label>
                <span className="text-muted-foreground italic text-xs">Select BRD from Confluence panel</span>
              </div>
              <Input
                id="brdUpdateConfluenceLinkInput"
                type="text"
                placeholder="Enter BRD Confluence Page link..."
                value={finalBrdConfluenceLink}
                onChange={(e) => setFinalBrdConfluenceLink(e.target.value)}
                className="text-sm"
              />
            </div>

            {/* Chat/Upload choice — shown when no mode selected yet */}
            {!brdUpdateMode && (
              <div className="flex gap-2 mt-2">
                <Button
                  onClick={() => setBrdUpdateMode('chat')}
                  disabled={!finalBrdConfluenceLink.trim()}
                  variant="outline"
                  className="text-xs px-4 py-1.5 h-8 transition-all duration-300 flex items-center gap-1.5"
                  style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
                >
                  <Send className="w-3 h-3" /> Describe via Chat
                </Button>
                <Button
                  onClick={() => setBrdUpdateMode('upload')}
                  disabled={!finalBrdConfluenceLink.trim()}
                  variant="outline"
                  className="text-xs px-4 py-1.5 h-8 transition-all duration-300 flex items-center gap-1.5"
                  style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
                >
                  <Upload className="w-3 h-3" /> Upload Document
                </Button>
              </div>
            )}

            {/* Chat mode — text area for update instructions */}
            {brdUpdateMode === 'chat' && (
              <>
                <div className="embedded-input-group mt-2">
                  <Label htmlFor="brdUpdateChatInput" className="text-xs mb-1" style={{ color: '#0ac4c5' }}>Update Instructions:</Label>
                  <textarea
                    id="brdUpdateChatInput"
                    placeholder="Describe the changes you want to make to the BRD..."
                    value={brdUpdateInstructions}
                    onChange={(e) => setBrdUpdateInstructions(e.target.value)}
                    className="w-full text-sm rounded-md border px-3 py-2 min-h-[80px] resize-y"
                    style={{ background: 'var(--chatbot-input-bg)', color: 'var(--chatbot-text)', borderColor: 'var(--chatbot-border)' }}
                  />
                </div>
                <div className="flex gap-2 mt-2">
                  <Button
                    onClick={handleBrdUpdate}
                    disabled={isLoading || !brdUpdateInstructions.trim()}
                    variant="outline"
                    className="text-xs px-4 py-1.5 h-8 transition-all duration-300"
                    style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
                  >
                    {isLoading ? (
                      <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Updating BRD...</>
                    ) : (
                      'Proceed'
                    )}
                  </Button>
                  <Button
                    onClick={() => { setBrdUpdateMode(null); }}
                    disabled={isLoading}
                    variant="ghost"
                    className="text-xs px-3 py-1.5 h-8"
                  >
                    Back
                  </Button>
                </div>
              </>
            )}

            {/* Upload mode — file upload for update content */}
            {brdUpdateMode === 'upload' && (
              <>
                <div className="embedded-input-group mt-2">
                  <Label htmlFor="brdUpdateFile" className="text-xs mb-1" style={{ color: '#0ac4c5' }}>Upload Update Document:</Label>
                  <div className="flex flex-col gap-2">
                    <input
                      ref={brdFileInputRef}
                      type="file"
                      id="brdUpdateFile"
                      multiple
                      onChange={(e) => {
                        const newFiles = Array.from(e.target.files || []);
                        setBrdFiles(prev => [...prev, ...newFiles]);
                        if (brdFileInputRef.current) brdFileInputRef.current.value = '';
                      }}
                      className="hidden"
                    />
                    <div
                      className="flex flex-col items-center justify-center gap-2 rounded-lg cursor-pointer transition-colors"
                      style={{
                        border: '2px dashed rgba(52, 152, 179, 0.4)',
                        background: 'rgba(52, 152, 179, 0.05)',
                        padding: brdFiles.length > 0 ? '8px 12px' : '16px 12px',
                      }}
                      onClick={() => brdFileInputRef.current?.click()}
                      onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); e.currentTarget.style.borderColor = '#3498B3'; e.currentTarget.style.background = 'rgba(52, 152, 179, 0.12)'; }}
                      onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); e.currentTarget.style.borderColor = 'rgba(52, 152, 179, 0.4)'; e.currentTarget.style.background = 'rgba(52, 152, 179, 0.05)'; }}
                      onDrop={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        e.currentTarget.style.borderColor = 'rgba(52, 152, 179, 0.4)';
                        e.currentTarget.style.background = 'rgba(52, 152, 179, 0.05)';
                        const droppedFiles = Array.from(e.dataTransfer.files);
                        if (droppedFiles.length > 0) setBrdFiles(prev => [...prev, ...droppedFiles]);
                      }}
                    >
                      {brdFiles.length === 0 ? (
                        <>
                          <Upload className="w-5 h-5" style={{ color: '#3498B3' }} />
                          <span className="text-xs" style={{ color: '#3498B3' }}>Drag & drop files here or click to browse</span>
                        </>
                      ) : (
                        <>
                          <div className="flex flex-wrap items-center gap-2 w-full">
                            {brdFiles.map((file, index) => (
                              <div key={index} className="flex items-center gap-1 px-2 py-1 rounded text-xs" style={{ background: 'rgba(52, 152, 179, 0.15)', color: 'var(--chatbot-text)' }}>
                                <span>{file.name}</span>
                                <button
                                  type="button"
                                  onClick={(e) => { e.stopPropagation(); setBrdFiles(prev => prev.filter((_, i) => i !== index)); }}
                                  className="text-red-500 hover:text-red-700 ml-1"
                                >
                                  &times;
                                </button>
                              </div>
                            ))}
                          </div>
                          <span className="text-xs" style={{ color: 'rgba(52, 152, 179, 0.7)' }}>Drop more files or click to add</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex gap-2 mt-2">
                  <Button
                    onClick={handleBrdUpdate}
                    disabled={isLoading || brdFiles.length === 0}
                    variant="outline"
                    className="text-xs px-4 py-1.5 h-8 transition-all duration-300"
                    style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
                  >
                    {isLoading ? (
                      <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Updating BRD...</>
                    ) : (
                      'Proceed'
                    )}
                  </Button>
                  <Button
                    onClick={() => { setBrdUpdateMode(null); setBrdFiles([]); if (brdFileInputRef.current) brdFileInputRef.current.value = ''; }}
                    disabled={isLoading}
                    variant="ghost"
                    className="text-xs px-3 py-1.5 h-8"
                  >
                    Back
                  </Button>
                </div>
              </>
            )}
          </>
        )}
        {/* Show BRD flow: conversational choice → Create New or Update Existing */}
        {nextagentflow === 'confirmedCreateBrd' && !brdFlowChoice && (
          <div className="flex gap-2 mt-2">
            <Button
              onClick={() => {
                addMessage('I want to create a new BRD.', 'user');
                addMessage('Great! Please review the project configuration and upload your transcript to generate a new BRD.', 'bot');
                setBrdFlowChoice('create');
              }}
              variant="outline"
              className="text-xs px-4 py-1.5 h-8 transition-all duration-300 flex items-center gap-1.5"
              style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
            >
              <Sparkles className="w-3 h-3" /> Create New BRD
            </Button>
            <Button
              onClick={() => {
                addMessage('I want to update an existing BRD.', 'user');
                addMessage('Sure! Please provide the Confluence page link for the BRD you want to update.', 'bot');
                setFinalBrdConfluenceLink('');
                setBrdUpdateMode(null);
                setBrdUpdateInstructions('');
                setBrdFiles([]);
                if (brdFileInputRef.current) brdFileInputRef.current.value = '';
                setBrdFlowChoice('update');
              }}
              variant="outline"
              className="text-xs px-4 py-1.5 h-8 transition-all duration-300 flex items-center gap-1.5"
              style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
            >
              <Pencil className="w-3 h-3" /> Update Existing BRD
            </Button>
          </div>
        )}
        {/* Show BRD creation inputs for: confirmedCreateBrd with 'create' choice */}
        {nextagentflow === 'confirmedCreateBrd' && brdFlowChoice === 'create' && (
          <>
            {/* Project context from auth backend — with inline override for demos */}
            <div className="embedded-input-group">
              <div className={`text-xs space-y-1 p-2 rounded ${isProjectNameOverriddenRef.current ? 'border-amber-500/60 border' : ''} ${isDarkMode ? 'bg-slate-800/50 border border-slate-700' : 'bg-slate-100 border border-slate-300'}`}
                   style={isProjectNameOverriddenRef.current ? { borderColor: 'rgba(245, 158, 11, 0.6)' } : undefined}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium flex items-center gap-1.5" style={{ color: '#1bc3bd' }}>Project Configuration</span>
                  {isProjectNameOverriddenRef.current && (
                    <span className="text-[10px] text-amber-500 italic">session override</span>
                  )}
                </div>
                {(!projectName || !brdStakeholders[0]?.name || !brdStakeholders[0]?.email) && (
                  <p className="text-red-400 italic mb-1">Project details not available — check project settings in Admin panel</p>
                )}
                <div className="flex gap-2 items-center">
                  <span className={isDarkMode ? 'text-slate-400' : 'text-slate-500'}>Project Name:</span>
                  {isEditingProjectName ? (
                    <div className="flex items-center gap-1.5 flex-1">
                      <input
                        type="text"
                        value={projectName}
                        onChange={(e) => {
                          setProjectName(e.target.value);
                          isProjectNameOverriddenRef.current = true;
                          sessionStorage.setItem('projectName', e.target.value);
                        }}
                        onKeyDown={(e) => { if (e.key === 'Enter') setIsEditingProjectName(false); }}
                        autoFocus
                        className={`text-xs px-1.5 py-0.5 rounded border flex-1 min-w-0 ${isDarkMode ? 'bg-slate-700 border-amber-500/50 text-white' : 'bg-white border-amber-400 text-gray-900'}`}
                        style={{ maxWidth: '200px' }}
                      />
                      <button
                        onClick={() => setIsEditingProjectName(false)}
                        className="text-green-500 hover:text-green-400"
                        title="Confirm"
                      >
                        <Check className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => {
                          setProjectName(externalProjectName || '');
                          sessionStorage.setItem('projectName', externalProjectName || '');
                          isProjectNameOverriddenRef.current = false;
                          setIsEditingProjectName(false);
                        }}
                        className="text-amber-500 hover:text-amber-400"
                        title="Reset to project default"
                      >
                        <RotateCcw className="w-3 h-3" />
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5">
                      <span className={`font-medium ${projectName ? (isDarkMode ? 'text-white' : 'text-gray-900') : 'text-red-400 italic'}`}>{projectName || 'Not set'}</span>
                      <button
                        onClick={() => setIsEditingProjectName(true)}
                        className={`${isDarkMode ? 'text-slate-400 hover:text-white' : 'text-slate-400 hover:text-gray-700'} transition-colors`}
                        title="Edit project name for this session"
                      >
                        <Pencil className="w-2.5 h-2.5" />
                      </button>
                      {isProjectNameOverriddenRef.current && (
                        <button
                          onClick={() => {
                            setProjectName(externalProjectName || '');
                            sessionStorage.setItem('projectName', externalProjectName || '');
                            isProjectNameOverriddenRef.current = false;
                          }}
                          className="text-amber-500 hover:text-amber-400 transition-colors"
                          title="Reset to project default"
                        >
                          <RotateCcw className="w-2.5 h-2.5" />
                        </button>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <span className={isDarkMode ? 'text-slate-400' : 'text-slate-500'}>Product Owner:</span>
                  <span className={`font-medium ${brdStakeholders[0]?.name ? (isDarkMode ? 'text-white' : 'text-gray-900') : 'text-red-400 italic'}`}>{brdStakeholders[0]?.name || 'Not set'}</span>
                </div>
                <div className="flex gap-2">
                  <span className={isDarkMode ? 'text-slate-400' : 'text-slate-500'}>Email:</span>
                  <span className={`font-medium ${brdStakeholders[0]?.email ? (isDarkMode ? 'text-white' : 'text-gray-900') : 'text-red-400 italic'}`}>{brdStakeholders[0]?.email || 'Not set'}</span>
                </div>
              </div>
            </div>

            <div className="embedded-input-group">
              <Label htmlFor="brdFile" className="text-xs mb-1" style={{ color: '#0ac4c5' }}>Transcript{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
              <div className="flex flex-col gap-2">
                <input
                  ref={brdFileInputRef}
                  type="file"
                  id="brdFile"
                  multiple
                  onChange={(e) => {
                    const newFiles = Array.from(e.target.files || []);
                    setBrdFiles(prev => [...prev, ...newFiles]);
                    if (brdFileInputRef.current) {
                      brdFileInputRef.current.value = '';
                    }
                  }}
                  className="hidden"
                />
                <div
                  className="flex flex-col items-center justify-center gap-2 rounded-lg cursor-pointer transition-colors"
                  style={{
                    border: '2px dashed rgba(52, 152, 179, 0.4)',
                    background: 'rgba(52, 152, 179, 0.05)',
                    padding: brdFiles.length > 0 ? '8px 12px' : '16px 12px',
                  }}
                  onClick={() => brdFileInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); e.currentTarget.style.borderColor = '#3498B3'; e.currentTarget.style.background = 'rgba(52, 152, 179, 0.12)'; }}
                  onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); e.currentTarget.style.borderColor = 'rgba(52, 152, 179, 0.4)'; e.currentTarget.style.background = 'rgba(52, 152, 179, 0.05)'; }}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    e.currentTarget.style.borderColor = 'rgba(52, 152, 179, 0.4)';
                    e.currentTarget.style.background = 'rgba(52, 152, 179, 0.05)';
                    const droppedFiles = Array.from(e.dataTransfer.files);
                    if (droppedFiles.length > 0) {
                      setBrdFiles(prev => [...prev, ...droppedFiles]);
                    }
                  }}
                >
                  {brdFiles.length === 0 ? (
                    <>
                      <Upload className="w-5 h-5" style={{ color: '#3498B3' }} />
                      <span className="text-xs" style={{ color: '#3498B3' }}>Drag & drop files here or click to browse</span>
                    </>
                  ) : (
                    <>
                      <div className="flex flex-wrap items-center gap-2 w-full">
                        {brdFiles.map((file, index) => (
                          <div key={index} className="flex items-center gap-1 px-2 py-1 rounded text-xs" style={{ background: 'rgba(52, 152, 179, 0.15)', color: 'var(--chatbot-text)' }}>
                            <span>{file.name}</span>
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); setBrdFiles(prev => prev.filter((_, i) => i !== index)); }}
                              className="text-red-500 hover:text-red-700 ml-1"
                            >
                              &times;
                            </button>
                          </div>
                        ))}
                      </div>
                      <span className="text-xs" style={{ color: 'rgba(52, 152, 179, 0.7)' }}>Drop more files or click to add</span>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Proceed button – conditionally calls BRD generation or Analyze */}
            <div className="flex justify-start mt-2">
              {nextagentflow === 'confirmedCreateBrd' ? (
                <Button
                  onClick={handleBrdGeneration}
                  disabled={
                    isLoading ||
                    !projectName.trim() ||
                    !brdStakeholders[0]?.name.trim() ||
                    !brdStakeholders[0]?.email.trim() ||
                    brdFiles.length === 0
                  }
                  variant="outline"
                  className="text-xs px-4 py-1.5 h-8 transition-all duration-300"
                  style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
                >
                  {isLoading ? (
                    <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Processing...</>
                  ) : (
                    'Proceed'
                  )}
                </Button>
              ) : (
                <Button
                  onClick={handleAnalyze}
                  disabled={
                    isLoading ||
                    !projectName.trim() ||
                    !brdStakeholders[0]?.name.trim() ||
                    !brdStakeholders[0]?.email.trim() ||
                    brdFiles.length === 0
                  }
                  variant="outline"
                  className="text-xs px-4 py-1.5 h-8 transition-all duration-300"
                  style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
                >
                  {isLoading ? (
                    <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Processing...</>
                  ) : (
                    'Proceed'
                  )}
                </Button>
              )}
            </div>
          </>
        )}

        {/* Show testE2EInput, testE2EUserStoryName, testEtoEInstrauctions for: confirmedEndToEndTest */}
        {nextagentflow === 'confirmedEndToEndTest' && (
          <>
            <div className="embedded-input-group">
              <Label htmlFor="inputTestTextE2E" className="text-xs mb-1">Input Test Text{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
              <textarea
                id="inputTestTextE2E"
                placeholder="Enter input test text..."
                value={inputTestTextE2E}
                onChange={(e) => setInputTestTextE2E(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 text-sm border border-border rounded-md bg-background text-foreground resize-none focus:outline-none focus:ring-2 focus:ring-[#3498B3]"
              />
            </div>

            <div className="embedded-input-group">
              <Label htmlFor="instructionsE2E" className="text-xs mb-1">Instructions{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
              <textarea
                id="instructionsE2E"
                placeholder="Enter instructions..."
                value={instructionsE2E}
                onChange={(e) => setInstructionsE2E(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 text-sm border border-border rounded-md bg-background text-foreground resize-none focus:outline-none focus:ring-2 focus:ring-[#3498B3]"
              />
            </div>

            <div className="embedded-input-group">
              <Label htmlFor="userStoryNameE2E" className="text-xs mb-1">User Story Name{nextagentflow && <span className="text-red-500 ml-1">*</span>}</Label>
              <textarea
                id="userStoryNameE2E"
                placeholder="Enter user story name..."
                value={userStoryNameE2E}
                onChange={(e) => setUserStoryNameE2E(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 text-sm border border-border rounded-md bg-background text-foreground resize-none focus:outline-none focus:ring-2 focus:ring-[#3498B3]"
              />
            </div>
          </>
        )}

        {/* ---- Code Assistant: Project Configuration (before lock) ---- */}
        {nextagentflow === 'confirmedCodeAssistant' && codeAssistantActive && !codeAssistantLocked && (
          <>
            <div className="embedded-input-group">
              <div className={`px-3 py-2.5 rounded-lg ${isDarkMode ? 'bg-slate-800/60 border border-slate-700/80' : 'bg-slate-50 border border-slate-200'}`} style={{ fontSize: '12px' }}>
                {/* Header row with title + settings icon */}
                <div className="flex items-center justify-between" style={{ marginBottom: '10px' }}>
                  <span className="font-semibold" style={{ color: '#3498B3', fontSize: '13px' }}>Configuration Summary</span>
                  <button
                    onClick={() => onOpenProjectSettings?.()}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded font-medium transition-colors hover:bg-[#3498B3]/10"
                    style={{ color: '#3498B3', fontSize: '11px' }}
                    title="Edit in Project Settings"
                  >
                    <Settings className="w-3.5 h-3.5" /> Edit
                  </button>
                </div>

                {/* 2-column layout: Left = Git + AI, Right = Repository */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>

                  {/* LEFT COLUMN */}
                  <div>
                    {/* Git Connection */}
                    <div style={{ marginBottom: '14px' }}>
                      <div className="flex items-center gap-2" style={{ marginBottom: '8px' }}>
                        <Link className="w-3.5 h-3.5" style={{ color: '#0ac4c5' }} />
                        <span className="font-medium" style={{ color: '#0ac4c5', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Git Connection</span>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '64px 1fr', rowGap: '6px', columnGap: '10px', paddingLeft: '20px', fontSize: '12px' }}>
                        <span className="text-muted-foreground">Repo</span>
                        <span className="font-medium truncate" style={{ fontFamily: "'Fira Code', monospace", minWidth: 0 }} title={caRepoRemoteUrl}>
                          {caRepoRemoteUrl ? (() => { try { const u = new URL(caRepoRemoteUrl); const parts = u.pathname.split('/').filter(Boolean); const proj = parts[parts.length - 1] || ''; const mid = parts.slice(0, -1).join('/'); return mid ? u.origin + '/...' + '/' + proj : caRepoRemoteUrl; } catch { return caRepoRemoteUrl; } })() : <span className="text-muted-foreground italic">Not set</span>}
                        </span>
                        <span className="text-muted-foreground">Token</span>
                        <span className="font-medium">{caGitToken ? '••••••••' : hasBackendGitToken ? '•••••••• (project)' : <span className="text-muted-foreground italic">Not set</span>}</span>
                        <span className="text-muted-foreground">User</span>
                        <span className="font-medium">{caGitUsername || <span className="text-muted-foreground italic">Not set</span>}</span>
                      </div>
                    </div>

                    {/* AI Settings */}
                    <div style={{ borderTop: isDarkMode ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)', paddingTop: '10px' }}>
                      <div className="flex items-center gap-2" style={{ marginBottom: '8px' }}>
                        <Sparkles className="w-3.5 h-3.5" style={{ color: '#0ac4c5' }} />
                        <span className="font-medium" style={{ color: '#0ac4c5', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>AI Settings</span>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '64px 1fr', rowGap: '6px', columnGap: '10px', paddingLeft: '20px', fontSize: '12px' }}>
                        <span className="text-muted-foreground">Model</span>
                        <span className="font-medium">{caModelOptions.find(m => m.value === caModel)?.label || caModel || 'Default'}</span>
                        <span className="text-muted-foreground">Autonomy</span>
                        <span className="font-medium capitalize">{caAutonomy}</span>
                        <span className="text-muted-foreground">Reasoning</span>
                        <span className="font-medium capitalize">{caReasoning}</span>
                      </div>
                    </div>
                  </div>

                  {/* RIGHT COLUMN */}
                  <div style={{ borderLeft: isDarkMode ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)', paddingLeft: '16px' }}>
                    {/* Repository */}
                    <div className="flex items-center gap-2" style={{ marginBottom: '10px' }}>
                      <Code2 className="w-3.5 h-3.5" style={{ color: '#0ac4c5' }} />
                      <span className="font-medium" style={{ color: '#0ac4c5', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Repository</span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '48px 1fr', rowGap: '10px', columnGap: '8px', paddingLeft: '20px', fontSize: '12px', alignItems: 'center' }}>
                      {/* Folder row */}
                      <span className="text-muted-foreground">Folder</span>
                      <div className="flex items-center" style={{ gap: '10px' }}>
                        <input
                          type="text"
                          value={caFolderName}
                          onChange={(e) => setCaFolderName(e.target.value)}
                          className="px-2 py-1 rounded border bg-background text-foreground focus:outline-none focus:border-[#3498B3] transition-colors"
                          style={{ fontFamily: "'Fira Code', monospace", fontSize: '11px', borderColor: isDarkMode ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.15)', width: '100px' }}
                        />
                        <div className="flex items-center" style={{ gap: '12px' }}>
                          <label className="flex items-center gap-1.5 cursor-pointer" style={{ fontSize: '11px' }}>
                            <input type="radio" name="caFolderModeChat" checked={caFolderMode === 'new'} onChange={() => setCaFolderMode('new')} className="accent-[#3498B3]" style={{ width: '13px', height: '13px' }} />
                            <span className={caFolderMode === 'new' ? 'text-green-400 font-medium' : 'text-muted-foreground'}>New</span>
                          </label>
                          <label className="flex items-center gap-1.5 cursor-pointer" style={{ fontSize: '11px' }}>
                            <input type="radio" name="caFolderModeChat" checked={caFolderMode === 'existing'} onChange={() => setCaFolderMode('existing')} className="accent-[#3498B3]" style={{ width: '13px', height: '13px' }} />
                            <span className={caFolderMode === 'existing' ? 'text-blue-400 font-medium' : 'text-muted-foreground'}>Existing</span>
                          </label>
                        </div>
                      </div>
                      {/* Branch row */}
                      <span className="text-muted-foreground">Branch</span>
                      <div className="flex items-center" style={{ gap: '10px' }}>
                        <input
                          type="text"
                          value={caBranchName}
                          onChange={(e) => setCaBranchName(e.target.value)}
                          className="px-2 py-1 rounded border bg-background text-foreground focus:outline-none focus:border-[#3498B3] transition-colors"
                          style={{ fontFamily: "'Fira Code', monospace", fontSize: '11px', borderColor: isDarkMode ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.15)', width: '100px' }}
                        />
                        <div className="flex items-center" style={{ gap: '12px' }}>
                          <label className="flex items-center gap-1.5 cursor-pointer" style={{ fontSize: '11px' }}>
                            <input type="radio" name="caLockModeChat" checked={caLockMode === 'new'} onChange={() => setCaLockMode('new')} className="accent-[#3498B3]" style={{ width: '13px', height: '13px' }} />
                            <span className={caLockMode === 'new' ? 'text-green-400 font-medium' : 'text-muted-foreground'}>New</span>
                          </label>
                          <label className="flex items-center gap-1.5 cursor-pointer" style={{ fontSize: '11px' }}>
                            <input type="radio" name="caLockModeChat" checked={caLockMode === 'existing'} onChange={() => setCaLockMode('existing')} className="accent-[#3498B3]" style={{ width: '13px', height: '13px' }} />
                            <span className={caLockMode === 'existing' ? 'text-blue-400 font-medium' : 'text-muted-foreground'}>Existing</span>
                          </label>
                        </div>
                      </div>
                    </div>
                  </div>

                </div>

                {/* Overwrite confirmation */}
                {caOverwriteConfirm && (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-md border border-amber-500/40 bg-amber-500/10" style={{ marginTop: '14px' }}>
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
                    <span className="text-amber-500" style={{ fontSize: '12px' }}>Local folder is out of sync. Click Proceed again to overwrite.</span>
                  </div>
                )}
              </div>
            </div>

            {/* Proceed + Close buttons */}
            <div className="flex items-center gap-2 mt-2">
              <Button
                onClick={handleCodeAssistantLock}
                disabled={caLocking || !caFolderName.trim() || !caBranchName.trim()}
                variant="outline"
                className="text-xs px-4 py-1.5 h-8 transition-all duration-300"
                style={{ borderColor: '#3498B3', color: '#3498B3', background: 'transparent' }}
              >
                {caLocking ? (
                  <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Locking...</>
                ) : (
                  <><Lock className="w-3.5 h-3.5 mr-1.5" /> Proceed</>
                )}
              </Button>
              <Button
                onClick={handleExitCodeAssistant}
                variant="outline"
                className="text-xs px-3 py-1.5 h-8 transition-all duration-300"
                style={{ borderColor: '#ef4444', color: '#ef4444', background: 'transparent' }}
              >
                <X className="w-3.5 h-3.5 mr-1" /> Close
              </Button>
            </div>
          </>
        )}

        {/* ---- Code Assistant: Repository Locked for Session (moved to sticky header) ---- */}

        </div>
        )}
        {/* end embedded-agent-fields */}
      </div>{/* end embedded-chat-messages */}

      {/* ---- Droid Terminal Panel ---- */}
      {droidTerminalVisible && (
        <DroidTerminal
          events={droidTerminalEvents}
          isActive={droidTerminalActive}
          isDarkMode={isDarkMode}
          onClose={() => setDroidTerminalVisible(false)}
        />
      )}

      {/* Input Section - sticky at bottom, single row */}
      <div className="embedded-input-section">
        <div className="embedded-input-row">
          <textarea
            id="userStory"
            placeholder="Enter your query here..."
            value={queryInputText}
            onChange={handleUserStoryChange}
            onKeyPress={handleKeyPress}
            onClick={() => setQueryInputText('')}
            rows={1}
            className="embedded-query-input"
            style={{ background: 'var(--chatbot-bg)', color: 'var(--chatbot-text)', border: '1px solid var(--chatbot-border)', fontFamily: 'inherit' }}
          />

          {/* Hide Analyze button when Save Validated User Story is shown */}
          {!(nextagentflow === 'intentOfUpdateUserStory' && validatedStories) && (
          <Button
            onClick={handleAnalyze}
            disabled={isLoading || !sessionId ||
              (!queryInputText.trim() && !createUserStoryText.trim() && !userStoryUri.trim() && !brdUri.trim()) ||
              (nextagentflow === 'confirmedCreateBrd' && brdFlowChoice === 'create' && (!projectName.trim() || !brdStakeholders[0]?.name.trim() || !brdStakeholders[0]?.email.trim() || brdFiles.length === 0)) ||
              (nextagentflow === 'confirmedCreateBrd' && brdFlowChoice === 'update' && (!finalBrdConfluenceLink.trim() || !brdUpdateMode || (brdUpdateMode === 'chat' && !brdUpdateInstructions.trim()) || (brdUpdateMode === 'upload' && brdFiles.length === 0))) ||
              (nextagentflow === 'confirmedBrdSummary' && !finalBrdConfluenceLink.trim())
            }
            className={`embedded-action-btn glossy-analyze-button transition-all duration-300 relative overflow-hidden ${
              isDarkMode
                ? 'bg-[#3498B3] hover:bg-[#2a7a99] text-white shadow-[0_4px_16px_rgba(52,152,179,0.4)] hover:shadow-[0_6px_24px_rgba(52,152,179,0.6)] border border-white/10'
                : 'bg-[#3498B3] hover:bg-[#2a7a99] text-white shadow-[0_2px_8px_rgba(52,152,179,0.25)] hover:shadow-[0_4px_16px_rgba(52,152,179,0.4)] border border-[#3498B3]/30'
            }`}
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
          )}
          {/* Save Validated User Story button â€” visible when intentOfUpdateUserStory */}
          {nextagentflow === 'intentOfUpdateUserStory' && validatedStories && (
            <Button
              onClick={handleSaveValidatedUserStory}
              disabled={isSavingValidatedStory}
              className={`embedded-action-btn glossy-analyze-button transition-all duration-300 relative overflow-hidden ${
                isDarkMode
                  ? 'bg-[#3498B3] hover:bg-[#2a7a99] text-white shadow-[0_4px_16px_rgba(52,152,179,0.4)] hover:shadow-[0_6px_24px_rgba(52,152,179,0.6)] border border-white/10'
                  : 'bg-[#3498B3] hover:bg-[#2a7a99] text-white shadow-[0_2px_8px_rgba(52,152,179,0.25)] hover:shadow-[0_4px_16px_rgba(52,152,179,0.4)] border border-[#3498B3]/30'
              }`}
            >
              {isSavingValidatedStory ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          )}
          <Button
            onClick={handleClear}
            variant="outline"
            className={`embedded-action-btn glossy-clear-button transition-all duration-300 relative overflow-hidden ${
              isDarkMode
                ? 'bg-[#3498B3] hover:bg-[#2a7a99] text-white shadow-[0_4px_16px_rgba(52,152,179,0.4)] hover:shadow-[0_6px_24px_rgba(52,152,179,0.6)] border border-white/10'
                : 'bg-[#3498B3] hover:bg-[#2a7a99] text-white shadow-[0_2px_8px_rgba(52,152,179,0.25)] hover:shadow-[0_4px_16px_rgba(52,152,179,0.4)] border border-[#3498B3]/30'
            }`}
          >
            <RotateCcw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* ---- Confirm Close Code Assistant Session Modal ---- */}
      <Dialog open={exitConfirmOpen} onOpenChange={setExitConfirmOpen}>
        <DialogContent
          className="!w-auto !max-w-[240px]"
          style={{
            background: isDarkMode ? '#0f1724' : '#ffffff',
            border: `1px solid ${isDarkMode ? '#1e2d3d' : '#e2e8f0'}`,
            boxShadow: isDarkMode
              ? '0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px rgba(52,152,179,0.15)'
              : '0 8px 32px rgba(0,0,0,0.15), 0 0 0 1px rgba(52,152,179,0.1)',
            padding: '16px 20px',
            borderRadius: '12px',
          }}
        >
          <DialogHeader style={{ borderBottom: `1px solid ${isDarkMode ? '#1e2d3d' : '#e2e8f0'}`, paddingBottom: '10px' }}>
            <DialogTitle style={{ color: isDarkMode ? '#f1f5f9' : '#0f172a', fontSize: '0.9rem', fontWeight: 600 }}>
              Code Assistant
            </DialogTitle>
          </DialogHeader>
          <div style={{ color: isDarkMode ? '#94a3b8' : '#475569', fontSize: '0.8rem', lineHeight: '1.5', padding: '8px 0 4px' }}>
            Do you want to close the Code Assistant session?
          </div>
          <DialogFooter style={{ gap: '8px', marginTop: '4px' }}>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setExitConfirmOpen(false)}
              style={{
                borderColor: isDarkMode ? '#1e2d3d' : '#e2e8f0',
                color: isDarkMode ? '#cbd5e1' : '#475569',
                background: 'transparent',
                fontSize: '0.8rem',
                height: '32px',
                padding: '0 14px',
              }}
            >
              No
            </Button>
            <Button
              size="sm"
              onClick={confirmExitCodeAssistant}
              style={{
                backgroundColor: '#ef4444',
                color: '#fff',
                border: 'none',
                fontSize: '0.8rem',
                height: '32px',
                padding: '0 14px',
              }}
            >
              Yes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
});

EmbeddedChatbot.displayName = 'EmbeddedChatbot';
