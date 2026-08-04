# Backend Contract — Stan, SymPy, Lean 4

Author role: Backend and Interoperability Engineer
Status: v0, tracks `docs/design/V0_DESIGN_FREEZE.md` (frozen)
Scope: `src/hamiltonian_lang/backends/{stan,sympy,lean}.py`

This document is the per-construct fidelity contract for the three execution and
verification backends. Its purpose is to make translation loss *auditable* rather than
discoverable-by-accident. Every row states what a construct becomes, how faithful the
result is, and why the target cannot do better.

---

## 0. How to read this, and what has actually been verified

**Fidelity vocabulary** — the same three words the backend API uses
(`Backend.drop` / `.approximate` / `.weaken`):

| Label | Meaning |
|-------|---------|
| **exact** | The target construct denotes the same thing. Nothing is reported. |
| **weakened** | The target expresses less than the source. The information is still recoverable by a reader who knows the convention, but the target does not *carry* it. |
| **approximated** | The target expresses something *different but close*, by a stated rewrite. The rewrite is named in the loss report. |
| **dropped** | The target cannot express it at all. Nothing is emitted except a comment recording what was lost. |

`BackendResult.faithful` is `False` whenever any of the three lower labels fired.
**Across all eight files in `examples/`, no backend returns `faithful == True`.** That
is asserted by
`tests/backends/test_{stan,sympy,lean}.py::test_no_example_is_losslessly_expressible_in_*`
and is the expected result, not a defect.

**Verification status — read this before trusting any "valid output" claim:**

| Target | Toolchain available? | What was actually verified |
|--------|----------------------|----------------------------|
| Stan | **No.** `stanc` is not installed and is never invoked. | Structural only: block presence, Stan's required block order, brace balance, statement termination, and that every name used in the `model` block is declared above it. A program passing these could still be rejected by a real `stanc`. |
| SymPy | **Yes.** `sympy 1.14.0` installed into `.venv`. | The emitted Python is written to a real file and executed. Execution proves it is valid Python and that every SymPy call is well-formed. Selected expressions are then compared against hand-written SymPy (kinetic energy, the regression predictor's shape, the concept's own invariant). Execution does **not** prove semantic equivalence in general. |
| Lean | **No.** `lean`/`lake`/Mathlib are not installed and are never invoked. | Structural only: namespace balance, paren balance, every theorem closed with `sorry`, no tactic other than `sorry`, every binder typed, every reference bound, and quantifier nesting order preserved. Nothing here establishes that the file elaborates. |

---

## 1. Stan

Target: the Stan modelling language (`data`/`transformed data`/`parameters`/
`transformed parameters`/`model`/`generated quantities`).

Stan is the only *executable* target of the three, which makes silent loss most
dangerous here: a wrong Stan program still compiles, still runs, and still returns
numbers with credible intervals around them.

### 1.1 Statements

