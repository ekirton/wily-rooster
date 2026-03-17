# Universe Constraint Inspection

Retrieval, parsing, graph construction, inconsistency diagnosis, and polymorphic inspection of Coq universe constraints, exposed through the MCP tool surface.

**Architecture**: [universe-inspection.md](../doc/architecture/universe-inspection.md)

---

## 1. Purpose

Define the universe inspection component that retrieves Coq universe constraints via vernacular commands, parses raw output into structured constraint data, builds queryable constraint graphs, diagnoses universe inconsistency errors with cycle detection and source attribution, and inspects universe-polymorphic definition instantiations — returning structured results through the MCP tool interface.

## 2. Scope

**In scope**: Constraint retrieval (full graph and per-definition), constraint parsing, constraint graph construction, graph filtering by reachability, inconsistency diagnosis (cycle detection, source attribution, resolution suggestions), polymorphic definition inspection (instantiation retrieval, compatibility comparison), error handling, response formatting.

**Out of scope**: MCP protocol handling (owned by mcp-server), session lifecycle management (owned by proof-session), Coq backend process management (owned by proof-session), general vernacular introspection (owned by vernacular-introspection), premise retrieval (owned by retrieval-pipeline).

## 3. Definitions

| Term | Definition |
|------|-----------|
| Universe variable | An internal Coq identifier for a universe level (e.g., `u.42`, `Top.37`) |
| Universe expression | A universe level expression: a variable, an algebraic form (`u.N+1`, `max(u.N, u.M)`), or a constant (`Set`, `Prop`) |
| Universe constraint | A relation between two universe expressions: strict (`<`), non-strict (`<=`), or equality (`=`) |
| Constraint graph | A directed graph where nodes are universe variables and edges are constraints |
| Inconsistent cycle | A directed cycle in the constraint graph containing at least one strict (`<`) edge, violating the well-foundedness requirement |
| Source attribution | The mapping from a constraint to the Coq definition that introduced it |
| Universe-polymorphic definition | A Coq definition declared with `Polymorphic` or `#[universes(polymorphic)]`, parameterized over universe levels |
| Reachable subgraph | The subset of a constraint graph reachable from a set of seed variables by following constraint edges in both directions |

## 4. Behavioral Requirements

### 4.1 Constraint Retrieval — Full Graph

#### retrieve_full_graph()

- REQUIRES: An active proof session exists in the Proof Session Manager.
- ENSURES: Submits `Print Universes.` via `coq_query`. Parses the raw text output into a `ConstraintGraph` containing all universe variables and constraints in the current environment. Returns the complete `ConstraintGraph`.
- MAINTAINS: The Coq session state is unchanged after retrieval.

> **Given** an active session with definitions introducing universes `u.1`, `u.2`, `u.3` and constraints `u.1 <= u.2`, `u.2 < u.3`
> **When** `retrieve_full_graph()` is called
> **Then** the returned `ConstraintGraph` has `node_count = 3`, `edge_count = 2`, and contains both constraints

> **Given** an environment with no user-defined universe constraints
> **When** `retrieve_full_graph()` is called
> **Then** a `ConstraintGraph` is returned (possibly containing Coq-internal constraints); no error is raised

### 4.2 Constraint Retrieval — Per-Definition

#### retrieve_definition_constraints(qualified_name)

- REQUIRES: `qualified_name` is a non-empty string identifying a Coq definition. An active proof session exists.
- ENSURES: Submits `Set Printing Universes.`, then `Print <qualified_name>.`, then `Unset Printing Universes.` as an atomic command sequence (no interleaving). Parses the annotated output to extract universe variables and constraints associated with the definition. Returns a `ConstraintGraph` with `filtered_from` set to `qualified_name`.
- MAINTAINS: The printing universe flag is restored to its prior state after the operation.

> **Given** a universe-polymorphic definition `my_id` with constraint `u.5 <= u.6`
> **When** `retrieve_definition_constraints("my_id")` is called
> **Then** the returned `ConstraintGraph` contains `u.5` and `u.6` in `variables` and the constraint `u.5 le u.6` in `constraints`, with `filtered_from = "my_id"`

> **Given** a definition `simple_nat` with no universe constraints
> **When** `retrieve_definition_constraints("simple_nat")` is called
> **Then** a `ConstraintGraph` with empty `constraints` is returned; no error is raised

> **Given** `qualified_name = "nonexistent_def"`
> **When** `retrieve_definition_constraints("nonexistent_def")` is called
> **Then** a `NOT_FOUND` error is returned

### 4.3 Constraint Parsing

