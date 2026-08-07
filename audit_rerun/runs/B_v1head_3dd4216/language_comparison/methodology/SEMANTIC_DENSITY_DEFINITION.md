# Semantic Density: Definition and Anti-Gaming Rules

Status: normative. This document defines the only sanctioned way to compute and
report density figures in the comparison.

---

## 1. The problem this document exists to prevent

"Semantic density" is intuitively *meaning per unit of notation*. Every naive
formalisation of it rewards the wrong behaviour, because the cheapest way to
raise a ratio whose denominator is length is to shorten the notation — and the
cheapest way to shorten notation is to stop saying things.

Concretely, the failure looks like this. Take the statement

> Let X be a random variable distributed normally with mean μ and standard
> deviation σ, where σ > 0.

A representation that writes `X ~ Normal(mu, sigma), sigma > 0` and one that
writes `X = N(m,s)` differ in length by a factor of about two. If facts are
counted from the *source statement* rather than from the *encoding*, both are
credited with the same fact count and the shorter one wins — despite having lost
the distributed-as relation (it wrote `=`), the parameter roles, and the
positivity constraint.

The rule that follows from this is the single most important rule in this
document:

> **Anti-gaming invariant.** Dropping semantics must never increase a density
> score. Formally: if encoding *E'* represents a strict subset of the faithful
> facts represented by *E*, then `density(E') ≤ density(E)`, for every specimen
> and every length measure.

Section 5 gives the formula that enforces this and proves it does.

---

## 2. Definitions

### 2.1 Canonical fact inventory (the reference)

For each specimen in `../benchmarks/semantic_density_specimens/SPECIMENS.json`,
a **canonical fact inventory** enumerates the distinct semantic facts asserted by
the mathematical object, in a **language-independent** form. Each fact has an id,
a prose statement and a kind drawn from:

| Kind | What it asserts |
|---|---|
| `ENTITY` | An object exists and is named. |
| `TYPE` | An object belongs to a type or mathematical kind. |
| `ROLE` | An object plays a specific structural role (location parameter, index, response variable). |
| `CONSTRAINT` | A restriction that must hold (positivity, normalisation, shape conformability). |
| `RELATION` | A relation holds between named objects (distributed-as, equality, membership, dependence). |
| `QUANTIFIER` | A binder with its variable, its domain, and its position in the alternation order. |
| `DOMAIN` | The set or region over which something ranges or is defined. |
| `EPISTEMIC` | The status of the statement: assumed, approximate, conditional, observed, unknown. |

The inventory is fixed **before** any system is encoded and is not amended in
response to what a system turns out to support. Amendments require a version bump
of the specimen file and re-measurement of every system.

`SEMANTIC_FACT_COUNT(p) = |inventory(p)|` — a property of the specimen alone.

### 2.2 Faithful representation of a fact

Given an encoding *E* of specimen *p* in system *S*, a fact *f* is **faithfully
represented** iff all three hold:

1. **Present** — *f* is determined by *E*. Not by the surrounding prose, not by
   an identifier's spelling, not by a comment: by the interpreted content.
2. **Recoverable** — *S*'s own machinery can extract *f* from *E*: the type
   checker knows it, the printer emits it, a query can retrieve it, or the
   canonical form contains it. A fact a human can infer but the system cannot is
   not represented.
3. **Enforced where enforceable** — if *f* is a `CONSTRAINT`, *S* rejects the
   corresponding violating instance. A constraint that is stored but never
   checked is `PRESENT_UNENFORCED` and counts as **half** a fact (see §2.4).

`FAITHFUL_FACTS(S, p) = |{ f ∈ inventory(p) : f faithfully represented }|`

### 2.3 Semantic fidelity

```
SEMANTIC_FIDELITY(S, p) = FAITHFUL_FACTS(S, p) / SEMANTIC_FACT_COUNT(p)   ∈ [0, 1]
```

Fidelity is the primary reported quantity. Density is secondary and is
**meaningless without it**. Any table showing density must show fidelity in an
adjacent column.

### 2.4 Partial credit schedule

Facts are not all-or-nothing in practice, so the credit schedule is fixed here
and applied uniformly:

| Situation | Credit |
|---|---|
| Present, recoverable, enforced | 1.0 |
| Present and recoverable; a `CONSTRAINT` that is stored but not checked | 0.5 |
| Present and recoverable, but only after a system-specific transformation the user must invoke | 0.5 |
| Present in an identifier name, comment, or docstring only | 0.0 |
| Present but **wrong** (an incorrect fact asserted in place of the correct one) | −1.0 |

The negative credit for a *wrong* fact is deliberate. Writing `X = Normal(μ,σ)`
does not merely fail to assert "X is distributed as"; it asserts something false
("X equals a distribution object"). A representation that states falsehoods is
worse than one that is silent, and the arithmetic must reflect that. Consequently
`FAITHFUL_FACTS` may be negative, and fidelity may be negative; this is reported
as-is and not clamped.

