# Red-Team V2 — the reasoning kernel

**Status:** measured, not estimated. Every row was produced by running the command shown
against the pinned V2 build and pasting the real output.

| Field | Value |
| --- | --- |
| Target commit | `7a98427b634d296b4ca04f000ce6c0c3813f6eff` (`feature/hml-reasoning-kernel-v2`) |
| Baseline for comparison | `3dd4216` (see `RED_TEAM_BASELINE.md`) |
| Interpreter | Python 3.14.6 (`/Users/moheet/hml_v2_worktree/.venv`) |
| Date measured | 2026-08-07 |
| Attacks attempted | 30 |
| **Attacks that SUCCEED** | **8** |
| Attacks BLOCKED | 22 |
| — of which CRITICAL soundness | **4** (one shared root cause, one-line fix) |

> **Verdict: BLOCKER.** A false conclusion reaches `VERIFIED`, and a false goal reaches
> `PROVED`, on a module that compiles with **zero errors and zero warnings**. The trusted
> kernel is not at fault — it is correct on every attack thrown at it. The hole is in the
> premise-supply path in `reasoning/check.py`, which admits three statement kinds that
> assert nothing.

---

## 0. Reproducing this run

The tree was clean at `7a98427` when measurement began, but a second agent is landing
expression work on the same branch. Every result below was therefore taken against a
pinned `git archive` export, exactly as in the Phase 1 baseline.

```sh
SNAP2=/tmp/hml_v2_snapshot
RT=/tmp/hml_redteam/v2
rm -rf "$SNAP2" && mkdir -p "$SNAP2" "$RT"
git -C /Users/moheet/hml_v2_worktree archive 7a98427 | tar -x -C "$SNAP2"

cat > /tmp/hmlv2 <<EOF
#!/bin/sh
PYTHONPATH=$SNAP2/src exec /Users/moheet/hml_v2_worktree/.venv/bin/python -m hamiltonian_lang.cli "\$@"
EOF
chmod +x /tmp/hmlv2
```

Confirm the snapshot is the V2 build:

```
$ grep -o '"derive", "goal", "proved", "from", "by"' $SNAP2/src/hamiltonian_lang/lexer/__init__.py
"derive", "goal", "proved", "from", "by"
```

### The `verdict.py` harness — required, because the CLI shows none of this

`hml check` does not print derivation status, goal status, or reasoning obligations
(finding **R-06**). Reaching the verdicts at all requires the API:

```python
# $RT/verdict.py
import sys
from hamiltonian_lang import compile_source
path = sys.argv[1]
r = compile_source(open(path).read(), path)
print(f"compile ok : {r.ok()}   errors={len(r.diagnostics.errors)} warnings={len(r.diagnostics.warnings)}")
if r.diagnostics.items:
    print(r.diagnostics.render())
rr = r.reasoning
if rr is None:
    print("reasoning stage DID NOT RUN"); sys.exit(0)
print("derivation_status :", rr.derivation_status)
print("goal_status       :", rr.goal_status)
print("VERIFIED          :", rr.verified())
print("obligations       :")
for o in rr.obligations:
    print("   ", o.to_dict())
```

Run as `PYTHONPATH=$SNAP2/src .venv/bin/python $RT/verdict.py <file>`.

Throughout, `$HMLV2` = `/tmp/hmlv2`, `$V` = the venv interpreter, `$RT` = the probe dir.

---

## 1. Findings table

Severity: **CRITICAL** = a false statement reaches a certified status · **HIGH** = the
tool's authoritative output misrepresents what it checked · **MEDIUM** = correct input
wrongly rejected, or a claimed invariant is looser than stated · **LOW** = footgun.

