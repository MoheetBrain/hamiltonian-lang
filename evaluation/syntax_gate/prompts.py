"""Frozen prompt templates — five conditions, matched in information content.

Four candidate syntaxes plus a **structured-English control**. The control is not
optional: Gate 2's cost threshold is *reasoning-inclusive completion tokens no more than
twice structured English*, so without a matched structured-English arm measured on the
same tasks under the same budget, that threshold has no denominator and the gate cannot
be evaluated at all.

What "matched in information content" means here, mechanically
--------------------------------------------------------------
Three things are asserted by ``tests/evaluation/test_syntax_gate_prompts.py`` rather than
promised in a comment:

1. ``cso.prose`` and ``cso.question`` appear **verbatim** in every condition.
2. Every condition's specification block is assembled from the **same ordered list of
   sections**, and each section covers the **same set of shared-core features** in every
   condition. A condition cannot document a distinction the others omit.
3. Every condition receives the **same number of demonstrations** and the **same answer
   instruction**, generated from the frozen ``AnswerSpec``.

What it cannot mean is equal character or token counts: an S-expression spec and a JSON
spec of the same content are not the same length, and forcing them to be would mean
padding one with noise. The residual difference is therefore **measured and reported**
(``spec_size_report``) rather than assumed away — the same treatment
``evaluation/corpus/renderers.py`` gives the out-of-distribution confound.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evaluation.corpus.cso import ANSWER_CLOSE, ANSWER_OPEN, CanonicalSemanticObject
from evaluation.corpus.renderers import SCHEMA_A_PRIME

from .candidates import (
    A_V0_LINEAR,
    B_V1_LINEAR,
    C_SEXPR,
    CANDIDATE_IDS,
    CANDIDATES,
    D_JSON_GRAPH,
    SE_CONTROL,
    SHARED_CORE_FEATURES,
    SyntaxAdapter,
)
from .tasks import GateTask

__all__ = [
    "CONDITIONS",
    "G4_CONDITIONS",
    "SECTION_ORDER",
    "SECTION_COVERAGE",
    "SPEC_SECTIONS",
    "Prompt",
    "RendererUnavailable",
    "render_spec",
    "build_prompt",
    "render_demonstration",
    "spec_size_report",
    "verify_shared_content_identical",
    "CHARS_PER_TOKEN_CONSERVATIVE",
    "CHARS_PER_TOKEN_OPTIMISTIC",
    "estimate_tokens",
    "prompt_budget_report",
]

#: No tokeniser is installed in this environment (``tiktoken`` and ``tokenizers`` are both
#: absent, verified), so prompt size is estimated from characters and **labelled as an
#: estimate**. The authoritative number is the ``prompt_tokens`` the server reports per
#: call, which the harness records. Punctuation-dense formal text tokenises worse than
#: prose, so the conservative divisor is the one used for a budget decision.
CHARS_PER_TOKEN_CONSERVATIVE = 3.0
CHARS_PER_TOKEN_OPTIMISTIC = 4.0

#: The five conditions. The four candidates decide the gate; SE_CONTROL is the matched
#: control the cost threshold is defined against.
CONDITIONS: tuple[str, ...] = (*CANDIDATE_IDS, SE_CONTROL)

#: G4 must carry the control. Asserted by test: dropping it would leave the token
#: threshold unevaluable while the run still looked complete.
G4_CONDITIONS: tuple[str, ...] = CONDITIONS


class RendererUnavailable(RuntimeError):
    """Raised when a demonstration is requested for a candidate with no front end.

    Never silently substituted. A demonstration rendered in the wrong surface would
    teach the model the wrong syntax and the resulting parse rate would be attributed to
    the candidate rather than to the harness.
    """


# ---------------------------------------------------------------------------
# Specification blocks, assembled section by section
# ---------------------------------------------------------------------------

SECTION_ORDER: tuple[str, ...] = (
    "declarations", "types", "definitions", "laws", "propositions", "queries",
    "dimensions", "quantifiers", "operators", "concepts",
)

#: Which shared-core features each section is responsible for documenting. Identical for
#: every condition by construction: the table is defined once and shared.
SECTION_COVERAGE: dict[str, frozenset[str]] = {
    "declarations": frozenset(
        {"decl_var", "decl_param", "decl_const", "decl_obs", "decl_index", "decl_rv"}
    ),
    "types": frozenset(
        {"type_scalar", "type_refined", "type_quantity", "type_proposition",
         "type_random_variable", "type_function", "type_set"}
    ),
    "definitions": frozenset({"def_simple", "def_parametric"}),
    "laws": frozenset(
        {"law_labelled_roles", "law_conditioning", "law_prior", "law_likelihood"}
    ),
    "propositions": frozenset({"assume", "require", "prove"}),
    "queries": frozenset({"objective", "solve", "infer"}),
    "dimensions": frozenset({"check_dimension"}),
    "quantifiers": frozenset({"quantifier_nested", "quantifier_negation"}),
    "operators": frozenset(
        {"op_implication", "op_equivalence", "op_comparison", "op_arithmetic",
         "op_logical"}
    ),
    "concepts": frozenset({"concept_block"}),
}


@dataclass(frozen=True)
class SpecSection:
    key: str
    body: str

    @property
    def covers(self) -> frozenset[str]:
        return SECTION_COVERAGE[self.key]


_A_SECTIONS = {
    "declarations": """DECLARATIONS -- the keyword records epistemic status, not style.
  var   <name> : <Type>            a free mathematical variable
  param <name> : <Type>            an unknown to be inferred or fixed
  const <name> : <Type> = <expr>   a fixed known value
  obs   <name> : <Type> = <expr>   an observed datum
  index <name> : Natural           a counting or dimension index
  rv    <name> : RandomVariable[T] an explicitly declared random variable""",
    "types": """TYPES
  Bool Natural Integer Rational Real NonNegativeReal PositiveReal Probability
  Proposition  Set[T]  Function[T -> U]  RandomVariable[T]  Distribution[T]
  Quantity[D] where D is built from Mass Length Time Temperature Current Amount
  Luminosity with * / ^, e.g. Quantity[Mass * Length^2 / Time^2].
  Probability is the closed interval [0,1] and is NOT a subtype of PositiveReal.
  A RandomVariable[T] is not a Distribution[T] and neither is a T.""",
    "definitions": """DEFINITIONS
  def <name> : <Type> := <expr>
  def <name>(<p> : <T>, ...) : <Type> := <expr>      a parameterised definition""",
    "laws": """PROBABILITY LAWS -- arguments MUST be labelled by role; positional is an error.
  law | prior | likelihood  <target> [| <given> ...] ~ <Family>(<role> := <expr>, ...)
  Normal(location, scale)   scale is the STANDARD DEVIATION, not the variance
  Beta(alpha, beta)   Binomial(trials, prob)   Exponential(rate)   rate = 1 / mean
  Gamma(shape, rate)  Poisson(rate)  Uniform(lower, upper)
  `prior` and `likelihood` are the same construct with the role recorded.
  `| x y` records the conditioning set.""",
    "propositions": """PROPOSITIONS
  assume  <prop>      taken as given, not to be proved
  require <prop>      a proof obligation the encoding must discharge
  prove   <prop>      the goal""",
    "queries": """QUERIES
  minimise <expr>     maximise <expr>     solve <name> ...
  infer posterior | expectation | variance | mle | map <name> ...""",
    "dimensions": """DIMENSIONS
  check dimension <expr> [= <dimension>]
  A dimension is a product of base dimensions with * / and integer or rational ^,
  e.g. Mass * Length^2 / Time^2, or Dimensionless. State the dimension you expect.""",
    "quantifiers": """QUANTIFIERS -- the domain and the '.' are mandatory; nesting order is meaning.
  forall x : Real . exists y : Real . y > x
  exists y : Real . forall x : Real . y > x      # a DIFFERENT statement
  not forall x : Real . P      # differs from   forall x : Real . not P""",
    "operators": """OPERATORS, loosest to tightest:
  => <=> | or | and | = != < <= > >= | + - | * / @ | unary - not | ^
  Chained comparison is an error: write `0 < x and x < 1`.
  ':=' binds a definition, '=' is equality, '~' is "is distributed as".
  '=>' is implication and '<=>' is equivalence; neither is correlation or causation.""",
    "concepts": """CONCEPTS
  concept <Name> [extends <Name>, ...]
      parameter <name> : <Type>
      transform <name>(<p> : <Type>) : <Type> := <expr>
      invariant <name> := <proposition>
      example <name> := <proposition>
  end""",
}

