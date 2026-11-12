# Negative evidence + measurement correction (BlackThrush, 2026-06-21)

## CORRECTION: deepcopy(DiGraph) is 1.67x, NOT the 0.96x recorded in 787b266aa
The native-deepcopy directed ledger measured deepcopy(DiGraph/MultiDiGraph) using
`fnx.gnm_random_graph(..., directed=True)` as the input — which (bug below) returns an
nx.DiGraph, so that bench compared nx-vs-nx (meaningless ~1.0x). Re-measured on a
DIRECTLY-built fnx.DiGraph (warm min-8):
  deepcopy(DiGraph)      4.84ms vs nx 8.07ms  = 1.67x WIN
  deepcopy(MultiDiGraph) 8.00ms vs nx 10.33ms = 1.29x WIN  (was already a win)
So the native-deepcopy lever flipped ALL FOUR types to wins:
  Graph 4.29x · MultiGraph 3.96x · DiGraph 1.67x · MultiDiGraph 1.29x.

## BUG (deferred): gnm_random_graph(directed=True) returns an nx.DiGraph
It is the ONLY directed generator that leaks an nx type (gnp_random_graph,
erdos_renyi_graph, scale_free_graph, random_k_out_graph all return fnx). Cause: its
wrapper delegates directed via `_call_networkx_for_parity` (built for algorithms; it does
NOT convert generator results to fnx). A native Python directed sampler was written +
verified BYTE-EXACT vs nx 3000/3000 (type+edges+succ+pred+nodes, incl complete/permutations
case) — but REVERTED because it measured 0.75x, blocked entirely by the gap below. Will
re-land once DiGraph construction is fast.

## THE REAL LEVER (scoped): fnx DiGraph batch construction is 4.3x slower than Graph
`DiGraph.add_edges_from(8000 int edges)` = 4.80ms vs `Graph.add_edges_from` = 1.11ms
(4.3x), and 0.83x vs nx's DiGraph. cProfile pins it to the native
`_try_add_edges_from_batch` method on PyDiGraph (~3.7ms of the 4.80ms; add_nodes_from's
per-node loop adds ~1ms). This is a broad lever — it taxes EVERY DiGraph-returning
constructor (directed generators, conversions, operators), not just gnm. NEXT: profile the
PyDiGraph `_try_add_edges_from_batch` Rust kernel (succ+pred CSR build + row-key maps) vs
the faster PyGraph batch; close the 4.3x. Then re-land the gnm directed native sampler
(it will dominate).
