"""Arm renderers — projections of one Canonical Semantic Object.

HML-EVAL-001 §3, §4. Seven arms:

    A   ordinary English
    A'  structured English (the mandated 8-point reasoning schema)
    B   LaTeX / conventional notation
    C   direct existing formal or executable language (Stan or Lean)
    D   Hamiltonian, no compiler feedback
    E   Hamiltonian, with compiler feedback
    F   Hamiltonian graph view

Fairness rules enforced here rather than left to care:

1. ``prose`` and ``question`` are inserted **verbatim and identically** into every arm.
   ``verify_shared_content_identical`` asserts it.
2. Every arm receives the **same number of worked demonstrations**, each rendered in that
   arm's own notation. Giving demonstrations only to the treatment arms would measure
   demonstrations, not representation.
3. Every arm is asked for the answer in the **same machine-checkable form**.

The asymmetry that cannot be removed is recorded, not hidden: arms D/E/F carry a language
specification for a language invented weeks ago, while arm C names languages the model
already saw in pretraining. That is the out-of-distribution confound, and no prompt
construction fixes it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .cso import ANSWER_CLOSE, ANSWER_OPEN, CanonicalSemanticObject

__all__ = ["ARMS", "render_arm", "ArmPrompt", "verify_shared_content_identical", "HML_SPEC"]

ARMS = ["A", "A_prime", "B", "C", "D", "E", "F"]

ARM_LABELS = {
    "A": "ordinary English",
    "A_prime": "structured English",
    "B": "LaTeX / conventional notation",
    "C": "direct formal or executable language",
    "D": "Hamiltonian Lang, no compiler feedback",
    "E": "Hamiltonian Lang, with compiler feedback",
    "F": "Hamiltonian Lang, graph view",
}


@dataclass
class ArmPrompt:
    arm: str
    problem_id: str
    system: str
    user: str
    #: True when the harness should run a compiler-feedback repair loop for this arm
    feedback: bool = False
    #: True when the arm's output contains a formal encoding we can parse and score
    formal_encoding: bool = False


# ---------------------------------------------------------------------------
# The mandated structured-English schema (directive §3). Verbatim.
# ---------------------------------------------------------------------------

SCHEMA_A_PRIME = """Work through the following eight steps explicitly, in order, before answering.

1. Declare all mathematical objects and their types.
2. Identify which are observations, which are unknowns, which are assumptions, and which are constraints.
3. Preserve variable and quantifier scope; state which variable is bound by which quantifier, and in what order.
4. Perform one explicit transformation per step.
5. State the justification for each transformation.
6. Check dimensions, domains, and parameter restrictions.
7. State any assumption you have relied on that the problem did not give you.
8. Verify the final conclusion against the original statement."""


# ---------------------------------------------------------------------------
# Concise frozen language specification supplied to arms D, E and F
# ---------------------------------------------------------------------------

HML_SPEC = """HAMILTONIAN LANG (HML-L1) — CONCISE REFERENCE

ASCII only. One statement per line. `#` starts a comment.

DECLARATIONS — the keyword records epistemic status, not style:
  var   <name> : <Type>            a free mathematical variable
  param <name> : <Type>            an unknown to be inferred or fixed
  const <name> : <Type> = <expr>   a fixed known value
  obs   <name> : <Type> = <expr>   an observed datum
  index <name> : Natural           a dimension or counting index
  rv    <name> : RandomVariable[T] an explicitly declared random variable

TYPES:
  Bool Natural Integer Rational Real NonNegativeReal PositiveReal Probability
  Vector[T, n]  Matrix[T, m, n]  Set[T]  Function[T -> U]
  RandomVariable[T]   Distribution[T]   Quantity[D]   Proposition
  Probability is the closed interval [0,1]. It is NOT a subtype of PositiveReal
  (0 is a probability and is not positive; 2.0 is positive and is not a probability).
  Quantity dimensions are built from Mass Length Time Temperature Current Amount
  Luminosity with * / ^, e.g. Quantity[Length / Time], Quantity[Mass * Length^2 / Time^2].

