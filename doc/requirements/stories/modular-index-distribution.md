# User Stories: Modular Index Distribution

Derived from [doc/requirements/modular-index-distribution.md](../modular-index-distribution.md).

---

## Epic 1: Library Configuration

### 1.1 Specify Library Selection

**As a** Coq developer,
**I want to** specify which libraries to include in my search index via a configuration file,
**so that** I only download and search the libraries relevant to my work.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a configuration file at `~/poule-libraries/config.toml` containing `libraries = ["stdlib", "mathcomp"]` WHEN the system reads the configuration THEN it selects exactly those two libraries for download and indexing
- GIVEN a configuration file listing all 6 supported libraries WHEN the system reads the configuration THEN all 6 are selected
- GIVEN a configuration file listing only `["stdlib"]` WHEN the system reads the configuration THEN only the standard library is selected

### 1.2 Validate Configuration

**As a** Coq developer,
**I want** clear error messages if my configuration references an unsupported library,
**so that** I can correct my configuration without guessing valid options.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a configuration file containing `libraries = ["stdlib", "unknown-lib"]` WHEN the system reads the configuration THEN it reports an error naming `unknown-lib` as unsupported and lists the 6 valid library identifiers
- GIVEN a configuration file with an empty `libraries = []` list WHEN the system reads the configuration THEN it reports an error indicating at least one library must be selected

### 1.3 Default Configuration

**As a** new user with no configuration file,
**I want** the system to use sensible defaults,
**so that** I can start using search immediately without manual setup.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN no configuration file exists at the expected path WHEN the system starts THEN it behaves as if `libraries = ["stdlib"]` were configured
- GIVEN the default configuration is used WHEN the index is built THEN it contains only standard library declarations

### 1.4 Custom Libraries Directory

**As a** Coq developer with a non-standard home directory layout,
**I want to** override the libraries directory path via an environment variable,
**so that** I can store library indexes wherever suits my system.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN `POULE_LIBRARIES_PATH` is set to `/data/my-libraries` WHEN the system starts THEN it reads configuration from `/data/my-libraries/config.toml` and stores per-library indexes in `/data/my-libraries/`
- GIVEN `POULE_LIBRARIES_PATH` is not set WHEN the system starts THEN it uses `~/poule-libraries/` as the libraries directory

---

## Epic 2: Per-Library Download

### 2.1 Download Selected Libraries

**As a** Coq developer,
**I want to** download only the per-library indexes I have selected,
**so that** I do not waste bandwidth or disk space on libraries I do not use.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a configuration with `libraries = ["stdlib", "flocq"]` WHEN the download runs THEN only the `index-stdlib.db` and `index-flocq.db` assets are fetched from the release
- GIVEN a configuration with `libraries = ["stdlib"]` WHEN the download runs THEN no other library index files are fetched

### 2.2 Skip Already-Downloaded Libraries

**As a** Coq developer,
**I want** the download process to skip libraries I already have at the correct version,
**so that** repeated startups are fast and do not re-download unchanged data.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN `index-stdlib.db` already exists locally with a checksum matching the current release WHEN the download runs THEN `index-stdlib.db` is not re-downloaded
- GIVEN `index-mathcomp.db` exists locally but its checksum does not match the current release WHEN the download runs THEN `index-mathcomp.db` is re-downloaded and replaced

### 2.3 Checksum Verification

**As a** Coq developer,
**I want** each downloaded library index verified by checksum before use,
**so that** corrupted or tampered downloads do not produce incorrect search results.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a per-library index is downloaded WHEN its SHA-256 checksum matches the manifest THEN the file is placed in the libraries directory
- GIVEN a per-library index is downloaded WHEN its SHA-256 checksum does not match the manifest THEN the file is deleted, an error is reported, and the merge does not proceed

---

## Epic 3: Index Merging

### 3.1 Merge Into Single Database

**As a** Coq developer,
**I want** downloaded per-library indexes merged into a single database,
**so that** all existing search tools work without modification.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN per-library indexes for stdlib and mathcomp have been downloaded WHEN the merge completes THEN a single `index.db` exists containing declarations from both libraries
- GIVEN a merged `index.db` WHEN a search query is executed THEN results from all merged libraries are returned and ranked together
- GIVEN a merged `index.db` WHEN a full-text search is executed THEN it searches across declarations from all merged libraries

### 3.2 Metadata Tracking

**As a** developer or maintainer,
**I want** the merged database to record which libraries and versions it contains,
**so that** the system can detect when the index needs to be rebuilt.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a merged `index.db` containing stdlib 8.19.2 and mathcomp 2.2.0 WHEN the metadata is queried THEN it reports both libraries and their versions
- GIVEN a merged `index.db` WHEN the user's configuration lists a library not present in the metadata THEN the system detects the mismatch

