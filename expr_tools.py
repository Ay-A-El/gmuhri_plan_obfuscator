# ==========================================================
# Expression Tools
# ==========================================================

from unified_planning.model import FNode

# Evaluates grounded up boolean expressions
def is_true(expr: FNode, truth: Set[str]) -> bool:
    if expr.is_fluent_exp():
        return str(expr) in truth
    if expr.is_bool_constant():
        return bool(expr.constant_value())
    if expr.is_and():
        return all(is_true(a, truth) for a in expr.args)
    if expr.is_or():
        return any(is_true(a, truth) for a in expr.args)
    if expr.is_not():
        return not is_true(expr.arg(0), truth)
    if expr.is_equals():
        return str(expr.arg(0)) == str(expr.arg(1))

# Collects positive predictates from boolean syntax tree.
def walk_logical_expr(node: FNode) -> Set[str]:
    if node.is_fluent_exp():
        return {str(node)}
    if node.is_bool_constant():
        return set()
    if node.is_not():
        return set()
    if node.is_and() or node.is_or():
        out = set()
        for child in node.args:
            out |= walk_logical_expr(child)
        return out
    return set()