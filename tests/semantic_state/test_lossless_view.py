"""SF-R15: the HML view of a transition renders every field and reads back identically.

The requirement is *"render every accepted neutral semantic field without hiding adapter
state or claiming unsupported pure-HML equivalence"*. Two halves, tested separately:

* **Render everything.** ``parse_transition(render_transition(t)) == t`` over all thirty
  acceptance fixtures. The model dataclasses are ``frozen=True``, so that is structural
  equality of the entire transition — not a content hash and not a normal form. This is a
  stricter bar than the AST round trip in ``tests/roundtrip/``, which compares canonical
  hashes and is explicitly allowed to lose spans.
* **Do not claim equivalence you do not have.** The view is a *rendering* of the canonical
  typed state, not a proof that HML-L1 can express a transition. Nothing here touches the
  lexer, the parser or ``backends/``, and ``test_the_view_did_not_smuggle_in_new_syntax``
  asserts that mechanically rather than in prose.

The chained property is the one that would catch a renderer built to satisfy its own test:
render the view, read it back, export it through the *neutral* adapter, and compare to the
original corpus JSON. A field this module invented, or dropped, does not survive that.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hamiltonian_lang.semantic_state import (
    Action,
    Branch,
    BranchStatus,
    Candidate,
    CandidateStatus,
    Claim,
    ClaimStatus,
    EvidenceRecord,
    Goal,
    Obligation,
    ObligationState,
    SemanticState,
    Transition,
    ViewError,
    export_transition,
    import_transition,
    parse_transition,
    render_transition,
)

CORPUS = Path("/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus")
FIXTURES = CORPUS / "experiments" / "semantic_firewall" / "acceptance" / "fixtures.json"

_PROVENANCE = {"pair_id", "split", "semantic_focus"}
_STRUCTURAL = {
    "action", "case_id", "evidence", "schema_version", "source",
    "state_after", "state_before",
}


def _fixtures():
    if not FIXTURES.exists():
        pytest.skip(f"research corpus not present at {CORPUS}")
    return json.loads(FIXTURES.read_text())["fixtures"]


_PARAMS = _fixtures() if FIXTURES.exists() else []


@pytest.mark.parametrize("fixture", _PARAMS, ids=lambda f: f["fixture_id"])
def test_the_view_round_trips_every_fixture_into_the_identical_state(fixture):
    transition = import_transition(fixture["case"])
    assert parse_transition(render_transition(transition)) == transition


@pytest.mark.parametrize("fixture", _PARAMS, ids=lambda f: f["fixture_id"])
def test_a_fixture_survives_the_whole_chain_back_to_its_own_json(fixture):
    """corpus JSON -> state -> view -> state -> corpus JSON.

    The strongest available check, because the endpoints are the corpus's bytes rather than
    anything this repository chose. A renderer that quietly normalised a field would pass
    the view-only round trip and fail here.
    """
    case = fixture["case"]
    extras = {k: v for k, v in case.items() if k not in _STRUCTURAL}
    assert set(extras) <= _PROVENANCE
    back = export_transition(parse_transition(render_transition(import_transition(case))),
                             extras=extras)
    assert json.dumps(back, sort_keys=True) == json.dumps(case, sort_keys=True)


@pytest.mark.parametrize("fixture", _PARAMS, ids=lambda f: f["fixture_id"])
def test_rendering_is_idempotent(fixture):
    once = render_transition(import_transition(fixture["case"]))
    assert render_transition(parse_transition(once)) == once


def test_the_previously_inexpressible_families_render():
    """FX-CAN-* and FX-BRN-* are SF-R15's own acceptance fixtures, with FX-OBL-*."""
    fx = {f["fixture_id"]: f for f in _fixtures()}
    for fid in ("FX-CAN-LEGAL", "FX-BRN-LEGAL", "FX-OBL-LEGAL"):
        transition = import_transition(fx[fid]["case"])
        text = render_transition(transition)
        assert parse_transition(text) == transition, fid


