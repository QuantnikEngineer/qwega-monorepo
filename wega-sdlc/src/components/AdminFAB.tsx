/**
 * AdminFAB
 *
 * Global floating action button for role-gated admin actions.
 * Replaces the removed ChatbotFAB with a contextual admin menu.
 * Uses CASL <Can> wrappers for capability-based item visibility.
 *
 * GAP-02: Admin module global entry point.
 */

import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Shield, Users, FolderOpen, Wrench, Eye, KeyRound, X, ChevronRight, Server, Bot } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Button } from './ui/button';
import { Can } from '../auth/abilities';
import { useAuth } from '../auth/AuthContext';
import { ManageUsersSheet } from '../admin/components/ManageUsersSheet';
import { RolesCapabilitiesDialog } from '../admin/components/RolesCapabilitiesDialog';
import { ManageProjectsSheet } from '../admin/components/ManageProjectsSheet';
import { ProjectToolSettingsPanel } from '../admin/components/ProjectToolSettingsPanel';
import { PlatformServicesPanel } from '../admin/components/PlatformServicesPanel';
import { AgentAccessPanel } from '../admin/components/AgentAccessPanel';
import { ProjectAgentConfigPanel } from '../admin/components/ProjectAgentConfigPanel';
import { ChangePasswordDialog } from '../admin/components/ChangePasswordDialog';
import { useProjects } from '../admin/hooks/useProjects';
import type { ProjectInfo } from '../admin/api/adminApi';

interface MenuItemProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}

function MenuItem({ icon, label, onClick }: MenuItemProps) {
  return (
    <button
      onClick={onClick}
      className="w-full text-foreground text-xs font-medium px-3 py-2.5 rounded-lg transition-all duration-200 flex items-center justify-between group hover:bg-accent"
    >
      <span className="flex items-center gap-3 min-w-0">
        {icon}
        <span className="truncate">{label}</span>
      </span>
      <ChevronRight className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0 opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all duration-200" />
    </button>
  );
}

