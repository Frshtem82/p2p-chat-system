#!/usr/bin/env bash
# Run STUN server + 2 terminal peers in separate terminals.
# Usage: ./scripts/run_all.sh
#
# This script tries to detect your terminal emulator.
# On macOS: uses Terminal.app via osascript.
# On Linux: tries gnome-terminal, konsole, xterm, etc.

set -e

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT"

# Colors
G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; N='\033[0m'

echo -e "${G}[+]${N} Starting P2P Chat System from: $ROOT"

# ─── Detect OS ──────────────────────────────────────────────────────────────
OS="$(uname -s)"

open_terminal() {
    local title="$1"; shift
    local cmd="$*"
    
    case "$OS" in
        Darwin)
            osascript <<EOF
tell application "Terminal"
    do script "cd '$ROOT' && $cmd"
    activate
end tell
EOF
            ;;
        Linux)
            if command -v gnome-terminal &>/dev/null; then
                gnome-terminal --title="$title" -- bash -c "cd '$ROOT' && $cmd; exec bash"
            elif command -v konsole &>/dev/null; then
                konsole --new-tab -p tabtitle="$title" -e bash -c "cd '$ROOT' && $cmd; exec bash"
            elif command -v xfce4-terminal &>/dev/null; then
                xfce4-terminal --title="$title" -e "bash -c \"cd '$ROOT' && $cmd; exec bash\""
            elif command -v xterm &>/dev/null; then
                xterm -title "$title" -e bash -c "cd '$ROOT' && $cmd; exec bash" &
            else
                echo -e "${R}[-]${N} No supported terminal emulator found."
                echo -e "${Y}[!]${N} Run these commands manually in separate terminals:"
                echo "    python -m stun_server.server --no-redis"
                echo "    python -m peer.peer"
                echo "    python -m peer.peer"
                exit 1
            fi
            ;;
        *)
            echo -e "${R}[-]${N} Unsupported OS: $OS"
            exit 1
            ;;
    esac
}

# ─── Launch ─────────────────────────────────────────────────────────────────
open_terminal "STUN Server" "python -m stun_server.server --no-redis"
sleep 2

open_terminal "Peer 1 (alice)" "python -m peer.peer"
open_terminal "Peer 2 (bob)"   "python -m peer.peer"

echo -e "${G}[+]${N} All services launched."
echo -e "${Y}[!]${N} In each peer terminal, enter:"
echo "        alice / 9000 / http://localhost:8000"
echo "        bob   / 9001 / http://localhost:8000"