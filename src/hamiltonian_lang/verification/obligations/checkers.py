"""The nine checkers. Each one decides a narrow class and refuses everything else.

A checker returns ``None`` when the obligation is not its business. It returns a
:class:`Judgement` when it applied — including when applying produced no answer, which
is ``INCONCLUSIVE`` and is still a result worth recording. Nothing in this module may
return ``DISCHARGED`` for a shape it did not actually decide; the record schema refuses
to build such a record, but the checkers are written so the schema never has to.

The order in :data:`DEFAULT_CHECKERS` is the policy. Exact closed evaluation comes
first because it is the strongest evidence available; refutation by sampling comes last
because it can only ever say *no*.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Protocol

from ...ast.nodes import (
    BinOp,
    Call,
    Comparison,
    Expr,
    Literal,
    LogicalOp,
    Quantifier,
    Ref,
    UnaryOp,
)
from ...types import (
    Dimension,
    Type,
    dimension_of,
    is_subtype,
    literal_inhabits,
)
from .domains import (
    Domain,
    assignments,
    constant_points,
    domain_of_type,
    sample_points,
)
from .evaluate import Environment, Undecidable, evaluate, free_names, interval_of
from .records import ObligationClass, ObligationMode, ObligationStatus, Witness

__all__ = [
    "Judgement",
    "ObligationTask",
    "Checker",
    "DEFAULT_CHECKERS",
    "SatisfiabilityChecker",
    "ClosedArithmeticEqualityChecker",
    "ClosedInequalityChecker",
    "LogicalConsistencyChecker",
    "FiniteSetMembershipChecker",
    "LiteralRefinementBoundChecker",
    "DimensionCompatibilityChecker",
    "DeclaredSignatureChecker",
    "SymbolicIdentityChecker",
    "NumericalCounterexampleChecker",
    "parse_dimension_text",
    "dimension_of_expr",
    "partiality_risk",
]


@dataclass(frozen=True)
class Judgement:
    """One checker's answer about one obligation."""

    status: ObligationStatus
    obligation_class: ObligationClass
    detail: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    witness: Witness | None = None
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObligationTask:
    """Everything a checker is given. Read-only by construction."""

    obligation_id: str
    kind: str
    statement: str
    proposition: Expr | None
    env: Environment
    #: What holding *means* here. See :class:`ObligationMode`. Checkers that prove a
    #: universal claim must refuse a satisfiability obligation and the reverse; the two
    #: have opposite sound directions and conflating them is the central hazard.
    mode: ObligationMode = ObligationMode.UNIVERSAL
    #: Sibling obligations, for checkers that reason across a whole module.
    siblings: tuple[ObligationTask, ...] = ()
    #: Free-form payload from the engine (the asserted dimension, the call site, ...).
    context: Mapping[str, Any] = field(default_factory=dict)

    def free(self) -> set[str]:
        if self.proposition is None:
            return set()
        return free_names(self.proposition, self.env)

    def closed(self) -> bool:
        return self.proposition is not None and not self.free()


class Checker(Protocol):
    name: str
    version: str
    obligation_class: ObligationClass

    def judge(self, task: ObligationTask) -> Judgement | None:
        ...


def _unsupported(cls: ObligationClass, detail: str, **evidence: Any) -> Judgement:
    return Judgement(ObligationStatus.UNSUPPORTED, cls, detail, evidence)


def _shape(expr: Expr | None) -> str:
    return type(expr).__name__ if expr is not None else "none"


def _literals(expr: object, depth: int = 0) -> list[Fraction]:
    """Every numeric literal in an expression, in source order.

    Fed to the sample grid so that a constraint's own constants are among the candidate
    values. Purely a search heuristic: nothing is concluded from a candidate until the
    proposition has actually been evaluated at it.
    """
    if depth > 32:
        return []
    out: list[Fraction] = []
    if isinstance(expr, Literal) and not isinstance(expr.value, bool):
        try:
            out.append(Fraction(expr.value))
        except (TypeError, ValueError):
            return []
        return out
    for attr in ("left", "right", "operand", "body", "base"):
        child = getattr(expr, attr, None)
        if isinstance(child, Expr):
            out.extend(_literals(child, depth + 1))
    for arg in getattr(expr, "args", ()) or ():
        if isinstance(arg, Expr):
            out.extend(_literals(arg, depth + 1))
    return out


# ---------------------------------------------------------------------------
# 1-2. Closed arithmetic
# ---------------------------------------------------------------------------


class _ClosedComparisonChecker:
    """Shared body for the two closed-comparison classes."""

    name = "closed_evaluator"
    version = "hml-obl-1.0.0"
    obligation_class = ObligationClass.CLOSED_ARITHMETIC_EQUALITY
    _ops: tuple[str, ...] = ()

    def judge(self, task: ObligationTask) -> Judgement | None:
        expr = task.proposition
        if not isinstance(expr, Comparison) or expr.op not in self._ops:
            return None
        if not task.closed():
            return None
        try:
            left = evaluate(expr.left, task.env)
            right = evaluate(expr.right, task.env)
            verdict = evaluate(expr, task.env)
        except Undecidable as exc:
            return Judgement(
                ObligationStatus.UNSUPPORTED,
                self.obligation_class,
                f"the closed evaluator cannot handle this expression: {exc}",
                {"reason": str(exc)},
            )
        evidence = {
            "left": left.render(),
            "right": right.render(),
            "operator": expr.op,
            "exact": left.exact and right.exact,
            "mode": str(task.mode),
        }
        # A closed proposition has the same verdict in both modes: it is either true —
        # and therefore both universally true and satisfiable — or false, and therefore
        # neither. The distinction only bites once a free name is involved.
        if verdict.as_bool():
            return Judgement(
                ObligationStatus.DISCHARGED,
                self.obligation_class,
                f"evaluated exactly: {left.render()} {expr.op} {right.render()}",
                evidence,
            )
        return Judgement(
            ObligationStatus.FAILED,
            self.obligation_class,
            "the closed expression evaluates false",
            evidence,
            witness=Witness(
                description=f"the two sides are {left.render()} and {right.render()}",
                evaluated=f"{left.render()} {expr.op} {right.render()} is false",
                produced_by=self.name,
            ),
        )


class ClosedArithmeticEqualityChecker(_ClosedComparisonChecker):
    """``2 + 3 = 5``. Exact rational equality only — never a float comparison."""

    name = "closed_arithmetic_equality"
    obligation_class = ObligationClass.CLOSED_ARITHMETIC_EQUALITY
    _ops = ("=", "!=")


class ClosedInequalityChecker(_ClosedComparisonChecker):
    """``9.81 > 9``. Ordering on exactly-represented rationals."""

    name = "closed_inequality"
    obligation_class = ObligationClass.CLOSED_INEQUALITY
    _ops = ("<", "<=", ">", ">=")


# ---------------------------------------------------------------------------
# 3. Simple logical consistency
# ---------------------------------------------------------------------------


