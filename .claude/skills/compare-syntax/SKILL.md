---
name: compare-syntax
description: Encode one task in multiple candidate syntaxes and record measured comparisons — character count, token count, parse success, ambiguity, readability. Use when evaluating a syntax change or adding a candidate grammar.
---

# /compare-syntax

Comparison is measurement, not preference. The output is a table of numbers plus stated
qualitative notes, clearly separated.

## Procedure

1. Encode the same task in every candidate under
   `examples/candidate_syntaxes/<candidate>/<task>.hml`. If a candidate cannot express the
   task, record that as a finding — do not fudge the encoding to make the table tidy.

2. Measure:
   ```bash
   .venv/bin/python experiments/alphabet/tokenisation_benchmark.py
   ```

3. Record per candidate:

   | metric | how |
   |--------|-----|
   | character count | `len(source)` |
   | line count | `source.count('\n')` |
   | token count | per tokeniser; label APPROXIMATE if the real tokeniser was unavailable |
   | fragmentation | tokens / characters |
   | parse success | `hml check` exit status, where a parser exists |
   | ambiguity | lookahead required; any genuinely ambiguous production |
   | error localisation | corrupt one character — does the diagnostic point at the right line? |
   | edit robustness | does a dropped line or lost indentation change meaning silently? |
   | readability | qualitative, and labelled as such |

4. Write results to `experiments/alphabet/results/` and the analysis to
   `docs/design/ALPHABET_STUDY.md`.

## Rules

- Never report a number you did not measure.
- A candidate winning on token count while losing on parse determinism has **not** won;
  state the trade-off rather than picking a headline metric.
- Do not declare a permanent winner from a single task. Reversibility is worth more than
  an early commitment.
