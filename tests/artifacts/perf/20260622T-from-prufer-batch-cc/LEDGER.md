# from_prufer_sequence batch construction (br-r37-c1-pruferbatch, cc)

from_prufer_sequence built the tree with per-node add_node + per-edge add_edge loops after the native kernel computed the edges (construction tax — PyO3 boundary per element). Batched to add_nodes_from(range(n)) + add_edges_from(edges).

0.35x -> 1.83x (n=400 tree, warm; fnx 0.265ms / nx 0.480ms). Byte-identical: nodes 0..n-1, edge order = kernel order; 0 fails / n=2..400 x seeds vs the loops AND vs networkx; invalid-seq NetworkXError contract preserved. Full suite 49239 passed, same 5 pre-existing.
