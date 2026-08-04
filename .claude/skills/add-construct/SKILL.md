---
name: add-construct
description: Add one new language construct to Hamiltonian Lang with the full eight-part definition. Use when adding a statement form, operator, type constructor, or distribution family.
---

# /add-construct

A construct is not added until **all eight** parts exist. Seven of eight is not done
(CLAUDE.md rule 4).

## The eight parts

| # | part | where |
|---|------|-------|
| 1 | surface syntax | `SPEC.md` + `parser/__init__.py` |
| 2 | AST form | `ast/nodes.py` — **frozen contract, needs `/design-change`** |
| 3 | semantic rule | `semantics/__init__.py` (binding, scope) |
| 4 | type rule | `type_system/__init__.py` + `spec/type_rules.yaml` |
| 5 | valid examples | `examples/` — must pass `hml check` |
| 6 | invalid examples | `tests/adversarial/` — must be *rejected*, asserted by code |
| 7 | backend behaviour | every backend either handles it or calls `drop()`/`approximate()` |
| 8 | round-trip test | `tests/roundtrip/` — render then re-parse to the same hash |

## Adding a distribution family (the common case)

1. Add a `DistributionSpec` to `type_system/distributions.py` with role names and the
   type each role demands, and the support type.
2. **Add the wrong role names to `MISPARAMETERISATIONS`.** If the family is commonly
   misparameterised across libraries, the compiler must name the confusion rather than
   emit a generic "unknown argument". This is the highest-value part of the work.
3. Add the Stan positional order to `backends/stan.py` and unit-test it. A role-to-
   position error is silent and catastrophic.
4. Add an example and a golden hash.

## Checklist before declaring done

```bash
.venv/bin/python -m pytest -q
.venv/bin/hml views <new example>
```

Both the positive example and the negative test must have been *executed*. Do not report
a passing test you did not run.
