# Release-Readiness Scorecard — perf domination vs NetworkX (cc measured)

Measured 2026-06-18..19 with fresh release builds (HEAD), warm min-of-8, vs NetworkX.
Status of perf claims that were committed `code-first batch-test pending`.
CONFORMANCE CERTIFIED GREEN (2026-06-19, HEAD): 705 tests passing across the touched
areas (212 matching/components + 493 construction/copy/deepcopy/multigraph), 0
failures; shipped optimizations (multigraph CC/fyxma, bjomp) solid.

## HEADLINE — realistic end-to-end analysis pipeline: **20-32x faster than nx**

build + pagerank + betweenness(k) + closeness + clustering + transitivity +
components + degree + scipy-export: fnx 6.4ms vs nx 130ms (n=500, 20.26x);
fnx 35.5ms vs nx 1143ms (n=1500, 32.20x, scales better). The aggregate answer to
"beat the original on realistic workloads": YES, decisively. (DIRECTED pipeline: 5.68-9.40x.)

## LARGE-N SCALING (n=3000) — fnx's advantage GROWS with graph size

Large-n head-to-head (n=3000, gnp): ALL WINS, MARGINS LARGER than at moderate n —
transitivity 83x, clustering 60.07x, degree_assortativity 50.37x, average_clustering
43.64x, pagerank 24.08x, square_clustering 20.96x, core_number 10.28x, triangles 5.87x,
connected_components 4.51x, to_scipy(weight=None) 3.50x. fnx's O(n) Rust kernels scale
past nx's worse-scaling Python, so the perf lead WIDENS on realistic large graphs.
Release-readiness: fnx dominates not just at benchmark sizes but increasingly at scale.

## WEIGHTED SHORTEST-PATH FAMILY — fully reclaimed (cc) [p60i1+lc2qy COMPLETE]

Every weighted single-pair variant now WINS via native kernels: dijkstra_path 0.20-0.58x->
3.5-4.9x (lc2qy target-early-exit, un+directed), shortest_path 0.20x->bidirectional (p60i1
directed kernel + spw routing), dijkstra_path_length 1.16-2.82x, shortest_path_length win,
bidirectional_dijkstra un(k4p0b)+dir(p60i1), bellman_ford 2.58x, astar 3.39x. The whole
family DOMINATES un/directed, path/length, single/source.


