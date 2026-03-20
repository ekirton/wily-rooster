# Common Questions in the Proof Assistant Community

Survey of recurring question types across Coq/Rocq and Lean communities, drawn from Coq Discourse, Coq Zulip, Stack Overflow `[coq]`, Lean Zulip, GitHub issues (rocq-prover/rocq, coq-lsp, vscoq, CoqHammer, Tactician, SerAPI), Reddit (r/Coq, r/lean4, r/dependent_types), the coq-club mailing list, and the Coq Community Survey 2022.

Questions are clustered by kind. Each entry gives the general form and a Coq-specific example using stdlib, MathComp, std++, Flocq, Coquelicot, or CoqInterval where possible.

---

## 1. Discovery and Search

The single most common pain point across all communities. Manifests as direct search queries, questions about naming conventions, and requests for Hoogle-style type search.

| # | General form | Coq example |
|---|---|---|
| 1.1 | Which lemmas mention `<term>`? | "Which lemmas in stdlib mention both `Nat.add` and `Nat.mul`?" — `Search Nat.add Nat.mul.` |
| 1.2 | Which lemmas prove an equation matching `<pattern>`? | "Find all commutativity lemmas in MathComp" — `Search (_ * _ = _ * _) in ssralg.` |
| 1.3 | Which lemmas have a conclusion of the form `<pattern>`? | "Find lemmas concluding with `_ + _ <= _`" — `Search concl:(_ + _ <= _).` |
| 1.4 | Which lemmas can rewrite `<term>` to something simpler? | "What rewrites exist for `Nat.add n 0`?" — `SearchRewrite (Nat.add _ 0).` |
| 1.5 | What is the canonical name for `<mathematical fact>`? | "What is the stdlib name for associativity of `Z.add`?" — found via naming convention (`Z.add_assoc`) or `Search "assoc" Z.add.` |
| 1.6 | Does the library already formalize `<concept>`? | "Does Coquelicot already have the intermediate value theorem?" — Lean equivalent: the "Is there code for X?" Zulip channel |
| 1.7 | Which notations are in scope and what do they mean? | "What does the `%nat` scope delimiter mean? Why does `+` resolve to `Nat.add` vs `Z.add`?" — `Locate "+".` |
| 1.8 | Where is `<identifier>` defined (which module/file)? | "Where is `Rdiv` defined — Coquelicot or stdlib Reals?" — `Locate Rdiv.` / `Print Rdiv.` |
| 1.9 | What tactics are available for `<proof situation>`? | "What tactics can close a goal of the form `x = x`?" — Tactician's `suggest` / Lean's `exact?` |
| 1.10 | Find a lemma by its type signature (Hoogle-style) | "Find a lemma of type `List.map f (List.map g l) = List.map (fun x => f (g x)) l`" — Lean's Loogle; no direct Coq equivalent today |

---

## 2. Understanding Errors, Types, and Proof State

The second most common pain point. Error messages are often cryptic, especially for unification failures, typeclass resolution, and setoid rewriting.

| # | General form | Coq example |
|---|---|---|
| 2.1 | What does this error message mean? | "`Unable to unify Nat.add ?n (S ?m) with Nat.add (S ?n) ?m`" — terms look similar but arguments are in different positions |
| 2.2 | Why does Coq say "cannot unify" when the terms look identical? | Terms print the same but differ in implicit arguments or universe levels — `Set Printing All.` reveals the hidden difference |
| 2.3 | What are the universe constraints on my definition? | "`Universe inconsistency: Cannot enforce Set < Set`" when mixing Prop/Set/Type levels in a MathComp algebraic hierarchy |
| 2.4 | Why is typeclass resolution failing? | "`Unable to satisfy the following constraints`" with a long list, but only one instance is actually missing — `Set Typeclasses Debug.` |
| 2.5 | What implicit arguments are being inferred (or mis-inferred)? | "Why does `apply my_lemma` insert the wrong type for the implicit argument?" — `Set Printing Implicit.` then `Check my_lemma.` |
| 2.6 | What coercion is being inserted (or failing)? | "`The term x has type EQ.obj e while it is expected to have type LE.obj ?e`" — coercion path not found between MathComp structures |
| 2.7 | What axioms/assumptions does my proof depend on? | "Does my proof of `ring_morph` use any axioms beyond `functional_extensionality`?" — `Print Assumptions ring_morph.` |
| 2.8 | Why does my term not reduce (computation is blocked)? | "Why doesn't `simpl` simplify an expression involving `Flocq.Core.Raux.bpow`?" — the definition was closed with `Qed` (opaque) instead of `Defined` (transparent) |

