"""Build a model-safe ACQ0 bundle, and prove it carries nothing it must not.

An allowlist, not a denylist. A denylist fails open on whatever nobody thought of, and the
thing being guarded here is the answer key: a leak looks exactly like success.

Nothing in this module sends anything anywhere.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .canonical_v2 import CanonicalAcq0TaskV2
from .v2_render import render_surface

__all__ = ["ALLOWED_PARTS", "FORBIDDEN_CONTENT", "SafeBundle", "build_bundle",
           "BundleLeak"]


class BundleLeak(RuntimeError):
    """Raised when a bundle would carry private material. Never downgraded to a warning."""


#: The only parts a model-visible bundle may contain.
ALLOWED_PARTS = (
    "blind_instruction",
    "shared_semantics",
    "surface_specification",
    "demonstrations",
    "structured_target",
    "prose",
    "output_contract",
)

#: Names of things that must never appear, checked by key and by value.
FORBIDDEN_CONTENT = (
    "reference_hml", "authoritative_source", "expected_hash", "canonical_hash",
    "semantic_identity", "scorer", "semantic_diff", "private", "answer_key",
    "human_review",
)


@dataclass(frozen=True)
class SafeBundle:
    task_id: str
    surface: str
    parts: dict[str, Any]
    part_hashes: dict[str, str] = field(default_factory=dict)
    bundle_hash: str = ""

    def inventory(self) -> list[tuple[str, int, str]]:
        return [(k, len(json.dumps(v)), self.part_hashes[k]) for k, v in self.parts.items()]


def _normalise(text: str) -> str:
    """Collapse whitespace and unescape, so escaping cannot hide a match."""
    return " ".join(text.replace("\\n", " ").replace("\\t", " ").split())


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def build_bundle(
    task: CanonicalAcq0TaskV2,
    surface: str,
    demonstrations: tuple[CanonicalAcq0TaskV2, ...] = (),
) -> SafeBundle:
    """Assemble, then scan. The scan runs on the assembled object, not on intentions."""
    parts: dict[str, Any] = {
        "blind_instruction": (
            "Encode the supplied mathematical object faithfully in the assigned surface "
            "syntax. Do not solve, add, remove or change anything. Output only the "
            "encoding."),
        "shared_semantics": "see MODEL_FILES/SHARED_HML_SEMANTICS.md",
        "surface_specification": surface,
        "demonstrations": [
            {"task_id": d.task_id, "rendering": render_surface(d, surface)}
            for d in demonstrations
        ],
        "structured_target": task.structured_target(),
        "prose": None,
        "output_contract": "one fenced encoding, nothing before or after",
    }

    unexpected = set(parts) - set(ALLOWED_PARTS)
    if unexpected:
        raise BundleLeak(f"bundle carries parts outside the allowlist: {sorted(unexpected)}")

    # Scan a WHITESPACE-NORMALISED blob, not the JSON text. json.dumps escapes newlines,
    # so a raw multi-line source is never a substring of it and every containment check
    # silently passes -- the negative control caught exactly that here. A leak check that
    # cannot fail is worse than none, because it reports safety.
    blob = _normalise(json.dumps(parts, sort_keys=True, default=str))

    # The authoritative source must not appear, in any surface, anywhere in the bundle.
    # Demonstrations legitimately carry *their own* renderings; the task under test must
    # not carry its own.
    if task.source.strip() and _normalise(task.source) in blob:
        raise BundleLeak("the authoritative source appears in the bundle")
    for name in ("A_v0_labelled_linear", "B_v1_labelled_linear_simplified",
                 "C_prefix_sexpr", "D_constrained_json_graph"):
        rendering = _normalise(render_surface(task, name))
        if rendering and rendering in blob:
            raise BundleLeak(f"the task's own {name} reference rendering appears in the bundle")

    for token in (task.canonical_hash(), task.semantic_identity()):
        if token in blob:
            raise BundleLeak("an expected hash appears in the bundle")

    for word in FORBIDDEN_CONTENT:
        if word in blob.lower():
            raise BundleLeak(f"forbidden term {word!r} appears in the bundle")

    part_hashes = {k: _sha(v) for k, v in parts.items()}
    return SafeBundle(task.task_id, surface, parts, part_hashes, _sha(parts))