| ID | Attack | Command | Verdict | Sev | What a fix requires |
| --- | --- | --- | --- | --- | --- |
| **R-01** | `prove` used as a derivation premise → VERIFIED + PROVED on a false conclusion | `$V $RT/verdict.py $RT/V1_prove_as_premise.hml` | **EXPLOIT SUCCEEDS** | **CRITICAL** | Do not write `RequireStmt`/`ProveStmt` into `self.propositions`. They assert nothing. |
| **R-02** | `require` used as a derivation premise | `$V $RT/verdict.py $RT/V2_require_as_premise.hml` | **EXPLOIT SUCCEEDS** | **CRITICAL** | Same one-line fix as R-01. |
| **R-03** | `goal` used as a premise — assume the conclusion, launder into a second goal | `$V $RT/verdict.py $RT/V3_goal_as_premise.hml` | **EXPLOIT SUCCEEDS** | **CRITICAL** | Do not write `GoalStmt` into `self.propositions`; a goal is a target, not a fact. |
| **R-04** | Self-proving goal: `goal → derive → derive → proved` closes a cycle the forward-reference rule cannot see | `$V $RT/verdict.py $RT/V4_self_proving_goal.hml` | **EXPLOIT SUCCEEDS** | **CRITICAL** | R-03's fix closes it. Additionally, `proved g by d` should reject when `d` transitively rests on `g`. |
| **R-05** | `graph` / `triples` drop all three V2 nodes and report `faithful=True` | `$HMLV2 graph $RT/B1_all_v2_nodes.hml` | **EXPLOIT SUCCEEDS** | HIGH | `_graph`/`_triples` are closures, not `Backend` subclasses, so `report_reasoning_loss()` can never fire. Give `build_graph` V2 cases, or route both through `Backend`. |
| **R-06** | CLI exposes no reasoning verdict; `hml obligations` actively misreports | `$HMLV2 check`, `$HMLV2 obligations` | **EXPLOIT SUCCEEDS** | HIGH | Surface `derivation_status`, `goal_status` and the reasoning obligations; make an undischarged mandatory obligation or an `UNSUBSTANTIATED` goal affect the exit code. |
| **R-07** | Unknown rule arguments silently accepted | `$V $RT/verdict.py $RT/I2_extra_rule_arg.hml` | **EXPLOIT SUCCEEDS** | LOW | `kernel.apply` checks for *missing* params only; reject roles not in `spec.params`. |
| **R-08** | `1` and `1.0` have different `expr_identity`, so correct proofs are rejected | `$V $RT/verdict.py $RT/I1_int_float_identity.hml` | **EXPLOIT SUCCEEDS** (safe direction) | MEDIUM | `refinement.py` already treats integer and float zero as one number; `expr_identity` does not. Reconcile the two. |
| B-01 | `assume x >= 0` must not discharge `x != 0` | `$V $RT/verdict.py $RT/O1_ge_not_ne.hml` | BLOCKED | — | — |
| B-02 | `assume k = 0` must not discharge `k > 0` | `.../O2_eq_zero_not_gt.hml` | BLOCKED | — | — |
| B-03 | Disjunction must not discharge either disjunct | `.../O3_disjunction.hml` | BLOCKED | — | — |
| B-04 | Assumption under a quantifier must not leak out | `.../O4_quantified_assumption.hml` | BLOCKED | — | — |
| B-05 | `require`/`prove` must not act as *facts* for discharge | `.../O5_require_as_fact.hml` | BLOCKED | — | — |
| B-06 | Legitimate discharge must work, with provenance | `.../O6_legit_discharge.hml` | BLOCKED (works correctly) | — | — |
| B-07 | `proved` against a CHECKED (not VERIFIED) derivation | `.../P1_proved_unverified.hml` | BLOCKED — `HML-R710` | — | — |
| B-08 | `proved` where the derivation concludes something else | `.../P2_proved_wrong_conclusion.hml` | BLOCKED — `HML-R711` | — | — |
| B-09 | `proved g by <an assume>` | `.../P3_proved_by_assume.hml` | BLOCKED — `HML-R709` | — | — |
| B-10 | `proved g by <another goal>` | `.../P4_proved_by_goal.hml` | BLOCKED — `HML-R709` | — | — |
| B-11 | Mutual recursion across derivation labels | `.../C1_mutual_recursion.hml` | BLOCKED — `HML-R703` | — | — |
| B-12 | Duplicate claim label / label shadowing | `.../C2_duplicate_label.hml` | BLOCKED — `HML-R701` | — | see §5 note |
| B-13 | Derivation citing itself | `.../N1_label_shadows_value.hml` | BLOCKED — `HML-R702` | — | — |
| B-14 | Unsound step by hiding a term under a binder | `.../S1_subst_under_binder.hml` | BLOCKED — `HML-R706` | — | — |
| B-15 | Two different expressions with one `expr_identity` | `.../I3_identity_pairs.py` | BLOCKED — none found | — | — |
| B-16 | Claim-label rename changes the content hash | `$HMLV2 hash A1_label_rename_{a,b}` | BLOCKED — identical | — | — |
| B-17 | Variable rename changes hash or derivation status | `$HMLV2 hash A2_var_rename_{a,b}` | BLOCKED — identical | — | — |
| B-18 | V1 module hashes change under the V2 compiler | `hashall.py` × both snapshots | BLOCKED — 43/43 identical | — | see §6 note |
| B-19 | Surface syntax that asserts `VERIFIED` | `grep status parser/` | BLOCKED — none exists | — | — |
| B-20 | Claim label collides with a value name | `.../N1`, `.../N2` | BLOCKED — namespaces disjoint | — | — |
| B-21 | Crash / hang / no-diagnostic on adversarial input | `.../X1`–`X5` | BLOCKED — 5/5 clean | — | — |
| B-22 | `latex`/`lean`/`stan`/`sympy` silently drop V2 nodes | `backend_probe.py` | BLOCKED — all reported | — | — |

