# MultiDiGraph bellman_ford_path_length: the collapse "optimization" costs more than it saves, and the handover's top row is a screening artifact (br-r37-c1-kacb2 handover)

SilverLarch, 2026-08-27. Instruction counts, because scripts/host_quiet_check.py has
refused this host all session. Whole program so the fnx and nx arms share one scope,
OpenBLAS/OMP/MKL pinned to 1, slope over IR_REPS 10->20 so the fixture build is not
charged per call. Fixture: MultiDiGraph N=800, 3 out-edges per node, float weights,
seed 7. fnx and nx return IDENTICAL results on every arm (146.0, path length 61).

## The handover's ranked #1 does not reproduce

br-r37-c1-kacb2 handed over "MultiDiGraph dijkstra_path 0.33x and bellman_ford_path_length
0.30x, against MultiDiGraph dijkstra_path_length at 8.2x - three sibling calls on one
class spanning 0.30x to 8.2x says the fast path is reached by one spelling and not its
neighbours." Those were explicitly SINGLE-RUN SCREENING numbers. Re-measured:

    op                          fnx Ir/call     nx Ir/call    ratio nx/fnx   handover
    dijkstra_path                 1,834,392      8,512,408        4.64x        0.33x
    dijkstra_path_length          1,720,233      7,926,805        4.61x        8.2x
    bellman_ford_path_length     55,129,849     20,060,386        0.364x       0.30x

dijkstra_path is a 4.64x WIN, not a 0.33x loss. It and dijkstra_path_length sit 6% apart,
so there is no path-versus-length split: BOTH reach the raw MultiDiGraph kernel, both
return non-None, and _should_delegate_dijkstra_to_networkx is False. Only the
bellman_ford row survives, and at 0.364x rather than 0.30x.

## Where the bellman_ford loss actually is

bellman_ford_path_length on a multigraph calls _multigraph_collapse_min_weight_bellman -
building a whole new simple graph per call - and then recurses into the simple kernel.
Isolating exactly that one step:

    collapse alone                              41,524,156 Ir/call   75.3%
    residual (simple kernel + wrapper)          13,605,693
    ------------------------------------------------------------
    full call                                   55,129,849
    networkx's ENTIRE call                      20,060,386

fnx's own algorithm costs 13.6M, which is 1.47x FASTER than networkx's whole call. The
per-call collapse is what turns that win into a 0.364x loss. The collapse alone costs
2.07x networkx's entire operation.

## The optimization is backwards

The source comment says the collapse "replaces the slow native multigraph kernel AND the
two O(|E|) Python gate scans". The native kernel is slow on a multigraph - but not as slow
as the collapse route. Applying it DIRECTLY to the multigraph, no collapse:

    current route: collapse + simple kernel     55,129,849 Ir/call
    direct raw kernel on the multigraph         44,296,504 Ir/call    1.24x cheaper
    networkx                                    20,060,386

_raw_bellman_ford_path_length accepts the MultiDiGraph and returns 146.0, the same answer
networkx and the public wrapper give. So the collapse is not buying speed at this size; it
is spending 41.5M to avoid a 44.3M path and paying 13.6M more on top.

## The root defect is the native kernel's multigraph handling

    native kernel on the COLLAPSED simple graph   ~13.6M Ir/call
    native kernel on the MULTIGRAPH                44.3M Ir/call     3.3x

That 3.3x is the thing worth fixing IN THE KERNEL. Neither route that recomputes per call
reaches parity: the best such fnx route is 44.3M against networkx's 20.1M, i.e. 0.45x.

CORRECTION (measured after this file was first written): the sentence here originally said
caching the collapse "only ever recovers the gap between 55.1M and 44.3M". That is WRONG -
44.3M is a different route, not a floor. A cache hit skips the collapse entirely and costs
15,256,361 Ir/call, which is 3.61x self and 1.315x AGAINST NETWORKX, i.e. a win. Caching is
the strongest route, not the weakest. See NEGATIVE_EVIDENCE_cc.md for the staleness blocker
that the obvious implementation of it would miss.

## Not shipped, and why

Rerouting to the raw kernel is a 1.24x self-speedup available with a Python-only change and
no Rust build. It is NOT made here because the collapse is not purely an optimization: the
comment records that it replaced two O(|E|) Python gate scans and that it "keeps negatives
(valid for Bellman-Ford) and delegates only NaN/inf/nonnumeric". Dropping it is therefore a
PARITY change on weight validation before it is a perf change, and this repo has a standing
record of fast paths entered ahead of their delegation predicate
(br-r37-c1-04z53.9172 is scarred into both dijkstra siblings for exactly that). Any reroute
needs the NaN / inf / non-numeric / negative-cycle rows green FIRST.

## Instrument notes

Every arm was checked for negative per-call deltas, which prove a symbol is driven by
elapsed wall time rather than by the loop. Worst case here was 0.068% of the total
(allocator jitter), against ~50% when an OpenBLAS spin thread contaminated an earlier
measurement this session - these rows are clean.

## Reproduce

    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=python \
    FNX_MOD=fnx FNX_OP=bellman_ford_path_length IR_REPS=20 FNX_N=800 PYTHONHASHSEED=0 \
    valgrind --tool=callgrind --callgrind-out-file=out --quiet python3 ir_probe_sssp.py

FNX_OP also accepts dijkstra_path, dijkstra_path_length, collapse (the collapse step in
isolation) and rawmg (the native kernel applied directly to the multigraph). Run each at
IR_REPS 10 and 20 and take the slope.