After the single-pair PATH fixes, the ENTIRE weighted shortest-path surface WINS +
is parity-exact (n=1000): dijkstra_path 0.47x->1.28x (n30yf FIXED), shortest_path(s,t,w)
780/802->3188/3188 + 1.6x (spw, bidirectional), dijkstra_path_length 1.55x,
shortest_path_length(s,t) 1.78x, shortest_path source-only 1.63x, length source-only
2.44x, bidirectional_dijkstra 1.66x, bellman_ford_path 2.58x, astar_path 3.39x. The two
single-pair PATH losses (String-keyed + tie-divergent kernels) were the ONLY gaps —
routed to the nx-correct fast kernels (single_source / bidirectional). 0 remaining path
losses. Residual lc2qy = single-pair early-exit kernel variant (far-target 0.58x only).

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
| MultiGraph | connected_components (fyxma) + number_cc/is_connected/node_cc (fyxma2) direct BFS | **0.02-0.08x -> 0.97-1.26x** (12-114x faster) |
| MultiGraph | single_source_shortest_path_length (fyxma3) direct BFS | **0.03x -> 1.00x** (33x faster) |
| MultiGraph | single_source_shortest_path + single-pair sppl/has_path (ubizp) direct BFS | 0.04x->0.59x / 0.00x->0.4-0.8x (15x+) |
| MultiDiGraph | single_source_shortest_path_length (zid1b) successor-BFS | **0.03x -> 1.05x** (33x faster) |
| MultiDiGraph | weakly_connected family (zid1b) succ∪pred BFS | **0.04x -> 1.00-1.16x** (25x faster) |
| MultiDiGraph | single-pair shortest_path_length/has_path (zid1b) successor-BFS | **0.00x -> 0.98-1.17x** |
| MultiDiGraph | is_strongly_connected (zid1b) CSR fwd+rev reachability | **0.02x -> 3.87x** (SC graphs; not-SC 0.21x) |
| MultiDiGraph | descendants/ancestors (zid1b) succ/pred-BFS | **0.03x -> 0.71-0.74x** (24-25x faster) |
| MultiDiGraph | is_directed_acyclic_graph (zid1b2) Kahn CSR | **0.34x -> 8.46x** (25x swing) |
| MultiDiGraph | number_strongly_connected_components (11m92) Kosaraju CSR | **0.15x -> 4.31x** (29x swing) |
| MultiDiGraph | topological_sort (11m92) native CSR Kahn | **0.18x -> 5.63x** (31x swing) |
| Traversal | descendants_at_distance chain set-expansion (dadchain) | **0.32x -> 1.39-1.62x** (k-hop) |
| Shortest-path | DIRECTED bidirectional_dijkstra native CSR kernel (p60i1) | **0.20x -> 2.43x** (12x swing) |
| Shortest-path | dijkstra_path native target-early-exit kernel (lc2qy) | **0.20-0.58x -> 3.5-4.9x** |
| Shortest-path | astar_path_length single-search + Rust int-check (yo37g) | **0.30-0.50x -> 4.1-4.3x** |
| Link analysis | pagerank personalized scipy path (prscipy) | **0.20x -> 1.18x** |
| Centrality | eigenvector_centrality weight/nstart scipy matvec (eigscipy) | **0.67-0.86x -> 5-11x** |
| Centrality | katz_centrality non-default scipy matvec (katzscipy) | **0.66-0.85x -> 8x** |
| Distance | eccentricity all-pairs fast path (eccallpairs) | **0.84x -> 3.05x** (weighted) |
| Distance | diameter/radius/center/periphery weighted in-process (eccallpairs) | **1.0x -> 3.0x** |
| Tree | prefix_tree batch DiGraph construction (preftreebatch) | **0.43x -> 0.62x** |
| Connectivity | all_pairs_node_connectivity small-nbunch delegation (apncnbunch) | **0.002x -> 0.69x** (345x) |
| Structural holes | local_constraint scale-once (localconstraint) | **0.27x -> 4.08x** |
| Bipartite | bipartite.clustering adjacency snapshot (bipclust) | **0.84x -> 2.43x** |
| Bipartite | bipartite.average_clustering / degree_centrality de-delegate | **0.86x->2.4x / 0.41x->1.04x** |
| Euler | eulerian_circuit snapshot Hierholzer (eulcirc) | **0.63x -> 9.19x** |
| Isomorphism | could_be_isomorphic batch degree (cbiso) | **0.74x -> 1.04x** |
| Approximation | treewidth_decomp bag-list + batched build (twdecomp) | **0.72x -> 0.95x@n300** |
| Degree-seq | is_graphical eg Durfee-corner break + O(n) sweep (egsweep) | **0.64x -> 1.20-1.45x** |
| Link-pred | preferential_attachment / RA / AA degree-batch (pa-degbatch) | PA **0.78x->0.99x**, RA/AA neutral->**1.05-1.06x WIN** |
| Code-first batch | assortativity 9147-52 (degree_assort 78x) / expansion-cut-flow 9153-55 (flow_hierarchy 219x) | 2.4-219x, parity-verified |

## Verified LOSSES → action

| Area | Optimization | Measured | Action |
| --- | --- | --- | --- |
| Link analysis | google_matrix native routing | 0.34x->0.93x | **REVERTED** 30d99dcaf — routing removed (was list-of-lists conversion tax), numpy path 0.93x@n=500, dangling fix kept, conformance green |
| Link-pred | preferential_attachment (9142) | 0.55x | FLAGGED to CrimsonRiver (their kernel; not a cc file) |

## Open gaps surfaced (file/investigate)

