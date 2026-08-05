"""Benchmark corpus governance — the five ordered gates a candidate must survive.

The research basis is FormalMATH (autoformalisation benchmark construction). Its central
finding, and the reason this package exists:

    **Compiler acceptance is not semantic correctness.**

FormalMATH's own funnel dropped from roughly 92% compiler-valid candidates to roughly 32%
retained after semantic checking. Two thirds of everything a type checker was willing to
accept did not mean what the specification said. A benchmark built on gate 1 alone is not
a benchmark; it is a syntax test wearing a benchmark's clothes.

The five gates, in order
-----------------------
1. :mod:`.gates` — parser/compiler validation. Necessary. Never sufficient.
2. :mod:`.semantic_checks` — deterministic semantic checks against the recorded ground
   truth. Offline, no model, no judgement.
3. :mod:`.back_translation` — render the formal object back into controlled natural
   language and compare against the original specification.
4. :mod:`.negation` — construct the negation and attempt to prove it. **Asymmetric**.
5. :mod:`.human_gate` — explicit human review wherever the machinery is unresolved or the
   decision is promotion-critical.

Three design commitments that are enforced by types rather than by convention
-----------------------------------------------------------------------------
**The negation attack cannot validate anything.** :mod:`.negation` has a ``Refutation``
constructor and a ``NoInformation`` constructor and no third one. There is no code path,
anywhere, that converts "we could not prove the negation" into support for the candidate,
because no type exists to hold that value. A comment saying "note: this is asymmetric"
would be deleted by the first person in a hurry; a missing constructor cannot be.

**Judge disagreement is preserved, never averaged.** :class:`.back_translation.JudgePanel`
retains every individual decision and exposes no majority vote. Where independent judges
disagree the panel returns ``INCONCLUSIVE`` and raises a human-review request. Collapsing
three judges into one number destroys the only signal that says "this item is ambiguous".

**The pipeline stops rather than resolves.** :mod:`.human_gate` has no ``auto_resolve``.
A corpus that silently self-approves its own hard cases is unfalsifiable: every item it
retains is an item its own machinery was comfortable with.

Local reality this package is built for
---------------------------------------
``stanc`` and Mathlib are absent from this machine, and the Lean backend closes every
obligation with ``sorry`` by design — so ``lean_verify`` rejects its own backend's output
and **no Lean path can certify anything here**. SymPy 1.14.0 is present and works. Every
check in this package is therefore either pure Python over the frozen AST, or SymPy, or
an explicitly-recorded human decision. Nothing here calls a model; nothing here calls a
proof assistant. ``tests/evaluation/test_corpus_governance.py`` asserts the absence of
both import edges.
"""

from __future__ import annotations

__all__ = [
    "CORPUS_GOVERNANCE_VERSION",
    "GATE_ORDER",
]

#: Bump when a gate is added, reordered, or its admission contract changes. Every report
#: records it, so a result can never be compared silently against a different funnel.
CORPUS_GOVERNANCE_VERSION = "hml-corpus-governance-1.0.0"

#: The funnel is ordered and total. A later gate never runs on an item an earlier gate
#: rejected, because the later gate's question is not meaningful for it: asking whether a
#: non-compiling object back-translates faithfully is asking about the meaning of
#: something that has no meaning.
GATE_ORDER: tuple[str, ...] = (
    "compiler",
    "deterministic_semantics",
    "back_translation",
    "negation_attack",
    "human_review",
)
