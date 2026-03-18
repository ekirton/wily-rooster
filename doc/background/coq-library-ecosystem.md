# Coq/Rocq Library Ecosystem: State of the Art (March 2026)

A survey of the Coq/Rocq library ecosystem covering standard libraries, mathematics formalizations, verification and programming language tools, meta-programming, automation, and community infrastructure. For each library this document records description, approximate size, maintenance status, proof style, key dependencies and dependents, and notable characteristics.

---

## 1. Standard Libraries

### 1.1 Rocq Standard Library

The **Rocq Standard Library** (formerly Coq stdlib) ships with the Rocq proof assistant and provides the foundational theories most projects depend on. As of Rocq 9.0 (March 2025) it has been split into two packages:

- **Corelib** (`rocq-core`): an extended prelude sufficient to run Rocq tactics, including the Ltac2 library and bindings for primitive types (integers, floats, arrays, strings). Remains part of the main `rocq` repository.
- **Stdlib** (`rocq-stdlib`): the main standard library, now maintained in its own repository (`rocq-prover/stdlib`).

Top-level modules include `Arith`, `Logic`, `Reals` (classical, with excluded middle and least upper bounds), `ZArith`, `Numbers`, `Sets`, `Strings`, `Lists`, `Bool`, `Init`, `Vectors`, `Program`, `Classes`, `Structures`, `Relations`, `Sorting`, and `Wellfounded`. The `From Coq Require` prefix was renamed to `From Stdlib Require` in Rocq 9.0; the old prefix still works with a deprecation warning.

| Attribute | Value |
|-----------|-------|
| Size | ~150–200k LOC (pre-split estimate) |
| Proof style | Standard Ltac (`intro`, `apply`, `rewrite`, `auto`, `lia`, `ring`, `field`) |
| Constructive | Mixed — `Reals` is classical/axiomatic |
| Maintenance | Active; Rocq core team |
| Dependents | Nearly every Coq/Rocq project |

### 1.2 Mathematical Components

**Mathematical Components** (MathComp) is an extensive, coherent repository of formalized mathematical theories powered by the SSReflect proof language. It grew out of Georges Gonthier's Four Color Theorem and Odd Order Theorem formalizations.

**Core packages** (v2.5.0, October 2025):

| Package | Contents |
|---------|----------|
| `mathcomp-boot` | Base files from ssreflect except order |
| `mathcomp-ssreflect` | Boolean reflection, basic data structures, natural numbers, sequences, finite types |
| `mathcomp-order` | Preorder and order theories |
| `mathcomp-fingroup` | Finite group theory |
| `mathcomp-algebra` | Rings, fields, polynomials, matrices, linear algebra |
| `mathcomp-field` | Field extensions, Galois theory, algebraic numbers |
| `mathcomp-solvable` | Abelian groups, center, commutators, Jordan–Hölder, Sylow theorems |
| `mathcomp-character` | Character theory of finite groups |

**Satellite packages** (separate repositories under `math-comp`):

| Package | Contents | Status |
|---------|----------|--------|
| `mathcomp-analysis` | Classical real analysis, measure theory, Lebesgue integration, topology | Active |
| `mathcomp-finmap` | Finite maps and finite sets | Maintained |
| `mathcomp-multinomials` | Multivariate polynomials | Maintained |
| `mathcomp-algebra-tactics` | `ring`/`field` tactics for MathComp algebraic structures | Maintained |
| `mathcomp-bigenough` | Asymptotic reasoning | Maintained |
| `mathcomp-real-closed` | Real closed fields | Maintained |

The MathComp family (core + fourcolor + odd-order) totals approximately 164k LOC across 187 files with ~11,300 lemmas. Proof style is SSReflect throughout: `move=>`, `apply/`, `rewrite`, `case`, `elim`, `have`, boolean reflection, and view mechanisms. Structure hierarchies use canonical structures, now managed through Hierarchy Builder. Naming conventions are systematic and formulaic.

MathComp is very actively maintained with releases approximately twice per year tracking Coq/Rocq versions. v2.5.0 supports Coq 8.20 and Rocq 9.0/9.1.

---

## 2. General-Purpose Extensions

Four libraries serve as alternative or supplementary standard libraries, each reflecting a distinct design philosophy.

