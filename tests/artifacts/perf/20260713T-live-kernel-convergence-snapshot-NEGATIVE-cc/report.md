# Live-kernel convergence snapshot — NEGATIVE (cc, 2026-07-13)

Reachability-verified sweep of the LIVE fast-path kernels (traced `.py` → binding → exact kernel,
ruling out `*_fast` bypass per the trap that burned prodnodebatch this session). Every one is already
optimal. Recorded so the next turn skips re-checking these and goes straight to the real frontier.

## Verified LIVE + already optimal this turn (do not re-mine)

| public op | live path | state |
|---|---|---|
| cartesian/tensor/strong/lexicographic product | `_native_graph_product` → `graph_product_fast` (algorithms.rs 15894) | node+edge batched (`extend_nodes_unrecorded` + `extend_edges_unrecorded`) |
| corona/modular/rooted product | `*_product_fast` (16283/16346/16407) | node+edge batched |
| line_graph(+directed) | `_fnx.line_graph_fast` (16623) | node+edge batched |
| square_clustering(+subset) | `square_clustering_fast` → `square_clustering_pairs_for` (41292) | integer-adjacency stamp-array kernel (sqclsub) |
| difference/intersection/sym_diff | `G._native_difference` (natdiff / natdiffsimple / cc-mgnatdiff-identity) | fully native, no Python edge materialization |
| bipartite projected_graph | native adjacency snapshot (bpproj) | de-delegated, direct build |
| random_geometric / soft_rgg / … | `_fnx.geometric_pairs_grid` (nt3co) | safe-Rust spatial-grid candidate gen (not O(N²)) |
| hopcroft_karp / maximum_matching | `_native_hopcroft_karp` (bngez/hknotop) | index kernel, no fnx→nx conversion |
| k_core / k_shell / k_crust / k_corona | native route (kcorenative/kshellnative, THIS session) | native subgraph build |
| is_isomorphic edge-count early-out | `edge_count()` (isoedgecount, THIS session) | O(1) |

The plain (non-fast) product/line_graph kernels `fnx_algorithms::{cartesian_product,tensor_product,
line_graph}` are DEAD (see 20260713T-product-linegraph-plain-kernels-dead-NEGATIVE-cc); their bindings
are registered but the `.py` routes to the `*_fast` siblings above.

## Dead kernels catalogued this session (never optimize — false-win class)

greedy_color non-largest_first branches; max_clique_approx / find_cliques / find_cliques_recursive
(Python reimplements for nx set-order parity); relabel_nodes / moral_graph / write_graphml_string_*
kernels (Python or fnx-readwrite path); plain product/line_graph kernels. See the four
`*-dead-NEGATIVE-cc` ledgers + [[pyo3_wrapper_can_itself_be_dead]] (now with the `*_fast`-bypass rule).

## THE remaining real frontier (NOT a clean one-turn increment)

The only LIVE head-to-head LOSSES are the String-keyed MultiGraph floor — mg_selfloop ~0.262x,
mdg_out_edges ~0.391x, etc. ([[h2h_loss_cluster_is_intadj_floor]]). The fix is the MultiGraph
INTEGER-ADJACENCY epoch ([[thp6w6_multigraph_intadj_epoch]]): S1+S2 shipped; S3 (index-pair edge
representation flip for mg_selfloop / mdg_out_edges) is the remaining BIG architectural slice — a
multi-turn epoch, likely coordinated, not a small single-turn lever. Other residual headroom
(binding-layer constant factors like centrality_to_dict throwaway to_owned) is floor-dominated and
needs a `Python::with_gil` A/B harness before it can even be gated.

## Net

The reachable, deterministic, clean small-increment perf surface for the cc lane is CONVERGED. Next
productive work is architectural (MultiGraph int-adjacency S3) or infra (with_gil binding A/B harness),
not another scan/materialization/batch swap. Verify `.py` reachability (incl. `*_fast` sibling) BEFORE
any kernel A/B.
