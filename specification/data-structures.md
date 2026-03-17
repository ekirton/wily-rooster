# Data Structures

Core data structures shared across the Coq/Rocq semantic lemma search and proof interaction system.

**Architecture**: [expression-tree.md](../doc/architecture/data-models/expression-tree.md), [index-entities.md](../doc/architecture/data-models/index-entities.md), [response-types.md](../doc/architecture/data-models/response-types.md), [proof-types.md](../doc/architecture/data-models/proof-types.md), [extraction-types.md](../doc/architecture/data-models/extraction-types.md)

---

## 1. Purpose

Define the canonical Python types for expression trees, node labels, enumerations, response types, proof interaction types, and extraction types used across all components — extraction, normalization, storage, retrieval, MCP server, proof session management, and batch extraction pipeline.

## 2. Scope

**In scope**: Enumerations (`SortKind`, `DeclKind`, `PremiseKind`, `ErrorKind`), node label hierarchy (abstract base + 15 concrete subtypes), `TreeNode`, `ExprTree`, response types (`SearchResult`, `LemmaDetail`, `Module`), proof interaction types (`Session`, `ProofState`, `Goal`, `Hypothesis`, `ProofTrace`, `TraceStep`, `PremiseAnnotation`, `Premise`, `ProofStateDiff`, `GoalChange`, `HypothesisChange`), extraction types (`ExtractionRecord`, `ExtractionStep`, `ExtractionDiff`, `ExtractionError`, `CampaignMetadata`, `ProjectMetadata`, `ExtractionSummary`, `ProjectSummary`, `FileSummary`, `DependencyEntry`, `DependencyRef`, `QualityReport`, `DistributionStats`, `TacticFrequency`, `ProjectQualityReport`, `ScopeFilter`), and tree utility functions (`recompute_depths`, `assign_node_ids`, `node_count`).

**Out of scope**: Serialization format (owned by storage, proof-serialization, and extraction-output), normalization logic (owned by coq-normalization and cse-normalization), retrieval algorithms, session management logic (owned by proof-session), campaign orchestration (owned by extraction-campaign).

## 3. Definitions

| Term | Definition |
|------|-----------|
| Expression tree | A rooted, ordered tree representing the normalized structure of a single Coq declaration's kernel term |
| Node label | The type tag on a tree node that determines whether it is a leaf or interior node and what payload it carries |
| CSE variable | A placeholder node (`LCseVar`) introduced by Common Subexpression Elimination to replace repeated non-constant subexpressions |
| Qualified name | A fully qualified canonical Coq name (e.g., `Coq.Init.Datatypes.nat`) |

## 4. Behavioral Requirements

### 4.1 Enumerations

#### SortKind

The system shall define a `SortKind` enumeration with exactly three members: `PROP`, `SET`, `TYPE_UNIV`.

#### DeclKind

The system shall define a `DeclKind` enumeration with members: `LEMMA`, `THEOREM`, `DEFINITION`, `INSTANCE`, `INDUCTIVE`, `CONSTRUCTOR`, `AXIOM`. Each member's string value shall be the lowercase form (e.g., `DeclKind.LEMMA` → `"lemma"`).

### 4.2 Node Labels

The system shall define an abstract base `NodeLabel` type that is equality-comparable and hashable. All 15 concrete label subtypes shall inherit from `NodeLabel`.

**Leaf labels** (nodes with zero children):

| Label | Payload | Hashable by |
|-------|---------|-------------|
| `LConst` | `name: str` (fully qualified) | name |
| `LInd` | `name: str` (fully qualified) | name |
| `LConstruct` | `name: str` (parent inductive FQN), `index: int` (≥ 0) | name + index |
| `LCseVar` | `id: int` (≥ 0) | id |
| `LRel` | `index: int` (≥ 0, de Bruijn index) | index |
| `LSort` | `kind: SortKind` | kind |
| `LPrimitive` | `value: int | float` | value |

