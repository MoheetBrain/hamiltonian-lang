# Alphabet Study

Owner: Alphabet, Tokenisation and Grammar Architect.
Status: complete for Wave 1. All numbers measured, none estimated.

This document tests the v0 freeze's alphabet and grammar choices against four
alternatives. It is allowed to contradict the freeze and, in three specific
places, it does.

---

## 0. What was measured, and how to reproduce it

**Exact command run:**

```
HF_HOME=<scratchpad>/hf <scratchpad>/venv/bin/python \
    experiments/alphabet/tokenisation_benchmark.py
```

(Python 3.14.6 in a private venv at
`/private/tmp/claude-501/-Users-moheet-hamiltonian-lang/3c82aceb-0ab1-4091-8c89-be3d7f632584/scratchpad/venv`;
the project and system Pythons were not modified.)

Full console output is preserved verbatim at
`experiments/alphabet/results/RUN_LOG.txt`. Machine-readable results:

| File | Contents |
|---|---|
| `results/corpus_metrics.csv` | chars, lines, tokens, fragmentation per file per tokenizer |
| `results/operator_cost.csv` | per-operator token cost, 4 measurement modes |
| `results/unicode_fragmentation.csv` | token cost + NFC/NFKC behaviour of 15 maths symbols |
| `results/unicode_confusables.csv` | 17 confusable pairs, normalisation and token-id collisions |
| `results/edit_robustness.csv` | 8 640 randomised corruption trials |
| `results/adversarial_cases.csv` | 23 hand-authored corruptions with declared expectations |
| `results/d003_micro_cost.csv` | D-003 cost on 16 isolated distribution statements |
| `results/d003_file_cost.csv` | D-003 cost on whole files |
| `results/baseline_wellformedness.csv` | proof that every pristine corpus file passes its own checker |
| `results/summary.json` | everything aggregated |
| `results/tokenizer_availability.json` | which tokenizers loaded, and the exact error for those that did not |

### Tokenizer availability — what was and was not measured

**Available and used (8 real tokenizers):**

| Family | Encodings |
|---|---|
| `tiktoken` 0.13.0 | `cl100k_base`, `o200k_base`, `p50k_base`, `r50k_base` |
| `transformers` 5.14.1 | `gpt2`, `NousResearch/Llama-2-7b-hf`, `EleutherAI/gpt-neox-20b`, `bigcode/starcoder2-3b` |

**NOT available — no numbers reported for it:**

* `meta-llama/Meta-Llama-3-8B` — gated repository, HTTP 401 without an
  `HF_TOKEN`. The exact exception is recorded in
  `results/tokenizer_availability.json`. No Llama-3 figure appears anywhere in
  this study, and none was estimated in its place.

**Fallback:** `regex_approx_APPROXIMATE` is a documented, dependency-free
tokenizer (whitespace runs / alphabetic runs split every 6 chars / digit runs /
every other character alone). It is reported in every CSV, always suffixed
`_APPROXIMATE`, and is **excluded from every aggregate and every claim in this
document**. It exists so the benchmark still returns an ordering on a machine
with no network. It must never be quoted as a model tokenizer.

---

## 1. Corpus

Five candidate syntaxes (`spec/grammars/{a..e}_*.ebnf`), seven reference
problems each, plus English and LaTeX baselines: 49 files in
`examples/candidate_syntaxes/`.

**Every candidate expressed all seven problems.** No candidate failed on
expressiveness. Two qualifications are recorded rather than hidden:

1. **Candidate D is not self-contained.** Its structural layer is YAML; its
   *expressions* are embedded candidate-A strings (`body: "0.5 * m * v^2"`).
   Encoding expressions as nested YAML was attempted and rejected as unusable
   (`0.5*m*v^2` becomes nine lines). D therefore has no grammar for its own
   expressions, and this turns out to be its fatal defect (§5).
2. **The seven problems do not exercise the whole IR.** `ast.nodes.Index`,
   `ast.nodes.LogicalOp`, `ast.nodes.AssumeStmt` and
   `Quantifier(kind="exists_unique")` appear in all five grammars but in none
   of the 35 encodings. That is a gap in the problem set, not in the grammars.

**Verified, not asserted:** all 7 candidate-D files parse with PyYAML
`safe_load`, and all 35 candidate files pass their own well-formedness checker
with **0 errors** (`results/baseline_wellformedness.csv`). This matters: the
corruption experiment measures *new* errors relative to that clean baseline,
so a leaky checker would have inflated the detection rates.

---

## 2. Size and token efficiency

Totals over all seven problems.

