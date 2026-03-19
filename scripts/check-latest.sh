#!/usr/bin/env bash
#
# Check for newer versions of Coq and the 5 indexed Coq libraries.
# Compares installed opam versions against the latest available in the
# coq-released repository.  Run inside the container.
#
# Usage:
#   ./scripts/check-latest.sh

set -euo pipefail

eval $(opam env --switch=coq 2>/dev/null) || true

# --- Package map: library identifier → opam package name ---

declare -A OPAM_PACKAGES=(
    [coq]=coq
    [flocq]=coq-flocq
    [coquelicot]=coq-coquelicot
    [mathcomp]=coq-mathcomp-ssreflect
    [coqinterval]=coq-interval
    [stdpp]=coq-stdpp
)

# --- Query installed and latest versions ---

updates_available=false

printf "%-28s  %-12s  %-12s  %s\n" "Package" "Installed" "Latest" "Status"
printf "%-28s  %-12s  %-12s  %s\n" "----------------------------" "------------" "------------" "------"

for lib in coq flocq coquelicot mathcomp coqinterval stdpp; do
    pkg="${OPAM_PACKAGES[$lib]}"

    installed=$(opam show "$pkg" --field=version 2>/dev/null | tr -d '"') || installed=""
    if [[ -z "$installed" ]]; then
        printf "%-28s  %-12s  %-12s  %s\n" "$pkg" "not installed" "-" "SKIP"
        continue
    fi

    # opam info --field=all-versions returns a space-separated list; last is latest
    all_versions=$(opam info "$pkg" --field=all-versions 2>/dev/null | tr -d '"') || all_versions=""
    if [[ -z "$all_versions" ]]; then
        printf "%-28s  %-12s  %-12s  %s\n" "$pkg" "$installed" "?" "UNKNOWN"
        continue
    fi

    latest=$(echo "$all_versions" | tr ' ' '\n' | tail -1)

    if [[ "$installed" == "$latest" ]]; then
        printf "%-28s  %-12s  %-12s  %s\n" "$pkg" "$installed" "$latest" "ok"
    else
        printf "%-28s  %-12s  %-12s  %s\n" "$pkg" "$installed" "$latest" "UPDATE"
        updates_available=true
    fi
done

echo ""

if [[ "$updates_available" == true ]]; then
    echo "Updates available. To upgrade, edit the pinned versions in the Dockerfile,"
    echo "then rebuild the image and publish new indexes."
else
    echo "All packages are up to date."
fi
