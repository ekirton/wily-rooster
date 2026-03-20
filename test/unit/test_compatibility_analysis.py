"""TDD tests for the Compatibility Analysis (specification/compatibility-analysis.md).

Tests are written BEFORE implementation. They will fail with ImportError
until src/poule/compat/ modules exist.

Spec: specification/compatibility-analysis.md
Architecture: doc/architecture/compatibility-analysis.md

Import paths under test (per spec §10):
  poule.compat  (scan_dependencies, resolve_metadata, parse_constraint, etc.)
"""

from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Lazy imports — fail with ImportError until implementation exists
# ---------------------------------------------------------------------------

def _import_scan_dependencies():
    from Poule.compat import scan_dependencies
    return scan_dependencies


def _import_resolve_metadata():
    from Poule.compat import resolve_metadata
    return resolve_metadata


def _import_parse_constraint():
    from Poule.compat import parse_constraint
    return parse_constraint


def _import_detect_conflicts():
    from Poule.compat import detect_conflicts
    return detect_conflicts


def _import_build_explanation():
    from Poule.compat import build_explanation
    return build_explanation


def _import_suggest_resolutions():
    from Poule.compat import suggest_resolutions
    return suggest_resolutions


def _import_compare_versions():
    from Poule.compat import compare_versions
    return compare_versions


def _import_intersect():
    from Poule.compat import intersect
    return intersect


def _import_is_empty():
    from Poule.compat import is_empty
    return is_empty


def _import_types():
    from Poule.compat.types import (
        CompatibleSet,
        Conflict,
        ConflictSet,
        ConstraintEdge,
        DeclaredDependency,
        DependencySet,
        ExplanationText,
        PackageNode,
        Resolution,
        ResolvedConstraintTree,
        VersionBound,
        VersionConstraint,
        VersionInterval,
    )
    return (
        CompatibleSet,
        Conflict,
        ConflictSet,
        ConstraintEdge,
        DeclaredDependency,
        DependencySet,
        ExplanationText,
        PackageNode,
        Resolution,
        ResolvedConstraintTree,
        VersionBound,
        VersionConstraint,
        VersionInterval,
    )


def _import_errors():
    from Poule.compat.errors import (
        CONSTRAINT_PARSE_ERROR,
        INVALID_PARAMETER,
        NO_DEPENDENCIES,
        OPAM_TIMEOUT,
        PACKAGE_NOT_FOUND,
        PROJECT_NOT_FOUND,
        TOOL_NOT_FOUND,
        CompatError,
    )
    return (
        CONSTRAINT_PARSE_ERROR,
        INVALID_PARAMETER,
        NO_DEPENDENCIES,
        OPAM_TIMEOUT,
        PACKAGE_NOT_FOUND,
        PROJECT_NOT_FOUND,
        TOOL_NOT_FOUND,
        CompatError,
    )


# ---------------------------------------------------------------------------
# Helpers — construct data model instances for test inputs
# ---------------------------------------------------------------------------

def _make_version_bound(version, inclusive):
    (
        CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
        DeclaredDependency, DependencySet, ExplanationText,
        PackageNode, Resolution, ResolvedConstraintTree,
        VersionBound, VersionConstraint, VersionInterval,
    ) = _import_types()
    return VersionBound(version=version, inclusive=inclusive)


def _make_version_interval(lower=None, upper=None):
    (
        CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
        DeclaredDependency, DependencySet, ExplanationText,
        PackageNode, Resolution, ResolvedConstraintTree,
        VersionBound, VersionConstraint, VersionInterval,
    ) = _import_types()
    return VersionInterval(lower=lower, upper=upper)


def _make_version_constraint(intervals):
    (
        CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
        DeclaredDependency, DependencySet, ExplanationText,
        PackageNode, Resolution, ResolvedConstraintTree,
        VersionBound, VersionConstraint, VersionInterval,
    ) = _import_types()
    return VersionConstraint(intervals=intervals)


def _make_declared_dependency(
    package_name, version_constraint=None, source_file="/tmp/test/mylib.opam",
    hypothetical=False,
):
    (
        CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
        DeclaredDependency, DependencySet, ExplanationText,
        PackageNode, Resolution, ResolvedConstraintTree,
        VersionBound, VersionConstraint, VersionInterval,
    ) = _import_types()
    return DeclaredDependency(
        package_name=package_name,
        version_constraint=version_constraint,
        source_file=source_file,
        hypothetical=hypothetical,
    )


def _make_dependency_set(
    dependencies, project_dir="/tmp/test", build_system="DUNE",
    unknown_packages=None,
):
    (
        CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
        DeclaredDependency, DependencySet, ExplanationText,
        PackageNode, Resolution, ResolvedConstraintTree,
        VersionBound, VersionConstraint, VersionInterval,
    ) = _import_types()
    return DependencySet(
        dependencies=dependencies,
        project_dir=project_dir,
        build_system=build_system,
        unknown_packages=unknown_packages or [],
    )


def _make_package_node(name, available_versions, installed_version=None):
    (
        CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
        DeclaredDependency, DependencySet, ExplanationText,
        PackageNode, Resolution, ResolvedConstraintTree,
        VersionBound, VersionConstraint, VersionInterval,
    ) = _import_types()
    return PackageNode(
        name=name,
        available_versions=available_versions,
        installed_version=installed_version,
    )


def _make_constraint_edge(from_package, to_package, constraint, raw_constraint):
    (
        CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
        DeclaredDependency, DependencySet, ExplanationText,
        PackageNode, Resolution, ResolvedConstraintTree,
        VersionBound, VersionConstraint, VersionInterval,
    ) = _import_types()
    return ConstraintEdge(
        from_package=from_package,
        to_package=to_package,
        constraint=constraint,
        raw_constraint=raw_constraint,
    )


def _make_constraint_tree(root_dependencies, nodes, edges):
    (
        CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
        DeclaredDependency, DependencySet, ExplanationText,
        PackageNode, Resolution, ResolvedConstraintTree,
        VersionBound, VersionConstraint, VersionInterval,
    ) = _import_types()
    return ResolvedConstraintTree(
        root_dependencies=root_dependencies,
        nodes=nodes,
        edges=edges,
    )


def _make_conflict(resource, minimal_constraint_set, explanation=None, resolutions=None):
    (
        CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
        DeclaredDependency, DependencySet, ExplanationText,
        PackageNode, Resolution, ResolvedConstraintTree,
        VersionBound, VersionConstraint, VersionInterval,
    ) = _import_types()
    return Conflict(
        resource=resource,
        minimal_constraint_set=minimal_constraint_set,
        explanation=explanation,
        resolutions=resolutions or [],
    )


def _make_explanation(summary, constraint_chains):
    (
        CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
        DeclaredDependency, DependencySet, ExplanationText,
        PackageNode, Resolution, ResolvedConstraintTree,
        VersionBound, VersionConstraint, VersionInterval,
    ) = _import_types()
    return ExplanationText(summary=summary, constraint_chains=constraint_chains)


def _make_resolution(
    strategy, target_package, target_version=None,
    alternative_package=None, trade_off="",
):
    (
        CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
        DeclaredDependency, DependencySet, ExplanationText,
        PackageNode, Resolution, ResolvedConstraintTree,
        VersionBound, VersionConstraint, VersionInterval,
    ) = _import_types()
    return Resolution(
        strategy=strategy,
        target_package=target_package,
        target_version=target_version,
        alternative_package=alternative_package,
        trade_off=trade_off,
    )


# ---------------------------------------------------------------------------
# Helper: build a simple constraint tree with two direct deps on coq
# ---------------------------------------------------------------------------

def _two_dep_tree(
    dep_a_name, dep_a_coq_raw, dep_a_coq_constraint,
    dep_b_name, dep_b_coq_raw, dep_b_coq_constraint,
    coq_versions,
):
    """Build a ResolvedConstraintTree where dep_a and dep_b both constrain coq."""
    nodes = {
        dep_a_name: _make_package_node(dep_a_name, ["2.2.0", "2.0.0"]),
        dep_b_name: _make_package_node(dep_b_name, ["4.1.0", "4.0.0"]),
        "coq": _make_package_node("coq", coq_versions),
    }
    edges = [
        _make_constraint_edge(dep_a_name, "coq", dep_a_coq_constraint, dep_a_coq_raw),
        _make_constraint_edge(dep_b_name, "coq", dep_b_coq_constraint, dep_b_coq_raw),
    ]
    return _make_constraint_tree(
        root_dependencies=[dep_a_name, dep_b_name],
        nodes=nodes,
        edges=edges,
    )


