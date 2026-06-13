/**
 * Auth Types
 *
 * TypeScript interfaces for the authentication system.
 * Used by AuthContext, authApi, Login, and PasswordChange components.
 */

export interface AuthUserProject {
  id: string;
  name: string;
  slug: string;
}

export interface AuthUser {
  id: string;
  email: string;
  displayName: string;
  roles: string[];
  capabilities: string[];           // Flat list (backward compat)
  allowedAgents: string[];           // Phase 5: role-inherent agent IDs from JWT
  orgId: string;
  projectId?: string;                // Primary project ID (from JWT — first created or first membership)
  projects: AuthUserProject[];       // All active project memberships from /auth/me
  mustChangePassword: boolean;
  // DEPRECATED — kept for backward compat during Phase 4→5 rolling deploy
  platformCapabilities: string[];
  orgCapabilities: string[];
  projectRoles: Record<string, string[]>;
  selfCapabilities: string[];
}

export interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<LoginResult>;
  logout: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  getAccessToken: () => string | null;
}

export interface LoginResult {
  accessToken: string;
  expiresIn: number;
  user: AuthUser;
  mustChangePassword: boolean;
}

export interface TokenRefreshResult {
  accessToken: string;
  expiresIn: number;
}
