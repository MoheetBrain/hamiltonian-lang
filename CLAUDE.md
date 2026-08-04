# CLAUDE.md — permanent project instructions

Hamiltonian Lang. Private research and development. Read `docs/design/V0_DESIGN_FREEZE.md`
before changing anything in `src/`.

1. **Semantic correctness outranks syntactic elegance.** A shorter syntax that admits an
   ambiguous reading is a regression.
2. **Never change the semantic contract silently.** `ast/nodes.py`, `types.py` and
   `backends/canonical.py` are the contract. Changing them changes every downstream
   consumer.
3. **Every grammar change requires tests and a decision record** in `DECISIONS.md`.
4. **Every new construct requires all eight of:** surface syntax · AST form · semantic
   rule · type rule · valid examples · invalid examples · backend behaviour ·
   round-trip test. Seven of eight is not done.
5. **Do not claim benchmark superiority without measured results.** No comparative
   measurement has been run. `tests/golden/test_golden.py::test_no_superiority_claim_in_public_docs`
   enforces this mechanically on the public docs.
6. **Do not expose private commercial strategy in public documentation.** `docs/private/`
   is never referenced from `README.md` or `GOAL.md`.
7. **Do not make the language more complex without a demonstrated requirement.** The
   burden of proof is on the addition.
8. **Preserve multiple valid mathematical representations.** One semantic object, many
   views. Do not collapse them.
9. **Reject unresolved names, invalid scopes, and incompatible types.** Rejection is the
   product. A permissive checker has no value here.
10. **All examples must compile or be explicitly marked illustrative.** `tests/golden`
    compiles every `.hml` under `examples/`.

## Prohibited conflations

These are enforced by the type system, not by convention. Do not add a subtyping path
between them:

- a `Distribution[T]` is not a value of `T`
- a `RandomVariable[T]` is not a `Distribution[T]` and is not a `T`
- `=` (equality) is not `~` (distributed as) and is not approximation
- `=>` (implication) is not correlation and is not causation
- `Probability` is not `PositiveReal` — they are incomparable, meeting at `NonNegativeReal`

## Backends

Every backend subclasses `backends.base.Backend` and **must** report translation loss via
`drop()` / `approximate()` / `weaken()`. A backend that silently omits a construct
produces authoritative-looking output that is wrong; that is the worst failure mode in
this codebase.

## Working commands

```bash
.venv/bin/hml check examples/statistics/bayesian_coin.hml
.venv/bin/hml views examples/logic/quantifier_scope.hml
.venv/bin/python -m pytest -q
```

Detailed procedures live in `.claude/skills/`, not here.
