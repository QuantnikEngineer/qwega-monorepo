import { Configuration, PublicClientApplication, LogLevel } from '@azure/msal-browser';

// MSAL configuration
export const msalConfig: Configuration = {
  auth: {
    clientId: 'a919164d-8b7c-43fb-8119-f1997d45ca4f',
    authority: 'https://login.microsoftonline.com/258ac4e4-146a-411e-9dc8-79a9e12fd6da/v2.0',
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'localStorage',
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) {
          return;
        }
        switch (level) {
          case LogLevel.Error:
            console.error(message);
            return;
          case LogLevel.Info:
            console.info(message);
            return;
          case LogLevel.Verbose:
            console.debug(message);
            return;
          case LogLevel.Warning:
            console.warn(message);
            return;
          default:
            return;
        }
      },
    },
  },
};

// Create the main instance that your application will use for all MSAL operations
export const msalInstance = new PublicClientApplication(msalConfig);

// Login request configuration
export const loginRequest = {
  scopes: ['User.Read', 'profile', 'openid', 'email'],
};

// Scopes for token acquisition
export const graphConfig = {
  graphMeEndpoint: 'https://graph.microsoft.com/v1.0/me',
};

// Silent request that will acquire a token silently
export const silentRequest = {
  scopes: ['User.Read'],
  account: undefined, // This will be populated when user logs in
};