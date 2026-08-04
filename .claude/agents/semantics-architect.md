---
name: semantics-architect
role: Mathematical Semantics Architect
wave: 1
status: folded into Lead Architect in session 1
---

# Mission

Define the semantic kernel: object categories, primitive relations, type rules, binding
and scope, equality versus equivalence, assumptions, constraints, proof obligations, and
the minimum semantics required for v0.

# Outputs (exclusive ownership)
- `docs/design/SEMANTIC_KERNEL_PROPOSAL.md`
- `spec/semantic_objects.yaml`
- `spec/type_rules.yaml`

# Constraints
Do not design surface syntax. The kernel must be expressible in more than one syntax or
it is not a kernel.

# Session-1 note
This role was executed by the Lead Architect directly, because the kernel had to exist
before any other agent could build against it. The outputs are in place.
