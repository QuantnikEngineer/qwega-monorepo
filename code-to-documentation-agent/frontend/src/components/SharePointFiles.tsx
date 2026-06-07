import React, { useState, useEffect } from "react";
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Card,
  CardContent,
  Chip,
  Divider,
  Button,
  CircularProgress,
  Alert,
  Tooltip,
} from "@mui/material";
import {
  Folder as FolderIcon,
  InsertDriveFile as FileIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
  OpenInNew as OpenInNewIcon,
  Description as DescriptionIcon,
  Image as ImageIcon,
  PictureAsPdf as PdfIcon,
  TableChart as SpreadsheetIcon,
  VideoFile as VideoIcon,
  AudioFile as AudioIcon,
  Archive as ArchiveIcon,
  ArrowBack as ArrowBackIcon,
  CloudUpload as CloudUploadIcon,
} from "@mui/icons-material";
import API_CONFIG from "../config/agentConfig";
import { useJWTAuth } from '../jwt-auth/contexts/JWTAuthContext';

interface SharePointFile {
  id: string;
  name: string;
  isFolder: boolean;
  size: number;
  createdDateTime: string;
  lastModifiedDateTime: string;
  webUrl: string;
  downloadUrl: string;
  mimeType: string;
  createdBy: string;
}

interface SharePointFilesProps {
  onFileSelect?: (file: SharePointFile) => void;
}

