# Grammar Candidates

Companion to `ALPHABET_STUDY.md`. That document scores the candidates; this one
specifies them, shows the same problem in all five, and gives the per-grammar
ambiguity analysis.

Grammars: `spec/grammars/{a_labelled_linear, b_symbolic_ascii, c_sexpr,
d_indent_block, e_graph_triple}.ebnf`
Encodings: `examples/candidate_syntaxes/<id>/{1..7}_*.hml`

---

## 1. The five candidates at a glance

| | A labelled-linear | B symbolic ASCII | C S-expression | D indent block | E graph triple |
|---|---|---|---|---|---|
| Structure carried by | line + keyword | line + first character | brackets | indentation | one fact per line |
| Whitespace | insignificant | insignificant | insignificant | **semantic** | separator |
| Statement kind selected by | reserved word | 1–2 char opcode | head symbol | mapping key | `is` predicate |
| Distribution roles | `location := mu` | `m:mu` | `(location mu)` | `location: mu` | `argRole location` |
| Blocks closed by | `end` | `^^` | `)` | dedent | nothing |
| Expressions | native infix | native infix | native prefix | **embedded A strings** | fully reified |
| chars / problem | 317 | **202** | 304 | 474 | 1 538 |
| mean tokens (8 tokenizers) | 670 | **649** | 682 | 1 149 | 4 530 |
| silent-meaning-change rate | **9.9%** | 13.6% | 15.6% | 27.1% | 22.0% |
| localisation precision | 96.5% | 89.7% | 51.5% | 55.4% | **100%** |
| weighted score /125 | **115** | 90 | 101 | 68 | 93 |

---

## 2. The same problem in all five

Reference problem 1: *X follows a normal distribution with mean mu and standard
deviation sigma, sigma strictly positive* — GOAL.md's worked example, the one
with six implicit commitments.

**A — labelled-linear** (8 lines, 78 tokens)

```
module NormalDistribution

param mu : Real
param sigma : PositiveReal
require sigma > 0
rv X : RandomVariable[Real]
law X ~ Normal(location := mu, scale := sigma)
```

**B — restricted-symbolic ASCII** (7 lines, 71 tokens)

```
%NormalDistribution
$mu:R
$sigma:R+
+sigma>0
'X:X[R]
X::N(m:mu,s:sigma)
```

**C — prefix / S-expression** (7 lines, 63 tokens — the cheapest)

```
(module NormalDistribution
  (param mu Real)
  (param sigma PositiveReal)
  (require (> sigma 0))
  (rv X (RandomVariable Real))
  (law X (Normal (location mu) (scale sigma))))
```

**D — indentation block** (20 lines, 132 tokens)

```yaml
module: NormalDistribution
declarations:
  - kind: param
    name: mu
    type: Real
  - kind: param
    name: sigma
    type: PositiveReal
  - kind: rv
    name: X
    type: RandomVariable[Real]
constraints:
  - "sigma > 0"
laws:
  - role: law
    target: X
    family: Normal
    args:
      location: mu
      scale: sigma
```

**E — graph triple** (59 lines, 433 tokens) — first 14 lines only:

```
M is Module
M name NormalDistribution
mu is Declaration
mu inModule M
mu order 1
mu declKind param
mu hasType _:t_mu
_:t_mu is Type
_:t_mu typeCtor Real
sigma is Declaration
sigma inModule M
sigma order 2
sigma declKind param
sigma hasType _:t_sg
...
```

All five state all six of GOAL.md §2's implicit commitments. They differ by
5.5x in tokens and 6.8x in lines to do it.

---

## 3. Ambiguity and lookahead analysis

The normative version of each analysis lives at the foot of its `.ebnf` file.
Summarised and cross-compared here.

### 3.1 Candidate A — labelled-linear

| ref | Issue | Lookahead | Genuine ambiguity? |
|---|---|---|---|
| A1 | `check dimension e` vs `check <prop>` | 1 token | **Yes, latent.** `dimension` is a *contextual* keyword. If a user binds a name `dimension`, `check dimension` is genuinely ambiguous. Resolved only by declaring `dimension` reserved after `check`. |
| A2 | `IDENT "(" ...` — ordinary call vs role-labelled argument list | **2 tokens** | No. LL(2). An LR(1) parser handles it without special casing. This is the one place A is not LL(1). |
| A3 | quantifier bodies extend maximally right: `forall x:Real . P and Q` ≡ `forall x:Real . (P and Q)` | 0 | No — a stated convention. But it is the most misread rule in the grammar and should be surfaced in every error message about quantifier scope. |
| A4 | `-` unary vs binary | 0 | No. Position-resolved. |
| A5 | statement dispatch | 1 | No. Every statement keyword is distinct and reserved. LL(1) on the first token of a line. |

**Worst case: LL(2), one latent contextual-keyword ambiguity.**

### 3.2 Candidate B — restricted-symbolic ASCII

