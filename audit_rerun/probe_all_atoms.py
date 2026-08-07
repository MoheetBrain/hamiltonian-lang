"""One executed probe for EVERY atom in MATHEMATICAL_REASONING_ONTOLOGY_V1 (486 atoms).

Why this file exists
--------------------
`probe_critical_atoms.py` probes the 64 CRITICAL atoms and `probe_composition.py` probes
14 more. That is 78 of 486. The remaining 408 were never given an executable state: they
were recorded `?`, and `docs/hml_v2/AUDIT_RERUN.md` is careful to say that every published
percentage is *over probed atoms only*. This file closes that hole. Every atom gets an
explicit, executed state or an explicit `NOT_MEASURED` with a reason.

Relationship to the existing tooling
------------------------------------
The compile-and-record idiom is `tools/hml_probe.py`'s: build an HML source string, call
``compile_source``, and read the real result. The pass/fail convention is the same one
(``accept`` = must compile clean, ``reject`` = must produce an error). What is new is the
*state vocabulary*, which is richer than PASS/FAIL because the question here is not "did
this probe pass" but "what is HML's relationship to this piece of mathematics".

The five states
---------------
PASS          representable AND enforced -- the compiler accepts a faithful encoding and
              REJECTS the corresponding misuse. Acceptance alone is never PASS.
PARTIAL       representable but incompletely enforced (the misuse compiles clean), or
              representable only in a restricted position.
BACKEND_ONLY  expressible only by lowering to a backend; not a first-class HML semantic.
LOSSY         the faithful spelling is refused, but a weakened encoding compiles and a
              NAMED declared property of the atom is not carried by it.
ABSENT        no faithful encoding exists; the natural spelling is refused.
NOT_MEASURED  no meaningful executable probe could be constructed. Reported, never guessed.

The decision procedure is mechanical (see ``classify``). It is deliberately biased against
PASS: an atom reaches PASS only when a misuse probe was written AND the compiler rejected
it. Where no misuse probe exists the atom cannot be PASS, by construction.

Pinning
-------
Other agents are editing ``src/hamiltonian_lang/reasoning/`` concurrently. HML_PROBE_SRC
must point at a tree extracted with ``git archive e435c77``; the working tree is NOT used
unless HML_PROBE_SRC is unset, and the resolved path is recorded in the output.

Nothing here modifies HML, and nothing here modifies the ontology. A probe that fails is a
finding, not a bug to fix.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

#: The ontology is the measuring instrument. It is read, hashed, and never written.
ONTOLOGY = (
    HERE / "runs" / "C_after_f0e3340" / "language_comparison" / "ontology"
    / "MATHEMATICAL_REASONING_ONTOLOGY_V1.json"
)
ONTOLOGY_SHA256 = "a10645a414296363b2a8206b4b5ad5331c2486f0531f40519f13bbb3837cf7c4"

_SRC = os.environ.get("HML_PROBE_SRC") or str(REPO / "src")
sys.path.insert(0, _SRC)

import hamiltonian_lang as H  # noqa: E402

M = "module M\n"

# Common preludes, so that a probe fails because of the mathematics rather than because
# of an undeclared name.
REALS = M + "var x : Real\nvar y : Real\nvar k : Real\n"
RVX = M + "rv X : RandomVariable[Real]\nlaw X ~ Normal(location := 0.0, scale := 1.0)\n"
RVXY = (
    M
    + "rv X : RandomVariable[Real]\nlaw X ~ Normal(location := 0.0, scale := 1.0)\n"
    + "rv Y : RandomVariable[Real]\nlaw Y ~ Normal(location := 0.0, scale := 1.0)\n"
)


# ---------------------------------------------------------------------------
# Spec and classification
# ---------------------------------------------------------------------------


@dataclass
class Spec:
    """What we will do to one ontology atom.

    ``accept``   the faithful encoding. Must compile clean.
    ``reject``   the corresponding MISUSE. Must be refused. Without it, no PASS.
    ``weakened`` a lesser encoding, tried only when ``accept`` is refused. If it compiles,
                 the atom is LOSSY and ``lost`` names the property that went missing.
    ``backend``  ``(source, target)``: tried only when ``accept`` is refused. If the module
                 compiles and the named backend emits it, the atom is BACKEND_ONLY.
    ``not_measured`` a reason string. Set it and nothing is executed.
    ``judgement`` set where the choice of encoding is a judgement call, and say why.

    ``structural`` ``(check_name, key)``. For atoms whose enforcement is not a rejected
                 source at all -- alpha-invariance, quantifier-order preservation,
                 round-trip fidelity, declared translation loss -- the evidence is a
                 boolean produced by one of the executed check functions below. PASS
                 requires that boolean to be True; otherwise the atom is PARTIAL. This
                 exists so that such atoms are neither given PASS for free nor punished
                 for being unexpressible as an accept/reject pair.
    ``downgrade`` a reason. When set, a classification of PASS is demoted to PARTIAL.
                 Used where the compiler genuinely enforces what it accepts, but the
                 atom names a sub-capability that is unreachable -- e.g. ANA.LIMIT
                 enforces its binder yet has no one-sided limits. Every downgrade is a
                 deliberate refusal to round upward and must say what is missing.
    """

    accept: str | None = None
    reject: str | None = None
    weakened: str | None = None
    lost: str = ""
    backend: tuple[str, str] | None = None
    structural: tuple[str, str] | None = None
    downgrade: str = ""
    not_measured: str = ""
    note: str = ""
    judgement: str = ""


@dataclass
class Outcome:
    atom: str
    domain: str
    criticality: str
    state: str
    evidence: str
    accept_codes: list[str] = field(default_factory=list)
    reject_codes: list[str] = field(default_factory=list)
    note: str = ""
    judgement: str = ""
    sources: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom": self.atom,
            "domain": self.domain,
            "criticality": self.criticality,
            "state": self.state,
            "evidence": self.evidence,
            "accept_codes": self.accept_codes,
            "reject_codes": self.reject_codes,
            "note": self.note,
            "judgement": self.judgement,
            "sources": self.sources,
        }


def _compile(src: str) -> tuple[bool, list[str], str]:
    """Return (ok, diagnostic codes, rendered first line or crash text)."""
    try:
        r = H.compile_source(src)
    except Exception as e:  # noqa: BLE001 -- a crash is itself a finding
        return False, ["CRASH"], f"{type(e).__name__}: {e}"
    codes = list(r.diagnostics.codes())
    rendered = r.diagnostics.render().strip().splitlines()
    return bool(r.ok()), codes, (rendered[0] if rendered else "")


def _backend_class(mod: Any) -> Any:
    """The one concrete Backend subclass in a backend module, or None.

    `Backend` itself is imported into most of these modules, and instantiating it calls
    the abstract `emit`, so the base class must be excluded explicitly.
    """
    from hamiltonian_lang.backends.base import Backend

    for _k, v in vars(mod).items():
        if isinstance(v, type) and issubclass(v, Backend) and v is not Backend:
            return v
    return None


def _emit(src: str, target: str) -> tuple[bool, str]:
    """Compile and lower to a backend. Returns (emitted_non_empty, note)."""
    import importlib

    try:
        r = H.compile_source(src)
        if not r.ok():
            return False, "module does not compile"
        mod = importlib.import_module(f"hamiltonian_lang.backends.{target}")
        cls = _backend_class(mod)
        if cls is None:
            return False, f"no Backend subclass in backends.{target}"
        res = cls(r.module, r.symbols).run()
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
    return bool(res.text.strip()), f"{len(res.unsupported)} losses declared"


_DECL_KEYWORDS = frozenset({"var", "param", "const", "obs", "index", "rv"})

_COMPOUND_TYPES = (
    "Set[", "Function[", "Product[", "Vector[", "Matrix[", "Tensor[", "Quantity[",
    "Distribution[", "RandomVariable[", "Predicate[",
)


def _is_vacuous(src: str) -> bool:
    """Does this weakened encoding actually encode anything?

    LOSSY is only an honest verdict when the weakened source still WRITES THE OBJECT
    DOWN and the compiler still checks something about it. A great many natural
    fallbacks do not: `var c : PositiveReal` + `require c >= 1.0` beside a matrix is not
    an encoding of a condition number, it is an unrelated scalar. Scoring those LOSSY
    would launder ABSENT into something that sounds partial.

    The test, stated so it can be re-run rather than argued about: an encoding is
    VACUOUS when it declares only plain scalars (no type constructor carries structure)
    AND every proposition in it is a syntactic self-identity `t = t`. Anything that
    declares a structured type, or states a non-trivial proposition, or binds a
    definition body, is NOT vacuous -- Set[Set[Real]] for a sigma-algebra is a real if
    lossy carrier, and so is a quantified least-upper-bound condition.
    """
    body = [ln.strip() for ln in src.strip().splitlines()[1:] if ln.strip()]
    if not body:
        return True
    decls = [ln for ln in body if ln.split(" ", 1)[0] in _DECL_KEYWORDS]
    # The STAND-IN is the last thing declared: in a fallback encoding that is the symbol
    # standing where the atom's object should be. `var A : Matrix[...]` + `var t : Real`
    # for a trace stands in with a bare scalar and encodes nothing about A.
    stand_in_structured = bool(decls) and any(c in decls[-1] for c in _COMPOUND_TYPES)
    substantive = False
    for ln in body:
        head = ln.split(" ", 1)[0]
        if head in _DECL_KEYWORDS:
            continue
        if head == "require":
            prop = ln[len("require") :].strip()
            lhs, sep, rhs = prop.partition("=")
            if sep and lhs.strip() and lhs.strip() == rhs.strip():
                continue
            substantive = True
            continue
        substantive = True
    return not (stand_in_structured or substantive)


def classify(spec: Spec, checks: dict[str, dict[str, Any]]) -> tuple[
    str, str, list[str], list[str]
]:
    """The whole decision procedure, in one place.

    Returns (state, evidence, accept_codes, reject_codes).
    """
    if spec.not_measured:
        return "NOT_MEASURED", spec.not_measured, [], []

    assert spec.accept is not None, "a spec must have an accept probe or a reason"
    a_ok, a_codes, a_first = _compile(spec.accept)

    if a_ok:
        if spec.structural is not None:
            name, key = spec.structural
            value = checks.get(name, {}).get(key)
            if value is True:
                state, evidence = (
                    "PASS",
                    f"faithful encoding compiles clean; enforcement established by the "
                    f"executed structural check {name}.{key} = True",
                )
            else:
                return (
                    "PARTIAL",
                    f"faithful encoding compiles clean, but the structural check "
                    f"{name}.{key} came back {value!r}, so enforcement is not "
                    f"established",
                    a_codes,
                    [],
                )
        elif spec.reject is None:
            return (
                "PARTIAL",
                "faithful encoding accepted; NO misuse probe was constructible, so "
                "enforcement is unestablished and PASS is withheld",
                a_codes,
                [],
            )
        else:
            r_ok, r_codes, r_first = _compile(spec.reject)
            if r_ok:
                return (
                    "PARTIAL",
                    "faithful encoding compiles clean, but the corresponding MISUSE "
                    "also compiles clean -- representable, not enforced",
                    a_codes,
                    r_codes,
                )
            state, evidence = (
                "PASS",
                f"faithful encoding compiles clean; misuse rejected with "
                f"{','.join(r_codes) or 'an error'}",
            )
            a_codes, rc = a_codes, r_codes
            if spec.downgrade:
                return (
                    "PARTIAL",
                    f"{evidence} -- DOWNGRADED from PASS: {spec.downgrade}",
                    a_codes,
                    rc,
                )
            return state, evidence, a_codes, rc

        if spec.downgrade:
            return (
                "PARTIAL",
                f"{evidence} -- DOWNGRADED from PASS: {spec.downgrade}",
                a_codes,
                [],
            )
        return state, evidence, a_codes, []

    # The faithful spelling was refused.
    if spec.weakened is not None:
        w_ok, w_codes, _ = _compile(spec.weakened)
        if w_ok and not _is_vacuous(spec.weakened):
            return (
                "LOSSY",
                f"faithful spelling refused ({','.join(a_codes) or 'error'}: "
                f"{a_first[:120]}); the weakened encoding compiles but LOSES: {spec.lost}",
                a_codes,
                w_codes,
            )
        if w_ok:
            return (
                "ABSENT",
                f"no faithful encoding ({','.join(a_codes) or 'error'}: "
                f"{a_first[:120]}). The fallback compiles but is VACUOUS by the "
                f"mechanical test in _is_vacuous -- it declares only plain scalars and "
                f"states only self-identities, so it encodes nothing about the atom. "
                f"What would have been lost: {spec.lost}",
                a_codes,
                w_codes,
            )

    if spec.backend is not None:
        b_src, b_target = spec.backend
        emitted, b_note = _emit(b_src, b_target)
        if emitted:
            return (
                "BACKEND_ONLY",
                f"no first-class HML semantics ({','.join(a_codes) or 'error'}); "
                f"reachable only by lowering to {b_target} ({b_note})",
                a_codes,
                [],
            )

    return (
        "ABSENT",
        f"no faithful encoding: {','.join(a_codes) or 'error'} -- {a_first[:160]}",
        a_codes,
        [],
    )


# ---------------------------------------------------------------------------
# The specs. One entry per ontology atom id.
# ---------------------------------------------------------------------------

SPECS: dict[str, Spec] = {}


def add(atom: str, **kw: Any) -> None:
    if atom in SPECS:
        raise SystemExit(f"duplicate spec for {atom}")
    SPECS[atom] = Spec(**kw)


# ===========================================================================
# A. FOUNDATIONS / LOGIC  (56 atoms)
# ===========================================================================

add(
    "LOGIC.ALPHA_EQUIVALENCE",
    accept=M + "require forall x : Real . x = x",
    structural=("hash_checks", "alpha_variants_share_a_hash"),
    note="there is no source-level MISUSE of alpha-equivalence to reject, so "
    "enforcement is established the only way it can be: the executed hash check "
    "confirms that two alpha-variants canonicalise to the same content hash",
)
add(
    "LOGIC.APPLICATION",
    accept=M + "def f(u : Real) : Real := u * u\nrequire f(2.0) = 4.0",
    reject=M + "def f(u : Real) : Real := u * u\nrequire f(2.0, 3.0) = 4.0",
    note="arity is checked, so application is distinguishable from juxtaposition",
)
add(
    "LOGIC.AXIOM",
    accept=M + "var p : Proposition\naxiom ax : p",
    weakened=M + "var p : Proposition\nassume ax : p",
    lost="the distinction between an axiom of a theory and a local assumption; "
    "`assume` is discharged/scoped machinery, an axiom is not",
)
add(
    "LOGIC.BICONDITIONAL",
    accept=M + "var p : Proposition\nvar q : Proposition\nrequire p iff q",
    reject=M + "var x : Real\nvar q : Proposition\nrequire x iff q",
)
add(
    "LOGIC.BOUNDED_QUANTIFIER",
    accept=M + "var S : Set[Real]\nrequire forall x : Real . x in S => x > 0.0",
    reject=M + "var S : Set[Real]\nrequire forall x : Real . x in S => x",
    judgement="HML has no `forall x in S .` form; the guard is spelled as an "
    "implication, which is the standard unfolding of bounded-forall. Whether that "
    "counts as the atom being present is a judgement call -- the asymmetry the atom "
    "names (bounded-exists unfolds to a CONJUNCTION) is NOT enforced anywhere.",
)
add(
    "LOGIC.CARTESIAN_PRODUCT",
    accept=M + "var p : Product[Real, Natural]\nrequire p = p",
    reject=M + "var p : Product[Real, Natural]\nvar q : Product[Natural, Real]\n"
    "require p = q",
    note="projection is separately absent: `p.0` is HML-P204",
)
add(
    "LOGIC.CHOICE",
    not_measured="the atom is about RECORDING that a choice principle was used. HML has "
    "no statement that attaches a foundational-principle tag to a claim, and no "
    "spelling of the concept exists to probe -- any probe would be inventing a syntax "
    "and then reporting that the invention failed to parse, which measures nothing.",
)
add(
    "LOGIC.CLASSICAL_VS_CONSTRUCTIVE",
    not_measured="same shape as LOGIC.CHOICE: the atom asks for a constructivity marker "
    "on a statement. There is no HML annotation surface at all, so there is nothing to "
    "aim a probe at.",
)
add(
    "LOGIC.CONJUNCTION",
    accept=M + "var x : Real\nrequire x > 0.0 and x < 1.0",
    reject=M + "var x : Real\nrequire x and 1.0",
)
add(
    "LOGIC.CONSERVATIVE_EXTENSION",
    accept=M + "const c : Real = 2.0\ndef d := c + 1.0",
    reject=M + "const c : Real = 2.0\ndef d := c + 1.0\ndef d := c + 2.0",
    note="the checkable part of conservativity is definitional well-formedness: fresh "
    "name, no free variables, terminating. Redefinition is rejected (HML-N303).",
)
add(
    "LOGIC.DEFINITIONAL_EQUALITY",
    accept=M + "const c : Real = 2.0\ndef d := c + 1.0",
    reject=M + "const c : Real = 2.0\ndef d = c + 1.0",
    note=":= definition and = assertion are distinct forms",
)
add(
    "LOGIC.DEPENDENT_TYPE",
    accept=M + "var A : Matrix[Real, M, N]\nvar v : Vector[Real, N]\ndef w := A @ v",
    reject=M + "var A : Matrix[Real, M, N]\nvar v : Vector[Real, M]\ndef w := A @ v",
    note="shape variables are symbolic and conformability is checked against them; this "
    "is nominal shape dependency, not a dependent type theory",
)
add(
    "LOGIC.DISJOINT_UNION",
    accept=M + "var u : Sum[Real, Bool]",
    weakened=M + "var u : Product[Real, Bool]",
    lost="the tag: a Product holds BOTH components, a sum holds exactly one. There is no "
    "injection, no case analysis and no exhaustiveness check.",
)
add(
    "LOGIC.DISJUNCTION",
    accept=M + "var x : Real\nrequire x > 0.0 or x < 1.0",
    reject=M + "var x : Real\nrequire x or 1.0",
)
add(
    "LOGIC.EQUALITY",
    accept=M + "var x : Real\nrequire x = x",
    reject=M + "var x : Real\nvar A : Matrix[Real, 2, 2]\nrequire x = A",
)
add(
    "LOGIC.EXCLUSIVE_DISJUNCTION",
    accept=M + "var p : Proposition\nvar q : Proposition\nrequire p xor q",
    weakened=M + "var p : Proposition\nvar q : Proposition\n"
    "require (p or q) and not (p and q)",
    lost="nothing semantically -- the unfolding is exact -- but xor is not a primitive, "
    "so no canonical form or backend renders it as exclusive disjunction, and the "
    "unfolding is not recognised as one",
)
add(
    "LOGIC.EXISTS",
    accept=M + "require exists x : Real . x = x",
    reject=M + "require exists x . x = x",
)
add(
    "LOGIC.EXISTS_UNIQUE",
    accept=M + "require unique x : Real . x * x = 0.0",
    weakened=M + "require exists x : Real . x * x = 0.0",
    lost="uniqueness. `unique` is a reserved keyword with no parser production "
    "(HML-P231), so the only encoding available is plain existence.",
)
add(
    "LOGIC.FORALL",
    accept=M + "require forall x : Real . x = x",
    reject=M + "require forall x . x = x",
)
add(
    "LOGIC.FREE_VS_BOUND",
    accept=M + "var y : Real\nrequire forall x : Real . x = y",
    reject=M + "require forall x : Real . x = y",
    note="an unintended free variable is REJECTED (HML-N301), which is the atom's own "
    "stated requirement",
)
add(
    "LOGIC.FUNCTIONAL_COMPLETENESS",
    accept=M + "var p : Proposition\nvar q : Proposition\n"
    "require (not p) or (p and q) or (not (p or q))",
    reject=M + "var p : Proposition\nrequire not 1.0",
    judgement="{not, and, or} is functionally complete, so the atom is satisfied by the "
    "connective set being present and typed. The probe exhibits a three-clause formula "
    "rather than attempting all 2^8 truth tables.",
)
add(
    "LOGIC.FUNCTION_AS_OBJECT",
    accept=M + "var f : Function[Real -> Real]\nrequire f = f",
    reject=M + "var f : Function[Real -> Real]\nvar x : Real\nrequire f = x",
)
add(
    "LOGIC.HYPOTHESIS_CONTEXT",
    accept=REALS + "assume a1 : k != 0.0\ndef z := y / k",
    reject=REALS + "assume a1 : k != 0.0\nassume a1 : k > 0.0",
    note="the refinement environment really is a context: a1 discharges the division "
    "obligation. Entering/leaving a context is NOT explicit -- there is no block form.",
)
add(
    "LOGIC.IMPLICATION",
    accept=M + "var x : Real\nrequire x > 1.0 => x > 0.0",
    reject=RVXY + "require X => Y",
)
add(
    "LOGIC.INDEXED_FAMILY",
    accept=M + "index i : Natural\nvar X : Function[Natural -> Real]\n"
    "require forall j : Natural . X(j) = X(j)",
    weakened=M + "index i : Natural\nvar x : Real\nrequire x = x",
    lost="the family as one object. A map from an index type to values IS writable as "
    "Function[Natural -> T] (see DISC.SEQUENCE), but `index` itself declares a bare "
    "symbol that no aggregate, law or constraint can range over, and there is no "
    "subscript form. NOTE: the original audit scored this atom P on the strength of "
    "`index i : Natural` compiling. That is acceptance, not representation of a family, "
    "so this measurement disagrees with the published verdict and says so.",
)
add(
    "LOGIC.INDEXED_UNION_INTERSECTION",
    accept=M + "index i : Natural\nvar A : Function[Natural -> Set[Real]]\n"
    "def U := union(i, 1, 10, A(i))",
    weakened=M + "var A : Set[Real]\nvar B : Set[Real]\ndef U := { x : Real | x in A }",
    lost="the index binder and the index set entirely; only a two-argument, "
    "comprehension-simulated union survives, and countable index sets are unreachable",
)
add(
    "LOGIC.INDUCTION_PRINCIPLE",
    accept=M + "var P : Function[Natural -> Bool]\n"
    "require P(0) and (forall n : Natural . P(n) => P(n + 1)) "
    "=> forall n : Natural . P(n)",
    reject=None,
    judgement="the induction SCHEMA is statable as an ordinary implication, and that is "
    "all that is measured. No misuse probe exists: the atom's failure mode is that "
    "induction cannot be APPLIED -- no kernel rule discharges a universal over Natural "
    "from base and step (see XFORM.INDUCTION_APPLICATION) -- which is an absence rather "
    "than something the compiler could reject, so PASS is withheld.",
)
add(
    "LOGIC.LAMBDA",
    accept=M + "def f := lambda x : Real . x * x",
    weakened=M + "def f(x : Real) : Real := x * x",
    lost="anonymity. Every function must be NAMED by a def; there is no expression-level "
    "abstraction, so a function cannot be built inline and passed.",
)
add(
    "LOGIC.MODAL_QUALIFIER",
    accept=M + "var p : Proposition\nrequire possibly p",
    weakened=M + "var p : Proposition\nassume p",
    lost="the modality. `assume` says 'taken as given', not 'possible'; collapsing "
    "possibility into assumption is exactly the conflation the atom forbids.",
)
add(
    "LOGIC.MODEL_SATISFACTION",
    not_measured="the atom needs a structure object and a satisfaction relation between "
    "it and a sentence. HML has `concept` (a signature-like bundle) but no model, no "
    "interpretation and no |= relation, and no candidate spelling exists to aim at.",
)
add(
    "LOGIC.NEGATION",
    accept=M + "var x : Real\nrequire not (x > 0.0)",
    reject=M + "var x : Real\nrequire not x",
)
add(
    "LOGIC.NESTED_QUANTIFIER_ORDER",
    accept=M + "require forall x : Real . exists y : Real . y > x",
    reject=M + "require forall x : Real . exists y . y > x",
    note="order sensitivity is asserted mechanically by hash_checks(), not by this probe",
)
add(
    "LOGIC.PARTIAL_DEFINEDNESS",
    accept=REALS + "assume a1 : k != 0.0\ndef z := x / k",
    reject=M + "var x : Real\ndef y := log(x)",
    note="log's domain restriction is enforced by the type (PositiveReal), and division "
    "raises a discharged obligation. This is definedness by refinement type, not by a "
    "general definedness-condition mechanism.",
)
add(
    "LOGIC.POWERSET",
    accept=M + "var A : Set[Real]\ndef P := powerset(A)",
    weakened=M + "var P : Set[Set[Real]]",
    lost="the powerset OPERATION. `Set[Set[Real]]` types a collection of subsets but "
    "nothing relates it to A, so 'F is a sub-collection of P(Omega)' is unstatable.",
)
add(
    "LOGIC.PREDICATE",
    accept=M + "var P : Predicate[Real]\nrequire forall x : Real . P(x)",
    weakened=M + "var P : Function[Real -> Bool]\nrequire forall x : Real . P(x)",
    lost="the proposition/value distinction. `Predicate[T]` parses but applying it is "
    "HML-T470; the documented workaround returns Bool, which is a VALUE type, so a "
    "predicate application is no longer distinguishable from a boolean-valued function.",
)
add(
    "LOGIC.PROOF_OBJECT",
    accept=REALS
    + "assume a1 : y = 2.0 * x\nderive d1 : 2.0 * x = y from a1 by symmetry",
    reject=REALS
    + "assume a1 : y = 2.0 * x\nderive d1 : 2.0 * x = y from a1 by hocus_pocus",
    note="a derivation carries premises, rule identity and conclusion, and the kernel "
    "re-derives the conclusion independently (HML-R706)",
)
add(
    "LOGIC.PROOF_OBLIGATION",
    accept=REALS + "def z := y / k",
    reject=REALS + "goal g : y / k = 2.0 * x / k\nassume a1 : y = 2.0 * x\n"
    "derive d1 : y / k = 2.0 * x / k from a1 by divide_both_sides(by := k)\n"
    "proved g by d1",
    downgrade="the `obligation` STATEMENT promised by the grammar contract is not "
    "implemented (HML-P205), so obligations are compiler-generated only and cannot be "
    "declared, named or discharged by hand as first-class items",
    note="obligations are generated (division raises k != 0), are first-class on the "
    "result, and an UNDISCHARGED mandatory obligation blocks the goal from reaching "
    "PROVED (HML-R710) -- which is what the reject probe demonstrates",
)
add(
    "LOGIC.PROPOSITION",
    accept=M + "var p : Proposition\nrequire p",
    reject=M + "var p : Proposition\ndef y := p + 1.0",
)
add(
    "LOGIC.QUOTIENT_BY_EQUIVALENCE",
    accept=M + "var R : Relation[Real, Real]\ndef Q := quotient(Real, R)",
    weakened=M + "var Q : Set[Set[Real]]",
    lost="everything that makes it a quotient: the equivalence relation, the class "
    "map, and the well-definedness obligation on functions defined on the quotient",
)
add(
    "LOGIC.RECURSIVE_DEFINITION",
    accept=M + "def f(n : Natural) : Natural := f(n - 1)",
    weakened=M + "var f : Function[Natural -> Natural]\n"
    "require forall n : Natural . f(n) = f(n)",
    lost="the recursion. Self-reference in a definition is rejected as a cycle "
    "(HML-S606) with no well-foundedness escape, so only a non-recursive axiomatisation "
    "of the graph of f survives.",
)
add(
    "LOGIC.RELATION",
    accept=M + "var R : Predicate[Real, Real]\nvar x : Real\nvar y : Real\n"
    "require R(x, y)",
    weakened=M + "var R : Function[Real, Real -> Bool]\nvar x : Real\nvar y : Real\n"
    "require R(x, y)",
    lost="relation-hood. The workaround is a Bool-valued function, so 'R is transitive' "
    "is a statement about a function's values, and there is no relation object to "
    "quantify over or to characterise.",
)
add(
    "LOGIC.SCHEMA",
    not_measured="an axiom schema needs metavariables ranging over FORMULAE, "
    "distinguished from object variables. HML has no metavariable sort and no syntax "
    "that could be read as one, so there is nothing to probe.",
)
add(
    "LOGIC.SECOND_ORDER_QUANTIFICATION",
    accept=M + "require forall f : Function[Real -> Real] . f = f",
    reject=M + "require forall f : Function[Real -> Real] . f",
)
add(
    "LOGIC.SET_COMPREHENSION",
    accept=M + "def T := { x : Real | x > 0.0 }",
    reject=M + "def T := { x : Real | x > 0.0 }\nrequire T = 1.0",
    note="separation, not naive comprehension: the domain type is mandatory",
)
add(
    "LOGIC.SET_MEMBERSHIP",
    accept=M + "var S : Set[Real]\nvar x : Real\nrequire x in S",
    reject=M + "var x : Real\nvar y : Real\nrequire x in y",
)
add(
    "LOGIC.SET_OPERATIONS",
    accept=M + "var A : Set[Real]\nvar B : Set[Real]\ndef C := A union B",
    weakened=M + "var A : Set[Real]\nvar B : Set[Real]\n"
    "def C := { x : Real | x in A or x in B }",
    lost="union/intersection/difference/complement as OPERATIONS. Each must be "
    "hand-unfolded into a comprehension, and complement has no ambient set to be "
    "relative to, so the Boolean algebra of sets is not an algebra of anything.",
)
add(
    "LOGIC.SUBSET",
    accept=M + "var A : Set[Real]\nvar B : Set[Real]\nrequire A subset B",
    weakened=M + "var A : Set[Real]\nvar B : Set[Real]\n"
    "require forall x : Real . x in A => x in B",
    lost="subset as a relation, and with it the proper/non-proper distinction and "
    "extensionality; only the unfolded implication survives",
)
add(
    "LOGIC.SUBSTITUTION",
    accept=REALS
    + "assume a1 : x = y\nassume a2 : x > 0.0\nderive d1 : y > 0.0 from a1, a2 by substitute",
    reject=M + "var x : Real\nvar y : Real\nassume a1 : x = y\n"
    "assume a2 : forall u : Real . x != u\n"
    "derive d1 : forall u : Real . y != u from a1, a2 by substitute",
    note="the kernel refuses to descend into quantifier bodies rather than performing a "
    "capture-unsafe substitution -- refusal is the correct behaviour for this atom",
)
add(
    "LOGIC.SUBTYPING_REFINEMENT",
    accept=M + "param s : PositiveReal\nvar r : Real\nrequire r = s",
    reject=M + "param p : Probability\nparam s : PositiveReal\ndef q : Probability := s",
    note="the refinement lattice is a partial order; Probability and PositiveReal are "
    "deliberately incomparable",
)
add(
    "LOGIC.THEOREM_STATEMENT",
    accept=M + "var f : Function[Real -> Real]\nvar D : Set[Real]\n"
    "goal mvt : continuous(f, on := D) => exists c : Real . c = c",
    reject=None,
    judgement="a goal names a statement whose hypotheses are the antecedent of an "
    "implication. They are NOT separately addressable -- there is no hypothesis list -- "
    "so the atom's second clause is unmet even though the first is met.",
)
add(
    "LOGIC.THEORY_SIGNATURE",
    accept=M + "concept Group\nparameter e : Real\ninvariant identity := e = e\nend\n"
    "var g : Group\nrequire g = g",
    reject=M + "concept Group\nparameter e : Real\ninvariant identity := e = e\nend\n"
    "var g : Group\nvar x : Real\nrequire g = x",
    downgrade="a concept bundles parameters, transforms and invariants and MUST carry a "
    "testable consequence (HML-S603 rejects an invariant-free concept), and a concept "
    "instance does not unify with a scalar. What is absent is the MODEL relation: "
    "nothing exhibits a structure satisfying the axioms, so theory and model cannot be "
    "distinguished, which is the atom's second clause.",
)
add(
    "LOGIC.TRUTH_VALUE",
    accept=M + "var b : Bool\nrequire b",
    reject=M + "require (2.0 < 3.0) + 1.0 = 2.0",
    note="Bool does not coerce into arithmetic (HML-T431), which is the atom's test",
)
add(
    "LOGIC.TYPE_JUDGEMENT",
    accept=M + "var x : Real",
    reject=M + "var x : Frobnicate",
)
add(
    "LOGIC.UNIVERSE_SORT",
    not_measured="the atom asks for a set/class stratification discipline. HML has one "
    "flat universe of types with no hierarchy and no size discipline; there is no "
    "construct that could be read as a universe level, so no probe exists.",
)
add(
    "LOGIC.VARIABLE_BINDING",
    accept=M + "require forall x : Real . x = x",
    reject=M + "require forall x : Real . x = x\nrequire x > 0.0",
    downgrade="the atom asks that shadowing be RESOLVABLE. HML rejects a nested "
    "rebinding outright (HML-N302), so binding structure is recorded and scope ends are "
    "enforced, but the shadowing case the atom names is refused rather than handled.",
    note="the reject probe uses the bound name after its binder's scope has closed and "
    "is refused (HML-N301), which is the scope-end half of the atom",
)
add(
    "LOGIC.WELL_FOUNDEDNESS",
    accept=M + "def f(n : Natural) : Natural := f(n - 1)",
    weakened=M + "var f : Function[Natural -> Natural]",
    lost="any notion of a termination measure. Recursion is refused outright, so "
    "well-foundedness is never expressed and never needed -- the atom is unreachable "
    "rather than satisfied.",
)

# ===========================================================================
# B. NUMBER SYSTEMS  (30 atoms)
# ===========================================================================

add(
    "NUM.ABSOLUTE_VALUE",
    accept=M + "var x : Real\nvar y : Real\ndef d := abs(x - y)",
    reject=M + "var A : Matrix[Real, 2, 2]\ndef d := abs(A)",
    note="abs : Real -> NonNegativeReal is a builtin with a real signature",
)
add(
    "NUM.ALGEBRAIC_NUMBER",
    accept=M + "var r : Algebraic\nrequire r * r = 2.0",
    weakened=M + "var r : Real\nrequire r * r = 2.0 and r > 0.0",
    lost="the presentation. The weakened form states a defining equation plus a branch "
    "condition but nothing records that r IS a root of a polynomial, and no branch "
    "selection machinery exists.",
)
add(
    "NUM.CARDINALITY",
    accept=M + "var S : Set[Real]\ndef n := cardinality(S)",
    weakened=M + "var v : Vector[Real, N]",
    lost="cardinality itself. A Vector's declared length is a shape extent, not the "
    "cardinality of a set, and finite / countable / uncountable are not distinguished "
    "anywhere in the type system.",
)
add(
    "NUM.COMPLEX",
    accept=M + "var z : Complex\nrequire z = z",
    weakened=M + "var z : Product[Real, Real]\nrequire z = z",
    lost="the field structure. A Product carries no multiplication, no conjugation, no "
    "modulus and no argument; and the atom's own requirement that `<` be ABSENT is not "
    "met by anything, since the pair simply has no order either way.",
)
add(
    "NUM.DIVISIBILITY",
    accept=M + "var d : Integer\nvar n : Integer\nrequire d divides n",
    weakened=M + "var d : Integer\nvar n : Integer\n"
    "require exists q : Integer . n = d * q",
    lost="divisibility as a relation. The unfolding is faithful but is an ordinary "
    "existential, so `3 | 12` has no distinguished form and no arithmetic support.",
)
add(
    "NUM.EXACT_VS_APPROX",
    accept=M + "const c : Real = 2.0\nvar x : Real\nrequire x ~= c",
    weakened=M + "const c : Real = 2.0\nvar x : Real\nrequire x = c",
    lost="the approximation marker. There is no approximate-equality relation, so an "
    "approximate claim is spelled exactly like an exact one -- precisely the silent "
    "promotion the atom forbids.",
)
add(
    "NUM.EXTENDED_REAL",
    accept=M + "var x : ExtendedReal\nrequire x = x",
    weakened=M + "var x : Real\nrequire x = x",
    lost="the two infinities. There is no +/-inf value, so `sup` of an unbounded set has "
    "nowhere to land and the indeterminate forms never arise to be left undefined.",
)
add(
    "NUM.FLOOR_CEIL_ROUND",
    accept=M + "var x : Real\ndef n := floor(x)",
    weakened=M + "var x : Real\nvar n : Integer\nrequire n <= x and x < n + 1.0",
    lost="the functions. The weakened form characterises floor by its defining "
    "inequality but there is no floor/ceil/round term and no tie-breaking convention.",
)
add(
    "NUM.GCD_LCM",
    accept=M + "def g := gcd(12, 18)",
    weakened=M + "var g : PositiveNatural\nvar a : PositiveNatural\n"
    "var b : PositiveNatural\nrequire exists q : Natural . a = g * q",
    lost="gcd and lcm entirely; only a hand-written divisibility statement about a "
    "declared symbol survives, and the universal property is unstatable",
)
add(
    "NUM.INTEGER",
    accept=M + "const n : Integer = -3",
    reject=M + "const n : Integer = 1.5",
)
add(
    "NUM.INTEGER_MOD_N",
    accept=M + "var a : IntegerMod[7]\nrequire a = a",
    weakened=M + "var a : Integer\nvar b : Integer\nvar q : Integer\n"
    "require a - b = 7 * q",
    lost="the quotient ring. Residue classes are not objects, congruence is not the "
    "equality, and `3 + 5 = 1 in Z/7Z` can only be written as a statement about "
    "integers and a witness.",
)
add(
    "NUM.INTERVAL_DOMAIN",
    accept=M + "def I := { x : Real | x >= 0.0 and x <= 1.0 }\nvar y : Real\n"
    "require y in I",
    reject=M + "def I := { x : Real | x >= 0.0 and x <= 1.0 }\nrequire I = 1.0",
    judgement="intervals are reachable as comprehensions and endpoint inclusion is "
    "visible in the predicate. What is NOT present is an interval as a distinguished "
    "object, so `integral over [a,b]` cannot name it -- integral takes bare bounds.",
)
add(
    "NUM.LITERAL_NOTATION",
    accept=M + "const c : Real = 1e-3",
    reject=M + "const n : Natural = -1",
)
add(
    "NUM.MODULAR_ARITHMETIC",
    accept=M + "var a : Integer\nvar b : Integer\nrequire a congruent b mod 7",
    weakened=M + "var a : Integer\nvar b : Integer\n"
    "require exists q : Integer . a - b = 7 * q",
    lost="congruence as a relation, and with it the distinction the atom names between "
    "the congruence PROPOSITION and a mod OPERATOR returning a residue -- HML has "
    "neither, so the distinction is vacuous rather than maintained",
)
add(
    "NUM.NATURAL",
    accept=M + "const n : Natural = 3",
    reject=M + "const n : Natural = -1",
)
add(
    "NUM.NONNEGATIVE_REAL",
    accept=M + "var v : NonNegativeReal\nrequire v >= 0.0",
    reject=M + "const v : NonNegativeReal = -1.0",
)
add(
    "NUM.NUMERIC_COERCION_POLICY",
    accept=M + "const n : Natural = 3\nvar i : Integer\nrequire i = n",
    reject=M + "param p : Probability\ndef q : PositiveReal := p",
    note="N -> Z -> Q -> R widening is automatic; the epistemic scalars are "
    "deliberately incomparable and the barrier holds",
)
add(
    "NUM.ORDER_RELATION",
    accept=M + "var x : Real\nrequire x <= x",
    reject=M + "var p : Proposition\nvar q : Proposition\nrequire p < q",
    judgement="the atom's second clause -- that `<` be ABSENT on C -- cannot be tested, "
    "because there is no Complex type at all (see NUM.COMPLEX). Only the presence half "
    "is measured here.",
)
add(
    "NUM.ORDINAL",
    accept=M + "var a : Ordinal\nrequire a = a",
    weakened=M + "index i : Natural",
    lost="transfinite indexing. Natural indices are the only indices, so a hierarchy "
    "indexed by countable ordinals cannot be stated at all.",
)
add(
    "NUM.PADIC",
    accept=M + "var x : PAdic[7]\nrequire x = x",
    weakened=M + "var x : Rational\nrequire x = x",
    lost="the non-archimedean absolute value and the completion; a Rational carries the "
    "ordinary metric and nothing marks a different notion of nearness",
)
add(
    "NUM.POSITIVE_REAL",
    accept=M + "param s : PositiveReal\ndef y := log(s)",
    reject=M + "const s : PositiveReal = 0.0",
    note="log is total exactly on PositiveReal, which is the atom's own criterion",
)
add(
    "NUM.PRIME",
    accept=M + "var n : Natural\nrequire prime(n)",
    weakened=M + "var n : Natural\nrequire n > 1 and forall d : Natural . "
    "(exists q : Natural . n = d * q) => (d = 1 or d = n)",
    lost="primality as a named predicate. The unfolded definition is statable, so the "
    "mathematics survives, but `Prime(n)` has no spelling and cannot be reused.",
)
add(
    "NUM.PROBABILITY_SCALAR",
    accept=M + "param p : Probability\nrequire p >= 0.0 and p <= 1.0",
    reject=M + "const p : Probability = 2.0",
    note="Probability is a distinct scalar, not a magnitude; the [0,1] bound is checked "
    "on literals",
)
add(
    "NUM.QUATERNION_HYPERCOMPLEX",
    accept=M + "var q : Quaternion\nrequire q = q",
    weakened=M + "var A : Matrix[Real, 2, 2]\nvar B : Matrix[Real, 2, 2]\n"
    "def C := A @ B",
    lost="everything except non-commutativity of a matrix product, which is a different "
    "object. There is no quaternion scalar and no non-commutative scalar domain.",
)
add(
    "NUM.RATIONAL",
    accept=M + "const q : Rational = 1\nrequire q = q",
    reject=M + "const q : Rational = 1\nvar A : Matrix[Real, 2, 2]\nrequire q = A",
    judgement="Rational is a scalar in the refinement lattice, so the TYPE is present. "
    "Exactness is not: there is no rational literal form (`1/3` is a division of reals) "
    "and no equality-up-to-reduction, so the atom's central claim is unenforced.",
)
add(
    "NUM.REAL",
    accept=M + "const x : Real = 1.5",
    reject=M + "var x : Real\nvar b : Bool\nrequire x = b",
)
add(
    "NUM.SIGN",
    accept=M + "var x : Real\ndef s := sign(x)",
    weakened=M + "var x : Real\nrequire (x > 0.0) or (x < 0.0) or (x = 0.0)",
    lost="the sign function and its three-valued codomain; only a case split on the "
    "ordering survives and sign(0) has no recorded convention",
)
add(
    "NUM.TRANSCENDENTAL_CONSTANT",
    accept=M + "def c := pi",
    weakened=M + "const pi_approx : Real = 3.14159265358979",
    lost="exactness and symbol-hood. A named constant bound to a decimal is the "
    "approximation the atom explicitly excludes.",
)
add(
    "NUM.UNIT_INTERVAL",
    accept=M + "param p : Probability\nparam q : Probability\ndef r := p * q",
    reject=M + "const p : Probability = 1.5",
    judgement="Probability IS the unit interval refinement and is closed under "
    "multiplication in the checker. Note that `p + q` also type-checks and yields a "
    "wider scalar, so non-closure under addition is handled by widening rather than by "
    "rejection -- which is correct, and is why the reject probe uses a literal.",
)
add(
    "NUM.VECTOR_OF_SCALARS",
    accept=M + "var v : Vector[Real, 3]\nrequire v = v",
    reject=M + "var u : Vector[Real, 3]\nvar v : Vector[Real, 4]\ndef d := u + v",
)

# ===========================================================================
# C. ALGEBRA  (46 atoms)
# ===========================================================================

add(
    "ALG.BASIS_CHANGE",
    accept=M + "var A : Matrix[Real, 3, 3]\nvar P : Matrix[Real, 3, 3]\n"
    "def B := inverse(P) @ A @ P",
    weakened=M + "var A : Matrix[Real, 3, 3]\nvar P : Matrix[Real, 3, 3]\n"
    "var Pinv : Matrix[Real, 3, 3]\ndef B := Pinv @ A @ P",
    lost="the inverse, and with it any statement that P is a change of basis rather "
    "than an arbitrary pair of matrices; nothing marks an invariant as basis-independent",
)
add(
    "ALG.BROADCAST_SEMANTICS",
    accept=M + "var A : Matrix[Real, 2, 3]\nvar B : Matrix[Real, 2, 3]\ndef C := A * B",
    reject=M + "var A : Matrix[Real, 2, 3]\nvar B : Matrix[Real, 3, 4]\ndef C := A * B",
    judgement="`*` and `@` are distinct operators, so elementwise and algebraic "
    "multiplication ARE distinguished -- that half is real. The reject probe tests "
    "whether elementwise multiplication of non-conformable matrices is caught.",
)
add(
    "ALG.CATEGORY",
    accept=M + "var C : Category\nrequire C = C",
    weakened=M + "concept Cat\nparameter f : Function[Real -> Real]\n"
    "invariant identity := f = f\nend",
    lost="objects, morphisms, composition and identities. Nothing in HML ranges over "
    "morphisms, so structural statements independent of elements are unreachable.",
)
add(
    "ALG.DETERMINANT",
    accept=M + "var A : Matrix[Real, 3, 3]\ndef d := det(A)",
    weakened=M + "var A : Matrix[Real, 3, 3]\nvar d : Real\nrequire d = d",
    lost="the determinant. A bare Real named `d` is not a matrix invariant; "
    "multiplicativity and the volume reading have no home.",
)
add(
    "ALG.DUAL_SPACE",
    accept=M + "var phi : Dual[Vector[Real, 3]]\nrequire phi = phi",
    weakened=M + "var phi : Function[Vector[Real, 3] -> Real]\nrequire phi = phi",
    lost="the vector/covector distinction. A linear functional typed as an ordinary "
    "function loses covariance, so a gradient and a tangent vector are the same type.",
)
add(
    "ALG.EIGEN",
    accept=M + "var A : Matrix[Real, 3, 3]\ndef e := eigenvalues(A)",
    weakened=M + "var A : Matrix[Real, 3, 3]\nvar v : Vector[Real, 3]\n"
    "var lam : Real\nrequire A @ v = lam * v",
    lost="multiplicity, the eigenvalue SET, and the possibility of complex eigenvalues "
    "for a real matrix (there is no Complex type). Only one defining equation survives.",
)
add(
    "ALG.EINSTEIN_SUMMATION",
    not_measured="the atom requires an index-notation surface in which a repeated index "
    "means summation. HML has no index notation on aggregates at all (see "
    "ALG.TENSOR_INDEX_NOTATION), so there is no place a summation convention could be "
    "declared or omitted, and no probe can distinguish the two.",
)
add(
    "ALG.EQUATION",
    accept=M + "var x : Real\nrequire x + 1.0 = 2.0",
    reject=M + "var x : Real\nx + 1.0 = 2.0",
)
add(
    "ALG.FACTORIZATION",
    accept=M + "var x : Real\ndef p := factor(x ** 2 + 1.0)",
    weakened=M + "var x : Real\nvar r : Real\nrequire x ** 2 - 2.0 = (x - r) * (x + r)",
    lost="the ground field, irreducibility and root multiplicity. A hand-written "
    "identity is not a factorisation relative to a declared field.",
)
add(
    "ALG.FIELD",
    accept=M + "concept Field\nparameter e : Real\ninvariant unit := e * e = e\nend",
    weakened=M + "var a : Real\nvar b : Real\nrequire a * b = b * a",
    lost="the structure. Axioms become loose propositions about Real; there is no field "
    "object, no instantiation, and nothing says Z is not one.",
)
add(
    "ALG.FUNCTOR",
    not_measured="a functor acts on objects AND morphisms of a category. ALG.CATEGORY "
    "is absent, so the domain of the construction does not exist; probing for the "
    "action would be probing for a map out of nothing.",
)
add(
    "ALG.GENERATORS_RELATIONS",
    accept=M + "var G : Presentation\nrequire G = G",
    weakened=M + "var g : Real\nrequire g ** 5 = 1.0",
    lost="the presentation. One imposed identity on a Real is not a generated structure "
    "and nothing marks g as a generator.",
)
add(
    "ALG.GROUP",
    accept=M + "concept Group\nparameter e : Real\n"
    "invariant associativity := (e * e) * e = e * (e * e)\nend",
    reject=M + "concept Group\nparameter e : Real\nend",
    lost="the structure and, critically, the atom's requirement that commutativity be "
    "DECLARED not assumed: the weakened form inherits Real's commutative `*`",
)
add(
    "ALG.HOMOMORPHISM",
    accept=M + "var f : Function[Real -> Real]\n"
    "require homomorphism(f, from := Real, to := Real)",
    weakened=M + "var f : Function[Real -> Real]\n"
    "require forall a : Real . forall b : Real . f(a + b) = f(a) * f(b)",
    lost="'is a homomorphism' as a checkable property. The preservation condition is "
    "statable per instance but there is no predicate and no pair of structures to be "
    "between.",
)
add(
    "ALG.IDEAL",
    accept=M + "var I : Ideal[Real]\nrequire I = I",
    weakened=M + "var I : Set[Real]\nrequire I = I",
    lost="absorption. A Set carries no ring operation, so nothing distinguishes an "
    "ideal from an arbitrary subset and no quotient can be formed.",
)
add(
    "ALG.INEQUALITY",
    accept=M + "var x : Real\nrequire x + 1.0 > 2.0",
    reject=M + "var p : Proposition\nvar q : Proposition\nrequire p > q",
)
add(
    "ALG.INNER_PRODUCT",
    accept=M + "var u : Vector[Real, 3]\nvar v : Vector[Real, 3]\n"
    "require inner(u, v) = 0.0",
    weakened=M + "var u : Vector[Real, 3]\nvar v : Vector[Real, 3]\n"
    "def s := sum(u * v)",
    lost="the form itself. `sum(u * v)` is an elementwise product summed, which "
    "coincides with the standard inner product but is not one: no bilinearity, no "
    "positive-definiteness, no orthogonality relation and no choice of form.",
)
add(
    "ALG.INVERSE",
    accept=M + "var A : Matrix[Real, 3, 3]\nvar b : Vector[Real, 3]\n"
    "def x := inverse(A) @ b",
    weakened=M + "var A : Matrix[Real, 3, 3]\nvar Ainv : Matrix[Real, 3, 3]\n"
    "var b : Vector[Real, 3]\ndef x := Ainv @ b",
    lost="the invertibility OBLIGATION, which is the whole point of the atom. Naming a "
    "second matrix `Ainv` asserts nothing and emits no side condition.",
)
add(
    "ALG.ISOMORPHISM",
    accept=M + "var V : VectorSpace[Real, 3]\nvar W : VectorSpace[Real, 3]\n"
    "require isomorphic(V, W)",
    weakened=M + "var f : Function[Real -> Real]\nvar g : Function[Real -> Real]\n"
    "require forall a : Real . g(f(a)) = a",
    lost="isomorphism as a relation between STRUCTURES, and with it the distinction "
    "from equality that the atom exists to protect",
)
add(
    "ALG.KERNEL_IMAGE",
    accept=M + "var T : Function[Vector[Real, 3] -> Vector[Real, 2]]\n"
    "def K := kernel(T)",
    weakened=M + "var T : Function[Vector[Real, 3] -> Vector[Real, 2]]\n"
    "def K := { v : Vector[Real, 3] | T(v) = T(v) }",
    lost="the subobject and the dimension relation. A comprehension gives a set of "
    "vectors but `dim` does not exist, so rank-nullity is unstatable.",
)
add(
    "ALG.KRONECKER_OUTER",
    accept=M + "var u : Vector[Real, 3]\nvar v : Vector[Real, 4]\ndef A := outer(u, v)",
    weakened=M + "var u : Matrix[Real, 3, 1]\nvar v : Matrix[Real, 1, 4]\n"
    "def A := u @ v",
    lost="nothing about the resulting shape -- 3x1 @ 1x4 really is 3x4 and is checked -- "
    "but the outer/Kronecker/tensor products have no names, so the operation must be "
    "encoded as a matrix product on hand-reshaped operands",
)
add(
    "ALG.LINEAR_MAP",
    accept=M + "var T : LinearMap[Vector[Real, 3] -> Vector[Real, 2]]\nrequire T = T",
    weakened=M + "var T : Function[Vector[Real, 3] -> Vector[Real, 2]]\nrequire T = T",
    lost="linearity and basis-independence. A Function is not known to be linear and "
    "nothing relates it to a matrix representation in chosen bases.",
)
add(
    "ALG.MATRIX",
    accept=M + "var A : Matrix[Real, 3, 3]\nrequire A = A",
    reject=M + "var A : Matrix[Real, 2, 3]\nvar B : Matrix[Real, 3, 4]\nrequire A = B",
)
add(
    "ALG.MATRIX_ARITHMETIC",
    accept=M + "var A : Matrix[Real, 3, 3]\nvar B : Matrix[Real, 3, 3]\n"
    "def C := A @ B\ndef D := A + B",
    reject=M + "var A : Matrix[Real, 2, 3]\nvar B : Matrix[Real, 3, 4]\ndef C := A + B",
    note="the reject probe tests ADDITION conformability specifically; multiplication "
    "order preservation is covered by ALG.MATRIX_SHAPE_TYPING",
)
add(
    "ALG.MATRIX_DECOMPOSITION",
    accept=M + "var A : Matrix[Real, 3, 3]\ndef L := cholesky(A)",
    weakened=M + "var A : Matrix[Real, 3, 3]\nvar L : Matrix[Real, 3, 3]\n"
    "require A = L @ transpose(L)",
    lost="existence conditions and uniqueness conventions. The defining equation is "
    "statable and its shapes are checked, but nothing says A must be positive definite "
    "or which convention fixes the sign.",
)
add(
    "ALG.MATRIX_SHAPE_TYPING",
    accept=M + "var A : Matrix[Real, M, N]\nvar B : Matrix[Real, N, K]\ndef C := A @ B",
    reject=M + "var A : Matrix[Real, 2, 3]\nvar B : Matrix[Real, 2, 3]\ndef C := A @ B",
    note="symbolic extents are supported and conformability is checked against them",
)
add(
    "ALG.MODULE",
    accept=M + "var Mo : Module[Integer]\nrequire Mo = Mo",
    weakened=M + "var v : Vector[Integer, 3]\nrequire v = v",
    lost="the ring of scalars as a parameter, and the atom's point that bases need not "
    "exist -- a Vector's length IS a basis size",
)
add(
    "ALG.NORM",
    accept=M + "var v : Vector[Real, 3]\ndef n := norm(v, p := 2)",
    weakened=M + "var v : Vector[NonNegativeReal, 3]\ndef n := sqrt(sum(v * v))",
    lost="which norm, AND the ability to take it of an arbitrary real vector. The "
    "unfolding hard-codes the 2-norm, and even that only compiles when the elements are "
    "declared NonNegativeReal: sum(v * v) over Real elements widens to Real, which sqrt "
    "refuses (HML-T427). There is no norm object, no p parameter, no matrix norm, and "
    "homogeneity/subadditivity are unstated.",
)
add(
    "ALG.ORDER_STRUCTURE",
    accept=M + "var a : Real\nvar b : Real\nvar c : NonNegativeReal\n"
    "require a <= b => a + c <= b + c",
    reject=M + "var A : Matrix[Real, 2, 2]\nvar B : Matrix[Real, 2, 2]\nrequire A <= B",
    judgement="compatibility axioms are statable as propositions over Real, and order "
    "is correctly unavailable on matrices. What is absent is an ordered-structure "
    "OBJECT: the axioms are not bundled with the carrier.",
)
add(
    "ALG.POLYNOMIAL",
    accept=M + "var x : Real\ndef p := Polynomial(x, coefficients := [1.0, 2.0, 3.0])",
    weakened=M + "var x : Real\ndef p := 3.0 * x ** 2 + 2.0 * x + 1.0",
    lost="structure. The weakened form is an opaque expression tree: degree, "
    "coefficients and the indeterminate are not addressable, which is exactly what the "
    "atom says a polynomial must not be.",
)
add(
    "ALG.POSITIVE_DEFINITE",
    accept=M + "var S : Matrix[Real, 3, 3]\nrequire positive_definite(S)",
    weakened=M + "var S : Matrix[Real, 3, 3]\n"
    "require forall v : Vector[Real, 3] . sum(v * (S @ v)) > 0.0",
    lost="the property as a type-level constraint. The quantified definition is "
    "statable only by hand-unfolding the quadratic form into an elementwise product "
    "and a sum, and nothing connects it to the type of S, so no operation preserves it "
    "and no distribution can require a PSD covariance.",
)
add(
    "ALG.QUOTIENT_STRUCTURE",
    accept=M + "var R : Quotient[Real]\nrequire R = R",
    weakened=M + "var R : Set[Set[Real]]\nrequire R = R",
    lost="the induced operations and their well-definedness obligation; a set of sets "
    "has no structure at all",
)
add(
    "ALG.RANK",
    accept=M + "var X : Matrix[Real, N, K]\nrequire rank(X) = K",
    weakened=M + "var X : Matrix[Real, N, K]\nvar r : Natural\nrequire r = r",
    lost="rank. Full column rank -- an identifiability condition used constantly in "
    "STAT.LINEAR_MODEL -- cannot be stated.",
)
add(
    "ALG.RATIONAL_FUNCTION",
    accept=M + "var x : Real\ndef f := RationalFunction(x, poles := [1.0])",
    weakened=REALS + "assume a1 : k != 0.0\ndef f := (x + 1.0) / k",
    lost="the pole structure. The weakened form carries a definedness obligation on ONE "
    "named denominator, not a domain-of-definition attached to a function object.",
)
add(
    "ALG.RING",
    accept=M + "concept Ring\nparameter e : Real\n"
    "invariant distributivity := e * (e + e) = e * e + e * e\nend",
    weakened=M + "var a : Real\nvar b : Real\nvar c : Real\n"
    "require a * (b + c) = a * b + a * c",
    lost="the structure; commutativity and unity cannot be declared because there is "
    "nothing to declare them of",
)
add(
    "ALG.SOLUTION_SET",
    accept=M + "var x : Real\ndef S := { u : Real | u * u = 2.0 }",
    reject=M + "var x : Real\ndef S := { u : Real | u * u = 2.0 }\nrequire S = 1.4",
    judgement="a solution set is expressible as a comprehension and is distinguishable "
    "from a single root (the reject probe shows Set != Real). What is missing is any "
    "connection to a SOLVE operation -- `solve` is HML-P204 -- so the set is written by "
    "hand and nothing produces it.",
)
add(
    "ALG.SUBSTRUCTURE",
    accept=M + "var V : VectorSpace[Real, 3]\nvar W : Subspace[V]\nrequire W = W",
    weakened=M + "var W : Set[Matrix[Real, 3, 3]]\nrequire W = W",
    lost="closure under the operations, which is the entire content of substructure-hood "
    "and is the checkable condition the atom asks for",
)
add(
    "ALG.SYMBOLIC_SIMPLIFICATION",
    accept=REALS + "assume a1 : k != 0.0\n"
    "assume a2 : x * k = y * k\nderive d1 : x * k / k = y * k / k from a2 "
    "by divide_both_sides(by := k)",
    reject=REALS + "assume a2 : x * k = y * k\n"
    "derive d1 : x = y from a2 by divide_both_sides(by := k)",
    note="the domain-narrowing step really is flagged: dividing raises a mandatory "
    "k != 0 obligation, and the unsound cancellation is refused outright",
)
add(
    "ALG.SYMBOLIC_VARIABLE",
    accept=M + "var x : Real\nrequire x = x",
    reject=M + "require x = x",
)
add(
    "ALG.SYMMETRY_CLASS",
    accept=M + "var Q : Orthogonal[Real, 3]\nrequire Q = Q",
    weakened=M + "var Q : Matrix[Real, 3, 3]\nrequire Q @ transpose(Q) = Q @ transpose(Q)",
    lost="the class as a type-level property. Symmetric / Hermitian / orthogonal / "
    "triangular / diagonal are not types, so no operation can preserve or lose them.",
)
add(
    "ALG.SYSTEM_OF_RELATIONS",
    accept=M + "var A : Matrix[Real, 3, 3]\nvar x : Vector[Real, 3]\n"
    "var b : Vector[Real, 3]\nrequire A @ x = b and x = x",
    reject=M + "var A : Matrix[Real, 3, 3]\nvar x : Vector[Real, 2]\n"
    "var b : Vector[Real, 3]\nrequire A @ x = b and x = x",
    judgement="a conjunction of relations sharing unknowns is expressible and its "
    "shapes are checked. It is not ONE OBJECT: there is no system value to name, pass "
    "or attach a joint solution set to.",
)
add(
    "ALG.TENSOR",
    accept=M + "var T : Tensor[Real, 2, 3, 4]\nrequire T = T",
    reject=M + "var T : Tensor[Real, 2, 3, 4]\nvar U : Tensor[Real, 2, 3, 5]\n"
    "def S := T + U",
)
add(
    "ALG.TENSOR_INDEX_NOTATION",
    accept=M + "var C : Matrix[Real, 3, 3]\nvar A : Matrix[Real, 3, 3]\n"
    "var B : Matrix[Real, 3, 3]\nrequire C[i, k] = A[i, j] * B[j, k]",
    weakened=M + "var C : Matrix[Real, 3, 3]\nvar A : Matrix[Real, 3, 3]\n"
    "var B : Matrix[Real, 3, 3]\nrequire C = A @ B",
    lost="named indices entirely. Entries are not addressable, so free and bound "
    "(summed) indices cannot be distinguished and only whole-array operations exist.",
)
add(
    "ALG.TRACE",
    accept=M + "var A : Matrix[Real, 3, 3]\ndef t := trace(A)",
    weakened=M + "var A : Matrix[Real, 3, 3]\nvar t : Real\nrequire t = t",
    lost="the trace; the cyclic property and basis-independence have nothing to attach to",
)
add(
    "ALG.TRANSPOSE_ADJOINT",
    accept=M + "var A : Matrix[Real, 2, 3]\nvar B : Matrix[Real, 3, 4]\n"
    "require transpose(A @ B) = transpose(B) @ transpose(A)",
    reject=M + "var v : Vector[Real, 3]\ndef t := transpose(v)",
    judgement="transpose is a real builtin, is shape-reversing, and refuses a "
    "non-matrix. The conjugate transpose is not distinguished from it, but that is "
    "moot: there is no Complex type for it to differ on.",
)
add(
    "ALG.VECTOR_SPACE",
    accept=M + "var V : VectorSpace[Real, 3]\nrequire V = V",
    weakened=M + "var v : Vector[Real, 3]\nvar w : Vector[Real, 3]\nvar a : Real\n"
    "def u := a * v + w",
    lost="the space as an object. Vectors and the scalar action exist and are shape "
    "checked, but the field, the dimension-as-property and basis-independence are not "
    "expressible because there is nothing to predicate them of.",
)

# ===========================================================================
# D. ANALYSIS  (48 atoms)
# ===========================================================================

add(
    "ANA.ALMOST_EVERYWHERE",
    accept=RVX + "require almost_surely X = X",
    weakened=RVX + "require probability(X = X) = 1.0",
    lost="the qualifier as an attachment to a statement. `P(A) = 1` is a numeric claim "
    "about a measure, not an a.e.-qualified assertion of A, and there is no null set "
    "and no reference measure to be almost-everywhere with respect to.",
)
add(
    "ANA.ASYMPTOTIC_NOTATION",
    accept=M + "var f : Function[Real -> Real]\nvar g : Function[Real -> Real]\n"
    "require bigO(f, g, as := x -> 0.0)",
    weakened=M + "var f : Function[Real -> Real]\nvar g : Function[Real -> Real]\n"
    "var C : PositiveReal\nrequire forall x : Real . abs(f(x)) <= C * abs(g(x))",
    lost="the limit point and the variable, which the atom names explicitly, and the "
    "relational reading of O(.) -- the unfolding is a global bound, not an asymptotic one",
)
add(
    "ANA.BOUNDARY_CONDITION",
    not_measured="a boundary condition is attached to a PDE on a specified part of a "
    "boundary. HML has no differential-equation object (see ANA.PDE) and no boundary, "
    "so there is nothing for the condition to be a condition on.",
)
add(
    "ANA.CHAIN_RULE",
    accept=M + "var f : Function[Real -> Real]\nvar g : Function[Real -> Real]\n"
    "require derivative(f(g(x)), x : Real) = "
    "derivative(f(g(x)), x : Real) * derivative(g(x), x : Real)",
    reject=None,
    judgement="the chain rule is STATABLE because derivative binds a variable and "
    "composition is ordinary application. Nothing DERIVES it: there is no kernel rule "
    "for differentiation, so the equation is an assertion the compiler never checks. "
    "The reject probe only establishes that the binder is mandatory.",
)
add(
    "ANA.COMPLEX_ANALYTIC",
    accept=M + "var f : Function[Complex -> Complex]\nrequire holomorphic(f)",
    weakened=M + "var f : Function[Real -> Real]\nvar D : Set[Real]\n"
    "require continuous(f, on := D)",
    lost="the entire subject. There is no Complex type, so holomorphy, poles, residues "
    "and contour integration have no domain; real continuity is not a substitute.",
)
add(
    "ANA.CONTINUITY",
    accept=M + "var f : Function[Real -> Real]\nvar D : Set[Real]\n"
    "require continuous(f, on := D)",
    reject=M + "var f : Function[Real -> Real]\nrequire continuous(f)",
    downgrade="the atom names TWO distinct claims -- continuity at a point and "
    "continuity on a set -- and only the second exists. `continuous(f, at := 0.0)` is "
    "HML-P266, so pointwise continuity has no spelling.",
    note="the domain argument is MANDATORY, which is the atom's other requirement",
)
add(
    "ANA.CONVERGENCE_MODES",
    accept=M + "var f : Function[Natural -> Real]\nvar g : Function[Real -> Real]\n"
    "require converges(f, to := g, mode := uniform)",
    weakened=M + "var f : Function[Real -> Real]\n"
    "def l := limit(f(x), x : Real -> 0.0)",
    lost="the mode. There is exactly one convergence notion in the language -- the "
    "`limit` binder -- so pointwise, uniform, L^p and a.e. convergence are merged into "
    "one relation, which is what the atom forbids.",
)
add(
    "ANA.CONVOLUTION",
    accept=M + "var f : Function[Real -> Real]\nvar g : Function[Real -> Real]\n"
    "def h := convolve(f, g)",
    weakened=M + "var f : Function[Real -> Real]\nvar g : Function[Real -> Real]\n"
    "var x : Real\ndef h := integral(f(t) * g(x - t), t : Real, 0.0, 1.0)",
    lost="the operation and its domain conditions. The integral spelling needs finite "
    "literal bounds (there is no infinity), so the convolution integral cannot even be "
    "written over its real domain.",
)
add(
    "ANA.DERIVATIVE",
    accept=M + "var f : Function[Real -> Real]\ndef d := derivative(f(x), x : Real)",
    reject=M + "var f : Function[Real -> Real]\ndef d := derivative(f, x)",
    downgrade="the atom also requires the POINT OF EVALUATION to be distinguished from "
    "the derivative function. There is no evaluation-at form (`derivative(...) at 0.0` "
    "is HML-P204), so f'(a) and f' are the same expression.",
    note="the differentiation variable is an explicitly typed binder",
)
add(
    "ANA.DIRECTIONAL_DERIVATIVE",
    accept=M + "var f : Function[Vector[Real, 3] -> Real]\nvar d : Vector[Real, 3]\n"
    "def g := directional_derivative(f, along := d)",
    weakened=M + "var f : Function[Real -> Real]\ndef g := derivative(f(x), x : Real)",
    lost="the direction, and the total (Frechet) derivative as a linear map. Only "
    "differentiation with respect to a scalar binder exists.",
)
add(
    "ANA.DOMAIN_CODOMAIN",
    accept=M + "var f : Function[Real -> NonNegativeReal]\nrequire f = f",
    reject=M + "var f : Function[Real -> NonNegativeReal]\n"
    "var g : Function[Real -> Real]\nrequire f = g",
    note="two functions with the same rule but different codomains are different "
    "objects, which is the atom's test",
)
add(
    "ANA.FIXED_POINT",
    accept=M + "var T : Function[Real -> Real]\nvar x : Real\nrequire T(x) = x",
    reject=M + "var T : Function[Real -> Real]\nvar x : Real\nrequire T(x, x) = x",
    judgement="the fixed-point EQUATION is expressible and arity-checked. The atom's "
    "real content -- contraction or compactness hypotheses making existence a theorem -- "
    "is not: there is no metric, no contraction constant and no existence rule.",
)
add(
    "ANA.FUNCTIONAL_DERIVATIVE",
    accept=M + "var J : Function[Function[Real -> Real] -> Real]\n"
    "var f : Function[Real -> Real]\ndef d := derivative(J(f), f : Function[Real -> Real])",
    weakened=M + "var J : Function[Function[Real -> Real] -> Real]\n"
    "var f : Function[Real -> Real]\ndef v := J(f)",
    lost="the variation. Only the functional's VALUE is expressible; differentiating "
    "with respect to a function argument is not, so calculus of variations is closed off.",
)
add(
    "ANA.FUNCTION_REAL",
    accept=M + "def f(u : Real) : Real := u * u\n"
    "var g : Function[Real, Real -> Vector[Real, 3]]\nrequire g = g",
    reject=M + "def f(u : Real) : Real := u * u\nrequire f(2.0, 3.0) = 4.0",
)
add(
    "ANA.FUNCTION_SPACE",
    accept=M + "var f : L2[Real]\nrequire f = f",
    weakened=M + "var F : Set[Function[Real -> Real]]\n"
    "var f : Function[Real -> Real]\nrequire f in F",
    lost="the norm and the equivalence relation that make it a function SPACE. "
    "Membership in a bare set of functions is checkable syntactically and says nothing "
    "about integrability, smoothness or completeness.",
)
add(
    "ANA.GENERALIZED_FUNCTION",
    accept=M + "var delta : Distribution2[Real]\nrequire delta = delta",
    weakened=M + "var delta : Function[Function[Real -> Real] -> Real]\n"
    "require delta = delta",
    lost="the distinction from an ordinary function, which is the atom's entire point, "
    "and the pairing with test functions. Note `Distribution[T]` is already taken by "
    "probability distributions, so the name collides.",
)
add(
    "ANA.GRADIENT",
    accept=M + "var f : Function[Vector[Real, 3] -> Real]\ndef g := gradient(f)",
    weakened=M + "var f : Function[Real, Real, Real -> Real]\n"
    "def g1 := derivative(f(x, y, z), x : Real)",
    lost="the vector of partials as one object with a shape determined by the domain, "
    "and the covector/total-derivative distinction. Only one component at a time.",
)
add(
    "ANA.HESSIAN",
    accept=M + "var f : Function[Vector[Real, 3] -> Real]\ndef Hf := hessian(f)",
    weakened=M + "var f : Function[Real, Real -> Real]\n"
    "def h := derivative(derivative(f(x, y), x : Real), x : Real)",
    lost="the matrix, its symmetry, and the connection to convexity and second-order "
    "optimality conditions; only iterated scalar differentiation survives",
)
add(
    "ANA.HIGHER_DERIVATIVE",
    accept=M + "var f : Function[Real -> Real]\n"
    "def d2 := derivative(derivative(f(x), x : Real), x : Real)",
    weakened=M + "var f : Function[Real -> Real]\n"
    "def d2 := derivative(derivative(f(u), u : Real), v : Real)",
    lost="repeated differentiation with respect to THE SAME variable. The inner binder "
    "shadows the outer one and is rejected (HML-N302), so d^2f/dx^2 has no spelling; "
    "only a mixed second derivative in two distinct binders compiles, which is a "
    "different object. Smoothness classes (C^k, C^infinity, analytic) are absent too.",
)
add(
    "ANA.IMPLICIT_DIFFERENTIATION",
    accept=M + "var F : Function[Real, Real -> Real]\nvar y : Function[Real -> Real]\n"
    "require derivative(F(x, y(x)), x : Real) = 0.0",
    reject=None,
    judgement="the implicit relation and its differentiation are statable. The "
    "non-degeneracy condition of the implicit function theorem is NOT attached to "
    "anything -- no partial derivative can be named, so 'dF/dy != 0' is unwritable.",
)
add(
    "ANA.IMPROPER_INTEGRAL",
    accept=M + "var f : Function[Real -> Real]\n"
    "def a := integral(f(x), x : Real, 0.0, infinity)",
    weakened=M + "var f : Function[Real -> Real]\n"
    "def a := integral(f(x), x : Real, 0.0, 1.0)",
    lost="the unbounded domain. There is no infinity literal and no extended real, so "
    "an improper integral must be silently replaced by a proper one -- and its "
    "existence, which the atom says is a claim, is never raised.",
)
add(
    "ANA.INITIAL_CONDITION",
    not_measured="an initial condition attaches a value of the unknown to a "
    "differential equation as part of ONE problem object. ANA.ODE has no representation "
    "at all, so there is no problem object to attach to and no spelling to probe.",
)
add(
    "ANA.INTEGRAL_DEFINITE",
    accept=M + "var f : Function[Real -> Real]\n"
    "def a := integral(f(x), x : Real, 0.0, 1.0)",
    reject=M + "var f : Function[Real -> Real]\ndef a := integral(f, x, 0.0, 1.0)",
    downgrade="the atom requires an explicit MEASURE or differential as well as a "
    "binder and a domain. `integral` takes two numeric bounds and nothing else, so the "
    "reference measure is fixed and unnameable -- see ANA.INTEGRAL_LEBESGUE.",
    note="binds a typed variable and carries explicit bounds; the untyped-binder "
    "spelling is refused",
)
add(
    "ANA.INTEGRAL_INDEFINITE",
    accept=M + "var f : Function[Real -> Real]\ndef F := antiderivative(f(x), x : Real)",
    weakened=M + "var f : Function[Real -> Real]\nvar F : Function[Real -> Real]\n"
    "var C : Real\nrequire forall x : Real . derivative(F(u), u : Real) = f(x)",
    lost="the family. The defining relation is statable for ONE antiderivative; the "
    "constant of integration is a declared symbol nothing uses, so 'a family of "
    "functions differing by a constant' is not what is represented.",
)
add(
    "ANA.INTEGRAL_LEBESGUE",
    accept=M + "var f : Function[Real -> Real]\nvar mu : Measure[Real]\n"
    "def a := integral(f(x), x : Real, with_respect_to := mu)",
    weakened=M + "var f : Function[Real -> Real]\n"
    "def a := integral(f(x), x : Real, 0.0, 1.0)",
    lost="the measure. `integral` takes two numeric bounds and nothing else, so the "
    "reference measure is fixed and unnameable and sums and Riemann integrals are not "
    "unified.",
)
add(
    "ANA.JACOBIAN",
    accept=M + "var F : Function[Vector[Real, 3] -> Vector[Real, 2]]\ndef J := jacobian(F)",
    weakened=M + "var J : Matrix[Real, 2, 3]\nrequire J = J",
    lost="everything that makes it a Jacobian. A declared 2x3 matrix has the right "
    "shape and no relationship to F.",
)
add(
    "ANA.LIMIT",
    accept=M + "var f : Function[Real -> Real]\ndef l := limit(f(x), x : Real -> 0.0)",
    reject=M + "var f : Function[Real -> Real]\ndef l := limit(f, 0.0)",
    downgrade="one-sided limits are not distinguished -- there is no direction argument "
    "(`from := left` is HML-P201) -- and `limit(...)` denotes a VALUE rather than the "
    "quantified statement the atom says a limit is.",
    judgement="the limit binder exists and is typed. One-sided limits are NOT "
    "distinguished (no direction argument), and the atom's claim that a limit is a "
    "quantified statement rather than an evaluation is not represented -- `limit(...)` "
    "denotes a value.",
)
add(
    "ANA.LIMIT_OF_SEQUENCE",
    accept=M + "var a : Function[Natural -> Real]\n"
    "def l := limit(a(n), n : Natural -> infinity)",
    weakened=M + "var a : Function[Natural -> Real]\n"
    "def l := limit(a(n), n : Natural -> 0.0)",
    lost="the limit point. n -> infinity is unwritable, so a sequence limit must be "
    "spelled as a limit at a finite point, which is a different statement; divergence "
    "and oscillation are not expressible at all.",
)
add(
    "ANA.LINE_SURFACE_INTEGRAL",
    accept=M + "var F : Function[Vector[Real, 3] -> Vector[Real, 3]]\n"
    "var C : Curve[Real, 3]\ndef w := integral(F, over := C)",
    weakened=M + "var f : Function[Real -> Real]\n"
    "def a := integral(f(x), x : Real, 0.0, 1.0)",
    lost="the curve or surface, its parameterisation and its orientation; only a "
    "one-dimensional integral over a numeric interval exists",
)
add(
    "ANA.MEASURABILITY",
    accept=M + "var f : Function[Real -> Real]\nvar F : Set[Set[Real]]\n"
    "var G : Set[Set[Real]]\nrequire measurable(f, from := F, to := G)",
    weakened=M + "var f : Function[Real -> Real]\nvar F : Set[Set[Real]]\n"
    "var G : Set[Set[Real]]\nrequire F = F and G = G",
    lost="measurability itself. The two sigma-algebras can be declared as sets of sets "
    "but no predicate relates a function to them, so measurability cannot be a "
    "hypothesis on anything.",
)
add(
    "ANA.MEASURE",
    accept=M + "var mu : Function[Set[Real] -> NonNegativeReal]\nrequire mu = mu",
    reject=M + "var mu : Function[Set[Real] -> NonNegativeReal]\nvar x : Real\n"
    "require mu = x",
    judgement="a measure encodes as a set function with a non-negative codomain, and "
    "that type is enforced. Countable additivity, the sigma-algebra as the domain, and "
    "'the reference measure of an integral' are all outside what the encoding carries.",
)
add(
    "ANA.METRIC_SPACE",
    accept=M + "var d : Function[Real, Real -> NonNegativeReal]\n"
    "require forall a : Real . forall b : Real . d(a, b) = d(b, a)",
    reject=M + "var d : Function[Real, Real -> NonNegativeReal]\n"
    "require forall a : Real . d(a) = 0.0",
    judgement="a distance function and its axioms are statable as an ordinary typed "
    "function plus propositions, and arity is enforced. There is no metric-space OBJECT, "
    "so balls, induced convergence and 'relative to which metric' are unavailable.",
)
add(
    "ANA.MONOTONICITY_BOUNDEDNESS",
    accept=M + "var f : Function[Real -> Real]\nvar D : Set[Real]\n"
    "require forall a : Real . forall b : Real . "
    "(a in D and b in D and a <= b) => f(a) <= f(b)",
    reject=None,
    judgement="the properties are statable as quantified propositions WITH a domain, "
    "which is what the atom asks for. They are not named, reusable predicates, so the "
    "reject probe records the absence of `monotone`/`convex` rather than a misuse.",
)
add(
    "ANA.MULTIPLE_INTEGRAL",
    accept=M + "var f : Function[Real, Real -> Real]\n"
    "def a := integral(integral(f(x, y), y : Real, 0.0, 1.0), x : Real, 0.0, 1.0)",
    reject=None,
    judgement="iterated integration nests and the order is syntactically visible, which "
    "meets the atom's 'order of integration explicit' clause. A general REGION is not "
    "describable -- bounds are two scalars -- so integration over a non-rectangular "
    "domain is out of reach.",
)
add(
    "ANA.ODE",
    accept=M + "var y : Function[Real -> Real]\nvar t : Real\n"
    "require derivative(y(t), t : Real) = y(t)",
    weakened=M + "var y : Function[Real -> Real]\nvar t : Real\n"
    "require derivative(y(u), u : Real) = y(t)",
    lost="the tie between the differentiation point and the independent variable. "
    "y'(t) = y(t) with ONE t is rejected (HML-N302: the binder shadows the declared t), "
    "so the two sides must use different symbols and nothing says they are the same "
    "point. The unknown function and the ORDER are not identified either, because there "
    "is no equation object.",
)
add(
    "ANA.PARTIAL_DERIVATIVE",
    accept=M + "var f : Function[Real, Real -> Real]\nvar y : Real\n"
    "def d := derivative(f(x, y), x : Real)",
    reject=M + "var f : Function[Real, Real -> Real]\nvar y : Real\n"
    "def d := derivative(f(x, y), x)",
    judgement="the differentiation variable is explicit, so d/dx of a two-argument "
    "function is distinguishable from d/dy. Which variables are HELD CONSTANT is only "
    "implicit in the argument list; there is no held-constant annotation, which is the "
    "half of the atom that thermodynamics actually needs.",
)
add(
    "ANA.PARTIAL_FUNCTION",
    accept=M + "var f : Function[PositiveReal -> Real]\n"
    "require forall s : PositiveReal . f(s) = log(s)",
    reject=M + "var f : Function[PositiveReal -> Real]\nvar x : Real\n"
    "require f(x) = 0.0",
    note="the definedness set is carried by the domain refinement type. Enforcement is "
    "SPLIT: applying a `def`-declared function outside its declared domain is refused "
    "(HML-T472) and a builtin's domain is refused (HML-T427), but applying a "
    "FUNCTION-TYPED VARIABLE outside its declared domain is not checked at all -- which "
    "is what the reject probe exercises. The same hole is recorded under "
    "EPIS.VALIDITY_DOMAIN.",
)
add(
    "ANA.PDE",
    accept=M + "var u : Function[Real, Real -> Real]\nvar t : Real\nvar z : Real\n"
    "require derivative(u(t, z), t : Real) = "
    "derivative(derivative(u(t, z), z : Real), z : Real)",
    weakened=M + "var u : Function[Real, Real -> Real]\nvar t : Real\nvar z : Real\n"
    "require derivative(u(a, z), a : Real) = "
    "derivative(derivative(u(t, b), b : Real), c : Real)",
    lost="the identification of the differentiation variables with the function's own "
    "arguments. Every binder must be a FRESH symbol (HML-N302), so the heat equation "
    "compiles only when each partial is taken in a different invented name and nothing "
    "records that they are the same variable. There is no domain, no boundary and no "
    "PDE object either.",
)
add(
    "ANA.PIECEWISE",
    accept=M + "var x : Real\ndef f := if x > 0.0 then x else 0.0",
    weakened=M + "var f : Function[Real -> Real]\nrequire forall x : Real . "
    "(x > 0.0 => f(x) = x) and (x <= 0.0 => f(x) = 0.0)",
    lost="the case construct, and with it any mechanical exhaustiveness or "
    "mutual-exclusivity check. The guards are ordinary implications the compiler does "
    "not relate to each other.",
)
add(
    "ANA.POWER_SERIES",
    accept=M + "var a : Function[Natural -> Real]\nvar x : Real\n"
    "def s := series(a(n) * (x - 0.0) ** n, n : Natural, 0, infinity)",
    weakened=M + "var a : Function[Natural -> Real]\nvar x : Real\n"
    "def s := a(0) + a(1) * x + a(2) * x ** 2",
    lost="the infinite sum, the centre as a recorded attribute and the radius of "
    "convergence; only a finite truncation is writable",
)
add(
    "ANA.SERIES",
    accept=M + "var a : Function[Natural -> Real]\n"
    "def s := sum(a(n), n : Natural, 1, infinity)",
    weakened=M + "var v : Vector[Real, N]\ndef s := sum(v)",
    lost="infiniteness. `sum` is a one-argument aggregate over a finite-shaped vector; "
    "there is no index binder, no range, no limit of partial sums, and absolute versus "
    "conditional convergence cannot be distinguished.",
)
add(
    "ANA.SIGMA_ALGEBRA",
    accept=M + "var F : SigmaAlgebra[Real]\nrequire F = F",
    weakened=M + "var F : Set[Set[Real]]\nrequire F = F",
    lost="closure under complement and countable union. `Set[Set[Real]]` types the "
    "carrier and nothing else, so a filtration or a conditioning sigma-algebra is a "
    "collection with no properties.",
)
add(
    "ANA.SPECIAL_FUNCTIONS",
    accept=M + "param s : PositiveReal\ndef g := gamma(s)",
    weakened=M + "param s : PositiveReal\ndef g := log(s)",
    lost="every special function except log/exp/sqrt/sin/cos/tan/abs. Gamma, Beta, "
    "Bessel and erf have no spelling, and no branch-cut or pole data is recorded for "
    "the ones that do exist.",
)
add(
    "ANA.SUP_INF",
    accept=M + "var S : Set[Real]\ndef s := supremum(S)",
    weakened=M + "var S : Set[Real]\nvar s : Real\n"
    "require (forall x : Real . x in S => x <= s) and "
    "(forall u : Real . (forall x : Real . x in S => x <= u) => s <= u)",
    lost="sup/inf as operations. The least-upper-bound property is statable by hand, so "
    "the mathematics survives, but an unattained or infinite supremum has no value to "
    "denote and the max/sup distinction is not made anywhere.",
)
add(
    "ANA.TAYLOR_EXPANSION",
    accept=M + "var f : Function[Real -> Real]\nvar x : Real\nvar a : Real\n"
    "def t := taylor(f, at := a, order := 2)",
    weakened=M + "var f : Function[Real -> Real]\nvar x : Real\nvar a : Real\n"
    "var R : Real\nrequire f(x) = f(a) + derivative(f(u), u : Real) * (x - a) + R",
    lost="the remainder's status. `R` is an unconstrained Real, so the expansion is an "
    "identity with a free symbol rather than a bounded-error statement -- the atom's "
    "'not an unqualified equality' requirement is exactly what is not met.",
)
add(
    "ANA.TRANSFORM",
    accept=M + "var f : Function[Real -> Real]\ndef F := fourier(f)",
    weakened=M + "var f : Function[Real -> Real]\nvar w : Real\n"
    "def F := integral(f(t) * cos(w * t), t : Real, 0.0, 1.0)",
    lost="the transform as an operator and its convention (sign, 2-pi placement), plus "
    "the infinite domain the definition needs",
)
add(
    "ANA.UNIFORM_CONTINUITY",
    accept=M + "var f : Function[Real -> Real]\n"
    "require forall e : PositiveReal . exists d : PositiveReal . "
    "forall a : Real . forall b : Real . abs(a - b) < d => abs(f(a) - f(b)) < e",
    structural=("hash_checks", "quantifier_order_changes_the_hash"),
    note="uniformity IS quantifier order, and the only meaningful enforcement question "
    "is whether swapping the quantifiers yields a different object. The executed hash "
    "check answers it. The named predicate `uniformly_continuous` does not exist "
    "(HML-N306); the epsilon-delta unfolding is the encoding measured here.",
)
add(
    "ANA.VARIATIONAL_PROBLEM",
    accept=M + "var J : Function[Function[Real -> Real] -> Real]\n"
    "param f : Function[Real -> Real]\nminimise J(f)",
    reject=M + "var J : Function[Function[Real -> Real] -> Real]\nminimise J",
    judgement="minimising over a function-typed param parses and type-checks, so the "
    "shape of a variational problem is reachable. The ADMISSIBLE CLASS -- which the "
    "atom says must be stated -- has no place to go: `require` constraints are not "
    "scoped to the optimisation (see OPT.CONSTRAINT_SCOPE).",
)

# ===========================================================================
# E. PROBABILITY  (50 atoms)
# ===========================================================================

add(
    "PROB.ARITHMETIC_ON_RANDOM_VARIABLES",
    accept=RVXY + "def Z := X + Y",
    reject=RVX + "var A : Matrix[Real, 2, 2]\ndef Z := X + A",
    judgement="X + Y types as a random variable, so measurable arithmetic lifts. "
    "Whether the RESULT's law depends on the joint law is not represented at all -- no "
    "law is derived for Z -- so the dependence-preserving half of the atom is unmet.",
)
add(
    "PROB.BAYES_RULE",
    accept=M + "param t : Probability\nprior t ~ Beta(alpha := 1.0, beta := 1.0)\n"
    "obs y : Bool = true\nlikelihood y | t ~ Bernoulli(prob := t)\ninfer posterior t",
    reject=M + "param t : Probability\nobs y : Bool = true\n"
    "likelihood y | t ~ Bernoulli(prob := t)\ninfer posterior t",
    note="the reject probe checks that a posterior without a prior is refused, which is "
    "the structural content of the rule",
)
add(
    "PROB.CDF",
    accept=RVX + "def F := cdf(X, 0.0)",
    weakened=RVX + "def F := probability(X <= 0.0)",
    lost="the CDF as a function. A single evaluated probability is a number; "
    "right-continuity, monotonicity and the 0/1 limits have no object to be properties of.",
)
add(
    "PROB.CHANGE_OF_VARIABLES_JACOBIAN",
    accept=RVX + "def Y := exp(X)\ndef J := jacobian(exp)",
    weakened=RVX + "def Y := exp(X)",
    lost="the density transformation. The pushforward variable is typed correctly, but "
    "no density is derived, no Jacobian determinant appears, and the invertibility "
    "requirement is never raised.",
)
add(
    "PROB.CLT",
    accept=M + "index i : Natural\nrv X : RandomVariable[Real]\n"
    "law X ~ Normal(location := 0.0, scale := 1.0)\n"
    "require converges(X, to := Normal(location := 0.0, scale := 1.0), "
    "mode := distribution)",
    weakened=RVX + "require variance(X) = 1.0",
    lost="the theorem. There is no convergence-in-distribution relation and no "
    "normalised sum over an index, so only a finite-variance hypothesis is writable.",
)
add(
    "PROB.CONDITIONAL_DISTRIBUTION",
    accept=M + "param t : Probability\nrv X : RandomVariable[Bool]\n"
    "likelihood X | t ~ Bernoulli(prob := t)",
    reject=M + "param t : Probability\nrv X : RandomVariable[Bool]\n"
    "likelihood X | t ~ Bernoulli(prob := 2.0)",
    note="the `|` given-list is HML's own conditional-law idiom",
)
add(
    "PROB.CONDITIONAL_EXPECTATION",
    accept=RVXY + "def m := expectation(X | Y)",
    reject=RVXY + "require expectation(X | Y) = Y",
    judgement="E[X|Y] is typed as a RandomVariable, which is precisely the atom's "
    "requirement, and the reject probe confirms it: `= Y` builds an Event that "
    "`require` refuses (HML-T480) rather than a numeric equation. The tower property is "
    "not statable, since equality of random variables is not a proposition.",
)
add(
    "PROB.CONDITIONAL_INDEPENDENCE",
    accept=RVXY + "rv Z : RandomVariable[Real]\n"
    "law Z ~ Normal(location := 0.0, scale := 1.0)\n"
    "require independent(X, Y given Z)",
    weakened=RVXY + "require independent(X, Y)",
    lost="the conditioning variable, and with it the whole point of the atom. The "
    "`given` form promised by the grammar contract does not parse (HML-P201), so only "
    "marginal independence is expressible -- which the atom says neither implies nor is "
    "implied by the conditional kind.",
)
add(
    "PROB.CONDITIONAL_PROBABILITY",
    accept=M + "var A : Event\nvar B : Event\nrequire probability(A | B) = 0.5",
    reject=M + "var A : Proposition\nvar B : Proposition\n"
    "require probability(A | B) = 0.5",
    note="Event and Proposition are deliberately incomparable; P(.) of a Proposition is "
    "refused. The P(B) > 0 positivity condition is NOT attached.",
)
add(
    "PROB.CONDITIONING_ON_SIGMA_ALGEBRA",
    accept=RVX + "var F : Set[Set[Real]]\ndef m := expectation(X | F)",
    weakened=RVXY + "def m := expectation(X | Y)",
    lost="the sigma-algebra. Conditioning is on a random variable only; a sub-sigma-"
    "algebra cannot be the conditioning object, so filtrations and the projection "
    "characterisation are unreachable.",
)
add(
    "PROB.CONVERGENCE_MODES",
    accept=RVX + "require converges(X, to := 0.0, mode := probability)",
    weakened=RVX + "require probability(X = 0.0) = 1.0",
    lost="all four modes and the implication ordering among them. No stochastic "
    "convergence relation exists at any mode.",
)
add(
    "PROB.COPULA",
    accept=RVXY + "def C := copula(joint(X, Y))",
    weakened=RVXY + "def j := joint(X, Y)",
    lost="the separation of marginals from dependence. `joint` yields one opaque "
    "distribution; nothing extracts marginals from it and no dependence structure on "
    "the unit cube exists.",
)
add(
    "PROB.DISTRIBUTED_AS",
    accept=RVX,
    reject=M + "rv X : RandomVariable[Real]\nvar d : Distribution[Real]\nrequire X = d",
    note="`~` relates RandomVariable[T] to Distribution[T]; `=` between them is refused",
)
add(
    "PROB.DISTRIBUTION_FAMILY",
    accept=M + "def d : Distribution[Real] := Normal(location := 0.0, scale := 1.0)",
    reject=M + "def d : Distribution[Real] := Normal(mean := 0.0, sd := 1.0)",
    note="role labels are mandatory and are checked against the family's declared "
    "parameterisation, which is the atom's 'convention explicit' clause",
)
add(
    "PROB.DISTRIBUTION_OBJECT",
    accept=M + "def d : Distribution[Real] := Normal(location := 0.0, scale := 1.0)",
    reject=M + "def d : Distribution[Real] := Normal(location := 0.0, scale := 1.0)\n"
    "var x : Real\nrequire x = d",
    note="a distribution is never a value of its support",
)
add(
    "PROB.DIVERGENCE",
    accept=M + "def a : Distribution[Real] := Normal(location := 0.0, scale := 1.0)\n"
    "def b : Distribution[Real] := Normal(location := 1.0, scale := 1.0)\n"
    "def d := kl(a, b)",
    weakened=M + "def a : Distribution[Real] := Normal(location := 0.0, scale := 1.0)\n"
    "def b : Distribution[Real] := Normal(location := 1.0, scale := 1.0)\n"
    "var d : NonNegativeReal\nrequire d >= 0.0",
    lost="the divergence. A non-negative Real declared beside two distributions is not "
    "a functional of them; asymmetry and absolute continuity have nothing to qualify.",
)
add(
    "PROB.ENTROPY_INFORMATION",
    accept=RVX + "def h := entropy(X)",
    weakened=RVX + "var h : Real\nrequire h = h",
    lost="entropy and mutual information entirely, together with the log base and the "
    "reference measure the atom requires to be declared",
)
add(
    "PROB.EVENT",
    accept=M + "var A : Event\nrequire probability(A) = 0.5",
    reject=M + "var A : Event\nrequire A",
    note="Event is a distinct type: `require` refuses it (HML-T480) precisely because "
    "an event is not a proposition, which is this atom's central distinction",
)
add(
    "PROB.EXCHANGEABILITY",
    accept=M + "index i : Natural\nrv X : RandomVariable[Real]\n"
    "law X ~ Normal(location := 0.0, scale := 1.0)\nrequire exchangeable(X)",
    weakened=M + "index i : Natural\nrv X : RandomVariable[Real]\n"
    "law X ~ Normal(location := 0.0, scale := 1.0)",
    lost="permutation invariance of the joint law. There is no joint law over an "
    "indexed family to be invariant, so exchangeability cannot even be stated, let "
    "alone distinguished from i.i.d.",
)
add(
    "PROB.EXPECTATION",
    accept=RVX + "require expectation(X) = 0.0",
    reject=M + "var x : Real\nrequire expectation(x) = 0.0",
    judgement="expectation(X) is a first-class term over a random variable and refuses "
    "a non-random argument. The DISTRIBUTION it integrates against is implicit in the "
    "`law` statement rather than an argument, so the atom's 'must be explicit' clause "
    "is met only by module context.",
)
add(
    "PROB.FILTRATION",
    accept=M + "var F : Filtration[Real]\nrequire F = F",
    weakened=M + "var F : Set[Set[Real]]\nrequire F = F",
    lost="the increasing family, the time index and adaptedness; a bare set of sets has "
    "no order and no process attached",
)
add(
    "PROB.FUNCTION_RETURNING_DISTRIBUTION",
    accept=M + "def kern(s : PositiveReal) : Distribution[Real] := "
    "Normal(location := 0.0, scale := s)",
    reject=M + "def kern(s : PositiveReal) : Distribution[Real] := s",
    note="a Markov kernel is typed as a function into Distribution[T] with no sampling",
)
add(
    "PROB.HIERARCHICAL_MODEL",
    accept=M + "param mu : Real\nparam s : PositiveReal\n"
    "prior mu ~ Normal(location := 0.0, scale := 1.0)\n"
    "prior s ~ HalfNormal(scale := 1.0)\nobs y : Real = 1.0\n"
    "likelihood y | mu, s ~ Normal(location := mu, scale := s)",
    reject=M + "param mu : Real\nprior mu ~ Normal(location := mu, scale := 1.0)",
    note="dependency order is explicit in the given-list and cycles are rejected, which "
    "is the atom's acyclicity requirement",
)
add(
    "PROB.IID",
    accept=M + "index i : Natural\nrv X : RandomVariable[Real]\n"
    "law X[i] ~ Normal(location := 0.0, scale := 1.0)",
    weakened=M + "index i : Natural\nrv X : RandomVariable[Real]\n"
    "law X ~ Normal(location := 0.0, scale := 1.0)",
    lost="the family. There is no subscript form, so `X` is one random variable and the "
    "index declaration is decorative: neither independence across i nor identical "
    "distribution across i is stated by anything.",
)
add(
    "PROB.INDEPENDENCE",
    accept=RVXY + "require independent(X, Y)",
    reject=M + "var x : Real\nvar y : Real\nrequire independent(x, y)",
    judgement="independence is a first-class relation and refuses non-random operands. "
    "Pairwise versus MUTUAL independence is not distinguished -- independent(X, Y, Z) "
    "has one reading -- and the measure it is relative to is never named.",
)
add(
    "PROB.INDEXED_FAMILY_RV",
    accept=M + "index i : Natural\nrv X : RandomVariable[Real]\n"
    "law X ~ Normal(location := 0.0, scale := 1.0)",
    reject=M + "index i : Natural\nrv X : RandomVariable[Real]\n"
    "law X ~ Normal(location := i, scale := 1.0)",
    judgement="this is the audit's own probe and it compiles. The reject arm asks "
    "whether the family can DEPEND on the index at all; the result is recorded as "
    "measured, and either outcome is informative -- acceptance would show the index is "
    "usable, rejection shows the family is not really indexed.",
)
add(
    "PROB.JOINT",
    accept=RVXY + "def j := joint(X, Y)",
    reject=M + "var x : Real\nvar y : Real\ndef j := joint(x, y)",
    judgement="joint(X, Y) is a Distribution over the pair. It does not DETERMINE the "
    "marginals in any operational sense -- `marginal` does not exist -- so the atom's "
    "defining property is stated by the type name only.",
)
add(
    "PROB.LLN",
    accept=RVX + "require converges(mean(X), to := expectation(X), mode := almost_sure)",
    weakened=RVX + "require expectation(X) = 0.0",
    lost="the theorem: no sample average over an index, no convergence relation and no "
    "mode",
)
add(
    "PROB.MARGINAL",
    accept=RVXY + "def j := joint(X, Y)\ndef m := marginal(j, X)",
    weakened=RVXY + "def j := joint(X, Y)",
    lost="marginalisation. The joint exists as an object but nothing integrates a "
    "variable out of it, so the marginalised variable is never identified.",
)
add(
    "PROB.MARKOV_PROPERTY",
    accept=RVXY + "rv Z : RandomVariable[Real]\n"
    "law Z ~ Normal(location := 0.0, scale := 1.0)\n"
    "require independent(Z, X given Y)",
    weakened=RVXY + "require independent(X, Y)",
    lost="the conditioning that IS the Markov property. Without conditional "
    "independence (HML-P201) the statement degenerates to marginal independence, which "
    "is a different and stronger claim.",
)
add(
    "PROB.MARTINGALE",
    accept=RVXY + "require expectation(X | Y) = Y",
    weakened=RVXY + "def m := expectation(X | Y)",
    lost="the defining equation. E[X|Y] is a RandomVariable, so `= Y` is an Event that "
    "`require` refuses; the martingale property therefore cannot be asserted, only the "
    "conditional expectation named.",
)
add(
    "PROB.MGF_CF",
    accept=RVX + "def m := mgf(X)",
    weakened=RVX + "def m := expectation(exp(X))",
    lost="the transform as a function of its argument and its domain of existence. "
    "E[exp(X)] is the MGF at ONE point (t = 1) with no t to vary, and the "
    "characteristic function needs complex values that do not exist.",
)
add(
    "PROB.MIXTURE",
    accept=M + "def d := 0.3 * Normal(location := 0.0, scale := 1.0) + "
    "0.7 * Normal(location := 1.0, scale := 1.0)",
    weakened=M + "def a : Distribution[Real] := Normal(location := 0.0, scale := 1.0)\n"
    "def b : Distribution[Real] := Normal(location := 1.0, scale := 1.0)",
    lost="the convex combination. Distributions do not support scalar multiplication or "
    "addition (HML-T430/T431), so a mixture cannot be formed and cannot be "
    "distinguished from a sum of random variables.",
)
add(
    "PROB.MOMENT",
    accept=RVX + "def m := expectation(X ** 3)",
    reject=M + "var x : Real\ndef m := expectation(x ** 3)",
    judgement="raw moments are expressible as expectations of powers, and variance is a "
    "keyword. Central and standardised moments, cumulants, and existence conditions of "
    "order k have no representation.",
)
add(
    "PROB.PARAMETER_ROLE",
    accept=M + "def d : Distribution[Real] := Normal(location := 0.0, scale := 1.0)",
    reject=M + "def d : Distribution[Real] := Normal(location := 0.0, scale := -1.0)",
    note="roles are mandatory labels and carry constraints -- scale must be PositiveReal",
)
add(
    "PROB.PDF",
    accept=RVX + "def f := density(X, 0.0)",
    weakened=RVX + "def p := probability(X <= 0.0)",
    lost="the density. A probability is not a density -- it cannot exceed one and "
    "carries no reference measure -- so substituting one for the other is exactly the "
    "confusion the atom exists to prevent.",
)
add(
    "PROB.PMF",
    accept=M + "rv K : RandomVariable[Natural]\n"
    "law K ~ Binomial(trials := 10, prob := 0.5)\ndef p := pmf(K, 3)",
    weakened=M + "rv K : RandomVariable[Natural]\n"
    "law K ~ Binomial(trials := 10, prob := 0.5)\ndef p := probability(K = 3)",
    lost="the mass FUNCTION. P(K = 3) is one evaluated event probability; there is no "
    "function over the support and no summing-to-one condition.",
)
add(
    "PROB.PROBABILITY_MEASURE",
    accept=M + "var P : Function[Set[Real] -> Probability]\nrequire P = P",
    reject=M + "var P : Function[Set[Real] -> Probability]\nvar x : Real\nrequire P = x",
    judgement="a probability measure encodes as a set function into Probability, and "
    "that codomain refinement is enforced. Total mass one and countable additivity are "
    "not: nothing states them and nothing checks them.",
)
add(
    "PROB.PROBABILITY_SPACE",
    accept=M + "var S : ProbabilitySpace[Real]\nrequire S = S",
    weakened=M + "var Om : Set[Real]\nvar F : Set[Set[Real]]\n"
    "var P : Function[Set[Real] -> Probability]\nrequire P = P",
    lost="the triple as ONE nameable object. The three components can be declared "
    "separately but nothing binds them, so 'these two random objects live on the same "
    "space' -- the reason the atom exists -- is unstatable.",
)
add(
    "PROB.PUSHFORWARD",
    accept=RVX + "def Y := exp(X)",
    reject=M + "var A : Matrix[Real, 2, 2]\ndef Y := exp(A)",
    judgement="measurable lifting at an application site is real: exp(X) types as "
    "RandomVariable[PositiveReal]. The LAW of the pushforward is not derived, so 'the "
    "distribution of g(X)' remains implicit.",
)
add(
    "PROB.QUANTILE",
    accept=RVX + "def q := quantile(X, 0.5)",
    weakened=RVX + "var q : Real\nrequire probability(X <= q) >= 0.5",
    lost="the generalised inverse and its convention. The weakened form characterises "
    "one quantile by an inequality; there is no quantile function and no tie-breaking "
    "rule for a non-strictly-increasing CDF.",
)
add(
    "PROB.RANDOM_FUNCTION",
    accept=M + "rv W : RandomVariable[Function[Real -> Real]]\n"
    "require probability(W = W) = 1.0",
    reject=M + "rv W : RandomVariable[Function[Real -> Real]]\nvar x : Real\n"
    "require W = x",
    note="the value space may be a function space, so a Gaussian-process-shaped "
    "declaration types correctly; no distribution family over function spaces exists",
)
add(
    "PROB.RANDOM_MATRIX",
    accept=M + "rv S : RandomVariable[Matrix[Real, 3, 3]]\n"
    "require probability(S = S) = 1.0",
    reject=M + "rv S : RandomVariable[Matrix[Real, 3, 3]]\n"
    "rv T : RandomVariable[Matrix[Real, 2, 2]]\nrequire probability(S = T) = 1.0",
)
add(
    "PROB.RANDOM_VARIABLE",
    accept=RVX + "require probability(X = X) = 1.0",
    reject=RVX + "def v : Real := X",
    note="a random variable is neither its distribution nor its value. The reject probe "
    "attempts to bind it to its support type and is refused (HML-T403); the "
    "distribution barrier is covered by PROB.DISTRIBUTED_AS.",
)
add(
    "PROB.REALIZATION",
    accept=M + "obs y : Real = 1.0",
    reject=M + "obs y : Real = 1.0\nrv X : RandomVariable[Real]\n"
    "law X ~ Normal(location := 0.0, scale := 1.0)\nrequire y = X",
    note="`obs` types the observed value as an element of the value space and it does "
    "not unify with the random variable",
)
add(
    "PROB.STOCHASTIC_PROCESS",
    accept=M + "rv W : RandomVariable[Function[Real -> Real]]\n"
    "require probability(W = W) = 1.0",
    reject=M + "rv W : RandomVariable[Function[Real -> Real]]\nvar t : Real\n"
    "require probability(W(t) = 0.0) = 1.0",
    judgement="a process encodes as a function-valued random variable, which types "
    "correctly. There is no index SET as such and the reject arm tests whether the "
    "process can be evaluated at a time -- the outcome is recorded either way.",
)
add(
    "PROB.STOPPING_TIME",
    accept=M + "rv T : RandomVariable[Real]\nvar F : Filtration[Real]\n"
    "require stopping_time(T, F)",
    weakened=M + "rv T : RandomVariable[Real]\n"
    "law T ~ Exponential(rate := 1.0)",
    lost="everything. A stopping time needs a filtration (absent) and a measurability "
    "condition relating {T <= t} to it (absent); only an ordinary positive random "
    "variable survives.",
)
add(
    "PROB.SUPPORT",
    accept=M + "rv X : RandomVariable[PositiveReal]\nlaw X ~ Exponential(rate := 1.0)",
    reject=M + "rv X : RandomVariable[PositiveReal]\n"
    "law X ~ Normal(location := 0.0, scale := 1.0)",
    note="the support is part of the family's spec and is checked against the declared "
    "value type (HML-T411), which constrains admissible observations",
)
add(
    "PROB.TRUNCATION_CENSORING",
    accept=M + "def d : Distribution[Real] := "
    "truncated(Normal(location := 0.0, scale := 1.0), lower := 0.0)",
    weakened=M + "rv X : RandomVariable[PositiveReal]\nlaw X ~ HalfNormal(scale := 1.0)",
    lost="truncation as an OPERATION on a distribution, the renormalisation it implies, "
    "and censoring altogether. Naming a different family that happens to be the "
    "truncated one is not the same statement.",
)
add(
    "PROB.VARIANCE_COVARIANCE",
    accept=RVX + "require variance(X) >= 0.0",
    reject=M + "var x : Real\nrequire variance(x) >= 0.0",
    judgement="variance is a keyword expression over a random variable and refuses a "
    "non-random argument. Covariance and correlation do not exist, so the PSD "
    "covariance matrix and the [-1,1] correlation typing the atom demands are absent.",
)

# ===========================================================================
# F. STATISTICS  (44 atoms)
# ===========================================================================

LIK = (
    M
    + "param t : Probability\nobs y : Bool = true\n"
    + "likelihood y | t ~ Bernoulli(prob := t)\n"
)

add(
    "STAT.BIAS",
    accept=M + "param th : Real\nobs y : Real = 1.0\ndef th_hat := y\n"
    "rv Y : RandomVariable[Real]\nlaw Y ~ Normal(location := th, scale := 1.0)\n"
    "def b := expectation(Y) - th",
    reject=M + "param th : Real\nobs y : Real = 1.0\ndef th_hat := y\n"
    "def b := expectation(th_hat) - th",
    judgement="E[estimator] - target is writable when the estimator is expressed as a "
    "random variable. The reject arm asks whether expectation of a DATA-valued "
    "definition is refused -- i.e. whether the estimator/estimate distinction is "
    "enforced at the point where bias is computed.",
)
add(
    "STAT.BOOTSTRAP",
    accept=M + "obs y : Real = 1.0\ndef b := bootstrap(y, replicates := 1000)",
    weakened=M + "obs y : Real = 1.0\ndef b := y",
    lost="resampling entirely, and with it the approximation status the atom requires "
    "to be explicit. There is no dataset to resample and no replicate count.",
)
add(
    "STAT.CAUSAL_INTERVENTION",
    accept=RVXY + "def p := probability(Y = 1.0 | do(X = 0.0))",
    weakened=RVXY + "require causes(X, Y)",
    lost="the do-operator. `causes(X, Y)` asserts a causal relation but P(Y | do(X)) "
    "has no spelling, so intervention and conditioning cannot be written differently -- "
    "which is precisely the confusion this atom names.",
)
add(
    "STAT.CONFIDENCE_INTERVAL",
    accept=M + "param th : Real\nobs y : Real = 1.0\n"
    "def ci := confidence_interval(th, level := 0.95)",
    weakened=M + "param th : Real\nvar lo : Real\nvar hi : Real\n"
    "require lo <= th and th <= hi",
    lost="the randomness of the interval and the coverage property of the PROCEDURE. "
    "The weakened form is a claim about one realised interval, which is the "
    "misinterpretation the atom exists to block.",
)
add(
    "STAT.CONFOUNDING",
    accept=RVXY + "rv Z : RandomVariable[Real]\n"
    "law Z ~ Normal(location := 0.0, scale := 1.0)\n"
    "require independent(X, Y given Z)",
    weakened=RVXY + "require associated(X, Y)",
    lost="adjustment sets. Conditional independence does not parse, so the criterion "
    "that identifies which variables must be conditioned on cannot be expressed at all.",
)
add(
    "STAT.CONSISTENCY",
    accept=M + "param th : Real\nrv T : RandomVariable[Real]\n"
    "law T ~ Normal(location := th, scale := 1.0)\n"
    "require converges(T, to := th, mode := probability)",
    weakened=M + "param th : Real\nrv T : RandomVariable[Real]\n"
    "law T ~ Normal(location := th, scale := 1.0)\nrequire expectation(T) = th",
    lost="convergence and its mode; unbiasedness is not consistency and there is no "
    "sample size to grow",
)
add(
    "STAT.COUNTERFACTUAL",
    accept=RVX + "rv Y1 : RandomVariable[Real]\n"
    "law Y1 ~ Normal(location := 1.0, scale := 1.0)\n"
    "rv Y0 : RandomVariable[Real]\n"
    "law Y0 ~ Normal(location := 0.0, scale := 1.0)\ndef te := Y1 - Y0",
    reject=M + "obs y1 : Real = 1.0\nobs y0 : Real = 0.0\ndef te := y1 - y0",
    judgement="two potential-outcome random variables and their difference type "
    "correctly, so the individual treatment effect is writable. Nothing marks that only "
    "one is observed -- the reject arm tests whether declaring BOTH as `obs` is "
    "refused, which is the fundamental problem of causal inference.",
)
add(
    "STAT.CREDIBLE_INTERVAL",
    accept=M + "param th : Real\nprior th ~ Normal(location := 0.0, scale := 1.0)\n"
    "param p : PosteriorProbability\nrequire p = 0.95",
    reject=M + "param th : Real\nparam p : PosteriorProbability\n"
    "param q : PValue\nrequire p = 0.95 and q = p",
    judgement="PosteriorProbability is a distinct scalar kind, so a posterior-mass "
    "statement is typed differently from a p-value -- which is the atom's real content. "
    "The INTERVAL itself is not an object; only its mass is nameable.",
)
add(
    "STAT.CROSS_VALIDATION",
    not_measured="cross-validation needs a dataset and a partitioning scheme over its "
    "units. STAT.DATASET has no representation, so there is nothing to partition and no "
    "candidate spelling for a fold structure to aim a probe at.",
)
add(
    "STAT.DATASET",
    accept=M + "obs y : Dataset[Real, N]\nrequire y = y",
    weakened=M + "obs y : Real = 1.0",
    lost="everything the atom names: the unit of observation, variable names, "
    "per-variable measurement types and the index. `obs` declares ONE scalar "
    "observation with a literal value; there is no collection.",
)
add(
    "STAT.DESIGN_MATRIX",
    accept=M + "var X : Matrix[Real, N, K]\nvar beta : Vector[Real, K]\n"
    "def eta := X @ beta",
    reject=M + "var X : Matrix[Real, N, K]\nvar beta : Vector[Real, N]\n"
    "def eta := X @ beta",
    judgement="the matrix and its conformability with the coefficient vector are "
    "typed and checked. The MAPPING from variables to columns -- categorical encoding, "
    "contrasts -- has no representation, so the atom's actual subject is absent.",
)
add(
    "STAT.EFFECT_SIZE",
    accept=M + "var d : Quantity[Length]\nvar s : Quantity[Length]\ndef e := d / s",
    reject=M + "param p : PValue\nvar d : Quantity[Length]\nrequire d = p",
    judgement="a standardised effect size is a dimensionless ratio and the dimension "
    "system computes it. The separation from an evidence measure is enforced by "
    "PValue being its own scalar kind, which the reject probe tests.",
)
add(
    "STAT.EFFICIENCY",
    accept=M + "param th : Real\nrv T : RandomVariable[Real]\n"
    "law T ~ Normal(location := th, scale := 1.0)\n"
    "def mse := variance(T) + (expectation(T) - th) ** 2",
    reject=M + "param th : Real\nvar t : Real\n"
    "def mse := variance(t) + (expectation(t) - th) ** 2",
    note="the bias-variance decomposition is writable over a random variable and "
    "refused over a deterministic one; there is no loss function and no bound to "
    "compare against",
)
add(
    "STAT.ESTIMATOR",
    accept=M + "param th : Real\nrv Y : RandomVariable[Real]\n"
    "law Y ~ Normal(location := th, scale := 1.0)\ndef th_hat := Y",
    reject=M + "param th : Real\nobs y : Real = 1.0\ndef th_hat := y\n"
    "require variance(th_hat) >= 0.0",
    judgement="an estimator as a random variable through the data is expressible, and "
    "the reject arm checks that a value-typed estimate is NOT treated as random. There "
    "is no dataset type, so 'a rule mapping a dataset to a value' is only approximated.",
)
add(
    "STAT.FISHER_INFORMATION",
    accept=LIK + "def I := fisher_information(t)",
    weakened=LIK + "var I : Matrix[Real, 1, 1]\nrequire I = I",
    lost="the functional. There is no log-likelihood term, no second derivative with "
    "respect to a parameter, and no expectation over the data, so the matrix is a "
    "declared symbol with no content.",
)
add(
    "STAT.GLM",
    accept=M + "param beta : Vector[Real, K]\nvar X : Matrix[Real, N, K]\n"
    "obs y : Natural = 3\n"
    "likelihood y | beta ~ Poisson(rate := exp(sum(X @ beta)))",
    reject=M + "param beta : Vector[Real, K]\nvar X : Matrix[Real, N, K]\n"
    "obs y : Natural = 3\nlikelihood y | beta ~ Poisson(rate := sum(X @ beta))",
    judgement="family, link and linear predictor are all present as separate pieces "
    "(distribution family, exp(.), X@beta) and the link is REQUIRED because rate must "
    "be PositiveReal -- the reject arm tests exactly that. They are not three "
    "separately identified COMPONENTS of a model object, because there is no model "
    "object.",
)
add(
    "STAT.HYPOTHESIS",
    accept=M + "param mu : Real\ndef H0 := { m : Real | m = 0.0 }\n"
    "def H1 := { m : Real | m != 0.0 }",
    reject=M + "param mu : Real\ndef H0 := { m : Real | m = 0.0 }\nrequire H0 = 0.0",
    judgement="null and alternative are expressible as subsets of the parameter space "
    "via comprehension, and a set does not collapse to a value. Disjointness is not "
    "checked, and simple versus composite is not marked.",
)
add(
    "STAT.IDENTIFIABILITY",
    accept=M + "param a : Real\nparam b : Real\nobs y : Real = 1.0\n"
    "likelihood y | a, b ~ Normal(location := a + b, scale := 1.0)\n"
    "require identifiable(a, b)",
    weakened=M + "param a : Real\nparam b : Real\nobs y : Real = 1.0\n"
    "likelihood y | a, b ~ Normal(location := a + b, scale := 1.0)",
    lost="identifiability. The classically non-identifiable model compiles clean with "
    "no warning, and there is no way to state that distinct parameter values induce "
    "distinct distributions.",
)
add(
    "STAT.LIKELIHOOD_FUNCTION",
    accept=LIK,
    reject=M + "param t : Probability\nobs y : Bool = true\n"
    "likelihood t | y ~ Bernoulli(prob := t)",
    note="the given-list fixes which side is data and which is parameter; reversing it "
    "is a different statement",
)
add(
    "STAT.LINEAR_MODEL",
    accept=M + "param beta : Vector[Real, K]\nparam s : PositiveReal\n"
    "var X : Matrix[Real, N, K]\nobs y : Real = 1.0\n"
    "likelihood y | beta, s ~ Normal(location := sum(X @ beta), scale := s)",
    reject=M + "param beta : Vector[Real, N]\nparam s : PositiveReal\n"
    "var X : Matrix[Real, N, K]\nobs y : Real = 1.0\n"
    "likelihood y | beta, s ~ Normal(location := sum(X @ beta), scale := s)",
    judgement="the error distribution, the shape of X and the conditioning on X are all "
    "present and shape-checked. `sum(X @ beta)` is a workaround: y is a scalar because "
    "there is no dataset, so the per-observation structure is faked.",
)
add(
    "STAT.LOG_LIKELIHOOD",
    accept=LIK + "def ll := log_likelihood(t)",
    weakened=LIK,
    lost="the log-likelihood as a term, its additivity over observations, and the "
    "independence assumption that additivity depends on. The likelihood STATEMENT "
    "exists; nothing denotes its value.",
)
add(
    "STAT.MCMC",
    accept=M + "param mu : Real\nprior mu ~ Normal(location := 0.0, scale := 1.0)\n"
    "obs y : Real = 1.0\nlikelihood y | mu ~ Normal(location := mu, scale := 1.0)\n"
    "infer posterior mu by mcmc(chains := 4)",
    backend=(
        M + "param mu : Real\nprior mu ~ Normal(location := 0.0, scale := 1.0)\n"
        "obs y : Real = 1.0\nlikelihood y | mu ~ Normal(location := mu, scale := 1.0)\n"
        "infer posterior mu",
        "stan",
    ),
    note="`infer posterior` states the inference GOAL; the chain, its target and the "
    "correlated-sample nature of its output exist only in the Stan lowering",
)
add(
    "STAT.MEASUREMENT_SCALE",
    accept=M + "obs y : Ordinal[5] = 3",
    weakened=M + "obs y : Natural = 3",
    lost="the scale. Nominal / ordinal / interval / ratio are not distinguished, so "
    "nothing prevents taking a mean of ordinal codes -- the atom's own example of the "
    "error it exists to prevent.",
)
add(
    "STAT.MISSING_DATA",
    accept=M + "obs y : Real = 1.0\nrv Mi : RandomVariable[Bool]\n"
    "law Mi ~ Bernoulli(prob := 0.1)\nrequire independent(Mi, y given y)",
    weakened=M + "obs y : Real = 1.0\nrv Mi : RandomVariable[Bool]\n"
    "law Mi ~ Bernoulli(prob := 0.1)",
    lost="the mechanism. MCAR/MAR/MNAR are conditional-independence statements about "
    "the missingness indicator, and conditional independence does not parse, so all "
    "three collapse into 'there is an indicator'.",
)
add(
    "STAT.MIXED_EFFECTS",
    accept=M + "index g : Natural\nparam s : PositiveReal\n"
    "param u : Real\nprior u ~ Normal(location := 0.0, scale := s)\n"
    "obs y : Real = 1.0\nlikelihood y | u ~ Normal(location := u, scale := 1.0)",
    reject=M + "index g : Natural\nparam u : Real\n"
    "prior u ~ Normal(location := 0.0, scale := -1.0)\nobs y : Real = 1.0\n"
    "likelihood y | u ~ Normal(location := u, scale := 1.0)",
    judgement="a parameter that is itself random with a hyperparameter scale is exactly "
    "the hierarchical form and it compiles. The GROUPING is not represented -- there is "
    "no indexed family -- so `u` is one random effect, not one per group.",
)
add(
    "STAT.MLE",
    accept=LIK + "infer mle t",
    reject=M + "param t : Probability\ninfer mle t",
    note="MLE requires a likelihood to maximise; without one it is refused. Existence "
    "and uniqueness are not addressed, and the argmax is not an object.",
)
add(
    "STAT.MODEL_SELECTION_CRITERION",
    accept=LIK + "def a := aic(t)",
    weakened=LIK,
    lost="the criteria entirely, and with them the comparability conditions (same data, "
    "same units) the atom says must be part of the statement",
)
add(
    "STAT.MULTIPLE_COMPARISON",
    accept=M + "param p : PValue\ndef adj := bonferroni(p, tests := 20)",
    weakened=M + "param p : PValue\nrequire p <= 0.05",
    lost="the number of tests and the error-rate criterion. A single p-value threshold "
    "carries no multiplicity information, which is the atom's whole subject.",
)
add(
    "STAT.OBSERVATION_VS_LATENT",
    accept=M + "param z : Real\nprior z ~ Normal(location := 0.0, scale := 1.0)\n"
    "obs y : Real = 1.0\nlikelihood y | z ~ Normal(location := z, scale := 1.0)",
    reject=M + "obs z : Real = 1.0\nobs y : Real = 1.0\n"
    "likelihood y | z ~ Normal(location := z, scale := 1.0)\ninfer posterior z",
    judgement="`param` versus `obs` IS the observed/latent distinction and it "
    "determines what may be inferred; the reject arm asks whether inferring a posterior "
    "for an observed quantity is refused.",
)
add(
    "STAT.POPULATION_VS_SAMPLE",
    accept=M + "param theta : Real\nobs y : Real = 1.0",
    reject=M + "param theta : Real\nobs y : Real",
    note="param is fixed-and-unknown, obs is supplied data and must carry a value",
)
add(
    "STAT.POSTERIOR",
    accept=M + "param mu : Real\nprior mu ~ Normal(location := 0.0, scale := 1.0)\n"
    "obs y : Real = 1.0\nlikelihood y | mu ~ Normal(location := mu, scale := 1.0)\n"
    "infer posterior mu",
    reject=M + "obs y : Real = 1.0\ninfer posterior y",
    note="the posterior is a named inference target distinct from the likelihood and "
    "from a point estimate (`infer mle` is a different statement)",
)
add(
    "STAT.POSTERIOR_PREDICTIVE",
    accept=M + "param mu : Real\nprior mu ~ Normal(location := 0.0, scale := 1.0)\n"
    "obs y : Real = 1.0\nlikelihood y | mu ~ Normal(location := mu, scale := 1.0)\n"
    "infer predictive y",
    weakened=M + "param mu : Real\nprior mu ~ Normal(location := 0.0, scale := 1.0)\n"
    "obs y : Real = 1.0\nlikelihood y | mu ~ Normal(location := mu, scale := 1.0)\n"
    "infer posterior mu",
    lost="the predictive distribution. There is no integration of the likelihood over "
    "the posterior and no new-observation object, so only the parameter posterior is "
    "reachable.",
)
add(
    "STAT.POWER",
    accept=M + "param mu : Real\ndef pw := power(mu, level := 0.05)",
    weakened=M + "param b : Probability\nrequire b = 0.8",
    lost="power as a FUNCTION of the alternative. A single Probability constant is the "
    "'single number' the atom explicitly says power is not.",
)
add(
    "STAT.PRIOR",
    accept=M + "param mu : Real\nprior mu ~ Normal(location := 0.0, scale := 1.0)",
    reject=M + "var mu : Real\nprior mu ~ Normal(location := 0.0, scale := 1.0)",
    note="a prior requires the symbol to be a param -- i.e. to be the kind of thing a "
    "distribution over the parameter space can range over",
)
add(
    "STAT.P_VALUE",
    accept=M + "param p : PValue\nrequire p <= 0.05",
    reject=M + "param p : PValue\nparam q : PosteriorProbability\n"
    "def r : PosteriorProbability := p",
    note="the prosecutor's fallacy is blocked in the type system: PValue and "
    "PosteriorProbability are incomparable (D-022)",
)
add(
    "STAT.RESIDUAL",
    accept=M + "param mu : Real\nrv E : RandomVariable[Real]\n"
    "law E ~ Normal(location := 0.0, scale := 1.0)\nobs y : Real = 1.0\n"
    "def r := y - mu",
    reject=M + "param mu : Real\nrv E : RandomVariable[Real]\n"
    "law E ~ Normal(location := 0.0, scale := 1.0)\nobs y : Real = 1.0\n"
    "def r := y - mu\nrequire r = E",
    note="the unobservable error is a RandomVariable and the computed residual is a "
    "value; equating them is refused, which is the atom's distinction",
)
add(
    "STAT.SAMPLING_DESIGN",
    accept=M + "obs y : Real = 1.0\ndesign stratified by y",
    weakened=M + "obs y : Real = 1.0",
    lost="the design. Randomisation, stratification, clustering and blocking have no "
    "representation, so how units were selected -- which determines what the data "
    "licenses -- is not part of the model.",
)
add(
    "STAT.SAMPLING_DISTRIBUTION",
    accept=M + "param th : Real\nrv T : RandomVariable[Real]\n"
    "law T ~ Normal(location := th, scale := 1.0)",
    reject=M + "param th : Real\nobs t : Real = 1.0\n"
    "law t ~ Normal(location := th, scale := 1.0)",
    judgement="the law of a statistic under repeated sampling is expressible by "
    "declaring the statistic as a random variable with a law depending on the "
    "parameter. Nothing connects it to a data-generating process or a sample size.",
)
add(
    "STAT.SUFFICIENCY",
    accept=LIK + "require sufficient(y, for := t)",
    weakened=LIK,
    lost="sufficiency. It is a conditional-independence statement (data independent of "
    "the parameter given the statistic) and conditional independence does not parse.",
)
add(
    "STAT.SUMMARY_STATISTIC",
    accept=M + "var v : Vector[Real, N]\ndef m := mean(v)",
    reject=M + "var A : Matrix[Real, 2, 2]\nvar b : Bool\ndef m := mean(b)",
    judgement="mean/sum/prod exist as aggregates over shaped values and refuse "
    "non-aggregates. The CONVENTIONS the atom demands -- variance denominator, quantile "
    "interpolation -- are not recorded, and median/quantile do not exist.",
)
add(
    "STAT.TEST_STATISTIC",
    accept=M + "rv T : RandomVariable[Real]\n"
    "law T ~ StudentT(degrees_of_freedom := 10.0, location := 0.0, scale := 1.0)",
    reject=M + "rv T : RandomVariable[Real]\n"
    "law T ~ StudentT(degrees_of_freedom := -10.0, location := 0.0, scale := 1.0)",
    judgement="a statistic together with its null distribution is exactly a `law` "
    "statement and the family's parameter constraints are enforced. Whether that "
    "distribution is exact or asymptotic is not recordable.",
)
add(
    "STAT.TIME_SERIES",
    accept=M + "index t : Natural\nrv Y : RandomVariable[Real]\n"
    "law Y[t] ~ Normal(location := 0.5 * Y[t - 1], scale := 1.0)",
    weakened=M + "index t : Natural\nrv Y : RandomVariable[Real]\n"
    "law Y ~ Normal(location := 0.0, scale := 1.0)",
    lost="time. Without a subscript form there is no lag, no AR recursion and no "
    "dependence across the index; stationarity has nothing to be a property of.",
)
add(
    "STAT.TYPE_ERRORS",
    accept=M + "param a : Probability\nparam b : Probability\n"
    "require a <= 0.05 and b <= 0.2",
    reject=M + "param a : Probability\nparam q : PValue\ndef r : PValue := a",
    judgement="two error rates are declarable as Probability and the epistemic barrier "
    "stops them being read as p-values. What is NOT present is that each is CONDITIONAL "
    "on a hypothesis -- there is no hypothesis object to condition on.",
)
add(
    "STAT.VARIATIONAL_INFERENCE",
    accept=M + "param mu : Real\nprior mu ~ Normal(location := 0.0, scale := 1.0)\n"
    "obs y : Real = 1.0\nlikelihood y | mu ~ Normal(location := mu, scale := 1.0)\n"
    "infer posterior mu by variational(family := Normal)",
    weakened=M + "param mu : Real\nprior mu ~ Normal(location := 0.0, scale := 1.0)\n"
    "obs y : Real = 1.0\nlikelihood y | mu ~ Normal(location := mu, scale := 1.0)\n"
    "infer posterior mu",
    lost="the approximation. `infer posterior` states the exact target; the variational "
    "family, the divergence being minimised and the fact that the result is an "
    "approximation are all unrepresentable.",
)

# ===========================================================================
# G. DISCRETE  (31 atoms)
# ===========================================================================

add(
    "DISC.ADJACENCY_MATRIX",
    accept=M + "var A : Matrix[Natural, N, N]\nrequire A = A",
    reject=M + "var A : Matrix[Natural, N, K]\nvar B : Matrix[Natural, K, N]\n"
    "require A = B",
    judgement="a square matrix over Natural is a faithful adjacency matrix and squareness "
    "is enforced by the shape variables. The atom's real content -- that the vertex "
    "ordering is arbitrary and results should be order-invariant -- has no "
    "representation, since there is no graph for the matrix to be a view of.",
)
add(
    "DISC.ALGORITHM_COST",
    accept=M + "var n : Natural\nrequire cost(n) = bigO(n * n)",
    weakened=M + "var n : Natural\nvar c : Function[Natural -> NonNegativeReal]\n"
    "require forall m : Natural . c(m) <= 3.0 * m * m",
    lost="the machine model, the measured resource and asymptotic order. A concrete "
    "polynomial bound on a declared function is not a cost statement.",
)
add(
    "DISC.AUTOMATON",
    accept=M + "var A : Automaton\nrequire A = A",
    weakened=M + "var S : Set[Natural]\nvar T : Set[Product[Natural, Natural]]\n"
    "require T = T",
    lost="acceptance, labelling and determinism. States and transitions can be typed as "
    "sets, but nothing makes them an automaton.",
)
add(
    "DISC.BINOMIAL_COEFFICIENT",
    accept=M + "def c := choose(5, 2)",
    weakened=M + "var c : Natural\nvar n : Natural\nvar k : Natural\n"
    "require k <= n => c >= 1",
    lost="the counting function. Only its domain condition can be stated, about a "
    "symbol that is not the coefficient.",
)
add(
    "DISC.BOOLEAN_ALGEBRA",
    accept=M + "var p : Proposition\nvar q : Proposition\nvar r : Proposition\n"
    "require (p and (q or r)) iff ((p and q) or (p and r))",
    reject=M + "var p : Proposition\nvar x : Real\nrequire (p and x) iff p",
    judgement="the lattice laws are statable and the connectives are typed. Canonical "
    "NORMAL FORMS -- CNF/DNF -- are not produced by canonicalisation, so the half of "
    "the atom about normal forms being available is unmet.",
)
add(
    "DISC.COLOURING_PARTITION",
    accept=M + "var V : Set[Natural]\nvar c : Function[Natural -> Natural]\n"
    "var E : Set[Product[Natural, Natural]]\n"
    "require forall u : Natural . forall v : Natural . c(u) = c(v) => u = v",
    reject=None,
    judgement="a colouring is a function and its constraint is a quantified "
    "proposition, so the mathematics is writable by hand. The constraint cannot mention "
    "the edge set, because membership of a PAIR in a set of pairs needs a pair "
    "constructor that does not exist -- so the encoding is not faithful to the "
    "adjacency condition.",
)
add(
    "DISC.COMBINATION",
    accept=M + "def c := choose(5, 2)",
    weakened=M + "var S : Set[Natural]\nvar T : Set[Natural]\n"
    "require forall x : Natural . x in T => x in S",
    lost="the counting. Subsets are expressible as sets; the number of size-k subsets, "
    "and the with/without-repetition distinction, are not.",
)
add(
    "DISC.COMBINATORIAL_IDENTITY",
    accept=M + "var n : Natural\nvar k : Natural\n"
    "require choose(n, k) = choose(n - 1, k - 1) + choose(n - 1, k)",
    weakened=M + "var n : Natural\nvar k : Natural\nrequire k <= n => n - k >= 0",
    lost="the identity and its validity range; without binomial coefficients there is "
    "nothing to state an identity between",
)
add(
    "DISC.COMPLEXITY_CLASS",
    not_measured="complexity classes are collections of PROBLEMS related by reductions. "
    "HML has no problem object (OPT.PROBLEM_AS_OBJECT is also absent) and no reduction "
    "relation, so there is no candidate spelling to execute.",
)
add(
    "DISC.COUNTING_ARGUMENT",
    accept=M + "var A : Set[Natural]\nvar B : Set[Natural]\n"
    "require cardinality(A union B) = cardinality(A) + cardinality(B) - "
    "cardinality(A intersect B)",
    weakened=M + "var A : Set[Natural]\nvar B : Set[Natural]\nrequire A = A and B = B",
    lost="the principles. Inclusion-exclusion needs cardinality and set operations; "
    "neither exists, so pigeonhole and bijective counting are equally unreachable.",
)
add(
    "DISC.DAG",
    accept=M + "var E : Set[Product[Natural, Natural]]\nrequire E = E",
    reject=M + "def a := b + 1.0\ndef b := a + 1.0",
    judgement="acyclicity IS checked in HML -- on the DEFINITION graph and on the "
    "reasoning graph, and the reject probe demonstrates it. It is not checked on a "
    "user-declared graph value, because a graph is only a set of pairs with no "
    "operations. The atom is scored on what the probe shows, and the two graphs are "
    "different objects; this entry is a judgement call and is flagged as one.",
)
add(
    "DISC.DIRECTED_GRAPH",
    accept=M + "var E : Set[Product[Natural, Natural]]\nvar u : Natural\n"
    "var v : Natural\nrequire (u, v) in E",
    weakened=M + "var E : Set[Product[Natural, Natural]]\nrequire E = E",
    lost="edges as usable objects. The type of a set of ordered pairs exists, but there "
    "is no tuple CONSTRUCTOR, so no edge can be written down, no degree computed and no "
    "direction observed.",
)
add(
    "DISC.FACTORIAL",
    accept=M + "def f := factorial(5)",
    weakened=M + "def f := 1 * 2 * 3 * 4 * 5",
    lost="the function and its conventions. A literal product is not factorial, and "
    "0! = 1 has nowhere to be fixed; falling and rising powers are absent too.",
)
add(
    "DISC.FLOW",
    accept=M + "index e : Natural\nparam f : Vector[NonNegativeReal, E]\n"
    "var cap : Vector[NonNegativeReal, E]\nrequire f <= cap\ndef obj := sum(f)\n"
    "maximise obj",
    weakened=M + "param f : Vector[NonNegativeReal, E]\ndef obj := sum(f)\nmaximise obj",
    lost="conservation. Per-vertex balance needs indexed constraints over an incidence "
    "structure; there is no indexed constraint form, so only capacity-free maximisation "
    "of a total survives.",
)
add(
    "DISC.FORMAL_LANGUAGE",
    not_measured="a formal language is a set of strings defined by a grammar. HML has "
    "no string or character type at all and no grammar object, so there is no spelling "
    "that could be tried and reported on.",
)
add(
    "DISC.GENERATING_FUNCTION",
    accept=M + "var a : Function[Natural -> Real]\nvar x : Real\n"
    "def G := series(a(n) * x ** n, n : Natural, 0, infinity)",
    weakened=M + "var a : Function[Natural -> Real]\nvar x : Real\n"
    "def G := a(0) + a(1) * x",
    lost="the formal power series. Only finite truncations are writable, so the "
    "formal/analytic distinction the atom names never arises.",
)
add(
    "DISC.GRAPH",
    accept=M + "var G : Graph[Natural]\nrequire G = G",
    weakened=M + "var V : Set[Natural]\nvar E : Set[Product[Natural, Natural]]\n"
    "require V = V and E = E",
    lost="the graph as one object, and simplicity / loops / multi-edges as declarable "
    "properties. Two unrelated sets are not a graph, and nothing checks that E's "
    "endpoints lie in V.",
)
add(
    "DISC.INDEXED_EXTREMUM",
    accept=M + "var v : Vector[Real, N]\ndef m := max(v)",
    weakened=M + "param x : Real\ndef f := x * x\nminimise f",
    lost="the indexed extremum. `minimise` is a STATEMENT about a whole module, not an "
    "expression over an index set, so argmax over a finite set is not a term and ties "
    "and emptiness are never handled.",
)
add(
    "DISC.LATTICE",
    accept=M + "var a : Real\nvar b : Real\nvar c : Real\n"
    "require (a <= c and b <= c) => (a <= c and b <= c)",
    reject=None,
    judgement="the ORDER exists on scalars and lattice laws are statable as "
    "propositions. Meet and join as operations do not exist at the surface, which the "
    "reject arm records -- even though the type system's own scalar lattice has them "
    "internally.",
)
add(
    "DISC.MATCHING_COVER",
    accept=M + "var E : Set[Product[Natural, Natural]]\nvar Mt : Set[Product[Natural, "
    "Natural]]\nrequire forall e : Product[Natural, Natural] . e in Mt => e in E",
    reject=None,
    judgement="a sub-collection of edges is expressible as a subset condition. The "
    "DEFINING constraint (no two edges share an endpoint) needs projections out of a "
    "pair, which do not exist, so what compiles is 'a subset', not 'a matching'.",
)
add(
    "DISC.MULTISET",
    accept=M + "var m : Multiset[Real]\nrequire m = m",
    weakened=M + "var m : Function[Real -> Natural]\nrequire m = m",
    lost="multiset-hood. A multiplicity function is the standard encoding and it types, "
    "but nothing distinguishes it from an arbitrary Natural-valued function, and no "
    "multiset operations exist.",
)
add(
    "DISC.PARTIAL_ORDER",
    accept=M + "param p : Probability\nparam s : PositiveReal\n"
    "def r : NonNegativeReal := p",
    reject=M + "param p : Probability\nparam s : PositiveReal\n"
    "def r : PositiveReal := p",
    note="the scalar refinement order IS a partial order with genuine incomparability, "
    "and the incomparable pair is rejected -- this is the atom's own criterion",
)
add(
    "DISC.PATH_CONNECTIVITY",
    accept=M + "var E : Set[Product[Natural, Natural]]\nvar u : Natural\n"
    "var v : Natural\nrequire reachable(u, v, in := E)",
    weakened=M + "var R : Function[Natural, Natural -> Bool]\nvar u : Natural\n"
    "var v : Natural\nrequire R(u, v)",
    lost="derivation from the edge relation. A reachability predicate can be POSTULATED "
    "as a Boolean function but nothing computes it from E, and walks, paths and cycles "
    "are not distinguished.",
)
add(
    "DISC.PERMUTATION",
    accept=M + "var s : Permutation[5]\nrequire s = s",
    weakened=M + "var s : Function[Natural -> Natural]\n"
    "require forall a : Natural . forall b : Natural . s(a) = s(b) => a = b",
    lost="finiteness and surjectivity onto the same set, plus composition and inverse. "
    "An injective Natural-valued function is not a permutation of a finite set.",
)
add(
    "DISC.PRODUCT_NOTATION",
    accept=M + "var a : Function[Natural -> Real]\n"
    "def p := prod(a(i), i : Natural, 1, 10)",
    weakened=M + "var v : Vector[Real, N]\ndef p := prod(v)",
    lost="the index binder and the range. `prod` is a one-argument aggregate, so the "
    "empty-product convention and order preservation in non-commutative cases have "
    "nowhere to live.",
)
add(
    "DISC.RECURRENCE",
    accept=M + "def F(n : Natural) : Natural := F(n - 1) + F(n - 2)",
    weakened=M + "var F : Function[Natural -> Natural]\n"
    "require forall n : Natural . F(n) = F(n)",
    lost="the recurrence. Self-reference is rejected as a definition cycle (HML-S606) "
    "with no initial-condition escape, so the relation cannot be written and the "
    "closed-form/recurrence distinction never arises.",
)
add(
    "DISC.SEQUENCE",
    accept=M + "var a : Function[Natural -> Real]\nrequire a = a",
    reject=M + "var a : Function[Natural -> Real]\nvar x : Real\nrequire a = x",
    judgement="a sequence as a function from Natural is faithful and is kept distinct "
    "from a value. The index ORIGIN is not declarable (Natural includes 0 by "
    "convention) and there is no sequence-specific machinery -- limits at infinity, "
    "partial sums -- so this is the type without the theory.",
)
add(
    "DISC.SET_FINITE",
    accept=M + "var S : Set[Natural]\ndef n := cardinality(S)",
    weakened=M + "var S : Set[Natural]\nrequire S = S",
    lost="finiteness and size. `Set[T]` has no cardinality and no finiteness marker, so "
    "'a finite collection whose size is available' is exactly what it is not.",
)
add(
    "DISC.SUMMATION",
    accept=M + "var a : Function[Natural -> Real]\n"
    "def s := sum(a(i), i : Natural, 1, 10)",
    weakened=M + "var v : Vector[Real, N]\ndef s := sum(v)",
    lost="the index binder and the range, which is the entire atom. `sum` takes exactly "
    "one aggregate argument (HML-T426), so ranges, empty-range conventions and "
    "multi-index sums are all unreachable.",
)
add(
    "DISC.TREE",
    accept=M + "var T : Tree[Natural]\nrequire T = T",
    weakened=M + "var E : Set[Product[Natural, Natural]]\nrequire E = E",
    lost="acyclicity, connectedness and the parent/child structure; a set of pairs has "
    "no root and no shape",
)
add(
    "DISC.WEIGHTED_GRAPH",
    accept=M + "var w : Function[Product[Natural, Natural] -> Quantity[Length]]\n"
    "require w = w",
    reject=M + "var w : Function[Product[Natural, Natural] -> Quantity[Length]]\n"
    "var t : Quantity[Time]\nvar e : Product[Natural, Natural]\nrequire w(e) = t",
    judgement="edge attributes with their own types and UNITS are expressible as a "
    "function on pairs, and the dimension system rejects a time-valued length. There is "
    "still no graph the weights are attached to.",
)

# ===========================================================================
# H. GEOMETRY / TOPOLOGY  (30 atoms)  -- zero atoms probed before this file
# ===========================================================================

add(
    "GEO.AFFINE_SPACE",
    accept=M + "var p : Point[Real, 3]\nvar v : Vector[Real, 3]\ndef q := p + v",
    weakened=M + "var p : Vector[Real, 3]\nvar v : Vector[Real, 3]\ndef q := p + v",
    lost="the point/vector distinction, which is the atom. With both typed as Vector, "
    "point + point compiles, and weight-one affine combinations are indistinguishable "
    "from arbitrary linear ones.",
)
add(
    "GEO.ANGLE",
    accept=M + "var a : Quantity[Angle]\nrequire a = a",
    weakened=M + "var a : Real\nrequire a >= 0.0 and a <= 6.283185307179586",
    lost="radian/degree distinction and the principal-range convention. Angle is not a "
    "base dimension, so an angle is a bare Real with a hand-written bound.",
)
add(
    "GEO.CHART_ATLAS",
    not_measured="charts and transition maps presuppose a manifold (GEO.MANIFOLD). No "
    "manifold, chart, patch or overlap has any spelling in HML, so a probe would be "
    "testing an invented syntax rather than the language.",
)
add(
    "GEO.COMPACTNESS",
    accept=M + "var K : Set[Real]\nrequire compact(K)",
    weakened=M + "var K : Set[Real]\nvar B : PositiveReal\n"
    "require forall x : Real . x in K => abs(x) <= B",
    lost="compactness. Boundedness is statable; closedness is not, open covers are not, "
    "and Heine-Borel is a theorem about a setting that does not exist.",
)
add(
    "GEO.CONE_ORDER",
    accept=M + "var A : Matrix[Real, 3, 3]\nvar B : Matrix[Real, 3, 3]\n"
    "require psd_order(A, B)",
    weakened=M + "var A : Matrix[Real, 3, 3]\nvar B : Matrix[Real, 3, 3]\n"
    "require A <= B",
    lost="the cone. `A <= B` compiles but is NOT the Loewner order -- nothing defines a "
    "cone, so the comparison has no declared meaning at all, which is worse than its "
    "absence.",
)
add(
    "GEO.CONNECTEDNESS",
    accept=M + "var S : Set[Real]\nrequire connected(S)",
    weakened=M + "var S : Set[Real]\nrequire S = S",
    lost="connectedness and path-connectedness both, and the one-directional "
    "implication between them; there is no topology to be relative to",
)
add(
    "GEO.CONTINUOUS_MAP",
    accept=M + "var f : Function[Real -> Real]\nvar D : Set[Real]\n"
    "require continuous(f, on := D)",
    reject=M + "var f : Function[Real -> Real]\nvar D : Set[Real]\n"
    "var g : Function[Real -> Real]\nrequire continuous(g, on := f)",
    judgement="continuity relative to an explicitly given domain SET is expressible and "
    "the domain argument is type-checked. Continuity relative to a TOPOLOGY on source "
    "and target -- the atom's actual definition -- is not, because there is no topology.",
)
add(
    "GEO.CONVEX_SET",
    accept=M + "var A : Matrix[Real, N, K]\nvar b : Vector[Real, N]\n"
    "def C := { u : Vector[Real, K] | A @ u <= b }\nrequire convex(C)",
    weakened=M + "var A : Matrix[Real, N, K]\nvar b : Vector[Real, N]\n"
    "def C := { u : Vector[Real, K] | A @ u <= b }",
    lost="convexity as a checkable property. The SET is describable by a comprehension "
    "and its shapes are checked, but nothing states or verifies that it is closed under "
    "convex combinations, so the guarantee is never available downstream.",
)
add(
    "GEO.COORDINATE_CHANGE",
    accept=M + "var T : Function[Vector[Real, 2] -> Vector[Real, 2]]\n"
    "def J := jacobian(T)",
    weakened=M + "var T : Function[Vector[Real, 2] -> Vector[Real, 2]]\nrequire T = T",
    lost="the volume-element correction. A coordinate change is just a function; there "
    "is no Jacobian factor, so integrals do not transform.",
)
add(
    "GEO.COORDINATE_SYSTEM",
    accept=M + "var p : Vector[Real, 2] in polar\nrequire p = p",
    weakened=M + "var r : NonNegativeReal\nvar th : Real\nrequire r >= 0.0",
    lost="the named system. Naming the components is not naming a coordinate system, so "
    "the convention (angle order, sign) and the validity region are not recorded and "
    "Cartesian and polar values are the same type.",
)
add(
    "GEO.CURVATURE",
    not_measured="curvature is derived from a metric tensor on a manifold. Neither "
    "exists (GEO.METRIC_TENSOR, GEO.MANIFOLD), so there is no object to differentiate "
    "and no spelling to probe.",
)
add(
    "GEO.DIFFERENTIAL_FORM",
    not_measured="differential forms require an exterior algebra and oriented "
    "submanifolds to integrate over. HML has neither, and no candidate surface syntax "
    "exists that a probe could distinguish from a typo.",
)
add(
    "GEO.DISTANCE",
    accept=M + "var d : Function[Vector[Real, 3], Vector[Real, 3] -> NonNegativeReal]\n"
    "var u : Vector[Real, 3]\nvar v : Vector[Real, 3]\nrequire d(u, v) >= 0.0",
    reject=M + "var d : Function[Vector[Real, 3], Vector[Real, 3] -> NonNegativeReal]\n"
    "var u : Vector[Real, 3]\nrequire d(u) >= 0.0",
    judgement="a distance can be declared as a typed two-argument function with a "
    "non-negative codomain, and arity is enforced. WHICH metric it is -- the atom's "
    "whole point -- is carried only by the symbol's name, not by anything checkable.",
)
add(
    "GEO.EUCLIDEAN_SPACE",
    accept=M + "var x : Vector[Real, 3]\nrequire x = x",
    reject=M + "var x : Vector[Real, 3]\nvar y : Vector[Real, 2]\nrequire x = y",
    judgement="R^n with the dimension in the type is exactly VectorType and dimension "
    "mismatch is rejected. The standard INNER PRODUCT that makes it Euclidean is not "
    "part of the type (see ALG.INNER_PRODUCT).",
)
add(
    "GEO.GEODESIC",
    not_measured="a geodesic is defined by a metric on a manifold. Both are absent, so "
    "there is nothing to minimise length over.",
)
add(
    "GEO.HOMEOMORPHISM",
    accept=M + "var X : TopologicalSpace\nvar Y : TopologicalSpace\n"
    "require homeomorphic(X, Y)",
    weakened=M + "var f : Function[Real -> Real]\nvar g : Function[Real -> Real]\n"
    "require forall a : Real . g(f(a)) = a",
    lost="bicontinuity and the spaces. A mutually inverse pair of real functions is not "
    "a homeomorphism and no invariant is preserved by anything.",
)
add(
    "GEO.HOMOTOPY",
    not_measured="homotopy is a continuous deformation between maps of topological "
    "spaces. There is no topological space and no space of maps, so the notion has no "
    "carrier and no probe.",
)
add(
    "GEO.MANIFOLD",
    accept=M + "var Mf : Manifold[2]\nrequire Mf = Mf",
    weakened=M + "def S := { p : Vector[Real, 3] | sum(p * p) = 1.0 }\nrequire S = S",
    lost="local Euclidean structure, declared dimension and smoothness class. A "
    "comprehension carves out a subset of R^3 and says nothing about charts.",
)
add(
    "GEO.MEASURE_ON_GEOMETRIC_DOMAIN",
    accept=M + "var vol : Function[Set[Vector[Real, 3]] -> Quantity[Length^3]]\n"
    "require vol = vol",
    reject=M + "var vol : Function[Set[Vector[Real, 3]] -> Quantity[Length^3]]\n"
    "var a : Quantity[Length^2]\nvar S : Set[Vector[Real, 3]]\nrequire vol(S) = a",
    judgement="a volume measure with the CORRECT dimension is expressible as a set "
    "function into Quantity[Length^3], and the dimension system refuses to equate it "
    "with an area. The geometry that should INDUCE the measure is absent.",
)
add(
    "GEO.METRIC_TENSOR",
    accept=M + "var g : Function[Vector[Real, 3] -> Matrix[Real, 3, 3]]\nrequire g = g",
    reject=M + "var g : Function[Vector[Real, 3] -> Matrix[Real, 3, 3]]\n"
    "var p : Vector[Real, 3]\nvar A : Matrix[Real, 2, 2]\nrequire g(p) = A",
    judgement="a field of matrices over points types correctly and its shape is "
    "enforced. Symmetry, positive-definiteness and the induced lengths/angles/volumes "
    "are not expressible, so what compiles is a matrix-valued function, not a metric.",
)
add(
    "GEO.OPEN_CLOSED",
    accept=M + "var S : Set[Real]\nvar X : Set[Real]\nrequire open(S, in := X)",
    weakened=M + "def S := { x : Real | x > 0.0 }\nrequire S = S",
    lost="openness, closedness, interior, closure and boundary -- all of them. A "
    "comprehension with a strict inequality LOOKS open but nothing says so, and the "
    "atom's point that open and closed are not complementary cannot even be stated.",
)
add(
    "GEO.ORIENTATION",
    not_measured="orientation is a sign convention on ordered bases or boundaries. "
    "There is no basis object and no boundary, so no probe can distinguish an oriented "
    "object from an unoriented one.",
)
add(
    "GEO.POINT_VECTOR_DISTINCTION",
    accept=M + "var p : Point[Real, 3]\nvar q : Point[Real, 3]\ndef v := p - q",
    weakened=M + "var p : Vector[Real, 3]\nvar q : Vector[Real, 3]\ndef v := p - q",
    lost="the distinction itself. Both are Vector, so point + point type-checks -- the "
    "exact error the atom exists to prevent.",
)
add(
    "GEO.POLYTOPE",
    accept=M + "var A : Matrix[Real, N, K]\nvar b : Vector[Real, N]\n"
    "var x : Vector[Real, K]\ndef P := { u : Vector[Real, K] | A @ u <= b }",
    weakened=M + "var A : Matrix[Real, N, K]\nvar b : Vector[Real, N]\n"
    "var x : Vector[Real, K]\nrequire A @ x <= b",
    lost="the polytope as an object with two interchangeable descriptions. The "
    "half-space intersection is statable as a constraint on a named point; the vertex "
    "description and the H/V duality are absent.",
)
add(
    "GEO.PROJECTION",
    accept=M + "var S : Set[Vector[Real, 3]]\nvar x : Vector[Real, 3]\n"
    "def p := project(x, onto := S)",
    weakened=M + "var S : Set[Vector[Real, 3]]\nvar x : Vector[Real, 3]\n"
    "var p : Vector[Real, 3]\nrequire p in S",
    lost="the nearest-point property, the metric it is nearest in, and the "
    "existence/uniqueness conditions; only membership survives",
)
add(
    "GEO.SIMPLEX",
    accept=M + "var p : Vector[Probability, 3]\nrequire sum(p) = 1.0",
    reject=M + "var p : Vector[Probability, 3]\nvar q : Vector[Probability, 4]\n"
    "require sum(p) = 1.0 and p = q",
    note="non-negativity comes from the element refinement Probability and the "
    "sum-to-one constraint is statable; the constraint is not part of the type, so it "
    "is an assertion rather than a domain",
)
add(
    "GEO.TANGENT_SPACE",
    accept=M + "var p : Point[Real, 3]\nvar v : Tangent[p]\nrequire v = v",
    weakened=M + "var v : Vector[Real, 3]\nrequire v = v",
    lost="the base point, which the atom says is part of the vector's identity. Two "
    "tangent vectors at different points have the same type and compare equal.",
)
add(
    "GEO.TOPOLOGICAL_SPACE",
    accept=M + "var X : TopologicalSpace\nrequire X = X",
    weakened=M + "var X : Set[Real]\nvar tau : Set[Set[Real]]\nrequire tau = tau",
    lost="the pairing and the axioms. A set and an unrelated collection of subsets are "
    "not (X, tau), so continuity and convergence cannot be made relative to a named "
    "structure.",
)
add(
    "GEO.TRANSFORMATION_GROUP",
    accept=M + "var R : Matrix[Real, 3, 3]\nvar v : Vector[Real, 3]\ndef w := R @ v",
    reject=M + "var R : Matrix[Real, 2, 2]\nvar v : Vector[Real, 3]\ndef w := R @ v",
    judgement="the ACTION of a matrix on a vector is expressible and shape-checked. "
    "The group (orthogonality, closure, invariance of a quantity under it) is not: "
    "there is no group object and no invariance predicate.",
)
add(
    "GEO.VECTOR_FIELD",
    accept=M + "var F : Function[Vector[Real, 3] -> Vector[Real, 3]]\ndef d := div(F)",
    weakened=M + "var F : Function[Vector[Real, 3] -> Vector[Real, 3]]\nrequire F = F",
    lost="the derived operations. The assignment of a vector to each point types "
    "correctly as a function; divergence and curl do not exist.",
)

# ===========================================================================
# I. OPTIMIZATION  (32 atoms)
# ===========================================================================

OPT = M + "param x : Real\ndef f := x * x\n"

add(
    "OPT.ARGMIN_ARGMAX",
    accept=OPT + "def S := argmin(f)",
    weakened=OPT + "minimise f",
    lost="the optimiser set. `minimise` is a statement, not a term, so the set of "
    "minimisers -- possibly empty, possibly non-singleton -- is never an object and "
    "cannot be distinguished from the optimal value.",
)
add(
    "OPT.BELLMAN",
    accept=M + "var V : Function[Natural -> Real]\nvar s : Natural\n"
    "require V(s) = max(V(s))",
    weakened=M + "var V : Function[Natural -> Real]\nvar s : Natural\n"
    "require V(s) = V(s)",
    lost="the whole equation: no indexed maximum over actions, no expectation over "
    "transitions, and no fixed-point status for the recursion",
)
add(
    "OPT.BOX_BOUND",
    accept=M + "param x : Real\nrequire x >= 0.0 and x <= 1.0\ndef f := x * x\n"
    "minimise f",
    reject=M + "param x : Quantity[Length]\nrequire x >= 0.0\n"
    "def f := x * x\nminimise f",
    judgement="per-variable bounds are ordinary `require` statements. The reject arm "
    "tests the atom's 'possibly with units' clause: whether a dimensionful decision "
    "variable can be bounded by a dimensionless literal, which it should not be.",
)
add(
    "OPT.CHANCE_CONSTRAINT",
    accept=M + "param x : Real\nrv Z : RandomVariable[Real]\n"
    "law Z ~ Normal(location := 0.0, scale := 1.0)\n"
    "require probability(Z <= x) >= 0.95\ndef f := x * x\nminimise f",
    reject=M + "param x : Real\nrv Z : RandomVariable[Real]\n"
    "law Z ~ Normal(location := 0.0, scale := 1.0)\n"
    "require probability(Z <= x) >= 2.0\ndef f := x * x\nminimise f",
    note="a probability of an event built from a decision variable, constrained to a "
    "level, is exactly the chance-constraint form; the level's [0,1] typing is enforced",
)
add(
    "OPT.CONIC_PROGRAM",
    accept=M + "param X : Matrix[Real, 3, 3]\nrequire positive_semidefinite(X)\n"
    "def f := trace(X)\nminimise f",
    weakened=M + "param X : Matrix[Real, 3, 3]\ndef f := sum(X)\nminimise f",
    lost="the cone membership constraint, which is the definition of a conic program; "
    "without PSD-ness or trace the problem is unconstrained and linear",
)
add(
    "OPT.CONSTRAINT_SCOPE",
    accept=M + "param x : Real\nvar c : Proposition\n"
    "require c => x >= 0.0\ndef f := x * x\nminimise f",
    reject=None,
    judgement="a CONDITIONAL constraint is expressible as an implication. A SCOPED one "
    "is not: `require` is a module-level assertion with no block and no index subset, "
    "which the reject arm records as an absence rather than as a caught misuse.",
)
add(
    "OPT.CONVEXITY",
    accept=OPT + "require convex(f)\nminimise f",
    weakened=OPT + "minimise f",
    lost="convexity as a checkable property. Nothing distinguishes a convex program "
    "from a non-convex one, so the guarantee that a local optimum is global is never "
    "available.",
)
add(
    "OPT.DECISION_VARIABLE",
    accept=OPT + "minimise f",
    reject=M + "obs x : Real = 1.0\ndef f := x * x\nminimise f",
    judgement="`param` marks the optimised symbol and is distinct from obs/const/var. "
    "The reject arm asks whether minimising over OBSERVED data is refused -- i.e. "
    "whether the decision/data distinction is enforced at the optimisation site.",
)
add(
    "OPT.DIRECTION",
    accept=OPT + "minimise f",
    reject=OPT + "minimise f\nmaximise f",
    note="sense is a distinct keyword and is not recoverable from the objective; the "
    "reject arm tests whether two contradictory senses on one objective are caught",
)
add(
    "OPT.DUALITY",
    accept=OPT + "require x >= 0.0\nminimise f\ndef d := dual(f)",
    weakened=OPT + "require x >= 0.0\nminimise f",
    lost="the dual problem, the multipliers and the gap. There is no problem object to "
    "dualise, so weak duality has nothing to relate.",
)
add(
    "OPT.DYNAMIC_PROGRAMMING",
    not_measured="a sequential decision problem needs stages, a state, a transition and "
    "a stagewise cost as one object. HML has no problem object and no stage index; "
    "there is no partial spelling to probe.",
)
add(
    "OPT.EQUALITY_CONSTRAINT",
    accept=M + "param x : Real\nparam y : Real\nrequire x + y = 1.0\n"
    "def f := x * x\nminimise f",
    reject=M + "param x : Real\nparam y : Real\nrequire x + y := 1.0\n"
    "def f := x * x\nminimise f",
    note="h(x) = 0 is an assertion, not a definition or an assignment; `:=` is refused "
    "in that position",
)
add(
    "OPT.EXPECTED_VALUE_OBJECTIVE",
    accept=M + "param x : Real\nrv Z : RandomVariable[Real]\n"
    "law Z ~ Normal(location := 0.0, scale := 1.0)\n"
    "def f := expectation(Z * x)\nminimise f",
    reject=M + "param x : Real\ndef f := expectation(x * x)\nminimise f",
    note="an expectation over a random variable can be the objective, and expectation "
    "of a deterministic term is refused",
)
add(
    "OPT.FEASIBLE_SET",
    accept=M + "param x : Real\nrequire x >= 0.0\ndef f := x * x\nminimise f",
    reject=None,
    judgement="constraints are statable and jointly define admissible decisions. They "
    "are NOT scoped to the optimisation and the feasible set is not an object -- the "
    "reject arm shows there is no `subject to` -- so emptiness cannot be a meaningful "
    "result.",
)
add(
    "OPT.GRADIENT_OF_OBJECTIVE",
    accept=M + "param x : Real\ndef g := derivative(x * x, x : Real)\nminimise g",
    weakened=M + "param x : Real\ndef g := derivative(u * u, u : Real)\nminimise g",
    lost="the connection to the decision variable. Differentiating with respect to the "
    "DECLARED param is rejected outright -- the binder shadows it (HML-N302) -- so the "
    "gradient must be taken in a fresh symbol that has no relationship to x, and "
    "'with respect to the decision variables, holding data fixed' becomes unstatable.",
)
add(
    "OPT.INEQUALITY_CONSTRAINT",
    accept=M + "param x : Real\nrequire x >= 0.0\ndef f := x * x\nminimise f",
    reject=M + "param x : Real\nvar b : Bool\nrequire x >= b\n"
    "def f := x * x\nminimise f",
    judgement="g(x) <= 0 is expressible and strictness is visible in the operator. "
    "ACTIVE/INACTIVE status at a solution is not representable, because there is no "
    "solution object.",
)
add(
    "OPT.INTEGER_VARIABLE",
    accept=M + "param n : Integer\ndef f := n * n\nminimise f",
    reject=M + "param n : Integer\nrequire n = 0.5\ndef f := n * n\nminimise f",
    note="integrality is a DOMAIN restriction carried by the declared type, which is "
    "exactly what the atom asks for, and a non-integral literal is refused",
)
add(
    "OPT.KKT",
    accept=M + "param x : Real\nparam lam : NonNegativeReal\n"
    "require derivative(x * x, x : Real) + lam = 0.0\nrequire lam * x = 0.0\n"
    "require x >= 0.0\ndef f := x * x\nminimise f",
    weakened=M + "param x : Real\nparam lam : NonNegativeReal\n"
    "require derivative(u * u, u : Real) + lam = 0.0\nrequire lam * x = 0.0\n"
    "require x >= 0.0\ndef f := x * x\nminimise f",
    lost="stationarity in the decision variable. Dual feasibility (lam typed "
    "NonNegativeReal) and complementary slackness are writable, but the gradient cannot "
    "be taken with respect to x itself (see OPT.GRADIENT_OF_OBJECTIVE), so the "
    "stationarity condition is about an unrelated symbol. Nothing derives or checks any "
    "of it, and no constraint qualification is expressible.",
)
add(
    "OPT.LAGRANGIAN",
    accept=M + "param x : Real\nparam lam : Real\n"
    "def L := x * x + lam * (x - 1.0)\nminimise L",
    reject=M + "param x : Quantity[Length]\nparam lam : Quantity[Time]\n"
    "def L := x * x + lam * (x - 1.0)\nminimise L",
    judgement="the Lagrangian is an ordinary expression and multipliers are ordinary "
    "params. The reject arm tests the atom's units clause -- multipliers carry units of "
    "objective per constraint -- by making the two incommensurable.",
)
add(
    "OPT.LINEAR_PROGRAM",
    accept=M + "param x : Vector[Real, K]\nvar c : Vector[Real, K]\n"
    "def f := sum(c * x)\nminimise f",
    reject=M + "param x : Vector[Real, K]\nvar c : Vector[Real, N]\n"
    "def f := sum(c * x)\nminimise f",
    judgement="a linear objective is writable and its shapes are checked. LINEARITY is "
    "not checkable -- nothing distinguishes this from a quadratic objective -- so the "
    "problem CLASS is not recognised, which is the atom's requirement.",
)
add(
    "OPT.LOCAL_VS_GLOBAL",
    accept=OPT + "minimise f locally in neighbourhood_of(0.0)",
    weakened=OPT + "minimise f",
    lost="the scope of the optimality claim. Every `minimise` is unqualified, so a "
    "local and a global claim are written identically and no neighbourhood can be "
    "identified.",
)
add(
    "OPT.MIXED_INTEGER",
    accept=M + "param n : Integer\nparam x : Real\nvar c : Proposition\n"
    "require c => x >= 0.0\ndef f := n * n + x * x\nminimise f",
    reject=M + "param n : Integer\nparam x : Real\nrequire n = 0.5\n"
    "def f := n * n + x * x\nminimise f",
    judgement="both variable kinds coexist and a logical implication among constraints "
    "is writable, so the shape of a MIP is reachable. Disjunctive constraints over "
    "index sets are not (see OPT.CONSTRAINT_SCOPE).",
)
add(
    "OPT.MULTI_OBJECTIVE",
    accept=M + "param x : Real\ndef f := x * x\ndef g := (x - 1.0) * (x - 1.0)\n"
    "minimise f, g",
    weakened=M + "param x : Real\ndef f := x * x\ndef g := (x - 1.0) * (x - 1.0)\n"
    "minimise f",
    lost="the second objective. Only one objective per statement is expressible, so "
    "Pareto optimality, the partial order on outcomes and the frontier are all absent.",
)
add(
    "OPT.OBJECTIVE",
    accept=OPT + "minimise f",
    reject=M + "param x : Real\nvar A : Matrix[Real, 2, 2]\ndef f := A\nminimise f",
    note="the objective must be scalar-valued; a matrix-valued one is refused",
)
add(
    "OPT.OPTIMAL_CONTROL",
    not_measured="optimal control needs a dynamical system as a constraint plus a "
    "state/control split. Neither an ODE object (ANA.ODE) nor scoped constraints "
    "(OPT.CONSTRAINT_SCOPE) exist, so there is nothing to aim a probe at.",
)
add(
    "OPT.OPTIMAL_VALUE",
    accept=OPT + "def v := min(f)\nminimise f",
    weakened=OPT + "minimise f",
    lost="the value as a term. `minimise` produces no denotable optimum, so the "
    "value/optimiser distinction the atom draws cannot be drawn, and an unattained "
    "infimum has nowhere to live.",
)
add(
    "OPT.PARAMETRIC_OPTIMIZATION",
    accept=M + "param x : Real\nvar a : Real\ndef f := (x - a) * (x - a)\nminimise f\n"
    "def v := min(f) as_function_of a",
    weakened=M + "param x : Real\nvar a : Real\ndef f := (x - a) * (x - a)\nminimise f",
    lost="the dependence. The objective may mention data, but the optimal value and "
    "optimiser are not objects and so cannot be functions of it; sensitivity analysis "
    "is closed off.",
)
add(
    "OPT.PROBLEM_AS_OBJECT",
    accept=M + "param x : Real\ndef f := x * x\ndef P := problem(minimise := f)",
    weakened=OPT + "minimise f",
    lost="the problem as one nameable value. Variables, objective, constraints and "
    "sense are separate module-level statements that cannot be bundled, passed, "
    "compared or transformed.",
)
add(
    "OPT.QUADRATIC_PROGRAM",
    accept=M + "param x : Vector[Real, K]\nvar Q : Matrix[Real, K, K]\n"
    "def f := sum(x * (Q @ x))\nminimise f",
    reject=M + "param x : Vector[Real, K]\nvar Q : Matrix[Real, K, N]\n"
    "def f := sum(x * (Q @ x))\nminimise f",
    judgement="the quadratic form is writable by hand-unfolding and its shapes are "
    "checked. The DEFINITENESS of Q, which determines convexity and is the atom's "
    "content, is not expressible (see ALG.POSITIVE_DEFINITE).",
)
add(
    "OPT.REGULARIZATION",
    accept=M + "param x : Quantity[Length]\nvar lam : Quantity[1]\n"
    "def f := x * x + lam * x * x\nminimise f",
    reject=M + "param x : Quantity[Length]\nvar lam : Quantity[Time]\n"
    "def f := x * x + lam * x * x\nminimise f",
    note="a penalty term is an ordinary summand and the dimension system enforces the "
    "atom's requirement that the weight's units be compatible with the loss",
)
add(
    "OPT.ROBUST_WORST_CASE",
    accept=M + "param x : Real\nvar u : Real\nvar U : Set[Real]\n"
    "def f := x * x + u\nminimise max(f, over := U)",
    weakened=M + "param x : Real\nvar u : Real\ndef f := x * x + u\nminimise f",
    lost="the inner maximisation over an uncertainty set, which is the alternating "
    "quantifier structure the atom names; only the inner objective survives",
)
add(
    "OPT.VARIATIONAL_OBJECTIVE",
    accept=M + "param f : Function[Real -> Real]\n"
    "var J : Function[Function[Real -> Real] -> Real]\nminimise J(f)",
    reject=M + "param f : Function[Real -> Real]\n"
    "var J : Function[Function[Real -> Real] -> Real]\nminimise J(f, f)",
    judgement="the decision variable may be function-typed and the objective's arity is "
    "checked. Optimising over a MEASURE is not reachable (Distribution-typed params "
    "have no arithmetic), and the admissible class cannot be stated.",
)

# ===========================================================================
# J. SCIENTIFIC UNITS  (25 atoms)
# ===========================================================================

add(
    "SCI.AFFINE_UNIT",
    accept=M + "var t : Quantity[Temperature, celsius]\nvar d : Quantity[Temperature]\n"
    "def s := t + d",
    weakened=M + "var t : Quantity[Temperature]\nvar d : Quantity[Temperature]\n"
    "def s := t + d",
    lost="the origin. HML dimensions are unit-free, so an absolute temperature and a "
    "temperature DIFFERENCE have the same type and adding two absolute temperatures "
    "compiles -- the exact error the atom exists to prevent.",
)
add(
    "SCI.BASE_DIMENSION_SYSTEM",
    accept=M + "var d : Quantity[Length]\nvar m : Quantity[Mass]\ndef p := d * m",
    reject=M + "var d : Quantity[Luminance]",
    note="the seven SI base dimensions are declared in BASE_DIMENSIONS and an "
    "undeclared base dimension is refused (HML-D501). The system is fixed, not "
    "user-declarable, so a domain-specific base set is not available.",
)
add(
    "SCI.CONSERVATION_LAW",
    accept=M + "var qin : Quantity[Mass / Time]\nvar qout : Quantity[Mass / Time]\n"
    "require qin = qout",
    reject=M + "var qin : Quantity[Mass / Time]\nvar qout : Quantity[Mass]\n"
    "require qin = qout",
    judgement="a balance relation is an ordinary equation and it is checked "
    "dimensionally, which is the atom's own criterion. There is no conservation "
    "statement FORM, so nothing marks the equation as a conservation law.",
)
add(
    "SCI.COORDINATE_FRAME",
    accept=M + "var v : Vector[Quantity[Length], 3] in frame_A\nrequire v = v",
    weakened=M + "var v : Vector[Quantity[Length], 3]\nrequire v = v",
    lost="the frame. Two vectors expressed in different frames have the same type and "
    "may be added, which the atom says must be refused.",
)
add(
    "SCI.COUNT_VS_MEASURE",
    accept=M + "var n : Natural\nparam p : Probability\nvar r : Quantity[1 / Time]\n"
    "require p >= 0.0 and r = r",
    reject=M + "var n : Natural\nvar r : Quantity[1 / Time]\nrequire n = r",
    note="a count (Natural), a proportion (Probability) and a rate (Quantity[1/Time]) "
    "are three distinct types and cross-type equality is refused",
)
add(
    "SCI.DIMENSION",
    accept=M + "var a : Quantity[Length / Time^2]\nrequire a = a",
    reject=M + "var a : Quantity[Length / Time^2]\nvar v : Quantity[Length / Time]\n"
    "require a = v",
    note="dimensions are rational-exponent vectors over the seven base dimensions and "
    "are compared exactly",
)
add(
    "SCI.DIMENSIONAL_HOMOGENEITY",
    accept=M + "var d : Quantity[Length]\nvar e : Quantity[Length]\ndef s := d + e",
    reject=M + "var d : Quantity[Length]\nvar t : Quantity[Time]\ndef s := d + t",
    note="addition, comparison and equality all require matching dimensions",
)
add(
    "SCI.DIMENSIONLESS",
    accept=M + "var r : Quantity[1]\nrequire r = r",
    reject=M + "var r : Quantity[1]\nvar d : Quantity[Length]\nrequire r = d",
    judgement="the zero dimension vector is expressible and is distinct from any other. "
    "A unit-like TAG on a dimensionless quantity -- radian, percent, dB -- is not: "
    "there are no units at all, only dimensions, so all dimensionless quantities are "
    "one type.",
)
add(
    "SCI.DIMENSIONLESS_GROUP",
    accept=M + "var rho : Quantity[Mass / Length^3]\nvar v : Quantity[Length / Time]\n"
    "var L : Quantity[Length]\nvar mu : Quantity[Mass / (Length * Time)]\n"
    "def Re := rho * v * L / mu\ncheck dimension Re",
    reject=M + "var rho : Quantity[Mass / Length^3]\nvar v : Quantity[Length / Time]\n"
    "var L : Quantity[Length]\ndef Re := rho * v * L\ncheck dimension Re",
    judgement="the Reynolds number really does come out dimensionless and `check "
    "dimension` verifies it -- the reject arm confirms a non-dimensionless combination "
    "is caught. Buckingham-pi DERIVATION is not performed; the group must be written by "
    "hand.",
)
add(
    "SCI.LOG_OF_RATIO",
    accept=M + "var p : Quantity[Mass]\nvar p0 : Quantity[Mass]\n"
    "def db := 10.0 * log(p / p0)",
    weakened=M + "var p : PositiveReal\nvar p0 : PositiveReal\n"
    "def db := 10.0 * log(p / p0)",
    lost="the dimensional guarantee that the argument IS a ratio. log demands a "
    "PositiveReal and a dimensionless Quantity is not one (HML-T427), so the ratio of "
    "two dimensionful quantities cannot be passed to log at all -- note that exp "
    "ACCEPTS the same ratio, so the two transcendental builtins disagree. Falling back "
    "to bare PositiveReal operands removes every unit check, and the reference value "
    "becomes a naming convention rather than recorded data.",
)
add(
    "SCI.PHYSICAL_CONSTANT",
    accept=M + "const g : Quantity[Length / Time^2] = 9.81\nrequire g = g",
    weakened=M + "const g : Real = 9.81\nrequire g = g",
    lost="the unit on a literal. A Quantity-typed constant cannot be given a numeric "
    "literal (HML-T402: there is no unit-bearing literal form), so a physical constant "
    "must be declared dimensionless -- losing exactly the unit the atom requires, along "
    "with its uncertainty and provenance.",
)
add(
    "SCI.PREFIX_SCALING",
    accept=M + "const d : Quantity[Length] = 1.0 kilometre",
    weakened=M + "var d : Quantity[Length]\nvar m : Quantity[Length]\n"
    "require d = 1000.0 * m",
    lost="prefixes and units. There is no unit surface at all, so a prefix has nothing "
    "to compose with and the scale factor must be written as a bare number.",
)
add(
    "SCI.QUANTITY",
    accept=M + "var d : Quantity[Length]\nrequire d = d",
    reject=M + "var d : Quantity[Length]\nvar x : Real\nrequire d = x",
    judgement="a Quantity is a distinct type and does not unify with a bare Real, which "
    "is the atom's central claim. It pairs a magnitude with a DIMENSION, not with a "
    "UNIT -- there is no unit object -- so 'value plus unit' is only half present.",
)
add(
    "SCI.SIGNIFICANT_FIGURES",
    accept=M + "const c : Real = 1.23 sigfigs 3",
    weakened=M + "const c : Real = 1.23",
    lost="precision as information about the value. A literal carries no digit count, "
    "so arithmetic silently invents precision, which the atom explicitly forbids.",
)
add(
    "SCI.TENSOR_UNITS",
    accept=M + "var v : Vector[Quantity[Length], 3]\nrequire v = v",
    reject=M + "var v : Vector[Quantity[Length], 3]\n"
    "var w : Vector[Quantity[Time], 3]\ndef s := v + w",
    judgement="a UNIFORM dimension across a tensor is expressible and is checked. A "
    "PER-COMPONENT dimension -- the mixed-unit state vector the atom names -- is not, "
    "because the element type is single.",
)
add(
    "SCI.TIME_AND_CALENDAR",
    accept=M + "var t : Instant\nvar d : Quantity[Time]\ndef u := t + d",
    weakened=M + "var t : Quantity[Time]\nvar d : Quantity[Time]\ndef u := t + d",
    lost="the instant/duration distinction. Both are Quantity[Time], so instant + "
    "instant compiles -- the affine-timeline error the atom names.",
)
add(
    "SCI.UNCERTAINTY",
    accept=M + "var m : Quantity[Mass] +/- 0.01\nrequire m = m",
    weakened=M + "var m : Quantity[Mass]\nvar sm : Quantity[Mass]\nrequire sm = sm",
    lost="the attachment. An uncertainty can be declared as a second quantity of the "
    "same dimension but nothing binds it to the value, and its interpretation "
    "(standard, coverage) is unrecorded.",
)
add(
    "SCI.UNCERTAINTY_PROPAGATION",
    accept=M + "var a : Quantity[Length] +/- 0.1\nvar b : Quantity[Length] +/- 0.1\n"
    "def c := a + b",
    weakened=M + "var sa : Quantity[Length]\nvar sb : Quantity[Length]\n"
    "def sc := sa * sa + sb * sb",
    lost="propagation, and the square root that the linearised formula needs -- sqrt "
    "demands a NonNegativeReal and refuses a Quantity (HML-T427), so only the sum of "
    "squares survives. The linearised formula can be written by hand for one operation; "
    "nothing carries an uncertainty through arithmetic automatically and no assumption "
    "is recorded.",
)
add(
    "SCI.UNIT",
    accept=M + "var d : Quantity[Length] in metre\nrequire d = d",
    weakened=M + "var d : Quantity[Length]\nvar e : Quantity[Length]\nrequire d = e",
    lost="units entirely. HML is deliberately unit-free (dimensions only), so two "
    "quantities of the same dimension are always directly comparable and there is "
    "nothing to convert between -- see SCI.UNIT_CONVERSION.",
)
add(
    "SCI.UNITFUL_RANDOM_VARIABLE",
    accept=M + "rv X : RandomVariable[Quantity[Length]]\n"
    "law X ~ Normal(location := 0.0, scale := 1.0)",
    weakened=M + "rv X : RandomVariable[Real]\n"
    "law X ~ Normal(location := 0.0, scale := 1.0)",
    lost="dimensionful randomness. A distribution's support must match the declared "
    "value type, and no family has a Quantity support (HML-T411), so a random variable "
    "cannot carry a dimension and location/scale cannot inherit one.",
)
add(
    "SCI.UNIT_ALGEBRA",
    accept=M + "var d : Quantity[Length]\nvar t : Quantity[Time]\n"
    "var v : Quantity[Length / Time]\ndef q := d / t\nrequire q = v",
    reject=M + "var d : Quantity[Length]\nvar t : Quantity[Time]\n"
    "var v : Quantity[Length * Time]\ndef q := d / t\nrequire q = v",
    note="compound dimensions multiply, divide and take rational powers with an exact "
    "canonical form, so equivalent compounds compare equal",
)
add(
    "SCI.UNIT_CONVERSION",
    accept=M + "var d : Quantity[Length]\ndef f := convert(d, to := foot)",
    weakened=M + "var d : Quantity[Length]\nvar e : Quantity[Length]\nrequire d = e",
    lost="conversion. With no units there is nothing to convert between; the atom is "
    "unreachable by design rather than by oversight, and the design note should say so.",
)
add(
    "SCI.UNIT_IN_TRANSCENDENTAL_ARG",
    accept=M + "var d : Quantity[Length]\nvar e : Quantity[Length]\ndef s := exp(d / e)",
    reject=M + "var d : Quantity[Length]\ndef s := exp(d)",
    note="transcendental functions require a dimensionless argument and refuse a "
    "dimensionful one (HML-T427)",
)
add(
    "SCI.UNIT_OF_DERIVATIVE",
    accept=M + "var f : Function[Quantity[Time] -> Quantity[Length]]\n"
    "var v : Quantity[Length / Time]\n"
    "def d := derivative(f(t), t : Quantity[Time])\nrequire d = v",
    reject=M + "var f : Function[Quantity[Time] -> Quantity[Length]]\n"
    "var v : Quantity[Length * Time]\n"
    "def d := derivative(f(t), t : Quantity[Time])\nrequire d = v",
    note="dy/dx carries the dimension of y divided by that of x, computed by the checker",
)
add(
    "SCI.UNIT_OF_INTEGRAL",
    accept=M + "var f : Function[Quantity[Time] -> Quantity[Mass / Time]]\n"
    "var e : Quantity[Mass]\nvar a : Quantity[Time]\nvar b : Quantity[Time]\n"
    "def i := integral(f(t), t : Quantity[Time], a, b)\nrequire i = e",
    weakened=M + "var f : Function[Real -> Real]\n"
    "def i := integral(f(x), x : Real, 0.0, 1.0)",
    lost="the differential's dimension. `integral` bounds must be numeric literals or "
    "dimensionless (HML-T489 on a dimensionful bound), so a dimensionful integral "
    "cannot be written and the unit product cannot be checked.",
)

# ===========================================================================
# K. NUMERICAL  (31 atoms)  -- zero atoms probed before this file
# ===========================================================================

add(
    "NUMER.ABSOLUTE_ERROR",
    accept=M + "var xh : Quantity[Length]\nvar xe : Quantity[Length]\n"
    "var tol : Quantity[Length]\nrequire abs(xh - xe) <= tol",
    weakened=M + "var xh : Real\nvar xe : Real\nvar tol : PositiveReal\n"
    "require abs(xh - xe) <= tol",
    lost="the units the atom says the error must carry. `abs` is typed Real -> "
    "NonNegativeReal and refuses a Quantity (HML-T427), so a dimensionful absolute "
    "error cannot be written and the operands must be demoted to bare Reals. There is "
    "no computed/exact distinction either -- see NUMER.EXACT_VS_NUMERIC_DISPATCH.",
)
add(
    "NUMER.APPROXIMATION_MARKER",
    accept=M + "var x : Real\nvar y : Real\nrequire x ~= y within 0.001",
    weakened=M + "var x : Real\nvar y : Real\nvar e : PositiveReal\n"
    "require abs(x - y) <= e",
    lost="the relation. Approximate equality has no operator, so an approximate claim is "
    "written as an exact inequality and nothing distinguishes it from a genuine bound; "
    "the error magnitude is carried by a free symbol.",
)
add(
    "NUMER.AUTODIFF",
    accept=M + "var f : Function[Real -> Real]\ndef g := autodiff(f)",
    weakened=M + "var f : Function[Real -> Real]\ndef g := derivative(f(x), x : Real)",
    lost="the distinction between algorithmic, symbolic and finite-difference "
    "differentiation. There is one `derivative` and it is not evaluated by anything, so "
    "the three cannot be told apart.",
)
add(
    "NUMER.COMPLEXITY_OF_EVALUATION",
    not_measured="the atom asks for the COST of evaluating a mathematical object, kept "
    "separate from the object. HML performs no evaluation at all and has no cost model "
    "or annotation surface; there is no spelling to probe.",
)
add(
    "NUMER.CONDITION_NUMBER",
    accept=M + "var A : Matrix[Real, N, N]\ndef c := condition_number(A)",
    weakened=M + "var A : Matrix[Real, N, N]\nvar c : PositiveReal\nrequire c >= 1.0",
    lost="the functional. A positive symbol bounded below by one is not the sensitivity "
    "of a problem to perturbation, and there is no problem object to be a property of.",
)
add(
    "NUMER.CONVERGENCE_RATE",
    accept=M + "var e : Function[Natural -> NonNegativeReal]\nvar p : PositiveReal\n"
    "var C : PositiveReal\nrequire forall n : Natural . e(n + 1) <= C * e(n) ** p",
    reject=None,
    judgement="the order-p recurrence on the error sequence is statable with typed "
    "symbols and undeclared exponents are refused. There is no iterative METHOD for it "
    "to be the rate of, and no asymptotic constant is identified as such.",
)
add(
    "NUMER.DISCRETIZATION",
    accept=M + "var h : PositiveReal\nvar u : Function[Real -> Real]\n"
    "var uh : Function[Real -> Real]\nvar C : PositiveReal\n"
    "require forall x : Real . abs(u(x) - uh(x)) <= C * h",
    reject=None,
    judgement="the discretisation parameter and the induced error bound are writable as "
    "typed symbols and a quantified inequality. The ACT of replacing a continuous "
    "object by a finite one has no representation, which the reject arm records.",
)
add(
    "NUMER.ERROR_BOUND",
    accept=M + "var f : Function[Real -> Real]\nvar g : Function[Real -> Real]\n"
    "var e : PositiveReal\nvar D : Set[Real]\n"
    "require forall x : Real . x in D => abs(f(x) - g(x)) <= e",
    reject=M + "var f : Function[Real -> Real]\nvar g : Function[Real -> Real]\n"
    "var e : PositiveReal\nrequire abs(f - g) <= e",
    note="a bound is a universally quantified claim over an explicitly given input "
    "class, which is exactly what the accept probe writes; the norm is not nameable, so "
    "abs on a pointwise difference is the only available spelling",
)
add(
    "NUMER.EXACT_VS_NUMERIC_DISPATCH",
    accept=M + "const c : Exact[Real] = 2.0\nvar x : Float64\nrequire x = c",
    weakened=M + "const c : Real = 2.0\nvar x : Real\nrequire x = c",
    lost="the separation. There is one Real and no float type, so symbolic and numeric "
    "evaluation paths cannot be distinguished -- which is defensible for an idealised "
    "language but means the atom is not present.",
)
add(
    "NUMER.FINITE_DIFFERENCE",
    accept=M + "var f : Function[Real -> Real]\nvar h : PositiveReal\nvar x : Real\n"
    "def d := (f(x + h) - f(x)) / h",
    reject=M + "var f : Function[Real -> Real]\nvar h : PositiveReal\nvar x : Real\n"
    "def d := (f(x + h) - f(x)) / h\nrequire d = derivative(f(u), u : Real)",
    judgement="the difference quotient is an ordinary expression with an explicit step "
    "size. Truncation and rounding error are not carried, and the reject arm asks "
    "whether the quotient can be silently equated with the true derivative -- if it "
    "can, the atom's central caution is unenforced.",
)
add(
    "NUMER.FIXED_POINT_ITERATION",
    accept=M + "var T : Function[Real -> Real]\nvar x : Function[Natural -> Real]\n"
    "require forall n : Natural . x(n + 1) = T(x(n))",
    reject=None,
    judgement="the iteration is statable as a recurrence over a sequence-as-function. "
    "The contraction condition that makes it converge -- the atom's actual content -- "
    "has no spelling, as the reject arm records.",
)
add(
    "NUMER.FLOATING_POINT",
    accept=M + "var x : Float64\nrequire x = x",
    weakened=M + "var x : Real\nrequire x = x",
    lost="the distinction from the real. There is no finite-precision type and no "
    "format declaration, so a floating-point value and a mathematical real are the same "
    "object -- exactly the conflation the atom names.",
)
add(
    "NUMER.INTERPOLATION",
    accept=M + "var d : Vector[Real, N]\ndef p := interpolate(d, scheme := linear)",
    weakened=M + "var p : Function[Real -> Real]\nvar x0 : Real\nvar y0 : Real\n"
    "require p(x0) = y0",
    lost="the scheme and the validity region. Interpolation conditions at named points "
    "are statable one at a time; nothing constructs the interpolant or records where it "
    "may be trusted.",
)
add(
    "NUMER.INTERVAL_ARITHMETIC",
    accept=M + "var x : IntervalEnclosure[Real]\nrequire x = x",
    weakened=M + "var lo : Real\nvar hi : Real\nvar x : Real\n"
    "require lo <= x and x <= hi",
    lost="the enclosure as a value. Bounds can be asserted about a symbol, but there is "
    "no interval type that arithmetic propagates, so validated computation is out of "
    "reach.",
)
add(
    "NUMER.ITERATION_SCHEME",
    accept=M + "var T : Function[Real -> Real]\nvar x : Function[Natural -> Real]\n"
    "var tol : PositiveReal\nvar x0 : Real\n"
    "require x(0) = x0 and forall n : Natural . x(n + 1) = T(x(n))",
    reject=None,
    judgement="update rule and initial value are statable together as a quantified "
    "recurrence. The TERMINATION criterion cannot be attached and the returned object's "
    "approximate status is not marked, as the reject arm records.",
)
add(
    "NUMER.LINEAR_SOLVE",
    accept=M + "var A : Matrix[Real, N, N]\nvar b : Vector[Real, N]\n"
    "var x : Vector[Real, N]\nrequire A @ x = b",
    reject=M + "var A : Matrix[Real, N, N]\nvar b : Vector[Real, K]\n"
    "var x : Vector[Real, N]\nrequire A @ x = b",
    judgement="the SYSTEM is expressible and shape-checked, and it is correctly not "
    "written as A^{-1}b (inverse does not exist). Solving it as a COMPUTATION with "
    "conditioning-dependent accuracy is not representable at all.",
)
add(
    "NUMER.MACHINE_EPSILON",
    accept=M + "const eps : Float64 = machine_epsilon\nrequire eps > 0.0",
    weakened=M + "const eps : PositiveReal = 2.220446049250313e-16",
    lost="the relationship to a format. A hard-coded literal is not the relative "
    "spacing of a representable set, and overflow/underflow range has no expression.",
)
add(
    "NUMER.MESH",
    accept=M + "var Mh : Mesh[Real, 2]\nrequire Mh = Mh",
    weakened=M + "var nodes : Vector[Real, N]\nvar h : PositiveReal\nrequire h > 0.0",
    lost="the covering. A vector of nodes and a resolution parameter do not cover a "
    "domain, and boundary handling has no representation.",
)
add(
    "NUMER.MONTE_CARLO",
    accept=RVX + "def m := monte_carlo(expectation(X), samples := 1000)",
    weakened=RVX + "def m := expectation(X)",
    lost="the estimation. The exact expectation is expressible; the sample size, the "
    "stochastic error and the estimator's own randomness are not, so an MC estimate and "
    "the true expectation are written identically.",
)
add(
    "NUMER.OVERFLOW_UNDERFLOW",
    accept=M + "var x : Float64\nrequire x != nan",
    weakened=M + "var x : Real\nrequire x = x",
    lost="special values. There is no NaN, no infinity and no subnormal, so their "
    "propagation rules cannot be stated and an overflowing computation is "
    "indistinguishable from a finite one.",
)
add(
    "NUMER.PRECISION_FORMAT",
    accept=M + "var x : Float[64]\nrequire x = x",
    weakened=M + "var x : Real\nrequire x = x",
    lost="the format. Width and representation are not part of any numeric type, so "
    "binary32, binary64 and arbitrary precision are the same declaration.",
)
add(
    "NUMER.QUADRATURE",
    accept=M + "var f : Function[Real -> Real]\n"
    "def q := quadrature(f(x), x : Real, 0.0, 1.0, nodes := 10)",
    weakened=M + "var f : Function[Real -> Real]\n"
    "def a := integral(f(x), x : Real, 0.0, 1.0)",
    lost="the approximation. The EXACT integral is representable -- which the atom "
    "requires -- but the rule, the node count and the error estimate are not, so an "
    "approximated integral cannot be marked as one.",
)
add(
    "NUMER.RELATIVE_ERROR",
    accept=M + "var xh : Quantity[Length]\nvar xe : Quantity[Length]\n"
    "def r := abs(xh - xe) / abs(xe)",
    weakened=M + "var xh : Real\nvar xe : Real\ndef r := abs(xh - xe) / abs(xe)",
    lost="the dimensional derivation of dimensionlessness. `abs` refuses a Quantity "
    "(HML-T427), so the ratio must be formed from bare Reals and its dimensionlessness "
    "is an accident of the operand types rather than a computed fact. Undefinedness at "
    "a zero true value raises a division obligation that nothing can discharge for an "
    "unbounded symbol.",
)
add(
    "NUMER.REPRODUCIBILITY",
    not_measured="reproducibility conditions are metadata about a COMPUTED result "
    "(precision, seed, ordering, library version). HML computes nothing and has no "
    "metadata surface on a value, so no probe can be aimed at it.",
)
add(
    "NUMER.RNG_SEED",
    accept=M + "var g : Generator = mt19937(seed := 42)",
    weakened=RVX,
    lost="pseudo-randomness. A `law` statement declares a MATHEMATICAL random variable, "
    "which the atom explicitly says a pseudo-random draw is not; there is no generator, "
    "no seed and no draw.",
)
add(
    "NUMER.ROOT_FINDING",
    accept=M + "var f : Function[Real -> Real]\nvar x : Real\nrequire f(x) = 0.0",
    reject=None,
    judgement="the root CONDITION is statable. The numerical act -- bracketing, initial "
    "guess, approximate root with an error estimate -- is not, and `solve` is "
    "unimplemented (HML-P204), which the reject arm records.",
)
add(
    "NUMER.ROUNDING_MODE",
    not_measured="a rounding mode presupposes a finite-precision format to round into. "
    "NUMER.FLOATING_POINT and NUMER.PRECISION_FORMAT are both absent, so there is no "
    "operation whose rounding rule could be stated or omitted.",
)
add(
    "NUMER.SPARSITY_STRUCTURE",
    accept=M + "var A : Sparse[Matrix[Real, N, N]]\nrequire A = A",
    weakened=M + "var A : Matrix[Real, N, N]\nrequire A = A",
    lost="the structural zero. A dense matrix type cannot record that an entry is known "
    "to be zero by the model, so a structural zero and a numerically small value are "
    "the same thing.",
)
add(
    "NUMER.STABILITY",
    accept=M + "var alg : Algorithm\nrequire backward_stable(alg)",
    weakened=M + "var A : Matrix[Real, N, N]\nvar c : PositiveReal\nrequire c >= 1.0",
    lost="stability. There is no algorithm object, so a property OF A METHOD cannot be "
    "stated and cannot be kept distinct from the conditioning of the problem -- which "
    "is the atom's entire point.",
)
add(
    "NUMER.TIME_STEP",
    accept=M + "var dt : Quantity[Time]\nvar dx : Quantity[Length]\n"
    "var c : Quantity[Length / Time]\nrequire c * dt / dx <= 1.0",
    reject=M + "var dt : Quantity[Time]\nvar dx : Quantity[Length]\n"
    "var c : Quantity[Length / Time]\nrequire c * dt <= 1.0",
    judgement="the CFL condition is a dimensionless inequality and the dimension system "
    "both computes it and rejects the malformed version -- a genuinely good result. The "
    "SCHEME (explicit/implicit) it constrains has no representation.",
)
add(
    "NUMER.TOLERANCE",
    accept=M + "const tol : PositiveReal = 1e-6\nvar x : Real\nvar y : Real\n"
    "require abs(x - y) <= tol",
    reject=M + "const tol : PositiveReal = -1e-6\nvar x : Real\nvar y : Real\n"
    "require abs(x - y) <= tol",
    judgement="a tolerance is an explicit, positively typed parameter of the "
    "comparison, and a negative one is refused. Its KIND -- absolute, relative or "
    "combined -- is not part of the type, so the two spellings are indistinguishable.",
)

# ===========================================================================
# L. REASONING / EPISTEMICS  (25 atoms)
# ===========================================================================

DIV = (
    REALS
    + "assume a1 : y = 2.0 * x\n"
    + "derive d1 : y / k = 2.0 * x / k from a1 by divide_both_sides(by := k)\n"
)

add(
    "EPIS.AMBIGUITY_FLAG",
    accept=M + "var x : Real\nambiguous x",
    weakened=M + "var x : Real\nrequire x = x",
    lost="the flag. There is no way to mark a statement as ambiguous or "
    "underspecified, so the alternative to silence is silence.",
)
add(
    "EPIS.APPROXIMATION_CLAIM",
    accept=M + "var x : Real\nvar y : Real\nrequire x ~= y asymptotically",
    weakened=M + "var x : Real\nvar y : Real\nvar e : PositiveReal\n"
    "require abs(x - y) <= e",
    lost="the approximation kind and its basis. An exact inequality with a free bound "
    "records neither that the claim is approximate nor why.",
)
add(
    "EPIS.ASSERTION_VS_DEFINITION",
    accept=M + "const c : Real = 2.0\nvar x : Real\nrequire x = 3.0\n"
    "assume a1 : x > 0.0\ngoal g : x = 3.0",
    reject=M + "const c : Real = 2.0\nvar x : Real\nrequire x := 3.0",
    note="def/const := , require = , assume , goal and prove are five distinct statement "
    "forms with distinct canonical shapes, which is the atom's speech-act distinction",
)
add(
    "EPIS.ASSUMPTION",
    accept=REALS + "assume a1 : k != 0.0\ndef z := y / k",
    reject=REALS + "goal g : k != 0.0\nassume a1 : k != 0.0\nproved g by a1",
    note="assumptions are marked, labelled, enumerable, and DISCHARGE obligations. The "
    "reject probe is the atom's real test -- an assumption is taken as given, not "
    "established, so it cannot prove a goal (HML-R709).",
)
add(
    "EPIS.CAUSAL_CLAIM",
    accept=RVXY + "require causes(X, Y)",
    reject=M + "var x : Real\nvar y : Real\nrequire causes(x, y)",
    judgement="a causal claim is a first-class relation and refuses non-random "
    "operands. Its IDENTIFYING ASSUMPTIONS -- no unmeasured confounding, positivity, "
    "consistency -- cannot be attached to it, so the atom's second clause is unmet.",
)
add(
    "EPIS.CONFIDENCE_QUALIFIER",
    accept=M + "var p : Proposition\nrequire p with confidence 0.9",
    weakened=M + "param c : PosteriorProbability\nrequire c = 0.9",
    lost="the attachment. A degree of belief can be declared as a typed scalar but "
    "nothing binds it to a statement, so the qualifier qualifies nothing.",
)
add(
    "EPIS.CONSISTENCY_CHECK",
    accept=M + "var x : Real\nvar d : Quantity[Length]\nrequire x > 0.0",
    reject=M + "var x : Real\nrequire y > 0.0",
    note="type-correctness, dimensional consistency and name resolution are all "
    "mechanically checked over a body of statements; that IS this atom",
)
add(
    "EPIS.CONTRADICTION_DETECTION",
    accept=M + "var x : Real\nrequire x > 1.0\nrequire x < 0.0",
    reject=M + "var x : Real\nrequire x > 1.0 and x < 0.0",
    judgement="the accept arm records that a contradictory pair COMPILES; the reject "
    "arm asks whether the same contradiction inside one proposition is caught. Both "
    "outcomes are informative: the atom asks for detection, and this measures whether "
    "any exists at either granularity.",
)
add(
    "EPIS.CORRELATION_VS_CAUSATION",
    accept=RVXY + "require causes(X, Y)\nrequire correlated(X, Y)\n"
    "require associated(X, Y)",
    reject=M + "var x : Real\nvar y : Real\nrequire x => y",
    note="association, correlation and causation are three distinct relations, and none "
    "of them is `=>`; implication over non-propositions is refused",
)
add(
    "EPIS.COUNTEREXAMPLE",
    accept=M + "var P : Function[Natural -> Bool]\n"
    "goal g : forall n : Natural . P(n)\ncounterexample c : not P(4)",
    weakened=M + "var P : Function[Natural -> Bool]\n"
    "goal g : forall n : Natural . P(n)\nassume c : not P(4)",
    lost="the refutation link. An assumption is not checked against the claim it would "
    "refute, and no goal ever reaches REFUTED, so a counterexample is an unattached "
    "statement.",
)
add(
    "EPIS.DEFEASIBLE_INFERENCE",
    accept=REALS + "assume a1 : x > 0.0\nderive d1 : x > 0.0 from a1 by defeasibly",
    weakened=REALS + "assume a1 : x > 0.0",
    lost="defeasibility. Every kernel rule is monotone and there is no retraction, so a "
    "withdrawable conclusion cannot be marked as one.",
)
add(
    "EPIS.EVIDENCE",
    accept=M + "var p : Proposition\nobs y : Real = 1.0\nevidence y supports p",
    weakened=M + "param t : Probability\nobs y : Bool = true\n"
    "likelihood y | t ~ Bernoulli(prob := t)",
    lost="the general relation. A likelihood IS an evidential link between data and a "
    "parameter, and it is the only one: a proposition cannot be supported by data "
    "without being asserted, which is the distinction the atom draws.",
)
add(
    "EPIS.GIVEN_VS_DERIVED",
    accept=M + "obs y : Real = 1.0\nparam t : Real\nconst c : Real = 2.0\n"
    "def d := c + 1.0",
    reject=M + "obs y : Real\nparam t : Real",
    note="obs (supplied), param (estimated), const (given) and def (derived) are "
    "distinct declaration kinds carried through to the canonical form",
)
add(
    "EPIS.IDEALIZATION",
    accept=M + "var f : Real\nidealisation a1 : f = 0.0",
    weakened=M + "var f : Real\nassume a1 : f = 0.0",
    lost="the marker. An idealising assumption known to be false is spelled exactly "
    "like one believed true, so 'false-but-useful' is not recorded.",
)
add(
    "EPIS.KNOWN_UNKNOWN",
    accept=M + "var x : Real\nrequire x = x",
    reject=None,
    judgement="`var` IS the declaration of a quantity whose value is not supplied, and "
    "it is distinct from `const` (given), `obs` (measured) and absence (a name error). "
    "There is no `unknown` VALUE, which the reject arm records; that is arguably "
    "correct design rather than a gap.",
)
add(
    "EPIS.LOCAL_ASSUMPTION_SCOPE",
    accept=M + "var x : Real\ndef f(u : Real) : Real := u * u\n"
    "assume a1 : x > 0.0\ndef y := log(x)",
    reject=None,
    judgement="assumptions are module-global. There is no block, no function body scope "
    "and no branch, so an assumption cannot be confined and cannot fail to leak -- the "
    "reject arm records the absence of any scoping syntax.",
)
add(
    "EPIS.MODEL_VS_REALITY",
    accept=M + "param t : Probability\nobs y : Bool = true\n"
    "likelihood y | t ~ Bernoulli(prob := t)",
    reject=M + "param t : Probability\nobs y : Bool = true\n"
    "likelihood y | t ~ Bernoulli(prob := t)\nrequire t = 2.0",
    judgement="`obs` (a measurement of the world) and `param` (a model quantity) are "
    "different declaration kinds, which is a real model/world seam. There is no "
    "statement-level marker separating an internal claim from a claim about the world.",
)
add(
    "EPIS.NORMATIVE_VS_DESCRIPTIVE",
    accept=OPT + "minimise f\nvar x2 : Real\nrequire x2 = x2",
    reject=None,
    judgement="`minimise` (a decision rule) and `require` (a statement of how things "
    "are) are different statement forms, so the distinction exists structurally. It is "
    "not a general annotation: an arbitrary proposition cannot be marked normative, "
    "which the reject arm records.",
)
add(
    "EPIS.OPEN_PROBLEM",
    accept=M + "var x : Real\ngoal g : x = x",
    reject=M + "var x : Real\ngoal g : x = x\nproved g by nothing",
    note="`goal` states a well-formed claim WITHOUT asserting it, and the only route to "
    "PROVED is a verified derivation -- a goal cannot be promoted by fiat",
)
add(
    "EPIS.PROOF_STATUS",
    accept=REALS + "goal g : 2.0 * x = y\nassume a1 : y = 2.0 * x\n"
    "derive d1 : 2.0 * x = y from a1 by symmetry\nproved g by d1",
    reject=DIV + "goal g : y / k = 2.0 * x / k\nproved g by d1",
    note="GoalStatus/DerivationStatus/ObligationStatus are finite closed enumerations "
    "and a goal reaches PROVED only via a VERIFIED derivation; an undischarged "
    "obligation blocks it (HML-R710)",
)
add(
    "EPIS.PROVENANCE",
    accept=REALS
    + "assume a1 : y = 2.0 * x\nderive d1 : 2.0 * x = y from a1 by symmetry",
    reject=REALS + "derive d1 : 2.0 * x = y from a1 by symmetry",
    note="every derived claim names its premises and its rule, and citing an "
    "unestablished premise is refused (HML-R703). Provenance for DATA and CONSTANTS "
    "(where a number came from) has no representation.",
)
add(
    "EPIS.SCOPE_OF_APPLICABILITY",
    accept=M + "var x : Real\nrequire x > 0.0 for population adults",
    weakened=M + "var x : Real\nrequire x > 0.0",
    lost="the reference class. A claim carries no population, no unit and no time "
    "period, so two claims about different populations are identical statements.",
)
add(
    "EPIS.SENSITIVITY_TO_ASSUMPTION",
    accept=REALS + "assume a1 : k != 0.0\ndef z := y / k\nsensitivity z to a1",
    weakened=REALS + "assume a1 : k != 0.0\ndef z := y / k",
    lost="the sensitivity relation. The dependency of a conclusion on an assumption is "
    "recorded structurally (the obligation names its discharger) but HOW MUCH the "
    "conclusion changes if the assumption is varied is not expressible.",
)
add(
    "EPIS.TRANSLATION_LOSS_DECLARATION",
    accept=REALS + "assume a1 : k != 0.0\ndef z := y / k",
    structural=("backend_checks", "lean_declares_loss_for_law_and_pvalue"),
    note="MEASURED BY BACKEND, not by an accept/reject pair: every Backend subclass "
    "must report via "
    "drop()/approximate()/weaken(), and backend_checks() below asserts that a module "
    "whose semantics no target carries emits a non-empty Unsupported list. The reject "
    "slot is None because the enforcement is structural rather than a rejected source.",
)
add(
    "EPIS.VALIDITY_DOMAIN",
    accept=M + "var f : Function[PositiveReal -> Real]\n"
    "require forall s : PositiveReal . f(s) = log(s)",
    reject=M + "var f : Function[PositiveReal -> Real]\nvar x : Real\n"
    "require f(x) = 0.0",
    judgement="a domain of validity IS expressible when it is a type refinement, and "
    "using the result outside it is refused -- that is the strongest form of the atom. "
    "A validity domain that is not a type (a regime, a population, a range of "
    "conditions) has no representation.",
)

# ===========================================================================
# M. TRANSFORMATIONS / INFERENCE  (38 atoms)
# ===========================================================================

add(
    "XFORM.ALPHA_RENAMING",
    accept=M + "require forall x : Real . x = x",
    structural=("hash_checks", "alpha_variants_share_a_hash"),
    downgrade="the atom asks for renaming to be PERFORMED where needed. HML never "
    "renames: it rejects a capture-risking nested binder (HML-N302) and refuses "
    "substitution under a binder. Alpha-INVARIANCE of identity holds -- the executed "
    "hash check confirms it -- but the transformation itself does not exist.",
)
add(
    "XFORM.BETA_REDUCTION",
    accept=M + "def f(u : Real) : Real := u * u\nrequire f(2.0) = 4.0",
    reject=M + "def f(u : Real) : Real := u * u\nrequire f(2.0, 3.0) = 4.0",
    judgement="application is checked against the definition's ordered parameters. No "
    "REDUCTION is performed -- f(2.0) is not rewritten to 2.0 * 2.0 anywhere -- so the "
    "atom's evaluation-order clause is vacuous.",
)
add(
    "XFORM.CANONICALIZATION",
    accept=M + "require forall x : Real . exists y : Real . y > x",
    structural=("hash_checks", "quantifier_order_changes_the_hash"),
    note="the substantive claim -- that canonicalisation must NOT reorder quantifiers "
    "-- is exactly what the executed hash check measures; the companion check that "
    "alpha-variants DO collapse is recorded alongside it in hash_checks",
)
add(
    "XFORM.CASE_ANALYSIS",
    accept=M + "var x : Real\nvar p : Proposition\nvar q : Proposition\n"
    "assume a1 : p or q\nassume a2 : p => x > 0.0\nassume a3 : q => x > 0.0\n"
    "derive d1 : x > 0.0 from a1, a2, a3 by or_elim",
    weakened=M + "var x : Real\nvar p : Proposition\nvar q : Proposition\n"
    "require (p or q) and (p => x > 0.0) and (q => x > 0.0)",
    lost="the inference. Disjunction elimination is not a kernel rule, so the case "
    "split cannot be USED; exhaustiveness is asserted, never required, and no branch "
    "carries its case hypothesis.",
)
add(
    "XFORM.CHANGE_OF_REPRESENTATION",
    accept=M + "var x : Real\nrequire x > 0.0",
    structural=("backend_checks", "all_five_targets_emit"),
    note="MEASURED BY BACKEND: the same module is emitted to latex, lean, stan, sympy "
    "and english, each a faithful view of one semantic object. backend_checks() below "
    "asserts that all five emit non-empty text for one module and that the content hash "
    "is unchanged by the emission.",
)
add(
    "XFORM.COMPILATION_TO_BACKEND",
    accept=RVX + "param p : PValue",
    structural=("backend_checks", "lean_declares_loss_for_law_and_pvalue"),
    note="MEASURED BY BACKEND: backend_checks() asserts that lowering a module "
    "containing a law and a PValue to Lean produces a non-empty Unsupported list rather "
    "than silently dropping either construct",
)
add(
    "XFORM.CONDITIONING_OP",
    accept=M + "param t : Probability\nprior t ~ Beta(alpha := 1.0, beta := 1.0)\n"
    "obs y : Bool = true\nlikelihood y | t ~ Bernoulli(prob := t)\ninfer posterior t",
    reject=M + "param t : Probability\nprior t ~ Beta(alpha := 1.0, beta := 1.0)\n"
    "var y : Bool\nlikelihood y | t ~ Bernoulli(prob := t)\ninfer posterior t",
    judgement="conditioning on observations is a real model transformation here: the "
    "`obs` kind is what makes the joint model conditional, and the reject arm tests "
    "whether conditioning on a non-observed symbol is refused. The conditioning "
    "OPERATION is not a term and cannot be applied to a model value.",
)
add(
    "XFORM.CONSTRAINT_PROPAGATION",
    accept=REALS + "assume a1 : k > 0.0\ndef z := y / k",
    reject=REALS + "assume a1 : k >= 0.0\ndef z := y / k\ngoal g : z = z\n"
    "derive d1 : z = z from a1 by symmetry",
    note="the refinement environment derives k != 0 from k > 0 and discharges the "
    "division obligation; it correctly refuses to derive it from k >= 0, so propagation "
    "is sound rather than merely present",
)
add(
    "XFORM.CONTRADICTION_PROOF",
    accept=M + "var p : Proposition\nvar q : Proposition\nassume a1 : p => q\n"
    "assume a2 : not q\nderive d1 : not p from a2, a1 by modus_tollens",
    reject=M + "var p : Proposition\nvar q : Proposition\nassume a1 : p => q\n"
    "assume a2 : q\nderive d1 : p from a2, a1 by modus_tollens",
    note="contraposition is a kernel rule and affirming the consequent is refused. "
    "Reductio proper -- assuming not-P and deriving falsity -- has no rule and no "
    "falsity constant.",
)
add(
    "XFORM.DIFF_OF_STATEMENTS",
    accept=M + "var x : Real\nrequire x > 0.0\ndiff against previous",
    weakened=M + "var x : Real\nrequire x > 0.0",
    lost="the comparison. Two modules have comparable content hashes, so INEQUALITY is "
    "detectable, but no semantic delta -- 'an assumption was added, a bound weakened' -- "
    "is produced by anything.",
)
add(
    "XFORM.EQUATIONAL_REASONING",
    accept=REALS + "assume a1 : x = y\nassume a2 : y = k\n"
    "derive d1 : x = k from a1, a2 by transitivity",
    reject=REALS + "assume a1 : x > y\nderive d1 : y > x from a1 by symmetry",
    note="a chain of justified steps is exactly the derive spine, and the kernel "
    "refuses to apply an equality rule to an inequality, so the relation is composed "
    "correctly rather than assumed",
)
add(
    "XFORM.EVALUATION_PARTIAL",
    accept=M + "const c : Real = 2.0\nvar x : Real\ndef y := c + x",
    reject=None,
    judgement="a term mixing knowns and unknowns is well-formed and unknowns stay "
    "symbolic, which is the atom's requirement that partial evaluation not fail. "
    "Nothing EVALUATES the known part, so 'evaluating what can be evaluated' is "
    "trivially satisfied by evaluating nothing.",
)
add(
    "XFORM.EXISTENTIAL_WITNESS",
    accept=M + "var x : Real\nassume a1 : exists u : Real . u > 0.0\n"
    "derive d1 : x > 0.0 from a1 by exists_elim(witness := x)",
    weakened=M + "require exists x : Real . x * x = 4.0",
    lost="both directions of use. An existential is statable but there is no rule to "
    "establish it from a witness and no rule to introduce a fresh constant from it, so "
    "it can never enter or leave a derivation.",
)
add(
    "XFORM.INDUCTION_APPLICATION",
    accept=M + "var P : Function[Natural -> Bool]\nassume a1 : P(0)\n"
    "assume a2 : forall n : Natural . P(n) => P(n + 1)\n"
    "derive d1 : forall n : Natural . P(n) from a1, a2 by induction",
    weakened=M + "var P : Function[Natural -> Bool]\n"
    "require P(0) and (forall n : Natural . P(n) => P(n + 1)) "
    "=> forall n : Natural . P(n)",
    lost="the inference. Induction is not a kernel rule (HML-R704), so the schema can "
    "be ASSERTED as a proposition but never applied, and no universal over Natural is "
    "ever discharged.",
)
add(
    "XFORM.LOSS_ANNOTATION",
    accept=RVX,
    structural=("backend_checks", "severities_within_closed_set"),
    note="MEASURED BY BACKEND: Unsupported carries construct / reason / line / severity "
    "in {dropped, approximated, weakened}, which is exactly the machine-readable "
    "three-way distinction the atom asks for. backend_checks() asserts the severities "
    "are drawn from that closed set.",
)
add(
    "XFORM.MARGINALIZATION",
    accept=RVXY + "def j := joint(X, Y)\ndef m := marginalise(j, over := Y)",
    weakened=RVXY + "def j := joint(X, Y)",
    lost="the operation. The joint is an object but nothing eliminates a variable from "
    "it, so the eliminated variable is never identified and no inference is performed.",
)
add(
    "XFORM.MODUS_PONENS",
    accept=M + "var p : Proposition\nvar q : Proposition\nassume a1 : p => q\n"
    "assume a2 : p\nderive d1 : q from a2, a1 by modus_ponens",
    reject=M + "var p : Proposition\nvar q : Proposition\nassume a1 : p => q\n"
    "assume a2 : q\nderive d1 : p from a2, a1 by modus_ponens",
    note="detachment is a kernel rule, the hypothesis is recorded as a premise, and "
    "affirming the consequent is refused",
)
add(
    "XFORM.MOMENT_COMPUTATION",
    accept=M + "def d : Distribution[Real] := Normal(location := 0.0, scale := 1.0)\n"
    "def m := expectation(d)",
    weakened=RVX + "def m := expectation(X)",
    lost="the derivation from the distribution OBJECT. Expectation applies to a random "
    "variable, and its value is never computed from the family, so 'the mean of a "
    "Normal(0,1) is 0' is not derivable.",
)
add(
    "XFORM.NORMAL_FORM",
    accept=M + "require forall x : Real . x = x",
    reject=None,
    judgement="a deterministic canonical form exists and is the content hash's input. "
    "It is a structural normalisation, NOT reached by exhaustive rewriting, so "
    "confluence and termination are not properties anything has -- the atom's stated "
    "conditions do not apply.",
)
add(
    "XFORM.PATTERN_MATCHING",
    accept=REALS + "assume a1 : y = 2.0 * x\n"
    "derive d1 : y + 1.0 = 2.0 * x + 1.0 from a1 by add_both_sides(by := 1.0)",
    reject=REALS + "assume a1 : y > 2.0 * x\n"
    "derive d1 : y + 1.0 = 2.0 * x + 1.0 from a1 by add_both_sides(by := 1.0)",
    note="the kernel matches a premise against a rule's input shape and refuses a "
    "mismatch. It is internal: there is no user-facing pattern language, and matching "
    "under binders is deliberately refused (see LOGIC.SUBSTITUTION).",
)
add(
    "XFORM.PRENEX_NORMAL_FORM",
    accept=M + "require forall x : Real . exists y : Real . y > x",
    reject=None,
    judgement="prenex statements are writable and quantifier ORDER is preserved by "
    "canonicalisation. No quantifier MOVEMENT is performed and no dual switching under "
    "negation is implemented, so the transformation the atom names does not exist.",
)
add(
    "XFORM.PROOF_CHECKING",
    accept=REALS
    + "assume a1 : y = 2.0 * x\nderive d1 : 2.0 * x = y from a1 by symmetry",
    reject=REALS + "assume a1 : y = 2.0 * x\nderive d1 : 3.0 * x = y from a1 by symmetry",
    note="the kernel builds the conclusion WITHOUT seeing the author's, then compares "
    "canonical identities (HML-R706) -- a producer-independent check, which is the atom",
)
add(
    "XFORM.QUANTIFIER_ELIMINATION",
    accept=M + "var x : Real\nrequire eliminate(exists y : Real . y > x)",
    weakened=M + "require forall x : Real . exists y : Real . y > x",
    lost="the elimination. Quantified formulae are statable but no equivalent "
    "quantifier-free form is produced by anything, and no decidable theory is "
    "identified.",
)
add(
    "XFORM.QUERY_OVER_STATEMENTS",
    accept=REALS + "assume a1 : k != 0.0\ndef z := y / k",
    structural=("structural_checks", "has_reasoning"),
    downgrade="there is no query LANGUAGE. The handles exist on the compile result, so "
    "a consumer can answer structural questions, but that is an API property rather "
    "than a property of the representation the atom is about.",
    note="MEASURED STRUCTURALLY: the compile result exposes module.statements, "
    "symbols, obligations and reasoning claims as inspectable data, so 'which "
    "statements assume X' is answerable by a consumer. There is no query LANGUAGE, so "
    "this is an API property, not a language one; structural_checks() asserts the "
    "handles exist.",
)
add(
    "XFORM.REWRITING",
    accept=REALS + "assume a1 : y = 2.0 * x\nassume a2 : y > 0.0\n"
    "derive d1 : 2.0 * x > 0.0 from a1, a2 by substitute",
    reject=REALS + "assume a1 : y = 2.0 * x\n"
    "derive d1 : 2.0 * x > 0.0 from a1 by rewrite",
    judgement="oriented replacement of equals is available as `substitute`, with the "
    "capture side condition enforced by refusal. There is no user-supplied rule set and "
    "no termination argument, which the reject arm records as the absence of a general "
    "rewrite rule.",
)
add(
    "XFORM.ROUND_TRIP",
    accept=M + "require forall x : Real . exists y : Real . y > x",
    structural=("roundtrip_checks", "all_preserved"),
    note="MEASURED STRUCTURALLY: roundtrip_checks() emits each of a set of modules "
    "through the hml backend, re-parses the output, and compares content hashes. That "
    "is the atom's own criterion and it cannot be expressed as an accept/reject pair.",
)
add(
    "XFORM.SEMANTICS_PRESERVING_CHECK",
    accept=REALS
    + "assume a1 : y = 2.0 * x\nderive d1 : 2.0 * x = y from a1 by symmetry",
    reject=REALS + "assume a1 : y = 2.0 * x\nderive d1 : 2.0 * x = y from a1 by "
    "multiply_both_sides(by := 0.0)",
    note="each derivation step is accompanied by the kernel's own check that the output "
    "follows from the input, and a step whose stated conclusion is not what the rule "
    "yields is rejected",
)
add(
    "XFORM.SIMPLIFICATION",
    accept=REALS + "assume a1 : k != 0.0\nassume a2 : x * k = y * k\n"
    "derive d1 : x * k / k = y * k / k from a2 by divide_both_sides(by := k)",
    reject=REALS + "assume a2 : x * k = y * k\n"
    "derive d1 : x = y from a2 by divide_both_sides(by := k)",
    judgement="the domain-of-definition side of the atom is genuinely handled: "
    "cancellation raises a nonzero obligation and the unguarded version is refused. "
    "No simplification is PERFORMED -- x*k/k is not reduced to x -- so complexity is "
    "never actually reduced.",
)
add(
    "XFORM.SKOLEMIZATION",
    accept=M + "var f : Function[Real -> Real]\n"
    "require skolemise(forall x : Real . exists y : Real . y > x)",
    weakened=M + "var f : Function[Real -> Real]\n"
    "require forall x : Real . f(x) > x",
    lost="the transformation and its record. The Skolemised form is writable by hand "
    "but nothing derives it, nothing marks it as Skolemised, and satisfiability "
    "preservation is unstated -- the atom explicitly warns against silent Skolemisation.",
)
add(
    "XFORM.SOLVE_FOR",
    accept=M + "var x : Real\nsolve x + 1.0 = 2.0 for x",
    weakened=M + "var x : Real\ndef S := { u : Real | u + 1.0 = 2.0 }",
    lost="the operation. `solve` is a reserved keyword with no production (HML-P204), "
    "so the solution SET can be written by hand as a comprehension but nothing produces "
    "it, and no branch choices or domain conditions are recorded.",
)
add(
    "XFORM.STAGING",
    not_measured="staging distinguishes a symbolic phase from a numeric one. HML has no "
    "numeric evaluation phase at all -- nothing is ever computed -- so there is no "
    "boundary to make explicit and no probe that could observe one.",
)
add(
    "XFORM.SUBSTITUTION_RULE",
    accept=REALS + "assume a1 : x = y\nassume a2 : x > 0.0\n"
    "derive d1 : y > 0.0 from a1, a2 by substitute",
    reject=M + "var x : Real\nvar y : Real\nassume a1 : x = y\n"
    "assume a2 : forall u : Real . x != u\n"
    "derive d1 : forall u : Real . y != u from a1, a2 by substitute",
    note="replacing equals by equals is a kernel rule, and it refuses to descend under "
    "a binder rather than performing an unsound substitution -- which is precisely the "
    "restriction the atom names",
)
add(
    "XFORM.SYMBOLIC_DIFFERENTIATION",
    accept=M + "var f : Function[Real -> Real]\n"
    "def d := derivative(f(x), x : Real)",
    reject=M + "var f : Function[Real -> Real]\ndef d := derivative(f(x), x)",
    downgrade="nothing is PRODUCED. There is no rule or evaluation that turns "
    "derivative(x * x, x : Real) into 2 * x, so the atom's 'producing a derivative "
    "expression' is met only in the sense of writing one down by hand.",
    judgement="a derivative EXPRESSION with respect to a named typed variable is "
    "formable and the binder is mandatory. No derivative is COMPUTED -- there is no "
    "rule producing d/dx (x*x) = 2x -- so the atom's 'producing a derivative "
    "expression' is met only in the sense of writing one down.",
)
add(
    "XFORM.SYMBOLIC_INTEGRATION",
    accept=M + "var f : Function[Real -> Real]\n"
    "def F := symbolic_integral(f(x), x : Real)",
    weakened=M + "var f : Function[Real -> Real]\n"
    "def a := integral(f(x), x : Real, 0.0, 1.0)",
    lost="the attempt and its outcome. An integral expression is formable, but nothing "
    "tries for a closed form, so 'reporting failure explicitly' -- the atom's actual "
    "requirement -- has no occasion to happen.",
)
add(
    "XFORM.TOPOLOGICAL_ORDER",
    accept=M + "const c : Real = 2.0\ndef d := c + 1.0\ndef e := d + 1.0",
    reject=M + "def a := b + 1.0\ndef b := a + 1.0",
    note="definitions are ordered by dependency and cycles are detected and reported "
    "(HML-S606); the same acyclicity discipline governs the reasoning graph",
)
add(
    "XFORM.TYPE_INFERENCE",
    accept=M + "param mu : Real\nparam sigma : PositiveReal\nvar z : Real\n"
    "def v := mu + sigma * z",
    reject=M + "param mu : Real\nvar b : Bool\ndef v := mu + b",
    note="compound expressions synthesise a type and ill-typed ones are rejected with a "
    "localised diagnostic",
)
add(
    "XFORM.UNIFICATION",
    accept=REALS + "assume a1 : y = 2.0 * x\n"
    "derive d1 : y + 1.0 = 2.0 * x + 1.0 from a1 by add_both_sides(by := 1.0)",
    reject=REALS + "assume a1 : y = 2.0 * x\n"
    "derive d1 : y + 1.0 = 2.0 * x + 2.0 from a1 by add_both_sides(by := 1.0)",
    judgement="the kernel's premise matching is a restricted, first-order, "
    "occurs-check-free form of unification and it does reject a non-matching "
    "conclusion. There is no general unification over terms and types at the surface.",
)
add(
    "XFORM.UNIVERSAL_INSTANTIATION",
    accept=M + "var x : Real\nassume a1 : forall u : Real . u = u\n"
    "derive d1 : x = x from a1 by instantiate(at := x)",
    weakened=M + "require forall u : Real . u = u",
    lost="the inference. A universal is statable but no kernel rule instantiates it, so "
    "a universally quantified fact can never be applied to a particular term.",
)


# ---------------------------------------------------------------------------
# Structural assertions that no accept/reject pair can express
# ---------------------------------------------------------------------------


def hash_checks() -> dict[str, Any]:
    """Content-hash claims underlying the canonicalisation family of atoms.

    These are executed, not asserted: each entry records the real hashes.
    """
    nested = M + "require forall x : Real . exists y : Real . y > x"
    swapped = M + "require exists y : Real . forall x : Real . y > x"
    renamed = M + "require forall u : Real . exists v : Real . v > u"
    out: dict[str, Any] = {}
    try:
        hn = H.compile_source(nested).hash()
        hs = H.compile_source(swapped).hash()
        hr = H.compile_source(renamed).hash()
        out["alpha_variants_share_a_hash"] = hn == hr
        out["quantifier_order_changes_the_hash"] = hn != hs
        out["hashes"] = {"nested": hn[:16], "swapped": hs[:16], "renamed": hr[:16]}
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def backend_checks() -> dict[str, Any]:
    """Loss-declaration and multi-view claims. Backing for four M/L atoms."""
    import importlib

    src = RVX + "param p : PValue\ncheck dimension 1.0\n"
    plain = M + "var x : Real\nrequire x > 0.0\n"
    out: dict[str, Any] = {}
    try:
        r = H.compile_source(RVX + "param p : PValue")
        emitted: dict[str, Any] = {}
        severities: set[str] = set()
        for target in ("latex", "lean", "stan", "sympy", "english"):
            mod = importlib.import_module(f"hamiltonian_lang.backends.{target}")
            cls = _backend_class(mod)
            if cls is None:
                emitted[target] = "no Backend subclass"
                continue
            res = cls(r.module, r.symbols).run()
            emitted[target] = {
                "chars": len(res.text),
                "losses": len(res.unsupported),
            }
            severities |= {u.severity for u in res.unsupported}
        out["emitted"] = emitted
        out["severities_observed"] = sorted(severities)
        out["severities_within_closed_set"] = severities <= {
            "dropped",
            "approximated",
            "weakened",
        }
        out["lean_declares_loss_for_law_and_pvalue"] = (
            isinstance(emitted.get("lean"), dict) and emitted["lean"]["losses"] > 0
        )
        out["all_five_targets_emit"] = all(
            isinstance(v, dict) and v["chars"] > 0 for v in emitted.values()
        ) and len(emitted) == 5
        out["plain_module_compiles"] = H.compile_source(plain).ok()
        out["src_probe_compiles"] = H.compile_source(src).ok()
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def roundtrip_checks() -> dict[str, Any]:
    """Parse -> print -> re-parse must preserve the content hash. Backs XFORM.ROUND_TRIP."""
    from hamiltonian_lang.backends import hml as hml_backend

    cases = [
        M + "require forall x : Real . exists y : Real . y > x",
        M + "var x : Real\nrequire x > 0.0 and x < 1.0",
        RVX,
        M + "param mu : Real\nparam s : PositiveReal\nvar z : Real\n"
        "def v := mu + s * z",
        M + "def T := { x : Real | x > 0.0 }",
        REALS + "assume a1 : y = 2.0 * x\n"
        "derive d1 : 2.0 * x = y from a1 by symmetry",
    ]
    results = []
    cls = _backend_class(hml_backend)
    render = getattr(hml_backend, "render_module", None) or getattr(
        hml_backend, "render", None
    )
    for src in cases:
        try:
            r = H.compile_source(src)
            if not r.ok():
                results.append({"ok": False, "why": "does not compile"})
                continue
            if cls is not None:
                text = cls(r.module, r.symbols).run().text
            elif render is not None:
                text = render(r.module)
            else:
                results.append({"ok": False, "why": "no hml emitter found"})
                continue
            r2 = H.compile_source(text)
            results.append(
                {
                    "ok": bool(r2.ok()) and r2.hash() == r.hash(),
                    "reparse_ok": bool(r2.ok()),
                    "hash_equal": r2.hash() == r.hash() if r2.ok() else False,
                }
            )
        except Exception as e:  # noqa: BLE001
            results.append({"ok": False, "why": f"{type(e).__name__}: {e}"})
    preserved = sum(1 for x in results if x.get("ok"))
    return {
        "cases": len(cases),
        "preserved": preserved,
        "all_preserved": preserved == len(cases),
        "detail": results,
    }


def structural_checks() -> dict[str, Any]:
    """Inspectable-handle claims backing XFORM.QUERY_OVER_STATEMENTS."""
    out: dict[str, Any] = {}
    try:
        r = H.compile_source(REALS + "assume a1 : k != 0.0\ndef z := y / k")
        out["has_statements"] = hasattr(r.module, "statements")
        out["n_statements"] = len(r.module.statements)
        out["has_symbols"] = r.symbols is not None
        out["has_obligations"] = hasattr(r, "obligations")
        out["n_obligations"] = len(r.obligations or [])
        out["has_reasoning"] = hasattr(r, "reasoning")
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    return out


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def load_ontology() -> tuple[list[dict[str, Any]], str]:
    raw = ONTOLOGY.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)["atoms"], digest


def main() -> int:
    atoms, digest = load_ontology()
    if digest != ONTOLOGY_SHA256:
        print(f"ONTOLOGY SHA MISMATCH\n  expected {ONTOLOGY_SHA256}\n  got      {digest}")
        return 2

    ids = {a["id"] for a in atoms}
    missing = sorted(ids - set(SPECS))
    extra = sorted(set(SPECS) - ids)
    if extra:
        print(f"specs that name no ontology atom: {extra}")
        return 2
    if missing:
        print(f"{len(missing)} atoms have no spec:")
        for m in missing[:40]:
            print(f"  {m}")
        return 2

    checks = {
        "hash_checks": hash_checks(),
        "backend_checks": backend_checks(),
        "roundtrip_checks": roundtrip_checks(),
        "structural_checks": structural_checks(),
    }

    outcomes: list[Outcome] = []
    for a in atoms:
        spec = SPECS[a["id"]]
        state, evidence, ac, rc = classify(spec, checks)
        srcs = {}
        if spec.accept:
            srcs["accept"] = spec.accept
        if spec.reject:
            srcs["reject"] = spec.reject
        if spec.weakened:
            srcs["weakened"] = spec.weakened
        outcomes.append(
            Outcome(
                atom=a["id"],
                domain=a["domain"],
                criticality=a["criticality"],
                state=state,
                evidence=evidence,
                accept_codes=ac,
                reject_codes=rc,
                note=spec.note,
                judgement=spec.judgement,
                sources=srcs,
            )
        )

    states = ("PASS", "PARTIAL", "BACKEND_ONLY", "LOSSY", "ABSENT", "NOT_MEASURED")
    overall = {s: sum(1 for o in outcomes if o.state == s) for s in states}
    critical = {
        s: sum(1 for o in outcomes if o.state == s and o.criticality == "CRITICAL")
        for s in states
    }
    by_domain: dict[str, dict[str, int]] = {}
    for o in outcomes:
        d = by_domain.setdefault(o.domain, {s: 0 for s in states})
        d[o.state] += 1

    payload = {
        "generated_by": "audit_rerun/probe_all_atoms.py",
        "ontology_sha256": digest,
        "ontology_path": str(ONTOLOGY),
        "hml_source_tree": _SRC,
        "hml_source_sha": _git_sha(),
        "n_atoms": len(outcomes),
        "state_definitions": {
            "PASS": "representable AND enforced (faithful encoding accepted, misuse "
            "rejected)",
            "PARTIAL": "representable but incompletely enforced, or only in a "
            "restricted position",
            "BACKEND_ONLY": "expressible only by lowering to a backend",
            "LOSSY": "faithful spelling refused; a weakened encoding compiles and a "
            "named property is lost",
            "ABSENT": "no faithful encoding exists",
            "NOT_MEASURED": "no meaningful executable probe could be constructed",
        },
        "counts_all_486": overall,
        "counts_critical_64": critical,
        "counts_by_domain": by_domain,
        "hash_checks": checks["hash_checks"],
        "backend_checks": checks["backend_checks"],
        "roundtrip_checks": checks["roundtrip_checks"],
        "structural_checks": checks["structural_checks"],
        "atoms": [o.to_dict() for o in outcomes],
    }

    out = HERE / "results" / "ALL_ATOMS.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))

    for o in outcomes:
        print(f"{o.atom:44s} {o.criticality:8s} {o.state}")
    print()
    print(f"ALL 486  : {overall}")
    print(f"CRITICAL : {critical}")
    print(f"-> {out}")
    return 0


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
