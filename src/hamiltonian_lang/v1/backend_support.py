"""Machine-readable backend support table — HML-V1-CONCEPT-001 Phase 8.

Populates the ``backend_support`` block of ``spec/concept_registry.schema.json``
programmatically instead of by hand, so that the schema's central promise —
*"``verified_by_toolchain``: True ONLY if a real compiler accepted it"* — is enforced by
construction rather than by good intentions.

The one rule this module exists to enforce
------------------------------------------
:attr:`Support.verified_by_toolchain` is a **derived property with no setter**. It is
True only when a :class:`ToolchainEvidence` record is attached *and* that record reports
an accepting run. There is deliberately no way to assert the flag without supplying the
command, the exit code and the output that justify it.

Why that rule needed teeth, measured on this machine
----------------------------------------------------
Three separate ways a naive "the compiler accepted it" check returns a false positive
were reproduced during Phase 8; each is recorded on the evidence record that refutes it.

1. **``sorry`` compiles.** ``theorem definitely_false : (1 : Nat) = 2 := by sorry``
   exits **0** under Lean 4.32.2, emitting only a warning. Exit status alone therefore
   certifies a demonstrably false theorem. ``#print axioms`` separates the cases:
   the skeleton depends on ``sorryAx``, a real proof does not. Hence
   :attr:`ToolchainEvidence.sorry_free`, which is mandatory for Lean.
2. **Lean invents missing types.** With the default ``autoImplicit``,
   ``theorem t : ∀ x : Real, x = x`` elaborates and exits 0 even though ``Real`` does
   not exist in core Lean: ``#print t`` reveals
   ``theorem t.{u_1} : ∀ {Real : Sort u_1} (x : Real), x = x``. Lean silently bound
   ``Real`` as an implicit variable of arbitrary sort, so the accepted theorem is a
   vacuous statement about an arbitrary type, not about the reals. Every Lean probe
   behind this table therefore sets ``autoImplicit false`` and
   ``relaxedAutoImplicit false``.
3. **Executing generated Python proves only that it runs.** The SymPy backend's output
   imports and executes cleanly, which establishes syntactic validity and nothing about
   whether the mathematics survived. Recorded in ``does_not_establish``.

Relationship to the V0 measured findings
----------------------------------------
The V0 rows restate results already measured in ``tests/roundtrip/test_importers.py``
and ``docs/evaluation/HML_EVAL_001_PILOT_REPORT.md`` §4. They are carried, not
rediscovered, and this module must never contradict them. In particular:

* Stan's ``real<lower=0>`` admits 0 and HML's ``PositiveReal`` does not, so every family
  carrying a ``PositiveReal`` role is outside the Stan round-trippable subset. Only
  ``Uniform``, ``Binomial`` and ``Bernoulli`` survive.
* Stan loses observed values and destroys interleaved declaration order.
* The Lean route drops probability laws silently and the reconstruction still compiles;
  only the content-hash comparison detects the loss.

**No general HML↔Stan or HML↔Lean round-trip equivalence is claimed anywhere.** It does
not exist, and the findings above are why.

Status vocabulary
-----------------
``status`` describes what survives *translation*; ``verified_by_toolchain`` separately
describes whether a compiler was actually run. The two are orthogonal on purpose: a
construct can be faithfully translatable into a target no compiler here can check, and a
construct can compile while meaning something other than it did.

* :attr:`Status.SUPPORTED` — survives with no declared loss. Carries no ``losses``.
* :attr:`Status.PARTIAL` — translates, but something is dropped, weakened or
  approximated. ``losses`` must be non-empty and says what.
* :attr:`Status.UNSUPPORTED` — no faithful encoding exists. ``reason`` must be non-empty.

Nothing here modifies V0, which is frozen at ``hml-v0-baseline``, and nothing here
modifies the epistemic contract in :mod:`hamiltonian_lang.v1.epistemic`, which is only
read.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .epistemic import EpistemicStatus

__all__ = [
    "Backend",
    "Status",
    "Layer",
    "Obstacle",
    "ToolchainProbe",
    "ToolchainEvidence",
    "Support",
    "LeanEncoding",
    "TOOLCHAINS",
    "PROBE_DATE",
    "V1_LAYERS",
    "V0_LAYERS",
    "SUPPORT",
    "LEAN_EPISTEMIC",
    "supported",
    "entry",
    "registry_backend_support",
    "toolchain",
    "unverified",
]

#: The date on which every probe recorded in this module was executed.
PROBE_DATE = "2026-08-05"


class Backend(StrEnum):
    """The three V0 backends this table covers. All are frozen; none is modified here."""

    LEAN = "lean"
    STAN = "stan"
    SYMPY = "sympy"


class Status(StrEnum):
    """What survives translation. See the module docstring for the exact contract."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"


class Obstacle(StrEnum):
    """Why a construct has no encoding in a target.

    The distinction between the last two is load-bearing and must not be collapsed:

    * :attr:`LIBRARY_GATED` — the target *language* can express it, but the library that
      supplies the vocabulary is absent here. Installing the library moves the row.
    * :attr:`CATEGORY_MISMATCH` — the target cannot express it at all, because the thing
      being expressed is not the kind of thing the target talks about. **No library
      fixes this.** Recording it as library-gated would imply a fix exists.
    """

    NONE = "none"
    LIBRARY_GATED = "library_gated"
    CATEGORY_MISMATCH = "category_mismatch"
    NO_SURFACE = "no_surface"


class Layer(StrEnum):
    """V1 layers, then every V0 construct carried over from the measured findings."""

    # -- V1 layers (spec/v1/semantic_objects.yaml) ------------------------
    CONCEPT_REGISTRY = "concept_registry"
    MINTING_PROTOCOL = "minting_protocol"
    MORPHOLOGY = "morphology"
    TRANSFORMATION = "transformation"
    INFERENCE = "inference"
    EPISTEMIC_STATUS = "epistemic_status"
    DISCOURSE_STATE = "discourse_state"

    # -- V0 constructs ----------------------------------------------------
    V0_DECLARATION_KIND = "v0_declaration_kind"
    V0_REFINEMENT_SCALAR = "v0_refinement_scalar"
    V0_QUANTITY_DIMENSION = "v0_quantity_dimension"
    V0_PROBABILITY_LAW = "v0_probability_law"
    V0_CONDITIONING_SET = "v0_conditioning_set"
    V0_INFERENCE_QUERY = "v0_inference_query"
    V0_QUANTIFIER = "v0_quantifier"
    V0_PROPOSITION = "v0_proposition"
    V0_OBJECTIVE = "v0_objective"
    V0_SOLVE = "v0_solve"
    V0_CHECK_DIMENSION = "v0_check_dimension"
    V0_CONCEPT_DECL = "v0_concept_decl"
    V0_VECTOR_MATRIX = "v0_vector_matrix"
    V0_DEFINITION = "v0_definition"
    V0_OBSERVED_VALUE = "v0_observed_value"
    V0_DECLARATION_ORDER = "v0_declaration_order"


V1_LAYERS: tuple[Layer, ...] = (
    Layer.CONCEPT_REGISTRY,
    Layer.MINTING_PROTOCOL,
    Layer.MORPHOLOGY,
    Layer.TRANSFORMATION,
    Layer.INFERENCE,
    Layer.EPISTEMIC_STATUS,
    Layer.DISCOURSE_STATE,
)

V0_LAYERS: tuple[Layer, ...] = tuple(
    layer for layer in Layer if layer.value.startswith("v0_")
)


# ---------------------------------------------------------------------------
# Toolchain presence, as actually probed
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolchainProbe:
    """What was found on this machine when Phase 8 looked. Not an aspiration."""

    name: str
    present: bool
    version: str
    command: str
    detail: str


TOOLCHAINS: tuple[ToolchainProbe, ...] = (
    ToolchainProbe(
        name="lean",
        present=True,
        version="4.32.2 (arm64-apple-darwin24.6.0, commit f3b06c705e6c)",
        command="/Users/moheet/.elan/bin/lean --version",
        detail=(
            "Installed on demand by elan during Phase 8. Core Lean 4 only: it has ℕ, ℤ "
            "and Prop, and it does NOT have ℝ, abs on ℝ, or any measure theory."
        ),
    ),
    ToolchainProbe(
        name="lake",
        present=True,
        version="5.0.0-src+f3b06c7",
        command="/Users/moheet/.elan/bin/lake --version",
        detail="Present but unused: no Lean package is built by this repository.",
    ),
    ToolchainProbe(
        name="mathlib",
        present=False,
        version="",
        command="/Users/moheet/.elan/bin/lean <file with `import Mathlib`>",
        detail=(
            "ABSENT. `error: unknown module prefix 'Mathlib'` — no directory 'Mathlib' "
            "or file 'Mathlib.olean' in the search path. This is the single most "
            "consequential gap in the table: the V0 Lean backend emits `import Mathlib` "
            "and every HML scalar except Bool/Natural/Integer maps to ℝ, which lives in "
            "Mathlib. Consequently no ℝ-typed HML module can be checked here at all."
        ),
    ),
    ToolchainProbe(
        name="stanc",
        present=False,
        version="",
        command="which stanc; which cmdstan; pip list | grep -i stan",
        detail=(
            "ABSENT. Not on PATH, no ~/.cmdstan or ~/cmdstan directory, and no "
            "cmdstanpy/pystan/httpstan in the virtualenv. No Stan row in this table is "
            "toolchain-verified, and none claims to be."
        ),
    ),
    ToolchainProbe(
        name="sympy",
        present=True,
        version="1.14.0",
        command=".venv/bin/python -c 'import sympy; print(sympy.__version__)'",
        detail=(
            "Present. The only target on this machine whose generated artefacts can be "
            "executed end to end — though execution establishes only that the file runs."
        ),
    ),
)


