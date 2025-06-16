# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV RAILWAY_ENVIRONMENT=production
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

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
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Upgrade pip and install wheel
RUN pip install --upgrade pip setuptools wheel

# Install packages one by one to identify issues
RUN pip install fastapi>=0.115.0
RUN pip install "uvicorn[standard]>=0.34.0"
RUN pip install supabase>=2.15.0
RUN pip install aiofiles>=24.1.0
RUN pip install aiohttp>=3.12.0
RUN pip install fastmcp>=2.3.4
RUN pip install typer>=0.15.0
RUN pip install gotrue>=1.0.0
RUN pip install PyJWT>=2.8.0
RUN pip install python-dotenv>=1.0.0
RUN pip install browser-use>=0.2.4

# Install Playwright and browsers (CRITICAL for browser-use)
RUN pip install playwright>=1.40.0
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
# Optionally run verification before starting the server
CMD python verify_playwright.py && xvfb-run -a -s '-screen 0 1920x1080x24' python -m uvicorn backend.api:app --host 0.0.0.0 --port ${PORT:-8000} 