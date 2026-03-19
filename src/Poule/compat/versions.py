"""Version comparison and interval arithmetic (spec sections 4.3, 10)."""

from __future__ import annotations

import re
from typing import Optional

from Poule.compat.types import VersionBound, VersionConstraint, VersionInterval

# Segment splitting: split on '.', '-', '~', '+' boundaries while keeping delimiters
_SEGMENT_RE = re.compile(r"([.+~-])")


def _split_version(v: str) -> list[str]:
    """Split a version string into segments for comparison."""
    parts = _SEGMENT_RE.split(v)
    return [p for p in parts if p]


def _segment_key(seg: str) -> tuple[int, int | str]:
    """Return a sort key for a single segment.

    Ordering rules (spec §4.3):
    - '~' sorts before everything (key type 0)
    - '.' and '-' are neutral separators (key type 1)
    - numeric segments sort numerically (key type 2)
    - string segments sort lexicographically (key type 3)
    - '+' sorts after everything (key type 4)
    """
    if seg == "~":
        return (0, 0)
    if seg in (".", "-"):
        return (1, 0)
    if seg == "+":
        return (4, 0)
    if seg.isdigit():
        return (2, int(seg))
    # Mixed alpha-numeric: try numeric first
    try:
        return (2, int(seg))
    except ValueError:
        return (3, seg)


def compare_versions(a: str, b: str) -> int:
    """Compare two version strings using opam ordering rules.

    Returns negative if a < b, 0 if equal, positive if a > b.
    """
    if a == b:
        return 0

    parts_a = _split_version(a)
    parts_b = _split_version(b)

    # Handle tilde: a version ending with ~ sorts before the version without it
    # e.g., "8.18~" < "8.18", "8.18~beta" < "8.18"
    len_a = len(parts_a)
    len_b = len(parts_b)
    max_len = max(len_a, len_b)

    for i in range(max_len):
        seg_a = parts_a[i] if i < len_a else None
        seg_b = parts_b[i] if i < len_b else None

        if seg_a is None and seg_b is None:
            return 0

        # Missing segment: depends on what the other segment is
        if seg_a is None:
            # b has more segments
            if seg_b == "~":
                # tilde sorts before end-of-string? No — end-of-string sorts after tilde
                return 1  # a > b (a is "8.18", b is "8.18~...")
            if seg_b == "+":
                return -1  # a < b (base sorts before +suffix)
            # For other segments (like ".0"), shorter version is less
            return -1
        if seg_b is None:
            if seg_a == "~":
                return -1  # a < b (tilde sorts before end)
            if seg_a == "+":
                return 1  # a > b (+suffix sorts after base)
            return 1

        key_a = _segment_key(seg_a)
        key_b = _segment_key(seg_b)

        if key_a < key_b:
            return -1
        if key_a > key_b:
            return 1

    return 0


def _version_satisfies_bound(version: str, bound: VersionBound, is_lower: bool) -> bool:
    """Check if a version satisfies a single bound."""
    cmp = compare_versions(version, bound.version)
    if is_lower:
        return cmp > 0 or (cmp == 0 and bound.inclusive)
    else:
        return cmp < 0 or (cmp == 0 and bound.inclusive)


def _version_in_interval(version: str, interval: VersionInterval) -> bool:
    """Check if a version falls within an interval."""
    if interval.lower is not None:
        if not _version_satisfies_bound(version, interval.lower, is_lower=True):
            return False
    if interval.upper is not None:
        if not _version_satisfies_bound(version, interval.upper, is_lower=False):
            return False
    return True


def version_in_constraint(version: str, constraint: VersionConstraint) -> bool:
    """Check if a version satisfies a constraint (any interval)."""
    if not constraint.intervals:
        return False
    return any(_version_in_interval(version, iv) for iv in constraint.intervals)


def _intersect_intervals(a: VersionInterval, b: VersionInterval) -> Optional[VersionInterval]:
    """Intersect two intervals, returning None if result is empty."""
    # Compute lower bound: take the higher of the two
    lower: Optional[VersionBound] = None
    if a.lower is not None and b.lower is not None:
        cmp = compare_versions(a.lower.version, b.lower.version)
        if cmp > 0:
            lower = a.lower
        elif cmp < 0:
            lower = b.lower
        else:
            # Same version: take the more restrictive (less inclusive)
            lower = VersionBound(a.lower.version, a.lower.inclusive and b.lower.inclusive)
    elif a.lower is not None:
        lower = a.lower
    elif b.lower is not None:
        lower = b.lower

    # Compute upper bound: take the lower of the two
    upper: Optional[VersionBound] = None
    if a.upper is not None and b.upper is not None:
        cmp = compare_versions(a.upper.version, b.upper.version)
        if cmp < 0:
            upper = a.upper
        elif cmp > 0:
            upper = b.upper
        else:
            upper = VersionBound(a.upper.version, a.upper.inclusive and b.upper.inclusive)
    elif a.upper is not None:
        upper = a.upper
    elif b.upper is not None:
        upper = b.upper

    # Check if result is empty
    if lower is not None and upper is not None:
        cmp = compare_versions(lower.version, upper.version)
        if cmp > 0:
            return None  # lower > upper: empty
        if cmp == 0 and not (lower.inclusive and upper.inclusive):
            return None  # touching but not both inclusive: empty

    return VersionInterval(lower=lower, upper=upper)


def intersect(a: VersionConstraint, b: VersionConstraint) -> VersionConstraint:
    """Intersect two version constraints (DNF intersection).

    Each constraint is a union of intervals. The intersection is the union of
    all pairwise interval intersections.
    """
    result_intervals: list[VersionInterval] = []
    for iv_a in a.intervals:
        for iv_b in b.intervals:
            iv = _intersect_intervals(iv_a, iv_b)
            if iv is not None:
                result_intervals.append(iv)
    return VersionConstraint(intervals=result_intervals)


def is_empty(vc: VersionConstraint) -> bool:
    """Check if a version constraint is empty (no satisfying versions)."""
    return len(vc.intervals) == 0
