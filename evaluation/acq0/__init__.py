"""HML-PAPER-DERIVED-INTEGRATION-005 — ACQ0 format-restriction and acquisition protocol.

Why this package exists
-----------------------
*Let Me Speak Freely?* (Tam et al., EMNLP 2024) reports that constraining a model to a
structured output format can degrade **reasoning itself**, not merely the parseability of
what comes back. Three of its findings bear directly on ACQ0:

1. Stricter constraints generally degraded more.
2. Constrained decoding was often worse than prompt-based restriction.
3. A two-stage *natural-language-then-format* approach came closest to unrestricted
   performance.

And one observation that this package is built around: a condition with a **0.148%
parse-error rate** coexisted with a **>38-point** reasoning gap. Parsing success and
content quality are different measurements of different things.

The risk to ACQ0, stated plainly
--------------------------------
ACQ0 asks which candidate surface a model can express a frozen semantic object in. It
runs today under exactly one generation protocol: problem in, target syntax out. If that
protocol is itself damaging the model's reasoning, the tournament does not select the
best syntax — it selects **whichever syntax happens to survive a flawed protocol best**.
The winner would be an artefact of the harness, and nothing downstream of ACQ0 would
reveal it, because every candidate would have been damaged under the same measurement.

So the protocol has to be chosen by measurement before the tournament is trusted, and the
measurement has to keep the eight quantities in :mod:`.protocols.metrics` apart.

What is here
------------
``protocols``
    The three generation protocols, their per-stage token ledgers, the oracle-leakage
    guard, the eight metrics, the offline-safe runner and the lexicographic selector.
``prompts``
    Stage prompts, the field-order inductive-bias controls, and the three
    semantically-identical phrasings for the prompt-sensitivity probe.

What is **not** here
--------------------
Any result. No model call has been made by this package. :func:`.protocols.runner.
run_protocol` refuses a live backend without an explicit :class:`.protocols.runner.
LiveCallAuthorisation`, and :func:`.protocols.selection.select_protocol` refuses to name a
winner from zero measured trials. The calibration design in :mod:`.protocols.calibration`
is built and asserted; executing it is the Lead's call, not this package's.
"""

from __future__ import annotations

ACQ0_PROTOCOL_PACKAGE_VERSION = "hml-acq0-protocol-1.0.0"

#: The paper this package is derived from, cited once so no downstream file has to
#: paraphrase it from memory.
RESEARCH_BASIS = (
    "Tam et al., 'Let Me Speak Freely? A Study on the Impact of Format Restrictions on "
    "Performance of Large Language Models', EMNLP 2024 (Industry Track). Findings used: "
    "format restriction can degrade reasoning, not only parseability; stricter "
    "constraints degrade more; constrained decoding is often worse than prompt-based "
    "restriction; a two-stage NL-then-format pipeline recovers most of the loss; and a "
    "0.148% parse-error rate was observed alongside a >38-point reasoning gap."
)

__all__ = ["ACQ0_PROTOCOL_PACKAGE_VERSION", "RESEARCH_BASIS"]
