import React from 'react';
import { 
  Button, 
  Collapse,
  Typography,
  Box,
  Chip,
  ListItemButton,
  LinearProgress,
  Checkbox,
  CircularProgress,
} from '@mui/material';
import { 
  ExpandMore, 
  ExpandLess,
  Refresh as RefreshIcon,
} from '@mui/icons-material';

interface Repository {
  id: string;
  name: string;
  description?: string;
  language?: string;
  updated_at?: string;
  size?: number;
  project_id?: string;
  [key: string]: any; // Allow for additional properties from the API
}

interface RepositorySectionProps {
  repos: Repository[];
  isLoadingRepos: boolean;
  reposError: string;
  selectedRepoIds: string[];
  isExpanded: boolean;
  onToggle: () => void;
  onRepoClick: (repoId: string) => void;
  onRefreshRepos: () => void;
  projectId?: string;
  projectName?: string;
}

export const RepositorySection: React.FC<RepositorySectionProps> = ({
  repos,
  isLoadingRepos,
  reposError,
  selectedRepoIds,
  isExpanded,
  onToggle,
  onRepoClick,
  onRefreshRepos,
  projectId,
  projectName,
}) => {
  
  const formatDate = (dateString?: string) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric' 
    });
  };

  const formatSize = (bytes?: number) => {
    if (!bytes) return '';
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(0)} KB`;
    const mb = kb / 1024;
    return `${mb.toFixed(1)} MB`;
  };

  return (
    <Box
      sx={{
        backgroundColor: "#ffffff",
        borderRadius: "8px",
        boxShadow: "0 2px 8px rgba(0, 0, 0, 0.1)",
        overflow: "hidden",
        border: "none",
        marginBottom: "8px",
        position: "relative",
      }}
    >
      {/* Repository Section Header */}
      <ListItemButton
        onClick={onToggle}
        sx={{
          padding: "8px 12px",
          backgroundColor: "#ffffff",
          borderRadius: "8px 8px 0 0",
          minHeight: "40px",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, width: "100%" }}>
           <Typography
            variant="h6"
            sx={{ display: "flex", alignItems: "center", fontSize: "14px", fontWeight: 600 }}
          >
            📚 Code Contexts
          </Typography>
          <Typography 
            variant="body2" 
            color="text.secondary"
            sx={{ 
              ml: 1.5,
              bgcolor: selectedRepoIds.length > 0 ? '#e3f2fd' : '#f5f5f5',
              px: 1,
              py: 0.25,
              borderRadius: '10px',
              fontWeight: 500,
              fontSize: '11px'
            }}
          >
            {selectedRepoIds.length} selected
          </Typography>
          <Box
            sx={{ ml: "auto", display: "flex", alignItems: "center", gap: 1 }}
          >
            <Button
              size="small"
              startIcon={
                isLoadingRepos ? <CircularProgress size={16} /> : <RefreshIcon />
              }
              onClick={(e) => {
                e.stopPropagation();
                onRefreshRepos();
              }}
              disabled={isLoadingRepos}
              sx={{
                fontSize: "13px",
                textTransform: "uppercase",
                minWidth: "auto",
                fontWeight: 600,
                color: "#1976d2",
                px: 1.5,
                '&:hover': {
                  backgroundColor: 'rgba(25, 118, 210, 0.04)',
                }
              }}
            >
              {isExpanded ? 'Refresh' : ''}
            </Button>
            <Box sx={{ color: "#666" }}>
              {isExpanded ? <ExpandLess style={{ fontSize: "20px" }} /> : <ExpandMore style={{ fontSize: "20px" }} />}
            </Box>
          </Box>
        </Box>
      </ListItemButton>

      {/* Expanded Content */}
      <Collapse in={isExpanded} timeout="auto" unmountOnExit>
        <Box
          sx={{
            padding: "8px 12px",
            backgroundColor: "#f8f9fa",
            maxHeight: "300px",
            overflowY: "auto",
            "&::-webkit-scrollbar": {
              width: "8px",
            },
            "&::-webkit-scrollbar-track": {
              background: "#f1f1f1",
              borderRadius: "4px",
            },
            "&::-webkit-scrollbar-thumb": {
              background: "#c1c1c1",
              borderRadius: "4px",
              "&:hover": {
                background: "#a8a8a8",
              },
            },
          }}
        >
          {/* Loading indicator */}
          {isLoadingRepos && (
            <Typography 
              variant="body2" 
              color="textSecondary" 
              style={{ textAlign: 'center', padding: '24px' }}
            >
              Loading repositories...
            </Typography>
          )}

          {/* Error message */}
          {reposError && (
            <Box 
              style={{ 
                textAlign: 'center', 
                padding: '12px',
                color: reposError.toLowerCase().includes('not configured') ? '#1976d2' : '#d32f2f',
                background: reposError.toLowerCase().includes('not configured') ? '#e3f2fd' : '#ffebee',
                borderRadius: '8px',
                border: reposError.toLowerCase().includes('not configured') ? '1px solid #90caf9' : '1px solid #ffcdd2',
                marginBottom: '12px'
              }}
            >
              <Typography variant="body2">{reposError}</Typography>
            </Box>
          )}

          {/* Repository Cards */}
          {!isLoadingRepos && !reposError && repos.length > 0 && (
            <Box>
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                {repos.map((repo, index) => (
                  <Box
                    key={repo.id}
                    onClick={() => onRepoClick(repo.id)}
                    sx={{
                      border: selectedRepoIds.includes(repo.id) 
                        ? "2px solid #4CAF50" 
                        : "1px solid #e0e0e0",
                      borderRadius: "6px",
                      padding: "10px 12px",
                      backgroundColor: selectedRepoIds.includes(repo.id) 
                        ? "#e8f5e9" 
                        : "#ffffff",
                      cursor: "pointer",
                      overflow: "hidden",
                      wordBreak: "break-word",
                      "&:hover": {
                        backgroundColor: "#f5f5f5",
                      },
                    }}
                  >
                    <Box sx={{ display: "flex", alignItems: "flex-start" }}>
                      {/* Checkbox */}
                      <Checkbox
                        checked={selectedRepoIds.includes(repo.id)}
                        onChange={() => onRepoClick(repo.id)}
                        onClick={(e) => e.stopPropagation()}
                        sx={{
                          padding: "4px",
                          mr: 1,
                          color: "#9e9e9e",
                          "&.Mui-checked": {
                            color: "#4CAF50",
                          },
                        }}
                      />
                      
                      {/* Repository Details */}
                      <Box sx={{ flex: 1 }}>
                        {/* Repository Name and Selection Icon */}
                        <Box
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            mb: 1,
                          }}
                        >
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              gap: 1,
                              flex: 1,
                            }}
                          >
                            <Typography
                              variant="body2"
                              sx={{
                                fontWeight: 600,
                                color: "#333",
                                fontSize: "13px",
                                lineHeight: 1.4,
                                wordBreak: "break-word",
                                whiteSpace: "normal",
                              }}
                            >
                              {repo.name}
                            </Typography>
                          </Box>

                          {/* Language Badge */}
                          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                            {repo.language && (
                              <Chip
                                label={repo.language}
                                size="small"
                                sx={{
                                  fontSize: "10px",
                                  height: "20px",
                                  bgcolor: "#e0e0e0",
                                  color: "#666",
                                  fontWeight: 500,
                                }}
                              />
                            )}
                          </Box>
                        </Box>

                        {/* Repository Description */}
                        {repo.description && (
                          <Typography 
                            variant="caption" 
                            color="text.secondary"
                            sx={{ 
                              display: "block",
                              mb: 1,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                              wordBreak: "break-all",
                              maxWidth: "100%",
                            }}
                          >
                            {repo.description}
                          </Typography>
                        )}

                        {/* Repository Metadata */}
                        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                          {repo.updated_at && (
                            <Typography variant="caption" color="text.secondary">
                              Updated: {formatDate(repo.updated_at)}
                            </Typography>
                          )}
                          {repo.size !== undefined && (
                            <Typography variant="caption" color="text.secondary">
                              {formatSize(repo.size)}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                    </Box>
                  </Box>
                ))}
              </Box>
            </Box>
          )}

          {/* No repositories message */}
          {!isLoadingRepos && !reposError && repos.length === 0 && (
            <Typography
              variant="body2"
              color="textSecondary"
              style={{
                textAlign: "center",
                padding: "24px",
                background: "#f8f9fa",
                borderRadius: "8px",
                border: "1px solid #e9ecef",
              }}
            >
              No repositories found
            </Typography>
          )}
        </Box>
      </Collapse>
      
      {/* Linear Progress for Refresh Loading */}
      {isLoadingRepos && (
        <LinearProgress
          sx={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            borderBottomLeftRadius: "12px",
            borderBottomRightRadius: "12px",
            height: "3px",
            "& .MuiLinearProgress-bar": {
              backgroundColor: "#3b82f6",
            },
            "& .MuiLinearProgress-root": {
              backgroundColor: "rgba(59, 130, 246, 0.1)",
            },
          }}
        />
      )}
    </Box>
  );
};

