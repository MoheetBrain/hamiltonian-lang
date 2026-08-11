"""The lossless HML view of a transition (SF-R15): typed state out, typed state back.

What this is
------------
``docs/04`` §6.14 makes the canonical typed state primary and HML text *one rendering of
it*. :mod:`.neutral` renders a transition as the corpus's own JSON. This module renders it
as something a person can read, and — the part that makes it a view rather than a report —
reads it back into the identical object.

The property is::

    parse_transition(render_transition(t)) == t

asserted over every acceptance fixture in
``tests/semantic_state/test_lossless_view.py``. The dataclasses in :mod:`.model` are
``frozen=True``, so that equality is structural equality of the whole transition, not a
hash or a normal form. A renderer whose output cannot be read back is a report; the
requirement is a view.

Still no new syntax
-------------------
Nothing here touches ``lexer/``, ``parser/``, ``ast/nodes.py`` or ``backends/``. This is a
self-contained surface with its own reader, which is the established pattern for a
non-HML-L1 surface in this repository (``evaluation/syntax_acquisition/_infix.py`` does the
same). It is deliberately *not* registered as a backend: :class:`backends.base.Backend`
exists to declare loss — its whole API is ``drop`` / ``approximate`` / ``weaken`` over
``Module.statements`` — and a lossless renderer of an object that has no statements and no
source spans would have to lie about both.

Where the view is HML-shaped and where it is not
------------------------------------------------
Claims, candidates, branches, goals, obligations, the action and the evidence records get
real block syntax, because they carry mathematical meaning and a reader should be able to
see the state.

The free-form fields — ``source``, ``typing``, ``warrant``, the six ``*_effect`` maps,
``preconditions``, ``obligations_created``, ``obligations_discharged`` and an evidence
record's ``payload`` — are written as JSON literals. That is a deliberate choice rather
than an unfinished one. Those fields are open dictionaries whose keys the corpus may extend
at any time; :mod:`.neutral` preserves them verbatim precisely because this codebase does
not know what is in them. Inventing an HML-flavoured surface for opaque data would mean
inventing a grammar for content with no semantics attached, and every extension upstream
would silently become unrepresentable. JSON round-trips exactly the types those fields
actually hold, and the renderer *refuses* anything it cannot round-trip rather than
emitting it approximately.

The identity trap
-----------------
A state maps ``id -> record``, and the record carries its own ``id`` field. The neutral
schema permits those to differ, because :func:`.neutral.import_state` reads
``raw.get("id", cid)``. So the view writes the **dictionary key** in the block header and
emits an explicit ``id`` line only when the record disagrees with it. Collapsing the two
would round-trip every fixture and lose a record the first time the corpus produced one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .model import (
    Action,
    Branch,
    BranchStatus,
    Candidate,
    CandidateStatus,
    Claim,
    ClaimStatus,
    EvidenceRecord,
    Goal,
    GoalStatus,
    Obligation,
    ObligationState,
    SemanticState,
    Transition,
)

__all__ = [
    "ViewError",
    "render_transition",
    "parse_transition",
    "render_state",
    "parse_state",
]

INDENT = "  "

#: Identifiers safe to write unquoted. Anything else is emitted as a JSON string, so an id
#: containing a space, a comma or a quote survives instead of corrupting the line.
_BARE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/@+-]*$")


class ViewError(Exception):
    """The view could not be rendered or read. Always a refusal, never a partial result.

    Same discipline as :class:`.neutral.NeutralImportError`: a half-parsed state that looks
    plausible is worse than no state, because nothing downstream can tell the difference.
    """


# ---------------------------------------------------------------------------
# Scalars
# ---------------------------------------------------------------------------


def _ident(value: str) -> str:
    return value if _BARE.match(value) else json.dumps(value)


def _text(value: str) -> str:
    """Propositions are always quoted, never rendered through the AST printer.

    ``Claim.proposition`` is a plain string that arrived from the corpus. Routing it through
    ``backends.hml`` would make it lossless only up to canonical form, and would couple this
    view to a grammar the corpus never agreed to.
    """
    return json.dumps(value)


def _json_safe(value: Any, where: str) -> Any:
    """Refuse a free-form value JSON cannot carry back unchanged.

    ``json.dumps`` will happily coerce a non-string mapping key to a string and a tuple to a
    list, and both survive a casual eye. The round trip would then fail somewhere else
    entirely, or — worse — pass because the test compared the coerced form to itself.
    """
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise ViewError(f"{where}: mapping key {key!r} is not a string")
        return {k: _json_safe(v, f"{where}.{k}") for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v, f"{where}[{i}]") for i, v in enumerate(value)]
    raise ViewError(f"{where}: value of type {type(value).__name__} is not representable")


def _blob(value: Any, where: str) -> str:
    return json.dumps(_json_safe(value, where), sort_keys=True)


def _read_blob(rest: str, where: str) -> Any:
    try:
        return json.loads(rest)
    except ValueError as exc:
        raise ViewError(f"{where}: not a readable value literal: {exc}") from exc


def _read_ident(token: str, where: str) -> str:
    token = token.strip()
    if not token:
        raise ViewError(f"{where}: expected a name")
    if token.startswith('"'):
        value = _read_blob(token, where)
        if not isinstance(value, str):
            raise ViewError(f"{where}: expected a name, got {type(value).__name__}")
        return value
    if not _BARE.match(token):
        raise ViewError(f"{where}: {token!r} is not a valid bare name; quote it")
    return token


def _read_text(rest: str, where: str) -> str:
    value = _read_blob(rest, where)
    if not isinstance(value, str):
        raise ViewError(f"{where}: expected a quoted string, got {type(value).__name__}")
    return value


def _split_idents(rest: str, where: str) -> tuple[str, ...]:
    """Split a comma list without cutting a quoted name in half."""
    out: list[str] = []
    buf: list[str] = []
    in_string = False
    escaped = False
    for ch in rest:
        if in_string:
            buf.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            buf.append(ch)
        elif ch == ",":
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if in_string:
        raise ViewError(f"{where}: unterminated quoted name")
    out.append("".join(buf))
    return tuple(_read_ident(tok, where) for tok in out if tok.strip())


def _enum(cls: Any, token: str, where: str) -> Any:
    try:
        return cls(token)
    except ValueError as exc:
        allowed = ", ".join(sorted(m.value for m in cls))
        raise ViewError(f"{where}: {token!r} is not one of {allowed}") from exc


def _bool(token: str, where: str) -> bool:
    if token == "true":
        return True
    if token == "false":
        return False
    raise ViewError(f"{where}: expected true or false, got {token!r}")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _field(out: list[str], depth: int, name: str, value: str | None) -> None:
    """Emit a field, or nothing at all when the record did not carry one.

    Omission is how the view distinguishes absent from empty. A renderer that helpfully
    wrote ``origin null`` for every record would produce a document that no longer equals
    the one it read, exactly as :func:`.neutral._drop_none` records for the JSON side.
    """
    if value is not None:
        out.append(f"{INDENT * depth}{name} {value}")


def _render_claim(out: list[str], depth: int, key: str, c: Claim) -> None:
    out.append(f"{INDENT * depth}claim {_ident(key)}")
    d = depth + 1
    _field(out, d, "id", _ident(c.id) if c.id != key else None)
    _field(out, d, "proposition", _text(c.proposition))
    _field(out, d, "status", str(c.status))
    _field(out, d, "scope", _ident(c.scope) if c.scope != "global" else None)
    _field(out, d, "domain", _text(c.domain) if c.domain is not None else None)
    _field(out, d, "depends", _idents(c.dependencies))


def _render_candidate(out: list[str], depth: int, key: str, c: Candidate) -> None:
    out.append(f"{INDENT * depth}candidate {_ident(key)}")
    d = depth + 1
    _field(out, d, "id", _ident(c.id) if c.id != key else None)
    _field(out, d, "proposition", _text(c.proposition))
    _field(out, d, "status", str(c.status))
    _field(out, d, "scope", _ident(c.scope) if c.scope != "global" else None)
    _field(out, d, "constraints", _idents(c.constraint_ids))
    _field(out, d, "origin", _text(c.origin) if c.origin is not None else None)
    _field(out, d, "depends", _idents(c.dependencies))
    _field(out, d, "evidence", _ident(c.evidence_id) if c.evidence_id is not None else None)
    _field(
        out,
        d,
        "result",
        _text(c.verification_result) if c.verification_result is not None else None,
    )


def _render_branch(out: list[str], depth: int, key: str, b: Branch) -> None:
    out.append(f"{INDENT * depth}branch {_ident(key)}")
    d = depth + 1
    _field(out, d, "id", _ident(b.id) if b.id != key else None)
    _field(out, d, "predicate", _text(b.predicate))
    _field(out, d, "status", str(b.status))
    _field(out, d, "scope", _ident(b.scope) if b.scope != "global" else None)
    _field(out, d, "conclusion", _text(b.conclusion) if b.conclusion is not None else None)
    _field(
        out, d, "partition", _ident(b.partition_id) if b.partition_id is not None else None
    )


def _render_goal(out: list[str], depth: int, key: str, g: Goal) -> None:
    out.append(f"{INDENT * depth}goal {_ident(key)}")
    d = depth + 1
    _field(out, d, "id", _ident(g.id) if g.id != key else None)
    _field(out, d, "proposition", _text(g.proposition))
    _field(out, d, "status", str(g.status))
    _field(out, d, "scope", _ident(g.scope) if g.scope != "global" else None)


def _render_obligation(out: list[str], depth: int, key: str, o: Obligation) -> None:
    out.append(f"{INDENT * depth}obligation {_ident(key)}")
    d = depth + 1
    _field(out, d, "id", _ident(o.id) if o.id != key else None)
    _field(out, d, "proposition", _text(o.proposition))
    _field(out, d, "status", str(o.status))
    _field(out, d, "mandatory", "true" if o.mandatory else "false")
    _field(out, d, "origin", _text(o.origin) if o.origin is not None else None)
    _field(out, d, "depends", _idents(o.dependencies))
    _field(
        out,
        d,
        "discharge",
        _ident(o.discharge_evidence_id) if o.discharge_evidence_id is not None else None,
    )


def _idents(values: tuple[str, ...]) -> str | None:
    return ", ".join(_ident(v) for v in values) if values else None


def render_state(state: SemanticState, label: str = "", depth: int = 0) -> str:
    out: list[str] = []
    _render_state(out, label, state, depth)
    return "\n".join(out) + "\n"


def _render_state(out: list[str], label: str, state: SemanticState, depth: int = 0) -> None:
    header = f"state {label}".rstrip()
    out.append(f"{INDENT * depth}{header}")
    d = depth + 1
    _field(out, d, "scopes", _idents(state.active_scopes))
    for key in state.claims:
        _render_claim(out, d, key, state.claims[key])
    for key in state.candidates:
        _render_candidate(out, d, key, state.candidates[key])
    for key in state.branches:
        _render_branch(out, d, key, state.branches[key])
    for key in state.goals:
        _render_goal(out, d, key, state.goals[key])
    for key in state.obligations:
        _render_obligation(out, d, key, state.obligations[key])


#: ``action`` field name -> attribute, for the free-form maps and lists. Kept as data so
#: the renderer and the reader cannot drift apart: a field added to :class:`.model.Action`
#: and to this table is handled by both directions at once.
_ACTION_BLOBS = (
    ("preconditions", "preconditions"),
    ("obligations_created", "obligations_created"),
    ("obligations_discharged", "obligations_discharged"),
    ("typing", "typing"),
    ("warrant", "warrant"),
    ("goal_effect", "goal_effect"),
    ("scope_effect", "scope_effect"),
    ("branch_effect", "branch_effect"),
    ("candidate_effect", "candidate_effect"),
    ("epistemic_effect", "epistemic_effect"),
)


def _render_action(out: list[str], action: Action, depth: int = 0) -> None:
    out.append(f"{INDENT * depth}action {_ident(action.id)}")
    d = depth + 1
    _field(out, d, "operation", _text(action.operation))
    _field(out, d, "summary", _text(action.summary) if action.summary else None)
    _field(out, d, "output", _ident(action.output_id) if action.output_id is not None else None)
    _field(out, d, "depends", _idents(action.dependencies))
    for name, attr in _ACTION_BLOBS:
        value = getattr(action, attr)
        if value:
            payload = list(value) if isinstance(value, tuple) else value
            _field(out, d, name, _blob(payload, f"action.{name}"))


def _render_evidence(out: list[str], key: str, rec: EvidenceRecord, depth: int = 0) -> None:
    out.append(f"{INDENT * depth}evidence {_ident(key)}")
    d = depth + 1
    _field(out, d, "id", _ident(rec.id) if rec.id != key else None)
    _field(out, d, "kind", _text(rec.kind))
    _field(out, d, "status", _text(rec.status))
    _field(out, d, "trusted", "true" if rec.trusted else "false")
    _field(
        out, d, "supports", _text(rec.supports_rule) if rec.supports_rule is not None else None
    )
    _field(out, d, "premises", _idents(rec.premise_ids))
    if rec.payload:
        _field(out, d, "payload", _blob(rec.payload, f"evidence.{key}.payload"))


def render_transition(transition: Transition) -> str:
    """Render one transition as readable text that :func:`parse_transition` reads back."""
    out: list[str] = [f"transition {_ident(transition.case_id)}"]
    _field(out, 1, "schema", _text(transition.schema_version))
    if transition.source:
        _field(out, 1, "source", _blob(transition.source, "source"))
    out.append("")
    _render_state(out, "before", transition.state_before)
    out.append("")
    _render_action(out, transition.action)
    for key, rec in transition.evidence.items():
        out.append("")
        _render_evidence(out, key, rec)
    out.append("")
    _render_state(out, "after", transition.state_after)
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Line:
    depth: int
    keyword: str
    rest: str
    number: int

    @property
    def where(self) -> str:
        return f"line {self.number}"


def _lex(text: str) -> list[_Line]:
    lines: list[_Line] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        body = raw.rstrip()
        lead = body[: len(body) - len(body.lstrip())]
        if "\t" in lead:
            # Measured off the *whitespace* run, not the space run: a leading tab is
            # invisible to ``lstrip(" ")``, so reading the indent first would silently
            # treat a tab-indented line as top level.
            raise ViewError(f"line {number}: indent with spaces, not tabs")
        spaces = len(lead)
        if spaces % len(INDENT):
            raise ViewError(f"line {number}: indent {spaces} is not a multiple of {len(INDENT)}")
        keyword, _, rest = stripped.partition(" ")
        lines.append(_Line(spaces // len(INDENT), keyword, rest.strip(), number))
    return lines


class _Cursor:
    """A depth-aware cursor. ``block(d)`` yields exactly the lines nested under a header."""

    def __init__(self, lines: list[_Line]) -> None:
        self._lines = lines
        self._i = 0

    def done(self) -> bool:
        return self._i >= len(self._lines)

    def peek(self) -> _Line | None:
        return None if self.done() else self._lines[self._i]

    def take(self) -> _Line:
        line = self._lines[self._i]
        self._i += 1
        return line

    def block(self, depth: int) -> list[_Line]:
        out = []
        while not self.done() and self._lines[self._i].depth >= depth:
            out.append(self.take())
        return out


def _one_of(line: _Line, allowed: set[str], context: str) -> None:
    if line.keyword not in allowed:
        raise ViewError(
            f"{line.where}: {context} has no field {line.keyword!r} "
            f"(expected one of {', '.join(sorted(allowed))})"
        )


def _read_record_fields(cursor: _Cursor, depth: int, allowed: set[str], context: str) -> dict:
    """Collect ``name value`` lines at ``depth``, refusing repeats and unknown names."""
    fields: dict[str, _Line] = {}
    while (line := cursor.peek()) is not None and line.depth >= depth:
        line = cursor.take()
        if line.depth != depth:
            raise ViewError(f"{line.where}: unexpected indentation inside {context}")
        _one_of(line, allowed, context)
        if line.keyword in fields:
            raise ViewError(f"{line.where}: {context} repeats field {line.keyword!r}")
        fields[line.keyword] = line
    return fields


_CLAIM_FIELDS = {"id", "proposition", "status", "scope", "domain", "depends"}
_CANDIDATE_FIELDS = {
    "id", "proposition", "status", "scope", "constraints", "origin", "depends",
    "evidence", "result",
}
_BRANCH_FIELDS = {"id", "predicate", "status", "scope", "conclusion", "partition"}
_GOAL_FIELDS = {"id", "proposition", "status", "scope"}
_OBLIGATION_FIELDS = {
    "id", "proposition", "status", "mandatory", "origin", "depends", "discharge",
}
_ACTION_FIELDS = {"operation", "summary", "output", "depends"} | {n for n, _ in _ACTION_BLOBS}
_EVIDENCE_FIELDS = {"id", "kind", "status", "trusted", "supports", "premises", "payload"}


def _get(fields: dict[str, _Line], name: str) -> _Line | None:
    return fields.get(name)


def _txt(fields: dict[str, _Line], name: str, default: str = "") -> str:
    line = _get(fields, name)
    return default if line is None else _read_text(line.rest, line.where)


def _opt_txt(fields: dict[str, _Line], name: str) -> str | None:
    line = _get(fields, name)
    return None if line is None else _read_text(line.rest, line.where)


def _opt_id(fields: dict[str, _Line], name: str) -> str | None:
    line = _get(fields, name)
    return None if line is None else _read_ident(line.rest, line.where)


def _ids(fields: dict[str, _Line], name: str) -> tuple[str, ...]:
    line = _get(fields, name)
    return () if line is None else _split_idents(line.rest, line.where)


def _status(fields: dict[str, _Line], cls: Any, fallback: Any) -> Any:
    line = _get(fields, "status")
    return fallback if line is None else _enum(cls, line.rest, line.where)


def _parse_state_block(cursor: _Cursor, depth: int) -> SemanticState:
    claims: dict[str, Claim] = {}
    candidates: dict[str, Candidate] = {}
    branches: dict[str, Branch] = {}
    goals: dict[str, Goal] = {}
    obligations: dict[str, Obligation] = {}
    scopes: tuple[str, ...] = ("global",)

    while (line := cursor.peek()) is not None and line.depth >= depth:
        line = cursor.take()
        if line.depth != depth:
            raise ViewError(f"{line.where}: unexpected indentation inside state")
        if line.keyword == "scopes":
            scopes = _split_idents(line.rest, line.where) or ("global",)
            continue
        key = _read_ident(line.rest, line.where)
        if line.keyword == "claim":
            f = _read_record_fields(cursor, depth + 1, _CLAIM_FIELDS, "a claim")
            claims[key] = Claim(
                id=_opt_id(f, "id") or key,
                proposition=_txt(f, "proposition"),
                status=_status(f, ClaimStatus, ClaimStatus.GIVEN),
                scope=_opt_id(f, "scope") or "global",
                domain=_opt_txt(f, "domain"),
                dependencies=_ids(f, "depends"),
            )
        elif line.keyword == "candidate":
            f = _read_record_fields(cursor, depth + 1, _CANDIDATE_FIELDS, "a candidate")
            candidates[key] = Candidate(
                id=_opt_id(f, "id") or key,
                proposition=_txt(f, "proposition"),
                status=_status(f, CandidateStatus, CandidateStatus.PROPOSED),
                scope=_opt_id(f, "scope") or "global",
                constraint_ids=_ids(f, "constraints"),
                origin=_opt_txt(f, "origin"),
                dependencies=_ids(f, "depends"),
                evidence_id=_opt_id(f, "evidence"),
                verification_result=_opt_txt(f, "result"),
            )
        elif line.keyword == "branch":
            f = _read_record_fields(cursor, depth + 1, _BRANCH_FIELDS, "a branch")
            branches[key] = Branch(
                id=_opt_id(f, "id") or key,
                predicate=_txt(f, "predicate"),
                status=_status(f, BranchStatus, BranchStatus.OPEN),
                scope=_opt_id(f, "scope") or "global",
                conclusion=_opt_txt(f, "conclusion"),
                partition_id=_opt_id(f, "partition"),
            )
        elif line.keyword == "goal":
            f = _read_record_fields(cursor, depth + 1, _GOAL_FIELDS, "a goal")
            goals[key] = Goal(
                id=_opt_id(f, "id") or key,
                proposition=_txt(f, "proposition"),
                status=_status(f, GoalStatus, GoalStatus.OPEN),
                scope=_opt_id(f, "scope") or "global",
            )
        elif line.keyword == "obligation":
            f = _read_record_fields(cursor, depth + 1, _OBLIGATION_FIELDS, "an obligation")
            mandatory = _get(f, "mandatory")
            obligations[key] = Obligation(
                id=_opt_id(f, "id") or key,
                proposition=_txt(f, "proposition"),
                status=_status(f, ObligationState, ObligationState.OPEN),
                mandatory=True if mandatory is None else _bool(mandatory.rest, mandatory.where),
                origin=_opt_txt(f, "origin"),
                dependencies=_ids(f, "depends"),
                discharge_evidence_id=_opt_id(f, "discharge"),
            )
        else:
            raise ViewError(
                f"{line.where}: a state holds claims, candidates, branches, goals and "
                f"obligations, not {line.keyword!r}"
            )
    return SemanticState(
        claims=claims,
        candidates=candidates,
        branches=branches,
        goals=goals,
        obligations=obligations,
        active_scopes=scopes,
    )


def _parse_action_block(cursor: _Cursor, key: str, depth: int) -> Action:
    f = _read_record_fields(cursor, depth, _ACTION_FIELDS, "an action")
    blobs: dict[str, Any] = {}
    for name, attr in _ACTION_BLOBS:
        line = _get(f, name)
        if line is None:
            blobs[attr] = () if attr.startswith(("precond", "obligations")) else {}
            continue
        value = _read_blob(line.rest, line.where)
        if attr.startswith(("precond", "obligations")):
            if not isinstance(value, list):
                raise ViewError(f"{line.where}: {name} must be a list")
            blobs[attr] = tuple(value)
        else:
            if not isinstance(value, dict):
                raise ViewError(f"{line.where}: {name} must be a mapping")
            blobs[attr] = value
    return Action(
        id=key,
        operation=_txt(f, "operation"),
        summary=_txt(f, "summary"),
        output_id=_opt_id(f, "output"),
        dependencies=_ids(f, "depends"),
        **blobs,
    )


def _parse_evidence_block(cursor: _Cursor, key: str, depth: int) -> EvidenceRecord:
    f = _read_record_fields(cursor, depth, _EVIDENCE_FIELDS, "an evidence record")
    trusted = _get(f, "trusted")
    payload_line = _get(f, "payload")
    payload: dict[str, Any] = {}
    if payload_line is not None:
        value = _read_blob(payload_line.rest, payload_line.where)
        if not isinstance(value, dict):
            raise ViewError(f"{payload_line.where}: an evidence payload must be a mapping")
        payload = value
    return EvidenceRecord(
        id=_opt_id(f, "id") or key,
        kind=_txt(f, "kind"),
        status=_txt(f, "status", "UNKNOWN"),
        trusted=False if trusted is None else _bool(trusted.rest, trusted.where),
        supports_rule=_opt_txt(f, "supports"),
        premise_ids=_ids(f, "premises"),
        payload=payload,
    )


def parse_state(text: str) -> SemanticState:
    cursor = _Cursor(_lex(text))
    line = cursor.peek()
    if line is None or line.keyword != "state":
        raise ViewError("expected a 'state' block")
    cursor.take()
    return _parse_state_block(cursor, line.depth + 1)


def parse_transition(text: str) -> Transition:
    """Read a rendered view back into the identical :class:`.model.Transition`.

    Fails closed. A field the reader does not recognise, a repeated field, a status outside
    its enum or a malformed literal is a refusal — never a default, and never a partial
    transition that happens to parse.
    """
    cursor = _Cursor(_lex(text))
    line = cursor.peek()
    if line is None or line.keyword != "transition":
        raise ViewError("a view must open with a 'transition' block")
    cursor.take()
    case_id = _read_ident(line.rest, line.where)

    schema = "semantic-firewall-case-0.1.0"
    source: dict[str, Any] = {}
    states: dict[str, SemanticState] = {}
    action: Action | None = None
    evidence: dict[str, EvidenceRecord] = {}

    while not cursor.done():
        line = cursor.take()
        if line.depth != 1 and line.keyword in ("schema", "source"):
            raise ViewError(f"{line.where}: {line.keyword} belongs to the transition header")
        if line.keyword == "schema":
            schema = _read_text(line.rest, line.where)
        elif line.keyword == "source":
            value = _read_blob(line.rest, line.where)
            if not isinstance(value, dict):
                raise ViewError(f"{line.where}: source must be a mapping")
            source = value
        elif line.keyword == "state":
            label = line.rest.strip()
            if label not in ("before", "after"):
                raise ViewError(f"{line.where}: a state is 'before' or 'after', not {label!r}")
            if label in states:
                raise ViewError(f"{line.where}: state {label} appears twice")
            states[label] = _parse_state_block(cursor, line.depth + 1)
        elif line.keyword == "action":
            if action is not None:
                raise ViewError(f"{line.where}: a transition carries exactly one action")
            action = _parse_action_block(
                cursor, _read_ident(line.rest, line.where), line.depth + 1
            )
        elif line.keyword == "evidence":
            key = _read_ident(line.rest, line.where)
            if key in evidence:
                raise ViewError(f"{line.where}: evidence {key!r} appears twice")
            evidence[key] = _parse_evidence_block(cursor, key, line.depth + 1)
        else:
            raise ViewError(f"{line.where}: unexpected block {line.keyword!r}")

    if action is None:
        raise ViewError("a transition record must carry an action")
    for label in ("before", "after"):
        if label not in states:
            raise ViewError(f"a transition must carry a 'state {label}' block")
    return Transition(
        case_id=case_id,
        action=action,
        state_before=states["before"],
        state_after=states["after"],
        evidence=evidence,
        schema_version=schema,
        source=source,
    )
