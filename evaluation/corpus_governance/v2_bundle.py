"""Build a model-safe ACQ0 bundle, and prove it carries nothing it must not.

An allowlist, not a denylist. A denylist fails open on whatever nobody thought of, and the
thing being guarded here is the answer key: a leak looks exactly like success.

Nothing in this module sends anything anywhere.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .canonical_v2 import CanonicalAcq0TaskV2
from .v2_render import render_prose, render_surface
from .v2_view import encoding_view

__all__ = ["ALLOWED_PARTS", "FORBIDDEN_CONTENT", "SafeBundle", "build_bundle",
           "BundleLeak", "SHARED_SEMANTICS_PATH"]

#: The surface-independent semantics every candidate must express. Carried by VALUE, not
#: as a path: the previous pointer named `MODEL_FILES/SHARED_HML_SEMANTICS.md`, which does
#: not exist in this repository, so the bundle promised a glossary it could not deliver.
SHARED_SEMANTICS_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "evaluation" /
    "model_files" / "SHARED_HML_SEMANTICS.md"
)


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
        "shared_semantics": SHARED_SEMANTICS_PATH.read_text(),
        "surface_specification": surface,
        # A demonstration must show the MAPPING, not just the output notation. Rendering
        # only the encoding exhibits the syntax and leaves the model to guess how a view
        # becomes one -- that measures guessing, not translation.
        "demonstrations": [
            {"task_id": d.task_id, "view": encoding_view(d),
             "rendering": render_surface(d, surface)}
            for d in demonstrations
        ],
        # The ORDERED view (D-030). `structured_target()` is the superseded bucketed form:
        # it is order-free while `content_hash` is order-sensitive, and it drops
        # `check` statements outright. Serving it here would have rebuilt, inside the
        # "model-safe" bundle, the exact defect that invalidated the previous tranche.
        "structured_target": encoding_view(task),
        "prose": render_prose(task),
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

    # Whole-rendering containment misses a SINGLE leaked line, and one line of surface A
    # is one statement of the answer. `derived_from` reached prose verbatim and did
    # exactly that. Short lines are skipped: a bare `var p : Bool` is generic enough that
    # matching it would fire on unrelated demonstration text.
    #
    # Surface D is excluded, and not as a convenience: its notation IS the JSON the
    # ordered view is written in, so `"module": "X",` occurs in both by construction. A
    # per-line check there reports a leak on every task and would be switched off, taking
    # the A/B/C check -- which does work -- with it.
    for name in ("A_v0_labelled_linear", "B_v1_labelled_linear_simplified",
                 "C_prefix_sexpr"):
        for line in render_surface(task, name).splitlines():
            stripped = _normalise(line)
            if len(stripped) >= 12 and stripped in blob:
                raise BundleLeak(
                    f"a line of the task's own {name} reference appears in the bundle: "
                    f"{stripped!r}")

    for token in (task.canonical_hash(), task.semantic_identity()):
        if token in blob:
            raise BundleLeak("an expected hash appears in the bundle")

    for word in FORBIDDEN_CONTENT:
        if word in blob.lower():
            raise BundleLeak(f"forbidden term {word!r} appears in the bundle")

    part_hashes = {k: _sha(v) for k, v in parts.items()}
    return SafeBundle(task.task_id, surface, parts, part_hashes, _sha(parts))
