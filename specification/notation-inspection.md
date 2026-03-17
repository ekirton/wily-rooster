# Notation Inspection

Structured notation lookup, scope inspection, precedence/associativity extraction, and ambiguity resolution via the shared `coq_query` tool.

**Architecture**: [notation-inspection.md](../doc/architecture/notation-inspection.md)

---

## 1. Purpose

Define the notation inspection subcommands of the `coq_query` tool that allow Claude to look up notation definitions, inspect scope contents and visibility, extract precedence and associativity metadata, and resolve ambiguities when a notation has interpretations in multiple open scopes.

## 2. Scope

**In scope**: Input normalization (underscore insertion, quote escaping, whitespace normalization), command dispatch for `print_notation`, `locate_notation`, `print_scope`, and `print_visibility`, output parsing into structured data, ambiguity resolution via multi-command chaining, two-step resolution for term-based queries, error handling for notation-specific failure modes.

**Out of scope**: MCP protocol framing (owned by mcp-server), Coq backend communication (owned by proof-session), session lifecycle (owned by proof-session), vernacular introspection commands `print`, `check`, `about`, `locate`, `search`, `compute`, `eval` (owned by vernacular introspection).

## 3. Definitions

| Term | Definition |
|------|-----------|
| Notation string | A Coq notation pattern with underscore placeholders at operand positions (e.g., `_ ++ _`) |
| Scope | A named namespace grouping related notations (e.g., `nat_scope`, `list_scope`) |
| Scope stacking order | The priority-ordered sequence of open scopes; higher-priority scopes override lower-priority ones for ambiguous notations |
| Type-directed binding | A scope bound to a specific Coq type, causing Coq to prefer that scope when the expected type matches |
| Level | An integer 0--200 controlling notation precedence; lower levels bind tighter |
| Associativity | Left, right, or none; determines grouping when the same notation appears consecutively |
| Two-step resolution | Issuing `Locate` to identify a notation from a term, then `Print Notation` to retrieve full metadata |
| Input normalization | Transforming user-provided notation strings into the quoting format expected by Coq vernacular commands |

## 4. Behavioral Requirements

### 4.1 Input Normalization

#### normalize_notation(raw_input)

- REQUIRES: `raw_input` is a non-empty string representing a notation pattern or a Coq term containing notation.
- ENSURES: Returns a normalized notation string suitable for submission to Coq vernacular commands. The normalization applies three transformations in order: (1) strip leading and trailing whitespace and collapse internal whitespace to single spaces, (2) if no underscore placeholders are present and the string matches an infix/prefix/postfix pattern, insert `_` placeholders at operand positions, (3) wrap the result in double quotes with internal double quotes escaped by doubling.
- MAINTAINS: The original user input is preserved for error reporting. The normalized form is used only for command construction.

> **Given** raw input `++`
> **When** `normalize_notation` is called
> **Then** the result is `"_ ++ _"` (underscores inserted, quotes added)

> **Given** raw input `_ ++ _`
> **When** `normalize_notation` is called
> **Then** the result is `"_ ++ _"` (quotes added, placeholders unchanged)

> **Given** raw input `  x  +  y  `
> **When** `normalize_notation` is called
> **Then** leading/trailing whitespace is stripped and internal whitespace is collapsed before further processing

### 4.2 Print Notation

#### coq_query(command="print_notation", notation, session_id)

- REQUIRES: `notation` is a non-empty string. `session_id` references an active Coq session.
- ENSURES: Normalizes `notation`, constructs `Print Notation "<normalized>".`, submits to the Coq backend, parses the output into a NotationInfo structure, and returns it. When Coq returns output for multiple scopes, returns a NotationAmbiguity structure instead (see 4.5).
- MAINTAINS: The Coq session state is unchanged after the command.

> **Given** session with `Require Import Coq.Lists.List.` loaded and notation `_ ++ _`
> **When** `coq_query(command="print_notation", notation="_ ++ _", session_id=sid)` is called
> **Then** a NotationInfo is returned with `notation_string = "_ ++ _"`, a non-empty `expansion`, `level` in 0--200, `associativity` in `{"left", "right", "none"}`, and `scope = "list_scope"`

> **Given** a notation string that does not match any in-scope notation
> **When** `coq_query(command="print_notation", notation="???", session_id=sid)` is called
> **Then** a `NOTATION_NOT_FOUND` error is returned

### 4.3 Locate Notation

#### coq_query(command="locate_notation", notation, session_id)

