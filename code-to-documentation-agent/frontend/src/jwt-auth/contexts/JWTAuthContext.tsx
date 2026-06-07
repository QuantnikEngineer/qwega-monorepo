import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { EncryptedJWTPayload, jwtAuthService } from '../services/JWTAuthService';

interface JWTAuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  authData: EncryptedJWTPayload | null;
  logout: () => void;
}

const JWTAuthContext = createContext<JWTAuthContextType | null>(null);

interface JWTAuthProviderProps {
  children: ReactNode;
}

export const JWTAuthProvider: React.FC<JWTAuthProviderProps> = ({ children }) => {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authData, setAuthData] = useState<EncryptedJWTPayload | null>(null);

  const initializeAuth = async () => {
    try {
      setIsLoading(true);
      
      // Set up event handlers for JWT auth service
      jwtAuthService.onAuthenticated = (data: EncryptedJWTPayload) => {
        setIsAuthenticated(true);
        setAuthData(data);
        setIsLoading(false);
      };

      jwtAuthService.onAuthenticationFailure = (err?: Error) => {
        setIsAuthenticated(false);
        setAuthData(null);
        setIsLoading(false);
      };

      // Initialize the JWT auth service
      await jwtAuthService.initializeAuth();

      // If no events were triggered, set loading to false
      setTimeout(() => {
        if (isLoading) {
          setIsLoading(false);
        }
      }, 1000);

    } catch (err) {
      console.error('JWT Auth initialization failed:', err);
      setIsAuthenticated(false);
      setAuthData(null);
      setIsLoading(false);
    }
  };


  const logout = () => {
    jwtAuthService.logout();
    setIsAuthenticated(false);
    setAuthData(null);
  };



  // Initialize on component mount
  useEffect(() => {
    initializeAuth();
  }, []);

  // Create context value
  const contextValue: JWTAuthContextType = {
    isAuthenticated,
    isLoading,
    authData,
    logout
  };

  return (
    <JWTAuthContext.Provider value={contextValue}>
      {children}
    </JWTAuthContext.Provider>
  );
};

/**
 * Custom hook to use JWT authentication context
 */
export const useJWTAuth = (): JWTAuthContextType => {
  const context = useContext(JWTAuthContext);
  
  if (!context) {
    throw new Error('useJWTAuth must be used within a JWTAuthProvider');
  }
  
  return context;
};