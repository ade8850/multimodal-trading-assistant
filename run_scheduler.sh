#!/bin/bash
# run_scheduler.sh

# Stop script if any command fails
set -e

# Function to check if a string is empty
is_empty() {
    local var=$1
    [ -z "$var" ]
}

# Load environment variables
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    exit 1
fi

# Source the .env file
source .env

# Check required variables
required_vars=(
    "BYBIT_API_KEY"
    "BYBIT_API_SECRET"
)

# Add AI provider check
if [ -n "$ANTHROPIC_API_KEY" ]; then
    AI_PROVIDER_KEY="ANTHROPIC_API_KEY"
elif [ -n "$GEMINI_API_KEY" ]; then
    AI_PROVIDER_KEY="GEMINI_API_KEY"
elif [ -n "$OPENAI_API_KEY" ]; then
    AI_PROVIDER_KEY="OPENAI_API_KEY"
else
    echo "Error: No AI provider API key found in .env!"
    exit 1
fi
required_vars+=("$AI_PROVIDER_KEY")

# Verify all required variables are set
for var in "${required_vars[@]}"; do
    if is_empty "${!var}"; then
        echo "Error: Required environment variable $var is not set!"
        exit 1
    fi
done

# Check for config.yaml
if [ ! -f scheduler_config.yaml ]; then
    echo "Error: scheduler_config.yaml not found!"
    exit 1
fi

# Create necessary directories and files
echo "Setting up directories and files..."
mkdir -p .graphs
mkdir -p .logs
touch .logs/scheduler.log

# Build the container
echo "Building scheduler container..."
docker build -f scheduler.Dockerfile -t trading-scheduler .

# Stop any existing container
echo "Stopping existing scheduler container (if any)..."
docker stop trading-scheduler 2>/dev/null || true
docker rm trading-scheduler 2>/dev/null || true

# Run the container
echo "Starting scheduler container..."
docker run -d \
    --name trading-scheduler \
    --restart unless-stopped \
    -v "$(pwd)/scheduler_config.yaml:/app/config.yaml:ro" \
    -v "$(pwd)/.logs/scheduler.log:/app/scheduler.log" \
    -v "$(pwd)/.graphs:/app/.graphs" \
    -e BYBIT_API_KEY="$BYBIT_API_KEY" \
    -e BYBIT_API_SECRET="$BYBIT_API_SECRET" \
    -e BYBIT_TESTNET="${BYBIT_TESTNET:-False}" \
    -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
    -e GEMINI_API_KEY="${GEMINI_API_KEY:-}" \
    -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
    -e DUMP_CHARTS="${DUMP_CHARTS:-False}" \
    -e CONFIG_PATH="/app/config.yaml" \
    trading-scheduler

# Wait a moment for the container to start
sleep 2

# Check container status and logs
container_status=$(docker ps -f name=trading-scheduler --format '{{.Status}}')
if [[ $container_status == *"Up"* ]]; then
    echo "Scheduler container started successfully!"
    echo "View logs with: docker logs -f trading-scheduler"
    echo "Log file location: .logs/scheduler.log"
    echo "Charts directory: .graphs/"
else
    echo "Error: Container failed to start properly."
    docker logs trading-scheduler
    exit 1
fi