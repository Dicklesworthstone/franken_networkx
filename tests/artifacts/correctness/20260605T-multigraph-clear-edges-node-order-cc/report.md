# fix: MultiGraph/MultiDiGraph.clear_edges() preserves node insertion order

br-r37-c1-pb8bj. PyMultiGraph::clear_edges / PyMultiDiGraph::clear_edges reset the
inner graph then re-added nodes by iterating `self.node_key_map.keys()` — a
HashMap, whose iteration order is RANDOM. So after clear_edges() the node order
was scrambled vs networkx, which preserves insertion order (it only drops edges).
Graph/DiGraph were already correct (they remove edges in-place, never touching the
node store).

Fix: capture `self.inner.nodes_ordered()` (insertion order) BEFORE resetting
inner, then rebuild the fresh inner in that order. node_key_map / node_py_attrs
unchanged.

Proof: clear_edges_parity_proof.py — 1600 cases (all 4 graph classes x random
node sets + edges + node/graph attrs) vs networkx: 0 mismatches on node order,
edges-cleared, node attrs, graph attrs, number_of_edges, copy()-after-clear node
order, and re-adding edges afterward.

Repro (before): MultiGraph nodes [5,3,8,1,9,2,7] -> after clear_edges [1,5,9,2,8,7,3]
(nx stays [5,3,8,1,9,2,7]).