| HML construct | Stan construct | Fidelity | Reason |
|---|---|---|---|
| `module <Name>` | header comment | dropped | Stan has no module or namespace concept. The name is preserved only as provenance. |
| `obs x : T` | `data { T x; }` | weakened | The declaration kind survives as block membership, but Stan does not record *why* a quantity is data. |
| `obs x : T = v` | `data { T x; }` + header comment `x = v` | weakened | Stan takes data values from the data file, never from the program text. The literal is recorded in a comment and **must be supplied at run time**; the emitted program alone is incomplete. |
| `const c : T` | `data { T c; }` | weakened | Stan has no separate constant block; a fixed quantity is supplied as data. The "this never varies" claim is not encoded. |
| `index N : Natural` | `data { int<lower=0> N; }` | weakened | Correct as a Stan array extent, but Stan does not know it is an index rather than an ordinary count. |
| `param p : T` | `parameters { T p; }` | exact¹ | ¹ Modulo the type mapping in §1.2, which is not always exact. |
| `var v : T` | `parameters { T v; }` | weakened | An unobserved quantity is a Stan parameter, which is right for a model, but HML's `var` also covers non-probabilistic free variables (see `constrained_optimisation.hml`) for which "parameter" is a misnomer. |
| `def f := e` (no params, data-only body) | `transformed data { T f = e; }` | exact |  |
| `def f := e` (no params, body mentions a parameter) | `transformed parameters { T f = e; }` | exact |  |
| `def f(a, b) := e` | `functions { T f(...) { return e; } }` | approximated | HML `def` parameters may be untyped; Stan requires a type, so `real` is assumed and reported. |
| `law X ~ D(...)` | `model { X ~ d(...); }` | weakened | See §1.3. Argument roles become positions. |
| `prior X ~ D(...)`, `likelihood Y \| X ~ D(...)` | `model { X ~ d(...); }` | weakened | Stan's `~` records **neither** the role (prior/likelihood/law) **nor** the conditioning set. `y \| x, beta, sigma ~ ...` and `y ~ ...` produce identical Stan; the conditioning is left implicit in which symbols appear on the right. |
| `require P` | comment `// require: P (NOT ENFORCED)` | **dropped** | Stan cannot state a hard constraint on parameters. The two available encodings are a `<lower=>/<upper=>` declaration bound (only expressible for simple interval constraints on a single symbol) and `reject()` (which truncates the posterior discontinuously and changes the model). Neither is a translation of `x + y >= 10`. |
| `assume P` | comment | dropped | Stan has no assumption context. |
| `prove P` | comment `// prove: P (NOT PROVED)` | dropped | Stan is a probabilistic programming language, not a prover. |
| `check <proposition>` | comment | dropped | Stan has no proposition type. |
| `check dimension e = D` | comment | dropped | Stan is dimensionless. |
| `minimise e` / `maximise e` | comment `(NO STAN ENCODING)` | dropped | The Stan *language* has no objective statement. Stan interfaces can maximise the log density (`optimize`), but that is a different objective; substituting it would be a fabrication. |
| `solve x y` | comment | dropped | `algebra_solver` solves a user-supplied equation system, which is not what `solve` means here. |
| `infer posterior \| mle \| map \| expectation \| variance` | comment naming the interface method | weakened | An inference query is an instruction to the *interface* (CmdStan / CmdStanPy / RStan), not a statement in the Stan language, so it cannot appear in the program at all. |
| `concept C ... end` | nothing | dropped | Stan has no user-defined type, class or concept mechanism. Parameters, transforms, invariants, examples and counterexamples all vanish. |
| `forall` / `exists` | placeholder comment | dropped | Stan has no quantifier. A *bounded* universal over a finite index could sometimes unroll into a `for` loop, but the examples quantify over `Real`, which cannot be enumerated. |

### 1.2 Types

| HML type | Stan declaration | Fidelity | Reason |
|---|---|---|---|
| `Real` | `real` | exact | |
| `PositiveReal` | `real<lower=0>` | weakened | HML's `PositiveReal` is **open** at 0; Stan's `<lower=0>` is closed. The emitted constraint admits 0, which the HML type does not. |
| `NonNegativeReal` | `real<lower=0>` | exact | |
| `Probability` | `real<lower=0,upper=1>` | exact | Both are the closed unit interval. |
| `Natural` | `int<lower=0>` | exact | |
| `PositiveNatural` | `int<lower=1>` | exact | |
| `Integer` | `int` | exact | |
| `Rational` | `real` | approximated | Stan has no exact rational type; exactness is lost to floating point. |
| `Bool` | `int<lower=0,upper=1>` | approximated | Stan has no boolean type. |
| `Quantity[D]` | `real` (carrier of the base scalar) | weakened | Stan is dimensionless. The whole rational-exponent vector is discarded, so dimensionally invalid Stan arithmetic is well-typed. |
| `Vector[Real, n]` | `vector[n]` | exact | |
| `Vector[PositiveReal, n]` | `vector<lower=0>[n]` | weakened | Same open/closed mismatch as the scalar case. |
| `Vector[Natural, n]` | `vector[n]` | approximated | Stan's `vector` elements are always real; integrality is lost. |
| `Matrix[Real, m, n]` | `matrix[m, n]` | exact | |
| `RandomVariable[T]` | declaration of `T` | weakened | Stan does not distinguish a random variable from a value of its support. The three-way separation of `T`, `RandomVariable[T]` and `Distribution[T]` — enforced structurally by the HML checker — collapses to two. |
| `Distribution[T]` | nothing | dropped | Stan has no first-class distribution value; a density can only appear to the right of `~`. |
| `Tensor[T, ...]` | nothing | dropped | No rank-n tensor type; an array-of-matrices convention would have to be invented. |
| `Set[T]`, `Function[..]`, `Predicate[..]`, `Proposition`, concept types | nothing | dropped | None exist in Stan. |

