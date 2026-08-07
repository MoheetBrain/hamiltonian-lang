# Red-Team Baseline — the BEFORE column

**Status:** measured, not estimated. Every row below was produced by running the command
shown against the pinned baseline build and pasting the real output.

| Field | Value |
| --- | --- |
| Baseline commit | `3dd4216e35ed5a8cca93e0dfd0e52a11b1e02732` (`feature/hml-reasoning-kernel-v2`) |
| Interpreter | Python 3.14.6 (`/Users/moheet/hml_v2_worktree/.venv`) |
| Package version | `hamiltonian-lang 0.1.0` |
| Date measured | 2026-08-07 |
| Exploits attempted | 24 |
| **Exploits that SUCCEED today** | **14** |
| Exploits BLOCKED | 8 |
| N/A (capability gap, not an exploit) | 2 |

---

## 0. Reproducing this baseline mechanically

The V2 build began modifying `src/` *while this baseline was being measured*
(`ast/nodes.py`, `lexer/`, `parser/`, `semantics/`, `backends/canonical.py` and a new
`reasoning/` package all changed mid-run, and at one point the tree did not import at
all). Measuring the BEFORE column against a moving tree would be worthless, so every
result here was taken against a **pristine export of the baseline commit**, not against
the working tree.

Recreate it exactly:

```sh
SNAP=/tmp/hml_before_snapshot
RT=/tmp/hml_redteam
rm -rf "$SNAP" && mkdir -p "$SNAP" "$RT"
git -C /Users/moheet/hml_v2_worktree archive 3dd4216 | tar -x -C "$SNAP"

cat > /tmp/hmlb <<EOF
#!/bin/sh
PYTHONPATH=$SNAP/src exec /Users/moheet/hml_v2_worktree/.venv/bin/python -m hamiltonian_lang.cli "\$@"
EOF
chmod +x /tmp/hmlb
```

`PYTHONPATH` precedes the editable-install `.pth` entry, so `/tmp/hmlb` runs the frozen
baseline regardless of the state of the working tree. Verified:

```
$ /tmp/hmlb --version
hamiltonian-lang 0.1.0
$ PYTHONPATH=$SNAP/src .venv/bin/python -c "import hamiltonian_lang; print(hamiltonian_lang.__file__)"
/tmp/hml_before_snapshot/src/hamiltonian_lang/__init__.py
```

Sanity check that the snapshot is genuinely pre-V2 — the V2 reasoning keywords must be
absent:

```
$ grep -c "derive\|goal\|proved" $SNAP/src/hamiltonian_lang/lexer/__init__.py
0
```

Every probe file is reproduced in full in §3 so this document is self-contained; the
`.hml` sources do not need to survive for the baseline to be re-run.

Throughout, `$HMLB` means `/tmp/hmlb` and `$RT` means the probe directory.

---

## 1. Findings table

Severity scale: **CRITICAL** = the tool emits authoritative output that is false, and
nothing in the output warns the reader · **HIGH** = unsound acceptance, but the output
records honestly that it is unproved · **MEDIUM** = misleading or lossy but recoverable ·
**LOW** = footgun.

| ID | Attack | Command | Verdict | Sev | What a fix requires |
| --- | --- | --- | --- | --- | --- |
| X-01 | `prove 1.0 = 2.0` | `$HMLB check $RT/01_false_theorem.hml` | **EXPLOIT SUCCEEDS** | HIGH | An `hml check` exit code that is non-zero, or a distinct exit code, when undischarged `theorem` obligations remain. |
| X-02 | Contradictory assumptions in one module; `assume false` | `$HMLB check $RT/02_contradictory_assumptions.hml` | **EXPLOIT SUCCEEDS** | HIGH | A consistency check over the assumption set; at minimum reject a literal-`false` assumption and flag syntactically opposed pairs. |
| X-03 | Division by a provably-zero divisor | `$HMLB check $RT/matrix/m_div_lit.hml` | **EXPLOIT SUCCEEDS** | CRITICAL | A `nonzero_divisor` obligation on every `/`; and `1.0/0.0` must not synthesise `NonNegativeReal`. |
| X-04 | Domain-guard matrix (sqrt·log·tan·`^`·index) | see §2 | **PARTIAL — 4 of 7 unguarded** | HIGH | Domain obligations for `tan`, `/`, `^`, and static extent-bounds checking for `Index`. |
| X-05 | Treat a `Real` as a `RandomVariable` and vice versa | `$HMLB check $RT/05_rv_barrier.hml` | BLOCKED | — | — (already enforced) |
| X-06 | Give a bare `Real` a distribution via `law`/`prior` | `$HMLB check $RT/06_law_typing_hole.hml` | **EXPLOIT SUCCEEDS** | CRITICAL | `check_law` must require `RandomVariable[T]` on the target, or promote the symbol's type; today it unwraps only when the target already *is* an RV. |
| X-07a | Coerce `Probability`/`PValue`/`PosteriorProbability` at a declaration | `$HMLB check $RT/07_epistemic_coercion.hml` | BLOCKED | — | — (already enforced) |
| X-07b | Erase the same distinction via comparison and arithmetic | `$HMLB check $RT/07c_epistemic_compare.hml` | **EXPLOIT SUCCEEDS** | CRITICAL | Comparison and binary-operator positions must impose the epistemic-kind relation, not fall back to the `NonNegativeReal` join. |
| X-08 | `forall.exists` vs `exists.forall` hash collision | `$HMLB hash $RT/08a…` / `08b…` | BLOCKED | — | — (hashes differ; audit claim confirmed correct) |
| X-09a | Silent dimensional erasure in any backend | `probe09.py` | BLOCKED — **0 silent losses** | — | — (all three erasing backends report it) |
| X-09b | Silent erasure of *modal force* (`require`/`check`) in LaTeX | `$HMLB render -t latex $RT/09d_modal_force.hml` | **EXPLOIT SUCCEEDS** | CRITICAL | The LaTeX backend must mark, or `weaken()`-report, `require` and `check` lines instead of emitting bare formulas. |
| X-10 | Break alpha-equivalence by renaming a binder | `$HMLB hash $RT/10a…` / `10b…` | BLOCKED | — | — (property holds for bound *and* free names) |
| X-11 | Escape / abuse `assume` scoping | `$HMLB obligations $RT/11_assume_scope.hml` | **EXPLOIT SUCCEEDS** | HIGH | Assumptions need a scope and obligations need to record the assumption context they were generated under. `ProofObligation` has no such field. |
| X-12 | Define a new rule / type / distribution / dimension; `import` | `$HMLB check $RT/12_import.hml`, `12b…` | N/A — confirmed absent | — | Capability gap, not an exploit. Audit claim confirmed. |
| X-13a | `check <proposition>` is a total no-op | `$HMLB check $RT/D3_false_check.hml` | **EXPLOIT SUCCEEDS** | CRITICAL | `check` on a proposition must either discharge or emit an obligation. Today it emits neither. |
| X-13b | `1e400` → `Infinity`; canonical form is not valid JSON | `$HMLB canonical $RT/E3b_infinity.hml` | **EXPLOIT SUCCEEDS** | CRITICAL | Reject non-finite literals at the lexer; the canonical serializer must be RFC-8259 conforming. |
| X-13c | `1e-400` silently becomes `0.0` in the canonical form | `$HMLB canonical $RT/E3_numeric_edges.hml` | **EXPLOIT SUCCEEDS** | HIGH | Reject or exactly represent literals that underflow binary64. |
| X-13d | `views` claims "every view", renders 4 of 9 backends | `$HMLB views …` | **EXPLOIT SUCCEEDS** | MEDIUM | Render every registered backend, or change the help text. |
| X-13e | `render --no-report` suppresses the loss header | CLI flag | **EXPLOIT SUCCEEDS** | LOW | Keep the flag but keep a one-line machine-readable loss marker. |
| X-13f | `HML-T402` help text recommends the X-06 hole | `$HMLB check $RT/05b_rv_assign.hml` | **EXPLOIT SUCCEEDS** | MEDIUM | The "declare `X : Real`" suggestion must not be offered for an RV-typed symbol. |
| A-01 | Audit: `fn` has no parser production | `$HMLB check $RT/B2_fn_colon.hml` | **AUDIT WRONG** — `fn` parses | MEDIUM | See §4. |
| A-02 | Audit: `unique` has no parser production | `$HMLB check $RT/B4_unique.hml` | **AUDIT WRONG** — parses, and is well implemented | — | See §4. |
| A-03 | Audit: `map` has no parser production | `$HMLB check $RT/B5_map_query.hml` | **AUDIT WRONG** — live infer query | — | See §4. |
| A-04 | Audit: `expectation`/`variance` keywords shadow builtins | `$HMLB check $RT/A1_expectation_keyword.hml` | **AUDIT CORRECT** | MEDIUM | See §4. |

