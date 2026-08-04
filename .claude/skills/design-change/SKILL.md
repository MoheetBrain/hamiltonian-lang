---
name: design-change
description: Create a formal design-change proposal before altering the frozen semantic contract. Use when a change would touch ast/nodes.py, types.py, the grammar, the canonical form, or any rule in SPEC.md.
---

# /design-change

The v0 contract is frozen (`docs/design/V0_DESIGN_FREEZE.md`). Changing it is allowed —
changing it silently is not.

## Procedure

1. **Establish the current behaviour by running it**, not by reading the code.
   ```bash
   .venv/bin/hml check <a file exercising the construct>
   .venv/bin/python -m pytest -q
   ```
   Record the actual output. A proposal built on an assumed behaviour is void.

2. Write the proposal into `DECISIONS.md` as the next `D-0NN`, with every field:

   - **Question** — one sentence, answerable
   - **Current behaviour** — with the command and its real output
   - **Proposed change**
   - **Semantic implications** — which of the prohibited conflations does this come near?
   - **Grammar implications** — does the change affect parse determinism or lookahead?
   - **Canonical-form implications** — will existing content hashes change? If yes, say
     so explicitly; golden tests will fail and that failure is the point.
   - **Compatibility** — which backends, examples and benchmarks break
   - **Tests** — the specific new positive, negative and round-trip tests
   - **Alternatives** — including doing nothing
   - **Confidence** and **Reversal cost**
   - **Decision**

3. Implement, then run the full conformance pass (`/run-conformance`).

4. If canonical hashes changed intentionally, re-bless and say why in the decision record:
   ```bash
   HML_BLESS=1 .venv/bin/python -m pytest tests/golden -q
   ```

## Refuse to proceed when

- the change makes the language more complex without a demonstrated requirement (rule 7)
- it introduces a subtyping path between `T`, `RandomVariable[T]` and `Distribution[T]`
- it linearises the scalar poset
- it makes any semantic distinction depend on whitespace