def toolchain(name: str) -> ToolchainProbe:
    """The probe record for ``name``. Raises if the toolchain was never probed."""
    for probe in TOOLCHAINS:
        if probe.name == name:
            return probe
    raise KeyError(f"no toolchain probe recorded for {name!r}")


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolchainEvidence:
    """A real run of a real toolchain, with the output that justifies the verdict.

    ``exit_code`` may be non-zero: a **negative** result is evidence too, and recording
    that the V0 Lean output was submitted to Lean and rejected is more informative than
    recording nothing. :attr:`accepted` is what gates
    :attr:`Support.verified_by_toolchain`, and it is False for such records.
    """

    tool: str
    version: str
    command: str
    exit_code: int
    output: str
    scope: str
    establishes: str
    does_not_establish: str
    #: Lean only, and mandatory there: whether `#print axioms` showed no `sorryAx` and
    #: no `declaration uses 'sorry'` warning was emitted. Exit code 0 is not sufficient.
    sorry_free: bool | None = None
    checked_at: str = PROBE_DATE

    def __post_init__(self) -> None:
        if not self.command.strip():
            raise ValueError("evidence must record the exact command that was run")
        if not self.scope.strip():
            raise ValueError("evidence must record what exactly was submitted")
        if not self.does_not_establish.strip():
            raise ValueError(
                "evidence must record what it does NOT establish; an unbounded claim "
                "of verification is the failure mode this field exists to prevent"
            )
        if self.tool == "lean" and self.exit_code == 0 and self.sorry_free is None:
            raise ValueError(
                "a Lean run that exited 0 must state whether it was sorry-free: "
                "`theorem : (1 : Nat) = 2 := by sorry` also exits 0"
            )

    @property
    def accepted(self) -> bool:
        """Whether the toolchain genuinely accepted the artefact.

        Exit code 0 is necessary and, for Lean, not sufficient — a ``sorry``-closed
        skeleton exits 0 while proving nothing.
        """
        if self.exit_code != 0:
            return False
        if self.tool == "lean" and not self.sorry_free:
            return False
        return True


# -- the evidence records actually produced in Phase 8 ----------------------

_LEAN_VERSION = "4.32.2"

#: Lean accepted a hand-written encoding of the V1 layer shapes over ℕ, with no `sorry`.
EV_LEAN_V1_LAYERS = ToolchainEvidence(
    tool="lean",
    version=_LEAN_VERSION,
    command="/Users/moheet/.elan/bin/lean V1Layers.lean",
    exit_code=0,
    output=(
        "'HmlV1Probe.double_even' depends on axioms: [propext]\n"
        "'HmlV1Probe.entailment_mp' does not depend on any axioms\n"
        "'HmlV1Probe.counterexample_not_all_even' depends on axioms: [propext]\n"
        "'HmlV1Probe.discharge_goal_comm' does not depend on any axioms"
    ),
    sorry_free=True,
    scope=(
        "A hand-written Lean file, `autoImplicit false` and `relaxedAutoImplicit "
        "false`, encoding: a concept-shaped definition plus a proved invariant; an "
        "Entailment discharged by modus ponens; a ConverseClaim stated as a "
        "Prop-valued `def` and not asserted; a Counterexample as a proof of a "
        "negation; a discourse Goal stated as a Prop and discharged by a proof term; "
        "and an open Goal left undischarged. All over ℕ."
    ),
    establishes=(
        "These encoding SHAPES elaborate and pass the Lean kernel with no `sorryAx`: "
        "the propositional structure of the concept, inference and discourse layers has "
        "a genuine Lean 4 realisation over a type core Lean provides."
    ),
    does_not_establish=(
        "It does NOT establish that HML emits these encodings — no V1 Lean emitter "
        "exists, and the file was written by hand. It does NOT establish anything about "
        "ℝ-typed content, which is what HML actually uses and which needs Mathlib. It "
        "does NOT establish that any particular HML module translates correctly."
    ),
)

#: Lean accepted the epistemic-status encodings that have one, again with no `sorry`.
EV_LEAN_EPISTEMIC = ToolchainEvidence(
    tool="lean",
    version=_LEAN_VERSION,
    command=(
        "/Users/moheet/.elan/bin/lean EpistemicProbe.lean; "
        "/Users/moheet/.elan/bin/lean AxiomAudit.lean"
    ),
    exit_code=0,
    output=(
        "EpistemicProbe.lean: no diagnostics, exit 0\n"
        "AxiomAudit.lean:\n"
        "  'A.status_proved' does not depend on any axioms\n"
        "  'A.status_disproved' depends on axioms: [propext, Quot.sound]\n"
        "  'A.skeleton_only' depends on axioms: [sorryAx]   <-- the control"
    ),
    sorry_free=True,
    scope=(
        "Hand-written core-Lean encodings, `autoImplicit false`, of exactly five "
        "epistemic statuses: proved (theorem + real proof term), definitionally_true "
        "(`rfl`), disproved (proof of a negation), conjectured (Prop-valued `def`, "
        "deliberately unproved) and model_conditional (hypothesis carried in the type). "
        "AxiomAudit.lean additionally contains a `sorry`-closed FALSE theorem as a "
        "control, to show what an unaccepted proof looks like."
    ),
    establishes=(
        "Those five statuses have real Lean encodings that the kernel accepts. The "
        "control confirms the accept/reject discrimination is meaningful: the false "
        "theorem exits 0 too, and is separated only by its `sorryAx` dependency."
    ),
    does_not_establish=(
        "It does NOT establish a Lean encoding for any of the remaining eleven "
        "statuses, none of which was submitted because none has an encoding to submit. "
        "It does NOT establish that HML generates these; there is no V1 Lean emitter."
    ),
)

#: NEGATIVE evidence: the V0 Lean backend's own output, submitted to Lean and rejected.
EV_LEAN_V0_OUTPUT_REJECTED = ToolchainEvidence(
    tool="lean",
    version=_LEAN_VERSION,
    command=(
        "hml views examples/logic/quantifier_scope.hml --target lean > QuantScope.lean; "
        "/Users/moheet/.elan/bin/lean QuantScope.lean"
    ),
    exit_code=1,
    output=(
        "QuantScope.lean:14:0: error: unknown module prefix 'Mathlib'\n"
        "  No directory 'Mathlib' or file 'Mathlib.olean' in the search path.\n"
        "-- with `import Mathlib` stripped, autoImplicit at its default:\n"
        "  error: failed to synthesize instance of type class LT ℝ  (x2)\n"
        "-- with `import Mathlib` stripped and autoImplicit false:\n"
        "  error: Unknown identifier `ℝ`  (x4)"
    ),
    sorry_free=None,
    scope=(
        "Unmodified V0 Lean backend output for examples/logic/quantifier_scope.hml, "
        "then two repair attempts. All three were rejected."
    ),
    establishes=(
        "V0 Lean backend output does not compile on this machine, and the failure is "
        "not incidental: ℝ is a Mathlib type and Mathlib is absent. The middle attempt "
        "is the instructive one — with autoImplicit at its default, Lean silently bound "
        "ℝ as an implicit variable of arbitrary sort and got as far as failing to find "
        "an `LT` instance for it, i.e. it was elaborating a fabricated type."
    ),
    does_not_establish=(
        "It does NOT establish that the emitted Lean is wrong. The statements may well "
        "be faithful; they simply cannot be checked here. Absence of verification is "
        "not evidence of a defect, and is not recorded as one."
    ),
)

#: Lean proved one HML quantifier scoping and refuted the other. Both `sorry`-free.
EV_LEAN_QUANTIFIER_SCOPE = ToolchainEvidence(
    tool="lean",
    version=_LEAN_VERSION,
    command="/Users/moheet/.elan/bin/lean QuantifierScoping.lean",
    exit_code=0,
    output=(
        "'Scope.forall_exists' does not depend on any axioms\n"
        "'Scope.exists_forall_is_false' does not depend on any axioms"
    ),
    sorry_free=True,
    scope=(
        "The two scopings HML deliberately keeps distinct "
        "(examples/logic/quantifier_scope.hml and quantifier_scope_reversed.hml), "
        "restated over ℕ with real proof terms and no `sorry`: "
        "`∀ a, ∃ b, b > a` proved via ⟨a+1, Nat.lt_succ_self a⟩, and "
        "`¬ (∃ b, ∀ a, b > a)` proved via Nat.lt_irrefl."
    ),
    establishes=(
        "Nesting order is preserved with its meaning intact, not merely its text: over "
        "ℕ one scoping is PROVABLE and the other is REFUTABLE, and Lean's kernel agrees "
        "with HML that they are different propositions. Neither proof touches any "
        "axiom, so neither is a skeleton."
    ),
    does_not_establish=(
        "It does NOT establish the ℝ-typed case, which is what the HML examples actually "
        "say and which needs Mathlib — over ℝ the first is true and the second false, "
        "and neither was checked here. It does NOT establish that the V0 Lean backend's "
        "own emitted file compiles; separately measured, it does not."
    ),
)

#: Lean accepted a derivation chain and DEMANDED a cancellation's side condition.
EV_LEAN_DERIVATION = ToolchainEvidence(
    tool="lean",
    version=_LEAN_VERSION,
    command="/Users/moheet/.elan/bin/lean Derivation.lean",
    exit_code=0,
    output=(
        "'Deriv.chain' does not depend on any axioms\n"
        "'Deriv.cancel_needs_nonzero' does not depend on any axioms\n"
        "-- control, side condition omitted and replaced by `sorry`:\n"
        "   DerivationBad.lean:2:8: warning: declaration uses `sorry`   (exit 0)"
    ),
    sorry_free=True,
    scope=(
        "A `calc` chain of rewrite steps over ℕ, and a cancellation step "
        "(Nat.eq_of_mul_eq_mul_left) whose `0 < a` side condition is supplied "
        "explicitly. A control file omits the side condition."
    ),
    establishes=(
        "Lean is a genuine home for a Derivation chain, and it DEMANDS the side "
        "condition rather than discarding it — the opposite of SymPy's behaviour on the "
        "same operation. The control shows what omitting it costs: the obligation does "
        "not disappear, it becomes a `sorry` and an unproved theorem."
    ),
    does_not_establish=(
        "It does NOT establish that HML emits `calc` chains — no V1 Lean emitter "
        "exists. It does NOT cover the ℝ-typed operations (differentiate, integrate, "
        "limit) that the transformation layer actually names, all of which need "
        "Mathlib. It does NOT establish that `simplify` can be made to record which "
        "identity it used; that remains unsolved in both targets."
    ),
)

