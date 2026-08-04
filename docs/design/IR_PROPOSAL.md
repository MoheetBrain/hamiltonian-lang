# IR Proposal — the representation of the semantic core

Owner: Lead Architect (the `graph-ir-architect` role was folded in under the four-agent
limit). Implemented in `src/hamiltonian_lang/ast/nodes.py`, `graph/`, and
`backends/canonical.py`. Schema in `spec/ir.schema.json`.

## 1. The choice: tree, graph, term, or hybrid

Four structures were considered for the semantic core.

| structure | strengths | why it was not chosen alone |
|-----------|-----------|-----------------------------|
| **tree (typed AST)** | direct correspondence to source, trivial to render back, cheap to traverse | cannot express sharing — the same symbol referenced from six places is six nodes; dependency queries are O(n) scans |
| **graph** | dependency and conditioning are first-class edges; retrieval and provenance are natural | no canonical linearisation, so hashing and equality need a separate spanning discipline; painful to render back to source |
| **term (S-expression / first-order term)** | uniform, easy to hash, easy to rewrite | roles become positions again, which reintroduces exactly the ambiguity D-003 exists to remove |
| **hybrid** | — | **chosen** |

### The hybrid, precisely

- **The tree is the object.** A `Module` holds ordered `Statement`s holding `Expr` trees.
  This is what is parsed, type-checked, rendered and round-tripped.
- **Sharing is carried by symbol identity, not by node identity.** Every binder gets a
  `SymbolId`; every reference carries the same `SymbolId`. So the tree is a tree, but the
  *symbol graph* it induces is a genuine graph, recovered in O(n) without any node
  aliasing.
- **The graph is a derived view** (`graph/build_graph`), never authored and never parsed
  back. This keeps exactly one source of truth.
- **The canonical form is a term-like linearisation** of the tree with names erased.

This gets the graph's query power and the term's hashability without paying either one's
cost in the representation that authors and the type checker actually touch.

## 2. Node and edge inventory

Nodes: `Module`, eleven `Statement` kinds, ten `Expr` kinds, `Arg`, `ConceptMember`. Every
`Node` carries `span: Span` and `type_: Type | None`.

The graph edge vocabulary is **closed** — `graph/EDGE_KINDS` — and `add_edge` asserts
membership. An open edge vocabulary would let each backend invent its own relations, which
is how a semantic graph quietly becomes an untyped property bag.

```
has_type  declared_as  has_law  family  role  conditioned_on  depends_on
constrains  objective_of  queries  binds  scope_of  member_of  extends
obligation_on
```

`scope_of` deserves note: quantifier nesting is recorded as an explicit chain, so
"which quantifier dominates which" is a graph query rather than a tree-walk convention.
That is what makes H7 (graph retrieval) testable at all.

## 3. Symbol identity

```python
SymbolId(name: str, ordinal: int, depth: int)
    .render()    -> "sym:mu:0.3"      # human-facing, keeps the spelling
    .canonical() -> "sym:#0.3"        # identity, spelling erased
```

`depth` is binder nesting depth (0 at module level); `ordinal` is declaration order within
the scope. Together they are a locally-nameless coordinate.

**Why not De Bruijn indices.** De Bruijn indices are counted from the use site outward,
which makes every index unstable under insertion of an enclosing binder and makes
diagnostics unreadable. `(depth, ordinal)` is counted from the binder, is stable under
edits elsewhere, and keeps `name` available for error messages. The invariance property
that matters — alpha-renaming does not change identity — is obtained either way.

**Why not raw unique IDs.** A gensym counter is not stable across two independent parses
of the same program, so it cannot be hashed.

## 4. Canonical serialization

Rules, each with a reason:

| rule | reason |
|------|--------|
| sorted keys | byte-stable output across Python versions |
| ASCII only | no normalisation ambiguity; safe to hash |
| no spans | source position is not part of meaning |
| symbols as `sym:#d.o` | renaming invariance |
| distribution roles sorted by role name | writing order is not meaning; role assignment is |
| version tag `hml-canonical-0.1.0` | a schema change becomes detectable, not silent |
| names omitted when hashing | required for criterion 6 (D-010) |

`content_hash` = SHA-256 of the nameless form. Suitable for equality testing,
deduplication, benchmark keys, and dataset identity.

Two programs hash identically **iff** they differ only by variable spelling, comments,
whitespace, or the writing order of distribution roles. They hash differently if
quantifier nesting, role assignment, type structure, or statement content differs. Both
directions are property-tested.

## 5. Versioning and provenance

**Versioning** is in: `CANONICAL_VERSION` is emitted in every document and asserted by the
schema.

**Provenance is deliberately out of v0** (D-011). The graph's `depends_on` and
`conditioned_on` edges give *dependency* tracking — which symbols a definition rests on.
That is not a *derivation* record: there is no history of how a statement was obtained,
by whom, or from which prior statement. `GOAL.md` originally claimed provenance and has
been corrected.

Building provenance now would violate CLAUDE.md rule 7 (no complexity without a
demonstrated requirement) and §22 of the master directive, which explicitly defers
cryptographic provenance until the core semantics work.

## 6. Multiple views, one identity

The IR was designed so that no view is privileged:

| view | direction | fidelity |
|------|-----------|----------|
| HML-L1 | round-trip | exact |
| canonical JSON | round-trip via hash | exact |
| semantic graph / triples | one-way | exact for structure, no expression trees |
| LaTeX | one-way | **lossy** — declares it |
| controlled English | one-way | **lossy** — declares it |
| Stan / SymPy / Lean | one-way | **lossy** — declares it |

Every lossy backend reports what it dropped. See `backends/base.py`.

## 7. Known weaknesses

1. **Ordinals are positional**, so reordering two differently-typed declarations changes
   the hash even though the program means the same thing. Fixing this needs a canonical
   *ordering* of declarations, which is not obviously well defined. Unresolved.
2. **`Arg` role labelling applies only to `DistExpr`.** Ordinary `Call` arguments remain
   positional, so the role discipline is narrower than the design rhetoric implies (Q-05).
3. **Shape extents are checked nominally.** `Vector[Real, N]` and `Vector[Real, M]` differ
   by name, not by arithmetic; `Vector[Real, N+1]` is not expressible.
4. **No sharing of expression subtrees.** Common subexpressions are duplicated. Irrelevant
   at v0 scale, relevant if the IR is ever used for rewriting.
