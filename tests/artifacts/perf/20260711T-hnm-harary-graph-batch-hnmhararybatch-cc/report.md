# br-r37-c1-hnmhararybatch — hnm_harary_graph batch-by-index (seen-set)

Status: **SHIP.** 8.24x, byte-identical. clippy clean.

## The target

`hnm_harary_graph(n, m)` builds the Harary graph H_{n,m}: a circulant of `offset = ⌊2m/n⌋/2` shifts, plus
(depending on parity) a diameter matching and/or a partial "remainder" shell (shift `offset+1`), or a
partial half-shift shell. The native builder emitted these via per-edge `add_edge(node_labels[…].clone(),
…)`; all nodes pre-exist (`graph_with_n_nodes`). Deterministic (no RNG) → insertion-bound.

The remainder/matching shells can overlap the circulant and each other, so this is a seen-set member.

## The lever

Collect the `(u, v)` INDEX pairs with a gnm-style integer seen-set — canonical `(min,max)` key,
skip-if-seen, first-occurrence order — in the SAME emission order (circulant, then matching, then
remainder/remaining), then one `Graph::extend_existing_index_edges_unrecorded`.

## Byte-identical argument

The seen-set reproduces `add_edge`'s dedup exactly. `extend_existing_index_edges_unrecorded` matches
`add_edge`'s endpoint canonicalization, `adj_indices` order, and self-loop/dedup handling (proven by the
sibling circulant win). **Verified profile-first** (before the production edit): `hnm_harary_batch_ab`
parity asserts across 6 configs covering every branch shape — n even/odd × degree_floor even/odd, plus
the remainder shell — `(10,15)`, `(10,20)`, `(9,9)`, `(9,14)`, `(11,17)`, `(50000,250000)` — all
`assert_eq!(edges_ordered_borrowed + nodes_ordered)` pass. Suite exact-vs-nx:
`hnm_harary_graph_even_order_remainder_matches_networkx_edges` (the remainder branch vs nx) passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib hnm_harary_batch_ab -- --ignored --nocapture`

hnm_harary(50000, 250000) (50000 nodes, ~250000 edges, degree_floor 10). 61 rounds. Ratio = base/cand,
**>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **8.2428x** | 61/61 | [6.3175, 10.0339] |
| `NULL_batch_vs_batch` | 0.9974x | 30/61 | [0.8048, 1.1847] |

Decisive: candidate p5 (6.32) ~5.3x above the NULL p95 (1.18); all 61 rounds won.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `hnm_harary_graph`.
- Test-only: `hnm_harary_batch_ab` A/B.

## Vein status

Eighteenth engine-level generator batch win (third seen-set member). Completes the Harary pair (hkn 19.86x
+ hnm 8.24x). Vein: gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan 16.22x, ring_of_cliques
19.94x, windmill 18.63x, caveman 3.86x, barbell 16.92x, lollipop 13.29x, tadpole 7.10x, hkn_harary 19.86x,
hypercube 6.47x, wheel 24.28x, binomial_tree 6.96x, grid_2d 4.08x, circulant 17.37x, generalized_petersen
6.13x, hnm_harary 8.24x; barabasi 1.04x surfaced. Remaining seen-set candidates: `sudoku_graph`,
`grid_graph`.
