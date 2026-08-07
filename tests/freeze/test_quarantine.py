"""Mechanical enforcement of `docs/evaluation/V1_FREEZE_MANIFEST.md`.

Phase F1 deliverable. The manifest classifies every feature; this file makes the
classification *load-bearing* rather than descriptive.

The rule it enforces
--------------------
**Every feature classified below ``SUPPORTED_ENFORCED`` must be unreachable from the
frozen syntax gate.** "The syntax gate" is what ``hml check`` accepts: the closed
keyword set, the closed statement-kind set, and the closed type-name set declared in
:mod:`tests.freeze.frozen_subset`.

Three independent barriers are asserted, so no single edit can breach the gate quietly:

1. **The closed sets themselves.** ``lexer.KEYWORDS``, the ``ast.nodes.Statement``
   subclasses and the admissible type names must equal the frozen sets exactly.
   Adding ``goal`` to the lexer, or a ``GoalStmt`` to the AST, fails here — before any
   behavioural test would notice.
2. **The import barrier.** No module under ``src/hamiltonian_lang/`` outside ``v1/``
   may import ``hamiltonian_lang.v1``, statically or at run time. That edge is the only
   way the quarantined layers could become reachable from ``compile_source``.
3. **Behavioural probes.** Every surface form V1_KERNEL.md proposes for a quarantined
   layer is compiled and must be rejected; every quarantined type name is placed in
   type position and must be rejected.

**Known-failure pins** are included. They assert that a currently-open hole is *still*
open. That is deliberate: if the hole is closed, this file fails, and the manifest must
be re-evidenced and re-classified in the same change. A freeze manifest that silently
keeps saying KNOWN_FAILED after the failure is fixed is as wrong as one that says
SUPPORTED_ENFORCED before it is.

The mechanism has now fired once, as designed. The `PValue` pin asserted that the
p-value-as-posterior conflation type-checked; D-022 closed it, the pin failed, and the
manifest row moved to `SUPPORTED_ENFORCED` with new evidence in the same change. What
replaced it is a pair: an assertion that the conflation is rejected when the kinds are
declared, and a narrower pin on the residual hole — a *mis-declared* p-value is still
admitted, and no type system detects that.
"""

from __future__ import annotations

import ast
import inspect
import re
import subprocess
import sys

import pytest

from hamiltonian_lang import compile_source
from hamiltonian_lang.ast import nodes as ast_nodes
from hamiltonian_lang.lexer import KEYWORDS
from hamiltonian_lang.types import SCALARS

from .frozen_subset import (
    CLASSIFICATIONS,
    COMPILER_SOURCE_DIR,
    FROZEN_KEYWORDS,
    FROZEN_SCALARS,
    FROZEN_STATEMENT_KINDS,
    FROZEN_TYPE_CONSTRUCTORS,
    GATE_ADMITS,
    MANIFEST,
    MANIFEST_CLASSIFICATION,
    QUARANTINED_PACKAGE,
    QUARANTINED_PACKAGE_DIR,
    QUARANTINED_SURFACE_FORMS,
    QUARANTINED_TYPE_NAMES,
    REQUIRED_MANIFEST_ROWS,
    quarantined_rows,
)

#: Words the V2 reasoning spine (D-025) claimed as statement heads in its own right.
#:
#: `goal` and `derive` lead a quarantined V1_KERNEL form *and* a V2 form, but they are
#: different grammars: V1_KERNEL wrote `goal g1 := 1 > 0` and
#: `derive e3 from [e1, e2] via s1`; V2 writes `goal g1 : 1 > 0` and
#: `derive d1 : c from p by rule(...)`. The V1_KERNEL spellings are still rejected --
#: `test_a_quarantined_surface_form_does_not_compile` proves it for every form in the
#: table -- so what is quarantined is the *layer*, and the word being spoken for by V2
#: does not unquarantine it. Subtracting these two here keeps the advertisement check
#: meaningful for the fifteen forms that remain genuinely unreachable.
V2_CLAIMED_HEADS = frozenset({"goal", "derive"})

#: The leading token of every quarantined surface form, i.e. the keyword each would need.
QUARANTINED_SURFACE_FORMS_HEADS = tuple(
    sorted({form.split()[0] for form in QUARANTINED_SURFACE_FORMS} - V2_CLAIMED_HEADS)
)


