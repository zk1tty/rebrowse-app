/**
 * Test script to verify JWT secret
 * Run with Node.js to test which secret works
 */

import crypto from 'crypto';

// Your JWT token from the console
const token = "eyJhbGciOiJIUzI1NiIsImtpZCI6IklKclRKS29xc0Z6ZmxUVWMiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2RtZ3Rzc2VxcXNpeXV1emhkeG5uLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiJiOTNkOGNhMy01YTFjLTQ2ZDMtOTU3MS0zNmFkNDRkMDlkNmQiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzQ5ODk0NjU2LCJpYXQiOjE3NDk4OTEwNTYsImVtYWlsIjoibm9yaWthQDB4Y2VyYmVydXMuaW8iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6Imdvb2dsZSIsInByb3ZpZGVycyI6WyJnb29nbGUiXX0sInVzZXJfbWV0YWRhdGEiOnsiYXZhdGFyX3VybCI6Imh0dHBzOi8vbGgzLmdvb2dsZXVzZXJjb250ZW50LmNvbS9hL0FDZzhvY0xpOXlmMTRLSVBTUXl0RWV1eXhTdWZadTN5TEtXS3FjS3JGT0FoNm5aNVZCdzB5alk9czk2LWMiLCJjdXN0b21fY2xhaW1zIjp7ImhkIjoiMHhjZXJiZXJ1cy5pbyJ9LCJlbWFpbCI6Im5vcmlrYUAweGNlcmJlcnVzLmlvIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsImZ1bGxfbmFtZSI6Ik5vcmlrYSBLaXphd2EiLCJpc3MiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20iLCJuYW1lIjoiTm9yaWthIEtpemF3YSIsInBob25lX3ZlcmlmaWVkIjpmYWxzZSwicGljdHVyZSI6Imh0dHBzOi8vbGgzLmdvb2dsZXVzZXJjb250ZW50LmNvbS9hL0FDZzhvY0xpOXlmMTRLSVBTUXl0RWV1eXhTdWZadTN5TEtXS3FjS3JGT0FoNm5aNVZCdzB5alk9czk2LWMiLCJwcm92aWRlcl9pZCI6IjExMTQwNDkzNjAzNzQ3MDU4MjQ2MSIsInN1YiI6IjExMTQwNDkzNjAzNzQ3MDU4MjQ2MSJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6Im9hdXRoIiwidGltZXN0YW1wIjoxNzQ5ODkxMDU2fV0sInNlc3Npb25faWQiOiI3NzU4OTkzOC1jZGZkLTQ3MTMtODU0NS03YjY0OTkyY2M1ZTMiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.52YDdHL7OkKYW5PD9t6laai_yhZ3OC27Qml7IQFTexs";

// Split the token
const [header, payload, signature] = token.split('.');

// Decode the header and payload
const decodedHeader = JSON.parse(Buffer.from(header, 'base64url').toString());
const decodedPayload = JSON.parse(Buffer.from(payload, 'base64url').toString());

console.log("🎯 JWT Header:", decodedHeader);
console.log("🎯 JWT Payload:", decodedPayload);
console.log("🎯 JWT Signature:", signature);

// Function to test a secret
function testSecret(secret, label) {
    try {
        const signingInput = header + '.' + payload;
        const expectedSignature = crypto
            .createHmac('sha256', secret)
            .update(signingInput)
            .digest('base64url');
        
        const isValid = expectedSignature === signature;
        console.log(`\n🔍 Testing ${label}:`);
        console.log(`   Secret: ${secret.substring(0, 20)}...`);
        console.log(`   Expected: ${expectedSignature.substring(0, 20)}...`);
        console.log(`   Actual:   ${signature.substring(0, 20)}...`);
        console.log(`   Valid: ${isValid ? '✅ YES' : '❌ NO'}`);
        
        return isValid;
    } catch (error) {
        console.log(`\n❌ Error testing ${label}:`, error.message);
        return false;
    }
}

// Test with the anon key (probably won't work, but let's see)
const anonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRtZ3Rzc2VxcXNpeXV1emhkeG5uIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk3MzE4ODIsImV4cCI6MjA2NTMwNzg4Mn0.e5bQXtdRsPY31fEp2xextWC4QKYUcAvj77hEDVZHuZw";

console.log("\n🔍 Testing JWT verification with different secrets:");
console.log("=" .repeat(60));

// Test with anon key (probably won't work)
testSecret(anonKey, "Anon Key");

// Test with the JWT secret from wf-backend/.env
const jwtSecret = "iVYEePJzuD71RYvIh1VqlkUxXIKV0Rzg38EYWA0ZlcAH6AWpYa2Cq/vm13c01fMUu/6wwfx71Tx1PvYby/Qd1w==";
testSecret(jwtSecret, "JWT Secret from .env");

console.log("\n💡 The JWT secret is typically different from the anon key.");
console.log("💡 You need to get the JWT secret from your Supabase dashboard:");
console.log("   1. Go to https://supabase.com/dashboard");
console.log("   2. Select project: dmgtsseqqsiyuuzhdxnn");
console.log("   3. Go to Settings → API");
console.log("   4. Find 'JWT Secret' (usually at the bottom)");
console.log("   5. Copy that value and use it as SUPABASE_JWT_SECRET"); 