"""Tests for the safe expression language (parser + evaluator)."""

from __future__ import annotations

import pytest

from theaios.context_router.expressions import (
    BinaryOp,
    BoolLiteral,
    ExpressionError,
    FieldAccess,
    NumberLiteral,
    StringLiteral,
    Variable,
    compile_expression,
    evaluate,
)


class TestCompileExpression:
    """Tests for compiling expression strings into AST nodes."""

    def test_empty_expression_is_always_true(self) -> None:
        ast = compile_expression("")
        assert isinstance(ast, BoolLiteral)
        assert ast.value is True

    def test_whitespace_only_is_always_true(self) -> None:
        ast = compile_expression("   ")
        assert isinstance(ast, BoolLiteral)
        assert ast.value is True

    def test_string_comparison(self) -> None:
        ast = compile_expression('action == "send_email"')
        assert isinstance(ast, BinaryOp)
        assert ast.op == "=="
        assert isinstance(ast.left, FieldAccess)
        assert ast.left.parts == ("action",)
        assert isinstance(ast.right, StringLiteral)
        assert ast.right.value == "send_email"

    def test_field_access_dot_notation(self) -> None:
        ast = compile_expression('recipient.domain == "example.com"')
        assert isinstance(ast, BinaryOp)
        assert isinstance(ast.left, FieldAccess)
        assert ast.left.parts == ("recipient", "domain")

    def test_variable_reference(self) -> None:
        ast = compile_expression("level > $threshold")
        assert isinstance(ast, BinaryOp)
        assert isinstance(ast.right, Variable)
        assert ast.right.name == "threshold"

    def test_number_literal(self) -> None:
        ast = compile_expression("count == 42")
        assert isinstance(ast, BinaryOp)
        assert isinstance(ast.right, NumberLiteral)
        assert ast.right.value == 42

    def test_invalid_expression_raises(self) -> None:
        with pytest.raises(ExpressionError, match="Unexpected character"):
            compile_expression("action == @bad")


class TestEvaluateComparisons:
    """Tests for evaluating comparison expressions."""

    def test_string_equality_true(self) -> None:
        ast = compile_expression('action == "send_email"')
        result = evaluate(ast, {"action": "send_email"})
        assert result is True

    def test_string_equality_false(self) -> None:
        ast = compile_expression('action == "send_email"')
        result = evaluate(ast, {"action": "read_file"})
        assert result is False

    def test_string_inequality(self) -> None:
        ast = compile_expression('status != "active"')
        assert evaluate(ast, {"status": "inactive"}) is True
        assert evaluate(ast, {"status": "active"}) is False

    def test_numeric_greater_than(self) -> None:
        ast = compile_expression("amount > 100")
        assert evaluate(ast, {"amount": 150}) is True
        assert evaluate(ast, {"amount": 50}) is False

    def test_numeric_less_than(self) -> None:
        ast = compile_expression("count < 10")
        assert evaluate(ast, {"count": 5}) is True
        assert evaluate(ast, {"count": 15}) is False

    def test_numeric_gte(self) -> None:
        ast = compile_expression("score >= 90")
        assert evaluate(ast, {"score": 90}) is True
        assert evaluate(ast, {"score": 89}) is False

    def test_numeric_lte(self) -> None:
        ast = compile_expression("score <= 90")
        assert evaluate(ast, {"score": 90}) is True
        assert evaluate(ast, {"score": 91}) is False


class TestEvaluateContains:
    """Tests for the contains operator."""

    def test_string_contains_true(self) -> None:
        ast = compile_expression('text contains "help"')
        result = evaluate(ast, {"text": "I need help with this"})
        assert result is True

    def test_string_contains_false(self) -> None:
        ast = compile_expression('text contains "help"')
        result = evaluate(ast, {"text": "Everything is fine"})
        assert result is False

    def test_starts_with(self) -> None:
        ast = compile_expression('name starts_with "Dr."')
        assert evaluate(ast, {"name": "Dr. Smith"}) is True
        assert evaluate(ast, {"name": "Mr. Jones"}) is False

    def test_ends_with(self) -> None:
        ast = compile_expression('email ends_with "@company.com"')
        assert evaluate(ast, {"email": "user@company.com"}) is True
        assert evaluate(ast, {"email": "user@gmail.com"}) is False


class TestEvaluateBooleanLogic:
    """Tests for and/or/not operators."""

    def test_and_both_true(self) -> None:
        ast = compile_expression('action == "send" and level > 5')
        result = evaluate(ast, {"action": "send", "level": 10})
        assert result is True

    def test_and_one_false(self) -> None:
        ast = compile_expression('action == "send" and level > 5')
        result = evaluate(ast, {"action": "send", "level": 3})
        assert result is False

    def test_or_one_true(self) -> None:
        ast = compile_expression('status == "active" or role == "admin"')
        result = evaluate(ast, {"status": "inactive", "role": "admin"})
        assert result is True

    def test_or_both_false(self) -> None:
        ast = compile_expression('status == "active" or role == "admin"')
        result = evaluate(ast, {"status": "inactive", "role": "user"})
        assert result is False

    def test_not_operator(self) -> None:
        ast = compile_expression('not status == "blocked"')
        assert evaluate(ast, {"status": "active"}) is True
        assert evaluate(ast, {"status": "blocked"}) is False

    def test_complex_boolean(self) -> None:
        ast = compile_expression('(action == "delete" or action == "drop") and role != "admin"')
        assert evaluate(ast, {"action": "delete", "role": "user"}) is True
        assert evaluate(ast, {"action": "delete", "role": "admin"}) is False
        assert evaluate(ast, {"action": "read", "role": "user"}) is False


class TestEvaluateVariables:
    """Tests for variable substitution."""

    def test_variable_comparison(self) -> None:
        ast = compile_expression("level > $min_level")
        result = evaluate(ast, {"level": 10}, variables={"min_level": 5})
        assert result is True

    def test_variable_string(self) -> None:
        ast = compile_expression("domain == $company_domain")
        result = evaluate(
            ast,
            {"domain": "acme.com"},
            variables={"company_domain": "acme.com"},
        )
        assert result is True

    def test_undefined_variable_raises(self) -> None:
        ast = compile_expression("level > $undefined_var")
        with pytest.raises(ExpressionError, match="Undefined variable"):
            evaluate(ast, {"level": 10})


class TestEvaluateFieldAccess:
    """Tests for nested field access."""

    def test_nested_field(self) -> None:
        ast = compile_expression('user.role == "admin"')
        result = evaluate(ast, {"user": {"role": "admin"}})
        assert result is True

    def test_deeply_nested_field(self) -> None:
        ast = compile_expression('config.database.host == "localhost"')
        result = evaluate(ast, {"config": {"database": {"host": "localhost"}}})
        assert result is True

    def test_missing_nested_field_returns_none(self) -> None:
        ast = compile_expression("user.role == null")
        result = evaluate(ast, {"user": {}})
        assert result is True


class TestEvaluateInOperator:
    """Tests for the in / not in operators."""

    def test_in_list(self) -> None:
        ast = compile_expression('status in ["active", "pending"]')
        assert evaluate(ast, {"status": "active"}) is True
        assert evaluate(ast, {"status": "blocked"}) is False

    def test_not_in_list(self) -> None:
        ast = compile_expression('role not in ["guest", "banned"]')
        assert evaluate(ast, {"role": "admin"}) is True
        assert evaluate(ast, {"role": "guest"}) is False
