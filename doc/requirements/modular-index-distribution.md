# Modular Index Distribution — Product Requirements Document

Cross-reference: see [semantic-lemma-search.md](semantic-lemma-search.md) for the core search initiative this extends.

## 1. Business Goals

The search index currently ships as a single monolithic file covering a fixed set of libraries. Users who only need the standard library download unnecessary data, while users who want additional libraries must rebuild the entire index from source — a process requiring the full Coq toolchain and 15–30 minutes of extraction time. Library maintainers cannot update a single library's index without republishing everything.

This initiative delivers modular, per-library index distribution: each supported library is indexed independently and published as a separate downloadable asset. Users configure which libraries they want, and the system downloads and assembles only the selected indexes. The container ships with all supported libraries pre-installed so proof interaction works out of the box.

**Success metrics:**
- Users can select any subset of the 6 supported libraries and receive a working search index containing only those libraries
- Adding or removing a library from the user's configuration triggers download and reassembly without re-extracting from source
- Container startup reports which libraries are currently indexed within 5 seconds of launch
- A merged index produces search results identical in ranking to a monolithically-extracted index of the same libraries

---

## 2. Target Users

| Segment | Needs | Priority |
|---------|-------|----------|
| Coq developers using Claude Code | Configure which libraries to search, download only what they need, update libraries independently | Primary |
| Project maintainers | Automate detection of new library versions, re-indexing, and publishing of updated indexes | Secondary |

---

## 3. Competitive Context

No Coq search tool offers modular library selection. Lean's search tools (Loogle, Moogle) index Mathlib monolithically — users cannot choose a subset. Modular distribution is a differentiator that reduces onboarding friction and supports diverse Coq workflows.

---

## 4. Requirement Pool

### P0 — Must Have

| ID | Requirement |
|----|-------------|
| R-P0-1 | A user configuration file specifies which libraries to include in the search index |
| R-P0-2 | The configuration file resides alongside library data in a persistent directory (default `~/poule-libraries/`) configurable via the `POULE_LIBRARIES_PATH` environment variable |
| R-P0-3 | Each supported library's index is published as an independent downloadable asset |
| R-P0-4 | The download process fetches only the libraries the user has selected in their configuration |
| R-P0-5 | Downloaded per-library indexes are merged into a single search database usable by all existing search tools |
| R-P0-6 | A merged index produces search results identical in ranking to a monolithically-extracted index of the same library set |
| R-P0-7 | The container pre-installs compiled library files for all 6 supported libraries so proof interaction and extraction work without additional installation |
| R-P0-8 | On every container startup, the system checks the user's configuration against the current index and downloads missing libraries or rebuilds the index if the configuration has changed |
| R-P0-9 | On container startup, the system displays which libraries are currently indexed and available |
| R-P0-10 | The container mounts two persistent directories from the host: a libraries directory for indexes and configuration, and the user's project directory |
| R-P0-11 | A `--update` flag on the launcher pulls the latest container image and updates library indexes according to the user's configuration |
| R-P0-12 | When no configuration file exists, the system defaults to indexing the Coq standard library only |

### P1 — Should Have

| ID | Requirement |
|----|-------------|
| R-P1-1 | A developer script detects new upstream versions of supported libraries, re-extracts changed libraries, and publishes updated index assets |
| R-P1-2 | A host-side launcher executes the developer re-index script inside a container, suitable for scheduled automation (e.g., cron) |

### P2 — Nice to Have

| ID | Requirement |
|----|-------------|
| R-P2-1 | Users can add their own project's declarations to the merged index alongside library declarations |

---

## 5. Scope Boundaries

**Supported libraries (this initiative):**
- Coq standard library (stdlib)
- Mathematical Components (mathcomp)
- std++ (stdpp)
- Flocq
- Coquelicot
- CoqInterval

**In scope:**
- Per-library index publishing and download
- User configuration of library selection
- Index merging from per-library components
- Container with all 6 libraries pre-installed
- Startup configuration check and library status reporting
- Launcher update flag for pulling new images and indexes
- Developer automation for detecting and publishing library updates

**Out of scope (this initiative):**
- Libraries beyond the 6 listed above
- Per-library neural model distribution (neural models are distributed separately)
- User project indexing merged with library indexes (existing requirement in semantic-lemma-search)
- Web-based configuration interface
