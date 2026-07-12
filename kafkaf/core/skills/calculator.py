"""A safe arithmetic evaluator — parses with `ast`, walks a whitelist of node
types, and never calls `eval`/`exec`. No access to names, attributes,
imports, or arbitrary function calls beyond a small fixed set of math
helpers.
"""

import ast
import operator

from kafkaf.core.skills.base import Skill

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_CONSTANTS = {"pi": 3.141592653589793, "e": 2.718281828459045}

_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": lambda x: x**0.5,
}


class CalculatorError(ValueError):
    pass


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise CalculatorError(f"unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _FUNCTIONS
    ):
        if node.keywords:
            raise CalculatorError("keyword arguments are not supported")
        args = [_eval_node(arg) for arg in node.args]
        return _FUNCTIONS[node.func.id](*args)
    raise CalculatorError(f"unsupported expression near: {ast.dump(node)}")


def safe_eval(expression: str) -> float:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError(f"invalid expression: {exc}") from exc
    return _eval_node(tree)


class CalculatorSkill(Skill):
    name = "calculator"
    description = "Evaluate a math expression, e.g. '2 * (3 + 4) / sqrt(16)'."

    async def run(self, arg: str) -> str:
        try:
            result = safe_eval(arg)
        except (CalculatorError, ZeroDivisionError, OverflowError) as exc:
            return f"error: {exc}"
        return str(result)
