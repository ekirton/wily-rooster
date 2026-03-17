# Deep Dependency Analysis

Transitive closure, impact analysis, cycle detection (Tarjan SCC), and module-level summaries over the Coq dependency graph, built from Storage or coq-dpdgraph output.

**Architecture**: [deep-dependency-analysis.md](../doc/architecture/deep-dependency-analysis.md), [component-boundaries.md](../doc/architecture/component-boundaries.md), [data-models/index-entities.md](../doc/architecture/data-models/index-entities.md)

---

## 1. Purpose

Define the deep dependency analysis engine that constructs an in-memory dependency graph from indexed Storage or coq-dpdgraph DOT files, then answers transitive queries — forward closure, reverse closure (impact analysis), cycle detection, and module-level aggregation — over that graph. Results integrate with the existing Mermaid Renderer for visualization via pre-resolved adjacency lists.

## 2. Scope

**In scope**: Graph construction from Storage and DOT files, graph caching and invalidation, transitive closure (forward BFS), impact analysis (reverse BFS), depth and scope filtering, cycle detection (Tarjan SCC), module-level aggregation and metrics, data model for all result types, error handling.

**Out of scope**: MCP protocol handling (owned by mcp-server), storage management (owned by storage), Mermaid diagram generation (owned by mermaid-renderer), one-hop `find_related` queries (owned by pipeline), coq-dpdgraph invocation (external tool; this component consumes its output).

## 3. Definitions

| Term | Definition |
|------|-----------|
| Forward adjacency | For declaration A, the set of declarations that A directly depends on (A uses B) |
| Reverse adjacency | For declaration A, the set of declarations that directly depend on A (B uses A) |
| Transitive closure | The set of all declarations reachable by following forward edges from a root, across any number of hops |
| Impact set | The set of all declarations reachable by following reverse edges from a root — declarations transitively affected by changes to the root |
| Strongly connected component (SCC) | A maximal set of declarations where every member is reachable from every other member via directed edges |
| Module | The dot-separated prefix of a fully qualified Coq declaration name, excluding the final component |
| Scope filter | A predicate that restricts which declarations are visited during graph traversal |
| Depth map | A mapping from BFS depth level (non-negative integer) to the set of declarations discovered at that level |
| DOT file | A Graphviz-format file produced by `coq-dpdgraph dpd2dot`, containing directed dependency edges between Coq declarations |

## 4. Behavioral Requirements

### 4.1 Graph Construction

#### build_graph_from_storage(index_reader)

- REQUIRES: `index_reader` provides read access to a valid index database containing `declarations` and `dependencies` tables.
- ENSURES: Returns a `DependencyGraph` containing all declarations and all edges where `relation = 'uses'`. Every edge `(src, dst)` appears in both `forward_adj[src]` and `reverse_adj[dst]`. Metadata (module, kind) is populated for every declaration in the graph.
- MAINTAINS: The index database is not modified. All reads are within a single consistent snapshot.

> **Given** an index database with declarations `A`, `B`, `C` and edges `A uses B`, `B uses C`
> **When** `build_graph_from_storage(index_reader)` is called
> **Then** the returned graph has `forward_adj[A] = {B}`, `forward_adj[B] = {C}`, `reverse_adj[B] = {A}`, `reverse_adj[C] = {B}`, and `node_count = 3`, `edge_count = 2`

> **Given** an index database with no `uses` edges
> **When** `build_graph_from_storage(index_reader)` is called
> **Then** the returned graph has all declarations as isolated nodes, `edge_count = 0`, and all adjacency sets are empty

#### build_graph_from_dpdgraph(dot_file_path)

- REQUIRES: `dot_file_path` is a path to a file in DOT format produced by `coq-dpdgraph dpd2dot`.
- ENSURES: Returns a `DependencyGraph` with the same structural guarantees as `build_graph_from_storage`. Node names are fully qualified Coq identifiers extracted from DOT node declarations. Module names are inferred from the qualified name prefix (everything up to the last dot-separated component).
- MAINTAINS: The DOT file is not modified.