---

## 2. The critical finding: three statement kinds that assert nothing are accepted as premises

### Root cause

`reasoning/check.py:206-222`. The comment names the exact hazard and then commits it:

```python
for st in self.module.statements:
    if isinstance(st, AssumeStmt):
        # An assumption is granted, not proved: that is what `assume` means.
        self.env.assume(st.proposition, source_label=st.label)
        if st.label:
            self.propositions[st.label] = st.proposition
    elif isinstance(st, (RequireStmt, ProveStmt)):
        # `require` and `prove` state obligations; they are NOT facts, so they
        # do not enter Γ. Letting `prove P` license steps that need P is exactly
        # the circularity that makes `prove 1 = 2` look like a proof.
        if st.label:
            self.propositions[st.label] = st.proposition     # <-- the hole
    elif isinstance(st, GoalStmt):
        self.result.goal_status[st.label] = GoalStatus.OPEN
        self.propositions[st.label] = st.proposition          # <-- the hole
```

The guard was applied to the wrong channel. `require`/`prove` are correctly kept out of
**Γ** (the refinement environment, which discharges obligations) — B-05 confirms that
holds. But `self.propositions` is a *different* dict, and it is the one
`_check_derivation` reads premises from (`check.py:245-251`):

```python
premise_props: list[Expr] = []
for name in st.premises:
    prop = self.propositions.get(name)
    if prop is None:
        self._reject(st, f"premise {name!r} carries no proposition")
        return
    premise_props.append(prop)
```

So a statement that is documented as proving nothing is handed to the kernel as an
established fact. The kernel then does its job perfectly — and certifies a step built on
sand.

D-025 states the intended contract explicitly: *"`prove` keeps its v1 meaning exactly —
it states an obligation and proves nothing."* It does prove something: it proves whatever
you cite it for.

### R-01 — `prove` as premise

```
module ProveAsPremise

goal   g1 : 2.0 = 1.0
prove  p1 : 1.0 = 2.0
derive d1 : 2.0 = 1.0 from p1 by symmetry
proved g1 by d1
```

```
$ $HMLV2 check $RT/V1_prove_as_premise.hml
ok: ProveAsPremise (5 statements, 0 symbols, 1 proof obligation(s))
EXIT=0

$ $V $RT/verdict.py $RT/V1_prove_as_premise.hml
compile ok : True   errors=0 warnings=0
derivation_status : {'d1': 'VERIFIED'}
goal_status       : {'g1': 'PROVED'}
VERIFIED          : ['d1']
obligations       :
```

`2.0 = 1.0` is **PROVED**. Zero errors, zero warnings, exit 0.

### R-02 — `require` as premise

```
module RequireAsPremise
param x : Real
require r1 : x = 1.0
derive  d1 : 1.0 = x from r1 by symmetry
```
```
compile ok : True   errors=0 warnings=0
derivation_status : {'d1': 'VERIFIED'}
```

A constraint the solver is being *asked to satisfy* is consumed as a fact already
established.

### R-03 — `goal` as premise: assume the conclusion

