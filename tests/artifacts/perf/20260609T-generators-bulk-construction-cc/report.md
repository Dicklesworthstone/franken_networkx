# generators: bulk node+edge construction (extend_*_unrecorded) — cycle/path now FASTER than nx (br-r37-c1-cyclebulk)

## Problem
Generator kernels in fnx-generators built graphs with per-node graph.add_node and
per-edge graph.add_edge, EACH recording a RuntimePolicy decision (the native
construction tax). RELEASE: cycle_graph 2.07x, ladder/circular_ladder ~1.85x slower
than nx. (The generator->PyGraph conversion generators.rs:21 is already zero-copy.)

## Lever
1. graph_with_n_nodes: bulk extend_nodes_unrecorded instead of per-node add_node
   (shared by ALL undirected generators).
2. cycle_graph / ladder_graph / circular_ladder_graph: collect edges into a Vec in
   the EXACT same emission order, then one extend_edges_unrecorded. Order is
   preserved so every node's adjacency row (G[u]) is byte-identical (these
   generators have no apply_row_orders; row order = emission order).

## Proof
- Parity vs nx 0 mismatches (nodes + per-node adjacency rows) across cycle/ladder/
  circular_ladder/path/star/wheel x n in {1,2,3,5,8,50,500}; pytest -k generator/
  cycle/ladder/path 2079 passed.
- RELEASE (min-of-20): cycle(4500) 2.07x -> 0.65x (FASTER); path(5000) -> 0.59x
  (FASTER, via node bulk); ladder(2000) 1.85x -> 1.45x; circular_ladder 1.83x -> 1.45x.