#: SymPy executed the V0 SymPy backend's output for the canonical example corpus.
EV_SYMPY_EXECUTES = ToolchainEvidence(
    tool="sympy",
    version="1.14.0",
    command=(
        "for f in examples/{algebra,concepts,logic,physics,statistics}/*.hml; do\n"
        "    hml views $f --target sympy > gen/$(basename $f .hml).py; done\n"
        "for g in gen/*.py; do .venv/bin/python $g; done"
    ),
    exit_code=0,
    output=(
        "8/8 canonical examples rendered and executed, exit 0, no exception:\n"
        "  constrained_optimisation (2 losses)  location_scale_family (5)\n"
        "  quantifier_scope (2)  quantifier_scope_reversed (2)  kinetic_energy (3)\n"
        "  bayesian_coin (6)  linear_regression (8)  normal_distribution (2)"
    ),
    scope=(
        "V0 SymPy backend output for every .hml under examples/algebra, "
        "examples/concepts, examples/logic, examples/physics and examples/statistics, "
        "executed as Python modules. Covers concepts, vectors, laws, objectives, "
        "solves, observed values, quantifiers and definitions."
    ),
    establishes=(
        "The generated Python is syntactically valid, imports SymPy, and constructs its "
        "expression objects without raising, across the whole canonical corpus."
    ),
    does_not_establish=(
        "Execution is NOT a semantic check — linear_regression executed cleanly while "
        "reporting EIGHT dropped or weakened constructs, which is exactly why running a "
        "file must never be reported as verifying it. Nor is clean execution even "
        "guaranteed: a separate probe found generated modules that raise NameError on "
        "import (see EV_SYMPY_DANGLING_REFERENCE), so this result is a property of this "
        "corpus, not of the backend."
    ),
)

#: NEGATIVE: a V0 SymPy defect found by executing generated code. Reported, not fixed.
EV_SYMPY_DANGLING_REFERENCE = ToolchainEvidence(
    tool="sympy",
    version="1.14.0",
    command=(
        "printf 'module Min\\n\\ndef p : Proposition := forall x : Real . x = x\\n\\n"
        "prove p\\n' | hml views - --target sympy > m.py; .venv/bin/python m.py"
    ),
    exit_code=1,
    output=(
        "generated module contains `claims.append(p)` while `definitions` is empty\n"
        "NameError: name 'p' is not defined\n"
        "also reproduced on "
        "examples/candidate_syntaxes/a_labelled_linear/6_quantifier_scope.hml"
    ),
    scope=(
        "A `define` whose declared type is Proposition and whose body is a quantifier, "
        "referenced afterwards by `prove`."
    ),
    establishes=(
        "A real defect in the frozen V0 SymPy backend, found only by EXECUTING the "
        "output rather than inspecting it. The quantified body is dropped — correctly, "
        "since SymPy has no binder — but the later `prove` still emits a reference to "
        "the name the dropped definition would have bound, so the module raises "
        "NameError on import. The drop is honest; the dangling reference it leaves "
        "behind is not handled."
    ),
    does_not_establish=(
        "It does NOT establish how widespread the pattern is: 8/8 canonical examples "
        "are unaffected because none of them names a quantified proposition and then "
        "proves it by name. Not fixed here — V0 is frozen at hml-v0-baseline and is "
        "outside this phase's write scope; it is reported for a separate change."
    ),
)

#: SymPy performs layer-2 operations while discharging none of their obligations.
EV_SYMPY_DROPS_OBLIGATIONS = ToolchainEvidence(
    tool="sympy",
    version="1.14.0",
    command=(
        ".venv/bin/python -c \"import sympy as sp; x,y=sp.symbols('x y'); "
        "print(sp.cancel((x*y)/x)); print(sp.simplify(sp.sin(x)**2+sp.cos(x)**2))\""
    ),
    exit_code=0,
    output=(
        "sp.cancel((x*y)/x)                -> y      # x != 0 neither recorded nor checked\n"
        "sp.simplify((x-x)/x)              -> 0      # same\n"
        "sp.simplify(sin(x)**2+cos(x)**2)  -> 1      # which identity? not recorded\n"
        "hasattr(sympy,'ForAll') -> False; hasattr(sympy,'Exists') -> False\n"
        "sp.Implies(P, Q)                  -> Implies(P, Q)   # propositional only\n"
        "sp.Eq(x+y, y+x)                   -> True   # auto-evaluates to a bool"
    ),
    scope="Direct probe of the SymPy operations the V1 transformation layer names.",
    establishes=(
        "SymPy performs `cancel`, `divide` and `simplify` while silently discarding the "
        "very side conditions the transformation layer exists to catch, and records no "
        "identity for a simplification. `sp.Implies` gives propositional inference only; "
        "there is no quantifier. `sp.Eq` collapses to a bare bool with no justification "
        "object, so proved and conjectured are indistinguishable in the target."
    ),
    does_not_establish=(
        "It does NOT establish that SymPy is unusable for the layer — it can compute the "
        "candidate rewrite. It establishes only that the obligation must be discharged "
        "on the HML side, because the target will not do it and will not complain."
    ),
)


# ---------------------------------------------------------------------------
# Support entries
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Support:
    """One (layer, backend) cell of the matrix."""

    layer: Layer
    backend: Backend
    status: Status
    losses: tuple[str, ...] = ()
    reason: str = ""
    evidence: ToolchainEvidence | None = None

    def __post_init__(self) -> None:
        if self.status is Status.UNSUPPORTED and not self.reason.strip():
            raise ValueError(
                f"{self.layer}/{self.backend}: an `unsupported` entry must carry a "
                "reason. 'Unsupported' with no stated why is indistinguishable from "
                "'nobody looked'."
            )
        if self.status is Status.PARTIAL and not self.losses:
            raise ValueError(
                f"{self.layer}/{self.backend}: a `partial` entry must enumerate its "
                "losses, otherwise it is a `supported` entry with a hedge attached."
            )
        if self.status is Status.SUPPORTED and self.losses:
            raise ValueError(
                f"{self.layer}/{self.backend}: a `supported` entry declares no losses. "
                "If something is lost the status is `partial`."
            )
        if self.status is Status.UNSUPPORTED and self.evidence is not None:
            if self.evidence.accepted:
                raise ValueError(
                    f"{self.layer}/{self.backend}: an accepting toolchain run cannot "
                    "back an `unsupported` entry — one of the two is wrong."
                )
        if self.evidence is not None:
            expected = {
                Backend.LEAN: "lean",
                Backend.STAN: "stanc",
                Backend.SYMPY: "sympy",
            }[self.backend]
            if self.evidence.tool != expected:
                raise ValueError(
                    f"{self.layer}/{self.backend}: evidence produced by "
                    f"{self.evidence.tool!r} cannot back the {self.backend} row; "
                    f"expected {expected!r}"
                )

    @property
    def verified_by_toolchain(self) -> bool:
        """True only when an attached evidence record reports an accepting run.

        There is no setter. The schema's ``verified_by_toolchain`` field is populated
        from this property, so the flag cannot be raised without a command and an exit
        code behind it.
        """
        return self.evidence is not None and self.evidence.accepted


def _s(
    layer: Layer,
    backend: Backend,
    status: Status,
    *,
    losses: tuple[str, ...] = (),
    reason: str = "",
    evidence: ToolchainEvidence | None = None,
) -> Support:
    return Support(layer, backend, status, losses, reason, evidence)


# Shorthand for the two obstacles that recur across many rows.
_NO_STAN_PROPS = (
    "Stan has no propositions, no quantifiers, no proof obligations and no user-defined "
    "types. The V0 Stan backend already emits `require`, `prove`, `assume` and `check` "
    "as comments and reports them as dropped; a comment is not code."
)
_NO_STANC = (
    "No Stan row in this table is toolchain-verified: `stanc` is not installed on this "
    "machine (see TOOLCHAINS)."
)

