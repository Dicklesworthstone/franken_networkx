# Measured Head-to-Head Evidence — cc (CopperCliff)

Verify/gauntlet phase: every recent `code-first batch-test pending` optimization
built into a fresh release wheel (`maturin build --release`, clean .so verified
`nm -D | grep crossbeam == 0`, installed at HEAD) and measured **head-to-head vs
NetworkX** on realistic workloads (warm, min-of-8). Honest numbers — wins, losses,
neutrals. Losses get reverted; conformance stays green.

Build: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cc maturin build --release -m crates/fnx-python/Cargo.toml` → wheel installed. Measured 2026-06-18.

## SHIPPED: link-prediction degree-batch — PA 0.78x->0.99x, RA/AA neutral->WIN

The PA 0.78x loss + RA/AA 0.97-0.98x neutral were in MY pure-Python scorer
(_link_prediction_compute), NOT the raw kernels: deg(n) lazily called G.degree(n)
(a PyO3 call) per unique node. For a large/default ebunch that is N PyO3 calls; one
batched G.degree() snapshot (0.08ms for all V) replaces them. Gated on
metric!=jaccard (jaccard uses set-union) AND (ebunch is None OR len>=V) so small
explicit ebunches stay lazy. MEASURED: PA 0.78x->0.99x, resource_allocation
0.98x->1.06x WIN, adamic_adar 0.97x->1.05x WIN; parity 96/96 + 1080 link-pred
conformance tests green. The deg-product PA loss is GONE (it was a cc-file Python
tax, separate from the stamp-mark common-neighbor kernel lever).

## Link-prediction stamp-mark baseline (04z53.9144, cod-b/TealSpring's kernel) — measured target

Benched link-pred over a 3000-pair explicit ebunch (the stamp-mark use case): jaccard
1.51x WIN, but adamic_adar 0.97x + resource_allocation 0.98x are NEUTRAL — exactly the
pairs the reusable stamp-marked scratch-vector lever (replace per-pair HashSet
intersection) would push to WINS. preferential_attachment 0.78x is a SEPARATE loss
(deg(u)*deg(v), no common-neighbor intersection — stamp-mark doesn't apply; CrimsonRiver
kernel 9142). The stamp-mark fix lives in fnx-algorithms/src/lib.rs (TealSpring's file,
NOT a cc file) — baseline recorded here as the peer's measured bench target.

## FIXED (cc): generalized_degree Graph-selfloop parity (was pre-existing)

test_clustering.py::TestGeneralizedDegreeParity[Graph-Graph-selfloop-kwargs4] FAILED
(pre-existing) — the native generalized_degree kernel counted a self-loop as a neighbour
(spurious triangle-distribution entries); nx excludes self-loops. FIXED: gate the native
path on number_of_selfloops==0, else the self-loop-correct Python triangle iterator.
30/30 parity, test_clustering.py 83 passed. Common (no-selfloop) case keeps the native
3.23x.

## PRE-EXISTING (not cc): 3 coverage/mixing test failures unrelated to MultiDiGraph work

test_coverage_gaps.py: test_public_coverage_has_no_networkx_delegated_exports,
test_generated_coverage_matrix_document_is_current, and
test_mixing_and_resistance_helpers_match_networkx_without_to_nx_fallback FAIL — VERIFIED
PRE-EXISTING (fail identically on cc_wheelI, the build BEFORE number_scc) and in domains
cc never touched (coverage-doc generation + degree-mixing/resistance helpers, not the
MultiGraph/MultiDiGraph BFS routing this campaign did). My native routing only REMOVES
delegation, so it cannot add NX_DELEGATED exports. Peer-domain / stale generated doc;
flagged, not a cc regression.

## zid1b MOSTLY SHIPPED: MultiDiGraph surface reclaimed (6 fns 24-114x); SCC is the deep remainder

MultiDiGraph conversion-tax vein: SHIPPED sssp_length 0.03x->1.05x, weakly-connected
family 0.04x->1.00-1.16x, single-pair shortest_path_length/has_path 0.00x->0.98-1.17x,
is_strongly_connected 0.02x->3.87x(SC), descendants 0.03x->0.74x, ancestors 0.03x->0.71x
(all direct successors/predecessors/CSR BFS, parity-verified, conformance green).
REMAINING: strongly_connected_components 0.13x — FILED br-r37-c1-8hjsu as deep+order-sensitive (the
SCC components must match nx's exact completion order for condensation; needs an
nx-ordered Tarjan over the CSR, not the order-invariant BFS lever). pagerank 0.71x
separate (numeric).

## DIRECTED weighted single-pair path — PARITY fixed (spw routing), perf k4p0b-bound

Verified DiGraph weighted shortest paths: my shortest_path spw routing ALSO fixed the
DIRECTED divergence (native _raw_shortest_path is 1021/1043 on directed too — diverges on
ties; bidirectional routing -> 1043/1043). dijkstra_path 1043/1043, shortest_path_length
1043/1043. PERF residual: directed PATH variants lose (dijkstra_path 0.56x, shortest_path
0.20x) — fnx's bidirectional_dijkstra is SLOW for directed (in-process Python reimpl's
succ/pred adjacency tax, k4p0b; native 0.42ms vs bidirectional 0.75ms vs nx 0.22ms).
Parity is correct (priority); perf needs k4p0b. ATTEMPTED+REVERTED (cc, ~0 gain): routing
the directed _bidirectional_dijkstra_local adjacency through _native_successor/predecessor
_row_dict (32x faster in isolation for dict(view), but the loop uses view.items() iteration
with NO materialization, so no gain — 0.20x->0.19-0.23x noise). The real bottleneck is the
PYTHON dijkstra loop (heap+dict ops per node), not adjacency — k4p0b needs a NATIVE directed
bidirectional kernel (the undirected _native_bidirectional_dijkstra is undirected-only,
374/1043 on directed). lc2qy (single-pair early-exit). Undirected path family already WINS 1.3-3.4x.

## average_neighbor_degree(weight) bincount 2.35x WIN blocked by lazy-key COO (l0bdz)

avg(weight) 0.63x = G.adj[node].items() edge-data view materialization. scipy matvec
(A@deg)/rowsum CORRECT but only 0.75x (CSR-build capped). Native COO + bincount = 2.35x
WIN but parity BREAKS 2/70 — default-order COO indices != G.degree()/list(G) order (lazy
display-key vs canonical, qq6hi). Both REVERTED. RESOLVED: bincount needs _sync_rust_edge_attrs (O(E) Python->inner) for correct weights;
WITH the sync it is 0.41-0.83x (sync erases the speedup). The 2.35x was the WRONG (unsynced
data=1.0) result. No clean win; needs a native weighted-avg-neighbor-degree kernel. NOTE: conformance (849) PASSED even with the WRONG bincount
result -> the avg_neighbor_degree weighted conformance is too weak to catch a 2.26-abs
divergence; trust the random head-to-head parity test over conformance here.

## node_disjoint_paths 35-failure conformance gap = TEST bug, NOT fnx (kfyyf RESOLVED)

test_directed_node_connectivity_satisfies_menger (owner Dicklesworthstone, NOT cc) asserts
nc == len(list(node_disjoint_paths(s,t))) without guarding nc==0. When t is unreachable
node_disjoint_paths raises NetworkXNoPath in BOTH nx and fnx (verified identical), so list()
raises and the assert errors. fnx is byte-correct. 35 'failures' = one unguarded test case.
DIAGNOSTIC: a conformance failure that reproduces IDENTICALLY in nx is a test bug, not a
port gap — always compare the fnx error to nx's before filing as an fnx regression.

## triangular/hexagonal_lattice 0.30-0.37x = tuple-key construction, need native kernel (br-r37-c1-ap7at)

Products/lattice sweep mostly WIN (hypercube 19x, grid_graph 14x, lexicographic_product 3.5x,
windmill 5x). triangular_lattice 0.30x + hexagonal 0.37x: _try_add_edges_from_batch with TUPLE
keys (i,j) = 53pct (per-edge tuple-canonical conversion). grid_2d_graph WINS 14x via NATIVE
_fnx.grid_2d_graph_simple kernel; triangular/hexagonal use pure-Python add_edges_from -> tax.
Need native Rust kernels like grid. Combining 4 add_edges_from into 1 does NOT help. Rust-side.

## weighted matrix exports LOSE at scale n2000 (FILED wvuf7)

BIG: at n=2000 WEIGHTED pagerank 0.54x, to_scipy 0.68x, adjacency_matrix 0.67x (unweighted
WIN 3x). to_scipy weighted profile: _sync_rust_edge_attrs = 6.87ms of 10.4ms (75pct); nx
whole weighted to_scipy = 7ms, less than fnx sync ALONE. sync pushes ALL edge dicts to read
one weight attr. edges(data=weight) bulk read = 3.35ms (HALF the sync). FIX: build weighted
COO from edges-view not sync, matrix order-invariant so any edge order works, 0.68x to ~2.7x.
CORE fn (pagerank/laplacian/adjacency all use it); needs careful focused impl + full
conformance. Degrades with scale (won 2.28x at n250). LARGE-N sweeps find what small-N misses.

## re-export hunt: asyn_fluidc 0.77x parity-bound pure-Python; rest WIN 7-32x

Hunted re-exported (module=nx) functions: rich_club 32x, harmonic 17x, triadic_census 13x,
avg_neighbor_degree(unweighted) 8.75x, reciprocity 7.7x WIN; girvan_newman/dag_to_branching
neutral. asyn_fluidc 0.77x LOSS: re-exported, runs nx pure-Python fluid-communities on slow
fnx adjacency (max_iter*V G[node] PyO3). Conformance checks INVARIANTS (coverage/disjoint/
modularity), not exact (already 0/19 vs nx, order-sensitive). But PURE-PYTHON algo -> fnx can
at best MATCH nx (delegate=convert+nx ~0.9x, snapshot-reimpl ~parity), never beat it; native
acceleration impossible (no Rust kernel for fluid communities). Parity-bound, not a clean win.

## min_edge_cover/max_weight_matching = order-sensitive blossom (NOT clean loss)

RE-CHARACTERIZED (cc): min_edge_cover + max_weight_matching(maxcardinality) vary 0.54-1.04x
across seeds (median 0.85x) — the HIGH VARIANCE is the blossom adjacency-order sensitivity
(fnx internal adj order vs nx in the traversal), NOT just the rebuild artifact and NOT a
consistent loss. nx.Graph(fnx.edges()) does NOT control the order (fnx vs nx internal structs
differ). Cover result always correct (same size). min_edge_cover is locked to max_weight_
matching for parity (specific matching edges). fnx adj order is on avg slightly less favorable;
fixable only via an adjacency-order-matching substrate. NOT a clean win. Asteroidal/planarity/
covering domain otherwise DOMINATED (find_asteroidal_triple 850x, is_at_free 826x).

## bounded-query sweep DOMINATED; 2 substrate residuals

Cutoff/depth-limit queries WIN (cutoff respected, native): sssp_length(cutoff) 1.94x,
descendants_at_distance 1.88x, ego_graph(r=2) 1.68x, bfs_tree(depth) 1.97x, dfs_tree 1.81x,
has_path 5.32x, shortest_path_length(s,t) 2.97x. LOSSES both substrate: single_target_
shortest_path(cutoff) 0.48x = path-construction (wjc8m, filed); all_neighbors(single) 0.44x
= is_directed() PyO3 check per call (~0.5us) + neighbors view vs nx Python attr — micro-op,
rarely hot (algos use _raw_neighbors internally). No clean win.

## single-node clustering family: clean ego wins + substrate losses

SWEPT single-node queries: node_clique_number 0.15x->1.56x + number_of_cliques single->10.63x
SHIPPED (ego-graph lever, whole-graph->ego). REMAINING single-node losses are SUBSTRATE not
whole-graph-waste: square_clustering(single) 0.55x = lazy _raw_neighbors(G,node) per-node PyO3
(node+nbrs+2hop), same frontier as dominating_set/link-pred. clustering(single) 0.87x same.
WINS in the sweep: closeness(single) 3.13x, eccentricity(single) 2.75x, communicability 21.6x,
local_reaching 6.76x, harmonic(nbunch) 2.65x.

## clustering(single,weighted) 0.28x max_weight edges-view substrate-capped

clustering(G,v,weight) builds whole-graph adj_snapshot(77us)+weight_cache(242us)+max_weight
(187us) for ONE node. The snapshot/cache (319us) ARE removable waste (local-sliver lever),
but max_weight ALONE (187us, slow edges(data=True) view) EXCEEDS nx full 169us -> even the
local fix only reaches ~0.59x. max_weight via edges-view is fnx FASTEST (to_scipy 418us,
native+sync 319us slower). Substrate (4b5ie edges-view mat). Niche (all-nodes has native
fast path). Not shipping the parity-closer.

## matrix-converter from_* substrate; to_* all WIN (sweep artifacts)

to_dict_of_dicts 1.17x, to_numpy_array 1.49x, to_scipy_sparse_array 2.28x WIN (sweep losses
were the in-lambda from_dict_of_dicts build). from_pandas_edgelist 1.76x WIN. LOSSES:
from_scipy_sparse_array 0.62x, from_numpy_array 0.78x — BOTH already use vectorized extraction
(coo / np.nonzero) AND batch add_edges_from((u,v,{attr:w})); residual = attributed-construction
substrate + necessary per-edge int(u),int(v) (fnx node keys type-sensitive, numpy-int
endpoints must canonicalise to Python int or duplicate nodes). Substrate-bound, no clean win.

## IO-reader residuals: from_dict_of_dicts 0.84x already-batched substrate; to_dict_of_lists WINS

to_dict_of_lists 2.11x (sweep 0.19x was the in-lambda fnx-graph build, artifact). from_sparse6
1.48x, from_dict_of_lists 1.91x WIN. from_dict_of_dicts 0.84x: simple-Graph path ALREADY
batches add_edges_from((u,v,attrs)) (br-nlanb) — residual is attributed-batch-construction
substrate (dual AttrMap+mirror). parse_multiline_adjlist 0.74x = parse, same edge-case-
divergence risk as read_edgelist (do not route). IO clean wins were from_graph6 (g6batch);
rest are parse-divergence or attributed-construction substrate.

## read_edgelist 0.40x: parse_edgelist NOT a drop-in (REVERTED)

read_edgelist(kwargs) delegates to nx + nx->fnx convert (0.40x). Routing to fnx.parse_edgelist
hit 1.73x BUT broke 13 conformance tests: fnx.parse_edgelist DIVERGES from nx on edge cases
(blank lines "a b\n\nc d", lonely 1-token lines, mid-line comments "a b # tail", self-loops,
dup edges) AND bypasses the native fast-path test. try/except cannot catch VALUE divergences.
Delegation is required for correctness. To fix: make fnx.parse_edgelist byte-match nx on edge
cases first (separate, risky). Filed-as-substrate/parse-divergence.

## normalized_laplacian weighted 0.90x = to_scipy edge-sync substrate (unweighted WINS 3.18x)

normalized_laplacian_matrix: UNWEIGHTED 3.18x (native vectorized COO from index arrays, no
weights/sync). WEIGHTED 0.90x byte-exact but falls back to to_scipy_sparse_array(weight) +
D^-1/2 L D^-1/2 matmuls (mirrors nx). The gap IS to_scipy weighted (native COO + edge-attr
sync ~2x vs nx pure-numpy) — same sync-tax class as l0bdz. Native weighted-COO path would
need the O(E) sync, erasing the gain. Marginal; unweighted (common) already dominates.

## SUBSTRATE FRONTIER MAPPED (cc) — remaining losses are per-node/small-input PyO3 tax

The accessible de-delegation / snapshot / batch-native wins are largely MINED. The residual
LOSSES cluster into ONE root cause: fnx accesses neighbours/degree across the PyO3 boundary
PER NODE, while nx reads native Python _adj/_degree dicts. fnx WINS at scale (amortised) but
loses on small/per-node access:
- dominating_set 0.94x(n150)->0.81x(n500): greedy touches ~V/deg nodes, each one set(_raw_nbrs
  (G,v)) PyO3; snapshot wastes O(V+E) for the few touched; native kernel diverges (set-order).
- maximal_independent_set 0.88x(n150)->1.16x(n500): small-input only, WINS at scale.
- selfloop_edges/number_of_selfloops (up5ig), is_path (ykqs0), link-pred small-ebunch,
  common_neighbors single: all the same per-node PyO3 vs nx Python-dict tax.
The RADICAL fix for the whole class is the persistent ordered Python adjacency mirror (4b5ie)
— one big substrate change would flip all of these. Not attempted (large/risky for one turn).

## link-pred small-ebunch 0.47-0.89x = same small-input PyO3 tax

preferential_attachment(ebunch) 0.47x, resource 0.62x, adamic 0.65x, jaccard 0.89x on a
5-pair ebunch; whole-graph WINS (jaccard 2.15x). _link_prediction_compute ALREADY memoizes
lazily (small ebunch touches only endpoints) so it is NOT a snapshot-waste bug — it is the
PyO3 per-node G.neighbors/G.degree access losing to nx pure-Python dict for tiny inputs.
Batch dict(G.degree()) does NOT help (per-node 3.3us < batch 11us for ~10 nodes). Same
substrate class as up5ig/ykqs0. Tiny absolute times; needs a native batch kernel to win.

## selfloop native-scan STALE + is_path PyO3 tax (br-r37-c1-up5ig, br-r37-c1-ykqs0)

selfloop_edges 0.44-0.65x / number_of_selfloops 0.74-0.76x: native nodes_with_selfloops_rust
scan (PyO3) now SLOWER than nx native Python _adj dict scan — my bd7a0c856 win is STALE.
Substrate (no persistent Python adj mirror). is_path 0.23x = per-step PyO3 has_edge tax
(has_edge swap ~0 gain, reverted). Both substrate/per-call-bound, filed.

## subgraph/induced_subgraph 0.70x = creation-only micro-artifact (usage WINS 2.60x)

subgraph(nbunch) view CREATION is 0.70x (fnx 16.4us vs nx 11.5us, ~5us) but subgraph +
list(edges()) is 2.60x WIN — fnx's heavier eager setup pays off the moment the view is
USED (the realistic pattern). Bare-creation timing is misleading, like the order-sensitive
rebuild artifact. NOT a real loss; do not trim creation (would hurt iteration). edge_subgraph
0.90x same shape.

## broad centrality sweep (group/percolation/communicability) — all WIN/neutral

Swept: communicability_betweenness 106.33x, percolation_centrality(weight) 13.67x,
group_closeness 7.05x, katz_centrality_numpy 3.57x, subgraph_centrality_exp 2.85x,
current_flow_betweenness(weight) 1.66x WINS; group_betweenness 0.96x / harmonic_centrality
(distance) 0.96x neutral. harmonic(distance) DELEGATES (parity 0.96x, not a loss); de-
delegation via per-source single_source_dijkstra loop ATTEMPTED+REVERTED (0.81x — V
single-source SETUPS cost more than the delegation's single conversion; all_pairs would
amortize but it is parity, not worth the accumulate-cost risk). No real new loss.

## weighted-centrality audit — all WIN/neutral after scipy-mirror vein

After the scipy-matvec vein (pagerank prscipy, eigenvector eigscipy, katz katzscipy), swept
weighted centralities: betweenness_centrality(weight) 13.92x, edge_betweenness 13.51x,
load_centrality 9.61x, current_flow_closeness 7.46x, closeness(distance) 3.61x WINS;
harmonic 0.95x / eigenvector_numpy(weight) 0.94x neutral. pagerank(dangling) APPEARED 0.65x
in the sweep but is 1.16x WIN on clean warm measurement (the scipy path IS taken; sweep
0.65x was cold/dict-creation noise). katz_centrality_numpy(weight) 0.89x marginal (numpy
linalg variant; the power-iteration katz now WINS 8x). Centrality surface dominated.

## bellman-ford/johnson/floyd/dijkstra weighted sweep — wins dominate, 2 kernel-bound losses

WINS: floyd_warshall 41.50x, all_pairs_dijkstra_path_length 2.68x, all_pairs_bellman_ford 2.35x,
single_source_bellman_ford 2.16x, single_source_bellman_ford_path 1.97x, johnson 1.57x,
floyd_warshall_numpy 1.47x, negative_edge_cycle 1.28x. LOSSES (filed br-r37-c1-0opkc, both
kernel/coercion-bound NOT Python-fixable): bellman_ford_path_length 0.73x (SPFA single-pair;
reroute ~0 gain) + single_source_dijkstra(combined) 0.77x (per-node f64->int coercion ~20%;
the _path variant WINS 1.57x). Need int-typed-distance kernels. Less-common, small.

## hbhli non-min audit — astar was the ONLY weighted fn using gr.undirected()

After fixing astar (gr.undirected() structure projection collapses parallel multigraph edges
to a NON-MIN weight -> use weighted_undirected_projection like dijkstra), audited other
weighted functions on parallel-edge multigraphs: minimum_spanning_tree, single_source_
dijkstra_path_length, dijkstra_path_length, bidirectional_dijkstra all 40/40 correct (they
use the weighted/min projection or delegate). Most gr.undirected() callers are UNWEIGHTED
(connectivity/BFS, multiplicity-invariant) so the non-min collapse is harmless there. astar
was the isolated case; fix complete.

## generators/IO/conversions sweep — all WIN/neutral, 0 new losses

random_lobster 2.92x, random_regular_graph 2.25x, to_dict_of_lists 2.08x, from_dict_of_lists
1.73x, to_dict_of_dicts 1.16x, powerlaw_cluster 1.15x WINS; adjacency_data/cytoscape_data/
generate_graphml neutral (~1.0x). The two apparent losses are ARTIFACTS: tree_data was a
no-op lambda (timing noise); freeze 0.69x is the fnx.Graph(edges) CONSTRUCTION tax (tbh4q),
not freeze (which is O(1) mark-frozen). astar_path_length now WINS (yo37g 4.1-4.3x). No new
accessible loss; surface remains dominated. Remaining real losses all filed: single_target
(wjc8m), adjacency view-materialization, multigraph astar value (hbhli), 6spkb, tbh4q.

## path-construction + view sweep — 3 losses (1 filed, 2 known)

has_path 8.56x, resistance_distance 23.17x, all_pairs_spl 3.98x, single_source_sp 1.57x WINS.
LOSSES: (1) astar_path_length 0.50x (int-weight) — runs a 2nd A* search to type-check;
Python walk-fix REVERTED (regressed float 0.06x); filed br-r37-c1-yo37g (kernel returns all_int).
(2) single_target_shortest_path(dir) 0.74x (re-measured) — native reverse BFS NOT integer-CSR-optimized
like single_source (cfsoi WINS 1.57x); reroute via reverse()+ssp is WORSE 0.21x. Filed br-r37-c1-wjc8m (mirror
cfsoi for the reverse direction in the kernel). Less-common. (3) dict(G.adjacency())
0.56x — the known view-materialization substrate (4b5ie/9hkgu), needs a persistent ordered
adj mirror. edges(data) 1.04x / nodes(data) 0.90x now neutral (mirror caches landed).

## tournament/tree/planarity/boundary sweep — all WIN, 1 marginal native loss

Swept: diameter(tree) 38.50x, min_edge_dominating_set 7.20x, tournament.is_tournament 6.58x,
is_planar 5.83x, is_distance_regular 4.54x, node_boundary 1.74x, score_sequence 1.23x,
center 1.22x WINS; edge_boundary 1.08x neutral. ONE marginal loss: tree_broadcast_center
0.79x — a PURE native-kernel call (_raw_tree_broadcast_center, no wrapper overhead), so the
kernel itself is a constant-factor behind nx on a less-common tree function (peer-crate,
not worth a chase). Also confirmed dijkstra_path_length wins all targets (1.16-2.82x, no
near gap) so lc2qy completed the weighted shortest-path family.

## less-common centralities/assortativity sweep — all WIN, 0 losses

Swept load_centrality 29.59x, communicability_betweenness 128.05x, communicability 23.66x,
katz_centrality_numpy 16.63x, subgraph_centrality 9.56x, information_centrality 5.46x,
numeric_assortativity 2.19x, voterank 1.89x, attribute_assortativity 1.84x, dispersion
1.71x — all WINS, 0 losses. Plus flow/connectivity/degree-seq: flow_hierarchy 126x,
s_metric 58x, degree_assortativity 39x, is_digraphical 18x, max_flow/min_cut 3.8-4.0x;
is_graphical(eg) FIXED 0.64x->1.20-1.45x (egsweep Durfee-corner break). The accessible-win
surface is now comprehensively swept; remaining residuals are the filed deep levers
(6spkb dirty-sync, tbh4q construction, lc2qy/2z0mw single-pair, order-sensitive 8hjsu/lmqwv),
marginal delegated taxes (bipartite.clustering 0.92x), and inherently-exponential
(dag_to_branching). fnx dominates the algorithm surface 1.2-1000x.

## DAG/distance/line-graph sweep — all WIN, 1 inherently-exponential near-parity

Swept DAG/distance/line-graph: eccentricity 13.79x, wiener_index 13.63x,
closeness_centrality 11.20x, local_reaching_centrality 8.79x, reciprocity 8.12x,
attracting_components 4.37x, line_graph 4.33x, is_aperiodic 2.72x, transitive_reduction
1.38x WINS. dag_to_branching 0.68x on a dense DAG / 0.96x near-parity on a sparse DAG —
it enumerates ALL root-to-leaf paths (exponential) then prefix_tree's them; both fnx and
nx are bound by the path explosion (36ms even on a 200-node sparse DAG, 0.96x). The 0.68x
dense-DAG gap is prefix_tree on exponentially-many paths — inherent + less-common, not a
clean lever. VERIFIED undirected bidirectional unaffected by the p60i1 binding branch
(weighted clean 2.30x, no regression). Surface stays comprehensively dominated.

## Native bidirectional MUTATED-weight per-call sync (filed br-r37-c1-6spkb)

The directed kernel (p60i1) WINS the COMMON case (clean/add_edge graphs: directed
shortest_path 0.20x->2.50x, sync is a 0.2us no-op). But graphs with MUTATED edge weights
(G[u][v]['weight']=w -> materialized edge dicts) pay a per-call O(materialized-E) edge-sync
(2.46ms@n=800) that does not clear a dirty flag -> directed shortest_path 0.05x. This is a
PRE-EXISTING class: undirected k4p0b has the identical sync slowness (mutated 0.14x). The
Python port (reads Python attrs, no sync) is faster for mutated (0.79x) but no cheap
Python-level dirty accessor exists to gate on. Kept the kernel (common case dominates +
consistency with undirected); filed br-r37-c1-6spkb for the root fix (dirty-tracked sync, helps
the whole native shortest-path family). NET POSITIVE: common case +2.5x, mutated tail
regressed to match undirected.

## Bipartite/similarity/structural sweep — wins dominate, 1 marginal delegated tax

Swept bipartite/similarity/structural: rich_club_coefficient 46.79x, harmonic_centrality
15.15x, local_efficiency 13.85x, bipartite.density 7.11x, effective_size 6.48x, constraint
5.70x WINS; simrank 0.92x / panther 0.97x / WL-hash 0.96x neutral. ONE marginal loss:
bipartite.clustering 0.92x — it DELEGATES to nx's own algorithm run on the fnx graph
(module networkx.algorithms.bipartite.cluster), so the gap is the fnx-graph-adjacency-as-
nx-backend tax (nx's Python iterates fnx's views slightly slower than native dicts).
Convert-first (nx.Graph(fb.edges()) then nx algo) only reaches 0.98x — still ~parity, NOT
a win; a native Rust kernel would be needed but bipartite.clustering is less-common. Marginal
delegated tax, not worth a kernel. Surface comprehensively dominated.

## Fresh cycles/cliques/coloring/connectivity sweep — all WIN, 0 losses

Swept cycles/cliques/coloring/chordal/connectivity/matching: node_connectivity 35.55x,
greedy_color 7.71x, find_cycle 7.06x, maximal_matching 5.02x, is_eulerian 3.94x,
cycle_basis 2.50x, is_chordal 1.74x; neutral find_cliques 0.99x / simple_cycles 1.00x /
dominating_set 0.90x (order/enumeration-bound, at parity). NO losses. Also swept
neighborhood/layer: ego_graph 1.27-1.56x, descendants/ancestors 1.16-1.37x,
single_source_spl 2.18-4.00x — all WIN (descendants_at_distance was the lone loss, FIXED
dadchain 0.32x->1.45x). Domain comprehensively dominated.

## Fresh simple-graph sweep (tree/flow/community/centrality) — 1 loss, j5u29-class

Swept tree/flow/community/centrality: WINS dominate (second_order_centrality 153x,
greedy_modularity 24x, harmonic 19x, label_propagation 2.37x, asyn_lpa 2.29x,
percolation 1.80x, minimum_cut 1.29x). ONE loss: voronoi_cells 0.69x — cProfile shows
it is dominated by the raw multi_source_dijkstra. CORRECTED: the weighted projection is
BORROWED for simple graphs (no build), so this is NOT the j5u29 projection class — the
cost is the FULL {node: path} String path construction while voronoi only uses path[0]
(the source/nearest center). Same path-materialization substrate as single_source_
shortest_path (ubizp). LEVER (filed br-r37-c1-2z0mw): a source-PROPAGATING multi_source
kernel returning {node: source}, skipping full paths. Marginal + less-common.
Simple-graph surface overwhelmingly WINS.

## MultiDiGraph OPERATOR/CONVERSION sweep — all trace to known walls (not new)

Swept MultiDiGraph operators/conversions: reverse 0.58x, copy 0.45x, subgraph 0.54x,
to_scipy/adjacency_matrix 0.58-0.61x. DIAGNOSED (not new gaps):
- reverse/copy/subgraph = the CONSTRUCTION/MIRROR-DICT substrate (tbh4q). reverse even
  HAS the integer-transpose fast path (inner.reversed()) gated on mirrors_all_empty, but
  add_edge eagerly allocs EMPTY node_py_attrs/edge_py_attrs dicts, so the all-empty CHECK
  scans O(V+E) PyO3 is_empty() calls. Root = eager-mirror-alloc (w1dm8/tbh4q); lazy mirror
  alloc would make the check O(1) + the fast path fast. Fundamental substrate.
- to_scipy_sparse_array/adjacency_matrix 0.58-0.61x = the weight=str+dtype=None
  correctness-GATE (verified: weight=None 1.59x WIN, dtype=float 0.98x). nx str-weight
  raises; the Python fallback is correctness-required (not fixable). Same as MultiGraph.
ALGORITHM surface dominated; OPERATOR/CONVERSION residuals are the substrate + gate walls.

## MultiDiGraph surface 7-50x slower — FILED br-r37-c1-zid1b (mirror MultiGraph direct-adjacency)

Swept MultiDiGraph: the ENTIRE shortest-path + connectivity + reachability surface
loses via the multidigraph->simple-digraph conversion: sssp_length 0.03x,
shortest_path_length 0.00x, has_path 0.00x, weakly_connected_components 0.04x,
strongly_connected_components 0.13x, is_strongly_connected 0.02x, is_weakly_connected
0.04x, number_weakly 0.04x, descendants 0.03x. All multiplicity-invariant -> the fyxma
direct-adjacency-BFS lever applies (MultiDiGraph has successors/predecessors/
successors_iter, digraph.rs:297+). Filed br-r37-c1-zid1b; cc implementing incrementally. pagerank
0.71x separate (numeric).

## SHIPPED ubizp: multigraph single-pair shortest_path_length + has_path — ms conversion eliminated

shortest_path_length(u,v) + has_path(u,v) unweighted on a MultiGraph ran the ms-level
gr.undirected() conversion for a microsecond query (~0.00x). Added
multigraph_target_bfs_distance: target-early-exit BFS over the adjacency, O(1) source
seeding (process source's neighbors directly). 0.00x (ms) -> 0.38-0.76x (us), parity
160/160 + 958 conformance. Residual ratio-loss = nx uses BIDIRECTIONAL BFS (~half the
nodes); filed ddw4l (microsecond, low-priority). The ms->us conversion-elimination is
the real practical win.

## SHIPPED ubizp(partial): multigraph single_source_shortest_path 0.04x->0.59x (15x)

Extended fyxma3 to PATHS: multigraph_sssp_paths BFS over the adjacency, building each
node's path from its discovery-parent's path (&str refs -> cheap clones, materialized
to String once at emit), matching nx's BFS-tree paths exactly (30/30 + cutoff). 0.04x
-> 0.38x (String clones) -> 0.59x (&str). Residual 1.7x loss = path String
materialization (nx uses native list-of-int-refs); index-based emit (like the simple
single_source_shortest_path_index path) could close it further. 15x improvement of a
25x loss; single-pair shortest_path/length still in ubizp.

## PRE-EXISTING (not cc): dijkstra_path weighted tie-break divergence (seed 50)

test_dijkstra_path_and_length_parity[False] fails: fnx dijkstra_path returns [0,1,2],
nx [0,4,2] (both valid shortest paths, weighted tie). VERIFIED PRE-EXISTING on committed
HEAD (cc_wheel6, before my single_source_shortest_path change) — NOT a cc regression.
Same tie-break class as max_weight_matching (lmqwv) — fnx's dijkstra picks a different
valid shortest path on weight ties than nx's exact relaxation order. Deep (match nx
heap/relaxation tie-break). Flagged as a real conformance gap (weighted-path tie).

## Multigraph biconnected family + MST 6-10x slower — FILED br-r37-c1-ij951 (parallel-edge-dependent, deeper)

Post-fyxma2 multigraph sweep found another cluster: articulation_points 0.12x,
is_biconnected 0.10x, biconnected_components 0.15x, MST 0.26x, bfs_edges 0.82x — all
CORRECT (20/20 parity w/ parallel edges) but slow. ROOT: gr.undirected() (118) runs
multigraph_to_simple_graph (attr-copy conversion) before the simple kernel. UNLIKE
connectivity, biconnectivity/MST DEPEND on parallel edges (cycle vs bridge; min
parallel edge), so the fyxma dedup-BFS trick is UNSAFE here — needs a multigraph-aware
int-CSR biconnected/MST kernel (deeper/riskier). Filed br-r37-c1-ij951. bridges 1.41x already WINS
(handles multigraphs natively). Simple-graph biconnected already fast.

## SHIPPED fyxma2: multigraph connectivity siblings 12-50x slower -> WIN/parity

The fyxma fix (connected_components direct-adjacency BFS) had THREE unfixed siblings
that still built a full simple Graph first: number_connected_components 0.08x (12x
slower), is_connected 0.09x (11x), node_connected_component 0.02x (50x!). Extended the
same lever (early-exit multigraph_is_connected, single-source
multigraph_node_connected_component, number_cc via the components helper). MEASURED:
number_cc 0.08x->1.24x WIN, is_connected 0.09x->1.26x WIN, node_cc 0.02x->0.97x parity;
multigraph parity 45/45 + simple 45/45 + empty-graph PointlessConcept preserved + 98
component conformance green. LESSON: when fixing a multigraph slow-path, audit ALL
siblings sharing multigraph_to_simple_graph_structure_only — they have the same tax.

## Small-input delegation sweep — all WINS except order-gated common_neighbors

Swept single-node/pair inputs: single_source_shortest_path_length 3.47x, has_path
5.43x, shortest_path 1.98x, resistance_distance 2.41x, node_connectivity 1.33x,
ego_graph 1.41x, descendants 1.12x — all WINS. ONLY common_neighbors(u,v) loses
(0.82x at ~1.5us). TESTED routing to the native _fnx.common_neighbors binding (1.07us,
faster than nx): UNSAFE — its ORDER-parity vs nx is only 110/158, while the current
wrapper (dict.keys() & dict.keys() preserves u's adjacency order like nx) is 154/158,
and there is an order conformance test. The microsecond loss is the PRICE of order
correctness; the wrapper is right. Another test-before-ship catch — not routed.

## Degree-batch vein audit — link-pred scorer was the ONLY loss; others win/already-batch

Grepped all per-node G.degree(/G.neighbors( call sites in __init__.py for the same
lazy-PyO3 pattern the link-pred fix addressed. Findings: is_forest 177x / is_tree 44x
WINS (the sum(G.degree(n)) loop is gated behind a fast edge-count path); rich_club
already snapshots (br-smetricdegcache); adjacency-building sites (11957, 12777) already
batch {n: list(G.neighbors(n)) for n in G}. So the lazy-deg loss was UNIQUE to the
link-prediction scorer — fixed (pa-degbatch). Vein exhausted: no other batchable loss.

## 3rd + 4th broad sweeps (link-pred family, structural holes, reciprocity, etc.) — all WINS

Post-degree-batch verification: Soundarajan community link-pred (cn_soundarajan 1.46x,
ra_index 1.12x, within_inter_cluster 1.14x), structural holes (constraint 8.46x,
effective_size 10.33x), dispersion(all) 11.15x, rich_club_coefficient 79.91x, s_metric
177.30x, reciprocity 7.18x, overall_reciprocity 6.69x, voterank 1.60x, pagerank 2.63x,
hits 1.36x — ALL WINS, zero new losses. The link-pred family is uniformly winning after
the degree-batch fix. Cumulative ~140 functions measured; fnx dominates the surface.

## 2nd broad sweep (distance/traversal/tree/community/dominance) — 12/12 WINS, no new losses

Swept 12 more unmeasured functions, ALL WINS: greedy_modularity_communities 20.67x,
harmonic_centrality 14.18x, eccentricity/center/periphery 11.9-12.3x, transitive_closure
5.57x, immediate_dominators 3.88x, label_propagation 1.90x, bfs_tree/dfs_tree 2.41x,
minimum_spanning_tree 1.38x. Zero new losses. Cumulative: ~120 functions across ~14
domains measured; fnx WINS everywhere except the 2 deep residuals (construction,
matching) + the 5 corrected artifacts. Domination confirmed broad + deep.

## Broad less-common-function sweep — mostly WINS; simple_cycles is the 5th artifact

Swept 12 less-common functions: WINS dominate (bridges 268x, articulation_points 38x,
greedy_color 10.5x, maximal_matching 10.9x, is_planar 6.85x, chain_decomposition 7.3x,
min_weighted_vertex_cover 6.65x). simple_cycles APPEARED 0.61x but that was the
islice(100) ORDER artifact (fnx/nx enumerate cycles in different order, so the first
100 differ) — measured fairly (ALL cycles, same count) it is 0.93-0.97x NEUTRAL.
5TH setup-artifact. dominating_set 0.70x is sub-0.1ms noise. min_edge_cover is a REAL ~1.2x loss (0.80x vs rebuilt) — TRACED (cProfile): it
delegates to max_weight_matching -> nx's Python blossom (the native blossom is
order-blocked, kpnc8). The loss is the fnx->nx conversion tax for the parity-required
nx blossom. De-delegation would be WORSE: the blossom is adjacency-heavy and fnx's
PyO3 adjacency access inside nx's algorithm would exceed the conversion. So it is
near-optimal given the order-blocked native blossom; the only real fix is fixing the
native blossom's tuple orientation (kpnc8). Less-common + deep. BOLD LEVER FILED br-r37-c1-lmqwv: the native _fnx.max_weight_matching blossom
is 8.8x FASTER (2.7ms vs nx 23.7ms) + valid (same weight) but diverges on ties (14/20
exact); test_matching_conformance needs bit-for-bit frozensets. Aligning the native
blossom's processing order to nx's (gnodes=list(G) + adjacency order) would kill the
6/20 divergence -> 8.8x WIN on the whole matching family (max_weight/min_weight/
min_edge_cover). Deep (replicate nx blossom tie-breaks) but high-value. ASSESSED (cc): the node
indexing (lib.rs:8059 node_names.sort_unstable() — lexicographic STRING sort) vs nx's
insertion order (list(G)) is ONE divergence source — using sort==insertion labels
lifts parity 14/20 -> 17/20, but 3/20 DEEPER divergences remain (augmenting-path /
blossom-formation order). So the node-order fix is necessary-but-not-sufficient; full
nx tie-break alignment is genuinely deep. Confirmed not a tractable single fix.

## CONSOLIDATED: after rigorous re-measurement, fnx's ONLY real loss surface is construction

FOUR of my initial "losses" were setup/benchmark artifacts where the REALISTIC case
WINS: node_link_data (cold measurement -> 1.43x), weighted-pagerank (mutation-dirty
sync -> 3-5x built-with-weights), dijkstra single-pair (kernel DOES early-exit; all-
pairs 4.86x; misdiagnosed), to_scipy multigraph (weight=None 1.20x / dtype-given
1.25x; only weight=str+dtype=None default falls to Python for dtype correctness).
TWO were real + FIXED: bjomp (construction deepcopy reversal), multigraph CC (114x).
The ONE genuinely-real, unfixed loss surface is the CONSTRUCTION SUBSTRATE
(compose/relabel/union/copy/subgraph attr-copy) — fundamental: CgseValue stores only
scalars+dicts (no list/tuple/exotic), so the Python attr-mirror MUST be eagerly
copied; the only fix is CoW custom-dict mirrors (tbh4q, deep redesign). Everything
else fnx WINS on realistic workloads.

## HEADLINE: composite realistic analysis pipeline = 20-32x faster than nx

The directive's "beat the legacy original on realistic workloads" — measured
end-to-end. Pipeline: build gnp + pagerank + betweenness(k=50) + closeness +
clustering + transitivity + connected_components + degree_centrality +
to_scipy_sparse_array. fnx vs nx (min-of-3):
- n=500:  fnx 6.4ms  vs nx 130.1ms  = **20.26x faster**
- n=1500: fnx 35.5ms vs nx 1142.8ms = **32.20x faster** (scales BETTER with n)
This is the aggregate release verdict: on a realistic multi-algorithm analysis
workload fnx dominates nx by 20-32x. The per-function detail below.

DIRECTED pipeline (build + pagerank + hits + in/out-degree + SCC/WCC + transitivity
+ reciprocity + triadic_census): fnx 5.68x@n=500 / 9.40x@n=1500 faster. Per-op
breakdown (n=1500) confirms NO hidden directed loss — ALL WINS: pagerank 26.73x,
triadic_census 17.14x (dominates fnx cost at 139ms but nx is 2387ms), reciprocity
5.43x, transitivity 3.01x, SCC 2.90x, WCC 1.99x, hits 1.69x. The lower aggregate
ratio is only because triadic_census is intrinsically the expensive op (fnx wins it
17x). Decisive win. New within_inter_cluster
kernel (91d8ff92f) verified 10/10 parity; full guard suite 1480 pass on the rebuilt
extension — the new commit is clean.

## Results

| Optimization | Workload | fnx | nx | ratio (nx/fnx) | Verdict | Action |
| --- | --- | --- | --- | --- | --- | --- |
| **laplacian_spectrum eigensolver n-gate** | gnp(300,.05) | 6.53ms | 8.65ms | **1.32x** | WIN | keep (was 0.47x BEFORE gate — real reversal) |
| **adjacency_spectrum eigensolver n-gate** | gnp(300,.05) | 8.49ms | 337.2ms | **39.7x** | WIN | keep |
| **modularity_spectrum eigensolver n-gate** | gnp(300,.05) | 12.0ms | 216.0ms | **18.0x** | WIN | keep |
| **gutman_index native routing** | conn(200) | 5.43ms | 11.73ms | **2.16x** | WIN | keep |
| **schultz_index native routing** | conn(200) | 5.44ms | 11.96ms | **2.20x** | WIN | keep |
| **generalized_degree native routing** | conn(400) | 0.60ms | 1.93ms | **3.23x** | WIN | keep |
| ~~google_matrix native routing~~ REVERTED | gnp(500,.05) digraph | 15.58ms->3.31ms | 5.46ms->3.06ms | 0.34x->**0.93x** | **REVERTED 30d99dcaf** | DONE — removed routing, numpy path restored (0.78x@200/0.93x@500, up from 0.34x). Dangling bug fix retained, conformance 58 pass. |

## Pre-existing losses surfaced by profiling (not cc optimizations — to investigate/file)

| Function | Workload | fnx | nx | ratio | Note |
| --- | --- | --- | --- | --- | --- |
| dijkstra_path(u,v) single-pair WEIGHTED | gnp(400,.04) wt | 5.85ms | 0.72ms | **0.12x** | DIAGNOSED + FILED br-r37-c1-j5u29. ROOT CAUSE: fnx `_raw_dijkstra_path` computes the FULL single-source SSSP (fnx dijkstra_path time ~= single_source time) then extracts path; nx early-TERMINATES when target is popped from heap. dijkstra_path_length same (4x). bidirectional_dijkstra (2.29ms) better but still 3x nx. Needs target-aware early-exit native dijkstra (Rust kernel, fnx-algorithms). Values already match nx. |
| max_weight_matching | gnp(300,.05) weighted | 86ms | 81ms | 0.94x | order-blocked native kernel (kpnc8); marginal, known. |

## Link-prediction scorers (CrimsonRiver 9142-9152) — measured (explicit ebunch 2000 pairs, gnp(800,.03))

| Scorer | fnx | nx | ratio | Verdict |
| --- | --- | --- | --- | --- |
| jaccard_coefficient | 7.50ms | 11.47ms | 1.53x | WIN |
| common_neighbor_centrality | 76.7ms | 205.8ms | 2.68x | WIN |
| adamic_adar_index | 5.28ms | 5.03ms | 0.95x | NEUTRAL |
| resource_allocation_index | 5.22ms | 5.00ms | 0.96x | NEUTRAL |
| **preferential_attachment** | 2.61ms | 1.43ms | **0.55x** | **LOSS** |

preferential_attachment (1.8x slower, persists at scale) is the simplest scorer
(deg(u)*deg(v)); nx is a trivial Python degree product. fnx's path (CrimsonRiver
9142 raw kernel) is slower — likely binding/per-pair overhead exceeding nx's
lightweight loop. CrimsonRiver's area (flagged via mail). Not a cc file.

## Generators (batch/native optimizations) — measured vs nx (warm min-of-5)

| Generator | fnx | nx | ratio | Verdict |
| --- | --- | --- | --- | --- |
| gnp_random_graph(800,.02) | 9.76ms | 23.16ms | 2.37x | WIN |
| random_geometric_graph(500,.1) | 1.38ms | 3.30ms | 2.38x | WIN |
| barabasi_albert(800,5) | 3.87ms | 5.05ms | 1.31x | WIN |
| watts_strogatz(800,6,.1) | 1.59ms | 1.78ms | 1.12x | WIN |
| gnm_random_graph(500,4000) | 3.93ms | 4.21ms | 1.07x | NEUTRAL |
| dual_barabasi_albert(800) | 3.31ms | 3.16ms | 0.95x | NEUTRAL |
| waxman_graph(400) | 31.1ms | 27.2ms | 0.87x | LOSS (marginal) |

waxman 0.87x: the batch optimization (memory: "3.8x") was a SELF-speedup vs the old
per-edge add_edge path, NOT vs nx — vs nx it's marginally slower (residual O(n^2)
distance compute + construction). Batch stays (better than per-edge); not a revert.

## IO / export — measured vs nx (gnp(1500,.01), warm min-of-5)

| Function | fnx | nx | ratio | Verdict |
| --- | --- | --- | --- | --- |
| to_scipy_sparse_array | 2.40ms | 6.29ms | 2.62x | WIN |
| to_dict_of_lists | 1.10ms | 2.08ms | 1.90x | WIN |
| to_dict_of_dicts | 0.24ms | 0.28ms | 1.15x | WIN |
| generate_edgelist | 5.90ms | 5.95ms | 1.01x | NEUTRAL |
| generate_adjlist | 1.85ms | 1.83ms | 0.99x | NEUTRAL |
| node_link_data | 2.37ms | 3.39ms | 1.43x | WIN (corrected: earlier 0.61x was cold-measurement NOISE; clean warm min-of-8 = 1.24x no-attrs / 1.43x attrs) |

node_link_data is a WIN (correction): edges(data=True) is at PARITY with nx
(3.26ms vs 3.30ms, inherent O(E)), and clean re-measurement of node_link_data
shows 1.24-1.43x WIN. The earlier 0.61x was a noisy cold measurement — HONEST
CORRECTION. Lesson: warm min-of-8, not min-of-5, for these.

## dijkstra_path early-exit — confirmed (near vs far target)

nx dijkstra_path NEAR 0.72ms / FAR 1.60ms (2.2x — strong target early-exit). fnx
dijkstra_path NEAR 2.68ms / FAR 3.32ms (~flat = full SSSP, no early-exit).
bidirectional_dijkstra flat 2.39ms (explores both ends). Confirms j5u29: needs a
forward target-early-exit native dijkstra with path-parity tie-breaking.

## Construction folds (with_mirror) — measured NEUTRAL-to-LOSS vs nx (substrate tax)

Attributed graph n=2000 (node attrs + edge attrs), warm min-of-6:

| Fold | fnx | nx | ratio | Verdict |
| --- | --- | --- | --- | --- |
| subgraph().copy() | 7.78ms | 6.26ms | 0.80x->? | was LOSS; copy() now 2.14x after bjomp deepcopy fast-path |
| G.copy() | 4.10ms | 8.77ms | **2.14x** | **WIN** (bjomp deepcopy fast-path) |
| to_directed() | 24.38ms | 27.91ms | **1.14x** | **FIXED -> WIN** (bjomp immutable-attr deepcopy fast-path, 6f9854787) |
| to_undirected() | 45.73ms | 56.80ms | **1.24x** | **FIXED -> WIN** (bjomp, 6f9854787) |

**RESOLVED (bjomp, commit 6f9854787)**: the dominant construction cost was
_native_to_directed_deepcopy round-tripping to Python copy.deepcopy per attr dict
(cProfile: 918k calls = 1.38s/1.88s). Fast-pathing all-immutable-scalar dicts to a
shallow dict.copy() (semantically identical; immutables never copied) REVERSED the
losses to WINS: to_directed 0.75x->1.14x, to_undirected 0.71x->1.24x, copy
0.98x->2.14x. 694 construction conformance cases pass; nested-mutable stays DEEP.
fnx's former weakest area now BEATS nx. (Subgraph .copy() also benefits.) The
residual reciprocal-edge-merge tax in to_undirected is CrimsonRiver's tbh4q.

## Graph operators — measured vs nx (attributed gnp(1500), warm min-of-6)

| Operator | fnx | nx | ratio | Verdict |
| --- | --- | --- | --- | --- |
| complement | 16.5ms | 43.9ms | 2.66x | WIN |
| cartesian_product | 1.72ms | 4.06ms | 2.37x | WIN |
| disjoint_union | 19.7ms | 22.2ms | 1.13x | WIN |
| union (rename) | 35.8ms | 23.2ms | 0.65x | LOSS |
| compose | 18.6ms | 9.1ms | 0.49x | LOSS |
| relabel_nodes | 11.6ms | 4.8ms | 0.41x | LOSS |

CONSTRUCTION-SUBSTRATE FRONTIER (consolidated): the operator + construction LOSSES
all share one root — per-node/edge PyO3 materialization + slow native build/clone
methods, NOT algorithm gaps:
- relabel_nodes 0.41x: per-node label PyO3 round-trips (native clone+rename was
  attempted + reverted 2026-06-09 — correct but 1.33x slower, parity-bound by the
  same round-trips).
- compose 0.49x: routes to native _native_compose (cProfile: 100% there). Rust
  read (lib.rs:9170) confirms the cost is per-node `py_node_key(py, node)` creation
  + per-node/edge `attrs.bind(py).copy()` (shallow Python mirror) + node_attrs
  clone — i.e. the per-node PyO3 MATERIALIZATION WALL, not a removable copy.deepcopy
  (so bjomp's trick does NOT apply). Same root as relabel + MultiGraph.copy.
- union 0.65x: union_all construction tax.
- MultiGraph.copy 0.45x (jelx1), __deepcopy__ walk (489mp).
This is fnx's residual weak frontier. Algorithms/spectral/centrality/IO DOMINATE
(13-1031x); the substrate is where the remaining vs-nx losses live. bjomp proved
the substrate CAN be beaten where the cost is copy.deepcopy (to_directed/copy now
WIN); the rest are the per-node attr-dict PyO3 copy wall. ISOLATED via micro-benchmark
(cc): compose WITHOUT attrs is a 1.36x WIN (fnx 8.17ms vs nx 11.13ms — structure +
py_node_key handling is FAST), but WITH attrs it is 0.54x (30.59ms; the attrs add
~22ms = ~6000 per-node attr-dict .copy() PyO3 round-trips). So the wall is
SPECIFICALLY the per-node/edge attr-mirror shallow-copy, NOT the node keys/structure
(those win). The fix is lazy/copy-on-write attr mirrors (tbh4q) — share the source
attr dict until mutated, avoiding the eager per-node PyO3 copy. That wall
is a fundamental substrate redesign (avoid materializing a Python label object +
attr dict per node), NOT a quick fix — bjomp only worked because copy.deepcopy was
a REMOVABLE cost layered on top. This is the honest floor of fnx-vs-nx on attributed
construction: fnx pays a Rust<->Python round-trip per node/edge that pure-Python nx
does not.

## MultiGraph.copy() — measured LOSS 0.45x (native inner-clone, separate from deepcopy)

MultiGraph.copy 0.45x vs nx (DiGraph.copy is 1.72x WIN). cProfile: 100% in native
_native_copy (no Python children). ASYMMETRY: PyGraph._native_copy is optimized
(with_mirror single-pass); PyMultiGraph._native_copy just delegates to the generic
copy() — never optimized. REFINED (cc): MultiGraph.copy ALREADY bulk-clones the inner via
inner.clone_with_fresh_policy() (br-copyclone) — it is NOT missing the bulk path.
The residual ~23ms is the unavoidable per-element work: ~6000 shallow Python
attr-dict copies (node_py_attrs + edge_py_attrs keyed by (u,v,key)) + MultiGraph's
heavier keydict/edge-key structure (vs DiGraph's flat (u,v)). This is the per-element
PyO3 materialization wall again, NOT a simple bulk-clone fix. jelx1 reduces to the
same fundamental frontier as compose/relabel.

## __deepcopy__ (copy.deepcopy(G)) — PARTIAL fix, still substrate-walk-bound

| Type | fnx | nx | ratio | Note |
| --- | --- | --- | --- | --- |
| DiGraph.deepcopy | 16.7ms | 11.7ms | 0.70x | improved from 0.53x via immutable fast-path (928875302) |
| Graph.deepcopy | 22.8ms | 9.9ms | 0.43x | LOSS |
| MultiGraph.deepcopy | 39.7ms | 15.2ms | 0.38x | LOSS |

The copy.deepcopy fast-path (same lever as bjomp) helps, but __deepcopy__ uses the
Python _graph_deepcopy which WALKS nodes/edges views + out[u][v] per element — the
substrate walk is the residual bottleneck. Unlike copy()/to_directed (now WINS via
the native path), __deepcopy__ has no native same-type deep-copy. Filed br-r37-c1-489mp.

## Weighted pagerank — WIN when built-with-weights; my "loss" was a benchmark artifact

HONEST CORRECTION (cc): an initial measurement showed weighted pagerank 0.68-0.91x
LOSS. ROOT CAUSE: my benchmark set weights via `fg[u][v]["weight"]=w` (POST-
CONSTRUCTION mutation), which materializes the edge mirror + marks the graph dirty,
triggering `_fnx_sync_edge_attrs_to_inner` (O(E), ~10ms@1k edges, the cProfile
bottleneck). Re-measured on graphs BUILT with weights (add_edge(weight=w), the
realistic case): weighted pagerank is a **3.16x (n=400) / 5.00x (n=1000) WIN**
(parity True). The narrow REAL gap is mutated-weight pagerank (0.45-0.81x) — the
dirty-edge sync is all-or-nothing (syncs ALL edges when any is mutated). Potential
future lever: incremental/per-edge dirty sync. But the realistic build-with-weights
path WINS. LESSON (again): how you set up the graph in a benchmark can BE the
result — node_link_data + weighted-pagerank both bit me; warm + realistic
construction matters.

## MULTIGRAPH pipeline — measured LOSS 0.50x (connected_components 114x + construction)

The third graph type. MultiGraph analysis pipeline: fnx 0.56x@n=500 / 0.50x@n=1500
(vs undirected 20-32x / directed 5-9x WINS). Per-op (n=1500): degree_centrality
1.02x NEUT, density/number_of_edges trivial WINS, but: **connected_components 0.07x -> 1.06x FIXED (a844588e1)** — isolated to 7.99ms vs same-structure Graph 0.07ms = 114x; the
_raw_connected_components MultiGraph path is pathologically slow (should use int-CSR
like Graph since connectivity ignores multiplicity). FILED br-r37-c1-fyxma. Plus the
construction-substrate losses: copy 0.57x (jelx1), subgraph 0.47x, to_scipy 0.39x.
MULTIGRAPH was fnx's one genuinely-losing realistic surface; CC now FIXED (0.07x->1.06x, parity 15/15) — residual loss is to_scipy_sparse_array ONLY in the weight=str+dtype=None default (0.41x: cProfile shows _native_edge_view_list
materializes all edge instances + a Python COO loop with dict.get/append per
instance — fix = the _probe_native_missing_default_weight pattern the Graph path uses, routing unweighted multigraphs to the EXISTING native adjacency_arrays_multigraph). NOTE: weight=None=1.20x WIN + dtype=float=1.25x WIN — the native multigraph COO already wins; only weight=str+dtype=None falls to Python — and that is CORRECTNESS-REQUIRED, not
a missed optimization: TESTED relaxing the gate and it is UNSAFE — for str weights
the native adjacency_arrays_multigraph silently returns 1.0 while nx RAISES
ValueError. The gate (dtype given for weight=str) is correct; the Python fallback
matches nx's str-weight error. 4th setup-artifact; the residual case is
correctness-gated, NOT fixable. + construction (copy/subgraph = tbh4q attr-copy wall) — driven by the
connected_components kernel + the attr-copy construction wall.

## Broad differential conformance sweep — CLEAN (undirected 23fn + directed 14fn + multigraph 3fn)

Swept 23 functions vs nx (triangles, clustering, square_clustering, core_number,
closeness/harmonic/degree centrality, pagerank, katz_numpy, constraint,
effective_size [undirected], eccentricity, average_clustering, transitivity,
node_clique_number, number_of_cliques, local/global_efficiency, s_metric,
wiener_index, estrada_index, degree_assortativity, rich_club). RESULT: all match nx.
Two apparent divergences were FALSE POSITIVES: rich_club_coefficient default
normalized=True is RANDOMIZED (normalized=False matches exactly); wiener_index on a
disconnected graph is inf in both (comparison artifact: inf-inf=nan). No real
regressions beyond effective_size (qbj9u, caught+reverted). The function surface is
conformance-correct. DIRECTED sweep (14 fns incl pagerank/betweenness/triadic_census/
reciprocity/flow_hierarchy/effective_size) + MULTIGRAPH sweep: also all match nx —
effective_size directed now matches via the revert (re-confirmed). No directed/multi
divergence anywhere.

## Assortativity kernels (9147-9152) — VERIFIED correct + all WINS (fresh build)

Measured head-to-head (attributed gnp(2000), warm min-of-6); parity verified.

| Function | fnx | nx | ratio | Verdict |
| --- | --- | --- | --- | --- |
| degree_assortativity_coefficient | 0.53ms | 41.15ms | 78.3x | WIN |
| average_neighbor_degree | 0.36ms | 5.64ms | 15.82x | WIN |
| average_degree_connectivity (9152) | 7.18ms | 18.98ms | 2.64x | WIN |
| degree_pearson_correlation | 28.9ms | 70.2ms | 2.43x | WIN |

All parity-correct. Another healthy code-first batch (CrimsonRiver 9147-9152).

## Recent code-first kernels (9153-9155) — VERIFIED correct + wins (fresh build)

Measured the latest code-first 'batch-test pending' kernels head-to-head (parity +
perf). All correct (45/45 expansion/cut parity, flow_hierarchy clean) — unlike
effective_size (the one that diverged). Perf (attributed gnp(2000), warm min-of-6):

| Kernel (bead) | fnx | nx | ratio | Verdict |
| --- | --- | --- | --- | --- |
| flow_hierarchy (9154) | 0.012ms | 2.60ms | 219x | WIN |
| edge_expansion (9155) | 0.39ms | 5.97ms | 15.33x | WIN |
| cut_size (9155) | 3.23ms | 5.28ms | 1.63x | WIN |
| node_expansion (9153) | 0.78ms | 0.77ms | 0.99x | NEUTRAL |

These are correct + (mostly) big wins — the code-first kernel pipeline is healthy;
effective_size (qbj9u) was the lone diverger, caught by the scaffold + reverted.

## SCAFFOLD-VALIDATED WIN: betweenness k-sampling (8ox3z) landed correctly

My 8ox3z lever (native k-sampled betweenness) was IMPLEMENTED (CrimsonRiver) and is
now a MASSIVE WIN: betweenness_centrality(gnp(600,.03), k=50, seed=1) fnx 1.5ms vs
nx 76.5ms = **49.78x** (was 0.89x LOSS — delegated to nx). VALUE PARITY vs nx
verified (True) by my scaffold test_betweenness_k_sampled_conformance_guard.py
(in the 1480-pass certification). The lever+scaffold pattern delivering: filed the
lever + the guard, kernel landed, guard confirmed it's correct AND it's a 50x win.
dijkstra_path single-pair (j5u29) improved 0.12x->0.42x (partial; still a loss).

## SCAFFOLD CAUGHT A REGRESSION: qbj9u directed effective_size kernel diverged (REVERTED)

The qbj9u directed effective_size kernel (effective_size_directed_rust) LANDED on
HEAD and DIVERGED from networkx by ~0.2/node on simple unweighted DiGraphs (node 0:
fnx 2.6 vs nx 2.8; 12 of 20 random seeds failed). Caught by
test_effective_size_directed_conformance_guard.py — the scaffold I filed WITH the
qbj9u lever, exactly as designed. REVERTED the directed routing in __init__.py
(d95c18bc0); directed now flows through the nx-correct matrix/parity fallback
(verified 0 divergences over 20 seeds). Flagged CrimsonRiver to fix the kernel
formula (mutual-weight / redundancy normalization). Full guard suite after fix:
1480 pass, 0 fail. LESSON: file-the-lever + ship-the-scaffold WORKS — the guard
caught a wrong kernel implementation before it could ship.

## CORRECTION: dijkstra_path single-pair — kernel ALREADY early-exits; cost is projection build

HONEST CORRECTION (cc) of the j5u29 diagnosis: I claimed dijkstra_path computed full
SSSP with no target early-exit. WRONG — the kernel shortest_path_weighted (lib.rs:1117)
DOES early-exit (`if u == target { break; }` line ~1189). Re-measured built-with-weights
(not the mutation-artifact): 0.22x@n=400 / 0.54x@n=1000, parity True. cProfile: 100% in
_fnx.dijkstra_path (21ms/call). The REAL bottleneck is the per-call O(E)
dijkstra_weighted_undirected_projection build — fnx builds the full weighted projection
(O(E)) before the early-exit dijkstra, while nx reads weights lazily per edge. For a
near target the projection build dwarfs the tiny BFS. FIX — CORRECTED AGAIN (cc): NOT the projection build either — weighted_undirected_projection
BORROWS the inner for SIMPLE graphs (algorithms.rs:416, no build). The real cost is that
shortest_path_weighted (lib.rs:1117) is STRING-KEYED (HashMap<&str,f64> distances + heap);
the per-node String hashing is the tax. LEVER (filed br-r37-c1-lc2qy): integer-relabel the
weighted dijkstra (CSR), like the Edmonds-Karp flow fix. LENGTH is order-invariant (safe);
PATH needs nx's counter-based tie-break (also fixes n30yf). 3rd dijkstra correction. REFINED: the dijkstra loss is NARROW — dijkstra_path_LENGTH
WINS 1.81x and single_source_dijkstra_path_length WINS 2.48x (fast kernels); ONLY the
single-pair dijkstra_PATH loses 0.47x. That path variant is BOTH String-keyed-slow AND
tie-divergent vs nx (n30yf) — lc2qy (integer-relabel + nx counter tie-break) fixes both
at once. Routing dijkstra_path to the fast length kernel does NOT help: its predecessors
still need nx's exact tie-break. SHIPPED (cc): routed dijkstra_path -> single_source_dijkstra_path[target] (nx-correct,
1245/1245 + 2332/2332 parity) — FIXES n30yf (conformance) + 0.47x->1.28x (moderate
target). RESIDUAL lc2qy: single_source has no early-exit, so far targets are 0.58x; a
single-pair EARLY-EXIT variant of the fast kernel (integer + nx tie-break) is the full
win. n30yf RESOLVED via the routing. THIRD honest correction (after node_link_data +
weighted-pagerank) — measuring honestly enough to falsify my own prior diagnosis.

## NEGATIVE: __deepcopy__ -> to_directed routing is a DEAD END (tested 2026-06-18)

Tested the obvious 489mp shortcut — route DiGraph.__deepcopy__ to the existing
native _native_to_directed_deepcopy (which makes to_directed a 1.14x WIN). RESULT:
to_directed is structurally + deep-semantically identical to deepcopy (verified),
BUT it is actually SLOWER than the current _graph_deepcopy (20.96ms vs 17.44ms on
DiGraph(1500)) AND drops the frozen flag (to_directed preserves frozen=False;
deepcopy must preserve it). So reusing existing native build methods for __deepcopy__
is a regression + a correctness break. DO NOT retry. 489mp requires a NEW dedicated
native same-type deep-copy binding (not a reuse); the Python _graph_deepcopy with the
immutable fast-path (928875302) remains the best available (DiGraph 0.70x).

## Eigensolver-gate detail (the headline reversal)

`symmetric_eigvals_rust` (safe-Rust eig) was used unconditionally on the general
dense path of laplacian/adjacency/modularity_spectrum. Profiled crossover n=30..300:
it is **2.3-4x slower than np.linalg.eigvalsh (LAPACK) at EVERY n**, identical
eigenvalues (1e-7) + identical ascending order. laplacian_spectrum was **2.4x
SLOWER than nx** because of it. Gate (n<=64 safe-Rust, LAPACK above) → measured
**1.32x WIN**. The other two were already winning (nx runs non-Hermitian dgeev);
the gate widened the margin. Commits 1f2338b8a + 6e8dd288d.

## NO-SHIP (CORRECTED): adjacency() outer-dict cache — FALSIFIED by durable per-crate Criterion bench (2026-06-24, CopperCliff)

**RETRACTION (2026-06-24):** the "0.95-0.99x" result below was a MEASUREMENT ARTIFACT of
interleaved-min-of-21 Python timing taken across SEPARATE processes under heavy host load (the
"after" run happened to see a slower NetworkX, inflating the ratio). When BlackThrush re-measured
with the directive's authoritative methodology — `cargo bench -p fnx-python --bench
networkx_head_to_head adjacency_outer_cache` on a durable remote worker (ovh-a) — the cache showed
**NO gain**, staying at the same 0.54-0.64x floor as baseline:

| workload | FNX median | NetworkX median | ratio vs nx |
| --- | ---: | ---: | ---: |
| `Graph dict(adjacency())` n=2000 | 88.5 us | 49.1 us | 0.55x |
| `Graph dict(adjacency())` n=8000 | 370.9 us | 206.9 us | 0.56x |
| `DiGraph dict(adjacency())` n=2000 | 164.4 us | 104.4 us | 0.64x |
| `DiGraph dict(adjacency())` n=8000 | 698.3 us | 377.2 us | 0.54x |

VERDICT: ~0-gain → REVERTED (production code never landed; BlackThrush reverted in `7b3b5811a` and
kept the focused Criterion group as negative evidence). Hypothesis for why the outer cache doesn't
help even warm: the underlying `dict_of_dicts_cache` likely misses on warm `adjacency()` calls
(rows rebuilt every call), so caching the OUTER dict on top saves nothing measurable; the real cost
is the rows rebuild + the user-side `dict()` copy, not the outer assembly. LESSON: use the per-crate
`cargo bench` (controlled before/after on ONE worker) as the authority — NOT cross-run interleaved
Python timing, which the host-noise confound can flip. Branch `cc-adjouter-land-20260624` abandoned.
The original (now-falsified) write-up is retained below for the record.

---

## (SUPERSEDED — see retraction above) adjacency() outer-dict cache — 0.55-0.62x -> 0.95-0.99x vs nx (2026-06-24, CopperCliff)

Lever (br-r37-c1-adjouter): `Graph.adjacency()` / `DiGraph.adjacency()` route through
`_fnx.adjacency_dict_shared` -> `share_dict_of_dicts_cache`, which serves the nested
`{node: shared_row}` snapshot. The per-EDGE rows were already cached (and shared, so
`r1[u] is r2[u]` matches nx's live-`_adj` contract), BUT the OUTER `{node: row}` dict was
rebuilt from scratch on EVERY call — one `set_item` per node, O(V). So `dict(G.adjacency())`
paid that redundant O(V) outer rebuild on TOP of the user-side `dict()` copy, while nx's
`adjacency()` returns `iter(self._adj.items())` and builds NOTHING. Measured **0.55-0.62x
vs nx**.

Fix: cache the outer dict on `DictOfDictsCache` (new `shared_outer: Mutex<Option<Py<PyDict>>>`,
lazily filled in `share_dict_of_dicts_cache`). Warm repeated calls — and every internal
`_native_adjacency_dict()` consumer (e.g. `average_degree_connectivity(weight=...)`) — reuse
the SAME outer object. Safe because (a) the public wrapper hands out `iter(outer.items())`,
never the dict itself, so callers cannot mutate it; (b) all `_native_adjacency_dict()` callers
read-only; (c) the whole cache (incl. `shared_outer`) is replaced wholesale on any
nodes_seq/edges_seq change, so the cached outer can never outlive its rows.

Why not the 6.7x fast-merge path: returning the dict directly so `dict()` C-fast-merges
(measured 6.7x) is BLOCKED by nx's contract — `nx.Graph.adjacency()` returns a single-use
`dict_itemiterator` (isinstance-dict == False, `len()` -> TypeError, exhausts on reuse). A
dict-subclass would diverge on all three; rejected. Caching the outer reaches PARITY without
any contract change — the irreducible remainder is the user-side `dict()` sequence-of-pairs
copy, which nx also pays once.

Measured (interleaved min-of-21, inner=3, BA n,m=4, paired graphs, same artifact env;
ratio = nx/fnx, >1 = fnx faster):

| workload | baseline (HEAD) | after | 
| --- | ---: | ---: |
| `[Graph] dict(adjacency())` n=2000 | 0.56x | 0.97x |
| `[Graph] dict(adjacency())` n=8000 | 0.55x | 0.95x |
| `[DiGraph] dict(adjacency())` n=2000 | 0.62x | 0.99x |
| `[DiGraph] dict(adjacency())` n=8000 | 0.56x | 0.99x |

Behavior proof:
- Direct artifact parity (paired BA n=300): content equality, two-call row identity
  (`a1[u] is a2[u]`), inner == live `G[u][v]`, live edge-attr mutation reflected, cache
  invalidation on `add_node`, iterator yields (node,row) pairs, `next()` works — all 4 graph
  paths PASS.
- `_native_adjacency_dict()` consumer parity: `average_degree_connectivity(G, weight="weight")`
  byte-equal to nx.
- pytest: 237 passed (adjacency_cache_consistency_guard, adj_mapping_parity, adj_row_key_parity,
  adjacency_data_native_parity, adj_item_readonly_parity, edge_subgraph_adjacency_parity,
  view_surface_mutation_parity, lazy_materialization_stress_guard); broader affected sweep
  (-k "adj or to_dict or dict_of_dicts or convert or assortativ or average_degree or copy or
  subgraph") 3505 passed, 9 skipped, 0 failed.
- cargo fmt --check, clippy -D warnings, git diff --check: all clean.

Files: crates/fnx-python/src/lib.rs (DictOfDictsCache struct + 1 init site),
crates/fnx-python/src/readwrite.rs (share_dict_of_dicts_cache + 2 init sites),
crates/fnx-python/src/digraph.rs (1 init site). Disjoint from BlackThrush's concurrent
size(weight)/weighted_degree int work (lib.rs L4021-8869).

Landing: branch `cc-adjouter-land-20260624` commit `8e880c0bd` (rebased onto current main,
re-built + re-benched 0.95-0.99x, 867 conformance pass). To avoid a double-land, the CODE is
landing via BlackThrush's in-flight batch (their working tree carries this exact patch under
their exclusive lib.rs/readwrite.rs/digraph.rs locks); this ledger entry lands the measured
evidence. Attribution: br-r37-c1-adjouter (CopperCliff).

## 2026-06-25 CopperCliff to_directed scalar deepcopy-skip - NO-SHIP ~0-gain (br-r37-c1-eilce family)

(Recorded here, not the shared NEGATIVE_EVIDENCE.md, which BlackThrush holds reserved.)

Attempted the deferred construction lever: in PyGraph::_native_to_directed_deepcopy, skip Python
`copy.deepcopy` for LOSSLESSLY-representable edge attrs (scalars + maps-of-scalars) and lazy-materialize
the directed graph's mirror (fresh PyDict per read == deepcopy semantics for value types), falling back
to deepcopy for None/list/object/non-str-key. Added loss-reporting `py_value_to_cgse_checked` /
`py_dict_to_attr_map_checked` (CgseValue has no object variant -> non-representable values stringify, so
representability == lossless round-trip).

CORRECTNESS: PERFECT (7/7) — edge+node data parity vs nx across scalar/list/nested-dict/None/object/
attr-less; deepcopy INDEPENDENCE verified (mutating directed scalar/nested/list attrs leaves source
unchanged). Real trap found+fixed: DiGraph `nodes(data=)` does NOT lazily materialize node attrs from
the store (edges do) — a lazy node mirror DROPS the attr; nodes keep the eager mirror, only EDGES use
the lazy fast path.

Per-crate A/B (Graph.to_directed, gnm n2000/e16000, all-weight, min-of-9): baseline fnx 70.6/nx 62.8 =
0.889x; after fnx 78.1/nx 70.3 = 0.900x (host ~10% slower that round; RATIO unchanged). Removing 32000
Python deepcopy calls registered NOTHING.

Decision: NO-SHIP (REVERT, stash cc-todir-NOSHIP). 4th NO-SHIP this session confirming the same floor:
removing ONE per-edge cost component is swamped — CPython scalar-dict deepcopy is cheap; the 0.9x
residual is the dual-AttrMap+mirror CONSTRUCTION body, not the deepcopy. The conversion helpers are
correct and could seed a future single-storage (lazy-AttrMap) rewrite — architectural, not a micro-opt.

PEER COLLISION: shared bench carries an uncommitted `ConstructionCopyWorkloads` /
`fnx_graph_to_directed_scalar_attrs` hunk (TealSpring owns the bench) — a peer is actively on this exact
target. Left their hunk untouched; messaging them that the deepcopy-skip angle is ~0-gain.

## 2026-06-25 CopperCliff set_edge/set_node_attributes broadcast - NO-SHIP ~0-gain (eager-mirror floor)

BOLD-VERIFY broad sweep found the biggest UN-swept gaps are attribute WRITE paths:
set_node_attributes(G, scalar, name) 0.22x, set_edge_attributes(G, scalar, name) 0.39x,
get_edge_attributes 0.49x vs NetworkX (BA n3000/e24000). The scalar-broadcast branches looped in
Python (`for n in G.nodes(): G.nodes[n][name]=v` / `for u,v,attrs in G.edges(data=True):
attrs[name]=v`) whereas the DICT branches already had native fast paths.

Attempt 1 (native per-element broadcast: one Rust pass, materialize mirror + set_item): correctness
6/6 but ~0-gain (set_node 0.22->0.23x, set_edge 0.39->0.37x). The loop overhead was NOT the
bottleneck — the per-element String-keyed mirror entry + PyO3 `set_item` is.

Attempt 2 (edge STORE-WRITE: when `edge_py_attrs.is_empty()` + value losslessly representable, write
the CgseValue store in one index-native Rust pass via new `Graph::set_attr_on_all_edges`, zero PyO3
per edge; reads materialize back from store): correctness parity-exact vs nx (incl. non-representable
list -> fallback, kernel degree(weight) sees it). But STILL ~0-gain: set_edge 0.39->0.43x on BA AND
0.44x on a fresh `add_edges_from` graph. ROOT CAUSE: `edge_py_attrs` is NOT empty even for freshly
constructed graphs — edge construction pre-populates EMPTY mirror PyDicts (eager), so the
`is_empty()` gate never fires and the per-edge PyO3 fallback always runs. Empty mirrors also SHADOW
the store on read, so a store-write without clearing them would be wrong anyway.

Decision: NO-SHIP (REVERT, stash cc-setattr-NOSHIP). The node broadcast can't use store-write at all
(nodes(data) reads the mirror, not the store). The REAL lever for the whole set/get-attr family is
LAZY edge-attr construction (stop allocating empty mirror PyDicts per edge — partial work exists,
br lazy_edge_attr_dict; once mirrors are truly absent on fresh graphs, the store-write fast path
fires and set_edge_attributes(scalar) becomes a Rust-only O(E) pass). That is an architectural
construction change, not a setter micro-opt. NOTE: a peer already landed a `_native_broadcast_edge_attribute`
in HEAD (different approach); my store-write is superseded + reverted. 6th convergent NO-SHIP this
session confirming the eager-mirror / String-keyed-PyO3 attr substrate floor.

## 2026-06-25 CopperCliff FRONTIER MAP - fnx vs nx is fully verified; only the String-keyed attr substrate remains

Consolidated BOLD-VERIFY across this session (~55 functions, 8 sweep rounds, all per-crate / warm
min-of-N). fnx is AT-OR-ABOVE NetworkX on every domain measured EXCEPT one. Ship future effort
accordingly — do not re-sweep the won domains.

WON (fnx faster, representative ratios):
- algorithms: cut_metrics 3-5x, assortativity (degree_mixing_dict 8.6x, node_degree_xy 5x), SCC 2.8x,
  descendants 1.8x, biconnected/articulation 3.5-10x, MST/bfs ~1.2x, core_number 16x, k_core 55x,
  clustering 124x, pagerank 26x, closeness 189x, harmonic 273x, eccentricity 13x.
- matrix/IO: adjacency_matrix / to_scipy_sparse / laplacian 2.4x, node_link_data 1.4x,
  parse/generate_edgelist 1.1-1.2x.
- community/iso: greedy_modularity 27x, label_propagation 1.9x, is_isomorphic 387x.
- construction: G.copy 1.7x, grid_2d 3.25x, line_graph 2.2x, from_dict_of_dicts(attrs) 1.4x,
  to_dict_of_lists 1.9x, single_source_shortest_path 1.8x, bfs/dfs_tree 3.2-3.5x.

FLOORED (the ONLY remaining vs-nx gaps — ALL the String-keyed attr substrate):
- set_node_attributes(scalar) 0.22x, set_edge_attributes(scalar) 0.39x, get_edge_attributes 0.49x,
  in_edges(data=attr) 0.29x, edges(keys=True) 0.61x, weighted degree views 0.7-0.9x,
  to_directed 0.89x, relabel 0.70x.
ROOT CAUSE (single, architectural): fnx stores attrs as `BTreeMap<String, CgseValue>` (the store) PLUS
a String-keyed Python mirror, while nx uses Python dicts with INTERNED string keys. Every per-element
attr write needs a per-element String key allocation (the store) or a PyO3 set_item on the String-keyed
mirror; nx reuses one interned key object and does C dict ops. This session proved 6 distinct micro-opts
against it all ~0-gain (degree index-accumulator, in_edges edge_key removal, to_directed deepcopy-skip,
selfloop [shipped the one that fit], set-attr per-element broadcast, set-attr store-write). The
store-write is correct but ~0-gain because (a) eager empty mirrors shadow it and (b) the per-edge
String key alloc is itself the floor.

ONLY viable lever (large, architectural, NOT a micro-opt): interned attr keys — `Rc<str>`/`Arc<str>` or
a global string-intern table for AttrMap keys + the mirror, so per-element attr writes reuse a shared
key object like nx. Until then these 8 paths are at their floor; further per-element micro-opts are
predictably ~0-gain. The correct store-write (stash cc-setattr-NOSHIP) is ready to fire IF construction
is made lazy AND keys are interned.

## 2026-06-25 CopperCliff BUILDFIX main was non-compiling + dijkstra sync-dirty NO-SHIP

BUILD FIX (SHIPPED): peer commit 0b2df6108 ("native one-pass broadcast") landed
`_native_broadcast_node_attribute` in `impl PyGraph` calling `self.ensure_node_py_attrs`,
which is PyMultiGraph-only (PyGraph has `materialize_node_py_attrs`). main did NOT COMPILE
(error[E0599]). Fixed: ensure_node_py_attrs -> materialize_node_py_attrs. Build green,
correctness 0 fails, node-broadcast parity vs nx intact.

DIJKSTRA SYNC-DIRTY NO-SHIP (reverted): found a real non-attr gap — astar/dijkstra/bellman
single-pair weighted 0.5-0.7x vs nx. Decomposed: the native kernel `dijkstra_path_to_target`
is 0.578ms (5.6x FASTER than nx); the Python wrapper adds ~6.3ms — `_sync_rust_edge_attrs(edge_only)`
re-syncs O(E) EVERY call (~4.35ms). Root: `edges_dirty` is set true on edge-attr exposure but
`store(false)` appears NOWHERE — it's sticky, so every weighted kernel re-syncs forever after any
edge mutation. Clearing it after sync gave dijkstra 5.65x / astar 6.73x / bellman 2.21x (!!), BUT
CORRECTNESS FAILED on `G[u][v]['weight']=x`: the canonical subscript-set does NOT call
mark_edges_dirty (only edges(data=) views + explicit mutation paths do), so after a clear the next
subscript mutation is invisible to kernels. That is exactly why the flag was never cleared (sticky +
always-sync is the only safe option without a mutation-detecting edge dict). REVERTED.
REAL LEVER (architectural): make the edge attr dict a custom mapping that marks edges_dirty on
__setitem__/__delitem__, OR track a per-edge dirty-key set populated by subscript mutation — then the
dirty flag can be cleared and the sticky O(E) re-sync (which taxes dijkstra/astar/bellman/to_scipy/
cut_size after any edge mutation) becomes a no-op when clean. The kernel is already 5.6x faster than
nx; only the wrapper's mandatory re-sync stands between fnx and a 5x+ shortest-path win.

## 2026-06-25 CopperCliff dijkstra sync-dirty REFINEMENT (handoff to BlackThrush — lib.rs owner)

Refines the prior sync-dirty entry with a key finding: `AtlasView::__getitem__` (views.rs:1047)
ALREADY calls `mark_edges_dirty()`, so `G[u][v]['w']=x` DOES re-mark dirty on access. That means
clearing `edges_dirty` after `_fnx_sync_edge_attrs_to_inner` is CLOSER to safe than I thought — the
common subscript-mutation pattern re-marks via the getitem.

Yet my clear-after-sync STILL returned the stale path on `G[u][v]['weight']=0.5; dijkstra(...)`.
So the residual bug is NOT missing dirty-marking; suspect the dijkstra wrapper's weight-check cache
`_fnx_dijkstra_weight_check_cache` (gated on `not edge_attrs_dirty`) OR a second dirty channel /
ordering between `_should_delegate_dijkstra_to_networkx` and `_sync_rust_edge_attrs`. Plus the
held-ref hazard (`d=G[u][v]; sync; d['w']=x`) won't re-mark.

HANDOFF (mail DB is in durability-error state, can't send — recording here): BlackThrush owns
`crates/fnx-python/src/lib.rs` (push-guard confirmed live reservation). The lever is theirs to land:
clear edges_dirty after both PyGraph sync methods (+ DiGraph siblings), resolve the weight-check-cache
interaction, gate `-k "dijkstra or astar or bellman or weight or shortest or sparse"` conformance +
the subscript-mutation probe. Payoff: dijkstra 5.65x / astar 6.73x / bellman 2.21x faster than nx
(raw kernel is already 5.6x faster; only the wrapper's sticky O(E) re-sync stands in the way), and it
also de-taxes to_scipy_sparse / cut_size after any edge mutation. I reverted my attempt cleanly.

## 2026-06-25 CopperCliff to_prufer_sequence O(n^2)->O(n) — KEEP (2.69x faster than nx)

`to_prufer_sequence` was 0.55x vs NetworkX. Decomposition: validation (is_tree 0.01ms, label set-check
0.066ms) negligible; the native kernel `fnx_algorithms::to_prufer_sequence` was 3.66ms — slower than
nx's whole pure-Python prufer (2.04ms). Root cause: the kernel was O(|V|^2) — it rescanned `(0..n)` for
the smallest alive leaf EVERY iteration and counted alive neighbours via a HashSet filter per candidate.

Fix: standard O(|V|) Prüfer with a monotonic `ptr` + degree array. `ptr` only advances; when removing a
leaf creates a smaller leaf we process it immediately, else advance to the next degree-1 node. Each
leaf's lone remaining neighbour is the single degree>0 entry in its adjacency (sum of neighbour scans =
O(sum deg) = O(|V|) for a tree). Output is byte-identical (still smallest-leaf-first).

Per-crate build + bench (balanced_tree(2,10), 2047 nodes): fnx 3.67ms -> **0.790ms**; nx 2.12ms;
**0.55x -> 2.69x faster** (~4.6x self-speedup). Correctness: parity vs nx on balanced(2,8)/path(500)/
star(300)/balanced(3,5) + 20 random labelled trees, and from_prufer(to_prufer(T)) round-trip exact — 0
fails. Kernel in fnx-algorithms/lib.rs (TealSpring's, but last-active 4 days = stale; push-guard backstop).

## 2026-06-25 CopperCliff partition family: route Random-seed SBM to native batch — KEEP (0.50x->0.79x)

gaussian_random_partition_graph was 0.50x vs nx, random_partition 0.79x. Root cause: gaussian passes
`seed=rng` (a live `random.Random` from `_generator_random_state`), so `_sbm_impl`'s native gate
(`seed is None or isinstance(seed,int)`) FAILED and it delegated to `_nx.stochastic_block_model` +
`_from_nx_graph` conversion (the construction tax). random_partition with an int seed already hit the
native `_sbm_native` batch path (0.79x).

Fix (pure-Python, __init__.py): `_sbm_native` now consumes a passed `random.Random` directly
(`rng = seed if isinstance(seed, Random) else Random(seed)`) and `_sbm_impl`'s gate accepts a Random
instance. Byte-exact: nx threads the same rng into its SBM, and `_sbm_native` reproduces nx's exact
draw order (combinations_with_replacement/product + geometric-skip), so consuming the same rng yields
identical edges. Now gaussian/random-partition/any-Random-seed SBM caller hits the native batch
instead of the nx round-trip.

Result: gaussian_random_partition_graph(600,40,10,0.3,0.01) fnx 11.8ms -> 7.5ms (1.57x self),
0.50x -> 0.79x vs nx. Parity: byte-exact (sorted nodes+edges) vs nx on gaussian (seeds 1/2/7/42/123),
random_partition (1/5), and SBM with a Random-instance seed — 0 mismatches. Conformance
`-k "partition or stochastic_block or sbm or caveman"`: 662 passed, 0 failed. Residual 0.79x is the
shared `_sbm_native` Python geometric-skip generation floor (a native Rust SBM sampler reproducing
nx's RNG sequence would close it — future, like the gnp_directed precedent c17d7a484).

## 2026-06-25 CopperCliff partition-family native-SBM-sampler lever (surface — needs native RNG port)

After shipping the gaussian Random-seed routing fix (c260e6317, 0.50x->0.79x), the WHOLE partition
family (random_partition / planted_partition / gaussian / stochastic_block_model) sits at ~0.79-0.83x
vs nx — the floor is the shared Python `_sbm_native` geometric-skip generation (byte-exact but
Python). relaxed_caveman_graph is 0.65x (per-edge rewire mutation, sequential RNG dependency).

To go BELOW 1.0x: a NATIVE Rust SBM sampler reproducing nx's exact draw sequence. The infra exists:
- Native `PythonRandom` (MT19937 + gen_res53 + _randbelow) at fnx-algorithms/lib.rs:12243 — already
  used by other byte-exact generators (gnp_directed c17d7a484, louvain).
- Byte-exact REFERENCE: Python `_sbm_native` in __init__.py (combinations_with_replacement/product
  block order + geometric-skip `floor(log(1-rand)/log(1-p))`).
- A native `stochastic_block_model` ALREADY exists at fnx-algorithms/lib.rs:37994 + binding
  generators.rs:1001 — but it uses a NON-nx LCG (`wrapping_mul(6364136223846793005)`), so it can
  never be byte-exact (my memory's "~25% edge count" = wrong RNG entirely). REPLACE its body with a
  port of `_sbm_native` over `PythonRandom`.
Then route `_sbm_impl` to the (now byte-exact) native binding for int/None/Random-instance seeds.
NOTE: that routing edit is in __init__.py (BlackThrush-reserved) + the kernel is fnx-algorithms
(TealSpring, stale). Expected payoff: whole partition family ~0.79x -> ~2x (like other native gens).
Deferred (multi-build, byte-parity-critical, reservation-touching) rather than half-done.

## 2026-06-25 CopperCliff is_distance_regular degree-2 cycle fast path — KEEP (6x faster than nx AND correct)

BOLD-VERIFY found is_distance_regular at fnx 204ms vs nx 0.54ms on cycle(800) (~0.00x). DECISIVE: this
is an nx CORRECTNESS BUG, not an fnx perf gap. nx's intersection_array uses an early diameter bound
`(8*log2 n)/3` that is only valid for valency>=3 distance-regular graphs; a cycle C_n has degree 2 and
diameter n/2, violating the bound, so nx EARLY-EXITS and returns False — WRONG, every cycle is
distance-regular. fnx's native _raw_is_distance_regular does the full O(V*(V+E)) intersection array and
returns the CORRECT True (in 204ms). Verified: cycle(50/200/800) -> fnx True (correct), nx False (wrong);
icosahedral/petersen/complete/hypercube -> both True.

Fix (pure-Python, __init__.py): after the regular+connected pre-check, a connected 2-regular graph is
exactly a single cycle C_n, which is always distance-regular -> return True in O(1) (skip the 204ms
native pass). Stays CORRECT (unlike nx). Result: is_distance_regular(cycle(800)) fnx 204ms -> 0.095ms
(~2150x self), 6.04x FASTER than nx AND correct (True vs nx's wrong False). Correctness 0 fails across
cycles / known DR graphs / non-DR / disconnected-deg2; conformance -k distance_regular 28 passed/0 failed.

NOTE: do NOT "match nx's speed" by adopting its diameter-bound early-exit — that would regress fnx to
nx's incorrect False on cycles. This is a case where fnx is MORE correct than NetworkX.

## 2026-06-25 CopperCliff tree_broadcast_center: drop graph clone+remove — KEEP (0.24x->1.22x)

tree_broadcast_center was 0.24x vs nx (fnx 17.6ms vs 4.2ms on balanced_tree(2,9)=1023 nodes). The
native kernel `fnx_algorithms::tree_broadcast_center` peeled leaves by `reduced = graph.clone()` then
`reduced.remove_node(leaf)` once per leaf — a full String-keyed graph clone + O(V) graph mutations
(each rehashing adjacency) = the cost (the per-iteration DP `tree_broadcast_max_value` is only O(deg)).

Fix (fnx-algorithms, no clone/mutation): peel using a `removed: HashSet<String>` + `degree:
HashMap<String,usize>` over the ORIGINAL graph — `reduced.remove_node` becomes `removed.insert` +
decrement the leaf's alive neighbour's degree; `reduced.neighbor_count` -> `degree[..]`;
`reduced.neighbors(leaf).next()` -> first non-removed neighbour; final root -> first non-removed node
in `nodes_ordered()`. Same peeling order, value DP, and String-name min tie-break -> byte-identical
(broadcast_time + center set).

Result: balanced_tree(2,9) fnx 17.6ms -> 3.43ms (~5x self), 0.24x -> 1.22x (now FASTER than nx).
Parity: tbc center + value + tree_broadcast_time byte-exact vs nx on balanced(2,9)/path(500)/star(300)/
balanced(3,5)/balanced(2,3) + 15 random labelled trees, 0 fails.

## 2026-06-25 CopperCliff subgraph_centrality: np.linalg.eigh -> scipy.linalg.eigh — KEEP (0.25x->34x)

subgraph_centrality was 0.25x vs nx (fnx 99.7ms vs ~25-96ms on BA(150,3)). fnx used `np.linalg.eigh`
which on this BLAS build dispatches the 'evd' divide-and-conquer driver (or numpy's reference LAPACK):
np.linalg.eigh = 69ms vs scipy.linalg.eigh (default 'evr' MRRR driver, optimized BLAS) = 2.5ms at
n=150 — a 27x driver/BLAS difference. nx's centrality path uses scipy, so fnx's numpy eigh was the
outlier.

Fix (pure-Python): swap `np.linalg.eigh(A)` -> `scipy.linalg.eigh(A)`. Result is numerically identical
(eigenvalues match; the combine `sum(exp(lambda) * v^2)` is invariant to eigenvector SIGN and eigenvalue
ORDER, so the 'evr' vs 'evd' driver difference cancels). subgraph_centrality(BA(150,3)) fnx 99.7ms ->
2.77ms (~36x self), now 9-34x FASTER than nx. Parity vs nx: max rel err ~1e-14 across BA(60/150/100/40);
conformance -k subgraph_centrality 110 passed/0 failed.

FOLLOW-UP: other __init__.py spectral sites use np.linalg.eigvalsh (eigenvalues-only, order-invariant ->
SAFE to swap to scipy.linalg.eigvalsh) at lines ~24652/25064/25177/32099/32204/34191, and _matrix_exp
(26277, V*D*V^T sign-invariant). Line 25314 (fiedler) uses eigenVECTORS (sign-sensitive) -> do NOT swap
blindly. Bench+verify each before swapping.

## 2026-06-25 CopperCliff numpy-LAPACK sweep — eigh vein mined; np.linalg.solve is NOT a lever

Follow-up to the subgraph_centrality eigh win (16861f033). Swept the rest of __init__.py's numpy linalg
usage for the same numpy-slow-vs-scipy-fast tax:
- np.linalg.eigh WITH eigenvectors ('evd'/numpy reference LAPACK, ~27x slower than scipy 'evr') — the
  ONLY real tax. Sites: subgraph_centrality (FIXED 16861f033); _matrix_exp -> communicability_exp
  (1.46x faster, fine); fiedler 25314 + spectral_graph_forge 51448 (sign-sensitive vectors / nx
  determinism parity -> MUST NOT swap). Vein exhausted.
- np.linalg.eigvalsh (eigenvalues-only, no vectors) is FAST even on numpy — adjacency_spectrum 27x,
  modularity 17x, estrada 26x, communicability 18x FASTER than nx. Not a lever.
- np.linalg.solve: an ISOLATED microbench showed 222ms vs scipy 1.41ms (n=400), BUT the fnx functions
  that use it ALREADY BEAT nx: katz_centrality_numpy 10x, second_order_centrality 3577x,
  current_flow_betweenness 38x, current_flow_closeness 10x faster. So np.linalg.solve is NOT a real
  gap here — do NOT chase it (red herring; nx is slower for other reasons / the matrices solve fast).
- np.linalg.inv/pinv/eig (non-symmetric): ~parity with scipy (no big tax). eigenvector_centrality_numpy
  1.17-1.68x, pagerank 4.23x, hits 1.18x, information_centrality 9.28x faster.
Also confirmed parity (no fixable gap): communicability_betweenness 0.79x (already uses scipy.linalg.expm
per node, same as nx — variance), laplacian/normalized_laplacian_spectrum ~1.0x, johnson/goldberg_radzik/
antichains ~parity at sub-ms (delegated, conversion tax negligible at these sizes). fnx is at-or-above nx
across the swept algorithm/centrality/spectral/generator domains.

## 2026-06-25 CopperCliff products/bipartite/operators/DAG sweep — REJECTS (modest delegation-tax gaps)

BOLD-VERIFY sweep of previously-unmeasured domains. All fnx at-or-above nx EXCEPT two modest delegation-
tax gaps, both REJECTED (not worth the de-delegation effort for niche functions):
- dag_to_branching 0.71x (fnx 12.2ms vs nx 8.7ms, gn(400)): delegates root-to-leaf path enumeration via
  `_root_to_leaf_paths_via_nx` (fnx->nx conversion) + builds result. The path enumeration is inherently
  expensive (both fnx and nx); the ~3.5ms gap is the conversion + result-graph construction. De-delegating
  needs reimplementing root_to_leaf_paths + prefix_tree in-process — large for a niche fn at 0.71x. REJECT.
- transitive_reduction 0.82x (2.06ms vs 1.69ms): delegated; borderline conversion tax. REJECT (marginal).

WINS confirmed (already fnx-faster, no action): cartesian/tensor/strong/lexicographic_product 2.6-3.7x,
power 1.66x, bipartite.clustering 2.2x, condensation 4.28x, topological_generations 2.37x,
lexicographical_topological_sort 2.96x, closeness_vitality 12.3x, harmonic(subset) 2.88x, voterank 1.56x,
average_degree_connectivity 2.6x, attribute_assortativity 73x. Parity (no fixable gap): bipartite.
projected_graph 0.99x, compose 1.05x, difference 1.12x. fnx is at-or-above nx across these domains.

## 2026-06-25 CopperCliff I/O sweep — parse_adjlist/adjacency_data REJECT (add_edges_from substrate floor)

I/O sweep: most fnx at-or-above nx (node_link_graph 1.33x, generate_adjlist 1.28x, node_link_data 1.25x,
to_dict_of_dicts 1.23x; generate_edgelist/parse_edgelist/generate_gml/cytoscape ~parity). Two gaps, both
REJECTED as construction-substrate-floored:
- parse_adjlist 0.66x (8.1ms): decomposed -> parse loop 1.1ms, but fnx add_nodes_from + add_edges_from
  = 6.86ms vs nx 3.67ms. The construction is the cost, not the parse.
- adjacency_data 0.76x: same family (builds result structure).

ROOT (systematic, quantified): `add_edges_from` itself is ~0.58x vs nx — 6.1ms vs nx 3.5ms for 7500
no-attr edges on a fresh Graph, for BOTH int (5.53 vs 3.28) and string (6.13 vs 3.53) nodes. fnx
already uses the optimized unrecorded bulk path (add_plain_edge_batch -> extend_edges_unrecorded, no
ledger, no eager mirrors, br-r37-c1-89kxg). The residual 1.7x is the DUAL-STORAGE substrate: fnx
maintains String-keyed successors adjacency (IndexMap<String,IndexMap<...>>) PLUS an index-keyed edges
map (IndexMap<(usize,usize),AttrMap>) + per-node-ref canonical stringification, where nx has a single
dict-of-dicts with native keys. This is THE remaining systematic construction lever (it taxes every
parse_*/from_*/read_* and graph-building op) but it is architectural (the edges map backs index-native
edge-attr ops) and has been worked extensively across prior sessions -> not a one-turn change. REJECT.

## 2026-06-25 CopperCliff bipartite hopcroft_karp/maximum_matching top_nodes=None — KEEP (0.33x->20x)

hopcroft_karp_matching(B) / maximum_matching(B) WITHOUT top_nodes were 0.33x vs nx (4.56ms vs 1.52ms,
K(80,80)): the native byte-exact kernel only owned the top_nodes-GIVEN case; with top_nodes=None it
returned None and the wrapper fell to `_nx_bipartite.hopcroft_karp_matching(_matching_nx_view(G))` — a
full fnx->nx conversion (the whole gap).

Fix (Python-only, bipartite.py): `_derive_top_nodes(G, None)` computes the bipartition via native
`bipartite.sets(G)` (~0.03ms) and feeds it to the existing native kernel. Byte-safe: nx's
bipartite_sets(None) returns X={n:color==1}; sets() reproduces X's elements, and CPython set iteration
order is HASH-determined for a fixed element set, so `set(sets(G)[0])` iterates identically to nx's X ->
identical augmenting-path order -> byte-identical matching dict. On any failure (nx-typed/multigraph/
directed/disconnected/non-bipartite) returns None so the original path raises nx's EXACT error
(AmbiguousSolution / NetworkXError preserved — verified vs nx on disconnected gnmk + odd cycle).

Result: K(80,80) 4.56ms->0.071ms, 0.33x->20.48x faster than nx. Parity: 8 gnmk seeds + complete +
string-node + explicit-top + non-bipartite/disconnected error contracts byte-exact; conformance
-k "hopcroft or maximum_matching or eppstein" 415 passed/0 failed. eppstein_matching has NO native
kernel (different algo) -> still delegated (0.55x), left as-is.

## 2026-06-25 CopperCliff REJECT: set-order-locked delegated algos are STRUCTURALLY unwinnable vs nx

DIG target = biggest measured gaps (greedy_color connected_sequential_bfs 0.34x, eppstein_matching 0.55x,
flow variants preflow_push/dinitz/sap/boykov_kolmogorov 0.64-0.77x). Investigated greedy_color
connected_sequential as the representative; decomposed on BA(500,5):
  faithful _fnx_to_nx conversion = 4.33ms ; nx greedy_color(cs_bfs) on the converted graph = 1.85ms ;
  full fnx = 6.29ms ; nx DIRECT = 1.85ms.
Tried the cheapest possible de-delegation — build a structural nx.Graph from a G.adjacency() dict-of-lists
(byte-exact: struct==faithful VERIFIED) = 2.55ms build + 1.85ms algo = ~4.4ms = 0.42x. STILL A LOSS.

ROOT (general principle, applies to the whole cluster): these outputs are SET-ORDER-LOCKED — the result
depends on CPython set/dict iteration order (greedy_color: connected_components order + arbitrary_element
= next(iter(set)) + bfs_edges adjacency-traversal order; eppstein: BFS/DFS layer dict order; nx flow
funcs: residual-network traversal order). A safe-Rust kernel CANNOT reproduce CPython set order, so fnx
MUST run nx's exact Python algorithm, which forces extracting fnx's Rust-side adjacency into a Python
structure FIRST. That extraction (~0.6-2.5ms depending on method) is a tax nx NEVER pays (its adjacency
already lives in Python dicts). Therefore: extraction + full-Python-algo  >=  nx's full-Python-algo, for
ANY set-order-locked delegated function. The best achievable is ~0.5-0.77x (reduce the extraction), NEVER
a win. REJECT (no code shipped; the partial struct-build improvement still loses vs nx).

FRONTIER PRINCIPLE (record once): a function is WINNABLE via a native Rust kernel IFF its output is
ORDER-INVARIANT (booleans/values/sorted-sets — is_planar, triangle/clustering, SCC counts, matching
CARDINALITY, flow VALUE — all already won 10-273x). If the output's IDENTITY depends on CPython set/dict
iteration order, it is order-LOCKED and structurally cannot beat nx (extraction tax). STOP attacking
order-locked delegated functions for a vs-nx win; only their COLD-conversion-tax on SMALL inputs (link-
pred precedent) or an order-invariant reformulation is routable.

## 2026-06-25 CopperCliff SURFACE: MG/MDG weighted degree 0.48-0.65x — lever found, blocked (peer-owned file)

DIG on the biggest current measured gaps (the 0.04x ones are fixed; current worst, n=1500/9000 multi-edges):
| op | fnx | nx | ratio |
| MultiGraph.degree(weight) INT | 14.18ms | 9.17ms | 0.647x |
| MultiGraph.degree(weight) FLOAT | 12.30ms | 5.88ms | 0.479x |
| MultiDiGraph.degree(weight) INT | 15.31ms | 9.63ms | 0.629x |
| MultiDiGraph.in_degree(weight) INT | 9.71ms | 5.18ms | 0.534x |
| MultiDiGraph.degree(weight) FLOAT | 15.54ms | 9.22ms | 0.593x |

ROOT: the FULL `_native_weighted_degree` (crates/fnx-python/src/lib.rs:6709 PyMultiGraph, ~11021 MDG)
always builds a Python LIST of per-edge weight values + calls `builtins.sum`, paying per edge: edge_key
STRING construction + edge_py_attrs HashMap<String> lookup + PyDict get_item + PyList append. It does
NOT use the store-sum fast path that the SUBSET variant has (`weighted_degree_py_int_row` -> i128,
6891), which my earlier MDG int work (ac98e77d4) measured at 0.78-0.95x.

LEVER (for the owner): route the full degree(weight) through a store-sum like the subset — sum i128 from
the inner AttrMap (index-keyed, NO per-edge string/PyDict) for all-int weights, plus an f64 sibling for
float/mixed (accumulate in edge-iteration order so IEEE result == builtins.sum byte-for-byte; track
all-int vs any-float for the return type; default missing weight to 1; selfloop double-count via the
trailing sum). Gate on `!edges_dirty`; when dirty, the mirror is source-of-truth so either flush once
then store-sum, or sum f64 from the mirror in Rust (skips PyList+builtins.sum). Expected ~0.5x -> ~0.9x.

CEILING CAVEAT (why this is SURFACE not a shipped win): the per-node degree-VIEW PyObject materialization
(building n (node, py-number) pairs) is a floor — the int-store version landed at 0.78-0.95x, NOT >1.0x,
and the eilce index-native accumulator lever was already REFUTED+NO-SHIP (6ee21ea28) for this exact
reason. So this closes the laggard gap toward parity but is unlikely to BEAT nx.

BLOCKED: the code is in crates/fnx-python/src/lib.rs, owned by BlackThrush (codex-cli), ACTIVE as of
2026-06-25T20:50Z (just committed there). Per coordination etiquette I did NOT start a competing change
in their active reserved file. Surfaced the lever to BlackThrush via agent-mail. No code shipped here.

## 2026-06-25 CopperCliff SURFACE: remaining laggard frontier (keys+data view emission) is core-Rust/peer-owned

Continued the 0.04-0.22x dig (different primitive: multigraph edge/selfloop VIEW emission). Measured
(n=2400, par=2 parallel edges):
| op | fnx | nx | ratio |
| selfloop_edges(MG, keys=True, data=True) | 1.657ms | 0.533ms | 0.322x |
| selfloop_edges(MG, keys=True, data='weight') | 1.534ms | 0.587ms | 0.383x |
| MG.edges(keys=True, data='weight') dense self-loops | 3.19ms | 1.81ms | 0.566x |
| MG.edges(keys=True, data='weight') non-selfloop chain | 4.34ms | 1.92ms | 0.442x |

NOT self-loop-specific (the non-selfloop chain is 0.442x too) — it is the MultiGraph keys+data edge-VIEW
emission: building (u, v, key, value) 4-tuples. selfloop_edges(__init__.py:21784) is a Python wrapper but
its multigraph path delegates to the native `_native_selfloop_edges` binding; edges(keys,data) is a
Rust-backed view iterator. BOTH live in crates/fnx-python (lib.rs / views.rs).

CONCLUSION (frontier map): every remaining vs-nx LOSS I can measure (weighted degree 0.48-0.65x [see
prior entry], multigraph keys+data edge/selfloop emission 0.32-0.57x, set/get_edge_attributes 0.37-0.64x,
edges(data=True) 0.68x) is in the CORE Rust substrate — the per-element PyObject materialization of view
tuples / attr dicts / degree pairs — owned and ACTIVELY edited by BlackThrush (codex-cli, last_active
2026-06-25T20:50Z). These are PyObject-materialization floored (the int-store degree capped at 0.9x; the
eilce accumulator was REFUTED) and in a peer's locked files, so CopperCliff (periphery: fnx-algorithms
kernels + Python wrappers) cannot cleanly land them without colliding with BlackThrush's active work.
agent-mail is in a durability-error state (can't send the lever directly) — surfaced via this ledger.
No code shipped (would be a competing change in a peer's active reserved file for a floored result).
Periphery veins (algorithms/centrality/spectral/generators/products/IO/bipartite) are EXHAUSTED at
at-or-above nx (6 wins shipped this session: prufer, gaussian, is_distance_regular, tree_broadcast_center,
subgraph_centrality, hopcroft_karp).

## 2026-06-25 CopperCliff REJECT: structural/copy/conversion primitive sweep — losses are native+floored

Dug a DIFFERENT primitive class (structural/copy/conversion, n=2000/12000) per the laggard directive.
WINS (no action): G.copy() 3.79x, nx.Graph(G) copy-construct 1.89x, G.subgraph().copy() 1.08x,
edge_subgraph 1.06x, MG.number_of_edges() native O(1). PARITY: G.to_directed() 0.91x, MG.subgraph 0.94x,
G.update 0.85x. LOSSES (all confirmed native + substrate-floored, REJECT):
- MG.copy() 0.788x (89.8ms): ALREADY routes to native `_native_copy()` (br-r37-c1-8uh84) — it's the
  dual-storage (String adjacency + index edges map + per-edge AttrMap) clone floor, same class as
  add_edges_from 0.58x. Not periphery-fixable.
- MG.to_directed() 0.805x (126ms): same native-rebuild construction floor.
- MG.get_edge_data(u,v) 0.457x: 0.46us/call — single-edge PyO3 boundary floor (nx is a pure dict index
  at 0.21us); not meaningfully beatable.

DEFINITIVE FRONTIER CLOSURE (CopperCliff, periphery agent): I have now measured every accessible
primitive class — algorithms/centrality/spectral/generators/products/bipartite/IO/DAG (all >= nx, 6 wins
shipped) AND attr/view/degree/copy substrate (all native + PyObject-materialization-floored at ~0.5-0.9x,
owned by active peer BlackThrush). There is NO remaining periphery-fixable vs-nx win. The entire residual
gap is the dual-storage / PyObject-materialization substrate in crates/fnx-{python,classes} — an
architectural single-storage / interned-key refactor (BlackThrush's locked core), not a point fix.
Levers handed off in the prior two ledger entries (f0b203ca3 weighted degree, 704e4db50 view emission).

## 2026-06-25 CopperCliff SURFACE (WINNABLE, high-cascade): weighted matrix construction 0.37-0.49x

Dug matrix-construction primitives (BA n=2000/m=6, weight=1.5). MEASURED gaps:
| op | fnx | nx | ratio |
| to_numpy_array(weight) | 17.0ms | 7.6ms | 0.448x |
| to_numpy_array | 19.0ms | 7.1ms | 0.372x |
| to_scipy_sparse_array(weight) | 15.6ms | 6.8ms | 0.439x |
| laplacian_matrix | 15.6ms | 7.7ms | 0.492x |
| normalized_laplacian_matrix | 16.0ms | 7.6ms | 0.477x |
| adjacency_matrix | 14.8ms | 9.9ms | 0.669x |
WINS (no action): from_scipy_sparse_array 1.95x, from_numpy_array 1.70x, to_dict_of_lists 1.94x,
incidence_matrix 6.03x.

DISTINCTION FROM PRIOR FLOOR SURFACES — this one is WINNABLE, not PyObject-floored. Proof:
to_scipy_sparse_array with **weight=None** is **2.84x FASTER** than nx (fnx 2.34ms vs 6.66ms) — it uses
the native `_native_adjacency_default_order_index_arrays` (rows+cols emitted from the index-native edge
store in 0.55ms, zero per-edge PyO3). The matrix OUTPUT is a numpy/scipy BUFFER, so there is NO
per-element PyObject materialization floor. The ONLY reason weighted is 0.45x is that the simple-Graph
weighted path either (a) falls to a Python COO loop (dtype=None, the conservative gate at __init__.py
~53037 `_use_native_weighted = isinstance(weight,str) and dtype is not None`), or (b) the forced-native
weighted read (dtype given) is itself ~11ms (sync + per-edge store read), with no fast buffer emitter.

LEVER (for BlackThrush — you own fnx-python/lib.rs + built the templates): add a native simple-Graph and
DiGraph weighted CSR-bytes / COO-arrays builder that emits (indptr/indices or rows/cols) + an f64 `data`
buffer + a `data_is_int` flag in ONE pass over the inner index-native edge store — EXACTLY mirroring the
existing `_native_adjacency_csr_bytes_multigraph_default_order_live_checked`. Then relax the __init__.py
gate to route weight=str + dtype=None through it (Python side picks int64 vs float64 from data_is_int,
same as the multidigraph CSR path at ~53090). Expected ~0.45x -> ~2-3x (matching the unweighted 2.84x),
cascading to all 5 functions above (laplacian/normalized/adjacency_matrix all call to_scipy_sparse_array).
NOT shipped by me: it's a NEW native method in your active reserved lib.rs; agent-mail is down so handing
off via ledger. (Worktree-buildable + byte-exact-verifiable if reassigned to me.)

## 2026-06-25 CopperCliff SURFACE (MASTER LEVER): sticky edges_dirty floors weighted matrix AND shortest-path clusters

Traced the weighted matrix-construction gap (to_numpy_array 0.37x, to_scipy_sparse_array(weight) 0.44x,
laplacian 0.49x, normalized_laplacian 0.48x, adjacency_matrix 0.67x) to its ROOT — and it is the SAME
root as the dijkstra/astar/bellman_ford cluster.

MEASURED PROOF (BA n=2000/m=6, weight=1.5):
- A fast native weighted COO builder ALREADY exists: `_fnx.adjacency_default_order_arrays(G,'weight',1.0)`
  -> (rows, cols, f64-data). After a manual `G._fnx_sync_edge_attrs_to_inner()` it returns CORRECT
  weights and runs in **1.64ms** (vs nx to_scipy 7ms = ~4.3x faster).
- BUT `to_scipy_sparse_array(G, dtype=f64)` (which routes through it) is 18.6ms on call #1 AND 18.3ms on
  the min-of-6 repeat -> the `_fnx_sync_edge_attrs_to_inner` sync (~16ms, PyO3 per edge) runs EVERY call
  because it never clears `edges_dirty` (sticky-dirty bug, same one noted for dijkstra). Without the sync
  the store is stale (add_edge writes the mirror, not the store) so the builder reads default 1.0.

CONSEQUENCE: every native-store-read path pays a full ~16ms re-sync per call. If `edges_dirty` were
cleared after a successful sync, call #1 pays the sync once and calls #2..N read the store in ~1.6ms ->
weighted matrix construction 0.4x -> ~4x (5 functions), AND dijkstra/astar/bellman 0.5x -> 5x+ (3
functions). ONE fix, ~8 functions.

THE FIX (BlackThrush's crates/fnx-python/src/lib.rs): clear `edges_dirty` after `_fnx_sync_edge_attrs_to_inner`
/ `_fnx_sync_attrs_to_inner` succeed, AND ensure the edge-attr-dict __setitem__ path (G[u][v]['w']=x)
RE-marks `edges_dirty` so the next sync re-runs. The naive clear was attempted+reverted before because
subscript-set didn't reliably re-mark dirty after the clear (broke G[u][v]['weight']=x parity). The
correct fix pairs the post-sync clear WITH a guaranteed re-mark on the mirror-dict mutation path
(AtlasView/edge-attr-dict __setitem__), not just __getitem__ (views.rs:1047 already marks on getitem).

This is the single highest-leverage lever found this session. Surfaced (mail down); lib.rs is
BlackThrush's active reserved core. Periphery-unfixable (the sync + dirty state live in Rust).

## 2026-06-25 CopperCliff verification: cycles/dominance/paths swept — no new periphery gap

Swept previously-unmeasured primitives to confirm frontier exhaustion. All fnx at-or-above nx:
cycle_basis 1.97x, minimum_cycle_basis 7.49x, square_clustering 18.9x, chain_decomposition 9.74x,
junction_tree 3.23x, voronoi_cells 1.46x, all_pairs_node_connectivity 1.64x. Sub-1.0x are tiny-absolute
PyObject/PyO3 single-call floors (immediate_dominators 0.644x @0.019ms, dominance_frontiers 0.651x
@0.037ms, simple_cycles(len_bound) 0.703x @1.77ms) — not meaningfully improvable.

FRONTIER STATE (CopperCliff, periphery agent, this session): 6 vs-nx wins shipped (prufer, gaussian,
is_distance_regular, tree_broadcast_center, subgraph_centrality 34x, hopcroft_karp 20x). All accessible
periphery primitive classes now measured at-or-above nx. The ENTIRE residual vs-nx loss reduces to ONE
root cause in BlackThrush's reserved fnx-python/lib.rs: the STICKY `edges_dirty` master lever (see prior
entry 2578350fe) — fixing it (post-sync clear + edge-attr-dict __setitem__ re-mark) unlocks ~8 functions
(weighted matrix construction 0.4x->~4x + dijkstra/astar/bellman 0.5x->5x+). Periphery-unfixable; handed
off via ledger (agent-mail in durability-error state). Next real vs-nx progress requires either
BlackThrush implementing the surfaced levers or reassignment of the core files to CopperCliff.

## 2026-06-25 CopperCliff RESOLVED: why the sticky-edges_dirty clear breaks mutation parity (the real fix)

Investigated the master lever's "deeper cause unresolved" (the post-sync edges_dirty clear that unlocks
~8 functions but was reverted for breaking G[u][v]['weight']=x). ROOT, now airtight by code + empirical:
- fnx's per-edge attr mirror (edge_py_attrs) is a PLAIN `Py<PyDict>` (verified type(G[u][v]) == dict).
- `AtlasView.__getitem__` (views.rs:1037-1047) marks edges_dirty on ACCESS, then returns that plain dict.
- The sync (`_fnx_sync_edge_attrs_to_inner`, lib.rs:10961) early-returns when !edges_dirty and never
  clears it -> sticky. This is a CORRECTNESS GUARANTEE: once any edge dict is handed to Python it may be
  mutated through a HELD REFERENCE with no fnx hook, so dirty must stay true so every native store-read
  re-syncs from the mirror.
- nx supports held-ref mutation (verified: `d=G[0][1]; d['weight']=5.0` -> G[0][1]['weight']==5.0; it is
  a documented contract because nx's dict IS the storage). fnx must preserve it.
- THE BREAK with a naive clear: `d=G[u][v]` (marks dirty) ; `kernel()` (syncs+CLEARS) ;
  `d['weight']=x` (plain-dict setitem, NO mark — held ref, no getitem) ; `kernel()` (dirty=false ->
  SKIPS sync -> reads STALE). Sticky-dirty avoids this by never skipping.

REAL FIX (not a flag clear): make the edge (and node) attr mirror a custom dict SUBCLASS whose
__setitem__/__delitem__/update/pop/clear/setdefault all call `mark_edges_dirty`, so EVERY mirror
mutation (including held-reference, no-getitem) re-marks dirty. THEN clearing edges_dirty after a
successful sync is safe, and the ~8-function unlock (weighted matrix 0.4x->~4x, dijkstra/astar/bellman
0.5x->5x+) lands without regressing held-ref mutation parity. TRADEOFF to measure: a Python-subclass
__setitem__ is slower than C-dict setitem, so the per-attr-write paths (set_edge_attributes etc.) may
regress — net win depends on read-heavy (matrix/shortest-path) vs write-heavy workloads; the subclass
could be Rust-side (pyclass mapping) to minimize setitem overhead. In BlackThrush's lib.rs/views.rs;
this resolves the long-open blocker so the implementer goes straight to the marking-subclass approach
instead of re-attempting the (correctness-breaking) bare flag clear.

## 2026-06-25 CopperCliff REJECT: approximation.steiner_tree 0.409x — conversion-tax-bound, de-delegation parity-risky

Swept WL-hash/traversal/similarity/steiner. All at-or-above nx EXCEPT steiner_tree 0.409x (fnx 6.5ms vs
nx 3.06ms, BA(400) weighted, 4 terminals). Wins/parity: weisfeiler_lehman_graph_hash 0.95x, wl_subgraph
0.95x, bfs_tree 3.06x, dfs_tree 3.20x, edge_bfs 1.26x, bfs_layers 1.56x, descendants 1.18x, simrank
1.04x, panther 1.01x, hits 0.95x.

steiner_tree decomposed: fnx.approximation.steiner_tree IS nx's function (namespace delegate). Cost =
faithful fnx->nx conversion 3.84ms + nx algo 3.09ms = 6.5ms (nx-on-nx = 3.06ms; nx algo on the converted
graph = 3.09ms -> the WHOLE gap is the conversion). No native steiner kernel exists.

De-delegation (run kou/mehlhorn in-process on fnx's fast native shortest-paths, skip the conversion) is
possible IN PRINCIPLE (graph-returning, round-trip-conversion class) BUT byte-exactness requires
reproducing nx's metric_closure dijkstra PATH tie-breaks AND the metric-closure MST tie-breaks exactly —
both CPython-order-sensitive. High parity risk for a niche approximation function whose only overhead is
the 3.84ms weighted-conversion (the same construction floor that taxes every delegated weighted fn).
REJECT (not worth the parity risk; cheaper-conversion would still be ~0.6x). Note: the construction-floor
fix (faster weighted fnx->nx / native weighted builders) would lift this too — ties back to the matrix
construction + sticky-dirty levers already surfaced.

## 2026-06-25 CopperCliff DEFINITIVE BLOCKER: agent-mail DB corrupted; core levers handed off via git only

Attempted to reserve crates/fnx-python/src/lib.rs + views.rs (to claim the sticky-edges_dirty master-lever
fix). The mcp-agent-mail file_reservation call returned: "Database corruption detected ... database disk
image is malformed ... Run 'am doctor repair' or 'am doctor reconstruct'". So BOTH agent-mail messaging
(noted down earlier) AND file reservations are now unavailable — there is NO working cross-agent
coordination channel; the git-committed ledger (this file) is the only handoff path.

STATE OF THE ENGAGEMENT (CopperCliff, periphery): 6 vs-nx wins shipped + verified intact (759 conformance
pass). Every accessible periphery primitive class (~24 swept) is at-or-above nx. ALL residual vs-nx loss
reduces to TWO root-caused levers in BlackThrush's reserved core, fully specified in this ledger:
  1. STICKY edges_dirty master lever (f91977f1e + 2578350fe): real fix = marking edge-attr dict subclass
     (mark_edges_dirty on __setitem__/__delitem__/...), THEN clear dirty after sync. Unlocks ~8 fns
     (weighted matrix construction 0.4x->~4x; dijkstra/astar/bellman 0.5x->5x+). Measured unlock: native
     weighted COO builder is 1.6ms post-sync vs 18ms sticky.
  2. Simple-Graph/DiGraph native weighted CSR-bytes builder (d3e0d340f): mirror the existing multigraph
     template; also subsumes steiner_tree 0.41x (2d03b3bbe) and other weighted-conversion gaps.

BLOCKER: both fixes are in crates/fnx-python/src/{lib.rs,readwrite.rs,algorithms.rs}, reserved by ACTIVE
peer BlackThrush; coordination infra (agent-mail) is corrupted so the work cannot be reserved/handed off
except via this ledger, and a rushed solo edit risks collision with their in-flight changes + the bare
flag-clear is proven to regress held-ref mutation parity. OPERATOR ACTION NEEDED: restore agent-mail
(`am doctor repair`) and/or reassign the core files to CopperCliff with a mandate, OR BlackThrush picks up
the two ledger levers. Not run by me: am doctor repair/reconstruct (could destroy other agents' mail).

## 2026-06-25 CopperCliff CORRECTION: weighted matrix lever folds into sticky-dirty (not independently buildable)

Refining d3e0d340f ("winnable weighted matrix builder"). Deep re-analysis: the dtype-preserving store
builder ALREADY EXISTS — `adjacency_default_order_typed_arrays(g, weight, default)` -> (rows, cols, f64
data, needs_float_dtype) in algorithms.rs:3122 — and is fast (~1.6ms) reading the INDEX-NATIVE store via
`edge_attrs_by_indices`/`edges_indexed`. BUT the store is stale unless synced (add_edge writes the mirror,
not the store), and the sync (`_fnx_sync_edge_attrs_to_inner`) is the sticky ~16ms cost. Routing
to_scipy(dtype=None) through it REGRESSES (12.5ms Python-loop -> 18ms sync+read). A sync-FREE mirror
reader must do the per-edge dual lookup (mirror-if-materialized else store else default) with the
index->name->edge_py_attrs string tax — exactly the pattern that makes `_native_weighted_degree` 0.5x.
Mirror dicts are also lazily materialized (br-r37-c1-89kxg: no eager empty mirrors) so iterating
edge_py_attrs alone is INCOMPLETE.

CONCLUSION: weighted matrix construction (to_scipy/to_numpy/laplacian/normalized/adjacency_matrix) is NOT
an independent periphery build — it requires the synced store, i.e. it FOLDS INTO the sticky-edges_dirty
master lever (clear-dirty-after-sync + marking dict subclass, f91977f1e). With that one core fix, the
EXISTING `adjacency_default_order_typed_arrays` store-reader becomes the fast path for dtype=None too
(first call syncs, repeats read store in ~1.6ms) -> matrix 0.4x->~4x falls out for free. So the master
lever's reach is even larger than stated: it unlocks weighted matrix construction WITHOUT any new builder.
Do NOT attempt a standalone periphery weighted matrix builder; it cannot be both fast and correct without
the sync. Single source of remaining vs-nx progress = the sticky-edges_dirty core fix.

## 2026-06-25 CopperCliff frontier coverage complete: layout/numerical/structural all >= nx

Final sweep (~10 fns previously unmeasured): all at-or-above nx. reciprocity 2.40x, s_metric 134x,
flow_hierarchy 11.6x, local_bridges 6.63x, bridges 22.5x, configuration_model 1.02x,
expected_degree_graph 1.06x, spectral_layout 0.96x, spring_layout 0.98x, kamada_kawai 1.09x,
random_reference 0.95x, non_randomness 0.835x (near-parity, eigvalsh-based). ~26 primitive classes now
measured: the ENTIRE accessible periphery is at-or-above nx.

TERMINAL PERIPHERY STATE (CopperCliff): 6 vs-nx wins shipped+verified (759 conformance pass). No
remaining periphery-fixable vs-nx win. ALL residual loss reduces to ONE core fix — the sticky-edges_dirty
marking-dict-subclass (f91977f1e), subsuming weighted matrix construction (82c94c296) AND dijkstra/astar/
bellman, ~8 fns. Blocked on BlackThrush's reserved lib.rs (core last commit 7634eebf7) + corrupted
agent-mail (git ledger is the only channel). Real progress = the one core fix.

## 2026-06-25 CopperCliff handoff status + master-lever implementation refinement

Verified my surfaced core gaps ARE being actioned by BlackThrush (the periphery-surface -> core-implement
division is working): landed since my surfaces — degree(nbunch,weight) Graph 0.12x->0.69x (e09a7265c) +
MultiGraph 0.04x->0.60x (4b7181fde) + 550bf893e; edges(nbunch,...) 0.09x->0.80x (acf280dd4/506683501);
in_edges(data) 0.09x->26.77x (accca957d); MultiGraph copy (cc7135681); weighted pagerank (019aa7efc).
The sticky-edges_dirty MASTER lever is NOT yet done (no `edges_dirty.store(false)` in lib.rs) — it remains
the single open high-value item (~8 fns: weighted matrix construction + dijkstra/astar/bellman).

IMPLEMENTATION REFINEMENT for the master lever (resolves the "marking subclass regresses construction"
concern in f91977f1e): the marking edge-attr dict MUST be a `#[pyclass(extends=PyDict)]` Rust type, NOT a
Python `class(dict)`. extends=PyDict (a) preserves `isinstance(d, dict)` and `type(G[u][v]) == dict`
(verified nx contract + downstream isinstance checks rely on it), and (b) gives a fast Rust-side
__setitem__/__delitem__/update/pop/clear/setdefault that calls mark_edges_dirty — avoiding the
Python-level per-op overhead of a `class(dict)`. CAVEAT to bench: per-edge instantiation of the pyclass
vs PyDict::new in the hot mirror-materialize path (add_edges_from etc.) — must confirm it does not regress
construction (the 0.58x add_edges_from floor); if it does, gate the marking type to graphs that have had a
native store-read (lazy upgrade) rather than all mirrors. Then clear edges_dirty after sync -> unlock.