| Arm | chars | lines | cl100k | o200k | p50k | r50k | gpt2 | Llama-2 | neox-20b | starcoder2 | **mean** | **vs English** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A** labelled-linear | 2 222 | 68 | 620 | 621 | 676 | 676 | 676 | 743 | 657 | 691 | **670.0** | **1.247x** |
| **B** symbolic ASCII | 1 411 | 59 | 566 | 559 | 687 | 692 | 692 | 684 | 658 | 655 | **649.1** | **1.209x** |
| **C** S-expression | 2 131 | 63 | 619 | 621 | 697 | 717 | 717 | 763 | 669 | 656 | **682.4** | **1.271x** |
| **D** indent block | 3 321 | 163 | 1 019 | 1 020 | 1 131 | 1 357 | 1 357 | 1 192 | 1 118 | 998 | **1 149.0** | **2.139x** |
| **E** graph triple | 10 765 | 587 | 4 092 | 4 058 | 4 838 | 4 840 | 4 840 | 4 926 | 4 402 | 4 241 | **4 529.6** | **8.433x** |
| ENG prose | 2 347 | 33 | 521 | 520 | 542 | 542 | 542 | 561 | 526 | 543 | 537.1 | 1.000x |
| TEX LaTeX | 1 684 | 54 | 697 | 695 | 772 | 772 | 772 | 687 | 656 | 678 | 716.1 | 1.333x |

### The single most important number in this study

**Candidate B uses 36.5% fewer characters than A and saves 3.1% of tokens.**

1 411 chars vs 2 222; 649.1 tokens vs 670.0. And the "saving" is not even a
saving on most tokenizers: **it is a 4–4 split.** B wins on cl100k (566 vs
620), o200k (559 vs 621), Llama-2 (684 vs 743) and starcoder2 (655 vs 691);
**B loses on p50k (687 vs 676), r50k (692 vs 676), gpt2 (692 vs 676) and
gpt-neox-20b (658 vs 657).** The 3.1% mean advantage is carried entirely by
the two newest OpenAI vocabularies and evaporates on everything else.

Character-level terseness does not buy token efficiency, because BPE
vocabularies are built on natural-language and code corpora in which
`location` is one token and `,s:` is three. Any future proposal to compress
Hamiltonian Lang by shortening its surface forms must clear this bar with
measurements, not intuition.

### Fragmentation (tokens per character, cl100k_base)

| Arm | ENG | A | C | D | E | B | TEX |
|---|---|---|---|---|---|---|---|
| tokens/char | 0.222 | **0.279** | 0.291 | 0.307 | 0.380 | 0.401 | 0.414 |

Terse punctuation-dense syntaxes (B, LaTeX) sit at the *bad* end. The
word-keyword syntaxes (A, C) sit near English. This is the same finding from
the other direction.

### Per-problem token cost (mean of 8 real tokenizers)

| Problem | A | B | C | D | E | ENG | TEX |
|---|---|---|---|---|---|---|---|
| 1 normal_distribution | 78 | 71 | **63** | 132 | 433 | 32 | 71 |
| 2 bayesian_coin | 95 | 85 | 88 | 186 | 549 | 76 | 99 |
| 3 linear_regression | **104** | 114 | 110 | 276 | 747 | 100 | 130 |
| 4 kinetic_energy | **85** | 92 | 110 | 133 | 548 | 64 | 95 |
| 5 constrained_optimisation | 89 | **65** | 84 | 138 | 671 | 55 | 79 |
| 6 quantifier_scope | **123** | 127 | 130 | 150 | 824 | 99 | 102 |
| 7 concept_definition | 97 | **95** | 97 | 136 | 758 | 111 | 140 |

Note problem 7: A, B and C all beat *both* baselines. Concept definition is
where explicit structure starts paying for itself, because prose and LaTeX
need paragraphs of hedging to say what `invariant scale > 0` says.

---

## 3. Reserved-token cost — is the frozen operator set expensive?

Marginal token cost of writing the operator, measured as
`len(enc("a <op> b")) − len(enc("a b"))` (space-delimited, the form a canonical
printer emits) and `len(enc("a<op>b")) − len(enc("ab"))` (glued).