class LogicalConsistencyChecker:
    """Closed propositional formulas, decided by evaluation.

    Also the home of the module-level contradiction obligation the engine derives: a
    set of constraints whose feasible region is empty is *inconsistent*, and that is a
    genuine failure even though no single constraint is false on its own.
    """

    name = "logical_consistency"
    version = "hml-obl-1.0.0"
    obligation_class = ObligationClass.LOGICAL_CONSISTENCY
    MAX_MODELS = 4096

    def judge(self, task: ObligationTask) -> Judgement | None:
        if task.context.get("derived") == "feasibility":
            return self._feasibility(task)
        expr = task.proposition
        if not isinstance(expr, (LogicalOp, UnaryOp)) and not (
            isinstance(expr, Literal) and isinstance(expr.value, bool)
        ):
            return None
        if isinstance(expr, UnaryOp) and expr.op != "not":
            return None
        if not task.closed():
            return None
        try:
            verdict = evaluate(expr, task.env)
        except Undecidable as exc:
            return _unsupported(
                self.obligation_class,
                f"the propositional evaluator cannot handle this formula: {exc}",
                reason=str(exc),
            )
        if verdict.as_bool():
            return Judgement(
                ObligationStatus.DISCHARGED,
                self.obligation_class,
                "the closed propositional formula evaluates true",
                {"connective": _shape(expr)},
            )
        return Judgement(
            ObligationStatus.FAILED,
            self.obligation_class,
            "the closed propositional formula evaluates false",
            {"connective": _shape(expr)},
            witness=Witness(
                description="the formula is false under its own closed values",
                evaluated=f"{task.statement} is false",
                produced_by=self.name,
            ),
        )

    def _feasibility(self, task: ObligationTask) -> Judgement:
        """Decide the derived obligation 'this constraint set has a model'.

        Two sound moves, in this order:

        1. **Infeasible by intervals.** When the interval constraints on one variable
           intersect to the empty set, no assignment can satisfy them together. That is
           a proof of unsatisfiability and it names the conflicting bounds.
        2. **Feasible by witness.** A single assignment satisfying every constraint at
           once is a proof of satisfiability, and it is handed back so a reader can
           check it by substitution.

        Finding no witness in the grid proves nothing, and is reported as such.
        """
        dependencies = tuple(str(d) for d in task.context.get("dependencies", ()))
        empties: Mapping[str, Sequence[str]] = task.context.get("empty_variables", {})
        if empties:
            variable, sources = next(iter(sorted(empties.items())))
            return Judgement(
                ObligationStatus.FAILED,
                self.obligation_class,
                f"the constraints on {variable!r} intersect to the empty set",
                {"variable": variable, "sources": list(sources), "definitional": False},
                witness=Witness(
                    description=(
                        f"no value of {variable!r} satisfies all of its constraints "
                        f"simultaneously, so the constraint set has no model"
                    ),
                    evaluated=f"{variable} ∈ {' ∩ '.join(sources)} = {{}}",
                    produced_by=self.name,
                ),
                dependencies=dependencies,
            )

        propositions: Sequence[Expr] = task.context.get("propositions", ())
        if not propositions:
            return _unsupported(
                self.obligation_class,
                "the derived feasibility obligation carries no constraints",
            )
        env = task.env
        free: set[str] = set()
        for prop in propositions:
            free |= free_names(prop, env)
        domains: dict[str, Domain] = {}
        for name in sorted(free):
            domain = env.domain(name)
            if domain is None or not sample_points(domain):
                return _unsupported(
                    self.obligation_class,
                    f"{name!r} has no sampleable domain, so joint satisfiability was "
                    f"not searched",
                    name=name,
                )
            domains[name] = domain
            if domain.type_name == "Bool":
                env = env.with_bool(name)
        extra = constant_points(
            c for prop in propositions for c in _literals(prop)
        )
        tried = 0
        for assignment in assignments(domains, budget=self.MAX_MODELS, extra=extra):
            tried += 1
            try:
                if all(evaluate(p, env, assignment).as_bool() for p in propositions):
                    return Judgement(
                        ObligationStatus.DISCHARGED,
                        self.obligation_class,
                        (
                            f"an assignment satisfying all {len(propositions)} constraint(s) "
                            f"at once was exhibited"
                        ),
                        {
                            "model": {k: str(v) for k, v in assignment.items()},
                            "constraints": len(propositions),
                            "assignments_tried": tried,
                            "definitional": False,
                        },
                        dependencies=dependencies,
                    )
            except Undecidable as exc:
                return _unsupported(
                    self.obligation_class,
                    f"joint satisfiability could not be evaluated: {exc}",
                    reason=str(exc),
                )
        if not free:
            try:
                holds = all(evaluate(p, env).as_bool() for p in propositions)
            except Undecidable as exc:
                return _unsupported(
                    self.obligation_class,
                    f"the closed constraint set could not be evaluated: {exc}",
                )
            if holds:
                return Judgement(
                    ObligationStatus.DISCHARGED,
                    self.obligation_class,
                    "every constraint is closed and true, so the empty model satisfies them",
                    {"constraints": len(propositions), "definitional": False},
                    dependencies=dependencies,
                )
            return Judgement(
                ObligationStatus.FAILED,
                self.obligation_class,
                "a closed constraint is false, so the constraint set has no model",
                {"constraints": len(propositions)},
                witness=Witness(
                    description="the closed constraint set is contradictory",
                    evaluated="at least one closed constraint evaluates false",
                    produced_by=self.name,
                ),
                dependencies=dependencies,
            )
        return _unsupported(
            self.obligation_class,
            (
                f"{tried} assignment(s) were tried and none satisfied every constraint. "
                f"A grid that finds no model does not prove that none exists, so this is "
                f"not a refutation"
            ),
            assignments_tried=tried,
        )


# ---------------------------------------------------------------------------
# 4. Finite-set membership
# ---------------------------------------------------------------------------


