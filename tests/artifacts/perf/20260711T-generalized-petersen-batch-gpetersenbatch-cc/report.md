# br-r37-c1-gpetersenbatch — generalized_petersen_graph batch-by-index (seen-set)

Status: **SHIP.** 6.13x, byte-identical. clippy clean.

## The target

`generalized_petersen_graph(n, k)` (validation `n>=3`, `1<=k<=n/2`) builds GP(n,k): an outer n-cycle,
n spokes, and an inner circulant with shift k. The native builder emitted, per `i`, the outer edge, the
spoke, then the inner edge via per-edge `add_edge(node_labels[…].clone(), …)`; all nodes pre-exist
(`graph_with_n_nodes`). Deterministic (no RNG) → insertion-bound.

The outer/spoke edges are always unique, but the inner circulant `(n+i, n+((i+k)%n))` **duplicates** each
edge when `2k == n` (i.e. `k == n/2`, n even — e.g. GP(4,2), GP(6,3)). So this is a seen-set member.

## The lever

Collect the `(u, v)` INDEX pairs with a gnm-style integer seen-set — canonical `(min,max)` key,
skip-if-seen, first-occurrence order — in the SAME emission order (outer, spoke, inner per i), then one
`Graph::extend_existing_index_edges_unrecorded`. No self-loops occur (`n>=3`, `k>=1`).

## Byte-identical argument

The seen-set reproduces `add_edge`'s dedup exactly (a simple graph ignores a repeated edge, keeping the
first occurrence). Only the inner circulant can duplicate, and only at `k==n/2`.
`extend_existing_index_edges_unrecorded` matches `add_edge`'s endpoint canonicalization and `adj_indices`
order (self-loop/dedup handling already proven byte-identical by the sibling circulant win). **Verified
profile-first** (before the production edit): `gpetersen_batch_ab` parity asserts across 6 configs —
including the `k==n/2` inner-dup cases GP(4,2), GP(6,3), GP(8,4) — all `assert_eq!(edges_ordered_borrowed
+ nodes_ordered)` pass. Suite exact-vs-nx: `generalized_petersen_graph_matches_networkx_petersen_case`,
`…_boundary_case`, `petersen_graph_matches_networkx_edges_and_degrees`,
`kneser_graph_generation_order_matches_networkx_petersen_case` all pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib gpetersen_batch_ab -- --ignored --nocapture`

GP(40000, 3) (80000 nodes, 120000 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **6.1290x** | 61/61 | [2.3962, 7.9258] |
| `NULL_batch_vs_batch` | 1.0166x | 37/61 | [0.6094, 1.2553] |

Decisive: candidate p5 (2.40) above the NULL p95 (1.26); all 61 rounds won. GP is cubic/sparse so the
construction is fast and timing noisier (wider spread), but the separation is clean.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `generalized_petersen_graph`.
- Test-only: `gpetersen_batch_ab` A/B.

## Vein status

Seventeenth engine-level generator batch win (second seen-set member). Vein: gnp 13.20x, gnm 8.55x,
complete_multipartite 13.24x, turan 16.22x, ring_of_cliques 19.94x, windmill 18.63x, caveman 3.86x,
barbell 16.92x, lollipop 13.29x, tadpole 7.10x, hkn_harary 19.86x, hypercube 6.47x, wheel 24.28x,
binomial_tree 6.96x, grid_2d 4.08x, circulant 17.37x, generalized_petersen 6.13x; barabasi 1.04x
surfaced. Remaining seen-set candidates: `hnm_harary_graph`, `sudoku_graph`, `grid_graph`.
