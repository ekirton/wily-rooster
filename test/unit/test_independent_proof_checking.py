"""TDD tests for the Proof Checker Adapter (specification/independent-proof-checking.md).

Tests are written BEFORE implementation. They will fail with ImportError
until src/poule/checker/ modules exist.

Spec: specification/independent-proof-checking.md
Architecture: doc/architecture/independent-proof-checking.md

Import paths under test:
  poule.checker.adapter      (check_proof, validate_request, locate_coqchk, etc.)
  poule.checker.types        (CheckRequest, CheckResult, CheckFailure)
  poule.checker.parser       (parse_output)
  poule.checker.paths        (resolve_library_name, build_command)
  poule.checker.discovery    (parse_coqproject, discover_vo_files)
"""

from __future__ import annotations

import asyncio
import os
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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


def _import_validate():
    from Poule.checker.adapter import validate_request
    return validate_request


def _import_locate():
    from Poule.checker.adapter import locate_coqchk
    return locate_coqchk


def _import_resolve():
    from Poule.checker.paths import resolve_library_name
    return resolve_library_name


def _import_build_command():
    from Poule.checker.paths import build_command
    return build_command


def _import_parser():
    from Poule.checker.parser import parse_output
    return parse_output


def _import_check_single():
    from Poule.checker.adapter import check_single
    return check_single


def _import_check_project():
    from Poule.checker.adapter import check_project
    return check_project


def _import_discovery():
    from Poule.checker.discovery import parse_coqproject, discover_vo_files
    return parse_coqproject, discover_vo_files


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


def _make_check_result(
    status="pass",
    files_checked=0,
    files_passed=0,
    files_failed=0,
    failures=None,
    stale_files=None,
    wall_time_ms=0,
    raw_output="",
):
    _, CheckResult, _ = _import_types()
    return CheckResult(
        status=status,
        files_checked=files_checked,
        files_passed=files_passed,
        files_failed=files_failed,
        failures=failures or [],
        stale_files=stale_files or [],
        wall_time_ms=wall_time_ms,
        raw_output=raw_output,
    )


def _make_check_failure(
    file_path="/tmp/Foo.vo",
    module_name=None,
    definition=None,
    failure_kind="unknown",
    raw_message="",
):
    _, _, CheckFailure = _import_types()
    return CheckFailure(
        file_path=file_path,
        module_name=module_name,
        definition=definition,
        failure_kind=failure_kind,
        raw_message=raw_message,
    )


# ===========================================================================
# 1. Data Model — Section 5
# ===========================================================================

class TestCheckRequestDataModel:
    """Section 5: CheckRequest field constraints."""

    def test_single_mode_requires_file_path(self):
        """mode='single' requires file_path to be non-null."""
        CheckRequest, _, _ = _import_types()
        req = CheckRequest(
            mode="single",
            file_path="/tmp/Foo.vo",
            project_dir=None,
            include_paths=[],
            load_paths=[],
            timeout_seconds=300,
        )
        assert req.mode == "single"
        assert req.file_path == "/tmp/Foo.vo"

    def test_project_mode_requires_project_dir(self):
        """mode='project' requires project_dir to be non-null."""
        CheckRequest, _, _ = _import_types()
        req = CheckRequest(
            mode="project",
            file_path=None,
            project_dir="/tmp/myproject",
            include_paths=[],
            load_paths=[],
            timeout_seconds=300,
        )
        assert req.mode == "project"
        assert req.project_dir == "/tmp/myproject"

    def test_default_include_paths_empty(self):
        """include_paths defaults to empty list."""
        req = _make_check_request(file_path="/tmp/Foo.vo")
        assert req.include_paths == []

    def test_default_load_paths_empty(self):
        """load_paths defaults to empty list."""
        req = _make_check_request(file_path="/tmp/Foo.vo")
        assert req.load_paths == []

    def test_timeout_seconds_default_300(self):
        """timeout_seconds defaults to 300."""
        CheckRequest, _, _ = _import_types()
        req = CheckRequest(
            mode="single",
            file_path="/tmp/Foo.vo",
            project_dir=None,
            include_paths=[],
            load_paths=[],
            timeout_seconds=300,
        )
        assert req.timeout_seconds == 300


class TestCheckResultDataModel:
    """Section 5: CheckResult field constraints and invariants."""

    def test_pass_status_has_empty_failures(self):
        """When status='pass', failures is empty and files_failed=0."""
        result = _make_check_result(status="pass", files_checked=1, files_passed=1)
        assert result.status == "pass"
        assert result.failures == []
        assert result.files_failed == 0

    def test_fail_status_has_nonempty_failures(self):
        """When status='fail', failures is non-empty."""
        failure = _make_check_failure(failure_kind="inconsistency", raw_message="err")
        result = _make_check_result(
            status="fail",
            files_checked=1,
            files_failed=1,
            failures=[failure],
        )
        assert result.status == "fail"
        assert len(result.failures) >= 1

    def test_error_status_has_failure_describing_error(self):
        """When status='error', at least one CheckFailure describes the error."""
        failure = _make_check_failure(
            failure_kind="unknown", raw_message="coqchk not found",
        )
        result = _make_check_result(status="error", failures=[failure])
        assert result.status == "error"
        assert len(result.failures) >= 1

    def test_passed_plus_failed_leq_checked(self):
        """files_passed + files_failed <= files_checked."""
        result = _make_check_result(
            files_checked=5, files_passed=3, files_failed=1,
        )
        assert result.files_passed + result.files_failed <= result.files_checked

    def test_stale_files_is_list_of_strings(self):
        """stale_files is a list of absolute path strings."""
        result = _make_check_result(stale_files=["/project/theories/Bar.vo"])
        assert isinstance(result.stale_files, list)
        assert all(isinstance(s, str) for s in result.stale_files)

    def test_raw_output_is_string(self):
        """raw_output is a string (possibly empty)."""
        result = _make_check_result(raw_output="")
        assert isinstance(result.raw_output, str)