class FiniteSetMembershipChecker:
    """Decision by exhaustion over a genuinely finite domain.

    Two shapes qualify:

    * a quantifier whose bound variable ranges over a finite scalar domain
      (``forall b : Bool . ...``);
    * an open proposition all of whose free names have finite domains, which is the
      membership question "is every admissible value in the asserted set?".

    Exhaustion is a proof. Sampling is not, and the two are kept in different checkers
    for exactly that reason.
    """

    name = "finite_set_membership"
    version = "hml-obl-1.0.0"
    obligation_class = ObligationClass.FINITE_SET_MEMBERSHIP
    #: A domain product larger than this is not exhausted; the checker says so instead
    #: of quietly sampling a subset and calling it exhaustive.
    MAX_PRODUCT = 4096

    def judge(self, task: ObligationTask) -> Judgement | None:
        expr = task.proposition
        if expr is None or task.mode is ObligationMode.STRUCTURAL:
            return None
        free = task.free()
        if isinstance(expr, Quantifier) and not free:
            return self._exhaust_quantifier(task, expr)
        if not free:
            return None
        domains = self._finite_domains(task, free)
        if domains is None:
            return None
        total = 1
        for d in domains.values():
            members = d.interval.finite_members()
            total *= len(members) if members is not None else self.MAX_PRODUCT + 1
        if total > self.MAX_PRODUCT:
            return _unsupported(
                self.obligation_class,
                f"the finite domain product is {total}, above the exhaustion bound "
                f"{self.MAX_PRODUCT}; a partial sweep is not an exhaustion",
                product=total,
            )
        return self._exhaust_open(task, domains, total)

    def _finite_domains(
        self, task: ObligationTask, free: set[str]
    ) -> dict[str, Domain] | None:
        out: dict[str, Domain] = {}
        for name in sorted(free):
            domain = task.env.domain(name)
            if domain is None or domain.interval.finite_members() is None:
                return None
            out[name] = domain
        return out or None

    def _exhaust_quantifier(self, task: ObligationTask, expr: Quantifier) -> Judgement:
        try:
            verdict = evaluate(expr, task.env)
        except Undecidable as exc:
            return _unsupported(
                self.obligation_class,
                f"the quantifier could not be exhausted: {exc}",
                reason=str(exc),
            )
        domain = domain_of_type(expr.var_type)
        members = domain.finite_members() if domain else None
        evidence = {
            "variable": expr.var,
            "domain": expr.var_type.render() if expr.var_type else "?",
            "cases": len(members) if members is not None else 0,
        }
        if verdict.as_bool():
            return Judgement(
                ObligationStatus.DISCHARGED,
                self.obligation_class,
                f"exhausted {evidence['cases']} case(s) of {expr.var!r}; all hold",
                evidence,
            )
        return Judgement(
            ObligationStatus.FAILED,
            self.obligation_class,
            "exhaustion found a case in which the body fails",
            evidence,
            witness=Witness(
                description=f"the quantified claim fails for some value of {expr.var!r}",
                evaluated=f"{task.statement} is false over the finite domain of {expr.var}",
                produced_by=self.name,
            ),
        )

    def _exhaust_open(
        self, task: ObligationTask, domains: Mapping[str, Domain], total: int
    ) -> Judgement:
        """Exhaustion decides both modes, because it really is exhaustive.

        For a ``UNIVERSAL`` obligation the answer is "every member holds"; for a
        ``SATISFIABLE`` one it is "some member holds". Only over a finite domain that
        has actually been walked in full may the negative answer be reported as a
        refutation — which is precisely why sampling lives in a different checker.
        """
        expr = task.proposition
        assert expr is not None
        env = task.env
        for name in domains:
            if domains[name].type_name == "Bool":
                env = env.with_bool(name)
        satisfiable = task.mode is ObligationMode.SATISFIABLE
        checked = 0
        first_true: dict[str, str] | None = None
        first_false: dict[str, str] | None = None
        for assignment in assignments(dict(domains), budget=self.MAX_PRODUCT):
            checked += 1
            try:
                holds = evaluate(expr, env, assignment).as_bool()
            except Undecidable as exc:
                return _unsupported(
                    self.obligation_class,
                    f"exhaustion stopped: {exc}",
                    reason=str(exc),
                )
            rendered = {k: str(v) for k, v in assignment.items()}
            if holds and first_true is None:
                first_true = rendered
                if satisfiable:
                    break
            if not holds and first_false is None:
                first_false = rendered
                if not satisfiable:
                    break
        if checked == 0:
            return _unsupported(
                self.obligation_class,
                "the finite domain enumerated no members, so nothing was exhausted",
                cases_checked=0,
            )
        evidence = {"cases_checked": checked, "domain_size": total, "mode": str(task.mode)}
        if satisfiable:
            if first_true is not None:
                return Judgement(
                    ObligationStatus.DISCHARGED,
                    self.obligation_class,
                    "a member of the finite domain satisfies the constraint",
                    {**evidence, "model": first_true},
                )
            return Judgement(
                ObligationStatus.FAILED,
                self.obligation_class,
                "the finite domain was exhausted and no member satisfies the constraint",
                evidence,
                witness=Witness(
                    description="the constraint has no model over its finite domain",
                    evaluated=f"all {checked} member(s) refute {task.statement}",
                    produced_by=self.name,
                ),
            )
        if first_false is not None:
            return Judgement(
                ObligationStatus.FAILED,
                self.obligation_class,
                "a member of the finite domain refutes the obligation",
                evidence,
                witness=Witness(
                    description="this assignment is admissible and refutes the claim",
                    bindings=first_false,
                    evaluated=f"{task.statement} is false at this assignment",
                    produced_by=self.name,
                ),
            )
        return Judgement(
            ObligationStatus.DISCHARGED,
            self.obligation_class,
            f"exhausted all {checked} member(s) of the finite domain; all hold",
            evidence,
        )


# ---------------------------------------------------------------------------
# 5. Literal refinement bounds
# ---------------------------------------------------------------------------

#: The exact wordings the type checker emits for a positivity obligation. Parsed rather
#: than trusted: the bound is re-derived from the declared type and compared, so a
#: change to either side shows up as a mismatch instead of passing silently.
_POSITIVITY_FORMS: tuple[tuple[str, str, str], ...] = (
    ("{name} > 0", ">", "0"),
    ("{name} >= 0", ">=", "0"),
    ("0 <= {name} <= 1", "in", "[0,1]"),
)


