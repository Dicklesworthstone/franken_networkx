# br-r37-c1-cavebatch — caveman_graph batch-by-index edge insertion

Status: **SHIP.** 3.86x, byte-identical. clippy clean.

## The target

`caveman_graph(l, k)` builds `l` disjoint complete cliques of `k` nodes. The edge loop used per-edge
`add_edge(node_labels[left].clone(), node_labels[right].clone())`; nodes pre-exist (`graph_with_n_nodes`).
Deterministic (no RNG) → insertion-bound.

## The lever

Collect the per-clique `(left, right)` INDEX pairs and batch-insert with
`Graph::extend_existing_index_edges_unrecorded`.

## Byte-identical argument

Nodes pre-exist; cliques are disjoint (`step_by(k)`) so all `(left, right)` pairs are unique with no
self-loops. `extend_existing_index_edges_unrecorded` canonicalizes endpoints by name-order + pushes
`adj_indices` exactly as `add_edge`; edges collected in the same per-clique order. Verified:
`assert_eq!(batch.edges_ordered_borrowed(), string.edges_ordered_borrowed())` + `nodes_ordered`; the
suite's caveman vs-nx tests pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib caveman_batch_ab -- --ignored --nocapture`

caveman(100, 60) (6000 nodes, 177000 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **3.8550x** | 61/61 | [3.1643, 26.0222] |
| `NULL_batch_vs_batch` | 1.0032x | 32/61 | [0.8342, 1.2169] |

Decisive: candidate p5 (3.16) ~2.6x above the NULL p95 (1.22); all 61 rounds won. Lower magnitude than
the other clique generators (windmill 18.63x etc.) but still a clean, decidable win.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `caveman_graph`.
- Test-only: `caveman_batch_ab` A/B.

## Vein status

Seventh engine-level generator batch win (gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan
16.22x, ring_of_cliques 19.94x, windmill 18.63x, caveman 3.86x); barabasi 1.04x surfaced. Next: re-scan
`add_edge(node_labels[` sites for remaining deterministic-dense generators.
