# V1 Concept Kernel — HML-V1-CONCEPT-001

Branch `hml-v1-concept-kernel`. V0 is preserved unchanged at tag `hml-v0-baseline`.
Supersedes `V1_KERNEL.md` as the implementation specification; that document remains the
narrative design rationale.

## 0. The mandate this work is licensed under

`docs/evaluation/V1_GATE_DECISION.md` passed the gate on **two criteria only**:

- compiler feedback gives a meaningful reliability gain — parse rate 73.3% → 85.7% and
  50.0% → 93.3%, encoding fidelity +0.065 CI [0.006, 0.136], replicated;
- the pilot exposed a specific representational weakness V1 can test — 27–50% of encodings
  do not compile, and the representation does not change what the model computes.

It did **not** pass on answer accuracy, semantic preservation, or measured failure
reduction. So:

> **V1 may claim to make errors catchable. It may not *yet* claim to make reasoning
> better** — that claim is **unproven, not refuted**.

Zero-shot Hamiltonian did not improve answer accuracy on this small, low-discrimination pilot. The experiment was underpowered and had a severe ceiling effect. A design whose minimum
detectable effect was ~33 percentage points cannot refute anything. HML-EVAL-002 is the
first adequately powered test.

The objective is not to expand Hamiltonian into a universal language. It is to determine
whether typed concept creation, morphology, transformation tracking, epistemic calibration
and discourse state produce a **measurable** advantage over V0 and matched structured
English. The milestone is not the number of new words.

## 1. The six layers

| # | layer | module | owner |
|---|-------|--------|-------|
| 1 | typed concept registry | `v1/registry.py` | Registry agent |
| 2 | concept-minting protocol | `v1/minting.py` | Registry agent |
| 3 | semantic morphology | `v1/morphology.py` | Registry agent |
| 4 | transformation & inference edges | `v1/transformation.py` | Transformation agent |
| 5 | epistemic-status types | `v1/epistemic.py` **(contract, Lead Architect)** + `v1/epistemic_checks.py` | Lead / Transformation agent |
| 6 | discourse-state types | `v1/discourse.py` | Transformation agent |

`v1/epistemic.py` and `spec/concept_registry.schema.json` are the **semantic contract**,
owned by the Lead Architect. No agent may modify them.

## 2. What the contract already enforces

Implemented and verified before any agent was spawned:

```
r1 = EpistemicClaim(FAIL_TO_REJECT, "H0", {"null":"H0","alpha":"0.05","p_value":"0.18"})

r1.justification            -> Evidence
r1.discharges_goals()       -> False
r1.may_be_used_as(Proof)    -> (False, "absence of evidence against a hypothesis is not
                                 evidence for it; failing to reject H0 does not prove H0")
```

and rendered in controlled English:

> "The test did not reject H0 at the 0.05 level (p = 0.18). **This is not evidence that H0
> is true.**"

The caveat is carried by the *type*, not by good manners. `fail_to_reject` can therefore
never compile into `H0 is proved`, `there is no effect`, or `H0 is true`.

Context is mandatory and verified: `with_high_probability` without a bound or regime,
`model_conditional` without a model, and `fail_to_reject` without alpha and a p-value are
all rejected as ill-formed rather than accepted and quietly ignored.

## 3. Concept registry — a name is only a handle

Schema: `spec/concept_registry.schema.json`. Required per concept: canonical identifier,
namespace, version, aliases, type signature, domain, codomain, formal definition,
parameters with **roles** (not positions), constraints, invariants, equivalences,
implications, counterexamples, proof obligations, computation methods, backend support,
dependencies, provenance, admission status.

Lifecycle: `proposed → defined → checked → admitted`, terminal `rejected | duplicate |
deprecated`. A concept may be cited by another only once **admitted**. Dependencies must
themselves be admitted; cycles are rejected.

Each claim carries its own status — `proved | tested | conjectured | unsupported` — so a
report cannot present a conjecture as a theorem, and `discharged_by: null` means *not
established*. Numerical agreement is `tested`, never `proved`.

## 4. Minting — the anti-word-generator rule

A proposed concept does not enter the trusted registry. Before admission the system must
search the registry for equality, equivalence, renaming, specialisation and
generalisation; require a valid type and formal definition; verify constraints; generate
obligations for claimed properties; test examples and counterexamples; and record which
claims are proved, tested, conjectured or unsupported.

