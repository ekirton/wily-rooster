# Extraction Reporting

Quality reports, scope filtering, benchmark subset generation, ML framework export, trace validation, and dataset deduplication for extracted proof traces.

**Architecture**: [extraction-reporting.md](../doc/architecture/extraction-reporting.md), [extraction-types.md](../doc/architecture/data-models/extraction-types.md)

---

## 1. Purpose

Define the post-extraction analysis tools: quality report generation (P1), benchmark subset generation (P2), ML framework export (P2), proof trace validation (P2), and dataset deduplication (P2).

## 2. Scope

**In scope**: Quality report computation, tactic keyword extraction, scope filter specification, benchmark splitting strategies, HuggingFace Datasets export, replay-based validation, cross-project deduplication heuristic.

**Out of scope**: Extraction logic (owned by extraction-campaign), output serialization (owned by extraction-output), model training (Phase 4).

## 3. Definitions

| Term | Definition |
|------|-----------|
| Premise coverage | The fraction of tactic steps (excluding step 0) that have at least one annotated premise |
| Tactic keyword | The first whitespace-delimited token of a tactic string, lowercased, with trailing punctuation stripped |
| Difficulty classification | A composite heuristic based on proof length and tactic diversity |

## 4. Behavioral Requirements

### 4.1 Quality Report Generation (P1)

#### generate_quality_report(extraction_output_path)

- REQUIRES: `extraction_output_path` is a valid JSON Lines extraction output file.
- ENSURES: Reads all ExtractionRecords (filtering by `record_type = "proof_trace"`). Computes aggregate and per-project quality metrics. Returns a QualityReport.

> **Given** an extraction output with 1000 ExtractionRecords across 2 projects
> **When** `generate_quality_report` is called
> **Then** a QualityReport is returned with aggregate metrics and 2 ProjectQualityReport entries

#### Premise coverage computation

The system shall compute premise coverage as:

```
premise_coverage = steps_with_premises / total_tactic_steps
```

Where `steps_with_premises` is the count of ExtractionSteps (with `step_index > 0`) that have at least one entry in `premises`. `total_tactic_steps` is the count of all ExtractionSteps with `step_index > 0`.

- REQUIRES: At least one ExtractionRecord in the input.
- ENSURES: Returns a float in [0.0, 1.0]. Returns 0.0 when no tactic steps exist.

> **Given** 100 tactic steps where 85 have at least one premise
> **When** premise coverage is computed
> **Then** the result is 0.85

#### Proof length distribution

The system shall compute DistributionStats from the `total_steps` field of each ExtractionRecord:

| Metric | Computation |
|--------|-------------|
| `min` | Minimum `total_steps` across all records |
| `max` | Maximum `total_steps` |
| `mean` | Arithmetic mean |
| `median` | Median (interpolated for even counts) |
| `p25` | 25th percentile |
| `p75` | 75th percentile |
| `p95` | 95th percentile |

- REQUIRES: At least one ExtractionRecord.
- ENSURES: All fields are populated. For a single record, min = max = mean = median = p25 = p75 = p95.

#### Tactic keyword extraction

The system shall extract tactic keywords from tactic text using the following algorithm:

1. Split the tactic text by `;` to handle compound tactics.
2. For each sub-tactic: take the first whitespace-delimited token.
3. Strip trailing punctuation (`.`, `,`, `;`).
4. Lowercase the result.

- ENSURES: Returns a list of tactic keywords for each step. Compound tactics produce multiple keywords.

> **Given** tactic text `"rewrite Nat.add_comm."`
> **When** the keyword is extracted
> **Then** the result is `["rewrite"]`

> **Given** tactic text `"simpl; reflexivity."`
> **When** keywords are extracted
> **Then** the result is `["simpl", "reflexivity"]`

> **Given** tactic text `"apply (f_equal S)."`
> **When** the keyword is extracted
> **Then** the result is `["apply"]`

#### Tactic vocabulary frequency

The system shall count tactic keyword occurrences across all steps and return a list of TacticFrequency objects sorted by `count` descending.

- ENSURES: The list contains one entry per distinct keyword. Sorting is stable (ties broken by lexicographic order).

### 4.2 Scope Filter Specification (P1)

The scope filter is applied by the Extraction Campaign Orchestrator, not by the reporting module. The filter is specified as an option to the extraction CLI:

#### ScopeFilter

| Field | Type | Semantics |
|-------|------|-----------|
| `name_pattern` | glob or regex string, or null | When non-null, only theorems whose fully qualified name matches are extracted |
| `module_prefixes` | list of strings, or null | When non-null, only theorems in modules matching any prefix are extracted |

- MAINTAINS: When both `name_pattern` and `module_prefixes` are set, both must match (conjunction).
- MAINTAINS: When neither is set, all theorems are extracted (default behavior).

> **Given** `name_pattern = ".*comm.*"` and `module_prefixes = ["Coq.Arith"]`
> **When** the filter is applied to theorem `Coq.Arith.PeanoNat.Nat.add_comm`
> **Then** the theorem matches both filters and is included

> **Given** `name_pattern = ".*comm.*"` and `module_prefixes = ["Coq.Arith"]`
> **When** the filter is applied to theorem `Coq.Logic.Classical.classic`
> **Then** the theorem matches the module filter but not the name pattern; it is excluded

### 4.3 Benchmark Subset Generation (P2)

#### generate_benchmarks(extraction_output_path, split_strategy, output_dir)

- REQUIRES: `extraction_output_path` is a valid extraction output. `split_strategy` is one of `"difficulty"`, `"project"`, `"domain"`. `output_dir` is a writable directory.
- ENSURES: Reads ExtractionRecords and writes subset JSON Lines files to `output_dir`.

#### Difficulty split

The system shall classify proofs into difficulty bins:

