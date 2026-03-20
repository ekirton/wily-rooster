# Feedback: vernacular-introspection.md

## 1. Session-free prelude/environment is underspecified

**Severity:** medium

**Section:** §4.3.2 (Session-Free Execution)

**Issue:** The spec says the command executes against "the default global environment (standard library and project-level imports configured for the MCP server)" but does not define:

- What "project-level imports" means concretely (opam packages? `_CoqProject` bindings? installed libraries?)
- How the prelude is configured (config file, environment variable, command-line argument?)
- Whether all installed opam packages should be available or only explicitly listed ones

**Impact:** The current implementation hardcodes `From Coq Require Import Arith.` as the default prelude. A user querying `Print leq` (MathComp) gets an error because MathComp isn't loaded, even though it's installed in the environment. The implementer must make a judgment call that the spec should have made.

**Suggested resolution:** Specify either:
- (a) The prelude auto-discovers installed Coq packages via `coqtop -config` or similar, or
- (b) The prelude is configurable via a server setting, with a defined default, or
- (c) All opam-installed Coq packages are available by default via `-R` / `-Q` path bindings
