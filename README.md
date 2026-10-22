# Dependency Analysis and Plan Obfuscator
This project was created for the Spring 2026 CS 690 004 Human-Robot Interaction course at George Mason University. The goal is to defend against adversial observers inferring the goal of a resolved plan.

Dependency Analysis does the following:
* Replay the plan ensuring actions are valid by checking preconditions. Keep track of environment's predicates before and after execution of action.
* Determine how one action depends on one or more previous actions, then build support edges.

The following obfuscation algorithms are implemented:
* _Alternating_ - If the plan achieves several subgoals, reorder how these subgoals are visited.
* _Diverting_ - Introduce noise to the plan by adding detour actions.

AI assistance used with permission from the course's instructor. For more information, writeup can be found in the `docs` directory.

## Setup
Clone the repository first. Inside the directory, create the virtual environment:
```
python -m venv env
```

Activiate the virtual environment using the appropiate command for your system: https://docs.python.org/3/library/venv.html#how-venvs-work

Install the required libraries:
```
pip install -r requirements.txt
```

You should be ready to use the program.

## Program Usage
```
plan_obfuscator_v2.py [-h] [-s SEED] domain_pddl_file problem_pddl_file
```
The only required arguments are domain and problem files, in that exact order. A numeric seed can be optionally set for consistent results. The output will be the following files:
```
genplan_01_original.gv
genplan_01_original.gv.pdf
genplan_01_original.txt
genplan_02_alternating.gv
genplan_02_alternating.gv.pdf
genplan_02_alternating.txt
genplan_03_diverting.gv
genplan_03_diverting.gv.pdf
genplan_03_diverting.txt
```
`.gv` files, rather than `.gv.pdf` files, are auxiliary files that can be ignored. They are created by the graphviz library before generating the pdf files.

## Test Files
`domain.pddl` and `problem.pddl` are obtained from https://github.com/dporfirio/ISL-Parser/tree/main/islparser/pddl/healthcare_goals. You will need to modify the problem file to use a complex goal (e.g., using `and` operators) as _Alternating_ does not support goals with only one predicate.
