# br-r37-c1-hypercubebatch — hypercube_graph batch-by-index edge insertion

Status: **SHIP.** 6.47x, byte-identical. clippy clean.

## The target

`hypercube_graph(n)` builds the n-dimensional hypercube Q_n on `2^n` nodes carrying binary-tuple labels;
each node connects to its `n` bit-flip neighbours. It is **dense** (`n·2^(n-1)` edges). The native
builder emitted each edge once (a `node < target` guard) via per-edge
`add_edge(labels[node].clone(), labels[target].clone())`; nodes pre-exist (added in index order by an
`add_node` loop). Deterministic (no RNG) → insertion-bound.

## The lever

Collect the `(node, target)` INDEX pairs in the SAME (node, bit) order and batch-insert with
`Graph::extend_existing_index_edges_unrecorded`. Drops per accepted edge: 2 String clones +
2 name→index hashes + 1 runtime-policy record.

## Byte-identical argument

The `node < target` guard means each undirected edge is produced exactly once, and `node ^ mask != node`
→ no self-loops → no duplicates. Nodes pre-exist with `labels[i]` at insertion index `i`, so the emitted
index pairs `(node, target)` are exactly the arguments the per-edge `add_edge(labels[node],
labels[target])` used. `extend_existing_index_edges_unrecorded` canonicalizes endpoints by the SAME node
*names* (`labels[node]` vs `labels[target]`) as `add_edge` — so the endpoint canonicalization is identical
regardless of how the binary-tuple labels sort relative to index order — and pushes `adj_indices` in the
same insertion order. Verified:
- A/B parity: `assert_eq!(batch.edges_ordered_borrowed(), string.edges_ordered_borrowed())` +
  `nodes_ordered` on Q_16.
- Suite exact-vs-nx: `hypercube_graph_three_dimensions_matches_networkx_counts_and_edges` (Q_3),
  `hypercube_graph_one_dimension_uses_singleton_tuple_labels` (Q_1),
  `hypercube_graph_zero_dimension_matches_networkx_empty_graph` (Q_0) all pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib hypercube_batch_ab -- --ignored --nocapture`

Q_16 (65536 nodes, 524288 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **6.4665x** | 61/61 | [5.4167, 7.5610] |
| `NULL_batch_vs_batch` | 1.0066x | 32/61 | [0.8748, 1.1457] |

Decisive: candidate p5 (5.42) ~4.7x above the NULL p95 (1.15); all 61 rounds won. Lower magnitude than
the short-label generators (6.47x vs hkn_harary 19.86x): the long binary-tuple labels make the name-order
endpoint canonicalization compare costlier in both arms, so the win is the dropped clones/hashes/policy.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `hypercube_graph`.
- Test-only: `hypercube_batch_ab` A/B.

## Vein status

Twelfth engine-level generator batch win (gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan
16.22x, ring_of_cliques 19.94x, windmill 18.63x, caveman 3.86x, barbell 16.92x, lollipop 13.29x,
tadpole 7.10x, hkn_harary 19.86x, hypercube 6.47x); barabasi 1.04x surfaced. First win on a generator
with non-sequential (tuple) node labels — confirms the index-batch is label-format-agnostic (canonicalizes
by name). Next clean candidates: `wheel_graph`, `binomial_tree`, `grid_2d_graph`/`grid_graph`.
