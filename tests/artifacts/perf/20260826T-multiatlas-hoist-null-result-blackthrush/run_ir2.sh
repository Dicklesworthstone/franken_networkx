#!/bin/bash
# Ir attributable to ONE pymethod, with setup excluded by construction.
#
# The two-point-slope version of this failed: total-program Ir varies ~±50M
# run to run (interpreter startup / GC / allocator), which swamps a ~200M
# signal and produced a NEGATIVE slope on one control -- proof the instrument,
# not the code, was wrong. --collect-atstart=no + --toggle-collect counts only
# the target function's own inclusive cost, so startup cannot contribute at all.
set -uo pipefail
W=/data/tmp/claude-1000/-data-projects-franken-networkx/58e12b6f-96f8-4c7b-b881-51d9992f6f6f/scratchpad
PY=/data/projects/franken_networkx/.venv/bin/python
N=${N:-20000}
OUT=$W/ir2_results.txt
: > "$OUT"

# op -> the pymethod whose inclusive Ir we collect
declare -A SYM=(
  [multi_adj]='*MultiAtlasView>::__pymethod___getitem____*'
  [multidi_adj]='*MultiDiAtlasView>::__pymethod___getitem____*'
  [graph_adj]='*AtlasView>::__pymethod___getitem____*'
)

for op in multi_adj multidi_adj graph_adj; do
    for arm in before5 after5; do
        for rep in 1 2; do
            mkdir -p "$W/cgtmp"
            f="$W/cgtmp/${op}_${arm}_${rep}.out"
            PYTHONPATH="$W/farm_$arm" FNX_OP=$op FNX_N=$N PYTHONHASHSEED=0 \
                valgrind --tool=callgrind --callgrind-out-file="$f" --quiet \
                         --collect-atstart=no --toggle-collect="${SYM[$op]}" \
                         "$PY" "$W/ir_probe.py" >/dev/null 2>&1
            ir=$(grep -m1 -oP '(?<=^summary: )\d+' "$f")
            echo "$op $arm rep$rep N=$N Ir=$ir per_call=$(( ${ir:-0} / N ))" | tee -a "$OUT"
        done
    done
done
echo "--- done ---"
