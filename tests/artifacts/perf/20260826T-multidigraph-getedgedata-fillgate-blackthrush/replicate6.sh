#!/bin/bash
# Balanced replication of the digraph A/B. Arm ORDER is B,A,A,B so that any
# monotone load drift over the session cancels between arms instead of being
# confounded with arm identity -- the same reason paired() alternates AB/BA per
# round, applied to the outer loop. A peer criterion benchmark is holding ~55
# cores for the whole run, so the dual A/A nulls and replication, not a quiet
# host, are what decide whether a row is usable.
set -uo pipefail
W=/data/tmp/claude-1000/-data-projects-franken-networkx/58e12b6f-96f8-4c7b-b881-51d9992f6f6f/scratchpad
PY=/data/projects/franken_networkx/.venv/bin/python
i=0
for arm in before6 after6 after6 before6; do
    i=$((i+1))
    farm="$W/farm_$arm"
    echo "===== pass $i arm=$arm ====="
    PYTHONPATH="$farm" FNX_ARM="$arm" FNX_EXPECT_SO="$farm/franken_networkx/_fnx.abi3.so" \
        "$PY" "$W/probe_ged.py" 2>&1 | tee "$W/rep_${i}_${arm}.log" \
        | grep -E '^  0\.|^  1\.|^arm=|^decidable'
done
