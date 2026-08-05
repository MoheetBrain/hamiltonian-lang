# Compiler Core Remediation — HML-COMPILER-CORE-003

Closing table for the defect-remediation sequence. Every row was found by **measurement**,
not review, and every fix carries a regression test that fails without it.

Baseline: `docs/evaluation/COMPILER_CORE_AUDIT.md`.

## Defects found, fixed and pinned

| # | measured defect | how it was found | fix | regression test | remaining limitation |
|---|-----------------|------------------|-----|-----------------|----------------------|
| 1 | **Parser crash.** 400 nested parens → `RecursionError` | 22-case malformed battery | `MAX_EXPR_DEPTH = 50` + `RecursionError` backstop at the parse boundary | `tests/fuzz/test_frontend_robustness.py` (23 malformed, 500 property cases, 200 truncations) | The bound is a *measurement*, not a proof: ~12.2 frames per level, ceiling at depth 82. A test fails if the grammar grows enough to invalidate it |
| 2 | **Unknown/truncated types accepted in silence.** `param x : Frobnicator` and `param sigma : Positiv` both compiled | 4 semantic-hole probes | `HML-T440` with a nearest-name correction, checked in every position a type can appear | `tests/type_system/test_unknown_types.py` (16 tests, 8 positions, 5 typo→suggestion pairs) | Suggestion is edit-distance + prefix, not semantic. It proposes a *candidate*, and can propose the wrong one |
| 3 | **Synthesis-only checking.** No `check(ctx, expr, expected)`; failures could not name the role that imposed the expectation | source inspection | explicit `synthesise` / `check` with `CheckedExpr`; distribution roles and declaration values routed through it | `tests/type_system/test_bidirectional.py` (10 tests, incl. one asserting the correction is not a restatement) | Only the two highest-value sites are routed through `check`. Function arguments, proof claims and concept members still synthesise-and-compare |
| 4a | **Rational dimension exponents rejected.** `Quantity[Length^1/2]` was `HML-P225`, though `Dimension` has always stored `Fraction` | 5 dimensional probes | disambiguation in `_dim_power`: `/` before a NUMBER is a fractional exponent, `/` before an identifier is division | `tests/type_system/test_dimension_grammar.py` | A benchmark case deleted for this reason has **not** been restored to the corpus |
| 4b | **No dimension variables.** `Quantity[D]` rejected | same | `Dimension.variables`, `unify()`, constrained to a **single capital letter** | same file, incl. 5 typo cases | Unification solves the single-variable case only. A general constraint solver is not built and no measurement justifies one |
| 5 | **Generated SymPy raised `NameError` on import.** A dropped quantified definition left a live reference | executing the output, not rendering it | `_dropped_names`; a reference to a dropped name is itself dropped and reported | `tests/backends/test_sympy_execution.py` — **executes** every generated module | Dropping propagates outward: one unencodable sub-expression removes the whole enclosing statement |
| 6 | **Lean `sorry` compiles and exits 0.** Exit status alone certifies a false theorem | direct experiment on Lean 4.32.2 | `lean_verify.verify()`: forbidden-tactic pre-check, `autoImplicit false`, compilation, statement comparison, `#print axioms` | `tests/v1/test_lean_verify.py` (12 tests, 7 against real Lean) | **Mathlib is absent**, so almost nothing HML emits is expressible: every scalar but `Bool`/`Natural`/`Integer` maps to `ℝ`. V0's Lean backend closes every obligation with `sorry`, so **no V0-emitted theorem can ever be verified** |
| 7 | **`PValue` specified and never implemented.** p-value-as-posterior type-checked, so L4 failed its own kill criterion | adversarial agent | `PValue` / `PosteriorProbability` as distinct types, deliberately not subclasses, identity the only coercion | `tests/v1/test_probability_kinds.py` | Not yet wired into the V0 surface syntax: it is a V1 kernel type, not a `Quantity`-style annotation |

## Deliberately not done — each condition unmet by measurement

| proposal | condition for adoption | measured status |
|----------|------------------------|-----------------|
| Pratt / precedence-climbing parser | a demonstrated precedence or associativity failure | **5/5 probes correct** — `1+2*3`, `2^3^2`, `-2^2`, `10-3-2`, `12/3/2` |
| locally nameless binders | a demonstrated binding defect | none found; alpha-equivalence property-tested over every binder form |
| red-green tree | an incremental IDE or large-document reparse requirement | none exists |
| e-graph | five conditions in `EGRAPH_ADOPTION_GATE.md` | none met; no syntax has passed the acquisition gate |
| cryptographic canonicalisation | — | SHA-256 over alpha-normalised JSON already satisfies all four identity rules |
| probability monads | lazy/infinite-dimensional Bayesian structure | out of scope for this milestone |

## Verification

| command | result |
|---------|--------|
| `./scripts/conformance.sh` | **PASS**, all 8 stages, **no override** |
| `pytest` | **1531 passed**, 4 skipped, 1 xfailed |
| front-end fuzz battery | 800 inputs, **0 hangs, 0 crashes** |
| generated SymPy execution | every example module runs, **0 failures** |
| Lean gate against real Lean 4.32.2 | false theorem rejected; true theorem verified with `axioms: []` |
| `hml check examples/*/*.hml` | 8/8; golden hashes unmoved |

## Open, and carried forward rather than closed

- **The minting protocol is gameable and fails its own criterion.** A seeded registry
  admitted three copies of one concept. Runnable reproduction in `audits/V1_RED_TEAM.md` §3.
- **V0 cannot express 38 of the 60 ablation problems**, so the V0 control is disadvantaged
  by construction on that corpus.
- **Mathlib absent**, so the Lean support matrix is mostly library-gated rather than
  category-gated — a distinction the matrix keeps explicitly separate.
- Three of the four syntax candidates are still **provisional engineering forms**; none is
  frozen and no winner is declared.

## Next

Freeze the supported V1 compiler, then run the four-syntax Gemma acquisition tournament.
The report must state whether at least one syntax clears **95% repaired parse success** and
**90% semantic preservation**.