class LiteralRefinementBoundChecker:
    """Bounds entailed by a declared refinement type, or by a pinned literal.

    Sound direction only: the obligation is ``DISCHARGED`` when the **whole** interval
    the declaration permits satisfies the bound. When it does not, this checker returns
    ``INCONCLUSIVE`` and leaves refutation to the checkers that can produce a witness.

    Known weakness, stated rather than hidden: a ``parameter_positivity`` obligation is
    generated *by* the declared type, so re-deriving it from that same type is a
    definitional discharge and cannot fail. Every such record carries
    ``evidence["definitional"] = true``, and the H3 task filter refuses to count a task
    whose only discharges are definitional.
    """

    name = "literal_refinement_bound"
    version = "hml-obl-1.0.0"
    obligation_class = ObligationClass.LITERAL_REFINEMENT_BOUND

    def judge(self, task: ObligationTask) -> Judgement | None:
        if task.kind == "parameter_positivity":
            return self._positivity(task)
        if task.mode is not ObligationMode.UNIVERSAL:
            return None  # entailment answers "for all", which is not what is asked
        expr = task.proposition
        if not isinstance(expr, Comparison) or expr.op not in ("<", "<=", ">", ">="):
            return None
        if task.closed():
            return None  # the closed checkers own this
        return self._entailment(task, expr)

    # -- standing refinement obligations ---------------------------------
    def _positivity(self, task: ObligationTask) -> Judgement:
        name, op, bound = self._parse_positivity(task.statement)
        if name is None:
            return _unsupported(
                self.obligation_class,
                f"the positivity obligation {task.statement!r} is not one of the "
                f"wordings this checker parses",
                statement=task.statement,
            )
        domain = task.env.domain(name)
        if domain is None:
            return _unsupported(
                self.obligation_class,
                f"{name!r} has no modelled domain, so its refinement cannot be checked",
                name=name,
            )
        interval = domain.interval
        holds = {
            ">": interval.entirely_above(Fraction(0), strict=True),
            ">=": interval.entirely_above(Fraction(0), strict=False),
            "in": (
                interval.entirely_above(Fraction(0), strict=False)
                and interval.entirely_below(Fraction(1), strict=False)
            ),
        }[op]
        evidence = {
            "name": name,
            "declared_type": domain.type_name,
            "domain": interval.render(),
            "bound": bound,
            "definitional": True,
            "pinned": None if domain.pinned is None else str(domain.pinned),
        }
        if not holds:
            return Judgement(
                ObligationStatus.INCONCLUSIVE,
                self.obligation_class,
                (
                    f"the declared domain of {name!r} is {interval.render()}, which does "
                    f"not entail {bound}"
                ),
                evidence,
            )
        return Judgement(
            ObligationStatus.DISCHARGED,
            self.obligation_class,
            (
                f"{name} : {domain.type_name} confines it to {interval.render()}, which "
                f"is contained in {bound}"
            ),
            evidence,
        )

    @staticmethod
    def _parse_positivity(statement: str) -> tuple[str | None, str, str]:
        text = " ".join(statement.split())
        for template, op, bound in _POSITIVITY_FORMS:
            prefix, _, suffix = template.partition("{name}")
            if text.startswith(prefix) and text.endswith(suffix):
                name = text[len(prefix) : len(text) - len(suffix) if suffix else None]
                name = name.strip()
                if name and all(c.isalnum() or c == "_" for c in name):
                    return name, op, bound
        return None, "", ""

    # -- interval entailment for an open inequality ----------------------
    def _entailment(self, task: ObligationTask, expr: Comparison) -> Judgement | None:
        try:
            right = evaluate(expr.right, task.env)
        except Undecidable:
            return None
        constant = right.number
        if not isinstance(constant, Fraction):
            return None
        interval = interval_of(expr.left, task.env)
        entailed = {
            ">": interval.entirely_above(constant, strict=True),
            ">=": interval.entirely_above(constant, strict=False),
            "<": interval.entirely_below(constant, strict=True),
            "<=": interval.entirely_below(constant, strict=False),
        }[expr.op]
        evidence = {
            "interval": interval.render(),
            "operator": expr.op,
            "bound": right.render(),
            "definitional": False,
            "domains": sorted(
                d.render() for n, d in task.env.domains.items() if n in task.free()
            ),
        }
        if entailed:
            return Judgement(
                ObligationStatus.DISCHARGED,
                self.obligation_class,
                (
                    f"every value the declarations permit lies in {interval.render()}, "
                    f"which satisfies {expr.op} {right.render()}"
                ),
                evidence,
            )
        return None  # not entailed: leave the verdict to a checker that can refute


# ---------------------------------------------------------------------------
# 6. Dimension compatibility
# ---------------------------------------------------------------------------


def _numeric(tok: str) -> bool:
    try:
        Fraction(tok)
    except (ValueError, ZeroDivisionError):
        return False
    return True


def parse_dimension_text(text: str) -> Dimension | None:
    """Parse ``Length^2 * Mass / Time^2`` into a :class:`Dimension`.

    A deliberately independent re-implementation of the grammar the parser accepts, so
    that a dimensional claim is compared against a second reading of the source text
    rather than against the type checker's own answer echoed back.
    """
    tokens = _dim_tokens(text)
    if tokens is None:
        return None
    pos = 0


    def _exponent() -> Fraction | None:
        """Read an exponent, which may be a rational written `1/2`.

        `/` is also the division operator, so `n / m` is an exponent only when BOTH
        sides are numeric -- `Length^1/2` is a half power, while `Mass^2 / Time` is a
        squared mass divided by time. The language parser draws the same distinction
        (`/`-before-NUMBER is a fractional exponent, `/`-before-identifier is division),
        and this re-reader must agree with it or it would reject valid programs.
        """
        nonlocal pos
        if pos >= len(tokens):
            return None
        raw = tokens[pos]
        pos += 1
        if (
            pos + 1 < len(tokens)
            and tokens[pos] == "/"
            and _numeric(raw)
            and _numeric(tokens[pos + 1])
        ):
            denom = tokens[pos + 1]
            pos += 2
            raw = f"{raw}/{denom}"
        try:
            return Fraction(raw)
        except (ValueError, ZeroDivisionError):
            return None

    def group() -> Dimension | None:
        """A parenthesised sub-expression, or a single term.

        Parentheses used to be **deleted** by the tokeniser, so `Mass / (Length * Time^2)`
        was re-read as `Mass / Length * Time^2` and the second divisor's exponent kept its
        sign. Since the compiler renders its own canonical form *with* parentheses, every
        dimension needing two divisions was re-read wrongly whatever the author wrote --
        pressure, density and the rest could not be asserted at all. See D-028.
        """
        nonlocal pos
        if pos < len(tokens) and tokens[pos] == "(":
            pos += 1
            inner = expression()
            if inner is None or pos >= len(tokens) or tokens[pos] != ")":
                return None
            pos += 1
            return _maybe_power(inner)
        return term()

    def _maybe_power(base: Dimension) -> Dimension | None:
        """`(...)^n` must bind to the whole group, not to its last factor."""
        nonlocal pos
        if pos < len(tokens) and tokens[pos] == "^":
            pos += 1
            if pos >= len(tokens):
                return None
            exponent = _exponent()
            return None if exponent is None else base.power(exponent)
        return base

    def expression() -> Dimension | None:
        """Left-associative `*` and `/` over groups. `a / b / c` is `(a / b) / c`."""
        nonlocal pos
        acc = group()
        if acc is None:
            return None
        while pos < len(tokens) and tokens[pos] in ("*", "/"):
            op = tokens[pos]
            pos += 1
            nxt = group()
            if nxt is None:
                return None
            acc = acc * nxt if op == "*" else acc / nxt
        return acc

    def term() -> Dimension | None:
        nonlocal pos
        if pos >= len(tokens):
            return None
        tok = tokens[pos]
        pos += 1
        if tok == "1" or tok == "Dimensionless":
            base = Dimension()
        elif tok.isidentifier():
            try:
                base = Dimension.of(**{tok: 1})
            except ValueError:
                from ...types import is_dimension_variable

                if not is_dimension_variable(tok):
                    return None
                base = Dimension.variable(tok)
        else:
            return None
        if pos < len(tokens) and tokens[pos] == "^":
            pos += 1
            if pos >= len(tokens):
                return None
            exponent = _exponent()
            if exponent is None:
                return None
            base = base.power(exponent)
        return base

    acc = expression()
    return acc if acc is not None and pos == len(tokens) else None


