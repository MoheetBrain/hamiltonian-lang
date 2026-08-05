# Candidate D — constrained JSON / graph

Implementation: `evaluation/syntax_acquisition/candidate_d.py`
Document tag: `hml-graph-d-1`

A node-typed tree with named edges, serialised as JSON with sorted keys and two-space
indentation. Informed by the `e_graph_triple` sketch in `examples/candidate_syntaxes/`,
with one deliberate and load-bearing departure from it.

## References are by name, not by node identity

The triple sketch writes

```
_:q1cl is Ref
_:q1cl refTo _:q1y
```

— an edge straight from a use to its binder. That hands candidate D the result of name
resolution, which candidates A, B and C all have to earn by walking scopes. It is exactly
the information leak that would invalidate the tournament, and it would **not** have shown
up in the round-trip figures: a pre-resolved document round-trips perfectly and hashes
correctly. It is caught instead by the "no pre-resolution" check, which asserts that no
candidate's parse output carries a `SymbolId`, and by its negative control
`test_pre_resolution_leak_is_detected`.

So D writes `{"node": "reference", "name": "y"}` and lets the shared resolver do the same
work it does for the other three. For the same reason a D document carries **no** node
ids, ordinals, depths, inferred types, distribution supports, or proof obligations.
Everything in it is something an author typed.

## Shape constraints, enforced on read

* every object carries a `node` (or `ctor`, or `member_kind`) discriminator drawn from a
  closed set;
* **no additional keys are tolerated.** An unexpected key is an error, not a comment.
  Tolerating one is how a surface acquires a private channel: the key carries information,
  nothing complains, and the tournament silently stops comparing like with like.
  `test_malformed.py` includes a document whose only defect is an extra
  `"resolved_symbol"` field;
* every required key must be present — no defaulting;
* numbers keep their JSON kind, so the integer `1` and the real `1.0` stay distinct, as
  they do in the canonical form;
* rational dimension exponents are **strings** (`"3/2"`), because JSON has no rationals
  and a float exponent is not exact. A numeric exponent is rejected;
* the document must be ASCII.

## Schema

```
document      = { "surface": "hml-graph-d-1", "module": Name, "statements": [ statement ] }

statement     = { "node": "declaration", "declaration_kind": declkind,
                  "name": Name, "type": type, "value": expr | null }
              | { "node": "definition", "name": Name,
                  "parameters": [ { "name": Name, "type": type | null } ],
                  "type": type | null, "body": expr }
              | { "node": "law", "role": lawrole, "target": Name,
                  "given": [ Name ], "distribution": distribution }
              | { "node": "assumption" | "constraint" | "theorem", "proposition": expr }
              | { "node": "objective", "direction": "minimise" | "maximise",
                  "expression": expr }
              | { "node": "solve", "targets": [ Name ] }
              | { "node": "inference", "query": query, "targets": [ Name ] }
              | { "node": "check", "subject": expr }
              | { "node": "dimension_check", "subject": expr,
                  "expected": dimension | null }
              | { "node": "concept", "name": Name, "extends": [ Name ],
                  "members": [ member ] }

member        = { "member_kind": memberkind, "name": Name,
                  "parameters": [ { "name": Name, "type": type | null } ],
                  "type": type | null, "body": expr | null }

expr          = { "node": "literal", "value": Number | Boolean }
              | { "node": "reference", "name": Name }
              | { "node": "unary", "operator": "-" | "not", "operand": expr }
              | { "node": "binary", "operator": "+|-|*|/|^|@",
                  "left": expr, "right": expr }
              | { "node": "comparison", "operator": "=|!=|<|<=|>|>=",
                  "left": expr, "right": expr }
              | { "node": "logical", "operator": "and|or|implies|iff",
                  "left": expr, "right": expr }
              | { "node": "call", "callee": Name, "arguments": [ expr ] }
              | { "node": "index", "base": expr, "indices": [ expr ] }
              | distribution
              | { "node": "quantifier",
                  "quantifier": "forall" | "exists" | "exists_unique",
                  "variable": Name, "variable_type": type, "body": expr }

distribution  = { "node": "distribution", "family": Name,
                  "arguments": [ { "role": Name, "value": expr } ] }

type          = { "ctor": scalar }                        -- Real, Probability, ...
              | { "ctor": "Proposition" }
              | { "ctor": "Concept", "name": Name }
              | { "ctor": "Quantity", "dimension": dimension }
              | { "ctor": "Vector", "element": type, "length": extent | null }
              | { "ctor": "Matrix", "element": type,
                  "rows": extent | null, "columns": extent | null }
              | { "ctor": "Tensor", "element": type, "shape": [ extent ] }
              | { "ctor": "Set", "element": type }
              | { "ctor": "Function", "domain": [ type ], "codomain": type }
              | { "ctor": "Predicate", "domain": [ type ] }
              | { "ctor": "RandomVariable", "codomain": type }
              | { "ctor": "Distribution", "support": type }
extent        = Integer | Name

dimension     = { "numerator":   [ [ Name, RationalString ] ],
                  "denominator": [ [ Name, RationalString ] ] }
```

