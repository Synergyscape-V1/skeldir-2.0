#!/bin/bash

# Skeldir 2.0 - Native Prism Mock Server Stop Script
# Stops all running Prism mock servers (ports 4010-4018)

echo "=============================================="
echo "  Skeldir 2.0 - Stop Prism Mock Servers"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# PID file directory
PID_DIR="/tmp/skeldir-mocks"

# Ports to check
PORTS=(4010 4011 4012 4013 4014 4015 4016 4017 4018)

stopped_count=0
not_running_count=0

# Function to stop a server by port
stop_server() {
    local port=$1
    local pid_file="$PID_DIR/prism_$port.pid"
    
    # Try to get PID from file first
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 $pid 2>/dev/null; then
            echo -e "${GREEN}→ Stopping process on port $port (PID: $pid)${NC}"
            kill $pid 2>/dev/null
            rm -f "$pid_file"
            ((stopped_count++))
            return 0
        fi
        rm -f "$pid_file"
    fi
    
    # Fallback: Find process by port
    local pids=$(lsof -t -i :$port 2>/dev/null)
    if [ -n "$pids" ]; then
        echo -e "${GREEN}→ Stopping process on port $port (PIDs: $pids)${NC}"
        echo $pids | xargs kill 2>/dev/null
        ((stopped_count++))
    else
        echo -e "${YELLOW}○ No process running on port $port${NC}"
        ((not_running_count++))
    fi
}

# Stop all mock servers
echo "Stopping mock servers..."
echo ""

for port in "${PORTS[@]}"; do
    stop_server $port
done

echo ""
echo "=============================================="
echo -e "${GREEN}Summary:${NC}"
echo "  Stopped:     $stopped_count servers"
echo "  Not running: $not_running_count ports"
echo ""

# Clean up log files (optional)
if [ -d "$PID_DIR" ]; then
    echo "Cleaning up log files..."
    rm -f "$PID_DIR"/*.log
    echo -e "${GREEN}✓ Log files cleaned${NC}"
fi

echo ""
echo "All Prism mock servers stopped."
echo "=============================================="
