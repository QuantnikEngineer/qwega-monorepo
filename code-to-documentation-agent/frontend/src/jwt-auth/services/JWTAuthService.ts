import CryptoJS from "crypto-js";

// JWT Payload Interface (matches the build ai app's EncryptedJWTPayload)
export interface EncryptedJWTPayload {
  user: {
    name?: string;
    email?: string;
    username?: string;
  };
  project?: {
    id?: string;
    name?: string;
    type?: string;
    agentId?: string;
  };
  auth: {
    msalAccessToken: string;
    resourceProvider: string;
  };
  metadata: {
    expiresAt: number;
    issuer: string;
  };
}

export class JWTAuthService {
  // Must match the ENCRYPTION_KEY in build ai app's secure-token.service.ts
  private static readonly ENCRYPTION_KEY = "X7k9P2mQ8vR5nE3wS6tY1uI4oL0aZ9bF"; // 32 chars for AES-256
  private static readonly IV_LENGTH = 16;

  private authData: EncryptedJWTPayload | null = null;
  private isAuthenticated: boolean = false;

  // Callback functions
  public onAuthenticated?: (data: EncryptedJWTPayload) => void;
  public onAuthenticationFailure?: (error?: Error) => void;

  /**
   * Decrypt JWT payload using CryptoJS AES-256-CBC (matches main app encryption)
   * Expected format from main app: "iv_hex:encrypted_base64_data"
   */
  private static decryptJWT(encryptedData: string): any {
    try {
      // Validate input format
      if (!encryptedData || typeof encryptedData !== "string") {
        throw new Error("Invalid encrypted data: must be a non-empty string");
      }

      // Validate token format (should be iv:encrypted_data)
      if (!encryptedData.includes(":")) {
        throw new Error('Invalid token format: expected "iv:encrypted_data"');
      }

      // Split IV and encrypted data (format: iv_hex:encrypted_base64_data)
      const [ivHex, encryptedPayload] = encryptedData.split(":");

      if (!ivHex || !encryptedPayload) {
        throw new Error("Invalid encrypted data format: missing IV or payload");
      }

      // Convert hex string back to WordArray (CryptoJS format)
      const iv = CryptoJS.enc.Hex.parse(ivHex);

      // Decrypt using CryptoJS AES (must match main app's encryption settings)
      const decrypted = CryptoJS.AES.decrypt(
        encryptedPayload,
        this.ENCRYPTION_KEY,
        {
          iv: iv,
          mode: CryptoJS.mode.CBC,
          padding: CryptoJS.pad.Pkcs7,
        }
      );

      // Convert decrypted WordArray to UTF-8 string
      const decryptedText = decrypted.toString(CryptoJS.enc.Utf8);

      if (!decryptedText) {
        throw new Error(
          "Decryption failed: empty result (possible key mismatch)"
        );
      }

      // Parse the JSON payload
      return JSON.parse(decryptedText);
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to decrypt JWT token: ${errorMessage}`);
    }
  }

  /**
   * Initialize JWT authentication
   * Looks for auth_token in URL params or checks existing session
   */
  async initializeAuth(): Promise<void> {
    try {
      // Extract auth token from URL
      const urlParams = new URLSearchParams(window.location.search);
      const authToken = urlParams.get("auth_token");

      if (authToken && authToken.trim().length > 0) {
        await this.handleJWTToken(authToken.trim());
      } else {
        // Check for existing valid session in localStorage
        const existingAuth = this.checkExistingAuth();
        if (existingAuth) {
          // Validate the MSAL token before accepting the existing auth
          const isValidMSAL = await this.validateMSALToken(
            existingAuth.auth.msalAccessToken
          );
          if (isValidMSAL) {
            this.authData = existingAuth;
            this.isAuthenticated = true;

            if (this.onAuthenticated && this.authData) {
              this.onAuthenticated(this.authData);
            }
          } else {
            localStorage.removeItem("jwt_auth_data");
            this.handleAuthenticationFailure();
          }
        } else {
          this.handleAuthenticationFailure();
        }
      }
    } catch (error) {
      this.handleAuthenticationFailure(error as Error);
    }
  }

  /**
   * Handle JWT token validation
   */
  private async handleJWTToken(token: string): Promise<void> {
    try {
      // Basic format validation
      if (!token.includes(":")) {
        throw new Error("Invalid token format - missing IV separator");
      }

      const parts = token.split(":");
      if (parts.length !== 2) {
        throw new Error('Invalid token format - expected "iv:encrypted_data"');
      }

      const [ivHex, encryptedPayload] = parts;
      if (!ivHex || !encryptedPayload) {
        throw new Error("Invalid token format - empty IV or payload");
      }

      // IV should be 32 hex characters (16 bytes)
      if (ivHex.length !== 32) {
        throw new Error(
          `Invalid IV length - expected 32 hex chars, got ${ivHex.length}`
        );
      }

      // Decrypt and parse the JWT token
      const payload: EncryptedJWTPayload = JWTAuthService.decryptJWT(token);

      // Validate token expiration
      if (Date.now() > payload.metadata.expiresAt) {
        throw new Error("JWT token has expired");
      }

      // Validate MSAL token with Microsoft Graph
      const isValidMSAL = await this.validateMSALToken(
        payload.auth.msalAccessToken
      );
      if (!isValidMSAL) {
        throw new Error("MSAL token in JWT is invalid");
      }

      // Store the encrypted payload directly
      this.authData = payload;

      this.isAuthenticated = true;

      // Store auth data in localStorage for persistence
      localStorage.setItem("jwt_auth_data", JSON.stringify(this.authData));

      // Clean up URL (remove token parameter for security)
      const url = new URL(window.location.href);
      url.searchParams.delete("auth_token");
      window.history.replaceState({}, document.title, url.toString());

      // Call success callback
      if (this.onAuthenticated && this.authData) {
        this.onAuthenticated(this.authData);
      }
    } catch (error) {
      this.handleAuthenticationFailure(error as Error);
    }
  }

  /**
   * Check for existing authentication in localStorage
   */
  private checkExistingAuth(): EncryptedJWTPayload | null {
    try {
      const authDataStr = localStorage.getItem("jwt_auth_data");
      if (!authDataStr) return null;

      const authData: EncryptedJWTPayload = JSON.parse(authDataStr);

      // Check if auth is still valid (expiresAt is already in milliseconds)
      if (Date.now() > authData.metadata.expiresAt) {
        localStorage.removeItem("jwt_auth_data");
        return null;
      }

      return authData;
    } catch (error) {
      localStorage.removeItem("jwt_auth_data");
      return null;
    }
  }

  /**
   * Validate MSAL token with Microsoft Graph
   */
  private async validateMSALToken(token: string): Promise<boolean> {
    try {
      const response = await fetch("https://graph.microsoft.com/v1.0/me", {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
      });

      return response.ok;
    } catch (error) {
      console.error("MSAL token validation failed:", error);
      return false;
    }
  }

  /**
   * Handle authentication failures (both errors and unauthenticated access)
   */
  private handleAuthenticationFailure(error?: Error): void {
    if (error) {
      console.error("🚨 Authentication Error:", error.message);
    } else {
      console.warn("⚠️ Agent accessed without proper authentication");
    }

    if (this.onAuthenticationFailure) {
      this.onAuthenticationFailure(error);
    }
  }

  logout(): void {
    this.authData = null;
    this.isAuthenticated = false;
    localStorage.removeItem("jwt_auth_data");
  }
}

// Create singleton instance
export const jwtAuthService = new JWTAuthService();