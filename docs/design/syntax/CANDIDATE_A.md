# Candidate A — V0 labelled-linear (HML-L1 as frozen)

Implementation: `evaluation/syntax_acquisition/candidate_a.py`
Reader: `hamiltonian_lang.parser` — candidate A *is* HML-L1, so it reads with the real
compiler front end rather than a private parser.

Line-oriented, one statement per line, role-labelled distribution arguments, blocks
closed by an explicit `end`. Frozen in `docs/design/V0_DESIGN_FREEZE.md` §§1–3.

## Grammar

Terminals are as the HML-L1 lexer defines them: identifiers `[A-Za-z_][A-Za-z0-9_]*`,
numbers, and the reserved operator set. `#` begins a comment; the renderer emits none.

```
module        ::= "module" Name NEWLINE statement*

statement     ::= declaration | definition | law | proposition | objective
                | solve | infer | check | concept

declaration   ::= declkind Name ":" type [ "=" expr ] NEWLINE
declkind      ::= "var" | "param" | "const" | "obs" | "index" | "rv"

definition    ::= "def" Name [ "(" params ")" ] [ ":" type ] ":=" expr NEWLINE
params        ::= param ("," param)*
param         ::= Name [ ":" type ]

law           ::= lawrole Name [ "|" Name+ ] "~" distribution NEWLINE
lawrole       ::= "law" | "prior" | "likelihood"
distribution  ::= Family "(" role ":=" expr ("," role ":=" expr)* ")"
                | Family                     -- law position only

proposition   ::= ("assume" | "require" | "prove") expr NEWLINE
objective     ::= ("minimise" | "maximise") expr NEWLINE
solve         ::= "solve" Name ("," ? Name)* NEWLINE
infer         ::= "infer" query Name ("," ? Name)* NEWLINE
query         ::= "posterior" | "expectation" | "variance" | "mle" | "map"
check         ::= "check" expr NEWLINE
                | "check" "dimension" additive [ "=" dimension ] NEWLINE

concept       ::= "concept" Name [ "extends" Name ("," Name)* ] NEWLINE
                  member* "end" NEWLINE
member        ::= memberkind Name [ "(" typedparams ")" ] [ ":" type ]
                  [ ":=" expr ] NEWLINE
memberkind    ::= "parameter" | "transform" | "invariant" | "property"
                | "example" | "counterexample"
```

Expressions, in binding order from loosest to tightest. `=>`/`<=>` and `^` are
**right**-associative; comparisons are non-associative (chaining is HML-P230); everything
else is left-associative.

```
expr          ::= implication
implication   ::= disjunction [ ("=>" | "<=>") implication ]
disjunction   ::= conjunction ("or" conjunction)*
conjunction   ::= negation ("and" negation)*
negation      ::= "not" negation | comparison
comparison    ::= additive [ ("=" | "!=" | "<" | "<=" | ">" | ">=") additive ]
additive      ::= multiplicative (("+" | "-") multiplicative)*
multiplicative::= unary (("*" | "/" | "@") unary)*
unary         ::= "-" unary | power
power         ::= postfix [ "^" unary ]
postfix       ::= primary ("[" expr ("," expr)* "]")*
primary       ::= Number | "true" | "false" | quantifier
                | Name [ "(" arguments ")" ] | "(" expr ")"
quantifier    ::= ("forall" | "exists" | "exists" "unique")
                  Name ":" type "." expr
```

Types and dimensions:

```
type          ::= scalar | "Proposition" | ConceptName
                | "Quantity" "[" dimension "]"
                | "Vector" "[" type [ "," extent ] "]"
                | "Matrix" "[" type [ "," extent [ "," extent ] ] "]"
                | "Tensor" "[" type ("," extent)+ "]"
                | "Set" "[" type "]"
                | "Function" "[" type ("," type)* "->" type "]"
                | "Predicate" "[" type ("," type)* "]"
                | "RandomVariable" "[" type "]" | "Distribution" "[" type "]"
extent        ::= Integer | Name
dimension     ::= dimterm (("*" | "/") dimterm)*
dimterm       ::= "(" dimension ")" [ power ] | "1" | Base [ power ] | Var [ power ]
power         ::= "^" [ "-" ] Integer [ "/" Integer ]
```

`Base` is one of the seven SI base dimensions or `Dimensionless`; `Var` is a single
capital letter that is not a base dimension.

## Worked example

Source object: the Bayesian coin, `Beta(1,1)` prior, 7 successes in 10 trials.

```
module BayesianCoin
param theta : Probability
const trials : Natural = 10
obs successes : Natural = 7
prior theta ~ Beta(alpha := 1, beta := 1)
likelihood successes | theta ~ Binomial(trials := trials, prob := theta)
infer posterior theta
```

239 bytes. This block is not hand-written: `test_candidate_surfaces.py` asserts it is
byte-identical to `CandidateA().render(...)` of the compiled object.

## Two places where the renderer is written against the parser, not the pretty-printer

Both are cases where `backends/hml.py` — the shipped round-trip backend — produces text
that reads back as a **different** object. They are recorded here because candidate A's
correctness depends on not inheriting them.

1. **Right-associative operators need parentheses on the left.** `^`, `=>` and `<=>` are
   right-associative in the parser. `backends/hml.py` parenthesises neither side at equal
   precedence, so `(a ^ b) ^ c` prints as `a ^ b ^ c`, which reads back as `a ^ (b ^ c)`.
   Verified: the canonical hash changes across `parse → render → parse`.
2. **`check dimension` reads its subject at the additive level**, because the `=` that
   may follow introduces a dimension and not an equation. A subject binding looser than
   `+` must be parenthesised.

A third, in the type printer rather than the expression printer:
`FunctionType.render()` and `PredicateType.render()` separate domain components with
`*` (`Function[Real * Real -> Real]`), but `parser.parse_type` reads a **comma**-separated
domain and rejects `*` with HML-P222/HML-P201. `Type.render()` is therefore not a
round-trippable spelling for either constructor at arity ≥ 2. Candidate A emits the comma
form.

## What candidate A cannot express

Everything in the shared exclusion list in [README.md](README.md#outside-the-subset-for-every-candidate),
plus one restriction that is A's alone:

* **identifiers that collide with HML-L1's 47 keywords.** `param law : Real` is a parse
  error (HML-P202). Candidates C and D could carry such a name; the frozen subset
  excludes it everywhere so that the four stay comparable.

A accepts an **empty document** as the empty module `Main`; C and D reject it. See the
asymmetry note in [README.md](README.md#one-measured-asymmetry-outside-the-subset).
