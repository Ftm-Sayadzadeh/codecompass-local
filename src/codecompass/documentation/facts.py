"""Deterministic syntax facts for one selected Python function or method."""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass

from codecompass.documentation.models import ParameterFact


class FactExtractionError(Exception):
    """Raised when the selected source cannot produce trustworthy facts."""


@dataclass(frozen=True, slots=True)
class SyntaxFacts:
    """Facts visible directly in the selected function syntax."""

    parameters: tuple[ParameterFact, ...]
    return_annotation: str | None
    is_async: bool
    explicit_raises: tuple[str, ...]
    direct_calls: tuple[str, ...]
    has_explicit_return: bool


def extract_syntax_facts(source_code: str, expected_name: str) -> SyntaxFacts:
    """Extract conservative facts without traversing nested definitions."""
    try:
        tree = ast.parse(textwrap.dedent(source_code))
    except (SyntaxError, ValueError, TypeError) as error:
        raise FactExtractionError("Selected source is not valid Python") from error
    target = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == expected_name
        ),
        None,
    )
    if target is None:
        raise FactExtractionError("Selected function is unavailable in source evidence")

    visitor = _FactVisitor()
    for statement in target.body:
        visitor.visit(statement)
    return SyntaxFacts(
        parameters=_parameters(target.args),
        return_annotation=_unparse(target.returns),
        is_async=isinstance(target, ast.AsyncFunctionDef),
        explicit_raises=tuple(visitor.raises),
        direct_calls=tuple(visitor.calls),
        has_explicit_return=visitor.has_return,
    )


class _FactVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.raises: list[str] = []
        self.calls: list[str] = []
        self.has_return = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_Raise(self, node: ast.Raise) -> None:
        expression = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
        name = _call_name(expression)
        if name is not None:
            _append_unique(self.raises, name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name is not None:
            _append_unique(self.calls, name)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        self.has_return = True
        self.generic_visit(node)


def _parameters(arguments: ast.arguments) -> tuple[ParameterFact, ...]:
    positional = [*arguments.posonlyargs, *arguments.args]
    first_default = len(positional) - len(arguments.defaults)
    result = [
        ParameterFact(
            name=argument.arg,
            annotation=_unparse(argument.annotation),
            default=_unparse(arguments.defaults[index - first_default]) if index >= first_default else None,
        )
        for index, argument in enumerate(positional)
    ]
    if arguments.vararg is not None:
        result.append(
            ParameterFact(
                name=f"*{arguments.vararg.arg}",
                annotation=_unparse(arguments.vararg.annotation),
                default=None,
            )
        )
    result.extend(
        ParameterFact(
            name=argument.arg,
            annotation=_unparse(argument.annotation),
            default=_unparse(default),
        )
        for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True)
    )
    if arguments.kwarg is not None:
        result.append(
            ParameterFact(
                name=f"**{arguments.kwarg.arg}",
                annotation=_unparse(arguments.kwarg.annotation),
                default=None,
            )
        )
    return tuple(result)


def _call_name(expression: ast.expr | None) -> str | None:
    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        parent = _call_name(expression.value)
        return f"{parent}.{expression.attr}" if parent is not None else None
    if (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == "super"
        and not expression.args
        and not expression.keywords
    ):
        return "super()"
    return None


def _unparse(expression: ast.expr | None) -> str | None:
    return ast.unparse(expression).strip() if expression is not None else None


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)
