#!/bin/bash
set -euo pipefail

# Restore Claude Code symlinks hidden by the persistent home directory mount.
# The build-time symlinks in ~/.local/bin/ and ~/.local/share/ are shadowed
# when ~/poule-home is bind-mounted over $HOME at runtime.
mkdir -p ~/.local/bin ~/.local/share
ln -sf "$(ls -d /opt/claude/versions/* | head -1)" ~/.local/bin/claude
ln -sf /opt/claude ~/.local/share/claude

if [ $# -gt 0 ]; then
    exec "$@"
fi

# Default: start the MCP server as a background daemon, then launch Claude.
# The server runs in SSE mode so Claude Code (and the developer) can stop and
# restart it independently without exiting Claude.
poule-mcp start

exec claude --dangerously-skip-permissions --model claude-opus-4-6
