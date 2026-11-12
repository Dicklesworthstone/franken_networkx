# perf: bulk incident-edge removal in DiGraph/MultiGraph/MultiDiGraph remove_node

## Lever
DiGraph::remove_node (and the Multi variants) removed each incident edge with a
separate `edges.shift_remove` — and IndexMap shift_remove is O(|E|) — so a single
remove was O(degree*|E|). Replaced with ONE O(|E|) `retain` pass dropping every
incident edge at once (out: node->*, in: *->node); the multigraph variants sum
the removed buckets' lengths into edge_count. Behaviour-preserving: retain removes
exactly the same edges and preserves kept-edge order -> byte-identical graph.

## Correctness
fnx-classes proptests already validate remove_node (prop_remove_node_clears_all_
directed_edges: node gone, no incident edges, core invariants incl. edge_count;
+ DiGraph/MultiDiGraph mixed-mutation invariant proptests). 61 cargo tests pass.
An A/B harness asserted node_count + edge_count identical to the old per-edge
path on the same graph.

## Perf (Rust substrate A/B, release, identical graph, n=1000 m=8000)
DiGraph remove_node x500: OLD 99.0ms -> NEW 49.6ms = 2.0x, byte-exact.
The residual is the OTHER half of the cost: the O(|V|) IndexMap shift_remove on
nodes/successors/predecessors (node-index RENUMBERING), unchanged here — that is
the deeper lever (br-r37-c1-xh7jk: non-renumbering node store, the path to nx's
O(degree) and the full ~51x). This commit removes the per-edge O(degree*|E|)
half; xh7jk removes the renumber half.

(Python-level discovery before: DiGraph remove_node x500 75.7ms = 51x vs nx;
MultiGraph 32.6ms = 24x. The Python-visible improvement is diluted by PyO3
per-call overhead + the unchanged renumber.)
