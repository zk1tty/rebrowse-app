#!/bin/bash

# Rebrowse Docker Setup Script
echo "🚀 Setting up Rebrowse with Docker..."

# Parse command line arguments
SELF_HOST=false
for arg in "$@"; do
    case $arg in
        --self-host)
            SELF_HOST=true
            shift
            ;;
        *)
            # unknown option
            ;;
    esac
done

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

# Function to load variables from project root .env file
load_root_env() {
    local root_env_file=".env"
    
    if [ -f "$root_env_file" ]; then
        echo "📂 Loading variables from project root .env file..."
        set -a
        source "$root_env_file"
        set +a
        return 0
    else
        echo "⚠️  No .env file found in project root"
        return 1
    fi
}

# Function to validate and get variable with fallback
get_env_var() {
    local var_name="$1"
    local fallback_value="$2"
    local current_value="${!var_name}"
    
    if [ -n "$current_value" ] && [ "$current_value" != "$fallback_value" ]; then
        echo "✅ Found $var_name in project root .env file" >&2
        echo "$current_value"
    else
        echo "⚠️  $var_name not found or not set in project root .env file" >&2
        echo "$fallback_value"
    fi
}

# Load variables from project root .env
if load_root_env; then
    # Get all required variables with fallbacks
    OPENAI_API_KEY=$(get_env_var "OPENAI_API_KEY" "your_openai_api_key_here")
    SUPABASE_URL=$(get_env_var "SUPABASE_URL" "https://your_project_id.supabase.co")
    SUPABASE_ANON_KEY=$(get_env_var "SUPABASE_ANON_KEY" "your_supabase_anon_key_here")
    SUPABASE_SERVICE_ROLE_KEY=$(get_env_var "SUPABASE_SERVICE_ROLE_KEY" "your_supabase_service_role_key_here")
    SUPABASE_JWT_SECRET=$(get_env_var "SUPABASE_JWT_SECRET" "your_supabase_jwt_secret_here")
else
    # Set fallback values if no .env file exists
    OPENAI_API_KEY="your_openai_api_key_here"
    SUPABASE_URL="https://your_project_id.supabase.co"
    SUPABASE_ANON_KEY="your_supabase_anon_key_here"
    SUPABASE_SERVICE_ROLE_KEY="your_supabase_service_role_key_here"
    SUPABASE_JWT_SECRET="your_supabase_jwt_secret_here"
fi

# Function to check if .env file has all required variables
check_env_completeness() {
    local env_file="$1"
    local missing_vars=()
    
    # Check each required variable
    if ! grep -q "^OPENAI_API_KEY=" "$env_file" 2>/dev/null; then
        missing_vars+=("OPENAI_API_KEY")
    fi
    
    if ! grep -q "^SUPABASE_URL=" "$env_file" 2>/dev/null; then
        missing_vars+=("SUPABASE_URL")
    fi
    
    if ! grep -q "^SUPABASE_ANON_KEY=" "$env_file" 2>/dev/null; then
        missing_vars+=("SUPABASE_ANON_KEY")
    fi
    
    if ! grep -q "^SUPABASE_SERVICE_ROLE_KEY=" "$env_file" 2>/dev/null; then
        missing_vars+=("SUPABASE_SERVICE_ROLE_KEY")
    fi
    
    if ! grep -q "^SUPABASE_JWT_SECRET=" "$env_file" 2>/dev/null; then
        missing_vars+=("SUPABASE_JWT_SECRET")
    fi
    
    # Return missing variables
    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo "${missing_vars[*]}"
        return 1
    else
        return 0
    fi
}

# Function to generate self-host .env file
generate_self_host_env() {
    echo "🔑 Generating Supabase API keys for self-hosting..."
    
    # Use a fixed JWT secret for demo mode to ensure signature consistency
    JWT_SECRET="g29OUlUz2TQw7q4ycKU7jKUN7Z94gpfeOcdWb0Aj"
    
    # These tokens are properly signed with the JWT_SECRET above
    ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlIiwiaWF0IjoxNzU0MjQ1ODAwLCJleHAiOjE5MTIwMTIyMDB9.n5yrM4T-zF_5bMilf-so1zIYRd7iWZfwU8d8-kVH2Gs"
    SERVICE_ROLE_KEY="REMOVED"
    
    echo "🔑 Using consistent JWT secret and properly signed tokens"
    echo "🔑 JWT_SECRET: $JWT_SECRET"
    
    cat > docker/.env << EOF
# Rebrowse Self-Hosting Configuration
# Generated automatically for enterprise demos

# OpenAI Configuration
OPENAI_API_KEY=${OPENAI_API_KEY}

# Supabase Self-Hosted Configuration (using Docker container networking)  
# Simple fix: Since Supabase client adds '/rest/v1', we provide base URL
# Client will call: http://supabase-rest:3000/rest/v1/workflows
# But PostgREST serves at: http://supabase-rest:3000/workflows  
# So we need to make PostgREST handle the /rest/v1 prefix
SUPABASE_URL=http://supabase-rest:80
SUPABASE_ANON_KEY=${ANON_KEY}
SUPABASE_SERVICE_ROLE_KEY=${SERVICE_ROLE_KEY}
SUPABASE_JWT_SECRET=${JWT_SECRET}

# UI Environment Variables (browser-accessible URLs)
VITE_PUBLIC_SUPABASE_URL=http://localhost:8001
VITE_PUBLIC_SUPABASE_ANON_KEY=${ANON_KEY}

# Database Configuration
POSTGRES_PASSWORD=your-super-secret-and-long-postgres-password
POSTGRES_DB=postgres
POSTGRES_PORT=5432

# PostgREST Configuration  
JWT_SECRET=${JWT_SECRET}
EOF
    
    # Copy .env to docker directory for Supabase services
    cp .env docker/.env
    
    echo "✅ Generated self-hosting configuration with secure API keys"
    echo "🔑 JWT_SECRET: ${JWT_SECRET}"
    echo "🌐 SUPABASE_URL: http://supabase-rest:3000 (container network)"
    echo ""
    if [ "$OPENAI_API_KEY" = "your_openai_api_key_here" ]; then
        echo "⚠️  IMPORTANT: Update OPENAI_API_KEY in project root .env file"
    else
        echo "✅ Using OPENAI_API_KEY from project root .env file"
    fi
}