### 1.3 Distributions — the role-to-position table

**This is the point of the Stan backend.** HML labels every distribution argument by
role; Stan takes them positionally. A wrong entry here produces a Stan program that
compiles, runs, and is silently wrong — exactly the failure mode the language exists to
prevent. The table lives in `STAN_DISTRIBUTIONS`, is cross-checked against
`type_system/distributions.py` by `audit_distribution_table()`, and every ordering below
is separately pinned in `tests/backends/test_stan.py::TestDistributionTable`.

| HML family (roles) | Stan call | Fidelity | Reason |
|---|---|---|---|
| `Normal(location, scale)` | `normal(location, scale)` | weakened | Order exact. Stan's second argument is the **standard deviation**, matching HML's `scale`. The role labels themselves are gone: a reader of the Stan file must recover them from the manual. |
| `HalfNormal(scale)` | `normal(0, scale)` | **approximated** | Stan has no `half_normal`. The idiom truncates via the *declaration* (`real<lower=0> s;`), not the statement. If the sampled variable's HML type induces no lower bound, the emitted model is a **full normal** — a genuine semantic difference, reported as *dropped*, not approximated. |
| `LogNormal(location, scale)` | `lognormal(location, scale)` | weakened | Order exact; roles lost. |
| `StudentT(degrees_of_freedom, location, scale)` | `student_t(dof, location, scale)` | weakened | Order exact; roles lost. |
| `Cauchy(location, scale)` | `cauchy(location, scale)` | weakened | Order exact; roles lost. |
| `Uniform(lower, upper)` | `uniform(lower, upper)` | weakened | Order exact; roles lost. |
| `Beta(alpha, beta)` | `beta(alpha, beta)` | weakened | Order exact; roles lost. |
| `Bernoulli(prob)` | `bernoulli(prob)` | weakened | |
| `Binomial(trials, prob)` | `binomial(trials, prob)` | weakened | Order exact — the **count** first, the probability second. |
| `Poisson(rate)` | `poisson(rate)` | weakened | Stan's `poisson` is rate-parameterised, matching HML. |
| `Exponential(rate)` | `exponential(rate)` | weakened | Stan's `exponential` is rate-parameterised (not mean), matching HML. |
| `Gamma(shape, rate)` | `gamma(shape, rate)` | weakened | Stan's `gamma` is shape-**rate**, matching HML. |
| `InverseGamma(shape, scale)` | `inv_gamma(shape, scale)` | weakened | Stan's `inv_gamma` is shape-**scale**, matching HML. |
| `Dirichlet(concentration)` | `dirichlet(concentration)` | weakened | |
| `Categorical(probs)` | `categorical(probs)` | **weakened** (extra) | Stan's categorical outcomes are **1-based** indices into the simplex; HML's support is `Natural`, which includes 0. The index origin is not preserved. |
| `NormalVector(location, scale)` | `normal(location, scale)` (vectorised) | **approximated** | The i.i.d.-with-shared-scale structure is implied by Stan's broadcasting rules rather than stated. |

Consequence worth stating explicitly: `Normal(location := mu, scale := sigma)` and
`Normal(scale := sigma, location := mu)` produce **byte-identical** Stan. Role labels,
not source order, determine position. This is asserted directly in
`test_normal_order_is_determined_by_role_not_by_source_order`.

---

## 2. SymPy

Target: a runnable Python module importing `sympy`. The emitted file leaves its results
in a fixed set of names: `definitions`, `requirements`, `claims`, `assumptions`,
`type_constraints`, `objective`, `objective_direction`, `solve_targets`,
`symbols_by_name`.

### 2.1 Statements