> **Given** a DOT file containing nodes `"Coq.Arith.Plus.add_comm"` and `"Coq.Arith.Plus.add_assoc"` with a directed edge between them
> **When** `build_graph_from_dpdgraph(path)` is called
> **Then** the returned graph contains both declarations with module `Coq.Arith.Plus` and the corresponding forward and reverse adjacency entries

> **Given** a DOT file with malformed syntax (missing closing brace)
> **When** `build_graph_from_dpdgraph(path)` is called
> **Then** a `PARSE_ERROR` is returned with details describing the syntax problem

#### Source Selection

When both an index database and a DOT file path are available, the caller selects the source explicitly. When only one source is available, that source is used. When neither source is available, the engine returns an `INDEX_MISSING` error.

### 4.2 Graph Cache

The engine shall cache the in-memory `DependencyGraph` per project, keyed by the source identifier (index database path or DOT file path).

- When a cached graph exists for the requested source, the engine shall validate the cache before reuse.
- When the index database's `schema_version` or `created_at` timestamp differs from the cached values, the engine shall invalidate the cache and rebuild the graph.
- When a different DOT file path is provided than the cached one, the engine shall invalidate the cache and rebuild.
- The cache shall hold at most one graph per distinct project key. The cache is process-scoped and not persisted across server restarts.

> **Given** a cached graph built from index database at path `/project/index.db` with `created_at = T1`
> **When** a query arrives and `created_at` is now `T2` (database was rebuilt)
> **Then** the cache is invalidated and the graph is reconstructed from the updated database

### 4.3 Transitive Closure

#### transitive_closure(graph, root, max_depth, scope_filter)

- REQUIRES: `graph` is a constructed `DependencyGraph`. `root` is a fully qualified declaration name present in `graph.forward_adj`. `max_depth` is a positive integer or null (null means unlimited). `scope_filter` is a list of filter predicates (empty list means no filtering).
- ENSURES: Returns a `TransitiveClosure` containing all declarations reachable from `root` via forward edges, respecting depth and scope constraints. The root is always included at depth 0. The `depth_map` assigns each reachable declaration to the earliest BFS level at which it was discovered. The `edges` set contains all edges `(u, v)` where both `u` and `v` are in the closure.
- MAINTAINS: The graph is not modified. BFS traversal visits each node at most once.

When `root` is not found in the graph, the engine shall return a `NOT_FOUND` error.

When `max_depth` is 1, the result shall contain exactly the same declaration set as `find_related(root, "uses")`.

> **Given** a graph with edges `A → B → C → D` and no scope filter
> **When** `transitive_closure(graph, "A", max_depth=null, scope_filter=[])` is called
> **Then** `nodes = {A, B, C, D}`, `depth_map = {0: {A}, 1: {B}, 2: {C}, 3: {D}}`, `total_depth = 3`

> **Given** a graph with edges `A → B → C → D`
> **When** `transitive_closure(graph, "A", max_depth=2, scope_filter=[])` is called
> **Then** `nodes = {A, B, C}`, `depth_map = {0: {A}, 1: {B}, 2: {C}}`, `total_depth = 2` (D is not reached)

> **Given** a graph with edges `A → B → C` where B is in module `Coq.Init` and C is in module `Coq.Arith`
> **When** `transitive_closure(graph, "A", max_depth=null, scope_filter=[exclude_prefix("Coq.Init")])` is called
> **Then** `nodes = {A}` (B is excluded by filter, so C is not reachable)

### 4.4 Scope Filtering

Scope filters restrict which nodes are followed during BFS traversal. Multiple filters compose as a conjunction (all must pass for a node to be included).

| Filter | Predicate |
|--------|-----------|
| `module_prefix(prefix)` | Include only nodes whose module starts with `prefix` |
| `exclude_prefix(prefix)` | Exclude nodes whose module starts with `prefix` |
| `same_project` | Include only nodes whose top-level module namespace matches the root's top-level namespace |

- REQUIRES: Each filter predicate receives a fully qualified declaration name and the graph's metadata.
- ENSURES: A node is visited during BFS only when all active filter predicates return true for that node.
- MAINTAINS: The root node is always included regardless of filter predicates. Filters apply only to neighbors during expansion.

