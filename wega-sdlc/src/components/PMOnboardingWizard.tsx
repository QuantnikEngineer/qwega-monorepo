/**
 * PMOnboardingWizard
 *
 * Guided onboarding dialog for first-time PMs (no project yet).
 * Three steps: Create Project → Add Team → All Set.
 *
 * Design principles:
 * - Reuses existing components (CreateEditUserPanel, useCreateProject)
 * - Matches WEGA design system: Figtree, #3498B3, oklch dark mode
 * - Apple-like transitions via motion/react (fade + slide between steps)
 * - Full dark-mode support, responsive down to mobile
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'motion/react';
import {
  Check,
  CheckCircle2,
  ChevronRight,
  FolderKanban,
  Rocket,
  Sparkles,
  UserPlus,
  Users,
} from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';

import { useAuth } from '../auth/AuthContext';
import { useCreateProject, useProjects } from '../admin/hooks/useProjects';
import { useUsers } from '../admin/hooks/useUsers';
import { CreateEditUserPanel } from '../admin/components/CreateEditUserPanel';

// ── Types ─────────────────────────────────────────────────

interface PMOnboardingWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// ── Animation presets ─────────────────────────────────────

const STEP_TRANSITION = {
  initial: { opacity: 0, x: 20 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -20 },
  transition: { duration: 0.25, ease: [0.25, 0.1, 0.25, 1] as const },
};

const FADE_UP = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3, ease: 'easeOut' as const },
};

// ── Step indicator ────────────────────────────────────────

const STEPS = [
  { label: 'Create Project', icon: FolderKanban },
  { label: 'Add Team', icon: Users },
  { label: 'All Set', icon: Rocket },
] as const;

function StepIndicator({ current }: { current: number }) {
  return (
    <div className="flex items-center justify-center gap-1 sm:gap-2 mb-2">
      {STEPS.map((s, i) => {
        const Icon = s.icon;
        const completed = i < current;
        const active = i === current;
        return (
          <div key={s.label} className="flex items-center gap-1 sm:gap-2">
            <div className="flex items-center gap-1.5">
              {/* Step circle */}
              <motion.div
                className={`
                  relative flex items-center justify-center rounded-full
                  text-xs font-semibold transition-colors duration-300
                  ${completed
                    ? 'bg-[#3498B3] text-white w-6 h-6 sm:w-7 sm:h-7'
                    : active
                      ? 'bg-[#3498B3] text-white w-6 h-6 sm:w-7 sm:h-7 ring-[3px] ring-[#3498B3]/20'
                      : 'bg-muted text-muted-foreground w-6 h-6 sm:w-7 sm:h-7'
                  }
                `}
                animate={active ? { scale: [1, 1.08, 1] } : {}}
                transition={active ? { duration: 0.4, ease: 'easeInOut' } : {}}
              >
                {completed ? (
                  <Check className="w-3 h-3 sm:w-3.5 sm:h-3.5" strokeWidth={3} />
                ) : (
                  <span className="text-[10px] sm:text-xs">{i + 1}</span>
                )}
              </motion.div>

              {/* Step label — hidden on small screens */}
              <span
                className={`text-xs hidden sm:inline transition-colors duration-200 ${
                  active
                    ? 'font-medium text-foreground'
                    : completed
                      ? 'text-[#3498B3] font-medium'
                      : 'text-muted-foreground'
                }`}
              >
                {s.label}
              </span>
            </div>

            {/* Connector line */}
            {i < STEPS.length - 1 && (
              <div className="flex items-center px-0.5 sm:px-1">
                <div
                  className={`h-px w-4 sm:w-8 transition-colors duration-300 ${
                    i < current ? 'bg-[#3498B3]' : 'bg-border'
                  }`}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Progress bar ──────────────────────────────────────────

function ProgressBar({ step }: { step: number }) {
  const progress = ((step + 1) / STEPS.length) * 100;
  return (
    <div className="w-full h-1 bg-muted rounded-full overflow-hidden mb-4">
      <motion.div
        className="h-full bg-[#3498B3] rounded-full"
        initial={{ width: 0 }}
        animate={{ width: `${progress}%` }}
        transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
      />
    </div>
  );
}

// ── Main component ────────────────────────────────────────

export function PMOnboardingWizard({ open, onOpenChange }: PMOnboardingWizardProps) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const firstName = user?.displayName?.split(' ')[0] ?? 'there';
  const nameInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState(0);

  // Step 1 state
  const [projectName, setProjectName] = useState('');
  const [projectDescription, setProjectDescription] = useState('');
  const createProjectMutation = useCreateProject();

  // Step 2 state — reuses CreateEditUserPanel
  const [showAddMember, setShowAddMember] = useState(false);
  const { data: usersData } = useUsers();
  const { data: projectsData } = useProjects();

  // Reset state on open
  useEffect(() => {
    if (open) {
      setStep(0);
      setProjectName('');
      setProjectDescription('');
      // Focus the name input after dialog animation completes
      setTimeout(() => nameInputRef.current?.focus(), 350);
    }
  }, [open]);

  // ── Derived state ───────────────────────────────────────

  const currentTeam = useMemo(
    () =>
      (usersData?.users ?? []).filter(
        (u) => u.id !== user?.id && !u.roles?.some((r) => r.roleName === 'superadmin'),
      ),
    [usersData, user?.id],
  );

  const hasMlops = useMemo(
    () => currentTeam.some((u) => u.roles?.some((r) => r.roleName === 'mlops')),
    [currentTeam],
  );

  const createdProject = projectsData?.projects?.[0];

  // ── Step 1: Create Project ──────────────────────────────

  const handleCreateProject = useCallback(async () => {
    const trimmedName = projectName.trim();
    if (!trimmedName) {
      toast.error('Project name is required');
      nameInputRef.current?.focus();
      return;
    }
    try {
      await createProjectMutation.mutateAsync({
        name: trimmedName,
        description: projectDescription.trim() || undefined,
      });
      toast.success('Project created!');
      setStep(1);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create project');
    }
  }, [projectName, projectDescription, createProjectMutation]);

  const handleProjectKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && projectName.trim()) {
        e.preventDefault();
        handleCreateProject();
      }
    },
    [handleCreateProject, projectName],
  );

  // ── Step 2: Team ────────────────────────────────────────

  const handleMemberAdded = useCallback(() => {
    setShowAddMember(false);
  }, []);

  // ── Step 3: Navigation ──────────────────────────────────

  const handleGoToDashboard = useCallback(() => {
    onOpenChange(false);
  }, [onOpenChange]);

  const handleGoToExecute = useCallback(() => {
    onOpenChange(false);
    navigate('/execute');
  }, [onOpenChange, navigate]);

  // ── Render ──────────────────────────────────────────────

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[520px] p-0 gap-0 overflow-hidden">

          {/* ── Header with progress ── */}
          <div className="px-6 pt-6 pb-0">
            <StepIndicator current={step} />
            <ProgressBar step={step} />
          </div>

          {/* ── Step content with animated transitions ── */}
          <div className="px-6 pb-2 min-h-[260px]">
            <AnimatePresence mode="wait">

              {/* ══ Step 0: Create Project ══ */}
              {step === 0 && (
                <motion.div key="step-0" {...STEP_TRANSITION}>
                  <DialogHeader className="mb-5">
                    <DialogTitle className="flex items-center gap-2.5 text-lg tracking-tight">
                      <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-[#3498B3]/10">
                        <Sparkles className="h-4 w-4 text-[#3498B3]" />
                      </div>
                      Welcome to WEGA, {firstName}!
                    </DialogTitle>
                    <DialogDescription className="text-sm leading-relaxed">
                      Let's set up your project. This takes about 2 minutes.
                    </DialogDescription>
                  </DialogHeader>

                  <div className="space-y-4">
                    <motion.div className="space-y-2" {...FADE_UP} transition={{ ...FADE_UP.transition, delay: 0.1 }}>
                      <Label htmlFor="onb-project-name" className="text-sm font-medium">
                        Project Name
                      </Label>
                      <Input
                        ref={nameInputRef}
                        id="onb-project-name"
                        placeholder="e.g. WEGA Platform"
                        value={projectName}
                        onChange={(e) => setProjectName(e.target.value)}
                        onKeyDown={handleProjectKeyDown}
                        className="h-10"
                        autoComplete="off"
                      />
                    </motion.div>

                    <motion.div className="space-y-2" {...FADE_UP} transition={{ ...FADE_UP.transition, delay: 0.2 }}>
                      <Label htmlFor="onb-project-desc" className="text-sm font-medium">
                        Description{' '}
                        <span className="font-normal text-muted-foreground">(optional)</span>
                      </Label>
                      <Input
                        id="onb-project-desc"
                        placeholder="Brief description of your project"
                        value={projectDescription}
                        onChange={(e) => setProjectDescription(e.target.value)}
                        onKeyDown={handleProjectKeyDown}
                        className="h-10"
                        autoComplete="off"
                      />
                    </motion.div>
                  </div>
                </motion.div>
              )}

              {/* ══ Step 1: Add Team ══ */}
              {step === 1 && (
                <motion.div key="step-1" {...STEP_TRANSITION}>
                  <DialogHeader className="mb-5">
                    <DialogTitle className="flex items-center gap-2.5 text-lg tracking-tight">
                      <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-[#3498B3]/10">
                        <Users className="h-4 w-4 text-[#3498B3]" />
                      </div>
                      Add Your Team
                    </DialogTitle>
                    <DialogDescription className="text-sm leading-relaxed">
                      Invite team members to <span className="font-medium text-foreground">{createdProject?.name ?? projectName}</span>.
                      They'll receive activation links.
                    </DialogDescription>
                  </DialogHeader>

                  <div className="space-y-4">
                    {/* Team members list */}
                    {currentTeam.length > 0 && (
                      <motion.div className="space-y-2" {...FADE_UP}>
                        {currentTeam.map((m, i) => (
                          <motion.div
                            key={m.id}
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.2, delay: i * 0.05 }}
                            className="flex items-center justify-between rounded-lg border px-3 py-2.5
                                       hover:border-[#3498B3]/30 transition-colors duration-200"
                          >
                            <div className="flex items-center gap-2.5 min-w-0">
                              <div className="flex items-center justify-center w-7 h-7 rounded-full
                                              bg-[#3498B3]/10 text-[#3498B3] text-xs font-semibold shrink-0">
                                {m.displayName?.charAt(0)?.toUpperCase() ?? '?'}
                              </div>
                              <div className="min-w-0">
                                <p className="text-sm font-medium truncate">{m.displayName}</p>
                              </div>
                            </div>
                            <div className="flex items-center gap-1.5 shrink-0">
                              {m.roles?.map((r) => (
                                <Badge key={r.roleName} variant="secondary" className="text-[10px] px-1.5 py-0">
                                  {r.roleName}
                                </Badge>
                              ))}
                            </div>
                          </motion.div>
                        ))}
                      </motion.div>
                    )}

                    {/* Empty state */}
                    {currentTeam.length === 0 && (
                      <motion.div
                        className="flex flex-col items-center text-center py-6"
                        {...FADE_UP}
                      >
                        <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
                          <UserPlus className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <p className="text-sm text-muted-foreground max-w-[260px]">
                          Add developers, testers, and MLOps engineers to get your team started.
                        </p>
                      </motion.div>
                    )}

                    {/* MLOps tip */}
                    {currentTeam.length > 0 && !hasMlops && (
                      <motion.div
                        className="flex gap-2.5 text-xs rounded-lg px-3 py-2.5
                                   bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400
                                   border border-amber-200/60 dark:border-amber-800/30"
                        {...FADE_UP}
                      >
                        <Sparkles className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                        <span>
                          Add an <strong>MLOps</strong> member — they'll configure Jira, Confluence, and other tool integrations for your project.
                        </span>
                      </motion.div>
                    )}

                    {/* Add member button */}
                    <Button
                      variant="outline"
                      className="w-full border-dashed border-[#3498B3]/30 text-[#3498B3]
                                 hover:bg-[#3498B3]/5 hover:border-[#3498B3]/50 transition-all duration-200"
                      onClick={() => setShowAddMember(true)}
                    >
                      <UserPlus className="h-4 w-4 mr-2" />
                      Add Team Member
                    </Button>
                  </div>
                </motion.div>
              )}

              {/* ══ Step 2: All Set ══ */}
              {step === 2 && (
                <motion.div key="step-2" {...STEP_TRANSITION}>
                  <DialogHeader className="mb-5">
                    <DialogTitle className="flex items-center gap-2.5 text-lg tracking-tight">
                      <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-emerald-500/10">
                        <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                      </div>
                      You're All Set!
                    </DialogTitle>
                    <DialogDescription className="text-sm leading-relaxed">
                      Your project is ready to go.
                    </DialogDescription>
                  </DialogHeader>

                  {/* Project summary card */}
                  <motion.div
                    className="rounded-xl border border-[#3498B3]/20 bg-[#3498B3]/[0.03]
                               dark:bg-[#3498B3]/[0.06] p-4 space-y-3 mb-5"
                    {...FADE_UP}
                  >
                    <div className="flex items-center gap-2.5">
                      <FolderKanban className="h-4 w-4 text-[#3498B3]" />
                      <span className="text-sm font-semibold">{createdProject?.name ?? projectName}</span>
                      <Badge variant="outline" className="text-[#3498B3] border-[#3498B3]/30 text-[10px] px-1.5 py-0">
                        Active
                      </Badge>
                    </div>
                    {(createdProject?.description || projectDescription) && (
                      <p className="text-xs text-muted-foreground leading-relaxed pl-[26px]">
                        {createdProject?.description ?? projectDescription}
                      </p>
                    )}
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground pl-[26px]">
                      <Users className="h-3 w-3" />
                      {currentTeam.length} team member{currentTeam.length !== 1 ? 's' : ''} invited
                    </div>
                  </motion.div>

                  {/* What's next */}
                  <motion.div className="space-y-3" {...FADE_UP} transition={{ ...FADE_UP.transition, delay: 0.15 }}>
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      What happens next
                    </h4>
                    <ul className="space-y-2.5">
                      {currentTeam.length > 0 && (
                        <li className="flex gap-2.5 text-sm text-muted-foreground leading-relaxed">
                          <CheckCircle2 className="h-4 w-4 text-[#3498B3] shrink-0 mt-0.5" />
                          Share activation links with your team so they can set up their accounts.
                        </li>
                      )}
                      <li className="flex gap-2.5 text-sm text-muted-foreground leading-relaxed">
                        <CheckCircle2 className={`h-4 w-4 shrink-0 mt-0.5 ${hasMlops ? 'text-[#3498B3]' : 'text-amber-500'}`} />
                        {hasMlops
                          ? 'Once your MLOps engineer activates, they can configure Jira, Confluence, and other tools.'
                          : 'Consider adding an MLOps member to configure tool integrations (Jira, Confluence, GitHub).'}
                      </li>
                      <li className="flex gap-2.5 text-sm text-muted-foreground leading-relaxed">
                        <CheckCircle2 className="h-4 w-4 text-[#3498B3] shrink-0 mt-0.5" />
                        You can start using AI agents right away — try BRD Generator or User Stories Creator.
                      </li>
                    </ul>
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* ── Footer actions ── */}
          <div className="px-6 pb-6 pt-2">
            <div className="flex items-center justify-between">
              {step === 0 && (
                <>
                  <Button
                    variant="ghost"
                    className="text-muted-foreground hover:text-foreground"
                    onClick={() => onOpenChange(false)}
                  >
                    Skip for now
                  </Button>
                  <Button
                    className="bg-[#3498B3] hover:bg-[#3498B3]/90 text-white gap-1.5 px-5
                               shadow-sm hover:shadow transition-all duration-200"
                    onClick={handleCreateProject}
                    disabled={createProjectMutation.isPending || !projectName.trim()}
                  >
                    {createProjectMutation.isPending ? (
                      <>
                        <motion.div
                          className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full"
                          animate={{ rotate: 360 }}
                          transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
                        />
                        Creating…
                      </>
                    ) : (
                      <>
                        Create Project
                        <ChevronRight className="h-4 w-4" />
                      </>
                    )}
                  </Button>
                </>
              )}
              {step === 1 && (
                <>
                  <Button
                    variant="ghost"
                    className="text-muted-foreground hover:text-foreground"
                    onClick={() => setStep(2)}
                  >
                    {currentTeam.length > 0 ? 'Continue' : 'Skip for now'}
                  </Button>
                  {currentTeam.length > 0 && (
                    <Button
                      className="bg-[#3498B3] hover:bg-[#3498B3]/90 text-white gap-1.5 px-5
                                 shadow-sm hover:shadow transition-all duration-200"
                      onClick={() => setStep(2)}
                    >
                      Next
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  )}
                </>
              )}
              {step === 2 && (
                <>
                  <Button
                    variant="outline"
                    className="gap-1.5"
                    onClick={handleGoToExecute}
                  >
                    <Rocket className="h-3.5 w-3.5" />
                    Start Using Agents
                  </Button>
                  <Button
                    className="bg-[#3498B3] hover:bg-[#3498B3]/90 text-white gap-1.5 px-5
                               shadow-sm hover:shadow transition-all duration-200"
                    onClick={handleGoToDashboard}
                  >
                    Go to Dashboard
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Reuse the existing CreateEditUserPanel for adding team members */}
      <CreateEditUserPanel
        open={showAddMember}
        onOpenChange={setShowAddMember}
        mode="team"
        onSuccess={handleMemberAdded}
      />
    </>
  );
}