def _dim_tokens(text: str) -> list[str] | None:
    out: list[str] = []
    i = 0
    body = text
    while i < len(body):
        ch = body[i]
        if ch.isspace():
            i += 1
            continue
        if ch in "*/^()":
            out.append(ch)
            i += 1
            continue
        j = i
        while j < len(body) and (body[j].isalnum() or body[j] in "_-."):
            j += 1
        if j == i:
            return None
        out.append(body[i:j])
        i = j
    return out or None


def dimension_of_expr(expr: Expr, env: Environment, *, depth: int = 0) -> Dimension | None:
    """Recompute an expression's dimension from declared types, independently.

    This does not read ``expr.type_``. Reading it would be reading the type checker's
    conclusion and calling the echo a verification.
    """
    if depth > 32:
        return None
    if isinstance(expr, Literal):
        return Dimension()
    if isinstance(expr, Ref):
        declared = env.declared_types.get(expr.name)
        if declared is not None:
            return dimension_of(declared)
        definition = env.definitions.get(expr.name)
        if definition is not None:
            if definition.declared_type is not None:
                return dimension_of(definition.declared_type)
            return dimension_of_expr(definition.body, env, depth=depth + 1)
        return None
    if isinstance(expr, UnaryOp) and expr.op == "-":
        return dimension_of_expr(expr.operand, env, depth=depth + 1)
    if isinstance(expr, BinOp):
        left = dimension_of_expr(expr.left, env, depth=depth + 1)
        if expr.op in ("+", "-"):
            right = dimension_of_expr(expr.right, env, depth=depth + 1)
            if left is None or right is None or left != right:
                return None
            return left
        if expr.op == "*":
            right = dimension_of_expr(expr.right, env, depth=depth + 1)
            return None if left is None or right is None else left * right
        if expr.op == "/":
            right = dimension_of_expr(expr.right, env, depth=depth + 1)
            return None if left is None or right is None else left / right
        if expr.op in ("^", "**") and isinstance(expr.right, Literal):
            if left is None:
                return None
            try:
                return left.power(Fraction(expr.right.value))
            except (TypeError, ValueError):
                return None
    if isinstance(expr, Call) and expr.callee == "abs" and len(expr.args) == 1:
        return dimension_of_expr(expr.args[0], env, depth=depth + 1)
    return None


class DimensionCompatibilityChecker:
    """``check dimension E = Length^2 * Mass / Time^2``.

    The dimension of the subject is recomputed from the declared types of its leaves
    and compared structurally against the asserted dimension re-parsed from the source
    text. Neither side is the type checker's stored answer.

    A ``check dimension`` with no asserted dimension asserts nothing beyond
    well-dimensionedness. That case is reported ``DISCHARGED`` with
    ``evidence["asserts_a_dimension"] = false``, so it can never be mistaken for a
    verified equality.
    """

    name = "dimension_compatibility"
    version = "hml-obl-1.0.0"
    obligation_class = ObligationClass.DIMENSION_COMPATIBILITY

    def judge(self, task: ObligationTask) -> Judgement | None:
        if task.kind != "dimension":
            return None
        subject = task.proposition
        if subject is None:
            return _unsupported(
                self.obligation_class,
                "the dimension obligation carries no subject expression",
            )
        computed = dimension_of_expr(subject, task.env)
        if computed is None:
            return _unsupported(
                self.obligation_class,
                "the subject's dimension could not be recomputed from declared types "
                "alone; this checker refuses to fall back on the type checker's answer",
            )
        asserted_text = task.context.get("asserted_dimension")
        if not asserted_text:
            return Judgement(
                ObligationStatus.DISCHARGED,
                self.obligation_class,
                (
                    f"the subject is well dimensioned at {computed.render()}; the "
                    f"program asserted no dimension, so nothing stronger is claimed"
                ),
                {
                    "computed": computed.render(),
                    "asserts_a_dimension": False,
                    "definitional": True,
                },
            )
        asserted = parse_dimension_text(str(asserted_text))
        if asserted is None:
            return _unsupported(
                self.obligation_class,
                f"the asserted dimension {asserted_text!r} did not re-parse",
                asserted=str(asserted_text),
            )
        evidence = {
            "computed": computed.render(),
            "asserted": asserted.render(),
            "asserts_a_dimension": True,
            "definitional": False,
        }
        if computed == asserted:
            return Judgement(
                ObligationStatus.DISCHARGED,
                self.obligation_class,
                f"recomputed dimension {computed.render()} equals the asserted dimension",
                evidence,
            )
        return Judgement(
            ObligationStatus.FAILED,
            self.obligation_class,
            "the recomputed dimension differs from the asserted dimension",
            evidence,
            witness=Witness(
                description="the subject's dimension is not the one asserted",
                evaluated=f"computed {computed.render()} != asserted {asserted.render()}",
                produced_by=self.name,
            ),
        )


# ---------------------------------------------------------------------------
# 7. Declared signature conformance
# ---------------------------------------------------------------------------


class DeclaredSignatureChecker:
    """Arity and argument types at every call site, re-derived from the declaration.

    The type checker already enforces this. That is the point: an independent second
    implementation is what makes a regression in the first one visible. The argument's
    synthesised type is read from the AST — a partial dependency, recorded as
    ``evidence["reads_synthesised_argument_type"] = true`` rather than glossed over.
    """

    name = "declared_signature_conformance"
    version = "hml-obl-1.0.0"
    obligation_class = ObligationClass.DECLARED_SIGNATURE_CONFORMANCE

    def judge(self, task: ObligationTask) -> Judgement | None:
        if task.context.get("derived") != "signature":
            return None
        callee = str(task.context["callee"])
        params: Sequence[tuple[str, Type | None]] = task.context["params"]
        args: Sequence[Expr] = task.context["args"]
        evidence: dict[str, Any] = {
            "callee": callee,
            "declared_arity": len(params),
            "supplied_arity": len(args),
            "reads_synthesised_argument_type": True,
        }
        if len(params) != len(args):
            return Judgement(
                ObligationStatus.FAILED,
                self.obligation_class,
                f"{callee} is declared with {len(params)} parameter(s) but called with "
                f"{len(args)}",
                evidence,
                witness=Witness(
                    description=f"arity mismatch at a call to {callee!r}",
                    evaluated=f"declared {len(params)}, supplied {len(args)}",
                    produced_by=self.name,
                ),
            )
        mismatches: list[str] = []
        for (pname, ptype), arg in zip(params, args, strict=True):
            if ptype is None:
                continue
            actual = arg.type_
            if actual is None:
                mismatches.append(f"{pname}: the argument has no synthesised type")
                continue
            if is_subtype(actual, ptype):
                continue
            if isinstance(arg, Literal) and literal_inhabits(arg.value, ptype):
                continue
            mismatches.append(
                f"{pname}: declared {ptype.render()}, supplied {actual.render()}"
            )
        evidence["mismatches"] = mismatches
        if mismatches:
            return Judgement(
                ObligationStatus.FAILED,
                self.obligation_class,
                f"{len(mismatches)} argument(s) do not inhabit their declared parameter type",
                evidence,
                witness=Witness(
                    description=f"argument type mismatch at a call to {callee!r}",
                    evaluated="; ".join(mismatches),
                    produced_by=self.name,
                ),
            )
        return Judgement(
            ObligationStatus.DISCHARGED,
            self.obligation_class,
            f"the call to {callee!r} matches its declared arity and parameter types",
            evidence,
        )


