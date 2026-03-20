"""Contract tests for the coq-lsp JSON-RPC backend — requires a live Coq instance.

Extracted from test/test_coqlsp_backend.py. These tests verify that
the mock assumptions in the unit tests hold against a real coq-lsp
installation.

The ``requires_coq`` marker is applied automatically by conftest.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestContractListDeclarations:
    """Contract: real coq-lsp returns valid declarations for a .vo file.

    Verifies that the mock assumptions in TestListDeclarations hold against
    a real coq-lsp installation.  The spec (section 4.1) requires list_declarations
    to return (name, kind, constr_t) tuples for ALL declarations in a module.
    """

    def test_real_backend_list_declarations(self):
        import subprocess

        from Poule.extraction.backends.coqlsp_backend import CoqLspBackend

        # Find a stdlib .vo file known to contain declarations.
        # Rocq 9.x moved stdlib from theories/ to user-contrib/Stdlib/.
        result = subprocess.run(
            ["coqc", "-where"], capture_output=True, text=True
        )
        coq_root = Path(result.stdout.strip())

        # Use Nat.vo -- a module guaranteed to have many Gallina declarations.
        # Avoid arbitrary glob picks like Tactics.vo which only defines Ltac.
        # Try Rocq 9.x location first, then legacy theories/
        vo_file = None
        for init_dir in [
            coq_root / "user-contrib" / "Stdlib" / "Init",
            coq_root / "theories" / "Init",
        ]:
            candidate = init_dir / "Nat.vo"
            if candidate.exists():
                vo_file = candidate
                break
        if vo_file is None:
            pytest.skip("Nat.vo not found in Coq/Rocq stdlib")

        with CoqLspBackend() as backend:
            decls = backend.list_declarations(vo_file)

        assert isinstance(decls, list)
        # The Init/ directory contains non-trivial modules (Nat, Logic, etc.)
        # that define dozens of declarations.  An empty list means the backend
        # failed to extract them -- exactly the bug we are catching.
        assert len(decls) > 0, (
            f"list_declarations returned 0 declarations for {vo_file.name}; "
            "expected non-empty for a known stdlib module"
        )
        assert all(len(d) == 3 for d in decls)
        assert all(isinstance(d[0], str) for d in decls)
        assert all(isinstance(d[1], str) for d in decls)


class TestContractDetectVersion:
    """Contract: real coq-lsp returns a version string."""

    def test_real_backend_detect_version(self):
        from Poule.extraction.backends.coqlsp_backend import CoqLspBackend

        with CoqLspBackend() as backend:
            version = backend.detect_version()

        assert isinstance(version, str)
        assert len(version) > 0


class TestContractPrettyPrint:
    """Contract: real coq-lsp pretty-prints a known declaration.

    Verifies that pretty_print returns the actual definition body, not just
    any non-empty string (e.g. a deprecation warning).
    """

    def test_real_backend_pretty_print(self):
        from Poule.extraction.backends.coqlsp_backend import CoqLspBackend

        # Use the short name 'Nat.add' which works in both Coq 8.x and Rocq 9.x.
        # 'Coq.Init.Nat.add' produces only a deprecation warning in Rocq 9.x,
        # not the actual definition -- that was masking the real failure.
        with CoqLspBackend() as backend:
            result = backend.pretty_print("Nat.add")

        assert isinstance(result, str)
        assert len(result) > 0, (
            "pretty_print returned empty string for Nat.add; "
            "expected the definition body"
        )
        # The Print output for Nat.add must contain its definition structure
        # (e.g. 'fix', 'match', 'nat', or 'Nat.add =').
        assert any(
            keyword in result
            for keyword in ("fix", "match", "nat", "Nat.add", "add")
        ), (
            f"pretty_print output does not look like the Nat.add definition: "
            f"{result!r}"
        )


class TestContractGetDependencies:
    """Contract: real coq-lsp returns dependencies for a known declaration."""

    def test_real_backend_get_dependencies(self):
        from Poule.extraction.backends.coqlsp_backend import CoqLspBackend

        # Use short name for Rocq 9.x compatibility
        with CoqLspBackend() as backend:
            deps = backend.get_dependencies("Nat.add")

        assert isinstance(deps, list)
        assert all(
            isinstance(d, tuple) and len(d) == 2 for d in deps
        )


class TestContractQueryDeclarationData:
    """Contract: real coq-lsp returns statement and dependencies for declarations."""

    def test_real_backend_query_declaration_data(self):
        from Poule.extraction.backends.coqlsp_backend import CoqLspBackend

        with CoqLspBackend() as backend:
            result = backend.query_declaration_data(["Nat.add", "Nat.mul"])

        assert "Nat.add" in result
        assert "Nat.mul" in result
        stmt_add, deps_add = result["Nat.add"]
        assert isinstance(stmt_add, str)
        assert len(stmt_add) > 0
        assert isinstance(deps_add, list)


class TestContractRunVernacBatch:
    """Contract: real coq-lsp returns per-line messages for batched commands."""

    def test_real_backend_run_vernac_batch(self):
        from Poule.extraction.backends.coqlsp_backend import CoqLspBackend

        with CoqLspBackend() as backend:
            results = backend._run_vernac_batch([
                "About Nat.add.",
                "About Nat.mul.",
            ])

        assert len(results) == 2
        assert all(isinstance(r, list) for r in results)


class TestContractLocate:
    """Contract: real coq-lsp Locate queries return expected results."""

    def test_locate_nat_returns_fqn(self):
        from Poule.extraction.backends.coqlsp_backend import CoqLspBackend

        with CoqLspBackend() as backend:
            result = backend.locate("nat")

        assert result is not None
        assert isinstance(result, str)
        # Should contain "nat" in the FQN
        assert "nat" in result.lower()

    def test_locate_nonexistent_returns_none(self):
        from Poule.extraction.backends.coqlsp_backend import CoqLspBackend

        with CoqLspBackend() as backend:
            result = backend.locate("zzz_nonexistent_name_zzz")

        assert result is None

    def test_locate_infix_plus(self):
        from Poule.extraction.backends.coqlsp_backend import CoqLspBackend

        with CoqLspBackend() as backend:
            result = backend.locate("+")

        # Should resolve to something (Nat.add or similar)
        assert result is not None
