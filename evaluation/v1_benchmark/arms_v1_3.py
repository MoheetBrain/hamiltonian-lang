"""The v1.3 repair prompt, which matches what the two arms carry into their second call.

The defect
----------
The frozen design states its own intent plainly (``arms.py``): *"The two arms then differ in
exactly one respect, which is the treatment: HML-V1's second call carries compiler
diagnostics, and SE's does not."*

They differ in two. Reading the pipeline:

* ``se_review_prompt(cso, r1.content)`` — the SE arm carries its **entire** first reply.
* ``hml_repair_prompt(cso, module, ...)`` — the HML arm carries **only the extracted fence**.

So the SE arm re-reads all of its own reasoning on its second attempt and the HML arm does
not. If the HML arm emitted no fence at all, its second call receives the literal string
``(no module emitted)`` and nothing else, while SE always receives everything it wrote.

Direction of the bias, and why it matters for a kill verdict
-------------------------------------------------------------
This handicaps the **treatment** arm. A *positive* HML result would therefore not be
explained by it. But a *null or negative* result could be — and this study's whole purpose
is to decide whether to continue or kill, so a kill verdict resting on an arm that was
denied its own working would not be trustworthy.

The fix is to carry the HML arm's full prior working as well, so that both arms re-read
everything they wrote, and the **only** remaining difference is the compiler diagnostics.
That is the design as written down; the code simply did not implement it.

What is deliberately NOT added
------------------------------
The language specification is **not** re-supplied on the repair call. ``hml_repair_prompt``
accepts a ``surface_spec`` argument and never uses it, which reads like a second defect and
is not one: ``se_review_prompt`` likewise omits ``SCHEMA_A_PRIME``, and calls carry no
conversation history, so under the frozen design *both* arms work without their format
guidance on call two. That is matched, and adding the spec to HML alone would create a new
asymmetry favouring the treatment. It is left exactly as frozen and recorded as a handicap.
"""

from __future__ import annotations

from evaluation.acq0.protocols.oracle import OracleExemption
from evaluation.corpus.cso import CanonicalSemanticObject
from evaluation.corpus.renderers import HML_SPEC
from evaluation.v1_benchmark.arms import (
    _CARRIED_PLACEHOLDER,
    Arm,
    ArmPrompt,
    _answer_block,
    _guard,
    _problem_block,
    _refuse_exemption,
    strip_answer_block,
)
from evaluation.v1_benchmark.protocol_v1_2 import PER_CALL_COMPLETION_ALLOWANCE

__all__ = ["hml_repair_prompt_v13"]

_NOTE = (
    "\n\nThe compiler checks the module's form: that it parses, that every name resolves, "
    "and that it type-checks. It does not know the answer and cannot tell you whether the "
    "module models the right problem. Re-examine your working above for errors of "
    "reasoning, scope or arithmetic, repair the module, then give your final answer."
)


def hml_repair_prompt_v13(
    cso: CanonicalSemanticObject,
    previous_reply: str,
    module: str,
    diagnostics: str,
    *,
    surface_spec: str = HML_SPEC,
    exemption: OracleExemption | None = None,
) -> ArmPrompt:
    """The repair call, carrying the same prior working the SE arm's review call carries.

    ``previous_reply`` is the model's whole first reply, stripped of its answer span exactly
    as the SE arm's is — so the anchoring confound ``strip_answer_block`` exists to remove is
    removed identically in both arms.
    """
    _refuse_exemption(exemption, "hml_repair_prompt_v13")
    system = (
        "You are solving a mathematics problem. Be precise. Do not restate the problem. "
        "Your reply must end with the final answer wrapped in "
        "<ANSWER> and </ANSWER> markers, and nothing after the closing marker."
    )

    def _assemble(working: str, mod: str, diags: str) -> str:
        return "\n\n".join(
            [
                _problem_block(cso),
                "YOUR PREVIOUS WORKING\n" + working,
                "YOUR PREVIOUS MODULE\n" + mod,
                "COMPILER OUTPUT\n" + diags + _NOTE,
                _answer_block(cso),
            ]
        )

    user = _assemble(strip_answer_block(previous_reply), module, diagnostics.strip())
    # Working, module and diagnostics are all model-produced, so all three are excluded from
    # the leak scan for the reason given in `arms._guard`; the authored scaffolding around
    # them is guarded on its own.
    _guard(
        system
        + "\n"
        + _assemble(_CARRIED_PLACEHOLDER, _CARRIED_PLACEHOLDER, _CARRIED_PLACEHOLDER),
        cso,
        "HML-V1:repair:v1.3",
    )
    return ArmPrompt(Arm.HML_V1, "repair", system, user, PER_CALL_COMPLETION_ALLOWANCE)
