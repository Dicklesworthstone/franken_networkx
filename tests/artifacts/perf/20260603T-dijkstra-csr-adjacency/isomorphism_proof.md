# Dijkstra integer-adjacency lever — isomorphism proof (br-r37-c1-fwudd)

## Change
`multi_source_dijkstra` (undirected weighted Dijkstra kernel) hot relaxation
loop now iterates **integer neighbor indices** via `graph.neighbors_indices(u_idx)`
instead of `graph.neighbors_iter(name) + graph.get_node_index(v_name)`.

This removes, per directed edge scan (~16k for the BA(2000,4) case):
- one String-keyed `get_node_index` IndexMap lookup, and
- one String-keyed adjacency lookup per finalized node.

The per-edge `edge_weight_or_default(u_name, v_name, weight)` value is unchanged
(node names resolved from `ordered_nodes[idx]`).

## Why output is bit-identical
`adj_indices` is built in the **same insertion order** as the string adjacency
(`adjacency` IndexSet); both push `(left, right)` / `(right, left)` in edge-add
order (see `fnx-classes/src/lib.rs` add_edge / rebuild_adj_indices). Therefore
`neighbors_indices(u_idx)` yields neighbors in the identical order to
`neighbors_iter(ordered_nodes[u_idx])`. Consequences:
- push order into the BinaryHeap is identical → `seq` counter assignment identical
- heap pop order (dist, seq) tie-breaks identical
- finalize (heap-pop) order identical → result dict KEY order identical
- distances and predecessors identical (same weights, same relax order)

CGSE decision recording still receives the same `(chosen, rejected)` node NAMES
(resolved via `ordered_nodes[idx]`); it is a no-op unless witness collection is
enabled, and is unchanged when enabled.

No floating point reassociation; no RNG.

## Golden verification
`dijkstra_parity_golden.py` compares fnx vs networkx across 24 cases
(directed/undirected × weighted/unweighted × N∈{80,300,2000} × 2 sources),
order-sensitive on dict keys and bit-sensitive on distances.

Pre-change and post-change golden digest, both matching networkx exactly:

    DIJKSTRA_GOLDEN 1caf2a5629178e67aa9d0e33c184a2f783a150c6cdeb331b40d5b3dced87a5cb

## Benchmark (criterion, pure kernel, weighted grid n=2025)
Host load on the shared rch worker is high and fluctuates ~2.5x, so absolute
numbers are noisy. Back-to-back same-window pair (most controlled):

    before (neighbors_iter + get_node_index): 14.04 ms
    after  (neighbors_indices):               11.42 ms   → 1.23x

The change does strictly less work per edge (one fewer hashmap lookup) and is
golden-bit-identical, so it cannot regress correctness or, on an unloaded host,
performance.

Opportunity Score = Impact 2 × Confidence 5 / Effort 1 = 10.0.
