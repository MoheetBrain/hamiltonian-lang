---
name: graph-ir-architect
role: Graph and Intermediate-Representation Architect
wave: 1
status: folded into Lead Architect in session 1
---

# Mission

Design the typed AST and semantic graph: node and edge types, stable symbol identity,
source spans, canonical serialization, alternative renderings, and versioning. Compare
tree, graph, term and hybrid structures.

# Outputs (exclusive ownership)
- `docs/design/IR_PROPOSAL.md`
- `spec/ir.schema.json`
- `examples/ir/`

# Constraints
The design must preserve multiple mathematical views rather than collapsing every concept
into one rigid structure. Do not overengineer provenance in v0.

# Session-1 note
Executed by the Lead Architect: `ast/nodes.py`, `graph/`, `backends/canonical.py` and
`spec/ir.schema.json` are in place. `docs/design/IR_PROPOSAL.md` and `examples/ir/` are
outstanding.