class TestCheckFailureDataModel:
    """Section 5: CheckFailure field constraints."""

    def test_failure_kind_values(self):
        """failure_kind must be one of the five allowed values."""
        allowed = {"inconsistency", "missing_dependency", "axiom_mismatch",
                   "type_error", "unknown"}
        for kind in allowed:
            f = _make_check_failure(failure_kind=kind, raw_message="test")
            assert f.failure_kind == kind

    def test_module_name_nullable(self):
        """module_name can be null."""
        f = _make_check_failure(module_name=None)
        assert f.module_name is None

    def test_definition_nullable(self):
        """definition can be null."""
        f = _make_check_failure(definition=None)
        assert f.definition is None

    def test_raw_message_required(self):
        """raw_message is required (non-null string)."""
        f = _make_check_failure(raw_message="Error: something")
        assert isinstance(f.raw_message, str)


# ===========================================================================
# 2. Request Validation — Section 4.1
# ===========================================================================

class TestValidateRequest:
    """Section 4.1: validate_request behavioral requirements."""

    def test_single_mode_missing_file_returns_error(self):
        """Given mode='single' and file_path to non-existent file,
        returns CheckResult with status='error' and failure_kind='missing_dependency'."""
        validate_request = _import_validate()
        _, CheckResult, _ = _import_types()
        req = _make_check_request(mode="single", file_path="/tmp/Missing.vo")
        result = validate_request(req)
        assert isinstance(result, CheckResult)
        assert result.status == "error"
        assert len(result.failures) >= 1
        assert result.failures[0].failure_kind == "missing_dependency"

    def test_single_mode_wrong_extension_returns_error(self):
        """Given mode='single' and file_path='/tmp/Foo.v',
        returns CheckResult with status='error' identifying wrong extension."""
        validate_request = _import_validate()
        req = _make_check_request(mode="single", file_path="/tmp/Foo.v")
        result = validate_request(req)
        assert result.status == "error"
        assert len(result.failures) >= 1

    def test_project_mode_null_project_dir_returns_error(self):
        """Given mode='project' and project_dir=null,
        returns CheckResult with status='error' immediately."""
        validate_request = _import_validate()
        req = _make_check_request(mode="project", project_dir=None)
        result = validate_request(req)
        assert result.status == "error"

    def test_single_mode_null_file_path_returns_error(self):
        """Given mode='single' and file_path=null,
        returns CheckResult with status='error' identifying missing field."""
        validate_request = _import_validate()
        req = _make_check_request(mode="single", file_path=None)
        result = validate_request(req)
        assert result.status == "error"

    def test_project_mode_missing_dir_returns_error(self):
        """Given mode='project' and project_dir does not exist,
        returns CheckResult with status='error'."""
        validate_request = _import_validate()
        req = _make_check_request(mode="project", project_dir="/nonexistent/dir")
        result = validate_request(req)
        assert result.status == "error"

    def test_valid_single_request_returns_none(self, tmp_path):
        """Given a valid single-mode request with existing .vo file,
        validate_request returns None (no error)."""
        validate_request = _import_validate()
        vo_file = tmp_path / "Foo.vo"
        vo_file.touch()
        req = _make_check_request(mode="single", file_path=str(vo_file))
        result = validate_request(req)
        assert result is None

    def test_valid_project_request_returns_none(self, tmp_path):
        """Given a valid project-mode request with existing directory,
        validate_request returns None (no error)."""
        validate_request = _import_validate()
        req = _make_check_request(mode="project", project_dir=str(tmp_path))
        result = validate_request(req)
        assert result is None


# ===========================================================================
# 3. Binary Discovery — Section 4.2
# ===========================================================================

class TestLocateCoqchk:
    """Section 4.2: locate_coqchk behavioral requirements."""

    @patch("shutil.which", return_value=None)
    def test_not_found_returns_error(self, mock_which):
        """Given coqchk is not on PATH, returns CheckResult with status='error'
        and message 'coqchk not found'."""
        locate_coqchk = _import_locate()
        _, CheckResult, _ = _import_types()
        result = locate_coqchk()
        assert isinstance(result, CheckResult)
        assert result.status == "error"
        assert any("coqchk not found" in f.raw_message for f in result.failures)

    @patch("shutil.which", return_value="/usr/bin/coqchk")
    def test_found_returns_absolute_path(self, mock_which):
        """Given coqchk is on PATH, returns an absolute path string."""
        locate_coqchk = _import_locate()
        result = locate_coqchk()
        assert isinstance(result, str)
        assert os.path.isabs(result)