_B_SECTIONS = {
    "declarations": """DECLARATIONS -- one keyword per epistemic status.
  var <name> : <Type>              a free mathematical variable
  param <name> : <Type>            an unknown to be inferred or fixed
  const <name> : <Type> = <expr>   a fixed known value
  obs <name> : <Type> = <expr>     an observed datum
  index <name> : Natural           a counting or dimension index
  rv <name> : RandomVariable[T]    an explicitly declared random variable""",
    "types": """TYPES
  Bool Natural Integer Rational Real NonNegativeReal PositiveReal Probability
  Proposition  Set[T]  Function[T -> U]  RandomVariable[T]  Distribution[T]
  Quantity[D], D over Mass Length Time Temperature Current Amount Luminosity
  with * / ^, e.g. Quantity[Mass * Length^2 / Time^2].
  Probability is [0,1] and is NOT a subtype of PositiveReal.
  A RandomVariable[T] is not a Distribution[T] and neither is a T.""",
    "definitions": """DEFINITIONS
  def <name> : <Type> := <expr>
  def <name>(<p> : <T>, ...) : <Type> := <expr>      a parameterised definition""",
    "laws": """PROBABILITY LAWS -- roles are labelled; positional arguments are an error.
  law | prior | likelihood  <target> [given <g> ...] ~ <Family>(<role> := <expr>, ...)
  Normal(location, scale)   scale is the STANDARD DEVIATION, not the variance
  Beta(alpha, beta)   Binomial(trials, prob)   Exponential(rate)   rate = 1 / mean
  Gamma(shape, rate)  Poisson(rate)  Uniform(lower, upper)
  `prior` and `likelihood` are the same construct with the role recorded.
  `given x y` records the conditioning set. (`|` is also accepted.)""",
    "propositions": """PROPOSITIONS
  assume <prop>       taken as given, not to be proved
  require <prop>      a proof obligation the encoding must discharge
  prove <prop>        the goal""",
    "queries": """QUERIES
  minimise <expr>     maximise <expr>     solve <name> ...
  infer posterior | expectation | variance | mle | map <name> ...""",
    "dimensions": """DIMENSIONS
  check dimension <expr> [= <dimension>]
  A dimension is a product of base dimensions with * / and integer or rational ^,
  e.g. Mass * Length^2 / Time^2, or Dimensionless. State the dimension you expect.""",
    "quantifiers": """QUANTIFIERS -- domain and '.' mandatory; nesting order is meaning.
  forall x : Real . exists y : Real . y > x
  exists y : Real . forall x : Real . y > x      # a DIFFERENT statement
  not forall x : Real . P      # differs from   forall x : Real . not P""",
    "operators": """OPERATORS, loosest to tightest:
  => <=> | or | and | = != < <= > >= | + - | * / @ | unary - not | ^
  Chained comparison is an error: write `0 < x and x < 1`.
  ':=' binds a definition, '=' is equality, '~' is "is distributed as".
  '=>' is implication and '<=>' is equivalence; neither is correlation or causation.""",
    "concepts": """CONCEPTS
  concept <Name> [extends <Name>, ...]
      parameter <name> : <Type>
      transform <name>(<p> : <Type>) : <Type> := <expr>
      invariant <name> := <proposition>
      example <name> := <proposition>
  end""",
}

