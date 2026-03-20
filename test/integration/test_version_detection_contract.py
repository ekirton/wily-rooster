"""Contract tests for library version detection with real tools.

These tests verify detect_library_version() against real coqc and opam.

Spec: specification/extraction.md
"""

from __future__ import annotations

import pytest


class TestDetectLibraryVersionContract:
    """Contract tests verifying detect_library_version with real tools."""

    def test_stdlib_version_real(self):
        """Contract: detect_library_version("stdlib") returns a version string from real coqc."""
        from Poule.extraction.version_detection import detect_library_version

        result = detect_library_version("stdlib")
        assert result != "none", "Expected coqc to be installed for contract test"
        # Version should look like a semver-ish string
        parts = result.split(".")
        assert len(parts) >= 2, f"Expected version with dots, got: {result}"
        assert parts[0].isdigit(), f"Major version not numeric: {result}"

    def test_mathcomp_version_real(self):
        """Contract: detect_library_version("mathcomp") returns a version or 'none'."""
        from Poule.extraction.version_detection import detect_library_version

        result = detect_library_version("mathcomp")
        # Either a version string or "none" — both are valid
        assert isinstance(result, str)
        if result != "none":
            assert "." in result, f"Expected dotted version, got: {result}"

    def test_stdpp_version_real(self):
        """Contract: detect_library_version("stdpp") returns a version or 'none'."""
        from Poule.extraction.version_detection import detect_library_version

        result = detect_library_version("stdpp")
        assert isinstance(result, str)
        if result != "none":
            assert "." in result, f"Expected dotted version, got: {result}"
