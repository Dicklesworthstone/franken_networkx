# transitive_closure (cyclic DiGraph): native kernel — 1.65x SLOWER -> 4.3-4.6x FASTER than nx (br-r37-c1-tc-cyclic)

## Problem
`transitive_closure` on a CYCLIC DiGraph (the common case) delegated entirely to
networkx and then rebuilt the (often dense, ~n^2-edge) result via _from_nx_graph
— 1.65x SLOWER than nx (2.76s @ n=500/m=2500). It delegated because the native
kernel dropped cycle-induced (v,v) self-loops: it pre-marked `source` visited so
a cycle could never rediscover it.

## Lever (ONE, two coordinated edits)
1. Kernel: seed the per-source BFS from `source`'s direct successors instead of
   pre-marking it visited. `source` is then rediscovered exactly when it lies on
   a non-trivial cycle (or has an explicit self-loop) — precisely nx's
   reflexive=False (v,v) rule. Discovery order recorded for deterministic
   emission (edge SET is the contract; nx's edge_bfs order is not pinned).
2. Binding: move the kernel's closure DiGraph straight into the PyDiGraph
   (`inner: result`) instead of re-walking edges_ordered() (clones every
   AttrMap) and allocating a PyDict per edge. Edge attr dicts are lazy (missing
   entry reads as empty), and the wrapper copies the original edges' attrs after.
Wrapper: cyclic DiGraphs no longer delegate.

## Proof (behavior parity — absolute)
- 80 random digraphs (self-loops, node+edge attrs, cycles): 0 mismatches across
  class, node set, edge SET, node attrs, edge attrs.
- Golden sha256 over a 5-graph corpus: fnx == nx (`63d6970a`).
- `pytest -k transitive`: 41 passed. reflexive in {True,None} + MultiDiGraph
  (class preserved) + undirected still delegate correctly.

## Result (median-of-3)
| n, m        | nx        | fnx (after) | speedup vs nx |
|-------------|-----------|-------------|---------------|
| 500, 2500   | 1738 ms   | 374 ms      | 4.64x         |
| 800, 4000   | 4645 ms   | 1074 ms     | 4.32x         |

Before: 1.65x SLOWER (delegate + _from_nx_graph rebuild). After: 4.3-4.6x faster.