_C_SECTIONS = {
    "declarations": """DECLARATIONS -- every form is parenthesised and prefix.
  (var <name> <type>)              a free mathematical variable
  (param <name> <type>)            an unknown to be inferred or fixed
  (const <name> <type> <expr>)     a fixed known value
  (obs <name> <type> <expr>)       an observed datum
  (index <name> Natural)           a counting or dimension index
  (rv <name> (RandomVariable <type>))  an explicitly declared random variable""",
    "types": """TYPES
  Bool Natural Integer Rational Real NonNegativeReal PositiveReal Probability
  Proposition   (Set <type>)   (Function <type> <type>)
  (RandomVariable <type>)   (Distribution <type>)
  (Quantity (dim (Mass 1) (Length 2) (Time -2)))   -- base, exponent pairs
  Probability is [0,1] and is NOT a subtype of PositiveReal.
  A (RandomVariable T) is not a (Distribution T) and neither is a T.""",
    "definitions": """DEFINITIONS
  (def <name> () <type> <expr>)
  (def <name> ((<p> <type>) ...) <type> <expr>)     a parameterised definition""",
    "laws": """PROBABILITY LAWS -- roles are nested forms; positional arguments do not exist.
  (law <target> (<Family> (<role> <expr>) ...))
  (prior <target> (<Family> (<role> <expr>) ...))
  (likelihood <target> (given <g> ...) (<Family> (<role> <expr>) ...))
  (Normal (location m) (scale s))   scale is the STANDARD DEVIATION, not the variance
  (Beta (alpha a) (beta b))   (Binomial (trials n) (prob p))
  (Exponential (rate r))   rate = 1 / mean
  (Gamma (shape a) (rate b))   (Poisson (rate r))   (Uniform (lower a) (upper b))
  `prior` and `likelihood` are the same construct with the role recorded.
  the (given ...) form records the conditioning set.""",
    "propositions": """PROPOSITIONS
  (assume <expr>)     taken as given, not to be proved
  (require <expr>)    a proof obligation the encoding must discharge
  (prove <expr>)      the goal""",
    "queries": """QUERIES
  (minimise <expr>)   (maximise <expr>)   (solve <name> ...)
  (infer posterior|expectation|variance|mle|map <name> ...)""",
    "dimensions": """DIMENSIONS
  (check dimension <expr> [<dim>])
  A dim is (dim (Base exponent) ...) over the seven base dimensions, with integer or
  rational exponents, e.g. (dim (Mass 1) (Length 2) (Time -2)). State the one you expect.""",
    "quantifiers": """QUANTIFIERS -- nesting is bracket nesting, and order is meaning.
  (forall (x Real) (exists (y Real) (> y x)))
  (exists (y Real) (forall (x Real) (> y x)))    -- a DIFFERENT statement
  (not (forall (x Real) P))    -- differs from   (forall (x Real) (not P))""",
    "operators": """OPERATORS -- prefix, no precedence, no infix position.
  (+ a b) (- a b) (* a b) (/ a b) (@ a b) (^ a b)
  (= a b) (!= a b) (< a b) (<= a b) (> a b) (>= a b)
  (and a b) (or a b) (not a) (implies a b) (iff a b)
  `implies` is implication and `iff` is equivalence; neither is correlation
  or causation. The distribution operator is the (law ...) form, not `=`.""",
    "concepts": """CONCEPTS
  (concept <Name> (extends <Name> ...)
      (parameter <name> <type>)
      (transform <name> ((<p> <type>)) <expr>)
      (invariant <expr>)
      (example <name> <expr>))""",
}

