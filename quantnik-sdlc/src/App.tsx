import { useState, useEffect, useRef, type CSSProperties, type ReactNode } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { MarketingLandingPage } from './components/MarketingLandingPage';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import { AdminFAB } from './components/AdminFAB';
import { CodeRepo } from './components/CodeRepo';
import { RepoDetails } from './components/RepoDetails';
import { FileBrowser } from './components/FileBrowser';
import { FileViewer } from './components/FileViewer';
import { Pipelines } from './components/Pipelines';
import { PipelineStudio } from './components/PipelineStudio';
import { DemoVideos } from './components/DemoVideos';
import { VideoPlayer } from './components/VideoPlayer';
import { MLOpsWorkspace } from './components/MLOpsWorkspace';
import { Enablement } from './components/Enablement';
import { Demo } from './components/Demo';
import { University } from './components/University';
import { Support } from './components/Support';
import { About } from './components/About';
import { Contact } from './components/Contact';
import { Execute } from './components/Execute';
import { PMDashboard } from './components/PMDashboard';
import { MarketResearchAgent } from './components/MarketResearchAgent';
import { Toaster } from './components/ui/sonner';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { ProtectedRoute } from './auth/ProtectedRoute';
import { FirstLoginGuard } from './auth/FirstLoginGuard';
import { AuthzGuard } from './auth/AuthzGuard';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';

interface Repository {
  name: string;
  description: string;
  project: string;
  language: string;
  stars: number;
  watchers: number;
  lastUpdated: string;
  status: string;
  branches: number;
  pullRequests: number;
}

interface Pipeline {
  id: string;
  name: string;
  repository: string;
  branch: string;
  status: 'running' | 'success' | 'failed' | 'pending' | 'cancelled';
  lastRun: string;
  duration: string;
  commitHash: string;
  commitMessage: string;
  author: string;
  buildNumber: number;
}

