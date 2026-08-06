"""The ordered model-visible view, and the gate that proves it is sufficient.

The defect this replaces
------------------------
`structured_target()` partitioned a module into unordered kind-buckets — declarations,
assumptions, requirements — while `content_hash` is order-sensitive. Three of eight tasks
were therefore unencodable: an encoder reading the view had no way to know that
`v2_transformation_side_condition_001` puts `require` *before* `assume`. The other five
passed by coincidence, their source order happening to match the bucket order.

A fourth task was worse: `structured_target()` had no `CheckStmt` branch, so
`check dimension pressure = ...` existed in the reference and in no model-visible artefact
at all.

Why three separate checks missed it
------------------------------------
`check_prose_coverage`, `reconstruct_semantic_payload` and the 32/32 surface round-trip all
validated an artefact **against itself**: the first two derive from `structured_target()`
and re-read its own keys; the third renders from `task.source` and never traverses the view.
None of them crossed the boundary where the loss occurs.

The gate
--------
    model-visible view  ->  reconstruct  ->  compile  ->  canonical hash  ==  reference

`reconstruct_source` may read the view and nothing else. Not the authored source, not the
reference, not the expected hash. If a task cannot survive that, a model cannot encode it,
and no amount of model capability would change the outcome.

Structured fields, not rendered lines
--------------------------------------
Each record carries *structured* content — kind, name, type, value, expression — rather than
a rendered HML-L1 line. Handing over the line would make surface A a copying exercise and
stop measuring translation, which is the whole point of ACQ0.
"""

from __future__ import annotations

from typing import Any

from .canonical_v2 import CanonicalAcq0TaskV2

__all__ = ["encoding_view", "statement_records", "reconstruct_source",
           "view_reconstructs_exactly", "ViewIncomplete", "UnsupportedStatement"]


class ViewIncomplete(RuntimeError):
    """The view lacks something reconstruction needs. Never defaulted around."""


class UnsupportedStatement(RuntimeError):
    """A statement kind with no model-visible representation. Fails closed."""


def _expr(node: Any) -> str:
    from hamiltonian_lang.backends.hml import render_expr
    return "" if node is None else render_expr(node)


def statement_records(module: Any, task_id: str = "<module>") -> list[dict[str, Any]]:
    """The ordered positional records of ONE module. The single statement derivation.

    Exposed separately from :func:`encoding_view` so that every consumer — the view, the
    fact layer, the prose generator, the semantic diff — reads the *same* traversal. The
    defect this closes is a second derivation drifting from the first: a parallel
    kind-bucket walk had no `CheckStmt` branch, so the fact layer certified full prose
    coverage for a task whose defining statement it could not see, and the semantic diff
    reported `equal: False` with an empty difference list.

    It also runs over a *submitted* module, which is what makes a positional diff possible.
    """
    from hamiltonian_lang.ast.nodes import (
        AssumeStmt,
        CheckStmt,
        Declaration,
        DefineStmt,
        InferStmt,
        LawStmt,
        ModuleDecl,
        ObjectiveStmt,
        ProveStmt,
        RequireStmt,
        SolveStmt,
    )

    statements: list[dict[str, Any]] = []
    position = 0
    for st in module.statements:
        if isinstance(st, ModuleDecl):
            continue  # carried as `module`, not as a positional statement
        position += 1
        base = {"position": position, "statement_id": f"s{position}", "emit": True}

        if isinstance(st, Declaration):
            rec = {**base, "kind": st.kind, "name": st.name,
                   "type": st.declared_type.render() if st.declared_type else None,
                   "epistemic_role": "declaration"}
            if st.value is not None:
                rec["value"] = _expr(st.value)
            statements.append(rec)
        elif isinstance(st, DefineStmt):
            statements.append({**base, "kind": "def", "name": st.name,
                               "binders": [{"name": n, "type": t.render() if t else None}
                                           for n, t in st.params],
                               "codomain": st.declared_type.render() if st.declared_type else None,
                               "body": _expr(st.body), "epistemic_role": "definition"})
        elif isinstance(st, AssumeStmt):
            statements.append({**base, "kind": "assume", "expression": _expr(st.proposition),
                               "epistemic_role": "supplied_assumption"})
        elif isinstance(st, RequireStmt):
            statements.append({**base, "kind": "require", "expression": _expr(st.proposition),
                               "epistemic_role": "domain_constraint"})
        elif isinstance(st, ProveStmt):
            statements.append({**base, "kind": "prove", "expression": _expr(st.proposition),
                               "epistemic_role": "proof_obligation"})
        elif isinstance(st, LawStmt):
            statements.append({**base, "kind": st.role,
                               "target": st.target_symbol.name if st.target_symbol else None,
                               "given": [g.symbol_id.name for g in st.given if g.symbol_id],
                               "distribution": _expr(st.distribution),
                               "epistemic_role": "probability_law"})
        elif isinstance(st, CheckStmt):
            # The statement whose absence made a task unencodable.
            statements.append({**base, "kind": f"check_{st.check_kind}",
                               "subject": _expr(st.subject),
                               "expression": str(st.expected),
                               "epistemic_role": "checked_property"})
        elif isinstance(st, (SolveStmt, InferStmt, ObjectiveStmt)):
            raise UnsupportedStatement(
                f"{task_id}: {type(st).__name__} has no model-visible representation "
                f"yet; failing closed rather than dropping it silently")
        else:
            raise UnsupportedStatement(
                f"{task_id}: {type(st).__name__} is not representable in the view")

    return statements