**Interior labels** (nodes with one or more children):

| Label | Payload | Children constraint |
|-------|---------|---------------------|
| `LApp` | none | Exactly 2 |
| `LAbs` | none | Exactly 1 |
| `LLet` | none | Exactly 2 |
| `LProj` | `name: str` (projection name) | Exactly 1 |
| `LCase` | `ind_name: str` (inductive type name) | At least 1 |
| `LProd` | none | Exactly 2 |
| `LFix` | `mutual_index: int` (≥ 0) | At least 1 |
| `LCoFix` | `mutual_index: int` (≥ 0) | At least 1 |

Each concrete label shall implement `__eq__` and `__hash__` based on its type and payload.

MAINTAINS: Two labels are equal if and only if they have the same concrete type and identical payload values.

### 4.3 TreeNode

The system shall define a `TreeNode` with fields:

| Field | Type | Default |
|-------|------|---------|
| `label` | `NodeLabel` | Required |
| `children` | `list[TreeNode]` | Required (empty list for leaves) |
| `depth` | `int` | 0 (set by `recompute_depths`) |
| `node_id` | `int` | 0 (set by `assign_node_ids`) |

### 4.4 ExprTree

The system shall define an `ExprTree` with fields:

| Field | Type | Constraint |
|-------|------|-----------|
| `root` | `TreeNode` | Required |
| `node_count` | `int` | Required; must be > 0 |

### 4.5 Utility Functions

#### recompute_depths

- REQUIRES: `tree` is a valid `ExprTree`
- ENSURES: `depth` on all nodes is set; root gets 0, each child gets `parent.depth + 1`. Modifies in place.

#### assign_node_ids

- REQUIRES: `tree` is a valid `ExprTree`
- ENSURES: `node_id` on all nodes is set via pre-order traversal (depth-first, parent before children); sequential from 0. Modifies in place.

#### node_count

- REQUIRES: `tree` is a valid `ExprTree`
- ENSURES: Returns total node count (interior + leaf).

### 4.6 Response Types

#### SearchResult

| Field | Type | Constraint |
|-------|------|-----------|
| `name` | `str` | Required; fully qualified canonical name |
| `statement` | `str` | Required |
| `type` | `str` | Required |
| `module` | `str` | Required |
| `kind` | `DeclKind` | Required |
| `score` | `float` | Required; range [0.0, 1.0] |

#### LemmaDetail

Extends `SearchResult` with:

| Field | Type | Constraint |
|-------|------|-----------|
| `dependencies` | `list[str]` | Required; may be empty |
| `dependents` | `list[str]` | Required; may be empty |
| `proof_sketch` | `str` | Required; empty string when unavailable |
| `symbols` | `list[str]` | Required; may be empty |
| `node_count` | `int` | Required; must be > 0 |

#### Module

| Field | Type | Constraint |
|-------|------|-----------|
| `name` | `str` | Required; fully qualified module name |
| `decl_count` | `int` | Required; ≥ 0 |

### 4.7 Proof Interaction Types

Canonical definitions from [proof-types.md](../doc/architecture/data-models/proof-types.md). These types are produced by the Proof Session Manager, serialized by the Proof Serialization layer, and returned by the MCP Server.

#### PremiseKind Enumeration

The system shall define a `PremiseKind` enumeration with exactly four members: `LEMMA`, `HYPOTHESIS`, `CONSTRUCTOR`, `DEFINITION`. Each member's string value shall be the lowercase form (e.g., `PremiseKind.LEMMA` → `"lemma"`).

#### Hypothesis

| Field | Type | Constraint |
|-------|------|-----------|
| `name` | `str` | Required; the hypothesis name as it appears in the proof context |
| `type` | `str` | Required; the hypothesis's type as a Coq expression string |
| `body` | `str` or `None` | Optional; the body for let-bound hypotheses; `None` for non-let hypotheses |

#### Goal

