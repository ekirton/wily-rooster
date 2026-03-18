#!/usr/bin/env bash
set -euo pipefail

IMAGE="poule:dev"

echo "═══════════════════════════════════════════════════════"
echo "  Stage 1: Unit tests (no Docker, no Coq)"
echo "═══════════════════════════════════════════════════════"
uv run pytest -m "not requires_coq" \
    --cov=poule --cov-report=term -v

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Stage 2: Build container image"
echo "═══════════════════════════════════════════════════════"
docker build -t "$IMAGE" .

# If a local index.db exists, copy it into the image
if [ -f index.db ]; then
    echo "  Found index.db — copying into image at /data/index.db"
    cid=$(docker create "$IMAGE")
    docker cp index.db "$cid":/data/index.db
    docker commit "$cid" "$IMAGE" > /dev/null
    docker rm "$cid" > /dev/null
else
    echo "  No index.db found — skipping database seed"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Stage 3: Integration tests (inside container)"
echo "═══════════════════════════════════════════════════════"
docker run --rm --entrypoint uv "$IMAGE" run pytest -m requires_coq -v

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  All stages passed."
echo "═══════════════════════════════════════════════════════"
echo ""
echo "To use the dev image:"
echo ""
echo "  bin/poule --dev                   Start interactive dev shell"
echo "  bin/poule --dev uv run pytest     Run tests with live source"
echo ""
echo "  Container image:  $IMAGE  (used by: bin/poule --dev)"
echo "  Required volume:  -v <host-data-dir>:/data  (for index.db persistence)"
echo "  Default command:  uv run python -m poule.server --db /data/index.db"
echo ""
echo "  Override entrypoint for a shell:"
echo "    docker run --rm -it --entrypoint bash $IMAGE"
echo ""