def encoding_view(task: CanonicalAcq0TaskV2) -> dict[str, Any]:
    """The complete model-visible artefact: ordered statements plus emit=false metadata."""
    return {
        "schema_version": task.schema_version,
        "task_id": task.task_id,
        "family": str(task.family),
        "module": task.module.name,
        "encoding_statements": statement_records(task.module, task.task_id),
        # emit=false records are explanatory. They must not reach the encoding, and the
        # rule is stated in the view rather than left to the reader -- v1's `digamma != 0`
        # sat beside the assumptions with nothing saying which to encode.
        "derived_facts": [
            {"expression": f.statement, "derived_from": list(f.derived_from),
             "emit": False} for f in task.derived_facts
        ],
        "prohibited_assumptions": [
            {"statement": p, "emit": False} for p in task.prohibited_assumptions
        ],
        # `emit: False` like every other metadata record. Without it the objective was
        # the one model-visible field with no disposition, and the emission rule -- which
        # excluded only "records with emit=false" -- did not reach it. An encoder could
        # read it as a further statement, and for all four objective-bearing tasks that
        # reading compiled and hashed differently.
        "objective": (None if task.objective is None
                      else {"kind": task.objective.kind,
                            "statement": task.objective.statement,
                            "emit": False}),
        "emission_rule": (
            "Emit the module header named by `module` first, then exactly the records in "
            "encoding_statements, in position order — no more and no fewer. Anything "
            "carrying emit=false — derived facts, prohibited assumptions, and the "
            "objective — is explanatory metadata describing statements already listed, "
            "and must never appear in the output as a statement of its own."
        ),
    }


def reconstruct_source(view: dict[str, Any]) -> str:
    """Rebuild HML-L1 from the view **alone**.

    Reads no authored source, no reference, no expected hash, no other task. A missing
    field raises: silently defaulting one is how an encoder gets blamed for information it
    never had.
    """
    for key in ("module", "encoding_statements"):
        if key not in view:
            raise ViewIncomplete(f"the view omits {key!r}")

    lines = [f"module {view['module']}"]
    records = sorted(
        (r for r in view["encoding_statements"] if r.get("emit", True)),
        key=lambda r: r["position"],
    )
    positions = [r["position"] for r in records]
    if positions != list(range(1, len(positions) + 1)):
        raise ViewIncomplete(f"positions are not a contiguous 1..n sequence: {positions}")

    for r in records:
        kind = r.get("kind")
        if kind in {"var", "const", "param", "obs", "index", "rv"}:
            if not r.get("type"):
                raise ViewIncomplete(f"{r['statement_id']}: declaration has no type")
            line = f"{kind} {r['name']} : {r['type']}"
            if kind in {"const", "obs"}:
                if "value" not in r:
                    raise ViewIncomplete(
                        f"{r['statement_id']}: {kind} {r['name']!r} has no value; an "
                        f"encoder cannot invent one")
                line += f" = {r['value']}"
            lines.append(line)
        elif kind == "def":
            if not r.get("body"):
                raise ViewIncomplete(f"{r['statement_id']}: definition has no body")
            if not r.get("codomain"):
                raise ViewIncomplete(
                    f"{r['statement_id']}: definition has no codomain; annotated and "
                    f"unannotated definitions canonicalise differently")
            binders = ", ".join(f"{b['name']} : {b['type']}" for b in r.get("binders", []))
            head = f"def {r['name']}({binders})" if binders else f"def {r['name']}"
            lines.append(f"{head} : {r['codomain']} := {r['body']}")
        elif kind in {"assume", "require", "prove"}:
            lines.append(f"{kind} {r['expression']}")
        elif kind in {"prior", "likelihood", "law", "posterior"}:
            given = " | " + " ".join(r["given"]) if r.get("given") else ""
            lines.append(f"{kind} {r['target']}{given} ~ {r['distribution']}")
        elif kind and kind.startswith("check_"):
            lines.append(f"check {kind[len('check_'):]} {r['subject']} = {r['expression']}")
        else:
            raise ViewIncomplete(f"{r['statement_id']}: unknown statement kind {kind!r}")

    return "\n".join(lines) + "\n"


def view_reconstructs_exactly(task: CanonicalAcq0TaskV2) -> tuple[bool, str]:
    """THE admission gate. View -> source -> compile -> hash == reference."""
    from hamiltonian_lang import compile_source, content_hash

    try:
        rebuilt = reconstruct_source(encoding_view(task))
    except (ViewIncomplete, UnsupportedStatement) as exc:
        return False, f"reconstruction failed: {exc}"

    result = compile_source(rebuilt, f"<{task.task_id}:reconstructed>")
    if not result.ok():
        return False, (f"the reconstruction does not compile: "
                       f"{[d.code for d in result.diagnostics.errors]}\n{rebuilt}")

    got = content_hash(rebuilt)
    if got != task.canonical_hash():
        return False, (f"canonical mismatch: reconstructed {got[:16]} vs reference "
                       f"{task.canonical_hash()[:16]}\n--- reconstructed ---\n{rebuilt}")
    return True, "exact"
