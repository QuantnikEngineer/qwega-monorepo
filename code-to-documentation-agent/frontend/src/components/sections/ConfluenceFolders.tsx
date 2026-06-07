import React from "react";
import { Box, Typography, ListItemButton, Collapse, LinearProgress } from "@mui/material";
import { ExpandMore, ExpandLess, Article } from "@mui/icons-material";
import ConfluenceFiles, {
  SelectedConfluenceFile,
} from "../content/ConfluenceFiles";

export type { SelectedConfluenceFile };

interface ConfluenceFoldersProps {
  isExpanded?: boolean;
  onToggle?: () => void;
  onSelectedFilesChange?: (files: SelectedConfluenceFile[]) => void;
  externalSelectedFiles?: SelectedConfluenceFile[]; // For syncing with parent state
}

const ConfluenceFolders: React.FC<ConfluenceFoldersProps> = ({
  isExpanded: externalIsExpanded,
  onToggle,
  onSelectedFilesChange,
  externalSelectedFiles,
}) => {
  const [internalIsExpanded, setInternalIsExpanded] = React.useState(false);
  const [selectedFilesCount, setSelectedFilesCount] = React.useState(0);
  const [selectedFilesArray, setSelectedFilesArray] = React.useState<
    SelectedConfluenceFile[]
  >([]);
  const [isLoading, setIsLoading] = React.useState(false);

  // Use external state if provided, otherwise use internal state
  const isExpanded =
    externalIsExpanded !== undefined ? externalIsExpanded : internalIsExpanded;
  const handleToggle =
    onToggle || (() => setInternalIsExpanded(!internalIsExpanded));

  const handleSelectionCountChange = (count: number) => {
    setSelectedFilesCount(count);
  };

  const handleSelectedFilesChange = (files: SelectedConfluenceFile[]) => {
    setSelectedFilesArray(files);
    console.log("Selected Confluence Files Array in ConfluenceFolders:", files);

    // Pass to parent component (Agent)
    if (onSelectedFilesChange) {
      onSelectedFilesChange(files);
    }
  };

  return (
    <Box
      sx={{
        width: { xs: "100%", sm: "400px" },
        maxWidth: "100%",
        backgroundColor: "#ffffff",
        borderRadius: "12px",
        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.18)",
        overflow: "hidden",
        zIndex: 5,
        margin: 0,
        alignSelf: "flex-start",
        mt: { xs: 0, sm: 2 },
        position: "relative",
      }}
    >
      {/* Confluence Folders Header */}
      <ListItemButton
        onClick={handleToggle}
        sx={{
          p: 2,
          "&:hover": {
            backgroundColor: "#f9fafb",
          },
        }}
      >
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1.5,
            width: "100%",
          }}
        >
          <Article sx={{ color: "#6b7280" }} />
          <Typography
            variant="body1"
            sx={{ fontWeight: 600, color: "#000000" }}
          >
            Confluence
          </Typography>
          <Typography
            variant="body2"
            sx={{
              backgroundColor: "#f3f4f6",
              color: "#000000",
              px: 1.5,
              py: 0.25,
              borderRadius: "12px",
              fontSize: "12px",
              fontWeight: 600,
            }}
          >
            {selectedFilesCount} selected
          </Typography>
          <Box sx={{ ml: "auto" }}>
            {isExpanded ? <ExpandLess /> : <ExpandMore />}
          </Box>
        </Box>
      </ListItemButton>

      {/* Expanded Content */}
      <Collapse in={isExpanded} timeout="auto" unmountOnExit>
        <Box
          sx={{
            borderTop: "1px solid #e5e7eb",
            p: 2,
          }}
        >
          <ConfluenceFiles
            onSelectionCountChange={handleSelectionCountChange}
            onSelectedFilesChange={handleSelectedFilesChange}
            externalSelectedFiles={externalSelectedFiles}
            onLoadingChange={setIsLoading}
          />
        </Box>
      </Collapse>
      {/* Linear Progress at Bottom Border */}
      {isLoading && (
        <Box
          sx={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: "4px",
            zIndex: 10,
          }}
        >
          <LinearProgress />
        </Box>
      )}
    </Box>
  );
};

export default ConfluenceFolders;
