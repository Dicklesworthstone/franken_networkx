# br-r37-c1-cmpbatch — complete_multipartite_graph batch-by-index edge insertion

Status: **SHIP.** 13.24x, byte-identical. clippy clean. Supersedes a stale 2026-06-25 surface.

## The target

`complete_multipartite_graph(subset_sizes)` (fnx-generators) connects every cross-partition node pair.
The edge loop did `graph.add_edge(node_labels[left].clone(), node_labels[right].clone())` per edge —
2 String clones + 2 name→index hashes + 1 policy record — even though `left`/`right` are node indices
and all nodes pre-exist (added with `subset` attrs in the node loop above).

## Profile-first

complete_multipartite is DETERMINISTIC (no RNG sampling), so 100% of the edge cost is the per-edge
`add_edge`. Per the barabasi/gnm/gnp calibration, a deterministic insertion-bound generator is a prime
batch candidate — confirmed 13.24x.

## The lever

Collect the cross-partition `(left, right)` INDEX pairs and batch-insert with
`Graph::extend_existing_index_edges_unrecorded`.

## Supersedes a stale surface

The 2026-06-25 ledger surface ("dense generators — complete_multipartite 0.76x — NOT improvable by
batching, construction-floor-bound") was measured at the **Python `add_edges_from` level**. The
**engine** per-edge `add_edge` path (this code) was never batched — and, exactly as gnp (13.20x) and
gnm (8.55x) showed, batching it removes the dominant clones/hashes/policy overhead → 13.24x. The "floor"
was the per-edge overhead, not the construction.

## Byte-identical argument

All nodes pre-exist; cross-partition pairs are unique with no self-loops (distinct partitions).
`extend_existing_index_edges_unrecorded` canonicalizes `edge_index_endpoints` by name-order and pushes
`adj_indices` exactly as `add_edge` (lib.rs:1698-1708); edges collected in the same order. Node attrs
are unchanged (the node loop is untouched). Verified:
`assert_eq!(batch.edges_ordered_borrowed(), string.edges_ordered_borrowed())` + `nodes_ordered`; the
suite's `complete_multipartite_*` vs-nx tests pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib complete_multipartite_batch_ab -- --ignored --nocapture`

K_{500,500} (1000 nodes, 250000 cross edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **13.2407x** | 61/61 | [9.3737, 27.2704] |
| `NULL_batch_vs_batch` | 0.9926x | 29/61 | [0.7986, 1.2191] |

Decisive: candidate p5 (9.37) ~8x above the NULL p95 (1.22); all 61 rounds won.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `complete_multipartite_graph`.
- Test-only: `complete_multipartite_batch_ab` A/B.

## Vein status

Third engine-level generator batch win (gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x); barabasi
1.04x surfaced (sampling-bound). The refined rule holds. Next: dense `watts_strogatz`, `turan_graph` /
`ring_of_cliques` / `stochastic_block_model` (the other 2026-06-25 "floor-bound" dense generators — same
supersession likely if their engine path is per-edge), `gnm_random_digraph` (directed).
