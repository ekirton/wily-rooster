# Type Expression Parser

Pure-Python parser that converts Coq type signature strings into ConstrNode trees for structural indexing and query-time parsing.

**Architecture**: [coq-extraction.md](../doc/architecture/coq-extraction.md) § Text-Based Type Parsing

---

## 1. Purpose

Define the TypeExprParser component that parses textual Coq type signatures (as returned by coq-lsp `Search` output) into `ConstrNode` intermediate representations, enabling structural search channels (WL histograms, symbol extraction, tree edit distance) for declarations that lack kernel terms.

## 2. Scope

**In scope**: Tokenizer, Pratt parser, de Bruijn index resolution, ConstrNode production, CoqParser protocol conformance.

**Out of scope**: Normalization (owned by coq-normalization), CSE (owned by cse-normalization), kernel term parsing (owned by constr_parser), tactic syntax, vernacular commands.

## 3. Definitions

| Term | Definition |
|------|-----------|
| TypeExprParser | A pure-Python parser implementing the `CoqParser` protocol that converts type signature text into `ConstrNode` |
| Pratt parser | A top-down operator precedence parser that handles infix operators with configurable precedence and associativity |
| Binder stack | A list of bound variable names used to resolve names to de Bruijn indices |

## 4. Behavioral Requirements

### 4.1 CoqParser Protocol Conformance

`TypeExprParser` shall implement the `CoqParser` protocol defined in `specification/pipeline.md` §4.2:

#### parse(expression)

- REQUIRES: `expression` is a non-empty string containing a Coq type expression.
- ENSURES: Returns a `ConstrNode` representing the parsed expression.
- On failure: raises `ParseError`.

> **Given** the expression `"nat -> nat"`,
> **When** `parse("nat -> nat")` is called,
> **Then** it returns `Prod("_", Const("nat"), Const("nat"))`.

> **Given** the expression `""` (empty),
> **When** `parse("")` is called,
> **Then** it raises `ParseError`.

### 4.2 Tokenizer

The tokenizer shall convert a type expression string into a list of `Token` values. Each `Token` has fields: `kind` (TokenKind enum), `value` (str), `pos` (int — byte offset in input).

Token kinds:

| Kind | Matches | Examples |
|------|---------|----------|
| `IDENT` | Alphabetic or `_`-prefixed identifier, may contain `.` and `'` | `nat`, `Coq.Init.Nat.add`, `n'` |
| `NUMBER` | Digit sequence | `0`, `42` |
| `SORT` | `Prop`, `Set`, `Type` | |
| `FORALL` | `forall` keyword | |
| `FUN` | `fun` keyword | |
| `ARROW` | `->` | |
| `DARROW` | `=>` | |
| `COLON` | `:` | |
| `COMMA` | `,` | |
| `LPAREN` | `(` | |
| `RPAREN` | `)` | |
| `LBRACE` | `{` | |
| `RBRACE` | `}` | |
| `PIPE` | <code>&#124;</code> | |
| `UNDERSCORE` | Standalone `_` (not followed by alphanumeric/`_`/`'`) | |
| `INFIX_OP` | Infix operator | `+`, `*`, `=`, `<`, `<=`, `>=`, `<>`, `\/`, `/\` |
| `EOF` | End of input | |

The standalone `_` token (UNDERSCORE) is distinguished from `_`-prefixed identifiers: `_` followed by alphanumeric, `_`, or `'` is an IDENT; `_` alone or followed by whitespace/punctuation is UNDERSCORE.