| Field | Type | Constraint |
|-------|------|-----------|
| `index` | `int` | Required; non-negative; position in the parent ProofState's goals list |
| `type` | `str` | Required; the goal's type as a Coq expression string |
| `hypotheses` | `list[Hypothesis]` | Required; may be empty; ordered as Coq presents them |

#### ProofState

| Field | Type | Constraint |
|-------|------|-----------|
| `schema_version` | `int` | Required; positive integer identifying the serialization format version |
| `session_id` | `str` | Required; reference to the owning session |
| `step_index` | `int` | Required; non-negative; 0 = initial state |
| `is_complete` | `bool` | Required; true when no open goals remain |
| `focused_goal_index` | `int` or `None` | Required; index into `goals`; `None` when `is_complete` is true |
| `goals` | `list[Goal]` | Required; may be empty when proof is complete |

#### TraceStep

| Field | Type | Constraint |
|-------|------|-----------|
| `step_index` | `int` | Required; non-negative; 0 for initial state, 1..N for tactic steps |
| `tactic` | `str` or `None` | Required; `None` for step 0; the tactic string for steps 1..N |
| `state` | `ProofState` | Required; the proof state after this step |

#### ProofTrace

| Field | Type | Constraint |
|-------|------|-----------|
| `schema_version` | `int` | Required; positive integer |
| `session_id` | `str` | Required |
| `proof_name` | `str` | Required; fully qualified proof name |
| `file_path` | `str` | Required; absolute path to the .v file |
| `total_steps` | `int` | Required; positive integer (the number of tactics) |
| `steps` | `list[TraceStep]` | Required; length must equal `total_steps + 1` |

#### Premise

| Field | Type | Constraint |
|-------|------|-----------|
| `name` | `str` | Required; fully qualified canonical name |
| `kind` | `str` | Required; one of: `"lemma"`, `"hypothesis"`, `"constructor"`, `"definition"` |

#### PremiseAnnotation

| Field | Type | Constraint |
|-------|------|-----------|
| `step_index` | `int` | Required; positive integer; range [1, N] |
| `tactic` | `str` | Required; the tactic string |
| `premises` | `list[Premise]` | Required; may be empty |

#### Session

| Field | Type | Constraint |
|-------|------|-----------|
| `session_id` | `str` | Required; unique across all active sessions |
| `file_path` | `str` | Required; absolute path to the .v source file |
| `proof_name` | `str` | Required; fully qualified name |
| `current_step` | `int` | Required; non-negative |
| `total_steps` | `int` or `None` | Required; `None` if proof is being constructed interactively |
| `created_at` | `str` | Required; ISO 8601 format |
| `last_active_at` | `str` | Required; ISO 8601 format |

#### GoalChange (P1)

| Field | Type | Constraint |
|-------|------|-----------|
| `index` | `int` | Required; non-negative |
| `before` | `str` | Required; the goal type before the tactic |
| `after` | `str` | Required; the goal type after the tactic |

#### HypothesisChange (P1)

| Field | Type | Constraint |
|-------|------|-----------|
| `name` | `str` | Required |
| `type_before` | `str` | Required |
| `type_after` | `str` | Required |
| `body_before` | `str` or `None` | Required; `None` if not let-bound |
| `body_after` | `str` or `None` | Required; `None` if not let-bound |

#### ProofStateDiff (P1)

| Field | Type | Constraint |
|-------|------|-----------|
| `from_step` | `int` | Required; non-negative |
| `to_step` | `int` | Required; must equal `from_step + 1` |
| `goals_added` | `list[Goal]` | Required; may be empty |
| `goals_removed` | `list[Goal]` | Required; may be empty |
| `goals_changed` | `list[GoalChange]` | Required; may be empty |
| `hypotheses_added` | `list[Hypothesis]` | Required; may be empty |
| `hypotheses_removed` | `list[Hypothesis]` | Required; may be empty |
| `hypotheses_changed` | `list[HypothesisChange]` | Required; may be empty |