| HML construct | SymPy construct | Fidelity | Reason |
|---|---|---|---|
| `module <Name>` | module docstring | dropped | No namespace mechanism for symbols. |
| `var`/`param`/`const`/`obs`/`index x : T` | `sympy.Symbol('x', <assumptions>)` | weakened | SymPy has exactly one kind of symbol. The declaration kind is a claim about the model's epistemology and has no encoding. |
| `obs x : T = v` | symbol + `requirements.append(sympy.Eq(x, v))` | weakened | There is no "observed" binding; the value is recorded as an equation rather than substituted, so the symbol stays free. |
| `def f := e` | `f = <expr>`, `definitions['f'] = f` | exact | The expression tree maps 1:1. |
| `def f(a) := e` | `f = sympy.Lambda((a,), <expr>)` | approximated | SymPy `Lambda` arguments are untyped, so any refinement on a parameter is lost. |
| `law` / `prior` / `likelihood` | comment only | **dropped** | See §2.4 — this is a deliberate choice, not an omission. |
| `require P` | `requirements.append(<relational>)` | exact¹ | ¹ The relational object is exact; that it is an *obligation* rather than a fact is conveyed only by which list it lands in. |
| `assume P` | `assumptions.append(<relational>)` | weakened | SymPy has no assumption *context*: nothing downstream uses the entry as a hypothesis. It is inert data. |
| `prove P` | `claims.append(<relational>)` | weakened | The statement is exact; SymPy is not a prover, so it is recorded, not discharged (§8). |
| `check <proposition>` | `claims.append(...)` | weakened | Nothing in the generated file performs the check. |
| `check dimension` | comment | dropped | See §2.4. |
| `minimise e` / `maximise e` | `objective = <expr>` + commented setup | weakened | The objective **expression** is preserved exactly. SymPy has no constrained optimiser; with `require` constraints present the correct system is the KKT conditions, which the backend will not fabricate. |
| `solve x y` | `solve_targets = [x, y]` + comment | weakened | `sympy.solve` needs a system of *equations*; the constraints in the examples are inequalities, and SymPy has no multivariate inequality solver. No solve call is emitted. |
| `infer <query>` | comment | dropped | The laws the query ranges over were themselves dropped; there is nothing to compute over. |
| `concept C` — `parameter` | mangled `C__p` symbol | weakened | SymPy has no namespace, so the concept scope is flattened by name-mangling (injective, but the scope structure is gone). |
| `concept C` — `transform t(u) := e` | `C__t = sympy.Lambda((u,), e)` | exact¹ / approximated | ¹ The expression is exact and the Lambda is callable; the *membership* in `C` is only a naming convention. Parameter assumptions are derived from the declared type when `ConceptMember.params` carries one (D-015); when the type slot is `None` the symbol gets no assumptions and that is reported as an approximation naming the parameter. |
| `concept C` — `invariant` | `claims.append(...)` | weakened | An inert relational; SymPy will not check it against the concept. |
| `concept C` — `example` / `counterexample` | bare relational object | weakened | The *witness* status — and, for a counterexample, that it is meant to refute something — has nowhere to attach. |
| `concept C extends P` | nothing | dropped | No inheritance encoding. |
| `forall` / `exists` / `exists unique` | nothing | **dropped** | See §2.4. |

### 2.2 Types → assumptions

SymPy's assumption system is a fixed predicate set. Where it has a predicate the
refinement is exact; where it does not, the residue is pushed into `type_constraints`,
which nothing enforces.

| HML type | SymPy declaration | Fidelity | Reason |
|---|---|---|---|
| `Real` | `Symbol(real=True)` | exact | |
| `Rational` | `Symbol(rational=True)` | exact | |
| `Integer` | `Symbol(integer=True)` | exact | |
| `Natural` | `Symbol(integer=True, nonnegative=True)` | exact | |
| `PositiveNatural` | `Symbol(integer=True, positive=True)` | exact | |
| `NonNegativeReal` | `Symbol(real=True, nonnegative=True)` | exact | |
| `PositiveReal` | `Symbol(real=True, positive=True)` | exact | |
| `Probability` | `Symbol(real=True, nonnegative=True)` + `type_constraints.append(Le(x, 1))` | **weakened** | SymPy assumptions have no upper-bound predicate. Half of the type becomes an assumption the solver honours; the other half becomes a relational that nothing enforces. |
| `Bool` | `Symbol()` | approximated | No boolean-valued symbol interoperates with the relational algebra used here. |
| `Quantity[D]` | symbol with the base scalar's assumptions | weakened | `sympy.physics.units` works in *units*; HML dimensions carry no unit, so mapping would require inventing one per dimension (forbidden by §8). |
| `Vector[T, n]` | `MatrixSymbol(name, n, 1)` | approximated | SymPy has no vector type; an n×1 column matrix is the nearest thing. Element refinements are additionally **dropped** — `MatrixSymbol` carries no element assumptions. |
| `Matrix[T, m, n]` | `MatrixSymbol(name, m, n)` | exact¹ | ¹ Shape is exact, including symbolic extents. Element refinements are dropped for the same reason. |
| `RandomVariable[T]` | plain symbol over `T` | weakened | No measurable-function type. Randomness, and the separation between `RandomVariable[T]` and `T`, are lost. |
| `Distribution[T]` | nothing | dropped | |
| `Tensor`, `Set`, `Function`, `Predicate`, `Proposition`, concept types | nothing | dropped | No declarable SymPy counterpart usable in this algebra. |

