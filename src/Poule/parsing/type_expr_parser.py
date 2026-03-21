"""TypeExprParser — pure-Python parser for Coq type expression strings.

Converts textual type signatures (as returned by coq-lsp Search output)
into ConstrNode trees for structural indexing and query-time parsing.

Specification: specification/type-expr-parser.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from Poule.normalization.constr_node import (
    App,
    Const,
    Lambda,
    Prod,
    Rel,
    Sort,
)
from Poule.pipeline.parser import ParseError


# ---------------------------------------------------------------------------
# Token types
# ---------------------------------------------------------------------------


class TokenKind(Enum):
    IDENT = auto()
    NUMBER = auto()
    SORT = auto()
    FORALL = auto()
    FUN = auto()
    ARROW = auto()
    DARROW = auto()
    COLON = auto()
    COMMA = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    PIPE = auto()
    UNDERSCORE = auto()
    INFIX_OP = auto()
    EOF = auto()


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: str
    pos: int


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_SORTS = frozenset({"Prop", "Set", "Type"})

# Infix binding powers: (left_bp, right_bp)
# Higher bp = tighter binding.
# Left-associative: right_bp = left_bp + 1
# Right-associative: right_bp = left_bp - 1
_INFIX_BP: dict[str, tuple[int, int]] = {
    "->": (10, 9),
    "=": (30, 31),
    "<>": (30, 31),
    "+": (50, 51),
    "-": (50, 51),
    "*": (60, 61),
    "\\/": (65, 66),
    "/\\": (65, 66),
    "<->": (20, 21),
    "||": (35, 36),
    "&&": (40, 41),
    "=?": (30, 31),
    "?=": (30, 31),
    "<": (70, 71),
    "<=": (70, 71),
    ">": (70, 71),
    ">=": (70, 71),
}

# Tokens that can start a primary expression (for application parsing).
_PRIMARY_STARTS = frozenset({
    TokenKind.IDENT,
    TokenKind.NUMBER,
    TokenKind.SORT,
    TokenKind.UNDERSCORE,
    TokenKind.LPAREN,
    TokenKind.LBRACE,
    TokenKind.LBRACKET,
})

# Regex for scope annotations: )%ident or trailing %ident
_SCOPE_RE = __import__("re").compile(r"%[a-zA-Z_][a-zA-Z0-9_]*")


def tokenize(text: str) -> list[Token]:
    """Tokenize a Coq type expression string into a list of Tokens."""
    # Pre-process: strip Coq scope annotations (%nat_scope, %bool, etc.)
    text = _SCOPE_RE.sub("", text)
    tokens: list[Token] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        # Skip whitespace
        if ch.isspace():
            i += 1
            continue

        pos = i

        # Three-character operators (check before two-char)
        if i + 2 < n:
            three = text[i : i + 3]
            if three == "<->":
                tokens.append(Token(TokenKind.INFIX_OP, "<->", pos))
                i += 3
                continue
            if three in ("<=?", "=?b", "<?b"):
                # Decidable comparison notations — treat as identifiers
                tokens.append(Token(TokenKind.IDENT, three, pos))
                i += 3
                continue

        # Two-character operators (check before single-char)
        if i + 1 < n:
            two = text[i : i + 2]
            if two == "->":
                tokens.append(Token(TokenKind.ARROW, "->", pos))
                i += 2
                continue
            if two == "=>":
                tokens.append(Token(TokenKind.DARROW, "=>", pos))
                i += 2
                continue
            if two in ("<=", ">=", "<>"):
                tokens.append(Token(TokenKind.INFIX_OP, two, pos))
                i += 2
                continue
            # Decidable operators: =?, <=?, ?=
            if two in ("=?", "?="):
                tokens.append(Token(TokenKind.INFIX_OP, two, pos))
                i += 2
                continue

        # Boolean operators: || and &&
        if i + 1 < n:
            if two == "||":
                tokens.append(Token(TokenKind.INFIX_OP, "||", pos))
                i += 2
                continue
            if two == "&&":
                tokens.append(Token(TokenKind.INFIX_OP, "&&", pos))
                i += 2
                continue

        # Disjunction: \/ (backslash + forward slash)
        if ch == "\\" and i + 1 < n and text[i + 1] == "/":
            tokens.append(Token(TokenKind.INFIX_OP, "\\/", pos))
            i += 2
            continue

        # Conjunction: /\ (forward slash + backslash)
        if ch == "/" and i + 1 < n and text[i + 1] == "\\":
            tokens.append(Token(TokenKind.INFIX_OP, "/\\", pos))
            i += 2
            continue

        # Single-character punctuation
        if ch == "(":
            tokens.append(Token(TokenKind.LPAREN, "(", pos))
            i += 1
            continue
        if ch == ")":
            tokens.append(Token(TokenKind.RPAREN, ")", pos))
            i += 1
            continue
        if ch == "{":
            tokens.append(Token(TokenKind.LBRACE, "{", pos))
            i += 1
            continue
        if ch == "}":
            tokens.append(Token(TokenKind.RBRACE, "}", pos))
            i += 1
            continue
        if ch == "[":
            tokens.append(Token(TokenKind.LBRACKET, "[", pos))
            i += 1
            continue
        if ch == "]":
            tokens.append(Token(TokenKind.RBRACKET, "]", pos))
            i += 1
            continue
        if ch == ":":
            tokens.append(Token(TokenKind.COLON, ":", pos))
            i += 1
            continue
        if ch == ",":
            tokens.append(Token(TokenKind.COMMA, ",", pos))
            i += 1
            continue
        if ch == "|":
            tokens.append(Token(TokenKind.PIPE, "|", pos))
            i += 1
            continue

        # Single-character infix operators
        if ch in ("+", "*"):
            tokens.append(Token(TokenKind.INFIX_OP, ch, pos))
            i += 1
            continue
        if ch == "=":
            tokens.append(Token(TokenKind.INFIX_OP, "=", pos))
            i += 1
            continue
        if ch == "<":
            tokens.append(Token(TokenKind.INFIX_OP, "<", pos))
            i += 1
            continue
        if ch == ">":
            tokens.append(Token(TokenKind.INFIX_OP, ">", pos))
            i += 1
            continue
        if ch == "-":
            tokens.append(Token(TokenKind.INFIX_OP, "-", pos))
            i += 1
            continue

        # @ (explicit application marker) — skip it
        if ch == "@":
            i += 1
            continue

        # ? followed by identifier (existential variable) — treat as identifier
        if ch == "?" and i + 1 < n and (text[i + 1].isalpha() or text[i + 1] == "_"):
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] in ("_", "'", ".")):
                j += 1
            tokens.append(Token(TokenKind.IDENT, text[i:j], pos))
            i = j
            continue

        # Standalone ?, !, ~, `, # — skip (negation, bang, etc.)
        if ch in ("?", "!", "`", "#", "~"):
            i += 1
            continue

        # Standalone / or \ not part of /\ or \/ — skip
        if ch in ("/", "\\"):
            i += 1
            continue

        # Numbers
        if ch.isdigit():
            j = i
            while j < n and text[j].isdigit():
                j += 1
            tokens.append(Token(TokenKind.NUMBER, text[i:j], pos))
            i = j
            continue

        # Identifiers, keywords, sorts
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (text[j].isalnum() or text[j] in ("_", "'", ".")):
                j += 1
            # Strip trailing dots (not part of identifiers)
            while j > i + 1 and text[j - 1] == ".":
                j -= 1
            word = text[i:j]
            if word == "_":
                tokens.append(Token(TokenKind.UNDERSCORE, "_", pos))
            elif word in _SORTS:
                tokens.append(Token(TokenKind.SORT, word, pos))
            elif word == "forall":
                tokens.append(Token(TokenKind.FORALL, word, pos))
            elif word == "fun":
                tokens.append(Token(TokenKind.FUN, word, pos))
            elif word in ("if", "then", "else", "let", "in",
                          "match", "with", "end", "return",
                          "as", "fix", "cofix"):
                # Control-flow keywords — treat as identifiers for indexing
                tokens.append(Token(TokenKind.IDENT, word, pos))
            else:
                tokens.append(Token(TokenKind.IDENT, word, pos))
            i = j
            continue

        raise ParseError(f"Unexpected character {ch!r} at position {pos}")

    tokens.append(Token(TokenKind.EOF, "", len(text)))
    return tokens


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class TypeExprParser:
    """Pure-Python parser for Coq type expression strings.

    Implements the ``CoqParser`` protocol. Converts type signature text
    into ``ConstrNode`` trees using a Pratt (top-down operator precedence)
    parser.
    """

    def parse(self, expression: str) -> Any:
        """Parse a Coq type expression string into a ConstrNode.

        Raises ``ParseError`` on failure.
        """
        if not expression or not expression.strip():
            raise ParseError("Empty expression")

        tokens = tokenize(expression)
        pos, node = self._expr(tokens, 0, [], 0)

        if tokens[pos].kind != TokenKind.EOF:
            tok = tokens[pos]
            raise ParseError(
                f"Unexpected token {tok.value!r} at position {tok.pos}"
            )
        return node

    # ----- Pratt parser core -----

    def _expr(
        self,
        tokens: list[Token],
        pos: int,
        binders: list[str],
        min_bp: int,
    ) -> tuple[int, Any]:
        """Parse an expression with minimum binding power *min_bp*."""
        pos, lhs = self._atom(tokens, pos, binders)

        while True:
            tok = tokens[pos]

            # Determine if the current token is an infix operator
            if tok.kind == TokenKind.ARROW:
                op = "->"
            elif tok.kind == TokenKind.INFIX_OP:
                op = tok.value
            else:
                break

            bp = _INFIX_BP.get(op)
            if bp is None:
                break

            left_bp, right_bp = bp
            if left_bp < min_bp:
                break

            pos += 1  # consume the operator

            if op == "->":
                # Non-dependent arrow: A -> B ≡ Prod("_", A, B)
                # Push "_" binder for correct de Bruijn offsets
                new_binders = binders + ["_"]
                pos, rhs = self._expr(tokens, pos, new_binders, right_bp)
                lhs = Prod("_", lhs, rhs)
            else:
                # Infix desugared to App: n + m ≡ App(Const("+"), [n, m])
                pos, rhs = self._expr(tokens, pos, binders, right_bp)
                lhs = App(Const(op), [lhs, rhs])

        return pos, lhs

    def _atom(
        self,
        tokens: list[Token],
        pos: int,
        binders: list[str],
    ) -> tuple[int, Any]:
        """Parse a primary expression and optional application arguments."""
        pos, node = self._primary(tokens, pos, binders)

        # Greedy application: collect arguments while next token starts a primary
        args: list[Any] = []
        while tokens[pos].kind in _PRIMARY_STARTS:
            pos, arg = self._primary(tokens, pos, binders)
            args.append(arg)

        if args:
            return pos, App(node, args)
        return pos, node

    def _primary(
        self,
        tokens: list[Token],
        pos: int,
        binders: list[str],
    ) -> tuple[int, Any]:
        """Parse a single primary expression (no application)."""
        tok = tokens[pos]

        if tok.kind == TokenKind.IDENT:
            return pos + 1, self._resolve(tok.value, binders)

        if tok.kind == TokenKind.SORT:
            return pos + 1, Sort(tok.value)

        if tok.kind == TokenKind.UNDERSCORE:
            return pos + 1, Sort("Type")

        if tok.kind == TokenKind.NUMBER:
            return pos + 1, Const(tok.value)

        if tok.kind == TokenKind.LPAREN:
            pos += 1
            pos, inner = self._expr(tokens, pos, binders, 0)
            if tokens[pos].kind != TokenKind.RPAREN:
                raise ParseError(
                    f"Expected ')' at position {tokens[pos].pos}"
                )
            return pos + 1, inner

        if tok.kind == TokenKind.LBRACE:
            pos += 1
            pos, inner = self._expr(tokens, pos, binders, 0)
            if tokens[pos].kind == TokenKind.PIPE:
                # Sig type {x : T | P} — parse the proposition after |
                pos += 1  # consume |
                pos, prop = self._expr(tokens, pos, binders, 0)
                # For indexing purposes, treat as Prod("_", inner, prop)
                inner = Prod("_", inner, prop)
            if tokens[pos].kind != TokenKind.RBRACE:
                raise ParseError(
                    f"Expected '}}' at position {tokens[pos].pos}"
                )
            return pos + 1, inner

        if tok.kind == TokenKind.LBRACKET:
            # Maximal implicit binders [A : T] — treat like {A : T}
            pos += 1
            pos, inner = self._expr(tokens, pos, binders, 0)
            if tokens[pos].kind != TokenKind.RBRACKET:
                raise ParseError(
                    f"Expected ']' at position {tokens[pos].pos}"
                )
            return pos + 1, inner

        if tok.kind == TokenKind.FORALL:
            return self._parse_forall(tokens, pos, binders)

        if tok.kind == TokenKind.FUN:
            return self._parse_fun(tokens, pos, binders)

        raise ParseError(
            f"Expected expression at position {tok.pos}, got {tok.value!r}"
        )

    # ----- Binder parsing -----

    def _parse_binder_groups(
        self,
        tokens: list[Token],
        pos: int,
        binders: list[str],
        separator: TokenKind,
    ) -> tuple[int, list[tuple[str, Any]]]:
        """Parse binder groups until *separator* (COMMA for forall, DARROW for fun).

        Returns (new_pos, list of (name, type) pairs).
        """
        all_pairs: list[tuple[str, Any]] = []
        current_binders = list(binders)

        while True:
            tok = tokens[pos]

            if tok.kind == TokenKind.LPAREN:
                # Parenthesized group: (x y ... : T)
                pos += 1
                names: list[str] = []
                while tokens[pos].kind == TokenKind.IDENT:
                    names.append(tokens[pos].value)
                    pos += 1
                if not names:
                    raise ParseError(
                        f"Expected variable name at position {tokens[pos].pos}"
                    )
                if tokens[pos].kind != TokenKind.COLON:
                    raise ParseError(
                        f"Expected ':' at position {tokens[pos].pos}"
                    )
                pos += 1
                pos, ty = self._expr(tokens, pos, current_binders, 0)
                if tokens[pos].kind != TokenKind.RPAREN:
                    raise ParseError(
                        f"Expected ')' at position {tokens[pos].pos}"
                    )
                pos += 1
                for name in names:
                    all_pairs.append((name, ty))
                    current_binders.append(name)
                continue

            if tok.kind == TokenKind.LBRACE:
                # Implicit group: {x y ... : T}
                pos += 1
                names = []
                while tokens[pos].kind == TokenKind.IDENT:
                    names.append(tokens[pos].value)
                    pos += 1
                if not names:
                    raise ParseError(
                        f"Expected variable name at position {tokens[pos].pos}"
                    )
                if tokens[pos].kind != TokenKind.COLON:
                    raise ParseError(
                        f"Expected ':' at position {tokens[pos].pos}"
                    )
                pos += 1
                pos, ty = self._expr(tokens, pos, current_binders, 0)
                if tokens[pos].kind != TokenKind.RBRACE:
                    raise ParseError(
                        f"Expected '}}' at position {tokens[pos].pos}"
                    )
                pos += 1
                for name in names:
                    all_pairs.append((name, ty))
                    current_binders.append(name)
                continue

            if tok.kind == TokenKind.LBRACKET:
                # Maximal implicit group: [x y ... : T]
                pos += 1
                names = []
                while tokens[pos].kind == TokenKind.IDENT:
                    names.append(tokens[pos].value)
                    pos += 1
                if not names:
                    raise ParseError(
                        f"Expected variable name at position {tokens[pos].pos}"
                    )
                if tokens[pos].kind != TokenKind.COLON:
                    raise ParseError(
                        f"Expected ':' at position {tokens[pos].pos}"
                    )
                pos += 1
                pos, ty = self._expr(tokens, pos, current_binders, 0)
                if tokens[pos].kind != TokenKind.RBRACKET:
                    raise ParseError(
                        f"Expected ']' at position {tokens[pos].pos}"
                    )
                pos += 1
                for name in names:
                    all_pairs.append((name, ty))
                    current_binders.append(name)
                continue

            if tok.kind == TokenKind.IDENT:
                # Unparenthesized binder(s): x y ... : T  (or untyped for fun)
                names = []
                while tokens[pos].kind == TokenKind.IDENT:
                    names.append(tokens[pos].value)
                    pos += 1
                if tokens[pos].kind == TokenKind.COLON:
                    pos += 1
                    pos, ty = self._expr(tokens, pos, current_binders, 0)
                    for name in names:
                        all_pairs.append((name, ty))
                        current_binders.append(name)
                else:
                    # Untyped binders (fun x => ...) — default type Sort("Type")
                    for name in names:
                        all_pairs.append((name, Sort("Type")))
                        current_binders.append(name)
                break  # unparenthesized group ends binder list

            # No more binder groups
            break

        return pos, all_pairs

    def _parse_forall(
        self,
        tokens: list[Token],
        pos: int,
        binders: list[str],
    ) -> tuple[int, Any]:
        """Parse ``forall (binders), body``."""
        pos += 1  # consume 'forall'

        pos, pairs = self._parse_binder_groups(
            tokens, pos, binders, TokenKind.COMMA
        )
        if not pairs:
            raise ParseError(
                f"Expected binder after 'forall' at position {tokens[pos].pos}"
            )

        if tokens[pos].kind != TokenKind.COMMA:
            raise ParseError(
                f"Expected ',' at position {tokens[pos].pos}"
            )
        pos += 1  # consume ','

        # Build binder stack for body
        body_binders = binders + [name for name, _ in pairs]
        pos, body = self._expr(tokens, pos, body_binders, 0)

        # Build nested Prod from right to left
        result = body
        for name, ty in reversed(pairs):
            result = Prod(name, ty, result)

        return pos, result

    def _parse_fun(
        self,
        tokens: list[Token],
        pos: int,
        binders: list[str],
    ) -> tuple[int, Any]:
        """Parse ``fun (binders) => body``."""
        pos += 1  # consume 'fun'

        pos, pairs = self._parse_binder_groups(
            tokens, pos, binders, TokenKind.DARROW
        )
        if not pairs:
            raise ParseError(
                f"Expected binder after 'fun' at position {tokens[pos].pos}"
            )

        if tokens[pos].kind != TokenKind.DARROW:
            raise ParseError(
                f"Expected '=>' at position {tokens[pos].pos}"
            )
        pos += 1  # consume '=>'

        # Build binder stack for body
        body_binders = binders + [name for name, _ in pairs]
        pos, body = self._expr(tokens, pos, body_binders, 0)

        # Build nested Lambda from right to left
        result = body
        for name, ty in reversed(pairs):
            result = Lambda(name, ty, result)

        return pos, result

    # ----- Name resolution -----

    @staticmethod
    def _resolve(name: str, binders: list[str]) -> Any:
        """Resolve a name against the binder stack.

        Returns ``Rel(n)`` for bound names (1-based de Bruijn index)
        or ``Const(name)`` for unbound names.
        """
        for i, binder_name in enumerate(reversed(binders)):
            if binder_name == name:
                return Rel(i + 1)
        return Const(name)
