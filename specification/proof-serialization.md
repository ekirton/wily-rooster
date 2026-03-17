# Proof Serialization

JSON serialization of proof interaction data types, used for MCP responses, trace export, and proof state diffs.

**Architecture**: [proof-serialization.md](../doc/architecture/proof-serialization.md), [proof-types.md](../doc/architecture/data-models/proof-types.md)

---

## 1. Purpose

Define the JSON serialization format for all proof interaction types — ProofState, ProofTrace, PremiseAnnotation, ProofStateDiff, and their constituent types. Establish determinism guarantees and the schema versioning contract.

## 2. Scope

**In scope**: JSON field mapping for all proof types, field ordering rules, null handling, schema version lifecycle, determinism requirements, diff computation algorithm.

**Out of scope**: MCP protocol framing (owned by mcp-server), proof state production (owned by proof-session), proof type definitions (owned by data-models/proof-types).

## 3. Definitions

| Term | Definition |
|------|-----------|
| Schema version | A positive integer identifying the structure of the serialized JSON; incremented on backward-incompatible changes |
| Deterministic serialization | The property that identical input always produces byte-identical output |
| Field ordering | The fixed order in which JSON object fields are emitted, matching the data model definition order |

## 4. Behavioral Requirements

### 4.1 Schema Version

The system shall assign schema version `1` to the initial proof serialization format.

Every serialized ProofState shall include a `schema_version` field. Every serialized ProofTrace shall include a `schema_version` field.

The schema version shall be incremented when any backward-incompatible change is made:
- A field is renamed or removed
- A field's type changes
- The nesting structure changes
- The semantic meaning of a field changes

Additive changes (new optional fields) shall not require a version increment.

### 4.2 ProofState Serialization

The system shall serialize a ProofState as a JSON object with fields in the following order:

| Position | Field | JSON type | Source |
|----------|-------|-----------|--------|
| 1 | `schema_version` | integer | Constant: `1` |
| 2 | `session_id` | string | Session.session_id |
| 3 | `step_index` | integer | ProofState.step_index |
| 4 | `is_complete` | boolean | ProofState.is_complete |
| 5 | `focused_goal_index` | integer or null | ProofState.focused_goal_index; null when is_complete is true |
| 6 | `goals` | array of Goal objects | ProofState.goals; empty array when is_complete is true |

- REQUIRES: `proof_state` is a valid ProofState. When `is_complete` is false, `focused_goal_index` is a valid index into `goals`.
- ENSURES: Returns a JSON string conforming to the field order above. All fields are present in every output (no conditional omission).

> **Given** a ProofState with step_index=3, is_complete=false, focused_goal_index=0, and one goal
> **When** it is serialized
> **Then** the JSON object contains exactly 6 fields in the order: schema_version, session_id, step_index, is_complete, focused_goal_index, goals

> **Given** a completed ProofState (is_complete=true, no goals)
> **When** it is serialized
> **Then** `focused_goal_index` is `null` and `goals` is `[]`

> **Given** a ProofState with focused_goal_index=5 but only 3 goals (indices 0–2)
> **When** it is serialized
> **Then** serialization raises `ValueError`: focused_goal_index out of bounds

### 4.3 Goal Serialization

The system shall serialize a Goal as a JSON object with fields in the following order:

| Position | Field | JSON type | Source |
|----------|-------|-----------|--------|
| 1 | `index` | integer | Goal.index |
| 2 | `type` | string | Goal.type |
| 3 | `hypotheses` | array of Hypothesis objects | Goal.hypotheses; ordered as Coq presents them |

- REQUIRES: `goal` is a valid Goal with a non-negative `index` and a non-empty `type` string.
- ENSURES: Returns a JSON object with exactly 3 fields in the order above. `hypotheses` may be an empty array.

> **Given** a Goal with index=0, type="n + m = m + n", and two hypotheses
> **When** it is serialized
> **Then** the JSON object has fields in order: `index`, `type`, `hypotheses`; `hypotheses` contains 2 elements

