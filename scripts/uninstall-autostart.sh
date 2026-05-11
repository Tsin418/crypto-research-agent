#!/bin/bash
set -e

PLIST_TARGET="$HOME/Library/LaunchAgents/com.crypto-research-agent.plist"

echo "==> Removing Crypto Research Agent service..."

launchctl unload "$PLIST_TARGET" 2>/dev/null || true
rm -f "$PLIST_TARGET"

lsof -i :8000 -t 2>/dev/null | xargs kill 2>/dev/null || true

# Clean up old artifacts from previous approaches
rm -rf "$HOME/Applications/CryptoResearchAgent.app" 2>/dev/null || true
rm -f "/usr/local/bin/crypto-research-agent.sh" 2>/dev/null || true

echo "Done. Service removed."
