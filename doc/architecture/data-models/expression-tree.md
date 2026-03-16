# Expression Tree

The normalized expression tree is the canonical structural representation of a Coq/Rocq declaration, used for structural similarity computation across WL histograms, tree edit distance, and collapse matching.

**Architecture docs**: [coq-normalization.md](../coq-normalization.md), [coq-extraction.md](../coq-extraction.md), [retrieval-pipeline.md](../retrieval-pipeline.md)

---

## Expression Tree (entity)

A rooted, ordered tree representing the normalized structure of a single Coq declaration's kernel term.

| Field | Type | Constraints |
|-------|------|-------------|
| `root` | tree node | Required; the top-level node of the tree |
| `node_count` | positive integer | Required; total number of nodes; must equal `declarations.node_count` for the owning declaration |

### Relationships

- **Belongs to** one declaration (1:1, serialized in `declarations.constr_tree`; owned by `declarations`).

---

## Tree Node (entity)

A single node in an expression tree, representing one syntactic element of a normalized Coq term.

| Field | Type | Constraints |
|-------|------|-------------|
| `node_type` | enumeration | Required; one of the leaf or interior types listed below |
| `label` | text | Required; semantics depend on node type (see below) |
| `children` | ordered list of tree nodes | Required; count constrained by node type (see below); empty for leaf nodes |

### Node type enumeration

**Leaf types** (children: none):

| Node type | Label constraint |
|-----------|-----------------|
| `LConst` | Must be a fully qualified canonical constant name |
| `LInd` | Must be a fully qualified canonical inductive type name |
| `LConstruct` | Must be a fully qualified canonical constructor name |
| `LCseVar` | Must be a non-negative integer (CSE variable identifier) |

**Interior types** (children: one or more):

| Node type | Label constraint | Children constraint |
|-----------|-----------------|---------------------|
| `LApp` | Empty | Exactly 2: `func`, `arg` (binary application after currification) |
| `LAbs` | Variable name | Exactly 1: `body` |
| `LLet` | Variable name | Exactly 2: `value`, `body` |
| `LProj` | Projection name | Exactly 1: `struct` |
| `LCase` | Inductive type name | At least 2: `scrutinee`, followed by one or more `branch` nodes |

### Relationships

- **Belongs to** one expression tree.
- **Owns** zero or more child tree nodes (1:*, recursive; ordered).

---

## Invariants

These constraints hold for all trees stored in `declarations.constr_tree` and for all query trees produced by the normalization pipeline.

| Invariant | Applies to | Constraint |
|-----------|-----------|------------|
| Binary application | `LApp` | All applications are binary. N-ary `App(f, [a1, a2, ...])` is currified to nested `LApp(LApp(f, a1), a2)`. |
| No cast nodes | All nodes | Cast nodes are stripped during normalization. No node in a stored tree represents a cast. |
| No universe annotations | `LConst`, `LInd`, `LConstruct` | Universe parameters are erased. Two references at different universe levels have identical labels. |
| Canonical names only | `LConst`, `LInd`, `LConstruct` | All names are fully qualified kernel-canonical names, not user-facing short names. |
| Closed forms only | All nodes | Section-local free variables are absent. Only post-section closed definitions from `.vo` files are represented. |
| Constants preserved by CSE | `LConst`, `LInd`, `LConstruct` | These node types are never replaced by `LCseVar`, regardless of repetition frequency. They carry semantic identity essential for symbol-based retrieval. |

---

## CSE Normalization

Common Subexpression Elimination reduces tree size by replacing repeated non-constant subexpressions with `LCseVar` references.

### Algorithm (three passes)

1. **Hash**: traverse the tree, computing a structural hash for each subexpression
2. **Count**: count frequency of each hash — subexpressions with frequency ≥ 2 are candidates
3. **Replace**: substitute repeated non-constant subexpressions with fresh `LCseVar(id)` nodes

Typical effect: 2–10× node reduction on expressions with heavy type annotation repetition.

---

## Normalization Pipeline

The full pipeline from Coq kernel term to stored tree:

```
Constr.t
  → constr_to_tree()      Adaptations applied inline:
                             • Currify n-ary applications
                             • Strip Cast nodes
                             • Erase universe annotations
                             • Fully qualify all names
                             • Keep Proj as interior node
  → recompute_depths()    Update depth fields on all nodes
  → assign_node_ids()     Assign unique IDs for reference
  → cse_normalize()       CSE replacement (three passes above)
  → serialized BLOB       Stored in declarations.constr_tree
```

Query expressions undergo the identical pipeline to ensure correct similarity computation.

---

## Serialization

The tree is serialized to a BLOB for storage in `declarations.constr_tree`. The specific serialization format is an implementation choice. Requirements:

- Must round-trip without data loss
- Must preserve all node types, labels, children ordering, and tree structure
- Must be deserializable at query time for TED computation and collapse matching
