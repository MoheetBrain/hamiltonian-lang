# V1 Red Team — adversarial review of the concept kernel

Written from the position that V1 should not be built. Every claim below is either an
executed demonstration or a citation to a file in this repository. Where an attack
succeeded, the reproduction is given so it can be re-run rather than believed.

Scope: `docs/design/V1_KERNEL.md`, `spec/v1/semantic_objects.yaml`,
`spec/concept_schema.yaml`, `spec/concept_registry.schema.json`, and
`src/hamiltonian_lang/v1/` as of this branch (8,035 lines across nine modules — 88% of the
V0 kernel's 9,161 lines, added on top of a V0 that measured no benefit).

Prior art in this repository: `audits/RED_TEAM_REPORT.md` did this to V0 and produced two
withdrawn claims. This document holds V1 to that standard.

---

## 1. Executive summary — the four findings that matter

| # | finding | status |
|---|---------|--------|
| 1 | **The minting protocol is gameable four different ways, and I gamed it.** A registry seeded with one concept accepted three further copies of that same concept in the same session. | **DEMONSTRATED**, §3 |
| 2 | **The three layers V1 is named after have no kill criterion.** `kill_criteria` covers L2, L3, L4, L5 and families. The concept registry, the minting protocol and semantic morphology are not in it. | **VERIFIED**, §4 |
| 3 | **L2's detection is circular.** The checker generates a division's side condition only when the encoder has already labelled the step a division. It catches what was declared, not what happened. | **DEMONSTRATED**, §5 |
| 4 | **One of the nine prohibited conflations type-checks today**, which is L4's own stated kill criterion. | **VERIFIED**, §6 |

None of these are objections to the *idea*. They are objections to treating the current
implementation as evidence for it.

---

## 2. Where V1 most likely adds structure without benefit

Ranked by my confidence that the layer will not repay its cost. Stated in advance of any
measurement so a surprise is visible as one.

### 2.1 The concept registry — highest risk of a spurious positive

The registry is the layer with the strongest *apparent* case and the weakest *testable*
one, which is the dangerous combination.

Its problem is that a registry supplied in a prompt is indistinguishable from an answer
key. In the ablation corpus the registry names the correct answer on 4 of the 12
concept-recognition items (`cr04`, `cr05`, `cr10`, `cr12`). If `V1_mint` beats
`V1_nomint` on those four and nowhere else, the finding is "the model can read a list",
and nothing about concepts has been shown.

The corpus mitigates this with a 7-item transfer set whose answers are deliberately absent
from the registry, and reports the interaction rather than the pooled accuracy
(`HML_V1_CONCEPT_ABLATION_REPORT.md` §3.5, V1-H8). **That mitigation is the only thing
standing between a real result and an artefact**, and it rests on 7 items — well under the
number needed for a paired test. Treat any registry result as suggestive at best.

### 2.2 L5 discourse — the kill criterion is vacuous as written

> `L5: adds no diagnostic V0 does not already produce`

V0 produces **no** discourse diagnostics: it has no `goal`, no `discharge`, no `case`, no
`otherwise`. Any diagnostic L5 emits is therefore one V0 does not produce, and the
criterion is satisfied by the layer existing. It cannot fail.

A criterion that cannot fail is not a criterion. The honest replacement is a rate: *on the
ablation corpus, what fraction of genuinely open goals does L5 report, and what fraction of
its reports are on closed ones?* That is measurable and it can come out badly.

`check_exhaustive` is the one part of L5 that is genuinely falsifiable, and its own
docstring bounds it to "one variable compared to numeric thresholds". That fragment is
real, decidable and narrow. Everything else in the 936-line module is bookkeeping whose
value depends on a human reading the report.

### 2.3 `backend_support.py` — 1,949 lines documenting what does not survive

The largest module in V1, and no backend can execute any of L2–L5. Its content is a
catalogue of translation losses. That is *correct* behaviour under the backend contract —
a backend that silently omits a construct is this codebase's worst failure mode — but it
is 24% of the V1 kernel spent describing the absence of a capability. If V1 is cut, this
module is cut with it and nothing is lost, because nothing depended on it.

### 2.4 L3 inference — already predicted least likely, and rightly

`V1_EXPERIMENT_PLAN.md` §6 puts L3 last, on the ground that checking inference chains
without a prover approaches re-implementing one. I agree and add: L3's kill criterion
("does not separate valid from invalid chains better than chance") is the only criterion in
the whole spec stated against a *chance* baseline, which is the right form — and the
ablation corpus does not contain an L3 block. **L3 is currently untested by the very
apparatus built to test V1.** Either add an inference-chain block or drop the layer; do not
ship it unmeasured.

---

## 3. Is the concept-minting protocol gameable? Yes. Here is the session.

Four attacks, all successful, all against `hamiltonian_lang.v1.minting.mint` as it stands.

```python
from hamiltonian_lang.v1 import minting as Mi
from hamiltonian_lang.v1.registry import *

S = "the centred two-term form"

def C(cid, **kw):
    f = dict(canonical_id=cid, namespace="RT", version="1",
             type_signature="Real * Real -> Real", domain="Real * Real", codomain="Real",
             formal_definition="C(a, b) = (a - b) + (a - b)",
             provenance=Provenance(proposed_by="rt", proposed_at="2026-08-05"),
             parameters=(Parameter(name="a", type="Real", role="l"),
                         Parameter(name="b", type="Real", role="r")),
             invariants=(Claim(statement="C(a,a)=0", status=ClaimStatus.PROVED,
                               discharged_by="lem"),),
             compresses=(S,))
    f.update(kw)
    return Concept(**f)

def cand(c):
    return Mi.ConceptCandidate(
        concept=c,
        examples=(Mi.Example("inhabited", lambda: True),),
        compression=(Mi.CompressionEvidence(
            S, ("does/not/exist_1.hml", "does/not/exist_2.hml"),
            "(a - b) + (a - b)", "C"),))

reg = ConceptRegistry()
Mi.mint(cand(C("Alpha")), reg)                                    # admitted
Mi.mint(cand(C("AlphaClone", constraints=("true",))), reg)        # admitted
Mi.mint(cand(C("AlphaNoParams", parameters=(),
              formal_definition="C(u, v) = (u - v) + (u - v)")), reg)   # admitted
Mi.mint(cand(C("AlphaRewritten",
              formal_definition="C(a, b) = 2 * (a - b)")), reg)   # admitted
```

Result: `['Alpha', 'AlphaClone', 'AlphaNoParams', 'AlphaRewritten']` — **four names for one
concept, all admitted.** The protocol does catch a byte-identical clone; every attack below
is one step around that.

### 3.1 A vacuous constraint converts a duplicate into a "specialisation"

`search_registry` classifies a candidate as a specialisation when its constraint set is a
strict superset of an existing concept's. The constraints are compared as **normalised
strings**. Adding the constraint `"true"` — which constrains nothing — makes the superset
test succeed and the candidate is admitted.

**Fix:** a constraint that does not reduce the admissible set is not a constraint. At
minimum, reject constraints that normalise to a tautology; better, require the
specialisation to be witnessed by an instance the parent admits and the child rejects.
That witness is checkable and cannot be written by assertion.

### 3.2 Undeclaring parameters defeats the renaming check

`_alpha_normalise` abstracts **declared parameters only**, and says so:

> "a symbol that the concept does not declare as a parameter is left alone."

The docstring frames this as a deliberate trade — miss a duplicate rather than merge two
real concepts — and that reasoning is sound in isolation. But it hands the proposer the
switch: declare no parameters, rename the symbols, and the definition normalises to a
different key. This is not a rare edge case; it is a one-line edit.

**Fix:** treat the free symbols of `formal_definition` that appear in binder position as
parameters whether or not they were declared, or refuse to admit a concept whose definition
contains free symbols it does not declare. The second is stricter, simpler, and turns the
loophole into a diagnostic.

### 3.3 Any algebraic rewriting defeats the equality check

`_equality_key` compares a **normalised string** of `formal_definition`. `(a-b)+(a-b)` and
`2*(a-b)` are the same function and different strings.

This is not a new weakness; it is a known one, inherited. `evaluation/score.py` documents
exactly this about V0's `hash_equals`, with measured counterexamples: `a > 0` and `0 < a`
hash differently, `a + b` and `b + a` hash differently. **The minting protocol's duplicate
detector is built on an equality relation this repository has already documented as
unsound**, and the docstring's claim that matching is "over typed structure, never over the
name" is true about the name and overstated about the structure.

**Fix:** say what it is. "Matching is over the normalised definition string modulo
declared-parameter renaming" is accurate and would have prevented me writing this section.

A real structural matcher is a bigger decision than it looks, and I withdraw the obvious
suggestion: `pyproject.toml` declares `dependencies = []`, and the SymPy backend *emits*
`import sympy` into generated code without importing it here. Deciding algebraic equality
inside the kernel would make the kernel depend on a CAS, which is close to the prover the
founding directive forbids. The defensible options are therefore (a) narrow the claim to
what the string comparison decides, or (b) match over the parsed V0 AST, which this
repository already has and which would at least make `(a-b)+(a-b)` and `2*(a-b)` comparable
after normalisation. Not (c) add SymPy.

### 3.4 The evidence fields are unverified proposer assertions

Two of the protocol's most load-bearing checks accept whatever the proposer supplies.

**`CompressionEvidence.occurrences`** — `recurs` is `len(set(occurrences)) >= 2`. Nothing
checks the cited sites exist, and nothing checks the structure appears at them. In the
session above the sites are `does/not/exist_1.hml` and `does/not/exist_2.hml`. They do not
exist. The concept was admitted. `shortens` compares `len(abbreviation) < len(expansion)`,
where both strings are supplied by the same proposer; nothing checks that `expansion` is
what the concept actually expands to.

This is the check the module's own comment calls "the step that separates a concept from a
synonym". It separates nothing from a proposer willing to type two filenames.

**`Example.run`** — "A witness that the concept is inhabited. `run` is actually executed."
It is executed, and it is a caller-supplied closure. `lambda: True` passes. Executing an
arbitrary callable and recording that it returned `True` is not evidence of inhabitation;
it is evidence that the proposer wrote `True`.

**Fix, and it is not hard:** require `occurrences` to be repository paths, verify they
exist, and verify that `expansion` occurs in each after whitespace normalisation. Require
`Example.run` to be a source expression the checker evaluates in a restricted environment,
not a closure the proposer supplies. Both turn an assertion into a check.

### 3.5 `PLACEHOLDER_DEFINITIONS` is a blocklist

Eighteen strings, and a good list: it covers `''`, `tbd`, `todo`, `n/a`, `clearly`,
`obvious`, `standard`, `the usual definition`, `as is well known` and nine more. It is
better than I expected to find and it catches every stock evasion I would have reached for
first.

It is still a blocklist. `"the definition given in the source"`, `"as in the reference"`,
or `"per the standard treatment"` all pass. That is fine as a lint; it should not be
described as establishing that a definition is *present* in any sense stronger than "the
proposer typed something not on a list of eighteen things". The registry schema says a
concept with no formal definition may not leave `proposed`; this check enforces
"non-empty and not obviously a stub", which is a weaker sentence and should be the one
written down.

### 3.6 What the protocol does get right

Stated because a review that finds only faults is not a review. The lifecycle is explicit
and terminal states are recorded; **rejections are written into the registry, not
discarded**, so the registry can say what has already been tried and refused; claims are
adjudicated down to their real evidential status rather than accepted at their claimed one
(`PROVED` with no proof becomes `UNSUPPORTED`, verified live in
`tests/v1/test_adversarial_v1.py`); and `compresses` being required at all is a genuinely
unusual constraint that most ontology systems do not impose. The design is right. The
verification behind it is not yet real.

---

## 4. Which layer is most at risk of being unfalsifiable

**The concept kernel itself — and that is not a subtle finding.**

`spec/v1/semantic_objects.yaml::kill_criteria` names five criteria: `L2`, `L3`, `L4`, `L5`,
`families`. `docs/design/V1_KERNEL.md` §8 has the same five rows.

`src/hamiltonian_lang/v1/__init__.py` names six layers:

1. typed concept registry — **no kill criterion**
2. concept-minting protocol — **no kill criterion**
3. semantic morphology — **no kill criterion** (partially covered by `families`)
4. transformation and inference edges — L2, L3
5. epistemic-status types — L4
6. discourse-state types — L5

The three layers with no criterion are the three the work is named for. `V1_KERNEL.md` §0
sets the rule that a construct enters only if it changes what the checker reports, and §8
says "every layer below therefore carries its own kill criterion". Three do not. The
2,638 lines of `registry.py` and `minting.py` — a third of V1 — are, on the project's own
terms, currently undroppable because nothing has been specified that would drop them.

**This is the single cheapest thing to fix in this document.** Two lines in a YAML file:

```yaml
concept_registry: >
  fewer than 70% of the ablation corpus's licensed concepts are cited correctly, or the
  minting arms' advantage is confined to items the registry names (the transfer
  interaction of V1-H8)
concept_minting: >
  the false-novelty rate among minted concepts exceeds 0.3, or any of the four attacks in
  audits/V1_RED_TEAM.md §3 still admits a duplicate
```

Second-place risk: **L5 discourse**, for the reason in §2.2 — its criterion is satisfied by
the layer existing.

---

## 5. L2's detection is circular

`transformation.step` generates obligations from the **declared operation**:

```
divide   -> ['[side_condition] s1 (divide): a != 0']
simplify -> ['[side_condition] s2 (simplify): the identity unstated holds on the domain of e1']
```

An encoder that writes a division and labels it `simplify` generates no `!= 0` obligation.
The checker did not detect a division; it looked one up in `OPERATIONS` after being told
which row to read.

This matters directly for the experiment. L2's kill criterion is "fewer than 30% of
injected invalid-step errors detected", and the ablation corpus presents chains in prose
where the model chooses the label. **What that criterion will measure is whether the model
annotates its steps correctly, not whether the checker catches anything.** Those are
different claims and the second does not follow from the first.

To L2's credit: the obligation table is honest about `square_both_sides` recording a
weakening rather than an equivalence, `simplify` demands that the identity used be named,
and `edge_kind_coercion_allowed` refuses `ALGEBRAIC -> LOGICAL_IMPLICATION` **in both
directions**. The distinction V1 §2 exists to draw is genuinely drawn.

**Fix:** state the claim precisely. L2 catches *unstated side conditions on correctly
labelled steps*. It does not catch mislabelled steps and cannot, without parsing the
mathematics — which is the prover the founding directive forbids. Reported that way it is a
modest, true, useful claim. Reported as "catches algebra errors V0 misses" it is an
overclaim.

---

## 6. L4 — the strongest layer, with one hole that is its own kill criterion

L4 is the best-built part of V1 and I could not break its core. `coercion_allowed` refuses
by default rather than permitting by default; the identity case is allowed so the checker
is not inert; `REQUIRED_CONTEXT` rejects `with_high_probability` with no regime and
`fail_to_reject` with no alpha at construction time; there is no two-hop laundering route
from `Evidence` to `Proof` (verified exhaustively in
`test_evidence_never_reaches_proof_by_any_two_step_route`); and `check_test_coherence`
catches a `fail_to_reject` reported with `p = 0.01` at `alpha = 0.05`.

Two faults.

**6.1 The p-value conflation type-checks.** `V1_KERNEL.md` §7 item 3 and
`spec/v1/semantic_objects.yaml::no_coercion_between` both prohibit `PValue -> Probability`.
There is no `PValue` type anywhere in `src/hamiltonian_lang/v1/`. V0 types both sides as
`Probability`, so `def posterior_h0 : Probability := p_value` compiles clean today —
verified live in `tests/v1/test_adversarial_v1.py`. L4's kill criterion is **"any prohibited
conflation type-checks"**. One does.

The `Justification`-level prohibitions are enforced; the *type*-level ones in
`no_coercion_between` — `[Credence, Probability]` and `[PValue, Probability]` — have no
implementation, because `Justification` is not a type lattice and `Probability` lives in
V0's `types.py`, which is frozen. This is a structural gap, not an oversight: **the two
prohibitions that need a type live in the layer that has no types.**

**6.2 Coherence is opt-in.** `EpistemicClaim(FAIL_TO_REJECT, ..., p_value="0.01", alpha="0.05")`
constructs successfully. The contradiction is found only if the caller separately invokes
`check_test_coherence`. The context rule fires in `__post_init__`; the obligation rule does
not. A consumer that constructs claims and never calls the checker gets an incoherent
object with no complaint — and `spec/v1/semantic_objects.yaml` lists `p_value > alpha(test)`
under `obligations`, i.e. as something generated, so this may be intended. If so, say which
checks are constructor-time and which are pass-time, because the asymmetry is currently
invisible at the call site.

---

## 7. Smaller findings

- **`otherwise` is not decidable by `check_exhaustive`.** `check_exhaustive(["x > 0",
  "otherwise"])` returns `decided=False`. The complement branch is modelled one level up as
  `Case(complement=True)`. Correct layering, but any caller reaching for the obviously named
  function alone will fail to recognise the one construct `V1_KERNEL` §4 says makes a split
  exhaustive by construction. Pinned by `test_otherwise_is_not_decidable_as_a_bare_condition`.
- **`morphology` is right for the wrong reason to be proud of.** `attribute_property`,
  `check_substitution` and `PROPERTY_CARRIERS` do exactly what §5 promises, and
  `STRING_DERIVATION_IS_PROHIBITED` is a real constant rather than a comment. But
  `PROPERTY_CARRIERS` is a hand-written table of 19 properties. It is correct for what it
  lists and silent on everything else, and `UnknownPropertyError` on a 20th property is a
  usability cliff. The table is the design; it should be documented as a closed set that
  grows by decision record, not as a rule.
- **Renderer output is not evidence.** `epistemic.render_english` produces
  "This is not evidence that H0 is true." `V1_EXPERIMENT_PLAN.md` §8 already says
  "V1 producing more mathematician-sounding English" is explicitly not a success condition.
  It is also the most demo-able thing V1 does, which is exactly why the prohibition needs
  restating each time it is shown.
- **The V0 control is disadvantaged by construction.** V0 cannot express 38 of the 60
  ablation problems. Asking the V0 arm for an encoding that cannot represent the question
  and then comparing encodings is not a fair contest. `HML_V1_CONCEPT_ABLATION_REPORT.md`
  §9 item 3 records this and §10 proposes the missing `V0-prose` control. Until that control
  exists, a V1-beats-V0 result on this corpus is partly a measurement of the corpus.

---

## 8. The strongest argument that V1 is not worth building

Unhedged, as commissioned.

V0 was a bet that a compact typed representation changes what a model computes. The bet was
run properly — 105 paired cells, a pre-registered scorer, a blinded audit, an independent
replication — and it lost. Not narrowly. **Six of seven paired contrasts had zero
discordant pairs.** The arms did not merely score the same; they succeeded and failed on
exactly the same problems. Whatever the representation was doing, it was not touching the
computation at all.

V1's answer to that is to add four more layers and 8,035 lines — 88% of the entire V0
kernel — to the thing that just failed. The argument for doing so is that V1's claims are
correctness claims rather than reasoning claims: "this program cannot express
`prove(fail_to_reject(H0))`" is true independently of any model. That argument is correct
and it is much weaker than it sounds, for three reasons.

**First, the correctness claims are true by construction, and being true by construction is
not the same as being useful.** A Python function that raises on the string
`"prove(fail_to_reject)"` also cannot express it. What V0's own pilot report classified as
"compiler property, not evidence" applies verbatim here: that the language rejects a
conflation is a property of the checker, true before any model ran, and it stays a property
of the checker no matter how many conflations are added to the list. The pilot drew that
line explicitly and V1 is built almost entirely on the wrong side of it.

**Second, the claims are only as good as the encoding, and the encoding does not compile.**
Between 27% and 50% of V0 encodings failed to parse, and the rate was *unstable* across
generations — 73.3% then 50.0%. V1 is a strictly larger language. The `V1_mint` prompt is
3.1× the `V0` prompt. A type error that would have been caught is not caught when the
program does not parse, so V1's entire value proposition is multiplied by a parse rate that
was already the dominant failure mode and is now being asked to carry four more layers.
`V1_EXPERIMENT_PLAN.md` names V1-H4 as most likely to fail. It is right, and if V1-H4 fails
then every other hypothesis is unanswerable, because none of them can be measured on
programs that do not compile.

**Third — and this is the part that should worry the project most — the verification behind
the correctness claims is not yet real.** §3 of this document put four copies of one concept
into a registry that had just rejected an exact clone, using fabricated file paths and a
`lambda: True`. §5 showed the transformation layer generates a division's side condition
only when the encoder has already declared a division. §6 showed one of the nine prohibited
conflations still type-checks. The strongest thing V1 can currently say about itself is that
it has an elaborate protocol for admitting concepts; the demonstration above is that the
protocol admits what it is told to admit. Every one of those is fixable, and none of them is
fixed, and the layers are being counted as built.

Put together: **V1 is 8,035 lines that make a set of true-by-construction claims, about
programs that compile between half and three-quarters of the time, verified by checks that
accept the proposer's word for the facts they check.** The honest position is that V1 is a
specification with an implementation in progress, and the pilot already showed that
specifications of this kind do not pay for themselves.

The counter-argument I would accept, and only this one: the ablation's L4 block is a real
test of a real thing. "Fail to reject H0" being read as "H0 is true" is the most common
error in applied statistics, machines now generate statistical prose at volume, and a
deterministic checker that catches it needs no reasoning claim to be worth having. If
`V1_mint` or `V1_full` catches the five insufficient-evidence items that `SE` and `V0` miss,
that is a useful artefact regardless of everything above — and it is a claim about **one
layer of 213 lines**, not about a concept kernel.

**So the strongest form of the argument is not "do not build V1". It is: build L4, measure
it, and delete the other five layers unless they clear a criterion that three of them do not
currently have.**

---

## 9. Recommendations, in priority order

| # | action | cost | why |
|---|--------|------|-----|
| 1 | Add kill criteria for the concept registry, minting, and morphology | ~10 lines of YAML | Three of six layers are currently undroppable on the project's own terms (§4) |
| 2 | Verify `CompressionEvidence.occurrences` against the filesystem and `expansion` against the cited sites | ~20 lines | Closes the widest gaming path (§3.4) |
| 3 | Reject tautological constraints, or require a specialisation witness | ~30 lines | Closes attack 1 (§3.1) |
| 4 | Refuse concepts whose definition has free symbols they do not declare | ~10 lines | Closes attack 2 (§3.2) |
| 5 | Restate `search_registry`'s matching claim accurately, or match over the parsed V0 AST | 1 docstring, or ~50 lines | The current claim overstates what a normalised string comparison decides (§3.3). Do **not** add a CAS dependency for this |
| 6 | Implement `PValue`, or withdraw the prohibition from `V1_KERNEL` §7 and the spec | ~40 lines, or 2 deletions | L4's kill criterion is currently met (§6.1) |
| 7 | Add the `V0-prose` control arm to the ablation | 60 more calls | Without it, a V1-beats-V0 result is partly a measurement of the corpus (§7) |
| 8 | Add an L3 inference block to the corpus, or drop L3 | 12 items, or 1,165 lines deleted | L3 is untested by the apparatus built to test V1 (§2.4) |
| 9 | Replace L5's kill criterion with a reported/false-report rate | 2 lines of YAML | The current one cannot fail (§2.2) |

Items 1 through 6 are all small, and together they are the difference between "V1 has a
minting protocol" and "V1 has a minting protocol that works". None of them requires a model
to be run.

---

## 10. What this review did not do

Recorded so the review is not over-read.

- **No model was run.** Every finding is about the specification and the implementation, not
  about behaviour. Nothing here predicts what the ablation will measure.
- **`backend_support.py` (1,949 lines) was read for size and purpose only**, not audited. It
  is the largest untested surface in V1 by this review's coverage.
- **`registry.py`'s lifecycle, dependency-cycle and alias machinery was not attacked.** The
  attacks in §3 all go through `minting.mint`. A separate pass on `ConceptRegistry.transition`,
  `check_dependencies` and `by_alias` is warranted, particularly the schema-validation path.
- **`discourse.py` (936 lines) was probed at two functions**, not audited.
- The corpus and scorer this document cites were written by the same agent that wrote this
  review. **A red team should not grade its own corpus**, and §2.1's warning about the
  registry-as-answer-key applies with equal force to my own judgement about which items are
  hard. A blinded review of the 60 items by an agent that did not author them is the missing
  control, and `HML_V1_CONCEPT_ABLATION_REPORT.md` §9 item 7 records it as an open confound.
