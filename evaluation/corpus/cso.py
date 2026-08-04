"""Canonical Semantic Object — the single source each arm is rendered from.

HML-EVAL-001 §4. A problem is authored **once**, as structure. Every arm is a
projection of that structure. Authoring five prose variants by hand is how information
asymmetry creeps in without anyone deciding to introduce it.

The scoring contract, which is what keeps the primary metric free of model judgement:

* every arm is asked the **same question** and must emit the answer in the **same
  machine-checkable form**, so final-answer accuracy is deterministic everywhere;
* arms whose output is a formal representation (Hamiltonian, Stan/Lean) are
  *additionally* scored on semantic-encoding accuracy against ``semantics`` below.

Nothing here calls a model. This module defines what is true about a problem.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

__all__ = [
    "AnswerSpec",
    "SemanticFacts",
    "CanonicalSemanticObject",
    "AnswerKind",
    "check_answer",
    "normalise_answer",
]

AnswerKind = Literal["numeric", "exact_string", "choice", "dimension", "role_map", "boolean"]

#: The literal marker every arm must wrap its final answer in. Identical across arms so
#: that extraction is not itself an arm-dependent variable.
ANSWER_OPEN = "<ANSWER>"
ANSWER_CLOSE = "</ANSWER>"


@dataclass
class AnswerSpec:
    """The verified answer and how to check a candidate against it deterministically."""

    kind: AnswerKind
    value: Any
    tolerance: float = 1e-6
    options: list[str] = field(default_factory=list)
    #: why this is the answer -- recorded so a wrong ground truth is auditable
    justification: str = ""

    def render_instruction(self) -> str:
        if self.kind == "numeric":
            return (
                f"a single number (no units, no thousands separators), "
                f"e.g. {ANSWER_OPEN}3.25{ANSWER_CLOSE}"
            )
        if self.kind == "boolean":
            return f"exactly TRUE or FALSE, e.g. {ANSWER_OPEN}TRUE{ANSWER_CLOSE}"
        if self.kind == "choice":
            opts = " or ".join(self.options)
            return f"exactly one of {opts}, e.g. {ANSWER_OPEN}{self.options[0]}{ANSWER_CLOSE}"
        if self.kind == "dimension":
            return (
                "the physical dimension as a product of the base dimensions Mass, Length, "
                "Time, Temperature, Current, Amount, Luminosity using * / and ^, "
                f"e.g. {ANSWER_OPEN}Mass * Length^2 / Time^2{ANSWER_CLOSE}"
            )
        if self.kind == "role_map":
            return (
                "a JSON object mapping each parameter role to the symbol filling it, "
                f'e.g. {ANSWER_OPEN}{{"location": "mu", "scale": "sigma"}}{ANSWER_CLOSE}'
            )
        return f"a short exact string, e.g. {ANSWER_OPEN}sigma{ANSWER_CLOSE}"


@dataclass
class SemanticFacts:
    """Ground truth about the problem's structure.

    Used for semantic-encoding accuracy (§8) and never shown to the model in any arm.
    """

    entities: dict[str, str] = field(default_factory=dict)          # name -> HML type
    declaration_kinds: dict[str, str] = field(default_factory=dict)  # name -> param/obs/...
    laws: dict[str, dict[str, str]] = field(default_factory=dict)    # target -> {role: symbol}
    law_families: dict[str, str] = field(default_factory=dict)       # target -> family
    conditioning: dict[str, list[str]] = field(default_factory=dict)  # target -> given
    constraints: list[str] = field(default_factory=list)
    quantifier_order: list[str] = field(default_factory=list)        # ["forall x", "exists y"]
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    objective: str | None = None
    dimensions: dict[str, str] = field(default_factory=dict)         # name -> dimension
    prohibited_assumptions: list[str] = field(default_factory=list)


@dataclass
class CanonicalSemanticObject:
    id: str
    domain: str
    difficulty: Literal["easy", "medium", "hard"]

    #: The mathematical content, in neutral prose. Identical across arms by construction:
    #: every arm receives this exact string.
    prose: str
    #: The question asked. Identical across arms.
    question: str

    answer: AnswerSpec
    semantics: SemanticFacts

    assumptions: list[str] = field(default_factory=list)
    valid_transformations: list[str] = field(default_factory=list)
    #: What a careless reader concludes. Used to classify near-miss failures.
    distractors: list[str] = field(default_factory=list)
    #: The reference Hamiltonian encoding. Ground truth for §8; never shown to the model.
    reference_hml: str = ""
    #: Deliberate, unavoidable differences between arms, recorded per §4.
    information_asymmetry: list[str] = field(default_factory=list)
    generator: str = ""
    seed: int | None = None
    corpus_version: str = "eval001-v1"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=True)

    @staticmethod
    def from_dict(d: dict) -> CanonicalSemanticObject:
        d = dict(d)
        d["answer"] = AnswerSpec(**d["answer"])
        d["semantics"] = SemanticFacts(**d["semantics"])
        return CanonicalSemanticObject(**d)


# ---------------------------------------------------------------------------
# Deterministic answer checking
# ---------------------------------------------------------------------------

_DIM_TOKEN = re.compile(r"([A-Za-z]+)(?:\^(-?\d+(?:/\d+)?))?")


def _parse_dimension(text: str) -> dict[str, float] | None:
    """Parse a dimension expression into an exponent map, so that
    'Mass * Length^2 / Time^2' and 'Length^2 * Mass / Time^2' compare equal."""
    from fractions import Fraction

    text = text.strip().replace("·", "*").replace("×", "*")
    if not text:
        return None
    if text.lower() in ("dimensionless", "1", "none"):
        return {}
    exps: dict[str, Fraction] = {}
    sign = 1
    # split on * and / while remembering which
    parts = re.split(r"([*/])", text)
    for tok in parts:
        tok = tok.strip()
        if not tok:
            continue
        if tok == "*":
            sign = 1
            continue
        if tok == "/":
            sign = -1
            continue
        m = _DIM_TOKEN.fullmatch(tok.replace(" ", ""))
        if not m:
            return None
        name, exp = m.group(1), m.group(2)
        name = name.capitalize()
        if name not in (
            "Mass", "Length", "Time", "Temperature", "Current", "Amount", "Luminosity"
        ):
            return None
        e = Fraction(exp) if exp else Fraction(1)
        exps[name] = exps.get(name, Fraction(0)) + sign * e
    return {k: float(v) for k, v in exps.items() if v != 0}


def normalise_answer(raw: str) -> str:
    """Extract the answer from the mandated markers, tolerating common wrappers."""
    if raw is None:
        return ""
    text = raw.strip()
    m = re.search(
        re.escape(ANSWER_OPEN) + r"(.*?)" + re.escape(ANSWER_CLOSE), text, re.S | re.I
    )
    if m:
        text = m.group(1)
    else:
        # A model that omits the closing marker is still scored on what follows the open
        # marker, so formatting compliance is measured separately from correctness.
        m2 = re.search(re.escape(ANSWER_OPEN) + r"(.*)", text, re.S | re.I)
        if m2:
            text = m2.group(1)
    text = text.strip()
    # strip code fences and surrounding maths delimiters
    text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text).strip()
    text = text.strip("`").strip()
    text = re.sub(r"^\$+|\$+$", "", text).strip()
    return text


def check_answer(spec: AnswerSpec, raw: str) -> tuple[bool, str]:
    """Return (correct, normalised_form). Never calls a model."""
    text = normalise_answer(raw)
    if not text:
        return False, ""

    if spec.kind == "numeric":
        m = re.search(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text.replace(",", ""))
        if not m:
            return False, text
        try:
            got = float(m.group(0))
        except ValueError:
            return False, text
        want = float(spec.value)
        tol = max(spec.tolerance, abs(want) * spec.tolerance)
        return abs(got - want) <= tol, str(got)

    if spec.kind == "boolean":
        t = text.strip().upper()
        t = re.sub(r"[^A-Z]", "", t)[:5]
        if t.startswith("TRUE"):
            return bool(spec.value) is True, "TRUE"
        if t.startswith("FALSE"):
            return bool(spec.value) is False, "FALSE"
        return False, text

    if spec.kind == "choice":
        t = text.strip().upper()
        hits = [o for o in spec.options if re.search(rf"\b{re.escape(o.upper())}\b", t)]
        if len(hits) != 1:
            return False, text
        return hits[0] == str(spec.value), hits[0]

    if spec.kind == "dimension":
        got = _parse_dimension(text)
        want = _parse_dimension(str(spec.value))
        if got is None or want is None:
            return False, text
        return got == want, str(sorted(got.items()))

    if spec.kind == "role_map":
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.S)
            if not m:
                return False, text
            try:
                obj = json.loads(m.group(0))
            except json.JSONDecodeError:
                return False, text
        if not isinstance(obj, dict):
            return False, text
        got = {str(k).strip().lower(): str(v).strip() for k, v in obj.items()}
        want = {str(k).strip().lower(): str(v).strip() for k, v in spec.value.items()}
        return got == want, json.dumps(got, sort_keys=True)

    got_s = re.sub(r"\s+", " ", text).strip().rstrip(".")
    want_s = re.sub(r"\s+", " ", str(spec.value)).strip().rstrip(".")
    return got_s.lower() == want_s.lower(), got_s