#### parse_constraints(raw_text, source_command)

- REQUIRES: `raw_text` is the string output from a Coq vernacular command. `source_command` indicates the originating command type (`"print_universes"` or `"print_definition"`).
- ENSURES: Parses `raw_text` line-by-line. For `print_universes` source, extracts constraints in `u.N op u.M` format. For `print_definition` source, extracts `Type@{u.N}` annotations and polymorphic universe parameter declarations. Returns a list of `UniverseConstraint` records. Blank lines, comments, and Coq informational messages are skipped. Lines matching no known format are recorded in a `diagnostic` field on the response.
- MAINTAINS: Successfully parsed constraints are never discarded due to later parse failures.

> **Given** raw text containing `u.1 <= u.2\nu.2 < u.3\n(* comment *)\nu.3 = u.4`
> **When** `parse_constraints(raw_text, "print_universes")` is called
> **Then** three `UniverseConstraint` records are returned with relations `le`, `lt`, `eq` respectively; the comment line is skipped

> **Given** raw text containing `u.1 <= u.2\nGARBAGE LINE\nu.3 < u.4`
> **When** `parse_constraints(raw_text, "print_universes")` is called
> **Then** two constraints are returned and the diagnostic field contains `"GARBAGE LINE"`

### 4.4 Constraint Graph Construction

#### build_graph(constraints)

- REQUIRES: `constraints` is a list of `UniverseConstraint` records (may be empty).
- ENSURES: Constructs a `ConstraintGraph` with `variables` containing all unique universe variable names from both sides of all constraints, `constraints` containing the input list, `node_count` equal to the number of distinct variables, and `edge_count` equal to the number of constraints.

> **Given** constraints `[u.1 < u.2, u.2 <= u.3, u.1 = u.3]`
> **When** `build_graph(constraints)` is called
> **Then** `variables = ["u.1", "u.2", "u.3"]`, `node_count = 3`, `edge_count = 3`

### 4.5 Subgraph Filtering

#### filter_by_reachability(graph, seed_variables)

- REQUIRES: `graph` is a `ConstraintGraph`. `seed_variables` is a non-empty list of universe variable names.
- ENSURES: Computes the set of variables reachable from `seed_variables` by following constraint edges in both directions (forward and backward). Returns a `ConstraintGraph` containing only the reachable variables and constraints where both endpoints are reachable.

> **Given** a graph with variables `u.1, u.2, u.3, u.4` and constraints `u.1 < u.2, u.2 <= u.3, u.4 < u.4`
> **When** `filter_by_reachability(graph, ["u.1"])` is called
> **Then** the returned graph contains `u.1, u.2, u.3` and constraints `u.1 < u.2, u.2 <= u.3`; `u.4` is excluded

### 4.6 Inconsistency Diagnosis

#### diagnose_universe_error(error_message, environment_context)

- REQUIRES: `error_message` is a non-empty string. An active proof session exists.
- ENSURES: Parses the error message to extract universe variable names. Retrieves the full constraint graph. Filters to the reachable subgraph from the error-named variables. Detects directed cycles containing at least one strict (`<`) edge. Attributes constraints in the cycle to source definitions (best-effort). Returns an `InconsistencyDiagnosis` containing the cycle, attributions, plain-language explanation, and at least one resolution suggestion.
- MAINTAINS: The Coq session state is unchanged after diagnosis.

> **Given** an error `"Universe inconsistency: cannot enforce u.42 < u.17 because u.17 <= u.42 is already required"`
> **When** `diagnose_universe_error(error_message, context)` is called
> **Then** the diagnosis contains a cycle involving `u.42` and `u.17`, an explanation describing the conflict, and at least one suggestion

> **Given** an error message that is not a universe inconsistency (e.g., a type mismatch)
> **When** `diagnose_universe_error(error_message, context)` is called
> **Then** an `INVALID_INPUT` error is returned

> **Given** a valid universe error, but the environment has changed and the inconsistency is no longer reproducible
> **When** `diagnose_universe_error(error_message, context)` is called
> **Then** an `InconsistencyDiagnosis` is returned with an empty `cycle` and an explanation noting the inconsistency could not be reproduced

### 4.7 Cycle Detection

When detecting inconsistent cycles in a constraint subgraph, the Inconsistency Diagnoser shall:

1. Perform depth-first search for back edges on the subgraph reachable from the error-named variables.
2. Among detected cycles, identify those containing at least one strict (`<`) edge.
3. Select the shortest such cycle as the primary explanation.

- REQUIRES: A `ConstraintGraph` filtered to the relevant subgraph.
- ENSURES: Returns the shortest cycle containing a strict edge, or an empty list if no such cycle exists.

