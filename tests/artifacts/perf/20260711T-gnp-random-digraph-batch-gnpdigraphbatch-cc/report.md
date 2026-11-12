# br-r37-c1-gnpdigraphbatch — gnp_random_digraph batch-by-index (directed)

Status: **SHIP.** 9.56x, byte-identical. clippy clean.

## The target

`gnp_random_digraph(n, p, seed)` visits every ordered pair `(u, v)` (`u != v`) exactly once, draws
`rng.random()`, and adds the directed edge when `draw < p`. The native builder did per-edge
`add_edge(node_labels[u].clone(), node_labels[v].clone())`; nodes pre-exist (`digraph_with_n_nodes`).
Deterministic given the seed → insertion-bound (no `has_edge`, no dedup — each pair is visited once).

## The lever

Collect the accepted `(u, v)` INDEX pairs in the SAME source-major order and batch-insert with
`DiGraph::extend_existing_index_edges_with_attrs_unrecorded` (empty `AttrMap` per edge = unweighted
`add_edge`). Drops per accepted edge: 2 String clones + 2 name→index hashes + 1 runtime-policy record.

## Byte-identical argument

Each ordered pair is visited exactly once (the `u == v` skip takes no draw), so there are no duplicate
edges and no self-loops — no seen-set needed. The per-pair RNG draw sequence is untouched, so the
accepted-edge sequence is identical to the per-edge loop.
`extend_existing_index_edges_with_attrs_unrecorded` pushes `succ_indices`/`pred_indices` in insertion
order matching `add_edge`. **Verified profile-first** (before the production edit): `gnp_digraph_batch_ab`
parity asserts across 4 configs — `(10,0.5)`, `(50,0.3)`, `(100,0.7)` (dense), `(1000,0.4)` — where
`build_string` is a **verbatim replica** of the production all-pairs loop; all
`assert_eq!(edges_ordered_borrowed + nodes_ordered)` pass.

Note: `gnp_random_digraph` has no dedicated exact-vs-networkx suite test in the crate, so byte-identity
rests on the parity asserts (batch == verbatim production loop). The change preserves the exact prior
production behavior and introduces no regression.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib gnp_digraph_batch_ab -- --ignored --nocapture`

gnp_random_digraph(1000, 0.4) (1000 nodes, 999000 pairs, ~399600 directed edges). 61 rounds. Ratio =
base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **9.5627x** | 61/61 | [5.8644, 18.5493] |
| `NULL_batch_vs_batch` | 1.0040x | 33/61 | [0.8473, 1.1436] |

Decisive: candidate p5 (5.86) ~5.1x above the NULL p95 (1.14); all 61 rounds won. Even though the O(n²)
per-pair RNG draws are common to both arms, the per-edge insertion overhead on the ~400k accepted edges
dominated enough to yield 9.56x.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `gnp_random_digraph`.
- Test-only: `gnp_digraph_batch_ab` A/B.

## Vein status

Twenty-second engine-level generator batch win (second directed). Vein now spans undirected + directed
generators. Next directed candidates: `fast_gnp_random_digraph` (p>=1.0 complete branch),
`random_uniform_k_out_digraph`, `random_k_out_graph`.
