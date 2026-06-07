import React, { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';
import { useMsal } from '@azure/msal-react';
import { AccountInfo } from '@azure/msal-browser';

interface User {
  id: string;
  name?: string;
  username?: string;
  email?: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  refreshUser: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const { instance, accounts } = useMsal();
  const [user, setUser] = useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const mapAccountToUser = (account: AccountInfo): User => {
    return {
      id: account.homeAccountId,
      name: account.name || undefined,
      username: account.username,
      email: account.username, // In MSAL, username is typically the email
    };
  };

  const refreshUser = useCallback(() => {
    setIsLoading(true);
    const activeAccount = instance.getActiveAccount();
    
    if (activeAccount) {
      const mappedUser = mapAccountToUser(activeAccount);
      setUser(mappedUser);
      setIsAuthenticated(true);
    } else if (accounts.length > 0) {
      // If no active account but accounts exist, use the first one
      instance.setActiveAccount(accounts[0]);
      const mappedUser = mapAccountToUser(accounts[0]);
      setUser(mappedUser);
      setIsAuthenticated(true);
    } else {
      setUser(null);
      setIsAuthenticated(false);
    }
    setIsLoading(false);
  }, [instance, accounts]);

  useEffect(() => {
    // Initial load
    refreshUser();

    // Listen for account changes
    const callbackId = instance.addEventCallback((event) => {
      if (event.eventType === 'msal:loginSuccess' || 
          event.eventType === 'msal:acquireTokenSuccess' ||
          event.eventType === 'msal:logoutSuccess') {
        // Small delay to ensure MSAL state is updated
        setTimeout(refreshUser, 100);
      }
    });

    return () => {
      if (callbackId) {
        instance.removeEventCallback(callbackId);
      }
    };
  }, [instance, accounts]);

  // Also refresh when accounts array changes
  useEffect(() => {
    refreshUser();
  }, [accounts]);

  const value = {
    user,
    isAuthenticated,
    isLoading,
    refreshUser,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuthContext = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuthContext must be used within an AuthProvider');
  }
  return context;
};