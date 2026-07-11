# br-r37-c1-turanbatch — turan_graph batch-by-index edge insertion

Status: **SHIP.** 16.22x, byte-identical. clippy clean. Second supersession of the 2026-06-25 surface.

## The target

`turan_graph(n, r)` is complete-multipartite with `r` near-equal partitions. The edge loop connected
every cross-partition pair via per-edge `add_edge(node_labels[left].clone(), node_labels[right].clone())`
(2 String clones + 2 name→index hashes + policy), nodes pre-exist (`graph_with_n_nodes`).

## The lever

Identical to complete_multipartite (br-r37-c1-cmpbatch): collect the cross-partition `(left, right)`
INDEX pairs and batch-insert with `Graph::extend_existing_index_edges_unrecorded`. Deterministic, no RNG.

## Supersedes the 2026-06-25 surface (again)

`turan_graph 0.75x` was one of the "dense generators NOT improvable by batching, construction-floor-bound"
cluster (Python `add_edges_from` level). The engine per-edge path was never batched — batching it removes
the dominant clones/hashes/policy → 16.22x (even higher than complete_multipartite's 13.24x).

## Byte-identical argument

All nodes pre-exist; cross-partition pairs unique + no self-loops. `extend_existing_index_edges_unrecorded`
canonicalizes endpoints by name-order + pushes `adj_indices` exactly as `add_edge`; edges collected in the
same partition-pair order. Verified with UNEQUAL partitions (turan(1000,3) → sizes 333/333/334):
`assert_eq!(batch.edges_ordered_borrowed(), string.edges_ordered_borrowed())` + `nodes_ordered`; the
suite's turan vs-nx tests pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib turan_batch_ab -- --ignored --nocapture`

turan(1000, 3) (partitions 333/333/334, ~333k cross edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **16.2181x** | 61/61 | [9.3470, 27.4042] |
| `NULL_batch_vs_batch` | 0.9785x | 28/61 | [0.8518, 1.1491] |

Decisive: candidate p5 (9.35) ~8x above the NULL p95 (1.15); all 61 rounds won.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `turan_graph`.
- Test-only: `turan_batch_ab` A/B.

## Vein status

Fourth engine-level generator batch win (gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan
16.22x); barabasi 1.04x surfaced. The 2026-06-25 "dense generators floor-bound" cluster is being
systematically superseded. Next: `ring_of_cliques`, `stochastic_block_model`, `random_partition_graph`
(same cluster — profile per-edge + insertion-bound); `gnm_random_digraph` (directed).
