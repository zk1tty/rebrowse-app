# Test Suite

This directory contains all test scripts for the wf-backend project. All tests have been configured with robust path handling to work from this subdirectory.

## Available Tests

### 🎭 Playwright Setup Test
**File:** `test_playwright_setup.py`
**Purpose:** Verify Playwright installation and browser functionality
**Usage:**
```bash
cd test
python test_playwright_setup.py
```
**Features Tested:**
- Playwright package installation
- browser-use import functionality
- Playwright browser installation (Chromium)
- Browser instance creation
- Basic browser functionality (navigation, page interaction)

### 🎮 Custom Screensaver Test
**File:** `test_custom_screensaver.py`
**Purpose:** Test the rebrowse custom DVD screensaver functionality
**Usage:**
```bash
cd test
python test_custom_screensaver.py
```
**Features Tested:**
- Auto-detection of rebrowse.png logo
- Purple gradient background
- Bouncing animation with physics
- Color-changing effects on bounce
- Sparkle particle effects

### 🌐 Session Execution Test
**File:** `test_session_execution.py`
**Purpose:** Test session-based workflow execution endpoints
**Usage:**
```bash
cd test
python test_session_execution.py
```
**Features Tested:**
- Health check endpoint
- Session token validation
- Workflow execution endpoint
- Background task management

### 🖥️ Browser Local Test
**File:** `test_browser_local.py`
**Purpose:** Comprehensive browser functionality testing
**Usage:**
```bash
cd test
python test_browser_local.py
```
**Features Tested:**
- System requirements check
- Basic browser functionality
- Headless browser configuration
- Real website navigation
- Production readiness validation

### 🔐 JWT Token Tests
**File:** `test-jwt-local.py`
**Purpose:** Test JWT token validation locally
**Usage:**
```bash
cd test
python test-jwt-local.py
```
**Features Tested:**
- JWT token decoding
- Signature verification
- API authentication

**File:** `test-fresh-token.py`
**Purpose:** Interactive test for fresh JWT tokens from Chrome extension
**Usage:**
```bash
cd test
python test-fresh-token.py
```
**Features Tested:**
- Interactive token input
- Token expiration checking
- Live API testing

## Running Tests

### From Test Directory
```bash
cd test
python <test_file_name>.py
```

### From Project Root
```bash
python test/<test_file_name>.py
```

## Recommended Test Order

For troubleshooting deployment issues, run tests in this order:

1. **Playwright Setup** - `test_playwright_setup.py` - Verify core browser functionality
2. **Browser Local** - `test_browser_local.py` - Comprehensive browser testing
3. **Custom Screensaver** - `test_custom_screensaver.py` - Test rebrowse features
4. **Session Execution** - `test_session_execution.py` - Test API endpoints
5. **JWT Tests** - `test-jwt-local.py` / `test-fresh-token.py` - Test authentication

## Path Handling

All test files use robust path handling with:
- `Path(__file__).parent.parent` to find project root
- `sys.path.insert(0, str(project_root))` for imports
- Automatic detection of configuration files (`.env`, `rebrowse.png`)

This ensures tests work correctly regardless of where they're run from.

## Prerequisites

- Python 3.11+
- All project dependencies installed (`pip install -r requirements.txt`)
- **Playwright browsers**: `playwright install chromium` (critical for production)
- For browser tests: Chromium/Chrome installed
- For API tests: Backend server running on localhost:8000
- For JWT tests: Valid `.env` file with `SUPABASE_JWT_SECRET`

## Production Deployment Issues

If you encounter browser-related errors in production:

1. **Run Playwright Setup Test** first to verify browser installation
2. **Check deployment logs** for Playwright installation messages
3. **Verify health endpoints**: `/health` and `/test-browser`
4. **Common fixes**:
   - Ensure `playwright install chromium` runs during build
   - Check Dockerfile/nixpacks.toml includes Playwright setup
   - Verify virtual display (Xvfb) is running in production

## Test Results

All tests provide detailed output with:
- ✅ Success indicators
- ❌ Failure indicators  
- 📋 Summary reports
- 💡 Troubleshooting tips 