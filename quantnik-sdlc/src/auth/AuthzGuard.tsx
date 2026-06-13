import type React from 'react';
import { useAuth } from './AuthContext';
import { useAbility } from './abilities';
import { ShieldAlert } from 'lucide-react';

interface AuthzGuardProps {
  children: React.ReactNode;
  /** Capability string in "resource:action" format (e.g. "sdlc:execute") */
  requiredCapability?: string;
  /** If true, user must have at least one entry in allowedAgents */
  requiresAnyAgent?: boolean;
}

function AccessDenied() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-6 text-center gap-4">
      <ShieldAlert className="h-12 w-12 text-muted-foreground" />
      <div>
        <h2 className="text-lg font-semibold text-foreground">Access Denied</h2>
        <p className="text-sm text-muted-foreground mt-1">
          You don't have the required permissions to access this page.
        </p>
      </div>
    </div>
  );
}

export function AuthzGuard({ children, requiredCapability, requiresAnyAgent }: AuthzGuardProps) {
  const { user } = useAuth();
  const ability = useAbility();

  if (requiredCapability) {
    const [resource, action] = requiredCapability.split(':');
    if (resource && action && !ability.can(action, resource)) {
      return <AccessDenied />;
    }
  }

  if (requiresAnyAgent && (!user?.allowedAgents || user.allowedAgents.length === 0)) {
    return <AccessDenied />;
  }

  return <>{children}</>;
}
