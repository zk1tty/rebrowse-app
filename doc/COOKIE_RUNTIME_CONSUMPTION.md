# Cookie Runtime Consumption Guide

This document explains how uploaded cookies are consumed at runtime to create authenticated browser sessions in the workflow execution system.

## Overview

The system automatically retrieves and decrypts user-uploaded cookies during browser context initialization, allowing headless Chromium sessions to start with authenticated state from the user's local browser.

## Architecture

```
User Uploads Cookies → Database (Encrypted) → Runtime Decryption → Playwright Context
```

1. **Upload**: User uploads encrypted cookies via Chrome Extension
2. **Storage**: Cookies stored encrypted in PostgreSQL `cookie_uploads` table
3. **Retrieval**: Runtime fetches latest verified cookies for user
4. **Decryption**: Server-side decryption using private key
5. **Injection**: Decrypted cookies injected into Playwright browser context

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FEATURE_USE_COOKIES` | `false` | Enable/disable cookie consumption |
| `COOKIE_VERIFY_TTL_HOURS` | `24` | Max age for verified cookies |
| `COOKIE_PRIVATE_KEY_PEM` | - | RSA private key for decryption |
| `COOKIE_KID` | - | Key ID for encryption |

### Health Check

Monitor cookie status via health endpoint:

```bash
curl http://localhost:8000/health
```

Response includes cookie summary:
```json
{
  "status": "healthy",
  "cookies": {
    "enabled": true,
    "kid": "rsa-prod-2024",
    "ttl_hours": 24,
    "allowlist": ["x.com", "linkedin.com", "instagram.com", "facebook.com", "tiktok.com"]
  }
}
```

## Runtime Flow

### 1. Workflow Execution Trigger

When a workflow is executed via `POST /workflows/{workflow_id}/execute`:

```python
# backend/service.py
async def run_workflow_session_with_visual_streaming(
    workflow_id: str,
    owner_id: str,
    # ... other params
):
    # 1. Check if cookies are enabled
    if os.getenv("FEATURE_USE_COOKIES", "false").lower() == "true":
        try:
            # 2. Fetch and decrypt latest verified cookies
            storage_state = await _get_storage_state_for_user(owner_id)
        except Exception as e:
            logger.warning(f"Failed to load cookies for user {owner_id}: {e}")
            storage_state = None
    else:
        storage_state = None
    
    # 3. Create browser with cookies
    browser = await browser_factory.create_browser_with_rrweb(
        storage_state=storage_state,  # Injected here
        # ... other params
    )
```

### 2. Cookie Retrieval

The system fetches the most recent verified cookie upload:

```python
async def _get_storage_state_for_user(owner_id: str):
    # Query latest verified record
    record = get_latest_verified_cookie_upload(
        user_id=owner_id,
        sites=None,  # All sites
        ttl_hours=int(os.getenv("COOKIE_VERIFY_TTL_HOURS", "24"))
    )
    
    if not record:
        return None
    
    # Decrypt the storage state
    return decrypt_storage_state_row(record)
```

### 3. Database Query

Queries the `cookie_uploads` table:

```sql
SELECT 
    id, ciphertext, wrapped_key, nonce, 
    metadata, created_at, verified
FROM cookie_uploads 
WHERE owner_id = $1 
  AND status = 'verified'
  AND verified IS NOT NULL
  AND created_at > NOW() - INTERVAL '$2 hours'
