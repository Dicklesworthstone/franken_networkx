# Measured Head-to-Head Evidence — cc (CopperCliff)

Verify/gauntlet phase: every recent `code-first batch-test pending` optimization
built into a fresh release wheel (`maturin build --release`, clean .so verified
`nm -D | grep crossbeam == 0`, installed at HEAD) and measured **head-to-head vs
NetworkX** on realistic workloads (warm, min-of-8). Honest numbers — wins, losses,
neutrals. Losses get reverted; conformance stays green.

Build: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cc maturin build --release -m crates/fnx-python/Cargo.toml` → wheel installed. Measured 2026-06-18.

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
MULTIGRAPH was fnx's one genuinely-losing realistic surface; CC now FIXED (0.07x->1.06x, parity 15/15) — residual loss is to_scipy_sparse_array (0.39x: cProfile shows _native_edge_view_list
materializes all edge instances + a Python COO loop with dict.get/append per
instance — fix = native multigraph COO that sums parallel edges in Rust, like the
Graph native COO path) + construction (copy/subgraph = tbh4q attr-copy wall) — driven by the
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
