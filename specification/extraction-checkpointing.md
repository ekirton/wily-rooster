# Extraction Checkpointing

Incremental re-extraction of changed files and resumption of interrupted extraction campaigns.

**Architecture**: [extraction-checkpointing.md](../doc/architecture/extraction-checkpointing.md), [extraction-types.md](../doc/architecture/data-models/extraction-types.md)

---

## 1. Purpose

Define the checkpointing system that enables incremental re-extraction (process only changed files) and campaign resumption (continue from the point of interruption). Both are P1 capabilities.

## 2. Scope

**In scope**: Checkpoint file format, checkpoint read/write operations, file-level change detection, incremental merge pipeline, campaign resumption pipeline, consistency validation.

**Out of scope**: Campaign orchestration logic (owned by extraction-campaign), output serialization (owned by extraction-output), session management (owned by proof-session).

## 3. Definitions

| Term | Definition |
|------|-----------|
| Checkpoint | A sidecar JSON file recording extraction progress, stored at `<output_path>.checkpoint` |
| Incremental re-extraction | Re-extracting only proofs in files whose content has changed since the prior extraction |
| Campaign resumption | Continuing an interrupted extraction from the last completed proof |
| Content hash | A deterministic hash of a .v file's contents, used for change detection |

## 4. Behavioral Requirements

### 4.1 Checkpoint File

#### Checkpoint location

The checkpoint file shall be stored at `<output_path>.checkpoint`, alongside the JSON Lines output file.

> **Given** an output path of `/data/stdlib.jsonl`
> **When** the checkpoint is written
> **Then** it is stored at `/data/stdlib.jsonl.checkpoint`

#### Checkpoint structure

The system shall write the checkpoint as a single JSON object (not JSON Lines) with the following fields in order:

| Position | Field | JSON type | Purpose |
|----------|-------|-----------|---------|
| 1 | `schema_version` | integer | Checkpoint format version |
| 2 | `campaign_metadata` | CampaignMetadata object | Campaign provenance for consistency validation |
| 3 | `completed_proofs` | object (map) | Keys: fully qualified theorem names. Values: content hash of the source file at extraction time |
| 4 | `completed_files` | object (map) | Keys: source file paths (relative to project root). Values: content hash |
| 5 | `last_position` | object | `{"project_index": int, "file_index": int, "theorem_index": int}` |

- ENSURES: The checkpoint file is valid JSON. All fields are present.

### 4.2 Checkpoint Write

#### update_checkpoint(checkpoint_path, theorem_name, source_file, content_hash, position)

- REQUIRES: `checkpoint_path` is a writable file path. All parameters are non-null.
- ENSURES: Adds `theorem_name → content_hash` to `completed_proofs`. Updates `completed_files[source_file]` to `content_hash` if all theorems in the file are complete. Updates `last_position` to `position`. Writes the full checkpoint to disk.
- MAINTAINS: The checkpoint is updated after each proof extraction (not batched). At most one proof's work is lost on crash.

> **Given** a checkpoint with 5 completed proofs
> **When** `update_checkpoint` is called after extracting proof 6
> **Then** the checkpoint on disk contains 6 completed proofs and the updated position

#### Non-atomic writes

Checkpoint writes are not atomic. A crash during write may corrupt the checkpoint. The system shall detect corrupted checkpoints (invalid JSON) on read and fall back to full extraction.

> **Given** a checkpoint file containing truncated JSON (mid-write crash)
> **When** the checkpoint is loaded
> **Then** the system logs a warning and falls back to full extraction

### 4.3 Incremental Re-Extraction

#### incremental_extract(project_dirs, output_path, options)

- REQUIRES: `output_path` exists and has a corresponding `.checkpoint` file. `project_dirs` matches the original campaign's project list.
- ENSURES: Loads the prior checkpoint. Validates consistency (same projects, same Coq versions). Classifies each file as unchanged, changed, new, or removed. Re-extracts proofs in changed and new files. Merges prior results for unchanged files with new results. Writes the merged output (replacing the prior output file). Updates the checkpoint.
- On checkpoint not found: falls through to full extraction.
- On consistency mismatch: discards checkpoint, runs full extraction.

> **Given** a prior extraction of 100 files where 3 files have changed
> **When** `incremental_extract` is called
> **Then** only the 3 changed files are re-extracted; results for the other 97 files are reused from the prior output

> **Given** a checkpoint from a different set of projects
> **When** `incremental_extract` is called
> **Then** the checkpoint is discarded and a full extraction runs

#### File classification

The system shall classify each file in the campaign plan:

| Classification | Condition | Action |
|---------------|-----------|--------|
| Unchanged | File in checkpoint, content hash matches | Reuse prior ExtractionRecords |
| Changed | File in checkpoint, content hash differs | Re-extract all proofs in file |
| New | File not in checkpoint | Extract all proofs in file |
| Removed | File in checkpoint but not in plan | Drop from output |