```
module GoalAsPremise

goal   g1 : 1.0 = 2.0 and 1.0 = 2.0
derive d1 : 1.0 = 2.0 from g1 by and_elim_left
goal   g2 : 1.0 = 2.0
proved g2 by d1
```
```
compile ok : True   errors=0 warnings=0
derivation_status : {'d1': 'VERIFIED'}
goal_status       : {'g1': 'OPEN', 'g2': 'PROVED'}
```

`g1` is honestly reported OPEN — and its content is nonetheless laundered into `g2`,
which is **PROVED**. Stating a goal makes its proposition available as a premise.

### R-04 — the self-proving goal ⚑

The purest form. A goal proves itself through two derivations:

```
module SelfProvingGoal

goal   g1 : 1.0 = 2.0
derive d1 : 2.0 = 1.0 from g1 by symmetry
derive d2 : 1.0 = 2.0 from d1 by symmetry
proved g1 by d2
```
```
$ $HMLV2 check $RT/V4_self_proving_goal.hml
ok: SelfProvingGoal (5 statements, 0 symbols, 0 proof obligation(s))
EXIT=0

$ $V $RT/verdict.py $RT/V4_self_proving_goal.hml
compile ok : True   errors=0 warnings=0
derivation_status : {'d1': 'VERIFIED', 'd2': 'VERIFIED'}
goal_status       : {'g1': 'PROVED'}
VERIFIED          : ['d1', 'd2']
```

**`1.0 = 2.0` is PROVED, by itself.**

This also defeats the stated acyclicity argument. D-025 and `resolve_premises`' docstring
both claim: *"A derivation may only cite claims established earlier in the module. That
one rule gives acyclicity for free — a cycle needs a backward edge, and there are none."*

The backward edge is real and the rule does not see it, for two compounding reasons:

1. A `goal` is a claim and is textually *earlier*, so citing it is a forward edge by the
   ordering rule while being a backward edge in the justification order.
2. `proved g1 by d2` is not part of the premise graph at all — `resolve_premises` only
   walks `DeriveStmt.premises`. The edge that closes the cycle is invisible to the check
   that is supposed to guarantee no cycle exists.

Textual order is a sound acyclicity argument only if every claim in the namespace is
*established* when cited. `goal`, `require` and `prove` are not.

### The English view of R-04

```
$ $HMLV2 render -t english $RT/V4_self_proving_goal.hml
Module SelfProvingGoal.

The goal g1 is to establish that 1.0 is equal to 2.0.
Step d1: applying symmetry from g1 is claimed to give 2.0 is equal to 1.0.
Step d2: applying symmetry from d1 is claimed to give 1.0 is equal to 2.0.
The goal g1 is claimed to follow from step d2; whether it does is decided by the checker, not by this claim.
```

The prose is scrupulous — *"whether it does is decided by the checker, not by this claim"*
is exactly the right register. The problem is that the checker decided **PROVED**, and
that verdict appears in no output the CLI can produce (**R-06**). The one honest sentence
in the document defers to a verdict the reader cannot see and which is wrong.

### Why the fix is small

The kernel needs no change. Every kernel-level attack was blocked (B-14, B-15) and every
obligation-level attack was blocked (B-01…B-06). The fix is to stop populating
`self.propositions` from `RequireStmt`, `ProveStmt` and `GoalStmt`, so that citing one
falls through to the existing, already-correct refusal:

```
self._reject(st, f"premise {name!r} carries no proposition")
```

A dedicated diagnostic would be better than that generic message — the author needs to be
told *why* a `prove` cannot be a premise, not merely that it "carries no proposition".

---

## 3. R-05 — `graph` and `triples` silently drop the entire reasoning layer

The same module, all three V2 nodes present and compiling clean:

```
module AllV2Nodes
param a : Real
param b : Real
goal   g1 : b = a
assume p1 : a = b
derive d1 : b = a from p1 by symmetry
proved g1 by d1
```

```
$ $HMLV2 graph $RT/B1_all_v2_nodes.hml
sym:#0.0 -> has_type type:Real
sym:#0.0 -> declared_as declkind:param
sym:#0.1 -> has_type type:Real
sym:#0.1 -> declared_as declkind:param
assumption:0 -> constrains sym:#0.0
assumption:0 -> constrains sym:#0.1
```

`goal g1`, `derive d1` and `proved g1 by d1` are **absent**. Both `graph` and `triples`
report `faithful=True` with **zero** loss reports.

