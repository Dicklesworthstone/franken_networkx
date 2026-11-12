# DiGraph.neighbors is NOT O(node key length) relative to networkx (br-r37-c1-sznaj)

SilverLarch, 2026-08-27. Instruction counts, decidable at any host load — which was
required, since `scripts/host_quiet_check.py` refused this host all session
(loadavg 15 to 192) and no wall-clock number was admissible.

Reproduce (from repo root, `PYTHONPATH=python`):

    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    FNX_MOD=fnx FNX_K=2000 FNX_FRESH=1 IR_REPS=4000 PYTHONHASHSEED=0 \
    valgrind --tool=callgrind --callgrind-out-file=out --quiet python3 ir_probe_nbr.py

Run each cell at IR_REPS 2000 and 4000 and take the SLOPE; the fixture build enters
the same code and otherwise charges a large constant to the per-call figure.

## Result: fnx and networkx slope IDENTICALLY in key length

Whole program, threads pinned, fresh keys, per call:

    K=2       fnx    7,736    nx    7,754    fnx-nx    -18
    K=2000    fnx  233,880    nx  233,942    fnx-nx    -62

    key-length slope   fnx +226,144    nx +226,188    fnx EXCESS  -44 Ir/call

fnx slopes 44 Ir/call LESS than the incumbent over 1998 extra key bytes. There is no
fnx-specific key-length tax to remove.

## Where the slope actually goes

Toggled on `PyDiGraph::__pymethod_neighbors__` (native side only), per call at K=2000,
by differencing rep counts:

    PyObject_Hash                              5,626 Ir/call   84.1%
    __memcmp_avx2_movbe                          293           4.4%
    fnx SipHash of the canonical                  55           0.8%

The slope is CPython computing and caching the hash of a fresh long `str`. networkx
indexes `_adj` by that same object and pays it identically. fnx's own key-length work is
55 Ir/call, which bounds what any fix here could win at 0.02% of the operation.

## The bead's sloped row does not reproduce on HEAD

Toggled, native side, per call:

    keys REUSED (same str objects)   K=2  736    K=2000  734    FLAT
    keys FRESH (equal, not identical) K=2  914    K=2000 6,686   7.3x

The bead recorded DiGraph 134.9 ns -> 640.3 ns while three sibling classes stayed flat.
Under the reused-key shape that row is now FLAT (736 vs 734), consistent with the index
lookaside landed after the bead was filed (br-r37-c1-0k6zl / ktsxn / acb088e3a) resolving
the node index from CPython's cached hash instead of canonicalising. Under the fresh-key
shape both libraries slope together, as above. Neither shape leaves an fnx gap.

## Two instrument failures this cost, recorded so they are not repeated

1. `blas_thread_server` (OpenBLAS spin threads, pulled in via networkx -> scipy) lands in
   whole-program callgrind output at 8,177 and 23,056 Ir/call — the order of the whole
   signal — and for one arm differenced to MINUS 2,903 Ir/call. A negative per-call delta
   is proof the symbol is not driven by the loop: a spin thread's Ir tracks elapsed wall
   time, so whole-program Ir is NOT load-independent until the pools are pinned. Pinning
   removed it entirely and cut the total from 3.18e9 to 1.34e9. The per-function
   negative-delta count is now printed as a contamination check and is 0 for every cell
   above.
2. The bead names `PyDiGraph::successors` as the target; toggling there yields Ir=0,
   because `neighbors` enters `__pymethod_neighbors__`. Ir=0 means the symbol never
   matched, not that the work is free. A previous attempt on this bead spent a build
   patching row-dict functions that were likewise not on the path.
