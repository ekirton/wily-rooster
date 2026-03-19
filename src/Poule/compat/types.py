"""Data model types for the compatibility analysis engine (spec section 5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class VersionBound:
    """A version bound with inclusive/exclusive flag."""

    version: str
    inclusive: bool


@dataclass(frozen=True)
class VersionInterval:
    """A contiguous range of versions defined by lower and upper bounds."""

    lower: Optional[VersionBound] = None
    upper: Optional[VersionBound] = None


@dataclass(frozen=True)
class VersionConstraint:
    """A version constraint in disjunctive normal form (union of intervals)."""

    intervals: list[VersionInterval] = field(default_factory=list)


@dataclass(frozen=True)
class DeclaredDependency:
    """A dependency declared in a project file."""

    package_name: str
    version_constraint: Optional[str] = None
    source_file: str = ""
    hypothetical: bool = False


@dataclass(frozen=True)
class DependencySet:
    """The set of dependencies extracted from a project."""

    dependencies: list[DeclaredDependency] = field(default_factory=list)
    project_dir: str = ""
    build_system: str = "UNKNOWN"
    unknown_packages: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PackageNode:
    """A package in the resolved constraint tree."""

    name: str
    available_versions: list[str] = field(default_factory=list)
    installed_version: Optional[str] = None


@dataclass(frozen=True)
class ConstraintEdge:
    """A directed edge carrying a version constraint between packages."""

    from_package: str
    to_package: str
    constraint: VersionConstraint = field(default_factory=lambda: VersionConstraint())
    raw_constraint: str = ""


@dataclass(frozen=True)
class ResolvedConstraintTree:
    """The full resolved dependency tree with constraint edges."""

    root_dependencies: list[str] = field(default_factory=list)
    nodes: dict[str, PackageNode] = field(default_factory=dict)
    edges: list[ConstraintEdge] = field(default_factory=list)


@dataclass(frozen=True)
class ExplanationText:
    """A plain-language explanation of a conflict."""

    summary: str = ""
    constraint_chains: list[list[str]] = field(default_factory=list)


@dataclass(frozen=True)
class Resolution:
    """A suggested resolution for a conflict."""

    strategy: str = ""
    target_package: str = ""
    target_version: Optional[str] = None
    alternative_package: Optional[str] = None
    trade_off: str = ""


@dataclass(frozen=True)
class Conflict:
    """A conflict on a shared resource."""

    resource: str = ""
    minimal_constraint_set: list[ConstraintEdge] = field(default_factory=list)
    explanation: Optional[ExplanationText] = None
    resolutions: list[Resolution] = field(default_factory=list)


@dataclass(frozen=True)
class ConflictSet:
    """Result when dependencies are incompatible."""

    verdict: str = "incompatible"
    conflicts: list[Conflict] = field(default_factory=list)


@dataclass(frozen=True)
class CompatibleSet:
    """Result when dependencies are compatible."""

    verdict: str = "compatible"
    version_map: dict[str, str] = field(default_factory=dict)
    coq_version_range: Optional[VersionConstraint] = None
