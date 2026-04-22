"""Simple built-in tool registry for Phase 2."""

from __future__ import annotations

import ast
import operator
from datetime import datetime, timezone
from typing import Callable

ToolFn = Callable[[str], str]


def _tool_echo(arg: str) -> str:
    return arg


def _tool_current_time(_: str) -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_eval_math(expr: str) -> float:
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Num):  # pragma: no cover - py<3.8 compatibility path
            return float(node.n)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and type(node.op) in operators:
            return operators[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            return operators[type(node.op)](_eval(node.left), _eval(node.right))
        raise ValueError("Unsupported expression")

    parsed = ast.parse(expr, mode="eval")
    return _eval(parsed.body)


def _tool_calculator(arg: str) -> str:
    if not arg.strip():
        raise ValueError("calculator requires a math expression")
    value = _safe_eval_math(arg)
    return str(value)


class ToolRegistry:
    """In-process tool registry with deterministic built-in tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolFn] = {
            "echo": _tool_echo,
            "current_time": _tool_current_time,
            "calculator": _tool_calculator,
        }

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())

    def call(self, name: str, arg: str) -> str:
        fn = self._tools.get(name)
        if fn is None:
            raise ValueError(f"Unknown tool: {name}")
        return fn(arg)

