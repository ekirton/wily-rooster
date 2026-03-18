#!/usr/bin/env bash
#
# Nightly re-index: detect new upstream Coq library versions,
# re-extract changed libraries, and publish updated index assets.
#
# Runs inside the container. See specification/nightly-reindex.md.

set -euo pipefail

# --- Constants ---

LIBRARIES="stdlib mathcomp stdpp flocq coquelicot coqinterval"

declare -A OPAM_PACKAGES=(
    [mathcomp]=coq-mathcomp-ssreflect
    [stdpp]=coq-stdpp
    [flocq]=coq-flocq
    [coquelicot]=coq-coquelicot
    [coqinterval]=coq-interval
)

# --- Workdir setup and cleanup ---

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

# --- Validate prerequisites ---

if [[ -z "${GH_TOKEN:-}" ]]; then
    echo "Error: GitHub authentication failed. Set GH_TOKEN with contents:write scope." >&2
    exit 1
fi

if ! command -v coqc &>/dev/null; then
    echo "Error: coqc not found on PATH." >&2
    exit 1
fi

if ! command -v opam &>/dev/null; then
    echo "Error: opam not found on PATH." >&2
    exit 1
fi

eval $(opam env) 2>/dev/null || true

# --- Fetch current manifest ---

echo "Fetching manifest from latest release..." >&2

latest_tag=""
latest_tag=$(gh release list --limit 20 --json tagName \
    | python3 -c 'import json,sys; tags=[r["tagName"] for r in json.load(sys.stdin) if r["tagName"].startswith("index-v")]; print(tags[0] if tags else "")' \
    2>/dev/null) || true

declare -A published_versions

if [[ -z "$latest_tag" ]]; then
    echo "No existing release found. Treating all as changed." >&2
else
    if ! gh release download "$latest_tag" -p manifest.json -D "$workdir" 2>/dev/null; then
        echo "Error: Failed to reach GitHub API." >&2
        exit 1
    fi

    # Parse published versions from manifest
    while IFS='=' read -r lib ver; do
        published_versions["$lib"]="$ver"
    done < <(python3 -c '
import json, sys
m = json.load(open(sys.argv[1]))
for lib, info in m.get("libraries", {}).items():
    print(f"{lib}={info[\"version\"]}")
' "$workdir/manifest.json" 2>/dev/null) || true

    # Clean up manifest so it does not interfere with asset staging
    rm -f "$workdir/manifest.json"
fi

# --- Detect installed versions ---

echo "Detecting installed versions..." >&2

declare -A installed_versions
skipped_libs=""

for lib in $LIBRARIES; do
    if [[ "$lib" == "stdlib" ]]; then
        ver=$(coqc --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1) || true
    else
        ver=$(opam list "${OPAM_PACKAGES[$lib]}" --short --columns=version 2>/dev/null) || true
    fi

    if [[ -z "$ver" ]]; then
        echo "Warning: Could not detect version for ${lib}. Skipping." >&2
        skipped_libs="$skipped_libs $lib"
        continue
    fi

    installed_versions["$lib"]="$ver"

    # Log comparison
    pub="${published_versions[$lib]:-}"
    if [[ -z "$pub" ]]; then
        echo "  ${lib}:$(printf '%*s' $((14 - ${#lib})) '')${ver} (no published version)" >&2
    elif [[ "$ver" != "$pub" ]]; then
        echo "  ${lib}:$(printf '%*s' $((14 - ${#lib})) '')${ver} (published: ${pub}) *changed*" >&2
    else
        echo "  ${lib}:$(printf '%*s' $((14 - ${#lib})) '')${ver} (published: ${pub})" >&2
    fi
done

# --- Compare versions ---

changed_libs=""
unchanged_libs=""

for lib in $LIBRARIES; do
    # Skip libraries we could not detect
    if [[ " $skipped_libs " == *" $lib "* ]]; then
        continue
    fi

    pub="${published_versions[$lib]:-}"
    inst="${installed_versions[$lib]:-}"

    if [[ -z "$pub" || "$inst" != "$pub" ]]; then
        changed_libs="$changed_libs $lib"
    else
        unchanged_libs="$unchanged_libs $lib"
    fi
done

changed_libs="${changed_libs# }"
unchanged_libs="${unchanged_libs# }"

# --- Early exit if nothing changed ---

if [[ -z "$changed_libs" ]]; then
    echo "All indexes are current." >&2
    exit 0
fi

# --- Extract changed libraries ---

extracted_libs=""
failed_libs=""
extraction_count=0
success_count=0

for lib in $changed_libs; do
    extraction_count=$((extraction_count + 1))
    echo "Extracting ${lib}..." >&2

    if python -m Poule.extraction --target "$lib" --db "$workdir/index-${lib}.db" --progress 2>&1 >&2; then
        extracted_libs="$extracted_libs $lib"
        success_count=$((success_count + 1))
    else
        echo "Error: Extraction failed for ${lib}. Carrying forward previous asset." >&2
        failed_libs="$failed_libs $lib"
        # Reclassify as unchanged for carry-forward
        unchanged_libs="$unchanged_libs $lib"
    fi
done

extracted_libs="${extracted_libs# }"
unchanged_libs="${unchanged_libs# }"

# Abort if all extractions failed
if [[ $success_count -eq 0 ]]; then
    echo "Error: All extractions failed. Aborting." >&2
    exit 1
fi

# --- Download unchanged assets ---

if [[ -n "$unchanged_libs" && -n "$latest_tag" ]]; then
    echo "Downloading unchanged assets..." >&2
    for lib in $unchanged_libs; do
        asset="index-${lib}.db"
        if ! gh release download "$latest_tag" -p "$asset" -D "$workdir" 2>/dev/null; then
            echo "Error: Failed to download ${asset} from release ${latest_tag}." >&2
            exit 1
        fi
    done
fi

# --- Publish release ---

echo "Publishing release..." >&2

if ! ./scripts/publish-release.sh --replace $workdir/index-*.db; then
    echo "Error: Release publication failed." >&2
    exit 1
fi

# --- Determine release tag for summary ---

coq_ver="${installed_versions[stdlib]:-}"
if [[ -z "$coq_ver" ]]; then
    coq_ver=$(coqc --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1) || true
fi

# Read schema version from one of the produced DBs
schema_ver=""
for f in "$workdir"/index-*.db; do
    if [[ -f "$f" ]] && command -v sqlite3 &>/dev/null; then
        schema_ver=$(sqlite3 "$f" "SELECT value FROM index_meta WHERE key='schema_version'" 2>/dev/null) || true
        break
    fi
done
release_tag="index-v${schema_ver:-1}-coq${coq_ver}"

# --- Print summary to stdout ---

# Build re-extracted list
re_extracted=""
for lib in $extracted_libs; do
    if [[ -n "$re_extracted" ]]; then
        re_extracted+=", "
    fi
    re_extracted+="${lib} ${installed_versions[$lib]}"
done

# Build unchanged list
unchanged_summary=""
for lib in $unchanged_libs; do
    ver="${installed_versions[$lib]:-}"
    if [[ -z "$ver" ]]; then
        continue
    fi
    if [[ -n "$unchanged_summary" ]]; then
        unchanged_summary+=", "
    fi
    unchanged_summary+="${lib} ${ver}"
done
if [[ -z "$unchanged_summary" ]]; then
    unchanged_summary="(none)"
fi

echo "Nightly re-index summary:"
echo "  Re-extracted: ${re_extracted}"
echo "  Unchanged:    ${unchanged_summary}"
echo "  Release:      ${release_tag}"
