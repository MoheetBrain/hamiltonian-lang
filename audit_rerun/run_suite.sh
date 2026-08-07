#!/bin/zsh
# Rerun driver.  $1 = run label (directory under runs/), $2 = source tree to measure.
# Uses ONE interpreter for every run so that Python-version differences cannot be
# mistaken for language differences.  The compiler under test is selected purely by
# HML_PROBE_SRC.
set -e
LABEL=$1
SRC=$2
PY=/Users/moheet/hml_v2_worktree/.venv/bin/python
BASE=/Users/moheet/hml_v2_worktree/audit_rerun/runs/$LABEL/language_comparison
export HML_PROBE_SRC=$SRC
export PYTHONDONTWRITEBYTECODE=1
mkdir -p $BASE/logs
echo "=== $LABEL  src=$SRC ==="
$PY -c "import sys; sys.path.insert(0,'$SRC'); import hamiltonian_lang as H; print('ATTRIBUTION:', H.__file__)" \
  | tee $BASE/logs/ATTRIBUTION.txt
for t in probe_definedness probe_composition probe_epistemic_extensibility probe_critical_atoms probe_backends; do
  echo "--- $t ---"
  $PY $BASE/tools/$t.py > $BASE/logs/$t.log 2>&1 || echo "  (non-zero exit)"
  tail -6 $BASE/logs/$t.log
done
echo "--- build_coverage ---"
$PY $BASE/tools/build_coverage.py > $BASE/logs/build_coverage.log 2>&1 || echo "  (non-zero exit)"
cat $BASE/logs/build_coverage.log