---

## 2. Raw evidence

### X-01 — `prove 1.0 = 2.0` compiles clean

```
$ $HMLB check $RT/01_false_theorem.hml
ok: FalseTheorem (2 statements, 0 symbols, 1 proof obligation(s))
EXIT=0

$ $HMLB obligations $RT/01_false_theorem.hml
1 proof obligation(s):
  [theorem               ] line   3  1.0 = 2.0
                           status: NOT DISCHARGED
```

**Verdict: EXPLOIT SUCCEEDS.** Exit code `0`. In fairness the obligation *is* recorded and
*is* marked `NOT DISCHARGED` — this is the honest half of the system, and it is why this is
rated HIGH rather than CRITICAL. The exploit is the exit code: any CI gate of the form
`hml check **/*.hml` passes a file that proves 1 = 2. Contrast X-13a, where nothing at all
is recorded.

### X-02 — contradictory assumptions, and `assume false`

```
$ $HMLB check $RT/02_contradictory_assumptions.hml
ok: Contradiction (5 statements, 1 symbols, 3 proof obligation(s))
EXIT=0

$ $HMLB obligations $RT/02_contradictory_assumptions.hml
3 proof obligation(s):
  [assumption            ] line   5  x > 0.0
                           status: NOT DISCHARGED
  [assumption            ] line   6  x < 0.0
                           status: NOT DISCHARGED
  [theorem               ] line   8  x = 999.0
                           status: NOT DISCHARGED
```

`assume x > 0` and `assume x < 0` coexist with no diagnostic. `assume false` is likewise
accepted (see X-11). Nothing records that the theorem was stated under an inconsistent
assumption set — from which it follows.

**Verdict: EXPLOIT SUCCEEDS.**

### X-03 — division by a provably-zero divisor

```
$ $HMLB check $RT/matrix/m_div_lit.hml
ok: MDivLit (2 statements, 1 symbols, 1 proof obligation(s))
EXIT=0

$ $HMLB obligations $RT/matrix/m_div_lit.hml
1 proof obligation(s):
  [parameter_positivity  ] line   2  r >= 0
                           status: NOT DISCHARGED

$ $HMLB obligations $RT/03_division_by_zero.hml
1 proof obligation(s):
  [parameter_positivity  ] line   5  bad2 >= 0
                           status: NOT DISCHARGED
```

No `nonzero divisor` obligation is generated for either `1.0 / zero` or `1.0 / 0.0`. Worse,
the canonical form asserts a **type** for the quotient:

```
$ $HMLB canonical $RT/03_division_by_zero.hml
      "body": {
        "kind": "BinOp",
        "left":  { "kind": "Literal", "type": "PositiveReal",    "value": 1.0 },
        "op": "/",
        "right": { "kind": "Literal", "type": "NonNegativeReal", "value": 0.0 },
        "type": "NonNegativeReal"
      },
      "symbol": { "id": "sym:#0.2", "name": "bad2" },
```

HML states, in its canonical machine-readable form, that `1.0 / 0.0` **is a non-negative
real number**, and then emits a standing obligation `bad2 >= 0` about it. That is an
authoritative artifact carrying a false mathematical claim.

**Verdict: EXPLOIT SUCCEEDS. Severity CRITICAL.**

### X-04 — the domain-guard matrix

One file per operator, each self-contained. `EXIT=0` means the unsound expression was
accepted.

```
PROBE            EXIT   OBLG  VERDICT
m_sqrt           1            GUARDED: HML-T427
m_log            1            GUARDED: HML-T427
m_tan            0            UNGUARDED (accepted)
m_div_lit        0      1     UNGUARDED (accepted)
m_div_sym        0            UNGUARDED (accepted)
m_pow_zero       0            UNGUARDED (accepted)
m_pow_frac       0            UNGUARDED (accepted)
m_index_oob      0            UNGUARDED (accepted)
m_index_neg      0            UNGUARDED (accepted)
m_index_frac     1            GUARDED: HML-T423
```

