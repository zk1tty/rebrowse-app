import React from 'react';
import { useAuth } from '../context/auth-provider';
import { useWorkflow } from '../context/workflow-provider';
import { Button } from '@/components/ui/button';
import { authClient } from '@/lib/auth';

export const InitialView: React.FC = () => {
  const { signIn, isAuthenticated } = useAuth();
  const { startRecording } = useWorkflow();
  
  const [userName, setUserName] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [signingIn, setSigningIn] = React.useState(false);

  // Extract name from email (e.g., "norika@gmail.com" -> "norika")
  const extractNameFromEmail = (email: string): string => {
    return email.split('@')[0];
  };

  // Get user name when authenticated
  React.useEffect(() => {
    const getUserName = async () => {
      if (isAuthenticated) {
        try {
          console.log('[initial-view] User is authenticated, getting user info...');
          
          // First, try to get session directly from authClient
          const { data: { session }, error } = await authClient.getSession();
          console.log('[initial-view] AuthClient session:', { hasSession: !!session, error });
          
          if (session?.access_token) {
            try {
              const tokenPayload = JSON.parse(atob(session.access_token.split('.')[1]));
              const email = tokenPayload.email;
              
              if (email) {
                const name = extractNameFromEmail(email);
                console.log('[initial-view] Extracted name from session:', name);
                setUserName(name);
                setLoading(false);
                return;
              }
            } catch (jwtError) {
              console.error('[initial-view] Failed to decode JWT from session:', jwtError);
            }
          }
          
          // Fallback: Check chrome storage with multiple possible keys
          const possibleKeys = [
            'supabase.auth.token',
            'sb-dmgtsseqqsiyuuzhdxnn-auth-token',
            'supabase.session',
            'sb-auth-token'
          ];
          
          for (const key of possibleKeys) {
            try {
              const result = await chrome.storage.local.get([key]);
              const authData = result[key];
              console.log(`[initial-view] Checking storage key ${key}:`, { hasData: !!authData });
              
              if (authData) {
                let accessToken = '';
                
                // Handle different storage formats
                if (typeof authData === 'string') {
                  try {
                    const parsed = JSON.parse(authData);
                    accessToken = parsed.access_token || '';
                  } catch {
                    accessToken = authData;
                  }
                } else if (authData.access_token) {
                  accessToken = authData.access_token;
                }
                
                if (accessToken) {
                  try {
                    const tokenPayload = JSON.parse(atob(accessToken.split('.')[1]));
                    const email = tokenPayload.email;
                    
                    if (email) {
                      const name = extractNameFromEmail(email);
                      console.log('[initial-view] Extracted name from storage:', name);
                      setUserName(name);
                      setLoading(false);
                      return;
                    }
                  } catch (jwtError) {
                    console.error(`[initial-view] Failed to decode JWT from ${key}:`, jwtError);
                  }
                }
              }
            } catch (storageError) {
              console.error(`[initial-view] Failed to read ${key} from storage:`, storageError);
            }
          }
          
          // If we get here, we're authenticated but couldn't get user info
          console.warn('[initial-view] Authenticated but could not extract user info');
          setUserName('User');
        } catch (error) {
          console.error('[initial-view] Failed to get user info:', error);
          setUserName('User');
        }
      } else {
        console.log('[initial-view] User not authenticated');
        setUserName(null);
      }
      setLoading(false);
    };

    if (isAuthenticated !== null) {
      getUserName();
    }
  }, [isAuthenticated]);

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

  // Show loading while AuthProvider is still checking authentication
  if (isAuthenticated === null || loading) {
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
        // Authenticated user - show welcome message and start recording button
        <div className="text-center space-y-4">
          <div className="text-lg text-black-600">
            Welcome back, {userName}! 👋
          </div>
          <Button 
            onClick={startRecording}
            className="bg-red-500 hover:bg-red-800 text-white px-6 py-2 rounded-lg font-medium"
            size="lg"
          >
            <span className="flex items-center gap-2">
              <span className="w-3 h-3 bg-white rounded-full"></span>
              Start Recording
            </span>
          </Button>
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