> **Given** filters `[module_prefix("Coq.Arith"), exclude_prefix("Coq.Arith.Div")]`
> **When** evaluating node `Coq.Arith.Plus.add_comm`
> **Then** the node passes (starts with `Coq.Arith`, does not start with `Coq.Arith.Div`)

> **Given** filter `[same_project]` and root in module `MyLib.Foo`
> **When** evaluating node `Coq.Init.Nat.add`
> **Then** the node is excluded (top-level namespace `Coq` differs from `MyLib`)

### 4.5 Impact Analysis

#### impact_analysis(graph, root, max_depth, scope_filter)

- REQUIRES: `graph` is a constructed `DependencyGraph`. `root` is a fully qualified declaration name. `max_depth` is a positive integer or null. `scope_filter` is a list of filter predicates.
- ENSURES: Returns an `ImpactSet` containing all declarations that transitively depend on `root`, computed by BFS over `reverse_adj`. The depth map indicates how many hops separate each impacted declaration from the root. Depth 1 nodes are direct dependents.
- MAINTAINS: The graph is not modified.

When `root` exists in the graph but has no reverse edges, the engine shall return an `ImpactSet` with `impacted_nodes = {root}` and `total_depth = 0`.

When `root` is not found in the graph, the engine shall return a `NOT_FOUND` error.

When `max_depth` is 1, the result shall contain exactly the same declaration set as `find_related(root, "used_by")`.

> **Given** a graph with edges `A → C`, `B → C`, `C → D` (A and B use C, C uses D)
> **When** `impact_analysis(graph, "D", max_depth=null, scope_filter=[])` is called
> **Then** `impacted_nodes = {D, C, A, B}`, `depth_map = {0: {D}, 1: {C}, 2: {A, B}}`, `total_depth = 2`

> **Given** a graph where declaration `X` has no dependents
> **When** `impact_analysis(graph, "X", max_depth=null, scope_filter=[])` is called
> **Then** `impacted_nodes = {X}`, `total_depth = 0`

### 4.6 Cycle Detection

#### detect_cycles(graph)

- REQUIRES: `graph` is a constructed `DependencyGraph`.
- ENSURES: Returns a `CycleReport` containing all strongly connected components (SCCs) with more than one member, identified using Tarjan's algorithm in O(V + E) time. Each SCC is an ordered list of participants, rotated to start with the lexicographically smallest member for canonical ordering. `is_acyclic` is true when no non-trivial SCCs exist.
- MAINTAINS: The graph is not modified. Every node and edge is visited exactly once.

> **Given** a graph with edges `A → B → C → A` (a 3-node cycle) and `D → E` (no cycle)
> **When** `detect_cycles(graph)` is called
> **Then** `cycles = [[A, B, C]]` (rotated to start with A), `total_cycle_count = 1`, `total_nodes_in_cycles = 3`, `is_acyclic = false`

> **Given** a graph with edges `A → B → C` (acyclic)
> **When** `detect_cycles(graph)` is called
> **Then** `cycles = []`, `total_cycle_count = 0`, `is_acyclic = true`

> **Given** a graph with two disjoint cycles: `A → B → A` and `C → D → E → C`
> **When** `detect_cycles(graph)` is called
> **Then** `cycles` contains both `[A, B]` and `[C, D, E]`, `total_cycle_count = 2`, `total_nodes_in_cycles = 5`

### 4.7 Module-Level Aggregation

#### module_summary(graph)

- REQUIRES: `graph` is a constructed `DependencyGraph` with metadata populated for all nodes.
- ENSURES: Returns a `ModuleSummary` with module-level forward adjacency, per-module metrics (fan_in, fan_out, internal_nodes), and module-level cycle detection. Self-edges (intra-module dependencies) are excluded from the module graph. Module-level SCCs are computed by applying Tarjan's algorithm to the projected module graph.
- MAINTAINS: The declaration-level graph is not modified.

> **Given** declarations `Foo.A`, `Foo.B`, `Bar.C` with edges `Foo.A → Foo.B`, `Foo.A → Bar.C`
> **When** `module_summary(graph)` is called
> **Then** module `Foo` has `fan_out = 1` (depends on `Bar`), `fan_in = 0`, `internal_nodes = 2`. Module `Bar` has `fan_out = 0`, `fan_in = 1`, `internal_nodes = 1`. The `Foo.A → Foo.B` edge is excluded from the module graph (intra-module).