ORDER BY created_at DESC 
LIMIT 1;
```

### 4. Decryption Process

The encrypted blob is decrypted using envelope encryption:

```python
def decrypt_storage_state_row(row):
    # 1. Decode base64 fields
    ciphertext = _b64_decode(row["ciphertext"])
    wrapped_key = _b64_decode(row["wrapped_key"]) 
    nonce = _b64_decode(row["nonce"])
    
    # 2. Unwrap AES key using RSA private key
    private_key = load_private_key()
    data_key = private_key.decrypt(
        wrapped_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    # 3. Decrypt payload using AES-GCM
    aesgcm = AESGCM(data_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    
    # 4. Parse JSON and return Playwright format
    return json.loads(plaintext)
```

### 5. Playwright Integration

Decrypted cookies are injected into the browser context:

```python
# In browser_factory.create_browser_with_rrweb()
context = await browser.new_context(
    storage_state=storage_state,  # Contains cookies + localStorage
    # ... other context options
)
```

The `storage_state` format matches Playwright's expected structure:

```json
{
  "cookies": [
    {
      "name": "auth_token",
      "value": "abc123...",
      "domain": ".x.com",
      "path": "/",
      "expires": 0,
      "httpOnly": true,
      "secure": true,
      "sameSite": "Lax"
    }
  ],
  "origins": [
    {
      "origin": "https://x.com",
      "localStorage": [
        {"name": "session_data", "value": "xyz789..."}
      ]
    }
  ]
}
```

## Error Handling

### Graceful Fallbacks

The system handles various failure scenarios gracefully:

1. **Cookies Disabled**: `FEATURE_USE_COOKIES=false` → Anonymous session
2. **No Verified Records**: No recent uploads → Anonymous session  
3. **Decryption Failure**: Invalid/corrupted data → Anonymous session
4. **Database Error**: Connection issues → Anonymous session

All failures are logged as warnings, and execution continues with anonymous context.

### Logging

Key log messages:

```
INFO: Loading cookies for user user-123
WARNING: Failed to load cookies for user user-123: No verified records found
WARNING: Failed to load cookies for user user-123: Decryption failed: Invalid padding
INFO: Starting browser with authenticated session (5 cookies loaded)
INFO: Starting browser with anonymous session (cookies disabled)
```

## Security Considerations

### Data Protection

- **Encryption at Rest**: All cookies encrypted with RSA-2048 + AES-256-GCM
- **Key Management**: Private keys stored in environment variables
- **Access Control**: Row-level security (RLS) restricts access by user
- **TTL Enforcement**: Automatic expiration of old cookie data

### Privacy

- **User Isolation**: Each user's cookies are completely isolated
- **No Logging**: Cookie values are never logged in plaintext
- **Secure Transmission**: All API calls use HTTPS
- **Minimal Retention**: Old records can be purged based on TTL

## Monitoring

### Health Checks

Monitor cookie system health:

```bash
# Check overall health
curl http://localhost:8000/health

# Check specific cookie record
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/auth/storage-state/st_abc123/debug
```

### Metrics

Key metrics to monitor:

- Cookie upload success rate
- Decryption failure rate  
- Anonymous session fallback rate
- Cookie age distribution
- Database query performance

## Troubleshooting

### Common Issues

1. **"No verified records found"**
   - User hasn't uploaded cookies recently
   - Check `COOKIE_VERIFY_TTL_HOURS` setting
   - Verify user has completed upload + verification

2. **"Decryption failed"**
   - Key mismatch between upload and runtime
   - Check `COOKIE_PRIVATE_KEY_PEM` matches upload key
   - Verify `COOKIE_KID` consistency

3. **"Database connection failed"**
   - Check Supabase connection
   - Verify database credentials
   - Check network connectivity

### Debug Commands

```bash
# Test cookie retrieval for specific user
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/auth/storage-state?limit=1"

# Check cookie record details
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/auth/storage-state/st_abc123/debug"

# Verify health status
curl http://localhost:8000/health | jq '.cookies'
```

## Performance

### Optimization

- **Caching**: Consider caching decrypted cookies for short periods
- **Batch Loading**: Load cookies once per session, not per request
- **Database Indexing**: Ensure proper indexes on `owner_id`, `status`, `created_at`
- **Connection Pooling**: Use connection pooling for database access

### Resource Usage

- **Memory**: Decrypted cookies stored in memory during session
- **CPU**: RSA decryption is CPU-intensive but infrequent
- **Network**: Database queries are lightweight
- **Storage**: Encrypted blobs are relatively small

## Future Enhancements

### Planned Features

1. **Cookie Refresh**: Automatic re-upload of expired cookies
2. **Selective Loading**: Load cookies only for specific domains
3. **Cookie Validation**: Verify cookies are still valid before use
4. **Analytics**: Track cookie usage patterns and success rates
5. **Multi-User Sessions**: Support multiple authenticated users per workflow

### Integration Points

- **Chrome Extension**: Seamless cookie upload experience
- **User Dashboard**: Cookie management interface
- **Monitoring**: Real-time cookie health monitoring
- **Backup**: Automated cookie backup and recovery