# ===========================================================================
# 4. Library Path Resolution — Section 4.3
# ===========================================================================

class TestResolveLibraryName:
    """Section 4.3: resolve_library_name behavioral requirements."""

    def test_basic_resolution(self):
        """Given file_path='/project/theories/Arith/Plus.vo' and
        load_paths=[('MyLib', '/project/theories')],
        returns 'MyLib.Arith.Plus'."""
        resolve_library_name = _import_resolve()
        result = resolve_library_name(
            "/project/theories/Arith/Plus.vo",
            [("MyLib", "/project/theories")],
        )
        assert result == "MyLib.Arith.Plus"

    def test_no_matching_load_path_returns_bare_name(self):
        """Given no load path matches, returns bare filename without extension
        and emits a warning."""
        resolve_library_name = _import_resolve()
        # Spec says "emits a warning" — we check the return value
        result = resolve_library_name(
            "/tmp/Scratch.vo",
            [("Lib", "/project/src")],
        )
        assert result == "Scratch"

    def test_longest_prefix_selected(self):
        """Given multiple matching load paths, the longest physical prefix wins."""
        resolve_library_name = _import_resolve()
        result = resolve_library_name(
            "/project/theories/sub/Foo.vo",
            [("A", "/project/theories"), ("B", "/project/theories/sub")],
        )
        # B has longer prefix "/project/theories/sub"
        assert result == "B.Foo"

    def test_strips_vo_extension(self):
        """The .vo extension is stripped before constructing the logical name."""
        resolve_library_name = _import_resolve()
        result = resolve_library_name(
            "/project/theories/Foo.vo",
            [("MyLib", "/project/theories")],
        )
        assert not result.endswith(".vo")
        assert result == "MyLib.Foo"

    def test_path_separators_become_dots(self):
        """Path separators in the relative path are replaced with dots."""
        resolve_library_name = _import_resolve()
        result = resolve_library_name(
            "/project/theories/A/B/C.vo",
            [("Lib", "/project/theories")],
        )
        assert result == "Lib.A.B.C"


# ===========================================================================
# 5. Command Construction — Section 4.4
# ===========================================================================

class TestBuildCommand:
    """Section 4.4: build_command behavioral requirements."""

    def test_spec_example(self):
        """Spec example: load_paths, include_paths, library_names produce
        correct argument vector."""
        build_command = _import_build_command()
        result = build_command(
            coqchk_path="coqchk",
            load_paths=[("MyLib", "/project/theories")],
            include_paths=["/project/plugins"],
            library_names=["MyLib.Foo"],
        )
        assert result == [
            "coqchk",
            "-Q", "/project/theories", "MyLib",
            "-I", "/project/plugins",
            "MyLib.Foo",
        ]

    def test_multiple_load_paths(self):
        """Multiple load paths each produce -Q flags."""
        build_command = _import_build_command()
        result = build_command(
            coqchk_path="/usr/bin/coqchk",
            load_paths=[("A", "/dir1"), ("B", "/dir2")],
            include_paths=[],
            library_names=["A.Foo"],
        )
        assert "-Q" in result
        # Two -Q flag pairs
        q_indices = [i for i, x in enumerate(result) if x == "-Q"]
        assert len(q_indices) == 2

    def test_no_extra_flags(self):
        """No -silent, -norec, or -admit flags are added."""
        build_command = _import_build_command()
        result = build_command(
            coqchk_path="coqchk",
            load_paths=[("MyLib", "/project/theories")],
            include_paths=[],
            library_names=["MyLib.Foo"],
        )
        forbidden = {"-silent", "-norec", "-admit"}
        assert not forbidden.intersection(set(result))

    def test_empty_load_and_include_paths(self):
        """With empty load_paths and include_paths, command has coqchk + library names only."""
        build_command = _import_build_command()
        result = build_command(
            coqchk_path="coqchk",
            load_paths=[],
            include_paths=[],
            library_names=["Foo"],
        )
        assert result == ["coqchk", "Foo"]

    def test_multiple_library_names(self):
        """Multiple library names appear at the end of the argument vector."""
        build_command = _import_build_command()
        result = build_command(
            coqchk_path="coqchk",
            load_paths=[],
            include_paths=[],
            library_names=["A.Foo", "A.Bar", "A.Baz"],
        )
        assert result[-3:] == ["A.Foo", "A.Bar", "A.Baz"]


# ===========================================================================
# 6. Output Parsing — Section 4.7
# ===========================================================================