# ===========================================================================
# 1. Data Model — spec §5
# ===========================================================================

class TestDataModel:
    """§5: All data structures are frozen dataclasses (§10)."""

    def test_dependency_set_frozen(self):
        """DependencySet is immutable (§10 frozen=True)."""
        ds = _make_dependency_set(
            dependencies=[_make_declared_dependency("coq", '>= "8.18"')],
        )
        with pytest.raises(AttributeError):
            ds.project_dir = "/other"  # type: ignore[misc]

    def test_declared_dependency_frozen(self):
        """DeclaredDependency is immutable."""
        dd = _make_declared_dependency("coq")
        with pytest.raises(AttributeError):
            dd.package_name = "other"  # type: ignore[misc]

    def test_version_constraint_requires_at_least_one_interval(self):
        """VersionConstraint.intervals must have at least one entry (§5)."""
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()
        # Construction with empty intervals should raise or be enforced
        # The spec says "at least one interval" — implementation should validate.
        vc = VersionConstraint(intervals=[])
        # If no validation at construction, the is_empty utility should detect it
        is_empty = _import_is_empty()
        assert is_empty(vc)

    def test_version_bound_fields(self):
        """VersionBound has version (string) and inclusive (boolean) (§5)."""
        vb = _make_version_bound("8.18", True)
        assert vb.version == "8.18"
        assert vb.inclusive is True

    def test_version_interval_nullable_bounds(self):
        """VersionInterval allows null lower/upper for unbounded ranges (§5)."""
        vi = _make_version_interval(lower=None, upper=None)
        assert vi.lower is None
        assert vi.upper is None

    def test_conflict_requires_at_least_two_constraints(self):
        """Conflict.minimal_constraint_set requires at least two entries (§5)."""
        # Verify the data model enforces or represents this constraint
        vc = _make_version_constraint([_make_version_interval()])
        edge1 = _make_constraint_edge("a", "coq", vc, '>= "8.18"')
        edge2 = _make_constraint_edge("b", "coq", vc, '< "8.18"')
        conflict = _make_conflict("coq", [edge1, edge2])
        assert len(conflict.minimal_constraint_set) >= 2

    def test_conflict_explanation_nullable(self):
        """Conflict.explanation is null when returned by detect_conflicts (§5 lifecycle)."""
        vc = _make_version_constraint([_make_version_interval()])
        edge1 = _make_constraint_edge("a", "coq", vc, '>= "8.18"')
        edge2 = _make_constraint_edge("b", "coq", vc, '< "8.18"')
        conflict = _make_conflict("coq", [edge1, edge2])
        assert conflict.explanation is None

    def test_explanation_requires_at_least_two_chains(self):
        """ExplanationText.constraint_chains requires at least two chains (§5)."""
        explanation = _make_explanation(
            "test conflict",
            [["a", "requires coq >= 8.18"], ["b", "requires coq < 8.18"]],
        )
        assert len(explanation.constraint_chains) >= 2

    def test_compatible_set_verdict_is_compatible(self):
        """CompatibleSet.verdict is always 'compatible' (§5)."""
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()
        vc = VersionConstraint(intervals=[VersionInterval(lower=None, upper=None)])
        cs = CompatibleSet(
            verdict="compatible",
            version_map={"coq": "8.19.0"},
            coq_version_range=vc,
        )
        assert cs.verdict == "compatible"

    def test_conflict_set_verdict_is_incompatible(self):
        """ConflictSet.verdict is always 'incompatible' (§5)."""
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()
        vc = VersionConstraint(intervals=[VersionInterval(lower=None, upper=None)])
        edge1 = ConstraintEdge("a", "coq", vc, '>= "8.18"')
        edge2 = ConstraintEdge("b", "coq", vc, '< "8.18"')
        # detect_conflicts returns Conflict with explanation=None (§5 lifecycle)
        conflict = Conflict(
            resource="coq",
            minimal_constraint_set=[edge1, edge2],
            explanation=None,
            resolutions=[],
        )
        result = ConflictSet(verdict="incompatible", conflicts=[conflict])
        assert result.verdict == "incompatible"
        assert len(result.conflicts) >= 1

    def test_resolution_strategy_values(self):
        """Resolution.strategy is one of UPGRADE, DOWNGRADE, ALTERNATIVE, NO_RESOLUTION (§5)."""
        valid_strategies = {"UPGRADE", "DOWNGRADE", "ALTERNATIVE", "NO_RESOLUTION"}
        for strategy in valid_strategies:
            r = _make_resolution(
                strategy=strategy,
                target_package="coq-lib",
                target_version="1.0" if strategy in ("UPGRADE", "DOWNGRADE") else None,
                alternative_package="coq-alt" if strategy == "ALTERNATIVE" else None,
                trade_off="some trade-off",
            )
            assert r.strategy in valid_strategies

    def test_package_node_versions_descending(self):
        """PackageNode.available_versions is ordered descending (§5)."""
        node = _make_package_node("coq", ["8.19.0", "8.18.0", "8.17.0"])
        assert node.available_versions == ["8.19.0", "8.18.0", "8.17.0"]

    def test_declared_dependency_hypothetical_flag(self):
        """DeclaredDependency.hypothetical is true for hypothetical additions (§5)."""
        dd = _make_declared_dependency("coq-equations", hypothetical=True)
        assert dd.hypothetical is True


# ===========================================================================
# 2. Dependency Scanning — spec §4.1
# ===========================================================================

