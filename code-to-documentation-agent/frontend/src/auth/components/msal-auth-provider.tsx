import React, { useEffect, useState } from 'react';
import { MsalProvider } from '@azure/msal-react';
import { msalInstance } from '../config/auth-config';
import { initializeMsal } from '../config/token-service';

interface MsalAuthProviderProps {
  children: React.ReactNode;
}

export const MsalAuthProvider: React.FC<MsalAuthProviderProps> = ({ children }) => {
  const [isInitialized, setIsInitialized] = useState(false);
  const [initializationError, setInitializationError] = useState<string | null>(null);

  useEffect(() => {
    const initialize = async () => {
      try {
        await initializeMsal();
        setIsInitialized(true);
      } catch (error) {
        console.error('Failed to initialize MSAL:', error);
        setInitializationError(error instanceof Error ? error.message : 'Unknown error occurred');
      }
    };

    initialize();
  }, []);

  if (initializationError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center p-8">
          <h1 className="text-2xl font-bold text-destructive mb-4">Authentication Error</h1>
          <p className="text-muted-foreground mb-4">
            Failed to initialize authentication service.
          </p>
          <p className="text-sm text-muted-foreground">
            Error: {initializationError}
          </p>
          <button 
            onClick={() => window.location.reload()} 
            className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!isInitialized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Initializing authentication...</p>
        </div>
      </div>
    );
  }

  return (
    <MsalProvider instance={msalInstance}>
      {children}
    </MsalProvider>
  );
};