| Operator | Meaning | spaced (all 8 tokenizers) | glued, worst tokenizer |
|---|---|---|---|
| `:` | type ascription | **1** | 1–2 |
| `:=` | definition | **1** | **3** (gpt2, p50k, r50k) |
| `~` | is distributed as | **1** | 2 |
| `\|` | conditioning | **1** | 2 |
| `->` | function mapping | **1** | 2 |
| `=>` | implication | **1** | 2 |
| `<=>` | equivalence | **2** (1 in cl100k only) | 3 |
| `@` | matrix product | **1** | 2 |
| `^` | exponentiation | **1** | 2 |
| `.` | quantifier body | **1** | 1–2 |
| `::` | (candidate B only) | 1 | 2 |
| `:<` `:>` | (candidate B only) | **2** | 3 |

**Verdict on the frozen reserved set: it is essentially free.** Every operator
in the freeze's §1 table costs exactly one token in all eight tokenizers when
space-delimited. `<=>` is the only exception at two tokens, and it is the
rarest operator in the language.

Two concrete consequences, both new relative to the freeze:

* **The canonical printer must space-delimit operators.** `a:=b` costs three
  tokens under gpt2/p50k/r50k where `a := b` costs one. This is a printer rule
  the freeze does not currently state, and it is worth ~2 tokens per
  definition.
* **Candidate B's digraphs are a false economy.** `:<` and `:>` cost 2 tokens
  under gpt2 and Llama-2, while candidate A's whole words ` prior` and
  ` likelihood` cost **1 token each** in cl100k, o200k, gpt2 and Llama-2. The
  abbreviation is more expensive than the word it abbreviates.

---

## 4. Unicode analysis

Measured on 15 mathematical symbols and 17 confusable pairs
(`results/unicode_*.csv`).

### 4.1 Fragmentation — Unicode operators cost 1–4x their ASCII equivalents

Standalone token cost:

| Symbol | cp | cl100k | o200k | p50k | r50k | gpt2 | Llama-2 | neox-20b | starcoder2 | ASCII equivalent | ASCII cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `→` | U+2192 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | `->` | 1 |
| `⇒` | U+21D2 | **3** | 1 | **3** | **3** | **3** | 2 | **3** | 2 | `=>` | **1** |
| `⇔` | U+21D4 | **3** | 2 | **3** | **3** | **3** | 2 | **3** | **3** | `<=>` | 2 |
| `∀` | U+2200 | 2 | 1 | 2 | 2 | 2 | 2 | 2 | 2 | `forall` | 1 |
| `∃` | U+2203 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | `exists` | 1 |
| `∈` | U+2208 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | `in` | 1 |
| `∑` | U+2211 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | `sum` | 1 |
| `∏` | U+220F | 2 | 2 | 2 | 2 | 2 | **4** | 2 | 2 | `prod` | 1 |
| `∫` | U+222B | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | `integral` | 1–2 |
| `∂` | U+2202 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | `d` | 1 |
| `≈` | U+2248 | 2 | 1 | 2 | 2 | 2 | 2 | 2 | 2 | `~=` | 1–2 |
| `λ` | U+03BB | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | `lambda` | 1 |
| `μ` | U+03BC | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | `mu` | 1 |
| `σ` | U+03C3 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | `sigma` | 1 |
| `θ` | U+03B8 | 1 | 1 | 2 | 2 | 2 | 2 | 1 | 1 | `theta` | 1 |

Worst offenders: **`⇒` and `⇔` cost 3 tokens in five of eight tokenizers**, and
`∏` costs 4 under Llama-2. Greek letters are cheap (1 token) except under
Llama-2 where they are uniformly 2. Mean cost per symbol ranges 1.47 (o200k)
to 2.07 (Llama-2) tokens; ASCII spellings average 1.

**Nothing is gained in tokens by adopting Unicode operators, and up to 3x is
lost on the logical connectives.**

### 4.2 Confusables — normalisation does not solve this

17 pairs tested. Results:

**Collapsed by plain NFC (2 pairs)** — these are canonical singletons, so any
NFC-normalising editor silently rewrites them:

* `Ω` U+03A9 GREEK CAPITAL OMEGA ≡ `Ω` U+2126 OHM SIGN
* `Å` U+00C5 LATIN A WITH RING ≡ `Å` U+212B ANGSTROM SIGN

**Collapsed only by NFKC (2 further pairs)** — the classic ones:

* `μ` U+03BC GREEK SMALL MU ≡ `µ` U+00B5 MICRO SIGN
* `θ` U+03B8 GREEK SMALL THETA ≡ `ϑ` U+03D1 GREEK THETA SYMBOL

**Survive BOTH NFC and NFKC as distinct codepoints (13 pairs)** — normalisation
is no defence at all against these:

