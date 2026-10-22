from unified_planning.model import InstantaneousAction, Parameter, FNode
from unified_planning.shortcuts import And
import re

def grounded_precondition(action: InstantaneousAction, binding: dict[Parameter, FNode]) -> FNode:
    return And([
        substitute_expr(p, binding)
        for p in action.preconditions
    ])

def grounded_effects(action: InstantaneousAction, binding: dict[Parameter, FNode]) -> dict[str, bool]:
    changes = {}

    for eff in action.effects:
        # Skip conditional effects here unless condition true at runtime
        if not str(eff.condition).lower() == "true":
            continue

        fluent = substitute_expr(eff.fluent, binding)
        sval = str(eff.value).lower()

        if sval == "true":
            changes[str(fluent)] = True
        elif sval == "false":
            changes[str(fluent)] = False

    return changes

# Given a problem and a set of truths, ground them accordingly
def grounded_predicates(problem: Problem, truths: Set[str]) -> [FNode]:
    preds = []
    for pred_str in truths:
        # 1. Parse name and arguments using regex
        # regex translation: Match any word character 1+ times, followed by (, then any unicode character 0+ times, then flollowed by )
        # there may or may not be commas within the literal parantheses, this gets processed later.
        match = re.match(r"(\w+)\((.*)\)", pred_str)
        if match is None: # Got a predicate that takes no arguments
            preds.append(problem.fluent(pred_str))
            continue
        name = match.group(1)
        # Split args by comma and strip whitespace
        arg_names = [a.strip() for a in match.group(2).split(',') if a.strip()]
        # 2. Get the Fluent object from the problem
        fluent = problem.fluent(name)
        # 3. Get the Object instances for the arguments
        objects = [problem.object(obj_name) for obj_name in arg_names]
        # Fluent(*objects) creates the FNode (the ground predicate)
        preds.append(fluent(*objects))
    return preds

def substitute_expr(expr: FNode, binding: dict[Parameter, FNode]) -> FNode:
    return expr.substitute(binding)