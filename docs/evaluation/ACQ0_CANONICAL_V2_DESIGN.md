# ACQ0 canonical task v2 — design

## The failure this replaces

The v1 corpus kept mathematics in **three independently authored places**: a prose
paragraph, a `SemanticFacts(...)` **Python repr string**, and a private reference encoding.
Nothing forced them to agree, and they did not.

In `assumption_boundary_000` the prose said *"varrho of an argument equals 5 divided by
that argument"*; the reference wrote `eta / mu` with `eta = 5`. Both denote the same
function; their canonical hashes differ. A frontier model followed the prose and was scored
FAIL. It also added a `prove` statement — invited by a natural-language question posed while
`objective=None` — that the reference did not contain.

The audit found **41 of 41 tasks inadmissible**: 41 with a question and no objective, 38
naming an entity absent from the prose, 10 with a function body only in the reference, 6
asserting an assumption while the visible assumption list was empty, 4 presenting a derived
fact as a premise, 3 depending on a literal nowhere visible.

**This was a scoring-instrument failure, not a model failure.** Editing prose would not fix
it: the defect is that three artefacts could be authored separately at all.

## Authority hierarchy

```
                CanonicalAcq0TaskV2.source        <- the ONLY authored mathematics
                          |
                    real compiler
                          |
                    typed AST + content hash
        ______________________|______________________
       |          |          |          |            |
  structured    prose     surface    reference    expected
    target              A/B/C/D      HML-L1        hash
```

Everything below the source is **derived**. Nothing is authored twice, so nothing can
disagree. The reference encoding **is** the authority, not a copy of it.

There is deliberately **no second mathematical AST**. The compiler's AST is the AST; a
parallel evaluation AST would reintroduce exactly the divergence being removed.

Only what cannot be read off the source is carried explicitly: epistemic categorisation,
derived-fact provenance, the objective, prohibited assumptions, task provenance. Each is
validated against the source at construction.

## Schema

`evaluation/corpus_governance/canonical_v2.py`, `schema_version = acq0.v2.lossless`.

| field | role |
|---|---|
| `task_id`, `family`, `schema_version` | identity |
| `source` | **the authoritative HML-L1** |
| `objective` | `Objective(kind, statement)` or `None` |
| `derived_facts` | `DerivedFact(statement, derived_from, state_in_prose)` |
| `prohibited_assumptions` | assumptions a solver must not make |
| `provenance` | author, timestamp, generator, notes |

Derived: `canonical_hash()` · `reference_hml()` · `structured_target()` · `content_digest()`.
`structured_target()` emits declarations (with values), definitions (typed binders,
codomain, **body**), probability laws with role labels, assumptions, domain constraints,
derived facts with provenance, and the objective — as **structured JSON, never a repr
string**.

### Invariants, enforced at construction

An invalid task cannot exist as an object.

1. the source compiles;
2. `const` has an initialiser — the v1 `eta` defect;
3. `def` has a body, typed binders and a codomain — the v1 `varrho` defect;
4. `objective is None` ⟹ the source contains no goal — the v1 invented-`prove` defect;
5. an objective ⟹ the source states a goal;
6. a derived fact is not also asserted as an assumption;
7. a derived fact names its premises.

`EpistemicCategory` gives exactly one category per proposition:
`supplied_assumption · domain_constraint · derived_fact · proof_obligation`.

**No new HML construct was introduced.** No symbolic-constant construct was added; a task
needing one is rejected as unsupported rather than accommodated.

## ACQ0 versus H2 versus H3

| | ACQ0_TRANSLATION | H2_REASONING | H3_REPAIR |
|---|---|---|---|
| structured target | **supplied** | `None` | interface only |
| question | **`None`** | rendered from the objective | — |
| reference encoding | is the answer | `None` | — |
| asks the model to | encode | solve | repair |

ACQ0 carries **no problem-solving question**. A question with no formal counterpart is what
let a model invent a goal. A formal objective that is itself part of the object to be
translated already appears in `structured_target`, so no prompt question is needed.

`assert_views_distinct` refuses an H2 view carrying a target or encoding, and an ACQ0 view
carrying a question. Both directions are tested, including the poisoned cases.

H3 remains **interface-only** and must never inherit ACQ0's target-aware diagnostics.

## Generated prose

Plain, complete, deterministic. Every declared entity appears; every supplied assumption
appears; a derived fact appears only when it declares `state_in_prose`, and then is labelled
*"this is a consequence, not a further restriction."*

The v1 phrase *"the assumption is the only restriction given"* — while a second constraint
was listed — is unreachable: prose enumerates what the object contains.

---

## Partiality policy — the current boundary

The corpus-side guard `_reject_unguarded_partiality` rejects a definition declared total
over a binder domain on which its body is not total.

**Detected:** division whose denominator is a **bare binder** declared with a type admitting
zero (`Real`, `Integer`, `Rational`, `NonNegativeReal`). Narrowing to `PositiveReal` or
`PositiveNatural` admits the definition.

**Not detected — these must fail closed until supported:**

- division by a compound denominator (`e / (mu - 1)`);
- `sqrt`, `log`, `tan` and other partial callees;
- negative or fractional powers (`mu ^ -1`, `mu ^ 0.5`);
- indexing, inversion, cancellation;
- partiality reachable only through a chain of definitions.

**Why the eight current tasks are safe.** Only two contain division. In
`v2_assumption_boundary_001` the denominator is the binder `mu : PositiveReal`, total. In
`v2_dimensional_algebra_001` the denominator is `area`, a module-level `var`, not a binder —
the definition is not quantified over it, so no totality claim is made over a domain
containing zero.

**The compiler generates no definedness obligation over a binder's declared domain at all.**
`verify_source` returns `VERIFIED` for `def f(mu : Real) := e / mu` *and* for the
`PositiveReal` spelling alike. The guard here is corpus admission, not a compiler fix; a
compiler fix would be a semantic-contract change.

Any future task using an undetected construct must be rejected by an explicit new detector
before admission — **never admitted on the assumption that it is probably fine.**

## ACQ0 scope boundary

`CanonicalAcq0TaskV2` is an **ACQ0 translation instrument only**. It is not the H2/H3
reasoning oracle and not a required proof trace.

`v2_firewall.acq0_semantic_diff` refuses to run outside `Mode.ACQ0`. It knows the intended
encoding: H2 scored against it would be penalised for any other valid derivation, and H3 fed
by it would be transcription rather than repair. H2/H3 must use an independent answer oracle
or mathematical verifier with matched representation arms.
