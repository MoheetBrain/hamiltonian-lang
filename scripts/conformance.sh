#!/usr/bin/env bash
# Deterministic conformance gate. Used by the pre-commit hook and by CI.
# Every stage reports its real result; an unavailable tool is reported, not skipped
# silently.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"
fail=0

stage() {
  local name="$1"; shift
  printf '\n=== %s ===\n' "$name"
  if "$@"; then
    printf '    PASS: %s\n' "$name"
  else
    printf '    FAIL: %s\n' "$name"
    fail=1
  fi
}

skip_or_stage() {
  local name="$1" tool="$2"; shift 2
  if [ -x "$tool" ]; then stage "$name" "$@";
  else printf '\n=== %s ===\n    NOT RUN: %s is not installed\n' "$name" "$tool"; fi
}

skip_or_stage "ruff lint"     ".venv/bin/ruff"  .venv/bin/ruff check src tests
skip_or_stage "mypy"          ".venv/bin/mypy"  .venv/bin/mypy src/hamiltonian_lang

stage "examples check" bash -c '
  rc=0
  for f in examples/*/*.hml; do
    .venv/bin/hml check "$f" >/dev/null 2>&1 || { echo "  example failed: $f"; rc=1; }
  done
  exit $rc'

stage "pytest" "$PY" -m pytest -q

stage "canonical form validates against spec/ir.schema.json" "$PY" - <<'PYEOF'
import json, pathlib, sys
try:
    import jsonschema
except ImportError:
    print("  NOT RUN: jsonschema is not installed"); sys.exit(0)
from hamiltonian_lang import compile_source
schema = json.loads(pathlib.Path("spec/ir.schema.json").read_text())
bad = 0
for p in sorted(pathlib.Path("examples").rglob("*.hml")):
    if "candidate_syntaxes" in p.parts:
        continue
    r = compile_source(p.read_text(), str(p))
    if not r.ok():
        print(f"  {p}: does not check"); bad += 1; continue
    try:
        jsonschema.validate(json.loads(r.canonical()), schema)
    except jsonschema.ValidationError as e:
        print(f"  {p}: {e.message}"); bad += 1
sys.exit(1 if bad else 0)
PYEOF

stage "no unsupported superiority claims in public docs" bash -c '
  hits=$(grep -rniE "outperforms|superior to|better than (english|latex|lean|stan)|proven to (improve|outperform)|demonstrably better|state of the art" \
    --include="*.md" README.md GOAL.md ARCHITECTURE.md SPEC.md ROADMAP.md docs/design docs/language-guide 2>/dev/null || true)
  if [ -n "$hits" ]; then echo "$hits"; exit 1; fi
  exit 0'

stage "docs/private is not referenced from public docs" bash -c '
  hits=$(grep -rn "docs/private/" README.md GOAL.md ARCHITECTURE.md SPEC.md 2>/dev/null || true)
  if [ -n "$hits" ]; then echo "$hits"; exit 1; fi
  exit 0'

stage "no unresolved placeholders in production source" bash -c '
  hits=$(grep -rnE "\b(TODO|FIXME|XXX|TBD|PLACEHOLDER)\b" src/hamiltonian_lang || true)
  if [ -n "$hits" ]; then echo "$hits"; exit 1; fi
  exit 0'

printf '\n============================\n'
if [ "$fail" -eq 0 ]; then echo "CONFORMANCE: PASS"; else echo "CONFORMANCE: FAIL"; fi
exit "$fail"