### 4.8 Extraction Types

Canonical definitions from [extraction-types.md](../doc/architecture/data-models/extraction-types.md). These types are produced by the Extraction Campaign Orchestrator, serialized by the Extraction Output layer, and consumed by downstream reporting and ML pipelines.

#### ErrorKind Enumeration

The system shall define an `ErrorKind` enumeration with exactly five members: `TIMEOUT`, `BACKEND_CRASH`, `TACTIC_FAILURE`, `LOAD_FAILURE`, `UNKNOWN`. Each member's string value shall be the lowercase form with underscores (e.g., `ErrorKind.BACKEND_CRASH` → `"backend_crash"`).

#### ExtractionRecord

| Field | Type | Constraint |
|-------|------|-----------|
| `schema_version` | `int` | Required; positive integer |
| `record_type` | `str` | Required; literal `"proof_trace"` |
| `theorem_name` | `str` | Required; fully qualified name |
| `source_file` | `str` | Required; path relative to project root |
| `project_id` | `str` | Required |
| `total_steps` | `int` | Required; non-negative |
| `steps` | `list[ExtractionStep]` | Required; length must equal `total_steps + 1` |

- MAINTAINS: `len(steps) == total_steps + 1`. `steps[0].tactic` is `None`. `steps[k].tactic` for k >= 1 is non-null.

#### ExtractionStep

| Field | Type | Constraint |
|-------|------|-----------|
| `step_index` | `int` | Required; non-negative; 0 = initial state |
| `tactic` | `str` or `None` | Required; `None` for step 0 |
| `goals` | `list[Goal]` | Required; reuses Goal from §4.7 |
| `focused_goal_index` | `int` or `None` | Required; `None` when proof is complete |
| `premises` | `list[Premise]` | Required; empty for step 0 |
| `diff` | `ExtractionDiff` or `None` | Required; `None` for step 0 or when diffs disabled (P1) |

#### ExtractionDiff (P1)

| Field | Type | Constraint |
|-------|------|-----------|
| `goals_added` | `list[Goal]` | Required; may be empty |
| `goals_removed` | `list[Goal]` | Required; may be empty |
| `goals_changed` | `list[GoalChange]` | Required; may be empty |
| `hypotheses_added` | `list[Hypothesis]` | Required; may be empty |
| `hypotheses_removed` | `list[Hypothesis]` | Required; may be empty |
| `hypotheses_changed` | `list[HypothesisChange]` | Required; may be empty |

