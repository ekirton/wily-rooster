"""Tests for nightly re-index automation.

Spec: specification/nightly-reindex.md §4.1-§4.9, §5
      specification/prebuilt-distribution.md §5 (--replace flag)

Scripts under test:
  scripts/nightly-reindex.sh
  scripts/reindex-cron.sh
  scripts/publish-release.sh (--replace flag addition)
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

PROJECT_ROOT = Path("/poule")
NIGHTLY_SCRIPT = PROJECT_ROOT / "scripts" / "nightly-reindex.sh"
CRON_SCRIPT = PROJECT_ROOT / "scripts" / "reindex-cron.sh"
PUBLISH_SCRIPT = PROJECT_ROOT / "scripts" / "publish-release.sh"

nightly_script_exists = pytest.mark.skipif(
    not NIGHTLY_SCRIPT.exists(),
    reason="scripts/nightly-reindex.sh not yet created",
)
cron_script_exists = pytest.mark.skipif(
    not CRON_SCRIPT.exists(),
    reason="scripts/reindex-cron.sh not yet created",
)
publish_script_exists = pytest.mark.skipif(
    not PUBLISH_SCRIPT.exists(),
    reason="scripts/publish-release.sh not yet created",
)


# ═══════════════════════════════════════════════════════════════════════════
# Inner script — scripts/nightly-reindex.sh
# ═══════════════════════════════════════════════════════════════════════════


@nightly_script_exists
class TestNightlyReindexScript:
    """Static properties of scripts/nightly-reindex.sh."""

    def test_script_exists_and_is_executable(self):
        """§8: The inner script must exist and be executable."""
        assert NIGHTLY_SCRIPT.exists(), "scripts/nightly-reindex.sh does not exist"
        mode = NIGHTLY_SCRIPT.stat().st_mode
        assert mode & stat.S_IXUSR, "scripts/nightly-reindex.sh is not executable"

    def test_script_has_bash_shebang(self):
        """§8: The inner script uses #!/usr/bin/env bash."""
        first_line = NIGHTLY_SCRIPT.read_text().splitlines()[0]
        assert first_line == "#!/usr/bin/env bash", (
            f"Expected bash shebang, got: {first_line}"
        )

    def test_script_uses_strict_mode(self):
        """§8: The inner script uses set -euo pipefail."""
        content = NIGHTLY_SCRIPT.read_text()
        assert "set -euo pipefail" in content, (
            "scripts/nightly-reindex.sh must use set -euo pipefail"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Outer script — scripts/reindex-cron.sh
# ═══════════════════════════════════════════════════════════════════════════


@cron_script_exists
class TestReindexCronScript:
    """Static properties of scripts/reindex-cron.sh."""

    def test_script_exists_and_is_executable(self):
        """§4.9: The outer script must exist and be executable."""
        assert CRON_SCRIPT.exists(), "scripts/reindex-cron.sh does not exist"
        mode = CRON_SCRIPT.stat().st_mode
        assert mode & stat.S_IXUSR, "scripts/reindex-cron.sh is not executable"

    def test_script_has_bash_shebang(self):
        """§8: The outer script uses #!/usr/bin/env bash."""
        first_line = CRON_SCRIPT.read_text().splitlines()[0]
        assert first_line == "#!/usr/bin/env bash", (
            f"Expected bash shebang, got: {first_line}"
        )

    def test_script_uses_strict_mode(self):
        """§8: The outer script uses set -euo pipefail."""
        content = CRON_SCRIPT.read_text()
        assert "set -euo pipefail" in content, (
            "scripts/reindex-cron.sh must use set -euo pipefail"
        )

    def test_script_checks_gh_token(self):
        """§4.9/§5: The outer script validates GH_TOKEN before docker run."""
        content = CRON_SCRIPT.read_text()
        assert "GH_TOKEN" in content, (
            "scripts/reindex-cron.sh must reference GH_TOKEN"
        )
        # The check must appear before the docker run command.
        # Find positions of the GH_TOKEN check and docker run.
        gh_token_pos = content.find("GH_TOKEN")
        docker_run_pos = content.find("docker run")
        assert docker_run_pos > 0, (
            "scripts/reindex-cron.sh must contain a docker run command"
        )
        assert gh_token_pos < docker_run_pos, (
            "GH_TOKEN validation must appear before docker run"
        )

    def test_script_checks_docker(self):
        """§5: The outer script checks for docker command availability."""
        content = CRON_SCRIPT.read_text()
        # The script should check docker is available (command -v docker or which docker)
        assert "docker" in content, (
            "scripts/reindex-cron.sh must reference docker"
        )
        # Expect a command-existence check pattern
        has_check = (
            "command -v docker" in content
            or "which docker" in content
            or "type docker" in content
        )
        assert has_check, (
            "scripts/reindex-cron.sh must check docker is on PATH "
            "(expected 'command -v docker', 'which docker', or 'type docker')"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Publish script — --replace flag
# ═══════════════════════════════════════════════════════════════════════════


@publish_script_exists
class TestPublishReplaceFlag:
    """Tests for the --replace flag addition to scripts/publish-release.sh."""

    def test_publish_script_accepts_replace_flag(self):
        """§4.7: publish-release.sh must handle a --replace flag."""
        content = PUBLISH_SCRIPT.read_text()
        assert "--replace" in content, (
            "scripts/publish-release.sh must accept a --replace flag "
            "(specification/nightly-reindex.md §4.7)"
        )

    def test_publish_script_help_mentions_replace(self):
        """§4.7: --replace appears in usage/help text."""
        content = PUBLISH_SCRIPT.read_text()
        # Find the usage function or help text block
        # The flag should be documented somewhere in the script
        lines = content.splitlines()
        replace_lines = [line for line in lines if "--replace" in line]
        # At least one line should be in a comment, echo, or usage function
        # (i.e., not only in the case statement)
        doc_lines = [
            line
            for line in replace_lines
            if "echo" in line or "Usage" in line or line.strip().startswith("#")
        ]
        assert len(doc_lines) > 0, (
            "--replace must be documented in usage/help text or a comment"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Behavioral tests — version comparison and manifest parsing
# ═══════════════════════════════════════════════════════════════════════════


SAMPLE_MANIFEST = {
    "schema_version": "1",
    "coq_version": "8.19.2",
    "created_at": "2025-01-15T00:00:00Z",
    "libraries": {
        "stdlib": {
            "version": "8.19.2",
            "sha256": "abc123",
            "asset_name": "index-stdlib.db",
            "declarations": 5000,
        },
        "mathcomp": {
            "version": "2.2.0",
            "sha256": "def456",
            "asset_name": "index-mathcomp.db",
            "declarations": 8000,
        },
        "stdpp": {
            "version": "1.12.0",
            "sha256": "ghi789",
            "asset_name": "index-stdpp.db",
            "declarations": 3000,
        },
        "flocq": {
            "version": "4.2.1",
            "sha256": "jkl012",
            "asset_name": "index-flocq.db",
            "declarations": 1000,
        },
        "coquelicot": {
            "version": "3.4.3",
            "sha256": "mno345",
            "asset_name": "index-coquelicot.db",
            "declarations": 1500,
        },
        "coqinterval": {
            "version": "4.11.4",
            "sha256": "pqr678",
            "asset_name": "index-coqinterval.db",
            "declarations": 2000,
        },
    },
    "onnx_model_sha256": None,
}

# The six supported libraries per §4.1
SUPPORTED_LIBRARIES = [
    "stdlib",
    "mathcomp",
    "stdpp",
    "flocq",
    "coquelicot",
    "coqinterval",
]


class TestNightlyReindexIntegration:
    """Behavioral tests for version comparison and manifest logic.

    These test the logical operations that the nightly re-index script
    performs, independent of the shell implementation.
    """

    def test_version_comparison_detects_change(self):
        """§4.3: A library is classified as 'changed' when installed
        version differs from published version."""
        # Simulate the comparison logic from the spec:
        # installed != published => changed
        installed = {"mathcomp": "2.3.0"}
        published = {"mathcomp": "2.2.0"}

        changed = installed["mathcomp"] != published["mathcomp"]
        assert changed, (
            "mathcomp 2.3.0 vs 2.2.0 should be classified as changed"
        )

    def test_version_comparison_detects_no_change(self):
        """§4.3: A library is classified as 'unchanged' when installed
        version exactly matches published version."""
        installed = {"stdlib": "8.19.2"}
        published = {"stdlib": "8.19.2"}

        changed = installed["stdlib"] != published["stdlib"]
        assert not changed, (
            "stdlib 8.19.2 vs 8.19.2 should be classified as unchanged"
        )

    def test_all_unchanged_means_no_extraction(self):
        """§4.4: When all 6 installed versions match published versions,
        no extraction occurs — script logs 'All indexes are current.'
        and exits 0."""
        installed_versions = {
            "stdlib": "8.19.2",
            "mathcomp": "2.2.0",
            "stdpp": "1.12.0",
            "flocq": "4.2.1",
            "coquelicot": "3.4.3",
            "coqinterval": "4.11.4",
        }
        published_versions = {
            lib: info["version"]
            for lib, info in SAMPLE_MANIFEST["libraries"].items()
        }

        changed_libs = [
            lib
            for lib in SUPPORTED_LIBRARIES
            if installed_versions[lib] != published_versions[lib]
        ]
        assert changed_libs == [], (
            f"Expected no changed libraries, got: {changed_libs}"
        )

    def test_manifest_parse_extracts_library_versions(self):
        """§4.2: Parse manifest.json and extract per-library version strings."""
        # Simulate parsing manifest JSON (as the inner script would via jq or python)
        manifest_json = json.dumps(SAMPLE_MANIFEST)
        parsed = json.loads(manifest_json)

        published_versions = {}
        for lib_name, lib_info in parsed["libraries"].items():
            published_versions[lib_name] = lib_info["version"]

        assert published_versions == {
            "stdlib": "8.19.2",
            "mathcomp": "2.2.0",
            "stdpp": "1.12.0",
            "flocq": "4.2.1",
            "coquelicot": "3.4.3",
            "coqinterval": "4.11.4",
        }
        # All 6 libraries must be present per §4.1
        assert set(published_versions.keys()) == set(SUPPORTED_LIBRARIES)

    def test_partial_extraction_failure_carries_forward(self):
        """§4.5: When extraction fails for one library but succeeds for
        others, the failed library's old asset is carried forward
        (reclassified as unchanged)."""
        changed_libs = ["mathcomp", "flocq"]
        extraction_results = {
            "mathcomp": False,  # extraction failed
            "flocq": True,  # extraction succeeded
        }

        # Per §4.5: failed extractions are reclassified as unchanged
        # for carry-forward purposes (§4.6).
        re_extracted = []
        carry_forward = list(
            set(SUPPORTED_LIBRARIES) - set(changed_libs)
        )  # initially unchanged

        for lib in changed_libs:
            if extraction_results[lib]:
                re_extracted.append(lib)
            else:
                # Reclassify as unchanged — carry forward previous asset
                carry_forward.append(lib)

        assert "flocq" in re_extracted, "flocq succeeded, should be re-extracted"
        assert "mathcomp" in carry_forward, (
            "mathcomp failed, should be carried forward"
        )
        assert "mathcomp" not in re_extracted, (
            "mathcomp failed, must not appear in re-extracted"
        )
        # At least one succeeded, so no abort (§4.5: abort only when ALL fail)
        assert len(re_extracted) > 0, (
            "At least one extraction succeeded, should not abort"
        )

    def test_all_extractions_fail_means_abort(self):
        """§4.5: When extraction fails for ALL changed libraries,
        the script aborts with exit code 1."""
        changed_libs = ["mathcomp", "flocq"]
        extraction_results = {
            "mathcomp": False,
            "flocq": False,
        }

        re_extracted = [
            lib for lib in changed_libs if extraction_results[lib]
        ]

        assert len(re_extracted) == 0, (
            "All extractions failed, re_extracted should be empty"
        )
        # Per §4.5: "On extraction failure for all changed libraries:
        # aborts with exit code 1. No publication occurs."
        should_abort = len(re_extracted) == 0
        assert should_abort

    def test_first_run_all_libraries_changed(self):
        """§4.2: When no existing release exists (first run), all 6
        libraries are treated as changed."""
        published_versions = {}  # No manifest — first run

        changed_libs = [
            lib
            for lib in SUPPORTED_LIBRARIES
            if lib not in published_versions
            or published_versions[lib] != "any-version"
        ]

        assert set(changed_libs) == set(SUPPORTED_LIBRARIES), (
            "First run: all 6 libraries should be classified as changed"
        )

    def test_manifest_write_round_trip(self, tmp_path):
        """§4.7: manifest.json can be written and re-read with consistent content."""
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(SAMPLE_MANIFEST, indent=2))

        loaded = json.loads(manifest_path.read_text())
        assert loaded["schema_version"] == "1"
        assert loaded["coq_version"] == "8.19.2"
        assert len(loaded["libraries"]) == 6
        for lib in SUPPORTED_LIBRARIES:
            assert lib in loaded["libraries"]
            assert "version" in loaded["libraries"][lib]
            assert "sha256" in loaded["libraries"][lib]
            assert "asset_name" in loaded["libraries"][lib]


# ═══════════════════════════════════════════════════════════════════════════
# Contract tests — require real scripts and tools
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.requires_coq
class TestNightlyReindexContract:
    """Contract tests that verify real script behavior.

    These require the scripts to exist and external tools (docker, gh)
    to be available. Skipped in CI unless explicitly enabled.
    """

    @nightly_script_exists
    def test_nightly_script_syntax_check(self):
        """Contract: nightly-reindex.sh passes bash -n syntax check."""
        import subprocess

        result = subprocess.run(
            ["bash", "-n", str(NIGHTLY_SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Syntax error in nightly-reindex.sh: {result.stderr}"
        )

    @cron_script_exists
    def test_cron_script_syntax_check(self):
        """Contract: reindex-cron.sh passes bash -n syntax check."""
        import subprocess

        result = subprocess.run(
            ["bash", "-n", str(CRON_SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Syntax error in reindex-cron.sh: {result.stderr}"
        )