> **Given** a subgraph with edges `u.1 < u.2, u.2 <= u.3, u.3 <= u.1` (cycle with one strict edge)
> **When** cycle detection runs
> **Then** the cycle `[u.1 < u.2, u.2 <= u.3, u.3 <= u.1]` is returned

> **Given** a subgraph with edges `u.1 <= u.2, u.2 <= u.1` (cycle with no strict edges)
> **When** cycle detection runs
> **Then** an empty cycle is returned (no inconsistency)

### 4.8 Source Attribution

For each constraint in an identified cycle, the Inconsistency Diagnoser shall:

1. Query `About <definition>` for definitions known to reference the constraint's universe variables.
2. When `About` output is insufficient, retrieve the annotated output via `Set Printing Universes` + `Print` for candidate definitions from the error context.
3. Record each attribution as a `ConstraintAttribution` with a confidence level.

- ENSURES: Each constraint in the cycle has a `ConstraintAttribution`. When a variable cannot be traced, confidence is set to `"unknown"` and `definition` is null.

> **Given** a constraint `u.5 < u.10` where `About my_def` shows `u.5` originates from `my_def`
> **When** attribution runs for this constraint
> **Then** the attribution has `definition = "my_def"` and `confidence = "certain"`

> **Given** a constraint `u.99 <= u.100` where no definition can be traced
> **When** attribution runs
> **Then** the attribution has `definition = null` and `confidence = "unknown"`

### 4.9 Resolution Suggestions

Based on cycle structure and source attribution, the diagnoser shall select applicable strategies from:

| Strategy | Condition |
|----------|-----------|
| Add universe polymorphism | A monomorphic definition introduces a rigid constraint in the cycle |
| Adjust universe declarations | Explicit `Constraint` or `Universe` declarations are involved |
| Restructure to break the cycle | Two definitions form a mutual constraint path |
| Use a universe-polymorphic variant | A monomorphic standard library definition is involved and a polymorphic variant exists |

- ENSURES: At least one suggestion is always included in the diagnosis. Suggestions are concrete (referencing specific definitions when attribution is available).

### 4.10 Polymorphic Instantiation Retrieval

#### retrieve_instantiations(use_site_name)

- REQUIRES: `use_site_name` is a non-empty string identifying a definition that references a universe-polymorphic definition. An active proof session exists.
- ENSURES: Submits `Set Printing Universes.`, then `Print <use_site_name>.`, then `Unset Printing Universes.` atomically. Parses annotated output to extract the mapping from universe parameters to concrete universe levels for each occurrence of a polymorphic definition. Returns a list of (polymorphic_definition, parameter_to_level_mapping) pairs.
- MAINTAINS: Printing state is restored after the operation.

> **Given** a definition `my_func` that uses `list@{u.5}` where `list` has one universe parameter
> **When** `retrieve_instantiations("my_func")` is called
> **Then** the result includes `("list", {"u" -> "u.5"})`

> **Given** `use_site_name = "nonexistent_def"`
> **When** `retrieve_instantiations("nonexistent_def")` is called
> **Then** a `NOT_FOUND` error is returned

### 4.11 Polymorphic Compatibility Comparison

#### compare_definitions(name_a, name_b)

- REQUIRES: `name_a` and `name_b` are non-empty strings identifying Coq definitions. An active proof session exists.
- ENSURES: Retrieves the universe constraints and `About` output for both definitions. Identifies the constraint sets for each. Checks whether an assignment of universe levels satisfies both constraint sets simultaneously. Returns compatibility status. When incompatible, identifies the specific conflicting constraints and reports which definition's constraint is more restrictive.

> **Given** `def_a` with constraint `u.1 < u.2` and `def_b` with constraint `u.2 <= u.1`
> **When** `compare_definitions("def_a", "def_b")` is called
> **Then** the result reports incompatibility, identifying the cycle formed by combining both constraint sets

> **Given** `def_a` with constraint `u.1 <= u.2` and `def_b` with constraint `u.1 <= u.3` (no conflict)
> **When** `compare_definitions("def_a", "def_b")` is called
> **Then** the result reports compatibility

## 5. Data Model

### UniverseExpression

| Field | Type | Constraints |
|-------|------|-------------|
| `kind` | `"variable"` or `"algebraic"` or `"set"` or `"prop"` | Required |
| `name` | string or null | Required when `kind = "variable"`; null otherwise |
| `base` | UniverseExpression or null | Present when `kind = "algebraic"` and expression is `base+offset`; null otherwise |
| `offset` | non-negative integer or null | Present when `kind = "algebraic"` and expression is `base+offset`; null otherwise |
| `operands` | list of UniverseExpression or null | Present when `kind = "algebraic"` and expression is `max(...)`; null otherwise |