def _codes(source: str) -> tuple[bool, list[str]]:
    """Compile ``source`` and return ``(ok, diagnostic codes)``."""
    result = compile_source(source, "<freeze-probe>")
    return result.ok(), [d.code for d in result.diagnostics.items]


# ---------------------------------------------------------------------------
# Barrier 1 — the closed sets that define the gate
# ---------------------------------------------------------------------------


def test_the_keyword_set_is_exactly_the_frozen_set():
    """A new surface keyword is how an L2-L5 construct would enter the gate."""
    added = sorted(set(KEYWORDS) - FROZEN_KEYWORDS)
    removed = sorted(FROZEN_KEYWORDS - set(KEYWORDS))
    assert not added, (
        f"keyword(s) {added} were added to the lexer without amending the freeze "
        f"manifest. If this is intended, classify the construct in "
        f"{MANIFEST.name} with executed evidence and update FROZEN_KEYWORDS."
    )
    assert not removed, f"keyword(s) {removed} vanished from the lexer"


def test_the_statement_kinds_are_exactly_the_frozen_set():
    live = {
        name
        for name, obj in vars(ast_nodes).items()
        if inspect.isclass(obj)
        and issubclass(obj, ast_nodes.Statement)
        and obj is not ast_nodes.Statement
    }
    assert live == FROZEN_STATEMENT_KINDS, (
        f"the statement inventory changed: added={sorted(live - FROZEN_STATEMENT_KINDS)}, "
        f"removed={sorted(FROZEN_STATEMENT_KINDS - live)}"
    )


def test_the_scalar_lattice_is_exactly_the_frozen_set():
    assert set(SCALARS) == FROZEN_SCALARS, (
        "a scalar type was added or removed. A scalar entering types.py is admissible "
        "in type position immediately, so it enters the gate as a side effect unless "
        "FROZEN_SCALARS and the manifest move with it (PValue / PosteriorProbability "
        "did so under D-022; Credence and the Justification types have not)"
    )


def test_the_three_unit_interval_kinds_are_pairwise_incomparable():
    """The D-022 lattice shape, asserted where the gate is defined.

    A later edit that gives one of these a parent among the others would restore the
    coercion path §4 of the manifest reports as closed, without touching any test that
    names a diagnostic code.
    """
    from hamiltonian_lang.types import UNIT_INTERVAL_KINDS, ScalarType, is_subtype

    assert UNIT_INTERVAL_KINDS <= set(SCALARS)
    for a in UNIT_INTERVAL_KINDS:
        for b in UNIT_INTERVAL_KINDS:
            if a == b:
                continue
            assert not is_subtype(ScalarType(a), ScalarType(b)), (
                f"{a} is now a subtype of {b}; that is a coercion path between two "
                f"epistemic kinds and D-022 forbids it in both directions"
            )


@pytest.mark.parametrize("name", sorted(QUARANTINED_TYPE_NAMES))
def test_a_quarantined_type_name_is_not_admissible_in_type_position(name):
    ok, codes = _codes(f"module M\nparam x : {name}\n")
    assert not ok, f"{name!r} is accepted in type position; it is a quarantined V1 type"
    assert "HML-T440" in codes, f"expected HML-T440 (unknown type) for {name!r}, got {codes}"


def test_no_quarantined_type_name_leaked_into_the_type_constructors():
    overlap = set(QUARANTINED_TYPE_NAMES) & (FROZEN_SCALARS | FROZEN_TYPE_CONSTRUCTORS)
    assert not overlap, f"quarantined type name(s) {sorted(overlap)} are in the frozen set"


# ---------------------------------------------------------------------------
# Barrier 2 — the V0 -> V1 import barrier
# ---------------------------------------------------------------------------


def _compiler_modules():
    for path in sorted(COMPILER_SOURCE_DIR.rglob("*.py")):
        if QUARANTINED_PACKAGE_DIR in path.parents or path == QUARANTINED_PACKAGE_DIR:
            continue
        yield path


