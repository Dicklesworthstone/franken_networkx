# br-r37-c1-windbatch — windmill_graph batch-by-index edge insertion

Status: **SHIP.** 18.63x, byte-identical. clippy clean.

## The target

`windmill_graph(n, k)` builds `n` cliques of `k` nodes all sharing the center node 0. The edge loop used
per-edge `add_edge(node_labels[..].clone(), ..)` for both the center→leaf edges and the leaf-clique
edges; nodes pre-exist (`graph_with_n_nodes`). Deterministic (no RNG) → insertion-bound.

## The lever

Collect all `(left, right)` INDEX pairs (center→leaf then leaf-clique, per blade, in the SAME order) and
batch-insert with `Graph::extend_existing_index_edges_unrecorded`.

## Byte-identical argument

Nodes pre-exist. Center edges `(0, leaf)` touch node 0; leaf-clique edges `(left, right)` are among
leaves (≥1) in disjoint per-blade ranges → unique, no self-loops, no center/clique overlap.
`extend_existing_index_edges_unrecorded` canonicalizes endpoints by name-order + pushes `adj_indices`
exactly as `add_edge`; edges collected in the same center-then-clique order. Verified:
`assert_eq!(batch.edges_ordered_borrowed(), string.edges_ordered_borrowed())` + `nodes_ordered`; the
suite's windmill vs-nx tests pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib windmill_batch_ab -- --ignored --nocapture`

windmill(200, 30) (5801 nodes, 87000 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **18.6331x** | 61/61 | [12.5283, 23.2285] |
| `NULL_batch_vs_batch` | 0.9872x | 28/61 | [0.7222, 1.5355] |

Decisive: candidate p5 (12.53) ~8x above the NULL p95 (1.54); all 61 rounds won.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `windmill_graph`.
- Test-only: `windmill_batch_ab` A/B.

## Vein status

Sixth engine-level generator batch win (gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan
16.22x, ring_of_cliques 19.94x, windmill 18.63x); barabasi 1.04x surfaced. The deterministic-dense
generator family (beyond the 2026-06-25 cluster) keeps yielding. Next: `caveman_graph` (2183, same
pattern), then re-scan `add_edge(node_labels[` sites for remaining deterministic-dense generators.
