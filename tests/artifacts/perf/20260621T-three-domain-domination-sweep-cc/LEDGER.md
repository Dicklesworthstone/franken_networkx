# VERIFICATION — three fresh domains swept, comprehensively DOMINATED (MEASURED)

- Agent: `BlackThrush` · 2026-06-21 · warm min-of-N, taskset -c 2, PYTHONHASHSEED=0

## Wins (nx/fnx, >1 = fnx faster)
community/matrix:  greedy_modularity 24.8x, louvain 21.2x, incidence_matrix 8.9x,
                   adjacency_spectrum 5.8x, modularity_matrix 3.0x, johnson 1.8x,
                   floyd_warshall_numpy 1.5x, label_propagation 1.5x, could_be_isomorphic 1.3x,
                   modularity(partition) 1.3x
dag/tree/travers:  is_forest 150.9x, is_tree 36.3x, lowest_common_ancestor 10.5x, bfs_tree 5.8x,
                   dfs_tree 4.6x, descendants 3.2x, ancestors 2.7x, dag_longest_path 2.4x,
                   dfs_preorder 2.1x, descendants_at_distance 1.9x, topological_generations 1.8x
coloring/approx:   flow_hierarchy 992x, min_weighted_vertex_cover 6.9x, is_kl_connected 5.6x

## Losses — ALL substrate-bound / fragile / parity-locked (no clean lever)
- all_node_cuts 0.25x: view-materialization substrate (_native_adjacency_dict ~4x nx), profiled
  in 20260621T-all-node-cuts-substrate-noship-cc.
- non_randomness 0.80x: LOCKED — intentionally calls nx's label_propagation for the community-
  count k (coverage-matrix PY_WRAPPER lock) so it pays a fnx->nx conversion; the eigvals(adj)
  order matches nx and CANNOT switch to the faster symmetric eigvalsh (would reorder eigenvalues[:k]
  and diverge). ~13ms = the unavoidable parity conversion.
- center 0.80x / dominating_set 0.72x: already-optimized (br-r37-c1-eccallpairs / -lj6bo); residual
  is per-node view-access substrate.
- greedy_color(smallest_last) 0.75x / treewidth 0.78x: same view substrate / set-order-locked.
- simrank/panther/weisfeiler_lehman: parity (0.96-0.98x).

## Conclusion
The non-substrate surface is comprehensively DOMINATED across every domain swept this session.
The single remaining perf lever is the VIEW/ADJACENCY MATERIALIZATION substrate (PyO3 dict
crossing ~4x nx native dict, bead 4b5ie/9hkgu — needs a persistent ordered Python node/adj
mirror); a deep, order-sensitive native change, not a quick win. No regressions; nothing to ship.
