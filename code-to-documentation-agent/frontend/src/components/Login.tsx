import React, { useState, useEffect } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { useNavigate } from 'react-router-dom';
import { loginRequest } from '../auth/config/auth-config';
import { useAuthContext } from '../auth/context/AuthContext';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  CircularProgress,
  Alert,
  Container,
  Avatar,
  Divider,
} from '@mui/material';
import { Microsoft as MicrosoftIcon } from '@mui/icons-material';

const Login: React.FC = () => {
  const { instance, accounts, inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const { refreshUser } = useAuthContext();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Clear logout flag when Login component mounts
    sessionStorage.removeItem('user_logging_out');
    
    // If user is already authenticated, redirect to the main app
    if (isAuthenticated && accounts.length > 0) {
      navigate('/documentation');
    }
  }, [isAuthenticated, accounts, navigate]);

  useEffect(() => {
    // Handle redirect result after login
    const handleRedirectPromise = async () => {
      try {
        const response = await instance.handleRedirectPromise();
        if (response && response.account) {
          console.log('Login successful:', response.account);
          navigate('/documentation');
        }
      } catch (error) {
        console.error('Error handling redirect:', error);
        setError('Authentication failed. Please try again.');
        setIsLoading(false);
      }
    };

    if (inProgress === 'none') {
      handleRedirectPromise();
    }
  }, [instance, navigate, inProgress]);

  const handleLogin = async () => {
    setIsLoading(true);
    setError(null);
    
    // Clear logout flag when user manually attempts login
    sessionStorage.removeItem('user_logging_out');

    try {
      console.log('Initiating login...');
      
      // Try popup login first, fall back to redirect if it fails
      try {
        const response = await instance.loginPopup(loginRequest);
        if (response && response.account) {
          console.log('Popup login successful:', response.account);
          
          // Refresh the auth context to immediately update user data
          refreshUser();
          
          // Small delay to ensure state propagation
          setTimeout(() => {
            navigate('/documentation');
          }, 100);
        }
      } catch (popupError) {
        console.log('Popup blocked, trying redirect login...');
        await instance.loginRedirect({
          ...loginRequest,
          redirectUri: window.location.origin + '/documentation'
        });
      }
    } catch (error) {
      console.error('Login failed:', error);
      setError(error instanceof Error ? error.message : 'Login failed. Please try again.');
      setIsLoading(false);
    }
  };

  // Show loading if MSAL is still processing
  if (inProgress !== 'none') {
    return (
      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        }}
      >
        <Box sx={{ textAlign: 'center', color: 'white' }}>
          <CircularProgress size={60} sx={{ color: 'white', mb: 2 }} />
          <Typography variant="h6">Signing you in...</Typography>
          <Typography variant="body2" sx={{ mt: 1, opacity: 0.8 }}>
            Status: {inProgress}
          </Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 2,
      }}
    >
      <Container maxWidth="sm">
        <Card
          sx={{
            boxShadow: '0 20px 40px rgba(0, 0, 0, 0.1)',
            borderRadius: 4,
            overflow: 'visible',
            position: 'relative',
          }}
        >
          {/* Header with Logo */}
          <Box
            sx={{
              bgcolor: '#6b46c1',
              color: 'white',
              p: 4,
              textAlign: 'center',
              borderRadius: '16px 16px 0 0',
              position: 'relative',
            }}
          >
            <Avatar
              sx={{
                width: 80,
                height: 80,
                bgcolor: '#8b5cf6',
                fontSize: '32px',
                fontWeight: 'bold',
                margin: '0 auto 16px',
                boxShadow: '0 8px 16px rgba(0, 0, 0, 0.2)',
              }}
            >
              FTA
            </Avatar>
            <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
              Functional Testing Agent
            </Typography>
            <Typography variant="body1" sx={{ opacity: 0.9, maxWidth: '300px', margin: '0 auto' }}>
              Your intelligent test analyst specialist powered by advanced AI capabilities
            </Typography>
          </Box>

          <CardContent sx={{ p: 4 }}>
            {/* Welcome Message */}
            <Box sx={{ textAlign: 'center', mb: 4 }}>
              <Typography variant="h5" sx={{ fontWeight: 600, mb: 2, color: '#1f2937' }}>
                Welcome Back!
              </Typography>
              <Typography variant="body1" sx={{ color: '#6b7280', mb: 3 }}>
                Sign in with your Microsoft account to access your organization's testing workspace
              </Typography>
            </Box>

            {/* Error Message */}
            {error && (
              <Alert 
                severity="error" 
                sx={{ mb: 3, borderRadius: 2 }}
                onClose={() => setError(null)}
              >
                {error}
              </Alert>
            )}

            {/* Login Button */}
            <Button
              fullWidth
              variant="contained"
              size="large"
              onClick={handleLogin}
              disabled={isLoading || inProgress !== 'none'}
              startIcon={
                isLoading || inProgress !== 'none' ? (
                  <CircularProgress size={20} color="inherit" />
                ) : (
                  <MicrosoftIcon />
                )
              }
              sx={{
                py: 1.5,
                fontSize: '16px',
                fontWeight: 600,
                textTransform: 'none',
                borderRadius: 2,
                bgcolor: '#0078d4',
                '&:hover': {
                  bgcolor: '#106ebe',
                },
                '&:disabled': {
                  bgcolor: '#9ca3af',
                },
                boxShadow: '0 4px 12px rgba(0, 120, 212, 0.3)',
              }}
            >
              {isLoading || inProgress !== 'none' ? 'Signing in...' : 'Sign in with Microsoft'}
            </Button>

            {/* Alternative Login Methods */}
            <Box sx={{ mt: 2 }}>
              <Button
                fullWidth
                variant="outlined"
                size="small"
                onClick={() => {
                  console.log('Forcing redirect login...');
                  instance.loginRedirect({
                    ...loginRequest,
                    redirectUri: window.location.origin + '/documentation'
                  });
                }}
                disabled={isLoading || inProgress !== 'none'}
                sx={{
                  py: 1,
                  fontSize: '14px',
                  textTransform: 'none',
                  borderRadius: 2,
                  borderColor: '#e5e7eb',
                  color: '#6b7280',
                  '&:hover': {
                    borderColor: '#d1d5db',
                    bgcolor: '#f9fafb',
                  },
                }}
              >
                Try Redirect Login
              </Button>
            </Box>

            <Divider sx={{ my: 3 }}>
              <Typography variant="caption" sx={{ color: '#9ca3af', px: 2 }}>
                Secure SSO Authentication
              </Typography>
            </Divider>

            {/* Features */}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    bgcolor: '#10b981',
                  }}
                />
                <Typography variant="body2" sx={{ color: '#4b5563' }}>
                  Advanced reasoning capabilities for test analysis
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    bgcolor: '#10b981',
                  }}
                />
                <Typography variant="body2" sx={{ color: '#4b5563' }}>
                  Access to your organization's knowledge base
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    bgcolor: '#10b981',
                  }}
                />
                <Typography variant="body2" sx={{ color: '#4b5563' }}>
                  Secure enterprise-grade authentication
                </Typography>
              </Box>
            </Box>
          </CardContent>

          {/* Footer */}
          <Box
            sx={{
              bgcolor: '#f8fafc',
              p: 3,
              textAlign: 'center',
              borderRadius: '0 0 16px 16px',
            }}
          >
            <Typography variant="caption" sx={{ color: '#9ca3af' }}>
              By signing in, you agree to our terms of service and privacy policy
            </Typography>
          </Box>
        </Card>
      </Container>
    </Box>
  );
};

export default Login;