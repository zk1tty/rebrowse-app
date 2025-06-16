/**
 * CHROME EXTENSION TOKEN EXTRACTOR
 * 
 * ⚠️  IMPORTANT: This script MUST be run in Chrome DevTools Console!
 * 
 * HOW TO USE:
 * 1. Open Chrome and go to chrome://extensions/
 * 2. Find your extension and click "service worker" or "background page"
 * 3. In the DevTools that opens, go to the Console tab
 * 4. Copy and paste this entire script into the console and press Enter
 * 
 * OR:
 * 1. Open your extension's sidepanel
 * 2. Right-click and select "Inspect"
 * 3. In DevTools, go to Console tab
 * 4. Copy and paste this entire script and press Enter
 */

// Function to get fresh token from extension storage
async function getFreshToken() {
  try {
    // Check if chrome API is available
    if (typeof chrome === 'undefined' || !chrome.storage) {
      console.error("❌ Chrome API not available. Make sure you're running this in Chrome DevTools console within the extension context!");
      console.log("📖 Instructions:");
      console.log("1. Go to chrome://extensions/");
      console.log("2. Find your extension and click 'service worker' or 'background page'");  
      console.log("3. In DevTools Console, paste and run this script");
      return null;
    }

    console.log("🔍 Searching Chrome storage for JWT tokens...");
    
    // Get all chrome storage
    const result = await chrome.storage.local.get(null);
    console.log("📦 All storage keys:", Object.keys(result));
    
    // Look for Supabase session
    const sessionKeys = Object.keys(result).filter(key => 
      key.includes('supabase') || key.includes('auth') || key.includes('session')
    );
    
    console.log("🔑 Auth-related keys found:", sessionKeys);
    
    for (const key of sessionKeys) {
      try {
        const value = result[key];
        let session = typeof value === 'string' ? JSON.parse(value) : value;
        
        // Handle nested session structure
        if (session.session && session.session.access_token) {
          session = session.session;
        }
        
        if (session.access_token) {
          const now = Math.floor(Date.now() / 1000);
          const expires = session.expires_at || 0;
          const isExpired = expires < now;
          
          console.log(`\n🎯 Found JWT token in key: ${key}`);
          console.log("📝 Token (first 50 chars):", session.access_token.substring(0, 50) + "...");
          console.log("⏰ Expired:", isExpired ? "❌ YES" : "✅ NO");
          console.log("⏳ Expires in:", Math.floor((expires - now) / 60), "minutes");
          console.log("🕐 Expires at:", new Date(expires * 1000).toLocaleString());
          
          if (!isExpired) {
            console.log("\n✅ This token is valid! Full token below:");
            console.log("═".repeat(80));
            console.log(session.access_token);
            console.log("═".repeat(80));
            
            // Also log user info if available
            if (session.user) {
              console.log("👤 User email:", session.user.email);
              console.log("🆔 User ID:", session.user.id);
            }
            
            return session.access_token;
          } else {
            console.log("⚠️  This token is expired");
          }
        }
      } catch (parseError) {
        console.log(`⚠️  Could not parse value for key ${key}:`, parseError.message);
      }
    }
    
    console.log("❌ No valid JWT token found in storage");
    console.log("💡 Try clicking 'Sign in with Google' in the extension first");
    return null;
    
  } catch (error) {
    console.error("❌ Error getting token:", error);
    return null;
  }
}

// Function to clear all auth tokens (useful for testing)
async function clearAuthTokens() {
  try {
    const result = await chrome.storage.local.get(null);
    const authKeys = Object.keys(result).filter(key => 
      key.includes('supabase') || key.includes('auth') || key.includes('session')
    );
    
    if (authKeys.length > 0) {
      await chrome.storage.local.remove(authKeys);
      console.log("🧹 Cleared auth tokens:", authKeys);
    } else {
      console.log("🧹 No auth tokens found to clear");
    }
  } catch (error) {
    console.error("❌ Error clearing tokens:", error);
  }
}

console.log("🚀 Chrome Extension Token Extractor loaded!");
console.log("📞 Run: getFreshToken() - to get current token");  
console.log("🧹 Run: clearAuthTokens() - to clear all tokens");
console.log("═".repeat(60));

// Auto-run the token extraction
getFreshToken().then(token => {
  if (token) {
    console.log("\n🎉 SUCCESS! Copy the token above for your curl test");
    console.log("💡 You can now test your upload with a valid JWT token");
  } else {
    console.log("\n💡 No valid token found. Sign in through the extension first, then run getFreshToken() again");
  }
}); 