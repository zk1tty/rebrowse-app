# Rebrowse Chromium Installation Guide

## 🚀 One-Liner Installation

Users can install all Chromium requirements with a single command:

```bash
curl -fsSL https://raw.githubusercontent.com/zk1tty/rebrowse-app/main/install-chromium.sh | bash
```

## 📋 What the Script Does

The installation script automatically:

1. **Detects Operating System** (Linux/macOS)
2. **Installs System Dependencies**:
   - Python 3.11+
   - System Chromium browser 
   - Xvfb (for headless operation)
   - Required fonts and libraries
3. **Installs Python Dependencies**:
   - Playwright >= 1.40.0
   - browser-use >= 0.2.4
   - FastAPI and other workflow dependencies
4. **Installs Playwright Chromium**:
   - Downloads Playwright's controlled Chromium
   - Installs system dependencies for Playwright
5. **Verifies Installation**:
   - Tests browser functionality
   - Creates a usage example
6. **Provides Next Steps**

## 🏗️ How to Host on GitHub

### Step 1: Create/Update Your Repository

1. Add the `install-chromium.sh` script to your repository root
2. Make sure the file is executable:
   ```bash
   chmod +x install-chromium.sh
   ```

### Step 2: Update the Script URL

Replace `YOUR_USERNAME/YOUR_REPO` in the script with your actual GitHub details:

```bash
# In install-chromium.sh, line 4:
# Usage: curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/install-chromium.sh | bash
```

For example:
```bash
# Usage: curl -fsSL https://raw.githubusercontent.com/rebrowse/workflow-backend/main/install-chromium.sh | bash
```

### Step 3: Commit and Push

```bash
git add install-chromium.sh
git commit -m "Add one-liner Chromium installation script"
git push origin main
```

### Step 4: Test the Installation

Test your hosted script:
```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/install-chromium.sh | bash
```

## 📖 Usage Examples

### Basic Installation
```bash
# Install everything with one command
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/install-chromium.sh | bash
```

### Download and Inspect First (Recommended)
```bash
# Download the script to inspect it
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/install-chromium.sh -o install-chromium.sh

# Make it executable
chmod +x install-chromium.sh

# Run it
./install-chromium.sh
```

### Silent Installation (for CI/CD)
```bash
# Run without interactive prompts
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/install-chromium.sh | bash -s -- --silent
```

## 🖥️ Supported Platforms

| Platform | Support | Package Manager |
|----------|---------|-----------------|
| Ubuntu/Debian | ✅ Full | apt-get |
| CentOS/RHEL/Fedora | ✅ Full | dnf/yum |
| macOS | ✅ Full | Homebrew |
| Windows | ❌ Use WSL2 | - |
| Alpine Linux | ⚠️ Manual | apk |

## 🧪 What Gets Installed

### Python Packages
- `playwright>=1.40.0` - Browser automation
- `browser-use>=0.2.4` - Workflow browser wrapper
- `fastapi>=0.115.0` - Web framework
- `uvicorn[standard]>=0.34.0` - ASGI server
- Additional workflow dependencies

### System Packages (Linux)
- `chromium-browser` - Chromium browser
- `xvfb` - Virtual display server
- Font packages (`liberation-fonts`, `dejavu-fonts`)
- Graphics libraries (`libgtk-3-0`, `libnss3`, etc.)

### System Packages (macOS)
- `chromium` - Chromium browser via Homebrew
- `python@3.11` - Python (if not installed)

## ✅ Verification

After installation, the script:

1. **Runs a test** to verify browser functionality
2. **Creates an example file** at `~/rebrowse_example.py`
3. **Provides usage instructions**

Test the installation manually:
```bash
python3 ~/rebrowse_example.py
```

## 🔧 Troubleshooting

### Common Issues

**"Permission denied" errors:**
```bash
# Run with explicit bash interpreter
bash <(curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/install-chromium.sh)
```

**"Command not found" errors:**
```bash
# Check if Python is in PATH
which python3
python3 --version

# Reinstall Playwright browsers
python3 -m playwright install chromium
```

**"Browser failed to start" errors:**
```bash
# For headless environments, set display
export DISPLAY=:99

# Run with xvfb
xvfb-run -a python3 ~/rebrowse_example.py
```

### Advanced Options

**Custom installation directory:**
```bash
# Set custom Python package location
export PYTHONUSERBASE=/custom/path
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/install-chromium.sh | bash
```

**Skip system dependencies (if already installed):**
Edit the script and comment out the system dependency installation sections.

## 📝 Documentation for Users

### In your README.md:

```markdown
## 🚀 Quick Setup

Install all requirements with one command:

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/install-chromium.sh | bash
```

This installs:
- ✅ Playwright Chromium browser
- ✅ Python dependencies (browser-use, playwright)
- ✅ System dependencies (fonts, libraries)
- ✅ Verification and testing tools

**Supported:** Ubuntu, Debian, CentOS, RHEL, Fedora, macOS  
**Requirements:** Python 3.11+, curl, sudo access
```

### Alternative Installation Methods:

```markdown
## Alternative Installation

### Manual Installation
```bash
# Install Python dependencies
pip install playwright>=1.40.0 browser-use>=0.2.4

# Install Playwright Chromium
playwright install chromium
playwright install-deps chromium
```

### Docker Installation
```dockerfile
FROM python:3.11-slim
RUN pip install playwright browser-use
RUN playwright install chromium
RUN playwright install-deps chromium
```
```

## 🔄 Updating the Script

To update the installation script:

1. **Modify** `install-chromium.sh`
2. **Test locally** first
3. **Commit and push** to GitHub
4. **Update version** if needed (add versioning in script comments)

Users will automatically get the latest version when they run the one-liner command.

## 🤝 Contributing

Users can contribute improvements to the installation script by:
1. Forking your repository
2. Making improvements to `install-chromium.sh`
3. Testing on their platform
4. Submitting a pull request

---

**Pro Tip:** Consider adding analytics to track installation success rates by having the script optionally report anonymized metrics. 