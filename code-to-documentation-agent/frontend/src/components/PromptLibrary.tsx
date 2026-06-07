import React, { useEffect, useRef, useState } from 'react';
import { 
  Card, 
  Typography,
  Box,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Collapse,
  CircularProgress
} from '@mui/material';
import { ExpandLess, ExpandMore, Lightbulb, LightbulbOutline } from '@mui/icons-material';

import API_CONFIG from '../config/agentConfig';
interface PromptLibraryProps {
  onFaqClick: (text: string) => void;
  isExpanded?: boolean;
  onToggle?: () => void;
  agentId?: string; // Optional agent ID, defaults to a default value
}

const PromptLibrary: React.FC<PromptLibraryProps> = ({ 
  onFaqClick, 
  isExpanded: externalIsExpanded, 
  onToggle,
  agentId = "69032a3be3e0024200236722" // Default agent ID from the example response
}) => {
  const [internalIsExpanded, setInternalIsExpanded] = useState(true);
  const [faqs, setFaqs] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Use external state if provided, otherwise use internal state
  const isExpanded = externalIsExpanded !== undefined ? externalIsExpanded : internalIsExpanded;
  const handleToggle = onToggle || (() => setInternalIsExpanded(!internalIsExpanded));

  // Helper function to construct API URLs
  const constructApiUrl = (endpoint: string): string => {
    const baseUrl = window.location.origin + window.location.pathname.replace(/\/$/, "");
    if (baseUrl.includes("localhost")) {
      return `${API_CONFIG.DOMAIN}:${API_CONFIG.PORT}${endpoint}`;
    } else {
      return `${baseUrl}${endpoint}`;
    }
  };


const fetchAgentPrompts = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        constructApiUrl(API_CONFIG.ENDPOINTS.GET_AGENT_PROMPTS),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            agent_id: agentId,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch prompts: ${response.status}`);
      }

      const data = await response.json();
      console.log("prompt data", data)
      if (data.status === "success" && data.data?.prompts) {
        setFaqs(data.data.prompts);
      } else {
        // Fallback to default FAQs if API doesn't return expected format
        setFaqs([
         "Generate documentation",
         "What are the main components and architecture of this repository?",
         "How do I set up and run this project locally? What are the prerequisites?",
         "What testing frameworks and deployment strategies does this project use?",
         "What are the key dependencies and third-party libraries used in this project?",
         "How is the project structured? Can you explain the folder organization and file purposes?"
       ]);
      }
    } catch (err) {
      console.error("Error fetching agent prompts:", err);
      setError(err instanceof Error ? err.message : "Failed to load prompts");
      // Fallback to default FAQs on error
     setFaqs([
         "Generate documentation",
         "What are the main components and architecture of this repository?",
         "How do I set up and run this project locally? What are the prerequisites?",
         "What testing frameworks and deployment strategies does this project use?",
         "What are the key dependencies and third-party libraries used in this project?",
        "How is the project structured? Can you explain the folder organization and file purposes?"
      ]);
    } finally {
      setLoading(false);
    }
  };
  
  // Ensure fetch runs only once on initial mount (even under StrictMode)
  const didFetch = useRef(false);
  useEffect(() => {
    if (didFetch.current) return;
    didFetch.current = true;
    fetchAgentPrompts();
  }, []);
  
 return (
    <Box
      sx={{
        width: '100%',
        backgroundColor: '#ffffff',
        borderRadius: '12px',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.18)',
        margin: 0,
        alignSelf: 'flex-start',
        zIndex: 5,
        transition: 'max-height 0.3s ease',
        maxHeight: isExpanded ? '500px' : '48px',
      }}
    >
        {/* Prompt Library Header */}
        <ListItemButton
          onClick={handleToggle}
          sx={{
            p: 2,
            '&:hover': {
              backgroundColor: '#f9fafb',
            },
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, width: '100%' }}>
            <LightbulbOutline sx={{ color: '#6b7280' }} />
            <Typography variant="body1" sx={{ fontWeight: 600, color: '#000000' }}>
              Prompt Library
            </Typography>
            <Typography
              variant="body2"
              sx={{
                backgroundColor: '#f3f4f6',
                color: '#000000',
                px: 1.5,
                py: 0.25,
                borderRadius: '12px',
                fontSize: '12px',
                fontWeight: 600,
              }}
            >
              {faqs.length} prompts
            </Typography>
            <Box sx={{ ml: 'auto' }}>
              {isExpanded ? <ExpandLess /> : <ExpandMore />}
            </Box>
          </Box>
        </ListItemButton>

        {/* Expanded Content */}
        <Collapse in={isExpanded} timeout="auto" unmountOnExit>
          <Box
            sx={{
              borderTop: '1px solid #e5e7eb',
              p: 3,
            }}
          >
            {/* Quick Actions from existing FAQs */}
            <Box sx={{ maxHeight: '300px', display: 'flex', flexDirection: 'column', overflowY: 'auto', }}>
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 600,
                  color: '#000000',
                  mb: 2,
                  fontSize: '14px',
                }}
              >
                Quick Actions
              </Typography>
              
              {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                  <CircularProgress size={24} />
                </Box>
              ) : error ? (
                <Box sx={{ py: 2 }}>
                  <Typography variant="body2" sx={{ color: '#dc2626', fontSize: '14px' }}>
                    {error}
                  </Typography>
                </Box>
              ) : faqs.length === 0 ? (
                <Box sx={{ py: 2 }}>
                  <Typography variant="body2" sx={{ color: '#6b7280', fontSize: '14px' }}>
                    No prompts available
                  </Typography>
                </Box>
              ) : (
                <List 
                  sx={{ 
                    p: 0, 
                    m: 0,
                    maxHeight: '600px',
                    overflowY: 'scroll',
                    paddingRight: '4px',
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
                  {faqs.map((faq, index) => (
                  <ListItem key={index} sx={{ p: 0, mb: 1.5, width: '100%' }}>
                    <ListItemButton
                      onClick={() => onFaqClick(faq)}
                      sx={{
                        border: '1px solid #e5e7eb',
                        borderRadius: '8px',
                        padding: '6px 16px',
                        backgroundColor: '#f8fafc',
                        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
                        width: '100%',
                        '&:hover': {
                          backgroundColor: '#e6f0fa',
                          borderColor: '#3b82f6',
                          boxShadow: '0 4px 12px rgba(59, 130, 246, 0.15)',
                          transform: 'translateY(-1px)',
                        },
                        transition: 'all 0.2s ease',
                        
                      }}
                    >
                      <ListItemText
                        primary={faq}
                        primaryTypographyProps={{
                          fontSize: '13px',
                          color: '#000000',
                          lineHeight: 1.4,
                          fontWeight: 500,
                        }}
                      />
                    </ListItemButton>
                  </ListItem>
                ))}
              </List>
              )}
            </Box>
          </Box>
        </Collapse>
    </Box>
  );
};

export default PromptLibrary;