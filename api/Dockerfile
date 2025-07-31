# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV RAILWAY_ENVIRONMENT=production
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV CHROME_DEVEL_SANDBOX=/usr/bin/chromium-browser
ENV DBUS_SESSION_BUS_ADDRESS=/dev/null

# Install system dependencies including build tools
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    xvfb \
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    ca-certificates \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    libffi-dev \
    libssl-dev \
    pkg-config \
    curl \
    dbus-x11 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libcups2 \
    libxss1 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Upgrade pip and install wheel
RUN pip install --upgrade pip setuptools wheel

# Install packages one by one to identify issues
RUN pip install fastapi==0.115.12
RUN pip install "uvicorn[standard]==0.34.3"
RUN pip install supabase==2.15.3
RUN pip install aiofiles==24.1.0
RUN pip install aiohttp==3.12.13
RUN pip install fastmcp==2.8.1
RUN pip install typer==0.16.0
RUN pip install gotrue==2.12.0
RUN pip install PyJWT==2.10.1
RUN pip install python-dotenv==1.1.0
RUN pip install browser-use==0.2.7
RUN pip install langchain-openai==0.3.21
RUN pip install langchain-core==0.3.64
RUN pip install langchain==0.3.25
RUN pip install requests==2.32.4
RUN pip install pyperclip==1.9.0
RUN pip install orjson==3.10.18
RUN pip install patchright==1.52.5
RUN pip install websockets==14.2
RUN pip install psutil==7.0.0
RUN pip install asyncio-mqtt==0.16.2
RUN pip install python-json-logger==3.3.0
RUN pip install "pydantic[email]==2.11.7"

# Install Playwright and browsers (CRITICAL for browser-use)
RUN pip install playwright==1.52.0
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY . .

# Create tmp directory for workflows
RUN mkdir -p tmp/logs

# Make verification script executable
RUN chmod +x verify_playwright.py

# Expose port (Railway will set PORT env var)
EXPOSE $PORT

# Start command with virtual display and dynamic port
# Run verification before starting the server (continues even with warnings)
CMD python verify_playwright.py && xvfb-run -a -s '-screen 0 1920x1080x24' python -m uvicorn backend.api:app --host 0.0.0.0 --port ${PORT:-8000} 