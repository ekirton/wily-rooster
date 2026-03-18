# Modular Index Distribution

Users configure which Coq libraries are included in their search index. The system downloads per-library indexes and merges them into a single searchable database, so existing search tools work without modification.

**PRD**: [Modular Index Distribution](../requirements/modular-index-distribution.md)
**Stories**: [Modular Index Distribution](../requirements/stories/modular-index-distribution.md)

---

## Problem

The search index ships as a single monolithic file covering a fixed library set. This creates three friction points:

1. **Wasted downloads** — users who only need the standard library download data for libraries they never use
2. **All-or-nothing updates** — when one library releases a new version, the entire index must be republished and re-downloaded
3. **No library choice** — users cannot add or remove libraries from their index without rebuilding from source, which requires the full Coq toolchain and 15–30 minutes

## Solution

Six Coq libraries are supported as independently downloadable index components:

| Library | Description |
|---------|-------------|
| stdlib | Coq standard library (default) |
| mathcomp | Mathematical Components |
| stdpp | Extended standard library (MPI-SWS) |
| flocq | Floating-point formalization |
| coquelicot | Real analysis |
| coqinterval | Interval arithmetic |

Users specify their selection in a configuration file stored alongside library data. The system downloads only the selected libraries' indexes and assembles them into a single database. All existing search and retrieval tools operate on this merged database without awareness of its modular origin.

## Configuration

A configuration file in the libraries directory (`~/poule-libraries/config.toml` by default) controls library selection. The directory path is overridable via `POULE_LIBRARIES_PATH`. When no configuration file exists, the system defaults to the standard library only.

## Container Experience

The container ships with all 6 libraries' compiled Coq files pre-installed, regardless of which are indexed. This means:

- **Proof interaction** works for any of the 6 libraries immediately — users can `Require Import` from any of them
- **Local extraction** is possible — users can rebuild their index for any combination without installing additional packages
- **Startup check** — every container launch compares the configuration against the current index and downloads or rebuilds as needed
- **Status display** — startup reports which libraries are currently indexed, so users can confirm their configuration took effect

Two host directories are mounted into the container: the libraries directory (for indexes and configuration) and the user's project directory (current working directory).

## Update Workflow

A `--update` flag on the launcher pulls the latest container image and checks for newer per-library index assets. If any configured library has an updated index available, it is downloaded and the merged index is rebuilt. This provides a single command for staying current.

## Developer Automation

A maintainer-facing script detects new upstream library versions (via the package manager), re-extracts changed libraries, and publishes updated index assets. A host-side launcher wraps this in a container invocation suitable for scheduled automation.

## Design Rationale

### Why download-and-merge rather than multiple attached databases

Merging per-library databases into a single file at install time keeps all existing search code unchanged — every retrieval channel, the full-text search index, and the dependency graph operate on a single database with a single ID space. The alternative (querying across multiple attached SQLite databases at runtime) would require rewriting every query, fragmenting the FTS index, and handling cross-database foreign keys for dependencies.

### Why 6 libraries

These 6 were selected because they are all: actively maintained, in the Rocq Platform, compatible with Coq 8.19, and extractable without special processing (no custom proof modes). They form two coherent dependency chains — the numerical analysis stack (Flocq → Coquelicot → CoqInterval) and the general-purpose extension (stdpp) — alongside the two anchor libraries (stdlib, MathComp). Libraries requiring custom extraction handling (Iris, CompCert) are excluded from the prebuilt set.

### Why stdlib-only default

New users should have the smallest possible first-run download. Most Coq beginners work only with the standard library. Users working with MathComp or other libraries are experienced enough to edit a configuration file.

### Why co-locate config with library data

Placing `config.toml` in the libraries directory (`~/poule-libraries/`) keeps all persistent library state in one place. This directory is mounted into the container, so both the host-side launcher and the in-container tools see the same configuration without synchronization.

## Scope Boundaries

This feature provides:

- User-configurable library selection for the search index
- Per-library download with integrity verification
- Transparent assembly of per-library indexes into a single search database
- Container with all 6 libraries available for proof interaction
- Startup configuration check and status reporting
- Single-command update workflow

It does **not** provide:

- Libraries beyond the 6 listed (future expansion possible by adding identifiers)
- Per-library neural model distribution
- Automatic detection of which libraries a user's project needs
- Runtime switching of library sets without container restart
