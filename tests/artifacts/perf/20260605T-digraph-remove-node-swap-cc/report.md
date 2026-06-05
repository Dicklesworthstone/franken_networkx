# perf: O(degree) DiGraph remove_node via swap_remove (nx-parity), + canonical to_undirected

## Lever
After 3a9b16201 DiGraph::remove_node dropped incident edges with an O(|E|)
`retain` scan. But the `edges` IndexMap's ORDER is observed by exactly one
internal consumer (`to_undirected`); every public consumer uses `edges_ordered`
(node->successor order). Canonicalise `to_undirected` to `edges_ordered` (which
ALSO fixes its reciprocal-edge merge order to match networkx — see below), making
the `edges` map order fully unobservable. Then remove each incident edge — known
exactly from successors/predecessors — with O(1) `edges.swap_remove` instead of
the O(|E|) retain scan. remove_node is now O(degree), matching nx.

## Correctness
- 50-graph randomized differential vs networkx (random DiGraphs + random node
  removals): 0 mismatches on node order, edge order, edge attrs, AND native
  strongly_connected_components (which reads successors/predecessors).
- fnx-classes proptests (prop_remove_node_clears_all_directed_edges, mixed-
  mutation invariants, snapshot determinism): 62 cargo tests pass.
- swap_remove reorders the private edges map but G.edges()/all algorithms read
  via edges_ordered (node->successor), so the result is byte-identical.

## Perf
Rust substrate A/B (release, identical n=1000 m=8000 graph): DiGraph
remove_node x500 retain 52.76ms -> swap_remove 7.27ms = 7.3x, byte-exact
(node_count + edge_count asserted equal).
Python end-to-end: DiGraph remove_node x500 75.7ms (original, 51x vs nx) ->
14.76ms (9.63x vs nx). The substrate is now O(degree); the residual ~9.6x is the
PyO3 per-call overhead (node_key_to_string + borrow per remove_node), the same
String-canonicalisation tax that bounds all node-keyed ops.

## Spin-off correctness bug found (filed separately)
The PYTHON-visible to_undirected (binding, TealSpring-locked fnx-python/digraph.rs)
diverges from networkx on RECIPROCAL-edge attrs: 32/60 random cases merge a<->b
with the wrong direction's attrs winning (it uses edges-map order, not nx's
node->successor "latter wins"). The substrate fix here is correct; the binding
needs the same canonicalisation.