| Operation | Probe | Guarded? | Mechanism |
| --- | --- | --- | --- |
| `sqrt(negative)` | `m_sqrt` | **YES** | `HML-T427`, via `_BUILTIN_SIGNATURES["sqrt"] = ((NonNegativeReal,), NonNegativeReal)` |
| `log(negative)` | `m_log` | **YES** | `HML-T427`, via `_BUILTIN_SIGNATURES["log"] = ((PositiveReal,), Real)` |
| `tan(π/2)` | `m_tan` | **NO** | signature is `((Real,), Real)` — the pole is not excluded and no obligation is emitted |
| `1.0 / 0.0` (literal) | `m_div_lit` | **NO** | no divisor obligation; quotient typed `NonNegativeReal` |
| `1.0 / zero` (symbolic) | `m_div_sym` | **NO** | no divisor obligation at all |
| `0.0 ^ -1.0` | `m_pow_zero` | **NO** | no obligation |
| `(-4.0) ^ 0.5` | `m_pow_frac` | **NO** | no obligation; a non-real result is typed as real |
| `v[99]` on `Vector[Real, 3]` | `m_index_oob` | **NO** | the static extent `3` is carried in the type and never consulted |
| `v[-1]` on `Vector[Real, 3]` | `m_index_neg` | **NO** | negative index accepted |
| `v[1.5]` | `m_index_frac` | **YES** | `HML-T423` — index must be `Natural` or `Integer` |
| indexing a non-indexable base | `04d` | **YES** | `HML-T425` — `Real cannot be indexed` |

Exact guarded diagnostics:

```
$ $HMLB check $RT/04_domain_matrix.hml
error HML-T427: the argument of sqrt has the wrong type
   7 | def a := sqrt(neg)
                     ^^^
  found:    Real
  expected: NonNegativeReal

error HML-T427: the argument of log has the wrong type
   8 | def b := log(neg)
                    ^^^
  found:    Real
  expected: PositiveReal
```

And the unguarded set, all in one clean-compiling file:

```
$ $HMLB check $RT/04b_domain_unguarded.hml
ok: DomainUnguarded (7 statements, 6 symbols, 0 proof obligation(s))
EXIT=0
```

Seven statements containing `tan(π/2)`, `0^-1`, `(-4)^0.5` and `1.0/zero` produce
**zero proof obligations**.

**Verdict: audit claim VERIFIED.** sqrt and log are guarded; division, `tan`, `^` and index
bounds are not. Indexing is guarded for index *type* but not for index *range*.

### X-05 — the RandomVariable / Distribution barrier

```
$ $HMLB check $RT/05_rv_barrier.hml
error HML-T431: '+' is not defined for these operand types
   7 | def mix1 := plain + X
                   ^^^^^^^^^
  found:    RandomVariable[Real]
  expected: Real

error HML-T430: arithmetic on a probability law is not defined
   8 | def mix2 := plain + d
                           ^
  found:    Distribution[Real]
  note: a Distribution[T] is not a value of T; sample it or take a summary such as expectation first

error HML-T430: arithmetic on a probability law is not defined
   9 | def mix3 := X + d
                       ^
  found:    Distribution[Real]
  note: a Distribution[T] is not a value of T; sample it or take a summary such as expectation first
EXIT=1
```

Assignment in both directions is likewise rejected:

```
$ $HMLB check $RT/05b_rv_assign.hml
error HML-T402: the declared type of 'y' requires Real
   5 | var y : Real = X
                      ^
  found:    RandomVariable[Real]
  expected: Real
  help: declare 'X : Real'

error HML-T402: the declared type of 'z' requires RandomVariable[Real]
   6 | var z : RandomVariable[Real] = c
                                      ^
  found:    Real
  expected: RandomVariable[Real]
  help: declare 'c : RandomVariable[Real]'
EXIT=1
```

**Verdict: BLOCKED.** The barrier is genuinely enforced from source in both directions.

> **But note X-13f:** the help text on the first error says `help: declare 'X : Real'`.
> Following that advice converts a correctly-typed random variable into a bare `Real` —
> which is precisely the X-06 law-typing hole. The compiler's own repair suggestion walks
> the user into the language's most serious unsoundness.

### X-06 — the law-typing hole (audit claim **VERIFIED**)

```
$ $HMLB check $RT/06_law_typing_hole.hml
ok: LawTypingHole (6 statements, 2 symbols, 0 proof obligation(s))
EXIT=0
```

Source: `param mu : Real` + `prior mu ~ Normal(location := 0.0, scale := 1.0)`.

The canonical form shows the symbol keeping its `Real` type while carrying a law:

```
    { "declaration_kind": "param", "kind": "Declaration",
      "symbol": { "id": "sym:#0.0", "name": "mu" }, "type": "Real", "value": null },
    { "kind": "Law", "role": "prior", "target": "sym:#0.0",
      "distribution": { "family": "Normal", "kind": "DistributionLaw",
                        "type": "Distribution[Real]" } },
```

`mu` is simultaneously usable as an ordinary number (`def mu_is_a_number := mu + 1.0`,
typed `Real`) **and** as an inference target (`infer posterior mu`, `infer expectation mu`,
both accepted). The semantic graph states both facts side by side:

```
$ $HMLB graph $RT/06_law_typing_hole.hml
sym:#0.0 -> has_type type:Real
sym:#0.0 -> declared_as declkind:param
law:0 -> family family:Normal
sym:#0.0 -> has_law:prior law:0
inference:0 -> queries:posterior sym:#0.0
inference:1 -> queries:expectation sym:#0.0
```

The LaTeX view renders the contradiction as publication-quality typeset mathematics, and
the loss report says nothing about it:

```
$ $HMLB views $RT/06_law_typing_hole.hml
===== latex =====
% module LawTypingHole
\begin{align}
\mu &\in \mathbb{R} \\
\mu &\sim \mathcal{N}\left(0.0, 1.0\right) \\
\mu_{is_a_number} &:= \mu + 1.0 \\
&p(\mu \mid \text{data}) \\
&\mathrm{expectation}[\mu]
\end{align}
# latex: 2 construct(s) not fully preserved
#   [weakened] param mu (line 3): declared type Real rendered as set membership; …
#   [weakened] Normal argument roles (line 4): role labels (location, scale) become positional …
```

`\mu \in \mathbb{R}` immediately above `\mu \sim \mathcal{N}(0.0, 1.0)`. Neither loss note
mentions that a set-element has been given a probability law.

**Root cause**, `type_system/__init__.py:744-748` (baseline snapshot):

```python
codomain = (
    target_type.codomain
    if isinstance(target_type, RandomVariableType)
    else target_type
)
```

The `else` branch is the hole: any value type is accepted as a law target, and only the
*support* is checked against it. `RandomVariable[T]` is unwrapped when present but is never
*required*.

**Verdict: EXPLOIT SUCCEEDS. Severity CRITICAL. The audit's allegation is confirmed
exactly as stated.**

### X-07a — epistemic coercion at a declaration is BLOCKED

```
$ $HMLB check $RT/07_epistemic_coercion.hml
error HML-T402: the declared type of 'a' requires PosteriorProbability
   7 | var a : PosteriorProbability = pv
                                      ^^
  found:    PValue
  expected: PosteriorProbability
  note: a p-value is P(data at least this extreme | H0); a posterior is P(H0 | data). Reading a p-value as a posterior is the prosecutor's fallacy
  help: there is no conversion from PValue to PosteriorProbability; …

error HML-T402: the declared type of 'b' requires PValue
   … found: Probability, expected: PValue
   note: a model probability is not the output of a hypothesis test

error HML-T402: the declared type of 'c' requires Probability
   … found: PosteriorProbability, expected: Probability
   note: a posterior is stated relative to the prior it was computed against; …
EXIT=1
```