const SharePointFiles: React.FC<SharePointFilesProps> = ({ onFileSelect }) => {
  const [files, setFiles] = useState<SharePointFile[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [folderPath, setFolderPath] = useState<string>("");
  const [siteName, setSiteName] = useState<string>("");
  const [navigationHistory, setNavigationHistory] = useState<string[]>([]);
  const [currentPath, setCurrentPath] = useState<string>("BuilderAI");
  const { authData } = useJWTAuth();

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

  const getFileIcon = (file: SharePointFile) => {
    if (file.isFolder) {
      return <FolderIcon color="primary" />;
    }

    const mimeType = file.mimeType.toLowerCase();
    if (mimeType.includes("pdf")) {
      return <PdfIcon style={{ color: "#d32f2f" }} />;
    } else if (mimeType.includes("word") || mimeType.includes("document")) {
      return <DescriptionIcon style={{ color: "#1976d2" }} />;
    } else if (mimeType.includes("excel") || mimeType.includes("spreadsheet")) {
      return <SpreadsheetIcon style={{ color: "#388e3c" }} />;
    } else if (mimeType.includes("image")) {
      return <ImageIcon style={{ color: "#f57c00" }} />;
    } else if (mimeType.includes("video")) {
      return <VideoIcon style={{ color: "#7b1fa2" }} />;
    } else if (mimeType.includes("audio")) {
      return <AudioIcon style={{ color: "#5d4037" }} />;
    } else if (
      mimeType.includes("zip") ||
      mimeType.includes("rar") ||
      mimeType.includes("archive")
    ) {
      return <ArchiveIcon style={{ color: "#616161" }} />;
    }
    return <FileIcon />;
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    if (!dateString) return "Unknown";
    return (
      new Date(dateString).toLocaleDateString() +
      " " +
      new Date(dateString).toLocaleTimeString()
    );
  };

  const fetchSharePointFiles = async (folderPath?: string) => {
    setLoading(true);
    setError("");

    try {
      const queryParams = new URLSearchParams();
      if (folderPath) {
        queryParams.append("folder_path", folderPath);
      }

      const url = constructApiUrl(
        `${API_CONFIG.ENDPOINTS.LIST_SHAREPOINT_FILES}?${queryParams}`
      );

      const response = await fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        setFiles(data.files || []);
        setFolderPath(data.folder_path || "");
        setSiteName(data.site_name || "");
        setCurrentPath(folderPath || "BuilderAI");
      } else {
        setError(data.error || "Failed to fetch SharePoint files");
      }
    } catch (err) {
      console.error("Error fetching SharePoint files:", err);
      setError(err instanceof Error ? err.message : "Unknown error occurred");
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (file: SharePointFile) => {
    if (file.isFolder) return;

    try {
       const queryParams = new URLSearchParams();
      if (folderPath) {
        queryParams.append("folder_path", folderPath);
      }
      const response = await fetch(
        constructApiUrl(
          `${API_CONFIG.ENDPOINTS.DOWNLOAD_SHAREPOINT_FILE}/${file.id}/download?${queryParams}`
        ),
        {
          method: "GET",
        }
      );

      if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
      }

      // Create download link
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.name;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Error downloading file:", err);
      setError(err instanceof Error ? err.message : "Download failed");
    }
  };

  const handleOpenInSharePoint = (file: SharePointFile) => {
    if (file.webUrl) {
      window.open(file.webUrl, "_blank");
    }
  };

  const handleFolderClick = (folderName: string) => {
    const newPath = currentPath ? `${currentPath}/${folderName}` : folderName;
    setNavigationHistory([...navigationHistory, currentPath]);
    fetchSharePointFiles(newPath);
  };

  const handleBackNavigation = () => {
    if (navigationHistory.length > 0) {
      const previousPath = navigationHistory[navigationHistory.length - 1];
      const newHistory = navigationHistory.slice(0, -1);
      setNavigationHistory(newHistory);
      fetchSharePointFiles(previousPath);
    }
  };

  const handleBreadcrumbClick = (pathIndex: number) => {
    const pathParts = currentPath.split("/");
    const newPath = pathParts.slice(0, pathIndex + 1).join("/");
    const newHistory = navigationHistory.slice(0, pathIndex);
    setNavigationHistory(newHistory);
    fetchSharePointFiles(newPath);
  };

  useEffect(() => {
    fetchSharePointFiles(); // Load initial files from default folder
  }, []);

  return (
    <Card
      sx={{
        width: "100%",
        backgroundColor: "#ffffff",
        borderRadius: "8px",
        boxShadow: "none",
        overflow: "hidden",
        zIndex: 5,
        marginBottom: 1,
        alignSelf: "flex-start",
      }}
    >
      <CardContent sx={{ paddingTop: '12px !important' }}>
        <Box
          display="flex"
          justifyContent="flex-end"
          alignItems="center"
          mb={1}
        >
          <Button
            startIcon={
              loading ? <CircularProgress size={16} /> : <RefreshIcon />
            }
            onClick={() => fetchSharePointFiles(currentPath)}
            disabled={loading}
            size="small"
            sx={{
              textTransform: 'uppercase',
              fontWeight: 600,
              color: '#1976d2',
              fontSize: '13px',
              '&:hover': {
                backgroundColor: 'rgba(25, 118, 210, 0.04)',
              }
            }}
          >
            Refresh
          </Button>
        </Box>

        {siteName && currentPath && (
          <Box mb={1.5}>
            <Box display="flex" alignItems="center" gap={1} mb={0.5}>
              {navigationHistory.length > 0 && (
                <Button
                  size="small"
                  onClick={handleBackNavigation}
                  startIcon={<ArrowBackIcon />}
                  variant="outlined"
                >
                  Back
                </Button>
              )}
            </Box>
            <Typography variant="body2" color="text.secondary">
              📍 Location:{" "}
              {currentPath.split("/").map((part, index, array) => (
                <span key={index}>
                  <Button
                    size="small"
                    onClick={() => handleBreadcrumbClick(index)}
                    style={{
                      textTransform: "none",
                      minWidth: "auto",
                      padding: "2px 4px",
                      fontSize: "12px",
                      color: index === array.length - 1 ? "#666" : "#007bff",
                    }}
                    disabled={index === array.length - 1}
                  >
                    {part}
                  </Button>
                  {index < array.length - 1 && " / "}
                </span>
              ))}
            </Typography>
          </Box>
        )}

        {error && (
          <Alert 
            severity={error.toLowerCase().includes("not configured") ? "info" : "error"} 
            sx={{ mb: 1 }}
          >
            {error}
          </Alert>
        )}

        {loading ? (
          <Box display="flex" justifyContent="center" p={3}>
            <CircularProgress />
          </Box>
        ) : (
          <List>
            {files.length === 0 && !loading && (
              <ListItem>
                <ListItemText
                  primary="No files found"
                  secondary="The SharePoint folder appears to be empty or inaccessible."
                />
              </ListItem>
            )}

            {files.map((file) => (
              <React.Fragment key={file.id}>
                <ListItem
                  sx={{
                    "&:hover": {
                      backgroundColor: "action.hover",
                    },
                    cursor: file.isFolder ? "pointer" : "default",
                  }}
                  onClick={() => {
                    if (file.isFolder) {
                      handleFolderClick(file.name);
                    }
                  }}
                >
                  <ListItemIcon>{getFileIcon(file)}</ListItemIcon>

                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography
                          variant="body2"
                          sx={{ fontWeight: file.isFolder ? "bold" : "normal" }}
                        >
                          {file.name}
                        </Typography>
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          Created by: {file.createdBy}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Modified: {formatDate(file.lastModifiedDateTime)}
                        </Typography>
                      </Box>
                    }
                  />

                  <Box display="flex" gap={1}>
                    {!file.isFolder && (
                      <Tooltip title="Download file">
                        <IconButton
                          onClick={() => handleDownload(file)}
                          size="small"
                          color="primary"
                        >
                          <DownloadIcon />
                        </IconButton>
                      </Tooltip>
                    )}

                    {file.webUrl && (
                      <Tooltip title="Open in SharePoint">
                        <IconButton
                          onClick={() => handleOpenInSharePoint(file)}
                          size="small"
                          color="secondary"
                        >
                          <OpenInNewIcon />
                        </IconButton>
                      </Tooltip>
                    )}
                  </Box>
                </ListItem>
                <Divider />
              </React.Fragment>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
};

export default SharePointFiles;
