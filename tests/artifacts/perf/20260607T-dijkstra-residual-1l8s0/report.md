# dijkstra residual (br-r37-c1-1l8s0): multi_source kernel accessor audit
The 1.33x dijkstra-len residual was the multi_source_dijkstra kernels
(which the with_pred length path calls) still fetching edge weights by
NAME — the accessor audit had reached the CSR builders but not these
in-loop relaxation fetches.

## Fixes
- undirected multi_source_dijkstra: edge_attrs_by_indices in the relax
  loop (was edge_weight_or_default by name = 2 node probes/relaxation).
- directed multi_source_dijkstra: walk succ_indices directly (new
  successors_indices/predecessors_indices slice accessors) — drops
  successors_iter name iteration AND get_node_index-per-edge.

## Result (same window)
dijkstra_len directed 1.33x -> 0.85x (FASTER than nx)
dijkstra_len undirected 1.13x
multi_source_dijkstra directed 2.11x -> 1.46x

## Rejected (reverted): wrapper raw-binding fast-path
Routing all-int length queries to the raw with_pred binding broke
cutoff parity — post-hoc v<=cutoff filter diverges from nx's in-search
cutoff on NaN/inf edges (2 suite failures). The win was the kernel
fetches, not the wrapper bypass; reverted.
