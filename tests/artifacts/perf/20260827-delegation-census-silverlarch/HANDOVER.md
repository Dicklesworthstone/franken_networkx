# Delegation census: the signal, two wins from it, and the ranked remainder

SilverLarch, 2026-08-27. Filed as an artifact because the beads store is malformed
("database disk image is malformed ... duplicate import comment id 965") and refused every
`br create` / `br comments add` this session. Re-file as beads when it is repaired.

## The signal, and why it is the right one

A function that runs networkx's own code by DELEGATING reads about 0.96x against networkx -
its own work plus a graph conversion. That signature found two levers, both now landed:

    effective_size(DiGraph, nodes=<iterable>)   0.964x -> 1068x   86e61d1d3
    greedy_color(DiGraph)                       0.136x -> 7.512x  d41439e0f

A COMPETING SIGNAL WAS TESTED AND REJECTED: "native kernel present but unreferenced". 55
such kernels exist in `_fnx`; 16 were screened against networkx and EVERY ONE is already a
win, 1.56x to 98.5x. A dead kernel is not a lever - `effective_size_directed_rust` paid off
because its function had a delegated BRANCH, not because the kernel was unused. Do not
mine that list.

## Method

    grep the enclosing public def of every `_call_networkx*` call site
      -> 130 public functions contain one
      -> 86 are callable as f(G)

Screen those against networkx on Graph and DiGraph, check parity on every row, then
RE-MEASURE anything that ranks badly with a FRESH GRAPH PER FUNCTION.

## HARNESS DEFECT - read before reusing the first screen

The first screen reused ONE graph object across all functions. Two of its verdicts did not
survive re-measurement with fresh graphs:

    all_pairs_dijkstra_path (DiGraph)   screen 0.712x @ 83.0ms   fresh 1.618x @ 2.9ms
    spectral_ordering (Graph)           screen 0.815x            fresh 1.021x

The first is a WIN reported as a loss, and its 83ms is 28x the directly measured 2.9ms.
I could not reproduce that 83ms: a fresh graph reads 5.4ms, and replaying the screen's
exact function prefix onto one shared graph reads 3.2ms. I also tested the obvious
mechanism - that earlier reads dirty fnx's store and force later calls onto slow paths -
and REFUTED it: prior calls make this function FASTER (4.16 -> 3.40 -> 2.89 ms), not slower.

So the one-graph screen has a defect I did not diagnose. Its numbers are not usable and are
not reproduced here. Only the fresh-graph rows below are.

## Ranked remainder, fresh graph per function, two independent runs each

N=60, weighted, attributed, spanning cycle plus random edges. Repeat-min wall clock on a
shared host - RANKING, not claims. Every row was parity-checked against networkx and
matches. Re-measure in instructions before acting.

    function                          class      run1     run2    fnx      note
    min_weight_matching               Graph     0.641x   0.692x   1.29ms   worst ratio
    maximum_branching                 Graph     0.747x   0.762x   2.39ms
    minimum_branching                 Graph     0.783x   0.813x   2.54ms
    harmonic_diameter                 DiGraph   0.830x   0.830x   3.67ms
    max_weight_matching               Graph     0.867x   0.866x   2.68ms
    transitive_closure                Graph     0.875x   0.868x  20.48ms   largest absolute
    minimum_edge_cut                  Graph     0.923x   0.913x   4.95ms
    spectral_ordering                 DiGraph   0.764x   0.855x  54.96ms   UNSTABLE, do not
                                                                           rank until pinned

Ranked by time actually lost per call, `transitive_closure` (~2.7 ms) and
`spectral_ordering` (~10 ms, if it holds up) lead; by ratio, `min_weight_matching` does.

Also still open and measured elsewhere: `constraint(DiGraph, nodes=<iterable>)` at 0.964x
and 2.59e9 Ir/call - the direct effective_size sibling, needing a directed kernel because
`constraint_rust` is undirected-only (548/807 mismatches). See
tests/artifacts/perf/20260827-structuralholes-directed-subset-silverlarch/.

## The recipe that worked twice

  * Confirm the function actually delegates on the shape you are measuring - both wins had
    a branch that delegated only for some inputs (directed, or nodes=<iterable>).
  * Check whether a kernel already exists before writing one. effective_size needed no Rust
    at all; greedy_color needed ~80 lines.
  * PROVE THE ALGORITHM IN PYTHON FIRST against the exact networkx path you must match,
    over randomized graphs, before writing Rust. Both ports were mechanical because of this.
  * Watch which networkx path you are matching. `effective_size` and `constraint` each have
    TWO implementations that disagree on directed graphs (a scipy matrix path for
    nodes=None, a loop otherwise) - matching the wrong one is what kept
    `effective_size_directed_rust` reverted for months.
  * Compare exceptions by TYPE AND ARGS. A type-only sweep reports false green.