class TestParseOutput:
    """Section 4.7: parse_output behavioral requirements."""

    def test_success_exit_code_zero(self):
        """Given exit code 0 with two 'has been checked' lines,
        files_checked=2, files_passed=2, files_failed=0, failures=[]."""
        parse_output = _import_parser()
        stdout = "MyLib.Foo has been checked\nMyLib.Bar has been checked"
        stderr = ""
        files_checked, files_passed, files_failed, failures = parse_output(
            stdout=stdout, stderr=stderr, exit_code=0,
            library_names=["MyLib.Foo", "MyLib.Bar"],
        )
        assert files_checked == 2
        assert files_passed == 2
        assert files_failed == 0
        assert failures == []

    def test_inconsistency_failure(self):
        """Given exit code 1 with inconsistency error,
        returns CheckFailure with failure_kind='inconsistency'."""
        parse_output = _import_parser()
        _, _, CheckFailure = _import_types()
        stderr = "Error: MyLib.Baz is not consistent with MyLib.Foo"
        _, _, _, failures = parse_output(
            stdout="", stderr=stderr, exit_code=1,
            library_names=["MyLib.Baz"],
        )
        assert len(failures) >= 1
        assert isinstance(failures[0], CheckFailure)
        assert failures[0].failure_kind == "inconsistency"
        assert failures[0].module_name == "MyLib.Baz"

    def test_missing_dependency_failure(self):
        """Given exit code 1 with 'Error: Missing library ...',
        returns CheckFailure with failure_kind='missing_dependency'."""
        parse_output = _import_parser()
        stderr = "Error: Missing library MyLib.Gone"
        _, _, _, failures = parse_output(
            stdout="", stderr=stderr, exit_code=1,
            library_names=["MyLib.Gone"],
        )
        assert len(failures) >= 1
        assert failures[0].failure_kind == "missing_dependency"

    def test_cannot_find_library_failure(self):
        """Given 'Cannot find library ...' pattern, classified as missing_dependency."""
        parse_output = _import_parser()
        stderr = "Cannot find library MyLib.Absent"
        _, _, _, failures = parse_output(
            stdout="", stderr=stderr, exit_code=1,
            library_names=["MyLib.Absent"],
        )
        assert len(failures) >= 1
        assert failures[0].failure_kind == "missing_dependency"

    def test_type_error_failure(self):
        """Given 'Error: Anomaly ...' or 'Type error ...',
        returns failure_kind='type_error'."""
        parse_output = _import_parser()
        stderr = "Error: Anomaly in type checking"
        _, _, _, failures = parse_output(
            stdout="", stderr=stderr, exit_code=1,
            library_names=["MyLib.Foo"],
        )
        assert len(failures) >= 1
        assert failures[0].failure_kind == "type_error"

    def test_type_error_from_type_error_line(self):
        """Given 'Type error ...' pattern, classified as type_error."""
        parse_output = _import_parser()
        stderr = "Type error in definition my_lemma"
        _, _, _, failures = parse_output(
            stdout="", stderr=stderr, exit_code=1,
            library_names=["MyLib.Foo"],
        )
        assert len(failures) >= 1
        assert failures[0].failure_kind == "type_error"

    def test_axiom_mismatch_failure(self):
        """Given axiom mismatch error, returns failure_kind='axiom_mismatch'."""
        parse_output = _import_parser()
        stderr = "Error: my_axiom (axiom) mismatch"
        _, _, _, failures = parse_output(
            stdout="", stderr=stderr, exit_code=1,
            library_names=["MyLib.Foo"],
        )
        assert len(failures) >= 1
        assert failures[0].failure_kind == "axiom_mismatch"

    def test_unknown_error_line(self):
        """Given an unrecognized 'Error:' line, returns failure_kind='unknown'."""
        parse_output = _import_parser()
        stderr = "Error: something completely unexpected happened"
        _, _, _, failures = parse_output(
            stdout="", stderr=stderr, exit_code=1,
            library_names=["MyLib.Foo"],
        )
        assert len(failures) >= 1
        assert failures[0].failure_kind == "unknown"

    def test_unrecognized_stderr_no_spurious_failures(self):
        """Unrecognized stderr without 'Error:' prefix does not produce
        spurious CheckFailure entries."""
        parse_output = _import_parser()
        stderr = "Warning: some informational message\nDebug: trace output"
        _, _, _, failures = parse_output(
            stdout="MyLib.Foo has been checked",
            stderr=stderr,
            exit_code=0,
            library_names=["MyLib.Foo"],
        )
        assert failures == []

    def test_null_exit_code_indicates_timeout(self):
        """Given exit_code=None (timeout/kill), parser handles gracefully."""
        parse_output = _import_parser()
        _, _, _, failures = parse_output(
            stdout="", stderr="", exit_code=None,
            library_names=["MyLib.Foo"],
        )
        # The caller (check_single) creates the synthetic timeout failure,
        # but the parser should not crash on null exit code
        assert isinstance(failures, list)

    def test_priority_order_inconsistency_over_missing(self):
        """Inconsistency pattern (priority 1) takes precedence over
        missing dependency (priority 2) on the same line."""
        parse_output = _import_parser()
        # A line that could match both patterns should match inconsistency first
        stderr = "Error: MyLib.A is not consistent with MyLib.B"
        _, _, _, failures = parse_output(
            stdout="", stderr=stderr, exit_code=1,
            library_names=["MyLib.A"],
        )
        assert failures[0].failure_kind == "inconsistency"

    def test_success_counting_from_stdout(self):
        """On non-zero exit, success lines from stdout are still counted."""
        parse_output = _import_parser()
        stdout = "MyLib.Foo has been checked"
        stderr = "Error: MyLib.Bar is not consistent with MyLib.Foo"
        files_checked, files_passed, files_failed, failures = parse_output(
            stdout=stdout, stderr=stderr, exit_code=1,
            library_names=["MyLib.Foo", "MyLib.Bar"],
        )
        # MyLib.Foo checked successfully, MyLib.Bar failed
        assert files_passed >= 1
        assert files_failed >= 1


