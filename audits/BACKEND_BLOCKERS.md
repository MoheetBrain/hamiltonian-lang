# Backend Blockers and Upstream Findings

Author role: Backend and Interoperability Engineer
Scope: findings in modules the backend work is not permitted to modify
(`ast/nodes.py`, `types.py`, `parser/`, `lexer/`, `semantics/`, `type_system/`,
`backends/{base,__init__,hml,latex,english,canonical}.py`, `graph/`, `cli/`,
`examples/`).

Only items actually encountered are recorded. Nothing here is speculative.

---

## B-001 — `ConceptMember.params` changed shape mid-development (resolved, no workaround needed)

**Status:** resolved. Backends adapted; no upstream change requested.

**What happened.** `ast/nodes.py` — the frozen IR — changed
`ConceptMember.params` from `list[str]` to `list[tuple[str, Type | None]]`, with an
in-file note citing decision **D-015** ("every object has a type"). The change landed
while the Stan/SymPy/Lean backends were being written against the previous shape.

**Effect observed.** `backends/sympy.py` and `backends/lean.py` iterated
`for p in m.params` treating each element as a parameter *name*, which raised
`TypeError: sequence item 0: expected str instance, tuple found` when rendering
`examples/concepts/location_scale_family.hml`. Reproduced by
`tests/backends/test_sympy.py::test_every_example_renders_without_crashing[concepts/location_scale_family.hml]`.

**Resolution.** Both backends now consume the pair form and, where a declared type is
present, use it:

* `backends/sympy.py::SympyBackend._concept_member` derives SymPy assumptions from the
  declared type of a transform parameter, and reports an *approximation* naming the
  parameter when the type slot is `None`.
* `backends/lean.py::LeanBackend._concept_member` emits `(p : T)` from the declared
  type, falling back to `ℝ` with an *approximation* report when the slot is `None`.

This is strictly better fidelity than the previous behaviour, which assumed an untyped
parameter unconditionally. **No upstream fix is requested and no workaround is in
place.**

**Note for other consumers.** `backends/english.py` also reads `ConceptMember.params`
(`" and ".join(m.params)` in `EnglishBackend.statement`). It is outside this role's
permitted edit set and was **not** modified. As of the last run of
`.venv/bin/python -m pytest tests/ -q` (586 passed, 8 xfailed) it is not failing, so
either it was updated in the same change or the join is not reached on the current
examples; this was not investigated further because it does not affect the three
backends delivered here.

---

## B-002 — transient resolver crash observed during a concurrent edit (not reproducible)

**Status:** not reproducible; recorded only so the observation is not lost.

During one test run, `semantics/__init__.py::Resolver._suggest` raised
`AttributeError: 'tuple' object has no attribute 'lower'` at line 194, from
`candidates.extend(s.by_name)` yielding a tuple-shaped scope key. This aborted
resolution of `examples/concepts/location_scale_family.hml`, so every backend test
touching that file failed.

The same command run a few minutes later succeeded (`compile_source(...) -> ok`), and
the whole suite has passed since. The most likely explanation is that the file was
observed mid-edit while D-015 (see B-001) was being applied. **No defect is being
asserted against `semantics/`**; if `_suggest` is ever reached with non-string scope
keys the failure mode is an `AttributeError` inside diagnostic *rendering*, which would
mask the real diagnostic, so it may be worth a defensive `str(c)` there — but that is a
suggestion, not a measured bug.
