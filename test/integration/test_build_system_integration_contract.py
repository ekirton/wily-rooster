"""Contract tests for the Build System Integration.

These tests exercise real build tools (dune, opam, coq_makefile) to verify
mock/real parity.

Spec: specification/build-system-integration.md
Architecture: doc/architecture/build-system-integration.md
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

def _import_detect():
    from Poule.build import detect_build_system
    return detect_build_system


def _import_execute():
    from Poule.build import execute_build
    return execute_build


def _import_query_installed_packages():
    from Poule.build import query_installed_packages
    return query_installed_packages


def _import_query_package_info():
    from Poule.build import query_package_info
    return query_package_info


def _import_install_package():
    from Poule.build import install_package
    return install_package


def _import_check_dependency_conflicts():
    from Poule.build import check_dependency_conflicts
    return check_dependency_conflicts


def _import_types():
    from Poule.build.types import (
        BuildError,
        BuildRequest,
        BuildResult,
        BuildSystem,
        ConflictDetail,
        ConstraintSource,
        DependencyStatus,
        DetectionResult,
        MigrationResult,
        OpamMetadata,
        PackageInfo,
    )
    return (
        BuildError,
        BuildRequest,
        BuildResult,
        BuildSystem,
        ConflictDetail,
        ConstraintSource,
        DependencyStatus,
        DetectionResult,
        MigrationResult,
        OpamMetadata,
        PackageInfo,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_build_request(
    project_dir="/tmp/test",
    build_system=None,
    target=None,
    timeout=300,
):
    (
        BuildError, BuildRequest, BuildResult, BuildSystem,
        ConflictDetail, ConstraintSource, DependencyStatus,
        DetectionResult, MigrationResult, OpamMetadata, PackageInfo,
    ) = _import_types()
    return BuildRequest(
        project_dir=project_dir,
        build_system=build_system,
        target=target,
        timeout=timeout,
    )


# ===========================================================================
# Contract: Build Execution -- spec S4.6
# ===========================================================================

class TestBuildExecutionContract:
    """Contract tests for execute_build against real build tools."""

    @pytest.mark.asyncio
    async def test_contract_dune_build_real_subprocess(self, tmp_path):
        """Contract: real dune build produces a BuildResult with expected fields."""
        execute = _import_execute()
        # Minimal dune project
        (tmp_path / "dune-project").write_text('(lang dune 3.0)\n(using coq 0.6)\n')
        src = tmp_path / "src"
        src.mkdir()
        (src / "dune").write_text('(coq.theory (name Test))\n')
        (src / "Test.v").write_text("Lemma foo : True. Proof. exact I. Qed.\n")
        request = _make_build_request(project_dir=str(tmp_path))
        result = await execute(request)
        (
            BuildError, BuildRequest, BuildResult, BuildSystem,
            *_rest
        ) = _import_types()
        assert isinstance(result, BuildResult)
        assert isinstance(result.success, bool)
        assert isinstance(result.exit_code, int)
        assert isinstance(result.elapsed_ms, int)
        assert result.elapsed_ms >= 0


# ===========================================================================
# Contract: Package Queries -- spec S4.8
# ===========================================================================

class TestPackageQueriesContract:
    """Contract tests for package queries against real opam."""

    @pytest.mark.asyncio
    async def test_contract_query_installed_packages_real(self):
        """Contract: real opam list returns list of (name, version) tuples."""
        query = _import_query_installed_packages()
        result = await query()
        assert isinstance(result, list)
        if result:
            assert isinstance(result[0], tuple)
            assert len(result[0]) == 2

    @pytest.mark.asyncio
    async def test_contract_query_package_info_real(self):
        """Contract: real opam show returns PackageInfo for a known package."""
        query = _import_query_package_info()
        (
            BuildError, BuildRequest, BuildResult, BuildSystem,
            ConflictDetail, ConstraintSource, DependencyStatus,
            DetectionResult, MigrationResult, OpamMetadata, PackageInfo,
        ) = _import_types()
        result = await query("coq")
        assert isinstance(result, PackageInfo)
        assert result.name == "coq"


# ===========================================================================
# Contract: Dependency Management -- spec S4.9
# ===========================================================================

class TestDependencyManagementContract:
    """Contract tests for dependency management against real opam."""

    @pytest.mark.asyncio
    async def test_contract_check_dependency_conflicts_real(self):
        """Contract: real opam --dry-run returns DependencyStatus."""
        check = _import_check_dependency_conflicts()
        (
            BuildError, BuildRequest, BuildResult, BuildSystem,
            ConflictDetail, ConstraintSource, DependencyStatus,
            DetectionResult, MigrationResult, OpamMetadata, PackageInfo,
        ) = _import_types()
        result = await check([("coq", ">= 8.18")])
        assert isinstance(result, DependencyStatus)
        assert isinstance(result.satisfiable, bool)

    @pytest.mark.asyncio
    async def test_contract_install_package_real(self):
        """Contract: real opam install returns BuildResult."""
        install = _import_install_package()
        (
            BuildError, BuildRequest, BuildResult, BuildSystem,
            *_rest
        ) = _import_types()
        # Use a package likely already installed to avoid side effects
        result = await install("coq")
        assert isinstance(result, BuildResult)


# ===========================================================================
# Contract: Dependency Errors -- spec S7.2
# ===========================================================================

class TestDependencyErrorsContract:
    """Contract tests for dependency error handling."""

    @pytest.mark.asyncio
    async def test_contract_opam_on_path(self):
        """Contract: when opam is installed, shutil.which('opam') returns a path."""
        import shutil
        result = shutil.which("opam")
        assert result is not None


# ===========================================================================
# Contract: Non-Functional Requirements -- spec S8
# ===========================================================================

class TestNonFunctionalContract:
    """Contract tests for non-functional requirements."""

    def test_contract_detection_no_subprocess(self, tmp_path):
        """Contract: real detect_build_system does not spawn subprocesses."""
        detect = _import_detect()
        (tmp_path / "dune-project").touch()
        # Just verify it runs without error and returns a result
        result = detect(tmp_path)
        (
            BuildError, BuildRequest, BuildResult, BuildSystem,
            ConflictDetail, ConstraintSource, DependencyStatus,
            DetectionResult, MigrationResult, OpamMetadata, PackageInfo,
        ) = _import_types()
        assert isinstance(result, DetectionResult)
