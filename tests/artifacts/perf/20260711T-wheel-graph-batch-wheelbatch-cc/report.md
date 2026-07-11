# br-r37-c1-wheelbatch — wheel_graph batch-by-index edge insertion

Status: **SHIP.** 24.28x, byte-identical. clippy clean.

## The target

`wheel_graph(n)` builds a hub (node 0) joined to every rim node, plus a cycle over the `n-1` rim nodes.
The native builder used per-edge `add_edge(node_labels[left].clone(), node_labels[right].clone())`; all
nodes pre-exist (`graph_with_n_nodes`). Deterministic (no RNG) → insertion-bound.

## The lever

Collect the `(left, right)` INDEX pairs in the SAME order (hub spokes `(0, rim)`, then the rim path,
then the closing rim edge) and batch-insert with `Graph::extend_existing_index_edges_unrecorded`. Drops
per accepted edge: 2 String clones + 2 name→index hashes + 1 runtime-policy record.

## Byte-identical argument

Hub spokes `(0, i)` for `i in 1..n` are unique and disjoint from the rim edges (which never touch node
0). The rim path `(1,2),(2,3),…,(n-2,n-1)` plus the closing edge `(1, n-1)` form a simple cycle over
the rim — all unique, no self-loops. So every produced pair is unique with no self-loop.
`extend_existing_index_edges_unrecorded` canonicalizes endpoints by name-order and pushes `adj_indices`
exactly as `add_edge`; edges collected in the identical order. Verified:
- A/B cross-branch parity: `assert_eq!(edges_ordered_borrowed + nodes_ordered)` of batch vs per-edge for
  n = 2, 3, 4, 100, 100000 (covers n≤1 / n==3 / n>3 branches) — all pass.
- Suite exact-vs-nx: `wheel_graph_matches_networkx_hub_and_rim_for_n_six` (n=6) and
  `wheel_graph_matches_networkx_small_n_behavior` (small n) both pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib wheel_batch_ab -- --ignored --nocapture`

wheel(100000) (100000 nodes, 199998 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **24.2788x** | 61/61 | [11.8570, 36.5300] |
| `NULL_batch_vs_batch` | 1.0153x | 37/61 | [0.8655, 1.2048] |

Decisive: candidate p5 (11.86) ~9.8x above the NULL p95 (1.20); all 61 rounds won. Highest-magnitude
generator batch win of the session — the star hub means the per-edge arm pays heavy String clone/hash on
node 0 for every spoke; the batch drops all of it.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `wheel_graph`.
- Test-only: `wheel_batch_ab` A/B.

## Vein status

Thirteenth engine-level generator batch win (gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan
16.22x, ring_of_cliques 19.94x, windmill 18.63x, caveman 3.86x, barbell 16.92x, lollipop 13.29x,
tadpole 7.10x, hkn_harary 19.86x, hypercube 6.47x, wheel 24.28x); barabasi 1.04x surfaced. Next clean
candidates: `binomial_tree`, `grid_2d_graph`/`grid_graph`, `generalized_petersen_graph`.
