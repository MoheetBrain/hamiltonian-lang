"""Tier 3 -- executable, property-based counterexample search.

The asymmetry, restated because it is the whole point of this module: **finding a
disagreement disproves equivalence; finding none proves nothing.** The return type
is therefore a union of two *different* classes --
:class:`~.status.Counterexample` and :class:`~.status.NoRefutation` -- and the
second one is not accepted anywhere a certificate is required. There is no code
path from "searched and found nothing" to ``VERIFIED_EQUIVALENT``, and
:func:`~.status.register_certifying_method` refuses to create one.

Sampling respects the declared types, so a ``Probability`` is never handed 1.7 and
a ``PositiveReal`` is never handed 0. Samples that violate an ``assume`` statement
are discarded rather than counted, because a disagreement outside the assumed
domain is not a counterexample.

Sampling is deterministic. A scoring engine whose verdict depends on the seed is
not a measurement instrument.
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..types import QuantityType, ScalarType, Type
from .status import Counterexample, NoRefutation
from .sympy_bridge import SYMPY_AVAILABLE

if SYMPY_AVAILABLE:  # pragma: no branch - sympy is present on this host
    import sympy

__all__ = [
    "SEED",
    "DEFAULT_BUDGET",
    "domain_for",
    "sample_assignments",
    "evaluate",
    "search_disagreement",
    "varies_with",
]

#: Fixed so a verdict is reproducible. Never expose this as a tunable.
SEED = 20260805
DEFAULT_BUDGET = 400


def _rat(n: int, d: int = 1) -> Any:
    return sympy.Rational(n, d)


def _domain_values(name: str) -> list[Any]:
    table: dict[str, list[Any]] = {
        "Bool": [sympy.true, sympy.false],
        "Natural": [_rat(0), _rat(1), _rat(2), _rat(3), _rat(7)],
        "PositiveNatural": [_rat(1), _rat(2), _rat(3), _rat(7)],
        "Integer": [_rat(-3), _rat(-1), _rat(0), _rat(1), _rat(3)],
        "Rational": [_rat(-3), _rat(-1, 2), _rat(0), _rat(1, 3), _rat(2), _rat(5)],
        "Real": [_rat(-3), _rat(-1, 2), _rat(0), _rat(1, 3), _rat(2), _rat(5)],
        "NonNegativeReal": [_rat(0), _rat(1, 3), _rat(1), _rat(7, 2)],
        "PositiveReal": [_rat(1, 5), _rat(1), _rat(2), _rat(7, 2)],
        "Probability": [_rat(0), _rat(1, 4), _rat(1, 2), _rat(3, 4), _rat(1)],
        "PValue": [_rat(0), _rat(1, 4), _rat(1, 2), _rat(3, 4), _rat(1)],
        "PosteriorProbability": [_rat(0), _rat(1, 4), _rat(1, 2), _rat(3, 4), _rat(1)],
    }
    return table.get(name, table["Real"])


def domain_for(t: Type | None) -> list[Any]:
    """Admissible sample values for a declared type.

    An unknown or unsupported type falls back to the ``Real`` grid. That is a
    coverage choice, not a soundness one: a disagreement found on the fallback
    grid is still checked against the assumptions before it is reported.
    """
    if isinstance(t, ScalarType):
        return _domain_values(t.name)
    if isinstance(t, QuantityType):
        return _domain_values(t.base.name)
    return _domain_values("Real")


def _as_python(value: Any) -> Any | None:
    try:
        if value.is_Integer:
            return int(value)
        if value.is_Rational or value.is_Float:
            return float(value)
    except AttributeError:
        return None
    return None


def harvest_hints(
    exprs: Sequence[Any],
    symbols: Mapping[str, Any],
    symbol_types: Mapping[str, Type | None],
) -> dict[str, list[Any]]:
    """Extra values worth trying, taken from the expressions themselves.

    A fixed grid misses the point where two equations disagree: ``2*x = 6`` and
    ``x = 6`` agree everywhere except at 3 and 6, and neither is on any sensible
    default grid. So the constants appearing in the pair are tried, and equalities
    are solved for each free symbol. Every hint is filtered through
    :func:`~hamiltonian_lang.types.literal_inhabits`, so a hint outside a declared
    type's domain is discarded rather than used to fabricate a counterexample.
    """
    from ..types import literal_inhabits

    constants: list[Any] = []
    for expr in exprs:
        if expr is None:
            continue
        for node in sympy.preorder_traversal(expr):
            if getattr(node, "is_number", False) and not node.free_symbols:
                constants.append(node)

    hints: dict[str, list[Any]] = {}
    for name, symbol in symbols.items():
        declared = symbol_types.get(name)
        found: list[Any] = list(constants)
        for expr in exprs:
            if expr is None or symbol not in getattr(expr, "free_symbols", set()):
                continue
            for node in sympy.preorder_traversal(expr):
                if isinstance(node, sympy.Equality):
                    try:
                        roots = sympy.solve(node, symbol, dict=False)
                    except (NotImplementedError, TypeError, ValueError, AttributeError):
                        continue
                    found.extend(r for r in roots if not getattr(r, "free_symbols", set()))
        admissible: list[Any] = []
        for value in found:
            plain = _as_python(value)
            if plain is None:
                continue
            if declared is not None and not literal_inhabits(plain, declared):
                continue
            if value not in admissible:
                admissible.append(value)
        if admissible:
            hints[name] = admissible[:8]
    return hints


def sample_assignments(
    symbol_types: Mapping[str, Type | None],
    symbols: Mapping[str, Any],
    budget: int = DEFAULT_BUDGET,
    hints: Mapping[str, Sequence[Any]] | None = None,
) -> list[dict[Any, Any]]:
    """Deterministic assignments covering the declared domains."""
    names = sorted(symbols)
    if not names:
        return [{}]
    extra = dict(hints or {})
    grids: list[list[Any]] = []
    for n in names:
        grid = list(domain_for(symbol_types.get(n)))
        for value in extra.get(n, ()):
            if value not in grid:
                grid.append(value)
        grids.append(grid)
    total = 1
    for g in grids:
        total *= len(g)
    if total <= budget:
        combos: Sequence[tuple[Any, ...]] = list(itertools.product(*grids))
    else:
        rng = random.Random(SEED)
        seen: set[tuple[str, ...]] = set()
        combos = []
        # Corners first: all-lowest and all-highest often expose the disagreement.
        for corner in (0, -1):
            combos.append(tuple(g[corner] for g in grids))
        while len(combos) < budget:
            pick = tuple(rng.choice(g) for g in grids)
            key = tuple(str(v) for v in pick)
            if key in seen:
                continue
            seen.add(key)
            combos.append(pick)
    return [dict(zip([symbols[n] for n in names], combo, strict=True)) for combo in combos]


def evaluate(expr: Any, assignment: Mapping[Any, Any]) -> Any | None:
    """Numeric or boolean value of ``expr`` under ``assignment``, or None.

    None means *this sample says nothing*: a division by zero, a complex result,
    or anything that did not reduce to a value. Treating such a sample as a
    disagreement would manufacture counterexamples out of undefined points.
    """
    try:
        substituted = expr.subs(assignment)
        substituted = substituted.doit() if hasattr(substituted, "doit") else substituted
        value = sympy.simplify(substituted)
    except (TypeError, ValueError, ZeroDivisionError, AttributeError, NotImplementedError):
        return None
    if value in (sympy.true, sympy.false):
        return bool(value)
    if isinstance(value, bool):
        return value
    if value.has(sympy.zoo) or value.has(sympy.nan) or value.has(sympy.oo):
        return None
    if value.free_symbols:
        return None
    try:
        numeric = complex(value)
    except (TypeError, ValueError):
        return None
    if abs(numeric.imag) > 1e-12:
        return None
    return numeric.real


def _disagrees(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(left) != bool(right)
    return abs(left - right) > 1e-9 * max(1.0, abs(left), abs(right))


@dataclass(frozen=True)
class _Sample:
    assignment: dict[Any, Any]
    left: Any
    right: Any


def search_disagreement(
    left: Any,
    right: Any,
    symbols: Mapping[str, Any],
    symbol_types: Mapping[str, Type | None],
    *,
    constraints: Sequence[Any] = (),
    budget: int = DEFAULT_BUDGET,
    label: str = "",
) -> Counterexample | NoRefutation:
    """Look for a value at which the two sides differ.

    Returns a :class:`~.status.Counterexample` on success and a
    :class:`~.status.NoRefutation` otherwise. The second is deliberately a
    different type; it cannot be turned into evidence of equivalence.
    """
    if not SYMPY_AVAILABLE:  # pragma: no cover
        return NoRefutation("tier3.numeric_counterexample", 0, "sympy is not importable")
    tried = 0
    skipped = 0
    hints = harvest_hints([left, right], symbols, symbol_types)
    for assignment in sample_assignments(symbol_types, symbols, budget, hints):
        if any(evaluate(c, assignment) is not True for c in constraints):
            skipped += 1
            continue
        lv = evaluate(left, assignment)
        rv = evaluate(right, assignment)
        if lv is None or rv is None:
            skipped += 1
            continue
        tried += 1
        if _disagrees(lv, rv):
            return Counterexample(
                "tier3.numeric_counterexample",
                f"the two sides disagree{f' in {label}' if label else ''} at a value "
                f"admitted by the declared types and the stated assumptions",
                assignment={str(k): str(v) for k, v in assignment.items()},
                left_value=str(lv),
                right_value=str(rv),
            )
    return NoRefutation(
        "tier3.numeric_counterexample",
        tried,
        f"{tried} admissible sample(s) evaluated, {skipped} skipped as undefined or "
        f"outside the assumptions; no disagreement was exhibited. This is not evidence "
        f"of equivalence",
    )


def varies_with(
    expr: Any,
    target: Any,
    symbols: Mapping[str, Any],
    symbol_types: Mapping[str, Type | None],
    *,
    budget: int = 200,
) -> dict[str, str] | None:
    """Witness that ``expr``'s value genuinely depends on ``target``.

    Returns the witnessing pair of assignments, or None. A positive answer is a
    *proof* of dependence: two assignments agreeing everywhere except ``target``
    and yielding different values mean no formula without ``target`` can be
    equivalent to ``expr``. A negative answer proves nothing, and callers must not
    read it as independence.
    """
    if not SYMPY_AVAILABLE:  # pragma: no cover
        return None
    others = {n: s for n, s in symbols.items() if s != target}
    target_name = next((n for n, s in symbols.items() if s == target), None)
    if target_name is None:
        return None
    target_values = domain_for(symbol_types.get(target_name))
    for assignment in sample_assignments(symbol_types, others, budget):
        seen: list[tuple[Any, Any]] = []
        for value in target_values:
            full = dict(assignment)
            full[target] = value
            got = evaluate(expr, full)
            if got is None:
                continue
            seen.append((value, got))
        for (v1, r1), (v2, r2) in itertools.combinations(seen, 2):
            if _disagrees(r1, r2):
                base = {str(k): str(v) for k, v in assignment.items()}
                return {
                    **base,
                    f"{target_name}(first)": str(v1),
                    f"{target_name}(second)": str(v2),
                    "value(first)": str(r1),
                    "value(second)": str(r2),
                }
    return None