- REQUIRES: `notation` is a non-empty string. `session_id` references an active Coq session.
- ENSURES: Normalizes `notation`, constructs `Locate "<normalized>".`, submits to the Coq backend, and parses the output into a list of NotationInterpretation structures. Each entry includes the expansion, scope, defining module, and whether it is the default interpretation.
- MAINTAINS: The Coq session state is unchanged after the command.

> **Given** a session where `+` has interpretations in `nat_scope` and `Z_scope`
> **When** `coq_query(command="locate_notation", notation="+", session_id=sid)` is called
> **Then** a list of NotationInterpretation entries is returned, one per scope, with exactly one marked `is_default = true`

> **Given** a notation with a single interpretation
> **When** `coq_query(command="locate_notation", notation="_ :: _", session_id=sid)` is called
> **Then** a list with one entry is returned, marked `is_default = true`

### 4.4 Print Scope

#### coq_query(command="print_scope", scope_name, session_id)

- REQUIRES: `scope_name` is a non-empty string. `session_id` references an active Coq session.
- ENSURES: Constructs `Print Scope <scope_name>.`, submits to the Coq backend, and parses the output into a ScopeInfo structure containing the scope name, bound type (if any), and a list of all notations registered in that scope.
- MAINTAINS: The Coq session state is unchanged after the command.

> **Given** an active session with the standard library loaded and scope `nat_scope`
> **When** `coq_query(command="print_scope", scope_name="nat_scope", session_id=sid)` is called
> **Then** a ScopeInfo is returned with `scope_name = "nat_scope"` and a non-empty `notations` list

> **Given** a scope name that does not match any registered scope
> **When** `coq_query(command="print_scope", scope_name="nonexistent_scope", session_id=sid)` is called
> **Then** a `SCOPE_NOT_FOUND` error is returned

### 4.5 Print Visibility

#### coq_query(command="print_visibility", session_id)

- REQUIRES: `session_id` references an active Coq session.
- ENSURES: Constructs `Print Visibility.`, submits to the Coq backend, and parses the output into an ordered list of (scope_name, bound_type_or_null) pairs. The list is ordered by priority (index 0 = highest priority).
- MAINTAINS: The Coq session state is unchanged after the command.

> **Given** a session with `Open Scope nat_scope.` and `Open Scope list_scope.` executed
> **When** `coq_query(command="print_visibility", session_id=sid)` is called
> **Then** an ordered list is returned containing entries for both scopes, with the most recently opened scope at a higher priority

> **Given** a session with no explicit scope openings
> **When** `coq_query(command="print_visibility", session_id=sid)` is called
> **Then** the default Coq scopes are returned in their default priority order

### 4.6 Ambiguity Resolution

When a notation has interpretations in multiple open scopes, the notation dispatcher shall resolve the ambiguity automatically:

1. The dispatcher shall issue `Locate "<notation>"` to retrieve all interpretations across scopes.
2. The dispatcher shall issue `Print Visibility.` to retrieve the current scope stacking order.
3. The dispatcher shall match each interpretation's scope against the visibility order to assign a priority rank (0 = highest).
4. The dispatcher shall identify the active interpretation as the one in the highest-priority open scope, or the one selected by type-directed scope binding.
5. The dispatcher shall return a NotationAmbiguity structure containing all interpretations in priority order, with `active_index` pointing to the active one and `resolution_reason` explaining the selection.

- REQUIRES: The notation has been located and at least two interpretations exist in currently open scopes.
- ENSURES: The returned NotationAmbiguity has `active_index` referencing a valid entry. All interpretations are present in priority order.
- MAINTAINS: The Coq session state is unchanged.

> **Given** notation `+` with interpretations in `nat_scope` (priority 0) and `Z_scope` (priority 1)
> **When** ambiguity resolution runs
> **Then** a NotationAmbiguity is returned with `active_index = 0`, `resolution_reason = "highest-priority open scope"`, and two entries in priority order

> **Given** notation `+` where `Z_scope` is bound to type `Z` and the expected type is `Z`
> **When** ambiguity resolution runs
> **Then** the `Z_scope` interpretation is active with `resolution_reason = "type-directed binding on Z"`

### 4.7 Two-Step Resolution

When the user provides a Coq term rather than a bare notation string, the dispatcher shall perform two-step resolution:

1. The dispatcher shall issue `Locate "<term>"` to identify which notation was used and in which scope.
2. The dispatcher shall issue `Print Notation "<notation>"` using the identified notation string.
3. The dispatcher shall return the full NotationInfo for the identified notation.

