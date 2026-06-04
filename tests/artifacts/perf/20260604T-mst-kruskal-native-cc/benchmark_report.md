# minimum_spanning_edges — native kruskal for weighted, no graph copy (br-r37-c1-mstcsr)

## Problem
`minimum_spanning_edges` yields edges (no result graph), yet was ~4-5x SLOWER than nx
(n=400: 14ms vs 3ms). Two causes:
1. The WEIGHTED case delegated to networkx (`_call_networkx_for_parity`) — a full fnx->nx
   O(V+E) conversion + nx kruskal — because the native kernel's String-canonical edge
   orientation `(min,max)` flipped tuples vs nx's iteration order and broke tie-breaks.
2. The native (unweighted) path's binding built a *sanitized graph copy*
   (`spanning_input_graph`, O(V+E) construction tax) and used a `HashMap<&str>` union-find.

## Lever (ONE structural)
Make the native kernel reproduce nx's EXACT output, then route the weighted simple-graph case
to it and drop the per-call graph copy:
- Kernel (`fnx_algorithms::minimum_spanning_tree`): collect edges in nx's `G.edges()` order
  and orientation by iterating node *index* order and emitting each edge once from its
  smaller-index endpoint (`s < v`, neighbour order) — reproduces nx's sequence so the
  weight-only stable sort yields nx's exact MST (set, order AND (u,v) orientation). Integer
  union-find over node indices replaces the `HashMap<&str>` String tax.
- Binding (`minimum_spanning_edges`): for the common `ignore_nan=false` path, validate NaN in
  place (same `edges_ordered` scan + message) and run the kernel directly on the original
  graph — no sanitized copy. `ignore_nan=true` keeps the copy (it must DROP NaN edges).
- Wrapper: route `algorithm=="kruskal"`, string weight, simple graph (weighted OR unweighted)
  to the native kernel; multigraph / prim / boruvka / callable weight still delegate to nx.

## Behavior parity (isomorphism proof)
- 120 random graphs × {int-weight ties, distinct floats, float ties, unweighted} × {string
  keys 30%} × {data True/False} = **240/240 exact** (edge values incl. data dicts AND (u,v)
  orientation AND yield order). minimum_spanning_tree (graph) edge set + total weight match.
  NaN weight raises ValueError like nx.
- Golden sha256: `83bffb9d00b06e7351d251efa59035346f7c64d72e4975087ab502a7f2b32058`.
- Tests: `pytest -k "spanning or mst or kruskal or tree_bipartite or new_bindings or
  weighted_sensitivity"` → 492 passed (incl. NaN-message + weighted-MST tests).

## Benchmark (warm min-of-8, ms; weighted gnp)
| n   | networkx | fnx before | fnx after | after vs nx |
|-----|----------|-----------|-----------|-------------|
| 150 | 0.85     | ~3.2      | 0.53      | **1.59x**   |
| 400 | 3.13     | 14.1      | 1.88      | **1.67x**   |
| 800 | 7.12     | ~42       | 7.79      | 0.91x       |

Before: weighted delegated (~4.7x slower). After: 1.6-1.7x FASTER at typical sizes
(~8x self-speedup at n=400); the very-sparse n=800 case is at parity (still ~4x better than
the old path) — the residual is the in-place NaN scan's `edges_ordered` clone + per-edge
weight lookups.

## Score
Impact: high (4.7x-slower -> 1.6-1.7x-faster swing, weighted MST is the common case).
Confidence: high (240-case golden incl orientation/ties/floats/string-keys, 492 tests,
golden sha). Effort: moderate (kernel + binding + wrapper, one lever). → Score >= 2.0.