# ---------------------------------------------------------------------------
# 8. Supported symbolic identities
# ---------------------------------------------------------------------------


def partiality_risk(expr: Expr, env: Environment, *, depth: int = 0) -> str | None:
    """The reason a generic simplification would not establish this everywhere.

    This guard exists because of a measured unsoundness, not a hypothetical one.
    ``sympy.simplify(x/x - 1)`` is ``0``, so without this check the engine discharged
    ``prove x / x = 1`` for a free real ``x`` — a claim that is **false at zero**. SymPy
    simplifies *generically*: it cancels on the assumption that it is not standing on the
    measure-zero set where the operation is undefined. That is the right behaviour for a
    CAS and the wrong basis for a proof.

    So every partial operation must be total over the declared domains before a symbolic
    result may be believed:

    * ``a / b`` needs ``b`` provably non-zero;
    * ``a ^ n`` with ``n`` negative or zero needs ``a`` provably non-zero, and with ``n``
      fractional needs ``a`` provably non-negative;
    * ``log(a)`` needs ``a`` provably positive, ``sqrt(a)`` needs ``a`` provably
      non-negative;
    * ``tan`` is refused outright — its poles are not expressible as an interval
      condition here.

    ``None`` means no risk was found. Any string means the identity is reported
    ``UNSUPPORTED``, which is the honest answer: the tool cannot establish it, and
    saying so is different from saying it is false.
    """
    if depth > 32:
        return "the expression is too deeply nested to check for partial operations"
    if isinstance(expr, BinOp):
        if expr.op == "/":
            interval = interval_of(expr.right, env)
            if not (
                interval.entirely_above(Fraction(0), strict=True)
                or interval.entirely_below(Fraction(0), strict=True)
            ):
                return (
                    f"a divisor ranges over {interval.render()}, which is not provably "
                    f"non-zero; a generic cancellation does not establish the identity "
                    f"where the divisor vanishes"
                )
        if expr.op in ("^", "**"):
            exponent = interval_of(expr.right, env)
            base = interval_of(expr.left, env)
            if exponent.is_point() and exponent.lo is not None:
                n = exponent.lo
                if n.denominator != 1 and not base.entirely_above(Fraction(0), strict=False):
                    return (
                        f"a fractional power is taken of a base ranging over "
                        f"{base.render()}, which is not provably non-negative"
                    )
                if n <= 0 and not (
                    base.entirely_above(Fraction(0), strict=True)
                    or base.entirely_below(Fraction(0), strict=True)
                ):
                    return (
                        f"a non-positive power is taken of a base ranging over "
                        f"{base.render()}, which is not provably non-zero"
                    )
            else:
                return "a symbolic exponent cannot be checked for totality"
        for child in (expr.left, expr.right):
            risk = partiality_risk(child, env, depth=depth + 1)
            if risk is not None:
                return risk
        return None
    if isinstance(expr, Call):
        if expr.callee == "tan":
            return "tan has poles that this checker cannot exclude by interval reasoning"
        if expr.callee == "log" and len(expr.args) == 1:
            interval = interval_of(expr.args[0], env)
            if not interval.entirely_above(Fraction(0), strict=True):
                return (
                    f"log is applied to an argument ranging over {interval.render()}, "
                    f"which is not provably positive"
                )
        if expr.callee == "sqrt" and len(expr.args) == 1:
            interval = interval_of(expr.args[0], env)
            if not interval.entirely_above(Fraction(0), strict=False):
                return (
                    f"sqrt is applied to an argument ranging over {interval.render()}, "
                    f"which is not provably non-negative"
                )
        for arg in expr.args:
            risk = partiality_risk(arg, env, depth=depth + 1)
            if risk is not None:
                return risk
        return None
    if isinstance(expr, UnaryOp):
        return partiality_risk(expr.operand, env, depth=depth + 1)
    if isinstance(expr, Ref):
        # A definition must be followed, because `_to_sympy` inlines `env.definitions`
        # before SymPy sees the expression. Without this case the guard inspected a
        # *different* expression from the one being decided, so one line of idiomatic
        # HML defeated it:
        #
        #     prove x / x = 1        , x : Real   ->  UNSUPPORTED   (guard sees the `/`)
        #     def q := x / x ; prove q = 1        ->  VERIFIED      (guard sees only `q`)
        #
        # The second is false at zero, and the federation inherited the unsound verdict.
        # Found by the M1.5 falsifier (F-2) and reproduced by the Lead. Mirrors the
        # definition-following already done by `_to_sympy` and `dimension_of_expr`, so
        # the guard and the decision procedure now read the same expression.
        definition = env.definitions.get(expr.name)
        if definition is not None:
            return partiality_risk(definition.body, env, depth=depth + 1)
        return None
    if isinstance(expr, (Comparison, LogicalOp)):
        for child in (expr.left, expr.right):
            risk = partiality_risk(child, env, depth=depth + 1)
            if risk is not None:
                return risk
    return None


_SYMPY_BUILTINS = {
    "exp": "exp",
    "log": "log",
    "sqrt": "sqrt",
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "abs": "Abs",
}

#: Assumptions carried across from the declared refinement type. These are facts the
#: program already committed to, not extra hypotheses invented here.
_SYMPY_ASSUMPTIONS: dict[str, dict[str, bool]] = {
    "Real": {"real": True},
    "Rational": {"rational": True},
    "Integer": {"integer": True},
    "Natural": {"integer": True, "nonnegative": True},
    "PositiveNatural": {"integer": True, "positive": True},
    "NonNegativeReal": {"real": True, "nonnegative": True},
    "PositiveReal": {"real": True, "positive": True},
    "Probability": {"real": True, "nonnegative": True},
    "PValue": {"real": True, "nonnegative": True},
    "PosteriorProbability": {"real": True, "nonnegative": True},
}


