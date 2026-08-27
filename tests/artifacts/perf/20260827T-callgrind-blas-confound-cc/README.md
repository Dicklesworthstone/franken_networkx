# Instruction-count measurement on this repo has an ASYMMETRIC BLAS confound (br-r37-c1-cgblas)

**Verdict: methodology artifact. `iter(G[u])` on a multigraph row measures
2.24x networkx's instructions — NOT the 3.17x a naive callgrind run reports.**

Wall-time on this host ranged loadavg 12-95 during this cycle, which voids
timing, so instruction counts were used to locate cost. They have their own trap.

## The trap

fnx's import chain pulls numpy, and numpy's OpenBLAS starts a `blas_thread_server`
that SPINS. networkx's does not:

    grep -c blas_thread_server  cg2_nx_60.out  -> 0
    grep -c blas_thread_server  cg2_fnx_60.out -> 1

In a naive callgrind run that spin was **65.79% of total Ir**. Worse, it does not
cancel in a difference: spin accrues with WALL-TIME, so the longer (more work)
run accrues more of it, and the extra lands in the delta as if it were work.

## Corrected numbers

Same-library zero-work subtraction (which correctly cancels import, interpreter
startup and graph construction), 18,000 `iter(row)` calls on a MultiGraph row,
V=800 E=3200:

    OPENBLAS_NUM_THREADS unset (naive)      nx 1538.7 Ir/call   fnx 4877.2   3.17x
    OPENBLAS_NUM_THREADS=1 (correct)        nx 1609.4 Ir/call   fnx 3605.7   2.24x

The confound inflated fnx by about 41 percent, and shrank fnx's zero-work total
from 2.89e9 to 0.95e9 Ir — roughly 2e9 Ir of pure spin.

## How to measure Ir on this repo

1. Pin `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`. Without it
   any fnx-vs-networkx instruction comparison is biased AGAINST fnx, because only
   fnx pulls the spinning thread.
2. Difference two runs of the SAME library (N work iterations vs zero). A
   baseline process that imports neither is useless here: fnx's import alone is
   ~0.95e9 Ir and swamps the signal.
3. Do not land on Ir alone. See below.

## Ir UNDER-PREDICTS the wall-clock gap here, so it locates but does not decide

    instructions   fnx / nx = 2.24x
    wall clock     fnx / nx = 3.3x   (iter(row) measured at 0.30x)

Instructions say 2.24x; the clock says 3.3x. The excess is not in the instruction
stream — it is PyO3 crossing cost per instruction (cache and branch behaviour),
which callgrind's Ir does not price. So Ir is the right tool for LOCATING cost
under a noisy host and the wrong tool for deciding whether a lever landed.
That direction of error is the opposite of the documented
`ir_can_move_opposite_to_wallclock` case, and both say the same thing: confirm on
the clock.

## Standing conclusion for the row itself

Unchanged from `20260827T-multigraph-row-iter-token-cc`: `iter(G[u])` is bounded
by its cache-validation token, whose two getters cost 64.2ns against networkx's
62.0ns for the ENTIRE operation. The instruction count corroborates a real ~2.2x
gap but does not change that ceiling, and the combined-accessor lever was already
built and refuted (br-r37-c1-revtoken).

## Provenance

    bench_elf_sha256=5ebd66b00b74898d61ce9af11022b013a7bd265fc26aa30690bc9f1bdc8a2ef8
    valgrind 3.25.1, callgrind, --callgrind-out-file per arm, `summary:` differenced