DEFINITIONS AND LAWS:
  def <name> [( <p> : <T>, ... )] [: <Type>] := <expr>
  law|prior|likelihood <target> [| <given> ...] ~ <Family>(<role> := <expr>, ...)

  Distribution arguments MUST be labelled by role. Positional arguments are a parse
  error. Families and their roles:
    Normal(location, scale)        scale is the STANDARD DEVIATION, not the variance
    Beta(alpha, beta)              support [0,1]
    Binomial(trials, prob)         Bernoulli(prob)
    Poisson(rate)                  Exponential(rate)      rate = 1 / mean
    Gamma(shape, rate)             InverseGamma(shape, scale)
    Uniform(lower, upper)          LogNormal(location, scale)
    HalfNormal(scale)              Cauchy(location, scale)
    StudentT(degrees_of_freedom, location, scale)
    NormalVector(location, scale)  Dirichlet(concentration)  Categorical(probs)

PROPOSITIONS AND QUERIES:
  assume <prop>       require <prop>       prove <prop>
  minimise <expr>     maximise <expr>      solve <name> ...
  infer posterior|expectation|variance|mle|map <name> ...
  check dimension <expr> [= <dimension>]

QUANTIFIERS — the domain and the '.' are mandatory, and nesting order is meaning:
  forall x : Real . exists y : Real . y > x
  exists y : Real . forall x : Real . y > x      # a DIFFERENT statement

OPERATORS, loosest to tightest:
  => <=> | or | and | = != < <= > >= | + - | * / @ | unary - not | ^
  Chained comparison is a parse error: write `0 < x and x < 1`.
  ':=' binds a definition. '=' is mathematical equality. '~' is "is distributed as".

CONCEPTS:
  concept <Name> [extends <Name>, ...]
      parameter <name> : <Type>
      transform <name>(<p> : <Type>) : <Type> := <expr>
      invariant <name> := <proposition>
      example <name> := <proposition>
  end
  A concept with no invariant and no example is rejected."""


HML_GRAPH_SPEC = """SEMANTIC GRAPH VIEW

The same object as a set of triples, one per line, `subject -> predicate object`.
Predicates: has_type, declared_as, has_law:<role>, family, role:<role_name>,
conditioned_on, depends_on, constrains, objective_of, queries:<query>, binds,
scope_of:<quantifier>, member_of, extends.

