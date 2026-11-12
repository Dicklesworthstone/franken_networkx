# br-r37-c1-gridnbatch — grid_graph (n-dimensional) batch-by-index edge insertion

Status: **SHIP.** 5.47x, byte-identical. clippy clean.

## The target

`grid_graph(dim, periodic)` builds the n-dimensional grid over `∏dim` nodes carrying reversed-axis grid
labels, with a forward edge along each axis plus optional periodic wraps. The native builder used per-edge
`add_edge(labels[index].clone(), labels[target_index].clone())`; nodes pre-exist (added in index order).
Deterministic (no RNG) → insertion-bound.

## The lever

Collect the `(index, target_index)` INDEX pairs in the SAME `(index, axis)` emission order and batch-insert
with `Graph::extend_existing_index_edges_unrecorded`. Drops per accepted edge: 2 String clones +
2 name→index hashes + 1 runtime-policy record.

## Byte-identical argument (no seen-set needed)

Forward edges (`coordinate+1`) are all unique. The `axis_size == 2` periodic case is guarded to `None`
(a wrap there would duplicate the single interior edge), and the `axis_size >= 3` wrap goes to coordinate
0 (distinct from the interior forwards). An `axis_size == 1` periodic axis emits one **unique** self-loop
per node (`target == coordinates`). So every produced pair is unique — no dedup needed — and self-loop
handling is byte-identical (proven by the sibling circulant win).
`extend_existing_index_edges_unrecorded` matches `add_edge`'s endpoint canonicalization and `adj_indices`
order. Verified:
- A/B parity across 6 configs — `([3,4],FF)`, `([3,4],TT)`, `([2,4],TT)` (size-2 guard), `([1,4],TF)`
  (size-1 periodic self-loops), `([3,3,3],TTT)`, `([100,100,10],FFF)` — all pass.
- Suite exact-vs-nx: `grid_graph_two_dimensional_integer_dims_match_networkx_reversed_labels`,
  `grid_graph_three_dimensions_match_networkx_counts_and_edges`,
  `grid_graph_periodic_scalar_matches_networkx_cycle_axes`, plus the empty/1D/invalid-policy cases — all pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib grid_n_batch_ab -- --ignored --nocapture`

grid_graph([100,100,10], non-periodic) (100000 nodes). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **5.4715x** | 61/61 | [4.7989, 6.4594] |
| `NULL_batch_vs_batch` | 1.0073x | 34/61 | [0.8544, 1.2018] |

Decisive: candidate p5 (4.80) ~4.0x above the NULL p95 (1.20); all 61 rounds won.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `grid_graph`.
- Test-only: `grid_n_batch_ab` A/B.

## Vein status

Nineteenth engine-level generator batch win; completes the grid family (grid_2d 4.08x + grid_graph 5.47x).
Vein: gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan 16.22x, ring_of_cliques 19.94x, windmill
18.63x, caveman 3.86x, barbell 16.92x, lollipop 13.29x, tadpole 7.10x, hkn_harary 19.86x, hypercube 6.47x,
wheel 24.28x, binomial_tree 6.96x, grid_2d 4.08x, circulant 17.37x, generalized_petersen 6.13x, hnm_harary
8.24x, grid_graph 5.47x; barabasi 1.04x surfaced. Last remaining seen-set candidate: `sudoku_graph`.