_D_SECTIONS = {
    "declarations": """DECLARATIONS -- every fact is one triple [subject, predicate, object].
  ["x", "is", "Declaration"]      ["x", "declKind", "var"]
  declKind is one of var | param | const | obs | index | rv
  ["x", "name", "x"]              ["x", "hasType", "_:t1"]
  ["x", "hasValue", "_:e1"]       -- const and obs only
  Node names beginning `_:` are blank nodes you introduce.""",
    "types": """TYPES -- a type is a node, not a string.
  ["_:t1", "is", "Type"]   ["_:t1", "typeCtor", "Real"]
  typeCtor is one of Bool Natural Integer Rational Real NonNegativeReal
  PositiveReal Probability Proposition Set Function RandomVariable
  Distribution Quantity
  ["_:t1", "typeElement", "_:t2"]      -- Set, Function, RandomVariable, Distribution
  ["_:t1", "dimExponent", "_:a1"] ["_:a1", "dimBase", "Mass"] ["_:a1", "dimPower", "1"]
  Probability is [0,1] and is NOT a subtype of PositiveReal.
  A RandomVariable of T is not a Distribution of T and neither is a T.""",
    "definitions": """DEFINITIONS
  ["d", "is", "Definition"]  ["d", "name", "d"]  ["d", "hasType", "_:t1"]
  ["d", "definedAs", "_:e1"]
  A parameterised definition adds ["d", "hasParam", "p"] for each formal, in order.""",
    "laws": """PROBABILITY LAWS -- roles are MANDATORY; no positional argument exists.
  ["_:l1", "is", "Law"]     ["_:l1", "lawRole", "prior"]      -- law | prior | likelihood
  ["_:l1", "lawTarget", "theta"]   ["_:l1", "lawGiven", "z"]  -- repeatable
  ["_:l1", "lawDist", "_:d1"]      ["_:d1", "distFamily", "Normal"]
  ["_:d1", "distArg", "_:a1"] ["_:a1", "argRole", "scale"] ["_:a1", "argValue", "_:e1"]
  Normal roles location, scale; scale is the STANDARD DEVIATION, not the variance.
  Beta alpha, beta. Binomial trials, prob. Exponential rate, rate = 1 / mean.
  Gamma shape, rate. Poisson rate. Uniform lower, upper.
  prior and likelihood are the same construct with the role recorded;
  lawGiven records the conditioning set.""",
    "propositions": """PROPOSITIONS
  ["_:s1", "is", "Assumption"]  ["_:s1", "asserts", "_:e1"]   taken as given
  ["_:s2", "is", "Constraint"]  ["_:s2", "asserts", "_:e2"]   a proof obligation
  ["_:s3", "is", "Proof"]       ["_:s3", "asserts", "_:e3"]   the goal""",
    "queries": """QUERIES
  ["_:o1", "is", "Objective"] ["_:o1", "objDirection", "minimise"|"maximise"]
  ["_:o1", "objExpr", "_:e1"]
  ["_:s1", "is", "Solve"]  ["_:s1", "solveFor", "x"]          -- repeatable
  ["_:i1", "is", "Infer"]  ["_:i1", "inferQuery", "posterior"|"expectation"|
  "variance"|"mle"|"map"]  ["_:i1", "inferTarget", "x"]       -- repeatable""",
    "dimensions": """DIMENSIONS
  ["_:c1", "is", "Check"]  ["_:c1", "checkKind", "dimension"]
  ["_:c1", "asserts", "_:e1"]  ["_:c1", "checkExpected", "_:t1"]""",
    "quantifiers": """QUANTIFIERS -- nesting is the quantBody edge, and order is meaning.
  ["_:q1","is","Quantifier"] ["_:q1","quantKind","forall"] ["_:q1","quantVar","x"]
  ["_:q1","quantBody","_:q2"]
  ["_:q2","is","Quantifier"] ["_:q2","quantKind","exists"] ["_:q2","quantVar","y"]
  Swapping which node is outer gives a DIFFERENT statement.
  Negation is a UnaryOp node with op "not"; whether it wraps the quantifier or its
  body is the difference between two different statements.""",
    "operators": """OPERATORS -- every expression is reified; there is no infix form.
  ["_:e1","is","BinOp"|"Comparison"|"LogicalOp"|"UnaryOp"]
  ["_:e1","op","+"|"-"|"*"|"/"|"@"|"^"|"="|"!="|"<"|"<="|">"|">="|
  "and"|"or"|"not"|"implies"|"iff"]
  ["_:e1","lhs","_:e2"] ["_:e1","rhs","_:e3"] ["_:e1","operand","_:e2"]
  ["_:e2","is","Literal"] ["_:e2","litValue","3"]
  ["_:e3","is","Ref"] ["_:e3","refTo","x"]
  "implies" is implication and "iff" is equivalence; neither is correlation or
  causation. Distribution is the Law node, never the "=" operator.""",
    "concepts": """CONCEPTS
  ["C","is","Concept"] ["C","name","C"] ["C","extends","B"]
  ["C","hasMember","_:m1"] ["_:m1","is","ConceptMember"] ["_:m1","name","p"]
  ["_:m1","memberKind","parameter"|"transform"|"invariant"|"example"]
  ["_:m1","memberParam","p"] ["_:m1","memberBody","_:e1"]""",
}

