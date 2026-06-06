# br-r37-c1-s0d4x — same-type ctor native absorb + multi-class copy walk order

## Gap (warm min-of-5 matrix, /data/tmp/fnx_ctor_check.py)
DiGraph(DiGraph) 4.44x/4.97x (n=800/3000); Graph(Graph) 1.45-1.71x;
Graph(DiGraph) 2.6-3.3x. Profile: _copy_constructor_graph_source re-adds
every edge via the Python walk.

## Lever: route exact-same-type ctor to the native copy
nx cls(G) structure == G.copy() (probed all 4 classes: nodes, edges+data,
adj/pred rows, graph attrs, shallow attr-dict copying). New
_fnx_absorb_copy pymethod (*self = other.copy()) + exact-type gate in
_copy_constructor_graph_source (pattern: digraph_absorb_graph_bidirected
wholesale replace), **attr applied after like nx.

## Latent bug found and fixed (the absorb's proof corpus caught it)
MultiGraph/MultiDiGraph copies kept verbatim insertion-order adjacency
CELLS where nx's copy walk reorders them u-major (the 0ek49 fix covered
only Graph/DiGraph; multi probes were too weak — needed mixed str/int
nodes + parallel keys + density). Added
MultiGraph::reorder_rows_for_nx_copy_walk +
MultiDiGraph::reorder_pred_rows_for_nx_copy_walk, called from
copy()/_native_copy.

## After
DiGraph(DiGraph) 1.95x/2.23x; Graph(Graph) 0.89-1.19x (~parity);
DiGraph(Graph) ~1.17x. Residual = copy()'s attr deep-copies.
Graph(DiGraph) 2.3-3.2x = cross-type collapse, follow-up.
Score: 4.97 -> 2.23 self-speedup ~2.2x + correctness fix => >=2.0.

## Proof
- 60-graph corpus x 4 classes: ctor parity, copy parity, copy-of-copy
  fixed point, ctor independence — CLEAN.
- metamorphic 4x1500 CLEAN; 251 focused tests; 8 new committed tests;
  full pytest 21576 passed, 0 failed.
