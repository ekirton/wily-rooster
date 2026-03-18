# Coq Library Extraction

Offline extraction of declarations from compiled Coq/Rocq libraries into the search index.

**Feature**: [Library Indexing](../features/library-indexing.md)
**Stories**: [Epic 1: Library Indexing](../requirements/stories/tree-search-mcp.md#epic-1-library-indexing)

---

## Extraction Pipeline

```
.vo files (compiled Coq libraries)
  │
  ▼
coq-lsp
  │  List declarations: (name, type_sig) per module via Search
  │  Detect kind per declaration (About queries, batched)
  │
  ▼
Deduplicate declarations by fully qualified name (keep first occurrence)
  │
  ▼
Per-declaration processing:
  1. Parse type_signature text → ConstrNode (via TypeExprParser)
     (parse failure → partial result stored, declaration reachable only via name/FTS search)
  2. coq_normalize(constr_node)→ normalized ExprTree (constr_to_tree + recompute_depths + assign_node_ids)
  3. cse_normalize(tree)       → CSE-reduced tree (recomputes depths + node_ids after)
  4. extract_symbols(tree)     → symbol set {constants, inductives, constructors}
  5. wl_histogram(tree, h=3)   → WL kernel vector for structural screening (Phase 1 computes h=3 only)
  6. pretty_print(name)        → human-readable statement
  7. pretty_print_type(name)   → human-readable type signature

  Pass 2 (after all declarations are inserted):
  8. extract_dependencies()   → dependency edges (uses, instance_of, ...)
  │
  ▼
SQLite database (see storage.md)
  Write: declarations, dependencies, symbols, wl_vectors, symbol_freq,
         declarations_fts, index_meta
```

### Fully qualified name derivation

Backends that return short names (e.g., coq-lsp `Search` returns `Nat.add_comm` rather than `Coq.Arith.PeanoNat.Nat.add_comm`) derive fully qualified names by prepending the `.vo` file's logical module path. The logical module path is derived from the filesystem path using heuristic prefix stripping (see below). The resulting name has the form `<logical_module_path>.<short_name>`.

### Module path derivation

The `module` field on each declaration is the logical path of the `.vo` file from which the declaration was extracted — not derived from string manipulation of the fully qualified name. For nested modules, the `.vo` file is the source of truth.

The logical path is derived from the `.vo` file's filesystem path by stripping known directory prefixes (`user-contrib/`, `theories/`), removing version-specific prefixes (e.g., `Stdlib/`), converting path separators to dots, and removing the `.vo` extension.

### Kind detection

Declaration kind is not always available directly from the backend's declaration listing. Some backends (e.g., coq-lsp) return only `(name, type_sig)` pairs and require a separate query per declaration to determine the kind. The kind detection mechanism is backend-dependent, and the response format may vary across Coq/Rocq versions. See the extraction specification (§4.1.1) for backend-specific detection contracts.

In Rocq 9.x, the `About` response may include multiple `Expands to:` lines when a notation aliases a real constant (e.g., `pred` is a notation that expands to `Nat.pred`, which is a `Constant`). Kind detection must prefer the underlying constant/inductive/constructor category over the notation category when both are present. This ensures that notation aliases of indexable declarations remain in the index.

### Kind mapping

Declaration kind values are stored as lowercase strings. The extraction layer maps Coq declaration forms to storage kinds and lowercases before storage.

| Coq Declaration Form | Storage Kind | Notes |
|---------------------|-------------|-------|
| `Lemma` | `lemma` | |
| `Theorem` | `theorem` | |
| `Definition` | `definition` | |
| `Let` | `definition` | Local definition |
| `Coercion` | `definition` | |
| `Canonical Structure` | `definition` | |
| `Inductive` | `inductive` | |
| `Record` | `inductive` | Records are inductive types |
| `Class` | `inductive` | Classes are records |
| `Constructor` | `constructor` | Inductive type constructors |
| `Instance` | `instance` | Typeclass instances |
| `Axiom` | `axiom` | |
| `Parameter` | `axiom` | |
| `Conjecture` | `axiom` | |
| `Notation` | *(excluded)* | Not indexable — no kernel term |
| `Abbreviation` | *(excluded)* | Not indexable — no kernel term |
| `Section Variable` | *(excluded)* | Not present in closed `.vo` forms |
| `Ltac` | *(excluded)* | Tactic definitions — no kernel term |
| `Module` | *(excluded)* | Module declarations — no kernel term |

### Serialization

The `constr_tree` BLOB format is defined in [storage.md](storage.md). See the storage specification for serialization requirements.

## Extraction Targets

### Phase 1 (MVP)

- **Coq standard library**: All declarations from the installed Coq/Rocq stdlib `.vo` files.
- **MathComp**: All declarations from the installed MathComp `.vo` files, indexed into the same database distinguished by module path.

### Phase 2

- **User project**: Declarations from a user-specified project directory. Supports incremental re-indexing — only changed files are re-extracted.

## Extraction Tooling

Declarations are read from compiled `.vo` files via coq-lsp. coq-lsp is the sole supported extraction backend (see [library-indexing.md](../features/library-indexing.md) for design rationale).

The `Search _ inside M.` command returns textual `name : type_signature` pairs without kernel terms. To produce structural data (expression trees, symbol sets, WL histograms), the pipeline parses type signature strings into `ConstrNode` trees using a pure-Python text parser (`TypeExprParser`). This parser is used at both index time and query time for consistent structural matching.

coq-lsp does not return declaration kinds directly. The backend issues a separate `About <name>.` query per declaration to determine kind, with queries batched into shared documents (≤100 per document) to reduce round-trip overhead.

Key requirement: coq-lsp must be version-compatible with the installed Coq/Rocq version. The extracted library version is recorded in `index_meta` for stale detection.

### Text-Based Type Parsing

When coq-lsp returns a type signature string (e.g., `"forall n : nat, n + 0 = n"`), the `TypeExprParser` converts it to a `ConstrNode` tree:

```
type_signature string
  │
  ▼
TypeExprParser.parse(text)
  │  Tokenize → Pratt parse → resolve names (de Bruijn) → ConstrNode
  │
  ▼
coq_normalize(constr_node) → ExprTree
  │
  ▼
cse_normalize(tree) → CSE-reduced tree
  │
  ▼
extract_symbols(tree), wl_histogram(tree, h=3)
```

The text parser produces `Const("nat")` rather than the kernel-precise `Ind("Coq.Init.Datatypes.nat")`. This is less precise than kernel terms, but since both index-time and query-time parsing use the same parser, WL histograms and symbol sets are internally consistent and structural matching works correctly.

## Error Handling

Extraction of individual declarations may fail (e.g., unsupported term constructors, serialization errors). Failures are logged with the declaration name and error, but do not abort the indexing run. The index is usable with partial coverage; missing declarations are a degraded-quality outcome, not a fatal error.

**Backend process crash or hang**: If the extraction backend (coq-lsp or SerAPI) crashes or becomes unresponsive during an indexing run, the pipeline aborts and deletes the partial database file. This is a pipeline-level fatal error.

## Progress Reporting

Progress reporting is opt-in: the indexing command is quiet by default and prints progress messages only when the caller enables a progress flag. When enabled, messages are written to stderr so they do not interfere with structured output.

Both extraction passes report progress at per-declaration granularity, and each message identifies the current stage:
- Pass 1: "Extracting declarations [N/total]"
- Pass 2: "Resolving dependencies [N/total]"

## Index Construction

The indexing command:
1. Deletes any existing database file at the output path
2. Detects the installed Coq/Rocq version and target library versions
3. Collects declarations from all `.vo` files, then deduplicates by fully qualified name (keeps first occurrence; duplicates arise from module re-exports across `.vo` files)
4. Processes each unique declaration through the pipeline above
5. Computes global symbol frequencies across all declarations
6. Writes everything to a single SQLite database
7. Records the index schema version and library versions in `index_meta`

The entire process runs without GPU, network access, or external API keys.