def test_no_compiler_module_statically_imports_the_quarantined_package():
    """`registry`, `minting`, `epistemic`, `discourse`, `transformation` and
    `morphology` are reachable only by importing them directly. Nothing on the
    ``hml check`` path may do so."""
    offenders: list[str] = []
    for path in _compiler_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(QUARANTINED_PACKAGE):
                        offenders.append(f"{path}:{node.lineno} import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                relative = "." * node.level + module
                if module.startswith(QUARANTINED_PACKAGE) or relative.endswith(".v1"):
                    offenders.append(f"{path}:{node.lineno} from {relative}")
    assert not offenders, (
        "the compiler now imports the quarantined V1 package:\n  "
        + "\n  ".join(offenders)
    )


def test_compiling_a_concept_never_loads_the_minting_or_registry_modules():
    """The `concept` block is a module-local declaration. It must make no admission
    decision, so a full compile must not pull in `v1.minting` or `v1.registry`."""
    probe = (
        "import sys\n"
        "from hamiltonian_lang import compile_source\n"
        "src = open('examples/concepts/location_scale_family.hml').read()\n"
        "r = compile_source(src, 'probe')\n"
        "assert r.ok(), r.diagnostics.render()\n"
        "r.canonical(); r.hash()\n"
        "print(sorted(m for m in sys.modules if m.startswith('hamiltonian_lang.v1')))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        cwd=str(MANIFEST.parents[2]),
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[]", (
        f"compiling a concept loaded quarantined modules: {proc.stdout.strip()}"
    )


# ---------------------------------------------------------------------------
# Barrier 3 — behavioural probes on the quarantined surface forms
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "form", sorted(QUARANTINED_SURFACE_FORMS), ids=lambda f: f.split()[0]
)
def test_a_quarantined_surface_form_does_not_compile(form):
    layer = QUARANTINED_SURFACE_FORMS[form]
    ok, codes = _codes(f"module M\n{form}\n")
    assert not ok, (
        f"{form!r} compiles. That surface belongs to {layer}, which the freeze manifest "
        f"classifies below SUPPORTED_ENFORCED and which must stay out of the gate."
    )
    assert codes, f"{form!r} was rejected with no diagnostic code"


def test_the_parser_advertises_only_the_frozen_statement_keywords():
    """HML-P205's correction text is what a repair loop reads. It enumerates the gate,
    so it must never come to advertise a quarantined construct."""
    # The probe must be a word that heads no statement at all. `goal` used to serve,
    # and stopped when V2 claimed it (D-025); `discharge` is still unreachable and
    # still belongs to the quarantined L5 discourse layer, so it exercises exactly the
    # path this test is about.
    result = compile_source("module M\ndischarge g1 by p1\n", "<freeze-probe>")
    text = result.diagnostics.render()
    assert "HML-P205" in text

    marker = "statements begin with one of:"
    line = next(ln for ln in text.splitlines() if marker in ln)
    advertised = set(line.split(marker, 1)[1].split())
    assert advertised <= FROZEN_KEYWORDS, (
        f"HML-P205 advertises keyword(s) outside the frozen set: "
        f"{sorted(advertised - FROZEN_KEYWORDS)}"
    )
    assert not advertised & set(QUARANTINED_SURFACE_FORMS_HEADS), (
        f"HML-P205 advertises a quarantined construct: "
        f"{sorted(advertised & set(QUARANTINED_SURFACE_FORMS_HEADS))}"
    )


# ---------------------------------------------------------------------------
# The manifest itself
# ---------------------------------------------------------------------------

_ROW = re.compile(r"^\|\s*(?P<feature>[^|]+?)\s*\|\s*`(?P<verdict>[A-Z_]+)`\s*\|")


def _manifest_rows() -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line)
        if match:
            rows[match.group("feature")] = match.group("verdict")
    return rows


def test_the_manifest_exists_and_classifies_every_required_feature():
    assert MANIFEST.exists(), f"{MANIFEST} is missing"
    rows = _manifest_rows()
    missing = [r for r in REQUIRED_MANIFEST_ROWS if r not in rows]
    assert not missing, f"the manifest omits required row(s): {missing}"


def test_every_manifest_verdict_is_from_the_closed_vocabulary():
    bad = {f: v for f, v in _manifest_rows().items() if v not in CLASSIFICATIONS}
    assert not bad, f"manifest rows carry unknown classifications: {bad}"


