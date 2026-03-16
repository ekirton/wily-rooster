# Response Types

Canonical definitions for the data types returned by MCP tool calls, defining the contract between the Retrieval Pipeline (which produces the data) and the MCP Server (which formats and returns it to Claude Code).

**Architecture docs**: [mcp-server.md](../mcp-server.md), [retrieval-pipeline.md](../retrieval-pipeline.md)

---

## SearchResult

The standard response entity for all search tools, representing one matched declaration with its relevance score.

| Field | Type | Constraints |
|-------|------|-------------|
| `name` | qualified name | Required; fully qualified canonical declaration name |
| `statement` | text | Required; pretty-printed statement for display |
| `type` | text | Required; pretty-printed type signature |
| `module` | qualified name | Required; fully qualified module path |
| `kind` | enumeration | Required; one of: `lemma`, `theorem`, `definition`, `instance`, `inductive`, `constructor`, `axiom` |
| `score` | relevance score | Required; range [0, 1]; higher is better; meaningful only for ordering within a single query response, not comparable across tools |

### Relationships

- **Derived from** one declaration (1:1; fields sourced from `declarations` entity in [index-entities.md](index-entities.md)).
- **Contained in** a search response (1:* per response; default limit 50).

---

## LemmaDetail

An extended declaration view for detailed inspection, combining search result fields with dependency and structural information.

| Field | Type | Constraints |
|-------|------|-------------|
| `name` | qualified name | Required; fully qualified canonical declaration name |
| `statement` | text | Required; pretty-printed statement |
| `type` | text | Required; pretty-printed type signature |
| `module` | qualified name | Required; fully qualified module path |
| `kind` | enumeration | Required; same enumeration as SearchResult |
| `score` | relevance score | Required; always 1.0 (exact match by name) |
| `dependencies` | list of qualified names | Required; declarations this one directly uses; may be empty |
| `dependents` | list of qualified names | Required; declarations that directly use this one; may be empty |
| `proof_sketch` | text | Required; tactic script or proof term if available; empty text otherwise |
| `symbols` | list of qualified names | Required; constant, inductive, and constructor names appearing in the declaration |
| `node_count` | positive integer | Required; expression tree node count; diagnostic field |

### Relationships

- **Extends** SearchResult (superset of fields; any consumer of SearchResult can consume the shared fields).
- **Derived from** one declaration, its dependency edges, and its symbol set (1:1; fields sourced from `declarations`, `dependencies`, and `symbol_set` in [index-entities.md](index-entities.md)).

---

## Module

A module listing entry representing one module in the Coq library hierarchy.

| Field | Type | Constraints |
|-------|------|-------------|
| `name` | qualified name | Required; fully qualified module name (e.g., `Coq.Arith.PeanoNat`) |
| `decl_count` | non-negative integer | Required; count of declarations directly contained in this module |

### Relationships

- **Derived from** declarations grouped by module (*:1; aggregated from `declarations.module`).
- **Contained in** a module listing response (1:* per response).
