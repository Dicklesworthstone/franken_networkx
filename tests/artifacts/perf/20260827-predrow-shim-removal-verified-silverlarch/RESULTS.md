# DiGraph.predecessors: the 0.383x shim is gone, verified on the bead's own controls (br-r37-c1-predrow-8vytj)

SilverLarch, 2026-08-27. Instruction counts, because scripts/host_quiet_check.py has
refused this host continuously (loadavg 15-192 across the session; the previous attempt
on this bead was refused at loadavg 67.98 with a failing A/A null). No wall-clock row is
admissible and none is quoted.

## Why this bead was closable without new code

The fix already landed: DiGraph.predecessors is a method_descriptor on
DiGraph._native_predecessors_iter, so the Python keydict shim the bead describes -
"four `not in vars(self)` probes, a state tuple, two dict lookups and the frame itself" -
is no longer on the path. What was missing was a measurement, and the host would not give
one in nanoseconds.

## The bead's control design, reproduced in instructions

The bead's four rows are self-contained: DiGraph.predecessors was 2.1x worse than the
SAME class's successors and 2.0x worse than the OTHER class's predecessors, which is what
localised the cost to one binding rather than to predecessors-ness or directedness. Both
controls have collapsed.

Whole program, pools pinned, slope over IR_REPS 2000->4000, live networkx as the arm:

    class          op             fnx Ir/call   nx Ir/call   ratio nx/fnx   excess
    DiGraph        predecessors          4929         4832        0.9803x     +97
    DiGraph        successors            4882         4832        0.9896x     +50
    MultiDiGraph   predecessors          4938         4832        0.9784x    +106
    MultiDiGraph   successors            4936         4832        0.9787x    +104

    same-class  control (succ/pred ratio-of-ratios)   was 2.14   now 1.010
    other-class control (MDG/DG pred ratio-of-ratios) was 2.02   now 0.998

Every per-function delta was checked for negatives (a spin thread's Ir tracks wall time,
not the loop); all four cells are clean.

Toggled on each native pymethod, so the shared Python frame, list() and loop are excluded
and the fnx side is undiluted:

    DiGraph.predecessors        742 Ir/call
    DiGraph.successors          732
    MultiDiGraph.predecessors   802
    MultiDiGraph.successors     805

DiGraph.predecessors is now the CHEAPEST of the four native paths and sits 1.4% from its
same-class sibling, where the bead recorded 2.1x.

## What is NOT claimed

* This is an instruction-count result, not the nanosecond ratio the bead recorded. Ir has
  moved opposite to wall-clock in this repo before (br-r37-c1-p1tvg cut 101 Ir/call and
  ran 1.27x SLOWER), so the wall-clock row remains UNMEASURED, not disproved.
* The whole-program ratio is DILUTED: about 4832 Ir/call of it is shared Python overhead
  (loop, list(), len()) that both arms pay, which compresses every ratio toward 1.0. The
  honest statements are the fnx EXCESS column (+50 to +106 Ir/call) and the toggled native
  rows, not the 0.98x.
* fnx and nx run in SEPARATE invocations here. That is sound for Ir - counts are
  deterministic given identical input - but it is NOT the same-invocation interleaving a
  wall-clock row needs, where interleaving exists to cancel drift.
* Keys are REUSED objects, matching the bead's own probe shape. All rows sit at one short
  key length, where the fresh and reused shapes agree.

## Reproduce

    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=python \
    FNX_MOD=fnx FNX_CLS=DiGraph FNX_OP=predecessors IR_REPS=4000 PYTHONHASHSEED=0 \
    valgrind --tool=callgrind --callgrind-out-file=out --quiet python3 ir_probe_pred.py

Run each cell at 2000 and 4000 and take the slope; the fixture build enters the same code
and would otherwise be charged per call. analyze_pred.py builds the table.
