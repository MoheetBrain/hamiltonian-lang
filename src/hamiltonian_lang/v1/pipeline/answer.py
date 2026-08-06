"""Reading the answer back out of a module that compiled, and grading it afterwards.

The answer is *extracted*, never inferred
-----------------------------------------
Three extraction routes exist, each grounded in something the compiler already computed:

``check dimension``   the asserted dimension the dimensional checker re-derived and
                      accepted. The value is the compiler's normalised form, not the
                      surface text.
``def``/``const``     exact evaluation by
                      :mod:`hamiltonian_lang.verification.obligations.evaluate`, which
                      raises ``Undecidable`` rather than approximating.
none of the above     ``NOT_EXTRACTED``, with the reason.

There is no fourth route in which a plausible value is composed. An answer this pipeline
cannot read out is reported as absent, because a fabricated one is indistinguishable from
a derived one once it is in the record.

Grading happens strictly afterwards
-----------------------------------
:func:`grade` is the only function that touches the answer key, and it runs after the
final model call has already been made. It calls
``evaluation.corpus.cso.check_answer`` — the deterministic checker every arm is scored
by — so ``solve`` cannot disagree with the evaluation harness about what counts as right.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from ...ast.nodes import CheckStmt, Declaration, DefineStmt, Ref
from . import _evaluation
from .record import AnswerRecord

__all__ = ["extract_answer", "grade"]


def _render(value: Any) -> str:
    """A number or truth value as text, exactly when it is exact."""
    if value.boolean is not None:
        return "TRUE" if value.boolean else "FALSE"
    number = value.number
    if number is None:
        return ""
    if isinstance(number, Fraction):
        if number.denominator == 1:
            return str(number.numerator)
        return repr(float(number))
    return repr(number)


def extract_answer(source: str, *, binding: str | None, file: str = "<answer>") -> AnswerRecord:
    """Read the answer out of ``source``. Never raises; absence is a recorded outcome."""
    from ... import compile_source
    from ...verification.obligations.evaluate import (
        Undecidable,
        build_environment,
        evaluate,
    )

    if binding is None:
        return AnswerRecord(
            kind="NOT_EXTRACTED",
            value=None,
            basis=(
                "the problem file names no answer_binding, so there is no declaration to "
                "read the answer from; nothing is guessed"
            ),
        )

    result = compile_source(source, file)
    if not result.ok():
        codes = ", ".join(d.code for d in result.diagnostics.errors) or "none reported"
        return AnswerRecord(
            kind="NOT_EXTRACTED",
            value=None,
            basis=f"the module does not compile ({codes}), so it denotes nothing to read",
        )

    # 1. An asserted dimension the dimensional checker re-derived and accepted.
    for statement in result.module.statements:
        if (
            isinstance(statement, CheckStmt)
            and statement.check_kind == "dimension"
            and isinstance(statement.subject, Ref)
            and statement.subject.name == binding
            and statement.expected
        ):
            return AnswerRecord(
                kind="DIMENSION",
                value=statement.expected,
                basis=(
                    f"`check dimension {binding}`; the value is the compiler's normalised "
                    "dimension, independently re-derived from the declared types"
                ),
            )

    # 2. Exact evaluation of a definition or a bound declaration.
    env = build_environment(result.module, result.symbols)
    for statement in result.module.statements:
        body = None
        kind_note = ""
        if isinstance(statement, DefineStmt) and statement.name == binding and not statement.params:
            body, kind_note = statement.body, "def"
        elif (
            isinstance(statement, Declaration)
            and statement.name == binding
            and statement.value is not None
        ):
            body, kind_note = statement.value, statement.kind
        if body is None:
            continue
        try:
            value = evaluate(body, env)
        except Undecidable as exc:
            return AnswerRecord(
                kind="NOT_EXTRACTED",
                value=None,
                basis=(
                    f"`{kind_note} {binding}` is outside the exactly-evaluable subset: "
                    f"{exc}"
                ),
            )
        rendered = _render(value)
        if not rendered:
            return AnswerRecord(
                kind="NOT_EXTRACTED",
                value=None,
                basis=f"`{kind_note} {binding}` evaluated to no number and no truth value",
            )
        exactness = "exactly" if value.exact else "inexactly (a float entered the computation)"
        return AnswerRecord(
            kind="BOOLEAN" if value.boolean is not None else "VALUE",
            value=rendered,
            basis=f"`{kind_note} {binding}` evaluated {exactness} by the obligation engine",
        )

    return AnswerRecord(
        kind="NOT_EXTRACTED",
        value=None,
        basis=(
            f"the module compiles but declares no `def`, `const` or `check dimension` "
            f"named {binding!r}"
        ),
    )


def grade(answer: AnswerRecord, answer_key: Any) -> AnswerRecord:
    """Compare against the withheld key. Called only after the last model call.

    Returns a new record; the extraction is never rewritten by the grading.
    """
    from dataclasses import replace

    module = _evaluation.cso()

    if answer.value is None:
        return replace(
            answer,
            matches_key=None,
            key_comparison="no answer was extracted, so nothing was compared",
        )
    spec = module.AnswerSpec(
        kind=answer_key.kind,
        value=answer_key.value,
        tolerance=answer_key.tolerance,
        options=list(answer_key.options),
    )
    correct, normalised = module.check_answer(spec, answer.value)
    return replace(
        answer,
        matches_key=correct,
        normalised=normalised,
        key_comparison=(
            f"checked against the withheld key by evaluation.corpus.cso.check_answer "
            f"(kind={answer_key.kind})"
        ),
    )