| Pair | Why it matters |
|---|---|
| `Σ` U+03A3 / `∑` U+2211 | capital sigma vs summation operator |
| `Π` U+03A0 / `∏` U+220F | capital pi vs product operator |
| `σ` U+03C3 / `ς` U+03C2 | medial vs final sigma — same letter to a reader |
| `ϵ` U+03F5 / `∈` U+2208 | lunate epsilon vs element-of |
| `−` U+2212 / `-` U+002D | minus sign vs hyphen-minus |
| `×` U+00D7 / `x` U+0078 | multiplication sign vs the variable x |
| `∅` U+2205 / `Ø` U+00D8 | empty set vs Danish O |
| `Α` U+0391 / `A` U+0041 | Greek alpha vs Latin A |
| `А` U+0410 / `A` U+0041 | Cyrillic A vs Latin A |
| `∂` U+2202 / `д` U+0434 | partial vs Cyrillic de |
| `′` U+2032 / `'` U+0027 | prime vs apostrophe |
| `⁄` U+2044 / `/` U+002F | fraction slash vs solidus |
| `ᴇ` U+1D07 / `e` U+0065 | small-capital E vs e |

So: **NFC fixes 2 of 17, NFKC fixes 4 of 17, and 13 of 17 survive both.** The
mitigation strategy fails on 76% of the cases tested.

### 4.3 The tokenizer makes it worse, not better

`gpt-neox-20b` assigns **identical token ids** to `Ω`/`Ω` (U+03A9/U+2126) and
`Å`/`Å` (U+00C5/U+212B). Under that tokenizer, a Unicode-canonical form would
not be injective: two byte-distinct programs would be indistinguishable to the
model reading them, while remaining distinct to the hash, the diff, and the
file system. That is precisely the class of bug that is impossible to
reproduce.

### 4.4 Recommendation — CONFIRMS the freeze

**Unicode should be a display layer only. Canonical serialisation stays
7-bit ASCII.** The freeze's §1 rationale ("eliminates normalisation and
confusable-identifier risk entirely rather than mitigating it") is now backed
by measurement: mitigation via normalisation demonstrably fails on 13 of 17
confusable pairs, and there is no compensating token saving — Unicode operators
cost up to 3x their ASCII spellings.

Concrete rule for the renderer: a Unicode *display* projection is free to emit
`∀ ∃ ⇒ μ σ`, but it must be one-directional. There must be no Unicode *reader*,
because a reader is what re-admits the 13 unresolvable pairs.

---

## 5. Edit robustness

8 640 randomised corruption trials (80 per file per corruption type, seeded)
plus 23 hand-authored adversarial cases. Each trial is classified:

* **LOCAL** — the checker reports an error *on the corrupted line*.
* **NONLOCAL** — an error is reported, but somewhere else.
* **SILENT_MEANING_CHANGE** — no error, and the semantic digest changed. This
  is the dangerous outcome.
* **SILENT_BENIGN** — no error and no meaning change (e.g. whitespace damage
  in a whitespace-insensitive syntax; damage inside a comment).

The digest normalises role-labelled argument *order*, so reordering labelled
arguments is correctly scored as no change. Without that normalisation the
benchmark would have credited D-003 with catching an error it did not catch.

### 5.1 Pooled results

| Arm | trials | LOCAL | NONLOCAL | **SILENT-MEANING-CHANGE** | SILENT-BENIGN | localisation precision |
|---|---|---|---|---|---|---|
| **A** | 1 600 | 55.5% | 2.0% | **9.88%** | 32.6% | **96.5%** |
| **B** | 1 600 | 47.3% | 5.4% | **13.56%** | 33.7% | 89.7% |
| **C** | 2 240 | 24.8% | 23.4% | **15.58%** | 36.3% | 51.5% |
| **E** | 1 200 | 66.8% | 0.0% | **22.00%** | 11.2% | **100.0%** |
| **D** | 2 000 | 34.9% | 28.0% | **27.10%** | 10.1% | 55.4% |

(localisation precision = LOCAL / (LOCAL + NONLOCAL): given that an error *was*
found, how often did the checker point at the right line.)

### 5.2 By corruption type — LOCAL% / SILENT-MEANING-CHANGE%

| Arm | delete char | swap adjacent | drop leading whitespace | delete closing bracket |
|---|---|---|---|---|
| **A** | 45.7 / 15.5 | 43.6 / 14.1 | 0.0 / **0.0** (no-op) | **80.5** / 0.0 |
| **B** | 26.1 / 25.0 | 32.7 / 18.2 | n/a (no indentation) | **90.8** / 0.0 |
| **C** | 28.0 / 34.1 | 43.4 / 30.4 | 0.0 / **0.0** (no-op) | 21.4 / 0.0 |
| **D** | 42.0 / 21.8 | 39.3 / 20.9 | **40.9** / 0.0 | **0.0 / 100.0** |
| **E** | 68.2 / 26.6 | 75.9 / 18.4 | n/a | 0.0 / 0.0 (comments only) |

