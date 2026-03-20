"""TDD tests for the TypeExprParser — written before implementation.

Tests target the specification in specification/type-expr-parser.md:
  - Tokenizer: text → Token list
  - Parser: text → ConstrNode
  - CoqParser protocol conformance
  - Normalization integration: parse → coq_normalize → ExprTree

Implementation will live in src/poule/parsing/type_expr_parser.py.
"""

from __future__ import annotations

import pytest

from Poule.normalization.constr_node import (
    App,
    Const,
    Lambda,
    Prod,
    Rel,
    Sort,
)
from Poule.parsing.type_expr_parser import (
    Token,
    TokenKind,
    TypeExprParser,
    tokenize,
)
from Poule.pipeline.parser import CoqParser, ParseError


# ---------------------------------------------------------------------------
# 1. Tokenizer
# ---------------------------------------------------------------------------


class TestTokenizer:
    """Token streams for representative inputs (§4.2)."""

    def test_simple_ident(self):
        tokens = tokenize("nat")
        assert tokens[0] == Token(TokenKind.IDENT, "nat", 0)
        assert tokens[1].kind == TokenKind.EOF

    def test_arrow(self):
        tokens = tokenize("nat -> nat")
        assert tokens[0] == Token(TokenKind.IDENT, "nat", 0)
        assert tokens[1] == Token(TokenKind.ARROW, "->", 4)
        assert tokens[2] == Token(TokenKind.IDENT, "nat", 7)
        assert tokens[3].kind == TokenKind.EOF

    def test_forall_keyword(self):
        tokens = tokenize("forall n : nat, n")
        assert tokens[0] == Token(TokenKind.FORALL, "forall", 0)
        assert tokens[1] == Token(TokenKind.IDENT, "n", 7)
        assert tokens[2] == Token(TokenKind.COLON, ":", 9)
        assert tokens[3] == Token(TokenKind.IDENT, "nat", 11)
        assert tokens[4] == Token(TokenKind.COMMA, ",", 14)
        assert tokens[5] == Token(TokenKind.IDENT, "n", 16)
        assert tokens[6].kind == TokenKind.EOF

    def test_sorts(self):
        for sort_name in ("Prop", "Set", "Type"):
            tokens = tokenize(sort_name)
            assert tokens[0] == Token(TokenKind.SORT, sort_name, 0)
            assert tokens[1].kind == TokenKind.EOF

    def test_infix_plus(self):
        tokens = tokenize("n + m")
        assert tokens[1] == Token(TokenKind.INFIX_OP, "+", 2)

    def test_infix_star(self):
        tokens = tokenize("n * m")
        assert tokens[1] == Token(TokenKind.INFIX_OP, "*", 2)

    def test_infix_eq(self):
        tokens = tokenize("n = m")
        assert tokens[1] == Token(TokenKind.INFIX_OP, "=", 2)

    def test_two_char_le(self):
        tokens = tokenize("a <= b")
        assert tokens[1] == Token(TokenKind.INFIX_OP, "<=", 2)

    def test_two_char_ge(self):
        tokens = tokenize("a >= b")
        assert tokens[1] == Token(TokenKind.INFIX_OP, ">=", 2)

    def test_two_char_neq(self):
        tokens = tokenize("a <> b")
        assert tokens[1] == Token(TokenKind.INFIX_OP, "<>", 2)

    def test_parentheses(self):
        tokens = tokenize("(nat)")
        assert tokens[0] == Token(TokenKind.LPAREN, "(", 0)
        assert tokens[1] == Token(TokenKind.IDENT, "nat", 1)
        assert tokens[2] == Token(TokenKind.RPAREN, ")", 4)

    def test_braces(self):
        tokens = tokenize("{x : T}")
        assert tokens[0] == Token(TokenKind.LBRACE, "{", 0)
        assert tokens[4] == Token(TokenKind.RBRACE, "}", 6)

    def test_standalone_underscore(self):
        tokens = tokenize("_")
        assert tokens[0] == Token(TokenKind.UNDERSCORE, "_", 0)

    def test_underscore_prefixed_ident(self):
        tokens = tokenize("_foo")
        assert tokens[0] == Token(TokenKind.IDENT, "_foo", 0)

    def test_number(self):
        tokens = tokenize("42")
        assert tokens[0] == Token(TokenKind.NUMBER, "42", 0)

    def test_qualified_name(self):
        tokens = tokenize("Coq.Init.Nat.add")
        assert tokens[0] == Token(TokenKind.IDENT, "Coq.Init.Nat.add", 0)

    def test_fun_and_darrow(self):
        tokens = tokenize("fun x => x")
        assert tokens[0] == Token(TokenKind.FUN, "fun", 0)
        assert tokens[2] == Token(TokenKind.DARROW, "=>", 6)

    def test_disjunction(self):
        tokens = tokenize("A \\/ B")
        assert tokens[1] == Token(TokenKind.INFIX_OP, "\\/", 2)

    def test_conjunction(self):
        tokens = tokenize("A /\\ B")
        assert tokens[1] == Token(TokenKind.INFIX_OP, "/\\", 2)

    def test_single_lt(self):
        tokens = tokenize("a < b")
        assert tokens[1] == Token(TokenKind.INFIX_OP, "<", 2)

    def test_single_gt(self):
        tokens = tokenize("a > b")
        assert tokens[1] == Token(TokenKind.INFIX_OP, ">", 2)

    def test_comma(self):
        tokens = tokenize(",")
        assert tokens[0] == Token(TokenKind.COMMA, ",", 0)

    def test_pipe(self):
        tokens = tokenize("|")
        assert tokens[0] == Token(TokenKind.PIPE, "|", 0)

    def test_ident_with_prime(self):
        tokens = tokenize("n'")
        assert tokens[0] == Token(TokenKind.IDENT, "n'", 0)


