"""Opam version constraint parsing (spec section 4.3).

Recursive descent parser for the opam constraint grammar:
    expr     := and_expr ('|' and_expr)*
    and_expr := atom ('&' atom)*
    atom     := comparison
    comparison := op version
    op       := '>=' | '<=' | '>' | '<' | '=' | '!='
    version  := quoted_string
"""

from __future__ import annotations

import re
from typing import Optional

from Poule.compat.errors import CONSTRAINT_PARSE_ERROR, CompatError
from Poule.compat.types import VersionBound, VersionConstraint, VersionInterval

# Token patterns
_TOKEN_RE = re.compile(
    r"""
    \s*                      # skip whitespace
    (?:
      (>=|<=|!=|>|<|=)       # operator
    | (&)                    # AND
    | (\|)                   # OR
    | "([^"]*)"              # quoted version
    )
    """,
    re.VERBOSE,
)


class _Token:
    __slots__ = ("kind", "value")

    def __init__(self, kind: str, value: str) -> None:
        self.kind = kind
        self.value = value


def _tokenize(expression: str) -> list[_Token]:
    """Tokenize an opam constraint expression."""
    tokens: list[_Token] = []
    pos = 0
    while pos < len(expression):
        m = _TOKEN_RE.match(expression, pos)
        if m is None:
            # Skip whitespace
            if expression[pos].isspace():
                pos += 1
                continue
            raise CompatError(
                CONSTRAINT_PARSE_ERROR,
                f"Unexpected character at position {pos} in: {expression}",
            )
        if m.group(1):  # operator
            tokens.append(_Token("OP", m.group(1)))
        elif m.group(2):  # AND
            tokens.append(_Token("AND", "&"))
        elif m.group(3):  # OR
            tokens.append(_Token("OR", "|"))
        elif m.group(4) is not None:  # quoted version
            tokens.append(_Token("VERSION", m.group(4)))
        pos = m.end()
    return tokens


class _Parser:
    """Recursive descent parser for opam constraint expressions."""

    def __init__(self, tokens: list[_Token], raw: str) -> None:
        self._tokens = tokens
        self._pos = 0
        self._raw = raw

    def _peek(self) -> Optional[_Token]:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _advance(self) -> _Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, kind: str) -> _Token:
        tok = self._peek()
        if tok is None or tok.kind != kind:
            expected = kind
            got = tok.kind if tok else "end of input"
            raise CompatError(
                CONSTRAINT_PARSE_ERROR,
                f"Expected {expected}, got {got} in: {self._raw}",
            )
        return self._advance()

    def parse(self) -> VersionConstraint:
        """Parse the full expression into a VersionConstraint."""
        result = self._parse_or_expr()
        if self._pos < len(self._tokens):
            raise CompatError(
                CONSTRAINT_PARSE_ERROR,
                f"Unexpected token after expression in: {self._raw}",
            )
        return result

    def _parse_or_expr(self) -> VersionConstraint:
        """Parse: and_expr ('|' and_expr)*"""
        left = self._parse_and_expr()
        intervals = list(left.intervals)
        while self._peek() and self._peek().kind == "OR":
            self._advance()
            right = self._parse_and_expr()
            intervals.extend(right.intervals)
        return VersionConstraint(intervals=intervals)

    def _parse_and_expr(self) -> VersionConstraint:
        """Parse: atom ('&' atom)*"""
        left = self._parse_atom()
        while self._peek() and self._peek().kind == "AND":
            self._advance()
            right = self._parse_atom()
            # Intersect the two constraints
            left = _intersect_constraints(left, right)
        return left

    def _parse_atom(self) -> VersionConstraint:
        """Parse: op version"""
        op_tok = self._expect("OP")
        ver_tok = self._expect("VERSION")
        return _comparison_to_constraint(op_tok.value, ver_tok.value)


def _comparison_to_constraint(op: str, version: str) -> VersionConstraint:
    """Convert a single comparison (op, version) to a VersionConstraint."""
    if op == ">=":
        return VersionConstraint(intervals=[
            VersionInterval(lower=VersionBound(version, True), upper=None),
        ])
    elif op == ">":
        return VersionConstraint(intervals=[
            VersionInterval(lower=VersionBound(version, False), upper=None),
        ])
    elif op == "<=":
        return VersionConstraint(intervals=[
            VersionInterval(lower=None, upper=VersionBound(version, True)),
        ])
    elif op == "<":
        return VersionConstraint(intervals=[
            VersionInterval(lower=None, upper=VersionBound(version, False)),
        ])
    elif op == "=":
        return VersionConstraint(intervals=[
            VersionInterval(
                lower=VersionBound(version, True),
                upper=VersionBound(version, True),
            ),
        ])
    elif op == "!=":
        # != produces two intervals: (-inf, version) and (version, +inf)
        return VersionConstraint(intervals=[
            VersionInterval(lower=None, upper=VersionBound(version, False)),
            VersionInterval(lower=VersionBound(version, False), upper=None),
        ])
    else:
        raise CompatError(CONSTRAINT_PARSE_ERROR, f"Unknown operator: {op}")


def _intersect_constraints(a: VersionConstraint, b: VersionConstraint) -> VersionConstraint:
    """Intersect two constraints (used during AND parsing)."""
    from Poule.compat.versions import intersect
    return intersect(a, b)


def parse_constraint(expression: str) -> VersionConstraint:
    """Parse an opam version constraint expression into a VersionConstraint.

    REQUIRES: expression is a non-empty string.
    ENSURES: Returns a VersionConstraint in disjunctive normal form.
    MAINTAINS: Deterministic — same expression always produces same result.
    """
    try:
        tokens = _tokenize(expression)
        if not tokens:
            raise CompatError(
                CONSTRAINT_PARSE_ERROR,
                f"Empty constraint expression: {expression}",
            )
        parser = _Parser(tokens, expression)
        return parser.parse()
    except CompatError:
        raise
    except Exception as e:
        raise CompatError(
            CONSTRAINT_PARSE_ERROR,
            f"Failed to parse constraint: {expression}: {e}",
        ) from e
