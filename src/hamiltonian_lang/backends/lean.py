"""Lean 4 statement-skeleton generation.

**No proof search of any kind.** ``docs/design/V0_DESIGN_FREEZE.md`` §8 says Lean
output is statement skeletons with ``sorry``, and this backend does exactly that: every
proof obligation becomes ``theorem <name> : <statement> := by sorry``. No tactic other
than ``sorry`` is ever emitted, no lemma is searched for, and no claim is made that any
statement here is true.

The refinement-type encoding, and why
-------------------------------------
Lean offers (at least) two ways to carry ``sigma : PositiveReal``:

1. a subtype, ``sigma : {x : ℝ // 0 < x}``;
2. a plain ``sigma : ℝ`` together with a hypothesis ``h_sigma_pos : 0 < sigma``.

**This backend uses (2).** Reasons, in order of weight:

* Every arithmetic expression in HML is written over the *carrier*, not over a
  subtype. Under (1) each use site needs ``sigma.val`` or a coercion, so a
  three-symbol HML expression becomes a noisy Lean expression whose shape no longer
  matches the source. The point of the skeleton is that a human can read the
  statement and recognise the HML it came from.
* Mathlib's own lemma statements overwhelmingly take the hypothesis form
  (``(hx : 0 < x)``), so a skeleton written this way can be discharged against
  Mathlib without first being un-subtyped.
* HML's scalar order is a *poset* (``Probability`` and ``PositiveReal`` are
  incomparable). Subtypes would force a coercion lattice that does not exist; separate
  hypotheses compose freely and do not.

The cost of (2) is real and is reported: a hypothesis is not part of the type, so
nothing stops a later Lean edit from applying a lemma to ``sigma`` without the
positivity hypothesis in scope. That is recorded as a *weakening* on every refined
declaration.

Quantifiers
-----------
``forall``/``exists``/``exists_unique`` map to ``∀``/``∃``/``∃!`` and **nesting order
is preserved structurally** — the emitter recurses on ``Quantifier.body`` and never
reorders. ``forall x, exists y, y > x`` and ``exists y, forall x, y > x`` therefore
produce different Lean text, which is asserted in ``tests/backends/test_lean.py``.

What has no Lean encoding here
------------------------------
* **Probability laws.** ``law``/``prior``/``likelihood`` need Mathlib's measure theory
  (``MeasureTheory.Measure``, ``ProbabilityTheory.pdf``, a measurable space instance for
  the codomain and a proof that the density integrates to one). None of that is
  derivable from an HML family name plus role labels. Reported as **dropped**; nothing
  is invented. The same applies to ``infer``.
* **Dimensions.** ``check dimension`` has no Lean encoding without a units library and
  a chosen unit per base dimension; v0 does not reconcile units (§8). Dropped.
* **Objectives and solves.** ``IsMinOn f s a`` could state a minimum, but only relative
  to a set ``s`` that HML does not give; fabricating one would be a different theorem.
  Dropped.

No Lean toolchain is invoked. Nothing here has been elaborated by ``lake``/``lean``;
the structural checks in ``tests/backends/test_lean.py`` are the only verification.
"""

from __future__ import annotations

from ..ast.nodes import (
    AssumeStmt,
    BinOp,
    Call,
    CheckStmt,
    Comparison,
    ConceptDecl,
    ConceptMember,
    Declaration,
    DefineStmt,
    DistExpr,
    Expr,
    Index,
    InferStmt,
    LawStmt,
    Literal,
    LogicalOp,
    ModuleDecl,
    ObjectiveStmt,
    ProveStmt,
    Quantifier,
    Ref,
    RequireStmt,
    SolveStmt,
    Statement,
    UnaryOp,
)
from ..types import (
    UNIT_INTERVAL_KINDS,
    ConceptType,
    DistributionType,
    FunctionType,
    MatrixType,
    PredicateType,
    PropositionType,
    QuantityType,
    RandomVariableType,
    ScalarType,
    SetType,
    TensorType,
    Type,
    UnknownType,
    VectorType,
)
from .base import Backend

__all__ = ["LeanBackend", "to_lean", "LEAN_SCALARS", "SCALAR_REFINEMENTS"]


