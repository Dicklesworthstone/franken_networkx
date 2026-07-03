# Measured Head-to-Head Evidence — cc (CopperCliff)

Verify/gauntlet phase: every recent `code-first batch-test pending` optimization
built into a fresh release wheel (`maturin build --release`, clean .so verified
`nm -D | grep crossbeam == 0`, installed at HEAD) and measured **head-to-head vs
NetworkX** on realistic workloads (warm, min-of-8). Honest numbers — wins, losses,
neutrals. Losses get reverted; conformance stays green.

Build: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cc maturin build --release -m crates/fnx-python/Cargo.toml` → wheel installed. Measured 2026-06-18.

## SHIPPED (cc, 2026-06-30): size(weight) 0.62-0.87x -> 19.6x (cargo bench) / 31-39x (micro) — native store SCALAR, no per-node degree materialization

The documented `mg size(weight) 0.625x` head2head gap (head2head_vein_map) was lumped with the
weighted-degree "materialization floor" family — WRONGLY. `size(weight)` returns a **scalar**, so
there is NO materialization floor: the implementation just wastefully materialized N `(node,
PyFloat)` degree pairs only to `sum(...)/2` them down to one number. The Python `size` wrapper
(`_size_with_unweighted_int`, __init__.py:481) routes weighted size through
`sum(d for _, d in self.degree(weight))/2`; profiling showed ~all of size(weight)'s cost IS that
degree materialization (Graph: size 3.32ms ≈ degree-materialize 3.28ms), and PyGraph's
`_native_weighted_degree` has NO store fast path at all (it always builds a per-node PyList +
`builtins.sum`).

INSIGHT: `size(weight)` == sum of each stored edge's weight ONCE — the `/2` exactly cancels the
double-endpoint counting (an undirected edge adds `w` to both endpoints' degree; a directed edge
adds `w` to `out(u)`+`in(v)`; a self-loop adds `2w` at its node → all halve back to `w` per stored
edge). True for ALL 4 graph types. So a single O(E) store walk is the whole answer.

FIX (br-r37-c1-wsize): `weighted_size_int(weight) -> Option<i128>` on inner Graph/MultiGraph
(fnx-classes/lib.rs) + DiGraph/MultiDiGraph (fnx-classes/digraph.rs) sums the CgseValue store once
(each edge once; missing weight = nx's int 1; bails `None` on ANY non-int value). Py-layer
`_weighted_size_fast` on all 4 PyGraph classes gates `!edges_dirty` (store authoritative) and returns
`total as f64`. The `size` closure tries it first when `type(weight) is str`. Byte-identical to nx's
`sum(int degrees)/2`: integer degree sums are exact (`2*size`), and `(2*size)/2` rounds to the same
f64 as `size as f64` (both round-to-nearest-even). Float/mixed/Bool weights, callable weights, a
dirty mirror (get_edge_data / per-edge mutation) all return `None` → the exact degree path is
UNCHANGED (zero regression risk).

RESULTS: authoritative cargo bench `networkx_head_to_head_multigraph_weighted_degree` ->
`fnx_size_weight_mg400_e3224` 62.05µs vs `nx_size_weight_mg400_e3224` 1.217ms = **19.6x** (was
0.625x). Micro (N=3000, 15k int-weight edges, warm min-of-25): Graph 0.78x->31.3x, MultiGraph
0.74x->31.4x, DiGraph 0.76x->38.7x, MultiDiGraph 1.97x->34.4x. Byte-exact 12 categories × 4 types
(int/float/self-loop/negative/missing-default-1/mixed-bail/bool-bail/other-key/empty/None/dirty/
callable). Conformance GREEN: utilities+density 696, flow_hierarchy/size net 930, assortativity+
hierarchy 276, whole-suite weighted/degree/weight net 6305 — all pass. clippy clean (my additions).

LEVER (general): a SCALAR-returning weighted reduction (`size`, total weight, density numerator)
routed through a per-node degree VIEW pays N PyObject materializations for one number — it is NOT a
materialization floor (those are for collection-returning views). Fast-path it with a single store
walk; integer reductions are order-independent so byte-exactness is free. AUDIT other scalar
reductions that call `self.degree(weight=...)` / `self.size(weight=...)` internally.

## SHIPPED (cc, 2026-06-28): directed subgraph.edges() 0.009x -> 2.56x vs nx (111x slower -> 2.6x faster, ~268x self) — hoist whole-graph snapshot out of per-source loop

THE BIG conversion/view-wall find. `list(G.subgraph(nodes).edges())` on a DiGraph was **0.009x vs
nx** (fnx 194ms vs nx 1.74ms, 111x SLOWER), n=600/sub-500. The default-node-set subgraph edge fast
path (br-r37-c1-r3gjb) called `_fast_succ_row(parent, source)` PER source — and for a DiGraph that
does `parent._native_adjacency_dict()[source]`, i.e. a WHOLE-GRAPH adjacency rebuild (0.55ms) EVERY
call => O(V*(V+E)). (Undirected was already fine: `_fast_adj_row` uses per-node
`_native_adjacency_row_dict(node)`.)

FIX (br-cvsubedges): hoist the whole-graph snapshot OUT of the source loop. data=False -> one
`dict(parent._native_adjacency_keys())` (key-only, cheapest; key order verified == adjacency_dict ==
_fast_succ_row across all nodes), iterate keys filtered by visible_keep. data=True -> one
`_native_adjacency_dict()` for the key/order rows + per-source `_native_successor_row_dict(source)`
(O(deg)) for LIVE attrs, replicating _fast_succ_row's `live.get(target, keyrow[target])` merge
exactly. Absent-native fallback keeps the old per-source path.

RESULT (n=600/sub-500): list(subgraph.edges()) fnx 0.726ms vs nx 1.806ms = **2.56x FASTER** (was
0.009x; ~268x self-speedup); edges(data=True) 1.09ms vs 2.36ms = ~2.2x. PARITY: order + data=True +
data=str + nbunch byte-exact vs nx over 8 seeds incl self-loops; edge-attr IDENTITY preserved
(d is G[u][v]). PURE-PYTHON (all natives pre-existed). Conformance: 5453 view/subgraph suite +
**full tests/python 49240 passed, 0 failures**. LEVER (reusable + AUDIT): any per-source/per-node
loop calling a helper that internally does a WHOLE-GRAPH native rebuild (`_native_adjacency_dict()`,
`_native_*_dict()` with no node arg) is an O(V*(V+E)) bomb — hoist the snapshot. Grep `_fast_succ_row`
callers and `_native_adjacency_dict()` inside loops.

## SHIPPED (cc, 2026-06-28): view edges() (data=False) skip unused attr materialization — to_undirected 0.20x->0.55x; + FOUND subgraph.edges() 0.009x bomb (111x)

`_ConversionGraphViewBase._edges` AND `_FilteredGraphView._edges` fetched `attrs =
self.adj[u][v]` (a per-edge conversion/filter attr-dict merge+copy) for EVERY edge even when
data=False — then appended only `(u,v)`, dropping attrs. Guard the fetch behind `if data:`
(strict work-removal; byte-identical output — the (u,v) pairs + iteration order are unchanged).
RESULT: list(to_undirected(DiGraph).edges()) n=400 fnx 7.31ms->2.60ms = 0.20x->**0.55x** vs nx
(~2.8x self). edges(data=True) path unchanged. PARITY: fnx output byte-identical pre/post (data
path identical; data=False just drops the unused fetch); conversion-view edges() order already
differs from nx (succ∪pred merge order) but is conformance-TOLERATED (4912 view/conversion/edge
tests pass — edges equal as a SET, 116==116) and orthogonal to this change. Subgraph-view edges()
order MATCHES nx exactly (verified 6 seeds di+undi + data variants). Conformance: 4912 + 246
subgraph passed (only pre-existing gexf meta-fail).

BIG FIND (next lever): `list(G.subgraph(nodes).edges())` directed n=600/sub-500 = fnx 194ms vs nx
1.74ms = **0.009x (111x SLOWER)** — far bigger than the conversion-view gap. The attr-fetch removal
barely dents it; the dominant cost is `_FilteredGraphView.adj[source]` synthesis (per-source
membership-filtered neighbor dict rebuild => likely O(V*E)). DIG NEXT: route subgraph.edges() to a
native induced-edge emit / fix the filtered-adj per-source rebuild. Order matches nx so a native is
lower-risk here than the conversion view.

## SHIPPED (cc, 2026-06-28): to_undirected-view degree() (weight=None) 0.053x -> 4.63x vs nx — reuse the native undirected degree count

Follow-up on the same conversion-view wall: `dict(to_undirected(DiGraph).degree())` was 0.053x vs nx
(fnx 8.0ms vs nx 0.44ms, 19x) — `_ConversionGraphViewBase.degree` iterates the Python-synthesized
per-node conversion-view adjacency (materializing attr dicts) per node. Route the whole-graph
unweighted case (nbunch=None, weight=None, undirected view of simple DiGraph) to `zip(self,
_native_undirected_degree_counts())` — the SAME native foundation shipped for number_of_edges
(5c87ad2d7). RESULT (n=400): dict(degree()) fnx 0.097ms vs nx 0.447ms = 4.63x FASTER (was 0.053x;
~87x self). PARITY exact over 6 seeds incl reciprocal+self-loops; weighted/single-node/nbunch all
fall through unchanged + verified == nx. PURE-PYTHON (native already in the .so). Conformance: 5718
passed (conversion/view/degree/operator suite; only the pre-existing gexf-classification meta-fail).
Remaining on this view: edges() iteration 5x, adjacency() 3.7x (need native undirected edge/adj
emit — next).

## SHIPPED (cc, 2026-06-28): to_undirected-view number_of_edges/size 0.063x -> 8.69x vs nx — native undirected degree count (first crack in the conversion-view wall)

The conversion-view materialization wall (flagged as the next-lever blocker in SWEEP 4 below) — its
cheapest, most common query is now NATIVE. `to_undirected(G).number_of_edges()` (and `.size()`) on a
DiGraph was 0.063x vs nx (fnx 7.9ms vs nx 0.44ms, 16x): `_ConversionGraphViewBase.number_of_edges`
did `len(self.edges())`, materializing the whole conversion-view edge list (per-edge tuple build +
reciprocal dedup in Python). nx's frozen view answers via sum(degree)//2 over plain dicts. A pure
Python `sum(self.degree())//2` did NOT help (NO-SHIP, prior turn) because the view's degree iterates
the same Python-synthesized per-node adjacency.

FIX (br-cvundeg): native `PyDiGraph::_native_undirected_degree_counts` — per node (index order) the
merged succ∪pred neighbour count, deduping reciprocal edges, self-loop counted twice (nx undirected
degree). `_ConversionGraphViewBase.number_of_edges` routes the undirected-view-of-simple-DiGraph case
to `sum(native())//2` (the exact undirected edge count). Other conversions (undirected source,
multigraph, to_directed) fall through unchanged.

RESULT (measured, rebuilt .so via rch cargo build --features extension-module): n=400 fnx 0.054ms vs
nx 0.467ms = **8.69x FASTER** (was 0.063x; ~140x self-speedup). PARITY: exact vs nx over 8 random
directed graphs incl reciprocal pairs + self-loops; fallback cases (undirected src / multigraph /
to_directed) re-verified exact. Conformance GREEN: 5832 passed in the conversion/view/degree/operator
suite; full tests/python 49243 passed (only the 3 pre-existing find_induced_nodes-cluster fails, zero
new). NOTE: this fixes number_of_edges/size; the iterate-the-view case (edges()/degree() materializing
attrs) still needs the broader native conversion-view adjacency — the degree-count native is the
reusable foundation for it. LEVER: route VIEW aggregate queries to a native index-space scan over the
SOURCE graph instead of the Python-synthesized view adjacency.

## SWEEP 4 (cc, 2026-06-28): generators / IO / tree / approximation — ALL wins; algorithm vein MINED across 4 sweeps

4th fnx-vs-nx sweep (generators, IO round-trips, tree, approximation; n=400-2000). ALL wins vs nx:
complete_graph 13.9x, is_forest 772x, is_tree 27x, balanced_tree 6.4x, random_regular 4.2x,
approx_vertex_cover 3.6x, grid_2d 2.5x, read_weighted_edgelist 2.4x, mst_edges 2.3x, random_tree
2.2x, convert_node_labels 1.9x, gnp 1.8x, approx_clique 1.6x, watts_strogatz 1.3x, barabasi_albert
1.1x, relabel/read_adjlist/powerlaw ~1.0-1.04x. Only sub-1.0 (all marginal, not fixable in Python):
adjacency_data 0.678x (ALREADY native `adjacency_data_simple` — this is the native-build floor),
approx_node_conn 0.779x (delegated namespace), write→node_link 0.919x (~parity).

FRONTIER after 4 sweeps (~80 fns across shortest-path/centrality/flow/matching/operators/traversal/
community/tree/generators/IO/approximation): the findable algorithm-level vein is MINED. This
session shipped the 3 substantial gaps it found (flow_hierarchy 7.1x, pagerank 6.7x,
all_pairs_dijkstra/closeness 3.4-3.8x). Every remaining vs-nx gap is ONE of three big-primitive /
hard classes, NONE Python-wrapper-fixable (proven by repeated no-gain attempts this session):
  1. CONVERSION-VIEW / VIEW MATERIALIZATION — to_undirected/to_directed query (number_of_edges/
     edges/degree/adj 0.06-0.7x), in_edges(data)/nodes(data)/adjacency. Needs a NATIVE conversion-
     view adjacency + persistent ordered Python-object mirror. Narrow native sub-fix for conversion
     number_of_edges (documented below): undirected_view = D - reciprocal_pairs (native
     overall_reciprocity); directed_view = 2*(U - selfloops) + selfloops; same-direction = source
     count — but the iterate-the-view case still needs the adjacency primitive.
  2. CONSTRUCTION TAX — union 0.80x etc., parity-bound by per-node label PyO3 round-trips
     ([[reference_construction_tax_relabel_lever]]).
  3. SCIPY/LAPACK — subgraph_centrality 0.70x, non_randomness 0.87x, hits small-n
     ([[reference_native_vein_mined_lapack_frontier]], [[reference_dense_eigsolver_tax]]).
NEXT REAL LEVER = the native conversion-view/object-mirror primitive (a multi-turn Rust build), not
another sweep. See [[reference_all_pairs_dijkstra_float_typeprop_tax]] for the full sweep record.

## DOMAIN MAP + 2 NO-SHIPs + BLOCKER (cc, 2026-06-28): dijkstra/bellman_ford family & flow/matching/operators/traversal sweeps — all wins except the conversion-view materialization wall

Two more fnx-vs-nx sweeps after the closeness win (per-edge add_edge-built, float weights, n=400-500):

SHORTEST-PATH FAMILY (all WINS, leave alone): single_source_dijkstra_path_length 3.0x, _path 3.6x,
(dist,paths) 3.6x, all_pairs_dijkstra 3.4x, _path 1.2x, all_pairs_bellman_ford_path_length 4.0x,
ss_bellman_ford_path 4.1x, dijkstra_predecessor 2.0x, harmonic(distance) 1.04x, eccentricity 181x.

FRESH DOMAINS (all WINS): maximum_flow_value 3.65x, minimum_cut_value 2.69x, maximal_matching 9.9x,
dfs/bfs_tree 3.6x, topological_sort 19x, is_DAG 22x, complement 4.2x, line_graph 4.1x, find_cliques
1.1x, immediate_dominators 3.4x, greedy_modularity 26x, node_connectivity 17.8x, difference 1.34x,
compose 1.3x, convert_to_dict_of_lists 1.8x. max_weight_matching 0.956x = the known rebuild
artifact ([[reference_order_sensitive_rebuild_benchmark_artifact]]), not real.

NO-SHIP #1 (reverted): `single_source_bellman_ford_path_length` 0.868x — has the same all-float
type-prop pattern as the shipped all_pairs fix ([[reference_all_pairs_dijkstra_float_typeprop_tax]]),
so I added the all-float skip. ~0 gain (0.868x->0.872x): for SINGLE-source the second (paths)
kernel + _sp_propagate_int_types walk is negligible (the 497k tax only multiplies in the all-PAIRS
case, already fixed). The 0.868x is in the bellman_ford kernel itself, not the type-prop. Reverted.

NO-SHIP #2 (reverted): `to_undirected(G).number_of_edges()` 0.063x (fnx 8.0ms vs nx 0.44ms, 16x) —
the to_undirected VIEW construction is already lazy/O(1) (0.003ms, beats nx); the gap is
`number_of_edges()` which does `len(self.edges())`, materializing the whole conversion-view edge
list (per-edge tuple build + reciprocal dedup) in Python. Tried `sum(degree)//2` (nx's formula,
byte-exact across simple/multi x directed/undirected): STILL 0.055x — `_ConversionGraphViewBase.degree`
iterates the SAME slow conversion-view `self.adj[node]` (per-node merged succ+pred adjacency rebuilt
in Python with attr materialization). The bottleneck is the conversion-view ADJACENCY, not the count
method. Reverted.

BLOCKER (conversion-view materialization wall): _ConversionGraphViewBase (to_undirected/to_directed)
answers degree/edges/number_of_edges/size/adjacency by synthesizing the merged adjacency in Python
per node — O(V+E) heavy per-element work vs nx's plain-dict view. Python-unfixable (2 no-gains).
FIX PATHS for a future native primitive: (a) a native conversion-view adjacency (the real lever,
benefits all view queries); or (b) narrow: route the undirected view's number_of_edges/size to a
native count via `undirected_edges = directed_edges - reciprocal_pairs` — fnx already has a native
`overall_reciprocity` binding (its wrapper computes n_overlap_edge = 2*reciprocal_pairs directly), so
number_of_edges = D - n_overlap_edge//2 in O(1) after one native O(E) scan. Same wall as
[[reference_warm_saturation_map_and_coldeig_noise]] / [[reference_algo_domain_mined_out_sweep]]
(in_edges/nodes(data)/adjacency view-materialization). ALGORITHM vein now broadly MINED — remaining
vs-nx gaps are this view wall + construction tax (union 0.80x) + scipy/LAPACK (subgraph_centrality
0.70x, non_randomness 0.87x, [[reference_native_vein_mined_lapack_frontier]]).

## SHIPPED (cc, 2026-06-28): all_pairs_dijkstra_path_length / closeness_centrality(distance) FLOAT weights 1.0x/0.69x -> 3.76x/3.44x vs nx

A second fnx-vs-nx algo sweep (per-edge add_edge-built, float weights) found weighted
closeness_centrality at **0.694x** (fnx 597ms vs nx 415ms). Profile: the native all_pairs_dijkstra
kernel is fast (0.2s) but `all_pairs_dijkstra_path_length`'s mixed/float branch ran
`_sp_propagate_int_types` per source — which, for any distance that is integer-VALUED (a sum of
float weights like 1.0+2.0=3.0), walks the whole path doing per-edge `G[u][v]` PyO3 lookups
(~497k calls = 0.95s) just to re-derive int-vs-float typing... and for all-FLOAT weights it always
concludes "float". Pure waste.

FIX (br-apdfloat): add an all-float fast path to `all_pairs_dijkstra_path_length` (symmetric to the
existing all-int one). New `_sp_edge_weights_all_float(G, weight)` returns True iff every edge
carries an explicit non-bool float; then no distance can be int EXCEPT nx's source seed
(`dist[source]=0`, int), so use the cheap length-only kernel `_raw_all_pairs_dijkstra_path_length`,
set `inner[source]=0`, and skip `_sp_propagate_int_types` + the paths kernel entirely. Proven
byte-identical to the old mixed path (the only int it ever produced for an all-float graph was the
source 0).

RESULT (measured n=500 directed float): `all_pairs_dijkstra_path_length` fnx 119ms vs nx 448ms =
**3.76x** (was ~1.0x parity); `closeness_centrality(distance="weight")` fnx 120.87ms vs nx 415ms =
**3.44x** (was 0.694x). Benefits every weighted all_pairs consumer (harmonic via distance, etc.).
PARITY: EXACT (values + int/float TYPES + per-source order) verified vs nx across
directed/undirected x float/int/mixed, and closeness exact for directed+undirected float.
Pure-Python wrapper change, no .so rebuild. Conformance: 4568 passed in the
dijkstra/shortest/closeness/centrality/weighted suite; full tests/python 49243 passed, the 8
remaining fails are ALL pre-existing & unrelated (find_induced_nodes delegation cluster + coverage/
gexf/unused-raw report-currency meta-tests + waxman RNG — none call all_pairs/closeness; my only
code delta vs main is this +43-line dijkstra float branch).

LEVER: type-preservation post-processing (int-vs-float, key re-typing) over native results is a
common hidden O(V^2) tax; add a fast path for the homogeneous case where the re-derivation is a
provable no-op. Audit single_source_dijkstra / bellman_ford for the same all-float skip.

## SHIPPED (cc, 2026-06-28): DiGraph/MDG weighted pagerank 0.50x -> 6.66x vs nx — directed edges_dirty never cleared after sync (+2 correctness fixes)

A fnx-vs-nx algorithm sweep (n=600/2000) found weighted pagerank the worst gap: DiGraph weighted
pagerank **0.50x vs nx** (fnx 8.5ms vs nx 4.2ms at n=2000), gap GROWING with n. Root cause: the
DiGraph/MultiDiGraph `_fnx_sync_edge_attrs_to_inner` / `_fnx_sync_attrs_to_inner` (digraph.rs)
flushed the Python edge-attr mirror into `inner` but — unlike PyGraph (lib.rs:11098) — NEVER did
`edges_dirty.store(false)`. So after a per-edge `add_edge(u,v,weight=w)` (the most natural nx
idiom) or any `edges(data=True)` walk, `edges_dirty` stayed TRUE forever: EVERY weighted native
call (pagerank / dijkstra / matrix exporters) re-walked the whole O(E) mirror AND the scipy matrix
cache (gated on the dirty token, algorithms.rs:3677) never engaged → matrix rebuilt every call.
Measured: DiGraph weighted pagerank on an add_edge-built n=2000 graph was **27ms** vs **0.63ms**
for a bulk-built (clean) graph = 43x self.

FIX (br-syncdirty): (1) clear `edges_dirty` (+ reset granular `edge_dirty_keys`) at the end of the
four directed sync methods, mirroring PyGraph. (2) CORRECTNESS — clearing dirty exposed a
PRE-EXISTING latent bug present for undirected Graph too: the scipy matrix cache key is structural
(nodes_seq/edges_seq), NOT attr VALUES, so `pagerank` after `G[u][v]['weight']=x` returned the
STALE result; its only invalidation had silently relied on edges_dirty never being cleared. Added
an explicit cache drop in `_sync_rust_edge_attrs`: when a cached matrix exists AND attrs are dirty
(about to flush), pop `_fnx_pagerank_scipy_matrix_cache`. A subsequent edge-dict access re-marks
dirty, so repeat calls stay both fast (clean → cache hit) and correct (mutated → rebuild).

RESULT (measured, rebuilt .so via rch cargo build --features extension-module): DiGraph weighted
pagerank n=2000 fnx **0.632ms** vs nx **4.206ms** = **6.66x FASTER** (was 0.50x / 8.5ms; 43x self
on dirty graphs). Affects dijkstra / weighted shortest paths / to_scipy/to_numpy on
add_edge-built or edges-walked directed graphs too. CORRECTNESS verified: post-`G[u][v][...]=x`
mutation now matches nx for Graph/DiGraph/MultiGraph/MultiDiGraph (was wrong for undirected on
main; would have been wrong for directed). Conformance GREEN: 11579 passed (full tests/python; the
1 unrelated fail = pre-existing `test_coverage_gaps` on find_induced_*/read_edgelist delegation,
untouched by this change, identical on origin/main).

BONUS FIX (br-prcallable): the non-string-weight-key pagerank path raised `NameError: name 'G' is
not defined` — `_pagerank_outgoing_weights(succ_row, ...)`'s simple-graph branch still referenced
`G.succ[node]` (stale from the succ-snapshot refactor; neither G nor node in scope). Use the
`succ_row` param (matching the multigraph branch + docstring). Was RED on origin/main; now green.

LEVER: when a perf path's correctness silently depends on a dirty flag never being cleared, clearing
it for speed needs an EXPLICIT cache invalidation. Audit other `vars(G)[...]` caches keyed on
nodes_seq/edges_seq for attr-mutation staleness.

## SHIPPED (cc, 2026-06-27): flow_hierarchy(weighted) 0.045x -> 7.12x vs nx (~157x self-speedup) — kill the per-SCC subgraph().size() bomb

The gauntlet (now runnable via the scipy guard below) surfaced a CATASTROPHIC gap:
`flow_hierarchy(G, weight=...)` ran at **0.045x vs nx** (fnx 55.7s vs nx 2.50s for 100 calls on a
900-node weighted DiGraph = ~22x SLOWER). Root cause: `_flow_hierarchy_weighted_scc_fold` computed
the cyclic weight as `sum(G.subgraph(component).size(weight) for component in
strongly_connected_components(G))` — a `subgraph(view).size(weight)` PER SCC. fnx's subgraph is a
filtered VIEW and `.size(weight)` runs the filtered-view degree machinery; building one view per SCC
(hundreds, for a graph that's mostly small SCCs) is the subgraph-in-loop bomb (br-r37-c1-wfoee
family, [[reference_subgraph_copy_in_loop_bomb]]). nx does the same per-SCC subgraph loop but its
views are lightweight, so nx was 22x ahead.

