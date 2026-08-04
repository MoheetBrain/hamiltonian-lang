# Changelog

## [0.1.0] — unreleased

First working vertical slice.

### Added
- Type system with a scalar refinement **poset** (not a chain), rational-exponent
  dimensions, and structurally distinct `T` / `RandomVariable[T]` / `Distribution[T]`
- HML-L1 lexer and recursive-descent parser, LL(1) at statement level
- Name resolution with stable `SymbolId`s, shadowing rejection, order-independent
  module scope
- Type checker with a role-labelled distribution registry and targeted diagnostics for
  known misparameterisations (scale vs variance, rate vs mean)
- Canonical JSON + content hash, invariant under renaming
- Semantic graph with a closed edge vocabulary, and triple output
- Backends: HML, canonical JSON, graph, triples, LaTeX, controlled English — each
  reporting its own translation loss
- `hml` CLI: `check render canonical hash graph obligations views`
- Seven reference examples; parser, semantics, type, round-trip and golden test suites

### Known gaps
- No comparative evaluation has been run. The central hypothesis is untested.
- Provenance is claimed in `GOAL.md` and not implemented (D-011)
- Proof obligations are collected and not discharged, by design
