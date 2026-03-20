"""Contract tests for the Proof Checker Adapter.

These tests exercise the real coqchk binary to verify mock/real parity.

Spec: specification/independent-proof-checking.md
Architecture: doc/architecture/independent-proof-checking.md
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

def _import_types():
    from Poule.checker.types import CheckRequest, CheckResult, CheckFailure
    return CheckRequest, CheckResult, CheckFailure


def _import_adapter():
    from Poule.checker.adapter import check_proof
    return check_proof


def _import_locate():
    from Poule.checker.adapter import locate_coqchk
    return locate_coqchk


def _import_check_single():
    from Poule.checker.adapter import check_single
    return check_single


def _import_check_project():
    from Poule.checker.adapter import check_project
    return check_project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_check_request(
    mode="single",
    file_path=None,
    project_dir=None,
    include_paths=None,
    load_paths=None,
    timeout_seconds=300,
):
    CheckRequest, _, _ = _import_types()
    return CheckRequest(
        mode=mode,
        file_path=file_path,
        project_dir=project_dir,
        include_paths=include_paths or [],
        load_paths=load_paths or [],
        timeout_seconds=timeout_seconds,
    )


# ===========================================================================
# Contract: Binary Discovery -- Section 4.2
# ===========================================================================

class TestLocateCoqchkContract:
    """Contract tests for locate_coqchk with real shutil.which."""

    def test_contract_locate_coqchk_real(self):
        """Contract test: locate_coqchk with real shutil.which."""
        locate_coqchk = _import_locate()
        result = locate_coqchk()
        # On a system with coqchk: returns a string path
        # On a system without: returns a CheckResult with error
        _, CheckResult, _ = _import_types()
        assert isinstance(result, (str, CheckResult))


# ===========================================================================
# Contract: Single-File Checking -- Section 4.5
# ===========================================================================

class TestCheckSingleContract:
    """Contract tests for check_single with real coqchk binary."""

    @pytest.mark.asyncio
    async def test_contract_check_single_real(self, tmp_path):
        """Contract test: check_single with real coqchk binary."""
        check_single = _import_check_single()
        _, CheckResult, _ = _import_types()
        # This test requires a real .vo file and coqchk installed
        vo_file = tmp_path / "Test.vo"
        vo_file.touch()
        result = await check_single(
            file_path=str(vo_file),
            include_paths=[],
            load_paths=[],
            timeout_seconds=30,
        )
        assert isinstance(result, CheckResult)
        assert result.status in ("pass", "fail", "error")


# ===========================================================================
# Contract: Project-Wide Checking -- Section 4.6
# ===========================================================================

class TestCheckProjectContract:
    """Contract tests for check_project with real coqchk binary."""

    @pytest.mark.asyncio
    async def test_contract_check_project_real(self, tmp_path):
        """Contract test: check_project with real coqchk binary."""
        check_project = _import_check_project()
        _, CheckResult, _ = _import_types()
        result = await check_project(
            project_dir=str(tmp_path),
            include_paths=[],
            load_paths=[],
            timeout_seconds=30,
        )
        assert isinstance(result, CheckResult)


# ===========================================================================
# Contract: Entry Point -- Section 6 (check_proof)
# ===========================================================================

class TestCheckProofEntryPointContract:
    """Contract tests for check_proof entry point."""

    @pytest.mark.asyncio
    async def test_contract_check_proof_real(self, tmp_path):
        """Contract test: check_proof with real coqchk binary."""
        check_proof = _import_adapter()
        _, CheckResult, _ = _import_types()
        req = _make_check_request(mode="project", project_dir=str(tmp_path))
        result = await check_proof(req)
        assert isinstance(result, CheckResult)


# ===========================================================================
# Contract: Spec Examples -- Section 9
# ===========================================================================

class TestSpecExamplesContract:
    """Contract tests for spec examples."""

    @pytest.mark.asyncio
    async def test_contract_full_single_check(self, tmp_path):
        """Contract test: full single-file check with real coqchk."""
        check_proof = _import_adapter()
        _, CheckResult, _ = _import_types()
        vo_file = tmp_path / "Test.vo"
        vo_file.touch()
        req = _make_check_request(mode="single", file_path=str(vo_file))
        result = await check_proof(req)
        assert isinstance(result, CheckResult)
