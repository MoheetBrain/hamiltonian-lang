# SPEC — Hamiltonian Lang v0 (HML-L1)

Normative reference for the frozen v0 subset. Where this document and the implementation
disagree, that is a bug in one of them; file it.

## 1. Lexical structure

Source is 7-bit ASCII. One statement per line. `#` begins a comment that runs to end of
line. Blank lines are insignificant.

```
identifier  ::= [A-Za-z_][A-Za-z0-9_]*
number      ::= [0-9]+ ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
```

Reserved operators, longest match first:

```
<=>  :=  ->  =>  <=  >=  !=  ::  **
:  ~  |  @  ^  +  -  *  /  =  <  >  (  )  [  ]  ,  .
```

Reserved words are listed in `lexer/__init__.py::KEYWORDS` and may not be used as
identifiers (`HML-P202`).

Unicode input is accepted and normalised, never made canonical. Greek letters in
identifier position fold to their ASCII spelling with warning `HML-L102`; `∀ ∃ → ⇒ ↔ ≤ ≥
≠ × ÷ ∼` normalise to their ASCII tokens with `HML-L103`; every other non-ASCII character
is error `HML-L101`.

## 2. Types

```
Bool
PositiveNatural <: Natural <: Integer <: Rational <: Real
Natural         <: NonNegativeReal
PositiveNatural <: PositiveReal <: NonNegativeReal <: Real
Probability     <: NonNegativeReal
```

`Probability` and `PositiveReal` are **incomparable** (D-004).

Constructors:

```
Vector[T, n]            Matrix[T, m, n]         Tensor[T, ...]
Set[T]                  Function[T, ... -> U]   Predicate[T, ...]
RandomVariable[T]       Distribution[T]         Quantity[D]
Proposition
```

`n`, `m` may be a positive integer literal, a symbolic name, or `?` (unknown extent,
which unifies with anything).

`D` is a dimension expression over `Mass Length Time Temperature Current Amount
Luminosity` and `Dimensionless`, with `*`, `/`, and `^` applied to rational literals.
Dimensions are rational-exponent vectors, so dimensional equality is exact and decidable.

`Function` is contravariant in its domain and covariant in its codomain. `Vector`,
`Matrix`, `Set`, `RandomVariable` and `Distribution` are covariant in their parameter.

There is **no subtyping path** between `T`, `RandomVariable[T]` and `Distribution[T]`.

A numeric literal is checked against a refinement by its **value**, not its nominal type
(D-009), so `const p : Probability = 1` is well typed.

## 3. Statements

```
module        <Name>
var|param|const|obs|index|rv  <name> : <Type> [= <expr>]
def           <name> [( <params> )] [: <Type>] := <expr>
law|prior|likelihood  <target> [| <ref>...] ~ <DistExpr>
assume        <proposition>
require       <proposition>
prove         <proposition>
minimise|maximise  <expr>
solve         <ref>...
infer         posterior|expectation|variance|mle|map  <ref>...
check         dimension <expr> [= <dimension>]
check         <proposition>
concept       <Name> [extends <Name>, ...]  <member>...  end
```

Concept members: `parameter` · `transform` · `invariant` · `property` · `example` ·
`counterexample`. A concept declaring neither an invariant nor an example is rejected
(`HML-S603`): a term that only sounds plausible is not a definition.

## 4. Expressions

Precedence, loosest first:

| level | operators | associativity |
|-------|-----------|---------------|
| 1 | `=>` `<=>` `implies` `iff` | right |
| 2 | `or` | left |
| 3 | `and` | left |
| 4 | `=` `!=` `<` `<=` `>` `>=` | **non-associative** |
| 5 | `+` `-` | left |
| 6 | `*` `/` `@` | left |
| 7 | unary `-`, `not` | prefix |
| 8 | `^` | right |

Comparison chaining (`0 < x < 1`) is a parse error (`HML-P230`). It is written
`0 < x and x < 1`.

Quantifiers require an explicit domain and a `.` separator:

```
forall x : Real . exists y : Real . y > x
```

Nesting order is structural. The two orderings produce different ASTs, different
canonical forms, and different content hashes.

## 5. Distribution expressions

```
<Family> ( <role> := <expr> , ... )
```

Roles are mandatory and unique. Positional arguments are `HML-P234`; a repeated role is
`HML-P235`. Argument *order* is not semantically significant and is normalised away in the
canonical form; role *assignment* is significant.

Families and their roles are defined in `type_system/distributions.py`. Common wrong role
names (`variance`, `mean`, `sd`, `n`, `p`, `lambda`, …) produce a targeted diagnostic
naming the confusion rather than a generic "unknown argument".

## 6. Laws

`law t | g... ~ D` requires that the support of `D` inhabit the declared type of `t`
(or its codomain, when `t : RandomVariable[T]`). A symbol has at most one law
(`HML-S601`). `infer posterior x` requires that `x` have a law (`HML-S604`).

## 7. Canonical form

Deterministic JSON: sorted keys, ASCII, no source spans, symbol references as
`sym:#<depth>.<ordinal>`, distribution roles sorted, schema version tagged.
`content_hash` additionally omits declaration names, so that:

- consistent renaming does not change the hash;
- quantifier reordering does change it;
- swapping two role assignments does change it;
- comments and whitespace do not change it.

## 8. Diagnostic codes

| range | stage |
|-------|-------|
| `HML-L1xx` | lexical |
| `HML-P2xx` | parse |
| `HML-N3xx` | name resolution and scope |
| `HML-T4xx` | type |
| `HML-D5xx` | dimensional |
| `HML-S6xx` | semantic / structural |
| `HML-B7xx` | backend |

Every diagnostic carries a code, a span, and — where a correction exists — a concrete
`help:` line. A diagnostic that says only "type error" is a defect.

## 9. Proof obligations

Every `require`, `assume`, `prove`, concept `invariant`, and every declaration of a
refined scalar type generates a `ProofObligation`. **v0 discharges none of them** except
dimensional checks, which the type system decides. `hml obligations FILE` lists them with
their status. Nothing in v0 constitutes a proof.
