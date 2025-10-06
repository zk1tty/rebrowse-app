#!/bin/bash

echo "🐳 Testing Docker Build for WF Backend"
echo "======================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

echo "✅ Docker is running"

# Build with progress output
echo "🔨 Building Docker image..."
docker build -t wf-backend:test . --progress=plain

if [ $? -eq 0 ]; then
    echo "✅ Docker image built successfully"
    
    # Show image info
    echo "📋 Image details:"
    docker images wf-backend:test
    
    echo ""
    echo "🚀 To run the container:"
    echo "docker run -p 8000:8000 \\"
    echo "  -e OPENAI_API_KEY=your_key \\"
    echo "  -e SUPABASE_URL=your_url \\"
    echo "  -e SUPABASE_ANON_KEY=your_key \\"
    echo "  -e SUPABASE_JWT_SECRET=your_secret \\"
    wf-backend:test
    
    echo ""
    echo "🔧 Or use docker-compose:"
    echo "docker-compose up --build"
    
else
    echo "❌ Docker build failed"
    exit 1
fi
