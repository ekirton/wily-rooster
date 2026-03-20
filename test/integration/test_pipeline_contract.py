"""Contract tests for the query processing pipeline — requires real coq-lsp.

Extracted from test/unit/test_pipeline.py. These tests exercise real coq-lsp
to verify mock assumptions in the unit tests.
"""

from __future__ import annotations

import pytest

from Poule.pipeline.coqlsp_parser import CoqLspParser
from Poule.pipeline.parser import ParseError


class TestCoqLspParserContract:
    """Contract tests exercising real coq-lsp.

    These tests require coq-lsp to be installed and on PATH.
    Run with: pytest -m requires_coq

    coq-lsp returns text output (not structured Constr.t JSON) for
    ``Check`` commands via ``proof/goals``, so ``parse()`` raises
    ``ParseError`` for valid Coq expressions.  These tests verify the
    actual coq-lsp behavior.
    """

    def test_parse_valid_expression_raises_parse_error(self):
        """parse("nat") raises ParseError because coq-lsp returns text,
        not structured JSON (spec §4.2: on failure raises ParseError)."""
        parser = CoqLspParser()
        try:
            with pytest.raises(ParseError):
                parser.parse("nat")
        finally:
            parser.close()

    def test_parse_invalid_expression_raises(self):
        """Parse 'not_a_valid_coq_thing!!!' and verify ParseError."""
        parser = CoqLspParser()
        try:
            with pytest.raises(ParseError):
                parser.parse("not_a_valid_coq_thing!!!")
        finally:
            parser.close()

    def test_close_terminates_process(self):
        """Verify close() terminates the coq-lsp subprocess."""
        parser = CoqLspParser()
        # Trigger _ensure_started by attempting a parse (will raise ParseError
        # because coq-lsp returns text, not structured JSON — catch it)
        try:
            parser.parse("nat")
        except ParseError:
            pass

        # Process should be running
        assert parser._proc is not None
        proc = parser._proc

        parser.close()

        # After close, internal ref should be None
        assert parser._proc is None
        # The real process should have terminated
        assert proc.poll() is not None