## 2026-06-25 CopperCliff /alien-graveyard unused-binding hunt — exhausted (no routing win)

Enumerated all 382 native pyfunctions; found ~40 unused by python/ wrappers. Triaged the candidates:
- STORE-reading bindings (get_edge_attributes_rust, get_node_attributes_rust): FAST (get_edge_attributes
  _rust 1.69ms vs current 5.2ms / nx 3.4ms) but WRONG — they read the index-native store which is stale
  while edges_dirty (weights live in the mirror). Sticky-dirty-bound (same master lever); unused for cause.
- STRUCTURAL operators with unused bindings (quotient_graph, dedensify, snap_aggregation) are ALREADY
  faster than nx via the existing wrapper paths (2.09-2.72x) — the unused *_rust bindings are superseded,
  not a missed win.
- number_of_selfloops_rust etc. are unused because slow/wrong (prior memory).
CONCLUSION: the unused-native-binding ("alien graveyard") lever is exhausted — every unused binding is
either sticky-dirty-bound (store-stale) or superseded by an already-fast wrapper. No periphery routing win.
Reconfirms: the ONLY remaining vs-nx lever is the sticky-edges_dirty core fix (pyclass(extends=PyDict)
marking dict + clear-after-sync, 27a335021). Store-reading bindings (get_edge_attributes_rust) would ALSO
become correct+fast once that lands — add to the master lever's unlock list (now ~9 fns).

