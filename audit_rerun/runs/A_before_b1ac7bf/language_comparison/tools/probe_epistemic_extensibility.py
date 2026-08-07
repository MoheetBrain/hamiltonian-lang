"""Epistemic-state and extensibility probes for HML (mission sections 11 and 15).

These are the two axes on which HML claims to differ from every reference system, so they
get the sharpest test. Two questions are kept strictly apart:

1. **Is the distinction expressible?** Can the source say "this is assumed" rather than
   "this is derived"?
2. **Is the distinction ENFORCED?** Does anything break if you use an assumed quantity
   where a derived one belongs, or does the keyword merely decorate?

A syntax-only epistemic system is worth very little: it records an intention that nothing
checks. The probes below try to make the compiler care about the distinction, and record
what actually happens.

For extensibility the question is the one that decides whether a language can grow:
can a user add a new mathematical abstraction INSIDE the language, or must the compiler be
edited? Each result is classified LANGUAGE_LEVEL / LIBRARY_LEVEL / COMPILER_CHANGE_REQUIRED.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hml_probe import Probe, emit, run_all, summarise  # noqa: E402

E = "epistemic"
X = "extensibility"

PROBES: list[Probe] = [
    # ---------------- epistemic states: expressible? ----------------
    Probe(
        id="EPI.DECLARED",
        group=E,
        capability="EPISTEMIC.DECLARED",
        source="module M\nvar x : Real",
        expectation="A symbol declared with a type and no value.",
        mode="accept",
    ),
    Probe(
        id="EPI.DEFINED",
        group=E,
        capability="EPISTEMIC.DEFINED",
        source="module M\nconst c : Real = 2.0\ndef d := c + 1.0",
        expectation="A defined quantity with a defining expression.",
        mode="accept",
    ),
    Probe(
        id="EPI.ASSUMED",
        group=E,
        capability="EPISTEMIC.ASSUMED",
        source="module M\nvar x : Real\nassume x > 0.0",
        expectation="An assumption: taken as true without proof.",
        mode="accept",
    ),
    Probe(
        id="EPI.REQUIRED",
        group=E,
        capability="EPISTEMIC.REQUIRED",
        source="module M\nvar x : Real\nrequire x > 0.0",
        expectation="A requirement: must hold, generates an obligation.",
        mode="accept",
    ),
    Probe(
        id="EPI.OBSERVED",
        group=E,
        capability="EPISTEMIC.OBSERVED",
        source="module M\nobs n : Natural = 10",
        expectation="Observed data, distinct from a parameter or a constant.",
        mode="accept",
    ),
    Probe(
        id="EPI.PARAMETER",
        group=E,
        capability="EPISTEMIC.PARAMETER",
        source="module M\nparam theta : Probability",
        expectation="An unknown parameter, distinct from observed data.",
        mode="accept",
    ),
    Probe(
        id="EPI.GOAL_PROVE",
        group=E,
        capability="EPISTEMIC.GOAL / PROOF_OBLIGATION",
        source="module M\nprove forall x : Real . x = x",
        expectation="A goal to be proved.",
        mode="accept",
    ),
    Probe(
        id="EPI.OBJECTIVE",
        group=E,
        capability="EPISTEMIC.OBJECTIVE",
        source="module M\nparam x : Real\ndef f := x * x\nminimise f",
        expectation="An optimisation objective as a distinct epistemic act.",
        mode="accept",
    ),
    Probe(
        id="EPI.CONJECTURED",
        group=E,
        capability="EPISTEMIC.CONJECTURED",
        source="module M\nconjecture forall x : Real . x = x",
        expectation=(
            "A conjecture: believed, not assumed, not proved. Distinct from both `assume` "
            "and `prove`. Probing whether the state exists."
        ),
        mode="observe",
    ),
    Probe(
        id="EPI.REFUTED",
        group=E,
        capability="EPISTEMIC.REFUTED",
        source="module M\nrefute forall x : Real . x > 0.0",
        expectation="An explicitly refuted proposition. Probing whether the state exists.",
        mode="observe",
    ),
    Probe(
        id="EPI.APPROXIMATE",
        group=E,
        capability="EPISTEMIC.APPROXIMATE",
        source="module M\nconst pi_a : Real ~= 3.14159",
        expectation=(
            "An approximate equality, distinct from exact `=`. The project forbids "
            "conflating `=` with approximation; probing whether approximation is sayable."
        ),
        mode="observe",
    ),
    Probe(
        id="EPI.UNCERTAIN",
        group=E,
        capability="EPISTEMIC.UNCERTAIN",
        source="module M\nconst m : Real = 9.81 +- 0.02",
        expectation=(
            "A measured value with uncertainty. Central to scientific mathematics; "
            "probing whether uncertainty is representable at the value level."
        ),
        mode="observe",
    ),
    Probe(
        id="EPI.PROHIBITED_ASSUMPTION",
        group=E,
        capability="EPISTEMIC.PROHIBITED_ASSUMPTION",
        source="module M\nvar x : Real\nprohibit assume x > 0.0",
        expectation=(
            "Marking an assumption as forbidden -- 'do not assume normality'. Probing "
            "whether the state exists."
        ),
        mode="observe",
    ),
    # ---------------- epistemic states: ENFORCED? ----------------
    Probe(
        id="EPI.ENFORCE.OBS_VS_PARAM",
        group=E,
        capability="EPISTEMIC.ENFORCEMENT",
        source=(
            "module M\nobs n : Natural = 10\nparam k : Natural\n"
            "def total := n + k"
        ),
        expectation=(
            "Mixing observed data and an unknown parameter in one expression. If this is "
            "accepted with no distinction recorded downstream, the epistemic tags are "
            "syntax only. (Accepting it is arguably CORRECT -- the question is whether the "
            "distinction survives into the canonical form, checked separately.)"
        ),
        mode="observe",
    ),
    Probe(
        id="EPI.ENFORCE.INFER_WITHOUT_LAW",
        group=E,
        capability="EPISTEMIC.ENFORCEMENT",
        source="module M\nparam theta : Probability\ninfer posterior theta",
        expectation=(
            "Asking for a posterior for a symbol with no law. SPEC says this is HML-S604. "
            "A genuine epistemic consistency check."
        ),
        mode="reject",
    ),
    Probe(
        id="EPI.ENFORCE.TWO_LAWS",
        group=E,
        capability="EPISTEMIC.ENFORCEMENT",
        source=(
            "module M\nparam t : Probability\nprior t ~ Beta(alpha := 1, beta := 1)\n"
            "prior t ~ Beta(alpha := 2, beta := 2)"
        ),
        expectation="A symbol has at most one law (HML-S601). Contradictory priors.",
        mode="reject",
    ),
    Probe(
        id="EPI.ENFORCE.CONCEPT_WITHOUT_CONTENT",
        group=E,
        capability="EPISTEMIC.ENFORCEMENT",
        source="module M\nconcept Vague\n  parameter x : Real\nend",
        expectation=(
            "A concept with no invariant and no example must be rejected (HML-S603): "
            "'sounds plausible' is not a definition. A distinctive HML check."
        ),
        mode="reject",
    ),
    # ---------------- extensibility ----------------
    Probe(
        id="EXT.NEW_FUNCTION",
        group=X,
        capability="EXTENSIBILITY.USER_FUNCTION",
        source="module M\ndef square(u : Real) : Real := u * u",
        expectation="A user-defined function, in-language.",
        mode="accept",
    ),
    Probe(
        id="EXT.NEW_CONCEPT",
        group=X,
        capability="EXTENSIBILITY.USER_ABSTRACTION",
        source=(
            "module M\nconcept Metric\n  parameter d : Function[Real, Real -> NonNegativeReal]\n"
            "  invariant nonneg := forall a : Real . a = a\n"
            "  example euclidean := d = d\nend"
        ),
        expectation="A new mathematical abstraction defined in-language via `concept`.",
        mode="accept",
    ),
    Probe(
        id="EXT.NEW_TYPE",
        group=X,
        capability="EXTENSIBILITY.USER_TYPE",
        source="module M\ntype Complexish := Real\nvar z : Complexish",
        expectation=(
            "A user-defined type alias or new type. If absent, every new type requires a "
            "compiler edit -- a hard ceiling on growth."
        ),
        mode="observe",
    ),
    Probe(
        id="EXT.NEW_DISTRIBUTION",
        group=X,
        capability="EXTENSIBILITY.USER_DISTRIBUTION",
        source=(
            "module M\ndistribution Gamma(shape : PositiveReal, rate : PositiveReal)\n"
            "rv X : RandomVariable[PositiveReal]\nlaw X ~ Gamma(shape := 1.0, rate := 1.0)"
        ),
        expectation=(
            "Declaring a new distribution family in-language. With only 7 built-in "
            "families, this determines whether statistics can grow without compiler edits."
        ),
        mode="observe",
    ),
    Probe(
        id="EXT.USE_UNDECLARED_DISTRIBUTION",
        group=X,
        capability="EXTENSIBILITY.USER_DISTRIBUTION",
        source=(
            "module M\nrv X : RandomVariable[PositiveReal]\n"
            "law X ~ Gamma(shape := 1.0, rate := 1.0)"
        ),
        expectation=(
            "Using a distribution family that is not built in. Confirms the closed-world "
            "family set."
        ),
        mode="observe",
    ),
    Probe(
        id="EXT.NEW_OPERATOR",
        group=X,
        capability="EXTENSIBILITY.USER_OPERATOR",
        source="module M\noperator <*> (a : Real, b : Real) : Real := a * b",
        expectation="A user-defined operator. Probing whether the grammar is extensible.",
        mode="observe",
    ),
    Probe(
        id="EXT.NEW_DIMENSION",
        group=X,
        capability="EXTENSIBILITY.USER_DIMENSION",
        source="module M\ndimension Information\nparam h : Quantity[Information]",
        expectation=(
            "A new base dimension beyond the seven SI bases. Probing whether the "
            "dimension system is closed."
        ),
        mode="observe",
    ),
    Probe(
        id="EXT.NEW_INFERENCE_RULE",
        group=X,
        capability="EXTENSIBILITY.USER_INFERENCE_RULE",
        source=(
            "module M\nrule modus_ponens(p : Proposition, q : Proposition) := "
            "(p and (p => q)) => q"
        ),
        expectation=(
            "A user-declared inference rule. Determines whether the reasoning layer is "
            "extensible or fixed by the compiler."
        ),
        mode="observe",
    ),
    Probe(
        id="EXT.IMPORT_MODULE",
        group=X,
        capability="EXTENSIBILITY.MODULE_SYSTEM",
        source="module M\nimport OtherModule",
        expectation=(
            "Importing another module. Without it there is no library layer at all and "
            "every file is closed-world."
        ),
        mode="observe",
    ),
]


def main() -> int:
    results = run_all(PROBES)
    out = (
        Path(__file__).resolve().parents[1]
        / "matrices"
        / "HML_EPISTEMIC_EXTENSIBILITY_PROBES.json"
    )
    emit(results, out)
    cur = None
    for r in results:
        if r.probe.group != cur:
            cur = r.probe.group
            print(f"\n--- {cur.upper()} ---")
        print(
            f"{r.probe.id:38s} {r.verdict:9s} ok={str(r.ok):5s} "
            f"{','.join(r.codes) if r.codes else '(clean)'}"
        )
    print(f"\n{summarise(results)['by_verdict']}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
