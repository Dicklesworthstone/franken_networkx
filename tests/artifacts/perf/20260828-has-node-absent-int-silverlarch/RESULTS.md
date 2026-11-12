# G.has_node: the published 0.41x LOSS is real, and it is ONLY the absent-INT-key case (br-r37-c1-p80x1)

SilverLarch, 2026-08-28. Instruction counts; host_quiet_check refuses this host
(loadavg 8-46 across the session), so no wall-clock is quoted. Whole program,
OpenBLAS/OMP/MKL pinned to 1, slope over IR_REPS 100k->200k, n=2000, both arms on the same
fixture, foreground.

## The claim, and two beads that disagreed about it

The README publishes `has_node` at 0.41x, and the claim-coverage audit lists it among three
published LOSSES that are "still unverified numbers, but nobody acts on them to their
detriment". Two later beads reached opposite conclusions:

  * br-r37-c1-fov4a: "has_node 0.5114x to 0.7701x and STILL A LOSS"
  * br-r37-c1-native-method-attribute-lookup-tax-w7wjs: "has_edge/has_node/neighbors are at
    parity or better once measured honestly"

Both are right, about different cells. The axis neither split on is PRESENT versus ABSENT.

## Measured

    key    probe    fnx Ir/call   nx Ir/call   ratio
    str    hit             1793         1803   1.006x
    int    hit             1812         1828   1.009x
    str    MISS            1432         1207   0.843x
    int    MISS            2828         1215   0.430x

Hits are at parity on both key types - w7wjs is correct there. The loss is entirely on
ABSENT keys, and the absent-INT cell reads 0.430x, which is the published 0.41x. The claim
is real and it has been sitting under an axis nobody split.

Key type is a known fnx axis (br-r37-c1-node_key_type_is_a_measured_axis records +38-53%
while networkx is flat), which is why this probe varies it; a str-only probe would have
reported 0.843x and missed the published number entirely.

## Where the 1612 Ir/call gap goes

fnx-minus-nx on the absent-int path, per call. Every row below is a symbol networkx never
executes:

     +182   0x0000000000541310                      (CPython, unresolved)
     +121   _PyObject_MakeTpCall
     +119   _fnx::write_int_decimal                 <- the key IS canonicalised
     +101   0x0000000000540e00
      +93   0x00000000005b0920
      +90   _Py_DecRef
      +85   0x00000000005532a0
      +84   <_fnx::PyGraph>::__pymethod___contains____
      +83   <pyo3::err::PyErr>::take                <- an exception is BUILT and discarded
      +77   PyObject_GC_Del
      +70   IndexMap::get_index_of

Symbols present only in fnx total 937 Ir/call of the 1612 gap.

Two mechanisms are named and neither is speculative:

  * A DISCARDED PyErr. `<pyo3::err::PyErr>::take` runs on every absent-int probe, so fnx
    constructs and throws away a Python exception where networkx simply misses a dict.
    This is the exact shape br-ctaxkey recorded for `node_key_to_string`: "extract::<String>()
    constructs and discards a PyErr for every int/float node key ... that discarded PyErr
    dominated". It was fixed there by probing concrete types with `downcast` before any
    `extract`; the same repair is available here.
  * CANONICALISATION ON A MISS. `write_int_decimal` runs, so the absent key is being turned
    into its canonical form and probed against the map. A present int key answers from the
    presence cache (br-r37-c1-fov4a wired that), but a MISS cannot, by construction - a
    cache hit is existence proof, so absence always falls through.

## What this does NOT claim

No fix is attempted here. The absent-key path is also where networkx is cheapest (a dict
miss with no exception), so parity on this cell is not a given even after the PyErr is
removed: `write_int_decimal` plus the IndexMap probe are real work networkx never does.
Removing the discarded PyErr is worth roughly 83 Ir of the 1612, and the unresolved CPython
frames above it are the larger share and are not yet attributed.

## Reproduce

    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=python \
    FNX_MOD=fnx FNX_KEY=int FNX_MISS=1 IR_REPS=200000 FNX_N=2000 PYTHONHASHSEED=0 \
    valgrind --tool=callgrind --callgrind-out-file=out --quiet python3 ir_probe_hasnode.py

FNX_KEY selects str/int, FNX_MISS=1 the absent class, FNX_MOD=nx the incumbent. Run at
IR_REPS 100000 and 200000 and take the slope.

NOTE ON THE PROBE: the probe list is a FIXED size iterated `REPS // len(probe)` times. A
first version built a REPS-long list, which put the INPUT CONSTRUCTION in the slope and
inflated every cell to ~3100 Ir/call for what is a dict lookup. Any rewrite must keep the
construction out of the measured region.