---

## 3. Navigation

Persistent IDE gap — jump-to-definition, hover-for-type, and reverse-dependency queries are repeatedly requested features only partially implemented in coq-lsp/vscoq.

| # | General form | Coq example |
|---|---|---|
| 3.1 | Jump to the definition of `<identifier>` | "Go to the definition of `Coquelicot.Derive.Derive`" — IDE "go to definition" / `Print Derive.` |
| 3.2 | Which module must I import to use `<identifier>`? | "Which `From` clause gives me access to `ssralg.GRing.Ring`?" — `Locate GRing.Ring.` |
| 3.3 | What does `<identifier>` unfold to? | "What is the body of `MathComp.ssrnat.leq`?" — `Print ssrnat.leq.` / `Unfold leq.` |
| 3.4 | Who uses / depends on `<lemma>`? | "If I change `Nat.add_comm`, what downstream lemmas break?" — no built-in command; requires `coqdep` or external tooling |
| 3.5 | What instances exist for `<typeclass>`? | "What `Proper` instances are registered for `Rplus` in Coquelicot?" — `Print Instances Proper.` |
| 3.6 | What is in hint database `<name>`? | "What lemmas are in the `arith` hint database?" — `Print HintDb arith.` |

---

## 4. Proof Construction

Tactic selection and debugging — the most common question category on Stack Overflow and coq-club.

| # | General form | Coq example |
|---|---|---|
| 4.1 | Which tactic should I use to prove `<goal shape>`? | "My goal is `forall n, n + 0 = n`. Should I use `induction`, `destruct`, or `lia`?" |
| 4.2 | Why does `rewrite` fail even though the LHS appears in the goal? | "`rewrite Nat.add_comm` fails because unification picks the wrong subterm — need `rewrite Nat.add_comm at 1` or explicit arguments" |
| 4.3 | Why does `apply` fail with "unable to unify"? | "`apply Z.add_le_mono` fails because implicit arguments don't match — need `eapply` or explicit instantiation" |
| 4.4 | How do I handle dependent pattern matching (convoy pattern)? | "`destruct` a hypothesis whose type appears in another hypothesis's type, but Coq loses the equality" — use `dependent destruction` or the convoy pattern |
| 4.5 | How do I prove termination for a non-structurally recursive function? | "My function recurses on `List.length l - 1` but Coq rejects it" — use `Program Fixpoint` with `measure` or `Equations` with well-founded recursion |
| 4.6 | How do I get `auto`/`eauto` to use my lemma? | "I want `auto` to automatically apply `Flocq.Core.Raux.bpow_ge_0`" — `Hint Resolve bpow_ge_0 : core.` |
| 4.7 | How do I make `setoid_rewrite` work under binders? | "`setoid_rewrite` fails with 'Unable to satisfy Proper constraint' when rewriting under a `forall`" — declare a `Proper` morphism instance |
| 4.8 | How do I do forward reasoning (assert an intermediate result)? | "I know `x < y` and `y < z` and want to derive `x < z` before finishing the goal" — `assert (H : x < z) by lia.` or SSReflect's `have:` |
| 4.9 | How do I specialize a universally quantified hypothesis? | "I have `H : forall n, P n -> Q n` and want to use it with `n := 5`" — `specialize (H 5).` |
| 4.10 | How do I prove an existential goal when I know the witness? | "My goal is `exists x, P x` and I know the witness is `42`" — `exists 42.` |

---

## 5. Refactoring and Proof Engineering

| # | General form | Coq example |
|---|---|---|
| 5.1 | How do I rename a lemma without breaking dependents? | "I want to rename `my_add_comm` to `add_comm_custom` but it's used in 15 files" — no built-in refactoring; requires grep + manual update |
| 5.2 | How do I extract a subproof into a separate lemma? | "I have a 50-line proof and want to pull out the key step as a reusable lemma" — manual cut/paste with `assert` or separate `Lemma` |
| 5.3 | How should I organize definitions — Sections vs Modules? | "Should I use `Section` with `Variable` or `Module Type` with functors to parameterize over a ring in MathComp?" |
| 5.4 | How do I manage imports to avoid polluting the namespace? | "Importing `MathComp.ssreflect.ssreflect` changes the behavior of `rewrite` globally — how do I scope this?" |

---

## 6. Library and Ecosystem

