#!/usr/bin/env bash
# Deploy humidifier driver to Raspberry Pi
# Usage: ./deploy.sh [pi-host] [user] [password] [remote-path]

set -euo pipefail

PI_HOST="${1:-pi410}"
PI_USER="${2:-pi}"
PI_PASS="${3:-raspberry}"
REMOTE_PATH="${4:-/home/pi/Desktop/humidifier}"
LOCAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# Check sshpass
if ! command -v sshpass &> /dev/null; then
    echo -e "${RED}sshpass not found. Install: sudo apt install sshpass  OR  brew install sshpass${NC}"
    exit 1
fi

SSH="sshpass -p '$PI_PASS' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $PI_USER@$PI_HOST"
SCP="sshpass -p '$PI_PASS' scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r"

echo -e "${CYAN}=== Deploying to $PI_USER@$PI_HOST:$REMOTE_PATH ===${NC}"

echo -e "${GREEN}Copying files...${NC}"
eval "$SCP '$LOCAL_ROOT/driver' $PI_USER@$PI_HOST:$REMOTE_PATH/"
eval "$SCP '$LOCAL_ROOT/example_usage.py' $PI_USER@$PI_HOST:$REMOTE_PATH/"

echo -e "${GREEN}Installing dependencies on Pi...${NC}"
eval "$SSH 'sudo apt update && sudo apt install -y python3-gpiozero python3-pigpio'"

echo -e "${GREEN}Starting pigpiod...${NC}"
eval "$SSH 'sudo systemctl enable pigpiod && sudo systemctl start pigpiod'"

echo -e "${GREEN}Running example on Pi...${NC}"
eval "$SSH 'cd $REMOTE_PATH && python3 example_usage.py'"

echo -e "${CYAN}Done.${NC}"