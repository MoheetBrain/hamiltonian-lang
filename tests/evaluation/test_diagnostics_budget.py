"""Regression tests for the unbounded-diagnostics defect.

The defect: compiler diagnostics rendered into the HML repair prompt grow without bound
relative to the module that produced them, by as much as 122x on pathological input. That
would have silently truncated the repair prompt on exactly the tasks where the model wrote
the worst HML, producing an artefact anti-correlated with the treatment.

These tests pin the bound, and pin the properties that make the bound honest.
"""

from __future__ import annotations

import pytest
from evaluation.v1_benchmark.diagnostics_budget import (
    DIAGNOSTICS_CHAR_CAP,
    DIAGNOSTICS_COUNT_CAP,
    bound_diagnostics,
)
from evaluation.v1_benchmark.scoring import classify_diagnostics

#: The input that produced the 122x blowup, kept as the regression case.
_GARBAGE_MODULE = "\n".join("%%% !!! ??? ###" for _ in range(200))


def test_the_unbounded_render_really_is_unbounded() -> None:
    """Guards the premise. If this stops holding, the cap may be reconsidered."""
    verdict = classify_diagnostics(_GARBAGE_MODULE)
    assert len(verdict.rendered) > 20 * len(_GARBAGE_MODULE)


@pytest.mark.parametrize(
    "source",
    [
        _GARBAGE_MODULE,
        "\n".join(f"let a{i} : Real = undefined_{i} + other_{i}" for i in range(200)),
        "\n".join(f"let ((( {i}" for i in range(200)),
        "\n".join(f"assume p{i} : Probability = 5.0" for i in range(200)),
    ],
)
def test_bounded_render_never_exceeds_the_cap(source: str) -> None:
    verdict = classify_diagnostics(source)
    bounded = bound_diagnostics(verdict.rendered)
    # The cap governs the diagnostics; the omission notice is added on top and is a fixed
    # short constant, so allow for it explicitly rather than loosening the cap.
    assert len(bounded.text) <= DIAGNOSTICS_CHAR_CAP + 200
    assert bounded.shown <= DIAGNOSTICS_COUNT_CAP


def test_truncation_is_announced_and_counted() -> None:
    verdict = classify_diagnostics(_GARBAGE_MODULE)
    bounded = bound_diagnostics(verdict.rendered)
    assert bounded.truncated
    assert bounded.omitted > 0
    assert "omitted" in bounded.text
    assert bounded.to_dict()["diagnostics_omitted"] == bounded.omitted


def test_short_diagnostics_pass_through_untouched() -> None:
    """The cap must not perturb the ordinary case, which is every realistic module."""
    verdict = classify_diagnostics("let x : Real = undefined_name")
    bounded = bound_diagnostics(verdict.rendered)
    assert not bounded.truncated
    assert bounded.omitted == 0
    assert bounded.text.strip() == verdict.rendered.strip()


def test_clean_module_yields_no_diagnostics_and_is_not_marked_truncated() -> None:
    bounded = bound_diagnostics("")
    assert not bounded.truncated
    assert bounded.omitted == 0
    assert bounded.text == "(no diagnostics)"


def test_cap_only_removes_information() -> None:
    """The cap can never add content the compiler did not emit.

    This is what licenses the claim that a positive HML result under the cap is a lower
    bound: the treatment arm can only ever be given less help by this function, never more.
    """
    verdict = classify_diagnostics(_GARBAGE_MODULE)
    bounded = bound_diagnostics(verdict.rendered)
    original_lines = [ln for ln in verdict.rendered.splitlines() if ln.strip()]
    kept = [ln for ln in bounded.text.splitlines() if not ln.startswith("... ")]
    assert kept == original_lines[: len(kept)]