> **Given** a Goal with index=1, type="True", and no hypotheses
> **When** it is serialized
> **Then** the JSON object has `"hypotheses":[]`

### 4.4 Hypothesis Serialization

The system shall serialize a Hypothesis as a JSON object with fields in the following order:

| Position | Field | JSON type | Source |
|----------|-------|-----------|--------|
| 1 | `name` | string | Hypothesis.name |
| 2 | `type` | string | Hypothesis.type |
| 3 | `body` | string or null | Hypothesis.body; null for non-let-bound hypotheses |

- REQUIRES: `hypothesis` is a valid Hypothesis with a non-empty `name` and non-empty `type`.
- ENSURES: Returns a JSON object with exactly 3 fields. The `body` field is always present — serialized as `null` when not let-bound.
- MAINTAINS: The `body` field is always present. When the hypothesis is not let-bound, it is serialized as `null`, not omitted.

> **Given** a non-let-bound hypothesis (name="n", type="nat", body=null)
> **When** it is serialized
> **Then** the output is `{"name":"n","type":"nat","body":null}` — `body` is explicitly `null`

> **Given** a let-bound hypothesis (name="x", type="nat", body="S O")
> **When** it is serialized
> **Then** the output is `{"name":"x","type":"nat","body":"S O"}` — `body` contains the definition term

### 4.5 ProofTrace Serialization

The system shall serialize a ProofTrace as a JSON object with fields in the following order:

| Position | Field | JSON type | Source |
|----------|-------|-----------|--------|
| 1 | `schema_version` | integer | Constant: `1` |
| 2 | `session_id` | string | ProofTrace.session_id |
| 3 | `proof_name` | string | ProofTrace.proof_name |
| 4 | `file_path` | string | ProofTrace.file_path |
| 5 | `total_steps` | integer | ProofTrace.total_steps |
| 6 | `steps` | array of TraceStep objects | ProofTrace.steps; length = total_steps + 1 |

- REQUIRES: `trace` is a valid ProofTrace with `len(steps) == total_steps + 1`.
- ENSURES: Returns a JSON string. `steps[0].tactic` is `null`. `steps[k].tactic` for k >= 1 is the tactic string. Steps are ordered by `step_index` ascending.

> **Given** a ProofTrace with total_steps=2 and 3 steps (indices 0, 1, 2)
> **When** it is serialized
> **Then** the output has `"total_steps":2` and `"steps"` contains 3 TraceStep objects

> **Given** a ProofTrace with total_steps=3 but only 3 steps (not 4)
> **When** it is serialized
> **Then** serialization raises `ValueError`: step count mismatch

### 4.6 TraceStep Serialization

The system shall serialize a TraceStep as a JSON object with fields in the following order:

| Position | Field | JSON type | Source |
|----------|-------|-----------|--------|
| 1 | `step_index` | integer | TraceStep.step_index |
| 2 | `tactic` | string or null | TraceStep.tactic; null for step 0 |
| 3 | `state` | ProofState object | TraceStep.state; inline ProofState serialization |

- REQUIRES: `trace_step` is a valid TraceStep. If `step_index == 0`, `tactic` must be null. If `step_index > 0`, `tactic` must be a non-null string.
- ENSURES: Returns a JSON object with exactly 3 fields. The `tactic` field is always present — `null` for step 0, a string for all other steps. The `state` field contains a full inline ProofState serialization.
- MAINTAINS: The `tactic` field is always present. For step 0, it is `null`, not omitted.

> **Given** a TraceStep at index 0 with tactic=null
> **When** it is serialized
> **Then** the output includes `"tactic":null` (not omitted)

> **Given** a TraceStep at index 0 with tactic="intro n."
> **When** it is serialized
> **Then** serialization raises `ValueError`: step 0 must have null tactic

> **Given** a TraceStep at index 3 with tactic=null
> **When** it is serialized
> **Then** serialization raises `ValueError`: steps 1..N must have non-null tactic