_SE_SECTIONS = {
    "declarations": """DECLARE EVERY OBJECT AND ITS EPISTEMIC STATUS.
  State, for each object, whether it is a free variable, an unknown to be inferred,
  a fixed known value, an observed datum, a counting or dimension index, or an
  explicitly declared random variable. These are six different statuses.""",
    "types": """STATE THE TYPE OF EVERY OBJECT.
  Boolean, natural, integer, rational, real, non-negative real, positive real,
  probability, proposition, set of, function from-to, random variable of,
  distribution over, or physical quantity with a dimension built from mass, length,
  time, temperature, current, amount and luminosity.
  A probability lies in [0,1] and is not the same kind of thing as a positive real.
  A random variable is not a distribution and neither is an ordinary value.""",
    "definitions": """STATE EVERY DEFINITION.
  Give the defined name, its type, and the expression defining it. If the definition
  takes arguments, name each argument and give its type.""",
    "laws": """STATE EVERY PROBABILITY LAW BY ROLE.
  Name the family and say which quantity fills which role; never rely on argument
  order. Say whether the law is a prior, a likelihood or an unqualified law, and list
  the quantities it is conditioned on.
  The scale of a normal law is its standard deviation, not its variance.
  Beta takes alpha and beta. Binomial takes trials and probability. The rate of an
  exponential law is the reciprocal of its mean. Gamma takes shape and rate.
  Poisson takes a rate. Uniform takes a lower and an upper bound.""",
    "propositions": """SEPARATE THE THREE KINDS OF PROPOSITION.
  Say which propositions are assumed and taken as given, which are obligations the
  argument must discharge, and which is the goal to be proved.""",
    "queries": """STATE WHAT IS BEING ASKED FOR.
  Whether a quantity is being minimised or maximised, which unknowns are being solved
  for, and which inferential query is required: posterior, expectation, variance,
  maximum likelihood estimate, or maximum a posteriori estimate.""",
    "dimensions": """CHECK DIMENSIONS EXPLICITLY.
  State the physical dimension of each quantity and of the derived expression, and
  state the dimension you expect the result to have.""",
    "quantifiers": """PRESERVE QUANTIFIER SCOPE AND ORDER.
  Say which variable is bound by which quantifier and in what order. "For every x
  there is a y" is a different statement from "there is a y such that for every x".
  Say whether a negation sits outside a quantifier or inside its body; those are
  different statements too.""",
    "operators": """KEEP THE OPERATORS DISTINCT.
  Distinguish equality from "is distributed as" and from approximation. Distinguish
  implication, which holds in one direction, from equivalence, which holds in both;
  neither is correlation and neither is causation. State the intended grouping of any
  arithmetic or comparison you rely on, rather than leaving it to precedence.""",
    "concepts": """DEFINE ANY STRUCTURE YOU INTRODUCE.
  Give it a name, its typed parameters, any transformation it supports, and at least
  one invariant or example it must satisfy. A structure with neither is not defined.""",
}