Example — `param theta : Probability` with a Beta prior and a Binomial likelihood:
  theta -> has_type Probability
  theta -> declared_as param
  law0 -> family Beta
  law0 -> role:alpha 1
  law0 -> role:beta 1
  theta -> has_law:prior law0
  law1 -> family Binomial
  law1 -> role:trials trials
  law1 -> role:prob theta
  successes -> has_law:likelihood law1
  successes -> conditioned_on theta"""


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_BASE_SYSTEM = (
    "You are solving a mathematics problem. Be precise. Do not restate the problem. "
    "Your reply must end with the final answer wrapped in "
    f"{ANSWER_OPEN} and {ANSWER_CLOSE} markers, and nothing after the closing marker."
)


def _answer_block(cso: CanonicalSemanticObject) -> str:
    return (
        f"QUESTION\n{cso.question}\n\n"
        f"Give your final answer as {cso.answer.render_instruction()}\n"
        f"The answer must appear exactly once, wrapped in {ANSWER_OPEN} … {ANSWER_CLOSE}."
    )


def _demos_for(arm: str, demos: list[tuple[str, str]]) -> str:
    """`demos` is a list of (problem prose, worked solution in this arm's notation)."""
    if not demos:
        return ""
    out = ["WORKED EXAMPLES\n"]
    for i, (prose, solution) in enumerate(demos, 1):
        out.append(f"--- Example {i} ---\nProblem: {prose}\n\n{solution}\n")
    return "\n".join(out)


def render_arm(
    arm: str,
    cso: CanonicalSemanticObject,
    demos: list[tuple[str, str]] | None = None,
) -> ArmPrompt:
    demos = demos or []
    problem = f"PROBLEM\n{cso.prose}"
    answer = _answer_block(cso)
    demo_block = _demos_for(arm, demos)

    if arm == "A":
        user = "\n\n".join(x for x in [demo_block, problem, answer] if x)
        return ArmPrompt("A", cso.id, _BASE_SYSTEM, user)

    if arm == "A_prime":
        user = "\n\n".join(
            x for x in [demo_block, problem, "METHOD\n" + SCHEMA_A_PRIME, answer] if x
        )
        return ArmPrompt("A_prime", cso.id, _BASE_SYSTEM, user)

    if arm == "B":
        user = "\n\n".join(
            x
            for x in [
                demo_block,
                problem,
                "METHOD\nWrite your working in LaTeX, using conventional mathematical "
                "notation for every object, distribution and quantifier.",
                answer,
            ]
            if x
        )
        return ArmPrompt("B", cso.id, _BASE_SYSTEM, user)

    if arm == "C":
        user = "\n\n".join(
            x
            for x in [
                demo_block,
                problem,
                "METHOD\nExpress the problem in an existing formal or executable "
                "language before answering. Use Stan for probabilistic and statistical "
                "models, and Lean 4 for logical, quantifier and algebraic statements. "
                "Put the code in a fenced block.",
                answer,
            ]
            if x
        )
        return ArmPrompt("C", cso.id, _BASE_SYSTEM, user, formal_encoding=True)

    if arm in ("D", "E"):
        method = (
            "METHOD\nEncode the problem in Hamiltonian Lang, using the reference below. "
            "Put the encoding in a fenced block marked ```hml. Then answer the question."
        )
        if arm == "E":
            method += (
                "\nYour encoding will be checked by the Hamiltonian Lang compiler. If it "
                "reports errors you will be shown them and asked to correct the encoding."
            )
        user = "\n\n".join(
            x for x in [HML_SPEC, demo_block, problem, method, answer] if x
        )
        return ArmPrompt(
            arm, cso.id, _BASE_SYSTEM, user, feedback=(arm == "E"), formal_encoding=True
        )

    if arm == "F":
        user = "\n\n".join(
            x
            for x in [
                HML_SPEC,
                HML_GRAPH_SPEC,
                demo_block,
                problem,
                "METHOD\nEncode the problem as a Hamiltonian Lang semantic graph, one "
                "triple per line, in a fenced block marked ```triples. Then answer the "
                "question.",
                answer,
            ]
            if x
        )
        return ArmPrompt("F", cso.id, _BASE_SYSTEM, user, formal_encoding=True)

    raise ValueError(f"unknown arm {arm!r}")


def verify_shared_content_identical(cso: CanonicalSemanticObject) -> None:
    """Assert every arm carries the problem statement and question verbatim.

    Cheap, and it is the only thing standing between this experiment and an
    information-asymmetry confound introduced by a typo.
    """
    for arm in ARMS:
        p = render_arm(arm, cso)
        if cso.prose not in p.user:
            raise AssertionError(f"arm {arm}: problem prose not carried verbatim")
        if cso.question not in p.user:
            raise AssertionError(f"arm {arm}: question not carried verbatim")


#: Information differences that cannot be removed by prompt construction, per §4.
#: Every one of these biases the comparison, and the direction is stated.
INFORMATION_ASYMMETRY = [
    "Arms D/E/F carry a ~90-line specification of a language invented weeks ago. "
    "Arm C names Stan and Lean, which the model saw extensively in pretraining and "
    "needs no specification for. This is the out-of-distribution confound and prompt "
    "construction cannot remove it. Direction: against the Hamiltonian arms.",
    "Arms D/E/F therefore have a longer prompt than arms A/A'/B. Prompt tokens are "
    "recorded per call so the difference is measured rather than assumed away. "
    "Direction: raises Hamiltonian cost, does not affect its accuracy.",
    "Arm E receives compiler diagnostics that no other arm receives. This is the "
    "experimental condition under test (H4), not an accident, and arm D is the matched "
    "control for it.",
    "Arm A' receives an explicit reasoning schema that arms B and C do not. A' is the "
    "control for scaffolding, so scaffolding is deliberately confounded with A' alone.",
    "The model under test is a reasoning model: it decomposes problems internally in "
    "every arm. This compresses the A-to-A' difference and therefore inflates any "
    "A'-to-Hamiltonian difference. Direction: in favour of the Hamiltonian arms.",
]