# Function to generate production .env file
generate_production_env() {
    echo "📝 Creating .env file template for production..."
    cat > docker/.env << EOF
# Rebrowse Production Configuration

# OpenAI Configuration
OPENAI_API_KEY=${OPENAI_API_KEY}

# Supabase Production Configuration
SUPABASE_URL=${SUPABASE_URL}
SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET}
EOF
    echo "✅ Created production .env file template."
    echo "📋 Required credentials:"
    echo "   - OpenAI API Key: https://platform.openai.com/api-keys"
    echo "   - Supabase credentials: https://supabase.com/dashboard"
    echo ""
    missing_vars=$(check_env_completeness .env)
    if [ $? -eq 0 ]; then
        echo "✅ Using all variables from project root .env file"
    else
        echo "⚠️  Missing variables in project root .env file: $missing_vars"
        echo "Please update the project root .env file with your actual credentials before continuing."
        exit 1
    fi
}

# ======= Main ======= #
# Generate appropriate .env file based on mode
if [ "$SELF_HOST" = true ]; then
    generate_self_host_env
elif [ ! -f .env ]; then
    generate_production_env
fi

# Load environment variables
if [ -f .env ]; then
    set -a  # Mark variables for export
    source .env
    set +a  # Unmark variables for export
    echo "✅ Environment variables loaded from .env"
else
    echo "❌ .env file not found"
    exit 1
fi

# Validate environment for production mode
if [ "$SELF_HOST" = false ]; then
    missing_vars=$(check_env_completeness .env)
    if [ $? -ne 0 ]; then
        echo "❌ Missing variables in project root .env file: $missing_vars"
        echo "📋 Required variables:"
        echo "   - OPENAI_API_KEY"
        echo "   - SUPABASE_URL"
        echo "   - SUPABASE_ANON_KEY"
        echo "   - SUPABASE_SERVICE_ROLE_KEY"
        echo "   - SUPABASE_JWT_SECRET"
        exit 1
    fi
fi

echo "✅ Environment variables configured."

# Build and start containers
if [ "$SELF_HOST" = true ]; then
    echo "🔨 Building and starting self-hosted PostgreSQL + PostgREST + Rebrowse..."
    echo "📦 Starting Supabase services (PostgreSQL + PostgREST + Adminer)..."
    cd docker && docker compose -f compose.supabase.yaml up -d
    cd ..
    
    echo "⏳ Waiting for services to be ready..."
    sleep 15
    
    echo "📦 Starting Rebrowse application..."
    docker compose -f docker/compose.yaml up -d --build
    
    echo "✅ Self-hosted Rebrowse is ready!"
    echo "🌐 Frontend: http://localhost:5173"
    echo "🔧 Backend API: http://localhost:8000"
    echo "🗄️  Database Admin: http://localhost:3001"
    echo "🔗 Database API (PostgREST): http://localhost:8001"
    echo ""
    echo "📊 Check status:"
    echo "   Rebrowse: docker compose -f docker/compose.yaml ps"
    echo "   Database: cd docker && docker compose -f compose.supabase.yaml ps"
    echo ""
    echo "🛑 Stop services:"
    echo "   Rebrowse: docker compose -f docker/compose.yaml down"
    echo "   Database: cd docker && docker compose -f compose.supabase.yaml down"
else
    echo "🔨 Building and starting containers with production Supabase..."
    docker compose -f docker/compose.yaml up -d --build
    
    echo "✅ Rebrowse is starting up!"
    echo "🌐 Frontend: http://localhost:5173"
    echo "🔧 Backend API: http://localhost:8000"
    echo ""
    echo "📊 Check container status: docker compose -f docker/compose.yaml ps"
    echo "📋 View logs: docker compose -f docker/compose.yaml logs -f"
    echo "🛑 Stop services: docker compose -f docker/compose.yaml down"
fi 