# V0 Design Freeze — HML-L1

Status: **FROZEN** for v0. Changes require a `/design-change` record in `DECISIONS.md`.
Owner: Lead Architect. No subagent may amend this file.

This freeze was issued *before* Wave 1 research completed, deliberately: the research
agents are chartered to **attack** these choices with evidence, and a frozen target is
attackable in a way that an open question is not. Every choice below carries a reversal
cost in `DECISIONS.md`. Choices marked **PROVISIONAL** are expected to move.

---

## 1. Canonical alphabet — Candidate B (ASCII + reserved semantic tokens)

Canonical serialization is **7-bit ASCII**. Unicode is a *display* layer only and never
a source of truth. Rationale: eliminates normalisation and confusable-identifier risk
entirely rather than mitigating it, and keeps byte-level diffing and hashing stable.

Reserved tokens, each with a formal meaning (not a convention):

| Token | Meaning |
|-------|---------|
| `:`   | type ascription — `x : Real` |
| `:=`  | definition / binding of a value |
| `~`   | "is distributed as" — relates a random variable to a `Distribution[T]` |
| `\|`  | conditioning — `y \| x` restricts a law to a conditioning set |
| `->`  | function mapping |
| `=>`  | material implication |
| `<=>` | logical equivalence |
| `.`   | quantifier body separator — `forall x : Real . P` |
| `@`   | matrix / vector product |
| `^`   | exponentiation |
| `?`   | query marker (reserved, unused in v0) |
| `!`   | proof obligation marker (reserved, unused in v0) |

Identifiers: `[A-Za-z_][A-Za-z0-9_]*`. Comments: `#` to end of line.

**Deliberately excluded from v0:** whitespace-significant semantics, bidirectional
text, invisible characters, and any operator whose meaning varies by context.

## 2. Grammar — line-oriented, role-labelled, block-delimited by `end`

One statement per line. Blocks (`concept`) close with an explicit `end` keyword rather
than indentation, so the grammar is insensitive to whitespace damage from copy/paste and
from model generation.

**The load-bearing decision (D-003): distribution arguments are role-labelled and
mandatory.**

```
theta ~ Beta(alpha := 1, beta := 1)
```

not `Beta(1, 1)`. Positional distribution arguments are a parse error.

**Precise statement of what this buys** (narrowed after the Wave 1 alphabet study, which
correctly flagged the original wording as false). Two separate mechanisms are involved:

1. *The grammar* forbids positional arguments (`HML-P234`). This alone does **not** close
   the sd-vs-variance hole: `Normal(location := mu, variance := s)` is perfectly
   well-formed at the grammar level.
2. *The type system* closes it, via closed per-family role signatures in
   `type_system/distributions.py`. An unrecognised role is `HML-T416`; a recognised-but-
   wrong role such as `variance` is `HML-T415`, carrying a diagnostic that names the
   confusion. Verified: `Normal(location := mu, variance := s)` and
   `Uniform(min := a, max := b)` are both rejected.

So the ambiguity is *unrepresentable in a well-typed program*, not *unparseable*. The
earlier claim that it "cannot be expressed" overstated the grammar's role and has been
withdrawn.

Cost: **+4 tokens per law statement, ≈5.9% of a program** — mean over the seven-problem
corpus in `examples/candidate_syntaxes/`, across eight tokenisers (tiktoken
cl100k/o200k/p50k/r50k and HF gpt2/Llama-2/gpt-neox-20b/starcoder2). Llama-3 was gated and
is excluded rather than estimated. Per-tokeniser figures are in
`experiments/alphabet/results/d003_file_cost.csv` and `d003_micro_cost.csv`; the run log is
`results/RUN_LOG.txt`.

Note that `tiktoken` is **not** installed in the project `.venv` — the measurement was
taken in the alphabet study's own environment, so `evaluation/score.py` falls back to an
approximate tokeniser and labels its own numbers `APPROXIMATE`. The two sets of token
figures are not interchangeable.

Whether the cost is worth paying is H5, and is open.

## 3. Statement inventory (v0)

