# Roadmap

## v0 — vertical slice (current)

Goal: an experiment that can return a verdict, not a language.

- [x] Semantic kernel: type lattice, dimensions, symbol identity
- [x] Lexer, parser, name resolution, type checker, diagnostics
- [x] Canonical form + content hash with alpha-renaming invariance
- [x] Views: HML, canonical JSON, semantic graph, triples, LaTeX, controlled English
- [x] Seven reference examples, all checking
- [x] Parser / semantics / type / round-trip / golden tests
- [ ] Stan, SymPy, Lean statement-skeleton backends
- [ ] Preregistered benchmark protocol with null hypotheses
- [ ] Adversarial rejection suite
- [ ] Alphabet and grammar candidate comparison with measured tokenisation

## v0.1 — close the Wave 1 findings

- [ ] Revise `GOAL.md` §5 per D-012: the architecture is apparatus, not contribution
- [ ] Resolve Q-03 (OpenMath IPR) before any reuse
- [ ] Decide Q-05 (role labels on ordinary calls)
- [ ] Add the out-of-distribution confound to the falsification conditions

## v0.2 — the cheapest high-value test, and it needs no model

Raised by the adversarial reviewer and adopted: **the only round trip verified today is
HML → HML, which is the one that cannot lose anything.**

- [ ] Demonstrate HML → Stan → HML and HML → Lean → HML preserving the content hash, or
      characterise exactly where and why it fails
- [ ] This tests `GOAL.md` §8 failure condition 4 (translation loss) and the
      one-object-many-views claim — the part of the design with the most residual novelty
- [ ] No model call is required, so it is cheap, deterministic, and falsifiable today

## v1 — the actual experiment

The only milestone that matters. Everything above is scaffolding for it.

- [ ] Model-in-the-loop arms: same problems, same model, matched compute, five arms
- [ ] The scaffolding-ablation arm (English + structural prompting) — the arm most
      likely to falsify the thesis, so it must be built first, not last
- [ ] Repair-loop evaluation: does deterministic compiler feedback raise verified success?
- [ ] Results document reporting the outcome honestly, including negative results

### The argument that this fails, stated plainly

From `audits/RED_TEAM_REPORT.md` §6, adopted rather than rebutted: **the inference the
thesis wants to eliminate happens when the file is written, not when it is read.** Someone
had to decide that `jitter` is a scale before `scale := jitter` could be typed. A
correct-looking encoding of a misunderstanding compiles clean, hashes correctly, and is
wrong. The reviewer's ESTIMATE is that arm A′ (prose plus a matched structural checklist)
closes most of the gap — in which case the right artefact is a prompt, not a compiler.

That is why A′ is built first.

## Not planned

- a theorem-prover kernel
- formalising all of mathematics
- cryptographic provenance
- a graphical IDE
- any syntax optimisation before the semantics are settled