@patch("Poule.compat.scanner._opam_package_exists", return_value=True)
class TestDependencyScanning:
    """§4.1: scan_dependencies(project_dir, hypothetical_additions)."""

    def test_opam_file_extracts_depends(self, _mock_exists, tmp_path):
        """Given a .opam file with depends, extract declared dependencies (§4.1 example 1)."""
        scan = _import_scan_dependencies()
        opam_content = textwrap.dedent("""\
            opam-version: "2.0"
            depends: [
              "coq" {>= "8.18"}
              "coq-mathcomp-ssreflect"
            ]
        """)
        (tmp_path / "mylib.opam").write_text(opam_content)
        result = asyncio.get_event_loop().run_until_complete(
            scan(tmp_path, [])
        )
        names = [d.package_name for d in result.dependencies]
        assert "coq" in names
        assert "coq-mathcomp-ssreflect" in names
        coq_dep = next(d for d in result.dependencies if d.package_name == "coq")
        assert coq_dep.version_constraint is not None
        assert "8.18" in coq_dep.version_constraint
        mathcomp_dep = next(
            d for d in result.dependencies if d.package_name == "coq-mathcomp-ssreflect"
        )
        assert mathcomp_dep.version_constraint is None

    def test_opam_file_source_tracking(self, _mock_exists, tmp_path):
        """Dependencies from .opam files have source_file pointing to the .opam file (§4.1)."""
        scan = _import_scan_dependencies()
        opam_content = 'opam-version: "2.0"\ndepends: ["coq" {>= "8.18"}]\n'
        opam_path = tmp_path / "mylib.opam"
        opam_path.write_text(opam_content)
        result = asyncio.get_event_loop().run_until_complete(scan(tmp_path, []))
        coq_dep = next(d for d in result.dependencies if d.package_name == "coq")
        assert str(opam_path) in coq_dep.source_file

    def test_dune_project_extracts_depends(self, _mock_exists, tmp_path):
        """Given a dune-project file with depends, extract entries (§4.1)."""
        scan = _import_scan_dependencies()
        dune_content = textwrap.dedent("""\
            (lang dune 3.0)
            (name mylib)
            (depends
             (coq (>= 8.18))
             coq-mathcomp-ssreflect)
        """)
        (tmp_path / "dune-project").write_text(dune_content)
        result = asyncio.get_event_loop().run_until_complete(scan(tmp_path, []))
        names = [d.package_name for d in result.dependencies]
        assert "coq" in names
        assert "coq-mathcomp-ssreflect" in names

    def test_coq_project_infers_package_from_logical_root(self, _mock_exists, tmp_path):
        """Given _CoqProject with -Q src Mathcomp, infer coq-mathcomp-ssreflect (§4.1 example 2)."""
        scan = _import_scan_dependencies()
        (tmp_path / "_CoqProject").write_text("-Q src Mathcomp\n")
        result = asyncio.get_event_loop().run_until_complete(scan(tmp_path, []))
        names = [d.package_name for d in result.dependencies]
        assert "coq-mathcomp-ssreflect" in names

    def test_hypothetical_additions_marked(self, _mock_exists, tmp_path):
        """Hypothetical additions are flagged with hypothetical=true (§4.1 example 3)."""
        scan = _import_scan_dependencies()
        opam_content = 'opam-version: "2.0"\ndepends: ["coq" {>= "8.18"}]\n'
        (tmp_path / "mylib.opam").write_text(opam_content)
        result = asyncio.get_event_loop().run_until_complete(
            scan(tmp_path, ["coq-equations"])
        )
        hyp = [d for d in result.dependencies if d.package_name == "coq-equations"]
        assert len(hyp) == 1
        assert hyp[0].hypothetical is True
        # File-sourced dependencies are not hypothetical
        coq_dep = next(d for d in result.dependencies if d.package_name == "coq")
        assert coq_dep.hypothetical is False

    def test_unknown_package_added_to_unknown_packages(self, _mock_exists, tmp_path):
        """Unknown packages go to unknown_packages; scanning continues (§4.1, §7.2)."""
        scan = _import_scan_dependencies()
        opam_content = 'opam-version: "2.0"\ndepends: ["coq" {>= "8.18"}]\n'
        (tmp_path / "mylib.opam").write_text(opam_content)
        with patch("Poule.compat.scanner._opam_package_exists", return_value=False):
            result = asyncio.get_event_loop().run_until_complete(
                scan(tmp_path, ["coq-nonexistent-lib"])
            )
        assert "coq-nonexistent-lib" in result.unknown_packages

    def test_same_package_multiple_files_retains_both(self, _mock_exists, tmp_path):
        """Same package in multiple files: retain one entry per source (§4.1)."""
        scan = _import_scan_dependencies()
        opam_content = 'opam-version: "2.0"\ndepends: ["coq" {>= "8.18"}]\n'
        (tmp_path / "mylib.opam").write_text(opam_content)
        dune_content = '(lang dune 3.0)\n(name mylib)\n(depends (coq (>= 8.18)))\n'
        (tmp_path / "dune-project").write_text(dune_content)
        result = asyncio.get_event_loop().run_until_complete(scan(tmp_path, []))
        coq_deps = [d for d in result.dependencies if d.package_name == "coq"]
        sources = {d.source_file for d in coq_deps}
        assert len(sources) >= 2

    def test_build_system_field_populated(self, _mock_exists, tmp_path):
        """DependencySet.build_system reflects detected build system (§4.1)."""
        scan = _import_scan_dependencies()
        (tmp_path / "dune-project").write_text('(lang dune 3.0)\n(name mylib)\n(depends coq)\n')
        result = asyncio.get_event_loop().run_until_complete(scan(tmp_path, []))
        assert result.build_system is not None

    def test_project_dir_is_absolute(self, _mock_exists, tmp_path):
        """DependencySet.project_dir is an absolute path (§5)."""
        scan = _import_scan_dependencies()
        (tmp_path / "mylib.opam").write_text('opam-version: "2.0"\ndepends: ["coq"]\n')
        result = asyncio.get_event_loop().run_until_complete(scan(tmp_path, []))
        assert Path(result.project_dir).is_absolute()

    def test_no_files_modified(self, _mock_exists, tmp_path):
        """MAINTAINS: No project files are modified (§4.1)."""
        scan = _import_scan_dependencies()
        opam_content = 'opam-version: "2.0"\ndepends: ["coq"]\n'
        opam_file = tmp_path / "mylib.opam"
        opam_file.write_text(opam_content)
        before = opam_file.read_text()
        asyncio.get_event_loop().run_until_complete(scan(tmp_path, []))
        assert opam_file.read_text() == before


# ===========================================================================
# 3. Dependency Scanning — Error Cases — spec §7.1
# ===========================================================================

class TestDependencyScanningErrors:
    """§7.1, §7.2: Error conditions for scan_dependencies."""

    def test_project_not_found_nonexistent(self, tmp_path):
        """PROJECT_NOT_FOUND when project_dir does not exist (§7.1)."""
        scan = _import_scan_dependencies()
        (
            CONSTRAINT_PARSE_ERROR, INVALID_PARAMETER, NO_DEPENDENCIES,
            OPAM_TIMEOUT, PACKAGE_NOT_FOUND, PROJECT_NOT_FOUND,
            TOOL_NOT_FOUND, CompatError,
        ) = _import_errors()
        with pytest.raises(CompatError) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                scan(tmp_path / "nonexistent", [])
            )
        assert exc_info.value.code == PROJECT_NOT_FOUND

    def test_project_not_found_is_file(self, tmp_path):
        """PROJECT_NOT_FOUND when project_dir is a file, not a directory (§7.1)."""
        scan = _import_scan_dependencies()
        (
            CONSTRAINT_PARSE_ERROR, INVALID_PARAMETER, NO_DEPENDENCIES,
            OPAM_TIMEOUT, PACKAGE_NOT_FOUND, PROJECT_NOT_FOUND,
            TOOL_NOT_FOUND, CompatError,
        ) = _import_errors()
        f = tmp_path / "not_a_dir"
        f.write_text("content")
        with pytest.raises(CompatError) as exc_info:
            asyncio.get_event_loop().run_until_complete(scan(f, []))
        assert exc_info.value.code == PROJECT_NOT_FOUND

    def test_no_dependencies_empty_project(self, tmp_path):
        """NO_DEPENDENCIES when no dependency declarations found (§7.1)."""
        scan = _import_scan_dependencies()
        (
            CONSTRAINT_PARSE_ERROR, INVALID_PARAMETER, NO_DEPENDENCIES,
            OPAM_TIMEOUT, PACKAGE_NOT_FOUND, PROJECT_NOT_FOUND,
            TOOL_NOT_FOUND, CompatError,
        ) = _import_errors()
        with pytest.raises(CompatError) as exc_info:
            asyncio.get_event_loop().run_until_complete(scan(tmp_path, []))
        assert exc_info.value.code == NO_DEPENDENCIES

    def test_invalid_parameter_empty_hypothetical(self, tmp_path):
        """INVALID_PARAMETER when hypothetical_additions contains empty string (§7.1)."""
        scan = _import_scan_dependencies()
        (
            CONSTRAINT_PARSE_ERROR, INVALID_PARAMETER, NO_DEPENDENCIES,
            OPAM_TIMEOUT, PACKAGE_NOT_FOUND, PROJECT_NOT_FOUND,
            TOOL_NOT_FOUND, CompatError,
        ) = _import_errors()
        (tmp_path / "mylib.opam").write_text('opam-version: "2.0"\ndepends: ["coq"]\n')
        with pytest.raises(CompatError) as exc_info:
            asyncio.get_event_loop().run_until_complete(scan(tmp_path, [""]))
        assert exc_info.value.code == INVALID_PARAMETER

    def test_all_unknown_packages_returns_no_dependencies(self, tmp_path):
        """All unknown packages → NO_DEPENDENCIES with names in unknown_packages (§7.5)."""
        scan = _import_scan_dependencies()
        (
            CONSTRAINT_PARSE_ERROR, INVALID_PARAMETER, NO_DEPENDENCIES,
            OPAM_TIMEOUT, PACKAGE_NOT_FOUND, PROJECT_NOT_FOUND,
            TOOL_NOT_FOUND, CompatError,
        ) = _import_errors()
        # Provide an opam file with an unknown package only
        opam_content = 'opam-version: "2.0"\ndepends: ["coq-fake-nonexistent"]\n'
        (tmp_path / "mylib.opam").write_text(opam_content)
        with patch("Poule.compat.scanner._opam_package_exists", return_value=False):
            with pytest.raises(CompatError) as exc_info:
                asyncio.get_event_loop().run_until_complete(scan(tmp_path, []))
            assert exc_info.value.code == NO_DEPENDENCIES


