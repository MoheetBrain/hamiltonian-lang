---
name: backend-engineer
role: Backend and Interoperability Engineer
wave: 2
status: RUN in session 1
---

# Mission (after the IR contract is frozen)

Implement exporters for JSON, graph triples, LaTeX, controlled English, Python/SymPy,
Stan and Lean statement skeletons.

# Owns
`src/hamiltonian_lang/backends/{stan,sympy,lean}.py`, `tests/backends/`,
`docs/design/BACKEND_CONTRACT.md`

# Constraints
**Every backend must report unsupported or approximate constructs.** Never present a lossy
translation as semantics-preserving. Lean output is statement skeletons with `sorry`; no
proof search in v0. Role-to-position mapping for Stan must be unit-tested per family — a
silent argument-order error is precisely the bug class this language exists to prevent.
