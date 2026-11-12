# perf: incremental index maintenance in Graph::remove_node (br-r37-c1-rmnode)

## Lever
`Graph::remove_node` called `rebuild_adj_indices()` + `rebuild_edge_index_endpoints()`
on EVERY removal — two O(|E|) passes each doing a `nodes.get_index_of()` HashMap
lookup for every neighbour of every node and every edge. So a single remove was
O(|V|+|E|)-WITH-HASHING and `remove_nodes_from` was O(k*(|V|+|E|)).

Replaced with: (1) remove ALL incident edges from `edges` + the parallel
`edge_index_endpoints` in ONE O(|E|) `retain` pass (sharing a keep-mask), instead
of O(degree*|E|) per-edge `shift_remove`; (2) repair the integer caches in place —
drop dangling refs to the removed index and decrement indices that shifted down —
NO hashing, NO full rebuild.

## Correctness (byte-exact)
40 randomized trials (random graphs, random node-removal subsets) vs networkx:
0 mismatches on node order + edge order + edge attrs + degrees, AND native
`triangles` (which reads the `adj_indices` CSR cache) stays correct after removal
— proving the integer caches are repaired correctly. golden sha 5efe6826.
fnx-classes cargo 61 passed; full Python suite: see log.

## Perf (warm min, isolated removes, n=1000 m=8000)
remove_node x500: ~563ms (before) -> 116.6ms (after) = ~4.8x self-speedup,
byte-exact. (build-only 43.6ms is unchanged; the discovery baseline build+500
removes was 607ms.)

## Honest residual / next lever
remove_node is STILL O(|V|+|E|) per call (so bulk is O(k*(|V|+|E|))) vs nx's
O(degree): the IndexMap `shift_remove` RENUMBERS all node indices > idx, forcing
the decrement pass. Matching nx's O(degree) needs a NON-RENUMBERING node store
(generational slot-map / tombstones + lazy compaction, or a lazy cache rebuild
behind a dirty flag — currently blocked by the `&self` `neighbors_indices` API +
no-unsafe + locked fnx-algorithms callers). Filed as a follow-up. Same rebuild
pattern likely affects DiGraph/MultiGraph remove_node + clear_edges (11x).