### 4.7 PremiseAnnotation Serialization

The system shall serialize a PremiseAnnotation as a JSON object with fields in the following order:

| Position | Field | JSON type | Source |
|----------|-------|-----------|--------|
| 1 | `step_index` | integer | PremiseAnnotation.step_index |
| 2 | `tactic` | string | PremiseAnnotation.tactic |
| 3 | `premises` | array of Premise objects | PremiseAnnotation.premises; ordered by appearance in tactic trace |

- REQUIRES: `annotation` is a valid PremiseAnnotation with `step_index >= 1` and a non-empty `tactic` string.
- ENSURES: Returns a JSON object with exactly 3 fields. `premises` preserves the order of appearance in the tactic trace. `premises` may be an empty array (for tactics that use no premises).

> **Given** a PremiseAnnotation with step_index=1, tactic="rewrite Nat.add_comm.", and one premise
> **When** it is serialized
> **Then** the output has fields in order: `step_index`, `tactic`, `premises`

> **Given** a PremiseAnnotation for a tactic that uses no premises (e.g., "reflexivity.")
> **When** it is serialized
> **Then** `premises` is `[]`

### 4.8 Premise Serialization

The system shall serialize a Premise as a JSON object with fields in the following order:

| Position | Field | JSON type | Source |
|----------|-------|-----------|--------|
| 1 | `name` | string | Premise.name; fully qualified canonical name |
| 2 | `kind` | string | Premise.kind; one of: `"lemma"`, `"hypothesis"`, `"constructor"`, `"definition"` |

- REQUIRES: `premise` is a valid Premise with a non-empty `name` and `kind` in `{"lemma", "hypothesis", "constructor", "definition"}`.
- ENSURES: Returns a JSON object with exactly 2 fields in the order above.

> **Given** a Premise with name="Coq.Arith.PeanoNat.Nat.add_comm" and kind="lemma"
> **When** it is serialized
> **Then** the output is `{"name":"Coq.Arith.PeanoNat.Nat.add_comm","kind":"lemma"}`

> **Given** a Premise with kind="axiom" (invalid kind)
> **When** it is serialized
> **Then** serialization raises `ValueError`: kind must be one of lemma, hypothesis, constructor, definition

### 4.9 Session Metadata Serialization

The system shall serialize Session metadata (for `list_sessions` responses) as a JSON object with fields in the following order:

| Position | Field | JSON type | Source |
|----------|-------|-----------|--------|
| 1 | `session_id` | string | Session.session_id |
| 2 | `file_path` | string | Session.file_path |
| 3 | `proof_name` | string | Session.proof_name |
| 4 | `current_step` | integer | Session.current_step |
| 5 | `total_steps` | integer or null | Session.total_steps |
| 6 | `created_at` | string | Session.created_at; ISO 8601 format |
| 7 | `last_active_at` | string | Session.last_active_at; ISO 8601 format |

- REQUIRES: `session` is a valid Session. `created_at` and `last_active_at` are UTC timestamps.
- ENSURES: Returns a JSON object with exactly 7 fields. Timestamps are formatted as ISO 8601 with seconds precision and UTC suffix `Z`. `total_steps` is `null` when the proof is open and the total is not yet known.

> **Given** a Session with total_steps=5
> **When** it is serialized
> **Then** `total_steps` is the integer `5`

> **Given** a Session where the proof has not been fully traversed (total_steps unknown)
> **When** it is serialized
> **Then** `total_steps` is `null`

> **Given** a Session with created_at="2026-03-17T14:00:00Z"
> **When** it is serialized
> **Then** `created_at` is `"2026-03-17T14:00:00Z"` (seconds precision, UTC suffix)

### 4.10 ProofStateDiff Serialization (P1)

Traceable to Story 5.2: Proof State Diff. This is a P1 (should-have) capability.

The system shall serialize a ProofStateDiff as a JSON object with fields in the following order:

