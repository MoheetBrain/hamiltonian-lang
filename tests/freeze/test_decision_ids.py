"""Referential integrity of the decision record.

`DECISIONS.md` is cited from production source, from the tests, from `spec/ir.schema.json`
and from most of `docs/`. A decision ID is therefore a reference like any other, and it
acquired the failure mode references acquire: on 2026-08-07 the V2 reasoning work appended
records numbered D-026, D-027 and D-028 while records with those numbers already existed.

That collision was found, documented, and **deliberately not repaired by renumbering**. The
rationale is recorded in the file itself and it holds up: roughly 65 sites reference one
number or the other, several are ambiguous without reading their surrounding context, and
ten of them sit in the frozen core (`ast/`, `lexer/`, `parser/`, `backends/`). A bulk
renumber would have had a worse expected outcome than the collision it fixed — it would
have meant editing frozen files to repair a documentation defect, with every edit a chance
to point a citation at the wrong record.

What was missing was enforcement. The file's own "Prevention" clause — *any future record
must take a number strictly greater than every number already present* — was a sentence,
and a sentence does not fail a build. This module makes it a gate: the three historical
collisions are pinned as accepted, and a **fourth** is a test failure.

None of these tests renumber anything or judge the original decision. They assert that the
situation stays exactly as documented.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DECISIONS = REPO / "DECISIONS.md"

#: The three IDs reused on 2026-08-07. Accepted, documented, and deliberately not
#: renumbered. Written out rather than computed, so that the set cannot quietly grow.
ACCEPTED_COLLISIONS = frozenset({"D-026", "D-027", "D-028"})

#: `## D-034 … D-039 — the architectural freeze` defines six records under one heading.
_HEADING = re.compile(r"^## (D-\d+)(?:\s*(?:…|\.\.\.)\s*(D-\d+))?", re.M)
_CITATION = re.compile(r"\bD-\d{3}\b")

_SEARCHED_SUFFIXES = {".md", ".py", ".json"}
_SKIPPED_PARTS = {".git", ".venv", "__pycache__", "node_modules"}


def _headings() -> list[str]:
    """Every ID a heading declares, in file order, ranges expanded."""
    out: list[str] = []
    for start, end in _HEADING.findall(DECISIONS.read_text()):
        if end:
            out.extend(f"D-{n:03d}" for n in range(int(start[2:]), int(end[2:]) + 1))
        else:
            out.append(start)
    return out


def _defined() -> set[str]:
    return set(_headings())


def _cited() -> dict[str, set[str]]:
    """Every decision ID referenced anywhere in the repository, with where."""
    found: dict[str, set[str]] = {}
    for path in REPO.rglob("*"):
        if path.suffix not in _SEARCHED_SUFFIXES or not path.is_file():
            continue
        if _SKIPPED_PARTS & set(path.parts):
            continue
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):  # pragma: no cover - binary or unreadable
            continue
        for ident in _CITATION.findall(text):
            found.setdefault(ident, set()).add(str(path.relative_to(REPO)))
    return found


def test_the_only_decision_id_collisions_are_the_three_accepted_ones():
    """A fourth collision is a new defect and must fail here rather than be discovered later.

    This is the whole point of the module. The three below are historical and documented;
    anything else means a record was appended without checking the numbers already in use,
    which is exactly how these three happened.
    """
    ids = _headings()
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert duplicates == set(ACCEPTED_COLLISIONS), (
        f"decision-ID collisions changed. Accepted: {sorted(ACCEPTED_COLLISIONS)}. "
        f"Found: {sorted(duplicates)}. A new record must take a number strictly greater "
        f"than every number already in DECISIONS.md."
    )


def test_every_cited_decision_id_resolves_to_a_record():
    """A citation naming a record that does not exist is a dangling reference.

    Checked across `src/`, `tests/`, `spec/` and `docs/` together, because a decision ID is
    cited from all four and an ID that resolves in one is not thereby resolvable.
    """
    defined = _defined()
    dangling = {k: sorted(v)[:5] for k, v in _cited().items() if k not in defined}
    assert not dangling, f"cited but not defined in DECISIONS.md: {dangling}"


def test_the_decision_numbers_are_contiguous_from_one():
    """No gaps. A gap is either a deleted record or a number skipped by accident.

    Either way the next author cannot tell which, and the safe next number stops being
    obvious — which is the condition the 2026-08-07 collision arose in.
    """
    defined = _defined()
    highest = max(int(i[2:]) for i in defined)
    missing = [f"D-{n:03d}" for n in range(1, highest + 1) if f"D-{n:03d}" not in defined]
    assert not missing, f"gaps in the decision record: {missing}"


def test_the_collision_block_still_describes_the_real_records():
    """The disambiguation rule is load-bearing, so it must not drift from the records.

    Every citation of a colliding ID is resolved by that block and nothing else. If the
    table stopped matching the headings, roughly sixty-five references would silently
    become ambiguous again with no other signal.
    """
    text = DECISIONS.read_text()
    block = text.split("## ⚠ DECISION-ID COLLISION", 1)
    assert len(block) == 2, "the collision warning block is missing from DECISIONS.md"

    for ident in sorted(ACCEPTED_COLLISIONS):
        assert f"| {ident} |" in block[1], f"{ident} is not listed in the collision table"

    headings = DECISIONS.read_text().splitlines()
    for ident in sorted(ACCEPTED_COLLISIONS):
        titles = [h for h in headings if h.startswith(f"## {ident} ")]
        assert len(titles) == 2, (
            f"{ident} is documented as colliding but has {len(titles)} headings"
        )


@pytest.mark.parametrize("ident", sorted(ACCEPTED_COLLISIONS))
def test_each_colliding_id_is_disambiguated_by_date_in_both_records(ident):
    """The stated rule is "the V2 records are dated 2026-08-07 and appear after D-033".

    Asserted positionally: the later record of each colliding pair must in fact appear
    after the D-033 heading, or the rule a reader is told to apply gives the wrong answer.
    """
    lines = DECISIONS.read_text().splitlines()
    anchor = next(i for i, line in enumerate(lines) if line.startswith("## D-033 "))
    positions = [i for i, line in enumerate(lines) if line.startswith(f"## {ident} ")]
    assert len(positions) == 2
    assert positions[0] < anchor < positions[1], (
        f"the disambiguation rule says the V2 {ident} appears after D-033; it does not"
    )
