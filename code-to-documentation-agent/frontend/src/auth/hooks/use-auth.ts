import { useEffect, useState, useCallback } from 'react';
import { useIsAuthenticated, useMsal } from '@azure/msal-react';
import { AccountInfo, EventType } from '@azure/msal-browser';
import { TokenService } from '../config/token-service';

interface UseAuthReturn {
  isAuthenticated: boolean;
  user: AccountInfo | null;
  isLoading: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  getAccessToken: () => Promise<string | null>;
}

export const useAuth = (): UseAuthReturn => {
  const isAuthenticated = useIsAuthenticated();
  const { instance } = useMsal();
  const [user, setUser] = useState<AccountInfo | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Function to update user from active account
  const updateUserFromActiveAccount = useCallback(() => {
    const activeAccount = TokenService.getActiveAccount();
    console.log('useAuth: Updating user from active account:', activeAccount);
    setUser(activeAccount);
    return activeAccount;
  }, []);

  useEffect(() => {
    console.log('useAuth: Setting up authentication state');
    
    // Initial load
    if (isAuthenticated) {
      updateUserFromActiveAccount();
    } else {
      setUser(null);
    }

    // Set up MSAL event listeners
    const callbackId = instance.addEventCallback((event) => {
      console.log('useAuth: MSAL event received:', event.eventType, event);
      
      if (event.eventType === EventType.LOGIN_SUCCESS ||
          event.eventType === EventType.ACQUIRE_TOKEN_SUCCESS ||
          event.eventType === EventType.SSO_SILENT_SUCCESS) {
        
        console.log('useAuth: Authentication success event, updating user');
        // Small delay to ensure account is set
        setTimeout(() => {
          updateUserFromActiveAccount();
        }, 100);
      }
      
      if (event.eventType === EventType.LOGOUT_SUCCESS) {
        console.log('useAuth: Logout success, clearing user');
        setUser(null);
      }
    });

    return () => {
      if (callbackId) {
        instance.removeEventCallback(callbackId);
      }
    };
  }, [isAuthenticated, instance, updateUserFromActiveAccount]);

  const login = async (): Promise<void> => {
    setIsLoading(true);
    try {
      const result = await TokenService.loginPopup();
      if (result) {
        console.log('useAuth: Login successful, updating user state:', result.account);
        setUser(result.account);
        // Also trigger the update from active account to ensure consistency
        setTimeout(() => {
          updateUserFromActiveAccount();
        }, 50);
      }
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async (): Promise<void> => {
    setIsLoading(true);
    try {
      await TokenService.logout();
      setUser(null);
    } catch (error) {
      console.error('Logout failed:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const getAccessToken = async (): Promise<string | null> => {
    return await TokenService.getAccessToken();
  };

  return {
    isAuthenticated,
    user,
    isLoading,
    login,
    logout,
    getAccessToken,
  };
};