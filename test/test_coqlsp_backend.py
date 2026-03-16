"""Tests for the coq-lsp JSON-RPC backend (specification/extraction.md §4.1).

Tests the LSP protocol implementation: Content-Length message framing,
initialization handshake, document lifecycle, Vernac-result parsing from
diagnostics, and error handling.

The CoqLspBackend communicates with ``coq-lsp`` over stdin/stdout using
LSP JSON-RPC (Content-Length framed).  Vernac commands are issued by
opening synthetic ``.v`` documents; results come back as
``textDocument/publishDiagnostics`` notifications.
"""

from __future__ import annotations

import io
import json
import os
import threading
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers: build LSP messages in wire format
# ---------------------------------------------------------------------------


def _encode_lsp(msg: dict) -> bytes:
    """Encode a JSON-RPC message with Content-Length header."""
    body = json.dumps(msg).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def _make_response(request_id: int, result: dict | None = None) -> dict:
    """Build a JSON-RPC response."""
    resp: dict = {"jsonrpc": "2.0", "id": request_id}
    if result is not None:
        resp["result"] = result
    else:
        resp["result"] = {}
    return resp


def _make_diagnostics_notification(
    uri: str, diagnostics: list[dict]
) -> dict:
    """Build a textDocument/publishDiagnostics notification."""
    return {
        "jsonrpc": "2.0",
        "method": "textDocument/publishDiagnostics",
        "params": {"uri": uri, "diagnostics": diagnostics},
    }


def _make_diagnostic(
    message: str,
    severity: int = 3,
    start_line: int = 0,
    start_char: int = 0,
    end_line: int = 0,
    end_char: int = 1,
) -> dict:
    """Build one LSP diagnostic.

    Severity: 1=Error, 2=Warning, 3=Information, 4=Hint.
    """
    return {
        "range": {
            "start": {"line": start_line, "character": start_char},
            "end": {"line": end_line, "character": end_char},
        },
        "severity": severity,
        "message": message,
    }


class FakeLspServer:
    """Simulates coq-lsp by feeding pre-scripted responses through a pipe.

    Usage::

        server = FakeLspServer(messages=[...])
        backend._proc = Mock()
        backend._proc.stdout = server.stdout
        backend._proc.stdin = server.stdin
        # Now backend._read_message() reads from server's pipe.
    """

    def __init__(self, messages: list[dict]) -> None:
        raw = b"".join(_encode_lsp(m) for m in messages)
        self.stdout = io.BytesIO(raw)
        self.stdin = io.BytesIO()

    def get_written_messages(self) -> list[dict]:
        """Parse all messages the backend wrote to stdin."""
        raw = self.stdin.getvalue()
        messages: list[dict] = []
        pos = 0
        while pos < len(raw):
            # Find Content-Length header
            header_end = raw.find(b"\r\n\r\n", pos)
            if header_end == -1:
                break
            header_block = raw[pos:header_end].decode("ascii")
            content_length = None
            for line in header_block.split("\r\n"):
                if line.lower().startswith("content-length:"):
                    content_length = int(line.split(":")[1].strip())
            assert content_length is not None
            body_start = header_end + 4
            body = raw[body_start : body_start + content_length]
            messages.append(json.loads(body))
            pos = body_start + content_length
        return messages


# ═══════════════════════════════════════════════════════════════════════════
# 1. LSP Message Framing
# ═══════════════════════════════════════════════════════════════════════════