- REQUIRES: The input is a Coq term containing notation syntax. `session_id` references an active Coq session.
- ENSURES: The returned NotationInfo corresponds to the notation used in the term, not the term itself.
- MAINTAINS: This resolution is transparent to the caller. The caller receives a NotationInfo or NotationAmbiguity as if they had provided the notation string directly.

> **Given** input `3 + 4` (a Coq term using the `+` notation)
> **When** `coq_query(command="print_notation", notation="3 + 4", session_id=sid)` is called
> **Then** the dispatcher identifies `_ + _` as the notation, retrieves its full metadata, and returns a NotationInfo for `_ + _`

## 5. Data Model

### NotationInfo

| Field | Type | Constraints |
|-------|------|-------------|
| `notation_string` | string | Required; the notation pattern with placeholders (e.g., `_ ++ _`) |
| `expansion` | string | Required; the underlying Coq term the notation desugars to |
| `level` | integer | Required; 0--200 inclusive |
| `associativity` | `"left"` or `"right"` or `"none"` | Required |
| `arg_levels` | ordered list of (string, integer) | Required; per-placeholder name and binding level; may be empty |
| `format` | string or null | Null when no format directive is defined |
| `scope` | string | Required; scope the notation is registered in |
| `defining_module` | string or null | Fully qualified module path; null when not resolved via `Locate` |
| `only_parsing` | boolean | Required; true if notation is accepted as input only |
| `only_printing` | boolean | Required; true if notation is used in output only |

### ScopeInfo

| Field | Type | Constraints |
|-------|------|-------------|
| `scope_name` | string | Required |
| `bound_type` | string or null | Null when the scope is not bound to a type |
| `notations` | ordered list of NotationInfo | Required; may be empty for scopes with no notations |

### NotationAmbiguity

| Field | Type | Constraints |
|-------|------|-------------|
| `notation_string` | string | Required; the ambiguous notation pattern |
| `interpretations` | ordered list of NotationInterpretation | Required; length >= 2; ordered by priority rank ascending |
| `active_index` | non-negative integer | Required; valid index into `interpretations` |
| `resolution_reason` | string | Required; one of "highest-priority open scope" or "type-directed binding on {type}" |

### NotationInterpretation

| Field | Type | Constraints |
|-------|------|-------------|
| `expansion` | string | Required; the Coq term this interpretation expands to |
| `scope` | string | Required |
| `defining_module` | string or null | Null when the defining module is not available |
| `priority_rank` | non-negative integer | Required; 0 = highest priority; unique within a NotationAmbiguity |
| `is_default` | boolean | Required; true if Coq marks this as the default interpretation |

## 6. Interface Contracts

### Notation Inspection -> Proof Session Manager

| Property | Value |
|----------|-------|
| Operations used | Submit vernacular command string, receive textual output |
| Concurrency | Serialized -- one command at a time per session |
| Multi-command chaining | Ambiguity resolution issues up to 2 commands (`Locate` + `Print Visibility`) in sequence; two-step resolution issues up to 2 commands (`Locate` + `Print Notation`) |
| Session mutation | None -- all notation commands are read-only queries |
| Error strategy | Coq-level errors are caught and translated to structured error responses (see 8) |

### Notation Inspection -> coq_query Dispatcher

| Property | Value |
|----------|-------|
| Extension mechanism | Four additional `command` values: `print_notation`, `locate_notation`, `print_scope`, `print_visibility` |
| Shared infrastructure | Backend communication, session awareness, error propagation |
| Notation-specific additions | Input normalization, dedicated output parsers, multi-command chaining |

## 7. Error Specification

### 7.1 Input Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| `notation` is empty string | `PARSE_ERROR` | Return error with message "Notation string must not be empty" |
| `notation` cannot be parsed after normalization | `PARSE_ERROR` | Return error with message "Failed to parse notation string: {details}" including both original and normalized forms |
| `scope_name` is empty string (for `print_scope`) | `PARSE_ERROR` | Return error with message "Scope name must not be empty" |

### 7.2 Coq Environment Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| Notation not found in current environment | `NOTATION_NOT_FOUND` | Return error with message `Notation "{notation_string}" not found in the current environment.` |
| Scope not registered in current environment | `SCOPE_NOT_FOUND` | Return error with message `Scope {scope_name} is not registered in the current environment.` |
| No active Coq session | `SESSION_NOT_FOUND` | Return error with message "No active Coq session. Load a file first." |
| Coq backend crashed during command | `BACKEND_CRASHED` | Return error with message "The Coq backend has crashed. Close the session and open a new one." |

