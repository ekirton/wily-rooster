# Extraction Dependency Graph

How theorem-level dependency graphs are extracted from Coq projects: which theorems, definitions, and axioms each proof depends on.

**Feature**: [Dependency Graph Extraction](../features/dependency-graph-extraction.md)
**Data models**: [extraction-types.md](data-models/extraction-types.md) (DependencyEntry, DependencyRef)

---

## Extraction Pipeline

```
extract_dependency_graph(project_dir, output_path)
  │
  ├─ Enumerate all provable theorems in the project
  │    (same enumeration as extraction campaign)
  │
  ├─ For each theorem:
  │    ├─ Extract the proof trace (reuse campaign extraction or read from prior output)
  │    │
  │    ├─ Collect all premises across all tactic steps
  │    │    (union of per-step premise lists from ExtractionRecord)
  │    │
  │    ├─ Resolve each premise to its declaration kind:
  │    │    lemma/theorem → DependencyRef(kind="theorem" or "lemma")
  │    │    definition    → DependencyRef(kind="definition")
  │    │    axiom         → DependencyRef(kind="axiom")
  │    │    constructor   → DependencyRef(kind="constructor")
  │    │    inductive     → DependencyRef(kind="inductive")
  │    │    hypothesis    → excluded (local, not a cross-theorem dependency)
  │    │
  │    ├─ Deduplicate premises by fully qualified name
  │    │
  │    └─ Emit DependencyEntry for this theorem
  │
  └─ Output: one DependencyEntry per theorem, JSON Lines format
```

## Relationship to Premise Annotations

The dependency graph is derived from premise annotations, not computed independently. For each theorem, the graph entry is the union of all premises across all tactic steps, excluding local hypotheses (which are proof-internal, not cross-theorem dependencies).

This means:
- Dependency graph quality is bounded by premise annotation quality
- Proofs with ExtractionError records have no dependency entry
- Proofs with incomplete premise annotations have incomplete dependency entries

## Hypothesis Exclusion

Local hypotheses (`kind: "hypothesis"`) are excluded from the dependency graph because they are proof-internal — they exist only within the proof's context and do not represent dependencies on external declarations. A hypothesis named `H : n + m = m + n` is a local assumption, not a reference to an external theorem.

## Output Format

Dependency entries are emitted as JSON Lines, one entry per theorem:

```json
{
  "theorem_name": "Coq.Arith.PeanoNat.Nat.add_comm",
  "source_file": "theories/Arith/PeanoNat.v",
  "project_id": "coq-stdlib",
  "depends_on": [
    {"name": "Coq.Arith.PeanoNat.Nat.add_0_r", "kind": "lemma"},
    {"name": "Coq.Arith.PeanoNat.Nat.add_succ_r", "kind": "lemma"},
    {"name": "Coq.Init.Datatypes.nat", "kind": "inductive"},
    {"name": "Coq.Init.Datatypes.S", "kind": "constructor"}
  ]
}
```

### Ordering

- Entries are ordered by theorem (same deterministic order as extraction records)
- `depends_on` entries are ordered by first appearance across the proof's tactic steps, then deduplicated

## Integration with Extraction Campaign

Dependency graph extraction can run in two modes:

1. **Inline with extraction**: Computed during the extraction campaign, emitted as a separate output file alongside the JSON Lines trace output
2. **Post-hoc from extraction output**: Computed from a previously produced JSON Lines file by reading ExtractionRecords and aggregating premises

Mode 1 avoids re-reading the output file but couples graph extraction to the campaign. Mode 2 is more flexible — it can be run on any extraction output without re-running the campaign.

## Integration with Search Index

The dependency graph produced by extraction campaigns provides theorem-to-theorem edges that cannot be obtained from `.vo`-only analysis (`Print Assumptions` returns axiom-level assumptions, not the theorems a proof invokes). These edges are the primary data source for deep dependency analysis tools (impact analysis, transitive closure, cycle detection).

### Import pipeline

```
import_dependencies(dependency_graph_path, index_db_path)
  │
  ├─ Open existing index database (read/write)
  │
  ├─ Read JSON Lines dependency graph file
  │
  ├─ For each DependencyEntry:
  │    ├─ Resolve theorem_name to declaration ID in index
  │    │
  │    ├─ For each DependencyRef in depends_on:
  │    │    ├─ Resolve ref.name to declaration ID in index
  │    │    │    (exact match, then suffix match against indexed FQNs)
  │    │    │
  │    │    ├─ Skip unresolvable names (dependency outside indexed scope)
  │    │    │
  │    │    └─ Insert (src_id, dst_id, "uses") into dependencies table
  │    │
  │    └─ Deduplicate edges by (src, dst, relation)
  │
  └─ Commit
```

### Relationship to existing dependency sources

The index build pipeline (`run_extraction`) already inserts dependency edges from three sources: tree-based `LConst` extraction, `Print Assumptions` output, and symbol-set cross-referencing. All three derive from type signatures and axiom-level assumptions — none capture proof-body dependencies for opaque theorems.

Premise-based import adds a fourth source that captures the actual theorems and definitions each proof uses. Edges from all four sources are merged and deduplicated by `(src, dst, relation)` in the `dependencies` table's primary key.

### When to run

Import runs after both the index build and the extraction campaign complete. The index must exist (provides the declaration ID mapping). The dependency graph file must exist (provides the edges). The import is idempotent — running it again on the same data produces no duplicate edges due to the primary key constraint.

## Design Rationale

### Why derive from premises rather than independent static analysis

Static analysis of Coq source could identify `Require Import` statements and `apply`/`rewrite` targets, but this misses implicit dependencies (type class resolution, canonical structures, coercions) and includes unused imports. Premise annotations capture what the proof actually used — the dynamic dependency set. This produces a more accurate graph for ML consumption.

### Why exclude hypotheses from the graph

Graph-based premise selection models predict which existing library results are relevant to a goal. Local hypotheses are not library results — they are proof-internal bindings. Including them would add noise to the graph without retrieval signal.

### Why per-theorem granularity rather than per-step

A per-step dependency graph (step k depends on premises P1, P2) would duplicate information already present in the ExtractionRecord's per-step premise lists. The dependency graph's value is the aggregated view: theorem T depends on theorems A, B, C. This aggregation is what graph neural networks consume for premise retrieval.