## 2026-06-25 CopperCliff INFRA: cargo-bench-via-rch does not return results; two infra blockers

Ran the directive's literal mechanism: rch exec -- cargo bench -p fnx-algorithms --bench
algorithm_benchmarks -- core_laggards (CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cc).
It built (54s) and ran remotely on hz2 (~120s) but criterion's stdout (time:/change: vs the existing
Jun-24 networkx_head_to_head_* baselines) was NOT streamed back, and the criterion estimates were NOT
synced to the local target dir (newest local estimates remain 2026-06-24 22:36; my 22:35 run stayed
remote). So the prescribed cargo-bench validation path yields NO readable vs-baseline result in this rch
setup — a Rust perf lever cannot be validated through the literal mechanism without extra remote-result
retrieval (capture the bench stdout, or rsync the remote criterion dir back).

TWO INFRA BLOCKERS confirmed (affect ALL agents; operator action needed):
1. agent-mail DB corrupted ("database disk image is malformed") -> messaging + reservations down; git
   ledger is the only coordination channel (am doctor repair needed).
2. cargo-bench via rch does not return criterion results -> Rust-lever validation path broken as-is.

Net: the one remaining vs-nx lever (sticky-edges_dirty pyclass(extends=PyDict) fix, ~9 fns) is in
BlackThrush's reserved lib.rs, can't be coordinated (mail down) and can't be bench-validated via rch
(results not returned). CopperCliff periphery work complete (6 wins, ~26 classes >= nx, unused-binding
vein exhausted). Real progress needs operator: restore agent-mail + fix bench-result retrieval, and/or
reassign the core file to CopperCliff.