### 5.3 The whitespace hypothesis was NOT confirmed as stated

The brief predicted candidate D would do badly on whitespace corruption.
**It did not.** Every one of 560 dedent trials was detected (40.9% on the exact
line, 59.1% elsewhere) and **none** silently changed meaning. The hand-authored
canonical hazard — dedenting `scale: sigma` out of the `args:` mapping —
was caught locally with the message `L21: unknown law key 'scale'`.

The reason is that a schema-aware checker gives D a strong defence: a key that
migrates between blocks lands in a block whose key set is closed. The
prediction should be retired.

**D fails for a worse reason instead.** 100% of closing-bracket deletions in D
silently changed meaning and 0% were detected. Every bracket in a D file lives
inside a quoted type or expression string (`type: Matrix[Real, N, P]`), and
YAML sees a string. The adversarial case `D-drop-type-bracket` confirms it:
`Matrix[Real, N, P` parses cleanly and means something different. D's
structural layer is blind to D's own expression sublanguage, which is the
direct consequence of D not being self-contained (§1).

### 5.4 A's characteristic strength, C's characteristic weakness

A confines meaning to a line, so it confines damage to a line: 96.5%
localisation precision, and 80.5% of bracket deletions caught *on the line*.

C cannot do this. A dropped paren is discovered only when the bracket
accounting fails, which is at EOF. Measured: `C-drop-inner-paren` edits line 11
of a 13-line file and the error surfaces at line 12 — and that distance grows
linearly with file length. Only 21.4% of C's bracket deletions are locally
detectable, against A's 80.5%. This is the single measured reason to prefer A
over C.

### 5.5 E's characteristic risk

E has perfect localisation (100%) but the second-worst silent rate (22%),
because E has no syntactic scope at all. Three adversarial cases:

* `E-quantifier-swap` — changing `quantKind forall` to `quantKind exists` on
  one line reverses the meaning of the whole proposition. Well-formed. Silent.
* `E-drop-edge` — deleting the single line `_:d distArg _:a2` removes the scale
  parameter from a Normal distribution. Well-formed. Silent.
* `E-dangling-ref` — retargeting an edge at an undefined node *is* caught, on
  the exact line. E's defence is referential integrity, and only that.

E is safe against typos and unsafe against deletions.

---

## 6. Verdict on D-003 (mandatory role-labelled distribution arguments)

**The frozen claim:** positional distribution arguments are a parse error;
`Normal(location := mu, scale := sigma)` not `Normal(mu, sigma)`; "cost: more
tokens. That cost is measured, not assumed."

### 6.1 The cost, measured

Whole-file overhead, per tokenizer, over all seven problems
(`results/d003_file_cost.csv`):

| Arm | cl100k | o200k | p50k | r50k | gpt2 | Llama-2 | neox-20b | starcoder2 | mean |
|---|---|---|---|---|---|---|---|---|---|
| **A** | 6.21% | 6.19% | 5.52% | 5.52% | 5.52% | 5.81% | 5.87% | 6.50% | **5.88%** |
| B | 3.97% | 4.03% | 5.41% | 5.39% | 5.39% | 5.51% | 5.67% | 5.73% | 5.19% |
| C | 8.53% | 8.47% | 7.87% | 7.56% | 7.56% | 6.90% | 8.05% | 7.69% | 7.79% |
| D | 4.17% | 4.17% | 4.29% | 8.47% | 8.47% | 4.44% | 4.60% | 4.00% | 5.52% |
| E | −0.45% | −0.45% | 0.00% | 0.00% | 0.00% | −0.33% | −0.38% | 0.00% | **−0.19%** |

Per-statement cost (cl100k, `results/d003_micro_cost.csv`):

| Statement | labelled | positional | delta |
|---|---|---|---|
| `law X ~ Normal(location := mu, scale := sigma)` | 12 | 8 | **+4** |
| `prior theta ~ Beta(alpha := 1, beta := 1)` | 14 | 10 | **+4** |
| `likelihood successes \| theta ~ Binomial(trials := trials, prob := theta)` | 16 | 12 | **+4** |
| `likelihood y \| x, beta, sigma ~ NormalVector(location := x @ beta, scale := sigma)` | 21 | 17 | **+4** |

