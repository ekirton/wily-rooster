# Implementation Guidelines

## Source of Authority

`specification/*.md` is authoritative for all implementation decisions.

Authority chain: `specification/*.md` → `doc/architecture/` → `doc/features/` → `doc/requirements/`

## Upstream Authority Is Immutable

Do not modify `test/`, `specification/`, `doc/architecture/`, or `doc/architecture/data-models/` when writing implementation code.

- If a test fails, fix the implementation — not the test.
- If a test imports from a specific module path, create that module at that path.
- If a test expects a specific function signature, implement that exact signature.
- If a test expects a specific exception type, raise that exact exception.
- File feedback in the appropriate `feedback/` folder if upstream appears wrong.

## Import Paths

Tests define the expected package structure:

| Package | Location |
|---------|----------|
| `poule.models.enums` | Enumerations (`SortKind`, `DeclKind`) |
| `poule.models.labels` | Node label hierarchy (15 concrete types) |
| `poule.models.tree` | `TreeNode`, `ExprTree`, utility functions |
| `poule.models.responses` | `SearchResult`, `LemmaDetail`, `Module` |
| `poule.normalization.constr_node` | `ConstrNode` variant types |
| `poule.normalization.normalize` | `constr_to_tree`, `coq_normalize` |
| `poule.normalization.cse` | `cse_normalize` |
| `poule.normalization.errors` | `NormalizationError` |
| `poule.storage.writer` | `IndexWriter` |
| `poule.storage.reader` | `IndexReader` |
| `poule.storage.errors` | `StorageError`, `IndexNotFoundError`, `IndexVersionError` |
| `poule.channels.wl_kernel` | WL histogram, cosine, size filter, screening |
| `poule.channels.mepo` | Symbol weight, relevance, iterative selection |
| `poule.channels.fts` | FTS5 query preprocessing and search |
| `poule.channels.ted` | Zhang-Shasha TED, rename cost, similarity |
| `poule.channels.const_jaccard` | Jaccard similarity, constant extraction |
| `poule.fusion.fusion` | Score clamping, collapse match, structural score, RRF |
| `poule.pipeline.context` | `PipelineContext`, `create_context` |
| `poule.pipeline.search` | `search_by_structure`, `search_by_type`, `search_by_symbols`, `search_by_name`, `score_candidates` |
| `poule.pipeline.parser` | `CoqParser`, `ParseError` |
| `poule.extraction.pipeline` | `run_extraction`, `discover_libraries` |
| `poule.extraction.kind_mapping` | `map_kind` |
| `poule.extraction.errors` | `ExtractionError` |
| `poule.server.handlers` | Tool handler functions |
| `poule.server.validation` | Input validation functions |
| `poule.server.errors` | Error formatting, error code constants |