def test_the_view_did_not_smuggle_in_new_syntax():
    """The frozen core must be untouched, asserted against git rather than asserted in prose.

    A renderer is exactly the change most likely to reach for a new keyword, so the
    constraint is checked where it can fail rather than restated where it cannot.
    """
    root = Path(__file__).resolve().parents[2]
    frozen = ["src/hamiltonian_lang/ast", "src/hamiltonian_lang/lexer",
              "src/hamiltonian_lang/parser", "src/hamiltonian_lang/backends"]
    diff = subprocess.run(
        ["git", "diff", "HEAD", "--", *frozen],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if diff.returncode != 0:  # pragma: no cover - not a git checkout
        pytest.skip("not a git working tree")
    assert diff.stdout == "", f"the view modified the frozen core:\n{diff.stdout[:2000]}"

    source = (Path(__file__).resolve().parents[2]
              / "src/hamiltonian_lang/semantic_state/view.py").read_text()
    for forbidden in ("from ..lexer", "from ..parser", "from ..backends",
                      "from ..ast", "import hamiltonian_lang.lexer",
                      "import hamiltonian_lang.parser"):
        assert forbidden not in source, f"view.py reaches into the frozen core: {forbidden}"


# ---------------------------------------------------------------------------
# SF-R05 — obligations, specifically, through the rendering
# ---------------------------------------------------------------------------


def test_every_obligation_field_survives_the_rendering():
    """SF-R05 names them: identity, origin, dependencies, persistence, named discharge.

    ``FX-OBL-*`` exercises only some of these, so the full set is asserted on a record
    built to carry all of them at once — including ``mandatory=False``, which no fixture
    contains and which a renderer that emitted the field only when true would drop.
    """
    obligation = Obligation(
        id="ob1",
        proposition="the denominator is non-zero",
        status=ObligationState.DISCHARGED,
        mandatory=False,
        origin="DIVISION at step 4",
        dependencies=("p0", "p1"),
        discharge_evidence_id="e_disc",
    )
    state = SemanticState(obligations={"ob1": obligation})
    transition = Transition(
        case_id="OBL",
        action=Action(
            id="a1",
            operation="DISCHARGE",
            obligations_discharged=({"id": "ob1", "evidence_id": "e_disc"},),
        ),
        state_before=state,
        state_after=state,
    )
    back = parse_transition(render_transition(transition))
    assert back == transition
    assert back.state_before.obligations["ob1"].mandatory is False
    assert back.state_before.obligations["ob1"].discharge_evidence_id == "e_disc"
    assert back.action.obligations_discharged == ({"id": "ob1", "evidence_id": "e_disc"},)


@pytest.mark.parametrize("status", list(ObligationState))
def test_every_obligation_status_round_trips(status):
    obligation = Obligation(id="ob1", proposition="p", status=status)
    state = SemanticState(obligations={"ob1": obligation})
    t = Transition(case_id="C", action=Action(id="a", operation="X"),
                   state_before=state, state_after=state)
    assert parse_transition(render_transition(t)) == t


# ---------------------------------------------------------------------------
# What the corpus never produces
# ---------------------------------------------------------------------------


def _wrap(state: SemanticState) -> Transition:
    return Transition(
        case_id="SYNTHETIC",
        action=Action(id="a1", operation="ASSERT"),
        state_before=state,
        state_after=SemanticState(),
    )


@pytest.mark.parametrize("status", list(CandidateStatus))
def test_every_candidate_status_round_trips_including_the_two_no_fixture_reaches(status):
    state = SemanticState(
        candidates={"k1": Candidate(id="k1", proposition="x = 2", status=status,
                                    constraint_ids=("c1", "c2"))}
    )
    t = _wrap(state)
    assert parse_transition(render_transition(t)) == t


@pytest.mark.parametrize("status", list(BranchStatus))
def test_every_branch_status_round_trips(status):
    state = SemanticState(
        branches={"b1": Branch(id="b1", predicate="n even", status=status,
                               conclusion="n = 2k", partition_id="p1")}
    )
    t = _wrap(state)
    assert parse_transition(render_transition(t)) == t


@pytest.mark.parametrize("status", list(ClaimStatus))
def test_every_claim_status_round_trips(status):
    state = SemanticState(claims={"c1": Claim(id="c1", proposition="p", status=status)})
    t = _wrap(state)
    assert parse_transition(render_transition(t)) == t


def test_a_record_whose_key_differs_from_its_id_survives():
    """The neutral schema permits it: ``import_state`` reads ``raw.get("id", cid)``.

    Collapsing the two would round-trip all thirty fixtures and lose a record the first
    time the corpus produced one, which is the kind of defect that surfaces as data loss
    rather than as a failure.
    """
    state = SemanticState(
        claims={"key": Claim(id="different", proposition="p")},
        candidates={"kkey": Candidate(id="kdiff", proposition="x")},
        branches={"bkey": Branch(id="bdiff", predicate="q")},
        goals={"gkey": Goal(id="gdiff", proposition="r")},
        obligations={"okey": Obligation(id="odiff", proposition="s")},
    )
    t = Transition(
        case_id="C", action=Action(id="a", operation="X"),
        state_before=state, state_after=SemanticState(),
        evidence={"ekey": EvidenceRecord(id="ediff", kind="K")},
    )
    back = parse_transition(render_transition(t))
    assert back == t
    assert back.state_before.claims["key"].id == "different"
    assert back.evidence["ekey"].id == "ediff"


@pytest.mark.parametrize(
    "awkward",
    [
        "a claim with spaces",
        'quotes "inside" it',
        "comma, separated",
        "unicode ∀x∈ℝ",
        "",
        "# looks like a comment",
        "line\nbreak",
    ],
)
def test_awkward_text_survives_verbatim(awkward):
    """Propositions are corpus strings, not HML expressions, and are never re-parsed.

    A newline inside a proposition is the interesting one: the view is line-oriented, so a
    renderer that wrote it raw would produce a document that no longer reads back.
    """
    state = SemanticState(claims={"c1": Claim(id="c1", proposition=awkward, domain=awkward)})
    t = _wrap(state)
    back = parse_transition(render_transition(t))
    assert back == t
    assert back.state_before.claims["c1"].proposition == awkward


def test_an_identifier_that_is_not_a_bare_word_survives():
    state = SemanticState(claims={"a b, c": Claim(id="a b, c", proposition="p",
                                                  dependencies=("x y", "z"))})
    t = _wrap(state)
    assert parse_transition(render_transition(t)) == t


def test_empty_and_absent_are_not_confused():
    """``domain=None`` and ``domain=""`` are different records and must stay different."""
    absent = _wrap(SemanticState(claims={"c": Claim(id="c", proposition="p", domain=None)}))
    empty = _wrap(SemanticState(claims={"c": Claim(id="c", proposition="p", domain="")}))
    assert render_transition(absent) != render_transition(empty)
    assert parse_transition(render_transition(absent)) == absent
    assert parse_transition(render_transition(empty)) == empty


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_a_value_the_view_cannot_carry_back_is_refused_not_approximated():
    """``json.dumps`` would coerce a non-string key and a set, and both look fine.

    SF-R15 is explicit that unsupported fields are *rejected* rather than commented away,
    so the renderer raises instead of emitting something that will not read back.
    """
    t = Transition(
        case_id="C",
        action=Action(id="a", operation="X", typing={1: "Integer"}),  # type: ignore[dict-item]
        state_before=SemanticState(), state_after=SemanticState(),
    )
    with pytest.raises(ViewError, match="not a string"):
        render_transition(t)

    t2 = Transition(
        case_id="C",
        action=Action(id="a", operation="X", warrant={"rule": {"a", "b"}}),
        state_before=SemanticState(), state_after=SemanticState(),
    )
    with pytest.raises(ViewError, match="not representable"):
        render_transition(t2)


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("claim c1\n", "must open with a 'transition' block"),
        ("transition C\n  schema \"semantic-firewall-case-0.1.0\"\n", "must carry an action"),
        ("transition C\naction a\n  operation \"X\"\nstate before\n", "state after"),
        ("transition C\nstate before\n  claim c\n    nonsense \"x\"\naction a\nstate after\n",
         "no field 'nonsense'"),
        ("transition C\nstate before\n  claim c\n    proposition \"p\"\n    proposition \"q\"\n"
         "action a\nstate after\n", "repeats field"),
        ("transition C\nstate before\n  claim c\n    status NOPE\naction a\nstate after\n",
         "is not one of"),
        ("transition C\nstate sideways\naction a\nstate after\n", "'before' or 'after'"),
        ("transition C\nstate before\n  lemma x\naction a\nstate after\n",
         "not 'lemma'"),
        ("transition C\nstate before\naction a\naction b\nstate after\n",
         "exactly one action"),
        ("transition C\nstate before\naction a\n  typing [1]\nstate after\n",
         "must be a mapping"),
        ("transition C\n   schema \"x\"\n", "not a multiple of"),
        ("transition C\n\tschema \"x\"\n", "spaces, not tabs"),
        ("transition C\nstate before\naction a\nevidence e\nevidence e\nstate after\n",
         "appears twice"),
        ("transition C\nstate before\nstate before\naction a\nstate after\n",
         "appears twice"),
    ],
)
def test_a_malformed_view_is_refused_with_a_specific_reason(text, match):
    with pytest.raises(ViewError, match=match):
        parse_transition(text)


def test_comments_and_blank_lines_are_ignored():
    t = _wrap(SemanticState(claims={"c": Claim(id="c", proposition="p")}))
    text = render_transition(t)
    decorated = "# a note\n\n" + text.replace("state before", "# another\nstate before")
    assert parse_transition(decorated) == t
