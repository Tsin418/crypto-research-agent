#!/bin/bash
set -e

echo "==> Removing Crypto Research Agent services..."

for plist in \
    "$HOME/Library/LaunchAgents/com.crypto-research-agent.backend.plist" \
    "$HOME/Library/LaunchAgents/com.crypto-research-agent.frontend.plist" \
    "$HOME/Library/LaunchAgents/com.crypto-research-agent.plist"; do
    launchctl unload "$plist" 2>/dev/null || true
    rm -f "$plist"
done

# Kill running processes
lsof -i :8000 -t 2>/dev/null | xargs kill 2>/dev/null || true
lsof -i :5173 -t 2>/dev/null | xargs kill 2>/dev/null || true

# Clean up old artifacts
rm -rf "$HOME/Applications/CryptoResearchAgent.app" 2>/dev/null || true

echo "Done. All services removed."
