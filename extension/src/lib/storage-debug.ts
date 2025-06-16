/**
 * Storage Debug Helper
 * Helper functions to inspect what's actually stored in Chrome storage
 */

export async function debugStorageContents(): Promise<void> {
  try {
    // Get all storage contents
    const allStorage = await chrome.storage.local.get(null);
    console.group("🔍 [Storage Debug] Current Chrome Storage Contents:");
    
    Object.entries(allStorage).forEach(([key, value]) => {
      console.log(`🔑 ${key}:`, value);
      
      // Special handling for Supabase session data
      if (key.includes('supabase') || key.includes('auth')) {
        console.log(`📋 [${key}] Details:`, JSON.stringify(value, null, 2));
      }
    });
    
    console.groupEnd();
    
    // Check for common Supabase keys
    const supabaseKeys = Object.keys(allStorage).filter(key => 
      key.includes('supabase') || key.includes('auth') || key.includes('session')
    );
    
    if (supabaseKeys.length === 0) {
      console.warn("⚠️ No Supabase/auth related keys found in storage!");
    } else {
      console.info(`✅ Found ${supabaseKeys.length} auth-related keys:`, supabaseKeys);
    }
    
  } catch (error) {
    console.error("❌ Failed to debug storage contents:", error);
  }
}

export async function debugSupabaseSession(): Promise<void> {
  try {
    // Try to find the Supabase session key
    const allStorage = await chrome.storage.local.get(null);
    const sessionKeys = Object.keys(allStorage).filter(key => 
      key.includes('supabase.auth.token') || key.includes('sb-') || key.includes('auth')
    );
    
    console.group("🔐 [Session Debug] Supabase Session Analysis:");
    
    if (sessionKeys.length === 0) {
      console.warn("⚠️ No Supabase session found in storage");
    } else {
      sessionKeys.forEach(key => {
        const session = allStorage[key];
        console.log(`📝 Session Key: ${key}`);
        
        if (typeof session === 'string') {
          try {
            const parsed = JSON.parse(session);
            console.log("🎯 Parsed Session:", {
              hasAccessToken: !!parsed.access_token,
              hasRefreshToken: !!parsed.refresh_token,
              expiresAt: parsed.expires_at ? new Date(parsed.expires_at * 1000) : 'N/A',
              user: parsed.user ? `${parsed.user.email} (${parsed.user.id})` : 'No user'
            });
            
            // Check if token is expired
            if (parsed.expires_at) {
              const now = Math.floor(Date.now() / 1000);
              const isExpired = parsed.expires_at < now;
              console.log(`⏰ Token Status: ${isExpired ? '❌ EXPIRED' : '✅ VALID'}`);
              if (!isExpired) {
                console.log(`⏳ Expires in: ${Math.floor((parsed.expires_at - now) / 60)} minutes`);
              }
            }
          } catch (e) {
            console.log("📄 Raw Session Data:", session);
          }
        } else {
          console.log("🔍 Session Object:", session);
        }
      });
    }
    
    console.groupEnd();
  } catch (error) {
    console.error("❌ Failed to debug Supabase session:", error);
  }
} 