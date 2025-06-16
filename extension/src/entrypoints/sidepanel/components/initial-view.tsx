import React from 'react';
import { useAuth } from '../context/auth-provider';

export const InitialView: React.FC = () => {
  const { signIn } = useAuth();
  
  const [isAuthenticated, setIsAuthenticated] = React.useState(false);
  const [userName, setUserName] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [signingIn, setSigningIn] = React.useState(false);

  // Extract name from email (e.g., "norika@gmail.com" -> "norika")
  const extractNameFromEmail = (email: string): string => {
    return email.split('@')[0];
  };

  // Check authentication status on component mount
  React.useEffect(() => {
    const checkAuthStatus = async () => {
      try {
        // Get the session token from Chrome storage
        const result = await chrome.storage.local.get(['supabase.auth.token']);
        const authData = result['supabase.auth.token'];
        
        if (authData && authData.access_token) {
          // User is authenticated, try to get user info
          setIsAuthenticated(true);
          
          // Extract user info from token payload (JWT decode)
          try {
            const tokenPayload = JSON.parse(atob(authData.access_token.split('.')[1]));
            const email = tokenPayload.email;
            
            if (email) {
              const name = extractNameFromEmail(email);
              setUserName(name);
            }
          } catch (jwtError) {
            console.error('Failed to decode JWT token:', jwtError);
            // Still authenticated, but couldn't get name
            setUserName('User');
          }
        } else {
          // User is not authenticated
          setIsAuthenticated(false);
          setUserName(null);
        }
      } catch (error) {
        console.error('Failed to check auth status:', error);
        setIsAuthenticated(false);
        setUserName(null);
      } finally {
        setLoading(false);
      }
    };

    checkAuthStatus();
  }, []);

  const handleSignIn = async () => {
    try {
      setSigningIn(true);
      await signIn();
      // signIn will handle success state via auth context
    } catch (error) {
      console.error('Sign in failed:', error);
      // Error is already handled in the auth provider
    } finally {
      setSigningIn(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-full">
      <h1 className="mb-4 text-xl">⏺️ Rebrowse Recorder</h1>
      
      {signingIn ? (
        // Signing in - show loading state
        <div className="text-center">
          <div className="mb-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-black mx-auto"></div>
          </div>
          <div className="text-sm text-gray-600 mb-2">
            Preparing Google Sign-in...
          </div>
        </div>
      ) : isAuthenticated && userName ? (
        // Authenticated user - show welcome message
        <div className="text-center">
          <div className="mb-4 text-lg text-green-600">
            Welcome back, {userName}! 👋
          </div>
          <div className="text-sm text-gray-600">
            You're ready to start recording workflows
          </div>
        </div>
      ) : (
        // Not authenticated - show sign in button
        <button
          className="bg-black text-white px-4 py-2 rounded hover:bg-gray-800 transition-colors"
          onClick={handleSignIn}
          disabled={signingIn}
        >
          Sign in with Google
        </button>
      )}
    </div>
  );
};