### 7.3 Output Parsing Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| Coq output does not match expected format | `PARSE_ERROR` | Return error with message "Failed to parse Coq output for {command}: {details}" including the raw output for diagnosis |

### 7.4 Version Compatibility Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| `Print Notation` not available (Coq < 8.19) | `UNSUPPORTED_COMMAND` | Return error with message "`Print Notation` requires Coq 8.19 or later. Use `Locate` as a fallback." |

## 8. Non-Functional Requirements

- Each notation subcommand (excluding ambiguity resolution) shall complete within 2 seconds wall-clock time under normal Coq backend load.
- Ambiguity resolution (2-command chain) shall complete within 4 seconds wall-clock time.
- Input normalization shall complete in under 10 ms for notation strings up to 500 characters.
- Output parsing shall complete in under 50 ms per command response.
- The notation dispatcher shall not cache results across tool invocations; each invocation queries the current Coq environment state.

## 9. Examples

### Print Notation -- single scope

```
coq_query(command="print_notation", notation="++", session_id="abc123")

Normalized: "_ ++ _"
Vernacular: Print Notation "_ ++ _".

Response:
{
  "notation_string": "_ ++ _",
  "expansion": "app (A:=?A) ?l ?m",
  "level": 60,
  "associativity": "right",
  "arg_levels": [("x", 59), ("y", 60)],
  "format": null,
  "scope": "list_scope",
  "defining_module": "Coq.Lists.List",
  "only_parsing": false,
  "only_printing": false
}
```

### Locate Notation -- multiple scopes

```
coq_query(command="locate_notation", notation="+", session_id="abc123")

Normalized: "_ + _"
Vernacular: Locate "_ + _".

Response:
[
  {"expansion": "Nat.add ?n ?m", "scope": "nat_scope",
   "defining_module": "Coq.Init.Nat", "priority_rank": 0, "is_default": true},
  {"expansion": "Z.add ?n ?m", "scope": "Z_scope",
   "defining_module": "Coq.ZArith.BinIntDef", "priority_rank": 1, "is_default": false}
]
```

### Print Scope

```
coq_query(command="print_scope", scope_name="nat_scope", session_id="abc123")

Vernacular: Print Scope nat_scope.

Response:
{
  "scope_name": "nat_scope",
  "bound_type": "nat",
  "notations": [
    {"notation_string": "_ + _", "expansion": "Nat.add ...", "level": 50, ...},
    {"notation_string": "_ * _", "expansion": "Nat.mul ...", "level": 40, ...},
    ...
  ]
}
```

### Ambiguity Resolution

```
coq_query(command="print_notation", notation="+", session_id="abc123")

Step 1: Locate "_ + _". -> 2 interpretations (nat_scope, Z_scope)
Step 2: Print Visibility. -> nat_scope at rank 0, Z_scope at rank 1

Response:
{
  "notation_string": "_ + _",
  "interpretations": [
    {"expansion": "Nat.add ?n ?m", "scope": "nat_scope",
     "defining_module": "Coq.Init.Nat", "priority_rank": 0, "is_default": true},
    {"expansion": "Z.add ?n ?m", "scope": "Z_scope",
     "defining_module": "Coq.ZArith.BinIntDef", "priority_rank": 1, "is_default": false}
  ],
  "active_index": 0,
  "resolution_reason": "highest-priority open scope"
}
```

### Error -- notation not found

```
coq_query(command="print_notation", notation="@@@", session_id="abc123")

Response:
{
  "error_code": "NOTATION_NOT_FOUND",
  "message": "Notation \"_ @@@ _\" not found in the current environment."
}
```

## 10. Language-Specific Notes (Python)

- Input normalization logic shall reside in a dedicated `normalize_notation` function for independent testability.
- Output parsers shall be implemented as separate functions per command type: `parse_print_notation`, `parse_locate_notation`, `parse_print_scope`, `parse_print_visibility`.
- Parsers shall use regular expressions for field extraction from Coq textual output. Each parser shall raise `ParseError` with the raw output attached when the format is not recognized.
- The notation dispatcher shall be a module within the `coq_query` handler, not a separate service. Suggested location: `src/poule/notation/`.
- Two-step resolution and ambiguity resolution shall be implemented as `async` functions to allow sequential backend commands without blocking.
- Use Python `dataclasses` or equivalent for NotationInfo, ScopeInfo, NotationAmbiguity, and NotationInterpretation.
