#!/bin/bash
set -euo pipefail

# Install or update Claude Code in the persistent home directory.
ensure-claude --update

if [ $# -gt 0 ]; then
    exec "$@"
fi

# Default: start the MCP server as a background daemon, then launch Claude.
# The server runs in SSE mode so Claude Code (and the developer) can stop and
# restart it independently without exiting Claude.
poule-mcp start

exec claude --dangerously-skip-permissions --model opus
