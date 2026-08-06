"""The frozen twelve-cell ACQ0 development taxonomy, and which task carries which cell.

Why a taxonomy at all
---------------------
"Twelve tasks" is not a specification. Without one, a corpus drifts toward whatever is easy
to author, and a surface can win by being good at the four things that happen to be
over-represented. The cells below are the features a candidate surface must express; the
matrix says which task is evidence for which cell, and the coverage rules say where one
carrier is not enough.

A cell with exactly one carrier is fragile: reject that task in review and the feature
leaves the corpus silently. Every rule in :data:`COVERAGE_RULES` exists because losing that
cell would change what the experiment measures rather than merely shrinking it.

This file is the authority. `docs/evaluation/ACQ0_V2_TAXONOMY.md` is generated from it, and
`tests/evaluation/test_taxonomy_coverage.py` fails if the corpus stops satisfying it.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Cell", "CELLS", "TASK_CELLS", "COVERAGE_RULES", "coverage_report",
           "TaxonomyGap"]


class TaxonomyGap(RuntimeError):
    """The corpus no longer covers the frozen taxonomy."""


@dataclass(frozen=True)
class Cell:
    number: int
    name: str
    what_it_tests: str


CELLS: tuple[Cell, ...] = (
    Cell(1, "binding and dependency order",
         "a later definition depends on an earlier one; order is content"),
    Cell(2, "assumptions versus requirements",
         "a supplied premise and a domain constraint are different statements"),
    Cell(3, "implication direction",
         "p => q is not q => p, and neither is a biconditional"),
    Cell(4, "two-sided approximation or equality boundary",
         "a bounded difference is not an equality; one inequality is not two"),
    Cell(5, "quantifier order and scope",
         "forall-exists and exists-forall are different propositions"),
    Cell(6, "probability-law named roles",
         "prior/likelihood, the conditioning set, and each named role"),
    Cell(7, "dimensional algebra",
         "rational-exponent dimension vectors, and their normalisation"),
    Cell(8, "transformation side conditions",
         "the condition a rewrite depends on, stated rather than assumed"),
    Cell(9, "objective-bearing proof task",
         "a `prove` goal, declared by an objective of matching kind"),
    Cell(10, "objective-bearing check or construction task",
         "a `check` goal discharged by a `decide` objective (D-031)"),
    Cell(11, "intentionally state-only, state_in_prose=True",
         "a consequence stated in prose that must NOT be encoded"),
    Cell(12, "mixed-order multi-statement, state_in_prose=False",
         "interleaved statement kinds; the direct carrier for the D-030 defect"),
)

#: task_id -> the cells it carries. A task may carry several; a cell may have several.
TASK_CELLS: dict[str, tuple[int, ...]] = {
    "v2_binding_dependency_001": (1,),
    "v2_assumption_boundary_001": (2, 12),
    "v2_implication_equivalence_001": (3,),
    "v2_approximation_equality_002": (4,),
    "v2_quantifier_scope_001": (5,),
    "v2_probability_law_role_001": (6,),
    "v2_dimensional_algebra_002": (7,),
    "v2_transformation_side_condition_001": (8, 2),
    "v2_quantifier_scope_003": (9, 5, 11, 3),
    "v2_dimensional_algebra_004": (10, 7),
    "v2_probability_law_role_002": (11, 6),
    "v2_assumption_boundary_002": (12, 2, 1),
    # sealed spares: admitted, never scored, and held for the two highest-risk cells
    "v2_dimensional_algebra_spare_001": (10, 7),
    "v2_implication_equivalence_spare_001": (9, 3),
}

#: label -> (predicate description, minimum count). Checked over the twelve development
#: tasks only; the spares are replacements, not coverage.
COVERAGE_RULES: tuple[tuple[str, int], ...] = (
    ("objective-bearing tasks", 2),
    ("state_in_prose=True tasks", 2),
    ("CheckStmt tasks", 2),
    ("dimensional tasks", 2),
    ("probability-role tasks", 2),
    ("quantifier/scope tasks", 2),
)


def _counts(tasks) -> dict[str, int]:
    from hamiltonian_lang.ast.nodes import CheckStmt, Quantifier

    def has_quantifier(task) -> bool:
        from hamiltonian_lang.backends.hml import render_expr
        for st in task.module.statements:
            for attr in ("body", "proposition", "subject"):
                node = getattr(st, attr, None)
                if node is not None and ("forall" in render_expr(node)
                                         or "exists" in render_expr(node)):
                    return True
        return False

    assert Quantifier  # the node the surface form above stands for
    return {
        "objective-bearing tasks": sum(t.objective is not None for t in tasks),
        "state_in_prose=True tasks": sum(
            any(f.state_in_prose for f in t.derived_facts) for t in tasks),
        "CheckStmt tasks": sum(
            any(isinstance(s, CheckStmt) for s in t.module.statements) for t in tasks),
        "dimensional tasks": sum("dimensional" in t.task_id for t in tasks),
        "probability-role tasks": sum("probability_law_role" in t.task_id for t in tasks),
        "quantifier/scope tasks": sum(has_quantifier(t) for t in tasks),
    }


def coverage_report(tasks) -> dict[str, object]:
    """Which cells are carried, by how many tasks, and whether every rule is met."""
    carriers: dict[int, list[str]] = {c.number: [] for c in CELLS}
    unknown = []
    for task in tasks:
        cells = TASK_CELLS.get(task.task_id)
        if cells is None:
            unknown.append(task.task_id)
            continue
        for n in cells:
            carriers[n].append(task.task_id)

    counts = _counts(tasks)
    both_flags = {
        True: sum(any(f.state_in_prose for f in t.derived_facts) for t in tasks),
        False: sum(any(not f.state_in_prose for f in t.derived_facts) for t in tasks),
    }
    return {
        "carriers": carriers,
        "uncovered": [n for n, ids in carriers.items() if not ids],
        "single_carrier": [n for n, ids in carriers.items() if len(ids) == 1],
        "counts": counts,
        "unmet_rules": [(label, need, counts[label])
                        for label, need in COVERAGE_RULES if counts[label] < need],
        "unknown_tasks": unknown,
        "both_state_in_prose_values": both_flags[True] > 0 and both_flags[False] > 0,
    }
