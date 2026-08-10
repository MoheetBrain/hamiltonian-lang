# hamiltonian-lang

Private research prototype exploring a compact, machine-oriented language for
representing mathematical structures, transformations, constraints, and executable
reasoning. Initial development focuses on the core grammar, semantic model, parser, and
evaluation tooling.

See [GOAL.md](GOAL.md) for the thesis and [docs/design/V0_DESIGN_FREEZE.md](docs/design/V0_DESIGN_FREEZE.md)
for the frozen v0 contract.

## Status

v0. A working vertical slice exists: lexer → parser → name resolution → type checking →
canonical form → multiple rendered views.

**Nothing measured so far supports the central hypothesis.** That hypothesis — that an AI
system reasons more accurately through this representation than through prose, LaTeX, or
code — has been probed several times at small N, and **no result favours this
representation**. Nothing in this repository should be read as evidence for it.

*Corrected 2026-08-10.* This paragraph previously read "No comparative evaluation has been
run." It was written on 2026-08-04 and had been false since. Comparative runs exist and are
recorded; the honest statement is not that they are absent but that they are negative or
null:

| probe | N | result |
|---|---|---|
| implication direction | 12 pairs | Structured English 5/12 · this representation 1/12 · generic AST 0/12 |
| next-action | 12 + 18 items | an apparent advantage did **not** survive independent replication (Δ 0.000) |
| quantifier scope | 8 pairs | a generic S-expression scored highest; this representation fell between it and Structured English |
| saturated benchmark | 105 calls × 7 arms | every arm saturated; paired difference 0.000, CI [0, 0] |

Every one is underpowered and none licenses a conclusion in either direction. The
preregistered experiment that would actually test the hypothesis is in
[docs/research/BENCHMARK_PROTOCOL.md](docs/research/BENCHMARK_PROTOCOL.md) and has not been
run.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

```bash
.venv/bin/hml check examples/statistics/bayesian_coin.hml
```

```bash
.venv/bin/hml views examples/statistics/normal_distribution.hml
```

## What a program looks like

```
module BayesianCoin

param theta : Probability
prior theta ~ Beta(alpha := 1, beta := 1)

obs trials : Natural = 10
obs successes : Natural = 7

likelihood successes | theta ~ Binomial(trials := trials, prob := theta)

infer posterior theta
```

Distribution arguments are labelled by **role**, and the labels are mandatory. There is no
way to write `Normal(mu, sigma)` and leave the reader to guess whether the second argument
is a standard deviation or a variance — that question is answered in the syntax or the
program does not parse.

## CLI

| command | effect |
|---------|--------|
| `hml check FILE` | parse, resolve, type-check |
| `hml render FILE -t TARGET` | emit one view (`english`, `latex`, `json`, `graph`, `triples`, `hml`, …) |
| `hml views FILE` | every view side by side |
| `hml canonical FILE` | canonical JSON |
| `hml hash FILE` | content hash — invariant under renaming, sensitive to structure |
| `hml graph FILE` | semantic graph as triples |
| `hml obligations FILE` | proof obligations the program generates and does **not** discharge |

## Layout

```
src/hamiltonian_lang/   lexer, parser, ast, semantics, type_system, graph, backends, cli
spec/                   grammars, schemas, semantic object definitions
examples/               the seven reference problems, all of which must check
benchmarks/             paired problems across representation arms
evaluation/             deterministic scoring harness
docs/design/            design decisions and the v0 freeze
docs/research/          prior art and the benchmark protocol
audits/                 adversarial review
tests/                  parser, semantics, type_system, roundtrip, golden, adversarial, backends
```

## Testing

```bash
.venv/bin/python -m pytest -q
```

Confidential. Not for distribution.
