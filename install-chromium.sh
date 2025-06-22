#!/bin/bash

# Rebrowse Workflow - Chromium Setup Script
# Usage: curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/install-chromium.sh | bash

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# Install system dependencies for Linux
install_linux_deps() {
    log_info "Installing Linux system dependencies..."
    
    if command_exists apt-get; then
        # Debian/Ubuntu
        sudo apt-get update
        sudo apt-get install -y \
            python3 \
            python3-pip \
            python3-venv \
            chromium-browser \
            xvfb \
            fonts-liberation \
            fonts-dejavu-core \
            fontconfig \
            ca-certificates \
            libnss3 \
            libgtk-3-0 \
            libatk-1.0-0 \
            libdrm2 \
            libxcomposite1 \
            libxdamage1 \
            libxrandr2 \
            libgbm1 \
            libxss1 \
            libasound2
    elif command_exists dnf; then
        # Fedora/CentOS/RHEL
        sudo dnf install -y \
            python3 \
            python3-pip \
            chromium \
            xorg-x11-server-Xvfb \
            liberation-fonts \
            dejavu-fonts \
            fontconfig \
            ca-certificates \
            nss \
            gtk3 \
            atk \
            mesa-libgbm \
            alsa-lib
    elif command_exists yum; then
        # Older CentOS/RHEL
        sudo yum install -y \
            python3 \
            python3-pip \
            chromium \
            xorg-x11-server-Xvfb \
            liberation-fonts \
            dejavu-fonts \
            fontconfig \
            ca-certificates \
            nss \
            gtk3 \
            atk \
            alsa-lib
    else
        log_warning "Unknown Linux package manager. Please install dependencies manually."
        return 1
    fi
    
    log_success "Linux system dependencies installed"
}

# Install system dependencies for macOS
install_macos_deps() {
    log_info "Installing macOS dependencies..."
    
    if ! command_exists brew; then
        log_info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    # Install Python if not already installed
    if ! command_exists python3; then
        brew install python@3.11
    fi
    
    # Install Chromium
    brew install chromium
    
    log_success "macOS dependencies installed"
}

# Install Python dependencies
install_python_deps() {
    log_info "Installing Python dependencies..."
    
    # Upgrade pip
    python3 -m pip install --upgrade pip
    
    # Install required packages
    python3 -m pip install \
        playwright>=1.40.0 \
        browser-use>=0.2.4 \
        fastapi>=0.115.0 \
        uvicorn[standard]>=0.34.0 \
        aiofiles>=24.1.0 \
        aiohttp>=3.12.0 \
        typer>=0.15.0 \
        python-dotenv>=1.0.0
    
    log_success "Python dependencies installed"
}

# Install Playwright browsers
install_playwright_browsers() {
    log_info "Installing Playwright Chromium browser..."
    
    # Install Playwright browsers
    python3 -m playwright install chromium
    
    # Install system dependencies for Playwright
    python3 -m playwright install-deps chromium
    
    log_success "Playwright Chromium browser installed"
}

# Verify installation
verify_installation() {
    log_info "Verifying installation..."
    
    # Create a temporary test script
    cat > /tmp/test_chromium.py << 'EOF'
import asyncio
import sys
import os

async def test_browser():
    try:
        from browser_use import Browser
        from browser_use.browser.browser import BrowserProfile
        
        # Test headless browser (production-like)
        profile = BrowserProfile(
            headless=True,
            disable_security=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--single-process',
                '--no-first-run',
                '--disable-extensions'
            ]
        )
        
        browser = Browser(browser_profile=profile)
        await browser.start()
        
        page = await browser.get_current_page()
        await page.goto("data:text/html,<html><body><h1>Test Success</h1></body></html>")
        
        title = await page.title()
        
        await browser.close()
        
        print(f"✅ Browser test successful! Page title: '{title}'")
        return True
        
    except Exception as e:
        print(f"❌ Browser test failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_browser())
    sys.exit(0 if result else 1)
EOF

    # Run the test
    if python3 /tmp/test_chromium.py; then
        log_success "Installation verification passed!"
        return 0
    else
        log_error "Installation verification failed!"
        return 1
    fi
}

# Create a simple usage example
create_usage_example() {
    log_info "Creating usage example..."
    
    cat > ~/rebrowse_example.py << 'EOF'
import asyncio
from browser_use import Browser
from browser_use.browser.browser import BrowserProfile

async def example_workflow():
    """Example of using the browser for automation"""
    
    # Create browser with production-like settings
    profile = BrowserProfile(
        headless=False,  # Set to True for headless mode
        disable_security=True,
        args=[
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu' if False else '',  # Remove for GUI mode
            '--disable-web-security',
            '--no-first-run',
            '--disable-extensions'
        ]
    )
    
    browser = Browser(browser_profile=profile)
    await browser.start()
    
    try:
        page = await browser.get_current_page()
        
        # Navigate to a website
        await page.goto("https://example.com")
        
        # Get page title
        title = await page.title()
        print(f"Page title: {title}")
        
        # Take a screenshot (optional)
        # await page.screenshot(path="example.png")
        
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(example_workflow())
EOF

    log_success "Usage example created at ~/rebrowse_example.py"
    log_info "Run it with: python3 ~/rebrowse_example.py"
}

# Main installation function
main() {
    echo ""
    echo "🚀 Rebrowse Workflow - Chromium Setup"
    echo "========================================"
    echo ""
    
    # Detect OS
    OS=$(detect_os)
    log_info "Detected OS: $OS"
    
    # Check Python
    if ! command_exists python3; then
        log_error "Python 3 is required but not installed."
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    log_info "Python version: $PYTHON_VERSION"
    
    # Install system dependencies based on OS
    case $OS in
        "linux")
            install_linux_deps
            ;;
        "macos")
            install_macos_deps
            ;;
        "windows")
            log_error "Windows is not supported by this script. Please use WSL2 or manual installation."
            exit 1
            ;;
        *)
            log_warning "Unknown OS. Skipping system dependencies installation."
            ;;
    esac
    
    # Install Python dependencies
    install_python_deps
    
    # Install Playwright browsers
    install_playwright_browsers
    
    # Verify installation
    if verify_installation; then
        create_usage_example
        
        echo ""
        log_success "🎉 Installation completed successfully!"
        echo ""
        echo "Next steps:"
        echo "1. Test the installation: python3 ~/rebrowse_example.py"
        echo "2. For headless mode, set headless=True in the BrowserProfile"
        echo "3. Check your workflow backend documentation for API usage"
        echo ""
        echo "Troubleshooting:"
        echo "- If you encounter issues, try: python3 -m playwright install chromium"
        echo "- For production/Docker: set DISPLAY=:99 and use xvfb-run"
        echo "- Logs location: Check your application logs for detailed error messages"
        echo ""
    else
        log_error "Installation verification failed. Please check the errors above."
        exit 1
    fi
}

# Run main function
main "$@" 