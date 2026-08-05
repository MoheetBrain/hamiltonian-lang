# Candidate B — simplified V1 labelled-linear

Implementation: `evaluation/syntax_acquisition/candidate_b.py`

Same semantics as candidate A, the same operators, the same role discipline, and
**17 reserved words instead of 47**.

## The single idea

Where HML-L1 spends a distinct keyword on each member of a closed family, B spends one
keyword on the family and writes the member as an ordinary word in a position where
nothing else can appear. `param`, `prior`, `posterior`, `invariant`, `min` are not
reserved in B: they are identifiers that happen to carry meaning immediately after
`dec`, `dist`, `ask`, at the head of a concept-member line, and after `opt`.

| HML-L1 | B |
|---|---|
| `var\|param\|const\|obs\|index\|rv x : T` | `dec <kind> x : T` |
| `def f(..) : T := e` | `fun f(..) : T := e` |
| `law\|prior\|likelihood y \| x ~ D` | `dist <role> y \| x ~ D` |
| `assume\|require\|prove\|check p` | `say <mode> p` |
| `check dimension e [= d]` | `say dim e [= d]` |
| `minimise\|maximise e` | `opt <min\|max> e` |
| `solve r…` / `infer <q> r…` | `ask <query> r…` |
| `concept C extends B1, B2 … end` | `kind C < B1, B2 … end` |
| `forall` / `exists` / `exists unique` | `all` / `some` / `one` |
| `implies` / `iff` keywords | `=>` / `<=>` only |

Reserved, in full:

```
mod dec fun dist say opt ask kind end all some one and or not true false
```

`and`, `or`, `not`, `true`, `false` stay reserved because they occur where an identifier
could also occur. `all`, `some`, `one` likewise. `end` must be distinguishable from a
concept-member line. Everything else is contextual.

## What is deliberately *not* simplified

Each of these would be a shorter surface and a semantic regression, so each was rejected:

* **`:=` still binds and `=` still means equality.** Collapsing them onto one token is
  the single largest saving available and it is exactly the conflation `CLAUDE.md`
  forbids.
* **Distribution arguments keep mandatory role labels** (D-003). Positional arguments are
  a parse error in B as in A.
* **Quantified variables keep mandatory type annotations.** Untyped quantification is
  rejected: the domain must be explicit.
* **Conditioning keeps its own token `|`.**
* **`~` is not `=` and not `:=`.**

One thing B removes that costs nothing: HML-L1 accepts two spellings for several
constructs (`=` and `:=` for declaration initialisers, `minimise`/`minimize`, `def`/`fn`,
`:`/`::`, `^`/`**`). B has exactly one spelling for everything, so its renderer is
deterministic by construction rather than by convention.

## Grammar

```
module        ::= "mod" Name NEWLINE statement*

statement     ::= "dec" declkind Name ":" type [ ":=" expr ] NEWLINE
                | "fun" Name [ "(" params ")" ] [ ":" type ] ":=" expr NEWLINE
                | "dist" lawrole Name [ "|" namelist ] "~" distribution NEWLINE
                | "say" ("assume" | "require" | "prove" | "check") expr NEWLINE
                | "say" "dim" additive [ "=" dimension ] NEWLINE
                | "opt" ("min" | "max") expr NEWLINE
                | "ask" ("solve" | query) namelist NEWLINE
                | concept

declkind      ::= "var" | "param" | "const" | "obs" | "index" | "rv"
lawrole       ::= "law" | "prior" | "likelihood"
query         ::= "posterior" | "expectation" | "variance" | "mle" | "map"
namelist      ::= Name ("," Name)*

concept       ::= "kind" Name [ "<" Name ("," Name)* ] NEWLINE member* "end" NEWLINE
member        ::= memberkind Name [ "(" typedparams ")" ] [ ":" type ]
                  [ ":=" expr ] NEWLINE
memberkind    ::= "parameter" | "transform" | "invariant" | "property"
                | "example" | "counterexample"

quantifier    ::= ("all" | "some" | "one") Name ":" type "." expr
```

Every other production — expressions, types, dimensions, distributions — is candidate A's,
unchanged, including the precedence table and its associativities. The two surfaces share
one printer and one reader (`evaluation/syntax_acquisition/_infix.py`) so that they cannot
drift apart on a precedence question.

## Worked example

```
mod BayesianCoin
dec param theta : Probability
dec const trials : Natural := 10
dec obs successes : Natural := 7
dist prior theta ~ Beta(alpha := 1, beta := 1)
dist likelihood successes | theta ~ Binomial(trials := trials, prob := theta)
ask posterior theta
```

258 bytes against candidate A's 239 — **B is longer**, not shorter, on this example, and
1.06× A's total over the 612-object corpus. The keyword *count* fell by 64%; the byte
count rose by 6%, because `dec ` and `dist ` are prefixes A does not pay for. If B has an
advantage it is in the size of the vocabulary a reader has to hold, not in tokens, and
this phase does not measure the former.

This block is asserted byte-identical to `CandidateB().render(...)` by
`test_candidate_surfaces.py`.

## What candidate B cannot express

Everything in the shared exclusion list in [README.md](README.md#outside-the-subset-for-every-candidate),
plus one restriction that is B's alone:

* **identifiers that collide with B's 17 reserved words**, of which 11
  (`mod dec fun dist say opt ask kind all some one`) are free identifiers in HML-L1. The
  frozen subset excludes them everywhere so that the four stay comparable, which means
  candidate A is carrying a restriction it does not need — the mirror image of the note
  in candidate A's document.

B accepts an **empty document** as the empty module `Main`, as A does; C and D reject it.