### 2.3 Expressions

| HML | SymPy | Fidelity | Reason |
|---|---|---|---|
| numeric literal | `sympy.Rational('<raw>')` | exact | **Design choice.** `0.5` is an exact decimal in the source and the target is a *symbolic* algebra system; `sympy.Float` would introduce a binary inexactness the source does not have. Recorded as a note, not as loss, because the value is preserved exactly. |
| `+ - * /` | `+ - * /` | exact | |
| `^` | `**` | exact | |
| `@` | `*` | weakened | HML's `@` is a dedicated matrix/vector product; SymPy overloads `*`, so the operator no longer distinguishes it from scalar multiplication. |
| `= != < <= > >=` | `Eq Ne Lt Le Gt Ge` | exact | |
| `and or implies iff` | `And Or Implies Equivalent` | exact | |
| `not` | `Not` | exact | |
| `exp log sqrt sin cos tan abs` | `sympy.*` | exact | |
| unknown call `f(x)` | `sympy.Function('f')(x)` | approximated | An uninterpreted function has no defining equation. |
| indexing `x[i]` | `x[i]` | weakened | `MatrixSymbol` subscripts are 0-based and require an integer index; HML fixes no index origin, so the subscript may be off by one. |

### 2.4 The three deliberate refusals

**Distributions.** `sympy.stats` exists and does have `Normal`, `Beta` and `Binomial`.
It has **no** representation of the prior/likelihood/law distinction, of a conditioning
set, or of an inference query. Emitting `sympy.stats.Normal(...)` would reproduce the
family and its parameters while silently discarding the rest of the statement, while
*looking* complete. Every law is therefore dropped with a comment recording exactly what
was lost. This is the honest answer and is asserted by
`test_distributions_are_dropped_not_faked`.

**Quantifiers.** SymPy has no first-order quantifier. `sympy.Q` is a predicate
namespace, not a binder. Consequence, asserted in
`test_quantifier_scope_pair_is_indistinguishable_in_sympy`: `quantifier_scope.hml` and
`quantifier_scope_reversed.hml` — which differ only in nesting order, one true over the
reals and one false — produce **identical** SymPy output. The backend reports this as
loss rather than letting a reader believe the order survived.

**Dimensions.** `sympy.physics.units` works in units, not in unit-free rational-exponent
vectors. §8 says v0 does not reconcile units; inventing a unit per dimension would be a
design decision, not a translation.

---

## 3. Lean 4

Target: Lean 4 **statement skeletons** with Mathlib. Per `V0_DESIGN_FREEZE.md` §8, no
proof search of any kind is performed. Every obligation is closed with `sorry`, and no
tactic other than `sorry` is ever emitted (asserted by
`test_no_tactic_other_than_sorry_is_emitted`).

### 3.1 The refinement encoding, and why

Lean offers two ways to carry `sigma : PositiveReal`:

1. a subtype, `sigma : {x : ℝ // 0 < x}`;
2. a carrier plus a hypothesis, `sigma : ℝ` with `h_sigma_pos : 0 < sigma`.

**This backend uses (2).** Reasons, in order of weight:

* HML expressions are written over the *carrier*. Under (1) every use site needs
  `sigma.val` or a coercion, and a three-symbol HML expression becomes a Lean expression
  whose shape no longer resembles the source. A skeleton a human cannot recognise is a
  skeleton nobody will discharge.
* Mathlib's own lemmas overwhelmingly take the hypothesis form `(hx : 0 < x)`, so a
  skeleton written this way can be attacked with Mathlib directly.
* HML's scalar order is a **poset** — `Probability` and `PositiveReal` are incomparable
  (`V0_DESIGN_FREEZE.md` §4). Subtypes would demand a coercion lattice that does not
  exist. Separate hypotheses compose freely; subtypes do not.