> **A concept survives only if it compresses recurring mathematical structure without
> losing semantics.** A candidate that type-checks but abbreviates nothing is a synonym and
> is returned `duplicate`.

`compresses` is a required field and `compression_demonstrated` is a required admission
check. This is the clause that stops the registry becoming a vocabulary list.

## 5. Morphology — declared relations, never string concatenation

Roles: `.law .density .logdensity .sample .parameter .property .predicate .transform
.inverse .measure .estimator .estimand .proof .counterexample`.

A derived member exists **only when its type and semantics are declared for that concept**.
`Normal.density` resolves because the Normal distribution admits a density. An arbitrary
concept does **not** automatically receive `.density`; asking for an undeclared role raises
rather than fabricating one.

`vary → variance` is not a safe grammatical rule and neither is `estimate → estimator`.
`estimator`, `estimate` and `estimation procedure` are three independently declared types,
which makes "the estimate is unbiased" a type error — unbiasedness is a property of the
estimator, not of a number.

## 6. Transformation and inference — three relations, not one

`yields`, `implies` and `is equivalent to` are **not synonyms**. Distinct edge kinds with
no coercion: algebraic transformation · logical implication · equivalence · approximation ·
numerical computation · statistical inference · definition expansion · theorem application.

Every operation declares the side conditions it generates: `divide_through` requires a
non-zero divisor, `take_log` a positive argument, `differentiate` differentiability, and
`square_both_sides` records a **weakening** rather than an equivalence. That is where the
layer earns its place — an algebra step that silently divides by zero is precisely what V0
cannot catch.

## 7. Discourse — only what changes the reasoning state

`goal subgoal pending_obligation consider_case return_to_goal established remains_to_show
converse_goal dependency_notice`.

Executable: a goal opens an obligation; `established` closes it and **requires a
Proof-justified claim**; case splits are checked for exhaustiveness; open goals are
reported at end of module.

"We now show" → `goal`. "It remains to establish" → `pending_obligation`. "Consider first
the special case" → `consider_case`. "The converse need not hold" → `converse_goal` or a
counterexample obligation. **"For completeness" stays out of the kernel** — it alters no
obligation and no dependency, so it is a renderer feature.

## 8. Backends

Established by measurement in the V0 pilot and carried forward, not re-litigated:

- **Stan** cannot express strict positivity (`real<lower=0>` admits 0), so every family
  with a `PositiveReal` role cannot round-trip; only Uniform, Binomial and Bernoulli can.
  It also loses observed values and destroys interleaved declaration order.
- **Lean** silently loses probability laws, and the reconstruction still compiles — only a
  content-hash comparison detects it. An unproved theorem is **never** labelled verified.
- **SymPy/Python** give numerical evidence, which is `tested`, not `proved`.

No general HML↔Stan or HML↔Lean round-trip equivalence is claimed. The support matrix is
`docs/design/V1_BACKEND_SUPPORT_MATRIX.md`.

## 9. Required examples

**RobustCentre** — `Dataset[Real] × LossFunction[Real, Real] -> ArgminSet[Real]`, the set
of minimisers of aggregate loss. Obligations: nonempty admissible domain; nonnegative loss;
existence conditions; measurability only where probabilistic integration requires it;
squared-loss minimisers correspond to the sample mean; absolute-loss minimisers correspond
to the set of sample medians. **Uniqueness must not be claimed without sufficient
conditions** — the codomain is an `ArgminSet`, not a point, precisely because the median is
not unique for even-sized samples.

**BayesianRegression** — typed observations, parameter domains, priors, likelihood,
conditional structure, dimensional obligations, posterior query, credible region.
`posterior is Proper` is a **proof obligation**, not an assertion, unless the conditions
are actually verified.

## 10. Falsifiability

Every layer carries a kill criterion (`spec/v1/semantic_objects.yaml::kill_criteria`) and
is dropped independently if it fails. Predicted survival order, recorded in advance so a
surprise is visible as one: epistemic (most likely) → discourse → morphology → registry →
transformation → inference (least likely; checking inference chains without a prover
approaches re-implementing one, which the founding directive forbids).

**Hard gate:** no V0-vs-V1 comparison may be reported until V1 parse rate reaches ≥ 90%.
A language the model cannot write is not being tested — and V1 is *larger* than a language
already written unparseably 27–50% of the time. That is the principal risk of this
milestone, not a footnote to it.
