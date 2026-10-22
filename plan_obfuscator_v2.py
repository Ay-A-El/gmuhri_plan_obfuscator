from unified_planning.io import PDDLReader
from unified_planning.shortcuts import OneshotPlanner, And, ObjectExp, get_environment
import itertools
import random
import copy
import graphviz
import argparse
# from this project
import expr_tools
import grounder

class PlanNode:
    def __init__(self, label, precondition, effect):
        self.label = label
        self.precondition = precondition
        self.effect = effect
        self.truth_before = set()
        self.truth_after = set()
        self.supports = []
        self.supported_by = []
        self.goals_just_added = set()
        self.goals_so_far = set()
        self.prev = None
        self.next = None

    def get_added_effects(self):
        added_effects = set()
        for item in self.effect:
            if not item.startswith("-"):
                added_effects.add(item)
        return added_effects

    def get_removed_effects(self):
        removed_effects = set()
        for item in self.effect:
            if item.startswith("-"):
                removed_effects.add(item[1:])
        return removed_effects

    def key(self):
        return str(id(self))

    def __repr__(self):
        return self.label

class PlanList:
    def __init__(self, domain_file: str, problem_file: str ):
        self.head = None
        self.tail = None
        self.length = 0

        # parse PDDLs
        reader: PDDLReader = PDDLReader()
        problem: Problem = reader.parse_problem(domain_file, problem_file)
        self.problem = problem # need this later
        self.final_truth = set()
        self.head, self.tail, self.length, self.initial_truth, self.goal = problem_to_plan_list(problem)

    def analyze_dependencies(self):
        self.__clear_metadata()
        if not self.__replay():
            self.__clear_metadata()
            return False
        self.__build_support_links()
        return True

    def __clear_metadata(self):
        self.final_truth = set()
        traversal = self.head
        while traversal is not None:
            traversal.truth_before = set()
            traversal.truth_after = set()
            traversal.supports = []
            traversal.supported_by = []
            traversal = traversal.next

    def __replay(self):
        truth_before = set(self.initial_truth)
        truth_final = truth_before
        traversal = self.head

        while traversal is not None:
            if not expr_tools.is_true(traversal.precondition, truth_before):
                return False

            traversal.truth_before = truth_before # record state before applying effects

            truth_after = set(truth_before)
            apply_effects(truth_after, traversal.effect)
            traversal.truth_after = truth_after
            truth_final = truth_after

            traversal.goals_so_far = truth_after.intersection(expr_tools.walk_logical_expr(self.goal))
            if traversal.prev is not None:
                traversal.goals_just_added = traversal.goals_so_far - traversal.prev.goals_so_far

            traversal = traversal.next
            truth_before = truth_after # "truth after" for this node becomes the "truth before" for next node

        self.final_truth = truth_final
        return True

    def __build_support_links(self):
        def find_latest_supporter(action, required_pred):
            traversal = action.prev
            while traversal is not None:
                if required_pred in traversal.get_added_effects():
                    # let's make sure this required predicate wasn't
                    # deleted between this action A and action B
                    deleted = False
                    begin = traversal.next
                    while begin is not None and begin is not action:
                        if required_pred in begin.get_removed_effects():
                            deleted = True
                            break
                        begin = begin.next

                    if not deleted:
                        return traversal
                    # end of checking
                traversal = traversal.prev
            return None

        b = self.head
        while b is not None:
            for pred in expr_tools.walk_logical_expr(b.precondition):
                a = find_latest_supporter(b, pred)
                if a is not None:
                    if b not in a.supports:
                        a.supports.append(b)
                    if a not in b.supported_by:
                        b.supported_by.append(a)
            b = b.next

    def print(self):
        traversal = self.head
        while traversal is not None:
            print("Action:", traversal.label)
            print("Supports:", traversal.supports)
            print("Supported by:", traversal.supported_by)
            print("~~~")
            traversal = traversal.next

    def obfuscate_alternating(self):
        if self.head is None or self.head.next is None:
            return

        # because python sets don't preserve insertion order :(
        # this should be more accurately called _mostly_ in order
        goals_in_order = []
        traversal = self.head
        while traversal:
            if traversal.goals_just_added:
                goals_in_order.extend(list(traversal.goals_just_added))
            traversal = traversal.next
        
        # can't really do much here with a single goal or no goal (the latter shouldn't happen, hopefully)
        if len(goals_in_order) <= 1:
            return

        goals = goals_in_order.copy()
        while True:
            random.shuffle(goals)
            if goals != goals_in_order:
                break

        old_head = self.head
        old_tail = self.tail
        old_len = self.length
        self.head = None
        self.tail = None
        current_truth = self.initial_truth
        while goals:
            goal = goals.pop()
            subproblem = self.problem.clone()
            problem_set_goal(subproblem, set([goal]))
            problem_set_init_preds(subproblem, current_truth)
            begin, end, length, _, _ = problem_to_plan_list(subproblem)
            if self.head is None:
                self.head = begin
                self.tail = end
                self.length = length
            else:
                self.tail.next = begin
                begin.prev = self.tail
                self.tail = end
                self.length += length

            if self.analyze_dependencies():
                current_truth = self.final_truth
            else:
                self.head = old_head
                self.tail = old_tail
                self.length = old_len
                self.analyze_dependencies()
                break

    def obfuscate_multitasking(self):
        pass

    def obfuscate_diverting(self, max_insertions=3):
        def generate_detour(node):
            detours = []
            truth = node.truth_after
            problem = self.problem
            # every schema (InstantanousAction) has the action, precondition, and effects
            for schema in problem.actions:
                params: list[Parameter] = schema.parameters # List of "type name" e.g., "location from", parameters of an action function.
                preconds: FNode = And(schema.preconditions)
                # Very, very slow. But I'm crunched on time.
                possible_args: [[FNode]] = []
                for param in params:
                    obs = list(problem.objects(param.type))
                    possible_args.append(map(ObjectExp, obs))
                for args in itertools.product(*possible_args):
                    binding: dict[Parameter, FNode] = { # Map parameters to arguments as key-value pairs {type name: arg, ...}
                        params[i]: args[i]
                        for i in range(len(params))
                    }
                    grounded_pre: FNode = grounder.grounded_precondition(schema, binding) # Precondition with the arguments substituted instead of "type name"
                    assert truth != node.truth_before, "Should not be equal"
                    if not expr_tools.is_true(grounded_pre, truth):
                        continue
                    else: # Found a detour that doesn't violate the previous node's preconditions!
                        label = schema.name + str(args)
                        grounded_eff: dict[str, bool] = grounder.grounded_effects(schema, binding) # Effects applied at this action, mapping grounded predicates -> boolean result
                        delta: Set[str] = compute_delta(truth, grounded_eff) # Convert delta with given args in mind to get a set of added and removed (preceded with -) predicates
                        detour = PlanNode(label, grounded_pre, delta)
                        # On second thoughts, avoid it if it contributes toward goal
                        if detour.get_added_effects().intersection(expr_tools.walk_logical_expr(self.goal)):
                            continue
                        detour.truth_before = truth
                        detour.truth_after = set(truth) # this took me an embarrasingly long time to debug (I forgot I was assigning references and not copies)
                        apply_effects(detour.truth_after, delta) 
                        detours.append(detour)
            return detours[random.randint(0, len(detours) - 1)] if len(detours) != 0 else None

        def generate_detour_chain(node):
            res = generate_detour(node)
            if res:
                subproblem = self.problem.clone()
                problem_set_init_preds(subproblem, res.truth_after)
                begin, end, length, _, _ = problem_to_plan_list(subproblem)
                res.next = begin
                begin.prev = res
                return res, end, length+1
            return None

        inserted = 0
        traversal = self.head
        i = 1
        while traversal and inserted < max_insertions:
            if traversal.next and random.randint(0,10) == 10:
                detour = generate_detour_chain(traversal)
                if detour is None:
                    continue
                begin, end, sublen = detour
                old_next = traversal.next
                traversal.next = begin
                if self.analyze_dependencies():
                    begin.prev = traversal
                    tail = end
                    inserted += 1
                    self.length = i + sublen
                else:
                    traversal.next = old_next
                    self.analyze_dependencies()
            i += 1
            traversal = traversal.next

    def get_visual(self):
        dot = graphviz.Digraph()
        dot.attr(rankdir='LR')

        traversal = self.head
        i = 1
        while traversal is not None:
            dot.node(traversal.key(), str(i))
            i += 1
            traversal = traversal.next
        traversal = self.head
        while traversal is not None:
            if traversal.next is not None:
                dot.edge(traversal.key(), traversal.next.key())

            if traversal.goals_just_added:
                dot.node(traversal.key(), style="filled", fillcolor="green")

            for supports in traversal.supports:
                dot.edge(traversal.key(), supports.key(), color="blue", dir='none')

            traversal = traversal.next
        return dot

    def export_data(self, filename):
        traversal = self.head
        with open(f"{filename}.txt", "w") as f:
            i = 1
            while traversal:
                f.write(f"{i}. {traversal.label}\n")
                f.write(f"\tsupports: {traversal.supports}\n")
                f.write(f"\tsupported by: {traversal.supported_by}\n")
                f.write("\n")
                i += 1
                traversal = traversal.next
        self.get_visual().render(f"{filename}.gv", format="pdf")



