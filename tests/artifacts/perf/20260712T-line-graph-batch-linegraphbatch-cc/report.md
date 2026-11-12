# br-r37-c1-linegraphbatch — line_graph hoist + batch

Status: **SHIP.** 4.28x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`line_graph(g)` (fnx-algorithms) builds L(G): a node per input edge, and an L(G) edge for each pair of
input edges sharing a vertex. The inner double loop recomputed `node_i = pair_label(u1, v1)` for **every
`j`**, and inserted each L(G) edge with a per-edge `add_edge`.

## The lever

Two folds: (1) hoist `node_i = pair_label(u1, v1)` **out of the inner `j` loop** (computed once per `i`,
cloned per push), and (2) collect the L(G) edges and insert with one `Graph::extend_edges_unrecorded`.

## Byte-identical argument

Each `i < j` pair is considered exactly once and the input edges are distinct, so every L(G) edge is
unique with no self-loop (`node_i != node_j`). Hoisting `node_i` produces the identical string; the pairs
are collected in the identical order; `extend_edges_unrecorded` canonicalizes + pushes adjacency exactly
as `add_edge` (and dedups, though there are no duplicates). Verified: A/B parity
`assert_eq!(edges_ordered_borrowed + nodes_ordered)` on L(K40); the 10 existing `line_graph*` suite tests
(triangle, directed variants, …) all pass against the batch.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib line_graph_batch_ab -- --ignored --nocapture`

L(K40) — line graph of the complete graph K40 (780 nodes). 61 rounds. Ratio = base/cand, **>1 = batch
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **4.2809x** | 61/61 | [3.3675, 5.7209] |
| `NULL_batch_vs_batch` | 0.9751x | 27/61 | [0.7615, 1.1813] |

Decisive: candidate p5 (3.37) ~2.9x above the NULL p95 (1.18); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production 39549-39574 / test 67044-67175, grep-verified). The
crate has ~12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `line_graph`.
- Test-only: `line_graph_batch_ab` A/B.

## Vein status

Seventh fnx-algorithms result-builder batch. Next: `line_graph_directed`, `power`, `reverse_digraph`.
