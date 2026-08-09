"""Causal diagnosis of the B1 loss: five matched conditions over identical worlds.

B1 gave SE > HML on implication direction. This asks *why*, at scout scale, by varying
one mechanism at a time over the same canonical worlds:

| condition | what changes | hypothesis probed |
|---|---|---|
| `SE` | nothing — the existing control | baseline |
| `HML_BASIC` | nothing — the frozen B1 treatment | H1 intrinsic harm |
| `HML_EPI` | epistemic status made explicit | H3 missing epistemic state |
| `HML_OBF` | surface keywords replaced, structure identical | H2 familiarity tax |
| `HML_VERIFY` | deterministic verifier signals supplied | H4 needs a closed loop |

**Two leakage problems in the requested design, and what was done about them.**

1. `HML_EPI` as literally specified — expose `status(query)` and `status(neg_query)` —
   is a *total* answer leak: those two booleans determine TRUE / FALSE / UNDETERMINED
   exactly, so the task collapses from "decide entailment" to "apply a 3-way lookup".
   It would win trivially and tell us nothing about representation. So the epistemic
   block here reports status for **every declared atom except the query target**. That
   still operationalises H3 — epistemic scaffolding is made explicit where HML currently
   leaves it implicit — while the query itself remains to be determined. Omitting the
   target signals nothing, since the question already names it.

2. `HML_VERIFY` as specified *is* a near-total leak, and the brief accepts that
   (`query_proof_found` / `neg_query_proof_found` jointly determine the class). It is
   implemented as asked, but it can only be read as an **upper bound and a sanity check**:
   if it does not approach ceiling, the model cannot apply a two-bit lookup, which is
   damning for the whole setup; if it does, that says the deficit lies in *deriving*
   entailment rather than in reading HML or in the answer format. It is **not** evidence
   about representation quality and must not be reported as such.

`HML_OBF` deliberately does not compile — synthetic tokens are not HML. That is the point
of the probe, and the compile invariant is waived for that condition only.
"""

from __future__ import annotations

from evaluation.arena.ir import Atom, Not
from evaluation.arena.oracles import entailment
from evaluation.arena.renderers.english import EnglishRenderer
from evaluation.arena.renderers.hml import HmlRenderer

__all__ = ["CONDITIONS", "OBFUSCATION_MAP", "build_items", "render_state", "render_question"]

#: One frozen mapping for the whole experiment -- never per item, or the probe would
#: measure novelty rather than familiarity. Structural keywords only: variable names,
#: labels, operators and nesting are untouched, so the parse tree is preserved.
OBFUSCATION_MAP = {
    "assume": "zeta1",
    "goal": "zeta2",
    "var": "zeta3",
    "Proposition": "zeta4",
    "implies": "zeta5",
    "iff": "zeta6",
    "and": "zeta7",
    "or": "zeta8",
    "not": "zeta9",
}

CONDITIONS = ("SE", "HML_BASIC", "HML_EPI", "HML_OBF", "HML_VERIFY")

_SE = EnglishRenderer()
_HML = HmlRenderer()


def _atom_status(w, name: str) -> str:
    """ESTABLISHED / REFUTED / OPEN for one atom, derived from the oracle."""
    atoms = [d.name for d in w.decls]
    facts = [f.prop for f in w.facts]
    v = entailment(atoms, facts, name)
    return {"TRUE": "ESTABLISHED", "FALSE": "REFUTED", "UNDETERMINED": "OPEN"}[v]


def _epistemic_block(w) -> str:
    """Status of every declared atom EXCEPT the query target. Oracle-derived, never hand-set."""
    lines = ["STATUS OF DECLARED PROPOSITIONS", ""]
    for d in w.decls:
        if d.name == w.query.target:
            continue
        lines.append(f"  {d.name} : {_atom_status(w, d.name)}")
    return "\n".join(lines)


def _verifier_block(w) -> str:
    """Structured proof signals. Deliberately not the class label -- see the module note."""
    atoms = [d.name for d in w.decls]
    facts = [f.prop for f in w.facts]
    v = entailment(atoms, facts, w.query.target)
    q = "true" if v == "TRUE" else "false"
    nq = "true" if v == "FALSE" else "false"
    return (
        "VERIFIER REPORT (deterministic; produced by a checker, not by you)\n\n"
        f"  query_proof_found     = {q}\n"
        f"  neg_query_proof_found = {nq}"
    )


def _obfuscate(text: str) -> str:
    """Token-level substitution. Longest-first so no key is a prefix of another's match."""
    import re

    pattern = re.compile(r"\b(" + "|".join(sorted(OBFUSCATION_MAP, key=len, reverse=True)) + r")\b")
    return pattern.sub(lambda m: OBFUSCATION_MAP[m.group(0)], text)


def render_state(w, condition: str) -> str:
    if condition == "SE":
        return _SE.state(w)
    base = _HML.state(w)
    if condition == "HML_BASIC":
        return base
    if condition == "HML_EPI":
        return f"{base}\n\n{_epistemic_block(w)}"
    if condition == "HML_OBF":
        return _obfuscate(base)
    if condition == "HML_VERIFY":
        return f"{base}\n\n{_verifier_block(w)}"
    raise KeyError(condition)


def render_question(w, condition: str) -> str:
    if condition == "SE":
        return _SE.question(w)
    q = _HML.question(w)
    return _obfuscate(q) if condition == "HML_OBF" else q


def build_items(seed_base: int = 800_001, level: str = "L3", n: int = 6):
    """Fresh implication-direction worlds, one item per world, answer-balanced where possible.

    Drawn from `contrast.build_pairs` so the worlds are exactly the B1 construction, then
    one member of each pair is taken -- the diagnosis is per item, not paired, because we
    are comparing conditions rather than measuring sensitivity to a twin.
    """
    from evaluation.arena.bands import assert_band, band_range
    from evaluation.arena.endpoints.common import Item
    from evaluation.arena.endpoints.contrast import build_pairs

    window = list(band_range("CAUSAL_DIAGNOSIS"))[:4000]
    pairs = build_pairs("IMPLICATION_DIRECTION", level, window)
    picked, seen = [], {"TRUE": 0, "FALSE": 0, "UNDETERMINED": 0}
    for a, b in pairs:
        for it in (a, b):
            if len(picked) >= n:
                break
            # Prefer an even spread of the three classes.
            if seen[it.answer] <= min(seen.values()):
                picked.append(it)
                seen[it.answer] += 1
        if len(picked) >= n:
            break
    if len(picked) < n:
        raise RuntimeError(f"only {len(picked)} causal-diagnosis items available")
    assert_band([i.world.seed for i in picked], "CAUSAL_DIAGNOSIS")
    return [
        Item(
            item_id=f"CD_{i.world.world_id}",
            endpoint="CAUSAL_DIAGNOSIS",
            kind="CLOSED",
            family=i.family,
            level=i.level,
            seed=i.world.seed,
            world=i.world,
            question="",
            answer=i.answer,
            answer_space=i.answer_space,
            metrics={"source": "IMPLICATION_DIRECTION"},
        )
        for i in picked
    ]