Structurally identical to ProofStateDiff (§4.7) but omits `from_step` and `to_step` (implicit from the containing ExtractionStep's `step_index`).

#### ExtractionError

| Field | Type | Constraint |
|-------|------|-----------|
| `schema_version` | `int` | Required; positive integer |
| `record_type` | `str` | Required; literal `"extraction_error"` |
| `theorem_name` | `str` | Required; fully qualified name |
| `source_file` | `str` | Required; path relative to project root |
| `project_id` | `str` | Required |
| `error_kind` | `str` | Required; one of: `"timeout"`, `"backend_crash"`, `"tactic_failure"`, `"load_failure"`, `"unknown"` |
| `error_message` | `str` | Required; human-readable description |

#### CampaignMetadata

| Field | Type | Constraint |
|-------|------|-----------|
| `schema_version` | `int` | Required; positive integer |
| `record_type` | `str` | Required; literal `"campaign_metadata"` |
| `extraction_tool_version` | `str` | Required; semantic version string |
| `extraction_timestamp` | `str` | Required; ISO 8601 with seconds precision and `Z` suffix |
| `projects` | `list[ProjectMetadata]` | Required; non-empty |

#### ProjectMetadata

| Field | Type | Constraint |
|-------|------|-----------|
| `project_id` | `str` | Required; unique within a campaign |
| `project_path` | `str` | Required; absolute path |
| `coq_version` | `str` | Required |
| `commit_hash` | `str` or `None` | Required; `None` if not a git repository |

#### ExtractionSummary

| Field | Type | Constraint |
|-------|------|-----------|
| `schema_version` | `int` | Required; positive integer |
| `record_type` | `str` | Required; literal `"extraction_summary"` |
| `total_theorems_found` | `int` | Required; non-negative |
| `total_extracted` | `int` | Required; non-negative |
| `total_failed` | `int` | Required; non-negative |
| `total_skipped` | `int` | Required; non-negative |
| `per_project` | `list[ProjectSummary]` | Required |

- MAINTAINS: `total_extracted + total_failed + total_skipped == total_theorems_found`.

#### ProjectSummary

| Field | Type | Constraint |
|-------|------|-----------|
| `project_id` | `str` | Required |
| `theorems_found` | `int` | Required; non-negative |
| `extracted` | `int` | Required; non-negative |
| `failed` | `int` | Required; non-negative |
| `skipped` | `int` | Required; non-negative |
| `per_file` | `list[FileSummary]` | Required |

- MAINTAINS: `extracted + failed + skipped == theorems_found`.

#### FileSummary

| Field | Type | Constraint |
|-------|------|-----------|
| `source_file` | `str` | Required; path relative to project root |
| `theorems_found` | `int` | Required; non-negative |
| `extracted` | `int` | Required; non-negative |
| `failed` | `int` | Required; non-negative |
| `skipped` | `int` | Required; non-negative |

- MAINTAINS: `extracted + failed + skipped == theorems_found`.

#### DependencyEntry (P1)

| Field | Type | Constraint |
|-------|------|-----------|
| `theorem_name` | `str` | Required; fully qualified name |
| `source_file` | `str` | Required; path relative to project root |
| `project_id` | `str` | Required |
| `depends_on` | `list[DependencyRef]` | Required; deduplicated by name, ordered by first appearance |

#### DependencyRef (P1)

| Field | Type | Constraint |
|-------|------|-----------|
| `name` | `str` | Required; fully qualified name |
| `kind` | `str` | Required; one of: `"theorem"`, `"lemma"`, `"definition"`, `"axiom"`, `"constructor"`, `"inductive"` |

#### QualityReport (P1)

| Field | Type | Constraint |
|-------|------|-----------|
| `premise_coverage` | `float` | Required; range [0.0, 1.0] |
| `proof_length_distribution` | `DistributionStats` | Required |
| `tactic_vocabulary` | `list[TacticFrequency]` | Required; sorted by `count` descending |
| `per_project` | `list[ProjectQualityReport]` | Required |

#### DistributionStats (P1)

| Field | Type | Constraint |
|-------|------|-----------|
| `min` | `int` | Required; non-negative |
| `max` | `int` | Required; non-negative |
| `mean` | `float` | Required |
| `median` | `float` | Required |
| `p25` | `float` | Required; 25th percentile |
| `p75` | `float` | Required; 75th percentile |
| `p95` | `float` | Required; 95th percentile |

#### TacticFrequency (P1)

| Field | Type | Constraint |
|-------|------|-----------|
| `tactic` | `str` | Required; lowercased keyword |
| `count` | `int` | Required; positive |

#### ProjectQualityReport (P1)

| Field | Type | Constraint |
|-------|------|-----------|
| `project_id` | `str` | Required |
| `premise_coverage` | `float` | Required; range [0.0, 1.0] |
| `proof_length_distribution` | `DistributionStats` | Required |
| `theorem_count` | `int` | Required; non-negative |

#### ScopeFilter (P1)

| Field | Type | Constraint |
|-------|------|-----------|
| `name_pattern` | `str` or `None` | Optional; glob or regex pattern for theorem name matching |
| `module_prefixes` | `list[str]` or `None` | Optional; list of module prefixes to include |

- MAINTAINS: When both fields are set, both must match (conjunction). When neither is set, all theorems are included.

## 5. Data Model

All entities defined in this specification are value types with no persistence logic. Expression tree and response types are serialized/deserialized by the storage layer and produced by the retrieval pipeline. Proof interaction types are produced by the session manager and serialized by the proof serialization layer. Extraction types are produced by the campaign orchestrator and serialized by the extraction output layer.

## 6. Interface Contracts

### Tree utility functions

| Function | Input | Output | Error |
|----------|-------|--------|-------|
| `recompute_depths(tree)` | `ExprTree` | `None` (mutates in place) | None — always succeeds on valid trees |
| `assign_node_ids(tree)` | `ExprTree` | `None` (mutates in place) | None — always succeeds on valid trees |
| `node_count(tree)` | `ExprTree` | `int` | None — always succeeds on valid trees |

## 7. Error Specification

### Validation errors

| Condition | Error |
|-----------|-------|
| `LCseVar.id < 0` | `ValueError`: CSE variable ID must be non-negative |
| `LRel.index < 0` | `ValueError`: de Bruijn index must be non-negative |
| `LConstruct.index < 0` | `ValueError`: constructor index must be non-negative |
| `LFix.mutual_index < 0` | `ValueError`: mutual index must be non-negative |
| `LCoFix.mutual_index < 0` | `ValueError`: mutual index must be non-negative |
| `ExprTree.node_count < 1` | `ValueError`: node count must be positive |

Validation shall occur at construction time.

### Proof type validation errors

| Condition | Error |
|-----------|-------|
| `Premise.kind` not in `{"lemma", "hypothesis", "constructor", "definition"}` | `ValueError`: kind must be one of lemma, hypothesis, constructor, definition |

### Extraction type validation errors

| Condition | Error |
|-----------|-------|
| `ExtractionRecord` with `len(steps) != total_steps + 1` | `ValueError`: step count mismatch |
| `ExtractionStep` at index 0 with non-null tactic | `ValueError`: step 0 must have null tactic |
| `ExtractionStep` at index > 0 with null tactic | `ValueError`: steps 1..N must have non-null tactic |
| `ExtractionError.error_kind` not in valid set | `ValueError`: error_kind must be one of timeout, backend_crash, tactic_failure, load_failure, unknown |
| `DependencyRef.kind` not in valid set | `ValueError`: kind must be one of theorem, lemma, definition, axiom, constructor, inductive |

## 8. Examples

### Creating a simple expression tree

Given a Coq term `Nat.add`:

```
tree = ExprTree(
    root=TreeNode(label=LConst("Coq.Init.Nat.add"), children=[]),
    node_count=1
)
```

### Binary application after currification

Given `Nat.add 1 2` (currified to `LApp(LApp(Nat.add, 1), 2)`):

```
inner = TreeNode(label=LApp(), children=[
    TreeNode(label=LConst("Coq.Init.Nat.add"), children=[]),
    TreeNode(label=LPrimitive(1), children=[])
])
outer = TreeNode(label=LApp(), children=[inner,
    TreeNode(label=LPrimitive(2), children=[])
])
tree = ExprTree(root=outer, node_count=5)
recompute_depths(tree)  # root.depth=0, inner.depth=1, leaves.depth=2
assign_node_ids(tree)   # pre-order: outer=0, inner=1, Nat.add=2, 1=3, 2=4
```

### Equality semantics

```
LConst("Coq.Init.Nat.add") == LConst("Coq.Init.Nat.add")  # True
LConst("Coq.Init.Nat.add") == LInd("Coq.Init.Nat.add")    # False (different types)
LSort(SortKind.PROP) == LSort(SortKind.PROP)                # True
hash(LConst("x")) == hash(LConst("x"))                      # True
```

### Creating proof interaction types

```
state = ProofState(
    schema_version=1, session_id="abc-123", step_index=0,
    is_complete=False, focused_goal_index=0,
    goals=[Goal(index=0, type="n + m = m + n",
        hypotheses=[
            Hypothesis(name="n", type="nat", body=None),
            Hypothesis(name="m", type="nat", body=None),
        ]
    )]
)
```

### Premise with valid kind

```
Premise(name="Coq.Arith.PeanoNat.Nat.add_comm", kind="lemma")      # valid
Premise(name="IHn", kind="hypothesis")                               # valid
```

### ProofStateDiff

```
diff = ProofStateDiff(
    from_step=2, to_step=3,
    goals_added=[], goals_removed=[],
    goals_changed=[GoalChange(index=0, before="S n + m = m + S n", after="S (n + m) = m + S n")],
    hypotheses_added=[Hypothesis(name="H", type="n + m = m + n", body=None)],
    hypotheses_removed=[], hypotheses_changed=[],
)
```

### Creating extraction types

```
record = ExtractionRecord(
    schema_version=1, record_type="proof_trace",
    theorem_name="Coq.Init.Logic.eq_refl", source_file="theories/Init/Logic.v",
    project_id="coq-stdlib", total_steps=1,
    steps=[
        ExtractionStep(step_index=0, tactic=None,
            goals=[Goal(index=0, type="x = x", hypotheses=[
                Hypothesis(name="A", type="Type", body=None),
                Hypothesis(name="x", type="A", body=None),
            ])],
            focused_goal_index=0, premises=[], diff=None),
        ExtractionStep(step_index=1, tactic="reflexivity.",
            goals=[], focused_goal_index=None, premises=[], diff=None),
    ]
)
```

### ExtractionError

```
error = ExtractionError(
    schema_version=1, record_type="extraction_error",
    theorem_name="Coq.Arith.PeanoNat.Nat.sub_diag",
    source_file="theories/Arith/PeanoNat.v", project_id="coq-stdlib",
    error_kind="timeout", error_message="Proof extraction exceeded 60s time limit"
)
```

### DependencyEntry

```
entry = DependencyEntry(
    theorem_name="Coq.Arith.PeanoNat.Nat.add_comm",
    source_file="theories/Arith/PeanoNat.v", project_id="coq-stdlib",
    depends_on=[
        DependencyRef(name="Coq.Arith.PeanoNat.Nat.add_0_r", kind="lemma"),
        DependencyRef(name="Coq.Init.Datatypes.nat", kind="inductive"),
    ]
)
```

## 9. Language-Specific Notes (Python)

- Use `@dataclass(frozen=True)` for all node label types to get `__eq__` and `__hash__` for free.
- Use `@dataclass` (mutable) for `TreeNode` since `depth` and `node_id` are mutated in place.
- Use `@dataclass` (mutable) for `ExprTree` since `node_count` may be recomputed after CSE.
- Use `enum.Enum` for `SortKind`, `DeclKind`, and `PremiseKind`.
- Use `@dataclass(frozen=True)` for `SearchResult`, `LemmaDetail`, and `Module` — response types are immutable once created.
- Use `@dataclass` (mutable) for proof interaction types — `ProofState`, `Goal`, `Hypothesis`, `TraceStep`, `ProofTrace`, `PremiseAnnotation`, `Premise`, `Session`, `GoalChange`, `HypothesisChange`, `ProofStateDiff`.
- Use `@dataclass(frozen=True)` for extraction types that are immutable once created — `ExtractionRecord`, `ExtractionStep`, `ExtractionDiff`, `ExtractionError`, `CampaignMetadata`, `ProjectMetadata`, `ExtractionSummary`, `ProjectSummary`, `FileSummary`, `DependencyEntry`, `DependencyRef`, `QualityReport`, `DistributionStats`, `TacticFrequency`, `ProjectQualityReport`, `ScopeFilter`.
- Use `enum.Enum` for `ErrorKind`.
- Proof interaction types package location: `src/poule/session/types.py`.
- Expression tree and response types package location: `src/poule/models/`.
- Extraction types package location: `src/poule/extraction/types.py`.