| Bin | Criteria |
|-----|----------|
| `short` | `total_steps <= 5` |
| `medium` | `6 <= total_steps <= 20` |
| `long` | `total_steps > 20` |

Thresholds are defaults; implementation may accept overrides.

- ENSURES: One output file per bin (`short.jsonl`, `medium.jsonl`, `long.jsonl`). Each file contains only ExtractionRecords matching the bin criteria.

> **Given** 100 proofs: 30 short, 50 medium, 20 long
> **When** difficulty split is applied
> **Then** `short.jsonl` has 30 records, `medium.jsonl` has 50, `long.jsonl` has 20

#### Project split

The system shall group ExtractionRecords by `project_id`.

- ENSURES: One output file per project (`<project_id>.jsonl`).

#### Domain split

The system shall classify proofs by module path prefix heuristic:

| Module prefix pattern | Domain label |
|----------------------|--------------|
| `*Arith*`, `*Nat*`, `*ZArith*` | `arithmetic` |
| `*Algebra*`, `*Ring*`, `*Field*` | `algebra` |
| `*Logic*`, `*Prop*` | `logic` |
| All others | `other` |

- ENSURES: One output file per domain. Patterns are case-insensitive. A proof matching multiple patterns is assigned to the first match.

### 4.4 ML Framework Export (P2)

#### export_to_huggingface(extraction_output_path, output_dir)

- REQUIRES: `extraction_output_path` is a valid extraction output. `output_dir` is a writable directory.
- ENSURES: Converts ExtractionRecords to HuggingFace Datasets format (Arrow/Parquet files + `dataset_info.json`). All ExtractionRecord fields are preserved as dataset columns. The exported dataset is loadable by the `datasets` library.

> **Given** an extraction output with 1000 records
> **When** `export_to_huggingface` is called
> **Then** `output_dir` contains Arrow files and `dataset_info.json` loadable by `datasets.load_from_disk(output_dir)`

### 4.5 Proof Trace Validation (P2)

#### validate_traces(extraction_output_path)

- REQUIRES: `extraction_output_path` is a valid extraction output. Coq is installed.
- ENSURES: For each ExtractionRecord: opens a proof session, replays the tactic sequence from the record, compares resulting proof states against recorded states (goal types and hypothesis names/types). Reports total validated, total failed, and per-failure details.

> **Given** an extraction record with tactic sequence `["intros n.", "induction n.", "simpl.", "reflexivity."]`
> **When** the trace is validated
> **Then** each tactic is replayed against Coq and the resulting proof states are compared against the recorded states

> **Given** a trace where step 2's recorded goal type does not match the replay result
> **When** validation completes
> **Then** the failure is reported with the step index, expected goal, and actual goal

### 4.6 Dataset Deduplication (P2)

#### deduplicate(extraction_output_path)

- REQUIRES: `extraction_output_path` is a valid extraction output.
- ENSURES: Identifies clusters of semantically equivalent proofs. Returns a deduplication report listing each cluster with its member proofs.

The system shall use the following heuristic for equivalence:

1. **Initial goal match**: Two proofs have identical initial goal types (step 0, goal 0, type string equality).
2. **Tactic sequence match**: The tactic sequences are identical after whitespace normalization.

Two proofs matching both criteria are considered semantic duplicates.

- MAINTAINS: Deduplication is symmetric and transitive (clusters, not pairs).

> **Given** proof `A` in project X and proof `B` in project Y with identical initial goals and tactic sequences
> **When** deduplication is run
> **Then** `A` and `B` are clustered together

> **Given** two proofs with identical goals but different tactic sequences
> **When** deduplication is run
> **Then** they are NOT clustered (different proof strategies)

## 5. Error Specification

| Condition | Behavior |
|-----------|----------|
| Input file is not valid JSON Lines | Raises `ValueError` with line number |
| Input contains no ExtractionRecords | Quality report returns zero metrics; benchmark/export produce empty output |
| HuggingFace `datasets` library not installed | Raises `ImportError` with installation instructions |
| Validation replay fails to create session | Marks proof as validation failure; continues with next proof |

## 6. Non-Functional Requirements

- Quality report generation shall process a 100K-record extraction output in < 2 minutes.
- Memory usage for quality reports shall be bounded by accumulator size (counters, histograms), not by input size.
- Benchmark generation shall process the input in a single pass per split strategy.

## 7. Examples

### Quality report output

```json
{
  "premise_coverage": 0.87,
  "proof_length_distribution": {
    "min": 1, "max": 342, "mean": 12.4, "median": 8.0,
    "p25": 4.0, "p75": 16.0, "p95": 45.0
  },
  "tactic_vocabulary": [
    {"tactic": "apply", "count": 24500},
    {"tactic": "rewrite", "count": 18200},
    {"tactic": "simpl", "count": 15800}
  ],
  "per_project": [
    {
      "project_id": "coq-stdlib",
      "premise_coverage": 0.89,
      "proof_length_distribution": {"min": 1, "max": 200, "mean": 10.2, "median": 7.0, "p25": 3.0, "p75": 14.0, "p95": 38.0},
      "theorem_count": 4500
    }
  ]
}
```

### Validation report

```
Validated: 4450 / 4500 (98.9%)
Failed: 50

Failures:
  Coq.Arith.PeanoNat.Nat.foo — step 3: expected goal "n = n", got "n + 0 = n"
  ...
```

## 8. Language-Specific Notes (Python)

- Use `statistics.median`, `statistics.quantiles` for distribution computation.
- Use `re.split(r'\s*;\s*', tactic)` for compound tactic splitting.
- Use `datasets.Dataset.from_dict()` for HuggingFace export.
- Read input files line by line for streaming processing.
- Package location: `src/poule/extraction/reporting.py`.
