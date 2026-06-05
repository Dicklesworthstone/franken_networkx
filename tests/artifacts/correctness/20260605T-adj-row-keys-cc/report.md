# fix: per-adjacency-row display-key objects, PyGraph phase 1 (br-r37-c1-z6uka)

## Bug (architectural)
nx's `_adj[u]` dict keeps the py object passed in the call that CREATED
each cell — divergent from `_node`'s global first-wins object when
hash-equal keys of different types mix (28 vs 28.0 vs True). fnx had ONE
display object per node, so adjacency rows / neighbors / edge-tuple
v-sides rendered the wrong object (shrunk: add_edge(36,16.0);
add_edge('n58',16) -> g['n58'] showed 16.0, nx 16).

## Fix
- sparse `PyGraph.adj_py_keys: HashMap<(owner, nbr), PyObject>` — entry
  only when the cell object differs from what py_node_key renders
  (identity, then type+eq for un-interned values); EMPTY for every
  uniform-key graph (is_empty fast-out on render paths; str keys skip
  the probe entirely — their canonical namespace cannot collide)
- populate: add_edge (new edges; SELF-LOOP keeps only v's object — nx's
  reverse assignment cannot replace the hash-equal dict key); batch
  collects BAIL to the per-edge path on mixed-display input
- maintain: remove_edge/remove_edges_from/remove_node/remove_nodes_from
  drop touched entries; clear/clear_edges clear
- propagate: copy()/subgraph()/edge_subgraph() use
  derive_copy_adj_py_keys — nx's u-major add_edges_from walk semantics
  (first-encountered direction keeps the source row object; the reverse
  cell is re-created with the node object — verified nx.copy() itself
  re-derives, it does NOT preserve source row objects); __copy__
  (shallow) clones the map (copy.copy shares structure)
- render: edge_alldata_items v-side, EdgeView tuple builders (x3),
  AtlasView materialize/__iter__/items, PyGraph adjacency(), neighbors()

## Proof
- pr8q6 90-case differential: 10 failures at HEAD -> 0 (golden corpus
  sha 275c260d... UNCHANGED — uniform-key cases bit-identical)
- nlanb 51-case from_dict_of_dicts differential: 12 -> 0
- 8-test committed suite: shrunk repros, self-loop mixed types, batch
  bail, removal+re-add reset, copy/subgraph derive semantics,
  remove_node cleanup, uniform-graph no-op
- full pytest: 21467 passed; pre-existing failures 6 -> 4 (the two
  MultiGraph/MultiDiGraph stateful-fuzz failures were this bug class
  surfacing through shared paths and now PASS)
- uniform-graph construction within noise (2.82x-range preserved;
  str-keyed batches skip the probe)

## Scope
Phase 1 = PyGraph. PyDiGraph succ/pred + Multi variants are phase 2
(same recipe; bead updated).