SPEC_SECTIONS: dict[str, tuple[SpecSection, ...]] = {
    A_V0_LINEAR: tuple(SpecSection(k, _A_SECTIONS[k]) for k in SECTION_ORDER),
    B_V1_LINEAR: tuple(SpecSection(k, _B_SECTIONS[k]) for k in SECTION_ORDER),
    C_SEXPR: tuple(SpecSection(k, _C_SECTIONS[k]) for k in SECTION_ORDER),
    D_JSON_GRAPH: tuple(SpecSection(k, _D_SECTIONS[k]) for k in SECTION_ORDER),
    SE_CONTROL: tuple(SpecSection(k, _SE_SECTIONS[k]) for k in SECTION_ORDER),
}

_SPEC_HEADERS = {
    A_V0_LINEAR: (
        "HAMILTONIAN LANG (LABELLED-LINEAR) -- CONCISE REFERENCE\n"
        "ASCII only. One statement per line. `#` starts a comment. A file may open "
        "with `module <Name>`."
    ),
    B_V1_LINEAR: (
        "HAMILTONIAN LANG (SIMPLIFIED LABELLED-LINEAR) -- CONCISE REFERENCE\n"
        "ASCII only. One statement per line. `#` starts a comment. A file may open "
        "with `module <Name>`."
    ),
    C_SEXPR: (
        "HAMILTONIAN LANG (PREFIX / S-EXPRESSION) -- CONCISE REFERENCE\n"
        "ASCII only. Everything is a parenthesised form; whitespace and newlines are "
        "pure separators. `;` starts a comment. A file is "
        "`(module <Name> <statement> ...)`."
    ),
    D_JSON_GRAPH: (
        "HAMILTONIAN LANG (CONSTRAINED JSON GRAPH) -- CONCISE REFERENCE\n"
        "ASCII only. Emit one JSON object:\n"
        '  {"module": "<Name>", "triples": [[subject, predicate, object], ...]}\n'
        "Every fact is one triple. The predicate vocabulary below is closed: a triple "
        "with any other predicate is rejected. Triples are unordered; where statement "
        'order matters, add ["<node>", "order", "<n>"].'
    ),
    SE_CONTROL: (
        "STRUCTURED ENGLISH -- THE REQUIRED METHOD\n"
        "Write in ordinary English, but make every distinction below explicit rather "
        "than leaving it to be inferred."
    ),
}

_METHOD = {
    A_V0_LINEAR: (
        "Encode the problem in Hamiltonian Lang using the reference above. Put the "
        "encoding in a fenced block marked ```hml. Then answer the question."
    ),
    B_V1_LINEAR: (
        "Encode the problem in Hamiltonian Lang using the reference above. Put the "
        "encoding in a fenced block marked ```hml. Then answer the question."
    ),
    C_SEXPR: (
        "Encode the problem in the prefix notation above. Put the encoding in a fenced "
        "block marked ```sexpr. Then answer the question."
    ),
    D_JSON_GRAPH: (
        "Encode the problem as the JSON graph above. Put the JSON in a fenced block "
        "marked ```json. Then answer the question."
    ),
    SE_CONTROL: (
        "Work through the eight steps below explicitly, in order, applying the "
        "distinctions above. Then answer the question."
    ),
}

_BASE_SYSTEM = (
    "You are solving a mathematics problem. Be precise. Do not restate the problem. "
    "Your reply must end with the final answer wrapped in "
    f"{ANSWER_OPEN} and {ANSWER_CLOSE} markers, and nothing after the closing marker."
)


def render_spec(condition: str) -> str:
    if condition not in SPEC_SECTIONS:
        raise ValueError(f"unknown condition {condition!r}")
    parts = [_SPEC_HEADERS[condition]]
    parts += [s.body for s in SPEC_SECTIONS[condition]]
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Demonstrations
# ---------------------------------------------------------------------------