```
module <Name>
var|param|const|obs|index|rv <name> : <Type> [= <expr>]
def <name> [(<params>)] [: <Type>] := <expr>
law|prior|likelihood <target> [| <refs>] ~ <DistExpr>
assume <proposition>
require <proposition>
minimise|maximise <expr>
solve <refs>
infer posterior|expectation|variance|mle|map <refs>
check dimension <expr> [= <dimexpr>]  |  check <proposition>
prove <proposition>
concept <Name> [extends <Name> (, <Name>)*] ... end
```

Notes on two under-specified points found by the Wave 1 grammar review and since resolved
against the implementation: `rv` is a declaration keyword (it was omitted from an earlier
draft of this list, though `DeclKind.RANDOM` has always existed and the parser has always
accepted it); and `extends` takes a **comma-separated** list.

## 4. Semantic primitives

Type constructors: `Bool Natural Integer Rational Real NonNegativeReal PositiveReal
Probability`, `Vector[T,n]`, `Matrix[T,m,n]`, `Tensor[T,...]`, `Set[T]`,
`Function[T -> U]`, `Predicate[T]`, `RandomVariable[T]`, `Distribution[T]`,
`Quantity[D]`, `Proposition`.

**The scalar order is a poset, not a chain.** `Probability` is *not* a subtype of
`PositiveReal` (0 is a probability, 0 is not a positive real) and `PositiveReal` is not
a subtype of `Probability` (2.0 is a positive real, not a probability). They meet at
`NonNegativeReal`. Implementations that linearise this order are wrong.

**`RandomVariable[T]`, `Distribution[T]`, and `T` are three distinct types.** Prohibited
conflations from the directive §22 are enforced structurally: `~` requires
`Distribution[T]` on the right and `RandomVariable[T]` on the left; there is no
subtyping path between them.

## 5. Binding mechanism (D-005)

Hybrid. Surface syntax uses readable names. The resolver assigns every binder a
`SymbolId(name, ordinal, depth)`. Canonicalisation projects to
`sym:#<depth>.<ordinal>`, discarding the spelling — a locally-nameless form obtained
without forcing De Bruijn indices onto the surface syntax.

Consequence, and a v0 success criterion: alpha-renaming a program must not change its
canonical hash. Property-tested in `tests/roundtrip/`.

## 6. Dimensions

Rational-exponent vectors over `Mass Length Time Temperature Current Amount Luminosity`.
Addition and comparison require dimensional equality; multiplication adds exponents;
`^` with a rational literal scales them. Decidable and exact (uses `Fraction`, not
floats).

## 7. Canonical form

Deterministic JSON: sorted keys, alpha-normalised binders, symbol references by
canonical id, no source spans, explicit version tag. `sha256` of the UTF-8 encoding is
the object identity. Suitable for equality testing, deduplication, and dataset keys.

## 8. Explicitly unsupported in v0

Stated so that no reader infers capability from silence:

- proof *search* of any kind (Lean output is statement skeletons with `sorry`);
- measure-theoretic foundations beyond family names and parameter roles;
- continuous-time processes, stochastic differential equations;
- dependent types over runtime values (shape variables are checked nominally, not
  arithmetically);
- unit *conversion* (dimensions are checked; units are not yet reconciled);
- user-defined distribution families with custom densities;
- import / multi-module linking;
- **provenance and derivation history** (added after Wave 1, D-011). `GOAL.md` §5 states
  that Layer 2 records provenance. It does not. `ast/nodes.py` carries source spans and
  types only. The semantic graph's `depends_on` / `conditioned_on` edges give dependency
  tracking, which is not the same thing as a derivation record;
- role-labelled arguments for ordinary function `Call`s — the role discipline currently
  applies to `DistExpr` only (Q-05).

## 9. Benchmark hypotheses under test

H1 binding · H2 quantifier scope · H3 type & dimensional validity · H4 verified success
with compiler feedback · H5 token efficiency · H6 morphological generalisation ·
H7 graph retrieval. Preregistered with null hypotheses in
`docs/research/BENCHMARK_PROTOCOL.md`.

**No superiority claim is made anywhere in this repository at the time of this freeze.**
No comparative measurement has been run.
