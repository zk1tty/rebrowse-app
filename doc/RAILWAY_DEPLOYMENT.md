# Railway Deployment Guide for Workflow Backend

This guide covers deploying the workflow backend with headless browser support to Railway.

## 🚀 Quick Deployment

### 1. Prerequisites
- Railway account ([railway.app](https://railway.app))
- Railway CLI installed: `npm install -g @railway/cli`
- Environment variables ready

### 2. Environment Variables
Set these in your Railway project dashboard:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_JWT_SECRET=your_supabase_jwt_secret

# Optional (Railway sets these automatically)
RAILWAY_ENVIRONMENT=production
PORT=8000
```

### 3. Deploy to Railway

```bash
# Login to Railway
railway login

# Link your project (or create new)
railway link

# Deploy
railway up
```

## 🔧 Browser Configuration

### Automatic Browser Setup
The application automatically detects the environment and configures the browser:

- **Local Development**: Standard browser with GUI
- **Railway Production**: Headless Chromium with optimized flags

### Browser Dependencies (Handled Automatically)
The `nixpacks.toml` configuration installs:
- Chromium browser
- Xvfb (virtual display)
- Required fonts and libraries
- GTK and graphics libraries

## 🧪 Testing Your Deployment

### 1. Health Check
```bash
curl https://your-app.railway.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "rebrowse-backend",
  "llm_available": true,
  "browser_available": true,
  "tmp_dir_exists": true,
  "filesystem_writable": true
}
```

### 2. Browser Test
```bash
curl https://your-app.railway.app/test-browser
```

Expected response:
```json
{
  "environment": {
    "environment": "production",
    "display": ":99",
    "railway_env": "production"
  },
  "chromium_detection": {
    "/usr/bin/chromium-browser": {
      "exists": true,
      "executable": true,
      "path": "/usr/bin/chromium-browser"
    }
  },
  "browser_test": {
    "status": "success",
    "chromium_path": "/usr/bin/chromium-browser",
    "page_title": "",
    "message": "Browser test completed successfully"
  }
}
```

### 3. Workflow Execution Test
```bash
curl -X POST "https://your-app.railway.app/workflows/{workflow_id}/execute/session" \
  -H "Content-Type: application/json" \
  -d '{
    "session_token": "your_valid_session_token",
    "inputs": {}
  }'
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Browser Not Found
**Symptoms**: `browser_test.status: "failed"`, Chromium not detected

**Solutions**:
- Check Railway build logs for Chromium installation
- Verify `nixpacks.toml` configuration
- Ensure all browser dependencies are installed

#### 2. Display Issues
**Symptoms**: Browser fails to start, display errors

**Solutions**:
- Verify Xvfb is running (handled by start command)
- Check `DISPLAY` environment variable is set
- Ensure virtual display is properly configured

#### 3. Memory Issues
**Symptoms**: Browser crashes, out of memory errors

**Solutions**:
- Upgrade Railway plan for more memory
- Optimize browser flags in `BrowserProfile`
- Use `--single-process` flag (already included)

#### 4. Permission Issues
**Symptoms**: Browser fails to start, permission denied

**Solutions**:
- Ensure `--no-sandbox` flag is used (already included)
- Check file system permissions
- Verify Railway container security settings

### Debug Commands

Check browser installation:
```bash
# In Railway console
which chromium-browser
chromium-browser --version
echo $DISPLAY
ps aux | grep Xvfb
```

Check logs:
```bash
railway logs
```

## 📊 Performance Optimization

### Browser Configuration
The production browser is configured with:
- Headless mode (no GUI)
- Single process (memory efficient)
- Disabled GPU acceleration
- Optimized flags for containers

### Resource Usage
- **Memory**: ~200-500MB per browser instance
- **CPU**: Moderate during workflow execution
- **Storage**: Minimal (temporary files cleaned up)

### Scaling Considerations
- Each workflow execution uses one browser instance
- Browser instances are created/destroyed per workflow
- Consider connection pooling for high-volume usage

## 🔒 Security

### Browser Security
- Web security disabled for automation
- Sandbox disabled (required for containers)
- No extensions or plugins loaded
- Isolated browser profiles

### Network Security
- HTTPS enforced in production
- CORS properly configured
- Session token validation
- Ownership verification

## 📝 Configuration Files

### `nixpacks.toml`
Handles system dependencies and browser installation.

### `railway.toml`
Railway-specific deployment configuration.

### `backend/service.py`
Browser configuration and environment detection.

## 🚀 Next Steps

1. **Monitor Deployment**: Use Railway dashboard to monitor performance
2. **Set Up Alerts**: Configure alerts for health check failures
3. **Scale Resources**: Upgrade plan if needed for higher usage
4. **Custom Domain**: Set up custom domain in Railway dashboard
5. **CI/CD**: Set up automatic deployments from GitHub

## 📞 Support

If you encounter issues:
1. Check Railway build logs
2. Test browser functionality with `/test-browser` endpoint
3. Verify environment variables are set correctly
4. Check health endpoint for service status

For Railway-specific issues, consult [Railway documentation](https://docs.railway.app). 