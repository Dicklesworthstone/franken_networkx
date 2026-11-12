# NEGATIVE EVIDENCE — all_node_cuts 0.25x is view-materialization-substrate bound (profiled)

- Agent: `BlackThrush` · 2026-06-21 · (no code change)

## Measured
all_node_cuts(connected_watts_strogatz): n=40 0.51x, n=80 0.24x (GROWS with n). Correct
(#cuts == nx). fnx is a faithful Python port of nx's algorithm (auxiliary node-connectivity
graph -> per (source,target) max_flow -> residual -> transitive_closure + condensation +
antichains -> cut).

## Profile (cProfile, n=80, by tottime)
  0.890s (68%)  _native_adjacency_dict (DiGraph), 307 calls   <-- THE hotspot
  0.101s        _cached_adj_row_keydict (calls the above)
  0.061s        transitive_closure (native, FAST)
  0.045s        maximum_flow (native, FAST)
The flow + closure COMPUTE are fast/native. The cost is materializing the per-flow residual /
transitive-closure DiGraph ADJACENCY (closure.predecessors, condensation): ~2 full-adjacency
materializations per flow x 146 flows. Each ~2.9ms for the dense closure — fnx's PyO3
`{node:{nbr:attrs}}` build is ~4x nx's native dict, so 146x that = the whole gap.

## Why no clean lever
- It is NOT the flow (0.045s) nor the closure compute (0.061s) — both native/fast.
- It is NOT construction order (residual built per-edge could batch, but that is not the hot path).
- It IS the substrate: fnx DiGraph adjacency/view materialization (PyO3 dict crossing) is ~4x
  nx's native dict, and this algorithm materializes 146 dense per-flow closures.
The lever would be a faster `_native_adjacency_dict` (PyO3 attributed-dict build) OR avoiding
the dense transitive_closure entirely (direct backward-BFS ancestors on the residual) — the
latter a moderate, order-sensitive rewrite. Same class affects other view-heavy ports
(greedy_color(smallest_last) 0.75x, treewidth_min_degree 0.78x in this sweep). Domain otherwise
DOMINATED (min_weighted_vertex_cover 6.9x, is_kl_connected 5.6x, flow_hierarchy 992x).
