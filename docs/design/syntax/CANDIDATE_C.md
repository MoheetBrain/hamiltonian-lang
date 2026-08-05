# Candidate C — prefix / S-expression

Implementation: `evaluation/syntax_acquisition/candidate_c.py`

One shape for everything: `(head . operands)`. Nesting is bracket nesting, so binder scope
is visible without a precedence table — the property the `c_sexpr` sketch in
`examples/candidate_syntaxes/` was written to show, now made to compile.

## Three rules that keep it unambiguous

* **Heads are a closed vocabulary.** Every list head is drawn from a fixed set
  (`candidate_c.C_HEADS`). A user symbol never appears in head position: an ordinary
  function call is `(call f x)`, never `(f x)`. No program can therefore be read two ways
  depending on whether a name collides with an operator. `test_candidate_surfaces.py`
  round-trips an object whose symbols are spelled `call`, `neg`, `mul`, `pow` and `given`
  to demonstrate it.
* **Unary minus is `neg`, not `-`.** Dispatching `-` on arity would work, but it makes
  arity load-bearing for the *meaning* of a head, which is the kind of context-dependence
  the v0 freeze excludes.
* **An unknown extent is written by omission**, exactly as in the linear surfaces, so no
  candidate carries an extent the others must infer.

Two atoms cannot be identifiers and so cannot collide with user names: `#none` (absent
type, absent body) and `#t`/`#f` (booleans). `;` begins a comment; the renderer emits none.
An atom is any run of characters other than whitespace, `(`, `)` and `;`.

## Grammar

```
document      ::= "(" "module" Name statement* ")"

statement     ::= "(" "dec" declkind Name type [ expr ] ")"
                | "(" "def" Name "(" param* ")" typeOrNone expr ")"
                | "(" "law" lawrole Name "(" "given" Name* ")" dist ")"
                | "(" ("assume" | "require" | "prove" | "check") expr ")"
                | "(" "check-dim" expr [ dimension ] ")"
                | "(" "objective" ("minimise" | "maximise") expr ")"
                | "(" "solve" Name+ ")"
                | "(" "infer" query Name+ ")"
                | "(" "concept" Name "(" "extends" Name* ")" member* ")"

param         ::= "(" Name ")" | "(" Name type ")"
member        ::= "(" memberkind Name "(" param* ")" typeOrNone exprOrNone ")"
typeOrNone    ::= type | "#none"
exprOrNone    ::= expr | "#none"

expr          ::= Number | "#t" | "#f" | Name
                | "(" binop expr expr ")"        -- + - * / ^ @
                | "(" cmpop expr expr ")"        -- = != < <= > >=
                | "(" logop expr expr ")"        -- and or => <=>
                | "(" "neg" expr ")" | "(" "not" expr ")"
                | "(" "call" Name expr* ")"
                | "(" "index" expr expr+ ")"
                | dist
                | "(" quant "(" Name type ")" expr ")"
quant         ::= "forall" | "exists" | "exists-unique"
dist          ::= "(" "dist" Family arg* ")"
arg           ::= "(" role expr ")"

type          ::= scalar | "Proposition" | "Dimensionless" | ConceptName
                | "(" "Quantity" dimension ")"
                | "(" "Vector" type [ extent ] ")"
                | "(" "Matrix" type [ extent [ extent ] ] ")"
                | "(" "Tensor" type extent+ ")"
                | "(" "Set" type ")"
                | "(" "Function" "(" type+ ")" type ")"
                | "(" "Predicate" type+ ")"
                | "(" "RandomVariable" type ")" | "(" "Distribution" type ")"
extent        ::= Integer | Name

dimension     ::= "Dimensionless" | Base | Var
                | "(" "pow" dimension Rational ")"
                | "(" "mul" dimension dimension+ ")"
                | "(" "div" dimension dimension ")"
Rational      ::= Integer | Integer "/" Integer      -- e.g. 2, -1, 3/2
```

Arity is fixed for every head, so a truncated or over-long form is a parse error rather
than a silently different reading.

## Dimensions: why not an exponent vector

`(div (mul (pow Length 2) Mass) (pow Time 2))` is a term-for-term transliteration of what
the linear surfaces print, `Length^2 * Mass / Time^2`: the same terms, the same grouping,
the same positive exponents. The shorter `((Length 2) (Mass 1) (Time -2))` was rejected.
It is the signed exponent vector the IR stores, and publishing it would hand candidate C a
normalisation — "the exponent of Time is −2" — that readers of candidates A and B have to
perform for themselves. That is the information leak this phase exists to prevent, and it
would not have shown up in the round-trip figures, only in a later tournament.

## Worked example

```
(module BayesianCoin
  (dec param theta Probability)
  (dec const trials Natural 10)
  (dec obs successes Natural 7)
  (law prior theta (given) (dist Beta (alpha 1) (beta 1)))
  (law likelihood successes (given theta) (dist Binomial (trials trials) (prob theta)))
  (infer posterior theta))
```

291 bytes, 1.22× candidate A on this example and 1.25× over the 612-object corpus. This
block is asserted byte-identical to `CandidateC().render(...)` by
`test_candidate_surfaces.py`.

The quantifier case is where the shape pays for itself — binder nesting *is* bracket
nesting, so the two scopings of the same atoms differ only in where the parentheses close:

```
(forall (x Real) (exists (y Real) (> y x)))
(exists (y Real) (forall (x Real) (> y x)))
```

## What candidate C cannot express

Everything in the shared exclusion list in [README.md](README.md#outside-the-subset-for-every-candidate).
There is nothing beyond it: C reserves no identifier, since every special word occurs only
in head position, and it can carry `?` extents and HML-L1 keywords as names — it is
restricted from doing so only because the subset is the union of every surface's limits.

C **rejects an empty document**, because the `(module …)` envelope is mandatory. A and B
accept one. See the asymmetry note in [README.md](README.md#one-measured-asymmetry-outside-the-subset).