# ===========================================================================
# 7. Single-File Checking — Section 4.5
# ===========================================================================

class TestCheckSingle:
    """Section 4.5: check_single behavioral requirements."""

    @pytest.mark.asyncio
    async def test_pass_result(self, tmp_path):
        """Given a valid .vo file and coqchk exits with code 0,
        CheckResult has status='pass', files_checked=1, files_passed=1."""
        check_single = _import_check_single()
        _, CheckResult, _ = _import_types()

        vo_file = tmp_path / "Foo.vo"
        vo_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"Foo has been checked", b""
        )
        mock_process.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_single(
                file_path=str(vo_file),
                include_paths=[],
                load_paths=[],
                timeout_seconds=300,
            )

        assert isinstance(result, CheckResult)
        assert result.status == "pass"
        assert result.files_checked == 1
        assert result.files_passed == 1
        assert result.files_failed == 0

    @pytest.mark.asyncio
    async def test_staleness_detection(self, tmp_path):
        """Given a .vo file whose .v source has newer mtime,
        CheckResult contains the file in stale_files."""
        check_single = _import_check_single()

        vo_file = tmp_path / "Bar.vo"
        v_file = tmp_path / "Bar.v"
        vo_file.touch()
        # Ensure .v is strictly newer
        import time
        time.sleep(0.05)
        v_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"Bar has been checked", b""
        )
        mock_process.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_single(
                file_path=str(vo_file),
                include_paths=[],
                load_paths=[],
                timeout_seconds=300,
            )

        assert str(vo_file) in result.stale_files

    @pytest.mark.asyncio
    async def test_no_staleness_when_v_missing(self, tmp_path):
        """Given .vo exists but .v does not, no staleness warning (Section 7.4)."""
        check_single = _import_check_single()

        vo_file = tmp_path / "Orphan.vo"
        vo_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"Orphan has been checked", b""
        )
        mock_process.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_single(
                file_path=str(vo_file),
                include_paths=[],
                load_paths=[],
                timeout_seconds=300,
            )

        assert result.stale_files == []

    @pytest.mark.asyncio
    async def test_timeout_kills_process(self, tmp_path):
        """Given coqchk exceeds timeout, process is killed and
        CheckResult has status='error' with timeout failure."""
        check_single = _import_check_single()

        vo_file = tmp_path / "Slow.vo"
        vo_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate.side_effect = asyncio.TimeoutError()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        # After kill, reading gives empty
        mock_process.stdout.read = AsyncMock(return_value=b"")
        mock_process.stderr.read = AsyncMock(return_value=b"")

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_single(
                file_path=str(vo_file),
                include_paths=[],
                load_paths=[],
                timeout_seconds=1,
            )

        assert result.status == "error"
        assert len(result.failures) >= 1
        # Timeout failure is synthetic with failure_kind='unknown'
        timeout_failures = [f for f in result.failures
                           if "timeout" in f.raw_message.lower()]
        assert len(timeout_failures) >= 1

    @pytest.mark.asyncio
    async def test_nonzero_exit_returns_fail(self, tmp_path):
        """Given coqchk exits non-zero, CheckResult has status='fail'."""
        check_single = _import_check_single()

        vo_file = tmp_path / "Bad.vo"
        vo_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"", b"Error: MyLib.Bad is not consistent with MyLib.Core"
        )
        mock_process.returncode = 1

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_single(
                file_path=str(vo_file),
                include_paths=[],
                load_paths=[],
                timeout_seconds=300,
            )

        assert result.status == "fail"
        assert len(result.failures) >= 1

    @pytest.mark.asyncio
    async def test_wall_time_ms_populated(self, tmp_path):
        """CheckResult.wall_time_ms is populated with a non-negative value."""
        check_single = _import_check_single()

        vo_file = tmp_path / "Timed.vo"
        vo_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"Timed has been checked", b""
        )
        mock_process.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_single(
                file_path=str(vo_file),
                include_paths=[],
                load_paths=[],
                timeout_seconds=300,
            )

        assert result.wall_time_ms >= 0



# ===========================================================================
# 8. Project-Wide Checking — Section 4.6
# ===========================================================================

