# br-r37-c1-barbellbatch — barbell_graph batch-by-index edge insertion

Status: **SHIP.** 16.92x, byte-identical. Compiles + all functional tests pass. clippy `-D warnings`
NOT re-run: a ~90-min fleet-wide `static.crates.io` download outage flaked every remote build (100+
attempts); per the remote-only directive no local fallback. Code is a line-for-line copy of the 7
already-shipped-and-clippy-passed sibling batch wins, so lint risk is near-zero; shipped under explicit
"commit what compiles" authorization. Re-run clippy when the fleet recovers.

## The target

`barbell_graph(m1, m2)` builds two disjoint complete cliques of `m1` nodes joined by a path of `m2`
nodes, plus two connection edges. The native engine builder used per-edge
`add_edge(node_labels[left].clone(), node_labels[right].clone())` for every clique/path/connection
edge; all nodes pre-exist (`graph_with_n_nodes`). Deterministic (no RNG) → insertion-bound.

## The lever

Collect the `(left, right)` INDEX pairs in the SAME order (left clique, path, right clique, then the
two connection edges) and batch-insert with `Graph::extend_existing_index_edges_unrecorded`. Drops
per accepted edge: 2 String clones + 2 name→index hashes + 1 runtime-policy record.

## Byte-identical argument

Nodes pre-exist. The two cliques (`0..m1`, `m1+m2..2*m1+m2`) are disjoint; the path (`m1..m1+m2`) and
the two connection edges `(m1-1, m1)` / `(m1+m2-1, m1+m2)` bridge disjoint index ranges → every pair
is unique with no self-loops. `extend_existing_index_edges_unrecorded` canonicalizes endpoints by
name-order and pushes `adj_indices` exactly as `add_edge`; edges are collected in the identical
per-block order. Verified three ways:
- A/B parity: `assert_eq!(batch.edges_ordered_borrowed(), string.edges_ordered_borrowed())` +
  `nodes_ordered` on `barbell(600, 10)`.
- Suite exact-vs-nx: `barbell_graph_matches_networkx_direct_join_case` (m2=0 branch) and
  `barbell_graph_matches_networkx_path_connected_case` (m2>0 path branch) both pass.
- `barbell_graph_rejects_m1_below_two_like_networkx` (guard path unchanged) passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib barbell_batch_ab -- --ignored --nocapture`

barbell(600, 10) (1210 nodes, 359411 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **16.9189x** | 61/61 | [13.0812, 25.6003] |
| `NULL_batch_vs_batch` | 1.0333x | 37/61 | [0.9129, 1.2014] |

Decisive: candidate p5 (13.08) ~10.9x above the NULL p95 (1.20); all 61 rounds won.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `barbell_graph`.
- Test-only: `barbell_batch_ab` A/B.

## Vein status

Eighth engine-level generator batch win (gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan
16.22x, ring_of_cliques 19.94x, windmill 18.63x, caveman 3.86x, barbell 16.92x); barabasi 1.04x
surfaced (sampling-bound). Next: re-scan `add_edge(node_labels[` sites for remaining
deterministic-dense generators (lollipop, tadpole, harary).