**The cost of D-003 in the frozen syntax is +4 tokens per law statement, or
5.88% of a whole program.** In absolute terms, across the entire seven-problem
corpus, D-003 costs **20.8 tokens per tokenizer on average** (range 20–23 over
the eight tokenizers; 166 summed across all eight, which is the raw figure in
`summary.json`). Candidate C pays 25.9, candidate D pays 31.0, and candidate E
pays −4.8 — role labels are free in a triple store.

### 6.2 The benefit, measured

Three adversarial cases isolate exactly what the labels buy:

| Case | Edit | Result |
|---|---|---|
| `A-transpose-labelled` | `Normal(scale := sigma, location := mu)` | **SILENT_BENIGN** — verified no meaning change |
| `A-transpose-positional` | `Normal(sigma, mu)` | **LOCAL** — `L8: positional distribution argument 'mu' (D-003 requires a role label)` |
| `A-positional-correct-order` | `Normal(mu, sigma)` | **LOCAL** — rejected even when correct |

So D-003 buys precisely one thing, and buys it completely: **argument order
becomes semantically inert.** A transposition that would silently invert
location and scale in any positional notation is, in the frozen syntax, either
a no-op (if labelled) or a parse error at the exact line (if positional). There
is no way to express the transposition bug.

### 6.3 What D-003 does NOT buy — the residual hole

`A-sd-vs-variance`: rewriting `scale := sigma` as `variance := sigma`
is well-formed, passes the checker, and **silently changes meaning**. Both are
legal roles. The `Normal(mu, sigma)` vs `Normal(mu, sigma^2)` confusion that
the freeze says "cannot be expressed" **can still be expressed** — it just has
to be spelled out rather than smuggled in positionally.

Candidate B makes this far worse: `B-role-code-typo` shows that changing `s:`
to `v:` is a one-character edit with the same silent outcome. Abbreviating
roles reintroduces the exact failure D-003 exists to prevent.

### 6.4 Verdict

**D-003 is correct and should be kept, at a measured price of 5.88% of tokens
and +4 tokens per law statement.** 5.88% is well inside the noise of choosing
one tokenizer over another (candidate A ranges 620–743 tokens over the eight
tokenizers tested, a 20% spread — three times the cost of D-003). Paying 5.88%
to make an entire class of bug
inexpressible is a good trade by any reading of GOAL.md §2, which counts
"eliminated inference" as the unit of value.

**But the freeze overstates the benefit and should be amended.** §2 currently
says the `Normal(mu, sigma)` vs `Normal(mu, sigma^2)` ambiguity "cannot be
expressed". Measured, that is false: order-confusion cannot be expressed;
*role*-confusion still can. Two recommended amendments:

* **R1.** Restate D-003's claim precisely: role labels make argument **order**
  semantically inert; they do not make role **choice** safe.
* **R2.** Close the residual hole with a **closed per-family role signature**:
  each distribution family declares its exact required role set, with no
  defaults and no optional roles. `Normal` accepts `{location, scale}` and
  nothing else; a variance-parameterised normal must be a *different family*
  (`NormalVariance`), not a different argument. Then `variance := sigma` on a
  `Normal` is a parse error on the right line instead of a silent semantic
  change. This costs zero additional tokens.

---

## 7. Scoring matrix

Thirteen criteria. Each score 1–5 with a stated rubric; measured criteria cite
the measurement, judged criteria state the anchor.

### 7.1 Rubrics