### 2.5 Length measures

Three, all reported:

- `TOKENS(S, p)` — token count under the frozen tokenizer (§4).
- `CHARACTERS(S, p)` — Unicode code points of the encoding, excluding trailing
  whitespace, including all syntactically required punctuation.
- `AST_NODES(S, p)` — nodes in the system's own parsed representation, counted by
  the system's own API where one exists; `null` where the system exposes no AST
  (a `null` is reported as `null`, never as an estimate).

### 2.6 The density family

```
TOKENS_PER_FAITHFUL_FACT(S, p)     = TOKENS(S, p)     / FAITHFUL_FACTS(S, p)
CHARACTERS_PER_FAITHFUL_FACT(S, p) = CHARACTERS(S, p) / FAITHFUL_FACTS(S, p)
AST_NODES_PER_FAITHFUL_FACT(S, p)  = AST_NODES(S, p)  / FAITHFUL_FACTS(S, p)

SEMANTIC_DENSITY(S, p) = FAITHFUL_FACTS(S, p) / TOKENS(S, p)
```

All four are **lower-is-better** except `SEMANTIC_DENSITY`, which is its
reciprocal and is higher-is-better. Report one or the other consistently within a
table; never mix directions in one figure.

Undefined cases: if `FAITHFUL_FACTS ≤ 0` the per-fact ratios are undefined and
are reported as `undefined`, never as infinity and never as a large number.

---

## 3. Why the naive formula is gameable, and how the operational one is not

### 3.1 Attack A — say less

*Attack:* omit the positivity constraint and the parameter roles; the encoding
gets shorter.

*Naive outcome:* `facts/tokens` rises because facts were counted from the
specimen, not the encoding.

*Operational outcome:* the omitted facts are not faithfully represented, so
`FAITHFUL_FACTS` falls by exactly the number omitted while `TOKENS` falls by at
most the tokens that expressed them. Since removing a fact costs at least one
token but removes exactly one fact, the ratio cannot improve unless a single
token was expressing more than one fact — which is the definition of a genuinely
denser notation, and is precisely what we intend to reward. Proof sketch in §5.

### 3.2 Attack B — abbreviate identifiers

*Attack:* rename `sigma` to `s`, `Normal` to `N`.

*Outcome:* `CHARACTERS` falls, `TOKENS` is unchanged (identifiers are one token
each under the frozen tokenizer), `FAITHFUL_FACTS` may fall if the abbreviation
destroys a distinction (e.g. `N` ambiguous between Normal and the naturals).
Mitigation: tokens are the primary length measure; characters are reported
alongside precisely so that a character-only advantage is visible as such.

### 3.3 Attack C — implicit defaults

*Attack:* make the system assume a default (independence, a parameterisation, a
unit) so it need not be written.

*Outcome:* a defaulted fact is `present` (the system does determine it) and
`recoverable`, so it counts — **but** the specimen inventory includes the fact,
and if the default differs from the specimen's assertion, the fact is *wrong* and
scores −1.0. Defaults therefore help only when they match, and are severely
penalised when they silently disagree. Additionally, every defaulted fact is
tagged `by_default: true` in the record, and the count of defaulted facts is
reported: a system whose density comes mostly from defaults is making a different
kind of claim than one that states things explicitly.

### 3.4 Attack D — fact-splitting in the inventory

*Attack:* inflate a favoured system's score by splitting one fact into three in
the inventory.

*Mitigation:* the inventory is language-independent, authored before probing, and
frozen; splitting affects **all** systems' numerators equally, so it cannot
create a relative advantage. Cross-specimen comparison of raw fact counts is
prohibited for the same reason — only within-specimen, across-system comparisons
are sanctioned.

### 3.5 Attack E — encode the fact somewhere the tokenizer cannot see

*Attack:* put semantics in a separate schema file, a naming convention, or an
external annotation, so the measured encoding is short.

*Mitigation:* the measured encoding is **everything the user must write** to
obtain that fidelity, including any auxiliary declarations, imports of
non-standard definitions, and side files. Standard-library imports available to
all systems are excluded uniformly; anything the user authored is included.

### 3.6 Attack F — measure only easy specimens

*Mitigation:* the specimen set spans all 13 domains and is fixed. A system may
not be scored on a subset; a specimen it cannot encode is recorded with
`FAITHFUL_FACTS` reflecting exactly what it managed, including 0.

---

## 4. Frozen tokenizer requirement

Density figures are only comparable if length is measured identically. The
tokenizer is therefore **specified, versioned and shared** rather than delegated
to each system's own lexer, because a system's own lexer is under the control of
the party being measured.

Requirements:

1. **One tokenizer for all systems.** A single reference tokenizer, checked into
   the audit tree, with a version string emitted into every result record. Using
   each system's native lexer is prohibited: differing lexer conventions (is
   `f(x)` two tokens or four?) would let tokenization choices masquerade as
   density differences.