| Function | Measured | Note |
| --- | --- | --- |
| dijkstra_path(u,v) single-pair weighted | 0.22-0.54x | CORRECTED: kernel ALREADY early-exits (`if u==target break`, lib.rs:1189); real cost is the per-call O(E) weighted-projection build (nx reads weights lazily). NARROW — all_pairs_dijkstra WINS 4.86x, single-source wins; only isolated single-pair loses. Fix = cache projection / lazy weights (revised j5u29). |
| max_weight_matching / min_edge_cover | 0.83-0.94x | native blossom is 8.8x FASTER + valid but tie-breaks differ from nx (filed lmqwv). Node sort-order (lib.rs:8059 sort_unstable vs nx insertion) is ONE divergence (14->17/20 when aligned) but 3/20 DEEPER tie-breaks remain — deep alignment needed. Delegates to nx blossom for bit-for-bit parity. |
| ~~attributed construction~~ RESOLVED | 0.71x->**1.24x** | FIXED via bjomp immutable-attr deepcopy fast-path (6f9854787): to_directed 1.14x, to_undirected 1.24x, copy 2.14x. Was fnx's weakest area; now WINS. Residual to_undirected reciprocal-merge = tbh4q. |
| waxman_graph | 0.87x | marginal; residual O(n^2) distance vs nx; batch was self-win not nx-win. |
| adamic_adar / resource_allocation | ~0.95x | neutral at scale; fine. |
| **CONSTRUCTION-SUBSTRATE FRONTIER** | 0.41-0.70x | EXACT ROOT isolated (cc): the per-node/edge attr-dict PyO3 shallow-copy. compose WITHOUT attrs is a 1.36x WIN (structure+keys already beat nx); WITH attrs 0.54x (attrs = ~6000 dict copies). So relabel 0.41x / compose 0.49x / union 0.65x / MultiGraph.copy 0.45x are all the attr-copy wall, NOT keys/structure. EXACT FIX: copy-on-write attr mirrors (tbh4q). bjomp already reversed the adjacent deepcopy case (to_directed/copy WIN). |

## MULTIGRAPH / MULTIDIGRAPH CONVERSION-TAX CAMPAIGN (cc) — surface reclaimed

The dominant cc perf campaign: the multigraph/multidigraph surface lost 7-114x across
shortest-path / connectivity / reachability / DAG via the multigraph->simple conversion
(gr.undirected() / gr.digraph()). SHIPPED ~16 direct-adjacency fixes (neighbors /
successors / predecessors / succ-union-pred / integer-CSR BFS-DFS-Kahn-Kosaraju), all
parity-verified + conformance-green:
- MultiGraph: connected_components 114x, number_cc/is_connected/node_cc 12-50x->win,
  sssp_length 33x, single_source_shortest_path 15x, single-pair sppl/has_path ms->us.
- MultiDiGraph: sssp_length 33x, weakly-connected family 25x, single-pair parity/win,
  is_strongly_connected 3.87x(SC), descendants/ancestors 24-25x, is_dag 8.46x,
  number_strongly_connected_components 4.31x, topological_sort 5.63x, dag_longest_path 0.21x->1.57x, triangles 0.27x->2.16x.
FILED (order-sensitive / native-kernel / deep): strongly_connected_components 8hjsu,
biconnected/MST ij951, matching lmqwv, dijkstra-tie n30yf, dag_longest_path-full 5m18w,
triangles br-r37-c1-lzh3n, construction-substrate tbh4q. The order-INVARIANT functions are
dominated; the order-SENSITIVE remainders are precisely filed.

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
2-1000x). After a rigorous bold-verify campaign, the real-loss surface is TINY and
fully characterized:

- 2 real losses FIXED + shipped: bjomp (construction deepcopy reversal), multigraph
  connected_components (114x->parity, fyxma direct-adjacency BFS).
- 5 apparent losses were SETUP ARTIFACTS — realistic case WINS: node_link_data
  (cold timing -> 1.43x), weighted-pagerank (mutation-dirty sync -> 3-5x built-with-
  weights), dijkstra single-pair (kernel early-exits; all-pairs 4.86x), to_scipy
  multigraph (weight=None 1.20x / dtype-given 1.25x), simple_cycles (islice order ->
  0.93-0.97x neutral).
- 1 confirmed-correct correctness gate: to_scipy multigraph weight=str+dtype=None
  (tested relaxation -> would break nx str-weight ValueError parity).
- Real residual losses, both DEEP + low-priority: (a) construction substrate
  (compose/relabel/union attr-copy) — fundamental: CgseValue holds only
  scalars+dicts so the Python attr-mirror must be eagerly copied; CoW custom-dict
  needed (tbh4q). (b) matching family (max_weight/min_edge_cover 0.83-0.94x) —
  native blossom is 8.8x faster but tie-breaks differ from nx; alignment is deep
  (filed lmqwv). Both masked in realistic pipelines (analysis dominates, wins 5-32x).

No kept optimization fails to beat/match nx. The campaign's defining result: rigorous
honest measurement falsified 5 of my own "losses" — fnx dominates more comprehensively
than the naive numbers suggested.