## Dimensions: why not an exponent vector

`Mass * Length^2 / Time^2` becomes

```json
{"numerator": [["Length", "2"], ["Mass", "1"]], "denominator": [["Time", "2"]]}
```

— the same terms, the same grouping, the same **positive** exponents as the linear
surfaces print. The signed vector `[["Length","2"],["Mass","1"],["Time","-2"]]` is what
`types.Dimension` actually stores and would have been shorter, but publishing it would
give a D reader the answer to "what is the exponent of Time?" for free while readers of
A, B and C have to combine the `/` with the exponent themselves. Same reasoning, same
decision, as candidate C.

## Worked example

```json
{
  "module": "BayesianCoin",
  "statements": [
    {
      "declaration_kind": "param",
      "name": "theta",
      "node": "declaration",
      "type": {
        "ctor": "Probability"
      },
      "value": null
    },
    {
      "declaration_kind": "const",
      "name": "trials",
      "node": "declaration",
      "type": {
        "ctor": "Natural"
      },
      "value": {
        "node": "literal",
        "value": 10
      }
    },
    {
      "declaration_kind": "obs",
      "name": "successes",
      "node": "declaration",
      "type": {
        "ctor": "Natural"
      },
      "value": {
        "node": "literal",
        "value": 7
      }
    },
    {
      "distribution": {
        "arguments": [
          {
            "role": "alpha",
            "value": {
              "node": "literal",
              "value": 1
            }
          },
          {
            "role": "beta",
            "value": {
              "node": "literal",
              "value": 1
            }
          }
        ],
        "family": "Beta",
        "node": "distribution"
      },
      "given": [],
      "node": "law",
      "role": "prior",
      "target": "theta"
    },
    {
      "distribution": {
        "arguments": [
          {
            "role": "trials",
            "value": {
              "name": "trials",
              "node": "reference"
            }
          },
          {
            "role": "prob",
            "value": {
              "name": "theta",
              "node": "reference"
            }
          }
        ],
        "family": "Binomial",
        "node": "distribution"
      },
      "given": [
        "theta"
      ],
      "node": "law",
      "role": "likelihood",
      "target": "successes"
    },
    {
      "node": "inference",
      "query": "posterior",
      "targets": [
        "theta"
      ]
    }
  ],
  "surface": "hml-graph-d-1"
}
```

1 909 bytes against candidate A's 239 — **8.0× on this example, 9.3× over the 612-object
corpus.** That is the headline cost of the surface and it is not a rendering artefact:
compact separators and no indentation still leave D well above the others, because every
node pays for a discriminator key and a JSON envelope. Whether that cost buys anything is
the tournament's question, not this phase's.

This block is asserted byte-identical to `CandidateD().render(...)` by
`test_candidate_surfaces.py`.

## What candidate D cannot express

Everything in the shared exclusion list in [README.md](README.md#outside-the-subset-for-every-candidate).
There is nothing beyond it: D reserves no identifier, since its special words are all JSON
keys, and it could carry `?` extents and HML-L1 keywords as names — it is restricted from
doing so only because the subset is the union of every surface's limits.

D **rejects an empty document**, because the JSON envelope is mandatory. A and B accept
one. See the asymmetry note in [README.md](README.md#one-measured-asymmetry-outside-the-subset).
