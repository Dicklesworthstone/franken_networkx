# minimum_branching: the published claim holds, the non-empty case is new evidence, and the UNDIRECTED class is a loss (br-r37-c1-p80x1.14)

SilverLarch, 2026-08-28. Instruction counts; `host_quiet_check` refuses this host (loadavg
19-28), so no wall-clock is quoted. Whole program, OpenBLAS/OMP/MKL pinned to 1, slope over
IR_REPS 2->4, n=400 with 5 out-edges per node, seed 11, both arms on the same fixture and
returning identical results.

## Three workloads, one function

    workload                                              fnx Ir/call    nx Ir/call   ratio
    DiGraph, weights 1..20   (result: 0 edges)             44,748,344   167,716,300   3.748x
    DiGraph, weights -20..-1 (result: 198 edges)          146,161,560   387,294,347   2.650x
    Graph,   weights 1..20   (result: 0 edges)            220,043,588   170,940,154   0.777x

## The published claim reproduces, and my suspicion of it was wrong

The README publishes minimum_branching at 3.9768x, and br-r37-c1-p80x1.14 records the
recovered fixture as n=800, m=4000, weights 1..20, "returns 800 nodes and zero edges". A
minimum branching over ALL-POSITIVE weights is empty by definition - selecting no edge
costs 0 and every edge adds cost - so I expected the published row to be timing an
algorithm that does nothing, and to fall apart on a real input.

IT DOES NOT. The empty-edge row reproduces at 3.748x against 3.9768x published, and the
non-empty workload is ALSO a win at 2.650x. The claim is lower on real work than on the
degenerate case, which is worth knowing, but it is not resting on a degenerate benchmark.

## The evidence the bead asked for

br-r37-c1-p80x1.14 states: "This exact row may only support the empty-edge workload. Any
claim about a non-empty minimum branching needs a separately preregistered fixture with at
least one selected edge and its own complete parity and timing evidence."

That fixture is the negative-weight row above: identical shape, weights negated, 198 edges
actually selected, fnx and networkx returning the same branching. 2.650x. Note this does
NOT satisfy the bead's own gate for re-running the EMPTY-edge row, which is blocked on an
RCH managed-target precondition and on 21 rounds with dual A/A nulls; it is the separate
non-empty evidence the bead names as missing, measured in instructions rather than
nanoseconds because the host will not hold still.

## The loss: undirected is 0.777x, a 4.8x spread on one function

networkx accepts an undirected graph here (br-r37-c1-ugod2 notes this), and fnx routes it
differently:

    if partition is not None or not G.is_directed() or G.is_multigraph():
        ... _call_networkx_for_parity(...) then _from_nx_graph(nx_result)

So the undirected class pays a faithful fnx->nx conversion, networkx's call, AND a
conversion back, where the directed class uses the native `_raw_minimum_branching`. On the
same empty-result workload that is 220.0M against the directed path's 44.7M - fnx is 4.9x
more expensive on itself for the same answer - and 0.777x against networkx.

This is the class-gated shape that br-r37-c1-vevfq had for greedy_color (Graph 8.7x,
DiGraph 0.114x), with the classes swapped.

## A short-circuit that does NOT work, tested

If networkx always returned a nodes-only graph for undirected input, fnx could emit that
directly and skip both conversions. It does not: over 150 undirected graphs with weights in
-20..20, 144 returned at least one edge. The undirected path does real work and the
delegation cannot be short-circuited. Node attributes are not preserved in the result, so
the return conversion is cheap; the input conversion is where to look.

## Reproduce

    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=python \
    FNX_MOD=fnx FNX_N=400 IR_REPS=4 PYTHONHASHSEED=0 \
    valgrind --tool=callgrind --callgrind-out-file=out --quiet python3 ir_probe_branching.py

FNX_NEG=1 selects the non-empty fixture, FNX_UNDIR=1 the undirected one, FNX_MOD=nx the
incumbent. Run each at IR_REPS 2 and 4 and take the slope.
