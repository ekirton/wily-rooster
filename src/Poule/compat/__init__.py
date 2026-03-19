"""Compatibility analysis engine (specification/compatibility-analysis.md)."""

import asyncio  # exposed so tests can patch Poule.compat.asyncio.create_subprocess_exec

from Poule.compat.detector import detect_conflicts
from Poule.compat.explainer import build_explanation
from Poule.compat.parser import parse_constraint
from Poule.compat.resolver import resolve_metadata
from Poule.compat.scanner import scan_dependencies
from Poule.compat.suggester import suggest_resolutions
from Poule.compat.versions import compare_versions, intersect, is_empty

__all__ = [
    "scan_dependencies",
    "resolve_metadata",
    "parse_constraint",
    "detect_conflicts",
    "build_explanation",
    "suggest_resolutions",
    "compare_versions",
    "intersect",
    "is_empty",
]