> **Given** modules `M1 → M2 → M3 → M1` (module-level cycle)
> **When** `module_summary(graph)` is called
> **Then** `module_cycles = [[M1, M2, M3]]`

### 4.8 Result Size Safety

When a transitive closure or impact analysis result exceeds 10,000 nodes, the engine shall return a `RESULT_TOO_LARGE` error with the actual count and the limit. The caller should retry with `max_depth` or `scope_filter` to narrow the result.

## 5. Data Model

### DependencyGraph

| Field | Type | Constraints |
|-------|------|-------------|
| `forward_adj` | map of qualified name to set of qualified names | Required; for each declaration, declarations it directly depends on |
| `reverse_adj` | map of qualified name to set of qualified names | Required; for each declaration, declarations that directly depend on it |
| `metadata` | map of qualified name to NodeMetadata | Required; one entry per declaration in the graph |
| `node_count` | non-negative integer | Required; equals number of keys in `metadata` |
| `edge_count` | non-negative integer | Required; equals total number of entries across all `forward_adj` value sets |

### NodeMetadata

| Field | Type | Constraints |
|-------|------|-------------|
| `module` | qualified name | Required; module containing the declaration |
| `kind` | enumeration: `lemma`, `theorem`, `definition`, `inductive`, `constructor`, `record`, `class`, `instance`, `notation`, `tactic`, `axiom` | Required |

### TransitiveClosure

| Field | Type | Constraints |
|-------|------|-------------|
| `root` | qualified name | Required; the declaration whose closure was computed |
| `nodes` | set of qualified names | Required; all declarations in the closure including root; size >= 1 |
| `edges` | set of (qualified name, qualified name) pairs | Required; all edges within the closure subgraph |
| `depth_map` | map of non-negative integer to set of qualified names | Required; key 0 always contains exactly `{root}` |
| `total_depth` | non-negative integer | Required; maximum depth reached |

### ImpactSet

| Field | Type | Constraints |
|-------|------|-------------|
| `root` | qualified name | Required; the declaration whose impact was analyzed |
| `impacted_nodes` | set of qualified names | Required; all declarations transitively depending on root including root; size >= 1 |
| `edges` | set of (qualified name, qualified name) pairs | Required; all reverse edges within the impact subgraph |
| `depth_map` | map of non-negative integer to set of qualified names | Required; key 0 always contains exactly `{root}` |
| `total_depth` | non-negative integer | Required; maximum reverse depth reached |

### CycleReport

| Field | Type | Constraints |
|-------|------|-------------|
| `cycles` | list of lists of qualified names | Required; each inner list is one SCC with size >= 2, rotated to start with the lexicographically smallest member |
| `total_cycle_count` | non-negative integer | Required; equals length of `cycles` |
| `total_nodes_in_cycles` | non-negative integer | Required; sum of inner list lengths |
| `is_acyclic` | boolean | Required; true when `total_cycle_count = 0` |

### ModuleSummary

| Field | Type | Constraints |
|-------|------|-------------|
| `modules` | map of module name to ModuleMetrics | Required; one entry per distinct module |
| `module_edges` | map of module name to set of module names | Required; module-level forward adjacency; excludes self-edges |
| `module_cycles` | list of lists of module names | Required; module-level SCCs with size >= 2 |
| `total_modules` | non-negative integer | Required; equals number of keys in `modules` |

### ModuleMetrics

| Field | Type | Constraints |
|-------|------|-------------|
| `fan_in` | non-negative integer | Required; number of modules that depend on this module |
| `fan_out` | non-negative integer | Required; number of modules this module depends on |
| `internal_nodes` | positive integer | Required; number of declarations in this module; >= 1 |

## 6. Interface Contracts

### MCP Server -> Deep Dependency Analysis Engine