_SUPPORT_LIST: tuple[Support, ...] = (
    # =====================================================================
    # V1 layer 1 — typed concept registry
    # =====================================================================
    _s(
        Layer.CONCEPT_REGISTRY,
        Backend.LEAN,
        Status.PARTIAL,
        losses=(
            "A concept is flattened, not made an object: the V0 Lean backend prefixes "
            "members with `Concept_` and says so. Members are then only conventionally "
            "related, and `extends` is dropped outright along with everything the "
            "parents contribute.",
            "The lifecycle (proposed/defined/checked/admitted/rejected/duplicate/"
            "deprecated) has no Lean encoding. A Lean file cannot say a definition is "
            "provisional.",
            "Provenance, aliases and the `compresses` justification carry no Lean form.",
            "`claimStatus` on invariants, equivalences and implications is lost. A "
            "`sorry`-closed theorem is textually identical to a proved one; only "
            "`#print axioms` separates them, and that is outside the file.",
            "Concept `example` and `counterexample` members are dropped by the V0 "
            "backend: stating them needs an existential over the concept as an object, "
            "and the concept was flattened rather than made one.",
            "Parameter types are the ordinary HML scalars, so any ℝ-typed concept is "
            "uncheckable here — Mathlib is absent.",
        ),
        evidence=EV_LEAN_V1_LAYERS,
    ),
    _s(
        Layer.CONCEPT_REGISTRY,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan has no user-defined types, no namespaces and no propositions, so a "
            "concept has nothing to become. A `formal_definition` could occasionally be "
            "a `functions` block entry, but invariants, equivalences, implications, "
            "counterexamples and proof obligations have no Stan form at all — and the "
            "V0 Stan importer explicitly rejects `functions` blocks as outside its "
            "subset. Separately, any concept with a `PositiveReal` parameter cannot "
            "round-trip: `real<lower=0>` admits 0. " + _NO_STANC
        ),
    ),
    _s(
        Layer.CONCEPT_REGISTRY,
        Backend.SYMPY,
        Status.PARTIAL,
        losses=(
            "The concept is not an object: members are name-mangled to "
            "`Concept__member` because SymPy has no namespace for symbols.",
            "Invariants survive only as relational expression objects. SymPy has no "
            "first-order quantifier (probed: no `ForAll`, no `Exists`), so any "
            "quantified invariant is dropped.",
            "There is no justification object. `sp.Eq(x+y, y+x)` auto-evaluates to the "
            "bare bool `True`, so a proved invariant and a conjectured one are "
            "indistinguishable in the target.",
            "Lifecycle, provenance, admission report and `compresses` have no encoding.",
        ),
        evidence=EV_SYMPY_EXECUTES,
    ),
    # =====================================================================
    # V1 layer 2 — concept-minting protocol
    # =====================================================================
    _s(
        Layer.MINTING_PROTOCOL,
        Backend.LEAN,
        Status.UNSUPPORTED,
        reason=(
            "The minting protocol is a *process* applied to a candidate concept — "
            "registry search, equality/equivalence/renaming matching, type validation, "
            "obligation generation, compression demonstration, verdict. Its output is "
            "an admission report about the registry, not a mathematical object in the "
            "concept's own domain. Lean has no surface for it, and manufacturing one "
            "(an `axiom` asserting admission, say) would state something the protocol "
            "never claimed. The obligations the protocol *generates* are a different "
            "thing and are covered by the concept_registry and inference rows."
        ),
    ),
    _s(
        Layer.MINTING_PROTOCOL,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "As for Lean: a protocol is not a construct any executable target "
            "represents, and Stan has strictly less surface than Lean does. " + _NO_STANC
        ),
    ),
    _s(
        Layer.MINTING_PROTOCOL,
        Backend.SYMPY,
        Status.UNSUPPORTED,
        reason=(
            "A protocol has no SymPy expression form. The admission report is registry "
            "metadata; it belongs in the registry JSON, which is where the schema puts "
            "it, and emitting it as Python data would not make it a SymPy object."
        ),
    ),
    # =====================================================================
    # V1 layer 3 — semantic morphology (concept families)
    # =====================================================================
    _s(
        Layer.MORPHOLOGY,
        Backend.LEAN,
        Status.UNSUPPORTED,
        reason=(
            "A Lean identifier is an atom: it carries no internal structure a checker "
            "can read. The obvious-looking encoding — a namespace hierarchy such as "
            "`Estimation.estimator` — imposes a tree on a relation that need not be a "
            "tree, and Lean would treat the components as opaque path segments anyway, "
            "so nothing is gained that a naming convention does not already give. The "
            "family's *content* does survive: its members are ordinary typed "
            "declarations and its invariants are ordinary theorems, both covered by the "
            "concept_registry row. It is the morphological relation between the names "
            "that has no encoding. Note that the spec forbids generating morphology "
            "('DECLARED, never GENERATED'), so there is no derivation rule to translate "
            "in the first place."
        ),
    ),
    _s(
        Layer.MORPHOLOGY,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan identifiers are flat ASCII names with no namespace mechanism at all, "
            "so even the unfaithful namespace approximation available in Lean does not "
            "exist here. " + _NO_STANC
        ),
    ),
    _s(
        Layer.MORPHOLOGY,
        Backend.SYMPY,
        Status.UNSUPPORTED,
        reason=(
            "A `sympy.Symbol` name is an opaque string; SymPy assumptions constrain "
            "values, not vocabulary. The V0 SymPy backend already flattens concept "
            "scope by mangling to `Concept__member`, which is a naming convention rather "
            "than a structure SymPy can interrogate. Critically, the estimator/estimate/"
            "procedure distinction the family layer exists to enforce would have to be "
            "carried by *types*, and every one of them becomes a bare `Symbol`."
        ),
    ),
    # =====================================================================
    # V1 layer 4a — transformation edges (Step, Derivation)
    # =====================================================================
    _s(
        Layer.TRANSFORMATION,
        Backend.LEAN,
        Status.PARTIAL,
        losses=(
            "Lean's `calc` blocks and `rw` are a genuine home for a Derivation chain, "
            "and — unlike SymPy — Lean *demands* the side conditions rather than "
            "discarding them, which is the right failure direction. But the demand is "
            "the loss: `divide`, `cancel`, `sqrt_both_sides`, `differentiate`, "
            "`integrate` and `limit` all become goals Lean will not close without a "
            "proof the HML source never supplied.",
            "`simplify` is required by the spec to record which identity was used. Lean "
            "tactics such as `simp` and `ring` close goals without returning a "
            "citable identity in the source text, so the record is not recoverable from "
            "the emitted file.",
            "`square_both_sides` records a weakening rather than an equivalence. Lean "
            "will state either direction faithfully, but nothing in the file marks that "
            "the step is one-way; the distinction lives in the HML layer.",
            "The operations are defined over ℝ in practice, so none of this is "
            "checkable here: Mathlib is absent.",
            "A Derivation is not an Entailment and there is no coercion. Lean's `calc` "
            "works over both equalities and implications with the same syntax, so the "
            "distinction is not carried by the target and must be preserved upstream.",
        ),
        evidence=EV_LEAN_DERIVATION,
    ),
    _s(
        Layer.TRANSFORMATION,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan is an executable modelling language, not an algebra system. It has no "
            "symbolic rewriting, no equation objects and no way to state a side "
            "condition such as `by != 0` other than a comment. " + _NO_STAN_PROPS + " "
            + _NO_STANC
        ),
    ),
    _s(
        Layer.TRANSFORMATION,
        Backend.SYMPY,
        Status.PARTIAL,
        losses=(
            "SymPy performs the operations and discharges none of the obligations. "
            "Probed directly: `sp.cancel((x*y)/x)` returns `y` with `x != 0` neither "
            "recorded nor checked, and `sp.simplify((x-x)/x)` returns `0` the same way. "
            "This is precisely the error the layer exists to catch, committed silently "
            "by the target.",
            "`simplify` does not report which identity it used: "
            "`sp.simplify(sin(x)**2 + cos(x)**2)` returns `1` with no citation, so the "
            "spec's checkability requirement cannot be met by reading SymPy's output.",
            "`sqrt_both_sides` needs a recorded case split on the sign branch; SymPy "
            "returns the principal branch and does not record the other.",
            "`square_both_sides` is a weakening, not an equivalence; SymPy has no "
            "marker for the direction, so a reader of the output cannot tell.",
            "`differentiate` and `integrate` are performed without establishing "
            "differentiability or integrability on the domain — SymPy will return an "
            "answer for expressions where the obligation fails.",
            "Contrast worth recording: Lean DEMANDS the same side conditions rather "
            "than discarding them. The two targets fail in opposite directions, and "
            "only one of the two failure directions is safe.",
        ),
        evidence=EV_SYMPY_DROPS_OBLIGATIONS,
    ),
    # =====================================================================
    # V1 layer 4b — inference edges (Entailment, Equivalence, Counterexample)
    # =====================================================================
    _s(
        Layer.INFERENCE,
        Backend.LEAN,
        Status.PARTIAL,
        losses=(
            "The `claimStatus` of an edge does not survive into the file. A `sorry`-"
            "closed theorem is textually indistinguishable from a proved one; the "
            "separation exists only in `#print axioms` output, which is not part of the "
            "artefact. Recorded as a loss because a reader of the emitted Lean cannot "
            "tell a conjecture from a theorem.",
            "A ConverseClaim must be stated without being asserted. That works — a "
            "Prop-valued `def` — but it looks nothing like the theorem beside it, so "
            "the relation between an Entailment and its converse is conventional rather "
            "than structural.",
            "The V0 backend states `require` obligations as theorems, and warns that "
            "read literally such a theorem may be false. Any inference edge routed "
            "through that path inherits the weakening.",
            "Everything ℝ-typed is uncheckable here; Mathlib is absent.",
        ),
        evidence=EV_LEAN_V1_LAYERS,
    ),
    _s(
        Layer.INFERENCE,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan has no propositions and no implication connective, so an Entailment "
            "has nothing to become. " + _NO_STAN_PROPS + " " + _NO_STANC
        ),
    ),
    _s(
        Layer.INFERENCE,
        Backend.SYMPY,
        Status.PARTIAL,
        losses=(
            "Propositional edges only. `sp.Implies(P, Q)` exists and does not license "
            "`sp.Implies(Q, P)`, which is the right behaviour — but SymPy has no "
            "quantifier (probed: no `ForAll`, no `Exists`), so any edge over a "
            "quantified proposition is dropped.",
            "There is no proof object and no inference-rule record. Modus ponens, "
            "contraposition, induction and case analysis are not represented; an edge "
            "arrives with its justification stripped.",
            "`sp.Eq` auto-evaluates: `sp.Eq(x+y, y+x)` is the bare bool `True`. An "
            "equivalence edge therefore collapses into a truth value with no status "
            "field, which is the Evidence/Proof conflation the epistemic layer forbids, "
            "reappearing in the target.",
            "A Counterexample is representable as a witness substitution, but nothing "
            "ties it to the proposition it refutes.",
        ),
        evidence=EV_SYMPY_DROPS_OBLIGATIONS,
    ),
    # =====================================================================
    # V1 layer 5 — epistemic status   (the hardest rows; see LEAN_EPISTEMIC)
    # =====================================================================
    _s(
        Layer.EPISTEMIC_STATUS,
        Backend.LEAN,
        Status.PARTIAL,
        losses=(
            "Five of the sixteen statuses have a Lean encoding that the kernel accepted "
            "here: proved, definitionally_true, disproved, conjectured (statable as a "
            "Prop, not assertable) and model_conditional. See LEAN_EPISTEMIC for the "
            "per-status table.",
            "Four are LIBRARY-GATED: almost_sure, converges_in_probability, "
            "asymptotically_equivalent and approximately_equal. Mathlib supplies the "
            "vocabulary; Mathlib is not installed here, so none was verified. "
            "`MeasureTheory.Measure` was probed and is an unknown identifier.",
            "with_high_probability is library-gated *and* underdetermined: the encoding "
            "depends on the asymptotic regime, and V1 carries the regime as an "
            "unstructured context string rather than a typed object, so there is no "
            "single target proposition to emit.",
            "Six have NO Lean encoding at any library level, because they are not "
            "propositions about mathematical objects: fail_to_reject, reject, "
            "estimated, consistent_with, possible and the `unsupported` status itself. "
            "Installing Mathlib does not change this and it must not be recorded as "
            "though it would.",
            "For fail_to_reject and reject the absence is not a gap to be closed but a "
            "requirement. Lean's `theorem` is a Proof claim, and the epistemic contract "
            "prohibits the Evidence-to-Proof coercion outright; emitting a theorem for "
            "a non-rejection would perform in the backend exactly the conflation the "
            "layer was built to prevent.",
            "No status marker survives into the file even for the five that work. The "
            "status must be carried by the HML side or by an out-of-band `#print "
            "axioms` audit.",
        ),
        evidence=EV_LEAN_EPISTEMIC,
    ),
    _s(
        Layer.EPISTEMIC_STATUS,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan has no propositions, so there is nothing for a status to qualify. "
            "Stan's `~` is a sampling statement, not a claim about the world, and it "
            "already loses the prior/likelihood/law role distinction in V0. The one "
            "superficially plausible mapping — a p-value or posterior probability to "
            "`real<lower=0, upper=1>` — is the PValue-to-posterior conflation the "
            "epistemic layer explicitly forbids, and Stan's type system could not tell "
            "the two apart. " + _NO_STANC
        ),
    ),
    _s(
        Layer.EPISTEMIC_STATUS,
        Backend.SYMPY,
        Status.UNSUPPORTED,
        reason=(
            "SymPy has no justification object of any kind. Probed: `sp.Eq(x+y, y+x)` "
            "auto-evaluates to the bare bool `True`, and `sp.Eq` has no `status` "
            "attribute — so proved, conjectured, estimated and fail_to_reject all "
            "arrive at the same representation, a truth value or an unevaluated "
            "relational object. That is the collapse the layer exists to prevent, so "
            "the honest verdict is unsupported rather than partial: a target that "
            "represents every status identically represents none of them."
        ),
    ),
    # =====================================================================
    # V1 layer 6 — discourse state (Goal, Discharge, Case)
    # =====================================================================
    _s(
        Layer.DISCOURSE_STATE,
        Backend.LEAN,
        Status.PARTIAL,
        losses=(
            "A Goal states cleanly as a Prop-valued `def` and a Discharge as a proof "
            "term of that Prop; both were kernel-accepted here over ℕ. But a Goal is "
            "not a Theorem and Lean has one keyword for both, so the intent/claim "
            "distinction the layer insists on is not carried by the target.",
            "The open-goal SET — the layer's actual product, reported at end of module "
            "— has no representation in the file. An undischarged goal is simply a "
            "`def` nobody proved; nothing marks it as outstanding and Lean will not "
            "report it. `sorry` would make it visible as a warning, but `sorry` also "
            "makes false theorems compile, so it cannot serve as the marker.",
            "Case / Otherwise / EndCase map onto `rcases` or `by_cases` inside a proof, "
            "not onto module-level structure, and the exhaustiveness check the layer "
            "performs is Lean's own — a different check, made at a different time.",
            "Discharging a goal with Evidence or Assumption must be a type error. Lean "
            "gets this right for Assumption (a hypothesis stays in the type) but has no "
            "Evidence category at all, so that half of the rule has nothing to bite on.",
            "V0 already measured that Lean's single `variable` mechanism loses the "
            "var/param/const/obs/index distinction. Discourse state is a strictly finer "
            "distinction than that one, which is direct evidence it will not survive.",
        ),
        evidence=EV_LEAN_V1_LAYERS,
    ),
    _s(
        Layer.DISCOURSE_STATE,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan's program structure is a fixed sequence of blocks, not a discourse. "
            "It was already measured to destroy interleaved declaration order, changing "
            "the content hash — so it does not even preserve the ordering V0 relies on, "
            "let alone track what remains to be shown. There are no propositions for a "
            "Goal to range over. " + _NO_STANC
        ),
    ),
    _s(
        Layer.DISCOURSE_STATE,
        Backend.SYMPY,
        Status.UNSUPPORTED,
        reason=(
            "A Python module namespace has no notion of an open obligation. The V0 "
            "SymPy backend collects claims into a `claims` list, which is a container, "
            "not a state: nothing distinguishes a discharged goal from an open one, and "
            "nothing reports the open set. Discharging by Evidence versus by Proof "
            "cannot be a type error because there are no such types."
        ),
    ),
    # =====================================================================
    # V0 constructs, carried over from the measured findings
    # =====================================================================
    _s(
        Layer.V0_DECLARATION_KIND,
        Backend.LEAN,
        Status.PARTIAL,
        losses=(
            "The declaration itself survives; the kind does not. Lean's `variable` is a "
            "single mechanism, so whether a symbol is observed data, a parameter to be "
            "inferred, or a fixed constant is lost. Stated as a limitation by the V0 "
            "backend itself.",
        ),
        evidence=EV_LEAN_V0_OUTPUT_REJECTED,
    ),
    _s(
        Layer.V0_DECLARATION_KIND,
        Backend.STAN,
        Status.PARTIAL,
        losses=(
            "`obs` and `param` survive as the `data` and `parameters` blocks, which is "
            "more than Lean keeps.",
            "`const`, `index` and `rv` have no distinct Stan form.",
            "The block grouping is itself destructive: it reorders declarations, and "
            "since HML declaration ordinals are positional the content hash changes.",
        ),
    ),
    _s(
        Layer.V0_DECLARATION_KIND,
        Backend.SYMPY,
        Status.PARTIAL,
        losses=(
            "Every kind becomes a `sympy.Symbol`. The V0 backend reports directly that "
            "SymPy has no notion of an observed or constant binding.",
        ),
        evidence=EV_SYMPY_EXECUTES,
    ),
    _s(
        Layer.V0_REFINEMENT_SCALAR,
        Backend.LEAN,
        Status.PARTIAL,
        losses=(
            "Refinements become a carrier type plus a separate hypothesis, not a "
            "subtype. A hypothesis is not part of the type, so nothing in Lean stops a "
            "later edit from using the symbol with the hypothesis out of scope — which "
            "HML's type system would. Declared as a weakening by the V0 backend.",
            "Every refined real scalar maps to ℝ, which is a Mathlib type, so none of "
            "this is checkable on this machine.",
        ),
        evidence=EV_LEAN_V0_OUTPUT_REJECTED,
    ),
    _s(
        Layer.V0_REFINEMENT_SCALAR,
        Backend.STAN,
        Status.PARTIAL,
        losses=(
            "PositiveReal CANNOT be expressed. Stan's `real<lower=0>` is a closed lower "
            "bound and admits 0; HML's PositiveReal excludes it. The V0 importer widens "
            "to NonNegativeReal on the way back and the reconstructed program is then "
            "correctly REJECTED with HML-T413, because a scale must be strictly "
            "positive. This is the single largest limitation in the table: every family "
            "with a PositiveReal role — Normal, Beta, Gamma, Exponential, Poisson, "
            "Cauchy and most others — is outside the round-trippable subset. Only "
            "Uniform, Binomial and Bernoulli survive.",
            "NonNegativeReal and Probability do map, to `real<lower=0>` and "
            "`real<lower=0, upper=1>`.",
            "Rationals have no Stan type.",
        ),
    ),
    _s(
        Layer.V0_REFINEMENT_SCALAR,
        Backend.SYMPY,
        Status.PARTIAL,
        losses=(
            "Probability loses its upper bound: SymPy assumptions cannot express "
            "`x <= 1`, so the lower half becomes an assumption and the upper half is "
            "demoted to an entry in `type_constraints`. Reported as a weakening by the "
            "V0 backend.",
            "Worth recording as a contrast rather than a loss: SymPy CAN express strict "
            "positivity, as `positive=True`. It is the one target here that does not "
            "hit the PositiveReal wall Stan hits.",
        ),
        evidence=EV_SYMPY_EXECUTES,
    ),
    _s(
        Layer.V0_QUANTITY_DIMENSION,
        Backend.LEAN,
        Status.UNSUPPORTED,
        reason=(
            "Lean has no dimensional analysis without a units library and a chosen unit "
            "per base dimension; HML dimensions are unit-free rational-exponent "
            "vectors. The quantity becomes its bare carrier type, so dimensionally "
            "invalid Lean expressions become well-typed — dropped, and the V0 backend "
            "says so."
        ),
    ),
    _s(
        Layer.V0_QUANTITY_DIMENSION,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan is dimensionless. `Quantity[D]` becomes `real` and the dimension "
            "vector is gone entirely. " + _NO_STANC
        ),
    ),
    _s(
        Layer.V0_QUANTITY_DIMENSION,
        Backend.SYMPY,
        Status.UNSUPPORTED,
        reason=(
            "`sympy.physics.units` exists, but the V0 design freeze §8 says v0 does not "
            "reconcile units and HML's Dimension carries no unit. Mapping one onto the "
            "other would mean inventing a unit per dimension, so it is dropped."
        ),
    ),
    _s(
        Layer.V0_PROBABILITY_LAW,
        Backend.LEAN,
        Status.UNSUPPORTED,
        reason=(
            "Dropped, and this is the most dangerous loss in the whole table. A law "
            "needs a measurable space on the family's support, a MeasureTheory.Measure, "
            "a density and a proof it integrates to one — none of which is determined "
            "by a family name plus role labels. What makes it dangerous is measured: "
            "the importer cannot know a law was ever there, the reconstruction compiles "
            "perfectly happily, and ONLY the content-hash comparison reveals that "
            "meaning went missing. A one-way test cannot detect this class of loss at "
            "all."
        ),
    ),
    _s(
        Layer.V0_PROBABILITY_LAW,
        Backend.STAN,
        Status.PARTIAL,
        losses=(
            "The sampling statement survives as `~`, and the role-to-position mapping "
            "is round-trip tested in both directions — a silent scale/variance swap is "
            "the failure this guards against.",
            "The role is lost: `prior`, `likelihood` and `law` all become `~`.",
            "Most families cannot round-trip at all, because their role types include "
            "PositiveReal. Only Uniform, Binomial and Bernoulli qualify.",
            "`HalfNormal` has no Stan density and is realised as `normal(0, scale)` "
            "with the truncation living in the declaration; if the declared type "
            "induces no lower bound the emitted model is a full normal.",
        ),
    ),
    _s(
        Layer.V0_PROBABILITY_LAW,
        Backend.SYMPY,
        Status.UNSUPPORTED,
        reason=(
            "Dropped deliberately. `sympy.stats` has Normal, Beta and Binomial, but no "
            "representation of the prior/likelihood/law role, no conditioning set and "
            "no inference query. Emitting `sympy.stats.Normal(...)` would reproduce one "
            "third of a law statement and silently discard the rest while looking "
            "complete — the V0 backend's stated reason for refusing. Note that the "
            "generated module still executes cleanly with the law dropped, which is "
            "why execution is never treated as verification."
        ),
    ),
    _s(
        Layer.V0_CONDITIONING_SET,
        Backend.LEAN,
        Status.UNSUPPORTED,
        reason=(
            "There is no law to condition: laws are dropped wholesale, so the "
            "conditioning set has nothing to attach to."
        ),
    ),
    _s(
        Layer.V0_CONDITIONING_SET,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan's sampling statement carries no conditioning set. `y | x beta sigma` "
            "and `y` produce the same `~` line, so the dependency structure is not "
            "recoverable from the emitted program. " + _NO_STANC
        ),
    ),
    _s(
        Layer.V0_CONDITIONING_SET,
        Backend.SYMPY,
        Status.UNSUPPORTED,
        reason=(
            "SymPy has no probability-law object that carries a conditioning set; the "
            "V0 backend names this explicitly among its reasons for dropping laws."
        ),
    ),
    _s(
        Layer.V0_INFERENCE_QUERY,
        Backend.LEAN,
        Status.UNSUPPORTED,
        reason=(
            "An inference query presupposes the probability laws, which were already "
            "dropped, so there is nothing left to state."
        ),
    ),
    _s(
        Layer.V0_INFERENCE_QUERY,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan's program defines a posterior implicitly; there is no statement form "
            "for `infer posterior theta`, and which quantity is being asked for is not "
            "recoverable from the emitted code. " + _NO_STANC
        ),
    ),
    _s(
        Layer.V0_INFERENCE_QUERY,
        Backend.SYMPY,
        Status.UNSUPPORTED,
        reason=(
            "SymPy has no inference engine. `sympy.stats` can compute an expectation "
            "for a random symbol it constructed itself, but the V0 backend does not "
            "construct one, so there is nothing to query."
        ),
    ),
    _s(
        Layer.V0_QUANTIFIER,
        Backend.LEAN,
        Status.SUPPORTED,
        evidence=EV_LEAN_QUANTIFIER_SCOPE,
    ),
    _s(
        Layer.V0_QUANTIFIER,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan has no quantifiers. A `forall`/`exists` statement is emitted as a "
            "comment and reported as dropped. " + _NO_STANC
        ),
    ),
    _s(
        Layer.V0_QUANTIFIER,
        Backend.SYMPY,
        Status.UNSUPPORTED,
        reason=(
            "SymPy has no first-order quantifier — probed directly: neither `ForAll` "
            "nor `Exists` exists. `sympy.Q` is an assumptions predicate system, not a "
            "binder, so there is no sound encoding of "
            "`forall x : Real . exists y : Real . y > x`. Dropped."
        ),
    ),
    _s(
        Layer.V0_PROPOSITION,
        Backend.LEAN,
        Status.PARTIAL,
        losses=(
            "`prove` is faithful: the statement is preserved exactly and closed with "
            "`sorry`, which proves nothing and is declared as such.",
            "`require` is WEAKENED, and the V0 backend states the danger plainly: an "
            "HML `require` is a constraint over free variables, Lean has no such "
            "statement form, so it is emitted as a theorem. Read literally that theorem "
            "may be false — `require x >= 0` for a free real x is — and no Lean reader "
            "can recover from the skeleton that it was a constraint rather than a claim.",
            "`assume` becomes a propositional `variable`, which the V0 backend notes "
            "may need an explicit `include` depending on the Lean version.",
        ),
        evidence=EV_LEAN_V0_OUTPUT_REJECTED,
    ),
    _s(
        Layer.V0_PROPOSITION,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=_NO_STAN_PROPS + " " + _NO_STANC,
    ),
    _s(
        Layer.V0_PROPOSITION,
        Backend.SYMPY,
        Status.PARTIAL,
        losses=(
            "Unquantified propositions survive as relational objects in `requirements`, "
            "`claims` and `assumptions`.",
            "Quantified propositions are dropped: SymPy has no binder.",
            "No proof, no obligation and no status. A claim and a requirement differ "
            "only by which list they land in.",
            "`prove <name>` where <name> was a dropped quantified definition emits a "
            "reference to a name the module never binds; the file then raises "
            "NameError on import. See the v0_definition/sympy row.",
        ),
        evidence=EV_SYMPY_EXECUTES,
    ),
    _s(
        Layer.V0_OBJECTIVE,
        Backend.LEAN,
        Status.UNSUPPORTED,
        reason=(
            "Mathlib can state `IsMinOn f s a`, but only relative to a set `s` and a "
            "witness `a`, neither of which the HML statement supplies. Inventing them "
            "would state a different theorem, so the objective is dropped."
        ),
    ),
    _s(
        Layer.V0_OBJECTIVE,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan is a probabilistic modelling language with no optimisation objective "
            "in the program text; `minimise` / `maximise` have no Stan form. "
            + _NO_STANC
        ),
    ),
    _s(
        Layer.V0_OBJECTIVE,
        Backend.SYMPY,
        Status.PARTIAL,
        losses=(
            "The expression is recorded in the generated module's `objective` name, so "
            "the target of the optimisation survives.",
            "The direction is recorded only by that convention, and no feasible set, no "
            "optimiser and no solution is produced. Nothing checks that the objective is "
            "attainable.",
        ),
        evidence=EV_SYMPY_EXECUTES,
    ),
    _s(
        Layer.V0_SOLVE,
        Backend.LEAN,
        Status.UNSUPPORTED,
        reason=(
            "Lean has no solve statement. The closest faithful form is an existence "
            "theorem, but which existential to state is not determined by `solve` "
            "alone, so it is dropped rather than guessed."
        ),
    ),
    _s(
        Layer.V0_SOLVE,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan samples; it does not solve. There is no statement form for `solve x y`. "
            + _NO_STANC
        ),
    ),
    _s(
        Layer.V0_SOLVE,
        Backend.SYMPY,
        Status.PARTIAL,
        losses=(
            "The targets survive in the generated module's `solve_targets` name.",
            "No solving is performed and no solution set is produced; the constraints "
            "and the targets are simply placed side by side for a caller to use.",
        ),
        evidence=EV_SYMPY_EXECUTES,
    ),
    _s(
        Layer.V0_CHECK_DIMENSION,
        Backend.LEAN,
        Status.UNSUPPORTED,
        reason=(
            "No Lean encoding without a units library and a chosen unit per base "
            "dimension, which v0 does not have (design freeze §8). Dropped."
        ),
    ),
    _s(
        Layer.V0_CHECK_DIMENSION,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "`check dimension` has no Stan encoding at all — Stan is dimensionless. "
            + _NO_STANC
        ),
    ),
    _s(
        Layer.V0_CHECK_DIMENSION,
        Backend.SYMPY,
        Status.UNSUPPORTED,
        reason=(
            "Dropped for the same reason as Quantity: HML's Dimension has no unit and "
            "`sympy.physics.units` requires one."
        ),
    ),
    _s(
        Layer.V0_CONCEPT_DECL,
        Backend.LEAN,
        Status.PARTIAL,
        losses=(
            "Scope is flattened by prefixing members with `Concept_`; the concept is "
            "not a Lean object and its members are only conventionally related. The "
            "faithful encoding — a structure or class — would turn every member into a "
            "field access and every invariant into a field of a proposition-carrying "
            "structure.",
            "`extends` is dropped, together with everything the parents contribute.",
            "`example` and `counterexample` members are dropped: stating them needs an "
            "existential over the concept as an object, and there is no object.",
            "Invariants become free-standing theorems with nothing tying them back to "
            "the concept.",
        ),
        evidence=EV_LEAN_V0_OUTPUT_REJECTED,
    ),
    _s(
        Layer.V0_CONCEPT_DECL,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan has no user-defined types and no namespaces; a concept has nothing to "
            "become. " + _NO_STANC
        ),
    ),
    _s(
        Layer.V0_CONCEPT_DECL,
        Backend.SYMPY,
        Status.PARTIAL,
        losses=(
            "Members are name-mangled to `Concept__member` because SymPy has no symbol "
            "namespace. The mangling is injective, so nothing collides, but the concept "
            "is not an object and its scope is gone.",
            "Invariants become expression objects with no binding to the concept.",
        ),
        evidence=EV_SYMPY_EXECUTES,
    ),
    _s(
        Layer.V0_VECTOR_MATRIX,
        Backend.LEAN,
        Status.PARTIAL,
        losses=(
            "`Vector[T, n]` becomes `Fin n -> T` and `Matrix[T, m, n]` becomes Mathlib's "
            "`Matrix (Fin m) (Fin n) T`.",
            "This MANUFACTURES obligations the source never had: Lean's `Fin` carries a "
            "bounds proof, so every subscript in the translated code acquires a proof "
            "obligation, whereas HML v0 checks shapes nominally. The two agree on the "
            "current examples but not in general. A translation that adds obligations "
            "is a distinct failure mode from one that drops them, and is recorded as "
            "such.",
            "A vector or matrix of unknown extent has no `Fin` index type and is "
            "dropped entirely.",
            "Mathlib's `Matrix` is unavailable here, so none of it compiles.",
        ),
        evidence=EV_LEAN_V0_OUTPUT_REJECTED,
    ),
    _s(
        Layer.V0_VECTOR_MATRIX,
        Backend.STAN,
        Status.PARTIAL,
        losses=(
            "`vector[n]` and `matrix[m, n]` exist and the shapes survive.",
            "Element refinements do not: Stan bounds apply to the declaration as a "
            "whole and there is no dimension information, since Stan is dimensionless.",
        ),
    ),
    _s(
        Layer.V0_VECTOR_MATRIX,
        Backend.SYMPY,
        Status.PARTIAL,
        losses=(
            "A vector becomes `sympy.MatrixSymbol(name, n, 1)` — a column-matrix "
            "approximation rather than a vector, as the V0 backend states.",
            "`MatrixSymbol` carries no element assumptions, so a refined element type "
            "such as Probability loses its refinement entirely.",
            "Subscripts are 0-based in SymPy and require an integer index.",
            "Unknown extents have no `MatrixSymbol` shape and are dropped.",
        ),
        evidence=EV_SYMPY_EXECUTES,
    ),
    _s(
        Layer.V0_DEFINITION,
        Backend.LEAN,
        Status.PARTIAL,
        losses=(
            "`define` maps well to Lean's `def`, which is the closest correspondence in "
            "the table.",
            "A parameter with no declared HML type is approximated as ℝ, because Lean "
            "requires one; any intended refinement is lost.",
            "If the definition's HML type has no Lean encoding the ascription is "
            "omitted and Lean must infer it.",
        ),
        evidence=EV_LEAN_V1_LAYERS,
    ),
    _s(
        Layer.V0_DEFINITION,
        Backend.STAN,
        Status.PARTIAL,
        losses=(
            "A definition can become a transformed-parameter assignment or a `functions` "
            "block entry.",
            "The V0 Stan importer rejects both `transformed parameters` and `functions` "
            "as outside its declared subset, so a definition emitted this way cannot "
            "come back — the route is one-way.",
        ),
    ),
    _s(
        Layer.V0_DEFINITION,
        Backend.SYMPY,
        Status.PARTIAL,
        losses=(
            "Definitions survive as entries in the generated module's `definitions` "
            "name, which is the strongest correspondence SymPy offers.",
            "Numeric literals become `sympy.Rational` rather than `Float`, preserving "
            "the source value exactly; recorded as a note by the V0 backend, not a loss.",
            "There is no parameter typing: a definition's parameters become bare "
            "symbols and any refinement is gone.",
            "MEASURED DEFECT: a `define` whose type is Proposition and whose body is a "
            "quantifier is dropped (correctly — SymPy has no binder), but a later "
            "reference to it is still emitted, so the generated module raises "
            "NameError on import. Found by executing the output, not by reading it. "
            "Reported, not fixed: V0 is frozen.",
        ),
        evidence=EV_SYMPY_EXECUTES,
    ),
    _s(
        Layer.V0_OBSERVED_VALUE,
        Backend.LEAN,
        Status.PARTIAL,
        losses=(
            "The value survives: `obs k : Natural = 7` becomes `def k : ℕ := 7`, which "
            "is more faithful than a variable plus an equation would be.",
            "That the binding was *observed* does not survive, because the declaration "
            "kind is lost.",
        ),
        evidence=EV_LEAN_V0_OUTPUT_REJECTED,
    ),
    _s(
        Layer.V0_OBSERVED_VALUE,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan reads data from a data file, not from the program text, so an "
            "observed value has nowhere to live in the emitted code. Measured directly: "
            "the backend honestly records `n = 20` in a comment header, but a comment "
            "is not code, the importer cannot recover it, and the round trip fails on a "
            "changed content hash. Observed values are outside the round-trippable "
            "subset. " + _NO_STANC
        ),
    ),
    _s(
        Layer.V0_OBSERVED_VALUE,
        Backend.SYMPY,
        Status.PARTIAL,
        losses=(
            "The value is preserved, recorded as an equation in `requirements`.",
            "SymPy has no notion of an observed or constant binding, so the value "
            "becomes a constraint indistinguishable from any other — declared as a "
            "weakening by the V0 backend.",
        ),
        evidence=EV_SYMPY_EXECUTES,
    ),
    _s(
        Layer.V0_DECLARATION_ORDER,
        Backend.LEAN,
        Status.SUPPORTED,
        evidence=EV_LEAN_V0_OUTPUT_REJECTED,
    ),
    _s(
        Layer.V0_DECLARATION_ORDER,
        Backend.STAN,
        Status.UNSUPPORTED,
        reason=(
            "Stan groups declarations into `data` and `parameters` blocks. HML "
            "declaration ordinals are positional, so a module whose observations and "
            "parameters are interleaved comes back reordered and its content hash "
            "changes. Measured directly. The meaning is arguably unaltered; the "
            "identity is not, and neither fact is normalised away. " + _NO_STANC
        ),
    ),
    _s(
        Layer.V0_DECLARATION_ORDER,
        Backend.SYMPY,
        Status.SUPPORTED,
        evidence=EV_SYMPY_EXECUTES,
    ),
)

