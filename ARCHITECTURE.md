# Architecture

## Three layers, one identity

```
                     SURFACE (Layer 1)
        HML-L1 source text, ASCII canonical, line-oriented
                            |
                        lexer  ──> tokens (+ Unicode folding, warned)
                            |
                       parser  ──> concrete AST, source spans on every node
                            |
              name resolution  ──> SymbolId on every binder and reference
                            |
                type checking  ──> Type on every node, proof obligations collected
                            v
                   SEMANTIC CORE (Layer 2)
       typed AST + symbol table + obligations  =  the object
                            |
        +-------------------+--------------------+
        |          |         |         |         |
      canonical  graph    latex    english    stan / sympy / lean
       JSON +    view     view      view          (Layer 3)
       hash
```

Layer 2 is the only source of truth. Everything else is a projection of it. No view is
authored independently; no view is parsed back except HML-L1 itself.

## Modules

| path | responsibility | owner |
|------|----------------|-------|
| `types.py` | the type lattice, dimensions, subtyping, literal refinement | Lead Architect |
| `ast/nodes.py` | **the frozen IR contract** | Lead Architect |
| `diagnostics/` | diagnostic codes, spans, rendering | Lead Architect |
| `lexer/` | tokenisation, ASCII canonicalisation, Unicode folding | Lead Architect |
| `parser/` | recursive descent, LL(1) at statement level | Lead Architect |
| `semantics/` | scopes, symbol identity, shadowing, cycles | Lead Architect |
| `type_system/` | type rules, distribution roles, dimensional algebra | Lead Architect |
| `type_system/distributions.py` | the distribution registry and role names | Lead Architect |
| `graph/` | semantic graph and triples | Lead Architect |
| `backends/base.py` | the backend contract and loss reporting | Lead Architect |
| `backends/{hml,canonical,latex,english}.py` | core views | Lead Architect |
| `backends/{stan,sympy,lean}.py` | execution and verification targets | Backend Engineer |
| `cli/` | the `hml` command | Lead Architect |
| `benchmarks/`, `evaluation/` | preregistered experiment and scoring | Benchmark Scientist |
| `audits/` | adversarial review | Adversarial Reviewer |

## Pipeline invariants

After `compile_source(...)` returns with `ok() == True`:

1. every `Ref` carries a `symbol_id` that appears in the symbol table;
2. every expression node carries a non-`Unknown` `type_`;
3. every node carries a populated `Span` (diagnostics depend on it);
4. the canonical hash is invariant under consistent renaming and sensitive to
   quantifier order, role assignment, and type structure;
5. every constraint, assumption, positivity requirement and theorem has been recorded as
   a `ProofObligation` and **none of them is marked discharged**, because v0 proves
   nothing.

## Why the errors are the product

The value of this design is concentrated in what it refuses. The three highest-value
rejections, each of which corresponds to a real class of bug in real statistical code:

- `Normal(location := mu, variance := s)` → `HML-T415`, naming the sd/variance confusion
  explicitly rather than silently accepting a wrong parameterisation;
- `param x : Real` used as a `scale` → `HML-T413`, because a scale must be positive;
- `forall x . exists y` vs `exists y . forall x` → different canonical hashes, so the two
  cannot be conflated by any downstream consumer.

## Design decisions

Recorded in `DECISIONS.md`. Frozen subset in `docs/design/V0_DESIGN_FREEZE.md`.
