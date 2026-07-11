# br-r37-c1-bintreebatch — binomial_tree batch-by-index edge insertion

Status: **SHIP.** 6.96x, byte-identical. clippy clean.

## The target

`binomial_tree(n)` builds the order-n binomial tree on `2^n` nodes by repeatedly duplicating the current
tree (shifting all edges by `tree_size`) and linking the two copies with `(0, tree_size)`. It already
accumulates its edges as a `Vec<(usize, usize)>` of INDEX pairs *in add_edge order*, but called per-edge
`add_edge(node_labels[left].clone(), node_labels[right].clone())` interleaved with that accumulation.
Nodes pre-exist (`graph_with_n_nodes`). Deterministic (no RNG) → insertion-bound.

## The lever

Drop the interleaved per-edge `add_edge` and do ONE `Graph::extend_existing_index_edges_unrecorded` over
the already-built `edges` vec at the end. Drops per accepted edge: 2 String clones + 2 name→index
hashes + 1 runtime-policy record.

## Byte-identical argument

The per-edge `add_edge` order is exactly the order edges are appended to `edges` (each iteration: the
shifted-subtree edges, then the `(0, tree_size)` link), so the accumulated vec == the add_edge sequence.
A binomial tree is a **tree** → every pair is unique with no self-loop (`tree_size >= 1` so
`0 != tree_size`; the shift preserves distinctness). `extend_existing_index_edges_unrecorded`
canonicalizes endpoints by node *name* (identical to `add_edge`, so the name-vs-index ordering of
multi-digit labels is irrelevant) and pushes `adj_indices` in the same order. Verified:
- A/B parity: `assert_eq!(edges_ordered_borrowed + nodes_ordered)` of batch vs per-edge for orders
  0, 1, 2, 5, 10, 16 (small orders exercise the multi-digit-label canonicalization) — all pass.
- Suite exact-vs-nx: `binomial_tree_matches_networkx_order_three_labels` (order 3) and
  `binomial_tree_matches_networkx_order_zero_case` (order 0) both pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib binomial_tree_batch_ab -- --ignored --nocapture`

binomial_tree(16) (65536 nodes, 65535 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **6.9641x** | 61/61 | [5.1021, 8.9643] |
| `NULL_batch_vs_batch` | 0.9940x | 28/61 | [0.7878, 1.1050] |

Decisive: candidate p5 (5.10) ~4.6x above the NULL p95 (1.11); all 61 rounds won.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `binomial_tree`.
- Test-only: `binomial_tree_batch_ab` A/B.

## Vein status

Fourteenth engine-level generator batch win (gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan
16.22x, ring_of_cliques 19.94x, windmill 18.63x, caveman 3.86x, barbell 16.92x, lollipop 13.29x,
tadpole 7.10x, hkn_harary 19.86x, hypercube 6.47x, wheel 24.28x, binomial_tree 6.96x); barabasi 1.04x
surfaced. Next clean candidates: `grid_2d_graph`/`grid_graph` (non-periodic), `generalized_petersen_graph`.