Laundering through an annotated `def` is also blocked (`HML-T403`, `07b`).

**Verdict: BLOCKED.** All six ordered pairs are refused, with genuinely good diagnostics.

### X-07b — but the same distinction is erased by comparison and arithmetic

```
$ $HMLB check $RT/07c_epistemic_compare.hml
ok: EpistemicCompare (8 statements, 4 symbols, 7 proof obligation(s))
EXIT=0

$ $HMLB obligations $RT/07c_epistemic_compare.hml
7 proof obligation(s):
  [constraint            ] line   7  pv = post
                           status: NOT DISCHARGED
  [constraint            ] line   8  p < pv
                           status: NOT DISCHARGED
  [theorem               ] line   9  post = pv
                           status: NOT DISCHARGED
  …
  [parameter_positivity  ] line  10  sum >= 0
                           status: NOT DISCHARGED
```

`require pv = post` — *a p-value equals a posterior probability* — is accepted, recorded as
a constraint, and rendered by the English backend as a plain requirement:

```
$ $HMLB render -t english $RT/07c_epistemic_compare.hml
Let pv be a parameter that is a p-value: the probability, computed under the null hypothesis, of data at least as extreme as those observed.
Let post be a parameter that is a posterior probability: the probability of a hypothesis given the data and a stated prior.
It is required that pv is equal to post.
It is required that p is strictly less than pv.
It is claimed, and not yet proved, that post is equal to pv.
Define sum to be pv plus post.
```

The module carefully explains what a p-value and a posterior each are, and then asserts
they are equal. `def sum := pv + post` — adding a p-value to a posterior — is also accepted
and typed `NonNegativeReal`.

This is exactly the prosecutor's fallacy that `types.py` names in its own docstring as the
reason the three kinds exist. The barrier holds in *checking-mode* positions (declaration
initialiser, definition body, call argument, distribution role) and collapses in
*synthesis-only* positions (comparison operands, binary-operator operands), where the three
kinds join at their common supertype `NonNegativeReal`. Per the checker's own table, seven
of twelve expression-bearing positions impose only a predicate and carry no type
expectation — these are two of them.

**Verdict: EXPLOIT SUCCEEDS. Severity CRITICAL.** The headline D-022 guarantee is
enforced in 5 of 12 positions.

### X-08 — quantifier order (audit claim confirmed correct)

```
$ $HMLB hash $RT/08a_forall_exists.hml   # prove forall x : Real . exists y : Real . y > x
f192c83fdea7fee8b4cf0d1d0554a5365f4f912b430bdce122319603e22423d6

$ $HMLB hash $RT/08b_exists_forall.hml   # prove exists y : Real . forall x : Real . y > x
5a9f6e4f1e3ebbe9ad0846d184cfaaaad7fd1c531cf5b63dcc4329c5284fffa1
```

The graph view also preserves nesting order (`quantifier:0 -> scope_of:exists quantifier:1`
vs `quantifier:0 -> scope_of:forall quantifier:1`).

**Verdict: BLOCKED.** Hashes differ, as the audit says.

### X-09a — dimensional erasure: zero silent losses

Every registered backend was run over a module carrying both dimensions and all three
epistemic kinds, checking whether each was preserved in the output text *or* declared in
the `BackendResult` loss report.

| Backend | `faithful` | loss reports | dimensions | epistemic kinds |
| --- | --- | --- | --- | --- |
| english | True | 0 | preserved | preserved (as prose) |
| graph | True | 0 | preserved | preserved |
| hml | True | 0 | preserved | preserved |
| json | True | 0 | preserved | preserved |
| latex | False | 5 | preserved | preserved |
| lean | False | 14 | **dropped — REPORTED** | **erased — REPORTED** |
| stan | False | 6 | **dropped — REPORTED** | **erased — REPORTED** |
| sympy | False | 8 | **dropped — REPORTED** | **erased — REPORTED** |
| triples | True | 0 | preserved | preserved |

Representative reports — these are unusually candid and are a genuine strength of the
baseline:

```
[weakened] m (line 3): Stan is dimensionless: the dimension Mass is dropped and the quantity becomes a bare real.
[weakened] pv (line 6): PValue becomes the same real<lower=0,upper=1> as Probability; Stan cannot carry the epistemic kind, so the p-value / posterior / model probability separation is lost in the emitted program.
[dropped]  check dimension (line 10): Stan has no dimensional analysis; the asserted dimension (Length^2 * Mass / Time^2) cannot be carried into the program.

[weakened] v (line 4): the dimension Length / Time is dropped; the quantity becomes its bare carrier type, so dimensionally invalid Lean expressions become well-typed.
[weakened] pv (line 6): PValue becomes the same ℝ with 0 ≤ x ≤ 1 hypotheses as Probability; Lean carries the bounds and not the epistemic kind, so a p-value and a posterior are indistinguishable in the emitted statement.
```

**SILENT dimensional losses: 0.** Every backend that drops a dimension says so.

**Verdict: BLOCKED.**

### X-09b — but modal force *is* silently erased by the LaTeX backend

```
$ $HMLB render -t latex $RT/09d_modal_force.hml
% latex: 1 construct(s) not fully preserved
% [weakened] param x (line 2): declared type Real rendered as set membership; the declaration role (param) has no LaTeX encoding

% module ModalForce
\begin{align}
x &\in \mathbb{R} \\
&x < 10.0 \\
&x > 0.0 \\
&\bot
\end{align}
```

Source was:

```
param x : Real
require x < 10.0
check x > 0.0
check false
```

* `require x < 10.0` → `&x < 10.0` — an undischarged constraint rendered as a bare formula.
* `check x > 0.0` → `&x > 0.0` — an inert no-op rendered as a bare formula.
* `check false` → `&\bot` — falsity rendered as a line of an `align` block.

Three constructs lost their modal force. **One** loss report was emitted, and it is about
the declaration role of `x`. Nothing warns that the display-math block mixes asserted
types, undischarged constraints and un-evaluated checks into one undifferentiated list that
a reader will parse as a derivation. The `english` backend gets this right
("It is required that…", "Check that…"), so the defect is LaTeX-specific.

**Verdict: EXPLOIT SUCCEEDS. Severity CRITICAL** — this is precisely the failure mode
`backends/base.py` names as "the worst failure mode in this codebase".

### X-10 — alpha-equivalence