| Position | Field | JSON type | Source |
|----------|-------|-----------|--------|
| 1 | `from_step` | integer | ProofStateDiff.from_step |
| 2 | `to_step` | integer | ProofStateDiff.to_step |
| 3 | `goals_added` | array of Goal objects | ProofStateDiff.goals_added |
| 4 | `goals_removed` | array of Goal objects | ProofStateDiff.goals_removed |
| 5 | `goals_changed` | array of GoalChange objects | ProofStateDiff.goals_changed |
| 6 | `hypotheses_added` | array of Hypothesis objects | ProofStateDiff.hypotheses_added |
| 7 | `hypotheses_removed` | array of Hypothesis objects | ProofStateDiff.hypotheses_removed |
| 8 | `hypotheses_changed` | array of HypothesisChange objects | ProofStateDiff.hypotheses_changed |

- REQUIRES: `diff` is a valid ProofStateDiff with `to_step == from_step + 1`.
- ENSURES: Returns a JSON object with exactly 8 fields. All array fields are present even when empty (serialized as `[]`).

> **Given** a ProofStateDiff where no goals or hypotheses changed (e.g., a tactic reordered subterms without changing the type string)
> **When** it is serialized
> **Then** all six array fields are `[]`

> **Given** a ProofStateDiff with one added goal and two removed hypotheses
> **When** it is serialized
> **Then** `goals_added` has 1 element, `hypotheses_removed` has 2 elements, all other arrays are `[]`

### 4.11 GoalChange Serialization (P1)

The system shall serialize a GoalChange as a JSON object with fields in the following order:

| Position | Field | JSON type | Source |
|----------|-------|-----------|--------|
| 1 | `index` | integer | GoalChange.index |
| 2 | `before` | string | GoalChange.before |
| 3 | `after` | string | GoalChange.after |

- REQUIRES: `goal_change` is a valid GoalChange where `before != after`.
- ENSURES: Returns a JSON object with exactly 3 fields.

> **Given** a GoalChange with index=0, before="S n + m = m + S n", after="S (n + m) = m + S n"
> **When** it is serialized
> **Then** the output is `{"index":0,"before":"S n + m = m + S n","after":"S (n + m) = m + S n"}`

### 4.12 HypothesisChange Serialization (P1)

The system shall serialize a HypothesisChange as a JSON object with fields in the following order:

| Position | Field | JSON type | Source |
|----------|-------|-----------|--------|
| 1 | `name` | string | HypothesisChange.name |
| 2 | `type_before` | string | HypothesisChange.type_before |
| 3 | `type_after` | string | HypothesisChange.type_after |
| 4 | `body_before` | string or null | HypothesisChange.body_before |
| 5 | `body_after` | string or null | HypothesisChange.body_after |

- REQUIRES: `hyp_change` is a valid HypothesisChange where `type_before != type_after` or `body_before != body_after` (or both).
- ENSURES: Returns a JSON object with exactly 5 fields. `body_before` and `body_after` are `null` for non-let-bound hypotheses.

> **Given** a HypothesisChange where only the type changed (name="IHn", type_before="n + m = m + n", type_after="S n + m = m + S n", body_before=null, body_after=null)
> **When** it is serialized
> **Then** both `body_before` and `body_after` are `null` in the output

> **Given** a HypothesisChange where the body changed (name="x", type_before="nat", type_after="nat", body_before="O", body_after="S O")
> **When** it is serialized
> **Then** `type_before` equals `type_after` and `body_before`/`body_after` reflect the change

### 4.13 Determinism

The serialization system shall produce byte-identical output for identical input. The following rules apply:

