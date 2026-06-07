import type React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';

const AUTH_ENABLED = import.meta.env.VITE_AUTH_ENABLED === 'true';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (!AUTH_ENABLED) {
    return <>{children}</>;
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center px-6" role="status" aria-live="polite" aria-busy="true">
        <p className="text-sm text-muted-foreground">Restoring your session…</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
