"""The evidence graph: what supports what, and what may never support anything.

Why this module exists as a graph rather than as a rule
-------------------------------------------------------
V2's first reasoning spine defended acyclicity with a single rule: *a derivation may cite
only claims declared earlier in the module.* That rule is sound for one module built in
one pass from source order, and it is not sound for anything else — an import, a batch
graph construction, or any assembly whose order is not textual order. It also could not
see the edge that closed the original exploit's loop, because a ``proved`` edge was never
in the premise graph at all.

So the ordering rule stays as a cheap first line, and this module adds the real one: an
explicit graph with an explicit cycle validator that walks **every** edge kind.

The distinction the graph is built around
-----------------------------------------
Not every claim is evidence. The three-way split is the whole point:

``ESTABLISHED``
    May support a conclusion outright. An in-scope ``assume`` (granted by definition) or
    a derivation the kernel VERIFIED.

``PROVISIONAL``
    May support a conclusion *only* by passing its unresolved obligations along. A
    ``CHECKED`` derivation is provisional: the rule applied correctly, but a side
    condition is open, so nothing built on it may be certified until that closes.
    **A provisional claim is not established, and this module never calls it that.**

``NOT_EVIDENCE``
    May never support anything. A ``goal`` states what we intend to show; a ``require``
    states what must hold; a ``prove`` states a claim. Letting any of them be a premise
    is how ``goal g1 : 1.0 = 2.0`` proved itself in the first V2 spine — both steps were
    valid applications of symmetry, and the defect was admitting an unestablished claim.

The invariants are enumerated as :data:`INVARIANTS` and each is checked by a named
method, so that "E4 holds" is a statement about code rather than about intent.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "EvidenceClass",
    "EdgeKind",
    "ClaimNode",
    "EvidenceEdge",
    "EvidenceGraph",
    "GraphViolation",
    "INVARIANTS",
]


class EvidenceClass(StrEnum):
    """What a claim may be used for. Ordered: NOT_EVIDENCE < PROVISIONAL < ESTABLISHED."""

    NOT_EVIDENCE = "NOT_EVIDENCE"
    PROVISIONAL = "PROVISIONAL"
    ESTABLISHED = "ESTABLISHED"


#: Total order used by the "weakest link" rule. A conclusion is never better evidence
#: than the worst thing it rests on.
_RANK = {
    EvidenceClass.NOT_EVIDENCE: 0,
    EvidenceClass.PROVISIONAL: 1,
    EvidenceClass.ESTABLISHED: 2,
}


class EdgeKind(StrEnum):
    """Every way one claim can depend on another.

    All of them are walked by the cycle validator. The original exploit closed its loop
    through a ``PROOF`` edge, which the premise-only view could not see — so "every kind"
    is load-bearing, not thoroughness for its own sake.
    """

    PREMISE = "premise"
    OBLIGATION = "obligation"
    PROOF = "proof"
    DISCHARGE = "discharge"


@dataclass(frozen=True)
class EvidenceEdge:
    """``source`` depends on ``target``."""

    source: str
    target: str
    kind: EdgeKind


@dataclass
class ClaimNode:
    label: str
    evidence_class: EvidenceClass
    #: Ids of unresolved mandatory obligations attached directly to this claim.
    own_open_obligations: tuple[str, ...] = ()
    #: Set by the checker. Present so E6 can assert nothing else writes it.
    status: str | None = None
    #: Environment/version this claim was established under (E8). ``None`` for claims
    #: originating in the module being checked.
    environment: str | None = None


@dataclass
class GraphViolation:
    invariant: str
    message: str
    labels: tuple[str, ...] = ()


#: The invariants this module enforces, quoted from the directive so the mapping from
#: requirement to check is inspectable rather than asserted.
INVARIANTS: dict[str, str] = {
    "E1": "the evidence graph is acyclic",
    "E2": "no GOAL/REQUIREMENT/CONJECTURE can be laundered into evidence",
    "E3": "every VERIFIED result depends only on valid scoped assumptions and verified evidence",
    "E4": "transitive OPEN obligations prevent VERIFIED status",
    "E7": "provenance is complete for every derivation",
    "E8": "imported evidence belongs to an explicit environment version",
    "E9": "an explicit cycle check runs; textual order is not the only defence",
}


class EvidenceGraph:
    """An explicit dependency graph over claims, with a real validator.

    Construction is deliberately independent of statement order: nodes and edges may be
    added in any sequence, and :meth:`validate` decides. That is exactly the property the
    textual-order rule lacks, and it is why this can be reused for imports later.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, ClaimNode] = {}
        self._edges: list[EvidenceEdge] = []

    # -- construction -----------------------------------------------------
    def add_claim(self, node: ClaimNode) -> None:
        self._nodes[node.label] = node

    def add_edge(self, source: str, target: str, kind: EdgeKind) -> None:
        self._edges.append(EvidenceEdge(source, target, kind))

    def node(self, label: str) -> ClaimNode | None:
        return self._nodes.get(label)

    def edges_from(self, label: str, *kinds: EdgeKind) -> list[EvidenceEdge]:
        wanted = set(kinds) or set(EdgeKind)
        return [e for e in self._edges if e.source == label and e.kind in wanted]

    # -- E1 / E9: cycles --------------------------------------------------
    def find_cycle(self) -> list[str] | None:
        """One cycle as a path, or None. Iterative DFS with colouring.

        Walks **every** edge kind. Iterative rather than recursive because a generated
        module can nest arbitrarily deep and a RecursionError here would be a crash in
        the soundness check itself.
        """
        WHITE, GREY, BLACK = 0, 1, 2
        colour = dict.fromkeys(self._nodes, WHITE)
        adjacency: dict[str, list[str]] = {label: [] for label in self._nodes}
        for e in self._edges:
            if e.source in adjacency and e.target in self._nodes:
                adjacency[e.source].append(e.target)

        parent: dict[str, str | None] = {}
        for root in self._nodes:
            if colour[root] != WHITE:
                continue
            stack: list[tuple[str, bool]] = [(root, False)]
            parent[root] = None
            while stack:
                node, processed = stack.pop()
                if processed:
                    colour[node] = BLACK
                    continue
                if colour[node] != WHITE:
                    continue
                colour[node] = GREY
                stack.append((node, True))
                for nxt in adjacency.get(node, []):
                    if colour.get(nxt) == GREY:
                        path = [nxt]
                        cur: str | None = node
                        while cur is not None and cur != nxt:
                            path.append(cur)
                            cur = parent.get(cur)
                        path.append(nxt)
                        return list(reversed(path))
                    if colour.get(nxt) == WHITE:
                        parent[nxt] = node
                        stack.append((nxt, False))
        return None

    # -- E4: transitive obligations ---------------------------------------
    def transitive_open_obligations(self, label: str) -> set[str]:
        """Every unresolved obligation ``label`` inherits, directly or through premises.

        Cycle-safe: a visited set bounds the walk, so this stays finite even if
        :meth:`find_cycle` has not run or a caller ignored its verdict. A soundness
        routine that can hang is a soundness routine that will be bypassed.
        """
        seen: set[str] = set()
        out: set[str] = set()
        stack = [label]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            node = self._nodes.get(cur)
            if node is None:
                continue
            out.update(node.own_open_obligations)
            for e in self.edges_from(cur, EdgeKind.PREMISE):
                stack.append(e.target)
        return out

    # -- weakest link -----------------------------------------------------
    def effective_class(self, label: str) -> EvidenceClass:
        """The weakest evidence class in ``label``'s premise closure.

        This is D-039's X2 rule applied to evidence rather than trust, and it is what
        stops a chain from being stronger than its worst link.
        """
        node = self._nodes.get(label)
        if node is None:
            return EvidenceClass.NOT_EVIDENCE
        worst = node.evidence_class
        seen: set[str] = set()
        stack = [label]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            here = self._nodes.get(cur)
            if here is None:
                continue
            if _RANK[here.evidence_class] < _RANK[worst]:
                worst = here.evidence_class
            for e in self.edges_from(cur, EdgeKind.PREMISE):
                stack.append(e.target)
        return worst

    # -- validation -------------------------------------------------------
    def validate(self, *, verified_labels: Iterable[str] = ()) -> list[GraphViolation]:
        """Check every invariant. Returns violations; empty means the graph is sound."""
        violations: list[GraphViolation] = []

        cycle = self.find_cycle()
        if cycle is not None:
            violations.append(
                GraphViolation(
                    "E1",
                    "the evidence graph contains a cycle: " + " -> ".join(cycle),
                    tuple(cycle),
                )
            )

        # E2 — nothing that is NOT_EVIDENCE may be the target of a premise edge.
        for e in self._edges:
            if e.kind is not EdgeKind.PREMISE:
                continue
            target = self._nodes.get(e.target)
            if target is not None and target.evidence_class is EvidenceClass.NOT_EVIDENCE:
                violations.append(
                    GraphViolation(
                        "E2",
                        f"{e.source!r} rests on {e.target!r}, which is not evidence",
                        (e.source, e.target),
                    )
                )

        for label in verified_labels:
            # E3 — a VERIFIED claim's whole premise closure must be ESTABLISHED.
            if self.effective_class(label) is not EvidenceClass.ESTABLISHED:
                violations.append(
                    GraphViolation(
                        "E3",
                        f"{label!r} is VERIFIED but its premise closure is "
                        f"{self.effective_class(label)}",
                        (label,),
                    )
                )
            # E4 — and it must inherit no open obligation.
            open_obs = self.transitive_open_obligations(label)
            if open_obs:
                violations.append(
                    GraphViolation(
                        "E4",
                        f"{label!r} is VERIFIED but inherits open obligation(s) "
                        f"{', '.join(sorted(open_obs))}",
                        (label,),
                    )
                )

        # E7 — a claim with premise edges must have a node for every one of them.
        for e in self._edges:
            if e.kind is EdgeKind.PREMISE and e.target not in self._nodes:
                violations.append(
                    GraphViolation(
                        "E7",
                        f"{e.source!r} cites {e.target!r}, which has no claim node: "
                        f"provenance is incomplete",
                        (e.source, e.target),
                    )
                )

        # E8 — evidence from another environment must say which.
        for label, node in self._nodes.items():
            if node.environment is not None and not node.environment.strip():
                violations.append(
                    GraphViolation(
                        "E8",
                        f"{label!r} carries an empty environment tag",
                        (label,),
                    )
                )

        return violations

    # -- introspection ----------------------------------------------------
    def labels(self) -> Sequence[str]:
        return tuple(self._nodes)

    def to_dict(self) -> dict:
        """Presentation only. Never enters a content hash (D-034 E1/E10)."""
        return {
            "claims": {
                label: {
                    "evidence_class": str(n.evidence_class),
                    "open_obligations": list(n.own_open_obligations),
                    "environment": n.environment,
                }
                for label, n in sorted(self._nodes.items())
            },
            "edges": [
                {"from": e.source, "to": e.target, "kind": str(e.kind)}
                for e in sorted(self._edges, key=lambda x: (x.source, x.target, x.kind))
            ],
        }