| Rule | Requirement |
|------|-------------|
| Field ordering | Fields shall be emitted in the position order defined in §4.2–§4.12 |
| List ordering — goals | Goals shall be ordered by `index` (ascending) |
| List ordering — hypotheses | Hypotheses shall be ordered as Coq presents them (insertion order from the proof context) |
| List ordering — premises | Premises shall be ordered by appearance in the tactic trace |
| List ordering — trace steps | Steps shall be ordered by `step_index` (ascending) |
| Null handling | Nullable fields shall be explicitly present with JSON `null`, never omitted |
| Integer formatting | Integers shall be serialized without leading zeros or decimal points |
| String formatting | Strings shall use JSON standard escaping (RFC 8259 §7) |
| Timestamp formatting | ISO 8601 with seconds precision and UTC timezone suffix `Z` (e.g., `"2026-03-17T14:30:00Z"`) |

> **Given** two ProofState objects with identical field values
> **When** both are serialized
> **Then** the resulting JSON strings are byte-identical

> **Given** a Hypothesis with body=null
> **When** it is serialized
> **Then** the output includes `"body": null`, not `"body"` omitted

### 4.14 Diff Computation (P1)

#### compute_diff(state_before, state_after)

- REQUIRES: `state_before` and `state_after` are valid ProofState objects. `state_after.step_index == state_before.step_index + 1`.
- ENSURES: Returns a ProofStateDiff with `from_step = state_before.step_index` and `to_step = state_after.step_index`.

**Goal matching algorithm:**

1. Build a map of `goal_index → goal_type` for both states.
2. For each index present in both states: if types differ → add to `goals_changed`. If types are identical → skip (unchanged).
3. For each index present only in `state_before` → add to `goals_removed`.
4. For each index present only in `state_after` → add to `goals_added`.

**Hypothesis matching algorithm:**

Applied to the focused goal only. The hypothesis diff compares hypotheses in `state_before.goals[state_before.focused_goal_index]` against `state_after.goals[state_after.focused_goal_index]`:

1. Build a map of `hypothesis_name → (type, body)` for the focused goal in both states.
2. For each name present in both: if `type` or `body` differs → add to `hypotheses_changed`. If both identical → skip.
3. For each name present only in state_before's focused goal → add to `hypotheses_removed`.
4. For each name present only in state_after's focused goal → add to `hypotheses_added`.

When the focused goal does not exist in both states (e.g., `state_before.focused_goal_index` refers to a goal in `goals_removed`, or one state is complete), the hypothesis-level diff lists are all empty.

MAINTAINS: Hypotheses belonging to goals in `goals_added` or `goals_removed` are reported within those goal objects, not in the hypothesis-level diff lists. The hypothesis diff tracks changes within the focused goal across both states.