# ===========================================================================
# 4. Opam Metadata Resolution — spec §4.2
# ===========================================================================

@patch("Poule.compat.resolver.shutil.which", return_value="/usr/bin/opam")
class TestOpamMetadataResolution:
    """§4.2: resolve_metadata(dependency_set)."""

    def test_returns_resolved_constraint_tree(self, _mock_which):
        """resolve_metadata returns a ResolvedConstraintTree (§4.2)."""
        resolve = _import_resolve_metadata()
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()
        ds = _make_dependency_set(
            dependencies=[_make_declared_dependency("coq-mathcomp-ssreflect")],
        )
        with patch("Poule.compat.resolver._opam_show") as mock_show:
            mock_show.return_value = {
                "depends": '"coq" {>= "8.18" & < "8.20~"}',
                "version": "2.2.0",
                "all-versions": "2.2.0  2.1.0  2.0.0",
            }
            result = asyncio.get_event_loop().run_until_complete(resolve(ds))
        assert isinstance(result, ResolvedConstraintTree)
        assert "coq-mathcomp-ssreflect" in result.root_dependencies

    def test_transitive_dependencies_expanded(self, _mock_which):
        """Transitive dependencies are included in the tree (§4.2 example 1)."""
        resolve = _import_resolve_metadata()
        ds = _make_dependency_set(
            dependencies=[_make_declared_dependency("coq-mathcomp-ssreflect")],
        )

        def fake_show(pkg):
            if pkg == "coq-mathcomp-ssreflect":
                return {
                    "depends": '"coq" {>= "8.18" & < "8.20~"}',
                    "version": "2.2.0",
                    "all-versions": "2.2.0  2.1.0  2.0.0",
                }
            elif pkg == "coq":
                return {
                    "depends": '"ocaml" {>= "4.14"}',
                    "version": "8.19.0",
                    "all-versions": "8.19.0  8.18.0  8.17.0",
                }
            elif pkg == "ocaml":
                return {
                    "depends": "",
                    "version": "4.14.1",
                    "all-versions": "4.14.1  4.14.0",
                }
            return {"depends": "", "version": "1.0", "all-versions": "1.0"}

        with patch("Poule.compat.resolver._opam_show", side_effect=fake_show):
            result = asyncio.get_event_loop().run_until_complete(resolve(ds))
        assert "coq" in result.nodes

    def test_circular_dependency_detected(self, _mock_which):
        """Circular opam dependency: cycle noted, expansion stops (§4.2 example 2)."""
        resolve = _import_resolve_metadata()
        ds = _make_dependency_set(
            dependencies=[_make_declared_dependency("pkg-a")],
        )
        call_count = {"pkg-a": 0, "pkg-b": 0, "pkg-c": 0}

        def fake_show(pkg):
            call_count[pkg] = call_count.get(pkg, 0) + 1
            if pkg == "pkg-a":
                return {"depends": '"pkg-b"', "version": "1.0", "all-versions": "1.0"}
            elif pkg == "pkg-b":
                return {"depends": '"pkg-c"', "version": "1.0", "all-versions": "1.0"}
            elif pkg == "pkg-c":
                return {"depends": '"pkg-a"', "version": "1.0", "all-versions": "1.0"}
            return {"depends": "", "version": "1.0", "all-versions": "1.0"}

        with patch("Poule.compat.resolver._opam_show", side_effect=fake_show):
            result = asyncio.get_event_loop().run_until_complete(resolve(ds))
        # Each package queried at most once (cycle detection stops recursion)
        for pkg, count in call_count.items():
            assert count <= 1, f"{pkg} queried {count} times"

    def test_opam_timeout_recorded(self, _mock_which):
        """opam show timeout: recorded, remaining packages resolved (§4.2 example 3, §7.2)."""
        resolve = _import_resolve_metadata()
        ds = _make_dependency_set(
            dependencies=[
                _make_declared_dependency("pkg-ok"),
                _make_declared_dependency("pkg-timeout"),
            ],
        )

        async def fake_show(pkg):
            if pkg == "pkg-timeout":
                raise asyncio.TimeoutError()
            return {"depends": "", "version": "1.0", "all-versions": "1.0"}

        with patch("Poule.compat.resolver._opam_show", side_effect=fake_show):
            result = asyncio.get_event_loop().run_until_complete(resolve(ds))
        # pkg-ok should be in the tree
        assert "pkg-ok" in result.nodes

    def test_cache_prevents_duplicate_queries(self, _mock_which):
        """Each package queried at most once — results cached within the run (§4.2)."""
        resolve = _import_resolve_metadata()
        ds = _make_dependency_set(
            dependencies=[
                _make_declared_dependency("pkg-a"),
                _make_declared_dependency("pkg-b"),
            ],
        )
        query_counts = {}

        def fake_show(pkg):
            query_counts[pkg] = query_counts.get(pkg, 0) + 1
            if pkg == "pkg-a":
                return {"depends": '"coq"', "version": "1.0", "all-versions": "1.0"}
            elif pkg == "pkg-b":
                return {"depends": '"coq"', "version": "1.0", "all-versions": "1.0"}
            elif pkg == "coq":
                return {"depends": "", "version": "8.19.0", "all-versions": "8.19.0"}
            return {"depends": "", "version": "1.0", "all-versions": "1.0"}

        with patch("Poule.compat.resolver._opam_show", side_effect=fake_show):
            asyncio.get_event_loop().run_until_complete(resolve(ds))
        assert query_counts.get("coq", 0) == 1, "coq should be queried exactly once"

    def test_only_read_only_opam_commands(self, _mock_which):
        """MAINTAINS: Only opam show is invoked, never install/upgrade (§4.2, §6)."""
        resolve = _import_resolve_metadata()
        ds = _make_dependency_set(
            dependencies=[_make_declared_dependency("coq")],
        )
        invoked_commands = []

        async def capture_subprocess(*args, **kwargs):
            invoked_commands.append(args)
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (
                b'depends: ""\nversion: "8.19.0"\nall-versions: "8.19.0"',
                b"",
            )
            mock_proc.returncode = 0
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=capture_subprocess):
            asyncio.get_event_loop().run_until_complete(resolve(ds))
        for cmd in invoked_commands:
            assert "install" not in cmd
            assert "upgrade" not in cmd


# ===========================================================================
# 5. Constraint Parsing — spec §4.3
# ===========================================================================