| # | Criterion | Basis | 5 | 4 | 3 | 2 | 1 |
|---|---|---|---|---|---|---|---|
| 1 | Parse determinism | max lookahead + count of contextual keywords / position-dependent lexing | LL(1) or regular, 0 issues | LL(2) or 1 contextual keyword | 2+ contextual keywords or position-dependent lexing | structure carried by the lexer | genuine ambiguity |
| 2 | Semantic explicitness | how many of the 6 GOAL §2 commitments are *stated*, and whether role names are words | 6/6, full words | 6/6, expressions opaque | 6/6, roles abbreviated to codes | ≥4/6 | ≤3/6 |
| 3 | Token efficiency | **measured**: mean tokens / English | ≤1.10x | ≤1.30x | ≤1.60x | ≤2.50x | >2.50x |
| 4 | Tokenizer fragmentation | **measured**: cl100k tokens/char | ≤0.24 | ≤0.30 | ≤0.35 | ≤0.42 | >0.42 |
| 5 | Visual distinctness | count of distinct *meanings* separated by ≤1 character in the surface form | 0 such pairs | 1–2 | 3–5 | 6–9 | ≥10 |
| 6 | Typing effort | **measured**: chars per problem | <200 | <320 | <420 | <800 | ≥800 |
| 7 | Error localisation | **measured**: LOCAL/(LOCAL+NONLOCAL) | ≥95% | ≥85% | ≥70% | ≥50% | <50% |
| 8 | Edit robustness | **measured**: silent-meaning-change rate | ≤10% | ≤15% | ≤20% | ≤25% | >25% |
| 9 | Canonicalisation | count of surface degrees of freedom that carry no meaning (whitespace, arg order, alternate spellings, node naming) | 0–1 | 2 | 3 | 4 | ≥5 |
| 10 | Unicode normalisation risk | confusable pairs admissible by the alphabet | 0 (ASCII-only) | — | — | — | 13+ survive NFKC |
| 11 | Cross-platform compatibility | ASCII + tab/CRLF/parser-version hazards | none | 1 minor | 2 | parser-version divergence | corruption on transport |
| 12 | Human readability | can a numerate reader restate the program after reading the reserved-token table once | yes, immediately | yes, with effort | needs the grammar open | needs a code table | needs a code table + tooling |
| 13 | Graph convertibility | work to reach the Layer-2 graph | file IS the graph | tree→graph, mechanical | tree→graph + re-parse a sublanguage | + reconstruct scope | + reconstruct semantics |

Criterion 10 does not discriminate among A–E: all five are ASCII-only by
construction and all score 5. A hypothetical **U** (Unicode-canonical) column
is included to show what the criterion is actually measuring.

### 7.2 The matrix

| # | Criterion | **A** | **B** | **C** | **D** | **E** | *(U)* |
|---|---|---|---|---|---|---|---|
| 1 | Parse determinism | 4 | 3 | **5** | 3 | **5** | – |
| 2 | Semantic explicitness | **5** | 3 | **5** | 4 | **5** | – |
| 3 | Token efficiency | 4 | 4 | 4 | 2 | 1 | – |
| 4 | Tokenizer fragmentation | **4** | 2 | **4** | 3 | 2 | – |
| 5 | Visual distinctness | 4 | 1 | **5** | 3 | 2 | – |
| 6 | Typing effort | 4 | **5** | 4 | 2 | 1 | – |
| 7 | Error localisation | **5** | 4 | 2 | 2 | **5** | – |
| 8 | Edit robustness | **5** | 4 | 3 | 1 | 2 | – |
| 9 | Canonicalisation | **5** | 4 | 4 | 2 | 4 | – |
| 10 | Unicode normalisation risk | **5** | **5** | **5** | **5** | **5** | 1 |
| 11 | Cross-platform compatibility | **5** | **5** | **5** | 2 | **5** | 2 |
| 12 | Human readability | **5** | 1 | 4 | 4 | 2 | – |
| 13 | Graph convertibility | 4 | 4 | 4 | 3 | **5** | – |
| | **unweighted total /65** | **59** | 45 | 54 | 36 | 44 | |

### 7.3 Weighted by GOAL.md priorities

GOAL.md optimises for machine cognition, so explicitness, determinism and error
visibility outrank typing effort and human readability. Weights (declared
before scoring, not tuned after):

parse determinism ×3 · semantic explicitness ×3 · token efficiency ×2 ·
fragmentation ×1 · visual distinctness ×1 · typing effort ×1 ·
error localisation ×3 · edit robustness ×3 · canonicalisation ×2 ·
Unicode risk ×2 · cross-platform ×1 · human readability ×1 ·
graph convertibility ×2 — total weight 25, maximum score 125.

| Arm | weighted score | % of max |
|---|---|---|
| **A labelled-linear** | **115** | **92%** |
| C prefix S-expression | 101 | 81% |
| E graph triple | 93 | 74% |
| B symbolic ASCII | 90 | 72% |
| D indentation block | 68 | 54% |

A leads on both the unweighted and the weighted scoring, and leads on the two
criteria the weighting cares most about (error localisation, edit robustness).

---

## 8. Recommendation

### 8.1 The frozen choice survives — CONFIRMED

**Keep candidate A (HML-L1) as the canonical Layer-1 syntax. Keep ASCII-only
canonical serialisation. Keep D-003.**

This is not a rubber stamp; it is the outcome of four specific attacks that
failed:

* *Attack: terse symbolic ASCII is more token-efficient.* **Refuted.** 36.5%
  fewer characters buys a 3.1% mean token saving that is actually a 4–4 split
  across tokenizers, at the price of 2x worse fragmentation, 37% more silent
  meaning changes, and a role-code table in which `s` and `v` are one keystroke
  apart.
