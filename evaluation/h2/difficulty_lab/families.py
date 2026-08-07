"""Four neutral synthetic task generators with deterministic oracles.

The previous calibration saturated at 10/10 on canonical textbook semantic traps, and the
only difficulty axis it found was *length* — which is invalid here, because HML is more
verbose than prose and a length-limited corpus would measure verbosity while appearing to
measure reasoning.

So difficulty in this lab comes from **interacting state**: how many facts must be held at
once, how deep the dependency chain runs, how many distractors compete, how many
quantifier alternations must be tracked. Every oracle is cheap and every answer fits on
one line, so a harder task is not a longer one.

**Neutrality.** Structures are generated in Python and the English is rendered *from* the
structure. Nothing here is written in HML first and translated, because a benchmark built
that way would be native to HML by construction and could not fairly test it. Whether a
generated structure is expressible in HML is a separate question, asked later.

**Oracles.** Exact `Fraction` arithmetic for algebra; exhaustive enumeration for the
finite worlds. No LLM judges anything.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from itertools import product
from typing import Literal

__all__ = [
    "Specimen",
    "LEVELS",
    "FAMILIES",
    "generate",
    "GENERATOR_VERSION",
]

GENERATOR_VERSION = "difficulty-lab-1.0.0"

Family = Literal[
    "ALGEBRAIC_DEPENDENCY_GRAPH",
    "FINITE_LOGIC_WORLD",
    "FINITE_QUANTIFIER_WORLD",
    "MIXED_STATE_COMPOSITION",
]


@dataclass
class Specimen:
    task_id: str
    family: str
    generator_version: str
    seed: int
    level: str
    domain: str
    prompt: str
    answer: str
    answer_format: str
    #: State-complexity metrics -- the thing being varied, recorded so a later analysis can
    #: correlate difficulty with structure rather than with prose length.
    metrics: dict = field(default_factory=dict)
    oracle: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


#: Five levels. Difficulty is MORE INTERACTING STATE, never a longer requested answer.
LEVELS: dict[str, dict] = {
    "L1": {"facts": 5, "depth": 3, "distractors": 1, "vars": 4, "alternations": 1},
    "L2": {"facts": 7, "depth": 4, "distractors": 1, "vars": 5, "alternations": 1},
    "L3": {"facts": 9, "depth": 5, "distractors": 2, "vars": 6, "alternations": 2},
    "L4": {"facts": 12, "depth": 7, "distractors": 3, "vars": 7, "alternations": 2},
    "L5": {"facts": 15, "depth": 9, "distractors": 4, "vars": 8, "alternations": 3},
    # L6/L7 extend the scale after L3 and L5 both came back 3/3 with no truncation.
    # This is tuning the levels to the generators, which the protocol asks for -- it is
    # NOT escalating length: the answer is still one line and every oracle is still
    # cheap. Only the amount of interacting state grows.
    "L6": {"facts": 20, "depth": 12, "distractors": 5, "vars": 9, "alternations": 3},
    "L7": {"facts": 26, "depth": 16, "distractors": 6, "vars": 10, "alternations": 3},
}

_ANSWER_RULE = (
    "Reason concisely. Do not restate the problem. "
    "End with exactly one line of the form:\nFINAL: <answer>"
)


# ---------------------------------------------------------------------------
# A. ALGEBRAIC_DEPENDENCY_GRAPH
# ---------------------------------------------------------------------------


def _algebraic(rng: random.Random, level: str, task_id: str) -> Specimen:
    """A DAG of exact rational definitions, with distractor branches.

    Every internal variable is an integer combination of two earlier ones, so the oracle
    is exact `Fraction` arithmetic and the arithmetic itself stays small. The work is
    holding the chain, not the multiplication.
    """
    p = LEVELS[level]
    depth, n_dis = p["depth"], p["distractors"]
    names = [f"v{i}" for i in range(depth + n_dis + 2)]
    rng.shuffle(names)

    value: dict[str, Fraction] = {}
    lines: list[str] = []

    # Two roots.
    for r in names[:2]:
        value[r] = Fraction(rng.randint(2, 9))
        lines.append(f"{r} = {value[r]}")

    chain = names[2 : 2 + depth]
    pool = names[:2]
    for nm in chain:
        a, b = rng.sample(pool, 2) if len(pool) >= 2 else (pool[0], pool[0])
        ca, cb = rng.randint(2, 5), rng.randint(1, 4)
        op = rng.choice(["+", "-"])
        value[nm] = ca * value[a] + cb * value[b] if op == "+" else ca * value[a] - cb * value[b]
        lines.append(f"{nm} = {ca} * {a} {op} {cb} * {b}")
        pool.append(nm)

    target = chain[-1]

    # Distractors: valid definitions that the target does not depend on.
    for nm in names[2 + depth : 2 + depth + n_dis]:
        a, b = rng.sample(pool, 2)
        ca, cb = rng.randint(2, 5), rng.randint(1, 4)
        value[nm] = ca * value[a] + cb * value[b]
        lines.append(f"{nm} = {ca} * {a} + {cb} * {b}")

    rng.shuffle(lines)
    body = "\n".join("  " + ln for ln in lines)
    prompt = (
        "All variables below are exact rational numbers. The definitions may be given "
        "in any order.\n\n"
        f"{body}\n\n"
        f"Determine the exact value of {target}.\n\n"
        f"{_ANSWER_RULE}"
    )
    ans = value[target]
    return Specimen(
        task_id=task_id,
        family="ALGEBRAIC_DEPENDENCY_GRAPH",
        generator_version=GENERATOR_VERSION,
        seed=0,
        level=level,
        domain="exact algebra",
        prompt=prompt,
        answer=str(ans.numerator) if ans.denominator == 1 else str(ans),
        answer_format="an exact integer or fraction",
        metrics={
            "n_facts": len(lines),
            "n_relevant_facts": depth + 2,
            "n_distractors": n_dis,
            "dependency_depth": depth,
        },
        oracle="exact Fraction arithmetic",
    )


# ---------------------------------------------------------------------------
# B. FINITE_LOGIC_WORLD
# ---------------------------------------------------------------------------

_LOGIC_TEMPLATES = [
    ("{a} implies {b}", lambda A, B: (not A) or B),
    ("if {a} then {b}", lambda A, B: (not A) or B),
    ("{a} and {b} cannot both hold", lambda A, B: not (A and B)),
    ("at least one of {a} and {b} holds", lambda A, B: A or B),
    ("{a} holds if and only if {b} holds", lambda A, B: A == B),
    ("{a} does not hold unless {b} holds", lambda A, B: (not A) or B),
]


def _logic(rng: random.Random, level: str, task_id: str) -> Specimen:
    """A satisfiable propositional world; the query may be UNDETERMINED.

    The three-way answer is the point. A model that assumes every query is decided will
    confidently answer TRUE or FALSE where the constraints leave it open, and that is a
    reasoning error rather than an arithmetic one.
    """
    p = LEVELS[level]
    n = p["vars"]
    names = [f"P{i+1}" for i in range(n)]

    for _ in range(200):
        constraints = []
        for _ in range(p["facts"]):
            a, b = rng.sample(names, 2)
            text, fn = rng.choice(_LOGIC_TEMPLATES)
            constraints.append((text.format(a=a, b=b), a, b, fn))
        # A couple of asserted facts to anchor the world.
        anchors = rng.sample(names, min(2, n))
        anchor_vals = {nm: rng.choice([True, False]) for nm in anchors}

        models = []
        for combo in product([False, True], repeat=n):
            asg = dict(zip(names, combo, strict=True))
            if any(asg[nm] is not v for nm, v in anchor_vals.items()):
                continue
            if all(fn(asg[a], asg[b]) for _, a, b, fn in constraints):
                models.append(asg)
        if not models:
            continue

        query = rng.choice(names)
        vals = {m[query] for m in models}
        answer = "TRUE" if vals == {True} else "FALSE" if vals == {False} else "UNDETERMINED"
        # Prefer worlds that are not trivially all-TRUE: an UNDETERMINED or FALSE answer
        # is where the reasoning actually happens.
        if answer == "TRUE" and rng.random() < 0.6:
            continue
        break
    else:  # pragma: no cover - the retry loop essentially always succeeds
        raise RuntimeError("could not generate a satisfiable logic world")

    facts = [f"  {nm} holds." if v else f"  {nm} does not hold." for nm, v in anchor_vals.items()]
    facts += [f"  {t}." for t, _, _, _ in constraints]
    rng.shuffle(facts)
    prompt = (
        "Consider the following statements about propositions "
        f"{', '.join(names)}. All of them are true.\n\n"
        + "\n".join(facts)
        + f"\n\nIs {query} necessarily true, necessarily false, or is it not determined "
        "by these statements?\n\n"
        "Answer with exactly one of: TRUE, FALSE, UNDETERMINED.\n\n"
        f"{_ANSWER_RULE}"
    )
    return Specimen(
        task_id=task_id,
        family="FINITE_LOGIC_WORLD",
        generator_version=GENERATOR_VERSION,
        seed=0,
        level=level,
        domain="propositional logic",
        prompt=prompt,
        answer=answer,
        answer_format="TRUE, FALSE or UNDETERMINED",
        metrics={
            "n_facts": len(facts),
            "n_variables": n,
            "n_models": len(models),
            "n_constraints": len(constraints),
        },
        oracle=f"exhaustive enumeration over 2^{n} assignments",
    )


# ---------------------------------------------------------------------------
# C. FINITE_QUANTIFIER_WORLD
# ---------------------------------------------------------------------------


def _quantifier(rng: random.Random, level: str, task_id: str) -> Specimen:
    """A relation given as an explicit table, and a quantified claim over it.

    Quantifier ORDER is the difficulty: `forall x exists y R(x,y)` and
    `exists y forall x R(x,y)` differ on most tables, and only one enumeration settles it.
    """
    p = LEVELS[level]
    d = min(3 + p["alternations"], 5)
    elems = list(range(1, d + 1))
    table = {(a, b): rng.random() < 0.45 for a in elems for b in elems}

    forms = [
        ("for every x there exists a y such that R(x, y)",
         lambda: all(any(table[(a, b)] for b in elems) for a in elems)),
        ("there exists a y such that for every x, R(x, y)",
         lambda: any(all(table[(a, b)] for a in elems) for b in elems)),
        ("for every x and every y, if R(x, y) then R(y, x)",
         lambda: all((not table[(a, b)]) or table[(b, a)] for a in elems for b in elems)),
        ("there exists an x such that for every y, R(x, y) is false",
         lambda: any(all(not table[(a, b)] for b in elems) for a in elems)),
    ]
    text, fn = rng.choice(forms)
    answer = "TRUE" if fn() else "FALSE"

    pairs = sorted(f"({a},{b})" for a, b in table if table[(a, b)])
    prompt = (
        f"Let D = {{{', '.join(str(e) for e in elems)}}}.\n"
        "R is a relation on D. R(x, y) holds for exactly the following ordered pairs "
        "(x, y), and for no others:\n\n"
        f"  {', '.join(pairs) if pairs else '(none)'}\n\n"
        f"Is the following statement true or false?\n\n  {text}\n\n"
        "Answer with exactly one of: TRUE, FALSE.\n\n"
        f"{_ANSWER_RULE}"
    )
    return Specimen(
        task_id=task_id,
        family="FINITE_QUANTIFIER_WORLD",
        generator_version=GENERATOR_VERSION,
        seed=0,
        level=level,
        domain="finite quantification",
        prompt=prompt,
        answer=answer,
        answer_format="TRUE or FALSE",
        metrics={
            "domain_size": d,
            "n_true_pairs": len(pairs),
            "quantifier_alternations": 2,
        },
        oracle=f"exhaustive enumeration over {d}x{d} relation",
    )


# ---------------------------------------------------------------------------
# D. MIXED_STATE_COMPOSITION
# ---------------------------------------------------------------------------


def _mixed(rng: random.Random, level: str, task_id: str) -> Specimen:
    """Algebra gates logic: the numeric values decide which propositions hold.

    Requires both families' information. Neither half alone determines the answer, which
    is what makes this a composition rather than two tasks side by side.
    """
    p = LEVELS[level]
    depth = max(3, p["depth"] - 2)
    names = [f"a{i}" for i in range(depth + 2)]
    value: dict[str, Fraction] = {}
    lines: list[str] = []
    for r in names[:2]:
        value[r] = Fraction(rng.randint(2, 9))
        lines.append(f"{r} = {value[r]}")
    pool = names[:2]
    for nm in names[2:]:
        a, b = rng.sample(pool, 2)
        ca, cb = rng.randint(2, 4), rng.randint(1, 3)
        op = rng.choice(["+", "-"])
        value[nm] = ca * value[a] + cb * value[b] if op == "+" else ca * value[a] - cb * value[b]
        lines.append(f"{nm} = {ca} * {a} {op} {cb} * {b}")
        pool.append(nm)

    # Three numeric predicates, then a logical question over them.
    picks = rng.sample(list(value), 3)
    thresholds = [rng.randint(5, 40) for _ in picks]
    preds = [(f"Q{i+1}", nm, t, value[nm] > t) for i, (nm, t) in enumerate(zip(picks, thresholds, strict=True))]
    pred_text = "\n".join(f"  {q} holds exactly when {nm} > {t}." for q, nm, t, _ in preds)

    q1, q2, q3 = (p[3] for p in preds)
    forms = [
        ("Q1 and Q2", q1 and q2),
        ("Q1 or Q3", q1 or q3),
        ("Q2 implies Q3", (not q2) or q3),
        ("exactly one of Q1, Q2, Q3", sum([q1, q2, q3]) == 1),
        ("Q1 and not Q2", q1 and (not q2)),
    ]
    text, truth = rng.choice(forms)

    rng.shuffle(lines)
    prompt = (
        "All variables below are exact rational numbers.\n\n"
        + "\n".join("  " + ln for ln in lines)
        + "\n\nThree propositions are defined by these values:\n\n"
        + pred_text
        + f"\n\nIs the following statement true or false?\n\n  {text}\n\n"
        "Answer with exactly one of: TRUE, FALSE.\n\n"
        f"{_ANSWER_RULE}"
    )
    return Specimen(
        task_id=task_id,
        family="MIXED_STATE_COMPOSITION",
        generator_version=GENERATOR_VERSION,
        seed=0,
        level=level,
        domain="algebra + logic composition",
        prompt=prompt,
        answer="TRUE" if truth else "FALSE",
        answer_format="TRUE or FALSE",
        metrics={
            "n_facts": len(lines) + 3,
            "dependency_depth": depth,
            "n_predicates": 3,
            "feature_families": 2,
        },
        oracle="exact Fraction arithmetic + boolean evaluation",
    )


FAMILIES: dict[str, object] = {
    "ALGEBRAIC_DEPENDENCY_GRAPH": _algebraic,
    "FINITE_LOGIC_WORLD": _logic,
    "FINITE_QUANTIFIER_WORLD": _quantifier,
    "MIXED_STATE_COMPOSITION": _mixed,
}


def generate(family: str, level: str, seed: int) -> Specimen:
    """Deterministic in ``seed``: the same seed always yields the same specimen."""
    if family not in FAMILIES:
        raise KeyError(f"unknown family {family!r}")
    if level not in LEVELS:
        raise KeyError(f"unknown level {level!r}")
    rng = random.Random(f"{GENERATOR_VERSION}|{family}|{level}|{seed}")
    task_id = f"{family[:4].lower()}_{level}_{seed}"
    spec = FAMILIES[family](rng, level, task_id)  # type: ignore[operator]
    spec.seed = seed
    return spec