#: The table, keyed for lookup. Every (layer, backend) pair must be present.
SUPPORT: dict[tuple[Layer, Backend], Support] = {
    (s.layer, s.backend): s for s in _SUPPORT_LIST
}


# ---------------------------------------------------------------------------
# Per-status Lean expressibility — the hardest rows in the deliverable
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LeanEncoding:
    """Whether one epistemic status has a Lean encoding, and if not, why not.

    ``obstacle`` carries the distinction that matters: a library-gated status becomes
    expressible when Mathlib is installed, a category-mismatched one never does. No
    encoding is invented for anything marked not expressible.
    """

    status: EpistemicStatus
    expressible: bool
    encoding: str
    obstacle: Obstacle
    note: str
    #: Whether an encoding of this status was compiled by Lean during Phase 8.
    kernel_checked: bool = False

    def __post_init__(self) -> None:
        if self.expressible and not self.encoding.strip():
            raise ValueError(f"{self.status}: expressible but no encoding given")
        if not self.expressible and self.obstacle is Obstacle.NONE:
            raise ValueError(f"{self.status}: not expressible but no obstacle recorded")
        if not self.expressible and self.encoding.strip():
            raise ValueError(
                f"{self.status}: an encoding is recorded for a status marked not "
                "expressible; inventing encodings is exactly what this table forbids"
            )
        if self.kernel_checked and not self.expressible:
            raise ValueError(f"{self.status}: cannot have been kernel-checked")
        if not self.note.strip():
            raise ValueError(f"{self.status}: every row must carry its reasoning")


