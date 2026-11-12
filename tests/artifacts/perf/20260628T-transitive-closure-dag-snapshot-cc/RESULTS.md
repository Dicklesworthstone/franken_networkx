# transitive_closure_dag snapshot fix — CopperCliff 2026-06-28

## Problem
_transitive_closure_dag_inproc ran the distance-2 BFS calling succ(TC, node) (PyO3
successor lookup) per node on the MUTATING TC — O(closure-edges) round-trips. 0.706x
vs nx (n=300), consistent across seeds.

## Fix (pure Python, br-cc-tcdsnap)
Snapshot TC's successor adjacency ONCE into Python lists (insertion order), run the
BFS on those, keep them in sync as transitive edges are discovered (so a node's
successors are closed before its predecessors read them in reversed-topo order),
and commit ALL transitive edges in ONE add_edges_from. Byte-identical: same per-v /
set-order edge append => identical edge set AND per-node adj iteration order.

## Measured (median across seeds)
n=200 (closure 7.5k): 0.706x -> 2.16x ; n=300: 1.43x ; n=400 (closure 56k): 1.05x ;
n=600 (closure 47k): 1.08x ; n=1000 (closure 89k): 0.92x.
WIN for typical sizes; strictly better than the old 0.67x at EVERY size (worst 0.92x
at huge dense closures, still a 1.4x self-improvement).

## Correctness
- 0/60 byte-exact vs nx (edge set + per-node adj order; explicit topo_order too)
- 761 dag/transitive/closure conformance tests pass