FIX (br-flowhier, __init__.py:33472): one O(V+E) pass — tag every node with its SCC id once
(`scc_id[node] = index`), then `cyclic_weight = sum(w for u,v,w in G.edges(data=weight, default=1)
if scc_id[u]==scc_id[v])`. Same value as the per-SCC subgraph sizes (a self-loop sits in its own
node's SCC, counted once, exactly matching subgraph.size). No subgraph views at all.

RESULT (measured): bench fixture (cargo bench -p fnx-python --bench public_api_gauntlet --
flow_hierarchy, rch) fnx **354.52ms** vs nx **2.523s** = **7.12x FASTER** (was 0.045x). Local
n=900 5.84x. Self-speedup ~157x (55.7s -> 0.355s). PARITY: byte-identical to nx for n=50/200/900
(float order happened to coincide; even where it doesn't, ~ULP < the round(.,9)/`_equiv`/approx
the conformance suite asserts). Conformance GREEN: 311 passed across test_hierarchy_module_parity,
test_scalar_metrics_parity, test_network_summary_measures_conformance, test_rust_wiring_parity,
test_directed_api_health_parity, test_kernel_fastpath_edgecase_parity, test_euler_triad_hierarchy_parity
(+323 in the broader flow/metrics -k sweep). Pure-Python wrapper change, no .so rebuild.

LEVER (reusable): any wrapper computing a per-component / per-group aggregate via
`G.subgraph(group).<metric>()` in a loop is a subgraph-view bomb — replace with one tagged pass
over nodes/edges. Audit other `for c in ...components...: G.subgraph(c)` sites.

Other gauntlet workloads (same run, sample-size 10, all WINS — no further dig): within_inter_cluster
1.27x, non_edges_sparse 1.17x, ubizp MG SSSP 1.34x, raw adamic_adar 1.50x, resource_allocation
2.17x, cn_soundarajan_hopcroft 2.36x, ra_index_soundarajan_hopcroft 4.79x, digraph_to_undirected
1.14x, multidigraph_to_scipy 1.44x; raw_preferential_attachment ~0.92x (near-parity, materialization
floor). flow_hierarchy was the ONE real gap on this surface.

## TOOLING-FIX + BLOCKER (cc, 2026-06-27): public_api_gauntlet bench — fixed os.getcwd() sys.path (rch-broken), now gated only by scipy missing on workers

The `public_api_gauntlet` bench (the only vs-nx bench covering ALGORITHM-level workloads —
flow_hierarchy, within_inter_cluster, non_edges_sparse, ubizp MG single_source_shortest_path,
raw link-prediction adamic_adar/resource_allocation/cn_sh/ra_sh/preferential_attachment,
digraph_to_undirected_attr_heavy, to_scipy_sparse_array) could NOT run via `rch exec` at all:
its preamble built sys.path from `os.getcwd()`, which is the repo root only when cargo is
launched there — on a remote worker the CWD differs, so `import networkx.exception` / the helper
import failed and the bench panicked (line 62/65) before any workload ran.

FIXED (br-gauntletfix, this commit): inject the repo root from `CARGO_MANIFEST_DIR` (compile-time
absolute) into the preamble, mirroring `networkx_head_to_head`'s prepare_* path setup. VERIFIED
the fix works — the rch run now advances PAST the path stage to the real next gate.

REMAINING BLOCKER (worker-provisioning, not code): the rch workers (hz2 etc.) lack `scipy`, and
the helper builds `_FNX_MDG_MATRIX = fnx.to_scipy_sparse_array(...)` at MODULE TOP-LEVEL
(public_api_gauntlet.py:562), so the whole helper import dies with
`ModuleNotFoundError: No module named 'scipy'`. To make the gauntlet fully rch-runnable: (a)
provision scipy on workers, OR (b) make the scipy graph/matrix build + the two
`*_to_scipy_sparse_array_*` workloads lazy/guarded so the helper imports without scipy and the
~10 non-scipy algorithm workloads run. NOTE the gauntlet also builds heavy graphs (2000-node MDG,
link-pred overlap graphs) and got OOM-killed (exit 144) when run locally under swarm contention —
size down or run on an unloaded host. Until then these algorithm-level workloads stay UNMEASURED
(the one vs-nx surface not yet mapped; the [[head_to_head]] view/degree surface IS mapped + mined).

## BLOCKER / VEIN-MAP (cc, 2026-06-27): full networkx_head_to_head sweep — every remaining benched gap is the per-element PyObject materialization floor (kernel-mined-out)

Ran the WHOLE `cargo bench -p fnx-python --bench networkx_head_to_head` suite (hz2). Every
group is a WIN except a tight cluster of gaps, and each gap is bound by the SAME wall: fnx
stores attrs/keys as native CgseValue + String node names, so any view that yields per-element
Python objects must REBUILD them (py_node_key clone + cgse_value_to_py / PyInt + PyTuple) — work
nx skips because it already stores the Python objects. This is NOT removable by kernel/hashing
micro-opts (confirmed by the eilce NO-SHIP 6ee21ea28 "halved Rust hashing, fnx UNCHANGED" AND my
own in_edges restructure NO-SHIP ef897a28e). Map of this sweep (nx/fnx, hz2):

WINS (do not touch): sticky_edge_dirty dijkstra-after-edges-data 7.4x; mdg SCC 2.86x;
descendants 1.76x; triangular_lattice 2.25x; hexagonal_lattice 1.58x; out_edges_nbunch_keys_data
1.95x; mdg_edges_keys ~1.0x.

GAPS — ALL materialization-floor-bound / COVERED, DO NOT re-dig with kernel work:
- mdg in_edges(keys,data=<key>) 0.24x — eager per-edge tuple list vs nx lazy InMultiEdgeDataView.
- mg selfloop_edges(keys,data=<attr>) 0.348x — pristine store-read ALREADY active
  (lib.rs:5246/5260); floor = 2502 PyTuple+value builds + NodeIterator __next__ (vs nx C gen).
- mdg in_degree(weight) 0.55x / out_degree(weight) 0.60x — ALREADY route to the bulk native
  (__init__.py:4862; native_weighted_directional_degree store_int path is optimal:
  predecessors_iter + edge_attr_values, no per-key re-hash). Floor = 1800 py_node_key + PyInt
  total builds. eilce already proved reducing native work here is invisible.
- mg degree(nbunch,weight) 0.582x — covered by the 752b2b98c weighted-subset native; residual
  is the per-node pair materialization.
- mg size(weight) 0.625x — deliberately routes through degree(weight) (sizedeg comment,
  __init__.py:496); inherits the degree-view materialization floor.

CONCLUSION: the benched view + weighted-degree vein is MINED OUT for kernel levers. The only
remaining lever is ARCHITECTURAL — a persistent ordered Python-object mirror (store the node-key
and edge-attr-value Python objects alongside the native store, kept in sync, so views hand back
borrowed refs like nx) OR true lazy native view-iterators that don't pre-build the list. Both are
large primitives, not micro-opts, and even lazy iterators don't escape the per-element PyObject
build for full-iteration `sum(...)` consumers. Surfaced as a blocker; not attempting a kernel
micro-opt here (would be a 3rd NO-SHIP on the same floor).

## SHIPPED (cc, 2026-06-27): MDG data=<key> reads — store-read fast path gated on !edges_dirty (skip per-edge edge_key String build) — out_edges(nbunch,keys,data) 0.57x->0.65x

Next core_laggards gap after the in_edges NO-SHIP below: `out_edges(nbunch, keys=True,
data="weight", default=0)` on the CUSTOM-key `MultiDiGraph` (n=700/e=12600). cargo bench
`networkx_head_to_head -- core_laggards`.

Root cause (NOT the same as the in_edges eager-materialization wall): the bench shares one
`mdg_custom_fnx` between the data=True and data=<key> workloads. The setup/data=True call runs
`ensure_edge_py_attrs`, which MATERIALIZES the edge mirror WITHOUT marking edges dirty — so by
the time data=<key> runs the graph is **non-pristine but clean** (`!edges_dirty`). The native
data=<key> path then falls to `edge_data_value_or_default`, whose first branch unconditionally
builds a `Self::edge_key(u,v,key)` String (heap alloc + format) per edge just to probe the
mirror dict — the avoidable tax (nx does a plain `dd[key]`).

Lever (br-mdg-datakey-storeread): add a fast path at the top of `edge_data_value_or_default` —
when `!edges_dirty` (CgseValue store authoritative, same invariant the weighted-degree fast
path uses) AND `data` is a `PyString`, read the scalar value straight from `self.inner.edge_attrs`
and return `cgse_value_to_py`, skipping the per-edge `edge_key` String build + mirror probe.
Map values fall through to the mirror path for dict identity; the dirty case is unchanged. This
strictly REDUCES work on the common scalar path (cannot regress it; only a rare extra store
lookup for Map values), and benefits ALL MDG data=<key> reads (out_edges/in_edges/edges/
selfloop) once a prior data=True materialized the mirror.

MEASURED (cargo bench, hz2): fnx `out_edges_nbunch_keys_weight` 800µs -> 747µs, nx/fnx 0.57x ->
~0.65x. Measurement caveat: rch worker load varies run-to-run and within-run nx/fnx is NOT
worker-invariant (an UNCHANGED control workload swung 35% across workers), so the exact ratio is
noisy; the ship rests on the change being a provable per-edge String-alloc removal (mechanistic
strict reduction), not on the noisy delta alone. Conformance GREEN: 1863 targeted parity tests
pass (edge_attr_dirty_sync, edge_attr_post_mutation_sync, edges_data_*, view_pickle, selfloop,
multidigraph, get_edge_data, degree) incl. the live-mutation dirty path; fmt + clippy -D clean.

## NO-SHIP (cc, 2026-06-27): MDG in_edges(keys,data=key) single-pass bucket walk + node-obj hoist — REGRESSION 0.263x->0.190x

Biggest measured core_laggards gap (cargo bench `networkx_head_to_head -- mdg_in_edges_data`,
`MultiDiGraph` n=700/e=12662, workload `sum(k+v for _,_,k,v in mdg.in_edges(keys=True, data="weight", default=0))`).
Baseline vs NetworkX (worker hz2, within-run nx/fnx): **fnx 9.09 ms / nx 2.39 ms = 0.263x** (3.8x slower).

Lever (br-mdg-inedges-datakey): the existing PRISTINE fast path
(`_native_mdg_in_edges_data_key`) rebuilt the target node object once PER EDGE and the
source object once per parallel key, re-hashed `(source,target)` for both
`edge_keys()` (Vec<usize> alloc/pair) and `edge_attrs()` (per key). Rewrote it to hoist
`py_node_key(target)` to once/target and `py_node_key(source)` to once/pair, drop the Vec
alloc via `predecessors_iter`, walk the parallel-edge bucket ONCE/pair via a NEW
`MultiDiGraph::edge_bucket_items` accessor (key+AttrMap straight off the iterator, no per-key
re-hash), and skip the `py_edge_key` String build when `edge_py_keys.is_empty()`.

MEASURED (same worker hz2, within-run nx/fnx): **fnx 13.86 ms / nx 2.64 ms = 0.190x** — a
~1.5x REGRESSION on fnx-side wall time vs ORIG (nx held ~2.4-2.6 ms). Cross-worker numbers
were misleading (vmi1264463 showed fnx 36.4/nx 14.2 = 0.392x, "better" ratio) — the within-run
nx/fnx ratio is NOT worker-invariant (Rust and Python scale differently per host), so ONLY
same-worker comparison is valid; on hz2 the lever loses. cargo check + bench's own
`fnx == nx` setup assert passed (values/order byte-identical), so it is correct-but-slower.
REVERTED (not landed); the `edge_bucket_items` accessor + rewrite live only in worktree
`.scratch/franken_networkx-cc-mdg-inedges-a92c6e3a3`.

Lesson: the residual MDG in_edges cost is NOT the redundant hashing/allocs I removed — the
iterator-adapter walk (`predecessors_iter` + `edge_bucket_items` nested `impl Iterator`)
did not beat the original plain `Vec` collect path, and the floor is the per-edge PyObject
tuple+value materialization (eager list of 12662 4-tuples vs nx's lazy `InMultiEdgeDataView`
generator). Real lever = a LAZY native view iterator that yields tuples on demand, not kernel
micro-opts on the eager path (consistent with the "needs lazy view objects" frontier note).

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

## 2026-06-25 CopperCliff WIN+FIX: is_perfect_graph bespoke DFS -> chordless_cycles — 0.046x->0.93-1.65x

is_perfect_graph was the next-biggest gap: 0.046x (fnx 1958ms vs nx 89ms on a perfect path(60)). The
Python wrapper used a bespoke per-node DFS (_has_odd_hole) that was exponential AND capped path length at
24 (so it SILENTLY MISSED odd holes longer than 24 = a latent correctness bug vs nx). Replaced with nx's
exact algorithm: `not any(len(c)>=5 and odd for c in chain(chordless_cycles(G), chordless_cycles(
complement(G))))`, using fnx's existing chordless_cycles + complement. Boolean = order-invariant -> byte-
exact (0/12 graph types; conformance -k perfect 102 passed). 0.046x -> 0.93x (path60 ~parity) / 1.65x
(BA60 win) / 0.84x (bipartite); also FIXES the >24-length-hole correctness divergence. Python-only
periphery (no build). LEVER: a bespoke exponential search reimplemented where nx uses a better-engineered
primitive (chordless_cycles) -> route to the existing fnx primitive matching nx's algorithm exactly.

## 2026-06-25 CopperCliff property-check + LCA/cuts/matching sweep — wins; min_weight_matching REJECT

Property checks (worst-case inputs): WINS — is_semiconnected 8.7x, is_attracting_components 8.5x,
is_strongly_connected 3.4x, is_biconnected 2.3x, has_bridges 2.7x, is_regular 3.0x; is_threshold_graph
0.161x is 0.002ms (PyO3/dispatch noise, not real). LCA/disjoint-paths/cuts/matching: WINS — node_disjoint
_paths 9.5x, edge_disjoint_paths 7.3x, all_node_cuts 2.3x, is_perfect_matching 8.5x, wiener_index 13.7x,
all_pairs_lowest_common_ancestor 1.2x, all_simple_paths(cutoff) 1.28x.
REJECT: min_weight_matching 0.79x (3.4ms vs 2.7ms) + min_edge_cover 0.62x (inherits it, defaults to
max_weight_matching). Verified NOT a layout phantom — fair baseline (both graphs from the same edgelist)
is also 0.793x. fnx's blossom (max/min_weight_matching) is genuinely ~0.79x of nx. The blossom algorithm
is ORDER-SENSITIVE (the matching depends on augmenting-path traversal order); optimizing the kernel risks
matching-value/identity divergence for a ~0.7ms gap -> not worth it. REJECT. No new clean win this batch;
the catastrophic-worst-case property-check vein (is_at_free, is_perfect_graph) is mined out — the rest are
already wins.

## 2026-06-25 CopperCliff chordal/dominating/eulerian sweep — wins; connected_dominating_set REJECT

WINS: complete_to_chordal_graph 5.09x, chordal_graph_cliques 10.0x, maximal_matching 6.67x, eulerize
3.16x, min_weighted_dominating_set 1.57x, is_dominating_set 3.15x, edge_load_centrality 1.38x,
percolation_centrality 1.85x, rich_club(unnorm) 43x, dominating_set 0.89x (~parity, sub-ms).
REJECT (both set-order-locked, sub-ms or known): connected_dominating_set 0.318x (0.846ms) — DELEGATED via
_call_networkx_for_parity; nx's algorithm is a heap-based greedy (grow a tree from the max-degree node,
max-heap of "seen" nodes, unseen-neighbor counts) whose specific CDS depends on heap + max-degree
tie-break (set/iteration) order -> de-delegating in-process risks divergence for a sub-ms gap, REJECT.
greedy_color(connected_sequential_dfs) 0.431x is the already-known set-order-locked conversion case
(reference_parity_blocked_by_set_order). No new clean win this batch.

## 2026-06-25 CopperCliff TSP/community sweep — wins; greedy_tsp SURFACE (approx-conversion-tax, order-sensitive)

WINS: k_clique_communities 3.2x, local_efficiency 9.6x, spectral_bipartivity 13.5x; christofides 0.807x /
girvan_newman 0.92x / simple_cycles(directed small) 0.96x ~parity. CORRECTNESS NOTE: fnx.tournament.
hamiltonian_path WORKS on a 300-node tournament where nx CRASHES (RecursionError) — fnx is MORE correct
(like is_distance_regular); no gap.
SURFACE: greedy_tsp scales 0.15x@n12 -> 0.08x@n50 -> 0.06x@n150 (fnx 23ms vs nx 1.17ms at n=150). It's
delegated via the approximation-namespace __getattr__ which does a FAITHFUL O(n^2) fnx->nx conversion on
the (dense, complete) weighted graph = the conversion tax (reference_approx_namespace_conversion_tax).
De-delegatable via a concrete fnx.approximation.greedy_tsp (vertex_cover precedent) BUT: the tour is
ORDER-SENSITIVE (nearest-neighbor min() tie-breaks by iteration order) so it needs nx's EXACT algorithm
run in-process on a weight snapshot (a numpy-vectorized argmin diverges on the many weight ties), and the
weight snapshot is itself O(n^2) construction-floor-bound -> best ~0.3-0.5x, not >nx. Not shipped (order-
sensitive + conversion-floor for a TSP heuristic); recorded as a de-delegate target. No clean win.

## 2026-06-25 CopperCliff distance/structural-holes/bipartite-centrality sweep — ALL WINS (no gap)

Final coverage sweep, all fnx >= nx (no gap, nothing to fix): eccentricity 16.6x, diameter 16.8x, center
16.5x, periphery 16.1x, barycenter 13.0x, effective_size 5.0x, constraint 5.2x, bipartite.betweenness
17.4x, bipartite.closeness 1.06x, robins_alexander_clustering 75.9x, resistance_distance 141x. (dispersion
0.704x is 0.093ms = sub-ms noise; eccentricity(weighted) "0.001x" was a bogus None baseline.) These
distance/structural-hole/bipartite-centrality domains join the already-verified frontier.
PERIPHERY TERMINAL: ~30+ function categories now measured at-or-above nx across this session. The last
three sweep batches were increasingly all-wins; fresh sweeps now CONFIRM wins rather than find gaps. The
only residual sub-1.0x items are order-locked-delegations (greedy_color non-default, connected_dominating
_set), order-sensitive kernels (blossom matching, greedy_tsp), and architectural-core (sticky-edges_dirty
master lever + dual-storage construction substrate). The sole high-value remaining lever is the core
sticky-edges_dirty fix (pyclass(extends=PyDict), ~9 fns), surfaced f91977f1e/2578350fe, blocked on core
access + corrupted agent-mail. Session: 9 clean vs-nx wins shipped (prufer, gaussian, is_distance_regular,
tree_broadcast_center, subgraph_centrality 34x, hopcroft_karp 20x, random_cograph, is_at_free 166-305x,
is_perfect_graph+fix) + *_all operator cluster + paley loss-reduction.

## 2026-06-25 CopperCliff per-pair/group/flow sweep + bespoke-kernel grep — all wins / vein mined

Per-pair-connectivity / group-centrality / flow sweep: ALL WINS — node_connectivity 35.7x, communicability
26.6x, second_order_centrality 22.3x, stoer_wagner 7.3x, group_closeness 7.5x, global_reaching 4.18x,
current_flow_betweenness_subset 3.7x, katz 3.3x, average_node_connectivity 1.65x (group_betweenness 0.90x /
non_randomness 0.756x near-parity, not real). Also grepped fnx-algorithms for the is_at_free O(n^4)
per-pair-fresh-BFS pattern: the nested-loop+BFS fns found (single_source_shortest_path, bfs_layers,
ancestors, transitive_closure, wiener_index) are all LEGITIMATE traversals (already benched as wins), NOT
pathological -> bespoke-kernel vein mined. find_asteroidal_triple is still O(n^4) but order-locked (returns
the triple) so left. CONCLUSION REINFORCED: periphery exhausted of gaps; sole high-value residual is the
core sticky-edges_dirty lever.

## 2026-06-25 CopperCliff matrix-builder + tree-function sweep — ALL WINS (no gap)

Matrix/spectral-matrix builders + tree fns, all fnx >= nx: modularity_matrix 1.74x, directed_modularity
2.45x, bethe_hessian_matrix 1.81x, directed_laplacian_matrix 1.15x, directed_combinatorial_laplacian
1.21x, attr_matrix 1.83x, adjacency_spectrum 1.45x, katz_centrality_numpy(dir) 1.14x, prefix_tree 0.82x
(~parity). Matrix builders show NO numpy-eigh issue (eigvalsh / efficient construction). to_nested_tuple
showed 0.396x COLD but warm is 1.32-1.51x FASTER (cold-measurement artifact, same class as random_cograph's
0.299x). NO real gap. ~37 function categories now at-or-above nx; periphery comprehensively exhausted.
Sole high-value residual remains the core sticky-edges_dirty lever (pyclass(extends=PyDict), ~9 fns;
surfaced f91977f1e), blocked on core-file access + corrupted agent-mail.

## 2026-06-25 CopperCliff serialization-format sweep — wins/near-parity; periphery definitively exhausted

Serialization round-trips (GML/GraphML/graph6/sparse6/pajek/gexf/json), all fnx >= nx or near-parity:
parse_gml 5.80x, to_graph6_bytes 1.45x, from_graph6_bytes 1.15x, to_sparse6_bytes 1.19x, node_link_data
1.27x, generate_gml 1.03x, generate_graphml 0.97x; generate_pajek 0.732x / generate_gexf 0.842x /
adjacency_data 0.815x are near-parity construction-string-floor (modest, not clean); forest_str 0.122x is
0.003ms (PyO3 noise). No real gap.

