# fix: DiGraph succ/pred row-key objects, z6uka phase 2 (br-r37-c1-z6uka)

## Contract (probed against nx)
- succ[u][v] keeps the v object of the creating add_edge; pred[v][u]
  keeps the u object — ASYMMETRIC for mixed-type self-loops:
  add_edge(12.0, 12) -> succ row 12, pred row 12.0
- edges()/out_edges v-side = succ-row object; in_edges u-side =
  pred-row object (v-side = node object)
- copy(): succ overrides preserved, pred RE-DERIVED with node objects
  (probed: nx copy walks _succ rows; pred cells get node objects)
- reverse(copy=True): succ overrides TRANSPOSE into pred-space
  (rev.pred = src succ overrides; rev.succ empty)
- subgraph/edge_subgraph: filtered succ overrides, pred re-derived

## Implementation
PyDiGraph.succ_py_keys + pred_py_keys (sparse, empty for uniform-key
graphs); add_edge populates new edges; remove_edge/remove_edges_from/
remove_node/remove_nodes_from/clear/clear_edges maintain; render via
py_succ_key/py_pred_key in successors/predecessors/adjacency/
_native_adjacency_dict/_native_edges_* /_native_in_edges_* and
DiAtlasView (AdjKind-aware). digraph_absorb_graph_bidirected bails on
mixed-display sources (Python path records rows correctly).

ALSO FIXES the phase-1 build break at 55e799682: the marker filter
dropped the unmarked `batch_first` declaration in
collect_plain_edge_batch — HEAD did not compile standalone (masked by
testing against the full-checkout-built extension). Declaration and
the display_objs_conflict pub(crate) now carried with markers.

## Proof
- pinned-contract probes: base/reverse/rev-rev/copy/copy-pred-rederive/
  subgraph/removal+readd all match nx
- 25-trial random mixed corpus (int/float/str/bool keys): 0 divergences
- 6 new committed tests (14 total in test_adj_row_key_parity.py)
- full pytest: 21473 passed; 4 failures identical to HEAD
