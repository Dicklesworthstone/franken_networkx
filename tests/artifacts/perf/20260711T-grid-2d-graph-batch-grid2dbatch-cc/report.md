# br-r37-c1-grid2dbatch — grid_2d_graph batch-by-index edge insertion

Status: **SHIP.** 4.08x, byte-identical. clippy clean.

## The target

`grid_2d_graph(m, n, periodic)` builds the m×n grid on `m*n` nodes carrying `(row, col)` tuple labels,
with vertical + horizontal interior edges and optional periodic wrap edges on each axis. The native
builder used per-edge `add_edge(labels[…].clone(), labels[…].clone())`; nodes pre-exist (added row-major,
so index `= row*n + col`). Deterministic (no RNG) → insertion-bound.

## The lever

Collect the `(left, right)` INDEX pairs in the SAME order (verticals, horizontals, row-wrap, col-wrap)
and batch-insert with `Graph::extend_existing_index_edges_unrecorded`. Drops per accepted edge: 2 String
clones + 2 name→index hashes + 1 runtime-policy record.

## Byte-identical argument

Interior vertical/horizontal edges are all distinct with no self-loops. The only dedup risk is a periodic
wrap over a 2-wide axis (the wrap `(0,c)–(m-1,c)` would coincide with the single interior edge when
`m == 2`) — but the builder already guards the wraps with `m > 2` / `n > 2`, so no wrap ever duplicates an
interior edge. Hence every produced pair is unique with no self-loop.
`extend_existing_index_edges_unrecorded` canonicalizes endpoints by node *name* (identical to `add_edge`,
so the `(row, col)` label sort order is irrelevant) and pushes `adj_indices` in the same order. Verified:
- A/B parity across 8 configs — `(5,7)` in all four periodic modes, plus the guard cases `(2,7,TT)`,
  `(7,2,TT)`, `(2,2,TT)`, and the `(300,300,FF)` timing config — all pass.
- Suite exact-vs-nx: `grid_2d_graph_periodic_axes_add_networkx_wrap_edges` and
  `grid_2d_graph_small_periodic_dimensions_do_not_duplicate_edges` (the exact guard case) both pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib grid_2d_batch_ab -- --ignored --nocapture`

grid_2d(300, 300, non-periodic) (90000 nodes, 179400 edges). 61 rounds. Ratio = base/cand, **>1 = batch
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **4.0803x** | 61/61 | [3.2183, 5.0429] |
| `NULL_batch_vs_batch` | 0.9845x | 27/61 | [0.7943, 1.1356] |

Decisive: candidate p5 (3.22) ~2.8x above the NULL p95 (1.14); all 61 rounds won. Lower magnitude than
short-label generators because the long `(row, col)` labels make the name-order canonicalization compare
costlier in both arms; the win is the dropped clones/hashes/policy.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `grid_2d_graph`.
- Test-only: `grid_2d_batch_ab` A/B.

## Vein status

Fifteenth engine-level generator batch win (gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan
16.22x, ring_of_cliques 19.94x, windmill 18.63x, caveman 3.86x, barbell 16.92x, lollipop 13.29x,
tadpole 7.10x, hkn_harary 19.86x, hypercube 6.47x, wheel 24.28x, binomial_tree 6.96x, grid_2d 4.08x);
barabasi 1.04x surfaced. The clean (no-dedup) generator vein is nearing exhaustion — remaining members
(generalized_petersen k=n/2, hnm_harary, sudoku, circulant) all require a gnm-style seen-set for the
duplicate pairs.