export function AdminFAB() {
  const { user, isAuthenticated } = useAuth();
  const { data: projectsData } = useProjects();
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);

  // Admin sheet/dialog state
  const [showManageUsers, setShowManageUsers] = useState(false);
  const [showManageProjects, setShowManageProjects] = useState(false);
  const [showRolesDialog, setShowRolesDialog] = useState(false);
  const [showMyTeam, setShowMyTeam] = useState(false);
  const [showMyProject, setShowMyProject] = useState(false);
  const [showToolSettings, setShowToolSettings] = useState(false);
  const [showToolSettingsReadOnly, setShowToolSettingsReadOnly] = useState(false);
  const [showPlatformServices, setShowPlatformServices] = useState(false);
  const [showAgentAccess, setShowAgentAccess] = useState(false);
  const [showProjectAgents, setShowProjectAgents] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);

  if (!isAuthenticated || !user) return null;

  // Resolve the org's single active project for tool settings
  const activeProject: ProjectInfo | undefined = (projectsData?.projects ?? []).find(
    (p: ProjectInfo) => p.isActive
  );

  const closeMenu = () => setIsOpen(false);

  return (
    <>
      {/* On /execute, stack above the AI Settings FAB (48px btn + 12px gap) */}
      <div className={`fixed right-2 z-50 ${location.pathname === '/execute' ? 'bottom-[76px]' : 'bottom-4'}`}>
        <Popover open={isOpen} onOpenChange={setIsOpen}>
          <PopoverTrigger asChild>
            <Button
              size="lg"
              className="w-12 h-12 rounded-full shadow-lg hover:shadow-xl transition-shadow text-white"
              style={{ backgroundColor: isOpen ? '#351A55' : '#746FA7' }}
            >
              {isOpen ? (
                <X className="size-6" />
              ) : (
                <Shield className="size-6" />
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent
            side="top"
            align="end"
            sideOffset={12}
            className="w-64 p-2 z-[60]"
          >
            <div className="space-y-1">
              {/* SuperAdmin: Platform management */}
              <Can I="manage_users" a="org">
                <div className="px-2 py-1.5">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Administration</p>
                </div>
                <MenuItem
                  icon={<Users className="w-4 h-4 text-[#746FA7]" />}
                  label="Manage Users"
                  onClick={() => { setShowManageUsers(true); closeMenu(); }}
                />
                <MenuItem
                  icon={<FolderOpen className="w-4 h-4 text-[#746FA7]" />}
                  label="Manage Projects"
                  onClick={() => { setShowManageProjects(true); closeMenu(); }}
                />
                <Can I="manage" a="platform">
                  <MenuItem
                    icon={<Eye className="w-4 h-4 text-[#746FA7]" />}
                    label="Roles & Capabilities"
                    onClick={() => { setShowRolesDialog(true); closeMenu(); }}
                  />
                  <MenuItem
                    icon={<Server className="w-4 h-4 text-[#746FA7]" />}
                    label="Service Registry"
                    onClick={() => { setShowPlatformServices(true); closeMenu(); }}
                  />
                  <MenuItem
                    icon={<Bot className="w-4 h-4 text-[#746FA7]" />}
                    label="Agent Access"
                    onClick={() => { setShowAgentAccess(true); closeMenu(); }}
                  />
                </Can>
              </Can>

              {/* PM: Project + Team management */}
              <Can I="create" a="project">
                <Can not I="manage_users" a="org">
                  <div className="border-t border-border my-1" />
                  <div className="px-3 pt-3 pb-1">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Project</span>
                  </div>
                  <MenuItem
                    icon={<FolderOpen className="w-4 h-4 text-[#3498B3]" />}
                    label="My Project"
                    onClick={() => { setShowMyProject(true); closeMenu(); }}
                  />
                </Can>
              </Can>

              <Can I="manage_agents" a="project">
                <MenuItem
                  icon={<Bot className="w-4 h-4 text-[#746FA7]" />}
                  label="Project Agent Access"
                  onClick={() => { setShowProjectAgents(true); closeMenu(); }}
                />
              </Can>

              <Can I="manage_users" a="team">
                <div className="border-t border-border my-1" />
                <div className="px-3 pt-3 pb-1">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Team</span>
                </div>
                <MenuItem
                  icon={<Users className="w-4 h-4 text-[#3498B3]" />}
                  label="Manage My Team"
                  onClick={() => { setShowMyTeam(true); closeMenu(); }}
                />
              </Can>

              {/* MLOps / SuperAdmin: Project tool integrations */}
              <Can I="configure_tools" a="integration">
                <div className="border-t border-border my-1" />
                <div className="px-3 pt-3 pb-1">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Integrations</span>
                </div>
                <MenuItem
                  icon={<Wrench className="w-4 h-4 text-[#3498B3]" />}
                  label="Project Integrations"
                  onClick={() => {
                    if (activeProject) {
                      setShowToolSettings(true);
                    }
                    closeMenu();
                  }}
                />
              </Can>

              {/* PM: View integration status (read-only) — only if NOT MLOps/SA */}
              <Can I="use_tools" a="integration" not>
                <Can I="configure_tools" a="integration">
                  {null}
                </Can>
              </Can>
              <Can I="use_tools" a="integration">
                <Can not I="configure_tools" a="integration">
                  <div className="border-t border-border my-1" />
                  <div className="px-3 pt-3 pb-1">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Integrations</span>
                  </div>
                  <MenuItem
                    icon={<Wrench className="w-4 h-4 text-muted-foreground" />}
                    label="View Integrations"
                    onClick={() => {
                      if (activeProject) {
                        setShowToolSettingsReadOnly(true);
                      }
                      closeMenu();
                    }}
                  />
                </Can>
              </Can>

              {/* All authenticated: Profile */}
              <div className="border-t border-border my-1" />
              <div className="px-3 pt-3 pb-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Account</span>
              </div>
              <MenuItem
                icon={<KeyRound className="w-4 h-4 text-muted-foreground" />}
                label="Change Password"
                onClick={() => {
                  closeMenu();
                  setShowChangePassword(true);
                }}
              />
            </div>
          </PopoverContent>
        </Popover>
      </div>

      {/* Admin sheets/dialogs — rendered only when open */}
      {showManageUsers && (
        <ManageUsersSheet
          open={showManageUsers}
          onOpenChange={setShowManageUsers}
          currentUserId={user.id}
          mode="admin"
        />
      )}
      {showMyTeam && (
        <ManageUsersSheet
          open={showMyTeam}
          onOpenChange={setShowMyTeam}
          currentUserId={user.id}
          mode="team"
        />
      )}
      {showMyProject && (
        <ManageProjectsSheet
          open={showMyProject}
          onOpenChange={setShowMyProject}
          currentUserId={user.id}
          mode="pm"
        />
      )}
      {showManageProjects && (
        <ManageProjectsSheet
          open={showManageProjects}
          onOpenChange={setShowManageProjects}
          currentUserId={user.id}
        />
      )}
      {showRolesDialog && (
        <RolesCapabilitiesDialog
          open={showRolesDialog}
          onOpenChange={setShowRolesDialog}
        />
      )}
      {showToolSettings && activeProject && (
        <ProjectToolSettingsPanel
          open={showToolSettings}
          onOpenChange={setShowToolSettings}
          project={activeProject}
        />
      )}
      {showToolSettingsReadOnly && activeProject && (
        <ProjectToolSettingsPanel
          open={showToolSettingsReadOnly}
          onOpenChange={setShowToolSettingsReadOnly}
          project={activeProject}
          readOnly
        />
      )}
      {showPlatformServices && (
        <PlatformServicesPanel
          open={showPlatformServices}
          onOpenChange={setShowPlatformServices}
        />
      )}
      {showAgentAccess && (
        <AgentAccessPanel
          open={showAgentAccess}
          onOpenChange={setShowAgentAccess}
        />
      )}
      {showProjectAgents && activeProject && (
        <ProjectAgentConfigPanel
          open={showProjectAgents}
          onOpenChange={setShowProjectAgents}
          projectId={activeProject.id}
          projectName={activeProject.name}
        />
      )}
      {showChangePassword && (
        <ChangePasswordDialog
          open={showChangePassword}
          onOpenChange={setShowChangePassword}
        />
      )}
    </>
  );
}
