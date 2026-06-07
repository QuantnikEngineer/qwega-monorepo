import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import projectTeamConfig from '../constants/projectTeamConfig.json';
import projectConfigSettings from '../constants/projectConfigSettings.json';
  import { ArrowLeft, Send, Bot, FileText, ClipboardList, TestTube, Database, Library, Settings, Sparkles, User, Paperclip, X, File, Image as ImageIcon, Book, ChevronRight, ChevronDown, RefreshCw, Search, FolderOpen, FileIcon, Layers, BookOpen, Circle, Shield, Users, Wrench, ExternalLink, Plus, Minus, Trash2, Link2, Key, Check, MessageCircle, Pin, PinOff, PanelLeftClose, PanelLeftOpen, Clock, Filter, ListX, CodeXml, Brain, Zap, Globe, Upload, GitBranch, Code2, RotateCcw } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { ScrollArea } from './ui/scroll-area';
import { Separator } from './ui/separator';
import { Badge } from './ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Slider } from './ui/slider';
import { Switch } from './ui/switch';
import { EmbeddedChatbot, CHAT_STREAM_ENDPOINT } from './EmbeddedChatbot';
import { SDLCJourney } from './sdlc-journey/SDLCJourney';
import { PlanningDetail } from './sdlc-journey/PlanningDetail';
import { AnalysisDesignDetail } from './sdlc-journey/AnalysisDesignDetail';
import { BuildDetail } from './sdlc-journey/BuildDetail';
import { TestingDetail } from './sdlc-journey/TestingDetail';
import { DeploymentDetail } from './sdlc-journey/DeploymentDetail';
import { ReliabilityDetail } from './sdlc-journey/ReliabilityDetail';
import { SecurityDetail } from './sdlc-journey/SecurityDetail';
import { GovernanceDetail } from './sdlc-journey/GovernanceDetail';
import { Can } from '../auth/abilities';
import { useAuth } from '../auth/AuthContext';
import { useProjectToolConfig } from '../auth/useProjectToolConfig';
import { useProjects } from '../admin/hooks/useProjects';
import {
  fetchConfluenceSpaces,
  fetchConfluenceSpaceById,
  getConfiguredSpaceId,
  fetchConfluencePagesTree,
  fetchChildPages,
  setConfluenceConfig,
  confluenceBrowseUrl,
  type ConfluencePage as ConfluencePageType,
  type ConfluenceSpace,
} from '../services/confluenceApi';
import {
  fetchJiraProjects,
  fetchEpicsWithStories,
  fetchUserStoriesByEpic,
  fetchTestCasesByStory,
  fetchTestStepsByTestCase,
  searchJiraIssues,
  setJiraConfig,
  type JiraProject,
  type JiraIssue,
} from '../services/jiraApi';
import {
  fetchJobStatus,
  retryFailedStories,
  type CronJob,
  type CronJobStatus,
  type CronJobDetail,
} from '../services/cronJobApi';
import { apiFetch } from '../services/apiClient';

interface ExecuteProps {
  onBack: () => void;
  isDarkMode: boolean;
}

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  url: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  files?: UploadedFile[];
}

interface AIAgent {
  id: string;
  name: string;
  description: string;
  icon: any;
  color: string;
  active: boolean;
  children?: AIAgent[];
}

interface PromptTemplate {
  id: string;
  title: string;
  content: string;
  agentId: string;
  nextagentflow?: string;
}

interface WegaBrainPrompt {
  id: string;
  title: string;
  nextagentflow: string;
}

interface ConfluencePage {
  id: string;
  title: string;
  date: string;
  children?: ConfluencePage[];
  parentId?: string | null;
  parentType?: string | null;
  isFolder?: boolean;
}

interface AdminTeamMember {
  id: string;
  role: string;
  name: string;
  email: string;
}

interface AdminProjectDetails {
  name: string;
  location: string;
  technologies: string[];
}

interface DevOpsToolConfig {
  url: string;
  patToken: string;
  isConfigured: boolean;
  projectKey?: string;
  projectName?: string;
  spaceKey?: string;
  spaceName?: string;
  spaceId?: string;
  jiraBaseUrl?: string;
  jiraProjectKey?: string;
  qtestProjectId?: string;
}

interface DevOpsTool {
  id: string;
  name: string;
  icon: string;
  color: string;
  description: string;
}

const DEVOPS_TOOLS: DevOpsTool[] = projectConfigSettings.devopsTools.map(({ id, name, icon, color, description }) => ({
  id, name, icon, color, description
}));