### UniverseConstraint

| Field | Type | Constraints |
|-------|------|-------------|
| `left` | UniverseExpression | Required |
| `relation` | `"lt"` or `"le"` or `"eq"` | Required |
| `right` | UniverseExpression | Required |
| `source` | string or null | Qualified name of the introducing definition; null when unknown |

### ConstraintGraph

| Field | Type | Constraints |
|-------|------|-------------|
| `variables` | list of string | Required; all universe variable names in the graph |
| `constraints` | list of UniverseConstraint | Required; all constraints in the graph |
| `node_count` | non-negative integer | Required; equals `len(variables)` |
| `edge_count` | non-negative integer | Required; equals `len(constraints)` |
| `filtered_from` | string or null | Non-null when this is a filtered subgraph; identifies the filter origin |

### InconsistencyDiagnosis

| Field | Type | Constraints |
|-------|------|-------------|
| `error_text` | string | Required; the original error message |
| `cycle` | list of UniverseConstraint | Required; empty when no cycle found |
| `attributions` | list of ConstraintAttribution | Required; one per constraint in `cycle` |
| `explanation` | string | Required; plain-language description of the conflict |
| `suggestions` | list of string | Required; at least one entry |
| `relevant_subgraph` | ConstraintGraph | Required; the reachable subgraph from error-named variables |

### ConstraintAttribution

| Field | Type | Constraints |
|-------|------|-------------|
| `constraint` | UniverseConstraint | Required |
| `definition` | string or null | Null when origin undetermined |
| `location` | string or null | Human-readable location hint; null when unavailable |
| `confidence` | `"certain"` or `"inferred"` or `"unknown"` | Required |

## 6. Interface Contracts

### Universe Inspection -> Coq Query Layer

| Property | Value |
|----------|-------|
| Operations used | `coq_query(command) -> raw_text` |
| Concurrency | Serialized per backend process; multi-command sequences (`Set`/`Print`/`Unset`) are atomic (no interleaving) |
| Error strategy | `coq_query` errors propagated to caller with appropriate error codes |
| Idempotency | Read-only queries are idempotent; `Set`/`Unset` pairs restore state |

### Universe Inspection -> Proof Session Manager

| Property | Value |
|----------|-------|
| Operations used | Session existence check (via `coq_query` routing) |
| Error strategy | `SESSION_NOT_FOUND` -> propagated immediately. `BACKEND_CRASHED` -> propagated immediately; no universe-specific recovery. |

### MCP Server -> Universe Inspection

| Property | Value |
|----------|-------|
| Operations exposed | `retrieve_full_graph`, `retrieve_definition_constraints`, `diagnose_universe_error`, `retrieve_instantiations`, `compare_definitions` |
| Input validation | Universe Inspection validates `qualified_name` is non-empty, `error_message` is non-empty; rejects with `INVALID_INPUT` otherwise |
| Output format | Structured JSON matching the data model entities |
| Error format | MCP error contract as defined in mcp-server specification |

## 7. Error Specification

### 7.1 Input Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| Definition name not found in environment | `NOT_FOUND` | `"Definition '{name}' not found in the current environment."` |
| Error message is not a universe inconsistency | `INVALID_INPUT` | `"The provided error is not a universe inconsistency error."` |
| Empty `qualified_name` or `error_message` | `INVALID_INPUT` | `"Required parameter '{param}' must be non-empty."` |

### 7.2 State Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| No active session | `SESSION_NOT_FOUND` | `"No active session. Open a proof session first to establish a Coq environment."` |

### 7.3 Dependency Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| Backend crash during query | `BACKEND_CRASHED` | Propagated from Proof Session Manager; no universe-specific handling |
| Query timeout | `QUERY_TIMEOUT` | `"Universe query timed out after {timeout}s. Try filtering to a specific definition."` |

### 7.4 Parse and Data Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| Coq backend returns unexpected output format | `PARSE_ERROR` | Return partial results with unparseable text in a diagnostic field; successfully parsed constraints are preserved |
| Constraint graph too large for response | `GRAPH_TOO_LARGE` | Return a truncated graph with `truncated = true` flag and the count of omitted constraints |

### 7.5 Non-Error Edge Cases