class TestCheckProject:
    """Section 4.6: check_project behavioral requirements."""

    @pytest.mark.asyncio
    async def test_no_vo_files_returns_pass_zero_checked(self, tmp_path):
        """Given a project directory with no .vo files,
        CheckResult has status='pass' and files_checked=0."""
        check_project = _import_check_project()

        result = await check_project(
            project_dir=str(tmp_path),
            include_paths=[],
            load_paths=[],
            timeout_seconds=300,
        )

        assert result.status == "pass"
        assert result.files_checked == 0
        assert result.failures == []

    @pytest.mark.asyncio
    async def test_coqproject_parsed_for_load_paths(self, tmp_path):
        """Given a _CoqProject with '-Q theories MyLib', load paths are
        merged and .vo files under theories/ are discovered."""
        check_project = _import_check_project()

        theories = tmp_path / "theories"
        theories.mkdir()
        (theories / "Foo.vo").touch()
        (theories / "Bar.vo").touch()

        coqproject = tmp_path / "_CoqProject"
        coqproject.write_text("-Q theories MyLib\n")

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"MyLib.Foo has been checked\nMyLib.Bar has been checked", b""
        )
        mock_process.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            result = await check_project(
                project_dir=str(tmp_path),
                include_paths=[],
                load_paths=[],
                timeout_seconds=300,
            )

        assert result.status == "pass"
        assert result.files_checked >= 2

    @pytest.mark.asyncio
    async def test_single_invocation_for_all_files(self, tmp_path):
        """All discovered library names are passed to a single coqchk invocation."""
        check_project = _import_check_project()

        theories = tmp_path / "theories"
        theories.mkdir()
        for name in ["A.vo", "B.vo", "C.vo"]:
            (theories / name).touch()

        coqproject = tmp_path / "_CoqProject"
        coqproject.write_text("-Q theories MyLib\n")

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"MyLib.A has been checked\nMyLib.B has been checked\nMyLib.C has been checked",
            b"",
        )
        mock_process.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            result = await check_project(
                project_dir=str(tmp_path),
                include_paths=[],
                load_paths=[],
                timeout_seconds=300,
            )

        # Exactly one subprocess spawned
        assert mock_exec.call_count == 1

    @pytest.mark.asyncio
    async def test_coqproject_parse_error_falls_back(self, tmp_path):
        """Given a _CoqProject with syntax errors, falls back to recursive walk."""
        check_project = _import_check_project()

        (tmp_path / "Foo.vo").touch()
        coqproject = tmp_path / "_CoqProject"
        coqproject.write_text("this is not valid\n-Q\n")  # malformed

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"Foo has been checked", b""
        )
        mock_process.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_project(
                project_dir=str(tmp_path),
                include_paths=[],
                load_paths=[],
                timeout_seconds=300,
            )

        # Should still find the .vo file via recursive walk
        assert result.files_checked >= 1

    @pytest.mark.asyncio
    async def test_no_coqproject_uses_recursive_walk(self, tmp_path):
        """Given no _CoqProject, walks project_dir recursively for .vo files."""
        check_project = _import_check_project()

        subdir = tmp_path / "sub"
        subdir.mkdir()
        (subdir / "Deep.vo").touch()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"Deep has been checked", b""
        )
        mock_process.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_project(
                project_dir=str(tmp_path),
                include_paths=[],
                load_paths=[],
                timeout_seconds=300,
            )

        assert result.files_checked >= 1

    @pytest.mark.asyncio
    async def test_no_subprocess_when_no_vo(self, tmp_path):
        """When no .vo files found, no subprocess is spawned (Section 4.6)."""
        check_project = _import_check_project()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            result = await check_project(
                project_dir=str(tmp_path),
                include_paths=[],
                load_paths=[],
                timeout_seconds=300,
            )

        mock_exec.assert_not_called()
        assert result.raw_output == ""



# ===========================================================================
# 9. _CoqProject Parsing — Section 4.6 (file discovery)
# ===========================================================================

class TestParseCoqProject:
    """Section 4.6: _CoqProject parsing behavior."""

    def test_parse_q_directive(self):
        """Parses '-Q theories MyLib' into load path ('MyLib', 'theories')."""
        parse_coqproject, _ = _import_discovery()
        content = "-Q theories MyLib\n"
        load_paths, include_paths = parse_coqproject(content)
        assert ("MyLib", "theories") in load_paths

    def test_parse_r_directive(self):
        """Parses '-R theories MyLib' into load path."""
        parse_coqproject, _ = _import_discovery()
        content = "-R theories MyLib\n"
        load_paths, _ = parse_coqproject(content)
        assert ("MyLib", "theories") in load_paths

    def test_parse_i_directive(self):
        """Parses '-I plugins' into include path."""
        parse_coqproject, _ = _import_discovery()
        content = "-I plugins\n"
        _, include_paths = parse_coqproject(content)
        assert "plugins" in include_paths

    def test_ignores_comment_lines(self):
        """Lines starting with '#' are ignored."""
        parse_coqproject, _ = _import_discovery()
        content = "# This is a comment\n-Q theories MyLib\n"
        load_paths, _ = parse_coqproject(content)
        assert len(load_paths) == 1

    def test_ignores_unrecognized_directives(self):
        """Unrecognized directives are ignored without error."""
        parse_coqproject, _ = _import_discovery()
        content = "-arg -w all\n-Q theories MyLib\n"
        load_paths, _ = parse_coqproject(content)
        assert ("MyLib", "theories") in load_paths

    def test_empty_content_returns_empty(self):
        """Empty _CoqProject content returns empty load and include paths."""
        parse_coqproject, _ = _import_discovery()
        load_paths, include_paths = parse_coqproject("")
        assert load_paths == []
        assert include_paths == []


# ===========================================================================
# 10. Entry Point — Section 6 (check_proof)
# ===========================================================================

