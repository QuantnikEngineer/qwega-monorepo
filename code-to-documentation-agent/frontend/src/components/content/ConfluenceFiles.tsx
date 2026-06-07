import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  CircularProgress,
  Tooltip,
  TextField,
  InputAdornment,
  Pagination,
} from "@mui/material";
import DescriptionIcon from "@mui/icons-material/Description";
import RefreshIcon from "@mui/icons-material/Refresh";
import RadioButtonUnchecked from "@mui/icons-material/RadioButtonUnchecked";
import CheckCircle from "@mui/icons-material/CheckCircle";
import SearchIcon from "@mui/icons-material/Search";
import ClearIcon from "@mui/icons-material/Clear";
import FolderIcon from "@mui/icons-material/Folder";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";

import API_CONFIG, { getItemsPerPage } from "../../config/agentConfig";

interface ConfluencePage {
  id: string;
  title: string;
  spaceKey: string;
  spaceName: string;
  createdDate: string;
  lastModifiedDate: string;
  webUrl: string;
  contentUrl: string;
  parentTitle?: string;
  parentId?: string;
  depth?: number;
}

interface PageTreeNode {
  page: ConfluencePage;
  children: PageTreeNode[];
}

// Flattened item for display with tree info
interface FlattenedItem {
  page: ConfluencePage;
  depth: number;
  hasChildren: boolean;
  childCount: number;
}

export interface SelectedConfluenceFile {
  pageId: string;
  pageTitle: string;
  extractedContent: string;
  spaceKey: string;
  spaceName: string;
  lastModifiedDate: string;
  webUrl: string;
}

interface ConfluenceFilesProps {
  onSelectionCountChange?: (count: number) => void;
  onSelectedFilesChange?: (files: SelectedConfluenceFile[]) => void;
  externalSelectedFiles?: SelectedConfluenceFile[]; // For syncing with parent state
  onLoadingChange?: (loading: boolean) => void; // To pass loading state to parent
}

