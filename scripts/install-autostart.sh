#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$PROJECT_DIR/frontend"
DATA_DIR="$PROJECT_DIR/data"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

# Dynamically resolve node from nvm or system
NODE_BIN="$(which node 2>/dev/null || echo '')"
if [ -z "$NODE_BIN" ] && [ -f "$HOME/.nvm/nvm.sh" ]; then
    NODE_BIN="$HOME/.nvm/versions/node/$(ls "$HOME/.nvm/versions/node/" | sort -V | tail -1)/bin/node"
fi

if [ ! -f "$PYTHON_BIN" ]; then
    echo "Error: virtualenv .venv not found at $PROJECT_DIR/.venv"
    echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

if [ ! -f "$NODE_BIN" ]; then
    echo "Error: node not found. Please install Node.js."
    exit 1
fi

echo "==> Installing Crypto Research Agent services..."
echo "    Project:  $PROJECT_DIR"
echo "    Python:   $PYTHON_BIN"
echo "    Node:     $NODE_BIN"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$DATA_DIR"

VITE_BIN="$FRONTEND_DIR/node_modules/.bin/vite"
NPM_BIN="$(dirname "$NODE_BIN")/npm"

if [ ! -f "$VITE_BIN" ]; then
    echo "==> Installing frontend dependencies..."
    cd "$FRONTEND_DIR" && "$NPM_BIN" ci
fi

# ---- Backend plist ----
cat > "$HOME/Library/LaunchAgents/com.crypto-research-agent.backend.plist" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.crypto-research-agent.backend</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>-m</string>
        <string>backend.server</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>5</integer>
    <key>StandardOutPath</key>
    <string>$DATA_DIR/server.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$DATA_DIR/server.stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
PLIST_EOF

# ---- Frontend plist ----
NODE_DIR="$(dirname "$NODE_BIN")"
cat > "$HOME/Library/LaunchAgents/com.crypto-research-agent.frontend.plist" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.crypto-research-agent.frontend</string>
    <key>ProgramArguments</key>
    <array>
        <string>$NODE_BIN</string>
        <string>$VITE_BIN</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$FRONTEND_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>5</integer>
    <key>StandardOutPath</key>
    <string>$DATA_DIR/frontend.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$DATA_DIR/frontend.stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$NODE_DIR:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
PLIST_EOF

echo "    Plists:  $HOME/Library/LaunchAgents/"

# Stop any existing instances
lsof -i :8000 -t 2>/dev/null | xargs kill 2>/dev/null || true
lsof -i :5173 -t 2>/dev/null | xargs kill 2>/dev/null || true

# Unload old plists
launchctl unload "$HOME/Library/LaunchAgents/com.crypto-research-agent.backend.plist" 2>/dev/null || true
launchctl unload "$HOME/Library/LaunchAgents/com.crypto-research-agent.frontend.plist" 2>/dev/null || true
# Clean up old single-service plist
launchctl unload "$HOME/Library/LaunchAgents/com.crypto-research-agent.plist" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/com.crypto-research-agent.plist"
rm -rf "$HOME/Applications/CryptoResearchAgent.app" 2>/dev/null || true

# Load new plists
launchctl load "$HOME/Library/LaunchAgents/com.crypto-research-agent.backend.plist"
launchctl load "$HOME/Library/LaunchAgents/com.crypto-research-agent.frontend.plist"

sleep 3

BACKEND_OK=false
FRONTEND_OK=false

curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1 && BACKEND_OK=true
lsof -i :5173 > /dev/null 2>&1 && FRONTEND_OK=true

echo ""
if $BACKEND_OK && $FRONTEND_OK; then
    echo "Done. Both services are running and will auto-start on login."
    echo ""
    echo "  Open:    http://localhost:5173/"
    echo "  Health:  curl http://127.0.0.1:8000/health"
    echo "  Logs:    tail -f '$DATA_DIR/server.stdout.log'"
    echo "  Remove:  $PROJECT_DIR/scripts/uninstall-autostart.sh"
else
    echo "WARNING: Some services failed to start."
    $BACKEND_OK && echo "  Backend:  OK"
    $BACKEND_OK || echo "  Backend:  FAILED (check $DATA_DIR/server.stderr.log)"
    $FRONTEND_OK && echo "  Frontend: OK"
    $FRONTEND_OK || echo "  Frontend: FAILED (check $DATA_DIR/frontend.stderr.log)"
    exit 1
fi
