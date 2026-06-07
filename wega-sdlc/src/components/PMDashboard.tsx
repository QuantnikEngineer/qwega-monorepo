/**
 * PMDashboard
 *
 * Landing page for Project Managers after login.
 *
 * First-time PMs (no project yet) see the onboarding wizard automatically.
 * Returning PMs see their project card, team overview, and a progress checklist
 * that auto-resolves based on real data (project, team, integrations).
 *
 * Sprint 4 — Phase 3: PM Landing Experience
 */

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import {
  Users,
  FolderKanban,
  Plus,
  Settings,
  CheckCircle2,
  Circle,
  Rocket,
  Sparkles,
  UserPlus,
} from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { useAuth } from '../auth/AuthContext';
import { useProjects } from '../admin/hooks/useProjects';
import { useUsers } from '../admin/hooks/useUsers';
import { ManageProjectsSheet } from '../admin/components/ManageProjectsSheet';
import { ManageUsersSheet } from '../admin/components/ManageUsersSheet';
import { PMOnboardingWizard } from './PMOnboardingWizard';

// ── Onboarding checklist ─────────────────────────────────

interface ChecklistItem {
  id: string;
  label: string;
  done: boolean;
  action?: () => void;
  actionLabel?: string;
}

function OnboardingChecklist({ items }: { items: ChecklistItem[] }) {
  const completed = items.filter((i) => i.done).length;
  const progress = (completed / items.length) * 100;
  const allDone = completed === items.length;

  return (
    <Card
      className={`border transition-colors duration-300 ${
        allDone
          ? 'border-emerald-500/20 bg-emerald-50/50 dark:bg-emerald-950/10'
          : 'border-[#3498B3]/20 bg-[#3498B3]/[0.03] dark:bg-[#3498B3]/[0.04]'
      }`}
    >
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            {allDone ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            ) : (
              <Rocket className="h-5 w-5 text-[#3498B3]" />
            )}
            <CardTitle className="text-base">
              {allDone ? 'Setup Complete' : 'Getting Started'}
            </CardTitle>
          </div>
          <span className="text-xs font-medium text-muted-foreground">
            {completed}/{items.length}
          </span>
        </div>

        {/* Progress bar */}
        <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden mt-3">
          <motion.div
            className={`h-full rounded-full ${allDone ? 'bg-emerald-500' : 'bg-[#3498B3]'}`}
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
          />
        </div>
      </CardHeader>

      <CardContent className="space-y-1 pb-6">
        {items.map((item, i) => (
          <motion.div
            key={item.id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: i * 0.05 }}
            className="flex items-center justify-between gap-2 py-2.5"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              {item.done ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              ) : (
                <Circle className="h-4 w-4 text-muted-foreground/50 shrink-0" />
              )}
              <span
                className={`text-sm ${
                  item.done ? 'text-muted-foreground line-through' : 'text-foreground'
                }`}
              >
                {item.label}
              </span>
            </div>
            {!item.done && item.action && (
              <Button
                variant="ghost"
                size="sm"
                className="text-[#3498B3] hover:text-[#3498B3] hover:bg-[#3498B3]/10 h-7 px-2 text-xs shrink-0"
                onClick={item.action}
              >
                {item.actionLabel ?? 'Set up'}
              </Button>
            )}
          </motion.div>
        ))}
      </CardContent>
    </Card>
  );
}

// ── Main component ───────────────────────────────────────

