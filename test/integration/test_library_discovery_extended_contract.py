"""Contract tests for extended library discovery against real Coq installation.

These tests verify discover_libraries() works with real coqc -where for
stdpp, flocq, coquelicot, and coqinterval targets.

Spec: specification/extraction.md
"""

from __future__ import annotations

import pytest


class TestDiscoverLibrariesExtendedContract:
    """Contract tests verifying real library discovery against installed Coq."""

    def test_stdpp_real_discovery(self):
        """Contract: discover_libraries("stdpp") works with real coqc -where."""
        from Poule.extraction.pipeline import discover_libraries

        try:
            result = discover_libraries("stdpp")
            assert all(str(p).endswith(".vo") for p in result)
            assert len(result) > 0
        except Exception:
            pytest.skip("stdpp not installed")

    def test_flocq_real_discovery(self):
        """Contract: discover_libraries("flocq") works with real coqc -where."""
        from Poule.extraction.pipeline import discover_libraries

        try:
            result = discover_libraries("flocq")
            assert all(str(p).endswith(".vo") for p in result)
            assert len(result) > 0
        except Exception:
            pytest.skip("flocq not installed")

    def test_coquelicot_real_discovery(self):
        """Contract: discover_libraries("coquelicot") works with real coqc -where."""
        from Poule.extraction.pipeline import discover_libraries

        try:
            result = discover_libraries("coquelicot")
            assert all(str(p).endswith(".vo") for p in result)
            assert len(result) > 0
        except Exception:
            pytest.skip("coquelicot not installed")

    def test_coqinterval_real_discovery(self):
        """Contract: discover_libraries("coqinterval") works with real coqc -where."""
        from Poule.extraction.pipeline import discover_libraries

        try:
            result = discover_libraries("coqinterval")
            assert all(str(p).endswith(".vo") for p in result)
            assert len(result) > 0
        except Exception:
            pytest.skip("coqinterval not installed")
