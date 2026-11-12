# average_degree_connectivity — directed + weighted fast paths → all cases now beat nx

Bead: br-r37-c1-9d98t
Agent: cc (CopperCliff)
Date: 2026-06-20

## Problem

Only the simple undirected-unweighted case had a native fast path. Everything
else fell through to a fallback that recomputed `_adc_weighted_degree` per source
node AND per neighbour inside the inner sum — O(E·avg_deg) AtlasView degree
walks. Measured (n=1500 gnp):

| case                       | fnx     | nx     | ratio  |
|----------------------------|---------|--------|--------|
| directed in+out (unw)      | 726 ms  | 9 ms   | 0.013x |
| directed in/out (unw)      | 54 ms   | 5.6 ms | 0.104x |
| undirected weighted        | 454 ms  | 17 ms  | 0.038x |
| directed weighted (in/out) | 70 ms   | 18 ms  | 0.255x |

## Fix (same lever as node_degree_xy wqhqr — bulk reads, order-invariant)

The result is a per-degree-bucket **sum** dict, so neighbour order is irrelevant.

1. **Memoize `target_degree`** in the generic fallback — each node's target
   degree computed at most once (collapses O(E·deg) → O(V·deg)). Byte-identical;
   covers multigraph / nbunch subset.
2. **Directed unweighted fast path**: unweighted degree dicts come from the FAST
   native views (`dict(degree())` ~0.4ms); neighbours from one
   `_native_adjacency_keys()` successor snapshot (inverted in O(E) for
   `source="in"` — order-free). O(V+E) dict lookups.
3. **Undirected weighted fast path**: one `_native_adjacency_dict()` snapshot
   ({n:{nbr:attrs}}); unweighted degree map from `dict(degree())`; the weighted
   source degree is **derived from the snapshot** (avoids the slow
   `degree(weight=...)` view, ~11ms). Self-loop weight doubles in the weighted
   degree, counted once in the inner sum — matches nx.
4. **Directed weighted fast path**: same, with predecessor inversion only when
   `source` touches in-edges (`source="out"` skips it).

## Proof

- `bench_and_parity.py` (this dir): **1500 value-parity checks, 0 fails** —
  all source×target×weight combos, self-loops, missing weights (default 1),
  empty/degenerate graphs, directed + undirected. Golden sha256
  `d82e8fa9adcc0187ae7a4c9e9510fa9cf481dcb6c016b749f450af7ba8a82bb6`.
- Conformance: 1853 passed in the `connectivity/assort/neighbor_degree/
  average_degree` family (excluding the pre-existing, unrelated `node_connectivity`
  Menger failures — confirmed failing on clean HEAD before this change).

## Timing (min-of-6, warm; run.log in this dir)

| case               | before  | after   | nx      | after vs nx |
|--------------------|---------|---------|---------|-------------|
| dir in+out (unw)   | 726 ms  | 2.6 ms  | 6.2 ms  | **2.37x**   |
| dir in/out (unw)   | 54 ms   | 3.7 ms  | 5.3 ms  | **1.46x**   |
| undir weighted     | 454 ms  | 7.3 ms  | 13.9 ms | **1.91x**   |
| dir wt out/in      | 70 ms   | 10.0 ms | 13.4 ms | **1.34x**   |
| dir wt in/out      | 70 ms   | 13.0 ms | 16.3 ms | **1.25x**   |
| dir wt in+out      | ~70 ms  | 15.4 ms | 16.2 ms | **1.05x**   |
| undir unweighted   | (native)| 2.5 ms  | 6.3 ms  | 2.49x       |

Pure-Python change scoped to `average_degree_connectivity`. No Rust/kernel change.
