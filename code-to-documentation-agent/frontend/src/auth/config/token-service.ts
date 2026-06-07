import { 
  AccountInfo, 
  AuthenticationResult, 
  SilentRequest,
  EndSessionRequest,
  InteractionRequiredAuthError
} from '@azure/msal-browser';
import { msalInstance, loginRequest, silentRequest } from './auth-config';

export class TokenService {
  /**
   * Get all accounts currently cached
   */
  static getAllAccounts(): AccountInfo[] {
    return msalInstance.getAllAccounts();
  }

  /**
   * Get the active account
   */
  static getActiveAccount(): AccountInfo | null {
    return msalInstance.getActiveAccount();
  }

  /**
   * Set the active account
   */
  static setActiveAccount(account: AccountInfo | null): void {
    msalInstance.setActiveAccount(account);
  }

  /**
   * Acquire token silently
   */
  static async acquireTokenSilent(account: AccountInfo): Promise<AuthenticationResult | null> {
    const request: SilentRequest = {
      ...silentRequest,
      account: account,
    };

    try {
      const response = await msalInstance.acquireTokenSilent(request);
      return response;
    } catch (error) {
      if (error instanceof InteractionRequiredAuthError) {
        // Fall back to interaction when silent call fails
        console.warn('Silent token acquisition failed. Using fallback to acquire token using popup.');
        return await this.acquireTokenPopup();
      }
      console.error('Silent token acquisition failed:', error);
      return null;
    }
  }

  /**
   * Acquire token using popup
   */
  static async acquireTokenPopup(): Promise<AuthenticationResult | null> {
    try {
      const response = await msalInstance.acquireTokenPopup(loginRequest);
      this.setActiveAccount(response.account);
      return response;
    } catch (error) {
      console.error('Token acquisition failed:', error);
      return null;
    }
  }

  /**
   * Login using popup
   */
  static async loginPopup(): Promise<AuthenticationResult | null> {
    try {
      const response = await msalInstance.loginPopup(loginRequest);
      this.setActiveAccount(response.account);
      return response;
    } catch (error) {
      console.error('Login failed:', error);
      return null;
    }
  }

  /**
   * Login using redirect
   */
  static async loginRedirect(): Promise<void> {
    try {
      await msalInstance.loginRedirect(loginRequest);
    } catch (error) {
      console.error('Login redirect failed:', error);
      throw error;
    }
  }

  /**
   * Logout
   */
  static async logout(account?: AccountInfo): Promise<void> {
    const logoutRequest: EndSessionRequest = {
      account: account || this.getActiveAccount(),
      postLogoutRedirectUri: window.location.origin + '/',
    };

    try {
      // Set a flag to indicate user is logging out
      sessionStorage.setItem('user_logging_out', 'true');
      await msalInstance.logoutPopup(logoutRequest);
    } catch (error) {
      console.error('Logout failed:', error);
      // Clear the flag if logout fails
      sessionStorage.removeItem('user_logging_out');
      throw error;
    }
  }

  /**
   * Check if user is authenticated
   */
  static isAuthenticated(): boolean {
    const accounts = this.getAllAccounts();
    return accounts.length > 0;
  }

  /**
   * Get user information from the active account
   */
  static getUserInfo(): {
    name?: string;
    email?: string;
    username?: string;
  } | null {
    const account = this.getActiveAccount();
    if (!account) return null;

    return {
      name: account.name,
      email: account.username,
      username: account.username,
    };
  }

  /**
   * Get access token for API calls
   */
  static async getAccessToken(): Promise<string | null> {
    const account = this.getActiveAccount();
    if (!account) {
      console.warn('No active account found');
      return null;
    }

    const tokenResponse = await this.acquireTokenSilent(account);
    return tokenResponse?.accessToken || null;
  }

  /**
   * Validate if token is still valid
   */
  static isTokenValid(token: string): boolean {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const currentTime = Date.now() / 1000;
      return payload.exp > currentTime;
    } catch (error) {
      console.error('Token validation failed:', error);
      return false;
    }
  }

  /**
   * Clear all cached tokens and accounts
   */
  static async clearCache(): Promise<void> {
    try {
      const accounts = this.getAllAccounts();
      for (const account of accounts) {
        await msalInstance.logoutPopup({
          account,
          postLogoutRedirectUri: window.location.origin,
        });
      }
    } catch (error) {
      console.error('Cache clearing failed:', error);
    }
  }
}

// Helper function to handle MSAL initialization
export const initializeMsal = async (): Promise<void> => {
  try {
    await msalInstance.initialize();
    
    // Handle redirect response if any
    const response = await msalInstance.handleRedirectPromise();
    if (response) {
      TokenService.setActiveAccount(response.account);
    } else {
      // Set the first account if available
      const accounts = TokenService.getAllAccounts();
      if (accounts.length > 0) {
        TokenService.setActiveAccount(accounts[0]);
      }
    }
  } catch (error) {
    console.error('MSAL initialization failed:', error);
    throw error;
  }
};