LEAN_EPISTEMIC: dict[EpistemicStatus, LeanEncoding] = {
    # -- expressible, and compiled here ----------------------------------
    EpistemicStatus.PROVED: LeanEncoding(
        status=EpistemicStatus.PROVED,
        expressible=True,
        encoding="theorem <name> : <P> := <proof term>",
        obstacle=Obstacle.NONE,
        note=(
            "The one exact correspondence. Lean's `theorem` IS a proof claim, and "
            "`#print axioms` confirms the proof is real: the probe's `status_proved` "
            "depends on no axioms at all. Caveat that must travel with this row: a "
            "`sorry`-closed theorem is textually identical and also exits 0."
        ),
        kernel_checked=True,
    ),
    EpistemicStatus.DEFINITIONALLY_TRUE: LeanEncoding(
        status=EpistemicStatus.DEFINITIONALLY_TRUE,
        expressible=True,
        encoding="def <name> : T := <body>;  theorem <name>_def : <name> = <body> := rfl",
        obstacle=Obstacle.NONE,
        note=(
            "`rfl` is definitional equality, which is precisely what the status "
            "asserts. Closer than any other row in the table."
        ),
        kernel_checked=True,
    ),
    EpistemicStatus.DISPROVED: LeanEncoding(
        status=EpistemicStatus.DISPROVED,
        expressible=True,
        encoding="theorem <name> : ¬ <P> := <proof term>",
        obstacle=Obstacle.NONE,
        note=(
            "A refutation is a proof of a negation, and Justification.REFUTATION "
            "discharges goals in HML for the same reason. The probe's "
            "`status_disproved` depends on [propext, Quot.sound] — standard, sound, and "
            "notably NOT `sorryAx`."
        ),
        kernel_checked=True,
    ),
    EpistemicStatus.CONJECTURED: LeanEncoding(
        status=EpistemicStatus.CONJECTURED,
        expressible=True,
        encoding="def <name> : Prop := <P>        -- stated, never asserted",
        obstacle=Obstacle.NONE,
        note=(
            "Statable but not assertable, which is exactly right: Justification.NONE "
            "discharges nothing. The Prop-valued `def` introduces the proposition "
            "without claiming it. The weakness is presentational — a reader must notice "
            "that no theorem proves it, and Lean will not point that out."
        ),
        kernel_checked=True,
    ),
    EpistemicStatus.MODEL_CONDITIONAL: LeanEncoding(
        status=EpistemicStatus.MODEL_CONDITIONAL,
        expressible=True,
        encoding="theorem <name> (h_model : <M>) : <P> := <proof term>",
        obstacle=Obstacle.NONE,
        note=(
            "The model becomes a hypothesis carried in the type, so it propagates as a "
            "dependency exactly as REQUIRED_CONTEXT demands — Lean will not let the "
            "conclusion be used without it. One of the better correspondences here."
        ),
        kernel_checked=True,
    ),
    # -- library-gated: Mathlib has the vocabulary, this machine does not --
    EpistemicStatus.ALMOST_SURE: LeanEncoding(
        status=EpistemicStatus.ALMOST_SURE,
        expressible=False,
        encoding="",
        obstacle=Obstacle.LIBRARY_GATED,
        note=(
            "Mathlib expresses this as `∀ᵐ x ∂μ, P x`, and REQUIRED_CONTEXT already "
            "demands the measure the encoding needs. Not expressible HERE: probed "
            "directly, `MeasureTheory.Measure` is an unknown identifier in core Lean. "
            "Installing Mathlib would move this row to partial. Not claimed as "
            "supported, because nothing was compiled."
        ),
    ),
    EpistemicStatus.CONVERGES_IN_PROBABILITY: LeanEncoding(
        status=EpistemicStatus.CONVERGES_IN_PROBABILITY,
        expressible=False,
        encoding="",
        obstacle=Obstacle.LIBRARY_GATED,
        note=(
            "Mathlib has `MeasureTheory.TendstoInMeasure`, and REQUIRED_CONTEXT supplies "
            "the sequence and the limit. Core Lean has neither filters over measures nor "
            "measures. Same verdict as almost_sure: gated, not impossible."
        ),
    ),
    EpistemicStatus.ASYMPTOTICALLY_EQUIVALENT: LeanEncoding(
        status=EpistemicStatus.ASYMPTOTICALLY_EQUIVALENT,
        expressible=False,
        encoding="",
        obstacle=Obstacle.LIBRARY_GATED,
        note=(
            "Mathlib's `Asymptotics.IsEquivalent` is stated along a filter, and the "
            "status's mandatory `regime` context is what picks the filter. Needs "
            "Mathlib for both the filter library and ℝ."
        ),
    ),
    EpistemicStatus.APPROXIMATELY_EQUAL: LeanEncoding(
        status=EpistemicStatus.APPROXIMATELY_EQUAL,
        expressible=False,
        encoding="",
        obstacle=Obstacle.LIBRARY_GATED,
        note=(
            "With the mandatory `tolerance` context this is `|a - b| ≤ ε`, an ordinary "
            "Mathlib proposition. Core Lean has no ℝ and no `abs` on it. Gated. Note "
            "the tolerance is what makes it a mathematical statement at all — which is "
            "why REQUIRED_CONTEXT demands one."
        ),
    ),
    EpistemicStatus.WITH_HIGH_PROBABILITY: LeanEncoding(
        status=EpistemicStatus.WITH_HIGH_PROBABILITY,
        expressible=False,
        encoding="",
        obstacle=Obstacle.LIBRARY_GATED,
        note=(
            "Doubly blocked. Mathlib could state a specific instance — a bound of the "
            "form `μ_n {ω | P_n ω} ≥ 1 - δ(n)` with `δ(n) → 0` — but WHICH proposition "
            "that is depends entirely on the asymptotic regime, and V1 carries the "
            "regime as an unstructured `bound_or_regime` context string rather than a "
            "typed object. So even with Mathlib installed there is no determinate "
            "target to emit. The spec is right that a regime is mandatory; until it is "
            "typed, no encoding can be generated, and none is invented here."
        ),
    ),
    # -- category mismatch: no library fixes these ------------------------
    EpistemicStatus.FAIL_TO_REJECT: LeanEncoding(
        status=EpistemicStatus.FAIL_TO_REJECT,
        expressible=False,
        encoding="",
        obstacle=Obstacle.CATEGORY_MISMATCH,
        note=(
            "The sharpest row in the table, and the one where absence is a REQUIREMENT "
            "rather than a gap. `fail_to_reject` records the output of a decision "
            "procedure applied to a sample; it asserts nothing about the world — that "
            "is the entire point of the layer, which renders it as 'This is not "
            "evidence that H0 is true'. Any Lean encoding must be a `theorem`, and a "
            "`theorem` is a Proof claim; PROHIBITED_COERCIONS forbids Evidence to Proof "
            "precisely so that failing to reject H0 cannot become proving H0. Emitting "
            "a theorem here would perform in the backend the exact conflation the layer "
            "was built to prevent. Mathlib does not change this and no encoding is "
            "offered."
        ),
    ),
    EpistemicStatus.REJECT: LeanEncoding(
        status=EpistemicStatus.REJECT,
        expressible=False,
        encoding="",
        obstacle=Obstacle.CATEGORY_MISMATCH,
        note=(
            "Symmetric to fail_to_reject. Rejecting at a significance level is not a "
            "disproof — PROHIBITED_COERCIONS blocks Evidence to Refutation for exactly "
            "this reason — so `theorem : ¬ H0` is the wrong statement, not a rough one."
        ),
    ),
    EpistemicStatus.ESTIMATED: LeanEncoding(
        status=EpistemicStatus.ESTIMATED,
        expressible=False,
        encoding="",
        obstacle=Obstacle.CATEGORY_MISMATCH,
        note=(
            "Rests on Evidence with an estimator and a sample. Lean can certainly "
            "formalise an estimator as a function and prove things about it — but the "
            "status attaches to a VALUE obtained from one sample, and there is no "
            "proposition whose truth is 'this number was estimated from that data'. "
            "Formalising the sample as a term would make the claim be about the "
            "formalisation. The concept-family spec makes the same point from the other "
            "side: 'the estimate is unbiased' is a type error, because unbiasedness is "
            "a property of the estimator, not of a number."
        ),
    ),
    EpistemicStatus.CONSISTENT_WITH: LeanEncoding(
        status=EpistemicStatus.CONSISTENT_WITH,
        expressible=False,
        encoding="",
        obstacle=Obstacle.CATEGORY_MISMATCH,
        note=(
            "'The data are consistent with H' is compatibility, and the layer says "
            "outright that compatibility is not support. Consistency in Lean's sense is "
            "a metatheoretic property — no contradiction is derivable — which a theory "
            "cannot state about itself, and which is a different claim from the "
            "statistical one anyway. Any Lean rendering would be either vacuous or a "
            "substitution of a different proposition."
        ),
    ),
    EpistemicStatus.POSSIBLE: LeanEncoding(
        status=EpistemicStatus.POSSIBLE,
        expressible=False,
        encoding="",
        obstacle=Obstacle.CATEGORY_MISMATCH,
        note=(
            "Justification.CREDENCE: a degree of belief ABOUT a model, not a "
            "proposition WITHIN one. Lean's Prop universe has no modal operator and "
            "PROHIBITED_COERCIONS blocks Credence to Proof. `∃ ...` would be a "
            "different, much stronger claim."
        ),
    ),
    EpistemicStatus.UNSUPPORTED: LeanEncoding(
        status=EpistemicStatus.UNSUPPORTED,
        expressible=False,
        encoding="",
        obstacle=Obstacle.CATEGORY_MISMATCH,
        note=(
            "Asserts the ABSENCE of grounds for P. That is a statement about the "
            "epistemic record, not about P: `¬ P` is a different and much stronger "
            "claim (that is DISPROVED), and silence in a Lean file is not an assertion "
            "of anything. Nothing in Lean says 'no grounds have been offered'."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Public accessors
# ---------------------------------------------------------------------------


def entry(layer: Layer, backend: Backend) -> Support:
    """The full support record for one cell. Raises if the cell is missing.

    Raising rather than defaulting is deliberate: a missing cell is an unanswered
    question, and returning a default would answer it.
    """
    try:
        key = (Layer(layer), Backend(backend))
    except ValueError:
        # An unknown layer or backend name is a lookup failure like any other, and is
        # reported as one rather than leaking the enum's own ValueError.
        raise KeyError(
            f"unknown layer={layer!r} or backend={backend!r}; "
            f"layers are {[m.value for m in Layer]}"
        ) from None
    try:
        return SUPPORT[key]
    except KeyError:
        raise KeyError(
            f"no support entry recorded for layer={layer!r} backend={backend!r}; "
            "the matrix is incomplete and must not be guessed at"
        ) from None


def supported(layer: Layer, backend: Backend) -> tuple[Status, tuple[str, ...]]:
    """The status and declared losses for one cell.

    This is the accessor the registry populator and the CLI use.
    """
    e = entry(layer, backend)
    return e.status, e.losses


def registry_backend_support(layer: Layer) -> dict[str, dict[str, object]]:
    """Build the ``backend_support`` block for ``spec/concept_registry.schema.json``.

    Emits one entry per backend, always — the schema says absence means unsupported and
    never 'assumed fine', but an explicit entry with a stated reason is strictly more
    informative than an absence. For an unsupported cell the reason is carried into
    ``losses`` so that no information is dropped on the way into the registry.
    """
    block: dict[str, dict[str, object]] = {}
    for backend in Backend:
        e = entry(layer, backend)
        losses = list(e.losses)
        if e.status is Status.UNSUPPORTED and e.reason:
            losses = [f"unsupported: {e.reason}"]
        block[str(backend.value)] = {
            "supported": e.status is not Status.UNSUPPORTED,
            "losses": losses,
            "verified_by_toolchain": e.verified_by_toolchain,
        }
    return block


def unverified() -> tuple[Support, ...]:
    """Every cell for which no toolchain acceptance was obtained.

    Most of the table. Kept as a first-class query so a report cannot quietly present
    the verified minority as though it were the whole.
    """
    return tuple(s for s in _SUPPORT_LIST if not s.verified_by_toolchain)
