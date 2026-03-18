#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker &>/dev/null; then
  echo "Error: docker not found on PATH." >&2
  exit 1
fi

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "Error: GH_TOKEN environment variable is not set." >&2
  exit 1
fi

docker pull ghcr.io/ekirton/Poule:dev

docker run --rm -e GH_TOKEN="$GH_TOKEN" ghcr.io/ekirton/Poule:dev /poule/scripts/nightly-reindex.sh
