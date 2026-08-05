# Candidate syntaxes — one directory is real, the rest are sketches

These directories hold the same seven problems written in competing surface syntaxes. They
exist to make the surface an *experimentally comparable* variable rather than a matter of
taste (`GOAL.md` §3, component Σ).

## Only `a_labelled_linear` is HML-L1

`a_labelled_linear/` is the implemented language. Every file in it **must compile**, and
`tests/golden/test_examples_compile.py` enforces that.

Every other directory is a **design sketch in a surface the compiler does not accept**.
Each carries a `.illustrative` marker file naming the reason. They keep the `.hml`
extension for side-by-side diffing, which is misleading on its own — the marker file, not
the extension, is authoritative.

| directory | surface | status |
|---|---|---|
| `a_labelled_linear/` | HML-L1, role-labelled, `end`-delimited | **implemented; must compile** |
| `b_symbolic_ascii/` | operator-dense ASCII | sketch |
| `c_sexpr/` | prefix / S-expression | sketch — becomes **Candidate C** in HML-PHASE-FG-001 |
| `d_indent_block/` | indentation-scoped blocks | sketch |
| `e_graph_triple/` | subject-predicate-object triples | sketch — informs **Candidate D** (JSON/graph) |
| `baseline_english/` | structured English | comparison baseline, not a syntax candidate |
| `baseline_latex/` | LaTeX | comparison baseline, not a syntax candidate |

## Why the marker exists

`CLAUDE.md` rule 10 requires that every example compile *or* be explicitly marked
illustrative. Until 2026-08-05 the conformance gate globbed `examples/*/*.hml` — one level
deep — so all 35 files here were silently unchecked, and two files in `a_labelled_linear`
had drifted out of the language without anyone noticing:

- `3_linear_regression.hml` used `infer posterior` with no prior, which D-016 made an error
- `7_concept_definition.hml` used unnamed invariants, which the parser now rejects

Both were the compiler being right and the example being stale. The gate now walks
`examples/` recursively, so this class of drift cannot recur silently.

## Adding a directory

A new sketch directory needs a `.illustrative` file whose contents state, in one line, why
its files are not expected to compile. A directory without that marker is treated as real
HML-L1 and every `.hml` in it must pass `hml check`.