### 3.3 Re-merge on Configuration Change

**As a** Coq developer who has changed my library selection,
**I want** the index rebuilt automatically,
**so that** my search results reflect my current configuration without manual intervention.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a user previously configured `["stdlib"]` and now changes to `["stdlib", "mathcomp"]` WHEN the container starts THEN `index-mathcomp.db` is downloaded and the index is rebuilt to include both libraries
- GIVEN a user previously configured `["stdlib", "mathcomp"]` and now changes to `["stdlib"]` WHEN the container starts THEN the index is rebuilt containing only stdlib declarations

---

## Epic 4: Container Library Support

### 4.1 Pre-installed Libraries

**As a** Coq developer,
**I want** all 6 supported libraries' compiled files available in the container,
**so that** I can write proofs using any of them and run extraction without additional installation.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN the container is running WHEN `From Flocq Require Import Core.Fcore_defs.` is executed in Coq THEN it succeeds without error
- GIVEN the container is running WHEN `From stdpp Require Import gmap.` is executed in Coq THEN it succeeds without error
- GIVEN the container is running WHEN `From Coquelicot Require Import Coquelicot.` is executed in Coq THEN it succeeds without error

### 4.2 Startup Configuration Check

**As a** Coq developer,
**I want** the container to check my configuration on every startup and update the index if needed,
**so that** I always have an up-to-date index matching my library selection.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN the user's configuration lists `["stdlib", "flocq"]` and the current `index.db` contains only stdlib WHEN the container starts THEN `index-flocq.db` is downloaded and the index is rebuilt before the user's session begins
- GIVEN the user's configuration matches the current `index.db` contents WHEN the container starts THEN no download or rebuild occurs and startup proceeds immediately

### 4.3 Startup Library Report

**As a** Coq developer,
**I want** to see which libraries are indexed when the container starts,
**so that** I can confirm my configuration took effect.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN the container starts with an index containing stdlib and mathcomp WHEN the startup message is displayed THEN it lists "stdlib 8.19.2, mathcomp 2.2.0" (or equivalent version strings)
- GIVEN the container starts with an index containing only stdlib WHEN the startup message is displayed THEN it lists only "stdlib 8.19.2"

### 4.4 Libraries Volume Mount

**As a** Coq developer,
**I want** per-library indexes and configuration stored in a persistent directory on my host machine,
**so that** they survive container restarts and are not re-downloaded each time.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN the libraries directory is mounted from `~/poule-libraries/` WHEN per-library indexes are downloaded THEN they are written to the mounted directory and persist after the container stops
- GIVEN the libraries directory contains previously downloaded indexes WHEN a new container starts THEN the existing indexes are available without re-downloading

---

## Epic 5: Update Workflow

### 5.1 Launcher Update Flag

**As a** Coq developer,
**I want** a single command that pulls the latest container and updates my library indexes,
**so that** I can stay current without multiple manual steps.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a newer container image is available WHEN `poule --update` is run THEN the latest image is pulled
- GIVEN newer per-library index assets are available for the user's configured libraries WHEN `poule --update` is run THEN the updated indexes are downloaded and the merged index is rebuilt
- GIVEN the container image and all indexes are already up to date WHEN `poule --update` is run THEN it reports that everything is current and exits

---

## Epic 6: Developer Automation

### 6.1 Nightly Re-index Script

**As a** project maintainer,
**I want** a script that detects new upstream library versions, re-extracts changed libraries, and publishes updated index assets,
**so that** users receive updated indexes without manual maintainer intervention.

**Priority:** P1
**Stability:** Draft

**Acceptance criteria:**
- GIVEN mathcomp has a new version available via opam WHEN the re-index script runs THEN it detects the version change, re-extracts mathcomp, and publishes an updated `index-mathcomp.db` asset
- GIVEN no libraries have new versions WHEN the re-index script runs THEN it reports that all indexes are current and does not publish

### 6.2 Cron-Friendly Host Launcher

**As a** project maintainer,
**I want** a host-side script that runs the nightly re-index inside a container,
**so that** I can schedule it via cron without manual Docker invocations.

**Priority:** P1
**Stability:** Draft

**Acceptance criteria:**
- GIVEN the script is invoked by cron WHEN it executes THEN it runs `docker run` with the appropriate image and mounts, executes the re-index script inside the container, and exits with code 0 on success or non-zero on failure
- GIVEN the script completes WHEN the output is inspected THEN it logs which libraries were checked, which were re-extracted, and whether a new release was published