export function PMDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data: projectsData, isLoading: projectsLoading } = useProjects();
  const { data: usersData, isLoading: usersLoading } = useUsers();

  const [showProjects, setShowProjects] = useState(false);
  const [showUsers, setShowUsers] = useState(false);
  const [showWizard, setShowWizard] = useState(false);

  const projects = projectsData?.projects ?? [];
  // Multi-project: match user's primary project from JWT, fall back to first
  const myProject = projects.find((p) => p.id === user?.projectId) ?? projects[0];
  const allUsers = usersData?.users ?? [];

  const firstName = user?.displayName?.split(' ')[0] ?? 'PM';
  const isFirstTime = !projectsLoading && !myProject;

  // Team members (excluding current user and superadmins)
  const teamMembers = useMemo(
    () =>
      allUsers.filter(
        (u) => u.id !== user?.id && !u.roles?.some((r) => r.roleName === 'superadmin'),
      ),
    [allUsers, user?.id],
  );

  const hasMlops = useMemo(
    () => teamMembers.some((u) => u.roles?.some((r) => r.roleName === 'mlops')),
    [teamMembers],
  );

  // Auto-show wizard for first-time PMs (once per session tab)
  useEffect(() => {
    if (isFirstTime && !sessionStorage.getItem('wega_wizard_dismissed')) {
      setShowWizard(true);
    }
  }, [isFirstTime]);

  const handleWizardOpenChange = (open: boolean) => {
    setShowWizard(open);
    if (!open) {
      sessionStorage.setItem('wega_wizard_dismissed', '1');
    }
  };

  // ── Onboarding checklist items ─────────────────────────

  const checklistItems: ChecklistItem[] = useMemo(
    () => [
      {
        id: 'project',
        label: 'Create your project',
        done: !!myProject,
        action: () => (isFirstTime ? setShowWizard(true) : setShowProjects(true)),
        actionLabel: 'Create',
      },
      {
        id: 'team',
        label: 'Add team members',
        done: teamMembers.length > 0,
        action: () => setShowUsers(true),
        actionLabel: 'Invite',
      },
      {
        id: 'mlops',
        label: 'Assign an MLOps engineer for tool integrations',
        done: hasMlops,
        action: () => setShowUsers(true),
        actionLabel: 'Add',
      },
      {
        id: 'agents',
        label: 'Try an AI agent',
        done: false, // We don't track agent usage yet — always shown as action
        action: () => navigate('/execute'),
        actionLabel: 'Explore',
      },
    ],
    [myProject, teamMembers.length, hasMlops, isFirstTime, navigate],
  );

  const showChecklist = !projectsLoading && !usersLoading && checklistItems.some((i) => !i.done);

  return (
    <div className="bg-background" style={{ minHeight: 'calc(100vh - var(--header-height, 0px))' }}>
      <div className="max-w-5xl mx-auto px-6 py-10 space-y-10">

        {/* ── Welcome header ── */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
        >
          <h1 className="text-3xl font-bold tracking-tight">
            {isFirstTime ? (
              <>
                Welcome, {firstName}
                <Sparkles className="inline-block h-6 w-6 text-[#3498B3] ml-2 -mt-0.5" />
              </>
            ) : (
              <>Welcome back, {firstName}</>
            )}
          </h1>
          <p className="text-muted-foreground mt-1.5 text-base">
            {isFirstTime
              ? "Let's set up your project and get your team started."
              : 'Manage your project and team from here.'}
          </p>

          {/* First-time CTA */}
          {isFirstTime && !showWizard && (
            <Button
              className="mt-4 bg-[#3498B3] hover:bg-[#3498B3]/90 text-white gap-2 px-5
                         shadow-sm hover:shadow transition-all duration-200"
              onClick={() => setShowWizard(true)}
            >
              <Rocket className="h-4 w-4" />
              Start Setup
            </Button>
          )}
        </motion.div>

        {/* ── Quick actions grid ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* My Project card */}
          <Card className="border-[#3498B3]/20 hover:border-[#3498B3]/40 transition-colors">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <FolderKanban className="h-5 w-5 text-[#3498B3]" />
                  <CardTitle className="text-lg">My Project</CardTitle>
                </div>
                {myProject && (
                  <Badge variant="outline" className="text-[#3498B3] border-[#3498B3]/30">
                    Active
                  </Badge>
                )}
              </div>
              <CardDescription>
                {myProject ? myProject.name : 'No project created yet'}
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-1">
              {projectsLoading ? (
                <p className="text-sm text-muted-foreground">Loading…</p>
              ) : myProject ? (
                <div className="space-y-3">
                  {myProject.description && (
                    <p className="text-sm text-muted-foreground leading-relaxed">{myProject.description}</p>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowProjects(true)}
                    className="mt-2"
                  >
                    <Settings className="h-4 w-4 mr-1" />
                    Manage Project
                  </Button>
                </div>
              ) : (
                <Button
                  size="sm"
                  onClick={() => setShowWizard(true)}
                  className="bg-[#3498B3] hover:bg-[#3498B3]/90 text-white"
                >
                  <Plus className="h-4 w-4 mr-1" />
                  Create Project
                </Button>
              )}
            </CardContent>
          </Card>

          {/* Team card */}
          <Card className="border-[#3498B3]/20 hover:border-[#3498B3]/40 transition-colors">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <Users className="h-5 w-5 text-[#3498B3]" />
                  <CardTitle className="text-lg">My Team</CardTitle>
                </div>
                <Badge variant="secondary">
                  {usersLoading ? '…' : teamMembers.length} member{teamMembers.length !== 1 ? 's' : ''}
                </Badge>
              </div>
              <CardDescription>
                Manage your project team members
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-1">
              {usersLoading ? (
                <p className="text-sm text-muted-foreground">Loading…</p>
              ) : teamMembers.length > 0 ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-1">
                    {teamMembers.slice(0, 5).map((m) => (
                      <Badge key={m.id} variant="outline" className="text-xs">
                        {m.displayName}
                      </Badge>
                    ))}
                    {teamMembers.length > 5 && (
                      <Badge variant="outline" className="text-xs text-muted-foreground">
                        +{teamMembers.length - 5} more
                      </Badge>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowUsers(true)}
                    className="mt-2"
                  >
                    <Users className="h-4 w-4 mr-1" />
                    Manage Team
                  </Button>
                </div>
              ) : (
                <Button
                  size="sm"
                  onClick={() => setShowUsers(true)}
                  className="bg-[#3498B3] hover:bg-[#3498B3]/90 text-white"
                >
                  <UserPlus className="h-4 w-4 mr-1" />
                  Add Team Members
                </Button>
              )}
            </CardContent>
          </Card>
        </div>

        {/* ── Onboarding progress checklist (auto-resolving) ── */}
        {showChecklist && <OnboardingChecklist items={checklistItems} />}
      </div>

      {/* ── Onboarding wizard ── */}
      <PMOnboardingWizard open={showWizard} onOpenChange={handleWizardOpenChange} />

      {/* ── Side sheets ── */}
      <ManageProjectsSheet
        open={showProjects}
        onOpenChange={setShowProjects}
        currentUserId={user?.id ?? ''}
        mode="pm"
      />
      <ManageUsersSheet
        open={showUsers}
        onOpenChange={setShowUsers}
        currentUserId={user?.id ?? ''}
        mode="team"
      />
    </div>
  );
}
