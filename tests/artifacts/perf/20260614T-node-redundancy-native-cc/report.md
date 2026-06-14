# Native bipartite node_redundancy — delegated → ~0.015x (≈65x faster than nx)

Bead: br-r37-c1-g6wla
Agent: cc / 2026-06-14

## Problem

`fnx.bipartite.node_redundancy` was re-exported from networkx
(`@nx._dispatchable`), so calling it on an fnx graph did a full `_fnx_to_nx`
conversion then ran nx's per-node `_node_redundancy`, which for every node counts
the neighbour pairs `{u,w}` sharing another common neighbour via Python
`set(G[u]) & set(G[w])` intersections. ~1.16x slower than nx and bound to nx's
slow set arithmetic.

## Fix (native integer-CSR overlap-count kernel)

`rc(v) = 2·overlap(v) / (deg(v)·(deg(v)-1))` where `overlap(v)` is an **integer
graph invariant** (a pair count, order-independent). Added a native kernel
`_fnx.node_redundancy_overlaps(G)` (crates/fnx-python/src/lib.rs) returning
`(overlap, deg)` per node in node order, computed over the integer CSR adjacency
(`neighbors_indices`) with a reusable mark array and **early exit**: for each
ordered neighbour `u` of `v`, mark `N(u)\{v}`, then for each later neighbour `w`
test whether any node of `N(w)` is marked (stop at the first hit). The Python
wrapper performs nx's exact float division `(2*overlap)/(deg*(deg-1))`, so the
result is byte-identical, and raises nx's exact `NetworkXError` when any node has
`deg < 2`. Directed / multigraph / nx-typed / explicit-`nodes` inputs delegate.

## Proof

- 60-seed random bipartite-graph sweep (default `nodes=None`): result `== nx`
  AND `repr == nx` (dict key order matches) — **0 value, 0 key-order mismatches**.
- Error parity: a graph with a degree-1 node raises the identical
  `NetworkXError("Cannot compute redundancy coefficient for a node that has
  fewer than two neighbors.")`.
- `cycle_graph(4)` → `{0:1.0,1:1.0,2:1.0,3:1.0}` (==nx, matches docstring).
- Golden (davis_southern_women): `repr` sha256 `b21fd613827564a7…`, equals nx.
- Full suite (remote, kernel confirmed present): 22265 passed, only the 6 known
  pre-existing failures.

## Timing (min-of-8)

| size (top×bottom/edges) | before (delegated) | after (fnx) | nx | now vs nx |
|-------------------------|--------------------|-------------|-----|-----------|
| 150×120 / 1200 | ~12ms (≈1.16x) | 0.20ms | 12.2ms | **0.016x (≈61x)** |
| 300×250 / 3000 | — | 0.59ms | 41.7ms | **0.014x (≈71x)** |

Native integer-CSR mark-array counting with early exit replaces nx's per-pair
Python set intersections; ~65x faster, byte-exact. Score ≫ 2.0. Kernel placed in
fnx-python/lib.rs (algorithms.rs was peer-reserved by BoldFalcon).
