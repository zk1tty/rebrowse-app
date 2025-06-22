#!/bin/bash

# Rebrowse Workflow - Chromium Setup Script
# Usage: curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/install-chromium.sh | bash
# 
# Environment variables:
# FORCE_PYTHON311=1    - Force install Python 3.11 even if newer version exists
# SKIP_REPORTING=1     - Skip sending installation reports to monitoring endpoint
# SKIP_DEMO=1          - Skip running the demo after installation
# SUPABASE_URL=...     - Custom Supabase project URL for reporting
# SUPABASE_KEY=...     - Custom Supabase anon key for reporting

set -e  # Exit on any error

# Configuration (can be overridden by environment variables)
REPORTING_ENDPOINT="https://dmgtsseqqsiyuuzhdxnn.supabase.co/rest/v1/installation_reports"
REPORTING_API_KEY="REMOVED.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRtZ3Rzc2VxcXNpeXV1emhkeG5uIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk3MzE4ODIsImV4cCI6MjA2NTMwNzg4Mn0.e5bQXtdRsPY31fEp2xextWC4QKYUcAvj77hEDVZHuZw"

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

# Check Python version compatibility
check_python_version() {
    # Use the specific Python path if set, otherwise default to python3
    local python_cmd="${PYTHON3_PATH:-python3}"
    
    if ! command_exists "$python_cmd"; then
        log_error "Python 3 is required but not installed at: $python_cmd"
        return 1
    fi
    
    PYTHON_VERSION=$($python_cmd --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    log_info "Checking Python version using: $python_cmd"
    log_info "Python version: $PYTHON_VERSION"
    
    # Check if Python version is >= 3.11
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
        log_error "Python 3.11 or higher is required for browser-use package."
        log_error "Current version: $PYTHON_VERSION (from $python_cmd)"
        return 1
    fi
    
    log_success "Python version $PYTHON_VERSION meets requirements (>=3.11)"
    return 0
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
    
    # Install Python 3.11+ if current version is too old or if forced
    CURRENT_PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' || echo "0.0.0")
    PYTHON_MAJOR=$(echo $CURRENT_PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $CURRENT_PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]) || [ "${FORCE_PYTHON311:-0}" = "1" ]; then
        log_info "Installing Python 3.11 (current version $CURRENT_PYTHON_VERSION is too old)..."
        brew install python@3.11
        
        # Update PATH to use the new Python
        export PATH="/opt/homebrew/bin:$PATH"
        
        # Set the Python path to use the new version
        if [ -f "/opt/homebrew/bin/python3.11" ]; then
            log_info "Using Python 3.11 from Homebrew: /opt/homebrew/bin/python3.11"
            export PYTHON3_PATH="/opt/homebrew/bin/python3.11"
        elif [ -f "/opt/homebrew/opt/python@3.11/bin/python3.11" ]; then
            log_info "Using Python 3.11 from Homebrew (alternate path)"
            export PYTHON3_PATH="/opt/homebrew/opt/python@3.11/bin/python3.11"
        elif command_exists python3.11; then
            log_info "Found python3.11 in PATH"
            export PYTHON3_PATH="python3.11"
        else
            log_warning "Could not find python3.11 binary, will try to use python3.11 from PATH"
            export PYTHON3_PATH="python3.11"
        fi
    else
        log_info "Python version $CURRENT_PYTHON_VERSION meets requirements"
        export PYTHON3_PATH="python3"
    fi
    
    # Install Chromium
    if ! command_exists chromium; then
        brew install chromium
    else
        log_info "Chromium already installed"
    fi
    
    log_success "macOS dependencies installed"
}

# Install Python dependencies
install_python_deps() {
    log_info "Installing Python dependencies..."
    
    # Use the correct Python path
    local python_cmd="${PYTHON3_PATH:-python3}"
    
    # Verify Python version again
    local version=$($python_cmd --version 2>&1 | awk '{print $2}')
    log_info "Using Python: $python_cmd (version: $version)"
    
    # Upgrade pip
    $python_cmd -m pip install --upgrade pip --user --no-warn-script-location
    
    # Install required packages
    log_info "Installing browser-use and dependencies..."
    $python_cmd -m pip install --user --no-warn-script-location \
        playwright>=1.40.0 \
        browser-use>=0.2.4 \
        fastapi>=0.115.0 \
        uvicorn[standard]>=0.34.0 \
        aiofiles>=24.1.0 \
        aiohttp>=3.12.0 \
        typer>=0.15.0 \
        python-dotenv>=1.0.0
    
    if [ $? -eq 0 ]; then
        log_success "Python dependencies installed"
    else
        log_error "Failed to install Python dependencies"
        return 1
    fi
}