def test_the_manifest_and_the_shared_allowlist_agree():
    """The document and the code are two views of one decision. They must not drift."""
    rows = _manifest_rows()
    disagreements = {
        feature: (MANIFEST_CLASSIFICATION[feature], rows[feature])
        for feature in REQUIRED_MANIFEST_ROWS
        if feature in rows and rows[feature] != MANIFEST_CLASSIFICATION[feature]
    }
    assert not disagreements, (
        "V1_FREEZE_MANIFEST.md disagrees with frozen_subset.MANIFEST_CLASSIFICATION "
        f"(manifest, allowlist): {disagreements}"
    )


def test_every_supported_enforced_row_cites_an_executed_rejection():
    """The evidential bar: SUPPORTED_ENFORCED requires a *shown* rejection with a code.
    A row that claims it without naming a diagnostic code has not met the bar."""
    text = MANIFEST.read_text(encoding="utf-8")
    for feature, verdict in MANIFEST_CLASSIFICATION.items():
        if verdict not in GATE_ADMITS:
            continue
        section = _section_for(text, feature)
        assert re.search(r"HML-[A-Z]\d{3}", section), (
            f"{feature!r} is classified {verdict} but its manifest section names no "
            f"HML diagnostic code, so no rejection was evidenced"
        )
        assert "$ " in section or "```" in section, (
            f"{feature!r} is classified {verdict} but its manifest section shows no "
            f"executed command"
        )


def _section_for(text: str, feature: str) -> str:
    """The manifest body between the heading naming ``feature`` and the next heading."""
    lowered = text.lower()
    needle = feature.lower()
    starts = [
        m.start()
        for m in re.finditer(r"^#{2,4} .*$", text, flags=re.M)
        if needle in lowered[m.start() : m.end()]
    ]
    if not starts:
        return ""
    start = starts[0]
    following = re.search(r"^#{2,4} ", text[start + 1 :], flags=re.M)
    end = start + 1 + following.start() if following else len(text)
    return text[start:end]


@pytest.mark.parametrize("feature", quarantined_rows())
def test_a_quarantined_feature_is_not_in_the_gate_admitting_set(feature):
    assert MANIFEST_CLASSIFICATION[feature] not in GATE_ADMITS


# ---------------------------------------------------------------------------
# Known-failure pins — these assert a hole is STILL open
# ---------------------------------------------------------------------------


@pytest.mark.adversarial
def test_the_pvalue_conflation_is_rejected_when_the_kind_is_declared():
    """The former KNOWN_FAILED pin, inverted after D-022 closed the hole it recorded.

    `PValue` is now an HML scalar, incomparable with `Probability` in both directions,
    so a program that states the kinds is rejected. This is the evidence behind the
    manifest's `SUPPORTED_ENFORCED` row for `PValue`.
    """
    ok, codes = _codes(
        "module M\nconst pv : PValue := 0.05\ndef posterior_h0 : Probability := pv\n"
    )
    assert not ok, "a PValue standing where a Probability is required must be rejected"
    assert "HML-T403" in codes, codes

    ok, codes = _codes(
        "module M\nconst p : Probability = 0.5\ndef observed_pvalue : PValue := p\n"
    )
    assert not ok, "the refusal is symmetric; neither direction is a widening"
    assert "HML-T403" in codes, codes


@pytest.mark.adversarial
def test_pin_a_mis_declared_p_value_is_still_admitted():
    """The residual hole, pinned so it is not mistaken for closed.

    Declaring a p-value as `Probability` and then reading it as a posterior still
    type-checks, because both sides genuinely *are* `Probability` — the author chose the
    wrong type. No type system can catch that; it is a modelling error, not a type
    error, and the language's contribution is that the correct type now exists to be
    chosen.

    Stated explicitly so that no report may claim the prosecutor's fallacy is
    unrepresentable in HML. It is unrepresentable only in a program that declares its
    kinds.
    """
    source = "module M\nparam p_value : Probability\ndef posterior_h0 : Probability := p_value\n"
    ok, _ = _codes(source)
    assert ok, (
        "a mis-declared p-value is now rejected. If a later change makes the checker "
        "infer epistemic kind from a symbol's *name*, that is a spelling heuristic and "
        "must be argued for explicitly in DECISIONS.md before this pin is relaxed."
    )


