# How to Get JWT Token from Chrome Extension

## Method 1: Using Extension Service Worker

1. **Open Chrome Extensions page:**
   - Go to `chrome://extensions/`
   - Find your extension in the list

2. **Access Extension DevTools:**
   - Click "service worker" or "background page" link under your extension
   - This opens Chrome DevTools for the extension

3. **Run Token Extractor:**
   - Go to the **Console** tab in DevTools
   - Copy the entire contents of `get-fresh-token.js`
   - Paste it into the console and press Enter

## Method 2: Using Extension Sidepanel

1. **Open Extension:**
   - Click your extension icon to open the sidepanel

2. **Inspect Element:**
   - Right-click anywhere in the sidepanel
   - Select "Inspect" from context menu

3. **Run Token Extractor:**
   - Go to the **Console** tab in DevTools
   - Copy the entire contents of `get-fresh-token.js`
   - Paste it into the console and press Enter

## Expected Output

The script will:
- ✅ Search all Chrome storage for JWT tokens
- ✅ Show token expiration status
- ✅ Display full valid token for copying
- ✅ Show user info if available

## If No Token Found

1. **Sign in first:**
   - Click "Sign in with Google" in your extension
   - Complete the OAuth flow

2. **Run script again:**
   - The script will now find your fresh JWT token

## Testing Your Token

Once you have the token, test it with curl:

```bash
curl -X POST http://localhost:8000/workflows/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \
  -d '{"test": "data"}'
```

## Troubleshooting

- **"chrome is not defined"** → You're running in wrong context, use Chrome DevTools
- **No tokens found** → Sign in through extension first
- **Token expired** → Sign in again to get fresh token
- **401 Unauthorized** → Check if backend has correct JWT secret configured 