---
name: red-team-language
description: Attack the current Hamiltonian Lang specification and implementation to find semantic holes, unsupported claims and gameable metrics. Use before any milestone is declared complete.
---

# /red-team-language

The goal is to break it. A red-team pass that finds nothing has failed.

## Attack surfaces, in descending order of value

1. **Programs that check but mean something wrong.** Write `.hml` that passes
   `hml check` and should not. Every one of these is a hole in the type system, and this
   is the most valuable category by a wide margin.

2. **Prohibited conflations that are still reachable.** Try to make a `Distribution[T]`
   behave as a `T`; give one symbol two laws; compare a law to a value; use `=` where `~`
   is meant.

3. **Scope and binding.** Capture, collision, an index reused across a quantifier, a name
   bound in one scope and read in another.

4. **Canonical-form collisions.** Find two programs that mean different things and hash
   identically, or two that mean the same and hash differently. Either is a defect.

5. **Unsupported claims.** Grep the repository for assertions that exceed the evidence:
   ```bash
   grep -rniE "outperform|superior|better than|proven|demonstrat|state of the art|novel" \
     --include=*.md --include=*.py . | grep -v "^./audits/"
   ```
   Quote each hit verbatim with its file path and line.

6. **Metric gaming.** For every benchmark metric, describe the cheapest way to produce a
   fake positive result, and what stops it.

7. **Where existing tools win.** Name the specific cases where LaTeX, Lean, Stan or plain
   English is genuinely better. Be concrete.

## Output

Append to `audits/RED_TEAM_REPORT.md`. Every finding needs a reproducible snippet or
command. Add executable cases to `tests/adversarial/`.

If a case that *should* be rejected currently passes, **do not weaken the test.** Mark it
`xfail` with a clear reason and escalate to the Lead Architect.

## Authority

Veto over claims, not over implementation.