The cost is real and is reported as a **weakening on every refined declaration**: a
hypothesis is not part of the type, so nothing in Lean stops a later edit from applying
a lemma to `sigma` with the positivity hypothesis out of scope. HML's type system would.

### 3.2 Statements

| HML construct | Lean construct | Fidelity | Reason |
|---|---|---|---|
| `module <Name>` | `namespace <Name> ... end <Name>` | exact | |
| `var`/`param`/`const`/`obs`/`index x : T` | `variable (x : T')` | weakened | Lean's `variable` is a single mechanism. Whether `x` is observed data, a parameter to be inferred, or a fixed constant has no encoding. |
| `obs x : T = v` | `def x : T' := v` | weakened | The value is exact; the "observed" status is not. |
| refinement on a declared symbol | `variable (h_x_pos : 0 < x)` etc. | weakened | See §3.1. |
| `def f := e` | `def f : T' := e` | exact¹ | ¹ Lean 4 auto-binds `variable`s referenced in the body, so the free symbols are captured. |
| `def f(a) := e` | `def f (a : ℝ) : ℝ := e` | approximated | HML `def` parameters may be untyped; Lean requires a type, so `ℝ` is assumed. |
| `require P` | `theorem require_N : P := by sorry` | **weakened** | An HML `require` is a *constraint the model must satisfy* — an obligation over free variables. Lean has no such statement form. Read literally the emitted theorem may be false (`require x >= 0` for a free real `x` is), and a Lean reader cannot recover from the skeleton that this was a constraint rather than a claim. |
| `assume P` | `variable (h_assume_N : P)` | exact | A hypothesis is exactly what an assumption is. |
| `prove P` | `theorem claim_N : P := by sorry` | weakened | The statement is preserved exactly; the proof is not attempted (§8). |
| `check <proposition>` | `theorem check_N : P := by sorry` | weakened | The HML checker may already have discharged it; that fact does not transfer. |
| `check dimension` | comment | dropped | No dimensional analysis without a units library and a chosen unit per base dimension (§8). |
| `law` / `prior` / `likelihood` | comment | **dropped** | See §3.4. |
| `infer <query>` | comment | dropped | Presupposes the laws, which were dropped. |
| `minimise` / `maximise` | comment | dropped | Mathlib can state `IsMinOn f s a`, but only relative to a set `s` and a witness `a`, neither of which the HML statement supplies. Inventing them would state a different theorem. |
| `solve x y` | comment | dropped | The closest faithful form is an existence theorem, but *which* existential is not determined by `solve` alone. |
| `forall x : T . P` | `∀ x : T', P` | **exact** | Nesting order preserved structurally — the emitter recurses on the body and never reorders. |
| `exists y : T . P` | `∃ y : T', P` | **exact** | |
| `exists unique z : T . P` | `∃! z : T', P` | **exact** | |
| `concept C` — `parameter` | `variable (C_p : T')` (+ refinement hypotheses) | weakened | Lean *has* structures and classes, which would be the faithful encoding, but that turns every member into a field access and every invariant into a field of a proposition-carrying structure. This backend flattens by prefixing instead, so `C` is not a Lean object and its members are only conventionally related. |
| `concept C` — `transform t(u) := e` | `def C_t (u : T') : ℝ := e` | exact / approximated | The parameter type is taken from `ConceptMember.params` when present (D-015). When the type slot is `None`, Lean still requires one, so `ℝ` is assumed and that is reported as an approximation naming the parameter. |
| `concept C` — `invariant` / `property` | `theorem C_inv : P := by sorry` | weakened | The statement is preserved exactly, but it becomes a free-standing theorem rather than a property *of the concept*: nothing ties it back to a concept object, because the concept was flattened. Proof not attempted (§8). |
| `concept C` — `example` / `counterexample` | comment | **dropped** | Stating a witness needs an existential over the concept *as an object*; the concept was flattened rather than objectified, so there is nothing to quantify over. |
| `concept C extends P` | nothing | dropped | No inheritance encoding. |

### 3.3 Types

