/**
 * auth.ts – Supabase auth helper for Chrome extension
 * --------------------------------------------------
 * This is the **single** source‑of‑truth auth helper used by background, popup &
 * side‑panel.  It adds a pile of `console.info` statements so you can see the
 * state‑machine step‑by‑step inside DevTools (☰ ▸ Extensions ▸ "service‑worker"
 * or the side‑panel frame).
 * --------------------------------------------------
 */

import { AuthClient } from "@supabase/auth-js";
import { createChromeStorageAdapter } from "./chrome-storage-adapter";
import { debugStorageContents, debugSupabaseSession } from "./storage-debug";

// ────────────────────────────────────────────────────────────────────────────────
// Single source‑of‑truth auth helper used by background, popup & side‑panel.
// Adds *very* chatty console output so you can follow every branch.                
// ────────────────────────────────────────────────────────────────────────────────

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || "https://dmgtsseqqsiyuuzhdxnn.supabase.co";
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || 
  "REMOVED.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRtZ3Rzc2VxcXNpeXV1emhkeG5uIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk3MzE4ODIsImV4cCI6MjA2NTMwNzg4Mn0.e5bQXtdRsPY31fEp2xextWC4QKYUcAvj77hEDVZHuZw";

// AuthClient with proper chrome.storage adapter for automatic session persistence
const supabase = new AuthClient({
  url: `${SUPABASE_URL}/auth/v1`,
  headers: { apikey: SUPABASE_ANON_KEY },
  persistSession: true,  // Enable automatic session persistence
  storage: createChromeStorageAdapter()  // Use proper Chrome storage adapter
});

// ───────────────────────────────── helpers ─────────────────────────────────────

// helper so we can pick up chrome.runtime.lastError *reliably*
function launchWebAuth(url: string): Promise<string> {
  return new Promise((resolve, reject) => {
    chrome.identity.launchWebAuthFlow(
      { url, interactive: true },
      (redirectUri) => {
        const err = chrome.runtime.lastError;
        if (err) {
          console.error("[auth] launchWebAuthFlow lastError →", err.message);
          reject(err);
          return;
        }
        if (!redirectUri) {
          reject(new Error("launchWebAuthFlow returned empty redirect URI"));
          return;
        }
        resolve(redirectUri);
      }
    );
  });
}

// ─────────────────────────────── ensureAuth() ──────────────────────────────────

