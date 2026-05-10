#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
#  Gate DEX CLI — GateClaw setup script (PROD)
#
#  Runs inside the GateClaw Pod (node user, no sudo, no TTY, idempotent).
#  Downloads the pre-built Linux binary into the GateClaw skills bin dir.
#
#  Default: tracks the `latest/` channel on the CDN. Set GATE_DEX_VERSION
#  (e.g. "1.0.1") to pin a specific release for rollback / debugging.
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SKILL_BIN_DIR="/home/node/.openclaw/skills/bin"
BINARY_NAME="gate-dex"
BIN_PATH="$SKILL_BIN_DIR/$BINARY_NAME"

CHANNEL="${GATE_DEX_VERSION:+v${GATE_DEX_VERSION}}"
CHANNEL="${CHANNEL:-latest}"
DOWNLOAD_URL="https://gate-dex-cli.gateweb3.cc/${CHANNEL}/gate-dex-linux-x64"

mkdir -p "$SKILL_BIN_DIR"

# ── Conditional download: server returns 304 if our local copy is current ────
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

echo "[gate-dex-cli] checking ${DOWNLOAD_URL} ..."
zopt=()
[ -f "$BIN_PATH" ] && zopt=(-z "$BIN_PATH")

http_code="$(curl -fsSL -o "$tmp" -w '%{http_code}' "${zopt[@]}" "$DOWNLOAD_URL")"

if [ "$http_code" = "304" ] || [ ! -s "$tmp" ]; then
  current="$([ -x "$BIN_PATH" ] && "$BIN_PATH" --version 2>/dev/null | tr -d '[:space:]' || echo unknown)"
  echo "[gate-dex-cli] already up-to-date (v${current}), skipping."
  exit 0
fi

chmod +x "$tmp"
mv "$tmp" "$BIN_PATH"

installed="$("$BIN_PATH" --version 2>/dev/null | tr -d '[:space:]' || echo unknown)"
echo "[gate-dex-cli] installed: v${installed} at ${BIN_PATH} (channel: ${CHANNEL})"