* *Attack: S-expressions are more deterministic and should be canonical.*
  **Partly true, decisively outweighed.** C wins parse determinism 5–4 and
  visual distinctness 5–4, and loses error localisation 2–5 (51.5% vs 96.5%)
  and edit robustness 3–5. For a language whose value proposition is that
  errors become loud, 51.5% localisation is disqualifying.
* *Attack: Unicode is worth adopting for compression or readability.*
  **Refuted.** Up to 3x token cost on connectives, 13 of 17 confusable pairs
  survive NFKC, and one tokenizer assigns identical ids to distinct codepoints.
* *Attack: D-003 is expensive explicitness theatre.* **Refuted on cost,
  partly upheld on claim.** 5.88% of tokens is a cheap price; but the freeze's
  stated benefit is overstated (§6.3).

### 8.2 Where the evidence contradicts the freeze — three amendments

**R1 — Correct the D-003 claim in V0_DESIGN_FREEZE.md §2.** The text says the
`Normal(mu, sigma)` vs `Normal(mu, sigma^2)` ambiguity "cannot be expressed".
Measured: argument *order* confusion cannot be expressed; *role* confusion can
(`A-sd-vs-variance` → SILENT_MEANING_CHANGE). The claim should be narrowed to
what is true.

**R2 — Add closed per-family role signatures.** Zero token cost, converts the
residual silent failure in R1 into a local parse error. `Normal` takes exactly
`{location, scale}`; a variance parameterisation is a different family.

**R3 — Add a canonical-printer rule: operators are space-delimited.**
`a:=b` costs 3 tokens under gpt2/p50k/r50k where `a := b` costs 1. The freeze
specifies a canonical *JSON* form (§7) but says nothing about the canonical
Layer-1 printer, and the difference is measurable.

### 8.3 Two defects found in the frozen specification itself

**Defect 1 — the statement inventory omits `rv`.** V0_DESIGN_FREEZE.md §3
lists `var|param|const|obs|index` as the declaration kinds, but
`src/hamiltonian_lang/ast/nodes.py` defines `DeclKind.RANDOM = "rv"`. There is
an AST declaration kind with no surface syntax in the freeze. Candidate A's
encodings in this study use `rv X : RandomVariable[Real]`, and the grammar in
`spec/grammars/a_labelled_linear.ebnf` includes it. **This needs a ruling from
the Lead Architect**: either §3 gains `rv`, or `DeclKind.RANDOM` is removed.

**Defect 2 — `extends` separator is unspecified.** §3 writes
`concept <Name> [extends <Name>...]` without saying whether the list is
comma- or space-separated. `spec/grammars/a_labelled_linear.ebnf` assumes
commas. Trivial, but it is exactly the kind of gap that produces two
incompatible parsers.

### 8.4 Dispositions for the non-canonical candidates

* **E (graph triple) — adopt as a projection, never as an authoring syntax.**
  100% error localisation and zero conversion cost to the Layer-2 graph make it
  the natural serialisation for hypothesis H7 (graph retrieval). 8.4x English
  token cost makes it unusable in a context window. Recommend: E becomes the
  graph export format, generated only, never hand-written, never parsed back
  as a source of truth.
* **C (S-expression) — keep as the fallback canonical.** If line-orientation
  ever has to be abandoned (e.g. for machine-to-machine transport where
  precedence rules are a liability), C is the right successor and scores 81%.
  Its EBNF in `spec/grammars/c_sexpr.ebnf` is maintained for that reason.
* **B (symbolic ASCII) — reject and do not revisit without new measurements.**
  Recorded here so the "make it terser" proposal does not recur ungrounded.
* **D (indentation block) — reject.** Worst silent-meaning-change rate (27.1%),
  100% silent on bracket damage, 2.14x English tokens, and a YAML 1.1/1.2
  portability defect (bare `N` and `y` are booleans) that no amount of
  discipline removes.

### 8.5 What this study does not establish

It measures the *representation*, not *reasoning accuracy*. Nothing here says
an AI system reasons better in candidate A. That is the central experiment in
GOAL.md §8 and it has not been run. In particular:

* The 5.88% token cost of D-003 is measured; its effect on reasoning accuracy
  is **not** measured and could be negative, zero, or large.
* Error localisation is measured against a checker written by the same author
  as the grammars. A checker written by an adversary might localise worse.
* `Index`, `LogicalOp`, `AssumeStmt` and `exists_unique` are unexercised by
  the reference problems, so no candidate has been stressed on them.
* Llama-3 was unavailable; the tokenizer sample is 8, not 9.