| Property | Value |
|----------|-------|
| Mechanism | Internal function calls (in-process) |
| Direction | Request-response (synchronous) |
| Input | Query type (`closure`, `impact`, `cycles`, `module_summary`) + parameters (`root`, `max_depth`, `scope_filter`, `source`) |
| Output | `TransitiveClosure`, `ImpactSet`, `CycleReport`, or `ModuleSummary` |
| Error strategy | All errors returned as structured error values with error code and message; caller formats for MCP |
| Concurrency | Serialized; one query at a time per graph instance |
| Idempotency | All query operations are idempotent and side-effect-free on the graph |

### Deep Dependency Analysis Engine -> Storage

| Property | Value |
|----------|-------|
| Mechanism | SQLite queries via existing IndexReader |
| Direction | Read-only |
| Tables read | `declarations`, `dependencies` |
| Error strategy | Database read errors propagate as `INDEX_MISSING` or connection-level errors |
| Concurrency | Single reader; no write contention |

### Deep Dependency Analysis Engine -> Mermaid Renderer (via MCP Server)

The engine does not call the Mermaid Renderer directly. The MCP Server extracts adjacency lists from engine results and passes them to `render_dependencies`. The renderer's contract (adjacency list in, Mermaid text out) is unchanged.

## 7. Error Specification

### 7.1 Input Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| `root` declaration not found in graph | `NOT_FOUND` | Return error with message: Declaration `{name}` not found in the dependency graph |
| `max_depth` <= 0 | Clamp to 1 | No error; treat as depth-limited to 1 |
| Empty `root` string | `INVALID_INPUT` | Return error with message: Root declaration name must be non-empty |

### 7.2 Dependency Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| No index database and no DOT file provided | `INDEX_MISSING` | Return error with message: No dependency data available. Provide a coq-dpdgraph DOT file or ensure the index database exists |
| DOT file not found at provided path | `FILE_NOT_FOUND` | Return error with message: DOT file not found: `{path}` |
| DOT file parse failure | `PARSE_ERROR` | Return error with message: Failed to parse DOT file: `{details}` |
| Graph not yet built (query before construction) | `GRAPH_NOT_READY` | Return error with message: Dependency graph has not been constructed. Call with a valid index or DOT file first |
| coq-dpdgraph not installed when DOT source requested | `TOOL_MISSING` | Return error with message: coq-dpdgraph is not installed or not on PATH |

### 7.3 Result Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| Transitive closure or impact set exceeds 10,000 nodes | `RESULT_TOO_LARGE` | Return error with message: Result contains `{count}` nodes, exceeding the limit of 10000. Use max_depth or scope filters to narrow the query |

### 7.4 Edge Cases

| Condition | Behavior |
|-----------|----------|
| Root has no forward edges | Return `TransitiveClosure` with `nodes = {root}`, `total_depth = 0` |
| Root has no reverse edges | Return `ImpactSet` with `impacted_nodes = {root}`, `total_depth = 0` |
| Graph has zero edges | `detect_cycles` returns `is_acyclic = true`, `cycles = []` |
| Graph has a single self-loop `A → A` | Self-loops are singleton SCCs; `detect_cycles` does not report them (SCC size < 2) |
| DOT file contains duplicate edges | Adjacency sets deduplicate naturally; no duplicates in graph |
| Declaration with empty module prefix (single-component name) | Module is set to empty string |

## 8. Non-Functional Requirements

- Graph construction from Storage shall complete within 2 seconds for projects with up to 50,000 edges.
- Graph construction from a DOT file shall complete within 3 seconds for files with up to 100,000 lines.
- Transitive closure and impact analysis BFS shall complete within 500 ms for graphs with up to 10,000 nodes and 50,000 edges.
- Tarjan SCC shall complete within 500 ms for graphs with up to 10,000 nodes and 50,000 edges.
- Module aggregation shall complete within 200 ms for graphs with up to 10,000 nodes.
- The in-memory graph for a project with 10,000 declarations and 50,000 edges shall consume no more than 20 MB of memory.
- The graph cache shall hold at most one graph per distinct project key.

## 9. Examples

### Transitive Closure