# ---------------------------------------------------------------------------
# 2. Simple types
# ---------------------------------------------------------------------------


class TestSimpleTypes:
    """Single identifiers and sorts (§4.4)."""

    def setup_method(self):
        self.parser = TypeExprParser()

    def test_single_ident(self):
        result = self.parser.parse("nat")
        assert result == Const("nat")

    def test_prop_sort(self):
        result = self.parser.parse("Prop")
        assert result == Sort("Prop")

    def test_set_sort(self):
        result = self.parser.parse("Set")
        assert result == Sort("Set")

    def test_type_sort(self):
        result = self.parser.parse("Type")
        assert result == Sort("Type")

    def test_underscore_wildcard(self):
        result = self.parser.parse("_")
        assert result == Sort("Type")

    def test_number_literal(self):
        result = self.parser.parse("0")
        assert result == Const("0")

    def test_simple_arrow(self):
        result = self.parser.parse("nat -> nat")
        assert result == Prod("_", Const("nat"), Const("nat"))


# ---------------------------------------------------------------------------
# 3. Arrow types
# ---------------------------------------------------------------------------


class TestArrowTypes:
    """Right-associativity, nested arrows, parenthesized arrows (§4.3, §4.4)."""

    def setup_method(self):
        self.parser = TypeExprParser()

    def test_right_associativity(self):
        """nat -> nat -> nat  ≡  nat -> (nat -> nat)"""
        result = self.parser.parse("nat -> nat -> nat")
        assert result == Prod(
            "_", Const("nat"),
            Prod("_", Const("nat"), Const("nat")),
        )

    def test_left_grouped_arrow(self):
        """(A -> B) -> C"""
        result = self.parser.parse("(A -> B) -> C")
        assert result == Prod(
            "_",
            Prod("_", Const("A"), Const("B")),
            Const("C"),
        )

    def test_three_nested_arrows(self):
        """A -> B -> C -> D"""
        result = self.parser.parse("A -> B -> C -> D")
        assert result == Prod(
            "_", Const("A"),
            Prod("_", Const("B"),
                 Prod("_", Const("C"), Const("D"))),
        )

    def test_arrow_with_sort(self):
        """(nat -> Prop) -> nat -> Prop"""
        result = self.parser.parse("(nat -> Prop) -> nat -> Prop")
        assert result == Prod(
            "_",
            Prod("_", Const("nat"), Sort("Prop")),
            Prod("_", Const("nat"), Sort("Prop")),
        )