class TestConstraintParsing:
    """§4.3: parse_constraint(constraint_expression)."""

    def test_simple_range_constraint(self):
        """Given >= '8.18' & < '8.20~', returns one interval (§4.3 example 1)."""
        parse = _import_parse_constraint()
        result = parse('>= "8.18" & < "8.20~"')
        assert len(result.intervals) == 1
        interval = result.intervals[0]
        assert interval.lower is not None
        assert interval.lower.version == "8.18"
        assert interval.lower.inclusive is True
        assert interval.upper is not None
        assert interval.upper.version == "8.20~"
        assert interval.upper.inclusive is False

    def test_disjunctive_constraint(self):
        """Given disjunctive constraint, returns two intervals (§4.3 example 2)."""
        parse = _import_parse_constraint()
        result = parse('>= "8.16" & < "8.18" | >= "8.19" & < "8.20"')
        assert len(result.intervals) == 2

    def test_malformed_constraint_returns_error(self):
        """Given malformed constraint, returns CONSTRAINT_PARSE_ERROR (§4.3 example 3)."""
        parse = _import_parse_constraint()
        (
            CONSTRAINT_PARSE_ERROR, INVALID_PARAMETER, NO_DEPENDENCIES,
            OPAM_TIMEOUT, PACKAGE_NOT_FOUND, PROJECT_NOT_FOUND,
            TOOL_NOT_FOUND, CompatError,
        ) = _import_errors()
        with pytest.raises(CompatError) as exc_info:
            parse('>= "8.18" &&& < "8.20"')
        assert exc_info.value.code == CONSTRAINT_PARSE_ERROR
        # Raw text preserved
        assert '>= "8.18" &&& < "8.20"' in str(exc_info.value)

    def test_equality_constraint(self):
        """Equality constraint = '8.18' produces single-point interval."""
        parse = _import_parse_constraint()
        result = parse('= "8.18"')
        assert len(result.intervals) == 1
        interval = result.intervals[0]
        assert interval.lower is not None
        assert interval.lower.version == "8.18"
        assert interval.lower.inclusive is True
        assert interval.upper is not None
        assert interval.upper.version == "8.18"
        assert interval.upper.inclusive is True

    def test_not_equal_constraint(self):
        """Inequality != '8.18' produces two intervals (below and above)."""
        parse = _import_parse_constraint()
        result = parse('!= "8.18"')
        assert len(result.intervals) == 2

    def test_single_lower_bound(self):
        """>= constraint produces interval with no upper bound."""
        parse = _import_parse_constraint()
        result = parse('>= "8.18"')
        assert len(result.intervals) == 1
        interval = result.intervals[0]
        assert interval.lower is not None
        assert interval.lower.version == "8.18"
        assert interval.lower.inclusive is True
        assert interval.upper is None

    def test_single_upper_bound(self):
        """< constraint produces interval with no lower bound."""
        parse = _import_parse_constraint()
        result = parse('< "8.18"')
        assert len(result.intervals) == 1
        interval = result.intervals[0]
        assert interval.lower is None
        assert interval.upper is not None
        assert interval.upper.version == "8.18"
        assert interval.upper.inclusive is False

    def test_deterministic_parsing(self):
        """MAINTAINS: Same expression always produces same result (§4.3)."""
        parse = _import_parse_constraint()
        expr = '>= "8.18" & < "8.20~"'
        result1 = parse(expr)
        result2 = parse(expr)
        assert result1 == result2


# ===========================================================================
# 6. Version Comparison — spec §4.3
# ===========================================================================

class TestVersionComparison:
    """§4.3: opam version ordering rules."""

    def test_numeric_comparison(self):
        """Numeric segments compared numerically: 8 < 18 (§4.3)."""
        cmp = _import_compare_versions()
        assert cmp("8", "18") < 0

    def test_string_segments_lexicographic(self):
        """String segments compared lexicographically (§4.3)."""
        cmp = _import_compare_versions()
        assert cmp("alpha", "beta") < 0

    def test_tilde_sorts_before(self):
        """Tilde prefix: 8.18~ < 8.18 (§4.3)."""
        cmp = _import_compare_versions()
        assert cmp("8.18~", "8.18") < 0

    def test_build_suffix_sorts_after(self):
        """Build suffix: 8.19 < 8.19+flambda (§4.3)."""
        cmp = _import_compare_versions()
        assert cmp("8.19", "8.19+flambda") < 0

    def test_equal_versions(self):
        """Equal versions return 0."""
        cmp = _import_compare_versions()
        assert cmp("8.18.0", "8.18.0") == 0

    def test_multi_segment_comparison(self):
        """Multi-segment: 8.18.0 < 8.19.0."""
        cmp = _import_compare_versions()
        assert cmp("8.18.0", "8.19.0") < 0

    def test_tilde_before_empty(self):
        """Tilde sorts before end-of-segment: 8.18~ < 8.18 (confirmed twice)."""
        cmp = _import_compare_versions()
        assert cmp("8.18~beta", "8.18") < 0


# ===========================================================================
# 7. Interval Arithmetic — spec §10
# ===========================================================================

class TestIntervalArithmetic:
    """§10: intersect(a, b) and is_empty(vc)."""

    def test_overlapping_intervals_intersect(self):
        """Overlapping intervals produce a non-empty intersection."""
        intersect = _import_intersect()
        is_empty = _import_is_empty()
        # [8.16, 8.20) and [8.18, 8.22) → [8.18, 8.20)
        a = _make_version_constraint([
            _make_version_interval(
                lower=_make_version_bound("8.16", True),
                upper=_make_version_bound("8.20", False),
            ),
        ])
        b = _make_version_constraint([
            _make_version_interval(
                lower=_make_version_bound("8.18", True),
                upper=_make_version_bound("8.22", False),
            ),
        ])
        result = intersect(a, b)
        assert not is_empty(result)

    def test_disjoint_intervals_empty(self):
        """Disjoint intervals produce an empty intersection."""
        intersect = _import_intersect()
        is_empty = _import_is_empty()
        # [8.16, 8.18) and [8.19, 8.20)
        a = _make_version_constraint([
            _make_version_interval(
                lower=_make_version_bound("8.16", True),
                upper=_make_version_bound("8.18", False),
            ),
        ])
        b = _make_version_constraint([
            _make_version_interval(
                lower=_make_version_bound("8.19", True),
                upper=_make_version_bound("8.20", False),
            ),
        ])
        result = intersect(a, b)
        assert is_empty(result)

    def test_touching_exclusive_bounds_empty(self):
        """[low, 8.18) intersect [8.18, high) is empty when both bounds exclusive."""
        intersect = _import_intersect()
        is_empty = _import_is_empty()
        a = _make_version_constraint([
            _make_version_interval(
                lower=None,
                upper=_make_version_bound("8.18", False),
            ),
        ])
        b = _make_version_constraint([
            _make_version_interval(
                lower=_make_version_bound("8.18", False),
                upper=None,
            ),
        ])
        result = intersect(a, b)
        assert is_empty(result)

    def test_touching_inclusive_bound_nonempty(self):
        """[low, 8.18] intersect [8.18, high) is non-empty (touching at 8.18)."""
        intersect = _import_intersect()
        is_empty = _import_is_empty()
        a = _make_version_constraint([
            _make_version_interval(
                lower=None,
                upper=_make_version_bound("8.18", True),
            ),
        ])
        b = _make_version_constraint([
            _make_version_interval(
                lower=_make_version_bound("8.18", True),
                upper=None,
            ),
        ])
        result = intersect(a, b)
        assert not is_empty(result)

    def test_unbounded_intersect(self):
        """Unbounded constraint intersect with bounded yields bounded."""
        intersect = _import_intersect()
        is_empty = _import_is_empty()
        unbounded = _make_version_constraint([
            _make_version_interval(lower=None, upper=None),
        ])
        bounded = _make_version_constraint([
            _make_version_interval(
                lower=_make_version_bound("8.18", True),
                upper=_make_version_bound("8.20", False),
            ),
        ])
        result = intersect(unbounded, bounded)
        assert not is_empty(result)

    def test_is_empty_on_empty_intervals(self):
        """is_empty returns True for VersionConstraint with no intervals."""
        is_empty = _import_is_empty()
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()
        vc = VersionConstraint(intervals=[])
        assert is_empty(vc)


# ===========================================================================
# 8. Conflict Detection — spec §4.4
# ===========================================================================