```
transitive_closure(graph, root="Coq.Arith.Plus.add_comm", max_depth=3, scope_filter=[])

Result:
{
  "root": "Coq.Arith.Plus.add_comm",
  "nodes": ["Coq.Arith.Plus.add_comm", "Coq.Init.Nat.add", "Coq.Init.Nat.nat",
            "Coq.Init.Datatypes.O", "Coq.Init.Datatypes.S"],
  "edges": [["Coq.Arith.Plus.add_comm", "Coq.Init.Nat.add"],
            ["Coq.Init.Nat.add", "Coq.Init.Nat.nat"],
            ["Coq.Init.Nat.nat", "Coq.Init.Datatypes.O"],
            ["Coq.Init.Nat.nat", "Coq.Init.Datatypes.S"]],
  "depth_map": {
    "0": ["Coq.Arith.Plus.add_comm"],
    "1": ["Coq.Init.Nat.add"],
    "2": ["Coq.Init.Nat.nat"],
    "3": ["Coq.Init.Datatypes.O", "Coq.Init.Datatypes.S"]
  },
  "total_depth": 3
}
```

### Impact Analysis

```
impact_analysis(graph, root="Coq.Init.Nat.nat", max_depth=2, scope_filter=[module_prefix("Coq.Arith")])

Result:
{
  "root": "Coq.Init.Nat.nat",
  "impacted_nodes": ["Coq.Init.Nat.nat", "Coq.Arith.Plus.add_comm", "Coq.Arith.Plus.add_assoc"],
  "edges": [["Coq.Arith.Plus.add_comm", "Coq.Init.Nat.nat"],
            ["Coq.Arith.Plus.add_assoc", "Coq.Init.Nat.nat"]],
  "depth_map": {
    "0": ["Coq.Init.Nat.nat"],
    "1": ["Coq.Arith.Plus.add_comm", "Coq.Arith.Plus.add_assoc"]
  },
  "total_depth": 1
}
```

### Cycle Detection

```
detect_cycles(graph)

Result:
{
  "cycles": [
    ["A.mutual_lemma_1", "A.mutual_lemma_2"],
    ["B.fix_f", "B.fix_g", "B.fix_h"]
  ],
  "total_cycle_count": 2,
  "total_nodes_in_cycles": 5,
  "is_acyclic": false
}
```

### Module Summary

```
module_summary(graph)

Result:
{
  "modules": {
    "Coq.Arith.Plus": {"fan_in": 5, "fan_out": 3, "internal_nodes": 12},
    "Coq.Init.Nat": {"fan_in": 20, "fan_out": 1, "internal_nodes": 8},
    "Coq.Init.Datatypes": {"fan_in": 25, "fan_out": 0, "internal_nodes": 15}
  },
  "module_edges": {
    "Coq.Arith.Plus": ["Coq.Init.Nat", "Coq.Init.Datatypes", "Coq.Init.Logic"],
    "Coq.Init.Nat": ["Coq.Init.Datatypes"]
  },
  "module_cycles": [],
  "total_modules": 3
}
```

## 10. Language-Specific Notes (Python)

- Use `dict[str, set[str]]` for forward and reverse adjacency lists.
- Use `collections.deque` for BFS frontier (O(1) popleft).
- Implement Tarjan's SCC iteratively (not recursively) to avoid stack overflow on large graphs. Use an explicit stack to simulate the recursive call stack.
- DOT file parsing: use the `pydot` library or a lightweight custom parser for the subset of DOT syntax emitted by `coq-dpdgraph dpd2dot` (quoted node names, directed edges, no subgraphs).
- Graph cache: `dict[str, tuple[DependencyGraph, CacheMetadata]]` keyed by source path.
- Package location: `src/poule/analysis/`.
- Entry points:
  - `def build_graph(index_reader=None, dot_file_path=None) -> DependencyGraph`
  - `def transitive_closure(graph, root, max_depth=None, scope_filter=None) -> TransitiveClosure`
  - `def impact_analysis(graph, root, max_depth=None, scope_filter=None) -> ImpactSet`
  - `def detect_cycles(graph) -> CycleReport`
  - `def module_summary(graph) -> ModuleSummary`
- Use `dataclasses.dataclass` (frozen) for all result types (`TransitiveClosure`, `ImpactSet`, `CycleReport`, `ModuleSummary`).
- Use `typing.NamedTuple` for `NodeMetadata` and `ModuleMetrics`.