class SymbolicIdentityChecker:
    """SymPy-decided identities and sign facts over the supported operator set.

    Restricted on purpose:

    * only ``= != < <= > >=`` at the top;
    * only ``+ - * / ^`` and the seven whitelisted functions beneath;
    * only free names whose declared type maps to a SymPy assumption;
    * a node budget, so no obligation can make the verifier hang.

    ``simplify(l - r) == 0`` is a proof of equality. Its failure is **not** a proof of
    inequality, so a non-zero simplification returns ``INCONCLUSIVE`` and refutation is
    left to the sampler.
    """

    name = "symbolic_identity"
    version = "sympy-1.14.0"
    obligation_class = ObligationClass.SYMBOLIC_IDENTITY
    MAX_NODES = 96

    def judge(self, task: ObligationTask) -> Judgement | None:
        if task.mode is not ObligationMode.UNIVERSAL:
            return None  # an identity is a universal claim; satisfiability is not
        expr = task.proposition
        if not isinstance(expr, Comparison) or expr.op not in ("=", "<", "<=", ">", ">="):
            return None
        if task.closed():
            return None
        try:
            import sympy
        except ImportError:  # pragma: no cover - sympy is a measured dependency
            return _unsupported(
                self.obligation_class,
                "sympy is not importable, so no symbolic identity can be decided",
                missing_capability="sympy",
            )
        if _node_count(expr) > self.MAX_NODES:
            return _unsupported(
                self.obligation_class,
                f"the expression exceeds the {self.MAX_NODES}-node budget for symbolic "
                f"simplification",
            )
        risk = partiality_risk(expr, task.env)
        if risk is not None:
            return _unsupported(
                self.obligation_class,
                f"a generic simplification would not establish this everywhere: {risk}",
                partiality_risk=risk,
            )
        symbols: dict[str, Any] = {}
        try:
            left = _to_sympy(expr.left, task.env, symbols, sympy)
            right = _to_sympy(expr.right, task.env, symbols, sympy)
        except Undecidable as exc:
            return _unsupported(
                self.obligation_class,
                f"the expression is outside the symbolic subset: {exc}",
                reason=str(exc),
            )
        difference = sympy.simplify(left - right)
        evidence = {
            "difference": str(difference),
            "assumptions": {k: str(v.assumptions0) for k, v in sorted(symbols.items())},
            "definitional": False,
        }
        if expr.op == "=":
            if difference == 0:
                return Judgement(
                    ObligationStatus.DISCHARGED,
                    self.obligation_class,
                    "sympy.simplify(left - right) is identically zero",
                    evidence,
                )
            return Judgement(
                ObligationStatus.INCONCLUSIVE,
                self.obligation_class,
                (
                    f"simplification left {difference}; a non-zero simplification is not "
                    f"a disproof, so no verdict is claimed here"
                ),
                evidence,
            )
        proven = {
            ">": difference.is_positive,
            ">=": difference.is_nonnegative,
            "<": difference.is_negative,
            "<=": difference.is_nonpositive,
        }[expr.op]
        if proven is True:
            return Judgement(
                ObligationStatus.DISCHARGED,
                self.obligation_class,
                f"sympy proves left - right is {expr.op} 0 under the declared assumptions",
                evidence,
            )
        return Judgement(
            ObligationStatus.INCONCLUSIVE,
            self.obligation_class,
            (
                f"sympy could not settle the sign of {difference} under the declared "
                f"assumptions"
            ),
            evidence,
        )


def _node_count(expr: object, depth: int = 0) -> int:
    if depth > 64:
        return 10**6
    total = 1
    for attr in ("left", "right", "operand", "body", "base"):
        child = getattr(expr, attr, None)
        if isinstance(child, Expr):
            total += _node_count(child, depth + 1)
    for arg in getattr(expr, "args", ()) or ():
        if isinstance(arg, Expr):
            total += _node_count(arg, depth + 1)
    return total


def _to_sympy(expr: Expr, env: Environment, symbols: dict[str, Any], sympy: Any) -> Any:
    if isinstance(expr, Literal):
        if isinstance(expr.value, bool):
            raise Undecidable("a truth literal has no symbolic numeric meaning here")
        return sympy.Rational(Fraction(expr.value))
    if isinstance(expr, Ref):
        domain = env.domain(expr.name)
        if domain is not None and domain.pinned is not None:
            return sympy.Rational(domain.pinned)
        definition = env.definitions.get(expr.name)
        if definition is not None:
            return _to_sympy(definition.body, env, symbols, sympy)
        if domain is None:
            raise Undecidable(f"{expr.name!r} has no modelled domain")
        assumptions = _SYMPY_ASSUMPTIONS.get(domain.type_name)
        if assumptions is None:
            raise Undecidable(
                f"{expr.name!r} has type {domain.type_name}, which carries no symbolic "
                f"assumption"
            )
        if expr.name not in symbols:
            symbols[expr.name] = sympy.Symbol(expr.name, **assumptions)
        return symbols[expr.name]
    if isinstance(expr, UnaryOp) and expr.op == "-":
        return -_to_sympy(expr.operand, env, symbols, sympy)
    if isinstance(expr, BinOp):
        left = _to_sympy(expr.left, env, symbols, sympy)
        right = _to_sympy(expr.right, env, symbols, sympy)
        table = {
            "+": lambda: left + right,
            "-": lambda: left - right,
            "*": lambda: left * right,
            "/": lambda: left / right,
            "^": lambda: left**right,
            "**": lambda: left**right,
        }
        if expr.op not in table:
            raise Undecidable(f"operator {expr.op!r} is outside the symbolic subset")
        return table[expr.op]()
    if isinstance(expr, Call):
        name = _SYMPY_BUILTINS.get(expr.callee)
        definition = env.functions.get(expr.callee)
        if definition is not None and len(definition.params) == len(expr.args):
            substituted: dict[str, Any] = dict(symbols)
            inner = _to_sympy(definition.body, env, substituted, sympy)
            mapping = {
                substituted[pname]: _to_sympy(arg, env, symbols, sympy)
                for (pname, _), arg in zip(definition.params, expr.args, strict=True)
                if pname in substituted
            }
            return inner.subs(mapping)
        if name is None or len(expr.args) != 1:
            raise Undecidable(f"call to {expr.callee!r} is outside the symbolic subset")
        return getattr(sympy, name)(_to_sympy(expr.args[0], env, symbols, sympy))
    raise Undecidable(f"{type(expr).__name__} is outside the symbolic subset")


# ---------------------------------------------------------------------------
# 9. Numerical counterexample search
# ---------------------------------------------------------------------------


