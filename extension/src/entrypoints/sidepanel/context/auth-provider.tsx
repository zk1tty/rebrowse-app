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

    // Initial session check and restore
    const initializeAuth = async () => {
      try {
        const { data: { session } } = await authClient.getSession();
        console.info("[auth-provider] initial session check:", { hasSession: !!session });
        
        if (mounted) {
          setAuth(!!session);
        }
      } catch (err) {
        console.error("[auth-provider] failed to get initial session:", err);
        if (mounted) {
          setAuth(false);
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
      }
    });

    // Listen for explicit success message from background script after OAuth
    const handler = (msg: any) => {
      if (msg.type === 'AUTH_SUCCESS') {
        console.info("[auth-provider] received AUTH_SUCCESS message");
        setAuth(true);
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