@pytest.mark.adversarial
def test_pin_the_minting_duplicate_admission_exploits_still_reproduce():
    """`concept minting and admission` is KNOWN_FAILED because audits/V1_RED_TEAM.md §3
    still admits four names for one concept. Re-run here so the classification is
    evidenced by execution rather than by citation."""
    from hamiltonian_lang.v1 import minting as minting_mod
    from hamiltonian_lang.v1.registry import (
        Claim,
        ClaimStatus,
        Concept,
        ConceptRegistry,
        Parameter,
        Provenance,
    )

    structure = "the centred two-term form"

    def concept(canonical_id: str, **overrides) -> Concept:
        fields = dict(
            canonical_id=canonical_id,
            namespace="RT",
            version="1",
            type_signature="Real * Real -> Real",
            domain="Real * Real",
            codomain="Real",
            formal_definition="C(a, b) = (a - b) + (a - b)",
            provenance=Provenance(proposed_by="rt", proposed_at="2026-08-05"),
            parameters=(
                Parameter(name="a", type="Real", role="l"),
                Parameter(name="b", type="Real", role="r"),
            ),
            invariants=(
                Claim(
                    statement="C(a,a)=0",
                    status=ClaimStatus.PROVED,
                    discharged_by="lem",
                ),
            ),
            compresses=(structure,),
        )
        fields.update(overrides)
        return Concept(**fields)

    def candidate(c: Concept):
        return minting_mod.ConceptCandidate(
            concept=c,
            examples=(minting_mod.Example("inhabited", lambda: True),),
            compression=(
                minting_mod.CompressionEvidence(
                    structure,
                    ("does/not/exist_1.hml", "does/not/exist_2.hml"),
                    "(a - b) + (a - b)",
                    "C",
                ),
            ),
        )

    registry = ConceptRegistry()
    attacks = {
        "Alpha": concept("Alpha"),
        "AlphaClone": concept("AlphaClone", constraints=("true",)),
        "AlphaNoParams": concept(
            "AlphaNoParams",
            parameters=(),
            formal_definition="C(u, v) = (u - v) + (u - v)",
        ),
        "AlphaRewritten": concept(
            "AlphaRewritten", formal_definition="C(a, b) = 2 * (a - b)"
        ),
    }
    admitted = [
        name
        for name, c in attacks.items()
        if minting_mod.mint(candidate(c), registry).admitted
    ]
    assert admitted == list(attacks), (
        "one or more of the V1_RED_TEAM §3 duplicate-admission attacks is now blocked "
        f"(admitted={admitted}). Re-evidence `concept minting and admission` in "
        "docs/evaluation/V1_FREEZE_MANIFEST.md before relaxing this pin."
    )


@pytest.mark.adversarial
def test_pin_a_byte_identical_clone_is_still_caught():
    """The control for the pin above: the protocol is not inert, it is circumventable.
    Without this, a mint() that admitted everything would also satisfy the pin."""
    from hamiltonian_lang.v1 import minting as minting_mod
    from hamiltonian_lang.v1.registry import (
        Claim,
        ClaimStatus,
        Concept,
        ConceptRegistry,
        Parameter,
        Provenance,
    )

    def concept(canonical_id: str) -> Concept:
        return Concept(
            canonical_id=canonical_id,
            namespace="RT",
            version="1",
            type_signature="Real * Real -> Real",
            domain="Real * Real",
            codomain="Real",
            formal_definition="C(a, b) = (a - b) + (a - b)",
            provenance=Provenance(proposed_by="rt", proposed_at="2026-08-05"),
            parameters=(
                Parameter(name="a", type="Real", role="l"),
                Parameter(name="b", type="Real", role="r"),
            ),
            invariants=(
                Claim(statement="C(a,a)=0", status=ClaimStatus.PROVED, discharged_by="lem"),
            ),
            compresses=("the centred two-term form",),
        )

    def candidate(c: Concept):
        return minting_mod.ConceptCandidate(
            concept=c,
            examples=(minting_mod.Example("inhabited", lambda: True),),
            compression=(
                minting_mod.CompressionEvidence(
                    "the centred two-term form",
                    ("a.hml", "b.hml"),
                    "(a - b) + (a - b)",
                    "C",
                ),
            ),
        )

    registry = ConceptRegistry()
    minting_mod.mint(candidate(concept("Alpha")), registry)
    report = minting_mod.mint(candidate(concept("AlphaExactClone")), registry)
    assert not report.admitted
    assert report.duplicate_of == "Alpha"