2. **Specification.** The reference tokenizer emits exactly these token classes:
   `IDENTIFIER`, `NUMBER`, `STRING`, `OPERATOR`, `DELIMITER`, `KEYWORD`. Rules:
   - Maximal-munch identifiers: `[A-Za-z_][A-Za-z0-9_]*` plus Unicode letters, one
     token regardless of length (so identifier length is a *character* effect).
   - Numeric literals including exponent and decimal point: one token.
   - Each bracket, comma, semicolon and colon: one token.
   - Maximal-munch operator symbols from a fixed table (`<=`, `~`, `=>`, `|->`,
     `:=`, `**`, …): one token each; unlisted symbol runs split per character.
   - Whitespace and line breaks: not tokens.
   - Comments: **not tokens**, and their content is not counted as fact-bearing.
3. **Frozen before measurement.** The tokenizer version is fixed before any
   system is measured. Any change requires re-measuring every system and a new
   version string; partial re-measurement is prohibited.
4. **No per-system tuning.** The operator table is populated from the union of all
   compared systems' operators before measurement begins, not adjusted afterwards.
5. **Published.** The tokenizer source and its test vectors are part of the audit
   artefact so any figure can be recomputed by a third party.
6. **Failure mode disclosure.** Where a system's notation is inherently
   token-disadvantaged by this tokenizer (e.g. it uses multi-character ASCII
   digraphs where another uses a single Unicode symbol), that is recorded as a
   known measurement bias next to the figure.

---

## 5. The anti-gaming formula and why it holds

Let *E* be an encoding with faithful fact set *F(E)* and token length *T(E)*.
Define

```
density(E) = |F(E)| / T(E),     with |F(E)| computed by §2.4 credits.
```

Let *E'* be obtained from *E* by removing the notation expressing some fact
*f ∈ F(E)*, so `F(E') = F(E) \ {f}` and `T(E') = T(E) − k` where *k ≥ 1* is the
number of tokens that expressed *f* and nothing else.

Then

```
density(E') = (|F| − 1) / (T − k)      and      density(E) = |F| / T
```

`density(E') > density(E)` requires `(|F| − 1)·T > |F|·(T − k)`, i.e.
`k·|F| > T`, i.e. `k > T / |F|`.

Reading: removing a fact improves density **only if** the notation for that one
fact was longer than the encoding's average tokens-per-fact. That is exactly the
case where the notation for that fact was inefficient — and the correct response
is to improve the notation, not to delete the fact. To close even that gap the
comparison additionally applies:

**Fidelity gate.** Density figures are compared **only** between encodings with
equal fidelity:

```
comparable(E_S, E_T)  ⟺  SEMANTIC_FIDELITY(S,p) == SEMANTIC_FIDELITY(T,p)
```

Where fidelity differs, the pair is reported as **not comparable on density**,
and only fidelity is reported. This is unconditional and admits no exceptions:
it makes the "say less" strategy unable to produce a density comparison at all,
rather than merely unlikely to win one.

**Fidelity-adjusted density** (reported as a secondary, clearly-labelled figure
for cases where a reader wants a single ordering across differing fidelity):

```
ADJUSTED_DENSITY(S, p) = SEMANTIC_FIDELITY(S,p)² × FAITHFUL_FACTS(S,p) / TOKENS(S,p)
```

The squared fidelity factor makes losing meaning quadratically costly, so that
no realistic token saving can offset it. This figure is explicitly a heuristic
summary and may not be used as evidence in a superiority claim; only the
fidelity-gated comparison may.

---

## 6. Reporting requirements

Every density result record contains, at minimum:

```json
{
  "specimen_id": "...",
  "system": "...",
  "encoding": "<verbatim source text as measured>",
  "auxiliary_declarations": "<verbatim, included in the measure>",
  "tokenizer_version": "...",
  "semantic_fact_count": 11,
  "faithful_facts": 8.5,
  "fact_ledger": [
    {"fact_id": "F3", "credit": 1.0, "evidence": "enforced by the type checker",
     "by_default": false}
  ],
  "wrong_facts": [],
  "tokens": 14,
  "characters": 41,
  "ast_nodes": 12,
  "semantic_fidelity": 0.773,
  "tokens_per_faithful_fact": 1.65,
  "comparable_with": ["<systems at equal fidelity on this specimen>"]
}
```

The `fact_ledger` is mandatory. A density number without a per-fact ledger is not
a measurement, because it cannot be checked or disputed.

Aggregation across specimens uses the **median** of per-specimen ratios, not the
mean of pooled counts, so that one long specimen cannot dominate; the
interquartile range is reported with it. Any aggregate is restricted to specimens
where the compared systems are fidelity-comparable, and the number of specimens
so restricted is stated.