# Install Playwright browsers
install_playwright_browsers() {
    log_info "Installing Playwright Chromium browser..."
    
    # Use the correct Python path
    local python_cmd="${PYTHON3_PATH:-python3}"
    
    # Install Playwright browsers
    $python_cmd -m playwright install chromium
    
    # Install system dependencies for Playwright
    $python_cmd -m playwright install-deps chromium
    
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
    local python_cmd="${PYTHON3_PATH:-python3}"
    if $python_cmd /tmp/test_chromium.py; then
        log_success "Installation verification passed!"
        return 0
    else
        log_error "Installation verification failed!"
        return 1
    fi
}

# Send installation report to monitoring endpoint
send_installation_report() {
    local status="$1"
    local python_cmd="$2"
    
    # Skip reporting if SKIP_REPORTING is set
    if [ "${SKIP_REPORTING:-0}" = "1" ]; then
        return 0
    fi
    
    # Collect system information
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local os_info=$(uname -a 2>/dev/null || echo "unknown")
    local python_version=$($python_cmd --version 2>&1 || echo "unknown")
    local script_version="1.0.0"
    
    # Create JSON payload
    local payload=$(cat << EOF
{
    "timestamp": "$timestamp",
    "status": "$status",
    "os_info": "$os_info",
    "python_version": "$python_version",
    "python_path": "$python_cmd",
    "script_version": "$script_version",
    "install_method": "curl_script"
}
EOF
    )
    
    # Try to send to Supabase endpoint (non-blocking)
    {
        if command_exists curl && [ "$REPORTING_ENDPOINT" != "https://dmgtsseqqsiyuuzhdxnn.supabase.co/rest/v1/installation_reports" ]; then
            curl -X POST "$REPORTING_ENDPOINT" \
                -H "Content-Type: application/json" \
                -H "apikey: $REPORTING_API_KEY" \
                -H "Authorization: Bearer $REPORTING_API_KEY" \
                -d "$payload" \
                --connect-timeout 5 \
                --max-time 10 \
                --silent \
                --show-error 2>/dev/null || true
        fi
    } &
    
    # Also log locally for debugging
    echo "$payload" >> ~/.rebrowse_install.log 2>/dev/null || true
}