PERIPHERY DEFINITIVELY EXHAUSTED (~40 function categories measured this session, all at-or-above nx): the
last 7 sweep batches were all-wins. Every residual sub-1.0x is (a) cold-measurement noise (warms to a win,
e.g. to_nested_tuple/random_cograph cold), (b) set-order-locked / order-sensitive (greedy_color non-default,
connected_dominating_set, blossom matching, greedy_tsp -- must match nx's exact iteration order), or (c)
construction-string-floor / architectural-core (the sticky-edges_dirty master lever + dual-storage
substrate). Sole high-value remaining lever = sticky-edges_dirty (pyclass(extends=PyDict), ~9 fns;
f91977f1e), blocked on core-file access (BlackThrush's active lib.rs) + corrupted agent-mail. 9 clean
vs-nx wins shipped this session; further vs-nx progress needs an operator unblock, not more sweeping.

## 2026-06-25 CopperCliff STATUS: 3 worst current gaps all = unaddressed sticky-edges_dirty lever

Re-measured the worst known core gaps on current HEAD (03da2d866) and confirmed the sticky-edges_dirty
master lever is STILL NOT implemented (`edges_dirty.store(false)` count in lib.rs = 0; BlackThrush's recent
core commits are degree-nbunch native paths / copy / clear_edges, NOT the marking-dict-subclass fix):
  dijkstra_path (BA n=2000 weighted, 0->1900)  fnx 21.2ms  nx 3.49ms  0.165x  <- WORST
  to_scipy_sparse_array(weight) (n=2000)        fnx 20.6ms  nx 7.85ms  0.381x
  MultiGraph.degree(weight) FLOAT (n=1500)      fnx 13.4ms  nx 9.75ms  0.726x
All three route through a native-store read preceded by a STICKY full resync (_fnx_sync_edge_attrs_to_inner
re-runs ~16ms every call because edges_dirty never clears; dijkstra's wrapper syncs unconditionally). No
periphery path: the wrapper can't tell the store is fresh (sticky flag), and a mirror-read pays the string
tax (the 0.5x weighted-degree pattern). THE fix is the pyclass(extends=PyDict) marking edge-dict +
clear-after-sync (f91977f1e/2578350fe, ~9 fns), in BlackThrush's ACTIVELY-edited lib.rs. Unaddressed for
10+ CopperCliff turns; agent-mail corrupted so it can only be handed off via this ledger. OPERATOR ACTION:
restore agent-mail + reassign fnx-python/lib.rs to CopperCliff with a mandate, OR BlackThrush implements it.
Periphery is exhausted (~40 categories at-or-above nx, 9 wins shipped); this lever is the only vs-nx
progress left and is purely coordination-blocked.

## 2026-06-25 CopperCliff girth/edge-betweenness/floyd/spanning-tree sweep — ALL WINS (no gap)

New-coverage sweep, all fnx >= nx: girth 6.81x, edge_betweenness_centrality 30.4x, load_centrality 33.9x,
floyd_warshall 15.2x, betweenness_centrality_subset 5.81x, johnson 1.63x, voterank 1.96x, prufer_to_tree
(from_prufer_sequence) 1.60x, random_spanning_tree 1.05x (~parity, RNG-bound). is_triangle_free 0.144x is
0.002ms (PyO3 noise, trivial check). bipartite König to_vertex_cover 0.917x (~parity). No real gap.
~45 function categories now measured at-or-above nx this session (8+ consecutive all-wins sweep batches).
Periphery conclusively exhausted; sole vs-nx progress = the coordination-blocked sticky-edges_dirty core
lever (dijkstra 0.165x / to_scipy 0.38x / MG-degree 0.73x), surfaced with the pyclass(extends=PyDict)
recipe (f91977f1e) + current ratios (95c55f43c). Awaiting operator unblock (restore agent-mail + core-file
reassign, or BlackThrush implements).

## 2026-06-25 CopperCliff checkpoint: all 9 session wins verified intact on HEAD (959 passed, no peer regression)

Conformance re-run on current HEAD (74022d9dd, after BlackThrush's concurrent core commits) across every
function I shipped this session: prufer / distance_regular / tree_broadcast / subgraph_centrality /
hopcroft+maximum_matching / cograph / paley / at_free / perfect / compose_all+union_all+disjoint_union_all
-> 959 passed, 0 failed. All 9 vs-nx wins (+ the *_all cluster + paley loss-reduction + is_at_free/
is_perfect_graph correctness fixes) remain byte-exact and conformance-green under the peer's in-flight
lib.rs/digraph.rs changes. No regression. Periphery remains exhausted (~45 categories at-or-above nx);
sole vs-nx progress = the coordination-blocked sticky-edges_dirty core lever (surfaced f91977f1e/95c55f43c).

## 2026-06-26 CopperCliff WIN: find_asteroidal_triple O(n^4)->O(n^3) component-structure — 158-308x vs nx

Sibling of the is_at_free win: find_asteroidal_triple was STILL O(n^4) (bfs_path_avoiding per (i,j,k)
triple) = 564ms / 0.075x on an AT-free path(80) (fast only on AT-exists via early-exit). Rewrote to the
same component-structure algorithm (cs[v][u] = component label of u in G-N[v], one BFS-labelling per node,
O(n^2+nm)), returning the first pairwise-non-adjacent triple satisfying the AT condition (O(n^3) early-exit).
Removed the now-dead bfs_path_avoiding. KEY: asteroidal triples are NOT unique (nx docstring) and the
parity tests assert existence + 3 distinct nodes + is_at_free-consistency, NOT nx's specific triple -- so
any valid AT in index order is correct (verified 0/12 graph types: path/cycle/complete/star/BA/tree/grid/
petersen/gnp/ladder + is_at_free consistency; conformance -k "asteroidal or at_free" 25 passed). Result:
0.075x -> 280.6x (path80) / 308.5x (path150) / 158x (cycle60) FASTER than nx. fnx-algorithms (TealSpring,
takeable). BUILD NOTE: first rch build failed on a bad worker (rustversion/arc-swap/blake3 incompatible-
rustc dep errors, NOT my code); retry on a consistent worker compiled clean.

## 2026-06-26 CopperCliff re-examined order-locked rejects vs their TEST CONTRACTS (after find_asteroidal win)

The find_asteroidal_triple win came from reading its conformance test (accepts ANY valid AT, not nx's
exact triple). Applied the same lens to the other order-locked rejects by reading their actual asserts:
- greedy_color (non-default strategies, connected_sequential 0.34x): test_coloring_conformance.py:158
  `assert fr == nr` + iteration-order for ALL deterministic strategies -> EXACT-LOCKED. Reject CONFIRMED
  (the faithful conversion is required for exact parity; can't speed up without matching nx's
  connected_components+bfs_edges set order).
- connected_dominating_set 0.32x: test_dominating_module_parity.py:71 `assert ... == nx.connected_
  dominating_set(...)` -> EXACT-LOCKED (heap/set-tie-break). Reject CONFIRMED.
- greedy_tsp 0.06-0.15x: TSP tests are lenient (valid cycle), BUT greedy_tsp is CONVERSION-FLOOR-bound
  (the O(n^2) weighted fnx->nx faithful conversion, not an algorithmic O(n^k) like the AT kernels), so
  even a de-delegated fast NN reaches only ~0.5x (loss-reduction, not a win). Not worth.
LESSON CONFIRMED + BOUNDED: re-reading test contracts unlocked find_asteroidal_triple (lenient + the gap
was algorithmic O(n^4)->O(n^3)); but lenient tests only help when the gap is ALGORITHMIC (not conversion/
construction-floor) AND the test doesn't assert exact-equality. greedy_color/connected_dominating_set are
genuinely exact-locked; greedy_tsp is floor-bound. No further wins in the order-locked-reject set.

## 2026-06-26 CopperCliff find_induced_nodes 0.478x->parity (2x self, byte-exact via convert+delegate)

find_induced_nodes was 0.478x (117ms vs 54ms, path(60); grows with n). It already ran nx's EXACT chordality-
breaker algorithm but on the fnx graph H (H.copy() + per-triplet H.add_edge + _find_chordality_breaker, all
per-edge PyO3) = 2x nx's dict primitives. Replaced the loop with the identical algorithm on a one-shot
structural nx copy -> byte-identical induced set (verified path60/path120 == nx; conformance -k
"find_induced or chordal" 871 passed). 0.478x -> 1.01x/1.03x (~2x self). NOT a vs-nx win (parity) but a
strict 2x self-improvement with no native-ness loss (the function was already a Python port of nx's algo,
never a native kernel). To BEAT nx: a native-Rust chordality-breaker kernel (exact-set-locked + niche, not
worth now). Shipped as a parity-reaching loss-reduction. is_chordal pre-check + error contract preserved.

## 2026-06-26 CopperCliff flow sweep — capacity_scaling/max_flow_min_cost WINS; min_cost_flow family REJECT (convert+delegate bound)

Flow sweep: WINS — capacity_scaling 7.29x, max_flow_min_cost 2.25x. NEAR-PARITY/REJECT — network_simplex
0.60->0.51x (n120->n400, delegates to min_cost_flow+cost_of_flow), min_cost_flow 0.76-0.81x, min_cost_flow
_cost 0.81x. Tried convert+delegate (the find_induced_nodes lever): for min_cost_flow it REGRESSES
(n400/e3000: cur 4.60ms -> convdeleg 6.18ms vs nx 3.51ms = 0.57x WORSE). WHY: building an nx DiGraph with
per-node demand + per-edge capacity/weight attrs costs MORE than the fnx-primitive overhead it saves,
because min_cost_flow is SINGLE-PASS (the algorithm runs once on the graph). find_induced won because its
fnx-primitive overhead was in a REPEATED loop (copy + add_edge + chordality_breaker x n), so one-time
conversion paid off. LEVER BOUND: convert+delegate only helps when the fnx-primitive tax is REPEATED
(loop), NOT for single-pass algorithms (conversion cost > saved overhead). min_cost_flow family is genuine
~0.76x near-parity; beating nx needs a native Rust network-simplex kernel (complex + order-sensitive
flowDict) -> not worth. REJECT.

## 2026-06-26 CopperCliff repeated-primitive-loop candidate sweep — ALL WINS (pattern mined)

Grepped __init__.py for the find_induced pattern (copy/subgraph/add_edge inside a loop) and benched the
candidates: ALL already optimized/wins — kl_connected_subgraph 14.4x, triadic_census 13.2x, core_number
8.4x, is_kl_connected 6.6x, all_triads 3.1x, adjacency_graph 2.1x, stochastic_graph 1.5x. No gap. The
repeated-primitive-loop vein is mined (find_induced_nodes was the last one; complete_to_chordal_graph was
fixed earlier per memory). ~50 function categories now measured at-or-above nx; periphery remains
comprehensively exhausted. Sole high-value residual = sticky-edges_dirty core lever (surfaced). Remaining
sub-1.0x are all documented: min_cost_flow family ~0.76x (single-pass near-parity, native-kernel-needed),
greedy_color non-default / connected_dominating_set (exact-locked), blossom matching (order-sensitive),
greedy_tsp (conversion-floor).

## 2026-06-26 CopperCliff WIN: node_classification native to_scipy — 0.37-0.55x -> 1.0-1.84x vs nx

fnx.algorithms.node_classification.{local_and_global_consistency, harmonic_function} were DELEGATED to nx
(0.37x/0.55x). nx's algorithm builds the adjacency via nx.to_scipy_sparse_array(G) + scans G.nodes(data=
True) for labels, then a deterministic 30-iter sparse matmul. On an fnx graph, nx's to_scipy iterates the
fnx graph edge-by-edge through PyO3 = the dominant cost. Created a real fnx submodule (algorithms/node_
classification.py) reusing fnx's NATIVE to_scipy_sparse_array (Rust matrix build) + nx's identical iterate
-> BYTE-IDENTICAL (order-invariant linear solve; parity verified n=150/500/1500) and FASTER:
local_and_global_consistency 1.28x (n150)/1.84x (n500)/1.71x (n1500); harmonic_function 1.00x/1.33x/1.27x.
Gap GROWS with n (matrix build is a larger share at scale + fnx native to_scipy is 2.84x). Wired via the
same sys.modules override pattern as bipartite/approximation in algorithms/__init__.py (KEY: the alias loop
pre-registers nx's leaf module under our dotted name, so pop it before import_module or you get the cached
nx module — that bug made the first install silently still-delegate at 0.19-0.58x). conformance: node_class
109 + algorithms/misc/wide_parity 1182 passed; bipartite/approximation/flow overrides intact. MY files
only (new submodule + algorithms/__init__.py, NOT top-level __init__.py). LEVER: delegated value-returning
fns that build a MATRIX from G (to_scipy/to_numpy) can WIN by reusing fnx's native matrix builder + nx's
math — order-invariant, no round-trip, and fnx's Rust matrix build beats nx's even on nx's own graph.

## 2026-06-26 CopperCliff WIN: laplacian_centrality O(n^3)->O(n^2) vectorization — 0.659x -> 13-90x vs nx

laplacian_centrality was already native (native laplacian_matrix + numpy energy loop) but 0.659x because
nx's per-node loop materialises an (n-1)x(n-1) submatrix EVERY iteration = O(n^3) (102ms at n=400; nx runs
the identical O(n^3) loop). Derived the closed form for the energy drop when node i is removed (delete
row+col i, subtract |L[:,i]| from the surviving diagonal): column terms cancel ->
  lapl_cent[i] = rowsq[i] - 2*diag[i]^2 + 2*(diag @ |L|)[i]
(rowsq = sum over columns of L^2). Vectorised over all nodes in O(n^2). BYTE-EXACT on unweighted (integer
L; dict ==) and 1e-16 on weighted/directed (verified path/complete/gnp/weighted/directed-Chung-Laplacian).
0.659x -> 13.0x (n=120) / 90.4x (n=400), speedup GROWS as O(n). conformance -k laplacian_centrality 164
passed. Python-only (__init__.py, warn-override). LEVER: a delegated/native VALUE fn with a per-node
"delete-row/col + re-sum a matrix functional" loop (O(n^3)) often has an O(n^2) closed form (rank-1 / row-col
removal algebra) — derive it; byte-exact on integer matrices. Audit other per-node matrix-recompute loops.

## 2026-06-26 CopperCliff removal/matrix-centrality sweep — WINS; communicability_betweenness O(n^4)-hard REJECT

Audited the per-node-matrix-recompute + matrix-functional centrality vein (after laplacian_centrality
13-90x). WINS: subgraph_centrality 20.6x, dispersion 14.5x, effective_size 7.1x, constraint 6.7x,
global_reaching 2.7x, effective_graph_resistance 2.05x, percolation_centrality 1.86x, kemeny_constant
1.18x. NEAR-PARITY/REJECT: communicability_betweenness_centrality 0.894x — BUT it is a ~1.5s function
(n=120) that is fundamentally O(n^4): it computes expm(A) then, for EACH node, expm(A with that node's
row/col zeroed). Unlike a matrix INVERSE (Woodbury rank-k update O(n^2)), the matrix EXPONENTIAL has NO
low-rank update under row/col zeroing, so n+1 expm calls = O(n^4) is inherent to the Estrada-Higham-Hatano
algorithm. fnx already runs the optimal path (native to_numpy_array + scipy.linalg.expm; its own Pade
kernel was 2.5x SLOWER per the in-tree comment). The principal-submatrix reformulation only saves a
(1-1/n)^3 constant. No sub-O(n^4) exact algorithm known -> genuine near-parity, REJECT. Laplacian-centrality
won because energy=sum(L^2) HAS a rank-1 closed form; communicability has none. LEVER BOUND: per-node
matrix-recompute loops yield O(n^2) closed forms ONLY for polynomial functionals (energy/trace of L^k), NOT
transcendental ones (expm/matrix functions).

## 2026-06-26 CopperCliff spectral sweep — fiedler_vector win CONFIRMED at scale; spectral_ordering sign-locked REJECT

Spectral family at scale (BA n=2000/4000): fiedler_vector 45.2x/9.4x WIN, algebraic_connectivity 41.8x/9.2x
WIN (both shipped sparse shift-invert, durable — verified holds; at n=800 they're ~0.83-0.88x only because
nx is fast at small n). eigenvector_centrality_numpy 1.21x, hits 1.16x, google_matrix 1.16x WINS.
GAP: spectral_ordering DELEGATES to nx (1.31x n=2000 / 0.96x n=4000 = 33x SLOWER than fiedler_vector's
fast native path: 3754ms vs 113ms at n=2000). Investigated routing it through fnx's fast Fiedler + argsort.
BLOCKED (confirms br-r37-c1-xiqgr / 193zq with the test contract): test_spectral_ordering_parity asserts
`fnx.spectral_ordering(g, seed=s) == nx.spectral_ordering(gx, seed=s)` — nx's EXACT seeded order. fnx's
fiedler_vector is only CANONICAL-sign-exact (test_nondegenerate_matches_nx_up_to_sign compares _canon(.)
up to sign) because fnx's native eigensolver doesn't bit-reproduce scipy's lobpcg/tracemin sign. Verified:
argsort(fnx.fiedler)==nx.spectral_ordering on path (sign matches) but NOT on BA300 (sign flips -> order
reverses). Matching nx's seeded sign needs reproducing scipy's exact eigensolver convergence sign (fragile,
already reverted). REJECT. The 45x fast Fiedler is unusable for the EXACT-order contract. (If the test ever
relaxes to up-to-reversal, this becomes a 33x win.)

## 2026-06-26 CopperCliff WIN: percolation_centrality unweighted -> native parallel kernel — 1.86x -> 66-157x vs nx

Unweighted percolation_centrality (the DEFAULT weight=None) ran a SERIAL Python Brandes loop over all N
sources (integer-CSR but Python-level): 2.18s at n=1500, only 1.86x vs nx. The WEIGHTED case already routes
to the native parallel Dijkstra-SSSP kernel (_raw_percolation_centrality_weighted). That kernel defaults a
MISSING edge-weight attribute to 1.0 = unit weights, whose shortest-path counts are identical to BFS — so
routing the unweighted case through it with a sentinel (absent) weight name is BYTE-IDENTICAL (verified
undirected/directed/disconnected/non-uniform-states: 0..7e-18 vs nx; conformance -k percolation 34 passed)
and parallel-native. 1.86x -> 66.5x (n=400) / 156.7x (n=1500); ~95x self (2.18s -> 22.9ms). Multigraph keeps
the Python loop (kernel guards !multigraph, like the weighted path). Python-only (__init__.py, warn-override).
LEVER: a Python wrapper with a SERIAL per-source Brandes loop for the unweighted case, while the WEIGHTED
case already has a native parallel kernel — route unweighted through the weighted kernel with unit weights
(missing-attr defaults to 1.0; Dijkstra-unit == BFS, byte-exact). Audit other dual weighted/unweighted
centralities where only the weighted path is native.

## 2026-06-26 CopperCliff serial-Brandes / dual-path audit — betweenness family WINS; group_betweenness(>=3) surfaced

After the percolation dual-path win (157x), audited serial per-source Brandes loops + dual weighted/unweighted
centralities at scale (n=800). WINS: betweenness_centrality 109x, betweenness_centrality(endpoints=True)
190x, edge_betweenness_centrality 96x, load_centrality 160x, betweenness_centrality_subset 6.3x,
edge_betweenness_centrality_subset 4.2x, group_closeness_centrality 7.7x, edge_load_centrality 1.33x. The
serial-Python betweenness variants still beat nx (nx is also serial; fnx's integer-CSR BFS is faster, and
subset iterates few sources). NEAR-PARITY/SURFACED: group_betweenness_centrality 0.961x (2.28s) — it has a
native fast path only for groups of 1-2 nodes; groups of >=3 DELEGATE to nx (the native inclusion-exclusion
path was buggy for >=3, br-r37-c1-q49py). De-delegation won't help (the 2.19s is nx's O(VE) preprocessing,
not the conversion — single-pass, like min_cost_flow). Beating it needs a CORRECT native parallel
group-Brandes kernel (Puzis inclusion-exclusion) — substantial + error-prone (prior attempt wrong) ->
SURFACED as a native-kernel candidate, not a cheap win. all_pairs_shortest_path(materialize) 0.726x =
PyObject path-dict materialization floor (view substrate, not cheaply winnable). No cheap win this batch.

## 2026-06-26 CopperCliff wide scale sweep (clustering/similarity/link-pred/core/structural-holes) — ALL WINS

Scale sweep n=1200: clustering 72x, k_core 41.2x, square_clustering 17.9x, average_neighbor_degree 10.2x,
local_constraint 10.9x, eccentricity 9.7x, constraint 6.3x, triangles 3.4x, generalized_degree 3.1x,
jaccard_coefficient(all-pairs) 2.24x, adamic_adar_index 1.99x. ALL WINS at scale — no gap. The clustering /
similarity / link-prediction / k-core / structural-holes / distance domains are comprehensively faster than
nx at scale. Combined with the prior betweenness-family all-wins and centrality/community all-wins sweeps,
the algorithm periphery is wins-at-scale except the documented residuals: group_betweenness(>=3) [Puzis
native kernel candidate], spectral_ordering [sign-locked], communicability_betweenness [O(n^4) transcendental],
min_cost_flow family [single-pass near-parity], all_pairs_shortest_path [PyObject materialization floor],
sticky-edges_dirty [architectural core, operator-gated]. 13 vs-nx wins shipped this session.

## 2026-06-26 CopperCliff flow/connectivity sweep — wins; k_components/minimum_node_cut(global) correctness-delegated

Flow/connectivity at n=150: WINS — node_connectivity 31.2x, k_edge_components 9.1x, all_pairs_node_
connectivity 1.76x, average_node_connectivity 1.60x, edge_connectivity 1.42x. NEAR-PARITY (correctness-
delegated to nx): k_components 1.013x (3.02s — delegates for Moody-White correctness outside narrow exact
cases, br-kcompalgo), minimum_node_cut(global) 0.984x (delegates for the global no-s,t contract),
minimum_edge_cut 1.005x. These delegate for CORRECTNESS (subtle algorithms) — beating them needs substantial
correct native kernels (same class as group_betweenness>=3 Puzis), not cheap wins. De-delegation won't help
(the cost is nx's algorithm, not conversion — single-pass). SURFACED as substantial-native-kernel candidates.
FRONTIER STATUS: the cheap-win veins (bespoke O(n^k) kernels, per-node polynomial loops, delegated-matrix
reuse, serial->native-parallel routing) yielded 13 wins this session and are now largely tapped; fresh
sweeps return wins + a few correctness-delegated near-parity residuals that need full native kernels.

## 2026-06-26 CopperCliff trophic sweep + CONSOLIDATED BLOCKER (Python-only veins tapped)

trophic_levels: n=300 0.707x but n=800 1.055x (ratio IMPROVES with scale -> small-n noise, NOT a systematic
gap), trophic_incoherence_parameter 1.06x, trophic_differences 0.861x. Already at/above nx at scale (native
wrappers using fnx's matrix builders). No gap.

CONSOLIDATED FRONTIER (after ~15 turns, 13 vs-nx wins shipped): the PYTHON-ONLY win veins are now TAPPED —
(1) bespoke O(n^k) kernels in fnx-algorithms [TealSpring, takeable] (is_at_free 305x, find_asteroidal 308x),
(2) per-node polynomial closed forms (laplacian_centrality 90x), (3) delegated-matrix reuse of fnx's native
to_scipy/to_numpy (node_classification 1.84x), (4) serial->existing-native-parallel-kernel routing
(percolation 157x). Fresh wide sweeps (clustering/similarity/link-pred/core/flow/trophic/spectral/centrality
/community) now return WINS + correctness-delegated near-parity residuals.

The remaining vs-nx wins ALL require a NEW native kernel + a binding in fnx-python/src/algorithms.rs OR
lib.rs (BlackThrush's RESERVED, actively-committed core), and agent-mail is DOWN (no coordination/reservation):
  - group_betweenness_centrality(>=3): correct parallel Puzis inclusion-exclusion kernel (prior native buggy)
  - k_components: correct native Moody-White
  - minimum_node_cut (global): native global node-cut
  - sticky-edges_dirty MASTER lever (dijkstra 0.165x / to_scipy(weight) 0.38x / MG-degree 0.73x): pyclass(
    extends=PyDict) marking dict in lib.rs (f91977f1e)
OPERATOR ACTION needed: restore agent-mail (am doctor repair) + reassign/clear fnx-python core for CopperCliff,
or have BlackThrush implement from this ledger. No further cheap Python-only vs-nx win remains to mine.

## 2026-06-26 CopperCliff isomorphism/branching/chains/paths sweep — ALL WINS (periphery coverage extended)

Final fresh-domain sweep: is_isomorphic 77.6x, bridges 27.0x, harmonic_diameter 10.1x, chain_decomposition
7.8x, minimum_spanning_arborescence 4.4x (1.9s abs, Edmonds), fast_could_be_isomorphic 1.70x, all_simple
_paths(cutoff) 1.27x, could_be_isomorphic 1.22x, voronoi_cells 1.45x. dag_to_branching 1.003x (parity).
ALL WINS — no gap. Extends the verified-won map to isomorphism/branching/chains/bridges/paths/voronoi.
Confirms (again) the Python-only periphery is comprehensively won; remaining vs-nx wins are the reserved-core
native-kernel candidates consolidated in 52bc19c6e (group_betweenness>=3, k_components, minimum_node_cut,
sticky-edges_dirty), all gated on BlackThrush's reserved fnx-python core + agent-mail down.

## 2026-06-26 CopperCliff group_betweenness(>=3) ROOT-CAUSED — kernel matches TEXTBOOK def, nx uses improved Puzis (diverges)

Investigated whether the existing native group_betweenness_centrality_rust kernel (fnx-algorithms, TealSpring/
takeable; binding EXISTS, no BlackThrush file needed) could be fixed to handle |C|>=3 (wrapper delegates there,
2.28s/0.961x). PRECISE root cause (upgrades br-r37-c1-q49py): the kernel computes sigma - sigma_no_c = the
TEXTBOOK Everett-Borgatti definition (fraction of shortest paths through >=1 group member) and is BYTE-EXACT
to that definition (brute-force over all_shortest_paths confirms kernel==definition for ALL |C|). BUT nx's
group_betweenness uses the IMPROVED Puzis algorithm (_group_preprocessing builds a path-betweenness matrix PB
via _accumulate_endpoints + delta[s][i]+=1, then applies triple inclusion-exclusion corrections
dxvy/dxyv/dvxy over every (v,x,y) in the group). nx's VALUE DIVERGES from its own docstring textbook
definition for |C|>=3: verified kernel==nx for |C|<=2 always; |C|==3 diverges 15/231 graphs (worst 1.25e-2);
|C|==4 diverges 19/60. So the kernel is "correct" to the definition but conformance needs nx's improved-algo
value. CANNOT relax the >=3 delegation (the kernel is wrong-vs-nx for some |C|==3 too). To win: port nx's
exact PB-matrix Puzis algorithm to Rust (O(VE + |C|^2 V), parallelizable) bug-for-bug — SUBSTANTIAL +
correctness-critical (must replicate nx's non-textbook value exactly). No code changed this turn. SURFACED
with the exact algorithm to port. Current kernel + >=3 delegation is CORRECT; leave it.

## 2026-06-26 CopperCliff group_betweenness Puzis port — WIP/NO-SHIP-yet (Rust bug, Python ref VERIFIED)

Attempted the native Puzis port (group_betweenness >=3) — REVERTED (stash@{0}), not shipped (buggy). Progress:
- VERIFIED-CORRECT Python verbatim port of nx's improved algorithm matches nx EXACTLY (0.3728117914 vs nx
  0.3728117914 on BA(20,2,seed=11), group [3,7,11,15,2]). So nx's algorithm is fully understood: per-source
  Brandes BFS -> sigma[s][*],D[s][*]; _accumulate_endpoints -> delta[s][*]; delta[s][i]+=1 for reachable
  i!=s; PB[g1][g2]=sum_node delta[node][g2]*sigma[node][g1]*sigma[g1][g2]/sigma[node][g2] over node with
  D[node][g2]==D[node][g1]+D[g1][g2]; then per-v group correction (dxvy/dxyv/dvxy triples, buffer-swap of
  sigma_m/PB_m); subtract endpoint scale (sum over g1, reachable node!=g1: +1 if in group else +2); /((n-c)(n-c-1)).
- My RUST translation of the same compiled + ran but is BUGGY: overcounts |C|>=3 by ~5e-3 (BA(20) |C|=5:
  rust 0.3778735 vs correct 0.3728118), 22/120 BA + 37/120 gnp/ws fail at 1e-7. CRUCIALLY: |C|<=2 EXACT
  (0 mism), and ORDER-INDEPENDENT (same value across 8 group permutations) -> NOT set-order-locked, NOT a
  misunderstanding (Python ref is correct). It's a pure Rust translation bug in the PB-matrix or correction
  loop (likely an index/buffer subtlety that only manifests with >=3 group nodes).
TEST TOLERANCE: pytest.approx(abs=1e-7). WIN IS REAL + RESERVED-FILE-FREE: kernel lives in fnx-algorithms
(TealSpring/takeable), binding group_betweenness_centrality_rust EXISTS, wrapper just needs the >=3
delegation relaxed to undirected/unweighted/no-endpoints once the kernel is correct. NEXT: diff the Rust
PB matrix + per-v sigma_m against the verified Python port (add eprintln, one rebuild) to locate the bug.
Buggy attempt in stash@{0}.

## 2026-06-26 CopperCliff group_betweenness(>=3) DEFINITIVE REJECT — nx's Puzis algorithm is SET-ORDER-DEPENDENT

Resolved the group_betweenness>=3 question PERMANENTLY (supersedes the q49py/ejuhf "buggy inclusion-exclusion"
framing): nx's improved Puzis algorithm is ORDER-DEPENDENT on the group's iteration order. Verified on
BA(20,2,seed=11) group {3,7,11,15,2}, computing gbc_before_scale with the group iterated in different orders:
  [3,7,11,15,2] -> 249.3534   [2,3,7,11,15] (set order) -> 248.2905   [15,11,7,3,2] -> 247.9571
The per-v inclusion-exclusion corrections (sigma_m/PB_m buffer-swap) DO NOT commute, so the result depends
on order. nx does `group = set(C)` and iterates in CPython SET-HASH order -> nx's value is tied to that
order. The spread (~1.4 pre-scale = ~0.006 after /((n-c)(n-c-1))) FAR exceeds the test tolerance
(pytest.approx abs=1e-7). Therefore a Rust kernel CANNOT match nx's value without reproducing CPython's set
iteration order of arbitrary group-node values — the SAME set-order wall as greedy_color / ramsey /
clique-family (see reference_parity_blocked_by_set_order). SET-ORDER-LOCKED -> the >=3 delegation is
MANDATORY and correct; the native port is STRUCTURALLY UNWINNABLE for exact nx parity. The textbook
sigma-sigma_no_c kernel (order-invariant) is correct-to-definition but != nx's order-dependent value, which
is why |C|<=2 (corrections trivial/commute) match but >=3 don't. STOP attempting this port. (My Python
verbatim port matched nx only because Python's set() reproduced nx's set order; a Rust port can't for general
nodes.) Reverted attempt held in a stash (not dropped, per directive).

## 2026-06-26 CopperCliff non_randomness/assortativity/reciprocity/polynomials sweep — wins; non_randomness dense-eig near-parity

WINS: s_metric 79x, degree_assortativity_coefficient 65x, reciprocity 3.75x, overall_reciprocity 2.0x.
NEAR-PARITY: non_randomness 0.891x (n=150, 7.5ms) — computes eigenvalues of the MODULARITY matrix
(B = A - d d^T / 2m), which is DENSE even when A is sparse, so dense eig is inherent; both fnx and nx are
eig-bound -> not cheaply winnable (no sparse shortcut like algebraic_connectivity had). numeric_assortativity
0.702x / attribute_mixing_matrix 0.865x are sub-ms (noise floor). tutte_polynomial / chromatic_polynomial:
sympy not installed locally -> cannot bench (and they are #P-hard, exponential for both fnx+nx). No cheap win
this batch. Frontier remains: cheap + reserved-file-free veins mined out; residual sub-1.0x are dense-eig
(non_randomness), single-pass (min_cost_flow), O(n^4) (communicability_betweenness), set-order-locked
(spectral_ordering, group_betweenness>=3, greedy_color, connected_dominating_set), materialization-floor
(all_pairs view), or the operator-gated sticky-edges_dirty core. 13 vs-nx wins shipped this session.

## 2026-06-26 CopperCliff smallworld/bipartite/euler sweep — wins; sigma/omega surfaced (random_reference native-kernel candidate)

WINS: bipartite.robins_alexander_clustering 459x, bipartite.spectral_bipartivity 284x, bipartite.node_
redundancy 19x, bipartite.clustering 2.16x, eulerian_circuit 3.47x, is_eulerian 2.61x, has_eulerian_path
1.95x. NEAR-PARITY (big absolute): sigma 1.027x (1.1s), omega 1.015x (2.5s). Profiled: the bottleneck is
random_reference (399ms for niter=5; transitivity/ASPL are ~0ms). random_reference DELEGATES to nx (seed-
locked: test_random_reference_seed_parity requires byte-for-byte; the fnx native double_edge_swap picks a
DIFFERENT sequence than nx's degree-weighted discrete_sequence algorithm). NEW SURFACED CANDIDATE: a native
random_reference reproducing nx's EXACT seeded swap RNG (degree-weighted discrete_sequence + neighbor picks)
would make sigma/omega multi-x. KEY DISTINCTION from group_betweenness: random_reference is RNG-REPRODUCIBLE
(deterministic given seed, like the shipped gnp_directed PythonRandom replication c17d7a484), NOT order-locked
-> FEASIBLE, not impossible. BUT needs a binding in fnx-python/src/algorithms.rs (BlackThrush reserved, mail
down) + substantial RNG-match work. Surfaced as the highest-EV FEASIBLE native candidate (reserved-gated).
double_edge_swap_rust binding exists but picks a different sequence (won't match nx's random_reference).

## 2026-06-26 CopperCliff steiner_tree — fast-Kou REJECT (weight-locked to nx mehlhorn default); LCA/dominating wins

LCA/dominating/matching sweep WINS: lowest_common_ancestor 16.7x, maximal_matching 6.5x, harmonic_centrality
(subset) 3.24x, descendants_at_distance 2.4x, min_weighted_dominating_set 1.45x, all_pairs_lca 1.16x.
steiner_tree 0.485x (5ms n=400/k=4, nx runs ON the fnx graph + _from_nx_graph roundtrip): prototyped a fast
reimpl (fnx single_source_dijkstra per terminal -> metric closure -> small MST -> expand) = 1.32-1.81x vs nx
AND a valid tree. BUT REJECT: the binding test test_flow_cut_matching_value_parity::test_steiner_tree_weight
asserts tw(fnx)==tw(nx) EXACTLY, and nx's DEFAULT method is "mehlhorn" (weight 16 on the probe), while my
fast Kou matches nx's "kou" method (weight 15) -> 15 != 16 FAILS. The validity test
(test_approximation_guarantee_invariants) is lenient, but the WEIGHT test locks fnx to nx's mehlhorn output.
To win: faithfully reimplement nx's MEHLHORN (multi_source_dijkstra Voronoi -> auxiliary MST -> expand) with
fnx fast primitives AND a tie-break-exact weight match — moderate effort + correctness risk for a 5-15ms
function. Surfaced as a possible future target; not a cheap win. No file changed (prototype only).

## 2026-06-26 CopperCliff steiner_tree UPGRADE — weight-match FEASIBLE; win needs native mehlhorn (reserved-gated)

Followed up the steiner_tree weight-lock. KEY NEW RESULT: reimplemented nx's exact MEHLHORN algorithm using
fnx's fast primitives (multi_source_dijkstra + shortest_path + nx MST on the small auxiliary) and the WEIGHT
MATCHES nx EXACTLY across 40 random graphs (0 mismatches) — so fnx's dijkstra/shortest_path tie-breaks ALIGN
with nx's for mehlhorn. So steiner_tree is NOT order-locked (unlike group_betweenness): a faithful native
mehlhorn IS weight-exact-feasible. BUT timing: the Python mehlhorn reimpl is 0.42-0.52x (SLOWER than nx) —
the bottleneck moved to the Python loop over G.edges(data=True) building G1 (fnx's edges-view materialization
tax over all E edges). convert+delegate (build nx.Graph H, run nx.steiner_tree(H), _from_nx_graph) is
byte-exact + 1.37x self but only 0.65x vs nx (conversion overhead) — a loss-reduction, NOT shipped (still a
loss; the current already delegates). CONCLUSION: steiner_tree win requires a FULL NATIVE mehlhorn kernel
(edge-loop + G1 + MST in Rust) -> reserved algorithms.rs binding (mail down), same tier as sigma/omega
random_reference. Weight-match feasibility now CONFIRMED (the hard part is solved). Surfaced as a feasible
native candidate. No file changed (prototype only).

## 2026-06-26 CopperCliff ROOT-CAUSE: multi_source_dijkstra 0.17-0.21x (stale weighted-gate + 1/40 kernel tie-break) — feasible win

Tracing steiner_tree's slowness led to the ROOT cause: multi_source_dijkstra is 0.205x (n=400) / 0.167x
(n=1500) vs nx — WHILE single_source_dijkstra is 2.9x/1.24x FASTER (its weighted gate was removed in
br-r37-c1-efv3d once the native kernel was confirmed weight-correct). multi_source STILL delegates weighted
input (__init__.py:31716, gate = _mst_has_weight_edge_attr / "inherits the weight-ignoring bug" comment,
NOW STALE). Verified the native _raw_multi_source_dijkstra: weighted DISTANCES match nx 0/30, weighted PATHS
match 39/40 — the 1 divergence is a SHORTEST-PATH TIE-BREAK (same distance, different equal-weight path:
fnx [72,13,0,36] vs nx [72,49,9,36]; both from src 72). The conformance test (test_traversal_tree_parity:550)
requires EXACT path match, so the gate can't be removed until the kernel matches nx's paths 100%. The kernel
is in fnx-algorithms (TealSpring/TAKEABLE) at lib.rs:1444 (multi_source_dijkstra); it uses strict-< relaxation
(line 1520) like nx, so the divergence is the multi-source FINALIZE ORDER (which equidistant predecessor is
finalized first when interleaving sources) — fnx's heap (dist,seq) pop order diverges from nx's (dist,c,node)
in rare interleavings. FEASIBLE WIN (not order-LOCKED — it's a deterministic tie-break to ALIGN, like
single_source already does): fix the multi_source kernel's finalize/push-seq to match nx exactly (compare to
the single_source kernel which matches), then remove the stale weighted-gate -> multi_source_dijkstra 0.17x
-> fast (single_source is 1.2-2.9x) AND fixes steiner_tree (its bottleneck is this, NOT the edge-loop).
Needs iterative build-debug (subtle, ~1/40). Kernel takeable; binding stays. No file changed (investigation).

## 2026-06-26 CopperCliff multi_source_dijkstra divergence REFINED — genuine kernel tie-break (~1/60), needs finalize-order trace

Refined the multi_source_dijkstra path divergence: persists 1/60 EVEN with identical adjacency order (gf built
from gn.edges() so neighbor-iteration order matches nx) -> NOT a generator-order artifact, a GENUINE rare
kernel tie-break. DijkstraState Ord is CORRECT (min-dist then min-seq pops first = nx's (dist,c)); seq-vs-c
offset is uniform; yet the multi-source finalize order of EQUIDISTANT nodes diverges in ~1/60 cases (traced:
node at dist 8 gets predecessor 0 in fnx vs 9 in nx, both preds at dist 7 — fnx finalizes 0-before-9, nx
9-before-0, a push-seq cascade from some earlier equidistant tie). Fix requires kernel-internal finalize-order
tracing (eprintln build, compare to nx's pop order, find the FIRST divergent finalize, align the push-seq) —
a dedicated multi-cycle build-debug. Kernel is TAKEABLE (fnx-algorithms:1444); binding stays; gate removal in
__init__.py (warn-override) once 0-divergence confirmed. STATUS: thoroughly characterized, feasible, but
deferred — a focused kernel-debug task, not a 60-min dig. (Spent several turns on the dijkstra/steiner chain;
moving on to fresh domains next.) Net new finding this turn: divergence is order-independent (genuine bug),
ruling out the easy generator-artifact hypothesis.

## 2026-06-26 CopperCliff multi_source_dijkstra gate-removal CONCLUSIVELY UNSAFE — genuine 8% kernel tie-break bug

DEFINITIVE (corrects the earlier "adjacency-artifact / maybe-safe-to-remove" hypothesis): tested
_raw_multi_source_dijkstra with TRULY IDENTICAL construction — gf and gn both built via
add_weighted_edges_from on the SAME shuffled edge list (so per-node adjacency order genuinely matches, unlike
the earlier gn.edges() test). Result: 6/78 path mismatches (~8%). So the divergence is a GENUINE kernel
multi-source finalize tie-break bug, NOT an adjacency-order artifact. Therefore removing the stale
_mst_has_weight_edge_attr gate (line 31728) would ship ~8% weighted-multi_source path-parity divergence vs nx
-> UNSAFE for a byte-exact project; the conformance test (test_traversal_tree_parity, exact path ==) would
likely catch it too. The gate STAYS. multi_source_dijkstra remains 0.17-0.21x (delegated weighted). The WIN
requires fixing the kernel's multi-source finalize/push-seq tie-break to match nx 100% (fnx-algorithms:1444,
TAKEABLE) — a dedicated build-debug (add finalize-order eprintln, compare pop order to nx on a small failing
case, align). single_source has no such bug (1 source = no interleave). Conclusively a kernel fix, not a
gate change. No file changed. Done deep-characterizing the dijkstra/steiner chain; dijkstra fix = a focused
kernel-debug task for a future session.

## 2026-06-26 CopperCliff multi_source_dijkstra fix ATTEMPT FAILED + deeper root found; build-infra note

ROOT CAUSE confirmed by kernel trace (CC_MSD_DEBUG eprintln build): the multi_source dijkstra kernel iterates
graph.neighbors_indices(8) = [0,3,4,1,7] but insertion order (nx + the Python view gf[8]) = [4,0,3,1,7] ->
wrong relaxation order -> wrong push-seq -> equidistant-node finalize tie-break diverges from nx (~8% weighted
multi-source paths). FIX ATTEMPT (br-r37-c1-msdorder): switched the kernel to graph.neighbors_iter(u_name) +
get_node_index, expecting insertion order like the single_source kernel uses. BUILT + verified: STILL DIVERGES
(small case node 2 still [8,0,2] vs nx [8,4,2]; 12/113 golden corpus). So neighbors_iter ALSO returns
non-insertion order (= same wrong order as neighbors_indices), NOT the insertion order the Python adjacency
VIEW (gf[node]) preserves. So BOTH native neighbor-iteration methods diverge from the view/nx order; only the
view preserves insertion. DEEPER ISSUE: the kernel needs the VIEW's insertion-order neighbor method (TBD,
likely a distinct storage accessor; possibly fnx-classes). CONCERN: single_source_dijkstra also uses
neighbors_iter -> may have a latent ~8% path tie-break divergence too (its gate was removed in efv3d; its path
tests may be less adversarial). REVERTED the futile fix (stash, zero-gain). NEXT: find the insertion-order
neighbor accessor the view uses; the multi_source win + steiner_tree remain gated on that.
BUILD-INFRA: 4 consecutive rch builds failed with E0514 "incompatible rustc" (pool cache deps compiled by
rustc 2026-06-09, workers now 2026-06-07). FIX: `rch exec -- bash -lc "cargo clean && cargo build ..."`
(full clean rebuilt all deps with the current worker rustc -> 3m28s success). Use a FULL cargo clean when
E0514 dep-mismatch errors appear (the pool cache went stale across a rustc bump).

## 2026-06-26 CopperCliff community-detection + generator sweep — ALL WINS (fresh domain, no gap)

Fresh domain (community detection + generators, n=600): random_regular_graph 5.26x, fast_label_propagation
2.35x, label_propagation_communities 2.27x, asyn_lpa_communities 1.69x, kernighan_lin_bisection 1.11x,
modularity 1.06x, partition_quality 1.05x, stochastic_block_model 1.02x, is_graphical 0.97x (~parity). ALL
WINS — no gap. Community-detection + generator domains comprehensively won. Confirms the pattern: every fresh
domain sweep returns wins; the periphery is mined out. Remaining vs-nx work is all gated: multi_source_
dijkstra (deep storage neighbor-ordering: view preserves insertion but neighbors_iter/neighbors_indices
don't — needs the view's accessor, possibly fnx-classes), sigma/omega random_reference + steiner mehlhorn +
sticky-edges_dirty (reserved fnx-python binding, mail down), group_betweenness>=3 + spectral_ordering
(proven set-order-locked), non_randomness/min_cost_flow/communicability/all_pairs (inherent/floored). 13
vs-nx wins shipped this session.

## 2026-06-26 CopperCliff multi_source_dijkstra — neighbor-order hypothesis RULED OUT; bug is interleaving-specific

CORRECTION (closes the neighbor-order theory): my neighbors_iter fix WAS built + installed (verified same .so
mtime/size at both the pool and CARGO_TARGET_DIR paths — they're synced) and STILL diverged ([8,0,2] vs nx
[8,4,2]). DECISIVE: single_source_dijkstra (which uses the SAME neighbors_iter) matches nx 0/116 on identical
construction. So neighbors_iter IS insertion-order-correct, and the multi_source divergence is NOT neighbor
order — it is MULTI-SOURCE-INTERLEAVING-specific (the equidistant-node finalize tie-break across multiple
initial sources). My neighbor-order fix was misguided -> RE-REVERTED (zero-gain, stash). The bug needs a full
pop-sequence trace (eprintln every heap pop in both fnx and a verbatim-nx python multisource, diff the first
divergent pop) to locate the source-seq/interleave mismatch — a dedicated debug I will NOT pursue further now
(6+ turns invested; 13 wins shipped; reserved-gated + impossible alternatives remain). DECISION: multi_source
_dijkstra stays gated (0.17x weighted); it is a genuine but deep interleaving tie-break bug, parked as a
characterized dedicated-debug target. Moving off the dijkstra/steiner chain for good.

## 2026-06-26 CopperCliff minors/contraction/line-graph/bulk-attr/conversion sweep — ALL WINS

Fresh domain (n=300): contracted_nodes 7.4x, contracted_edge 5.6x, get_node_attributes 5.8x, line_graph
4.91x, set_node_attributes(bulk) 4.33x, quotient_graph 3.29x, power 2.4x, to_dict_of_lists 2.17x, is_frozen
2.05x, from_dict_of_lists 1.05x. ALL WINS — no gap. Minors/contraction/line-graph/bulk-attribute/conversion
domains comprehensively won. Confirms (~25 domains swept this session): every fresh-domain sweep returns
wins; accessible periphery mined out. 13 vs-nx wins shipped. Remaining vs-nx work is coordination/depth-gated
(reserved fnx-python: sigma/omega+steiner+sticky; deep-storage-parked: multi_source interleaving tie-break;
proven-impossible: group_betweenness>=3+spectral_ordering; inherent: non_randomness/min_cost_flow/communicability
/all_pairs), NOT discovery-gated.

## 2026-06-26 CopperCliff checkpoint: all session wins intact on HEAD (1302 passed, no peer regression)

Conformance re-run on current HEAD (5d2d0c283, after peers' concurrent commits) across every function shipped
this session: prufer / distance_regular / tree_broadcast / subgraph_centrality / hopcroft+maximum_matching /
cograph / paley / at_free / perfect / compose_all+union_all+disjoint_union_all / find_induced / node_
classification / laplacian_centrality / percolation / asteroidal -> 1302 passed, 0 failed, 3 conditional-skip.
All 13 vs-nx wins + 2 parity-fixes remain byte-exact + conformance-green under peer churn. No regression.
Periphery comprehensively won (~25 domains swept, all wins); remaining vs-nx work is coordination/depth-gated
(reserved fnx-python core; parked multi_source interleaving; proven-impossible; inherent), not discovery-gated.

## 2026-06-26 CopperCliff multi_source_dijkstra ROOT CAUSE RESOLVED — weighted-projection reorders neighbors (RESERVED-gated)

DEFINITIVE resolution of the multi_source_dijkstra 0.17x / ~8% path-divergence chain: the binding
(algorithms.rs:3848) runs the kernel on a WEIGHTED PROJECTION — dijkstra_weighted_undirected_projection ->
dijkstra_single_weight_graph_projection(py, pg, weight) (algorithms.rs:441/448), NOT the original graph. My
earlier CC_MSD_DEBUG eprintln (which traced neighbors INSIDE the kernel, i.e. on the projection) showed node
8's neighbors = [0,3,4,1,7], whereas the original graph's insertion order (= nx + the Python view gf[8]) is
[4,0,3,1,7]. So the WEIGHTED PROJECTION BUILDER REORDERS NEIGHBORS (non-insertion order) -> the kernel relaxes
in the wrong order -> the equidistant-node finalize tie-break diverges from nx in multi-source (single_source
matches because it does not hit this reordered projection the same way). This explains why my fnx-algorithms
kernel neighbor-iterator change (neighbors_iter) DIDN'T help: the kernel was already fed wrong-order neighbors
by the projection. FIX LOCATION: dijkstra_single_weight_graph_projection in fnx-python/src/algorithms.rs
(BlackThrush RESERVED, agent-mail down) must build the projection's adjacency in INSERTION order. So
multi_source_dijkstra is RESERVED-GATED (re-classified from "takeable-fnx-algorithms" — the kernel is takeable
but the bug is in the reserved projection builder). steiner_tree (uses multi_source) is gated on the same.
CHAIN CLOSED: root cause precise, fix is a reserved-file 1-spot change (make the weighted projection preserve
insertion-order adjacency). 13 vs-nx wins shipped this session.

## 2026-06-26 CopperCliff weighted-dijkstra family sweep — ALL WINS except multi_source (projection bug is NARROW)

Benched the full weighted-dijkstra family (n=800) to check whether the weighted-projection neighbor-reorder
bug affects more than multi_source: dijkstra_path 7.89x, astar_path 6.26x, single_source_dijkstra 5.41x,
single_source_dijkstra_path_length 3.42x, all_pairs_dijkstra_path_length 3.14x, bidirectional_dijkstra 2.09x,
shortest_path(weight) 1.89x, dijkstra_predecessor_and_distance 1.53x — ALL WINS. ONLY multi_source_dijkstra
0.157x (gated, the projection-reorder). So the projection-reorder bug is NARROW (it only manifests as a
divergence in multi_source's multi-initial-source interleaving tie-break; single_source and the rest match nx
+ are fast, so they either preserve order or are not order-sensitive at one source). REFUTES the broad-latent-
cluster worry: fixing the reserved projection builder unlocks essentially just multi_source_dijkstra (+ steiner
which calls it), not a family. Modest scope, still reserved-gated. Weighted-dijkstra family otherwise
comprehensively won. 13 vs-nx wins shipped this session.

## 2026-06-26 CopperCliff multi_source via k-single_source workaround — REJECT (paths diverge + slower); fully reserved-gated

Final takeable-hope test for multi_source_dijkstra: compute it as a merge of k single_source_dijkstra calls
(single_source is correct 0/116 + fast 5.4x; merge = min dist, earlier-source-wins-ties). RESULT: distances
match nx 0/77, but PATHS diverge 61/77, AND it's slower (0.33x at k=8 / 0.87x at k=3 — k dijkstra calls +
merge). WHY paths diverge: nx.multi_source's path to a node is NOT nx.single_source's path from its nearest
source — the multi-source heap interleaving tie-breaks shortest-path choices differently than a standalone
single-source run. So the merge is both wrong (61/77) and slow. NO PYTHON WORKAROUND for multi_source.
CONCLUSION: multi_source_dijkstra is FULLY reserved-gated — the only fix is making the reserved weighted-
projection builder (dijkstra_single_weight_graph_projection, fnx-python) preserve insertion-order adjacency
so the native kernel's interleaving tie-break matches nx. All avenues exhausted (kernel neighbor-iter fix:
futile; k-single-source merge: wrong+slow; gate-removal: 8% divergence). multi_source chain fully closed.
13 vs-nx wins shipped this session; remaining work is operator-unblock-gated.

## 2026-06-26 CopperCliff multi_source FINAL: projection builder confirmed reserved+ACTIVE; exact fix spec recorded

Confirmed the projection-reorder fix is reserved-gated (not takeable): dijkstra_single_weight_graph_projection
lives in fnx-python/src/algorithms.rs, which is ACTIVELY committed (recent peer commits: b7da26873/e0257a6d7
connectivity, accca957d in_edges, e46006d20 paths) — genuinely reserved+active (vs TealSpring's stale
fnx-algorithms/lib.rs I could take). Root of the reorder: the builder constructs the projection from
pg.inner.edges_ordered_indices() (edge-insertion order) + extend_fresh_index_edges_with_attrs_unrecorded,
which yields per-node adjacency in EDGE order, NOT the original per-node neighbor-insertion order (node 8:
projection [0,3,4,1,7] vs original [4,0,3,1,7]). EXACT FIX (for whoever holds algorithms.rs): build the
projection's per-node adjacency by iterating each node's neighbors via neighbors_iter (insertion order) rather
than edges_ordered_indices, so the native multi_source kernel's interleaving tie-break matches nx. Then remove
the Python weighted-gate (__init__.py:31728) -> multi_source_dijkstra 0.157x -> fast + byte-exact, unlocks
steiner_tree too. multi_source chain DEFINITIVELY closed (reserved-active, fix fully specced). 13 wins shipped.

## 2026-06-26 CopperCliff distance-measures + hashing + planarity sweep — ALL WINS (no gap)

Fresh domain (n=400): resistance_distance 274x, radius 18.99x, center 17.68x, periphery 17.60x, barycenter
17.50x, diameter 16.90x, check_planarity 7.67x, is_regular 3.56x. NEAR-PARITY: weisfeiler_lehman_graph_hash
0.93x / weisfeiler_lehman_subgraph_hashes 0.88x (SHA-computation-bound; both compute identical hash strings,
the hashlib calls dominate — not cheaply winnable). No gap. ~27 domains swept this session, all return wins.
Accessible periphery DEFINITIVELY mined out; remaining vs-nx work is operator-unblock-gated (reserved
fnx-python core: sigma/omega random_reference + steiner mehlhorn + sticky-edges_dirty + multi_source
projection-builder, all with exact fix specs in this ledger) / proven-impossible (group_betweenness>=3,
spectral_ordering) / inherent (non_randomness dense-eig, min_cost_flow single-pass, communicability O(n^4),
all_pairs materialization). 13 vs-nx wins + 2 parity-fixes shipped, all durability-verified.

## 2026-06-26 CopperCliff traversal-family sweep (n=2000) — ALL WINS; multi_source now peer-worked

Aggressive traversal hot-path sweep (directive: go aggressive on traversal): bfs_tree 3.06x, dfs_tree 3.09x,
dfs_edges 1.87x, dfs_predecessors 1.83x, bfs_edges 1.60x, bfs_successors 1.52x, edge_bfs 1.45x, bfs_layers
1.44x, edge_dfs 1.41x, dfs_postorder_nodes 1.34x, bfs_predecessors 1.31x, descendants 2.34x. ALL WINS. The
low-end (bfs_layers/predecessors 1.3-1.4x) is PyObject-result-materialization-floored (native BFS is fast;
building the Python edge/node lists is the residual — view-substrate floor, not cheaply improvable). No
takeable gap in the traversal family. SIGNAL: origin/main HEAD = 3135ea43e "docs(perf): reject weighted
multi-source de-gate" — a PEER is now working the multi_source gate (independently reached the same
de-gate-is-unsafe conclusion I recorded). So the one remaining takeable-after-projection-fix gap
(multi_source) is actively peer-owned + reserved (algorithms.rs) -> I must not duplicate/collide. Traversal +
centrality hot paths confirmed comprehensively won. 13 vs-nx wins shipped this session.

## 2026-06-26 CopperCliff core_laggards bench-group measured — biggest gap = MDG weighted degree 0.633x (sticky+view-floored, reserved)

Benched the head_to_head bench suite's EXPLICIT core_laggards group (n=1500/e=9000 MDG): biggest measured
gaps = MDG.in_degree(weight) 0.633x (7.17 vs 4.54ms), MDG.degree(weight) 0.657x (11.45 vs 7.52ms), MG
selfloop_edges(keys,data) 0.659x (0.13 vs 0.09ms, sub-ms). The rest are WINS (peer fixes landed): MDG.in_edges
(data) 28.3x, out_edges(nbunch,keys,data) 23.0x, out_edges(keys,data) 5.97x, edges(keys) 3.25x. ROOT CAUSE of
the weighted-degree gap (per reference_mdg_weighted_degree_store_int + this measurement): the native store-int
weighted-degree fast path (ac98e77d4) is gated on !edges_dirty, but a freshly-built/mutated MDG leaves
edges_dirty STICKY-true (weights live in the per-edge Python mirror, store stale) -> falls to per-edge PyO3
weight reads. AND the residual floor is PyObject per-node degree-VIEW materialization (the eilce index-native
accumulator lever was REFUTED/NO-SHIP — halving Rust work left fnx unchanged). So MDG weighted degree is
DOUBLY gated: sticky-edges_dirty (reserved lib.rs, the pyclass(extends=PyDict) master fix) + PyObject view
floor. NOT takeable. This IS the biggest measured laggard and it reduces to the already-surfaced sticky-
edges_dirty reserved-core lever. Traversal/centrality hot paths separately confirmed all-wins (prior turn).
13 vs-nx wins shipped this session.

## 2026-06-26 CopperCliff biggest measured gap = MultiGraph.degree(weight) 0.233x — reserved views.rs/lib.rs + sticky

Continued the bench-group measurement: MultiGraph.degree(weight) is the BIGGEST measured gap = 0.233x
(13.89ms vs nx 3.24ms, n=1500/e=9000) — WORSE than MDG.degree(weight) 0.657x (the MDG store-int fix
ac98e77d4 did not equivalently cover MultiGraph). Other construction/copy near-parity: to_directed(scalar)
0.882x, to_undirected(DiGraph) 0.854x, reverse 0.884x, Graph.degree(weight) 0.804x (all ~parity, established
construction/sticky floor); WINS: Graph.copy 1.55x, attr_assortativity 1.92x, number_of_edges 361x. The MG
weighted-degree path (MultiGraphDegreeView in views.rs + weighted_degree_py_int_row in lib.rs, both reserved
fnx-python) sums per-edge weights from the Python mirror (PyO3) because the store-int fast path is sticky-
edges_dirty-gated (construction leaves it dirty) AND MG may lack MDG's store-int routing. No Python
workaround (to_scipy weighted is sticky-bound; weighted sum needs per-edge weights = mirror PyO3). FIX is in
reserved views.rs/lib.rs (route MG weighted degree to a store-int sum + the sticky-edges_dirty master fix),
BlackThrush-owned + actively-worked (mdg-edge-baseline/selfloop-cache worktrees). NOT takeable. CONSOLIDATED:
every remaining biggest measured vs-nx gap (MG/MDG weighted degree, sticky paths, multi_source projection)
is in BlackThrush's reserved+active fnx-python core (lib.rs/views.rs/algorithms.rs); fnx-algorithms kernels
are all wins/impossible. 13 vs-nx wins shipped this session; new wins require the reserved-core operator unblock.

## 2026-06-26 CopperCliff OFFICIAL cargo bench (core_laggards, directive method) — canonical ratios + in_edges cache-is-warm-only finding

Ran rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head -- core_laggards (the directive's
prescribed method; criterion median of 20 samples). CANONICAL ratios (fnx/nx, lower=worse):
  fnx_mdg_in_edges_data_n700_e12662         5.4927ms / nx 2.4985ms = 0.45x  <- BIGGEST canonical gap
  fnx_mg_selfloop_keys_weight_n2500         811.51us / nx 465.08us = 0.57x
  fnx_mdg_in_degree_weight_n700_e12662      2.2579ms / nx 1.4710ms = 0.65x
  fnx_mdg_edges_keys_n700_e12662            1.2408ms / nx 1.0661ms = 0.86x (~parity)
  fnx_mdg_out_edges_nbunch_keys_data_n700   180.70us / nx 406.88us = 2.25x (WIN)
NEW FINDING: mdg_in_edges_data is 0.45x in the official bench but I measured 28x WARM in Python (repeated
calls on one graph). DISCREPANCY = the peer's in_edges(data) tuple cache (accca957d) is WARM-ONLY: criterion's
per-sample iteration evidently doesn't reuse the cached tuples (cold/rebuilt each iter), so the realistic
single-call cost is 0.45x, not 28x. So the in_edges cache helps repeated-call microbenchmarks but NOT a cold
call. All four canonical laggards (in_edges_data, mg_selfloop, mdg_in_degree_weight, mdg_edges_keys) are
reserved fnx-python view/degree paths (views.rs/lib.rs), BlackThrush-owned + actively-worked. The
warm-vs-cold in_edges nuance is a real reserved-side optimization target (make the in_edges cold path fast,
not just cached-warm) for whoever holds views.rs. NOT takeable. 13 vs-nx wins shipped this session.

## 2026-06-26 CopperCliff treewidth_min_degree convert+delegate — REJECT (decomp is adjacency-order-sensitive, breaks byte-exactness)

Dug the approximation namespace: treewidth_min_degree is the biggest TAKEABLE gap (0.47-0.65x; fnx.approximation
.treewidth_min_degree -> _treewidth_min_degree in __init__.py runs nx's _MinDegreeHeuristic + _treewidth_decomp
DIRECTLY on the fnx graph G = per-op PyO3). It's a Python path (not reserved Rust). Attempted convert+delegate
(build a one-shot nx.Graph copy H from G.nodes()+G.edges(), run nx's treewidth on H). RESULT: BREAKS byte-
exactness -> 3 conformance failures (test_matches_networkx_without_fallback). ROOT CAUSE: building H from
G.edges() does NOT preserve G's per-node ADJACENCY insertion order (G.edges() iteration order != per-node order
-- the SAME wall as multi_source_dijkstra), and the min-degree elimination heuristic's tie-break is adjacency-
order-sensitive, so the tree DECOMPOSITION diverges (treewidth int matches but the bag/edge structure differs).
The only byte-exact path is running nx's algo on G directly (preserving G's order) = the slow status quo
(0.47x). Convert+delegate is byte-exactness-incompatible here (order-sensitive output). REVERTED both
__init__.py + approximation.py edits (conformance restored 92 passed). treewidth_min_degree stays the slow
byte-exact nx-on-fnx path; a real win needs an order-preserving native treewidth (would need to iterate G's
exact adjacency order). Same adjacency-order-sensitivity class as multi_source. NO-SHIP. 13 wins shipped.

## 2026-06-26 CopperCliff treewidth_min_degree CONCLUSIVELY non-takeable (decomp copy-fragile + test forbids nx-fallback)

Closed the treewidth_min_degree convert+delegate question definitively: tested nx.Graph(gf) (the direct
constructor, which DOES preserve gf's per-node adjacency order: 0/25 adjacency mismatches) -> but
treewidth_min_degree(nx.Graph(gf)) still DIVERGES from treewidth(gn) 4/25 (decomp differs even with identical
adjacency). So the min-degree tree DECOMPOSITION is sensitive to node-dict insertion order / degree-heap
tie-breaks BEYOND adjacency order -> no graph copy reliably reproduces nx's exact decomp; only running on the
original graph object is byte-exact. ALSO: the conformance test is test_matches_networkx_WITHOUT_FALLBACK,
which explicitly FORBIDS delegating to nx's public fn (fnx must compute natively) -- so the convert+delegate-
to-nx-public approach fails the no-fallback assertion regardless of timing. The internals-on-copy approach
passed conformance once but is byte-exactness-FRAGILE (the 4/25 copy-divergence shows copies aren't reliable).
CONCLUSION: treewidth_min_degree stays the slow byte-exact native-on-fnx-graph path (0.47x); a real win needs
an order-preserving NATIVE treewidth kernel (iterate G's exact node+adjacency order in Rust) -> reserved
binding. Non-takeable via Python. Same order-sensitivity class as multi_source. Definitively closed. 13 wins
shipped this session.

## 2026-06-26 CopperCliff fnx.degree(nbunch,weight) — biggest OFFICIAL gap 0.043x; G.degree routing RECURSES (reserved)

Official cargo bench (weighted_degree group) biggest gap: fnx_degree_nbunch_weight_mg400 51.9ms / nx 2.26ms =
0.043x (23x slower!) -- MultiGraph fnx.degree(G, nbunch, weight) where nbunch has dups + missing nodes
(bench line 1356: [(i*7)%400 for i in range(280)] + [401,402,3,3,99]). ROOT CAUSE: the top-level fnx.degree
weighted path uses a Python weighted_degree(node) helper that iterates G.adj[node] through PyO3 per multi-edge
(~73us/node). Attempted routing to the native view (return G.degree(nbunch, weight=weight)) -> BYTE-EXACT
(==nx, all graph types) + 21x self (0.030x->0.64x) in a standalone list-nbunch test, BUT BREAKS conformance:
"!!! Recursion detected" in 3 tests (multigraph_classes_expose_callable_degree, reverse_view ...without_
fallback). CAUSE: for MultiGraph/MultiDiGraph the native DegreeView's weighted single-node/None path delegates
BACK to the top-level fnx.degree -> routing fnx.degree -> G.degree closes the cycle -> infinite recursion.
So fnx.degree CANNOT route to G.degree (circular). REVERTED (conformance restored). A fast fix needs either
breaking the DegreeView<->fnx.degree cycle or a native store-int weighted-degree sum -- both in reserved
views.rs/lib.rs (BlackThrush, sticky-gated). The biggest official gap (0.043x MG degree(nbunch,weight)) is
reserved. Other weighted_degree official ratios: MDG out_degree 0.56x, MG size_weight 0.42x, MDG in_degree
0.74x -- all reserved degree-view paths. 13 wins shipped.

## 2026-06-26 CopperCliff SHIP: fnx.degree(iterable nbunch, weight) 0.043x->0.48x (biggest official gap, 11x self, byte-exact)

LANDED the biggest OFFICIAL cargo-bench gap. fnx.degree(G, nbunch, weight) for an iterable nbunch built a
Python generator calling weighted_degree(node) that iterates G.adj[node] through PyO3 per multi-edge ->
official fnx_degree_nbunch_weight_mg400 0.043x (51.9ms vs nx 2.26ms, 23x slower; bench nbunch = [(i*7)%400
for i in range(280)] + [401,402,3,3,99], dups + missing nodes). FIX: route ONLY the iterable-nbunch weighted
branch to the native DegreeView (return G.degree(nbunch, weight=weight)) -> 0.043x->0.48x (11x self),
byte-identical to nx across Graph/DiGraph/MultiGraph/MultiDiGraph (same dup/missing handling + self-loop
doubling). The None + single-node branches MUST stay Python: for MultiGraph the native view delegates those
back to fnx.degree, so routing them recurses ("Recursion detected", 3 tests) -- list-only routing avoids it
(the iterable path is native + non-recursive). conformance GREEN (2869 passed -k degree). Per
reference_parity_blocked_by_set_order, value-returning de-delegation maxes ~0.5-0.77x (can't beat nx), so
0.48x is near-ceiling; the residual to parity is the reserved native store-int weighted sum (sticky-gated).
14th win this session.

## 2026-06-26 CopperCliff OFFICIAL cargo-bench CONFIRMATION of the degree fix (f22e353e0)

Re-ran rch cargo bench -p fnx-python -- multigraph_weighted_degree AFTER the fix. CONFIRMED:
  fnx_degree_nbunch_weight_mg400: 51.947ms -> 1.0725ms  (nx 655.92us) = 0.043x -> 0.61x  (48x self-speedup!)
  fnx_size_weight_mg400:           6.96ms  -> 1.3447ms   (nx 846.80us) = 0.42x  -> 0.63x  (size formula shares
                                                                                            the degree path)
Official criterion median, directive's prescribed method. The biggest official core_laggards gap (23x slower)
is now 1.6x slower -- byte-exact, conformance GREEN. Real, durable, landed on main+master.

## 2026-06-26 CopperCliff SHIP: in/out_degree_centrality 0.56x->1.23x (native kernel was slower AND wrong)

Found via the degree_centrality family sweep (after the fnx.degree win): in_degree_centrality /
out_degree_centrality on a simple DiGraph routed to _raw_in/out_degree_centrality (native Rust), which is
(a) SLOWER -- 0.51-0.62x vs nx (builds the {node: centrality} dict through PyO3 per node = the PyObject-
materialization floor) AND (b) NOT byte-exact -- native!=nx on n>=1500 (f64 ULP drift from a different
d*(1/(n-1)) order) and returns float 1.0 vs nx's int 1 for n==1. nx's own implementation is just
{n: d*(1.0/(n-1.0)) for n,d in G.in_degree()} -- a Python dict-comp over the (fast) native in_degree view.
FIX: route the simple-DiGraph branch to nx's verbatim dict-comp (matching the existing multigraph branch).
RESULT: 0.56x -> 1.22-1.23x (BEATS nx), byte-IDENTICAL to nx across n=0/1/2/large + MultiDiGraph + int-1
singleton type, conformance GREEN (302 passed). LEVER: a NATIVE kernel that materializes a per-node dict via
PyO3 can be SLOWER than nx's C-level dict-comp over the native view -- when the wrapper already has the view,
the Python dict-comp wins (inverse of the fnx.degree fix where Python->native won). Audit other _raw_*
centrality/dict kernels that build {node: val} via PyO3. 15th win this session.

## 2026-06-26 CopperCliff SHIP: preferential_attachment explicit-ebunch endpoint degree-batch 0.24x->0.67x (2.8x self)

Family sweep found two link-pred per-pair gaps: preferential_attachment 0.242x, resource_allocation_index
0.569x (jaccard/adamic were fixed in c7ffab536; these weren't fully). _link_prediction_compute batched the
degree snapshot only for the full/default ebunch (len>=n_nodes); a MODERATE explicit ebunch (200 pairs <
1200 nodes) stayed on the lazy per-node deg() path = N G.degree(n) PyO3 calls. FIX: preferential_attachment
uses ONLY endpoint degrees, so batch the distinct endpoints in ONE native G.degree(nbunch) call (the
fnx.degree win makes that fast) -> 0.24x -> 0.67x (2.8x self), byte-identical (==nx incl default + single-pair
ebunch), conformance GREEN (1233 passed). Residual cap to beat-nx is _link_prediction_validate_ebunch's
per-node membership checks (the degree batch alone gets a standalone 1.71x; the validation machinery holds
the full wrapper to 0.67x) -- not touched (correctness/error contract). resource_allocation_index 0.57x left:
its deg(w) are for per-pair COMMON NEIGHBORS (dynamic), not endpoints, so endpoint-batch doesn't apply (would
need a two-pass neighbor-union batch). 16th ship this session.

## 2026-06-26 CopperCliff resource_allocation substrate-floored + broad sweep (takeable cheap-dict vein mined)

After the 3 degree/link-pred ships, dug the residual + swept broadly:
- resource_allocation_index 0.57x: REJECT batch. Prototyped batching all endpoint-neighbor degrees -> 0.46x
  (WORSE: the neighbor union is huge vs the few common neighbors actually used; lazy deg(w) over actual
  common neighbors is already optimal). The real floor is the per-endpoint neighbor FETCH:
  fnx must materialize list(G.neighbors(u)) via PyO3 per endpoint, whereas nx iterates its native Python
  dict G[u] directly (zero materialization). Substrate-floored (Rust adjacency + PyO3 vs native Python
  dict) -- NOT takeable in Python. The degree-batch lever (which won preferential_attachment) doesn't apply
  (resource_allocation's degrees are common-neighbor, not endpoint).
- BROAD SWEEP all WINS/parity (no new <0.7x takeable gap): connected/strongly_connected/attracting_components
  3.5-5.8x, descendants/ancestors ~1.0x, dfs/bfs_tree 3.0x, is_tree 39x, immediate_dominators 4.9x,
  single_source_shortest_path_length 3.7x, eccentricity 9.3x, edge_boundary 1.8x, closeness_vitality 12.2x,
  clustering 84x, transitivity 161x, pagerank 12.6x, harmonic 238x. Borderline (not clean fixes):
  node_boundary 0.80x (native _raw + needed set() coercion), bipartite.degrees 0.74x (niche).
- OFFICIAL cargo bench link_prediction (common_neighbor_centrality g600 e2000): fnx 37.4ms / nx 136.8ms =
  3.66x WIN.
CONCLUSION: the takeable cheap-per-node/per-pair dict vein is MINED (degree nbunch, in/out_degree_centrality,
preferential_attachment shipped this session). Residual gaps = reserved MDG/MG weighted-degree views
(sticky) + substrate-floored adjacency-materialization (resource_allocation). Don't re-dig resource_allocation
via batching.

## 2026-06-26 CopperCliff SHIP: fnx.tree.min/max_spanning_tree route to native top-level 0.36x->0.69x (full-bench hidden gap)

Ran the OFFICIAL cargo bench across unexplored groups (construction_copy/sticky/cut_metrics/assortativity/
tree_submodule/multigraph_biconnected/multidigraph_connectivity/lattice). 20/21 workloads win or parity; the
ONE hidden gap = tree_submodule/tree_minimum_spanning_tree_g1000_e4999 0.352x. CAUSE: fnx.tree.minimum_
spanning_tree (in tree.py) is a SEPARATE function from the top-level fnx.minimum_spanning_tree -- it delegated
to nx (_nx_tree.minimum_spanning_tree + _from_nx_graph = full fnx->nx->fnx round-trip, 0.36x), while the
top-level has a byte-exact native Kruskal/Prim/Boruvka kernel returning an fnx graph directly (0.66x). FIX:
route fnx.tree.min/maximum_spanning_tree -> _fnx.min/maximum_spanning_tree (drop the nx round-trip). RESULT:
0.36x -> 0.69x (min) / 0.65x (max), 1.9x self, byte-IDENTICAL edge+weight set ==nx, conformance GREEN (3337
passed). LEVER: submodule namespaces (tree/approximation) can carry a SECOND nx-delegating copy of a function
the top-level already does natively -- audit fnx.tree.* / other submodules for delegating wrappers shadowing
a fast top-level. NOTE: the top-level MST itself is 0.66-0.69x on simple graphs (native kernel + edge-sync +
PyO3 result build) -- a separate deeper floor, not closed here. Full-bench frontier (this run): only gap was
this one; construction_copy graph_to_directed_scalar 0.81x (near-parity); everything else 1.3-7.7x wins.
17th ship this session.

## 2026-06-26 CopperCliff maximum_spanning_edges weighted FLOORED ~0.28x (reserved _raw_mse) + fresh sweep clean

Tree-submodule audit (continuing the de-delegation lever) found tree.maximum_spanning_edges 0.279x (vs
minimum_spanning_edges 2.48x WIN). ROOT CAUSE: maximum_spanning_edges gated its native kruskal path on
``not _mst_has_weight_edge_attr(G, weight)`` (UNWEIGHTED only) -> WEIGHTED graphs fell through to
_call_networkx_for_parity (nx delegate, 0.28x). Tried mirroring minimum_spanning_edges' weighted native path
(_sync_rust_edge_attrs + _raw_mse + lazy-mirror post-check): byte-EXACT (==nx, order+orientation+data) but
REGRESSED/no-gain -- native _raw_mse is itself ~0.21-0.38x (the maximum kruskal Rust kernel is ~9x slower
than _raw_minimum_spanning_edges; the original unweighted-only gate was deliberately avoiding it). REVERTED
(stashed). Also tried negated-minimum (build -weight temp graph, run the FAST minimum kernel, restore data):
byte-exact but ~0.26-0.31x -- the O(E) temp-graph CONSTRUCTION tax offsets the fast kernel. So weighted
maximum_spanning_edges is FLOORED at ~0.28x across all 3 paths (delegate / native _raw_mse / negated-min);
the only real fix is optimizing the reserved _raw_mse Rust kernel (make it as fast as _raw_minimum_spanning_
edges) -- and the MST/tree area is now PEER-ACTIVE (200c81c33 "perf(tree): lazy MST result materialization").
NOT takeable. FRESH SWEEP (coloring/matching/clique/dominating/k_core) all wins/parity: greedy_color 8.7x,
maximal_matching 8.3x, k_core 40.7x, find_cliques 1.0x, max_weight_matching 0.95x, dominating_set 0.84x --
no new <0.7x takeable gap. 17 ships stand.

## 2026-06-26 CopperCliff SHIP: maximum_spanning_edges weighted 0.28x->2.7x (kernel-level: kill per-call graph copy + route native)

SINGLE biggest measured gap was maximum_spanning_edges (weighted kruskal) ~0.28x vs nx. RADICAL fix at the
RUST binding level (codex walled -> reserved fnx-python now collision-free): the maximum_spanning_edges
binding (algorithms.rs:8098) UNCONDITIONALLY built a sanitized O(V+E) copy via spanning_input_graph EVERY
call, while minimum_spanning_edges only copies for ignore_nan and otherwise runs the kernel on the borrowed
gr.undirected() (no copy). That redundant per-call copy was the ~9x slowdown. FIX (two-part, both required):
  1. algorithms.rs: mirror minimum_spanning_edges -- copy only for ignore_nan; common path runs the kernel on
     the borrowed graph (no O(V+E) copy).
  2. __init__.py: the Python wrapper gated the native path on ``not _mst_has_weight_edge_attr`` (unweighted
     ONLY) so weighted delegated to nx; route weighted kruskal to native _raw_mse via _sync_rust_edge_attrs +
     lazy-mirror post-check (mirrors minimum_spanning_edges).
RESULT: 0.28x -> 2.75x (n=500) / 2.65x (n=1000, the bench size) / 0.84x (n=2000), byte-IDENTICAL to nx
(order+orientation+data; unweighted/weighted/data=False/small all ==nx), conformance GREEN (3420 passed).
Built fnx-python per-crate via rch, crossbeam-clean .so. (Last turn this REGRESSED because only the wrapper
was changed while the binding still copied -- BOTH halves are needed.) Residual: n=2000 0.84x (result
materialization at scale, separate). 18th ship.

## 2026-06-26 CopperCliff NEGATIVE: MG.size(weight) native-AttrMap read — byte-exact but perf inconsistent (REVERTED)

SINGLE biggest measured gap (post earlier fixes): MG.size(weight) ~0.21x (PyMultiGraph::size, lib.rs:4019
used edges_ordered() = EdgeSnapshot+String-key alloc per edge + PyO3 mirror-dict lookup + extract::<f64> per
edge). RADICAL try (codex walled -> reserved lib.rs free): when the per-edge mirror is PRISTINE
(edge_py_attrs.is_empty()), read the weight straight from the native AttrMap (CgseValue Int/Float/Bool) via
edges_ordered_borrowed -- no snapshot/String/PyO3; String/Map + non-pristine fall back to the mirror path.
BYTE-EXACT (int/float/missing=1.0/str-weight TypeError/multi all ==nx). BUT perf INCONSISTENT + DEGRADES with
scale: n=400 0.65x, n=1500 0.50x, n=2500 0.23x. ROOT: edges_ordered_borrowed() still allocates an O(E) Vec of
tuples (the snapshot tax isn't fully removed), and the pristine-mirror gate's state is unpredictable
(add_edge vs add_edges_from materialize the mirror differently -> the fast path fires inconsistently). Net
~0-gain at the sizes that matter. REVERTED (stashed). A real win needs a NON-allocating edge+attr streaming
iterator (no Vec) over the native store; edges_ordered_borrowed's Vec is the floor. 
ALSO FOUND (pre-existing, NOT mine): tests/python/test_laplacian_spectrum_native.py 2 failures
(test_weighted_star_laplacian_stays_on_weighted_route, ..._complete_bipartite_normalized_..._weighted_route)
PERSIST after reverting my change + rebuilding clean source -> a regression already on main (likely a recent
peer commit, e.g. 200c81c33). BLOCKER FLAG for whoever owns the laplacian route.

## 2026-06-26 CopperCliff CLARIFICATION on the 2 laplacian-route test failures (public API is CORRECT)

Refined the earlier flag: the PUBLIC fnx.laplacian_spectrum on a held-ref-weighted star (Gf[0][1]['weight']
=2.5) returns the CORRECT weighted spectrum (np.allclose vs nx == True: [0,1,1,1,1,1,1,2.056,10.944]). So
this is NOT a user-facing correctness regression. The 2 failing tests assert an INTERNAL invariant --
_star_laplacian_spectrum_sorted_value_safe(G,'weight') should return None (bail to the weighted route) for a
weighted graph, but it returns the UNWEIGHTED spectrum [0,1..,9]. ROOT: dijkstra_weight_cache_token
(algorithms.rs:3677) reports edge_attrs_dirty=False after a HELD-REF dict mutation (G[u][v]['weight']=x first
materializes the mirror dict then mutates it; the token doesn't treat a materialized/non-pristine edge_py_attrs
as dirty). The sticky-edges_dirty class. Likely surfaced by a recent mirror/dirty commit (114e968f3 lazily-
invalidate clear_edges mirrors / 29b752d47 clear edges_dirty after bulk replace). FIX (next, kernel-level):
dijkstra_weight_cache_token should report dirty (or bail) when edge_py_attrs is non-empty for the edges in
question. Public laplacian_spectrum stays correct meanwhile (it re-validates). Not blocking users; cleaning up
the internal certificate is the follow-up.

## 2026-06-26 CopperCliff NEGATIVE #2: MG.size(weight) zero-alloc native fold — ~0-gain at bench size (REVERTED)

Follow-up to NEGATIVE #1's lever ("needs a non-allocating edge+attr iterator"). Added
MultiGraph::sum_edge_attr_numeric (fnx-classes) -- a ZERO-allocation fold over self.edges (each canonical
pair once, no Vec/dedup-HashSet, unlike edges_ordered_borrowed), matching number_of_selfloops' pattern; wired
PyMultiGraph::size to call it gated on a pristine mirror (edge_py_attrs.is_empty()). BYTE-EXACT (int/float/
missing=1.0/str-weight TypeError/multi/float all ==nx), conformance GREEN (858 size tests). Python timing
improved at scale (n=2500 0.23x->0.75x vs NEGATIVE #1) but OFFICIAL cargo bench (the decider) =
fnx_size_weight_mg400 1.3995ms / nx 891us = 0.637x == the ~0.63x baseline -> ~0-GAIN at the bench size (n=400,
3224 edges). ROOT: even zero-alloc, the per-edge BTreeMap(AttrMap)::get(attr) lookup + FxIndexMap iteration
over E edges (1.40ms) is slower than nx's sum(degree(weight))/2 over native C dicts (0.89ms). The native edge
fold cannot beat nx's degree-sum at this size; the AttrMap-BTreeMap-lookup is the floor. REVERTED both files
(fnx-classes method + lib.rs gate). MG.size(weight) is FLOORED ~0.63x for the native approach; a real win
would need a numeric-attr fast-lane in the storage layer (e.g. a parallel f64 weight column) -- out of scope.
Conclusion: MG.size(weight) / weighted-degree family is storage-substrate-bound (BTreeMap attr lookup), not a
clean kernel win. STOP attacking MG.size(weight) via edge iteration.

## 2026-06-26 CopperCliff weighted-degree-family "fast sibling" was NOISE — whole family substrate-bound (closure)

Probed the apparent asymmetry (MDG.degree(weight) 1.28x WIN vs in_degree 0.239x GAP) as a candidate
"mirror-the-fast-sibling" win (like maximum_spanning_edges). RE-MEASURED on a clean reverted build: MDG.degree
(weight) 0.59x, in_degree 0.44x, out_degree 0.73x -- the earlier 1.28x was MEASUREMENT NOISE (warm-cache/
variance), NOT a real fast path. There is NO clean fast sibling to mirror; the entire weighted-degree/size
family (MG.degree 0.45x, MG.size 0.63x, MDG in/out/degree 0.44-0.73x) sits at the SAME ~0.4-0.7x substrate
floor: per-edge AttrMap (BTreeMap) weight lookup + PyObject degree-view tuple materialization, both slower
than nx's native C dicts. CONCLUSION: the weighted-view family is storage-substrate-bound, not a kernel-lever
win. A real win needs a storage-layer change (numeric weight column / faster attr map) -- a large structural
project, out of scope for a single dig. STOP attacking the weighted-degree/size family via kernel/iteration
levers. Clean kernel wins remain elsewhere (the de-delegation / redundant-copy class, e.g. maximum_spanning_
edges 0.28x->2.7x shipped).

## 2026-06-26 CopperCliff wide sweep — redundant-copy vein mined, no new takeable <0.7x gap (frontier state)

After closing the weighted-degree/size family (substrate-bound), swept for the next CLEAN kernel/de-delegation
lever (the class that gave maximum_spanning_edges 0.28x->2.7x):
- REDUNDANT-COPY audit (spanning_input_graph callers): all clean -- minimum/maximum_spanning_edges copy ONLY
  for ignore_nan; maximum_spanning_tree uses gr.undirected() (no copy); the only other caller (algorithms.rs
  :23117) is a #[test]. Vein mined for spanning.
- DIRECTED/TRAVERSAL/DAG: all WINS -- transitive_closure 7.7x, transitive_reduction 2.2x, condensation 4.4x,
  dfs_pre/postorder 2.4x/1.25x, find_cycle 6.1x.
- OPERATORS (graph-returning de-delegation candidates): all WINS/parity -- compose 1.1x, cartesian_product
  2.5x, tensor_product 3.1x, line_graph 3.5x, power 1.8x, complement 3.1x, to_undirected 3.3x, subgraph.copy
  1.1x, quotient_graph 1.5x; only ego_graph 0.78x (near-parity, Python BFS over PyO3 neighbors +
  construction = substrate-bound, not a clean lever).
CONCLUSION: the takeable kernel/de-delegation frontier is MINED. Remaining vs-nx gaps are all (a)
substrate-bound (weighted-degree/size AttrMap-lookup, in_edges cold tuple-materialization, resource_allocation
adjacency-materialization, ego_graph BFS) or (b) near-parity (construction_copy 0.81x, junction_tree 0.96x,
ego_graph 0.78x). No clean <0.7x kernel win remains; the next tier needs storage-layer work (numeric weight
column / faster attr map) or is within noise. 18 perf ships stand.

## 2026-06-26 CopperCliff fresh-domain sweep (similarity/iso/flow-centrality/structural/reciprocity) — all wins/parity

Swept domains not previously covered this session, looking for a clean <0.7x kernel/de-delegation gap:
  simrank_similarity 1.07x, panther_similarity 0.97x, could_be_isomorphic 0.81x (already fnx-optimized: native
  degree early-exit br-r37-c1-cbiso; residual is triangles/cliques, near-parity), fast_could_be_isomorphic
  2.08x, current_flow_betweenness 48x, communicability 12.5x, subgraph_centrality 44.5x, second_order_centrality
  3260x, constraint 6.5x, effective_size 6.9x, flow_hierarchy 175x, reciprocity 7.3x, overall_reciprocity 5.6x,
  local_efficiency 12.1x, non_randomness 0.89x.
NO new <0.7x takeable gap. Combined with the prior wide sweep (directed/traversal/operators) and the
substrate-bound family closures, the takeable kernel/de-delegation frontier is COMPREHENSIVELY MINED across
all benched domains. Remaining vs-nx gaps are exclusively substrate-bound (weighted-degree/size AttrMap lookup,
in_edges cold, resource_allocation, ego_graph) or near-parity within noise (could_be_isomorphic 0.81x,
construction_copy 0.81x, junction_tree 0.96x). 18 perf ships stand; next-tier wins require storage-layer work
(numeric weight column / non-BTreeMap attr map), a multi-hour structural project, not a single-dig lever.

## 2026-06-26 CopperCliff lazy-mirror lever RULED OUT for the edge-attr family (selfloop_edges also ~0.68x native)

Probed whether the substrate-family ~0-gain was due to the pristine-mirror gate NOT firing (i.e. add_edge
eagerly populating edge_py_attrs), which lazy-mirror construction could fix. Tested selfloop_edges(data=weight)
on an add_edge-built MG: 0.68x, and a held-ref edge access (which breaks pristine) did NOT change it (0.68->
0.70x). So selfloop_edges' native path is ALREADY ~0.68x regardless of mirror state -- the AttrMap/PyObject
substrate is the floor, NOT the gate. CONCLUSION: making add_edge leave the mirror lazy/pristine would NOT
unlock meaningful wins for the edge-attr family (size/degree/selfloop_edges all ~0.4-0.7x via native paths);
the lazy-mirror lever is RULED OUT. The ONLY remaining lever for this family is a storage-layer change (a
parallel numeric f64 weight column updated on mutation, replacing per-edge BTreeMap<String,CgseValue>
lookups), a multi-hour structural project across fnx-classes edge mutation paths. DON'T re-attempt lazy-mirror
or native-fold variants for size/degree/selfloop weighted -- they're all substrate-floored. 18 ships stand.

## 2026-06-26 CopperCliff SHIP (correctness): star/complete-bipartite spectrum certs wrongly certified SYNCED-WEIGHTED graphs as unweighted

USER-FACING BUG (found while diagnosing 2 pre-existing red tests): fnx.laplacian_spectrum /
normalized_laplacian_spectrum / adjacency_spectrum on a weighted star or complete_bipartite graph returned the
correct weighted spectrum on the FIRST call but the WRONG UNWEIGHTED spectrum on the SECOND call. Root cause:
_star_shape_certificate_size + _complete_bipartite_shape_certificate_parts certify "unweighted" via the
dijkstra_weight_cache_token's edge_attrs_dirty flag, but the first spectrum call SYNCS the graph (clears
edges_dirty) while the weights remain in the native store -> the 2nd call sees a clean token and wrongly takes
the unweighted closed-form fast path. edges_dirty cannot witness "no weights". FIX (Python, no build): require
the O(1) native graph_has_any_attrs(G) to be False for the unweighted fast path; attr-bearing graphs fall
through to the explicit per-edge weight check / weighted route. Verified: star+bipartite call1==call2==nx for
laplacian/normalized/adjacency spectrum; attr-free graphs keep the closed-form fast path (cert still fires);
dijkstra/shortest_path double-call unaffected. The 2 pre-existing red tests
(test_weighted_star_laplacian_stays_on_weighted_route, ..._complete_bipartite_normalized_...) now PASS.
conformance GREEN (2661 spectrum/laplacian/dijkstra/shortest_path tests + 30 laplacian-native). Correctness
ship; greens main.

## 2026-06-26 CopperCliff cert-bug-class AUDIT closed + last-turn fix verified regression-free

Followed up the synced-weighted spectrum-cert fix (00bbf464a) with a full audit of every edge_attrs_dirty cert:
- OTHER closed-form spectrum certs (complete/cycle/path/edgeless, laplacian+adjacency+normalized): double-call
  on held-ref-weighted inputs all CORRECT (call1==call2==nx). They use a PRECISE per-edge `weight in attrs`
  O(E) scan (not the buggy edges_dirty fast-cert), so no synced-weighted bug. (Already 410x@n200 / 3167x@n400
  faster than nx via the closed form, so the O(E)->O(1) graph_has_any_attrs micro-opt is ~0-gain vs nx -> NOT
  shipped.)
- DELEGATION/cache certs (_should_delegate_dijkstra / _should_delegate_bellman_ford / _pagerank_scipy):
  dijkstra/bellman_ford/pagerank double-call (incl. unweighted-then-weighted sync scenario) all CORRECT. These
  read weights directly (no unweighted closed form), so the bug class doesn't apply.
- REGRESSION CHECK on the last-turn fix: star/complete_bipartite with a NON-weight edge attr ('color', no
  'weight') still FIRE the fast path (cert returns non-None) and ==nx -> NO over-bail. The graph_has_any_attrs
  gate routes attr-graphs to the precise per-edge weight scan, which proceeds when 'weight' is absent.
CONCLUSION: the synced-weighted cert-bug class is FULLY CLOSED (only star + complete_bipartite were buggy,
both fixed + verified); no other latent instances; the fix is precise (no over-bail) + conformance GREEN. Main
is clean. Perf frontier remains substrate-bound (storage-layer project is the only remaining lever).

## 2026-06-26 CopperCliff IO/generators sweep — parse_adjlist construction-substrate-bound (0.56x); rest wins

Swept IO + generators + hashing (domains not before covered this session). Mostly WINS/parity: generate_adjlist
0.96x, generate_edgelist 1.20x, node_link_data 1.30x, to_dict_of_lists 1.75x, to_dict_of_dicts 1.26x,
gnp_random 2.23x, watts_strogatz 1.73x, random_regular 2.92x, powerlaw_cluster 1.30x, random_geometric 1.44x,
weisfeiler_lehman_hash 0.97x. GAPS: parse_adjlist 0.666-0.695x, adjacency_data 0.718x.
parse_adjlist ROOT: already batches (bulk add_nodes_from + add_edges_from, br-r37-c1-pjadl), so the gap is NOT
the parse loop -- isolated the CONSTRUCTION (add_nodes_from+add_edges_from on the parsed string-keyed nodes) =
0.561x (fnx 3.40ms vs nx 1.93ms). The per-edge record_decision LEDGER tax + PyO3 string-key construction is
slower than nx's plain Python dicts. read_adjlist beat this only via the NATIVE read_adjlist_simple file
reader (extend_*_unrecorded), which is N/A for a Python line-stream and whose unrecorded bulk APIs are NOT
exposed to Python (dir(Graph) has no extend/unrecorded). So parse_adjlist is construction-substrate-bound like
the rest. CONSOLIDATED: every remaining vs-nx gap is one of three DEEP native substrates -- (1) edge-attr
BTreeMap+PyObject (weighted degree/size/selfloop), (2) construction record_decision LEDGER + PyO3 string-key
(parse_adjlist, dict-builders), (3) adjacency PyO3 materialization (resource_allocation, ego_graph). All need
multi-hour native work (storage numeric column / Python-exposed unrecorded bulk builder / marking-dict). No
single-dig 60m-safe win remains. 18 perf + 1 correctness ship stand; main clean.

## 2026-06-26 CopperCliff construction-ledger lever RULED OUT — add_edges_from ALREADY unrecorded; gap is inherent Rust-storage

Was about to attempt a "Python-exposed unrecorded bulk builder" to bypass the record_decision ledger for the
construction class (parse_adjlist 0.56x). VERIFIED IT'S ALREADY DONE: add_edges_from's plain fast path
(PyGraph::add_plain_edge_batch, lib.rs:1378) ALREADY calls self.inner.extend_edges_unrecorded(edges) (NO
ledger) AND skips eager empty mirror dicts (br-r37-c1-89kxg). So the 0.561x construction is NOT the ledger --
it is the INHERENT string-key Rust-storage construction cost: per new node a node_key_map String->PyObject
insert + node_iter_mirror_insert, plus extend_edges_unrecorded's Rust-HashMap insert + string interning per
edge -- vs nx's plain CPython dict {str:{str:{}}} (a single highly-optimized C hashtable, no interning, no
mirror). CORRECTION to my earlier "ledger tax" framing: the ledger was the read_adjlist DELEGATION tax (7.3x),
already fixed; add_edges_from itself is already unrecorded. The construction-class lever is RULED OUT.
DEFINITIVE: all 3 remaining substrate classes are INHERENT to fnx's architecture (Rust storage + String keys +
PyObject mirror) vs nx's native CPython dicts -- (1) edge-attr BTreeMap lookup, (2) string-key construction,
(3) adjacency PyO3 access. CPython dicts are extremely hard to beat for raw string-keyed construction/lookup;
fnx's advantage is ALGORITHMS (computation kernels), where it wins 2-3000x, NOT raw dict-substrate ops. No
cheap single-dig win exists for these; only a fundamental storage redesign (numeric columns / int-key fast
lanes) could move them, and even that may not beat CPython dicts for string-keyed graphs. 18 perf + 1
correctness ship; main clean.

## 2026-06-26 CopperCliff DURABILITY: 19908 conformance tests GREEN — session's 19 ships durable, main healthy

Ran broad conformance across every shipped area + core (spanning/degree/centrality/spectrum/laplacian/
link-pred/tree/matching/clustering/components/flow/operators/adjacency/shortest-path/dijkstra/bipartite/
planar/community/triads/constraint/isomorphism): 19908 PASSED, 625 skipped, 1 xfailed, 0 FAILURES (95s).
Confirms the session's 19 ships are durable and main is clean under all the session's churn:
  18 perf ships (degree(nbunch) 0.043x->0.61x, in/out_degree_centrality 0.56x->1.23x, preferential_attachment
  0.24x->0.67x, tree min/max_spanning_tree 0.36x->0.69x, maximum_spanning_edges 0.28x->2.7x, + earlier
  find_asteroidal/node_classification/laplacian_centrality/percolation/etc.) + 1 user-facing correctness fix
  (star/complete-bipartite synced-weighted spectrum cert, 00bbf464a).
FINAL FRONTIER STATE: single-dig perf vein exhausted across all domains; the 3 remaining substrate classes
(edge-attr BTreeMap, string-key construction [ledger already bypassed], adjacency PyO3) are INHERENT to fnx's
Rust-storage-vs-CPython-dict architecture and not cheap-fixable. fnx decisively wins on ALGORITHM kernels
(2-3000x) and is at-or-near parity elsewhere; the only sub-parity cases are string-keyed dict-substrate ops
that are structurally hard to beat CPython dicts. Next move is an architecture decision (int-key fast lanes
already make int-keyed construction a win), not a single-dig.

## 2026-06-26 CopperCliff FULL official bench — every <0.7x gap is substrate-bound; clear_edges root-caused

Ran the FULL official cargo bench (all groups). Of 17 fnx/nx pairs in the gap-bearing groups: 12 WIN (>=1x),
and all 5 sub-0.7x gaps are SUBSTRATE-bound (no takeable kernel/de-delegation lever):
  0.162x mdg_in_edges_data         -- view tuple+PyDict materialization (cold; warm-only cache)
  0.325x mg_selfloop_keys_weight   -- edge-attr BTreeMap + tuple materialization
  0.379x multigraph_clear_edges    -- NEW root-cause below
  0.536x mdg_in_degree_weight      -- edge-attr weighted-degree (BTreeMap + PyObject view)
  0.645x graph_to_directed_scalar  -- construction (deepcopy-skip tried earlier, ~0-gain)
CLEAR_EDGES root-caused (fnx 719us vs nx 299us = 0.42x): PyMultiGraph::clear_edges is lazy at the Python layer
(edge_mirrors_stale flag) and the native MultiGraph::clear_edges is O(N) (edges.clear() + per-row clear) -- so
the cost is `self.edges.clear()` EAGERLY DROPPING ~4000 per-edge AttrMaps (BTreeMap + "weight" String +
CgseValue) = O(E) Rust deallocation, whereas nx's dict.clear() defers the data-dict deallocation to GC. This
is the edge-attr-storage substrate again (Rust eager-drop + per-edge String-keyed AttrMap alloc model vs
CPython dict + deferred GC). Not cheaply fixable (recycling/deferring drops is complex + unsafe; the real fix
is the columnar/interned-key storage redesign). CONFIRMS: the entire <0.7x frontier is the 3 inherent
substrate classes (edge-attr, construction, adjacency) + this deallocation variant -- all Rust-storage-vs-
CPython-dict architecture. 18 perf + 1 correctness ship; main green (19908 tests).

## 2026-06-26 CopperCliff clear_edges root-cause CONFIRMED via weighted/unweighted split (AttrMap dealloc, not row-clear)

Pinpointed the clear_edges 0.44x gap precisely: weighted MultiGraph clear_edges = 665us / nx 294us = 0.443x,
but UNWEIGHTED clear_edges = 354us / nx 315us = 0.890x (near-parity). So the entire ~310us gap is the EAGER
per-edge AttrMap (BTreeMap + "weight" String + CgseValue) deallocation in self.edges.clear() (4000 frees);
the adjacency-row-clearing machinery is fine (unweighted near-parity). RULES OUT a row-clearing fix. The only
lever is deferred or recycled deallocation (move the old edges map to a background-thread drop or a free-list)
-- a hacky infra change (thread-spawn overhead/accumulation, Send/memory-semantics risk) with marginal EV for
a sub-ms niche op; NOT attempted (would be ~0-gain-to-regression after thread overhead + conformance risk).
clear_edges is the edge-attr-storage substrate (Rust eager-drop + per-edge String-keyed AttrMap vs CPython
dict + deferred GC), same as the rest. The real fix is the storage redesign (interned attr keys make the
String drop free; columnar numeric weights eliminate the per-edge BTreeMap). Frontier unchanged: all <0.7x
gaps inherent Rust-storage-vs-CPython-dict. 18 perf + 1 correctness ship; main green.

## 2026-06-26 CopperCliff DEFINITIVE full-bench snapshot — 27 pairs: 21 win, 1 near-parity, 5 substrate gaps

Complete official cargo bench (all groups, 27 fnx/nx pairs): 21 WIN (>=0.85x, many 2-3000x), 1 near-parity
(multigraph_weighted_degree/degree_nbunch_weight 0.706x -- my earlier fix holding, up from 0.043x), and 5
sub-0.7x gaps, ALL substrate-bound + individually root-caused this session:
  0.162x mdg_in_edges_data        -- view (u,v,PyDict) tuple materialization (cold; warm-only cache)
  0.325x mg_selfloop_keys_weight  -- edge-attr BTreeMap + keyed tuple materialization
  0.379x clear_edges (multigraph) -- eager per-edge AttrMap dealloc (weighted 0.44x, unweighted 0.89x)
  0.536x mdg_in_degree_weight     -- edge-attr weighted-degree (BTreeMap + PyObject view)
  0.645x graph_to_directed_scalar -- construction (deepcopy-skip ~0-gain)
ALL 5 reduce to the inherent Rust-storage-vs-CPython-dict architecture (per-edge String-keyed BTreeMap attr
storage + PyObject mirror/view materialization vs nx's native C dicts). 78% of the bench's own designated
laggard/head-to-head workloads are at-or-above nx; the residual is exclusively CPython-dict-substrate ops that
are structurally hard to beat. SESSION CLOSE: 18 perf ships + 1 user-facing correctness fix, all durable
(19908 conformance tests green), main clean. The single-dig frontier is exhausted and fully root-caused; the
only remaining perf lever is a storage-layer redesign (interned attr keys / columnar numeric weights /
deferred edge drops), a deliberate multi-turn architecture project, not a single-dig.

## 2026-06-26 CopperCliff SHIP: MDG in_edges(keys,data=<attr>) 0.16x->0.40x — pristine single-pass borrowed-attr fast path

The biggest official core_laggards gap = mdg in_edges(keys=True, data="weight", default=0) at 0.162x.
ROOT: _native_mdg_in_edges_data_key (digraph.rs) built an owned Vec<(String,String,usize)> triples list (2
String clones PER EDGE) then re-looked-up each attr via edge_data_value_or_default (per-edge edge_key build +
mirror probe + store re-lookup). FIX: when the edge mirror is PRISTINE (edge_py_attrs.is_empty(), the common
add_edge-built case), a single pred-major borrowed pass reads the attr straight from the borrowed AttrMap
(self.inner.edge_attrs(s,t,key).get(attr)) -> no String clones, no edge_key, no mirror probe, no re-lookup.
RESULT: 0.162x -> 0.402x (2.5x self) for keys+data; in_edges(data) 0.49x; byte-IDENTICAL to nx (==nx keys+data
& data), held-ref-mutated graphs fall through to the general mirror path (verified ==nx), in_edges conformance
GREEN (1362 passed). Still <nx (substrate floor = N tuple + cgse_value_to_py PyObject creations, shared with
edges() 0.74x) but a 2.5x improvement on the suite's #1 laggard. PRE-EXISTING UNRELATED red test flagged:
test_review_mode_regression_lock::test_write_gexf_classified_as_py_wrapper_not_nx_delegated (readwrite/gexf
classification; my Rust digraph.rs change cannot affect a Python-wrapper classification -> not mine, needs
separate investigation). 19th perf ship.

## 2026-06-27 CopperCliff NEGATIVE: DiGraph in_edges(data=str) store-read ~0-gain (already near floor; REVERTED)

Tried the MDG in_edges win's lever on the DiGraph sibling (in_edges(data='weight') 0.548x): a !edges_dirty
store-read fast path (edge_attrs() index-keyed lookup, no Self::edge_key String-tuple build + no mirror hash
probe). BYTE-EXACT (==nx incl default + missing-attr; held-ref falls to mirror, ==nx) but ~0-GAIN: 0.548x ->
0.575x. ROOT: unlike _native_mdg_in_edges_data_key (which built an owned (String,String,usize) triples Vec +
re-looked-up via edge_data_value_or_default = the 2.5x overhead I removed), the DiGraph _native_in_edges_data
_key was ALREADY single-pass with a direct mirror probe. Swapping the mirror probe (2 String clones + str-key
hash) for the store read (2 nodes.get_index_of + (usize,usize) hash) is ~equal cost -- get_index_of(&str) is
itself a hash+probe. So DiGraph in_edges is already near its substrate floor (tuple + cgse_value_to_py +
py_node_key + one per-edge lookup, mirror or store). REVERTED (kept the committed MDG win). LESSON: the MDG
in_edges 2.5x came specifically from the redundant triples-Vec + re-lookup pattern; siblings without that
pattern (DiGraph in_edges, and selfloop_edges which already has the pristine fast path) are already near-floor.
The biggest remaining MDG-only avoidable-overhead gaps are mined. 19 perf + 1 correctness ship; main green.

## 2026-06-27 CopperCliff mdg_in_degree_weight is floored (store_int fires; per-node tuple floor) — degree-family overhead mined

Applied the "dig deeper for avoidable overhead" lesson to mdg_in_degree_weight 0.536x (bench core_laggards).
Traced: in_degree(weight) -> native_weighted_directional_degree -> tries native_weighted_directional_degree_
store_int FIRST, gated only on `!edges_dirty`. A fresh add_edge MDG has edges_dirty=False, so the RUST-STORE
fast path FIRES (weighted_degree_store_int_row reads the CgseValue store, ZERO per-edge PyO3 -- no String
edge_key, no mirror get_item). So 0.536x is NOT avoidable overhead: it is the per-node (node, deg) tuple
materialization floor (n=700 -> 700 py_node_key + i64->PyObject + 2-tuple), matching the memory note that the
floor is the PyObject view build, not the edge lookup. UNLIKE in_edges(data=key) (which had a redundant
triples-Vec + edge_data_value_or_default re-lookup = the 2.5x I removed last turn), in_degree has NO such
avoidable layer -- the store fast path is already in place. CONCLUSION: the degree/in_edges-family avoidable-
overhead vein is MINED -- in_edges(data=key) won (0.16x->0.40x), and in_degree_weight / DiGraph in_edges /
selfloop are all at their substrate floor (per-node/per-edge PyObject materialization), store/pristine fast
paths already applied. Remaining gaps are the genuine Rust-PyObject-build floor. 19 perf + 1 correctness ship;
main green.

## 2026-06-27 CopperCliff SHIP: Graph.to_directed(scalar attrs) 0.645x->0.782x — edges_ordered_borrowed (kill snapshot+double clones)

Dug the construction_copy bench gap (Graph.to_directed() with scalar node+edge attrs, 0.645x) for avoidable
overhead (in_edges lesson). FOUND: PyGraph::to_directed's edge loop used edges_ordered() (allocates a per-edge
EdgeSnapshot with OWNED left/right Strings + a cloned AttrMap) THEN `edge.attrs.clone()` THEN
`rust_attrs.clone()` for the forward edge = 2 wasted String clones + 1 wasted AttrMap clone PER EDGE. FIX:
iterate edges_ordered_borrowed() (borrowed &str + &AttrMap, no snapshot) and clone the borrowed AttrMap once
per direction; the mirror edge_key probe runs only when the edge mirror is non-pristine. RESULT: 0.645x ->
0.782x (1.2x self), BYTE-IDENTICAL (==nx edges + node-attrs + edge-attrs; edge-dict identity preserved;
unweighted ==nx), conformance GREEN (5388 to_directed/copy/convert tests). Still <nx (the 2 directed edges +
2 AttrMap copies + node-mirror crossing are the real construction floor) but a genuine 1.2x on the bench gap.
LEVER (generalizes the in_edges/size finding): construction/view kernels using edges_ordered() (snapshot)
where edges_ordered_borrowed() suffices pay needless per-edge String+AttrMap clones -- audit other
edges_ordered() callers. 20th perf ship.

## 2026-06-27 CopperCliff edges_ordered_borrowed lever is SIMPLE-GRAPH-ONLY (multi dedup-HashSet) + conversion-family map

Audited the to_directed/to_undirected/copy family after the Graph.to_directed win (edges_ordered_borrowed,
0.65x->0.78x). Measured gaps: DiGraph.to_directed 0.58x, MultiDiGraph.to_directed 0.65x, MultiDiGraph.copy
0.69x, DiGraph.to_undirected 0.59x, MultiDiGraph.to_undirected 0.57x.
- MultiDiGraph.to_undirected: applied edges_ordered_borrowed -> REGRESSED 0.57x->0.455x. ROOT: for MULTI
  graphs edges_ordered_borrowed allocates a dedup HashSet (it de-dups the both-direction adjacency walk),
  so it is SLOWER than edges_ordered()'s snapshot. The borrowed lever is SIMPLE-GRAPH/DIGRAPH-ONLY (their
  edges_ordered_borrowed is a dedup-free succ-major Vec). REVERTED.
- DiGraph.to_directed (0.58x) = self.copy() -- copy path (inner clone + mirror), NOT an edges_ordered
  edge-duplication loop; borrowed lever N/A.
- DiGraph.to_undirected (0.59x) = _native_to_undirected_deepcopy: walks nodes_ordered->successors (no
  snapshot) and DEEPCOPYs each edge attr dict (inherent, matches nx's deepcopy default); deepcopy is the
  floor, only ~2 redundant mirror-key String clones/edge avoidable (marginal, deepcopy dominates).
CONCLUSION: the edges_ordered_borrowed snapshot lever cleanly applies ONLY to simple-graph SHALLOW
edge-duplication loops (Graph.to_directed, shipped). The multi conversions are dedup-HashSet-bound and the
DiGraph conversions are copy/deepcopy-bound -- different floors, not this lever. 20 perf + 1 correctness ship.

## 2026-06-27 CopperCliff conversion/copy/subgraph family audit — borrowed lever mined; remaining floors mapped

Comprehensive audit of the construction/conversion family after the Graph.to_directed win (edges_ordered_
borrowed, simple-graph shallow). Measured + root-caused:
- MultiGraph/MultiDiGraph.copy 0.69-0.76x: _native_copy CLONEs the inner wholesale (O(E) AttrMap clones in
  the Rust store) + reorders pred rows; the Python mirror clone is FREE (pristine/empty for add_edge graphs).
  Inner-clone-bound vs nx's per-dict shallow copy -- substrate, no avoidable layer.
- DiGraph.reverse 1.47x, reverse(copy=False) 1.63x: WIN (already optimized).
- DiGraph.subgraph.copy 0.93x: near-parity.
- DiGraph.edge_subgraph 0.699x: Graph/DiGraph.edge_subgraph routes to the Python top-level edge_subgraph which
  returns a VIEW (nx semantics); the native edge_subgraph methods (return a COPY) are intentionally bypassed
  (view != copy) -- can't route to native without breaking semantics. View-construction-bound.
- Remaining edges_ordered() callers in lib.rs are all PyMultiGraph (borrowed = dedup-HashSet slower) or niche
  (broadcast_edge_attribute). No clean simple-graph snapshot-waste caller left.
CONCLUSION: the edges_ordered_borrowed snapshot lever's clean applications are MINED -- Graph.to_directed
(shipped) was the one simple-graph shallow edge-dup loop. The rest of the conversion/copy/subgraph family is
inner-clone / deepcopy / dedup-HashSet / view-construction bound (genuine floors, not avoidable overhead).
20 perf + 1 correctness ship; main green.

## 2026-06-27 CopperCliff fresh-domain sweep (euler/graphical/covering/wiener/chains/distance) all wins; selfloop opportunity noted

Swept domains not before benched this session: ALL wins/parity -- is_eulerian 14.7x, eulerian_circuit 9.7x,
has_eulerian_path 1.27x, is_graphical 1.24x, is_valid_degree_sequence_erdos_gallai 1.34x, wiener_index 9.0x,
chain_decomposition 7.9x, diameter 9.0x, center 8.5x, is_dominating_set 4.8x, is_regular 4.2x, density 114x;
near-parity min_edge_cover 0.93x, dominating_set 0.84x. NO new <0.7x takeable gap.
BIGGEST remaining bench gap after the in_edges/to_directed wins = mg_selfloop_keys_weight 0.325x. Its native
_native_selfloop_edges (lib.rs) ALREADY has the pristine-mirror store-read value fast path; the residual
avoidable overhead is the NODE COLLECTION: a Vec<String> of selfloop nodes built via a has_edge(n,n) scan over
ALL nodes (2500 probes) + to_owned() clones (2502), then re-fetched via edge_keys in the loop. A borrowed
fast-path branch (iterate nodes_ordered() + edge_keys(n,n) as the selfloop check, no has_edge scan, no owned
Vec) could give ~1.4x self (0.325x->~0.45x) BUT requires duplicating the value branch (the want_dict path
needs &mut self -> owned nodes) and carefully preserving the Map-value mirror-identity fallback -- moderate
complexity + Map-identity risk for a sub-ms workload. Deferred as a focused future attempt. 20 perf + 1
correctness ship; main green.

## 2026-06-27 CopperCliff SHIP: selfloop_edges(keys,data=<attr>) 0.325x->0.418x — single-pass node+keys collection

The biggest remaining bench gap (mg_selfloop_keys_weight 0.325x). _native_selfloop_edges (lib.rs) already had
the pristine-mirror store-read value fast path; the residual avoidable overhead was the NODE COLLECTION: a
separate has_edge(n,n) scan over ALL nodes (redundant edge_pair_key + edges.get per node) to build a
Vec<String>, THEN a per-loop-node edge_keys(n,n) re-fetch. FIX: collect (selfloop node, its keys) in ONE pass
via edge_keys(n,n) -- which is BOTH the self-loop test (None for non-loop nodes via filter_map `?`) AND the
keys needed in the loop -- eliminating the has_edge scan + the in-loop re-fetch. Node order + owned collection
(releases the self.inner borrow before the &mut want_dict path) preserved; value/Map logic UNTOUCHED (safe).
RESULT: 0.325x -> 0.418x (1.29x self), BYTE-IDENTICAL (==nx for keys+data, data=True, no-keys, plain),
conformance GREEN (779 selfloop tests). Still <nx (the per-edge 4-tuple + cgse_value_to_py PyObject floor) but
a real 1.29x on the suite's #1 remaining laggard. 21st perf ship.

## 2026-06-27 CopperCliff SHIP: MDG out_edges(nbunch, keys, data=<attr>) 0.34x->0.57x — native keys support + pristine store-read

Edge-view matrix sweep found MDG.out_edges(nbunch, keys=True, data="weight") at 0.336x -- it fell to the slow
Python view because the wrapper gated _native_mdg_out_edges_nbunch_data_key on `not keys` (the native built a
3-tuple, no key). FIX: (1) add a `keys: bool` param to the native -> build the 4-tuple (node, nbr, key, value)
when keys; (2) PRISTINE store-read fast path -- when the edge mirror is empty read the attr straight from the
store (edge_attrs) instead of edge_data_value_or_default's edge_key build + mirror probe + re-lookup; (3) route
keys=True through it (drop the `not keys` gate in both the out_edges wrapper + the edges() view path; update
both callers to pass keys). RESULT: 0.336x -> 0.567x (1.7x self), BYTE-IDENTICAL (==nx for keys+data, no-keys
data 1.13x, dups/missing nbunch, data=True keys unchanged, missing-attr default), conformance GREEN (1158
out_edges + 630 graph_utilities). NOTE: the bench's mdg_out_edges_nbunch_keys_data uses data=True (the fast
2.03x dict path); the data=<attr> (specific-attr) keys form was the uncovered gap. 22nd perf ship.

## 2026-06-27 CopperCliff SHIP x2: MDG in_edges + MG edges (nbunch,keys,data=<attr>) pristine store-read

Continuing the edge-view matrix sweep (siblings of the out_edges nbunch data_key win): MDG.in_edges(nbunch,
keys,data="weight") 0.372x and MG.edges(nbunch,keys,data="weight") 0.313x. Both natives already had keys
support + were routed (not Python-fallback), so the cost was edge_data_value_or_default(_with_key)'s per-edge
edge_key build + mirror probe + re-lookup. FIX (same pristine store-read as out_edges): when the edge mirror is
empty, read the attr straight from the store (inner.edge_attrs(...).get(attr)) instead of the mirror helper.
RESULTS: MDG.in_edges 0.372x->0.814x (2.2x self); MG.edges 0.313x->0.822x (2.6x self); BYTE-IDENTICAL (==nx
keys+data, no-keys, default), conformance GREEN (3422 view tests). (Build hit E0514 worker-rustc dep-cache
inconsistency -> fixed with full `cargo clean && cargo build`.) 23rd+24th perf ships. The nbunch+keys+data=<attr>
edge-view family across MDG out/in + MG edges is now pristine-store-read across the board.

## 2026-06-27 CopperCliff SHIP: DiGraph in_edges(nbunch, data=<attr>) 0.32x->0.65x — new index-native data_key kernel

Edge-view matrix sweep: DiGraph.in_edges(nbunch, data="weight") was 0.32x because there was NO native data_key
path for it (the wrapper's iterable-nbunch in_edges routed data=False/True to natives but data=<attr> fell to
the Python pred[target].items() walk). FIX: added _native_in_edges_nbunch_data_key -- the pred-major sibling of
_native_out_edges_nbunch_data_key, index-native (edge_attrs_by_indices store read, cached node-key vec, no
String edge_key) when edges are clean + data is a plain str; Map values + dirty/non-str fall to the mirror
path. Wired the in_edges wrapper's else-branch to route data=<attr> -> native(nbunch, data, default). RESULT:
0.32x -> 0.65x (2.0x self), BYTE-IDENTICAL (==nx for data, missing-attr default, dict-valued attr/Map branch,
post-mutation/dirty path), conformance GREEN (3007 in_edges/digraph view tests). Sibling DiGraph out_edges
data_key was ALREADY index-native (0.688x = pure PyObject tuple floor). 25th perf ship.

## 2026-06-27 CopperCliff REVERTED a571d20d6 (degree index-native = host-noise false win)

a571d20d6 ("Graph.degree(nbunch,weight) 0.239x->0.404x index-native store-int") was a HOST-NOISE false win,
now reverted (e180327a2). CONTROLLED same-build A/B (identical structure+weights; pristine graph = index-native
gate HIT vs held-ref-dirty graph = original PyList+builtins.sum path; interleaved min-of-15 x5): index-native
7.98ms vs PyList+sum 6.98ms = 0.87x -- the index-native is ~13% SLOWER. builtins.sum over a PyList is
C-optimized and beats a per-edge Rust i64 checked_add + into_py_any(PyInt) once the per-node
node_key_to_string + get_node_index + result-tuple build (the floor nx never pays) dominates. The DiGraph
sibling (successors/predecessors_indices) measured the SAME ~0-gain and was never committed. degree(nbunch,
weight) across ALL types is SUBSTRATE-BOUND -- DO NOT re-attempt index-native store-int. LESSON (re-confirmed):
few-shot perf sweeps LIE under host noise; a degree/view micro-opt needs a same-build A/B (gate-hit vs
gate-skip) with interleaved min-of-N BEFORE shipping.

## 2026-06-27 CopperCliff RIGOROUS MEASURE: neighbors/adjacency views ~0.43-0.56x = substrate-bound (eager materialization vs nx lazy keys-iterator)

Using disciplined interleaved min-of-10 x5-trials (median + tight range = low noise, post the a571d20d6 noise
burn): G.neighbors 0.536x [0.515,0.551], DG.successors 0.547x, DG.predecessors 0.558x, G.adj[n] iterate 0.425x,
G[n] getitem 1.174x (win). The neighbors/adjacency family is a REAL, consistent gap on HOT functions.
MECHANISM (why it's substrate, not avoidable overhead): nx's G.neighbors(n) returns iter(self._adj[n]) -- a
LAZY dict_keyiterator whose elements are the node-key objects already living in the adjacency dict (zero
materialization until consumed, no per-neighbor work). fnx's neighbors builds an EAGER Vec<PyObject>, resolving
each neighbor via py_adj_key -> py_node_key (a String-keyed node_key_map lookup + clone_ref) per neighbor.
ASSESSED + REJECTED the "index-native" lever (neighbors_indices + cached node-key tuple by index): the
per-neighbor String-hash vs PyTuple_GetItem is a WASH, and the dominant cost (clone_ref materialization of a
fresh list vs nx's lazy keys view) is unavoidable without returning a LAZY neighbor iterator -- an architectural
change to the view layer, not a kernel micro-opt. So neighbors/adjacency is substrate-bound at ~0.5x; the only
real lever is lazy adjacency-key iterators (deferred, architectural). DO NOT chase a kernel/index micro-opt here.

## 2026-06-27 CopperCliff RA/AA link-pred 0.59x = neighbors-materialization substrate (degree-batch REGRESSED, reverted)

Rigorous (interleaved min-of-8 x5): resource_allocation_index 0.589x [0.578,0.596] and adamic_adar_index 0.597x
both lag their sibling jaccard_coefficient (0.902x). They share _link_prediction_compute; the difference is
RA/AA score = sum(1/deg(w) for w in common neighbors) while jaccard = C set-ops. HYPOTHESIS (deg lookup is the
cost) -> TESTED: batched the endpoints'-neighborhood degrees for explicit ebunches -> REGRESSED to 0.48x (for
RANDOM pairs common neighbors are sparse, so the lazy deg() path only touches a few nodes; batching all
endpoint neighborhoods computes a huge unused superset). REVERTED. ROOT CAUSE: nx's RA iterates `for w in
nx.common_neighbors(G,u,v)` over `G[u]` (a lazy dict view); fnx mirrors the exact algorithm but `nbr_order(u) =
list(G.neighbors(u))` EAGERLY materializes the neighbor list (the same 0.54x neighbors-materialization substrate
documented above). The deg() lazy memo is already optimal for sparse-common-neighbor ebunches. So RA/AA is
neighbors-materialization-bound, NOT degree-bound -- same substrate floor as neighbors/adjacency; no kernel
lever. (PA + jaccard already at/above parity for their access patterns.) LESSON: confirm WHICH sub-op dominates
(profile/bisect) before batching -- batching the wrong quantity regresses.

## 2026-06-27 CopperCliff SHIP: RA/AA link-pred (explicit ebunch, simple Graph) 0.59x->1.1x — native common-neighbor degrees + Python sum

The neighbors-materialization substrate (documented above) was BYPASSED for RA/adamic_adar by splitting the
work: a new native binding link_pred_common_neighbor_degrees returns, per pair, the DEGREES of common
neighbors {w in N(u): w in N(v), w!=u,v} in nx's exact G[u] adjacency order (index-native:
neighbors_indices + lazy inner.degree cache, no eager list(G.neighbors(u)) PyObject materialization); the
Python wrapper then does sum(1/d) (RA) / sum(1/log(d)) (AA) so EVERY float op happens in Python ->
parity GUARANTEED (no Rust-vs-CPython Neumaier/log ULP risk). The pre-existing native _raw_resource_allocation
kernel was 2.7x faster than nx but 1-ULP off (naive f64 sum + larger-row order) -> unusable; this split keeps
its speed with exact parity. Gated: explicit ebunch + type(G) is Graph (default non_edges order + directed/
multi stay on the Python path); returns a generator (type-match); validation stays in Python (error contract).
RESULTS (interleaved min-of-8 x5, tight): RA 0.589x->1.129x, AA 0.597x->1.100x (both BEAT nx), high-degree-
endpoint pairs 1.508x. GOLDEN CORPUS 24/24 byte-exact (BA/WS/gnp/tree + selfloops x RA/AA x 60 pairs); default
ebunch ==nx; conformance GREEN (1315 link-pred tests). LEVER (generalizes): when an algo's float-sum parity
blocks a fast native kernel, return the native-computed TERMS/operands and do the final reduction in Python --
native speed + guaranteed float parity. 26th perf ship.

## 2026-06-27 CopperCliff community link-pred (cn/ra_index/within_inter soundarajan_hopcroft) hybrid native REGRESSED, reverted

Tried extending the RA/AA hybrid lever (native common neighbors + Python reduce, shipped face2f4f5) to the
COMMUNITY link-pred functions: cn_soundarajan_hopcroft (0.710x), ra_index_soundarajan_hopcroft (0.595x),
within_inter_cluster (0.633x). Added link_pred_common_neighbors_full returning per-pair common neighbors as
(node_obj, degree) so Python could look up each common neighbor's community attr. GOLDEN CORPUS 36/36 byte-exact
(incl. selfloops + communities), conformance GREEN (1857). BUT MEASURED REGRESSION: ra_index 0.595x->0.367x,
within_inter 0.633x->0.356x (cn only 0.710x->0.804x). ROOT CAUSE: unlike RA/AA (degree-only -> native returns
i64 degrees, zero per-occurrence PyObjects), the community metrics need each common neighbor's COMMUNITY ATTR
(G.nodes[w][community]) -- inherently per-node Python attr access the native can't cheaply provide. Returning
the common-neighbor OBJECT per OCCURRENCE (same node repeats across pairs) adds py_node_key materialization the
degree-only path avoided, AND Python still does G.nodes[w] per common. So community link-pred is
COMMUNITY-ACCESS-bound, not common-neighbor-finding-bound -- the hybrid lever does NOT transfer. REVERTED.
LESSON: the native-operands+Python-reduce lever wins only when the native can return CHEAP scalar operands
(degrees/counts as ints); when the reduce needs per-element Python OBJECT attrs, returning objects per
occurrence regresses. RA/AA win stands.

## 2026-06-27 CopperCliff SHIP: jaccard_coefficient (explicit ebunch, simple Graph) 0.94x->2.80x — native counts + Python division

Completes the scalar-operand hybrid lever across the link-pred family (after RA/AA face2f4f5; community variants
REVERTED as object-attr-bound). New native link_pred_jaccard_counts returns per pair (common_count, union_size)
computed INDEX-NATIVE: common = |{w in N(u): w in N(v), w!=u,v}|, union = |N(u)|+|N(v)|-|N(u) cap N(v)| =
|set(G[u])|set(G[v])| (nx's denominator). The Python wrapper does common/union (one int-division -> exact
parity) or int 0 when union==0 -- no eager set(G[u])|set(G[v]) materialization (the 0.94x cost). RESULT: 0.94x
-> 2.796x (tight [2.76,2.80], 3x self, BEATS nx), GOLDEN CORPUS 12/12 byte-exact (BA/WS/gnp + selfloops),
default ebunch ==nx, conformance GREEN (1182). CONFIRMS the lever boundary: cheap SCALAR operands (counts, like
RA/AA degrees) -> native+Python-reduce WINS; per-element OBJECT attrs (community) -> regresses. Link-pred family
now: RA/AA/jaccard native-fast (explicit ebunch), PA at parity, community delegated (object-attr-bound), default
ebunch set-order-blocked. 27th perf ship.

## 2026-06-27 CopperCliff frontier sweep: structural-holes/core/centrality/bipartite all at-or-above nx — no new single-fn gap

Post-jaccard, swept for the next gap across domains not recently checked. ALL at-or-above nx:
- structural holes: effective_size 5.4x, constraint 5.7x, local_constraint 5.3x (memory's chq2a has_edge-tax
  item RESOLVED).
- core: k_core 37.5x, k_shell 28.8x, core_number 11.6x, onion_layers 5.5x (memory's 0ysvh RESOLVED).
- centrality: pagerank 12.6x, load 32.8x, katz_numpy 1.74x, voterank 1.95x, hits 1.28x, second_order
  centrality ~3850x (fnx 0.003s vs nx 11.57s @n=150 -- nx is O(n^3)+, not a fnx hang).
- bipartite density 18x / spectral_bipartivity 1461x; tournament is_tournament 7x; transitivity 140x; triangles
  4x; square_clustering 17x; weisfeiler_lehman_graph_hash 1.5x; is_chordal 2.5x.
NEAR-PARITY (not gaps, substrate/LAPACK): subgraph_centrality 0.767x (dense eigh), hits 1.28x (iterative).
CONCLUSION: the single-function vs-nx frontier is comprehensively mined (27 perf ships). Remaining sub-1.0x
are substrate-bound (eager view materialization, Python-node->String-key tax, dense LAPACK) or parity-blocked
(set-order default ebunches). The productive vein remains the native-scalar-operands + Python-reduce hybrid
(mined across link-pred: RA/AA/jaccard) and architectural work (lazy view layer / integer-node-index cache).

## 2026-06-27 CopperCliff substrate view-materialization gaps RESOLVED — memory's "core remaining frontier" is outdated

Re-measured WARM (min-of-6 x4) the view-materialization substrate that earlier memory flagged as the ONLY real
remaining gaps (dict(adjacency()) 0.19x, nodes(data=attr) 0.20x): ALL resolved -- dict(G.adjacency()) 1.045x,
nodes(data=True) 0.993x, list(edges(data=True)) 1.295x, to_dict_of_dicts 1.393x, to_dict_of_lists 2.073x (the
adjacency outer-dict cache + node_data_mirror + edges-data cache all landed). The ONLY residual sub-1.0x here is
dict(G.adj) 0.704x -- the .adj AdjacencyView outer materialization creates N inner AtlasView objects (genuine
view-object substrate, distinct from adjacency()'s cached path; marginal + delicate inner-view structure, not
pursued). Also re-confirmed less-common fns at-or-above nx: kemeny 2.1x, effective_graph_resistance 1.8x,
estrada 54x, flow_hierarchy 174x, is_distance_regular 29x, tree_broadcast_time 4.2x; near-parity
number_of_cliques 0.86x (find_cliques set-order) + attribute_mixing_dict 0.887x (object-attr-bound, like the
community link-pred). CONCLUSION: the per-function vs-nx surface is comprehensively at-or-above nx; the
substrate-frontier thesis in older memory is OUTDATED -- those gaps are fixed.

## 2026-06-27 CopperCliff weighted-variant sweep clean + dict(G.adj) 0.704x = view-object substrate (frontier exhausted)

Last unchecked dimension — WEIGHTED algorithm variants — all at-or-above nx: clustering(weight) 2.47x,
average_clustering(weight) 2.51x, betweenness(weight) 15.7x, closeness(distance) 3.62x, pagerank(weight) 2.39x,
degree_assortativity(weight) 6.59x, floyd_warshall 1.55x; near-parity eigenvector(weight) 1.10x,
average_neighbor_degree(weight) 1.01x, minimum_spanning_tree(weight) 0.890x (construction-tax residual).
DIAGNOSED the biggest remaining view residual dict(G.adj) 0.704x: AdjacencyView.__getitem__ builds a per-node
AtlasView wrapping the Rust row (N constructions) + __iter__ dict.fromkeys(atlas); nx builds N lightweight
Python AtlasViews over its _adj dict. A native bulk path can't avoid the N Python view-object constructions
(the cost) -> genuine view-object substrate, NOT cleanly fixable; marginal. CONCLUSION (consolidated across this
session's sweeps: link-pred, structural-holes, core, centrality, bipartite, tournament, less-common, substrate
views, weighted): the per-function vs-nx surface is COMPREHENSIVELY at-or-above nx. Every residual sub-1.0x is
substrate-bound (view-object/eager-materialization/Python-node->String-key/dense-LAPACK) or parity-blocked
(CPython set-order). Single-dig kernel frontier EXHAUSTED; remaining productive work is architectural
(lazy view layer / integer-node-index cache) — multi-session, not a 60-min dig.

## 2026-06-27 CopperCliff SHIP x2: Graph + DiGraph clear_edges 0.05x/0.003x -> in-place (40-275x self, unweighted Graph BEATS nx)

Re-measuring the bench laggards (the source of truth) caught two CATASTROPHIC clear_edges gaps the per-function
sweeps missed (they're mutators, not in the read-only sweeps):
- SIMPLE Graph.clear_edges 0.048-0.057x (20x slower): the binding REBUILT a fresh inner via a per-node
  add_node_with_attrs loop (ledger record_decision tax + node-attr clone + old-inner drop).
- DiGraph.clear_edges 0.003-0.011x (up to 330x slower): the binding collected edge_py_attrs.keys() then
  remove_edge per edge -- each an O(degree) adj-row retain => O(E*degree) (~240ms on 15k edges). ALSO a latent
  CORRECTNESS BUG: keyed off the mirror, so a pristine add_edge graph (empty edge_py_attrs) had its store edges
  NOT cleared.
FIX: added in-place clear_edges to fnx-classes Graph + DiGraph (edges.clear() + adj/succ/pred index rows
clear() + revision bump; sibling of the existing MultiGraph/MultiDiGraph in-place clears) and routed both
bindings to it. RESULTS: Graph weighted 0.057x->0.236x, Graph UNWEIGHTED 0.048x->11.94x (BEATS nx 12x -- empty
AttrMaps + Vec row clear keeps capacity = near-free); DiGraph weighted 0.011x->0.428x, DiGraph unweighted
0.003x->0.508x (240ms->2.3ms). BYTE-EXACT (nodes/attrs kept, edges empty, re-add ==nx, pristine clear now
empties), conformance GREEN (3387). Weighted residual = AttrMap dealloc (inherent). 28th+29th perf ship.
LESSON: MUTATOR functions (clear_edges, remove_*) are invisible to read-only perf sweeps -- the bench laggard
list is the source of truth; re-measure it even when single-function sweeps look exhausted.

## 2026-06-27 CopperCliff mutator-surface audit: remove_edges_from is the next bulk-retain target; remove_nodes_from already bulk; clear/remove_node substrate

Following the clear_edges wins (50d0f4074), swept the MUTATOR surface (invisible to read-only sweeps). Measured
gaps (build-fresh-then-time-op, interleaved): Graph.remove_edges_from(4000) 0.269x, Graph.remove_nodes_from(500)
0.194x, DiGraph.remove_edges_from 0.304x, DiGraph.remove_nodes_from 0.421x, Graph.remove_node(single) 0.020x
(50x!), Graph.clear 0.045x (31ms vs 1.4ms).
TRIAGE:
- remove_nodes_from (Graph): the binding (lib.rs:9333, impl PyGraph) ALREADY calls the bulk
  inner.remove_nodes_from (single retain + single index repair). The 0.194x residual is SUBSTRATE -- the
  integer adj_indices re-index after a shift_remove of order-preserving node removal (nx dict = O(sum degrees),
  fnx = O(V+E)). NOT a binding gap. (Attempted a redundant "bulk" edit on PyMultiGraph by mistake -> MultiGraph
  inner lacks remove_nodes_from -> E0599; reverted.)
- Graph.clear 0.045x + remove_node(single) 0.020x: SUBSTRATE -- clear rebuilds+drops the whole inner (O(N+E)
  eager dealloc); single remove_node pays the full O(V+E) shift_remove index repair (order-preserving integer
  index). Not single-dig fixable without an index-stability redesign.
- remove_edges_from 0.269x: TRACTABLE NEXT -- the binding (lib.rs:7818) loops `self.remove_edge` per edge, each
  an O(degree) adj_indices retain -> O(k*degree). LEVER: a native Graph::remove_edges bulk (one shared keep-mask
  retain over edges + parallel edge_index_endpoints, then ONE grouped retain per affected adj row), modelled on
  the existing remove_node 1b retain pass. Add to fnx-classes Graph (+ DiGraph), route the bindings. Clean
  next-turn win (the clear_edges/remove_nodes bulk-retain lever).
LESSON (reinforced): verify the binding actually loops before "fixing" -- remove_nodes_from already had the bulk.

## 2026-06-27 CopperCliff remove_edges_from bulk-retain = ~0-gain (REVERTED) — per-edge swap_remove+String-hash is the floor

Implemented the teed-up bulk lever: native Graph::remove_edges (swap_remove each edge O(1), keep
edge_index_endpoints parallel, collect neighbor pairs per node, then retain EACH affected adj row ONCE) +
routed the binding (collect (u,v) pairs + mirror cleanup, then one inner.remove_edges). BYTE-EXACT (==nx incl
selfloops/missing/dups, neighbors intact, re-add works). But MEASURED ~0-gain/REGRESSION: remove_edges_from(4000)
0.269x -> 0.236x (fnx 1.82ms -> 2.24ms, SLOWER). WHY: the per-edge cost is dominated by swap_remove_full
(HashMap) + edge_pair_key (2 get_index_of String hashes) -- both UNAVOIDABLE and NOT batched. The only batched
part (the 2 adj_indices retains) is a small fraction, and for RANDOM edges each node has only ~5 removed edges
so the per-node retain-batching saves little; meanwhile the bulk ADDED a Vec<(String,String)> collection (~8000
allocs) + a per_node HashMap<HashSet> that offset it. REVERTED both. CONCLUSION: remove_edges_from is
substrate-bound (per-edge swap_remove + String-key hash), like remove_nodes_from (already bulk) + remove_node
(index repair) + clear (dealloc). clear_edges (shipped 50d0f4074) was the ONE mutator win because clearing ALL
edges = one edges.clear()+row.clear() (no per-edge hashing). The mutator vein is now MINED. LESSON: batching
only wins when the batched op dominates AND the batch setup is cheaper than what it saves.

## 2026-06-27 CopperCliff FINDING: add_edges_from(dict attrs) leaves Rust store stale -> size/degree/wiener(weight) WRONG (correctness bug); add_weighted perf-batch reverted

Dug construction gaps; found add_weighted_edges_from 0.135x (7x slow: per-edge add_edge PyO3 loop) + from_edgelist
0.593x. Tried routing add_weighted to add_edges_from((u,v,{weight:w})) EXACTLY as nx -> 0.135x->1.13x, BYTE-EXACT
on edges(data) across all 4 types + **attr + error contract. BUT it REGRESSED the wiener_index conformance test.
ROOT CAUSE (a pre-existing LATENT CORRECTNESS BUG, exposed not caused by the perf change): building a weighted
graph via add_edges_from((u,v,{'weight':w})) stores the weights in the Python MIRROR (edge_py_attrs) but leaves
the Rust STORE without them (and apparently without a dirty flag that _sync_rust_edge_attrs honors -- calling it
did NOT fix wiener). Native weighted kernels that read the STORE then return WRONG results:
  - n=5 directed-complete weighted via add_edges_from(dict): size(weight) fnx=20 vs nx=71; in_degree(0,weight)
    fnx=4 vs nx=19; wiener_index fnx=20 vs nx=58. (fnx reads UNIT weights = the store had none.)
  - dijkstra_path_length / shortest_path_length(weight): CORRECT (they sync/read properly).
  - edges(data='weight'): CORRECT (reads the mirror).
The OLD add_weighted (add_edge(weight=w) per edge -> writes the STORE directly) AVOIDS the bug -> REVERTED to it.
SCOPE: any graph built via add_edges_from(dict attrs) (a common nx pattern) then queried by size(weight) /
*_degree(weight) / wiener_index gives silently-wrong results. dijkstra-family is fine. NEEDS a dedicated
correctness fix (the store-reading weighted kernels must sync the mirror first, like dijkstra; or add_edges_from
must mark edges_dirty so the existing sync path fires). HIGH PRIORITY -- separate from perf. add_weighted stays
on the correct per-edge path (0.135x) until the store-sync bug is fixed (then it can batch + win).

## 2026-06-27 CopperCliff CORRECTION (supersedes 0e30e44a5): the bug is NARROW — add_edges_from(dict)+weighted wiener_index only; size/degree FINE

CLEAN-BUILD verification (the 0e30e44a5 entry was measured on an INCONSISTENT .so during a failed remove_edges
build + reverts/touches -> it OVER-CLAIMED size/degree wrong). On a fresh `cargo clean` build of HEAD, the
ACCURATE finding:
- add_edges_from((u,v,{'weight':w})) BATCH (large input) leaves the weights MIRROR-ONLY (store stale).
- size(weight) 71==71, in/out_degree(weight) 19/14 match, edges(data='weight') matches, dijkstra/shortest_path
  match -- ALL CORRECT (these are mirror-aware: degree checks edges_dirty -> reads the mirror).
- ONLY weighted wiener_index is WRONG (n=5 directed-complete via add_edges_from(dict): fnx 20 vs nx 58),
  because its weighted path builds weighted_adj from `G.adjacency()` (lib.rs:12973), and adjacency()'s per-edge
  attrs read the STALE STORE for batch-built graphs. Neither _sync_rust_edge_attrs NOR _fnx_sync_attrs_to_inner
  flushes it; only a `list(G.edges(data=True))` materialization makes a subsequent adjacency() correct (deep
  mirror/store side-effect, root in the Rust adjacency binding -- not safely fixable this turn).
- The wiener CONFORMANCE suite PASSES (54) because its builders use add_weighted_edges_from = per-edge
  add_edge -> writes the STORE -> correct. So the bug is unreached by current tests.
NET: NARROW pre-existing bug (weighted wiener_index over an add_edges_from(dict)-built graph). add_weighted
perf-batch (routing to add_edges_from) is BLOCKED by it (would make wiener stale) -> add_weighted STAYS on the
correct per-edge path (0.135x). A proper fix = make adjacency() mirror-aware (like edges-data/degree) OR have
the weighted wiener build weighted_adj from edges(data) [order-care for float-sum parity]. Dedicated follow-up.
LESSON (hard-won this turn): NEVER measure correctness/perf on an inconsistent .so -- a failed build + reverts +
touch left a Frankenstein .so that produced contradictory results (size wrong then right, edges-data None then
correct). Always `cargo clean` rebuild to ground truth before drawing conclusions.

## 2026-06-27 CopperCliff SHIP: from_edgelist / add_edges_from(empty graph) 0.72x->1.14x — skip the O(E) has_edge pre-scan on empty graphs

(Re-measured on a CLEAN build per the prior lesson.) add_edges_from's native-batch fast path is gated on
`not _simple_add_edges_from_touches_existing_plain_edge(self, ebunch)`, which loops `graph.has_edge(u,v)` PER
edge (O(E) PyO3 round-trips) to detect a pre-existing edge (the batch must bail-to-per-edge if any edge already
exists, for the attr-update contract). But on a FRESH/EMPTY graph -- from_edgelist, Graph(edgelist),
add_edges_from on a new graph: the common construction case -- NO edge can pre-exist, so the entire pre-scan is
wasted, ~doubling the work. FIX: short-circuit `if graph.number_of_edges() == 0: return False` (O(1)) at the top
of the gate. RESULT: from_edgelist 0.724x -> 1.136x (1.57x self, BEATS nx), byte-identical (from_edgelist ==nx;
non-empty add_edges_from with existing-edge attr-update still ==nx -- the pre-scan still runs there), conformance
GREEN (911). Python-only (no rebuild). Helps every construction path that add_edges_from's onto a fresh graph.
(Graph(edgelist) 0.74x is a separate constructor path, not this gate -- follow-up.) 30th perf ship.

## 2026-06-27 CopperCliff FIX: weighted wiener_index over add_edges_from(dict)-built graphs (store-stale adjacency bug)

Fixed the narrow correctness bug characterized 88446b637: weighted wiener_index built weighted_adj from
G.adjacency(), whose per-edge attrs read the Rust STORE -- STALE for graphs built via add_edges_from(dict attrs)
(weights mirror-only) -> silently used default-1 weights (n=5 directed-complete via add_edges_from(dict): 20 vs
nx 58). FIX: source the WEIGHTS from a bulk edges(data=True) map (reads the MIRROR, always fresh) while keeping
adjacency()'s neighbor STRUCTURE/ORDER (so Dijkstra discovery + float-sum order stay byte-identical). RESULTS:
batch-built wiener 20->58 (==nx), store-built still 58 (==nx), undirected ==nx, conformance GREEN (4393
wiener/weighted/distance tests). Perf 0.876x (near-parity; small cost vs the old fast-but-WRONG adjacency
snapshot -- correctness > a few %). size(weight)/degree(weight)/dijkstra were already correct (mirror-aware);
wiener was the lone adjacency()-consuming weighted kernel. This also UNBLOCKS the add_weighted_edges_from 8x
batch win (the wiener regression that blocked it is now fixed) -- pending a broad check that no OTHER
adjacency()-consuming weighted kernel is affected. 3rd correctness fix this session.

## 2026-06-27 CopperCliff SHIP: add_weighted_edges_from 0.135x->1.10x (8x self) — delegate to add_edges_from batch (UNBLOCKED by the wiener fix)

Now that the weighted-wiener stale-store bug is fixed (7b61292a3), re-enabled the add_weighted batch win:
delegate the string-weight case to add_edges_from((u,v,{weight:w})) EXACTLY as nx does, hitting the native
attributed batch instead of the per-edge add_edge PyO3 loop. Verified the regression that previously blocked it
is gone: broad batch-vs-store check (wiener/size/in_degree/dijkstra/pagerank/betweenness/closeness/
adjacency_matrix/degree_pearson) ALL match; wiener after add_weighted = 58 ==nx. RESULTS: 0.135x -> 1.095x
(~8x self, BEATS nx), edges(data) byte-identical across Graph/DiGraph/MultiGraph/MultiDiGraph + **attr + error
contract, conformance GREEN (2404 weighted/wiener/add_edges). 31st perf ship. (Two-step: fix the latent
correctness bug, then land the perf win it gated.)

## 2026-06-27 CopperCliff subgraph(view) 0.5x view-machinery-bound (filt set-intersection marginal, reverted) + find_induced_nodes without_fallback PRE-EXISTING failure

Construction sweep (clean build): all wins (gnp 3.7x, complete 12.5x, Graph(G) copy 11x) EXCEPT
G.subgraph(nbunch) VIEW (no copy) 0.529x. Profiled: filt build (_subgraph_filter_from_nbunch) is 66us of 76us
(set(G) only 10us -> the per-node hash+membership+add loop is ~56us). Tried a C set-intersection fast path
(set(nb_list) & gnodes for large nbunch): filt build 66->44us BUT full subgraph only 76->60us (~1.1-1.27x self,
NOISY 0.48-0.59x) -- the _generic_filtered_graph_view / _FilteredGraphView object construction is the remaining
floor (view machinery, not the filt). MARGINAL at the operation level -> REVERTED.
SEPARATELY DISCOVERED (clean-build, NOT mine): TestFindInducedNodesParity::test_matches_networkx_without_fallback
+ error_contract FAIL on HEAD (3 cases). Cause: peer commit 17040bd66 made find_induced_nodes "run nx's
chordality-breaker on an nx copy" -- byte-exact VALUES but a NX FALLBACK, which the without_fallback test forbids.
Not a correctness bug (values match); a no-fallback contract violation in the peer's perf commit. Flagged for
the owner (find_induced_nodes needs a native non-nx path to satisfy without_fallback, or the test relaxed).
LESSON (again): re-confirmed via clean rebuild before attributing a conformance failure (the 3 fails were
CONSTANT across my fix + revert -> pre-existing, not mine).

## MultiGraph/MultiDiGraph remove_nodes_from — batched inner, byte-exact, BENCH-NEUTRAL at N=1000 (CopperCliff)

Surfaced the mutation-loop cluster's `remove_nodes_from` asymmetry: simple `Graph`/`DiGraph`
bindings compact via a batched `inner.remove_nodes_from` (Graph rnf 1.05x), but `MultiGraph`/
`MultiDiGraph` bindings LOOPED `inner.remove_node` per node — and `MultiGraph::remove_node` pays
two O(|V|) `shift_remove`s (adjacency + nodes IndexMaps preserve insertion order) per call, so the
loop was O(k·|V|). Measured (n=1000, m=5000, k=500): MultiGraph rnf 0.118x (8.5x slower), MDG 0.126x.

FIX (SHIPPED, byte-exact): added `MultiGraph::remove_nodes_from` batch (one `retain` per structure =
O(|V|+|E|) total; edges-map order unobserved so `retain` is order-safe; edge_count tallied from dropped
parallel-edge buckets) + routed `PyMultiGraph::remove_nodes_from` to purge Python mirrors while `inner`
is intact, then compact `inner` ONCE. Byte-exact 256/256 (64 specs × 4 seeds: parallel edges, self-loops,
node/edge attrs, explicit str/int keys, mixed dup+nonexistent victims).

BENCH REJECTION / next-lever: end-to-end MultiGraph rnf stayed 0.13x — the O(k·|V|) inner shift_remove
was NOT the dominant term at N=1000. The real floor is the BINDING's per-node mirror-cleanup loop:
`inner.neighbors(n)` returns a fresh Vec and each neighbor triggers `inner.edge_keys(n,nb)` returning
another Vec — O(k·degree) allocations nx avoids by walking live dicts. The inner batch is the correct
complexity fix (helps at large |V|, closes the Graph/DiGraph parity gap) but is masked here. LEVER for
the win: collapse the per-node neighbors()/edge_keys() allocation loop into a single borrowed adjacency
walk (or skip it entirely when edge_py_attrs/edge_py_keys mirrors are empty — the pristine-mirror case).
MultiDiGraph binding still loops inner.remove_node (no inner batch added yet) — same fix pending.

## MultiGraph.remove_nodes_from — kill the O(k·degree) binding edge-walk (CopperCliff, MEASURED WIN)

Follow-up to the bench-neutral inner batch (7faa668e6). Profiled the residual floor: the
PyMultiGraph binding walked `inner.neighbors(n)` + `inner.edge_keys(n,nb)` PER removed node —
a fresh Vec<String>+Vec<usize> alloc per incident edge plus a canonical-String edge_key build
per HashMap probe — purely to purge the edge mirrors. Per-removal cost scaled LINEARLY with
degree (3.3us@deg4 -> 9.3us@deg10 -> 22.7us@deg20 -> 57.8us@deg40), confirming O(k·degree).

FIX (SHIPPED, byte-exact 256/256 structural + 256/256 mirror-coherence incl. touched mirrors +
stale-resurrection on re-add): dropped the per-node edge walk for a single endpoint-keyed
`retain` over each edge mirror (edge_py_attrs/edge_py_keys) — O(mirror size) once, and 0 for the
common bulk-built/pristine graph. Node-side mirror purge stays O(k). `had_incident_edges` now
comes free from the inner batch's returned `removed_edges`. Also swapped the inner `remove_set`
and binding `present_set` from std SipHash to FxHashSet (probed once per adjacency entry in the
O(|E|) retains; SipHash on those string keys was a profiled hot spot; byte-exact by construction).

MEASURED (n=1000, k=500, MG rnf): ~0.13x -> **0.203x @ m=5000**, 0.223x -> **0.326x @ m=2000**
(per-edge-built). Batch-built/pristine-mirror **0.343x @ m=10000**. Real ~25-45% self-speedup;
closes the per-node-alloc floor. NOTE: the FxHash swap is compile-checked + byte-exact by
construction but its magnitude was not separately benchmarked (build was frozen mid-measure);
the 0.20x/0.33x figures are the pre-FxHash std-hash FLOOR.

RESIDUAL / NEXT LEVER: even batch-built (empty mirror) is 0.34x — the inner MultiGraph batch does
a WHOLE-GRAPH O(|E|) retain scan (edges map + every surviving adjacency row) regardless of k,
where nx touches only incident edges. For k << N an incident-only batch (walk removed nodes'
adjacency, swap_remove... but MG rows are order-observed so must shift_remove) would win; for
k~N/2 the whole-scan is order-comparable but has a ~3x constant (Rust IndexMap retain+shift vs
Python dict del). MultiDiGraph sibling (identical pattern, inner batch + binding written, FxHash)
is STASHED UNVERIFIED (cc-mdg-remove_nodes_from-batch-UNVERIFIED-never-built) — build+byte-verify
then ship. MDG rnf still 0.16x.

## MultiDiGraph.remove_nodes_from — batch inner + kill binding edge-walk (CopperCliff, MEASURED WIN, follow-up)

Shipped the MDG sibling of the MG fix (was stashed unverified; rebuilt + verified). MultiDiGraph
had NO inner batch (looped inner.remove_node = three O(|V|) shift_removes each => O(k·|V|)) AND the
binding walked successors()/predecessors()+edge_keys() per node (O(k·degree) allocs). Added
MultiDiGraph::remove_nodes_from (one retain per structure over edges/successors/predecessors/nodes
= O(|V|+|E|); revision bump invalidates csr_cache) + routed the binding to node-side O(k) purge +
single endpoint-keyed retains over edge_py_attrs/edge_py_keys/succ_py_keys/pred_py_keys + FxHashSet.

MEASURED (n=1000,k=500): MDG rnf 0.102x -> **0.424x @ m=2000**, 0.125x -> **0.239x @ m=5000**,
0.109x -> **0.166x @ m=10000**. Byte-exact 256/256 MG + 256/256 MDG (512 checks: parallel edges,
self-loops, node/edge attrs, str+int explicit keys, touched mirrors, dup+nonexistent victims,
stale-resurrection on re-add) + 3116 targeted conformance tests pass. FxHash confirmed the MG floor
too: MG rnf now 0.236x @ m=5000 / 0.374x @ m=2000 (above the 0.203x std-hash floor reported in the
prior commit).

RESIDUAL (both types): whole-graph O(|E|) inner retain scan regardless of k (~3x nx incident-only
dict dels) — the last lever for k<<N.

## Multi(Di)Graph.remove_nodes_from — incident-only small-k fast path (CopperCliff, MEASURED WIN)

Profiled remove_nodes_from at varying k: the whole-graph O(|V|+|E|) batch (retain scans over the
entire edges map + every adjacency row + the whole Python edge mirror) is catastrophic when k<<N —
removing 10 nodes from a 2000/10000 graph was **0.01x (100x slower than nx)**, which touches only
incident edges (O(sum_removed_degrees)). This is the realistic case: prune a few nodes from a large
graph.

FIX (SHIPPED, byte-exact): adaptive dispatch gated on `k*4 <= |V|`. Small-k path walks ONLY the
removed nodes' adjacency (inner: drop incident edge buckets O(1) + prune the removed node from each
SURVIVING neighbour's opposite row + compact the outer maps ONCE; binding: reconstruct exactly the
incident Python-mirror keys from `inner` while intact and drop only those). Large-k falls through to
the whole-graph retain (avoids repeated hub shift_remove). Applied to BOTH inner
(MultiGraph/MultiDiGraph::remove_nodes_from) AND binding (edge_py_attrs/edge_py_keys purge).

MEASURED (n=2000, m=10000, per-edge-built): MG rnf k=10 **0.01x -> 0.20x (20x)**, k=200 0.09x -> 0.17x;
MDG k=10 0.02x -> 0.13x. Batch-built/empty-mirror MG k=10 -> 0.21x. No regression at k=N/2 (whole-graph
path unchanged: MG 0.225x, MDG 0.279x). Byte-exact 1792 checks (k in {1,2,N/8,N/4,N/4+1,N/2,N} x
parallel edges/self-loops/attrs/str+int keys/touched-mirrors/dup+nonexistent victims + stale-
resurrection on re-add for BOTH paths) + 512 k=N/2 checks + 3799 conformance tests.

RESIDUAL: even small-k is ~0.20x — the inner's final adjacency.retain + nodes.retain are O(|V|) once
(IndexMap can't O(1)-delete preserving order; nx's dict can). That O(|V|) compaction floor is the
storage-model wall for k<<N. Simple Graph/DiGraph small-k (0.05x) is the separate int-index renumber
bomb (architectural). Single remove_node loop 0.014x remains the biggest architectural gap (slotmap).

## Mutation-cluster residual is a PyO3 call-boundary floor — SURFACED (CopperCliff, no-ship)

After shipping the remove_nodes_from cluster (batch + walk-removal + FxHash + incident-only small-k),
ran a fresh broad cross-domain sweep (24 ops, n=800/m=4000) to find the next lever. Result: fnx is
at-or-above nx on 20/24 — algorithms 3-50x (clustering 49.9x, k_core 46.5x, betweenness 31.1x,
core_number 13.0x, connected_components 10.4x, triangles 7.0x, bfs/pagerank/dijkstra 3.6-4.4x),
conversions 1.2-3.5x (to_dict_of_lists 3.49x, adjacency_matrix 2.64x, to_scipy 2.47x), generators
1.4-3.9x. The only sub-1.0x are near-parity floors: degree_weight 0.85x, nodes_data 0.92x,
reverse_digraph 0.98x, adj_iter 0.99x. This algorithm/view/conversion vein is MINED OUT.

Every DRAMATIC gap is the single-element mutation cluster (n=1000/m=5000): single remove_node loop
0.014x, remove_edge loop 0.28x, has_edge 0.32-0.35x, add_edge 0.39x. Proved these are a PyO3
call-boundary floor, NOT a fixable inefficiency:
- has_edge int-node (existing `has_edge_by_indices` fast path — NO alloc, NO String hash): **0.316x**.
- has_edge str-node (node_key_to_string heap-alloc path): 0.194x.
So the alloc costs ~40%, but even the ALLOC-FREE fast path floors at 0.316x — that residual is the
PyO3 boundary crossing (arg extract + into-Rust call + return) which for a micro-op costs MORE than
nx's pure-Python C-level dict lookup it replaces. remove_edge/add_edge can't even use the int fast
path: the canonical String is needed downstream (String-keyed store + edge mirror), so the alloc is
load-bearing. Micro-opts (defer py_adj_key when adj_row_py empty) net ~3-5% — below the 9-18% rch
bench-worker noise. NON-TAKEABLE without eliminating the FFI boundary (impossible for a PyO3 ext).

Single remove_node loop 0.014x is additionally the int-index CONTIGUITY renumber bomb: simple
Graph/DiGraph store adj_indices/edge_index_endpoints/edges by contiguous [0,N) position, so removing
one node renumbers every index > idx = O(|V|+|E|) per call (loop = O(k(|V|+|E|))). Requires a
stable-id (slotmap/generational-arena) storage rewrite with a decoupled insertion-order index — a
multi-day refactor touching every `_by_index`/matrix-export consumer across 57k lines, NOT a
one-session lever. MG/MDG avoid the renumber (string-keyed adjacency) which is why the incident-only
small-k win landed there and not for simple Graph.

CONCLUSION: the remaining vs-nx gaps are architectural floors (PyO3 boundary for micro-mutations;
int-index renumber for simple-Graph remove_node). Future cycles on has_edge/add_edge/remove_edge
micro-opts are low-EV (capped ~0.35x by FFI). The only real remaining lever is the slotmap rewrite.

## I/O + Multi-type sweep clean; DiGraph weighted-degree floor = EAGER-MIRROR (lever: lazy unification) — SURFACED (CopperCliff)

Fresh sweep of previously-unswept domains (I/O formats, flow, Multi-type ops, 24 ops, n=600/m=3000):
fnx at-or-above nx on all but near-parity floors. Wins: transitivity 60x, mg_number_of_edges huge,
multidigraph_edges_kd 7.6x, diameter/harmonic/eccentricity 5.7-6.6x, square_clustering/dfs 4.5x,
multigraph_degree_w 2.2x, edgelist/adjlist_write 1.5-2x, multigraph_copy/reverse 1.2-1.4x. Sub-parity:
DiGraph in_degree(w) ~0.85-0.90x, out_degree(w) ~0.83-0.87x (the only real one), plus near-parity
gexf/graphml/adjacency_data/node_link 0.88-0.97x. No NEW one-session-takeable gap.

DiGraph weighted-degree ROOT CAUSE (new framing): DiGraph is the ONLY graph type with an EAGER edge
mirror (add_edges_from populates one PyDict/edge, digraph.rs ~9041). So its weighted degree goes
through per-node row-dict materialization (successor_row_dict_by_canonical/predecessor_*, which also
mark_edges_dirty on a READ) + Python sum(). MultiDiGraph/MultiGraph are LAZY -> their store twins
(native_weighted_directional_degree, read-only, sums in Rust) ENGAGE. DIRECT EVIDENCE (batch-built,
same op): **MultiDiGraph out_degree(w) = 2.16x (BEATS nx)** vs **DiGraph out_degree(w) = 0.85x**.

Confirmed NOT a store-twin fix: the DiGraph int+float store-twin port is a fresh NO-SHIP (704254a93,
2026-07-02) that POSTDATES the edges_dirty-clear fix (c314372dd, 2026-06-28) by 4 days, so it was
tested with the store accessible and STILL break-even — the eager mirror makes store-vs-mirror
equal-cost. The ACTUAL lever is unifying DiGraph to a LAZY mirror like MG/MDG: unlocks the store
fast paths (degree/edge-data -> potential ~2x like MDG) AND speeds builds (no per-edge PyDict). This
is a large refactor (every DiGraph edge_py_attrs reader must handle materialize-on-demand), NOT a
one-session lever — but it's the single highest-value remaining architectural lever, distinct from
the mutation-cluster PyO3 floor and the simple-Graph remove_node int-index renumber bomb.

## DiGraph degree(weight) 0.76x -> 3.7x (INT) / 2.1x (FLOAT) — SHIPPED (CopperCliff), corrects the "eager-mirror floor"

The DiGraph weighted-degree gap I'd repeatedly surfaced as an "eager-mirror floor" (NO-SHIP
704254a93) was a MISDIAGNOSIS. Root cause found by introspecting the actual generator
(`gen.gi_code.co_name`): `dict(g.degree(weight))` routed to `_di_total_weighted_gen` (__init__.py),
which called `_native_adjacency_row_dict(node)` + `_native_predecessor_row_dict(node)` PER NODE
(materializing a full {neighbor: attr_dict} PyDict per node — AND marking the store dirty on a READ)
then Python `sum()`. My store-int / mirror-int accumulator experiments looked "bench-neutral" ONLY
because they were wired into a DIFFERENT view path (`_native_weighted_degree` / the wrong
`MultiGraphDegreeView.__iter__`) that `g.degree(weight)` never hits.

FIX: added `_native_weighted_degree_values` (values-only total degree in node-index order: int-store
fast path via `edge_attrs_by_indices` + `successors_indices`/`predecessors_indices`, else exact
PyList+sum) and routed `_di_total_weighted_gen` to `zip(list(G), values(weight))` — no per-node
row-dict materialization, no py_node_key rebuild, no store-dirtying. list(G) order == nodes_ordered()
order (verified). MEASURED (n=600,m=3000): degree(w) INT 0.76x -> **3.72x**, FLOAT 0.84x -> **2.10x**.
No regression (in/out_degree untouched at 0.69-0.85x; unweighted 1.1x). Byte-exact across
int/float/mixed/missing/bool/self-loop/bignum(i64-overflow bail)/neg-zero/str(raises)/isolated +
6305 conformance tests.

LEVER: when a perf change measures "bench-neutral", VERIFY THE DISPATCH ACTUALLY HITS YOUR CODE
(introspect the generator/method via co_name/co_filename) before concluding it's a floor — the wrong
path masked a real 3.7x win for THREE turns. FOLLOW-UP: in/out_degree(weight) (0.69-0.85x) use the
same row-dict `_di_*` gens — a directional `_native_weighted_{out,in}_degree_values` + zip would give
the same win.

## DiGraph in/out_degree(weight) 0.69-0.85x -> 3.0x INT / 2.0x FLOAT — SHIPPED (CopperCliff, follow-up)

Same lever as the total-degree win: the in/out weighted gens (__init__.py ~5016) materialized
`_native_adjacency_row_dict(node)` / `_native_predecessor_row_dict(node)` per node + Python sum().
Generalized the store/exact value helpers to directional (inc_out/inc_in), added
`_native_weighted_{out,in}_degree_values`, and routed the in/out gens to zip(list(G), values(w)).
MEASURED: in_degree(w) 0.85x->3.06x, out_degree(w) 0.69x->3.05x (INT); ~2.0-2.04x (FLOAT). degree(w)
holds 3.68x/2.12x. Byte-exact (int/float/mixed/missing/bool/self-loop/bignum/neg/str/isolated for
all three) + 8787 conformance tests. The whole DiGraph weighted-degree family now BEATS nx 2-3.7x.

## undirected Graph.degree(weight) INT 0.80x -> 2.80x — SHIPPED (CopperCliff)

Same lever as the DiGraph weighted-degree family, applied to the last graph type with the gap
(Multi types already fast via store twins). `dict(g.degree(weight))` for undirected Graph routed to
`_weighted_degree_gen` (__init__.py ~5483) which materialized the WHOLE `to_dict_of_dicts(G)` +
Python sum() per node. Added `_native_weighted_degree_int_values` to PyGraph (i128 accumulate per
node straight from the CgseValue store via neighbors_indices + edge_attrs_by_indices; undirected
self-loop appears ONCE in adj_indices but counts 2·w per nx; gated !edges_dirty; None on non-int/
overflow -> gen fallback) and routed the gen to zip(list(G), values(weight)) for INT.

MEASURED (n=600,m=3000): Graph.degree(w) INT 0.80x -> **2.80x**. FLOAT stays on the near-parity gen
(0.93x, unchanged — the lazy undirected mirror means the exact-float path can't cheaply read the
mirror; low ROI given near-parity). Byte-exact across int/float/mixed/missing/bool/self-loop(x2)/
bignum(i64-overflow bail)/neg-zero/str(raises)/isolated + 6305 conformance. DiGraph wins intact
(3.67x/3.02x). GOTCHA this session: first placed the method in the wrong impl block (PyMultiGraph
2475-8703 vs PyGraph 905-2410/9363+) — `hasattr(g, method)` returned False, exposing it; the
introspection habit caught it fast.

FOLLOWUP: undirected Graph in/out have no direction (total only); FLOAT undirected degree(weight)
0.93x could reach ~2x with a store-float Neumaier values path (as DiGraph has) — low ROI, near-parity.
The whole weighted-degree surface (Graph/DiGraph/MultiGraph/MultiDiGraph, int) now BEATS nx 2.2-3.7x.

## Graph.degree(nbunch, weight) INT 0.58x -> 1.68x — SHIPPED (CopperCliff)

Weighted degree over a node SUBSET was the last weighted-degree gap (Graph 0.58x, DiGraph 0.73x).
The undirected subset native `_native_weighted_degree_subset` already reused the passed nbunch object
as the key (== nx, no py_node_key redundancy) but paid per-node: `neighbors(canonical)` Vec<&str>
alloc + String hashing, `edge_attr_py_value` per neighbour (String edge_key + PyO3), PyList append,
and Python `sum()`. Added an INT-store fast path: materialize the (validated, in-graph) nbunch ONCE
(nbunch may be a one-shot generator), then i128-accumulate per node from the CgseValue store via
`neighbors_indices` + `edge_attrs_by_indices` (undirected self-loop counts 2·w), reusing the nbunch
object. Gated !edges_dirty; a labeled-break bails the whole subset to the exact path on any non-int
weight / overflow (so float/heterogeneous keep the byte-identical builtins.sum result).

MEASURED (n=600,m=3000,nbunch=200 nodes): Graph.degree(nbunch,w) INT 0.58x -> **1.68x**. Byte-exact
across list/tuple/set/absent-node/generator/all/single/empty/float/mixed/missing/bigint(overflow-bail)/
neg/unhashable(TypeError) + 6393 conformance. This corrects the reference_degree_nbunch_weight_store_floor
NO-SHIP (that was a mirror int-accumulator twin double-walking neighbours; the INDEX-store read + nbunch
materialization is the clean version). FLOAT subset stays 0.70x (exact PyList+sum path; a store-float
Neumaier subset path would win but is lower ROI). DiGraph subset (0.73x, weighted_degree_subset_impl)
is the remaining follow-up. HARNESS GOTCHA: a shared generator nbunch is consumed by the first call —
use a factory (fresh nbunch per graph) or it falsely reports a mismatch.

## DiGraph degree/in/out(nbunch, weight) 0.55-0.80x -> 0.89-2.15x — SHIPPED (CopperCliff)

Directed subset weighted degree (same lever as the undirected subset + full-graph family). PyDiGraph
`weighted_degree_subset_impl` (out/in/total via DegreeKind) built per-node PyLists via
`edge_attr_py_value` (String edge_key + PyO3 per edge) + Python `sum()`. Added an INT-store fast path:
materialize the validated in-graph nbunch ONCE (may be one-shot generator), i128-accumulate per node
from the CgseValue store via `successors_indices`/`predecessors_indices` + `edge_attrs_by_indices`
(directed self-loop sits in each direction once, so Total's out+in counts it twice = nx — NO special
doubling, unlike undirected). Reuses the nbunch object as key; gated !edges_dirty; labeled-break bails
the whole subset to the exact path on non-int/overflow.

MEASURED (n=600,m=3000,nbunch=200): degree(nb,w) 0.80x -> **2.15x**, in_degree(nb,w) 0.55x -> ~0.89x,
out_degree(nb,w) 0.55x -> ~0.89x. Byte-exact across list/tuple/set/absent/generator/all/empty/float/
mixed/missing/bigint/neg for all three methods + 6393 conformance. in/out stay just below parity: the
per-node node_key_to_string (int->String) + get_node_index (String hash) is the residual String-key
floor nx avoids (int dict key direct); total degree beats nx because its 2x edge work amortizes that
per-node overhead. FOLLOWUPS: MG/MDG subset (0.71-0.73x, multi parallel-key int accumulate) + FLOAT
subset (store-Neumaier). BUILD NOTE: `&canonical` on a `for (_,canonical) in &items` loop is `&&String`
-> pass `canonical` (deref-coerces to &str), not `&canonical`.

## Graph.nbunch_iter 0.25x -> 0.64x (int) — SHIPPED (CopperCliff), PyO3-membership floor lifted

nbunch_iter (filter a nbunch to in-graph nodes, yielding the ORIGINAL objects) was the biggest gap
in a fresh broad sweep (0.247x). `_graph_nbunch_iter` (Python) built `self.adj` then did `hash(n)` +
`n in adj` PER NODE — each `n in adj` crosses the PyO3 boundary (adjacency-view __contains__ ->
node_key_to_string int->String alloc + has_node). nx uses a plain dict (C-level). Ratio worsened
with k (per-node dominated, not the O(1) adj construction).

FIX: native `PyGraph::_nbunch_present(nbunch) -> Option<Vec<PyObject>>` — one Python->Rust crossing
for the whole (re-iterable list/tuple/set) nbunch, returning present members in order as the original
objects. An EXACT int at its own index is present with NO String work (node_index_matches_int).
Returns None on the first unhashable element -> the Python lazy generator raises nx's exact
NetworkXError, so error semantics stay byte-identical. Routed from `_graph_nbunch_iter` gated
`isinstance(nbunch,(list,tuple,set,frozenset)) and not hasattr(self,'_graph')` — generators keep the
lazy path; PROXY VIEWS (conversion/filtered/reverse carry a `_graph` parent + EMPTY native inner,
membership behind the Python self.adj proxy) MUST skip the native (else it drops all nodes — caught
by test_conversion_live_view_exposes_nbunch_iter).

MEASURED: Graph.nbunch_iter k=1000 int 0.156x -> 0.64x, k=100 0.27x -> 0.57x; str-nodes ~0.35x (bulk
without the int fast path). Downstream subgraph(sub).copy() 1.22x (no regression). Byte-exact 0 mism
across 4 types x list/tuple/set/absent/generator/str/mixed/noncontig/unhashable/single/None + 6702
conformance. STILL below parity: the eager Vec + per-int PyO3 extract is a floor vs nx's C dict, but a
real ~2.5x self-speedup on a broadly-used primitive. FOLLOWUP: DiGraph/MG/MDG lack node_index_matches_int
on their inners + _nbunch_present (would need adding) — they keep the generator (still 0.25x).
GOTCHA: `self` in `_graph_nbunch_iter` IS the raw graph (no `_graph` wrapper) — `getattr(self,...)`,
not `self._graph`.

## nbunch_iter extended to DiGraph/MultiGraph/MultiDiGraph — 0.10-0.15x -> 0.62-0.66x — SHIPPED (CopperCliff)

Follow-up to the undirected Graph nbunch_iter win (c3961bdbe). The 3 remaining types were still 0.15x
(DiGraph) / 0.10x (MultiGraph) / 0.11x (MultiDiGraph) — Multi even worse (heavier MultiAdjacencyView
`n in adj`). Added `node_index_matches_int` to the DiGraph/MultiGraph/MultiDiGraph inners (identical
O(1) index-probe + no-alloc parse) and `_nbunch_present` to all 3 pyclasses (identical to PyGraph's).
No Python change — `_graph_nbunch_iter`'s `getattr(self,'_nbunch_present')` + `not hasattr(self,'_graph')`
view gate already route/protect all 4 types.

MEASURED (k=1000, contiguous-int): DiGraph 0.154x -> **0.657x**, MultiGraph 0.105x -> **0.663x**,
MultiDiGraph 0.111x -> **0.615x** (Graph 0.83x). Byte-exact 0 mism across all 4 types x
list/tuple/set/absent/generator/str/mixed/noncontig/unhashable/single/None + 6319 conformance (view
gate holds for conversion/filtered/reverse across all types). All 4 nbunch_iter now ~0.6-0.8x (from
0.10-0.25x) — still PyO3-floored below parity but a 4-6x self-speedup on a broadly-used primitive
(edges/degree/subgraph over nbunch all route through it).

## 2026-07-02 CopperCliff SHIP (strict-work-removal): DG/MG/MDG inner remove_edge shift_remove->swap_remove (O(|E|)->O(1)) + BLOCKER surfaced

BIGGEST measured gap this session: remove_edges_from is catastrophic for the 3 non-simple types
(isolated us/edge, n=2000 m=12000): DG 18-22us/edge ratio 0.015x, MG 29-36us/edge 0.016x, MDG
30-36us/edge 0.016x — vs simple Graph 0.4us/edge 0.55x (55-60x slower than nx). Scale probe (fix
k=100, vary E): DG 4.9->22.6->96.7 us/edge as E=3k->12k->48k with CONSTANT avg degree 6 -> genuinely
O(|E|), not O(degree).

ROOT (one lever found, one still open):
(1) FIXED — the inner *::remove_edge for DiGraph (digraph.rs:1460), MultiGraph (lib.rs:3199 OUTER
node-pair map), MultiDiGraph (digraph.rs:2721 OUTER map) used `self.edges.shift_remove` = O(|E|)
IndexMap shift. Simple Graph was ALREADY ported to `swap_remove_full` (br-r37-c1-vbwpl); the 3 others
only got swap_remove for remove_NODE, missing it for remove_EDGE. Ported: shift_remove->swap_remove
on the edges map. SAFE: edges-map STORAGE order is never observed (edges_ordered walks adjacency/
succ_indices and looks pairs up by key; COO exporters are triple-order-irrelevant; weighted_size sums
are order-insensitive) — and remove_node already swap_removes the SAME map under full conformance, so
the invariant is committed. Multigraph INNER bucket keeps shift_remove (per-pair key order IS observed
by edges(keys=True); nx preserves surviving-key insertion order). Byte-EXACT: 120/120 differential
(random build + mixed (u,v)/(u,v,key) removals + non-existent skips + re-add/slot-reuse, all 4 types)
+ targeted MG/MDG middle-key-removal order preserved.

(2) BLOCKER (residual, dominant) — the fix did NOT move the Python-facing remove_edges_from ratio
(still 0.016x). The O(|E|) that dominates the API path is NOT the edges-map shift: it is the
Python-wrapper `_invalidate_adjacency_row_caches(self)` (called once per batch, walks the cached
adjacency-row dict) and/or a still-unlocalized per-edge O(|E|) in the DiGraph remove path — per-edge
cost stayed 19-22us after the swap. The inner swap_remove is strict-work-removal (swap_remove does
strictly less than shift_remove, never slower) and correct, and speeds up Rust-side remove-heavy
callers that bypass the Python cache wrapper (double_edge_swap family), but the Python remove_edges_from
gap needs the wrapper/per-edge O(|E|) localized next. NEXT LEVER: profile the exact 19us/edge split
(native raw() vs _invalidate_adjacency_row_caches vs Python validation loop) on a SMALL per-crate bench.

## 2026-07-02 CopperCliff CORRECTION (BIG measured WIN, not neutral): remove_edge O(|E|)->O(1) — DG 0.018x->0.82x, MG 0.016x->0.35x, MDG 0.016x->0.42x

The prior entry (same session) claimed the swap_remove fix "did NOT move the Python-facing
remove_edges_from ratio (still 0.016x)". THAT WAS A STALE-BINARY ARTIFACT: `python3` (system) loads
the .so from ~/.local/lib/python3.13/site-packages (mtime Jul-1, PRE-change, missing many recent
commits), while `maturin develop` installs the editable build into ./python/franken_networkx (loaded
only by ./.venv/bin/python). ALL my probes ran against the stale .so, so the fix looked inert. LESSON
(load-bearing): after `maturin develop`, VERIFY which .so Python actually imports
(`franken_networkx._fnx.__file__` + mtime) before trusting ANY before/after bench — plain `python3`
here is NOT the maturin target. Use `.venv/bin/python` (or check __file__).

Re-run on the FRESH .so: the shift_remove->swap_remove on the inner edges/node-pair map turned
remove_edge from O(|E|) into O(1) exactly as designed. NAIL probe (remove_edge us/call, E=6k/24k/96k):
STALE 11.5/48.8/201.7 (linear O(|E|)) -> FRESH 1.11/1.52/2.85 (FLAT O(1)). Head-to-head vs nx
(n=2000 m=12000, isolated removal):
  DG  remove_edges_from: 0.018x -> 0.819x (k=6000) / 0.502x (k=100)   ~55x self
  MG  remove_edges_from: 0.016x -> 0.349x / 0.332x                    ~17x self
  MDG remove_edges_from: 0.016x -> 0.419x / 0.347x                    ~24x self
  G   unchanged 0.585x (already had swap_remove_full via br-r37-c1-vbwpl)
Byte-EXACT on the fresh .so: 120/120 differential (all 4 types, mixed (u,v)/(u,v,key) removals,
non-existent skips, re-add/slot-reuse) + MG/MDG middle-key-removal order preserved. This was THE
biggest measured gap of the session (55-60x slower) and is now within 2-3x of nx (residual = the
multigraph per-pair bucket + PyO3 mirror maintenance, a much smaller floor). code already shipped in
d947bf3fa; this entry corrects the (stale-binary) framing to record the real win.

## 2026-07-02 CopperCliff SHIP: MultiGraph weighted remove_edge O(|E|)->O(1) — MG weighted removal 0.002x->0.32x (159x self at scale)

Follow-up to the shift_remove->swap_remove remove_edge fix. After that, a scale probe (isolate removal,
k=100, vary E, on the FRESH .venv binary) exposed a SECOND O(|E|) — SPECIFIC to undirected MultiGraph
WITH edge attrs: MG weighted removal was 26.8/116.8/722.9 us/edge at E=6k/24k/96k (ratio 0.021x->0.008x
->0.002x — 500x slower than nx at scale). MG unweighted, MDG (both weighted/unweighted), DG: all fine
(~O(1)). The weighted-only + undirected-only signature localized it.

ROOT: PyMultiGraph::remove_edge (lib.rs ~6866), when the last parallel key empties a (u,v) pair, purged
the pair's mirror entries with `self.edge_py_attrs.retain(|(x,y,_),_| !(x==a && y==b))` +
`edge_py_keys.retain(...)` — an O(|edge_py_attrs|)=O(|E|) scan over the WHOLE mirror, on EVERY
pair-emptying removal. For a typical multigraph (single edge per pair) EVERY removal empties its pair ->
O(k*|E|). It only fires when edge_py_attrs is populated (weighted), hence weighted-only. (MDG's
remove_edge never had this exhaustive retain — it was already fine; only undirected MG.) The retain was
a br-r37-c1-kuxuc correctness backstop: mirror entries can live under a key != removed_key when keys are
REMAPPED (mirror under a public key not in the inner bucket); exhaustive-by-pair is exact regardless of
key space.

FIX (br-r37-c1-rmedge-oE): capture the pair's INTERNAL bucket keys BEFORE removal (only when
!has_remapped_int_key AND a mirror exists), and on pair-empty drop exactly those `(a,b,k)` mirror slots
via remove_edge_metadata — O(bucket) instead of O(|E|). When keys are identity-int the mirror is keyed
by exactly the internal bucket keys (note_public_key_value flags ANY non-identity key str/float/bool/
remapped as has_remapped_int_key=true), so the targeted purge is COMPLETE. The remapped case keeps the
exhaustive retain (rare, O(|E|) acceptable). RESULT: MG weighted removal 26.8/116.8/722.9 ->
2.01/3.25/4.55 us/edge (FLAT O(1), 159x self at E=96k), ratio 0.002x->0.32x (now == MG unweighted, the
per-pair-bucket+PyO3 mirror floor). End-to-end MG remove_edges_from(weighted, incl construction)
0.079x->0.642x. Byte-EXACT: 50/50 metamorphic resurrection (self-loop add(w)/remove/re-add, parallel
remove-last/re-add, empty-then-readd-fresh, explicit-int-key, str/float-key remapped path, 40 random
weighted MG/MDG) + 120/120 differential — the exact kuxuc/0a0uo fuzz patterns the exhaustive retain
protected are covered and pass. LEVER: an O(|E|) full-mirror `retain` used as a correctness backstop ->
capture the bucket keys before removal + gate the exhaustive scan behind the key-remap flag that is the
ONLY source of key-space mismatch.

## 2026-07-02 CopperCliff SURFACE (architectural, NO-SHIP this pass): node removal is the storage-model wall — 0.003-0.14x, needs slotmap/deferred-compaction

After the two remove_EDGE wins, the biggest remaining MUTATION gap is node removal (remove_node /
remove_nodes_from). Clean measurement (n=16000, m=96000 weighted, GC DISABLED during the timed region —
see below): remove_node(0) fnx 4.4-10.8ms vs nx 0.03ms = 0.003-0.007x (150-300x slower). remove_nodes_from
small-k similar. This is the "storage-model wall" — fnx pays ~O(|V|+|E|) per removal where nx pays
O(degree):

- DG/G (INTEGER-indexed, nodes: IndexMap, edges keyed by (usize,usize) or endpoint indices): removing ANY
  node forces an index RENUMBER — decrement every adjacency-row index > removed + rekey the whole edges
  map. PROVEN architectural: (a) removing an ISOLATED node (degree 0) still costs 2.2ms (pure renumber,
  no incident work); (b) index-INDEPENDENT — first/mid/last node all ~4.5-5.5ms; (c) weight-independent.
  nx's dict-of-dicts has no indices to renumber -> O(degree). This is the compact-integer-index tradeoff.
- MG/MDG (STRING-keyed adjacency, no integer renumber): isolated-node removal is FAST (0.02ms), but a node
  WITH incident edges costs 4-13ms. Weakly index-dependent (LAST node 4.4ms < FIRST 10.8ms — the
  nodes.shift_remove O(|V|-idx) shift shows through). The exact super-linear factor for incident-edge
  removal was not cleanly localized (candidates: per-incident adjacency shift_remove, edges-map ops).

WHAT'S ALREADY DONE (so this is NOT low-hanging): the PyO3 bindings already carry the adaptive
small-fraction mirror purge (br-r37-c1-mgrnf-incident: reconstruct incident mirror keys for small k
instead of O(|E|) whole-mirror retain) AND the batched single-pass inner remove_nodes_from
(br-r37-c1-d58s8: one renumber pass, not k). The residual is the INHERENT renumber/compaction cost of the
storage model, not a stray O(|E|) retain like the two remove_edge bombs.

LEVER (deferred, LARGE primitive): tombstone/slotmap node storage or DEFERRED compaction — don't renumber
on remove; free-list the slot and reuse on add; compact lazily. This is the "slotmap rewrite" flagged
across the ledger as the one remaining structural lever for the per-call mutation floor. High-risk
(touches core storage of all 4 types + every index consumer); NOT a clean single-session ship. Surfacing
with the measured decomposition so the next pass can scope it.

MEASUREMENT NOTE (load-bearing): benching node removal on 16k/96k WEIGHTED graphs (~100K Py<PyDict>
allocations per build) is GC-DOMINATED — naive timing swung 0.3ms..10ms for the SAME op. Must
`gc.collect(); gc.disable()` around the timed region (re-enable after) for a stable signal. Sibling of
[[feedback_maturin_stale_so_wrong_python]] / [[feedback_rch_bench_worker_noise]] — verify the substrate.

## 2026-07-02 CopperCliff SHIP: G[u][v] edge-attr access 0.04x->0.18x (4.5x self) — single-edge fast path, kill the O(degree) row-keydict build

Scale-probing attribute/access paths (fresh .venv binary, gc.disable()) surfaced the biggest CLEAN
per-call gap outside node removal: `G[u][v]` (edge attr dict access) was 0.040-0.057x vs nx (20-25x
slower), and `G[u][v]['k']=x` / `g.adj[u][v]` the same (both dominated by the `G[u][v]` getitem).
ROOT: AtlasView.__getitem__ (Python) served every access from the row KEYDICT, and a COLD keydict is
built by `_native_adjacency_row_dict(u)` = one PyO3 round-trip that materializes u's ENTIRE row
{nbr: edge_dict} (O(degree)). For the common `for u, v in G.edges(): G[u][v][...]` pattern every access
hits a distinct (cold) row -> O(degree) per single-edge access. Diagnosis: distinct G[u][v] 0.04x vs
SAME-edge-repeated 0.27x (warm keydict) vs get_edge_data 0.17x (single-edge native) -> the row build is
the cost.

FIX (br-r37-c1-atlasget): new native `_fnx_edge_attr_dict_fast(u, v)` on PyGraph + PyDiGraph — O(1)
single-edge live dict via the SHARED `materialize_edge_py_attrs` entry point (so identity + mutation
reflection are byte-identical to the keydict path; marks edges dirty exactly as `_native_adjacency_row_
dict` does). AtlasView.__getitem__ now: (a) serve from an ALREADY-WARM keydict (pure-Python, covers
iterated/repeated rows — no regression), else (b) single-edge fast path on cold access (skip the row
build), (c) keydict fallback for multigraph-inner / private-storage / view owners lacking the method.
Directed succ/adj rows pass (row_node, node); pred rows pass (node, row_node). RESULT: distinct G[u][v]
13-20us/access (O(degree)) -> 2.6-4.1us (flat O(1)); 0.04x -> 0.18x (G) / ~0.18x (DG), 4.5x self.
Residual 0.18x = the per-call node_key_to_string x2 + PyO3 crossing floor (same as get_edge_data/has_edge).
Byte-EXACT: 584/584 (identity G[u][v] is G[u][v] is get_edge_data, mutation reflection, KeyError(orig key)
on missing, TypeError on unhashable, DiGraph succ/pred direction, 30-trial warm+cold differential vs nx) +
3718 pytest (adjacency/atlas/edge-data/views/neighbors). MG/MDG use MultiAtlasView (unaffected). LEVER:
single-element view access falling to whole-row/collection materialization -> add an O(1) single-element
native getter that shares the materialization entry point (identity-safe), gate on a warm-cache check to
keep iteration parity. (Sibling of [[reference_single_arg_fastpath_extend_to_list]].)
NOTE: 1 pre-existing UNRELATED pytest failure (test_write_gexf...: find_induced_nodes/read_edgelist
classify NX_DELEGATED) — a policy regression-lock, not touched by this change.

## 2026-07-02 CopperCliff SURFACE: view-access family map after the G[u][v] win — MG[u][v] real gap (scoped), membership/DG[u] are ARTIFACTS

Followed the G[u][v] win (4e2a3cf72) into sibling view-access paths. Findings (fresh .venv binary,
gc.disable()):

CORRECTION (supersedes my first draft of this entry): I initially wrote that MG[u][v] BUILDS node u's
whole multi-adjacency row. THAT IS WRONG — `_native_adjacency_row(u)` (lib.rs:7103) is LAZY: it just
checks node existence and returns a `MultiAtlasView` (O(1)); `MultiAtlasView.__getitem__(v)` returns a
`MultiKeyDictView` (O(1), lib.rs:3711). No whole-row materialization anywhere on the MG[u][v] path.

ACCURATE finding — MG[u][v] / MDG[u][v] = 0.055-0.11x in the rebuild-per-rep probe, but that is NOT a
clean O(degree) crack like simple G[u][v]. Decomposed (build-once, steady-state): warm MG[u][v] ~1.5us
(~5x nx floor). The rebuild-per-rep "0.055x" is dominated by (a) the SAME one-time-per-graph
node_key_to_string warmup as membership below (first int->canonical on a fresh graph ~12us, node #2
~1us, then <0.75us — see the fresh-graph 200-distinct test = 0.73us/node), and (b) LAYERED PyO3 view-
object creation per access: AdjacencyView (MG[u]) -> MultiAtlasView (the lambda) -> MultiKeyDictView ->
AtlasView (MG[u][v]) = ~4-5 objects. Both are floors, not overbuilds. A real (but MODEST, risky)
follow-up: make `_multigraph_getitem_from_native_row` return the native MultiAtlasView directly (skip the
AdjacencyView+AtlasView wrapper layers so MG[u][v] -> native MultiKeyDictView, O(1) fewer objects) — but
that CHANGES type(MG[u]) AdjacencyView->MultiAtlasView and type(MG[u][v]) AtlasView->MultiKeyDictView, and
the Python override exists for a reason (native PyMultiGraph.__getitem__ at 7155 already returns
MultiAtlasView but was deliberately overridden). Must first establish WHY the override exists +
type-locks before touching. Low EV vs risk; DEFERRED.

ARTIFACTS — DO NOT CHASE (rebuild-per-rep benching captured one-time / measurement-floor costs):
- `n in G` / has_node MG/MDG "0.018x (7us)" and DG[u] "30us single access" are NOT per-call bombs. PROVEN
  one-time-per-graph warmup: on a FRESH MG, membership node #0 = 12.5us, #1 = 3.3us, #2 = 1.1us, #3 =
  0.73us; 200 DISTINCT first-touch nodes on a fresh graph = 0.73us/node (nx ~0.13us -> a ~5x per-call
  FLOOR, not 55x). The rebuild-fresh-graph-each-rep harness (correct for O(degree)/O(E) probes) pays that
  first-touch warmup EVERY rep so min() reports it as the per-call cost — MISLEADING for one-time costs.
  For those, build ONCE and measure steady-state. Single-op timing also has a ~15-30us perf_counter+
  gc.collect FLOOR (nx "17us" for one G[u] is the floor, not the op). (Third substrate trap this session;
  see [[reference_node_removal_storage_wall]] gc note + [[feedback_maturin_stale_so_wrong_python]].)
- neighbors() list = per-call node-key MATERIALIZATION floor (nx yields live adjacency-dict keys; fnx
  reconstructs degree PyObjects) — not a whole-row overbuild, genuine floor.

NET: the Python view-access family is now MINED (simple G[u][v] shipped 4e2a3cf72; MG[u][v]/neighbors/
membership are per-call PyO3/materialization floors or bench artifacts, not clean O(...) cracks). The only
architectural lever left across this family is the persistent ordered Python-object mirror (repeatedly
flagged) — a large primitive, not a single-session ship.

## 2026-07-02 CopperCliff SURFACE: correct-methodology broad sweep = fnx wins/parity everywhere; remaining gaps architectural + a CONSOLIDATED bench-substrate checklist

Broad head-to-head across untouched domains (conversions, IO serializers, operators, products, structural,
traversal). After correcting FIVE distinct measurement traps, the real result: fnx WINS or is at parity on
every non-architectural workload (to_pandas_adjacency 1.09x, to_numpy 1.1x, to_dict_of_dicts 1.7x,
complement 3.8x, bfs/dfs 2.6-2.9x, reverse 5.4x, difference simple 1.7-2.4x, disjoint_union 1.0-1.13x,
copy 1.7x, subgraph 1.4x). The ONLY sub-0.7x results are the already-documented architectural gaps:
- Multigraph union/compose/difference 0.45-0.76x = the nested-bucket construction tax (add_edges_from for
  Multi(Di)Graph ~0.70x — IndexMap<EdgeKey, IndexMap<key, AttrMap>> insertion vs nx dict-of-dict-of-dict).
  Partially mined (has_remapped_int_key mirror-skip, 7a49dd943/a6e8a9a0d); residual = extend_keyed_edges
  insertion. Simple Graph/DiGraph operators are at/near parity (0.76-2.4x). Next deep-dive candidate for
  /alien-graveyard (needs a profile of extend_keyed_edges first — is it hashing / order-maintenance /
  alloc?).
- Edge-attributed tensor/strong/lexicographic products 0.23-0.28x = "Rust dig" (per-element-pairing axis,
  each product edge pairs TWO factor edges — not decoratable). cartesian IS handled (0.98x, single-factor-
  edge decoration, dbce71884).

CONSOLIDATED BENCH-SUBSTRATE CHECKLIST (5 traps hit THIS session — every one made a non-gap look like a
gap or vice-versa; verify ALL before trusting a ratio):
1. WRONG BINARY: `python3` loads stale ~/.local .so; maturin installs to ./python. Use `.venv/bin/python`;
   assert `franken_networkx._fnx.__file__` + mtime. (feedback_maturin_stale_so_wrong_python)
2. GC NOISE: 100K-PyDict builds are GC-dominated (swung 0.3-10ms same op). gc.collect();gc.disable() around
   the timed region. (reference_node_removal_storage_wall)
3. REBUILD-PER-REP WARMUP: rebuilding the graph each rep pays one-time per-graph warmup (node_key_to_string
   first-touch ~12us) every rep -> min() reports it as per-call. For one-time costs build ONCE, measure
   steady-state. Single-op perf_counter+gc.collect has a ~15-30us FLOOR. (reference_atlasview...)
4. nx.X ON fnx GRAPH: for MODULE-level funcs, `nx.to_pandas_adjacency(fnx_graph)` runs REAL nx's impl over
   fnx's slow Python views (false 0.54x). Call `fnx.X(fnx_graph)` vs `nx.X(nx_graph)`. (Methods dispatch
   correctly.)
5. RANDOM SELF-LOOPS: `(randrange, randrange)` edges inject incidental self-loops that BAIL self-loop-gated
   fast paths (products, line_graph) -> false gaps. Use self-loop-free generators when testing those.
6. list(g.edges())[:k] in setup is O(|E|)-contaminated (fnx wins edges()) -> use pre-known edge lists.

NET: the value/mutation/view/conversion/IO/algorithm/operator veins are MINED. Real remaining levers are
all LARGE primitives: nested-bucket multigraph construction, edge-attr product pairing kernel, persistent
ordered Python-object mirror, tombstone/slotmap node storage. None is a clean single-session crack.

## 2026-07-02 CopperCliff /alien-graveyard dig on MG construction tax — clean number 0.80x, residual is ARCHITECTURAL nested-bucket (profiled, not strippable)

Per the meta-lesson (don't declare architectural without trying graveyard levers), profiled the multigraph
construction tax. CORRECTED clean number (self-loop-free, correct methodology): MG add_edges_from(12k) =
0.799x (2.49us/edge), MDG = 0.888x (2.42us/edge) — NOT the 0.45-0.70x my earlier parallel-edge-heavy +
operator-wrapper tests showed. Simple Graph = 1.664x (0.43us/edge), DiGraph = 1.684x — fnx WINS. So the
multigraph residual is 5x the per-edge cost of simple graphs. DIG RESULT: the extra cost is the NESTED
bucket level `edges: IndexMap<EdgeKey, IndexMap<key, AttrMap>>` + adjacency `IndexMap<node, IndexMap<nbr,
IndexSet<key>>>` — TWO nested inserts/edge vs simple Graph's flat maps. NOT a strippable tax: simple Graph
uses the SAME String node-keying + FxHash + PyDict->AttrMap collect and WINS, so the differentiator is
purely the parallel-edge-capable nested structure (which nx also pays as dict-of-dict-of-dict; fnx is 20%
slower on the nested build). The graveyard-reducible part (the redundant edge_py_keys mirror) was already
cracked (7a49dd943). No further avoidable per-edge work found — the 20% is the IndexMap-nested vs dict-
nested constant factor. VERDICT: architectural, low-EV; a native bulk-nested-builder (pre-sized, single
pass) MIGHT shave the constant but is high-effort for ~20%. Operators (union/compose/difference Multi*
0.45-0.76x) = this 0.80x construction + view-iteration wrapper overhead; same architectural root.
## 2026-07-02 CopperCliff CORRECTNESS FIX: DiGraph size/degree(weight) FLOAT on batch-built graphs returned edge COUNT -> flow_hierarchy went negative

Found via the public_api_gauntlet (its flow_hierarchy parity assertion FAILED: fnx=-2.54 vs nx=0.517).
ROOT: for a simple DiGraph built via the batch path (add_edges_from/add_weighted_edges_from >= 8 edges,
FLOAT weights), the inner CgseValue store correctly holds the float weights BUT the edge_py_attrs mirror is
left EMPTY (the fresh-int-attr batch, digraph.rs:8940, skips the eager mirror population the rest of
DiGraph assumes). `weighted_degree_exact_values` (digraph.rs:12306 — the float/exact degree fallback,
reached because weighted_size_int bails on non-int) read the weight value from `self.edge_py_attrs.get(ek)`
ONLY and defaulted to nx's int 1 on a mirror MISS: `None => one.clone()`. Mirror-empty batch graph => every
edge's weight read as 1 => degree(weight)/size(weight) returned the EDGE COUNT. size(weight) feeds
flow_hierarchy's total_weight denominator, so `1 - cyclic/total` with a too-small total went NEGATIVE
(-2.54). INT weights were unaffected (the int store twin weighted_degree_int_store_values reads the store).
Other 3 types (Graph/MultiGraph/MultiDiGraph) were correct (store twins / lazy-store-materialising paths).

FIX (br-r37-c1-degf-storemiss): on a mirror MISS, read the authoritative CgseValue store
(`self.inner.edge_attrs(u, v).get(weight)` -> cgse_value_to_py), defaulting to int 1 ONLY when the STORE
also lacks `weight` (nx's actual contract). A mirror miss means the edge was never exposed/edited (bulk
graph), so the store is current — safe even when edges_dirty (a pending edit would have mirrored the edge).
`weight` is always a str so the str-keyed store is authoritative (the non-str data-key paths at 12043/12149
correctly stay mirror-only). BYTE-EXACT: 149/149 (flow_hierarchy n=12..900 + size/degree/in_degree/
out_degree(weight) x Graph/DiGraph/MultiGraph/MultiDiGraph x batch sizes 8/10/20/50 x float/int/int-valued-
float + post-mutation dirty path) + 5525 pytest (degree/size/flow_hierarchy/weighted) + gauntlet
flow_hierarchy assertion now PASSES. No perf change (only the mirror-MISS arm reads the store now; the
mirror-hit path is untouched). degree(nbunch,weight) was already correct (index-store reads). CORRECTNESS
bug > perf: flow_hierarchy(weighted) went from a WRONG negative value to nx-exact.

## 2026-07-02 CopperCliff CORRECTNESS FIX: simple Graph/DiGraph batch add_edges_from ALPHABETISED multi-attr edge keys (nx = insertion order)

Found via the attr-preservation audit. AttrMap = BTreeMap<String,CgseValue> (sorted keys). Simple Graph/
DiGraph batch add_edges_from (>=8, fresh) left the edge_py_attrs mirror EMPTY, so edges(data)/get_edge_data
materialised MULTI-attr dicts from the sorted store -> alphabetical keys (alpha,color,cost,weight) vs nx's
insertion order (weight,cost,color,alpha). Per-edge add_edge and both multigraph types were correct (they
retain the ordered mirror; MultiDiIndexedAttrEdgeBatch already carried a Py<PyDict>, DiIndexedAttrEdgeBatch
did not). FIX (br-r37-c1-batchattrorder): the batch tuple now carries an Option<Py<PyDict>> ordered mirror,
populated ONLY for >=2-key dicts (single-key/weight-float stay mirror-free -> no perf cost) and stored in
edge_py_attrs (directed key raw, undirected canonicalised). DUPLICATE edges in a batch -> nx merges attrs
(dict.update); rather than replicate the multi-occurrence merge in the mirror, collect declines to the
per-edge path on any duplicate (seen-edges HashSet; directed (u,v), undirected canonical) — rare in a fresh
batch. Byte-exact 103/103 (order across 4 types x insertion orders x batch sizes + mixed single/multi + post-
mutation) + 27/27 test_add_edges_attr_batch_parity (3 were failing) + values unchanged (size/to_numpy/
flow_hierarchy). Perf: single-weight batch 1.56x, multi-attr 1.42x (both still BEAT nx). CORRECTNESS bug.

## 2026-07-02 CopperCliff CORRECTNESS FIX: Graph/MultiGraph batch add_nodes_from ALPHABETISED multi-attr NODE keys (node analog of the edge fix)

Found via the node-attr audit (sibling of the edge-attr-order fix). Same root: AttrMap=BTreeMap sorts keys.
Graph/MultiGraph `add_attr_node_batch` (br-r37-c1-lazynodeattr) DROPPED the ordered src mirror
(`nodes.into_iter().map(|(c,a,_)|(c,a))`) to save O(N) PyDict alloc, relying on lazy materialisation from
the sorted store -> nodes(data)/nodes[n] returned MULTI-attr node dicts alphabetically vs nx insertion
order. DiGraph/MultiDiGraph already carried the mirror (create empty dict + dict.update(src)) so they were
correct. FIX (br-r37-c1-batchattrorder): create+update the ordered mirror ONLY for MULTI-attr (>=2 key)
nodes (single-key/plain stay lazy -> single-attr construction stays at PARITY 0.96x); duplicate node in the
batch declines to the per-node path (nx merges via dict.update; seen-node HashSet). Byte-exact 58/58 (node
order x 4 types x insertion orders x batch sizes) + dup-node merge OK (all 4 types) + 4229 pytest + edge
order still 103/103. PERF: single-attr add_nodes_from 0.96x (was 0.73x with the over-eager first pass, now
parity), multi-attr 0.585x (the inherent double-storage cost — mirror for order + BTreeMap store for
kernels; nx keeps one dict). CORRECTNESS > perf; the common single-attr path is untouched.

## 2026-07-02 CopperCliff VERIFY (clean): mutation/attr layer byte-exact after the 3 correctness fixes — 80/80 metamorphic + 6th bench trap

After fixing flow_hierarchy (15099d2ff) + edge/node attr key-order (4c6c1fc80/bb6d5895d), ran a metamorphic
differential oracle: 80 random interleaved-op sequences (add/remove edge+node, set edge/node attr, on
batch-built multi-attr graphs) across all 4 types, comparing full structure (nodes(data), edges(keys,data),
adjacency, degree, size(weight)) to nx byte-for-byte -> 80/80 EXACT. Plus focused audits all clean:
relabel_nodes/graph-attrs/subgraph-views/node_link/adjacency_data/to_dict_of_dicts/graphml (38/38),
data-key edges/in_edges/out_edges(data=custom,default)/size/degree(custom weight)/post-mutation (60/60).
The mutation/attr layer is now certified byte-exact; the 3 shipped fixes closed the batch-mirror bug family
(sorted-order + mirror-miss-default). 6th BENCH-SUBSTRATE TRAP (differential-testing variant): calling
rng.randint() SEPARATELY for the fnx and nx graph in the same op (`gf.add_node(u,x=rng.randint());
gn.add_node(u,x=rng.randint())`) feeds DIFFERENT random values -> 78/80 false "divergences" that were all
value (not structure) mismatches. Compute the random value ONCE and use it for both graphs. Add to
[[reference_bench_substrate_checklist]].

## 2026-07-02 CopperCliff CORRECTNESS FIX (DATA LOSS): DiGraph pickle/deepcopy DROPPED all edge attributes for store-only edges

Found via the pickle round-trip audit. `PyDiGraph::__getstate__` (digraph.rs ~13568) built the edges list
from `inner.edges_ordered()` (correct order) but read each edge's attrs from `self.edge_py_attrs`
(the mirror) with `.map_or_else(|| PyDict::new(py), ...)` -> a MISSING mirror entry defaulted to an EMPTY
dict. Non-fresh / bulk `add_edges_from` stores attrs in the CgseValue store and leaves the mirror EMPTY
(e.g. `add_nodes_from(attrs)` THEN `add_edges_from(attrs)` — the node insert makes the graph non-fresh so
the edge batch declines the mirror-populating fast path). Result: `pickle.loads(pickle.dumps(G))` /
`copy.deepcopy(G)` returned EVERY edge as `{}` — total edge-attr DATA LOSS. The LIVE graph was fine
(edges(data) materialises from the store); only the SERIALIZED state dropped them. Simple DiGraph ONLY —
Graph/MultiGraph/MultiDiGraph __getstate__ already read the store. FIX (br-r37-c1-getstate-storemiss): on a
mirror miss, materialise from the store's AttrMap (edge.attrs from edges_ordered) via attr_map_to_pydict
instead of an empty dict. Byte-exact: pickle+deepcopy x 4 types x nodes-first/edges-first ALL OK + 20/20
pickle audit (self-loop/parallel/multi-attr) + 1576 pickle/serialization pytest. Same mirror-vs-store bug
class as flow_hierarchy (15099d2ff) but in the pickle serializer, and the WORST symptom yet (silent data
loss on a std pickle/deepcopy). CORRECTNESS.

## 2026-07-02 CopperCliff CORRECTNESS FIX: EXISTING-NODES batch add_edges_from also alphabetised multi-attr edge keys (from_dict_of_dicts / nodes-first)

The batch edge-order fix (4c6c1fc80) only covered the FRESH batch (node_count==0). The EXISTING-NODES index
batches — try_add_existing_exact_int_attr_edge_index_batch + try_add_existing_int_label_attr_edge_batch
(lib.rs 1499/1613, digraph.rs 9082), used when nodes are pre-added (add_nodes_from(range) THEN
add_edges_from, i.e. from_dict_of_dicts / convert_node_labels_to_integers / contracted_nodes / ego_graph /
induced_subgraph.copy) — still stored multi-attr edges to the sorted BTreeMap store with NO ordered mirror
("attrs stay LAZY... matching the fresh path" — but the fresh path was since fixed). So those transforms
returned edges(data) with ALPHABETISED keys (cap,name,weight) vs nx (weight,cap,name). Simple Graph/DiGraph
only (multigraphs kept order). FIX (br-r37-c1-batchattrorder): the 3 existing-nodes collects DECLINE on a
>=2-key dict -> the dispatcher falls through to collect_attr_edge_batch (which retains the ordered mirror
via create+update). Single-key/empty stay on the fast index path. Byte-exact: transform audit 30/30
(convert_node_labels/contracted_nodes/ego_graph/induced_subgraph/relabel/freeze x 4 types) + 8229 pytest.
PERF: single-attr from_dict_of_dicts 1.20x (unchanged); MULTI-attr from_dict_of_dicts 0.376x (REGRESSED from
~1.2x — the decline routes multi-attr to the ~4x-slower String-keyed collect_attr_edge_batch). CORRECTNESS
> perf, narrow case (multi-attr from_dict). FOLLOW-UP (scoped): retain the ordered mirror IN the index batch
(thread Option<Py<PyDict>> for >=2-key, store under the int-label key) to recover the fast path — same
pattern as the fresh-batch fix, avoids the decline.

## 2026-07-02 CopperCliff PERF-RECOVERY (of my own regression): exact-int existing-nodes batch retains ordered mirror — Graph from_dict multi-attr 0.376x->0.685x

The prior commit (87499b300) fixed the existing-nodes multi-attr order bug by DECLINING >=2-key dicts to
the slow String-keyed collect_attr_edge_batch (Graph multi-attr from_dict_of_dicts dropped to 0.376x).
Recovered the common contiguous-int path (from_dict_of_dicts of a 0..n graph, convert_node_labels) by
RETAINING the ordered mirror IN the exact-int index batch (collect_existing_exact_int_attr_edge_indices +
try_add_existing_exact_int_attr_edge_index_batch, lib.rs): thread Option<Py<PyDict>> for >=2-key dicts
(py_dict_to_attr_map_with_mirror), store under the canonical edge_key (label==index for the contiguous
prefix), + duplicate-edge decline (seen-set). Single-key/empty stay mirror-free (no order cost). RESULT:
Graph from_dict_of_dicts multi-attr 0.376x -> 0.685x (1.8x recovery; residual < nx = the per-multi-attr-edge
ordered-mirror creation, same inherent cost as the fresh-batch multi-attr path). Byte-exact: transform audit
30/30 + 5677 pytest. NOTE: DiGraph (int-label index batch, digraph.rs 9082) + Graph scrambled-int
(int-label, lib.rs 1613) still DECLINE multi-attr (0.376x) — narrower cases; the same retain-mirror
(key from the int label, not index) is the remaining scoped follow-up.

## 2026-07-02 CopperCliff PERF-RECOVERY complete: int-label existing-nodes batches retain ordered mirror — DiGraph from_dict multi-attr 0.376x->0.672x

Completed the batch-attr-order family. The remaining int-label existing-nodes batches (Graph scrambled-int
lib.rs 1644, DiGraph any-int digraph.rs 9082 — DiGraph has NO exact-int batch so ALL its from_dict/
convert_node_labels multi-attr went through here) were still DECLINING >=2-key dicts (0.376x). Applied the
retain-mirror pattern: thread Option<((String,String),Py<PyDict>)> (the canonical/directed LABEL pair as the
key, since label != index for these batches) via py_dict_to_attr_map_with_mirror, store in edge_py_attrs;
single-key/empty stay lazy; duplicate-edge decline (seen-set). RESULT: DiGraph from_dict_of_dicts multi-attr
0.376x -> 0.672x; Graph scrambled-int likewise; order byte-exact (DiGraph/Graph-scrambled nodes-first =
insertion order). Transform audit 30/30 + 6507 pytest. The ENTIRE batch-attr-order family (fresh +
existing-exact-int + existing-int-label, edges + nodes, Graph+DiGraph) now preserves nx insertion order at
~0.67-1.2x (multi-attr pays the inherent ordered-mirror creation; single-attr unchanged and >=nx). Bug
family CLOSED.

## 2026-07-02 CopperCliff CORRECTNESS FIX (DATA LOSS): Graph/MultiGraph pickle/deepcopy DROPPED single-attr NODE attributes

Node analog of the DiGraph edge pickle data-loss (5bfc143f2). PyGraph + PyMultiGraph __getstate__ (lib.rs
~8842/12848) read each node's attrs from node_py_attrs (mirror) with map_or_else(|| PyDict::new(py)) ->
EMPTY dict on a miss. After the node-attr-order fix (bb6d5895d), Graph/MultiGraph only eagerly mirror
MULTI-attr (>=2 key) nodes; SINGLE-attr nodes stay LAZY in the store with no mirror entry. So
pickle.loads(pickle.dumps(G)) / copy.deepcopy(G) returned every node as {} for single-attr batch-built
nodes — e.g. add_nodes_from([(i,{'p':i})]) or convert_node_labels_to_integers -> pickle -> node attrs GONE.
DiGraph/MultiDiGraph were fine (their node batch eagerly mirrors ALL nodes). FIX (br-r37-c1-getstate-
storemiss): on a node-mirror miss, materialise from the store's node AttrMap (self.inner.node_attrs) via
attr_map_to_pydict instead of an empty dict. Byte-exact: single-attr node pickle x 4 types OK + pickle2
audit 32/32 (nodes-first/from_dict/single-attr/convert_labels x pickle+deepcopy x 4 types) + 1632 pickle/
serialization pytest. Third mirror-miss instance (degree/flow_hierarchy, DiGraph edge pickle, now
Graph/MG node pickle); the __getstate__ EDGE sections already read the store (single-attr edge pickle was
fine). CORRECTNESS (silent data loss).
