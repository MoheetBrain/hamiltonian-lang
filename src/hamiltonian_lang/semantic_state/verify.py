"""The transition verifier: ten invariants over one canonical state transition.

What this is
------------
Given ``state_before --action--> state_after`` and the evidence offered, decide whether the
transition is ``VALID``, ``INVALID`` (with a named error class), or ``UNRESOLVED``.

Three-valued, and the third value is the point
----------------------------------------------
Each invariant family ships a LEGAL, an ILLEGAL and an **UNKNOWN** case. The UNKNOWN case
is not a weaker ILLEGAL: it is a transition whose legality cannot be determined because
something it depends on is itself unknown — an unknown claim status, an unknown
precondition, unknown evidence, an unknown domain. Reporting it as a detected violation
would be as wrong as accepting it, so it gets its own verdict and is excluded from both the
accept count and the detect count.

That is why :func:`verify` collects UNKNOWNs **before** violations and returns early. An
invariant cannot meaningfully be checked against a field whose value is "we do not know",
and a checker that guessed in that situation would produce a confident answer with nothing
behind it.

Ownership
---------
Nothing here reads ``EvidenceRecord.trusted`` as authority. That flag records who produced
a record, not what it licenses. Acceptance always requires the structural facts: the
referenced evidence exists, it supports the rule actually being applied, its premises are
among the action's declared dependencies, and its status is VALID. The corrupted fixtures
attack precisely that reference — they point an action at evidence that is not there — and
a checker that believed the flag would accept every one of them.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from .domains import inhabits
from .model import (
    Action,
    BranchStatus,
    EvidenceRecord,
    SemanticState,
    Transition,
    Verdict,
)
from .trust import Attestation, TrustMode

__all__ = [
    "Finding", "TransitionResult", "INVARIANTS",
    "verify", "verify_replay", "verify_runtime", "replay_payload",
]

#: The literal a neutral record uses to say "not determined". Present in claim status,
#: precondition status, evidence status and declared domain.
UNKNOWN = "UNKNOWN"

#: The ten invariant families, with the error class each reports. Names match the neutral
#: fixtures' ``expected_error_class`` exactly, because a verifier that reported its own
#: vocabulary could not be compared against the reference checker at all.
INVARIANTS: dict[str, str] = {
    "DEPENDENCY": "DEPENDENCY_VIOLATION",
    "SCOPE": "SCOPE_LEAK",
    "PRECONDITIONS": "PRECONDITION_VIOLATION",
    "OBLIGATIONS": "OBLIGATION_DROP",
    "CANDIDATES": "CANDIDATE_PROMOTION",
    "BRANCH_JOIN": "INVALID_BRANCH_JOIN",
    "WARRANT": "WARRANT_MISMATCH",
    "EPISTEMIC_STATUS": "EPISTEMIC_PROMOTION",
    "GOAL_DISCHARGE": "FALSE_GOAL_DISCHARGE",
    "TYPE_DOMAIN": "TYPE_OR_DOMAIN_MISMATCH",
    #: The reference reports its frame violations under DEPENDENCY, so the error class
    #: matches even though the invariant is named separately here.
    "FRAME": "DEPENDENCY_VIOLATION",
}


@dataclass(frozen=True)
class Finding:
    invariant: str
    error_class: str
    detail: str


@dataclass
class TransitionResult:
    verdict: Verdict
    findings: list[Finding] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)

    @property
    def error_class(self) -> str | None:
        return self.findings[0].error_class if self.findings else None

    def to_dict(self) -> dict:
        return {
            "verdict": str(self.verdict),
            "error_class": self.error_class,
            "findings": [
                {"invariant": f.invariant, "error_class": f.error_class, "detail": f.detail}
                for f in self.findings
            ],
            "unknowns": list(self.unknowns),
        }


def _evidence(transition: Transition, eid: str | None) -> EvidenceRecord | None:
    return transition.evidence.get(eid) if eid else None


def _supports(record: EvidenceRecord, rule: str | None) -> bool:
    """Evidence must support the rule actually being applied, not merely exist."""
    return rule is None or record.supports_rule == rule


# ---------------------------------------------------------------------------
# UNKNOWN collection -- runs first, and short-circuits
# ---------------------------------------------------------------------------


def _relevant(action: Action) -> tuple[set[str], set[str], set[str]]:
    """The claims, candidates and branches this action actually depends on.

    Relevance is what makes UNKNOWN a *fail-closed* rule rather than a denial of service.
    An unknown value the action never consults tells us nothing about whether the action is
    sound, and treating it as grounds for refusal means one junk record disables the
    verifier — measured: appending a single unrelated ``status: UNKNOWN`` claim turned all
    ten ILLEGAL acceptance fixtures from INVALID into UNRESOLVED, which is a total detection
    bypass, because UNRESOLVED is counted as neither accepted nor detected. Evidence
    unknowns were already scoped this way; the rest were not (D-049).
    """
    claims = set(action.dependencies)
    if action.output_id:
        claims.add(action.output_id)
    claims |= set(action.typing.get("input_domains") or {})
    candidates = {action.candidate_effect.get("candidate_id")} - {None}
    branches = set(action.branch_effect.get("branch_ids") or ())
    return claims, {c for c in candidates if c}, branches


def _collect_unknowns(transition: Transition) -> list[str]:
    action, before, after = transition.action, transition.state_before, transition.state_after
    out: list[str] = []
    want_claims, want_candidates, want_branches = _relevant(action)

    for name, state in (("state_before", before), ("state_after", after)):
        # Keyed by the dictionary key, not ``record.id``: the neutral schema permits the
        # two to differ, and an action cites the key.
        for key, claim in state.claims.items():
            if key not in want_claims:
                continue
            if str(claim.status) == UNKNOWN:
                out.append(f"{name}.claims.{key}.status is UNKNOWN")
            if claim.domain == UNKNOWN:
                out.append(f"{name}.claims.{key}.domain is UNKNOWN")
            if claim.scope == UNKNOWN:
                out.append(f"{name}.claims.{key}.scope is UNKNOWN")
        for key, candidate in state.candidates.items():
            if key in want_candidates and str(candidate.status) == UNKNOWN:
                out.append(f"{name}.candidates.{key}.status is UNKNOWN")
        for key, branch in state.branches.items():
            if key in want_branches and str(branch.status) == UNKNOWN:
                out.append(f"{name}.branches.{key}.status is UNKNOWN")

    for i, pre in enumerate(action.preconditions):
        if isinstance(pre, dict) and pre.get("status") == UNKNOWN:
            out.append(f"action.preconditions[{i}].status is UNKNOWN")

    # Only evidence the action actually relies on. An unrelated UNKNOWN record in the
    # bundle is not a reason to refuse a transition that never cites it.
    for eid in _cited_evidence_ids(action):
        record = transition.evidence.get(eid)
        if record is not None and record.status == UNKNOWN:
            out.append(f"evidence.{eid}.status is UNKNOWN")

    # An *absent* domain is unavailable evidence, not a violation (SF-R13, D-048). A claim
    # the action types but the state does not annotate says nothing about whether the
    # domains agree, and reporting a mismatch there would be a confident answer with
    # nothing behind it. Only annotations the action actually depends on are consulted --
    # an unannotated claim nobody typed is not this check's business.
    for cid in (action.typing.get("input_domains") or {}):
        typed = before.claims.get(cid)
        if typed is not None and typed.domain is None:
            out.append(f"state_before.claims.{cid}.domain is not declared")
    if action.typing.get("output_domain") and action.output_id:
        produced = after.claims.get(action.output_id)
        if produced is not None and produced.domain is None:
            out.append(f"state_after.claims.{action.output_id}.domain is not declared")

    return out


def _cited_evidence_ids(action: Action) -> list[str]:
    ids = []
    for source in (
        action.warrant.get("evidence_id"),
        action.epistemic_effect.get("evidence_id"),
        action.candidate_effect.get("evidence_id"),
        action.branch_effect.get("coverage_evidence_id"),
        action.scope_effect.get("discharge_evidence_id"),
    ):
        if source:
            ids.append(source)
    # Obligation discharges cite their own evidence, one per discharged obligation. Missing
    # these was a real hole: a discharge resting on UNKNOWN evidence would have been read
    # as an ordinary valid transition rather than an unresolved one.
    for entry in action.obligations_discharged:
        if isinstance(entry, dict) and entry.get("evidence_id"):
            ids.append(entry["evidence_id"])
    for entry in action.preconditions:
        if isinstance(entry, dict) and entry.get("evidence_id"):
            ids.append(entry["evidence_id"])
    return ids


# ---------------------------------------------------------------------------
# The ten invariants
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Evidence authority (D-050)
# ---------------------------------------------------------------------------

#: The mode and attestations in force for the transition currently being checked. Held in a
#: ContextVar rather than threaded through twelve signatures: every check reaches evidence
#: through :func:`_accepted`, so one seam is enough, and a ContextVar cannot leak across
#: concurrent verifications the way a module global would.
_TRUST: ContextVar[tuple[TrustMode, dict[str, Attestation]]] = ContextVar(
    "_TRUST", default=(TrustMode.OFFLINE_REPLAY, {})
)


def _accepted(
    t: Transition,
    record: EvidenceRecord | None,
    *,
    cited_as: str | None = None,
    claim: str | None = None,
    premises: tuple[str, ...] = (),
    rule: str | None = None,
) -> tuple[bool, str]:
    """Whether this evidence may be relied on. The single authority seam.

    In ``OFFLINE_REPLAY`` the recorded ``status`` is observed reference data from a frozen
    external corpus and is read as such. In ``RUNTIME`` it is **ignored entirely** — the
    author of the record may be the party that benefits from the verdict, so acceptance
    requires an :class:`~.trust.Attestation` carrying a ``CheckedEvidence`` that only
    ``reasoning.certificates.check`` can mint (D-050).
    """
    if record is None:
        return False, "no such evidence record"
    mode, attestations = _TRUST.get()
    if mode is TrustMode.OFFLINE_REPLAY:
        return (record.status == "VALID"), f"evidence {record.id!r} is {record.status}"

    # Keyed by the id the ACTION cites, never by ``record.id``. The neutral schema lets a
    # record's own ``id`` differ from the key it is filed under, and ``record.id`` is
    # payload-controlled, so filing an attestation under it lets a producer route a genuine
    # certificate for ``e_genuine`` onto a record it cites as ``e_forged`` (D-052).
    att = attestations.get(cited_as or record.id)
    if att is None:
        return False, (
            f"evidence {record.id!r} carries no checker attestation; a self-asserted "
            f"status is not authority at runtime"
        )
    ok, why = att.binds(claim=claim, premises=premises, rule=rule)
    return (ok, why)


def _check_dependency(t: Transition) -> list[Finding]:
    out = []
    for dep in t.action.dependencies:
        if dep not in t.state_before.claims:
            out.append(
                Finding(
                    "DEPENDENCY",
                    INVARIANTS["DEPENDENCY"],
                    f"action cites {dep!r}, which is not present in the prior state",
                )
            )
    # The produced claim must rest on what the action said it rests on. Letting these
    # drift is how a conclusion acquires ancestry it never had.
    out_id = t.action.output_id
    produced = t.state_after.claims.get(out_id) if out_id else None
    if produced is not None and set(produced.dependencies) != set(t.action.dependencies):
        out.append(
            Finding(
                "DEPENDENCY",
                INVARIANTS["DEPENDENCY"],
                f"{out_id!r} records dependencies {sorted(produced.dependencies)} "
                f"but the action declared {sorted(t.action.dependencies)}",
            )
        )
    return out


def _check_scope(t: Transition) -> list[Finding]:
    """A conclusion may not be wider than the narrowest premise it rests on.

    This is the invariant, and it is not "the output scope is active". ``global`` is
    always active, so that weaker reading accepts the corrupted fixture, which promotes a
    ``branch:b1`` conclusion straight to ``global``. The real rule is containment: a fact
    derived inside a frame stays inside it, and leaving requires an explicit discharge
    whose evidence is checked like any other.

    Depth is read off ``active_scopes``, which the neutral record orders outermost-first,
    so a later entry is strictly inside an earlier one.
    """
    out = []
    order = list(t.state_before.active_scopes)

    def depth(scope: str) -> int:
        return order.index(scope) if scope in order else -1

    for dep in t.action.dependencies:
        claim = t.state_before.claims.get(dep)
        if claim is not None and claim.scope not in order:
            out.append(
                Finding(
                    "SCOPE",
                    INVARIANTS["SCOPE"],
                    f"{dep!r} lives in inactive scope {claim.scope!r} and cannot be cited",
                )
            )

    out_id = t.action.output_id
    produced = t.state_after.claims.get(out_id) if out_id else None
    if produced is None:
        return out
    if produced.scope not in order:
        out.append(
            Finding(
                "SCOPE",
                INVARIANTS["SCOPE"],
                f"{out_id!r} was written into scope {produced.scope!r}, which is not "
                f"active ({', '.join(order)})",
            )
        )
        return out

    innermost = max(
        (depth(t.state_before.claims[d].scope) for d in t.action.dependencies
         if d in t.state_before.claims),
        default=-1,
    )
    if innermost > depth(produced.scope):
        discharged = _discharge_licenses_escape(t)
        if not discharged:
            narrow = order[innermost]
            out.append(
                Finding(
                    "SCOPE",
                    INVARIANTS["SCOPE"],
                    f"{out_id!r} rests on a premise local to {narrow!r} but was written "
                    f"into the wider scope {produced.scope!r} with no discharge; a "
                    f"branch-local fact does not become global by being restated there",
                )
            )
    return out


def _discharge_licenses_escape(t: Transition) -> bool:
    """Whether an explicit, valid discharge permits the conclusion to leave its frame."""
    effect = t.action.scope_effect
    if effect.get("kind") != "DISCHARGE":
        return False
    record = _evidence(t, effect.get("discharge_evidence_id"))
    out_id = t.action.output_id
    produced = t.state_after.claims.get(out_id) if out_id else None
    ok, _ = _accepted(
        t, record,
        cited_as=effect.get("discharge_evidence_id"),
        claim=produced.proposition if produced is not None else None,
        premises=t.action.dependencies,
    )
    return ok


def _check_preconditions(t: Transition) -> list[Finding]:
    """SF-R04. SATISFIED executes; DEFERRED becomes explicit debt; UNSATISFIED refuses.

    UNKNOWN never reaches here — it was collected earlier and made the whole transition
    UNRESOLVED, which is the fail-closed requirement: an unknown precondition must not
    execute as valid.
    """
    out = []
    for i, pre in enumerate(t.action.preconditions):
        if not isinstance(pre, dict):
            continue
        status = pre.get("status")
        if status in ("SATISFIED", "DEFERRED", "DEFERRED_AS_OBLIGATION"):
            continue
        out.append(
            Finding(
                "PRECONDITIONS",
                INVARIANTS["PRECONDITIONS"],
                f"precondition[{i}] {pre.get('description', pre.get('id', ''))!r} "
                f"is {status!r}",
            )
        )
    return out


def _check_obligations(t: Transition) -> list[Finding]:
    """Created obligations must persist; discharged ones must name their evidence."""
    out = []
    for spec in t.action.obligations_created:
        oid = spec.get("id") if isinstance(spec, dict) else spec
        if oid and oid not in t.state_after.obligations:
            out.append(
                Finding(
                    "OBLIGATIONS",
                    INVARIANTS["OBLIGATIONS"],
                    f"obligation {oid!r} was created by the action but is absent from the "
                    f"resulting state",
                )
            )
    for entry in t.action.obligations_discharged:
        # The neutral schema records a discharge as ``{id, evidence_id}``, not a bare id.
        oid = entry.get("id") if isinstance(entry, dict) else entry
        settled = t.state_after.obligations.get(oid) if oid else None
        if settled is None:
            continue
        if str(settled.status) != "DISCHARGED":
            out.append(
                Finding(
                    "OBLIGATIONS",
                    INVARIANTS["OBLIGATIONS"],
                    f"obligation {oid!r} is claimed discharged but remains {settled.status}",
                )
            )
    return out


def _check_candidates(t: Transition) -> list[Finding]:
    """SF-R07. Promotion is verifier-owned and checks EVERY original constraint."""
    effect = t.action.candidate_effect
    kind = effect.get("kind", "NONE")
    if kind in (None, "NONE"):
        return []
    cid = effect.get("candidate_id")
    candidate = t.state_before.candidates.get(cid) if cid else None
    after = t.state_after.candidates.get(cid) if cid else None
    # Identity must survive the transition. A candidate that vanishes, or appears only
    # afterwards, is not the object the evidence was about.
    if candidate is None or after is None:
        return [
            Finding(
                "CANDIDATES",
                INVARIANTS["CANDIDATES"],
                f"candidate {cid!r} is not present in both the prior and resulting state",
            )
        ]
    if kind != "PROMOTE":
        return []

    if not candidate.may_transition_to(after.status):
        return [
            Finding(
                "CANDIDATES",
                INVARIANTS["CANDIDATES"],
                f"candidate {cid!r} cannot move {candidate.status} -> {after.status}",
            )
        ]
    if t.action.operation != "VERIFY_CANDIDATE":
        return [
            Finding(
                "CANDIDATES",
                INVARIANTS["CANDIDATES"],
                f"a candidate is promoted by VERIFY_CANDIDATE, not by "
                f"{t.action.operation!r}",
            )
        ]

    record = _evidence(t, effect.get("evidence_id"))
    if record is None:
        return [
            Finding(
                "CANDIDATES",
                INVARIANTS["CANDIDATES"],
                f"candidate {cid!r} was promoted with evidence "
                f"{effect.get('evidence_id')!r}, which does not exist",
            )
        ]
    ok, why = _accepted(
        t, record, cited_as=effect.get("evidence_id"), claim=candidate.proposition,
        premises=t.action.dependencies, rule=t.action.operation,
    )
    if not ok:
        return [Finding("CANDIDATES", INVARIANTS["CANDIDATES"], why)]
    if not _supports(record, t.action.operation):
        return [
            Finding(
                "CANDIDATES",
                INVARIANTS["CANDIDATES"],
                f"evidence {record.id!r} supports {record.supports_rule!r}, not "
                f"{t.action.operation!r}",
            )
        ]
    # THE check. A candidate is only ever a solution to *these* constraints, so a
    # promotion that verified a subset has verified a different claim than the one made.
    checked = set(record.payload.get("checked_constraints") or ())
    missing = [c for c in candidate.constraint_ids if c not in checked]
    if missing:
        return [
            Finding(
                "CANDIDATES",
                INVARIANTS["CANDIDATES"],
                f"promotion evidence does not check original constraint(s) "
                f"{', '.join(missing)}",
            )
        ]
    if record.payload.get("candidate_id") not in (None, cid):
        return [
            Finding(
                "CANDIDATES",
                INVARIANTS["CANDIDATES"],
                f"evidence {record.id!r} is about candidate "
                f"{record.payload.get('candidate_id')!r}, not {cid!r}",
            )
        ]
    return []


def _check_branch_join(t: Transition) -> list[Finding]:
    """SF-R08. A conclusion does not become global because several branches agree."""
    effect = t.action.branch_effect
    kind = effect.get("kind", "NONE")
    if kind in (None, "NONE"):
        return []
    ids = list(effect.get("branch_ids") or ())
    if kind != "JOIN":
        return []
    if not ids:
        return [
            Finding("BRANCH_JOIN", INVARIANTS["BRANCH_JOIN"], "a join names no branches")
        ]

    for bid in ids:
        branch = t.state_before.branches.get(bid)
        if branch is None:
            return [
                Finding(
                    "BRANCH_JOIN",
                    INVARIANTS["BRANCH_JOIN"],
                    f"branch {bid!r} is not in the prior state",
                )
            ]
        if branch.status not in (BranchStatus.CLOSED, BranchStatus.JOINED):
            return [
                Finding(
                    "BRANCH_JOIN",
                    INVARIANTS["BRANCH_JOIN"],
                    f"branch {bid!r} is {branch.status}; an open branch has not concluded",
                )
            ]

    record = _evidence(t, effect.get("coverage_evidence_id"))
    if record is None:
        return [
            Finding(
                "BRANCH_JOIN",
                INVARIANTS["BRANCH_JOIN"],
                f"the join cites coverage evidence "
                f"{effect.get('coverage_evidence_id')!r}, which does not exist. Branches "
                f"that agree are not a proof that they exhaust the cases",
            )
        ]
    ok, why = _accepted(
        t, record, cited_as=effect.get("coverage_evidence_id"),
        claim=(t.state_after.claims[t.action.output_id].proposition
               if t.action.output_id in t.state_after.claims else None),
        premises=t.action.dependencies, rule=t.action.operation,
    )
    if not ok:
        return [Finding("BRANCH_JOIN", INVARIANTS["BRANCH_JOIN"], why)]
    if not _supports(record, t.action.operation):
        return [
            Finding(
                "BRANCH_JOIN",
                INVARIANTS["BRANCH_JOIN"],
                f"evidence {record.id!r} supports {record.supports_rule!r}, not "
                f"{t.action.operation!r}",
            )
        ]
    covered = set(record.payload.get("branch_ids") or ())
    uncovered = [b for b in ids if b not in covered]
    if uncovered:
        return [
            Finding(
                "BRANCH_JOIN",
                INVARIANTS["BRANCH_JOIN"],
                f"the partition certificate does not cover branch(es) "
                f"{', '.join(uncovered)}",
            )
        ]

    # Every branch must have concluded the SAME thing, and it must be what the join
    # publishes. Context is the only legitimate variance across branches -- that is what
    # makes a case analysis a proof of one proposition rather than a collection of
    # different local results that happen to sit next to each other.
    #
    # Note what is deliberately NOT required: disjointness. Disjunction elimination is
    # sound for overlapping cases, so demanding it would reject valid reasoning. Coverage
    # is the obligation; overlap is not.
    out_id = t.action.output_id
    published = t.state_after.claims.get(out_id) if out_id else None
    if published is not None:
        for bid in ids:
            branch = t.state_before.branches[bid]
            if branch.conclusion is not None and branch.conclusion != published.proposition:
                return [
                    Finding(
                        "BRANCH_JOIN",
                        INVARIANTS["BRANCH_JOIN"],
                        f"branch {bid!r} concluded something other than the joined "
                        f"claim; a join publishes what every branch established, not a "
                        f"new proposition",
                    )
                ]
    return []


def _check_warrant(t: Transition) -> list[Finding]:
    warrant = t.action.warrant
    rule = warrant.get("rule")
    record = _evidence(t, warrant.get("evidence_id"))
    if record is None:
        if warrant.get("evidence_id"):
            return [
                Finding(
                    "WARRANT",
                    INVARIANTS["WARRANT"],
                    f"warrant cites evidence {warrant.get('evidence_id')!r}, which does "
                    f"not exist",
                )
            ]
        return []
    if not _supports(record, rule):
        return [
            Finding(
                "WARRANT",
                INVARIANTS["WARRANT"],
                f"the action claims warrant {rule!r} but evidence {record.id!r} supports "
                f"{record.supports_rule!r}",
            )
        ]
    # The fifth trust site, and it read no status at all until D-052: evidence explicitly
    # marked "REJECTED" was accepted as a warrant. A repair that gated only the four sites
    # D-050 named would have left this open.
    out_id = t.action.output_id
    produced = t.state_after.claims.get(out_id) if out_id else None
    ok, why = _accepted(
        t, record, cited_as=warrant.get("evidence_id"),
        claim=produced.proposition if produced is not None else None,
        premises=t.action.dependencies, rule=rule,
    )
    if not ok:
        return [Finding("WARRANT", INVARIANTS["WARRANT"], why)]

    # SF-R09 binds the *exact* premise list, and the reference checker compares the two
    # lists outright. A subset test was the earlier reading and it is too weak in the
    # dangerous direction: evidence that rests on fewer premises than the action declares
    # was accepted, so an action could quietly acquire ancestry its warrant never
    # justified. Order is significant because the reference treats it as significant; a
    # premise envelope is a record of what was checked, not a set.
    if list(record.premise_ids) != list(t.action.dependencies):
        return [
            Finding(
                "WARRANT",
                INVARIANTS["WARRANT"],
                f"evidence {record.id!r} binds premises {list(record.premise_ids)} but the "
                f"action declares {list(t.action.dependencies)}; a warrant envelope must "
                f"name exactly the premises it was checked against",
            )
        ]
    return []


def _check_epistemic(t: Transition) -> list[Finding]:
    """Generation cannot self-certify: a status upgrade needs valid supporting evidence."""
    effect = t.action.epistemic_effect
    to_status = effect.get("to_status")
    if to_status in (None, "PROPOSED", "UNRESOLVED"):
        return []
    eid = effect.get("evidence_id") or t.action.warrant.get("evidence_id")
    record = _evidence(t, eid)
    if record is None:
        return [
            Finding(
                "EPISTEMIC_STATUS",
                INVARIANTS["EPISTEMIC_STATUS"],
                f"status was raised to {to_status} with no existing supporting evidence",
            )
        ]
    ok, why = _accepted(
        t, record, cited_as=eid,
        claim=(t.state_after.claims[t.action.output_id].proposition
               if t.action.output_id in t.state_after.claims else None),
        premises=t.action.dependencies,
    )
    if not ok:
        return [
            Finding(
                "EPISTEMIC_STATUS",
                INVARIANTS["EPISTEMIC_STATUS"],
                f"status was raised to {to_status} on evidence that does not support it: "
                f"{why}",
            )
        ]
    return []


def _check_goal_discharge(t: Transition) -> list[Finding]:
    """The recorded conclusion must be the one the action actually claims."""
    out = []
    out_id = t.action.output_id
    produced = t.state_after.claims.get(out_id) if out_id else None
    if produced is not None and t.action.summary:
        if produced.proposition != t.action.summary:
            out.append(
                Finding(
                    "GOAL_DISCHARGE",
                    INVARIANTS["GOAL_DISCHARGE"],
                    f"{out_id!r} records a proposition that is not the one the action "
                    f"states; a goal is discharged by its exact target, not an adjacent one",
                )
            )
    effect = t.action.goal_effect
    if effect.get("kind") == "DISCHARGE":
        gid = effect.get("goal_id")
        goal = t.state_before.goals.get(gid) if gid else None
        if goal is None:
            out.append(
                Finding(
                    "GOAL_DISCHARGE",
                    INVARIANTS["GOAL_DISCHARGE"],
                    f"the action discharges goal {gid!r}, which is not in the prior state",
                )
            )
        elif produced is not None and produced.proposition != goal.proposition:
            out.append(
                Finding(
                    "GOAL_DISCHARGE",
                    INVARIANTS["GOAL_DISCHARGE"],
                    f"goal {gid!r} was discharged by a claim that does not state it",
                )
            )
    return out


def _check_type_domain(t: Transition) -> list[Finding]:
    """SF-R13. Declared domains must survive the crossing and must agree."""
    out = []
    declared: dict[str, Any] = t.action.typing.get("input_domains") or {}
    for cid, domain in declared.items():
        claim = t.state_before.claims.get(cid)
        if claim is None:
            continue
        if claim.domain is None:
            # Unreachable: an undeclared domain on a typed input is collected as an unknown
            # and short-circuits to UNRESOLVED before any check runs (D-048). Kept as a
            # guard rather than an assertion because reaching it would mean the collector
            # and this check disagree about which claims the action types, and silently
            # reporting a mismatch would be the worse failure.
            continue
        if not inhabits(claim.domain, domain):
            out.append(
                Finding(
                    "TYPE_DOMAIN",
                    INVARIANTS["TYPE_DOMAIN"],
                    f"{cid!r} is {claim.domain!r} in the state, which does not inhabit the "
                    f"{domain!r} the action requires",
                )
            )
    expected_out = t.action.typing.get("output_domain")
    out_id = t.action.output_id
    produced = t.state_after.claims.get(out_id) if out_id else None
    # Deliberately stricter than the reference checker, which never reads ``output_domain``
    # at all. Retained after adjudication (D-048): where BOTH annotations are present and
    # disagree, that is a real inconsistency and the reference simply does not look. What
    # was withdrawn is the other half -- ``produced.domain or ""`` turned an *absent*
    # annotation into the empty string, which inhabits nothing, so a transition was
    # refused for carrying no domain rather than for carrying a wrong one. SF-R13 says
    # return unresolved when domain evidence is unavailable, and absence is unavailability.
    if produced is not None and produced.domain is not None and expected_out \
            and not inhabits(produced.domain, expected_out):
        out.append(
            Finding(
                "TYPE_DOMAIN",
                INVARIANTS["TYPE_DOMAIN"],
                f"{out_id!r} has domain {produced.domain!r} but the action produces "
                f"{expected_out!r}",
            )
        )
    return out


def _check_frame(t: Transition) -> list[Finding]:
    """The frame condition: ``state_after`` must be what this action produced, and no more.

    The invariant nothing else enforces, and its absence made every other check optional.
    The ten invariants all examine what the action *declares*; not one of them examined
    whether the resulting state is the result of applying that declaration. So a claim
    could simply appear — measured at ``7c9137a``: a record asserting ``0 = 1`` with status
    VERIFIED, no evidence, no warrant and no epistemic effect, was accepted as VALID, and an
    existing premise could be rewritten from ASSUMED to VERIFIED with its proposition
    changed. No forgery of evidence was needed for either; the state was simply asserted.

    The frozen reference has carried this as ``_exact_state_change`` all along, over claims.
    None of the thirty acceptance fixtures attacks it, because every fixture is a
    well-formed record whose delta already matches its action, which is why this survived
    two commits and a 30/30 pass rate (D-049).

    Extended beyond the reference to candidates, branches and obligations. The reference
    frames claims only, so a candidate could be walked ``PROPOSED -> VERIFIED`` with
    ``candidate_effect.kind`` set to ``NONE`` and *zero* constraints checked, and a mandatory
    open obligation could be deleted outright. Both were accepted here and by the reference.
    Recorded as deliberate strictness rather than silently inherited: a verifier whose
    promotion rules can be skipped by declining to mention them is not checking anything.
    """
    out: list[str] = []
    before, after, action = t.state_before, t.state_after, t.action

    for kind, prior, later, licensed in (
        ("claims", before.claims, after.claims, {action.output_id} if action.output_id else set()),
        ("candidates", before.candidates, after.candidates, set()),
        ("branches", before.branches, after.branches, set()),
        ("obligations", before.obligations, after.obligations, _created_obligation_ids(action)),
    ):
        for key, record in prior.items():
            if key not in later:
                out.append(f"{kind}.{key} was removed from the resulting state")
            elif later[key] != record and not _licensed_change(kind, key, t):
                out.append(f"{kind}.{key} changed without a licensed state effect")
        unlicensed = sorted(set(later) - set(prior) - licensed)
        if unlicensed:
            out.append(f"{kind} gained {', '.join(unlicensed)}, which this action does not produce")

    return [Finding("FRAME", INVARIANTS["FRAME"], detail) for detail in out]


def _created_obligation_ids(action: Action) -> set[str]:
    ids = set()
    for spec in action.obligations_created:
        oid = spec.get("id") if isinstance(spec, dict) else spec
        if oid:
            ids.add(oid)
    return ids


def _licensed_change(kind: str, key: str, t: Transition) -> bool:
    """Whether an effect the action declared explicitly licenses mutating this record.

    Only a *declared* effect licenses a change, and the effect's own invariant then decides
    whether the change was legitimate. This is what keeps the frame from forbidding the
    transitions the system exists to make, without letting an undeclared mutation through.
    """
    action = t.action
    if kind == "candidates":
        return action.candidate_effect.get("candidate_id") == key
    if kind == "branches":
        return key in set(action.branch_effect.get("branch_ids") or ())
    if kind == "obligations":
        discharged = {
            e.get("id") if isinstance(e, dict) else e for e in action.obligations_discharged
        }
        return key in discharged
    if kind == "claims":
        return action.scope_effect.get("kind") not in (None, "NONE")
    return False


_CHECKS = (
    _check_dependency,
    _check_scope,
    _check_preconditions,
    _check_obligations,
    _check_candidates,
    _check_branch_join,
    _check_warrant,
    _check_epistemic,
    _check_goal_discharge,
    _check_type_domain,
    #: Last, so a more specific invariant claims the error class first -- the reference
    #: orders it the same way for the same reason.
    _check_frame,
)


def verify(
    transition: Transition,
    *,
    mode: TrustMode,
    attestations: dict[str, Attestation] | None = None,
) -> TransitionResult:
    """Decide one transition.

    ``mode`` is **mandatory** and has no default (D-052). It decides what a recorded
    evidence ``status`` is worth, and there is no answer that is safe to assume: defaulting
    to ``OFFLINE_REPLAY`` means a caller who forgets the argument silently trusts a status
    the record's own author wrote, which is the exact hole D-050 was raised about. Defaulting
    to ``RUNTIME`` would instead make the frozen corpus unreplayable. So the caller states
    which world they are in, every time.

    Prefer :func:`verify_replay` or :func:`verify_runtime`, which name the trust mode in the
    call rather than in an argument.

    Unknowns are collected first and short-circuit, because an invariant cannot be checked
    against a field whose value is "we do not know". They are now **dependency-scoped**
    (:func:`_relevant`): only records the action actually cites can make a transition
    unresolved. Before that, one unrelated ``status: UNKNOWN`` claim appended anywhere in
    either state turned all ten ILLEGAL acceptance fixtures from INVALID to UNRESOLVED — a
    complete detection bypass, since UNRESOLVED counts as neither accepted nor detected
    (D-049).

    **Known divergence, recorded not repaired.** The reference runs every check and only
    then asks whether anything was unknown, so where a transition carries both a violation
    and an unknown, the reference says INVALID and this says UNRESOLVED. Matching it needs
    each check to skip unknown values individually rather than the whole verdict
    short-circuiting, which is a larger change than can be verified against the thirty
    fixtures alone. Narrow, now that the unknown must be on a record the action cites.
    """
    token = _TRUST.set((mode, dict(attestations or {})))
    try:
        unknowns = _collect_unknowns(transition)
        if unknowns:
            return TransitionResult(Verdict.UNRESOLVED, [], unknowns)

        findings: list[Finding] = []
        for check in _CHECKS:
            findings.extend(check(transition))
    finally:
        _TRUST.reset(token)
    if findings:
        return TransitionResult(Verdict.INVALID, findings, [])
    return TransitionResult(Verdict.VALID, [], [])


def verify_replay(transition: Transition) -> TransitionResult:
    """Verify a transition from a **frozen, externally adjudicated corpus**.

    Recorded evidence status is read as observed reference data produced by a process this
    repository does not run. Correct for the Semantic Firewall fixtures and for nothing
    else: never call this on anything a model, a user, or this repository authored.
    """
    return verify(transition, mode=TrustMode.OFFLINE_REPLAY)


def verify_runtime(
    transition: Transition, attestations: dict[str, Attestation] | None = None
) -> TransitionResult:
    """Verify a transition from an **untrusted author** — a model, a user, a generator.

    The record's evidence ``status`` is ignored entirely. Acceptance requires an
    ``Attestation`` carrying a ``CheckedEvidence`` minted by
    ``reasoning.certificates.check``. Passing no attestations is legitimate and simply means
    nothing is attested, so nothing that needs evidence will be accepted.
    """
    return verify(transition, mode=TrustMode.RUNTIME, attestations=attestations)


def replay_payload(payload: dict) -> TransitionResult:
    """Import and replay one frozen corpus record. Import failure is a refusal.

    Named for its trust mode rather than for its mechanics: there is no ``replay_payload``,
    because a caller reaching for "the obvious one" must not thereby choose a trust
    boundary without noticing (D-052).
    """
    from .neutral import import_transition

    return verify_replay(import_transition(payload))


def _unused(state: SemanticState) -> None:  # pragma: no cover - keeps the import honest
    return None