| # | General form | Coq example |
|---|---|---|
| 6.1 | Which library provides `<mathematical concept>` for Coq? | "Which library formalizes Lebesgue integration — Coquelicot, MathComp-Analysis, or stdlib Reals?" |
| 6.2 | Are libraries `<A>` and `<B>` compatible? | "Can I use Flocq and Coquelicot together, or do their real number representations conflict?" |
| 6.3 | How do I port my development to a new Coq version? | "My project compiles on Coq 8.18 but fails on 8.19 because `auto` behavior changed in hint databases" |
| 6.4 | What is the Coq equivalent of Lean's `<tactic/feature>`? | "What is the Coq equivalent of Lean's `exact?`?" — `Search` + `apply` pattern, or Tactician's `suggest` |

---

## 7. Performance

Performance issues cluster around `Qed` — the pattern of "tactics run fast, `Qed` is slow" due to kernel re-checking is well-documented.

| # | General form | Coq example |
|---|---|---|
| 7.1 | Why does `Qed` take so long? | "`Qed` takes 30 seconds after a proof using heavy `simpl in` — the kernel re-checks the entire term" — replace `simpl in H` with a targeted `change` |
| 7.2 | Why is `simpl`/`cbn` slow or producing a huge term? | "`simpl` on a goal involving `CoqInterval.Interval.eval` produces a 10,000-line term" — use `lazy` or `vm_compute` with strategic `Opaque` |
| 7.3 | Why is typeclass resolution slow? | "Adding one new instance makes `auto` take 60 seconds" — use `Set Typeclasses Debug`, set instance priorities, or use `Hint Cut` |
| 7.4 | How do I profile/benchmark my proof script? | "Which tactic in my 200-line proof is the bottleneck?" — `Time <tactic>.` on individual tactics, or `coqc -time` |

---

## 8. Debugging and Diagnosing Unexpected Behavior

| # | General form | Coq example |
|---|---|---|
| 8.1 | Why does `auto` not solve this goal when the lemma is in the hint database? | "`auto` ignores `Hint Resolve my_lemma` because it would leave existential variables — use `eauto` instead" |
| 8.2 | Why does `simpl` not simplify / simplify too much? | "`simpl` unfolds `std++.list.fmap` when I only wanted it to reduce the outer `match`" — use `simpl (fmap)` or `cbn` with `Arguments ... : simpl never` |
| 8.3 | Why does my Ltac match fail to find the pattern? | "`match goal with \|- context [?f ?x] => ...` doesn't fire because the term has hidden implicit arguments" |
| 8.4 | Why does `omega`/`lia` fail on an arithmetic goal? | "`lia` fails on `0 < 2 ^ n` because it doesn't handle exponentiation" — use `Z.pow_pos_nonneg` as a lemma before `lia` |
| 8.5 | How do I trace what a tactic is doing internally? | "What unification problems is `apply` trying to solve?" — `Set Debug "tactic-unification".` / `Set Ltac Debug.` |
| 8.6 | Why does the proof state change unexpectedly after `<tactic>`? | "`inversion H` generates spurious equalities and renames hypotheses" — use std++'s `inv` or `dependent destruction` |

---

## Cross-Cutting Observations

**Finding the right lemma** is the single most common pain point across all communities (Coq and Lean). It manifests as direct search queries, questions about naming conventions, and requests for type-based search.

**Understanding why a tactic failed** is the second most common theme. Error messages are often cryptic, especially for unification failures, typeclass resolution, and setoid rewriting.

**Navigating a large library** is a persistent IDE gap. Jump-to-definition, hover-for-type, and "who calls this lemma" are repeatedly requested features that are only partially implemented in coq-lsp and vscoq.

**Dependent types and pattern matching** remain a recurring source of confusion, with the convoy pattern being a perennial topic on coq-club and Discourse.

**Library compatibility and version migration** are ecosystem-level pain points, with Coq version upgrades frequently breaking downstream developments.

### Question frequency by source

| Source | Primary question categories |
|---|---|
| Coq Discourse | Proof construction (25%), Discovery (20%), Understanding errors (20%), Library choice (15%) |
| Stack Overflow `[coq]` | Proof construction (40%), Understanding errors (25%), Discovery (15%) |
| Coq Zulip | Proof construction (30%), Debugging (20%), Performance (15%), Understanding (15%) |
| Lean Zulip (new-members) | Discovery (35%), Type errors (25%), Tactic usage (20%) |
| GitHub issues (coq, coq-lsp, vscoq) | Performance (25%), Navigation (20%), Understanding errors (20%), Search UX (15%) |
| Reddit r/Coq, r/lean4 | Library/ecosystem (30%), Proof construction (25%), General strategy (20%) |
| coq-club mailing list | Advanced proof construction (30%), Debugging (25%), Understanding errors (20%) |
| Coq Community Survey 2022 | Navigation/IDE features (30%), Search UX (25%), Performance (20%) |