| HML type | Lean type | Fidelity | Reason |
|---|---|---|---|
| `Real` | `ℝ` | exact | |
| `Rational` | `ℚ` | exact | |
| `Integer` | `ℤ` | exact | |
| `Natural` | `ℕ` | exact | `ℕ` already excludes negatives, so no hypothesis is needed. |
| `PositiveNatural` | `ℕ` + `0 < x` | weakened | `ℕ` contains 0. |
| `PositiveReal` | `ℝ` + `0 < x` | weakened | See §3.1. |
| `NonNegativeReal` | `ℝ` + `0 ≤ x` | weakened | See §3.1. |
| `Probability` | `ℝ` + `0 ≤ x` + `x ≤ 1` | weakened | See §3.1. Both bounds are emitted. |
| `Bool` | `Bool` | exact | |
| `Proposition` | `Prop` | exact | |
| `Quantity[D]` | `ℝ` | weakened | Dimension dropped, so dimensionally invalid Lean arithmetic becomes well-typed. |
| `Vector[T, n]` | `Fin n → T'` | weakened | Total function on a finite index type. Lean's `Fin` carries a **bounds proof**, so every translated subscript acquires a proof obligation that did not exist in the source, where shapes are checked nominally (§8). |
| `Matrix[T, m, n]` | `Matrix (Fin m) (Fin n) T'` | weakened | Mathlib's `Matrix` is dependently typed; HML v0 is not. They agree on these examples, not in general. |
| `Set[T]` | `Set T'` | exact | |
| `Function[A -> B]` | `A' → B'` | exact | |
| `Predicate[A]` | `A' → Prop` | exact | |
| `RandomVariable[T]` | nothing | **dropped** | Lean *can* express a measurable function (`Ω → ℝ` plus `Measurable`), but the probability space `Ω` is named nowhere in the HML source, so declaring one would be invention. Declaring it as `T` instead would conflate `RandomVariable[T]` with `T`, which the type system explicitly forbids (§4). Asserted by `test_random_variable_type_is_dropped_not_conflated`. |
| `Distribution[T]` | nothing | dropped | A distribution is a measure; the scaffolding is not determined by the source. |
| `Tensor[T, ...]` | nothing | dropped | No single Mathlib type matches; choosing one would be a design decision. |
| concept types | nothing | dropped | Concepts are flattened, not objectified. |

Operators: `+ - * /` and `^` map directly; `@` becomes `Matrix.mulVec` when the left
operand's resolved HML type is a matrix (weakened — Mathlib's `mulVec` fixes operand
orientation, HML's `@` does not) and falls back to plain multiplication with an
*approximated* report otherwise. Comparisons map to `= ≠ < ≤ > ≥`; connectives to
`∧ ∨ → ↔`; `not` to `¬`. `exp/log/sqrt/sin/cos/tan` map to `Real.*`.

### 3.4 The refusal to encode probability

`law`, `prior`, `likelihood` and `infer` are **dropped**, not approximated. A faithful
Lean encoding needs a measurable space on the support, a `MeasureTheory.Measure`, a
density, and a proof that it integrates to one. None of that is determined by a family
name plus role labels. The backend emits a comment recording the full statement and
reports the drop; it invents nothing. `test_probability_laws_are_reported_as_dropped`
additionally asserts that no `MeasureTheory`/`ProbabilityTheory`/`Measure`/`pdf` token
appears in the emitted *code* — only in comments describing what was lost.

---

## 4. What each target can express that Hamiltonian Lang cannot

An honest contract runs in both directions. HML v0 is not a superset of any of these
targets, and in several places it is plainly poorer.

### 4.1 Stan

* **Vectorised sampling statements.** `y ~ normal(X * beta, sigma)` with `y` a
  `vector[N]` is a single statement standing for N conditionally independent draws, with
  broadcasting rules that make the shapes work out. HML has to spell this as a separate
  family (`NormalVector`) and still cannot say "these N draws are conditionally
  independent given the location vector" — the i.i.d. structure is in the family's
  documentation note, not in the type.
* **Truncation and censoring.** `y ~ normal(mu, sigma) T[a, b];` and the `_lcdf`/`_lccdf`
  idioms express truncated and censored likelihoods directly. HML v0 has no notion of a
  truncated law at all.
* **Direct log-density manipulation.** `target += ...` lets a Stan user write a density
  that has no name. HML v0 forbids user-defined families with custom densities (§8), so
  anything outside the sixteen registered families is inexpressible.
* **Constrained parameter spaces as types.** `simplex[K]`, `ordered[K]`,
  `cholesky_factor_corr[K]`, `cov_matrix[K]` are types carrying nontrivial geometric
  constraints, with the transforms to and from the unconstrained space built in. HML has
  `Vector[Probability, K]`, which is not a simplex — it does not say the entries sum
  to 1.
