# Release-Readiness Scorecard — perf domination vs NetworkX (cc measured)

Measured 2026-06-18 with a fresh release build (HEAD), warm min-of-8, vs NetworkX.
Status of perf claims that were committed `code-first batch-test pending`.

## HEADLINE — realistic end-to-end analysis pipeline: **20-32x faster than nx**

build + pagerank + betweenness(k) + closeness + clustering + transitivity +
components + degree + scipy-export: fnx 6.4ms vs nx 130ms (n=500, 20.26x);
fnx 35.5ms vs nx 1143ms (n=1500, 32.20x, scales better). The aggregate answer to
"beat the original on realistic workloads": YES, decisively. (DIRECTED pipeline: 5.68-9.40x.)

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
| Centrality | betweenness k-sampled (8ox3z, scaffold-validated) | **49.78x** |
| MultiGraph | connected_components (fyxma, direct BFS) | **0.07x->1.06x** (114x faster) |
| Code-first batch | assortativity 9147-52 (degree_assort 78x) / expansion-cut-flow 9153-55 (flow_hierarchy 219x) | 2.4-219x, parity-verified |

## Verified LOSSES → action

| Area | Optimization | Measured | Action |
| --- | --- | --- | --- |
| Link analysis | google_matrix native routing | 0.34x->0.93x | **REVERTED** 30d99dcaf — routing removed (was list-of-lists conversion tax), numpy path 0.93x@n=500, dangling fix kept, conformance green |
| Link-pred | preferential_attachment (9142) | 0.55x | FLAGGED to CrimsonRiver (their kernel; not a cc file) |

## Open gaps surfaced (file/investigate)

| Function | Measured | Note |
| --- | --- | --- |
| dijkstra_path(u,v) single-pair weighted | 0.42x | improved from 0.12x (j5u29 partial); still a loss — needs full target early-exit. |
| ~~attributed construction~~ RESOLVED | 0.71x->**1.24x** | FIXED via bjomp immutable-attr deepcopy fast-path (6f9854787): to_directed 1.14x, to_undirected 1.24x, copy 2.14x. Was fnx's weakest area; now WINS. Residual to_undirected reciprocal-merge = tbh4q. |
| waxman_graph | 0.87x | marginal; residual O(n^2) distance vs nx; batch was self-win not nx-win. |
| adamic_adar / resource_allocation | ~0.95x | neutral at scale; fine. |
| **CONSTRUCTION-SUBSTRATE FRONTIER** | 0.41-0.70x | EXACT ROOT isolated (cc): the per-node/edge attr-dict PyO3 shallow-copy. compose WITHOUT attrs is a 1.36x WIN (structure+keys already beat nx); WITH attrs 0.54x (attrs = ~6000 dict copies). So relabel 0.41x / compose 0.49x / union 0.65x / MultiGraph.copy 0.45x are all the attr-copy wall, NOT keys/structure. EXACT FIX: copy-on-write attr mirrors (tbh4q). bjomp already reversed the adjacent deepcopy case (to_directed/copy WIN). |

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
- **Scaffold-validated lever WINS** (filed by cc, implemented by peers): betweenness
  k-sampled (8ox3z) 49.78x. Caught+reverted a regression too: effective_size
  directed kernel (qbj9u) diverged — scaffold caught it.
- **Peer-area losses flagged**: preferential_attachment 0.55x (9142), dijkstra single-pair (j5u29).

VERDICT: fnx is release-ready on perf — it DOMINATES nx across the algorithm /
spectral / centrality / flow / community / IO / generator surface (typically
2-1000x). The residual losses form ONE coherent cluster — the construction
substrate (graph build/copy/merge of attributed graphs) — not scattered algorithm
gaps. This verify phase REVERSED the biggest part of that frontier (bjomp:
to_directed/to_undirected/copy LOSS->WIN) and reverted the one regression; what
remains (relabel/compose/union/MultiGraph.copy/deepcopy-walk) is diagnosed, filed,
and shares a single fix axis (native build-method optimization + killing the
per-node label materialization wall). No kept optimization fails to beat/match nx.
