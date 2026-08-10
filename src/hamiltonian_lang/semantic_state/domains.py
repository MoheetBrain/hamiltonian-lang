"""The neutral domain lattice, as library data rather than a rule in the verifier (SF-R14).

Why this file exists at all
---------------------------
SF-R14 says domain applicability facts arrive *through libraries, not kernel keywords*. The
failure mode it names is a verifier that grows a hardcoded table of subject-matter
knowledge, because every later domain then needs a change to the checker rather than an
entry in a list. So the lattice is data: versioned, enumerable, and carrying its own
justification.

It closes a real divergence, and that is the honest reason
----------------------------------------------------------
This is not a change that makes a failing fixture pass. All thirty acceptance fixtures
passed before it existed, and they pass unchanged after. It exists because
``verify._check_type_domain`` compared declared domains with ``!=`` while the frozen
reference checker walks a parent chain (``reference_checker.py::_is_subtype``, over
``_DOMAIN_PARENTS``). Those agree on every fixture — each one declares the domain it
already has — and disagree on the first record that does not: a claim in ``Natural``
offered to an operation requiring ``Integer`` is accepted by the reference and was
**rejected** here. A false ``INVALID`` on sound reasoning.

No fixture exercises a proper subtype relation, so nothing in the acceptance set
demonstrates this behaviour either way. The entries below are justified by the reference
checker's *source*, which the implementation is required to match, and that is a weaker
warrant than a passing fixture. Recorded here so a later reader does not mistake one for
the other.

What is deliberately absent
---------------------------
**No warrant-rule registry.** SF-R10 also speaks of theorem warrants, and it is tempting to
add a table of the six rule names the corpus uses. The reference checker consults no such
table: it compares ``action.warrant.rule`` against the attached record's ``supports_rule``
and nothing else, so ``UNRELATED_RULE`` fails because the two strings differ, not because
the rule is unrecognised. A closed-world registry would reject a warrant the reference
accepts — a new divergence introduced in the name of closing one. Warrants are already data
on the action rather than core operations, which is what SF-R10 actually requires.

**This is not the mathematical library.** ``libraries/`` holds mathematics under
``MATHEMATICAL_LIBRARY_CONTRACT.md``. These are the corpus's domain *names* and their
containment order — adapter vocabulary, not theorems — and mixing them would put neutral
schema vocabulary inside the mathematical trust table. It is also not
``types.py::_SCALAR_PARENTS``: that is a different, multi-parent lattice over HML's own
scalar types, and merging the two would be exactly the kind of conflation ``CLAUDE.md``
prohibits. Two lattices, two purposes, no subtyping path between them.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["DomainEntry", "DOMAINS", "inhabits", "is_registered"]


@dataclass(frozen=True)
class DomainEntry:
    """One node of the lattice, with the provenance for its single containment edge."""

    name: str
    #: The domain immediately containing this one. ``None`` marks a root.
    parent: str | None
    version: int
    justification: str
    provenance: str

    @property
    def key(self) -> str:
        """Stable versioned key, matching the ``LibraryTheorem`` convention."""
        return f"{self.name}_v{self.version}"


DOMAINS: dict[str, DomainEntry] = {}


def _register(entry: DomainEntry) -> DomainEntry:
    """Package-private. Not exported and not reachable from HML source.

    Same trust boundary the mathematical library draws: a document being checked must never
    be able to widen the lattice it is checked against.
    """
    if entry.name in DOMAINS:
        raise RuntimeError(f"domain {entry.name!r} is already registered")
    if not entry.justification.strip():
        raise RuntimeError(f"domain {entry.name!r} carries no justification")
    DOMAINS[entry.name] = entry
    return entry


_CORPUS = (
    "the frozen Semantic Firewall reference checker, "
    "experiments/semantic_firewall/reference_checker.py::_DOMAIN_PARENTS"
)

for _name, _parent, _why in (
    ("Number", None, "the root of the neutral lattice; nothing contains it"),
    ("Real", "Number", "every real number is a number"),
    ("Integer", "Real", "every integer is a real number"),
    ("Natural", "Integer", "every natural number is an integer"),
    ("Rational", "Real", "every rational is a real number"),
    ("Probability", "Real", "a probability is a real number in [0, 1]"),
    (
        "NonNegativeReal",
        "Real",
        "a non-negative real is a real number",
    ),
    (
        "PositiveReal",
        "NonNegativeReal",
        "every positive real is non-negative; the converse fails at zero, which is why "
        "these are separate nodes rather than one",
    ),
):
    _register(
        DomainEntry(
            name=_name,
            parent=_parent,
            version=1,
            justification=_why,
            provenance=_CORPUS,
        )
    )


def is_registered(name: str) -> bool:
    return name in DOMAINS


def inhabits(actual: str, required: str) -> bool:
    """Whether a value declared ``actual`` may be offered where ``required`` is demanded.

    Reflexive first, then upward along ``parent``. A name absent from the lattice is
    therefore comparable only to itself — which is the reference checker's behaviour and
    the right one: ``Proposition`` and ``Boolean`` appear in the corpus but in no
    containment relation, and inventing one would let a Boolean satisfy an Integer
    contract. The traversal carries a ``seen`` guard so a malformed registration cannot
    hang the verifier; :func:`_assert_acyclic` makes that unreachable in practice.
    """
    if actual == required:
        return True
    seen: set[str] = set()
    current = actual
    while (entry := DOMAINS.get(current)) is not None and current not in seen:
        seen.add(current)
        if entry.parent is None:
            return False
        current = entry.parent
        if current == required:
            return True
    return False


def _assert_acyclic() -> None:
    """Every chain terminates at a root, checked at import rather than trusted."""
    for name in DOMAINS:
        seen: set[str] = set()
        current: str | None = name
        while current is not None:
            if current in seen:
                raise RuntimeError(f"the domain lattice cycles through {current!r}")
            seen.add(current)
            entry = DOMAINS.get(current)
            if entry is None:
                raise RuntimeError(f"domain {current!r} names an unregistered parent")
            current = entry.parent


_assert_acyclic()