# ---------------------------------------------------------------------------
# 4. Forall
# ---------------------------------------------------------------------------


class TestForall:
    """Typed binders, grouped binders, implicit binders (§4.4, §4.6)."""

    def setup_method(self):
        self.parser = TypeExprParser()

    def test_simple_forall(self):
        """forall n : nat, n"""
        result = self.parser.parse("forall n : nat, n")
        assert result == Prod("n", Const("nat"), Rel(1))

    def test_grouped_binders(self):
        """forall (x y : nat), x"""
        result = self.parser.parse("forall (x y : nat), x")
        assert result == Prod(
            "x", Const("nat"),
            Prod("y", Const("nat"), Rel(2)),
        )

    def test_multiple_binder_groups(self):
        """forall (x : nat) (y : nat), x"""
        result = self.parser.parse("forall (x : nat) (y : nat), x")
        assert result == Prod(
            "x", Const("nat"),
            Prod("y", Const("nat"), Rel(2)),
        )

    def test_implicit_binder(self):
        """forall {x : nat}, x"""
        result = self.parser.parse("forall {x : nat}, x")
        assert result == Prod("x", Const("nat"), Rel(1))

    def test_forall_with_arrow_type(self):
        """forall (P : nat -> Prop), P"""
        result = self.parser.parse("forall (P : nat -> Prop), P")
        assert result == Prod(
            "P",
            Prod("_", Const("nat"), Sort("Prop")),
            Rel(1),
        )

    def test_unparenthesized_grouped_binders(self):
        """forall n m : nat, n"""
        result = self.parser.parse("forall n m : nat, n")
        assert result == Prod(
            "n", Const("nat"),
            Prod("m", Const("nat"), Rel(2)),
        )

    def test_forall_body_with_infix(self):
        """forall n : nat, n + 0 = n"""
        result = self.parser.parse("forall n : nat, n + 0 = n")
        assert result == Prod(
            "n", Const("nat"),
            App(Const("="), [
                App(Const("+"), [Rel(1), Const("0")]),
                Rel(1),
            ]),
        )


# ---------------------------------------------------------------------------
# 5. Application
# ---------------------------------------------------------------------------


class TestApplication:
    """Function application by juxtaposition (§4.3, §4.4)."""

    def setup_method(self):
        self.parser = TypeExprParser()

    def test_simple_application(self):
        """list nat"""
        result = self.parser.parse("list nat")
        assert result == App(Const("list"), [Const("nat")])

    def test_multi_arg_application(self):
        """f x y"""
        result = self.parser.parse("f x y")
        assert result == App(Const("f"), [Const("x"), Const("y")])

    def test_nested_application(self):
        """S (S n)"""
        result = self.parser.parse("S (S n)")
        assert result == App(
            Const("S"),
            [App(Const("S"), [Const("n")])],
        )

    def test_application_binds_tighter_than_arrow(self):
        """list nat -> list nat"""
        result = self.parser.parse("list nat -> list nat")
        assert result == Prod(
            "_",
            App(Const("list"), [Const("nat")]),
            App(Const("list"), [Const("nat")]),
        )

    def test_application_binds_tighter_than_infix(self):
        """f x + g y  ≡  (f x) + (g y)"""
        result = self.parser.parse("f x + g y")
        assert result == App(
            Const("+"),
            [App(Const("f"), [Const("x")]),
             App(Const("g"), [Const("y")])],
        )


# ---------------------------------------------------------------------------
# 6. Infix operators
# ---------------------------------------------------------------------------


