import React, { ReactNode } from 'react';
import { 
  Box, 
  CircularProgress, 
  Typography, 
  Alert, 
  Button, 
  Card, 
  CardContent, 
  Container 
} from '@mui/material';
import { useJWTAuth } from '../contexts/JWTAuthContext';

interface JWTAuthGuardProps {
  children: ReactNode;
}

/**
 * JWT Authentication Guard Component
 * 
 * This component wraps protected content and handles authentication states
 */
export const JWTAuthGuard: React.FC<JWTAuthGuardProps> = ({ 
  children
}) => {
  const { 
    isLoading, 
    isAuthenticated, 
    authData
  } = useJWTAuth();

  // Loading state
  if (isLoading) {
    return (
      <Box 
        display="flex" 
        flexDirection="column" 
        alignItems="center" 
        justifyContent="center" 
        minHeight="100vh"
        gap={2}
      >
        <CircularProgress size={48} />
        <Typography variant="h6" color="textSecondary">
          Authenticating...
        </Typography>
      </Box>
    );
  }

  // Unauthenticated state
  if (!isAuthenticated || !authData) {
    return (
      <Container maxWidth="sm">
        <Box 
          display="flex" 
          flexDirection="column" 
          alignItems="center" 
          justifyContent="center" 
          minHeight="100vh"
          gap={3}
        >
          <Card sx={{ width: '100%', maxWidth: 500 }}>
            <CardContent>
              <Box textAlign="center">
                <Typography variant="h4" gutterBottom sx={{ color: '#1976d2' }}>
                  🔐 Authentication Required
                </Typography>
                <Alert severity="info" sx={{ mb: 3 }}>
                  <Typography variant="body1" gutterBottom>
                    Please access this agent through the main application.
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    This application requires proper authentication from main application.
                  </Typography>
                </Alert>
                
                <Button 
                  variant="contained" 
                  onClick={() => window.location.reload()}
                  color="primary"
                  size="large"
                >
                  Reload Page
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Container>
    );
  }

  // Authenticated state - render children
  return <>{children}</>;
};
