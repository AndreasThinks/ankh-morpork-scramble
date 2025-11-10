#!/bin/bash
# Test script for async MCP server setup

set -e

echo "=== Testing Async MCP Server Setup ==="
echo ""

# Start FastAPI game server on port 8000
echo "Starting FastAPI game server on port 8000..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
FASTAPI_PID=$!
sleep 3

# Start async MCP server on port 8001
echo "Starting async MCP server on port 8001..."
python -m app.mcp_async_server &
MCP_PID=$!
sleep 3

echo ""
echo "=== Servers Started ==="
echo "FastAPI server PID: $FASTAPI_PID (port 8000)"
echo "MCP server PID: $MCP_PID (port 8001)"
echo ""

# Test FastAPI endpoint
echo "Testing FastAPI server..."
curl -s http://localhost:8000/ | jq .

echo ""
echo "=== Setup Complete ==="
echo "FastAPI game server: http://localhost:8000"
echo "Async MCP server: http://localhost:8001"
echo ""
echo "To stop servers:"
echo "  kill $FASTAPI_PID $MCP_PID"
echo ""
echo "Or press Ctrl+C to stop both servers"

# Wait for interrupt
wait