class NumericalCounterexampleChecker:
    """Refutation only. This checker can say ``FAILED``; it can never say ``DISCHARGED``.

    A concrete assignment drawn from the declared domains, at which the proposition
    evaluates false, is a genuine disproof and is reported as one. Finding no such
    assignment across a fixed grid is not evidence of truth and is reported
    ``UNSUPPORTED`` with the size of the search, so the gap is visible rather than
    absorbed.
    """

    name = "numerical_counterexample"
    version = "hml-obl-1.0.0"
    obligation_class = ObligationClass.NUMERICAL_COUNTEREXAMPLE
    BUDGET = 4096

    def judge(self, task: ObligationTask) -> Judgement | None:
        if task.mode is not ObligationMode.UNIVERSAL:
            # A counterexample refutes "for all". It says nothing about "there exists",
            # and offering it there would turn every ordinary `require` into a failure.
            return None
        expr = task.proposition
        if expr is None:
            return None
        free = task.free()
        if not free:
            return None
        domains: dict[str, Domain] = {}
        for name in sorted(free):
            domain = task.env.domain(name)
            if domain is None or not sample_points(domain):
                return _unsupported(
                    self.obligation_class,
                    f"{name!r} has no sampleable domain, so no counterexample search "
                    f"was attempted",
                    name=name,
                )
            domains[name] = domain
        env = task.env
        for name, domain in domains.items():
            if domain.type_name == "Bool":
                env = env.with_bool(name)
        tried = 0
        undecidable: str | None = None
        extra = constant_points(_literals(expr))
        for assignment in assignments(domains, budget=self.BUDGET, extra=extra):
            tried += 1
            try:
                verdict = evaluate(expr, env, assignment)
            except Undecidable as exc:
                undecidable = str(exc)
                continue
            if not verdict.as_bool():
                return Judgement(
                    ObligationStatus.FAILED,
                    self.obligation_class,
                    "a value drawn from the declared domains refutes the obligation",
                    {"assignments_tried": tried, "grid": "deterministic sample grid"},
                    witness=Witness(
                        description=(
                            "this assignment satisfies every declared type constraint and "
                            "makes the obligation false"
                        ),
                        bindings={k: str(v) for k, v in assignment.items()},
                        evaluated=f"{task.statement} is false at this assignment",
                        produced_by=self.name,
                    ),
                )
        if tried == 0:
            return _unsupported(
                self.obligation_class,
                (
                    f"the sample grid for {sorted(domains)} exceeded the {self.BUDGET}-"
                    f"assignment budget or was empty; no search was performed"
                ),
                assignments_tried=0,
            )
        return _unsupported(
            self.obligation_class,
            (
                f"{tried} assignment(s) were checked and none refuted the obligation. "
                f"Sampling cannot establish a universal claim, so this is not a discharge"
                + (f" (last undecidable point: {undecidable})" if undecidable else "")
            ),
            assignments_tried=tried,
        )


class SatisfiabilityChecker:
    """Model search for ``SATISFIABLE`` obligations. The mirror of the sampler.

    An HML ``require`` constrains the solution; it does not claim to hold everywhere.
    Its obligation is therefore *this constraint has a model*, and a single assignment
    drawn from the declared domains that satisfies it **is** a proof of that. The
    witness is recorded so a reader can re-substitute it.

    Failure to find a model in a finite grid is not a proof that none exists, so the
    negative answer is ``UNSUPPORTED`` and never ``FAILED``. Refutation of a constraint
    set comes from the interval-infeasibility argument in
    :class:`LogicalConsistencyChecker`, or from exhausting a genuinely finite domain.
    """

    name = "satisfiability_witness"
    version = "hml-obl-1.0.0"
    obligation_class = ObligationClass.LOGICAL_CONSISTENCY
    BUDGET = 4096

    def judge(self, task: ObligationTask) -> Judgement | None:
        if task.mode is not ObligationMode.SATISFIABLE:
            return None
        expr = task.proposition
        if expr is None:
            return None
        free = task.free()
        if not free:
            return None  # closed constraints belong to the closed checkers
        excluded = self._excluded_by_declaration(task, expr)
        if excluded is not None:
            return excluded
        domains: dict[str, Domain] = {}
        env = task.env
        for name in sorted(free):
            domain = env.domain(name)
            if domain is None or not sample_points(domain):
                return _unsupported(
                    self.obligation_class,
                    f"{name!r} has no sampleable domain, so no model was searched for",
                    name=name,
                )
            domains[name] = domain
            if domain.type_name == "Bool":
                env = env.with_bool(name)
        tried = 0
        extra = constant_points(_literals(expr))
        for assignment in assignments(domains, budget=self.BUDGET, extra=extra):
            tried += 1
            try:
                holds = evaluate(expr, env, assignment).as_bool()
            except Undecidable as exc:
                return _unsupported(
                    self.obligation_class,
                    f"the constraint could not be evaluated at a sample point: {exc}",
                    reason=str(exc),
                )
            if holds:
                return Judgement(
                    ObligationStatus.DISCHARGED,
                    self.obligation_class,
                    "a model satisfying the constraint was exhibited",
                    {
                        "model": {k: str(v) for k, v in assignment.items()},
                        "assignments_tried": tried,
                        "definitional": False,
                        "mode": str(task.mode),
                    },
                )
        return _unsupported(
            self.obligation_class,
            (
                f"{tried} assignment(s) were tried and none satisfied the constraint. "
                f"A grid that finds no model does not prove that none exists"
            ),
            assignments_tried=tried,
        )

    def _excluded_by_declaration(
        self, task: ObligationTask, expr: Expr
    ) -> Judgement | None:
        """Refute a constraint the declarations already rule out.

        ``param theta : Probability`` followed by ``require theta > 1`` has no model,
        and saying so needs no search: the declared domain over-approximates every
        value ``theta`` can take, and it lies entirely at or below 1. Because the
        interval is an over-approximation, an *empty* intersection with the constraint
        is a proof of unsatisfiability — the one direction that reasoning supports.
        """
        if not isinstance(expr, Comparison):
            return None
        try:
            right = evaluate(expr.right, task.env)
        except Undecidable:
            return None
        constant = right.number
        if not isinstance(constant, Fraction):
            return None
        interval = interval_of(expr.left, task.env)
        impossible = {
            ">": interval.entirely_below(constant, strict=False),
            ">=": interval.entirely_below(constant, strict=True),
            "<": interval.entirely_above(constant, strict=False),
            "<=": interval.entirely_above(constant, strict=True),
            "=": not interval.contains(constant),
        }.get(expr.op, False)
        if not impossible:
            return None
        return Judgement(
            ObligationStatus.FAILED,
            self.obligation_class,
            (
                f"the declarations confine the left side to {interval.render()}, which "
                f"cannot satisfy {expr.op} {right.render()}"
            ),
            {
                "interval": interval.render(),
                "operator": expr.op,
                "bound": right.render(),
                "definitional": False,
            },
            witness=Witness(
                description=(
                    "the declared types already exclude every value the constraint would "
                    "need, so the constraint has no model"
                ),
                evaluated=(
                    f"admissible values ⊆ {interval.render()}; required "
                    f"{expr.op} {right.render()}; intersection empty"
                ),
                produced_by=self.name,
            ),
        )


#: The pipeline, strongest-evidence-first.
DEFAULT_CHECKERS: tuple[Checker, ...] = (
    DimensionCompatibilityChecker(),
    DeclaredSignatureChecker(),
    ClosedArithmeticEqualityChecker(),
    ClosedInequalityChecker(),
    LogicalConsistencyChecker(),
    FiniteSetMembershipChecker(),
    LiteralRefinementBoundChecker(),
    SymbolicIdentityChecker(),
    SatisfiabilityChecker(),
    NumericalCounterexampleChecker(),
)
