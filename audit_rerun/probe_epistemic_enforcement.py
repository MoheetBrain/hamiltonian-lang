"""Executed probes for the EPISTEMIC_STATE_MATRIX and for the inference-rule catalogue.

Like the transformation matrix, `EPISTEMIC_STATE_MATRIX.csv` was **hand-authored** in
`tools/build_hml_matrices.py`: the 13 rows, the `expressible` column and the `enforced_by`
column are all literals. The 8/13 and 5/13 headline figures were never computed from a
probe. This file computes them.

EXPRESSIBLE  the state's surface form compiles clean.  (This half was in fact backed by the
             executed EPI.* probes in probe_epistemic_extensibility.py; it is recomputed
             here so both halves come from one place.)
ENFORCED     something observably breaks when the state is misused.  Each state gets a
             specific falsifier: a program that SHOULD be rejected if the state carries
             semantic weight, and is accepted if the keyword is decoration.  "Enforced"
             requires the falsifier to be rejected.

Also runs every rule in the closed inference catalogue with a correct step and a
deliberately broken variant, which is the direct evidence for MATURITY_LADDER 3.5.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SRC = os.environ.get("HML_PROBE_SRC")
if _SRC:
    sys.path.insert(0, _SRC)

import hamiltonian_lang as H  # noqa: E402

M = "module M\n"


def compile_ok(src: str) -> tuple[bool, list[str]]:
    try:
        r = H.compile_source(src, "<probe>")
    except Exception as e:  # noqa: BLE001
        return False, [f"CRASH {type(e).__name__}: {e}"]
    return bool(r.ok()), list(r.diagnostics.codes())


#: state -> (expressibility specimen, falsifier that MUST be rejected if the state is
#:           enforced, what the falsifier means)
#: States whose specimen COMPILES but does not express the state.  Recording them as
#: expressible would be a false positive of exactly the kind the original audit warned
#: about, so they are forced to NO with the reason stated in the row.
_FORCE_NOT_EXPRESSIBLE = {"UNCERTAIN"}

STATES: dict[str, tuple[str, str | None, str]] = {
    "DECLARED": (
        M + "var x : Real",
        M + "var x : Real\nconst n : Natural = x",
        "a declared symbol's type must constrain its uses",
    ),
    "DEFINED": (
        M + "const c : Real = 2.0\ndef d := c + 1.0",
        M + "const c : Real = 2.0\nconst c : Real = 3.0",
        "a definition must be unique",
    ),
    "ASSUMED": (
        M + "var x : Real\nassume x > 0.0",
        M + "var x : Real\nassume a0 : x > 0.0\nvar k : Real\n"
        "assume a1 : k = 2.0 * x\nderive d1 : k / x = 2.0 * x / x from a1 "
        "by divide_both_sides(by := x)\ngoal g : k / x = 2.0 * x / x\nproved g by d1",
        "ENFORCEMENT TEST IS INVERTED HERE: this program must be ACCEPTED, because an "
        "assumption that discharges the x != 0 obligation is the only way the goal can "
        "reach PROVED. Scored separately below.",
    ),
    "REQUIRED": (
        M + "var x : Real\nrequire x > 0.0",
        M + "require 1.0 = 2.0",
        "a false requirement should not pass silently if `require` is load-bearing",
    ),
    "OBSERVED": (
        M + "obs n : Natural = 10",
        M + "obs n : Natural = 10\nparam k : Natural\ndef total := n + k",
        "mixing observed data with an unknown parameter -- accepting this is arguably "
        "CORRECT, so a PASS here is not evidence of enforcement either way",
    ),
    "PARAMETER": (
        M + "param theta : Probability",
        M + "param theta : Probability\ninfer posterior theta",
        "a posterior for a symbol with no law must be rejected (HML-S604)",
    ),
    "GOAL": (
        # `prove` is the form BOTH trees have; using v2-only `goal` here would measure the
        # keyword rather than the epistemic state.
        M + "prove forall x : Real . x = x",
        # The falsifier must be writable in BOTH trees or it measures the keyword, not
        # the state.  `prove` is v1's goal form and v2 retains it.
        M + "prove 1.0 = 2.0",
        "a false goal must not pass silently if the goal state is load-bearing",
    ),
    "OBJECTIVE": (
        M + "param x : Real\ndef f := x * x\nminimise f",
        M + "param x : Real\nminimise undeclared_thing",
        "an objective over an unresolved name must be rejected",
    ),
    "CONJECTURED": (M + "conjecture forall x : Real . x = x", None, "state absent"),
    "REFUTED": (M + "refute forall x : Real . x > 0.0", None, "state absent"),
    "APPROXIMATE": (M + "const pi_a : Real ~= 3.14159", None, "state absent"),
    "UNCERTAIN": (
        M + "const m : Real = 9.81 +- 0.02",
        None,
        "state absent: this COMPILES, but it parses as 9.81 + (-0.02) and therefore "
        "expresses subtraction, not uncertainty. Forced to NO.",
    ),
    "PROHIBITED_ASSUMPTION": (
        M + "var x : Real\nprohibit assume x > 0.0", None, "state absent"
    ),
}

PRELUDE = "module M\nvar x : Real\nvar y : Real\nvar k : Real\nvar z : Real\nvar w : Real\n"

#: rule -> (correct step, broken step)
RULE_CASES: dict[str, tuple[str, str]] = {
    "symmetry": (
        "assume a1 : y = 2.0 * x\nderive d : 2.0 * x = y from a1 by symmetry\n",
        "assume a1 : y = 2.0 * x\nderive d : 3.0 * x = y from a1 by symmetry\n",
    ),
    "transitivity": (
        "assume a1 : y = 2.0 * x\nassume a2 : 2.0 * x = k\n"
        "derive d : y = k from a1, a2 by transitivity\n",
        "assume a1 : y = 2.0 * x\nassume a2 : 2.0 * x = k\n"
        "derive d : y = z from a1, a2 by transitivity\n",
    ),
    "add_both_sides": (
        "assume a1 : y = 2.0 * x\n"
        "derive d : y + 1.0 = 2.0 * x + 1.0 from a1 by add_both_sides(by := 1.0)\n",
        "assume a1 : y = 2.0 * x\n"
        "derive d : y + 1.0 = 2.0 * x + 9.0 from a1 by add_both_sides(by := 1.0)\n",
    ),
    "subtract_both_sides": (
        "assume a1 : y = 2.0 * x\n"
        "derive d : y - 1.0 = 2.0 * x - 1.0 from a1 by subtract_both_sides(by := 1.0)\n",
        "assume a1 : y = 2.0 * x\n"
        "derive d : y - 1.0 = 2.0 * x - 9.0 from a1 by subtract_both_sides(by := 1.0)\n",
    ),
    "multiply_both_sides": (
        "assume a1 : y = 2.0 * x\n"
        "derive d : y * 3.0 = 2.0 * x * 3.0 from a1 by multiply_both_sides(by := 3.0)\n",
        "assume a1 : y = 2.0 * x\n"
        "derive d : y * 3.0 = 2.0 * x * 9.0 from a1 by multiply_both_sides(by := 3.0)\n",
    ),
    "divide_both_sides": (
        "assume a0 : k != 0.0\nassume a1 : y = 2.0 * x\n"
        "derive d : y / k = 2.0 * x / k from a1 by divide_both_sides(by := k)\n",
        "assume a0 : k != 0.0\nassume a1 : y = 2.0 * x\n"
        "derive d : y / k = 2.0 * x from a1 by divide_both_sides(by := k)\n",
    ),
    "substitute": (
        "assume a1 : y = 2.0 * x\nassume a2 : z = y + k\n"
        "derive d : z = 2.0 * x + k from a1, a2 by substitute\n",
        "assume a1 : y = 2.0 * x\nassume a2 : z = y + k\n"
        "derive d : z = 2.0 * x + 99.0 from a1, a2 by substitute\n",
    ),
    "congruence": (
        "assume a1 : y = 2.0 * x\n"
        "derive d : exp(y) = exp(2.0 * x) from a1 by congruence(fn := exp)\n",
        "assume a1 : y = 2.0 * x\n"
        "derive d : exp(y) = exp(3.0 * x) from a1 by congruence(fn := exp)\n",
    ),
    "modus_ponens": (
        "assume a1 : x > 0.0\nassume a2 : x > 0.0 implies y > 0.0\n"
        "derive d : y > 0.0 from a1, a2 by modus_ponens\n",
        "assume a1 : x > 0.0\nassume a2 : x > 0.0 implies y > 0.0\n"
        "derive d : y > 1.0 from a1, a2 by modus_ponens\n",
    ),
    "modus_tollens": (
        "assume a1 : x > 0.0 implies y > 0.0\nassume a2 : not (y > 0.0)\n"
        "derive d : not (x > 0.0) from a2, a1 by modus_tollens\n",
        "assume a1 : x > 0.0 implies y > 0.0\nassume a2 : not (y > 0.0)\n"
        "derive d : not (x > 1.0) from a2, a1 by modus_tollens\n",
    ),
    "and_intro": (
        "assume a1 : x > 0.0\nassume a2 : y > 0.0\n"
        "derive d : x > 0.0 and y > 0.0 from a1, a2 by and_intro\n",
        "assume a1 : x > 0.0\nassume a2 : y > 0.0\n"
        "derive d : x > 0.0 and y > 1.0 from a1, a2 by and_intro\n",
    ),
    "and_elim_left": (
        "assume a1 : x > 0.0 and y > 0.0\nderive d : x > 0.0 from a1 by and_elim_left\n",
        "assume a1 : x > 0.0 and y > 0.0\nderive d : y > 0.0 from a1 by and_elim_left\n",
    ),
    "and_elim_right": (
        "assume a1 : x > 0.0 and y > 0.0\nderive d : y > 0.0 from a1 by and_elim_right\n",
        "assume a1 : x > 0.0 and y > 0.0\nderive d : x > 0.0 from a1 by and_elim_right\n",
    ),
    "weaken_inequality": (
        "assume a1 : x > 0.0\nderive d : x >= 0.0 from a1 by weaken_inequality\n",
        "assume a1 : x >= 0.0\nderive d : x > 0.0 from a1 by weaken_inequality\n",
    ),
    # arity 1 with a `by` parameter: a < b |- a + k < b + k.  The first draft of this
    # probe treated it as "add two inequalities" and scored it REJECTED; that was a
    # probe-authoring error, corrected against the rule's own `shape` string.
    "add_inequality": (
        "assume a1 : x < y\nderive d : x + k < y + k from a1 by add_inequality(by := k)\n",
        "assume a1 : x < y\nderive d : x + k > y + k from a1 by add_inequality(by := k)\n",
    ),
    "multiply_inequality": (
        "assume a0 : k > 0.0\nassume a1 : x < y\n"
        "derive d : x * k < y * k from a1 by multiply_inequality(by := k)\n",
        "assume a0 : k > 0.0\nassume a1 : x < y\n"
        "derive d : x * k > y * k from a1 by multiply_inequality(by := k)\n",
    ),
}


def _status(src: str, label: str = "d") -> tuple[bool, list[str], str | None]:
    try:
        r = H.compile_source(PRELUDE + src, "<probe>")
    except Exception as e:  # noqa: BLE001
        return False, [f"CRASH {type(e).__name__}: {e}"], None
    st = None
    try:
        from hamiltonian_lang.ast.nodes import DeriveStmt

        for s in r.module.statements:
            if isinstance(s, DeriveStmt) and s.label == label:
                st = str(s.status)
    except Exception:  # noqa: BLE001
        st = None
    return bool(r.ok()), list(r.diagnostics.codes()), st


def main() -> int:
    rows = []
    for state, (spec, falsifier, meaning) in STATES.items():
        ok, codes = compile_ok(spec)
        if state in _FORCE_NOT_EXPRESSIBLE:
            ok = False
        row = {
            "state": state,
            "expressible": "YES" if ok else "NO",
            "expressibility_codes": codes,
            "falsifier": falsifier,
            "falsifier_meaning": meaning,
        }
        if not ok:
            # Enforcement of a state the language cannot state is not a meaningful
            # question, and scoring it YES because the falsifier failed at the PARSER
            # would credit the language for a keyword it does not have.
            row["enforced"] = "N/A (not expressible)"
        elif falsifier is None:
            row["enforced"] = "NOT_MEASURED"
        else:
            fok, fcodes = compile_ok(falsifier)
            row["falsifier_accepted"] = fok
            row["falsifier_codes"] = fcodes
            if state == "ASSUMED":
                # inverted: the program must be ACCEPTED for the assumption to be
                # load-bearing inside the kernel
                row["enforced"] = "YES (kernel only)" if fok else "NO"
            elif state == "OBSERVED":
                row["enforced"] = "INCONCLUSIVE"
            else:
                row["enforced"] = "NO" if fok else "YES"
        rows.append(row)

    # Outside the fixed 13-state denominator: the v2-only goal/derive/proved path.
    # Reported separately so it cannot inflate the epistemic-state figures.
    extra = {}
    for name, src, must_be_rejected in (
        (
            "GOAL_VIA_PROVED_false_step",
            M + "var x : Real\nvar y : Real\nassume a1 : y = 2.0 * x\n"
            "derive d1 : y = 2.0 * x + 1.0 from a1 by symmetry\n"
            "goal g : y = 2.0 * x + 1.0\nproved g by d1",
            True,
        ),
        (
            "GOAL_VIA_PROVED_open_obligation",
            M + "var x : Real\nvar y : Real\nvar k : Real\nassume a1 : y = 2.0 * x\n"
            "derive d1 : y / k = 2.0 * x / k from a1 by divide_both_sides(by := k)\n"
            "goal g : y / k = 2.0 * x / k\nproved g by d1",
            True,
        ),
        (
            "GOAL_VIA_PROVED_sound_step",
            M + "var x : Real\nvar y : Real\nassume a1 : y = 2.0 * x\n"
            "derive d1 : 2.0 * x = y from a1 by symmetry\n"
            "goal g : 2.0 * x = y\nproved g by d1",
            False,
        ),
        (
            "GOAL_IS_NOT_ITS_OWN_PREMISE",
            M + "var x : Real\nvar y : Real\ngoal g : y = 2.0 * x\n"
            "derive d1 : 2.0 * x = y from g by symmetry\nproved g by d1",
            True,
        ),
        ("PROVE_STILL_PROVES_NOTHING", M + "prove 1.0 = 2.0", True),
    ):
        ok, codes = compile_ok(src)
        extra[name] = {
            "source": src,
            "accepted": ok,
            "codes": codes,
            "expected_rejected": must_be_rejected,
            "behaves_as_required": (not ok) if must_be_rejected else ok,
        }

    rule_rows = []
    try:
        from hamiltonian_lang.reasoning import kernel as K

        catalogue = sorted(K.RULES)
    except Exception:  # noqa: BLE001
        catalogue = []
    for rule in sorted(RULE_CASES):
        gok, gcodes, gst = _status(RULE_CASES[rule][0])
        bok, bcodes, bst = _status(RULE_CASES[rule][1])
        rule_rows.append(
            {
                "rule": rule,
                "in_catalogue": rule in catalogue,
                "correct_ok": gok,
                "correct_status": gst,
                "correct_codes": gcodes,
                "broken_ok": bok,
                "broken_status": bst,
                "broken_codes": bcodes,
                "sound_check": (gst == "VERIFIED" and not bok),
            }
        )

    expressible = sum(1 for r in rows if r["expressible"] == "YES")
    enforced = sum(1 for r in rows if str(r["enforced"]).startswith("YES"))
    sound = sum(1 for r in rule_rows if r["sound_check"])

    out = Path(__file__).resolve().parent / "results" / (
        f"EPISTEMIC_{os.environ.get('HML_RUN_LABEL', 'unlabelled')}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "summary": {
                    "src": H.__file__,
                    "expressible": f"{expressible}/{len(rows)}",
                    "enforced": f"{enforced}/{len(rows)}",
                    "rules_in_catalogue": len(catalogue),
                    "rules_probed": len(rule_rows),
                    "rules_passing_sound_check": sound,
                    "catalogue": catalogue,
                },
                "states": rows,
                "v2_only_reasoning_path": extra,
                "rules": rule_rows,
            },
            indent=2,
        )
    )

    print(f"src = {H.__file__}")
    print(f"{'state':24s} {'EXPR':5s} {'ENFORCED':22s} falsifier codes")
    print("-" * 100)
    for r in rows:
        print(
            f"{r['state']:24s} {r['expressible']:5s} {str(r['enforced']):22s} "
            f"{','.join(r.get('falsifier_codes') or []) or '-'}"
        )
    print(f"\nexpressible {expressible}/{len(rows)} · enforced {enforced}/{len(rows)}")
    print("\nv2-only goal/derive/proved path (outside the 13-state denominator):")
    for k, v in extra.items():
        print(f"  {k:36s} accepted={str(v['accepted']):5s} "
              f"as_required={str(v['behaves_as_required']):5s} {','.join(v['codes']) or '-'}")
    print(f"\ninference rules in catalogue: {len(catalogue)}")
    if rule_rows:
        print(f"{'rule':22s} {'correct':10s} {'broken_rejected':16s} SOUND?")
        for r in rule_rows:
            print(
                f"{r['rule']:22s} {str(r['correct_status']):10s} "
                f"{str(not r['broken_ok']):16s} {'YES' if r['sound_check'] else 'NO'}"
            )
        print(f"\nrules passing accept-correct + reject-broken: {sound}/{len(rule_rows)}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
