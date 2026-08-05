# Candidate surfaces — HML-PHASE-FG-001 phase F3

Four deterministic renderer/parser pairs over **one** canonical Hamiltonian object.

| id | surface | module | spec |
|---|---|---|---|
| A | V0 labelled-linear (HML-L1 as frozen) | `evaluation/syntax_acquisition/candidate_a.py` | [CANDIDATE_A.md](CANDIDATE_A.md) |
| B | simplified V1 labelled-linear | `evaluation/syntax_acquisition/candidate_b.py` | [CANDIDATE_B.md](CANDIDATE_B.md) |
| C | prefix / S-expression | `evaluation/syntax_acquisition/candidate_c.py` | [CANDIDATE_C.md](CANDIDATE_C.md) |
| D | constrained JSON / graph | `evaluation/syntax_acquisition/candidate_d.py` | [CANDIDATE_D.md](CANDIDATE_D.md) |

Measured round-trip results are in
[`docs/evaluation/OFFLINE_ROUND_TRIP_REPORT.md`](../../evaluation/OFFLINE_ROUND_TRIP_REPORT.md).

## What these documents are for

The surface is being made an *experimentally comparable* variable rather than a matter of
taste (`GOAL.md` §3, component Σ). That only works if the four candidates encode exactly
the same mathematics, so the phase's central obligation is negative: **no candidate may
receive additional mathematical information.** These documents record what each surface
writes down and — equally important — what it does not.

## The frozen supported subset

The subset is defined once, in `evaluation/syntax_acquisition/core.py`
(`validate_supported`, version tag `hml-fg001-subset-1.0.0`), and every renderer calls it
before emitting a byte. It is therefore a property of the phase, not of any candidate: no
surface can quietly support something the others drop, and none can silently drop
something. `tests/syntax_acquisition/test_unsupported.py::test_the_four_surfaces_agree_on_what_is_unsupported`
asserts the agreement mechanically over 37 out-of-subset objects.

### Inside the subset

* every statement in the v0 inventory: `module`, the six declaration kinds, `def`,
  `law`/`prior`/`likelihood` with conditioning, `assume`, `require`, `prove`,
  `minimise`/`maximise`, `solve`, `infer` × 5 queries, `check` (proposition and
  dimension, with and without an asserted dimension), `concept` with `extends` and all
  six member kinds;
* every expression form: literals, references, unary `-`/`not`, the six binary
  operators, the six comparisons, the four connectives, calls, indexing, distribution
  laws with role-labelled arguments, and `forall`/`exists`/`exists unique` at any nesting
  depth;
* every type constructor, including `Quantity` with rational exponents and dimension
  variables.

### Outside the subset, for every candidate

These are not candidate weaknesses. They are places where the frozen IR admits a value
that the v0 *grammar* cannot spell, so no surface can round-trip them and all four refuse
them identically.

| excluded | why |
|---|---|
| `CheckStmt.check_kind == "type"` | the field exists in `ast/nodes.py`; the grammar has no production for it |
| `RequireStmt.label`, `ProveStmt.label` | fields exist; no surface syntax, and the canonical form ignores them |
| negative numeric literals | `-3` is unary minus applied to `3` in every surface, a different tree |
| non-finite literals (`nan`, `inf`) | no token |
| an explicit unknown extent (`?`) | `?` appears in `parser.parse_extent` and in the v0 freeze's reserved-token table but is **absent from the lexer's operator list**, so `Vector[Real, ?]` dies at HML-L101. An unknown extent is written by *omission* instead |
| `Tensor` with an empty shape, or with any unknown extent | omission is positional; `Tensor[T]` has no extents at all, not one unknown one |
| `Matrix` with unknown rows and known columns | same reason: `Matrix[T, ?, 3]` is unspellable |
| `Function`/`Predicate` with an empty domain | `Function[Unit -> T]` would read back as a concept named `Unit` |
| an unannotated `def` parameter | it parses, but never type-checks (HML-T450), so it cannot occur in a checked object |
| an unannotated `transform` parameter | HML-P214 |
| a bare distribution (`Beta` with no arguments) outside law position | in law position it is a `DistExpr`; in expression position the same text is a `Ref` |
| role-labelled ordinary function calls | the role discipline applies to `DistExpr` only in v0 (Q-05) |
| identifiers reserved in *any* surface | see below |

### The reserved-name union

A name free in one surface and reserved in another would make the subset
surface-dependent, and a subset that differs per candidate is not a subset. The union of
every surface's reserved words is therefore excluded from all four:

* HML-L1's 47 keywords (`lexer.KEYWORDS`), which constrains A;
* candidate B's 11 additional words `mod dec fun dist say opt ask kind all some one`.

Candidates C and D reserve nothing at identifier positions — C's special words occur only
as list heads and D's only as JSON keys — so they pay for a restriction they do not need.
That is recorded rather than optimised away, because relaxing it for two candidates and
not the other two is exactly the asymmetry this phase exists to avoid.

### One measured asymmetry outside the subset

An **empty document** is not malformed, and the four surfaces disagree about it. A and B
are line-oriented with no envelope, so empty input is a well-formed empty module whose
name falls back to the parser's default `Main`. C and D have an explicit envelope and
reject empty input for lack of one. It never arises for rendered output — every renderer
emits the module header — so it does not affect the round-trip figures. Asserted in
`tests/syntax_acquisition/test_malformed.py::test_the_empty_document_is_a_measured_asymmetry_between_the_surfaces`.

## How information parity is enforced

Three independent checks, each with a negative control in
`tests/syntax_acquisition/test_information_parity.py`. A fairness test with no negative
control is indistinguishable from one that always passes.

1. **Content parity.** All four renderings, parsed back *before* resolution, normalise to
   a byte-identical `declared_content` — names, declared types, literal values and their
   numeric kind, operators, families, roles, and every structural nesting relation, with
   spans, `SymbolId`s and inferred types discarded. Control: a candidate that supplies a
   `def`'s inferred type as if the author had declared it must be caught.
2. **No pre-resolution.** No candidate's `parse` output carries a `SymbolId` or an
   inferred `type_`. All four hand the identical scope walk and type inference to the
   shared checker. Control: a candidate that emits a use→binder pointer — the
   `_:q1cl refTo _:q1y` edge in the `e_graph_triple` sketch — must be caught.
3. **Recovery parity.** All four recover the same canonical content hash. Control: a
   candidate that drops a law's conditioning set must be caught.

The dimension notation is where this bites hardest, and it is the one place where a
shorter encoding was deliberately rejected. Candidates C and D both *could* have written
the signed exponent vector the IR stores (`Time: -2`). Both instead transliterate the
same numerator/denominator decomposition the linear surfaces print, term for term, so
that "what is the exponent of Time?" costs a reader the same step in all four.
