#!/usr/bin/env bash
# Repeat-run a pytest selection and record the exit status of every run.
#
# Why this exists: `pyproject.toml` already puts `-q` in `addopts`, so passing `-q`
# again silences the final "N passed" line and a naive loop then has no evidence of
# what happened. This script never adds `-q`; it captures each run's real exit code
# and the real summary line, one file per run.
#
# Usage:
#   scripts/reproducibility/stability_runs.sh <runs> <label> [pytest args...]
#
# Example:
#   scripts/reproducibility/stability_runs.sh 5 full -n 18 -p no:cacheprovider
#
# Exit status is 0 only if every run exited 0.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${HML_PYTHON:-$REPO/.venv/bin/python}"

RUNS="${1:?usage: stability_runs.sh <runs> <label> [pytest args...]}"
LABEL="${2:?usage: stability_runs.sh <runs> <label> [pytest args...]}"
shift 2

OUTDIR="${HML_STABILITY_OUTDIR:-${TMPDIR:-/tmp}/hml-stability}/$LABEL"
mkdir -p "$OUTDIR"

failures=0
for i in $(seq 1 "$RUNS"); do
    log="$OUTDIR/run_${i}.log"
    start=$(date +%s)
    "$PY" -m pytest "$@" >"$log" 2>&1
    status=$?
    end=$(date +%s)
    summary=$(grep -oE '[0-9]+ (passed|failed|error)[^\n]*' "$log" | tail -1)
    [ -n "$summary" ] || summary="(no summary line; see $log)"
    printf '%s run %d/%d: exit=%d elapsed=%ds :: %s\n' \
        "$LABEL" "$i" "$RUNS" "$status" "$((end - start))" "$summary"
    if [ "$status" -ne 0 ]; then
        failures=$((failures + 1))
        echo "--- failing tail of $log ---"
        tail -40 "$log"
        echo "--- end tail ---"
    fi
done

echo "$LABEL: $((RUNS - failures))/$RUNS runs exited 0 (logs in $OUTDIR)"
[ "$failures" -eq 0 ]