class TestConflictDetection:
    """§4.4: detect_conflicts(constraint_tree)."""

    def test_incompatible_coq_constraints(self):
        """Given conflicting coq constraints, returns ConflictSet (§4.4 example 1)."""
        detect = _import_detect_conflicts()
        parse = _import_parse_constraint()
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()

        tree = _two_dep_tree(
            dep_a_name="coq-mathcomp-ssreflect",
            dep_a_coq_raw='>= "8.18"',
            dep_a_coq_constraint=parse('>= "8.18"'),
            dep_b_name="coq-iris",
            dep_b_coq_raw='< "8.18"',
            dep_b_coq_constraint=parse('< "8.18"'),
            coq_versions=["8.19.0", "8.18.0", "8.17.0", "8.16.0"],
        )
        result = detect(tree)
        assert isinstance(result, ConflictSet)
        assert result.verdict == "incompatible"
        assert len(result.conflicts) >= 1
        coq_conflict = next(c for c in result.conflicts if c.resource == "coq")
        assert len(coq_conflict.minimal_constraint_set) >= 2
        # detect_conflicts returns null explanation (§5 lifecycle)
        assert coq_conflict.explanation is None
        assert coq_conflict.resolutions == []

    def test_compatible_dependencies(self):
        """Given compatible constraints, returns CompatibleSet (§4.4 example 2)."""
        detect = _import_detect_conflicts()
        parse = _import_parse_constraint()
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()

        tree = _two_dep_tree(
            dep_a_name="coq-mathcomp-ssreflect",
            dep_a_coq_raw='>= "8.18"',
            dep_a_coq_constraint=parse('>= "8.18"'),
            dep_b_name="coq-equations",
            dep_b_coq_raw='>= "8.18" & < "8.20~"',
            dep_b_coq_constraint=parse('>= "8.18" & < "8.20~"'),
            coq_versions=["8.19.0", "8.18.0", "8.17.0"],
        )
        result = detect(tree)
        assert isinstance(result, CompatibleSet)
        assert result.verdict == "compatible"
        assert "coq" in result.version_map
        # Newest compatible version selected
        assert result.version_map["coq"] in ("8.19.0", "8.18.0")
        assert result.coq_version_range is not None

    def test_target_coq_version_pin(self):
        """Given a target Coq version, pin and check constraints (§4.4 example 3)."""
        detect = _import_detect_conflicts()
        parse = _import_parse_constraint()
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()

        tree = _two_dep_tree(
            dep_a_name="coq-mathcomp-ssreflect",
            dep_a_coq_raw='>= "8.18"',
            dep_a_coq_constraint=parse('>= "8.18"'),
            dep_b_name="coq-equations",
            dep_b_coq_raw='>= "8.17" & < "8.20~"',
            dep_b_coq_constraint=parse('>= "8.17" & < "8.20~"'),
            coq_versions=["8.19.0", "8.18.0", "8.17.0"],
        )
        # Pin to 8.17 — conflicts with coq-mathcomp-ssreflect requiring >= 8.18
        result = detect(tree, target_coq_version="8.17")
        assert isinstance(result, ConflictSet)
        assert result.verdict == "incompatible"

    def test_single_dependency_no_conflict(self):
        """Single dependency with no shared resources → compatible (§7.5)."""
        detect = _import_detect_conflicts()
        parse = _import_parse_constraint()
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()

        nodes = {
            "coq-mathcomp-ssreflect": _make_package_node(
                "coq-mathcomp-ssreflect", ["2.2.0", "2.0.0"],
            ),
            "coq": _make_package_node("coq", ["8.19.0", "8.18.0"]),
        }
        edges = [
            _make_constraint_edge(
                "coq-mathcomp-ssreflect", "coq",
                parse('>= "8.18"'), '>= "8.18"',
            ),
        ]
        tree = _make_constraint_tree(
            root_dependencies=["coq-mathcomp-ssreflect"],
            nodes=nodes,
            edges=edges,
        )
        result = detect(tree)
        assert isinstance(result, CompatibleSet)

    def test_no_shared_resources_compatible(self):
        """No shared resources in the tree → compatible (§7.5)."""
        detect = _import_detect_conflicts()
        parse = _import_parse_constraint()
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()

        # Two independent packages with no shared transitive deps
        nodes = {
            "pkg-a": _make_package_node("pkg-a", ["1.0"]),
            "pkg-b": _make_package_node("pkg-b", ["1.0"]),
            "dep-a": _make_package_node("dep-a", ["1.0"]),
            "dep-b": _make_package_node("dep-b", ["1.0"]),
        }
        edges = [
            _make_constraint_edge(
                "pkg-a", "dep-a",
                _make_version_constraint([_make_version_interval()]),
                "",
            ),
            _make_constraint_edge(
                "pkg-b", "dep-b",
                _make_version_constraint([_make_version_interval()]),
                "",
            ),
        ]
        tree = _make_constraint_tree(
            root_dependencies=["pkg-a", "pkg-b"],
            nodes=nodes,
            edges=edges,
        )
        result = detect(tree)
        assert isinstance(result, CompatibleSet)

    def test_ocaml_version_conflict_treated_same(self):
        """Conflict on 'ocaml' treated identically to 'coq' (§7.5)."""
        detect = _import_detect_conflicts()
        parse = _import_parse_constraint()
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()

        nodes = {
            "pkg-a": _make_package_node("pkg-a", ["1.0"]),
            "pkg-b": _make_package_node("pkg-b", ["1.0"]),
            "ocaml": _make_package_node("ocaml", ["4.14.1", "4.14.0", "4.13.0"]),
        }
        edges = [
            _make_constraint_edge(
                "pkg-a", "ocaml",
                parse('>= "4.14"'), '>= "4.14"',
            ),
            _make_constraint_edge(
                "pkg-b", "ocaml",
                parse('< "4.14"'), '< "4.14"',
            ),
        ]
        tree = _make_constraint_tree(
            root_dependencies=["pkg-a", "pkg-b"],
            nodes=nodes,
            edges=edges,
        )
        result = detect(tree)
        assert isinstance(result, ConflictSet)
        assert result.conflicts[0].resource == "ocaml"

    def test_constraint_tree_not_modified(self):
        """MAINTAINS: Constraint tree is not modified (§4.4)."""
        detect = _import_detect_conflicts()
        parse = _import_parse_constraint()
        tree = _two_dep_tree(
            dep_a_name="coq-mathcomp-ssreflect",
            dep_a_coq_raw='>= "8.18"',
            dep_a_coq_constraint=parse('>= "8.18"'),
            dep_b_name="coq-equations",
            dep_b_coq_raw='>= "8.17"',
            dep_b_coq_constraint=parse('>= "8.17"'),
            coq_versions=["8.19.0", "8.18.0"],
        )
        edges_before = list(tree.edges)
        nodes_before = dict(tree.nodes)
        detect(tree)
        assert list(tree.edges) == edges_before
        assert dict(tree.nodes) == nodes_before

    def test_newest_compatible_version_selected(self):
        """CompatibleSet.version_map contains newest compatible version (§4.4)."""
        detect = _import_detect_conflicts()
        parse = _import_parse_constraint()
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()

        tree = _two_dep_tree(
            dep_a_name="coq-mathcomp-ssreflect",
            dep_a_coq_raw='>= "8.18"',
            dep_a_coq_constraint=parse('>= "8.18"'),
            dep_b_name="coq-equations",
            dep_b_coq_raw='>= "8.18" & < "8.20~"',
            dep_b_coq_constraint=parse('>= "8.18" & < "8.20~"'),
            coq_versions=["8.19.0", "8.18.0", "8.17.0"],
        )
        result = detect(tree)
        assert isinstance(result, CompatibleSet)
        # 8.19.0 is the newest version satisfying both constraints
        assert result.version_map["coq"] == "8.19.0"

    def test_hypothetical_already_declared_no_error(self):
        """Hypothetical addition already declared: both entries included (§7.5)."""
        detect = _import_detect_conflicts()
        parse = _import_parse_constraint()
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()

        # coq-equations appears both as file-sourced and hypothetical
        # — should not cause a deduplication error, just extra edges
        nodes = {
            "coq-equations": _make_package_node("coq-equations", ["1.3.1", "1.3.0"]),
            "coq": _make_package_node("coq", ["8.19.0", "8.18.0"]),
        }
        edges = [
            _make_constraint_edge(
                "coq-equations", "coq",
                parse('>= "8.18"'), '>= "8.18"',
            ),
        ]
        tree = _make_constraint_tree(
            root_dependencies=["coq-equations"],
            nodes=nodes,
            edges=edges,
        )
        # Should not raise
        result = detect(tree)
        assert isinstance(result, (CompatibleSet, ConflictSet))

    def test_multiple_conflicts_same_resource(self):
        """Multiple conflicts on the same resource → single resource entry with combined set (§7.5)."""
        detect = _import_detect_conflicts()
        parse = _import_parse_constraint()
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()

        # Three packages all constraining coq incompatibly
        nodes = {
            "pkg-a": _make_package_node("pkg-a", ["1.0"]),
            "pkg-b": _make_package_node("pkg-b", ["1.0"]),
            "pkg-c": _make_package_node("pkg-c", ["1.0"]),
            "coq": _make_package_node("coq", ["8.19.0", "8.18.0", "8.17.0"]),
        }
        edges = [
            _make_constraint_edge("pkg-a", "coq", parse('= "8.17"'), '= "8.17"'),
            _make_constraint_edge("pkg-b", "coq", parse('= "8.18"'), '= "8.18"'),
            _make_constraint_edge("pkg-c", "coq", parse('= "8.19"'), '= "8.19"'),
        ]
        tree = _make_constraint_tree(
            root_dependencies=["pkg-a", "pkg-b", "pkg-c"],
            nodes=nodes,
            edges=edges,
        )
        result = detect(tree)
        assert isinstance(result, ConflictSet)
        coq_conflicts = [c for c in result.conflicts if c.resource == "coq"]
        # Single resource entry, not three separate entries
        assert len(coq_conflicts) == 1


