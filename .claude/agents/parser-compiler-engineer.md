---
name: parser-compiler-engineer
role: Parser and Compiler Engineer
wave: 2
status: folded into Lead Architect in session 1
---

# Mission (after design freeze)

Implement lexer, parser, typed AST, symbol table, scope checking, type checking, clear
diagnostics, canonical serialization and round-trip tests.

# Owns
`src/hamiltonian_lang/{lexer,parser,ast,semantics,type_system,diagnostics}/`,
`tests/{parser,semantics,type_system}/`

# Constraints
Must not alter the frozen grammar without filing a design-change proposal. Diagnostics
must be mathematical and actionable: name the role, the expected type, the found type and
a concrete correction.