#: HML scalar -> Lean carrier type.
LEAN_SCALARS: dict[str, str] = {
    "Bool": "Bool",
    "Natural": "ℕ",
    "PositiveNatural": "ℕ",
    "Integer": "ℤ",
    "Rational": "ℚ",
    "Real": "ℝ",
    "NonNegativeReal": "ℝ",
    "PositiveReal": "ℝ",
    "Probability": "ℝ",
    # All three unit-interval kinds carry to the same ℝ. The bounds come back as
    # hypotheses via SCALAR_REFINEMENTS; the epistemic kind does not come back at all,
    # and `lean_type` weakens to say so.
    "PValue": "ℝ",
    "PosteriorProbability": "ℝ",
}

#: HML scalar -> hypotheses that recover the refinement the carrier type dropped.
#: ``{x}`` is the term the refinement constrains.
SCALAR_REFINEMENTS: dict[str, tuple[tuple[str, str], ...]] = {
    "PositiveReal": (("pos", "0 < {x}"),),
    "NonNegativeReal": (("nonneg", "0 ≤ {x}"),),
    "Probability": (("nonneg", "0 ≤ {x}"), ("le_one", "{x} ≤ 1")),
    "PValue": (("nonneg", "0 ≤ {x}"), ("le_one", "{x} ≤ 1")),
    "PosteriorProbability": (("nonneg", "0 ≤ {x}"), ("le_one", "{x} ≤ 1")),
    # ℕ already excludes negatives, so Natural needs no hypothesis; PositiveNatural
    # still needs one because ℕ contains 0.
    "PositiveNatural": (("pos", "0 < {x}"),),
}

_LEAN_KEYWORDS = {
    "abbrev", "attribute", "axiom", "by", "calc", "class", "def", "deriving", "do",
    "else", "end", "example", "exists", "extends", "forall", "from", "fun", "have",
    "if", "import", "in", "inductive", "instance", "lemma", "let", "macro", "match",
    "mutual", "namespace", "noncomputable", "notation", "open", "partial", "private",
    "protected", "rec", "section", "set_option", "show", "sorry", "structure", "then",
    "theorem", "this", "universe", "unsafe", "variable", "where", "with", "at",
    "Prop", "Sort", "Type", "fst", "snd",
}

# Relative precedence, high binds tighter. Mirrors Lean 4's own ordering.
_PREC = {
    "quant": 0,
    "iff": 1, "implies": 2, "or": 3, "and": 4, "not": 5,
    "=": 6, "!=": 6, "<": 6, "<=": 6, ">": 6, ">=": 6,
    "+": 7, "-": 7,
    "*": 8, "/": 8, "@": 8,
    "unary": 9,
    "^": 10,
    "app": 11,
}
_ATOM = 100

_CMP = {"=": "=", "!=": "≠", "<": "<", "<=": "≤", ">": ">", ">=": "≥"}
_LOGIC = {"and": "∧", "or": "∨", "implies": "→", "iff": "↔"}
_QUANT = {"forall": "∀", "exists": "∃", "exists_unique": "∃!"}
_REAL_FNS = {
    "exp": "Real.exp", "log": "Real.log", "sqrt": "Real.sqrt",
    "sin": "Real.sin", "cos": "Real.cos", "tan": "Real.tan", "abs": "abs",
}


def _lean_name(name: str) -> str:
    return f"{name}_" if name in _LEAN_KEYWORDS else name


def _top(t: str) -> str:
    """Strip one fully-enclosing paren pair.

    :meth:`LeanBackend.lean_type` parenthesises compound types so they compose safely
    inside other types. At the outermost position of a ``variable``/``def``
    ascription that paren is redundant noise, so it is removed there and only there.
    """
    if not (t.startswith("(") and t.endswith(")")):
        return t
    depth = 0
    for i, ch in enumerate(t):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return t[1:-1] if i == len(t) - 1 else t
    return t


