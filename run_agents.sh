#!/bin/bash
# Ankh-Morpork Scramble - Agent Launch Script
# Automates game creation and agent deployment

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default game ID
GAME_ID="${1:-friendly}"

# Function to print colored messages
print_status() {
    echo -e "${BLUE}[*]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Function to cleanup on exit
cleanup() {
    print_status "Cleaning up..."
    
    # Kill agents if running
    if [ ! -z "$AGENT_PID" ]; then
        print_status "Stopping agents (PID: $AGENT_PID)..."
        kill $AGENT_PID 2>/dev/null || true
    fi
    
    # Optionally kill server (commented out - you might want to keep it running)
    # if [ ! -z "$SERVER_PID" ]; then
    #     print_status "Stopping game server (PID: $SERVER_PID)..."
    #     kill $SERVER_PID 2>/dev/null || true
    # fi
    
    print_success "Cleanup complete"
    exit 0
}

# Trap CTRL+C and cleanup
trap cleanup SIGINT SIGTERM

# Banner
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║        Ankh-Morpork Scramble - Agent Launcher             ║"
echo "║          Two AI Teams Battle for Victory!                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Load environment variables
print_status "Loading environment from .env file..."
if [ ! -f .env ]; then
    print_error ".env file not found!"
    print_status "Copy .env.example to .env and configure your API key"
    exit 1
fi

# Load .env file
set -a
source .env
set +a

print_success "Environment loaded"

# Step 2: Validate required variables
print_status "Validating configuration..."

if [ -z "$OPENROUTER_API_KEY" ]; then
    print_error "OPENROUTER_API_KEY not set in .env file"
    exit 1
fi

if [ -z "$OPENROUTER_MODEL" ]; then
    print_warning "OPENROUTER_MODEL not set, using default"
    export OPENROUTER_MODEL="openrouter/auto"
fi

print_success "API Key: ${OPENROUTER_API_KEY:0:12}..."
print_success "Model: $OPENROUTER_MODEL"
print_success "Game ID: $GAME_ID"

# Step 3: Check if game server is running
print_status "Checking game server status..."

if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    print_success "Game server is already running"
    SERVER_PID=$(pgrep -f "uvicorn app.main:app" | head -1)
else
    print_status "Starting game server..."
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/game_server_$GAME_ID.log 2>&1 &
    SERVER_PID=$!
    
    # Wait for server to be ready
    print_status "Waiting for server to start..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
            print_success "Game server started (PID: $SERVER_PID)"
            break
        fi
        sleep 1
        if [ $i -eq 30 ]; then
            print_error "Server failed to start. Check /tmp/game_server_$GAME_ID.log"
            exit 1
        fi
    done
fi

# Step 4: Create game
print_status "Creating game '$GAME_ID'..."

RESPONSE=$(curl -s -X POST "http://localhost:8000/game?game_id=$GAME_ID" 2>&1)

if echo "$RESPONSE" | grep -q "game_id"; then
    print_success "Game created successfully"
elif echo "$RESPONSE" | grep -q "already exists"; then
    print_warning "Game already exists, using existing game"
else
    print_error "Failed to create game: $RESPONSE"
    exit 1
fi

# Get game state to confirm
GAME_STATE=$(curl -s "http://localhost:8000/game/$GAME_ID")
PHASE=$(echo "$GAME_STATE" | grep -o '"phase":"[^"]*"' | cut -d'"' -f4)
print_success "Game phase: $PHASE"

# Step 5: Launch agents
echo ""
print_status "Launching AI agents..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Team 1: City Watch Constables"
echo "  Team 2: Unseen University Wizards"
echo "  "
echo "  The agents will:"
echo "    1. Join the game"
echo "    2. Build their rosters (1M gold each)"
echo "    3. Place players strategically"
echo "    4. Play until someone wins!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

print_status "Watch the game at: http://localhost:8000/ui"
echo ""

# Launch agents with environment
uv run python -m app.agents.langgraph.launch \
    --game-id "$GAME_ID" \
    --poll-interval 2.0 &

AGENT_PID=$!

print_success "Agents launched (PID: $AGENT_PID)"
echo ""
print_status "Agent output below (Press CTRL+C to stop):"
echo ""

# Wait for agents to complete
wait $AGENT_PID

# Done
print_success "Match complete!"
print_status "View final results at: http://localhost:8000/game/$GAME_ID"
print_status "Game logs saved to: logs/games/$GAME_ID/"