```
$ $HMLB hash $RT/10a_alpha.hml            # prove forall x   : Real . x = x
7af516fd81f2877d6c234fa82ff5282fbec0dda69f8b72d7bb0623a4c8d58a0d
$ $HMLB hash $RT/10b_alpha_renamed.hml    # prove forall zzz : Real . zzz = zzz
7af516fd81f2877d6c234fa82ff5282fbec0dda69f8b72d7bb0623a4c8d58a0d

$ $HMLB hash $RT/10c_alpha_free.hml       # param aaa : Real ; require aaa > 0.0
af4a6fa7140e028565e1ece5e205c08545144d392a4c981892bd39570c638380
$ $HMLB hash $RT/10d_alpha_free_renamed.hml  # param bbb : Real ; require bbb > 0.0
af4a6fa7140e028565e1ece5e205c08545144d392a4c981892bd39570c638380
```

**Verdict: BLOCKED — the property holds**, for bound variables and for module-level free
names alike. Renaming preserves the content hash exactly as designed.

### X-11 — `assume` has no scope, and obligations carry no assumption context

```
$ $HMLB check $RT/11_assume_scope.hml
ok: AssumeScope (6 statements, 1 symbols, 4 proof obligation(s))
EXIT=0

$ $HMLB obligations $RT/11_assume_scope.hml
4 proof obligation(s):
  [theorem               ] line   5  x > 0.0
                           status: NOT DISCHARGED
  [assumption            ] line   6  x > 0.0
                           status: NOT DISCHARGED
  [assumption            ] line   7  false
                           status: NOT DISCHARGED
  [theorem               ] line   8  x < 0.0
                           status: NOT DISCHARGED
```

Three separate defects visible in one output:

1. **`assume` is module-flat.** There is no block, no scope, no discharge. The parser has a
   single production `assume <expr>` and the resolver treats it as a module-level statement.
2. **`assume false` is accepted with no diagnostic.** Ex falso quodlibet is admitted as a
   premise.
3. **Order is irrelevant and unrecorded.** The `prove x > 0.0` on line 5 *precedes* its
   assumption on line 6, yet appears as a peer obligation. `ProofObligation` has fields
   `kind · description · span · expression · discharged_by` and no assumption-context
   field at all, so a downstream discharger receives `x < 0.0` with no way to learn it was
   stated under `assume false`.

**Verdict: EXPLOIT SUCCEEDS.**

### X-12 — extensibility (audit claim confirmed)

```
$ $HMLB check $RT/12_import.hml
error HML-P205: 'import' does not begin a statement
   2 | import Other
       ^^^^^^
  help: statements begin with one of: module var param const obs index rv def law prior likelihood assume require prove minimise maximise solve infer check concept
EXIT=1
```

`type`, `distribution`, `dimension`, `rule` and `axiom` all fail identically with
`HML-P205`. The complete statement vocabulary is the 19 keywords listed in that help text.
A user cannot define a new inference rule, type, distribution family, base dimension, or
import another module. The only user-extensible construct is `concept`, and an undeclared
concept name is correctly rejected (`HML-T440`).

**Verdict: N/A — capability gap, not an exploit. Audit claim confirmed: there is no
`import` at all.**

### X-13a — `check <proposition>` is a total no-op ⚑

```
$ $HMLB check $RT/D3_false_check.hml
ok: FalseCheck (3 statements, 0 symbols, 0 proof obligation(s))
EXIT=0

$ $HMLB obligations $RT/D3_false_check.hml
no proof obligations generated
```

The file is:

```
module FalseCheck
check 1.0 = 2.0
check false
```

**Zero proof obligations.** Not "undischarged" — *absent*. `hml check` reports `ok`. The
statements survive into every view and read as though something was verified:

```
$ $HMLB render -t english $RT/D3_false_check.hml
Module FalseCheck.

Check that 1.0 is equal to 2.0.
Check that false.

$ $HMLB render -t latex $RT/D3_false_check.hml
% module FalseCheck
\begin{align}
&1.0 = 2.0 \\
&\bot
\end{align}
```

Root cause, `type_system/__init__.py:916-956` (baseline snapshot) — `check_check` branches
on `check_kind`:

```python
if st.check_kind == "dimension":
    …
    self._obligate("dimension", f"dimension = {dim.render()}", st.span, st.subject)
    self.obligations[-1].discharged_by = "hamiltonian_lang.type_system"
else:
    if not (isinstance(t, PropositionType) or is_subtype(t, BOOL)):
        self.diags.error("HML-T404", "check requires a proposition", …)
```

The `dimension` arm really does verify, and marks the obligation discharged. The
proposition arm tests only that the subject *is* a proposition and then returns. One
keyword, `check`, therefore means two incompatible things — "verified by the type system"
and "completely ignored" — and no view distinguishes them.

This is strictly worse than X-01: `prove 1.0 = 2.0` at least leaves a `NOT DISCHARGED`
record. `check 1.0 = 2.0` leaves nothing, and a reader of the obligation list sees a clean
report.

**Verdict: EXPLOIT SUCCEEDS. Severity CRITICAL.**

### X-13b — `1e400` becomes `Infinity`, and the canonical form stops being JSON

```
$ $HMLB check $RT/E3b_infinity.hml
ok: InfinityLiteral (2 statements, 1 symbols, 0 proof obligation(s))
EXIT=0

$ $HMLB canonical $RT/E3b_infinity.hml
      "value": { "kind": "Literal", "type": "PositiveReal", "value": Infinity }
```

Fed to a conforming JSON parser:

```
$ $HMLB canonical $RT/E3b_infinity.hml | python -c \
    "import json,sys; json.loads(sys.stdin.read(), parse_constant=lambda c: (_ for _ in ()).throw(ValueError(f'invalid JSON constant: {c}')))"
ValueError: invalid JSON constant: Infinity
EXIT=1
```

Three compounding defects:

1. `1e400` is accepted as inhabiting `Real` and typed **`PositiveReal`**. ∞ is not a real
   number.
2. The **"canonical JSON form" is not valid JSON.** `Infinity` is not a JSON literal
   (RFC 8259). Python's default `json.dumps` emits it; no conforming parser accepts it.
   Any external consumer of `hml canonical` breaks on this input.
3. A **content hash is still produced** over that non-JSON document:
   `5ea6e669640bb9668dd9621bde33c2eb263f534a22b0fa0758d1b7605a72f690`. The hash is the
   identity of the semantic object, and here it is the identity of a document that cannot
   be parsed back.

The English view completes the picture:

```
$ $HMLB render -t english $RT/E3b_infinity.hml
Let huge be a constant that is a real number. huge equals 1e400.
```

**Verdict: EXPLOIT SUCCEEDS. Severity CRITICAL.**

### X-13c — `1e-400` silently becomes exactly zero