function AppContent() {
  const navigate = useNavigate();
  const { isAuthenticated, isLoading } = useAuth();
  const AUTH_ENABLED = import.meta.env.VITE_AUTH_ENABLED === 'true';

  const [selectedRepository, setSelectedRepository] = useState<Repository | null>(null);
  const [selectedPipeline, setSelectedPipeline] = useState<Pipeline | null>(null);
  const [currentFolderPath, setCurrentFolderPath] = useState<string>('');
  const [currentFilePath, setCurrentFilePath] = useState<string>('');
  const [isDarkMode, setIsDarkMode] = useState<boolean>(false);
  const [selectedVideo, setSelectedVideo] = useState<{ title: string; url: string } | null>(null);

  // Measure fixed header height and expose as CSS variable
  const headerRef = useRef<HTMLElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const measure = () => {
      if (headerRef.current && rootRef.current) {
        const h = headerRef.current.getBoundingClientRect().height;
        rootRef.current.style.setProperty('--header-height', `${h}px`);
      }
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, []);

  // Set document title
  useEffect(() => {
    document.title = 'QUANTNIK - Enterprise Software Engineering Platform';
  }, []);

  // Handle dark mode toggle - defaults to dark theme
  useEffect(() => {
    const savedTheme = localStorage.getItem('buildiq-theme');
    // Default to dark theme if no saved preference
    const shouldUseDark = savedTheme === 'dark' || savedTheme === null;
    
    setIsDarkMode(shouldUseDark);
    if (shouldUseDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, []);

  const toggleTheme = () => {
    const newDarkMode = !isDarkMode;
    setIsDarkMode(newDarkMode);
    
    if (newDarkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('buildiq-theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('buildiq-theme', 'light');
    }
  };

  const navigateToCodeRepo = () => {
    navigate('/coderepo');
    window.scrollTo(0, 0);
  };

  const scrollToSignup = () => {
    const signupSection = document.getElementById('signup-section');
    if (signupSection) {
      signupSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const navigateToPipelines = () => {
    navigate('/pipelines');
    window.scrollTo(0, 0);
  };

  const navigateToPipelineStudio = (pipeline: Pipeline) => {
    setSelectedPipeline(pipeline);
    navigate('/pipelinestudio');
    window.scrollTo(0, 0);
  };

  const navigateToDashboard = () => {
    navigate('/');
    window.scrollTo(0, 0);
  };

  const navigateToRepoDetails = (repository: Repository) => {
    setSelectedRepository(repository);
    navigate('/repodetails');
    window.scrollTo(0, 0);
  };

  const navigateBackToCodeRepo = () => {
    navigate('/coderepo');
    window.scrollTo(0, 0);
  };

  const navigateToFileBrowser = (repository: Repository, folderPath: string) => {
    setSelectedRepository(repository);
    setCurrentFolderPath(folderPath);
    navigate('/filebrowser');
    window.scrollTo(0, 0);
  };

  const navigateToFileViewer = (repository: Repository, filePath: string) => {
    setSelectedRepository(repository);
    setCurrentFilePath(filePath);
    navigate('/fileviewer');
    window.scrollTo(0, 0);
  };

  const navigateToFolder = (folderPath: string) => {
    setCurrentFolderPath(folderPath);
  };

  const navigateToFile = (filePath: string) => {
    setCurrentFilePath(filePath);
    navigate('/fileviewer');
    window.scrollTo(0, 0);
  };

  const navigateToDemoVideos = () => {
    navigate('/demovideos');
    window.scrollTo(0, 0);
  };

  const navigateToVideoPlayer = (videoTitle: string, videoUrl: string) => {
    setSelectedVideo({ title: videoTitle, url: videoUrl });
    navigate('/videoplayer');
    window.scrollTo(0, 0);
  };

  const navigateBackToDemoVideos = () => {
    navigate('/demovideos');
    window.scrollTo(0, 0);
  };

  const navigateToMLOps = () => {
    navigate('/mlops');
    window.scrollTo(0, 0);
  };

  const navigateToEnablement = () => {
    navigate('/enablement');
    window.scrollTo(0, 0);
  };

  const navigateToDemo = () => {
    navigate('/demo');
    window.scrollTo(0, 0);
  };

  const navigateToUniversity = () => {
    navigate('/university');
    window.scrollTo(0, 0);
  };

  const navigateToSupport = () => {
    navigate('/support');
    window.scrollTo(0, 0);
  };

  const navigateToAbout = () => {
    navigate('/about');
    window.scrollTo(0, 0);
  };

  const navigateToContact = () => {
    navigate('/contact');
    window.scrollTo(0, 0);
  };

  const navigateToExecute = () => {
    navigate('/execute');
    window.scrollTo(0, 0);
  };

  const withAuthGuard = (element: ReactNode, opts?: { requiredCapability?: string; requiresAnyAgent?: boolean }) => (
    <ProtectedRoute>
      <FirstLoginGuard>
        <AuthzGuard requiredCapability={opts?.requiredCapability} requiresAnyAgent={opts?.requiresAnyAgent}>
          {element}
        </AuthzGuard>
      </FirstLoginGuard>
    </ProtectedRoute>
  );

  // AUTH WALL: when auth is enabled, gate the entire app behind login.
  if (AUTH_ENABLED) {
    if (isLoading) {
      return (
        <div
          className="flex min-h-screen items-center justify-center px-6 bg-[#0c0a2e] text-white/80"
          role="status"
          aria-live="polite"
          aria-busy="true"
        >
          <p className="text-sm">Restoring your session…</p>
        </div>
      );
    }
    if (!isAuthenticated) {
      // Allow /register to render its own page without the login wall
      const currentPath = window.location.pathname;
      if (currentPath === '/register') {
        return (
          <div ref={rootRef} className="flex flex-col overflow-x-hidden min-h-screen bg-[#0c0a2e]">
            <main className="flex-1">
              <RegisterPage />
            </main>
            <Toaster />
          </div>
        );
      }
      // Render LoginPage (which itself handles activation-token -> ActivationForm).
      // LoginPage reads location.pathname/search to honor deep-link redirects post-login.
      // Background is dark navy to match the branded auth-bg image and avoid a
      // white flash before the image paints (QUANTNIK-1936).
      return (
        <div ref={rootRef} className="flex flex-col overflow-x-hidden min-h-screen bg-[#0c0a2e]">
          <main className="flex-1">
            <LoginPage />
          </main>
          <Toaster />
        </div>
      );
    }
  }

  return (
    <div ref={rootRef} className="bg-background flex flex-col overflow-x-hidden min-h-screen" style={{ '--header-height': '0px' } as CSSProperties}>
      <header ref={headerRef} className="fixed top-0 left-0 right-0 z-50 bg-background border-b border-border">
        <Header 
          onLogoClick={navigateToDashboard} 
          isDarkMode={isDarkMode} 
          onToggleTheme={toggleTheme}
          onNavigateToEnablement={navigateToEnablement}
          onNavigateToDemo={navigateToDemo}
          onNavigateToExecute={navigateToExecute}
          onNavigateToUniversity={navigateToUniversity}
          onNavigateToSupport={navigateToSupport}
          onNavigateToAbout={navigateToAbout}
          onNavigateToContact={navigateToContact}
        />
      </header>
      
      {/* Main Content below fixed header */}
      <main className="flex-1" style={{ paddingTop: 'var(--header-height)' }}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route path="/" element={
            <MarketingLandingPage 
              onNavigateToCodeRepo={navigateToCodeRepo}
              onNavigateToPipelines={navigateToPipelines}
              onScrollToSignup={scrollToSignup}
              onNavigateToMLOps={navigateToMLOps}
              onNavigateToDemoVideos={navigateToDemoVideos}
              isDarkMode={isDarkMode}
            />
          } />
          
          <Route path="/enablement" element={
            <Enablement 
              onBack={navigateToDashboard}
              isDarkMode={isDarkMode}
            />
          } />
          
          <Route path="/demo" element={
            <Demo 
              onBack={navigateToDashboard}
              isDarkMode={isDarkMode}
            />
          } />
          
          <Route path="/university" element={
            <University 
              onBack={navigateToDashboard}
              isDarkMode={isDarkMode}
            />
          } />
          
          <Route path="/support" element={
            <Support 
              onBack={navigateToDashboard}
              isDarkMode={isDarkMode}
            />
          } />
          
          <Route path="/about" element={
            <About 
              onBack={navigateToDashboard}
              isDarkMode={isDarkMode}
            />
          } />
          
          <Route path="/contact" element={
            <Contact 
              onBack={navigateToDashboard}
              isDarkMode={isDarkMode}
            />
          } />
          
          <Route
            path="/execute"
            element={withAuthGuard(
              <Execute 
                onBack={navigateToDashboard}
                isDarkMode={isDarkMode}
              />,
              { requiresAnyAgent: true }
            )}
          />

          <Route
            path="/dashboard"
            element={withAuthGuard(
              <PMDashboard />,
              { requiredCapability: 'team:manage_users' }
            )}
          />
          
          <Route
            path="/marketresearch"
            element={withAuthGuard(
              <MarketResearchAgent 
                onBack={navigateToDashboard}
                isDarkMode={isDarkMode}
              />,
              { requiredCapability: 'sdlc:execute' }
            )}
          />
          
          <Route
            path="/coderepo"
            element={withAuthGuard(
              <CodeRepo 
                onBack={navigateToDashboard} 
                onNavigateToRepoDetails={navigateToRepoDetails} 
                isDarkMode={isDarkMode} 
                onToggleTheme={toggleTheme}
              />
            )}
          />
          
          <Route
            path="/pipelines"
            element={withAuthGuard(
              <Pipelines 
                onBack={navigateToDashboard} 
                onNavigateToPipelineStudio={navigateToPipelineStudio} 
                isDarkMode={isDarkMode} 
                onToggleTheme={toggleTheme}
              />
            )}
          />
          
          <Route
            path="/pipelinestudio"
            element={withAuthGuard(
              selectedPipeline ? (
                <PipelineStudio 
                  pipeline={selectedPipeline} 
                  onBack={navigateToPipelines} 
                  onBackToDashboard={navigateToDashboard} 
                  isDarkMode={isDarkMode} 
                  onToggleTheme={toggleTheme}
                />
              ) : null
            )}
          />
          
          <Route
            path="/repodetails"
            element={withAuthGuard(
              selectedRepository ? (
                <RepoDetails 
                  repository={selectedRepository}
                  onBack={navigateToDashboard}
                  onBackToRepo={navigateBackToCodeRepo}
                  onNavigateToFolder={(folderPath) => navigateToFileBrowser(selectedRepository, folderPath)}
                  onNavigateToFile={(filePath) => navigateToFileViewer(selectedRepository, filePath)}
                  isDarkMode={isDarkMode}
                  onToggleTheme={toggleTheme}
                />
              ) : null
            )}
          />
          
          <Route
            path="/filebrowser"
            element={withAuthGuard(
              selectedRepository ? (
                <FileBrowser
                  repository={selectedRepository}
                  folderPath={currentFolderPath}
                  onBack={navigateToDashboard}
                  onBackToRepo={() => navigateToRepoDetails(selectedRepository)}
                  onNavigateToFolder={navigateToFolder}
                  onNavigateToFile={navigateToFile}
                  isDarkMode={isDarkMode}
                  onToggleTheme={toggleTheme}
                />
              ) : null
            )}
          />
          
          <Route
            path="/fileviewer"
            element={withAuthGuard(
              selectedRepository ? (
                <FileViewer
                  repository={selectedRepository}
                  filePath={currentFilePath}
                  onBack={navigateToDashboard}
                  onBackToRepo={() => navigateToRepoDetails(selectedRepository)}
                  isDarkMode={isDarkMode}
                  onToggleTheme={toggleTheme}
                />
              ) : null
            )}
          />
          
          <Route path="/demovideos" element={
            <DemoVideos 
              onBack={navigateToDashboard}
              isDarkMode={isDarkMode}
              onNavigateToVideo={navigateToVideoPlayer}
            />
          } />
          
          <Route path="/videoplayer" element={
            selectedVideo ? (
              <VideoPlayer 
                videoTitle={selectedVideo.title}
                videoUrl={selectedVideo.url}
                onBack={navigateBackToDemoVideos}
                isDarkMode={isDarkMode}
              />
            ) : null
          } />
          
          <Route
            path="/mlops"
            element={
              <MLOpsWorkspace 
                onBack={navigateToDashboard}
                isDarkMode={isDarkMode}
              />
            }
          />

          {/* Legacy route redirect */}
          <Route path="/forwarddeployengineer" element={<Navigate to="/mlops" replace />} />
          
          {/* Catch-all route - redirect to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      
      {/* Footer */}
      <footer>
        <Footer isDarkMode={isDarkMode} onNavigateToDemoVideos={navigateToDemoVideos} />
      </footer>
      
      {/* Global Admin FAB - shown for authenticated users */}
      <AdminFAB />
      
      {/* Toaster */}
      <Toaster />
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </Router>
  );
}
