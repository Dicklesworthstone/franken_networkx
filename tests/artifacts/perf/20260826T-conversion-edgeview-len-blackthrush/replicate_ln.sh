#!/bin/bash
set -uo pipefail
W=/data/tmp/claude-1000/-data-projects-franken-networkx/58e12b6f-96f8-4c7b-b881-51d9992f6f6f/scratchpad
PY=/data/projects/franken_networkx/.venv/bin/python
i=0
for arm in before13 after13 after13 before13 before13 after13; do
  i=$((i+1))
  PYTHONPATH="$W/farm_$arm" FNX_ARM="$arm" FNX_EXPECT_SO="$W/farm_$arm/franken_networkx/_fnx.abi3.so" \
    "$PY" "$W/probe_ln.py" > "$W/ln_${i}_${arm}.log" 2>&1
  echo "pass $i $arm done"
done
