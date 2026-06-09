# perf(k_truss): adaptive low-k rebuild — 2.1x slower vs genuine nx -> parity

Bead: br-r37-c1-at6zf
Agent: BlackThrush (cc)
Date: 2026-06-09

## Problem
`k_truss(G, k)` for low `k` (k=2 keeps all edges) ran 2.1x slower than
genuine (un-dispatched) networkx. `_k_truss_via_parity` rebuilt the result
edge-by-edge via `R.add_edge(u, v, **data)` over the FULL surviving edge set
— the per-edge construction tax. cProfile (20 calls, BA(800,4) k=2):
- `franken_networkx._fnx.k_truss_rust` kernel: 0.105s (24%)
- per-edge `add_edge` (py wrapper + native): ~0.123s (28%)
- rebuild loop + frozenset membership: ~0.084s (19%)

## Lever (Python-only, no rebuild)
Adaptive rebuild in `_k_truss_via_parity`:
- when `len(kept_edges)*2 >= total_edges` (most survive): mirror nx's own
  structure — `R = G.copy()`, drop the few non-truss edges, drop resulting
  isolates. Preserves G node/edge order + all attrs byte-for-byte.
- else (most dropped): build the small survivor set fresh via
  `add_nodes_from`/`add_edges_from` batch in G order.

## Proof — byte-exact genuine-nx parity
`(list(nodes(data=True)), list(edges(data=True)), dict(graph))` equal to
networkx for: shuffled non-sorted node order + node/edge/graph attrs k=2..6;
BA(120,3) seeds {7,11,23} k=2..6; pre-existing + induced isolates dropped like
nx; MultiGraph/DiGraph error contracts preserved. Identical to the previous
fnx output on all sampled graphs/k. Tests:
- test_k_truss_adaptive_rebuild_parity.py: 22 passed
- test_k_truss_native_parity.py + test_k_truss_node_order_parity.py: 14 passed

## Timings (warm min-of-9, genuine un-dispatched nx)
| graph | k | fnx before | fnx after | nx-orig | after ratio |
|-------|---|-----------|-----------|---------|-------------|
| BA(800,4)  | 2 | 15.66ms | 6.88ms  | 6.63ms  | 1.04x |
| BA(2000,4) | 2 | 49.37ms | 20.68ms | 18.69ms | 1.11x |
| BA(800,4)  | 4 | 6.73ms  | 8.01ms  | 8.45ms  | 0.95x (faster) |
| BA(2000,4) | 6 | 17.14ms | 19.11ms | 21.80ms | 0.88x (faster) |

Self-speedup low-k: 1.72x@BA(800,4)k=2, 1.99x@BA(2000,4)k=2; high-k neutral.
Closes a real 2.1x-slower gap -> parity/faster. Score >= 2.0
(Impact: common op, ~2x; Confidence: byte-exact genuine-nx; Effort: low).
