# INVALID INSTRUMENT — Tranche A was halted before it ran

**Status:** ACQ0 v2 Tranche A was **halted by the Lead before any base call was made.**
No tranche generation exists. No rate, no viability verdict and no failure taxonomy was
computed, and none may be computed from this directory.

**Repo state:** commit `1b82c02`, branch `integration/m1.5-paper-derived-closeout`.
**Halted:** 2026-08-06, after the context probe and before condition 1 of 32.

## What is in this directory

| file | what it is | validity |
|---|---|---|
| `context_probe.json` | 4 live calls, `num_predict=1`, the largest prompt of each surface | **VALID — see below** |
| `INVALID_INSTRUMENT.md` | this marker | — |

There is no `conditions/` directory and no `run_manifest.json` because the tranche never
started. **Zero** base calls, **zero** repair calls, **zero** capped generations, **zero**
transport failures.

## Why the tranche was halted

An independent task review found two structural defects in
`evaluation/corpus_governance/`. Both were reproduced independently here, offline, with no
model call.

**Defect 1 — statement order is part of canonical identity but absent from the
model-visible view.** `CanonicalAcq0TaskV2.structured_target()` partitions a module into
kind-keyed lists (`declarations`, `definitions`, `probability_laws`, `assumptions`,
`domain_constraints`) carrying **no positional index**, while `content_hash` is
order-sensitive. Reassembling each task in the order the view presents it and re-hashing:

| task | reordered by the view | hash matches reference |
|---|---|---|
| `v2_binding_dependency_001` | no | yes |
| `v2_assumption_boundary_001` | **yes** | **NO** |
| `v2_implication_equivalence_001` | no | yes |
| `v2_approximation_equality_001` | no | yes |
| `v2_quantifier_scope_001` | no | yes |
| `v2_probability_law_role_001` | **yes** | **NO** |
| `v2_dimensional_algebra_001` | no | yes |
| `v2_transformation_side_condition_001` | **yes** | **NO** |

The four passing tasks pass because their source order happens to coincide with the view's
bucket order. That is luck, not design: the view cannot express the distinction, so a model
given only the view cannot recover the reference hash for the three failing tasks by any
means other than guessing.

**Defect 2 — `v2_dimensional_algebra_001` drops a whole statement.**
`structured_target()` has no `CheckStmt` branch, so `check dimension pressure = Mass /
(Length * Time^2)` reaches neither the prose nor the structured target — yet it is in the
AST and enters the hash. Statement counts, AST versus model-visible view:

```
v2_dimensional_algebra_001            ast=5  view=3   <-- two short
every other task                      ast=n  view=n-1 <-- the module header, carried separately
```

Every other task is short by exactly one (the `module` header, which the view carries in
its own `module` key). `v2_dimensional_algebra_001` is short by two. The extra one is the
`check` statement. No encoder can emit a statement it was never shown, so this task fails
deterministically for every surface and every model.

**Net: four of the eight tasks are unencodable by construction.** A parse or preservation
rate computed over them would measure the corpus, not the model.

## Why the preflight did not catch it

The preflight run before the probe checked `render_surface(task, surface) →
adapter.parse(...) → classify_stages(...)` and reported 0/32 round-trip failures. That
result is real but it validates the **renderer/importer pair only**: it renders from
`task.source`, the authoritative object, and never passes through the model-visible view.
The defect lives strictly between `structured_target()` and the source, so this check could
not have found it and no amount of care in running it would have helped.

**The check that would have caught it**, and which should gate any future tranche: for each
task, reconstruct the module *from the model-visible view alone* and assert the
reconstruction's `content_hash` equals the reference. Any task failing that assertion is
unencodable and must not enter a tranche. That is an encodability gate on the view, not a
round-trip on the source, and it is the missing precondition.

## The probe measurements remain valid

`context_probe.json` measures **properties of the assembled prompts** — token counts under
the frozen runtime. It is independent of whether the tasks are encodable: the prompt strings
were built and sent, and the server counted them. The counts stand and are reusable, with
one caveat recorded honestly: the prompts were assembled from the *current* corpus, so if
the view is repaired by adding positional indices and the missing `check` statement, the
prompts will grow and **must be re-probed**. The measured chars-per-token ratios (3.07–3.37)
will carry over; the absolute counts will not.

## Preservation

`context_probe.json` is preserved byte-for-byte as written. Nothing in this directory has
been deleted, overwritten or cleaned up.