Backend-by-backend, on the three V2 node kinds:

| Backend | `faithful` | reports | GoalStmt | DeriveStmt | ProvedStmt |
| --- | --- | --- | --- | --- | --- |
| english | True | 0 | present | present | present |
| **graph** | **True** | **0** | **SILENT** | **SILENT** | **SILENT** |
| hml | True | 0 | present | present | present |
| json | True | 0 | present | present | present |
| latex | False | 5 | reported | reported | reported |
| lean | False | 5 | reported | reported | reported |
| stan | False | 4 | reported | reported | reported |
| sympy | False | 4 | reported | reported | reported |
| **triples** | **True** | **0** | **SILENT** | **SILENT** | **SILENT** |

**Silent losses: 6** (3 node kinds × 2 backends).

The four lowering backends report exactly as D-025 claims, and the reports are good:

```
[dropped] goal g1 (line 4): latex has no goal state; the proposition is not carried and its OPEN/PROVED status is erased
[dropped] derive d1 (line 6): latex has no derivation form; the inference (symmetry from p1), its generated obligations and its verification status are all erased
[dropped] proved g1 (line 7): latex cannot express that a goal was adjudicated; the proof claim and the checker's verdict are erased
```

### Root cause

```
$ grep -rn "report_reasoning_loss" $SNAP2/src/hamiltonian_lang/
backends/base.py:94       def report_reasoning_loss(self) -> None:
backends/latex.py:88          self.report_reasoning_loss()
backends/lean.py:235          self.report_reasoning_loss()
backends/stan.py:310          self.report_reasoning_loss()
backends/sympy.py:204         self.report_reasoning_loss()

$ grep -n "GoalStmt\|DeriveStmt\|ProvedStmt" $SNAP2/src/hamiltonian_lang/graph/__init__.py
(no output — build_graph has no case for any V2 node)
```

`report_reasoning_loss()` was correctly placed on the `Backend` base class — the note in
D-025 says it was put there "so the next construct is remembered once rather than five
times". But `graph` and `triples` are **not `Backend` subclasses**. They are closures in
`backends/__init__.py` that construct `BackendResult` directly:

```python
def _triples(module, symbols=None) -> BackendResult:
    from ..graph import build_graph
    ...
    return BackendResult(target="triples", text=build_graph(module, symbols).render_triples())
```

So the base-class remedy can never fire for them. The fix covered 4 of the 6 lossy
backends and missed the 2 that bypass the class hierarchy — and those 2 are the *semantic
graph* views, the machine-readable ones a downstream consumer is most likely to trust as
a complete picture of the module's content.

This is a regression of precisely the defect D-025 records as introduced-and-closed.

---

## 4. R-06 — the CLI reports none of the reasoning layer, and `obligations` misreports

`hml check` and `hml obligations` are byte-identical to `3dd4216`:

```
$ diff <(git show 3dd4216:src/hamiltonian_lang/cli/__init__.py) $SNAP2/src/hamiltonian_lang/cli/__init__.py
(no output)
```

Consequences, on the module where `1.0 = 2.0` is PROVED:

```
$ $HMLV2 check $RT/V4_self_proving_goal.hml
ok: SelfProvingGoal (5 statements, 0 symbols, 0 proof obligation(s))
EXIT=0

$ $HMLV2 obligations $RT/V4_self_proving_goal.hml
no proof obligations generated
```

No goal status. No derivation status. No reasoning obligations. Exit 0.

`hml obligations` is worse than silent — it is wrong in both directions. On the module
where a real obligation was legitimately discharged (`O6_legit_discharge.hml`, whose
reasoning obligation `x != 0` is `DISCHARGED` by `h1`):

```
$ $HMLV2 obligations $RT/O6_legit_discharge.hml
2 proof obligation(s):
  [assumption            ] line   5  x > 0.0
                           status: NOT DISCHARGED
  [assumption            ] line   6  a = b
                           status: NOT DISCHARGED
```

It lists the two **assumptions** as undischarged obligations — assumptions are granted,
not obligations — and omits the one genuine obligation the reasoning layer generated *and
discharged*. A reader of this output would conclude the module has two unmet obligations
and no verified reasoning. The truth is the exact inverse.

