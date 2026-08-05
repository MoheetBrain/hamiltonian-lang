# Hypothesis register

**The purpose of this file is to make it possible, a year from now, to say exactly what
went right and what went wrong.**

Four experimental identifiers are maintained, permanently and separately. They can come
apart, and conflating them is the single most likely way to destroy the value of every
measurement taken so far.

| id | what it asks | status |
|----|--------------|--------|
| **ACQ0** | Can the model reliably *express* frozen semantic objects in a candidate syntax? | **BLOCKED** |
| **H1** | Does the representation as **input** improve the answer? | **UNTESTED** |
| **H2** | Does the representation as **reasoning workspace** improve the answer? | **UNTESTED** |
| **H3** | Does **verifier-guided repair** improve the verified answer? | **UNTESTED** |

## The eight rules

1. **ACQ0 is a prerequisite experiment, not evidence for H1, H2 or H3.** Passing it means
   the model can write the language. It says nothing about whether the language helps.
2. **Compiler-assisted syntax repair during ACQ0 is `ACQ0_REPAIR`, not H3.** Fixing a
   malformed encoding is not the same act as fixing a wrong argument. They differ in what
   is being repaired and in what would count as success.
3. **H3 requires a mathematical reasoning endpoint** and tests feedback versus no feedback
   with the reasoning representation held constant.
4. **No aggregate "Hamiltonian score" may combine H1, H2 and H3.** A compensatory scalar
   would let a strong H3 conceal a null H1, which is precisely the error to avoid.
5. **Every episode, result row, evidence package and report carries exactly one
   `hypothesis_id`.**
6. **A controller gate may consume evidence only from the hypothesis or prerequisite its
   gate explicitly names.**
7. **Null, positive and negative results are preserved separately.** A null result is
   evidence; an overwritten null result is nothing.
8. **No earlier conclusion is rewritten silently.** Corrections are appended and dated.

---

## ACQ0 — syntax acquisition and semantic preservation

| field | value |
|---|---|
| **causal question** | Can `gemma4:31b`, given a frozen curriculum, express frozen canonical semantic objects through a candidate surface such that they parse and recover the same canonical object? |
| **treatment** | one of four candidate syntaxes: A v0 labelled-linear · B simplified v1 labelled-linear · C prefix/S-expression · D constrained JSON/graph |
| **comparator** | the other candidates; matched structured English for token cost only |
| **fixed variables** | model digest · server settings · canonical task content · demonstration count · temperature 0 · one repair maximum · scoring code |
| **primary endpoint** | repaired parse rate **and** exact semantic-preservation rate, reported separately |
| **success threshold** | repaired parse ≥95% · semantic preservation ≥90% · no domain below 70% repaired parse · completion tokens ≤2× matched structured English |
| **legitimate negative** | a candidate that fails these thresholds has failed *the prerequisite*. It does **not** refute H1, H2 or H3. |
| **current status** | **BLOCKED** — not yet run |
| **supporting experiments** | none yet; offline round-trip evidence only |
| **first eligible stage** | M2_FROZEN_SYNTAX_ACQUISITION |

**Why BLOCKED rather than UNTESTED.** The offline equivalence gate has passed for the
adapter layer — all four surfaces recover hash-identical canonical objects on four examples
— but no model call has been made. The block is `REMOTE_SAFETY_BLOCKED` at the repository
level plus incomplete M1 integration, not a scientific obstacle.

---

## H1 — input representation

| field | value |
|---|---|
| **causal question** | Does receiving the problem *in* the representation improve answer accuracy relative to receiving it in English? |
| **treatment** | Hamiltonian encoding as model input |
| **comparator** | matched structured English; LaTeX; existing formal notation |
| **fixed variables** | model · output format · compute budget · mathematical information content · demonstration count |
| **primary endpoint** | paired answer accuracy |
| **success threshold** | ≥+5 percentage points paired, CI excluding zero |
| **legitimate negative** | no improvement once tokens and information are matched — a real and reportable finding |
| **current status** | **UNTESTED** |
| **supporting experiments** | none. HML-EVAL-001 did **not** isolate H1. |
| **first eligible stage** | M3, after ACQ0 passes |

---

## H2 — reasoning representation

| field | value |
|---|---|
| **causal question** | Does *reasoning in* the representation improve the answer, independently of how the problem was presented? |
| **treatment** | English input, Hamiltonian derivation **required** |
| **comparator** | English input, free-form reasoning |
| **fixed variables** | model · input representation (English, both arms) · compute · recorded inference limits |
| **primary endpoint** | paired answer accuracy; secondarily structural-error rate |
| **success threshold** | ≥+5 points answer accuracy, or ≥30% structural-error reduction |
| **legitimate negative** | forcing a formal derivation degrades performance — published evidence (Tam et al., EMNLP 2024) points this way, so a negative here is expected-plausible, not anomalous |
| **current status** | **UNTESTED** |
| **supporting experiments** | none |
| **first eligible stage** | M3 |

---

## H3 — verifier-guided reasoning

| field | value |
|---|---|
| **causal question** | Does compiler/verifier feedback change the reasoning *trajectory* enough to improve the verified answer? |
| **treatment** | same input and derivation, **plus** diagnostic feedback and one repair |
| **comparator** | identical condition with feedback withheld |
| **fixed variables** | input representation · reasoning representation · model · task set · repair budget |
| **primary endpoint** | kernel-verified completion rate |
| **success threshold** | ≥+10 points verified success |
| **legitimate negative** | feedback does not change the trajectory, only the surface |
| **current status** | **UNTESTED** |
| **supporting experiments** | none |
| **first eligible stage** | M3 |

**The most important reporting rule in this document.** A win on H3 alone is a win for
**verifier-guided reasoning**, not for the representation. It would mean the compiler is
valuable and the language is not — a real, publishable, and quite different result from the
one the project set out to find. It must be reported as such.

**Two structural threats to H3, both already present in the codebase:**

1. *Answer leakage.* A diagnostic containing the complete target program, the final answer,
   or an unrestricted replacement patch converts H3 from a measurement into a tautology.
   The diagnostic contract forbids all three.
2. *No diagnostic at all.* Where the compiler accepts wrong code, the repair loop receives
   nothing to act on. Confirmed on 2026-08-05: a user `def` call checks neither arity nor
   argument type, so `f(1.0)` on a two-parameter definition compiles clean. Such errors are
   **unrepairable by construction** and would depress H3 for a reason unrelated to the
   hypothesis. This is why the Phase 1 repair blockers precede any H3 measurement.

---

## Correction log

Append-only. Never edit an entry; add a new one.

### 2026-08-05 — HML-EVAL-001 does not bear on H1, H2 or H3

The pilot conflated all three and its conclusion is:

> Zero-shot Hamiltonian did not improve answer accuracy on this small, low-discrimination
> pilot. The experiment was underpowered and had a severe ceiling effect.

14 of 15 problems were solved by nearly every arm; minimum detectable effect ~33 points.
**Status of the thesis: UNPROVEN, NOT REFUTED.** An earlier version of
`V1_GATE_DECISION.md` used the word "refuted", contradicting the project's own pilot report
§9. The report was right; the word was wrong; the correction is recorded there.

### 2026-08-05 — ACQ0 introduced as a distinct identifier

Earlier documents treated syntax acquisition as part of the H1/H2/H3 programme. It is a
**prerequisite**, and its repair mechanism (`ACQ0_REPAIR`) is not H3. Separating them
prevents a future reader from mistaking "the model learned to write the syntax with
compiler help" for "verifier feedback improved mathematical reasoning".