export function Execute({ onBack, isDarkMode }: ExecuteProps) {
  const { user } = useAuth();
  const allowedAgentIds = user?.allowedAgents ?? [];

  // Fetch real project + members from auth backend
  const { data: projectsData } = useProjects();
  const myProject = useMemo(() => {
    const projects = projectsData?.projects ?? [];
    return projects.find((p: { id: string }) => p.id === user?.projectId) ?? projects[0];
  }, [projectsData, user?.projectId]);
  const myProjectId = myProject?.id ?? null;

  // Fetch project tool settings - use myProject.id as fallback when user.projectId is undefined
  const { tools: projectTools, isLoading: toolsLoading } = useProjectToolConfig(myProjectId);

  // Memoize harnessToolConfig to prevent infinite re-renders in EmbeddedChatbot
  const harnessToolConfig = useMemo(() => {
    const tool = projectTools['harness-repo'];
    if (!tool) return undefined;
    return { ready: tool.ready, config: tool.config, secretKeys: tool.secretKeys };
  }, [projectTools]);
  const [gatewayReady, setGatewayReady] = useState<boolean | null>(null);
  const [inputMessage, setInputMessage] = useState('');
  const [selectedLLM, setSelectedLLM] = useState('gpt-4');
  const [temperature, setTemperature] = useState([0.7]);
  const [maxTokens, setMaxTokens] = useState([2048]);
  const [enableStreaming, setEnableStreaming] = useState(true);
  const [attachedFiles, setAttachedFiles] = useState<UploadedFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatbotRef = useRef<any>(null);
  const [selectedPromptAgent, setSelectedPromptAgent] = useState<string>('all');
  const [expandedAgentId, setExpandedAgentId] = useState<string | null>(null);
  const [promptSearchFilter, setPromptSearchFilter] = useState<string>('');
  const [agentListCollapsed, setAgentListCollapsed] = useState<boolean>(false);
  const [selectedPromptForChatbot, setSelectedPromptForChatbot] = useState<string>('');
  const [selectedNextagentflowForChatbot, setSelectedNextagentflowForChatbot] = useState<string>('');
  // Accordion state: only one section can be expanded at a time. Default: 'promptLibrary'
  const [expandedSection, setExpandedSection] = useState<'agents' | 'promptLibrary' | 'confluence' | 'jira' | 'cronJobs' | 'wegaBrain' | null>('promptLibrary');
  const [currentNextagentflow, setCurrentNextagentflow] = useState<string>('');
  const [showOnboardingPopup, setShowOnboardingPopup] = useState(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  // Wega Brain: when ON, the RAG service also searches the non-critical KB.
  // Defaults to ON so Context Fabric uploads are always queryable regardless of classification.
  const [wegaBrainIncludeNonCritical, setWegaBrainIncludeNonCritical] = useState<boolean>(true);

  // SDLC Journey state
  const [selectedStage, setSelectedStage] = useState<string | null>(null);
  const [showStageModal, setShowStageModal] = useState(false);
  const [sdlcExpanded, setSdlcExpanded] = useState(false);

  const handleStageClick = (stageName: string) => {
    setSelectedStage(stageName);
    setShowStageModal(true);
  };

  const handleStageBack = () => {
    setSelectedStage(null);
    setShowStageModal(false);
  };

  const renderStageDetail = () => {
    switch (selectedStage) {
      case 'Planning':
        return <PlanningDetail onBack={handleStageBack} onStageClick={handleStageClick} currentStage="Planning" />;
      case 'Analysis & Design':
        return <AnalysisDesignDetail onBack={handleStageBack} onStageClick={handleStageClick} currentStage="Analysis & Design" />;
      case 'Build':
        return <BuildDetail onBack={handleStageBack} onStageClick={handleStageClick} currentStage="Build" />;
      case 'Testing':
        return <TestingDetail onBack={handleStageBack} onStageClick={handleStageClick} currentStage="Testing" />;
      case 'Deployment':
        return <DeploymentDetail onBack={handleStageBack} onStageClick={handleStageClick} currentStage="Deployment" />;
      case 'Reliability':
        return <ReliabilityDetail onBack={handleStageBack} onStageClick={handleStageClick} currentStage="Reliability" />;
      case 'Security':
        return <SecurityDetail onBack={handleStageBack} onStageClick={handleStageClick} currentStage="Security" />;
      case 'Governance':
        return <GovernanceDetail onBack={handleStageBack} onStageClick={handleStageClick} currentStage="Governance" />;
      default:
        return null;
    }
  };

  // Left sidebar collapse/expand state
  const [sidebarExpanded, setSidebarExpanded] = useState(false);

  // Confluence state
  const [confluenceSearch, setConfluenceSearch] = useState<string>('');
  const [selectedConfluencePages, setSelectedConfluencePages] = useState<Set<string>>(new Set());
  const [expandedConfluenceFolders, setExpandedConfluenceFolders] = useState<Set<string>>(new Set());
  const [confluenceFolderShowAll, setConfluenceFolderShowAll] = useState<Set<string>>(new Set());
  const [confluencePages, setConfluencePages] = useState<ConfluencePage[]>([]);
  const [confluenceSpaceName, setConfluenceSpaceName] = useState<string>(
    projectTools['confluence']?.config?.spaceName || ''
  );
  const [selectedSpaceKey, setSelectedSpaceKey] = useState<string>(
    projectTools['confluence']?.config?.spaceKey || ''
  );
  const [confluenceSpaces, setConfluenceSpaces] = useState<ConfluenceSpace[]>([]);
  const [confluenceLoading, setConfluenceLoading] = useState<boolean>(false);
  const [confluenceError, setConfluenceError] = useState<string>('');
  const [selectedConfluencePageUrl, setSelectedConfluencePageUrl] = useState<string>('');
  const CONFLUENCE_PAGES_PER_LOAD = 10;
  const [confluencePagePage, setConfluencePagePage] = useState<number>(1);

  // Jira state
  const [jiraSearch, setJiraSearch] = useState<string>('');
  const [selectedJiraIssues, setSelectedJiraIssues] = useState<Set<string>>(new Set());
  const [jiraSelectionLocked, setJiraSelectionLocked] = useState(false);
  const [expandedEpics, setExpandedEpics] = useState<Set<string>>(new Set());
  const [jiraEpics, setJiraEpics] = useState<JiraIssue[]>([]);
  const [jiraProjects, setJiraProjects] = useState<JiraProject[]>([]);
  const [selectedProjectKey, setSelectedProjectKey] = useState<string>('');
  const [jiraLoading, setJiraLoading] = useState<boolean>(false);
  const [jiraError, setJiraError] = useState<string>('');
  const JIRA_EPICS_PER_PAGE = 10;
  const [jiraEpicPage, setJiraEpicPage] = useState<number>(1);
  const [jiraSearchResults, setJiraSearchResults] = useState<JiraIssue[] | null>(null);
  const [jiraSearchLoading, setJiraSearchLoading] = useState(false);
  const jiraSearchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Test cases state (fetched from Jira, linked to stories)
  const [testCasesMap, setTestCasesMap] = useState<Record<string, JiraIssue[]>>({});
  const [testCasesLoading, setTestCasesLoading] = useState<Record<string, boolean>>({});
  const [selectedTestCaseKeys, setSelectedTestCaseKeys] = useState<Set<string>>(new Set());
  const [expandedStoryTestCases, setExpandedStoryTestCases] = useState<Set<string>>(new Set());
  // Test steps keyed by test case key
  const [testStepsMap, setTestStepsMap] = useState<Record<string, { Step: string; Expected: string }[]>>({});

  // Cron Job Status state — persisted in sessionStorage
  const [cronJobs, setCronJobs] = useState<CronJob[]>(() => {
    try {
      const stored = sessionStorage.getItem('cronJobs');
      return stored ? JSON.parse(stored) : [];
    } catch { return []; }
  });
  const [cronJobsLoading, setCronJobsLoading] = useState<Record<string, boolean>>({});
  const [expandedCronJob, setExpandedCronJob] = useState<string | null>(null);
  const [cronSectionExpanded, setCronSectionExpanded] = useState(true);

  // Admin Module state
  const [showTeamModal, setShowTeamModal] = useState(false);
  // Context Enrichment state
  const [contextEnrichUrls, setContextEnrichUrls] = useState<string[]>(['']);
  const [contextEnrichFiles, setContextEnrichFiles] = useState<File[]>([]);
  const [contextEnrichLoading, setContextEnrichLoading] = useState(false);
  const [contextEnrichProgress, setContextEnrichProgress] = useState(0);
  const [contextEnrichStatus, setContextEnrichStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [contextEnrichMessage, setContextEnrichMessage] = useState('');
  const contextEnrichFileInputRef = useRef<HTMLInputElement>(null);
  const [showContextEnrichModal, setShowContextEnrichModal] = useState(false);
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(false);
  const [isAISettingsOpen, setIsAISettingsOpen] = useState(false);
  const [expandedToolCategories, setExpandedToolCategories] = useState<Record<string, boolean>>({});
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});
  const [adminProjectDetails, setAdminProjectDetails] = useState<AdminProjectDetails>({
    name: projectTeamConfig.projectDetails.defaults.name,
    location: projectTeamConfig.projectDetails.defaults.location,
    technologies: [...projectTeamConfig.projectDetails.defaults.technologies],
  });
  const [adminTechInput, setAdminTechInput] = useState('');
  const [adminTeamMembers, setAdminTeamMembers] = useState<AdminTeamMember[]>(
    projectTeamConfig.teamMembers.defaultMembers.map(m => ({ ...m }))
  );
  // Legacy devopsConfigs removed — all tool config now comes from backend via useProjectToolConfig()
  const devopsConfigs: Record<string, DevOpsToolConfig> = {};
  const [showPatToken, setShowPatToken] = useState<Record<string, boolean>>({});
  const [contextFabricUrl, setContextFabricUrl] = useState('');
  const [contextFabricFiles, setContextFabricFiles] = useState<File[]>([]);
  const contextFabricFileInputRef = useRef<HTMLInputElement>(null);
  const [contextFabricStatus, setContextFabricStatus] = useState<{ state: 'idle' | 'loading' | 'success' | 'error'; message: string }>({ state: 'idle', message: '' });
  const [teamValidationErrors, setTeamValidationErrors] = useState<Record<string, string[]>>({});
  const [teamSaveError, setTeamSaveError] = useState<string>('');

  // Code Assistant Configuration state — prefer backend tool config, fallback to static defaults
  const backendHarness = projectTools['harness-repo'];
  const caDefaults = (projectConfigSettings as any).codeAssistant;
  const [caRepoUrl, setCaRepoUrl] = useState('');
  const [caGitToken, setCaGitToken] = useState('');
  const [caGitUsername, setCaGitUsername] = useState(caDefaults?.gitConnection?.fields?.gitUsername?.defaultValue || 'git');
  const [caFolderName, setCaFolderName] = useState(caDefaults?.repoConfig?.fields?.folderName?.defaultValue || '');
  const [caFolderMode, setCaFolderMode] = useState<'new' | 'existing'>(caDefaults?.repoConfig?.fields?.folderMode?.defaultValue || 'new');
  const [caBranchName, setCaBranchName] = useState(caDefaults?.repoConfig?.fields?.branchName?.defaultValue || '');
  const [caBranchMode, setCaBranchMode] = useState<'new' | 'existing'>(caDefaults?.repoConfig?.fields?.branchMode?.defaultValue || 'new');
  const [caModel, setCaModel] = useState(caDefaults?.aiSettings?.fields?.model?.defaultValue || 'gpt-5.2-codex');
  const [caAutonomy, setCaAutonomy] = useState<'high' | 'medium' | 'low'>(caDefaults?.aiSettings?.fields?.autonomy?.defaultValue || 'high');
  const [caReasoning, setCaReasoning] = useState<'high' | 'medium' | 'low'>(caDefaults?.aiSettings?.fields?.reasoning?.defaultValue || 'high');
  const [caConfigSaved, setCaConfigSaved] = useState(false);
  const [showCaGitToken, setShowCaGitToken] = useState(false);
  // Track if harness-repo has a stored PAT token (secrets are write-only, not returned)
  const caHasStoredToken = backendHarness?.secretKeys?.includes('patToken') ?? false;

  // Sync Code Assistant git fields when backend harness-repo config loads
  useEffect(() => {
    if (backendHarness?.ready && backendHarness.config) {
      const cfg = backendHarness.config;
      if (cfg.url) setCaRepoUrl(cfg.url);
    }
  }, [backendHarness]);

  const [configJiraProjects, setConfigJiraProjects] = useState<JiraProject[]>([]);
  const [configJiraProjectsLoading, setConfigJiraProjectsLoading] = useState(false);
  // Refs for smooth accordion height animation
  const promptLibraryRef = useRef<HTMLDivElement>(null);
  const confluenceRef = useRef<HTMLDivElement>(null);
  const jiraRef = useRef<HTMLDivElement>(null);
  const [sectionHeights, setSectionHeights] = useState<Record<string, number>>({ promptLibrary: 0, confluence: 0, jira: 0 });

  // Measure section heights whenever expandedSection or content changes
  useEffect(() => {
    const refs: Record<string, React.RefObject<HTMLDivElement | null>> = {
      promptLibrary: promptLibraryRef,
      confluence: confluenceRef,
      jira: jiraRef,
    };
    const newHeights: Record<string, number> = {};
    for (const key of Object.keys(refs)) {
      const el = refs[key].current;
      if (el) {
        newHeights[key] = el.scrollHeight;
      }
    }
    setSectionHeights(prev => ({ ...prev, ...newHeights }));
  }, [expandedSection, confluencePages, confluenceLoading, confluenceError, confluenceSearch, jiraEpics, jiraLoading, jiraError, jiraSearch, selectedPromptAgent, expandedAgentId, expandedConfluenceFolders, expandedEpics, selectedConfluencePages, selectedJiraIssues]);

  // Derive project details + team members from auth backend (reactive — updates on data change)
  // Stable references for useEffect dependencies
  const myProjectName = myProject?.name;
  const userId = user?.id;
  const userDisplayName = user?.displayName;
  const userEmail = user?.email;
  const userRoles = user?.roles;

  useEffect(() => {
    if (!myProjectName) return;
    setAdminProjectDetails(prev => {
      if (prev.name === myProjectName) return prev;
      return { ...prev, name: myProjectName };
    });
  }, [myProjectName]);

  // NOTE (WEGA-2002): adminTeamMembers holds BUSINESS stakeholders for BRD agent use —
  // initialized from projectTeamConfig.json defaults. We do NOT overwrite them with
  // auth-service platform RBAC members. Platform team management is via AdminFAB → ManageUsersSheet.

  // Restore stakeholders from sessionStorage when project name is known
  useEffect(() => {
    const projName = myProjectName;
    if (!projName) return;
    const stored = sessionStorage.getItem(`brdStakeholders_${projName}`);
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setAdminTeamMembers(parsed.map((s: { name: string; role: string; email: string }, i: number) => ({
            id: adminTeamMembers[i]?.id ?? `restored-${i}`,
            ...s
          })));
        }
      } catch { /* ignore corrupt data */ }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once when project name resolves
  }, [myProjectName]);


  const togglePatTokenVisibility = (toolId: string) => {
    setShowPatToken(prev => ({ ...prev, [toolId]: !prev[toolId] }));
  };

  const configureDevOpsTool = (_toolId: string) => {
    // Legacy — tool configuration now handled via AdminFAB → ProjectToolSettingsPanel
  };

  // Admin Module helper functions
  const addAdminTeamMember = () => {
    setAdminTeamMembers([...adminTeamMembers, { id: Date.now().toString(), role: '', name: '', email: '' }]);
  };

  const removeAdminTeamMember = (id: string) => {
    setAdminTeamMembers(adminTeamMembers.filter(m => m.id !== id));
  };

  const updateAdminTeamMember = (id: string, field: keyof AdminTeamMember, value: string) => {
    setAdminTeamMembers(adminTeamMembers.map(m => m.id === id ? { ...m, [field]: value } : m));
  };

  const isValidEmail = (email: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const saveAdminTeam = () => {
    const errors: Record<string, string[]> = {};

    adminTeamMembers.forEach((member) => {
      const memberErrors: string[] = [];
      const hasName = member.name.trim() !== '';
      const hasEmail = member.email.trim() !== '';
      const hasAnyField = hasName || hasEmail;
      const isMandatory = member.role === projectTeamConfig.teamMembers.mandatoryRole;

      if (isMandatory || hasAnyField) {
        if (!hasName) memberErrors.push('name');
        if (!hasEmail) {
          memberErrors.push('email');
        } else if (!isValidEmail(member.email.trim())) {
          memberErrors.push('emailInvalid');
        }
      }

      if (memberErrors.length > 0) {
        errors[member.id] = memberErrors;
      }
    });

    if (Object.keys(errors).length > 0) {
      setTeamValidationErrors(errors);
      const hasInvalidEmail = Object.values(errors).some(e => e.includes('emailInvalid'));
      const hasMissing = Object.values(errors).some(e => e.includes('name') || e.includes('email'));
      const messages: string[] = [];
      if (hasMissing) messages.push(projectTeamConfig.validation.missingFieldsError);
      if (hasInvalidEmail) messages.push(projectTeamConfig.validation.invalidEmailError);
      setTeamSaveError(messages.join(' '));
      return;
    }

    setTeamValidationErrors({});
    setTeamSaveError('');
    console.log('Saving team:', adminTeamMembers);
    setShowTeamModal(false);

    // Sync adminTeamMembers → brdStakeholders for BRD generation
    const mapped = adminTeamMembers
      .filter(m => m.name.trim() && m.email.trim())
      .map(m => ({ name: m.name, role: m.role, email: m.email }));
    if (mapped.length > 0) {
      setBrdStakeholders(mapped);
    }

    // Persist to sessionStorage keyed by project name
    const projName = myProjectName || derivedProjectName;
    if (projName) {
      sessionStorage.setItem(`brdStakeholders_${projName}`, JSON.stringify(
        adminTeamMembers.map(m => ({ name: m.name, role: m.role, email: m.email }))
      ));
    }
  };

  const addAdminTechnology = () => {
    if (adminTechInput.trim() && !adminProjectDetails.technologies.includes(adminTechInput.trim())) {
      setAdminProjectDetails({
        ...adminProjectDetails,
        technologies: [...adminProjectDetails.technologies, adminTechInput.trim()],
      });
      setAdminTechInput('');
    }
  };

  const removeAdminTechnology = (tech: string) => {
    setAdminProjectDetails({
      ...adminProjectDetails,
      technologies: adminProjectDetails.technologies.filter(t => t !== tech),
    });
  };

  // Pre-flight gateway health check — skip all external API calls when gateway is down
  useEffect(() => {
    const GATEWAY_URL = (import.meta.env.VITE_GATEWAY_URL || '').replace(/\/$/, '');
    fetch(`${GATEWAY_URL}/health`, { signal: AbortSignal.timeout(3000) })
      .then(r => setGatewayReady(r.ok))
      .catch(() => {
        console.debug('[Gateway] Not reachable — external API calls will be skipped');
        setGatewayReady(false);
      });
  }, []);

  // Push runtime config to API services when project tool settings load
  useEffect(() => {
    const jira = projectTools['jira'];
    if (jira?.ready) {
      setJiraConfig({
        baseUrl: jira.config.url,
        projectKey: jira.config.projectKey,
      });
    }
    const confluence = projectTools['confluence'];
    if (confluence?.ready) {
      setConfluenceConfig({
        spaceId: confluence.config.spaceId,
        spaceKey: confluence.config.spaceKey,
        baseUrl: confluence.config.url,
      });
    }
  }, [projectTools]);

  // Fetch Confluence space — only when gateway is available and tool is configured
  useEffect(() => {
    if (gatewayReady !== true) return;
    if (!isToolConfigured('confluence')) return;
    const loadSpace = async () => {
      try {
        const spaces = await fetchConfluenceSpaces();
        setConfluenceSpaces(spaces);
        const configuredSpaceId = getConfiguredSpaceId();
        // Use backend config spaceKey
        const configSpaceKey = projectTools['confluence']?.config?.spaceKey;
        if (configSpaceKey) {
          const matched = spaces.find(s => s.key === configSpaceKey);
          if (matched) {
            setConfluenceSpaceName(matched.name);
            setSelectedSpaceKey(matched.key);
          } else if (spaces.length > 0) {
            setConfluenceSpaceName(spaces[0].name);
            setSelectedSpaceKey(spaces[0].key);
          }
        } else if (configuredSpaceId) {
          // Fetch the specific space by ID
          const space = await fetchConfluenceSpaceById(configuredSpaceId);
          setConfluenceSpaceName(space.name);
          setSelectedSpaceKey(space.key);
        } else if (spaces.length > 0) {
          setConfluenceSpaceName(spaces[0].name);
          setSelectedSpaceKey(spaces[0].key);
        }
      } catch (err: any) {
        const msg = err?.message || String(err);
        if (msg.includes('401')) {
          console.debug('[Confluence] Auth not configured — skipping space load');
          setConfluenceError('Confluence credentials not configured. Update proxy settings to connect.');
        } else if (err instanceof TypeError || msg.includes('Failed to fetch') || msg.includes('502') || msg.includes('500')) {
          console.debug('[Confluence] Gateway unavailable — skipping space load');
          setConfluenceError('Service unavailable. Start the API gateway to connect.');
        } else {
          console.warn('Failed to load Confluence space:', err);
          setConfluenceError('Failed to load space. Check API credentials.');
        }
      }
    };
    loadSpace();
  }, [gatewayReady, projectTools]);

  // Fetch pages when selected space changes
  useEffect(() => {
    if (!selectedSpaceKey) return;
    if (!isToolConfigured('confluence')) return;
    loadConfluencePages(selectedSpaceKey);
  }, [selectedSpaceKey]);

  const loadConfluencePages = useCallback(async (spaceKey: string) => {
    setConfluenceLoading(true);
    setConfluenceError('');
    setConfluencePagePage(1);
    try {
      const pages = await fetchConfluencePagesTree(spaceKey);
      setConfluencePages(pages);
      // Auto-expand the first folder (or first page with children)
      const firstFolder = pages.find(p => p.isFolder || (p.children && p.children.length > 0));
      if (firstFolder) {
        setExpandedConfluenceFolders(new Set([firstFolder.id]));
      }
    } catch (err: any) {
      const msg = err?.message || String(err);
      if (msg.includes('401') || msg.includes('502') || msg.includes('500') || err instanceof TypeError) {
        console.debug('[Confluence] Pages load skipped — service/auth unavailable');
      } else {
        console.warn('Failed to load Confluence pages:', err);
      }
      setConfluenceError(msg.includes('401') ? 'Confluence credentials not configured.' : msg.includes('502') || msg.includes('500') || err instanceof TypeError ? 'Service unavailable.' : (err?.message || 'Failed to load pages'));
      setConfluencePages([]);
    } finally {
      setConfluenceLoading(false);
    }
  }, []);

  const handleConfluenceRefresh = () => {
    if (selectedSpaceKey) {
      loadConfluencePages(selectedSpaceKey);
    }
  };

  // After BRD generation, refresh Confluence and auto-select the newly created BRD page
  const handleBrdGenerated = useCallback(async (brdLink: string, brdProjectName: string) => {
    if (!selectedSpaceKey) return;
    try {
      // Extract page ID from the BRD confluence link (format: .../pages/{pageId}/...)
      const pageIdMatch = brdLink.match(/\/pages\/(\d+)/);
      const brdPageId = pageIdMatch ? pageIdMatch[1] : null;

      // Refresh the Confluence pages tree
      const pages = await fetchConfluencePagesTree(selectedSpaceKey);
      setConfluencePages(pages);

      if (brdPageId) {
        // Auto-select the newly created BRD page
        setSelectedConfluencePages(new Set([brdPageId]));
        setSelectedConfluencePageUrl(brdLink);

        // Expand the parent folder so the page is visible
        const parentFolder = pages.find(p =>
          p.children?.some(c => c.id === brdPageId)
        );
        if (parentFolder) {
          setExpandedConfluenceFolders(prev => {
            const next = new Set(prev);
            next.add(parentFolder.id);
            return next;
          });
        }

        // Expand the Confluence section in the sidebar so user can see it
        setExpandedSection('confluence');
      }
    } catch (err) {
      console.error('Failed to refresh Confluence after BRD generation:', err);
    }
  }, [selectedSpaceKey]);

  // After user story generation, refresh Jira and auto-select the generated epics
  const handleUserStoryGenerated = useCallback(async (epicKeys: string[]) => {
    if (!selectedProjectKey || epicKeys.length === 0) return;
    try {
      // Clear previous Jira selections (keep Confluence/BRD selection for validate flow)
      setSelectedJiraIssues(new Set());

      // Refresh the Jira epics tree
      const epics = await fetchEpicsWithStories(selectedProjectKey);
      setJiraEpics(epics);

      // Auto-expand and select stories under the generated epics
      const newExpanded = new Set<string>();
      const newSelected = new Set<string>();
      for (const epicKey of epicKeys) {
        const epic = epics.find(e => e.key === epicKey);
        if (epic) {
          newExpanded.add(epicKey);
          // Select all stories under this epic
          if (epic.children) {
            epic.children.forEach(story => newSelected.add(story.key));
          }
        }
      }
      // Replace expanded epics with only the newly generated ones
      setExpandedEpics(newExpanded);
      setSelectedJiraIssues(newSelected);

      // Simulate clicking "Validate User Story" prompt on the left panel:
      // activate the validator agent and set prompt text so user can manually click Analyze
      toggleAgent('user-story-validator');
      setSelectedPromptAgent('user-story-validator');
      setExpandedAgentId('user-story-validator');

      // Expand the Jira section in the sidebar so user can see the selection
      setExpandedSection('jira');
    } catch (err) {
      console.error('Failed to refresh Jira after user story generation:', err);
    }
  }, [selectedProjectKey]);

  // After validated user stories are saved, refresh Jira and auto-select all stories in the respective epics
  const handleValidatedUserStorySaved = useCallback(async (epicKeys: string[]) => {
    if (!selectedProjectKey || epicKeys.length === 0) return;

    const MAX_RETRIES = 3;
    const INITIAL_DELAY = 8000;

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        // Wait for Jira search index to catch up — longer on first attempt, shorter on retries
        const delay = attempt === 0 ? INITIAL_DELAY : 5000;
        await new Promise(resolve => setTimeout(resolve, delay));

        // Refresh the Jira epics tree
        const epics = await fetchEpicsWithStories(selectedProjectKey);

        // Verify that all expected epics have their children (stories) loaded
        const missingStories = epicKeys.some(ek => {
          const epic = epics.find(e => e.key === ek);
          return epic && !epic.children;
        });

        if (missingStories && attempt < MAX_RETRIES - 1) {
          console.warn(`Jira refresh attempt ${attempt + 1}: some epics still missing stories, retrying...`);
          continue;
        }

        setJiraEpics(epics);

        // Auto-expand and select all stories under the respective epics
        const newExpanded = new Set<string>();
        const newSelected = new Set<string>();
        for (const epicKey of epicKeys) {
          const epic = epics.find(e => e.key === epicKey);
          if (epic) {
            newExpanded.add(epicKey);
            if (epic.children) {
              epic.children.forEach(story => newSelected.add(story.key));
            }
          }
        }
        setExpandedEpics(newExpanded);
        setSelectedJiraIssues(newSelected);

        // Expand the Jira section so user can see the refreshed selection
        setExpandedSection('jira');
        break;
      } catch (err) {
        console.error(`Failed to refresh Jira (attempt ${attempt + 1}):`, err);
        if (attempt === MAX_RETRIES - 1) {
          console.error('All Jira refresh attempts failed');
        }
      }
    }
  }, [selectedProjectKey]);

  // Lazy-load children when expanding a folder that hasn't loaded them yet
  const toggleConfluenceFolder = async (folderId: string) => {
    // If collapsing, just toggle
    if (expandedConfluenceFolders.has(folderId)) {
      setExpandedConfluenceFolders(prev => {
        const next = new Set(prev);
        next.delete(folderId);
        return next;
      });
      return;
    }

    // If expanding and page has no children loaded yet, fetch them
    const page = confluencePages.find(p => p.id === folderId);
    if (page && !page.children) {
      try {
        const children = await fetchChildPages(folderId);
        if (children.length > 0) {
          setConfluencePages(prev =>
            prev.map(p => p.id === folderId ? { ...p, children } : p)
          );
        }
      } catch (err) {
        console.error('Failed to load child pages:', err);
      }
    }

    setExpandedConfluenceFolders(prev => {
      const next = new Set(prev);
      next.add(folderId);
      return next;
    });
  };

  const toggleConfluencePageSelection = (pageId: string, pageTitle?: string) => {
    const isCurrentlySelected = selectedConfluencePages.has(pageId);
    if (isCurrentlySelected) {
      // Unselect the page
      setSelectedConfluencePages(new Set());
      setSelectedConfluencePageUrl('');
    } else {
      // Single select: replace any previous selection with the new one
      setSelectedConfluencePages(new Set([pageId]));
      if (pageTitle) {
        const url = confluenceBrowseUrl(pageId, pageTitle, selectedSpaceKey);
        setSelectedConfluencePageUrl(url);
      }
    }
  };

  const filterConfluencePages = (pages: ConfluencePage[]): ConfluencePage[] => {
    if (!confluenceSearch.trim()) return pages;
    return pages.reduce<ConfluencePage[]>((acc, page) => {
      if (page.children) {
        const filteredChildren = page.children.filter(child =>
          child.title.toLowerCase().includes(confluenceSearch.toLowerCase())
        );
        if (filteredChildren.length > 0 || page.title.toLowerCase().includes(confluenceSearch.toLowerCase())) {
          acc.push({ ...page, children: filteredChildren.length > 0 ? filteredChildren : page.children });
        }
      } else if (page.title.toLowerCase().includes(confluenceSearch.toLowerCase())) {
        acc.push(page);
      }
      return acc;
    }, []);
  };

  // Fetch Jira projects — only when gateway is available and tool is configured
  useEffect(() => {
    if (gatewayReady !== true) return;
    if (!isToolConfigured('jira')) return;
    const loadProjects = async () => {
      try {
        const projects = await fetchJiraProjects();
        setJiraProjects(projects);
        if (projects.length > 0) {
          // Use backend config projectKey
          const configProjectKey = projectTools['jira']?.config?.projectKey;
          const matchedProject = configProjectKey ? projects.find(p => p.key === configProjectKey) : null;
          const projectKey = matchedProject ? matchedProject.key : projects[0].key;
          const project = projects.find(p => p.key === projectKey);
          setSelectedProjectKey(projectKey);
        }
      } catch (err: any) {
        const msg = err?.message || String(err);
        if (msg.includes('401')) {
          console.debug('[Jira] Auth not configured — skipping project load');
          setJiraError('Jira credentials not configured. Update proxy settings to connect.');
        } else if (err instanceof TypeError || msg.includes('Failed to fetch') || msg.includes('502') || msg.includes('500')) {
          console.debug('[Jira] Gateway unavailable — skipping project load');
          setJiraError('Service unavailable. Start the API gateway to connect.');
        } else {
          console.warn('Failed to load Jira projects:', err);
          setJiraError('Failed to load projects. Check API credentials.');
        }
      }
    };
    loadProjects();
  }, [gatewayReady, projectTools]);

  // Fetch epics when selected project changes
  useEffect(() => {
    if (!selectedProjectKey) return;
    if (!isToolConfigured('jira')) return;
    loadJiraEpics(selectedProjectKey);
  }, [selectedProjectKey]);

  const loadJiraEpics = useCallback(async (projectKey: string) => {
    setJiraLoading(true);
    setJiraError('');
    setJiraEpicPage(1);
    try {
      const epics = await fetchEpicsWithStories(projectKey);
      setJiraEpics(epics);
      if (epics.length > 0 && epics[0].children) {
        setExpandedEpics(new Set([epics[0].key]));
      }
    } catch (err: any) {
      const msg = err?.message || String(err);
      if (msg.includes('401') || msg.includes('502') || msg.includes('500') || err instanceof TypeError) {
        console.debug('[Jira] Epics load skipped — service/auth unavailable');
      } else {
        console.warn('Failed to load Jira epics:', err);
      }
      setJiraError(msg.includes('401') ? 'Jira credentials not configured.' : msg.includes('502') || msg.includes('500') || err instanceof TypeError ? 'Service unavailable.' : (err?.message || 'Failed to load epics'));
      setJiraEpics([]);
    } finally {
      setJiraLoading(false);
    }
  }, []);

  const handleJiraRefresh = () => {
    if (selectedProjectKey) {
      loadJiraEpics(selectedProjectKey);
    }
  };

  const toggleEpicExpand = async (epicKey: string) => {
    if (expandedEpics.has(epicKey)) {
      setExpandedEpics(prev => {
        const next = new Set(prev);
        next.delete(epicKey);
        return next;
      });
      return;
    }

    // Lazy-load stories if not yet loaded
    const epic = jiraEpics.find(e => e.key === epicKey);
    const searchEpic = jiraSearchResults?.find(e => e.key === epicKey);
    const targetEpic = epic || searchEpic;
    if (targetEpic && (!targetEpic.children || targetEpic.children.length === 0)) {
      try {
        const stories = await fetchUserStoriesByEpic(epicKey);
        if (stories.length > 0) {
          setJiraEpics(prev =>
            prev.map(e => e.key === epicKey ? { ...e, children: stories } : e)
          );
          // Also update search results if present
          setJiraSearchResults(prev =>
            prev ? prev.map(e => e.key === epicKey ? { ...e, children: stories } : e) : prev
          );
        }
      } catch (err) {
        console.error('Failed to load user stories:', err);
      }
    }

    setExpandedEpics(prev => {
      const next = new Set(prev);
      next.add(epicKey);
      return next;
    });
  };

  // Find which epic a story belongs to
  const findEpicForStory = (storyKey: string) => {
    return jiraEpics.find(e => e.children?.some(s => s.key === storyKey));
  };



  const toggleJiraIssueSelection = (issueKey: string) => {
    if (jiraSelectionLocked) return;
    setSelectedJiraIssues(prev => {
      if (prev.has(issueKey)) {
        // Deselect
        const next = new Set(prev);
        next.delete(issueKey);
        return next;
      }
      // Default: allow multiple epics and stories
      const next = new Set(prev);
      next.add(issueKey);
      return next;
    });
  };

  const toggleEpicSelection = (epicKey: string) => {
    if (jiraSelectionLocked) return;
    const epic = jiraEpics.find(e => e.key === epicKey);
    if (!epic?.children) return;
    const childKeys = epic.children.map(s => s.key);
    setSelectedJiraIssues(prev => {
      const allSelected = childKeys.every(k => prev.has(k));
      if (allSelected) {
        // Deselect all children of this epic, keep other epics' selections
        const next = new Set(prev);
        childKeys.forEach(k => next.delete(k));
        return next;
      } else {
        // Keep existing selections and add this epic's children
        const next = new Set(prev);
        childKeys.forEach(k => next.add(k));
        return next;
      }
    });
  };

  // Build the list of selected stories with full info (including parent epic) for the chatbot
  const selectedJiraStoriesForChatbot = useMemo(() => {
    const result: { id: string; key: string; url: string; summary: string; description: string; epicKey?: string; epicSummary?: string }[] = [];
    for (const epic of jiraEpics) {
      if (!epic.children) continue;
      for (const story of epic.children) {
        if (selectedJiraIssues.has(story.key)) {
          result.push({
            id: story.id,
            key: story.key,
            url: story.url,
            summary: story.summary,
            description: story.description || story.summary || '',
            epicKey: epic.key,
            epicSummary: epic.summary,
          });
        }
      }
    }
    return result;
  }, [selectedJiraIssues, jiraEpics]);

  const filterJiraEpics = (epics: JiraIssue[]): JiraIssue[] => {
    if (!jiraSearch.trim()) return epics;
    const q = jiraSearch.toLowerCase();
    return epics.reduce<JiraIssue[]>((acc, epic) => {
      if (epic.children) {
        const filteredChildren = epic.children.filter(child =>
          child.summary.toLowerCase().includes(q) || child.key.toLowerCase().includes(q)
        );
        if (filteredChildren.length > 0 || epic.summary.toLowerCase().includes(q) || epic.key.toLowerCase().includes(q)) {
          acc.push({ ...epic, children: filteredChildren.length > 0 ? filteredChildren : epic.children });
        }
      } else if (epic.summary.toLowerCase().includes(q) || epic.key.toLowerCase().includes(q)) {
        acc.push(epic);
      }
      return acc;
    }, []);
  };

  // Debounced Jira API search — triggers when user types in the search bar
  useEffect(() => {
    if (jiraSearchTimerRef.current) clearTimeout(jiraSearchTimerRef.current);
    const trimmed = jiraSearch.trim();
    if (!trimmed) {
      setJiraSearchResults(null);
      setJiraSearchLoading(false);
      return;
    }
    setJiraSearchLoading(true);
    jiraSearchTimerRef.current = setTimeout(async () => {
      try {
        const results = await searchJiraIssues(trimmed, selectedProjectKey || undefined);
        // Group results into epics with their stories as children
        const epicMap = new Map<string, JiraIssue>();
        const storyList: JiraIssue[] = [];
        for (const issue of results) {
          if (issue.issueType === 'Epic') {
            if (!epicMap.has(issue.key)) epicMap.set(issue.key, { ...issue, children: issue.children || [] });
          } else {
            storyList.push(issue);
          }
        }
        // Also include stories under their parent epics already loaded in jiraEpics
        for (const story of storyList) {
          const parentEpic = jiraEpics.find(e => e.children?.some(c => c.key === story.key));
          if (parentEpic) {
            if (!epicMap.has(parentEpic.key)) epicMap.set(parentEpic.key, { ...parentEpic, children: [] });
            const epic = epicMap.get(parentEpic.key)!;
            if (!epic.children?.some(c => c.key === story.key)) {
              epic.children = [...(epic.children || []), story];
            }
          } else {
            // Story without a known epic — show under a synthetic "Search Results" group
            const ungroupedKey = '__search_results__';
            if (!epicMap.has(ungroupedKey)) {
              epicMap.set(ungroupedKey, { id: ungroupedKey, key: ungroupedKey, summary: 'Search Results', status: '', issueType: 'Epic', updated: '', url: '', children: [] });
            }
            epicMap.get(ungroupedKey)!.children = [...(epicMap.get(ungroupedKey)!.children || []), story];
          }
        }
        setJiraSearchResults(Array.from(epicMap.values()));

        // Fetch user stories for epics that don't have children yet
        const epicsNeedingStories = Array.from(epicMap.values()).filter(
          e => e.issueType === 'Epic' && e.key !== '__search_results__' && (!e.children || e.children.length === 0)
        );
        if (epicsNeedingStories.length > 0) {
          const storyResults = await Promise.all(
            epicsNeedingStories.map(e => fetchUserStoriesByEpic(e.key).catch(() => [] as JiraIssue[]))
          );
          epicsNeedingStories.forEach((epic, i) => {
            if (storyResults[i].length > 0) {
              epicMap.set(epic.key, { ...epicMap.get(epic.key)!, children: storyResults[i] });
            }
          });
          setJiraSearchResults(Array.from(epicMap.values()));
        }

        // Auto-expand epics that have story results so user can see matched stories
        const epicsWithStories = Array.from(epicMap.values())
          .filter(e => e.children && e.children.length > 0)
          .map(e => e.key);
        if (epicsWithStories.length > 0) {
          setExpandedEpics(prev => {
            const next = new Set(prev);
            epicsWithStories.forEach(k => next.add(k));
            return next;
          });
        }
      } catch (err) {
        console.error('Jira search failed:', err);
        setJiraSearchResults([]);
      } finally {
        setJiraSearchLoading(false);
      }
    }, 500);
    return () => { if (jiraSearchTimerRef.current) clearTimeout(jiraSearchTimerRef.current); };
  }, [jiraSearch, selectedProjectKey, jiraEpics]);

  // Toggle expanding test cases dropdown for a story & fetch test cases from Jira
  const toggleStoryTestCases = async (storyKey: string) => {
    setExpandedStoryTestCases(prev => {
      const next = new Set(prev);
      if (next.has(storyKey)) {
        next.delete(storyKey);
      } else {
        next.add(storyKey);
      }
      return next;
    });
    // Fetch test cases from Jira if not already fetched
    if (!testCasesMap[storyKey] && !testCasesLoading[storyKey]) {
      setTestCasesLoading(prev => ({ ...prev, [storyKey]: true }));
      try {
        const testCases = await fetchTestCasesByStory(storyKey);
        setTestCasesMap(prev => ({ ...prev, [storyKey]: testCases }));
      } catch (err) {
        console.error('Failed to fetch test cases for', storyKey, err);
        setTestCasesMap(prev => ({ ...prev, [storyKey]: [] }));
      } finally {
        setTestCasesLoading(prev => ({ ...prev, [storyKey]: false }));
      }
    }
  };

  // When confirmedTestCaseToTestScript or confirmedTestDataGenerator is active and epics are selected,
  // auto-fetch test cases for all user stories under those epics and auto-select them all
  useEffect(() => {
    if (currentNextagentflow !== 'confirmedTestCaseToTestScript' && currentNextagentflow !== 'confirmedTestDataGenerator') return;
    if (selectedJiraIssues.size === 0) {
      // No stories selected — clear test case selections
      setSelectedTestCaseKeys(new Set());
      return;
    }

    // Gather all selected story keys that belong to selected epics
    const selectedStoryKeys: string[] = [];
    for (const epic of jiraEpics) {
      if (!epic.children) continue;
      for (const story of epic.children) {
        if (selectedJiraIssues.has(story.key)) {
          selectedStoryKeys.push(story.key);
        }
      }
    }
    if (selectedStoryKeys.length === 0) return;

    // Auto-expand and fetch test cases for every selected story
    const fetchAndSelect = async () => {
      const newTestCases: Record<string, JiraIssue[]> = {};
      const allTcKeys = new Set<string>();

      await Promise.all(
        selectedStoryKeys.map(async (storyKey) => {
          // Expand the test-case section in the left panel
          setExpandedStoryTestCases(prev => { const next = new Set(prev); next.add(storyKey); return next; });

          let tcs = testCasesMap[storyKey];
          if (!tcs && !testCasesLoading[storyKey]) {
            setTestCasesLoading(prev => ({ ...prev, [storyKey]: true }));
            try {
              tcs = await fetchTestCasesByStory(storyKey);
              newTestCases[storyKey] = tcs;
            } catch (err) {
              console.error('Auto-fetch test cases failed for', storyKey, err);
              newTestCases[storyKey] = [];
              tcs = [];
            } finally {
              setTestCasesLoading(prev => ({ ...prev, [storyKey]: false }));
            }
          }
          if (tcs) {
            tcs.forEach(tc => allTcKeys.add(tc.key));
          }
        })
      );

      // Merge newly fetched test cases into testCasesMap
      if (Object.keys(newTestCases).length > 0) {
        setTestCasesMap(prev => ({ ...prev, ...newTestCases }));
      }

      // Also include test cases that were already in the map for selected stories
      for (const storyKey of selectedStoryKeys) {
        const existing = testCasesMap[storyKey];
        if (existing) {
          existing.forEach(tc => allTcKeys.add(tc.key));
        }
      }

      // Auto-select ALL test cases across the selected stories
      setSelectedTestCaseKeys(allTcKeys);
    };

    fetchAndSelect();
  }, [currentNextagentflow, selectedJiraIssues, jiraEpics]);

  // Toggle test case selection for the chatbot
  // Multi-select when confirmedTestCaseToTestScript or confirmedTestDataGenerator, single-select otherwise
  const toggleTestCaseSelection = (tcKey: string) => {
    if (currentNextagentflow === 'confirmedTestCaseToTestScript' || currentNextagentflow === 'confirmedTestDataGenerator') {
      // Multi-select: toggle individual test case
      setSelectedTestCaseKeys(prev => {
        const next = new Set(prev);
        if (next.has(tcKey)) {
          next.delete(tcKey);
        } else {
          next.add(tcKey);
        }
        return next;
      });
    } else {
      // Single-select for other flows
      setSelectedTestCaseKeys(prev => {
        if (prev.has(tcKey)) {
          return new Set<string>();
        }
        return new Set<string>([tcKey]);
      });
    }
  };

  // Toggle all test cases for a specific story (select all / deselect all)
  const toggleAllTestCasesForStory = (storyKey: string) => {
    const tcs = testCasesMap[storyKey];
    if (!tcs || tcs.length === 0) return;
    const tcKeys = tcs.map(tc => tc.key);
    const allSelected = tcKeys.every(k => selectedTestCaseKeys.has(k));
    setSelectedTestCaseKeys(prev => {
      const next = new Set(prev);
      if (allSelected) {
        tcKeys.forEach(k => next.delete(k));
      } else {
        tcKeys.forEach(k => next.add(k));
      }
      return next;
    });
  };

  // Build the list of selected test cases with full info for the chatbot
  const selectedTestCasesForChatbot = useMemo(() => {
    const result: { key: string; summary: string; description: string; url: string; steps?: { Step: string; Expected: string }[] }[] = [];
    for (const [_storyKey, testCases] of Object.entries(testCasesMap)) {
      for (const tc of testCases) {
        if (selectedTestCaseKeys.has(tc.key)) {
          result.push({
            key: tc.key,
            summary: tc.summary,
            description: tc.description || tc.summary || '',
            url: tc.url,
            steps: testStepsMap[tc.key] || [],
          });
        }
      }
    }
    return result;
  }, [selectedTestCaseKeys, testCasesMap, testStepsMap]);

  // Fetch test steps for selected test cases that haven't been fetched yet
  useEffect(() => {
    if (selectedTestCaseKeys.size === 0) return;
    const keysToFetch = Array.from(selectedTestCaseKeys).filter(k => !(k in testStepsMap));
    if (keysToFetch.length === 0) return;

    const fetchSteps = async () => {
      const newSteps: Record<string, { Step: string; Expected: string }[]> = {};
      await Promise.all(
        keysToFetch.map(async (tcKey) => {
          try {
            const steps = await fetchTestStepsByTestCase(tcKey);
            newSteps[tcKey] = steps;
          } catch (err) {
            console.error('Failed to fetch test steps for', tcKey, err);
            newSteps[tcKey] = [];
          }
        })
      );
      if (Object.keys(newSteps).length > 0) {
        setTestStepsMap(prev => ({ ...prev, ...newSteps }));
      }
    };
    fetchSteps();
  }, [selectedTestCaseKeys]);

  // ---- Cron Job handlers ----

  // Persist cron jobs to sessionStorage whenever they change
  useEffect(() => {
    sessionStorage.setItem('cronJobs', JSON.stringify(cronJobs));
  }, [cronJobs]);

  const handleCronJobSubmitted = useCallback((job: CronJob) => {
    setCronJobs(prev => [job, ...prev]);
  }, []);

  // Refresh a single job's status
  const refreshCronJobStatus = useCallback(async (jobId: string) => {
    setCronJobsLoading(prev => ({ ...prev, [jobId]: true }));
    try {
      const job = cronJobs.find(j => j.jobId === jobId);
      const detail: CronJobDetail = await fetchJobStatus(jobId);
      const previousStatus = job?.status;
      setCronJobs(prev =>
        prev.map(j =>
          j.jobId === jobId
            ? { ...j, status: detail.status, detail }
            : j
        )
      );

      // When job transitions to completed, refetch test cases for its stories in Jira
      if (detail.status === 'completed' && previousStatus !== 'completed' && job?.stories?.length) {
        const storyKeys = job.stories.map(s => s.key);
        const newTestCases: Record<string, JiraIssue[]> = {};
        await Promise.all(
          storyKeys.map(async (storyKey) => {
            try {
              const tcs = await fetchTestCasesByStory(storyKey);
              newTestCases[storyKey] = tcs;
            } catch (err) {
              console.error('Failed to refetch test cases for', storyKey, err);
            }
          })
        );
        if (Object.keys(newTestCases).length > 0) {
          setTestCasesMap(prev => ({ ...prev, ...newTestCases }));
          // Auto-expand the test case sections for these stories
          setExpandedStoryTestCases(prev => {
            const next = new Set(prev);
            storyKeys.forEach(k => next.add(k));
            return next;
          });
        }
      }
    } catch (err) {
      console.error('Failed to refresh job status:', err);
    } finally {
      setCronJobsLoading(prev => ({ ...prev, [jobId]: false }));
    }
  }, [cronJobs]);

  const handleRerunFailedStories = useCallback(async (jobId: string) => {
    setCronJobsLoading(prev => ({ ...prev, [jobId]: true }));
    try {
      // Optimistically mark failed stories as queued in UI
      setCronJobs(prev =>
        prev.map(j =>
          j.jobId === jobId && j.detail
            ? {
                ...j,
                status: 'running' as CronJobStatus,
                detail: {
                  ...j.detail,
                  status: 'running' as CronJobStatus,
                  stories: j.detail.stories.map(s =>
                    s.status === 'failed' ? { ...s, status: 'queued' as const } : s
                  ),
                },
              }
            : j
        )
      );
      await retryFailedStories(jobId);
      // Poll for updated status after triggering retry
      await refreshCronJobStatus(jobId);
    } catch (err) {
      console.error('Failed to retry failed stories:', err);
      // Revert by fetching actual status
      await refreshCronJobStatus(jobId);
    } finally {
      setCronJobsLoading(prev => ({ ...prev, [jobId]: false }));
    }
  }, [refreshCronJobStatus]);

  // Auto-poll all pending/processing (queued or running) jobs every 3 minutes
  useEffect(() => {
    const activeJobs = cronJobs.filter(j => j.status === 'queued' || j.status === 'running' || j.status === 'processing' || j.status === 'pending');
    if (activeJobs.length === 0) return;

    const interval = setInterval(() => {
      const currentActiveJobs = cronJobs.filter(j => j.status === 'queued' || j.status === 'running' || j.status === 'processing' || j.status === 'pending');
      currentActiveJobs.forEach(job => {
        refreshCronJobStatus(job.jobId);
      });
    }, 2 * 60 * 1000); // 2 minutes

    return () => clearInterval(interval);
  }, [cronJobs, refreshCronJobStatus]);

  // Status badge colour helper
  const getCronStatusColor = (status: CronJobStatus | string): string => {
    switch (status.toLowerCase()) {
      case 'completed':
      case 'success':          return 'rgba(74,222,128,0.6)';
      case 'partial success':
      case 'partial_success':  return 'rgba(251,146,60,0.6)';
      case 'running':
      case 'processing':
      case 'queued':
      case 'pending':          return 'rgba(250,204,21,0.6)';
      case 'scheduled':        return 'rgba(192,132,252,0.6)';
      case 'failed':           return 'rgba(248,113,113,0.6)';
      default:                 return 'rgba(156,163,175,0.6)';
    }
  };

  // Compute effective job-level display status:
  // If job is completed but any story failed, show "Partial Success"
  const getEffectiveJobStatus = (job: CronJob): string => {
    const s = job.status.toLowerCase();
    if (s === 'partial_success' || s === 'partial success') {
      return 'Partial Success';
    }
    const hasFailed = (job.detail && job.detail.failed_count > 0) || job.failedCount > 0;
    if ((s === 'completed' || s === 'success') && hasFailed) {
      return 'Partial Success';
    }
    return job.status;
  };

  // Per-story status icon helper
  const getStoryStatusConfig = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed':
      case 'success':    return { color: 'rgba(74,222,128,0.6)' };
      case 'running':
      case 'processing':
      case 'queued':
      case 'pending':    return { color: 'rgba(250,204,21,0.6)' };
      case 'failed':     return { color: 'rgba(248,113,113,0.6)' };
      default:           return { color: 'rgba(156,163,175,0.6)' };
    }
  };


  const getStatusColor = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'done' || s === 'closed' || s === 'resolved') return 'text-green-500 bg-green-500/10';
    if (s === 'in progress' || s === 'in review') return 'text-blue-500 bg-blue-500/10';
    return 'text-muted-foreground bg-muted/50';
  };

  // Derive BRD values from admin team members (shared with EmbeddedChatbot)
  const derivedProjectName = adminProjectDetails.name.trim() || '';
  const contextFabricProjectName = derivedProjectName;
  const canProceedContextFabric = Boolean(contextFabricProjectName) && (
    contextFabricUrl.trim().length > 0 || contextFabricFiles.length > 0
  );
  const derivedProductOwner = useMemo(() => {
    // Derive PO from logged-in auth user (WEGA-2002: decouple from adminTeamMembers)
    if (user && user.displayName && user.email) {
      return { name: user.displayName, role: 'Product Owner', email: user.email };
    }
    // Fallback: first filled PO in adminTeamMembers (projectTeamConfig defaults)
    const po = adminTeamMembers.find(m => {
      const r = m.role.toLowerCase();
      return r.includes('product owner') || r.includes('po');
    });
    if (po && po.name.trim() && po.email.trim()) {
      return { name: po.name, role: po.role, email: po.email };
    }
    return { name: '', role: 'Product Owner', email: '' };
  }, [user?.displayName, user?.email, adminTeamMembers]);

  // BRD Stakeholder state (used in onboarding popup for additional stakeholders)
  const [brdStakeholders, setBrdStakeholders] = useState<{ name: string; role: string; email: string }[]>([
    { name: '', role: 'Product Owner', email: '' },
    { name: '', role: 'Business Analyst', email: '' },
    { name: '', role: 'Project Manager', email: '' },
    { name: '', role: 'Technical Lead', email: '' },
    { name: '', role: 'Developer', email: '' },
    { name: '', role: 'QA Engineer', email: '' },
    { name: '', role: 'UX Designer', email: '' },
    { name: '', role: 'Stakeholder', email: '' },
    { name: '', role: 'Architect', email: '' },
    { name: '', role: 'Scrum Master', email: '' }
  ]);

  // Auto-prefill BRD stakeholders from Project Team Management (adminTeamMembers)
  // whenever those entries have values — so the BRD agent's "Project Configuration"
  // input section is populated by default, without requiring an explicit
  // "Save Team Configuration" click. Only members with both name + email are mapped;
  // empty defaults are skipped so we never overwrite a populated stakeholder with blanks.
  useEffect(() => {
    const mapped = adminTeamMembers
      .filter(m => m.name.trim() && m.email.trim())
      .map(m => ({ name: m.name, role: m.role, email: m.email }));
    if (mapped.length === 0) return;
    setBrdStakeholders(prev => {
      // Skip update if values are already identical to avoid render churn
      if (
        prev.length === mapped.length &&
        prev.every((p, i) => p.name === mapped[i].name && p.role === mapped[i].role && p.email === mapped[i].email)
      ) {
        return prev;
      }
      return mapped;
    });
  }, [adminTeamMembers]);

  // Map agent IDs to nextagentflow values
  const agentIdToNextagentflowMap: { [key: string]: string } = {
    'brd-generator': 'confirmedCreateBrd',
    'brd-summary': 'confirmedBrdSummary',
    'user-story-generator': 'confirmedCreateUserStory',
    'user-story-validator': 'confirmedValidateUserStory',
    'test-case': 'confirmedUserStoryToTestScenario',
    'test-script': 'confirmedTestCaseToTestScript',
    'test-data-generator': 'confirmedTestDataGenerator',
    'end-to-end-test': 'confirmedEndToEndTest',
    'user-manual': 'confirmedCreateUserManual',
  };

  const [agents, setAgents] = useState<AIAgent[]>([
    {
      id: 'Wega-Orchestrator',
      name: 'WEGA Orchestrator',
      description: 'Orchestrator for managing Wega AI agents',
      icon: FileText,
      color: '#3498B3',
      active: true,
    },
    {
      id: 'brd-generator',
      name: 'BRD Generator',
      description: 'Business Requirements Document Generator',
      icon: FileText,
      color: '#3498B3',
      active: false,
    },
    {
      id: 'brd-summary',
      name: 'BRD Summary',
      description: 'Business Requirements Document Summary Generator',
      icon: FileText,
      color: '#3498B3',
      active: false,
    },
    {
      id: 'user-story-generator',
      name: 'User Stories Creator',
      description: 'User Stories Creator',
      icon: ClipboardList,
      color: '#355493',
      active: false,
    },
    {
      id: 'user-story-validator',
      name: 'User Stories Validator',
      description: 'User Stories Validator',
      icon: ClipboardList,
      color: '#355493',
      active: false,
    },
    {
      id: 'code-assistant',
      name: 'Code Assistant',
      description: 'AI-powered Code Generation Assistant',
      icon: CodeXml,
      color: '#E67E22',
      active: false,
    },
    {
      id: 'test-case',
      name: 'Test Case',
      description: 'Test Case Generator',
      icon: ClipboardList,
      color: '#BE266A',
      active: false,
    },
    {
      id: 'test-script',
      name: 'Test Script',
      description: 'Test Script Generator',
      icon: ClipboardList,
      color: '#7b2d50',
      active: false,
    },
    {
      id: 'test-data',
      name: 'Test Data',
      description: 'Test Data Creator',
      icon: Database,
      color: '#351A55',
      active: false,
    },
    {
      id: 'test-data-generator',
      name: 'Test Data',
      description: 'Generate structured test data from test cases',
      icon: Database,
      color: '#351A55',
      active: false,
    },
    {
      id: 'end-to-end-test',
      name: 'End-to-End Test',
      description: 'End-to-End Test Artifacts Generator',
      icon: TestTube,
      color: '#746FA7',
      active: false,
    },
    {
      id: 'user-manual',
      name: 'User Manual',
      description: 'User Manual Generator',
      icon: Book,
      color: '#746FA7',
      active: false,
    },
  ]);

  // Role-filtered agents: hide Orchestrator (D-12) + filter by JWT allowedAgents
  const visibleAgents = useMemo(() =>
    agents.filter(
      (agent) =>
        agent.id !== 'Wega-Orchestrator' &&         // D-12: always hidden
        allowedAgentIds.includes(agent.id)
    ),
    [agents, allowedAgentIds]
  );

  // Tool configuration status — driven by backend readiness flag
  const isToolConfigured = useCallback((toolKey: string): boolean => {
    return projectTools[toolKey]?.ready === true;
  }, [projectTools]);

  const promptTemplates: PromptTemplate[] = [
    {
      id: '1',
      title: 'Create BRD',
      content: 'Create BRD',
      agentId: 'brd-generator',
    },
    {
      id: '2',
      title: 'Create BRD Summary',
      content: 'Create BRD Summary',
      agentId: 'brd-summary',
    },
    {
      id: '3',
      title: 'Create User Story',
      content: 'Create User Story',
      agentId: 'user-story-generator',
    },
    {
      id: '4',
      title: 'Validate User Story',
      content: 'Validate User Story',
      agentId: 'user-story-validator',
    },
    {
      id: '5',
      title: 'Create Test Cases',
      content: 'Create Test Cases',
      agentId: 'test-case',
    },
    {
      id: '7',
      title: 'Create Test Scripts',
      content: 'Create Test Scripts',
      agentId: 'test-script',
    },
    {
      id: '8',
      title: 'Create Test Data',
      content: 'Create Test Data',
      agentId: 'test-data-generator',
    },
    {
      id: '9',
      title: 'Code Generation Assistant',
      content: 'Code Generation Assistant',
      agentId: 'code-assistant',
    },
    {
      id: '10',
      title: 'Create User Manual',
      content: 'Create User Manual',
      agentId: 'user-manual',
      nextagentflow: 'confirmedCreateUserManual',
    },
  ];

  const wegaBrainPrompts: WegaBrainPrompt[] = [
    {
      id: 'wb-1',
      title: 'Query Knowledge Base',
      nextagentflow: 'confirmedQueryKnowledgeBase',
    },
  ];

  // Filter prompts based on selected agent
  const filteredPrompts = selectedPromptAgent === 'all' 
    ? promptTemplates 
    : promptTemplates.filter(prompt => prompt.agentId === selectedPromptAgent);

  const toggleAgent = (agentId: string) => {
    setAgents(agents.map(agent => 
      agent.id === agentId ? { ...agent, active: true } : { ...agent, active: false }
    ));
  };

  const handlePromptSelect = (prompt: PromptTemplate) => {
    // Clear inputs first, then set new prompt
    setInputMessage('');
    setSelectedPromptForChatbot('');
    setSelectedNextagentflowForChatbot('');
    
    // Only clear Jira & Confluence selections for Create BRD; preserve them for all other agents
    if (prompt.agentId === 'brd-generator') {
      setSelectedJiraIssues(new Set());
      setSelectedTestCaseKeys(new Set());
      setExpandedEpics(new Set());
      setExpandedStoryTestCases(new Set());
    }
    setJiraSelectionLocked(false);
    // Clear chatbot internal fields without clearing Confluence/Jira left-sidebar selections
    chatbotRef.current?.clearFieldsForPromptSwitch();

    // Use setTimeout to ensure clear happens before setting new values
    setTimeout(() => {
      setInputMessage(prompt.title);
      setSelectedPromptForChatbot(prompt.title);
      // Set nextagentflow if the prompt defines one (e.g., User Manual needs form shown immediately)
      setSelectedNextagentflowForChatbot(prompt.nextagentflow || '');
    }, 0);
    // Also toggle the corresponding agent as active
    toggleAgent(prompt.agentId);
  };

  const handleWegaBrainPromptSelect = (prompt: WegaBrainPrompt) => {
    setInputMessage('');
    setSelectedPromptForChatbot('');
    setSelectedNextagentflowForChatbot('');

    setJiraSelectionLocked(false);
    chatbotRef.current?.clearFieldsForPromptSwitch();

    setTimeout(() => {
      setInputMessage(prompt.title);
      setSelectedPromptForChatbot(prompt.title);
      setSelectedNextagentflowForChatbot(prompt.nextagentflow);
    }, 0);

    toggleAgent('wega-brain');
  };

  const handleAgentClick = (agentId: string) => {
    if (expandedAgentId === agentId) {
      setExpandedAgentId(null);
    } else {
      setExpandedAgentId(agentId);
    }
  };

  const getPromptsForAgent = (agentId: string) => {
    return promptTemplates.filter(prompt => prompt.agentId === agentId);
  };

  // Context Enrichment: submit URL/file to SDLC orchestrator with context_enrich intent
  // Uses the /stream endpoint with the same payload pattern as other agent flows.
  // URLs that look like a code-repository host (GitHub / Harness / GitLab / Bitbucket /
  // Azure DevOps) are routed as source="repo" so the backend uses RepositoryConnector
  // (GitHub/Harness API) instead of plain HTML scraping. All other URLs go as
  // source="website".
  const REPO_HOST_PATTERNS: Array<RegExp> = [
    /(^|\.)github\.com$/i,
    /(^|\.)gitlab\.com$/i,
    /(^|\.)bitbucket\.org$/i,
    /(^|\.)dev\.azure\.com$/i,
    /\.visualstudio\.com$/i,
    /(^|\.)harness\.io$/i,
    /(^|\.)app\.harness\.io$/i,
  ];

  const isRepoUrl = (raw: string): boolean => {
    try {
      const u = new URL(raw);
      const host = u.hostname.toLowerCase();
      if (!REPO_HOST_PATTERNS.some(rx => rx.test(host))) return false;
      // GitHub/GitLab/Bitbucket repo URLs always have /<owner>/<repo> at minimum.
      // Harness Code: /<account>/orgs/<org>/projects/<project>/repos/<repo>
      const parts = u.pathname.replace(/^\/+|\/+$/g, '').split('/').filter(Boolean);
      if (host.endsWith('harness.io')) return parts.includes('repos') || parts.length >= 4;
      return parts.length >= 2;
    } catch {
      return false;
    }
  };

  const handleContextEnrichSubmit = async () => {
    // Filter out empty URLs
    const validUrls = contextEnrichUrls.map(u => u.trim()).filter(u => u.length > 0);
    if (validUrls.length === 0 && contextEnrichFiles.length === 0) {
      setContextEnrichStatus('error');
      setContextEnrichMessage('Please enter at least one URL or upload a file.');
      return;
    }
    setContextEnrichLoading(true);
    setContextEnrichProgress(0);
    setContextEnrichStatus('idle');
    setContextEnrichMessage('');

    // Split URLs into repo vs website based on hostname pattern
    const repoUrls = validUrls.filter(isRepoUrl);
    const websiteUrls = validUrls.filter(u => !isRepoUrl(u));

    // Generate a session ID (same pattern as other flows: sess_ + random hex)
    const sessionId = 'sess_' + Array.from(crypto.getRandomValues(new Uint8Array(6)))
      .map(b => b.toString(16).padStart(2, '0')).join('');

    // Helper: build one request body for a given URL bucket. Files (if any) are
    // attached only on the FIRST request (upload intent), all other requests are
    // pure-URL ingest intents.
    type SubmitJob = { body: FormData | string; headers: HeadersInit; label: string };
    const jobs: SubmitJob[] = [];

    const buildIngestJob = (kind: 'website' | 'repo', urls: string[]): SubmitJob => {
      if (kind === 'website') {
        const payload = {
          session_id: sessionId,
          message: 'Context Enrichment',
          explicit_intent: 'context_enrich_ingest',
          context: { source: 'website', urls, project_name: contextFabricProjectName },
        };
        return {
          body: JSON.stringify(payload),
          headers: { 'Content-Type': 'application/json' },
          label: `${urls.length} website URL(s)`,
        };
      }
      // repo: backend accepts ONE repo_url per /api/v1/ingest call, so we send
      // one request per repo URL. The orchestrator/common-integration use the
      // same single-URL contract (context.repo_url).
      const repoUrl = urls[0];
      const payload = {
        session_id: sessionId,
        message: 'Context Enrichment',
        explicit_intent: 'context_enrich_ingest',
        context: { source: 'repo', repo_url: repoUrl, project_name: contextFabricProjectName },
      };
      return {
        body: JSON.stringify(payload),
        headers: { 'Content-Type': 'application/json' },
        label: `repo ${repoUrl}`,
      };
    };

    try {
      if (contextEnrichFiles.length > 0) {
        // Files always go through context_enrich_upload (multipart). Any website
        // URLs typed alongside the files are forwarded on the same multipart so
        // the upload intent can also kick off a website ingest in one round-trip
        // (existing orchestrator behavior). Repo URLs cannot ride along on a
        // multipart upload, so we send them as separate ingest jobs below.
        const formData = new FormData();
        formData.append('session_id', sessionId);
        formData.append('message', 'Context Enrichment');
        formData.append('explicit_intent', 'context_enrich_upload');
        const uploadContext: Record<string, any> = { project_name: contextFabricProjectName };
        if (websiteUrls.length > 0) {
          uploadContext.source = 'website';
          uploadContext.urls = websiteUrls;
        }
        formData.append('context', JSON.stringify(uploadContext));
        contextEnrichFiles.forEach(file => formData.append('file', file));
        jobs.push({
          body: formData,
          headers: {}, // browser sets multipart boundary
          label: `${contextEnrichFiles.length} file(s)` + (websiteUrls.length > 0 ? ` + ${websiteUrls.length} URL(s)` : ''),
        });
        // Each repo URL gets its own ingest job
        repoUrls.forEach(u => jobs.push(buildIngestJob('repo', [u])));
      } else {
        if (websiteUrls.length > 0) jobs.push(buildIngestJob('website', websiteUrls));
        repoUrls.forEach(u => jobs.push(buildIngestJob('repo', [u])));
      }

      // For multi-job submissions, dispatch sequentially so a single SSE-style
      // progress UI stays coherent. Aggregate the result message at the end.
      const messages: string[] = [];
      const errors: string[] = [];

      // One simulated-progress interval shared across all jobs.
      let progressValue = 5;
      setContextEnrichProgress(progressValue);
      const progressInterval = setInterval(() => {
        progressValue += progressValue < 30 ? 4 : progressValue < 60 ? 3 : progressValue < 85 ? 1.5 : 0.3;
        if (progressValue > 92) progressValue = 92;
        setContextEnrichProgress(Math.round(progressValue));
      }, 300);

      try {
        for (let i = 0; i < jobs.length; i++) {
          const job = jobs[i];

          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 600000);
          const response = await apiFetch(
            CHAT_STREAM_ENDPOINT,
            {
              method: 'POST',
              headers: job.headers,
              body: job.body,
              signal: controller.signal,
            }
          );
          clearTimeout(timeoutId);

          // Handle streaming response (SSE / text event-stream)
          const contentType = response.headers.get('content-type') || '';
          let data: any;

          if (contentType.includes('text/event-stream') || contentType.includes('text/plain')) {
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            let accumulated = '';
            if (reader) {
              while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                accumulated += decoder.decode(value, { stream: true });
              }
            }
            const jsonChunks = accumulated.split('\n').filter(line => line.trim());
            const lastChunk = jsonChunks[jsonChunks.length - 1] || '';
            try {
              const jsonStr = lastChunk.replace(/^data:\s*/, '');
              data = JSON.parse(jsonStr);
            } catch {
              data = { success: response.ok, message: accumulated.trim() || 'Context enrichment completed.' };
            }
          } else {
            data = await response.json();
          }

          const ok = response.ok && (data?.success !== false);
          const msg = (data && (data.message || data.error)) || (ok ? 'Completed.' : 'Failed.');
          if (ok) {
            messages.push(`${job.label}: ${msg}`);
          } else {
            errors.push(`${job.label}: ${msg}`);
          }
        }

        clearInterval(progressInterval);
        setContextEnrichProgress(100);

        if (errors.length === 0) {
          setContextEnrichStatus('success');
          setContextEnrichMessage(messages.join(' | ') || 'Context enrichment completed successfully.');
          setContextEnrichUrls(['']);
          setContextEnrichFiles([]);
          if (contextEnrichFileInputRef.current) contextEnrichFileInputRef.current.value = '';
        } else if (messages.length === 0) {
          setContextEnrichStatus('error');
          setContextEnrichMessage(errors.join(' | '));
        } else {
          // Partial success
          setContextEnrichStatus('error');
          setContextEnrichMessage(`Partial: OK[${messages.join(' | ')}] FAILED[${errors.join(' | ')}]`);
        }
      } catch (error) {
        clearInterval(progressInterval);
        throw error;
      }
    } catch (error) {
      console.error('Context enrichment error:', error);
      setContextEnrichProgress(100);
      setContextEnrichStatus('error');
      if (error instanceof DOMException && error.name === 'AbortError') {
        setContextEnrichMessage('Request timed out. The server took too long to respond.');
      } else {
        setContextEnrichMessage(error instanceof Error ? error.message : 'Unknown error occurred.');
      }
    } finally {
      setContextEnrichLoading(false);
    }
  };

  const handleAgentChange = useCallback((nextagentflow: string) => {
    // Update currentNextagentflow state
    setCurrentNextagentflow(nextagentflow);
    
    // Map nextagentflow values to agent IDs
    const agentFlowMap: { [key: string]: string } = {
      'confirmedBrdSummary': 'brd-summary',
      'confirmedCreateBrd': 'brd-generator',
      'confirmedCreateUserStory': 'user-story-generator',
      'confirmedValidateUserStory': 'user-story-validator',
      'confirmedUserStoryToTestScenario': 'test-case',
      'confirmedTestCaseToTestScript': 'test-script',
      'confirmedTestDataGenerator': 'test-data-generator',
      'confirmedEndToEndTest': 'end-to-end-test',
      'confirmedCreateUserManual': 'user-manual',
      'confirmedCodeAssistant': 'code-assistant',
      'context_enrich': 'context-enrich',
    };

    // If nextagentflow is empty, set SDLC Orchestrator as active and reset BRD state
    if (!nextagentflow || nextagentflow === '') {
      toggleAgent('Wega-Orchestrator');
      // Reset BRD stakeholder state (projectName is derived from admin team)
      setBrdStakeholders([
        { name: '', role: 'Product Owner', email: '' },
        { name: '', role: 'Business Analyst', email: '' },
        { name: '', role: 'Project Manager', email: '' },
        { name: '', role: 'Technical Lead', email: '' },
        { name: '', role: 'Developer', email: '' },
        { name: '', role: 'QA Engineer', email: '' },
        { name: '', role: 'UX Designer', email: '' },
        { name: '', role: 'Stakeholder', email: '' },
        { name: '', role: 'Architect', email: '' },
        { name: '', role: 'Scrum Master', email: '' }
      ]);
      return;
    }

    const agentId = agentFlowMap[nextagentflow];
    if (agentId) {
      toggleAgent(agentId);
    }
  }, []);

  return (
    <div className="bg-background">

      {/* SDLC Stage Detail Modal */}
      {showStageModal && selectedStage && createPortal(
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto"
          style={{ backgroundColor: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(4px)', animation: 'fadeIn 0.3s ease-out' }}
        >
          <div
            className="relative w-full mx-4 my-8"
            style={{ maxWidth: '64rem', animation: 'slideUp 0.5s ease-out' }}
          >
            {/* Close Button */}
            <button
              onClick={handleStageBack}
              className="absolute rounded-full flex items-center justify-center border-2 transition-all duration-300 group"
              style={{
                top: '-1rem',
                right: '-1rem',
                zIndex: 60,
                width: '3rem',
                height: '3rem',
                background: 'linear-gradient(to bottom right, #1e293b, #0f172a)',
                borderColor: 'rgb(59 130 246 / 0.5)',
                boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'linear-gradient(to bottom right, #2563eb, #9333ea)';
                e.currentTarget.style.borderColor = '#60a5fa';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'linear-gradient(to bottom right, #1e293b, #0f172a)';
                e.currentTarget.style.borderColor = 'rgb(59 130 246 / 0.5)';
              }}
            >
              <X className="w-6 h-6 text-gray-300 group-hover:text-white transition-colors" />
            </button>

            {/* Modal Card */}
            <div
              className="rounded-2xl shadow-2xl overflow-hidden"
              style={{
                background: 'linear-gradient(to bottom right, #0f172a, #1e293b)',
                border: '1px solid rgb(59 130 246 / 0.3)',
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {renderStageDetail()}
            </div>

            {/* Click outside to close */}
            <div
              className="fixed inset-0"
              style={{ zIndex: -1 }}
              onClick={handleStageBack}
            />
          </div>
        </div>,
        document.body
      )}

    <div className="bg-background flex flex-col overflow-hidden" style={{ height: 'calc(100vh - var(--header-height))' }}>
      {/* Execute Header */}
      <div className="z-40 bg-background pb-2 flex-shrink-0">
        <div className="max-w-[1800px] mx-auto px-6 pt-3">
          <div className="rounded-xl overflow-hidden transition-all duration-300" style={{ background: 'linear-gradient(135deg, rgba(53,26,85,0.06), rgba(52,152,179,0.06))' }}>
            {/* Collapse / Expand Toggle Bar */}
            <button
              onClick={() => setSdlcExpanded(!sdlcExpanded)}
              className="w-full flex items-center justify-between pl-5 pr-12 py-3 hover:bg-muted/40 transition-colors duration-200 cursor-pointer"
            >
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-gradient-to-br from-[#351A55] to-[#3498B3] shadow-md">
                  <Sparkles className="w-5 h-5 text-white" />
                </div>
                <span className="text-base font-bold text-foreground">Execute</span>
              </div>
              <ChevronDown
                className={`w-5 h-5 text-muted-foreground transition-transform duration-300 mr-2 ${sdlcExpanded ? 'rotate-0' : '-rotate-90'}`}
              />
            </button>

            {/* Expanded Content */}
            <div
              className="transition-all duration-300 ease-in-out overflow-hidden"
              style={{ maxHeight: sdlcExpanded ? '600px' : '0px', opacity: sdlcExpanded ? 1 : 0 }}
            >
              <div className="px-5 pt-0 pb-4">
              {/* Description */}
              <div style={{ paddingLeft: '48px', marginBottom: '12px' }}>
                <p className="text-muted-foreground text-sm max-w-full whitespace-nowrap">
                  Interact with AI agents to generate BRDs, user stories, test scenarios, and more. Leverage the power of agentic orchestration to accelerate your software delivery lifecycle.
                </p>
              </div>

              {/* SDLC Journey */}
              <SDLCJourney onStageClick={handleStageClick} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area - keeps full viewport height, scrolls when SDLC expanded */}
      <div className="flex-shrink-0" style={{ height: 'calc(100vh - var(--header-height) - 68px)' }}>
      <div className="max-w-[1800px] mx-auto px-6 pb-2 h-full">
        {/* Two Column Layout */}
        <div className="grid h-full" style={{ gap: sidebarExpanded ? '24px' : '12px', gridTemplateColumns: sidebarExpanded ? '0.75fr 1.25fr' : '60px 1fr', transition: 'grid-template-columns 0.3s ease, gap 0.3s ease' }}>
          {/* Left Column - AI Agents & Prompt Library */}
          <div
            className="min-w-0 rounded-lg relative overflow-hidden"
            style={{ backgroundColor: 'var(--sidebar-panel-bg)', border: '1px solid var(--sidebar-panel-border)' }}
          >
            {/* Expanded sidebar */}
            <div className={`absolute inset-0 h-full flex flex-col transition-opacity duration-300 ${sidebarExpanded ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
              <div className="flex items-center justify-end p-4 flex-shrink-0" style={{ minHeight: '73px', borderBottom: '1px solid var(--sidebar-panel-border)' }}>
                <button
                  onClick={() => setSidebarExpanded(false)}
                  className="p-1 rounded hover:bg-muted transition-colors"
                  title="Collapse sidebar"
                >
                  <span className="text-xl font-bold text-[#3498B3]">&laquo;</span>
                </button>
              </div>
              <div className="space-y-3 p-2 flex-1 overflow-y-auto themed-scroll">
                {/* Empty state when user has no visible agents */}
                {visibleAgents.length === 0 && (
                  <div className="flex flex-col items-center justify-center text-center py-8 px-4 gap-2">
                    <Library className="w-8 h-8 text-muted-foreground/40" />
                    <p className="text-base text-muted-foreground">No agents available for your role.</p>
                  </div>
                )}
                {/* Prompt Library — hidden when user has 0 visible agents (MLOps, PM per D-10) */}
                {visibleAgents.length > 0 && (
                <Card className="overflow-hidden shadow-sm" style={{ backgroundColor: 'var(--sidebar-section-bg)', border: '1px solid var(--sidebar-section-border)', gap: 0 }}>
                  <div 
                    className={`flex items-center justify-between px-3 cursor-pointer transition-all ${expandedSection === 'promptLibrary' ? 'py-2.5' : 'py-2.5'}`}
                    style={{ borderBottom: expandedSection === 'promptLibrary' ? '1px solid var(--sidebar-section-border)' : 'none', backgroundColor: expandedSection === 'promptLibrary' ? 'var(--sidebar-header-bg)' : 'transparent' }}
                    onClick={() => { setExpandedSection(expandedSection === 'promptLibrary' ? null : 'promptLibrary'); setCronSectionExpanded(false); }}
                  >
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2">
                        <Library className="w-4 h-4 text-[#746FA7]" />
                        <h3 className="text-base font-semibold text-foreground">Prompt Library</h3>
                      </div>
                      <span className="text-[10px] text-muted-foreground" style={{ marginLeft: '1.6rem' }}>{visibleAgents.filter(a => getPromptsForAgent(a.id).length > 0).length} Agents</span>
                    </div>
                    <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform duration-200 ${expandedSection !== 'promptLibrary' ? '-rotate-90' : ''}`} />
                  </div>
                  
                  <div
                    ref={promptLibraryRef}
                    className={expandedSection === 'promptLibrary' ? 'themed-scroll' : ''}
                    style={{
                      maxHeight: expandedSection === 'promptLibrary' ? '600px' : 0,
                      overflowY: expandedSection === 'promptLibrary' ? 'auto' : 'hidden',
                      transition: 'max-height 0.3s ease',
                    }}
                  >
                  <div className="p-2">
                  {/* Search Filter */}
                  <div className="mb-2">
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3 h-3" style={{ color: 'var(--sidebar-search-focus)', opacity: 0.5 }} />
                      <input
                        type="text"
                        placeholder="Search agents or prompts..."
                        value={promptSearchFilter}
                        onChange={(e) => { setPromptSearchFilter(e.target.value); setAgentListCollapsed(false); }}
                        className="w-full pl-8 pr-7 py-1.5 text-base rounded-md focus:outline-none focus:ring-1 placeholder:text-muted-foreground/40 text-foreground transition-all"
                        style={{ backgroundColor: 'var(--sidebar-search-bg)', border: '1px solid var(--sidebar-search-border)', '--tw-ring-color': 'var(--sidebar-search-focus)' } as React.CSSProperties}
                      />
                      {promptSearchFilter && (
                        <button
                          onClick={() => setPromptSearchFilter('')}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground/50 hover:text-foreground transition-colors"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Agent List */}
                  <div style={{ maxHeight: agentListCollapsed ? 0 : 2000, overflow: 'hidden', transition: 'max-height 0.25s ease' }}>
                  <div className="space-y-0.5">
                    {visibleAgents
                      .filter(agent => {
                        const agentPrompts = getPromptsForAgent(agent.id);
                        if (agentPrompts.length === 0) return false;
                        if (!promptSearchFilter) return true;
                        const search = promptSearchFilter.toLowerCase();
                        return agent.name.toLowerCase().includes(search) || agentPrompts.some(p => p.title.toLowerCase().includes(search));
                      })
                      .map((agent) => {
                        const agentPrompts = getPromptsForAgent(agent.id);
                        const isExpanded = expandedAgentId === agent.id;
                        const isActive = agent.active;
                        return (
                          <div key={agent.id}>
                            <div
                              onClick={() => handleAgentClick(agent.id)}
                              className={`flex items-center gap-1.5 px-2 py-1.5 rounded-md cursor-pointer transition-all group ${isActive ? 'border' : ''}`}
                              style={isActive ? { backgroundColor: 'var(--sidebar-accent-subtle)', borderColor: 'var(--sidebar-search-border)' } : {}}
                            >
                              <ChevronDown className="w-3 h-3 text-muted-foreground flex-shrink-0 transition-transform duration-150" style={{ transform: isExpanded ? 'rotate(0deg)' : 'rotate(-90deg)' }} />
                              <div className="w-5 h-5 rounded flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${agent.color}15` }}>
                                <agent.icon className="w-3 h-3 flex-shrink-0" style={{ color: agent.color }} />
                              </div>
                              <span className={`text-base truncate flex-1 ${isActive ? 'text-[#746FA7] font-medium' : 'text-foreground group-hover:text-[#746FA7]'}`}>
                                {agent.name}
                              </span>
                            </div>
                            <div style={{ maxHeight: isExpanded ? 500 : 0, overflow: 'hidden', transition: 'max-height 0.2s ease' }}>
                              <div className="relative mt-0.5 mb-1 space-y-px" style={{ marginLeft: '1.1rem', paddingLeft: '1rem', borderLeft: '1px dashed var(--sidebar-tree-line)' }}>
                                {agentPrompts.map((prompt, idx) => (
                                  <div
                                    key={prompt.id}
                                    onClick={() => handlePromptSelect(prompt)}
                                    className="relative flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer transition-all group"
                                    style={{ ['--hover-bg' as string]: 'var(--sidebar-section-hover)' }}
                                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--sidebar-section-hover)')}
                                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                                  >
                                    <span className="absolute" style={{ left: '-1rem', width: '1rem', top: '50%', borderBottom: '1px dashed var(--sidebar-tree-line)' }} />
                                    {idx === agentPrompts.length - 1 && (
                                      <span className="absolute" style={{ left: '-1px', top: '50%', bottom: 0, width: '2px', background: 'var(--sidebar-section-bg)' }} />
                                    )}
                                    <Sparkles className="w-2.5 h-2.5 text-[#746FA7]/40 flex-shrink-0" />
                                    <span className="text-base text-muted-foreground group-hover:text-[#746FA7] transition-colors">
                                      {prompt.title}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    {visibleAgents.filter(agent => {
                      const agentPrompts = getPromptsForAgent(agent.id);
                      if (agentPrompts.length === 0) return false;
                      if (!promptSearchFilter) return true;
                      const search = promptSearchFilter.toLowerCase();
                      return agent.name.toLowerCase().includes(search) || agentPrompts.some(p => p.title.toLowerCase().includes(search));
                    }).length === 0 && (
                      <div className="text-center py-6">
                        <Search className="w-4 h-4 mx-auto mb-2 text-muted-foreground/30" />
                        <p className="text-base text-muted-foreground/60">
                          No agents match "{promptSearchFilter}"
                        </p>
                      </div>
                    )}
                  </div>
                  </div>
                  </div>
                  </div>
                </Card>
                )}

                {/* Confluence Section — conditional on tool configuration (D-16) */}
                {isToolConfigured('confluence') && (
                <Card className="overflow-hidden shadow-sm" style={{ backgroundColor: 'var(--sidebar-section-bg)', border: '1px solid var(--sidebar-section-border)', gap: 0 }}>
                  <div 
                    className={`flex items-center justify-between px-3 cursor-pointer transition-all ${expandedSection === 'confluence' ? 'py-2.5' : 'py-2.5'}`}
                    style={{ borderBottom: expandedSection === 'confluence' ? '1px solid var(--sidebar-section-border)' : 'none', backgroundColor: expandedSection === 'confluence' ? 'var(--sidebar-header-bg)' : 'transparent' }}
                    onClick={() => { setExpandedSection(expandedSection === 'confluence' ? null : 'confluence'); setCronSectionExpanded(false); }}
                  >
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2">
                      <svg className="w-4 h-4 text-[#0052CC]" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M2.65 18.776c-.198.326-.418.7-.594.998a.543.543 0 0 0 .197.744l3.503 2.129a.543.543 0 0 0 .744-.179c.155-.262.38-.642.62-1.054 1.674-2.88 3.37-2.534 6.434-1.2l3.467 1.508c.268.117.58-.003.706-.266l1.87-4.088a.54.54 0 0 0-.26-.716s-1.84-.794-3.538-1.527c-5.49-2.378-9.867-2.075-13.149 3.651zm18.7-13.552c.198-.326.418-.7.594-.998a.543.543 0 0 0-.197-.744L18.244 1.353a.543.543 0 0 0-.744.179c-.155.262-.38.642-.62 1.054-1.674 2.88-3.37 2.534-6.434 1.2L6.979 2.278a.544.544 0 0 0-.706.266l-1.87 4.088a.54.54 0 0 0 .26.716s1.84.794 3.538 1.527c5.49 2.378 9.867 2.075 13.149-3.651z" />
                      </svg>
                      <h3 className="text-base font-semibold text-foreground">Confluence</h3>
                      </div>
                      <span className="text-[10px] text-muted-foreground" style={{ marginLeft: '1.6rem' }}>{selectedConfluencePages.size} {selectedConfluencePages.size === 1 ? 'Space' : 'Spaces'}</span>
                    </div>
                    <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform duration-200 ${expandedSection !== 'confluence' ? '-rotate-90' : ''}`} />
                  </div>

                  <div
                    ref={confluenceRef}
                    style={{
                      maxHeight: expandedSection === 'confluence' ? sectionHeights.confluence || 1000 : 0,
                      overflow: 'hidden',
                      transition: 'max-height 0.3s ease',
                    }}
                  >
                    <div className="p-2">
                      {/* Sub-header with refresh */}
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-base text-muted-foreground font-medium">Folders & Pages</p>
                        <div className="flex items-center gap-1.5">
                          {selectedConfluencePages.size > 0 && (
                            <button
                              type="button"
                              className="text-muted-foreground hover:text-[#0052CC] transition-colors"
                              onClick={() => setSelectedConfluencePages(new Set())}
                              title="Clear all selections"
                            >
                              <ListX className="w-4 h-4" />
                            </button>
                          )}
                          <button
                            type="button"
                            className={`text-muted-foreground hover:text-[#0052CC] transition-colors ${confluenceLoading ? 'animate-spin' : ''}`}
                            onClick={handleConfluenceRefresh}
                            disabled={confluenceLoading}
                            title="Refresh Confluence"
                          >
                            <RefreshCw className="w-4 h-4" />
                          </button>
                        </div>
                      </div>

                      {/* Search */}
                      <div className="relative mb-2">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3 h-3" style={{ color: '#0052CC', opacity: 0.5 }} />
                        <Input
                          type="text"
                          placeholder="Search pages..."
                          value={confluenceSearch}
                          onChange={(e) => setConfluenceSearch(e.target.value)}
                          className="pl-8 text-base"
                          style={{ backgroundColor: 'var(--sidebar-search-bg)', border: '1px solid var(--sidebar-search-border)' }}
                        />
                      </div>

                      {/* Tree View */}
                      <div
                        className="space-y-1 pr-1 themed-scroll"
                        style={{ maxHeight: '400px', overflowY: 'auto' }}
                      >
                        {/* Loading */}
                        {confluenceLoading && (
                          <div className="flex items-center justify-center py-6">
                            <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#0052CC] mr-2" />
                            <p className="text-base text-muted-foreground">Loading pages...</p>
                          </div>
                        )}

                        {/* Error */}
                        {confluenceError && !confluenceLoading && (
                          <div className="text-center py-4">
                            <p className="text-base text-red-500 mb-2">{confluenceError}</p>
                            <Button variant="outline" size="sm" onClick={handleConfluenceRefresh} className="text-base">
                              Retry
                            </Button>
                          </div>
                        )}

                        {/* Page tree */}
                        {!confluenceLoading && !confluenceError && (() => {
                          const allPages = filterConfluencePages(confluencePages);
                          const isSearchMode = confluenceSearch.trim().length > 0;
                          const visiblePages = isSearchMode ? allPages : allPages.slice(0, confluencePagePage * CONFLUENCE_PAGES_PER_LOAD);
                          const hasMore = !isSearchMode && allPages.length > visiblePages.length;
                          return (<>
                        {visiblePages.map((page) => (
                          <div key={page.id}>
                            {(page.isFolder || (page.children && page.children.length > 0)) ? (
                              <>
                                {/* ── Folder row (matches Jira epic style) ── */}
                                <div
                                  className="flex items-center space-x-2 p-2 rounded-lg hover:bg-muted/50 cursor-pointer transition-all group"
                                  onClick={() => toggleConfluenceFolder(page.id)}
                                >
                                  {expandedConfluenceFolders.has(page.id) ? (
                                    <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                                  ) : (
                                    <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                                  )}
                                  <FolderOpen className="w-3.5 h-3.5 text-[#0052CC] flex-shrink-0" />
                                  <div className="flex-1 min-w-0">
                                    <p className="text-base text-foreground truncate group-hover:text-[#0052CC]">
                                      {page.title}
                                    </p>
                                    {page.children && page.children.length > 0 && (
                                      <span className="text-[10px] text-muted-foreground">
                                        {page.children.length} pages
                                      </span>
                                    )}
                                  </div>
                                </div>

                                {/* ── Child pages (matches Jira story style) ── */}
                                {expandedConfluenceFolders.has(page.id) && page.children && page.children.length > 0 && (
                                  <div
                                    className="ml-4 space-y-1 pr-1 themed-scroll"
                                    style={{ maxHeight: '280px', overflowY: 'auto' }}
                                  >
                                    {(confluenceFolderShowAll.has(page.id) ? page.children : page.children.slice(0, 10)).map((child) => (
                                      <div
                                        key={child.id}
                                        className="flex items-center space-x-2 p-2 rounded-lg hover:bg-muted/50 cursor-pointer transition-all group"
                                        onClick={() => toggleConfluencePageSelection(child.id, child.title)}
                                      >
                                        {/* Selection circle */}
                                        <div className={`w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
                                          selectedConfluencePages.has(child.id)
                                            ? 'border-[#0052CC] bg-[#0052CC]'
                                            : 'border-muted-foreground'
                                        }`}>
                                          {selectedConfluencePages.has(child.id) && (
                                            <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: isDarkMode ? '#ffffff' : '#1e3a5f' }} />
                                          )}
                                        </div>
                                        <FileText className="w-3.5 h-3.5 text-[#36B37E] flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                          <p className="text-base text-foreground truncate group-hover:text-[#0052CC]">
                                            {child.title}
                                          </p>
                                          {child.date && (
                                            <span className="text-[10px] text-muted-foreground">
                                              {child.date}
                                            </span>
                                          )}
                                        </div>
                                        <a
                                          href={confluenceBrowseUrl(child.id, child.title, selectedSpaceKey)}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          onClick={(e) => e.stopPropagation()}
                                          className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                                          title="Open in Confluence"
                                        >
                                          <ExternalLink className="w-3.5 h-3.5 text-muted-foreground hover:text-[#0052CC]" />
                                        </a>
                                      </div>
                                    ))}
                                    {!confluenceFolderShowAll.has(page.id) && page.children.length > 10 && (
                                      <div className="flex justify-center py-2">
                                        <Button
                                          variant="outline"
                                          size="sm"
                                          onClick={(e) => { e.stopPropagation(); setConfluenceFolderShowAll(prev => { const next = new Set(prev); next.add(page.id); return next; }); }}
                                          className="text-base gap-1.5"
                                          style={{ borderColor: '#0052CC', color: '#0052CC' }}
                                        >
                                          Load More
                                        </Button>
                                      </div>
                                    )}
                                  </div>
                                )}

                                {/* Expanded but empty */}
                                {expandedConfluenceFolders.has(page.id) && (!page.children || page.children.length === 0) && (
                                  <div className="ml-8 py-2">
                                    <p className="text-base text-muted-foreground italic">No child pages</p>
                                  </div>
                                )}
                              </>
                            ) : (
                              /* ── Standalone page ── */
                              <div
                                className="flex items-center space-x-2 p-2 rounded-lg hover:bg-muted/50 cursor-pointer transition-all group"
                                onClick={() => toggleConfluencePageSelection(page.id, page.title)}
                              >
                                <div className={`w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
                                  selectedConfluencePages.has(page.id)
                                    ? 'border-[#0052CC] bg-[#0052CC]'
                                    : 'border-muted-foreground'
                                }`}>
                                  {selectedConfluencePages.has(page.id) && (
                                    <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: isDarkMode ? '#ffffff' : '#1e3a5f' }} />
                                  )}
                                </div>
                                <FileText className="w-3.5 h-3.5 text-[#36B37E] flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                  <p className="text-base text-foreground truncate group-hover:text-[#0052CC]">
                                    {page.title}
                                  </p>
                                  {page.date && (
                                    <span className="text-[10px] text-muted-foreground">
                                      {page.date}
                                    </span>
                                  )}
                                </div>
                                <a
                                  href={confluenceBrowseUrl(page.id, page.title, selectedSpaceKey)}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                                  title="Open in Confluence"
                                >
                                  <ExternalLink className="w-3.5 h-3.5 text-muted-foreground hover:text-[#0052CC]" />
                                </a>
                              </div>
                            )}
                          </div>
                        ))}

                        {hasMore && (
                          <div className="flex justify-center py-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setConfluencePagePage(prev => prev + 1)}
                              className="text-base gap-1.5"
                              style={{ borderColor: '#0052CC', color: '#0052CC' }}
                            >
                              Load More
                            </Button>
                          </div>
                        )}
                          </>);
                        })()}

                        {!confluenceLoading && !confluenceError && (() => {
                          const allPagesCheck = filterConfluencePages(confluencePages);
                          const isSearchActive = confluenceSearch.trim().length > 0;
                          const pagesToCheck = isSearchActive ? allPagesCheck : allPagesCheck.slice(0, confluencePagePage * CONFLUENCE_PAGES_PER_LOAD);
                          return pagesToCheck.length === 0 && allPagesCheck.length === 0;
                        })() && (
                          <div className="text-center py-4">
                            <p className="text-base text-muted-foreground">
                              No pages found
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </Card>
                )}

                {/* Jira Section — conditional on tool configuration (D-16) */}
                {isToolConfigured('jira') && (
                <Card className="overflow-hidden shadow-sm" style={{ backgroundColor: 'var(--sidebar-section-bg)', border: '1px solid var(--sidebar-section-border)', gap: 0 }}>
                  <div 
                    className={`flex items-center justify-between px-3 cursor-pointer transition-all ${expandedSection === 'jira' ? 'py-2.5' : 'py-2.5'}`}
                    style={{ borderBottom: expandedSection === 'jira' ? '1px solid var(--sidebar-section-border)' : 'none', backgroundColor: expandedSection === 'jira' ? 'var(--sidebar-header-bg)' : 'transparent' }}
                    onClick={() => { setExpandedSection(expandedSection === 'jira' ? null : 'jira'); setCronSectionExpanded(false); }}
                  >
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2">
                      <svg className="w-4 h-4 text-[#0052CC]" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005zm5.723-5.756H5.736a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.218 5.218 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001zM23.013 0H11.455a5.215 5.215 0 0 0 5.215 5.215h2.129v2.057A5.215 5.215 0 0 0 24.013 12.487V1.005A1.005 1.005 0 0 0 23.013 0z" />
                      </svg>
                      <h3 className="text-base font-semibold text-foreground">Jira</h3>
                      </div>
                      <span className="text-[10px] text-muted-foreground" style={{ marginLeft: '1.6rem' }}>{selectedJiraIssues.size} {selectedJiraIssues.size === 1 ? 'Story' : 'Stories'}</span>
                    </div>
                    <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform duration-200 ${expandedSection !== 'jira' ? '-rotate-90' : ''}`} />
                  </div>

                  <div
                    ref={jiraRef}
                    className={expandedSection === 'jira' ? 'themed-scroll' : ''}
                    style={{
                      maxHeight: expandedSection === 'jira' ? '600px' : 0,
                      overflowY: expandedSection === 'jira' ? 'auto' : 'hidden',
                      transition: 'max-height 0.3s ease',
                    }}
                  >
                    <div className="p-2">
                      {/* Sub-header with refresh */}
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-base text-muted-foreground font-medium">Epics & User Stories</p>
                        <div className="flex items-center gap-1.5">
                          {selectedJiraIssues.size > 0 && (
                            <button
                              type="button"
                              className="text-muted-foreground hover:text-[#0052CC] transition-colors"
                              onClick={() => setSelectedJiraIssues(new Set())}
                              title="Clear all selections"
                            >
                              <ListX className="w-4 h-4" />
                            </button>
                          )}
                          <button
                            type="button"
                            className={`text-muted-foreground hover:text-[#0052CC] transition-colors ${jiraLoading ? 'animate-spin' : ''}`}
                            onClick={handleJiraRefresh}
                            disabled={jiraLoading}
                            title="Refresh Jira"
                          >
                            <RefreshCw className="w-4 h-4" />
                          </button>
                        </div>
                      </div>

                      {/* Search */}
                      <div className="relative mb-2">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3 h-3" style={{ color: '#0052CC', opacity: 0.5 }} />
                        <Input
                          type="text"
                          placeholder="Search by Jira ID, epic, or description..."
                          value={jiraSearch}
                          onChange={(e) => { setJiraSearch(e.target.value); setJiraEpicPage(1); }}
                          className={`pl-8 ${jiraSearch.trim() ? 'pr-9' : 'pr-3'} text-base`}
                          style={{ backgroundColor: 'var(--sidebar-search-bg)', border: '1px solid var(--sidebar-search-border)' }}
                        />
                        {jiraSearch.trim() && (
                          <button
                            type="button"
                            onClick={() => { setJiraSearch(''); setJiraSearchResults(null); setJiraEpicPage(1); }}
                            className="text-muted-foreground hover:text-foreground transition-colors"
                            style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', zIndex: 10 }}
                            title="Clear search"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>

                      {/* Tree View */}
                      <div
                        className="space-y-1 pr-1 themed-scroll"
                        style={{ maxHeight: '400px', overflowY: 'auto' }}
                      >
                        {/* Loading state */}
                        {(jiraLoading || jiraSearchLoading) && (
                          <div className="flex items-center justify-center py-6">
                            <RefreshCw className="w-4 h-4 animate-spin text-[#0052CC] mr-2" />
                            <p className="text-base text-muted-foreground">{jiraSearchLoading ? 'Searching Jira...' : 'Loading epics...'}</p>
                          </div>
                        )}

                        {/* Error state */}
                        {jiraError && !jiraLoading && (
                          <div className="text-center py-4">
                            <p className="text-base text-red-500 mb-2">{jiraError}</p>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={handleJiraRefresh}
                              className="text-base"
                            >
                              Retry
                            </Button>
                          </div>
                        )}

                        {/* Epics tree */}
                        {!jiraLoading && !jiraSearchLoading && !jiraError && (() => {
                          const isSearchMode = jiraSearch.trim().length > 0;
                          const epicsToRender = isSearchMode && jiraSearchResults !== null
                            ? jiraSearchResults
                            : filterJiraEpics(jiraEpics);
                          const visibleEpics = isSearchMode
                            ? epicsToRender
                            : epicsToRender.slice(0, jiraEpicPage * JIRA_EPICS_PER_PAGE);
                          const hasMore = !isSearchMode && epicsToRender.length > visibleEpics.length;
                          return (<>
                        {visibleEpics.map((epic) => (
                          <div key={epic.key} data-jira-key={epic.key}>
                            {/* Epic row */}
                            <div
                              className="flex items-center space-x-2 p-2 rounded-lg hover:bg-muted/50 cursor-pointer transition-all group"
                              onClick={() => toggleEpicExpand(epic.key)}
                            >
                              {epic.children ? (
                                expandedEpics.has(epic.key) ? (
                                  <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                                ) : (
                                  <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                                )
                              ) : (
                                <ChevronRight className="w-4 h-4 text-muted-foreground/30 flex-shrink-0" />
                              )}
                              {/* Epic checkbox */}
                              {epic.children && epic.children.length > 0 && (
                                <div
                                  className={`w-4 h-4 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors ${jiraSelectionLocked ? 'opacity-60 cursor-not-allowed' : ''} ${
                                    epic.children.every(s => selectedJiraIssues.has(s.key))
                                      ? 'border-[#0052CC] bg-[#0052CC]'
                                      : epic.children.some(s => selectedJiraIssues.has(s.key))
                                        ? 'border-[#0052CC] bg-[#0052CC]/40'
                                        : 'border-muted-foreground'
                                  }`}
                                  onClick={(e) => { e.stopPropagation(); toggleEpicSelection(epic.key); }}
                                >
                                  {epic.children.every(s => selectedJiraIssues.has(s.key)) && (
                                    <Check className="w-3 h-3" style={{ color: isDarkMode ? '#ffffff' : '#1e3a5f' }} />
                                  )}
                                  {!epic.children.every(s => selectedJiraIssues.has(s.key)) && epic.children.some(s => selectedJiraIssues.has(s.key)) && (
                                    <div className="w-2 h-0.5 rounded" style={{ backgroundColor: isDarkMode ? '#ffffff' : '#1e3a5f' }} />
                                  )}
                                </div>
                              )}
                              <div className="flex-1 min-w-0">
                                <p className="text-base text-foreground truncate group-hover:text-[#0052CC]">
                                  <span className="font-medium" style={{ color: '#746FA7' }}>{epic.key}</span> - {epic.summary}
                                </p>
                              </div>
                              <a
                                href={epic.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                                title="Open in Jira"
                              >
                                <ExternalLink className="w-3.5 h-3.5 text-muted-foreground hover:text-[#0052CC]" />
                              </a>
                            </div>

                            {/* User Stories */}
                            {epic.children && expandedEpics.has(epic.key) && (
                              <div
                                className="pl-3 space-y-1 pr-1 themed-scroll"
                                style={{ maxHeight: '500px', overflowY: 'auto', marginLeft: '2.5rem', borderLeft: '2px dotted rgba(0, 82, 204, 0.3)' }}
                              >
                                {epic.children.map((story) => (
                                  <div key={story.key}>
                                    <div
                                      data-jira-key={story.key}
                                      className={`flex items-center space-x-2 p-2 rounded-lg hover:bg-muted/50 transition-all group ${jiraSelectionLocked ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
                                      onClick={() => toggleJiraIssueSelection(story.key)}
                                    >
                                      {/* Selection checkbox */}
                                      <div className={`w-4 h-4 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
                                        selectedJiraIssues.has(story.key)
                                          ? 'border-[#0052CC] bg-[#0052CC]'
                                          : 'border-muted-foreground'
                                      }`}>
                                        {selectedJiraIssues.has(story.key) && (
                                          <Check className="w-3 h-3" style={{ color: isDarkMode ? '#ffffff' : '#1e3a5f' }} />
                                        )}
                                      </div>
                                      <div className="flex-1 min-w-0">
                                        <p className="text-base text-foreground truncate group-hover:text-[#0052CC]">
                                          <span className="font-medium" style={{ color: '#746FA7' }}>{story.key}</span> - {story.summary}
                                        </p>
                                      </div>
                                      <a
                                        href={story.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        onClick={(e) => e.stopPropagation()}
                                        className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                                        title="Open in Jira"
                                      >
                                        <ExternalLink className="w-3.5 h-3.5 text-muted-foreground hover:text-[#0052CC]" />
                                      </a>
                                    </div>

                                    {/* Test Cases sub-dropdown for selected stories */}
                                    {selectedJiraIssues.has(story.key) && (
                                      <div className="mt-1 mb-1" style={{ marginLeft: '1.75rem', paddingLeft: '0.5rem', borderLeft: '2px dotted rgba(52, 152, 179, 0.3)' }}>
                                        <div className="flex items-center gap-2">
                                          {testCasesMap[story.key] && testCasesMap[story.key].length > 0 && (() => {
                                            const tcKeys = testCasesMap[story.key].map(tc => tc.key);
                                            const allSelected = tcKeys.every(k => selectedTestCaseKeys.has(k));
                                            const someSelected = !allSelected && tcKeys.some(k => selectedTestCaseKeys.has(k));
                                            return (
                                              <div
                                                className={`w-4 h-4 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors cursor-pointer ${
                                                  allSelected
                                                    ? 'border-[#3498B3] bg-[#3498B3]'
                                                    : someSelected
                                                      ? 'border-[#3498B3] bg-[#3498B3]/40'
                                                      : 'border-muted-foreground'
                                                }`}
                                                onClick={(e) => { e.stopPropagation(); toggleAllTestCasesForStory(story.key); }}
                                                title={allSelected ? 'Deselect all test cases' : 'Select all test cases'}
                                              >
                                                {allSelected && <Check className="w-3 h-3" style={{ color: isDarkMode ? '#ffffff' : '#1e3a5f' }} />}
                                                {someSelected && <span className="w-1.5 h-0.5 rounded-full" style={{ backgroundColor: isDarkMode ? '#ffffff' : '#1e3a5f' }} />}
                                              </div>
                                            );
                                          })()}
                                          <button
                                            type="button"
                                            className="flex items-center gap-1.5 text-base font-medium text-[#3498B3] hover:text-[#2dd4bf] transition-colors py-1 px-1.5 rounded hover:bg-[#3498B3]/10"
                                            onClick={(e) => { e.stopPropagation(); toggleStoryTestCases(story.key); }}
                                          >
                                            {expandedStoryTestCases.has(story.key) ? (
                                              <ChevronDown className="w-3 h-3" />
                                            ) : (
                                              <ChevronRight className="w-3 h-3" />
                                            )}
                                            <span>Test Cases</span>
                                            {testCasesMap[story.key] && (
                                              <span className="opacity-70">({testCasesMap[story.key].length})</span>
                                            )}
                                          </button>
                                        </div>

                                        {expandedStoryTestCases.has(story.key) && (
                                          <div className="ml-4 mt-1 space-y-0.5 pl-2 overflow-y-auto themed-scroll" style={{ maxHeight: '200px', borderLeft: '2px dotted rgba(52, 152, 179, 0.4)' }}>
                                            {testCasesLoading[story.key] ? (
                                              <div className="flex items-center gap-2 py-1.5 text-base text-muted-foreground">
                                                <RefreshCw className="w-3 h-3 animate-spin text-[#3498B3]" />
                                                <span>Fetching test cases...</span>
                                              </div>
                                            ) : testCasesMap[story.key] && testCasesMap[story.key].length > 0 ? (
                                              testCasesMap[story.key].map((tc) => {
                                                const isSelected = selectedTestCaseKeys.has(tc.key);
                                                return (
                                                <div
                                                  key={tc.key}
                                                  className={`flex items-center gap-2 py-1.5 px-1.5 rounded-lg cursor-pointer transition-colors group ${
                                                    isSelected ? 'bg-[#3498B3]/10' : 'hover:bg-muted/50'
                                                  }`}
                                                  onClick={(e) => { e.stopPropagation(); toggleTestCaseSelection(tc.key); }}
                                                >
                                                  <div className={`w-4 h-4 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
                                                    isSelected
                                                      ? 'border-[#3498B3] bg-[#3498B3]'
                                                      : 'border-muted-foreground'
                                                  }`}>
                                                    {isSelected && (
                                                      <Check className="w-3 h-3" style={{ color: isDarkMode ? '#ffffff' : '#1e3a5f' }} />
                                                    )}
                                                  </div>
                                                  <div className="flex-1 min-w-0">
                                                    <p className="text-base text-foreground truncate">
                                                      <span className="font-medium" style={{ color: '#3498B3' }}>{tc.key}</span>
                                                      <span className="text-muted-foreground">- {tc.summary}</span>
                                                    </p>
                                                  </div>
                                                  <a
                                                    href={tc.url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    onClick={(e) => e.stopPropagation()}
                                                    className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                                                    title="Open in Jira"
                                                  >
                                                    <ExternalLink className="w-3.5 h-3.5 text-muted-foreground hover:text-[#3498B3]" />
                                                  </a>
                                                </div>
                                                );
                                              })
                                            ) : (
                                              <p className="text-base text-muted-foreground py-1.5 px-1.5">No test cases found</p>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}

                        {hasMore && (
                          <div className="flex justify-center py-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setJiraEpicPage(prev => prev + 1)}
                              className="text-base gap-1.5"
                              style={{ borderColor: '#0052CC', color: '#0052CC' }}
                            >
                              Load More
                            </Button>
                          </div>
                        )}
                        </>);
                        })()}

                        {!jiraLoading && !jiraSearchLoading && !jiraError && (() => {
                          const isSearchActive = jiraSearch.trim().length > 0;
                          const epicsToCheck = isSearchActive && jiraSearchResults !== null
                            ? jiraSearchResults
                            : filterJiraEpics(jiraEpics);
                          return epicsToCheck.length === 0;
                        })() && (
                          <div className="text-center py-6">
                            <p className="text-base text-muted-foreground">
                              {jiraSearch.trim() ? 'No matching results found' : 'No epics found'}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </Card>
                )}

                {/* ── Cron Job Status Panel ── */}
                <Card className="overflow-hidden shadow-sm" style={{ backgroundColor: 'var(--sidebar-section-bg)', border: '1px solid var(--sidebar-section-border)', gap: 0 }}>
                  <div
                    className={`flex items-center justify-between px-3 cursor-pointer transition-all ${expandedSection === 'cronJobs' ? 'py-2.5' : 'py-2.5'}`}
                    style={{ borderBottom: expandedSection === 'cronJobs' ? '1px solid var(--sidebar-section-border)' : 'none', backgroundColor: expandedSection === 'cronJobs' ? 'var(--sidebar-header-bg)' : 'transparent' }}
                    onClick={() => { setExpandedSection(expandedSection === 'cronJobs' ? null : 'cronJobs'); setCronSectionExpanded(expandedSection !== 'cronJobs'); }}
                  >
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-[#3498B3]" />
                      <h3 className="text-base font-semibold text-foreground">Cron Job Status</h3>
                      </div>
                      <span className="text-[10px] text-muted-foreground" style={{ marginLeft: '1.6rem' }}>{cronJobs.length} {cronJobs.length === 1 ? 'Job' : 'Jobs'}</span>
                    </div>
                    <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform duration-200 ${expandedSection !== 'cronJobs' ? '-rotate-90' : ''}`} />
                  </div>

                  {expandedSection === 'cronJobs' && (
                    <div className="p-2 space-y-1 themed-scroll" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                      {cronJobs.length === 0 ? (
                        <div className="text-center py-4">
                          <p className="text-base text-muted-foreground">No jobs submitted yet</p>
                          <p className="text-[10px] text-muted-foreground mt-1">Jobs will appear here when test cases are generated</p>
                        </div>
                      ) : (
                        cronJobs.map(job => (
                          <div key={job.jobId}>
                            {/* Job row - like epic row in Jira */}
                            <div
                              className="flex items-center space-x-2 p-2 rounded-lg hover:bg-muted/50 cursor-pointer transition-all group"
                              onClick={() => setExpandedCronJob(prev => prev === job.jobId ? null : job.jobId)}
                            >
                              {expandedCronJob === job.jobId ? (
                                <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                              ) : (
                                <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                              )}
                              <div className="flex-1 min-w-0">
                                <p className="text-base text-foreground truncate group-hover:text-[#3498B3]">
                                  <span className="font-medium text-[#746FA7]">{job.agentType}</span> - {job.jobName}
                                </p>
                                <p className="text-[10px] text-muted-foreground mt-0.5" style={{ wordBreak: 'break-all' }}>
                                  ID: {job.jobId}
                                </p>
                                <span style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', color: getCronStatusColor(getEffectiveJobStatus(job)), display: 'inline-block', marginTop: '2px' }}>
                                  {getEffectiveJobStatus(job)}
                                </span>
                              </div>
                              <div className="flex items-center flex-shrink-0">
                                {getEffectiveJobStatus(job).toLowerCase() === 'partial success' ? (
                                  <button
                                    className="flex items-center gap-1 px-2 py-1 rounded hover:bg-muted/50 transition-all"
                                    style={{ color: 'rgba(251,146,60,0.6)', fontSize: '10px', fontWeight: 600 }}
                                    title="Rerun failed stories"
                                    onClick={(e) => { e.stopPropagation(); handleRerunFailedStories(job.jobId); }}
                                    disabled={cronJobsLoading[job.jobId]}
                                  >
                                    <RotateCcw className={`w-3.5 h-3.5 ${cronJobsLoading[job.jobId] ? 'animate-spin' : ''}`} />
                                    Re-run
                                  </button>
                                ) : (
                                  <button
                                    className="opacity-0 group-hover:opacity-100 p-2 rounded hover:bg-muted/50 transition-all"
                                    title="Refresh status"
                                    onClick={(e) => { e.stopPropagation(); refreshCronJobStatus(job.jobId); }}
                                    disabled={cronJobsLoading[job.jobId]}
                                  >
                                    <RefreshCw className={`w-4 h-4 text-muted-foreground hover:text-[#3498B3] ${cronJobsLoading[job.jobId] ? 'animate-spin' : ''}`} />
                                  </button>
                                )}
                              </div>
                            </div>

                            {/* Expanded stories - like user stories under epic */}
                            {expandedCronJob === job.jobId && (
                              <div
                                className="space-y-1 pr-1 themed-scroll"
                                style={{ marginLeft: '2.5rem', paddingLeft: '0.5rem', borderLeft: '2px dotted rgba(52, 152, 179, 0.3)', maxHeight: '300px', overflowY: 'auto' }}
                              >
                                {/* Progress summary */}
                                {job.detail && job.detail.total > 0 && (
                                  <div className="p-2 rounded-lg bg-muted/30">
                                    <div className="flex items-center justify-between text-[10px] mb-1.5">
                                      <span style={{ color: 'rgba(156,163,175,0.6)' }}>Total: {job.detail.total}</span>
                                      <span style={{ color: 'rgba(74,222,128,0.6)' }}>Done: {job.detail.completed_count}</span>
                                      {job.detail.failed_count > 0 && <span style={{ color: 'rgba(248,113,113,0.6)' }}>Failed: {job.detail.failed_count}</span>}
                                    </div>
                                    {(() => {
                                      const total = job.detail.total;
                                      const done = job.detail.completed_count;
                                      const failed = job.detail.failed_count;
                                      const pct = Math.round(((done + failed) / total) * 100);
                                      const isInProgress = ['running', 'processing', 'queued', 'pending'].includes(job.status.toLowerCase());
                                      return (
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', width: '100%' }}>
                                          <div style={{ flex: 1, display: 'flex', gap: '3px' }}>
                                            {Array.from({ length: total }).map((_, idx) => {
                                              let color = 'rgba(255,255,255,0.06)';
                                              if (idx < done) {
                                                color = 'rgba(74,222,128,0.5)';
                                              } else if (idx < done + failed) {
                                                color = 'rgba(248,113,113,0.5)';
                                              } else if (isInProgress) {
                                                color = 'rgba(250,204,21,0.12)';
                                              }
                                              return (
                                                <div
                                                  key={idx}
                                                  style={{
                                                    flex: 1,
                                                    height: '8px',
                                                    borderRadius: '2px',
                                                    backgroundColor: color,
                                                    transition: 'background-color 0.3s ease',
                                                  }}
                                                />
                                              );
                                            })}
                                          </div>
                                        </div>
                                      );
                                    })()}
                                  </div>
                                )}

                                {/* Stories list - like Jira story rows */}
                                {job.stories && job.stories.length > 0 && job.stories.map((s, i) => {
                                  const detailStory = job.detail?.stories?.find(ds => ds.userStoryJiraId === s.key);
                                  const storyStatusCfg = detailStory ? getStoryStatusConfig(detailStory.status) : null;
                                  return (
                                    <div
                                      key={i}
                                      className="flex items-center space-x-2 p-2 rounded-lg hover:bg-muted/50 transition-all group"
                                    >
                                      <div className="flex-1 min-w-0">
                                        <p className="text-xs text-foreground truncate">
                                          <span className="font-medium text-[#746FA7]">{s.key}</span>{s.summary ? ` - ${s.summary}` : ''}
                                        </p>
                                      </div>
                                      {storyStatusCfg && (
                                        <span style={{ fontSize: '10px', flexShrink: 0, textTransform: 'uppercase', fontWeight: 600, color: storyStatusCfg.color }}>
                                          {detailStory!.status}
                                        </span>
                                      )}
                                    </div>
                                  );
                                })}

                                {/* If no stories but has detail stories */}
                                {(!job.stories || job.stories.length === 0) && job.detail?.stories && job.detail.stories.length > 0 && (
                                  job.detail.stories.map((story, idx) => {
                                    const cfg = getStoryStatusConfig(story.status);
                                    return (
                                      <div
                                        key={idx}
                                        className="flex items-center space-x-2 p-2 rounded-lg hover:bg-muted/50 transition-all group"
                                      >
                                        <div className="flex-1 min-w-0">
                                          <p className="text-xs text-foreground truncate">
                                            <span className="font-medium text-[#746FA7]">{story.userStoryJiraId || `Story ${story.index + 1}`}</span>
                                          </p>
                                        </div>
                                        <span style={{ fontSize: '10px', flexShrink: 0, textTransform: 'uppercase', fontWeight: 600, color: cfg.color }}>
                                          {story.status}
                                        </span>
                                      </div>
                                    );
                                  })
                                )}
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </Card>

                <Card className="overflow-hidden shadow-sm" style={{ backgroundColor: 'var(--sidebar-section-bg)', border: '1px solid var(--sidebar-section-border)', gap: 0 }}>
                  <div
                    className={`flex items-center justify-between px-3 cursor-pointer transition-all ${expandedSection === 'wegaBrain' ? 'py-2.5' : 'py-2.5'}`}
                    style={{ borderBottom: expandedSection === 'wegaBrain' ? '1px solid var(--sidebar-section-border)' : 'none', backgroundColor: expandedSection === 'wegaBrain' ? 'var(--sidebar-header-bg)' : 'transparent' }}
                    onClick={() => { setExpandedSection(expandedSection === 'wegaBrain' ? null : 'wegaBrain'); setCronSectionExpanded(false); }}
                  >
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2">
                        <BookOpen className="w-4 h-4 text-[#746FA7]" />
                        <h3 className="text-base font-semibold text-foreground">Wega Brain</h3>
                      </div>
                      <span className="text-[10px] text-muted-foreground" style={{ marginLeft: '1.6rem' }}>{wegaBrainPrompts.length} {wegaBrainPrompts.length === 1 ? 'Prompt' : 'Prompts'}</span>
                    </div>
                    <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform duration-200 ${expandedSection !== 'wegaBrain' ? '-rotate-90' : ''}`} />
                  </div>

                  <div
                    className={expandedSection === 'wegaBrain' ? 'themed-scroll' : ''}
                    style={{
                      maxHeight: expandedSection === 'wegaBrain' ? '600px' : 0,
                      overflowY: expandedSection === 'wegaBrain' ? 'auto' : 'hidden',
                      transition: 'max-height 0.3s ease',
                    }}
                  >
                  {/* Critical / Non-Critical scope toggle.
                      Default: Critical only. Turn on to ALSO search the non-critical KB
                      (useful when the critical KB returns no answer). */}
                  <div
                    className="px-3 py-2 flex items-center justify-between"
                    style={{ borderBottom: '1px solid var(--sidebar-section-border)' }}
                  >
                    <div className="flex flex-col">
                      <span className="text-[11px] font-medium text-foreground">
                        Search scope
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {wegaBrainIncludeNonCritical
                          ? 'Critical + Non-Critical'
                          : 'Critical only'}
                      </span>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={wegaBrainIncludeNonCritical}
                      title={
                        wegaBrainIncludeNonCritical
                          ? 'Searching critical and non-critical KB. Click to limit to critical only.'
                          : 'Searching critical KB only. Click to also include non-critical.'
                      }
                      onClick={(e) => {
                        e.stopPropagation();
                        setWegaBrainIncludeNonCritical((v) => !v);
                      }}
                      className="relative inline-flex h-4 w-8 items-center rounded-full transition-colors flex-shrink-0"
                      style={{
                        backgroundColor: wegaBrainIncludeNonCritical
                          ? '#746FA7'
                          : 'var(--sidebar-section-border)',
                      }}
                    >
                      <span
                        className="inline-block h-3 w-3 transform rounded-full bg-white transition-transform"
                        style={{
                          transform: wegaBrainIncludeNonCritical
                            ? 'translateX(18px)'
                            : 'translateX(2px)',
                        }}
                      />
                    </button>
                  </div>
                  {/* Project Name Banner */}
                  {derivedProjectName && (<>
                  <div className="px-3 py-2" style={{ borderBottom: '1px solid var(--sidebar-section-border)' }}>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11px] text-muted-foreground">Project Name:</span>
                        <span className="text-base font-medium text-foreground">{derivedProjectName}</span>
                      </div>
                  </div>
                  <div className="p-2 space-y-1">
                    {wegaBrainPrompts.map((prompt) => (
                      <button
                        key={prompt.id}
                        onClick={() => handleWegaBrainPromptSelect(prompt)}
                        className="w-full text-left flex items-center gap-2 px-2 py-2 rounded-md transition-all group"
                        style={{
                          backgroundColor: selectedPromptForChatbot === prompt.title ? 'var(--sidebar-section-hover)' : 'transparent',
                        }}
                        onMouseEnter={(e) => {
                          if (selectedPromptForChatbot !== prompt.title) {
                            e.currentTarget.style.backgroundColor = 'var(--sidebar-section-hover)';
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (selectedPromptForChatbot !== prompt.title) {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }
                        }}
                      >
                        <Sparkles className="w-2.5 h-2.5 text-[#746FA7]/40 flex-shrink-0" />
                        <span className={`text-base transition-colors ${selectedPromptForChatbot === prompt.title ? 'text-[#746FA7]' : 'text-muted-foreground group-hover:text-[#746FA7]'}`}>
                          {prompt.title}
                        </span>
                      </button>
                    ))}
                  </div>
                  </>)}
                  </div>
                </Card>
              </div>
            </div>
            {/* Collapsed sidebar */}
            <div className={`absolute inset-0 flex flex-col items-center bg-card border border-border rounded-lg h-full transition-opacity duration-300 ${!sidebarExpanded ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
              <div className="border-b border-border w-full flex justify-center items-center flex-shrink-0" style={{ minHeight: '73px' }}>
                <button
                  onClick={() => setSidebarExpanded(true)}
                  className="p-1 rounded hover:bg-muted transition-colors"
                  title="Expand sidebar"
                >
                  <span className="text-xl font-bold text-[#3498B3]">&raquo;</span>
                </button>
              </div>
              <div className="flex flex-col items-center space-y-6 pt-4 flex-1 overflow-visible px-3">
              {visibleAgents.length > 0 && (
              <Library className="w-6 h-6 text-[#746FA7] cursor-pointer" onClick={() => { setExpandedSection('promptLibrary'); setCronSectionExpanded(false); setSidebarExpanded(true); }} />
              )}
              {isToolConfigured('confluence') && (
              <div className="relative cursor-pointer" onClick={() => { setExpandedSection('confluence'); setCronSectionExpanded(false); setSidebarExpanded(true); }}>
                <svg className="w-6 h-6 text-[#0052CC]" viewBox="0 0 24 24" fill="currentColor">
                  <title>Confluence</title>
                  <path d="M2.65 18.776c-.198.326-.418.7-.594.998a.543.543 0 0 0 .197.744l3.503 2.129a.543.543 0 0 0 .744-.179c.155-.262.38-.642.62-1.054 1.674-2.88 3.37-2.534 6.434-1.2l3.467 1.508c.268.117.58-.003.706-.266l1.87-4.088a.54.54 0 0 0-.26-.716s-1.84-.794-3.538-1.527c-5.49-2.378-9.867-2.075-13.149 3.651zm18.7-13.552c.198-.326.418-.7.594-.998a.543.543 0 0 0-.197-.744L18.244 1.353a.543.543 0 0 0-.744.179c-.155.262-.38.642-.62 1.054-1.674 2.88-3.37-2.534-6.434 1.2L6.979 2.278a.544.544 0 0 0-.706.266l-1.87 4.088a.54.54 0 0 0 .26.716s1.84.794 3.538 1.527c5.49 2.378 9.867 2.075 13.149-3.651z" />
                </svg>
                {selectedConfluencePages.size > 0 && (
                  <span style={{ position: 'absolute', top: '-6px', right: '-8px', width: '18px', height: '18px', borderRadius: '50%', backgroundColor: '#e31a06', color: '#fff', fontSize: '9px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1, border: '2px solid var(--card)', zIndex: 10 }}>
                    {selectedConfluencePages.size}
                  </span>
                )}
              </div>
              )}
              {isToolConfigured('jira') && (
              <div className="relative cursor-pointer" onClick={() => { setExpandedSection('jira'); setCronSectionExpanded(false); setSidebarExpanded(true); }}>
                <svg className="w-6 h-6 text-[#0052CC]" viewBox="0 0 24 24" fill="currentColor">
                  <title>Jira</title>
                  <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005zm5.723-5.756H5.736a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.218 5.218 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001zM23.013 0H11.455a5.215 5.215 0 0 0 5.215 5.215h2.129v2.057A5.215 5.215 0 0 0 24.013 12.487V1.005A1.005 1.005 0 0 0 23.013 0z" />
                </svg>
                {selectedJiraIssues.size > 0 && (
                  <span style={{ position: 'absolute', top: '-6px', right: '-8px', width: '18px', height: '18px', borderRadius: '50%', backgroundColor: '#e31a06', color: '#fff', fontSize: '9px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1, border: '2px solid var(--card)', zIndex: 10 }}>
                    {selectedJiraIssues.size}
                  </span>
                )}
              </div>
              )}
              <div className="relative cursor-pointer" onClick={() => { setExpandedSection('cronJobs'); setCronSectionExpanded(true); setSidebarExpanded(true); }} title="Cron Job Status">
                <Clock className="w-6 h-6 text-[#3498B3]" />
                {cronJobs.filter(j => j.status === 'running' || j.status === 'queued').length > 0 && (
                  <span style={{ position: 'absolute', top: '-6px', right: '-8px', width: '18px', height: '18px', borderRadius: '50%', backgroundColor: '#e31a06', color: '#fff', fontSize: '9px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1, border: '2px solid var(--card)', zIndex: 10 }}>
                    {cronJobs.filter(j => j.status === 'running' || j.status === 'queued').length}
                  </span>
                )}
              </div>
              <div className="relative cursor-pointer" onClick={() => { setExpandedSection('wegaBrain'); setCronSectionExpanded(false); setSidebarExpanded(true); }} title="Wega Brain">
                <BookOpen className="w-6 h-6 text-[#746FA7]" />
              </div>
              </div>
            </div>
         {/* -- Mani End of Confluence Pages */}
          </div>

          {/* Middle Column - Embedded Chatbot */}
          <div className="flex flex-col min-w-0" style={{ height: '100%', maxHeight: '100%', minHeight: 0 }}>
            <Card className={`flex-1 flex flex-col overflow-hidden gap-0 ${isDarkMode ? 'border border-[#1b2430]' : 'border border-[#e0e4e8]'}`} style={{ background: isDarkMode ? '#0d1117' : '#ffffff' }}>
              {/* Chat Header */}
              <div className="p-3 border-b flex-shrink-0" style={{ minHeight: '73px', background: isDarkMode ? '#161b22' : '#f0f3f6', borderColor: isDarkMode ? '#1b2430' : '#e0e4e8', display: 'flex', alignItems: 'center' }}>
                <div className="flex items-center justify-between w-full">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 rounded-md" style={{ background: 'rgba(52,152,179,0.15)' }}>
                      <Sparkles className="w-5 h-5 text-[#3498B3]" />
                    </div>
                    <h3 className="text-sm font-semibold" style={{ color: isDarkMode ? '#c9d1d9' : '#1f2937', fontFamily: "'JetBrains Mono', 'Fira Code', monospace", letterSpacing: '0.5px' }}>WEGA AI Assistant</h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-md" style={{ background: isDarkMode ? 'rgba(168,85,247,0.10)' : 'rgba(168,85,247,0.07)', border: isDarkMode ? '1px solid rgba(168,85,247,0.30)' : '1px solid rgba(168,85,247,0.25)' }}>
                      <span className="text-[10px] font-medium uppercase tracking-wider" style={{ color: isDarkMode ? '#8b949e' : '#6b7280', letterSpacing: '0.08em' }}>Active Agent</span>
                      <span style={{ width: '1px', height: '14px', background: isDarkMode ? '#30363d' : '#d1d5db' }} />
                      <span className="inline-flex items-center gap-1.5">
                        <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: '#a855f7', animation: 'activeAgentGlow 1.8s ease-in-out infinite' }} />
                        <span className="text-xs font-semibold" style={{ color: '#a855f7', fontFamily: "'JetBrains Mono', 'Fira Code', monospace" }}>{isProcessing ? (agents.find(a => a.active)?.name || 'SDLC Orchestrator') : 'SDLC Orchestrator'}</span>
                      </span>
                    </div>
                    {/* <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium" style={{ background: isDarkMode ? 'rgba(63,185,80,0.12)' : 'rgba(22,163,74,0.1)', color: isDarkMode ? '#3fb950' : '#16a34a', border: isDarkMode ? '1px solid rgba(63,185,80,0.25)' : '1px solid rgba(22,163,74,0.25)' }}>
                      <span className="inline-block w-2 h-2 rounded-full animate-pulse" style={{ background: isDarkMode ? '#3fb950' : '#16a34a' }} />
                      Orchestrator
                    </span> */}
                  </div>
                </div>
              </div>

              {/* Embedded Chatbot Component */}
              <div className="flex-1 overflow-hidden min-h-0">
                  <EmbeddedChatbot
                    ref={chatbotRef}
                    isDarkMode={isDarkMode} 
                    onAgentChange={handleAgentChange}
                    selectedPromptText={selectedPromptForChatbot}
                    selectedNextagentflow={selectedNextagentflowForChatbot}
                    projectName={contextFabricProjectName}
                    productOwner={derivedProductOwner}
                    businessStakeholders={brdStakeholders}
                    selectedJiraStories={selectedJiraStoriesForChatbot}
                    selectedTestCasesFromJira={selectedTestCasesForChatbot}
                    isLoadingTestCases={Object.values(testCasesLoading).some(Boolean)}
                    onJiraSelectionLock={setJiraSelectionLocked}
                    selectedConfluencePageUrl={selectedConfluencePageUrl}
                    onClearSelections={() => {
                      setSelectedJiraIssues(new Set());
                      setSelectedConfluencePages(new Set());
                      setSelectedConfluencePageUrl('');
                    }}
                    onBrdGenerated={handleBrdGenerated}
                    onUserStoryGenerated={handleUserStoryGenerated}
                    onValidatedUserStorySaved={handleValidatedUserStorySaved}
                    onCronJobSubmitted={handleCronJobSubmitted}
                    onOpenProjectTeamModal={() => setShowTeamModal(true)}
                    onOpenProjectSettings={() => { /* Legacy modal removed — tool config is via AdminFAB */ }}
                    onProcessingChange={setIsProcessing}
                    harnessToolConfig={harnessToolConfig}
                    projectId={myProjectId}
                    wegaBrainIncludeNonCritical={wegaBrainIncludeNonCritical}
                  />
              </div>
            </Card>
          </div>

        </div>
      </div>
      </div>

      {/* AI Settings FAB — exact position of old Chat FAB */}
      <div className="fixed bottom-4 right-2 z-40">
        <button
          className="w-12 h-12 rounded-full shadow-lg hover:shadow-2xl text-white flex items-center justify-center transition-all duration-300 hover:scale-105"
          style={{ backgroundColor: isAISettingsOpen ? '#351A55' : '#3498B3' }}
          onClick={() => setIsAISettingsOpen(!isAISettingsOpen)}
          title="AI Settings"
        >
          {isAISettingsOpen ? <X className="size-6" /> : <Sparkles className="size-6" />}
        </button>
      </div>

      {/* Settings Panel — opens to the left of right column */}
      {isAISettingsOpen && createPortal(
        <div 
          className="fixed rounded-xl shadow-2xl border border-white/10 flex flex-col animate-in slide-in-from-bottom-4 fade-in duration-200 overflow-hidden" 
          style={{ 
            zIndex: 41, 
            bottom: '24px', 
            right: '76px', 
            width: '340px',
            maxHeight: 'calc(100vh - 100px)',
            backgroundColor: 'var(--card, #1a1a2e)',
            color: 'var(--card-foreground, #ffffff)',
          }}
        >
          {/* Panel Header */}
          <div className="bg-gradient-to-r from-[#351A55] to-[#3498B3] px-4 py-3 flex items-center gap-3 rounded-t-xl" style={{ flexShrink: 0 }}>
            <div className="w-8 h-8 rounded-lg bg-white/15 backdrop-blur flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-white text-sm font-semibold truncate leading-tight">AI & Pipeline Settings</h3>
              <p className="text-white/60 text-[10px] truncate mt-0.5">Configure AI behavior for this workspace</p>
            </div>
            <button
              onClick={() => setIsAISettingsOpen(false)}
              className="ml-auto text-white/70 hover:text-white hover:bg-white/15 p-1 rounded-md transition-colors flex-shrink-0"
              title="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Panel Body — scrollable */}
          <div className="admin-panel-scroll p-4 space-y-4" style={{ flex: '1 1 auto', overflowY: 'auto', minHeight: 0 }}>
            {/* Quick Actions */}
            <div className="space-y-2.5">
              <button
                onClick={() => { setShowTeamModal(true); setIsAISettingsOpen(false); }}
                className="w-full text-foreground text-xs font-medium pl-7 pr-5 py-3 rounded-lg transition-all duration-200 flex items-center justify-between group border bg-[#8B5CF6]/10 hover:bg-[#8B5CF6]/20 border-[#8B5CF6]/30 hover:border-[#8B5CF6]/50"
              >
                <span className="flex items-center gap-6 min-w-0">
                  <Users className="w-5 h-5 text-[#8B5CF6] flex-shrink-0" />
                  <span className="truncate">Project Stakeholders</span>
                </span>
                <ChevronRight className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0 group-hover:translate-x-0.5 transition-transform duration-200" />
              </button>
              <button
                onClick={() => { setShowContextEnrichModal(true); setIsAISettingsOpen(false); }}
                className={`w-full text-foreground text-xs font-medium pl-7 pr-5 py-3 rounded-lg transition-all duration-200 flex items-center justify-between group border ${
                  showContextEnrichModal
                    ? 'bg-[#E67E22]/25 border-[#E67E22]/60 ring-1 ring-[#E67E22]/40'
                    : 'bg-[#E67E22]/10 hover:bg-[#E67E22]/20 border-[#E67E22]/30 hover:border-[#E67E22]/50'
                }`}
              >
                <span className="flex items-center gap-6 min-w-0">
                  <Database className="w-5 h-5 text-[#E67E22] flex-shrink-0" />
                  <span className="truncate">Context Fabric</span>
                  {showContextEnrichModal && <span className="w-1.5 h-1.5 rounded-full bg-[#E67E22] flex-shrink-0 animate-pulse" />}
                </span>
                <ChevronRight className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0 group-hover:translate-x-0.5 transition-transform duration-200" />
              </button>
            </div>

            {/* Divider */}
            <div className="border-t border-white/10" />
            {/* AI Settings */}
            <div className="space-y-2.5">
              <div className="flex items-center gap-2">
                <Settings className="w-4 h-4 text-[#BE266A]" />
                <h4 className="text-foreground text-xs font-semibold uppercase tracking-wider">AI Settings</h4>
              </div>

              {/* LLM Selection */}
              <div className="space-y-3 bg-muted/20 border border-border/40 rounded-md px-2.5 py-2">
                <Label htmlFor="llm-select" className="text-xs">Language Model</Label>
                <Select value={selectedLLM} onValueChange={setSelectedLLM}>
                  <SelectTrigger id="llm-select" className="bg-background border-[#3498B3]/30 h-8 text-xs text-foreground hover:border-[#3498B3]/60 focus:ring-[#3498B3]/30">
                    <SelectValue placeholder="Select LLM" />
                  </SelectTrigger>
                  <SelectContent style={{ zIndex: 9999 }} className="bg-card border-[#3498B3]/30">
                    <SelectItem value="gpt-4">GPT-4</SelectItem>
                    <SelectItem value="gpt-4-turbo">GPT-4 Turbo</SelectItem>
                    <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
                    <SelectItem value="claude-3-opus">Claude 3 Opus</SelectItem>
                    <SelectItem value="claude-3-sonnet">Claude 3 Sonnet</SelectItem>
                    <SelectItem value="gemini-pro">Gemini Pro</SelectItem>
                    <SelectItem value="llama-2-70b">LLaMA 2 70B</SelectItem>
                    <SelectItem value="mixtral-8x7b">Mixtral 8x7B</SelectItem>
                    <SelectItem value="glm-5">GLM-5</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-[10px] text-muted-foreground">
                  Currently using {selectedLLM}
                </p>
              </div>

              {/* Temperature */}
              <div className="space-y-3 bg-muted/20 border border-border/40 rounded-md px-2.5 py-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs">Temperature</Label>
                  <span className="text-xs text-muted-foreground">{temperature[0]}</span>
                </div>
                <Slider
                  value={temperature}
                  onValueChange={setTemperature}
                  min={0}
                  max={1}
                  step={0.1}
                  className="w-full"
                />
                <p className="text-[10px] text-muted-foreground">
                  Controls randomness. Lower = focused, Higher = creative
                </p>
              </div>

              {/* Max Tokens */}
              <div className="space-y-3 bg-muted/20 border border-border/40 rounded-md px-2.5 py-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs">Max Tokens</Label>
                  <span className="text-xs text-muted-foreground">{maxTokens[0]}</span>
                </div>
                <Slider
                  value={maxTokens}
                  onValueChange={setMaxTokens}
                  min={256}
                  max={4096}
                  step={256}
                  className="w-full"
                />
                <p className="text-[10px] text-muted-foreground">
                  Maximum length of the response
                </p>
              </div>

              {/* Streaming */}
              <div className="space-y-1.5 bg-muted/20 border border-border/40 rounded-md px-2.5 py-2">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-xs">Enable Streaming</Label>
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      Stream responses in real-time
                    </p>
                  </div>
                  <Switch
                    checked={enableStreaming}
                    onCheckedChange={setEnableStreaming}
                  />
                </div>
              </div>

              {/* Project Onboarding - Show when confirmedCreateBrd */}
              {currentNextagentflow === 'confirmedCreateBrd' && (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <Label className="text-[#3498B3] text-xs">Project Onboarding</Label>
                    <p className="text-[10px] text-muted-foreground">Add optional stakeholders</p>
                    
                    <Button
                      type="button"
                      onClick={() => setShowOnboardingPopup(true)}
                      className="bg-gradient-to-br from-[#351A55] to-[#3498B3] hover:from-[#2a1544] hover:to-[#2a7a99] text-white text-xs px-3 py-1 h-7"
                    >
                      + Add Stakeholders
                    </Button>

                    {brdStakeholders.slice(1).some(s => s.name.trim()) && (
                      <div className="space-y-1">
                        <p className="text-[10px] font-medium">Added Stakeholders:</p>
                        <div className="space-y-1">
                          {brdStakeholders.slice(1).filter(s => s.name.trim()).map((s, idx) => (
                            <div key={idx} className="flex items-center justify-between text-[10px] bg-muted/50 px-2 py-1 rounded">
                              <span><Badge variant="outline" className="text-[9px] mr-1">{s.role}</Badge>{s.name}</span>
                              <button
                                type="button"
                                onClick={() => {
                                  const roleIdx = brdStakeholders.findIndex(st => st.role === s.role);
                                  if (roleIdx > 0) {
                                    const updated = [...brdStakeholders];
                                    updated[roleIdx] = { ...updated[roleIdx], name: '', email: '' };
                                    setBrdStakeholders(updated);
                                  }
                                }}
                                className="text-red-500 hover:text-red-700"
                              >
                                ├ù
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </>
              )}

              {/* Stakeholder Details Popup Modal - Full Table */}
              {showOnboardingPopup && (
                <div 
                  className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
                  onClick={(e) => {
                    if (e.target === e.currentTarget) {
                      setShowOnboardingPopup(false);
                    }
                  }}
                >
                  <div className="bg-background border border-border rounded-lg shadow-xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
                    <div className="flex justify-center items-center mb-4 relative">
                      <h3 className="text-lg font-semibold text-[#3498B3]">Project Onboarding - Stakeholders</h3>
                      <button
                        type="button"
                        onClick={() => setShowOnboardingPopup(false)}
                        className="absolute right-0 text-muted-foreground hover:text-foreground text-xl font-bold"
                      >
                        ├ù
                      </button>
                    </div>
                    
                    <table className="w-full border-collapse border border-border text-sm">
                      <thead>
                        <tr className="bg-gradient-to-r from-[#351A55] to-[#3498B3]">
                          <th className="border border-border px-3 py-2 font-medium text-white">Roles</th>
                          <th className="border border-border px-3 py-2 font-medium text-white">Stakeholder's Names</th>
                          <th className="border border-border px-3 py-2 font-medium text-white">Stakeholder's Emails</th>
                        </tr>
                      </thead>
                      <tbody>
                        {brdStakeholders.slice(1).map((stakeholder, idx) => (
                          <tr key={idx + 1}>
                            <td className="border border-border px-3 py-2 bg-muted/50">
                              <span className="font-medium">{stakeholder.role}</span>
                            </td>
                            <td className="border border-border px-3 py-2">
                              <Input
                                type="text"
                                placeholder="Enter name..."
                                value={stakeholder.name}
                                onChange={(e) => {
                                  const updated = [...brdStakeholders];
                                  updated[idx + 1] = { ...updated[idx + 1], name: e.target.value };
                                  setBrdStakeholders(updated);
                                }}
                                className="text-sm"
                              />
                            </td>
                            <td className="border border-border px-3 py-2">
                              <Input
                                type="email"
                                placeholder="Enter email..."
                                value={stakeholder.email}
                                onChange={(e) => {
                                  const updated = [...brdStakeholders];
                                  updated[idx + 1] = { ...updated[idx + 1], email: e.target.value };
                                  setBrdStakeholders(updated);
                                }}
                                className="text-sm"
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    
                    <div className="mt-4 flex justify-end">
                      <Button
                        type="button"
                        onClick={() => setShowOnboardingPopup(false)}
                        className="bg-gradient-to-br from-[#351A55] to-[#3498B3] hover:from-[#2a1544] hover:to-[#2a7a99] text-white text-xs px-4 py-2"
                      >
                        Done
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Team Management Modal - rendered via portal to document.body */}
      {showTeamModal && createPortal(
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center px-4 py-10"
          style={{ zIndex: 9999999 }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowTeamModal(false); }}
        >
          <div
            className="bg-background border border-border rounded-xl w-full max-w-3xl shadow-2xl flex flex-col"
            style={{ maxHeight: 'calc(100vh - 3rem)', minHeight: '70vh' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border flex-shrink-0">
              <div>
                <h3 className="text-base font-bold text-foreground">{projectTeamConfig.modal.title}</h3>
                <p className="text-xs text-muted-foreground mt-0.5">{projectTeamConfig.modal.subtitle}</p>
              </div>
              <button
                onClick={() => setShowTeamModal(false)}
                className="text-muted-foreground hover:text-foreground p-1.5 hover:bg-muted rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto themed-scroll px-6 py-6 min-h-0">
              {/* Project Details Section */}
              <div className="mb-6 bg-gradient-to-r from-blue-950/30 to-purple-950/30 border border-blue-800/30 rounded-lg p-2">
                <div className="flex items-center gap-2 mb-6">
                  <div className="w-5 h-5 rounded bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
                    <FileText className="w-3 h-3 text-white" />
                  </div>
                  <h4 className="text-sm font-semibold text-foreground">{projectTeamConfig.projectDetails.sectionTitle}</h4>
                </div>
                <div className="space-y-6">
                  <div>
                    <label className="text-xs text-muted-foreground mb-3 block">{projectTeamConfig.projectDetails.fields.name.label} {projectTeamConfig.projectDetails.fields.name.required && <span className="text-red-500">*</span>}</label>
                    <input
                      type="text"
                      value={adminProjectDetails.name}
                      onChange={(e) => setAdminProjectDetails({ ...adminProjectDetails, name: e.target.value })}
                      placeholder={projectTeamConfig.projectDetails.fields.name.placeholder}
                      className="w-full bg-background border border-border rounded-md px-4 py-2.5 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-blue-500 transition-colors"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground mb-3 block">{projectTeamConfig.projectDetails.fields.location.label}</label>
                    <input
                      type="text"
                      value={adminProjectDetails.location}
                      onChange={(e) => setAdminProjectDetails({ ...adminProjectDetails, location: e.target.value })}
                      placeholder={projectTeamConfig.projectDetails.fields.location.placeholder}
                      className="w-full bg-background border border-border rounded-md px-4 py-2.5 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-blue-500 transition-colors"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground mb-3 block">{projectTeamConfig.projectDetails.fields.technologies.label}</label>
                    <div className="flex gap-2 mb-2">
                      <input
                        type="text"
                        value={adminTechInput}
                        onChange={(e) => setAdminTechInput(e.target.value)}
                        onKeyPress={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            addAdminTechnology();
                          }
                        }}
                        placeholder={projectTeamConfig.projectDetails.fields.technologies.placeholder}
                        className="flex-1 bg-background border border-border rounded-md px-4 py-2.5 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-blue-500 transition-colors"
                      />
                      <button
                        onClick={addAdminTechnology}
                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition-colors flex items-center gap-1"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        {projectTeamConfig.projectDetails.fields.technologies.addButtonText}
                      </button>
                    </div>
                    {adminProjectDetails.technologies.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {adminProjectDetails.technologies.map((tech, index) => (
                          <div
                            key={index}
                            className="bg-blue-500/20 border border-blue-500/40 rounded-md px-2.5 py-1 flex items-center gap-1.5 group hover:bg-blue-500/30 transition-colors"
                          >
                            <span className="text-xs text-blue-300 font-medium">{tech}</span>
                            <button
                              onClick={() => removeAdminTechnology(tech)}
                              className="text-blue-400 hover:text-blue-200 transition-colors"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Team Members Section */}
              <div className="flex items-center gap-2 mb-4">
                <div className="w-5 h-5 rounded bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                  <Users className="w-3 h-3 text-white" />
                </div>
                <h4 className="text-sm font-semibold text-foreground">{projectTeamConfig.teamMembers.sectionTitle}</h4>
              </div>

              <div className="space-y-3">
                {adminTeamMembers.map((member, index) => (
                  <div
                    key={member.id}
                    className="bg-muted/30 border border-border rounded-lg p-4 hover:border-muted-foreground/30 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-white font-bold text-xs">
                        {index + 1}
                      </div>
                      <div className="flex-1 flex items-end gap-3">
                        <div className="flex-1">
                          <label className="text-[10px] text-muted-foreground mb-1 block">{projectTeamConfig.teamMembers.fields.role.label}</label>
                          <input
                            type="text"
                            value={member.role}
                            onChange={(e) => updateAdminTeamMember(member.id, 'role', e.target.value)}
                            placeholder={projectTeamConfig.teamMembers.fields.role.placeholder}
                            readOnly={member.role === projectTeamConfig.teamMembers.mandatoryRole}
                            className={`w-full bg-background border border-border rounded-md px-3 py-1.5 text-xs text-foreground placeholder-muted-foreground focus:outline-none focus:border-purple-500 transition-colors ${member.role === projectTeamConfig.teamMembers.mandatoryRole ? 'cursor-not-allowed opacity-70' : ''}`}
                          />
                        </div>
                        <div className="flex-1">
                          <label className="text-[10px] text-muted-foreground mb-1 block">{projectTeamConfig.teamMembers.fields.name.label} {member.role === projectTeamConfig.teamMembers.mandatoryRole && <span className="text-red-500">*</span>}</label>
                          <input
                            type="text"
                            value={member.name}
                            onChange={(e) => updateAdminTeamMember(member.id, 'name', e.target.value)}
                            placeholder={projectTeamConfig.teamMembers.fields.name.placeholder}
                            className={`w-full bg-background border rounded-md px-3 py-1.5 text-xs text-foreground placeholder-muted-foreground focus:outline-none focus:border-purple-500 transition-colors ${teamValidationErrors[member.id]?.includes('name') ? 'border-red-500' : 'border-border'}`}
                          />
                          {teamValidationErrors[member.id]?.includes('name') && (
                            <p className="text-[10px] text-red-500 mt-0.5">Required</p>
                          )}
                        </div>

                        <div className="flex-1">
                          <label className="text-[10px] text-muted-foreground mb-1 block">{projectTeamConfig.teamMembers.fields.email.label} {member.role === projectTeamConfig.teamMembers.mandatoryRole && <span className="text-red-500">*</span>}</label>
                          <input
                            type="email"
                            value={member.email}
                            onChange={(e) => updateAdminTeamMember(member.id, 'email', e.target.value)}
                            placeholder={projectTeamConfig.teamMembers.fields.email.placeholder}
                            className={`w-full bg-background border rounded-md px-3 py-1.5 text-xs text-foreground placeholder-muted-foreground focus:outline-none focus:border-purple-500 transition-colors ${teamValidationErrors[member.id]?.includes('email') || teamValidationErrors[member.id]?.includes('emailInvalid') ? 'border-red-500' : 'border-border'}`}
                          />
                          {teamValidationErrors[member.id]?.includes('email') && (
                            <p className="text-[10px] text-red-500 mt-0.5">Required</p>
                          )}
                          {teamValidationErrors[member.id]?.includes('emailInvalid') && (
                            <p className="text-[10px] text-red-500 mt-0.5">Invalid email format</p>
                          )}
                        </div>
                      </div>
                      {member.role !== projectTeamConfig.teamMembers.mandatoryRole && (
                        <button
                          onClick={() => removeAdminTeamMember(member.id)}
                          className="flex-shrink-0 text-red-400 hover:text-red-300 hover:bg-red-500/10 p-1.5 rounded-lg transition-colors"
                          title="Remove member"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <button
                onClick={addAdminTeamMember}
                className="mt-4 w-full border-2 border-dashed border-border hover:border-purple-500 rounded-lg px-4 py-2.5 text-muted-foreground hover:text-purple-400 transition-colors flex items-center justify-center gap-2 group"
              >
                <Plus className="w-4 h-4 group-hover:scale-110 transition-transform" />
                <span className="text-xs font-medium">{projectTeamConfig.modal.addMemberButtonText}</span>
              </button>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-border bg-muted/30 rounded-b-xl flex-shrink-0 space-y-2">
              {teamSaveError && (
                <p className="text-xs text-red-500 font-medium">{teamSaveError}</p>
              )}
              <div className="flex items-center justify-between gap-4">
              <p className="text-xs text-muted-foreground">
                {adminTeamMembers.length} team member{adminTeamMembers.length !== 1 ? 's' : ''} configured
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowTeamModal(false)}
                  className="px-4 py-1.5 rounded-lg border border-border text-muted-foreground hover:bg-muted transition-colors text-sm font-medium"
                >
                  {projectTeamConfig.modal.cancelButtonText}
                </button>
                <button
                  onClick={saveAdminTeam}
                  className="px-4 py-1.5 rounded-lg bg-gradient-to-r from-[#351A55] to-[#3498B3] hover:from-[#2a1544] hover:to-[#2a7a99] text-white transition-all text-sm font-semibold"
                >
                  {projectTeamConfig.modal.saveButtonText}
                </button>
              </div>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}


      {/* Context Fabric / Enrichment Modal */}
      {showContextEnrichModal && createPortal(
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center px-4 py-10"
          style={{ zIndex: 9999999 }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowContextEnrichModal(false); }}
        >
          <div
            className="bg-background border border-border rounded-xl w-full max-w-3xl shadow-2xl flex flex-col overflow-hidden"
            style={{ maxHeight: 'calc(100vh - 3rem)' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header - Enhanced with gradient and icon */}
            <div className="relative px-6 py-5 border-b border-border flex-shrink-0">
              {/* Decorative background elements */}
              <div className="absolute inset-0 overflow-hidden">
                <div className="absolute -top-10 -right-10 w-32 h-32 bg-[#E67E22]/10 rounded-full blur-3xl" />
                <div className="absolute -top-5 right-20 w-20 h-20 bg-purple-500/10 rounded-full blur-2xl" />
              </div>
              
              <div className="relative flex items-start justify-between">
                <div className="flex items-center gap-4">
                  {/* RAG Icon with animated glow */}
                  <div className="relative">
                    <div className="absolute inset-0 bg-[#E67E22]/30 rounded-xl blur-lg animate-pulse" />
                    <div className="relative w-12 h-12 bg-gradient-to-br from-[#E67E22] to-[#D35400] rounded-xl flex items-center justify-center shadow-lg">
                      <Brain className="w-6 h-6 text-white" />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
                      Context Fabric
                      <Sparkles className="w-4 h-4 text-[#E67E22]" />
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1.5">
                      <Zap className="w-3 h-3 text-[#E67E22]" />
                      Intelligent RAG-powered knowledge ingestion
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowContextEnrichModal(false)}
                  className="text-muted-foreground hover:text-foreground p-1.5 hover:bg-muted rounded-lg transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto px-6 py-6 min-h-0 space-y-5">
              {/* URL Section */}
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500/20 to-cyan-500/20 border border-blue-500/30 flex items-center justify-center">
                    <Globe className="w-4 h-4 text-blue-400" />
                  </div>
                  <div>
                    <label className="text-base font-semibold text-foreground">Web Sources</label>
                    <p className="text-[10px] text-muted-foreground">Add URLs to ingest content from websites</p>
                  </div>
                </div>
                <div className="space-y-2 pl-10">
                  {contextEnrichUrls.map((url, index) => (
                    <div key={index} className="flex items-center gap-2 group">
                      <div className="flex-1 relative">
                        <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <input
                          type="text"
                          value={url}
                          onChange={(e) => {
                            const newUrls = [...contextEnrichUrls];
                            newUrls[index] = e.target.value;
                            setContextEnrichUrls(newUrls);
                            setContextEnrichStatus('idle');
                          }}
                          placeholder="https://example.com or Confluence page..."
                          className="w-full bg-background border border-border rounded-lg pl-10 pr-3 py-2.5 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-[#E67E22] focus:ring-1 focus:ring-[#E67E22]/30 transition-all"
                          onKeyDown={(e) => { if (e.key === 'Enter') handleContextEnrichSubmit(); }}
                        />
                      </div>
                      {/* Show + button only when this URL has content */}
                      {url.trim() && index === contextEnrichUrls.length - 1 && (
                        <button
                          type="button"
                          onClick={() => { setContextEnrichUrls([...contextEnrichUrls, '']); setContextEnrichStatus('idle'); }}
                          className="p-2 text-[#E67E22] hover:text-[#D35400] bg-[#E67E22]/10 hover:bg-[#E67E22]/20 rounded-lg transition-all"
                          title="Add another URL"
                        >
                          <Plus className="w-4 h-4" />
                        </button>
                      )}
                      {contextEnrichUrls.length > 1 && (
                        <button
                          type="button"
                          onClick={() => {
                            const newUrls = contextEnrichUrls.filter((_, i) => i !== index);
                            setContextEnrichUrls(newUrls);
                            setContextEnrichStatus('idle');
                          }}
                          className="p-2 text-muted-foreground hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                          title="Remove URL"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  ))}
                  {contextEnrichUrls.filter(u => u.trim()).length > 1 && (
                    <p className="text-[10px] text-[#E67E22] font-medium">{contextEnrichUrls.filter(u => u.trim()).length} URLs ready for ingestion</p>
                  )}
                  {contextEnrichLoading && contextEnrichUrls.some(u => u.trim()) && (
                    <div className="flex items-center gap-2 mt-2">
                      <Zap className="w-3 h-3 text-[#E67E22] flex-shrink-0" />
                      <div className="flex-1 h-[2px] bg-border rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-[#E67E22] to-[#D35400] rounded-full transition-all duration-300 ease-out" style={{ width: `${contextEnrichProgress}%` }} />
                      </div>
                      <span className="text-[10px] text-muted-foreground tabular-nums">{contextEnrichProgress}%</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Divider */}
              <div className="flex items-center gap-3 px-10">
                <div className="flex-1 h-px bg-border" />
                <span className="text-xs text-muted-foreground font-medium">OR</span>
                <div className="flex-1 h-px bg-border" />
              </div>

              {/* File Upload Section */}
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#E67E22]/20 to-orange-500/20 border border-[#E67E22]/30 flex items-center justify-center">
                    <Upload className="w-4 h-4 text-[#E67E22]" />
                  </div>
                  <div>
                    <label className="text-base font-semibold text-foreground">Document Upload</label>
                    <p className="text-[10px] text-muted-foreground">Upload files to enrich your knowledge base</p>
                  </div>
                </div>
                <div className="pl-10">
                  {/* Uploaded files list */}
                  {contextEnrichFiles.length > 0 && (
                    <div className="space-y-2 mb-3">
                      {contextEnrichFiles.map((file, index) => (
                        <div key={index} className="flex items-center gap-2 bg-gradient-to-r from-[#E67E22]/10 to-transparent border border-[#E67E22]/20 rounded-lg px-3 py-2.5 group">
                          <div className="w-8 h-8 rounded-lg bg-[#E67E22]/20 flex items-center justify-center flex-shrink-0">
                            <FileText className="w-4 h-4 text-[#E67E22]" />
                          </div>
                          <span className="text-sm text-foreground flex-1 truncate">{file.name}</span>
                          <span className="text-[10px] text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</span>
                          {index === contextEnrichFiles.length - 1 && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                contextEnrichFileInputRef.current?.click();
                              }}
                              className="p-1.5 text-[#E67E22] hover:text-[#D35400] bg-[#E67E22]/10 hover:bg-[#E67E22]/20 rounded-lg transition-all"
                              title="Add another file"
                            >
                              <Plus className="w-4 h-4" />
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setContextEnrichFiles(contextEnrichFiles.filter((_, i) => i !== index));
                              setContextEnrichStatus('idle');
                            }}
                            className="p-1.5 text-muted-foreground hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                            title="Remove file"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  {/* Drop zone */}
                  {contextEnrichFiles.length === 0 && (
                    <div
                      className="relative border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer border-border hover:border-[#E67E22]/50 hover:bg-[#E67E22]/5 group"
                      onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
                      onDrop={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const droppedFiles = Array.from(e.dataTransfer.files || []);
                        if (droppedFiles.length > 0) {
                          setContextEnrichFiles([...contextEnrichFiles, ...droppedFiles]);
                          setContextEnrichStatus('idle');
                        }
                      }}
                      onClick={() => contextEnrichFileInputRef.current?.click()}
                    >
                      <div className="flex flex-col items-center gap-3">
                        <div className="w-12 h-12 rounded-xl bg-muted group-hover:bg-[#E67E22]/10 flex items-center justify-center transition-all">
                          <Upload className="w-6 h-6 text-muted-foreground group-hover:text-[#E67E22] transition-colors" />
                        </div>
                        <div>
                          <p className="text-sm text-foreground font-medium">Drop files here or click to browse</p>
                          <p className="text-xs text-muted-foreground mt-1">PDF, DOCX, TXT, MD and other text files</p>
                        </div>
                      </div>
                    </div>
                  )}
                  <input
                    ref={contextEnrichFileInputRef}
                    type="file"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) {
                        setContextEnrichFiles([...contextEnrichFiles, f]);
                        setContextEnrichStatus('idle');
                        if (contextEnrichFileInputRef.current) contextEnrichFileInputRef.current.value = '';
                      }
                    }}
                  />
                  {contextEnrichFiles.length > 1 && (
                    <p className="text-[10px] text-[#E67E22] font-medium mt-2">{contextEnrichFiles.length} files ready for upload</p>
                  )}
                  {contextEnrichLoading && contextEnrichFiles.length > 0 && (
                    <div className="flex items-center gap-2 mt-2">
                      <Zap className="w-3 h-3 text-[#E67E22] flex-shrink-0" />
                      <div className="flex-1 h-[2px] bg-border rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-[#E67E22] to-[#D35400] rounded-full transition-all duration-300 ease-out" style={{ width: `${contextEnrichProgress}%` }} />
                      </div>
                      <span className="text-[10px] text-muted-foreground tabular-nums">{contextEnrichProgress}%</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Status Message */}
              {contextEnrichStatus !== 'idle' && (
                <div className={`flex items-center gap-2 pl-10 py-2 rounded-xl ${
                  contextEnrichStatus === 'success' 
                    ? '' 
                    : ''
                }`}>
                  {contextEnrichStatus === 'success' ? (
                    <Check className="w-4 h-4 text-green-400 flex-shrink-0" />
                  ) : (
                    <X className="w-4 h-4 text-red-400 flex-shrink-0" />
                  )}
                  <p className={`text-sm ${contextEnrichStatus === 'success' ? 'text-green-400' : 'text-red-400'}`}>
                    {contextEnrichMessage}
                  </p>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-between px-6 py-4 border-t border-border bg-background flex-shrink-0">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Database className="w-3.5 h-3.5" />
                <span>Powered by RAG Pipeline</span>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setShowContextEnrichModal(false)}
                  className="px-4 py-2 rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-muted transition-all text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={handleContextEnrichSubmit}
                  disabled={contextEnrichLoading || (contextEnrichUrls.every(u => !u.trim()) && contextEnrichFiles.length === 0)}
                  className="px-5 py-2 rounded-lg bg-gradient-to-r from-[#E67E22] to-[#D35400] hover:from-[#D35400] hover:to-[#C0392B] disabled:from-muted disabled:to-muted disabled:text-muted-foreground text-white transition-all text-sm font-semibold flex items-center gap-2 shadow-lg shadow-[#E67E22]/20 disabled:shadow-none"
                >
                  {contextEnrichLoading ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4" />
                      Proceed
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
    </div>
  );
}