# Create a simple usage example
create_usage_example() {
    log_info "Creating usage example..."
    
    cat > ~/rebrowse_example.py << 'EOF'
import asyncio
import base64
from pathlib import Path
from typing import Optional
from browser_use import Browser
from browser_use.browser.browser import BrowserProfile

def get_rebrowse_logo_data_url() -> Optional[str]:
    """Convert the local rebrowse.png to a data URL for use in the browser"""
    try:
        # Try multiple potential locations for rebrowse.png
        possible_paths = [
            Path("rebrowse.png"),  # Current directory
            Path("../rebrowse.png"),  # Parent directory
            Path("../../rebrowse.png"),  # Project root
            Path(__file__).parent / "rebrowse.png",  # Same as script
            Path(__file__).parent.parent / "rebrowse.png",  # One level up
        ]
        
        logo_path = None
        for path in possible_paths:
            if path.exists():
                logo_path = path
                break
        
        if not logo_path:
            print("ℹ️ rebrowse.png not found, using text logo")
            return None
        
        # Read the image file and convert to base64
        with open(logo_path, "rb") as image_file:
            image_data = image_file.read()
            base64_data = base64.b64encode(image_data).decode('utf-8')
            
        # Create data URL
        data_url = f"data:image/png;base64,{base64_data}"
        print(f"✅ Loaded rebrowse.png logo ({len(image_data)} bytes)")
        return data_url
        
    except Exception as e:
        print(f"ℹ️ Using text logo (rebrowse.png not available: {e})")
        return None

async def show_custom_dvd_screensaver(page, logo_url: Optional[str] = None, logo_text: str = "REBROWSE") -> None:
    """Custom simple ASCII logo screensaver"""
    # ASCII art logo for REBROWSE
    ascii_logo = """
██████╗ ███████╗██████╗ ██████╗  ██████╗ ██╗    ██╗███████╗███████╗
██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔═══██╗██║    ██║██╔════╝██╔════╝
██████╔╝█████╗  ██████╔╝██████╔╝██║   ██║██║ █╗ ██║███████╗█████╗  
██╔══██╗██╔══╝  ██╔══██╗██╔══██╗██║   ██║██║███╗██║╚════██║██╔══╝  
██║  ██║███████╗██████╔╝██║  ██║╚██████╔╝╚███╔███╔╝███████║███████╗
╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚══╝╚══╝ ╚══════╝╚══════╝
    """

    await page.evaluate(f"""() => {{
        document.title = 'Rebrowse - Setting up...';

        // Remove any existing loading animation
        const existing = document.getElementById('pretty-loading-animation');
        if (existing) existing.remove();

        // Create the main overlay
        const loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'pretty-loading-animation';
        loadingOverlay.style.position = 'fixed';
        loadingOverlay.style.top = '0';
        loadingOverlay.style.left = '0';
        loadingOverlay.style.width = '100vw';
        loadingOverlay.style.height = '100vh';
        loadingOverlay.style.background = 'linear-gradient(135deg, #ff69b4 0%, #ff1493 50%, #da70d6 100%)';
        loadingOverlay.style.zIndex = '99999';
        loadingOverlay.style.overflow = 'hidden';
        loadingOverlay.style.display = 'flex';
        loadingOverlay.style.alignItems = 'center';
        loadingOverlay.style.justifyContent = 'center';
        loadingOverlay.style.flexDirection = 'column';

        // Create the ASCII logo container
        const logoContainer = document.createElement('pre');
        logoContainer.textContent = `{ascii_logo}`;
        logoContainer.style.color = '#ffffff';
        logoContainer.style.fontFamily = 'monospace';
        logoContainer.style.fontSize = '16px';
        logoContainer.style.lineHeight = '1.2';
        logoContainer.style.textAlign = 'center';
        logoContainer.style.margin = '0';
        logoContainer.style.padding = '20px';
        logoContainer.style.textShadow = '0 0 10px rgba(255, 255, 255, 0.8), 0 0 20px rgba(255, 105, 180, 0.6)';
        logoContainer.style.animation = 'pulse 2s ease-in-out infinite';

        // Create subtitle
        const subtitle = document.createElement('div');
        subtitle.textContent = 'Setting up browser automation...';
        subtitle.style.color = '#ffffff';
        subtitle.style.fontFamily = 'Arial, sans-serif';
        subtitle.style.fontSize = '18px';
        subtitle.style.marginTop = '20px';
        subtitle.style.textAlign = 'center';
        subtitle.style.opacity = '0.9';
        subtitle.style.textShadow = '0 0 5px rgba(255, 255, 255, 0.5)';

        loadingOverlay.appendChild(logoContainer);
        loadingOverlay.appendChild(subtitle);
        document.body.appendChild(loadingOverlay);

        // Add pulse animation CSS
        const style = document.createElement('style');
        style.textContent = `
            @keyframes pulse {{
                0% {{ 
                    text-shadow: 0 0 10px rgba(255, 255, 255, 0.8), 0 0 20px rgba(255, 105, 180, 0.6);
                    transform: scale(1);
                }}
                50% {{ 
                    text-shadow: 0 0 15px rgba(255, 255, 255, 1), 0 0 30px rgba(255, 105, 180, 0.8);
                    transform: scale(1.02);
                }}
                100% {{ 
                    text-shadow: 0 0 10px rgba(255, 255, 255, 0.8), 0 0 20px rgba(255, 105, 180, 0.6);
                    transform: scale(1);
                }}
            }}
        `;
        document.head.appendChild(style);
    }}""")

def patch_browser_use_screensaver(logo_url: Optional[str] = None, logo_text: str = "REBROWSE"):
    """Monkey patch the browser-use screensaver function with our custom one"""
    try:
        from browser_use.browser.session import BrowserSession
        
        # Store the original function
        original_func = getattr(BrowserSession, '_show_dvd_screensaver_loading_animation', None)
        if original_func and not hasattr(BrowserSession, '_original_show_dvd_screensaver'):
            setattr(BrowserSession, '_original_show_dvd_screensaver', original_func)
        
        # Replace with our custom function
        async def custom_screensaver(self, page):
            await show_custom_dvd_screensaver(page, logo_url, logo_text)
        
        setattr(BrowserSession, '_show_dvd_screensaver_loading_animation', custom_screensaver)
        
        logo_info = logo_url or "rebrowse.png (auto)" if get_rebrowse_logo_data_url() else logo_text
        print(f"🌸 Custom Rebrowse screensaver enabled! Logo: {logo_info}")
        
    except ImportError as e:
        print(f"⚠️ Could not patch screensaver: {e}")
    except Exception as e:
        print(f"⚠️ Screensaver patch error: {e}")

async def example_workflow():
    """Example of using the browser for automation
    
    This demonstrates basic browser automation tasks:
    - Opening a browser with custom configuration
    - Navigating to websites
    - Extracting information (page title)
    - Taking screenshots (optional)
    - Proper cleanup
    """
    
    # Create browser with production-like settings
    profile = BrowserProfile(
        headless=False,  # Set to True for headless mode (no browser window)
        disable_security=True,  # Needed for automation, disables web security
        args=[
            '--no-sandbox',                # Required for many environments
            '--disable-dev-shm-usage',     # Overcome limited resource problems
            # '--disable-gpu',             # Uncomment for headless mode or if GPU issues
            '--disable-web-security',      # Disable web security for automation
            '--no-first-run',             # Skip first run wizards
            '--disable-extensions'         # Disable browser extensions
        ]
    )
    
    print("🚀 Starting browser automation example...")
    
    # Enable custom Rebrowse screensaver
    patch_browser_use_screensaver()
    
    browser = Browser(browser_profile=profile)
    await browser.start()
    
    try:
        page = await browser.get_current_page()
        
        # Example 1: Navigate to Rebrowse website
        print("📍 Navigating to rebrowse.me...")
        await page.goto("https://rebrowse.me")
        
        # Get page title
        title = await page.title()
        print(f"📄 Page title: {title}")
        
        # Get page URL
        url = page.url
        print(f"🔗 Current URL: {url}")
        
        # Example 2: Take a screenshot (uncomment to enable)
        # print("📸 Taking screenshot...")
        # await page.screenshot(path="rebrowse_screenshot.png")
        # print("✅ Screenshot saved as 'rebrowse_screenshot.png'")
        
        # Example 3: Extract text content (uncomment to try)
        # body_text = await page.text_content('body')
        # print(f"📝 Page contains {len(body_text)} characters")
        
        # Example 4: Navigate to another page for comparison
        print("📍 Navigating to httpbin.org...")
        await page.goto("https://httpbin.org/")
        
        new_title = await page.title()
        print(f"📄 New page title: {new_title}")
        
    except Exception as e:
        print(f"❌ Error during automation: {e}")
        return False
        
    finally:
        print("🔄 Closing browser...")
        await browser.close()
        print("✅ Browser automation completed!")
        return True

if __name__ == "__main__":
    print("=== Browser-Use Example Script ===")
    print("This script demonstrates browser automation with browser-use library")
    print()
    
    # Run the main example
    success = asyncio.run(example_workflow())
    exit(0 if success else 1)
EOF

    local python_cmd="${PYTHON3_PATH:-python3}"
    log_success "Usage example created at ~/rebrowse_example.py"
    log_info "Run it with: $python_cmd ~/rebrowse_example.py"
}