Severity HIGH rather than CRITICAL only because the underlying verdicts are correct here;
it is the reporting surface that lies. But it is what makes R-01…R-04 undetectable in
practice: there is no command a user can run that would reveal a falsely PROVED goal.

---

## 5. What holds — 22 blocked attacks

These are the results worth protecting. Each was attacked and refused.

### The obligation layer is sound (B-01…B-06)

Every unsound discharge route was refused, and the legitimate one works with correct
provenance. All six use `divide_both_sides` / `multiply_inequality`, whose mandatory
obligations are the ones that matter.

| Assumption in scope | Obligation | Result |
| --- | --- | --- |
| `x >= 0.0` | `x != 0` | **OPEN** — `HML-R707`, status CHECKED |
| `k = 0.0` | `k > 0` | **OPEN** — `HML-R707`, status CHECKED |
| `x > 0.0 or x < 0.0` | `x != 0` | **OPEN** — disjunction asserts neither disjunct |
| `forall z : Real . x != 0.0` | `x != 0` | **OPEN** — no fact escapes a binder |
| `require r1 : x != 0.0` + `prove t1 : x != 0.0` | `x != 0` | **OPEN** — obligations are not facts |
| `x > 0.0` | `x != 0` | **DISCHARGED** by `h1` |

Representative refusal:

```
warning HML-R707: derivation 'd1' is CHECKED but not VERIFIED: x != 0 is not established
  note: obligation o1 (divide_domain) generated by rule 'divide_both_sides'
  note: the step is structurally correct; its side condition is not discharged, so the result is not certified
  help: add 'assume x != 0' above this derivation, or derive it
derivation_status : {'d1': 'CHECKED'}
```

and the legitimate case:

```
derivation_status : {'d1': 'VERIFIED'}
obligations : {'id': 'o1', 'proposition': 'x != 0', 'generated_by': 'd1',
               'reason': 'divide_domain', 'mandatory': True,
               'status': 'DISCHARGED', 'discharged_by': 'h1'}
```

The `_ENTAILS` table is doing real work. `assume k = 0.0` fails to discharge `k > 0`
because `("=", ">")` is absent from the table, so the numeric-bound shortcut below it is
never reached — worth noting, because that shortcut *would* have accepted it
(`f.bound_literal >= want_literal` is `0.0 >= 0.0`, and the `>=`-specific guard does not
cover relation `=`). The table gate is load-bearing; do not relax it without moving that
guard.

### `proved` is genuinely adjudicated (B-07…B-10)

```
error HML-R710: goal 'g1' is not proved: derivation 'd1' is CHECKED, not VERIFIED
  found:    CHECKED
  expected: VERIFIED
  note: a proof claim is adjudicated, not accepted; writing 'proved' does not make a goal proved

error HML-R711: derivation 'd1' does not conclude goal 'g1'
  found:    1.0 = 1.0
  expected: 2.0 = 2.0

error HML-R709: 'a1' is not a declared derivation
  found:    a1
  help: reference a 'derive' statement
```

`proved` cannot cite an `assume` or another `goal`, cannot launder a CHECKED derivation,
and cannot close a goal the derivation does not conclude.

### The kernel is not defeatable (B-14, B-15)

**Substitution under a binder** behaves exactly as documented — conservative, refusing
rather than capturing:

```
error HML-R706: the stated conclusion is not what 'substitute' yields
  found:    forall z : Real . z > b
  expected: forall z : Real . z > a
  note: the conclusion is compared under canonical identity, so this is not a formatting difference
```

The companion derivation — the one whose conclusion is the *unchanged* quantifier — is
VERIFIED, which is sound (`P ⊢ P`) if useless.

**`expr_identity` discriminates correctly.** No collision was found:

| Pair | Identical? | Correct? |
| --- | --- | --- |
| `a + 1` vs `a + 1.0` | False | yes (see R-08 for the cost) |
| `forall x : Real . x > 0` vs `forall y : Real . y > 0` | **True** | yes — alpha-equivalence |
| `forall x : Real . …` vs `forall y : Probability . …` | False | yes |

The binder type survives type-stripping because it is serialised under `binder_type`,
not `type`, and `_strip_types` removes only the key `type`. That is a careful detail and
it is what stops a `Real` conclusion matching a `Probability` one. The coordinator asked
whether a conclusion about a `RandomVariable` could match one about a `Real`: it cannot —
`Ref` nodes carry `SymbolId`s, which are unique per module scope, so two differently-typed
symbols never share an identity.