> **Given** state_before has goals [G0, G1] and state_after has goals [G0'] where G0.type changed and G1 was removed
> **When** `compute_diff` is called
> **Then** `goals_changed` contains G0 with before/after types, `goals_removed` contains G1, and `goals_added` is empty

> **Given** state_before (step 2) has focused_goal_index=0 with hypotheses [n, m, IHn] and state_after (step 3) has focused_goal_index=0 with hypotheses [n, m, IHn, H] where H is new
> **When** `compute_diff` is called
> **Then** `hypotheses_added` contains H, `hypotheses_removed` is empty, `hypotheses_changed` is empty

> **Given** state_before is complete (is_complete=true, no goals) and state_after has one goal (a tactic-induced error scenario should not occur — but if called with a complete before-state)
> **When** `compute_diff` is called
> **Then** hypothesis-level diff lists are all empty (no focused goal to compare); goals in state_after appear in `goals_added`

## 5. Error Specification

| Condition | Error |
|-----------|-------|
| ProofState with `focused_goal_index` pointing to a non-existent goal | Serialization shall raise `ValueError`: focused_goal_index out of bounds |
| ProofTrace with `len(steps) != total_steps + 1` | Serialization shall raise `ValueError`: step count mismatch |
| TraceStep at index 0 with non-null tactic | Serialization shall raise `ValueError`: step 0 must have null tactic |
| TraceStep at index > 0 with null tactic | Serialization shall raise `ValueError`: steps 1..N must have non-null tactic |
| `compute_diff` with non-consecutive step indices | `ValueError`: states must be consecutive (to_step must equal from_step + 1) |
| Premise with invalid `kind` value | `ValueError`: kind must be one of lemma, hypothesis, constructor, definition |

## 6. Non-Functional Requirements

- Serialization of a single ProofState shall complete in < 1 ms for states with up to 50 goals and 200 hypotheses.
- Serialization of a ProofTrace with 100 steps shall complete in < 100 ms.
- JSON output shall be compact (no pretty-printing whitespace) unless a formatting option is explicitly requested.

## 7. Examples

### ProofState with one goal

Input:
```
ProofState(
  schema_version=1, session_id="abc-123", step_index=1,
  is_complete=false, focused_goal_index=0,
  goals=[Goal(index=0, type="n + m = m + n",
    hypotheses=[
      Hypothesis(name="n", type="nat", body=null),
      Hypothesis(name="m", type="nat", body=null)
    ]
  )]
)
```

Output:
```json
{"schema_version":1,"session_id":"abc-123","step_index":1,"is_complete":false,"focused_goal_index":0,"goals":[{"index":0,"type":"n + m = m + n","hypotheses":[{"name":"n","type":"nat","body":null},{"name":"m","type":"nat","body":null}]}]}
```

### Completed ProofState

Input:
```
ProofState(
  schema_version=1, session_id="abc-123", step_index=5,
  is_complete=true, focused_goal_index=null, goals=[]
)
```

Output:
```json
{"schema_version":1,"session_id":"abc-123","step_index":5,"is_complete":true,"focused_goal_index":null,"goals":[]}
```

### PremiseAnnotation

Input:
```
PremiseAnnotation(
  step_index=3, tactic="rewrite Nat.add_comm.",
  premises=[
    Premise(name="Coq.Arith.PeanoNat.Nat.add_comm", kind="lemma")
  ]
)
```

Output:
```json
{"step_index":3,"tactic":"rewrite Nat.add_comm.","premises":[{"name":"Coq.Arith.PeanoNat.Nat.add_comm","kind":"lemma"}]}
```

### Session metadata

Input:
```
Session(
  session_id="abc-123", file_path="/path/to/Nat.v", proof_name="Nat.add_comm",
  current_step=3, total_steps=5,
  created_at="2026-03-17T14:00:00Z", last_active_at="2026-03-17T14:05:00Z"
)
```

Output:
```json
{"session_id":"abc-123","file_path":"/path/to/Nat.v","proof_name":"Nat.add_comm","current_step":3,"total_steps":5,"created_at":"2026-03-17T14:00:00Z","last_active_at":"2026-03-17T14:05:00Z"}
```

### Diff (P1)

Given state_before (step 2) with goal G0 type `"S n + m = m + S n"` and hypothesis `IHn : n + m = m + n`, and state_after (step 3) with goal G0 type `"S (n + m) = m + S n"` and same hypothesis plus new `H : n + m = m + n`:

Output:
```json
{"from_step":2,"to_step":3,"goals_added":[],"goals_removed":[],"goals_changed":[{"index":0,"before":"S n + m = m + S n","after":"S (n + m) = m + S n"}],"hypotheses_added":[{"name":"H","type":"n + m = m + n","body":null}],"hypotheses_removed":[],"hypotheses_changed":[]}
```

## 8. Language-Specific Notes (Python)

- Use `json.dumps(obj, separators=(',', ':'), sort_keys=False)` for compact output without whitespace.
- Implement serialization functions per type (e.g., `serialize_proof_state(state) → str`) rather than relying on generic `dataclasses.asdict()`, to enforce field ordering and validation.
- Use `datetime.isoformat()` with `timespec='seconds'` for ISO 8601 timestamps. Ensure UTC timezone.
- For deterministic field ordering, construct dictionaries using `collections.OrderedDict` or rely on Python 3.7+ dict insertion order with explicit key ordering in the constructor.
- Package location: `src/poule/serialization/`.