```
$ $HMLB check $RT/E3_numeric_edges.hml
ok: NumericEdges (4 statements, 3 symbols, 0 proof obligation(s))
EXIT=0

$ $HMLB canonical $RT/E3_numeric_edges.hml
      "value": { "kind": "Literal", "type": "NonNegativeReal", "value": 0.0 }   # was 1e-400
```

The source says a small positive number; the canonical form says exactly `0.0`, and the
refinement type shifts from `PositiveReal` to `NonNegativeReal` as a result. No warning.
The corruption becomes visible only when the declared type forces the issue, and even then
the diagnostic quotes a value the user never wrote:

```
$ $HMLB check $RT/E3c_underflow.hml
error HML-T402: the declared type of 'tiny' requires PositiveReal
   2 | const tiny : PositiveReal = 1e-400
                                   ^^^^^^
  found:    NonNegativeReal
  expected: PositiveReal
  help: supply a value in PositiveReal; 0.0 is not one
```

The caret points at `1e-400` while the help says `0.0 is not one`.

**Verdict: EXPLOIT SUCCEEDS.**

### X-13d — `views` claims completeness and delivers 4 of 9

```
$ python -c "from hamiltonian_lang.backends import available; print(available())"
['english', 'graph', 'hml', 'json', 'latex', 'lean', 'stan', 'sympy', 'triples']

$ $HMLB views $RT/09_dimensional.hml | grep '^====='
===== hml =====
===== english =====
===== latex =====
===== triples =====
===== canonical hash =====
```

The CLI advertises `views` as *"print every view of the same object"*. It renders a
hard-coded tuple `("hml", "english", "latex", "triples")` — omitting `stan`, `lean` and
`sympy`, which are exactly the three backends that report the heaviest translation loss
(6, 14 and 8 reports respectively on the same input). The command that promises the
complete picture shows the user only the subset that looks lossless.

**Verdict: EXPLOIT SUCCEEDS.**

### X-13e — `--no-report` suppresses the loss header

`hml render --no-report` is documented as *"suppress the translation-loss header (not
recommended)"*. It emits backend output with the `Unsupported` list discarded entirely, so
a Stan program that silently dropped every dimension is indistinguishable from a faithful
one. The flag is honestly labelled, hence LOW, but it means no downstream consumer can rely
on the presence of a loss header.

**Verdict: EXPLOIT SUCCEEDS (by design).**

---

## 3. Probe corpus

All files live under `$RT`. Reproduced in full so the baseline is re-runnable without them.

<details>
<summary>Probe sources</summary>

`01_false_theorem.hml`
```
module FalseTheorem

prove 1.0 = 2.0
```

`02_contradictory_assumptions.hml`
```
module Contradiction

param x : Real

assume x > 0.0
assume x < 0.0

prove x = 999.0
```

`03_division_by_zero.hml`
```
module DivZero

const zero : Real = 0.0
def bad := 1.0 / zero
def bad2 := 1.0 / 0.0
```

`04_domain_matrix.hml`
```
module DomainMatrix

param x : Real
const neg : Real = -4.0
index i : Natural

def a := sqrt(neg)
def b := log(neg)
def c := tan(1.5707963267948966)
def d := 0.0 ^ -1.0
def e := neg ^ 0.5
```

`04b_domain_unguarded.hml`
```
module DomainUnguarded

const neg : Real = -4.0
const zero : Real = 0.0

def c := tan(1.5707963267948966)
def d := zero ^ -1.0
def e := neg ^ 0.5
def f := 1.0 / zero
```

`04d_index_oob.hml`
```
module IndexOOB2

param v : Vector[Real, 3]
def oob := v[99]
def negidx := v[-1]
def scalar_indexed := oob[0]
```

`05_rv_barrier.hml`
```
module RVBarrier

param plain : Real
rv X : RandomVariable[Real]
param d : Distribution[Real]

def mix1 := plain + X
def mix2 := plain + d
def mix3 := X + d
```

`05b_rv_assign.hml`
```
module RVAssign

rv X : RandomVariable[Real]
const c : Real = 1.0
var y : Real = X
var z : RandomVariable[Real] = c
```

`06_law_typing_hole.hml`
```
module LawTypingHole

param mu : Real
prior mu ~ Normal(location := 0.0, scale := 1.0)

def mu_is_a_number := mu + 1.0

infer posterior mu
infer expectation mu
```

`07_epistemic_coercion.hml`
```
module EpistemicCoercion

param p : Probability
param pv : PValue
param post : PosteriorProbability

var a : PosteriorProbability = pv
var b : PValue = p
var c : Probability = post
```

`07b_epistemic_launder.hml`
```
module EpistemicLaunder

param pv : PValue

def launder : Probability := pv + 0.0
def launder2 : PosteriorProbability := pv * 1.0
require pv = 0.05
```

`07c_epistemic_compare.hml`
```
module EpistemicCompare

param p : Probability
param pv : PValue
param post : PosteriorProbability

require pv = post
require p < pv
prove post = pv
def sum := pv + post
```

`08a_forall_exists.hml`
```
module QuantOrder
prove forall x : Real . exists y : Real . y > x
```

`08b_exists_forall.hml`
```
module QuantOrder
prove exists y : Real . forall x : Real . y > x
```

`09_dimensional.hml`
```
module DimensionalErasure

param m : Quantity[Mass]
param v : Quantity[Length / Time]
param p : Probability
param pv : PValue
param post : PosteriorProbability

def kinetic_energy := 0.5 * m * v^2
check dimension kinetic_energy = Mass * Length^2 / Time^2
```

`09d_modal_force.hml`
```
module ModalForce
param x : Real
require x < 10.0
check x > 0.0
check false
```

`10a_alpha.hml` / `10b_alpha_renamed.hml`
```
module Alpha
prove forall x : Real . x = x
```
```
module Alpha
prove forall zzz : Real . zzz = zzz
```

`10c_alpha_free.hml` / `10d_alpha_free_renamed.hml`
```
module AlphaFree
param aaa : Real
require aaa > 0.0
```
```
module AlphaFree
param bbb : Real
require bbb > 0.0
```

`11_assume_scope.hml`
```
module AssumeScope

param x : Real

prove x > 0.0
assume x > 0.0
assume false
prove x < 0.0
```

`12_import.hml` / `12b_user_extensions.hml`
```
module WantsImport
import Other
```
```
module UserExtensions

type MyReal := Real
distribution MyDist(shape)
dimension Money
rule modus_ponens
axiom foo
```

`D3_false_check.hml`
```
module FalseCheck
check 1.0 = 2.0
check false
```

`E3_numeric_edges.hml` / `E3b_infinity.hml` / `E3c_underflow.hml`
```
module NumericEdges
const huge : Real = 1e400
const tiny : Real = 1e-400
const nat_big : Natural = 99999999999999999999999999
```
```
module InfinityLiteral
const huge : Real = 1e400
```
```
module Underflow
const tiny : PositiveReal = 1e-400
```