Multi-character operators (`->`, `=>`, `<=`, `>=`, `<>`, `\/`, `/\`) shall be recognized before single-character operators.

> **Given** the input `"forall n : nat, n"`,
> **When** tokenized,
> **Then** the token stream is: `FORALL("forall")`, `IDENT("n")`, `COLON(":")`, `IDENT("nat")`, `COMMA(",")`, `IDENT("n")`, `EOF`.

### 4.3 Grammar and Precedence

The parser shall use Pratt (top-down operator precedence) parsing with the following infix operator precedence levels, from tightest to loosest binding:

| Binding power | Operators | Associativity |
|--------------|-----------|---------------|
| 70 | `<`, `<=`, `>`, `>=` | left |
| 65 | `\/`, `/\` | left |
| 60 | `*` | left |
| 50 | `+`, `-` | left |
| 30 | `=`, `<>` | left |
| 10 | `->` | right |

Function application (juxtaposition) binds tighter than all infix operators. The parser shall greedily consume adjacent primary expressions as application arguments.

### 4.4 ConstrNode Production Rules

| Input form | ConstrNode | Notes |
|-----------|------------|-------|
| `forall (x : T), body` | `Prod("x", T, body)` | `x` pushed to binder stack for body |
| `forall (x y : T), body` | `Prod("x", T, Prod("y", T, body))` | Grouped binders produce nested Prod |
| `forall {x : T}, body` | `Prod("x", T, body)` | Implicit binder — same ConstrNode as explicit |
| `A -> B` | `Prod("_", A, B)` | Non-dependent arrow; `"_"` binder pushed for correct de Bruijn offsets |
| `fun (x : T) => body` | `Lambda("x", T, body)` | `x` pushed to binder stack for body |
| `fun x => body` | `Lambda("x", Sort("Type"), body)` | Untyped binder defaults to `Sort("Type")` |
| `f x y` | `App(f, [x, y])` | Multi-argument application |
| `n + m` | `App(Const("+"), [n, m])` | Infix desugared to application |
| Bound name `x` | `Rel(n)` | `n` = 1-based distance from top of binder stack |
| Unbound name `x` | `Const("x")` | Names not in binder stack become constants |
| `Prop`, `Set`, `Type` | `Sort("Prop")`, `Sort("Set")`, `Sort("Type")` | |
| `_` (standalone) | `Sort("Type")` | Wildcard |
| `Coq.Init.Nat.add` | `Const("Coq.Init.Nat.add")` | Qualified names preserved as-is |
| `42` | `Const("42")` | Numeric literals as constants |
| `(expr)` | `expr` | Parentheses for grouping only |
| `{expr}` | `expr` | Braces for grouping in expression position |

### 4.5 De Bruijn Index Resolution

Names shall be resolved against a binder stack using 1-based de Bruijn indices:

- The binder stack grows as `forall`, `fun`, and `->` binders are entered.
- Name lookup searches from the top (most recently bound) to the bottom.
- The index is 1 for the most recently bound name, 2 for the next, etc.
- `"_"` binders (from non-dependent arrows) are pushed to the stack for correct offset computation but are never matched by name lookup.
- Names not found in the binder stack produce `Const(name)`.

> **Given** `forall (x : nat) (y : nat), x`,
> **When** parsing the body `x`,
> **Then** `x` resolves to `Rel(2)` (binder stack is `["x", "y"]`; `x` is at distance 2 from top).

> **Given** `forall (x : nat), x -> x`,
> **When** parsing the body `x -> x`,
> **Then** the first `x` is `Rel(1)`, the arrow pushes `"_"`, and the second `x` is `Rel(2)`.

### 4.6 Binder Parsing

Binder groups for `forall` and `fun` shall be parsed in three forms:

1. **Parenthesized**: `(name1 name2 ... : Type)` — explicit typed binder group
2. **Implicit**: `{name1 name2 ... : Type}` — implicit typed binder group (produces same ConstrNode as explicit)
3. **Unparenthesized**: `name1 name2 ... : Type` — typed binder group without delimiters (only one group before the separator `,` or `=>`)

For grouped binders like `(x y : T)`, the type `T` is shared by all names in the group. The names are not in scope during parsing of `T` (they are added after the group is complete). Subsequent binder groups DO have access to previously bound names.

> **Given** `forall (x : nat) (y : x = 0), y`,
> **When** parsing,
> **Then** in `y`'s type `x = 0`, `x` resolves to `Rel(1)` (only `x` is in scope). In the body, `y` resolves to `Rel(1)` and `x` to `Rel(2)`.

## 5. Error Specification

| Condition | Error type | Outcome |
|-----------|-----------|---------|
| Empty input | `ParseError` | Raised with descriptive message |
| Unexpected character | `ParseError` | Raised with position information |
| Unclosed parenthesis or brace | `ParseError` | Raised with position information |
| Unexpected token (e.g., trailing tokens after complete expression) | `ParseError` | Raised with position and token information |
| Missing `)` or `}` | `ParseError` | Raised with position information |

Parse failures shall never raise exceptions other than `ParseError`.

## 6. Non-Functional Requirements

- Pure Python — no external processes, no subprocess calls, no network access.
- Parsing a single type expression shall complete in under 1 millisecond for expressions up to 1000 characters.

## 7. Examples

### Simple types

```
"nat"                          → Const("nat")
"Prop"                         → Sort("Prop")
"nat -> nat"                   → Prod("_", Const("nat"), Const("nat"))
"nat -> nat -> nat"            → Prod("_", Const("nat"), Prod("_", Const("nat"), Const("nat")))
```

### Forall with binders

```
"forall n : nat, n + 0 = n"
  → Prod("n", Const("nat"),
      App(Const("="), [App(Const("+"), [Rel(1), Const("0")]), Rel(1)]))

"forall (P : nat -> Prop) (k l : nat), between P k l -> k <= l"
  → Prod("P", Prod("_", Const("nat"), Const("Prop")),
      Prod("k", Const("nat"),
        Prod("l", Const("nat"),
          Prod("_",
            App(Const("between"), [Rel(3), Rel(2), Rel(1)]),
            App(Const("<="), [Rel(3), Rel(2)])))))
```

### Infix precedence

```
"n + m * p"                    → App(Const("+"), [Const("n"), App(Const("*"), [Const("m"), Const("p")])])
```

## 8. Language-Specific Notes (Python)

- Package location: `src/poule/parsing/`.
- `Token` as a `dataclass`.
- `TokenKind` as an `Enum`.
- `TypeExprParser` class with `parse(expression: str) -> ConstrNode` method.
- Pratt parser implemented as `_expr(tokens, pos, binders, min_bp)` returning `(new_pos, ConstrNode)`.