### Alpha-equivalence holds on the reasoning graph (B-16, B-17)

```
$ $HMLV2 hash A1_label_rename_a.hml     # labels p1 / d1
c45dca69275e278e8609e4ad3c29afba052e2342ae57a3e46c8be22c2947a163
$ $HMLV2 hash A1_label_rename_b.hml     # labels premise_one / step_one
c45dca69275e278e8609e4ad3c29afba052e2342ae57a3e46c8be22c2947a163

$ $HMLV2 hash A2_var_rename_a.hml       # params a / b
a209fc43ae454b332068efce59dd8f27a608a5e158ffeb57f7fc40f808dc3787
$ $HMLV2 hash A2_var_rename_b.hml       # params zeta / omega
a209fc43ae454b332068efce59dd8f27a608a5e158ffeb57f7fc40f808dc3787
```

and the derivation status is invariant under the variable rename (`VERIFIED` in both).

### Structural guards (B-11…B-13, B-19, B-20)

* Mutual recursion → `HML-R703` (*"premise 'd2' is declared later in the module"*).
* Duplicate claim label → `HML-R701`.
* Self-citation → `HML-R702` (*"circular provenance would make the reasoning graph
  unsound: every claim would support itself"*).
* **No surface syntax asserts a status.** `grep status parser/__init__.py` returns
  nothing, and in the reasoning path `DerivationStatus.VERIFIED` is assigned at exactly
  one site, `check.py:354`, inside `_finalise_status`. This D-025 claim **holds**.
* **Claim labels are disjoint from values.** `param p1 : Real` alongside
  `assume p1 : p1 > 0.0` produces no name collision.

> **Note on B-12.** The duplicate-label error is emitted, and the module correctly fails
> to compile — so this is BLOCKED. But `run()` still writes `self.propositions[st.label]`
> for *both* colliding statements, so the second silently overwrites the first and the
> reasoning verdicts are computed on a module the checker has already rejected
> (`C2_duplicate_label.hml` reports `d1: VERIFIED` off the shadowed proposition). No
> exploit today, because the error blocks the compile. It is one dropped error-check away
> from becoming one, and it should be tightened alongside the R-01 fix since it is the
> same dict.

### Robustness (B-21)

No crash, no hang, and at least one diagnostic on every failure:

| Input | Elapsed | Result |
| --- | --- | --- |
| 1001 premises on a 1-premise rule | 9 ms | `HML-R705`, REJECTED |
| 500-deep derivation chain | 23 ms | 500 × VERIFIED, no stack growth |
| Unicode claim labels (`μ1`, `∂1`) | 0 ms | `HML-L101`, `HML-L102`, `HML-P203` |
| Degenerate syntax (`derive`, `proved by`, `goal`) | 0 ms | 4 errors, `HML-P202`/`P203` |
| 200-deep nested rule argument | 2 ms | `HML-P240` (MAX_EXPR_DEPTH), no `RecursionError` |

---

## 6. R-07 and R-08 — the two non-soundness defects

### R-07 — unknown rule arguments are silently accepted (LOW)

```
derive d1 : a * k < b * k from p1 by multiply_inequality(by := k, bogus := 99.0, fn := k)
```
```
compile ok : True   errors=0 warnings=0
derivation_status : {'d1': 'VERIFIED'}
```

`kernel.apply` computes `missing = [p for p in spec.params if p not in args]` and never
checks the converse. `bogus` and `fn` are meaningless to `multiply_inequality`; both are
accepted, and both are recorded in the canonical form under `"arguments"`. No unsoundness
— the rule ignores them — but a derivation that records `fn := k` on a rule with no `fn`
role is authoritative-looking noise, and a misspelled-but-plausible role name would be
accepted rather than corrected.

### R-08 — `1` and `1.0` are different expressions to the kernel (MEDIUM, safe direction)

```
module IntFloatIdentity
param a : Real
param b : Real
assume p1 : a = b
derive d1 : a + 1.0 = b + 1.0 from p1 by add_both_sides(by := 1)
```
```
error HML-R706: the stated conclusion is not what 'add_both_sides' yields
  found:    a + 1.0 = b + 1.0
  expected: a + 1 = b + 1
  note: the conclusion is compared under canonical identity, so this is not a formatting difference
derivation_status : {'d1': 'REJECTED'}
```

A mathematically correct derivation is rejected, and the diagnostic's own note insists
this is "not a formatting difference" — when it is precisely that.

This matters because the codebase has already litigated this exact question and decided
the other way, one module over. `refinement.py:206-214` handles integer-vs-float zero
deliberately, with a comment recording that the omission "left every division obligation
OPEN no matter what the author assumed", plus a named regression test
(`test_integer_and_float_zero_agree`). So the obligation layer treats `0` and `0.0` as
one number while the identity layer treats `1` and `1.0` as two. The two halves disagree
about what a number is.

The direction is safe — it rejects correct proofs rather than accepting false ones — so
this is MEDIUM, not CRITICAL. But it will read as arbitrary to any author who hits it,
and the fix (numeric normalisation in `_expr` for `Literal`, or a numeric-aware compare
in the one place the kernel uses) is small.

### Note on B-18 — the "43/43" claim is true but loosely worded

Re-measured across both pinned snapshots:

```
$ diff <(PYTHONPATH=$SNAP1/src $V hashall.py $SNAP1/examples) \
       <(PYTHONPATH=$SNAP2/src $V hashall.py $SNAP2/examples)
(no output — all identical)
```

43 files, identical results under both compilers. **Backward compatibility holds.**

For precision: only **15** of the 43 are HML-L1 modules that compile and therefore produce
a content hash. The other 28 all live under `examples/candidate_syntaxes/` — the
s-expression, indent-block, graph-triple and symbolic-ASCII grammars from the syntax
tournament — and fail to compile as HML-L1 by design, identically under both compilers.
D-025 says "all 43 `.hml` files under `examples/` produce byte-identical content hashes";
the accurate statement is "all 43 produce byte-identical *results*, of which 15 are
hashes and 28 are the same parse failure." The claim is not wrong, and the evidence for
backward compatibility is real. It is worth restating so nobody later reads "43 hashes"
as "43 compiling modules".

---

## 7. Summary

**8 attacks succeed: R-01, R-02, R-03, R-04, R-05, R-06, R-07, R-08.**
**22 blocked**, including every attack on the trusted kernel, the obligation layer, the
`proved` adjudicator, alpha-equivalence, and robustness.

### The three most serious

**1 · R-01 / R-02 / R-03 / R-04 — `goal`, `require` and `prove` are accepted as premises.**
One root cause, one line each, four exploits. `1.0 = 2.0` reaches `VERIFIED` and its goal
reaches `PROVED` on a module with zero errors and zero warnings. R-04 is the sharpest
form: a goal proves itself through two symmetry steps, defeating the stated acyclicity
argument because a `goal` is textually earlier than the derivations that consume it, and
because the `proved` edge that closes the cycle is not in the premise graph the acyclicity
check walks. The kernel is blameless — it certified exactly what it was handed. **This is
the blocker; nothing else in V2 should ship until it is closed.**

**2 · R-05 — `graph` and `triples` drop every V2 node while reporting `faithful=True`.**
Six silent losses. The `Backend.report_reasoning_loss()` remedy from D-025 cannot reach
them because neither is a `Backend` subclass, and `build_graph` has no case for
`GoalStmt`, `DeriveStmt` or `ProvedStmt`. The semantic-graph view of a module full of
reasoning shows no reasoning at all and asserts nothing was lost — the failure mode
`backends/base.py` calls the worst in the codebase, in the two views most likely to be
consumed by machine.

**3 · R-06 — no CLI surface reports any reasoning verdict, and `hml obligations` inverts
the truth.** `hml check` on the falsely-PROVED module prints `ok` and exits 0.
`hml obligations` prints "no proof obligations generated" for a module containing a
derivation, and on a module with a correctly discharged obligation it reports the two
*assumptions* as `NOT DISCHARGED` while omitting the real obligation entirely. This is
what makes findings 1 and 2 undetectable in normal use: there is no command a user can run
that would show a false goal marked PROVED.

Runners-up: **R-08**, where the kernel's notion of a number disagrees with the refinement
environment's and rejects correct proofs; and **R-07**, silent acceptance of rule
arguments no rule has.