# ===========================================================================
# 9. Explanation Building — spec §4.5
# ===========================================================================

class TestExplanationBuilding:
    """§4.5: build_explanation(conflict)."""

    def test_direct_dependency_explanation(self):
        """Direct deps: names both packages and the resource (§4.5 example 1)."""
        build_expl = _import_build_explanation()
        parse = _import_parse_constraint()

        edges = [
            _make_constraint_edge(
                "coq-mathcomp-ssreflect", "coq",
                parse('>= "8.18"'), '>= "8.18"',
            ),
            _make_constraint_edge(
                "coq-iris", "coq",
                parse('< "8.18"'), '< "8.18"',
            ),
        ]
        # Conflict from detect_conflicts has explanation=None (§5 lifecycle)
        conflict = _make_conflict("coq", edges)
        result = build_expl(conflict)
        assert "coq-mathcomp-ssreflect" in result.summary or "coq-mathcomp" in result.summary
        assert "coq-iris" in result.summary
        assert len(result.constraint_chains) >= 2

    def test_transitive_dependency_chain(self):
        """Transitive deps: chain includes intermediates (§4.5 example 2)."""
        build_expl = _import_build_explanation()
        parse = _import_parse_constraint()

        edges = [
            _make_constraint_edge(
                "coq-mathcomp-ssreflect", "coq",
                parse('>= "8.18"'), '>= "8.18"',
            ),
            # Transitive: coq-my-lib → coq-util → coq < 8.17
            _make_constraint_edge(
                "coq-util", "coq",
                parse('< "8.17"'), '< "8.17"',
            ),
        ]
        conflict = _make_conflict("coq", edges)
        result = build_expl(conflict)
        assert len(result.constraint_chains) >= 2
        # At least one chain should trace a transitive path
        all_chains_flat = [item for chain in result.constraint_chains for item in chain]
        assert any("coq-util" in item for item in all_chains_flat)

    def test_explanation_deterministic(self):
        """MAINTAINS: Same conflict always produces same explanation (§4.5)."""
        build_expl = _import_build_explanation()
        parse = _import_parse_constraint()

        edges = [
            _make_constraint_edge(
                "coq-mathcomp-ssreflect", "coq",
                parse('>= "8.18"'), '>= "8.18"',
            ),
            _make_constraint_edge(
                "coq-iris", "coq",
                parse('< "8.18"'), '< "8.18"',
            ),
        ]
        conflict = _make_conflict("coq", edges)
        result1 = build_expl(conflict)
        result2 = build_expl(conflict)
        assert result1 == result2

    def test_explanation_summary_nonempty(self):
        """ExplanationText.summary is non-empty (§5)."""
        build_expl = _import_build_explanation()
        parse = _import_parse_constraint()

        edges = [
            _make_constraint_edge("a", "coq", parse('>= "8.18"'), '>= "8.18"'),
            _make_constraint_edge("b", "coq", parse('< "8.18"'), '< "8.18"'),
        ]
        conflict = _make_conflict("coq", edges)
        result = build_expl(conflict)
        assert len(result.summary) > 0


# ===========================================================================
# 10. Resolution Suggestion — spec §4.6
# ===========================================================================

class TestResolutionSuggestion:
    """§4.6: suggest_resolutions(conflict, constraint_tree)."""

    def test_upgrade_resolution(self):
        """UPGRADE when newer version relaxes constraint (§4.6 example 1)."""
        suggest = _import_suggest_resolutions()
        parse = _import_parse_constraint()

        edges = [
            _make_constraint_edge(
                "coq-lib-a", "coq", parse('>= "8.18"'), '>= "8.18"',
            ),
            _make_constraint_edge(
                "coq-lib-b", "coq", parse('< "8.18"'), '< "8.18"',
            ),
        ]
        conflict = _make_conflict("coq", edges)

        # Build a tree where coq-lib-b has a newer version
        nodes = {
            "coq-lib-a": _make_package_node("coq-lib-a", ["1.0"]),
            "coq-lib-b": _make_package_node("coq-lib-b", ["2.0", "1.0"]),
            "coq": _make_package_node("coq", ["8.19.0", "8.18.0", "8.17.0"]),
        }
        tree_edges = list(edges)
        tree = _make_constraint_tree(
            root_dependencies=["coq-lib-a", "coq-lib-b"],
            nodes=nodes,
            edges=tree_edges,
        )

        # Mock opam to show newer version relaxes constraint
        with patch("Poule.compat.resolver._opam_show") as mock_show:
            mock_show.return_value = {
                "depends": '"coq" {>= "8.18"}',
                "version": "2.0",
                "all-versions": "2.0  1.0",
            }
            result = asyncio.get_event_loop().run_until_complete(
                suggest(conflict, tree)
            )
        upgrades = [r for r in result if r.strategy == "UPGRADE"]
        assert len(upgrades) >= 1
        assert upgrades[0].target_package == "coq-lib-b"
        assert upgrades[0].target_version is not None
        assert len(upgrades[0].trade_off) > 0

    def test_no_resolution_emitted(self):
        """NO_RESOLUTION when no version resolves the conflict (§4.6 example 2)."""
        suggest = _import_suggest_resolutions()
        parse = _import_parse_constraint()

        edges = [
            _make_constraint_edge("a", "coq", parse('>= "8.18"'), '>= "8.18"'),
            _make_constraint_edge("b", "coq", parse('< "8.18"'), '< "8.18"'),
        ]
        conflict = _make_conflict("coq", edges)

        nodes = {
            "a": _make_package_node("a", ["1.0"]),
            "b": _make_package_node("b", ["1.0"]),
            "coq": _make_package_node("coq", ["8.19.0", "8.18.0", "8.17.0"]),
        }
        tree = _make_constraint_tree(
            root_dependencies=["a", "b"],
            nodes=nodes,
            edges=list(edges),
        )

        # Mock: no newer versions available for any package
        with patch("Poule.compat.resolver._opam_show") as mock_show:
            mock_show.return_value = {
                "depends": "",
                "version": "1.0",
                "all-versions": "1.0",
            }
            result = asyncio.get_event_loop().run_until_complete(
                suggest(conflict, tree)
            )
        no_res = [r for r in result if r.strategy == "NO_RESOLUTION"]
        assert len(no_res) == 1
        assert len(no_res[0].trade_off) > 0

    def test_resolution_ordering(self):
        """Resolutions sorted: UPGRADE, DOWNGRADE, ALTERNATIVE, NO_RESOLUTION (§4.6 example 3)."""
        suggest = _import_suggest_resolutions()
        parse = _import_parse_constraint()

        edges = [
            _make_constraint_edge("a", "coq", parse('>= "8.18"'), '>= "8.18"'),
            _make_constraint_edge("b", "coq", parse('< "8.18"'), '< "8.18"'),
        ]
        conflict = _make_conflict("coq", edges)

        nodes = {
            "a": _make_package_node("a", ["2.0", "1.0"]),
            "b": _make_package_node("b", ["2.0", "1.0"]),
            "coq": _make_package_node("coq", ["8.19.0", "8.18.0", "8.17.0"]),
        }
        tree = _make_constraint_tree(
            root_dependencies=["a", "b"],
            nodes=nodes,
            edges=list(edges),
        )

        with patch("Poule.compat.resolver._opam_show") as mock_show:
            # Return different constraints for different versions
            def show_side_effect(pkg):
                return {
                    "depends": '"coq" {>= "8.18"}',
                    "version": "2.0",
                    "all-versions": "2.0  1.0",
                }
            mock_show.side_effect = show_side_effect
            result = asyncio.get_event_loop().run_until_complete(
                suggest(conflict, tree)
            )

        if len(result) >= 2:
            strategy_order = {"UPGRADE": 0, "DOWNGRADE": 1, "ALTERNATIVE": 2, "NO_RESOLUTION": 3}
            indices = [strategy_order.get(r.strategy, 99) for r in result]
            assert indices == sorted(indices), f"Strategies not in order: {[r.strategy for r in result]}"

    def test_resolution_read_only(self):
        """MAINTAINS: No project files or opam state modified (§4.6)."""
        suggest = _import_suggest_resolutions()
        parse = _import_parse_constraint()

        edges = [
            _make_constraint_edge("a", "coq", parse('>= "8.18"'), '>= "8.18"'),
            _make_constraint_edge("b", "coq", parse('< "8.18"'), '< "8.18"'),
        ]
        conflict = _make_conflict("coq", edges)

        nodes = {
            "a": _make_package_node("a", ["1.0"]),
            "b": _make_package_node("b", ["1.0"]),
            "coq": _make_package_node("coq", ["8.19.0"]),
        }
        tree = _make_constraint_tree(
            root_dependencies=["a", "b"],
            nodes=nodes,
            edges=list(edges),
        )

        invoked_commands = []

        async def capture_subprocess(*args, **kwargs):
            invoked_commands.append(args)
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (b"", b"")
            mock_proc.returncode = 0
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=capture_subprocess):
            asyncio.get_event_loop().run_until_complete(suggest(conflict, tree))
        for cmd in invoked_commands:
            assert "install" not in cmd
            assert "upgrade" not in cmd
            assert "remove" not in cmd

    def test_upgrade_target_version_required(self):
        """UPGRADE resolution has non-null target_version (§5)."""
        r = _make_resolution(
            strategy="UPGRADE",
            target_package="coq-lib-b",
            target_version="2.0",
            trade_off="May introduce API changes.",
        )
        assert r.target_version is not None

    def test_no_resolution_target_version_null(self):
        """NO_RESOLUTION has null target_version (§5)."""
        r = _make_resolution(
            strategy="NO_RESOLUTION",
            target_package="coq-lib",
            target_version=None,
            trade_off="No compatible combination exists.",
        )
        assert r.target_version is None

    def test_alternative_has_alternative_package(self):
        """ALTERNATIVE resolution has non-null alternative_package (§5)."""
        r = _make_resolution(
            strategy="ALTERNATIVE",
            target_package="coq-lib-b",
            target_version=None,
            alternative_package="coq-lib-b-alt",
            trade_off="Replaces coq-lib-b with coq-lib-b-alt.",
        )
        assert r.alternative_package is not None