export async function ensureAuth(): Promise<string> {
  const started = Date.now();
  console.info("[auth] ensureAuth() • start ─────────────────────────");

  // 🔍 DEBUG: Show what's currently in storage
  await debugStorageContents();
  await debugSupabaseSession();

  // 1. Check for existing session ──────────────────────────────────────
  try {
    const { data: { session }, error } = await supabase.getSession();
    console.info("[auth] getSession() result:", { 
      hasSession: !!session, 
      hasAccessToken: !!session?.access_token,
      hasRefreshToken: !!session?.refresh_token,
      expiresAt: session?.expires_at ? new Date(session.expires_at * 1000) : null,
      error 
    });
    
    if (session?.access_token) {
      // Validate token is not expired
      const now = Math.floor(Date.now() / 1000);
      const isExpired = session.expires_at ? session.expires_at < now : false;
      
      if (!isExpired) {
        console.info("[auth] ✅ using existing valid session");
        console.info(`[auth] ✅ token expires in ${session.expires_at ? Math.floor((session.expires_at - now) / 60) : 'unknown'} minutes`);
        console.info(`[auth] done in ${Date.now() - started} ms`);
        return session.access_token;
      } else {
        console.log("[auth] ⚠️ existing session is expired, will attempt refresh");
      }
    } else {
      console.log("[auth] ⚠️ no access token in session");
    }
  } catch (err) {
    console.error("[auth] ❌ getSession() threw", err);
  }

  // 2. Silent refresh ─────────────────────────────────────────────────
  try {
    console.info("[auth] attempting refreshSession() …");
    const { data, error } = await supabase.refreshSession();
    console.info("[auth] refreshSession() result:", { 
      hasSession: !!data?.session, 
      hasAccessToken: !!data?.session?.access_token,
      error 
    });

    const refreshed = data?.session?.access_token;
    if (refreshed) {
      console.info("[auth] ✅ got new token from refresh");
      console.info(`[auth] done in ${Date.now() - started} ms`);
      return refreshed;
    }
    if (error) console.log("[auth] ⚠️ refreshSession() error", error);
  } catch (err) {
    console.error("[auth] ❌ refreshSession() threw", err);
  }

  // 2.5. FALLBACK: Direct storage check ─────────────────────────────────
  try {
    console.info("[auth] 🔍 attempting direct storage fallback...");
    const storageAdapter = createChromeStorageAdapter();
    
    // Check for any stored session data
    const possibleKeys = [
      'supabase.auth.token',
      'sb-dmgtsseqqsiyuuzhdxnn-auth-token',
      'supabase.session',
      'sb-auth-token'
    ];
    
    for (const key of possibleKeys) {
      const stored = await storageAdapter.getItem(key);
      if (stored) {
        console.info(`[auth] 🔍 found stored data with key: ${key}`);
        try {
          const parsed = JSON.parse(stored);
          if (parsed.access_token) {
            // Validate expiration
            const now = Math.floor(Date.now() / 1000);
            const isExpired = parsed.expires_at ? parsed.expires_at < now : false;
            
            if (!isExpired) {
              console.info("[auth] ✅ using fallback stored token");
              // Try to restore the session
              await supabase.setSession({
                access_token: parsed.access_token,
                refresh_token: parsed.refresh_token || ''
              });
              return parsed.access_token;
            } else {
              console.log("[auth] ⚠️ fallback token is expired");
            }
          }
        } catch (parseErr) {
          console.log("[auth] ⚠️ failed to parse stored data", parseErr);
        }
      }
    }
    console.info("[auth] 🔍 no valid fallback tokens found");
  } catch (err) {
    console.error("[auth] ❌ direct storage fallback failed", err);
  }

  // 3. Interactive OAuth ──────────────────────────────────────────────
  // Use Chrome extension identity URL for OAuth redirects
  // Option 1: Direct URL construction (recommended for unpacked extensions)
  const redirectUrl = `https://${chrome.runtime.id}.chromiumapp.org/`;
  
  // Option 2: Using chrome.identity.getRedirectURL() (alternative)
  // Note: getRedirectURL() might add extra paths that cause issues
  // const redirectUrl = chrome.identity.getRedirectURL('oauth2').replace(/\/$/, ''); // Remove trailing slash
  
  console.info("[auth] starting OAuth flow – redirectURL:", redirectUrl);
  console.info("[auth] extension ID:", chrome.runtime.id);

  let oauthUrl: string;
  try {
    const { data: oauth, error: oauthErr } = await supabase.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: redirectUrl,
        skipBrowserRedirect: true,
      },
    });
    console.info("[auth] signInWithOAuth response:", { oauthErr, hasUrl: !!oauth?.url });
    if (oauthErr || !oauth?.url) throw oauthErr ?? new Error("OAuth URL missing");
    oauthUrl = oauth.url;
  } catch (e) {
    console.error("[auth] signInWithOAuth threw", e);
    throw e;
  }

  console.info("[auth] launching chrome.identity.launchWebAuthFlow …");
  let finalRedirect: string;
  try {
    console.info("[auth] opening URL →", oauthUrl);
    finalRedirect = await launchWebAuth(oauthUrl);
  } catch (e) {
    console.error("[auth] launchWebAuthFlow threw/lastError", e);
    throw e;
  }
  console.info("[auth] launchWebAuthFlow returned:", finalRedirect?.slice(0, 120));

  const qs = finalRedirect.split("#")[1] ?? "";
  const accessToken = new URLSearchParams(qs).get("access_token");
  const refreshToken = new URLSearchParams(qs).get("refresh_token") || "";
  console.info("[auth] extracted tokens:", { 
    hasAccessToken: !!accessToken,
    hasRefreshToken: !!refreshToken
  });
  
  if (!accessToken) throw new Error("access_token not returned from OAuth flow");

  // Set the session in the AuthClient (it will handle storage automatically)
  try {
    await supabase.setSession({
      access_token: accessToken,
      refresh_token: refreshToken
    });
    console.info("[auth] session set successfully");
  } catch (err) {
    console.error("[auth] failed to set session", err);
  }

  console.info("[auth] token stored – broadcasting AUTH_SUCCESS …");
  chrome.runtime.sendMessage({ type: "AUTH_SUCCESS" }).catch(() => {});

  console.info(`[auth] ensureAuth() • done in ${Date.now() - started} ms`);
  return accessToken;
}

// Legacy functions for backward compatibility (now simplified)
export async function loadJwt(): Promise<string | undefined> {
  const { data: { session } } = await supabase.getSession();
  return session?.access_token;
}

export function signOut() {
  console.info("[auth] signOut() called – signing out of Supabase");
  return supabase.signOut();
}

export const authClient = supabase;   // 👈 share the live instance