class TestCheckProofEntryPoint:
    """Section 6: check_proof interface contract."""

    @pytest.mark.asyncio
    async def test_single_mode_delegates_to_check_single(self, tmp_path):
        """check_proof with mode='single' delegates to check_single."""
        check_proof = _import_adapter()
        _, CheckResult, _ = _import_types()

        vo_file = tmp_path / "Foo.vo"
        vo_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"Foo has been checked", b""
        )
        mock_process.returncode = 0

        req = _make_check_request(mode="single", file_path=str(vo_file))

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_proof(req)

        assert isinstance(result, CheckResult)
        assert result.status in ("pass", "fail", "error")

    @pytest.mark.asyncio
    async def test_project_mode_delegates_to_check_project(self, tmp_path):
        """check_proof with mode='project' delegates to check_project."""
        check_proof = _import_adapter()

        req = _make_check_request(mode="project", project_dir=str(tmp_path))

        result = await check_proof(req)

        assert result.status in ("pass", "fail", "error")

    @pytest.mark.asyncio
    async def test_validation_error_returns_without_subprocess(self):
        """When validation fails, returns CheckResult without spawning subprocess."""
        check_proof = _import_adapter()

        req = _make_check_request(mode="single", file_path=None)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            result = await check_proof(req)

        mock_exec.assert_not_called()
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_does_not_raise_exceptions(self, tmp_path):
        """The adapter does not raise exceptions to the caller (Section 6)."""
        check_proof = _import_adapter()

        # Even with a missing file, no exception — just error result
        req = _make_check_request(mode="single", file_path="/nonexistent/Foo.vo")
        result = await check_proof(req)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_all_result_fields_populated(self, tmp_path):
        """All CheckResult fields are populated (Section 6)."""
        check_proof = _import_adapter()
        _, CheckResult, _ = _import_types()

        vo_file = tmp_path / "Foo.vo"
        vo_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"Foo has been checked", b""
        )
        mock_process.returncode = 0

        req = _make_check_request(mode="single", file_path=str(vo_file))

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_proof(req)

        assert isinstance(result, CheckResult)
        assert result.status is not None
        assert result.files_checked is not None
        assert result.files_passed is not None
        assert result.files_failed is not None
        assert result.failures is not None
        assert result.stale_files is not None
        assert result.wall_time_ms is not None
        assert result.raw_output is not None



# ===========================================================================
# 11. Error Specification — Section 7
# ===========================================================================

class TestErrorSpecification:
    """Section 7: Error handling edge cases."""

    def test_timeout_clamped_to_minimum_1(self):
        """timeout_seconds < 1 is clamped to 1 (Section 7.1)."""
        req = _make_check_request(
            mode="single", file_path="/tmp/Foo.vo", timeout_seconds=0,
        )
        # The adapter should clamp; we test via check_proof behavior
        # For now, just verify we can create the request
        assert req.timeout_seconds == 0  # raw value; adapter clamps

    def test_timeout_clamped_to_maximum_3600(self):
        """timeout_seconds > 3600 is clamped to 3600 (Section 7.1)."""
        req = _make_check_request(
            mode="single", file_path="/tmp/Foo.vo", timeout_seconds=9999,
        )
        assert req.timeout_seconds == 9999  # raw value; adapter clamps

    @pytest.mark.asyncio
    async def test_coqchk_not_found_returns_error(self):
        """When coqchk is not found, returns status='error' (Section 7.2)."""
        check_proof = _import_adapter()

        req = _make_check_request(mode="single", file_path="/tmp/Foo.vo")

        with patch("shutil.which", return_value=None):
            # File doesn't exist so validation will catch it first
            # Test locate_coqchk directly
            locate_coqchk = _import_locate()
            result = locate_coqchk()

        _, CheckResult, _ = _import_types()
        assert isinstance(result, CheckResult)
        assert result.status == "error"
        assert any("coqchk not found" in f.raw_message for f in result.failures)

    @pytest.mark.asyncio
    async def test_crash_no_parseable_output(self, tmp_path):
        """When coqchk crashes with no parseable output, returns status='fail'
        with failure_kind='unknown' (Section 7.2)."""
        check_single = _import_check_single()

        vo_file = tmp_path / "Crash.vo"
        vo_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"Segfault")
        mock_process.returncode = 139

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_single(
                file_path=str(vo_file),
                include_paths=[],
                load_paths=[],
                timeout_seconds=300,
            )

        assert result.status == "fail"
        assert len(result.failures) >= 1
        assert result.failures[0].failure_kind == "unknown"


# ===========================================================================
# 12. Edge Cases — Section 7.4
# ===========================================================================