# ===========================================================================
# 11. End-to-End Pipeline Examples — spec §9
# ===========================================================================

class TestPipelineExamples:
    """§9: Full pipeline examples from the specification."""

    def test_compatible_example(self):
        """§9 example 1: Compatible dependencies produce CompatibleSet."""
        detect = _import_detect_conflicts()
        parse = _import_parse_constraint()
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()

        nodes = {
            "coq-mathcomp-ssreflect": _make_package_node(
                "coq-mathcomp-ssreflect", ["2.2.0", "2.0.0"],
            ),
            "coq-equations": _make_package_node(
                "coq-equations", ["1.3.1", "1.3.0"],
            ),
            "coq": _make_package_node(
                "coq", ["8.19.0", "8.18.0", "8.17.0"],
            ),
        }
        edges = [
            _make_constraint_edge(
                "coq-mathcomp-ssreflect", "coq",
                parse('>= "8.18"'), '>= "8.18"',
            ),
            _make_constraint_edge(
                "coq-equations", "coq",
                parse('>= "8.18" & < "8.20~"'), '>= "8.18" & < "8.20~"',
            ),
        ]
        tree = _make_constraint_tree(
            root_dependencies=["coq-mathcomp-ssreflect", "coq-equations"],
            nodes=nodes,
            edges=edges,
        )
        result = detect(tree)
        assert isinstance(result, CompatibleSet)
        assert result.verdict == "compatible"
        assert result.version_map["coq"] == "8.19.0"

    def test_incompatible_example(self):
        """§9 example 2: Incompatible dependencies produce ConflictSet."""
        detect = _import_detect_conflicts()
        parse = _import_parse_constraint()
        (
            CompatibleSet, Conflict, ConflictSet, ConstraintEdge,
            DeclaredDependency, DependencySet, ExplanationText,
            PackageNode, Resolution, ResolvedConstraintTree,
            VersionBound, VersionConstraint, VersionInterval,
        ) = _import_types()

        nodes = {
            "coq-mathcomp-ssreflect": _make_package_node(
                "coq-mathcomp-ssreflect", ["2.2.0"],
            ),
            "coq-iris": _make_package_node("coq-iris", ["4.0.0"]),
            "coq": _make_package_node(
                "coq", ["8.19.0", "8.18.0", "8.17.0"],
            ),
        }
        edges = [
            _make_constraint_edge(
                "coq-mathcomp-ssreflect", "coq",
                parse('>= "8.18"'), '>= "8.18"',
            ),
            _make_constraint_edge(
                "coq-iris", "coq",
                parse('< "8.18"'), '< "8.18"',
            ),
        ]
        tree = _make_constraint_tree(
            root_dependencies=["coq-mathcomp-ssreflect", "coq-iris"],
            nodes=nodes,
            edges=edges,
        )
        result = detect(tree)
        assert isinstance(result, ConflictSet)
        assert result.verdict == "incompatible"
        assert len(result.conflicts) >= 1
        coq_conflict = result.conflicts[0]
        assert coq_conflict.resource == "coq"
        # Minimal constraint set has both conflicting edges
        from_pkgs = {e.from_package for e in coq_conflict.minimal_constraint_set}
        assert "coq-mathcomp-ssreflect" in from_pkgs
        assert "coq-iris" in from_pkgs


# ===========================================================================
# 12. Interface Contract — spec §6
# ===========================================================================

class TestInterfaceContract:
    """§6: Interface contracts and statefulness requirements."""

    def test_stateless_between_invocations(self):
        """All operations are stateless — no data persists between invocations (§6)."""
        detect = _import_detect_conflicts()
        parse = _import_parse_constraint()

        tree = _two_dep_tree(
            dep_a_name="coq-mathcomp-ssreflect",
            dep_a_coq_raw='>= "8.18"',
            dep_a_coq_constraint=parse('>= "8.18"'),
            dep_b_name="coq-iris",
            dep_b_coq_raw='< "8.18"',
            dep_b_coq_constraint=parse('< "8.18"'),
            coq_versions=["8.19.0", "8.18.0", "8.17.0"],
        )
        result1 = detect(tree)
        result2 = detect(tree)
        # Both invocations produce the same result (no lingering state)
        assert result1.verdict == result2.verdict

    def test_idempotent(self):
        """All operations are idempotent given the same opam repository state (§6)."""
        parse = _import_parse_constraint()
        expr = '>= "8.18" & < "8.20~"'
        r1 = parse(expr)
        r2 = parse(expr)
        assert r1 == r2


# ===========================================================================
# 13. Tool Not Found — spec §7.2
# ===========================================================================

class TestToolNotFound:
    """§7.2: opam not on PATH."""

    def test_opam_not_found_error(self):
        """TOOL_NOT_FOUND when opam is not on PATH (§7.2)."""
        resolve = _import_resolve_metadata()
        (
            CONSTRAINT_PARSE_ERROR, INVALID_PARAMETER, NO_DEPENDENCIES,
            OPAM_TIMEOUT, PACKAGE_NOT_FOUND, PROJECT_NOT_FOUND,
            TOOL_NOT_FOUND, CompatError,
        ) = _import_errors()
        ds = _make_dependency_set(
            dependencies=[_make_declared_dependency("coq")],
        )
        with patch("shutil.which", return_value=None):
            with pytest.raises(CompatError) as exc_info:
                asyncio.get_event_loop().run_until_complete(resolve(ds))
            assert exc_info.value.code == TOOL_NOT_FOUND
            assert "opam" in str(exc_info.value)
