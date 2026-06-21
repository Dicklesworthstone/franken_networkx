# REGRESSION FIX — graph_has_edge_attr lazy-mirror false-negative (br-r37-c1-hasattrlazyfix)

- Agent: `BlackThrush` · 2026-06-21 · File: `__init__.py` · fixes MY own br-r37-c1-hasattrnative (3cf685558)

## The regression I introduced
br-hasattrnative routed `_graph_has_edge_attribute` through the native `graph_has_edge_attr`,
which scans the Rust-side `edge_py_attrs` MIRROR. That mirror is LAZY: a freshly batch-built
graph (add_edges_from / DiGraph(G)) has it unmaterialized, so the native returns False even
when the attr IS present. Effects:
- second_order_centrality(weight='weight') on a fresh weighted graph mis-gated to the
  UNWEIGHTED Rust kernel -> centrality off by ~17 vs nx (test_second_order_centrality_
  woodbury_parity, 2 failing). (cost dodged it — the gate is `weight=='weight'`.)
- the weighted-dijkstra / MST delegation gates could mis-route a lazy weighted graph.
Verified: `_graph_has_edge_attribute(fresh_batch_weighted_Gf,'weight')` returned False (bug);
the Python `G.edges(data=True)` scan returns True (correct, it materializes).

## The fix
- `_graph_has_edge_attribute`: trust ONLY a native True (the attr is really there); on
  False/None fall back to the correct `G.edges(data=True)` scan (which materializes). Keeps
  the fast path for already-materialized weighted graphs; pays the scan otherwise.
- second_order_centrality: build the transition matrix directly in numpy from
  `G.edges(data=True)` (robust — independent of the lazy in_degree/to_numpy fast paths).

## Verify
- pytest second_order woodbury 7/7; second_order broad 600/600 (weight/cost/None);
  pytest -k 'dijkstra/voronoi/spanning/mst/size/has_edge_attr/weighted' 4544 passed, 0 failed.

## Perf note
The br-hasattrnative speedup (voronoi 0.66x->1.06x; dijkstra gate 420us->0.1us) is RETAINED
only for already-materialized weighted graphs; an unweighted / lazy graph now pays the scan
again. The proper way to keep BOTH correctness and speed is to make the native binding read
the Rust INNER edge attrs (which `edges(data=True)` reads correctly) instead of the lazy
edge_py_attrs mirror — a Rust follow-up. Correctness > the partial perf regression.
