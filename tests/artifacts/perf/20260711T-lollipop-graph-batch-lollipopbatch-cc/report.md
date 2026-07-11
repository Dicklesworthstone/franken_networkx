# br-r37-c1-lollipopbatch — lollipop_graph batch-by-index edge insertion

Status: **SHIP.** 13.29x, byte-identical. Compiles + all functional tests pass.

## The target

`lollipop_graph(m, n)` builds a complete clique of `m` nodes with a path of `n` nodes attached by one
connection edge. The native engine builder used per-edge
`add_edge(node_labels[left].clone(), node_labels[right].clone())` for every clique/path/connection
edge; all nodes pre-exist (`graph_with_n_nodes`). Deterministic (no RNG) → insertion-bound. This is
the barbell pattern with a single clique.

## The lever

Collect the `(left, right)` INDEX pairs in the SAME order (clique, path, connection) and batch-insert
with `Graph::extend_existing_index_edges_unrecorded`. Drops per accepted edge: 2 String clones +
2 name→index hashes + 1 runtime-policy record.

## Byte-identical argument

Nodes pre-exist. The clique (`0..m`), path (`m..m+n`), and connection edge `(m-1, m)` span disjoint /
bridging index ranges → every pair is unique with no self-loops.
`extend_existing_index_edges_unrecorded` canonicalizes endpoints by name-order and pushes `adj_indices`
exactly as `add_edge`; edges are collected in the identical per-block order. Verified three ways:
- A/B parity: `assert_eq!(batch.edges_ordered_borrowed(), string.edges_ordered_borrowed())` +
  `nodes_ordered` on `lollipop(800, 10)`.
- Suite exact-vs-nx: `lollipop_graph_matches_networkx_pure_clique_case` (n=0 branch) and
  `lollipop_graph_matches_networkx_clique_plus_path_case` (n>0 branch) both pass.
- `lollipop_graph_rejects_m_below_two_like_networkx` (guard path unchanged) passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib lollipop_batch_ab -- --ignored --nocapture`

lollipop(800, 10) (810 nodes, 319610 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **13.2854x** | 61/61 | [9.5126, 22.8564] |
| `NULL_batch_vs_batch` | 0.9896x | 26/61 | [0.8417, 1.2266] |

Decisive: candidate p5 (9.51) ~7.8x above the NULL p95 (1.23); all 61 rounds won.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `lollipop_graph`.
- Test-only: `lollipop_batch_ab` A/B.

## Vein status

Ninth engine-level generator batch win (gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan
16.22x, ring_of_cliques 19.94x, windmill 18.63x, caveman 3.86x, barbell 16.92x, lollipop 13.29x);
barabasi 1.04x surfaced (sampling-bound). Next dense candidates: tadpole (cycle + tail), harary.