const ConfluenceFiles: React.FC<ConfluenceFilesProps> = ({
  onSelectionCountChange,
  onSelectedFilesChange,
  externalSelectedFiles,
  onLoadingChange,
}) => {
  const [pages, setPages] = useState<ConfluencePage[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [selectedPages, setSelectedPages] = useState<Set<string>>(new Set());
  const [selectedPagesArray, setSelectedPagesArray] = useState<
    SelectedConfluenceFile[]
  >([]);
  const [extractingPages, setExtractingPages] = useState<Set<string>>(
    new Set()
  );
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Get items per page from runtime config
  const ITEMS_PER_PAGE = useMemo(() => getItemsPerPage(), []);

  // Build tree structure from flat pages list
  const buildPageTree = (pages: ConfluencePage[]): PageTreeNode[] => {
    const pageMap = new Map<string, PageTreeNode>();
    const rootNodes: PageTreeNode[] = [];

    // First pass: create nodes for all pages
    pages.forEach(page => {
      pageMap.set(page.id, { page, children: [] });
    });

    // Second pass: build the tree structure
    pages.forEach(page => {
      const node = pageMap.get(page.id)!;
      if (page.parentId && pageMap.has(page.parentId)) {
        pageMap.get(page.parentId)!.children.push(node);
      } else {
        rootNodes.push(node);
      }
    });

    // Sort children by title
    const sortChildren = (nodes: PageTreeNode[]) => {
      nodes.sort((a, b) => a.page.title.localeCompare(b.page.title));
      nodes.forEach(node => sortChildren(node.children));
    };
    sortChildren(rootNodes);

    return rootNodes;
  };

  // Flatten tree into list based on expanded state (for combined pagination)
  const flattenTree = (
    nodes: PageTreeNode[], 
    expanded: Set<string>, 
    depth: number = 0
  ): FlattenedItem[] => {
    const result: FlattenedItem[] = [];
    nodes.forEach(node => {
      result.push({
        page: node.page,
        depth,
        hasChildren: node.children.length > 0,
        childCount: node.children.length,
      });
      // Only include children if parent is expanded
      if (node.children.length > 0 && expanded.has(node.page.id)) {
        result.push(...flattenTree(node.children, expanded, depth + 1));
      }
    });
    return result;
  };

  // Build tree structure
  const pageTree = useMemo(() => buildPageTree(pages), [pages]);

  // Flatten tree for pagination (includes only visible items based on expanded state)
  const flattenedItems = useMemo(() => 
    flattenTree(pageTree, expandedFolders), 
    [pageTree, expandedFolders]
  );

  // Filter flattened items based on search query
  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) {
      return flattenedItems;
    }
    const lowerQuery = searchQuery.toLowerCase();
    return flattenedItems.filter(
      (item) =>
        item.page.title.toLowerCase().includes(lowerQuery) ||
        item.page.spaceName.toLowerCase().includes(lowerQuery) ||
        item.page.spaceKey.toLowerCase().includes(lowerQuery)
    );
  }, [flattenedItems, searchQuery]);

  // Pagination helper functions
  const getPaginatedItems = <T,>(items: T[], page: number): T[] => {
    const startIndex = (page - 1) * ITEMS_PER_PAGE;
    const endIndex = startIndex + ITEMS_PER_PAGE;
    return items.slice(startIndex, endIndex);
  };

  const getTotalPages = (itemCount: number): number => {
    return Math.ceil(itemCount / ITEMS_PER_PAGE);
  };

  // Toggle folder expansion
  const toggleFolder = (pageId: string) => {
    setExpandedFolders(prev => {
      const newSet = new Set(prev);
      if (newSet.has(pageId)) {
        newSet.delete(pageId);
      } else {
        newSet.add(pageId);
      }
      return newSet;
    });
    // Reset to page 1 when expanding/collapsing to avoid showing empty page
    setCurrentPage(1);
  };

  // Sync internal state with external selected files (when files are removed via X icon)
  useEffect(() => {
    if (externalSelectedFiles !== undefined) {
      const externalPageIds = new Set(
        externalSelectedFiles.map((file) => file.pageId)
      );

      const currentPageIds = new Set(selectedPages);

      const pageIdsChanged =
        externalPageIds.size !== currentPageIds.size ||
        !Array.from(externalPageIds).every((id) => currentPageIds.has(id)) ||
        !Array.from(currentPageIds).every((id) => externalPageIds.has(id));

      if (pageIdsChanged) {
        setSelectedPages(externalPageIds);
        setSelectedPagesArray(externalSelectedFiles);

        if (onSelectionCountChange) {
          onSelectionCountChange(externalPageIds.size);
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalSelectedFiles]);

  const baseUrl =
    window.location.origin + window.location.pathname.replace(/\/$/, "");

  const constructApiUrl = (endpoint: string) => {
    if (baseUrl.includes("localhost")) {
      return `${API_CONFIG.DOMAIN}:${API_CONFIG.PORT}${endpoint}`;
    } else {
      return `${baseUrl}${endpoint}`;
    }
  };

  const didFetch = useRef(false);
  useEffect(() => {
    if (didFetch.current) return;
    didFetch.current = true;
    fetchConfluencePages();
  }, []);

  const fetchConfluencePages = async () => {
    try {
      setLoading(true);
      if (onLoadingChange) {
        onLoadingChange(true);
      }
      setError("");
      
      // Reset pagination when fetching
      setCurrentPage(1);

      // Fetch pages - backend will use CONFLUENCE_SPACE_KEY from env
      const response = await fetch(
        constructApiUrl(`${API_CONFIG.ENDPOINTS.LIST_CONFLUENCE_PAGES}`),
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.success && data.pages) {
        setPages(data.pages);
      } else {
        setError(data.error || "Failed to fetch Confluence pages");
        setPages([]);
      }
    } catch (err: any) {
      console.error("Error fetching Confluence pages:", err);
      setError(err.message || "Failed to fetch Confluence pages");
      setPages([]);
    } finally {
      setLoading(false);
      if (onLoadingChange) {
        onLoadingChange(false);
      }
    }
  };

  const extractPageContent = async (
    pageId: string,
    pageTitle: string
  ): Promise<string> => {
    try {
      const response = await fetch(
        constructApiUrl(
          `${API_CONFIG.ENDPOINTS.CONTENT_FROM_CONFLUENCE_PAGE}/${pageId}`
        ),
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.success && data.content) {
        return data.content;
      } else {
        throw new Error(data.error || "Failed to extract page content");
      }
    } catch (error) {
      console.error("Error extracting Confluence page content:", error);
      throw error;
    }
  };

  const handlePageSelection = async (pageId: string, isSelected: boolean) => {
    const newSelectedPages = new Set(selectedPages);
    let newSelectedPagesArray = [...selectedPagesArray];

    if (isSelected) {
      newSelectedPages.add(pageId);

      const selectedPage = pages.find((page) => page.id === pageId);
      if (selectedPage) {
        setExtractingPages((prev) => {
          const newSet = new Set(prev);
          newSet.add(pageId);
          return newSet;
        });

        try {
          console.log(
            `Extracting content for Confluence page: ${selectedPage.title} (ID: ${selectedPage.id})`
          );
          const extractedContent = await extractPageContent(
            selectedPage.id,
            selectedPage.title
          );

          console.log(
            `Content extracted successfully for ${selectedPage.title}. Length: ${extractedContent.length} characters`
          );
          console.log(
            `Content preview: ${extractedContent.substring(0, 200)}...`
          );

          const newSelectedPageObj: SelectedConfluenceFile = {
            pageId: selectedPage.id,
            pageTitle: selectedPage.title,
            extractedContent: extractedContent,
            spaceKey: selectedPage.spaceKey,
            spaceName: selectedPage.spaceName,
            lastModifiedDate: selectedPage.lastModifiedDate,
            webUrl: selectedPage.webUrl,
          };

          newSelectedPagesArray.push(newSelectedPageObj);
          console.log(
            `Confluence page added to selection. Total selected: ${newSelectedPagesArray.length}`
          );
        } catch (error) {
          console.error("Error extracting page content:", error);
          newSelectedPages.delete(pageId);
        } finally {
          setExtractingPages((prev) => {
            const newSet = new Set(prev);
            newSet.delete(pageId);
            return newSet;
          });
        }
      }
    } else {
      newSelectedPages.delete(pageId);
      newSelectedPagesArray = newSelectedPagesArray.filter(
        (file) => file.pageId !== pageId
      );
    }

    setSelectedPages(newSelectedPages);
    setSelectedPagesArray(newSelectedPagesArray);

    if (onSelectionCountChange) {
      onSelectionCountChange(newSelectedPages.size);
    }

    if (onSelectedFilesChange) {
      onSelectedFilesChange(newSelectedPagesArray);
    }
  };

  const formatDate = (dateString: string): string => {
    if (!dateString) return "Unknown";
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return dateString;
    }
  };

  return (
    <Box>
      {/* Header with refresh button */}
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 2,
        }}
      >
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          Confluence Pages
        </Typography>
        <Tooltip title="Refresh">
          <IconButton size="small" onClick={fetchConfluencePages}>
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Search Bar */}
      <Box sx={{ mb: 2 }}>
        <TextField
          fullWidth
          size="small"
          placeholder="Search Confluence pages..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ color: "#9ca3af", fontSize: "20px" }} />
              </InputAdornment>
            ),
            endAdornment: searchQuery && (
              <InputAdornment position="end">
                <IconButton
                  size="small"
                  onClick={() => setSearchQuery("")}
                  edge="end"
                  aria-label="clear search"
                >
                  <ClearIcon sx={{ fontSize: "18px" }} />
                </IconButton>
              </InputAdornment>
            ),
          }}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: "8px",
              backgroundColor: "#f9fafb",
              "&:hover": {
                backgroundColor: "#f3f4f6",
              },
              "&.Mui-focused": {
                backgroundColor: "#ffffff",
              },
            },
          }}
        />
        {searchQuery && (
          <Typography
            variant="caption"
            sx={{ mt: 0.5, display: "block", color: "#6b7280" }}
          >
            Found {filteredItems.length} of {pages.length} pages
          </Typography>
        )}
      </Box>

      {loading && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 2 }}>
          <CircularProgress size={24} />
        </Box>
      )}

      {error && (
        <Typography
          variant="caption"
          color={error.toLowerCase().includes("not configured") ? "info" : "error"}
          sx={{ mb: 1, display: "block" }}
        >
          {error}
        </Typography>
      )}

      <List sx={{ maxHeight: "400px", overflowY: "auto" }}>
        {!loading && filteredItems.length === 0 ? (
          <ListItem>
            <ListItemText
              primary={searchQuery ? "No matching pages found" : "No Confluence pages found"}
              secondary={searchQuery ? "Try a different search term." : "Pages will appear here once available."}
            />
          </ListItem>
        ) : (
          // Tree view with combined pagination (parent + child items count together)
          <>
            {getPaginatedItems<FlattenedItem>(filteredItems, currentPage).map((item) => {
              const { page, depth, hasChildren, childCount } = item;
              const isExpanded = expandedFolders.has(page.id);
              const isSelected = selectedPages.has(page.id);
              const isExtracting = extractingPages.has(page.id);

              return (
                <ListItem
                  key={page.id}
                  sx={{
                    border: "1px solid #e0e0e0",
                    borderRadius: "8px",
                    mb: 0.5,
                    ml: depth * 2, // Indent based on depth
                    backgroundColor: isSelected ? "#daffda" : "transparent",
                    "&:hover": {
                      backgroundColor: isSelected ? "#c8f5c8" : "#f5f5f5",
                    },
                    cursor: "pointer",
                    py: 0.5,
                  }}
                >
                  {/* Expand/Collapse button for folders */}
                  <ListItemIcon sx={{ minWidth: 28 }}>
                    {hasChildren ? (
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleFolder(page.id);
                        }}
                        sx={{ p: 0.25 }}
                      >
                        {isExpanded ? (
                          <ExpandMoreIcon sx={{ fontSize: "20px", color: "#6b7280" }} />
                        ) : (
                          <ChevronRightIcon sx={{ fontSize: "20px", color: "#6b7280" }} />
                        )}
                      </IconButton>
                    ) : (
                      <Box sx={{ width: 20 }} />
                    )}
                  </ListItemIcon>

                  {/* Selection checkbox */}
                  <ListItemIcon 
                    sx={{ minWidth: 32, cursor: "pointer" }}
                    onClick={() => handlePageSelection(page.id, !isSelected)}
                  >
                    {isExtracting ? (
                      <CircularProgress size={18} />
                    ) : isSelected ? (
                      <CheckCircle sx={{ color: "#4caf50", fontSize: "22px" }} />
                    ) : (
                      <RadioButtonUnchecked sx={{ color: "#6b7280", fontSize: "22px" }} />
                    )}
                  </ListItemIcon>

                  {/* Folder or Document icon */}
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    {hasChildren ? (
                      isExpanded ? (
                        <FolderOpenIcon sx={{ color: "#f59e0b", fontSize: "20px" }} />
                      ) : (
                        <FolderIcon sx={{ color: "#f59e0b", fontSize: "20px" }} />
                      )
                    ) : (
                      <DescriptionIcon sx={{ color: "#1976d2", fontSize: "20px" }} />
                    )}
                  </ListItemIcon>

                  {/* Page title and info */}
                  <ListItemText
                    onClick={() => handlePageSelection(page.id, !isSelected)}
                    primary={
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: isSelected || hasChildren ? 600 : 400,
                          wordWrap: "break-word",
                          fontSize: "13px",
                        }}
                      >
                        {page.title}
                        {hasChildren && (
                          <Typography
                            component="span"
                            variant="caption"
                            sx={{ ml: 1, color: "#6b7280" }}
                          >
                            ({childCount})
                          </Typography>
                        )}
                      </Typography>
                    }
                    secondary={
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: "11px" }}>
                        {formatDate(page.lastModifiedDate)}
                      </Typography>
                    }
                  />
                </ListItem>
              );
            })}
            {/* Combined pagination for all visible items (parent + expanded children) */}
            {getTotalPages(filteredItems.length) > 1 && (
              <Box sx={{ display: "flex", justifyContent: "center", mt: 2, mb: 1 }}>
                <Pagination
                  count={getTotalPages(filteredItems.length)}
                  page={currentPage}
                  onChange={(_, newPage) => setCurrentPage(newPage)}
                  size="small"
                  color="primary"
                />
              </Box>
            )}
          </>
        )}
      </List>
    </Box>
  );
};

export default ConfluenceFiles;
