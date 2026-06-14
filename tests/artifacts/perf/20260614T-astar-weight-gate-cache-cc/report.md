# astar_path / astar_path_length — 2.6x slower → 0.88-0.94x (beats nx), ~2.7x self

Bead: filed this turn (br-r37-c1-ixp5q)
Agent: cc / 2026-06-14

## Problem (found via pairwise/2-arg exhaustive scan)

`astar_path` on a weighted graph was **2.37-2.62x slower than nx** (a real
algorithm gap, not construction/parity-locked). cProfile of a weighted
single-pair call (n=1000):

| component | ms |
|-----------|-----|
| `_has_negative_edge_weight` scan | 0.90 |
| `_has_positive_infinity_edge_weight` scan | 0.45 |
| `_has_nonnumeric_edge_weight` scan | 0.44 |
| **3 weight-validity scans total** | **1.78** |
| native `_raw_astar_path` kernel | 1.05 (≈ nx 1.10) |

The native kernel is already at nx parity; the **3 separate, uncached O(\|E\|)
weight-validity scans** were pure per-call overhead.

## Fix (reuse dijkstra's cached, fused, sync-free gate)

dijkstra already solved this: `_should_delegate_dijkstra_to_networkx` calls
`_native_check_dijkstra_weights_fast` (one pass returning
`(has_negative, has_nonfinite, has_nonnumeric)` directly off `edge_py_attrs`, no
sync) and **memoizes the result in `vars(G)` keyed by the revision token**
(`_native_dijkstra_weight_cache_token` → nodes_seq/edges_seq/edge_attrs_dirty).
astar reinvented the gate with three uncached scans + a sync. Routed both
`astar_path` and `astar_path_length` through the existing cached gate; kept the
edges-dirty-guarded kernel sync. One lever, ~10 lines, pure-Python.

Behavior: identical delegation for negative/±inf/nonnumeric; **nan-weighted
edges now delegate to nx** (dijkstra's `nonfinite` flag includes nan) — strictly
more correct than the old silent native run on an unordered-comparison weight.

## Proof

- 240-case parity sweep (40 seeds × 3 random pairs × {astar_path,
  astar_path_length}, weighted/unweighted/directed) — **0 mismatches** vs nx.
- Negative-weight graph still delegates correctly (path == nx).
- Golden (gnp 200,0.05,seed=7; 10 paths to node 199): sha256 `78e333bb6b4f3c99…`,
  equals nx.
- Full suite: only the 6 known pre-existing failures.

## Timing (min-of-20, repeated single-pair on the same graph)

| op | before | after | nx | now vs nx |
|----|--------|-------|-----|-----------|
| astar_path (n=300, weighted) | 2.37x | 0.371ms | 0.421ms | **0.88x** |
| astar_path (n=1000, weighted) | 2.62x | 1.089ms | 1.160ms | **0.94x** |

~2.7x self-speedup; astar now beats nx. The cached gate makes repeated
shortest-path queries on a graph free of the weight-validity rescan.