* **Loops, conditionals, local variables, recursion.** Stan is a programming language.
  HML v0 is a declarative statement inventory with no control flow whatsoever.
* **Missing-data and ragged-array idioms**, `generated quantities` for posterior
  predictive simulation, and the whole `_rng` family. HML has no notion of simulation.

### 4.2 SymPy

* **Actual computation.** SymPy simplifies, differentiates, integrates, solves, factors
  and evaluates numerically. HML v0 computes nothing at all: it states and checks.
* **Unrestricted symbolic algebra.** Series expansions, limits, ODE solving, matrix
  decompositions, Gröbner bases, assumptions-aware simplification. HML has no algebraic
  rewriting engine.
* **Arbitrary-precision and exact arithmetic over algebraic numbers** — `sympy.Rational`,
  `sympy.AlgebraicNumber`, `sympy.RootOf`. HML literals are decimals and integers.
* **First-class expression manipulation.** A SymPy expression is data that can be
  traversed, substituted into and rebuilt at run time. HML's IR is frozen and consumed,
  not programmatically constructed.
* **Piecewise, `Sum`, `Product`, `Integral`** as first-class expression nodes. HML has
  none of these binders.

### 4.3 Lean 4

* **Dependent types**, which HML v0 explicitly excludes (§8: "dependent types over
  runtime values ... shape variables are checked nominally, not arithmetically"). Lean
  can state and *prove* that a product of an `m × n` and an `n × p` matrix is `m × p`;
  HML checks the same thing by name matching, and cannot express any shape arithmetic
  at all.
* **Proof.** The entire point of Lean. HML states obligations and discharges none
  of them (§8).
* **Higher-order logic and inductive definitions.** Inductive types, recursors,
  well-founded recursion, type classes, universe polymorphism. HML has no way to define
  a new type at all — only to name a concept.
* **Measure theory, topology, category theory** — Mathlib's actual content. HML's
  probability vocabulary stops at family names and parameter roles (§8).
* **Computation with proofs attached.** A Lean `def` is executable *and* reasoned about
  in the same system.
* **Anonymous constructor / structure eta / definitional unfolding**: a Lean statement
  can be *rewritten* into an equivalent one by the elaborator. HML has exactly one
  canonical form and no rewriting.

### 4.4 What HML has that none of the three has

Stated for symmetry, not as a superiority claim (no comparative measurement has been
run — see `V0_DESIGN_FREEZE.md` §9):

* **Mandatory role labels on distribution arguments.** The `Normal(mu, sigma)` vs
  `Normal(mu, sigma²)` confusion is a parse error in HML and is expressible in all three
  targets. Stan and SymPy take positions; Lean has no distributions at all.
* **A single object with a declared loss report per view.** Each backend must say what
  it could not carry. None of the three targets carries provenance about what its own
  input lost.
* **Dimensional analysis with exact rational exponents**, present in none of the three.
* **A scalar refinement *poset*.** Stan linearises to interval constraints, SymPy to a
  fixed predicate set, Lean to a carrier plus hypotheses — all three flatten the
  `Probability` / `PositiveReal` incomparability the HML type system enforces.

---

## 5. Where the loss is concentrated

Counting the reports produced over `examples/` (`hml render -t <target>` prints them):

| HML construct class | Stan | SymPy | Lean |
|---|---|---|---|
| Distribution laws | weakened (roles → positions) | **dropped** | **dropped** |
| Quantifier nesting | **dropped** | **dropped** | **exact** |
| Refinement types | exact, except `PositiveReal` (open vs closed bound) | exact, except `Probability` (no upper bound) | weakened everywhere (hypothesis, not type) |
| Dimensions | **dropped** | **dropped** | **dropped** |
| Proof obligations | **dropped** | weakened (inert objects) | weakened (theorem + `sorry`) |
| Optimisation | **dropped** | weakened (setup only) | **dropped** |
| Concepts | **dropped** | weakened (flattened) | weakened (flattened) |
| `RandomVariable[T]` vs `T` | weakened (conflated) | weakened (conflated) | **dropped** (refuses to conflate) |

No single target dominates. Stan is the only one that can express a probability law;
Lean is the only one that preserves quantifier scope; SymPy is the only one whose output
this repository can actually execute. That the three are complementary — and that each
loses something the others keep — is the observation the multi-backend design is
built on.
