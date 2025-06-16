import React, { createContext, useContext, useEffect, useState } from 'react';
import { 
    ensureAuth, 
    signOut as supabaseSignOut,
    authClient
} from '@/lib/auth';
import type { AuthChangeEvent, Session } from '@supabase/auth-js';

type AuthCtx = {
  isAuthenticated: boolean | null;   // null = still checking
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthCtx | undefined>(undefined);

export const AuthProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [isAuthenticated, setAuth] = useState<boolean | null>(null);

  /* ── watch Supabase session and restore on mount ──────────────────── */
  useEffect(() => {
    let mounted = true;
    let retryCount = 0;
    const maxRetries = 3;

    // Initial session check and restore with retry logic
    const initializeAuth = async () => {
      try {
        console.info("[auth-provider] checking session...");
        const { data: { session } } = await authClient.getSession();
        console.info("[auth-provider] initial session check:", { 
          hasSession: !!session, 
          hasAccessToken: !!session?.access_token,
          retryCount 
        });
        
        if (mounted) {
          setAuth(!!session);
        }
        
        // If no session found and we haven't exhausted retries, try again after a short delay
        // This helps with cases where the OAuth redirect just happened
        if (!session && retryCount < maxRetries) {
          retryCount++;
          console.info(`[auth-provider] no session found, retrying in 1s (attempt ${retryCount}/${maxRetries})`);
          setTimeout(() => {
            if (mounted) {
              initializeAuth();
            }
          }, 1000);
        }
      } catch (err) {
        console.error("[auth-provider] failed to get initial session:", err);
        if (mounted) {
          // Retry on error too, but with exponential backoff
          if (retryCount < maxRetries) {
            retryCount++;
            console.info(`[auth-provider] retrying after error in ${retryCount * 1000}ms`);
            setTimeout(() => {
              if (mounted) {
                initializeAuth();
              }
            }, retryCount * 1000);
          } else {
            setAuth(false);
          }
        }
      }
    };

    // Start initialization
    initializeAuth();

    // Listen for auth state changes
    const { data: sub } = authClient.onAuthStateChange((_event: AuthChangeEvent, session: Session | null) => {
      console.info("[auth-provider] auth state changed:", { event: _event, hasSession: !!session });
      if (mounted) {
        setAuth(!!session);
        // Reset retry count when we get a valid state change
        retryCount = 0;
      }
    });

    // Listen for explicit success message from background script after OAuth
    const handler = (msg: any) => {
      if (msg.type === 'AUTH_SUCCESS') {
        console.info("[auth-provider] received AUTH_SUCCESS message, rechecking session...");
        // Force a session recheck when we get the success message
        setTimeout(() => {
          if (mounted) {
            authClient.getSession().then(({ data: { session } }) => {
              console.info("[auth-provider] session recheck after AUTH_SUCCESS:", { hasSession: !!session });
              setAuth(!!session);
            }).catch(err => {
              console.error("[auth-provider] failed to recheck session after AUTH_SUCCESS:", err);
            });
          }
        }, 500); // Small delay to ensure session is stored
      }
    };
    chrome.runtime.onMessage.addListener(handler);

    return () => {
      mounted = false;
      chrome.runtime.onMessage.removeListener(handler);
      if (sub?.subscription) {
        sub.subscription.unsubscribe();
      }
    };
  }, []);

  /* ── public api ───────────────────────────────────────────────────── */
  const signIn = async () => {
    try {
      const token = await ensureAuth();
      console.info("[auth-provider] sign in successful, token received");
      
      // Update React state immediately for better UX
      // The session should already be set by ensureAuth(), but we update state for immediate feedback
      setAuth(true);
    } catch (err) {
      console.error("Sign in failed:", err);
      chrome.notifications.create({
        type: 'basic',
        iconUrl: chrome.runtime.getURL('icon/48.png'),
        title: 'Sign-in failed',
        message: String(err)
      });
    }
  };

  const signOut = async () => {
    try {
      await supabaseSignOut();
      console.info("[auth-provider] sign out successful");
      setAuth(false); // Update state immediately for better UX
    } catch (err) {
      console.error("[auth-provider] sign out failed:", err);
      // Still update state to false even if signOut failed
      setAuth(false);
    }
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}; 