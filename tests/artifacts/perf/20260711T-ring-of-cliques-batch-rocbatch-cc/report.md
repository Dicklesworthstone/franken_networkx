# br-r37-c1-rocbatch — ring_of_cliques batch-by-index edge insertion

Status: **SHIP.** 19.94x, byte-identical. clippy clean. 3rd supersession of the 2026-06-25 surface.

## The target

`ring_of_cliques(num_cliques, clique_size)` builds `num_cliques` complete cliques, each connected to the
next by one ring edge. The edge loop used per-edge `add_edge(node_labels[left].clone(),
node_labels[right].clone())` (2 clones + 2 name→index hashes + policy) for both the clique edges and the
per-clique ring edge; nodes pre-exist (`graph_with_n_nodes`). Deterministic (no RNG) → insertion-bound.

## The lever

Collect all `(left, right)` INDEX pairs — clique edges then the cross-clique ring edge, per clique, in
the SAME order — and batch-insert with `Graph::extend_existing_index_edges_unrecorded`.

## Byte-identical argument

Nodes pre-exist. Clique edges `(left, right)` with left<right are unique within a clique; the ring edge
`(start+1, next_start)` is cross-clique (never a clique edge, distinct source per clique) → no
duplicates, no self-loops. `extend_existing_index_edges_unrecorded` canonicalizes endpoints by name-order
+ pushes `adj_indices` exactly as `add_edge`; edges collected in the same clique-then-ring order. Even if
a duplicate existed, both paths skip it via `edges.contains_key`. Verified:
`assert_eq!(batch.edges_ordered_borrowed(), string.edges_ordered_borrowed())` + `nodes_ordered`; the
suite's ring_of_cliques vs-nx tests pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib ring_of_cliques_batch_ab -- --ignored --nocapture`

100 cliques × 50 (5000 nodes, 122600 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **19.9437x** | 61/61 | [15.6427, 29.3978] |
| `NULL_batch_vs_batch` | 0.9969x | 29/61 | [0.3570, 1.5722] |

Decisive: candidate p5 (15.64) ~10x above the NULL p95 (1.57); all 61 rounds won.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `ring_of_cliques`.
- Test-only: `ring_of_cliques_batch_ab` A/B.

## Vein status

Fifth engine-level generator batch win (gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan
16.22x, ring_of_cliques 19.94x); barabasi 1.04x surfaced. 3rd supersession of the 2026-06-25
"dense generators floor-bound" cluster. Remaining: `stochastic_block_model`, `random_partition_graph`
(the last two — SBM/random_partition are RNG-per-edge, so PROFILE the sampling-vs-insertion split first).