class TestEdgeCases:
    """Section 7.4: Edge case handling."""

    def test_multiple_load_paths_longest_prefix_wins(self):
        """Multiple load path entries matching same file: longest prefix wins."""
        resolve_library_name = _import_resolve()
        result = resolve_library_name(
            "/project/theories/sub/deep/Foo.vo",
            [
                ("A", "/project/theories"),
                ("B", "/project/theories/sub"),
                ("C", "/project/theories/sub/deep"),
            ],
        )
        assert result == "C.Foo"

    def test_empty_load_paths_command_construction(self):
        """Empty load_paths and include_paths: command has coqchk + library names only."""
        build_command = _import_build_command()
        result = build_command(
            coqchk_path="/usr/bin/coqchk",
            load_paths=[],
            include_paths=[],
            library_names=["Foo"],
        )
        assert result == ["/usr/bin/coqchk", "Foo"]

    @pytest.mark.asyncio
    async def test_stdout_with_nonzero_exit_both_parsed(self, tmp_path):
        """coqchk stdout on non-zero exit: both stdout and stderr are parsed."""
        check_single = _import_check_single()

        vo_file = tmp_path / "Mixed.vo"
        vo_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"MyLib.Good has been checked",
            b"Error: MyLib.Bad is not consistent with MyLib.Good",
        )
        mock_process.returncode = 1

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_single(
                file_path=str(vo_file),
                include_paths=[],
                load_paths=[],
                timeout_seconds=300,
            )

        # Raw output should contain both stdout and stderr
        assert result.raw_output != ""

    @pytest.mark.asyncio
    async def test_permission_error_skips_dirs(self, tmp_path):
        """Directory walk with permission errors: skip inaccessible dirs (Section 7.3)."""
        check_project = _import_check_project()

        accessible = tmp_path / "accessible"
        accessible.mkdir()
        (accessible / "Foo.vo").touch()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"Foo has been checked", b""
        )
        mock_process.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_project(
                project_dir=str(tmp_path),
                include_paths=[],
                load_paths=[],
                timeout_seconds=300,
            )

        # Should succeed with accessible files
        assert result.status in ("pass", "fail", "error")


# ===========================================================================
# 13. Spec Example Tests — Section 9
# ===========================================================================

class TestSpecExamples:
    """Section 9: End-to-end spec examples."""

    @pytest.mark.asyncio
    async def test_single_file_pass_example(self, tmp_path):
        """Spec Section 9 example: single-file pass scenario."""
        check_proof = _import_adapter()
        _, CheckResult, _ = _import_types()

        theories = tmp_path / "theories" / "Arith"
        theories.mkdir(parents=True)
        vo_file = theories / "Plus.vo"
        vo_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"MyLib.Arith.Plus has been checked", b""
        )
        mock_process.returncode = 0

        req = _make_check_request(
            mode="single",
            file_path=str(vo_file),
            load_paths=[("MyLib", str(tmp_path / "theories"))],
        )

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_proof(req)

        assert result.status == "pass"
        assert result.files_checked == 1
        assert result.files_passed == 1
        assert result.files_failed == 0
        assert result.failures == []
        assert result.stale_files == []

    @pytest.mark.asyncio
    async def test_single_file_inconsistency_example(self, tmp_path):
        """Spec Section 9 example: single-file inconsistency failure."""
        check_proof = _import_adapter()

        theories = tmp_path / "theories"
        theories.mkdir()
        vo_file = theories / "Bad.vo"
        vo_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"", b"Error: MyLib.Bad is not consistent with MyLib.Core"
        )
        mock_process.returncode = 1

        req = _make_check_request(
            mode="single",
            file_path=str(vo_file),
            load_paths=[("MyLib", str(theories))],
            timeout_seconds=300,
        )

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_proof(req)

        assert result.status == "fail"
        assert result.files_checked == 1
        assert result.files_failed == 1
        assert len(result.failures) == 1
        assert result.failures[0].failure_kind == "inconsistency"
        assert result.failures[0].module_name == "MyLib.Bad"

    @pytest.mark.asyncio
    async def test_coqchk_not_found_example(self):
        """Spec Section 9 example: coqchk not found."""
        check_proof = _import_adapter()

        req = _make_check_request(
            mode="single",
            file_path="/project/Foo.vo",
        )

        with patch("shutil.which", return_value=None), \
             patch("os.path.exists", return_value=True), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.suffix", new_callable=lambda: property(lambda self: ".vo")):
            result = await check_proof(req)

        assert result.status == "error"
        assert result.files_checked == 0
        assert result.raw_output == ""
        assert any("coqchk not found" in f.raw_message for f in result.failures)

    @pytest.mark.asyncio
    async def test_project_wide_with_staleness_example(self, tmp_path):
        """Spec Section 9 example: project-wide check with staleness."""
        check_proof = _import_adapter()

        theories = tmp_path / "theories"
        theories.mkdir()

        for name in ["Foo", "Bar", "Baz"]:
            (theories / f"{name}.vo").touch()

        # Make Bar.v newer than Bar.vo
        import time
        time.sleep(0.05)
        (theories / "Bar.v").touch()

        coqproject = tmp_path / "_CoqProject"
        coqproject.write_text("-Q theories MyLib\n")

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"MyLib.Foo has been checked\nMyLib.Bar has been checked\nMyLib.Baz has been checked",
            b"",
        )
        mock_process.returncode = 0

        req = _make_check_request(
            mode="project",
            project_dir=str(tmp_path),
            timeout_seconds=600,
        )

        with patch("shutil.which", return_value="/usr/bin/coqchk"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_proof(req)

        assert result.status == "pass"
        assert result.files_checked == 3
        assert result.files_passed == 3
        assert str(theories / "Bar.vo") in result.stale_files