class TestInfixOperators:
    """Precedence and desugaring (§4.3, §4.4)."""

    def setup_method(self):
        self.parser = TypeExprParser()

    def test_addition(self):
        """n + m"""
        result = self.parser.parse("n + m")
        assert result == App(Const("+"), [Const("n"), Const("m")])

    def test_equality(self):
        """n = 0"""
        result = self.parser.parse("n = 0")
        assert result == App(Const("="), [Const("n"), Const("0")])

    def test_mul_binds_tighter_than_add(self):
        """n + m * p  ≡  n + (m * p)"""
        result = self.parser.parse("n + m * p")
        assert result == App(
            Const("+"),
            [Const("n"), App(Const("*"), [Const("m"), Const("p")])],
        )

    def test_comparison_in_arrow(self):
        """n < m -> m < p -> n < p"""
        result = self.parser.parse("n < m -> m < p -> n < p")
        assert result == Prod(
            "_",
            App(Const("<"), [Const("n"), Const("m")]),
            Prod(
                "_",
                App(Const("<"), [Const("m"), Const("p")]),
                App(Const("<"), [Const("n"), Const("p")]),
            ),
        )

    def test_le_operator(self):
        """a <= b"""
        result = self.parser.parse("a <= b")
        assert result == App(Const("<="), [Const("a"), Const("b")])

    def test_neq_operator(self):
        """a <> b"""
        result = self.parser.parse("a <> b")
        assert result == App(Const("<>"), [Const("a"), Const("b")])

    def test_eq_binds_looser_than_add(self):
        """n + 0 = n  ≡  (n + 0) = n"""
        result = self.parser.parse("n + 0 = n")
        assert result == App(
            Const("="),
            [App(Const("+"), [Const("n"), Const("0")]), Const("n")],
        )


# ---------------------------------------------------------------------------
# 7. De Bruijn indices
# ---------------------------------------------------------------------------


class TestDeBruijn:
    """Bound vs unbound names, nested binders, shadowing (§4.5)."""

    def setup_method(self):
        self.parser = TypeExprParser()

    def test_bound_variable(self):
        """forall n : nat, n  → Rel(1)"""
        result = self.parser.parse("forall n : nat, n")
        assert result == Prod("n", Const("nat"), Rel(1))

    def test_unbound_variable(self):
        """forall n : nat, m  → Const("m")"""
        result = self.parser.parse("forall n : nat, m")
        assert result == Prod("n", Const("nat"), Const("m"))

    def test_nested_binders(self):
        """forall (x : nat) (y : nat), x  → Rel(2)"""
        result = self.parser.parse("forall (x : nat) (y : nat), x")
        assert result == Prod(
            "x", Const("nat"),
            Prod("y", Const("nat"), Rel(2)),
        )

    def test_inner_binder_is_rel_1(self):
        """forall (x : nat) (y : nat), y  → Rel(1)"""
        result = self.parser.parse("forall (x : nat) (y : nat), y")
        assert result == Prod(
            "x", Const("nat"),
            Prod("y", Const("nat"), Rel(1)),
        )

    def test_arrow_pushes_anonymous_binder(self):
        """forall (x : nat), x -> x
        After the arrow, the binder stack is ["x", "_"],
        so x in the body is Rel(2)."""
        result = self.parser.parse("forall (x : nat), x -> x")
        assert result == Prod(
            "x", Const("nat"),
            Prod("_", Rel(1), Rel(2)),
        )

    def test_shadowing(self):
        """forall (x : nat) (x : nat), x  → inner x = Rel(1)"""
        result = self.parser.parse("forall (x : nat) (x : nat), x")
        assert result == Prod(
            "x", Const("nat"),
            Prod("x", Const("nat"), Rel(1)),
        )


# ---------------------------------------------------------------------------
# 8. Fun (lambda)
# ---------------------------------------------------------------------------


class TestFun:
    """Lambda abstractions (§4.4)."""

    def setup_method(self):
        self.parser = TypeExprParser()

    def test_typed_fun(self):
        """fun (x : nat) => x"""
        result = self.parser.parse("fun (x : nat) => x")
        assert result == Lambda("x", Const("nat"), Rel(1))

    def test_untyped_fun(self):
        """fun x => x  — untyped binder defaults to Sort("Type")"""
        result = self.parser.parse("fun x => x")
        assert result == Lambda("x", Sort("Type"), Rel(1))

    def test_multi_arg_fun(self):
        """fun (x y : nat) => x"""
        result = self.parser.parse("fun (x y : nat) => x")
        assert result == Lambda(
            "x", Const("nat"),
            Lambda("y", Const("nat"), Rel(2)),
        )


# ---------------------------------------------------------------------------
# 9. Qualified names
# ---------------------------------------------------------------------------