| ref | Issue | Lookahead | Genuine ambiguity? |
|---|---|---|---|
| B1 | line-start position is load-bearing: `@x:R` is an obs declaration, `x@beta` is a matrix product | 0, but | **Structural restriction, not ambiguity.** B cannot put two statements on one line, and cannot wrap a statement onto a second line. A, C and E have no such restriction. |
| B2 | `::` / `:<` / `:>` maximal munch | 1 char (lexer) | No — no type begins with `<` or `>`. But `theta:<B(...)` reads to a human as `theta : <B(...)`. |
| B3 | type codes and family codes share a namespace: `N` = Natural *and* Normal; `B` = Bool *and* Beta; `P` = Probability and near-`Po` | 0 | No — position-resolved. But a token in the wrong position produces a *type error far from the typo*, which is why B's localisation is 89.7% against A's 96.5%. |
| B4 | role codes are a closed 1–2 char table; `m` vs `v` is mean vs variance | 0 | No. But a misremembered code is a **silent semantic change** — measured directly as `B-role-code-typo` → SILENT_MEANING_CHANGE. |
| B5 | `.p` (concept parameter) vs `p` (probability role) | 0 | No — different positions, near-identical glyphs. |
| B6 | `^` opens a concept at line start, exponentiates inside an expression; `*` declares a const at line start, multiplies inside | 0 | Same class as B1. |

**Worst case: LL(1) with a position-dependent lexer and two silent-failure
modes (B3, B4) that A does not have.**

### 3.3 Candidate C — prefix / S-expression

| ref | Issue | Lookahead | Genuine ambiguity? |
|---|---|---|---|
| C1 | bracket structure | 0 | None. Every construct is delimited. |
| C2 | `(law X (given a b) ...)` vs `(law X (Normal ...))` | **2 tokens** — must read the head of the *second* subform | No, once `given` is reserved. |
| C3 | `(check dimension e)` vs `(check <prop>)` | 1 token | Same contextual-keyword issue as A1, but **confined inside a known bracket**, so a misparse cannot leak past the closing paren. C is strictly better than A here. |
| C4 | arity is unconstrained: `(^ a)` and `(- a b c)` parse | – | **Yes, in a weak sense.** The grammar accepts programs that are meaningless. Arity becomes a semantic check, which weakens "parse determinism" as a proxy for correctness. |
| C5 | a dropped `)` is reported at EOF or at the next `(module` | – | Not ambiguity — **error non-locality**, and it is C's disqualifying property. Measured: 21.4% of bracket deletions locally detectable vs A's 80.5%; 51.5% overall localisation precision. |

**Worst case: LL(2) on one production; formally the cleanest grammar of the
five and the second worst at telling you where you went wrong.**

### 3.4 Candidate D — indentation block

| ref | Issue | Lookahead | Genuine ambiguity? |
|---|---|---|---|
| D1 | grammar given INDENT/DEDENT | 1 token | No. **All of D's risk is in the lexer, none in the parser.** |
| D2 | a dedented key migrates between blocks and the file stays well-formed YAML | – | **Predicted silent failure. NOT OBSERVED.** 560/560 dedent trials were detected; 40.9% locally. A schema-aware checker defends D well here because block key sets are closed. The prediction should be retired. |
| D3 | plain scalars swallow expression text: `body: 0.5 * m * v^2` is a string | – | **The real defect.** A typo inside an expression string is invisible to the structural parser. Measured: 100% of closing-bracket deletions in D silently changed meaning, 0% detected. |
| D4 | YAML 1.1 boolean coercion: bare `y`, `n`, `N`, `on`, `off`, `yes`, `no` | – | **Yes — a genuine cross-parser ambiguity.** The same file means different things to a YAML 1.1 parser and a YAML 1.2 parser. The corpus quotes every affected name (`name: "y"`, `name: "N"` in problem 3); the tax is permanent and cannot be designed away while D is YAML. |
| D5 | tabs forbidden in indentation | – | No — a hard error, and at least a loud one. |

**Worst case: LL(1) parser over a lexer that carries all the meaning, plus a
version-dependent scalar-typing ambiguity that is not fixable within YAML.**

### 3.5 Candidate E — graph triple

| ref | Issue | Lookahead | Genuine ambiguity? |
|---|---|---|---|
| E1 | three fields, one line | **0** | None. The grammar is regular. |
| E2 | no syntactic scope: quantifier nesting is one `quantBody` edge | – | **Not ambiguity — total absence of redundancy.** `forall x . exists y . y > x` and `exists y . forall x . y > x` differ by which node is outer. Measured: `E-quantifier-swap` flips the meaning with one line edited and is SILENT. |
| E3 | file order is not statement order; `order` triples are required | – | **Under-determination**, not ambiguity. A file that omits `order` is well-formed and incompletely specified. |
| E4 | blank-node name collisions merge two nodes into one wrong node | – | Detectable only by a vocabulary-aware checker, never by the grammar. |
| E5 | an expression with k operators costs ≥3k lines | – | Not ambiguity — the cost of full reification, and the reason E is 8.4x English. |

