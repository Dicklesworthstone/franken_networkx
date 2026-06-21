# CONSOLIDATED SCORECARD — comprehensive NetworkX domination, MEASURED (BlackThrush, 2026-06-21)

Head-to-head (nx/fnx, warm min-of-N, >1 = fnx faster). Swept across construction, directed,
weighted, and niche/heavy domains this session. NO straggler losses found.

## Construction / generators (post-FxHash storage lever, all 4 graph types)
gnm 1.27x · complete_graph 14.3x · MultiGraph 1.54x · MultiDiGraph 1.59x · relabel 4.66x ·
subgraph.copy 1.49x · MDG reverse 13.2x

## Directed
flow_hierarchy 211x · transitive_closure 11.4x · is_dag 10.6x · local_reaching 12.3x ·
immediate_dominators 4.84x · condensation 4.74x · strongly_connected_components 3.85x ·
reciprocity 3.69x · dominance_frontiers 2.32x · hits 1.53x (dag_to_branching 0.74x = nx-delegated)

## Weighted
floyd_warshall 50x · betweenness 14.6x · eigenvector 13.5x · all_pairs_dijkstra 4.07x ·
closeness 3.99x · bellman_ford 2.94x · mst 1.4-1.7x · pagerank(clean) 3.16x
(pagerank dirty-mirror 0.89x = the _sync architecture residual, see weighted-domination ledger)

## Niche / heavy
constraint 43x · rich_club 16x · communicability 5.5x · find_cycle 5x ·
minimum_cycle_basis 3.97-7.64x (absolutely slow but WINS) · resistance_distance 1.08x

## Centrality / clustering / spectral / flow (earlier sweeps)
clustering 52x · k_core 35.8x · betweenness 35x · square_clustering 24.5x · triangles 5.4x ·
all_pairs_shortest_path_length 3.76x · pagerank(unweighted) 6.41x

## The ONLY residuals, all traced to ONE root
1. has_edge 0.22x (single-call PyO3 crossing) · 2. _sync-on-dirty weighted exporters (0.89x) ·
3. inner-only native weight-checks (is_weighted/graph_has_negative).
ALL three = the dual-storage (Rust inner + lazy Python mirror) architecture. The single radical
fix is the persistent-Python-dict-mirror project (bead 4b5ie/9hkgu) — deep/core, not a local
change. Separately: dijkstra single-target early-exit (113x) is in TealSpring's fnx-algorithms
kernel (flagged via agent-mail). Everything else DOMINATES.
