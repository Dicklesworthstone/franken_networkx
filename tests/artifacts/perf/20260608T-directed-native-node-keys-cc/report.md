# _native_node_keys on PyDiGraph/PyMultiDiGraph (br-r37-c1-cijlm)

## Problem
_native_node_keys (all node display objects in ONE PyO3 call) existed only on
PyGraph/PyMultiGraph. non_neighbors + selfloop_edges gate on
`getattr(graph, "_native_node_keys", None)`; for DiGraph/MultiDiGraph the
attribute was absent, so they fell back to the slow path — DiGraph
`set(graph)` (per-node __iter__ PyO3 tax) and MultiDiGraph `set(graph.adj)`
(re-materialises every AdjacencyView row).

## Lever (ONE)
Add the `_native_node_keys` binding to PyDiGraph + PyMultiDiGraph in digraph.rs,
mirroring the lib.rs simple-graph impl (`inner.nodes_ordered()` -> `py_node_key`,
node-insertion order). non_neighbors/selfloop_edges now take the native branch.

## Proof
- Parity: non_neighbors directed 0/360, selfloop_edges directed 0/720 (incl
  MultiDiGraph, data/keys variants). type(node) preserved (int stays int).
- Test suite: 2039 passed, 2 skipped (non_neighbor/non_edge/selfloop/digraph).
- Self-speedup vs the PRIOR fnx path (n=2000, x50, interleaved min-of-7):
  - DiGraph non_neighbors: set(graph) 57.2ms -> native_keys 26.7ms = 2.15x
  - MultiDiGraph non_neighbors: set(graph.adj) 3046ms -> 27.1ms = 112.6x
    (the AdjacencyView-rematerialization trap, eliminated)

## Residual (follow-up, separate bead)
vs nx, directed non_neighbors is still ~16-22x slower: py_node_key reconstructs
each int node object from the canonical String key (node_key_map lookup) per
node, while nx iterates pre-existing dict keys. A cached/bulk-int node-key path
(invalidated by nodes_seq) is the substrate lever to close the nx gap.
