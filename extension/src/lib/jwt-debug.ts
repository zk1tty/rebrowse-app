/**
 * JWT Debug Helper
 * Helper functions to inspect and validate JWT tokens
 */

export function decodeJWT(token: string): any {
  try {
    // JWT has 3 parts: header.payload.signature
    const parts = token.split('.');
    if (parts.length !== 3) {
      throw new Error('Invalid JWT format');
    }

    // Decode the payload (base64url)
    const payload = parts[1];
    // Add padding if needed
    const paddedPayload = payload + '='.repeat((4 - payload.length % 4) % 4);
    const decodedPayload = atob(paddedPayload.replace(/-/g, '+').replace(/_/g, '/'));
    
    return JSON.parse(decodedPayload);
  } catch (error) {
    console.error('Failed to decode JWT:', error);
    return null;
  }
}

export function inspectJWT(token: string): void {
  console.group("🔍 [JWT Debug] Token Inspection");
  
  if (!token) {
    console.error("❌ No token provided");
    console.groupEnd();
    return;
  }

  console.log("📝 Token length:", token.length);
  console.log("🔤 Token start:", token.substring(0, 50) + "...");
  console.log("🔤 Token end:", "..." + token.substring(token.length - 50));
  
  const decoded = decodeJWT(token);
  if (decoded) {
    console.log("🎯 Decoded payload:", decoded);
    
    // Check standard JWT claims
    const now = Math.floor(Date.now() / 1000);
    
    if (decoded.exp) {
      const isExpired = decoded.exp < now;
      const expiresIn = Math.floor((decoded.exp - now) / 60);
      console.log(`⏰ Expiration: ${isExpired ? '❌ EXPIRED' : '✅ VALID'}`);
      if (!isExpired) {
        console.log(`⏳ Expires in: ${expiresIn} minutes`);
      }
    }
    
    if (decoded.iat) {
      const issuedAgo = Math.floor((now - decoded.iat) / 60);
      console.log(`📅 Issued: ${issuedAgo} minutes ago`);
    }
    
    if (decoded.sub) {
      console.log(`👤 Subject (user ID): ${decoded.sub}`);
    }
    
    if (decoded.email) {
      console.log(`📧 Email: ${decoded.email}`);
    }
    
    if (decoded.role) {
      console.log(`🎭 Role: ${decoded.role}`);
    }
    
    // Check for Supabase specific claims
    if (decoded.aud) {
      console.log(`🎯 Audience: ${decoded.aud}`);
    }
    
    if (decoded.iss) {
      console.log(`🏢 Issuer: ${decoded.iss}`);
    }
  }
  
  console.groupEnd();
}

export function validateJWTForAPI(token: string): { valid: boolean; reason?: string } {
  if (!token) {
    return { valid: false, reason: "No token provided" };
  }
  
  const decoded = decodeJWT(token);
  if (!decoded) {
    return { valid: false, reason: "Failed to decode JWT" };
  }
  
  const now = Math.floor(Date.now() / 1000);
  
  // Check expiration
  if (decoded.exp && decoded.exp < now) {
    return { valid: false, reason: "Token is expired" };
  }
  
  // Check if issued too long ago (sanity check)
  if (decoded.iat && (now - decoded.iat) > (24 * 60 * 60)) {
    return { valid: false, reason: "Token is too old (>24h)" };
  }
  
  // Check required claims for API
  if (!decoded.sub) {
    return { valid: false, reason: "Missing subject (user ID)" };
  }
  
  return { valid: true };
} 