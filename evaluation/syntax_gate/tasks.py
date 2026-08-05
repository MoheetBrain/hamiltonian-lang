"""The HML-PHASE-FG-001 task corpus: Track A, Track B, and the recorded exclusions.

Every task is a ``CanonicalSemanticObject`` from ``evaluation.corpus.cso`` — the frozen
contract — wrapped in a ``GateTask`` that adds the two things Phase F2 needs and the CSO
does not carry: the set of core features the task uses, and the set of ground-truth
facets its answer key actually populates. Those two sets decide Track A membership
mechanically (see ``partition``), so membership is not a judgement call.

Why the corpus is generated rather than reused
----------------------------------------------
``evaluation/corpus/generators.py`` holds 120 validated V0 objects, and reusing them
would be cheaper. It would also be contamination: HML-EVAL-001 ran a subset of them
against this exact model and stored 221 trials. Every item here is generated under the
seed namespace ``hml-phase-fg-001::`` so that no held-out item is verbatim an item the
model has already been shown.

What "excluded" means
---------------------
A task that cannot be represented in all four candidates is **recorded with its reason**,
not deleted. ``build_excluded()`` deliberately carries tasks for each of the three
non-V1 exclusion axes so that ``EXPRESSIBILITY_MATRIX.csv`` demonstrates the exclusion
machinery on real content rather than asserting that it would work.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field

from evaluation.corpus.cso import AnswerSpec, CanonicalSemanticObject, SemanticFacts

from . import SYNTAX_GATE_VERSION, TRACK_A, TRACK_B

__all__ = [
    "GateTask",
    "TRACK_A_DOMAINS",
    "TRACK_B_DOMAINS",
    "TRACK_A_DOMAIN_COUNTS",
    "build_track_a",
    "build_track_b",
    "build_excluded",
    "build_corpus",
    "content_hash",
]

#: The eight supported domains. G4 confirmatory runs ~10 held-out tasks in each, which is
#: also the unit the "no domain below 70% repaired parse" floor is evaluated over.
TRACK_A_DOMAINS = (
    "binding_chain",
    "quantifier_scope",
    "distribution_law",
    "dimensional_algebra",
    "transformation_chain",
    "assumption_boundary",
    "equivalence_vs_implication",
    "approximation_vs_equality",
)

TRACK_B_DOMAINS = (
    "v1_epistemic_calibration",
    "v1_discourse_obligation",
    "v1_semantic_morphology",
    "v1_concept_structure",
    "v1_transformation_relation",
)

#: 30 + 30 + 29*6 = 234 = 50 demonstrations + 16 (G2) + 48 (G3) + 80 (G4) + 40 (replication).
TRACK_A_DOMAIN_COUNTS = {
    "binding_chain": 30,
    "quantifier_scope": 30,
    "distribution_law": 29,
    "dimensional_algebra": 29,
    "transformation_chain": 29,
    "assumption_boundary": 29,
    "equivalence_vs_implication": 29,
    "approximation_vs_equality": 29,
}

_SYMS = [
    "alpha", "beta", "gamma", "delta", "kappa", "lambda_", "mu", "nu",
    "rho", "sigma", "tau", "phi", "chi", "psi", "omega", "eta",
    "zeta", "iota", "theta", "xi", "upsilon", "varrho", "digamma", "koppa",
]


def _rng(pid: str) -> random.Random:
    """Seeded per problem id, in a namespace no earlier study used."""
    return random.Random(f"hml-phase-fg-001::{pid}")


@dataclass(frozen=True)
class GateTask:
    """One semantic object plus everything Phase F2 needs to place it."""

    cso: CanonicalSemanticObject
    track: str
    #: Core features the task uses. Decides representability against each candidate.
    features: frozenset[str]
    #: Ground-truth facets the answer key populates. Decides scoreability.
    scored_facets: frozenset[str]
    #: "hml_l1" for anything the frozen compiler accepts; "hml_v1_proposed" for the V1
    #: surface, which has no parser. Never claim a proposed surface compiles.
    reference_syntax: str = "hml_l1"
    #: True only for tasks deliberately built to fail Track A membership.
    intentionally_excluded: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def id(self) -> str:
        return self.cso.id

    @property
    def domain(self) -> str:
        return self.cso.domain

    @property
    def content_hash(self) -> str:
        return content_hash(self.cso)


def content_hash(cso: CanonicalSemanticObject) -> str:
    """Hash the task's *content*, never its name.

    Disjointness between demonstrations and held-out tasks is asserted on this value.
    Asserting it on ids would pass for two tasks that differ only in their id, which is
    precisely the leak the assertion exists to catch.
    """
    payload = json.dumps(
        {
            "prose": cso.prose,
            "question": cso.question,
            "answer_kind": cso.answer.kind,
            "answer_value": cso.answer.value,
            "answer_options": sorted(cso.answer.options),
            "reference": cso.reference_hml,
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _cso(
    pid: str,
    domain: str,
    difficulty: str,
    prose: str,
    question: str,
    answer: AnswerSpec,
    facts: SemanticFacts,
    reference: str,
    distractors: list[str],
    generator: str,
) -> CanonicalSemanticObject:
    return CanonicalSemanticObject(
        id=pid,
        domain=domain,
        difficulty=difficulty,  # type: ignore[arg-type]
        prose=prose,
        question=question,
        answer=answer,
        semantics=facts,
        distractors=distractors,
        reference_hml=reference,
        generator=generator,
        corpus_version=SYNTAX_GATE_VERSION,
    )


# ===========================================================================
# Domain 1 - binding_chain: long variable-binding chains
# ===========================================================================


def _binding_chain(pid: str, variant: int) -> GateTask:
    rng = _rng(pid)
    a, b, s, t, u, w = rng.sample(_SYMS, 6)
    va, vb, k, off = rng.randint(2, 9), rng.randint(2, 9), rng.randint(2, 5), rng.randint(1, 9)

    if variant == 0:
        lines = [
            f"const {a} : Real = {va}",
            f"const {b} : Real = {vb}",
            f"def {s} : Real := {a} + {b}",
            f"def {t} : Real := {s} * {k}",
            f"def {u} : Real := {t} - {a} + {off}",
            f"solve {u}",
        ]
        entities = {a: "Real", b: "Real", s: "Real", t: "Real", u: "Real"}
        kinds = {a: "const", b: "const", s: "def", t: "def", u: "def"}
        value = float((va + vb) * k - va + off)
        target, depth = u, 3
        prose_body = (
            f"Let {a} be {va} and let {b} be {vb}. Define {s} to be {a} plus {b}; "
            f"define {t} to be {s} multiplied by {k}; define {u} to be {t} minus {a}, "
            f"plus {off}."
        )
        wrong = float((va + vb) * k - vb + off)
    elif variant == 1:
        lines = [
            f"const {a} : Real = {va}",
            f"const {b} : Real = {vb}",
            f"def {s} : Real := {a} * {b}",
            f"def {t} : Real := {s} + {a}",
            f"def {u} : Real := {t} - {b}",
            f"def {w} : Real := {u} * {k}",
            f"solve {w}",
        ]
        entities = {a: "Real", b: "Real", s: "Real", t: "Real", u: "Real", w: "Real"}
        kinds = {a: "const", b: "const", s: "def", t: "def", u: "def", w: "def"}
        value = float((va * vb + va - vb) * k)
        target, depth = w, 4
        prose_body = (
            f"Let {a} be {va} and let {b} be {vb}. Define {s} to be {a} times {b}; "
            f"define {t} to be {s} plus {a}; define {u} to be {t} minus {b}; "
            f"define {w} to be {u} multiplied by {k}."
        )
        wrong = float(va * vb + va - vb + k)
    else:
        lines = [
            f"const {a} : Real = {va}",
            f"const {b} : Real = {vb}",
            f"def {s}({t} : Real) : Real := {t} * {k} + {a}",
            f"def {u} : Real := {s}({b})",
            f"def {w} : Real := {u} - {a}",
            f"solve {w}",
        ]
        entities = {
            a: "Real", b: "Real", s: "Function[Real -> Real]", u: "Real", w: "Real",
        }
        kinds = {a: "const", b: "const", s: "def", u: "def", w: "def"}
        value = float(vb * k + va - va)
        target, depth = w, 3
        prose_body = (
            f"Let {a} be {va} and let {b} be {vb}. Define {s} to be the function that "
            f"sends an argument to that argument multiplied by {k}, plus {a}. "
            f"Define {u} to be {s} applied to {b}; define {w} to be {u} minus {a}."
        )
        wrong = float(vb * k + va)

    reference = "module BindingChain\n\n" + "\n".join(lines) + "\n"
    prose = (
        "A chain of named definitions is given. Each definition may refer to earlier "
        "names, and a name refers to exactly the object it was bound to.\n\n" + prose_body
    )
    question = f"What is the numerical value of {target}?"
    facts = SemanticFacts(
        entities=entities,
        declaration_kinds=kinds,
        dependencies={target: [n for n in entities if n != target]},
    )
    return GateTask(
        cso=_cso(
            pid, "binding_chain", "medium" if depth >= 4 else "easy", prose, question,
            AnswerSpec("numeric", value, tolerance=1e-9,
                       justification=f"resolve the chain of {depth} definitions in order"),
            facts, reference,
            [f"substituting the wrong bound name gives {wrong}"],
            "_binding_chain",
        ),
        track=TRACK_A,
        features=frozenset(
            {"decl_const", "def_simple", "type_scalar", "op_arithmetic", "solve"}
            | ({"def_parametric", "type_function"} if variant == 2 else set())
        ),
        scored_facets=frozenset({"entities", "types", "declaration_kinds"}),
    )


# ===========================================================================
# Domain 2 - quantifier_scope: nested quantifiers and scope
# ===========================================================================

_QUANT_VARIANTS = (
    # (template, quantifier_order facts, truth, features)
    ("forall {x} : Real . exists {y} : Real . {y} > {x} + {c}",
     ["forall", "exists"], True, ()),
    ("exists {y} : Real . forall {x} : Real . {y} > {x} + {c}",
     ["exists", "forall"], False, ()),
    ("not forall {x} : Real . exists {y} : Real . {y} > {x} + {c}",
     ["not", "forall", "exists"], False, ("quantifier_negation",)),
    ("not exists {y} : Real . forall {x} : Real . {y} > {x} + {c}",
     ["not", "exists", "forall"], True, ("quantifier_negation",)),
)


def _quantifier_scope(pid: str, variant: int) -> GateTask:
    rng = _rng(pid)
    x, y = rng.sample(_SYMS, 2)
    c = rng.randint(1, 12)
    template, order, truth, extra = _QUANT_VARIANTS[variant % len(_QUANT_VARIANTS)]
    body = template.format(x=x, y=y, c=c)
    reference = f"module QuantifierScope\n\ndef claim : Proposition := {body}\nprove claim\n"

    english = {
        0: (f"for every real number {x} there is a real number {y} with "
            f"{y} greater than {x} plus {c}"),
        1: (f"there is a real number {y} such that for every real number {x}, "
            f"{y} is greater than {x} plus {c}"),
        2: (f"it is not the case that for every real number {x} there is a real "
            f"number {y} with {y} greater than {x} plus {c}"),
        3: (f"it is not the case that there is a real number {y} such that for every "
            f"real number {x}, {y} is greater than {x} plus {c}"),
    }[variant % 4]
    prose = (
        "A statement about the real numbers is given. The order in which the "
        "quantifiers appear is part of the statement: reordering them produces a "
        "different statement, which may have a different truth value.\n\n"
        f"Statement: {english}."
    )
    facts = SemanticFacts(quantifier_order=[f"{q} binder" for q in order])
    return GateTask(
        cso=_cso(
            pid, "quantifier_scope", "medium", prose,
            "Is the statement true over the real numbers?",
            AnswerSpec("boolean", truth,
                       justification="the reals are unbounded above, so no single "
                                     "witness dominates every argument"),
            facts, reference,
            ["treating the two quantifier orders as interchangeable"],
            "_quantifier_scope",
        ),
        track=TRACK_A,
        features=frozenset(
            {"quantifier_nested", "type_scalar", "type_proposition", "op_comparison",
             "op_arithmetic", "def_simple", "prove"} | set(extra)
        ),
        scored_facets=frozenset({"quantifier_order"}),
    )


# ===========================================================================
# Domain 3 - distribution_law: Bayesian and frequentist reasoning
# ===========================================================================


def _distribution_law(pid: str, variant: int) -> GateTask:
    rng = _rng(pid)
    v = variant % 4

    if v == 0:
        th, n, k = rng.sample(_SYMS, 3)
        a, b = rng.randint(1, 6), rng.randint(1, 6)
        trials, succ = rng.randint(8, 40), 0
        succ = rng.randint(1, trials - 1)
        reference = (
            "module BetaBinomial\n\n"
            f"param {th} : Probability\n"
            f"prior {th} ~ Beta(alpha := {a}, beta := {b})\n"
            f"const {n} : Natural = {trials}\n"
            f"obs {k} : Natural = {succ}\n"
            f"likelihood {k} | {th} ~ Binomial(trials := {n}, prob := {th})\n"
            f"infer posterior {th}\n"
        )
        prose = (
            f"An unknown proportion {th} lies in [0, 1]. Before seeing data it is given "
            f"a Beta prior with alpha = {a} and beta = {b}. Then {trials} independent "
            f"trials are run and {succ} of them succeed; the count of successes is "
            f"binomial with that many trials and success probability {th}."
        )
        question = f"What is the posterior mean of {th}?"
        value = (a + succ) / (a + b + trials)
        facts = SemanticFacts(
            entities={th: "Probability", n: "Natural", k: "Natural"},
            declaration_kinds={th: "param", n: "const", k: "obs"},
            law_families={th: "Beta", k: "Binomial"},
            laws={th: {"alpha": str(a), "beta": str(b)},
                  k: {"trials": n, "prob": th}},
            conditioning={k: [th]},
        )
        distractors = [f"reporting the sample proportion {succ}/{trials} and ignoring the prior"]
        feats = {"decl_param", "decl_const", "decl_obs", "type_refined", "law_prior",
                 "law_likelihood", "law_labelled_roles", "law_conditioning", "infer"}
    elif v == 1:
        mu, sg, xr = rng.sample(_SYMS, 3)
        scale = rng.randint(2, 9)
        loc = rng.randint(-6, 6)
        reference = (
            "module NormalScale\n\n"
            f"param {mu} : Real\n"
            f"param {sg} : PositiveReal\n"
            f"rv {xr} : RandomVariable[Real]\n"
            f"law {xr} ~ Normal(location := {mu}, scale := {sg})\n"
            f"infer variance {xr}\n"
        )
        prose = (
            f"A quantity {xr} is normally distributed. Its location is {loc} and its "
            f"scale is {scale}. In this notation the scale of a normal law is its "
            "standard deviation."
        )
        question = f"What is the variance of {xr}?"
        value = float(scale * scale)
        facts = SemanticFacts(
            entities={mu: "Real", sg: "PositiveReal", xr: "RandomVariable[Real]"},
            declaration_kinds={mu: "param", sg: "param", xr: "rv"},
            law_families={xr: "Normal"},
            laws={xr: {"location": mu, "scale": sg}},
        )
        distractors = [f"reporting the scale {scale} as if it were the variance"]
        feats = {"decl_param", "decl_rv", "type_scalar", "type_refined",
                 "type_random_variable", "law_labelled_roles", "infer"}
    elif v == 2:
        lam, tr = rng.sample(_SYMS, 2)
        rate = rng.randint(2, 12)
        reference = (
            "module ExponentialRate\n\n"
            f"param {lam} : PositiveReal\n"
            f"rv {tr} : RandomVariable[NonNegativeReal]\n"
            f"law {tr} ~ Exponential(rate := {lam})\n"
            f"infer expectation {tr}\n"
        )
        prose = (
            f"A waiting time {tr} is exponentially distributed with rate {rate}. "
            "The rate of an exponential law is the reciprocal of its mean."
        )
        question = f"What is the mean of {tr}?"
        value = 1.0 / rate
        facts = SemanticFacts(
            entities={lam: "PositiveReal", tr: "RandomVariable[NonNegativeReal]"},
            declaration_kinds={lam: "param", tr: "rv"},
            law_families={tr: "Exponential"},
            laws={tr: {"rate": lam}},
        )
        distractors = [f"reporting the rate {rate} as if it were the mean"]
        feats = {"decl_param", "decl_rv", "type_refined", "type_random_variable",
                 "law_labelled_roles", "infer"}
    else:
        sh, rt, yr = rng.sample(_SYMS, 3)
        shape, rate = rng.randint(2, 9), rng.randint(2, 9)
        reference = (
            "module GammaMean\n\n"
            f"param {sh} : PositiveReal\n"
            f"param {rt} : PositiveReal\n"
            f"rv {yr} : RandomVariable[PositiveReal]\n"
            f"law {yr} ~ Gamma(shape := {sh}, rate := {rt})\n"
            f"infer expectation {yr}\n"
        )
        prose = (
            f"A positive quantity {yr} follows a gamma law with shape {shape} and "
            f"rate {rate}. In this parameterisation the mean is the shape divided by "
            "the rate."
        )
        question = f"What is the mean of {yr}?"
        value = shape / rate
        facts = SemanticFacts(
            entities={sh: "PositiveReal", rt: "PositiveReal",
                      yr: "RandomVariable[PositiveReal]"},
            declaration_kinds={sh: "param", rt: "param", yr: "rv"},
            law_families={yr: "Gamma"},
            laws={yr: {"shape": sh, "rate": rt}},
        )
        distractors = [f"multiplying instead of dividing gives {shape * rate}"]
        feats = {"decl_param", "decl_rv", "type_refined", "type_random_variable",
                 "law_labelled_roles", "infer"}

    scored = {"entities", "types", "declaration_kinds", "law_families", "roles"}
    if facts.conditioning:
        scored.add("conditioning")
    return GateTask(
        cso=_cso(
            pid, "distribution_law", "medium", prose, question,
            AnswerSpec("numeric", value, tolerance=1e-6,
                       justification="the role each parameter fills determines the answer"),
            facts, reference, distractors, "_distribution_law",
        ),
        track=TRACK_A,
        features=frozenset(feats),
        scored_facets=frozenset(scored),
    )


# ===========================================================================
# Domain 4 - dimensional_algebra: dimensions and units
# ===========================================================================

_DIM_VARIANTS = (
    ("KineticEnergy",
     (("Mass",), ("Length / Time",)),
     "Mass * Length^2 / Time^2",
     "0.5 * {0} * {1}^2",
     "a mass and a speed; the derived quantity is half the mass times the square of the speed",
     "forgetting to square the speed gives Mass * Length / Time"),
    ("Pressure",
     (("Mass * Length / Time^2",), ("Length^2",)),
     "Mass / (Length * Time^2)",
     "{0} / {1}",
     "a force and an area; the derived quantity is the force divided by the area",
     "multiplying instead of dividing gives Mass * Length^3 / Time^2"),
    ("Power",
     (("Mass * Length^2 / Time^2",), ("Time",)),
     "Mass * Length^2 / Time^3",
     "{0} / {1}",
     "an energy and a duration; the derived quantity is the energy divided by the duration",
     "leaving the time exponent at 2 gives Mass * Length^2 / Time^2"),
    ("Density",
     (("Mass",), ("Length^3",)),
     "Mass / Length^3",
     "{0} / {1}",
     "a mass and a volume; the derived quantity is the mass divided by the volume",
     "inverting the ratio gives Length^3 / Mass"),
)


def _dimensional_algebra(pid: str, variant: int) -> GateTask:
    rng = _rng(pid)
    name, (d1, d2), result, expr, description, distractor = _DIM_VARIANTS[
        variant % len(_DIM_VARIANTS)
    ]
    p, q, e = rng.sample(_SYMS, 3)
    reference = (
        f"module {name}\n\n"
        f"param {p} : Quantity[{d1[0]}]\n"
        f"param {q} : Quantity[{d2[0]}]\n"
        f"def {e} : Quantity[{result}] := {expr.format(p, q)}\n"
        f"check dimension {e} = {result}\n"
    )
    prose = (
        "Two physical quantities are given, each with a stated physical dimension, and "
        "a third is derived from them.\n\n"
        f"{p} has dimension {d1[0]}. {q} has dimension {d2[0]}. "
        f"The problem concerns {description}, written {e}."
    )
    facts = SemanticFacts(
        dimensions={p: d1[0], q: d2[0], e: result},
    )
    return GateTask(
        cso=_cso(
            pid, "dimensional_algebra", "medium", prose,
            f"What is the physical dimension of {e}?",
            AnswerSpec("dimension", result,
                       justification="exponents add under multiplication and subtract "
                                     "under division"),
            facts, reference, [distractor], "_dimensional_algebra",
        ),
        track=TRACK_A,
        features=frozenset(
            {"decl_param", "type_quantity", "def_simple", "check_dimension",
             "op_arithmetic"}
        ),
        scored_facets=frozenset({"dimensions"}),
    )


# ===========================================================================
# Domain 5 - transformation_chain: transformation chains
# ===========================================================================

_CHAIN_STEPS = (
    # (english, hml_proposition_template, side_condition or None)
    ("add {c} to both sides", "{u} + {c} = {v} + {c}", None),
    ("multiply both sides by {c}", "{u} * {c} = {v} * {c}", None),
    ("divide both sides by {w}", "{u} / {w} = {v} / {w}", "{w} != 0"),
    ("cancel the common factor {w}", "{u} = {v}", "{w} != 0"),
    ("subtract {c} from both sides", "{u} - {c} = {v} - {c}", None),
)


def _transformation_chain(pid: str, variant: int) -> GateTask:
    rng = _rng(pid)
    u, v, w = rng.sample(_SYMS, 3)
    c = rng.randint(2, 11)
    # variant selects which step carries the unmet side condition
    plans = (
        (0, 2, 1),   # obligation at step 2
        (0, 1, 3),   # obligation at step 3
        (4, 0, 1, 2),  # obligation at step 4
        (2, 0, 1),   # obligation at step 1
    )
    plan = plans[variant % len(plans)]
    answer_step = next(i for i, s in enumerate(plan, 1) if _CHAIN_STEPS[s][2])

    english_steps, obligations = [], []
    for n, s in enumerate(plan, 1):
        english, _prop, cond = _CHAIN_STEPS[s]
        english_steps.append(f"  step {n}: {english.format(c=c, w=w)}")
        if cond:
            obligations.append(cond.format(w=w, c=c))

    ref_lines = [
        "module TransformationChain",
        "",
        f"var {u} : Real",
        f"var {v} : Real",
        f"var {w} : Real",
        f"assume {u} = {v}",
    ]
    ref_lines += [f"require {o}" for o in dict.fromkeys(obligations)]
    ref_lines += [f"def conclusion : Proposition := {u} = {v}", "prove conclusion"]
    reference = "\n".join(ref_lines) + "\n"

    prose = (
        f"A derivation begins from the premise that {u} equals {v} and proceeds by the "
        "numbered steps below. Each step names the operation applied to both sides. "
        f"Nothing is known about {w} beyond the fact that it is a real number.\n\n"
        + "\n".join(english_steps)
    )
    facts = SemanticFacts(
        entities={u: "Real", v: "Real", w: "Real", "conclusion": "Proposition"},
        declaration_kinds={u: "var", v: "var", w: "var", "conclusion": "def"},
        constraints=list(dict.fromkeys(obligations)),
    )
    return GateTask(
        cso=_cso(
            pid, "transformation_chain", "medium", prose,
            "At which numbered step is a side condition first required that the problem "
            "never establishes? Answer with the step number.",
            AnswerSpec("numeric", float(answer_step), tolerance=1e-9,
                       justification=f"the step operating on {w} needs {w} != 0, which "
                                     "the premise never supplies"),
            facts, reference,
            ["treating every step as unconditionally valid because each is a familiar "
             "algebraic move"],
            "_transformation_chain",
        ),
        track=TRACK_A,
        features=frozenset(
            {"decl_var", "type_scalar", "type_proposition", "assume", "require",
             "prove", "def_simple", "op_arithmetic", "op_comparison"}
        ),
        scored_facets=frozenset({"entities", "types", "declaration_kinds"}),
    )


# ===========================================================================
# Domain 6 - assumption_boundary: assumptions and boundary conditions
# ===========================================================================


def _assumption_boundary(pid: str, variant: int) -> GateTask:
    rng = _rng(pid)
    c, t, f, z = rng.sample(_SYMS, 4)
    cv = rng.randint(2, 12)
    lo = rng.randint(0, 5)
    v = variant % 4
    # Two variants answer FALSE and two answer TRUE, so the modal-answer floor stays at
    # the 0.5 chance level for a binary question rather than drifting toward one side.
    strict = v != 1
    op = ">" if strict else ">="
    if v == 0:      # strict, probed exactly at the boundary
        probe, admissible = lo, False
    elif v == 1:    # non-strict, probed exactly at the boundary
        probe, admissible = lo, True
    elif v == 2:    # strict, probed below the boundary
        probe, admissible = lo - rng.randint(1, 4), False
    else:           # strict, probed strictly inside the region
        probe, admissible = lo + rng.randint(1, 4), True

    reference = (
        "module BoundaryCondition\n\n"
        f"const {c} : Real = {cv}\n"
        f"var {t} : Real\n"
        f"assume {t} {op} {lo}\n"
        f"def {f}({z} : Real) : Real := {c} / {z}\n"
        f"require {t} != 0\n"
    )
    prose = (
        f"A quantity {t} is constrained by the stated assumption, and a function {f} is "
        f"defined by {f} of an argument equals {cv} divided by that argument. The "
        "assumption is the only restriction given.\n\n"
        f"Assumption: {t} is {'strictly greater than' if strict else 'greater than or equal to'} {lo}."
    )
    facts = SemanticFacts(
        entities={c: "Real", t: "Real", f: "Function[Real -> Real]"},
        declaration_kinds={c: "const", t: "var", f: "def"},
        constraints=[f"{t} {op} {lo}", f"{t} != 0"],
    )
    return GateTask(
        cso=_cso(
            pid, "assumption_boundary", "medium", prose,
            f"Is the value {t} = {probe} admissible under the stated assumption?",
            AnswerSpec("boolean", admissible,
                       justification=("a strict inequality excludes its own boundary; a "
                                      "non-strict one includes it")),
            facts, reference,
            ["reading a strict inequality as if it included its boundary"],
            "_assumption_boundary",
        ),
        track=TRACK_A,
        features=frozenset(
            {"decl_const", "decl_var", "def_parametric", "type_scalar", "type_function",
             "assume", "require", "op_comparison", "op_arithmetic"}
        ),
        scored_facets=frozenset({"entities", "types", "declaration_kinds"}),
    )


# ===========================================================================
# Domain 7 - equivalence_vs_implication
# ===========================================================================

_EQ_OPTIONS = ["IMPLICATION_ONLY", "EQUIVALENCE", "NEITHER"]


def _equivalence_vs_implication(pid: str, variant: int) -> GateTask:
    rng = _rng(pid)
    t, lo_n, hi_n = rng.sample(_SYMS, 3)
    lo = rng.randint(1, 6)
    hi = lo + rng.randint(1, 6)
    v = variant % 3

    if v == 0:
        body = f"forall {t} : Real . {t} > {hi_n} => {t} > {lo_n}"
        english = (f"for every real {t}, if {t} is greater than {hi} then {t} is "
                   f"greater than {lo}")
        answer = "IMPLICATION_ONLY"
        why = f"every number above {hi} is above {lo}, but not conversely"
    elif v == 1:
        body = f"forall {t} : Real . {t} > {hi_n} <=> {t} - {hi_n} > 0"
        english = (f"for every real {t}, {t} is greater than {hi} exactly when "
                   f"{t} minus {hi} is greater than zero")
        answer = "EQUIVALENCE"
        why = "the two sides are the same condition rearranged"
    else:
        body = f"forall {t} : Real . {t} > {lo_n} => {t} > {hi_n}"
        english = (f"for every real {t}, if {t} is greater than {lo} then {t} is "
                   f"greater than {hi}")
        answer = "NEITHER"
        why = f"a number strictly between {lo} and {hi} refutes it"

    reference = (
        "module ImplicationDirection\n\n"
        f"const {lo_n} : Real = {lo}\n"
        f"const {hi_n} : Real = {hi}\n"
        f"def claim : Proposition := {body}\nprove claim\n"
    )
    prose = (
        "A relationship between two conditions on the real numbers is stated. An "
        "implication holds in one direction only; an equivalence holds in both; "
        "neither is the third possibility.\n\n"
        f"Statement: {english}."
    )
    facts = SemanticFacts(
        entities={lo_n: "Real", hi_n: "Real", "claim": "Proposition"},
        declaration_kinds={lo_n: "const", hi_n: "const", "claim": "def"},
        quantifier_order=["forall binder"],
    )
    return GateTask(
        cso=_cso(
            pid, "equivalence_vs_implication", "medium", prose,
            "Does the stated relationship hold as an implication in one direction only, "
            "as an equivalence in both directions, or neither?",
            AnswerSpec("choice", answer, options=list(_EQ_OPTIONS), justification=why),
            facts, reference,
            ["reading a one-directional implication as an equivalence"],
            "_equivalence_vs_implication",
        ),
        track=TRACK_A,
        features=frozenset(
            {"decl_const", "def_simple", "type_scalar", "type_proposition", "prove",
             "quantifier_nested", "op_implication", "op_equivalence", "op_comparison",
             "op_arithmetic"}
        ),
        scored_facets=frozenset(
            {"entities", "types", "declaration_kinds", "quantifier_order"}
        ),
    )


# ===========================================================================
# Domain 8 - approximation_vs_equality
# ===========================================================================

_APPROX_OPTIONS = ["EXACT", "APPROXIMATE_WITHIN_TOLERANCE", "OUTSIDE_TOLERANCE"]


def _approximation_vs_equality(pid: str, variant: int) -> GateTask:
    rng = _rng(pid)
    lhs, rhs, tol = rng.sample(_SYMS, 3)
    v = variant % 3
    base = rng.randint(2, 40)
    tolerance = round(rng.choice([0.01, 0.05, 0.1, 0.5]), 3)

    if v == 0:
        a = float(base)
        b = float(base)
        answer = "EXACT"
        constraint = f"{lhs} = {rhs}"
        why = "the two quantities are the same number, so the relation is exact"
    elif v == 1:
        a = float(base)
        b = round(base + tolerance / 2, 6)
        answer = "APPROXIMATE_WITHIN_TOLERANCE"
        constraint = (f"{lhs} - {rhs} <= {tol} and {rhs} - {lhs} <= {tol}")
        why = "the quantities differ, but by less than the stated tolerance"
    else:
        a = float(base)
        b = round(base + tolerance * 4, 6)
        answer = "OUTSIDE_TOLERANCE"
        constraint = (f"{lhs} - {rhs} <= {tol} and {rhs} - {lhs} <= {tol}")
        why = "the difference exceeds the stated tolerance, so neither relation holds"

    reference = (
        "module ApproximationStatus\n\n"
        f"const {lhs} : Real = {a}\n"
        f"const {rhs} : Real = {b}\n"
        f"const {tol} : Real = {tolerance}\n"
        f"require {constraint}\n"
    )
    prose = (
        "Two numerical quantities and a tolerance are given. Exact equality and "
        "agreement to within a tolerance are different relations and must not be "
        "conflated.\n\n"
        f"{lhs} = {a}. {rhs} = {b}. The stated tolerance is {tolerance}."
    )
    facts = SemanticFacts(
        entities={lhs: "Real", rhs: "Real", tol: "Real"},
        declaration_kinds={lhs: "const", rhs: "const", tol: "const"},
        constraints=[constraint],
    )
    return GateTask(
        cso=_cso(
            pid, "approximation_vs_equality", "medium", prose,
            f"Is the relation between {lhs} and {rhs} exact equality, agreement to "
            "within the stated tolerance, or neither?",
            AnswerSpec("choice", answer, options=list(_APPROX_OPTIONS), justification=why),
            facts, reference,
            ["reporting close agreement as exact equality"],
            "_approximation_vs_equality",
        ),
        track=TRACK_A,
        features=frozenset(
            {"decl_const", "type_scalar", "require", "op_comparison", "op_logical",
             "op_arithmetic"}
        ),
        scored_facets=frozenset({"entities", "types", "declaration_kinds"}),
    )


_TRACK_A_BUILDERS = {
    "binding_chain": _binding_chain,
    "quantifier_scope": _quantifier_scope,
    "distribution_law": _distribution_law,
    "dimensional_algebra": _dimensional_algebra,
    "transformation_chain": _transformation_chain,
    "assumption_boundary": _assumption_boundary,
    "equivalence_vs_implication": _equivalence_vs_implication,
    "approximation_vs_equality": _approximation_vs_equality,
}

_CACHE_A: list[GateTask] | None = None


def build_track_a() -> list[GateTask]:
    """234 shared-core tasks: 50 demonstrations + 184 held-out. Deterministic."""
    global _CACHE_A
    if _CACHE_A is not None:
        return _CACHE_A
    out: list[GateTask] = []
    for domain in TRACK_A_DOMAINS:
        builder = _TRACK_A_BUILDERS[domain]
        for i in range(TRACK_A_DOMAIN_COUNTS[domain]):
            pid = f"{domain}_{i:03d}"
            out.append(builder(pid, i))
    _CACHE_A = out
    return out


# ===========================================================================
# Track B - V1 capability. Engineering validation only.
# ===========================================================================

_TRACK_B_SPECS: dict[str, tuple[str, frozenset[str]]] = {
    "v1_epistemic_calibration": (
        "v1_epistemic_status",
        frozenset({"v1_epistemic_status"}),
    ),
    "v1_discourse_obligation": (
        "v1_discourse_goal",
        frozenset({"v1_discourse_goal", "v1_case_analysis"}),
    ),
    "v1_semantic_morphology": (
        "v1_semantic_morphology",
        frozenset({"v1_semantic_morphology", "v1_family_declaration"}),
    ),
    "v1_concept_structure": (
        "v1_concept_minting",
        frozenset({"v1_concept_minting", "concept_block", "concept_named_invariant"}),
    ),
    "v1_transformation_relation": (
        "v1_transformation_step",
        frozenset({"v1_transformation_step", "v1_derivation", "v1_entailment"}),
    ),
}

_TRACK_B_ITEMS = {
    "v1_epistemic_calibration": [
        ("A hypothesis test at level {a} fails to reject its null hypothesis, and the "
         "reported tail probability is {p}.",
         "What has the test established about the null hypothesis?",
         ["INSUFFICIENT_EVIDENCE_AGAINST", "NULL_IS_PROBABLY_TRUE",
          "NULL_IS_PROVED", "ALTERNATIVE_IS_REFUTED"],
         "INSUFFICIENT_EVIDENCE_AGAINST",
         "fail_to_reject(test, p_value := {p})  # returns Evidence, never Proof"),
        ("A quantity is asserted to hold with high probability, and no regime is named.",
         "Is the assertion well formed?",
         ["NO_REGIME_IS_MANDATORY", "YES", "ONLY_IF_PROBABILITY_EXCEEDS_HALF",
          "ONLY_UNDER_A_PRIOR"],
         "NO_REGIME_IS_MANDATORY",
         "with_high_probability(P, regime := <MISSING>)  # regime is MANDATORY"),
        ("A tail probability of {p} is reported, and a reader restates it as the "
         "probability that the null hypothesis is true.",
         "Is the restatement licensed?",
         ["NO_PVALUE_IS_NOT_A_POSTERIOR", "YES", "ONLY_UNDER_A_UNIFORM_PRIOR",
          "ONLY_IF_THE_TEST_IS_TWO_SIDED"],
         "NO_PVALUE_IS_NOT_A_POSTERIOR",
         "PValue is its own type; there is no coercion PValue -> PosteriorProbability"),
        ("A proposition is supported by evidence at strength {a} and is then used to "
         "discharge a proof goal.",
         "Is the discharge licensed?",
         ["NO_ONLY_A_PROOF_DISCHARGES", "YES", "ONLY_IF_EVIDENCE_EXCEEDS_A_THRESHOLD",
          "ONLY_FOR_EXISTENTIAL_GOALS"],
         "NO_ONLY_A_PROOF_DISCHARGES",
         "discharge g by Evidence  # REJECTED: only a Proof discharges a goal"),
    ],
    "v1_discourse_obligation": [
        ("A derivation opens {a} goals and closes {p} of them by proof.",
         "How many obligations remain open?",
         [], None,
         "goal g{a} := <proposition>   # opened\ndischarge g{p} by <Proof>  # closed"),
        ("A case analysis names the cases 'greater than {a}' and 'less than {a}'.",
         "Is the case analysis exhaustive over the reals?",
         ["NO_THE_BOUNDARY_IS_UNCOVERED", "YES", "ONLY_FOR_INTEGERS",
          "ONLY_IF_THE_BOUND_IS_IRRATIONAL"],
         "NO_THE_BOUNDARY_IS_UNCOVERED",
         "case c := <condition> ... otherwise ... end_case  # exhaustiveness is CHECKED"),
    ],
    "v1_semantic_morphology": [
        ("A writer forms the word 'variancer' from 'variance' by analogy with "
         "'estimate' and 'estimator'.",
         "Is the formation licensed?",
         ["NO_MEMBERS_ARE_DECLARED_NOT_GENERATED", "YES",
          "ONLY_INSIDE_A_DECLARED_FAMILY", "ONLY_FOR_ESTIMATION_CONCEPTS"],
         "NO_MEMBERS_ARE_DECLARED_NOT_GENERATED",
         "family Estimation of theta : ParameterSpace\n    member estimator : "
         "Function[Sample -> ParameterSpace]\nend"),
        ("A report states that 'the estimate is unbiased', where the estimate is a "
         "single number computed from one sample of size {a}.",
         "Is the statement well typed?",
         ["NO_UNBIASEDNESS_IS_A_PROPERTY_OF_THE_ESTIMATOR", "YES",
          "ONLY_IF_THE_SAMPLE_IS_LARGE", "ONLY_UNDER_THE_SAMPLING_LAW"],
         "NO_UNBIASEDNESS_IS_A_PROPERTY_OF_THE_ESTIMATOR",
         "relation sampling_law = law_of(estimator, under := sampling_model)"),
    ],
    "v1_concept_structure": [
        ("A new concept is proposed with a name, a type signature and typed parameters, "
         "but with no invariant and no example.",
         "Is the concept admissible?",
         ["NO_AN_INVARIANT_OR_EXAMPLE_IS_REQUIRED", "YES",
          "ONLY_IF_IT_EXTENDS_AN_ADMITTED_CONCEPT", "ONLY_IF_IT_COMPRESSES_A_STRUCTURE"],
         "NO_AN_INVARIANT_OR_EXAMPLE_IS_REQUIRED",
         "concept C\n    parameter p : Real\n    invariant nonneg := p >= 0\nend"),
        ("A new concept is proposed whose formal definition matches an admitted concept "
         "exactly, under a different name.",
         "Is the concept admissible?",
         ["NO_IT_IS_A_DUPLICATE", "YES", "ONLY_AS_AN_ALIAS",
          "ONLY_IF_IT_COMPRESSES_MORE"],
         "NO_IT_IS_A_DUPLICATE",
         "a concept whose definition matches an admitted one is rejected as a duplicate "
         "regardless of its name"),
    ],
    "v1_transformation_relation": [
        ("A derivation squares both sides of an equation at step {a} and reports the "
         "result as an equivalence.",
         "Is the report correct?",
         ["NO_SQUARING_RECORDS_A_WEAKENING", "YES", "ONLY_FOR_NONNEGATIVE_SIDES",
          "ONLY_IF_BOTH_SIDES_ARE_REAL"],
         "NO_SQUARING_RECORDS_A_WEAKENING",
         "step s := square_both_sides(expr := e)  # records a WEAKENING, not an equivalence"),
        ("A derivation rewrites one expression into another and reports that the second "
         "is implied by the first.",
         "Is a rewriting the same relation as an implication?",
         ["NO_A_DERIVATION_IS_NOT_AN_ENTAILMENT", "YES", "ONLY_FOR_EQUALITIES",
          "ONLY_UNDER_MODUS_PONENS"],
         "NO_A_DERIVATION_IS_NOT_AN_ENTAILMENT",
         "derive r from [e] via s   # L2\nentails q from [p] via modus_ponens   # L3"),
    ],
}

#: Eight distinct settings so that the eight items in a Track B domain differ in content
#: and not only in an index. Content-hash uniqueness is asserted over the whole corpus,
#: and two items that differ only by a name would defeat the disjointness check.
_TRACK_B_SETTINGS = (
    "a clinical trial report",
    "a manufacturing quality review",
    "an ecological survey write-up",
    "a materials fatigue study",
    "an educational intervention analysis",
    "a network reliability audit",
    "an agricultural yield comparison",
    "a pharmacokinetics summary",
)

_CACHE_B: list[GateTask] | None = None


def build_track_b() -> list[GateTask]:
    """40 V1-capability tasks. Engineering validation; excluded from the gate by
    construction, and proved excluded by differential test in ``tests/evaluation``."""
    global _CACHE_B
    if _CACHE_B is not None:
        return _CACHE_B
    out: list[GateTask] = []
    for domain in TRACK_B_DOMAINS:
        _primary, feats = _TRACK_B_SPECS[domain]
        items = _TRACK_B_ITEMS[domain]
        for i in range(8):
            pid = f"{domain}_{i:03d}"
            rng = _rng(pid)
            prose_t, question, options, answer, ref_t = items[i % len(items)]
            a, p = rng.randint(2, 9), round(rng.uniform(0.06, 0.9), 3)
            setting = _TRACK_B_SETTINGS[i]
            if options:
                spec = AnswerSpec("choice", answer, options=list(options),
                                  justification="V1 layer rule")
            else:
                discharged = min(a - 1, max(1, a // 2))
                p = discharged
                spec = AnswerSpec("numeric", float(a - discharged), tolerance=1e-9,
                                  justification="opened obligations minus discharged")
            prose = f"In {setting}: " + prose_t.format(a=a, p=p)
            reference = f"# {setting}\n" + ref_t.format(a=a, p=p)
            out.append(
                GateTask(
                    cso=_cso(
                        pid, domain, "hard", prose, question, spec,
                        SemanticFacts(), reference,
                        ["applying a V0 reading to a V1 distinction"],
                        "build_track_b",
                    ),
                    track=TRACK_B,
                    features=feats,
                    scored_facets=frozenset(),
                    reference_syntax="hml_v1_proposed",
                    notes=(
                        "the V1 surface has no parser; this reference is a proposal and "
                        "is never claimed to compile",
                    ),
                )
            )
    _CACHE_B = out
    return out


# ===========================================================================
# Deliberate exclusions - recorded, never dropped
# ===========================================================================

_CACHE_X: list[GateTask] | None = None


def build_excluded() -> list[GateTask]:
    """Twelve shared-core-looking tasks that fail Track A on a non-V1 axis.

    Four per axis. They exist so ``EXPRESSIBILITY_MATRIX.csv`` records an exclusion
    reason derived from real content rather than from a hypothetical.
    """
    global _CACHE_X
    if _CACHE_X is not None:
        return _CACHE_X
    out: list[GateTask] = []

    for i in range(4):
        pid = f"excluded_exists_unique_{i:03d}"
        rng = _rng(pid)
        x = rng.sample(_SYMS, 1)[0]
        c = rng.randint(1, 20)
        reference = (
            "module UniqueExistence\n\n"
            f"def claim : Proposition := exists_unique {x} : Real . {x} + 1 = {c}\n"
            "prove claim\n"
        )
        out.append(
            GateTask(
                cso=_cso(
                    pid, "quantifier_scope", "medium",
                    "A statement asserts that exactly one real number satisfies a "
                    f"condition.\n\nStatement: there is exactly one real {x} with "
                    f"{x} plus one equal to {c}.",
                    "Is the statement true over the real numbers?",
                    AnswerSpec("boolean", True, justification="the equation is linear"),
                    SemanticFacts(quantifier_order=["exists_unique binder"]),
                    reference, ["confusing uniqueness with existence"],
                    "build_excluded",
                ),
                track=TRACK_A,
                features=frozenset(
                    {"quantifier_exists_unique", "type_scalar", "type_proposition",
                     "def_simple", "prove", "op_comparison", "op_arithmetic"}
                ),
                scored_facets=frozenset({"quantifier_order"}),
                intentionally_excluded=True,
                notes=("candidate A's parser rejects exists_unique with HML-P204, so "
                       "this reference does not compile; that rejection is the evidence",),
            )
        )

    for i in range(4):
        pid = f"excluded_named_invariant_{i:03d}"
        rng = _rng(pid)
        n, p = rng.sample(_SYMS, 2)
        reference = (
            "module ConceptWithInvariant\n\n"
            f"concept Seminorm{i}\n"
            f"    parameter {n} : Function[Real -> NonNegativeReal]\n"
            f"    parameter {p} : Real\n"
            f"    invariant nonnegativity := {p} >= 0\n"
            "end\n"
        )
        out.append(
            GateTask(
                cso=_cso(
                    pid, "equivalence_vs_implication", "hard",
                    "A structure is defined by a named parameter and a named invariant "
                    "it must satisfy. The invariant's name is part of the definition, "
                    "because later text refers to the invariant by name.",
                    "Does the structure require its invariant to carry a name?",
                    AnswerSpec("boolean", True,
                               justification="later reference by name requires the name"),
                    SemanticFacts(),
                    reference, ["treating the invariant name as decoration"],
                    "build_excluded",
                ),
                track=TRACK_A,
                features=frozenset({"concept_block", "concept_named_invariant",
                                    "type_function", "op_comparison"}),
                scored_facets=frozenset(),
                intentionally_excluded=True,
                notes=("candidate C's grammar has no IDENT slot on an invariant "
                       "(c_sexpr.ebnf line 54)",),
            )
        )

    for i in range(4):
        pid = f"excluded_precedence_{i:03d}"
        rng = _rng(pid)
        a, b, c, e = rng.sample(_SYMS, 4)
        va, vb, vc = rng.randint(1, 9), rng.randint(1, 9), rng.randint(2, 4)
        reference = (
            "module PrecedenceGrouping\n\n"
            f"const {a} : Real = {va}\n"
            f"const {b} : Real = {vb}\n"
            f"const {c} : Real = {vc}\n"
            f"def {e} : Real := {a} + {b} * {c} ^ 2\n"
            f"solve {e}\n"
        )
        out.append(
            GateTask(
                cso=_cso(
                    pid, "binding_chain", "medium",
                    "An arithmetic expression is written without parentheses. Its "
                    "meaning is fixed by the precedence of the operators in the "
                    "surface notation.\n\n"
                    f"{a} = {va}. {b} = {vb}. {c} = {vc}. "
                    f"The expression is {a} + {b} * {c} ^ 2.",
                    "What is the value of the expression?",
                    AnswerSpec("numeric", float(va + vb * vc**2), tolerance=1e-9,
                               justification="exponentiation binds tightest, then "
                                             "multiplication, then addition"),
                    SemanticFacts(
                        entities={a: "Real", b: "Real", c: "Real", e: "Real"},
                        declaration_kinds={a: "const", b: "const", c: "const", e: "def"},
                    ),
                    reference, ["evaluating strictly left to right"],
                    "build_excluded",
                ),
                track=TRACK_A,
                features=frozenset({"decl_const", "def_simple", "type_scalar",
                                    "op_arithmetic", "solve",
                                    "surface_precedence_disambiguation"}),
                scored_facets=frozenset({"entities", "types", "declaration_kinds"}),
                intentionally_excluded=True,
                notes=("candidates C and D have no unparenthesised infix form, so the "
                       "question cannot be posed in them at all",),
            )
        )

    _CACHE_X = out
    return out


def build_corpus() -> list[GateTask]:
    """Everything: Track A, the recorded exclusions, and Track B."""
    return build_track_a() + build_excluded() + build_track_b()
