import { useIsAuthenticated, useMsal } from '@azure/msal-react';
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TokenService } from '../config/token-service';
import { useAuthContext } from '../context/AuthContext';

interface AuthGuardProps {
  children: React.ReactNode;
}

export const AuthGuard: React.FC<AuthGuardProps> = ({ children }) => {
  const isAuthenticated = useIsAuthenticated();
  const { instance, inProgress } = useMsal();
  const { refreshUser } = useAuthContext();
  const navigate = useNavigate();
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const loginAttemptRef = useRef(false);

  useEffect(() => {
    const initiateLogin = async () => {
      // Check if user just logged out
      const userLoggingOut = sessionStorage.getItem('user_logging_out');
      if (userLoggingOut) {
        // Clear the flag and don't attempt login
        sessionStorage.removeItem('user_logging_out');
        return;
      }

      // Don't start login if already authenticated, already in progress, or already attempted
      if (isAuthenticated || inProgress !== 'none' || isLoggingIn || loginAttemptRef.current) {
        return;
      }

      loginAttemptRef.current = true;
      setIsLoggingIn(true);
      
      try {
        // Try silent authentication first
        const accounts = TokenService.getAllAccounts();
        if (accounts.length > 0) {
          const account = accounts[0];
          try {
            const silentResult = await TokenService.acquireTokenSilent(account);
            if (silentResult) {
              refreshUser(); // Refresh user context after silent auth
              setIsLoggingIn(false);
              return; // Successfully authenticated silently
            }
          } catch (silentError) {
            console.warn('Silent authentication failed, proceeding with interactive login:', silentError);
          }
        }

        // If silent auth fails, trigger popup login
    
        const result = await TokenService.loginPopup();
        if (!result) {
          console.log("Authentication cancelled, redirecting to login page...");
          navigate('/');
          return;
        }
      } catch (error) {
        console.error("Authentication error:", error);
        // Instead of showing error, redirect to login page
        navigate('/');
        return;
      } finally {
        setIsLoggingIn(false);
      }
    };

    initiateLogin();
  }, [isAuthenticated, inProgress, isLoggingIn, instance, refreshUser, navigate]);

  // Reset login attempt when user becomes authenticated
  useEffect(() => {
    if (isAuthenticated) {
      loginAttemptRef.current = false;
      setIsLoggingIn(false);
      refreshUser(); // Refresh user context when authentication is detected
    }
  }, [isAuthenticated, refreshUser]);

  if (!isAuthenticated) {
    if (isLoggingIn || inProgress !== 'none') {
      return (
        <div className="min-h-screen flex items-center justify-center bg-background">
          <div className="text-center space-y-4">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
            <p className="text-lg text-muted-foreground">Signing you in...</p>
            <p className="text-sm text-muted-foreground/70">Please complete the authentication in the popup window</p>
          </div>
        </div>
      );
    }

    // Fallback - redirect to login
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-2">
          <div className="animate-pulse h-2 w-48 bg-muted rounded mx-auto"></div>
          <p className="text-muted-foreground">Redirecting to login...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
 