class LeanBackend(Backend):
    target = "lean"
    limitations = (
        "Statement skeletons only. Every obligation is closed with `sorry`; no proof "
        "search is performed, and no statement emitted here is asserted to be true "
        "(design freeze §8).",
        "Refinement types are encoded as a carrier type plus a separate hypothesis, "
        "not as a subtype. A hypothesis is not part of the type, so nothing in Lean "
        "prevents a later edit from using the symbol without it in scope.",
        "Probability laws have no faithful Lean encoding without Mathlib's measure "
        "theory: a family name and role labels do not determine a measure, a density, "
        "or the measurability instances such an encoding needs. All law and infer "
        "statements are dropped rather than approximated.",
        "Lean has no dimensional analysis without a units library and a chosen unit "
        "per base dimension; HML dimensions are unit-free, so `check dimension` is "
        "dropped.",
        "Lean's `variable` is one mechanism: the epistemic distinction between "
        "var, param, const, obs and index does not survive.",
        "Lean has dependent types and HML v0 does not, so shape agreement that HML "
        "checks nominally is re-expressed with `Fin n` indices whose bounds Lean "
        "would then demand real proofs for; those proof obligations are created by "
        "the translation and did not exist in the source.",
        "No Lean toolchain is invoked by this backend; the emitted file has not been "
        "elaborated or type-checked by Lean.",
    )

    def __init__(self, module, symbols=None) -> None:
        super().__init__(module, symbols)
        self._alias: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    def _fresh(self, stem: str) -> str:
        self._counters[stem] = self._counters.get(stem, 0) + 1
        return f"{stem}_{self._counters[stem]}"

    # -- entry point ------------------------------------------------------

    def emit(self) -> str:
        ns = _lean_name(self.module.name)
        out: list[str] = [
            "/-",
            f"  Lean 4 statement skeleton generated from Hamiltonian Lang module "
            f"{self.module.name}.",
            "",
            "  Generated code. Not elaborated or type-checked by any Lean toolchain.",
            "  Every obligation is closed with `sorry`: this backend performs no proof",
            "  search (design freeze §8). Refinement types are encoded as a carrier",
            "  type plus a hypothesis, not as a subtype -- see the module docstring of",
            "  hamiltonian_lang.backends.lean for why.",
            "",
            "  Note: Lean 4 auto-binds `variable`s that appear in a declaration's",
            "  statement, but propositional variables (the `h_*` hypotheses below) may",
            "  need an explicit `include` depending on the Lean version in use.",
            "-/",
            "import Mathlib",
            "",
            f"namespace {ns}",
            "",
        ]
        for st in self.module.statements:
            out.extend(self._statement(st))
        out.append("")
        out.append(f"end {ns}")
        return "\n".join(out) + "\n"

    # -- statements -------------------------------------------------------

    def _statement(self, st: Statement) -> list[str]:
        if isinstance(st, ModuleDecl):
            return []

        if isinstance(st, Declaration):
            return self._declaration(st)

        if isinstance(st, DefineStmt):
            return self._define(st)

        if isinstance(st, LawStmt):
            cond = " | " + " ".join(g.name for g in st.given) if st.given else ""
            family = st.distribution.family if st.distribution else "?"
            self.drop(
                f"{st.role} {st.target}{cond}",
                "a probability law has no faithful Lean statement without Mathlib "
                "measure theory. Encoding it would require a measurable space on the "
                f"support of {family}, a MeasureTheory.Measure, a density and a proof "
                "that it integrates to one -- none of which is determined by a family "
                "name and role labels. Nothing is invented here.",
                st.span.line,
            )
            roles = (
                ", ".join(f"{a.role} := {self.expr(a.value)}" for a in st.distribution.args)
                if st.distribution
                else ""
            )
            return [f"-- DROPPED law: {st.role} {st.target}{cond} ~ {family}({roles})"]

        if isinstance(st, RequireStmt):
            prop = self.expr(st.proposition)
            if prop is None:
                return []
            name = _lean_name(st.label) if st.label else self._fresh("require")
            self.weaken(
                f"require{' ' + st.label if st.label else ''}",
                "an HML `require` is a constraint the model must satisfy, i.e. an "
                "obligation over free variables. Lean has no such statement form, so "
                "it is emitted as a theorem over those free variables. Read literally "
                "the theorem may be false (`require x >= 0` for a free real x is), and "
                "no Lean reader can recover from the skeleton that this was a "
                "constraint rather than a claim.",
                st.span.line,
            )
            return [
                "-- obligation from `require` (a constraint, stated here as a theorem)",
                f"theorem {name} : {prop} := by sorry",
                "",
            ]

        if isinstance(st, AssumeStmt):
            prop = self.expr(st.proposition)
            if prop is None:
                return []
            name = self._fresh("h_assume")
            return [f"variable ({name} : {prop})", ""]

        if isinstance(st, ProveStmt):
            prop = self.expr(st.proposition)
            if prop is None:
                return []
            name = _lean_name(st.label) if st.label else self._fresh("claim")
            self.weaken(
                f"prove{' ' + st.label if st.label else ''}",
                "the statement is preserved exactly; the proof is not attempted. "
                "`sorry` makes the file elaborate while proving nothing (design "
                "freeze §8 forbids proof search).",
                st.span.line,
            )
            return [f"theorem {name} : {prop} := by sorry", ""]

        if isinstance(st, CheckStmt):
            if st.check_kind == "dimension":
                self.drop(
                    "check dimension",
                    "Lean has no dimensional analysis over unit-free rational-exponent "
                    "vectors; encoding it would need a units library and a chosen unit "
                    "per base dimension, which v0 does not have (§8).",
                    st.span.line,
                )
                subj = self.expr(st.subject) if st.subject is not None else "?"
                return [f"-- DROPPED check dimension: [{subj}] = {st.expected or '?'}"]
            prop = self.expr(st.subject) if st.subject is not None else None
            if prop is None:
                self.drop(
                    "check", "nothing translatable in the checked subject", st.span.line
                )
                return []
            name = self._fresh("check")
            self.weaken(
                "check",
                "the checked proposition becomes a theorem skeleton; the HML checker "
                "may already have discharged it, but that fact does not transfer.",
                st.span.line,
            )
            return [f"theorem {name} : {prop} := by sorry", ""]

        if isinstance(st, ObjectiveStmt):
            self.drop(
                st.direction,
                "Mathlib can state `IsMinOn f s a`, but only relative to a set `s` and "
                "a witness `a`, neither of which the HML statement supplies. Inventing "
                "them would state a different theorem.",
                st.span.line,
            )
            return [
                f"-- DROPPED objective: {st.direction} {self.expr(st.expression)}"
            ]

        if isinstance(st, SolveStmt):
            self.drop(
                "solve",
                "Lean has no solve statement; the closest faithful form is an "
                "existence theorem, but which existential to state is not determined "
                "by `solve` alone.",
                st.span.line,
            )
            return [
                "-- DROPPED solve for: "
                + ", ".join(_lean_name(t.name) for t in st.targets)
            ]

        if isinstance(st, InferStmt):
            self.drop(
                f"infer {st.query}",
                "an inference query presupposes the probability laws, which this "
                "backend already dropped; there is nothing left to state.",
                st.span.line,
            )
            names = ", ".join(_lean_name(t.name) for t in st.targets)
            return [f"-- DROPPED inference: infer {st.query} {names}"]

        if isinstance(st, ConceptDecl):
            return self._concept(st)

        return []

    # -- declarations -----------------------------------------------------

    def _declaration(self, st: Declaration) -> list[str]:
        self.weaken(
            f"{st.kind} {st.name}",
            f"Lean's `variable` is a single mechanism: the declaration kind "
            f"({st.kind}) -- whether the symbol is observed data, a parameter to be "
            "inferred, or a fixed constant -- has no Lean encoding and is lost.",
            st.span.line,
        )
        lean_t = self.lean_type(st.declared_type, st.name, st.span.line)
        if lean_t is None:
            return []
        name = _lean_name(st.name)
        lines: list[str] = []
        if st.value is not None:
            value = self.expr(st.value)
            if value is None:
                lines.append(f"variable ({name} : {_top(lean_t)})")
            else:
                # A definitional binding is more faithful to `x : T = v` than a
                # variable plus an equation would be.
                lines.append(f"def {name} : {_top(lean_t)} := {value}")
        else:
            lines.append(f"variable ({name} : {_top(lean_t)})")
        lines.extend(self._refinement_hypotheses(st.name, st.declared_type, st.span.line))
        return lines

    def _refinement_hypotheses(
        self, hml_name: str, t: Type | None, line: int
    ) -> list[str]:
        """Hypotheses recovering the refinement the Lean carrier type dropped."""
        name = _lean_name(hml_name)
        base: ScalarType | None = None
        term = name
        if isinstance(t, ScalarType):
            base = t
        elif isinstance(t, QuantityType):
            base = t.base
        elif isinstance(t, RandomVariableType) and isinstance(t.codomain, ScalarType):
            base = t.codomain
        elif isinstance(t, VectorType) and isinstance(t.element, ScalarType):
            base = t.element
            term = f"{name} i"
        elif isinstance(t, MatrixType) and isinstance(t.element, ScalarType):
            base = t.element
            term = f"{name} i j"
        if base is None:
            return []
        refinements = SCALAR_REFINEMENTS.get(base.name)
        if not refinements:
            return []
        self.weaken(
            f"{hml_name} : {base.name}",
            f"the refinement is carried as a separate hypothesis over the carrier "
            f"type {LEAN_SCALARS.get(base.name, '?')}, not as part of the type. Lean "
            "will not stop a later edit from using the symbol with the hypothesis out "
            "of scope, which HML's type system would.",
            line,
        )
        binder = ""
        if isinstance(t, VectorType):
            binder = "∀ i, "
        elif isinstance(t, MatrixType):
            binder = "∀ i j, "
        out = []
        for suffix, template in refinements:
            out.append(
                f"variable (h_{name}_{suffix} : {binder}{template.format(x=term)})"
            )
        return out

    def _define(self, st: DefineStmt) -> list[str]:
        t = st.declared_type or st.type_
        lean_t = self.lean_type(t, st.name, st.span.line)
        body = self.expr(st.body)
        if body is None:
            self.drop(
                f"def {st.name}",
                "the body contains nothing this backend can translate.",
                st.span.line,
            )
            return []
        name = _lean_name(st.name)
        binders = ""
        for pname, ptype in st.params:
            pt = self.lean_type(ptype, pname, st.span.line) if ptype else None
            if pt is None:
                self.approximate(
                    f"def {st.name} parameter {pname}",
                    "the parameter has no declared HML type; Lean requires one, so ℝ "
                    "is assumed.",
                    st.span.line,
                )
                pt = "ℝ"
            binders += f" ({_lean_name(pname)} : {_top(pt)})"
        ascription = f" : {_top(lean_t)}" if lean_t else ""
        if lean_t is None:
            self.approximate(
                f"def {st.name}",
                "no Lean type for the definition's HML type; the ascription is "
                "omitted and Lean must infer it.",
                st.span.line,
            )
        return [f"def {name}{binders}{ascription} := {body}", ""]

    # -- concepts ---------------------------------------------------------

    def _concept(self, st: ConceptDecl) -> list[str]:
        prefix = _lean_name(st.name)
        self.weaken(
            f"concept {st.name}",
            "Lean has structures and classes, which would be the faithful encoding, "
            "but that changes every member into a field access and every invariant "
            "into a field of a proposition-carrying structure. This backend instead "
            f"flattens the concept's scope by prefixing members with {prefix}_, so the "
            "concept itself is not a Lean object and its members are merely "
            "conventionally related.",
            st.span.line,
        )
        if st.extends:
            self.drop(
                f"concept {st.name} extends",
                "concept inheritance is not encoded; the parents ("
                + ", ".join(st.extends)
                + ") are dropped along with whatever they contribute.",
                st.span.line,
            )
        lines = [f"-- concept {st.name} (scope flattened to {prefix}_* names)"]
        saved = dict(self._alias)
        for m in st.members:
            self._alias[m.name] = f"{prefix}_{_lean_name(m.name)}"
        for m in st.members:
            lines.extend(self._concept_member(st, m, prefix))
        self._alias = saved
        lines.append("")
        return lines

    def _concept_member(
        self, decl: ConceptDecl, m: ConceptMember, prefix: str
    ) -> list[str]:
        name = self._alias[m.name]
        if m.kind == "parameter":
            lean_t = self.lean_type(m.declared_type, name, m.span.line)
            if lean_t is None:
                return []
            out = [f"variable ({name} : {_top(lean_t)})"]
            saved = self._alias.pop(m.name)
            # _refinement_hypotheses mangles through _lean_name, so hand it the
            # already-mangled name directly.
            out.extend(self._refinement_hypotheses(name, m.declared_type, m.span.line))
            self._alias[m.name] = saved
            return out
        if m.kind == "transform":
            body = self.expr(m.body) if m.body is not None else None
            if body is None:
                self.drop(
                    f"{decl.name}.{m.name}", "transform has no body", m.span.line
                )
                return []
            # ConceptMember.params is (name, declared type) pairs; the type is
            # optional (D-015), and Lean requires one, so ℝ is assumed when absent.
            binders = ""
            for pname, ptype in m.params:
                pt = self.lean_type(ptype, pname, m.span.line) if ptype else None
                if pt is None:
                    self.approximate(
                        f"{decl.name}.{m.name} parameter {pname}",
                        "the parameter carries no declared HML type; Lean requires "
                        "one, so ℝ is assumed and any intended refinement is lost.",
                        m.span.line,
                    )
                    pt = "ℝ"
                binders += f" ({_lean_name(pname)} : {_top(pt)})"
            return [f"def {name}{binders} : ℝ := {body}"]
        if m.kind in ("invariant", "property"):
            body = self.expr(m.body) if m.body is not None else None
            if body is None:
                return []
            self.weaken(
                f"{decl.name}.{m.name}",
                f"the {m.kind}'s statement is preserved exactly, but it becomes a "
                "free-standing theorem rather than a property *of the concept*: "
                "nothing in Lean ties it back to a concept object, because the "
                "concept was flattened. The proof is not attempted (§8).",
                m.span.line,
            )
            return [f"theorem {name} : {body} := by sorry"]
        if m.kind in ("example", "counterexample"):
            body = self.expr(m.body) if m.body is not None else None
            self.drop(
                f"{decl.name}.{m.name}",
                f"a concept {m.kind} is a witness that the concept is inhabited (or, "
                "for a counterexample, that a nearby claim fails). Stating it in Lean "
                "needs an existential over the concept as an object, and the concept "
                "was flattened rather than made an object, so there is nothing to "
                "quantify over.",
                m.span.line,
            )
            return [f"-- DROPPED {m.kind} {decl.name}.{m.name}: {body or '?'}"]
        self.drop(
            f"{decl.name}.{m.name}",
            f"concept member kind {m.kind!r} has no Lean encoding.",
            m.span.line,
        )
        return []

    # -- types ------------------------------------------------------------

    def lean_type(self, t: Type | None, who: str, line: int) -> str | None:
        if t is None or isinstance(t, UnknownType):
            self.approximate(
                who, "no resolved HML type; ℝ assumed by the Lean backend", line
            )
            return "ℝ"

        if isinstance(t, ScalarType):
            if t.name in UNIT_INTERVAL_KINDS and t.name != "Probability":
                self.weaken(
                    who,
                    f"{t.name} becomes the same ℝ with 0 ≤ x ≤ 1 hypotheses as "
                    "Probability; Lean carries the bounds and not the epistemic kind, "
                    "so a p-value and a posterior are indistinguishable in the emitted "
                    "statement.",
                    line,
                )
            carrier = LEAN_SCALARS.get(t.name)
            if carrier is None:
                self.approximate(who, f"unmapped scalar {t.name}; ℝ assumed", line)
                return "ℝ"
            return carrier

        if isinstance(t, QuantityType):
            self.weaken(
                who,
                f"the dimension {t.dimension.render()} is dropped; the quantity "
                "becomes its bare carrier type, so dimensionally invalid Lean "
                "expressions become well-typed.",
                line,
            )
            return self.lean_type(t.base, who, line)

        if isinstance(t, PropositionType):
            return "Prop"

        if isinstance(t, RandomVariableType):
            self.drop(
                who,
                "a random variable is a measurable function from a probability space; "
                "Lean can express that (`Ω → ℝ` plus `Measurable`), but the space Ω is "
                "not named anywhere in the HML source, so declaring one would be "
                "invention. Declaring it as its codomain instead would conflate "
                "RandomVariable[T] with T, which the type system explicitly forbids.",
                line,
            )
            return None

        if isinstance(t, DistributionType):
            self.drop(
                who,
                "a distribution is a measure; without Mathlib measure-theoretic "
                "scaffolding that the HML source does not determine, there is nothing "
                "faithful to emit.",
                line,
            )
            return None

        if isinstance(t, VectorType):
            n = _extent(t.length)
            if n is None:
                self.drop(who, "a vector of unknown length has no Fin index type", line)
                return None
            elem = self.lean_type(t.element, who, line)
            if elem is None:
                return None
            self.weaken(
                who,
                "Vector[T, n] becomes `Fin n → T`, a total function on a finite index "
                "type. Lean's Fin carries a bounds *proof*, so every subscript in the "
                "translated code acquires a proof obligation that did not exist in the "
                "HML source, where shapes are checked nominally (§8).",
                line,
            )
            return f"(Fin {n} → {elem})"

        if isinstance(t, MatrixType):
            r, c = _extent(t.rows), _extent(t.cols)
            if r is None or c is None:
                self.drop(who, "a matrix of unknown extent has no Fin index type", line)
                return None
            elem = self.lean_type(t.element, who, line)
            if elem is None:
                return None
            self.weaken(
                who,
                "Matrix[T, m, n] becomes Mathlib's `Matrix (Fin m) (Fin n) T`, which "
                "is dependently typed; HML v0 checks shapes nominally, so the two "
                "agree on these examples but not in general (§8).",
                line,
            )
            return f"(Matrix (Fin {r}) (Fin {c}) {elem})"

        if isinstance(t, TensorType):
            self.drop(
                who,
                "there is no single Mathlib rank-n tensor type matching HML's "
                "Tensor[T, ...]; choosing one would be a design decision, not a "
                "translation.",
                line,
            )
            return None

        if isinstance(t, SetType):
            elem = self.lean_type(t.element, who, line)
            return None if elem is None else f"(Set {elem})"

        if isinstance(t, FunctionType):
            parts = [self.lean_type(d, who, line) for d in t.domain]
            cod = self.lean_type(t.codomain, who, line)
            if cod is None or any(p is None for p in parts):
                return None
            return "(" + " → ".join([*(p for p in parts if p), cod]) + ")"

        if isinstance(t, PredicateType):
            parts = [self.lean_type(d, who, line) for d in t.domain]
            if any(p is None for p in parts):
                return None
            return "(" + " → ".join([*(p for p in parts if p), "Prop"]) + ")"

        if isinstance(t, ConceptType):
            self.drop(
                who,
                "concepts are flattened rather than made Lean objects, so a concept "
                "type has no inhabitant to declare.",
                line,
            )
            return None

        self.drop(who, f"no Lean encoding for type {t.render()}", line)
        return None

    # -- expressions ------------------------------------------------------

    def _ref_name(self, name: str) -> str:
        return self._alias.get(name, _lean_name(name))

    def expr(self, e: Expr | None) -> str | None:
        r = self._expr(e)
        return None if r is None else r[0]

    def _wrap(self, e: Expr | None, outer: int, *, right: bool = False) -> str:
        r = self._expr(e)
        if r is None:
            return "sorry"
        text, prec = r
        if prec < outer or (right and prec == outer):
            return f"({text})"
        return text

    def _expr(self, e: Expr | None) -> tuple[str, int] | None:
        if e is None:
            return None

        if isinstance(e, Literal):
            if isinstance(e.value, bool):
                return ("True" if e.value else "False"), _ATOM
            return (e.raw or str(e.value)), _ATOM

        if isinstance(e, Ref):
            return self._ref_name(e.name), _ATOM

        if isinstance(e, UnaryOp):
            if e.op == "not":
                p = _PREC["not"]
                return f"¬{self._wrap(e.operand, p)}", p
            p = _PREC["unary"]
            return f"-{self._wrap(e.operand, p)}", p

        if isinstance(e, BinOp):
            if e.op == "@":
                p = _PREC["app"]
                left_t = e.left.type_
                fn = "Matrix.mulVec" if isinstance(left_t, MatrixType) else "HMul.hMul"
                if fn == "HMul.hMul":
                    self.approximate(
                        "matrix product",
                        "the left operand of `@` is not a Matrix in the resolved HML "
                        "types, so the Mathlib operation to use cannot be determined; "
                        "plain multiplication is emitted.",
                        e.span.line,
                    )
                else:
                    self.weaken(
                        "matrix product",
                        "HML's `@` becomes Mathlib's `Matrix.mulVec`, which fixes the "
                        "operand order and orientation (matrix on the left, vector on "
                        "the right); HML's `@` does not.",
                        e.span.line,
                    )
                return (
                    f"{fn} {self._wrap(e.left, p)} {self._wrap(e.right, p)}",
                    p,
                )
            if e.op == "^":
                p = _PREC["^"]
                return (
                    f"{self._wrap(e.left, p, right=True)} ^ {self._wrap(e.right, p)}",
                    p,
                )
            p = _PREC.get(e.op, 7)
            return (
                f"{self._wrap(e.left, p)} {e.op} {self._wrap(e.right, p, right=True)}",
                p,
            )

        if isinstance(e, Comparison):
            p = _PREC["="]
            op = _CMP[e.op]
            return f"{self._wrap(e.left, p)} {op} {self._wrap(e.right, p)}", p

        if isinstance(e, LogicalOp):
            p = _PREC[e.op]
            sym = _LOGIC[e.op]
            # → and ↔ are right-associative in Lean; ∧ and ∨ are too.
            return (
                f"{self._wrap(e.left, p, right=True)} {sym} {self._wrap(e.right, p)}",
                p,
            )

        if isinstance(e, Call):
            p = _PREC["app"]
            args = [self._wrap(a, p) for a in e.args]
            if e.callee in _REAL_FNS:
                fn = _REAL_FNS[e.callee]
            elif e.callee in self._alias:
                fn = self._alias[e.callee]
            else:
                self.approximate(
                    f"call {e.callee}",
                    "not a known Mathlib function and not a definition in this module; "
                    "emitted as a bare application, which Lean will reject unless the "
                    "name is supplied.",
                    e.span.line,
                )
                fn = _lean_name(e.callee)
            return f"{fn} {' '.join(args)}".rstrip(), p

        if isinstance(e, Index):
            p = _PREC["app"]
            idx = " ".join(self._wrap(i, p) for i in e.indices)
            self.weaken(
                "index expression",
                "Lean indexes a `Fin n → T` by a `Fin n`, which carries a proof that "
                "the index is in range. The HML subscript carries no such proof, so "
                "the emitted application will need a coercion or a bounds proof that "
                "the source never supplied.",
                e.span.line,
            )
            return f"{self._wrap(e.base, p)} {idx}", p

        if isinstance(e, Quantifier):
            var_t = self.lean_type(e.var_type, e.var, e.span.line)
            if var_t is None:
                self.drop(
                    f"{e.kind} {e.var}",
                    "the quantified variable's type has no Lean encoding, so the "
                    "binder cannot be emitted.",
                    e.span.line,
                )
                return None
            body = self._expr(e.body)
            if body is None:
                self.drop(
                    f"{e.kind} {e.var}",
                    "the quantifier body has no Lean encoding.",
                    e.span.line,
                )
                return None
            # Nesting order is preserved by construction: the body is emitted inside
            # this binder and never reordered.
            q = _QUANT[e.kind]
            return f"{q} {_lean_name(e.var)} : {_top(var_t)}, {body[0]}", _PREC["quant"]

        if isinstance(e, DistExpr):
            self.drop(
                f"{e.family} distribution expression",
                "no Lean term denotes a distribution here; see the law statement.",
                e.span.line,
            )
            return None

        self.drop("expression", f"no Lean encoding for {type(e).__name__}", e.span.line)
        return None


def _extent(n: str | int | None) -> str | None:
    if n is None:
        return None
    return _lean_name(str(n)) if isinstance(n, str) else str(n)


def to_lean(module, symbols=None):
    return LeanBackend(module, symbols).run()
