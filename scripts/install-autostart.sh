#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_TARGET="$HOME/Library/LaunchAgents/com.crypto-research-agent.plist"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

if [ ! -f "$PYTHON_BIN" ]; then
    echo "Error: virtualenv .venv not found at $PROJECT_DIR/.venv"
    echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

echo "==> Installing Crypto Research Agent as a launchd service..."
echo "    Project: $PROJECT_DIR"
echo "    Python:  $PYTHON_BIN"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$PROJECT_DIR/data"

cat > "$PLIST_TARGET" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.crypto-research-agent</string>

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
    <string>$PROJECT_DIR/data/server.stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/data/server.stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
PLIST_EOF

echo "    Plist:   $PLIST_TARGET"

# Clean up any old approaches
rm -rf "$HOME/Applications/CryptoResearchAgent.app" 2>/dev/null || true
rm -f "/usr/local/bin/crypto-research-agent.sh" 2>/dev/null || true

# Stop any running instance on port 8000
lsof -i :8000 -t 2>/dev/null | xargs kill 2>/dev/null || true

launchctl unload "$PLIST_TARGET" 2>/dev/null || true
launchctl load "$PLIST_TARGET"

sleep 3

if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo ""
    echo "Done. Backend is running and will auto-start on login."
    echo ""
    echo "  Status:  launchctl list | grep crypto-research-agent"
    echo "  Logs:    tail -f '$PROJECT_DIR/data/server.stdout.log'"
    echo "  Remove:  $PROJECT_DIR/scripts/uninstall-autostart.sh"
else
    echo ""
    echo "WARNING: Backend did not start. Check logs:"
    echo "  tail '$PROJECT_DIR/data/server.stderr.log'"
    echo ""
    echo "If the error mentions 'Operation not permitted', grant Full Disk Access"
    echo "to $PYTHON_BIN in System Settings > Privacy & Security."
    exit 1
fi
