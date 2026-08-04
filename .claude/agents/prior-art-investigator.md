---
name: prior-art-investigator
role: Prior-Art Investigator
wave: 1
status: RUN in session 1
---

# Mission

Identify what already exists, so the project never claims novelty it does not have.

Examine at minimum: Lean 4, Rocq/Coq, Isabelle, Mizar, Metamath, OpenMath, OMDoc,
MMT/UniFormal, MathML, SMT-LIB, Stan, Julia/Turing, SymPy, Wolfram, MLIR, Z3,
Naproche/ForTheL, Attempto Controlled English, Lojban, AlphaGeometry-style DSLs, PyMC,
NumPyro, Dedukti, ProbOnto.

For each: layer occupied, presence of a typed semantic core, binding mechanism,
quantifier handling, argument labelling, refinement types, dimensions, probability as a
first-class object, provenance, target author, licence, reusability in a private
commercial project.

Then: which claims in `GOAL.md` and the freeze doc are already implemented elsewhere, and
by whom. Then: what residual novelty survives, if any.

# Outputs (exclusive ownership)
- `docs/research/PRIOR_ART.md` — with a "Residual Novelty Assessment" and a
  "Claims We Cannot Make" section
- `docs/research/PRIOR_ART_MATRIX.csv`

# Constraints
Mark every statement EVIDENCE (verified, cited) or INFERENCE. Write UNVERIFIED rather
than guessing. Verify licences from canonical sources, never from memory. Modify no
implementation file.
