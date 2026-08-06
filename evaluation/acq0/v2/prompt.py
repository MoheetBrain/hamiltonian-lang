"""The frozen ACQ0 v2 prompt assembly. One builder, used by the probe and the run.

If the probe measured a different string from the one sent, the budget would be a fiction.
That is the v1 failure -- the 5,893-token figure was measured on legacy material and
carried forward as though it described the real curriculum.

Two properties of the demonstrations are deliberate.

**They are not corpus tasks.** Drawing demonstrations from the scored corpus would show a
model the exact answer to task 1 while it encodes task 2, and would hand a demo task fewer
demonstrations than a non-demo task. These four modules are authored here, are never
scored, and duplicate no scored task's mathematics.

**They show the MAPPING, not just the notation.** Each demonstration prints the ordered
view *and* its encoding. Rendering only the encoding exhibits the syntax and leaves the
model to infer how a view becomes one, which measures inference rather than translation --
and would penalise whichever surface is least guessable rather than least expressive.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from evaluation.corpus_governance.v2_render import acq0_view
from evaluation.corpus_governance.v2_view import statement_records
from evaluation.syntax_gate import prompts as _spec

__all__ = ["DEMONSTRATIONS", "build_prompt", "prompt_hash", "COMPLETION_ALLOWANCE",
           "SAFETY_RESERVE", "SLOT_CONTEXT", "CEILING", "Demonstration",
           "demonstration_block"]


@dataclass(frozen=True)
class Demonstration:
    """A worked example: authored HML source, never a scored task."""

    name: str
    source: str


#: Four demonstrations, in frozen order. Between them they exercise every statement kind
#: the corpus uses -- declarations with and without initialisers, a definition, `require`
#: and `assume`, a prior/likelihood pair with named roles and a conditioning set, and a
#: dimension check -- while duplicating no scored task's mathematics.
DEMONSTRATIONS: tuple[Demonstration, ...] = (
    Demonstration("DemoBinding",
                  "module DemoBinding\n"
                  "const a : Real = 2\n"
                  "var b : Real\n"
                  "def c : Real := a + b\n"),
    Demonstration("DemoConstraint",
                  "module DemoConstraint\n"
                  "var t : PositiveReal\n"
                  "require t < 10\n"
                  "assume t > 1\n"),
    Demonstration("DemoLaw",
                  "module DemoLaw\n"
                  "param sigma : PositiveReal\n"
                  "prior sigma ~ Exponential(rate := 1)\n"
                  "obs y : Real = 3\n"
                  "likelihood y | sigma ~ Normal(location := 0, scale := sigma)\n"),
    Demonstration("DemoDimension",
                  "module DemoDimension\n"
                  "var length : Quantity[Length]\n"
                  "var width : Quantity[Length]\n"
                  "def area : Quantity[Length^2] := length * width\n"
                  "check dimension area = Length^2\n"),
)

COMPLETION_ALLOWANCE = 6144
SAFETY_RESERVE = 256
SLOT_CONTEXT = 16384          # 2 slots x 16384; the server is fixed at -c 32768 -np 2
CEILING = SLOT_CONTEXT - COMPLETION_ALLOWANCE - SAFETY_RESERVE   # 9984


def demonstration_block(demo: Demonstration, surface: str) -> str:
    """One input/output pair: the view the model would be given, and the answer."""
    from evaluation.corpus_governance.v2_render import render_surface_source

    from hamiltonian_lang import compile_source

    result = compile_source(demo.source, f"<demo:{demo.name}>")
    if not result.ok():
        raise RuntimeError(
            f"demonstration {demo.name} does not compile: "
            f"{[d.code for d in result.diagnostics.errors]}")
    view = {"module": result.module.name,
            "encoding_statements": statement_records(result.module, demo.name)}
    return (f"--- {demo.name} ---\n"
            f"GIVEN:\n{json.dumps(view, indent=2)}\n"
            f"ENCODING:\n{render_surface_source(demo.source, surface)}")


def build_prompt(task, surface: str) -> str:
    """Exactly what is sent. No hidden material: no reference, no hash, no answer key."""
    view = acq0_view(task)
    demos = "\n\n".join(demonstration_block(d, surface) for d in DEMONSTRATIONS)
    return (
        f"{view['instruction']}\n\n"
        f"=== SURFACE SPECIFICATION ===\n{_spec.render_spec(surface)}\n\n"
        f"=== DEMONSTRATIONS ===\n{demos}\n\n"
        f"=== TASK ===\n{view['prose']}\n\n"
        f"STRUCTURED TARGET:\n{json.dumps(view['structured_target'], indent=2)}\n\n"
        f"Output only the encoding in the assigned surface.\n"
    )


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