# ==========================================================
# Truth Delta
# ==========================================================

def compute_delta(current_truth: Set[str], effects: Dict[str, bool] ) -> Set[str]:
    delta = set()
    for lit, val in effects.items():
        if val:
            if lit not in current_truth:
                delta.add(lit)
        else:
            if lit in current_truth:
                delta.add("-" + lit)
    return delta


def apply_effects(truth: Set[str], delta: Set[str]):
    for item in delta:
        if item.startswith("-"):
            truth.discard(item[1:])
        else:
            truth.add(item)

# ==========================================================
# Helper for PlanList
# ==========================================================

def problem_set_goal(problem, truths: Set[str]):
    problem.clear_goals()
    problem.add_goal(And(*grounder.grounded_predicates(problem, truths)))

def problem_set_init_preds(problem, truths: Set[str]):
    problem.explicit_initial_values.clear()
    for predicate in grounder.grounded_predicates(problem, truths):
        problem.set_initial_value(predicate, True)

def problem_to_plan_list(problem):
    with OneshotPlanner(name="fast-downward") as planner:
        result: PlanGenerationResult = planner.solve(problem)
    if result.plan is None:
        raise RuntimeError("No plan found.")

    plan: Plan = result.plan
    goal = And(problem.goals)

    # initialize truths (universe of grounded predicates) from parsed problem
    current_truth: Set[str] = set()
    for fluent_exp, val in problem.initial_values.items():
        if str(val).lower() == "true":
            current_truth.add(str(fluent_exp))
    initial_truth: Set[str] = set(current_truth)

    head = None
    tail = None

    for ai in plan.actions:
        schema: InstantaneousAction = ai.action # Contains the action, precondition, and effects (for classicial planning this is unified_planning.model.action.InstantaneousAction).
        params: list[Parameter] = schema.parameters # List of "type name" e.g., "location from", parameters of an action function.
        args: Tuple[FNode, ...] = ai.actual_parameters # Arguments passed to the action, represented as a tuple.
        binding: dict[Parameter, FNode] = { # Map parameters to arguments as key-value pairs {type name: arg, ...}
            params[i]: args[i]
            for i in range(len(params))
        }

        grounded_pre: FNode = grounder.grounded_precondition(schema, binding) # Precondition with the arguments substituted instead of "type name"
        grounded_eff: dict[str, bool] = grounder.grounded_effects(schema, binding) # Effects applied at this action, mapping grounded predicates -> boolean result
        
        delta: Set[str] = compute_delta(current_truth, grounded_eff) # Convert delta with given args in mind to get a set of added and removed (preceded with -) predicates
        apply_effects(current_truth, delta) # Then apply them to affect the current truth

        node = PlanNode(str(ai), grounded_pre, delta)
        if head is None:
            head = node
            tail = node
        else:
            tail.next = node
            node.prev = tail
            tail = node

    return head, tail, len(plan.actions), initial_truth, goal

# ==========================================================
# Main
# ==========================================================

get_environment().credits_stream = None
parser = argparse.ArgumentParser()
parser.add_argument("file", nargs=2, help="requires domain and problem pddl files, in that order.")
parser.add_argument('-s', '--seed', type=int, default=None, help="optional random seed used by the obfuscation algorithms.")
args = parser.parse_args()
if args.file is None:
    parser.print_help()
else:
    random.seed(args.seed)
    plan = PlanList(args.file[0], args.file[1])
    plan.analyze_dependencies()
    plan.export_data("genplan_01_original")
    print("Original plan exported ...")
    plan.obfuscate_alternating()
    plan.export_data("genplan_02_alternating")
    print("Obfuscated plan (Alternating) exported ...")
    plan.obfuscate_diverting()
    plan.export_data("genplan_03_diverting")
    print("Obfuscated plan (Diverting) exported ...")
    print("genplan_* files exported ...")