| Library | Description | Size | Proof style | Key dependents | Status |
|---------|-------------|------|-------------|----------------|--------|
| **std++** (`coq-stdpp`) | Extended standard library from MPI-SWS. Efficient finite maps (`gmap`) and sets over countable keys using radix-2 search trees with extensional equality. Rich tactics and type-class-based automation. | Large (v1.12.0) | Ltac + heavy type classes | Iris, lambda-rust, and the entire Iris ecosystem | Very active |
| **coq-ext-lib** | General-purpose extension inspired by Haskell. Monads, functors, type classes, supplementary theories. Universe-polymorphic, primitive projections. | Medium (v0.13.0) | Ltac + type classes (Haskell-influenced) | Interaction Trees, Vellvm, Penn PL group projects | Maintained |
| **TLC** | Arthur Charguéraud's alternative stdlib for classical reasoning. Adopts functional extensionality, propositional extensionality, and indefinite description (Hilbert's epsilon). Includes an optimal fixed-point combinator and custom tactic library. | Large | Classical Ltac | CFML (separation logic for OCaml) | Maintained |
| **coq-record-update** | Small utility automating record field update functions via a `Settable` type class. | Very small (v0.3.6) | Ltac | Perennial, Goose, MIT PDOS projects | Maintained |

`std++` and `coq-ext-lib` are included in the Rocq Platform. `TLC` is strongly opinionated — choosing it means committing to classical axioms and its own tactic conventions. `coq-record-update` addresses a long-standing ergonomic gap; native record update syntax remains under discussion (coq/coq#10117).

---

## 3. Mathematics Libraries

### 3.1 Real and Numerical Analysis

| Library | Description | Size | Proof style | Dependencies | Status |
|---------|-------------|------|-------------|--------------|--------|
| **Coquelicot** (v3.4.3) | User-friendly real analysis. Conservative extension of stdlib `Reals` using total functions for limits, derivatives, integrals, and power series. | ~15–20k LOC | Ltac (stdlib-based) | MathComp ssreflect, stdlib Reals | Active |
| **Flocq** (v4.2.1) | Multi-radix, multi-precision floating-point formalization. Covers IEEE-754 formats, rounding modes, error bounds, FMA, square root. | ~20–30k LOC | Ltac | Stdlib (Reals, ZArith) | Active |
| **CoqInterval** (v4.11.4) | Interval arithmetic with Taylor models and automatic differentiation. Provides `interval` tactic for discharging real inequalities. | Moderate | Ltac (reflexive) | Flocq, MathComp, Coquelicot, BigNums | Active |

These three libraries form a dependency chain: Flocq provides floating-point foundations, Coquelicot provides real analysis, and CoqInterval sits on top providing automation. All are developed at Inria Saclay (Boldo, Melquiond) and included in the Rocq Platform. Flocq is also a dependency of CompCert.

### 3.2 Constructive Mathematics

| Library | Description | Size | Proof style | Status |
|---------|-------------|------|-------------|--------|
| **CoRN** | Constructive Coq Repository at Nijmegen. Algebraic hierarchy (setoids → groups → rings → fields), constructive real numbers, metric spaces, integration, exact real arithmetic. One of the oldest large Coq libraries. | ~80–100k LOC | Ltac (heavy setoid use, pre-dates type classes) | Maintained (rocq-community) |
| **math-classes** | Abstract interfaces for mathematical structures using Coq type classes. Semigroups, monoids, groups, rings, fields, lattices, categories. | Moderate | Ltac + type classes | Maintained (rocq-community) |

CoRN uses `math-classes` for its algebraic hierarchy. Both are constructive — no classical axioms. The type-class-based approach in `math-classes` contrasts with MathComp's canonical structures and CoRN's older setoid-based approach.

### 3.3 Homotopy Type Theory

**UniMath** is a large library formalizing mathematics from the univalent point of view, founded by Vladimir Voevodsky. Major packages include Foundations, Algebra, CategoryTheory (very large), Bicategories (very large), Topology, and RealNumbers. It does not depend on the Coq standard library, building entirely on its own foundations with the univalence axiom. UniMath imposes strict coding conventions: no `Admitted`, no `Axiom` beyond univalence and resizing, and avoidance of tactics that produce terms with matches on identity types. The proof style is deliberately term-based (`exact`, `apply`, `use`, `intro`, `exists`). With ~140 contributors and hundreds of thousands of lines, it is one of the largest single Coq developments. Build times are very long.

**Coq-HoTT** formalizes homotopy type theory following the HoTT Book. It covers equivalences, univalence, truncations, higher inductive types (circle, suspension, pushout), homotopy groups (including π₁(S¹) = ℤ), synthetic homotopy theory, categories, and modalities. Like UniMath it does not use the standard library (requires `-noinit -indices-matter`), but it is less restrictive in tactic usage and more willing to use Coq-specific automation. Actively maintained (last update February 2026) and included in the Rocq Platform.

| Library | Size | Proof style | Stdlib dep? | Status |
|---------|------|-------------|-------------|--------|
| **UniMath** | Very large (hundreds of k LOC) | Restricted term-based (no standard Ltac patterns) | No | Active |
| **Coq-HoTT** | Large (~100+ files) | HoTT-specific (less restrictive than UniMath) | No | Active |

### 3.4 Geometry and Information Theory

| Library | Description | Size | Proof style | Status |
|---------|-------------|------|-------------|--------|
| **GeoCoq** | Geometry based on Tarski's axiom system. Covers Euclid, Hilbert, and Tarski axiom systems, their mutual interpretations, and arithmetization connecting synthetic to analytic geometry. 199 Coq files. | ~50–80k LOC | Ltac | Active |
| **Infotheo** (v0.9.3) | Discrete probabilities, information theory, and linear error-correcting codes. Shannon entropy, mutual information, channel capacity, source coding theorem, Hamming codes. | Moderate–large | SSReflect (MathComp-based) | Active |

GeoCoq is one of the most comprehensive geometry formalizations in any proof assistant. Infotheo demonstrates MathComp's applicability beyond pure algebra and depends on MathComp ≥ 2.2.0 and MathComp-Analysis ≥ 1.2.0.

### 3.5 Number Theory and Algebra

| Library | Description | Size | Proof style | Status |
|---------|-------------|------|-------------|--------|
| **CoqPrime** | Certifying primality using Pocklington and elliptic curve certificates. Includes Lagrange and Euler–Fermat theorems. | Moderate | Ltac (computational emphasis) | Active |
| **Gaia** | Bourbaki's *Elements of Mathematics* in Coq. Set theory, ordinals (Veblen hierarchy, Schütte ψ), cardinals, natural numbers, integers, rationals, reals. Multiple sub-packages (`gaia-ordinals`, `gaia-numbers`, `gaia-schutte`, `gaia-sets`). | Moderate–large | SSReflect (MathComp-based) | Maintained (rocq-community) |

### 3.6 Landmark Formalizations

| Formalization | Description | Size | Proof style | Status |
|---------------|-------------|------|-------------|--------|
| **Four Color Theorem** | Formal proof by Georges Gonthier (2005). Combinatorial hypermaps, reducibility, discharging. Pioneered techniques that became SSReflect. | ~60k LOC | SSReflect | Maintained (rocq-community) |
| **Odd Order Theorem** | Feit–Thompson theorem: every finite group of odd order is solvable. Six-year effort completed 2012. ~4,000 definitions, ~13,000 lemmas. | ~170k LOC total (~40k proof-proper) | SSReflect | Maintained (math-comp) |
| **Coqtail-Math** | Real and complex analysis: L'Hôpital's rule, Riemann integrals for series, uncountability of reals. Extends stdlib `Reals`. | Moderate | Ltac (stdlib-based) | Maintained (rocq-community) |

The Four Color and Odd Order formalizations are historically foundational — the MathComp library and SSReflect proof language grew directly out of these projects. Many supporting libraries were factored out to become MathComp proper.

### Mathematics Libraries Summary

| Library | Proof style | Constructive? | Stdlib dep? | Maintenance |
|---------|-------------|---------------|-------------|-------------|
| Coquelicot | Ltac | No (classical) | Yes | Active |
| Flocq | Ltac | No | Yes | Active |
| CoqInterval | Ltac (reflexive) | No | Yes (via deps) | Active |
| CoRN | Ltac (setoids) | Yes | No | Moderate |
| math-classes | Ltac + type classes | Yes | Yes | Moderate |
| UniMath | Restricted term-based | Yes | No | Active |
| Coq-HoTT | HoTT-specific | Yes | No | Active |
| GeoCoq | Ltac | No | Yes | Active |
| Infotheo | SSReflect | No | Via MathComp | Active |
| CoqPrime | Ltac | No | Yes | Active |
| Gaia | SSReflect | No | Via MathComp | Maintained |
| Four Color | SSReflect | Yes | Via MathComp | Maintained |
| Odd Order | SSReflect | Yes | Via MathComp | Maintained |
| Coqtail-Math | Ltac | No | Yes | Maintained |

---

## 4. Verification and Programming Languages

### 4.1 Concurrent Separation Logic

**Iris** is a higher-order concurrent separation logic framework developed primarily at MPI-SWS. It is the most influential concurrent separation logic framework in the Coq ecosystem, serving as the foundation for a large number of verification projects. Iris uses its own standard library (`coq-stdpp`) rather than the Coq stdlib. Proofs use the Iris Proof Mode (IPM), a tactic-based DSL for separation logic with `iIntros`, `iApply`, `iDestruct`, and other `i`-prefixed tactics. The framework is very actively maintained (fifth Iris Workshop held June 2025; tutorial at POPL January 2026).

| Library | Description | Size | Proof style | Dependencies | Status |
|---------|-------------|------|-------------|--------------|--------|
| **Iris** | Higher-order concurrent separation logic framework | Large | IPM (custom Ltac DSL over stdpp) | stdpp | Very active |
| **FCSL-PCM** | Partial commutative monoids for fine-grained concurrent separation logic. ~690 lemmas. | Small–moderate | SSReflect + Hierarchy Builder | MathComp ssreflect, algebra; HB | Maintained |

FCSL-PCM is part of the IMDEA Software Institute's FCSL project and uses MathComp/SSReflect — a different ecosystem choice from Iris/stdpp.

### 4.2 Compiler Verification

**CompCert** is a high-assurance compiler for almost all of ISO C 2011, targeting ARM, PowerPC, RISC-V, and x86. Its machine-checked correctness proof guarantees generated assembly matches source C semantics. With ~100k+ LOC of Coq and ~6 person-years of original effort, it is one of the largest Coq developments. CompCert uses vanilla Ltac with extensive simulation diagrams between compiler passes. It is commercially available via AbsInt under a dual license (non-commercial use free; commercial license required otherwise). Version 3.17 (February 2026) migrated to Rocq 9.1. CompCert's Clight semantics serve as the target language for VST, CertiCoq, and Velus.

| Library | Description | Proof style | Key deps | Status |
|---------|-------------|-------------|----------|--------|
| **CompCert** (v3.17) | Verified C compiler. Found bugs in GCC/LLVM during Csmith testing while having zero itself. | Ltac (simulation diagrams) | Flocq, MenhirLib | Very active |
| **CertiCoq** / **CertiRocq** | Verified compiler from Gallina to Clight. Self-referential: a verified compiler for Coq written in Coq. Princeton (Appel group). | Ltac | MetaCoq, CompCert | Active |
| **Velus** (v3.0) | Verified Lustre compiler for safety-critical embedded systems (avionics, automotive). | Ltac (simulation-based) | CompCert (modified) | Active |
| **Jasmin** | Verified assembly language for high-assurance cryptography. Combines high-level constructs with low-level control. | SSReflect (MathComp-based) | MathComp, coqword | Active |

### 4.3 Systems Verification

| Library | Description | Proof style | Key deps | Status |
|---------|-------------|-------------|----------|--------|
| **VST** (v3.1beta) | Verified Software Toolchain. "Verifiable C" higher-order separation Hoare logic proved sound w.r.t. CompCert Clight. Floyd automation provides semi-automated tactics. VST 3.x integrates with Iris. | Separation logic (custom Ltac) | CompCert, Flocq; optionally Iris + stdpp | Active |
| **Bedrock2** | Low-level systems programming language with verified compiler targeting bare-metal RISC-V. C-like with words as only data type. LiveVerif extension provides live verification workflow. | Custom separation logic (Ltac) | coqutil, riscv-coq | Active |
| **Verdi** | Framework for verified distributed systems. Supports multiple fault models with proof transfer between idealized and realistic models. Verified Raft consensus (Verdi-Raft). | Ltac (network state machines) | Minimal | Mature |

VST's Iris integration (VST 3.x / `coq-vst-iris`) is a significant recent development unifying two major separation logic ecosystems. Bedrock2 enables end-to-end verification from specification to bare-metal RISC-V and includes Kami processor specifications for full hardware-software stack verification.

### 4.4 Cryptography and Contracts

**Fiat-Crypto** builds verified binary compilers generating correct-by-construction implementations of cryptographic field arithmetic. It synthesizes optimized C, Go, Rust, and Java from high-level specifications parameterized by modulus and hardware bitwidth. It is the most widely deployed Coq-verified code in the world — generated code runs in Google Chrome (via BoringSSL), Android, Go's standard library, the Linux kernel, and OpenBSD, estimated to secure 99%+ of web HTTPS connections. The proof style is heavily reflective/computational with reification and partial evaluation. Very actively maintained; MIT/Apache-2.0 dual license.

**ConCert** is a framework for smart contract verification featuring a certified extraction pipeline (via MetaCoq) to Liquidity, CameLIGO, and Elm. It depends on MetaCoq, stdpp, and QuickChick, combining testing with formal proofs. Developed at Aarhus University (AU-COBRA group); works with Rocq 9.0.

### 4.5 Programming Abstractions

| Library | Description | Proof style | Key deps | Status |
|---------|-------------|-------------|----------|--------|
| **Interaction Trees** (ITrees) | Coinductive data structure for representing behaviors of recursive programs that interact with environments. Coinductive variant of free monads. Solves the fundamental problem of representing impure, potentially nonterminating computations in Coq's total language. POPL 2020. | Coinductive reasoning (Ltac), weak bisimulation | paco, coq-ext-lib | Maintained |
| **lambda-rust** (RustBelt) | Semantic verification of Rust's type system soundness via logical relations built on Iris separation logic. Proves unsafe code can be verified individually and composed with the type system. POPL 2018. | Iris Proof Mode | Iris, stdpp | Maintained |
| **SSProve** | Modular cryptographic proofs via state-separating proofs. Combines algebraic SSP laws with a probabilistic relational program logic. Distinguished Paper at CSF 2025. | SSReflect (MathComp-based) | MathComp, Equations | Active |
| **WasmCert-Coq** | Mechanization of WebAssembly: operational semantics, typing, verified interpreter, type soundness (progress + preservation). Covers Wasm 2.0 with GC extension proposals. Requires ≥ 8 GB RAM to compile. | Ltac; Iris-Wasm branch adds Iris | Stdlib; optionally Iris + stdpp | Active |
| **Monae** | Hierarchy of monads with laws for equational reasoning about effectful programs. Uses Hierarchy Builder for the monad hierarchy. | SSReflect (MathComp-based) | MathComp (extensive chain through analysis) | Maintained |

### Verification Libraries Summary

| Library | Proof style | Real-world deployment | Maintenance |
|---------|-------------|-----------------------|-------------|
| Iris | IPM (custom Ltac DSL) | Research | Very active |
| FCSL-PCM | SSReflect | Research | Maintained |
| CompCert | Ltac (simulation) | Commercial (AbsInt) | Very active |
| CertiCoq | Ltac | Research | Active |
| Velus | Ltac (simulation) | Aerospace/automotive target | Active |
| Jasmin | SSReflect | Production crypto | Active |
| VST | Custom separation logic (Ltac) | Research/teaching | Active |
| Bedrock2 | Custom separation logic (Ltac) | Research | Active |
| Verdi | Ltac | Research | Mature |
| Fiat-Crypto | Reflective/computational (Ltac) | Chrome, Android, Go, Linux kernel | Very active |
| ConCert | Ltac + MetaCoq | DeFi contracts | Active |
| ITrees | Coinductive (Ltac) | Research | Maintained |
| lambda-rust | Iris Proof Mode | Research | Maintained |
| SSProve | SSReflect | Research | Active |
| WasmCert | Ltac / Iris | WebAssembly spec | Active |
| Monae | SSReflect | Research | Maintained |

---

## 5. Meta-Programming and Reflection

**MetaCoq** (now **MetaRocq**, v1.4 for Rocq 9.0) formalizes Rocq in itself. It provides syntax tree reification (Template-Rocq), a metatheory of the Polymorphic Cumulative Calculus of Inductive Constructions (PCUIC), a verified type checker (Safe Checker), and verified extraction to untyped lambda calculus. At ~300k lines of Rocq plus ~30k lines of OCaml, it is the only project providing a *verified* type checker and extraction pipeline for Rocq. Maintained by Sozeau, Forster, Tabareau, and Winterhalter. Proof style is Ltac with heavy dependent types.

**Equations** is a plugin for defining functions by dependent pattern matching and well-founded, structural, mutual, or nested recursion. It compiles to eliminators without axioms and automatically derives elimination principles. Maintained by Matthieu Sozeau; included in the Rocq Platform. It fills a genuine gap — dependent pattern matching compilation is non-trivial and error-prone by hand. Compatible with both SSReflect and vanilla Ltac.

**Coq-Elpi** (now **Rocq-Elpi**) embeds the Elpi lambda-Prolog dialect into Rocq, enabling rule-based meta-programming with native support for syntax trees with binders (HOAS). It is increasingly the preferred meta-programming platform over raw OCaml plugins, driven largely by Hierarchy Builder's success. Keynote at CoqPL 2025. Very actively maintained; supports Rocq 9.0 and 9.1.

| Library | Description | Size | Proof style / usage | Status |
|---------|-------------|------|---------------------|--------|
| **MetaCoq / MetaRocq** | Rocq formalized in itself; verified type checker and extraction | ~300k LOC Rocq + ~30k OCaml | Ltac (heavy dependent types) | Very active |
| **Equations** | Dependent pattern matching and complex recursion | Medium | Agnostic (generates proof principles) | Active |
| **Coq-Elpi / Rocq-Elpi** | Lambda-Prolog meta-programming with HOAS | Medium–large | N/A (infrastructure) | Very active |
| **Paramcoq** | Parametricity translations for data refinement | Small | N/A (automated translation) | Maintained (minimal) |
| **CoqEAL** (v2.1.0) | Effective Algebra Library — refinement from rich types to efficient implementations. Demonstrated on matrix rank, Winograd product, Karatsuba multiplication. | Medium | SSReflect + type classes | Maintained |

Paramcoq is acknowledged by its maintainers as buggy and gradually being superseded by **Trocq**, a modular parametricity plugin implemented in Coq-Elpi that unifies raw parametricity, univalent parametricity, and CoqEAL-style refinement in a single framework.

---

## 6. Automation and Decision Procedures

### 6.1 Hammers and Tactic Learners

**CoqHammer** (v1.3.2, November 2025) combines machine learning from previous proofs with translation to external ATPs (Vampire, CVC4/cvc5, E-prover, Z3) and proof reconstruction via the `sauto` tactic family. Success rate is ~40% on typical developments, reaching 78.7% on Software Foundations textbook theorems. The `sauto`/`hauto`/`qauto` tactics are useful even without external ATPs as a powerful general proof search. Included in the Rocq Platform. Proof style is agnostic — works on any Ltac-based goal.

**Tactician** learns from previously written tactic scripts using online learning that improves as the user writes more proofs. Models include k-nearest neighbors (locality-sensitive hashing), random decision forests, and Graph2Tac (graph neural network). Best models prove up to 26% of theorems fully automatically. Different niche from CoqHammer: Tactician replays Ltac-style tactics while CoqHammer translates to first-order logic. Part of Coq's CI test suite.

| Library | Approach | Success rate | Proof style | Status |
|---------|----------|-------------|-------------|--------|
| **CoqHammer** | ATP translation + `sauto` reconstruction | ~40% typical, ~79% SF | Agnostic (Ltac-based) | Very active |
| **Tactician** | Online tactic learning (k-NN, GNN) | ~26% fully automatic | Replays Ltac scripts | Active |
| **Mtac2** | Typed meta-programming monad (ICFP 2018) | N/A (manual tactic writing) | Monadic (typed alternative to Ltac) | Maintained (limited) |

### 6.2 SMT and Decision Procedures

| Library | Description | Proof style | Status |
|---------|-------------|-------------|--------|
| **SMTCoq** (v2.2) | Integrates SAT/SMT solvers (ZChaff, veriT, CVC4, cvc5) by checking proof witnesses with a certified checker. Includes Sniper extension for abducts. | Reflexive | Maintained (up to Coq 8.19) |
| **Itauto** (v8.20.0) | Reflexive intuitionistic SAT solver with DPLL-style search. Extensible: wraps arbitrary Coq tactics (`lia`, `congruence`) as theory modules for Nelson–Oppen combination. More scalable than `tauto`/`intuition` on large goals. | Reflexive | Active |
| **Gappa** (v1.7.1) | Floating-point and fixed-point bound verification. External C++ tool with Coq tactic that imports proof certificates. Part of the Flocq/Gappa/Interval trio. | Reflexive (external tool) | Active |
| **Trakt** (v1.0) | Generic goal preprocessing: translates goals by rewriting along registered morphisms before passing to decision procedures. | N/A (preprocessing) | Maintained |

### 6.3 Rewriting

**AAC Tactics** provides tactics for rewriting and proving equations modulo associativity and commutativity (`aac_rewrite`, `aac_reflexivity`, `aac_normalise`). Reflexive decision procedure for AC equality plus OCaml plugin for AC pattern matching. Users register operators as type class instances. Small, stable, solves a frequently encountered pain point. Maintained at rocq-community.

### 6.4 Testing

**QuickChick** (v2.1.1) is a randomized property-based testing plugin inspired by Haskell's QuickCheck. It includes automatic generator derivation for inductive relations and a mutation testing tool. Critical for catching bugs early before attempting proofs. Software Foundations Volume 4 is entirely devoted to QuickChick. Included in the Rocq Platform. Proof style is N/A — testing, not proving — but integrated into the Coq environment.

### Automation Summary

| Library | Type | Proof style / mechanism | In Platform? | Status |
|---------|------|-------------------------|-------------|--------|
| CoqHammer | Hammer (ATP + reconstruction) | Agnostic (Ltac-based goals) | Yes | Very active |
| Tactician | Tactic learner | Replays Ltac | No | Active |
| Mtac2 | Typed tactic programming | Monadic | Yes | Maintained |
| SMTCoq | SMT integration | Reflexive | No | Maintained |
| Itauto | Intuitionistic SAT | Reflexive (Ltac-extensible) | Yes | Active |
| Gappa | Floating-point bounds | Reflexive (external) | Yes | Active |
| Trakt | Goal preprocessing | N/A | No | Maintained |
| AAC Tactics | AC rewriting | Reflexive + plugin | Yes | Maintained |
| QuickChick | Property-based testing | N/A (testing) | Yes | Active |

---

## 7. Community Collections and Distribution

**rocq-community** (GitHub organization, renamed from coq-community) provides collaborative, community-driven long-term maintenance of Rocq packages. Projects become collective works with shared CI infrastructure, templates, and governance. Key hosted projects include AAC Tactics, Paramcoq, CoqEAL, coq-ext-lib, Trocq, CoRN, math-classes, Gaia, fourcolor, and Coqtail-Math. Each project has one or more official maintainers who can step down at any time.

**coq-contribs / rocq-archive**: The coq-contribs collection started in the mid-1990s as a tarball of user contributions. In 2015, opam replaced the tarball model. The `rocq-archive` GitHub organization now archives unmaintained projects as a historical repository.

**Rocq Platform** (latest: 2025.08.0 for Rocq 9.0.1) organizes packages into tiers:

| Level | Contents |
|-------|----------|
| Base | rocq-core, rocq-stdlib, dune |
| IDE | RocqIDE (GTK3), vscoq-language-server |
| Full | ~50+ packages: MathComp suite, Iris + stdpp, CoqHammer, Equations, Coq-Elpi, QuickChick, Flocq, Gappa, Interval, Coquelicot, HoTT, CoRN, CoqEAL, ext-lib, Mtac2, Itauto, AAC Tactics, and more |
| Extended | Beta-stage packages with plans for promotion |
| Optional | Mature but slow to build or non-open-source |

Package selection criteria include use in courses (25+ attendees) or as a prerequisite in 3+ independent developments. Maintainers commit to releasing compatible versions shortly after each Rocq release.

**Package Index**: The opam repository (`rocq-prover/opam`, renamed from `coq/opam-coq-archive`) hosts all released packages. Post-Rocq 9.0, fully ported packages use `rocq-*` names with `rocq-core`/`rocq-stdlib` dependencies; packages using compatibility shims retain `coq-*` names.

---

## 8. Cross-Cutting Observations

### 8.1 SSReflect vs. Ltac Proof Style Camps

The ecosystem has two major proof style traditions creating a soft cultural divide:

- **Vanilla Ltac**: `intros`, `apply`, `rewrite`, `destruct`, `induction`. Used by the Coq stdlib, Software Foundations, stdpp/Iris, CompCert, and most tutorials.
- **SSReflect**: Focused bookkeeping on the goal conclusion. Uses `move=>`, `apply:`, `case`, `elim` with different semantics from their Ltac counterparts. Mandatory `by` for closing goals. Used by MathComp and its ecosystem (Infotheo, FCSL-PCM, Jasmin, SSProve, Monae, Gaia).

The two styles can be mixed in a single file but not always seamlessly within a single tactic expression — SSReflect's `rewrite` has different occurrence selection and rule chaining syntax. Libraries tend to commit to one camp, creating friction when combining libraries across traditions. Ltac2 modernizes the vanilla side but does not unify with SSReflect.

### 8.2 Canonical Structures vs. Type Classes

- **Canonical structures** (CS): resolution by unification on record *fields*. Single forward rule, deterministic, predictable. Harder to use but avoids search explosions. Core mechanism in MathComp (packed classes discipline).
- **Type classes** (TC): resolution by Prolog-style backtracking search on record *parameters*. More powerful and easier to use but can cause combinatorial explosion with many indices.

Projects using MathComp should use CS (via Hierarchy Builder). Projects using stdpp/Iris or ext-lib should use TC. The debate has become less heated as Hierarchy Builder has reduced the usability gap.

### 8.3 Hierarchy Builder

**Hierarchy Builder** (HB) is a high-level DSL for declaring algebraic structure hierarchies, implemented in Coq-Elpi. Commands compile to Coq modules, sections, records, coercions, canonical structures, and notations following the packed classes discipline. MathComp 2.x rewrote its entire structure hierarchy using HB, making hierarchy extension feasible without deep knowledge of the packed class pattern. HB is arguably the most successful application of Coq-Elpi and has driven its adoption across the ecosystem. Maintained by Cohen, Sakaguchi, and Tassi.

### 8.4 Coq-to-Rocq Renaming Transition

The rename was announced October 2023 and completed with Rocq 9.0 (March 2025). Key changes:

- Binary renamed to `rocq` (compatibility shims for `coqc`, `coqtop`, etc.)
- Standard library namespace `Coq` → `Stdlib`
- Standard library split into Corelib and Stdlib
- Opam naming: `rocq-*` for ported packages, `coq-*` for shim-dependent packages
- Major projects have renamed: MetaRocq, Rocq-Elpi, rocq-community organization
- The CoqPL workshop became RocqPL starting 2026; Discourse forum moved to `discourse.rocq-prover.org`

Backward compatibility shims allow `Coq.*` imports during transition. The rename is ecosystem-wide but still in progress for many smaller packages.

### 8.5 Dependency Clustering and Ecosystem Fragmentation

The library ecosystem clusters around a few foundational choices that rarely cross:

| Cluster | Foundation | Proof style | Structure mechanism | Notable members |
|---------|-----------|-------------|---------------------|-----------------|
| **MathComp cluster** | MathComp ssreflect + algebra | SSReflect | Canonical structures (HB) | MathComp-Analysis, Infotheo, FCSL-PCM, Jasmin, SSProve, Monae, Gaia, CoqEAL |
| **Iris/stdpp cluster** | stdpp | Ltac + IPM | Type classes | Iris, lambda-rust, Actris, Diaframe, Aneris, ConCert |
| **CompCert cluster** | CompCert Clight | Vanilla Ltac | Ad hoc | VST, CertiCoq, Velus |
| **Stdlib cluster** | Coq stdlib | Vanilla Ltac | Mixed | Coquelicot, Flocq, CoqInterval, GeoCoq, Coqtail-Math |
| **HoTT cluster** | Own foundations | Term-based / restricted | N/A | UniMath, Coq-HoTT |
| **Haskell-style cluster** | coq-ext-lib | Ltac + type classes | Type classes | Interaction Trees, Vellvm |

CompCert's non-free license is a notable constraint — projects depending on CompCert inherit licensing restrictions. The MathComp and Iris/stdpp clusters are the two largest and most active but rarely interoperate directly, though VST 3.x's Iris integration and Bedrock2/Fiat-Crypto's connections to both ecosystems are bridging efforts. Projects at the boundaries (e.g., ConCert using both MetaCoq and stdpp) face dependency management challenges.

---

## References

- Bertot, Y. et al. "Canonical Structures for the Working Coq User." ITP 2013.
- Cohen, C. et al. "Hierarchy Builder: Algebraic Hierarchies Made Easy." FSCD 2020.
- Czajka, Ł. "CoqHammer: Automation for Dependent Type Theory." JAR 2018.
- Gonthier, G. "Formal Proof — The Four Color Theorem." Notices of the AMS 55(11), 2008.
- Gonthier, G. et al. "A Machine-Checked Proof of the Odd Order Theorem." ITP 2013.
- Kaiser, J.-O. et al. "Mtac2: Typed Tactics for Backward Reasoning in Coq." ICFP 2018.
- Jung, R. et al. "Iris from the Ground Up: A Modular Foundation for Higher-Order Concurrent Separation Logic." JFP 28, 2018.
- Jung, R. et al. "RustBelt: Securing the Foundations of the Rust Programming Language." POPL 2018.
- Leroy, X. "Formal Verification of a Realistic Compiler." CACM 52(7), 2009.
- Sozeau, M. et al. "MetaCoq: Complete and Certified Verified Meta-Programming for Coq." JAR 2025.
- Xia, L.-y. et al. "Interaction Trees: Representing Recursive and Impure Programs in Coq." POPL 2020.
- Ringer, T. et al. "QED at Large: A Survey of Engineering of Formally Verified Software." Foundations and Trends in PL 5(2–3), 2019.
- Rocq 9.0 Release Notes. https://rocq-prover.org/releases/9.0.0
- Rocq Platform 2025.08.0 Package List. https://github.com/rocq-prover/platform
- Iris Project. https://iris-project.org/
- MathComp. https://math-comp.github.io/
- Fiat-Crypto Adoption. https://andres.systems/fiat-crypto-adoption.html
