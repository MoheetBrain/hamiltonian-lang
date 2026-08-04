---
name: run-conformance
description: Run the full conformance pass — formatting, lint, type checking, unit tests, golden tests, round-trip tests, schema validation and adversarial tests. Use before declaring any change complete.
---

# /run-conformance

Run every stage. Report the real result of each, including failures. "Not run" is a valid
and required answer when a tool is unavailable.

```bash
.venv/bin/ruff format --check src tests
```

```bash
.venv/bin/ruff check src tests
```

```bash
.venv/bin/mypy src/hamiltonian_lang
```

```bash
.venv/bin/python -m pytest -q
```

```bash
.venv/bin/python -m pytest tests/golden tests/roundtrip tests/adversarial -q
```

Schema validation of the canonical form against `spec/ir.schema.json`:

```bash
.venv/bin/python -c "
import json, jsonschema, pathlib
from hamiltonian_lang import compile_source
schema = json.loads(pathlib.Path('spec/ir.schema.json').read_text())
bad = 0
for p in pathlib.Path('examples').rglob('*.hml'):
    if 'candidate_syntaxes' in p.parts: continue
    r = compile_source(p.read_text(), str(p))
    if not r.ok():
        print('CHECK FAILED', p); bad += 1; continue
    jsonschema.validate(json.loads(r.canonical()), schema)
    print('ok', p)
raise SystemExit(1 if bad else 0)"
```

Every example must still check:

```bash
for f in examples/*/*.hml; do .venv/bin/hml check "$f" || echo "FAILED $f"; done
```

## Reporting rules

- Record the exact command and its actual output.
- A changed golden hash is a **semantic change**, not a test flake. Do not re-bless it
  without a `DECISIONS.md` record.
- Never claim a stage passed unless it was executed.