## 2026-06-25 CopperCliff CLOSURE: mirror-read matrix builder ruled out by direct evidence (coowt)

Final investigation of whether a sync-free mirror-reading weighted COO builder (in the SHARED algorithms.rs,
not BlackThrush's lib.rs, validatable via Python) could win the matrix gap without the sticky-dirty fix.
RULED OUT by direct in-tree evidence: the existing builder's `br-r37-c1-coowt` comment (algorithms.rs:3060)
states it deliberately AVOIDS get_node_name+edge_attrs(&str,&str) because that "paid two index->String
resolutions plus a String->index round-trip per edge (the String-adjacency tax on the weighted CSR
export)" — i.e. the mirror/string-keyed read IS the known-slow path already rejected in favor of the
index-native store read (`edge_attrs_by_indices`, 1.6ms). A mirror-reader would reproduce that tax (also
node_key_map is str->PyObject, not str->index, so it needs inner.node_index per endpoint — the exact
round-trip). So it cannot be a periphery win.

DEFINITIVE: the weighted matrix gap's only fast path is the index-native store (fast) which is stale
without a sync; the sync is sticky. There is NO periphery matrix build. Confirms (3rd angle) that ALL
residual vs-nx loss = the single sticky-edges_dirty core fix. CopperCliff periphery is provably exhausted
across every approach: primitive sweeps (~26 classes), unused bindings, mirror-vs-store matrix read, and
de-delegation — all ruled out with evidence. The one lever is core (lib.rs), uncoordinatable (mail down),
unvalidatable via rch (bench results not returned). Operator unblock required.

## 2026-06-25 CopperCliff WIN: random_cograph one-pass — 1.76-6.27x vs nx (construction-tax removed)

Community/isomorphism/generator sweep (all >= nx: louvain 15x, greedy_modularity 24.8x, vf2 22.6x,
label_propagation 2x) surfaced random_cograph as slow on dense instances. It's a pure-Python generator
that looped n times doing copy() + relabel_nodes() + full_join/disjoint_union — each rebuilding an fnx
graph (construction tax, compounding as the graph doubles). Rewrote to accumulate the edge list in plain
Python (shifted left-edges + full_join cross-edges left x right) and commit via ONE add_edges_from.
rng.randint(0,1) draw order preserved; node labels 0..2**n-1; shifted-then-cross emission order matches
the operator path -> BYTE-IDENTICAL node + edge iteration order (verified 240 cases: n in {0,1,2,3,5,7} x
40 seeds vs current fnx AND nx; conformance -k cograph 44 passed). random_cograph(8): seed1 6.27x, seed2
1.76x, seed5 2.35x vs nx (4.3x self on sparse, more on dense). Python-only periphery win, no build, no
core lock. LEVER (reconfirms reference_batch_add_edges_from_construction): generators looping
copy/relabel/union/join per step -> track edges in Python, build once.

## 2026-06-25 CopperCliff paley_graph batch — 0.25x->0.70x (loss-REDUCTION, byte-exact)

Generator construction-pattern sweep: paley_graph 0.25x, chordal_cycle 0.36x, generalized_petersen 0.56x
gaps (caveman 4.3x, lollipop 12.5x, windmill 3.4x, visibility 3.2x are wins). paley_graph looped per-edge
add_edge over (x outer, square inner); batched to ONE add_edges_from in the same order (no pre-add of nodes
-> nodes inserted in edge-discovery order matching the loop). BYTE-EXACT: node+edge order == current fnx AND
nx for p in {5,13,17,101,103,107}; conformance -k paley 3 passed. Result: 0.25x->0.70x (101)/0.74x (503),
~2.8x self BUT STILL <nx. Unlike random_cograph (batching killed repeated full-graph reconstruction = real
win), paley's per-edge loop had no repeated reconstruction, so batching only drops to the add_edges_from
construction floor (3.4ms vs nx per-edge 2.4ms / 5000 directed edges) = loss-REDUCTION, not a vs-nx win.
KEPT (byte-exact, 2.8x faster, cleaner code) but transparently still a loss. To BEAT nx: fix the disabled
native _rust paley builder (br-paleydir: was wrong, defaulted undirected; nx default DiGraph) to emit
directed edges natively (Rust). chordal_cycle (multigraph) batch had divergent edge KEYS -> NOT batched
(parity risk). generalized_petersen 0.56x is the NATIVE _rust path (slow native construction, Rust).

## 2026-06-25 CopperCliff generator vein mapped — dense generators floor-bound; no new clean win

Extended generator sweep. WINS (nx-slow or sparse structure): random_regular_graph 2.48x, random_lobster
3.47x, duplication_divergence 1.99x, random_powerlaw_tree 1.52x, planted_partition 1.15x. FLOOR-BOUND
LOSSES (dense-edge generators, all clustered ~0.70-0.76x = the add_edges_from construction floor, already
near-batched, NOT the 0.25x per-edge-loop case): random_partition_graph 0.70x, stochastic_block_model
0.75x, turan_graph 0.75x, complete_multipartite 0.76x, ring_of_cliques 0.87x. These are NOT improvable by
batching (already at the floor) — they fold into the dual-storage construction floor (add_edges_from
0.58-0.70x), the same architectural limit as parse_adjlist/weighted-matrix. Generator vein CONCLUSION:
clean wins exist only where nx is slow or structure is sparse (shipped/confirmed); dense generators are
construction-floor-bound and need the core single-storage/interned-key refactor (not periphery-fixable).
No new clean periphery win this pass.

## 2026-06-25 CopperCliff WIN: *_all operators O(k^2) fold -> O(k) collect-batch (disjoint_union_all 1.72x)

compose_all/union_all/disjoint_union_all were PAIRWISE FOLDS (R = R._native_compose(H) per graph) — the
growing result re-copied each step = O(k^2): measured compose_all 0.13x@k=40 / 0.02x@k=240, union_all
0.14x, disjoint_union_all 0.24x vs nx. Rewrote all three to COLLECT every graph's nodes/edges and commit
via ONE add_nodes_from + ONE add_edges_from (single-pass disjoint-node check for union_all raising nx's
exact NetworkXError; compose = later-graph-wins via add_*_from dict-merge order). O(k^2)->O(k):
  disjoint_union_all 0.24x -> 1.72x@k40 / 1.60x@k240 (clean WIN both)
  union_all          0.14x -> 1.47x@k40 / 0.82x@k240
  compose_all        0.13x -> 0.99x@k40 / 0.83x@k240
BYTE-EXACT: node+edge(+keys)+graph-attr iteration order vs nx across all 4 graph classes x overlap
(0/8 compose, 0/4 union) + overlap-raise; conformance -k "union_all or disjoint_union or compose_all"
51 passed. Python-only periphery (no build, no core lock). LEVER (extends random_cograph): operators/
generators that iteratively pairwise-combine a GROWING result are O(k^2) — collect-all + single batch add
is O(k). The collect-ALL-then-one-batch beats per-graph add (which has growing-R overhead) AND the fold.

## 2026-06-25 CopperCliff construction-builder sweep — binomial_tree REJECT, rest wins/floor-bound

Swept line_graph/complement/contracted/tree/conversion/lattice builders. WINS (no action): line_graph
4.09x, complement 4.74x, contracted_nodes 8.34x, contracted_edge 8.04x, to_undirected(DiG) 10.6x,
full_rary_tree 4.16x, balanced_tree 5.31x, kneser 3.51x, from_pandas_edgelist 2.0x, hexagonal_lattice
1.56x, triangular_lattice 1.94x, grid_2d 2.46x, ego_graph 1.83x, weighted_projected 1.59x, power 1.68x.
GAPS triaged:
- binomial_tree 0.495x: REJECT. It's a doubling fold (B_k = 2x B_{k-1} + root edge) reading G.edges()
  each step. Tried plain-Python edge accumulation (random_cograph style) -> DIVERGES for n>=4 (node/edge
  order is tied to the GROWING graph's G.edges() iteration, NOT reproducible from a raw insertion list;
  matches the br-r37-c1-btorder comment "node 12 before 11 at n=4") AND the batch was NOT faster
  (0.71x@n12, 0.47x@n14). Order-locked to the live graph + no speedup -> not shippable. Reverted (proto only).
- from_dict_of_lists 0.458x / from_dict_of_dicts 0.599x: already batched (br-r37-c1-dolsymdedup symmetric-
  dedup bulk path) -> construction-floor-bound, not improvable without the core single-storage refactor.
- inverse_line_graph 0.696x (1.6ms): niche + small, set-order-locked algorithm; not pursued.
No new clean periphery win this batch; construction-builder vein now largely mapped (wins where nx-slow or
sparse; floor-bound for dense/dict conversions; binomial_tree order-locked).

## 2026-06-25 CopperCliff WIN: is_at_free O(n^4)->O(n^3) component-structure — 166-305x vs nx (BIGGEST gap)

is_at_free was the worst measured gap: 0.074x (fnx 564ms vs nx 41ms on AT-free path(80)). The native
kernel (fnx-algorithms is_at_free) did a BFS PER TRIPLE (bfs_avoiding for every (i,j,k)) = O(n^3 * (n+m))
~ O(n^4); fast only when an AT exists (early-exit), catastrophic when AT-free (full search). Rewrote to
networkx's component-structure algorithm: build cs[v][u] = component label of u in G - N[v] (0 if u in
N[v]∪{v}) via ONE BFS-labelling per node (O(n*(n+m))), then test pairwise-non-adjacent triples u<v<w
against the precomputed cs (O(n^3), early-exit). is_at_free is a BOOLEAN (order-invariant) so byte-exact
regardless of iteration order; removed the now-dead bfs_avoiding. Result: 0.074x -> 166x (cycle60) / 170x
(BA80) / 291x (path80) / 305x (path150) FASTER than nx — uniformly fast (0.04-0.76ms) and beats nx in
BOTH the AT-exists and AT-free cases. Parity 0/18 graph types (path/cycle/complete/star/BA/tree/grid/
petersen/gnp/wheel/ladder/lollipop/barbell) + conformance -k "at_free or asteroidal" 25 passed. In
fnx-algorithms/lib.rs (TealSpring's, takeable). NOTE: find_asteroidal_triple (returns the TRIPLE) is
order-locked (set-iteration order) -> left as-is; only the boolean is_at_free is routable.
