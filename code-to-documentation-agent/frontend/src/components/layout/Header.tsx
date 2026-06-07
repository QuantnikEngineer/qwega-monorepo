import React from "react";
import {
  Box,
  Select,
  MenuItem,
  FormControl,
  Typography,
  Avatar,
  IconButton,
} from "@mui/material";
import { ArrowBack } from "@mui/icons-material";
import { useEffect, useRef, useState } from "react";
import { useJWTAuth } from "../../jwt-auth/contexts/JWTAuthContext";
import API_CONFIG, { BUILD_AI_FRONTEND_URL } from "../../config/agentConfig";

interface HeaderProps {
  selectedProvider: string;
  selectedModel: string;
  onProviderChange: (provider: string) => void;
  onModelChange: (model: string) => void;
}

const Header: React.FC<HeaderProps> = ({
  selectedProvider,
  selectedModel,
  onProviderChange,
  onModelChange,
}) => {
  const [providers, setProviders] = useState<
    { key: string; label: string; default?: boolean }[]
  >([]);
  const [models, setModels] = useState<
    { key: string; label: string; provider: string; default?: boolean }[]
  >([]);
  const [configLoaded, setConfigLoaded] = useState(false);
  const [projectInfo, setProjectInfo] = useState<{ project_id: string; auth_provider: string } | null>(null);
  const requestCountRef = useRef(0);
  const baseUrl =
    window.location.origin + window.location.pathname.replace(/\/$/, "");

  // Helper function to construct API URLs based on baseUrl
  const constructApiUrl = (endpoint: string) => {
    if (baseUrl.includes("localhost")) {
      return `${API_CONFIG.DOMAIN}:${API_CONFIG.PORT}${endpoint}`;
    } else {
      return `${baseUrl}${endpoint}`;
    }
  };

  async function loadConfig() {
    try {
      // First, initialize secrets on the backend with JWT values
      if (authData?.project?.id || authData?.auth?.resourceProvider) {
        const initResp = await fetch(constructApiUrl("/api/init-secrets"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            project_id: authData?.project?.id || "",
            auth_provider: authData?.auth?.resourceProvider || "azure"
          })
        });
        
        if (initResp.ok) {
          const initData = await initResp.json();
          console.log("[DEBUG] Secrets initialized:", initData);
          setProjectInfo({
            project_id: authData?.project?.id || "",
            auth_provider: authData?.auth?.resourceProvider || "azure"
          });
        }
      }
      const resp = await fetch(
        constructApiUrl(API_CONFIG.ENDPOINTS.LLM_CONFIG)
      );
      if (!resp.ok) throw new Error("Failed to fetch /llm-config");
      const data = await resp.json();

      // Ignore the first call response (e.g., StrictMode double-fetch)
      // const currentCount = requestCountRef.current;
      // requestCountRef.current = currentCount + 1;
      // if (currentCount === 0) {
      //   return; // skip updating state for the first call
      // }

      console.log("[DEBUG] Fetched LLM config:", data);

      const fetchedProviders = Array.isArray(data.providers)
        ? data.providers
        : [];
      const fetchedModels = Array.isArray(data.models) ? data.models : [];

      const providerObjs = fetchedProviders.map((p: any) =>
        typeof p === "string" ? { key: p, label: p } : p
      );
      const modelObjs = fetchedModels.map((m: any) =>
        typeof m === "string"
          ? {
              key: m,
              label: m,
              provider: m.includes("/") ? m.split("/")[0] : "",
            }
          : m
      );

      setProviders(providerObjs);
      setModels(modelObjs);
      setConfigLoaded(true);
      console.log("models and providers", modelObjs, providerObjs, models, providers);

      // Set default provider and model based on 'default: true' from config
      const defaultProvider = providerObjs.find((p: any) => p.default === true);
      if (defaultProvider) {
        onProviderChange(defaultProvider.key);
        
        // Find default model for this provider
        const defaultModel = modelObjs.find(
          (m: any) => m.default === true && m.provider === defaultProvider.key
        );
        if (defaultModel) {
          onModelChange(defaultModel.key);
        } else {
          // Fallback to first model of the default provider if no default model
          const firstModelForProvider = modelObjs.find(
            (m: any) => m.provider === defaultProvider.key
          );
          if (firstModelForProvider) {
            onModelChange(firstModelForProvider.key);
          }
        }
      } else if (providerObjs.length > 0) {
        // Fallback to first provider if no default
        onProviderChange(providerObjs[0].key);
        const firstModelForProvider = modelObjs.find(
          (m: any) => m.provider === providerObjs[0].key
        );
        if (firstModelForProvider) {
          onModelChange(firstModelForProvider.key);
        }
      }
    } catch (e) {
      console.error("[ERROR] Failed to load LLM config:", e);
      setProviders([]);
      setModels([]);
      setConfigLoaded(true); // allow UI to render with current selections
    }
  }

  // Load provider/model config from backend only
  useEffect(() => {
    loadConfig();
  }, []);

  // JWT Authentication (ACTIVE)
  const { authData, isAuthenticated } = useJWTAuth();
  const user = authData?.user;

  // Get provider and model labels
  const getProviderLabel = (providerKey: string) => {
    const provider = providers.find((p: { key: string; label: string; default?: boolean }) => p.key === providerKey);
    return provider ? provider.label : providerKey;
  };

  const getModelLabel = (modelKey: string) => {
    const model = models.find((m: { key: string; label: string; provider: string; default?: boolean }) => m.key === modelKey);
    return model ? model.label : modelKey;
  };

  // Generate user initials from the authenticated user's name
  const getUserInitials = (name?: string) => {
    return (
      name
        ?.split(" ")
        .map((part) => part.charAt(0))
        .join("")
        .toUpperCase()
        .slice(0, 2) || "U"
    );
  };

  // Get user display name
  const getUserDisplayName = () => {
    if (!isAuthenticated || !authData?.user) return "Not signed in";
    return authData?.user.name || "Unknown User";
  };

  // Get user role (from user claims or default)
  const getUserRole = () => {
    return "Admin"; // Default role, can be customized based on user data
  };

  const handleBackClick = () => {
    window.location.href = `${BUILD_AI_FRONTEND_URL}/`;
  };

  return (
    <>
      {/* Desktop Header - only show on larger screens */}
      <Box
        sx={{
          display: { xs: "none", lg: "flex" },
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "20px 40px",
          backgroundColor: "#ffffff",
          minHeight: "80px",
          boxShadow: "0 8px 24px rgba(0, 0, 0, 0.2)",
          borderRadius: "16px",
          border: "1px solid #e5e7eb",
          zIndex: 10,
          margin: 0,
        }}
      >
        {/* Left side - Back Button and Agent Info */}
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: { xs: 1, sm: 2 },
            width: { xs: "100%", md: "auto" },
          }}
        >
          <IconButton
            onClick={handleBackClick}
            sx={{
              color: "#6b7280",
              "&:hover": {
                backgroundColor: "#f3f4f6",
                color: "#374151",
              },
            }}
          >
            <ArrowBack />
          </IconButton>
          <Avatar
            sx={{
              background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
              color: "white",
              width: { xs: 32, md: 40 },
              height: { xs: 32, md: 40 },
              fontSize: { xs: "12px", md: "14px" },
              fontWeight: "bold",
              boxShadow: "0 4px 12px rgba(99, 102, 241, 0.3)",
            }}
          >
            CD
          </Avatar>
          <Box>
            <Box
              sx={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: 1,
              }}
            >
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 600,
                  color: "#1f2937",
                  fontSize: { xs: "14px", sm: "16px", md: "20px" },
                }}
              >
                Code To Documentation Agent
              </Typography>
              <Box
                sx={{
                  backgroundColor: "#dbeafe",
                  color: "#3b82f6",
                  px: 1.5,
                  py: 0.3,
                  borderRadius: "20px",
                  fontSize: { xs: "11px", sm: "13px" },
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  gap: 0.4,
                }}
              >
                💬 Active
              </Box>
            </Box>
            <Typography
              variant="body2"
              sx={{ color: "#6b7280", fontSize: { xs: "11px", sm: "14px" } }}
            >
              {configLoaded
                ? `AI-Powered Documentation | ${getModelLabel(
                    selectedModel
                  )} on ${getProviderLabel(selectedProvider)}`
                : "AI-Powered Documentation"}
            </Typography>
          </Box>
        </Box>

        {/* Right side - Provider/Model Selection and User Info */}
        <Box
          sx={{
            display: "flex",
            flexDirection: { xs: "column", sm: "row" },
            alignItems: { xs: "flex-start", sm: "center" },
            gap: { xs: 2, sm: 3 },
            width: { xs: "100%", md: "auto" },
          }}
        >
          {/* Provider and Model Selection (render only after config is loaded) */}
          <Box
            sx={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: { xs: 1, sm: 2 },
            }}
          >
            {!configLoaded && (
              <Typography
                variant="body2"
                sx={{ color: "#6b7280", fontStyle: "italic" }}
              >
                Loading LLM providers and models...
              </Typography>
            )}
            {configLoaded && (
              <Typography
                variant="body2"
                sx={{
                  color: "#374151",
                  fontWeight: 500,
                  display: { xs: "none", sm: "block" },
                }}
              >
                Provider:
              </Typography>
            )}
            {configLoaded && (
              <FormControl size="small" sx={{ minWidth: { xs: 100, sm: 120 } }}>
                <Select
                  value={selectedProvider}
                  onChange={(e) => onProviderChange(e.target.value)}
                  displayEmpty
                  sx={{
                    fontSize: { xs: "12px", sm: "14px" },
                    "& .MuiOutlinedInput-notchedOutline": {
                      borderColor: "#d1d5db",
                    },
                  }}
                >
                  {(providers.length
                    ? providers
                    : [{ key: selectedProvider, label: selectedProvider }]
                  ).map((provider) => (
                    <MenuItem key={provider.key} value={provider.key}>
                      {provider.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
            {configLoaded && (
              <Typography
                variant="body2"
                sx={{
                  color: "#374151",
                  fontWeight: 500,
                  display: { xs: "none", sm: "block" },
                }}
              >
                Model:
              </Typography>
            )}
            {configLoaded && (
              <FormControl size="small" sx={{ minWidth: { xs: 100, sm: 120 } }}>
                <Select
                  value={selectedModel}
                  onChange={(e) => onModelChange(e.target.value)}
                  displayEmpty
                  sx={{
                    fontSize: { xs: "12px", sm: "14px" },
                    "& .MuiOutlinedInput-notchedOutline": {
                      borderColor: "#d1d5db",
                    },
                  }}
                >
                  {(models.length
                    ? models.filter(
                        (model) => model.provider === selectedProvider
                      )
                    : [
                        {
                          key: selectedModel,
                          label: selectedModel,
                          provider: selectedProvider,
                        },
                      ]
                  ).map((model) => (
                    <MenuItem key={model.key} value={model.key}>
                      {model.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
          </Box>

          {/* User Info */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            <Box sx={{ textAlign: "right" }}>
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 600,
                  color: "#1f2937",
                  fontSize: { xs: "11px", sm: "14px" },
                }}
              >
                {getUserDisplayName()} {isAuthenticated && `(${getUserRole()})`}
              </Typography>
              <Typography
                variant="body2"
                sx={{ color: "#6b7280", fontSize: { xs: "10px", sm: "12px" } }}
              >
                Project: {authData?.project?.name || "Default Project"}
              </Typography>
            </Box>
            <Avatar
              sx={{
                background: "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
                color: "white",
                width: { xs: 28, sm: 32 },
                height: { xs: 28, sm: 32 },
                fontSize: { xs: "12px", sm: "14px" },
                fontWeight: "bold",
                boxShadow: "0 4px 12px rgba(59, 130, 246, 0.3)",
              }}
            >
              {getUserInitials(getUserDisplayName())}
            </Avatar>
          </Box>
        </Box>
      </Box>
    </>
  );
};

export default Header;