# Main installation function
main() {
    echo ""
    echo ""
    echo -e "\033[95m██████╗ ███████╗██████╗ ██████╗  ██████╗ ██╗    ██╗███████╗███████╗\033[0m"
    echo -e "\033[95m██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔═══██╗██║    ██║██╔════╝██╔════╝\033[0m"
    echo -e "\033[95m██████╔╝█████╗  ██████╔╝██████╔╝██║   ██║██║ █╗ ██║███████╗█████╗  \033[0m"
    echo -e "\033[95m██╔══██╗██╔══╝  ██╔══██╗██╔══██╗██║   ██║██║███╗██║╚════██║██╔══╝  \033[0m"
    echo -e "\033[95m██║  ██║███████╗██████╔╝██║  ██║╚██████╔╝╚███╔███╔╝███████║███████╗\033[0m"
    echo -e "\033[95m╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚══╝╚══╝ ╚══════╝╚══════╝\033[0m"
    echo ""
    echo ""
    echo "🚀 Chromium Setup"
    echo "========================================"
    echo ""
    
    # Detect OS
    OS=$(detect_os)
    log_info "Detected OS: $OS"
    
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
    
    # Check Python version after potential installation/upgrade
    if ! check_python_version; then
        echo ""
        log_error "❌ Python version check failed!"
        echo ""
        echo "Solutions:"
        case $OS in
            "macos")
                echo "1. The script attempted to install Python 3.11, but it may not be the default."
                echo "2. Try running: brew install python@3.11"
                echo "3. Then add to your shell profile: export PATH=\"/opt/homebrew/bin:\$PATH\""
                echo "4. Restart your terminal and run: python3.11 --version"
                echo "5. Re-run this script"
                ;;
            "linux")
                echo "1. Install Python 3.11+: sudo apt install python3.11 python3.11-pip"
                echo "2. Or use pyenv to manage Python versions"
                echo "3. Make sure python3 points to version 3.11+"
                ;;
        esac
        echo ""
        exit 1
    fi
    
    # Install Python dependencies
    install_python_deps
    
    # Install Playwright browsers
    install_playwright_browsers
    
    # Verify installation
    if verify_installation; then
        create_usage_example
        
        echo ""
        local python_cmd="${PYTHON3_PATH:-python3}"
        log_success "🎉 Installation completed successfully!"
        echo ""
        
        # Auto-run the example to demonstrate functionality (unless skipped)
        if [ "${SKIP_DEMO:-0}" != "1" ]; then
            log_info "🚀 Running example demonstration..."
            echo "This will show browser automation in action!"
            echo ""
            echo "👀 Watch for:"
            echo "  - 🌸 Pink bouncing REBROWSE screensaver with sparkles"
            echo "  - Browser window opening"
            echo "  - Navigation to rebrowse.me and httpbin.org"
            echo "  - Page titles being extracted"
            echo ""
            echo "💡 To skip this demo next time, use: SKIP_DEMO=1 curl ... | bash"
            echo ""
            sleep 2
            
            if $python_cmd ~/rebrowse_example.py; then
                echo ""
                log_success "✨ Example demonstration completed successfully!"
                echo "🎯 Everything is working perfectly!"
                
                # Send success report
                send_installation_report "success" "$python_cmd"
            else
                echo ""
                log_warning "⚠️ Example demonstration had issues, but basic installation is complete"
                
                # Send partial success report
                send_installation_report "example_failed" "$python_cmd"
            fi
        else
            log_info "📋 Demo skipped (SKIP_DEMO=1)"
            
            # Send success report without demo
            send_installation_report "success_no_demo" "$python_cmd"
        fi
        
        echo ""
        echo "🎉 Installation & Demo Complete!"
        echo "================================="
        echo ""
        echo "What just happened:"
        echo "✅ Python 3.11+ installed and configured"
        echo "✅ browser-use package installed"
        echo "✅ Playwright Chromium browser installed"
        echo "✅ Example script created and tested"
        echo ""
        echo "Next steps:"
        echo "1. 🎯 You're all set!"
        echo "2. 🤖 For headless mode, set headless=True in the BrowserProfile"
        echo "3. 🗣️ Get support on Telegram: https://t.me/n0rixpunks"
        echo ""
        echo "Files created:"
        echo "- ~/rebrowse_example.py (your starting template)"
        echo "- ~/.rebrowse_install.log (installation log)"
        echo ""
        echo "Troubleshooting:"
        echo "- Re-run example: $python_cmd ~/rebrowse_example.py"
        echo "- For headless issues: uncomment --disable-gpu in the script"
        echo "- Python path: $python_cmd"
        echo ""
    else
        log_error "Installation verification failed. Please check the errors above."
        
        # Send failure report
        send_installation_report "failed" "${PYTHON3_PATH:-python3}"
        exit 1
    fi
}

# Run main function
main "$@" 