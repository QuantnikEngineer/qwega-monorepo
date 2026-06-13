import type React from 'react';
import { useState } from 'react';
import { useAuth } from './AuthContext';
import { ChangePasswordDialog } from '../admin/components/ChangePasswordDialog';

export function FirstLoginGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [forcedOpen, setForcedOpen] = useState(true);

  if (user?.mustChangePassword) {
    return (
      <>
        {children}
        <ChangePasswordDialog open={forcedOpen} onOpenChange={setForcedOpen} forced />
      </>
    );
  }

  return <>{children}</>;
}