| Condition | Behavior |
|-----------|----------|
| Definition has no universe constraints | Success response with empty constraint set; not an error |
| Cycle detection finds no cycle | Diagnosis returned with empty `cycle` and explanation that the inconsistency could not be reproduced |
| Source attribution fails for a constraint | Attribution `confidence` set to `"unknown"`; diagnosis proceeds |

## 8. Non-Functional Requirements

- Constraint parsing shall process at least 10,000 constraint lines per second.
- Graph construction from a parsed constraint list shall complete in O(n) time where n is the number of constraints.
- Cycle detection shall complete in O(V + E) time where V is the number of variables and E is the number of constraints in the filtered subgraph.
- The component shall handle constraint graphs with up to 100,000 constraints without exceeding 50 MB of memory.
- The `Set Printing Universes` / `Print` / `Unset Printing Universes` sequence shall complete within a single `coq_query` atomic scope; no partial execution is permitted.

## 9. Examples

### Full graph retrieval

```
retrieve_full_graph()

Coq output (Print Universes):
  u.1 <= u.2
  u.2 < u.3
  u.3 = u.4

Result:
{
  "variables": ["u.1", "u.2", "u.3", "u.4"],
  "constraints": [
    {"left": {"kind": "variable", "name": "u.1"}, "relation": "le", "right": {"kind": "variable", "name": "u.2"}, "source": null},
    {"left": {"kind": "variable", "name": "u.2"}, "relation": "lt", "right": {"kind": "variable", "name": "u.3"}, "source": null},
    {"left": {"kind": "variable", "name": "u.3"}, "relation": "eq", "right": {"kind": "variable", "name": "u.4"}, "source": null}
  ],
  "node_count": 4,
  "edge_count": 3,
  "filtered_from": null
}
```

### Inconsistency diagnosis

```
diagnose_universe_error(
  error_message="Universe inconsistency: cannot enforce u.42 < u.17 because u.17 <= u.42 is already required",
  environment_context={...}
)

Result:
{
  "error_text": "Universe inconsistency: cannot enforce u.42 < u.17 because u.17 <= u.42 is already required",
  "cycle": [
    {"left": {"kind": "variable", "name": "u.42"}, "relation": "lt", "right": {"kind": "variable", "name": "u.17"}, "source": "MyModule.my_def"},
    {"left": {"kind": "variable", "name": "u.17"}, "relation": "le", "right": {"kind": "variable", "name": "u.42"}, "source": "MyModule.other_def"}
  ],
  "attributions": [
    {"constraint": {...}, "definition": "MyModule.my_def", "location": "MyFile.v:42", "confidence": "certain"},
    {"constraint": {...}, "definition": "MyModule.other_def", "location": "MyFile.v:58", "confidence": "inferred"}
  ],
  "explanation": "The constraint u.42 < u.17 (from MyModule.my_def) conflicts with u.17 <= u.42 (from MyModule.other_def), forming a cycle with a strict inequality that violates universe well-foundedness.",
  "suggestions": [
    "Make MyModule.my_def universe-polymorphic to avoid the rigid constraint on u.42.",
    "Restructure MyModule.other_def to decouple its universe dependency on u.42."
  ],
  "relevant_subgraph": {
    "variables": ["u.17", "u.42"],
    "constraints": [...],
    "node_count": 2,
    "edge_count": 2,
    "filtered_from": null
  }
}
```

### Polymorphic instantiation retrieval

```
retrieve_instantiations("my_func")

Coq output (Set Printing Universes + Print my_func):
  my_func = fun (A : Type@{u.5}) => @nil@{u.5} A
     : Type@{u.5} -> list@{u.5} A

Result:
[
  {"definition": "nil", "mapping": {"u": "u.5"}},
  {"definition": "list", "mapping": {"u": "u.5"}}
]
```

## 10. Language-Specific Notes (Python)

- Use `re` module for constraint line parsing with precompiled patterns for the three constraint formats (`<=`, `<`, `=`) and annotated type format (`Type@{...}`).
- Use `dataclasses` for `UniverseConstraint`, `UniverseExpression`, `ConstraintGraph`, `InconsistencyDiagnosis`, and `ConstraintAttribution`.
- Use `collections.defaultdict(list)` for the adjacency list representation in `ConstraintGraph`.
- Cycle detection: implement iterative DFS (not recursive) to avoid stack overflow on large graphs.
- Use `async` for all operations that call `coq_query`, consistent with the Proof Session Manager interface.
- Package location: `src/poule/universe/`.
- Entry points: `async def retrieve_full_graph(session_manager, session_id) -> ConstraintGraph`, `async def diagnose_universe_error(session_manager, session_id, error_message, context) -> InconsistencyDiagnosis`.