def _se_demonstration(task: GateTask) -> str:
    """A deterministic structured-English worked solution.

    Built from the frozen ``SemanticFacts``, so it carries exactly the content the
    formal demonstrations carry and no more. Hand-writing it per task is how the
    control arm quietly acquires extra information.
    """
    f = task.cso.semantics
    lines = []
    if f.entities:
        lines.append(
            "Objects and types: "
            + "; ".join(f"{k} is a {v}" for k, v in sorted(f.entities.items()))
            + "."
        )
    if f.declaration_kinds:
        lines.append(
            "Epistemic status: "
            + "; ".join(f"{k} is declared {v}" for k, v in sorted(f.declaration_kinds.items()))
            + "."
        )
    if f.law_families:
        lines.append(
            "Laws: "
            + "; ".join(f"{k} follows a {v} law" for k, v in sorted(f.law_families.items()))
            + "."
        )
    for target, roles in sorted(f.laws.items()):
        lines.append(
            f"Roles for {target}: "
            + "; ".join(f"{r} is filled by {v}" for r, v in sorted(roles.items()))
            + "."
        )
    for target, given in sorted(f.conditioning.items()):
        lines.append(f"{target} is conditioned on {', '.join(given)}.")
    if f.quantifier_order:
        lines.append("Quantifiers, outermost first: " + " then ".join(f.quantifier_order) + ".")
    if f.dimensions:
        lines.append(
            "Dimensions: "
            + "; ".join(f"{k} has dimension {v}" for k, v in sorted(f.dimensions.items()))
            + "."
        )
    if f.constraints:
        lines.append("Obligations: " + "; ".join(f.constraints) + ".")
    if f.objective:
        lines.append(f"Objective: {f.objective}.")
    if not lines:
        lines.append("No structural facts are recorded for this demonstration.")
    return "\n".join(lines)


def render_demonstration(
    task: GateTask,
    condition: str,
    adapters: dict[str, SyntaxAdapter | None] | None = None,
) -> str:
    """One worked example in the condition's own notation, plus its answer."""
    answer = f"{ANSWER_OPEN}{task.cso.answer.value}{ANSWER_CLOSE}"
    if condition == SE_CONTROL:
        return f"{_se_demonstration(task)}\n\n{answer}"
    adapters = adapters if adapters is not None else {}
    adapter = adapters.get(condition)
    if adapter is None:
        raise RendererUnavailable(
            f"no front end for {condition}; demonstrations cannot be rendered until "
            "evaluation.syntax_acquisition supplies one (Phase F3). "
            "Curriculum size 0 needs no demonstrations and remains runnable."
        )
    surface = adapter.render(task.cso.reference_hml)
    tag = CANDIDATES[condition].fence_tags[0]
    return f"```{tag}\n{surface}\n```\n\n{answer}"


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Prompt:
    condition: str
    task_id: str
    system: str
    user: str
    curriculum_size: int
    #: True when the condition's output contains a formal encoding the scorer parses.
    formal_encoding: bool
    demonstration_ids: tuple[str, ...] = field(default_factory=tuple)


def _answer_block(cso: CanonicalSemanticObject) -> str:
    return (
        f"QUESTION\n{cso.question}\n\n"
        f"Give your final answer as {cso.answer.render_instruction()}\n"
        f"The answer must appear exactly once, wrapped in {ANSWER_OPEN} ... {ANSWER_CLOSE}."
    )