class TestQualifiedNames:
    """Dot-separated qualified names (§4.4)."""

    def setup_method(self):
        self.parser = TypeExprParser()

    def test_qualified_const(self):
        result = self.parser.parse("Coq.Init.Nat.add")
        assert result == Const("Coq.Init.Nat.add")

    def test_qualified_in_application(self):
        result = self.parser.parse("Coq.Init.Nat.add n m")
        assert result == App(
            Const("Coq.Init.Nat.add"),
            [Const("n"), Const("m")],
        )


# ---------------------------------------------------------------------------
# 10. Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    """Parse failures (§5)."""

    def setup_method(self):
        self.parser = TypeExprParser()

    def test_empty_input(self):
        with pytest.raises(ParseError):
            self.parser.parse("")

    def test_unclosed_paren(self):
        with pytest.raises(ParseError):
            self.parser.parse("(nat")

    def test_trailing_tokens(self):
        with pytest.raises(ParseError):
            self.parser.parse("nat nat )")

    def test_unexpected_rparen(self):
        with pytest.raises(ParseError):
            self.parser.parse(")")

    def test_unclosed_brace(self):
        with pytest.raises(ParseError):
            self.parser.parse("{nat")


# ---------------------------------------------------------------------------
# 11. CoqParser protocol conformance
# ---------------------------------------------------------------------------


class TestCoqParserProtocol:
    """TypeExprParser satisfies the CoqParser protocol (§4.1)."""

    def test_isinstance_check(self):
        parser = TypeExprParser()
        assert isinstance(parser, CoqParser)

    def test_parse_returns_constr_node(self):
        parser = TypeExprParser()
        result = parser.parse("nat")
        # Should be a ConstrNode variant (Const in this case)
        assert isinstance(result, Const)

    def test_parse_raises_parse_error(self):
        parser = TypeExprParser()
        with pytest.raises(ParseError):
            parser.parse("")


# ---------------------------------------------------------------------------
# 12. Normalization integration
# ---------------------------------------------------------------------------


class TestNormalizationIntegration:
    """parse → coq_normalize → verify ExprTree structure."""

    def test_simple_type_normalizes(self):
        from Poule.normalization.normalize import coq_normalize

        parser = TypeExprParser()
        constr_node = parser.parse("nat -> nat")
        tree = coq_normalize(constr_node)

        # Should produce a valid ExprTree with root and node_count
        assert tree.root is not None
        assert tree.node_count > 0

    def test_forall_type_normalizes(self):
        from Poule.normalization.normalize import coq_normalize

        parser = TypeExprParser()
        constr_node = parser.parse("forall n : nat, n + 0 = n")
        tree = coq_normalize(constr_node)

        assert tree.root is not None
        assert tree.node_count > 0

    def test_cse_normalize_after_parse(self):
        from Poule.normalization.cse import cse_normalize
        from Poule.normalization.normalize import coq_normalize

        parser = TypeExprParser()
        constr_node = parser.parse("forall n m : nat, n + m = m + n")
        tree = coq_normalize(constr_node)
        cse_normalize(tree)

        # CSE should not crash; tree should still be valid
        assert tree.root is not None
        assert tree.node_count > 0

    def test_wl_histogram_after_parse(self):
        from Poule.channels.wl_kernel import wl_histogram
        from Poule.normalization.cse import cse_normalize
        from Poule.normalization.normalize import coq_normalize

        parser = TypeExprParser()
        constr_node = parser.parse("nat -> nat -> nat")
        tree = coq_normalize(constr_node)
        cse_normalize(tree)
        hist = wl_histogram(tree, h=3)

        # Should produce a non-empty histogram
        assert isinstance(hist, dict)
        assert len(hist) > 0

    def test_extract_consts_after_parse(self):
        from Poule.channels.const_jaccard import extract_consts
        from Poule.normalization.normalize import coq_normalize

        parser = TypeExprParser()
        constr_node = parser.parse("nat -> nat")
        tree = coq_normalize(constr_node)
        consts = extract_consts(tree)

        # Should find "nat" as a constant
        assert "nat" in consts