class TestWriteMessage:
    """_write_message encodes JSON-RPC messages with Content-Length header."""

    def test_produces_content_length_header_and_json_body(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        output = io.BytesIO()
        backend._proc = Mock()
        backend._proc.stdin = output
        backend._proc.stdin.write = output.write
        backend._proc.stdin.flush = output.flush

        msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        backend._write_message(msg)

        raw = output.getvalue()
        header, body = raw.split(b"\r\n\r\n", 1)
        assert header.startswith(b"Content-Length: ")
        content_length = int(header.split(b": ")[1])
        assert content_length == len(body)
        assert json.loads(body) == msg

    def test_body_is_utf8_encoded(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        output = io.BytesIO()
        backend._proc = Mock()
        backend._proc.stdin = output
        backend._proc.stdin.write = output.write
        backend._proc.stdin.flush = output.flush

        # Unicode content
        msg = {"jsonrpc": "2.0", "id": 1, "method": "test", "params": {"text": "∀ n, n = n"}}
        backend._write_message(msg)

        raw = output.getvalue()
        header, body = raw.split(b"\r\n\r\n", 1)
        content_length = int(header.split(b": ")[1])
        # Content-Length counts bytes, not characters
        assert content_length == len(body)
        assert json.loads(body)["params"]["text"] == "∀ n, n = n"


class TestReadMessage:
    """_read_message decodes Content-Length framed JSON-RPC messages."""

    def test_parses_single_message(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        msg = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        raw = _encode_lsp(msg)

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.stdout = io.BytesIO(raw)

        result = backend._read_message()
        assert result == msg

    def test_handles_multiple_headers(self):
        """Reader handles Content-Type and other headers per LSP spec."""
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        msg = {"jsonrpc": "2.0", "id": 2, "result": {}}
        body = json.dumps(msg).encode("utf-8")
        raw = (
            f"Content-Length: {len(body)}\r\n"
            f"Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n"
            f"\r\n"
        ).encode("ascii") + body

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.stdout = io.BytesIO(raw)

        result = backend._read_message()
        assert result == msg

    def test_reads_two_consecutive_messages(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        msg1 = {"jsonrpc": "2.0", "id": 1, "result": {"a": 1}}
        msg2 = {"jsonrpc": "2.0", "id": 2, "result": {"b": 2}}
        raw = _encode_lsp(msg1) + _encode_lsp(msg2)

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.stdout = io.BytesIO(raw)

        assert backend._read_message() == msg1
        assert backend._read_message() == msg2

    def test_eof_raises_backend_crash_error(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend
        from wily_rooster.extraction.errors import BackendCrashError

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.stdout = io.BytesIO(b"")

        with pytest.raises(BackendCrashError):
            backend._read_message()


# ═══════════════════════════════════════════════════════════════════════════
# 2. Initialization Handshake
# ═══════════════════════════════════════════════════════════════════════════


class TestInitialization:
    """start() performs the LSP initialize/initialized handshake."""

    def test_start_sends_initialize_then_initialized(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        init_response = _make_response(1, {
            "capabilities": {},
            "serverInfo": {"name": "coq-lsp", "version": "0.2.2+9.1.1"},
        })

        server = FakeLspServer(messages=[init_response])

        with patch("subprocess.Popen") as mock_popen:
            proc = Mock()
            proc.stdin = server.stdin
            proc.stdout = server.stdout
            proc.stderr = io.BytesIO(b"")
            proc.poll.return_value = None
            mock_popen.return_value = proc

            backend = CoqLspBackend()
            backend.start()

        written = server.get_written_messages()
        # First message must be "initialize"
        assert written[0]["method"] == "initialize"
        assert "id" in written[0]
        # Second message must be "initialized" notification (no id)
        assert written[1]["method"] == "initialized"
        assert "id" not in written[1]

        backend.stop()

    def test_start_passes_process_id(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        init_response = _make_response(1, {
            "capabilities": {},
            "serverInfo": {"name": "coq-lsp", "version": "0.2.2+9.1.1"},
        })
        server = FakeLspServer(messages=[init_response])

        with patch("subprocess.Popen") as mock_popen:
            proc = Mock()
            proc.stdin = server.stdin
            proc.stdout = server.stdout
            proc.stderr = io.BytesIO(b"")
            proc.poll.return_value = None
            mock_popen.return_value = proc

            backend = CoqLspBackend()
            backend.start()

        written = server.get_written_messages()
        assert written[0]["params"]["processId"] == os.getpid()

        backend.stop()

    def test_start_spawns_coq_lsp_subprocess(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        init_response = _make_response(1, {
            "capabilities": {},
            "serverInfo": {"name": "coq-lsp", "version": "0.2.2+9.1.1"},
        })
        server = FakeLspServer(messages=[init_response])

        with patch("subprocess.Popen") as mock_popen:
            proc = Mock()
            proc.stdin = server.stdin
            proc.stdout = server.stdout
            proc.stderr = io.BytesIO(b"")
            proc.poll.return_value = None
            mock_popen.return_value = proc

            backend = CoqLspBackend()
            backend.start()

        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert "coq-lsp" in cmd[0]

        backend.stop()


# ═══════════════════════════════════════════════════════════════════════════
# 3. Version Detection
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectVersion:
    """detect_version() returns the Coq/Rocq version string."""

    def test_returns_version_from_server_info(self):
        """Version is extracted from the initialize response serverInfo."""
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        init_response = _make_response(1, {
            "capabilities": {},
            "serverInfo": {"name": "coq-lsp", "version": "0.2.2+9.1.1"},
        })
        server = FakeLspServer(messages=[init_response])

        with patch("subprocess.Popen") as mock_popen:
            proc = Mock()
            proc.stdin = server.stdin
            proc.stdout = server.stdout
            proc.stderr = io.BytesIO(b"")
            proc.poll.return_value = None
            mock_popen.return_value = proc

            backend = CoqLspBackend()
            backend.start()

        version = backend.detect_version()
        # Should extract "9.1.1" from "0.2.2+9.1.1"
        assert "9.1" in version

        backend.stop()

    def test_fallback_to_coqc_version(self):
        """When serverInfo has no Coq version, falls back to coqc --version."""
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        init_response = _make_response(1, {
            "capabilities": {},
            "serverInfo": {"name": "coq-lsp", "version": "0.2.2"},
        })
        server = FakeLspServer(messages=[init_response])

        with patch("subprocess.Popen") as mock_popen:
            proc = Mock()
            proc.stdin = server.stdin
            proc.stdout = server.stdout
            proc.stderr = io.BytesIO(b"")
            proc.poll.return_value = None
            mock_popen.return_value = proc

            backend = CoqLspBackend()
            backend.start()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                stdout="The Rocq Prover, version 9.1.1\n", returncode=0
            )
            version = backend.detect_version()

        assert "9.1" in version

        backend.stop()


# ═══════════════════════════════════════════════════════════════════════════
# 4. Document Lifecycle
# ═══════════════════════════════════════════════════════════════════════════


class TestDocumentLifecycle:
    """Backend opens/closes synthetic .v documents for Vernac queries."""

    def test_open_document_sends_did_open_notification(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        server = FakeLspServer(messages=[])
        backend._proc = Mock()
        backend._proc.stdin = server.stdin
        backend._proc.stdin.write = server.stdin.write
        backend._proc.stdin.flush = server.stdin.flush
        backend._proc.poll.return_value = None

        uri = "file:///tmp/wily_query_1.v"
        text = "Check True."
        backend._open_document(uri, text)

        written = server.get_written_messages()
        assert len(written) == 1
        assert written[0]["method"] == "textDocument/didOpen"
        doc = written[0]["params"]["textDocument"]
        assert doc["uri"] == uri
        assert doc["languageId"] == "coq"
        assert doc["text"] == text

    def test_close_document_sends_did_close_notification(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        server = FakeLspServer(messages=[])
        backend._proc = Mock()
        backend._proc.stdin = server.stdin
        backend._proc.stdin.write = server.stdin.write
        backend._proc.stdin.flush = server.stdin.flush
        backend._proc.poll.return_value = None

        uri = "file:///tmp/wily_query_1.v"
        backend._close_document(uri)

        written = server.get_written_messages()
        assert len(written) == 1
        assert written[0]["method"] == "textDocument/didClose"
        assert written[0]["params"]["textDocument"]["uri"] == uri


# ═══════════════════════════════════════════════════════════════════════════
# 5. Waiting for Diagnostics
# ═══════════════════════════════════════════════════════════════════════════


class TestWaitForDiagnostics:
    """_wait_for_diagnostics collects publishDiagnostics for a URI."""

    def test_collects_diagnostics_matching_uri(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        uri = "file:///tmp/wily_query_1.v"
        diag = _make_diagnostic("nat : Set", severity=3, start_line=1)
        notification = _make_diagnostics_notification(uri, [diag])

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.stdout = io.BytesIO(_encode_lsp(notification))
        backend._proc.poll.return_value = None
        backend._notification_buffer = []

        result = backend._wait_for_diagnostics(uri)
        assert len(result) == 1
        assert result[0]["message"] == "nat : Set"

    def test_ignores_diagnostics_for_other_uris(self):
        """Diagnostics for other documents are buffered, not returned."""
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        target_uri = "file:///tmp/wily_query_1.v"
        other_uri = "file:///tmp/other.v"

        other_notif = _make_diagnostics_notification(
            other_uri, [_make_diagnostic("irrelevant")]
        )
        target_notif = _make_diagnostics_notification(
            target_uri, [_make_diagnostic("relevant result")]
        )

        backend = CoqLspBackend.__new__(CoqLspBackend)
        raw = _encode_lsp(other_notif) + _encode_lsp(target_notif)
        backend._proc = Mock()
        backend._proc.stdout = io.BytesIO(raw)
        backend._proc.poll.return_value = None
        backend._notification_buffer = []

        result = backend._wait_for_diagnostics(target_uri)
        assert len(result) == 1
        assert result[0]["message"] == "relevant result"

    def test_buffers_interleaved_notifications(self):
        """Server responses (to other requests) are buffered while waiting."""
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        target_uri = "file:///tmp/wily_query_1.v"
        # An unrelated response arrives before our diagnostics
        unrelated = {"jsonrpc": "2.0", "method": "$/progress", "params": {"token": 1}}
        target_notif = _make_diagnostics_notification(
            target_uri, [_make_diagnostic("result")]
        )

        backend = CoqLspBackend.__new__(CoqLspBackend)
        raw = _encode_lsp(unrelated) + _encode_lsp(target_notif)
        backend._proc = Mock()
        backend._proc.stdout = io.BytesIO(raw)
        backend._proc.poll.return_value = None
        backend._notification_buffer = []

        result = backend._wait_for_diagnostics(target_uri)
        assert len(result) == 1
        assert result[0]["message"] == "result"


# ═══════════════════════════════════════════════════════════════════════════
# 6. list_declarations
# ═══════════════════════════════════════════════════════════════════════════


class TestListDeclarations:
    """list_declarations extracts (name, kind, constr_t) from a .vo file."""

    def test_returns_name_kind_constr_tuples(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.poll.return_value = None
        backend._server_info = {}
        backend._notification_buffer = []

        # Simulate: open doc → diagnostics with Search results → close doc
        search_results = [
            _make_diagnostic("Nat.add : nat -> nat -> nat", severity=3, start_line=1),
            _make_diagnostic("Nat.mul : nat -> nat -> nat", severity=3, start_line=1),
        ]
        # About results for kind detection
        about_results_add = [
            _make_diagnostic("Nat.add is a definition", severity=3),
        ]
        about_results_mul = [
            _make_diagnostic("Nat.mul is a definition", severity=3),
        ]

        with (
            patch.object(backend, "_open_document"),
            patch.object(backend, "_close_document"),
            patch.object(
                backend,
                "_wait_for_diagnostics",
                side_effect=[search_results, about_results_add, about_results_mul],
            ),
        ):
            result = backend.list_declarations(
                Path("/coq/theories/Init/Nat.vo")
            )

        assert isinstance(result, list)
        assert len(result) == 2
        # Each entry is (name, kind, constr_t)
        names = {r[0] for r in result}
        assert "Nat.add" in names or any("add" in r[0] for r in result)
        assert all(len(r) == 3 for r in result)

    def test_opens_document_with_require_and_search(self):
        """The synthetic doc must Require the module then Search inside it."""
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.poll.return_value = None
        backend._server_info = {}
        backend._notification_buffer = []
        backend._next_uri_id = 0

        opened_docs: list[tuple[str, str]] = []

        def capture_open(uri, text):
            opened_docs.append((uri, text))

        with (
            patch.object(backend, "_open_document", side_effect=capture_open),
            patch.object(backend, "_close_document"),
            patch.object(
                backend, "_wait_for_diagnostics", return_value=[]
            ),
        ):
            backend.list_declarations(Path("/coq/theories/Init/Nat.vo"))

        # At least one document must contain both Require and Search
        assert len(opened_docs) >= 1
        search_doc = opened_docs[0][1]
        assert "Require" in search_doc
        assert "Search" in search_doc

    def test_empty_module_returns_empty_list(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.poll.return_value = None
        backend._server_info = {}
        backend._notification_buffer = []
        backend._next_uri_id = 0

        with (
            patch.object(backend, "_open_document"),
            patch.object(backend, "_close_document"),
            patch.object(
                backend, "_wait_for_diagnostics", return_value=[]
            ),
        ):
            result = backend.list_declarations(Path("/coq/theories/Empty.vo"))

        assert result == []

    def test_error_diagnostics_for_require_returns_empty(self):
        """If Require Import fails, return empty list (don't crash)."""
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.poll.return_value = None
        backend._server_info = {}
        backend._notification_buffer = []
        backend._next_uri_id = 0

        # Error diagnostic (severity 1 = Error)
        error_diags = [
            _make_diagnostic(
                "Cannot find a physical path bound to logical path Init.Nonexistent.",
                severity=1,
            ),
        ]

        with (
            patch.object(backend, "_open_document"),
            patch.object(backend, "_close_document"),
            patch.object(
                backend, "_wait_for_diagnostics", return_value=error_diags
            ),
        ):
            result = backend.list_declarations(
                Path("/coq/theories/Init/Nonexistent.vo")
            )

        assert result == []


# ═══════════════════════════════════════════════════════════════════════════
# 7. Parsing Search Output from Diagnostics
# ═══════════════════════════════════════════════════════════════════════════


class TestParseSearchDiagnostics:
    """_parse_search_diagnostics extracts declaration names from Search output."""

    def test_parses_name_colon_type_lines(self):
        """Search output lines are 'name : type_sig'."""
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        diags = [
            _make_diagnostic("Nat.add : nat -> nat -> nat"),
            _make_diagnostic("Nat.add_comm : forall n m, n + m = m + n"),
        ]

        result = CoqLspBackend._parse_search_diagnostics(diags)
        assert len(result) == 2
        assert result[0][0] == "Nat.add"
        assert result[0][1] == "nat -> nat -> nat"
        assert result[1][0] == "Nat.add_comm"

    def test_skips_error_diagnostics(self):
        """Error diagnostics (severity 1) are not search results."""
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        diags = [
            _make_diagnostic("Nat.add : nat -> nat -> nat", severity=3),
            _make_diagnostic("Error: something broke", severity=1),
        ]

        result = CoqLspBackend._parse_search_diagnostics(diags)
        assert len(result) == 1

    def test_empty_diagnostics_returns_empty(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        result = CoqLspBackend._parse_search_diagnostics([])
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════
# 8. pretty_print
# ═══════════════════════════════════════════════════════════════════════════


class TestPrettyPrint:
    """pretty_print returns human-readable statement for a declaration."""

    def test_returns_print_output(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.poll.return_value = None
        backend._server_info = {}
        backend._notification_buffer = []
        backend._next_uri_id = 0

        print_diags = [
            _make_diagnostic(
                "Nat.add =\nfix add (n m : nat) {struct n} : nat :=\n"
                "  match n with\n  | 0 => m\n  | S p => S (add p m)\n  end",
                severity=3,
            ),
        ]

        with (
            patch.object(backend, "_open_document"),
            patch.object(backend, "_close_document"),
            patch.object(
                backend, "_wait_for_diagnostics", return_value=print_diags
            ),
        ):
            result = backend.pretty_print("Nat.add")

        assert "Nat.add" in result
        assert isinstance(result, str)

    def test_opens_document_with_print_command(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.poll.return_value = None
        backend._server_info = {}
        backend._notification_buffer = []
        backend._next_uri_id = 0

        opened_docs: list[str] = []

        def capture_open(uri, text):
            opened_docs.append(text)

        with (
            patch.object(backend, "_open_document", side_effect=capture_open),
            patch.object(backend, "_close_document"),
            patch.object(backend, "_wait_for_diagnostics", return_value=[]),
        ):
            backend.pretty_print("Nat.add")

        assert any("Print Nat.add" in doc for doc in opened_docs)


# ═══════════════════════════════════════════════════════════════════════════
# 9. pretty_print_type
# ═══════════════════════════════════════════════════════════════════════════


class TestPrettyPrintType:
    """pretty_print_type returns the type signature or None."""

    def test_returns_type_from_check_output(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.poll.return_value = None
        backend._server_info = {}
        backend._notification_buffer = []
        backend._next_uri_id = 0

        check_diags = [
            _make_diagnostic("Nat.add\n     : nat -> nat -> nat", severity=3),
        ]

        with (
            patch.object(backend, "_open_document"),
            patch.object(backend, "_close_document"),
            patch.object(
                backend, "_wait_for_diagnostics", return_value=check_diags
            ),
        ):
            result = backend.pretty_print_type("Nat.add")

        assert result is not None
        assert "nat" in result

    def test_returns_none_on_error(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.poll.return_value = None
        backend._server_info = {}
        backend._notification_buffer = []
        backend._next_uri_id = 0

        error_diags = [
            _make_diagnostic("Error: Unknown reference Nonexistent", severity=1),
        ]

        with (
            patch.object(backend, "_open_document"),
            patch.object(backend, "_close_document"),
            patch.object(
                backend, "_wait_for_diagnostics", return_value=error_diags
            ),
        ):
            result = backend.pretty_print_type("Nonexistent")

        assert result is None

    def test_opens_document_with_check_command(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.poll.return_value = None
        backend._server_info = {}
        backend._notification_buffer = []
        backend._next_uri_id = 0

        opened_docs: list[str] = []

        def capture_open(uri, text):
            opened_docs.append(text)

        with (
            patch.object(backend, "_open_document", side_effect=capture_open),
            patch.object(backend, "_close_document"),
            patch.object(backend, "_wait_for_diagnostics", return_value=[]),
        ):
            backend.pretty_print_type("Nat.add")

        assert any("Check Nat.add" in doc for doc in opened_docs)


# ═══════════════════════════════════════════════════════════════════════════
# 10. get_dependencies
# ═══════════════════════════════════════════════════════════════════════════


class TestGetDependencies:
    """get_dependencies returns (target_name, relation) pairs."""

    def test_parses_print_assumptions_output(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.poll.return_value = None
        backend._server_info = {}
        backend._notification_buffer = []
        backend._next_uri_id = 0

        assumption_diags = [
            _make_diagnostic(
                "Coq.Init.Logic.eq_refl : forall (A : Type) (x : A), x = x\n"
                "Coq.Init.Peano.nat_ind : forall P, P 0 -> ...",
                severity=3,
            ),
        ]

        with (
            patch.object(backend, "_open_document"),
            patch.object(backend, "_close_document"),
            patch.object(
                backend, "_wait_for_diagnostics", return_value=assumption_diags
            ),
        ):
            result = backend.get_dependencies("Nat.add_comm")

        assert isinstance(result, list)
        assert len(result) >= 1
        assert all(isinstance(r, tuple) and len(r) == 2 for r in result)

    def test_closed_under_global_context_returns_empty(self):
        """Declarations with no axioms return empty dependency list."""
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.poll.return_value = None
        backend._server_info = {}
        backend._notification_buffer = []
        backend._next_uri_id = 0

        closed_diags = [
            _make_diagnostic("Closed under the global context", severity=3),
        ]

        with (
            patch.object(backend, "_open_document"),
            patch.object(backend, "_close_document"),
            patch.object(
                backend, "_wait_for_diagnostics", return_value=closed_diags
            ),
        ):
            result = backend.get_dependencies("Nat.add")

        assert result == []

    def test_opens_document_with_print_assumptions(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.poll.return_value = None
        backend._server_info = {}
        backend._notification_buffer = []
        backend._next_uri_id = 0

        opened_docs: list[str] = []

        def capture_open(uri, text):
            opened_docs.append(text)

        with (
            patch.object(backend, "_open_document", side_effect=capture_open),
            patch.object(backend, "_close_document"),
            patch.object(backend, "_wait_for_diagnostics", return_value=[]),
        ):
            backend.get_dependencies("Nat.add")

        assert any("Print Assumptions Nat.add" in doc for doc in opened_docs)


# ═══════════════════════════════════════════════════════════════════════════
# 11. Module Path Derivation
# ═══════════════════════════════════════════════════════════════════════════


class TestVoToLogicalPath:
    """_vo_to_logical_path derives Coq module path from .vo file path."""

    def test_stdlib_path(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        path = Path("/home/user/.opam/default/lib/coq/theories/Init/Nat.vo")
        result = CoqLspBackend._vo_to_logical_path(path)
        assert result == "Init.Nat"

    def test_mathcomp_path(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        path = Path(
            "/home/user/.opam/default/lib/coq/user-contrib/mathcomp/ssreflect/ssrnat.vo"
        )
        result = CoqLspBackend._vo_to_logical_path(path)
        assert result == "mathcomp.ssreflect.ssrnat"

    def test_nested_stdlib_path(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        path = Path(
            "/coq/theories/Arith/PeanoNat.vo"
        )
        result = CoqLspBackend._vo_to_logical_path(path)
        assert result == "Arith.PeanoNat"


# ═══════════════════════════════════════════════════════════════════════════
# 12. Error Handling
# ═══════════════════════════════════════════════════════════════════════════


class TestBackendErrors:
    """Error handling for coq-lsp subprocess failures."""

    def test_start_raises_extraction_error_when_coq_lsp_not_found(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend
        from wily_rooster.extraction.errors import ExtractionError

        with patch("subprocess.Popen", side_effect=FileNotFoundError("coq-lsp not found")):
            backend = CoqLspBackend()
            with pytest.raises(ExtractionError):
                backend.start()

    def test_process_exit_raises_backend_crash_error(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend
        from wily_rooster.extraction.errors import BackendCrashError

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.poll.return_value = 1  # exited
        backend._proc.returncode = 1
        backend._proc.stderr = io.BytesIO(b"segfault")

        with pytest.raises(BackendCrashError):
            backend._ensure_alive()

    def test_json_rpc_error_response_raises_extraction_error(self):
        """A JSON-RPC error response is converted to ExtractionError."""
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend
        from wily_rooster.extraction.errors import ExtractionError

        error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32600, "message": "Invalid Request"},
        }

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = Mock()
        backend._proc.stdout = io.BytesIO(_encode_lsp(error_response))
        backend._proc.poll.return_value = None
        backend._notification_buffer = []

        with pytest.raises(ExtractionError, match="Invalid Request"):
            backend._send_request("badMethod", {})


# ═══════════════════════════════════════════════════════════════════════════
# 13. Lifecycle
# ═══════════════════════════════════════════════════════════════════════════


class TestLifecycle:
    """start/stop lifecycle and context manager support."""

    def test_stop_sends_shutdown_then_exit(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        # Prepare server: respond to shutdown request
        shutdown_response = _make_response(1, None)
        server = FakeLspServer(messages=[shutdown_response])

        backend._proc = Mock()
        backend._proc.stdin = server.stdin
        backend._proc.stdin.write = server.stdin.write
        backend._proc.stdin.flush = server.stdin.flush
        backend._proc.stdout = server.stdout
        backend._proc.poll.return_value = None
        backend._proc.wait.return_value = 0
        backend._next_id = 0
        backend._notification_buffer = []

        backend.stop()

        written = server.get_written_messages()
        methods = [m["method"] for m in written]
        assert "shutdown" in methods
        assert "exit" in methods
        # shutdown must come before exit
        assert methods.index("shutdown") < methods.index("exit")

    def test_context_manager_calls_start_and_stop(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        init_response = _make_response(1, {
            "capabilities": {},
            "serverInfo": {"name": "coq-lsp", "version": "0.2.2+9.1.1"},
        })
        shutdown_response = _make_response(2, None)
        server = FakeLspServer(messages=[init_response, shutdown_response])

        with patch("subprocess.Popen") as mock_popen:
            proc = Mock()
            proc.stdin = server.stdin
            proc.stdout = server.stdout
            proc.stderr = io.BytesIO(b"")
            proc.poll.return_value = None
            proc.wait.return_value = 0
            mock_popen.return_value = proc

            with CoqLspBackend() as backend:
                assert backend._proc is not None

        # After exiting context, stop should have been called
        written = server.get_written_messages()
        methods = [m["method"] for m in written]
        assert "initialize" in methods
        assert "shutdown" in methods

    def test_stop_on_already_stopped_is_noop(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        backend = CoqLspBackend.__new__(CoqLspBackend)
        backend._proc = None

        # Should not raise
        backend.stop()

    def test_double_start_is_idempotent(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        init_response = _make_response(1, {
            "capabilities": {},
            "serverInfo": {"name": "coq-lsp", "version": "0.2.2+9.1.1"},
        })
        server = FakeLspServer(messages=[init_response])

        with patch("subprocess.Popen") as mock_popen:
            proc = Mock()
            proc.stdin = server.stdin
            proc.stdout = server.stdout
            proc.stderr = io.BytesIO(b"")
            proc.poll.return_value = None
            mock_popen.return_value = proc

            backend = CoqLspBackend()
            backend.start()
            backend.start()  # should be a no-op

        # Popen called only once
        mock_popen.assert_called_once()
        backend.stop()


# ═══════════════════════════════════════════════════════════════════════════
# 14. CoqBackend Protocol Conformance
# ═══════════════════════════════════════════════════════════════════════════


class TestProtocolConformance:
    """CoqLspBackend satisfies the CoqBackend protocol."""

    def test_implements_coq_backend_protocol(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend
        from wily_rooster.extraction.coq_backend import CoqBackend

        assert issubclass(CoqLspBackend, CoqBackend) or (
            hasattr(CoqLspBackend, "list_declarations")
            and hasattr(CoqLspBackend, "pretty_print")
            and hasattr(CoqLspBackend, "pretty_print_type")
            and hasattr(CoqLspBackend, "get_dependencies")
            and hasattr(CoqLspBackend, "detect_version")
        )


# ═══════════════════════════════════════════════════════════════════════════
# 15. Contract Tests (require real coq-lsp installation)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.requires_coq
class TestContractListDeclarations:
    """Contract: real coq-lsp returns valid declarations for a .vo file."""

    def test_real_backend_list_declarations(self):
        import subprocess

        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        # Find a stdlib .vo file
        result = subprocess.run(
            ["coqc", "-where"], capture_output=True, text=True
        )
        coq_root = Path(result.stdout.strip())
        vo_file = next((coq_root / "theories" / "Init").glob("*.vo"), None)
        if vo_file is None:
            pytest.skip("No .vo files found in Coq stdlib")

        with CoqLspBackend() as backend:
            decls = backend.list_declarations(vo_file)

        assert isinstance(decls, list)
        if decls:
            assert all(len(d) == 3 for d in decls)
            assert all(isinstance(d[0], str) for d in decls)
            assert all(isinstance(d[1], str) for d in decls)


@pytest.mark.requires_coq
class TestContractDetectVersion:
    """Contract: real coq-lsp returns a version string."""

    def test_real_backend_detect_version(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        with CoqLspBackend() as backend:
            version = backend.detect_version()

        assert isinstance(version, str)
        assert len(version) > 0


@pytest.mark.requires_coq
class TestContractPrettyPrint:
    """Contract: real coq-lsp pretty-prints a known declaration."""

    def test_real_backend_pretty_print(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        with CoqLspBackend() as backend:
            result = backend.pretty_print("Coq.Init.Nat.add")

        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.requires_coq
class TestContractGetDependencies:
    """Contract: real coq-lsp returns dependencies for a known declaration."""

    def test_real_backend_get_dependencies(self):
        from wily_rooster.extraction.backends.coqlsp_backend import CoqLspBackend

        with CoqLspBackend() as backend:
            deps = backend.get_dependencies("Coq.Init.Nat.add")

        assert isinstance(deps, list)
        assert all(
            isinstance(d, tuple) and len(d) == 2 for d in deps
        )
