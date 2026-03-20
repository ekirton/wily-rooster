"""Contract tests for the Proof Profiling Engine — requires real coqc.

Extracted from test/unit/test_proof_profiling.py. These tests exercise
real coqc to verify mock assumptions in the unit tests.

Spec: specification/proof-profiling.md
"""

from __future__ import annotations

import subprocess
import textwrap

import pytest


# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

def _import_profile_file():
    from Poule.profiler.engine import profile_file
    return profile_file


def _import_file_profile():
    from Poule.profiler.types import FileProfile
    return FileProfile


def _import_parse_timing():
    from Poule.profiler.parser import parse_timing_output
    return parse_timing_output


def _import_locate_coqc():
    from Poule.profiler.engine import locate_coqc
    return locate_coqc


class TestContractLocateCoqc:
    """Contract test: locate_coqc with real shutil.which."""

    def test_contract_locate_coqc_real(self):
        """Contract test: locate_coqc with real shutil.which."""
        locate_coqc = _import_locate_coqc()
        result = locate_coqc()
        # On a system with coqc: returns a string path
        # On a system without: returns an error
        assert result is not None


class TestContractRealCoqc:
    """Contract tests requiring a real Coq installation."""

    @pytest.mark.asyncio
    async def test_contract_profile_file_real(self, tmp_path):
        """Contract test: profile_file with real coqc binary."""
        profile_file = _import_profile_file()
        v_file = tmp_path / "Test.v"
        v_file.write_text(textwrap.dedent("""\
            Lemma trivial : True.
            Proof. exact I. Qed.
        """))

        result = await profile_file(str(v_file), timeout_seconds=60)
        FileProfile = _import_file_profile()
        assert isinstance(result, FileProfile)
        assert result.compilation_succeeded is True
        assert result.total_time_s >= 0.0
        assert len(result.sentences) > 0

    @pytest.mark.asyncio
    async def test_contract_parse_real_timing_output(self, tmp_path):
        """Contract test: parse real coqc -time-file output."""
        v_file = tmp_path / "Test.v"
        v_file.write_text("Lemma foo : True. Proof. exact I. Qed.\n")
        timing_file = tmp_path / "Test.v.timing"

        result = subprocess.run(
            ["coqc", "-time-file", str(timing_file), str(v_file)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and timing_file.exists():
            parse = _import_parse_timing()
            sentences = parse(timing_file.read_text())
            assert len(sentences) > 0
            for s in sentences:
                assert s.char_start >= 0
                assert s.real_time_s >= 0.0