**Worst case: zero lookahead, zero ambiguity, zero redundancy. E cannot
misparse and cannot notice a deletion.**

### 3.6 Cross-comparison

| | max lookahead | genuine ambiguities | position-dependent lexing | silent-failure modes measured |
|---|---|---|---|---|
| A | 2 | 1 latent (A1) | no | quantifier order, wrong role choice |
| B | 1 | 0 | **yes** | + role-code typo, namespace collision |
| C | 2 | 1 latent (C3), 1 weak (C4) | no | quantifier order, wrong role choice |
| D | 1 | 1 real (D4, cross-parser) | **yes (indentation)** | + all expression-string damage |
| E | **0** | 0 | no | quantifier flip, edge deletion |

The ranking on formal grammar quality (E > C ≈ B > A ≈ D) is almost the
*inverse* of the ranking on practical error behaviour (A > B > C ≈ D, with E
split). Formal cleanliness and diagnosability are close to orthogonal here,
and the study weights diagnosability higher because GOAL.md §7 lists "error
visibility (do mistakes become *loud* rather than silent?)" as a measured
criterion and does not list grammar class at all.

---

## 4. Expressiveness against the frozen IR

Every candidate can express every node in `src/hamiltonian_lang/ast/nodes.py`.

| AST node | A | B | C | D | E | exercised by the 7 problems? |
|---|---|---|---|---|---|---|
| `ModuleDecl` | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `Declaration` (var/param/const/obs/index/rv) | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `DefineStmt` (+ params) | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `LawStmt` (+ `given`, + role) | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `DistExpr` + `Arg` (role-labelled) | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `RequireStmt` | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `ObjectiveStmt` | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `SolveStmt` | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `InferStmt` | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `CheckStmt` (dimension) | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `ProveStmt` | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `Quantifier` forall/exists | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `Quantifier` exists_unique | ✓ | ✓ | ✓ | ✓ | ✓ | **no** |
| `Comparison`, `BinOp`, `UnaryOp`, `Literal`, `Ref` | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `Call` | ✓ | ✓ | ✓ | ✓ | ✓ | yes (concept invariant) |
| `ConceptDecl` + `ConceptMember` | ✓ | ✓ | ✓ | ✓ | ✓ | yes |
| `AssumeStmt` | ✓ | ✓ | ✓ | ✓ | ✓ | **no** |
| `LogicalOp` (and/or/implies/iff) | ✓ | ✓ | ✓ | ✓ | ✓ | **no** |
| `Index` | ✓ | ✓ | ✓ | ✓ | ✓ | **no** |

**No candidate failed to express any of the seven problems.** Two honest
qualifications:

1. **D's `✓` for expressions is conditional.** D expresses expressions by
   embedding candidate-A strings. Its own grammar has no expression
   production. On its own vocabulary D cannot write `0.5 * m * v^2`; nested
   YAML was tried and rejected at nine lines for that one expression.
2. **Four AST constructs are unexercised** (`exists_unique`, `AssumeStmt`,
   `LogicalOp`, `Index`). All five grammars have productions for them; none has
   been demonstrated. The reference problem set should be extended before any
   of these is treated as validated.

---

## 5. Notes on the reference encodings

Deliberate choices worth flagging, so nobody mistakes them for accidents:

* **Problem 6 puts both quantifier orders in one file** in every candidate,
  with the true and false readings labelled. In A and C the two differ
  structurally (binder nesting). In E they differ by which node owns the other
  as `quantBody` — two triples out of 92 lines. In D they differ inside a
  quoted string, so YAML sees no structure at all.
* **Problem 3 quotes `"N"` and `"y"` in candidate D** because bare `N` and `y`
  are booleans to a YAML 1.1 parser. This is not defensive style; it is
  required for correctness, and it is a tax A, B, C and E do not pay.
* **Candidate B's problem 1 writes `'X:X[R]`** — the rv sigil, the name `X`,
  and the RandomVariable type constructor `X`, all in six characters. It is
  legal and it is exactly the legibility hazard recorded as B3.
* **Candidate E reifies expressions completely** rather than embedding strings.
  This is why E is 8.4x English tokens and also why it is the only candidate
  whose file *is* the semantic graph.
* **Comments are included in the corpus and in all measurements.** They are
  part of real files. One consequence: candidate E's `delete_closing_bracket`
  trials all landed inside comments (E has no brackets in its syntax), so that
  cell is reported as 0%/0% rather than as a meaningful result.

---

## 6. Where to look next

* Scores, Unicode analysis, and the D-003 verdict: `ALPHABET_STUDY.md`.
* Structured candidate descriptions: `experiments/alphabet/candidates.yaml`.
* Raw numbers: `experiments/alphabet/results/`.
* Reproduce: `experiments/alphabet/tokenisation_benchmark.py`.
