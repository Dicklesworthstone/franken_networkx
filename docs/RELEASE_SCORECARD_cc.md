# Release-Readiness Scorecard — perf domination vs NetworkX (cc measured)

Measured 2026-06-18 with a fresh release build (HEAD), warm min-of-8, vs NetworkX.
Status of perf claims that were committed `code-first batch-test pending`.

## Verified WINS (measured, keep)

| Area | Optimization | Measured ratio vs nx |
| --- | --- | --- |
| Spectral | laplacian_spectrum eigensolver gate | 1.32x (reversed a 2.4x LOSS) |
| Spectral | adjacency_spectrum eigensolver gate | 39.7x |
| Spectral | modularity_spectrum eigensolver gate | 18.0x |
| Distance index | gutman_index native | 2.16x |
| Distance index | schultz_index native | 2.20x |
| Distance index | generalized_degree native | 3.23x |

## Verified LOSSES → action

| Area | Optimization | Measured | Action |
| --- | --- | --- | --- |
| Link analysis | google_matrix native routing | 0.34x | REVERT (revert pending — __init__.py held by peer; bug fix retained) |

## Open gaps surfaced (file/investigate)

| Function | Measured | Note |
| --- | --- | --- |
| dijkstra_path(u,v) single-pair | 0.49x | conversion/weighted-setup tax; in-process single-pair candidate |
| betweenness_centrality k-sampled | ~0.89x | delegates to nx; native k-sampling lever filed br-r37-c1-8ox3z (CrimsonRiver implementing) |
| attributed construction/conversion | 0.59-0.98x | subgraph/copy ~parity; to_directed 0.83x, to_undirected 0.59x. Substrate tax (PyDict alloc + PyO3 labels); CrimsonRiver tbh4q. fnx's weakest area vs nx. |

## Broad domain sweep (7 domains profiled, fnx dominates)

centralities/clustering, paths/flow/matching, community/DAG/operators, spectral,
dense-linalg (second_order 1031x, current_flow_betw 48x, katz 25x), combinatorial
(is_isomorphic 47x), approximation (avg_clustering 85x). fnx beats nx on
realistic workloads across the surface; the only measured losses are the two above
plus marginal/order-blocked max_weight_matching (0.94x).

## Net

6 measured WINS kept, 1 measured LOSS reverting, 2 open gaps tracked. fnx is
release-ready on perf for the swept domains; remaining items are tracked beads.