- REQUIRES: Content hash computation uses the same algorithm as the original extraction.
- ENSURES: Classification is deterministic — same file contents produce the same hash.

> **Given** a file `A.v` with the same content hash as in the checkpoint
> **When** the file is classified
> **Then** it is marked `unchanged` and its proofs are reused without re-extraction

> **Given** a file `B.v` that exists in the checkpoint but not on disk
> **When** the file is classified
> **Then** it is marked `removed` and its records are dropped from the output

#### Output equivalence

The merged output shall be byte-identical to what a full extraction would produce, with one permitted exception: the `extraction_timestamp` in CampaignMetadata may differ.

- MAINTAINS: Record ordering follows the same deterministic rules as full extraction.
- MAINTAINS: Records from unchanged files use the exact bytes from the prior output (not re-serialized).

> **Given** an incremental extraction where only `B.v` changed
> **When** the merged output is compared to a full extraction on the same inputs
> **Then** they are byte-identical except for `extraction_timestamp`

### 4.4 Campaign Resumption

#### resume_extract(output_path)

- REQUIRES: `output_path` exists with a corresponding `.checkpoint` file.
- ENSURES: Loads the checkpoint. Validates consistency (project directories exist, Coq versions match). Rebuilds the campaign plan. Seeks to `last_position` in the plan. Continues extraction from that point. Appends new records to the existing output file. On completion, rewrites the output file with updated CampaignMetadata (timestamp) and ExtractionSummary. Updates the checkpoint.
- On checkpoint not found: raises `NO_CHECKPOINT` error.
- On consistency failure (project dir missing, Coq version changed): raises `CHECKPOINT_STALE` error.

> **Given** a checkpoint indicating extraction completed through file 50 of 100
> **When** `resume_extract` is called
> **Then** extraction resumes from file 51 without re-extracting files 1-50

> **Given** a checkpoint file that does not exist
> **When** `resume_extract` is called
> **Then** a `NO_CHECKPOINT` error is raised

> **Given** a checkpoint where the project directory no longer exists
> **When** `resume_extract` is called
> **Then** a `CHECKPOINT_STALE` error is raised

#### Output rewrite on completion

When resumed extraction completes, the system shall rewrite the output file to:
1. Update CampaignMetadata with the current `extraction_timestamp`
2. Append the ExtractionSummary as the last line (covering the full campaign)

- ENSURES: The final output has the same structure as a non-interrupted extraction.

## 5. Error Specification

| Error code | Category | Condition |
|-----------|----------|-----------|
| `NO_CHECKPOINT` | State error | `resume_extract` called without a checkpoint file |
| `CHECKPOINT_STALE` | State error | Checkpoint references projects or Coq versions that no longer match |
| `CHECKPOINT_CORRUPT` | State error | Checkpoint file is not valid JSON (detected on load, falls back to full extraction) |

### Edge cases

| Condition | Behavior |
|-----------|----------|
| Checkpoint exists but output file is missing | Full extraction (checkpoint without output is useless) |
| Checkpoint indicates 0 completed proofs | Equivalent to full extraction |
| All files unchanged in incremental extraction | Output is rewritten with new timestamp; all records reused |
| New file added since last extraction | File classified as `new`; extracted normally |
| File renamed (old path gone, new path added) | Old path classified as `removed`, new path as `new` |

## 6. Non-Functional Requirements

- Checkpoint writes shall complete in < 100 ms (JSON serialization of checkpoint state).
- Content hash computation shall use a cryptographic hash (SHA-256 or equivalent) for collision resistance.
- Incremental extraction of a project where 1% of files changed shall complete in < 5% of full extraction time (I/O for reuse dominates).

## 7. Examples

### Incremental extraction workflow

```
# First run: full extraction
run_campaign(["/stdlib"], "/data/stdlib.jsonl", options)
# Creates /data/stdlib.jsonl and /data/stdlib.jsonl.checkpoint

# User modifies 2 files in stdlib
# Second run: incremental
incremental_extract(["/stdlib"], "/data/stdlib.jsonl", options)
# Re-extracts only the 2 changed files
# Merges with prior results for all other files
# Output is byte-identical to a full re-extraction (except timestamp)
```

### Resumption workflow

```
# First run: interrupted at theorem 500 of 1000
run_campaign(["/stdlib"], "/data/stdlib.jsonl", options)
# Interrupted by SIGINT — checkpoint saved at position 500

# Second run: resume
resume_extract("/data/stdlib.jsonl")
# Continues from theorem 501, extracts 501-1000
# Rewrites output with complete metadata and summary
```

## 8. Language-Specific Notes (Python)

- Use `hashlib.sha256(file_contents).hexdigest()` for content hashing.
- Use `json.load()` / `json.dump()` for checkpoint read/write.
- Catch `json.JSONDecodeError` for checkpoint corruption detection.
- Use `pathlib.Path` for checkpoint path derivation (`output_path.with_suffix(output_path.suffix + '.checkpoint')`).
- Package location: `src/poule/extraction/checkpoint.py`.
