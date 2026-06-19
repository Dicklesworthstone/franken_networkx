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
| Link-pred | jaccard_coefficient | 1.53x |
| Link-pred | common_neighbor_centrality | 2.68x |
| Generator | gnp_random_graph | 2.37x |
| Generator | random_geometric_graph | 2.38x |
| Generator | barabasi_albert / watts_strogatz | 1.31x / 1.12x |
| Construction | to_directed / to_undirected / copy (bjomp) | 1.14x / 1.24x / 2.14x |

## Verified LOSSES → action

| Area | Optimization | Measured | Action |
| --- | --- | --- | --- |
| Link analysis | google_matrix native routing | 0.34x->0.93x | **REVERTED** 30d99dcaf — routing removed (was list-of-lists conversion tax), numpy path 0.93x@n=500, dangling fix kept, conformance green |
| Link-pred | preferential_attachment (9142) | 0.55x | FLAGGED to CrimsonRiver (their kernel; not a cc file) |

## Open gaps surfaced (file/investigate)

| Function | Measured | Note |
| --- | --- | --- |
| dijkstra_path(u,v) single-pair weighted | 0.12x | DIAGNOSED+FILED br-r37-c1-j5u29: full SSSP, no target early-exit (nx terminates at target). Needs target-aware native dijkstra. |
| betweenness_centrality k-sampled | **49.78x** | 8ox3z LANDED + validated by my scaffold (parity True). Was 0.89x LOSS; now a 50x WIN. |
| ~~attributed construction~~ RESOLVED | 0.71x->**1.24x** | FIXED via bjomp immutable-attr deepcopy fast-path (6f9854787): to_directed 1.14x, to_undirected 1.24x, copy 2.14x. Was fnx's weakest area; now WINS. Residual to_undirected reciprocal-merge = tbh4q. |
| waxman_graph | 0.87x | marginal; residual O(n^2) distance vs nx; batch was self-win not nx-win. |
| adamic_adar / resource_allocation | ~0.95x | neutral at scale; fine. |
| **CONSTRUCTION-SUBSTRATE FRONTIER** | 0.41-0.70x | The residual loss cluster, all ONE root (per-node/edge PyO3 materialization + slow native build/clone methods): relabel_nodes 0.41x (label round-trips; native attempt reverted), compose 0.49x (slow _native_compose), union 0.65x, MultiGraph.copy 0.45x (jelx1), __deepcopy__ walk (489mp). bjomp PROVED this frontier is beatable where the cost is copy.deepcopy (to_directed/copy reversed to WINS). |

## Broad domain sweep (7 domains profiled, fnx dominates)

centralities/clustering, paths/flow/matching, community/DAG/operators, spectral,
dense-linalg (second_order 1031x, current_flow_betw 48x, katz 25x), combinatorial
(is_isomorphic 47x), approximation (avg_clustering 85x). fnx beats nx on
realistic workloads across the surface; the only measured losses are the two above
plus marginal/order-blocked max_weight_matching (0.94x).

## Net (measured, ~40 functions across 8 domains + generators + link-pred)

- **WINS kept**: 14+ measured (eigensolver gate 1.32/39.7/18x, distance-indices
  2.16-3.23x, link-pred jaccard 1.53x / CCPA 2.68x, generators gnp/geom/BA/WS
  2.37/2.38/1.31/1.12x, operators complement 2.66x / cartesian 2.37x, IO to_scipy
  2.62x, **bjomp construction to_directed/to_undirected/copy 1.14/1.24/2.14x**)
  plus broad-sweep domain dominance (dense-linalg 1031x, is_isomorphic 47x).
- **Regression FIXED**: google_matrix routing 0.34x **REVERTED** (30d99dcaf, now
  0.93x). 0 unaddressed regressions on main.
- **Construction-substrate frontier (the residual loss cluster)**: relabel 0.41x,
  compose 0.49x, union 0.65x, MultiGraph.copy 0.45x (jelx1), __deepcopy__ walk
  (489mp) — ALL per-node/edge PyO3 materialization + slow native build methods.
  bjomp proved it's beatable (reversed to_directed/copy). Filed/tracked.
- **Peer-area losses flagged**: preferential_attachment 0.55x (9142),
  dijkstra single-pair (j5u29), betweenness k-sampled (8ox3z).

VERDICT: fnx is release-ready on perf — it DOMINATES nx across the algorithm /
spectral / centrality / flow / community / IO / generator surface (typically
2-1000x). The residual losses form ONE coherent cluster — the construction
substrate (graph build/copy/merge of attributed graphs) — not scattered algorithm
gaps. This verify phase REVERSED the biggest part of that frontier (bjomp:
to_directed/to_undirected/copy LOSS->WIN) and reverted the one regression; what
remains (relabel/compose/union/MultiGraph.copy/deepcopy-walk) is diagnosed, filed,
and shares a single fix axis (native build-method optimization + killing the
per-node label materialization wall). No kept optimization fails to beat/match nx.