Domain matrix, one operator per file — `$RT/matrix/m_*.hml`:
```
m_sqrt      : module MSqrt      / const neg : Real = -4.0 / def r := sqrt(neg)
m_log       : module MLog       / const neg : Real = -4.0 / def r := log(neg)
m_tan       : module MTan       / def r := tan(1.5707963267948966)
m_div_lit   : module MDivLit    / def r := 1.0 / 0.0
m_div_sym   : module MDivSym    / const zero : Real = 0.0 / def r := 1.0 / zero
m_pow_zero  : module MPowZero   / const zero : Real = 0.0 / def r := zero ^ -1.0
m_pow_frac  : module MPowFrac   / const neg : Real = -4.0 / def r := neg ^ 0.5
m_index_oob : module MIndexOOB  / param v : Vector[Real, 3] / def r := v[99]
m_index_neg : module MIndexNeg  / param v : Vector[Real, 3] / def r := v[-1]
m_index_frac: module MIndexFrac / param v : Vector[Real, 3] / def r := v[1.5]
```

Audit-verification probes — `A1`, `A2`, `A3`, `B1`–`B5`, `C1`, `D1`, `D2`, `D4`, `D5`,
`E1`, `E2`, `E4` — are quoted inline in §4 and §5.

</details>

---

## 4. Verification of the audit's specific claims

The lead flagged four audit claims as suspect. All four were re-tested from source. **Three
are wrong; one is correct.**

### A-01 — "`fn` is a keyword with no parser production" → **AUDIT WRONG**

`fn` *is* parsed. `parser/__init__.py:225` (baseline snapshot):

```python
if t.is_kw("def", "fn"):
    return self.parse_define()
```

It is a bare alias of `def` and compiles clean:

```
$ $HMLB check $RT/B2_fn_colon.hml
ok: FnColon (3 statements, 3 symbols, 0 proof obligation(s))
EXIT=0
```
```
module FnColon
fn f(x : Real) : Real := x + 1.0
def g(x : Real) : Real := x + 1.0
```

**Its real defects are three, and none is "unparsed":**

1. **No return-type arrow.** The lead's suspicion is confirmed — `fn` accepts a return type
   only via `:`, never via `->`, and the resulting diagnostic is actively misleading:

   ```
   $ $HMLB check $RT/B1_fn_arrow.hml     # fn f(x : Real) -> Real := x + 1.0
   error HML-P207: a definition requires ':='
      2 | fn f(x : Real) -> Real := x + 1.0
                         ^^
     note: ':=' binds a definition; '=' is mathematical equality
     help: def f := <expression>
   EXIT=1
   ```

   The caret points at `->`, but the message says `:=` is missing — and `:=` *is present*,
   four tokens later. The `help` line then discards the parameter list entirely, suggesting
   `def f := <expression>`. A user following that advice loses their function's arity. The
   `->` operator exists in the lexer's `_OPERATORS` table and is used by `Function[A -> B]`
   types, so it lexes fine and then dead-ends.

2. **Two spellings, one meaning.** `fn` and `def` produce byte-identical `DefineStmt`
   nodes. This violates the project's own rule that a spelling should have exactly one
   meaning — here one meaning has two spellings, with no decision record distinguishing
   them, and the `hml` backend normalises both to `def` on round-trip.

3. Neither `fn` nor `def` may take an untyped parameter — but that is caught by a late
   backstop rather than at the binder, unlike concept transforms which reject it at parse
   time with `HML-P214`. See §5.

### A-02 — "`unique` is a keyword with no parser production" → **AUDIT WRONG**

`unique` *is* parsed, at `parser/__init__.py:982-984`, as part of `exists unique`:

```python
if kind == "exists" and self.cur.is_kw("unique"):
    self.next()
    kind = "exists_unique"
```
```
$ $HMLB check $RT/B4_unique.hml       # prove exists unique z : Real . z > 0.0
ok: UniqueQ (2 statements, 1 symbols, 1 proof obligation(s))
EXIT=0
```

**`unique` has no real defect — it is one of the better-implemented constructs in the
language.** It is distinguished everywhere it should be:

* distinct content hash from plain `exists`
  (`3f84711d…` vs `a30c304a…`);
* English: *"there exists exactly one z that is a real number"*;
* LaTeX: `\exists! z \in \mathbb{R}`;
* graph: `theorem:0 -> scope_of:exists_unique quantifier:0`;
* correctly reported as unrepresentable by the backends that cannot carry it —
  `[dropped] exists_unique quantifier (line 2): SymPy has no first-order quantifier…`,
  and likewise for Stan.

This claim should be struck from the audit outright.

### A-03 — "`map` is a keyword with no parser production" → **AUDIT WRONG**

`map` is a live inference query. `parser/__init__.py:78`:

```python
_INFER_QUERIES = {"posterior", "expectation", "variance", "mle", "map"}
```
```
$ $HMLB check $RT/B5_map_query.hml
ok: MapQuery (4 statements, 1 symbols, 1 proof obligation(s))
EXIT=0
```
```
module MapQuery
param theta : Probability
prior theta ~ Beta(alpha := 1, beta := 1)
infer map theta
```

`map` is additionally well-posedness-checked: `_query_is_well_posed` requires a prior on
the target for `map` and `posterior`, and requires appearance in a likelihood for `mle`.
Working as intended.

### A-04 — "`expectation`/`variance` shadow implemented builtins" → **AUDIT CORRECT**

This one holds, and is worth stating precisely.

Both names are in the lexer's `KEYWORDS` set (`lexer/__init__.py:42`), so they lex as
`TokenKind.KEYWORD`. `parse_primary` admits a call only when the head token is
`TokenKind.IDENT`. A keyword in expression position therefore cannot begin a call:

```
$ $HMLB check $RT/A1_expectation_keyword.hml
error HML-P231: expected an expression, found 'expectation'
   4 | require expectation(X) > 0.0
               ^^^^^^^^^^^
EXIT=1

$ $HMLB check $RT/A2_variance_keyword.hml
error HML-P231: expected an expression, found 'variance'
   3 | require variance(s) > 0.0
               ^^^^^^^^
EXIT=1
```

**And there are real, unreachable registrations behind them.**
`semantics/__init__.py:528-531` (baseline snapshot):

```python
_BUILTIN_FUNCTIONS = {
    "exp", "log", "sqrt", "abs", "sin", "cos", "tan",
    "sum", "prod", "mean", "variance", "expectation", "transpose",
}
```

The resolver will happily accept a `Call` to `variance` or `expectation` — but the parser
can never construct one, so those two entries are dead code. The remaining four non-keyword
names in that set (`sum`, `prod`, `mean`, `transpose`) *are* reachable and *are* checked,
despite having no entry in `_BUILTIN_SIGNATURES`:

```
$ $HMLB check $RT/A3_unsigned_builtins.hml
error HML-T427: transpose requires a matrix
   7 | def d := transpose(v)
                ^^^^^^^^^^^^
  found:    Vector[Real, 3]
  expected: Matrix[...]

error HML-T426: sum takes 1 argument, 5 given
   8 | def e := sum(x, v, 1.0, 2.0, 3.0)
                ^^^^^^^^^^^^^^^^^^^^^^^^
EXIT=1
```

So the accurate statement of the defect is narrower than the audit's: it is not that the
builtins are unimplemented, but that **two of twelve builtin names are permanently
unreachable because the lexer classifies them as keywords**, and the diagnostic a user gets
(`expected an expression`) gives no hint that the name exists as a function. The correct
fix is either to make `expectation`/`variance` contextual keywords (recognised as query
kinds only immediately after `infer`), or to delete the two dead entries and say so.

---

## 5. Defenses that hold (do not regress these)

Measured, not assumed. Each was attacked and refused.

| Defense | Probe | Diagnostic |
| --- | --- | --- |
| `Distribution[T]` is not a `T`; `RandomVariable[T]` is not a `T` | `05`, `05b` | `HML-T430`, `HML-T431`, `HML-T402` |
| Epistemic kinds do not coerce at declarations or annotated definitions | `07`, `07b` | `HML-T402`, `HML-T403` |
| Literal refinement is exact (`2.0 ∉ Probability`, `0.0 ∉ PositiveReal`, `-3 ∉ Natural`) | `D5` | `HML-T402` |
| Distribution role types are enforced (`scale := -1.0`, `alpha := -1.0`) | `D1`, `D2` | `HML-T413`, with `note: scale is the standard deviation, not the variance` |
| Dimensional algebra is exact, and normalises operand order | `D4`, `E2` | `HML-D504`; `Time^-2 * Length^2 * Mass` correctly accepted as equal to `Mass * Length^2 / Time^2` |
| Dimension **variables** never silently unify with concrete dimensions | `E1` | `HML-D502` (`found: Mass, expected: D`), `HML-D504` |
| `Unknown` may not survive a successful check | `C1` | `HML-T450` — *"an untyped expression compares equal to anything, so it must not survive a successful check"* |
| Unknown type names are rejected (no silent concept minting) | `12c` | `HML-T440` |
| Chained comparisons rejected | parser | `HML-P230` |
| Round-trip through the `hml` backend is hash-stable | `09b` | 16-statement kitchen-sink module (14 symbols, 6 obligations), `HASH MATCH: True` |
| Non-ASCII operators fold to ASCII **with a warning**, never silently | `E4` | `HML-L103` |
| Backends that erase dimensions or epistemic kinds all report it | `probe09.py` | 0 silent losses across 9 backends |

Two of these deserve emphasis because they are the mirror image of findings above:

* **`HML-T450`** is the reason the untyped-parameter attack fails. `def f(x) := x + 1.0`
  is rejected because `Unknown` reaches a typed position. Note the asymmetry, though:
  concept transforms reject an untyped binder *at parse time* (`HML-P214`, with the note
  "every object has a type (governing principle 1)"), while `def`/`fn` rely on a late
  semantic backstop. The outcome is the same; the diagnostic quality is not.

* **Round-trip hash stability** held on a module exercising `param`/`obs`/`index`/`rv`,
  `prior`, a two-parameter `def`, `forall`/`exists unique`, `require`, `assume`,
  `minimise`, `solve`, `infer posterior`, `check dimension`, and a full `concept` with
  `parameter`/`transform`/`invariant`/`example`/`counterexample`/`property`. No silent loss
  in the `hml` backend for any of them.

---

## 6. Summary — 14 exploits succeed today

**Succeeding:** X-01, X-02, X-03, X-04, X-06, X-07b, X-09b, X-11, X-13a, X-13b, X-13c,
X-13d, X-13e, X-13f.

**Blocked:** X-05, X-07a, X-08, X-09a, X-10, plus the three defense classes in §5 that were
attacked directly (`HML-T450`, `HML-T440`, `HML-D502` on dimension variables).

**N/A:** X-12 (extensibility gap), A-02/A-03 (audit claims that turned out to describe
working features).

### The three most serious

**1 · X-13a — `check <proposition>` verifies nothing and records nothing.**
A module containing `check false` compiles with **zero proof obligations** and exit code 0.
The same keyword, applied to a dimension, genuinely verifies and marks the obligation
`discharged_by: hamiltonian_lang.type_system`. One keyword therefore means both "checked by
the type system" and "silently ignored", and no view — English, LaTeX, canonical, graph or
the obligation list — distinguishes them. This is worse than `prove 1.0 = 2.0`, which at
least leaves a `NOT DISCHARGED` record. A reader auditing the obligation list of a file full
of `check` statements sees a clean report and concludes the checks passed.

**2 · X-06 — the law-typing hole.**
`param mu : Real` + `prior mu ~ Normal(...)` compiles clean. `mu` keeps type `Real` in the
canonical form and the semantic graph, remains usable in ordinary arithmetic, and is
simultaneously a valid target for `infer posterior` and `infer expectation`. The LaTeX view
prints `\mu \in \mathbb{R}` directly above `\mu \sim \mathcal{N}(0.0, 1.0)` as
publication-quality typeset mathematics, and the loss report mentions neither. Root cause is
the `else target_type` fallback at `type_system/__init__.py:744-748`, which unwraps
`RandomVariable[T]` when present but never requires it. Compounding this, the `HML-T402`
diagnostic actively recommends the hole: its help text on a correctly-typed RV says
`help: declare 'X : Real'` (X-13f).

**3 · X-07b — the epistemic barrier collapses in comparison and arithmetic.**
`require pv = post`, asserting that a p-value equals a posterior probability, is accepted
and rendered in English as *"It is required that pv is equal to post"* — in a module whose
own English output has just explained that one is P(data | H0) and the other P(H0 | data).
`def sum := pv + post` is likewise accepted, typed `NonNegativeReal`. The D-022 separation
that `types.py` names in its docstring as the whole point of the three kinds is enforced in
5 of 12 expression-bearing positions; comparison operands and binary-operator operands are
among the 7 where it is not, and there the three kinds join at `NonNegativeReal`.

Close runners-up, both CRITICAL and both in the "authoritative-looking but false" class:
**X-03** (`1.0 / 0.0` is typed `NonNegativeReal` in the canonical form, with a standing
obligation `bad2 >= 0` attached to it) and **X-13b** (`1e400` is typed `PositiveReal`, and
the "canonical JSON form" emits a bare `Infinity` token that no conforming JSON parser will
read — yet a content hash is still minted over it).