def build_prompt(
    task: GateTask,
    condition: str,
    demonstrations: list[GateTask] | None = None,
    adapters: dict[str, SyntaxAdapter | None] | None = None,
) -> Prompt:
    """Assemble one frozen prompt. Same shape in every condition, by construction."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}")
    demos = demonstrations or []
    blocks: list[str] = [render_spec(condition)]
    if demos:
        rendered = ["WORKED EXAMPLES\n"]
        for i, d in enumerate(demos, 1):
            rendered.append(
                f"--- Example {i} ---\nProblem: {d.cso.prose}\n\n"
                f"{render_demonstration(d, condition, adapters)}\n"
            )
        blocks.append("\n".join(rendered))
    blocks.append(f"PROBLEM\n{task.cso.prose}")
    method = "METHOD\n" + _METHOD[condition]
    if condition == SE_CONTROL:
        method += "\n\n" + SCHEMA_A_PRIME
    blocks.append(method)
    blocks.append(_answer_block(task.cso))
    return Prompt(
        condition=condition,
        task_id=task.id,
        system=_BASE_SYSTEM,
        user="\n\n".join(blocks),
        curriculum_size=len(demos),
        formal_encoding=condition != SE_CONTROL,
        demonstration_ids=tuple(d.id for d in demos),
    )


def verify_shared_content_identical(task: GateTask) -> None:
    """Assert every condition carries the problem and question verbatim.

    Cheap, and the only thing between this experiment and an information-asymmetry
    confound introduced by a typo.
    """
    for condition in CONDITIONS:
        p = build_prompt(task, condition)
        if task.cso.prose not in p.user:
            raise AssertionError(f"{condition}: problem prose not carried verbatim")
        if task.cso.question not in p.user:
            raise AssertionError(f"{condition}: question not carried verbatim")


def estimate_tokens(text: str) -> dict[str, int]:
    """A character-based estimate, both directions, never presented as a measurement."""
    return {
        "characters": len(text),
        "estimated_tokens_conservative": int(len(text) / CHARS_PER_TOKEN_CONSERVATIVE),
        "estimated_tokens_optimistic": int(len(text) / CHARS_PER_TOKEN_OPTIMISTIC),
    }


def prompt_budget_report(
    task: GateTask,
    demonstrations_by_size: dict[int, list[GateTask]],
    adapters: dict[str, SyntaxAdapter | None] | None = None,
    per_slot_token_budget: int = 8192,
) -> dict[str, Any]:
    """Does each curriculum fit the per-slot context budget?

    ``OLLAMA_NUM_PARALLEL=4`` divides the 32768-token context into four 8192-token slots
    (``docs/evaluation/EXECUTION_ENVIRONMENT.md`` Finding 3), so the longest prompt must
    be measured against **8192, not 32768**. If a curriculum does not fit, the correct
    response is to lower the slot count or shorten the curriculum *as a design decision*
    — never to let the server truncate it, because a truncated curriculum is a different
    experimental condition wearing the same label.
    """
    rows: list[dict[str, Any]] = []
    for size, demos in sorted(demonstrations_by_size.items()):
        for condition in CONDITIONS:
            if condition in CANDIDATE_IDS and (adapters or {}).get(condition) is None:
                rows.append({
                    "curriculum_size": size, "condition": condition,
                    "NOT MEASURED": True,
                    "reason": "no front end; demonstrations cannot be rendered",
                })
                continue
            p = build_prompt(task, condition, demos, adapters)
            est = estimate_tokens(p.system + "\n" + p.user)
            rows.append({
                "curriculum_size": size,
                "condition": condition,
                **est,
                "per_slot_token_budget": per_slot_token_budget,
                "fits_conservative": est["estimated_tokens_conservative"]
                <= per_slot_token_budget,
                "fits_optimistic": est["estimated_tokens_optimistic"]
                <= per_slot_token_budget,
            })
    measured = [r for r in rows if not r.get("NOT MEASURED")]
    by_size: dict[int, list[dict[str, Any]]] = {}
    for r in measured:
        by_size.setdefault(r["curriculum_size"], []).append(r)
    per_size = {
        size: {
            "fits_every_condition": all(r["fits_conservative"] for r in group),
            "conditions_over_budget": sorted(
                r["condition"] for r in group if not r["fits_conservative"]
            ),
            "largest_estimated_tokens": max(
                r["estimated_tokens_conservative"] for r in group
            ),
        }
        for size, group in sorted(by_size.items())
    }
    # "Every condition", not "some condition". A curriculum that fits three surfaces and
    # overflows the fourth is not a runnable curriculum: it would silently become a
    # different experimental condition for that one surface.
    largest_fitting = max(
        (s for s, v in per_size.items() if v["fits_every_condition"]), default=None
    )
    return {
        "per_slot_token_budget": per_slot_token_budget,
        "estimate_only": True,
        "authoritative_measurement": "prompt_tokens recorded per call by the harness",
        "largest_curriculum_that_fits_every_condition": largest_fitting,
        "per_size": per_size,
        "rows": rows,
    }


def spec_size_report() -> dict[str, dict[str, int]]:
    """The residual, unremovable difference between conditions, measured.

    Character counts are not token counts; the tournament records prompt tokens per
    call, and that measurement supersedes this one. This exists so the asymmetry is
    visible before any call is made.
    """
    out: dict[str, dict[str, int]] = {}
    for condition in CONDITIONS:
        spec = render_spec(condition)
        out[condition] = {
            "spec_characters": len(spec),
            "spec_lines": spec.count("\n") + 1,
            "sections": len(SPEC_SECTIONS[condition]),
            "features_documented": len(
                frozenset().union(*(s.covers for s in SPEC_SECTIONS[condition]))
            ),
        }
    out["_shared_core_feature_count"] = {"features": len(SHARED_CORE_FEATURES)}
    return out
